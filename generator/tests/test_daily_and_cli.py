import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from jff_gen.cli import main
from jff_gen.config import Config
from jff_gen.context import Context, build_context
from jff_gen.daily import generate_day, generate_range
from jff_gen.sinks import Sink

START = date(2026, 10, 1)


def _digests(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _read(root: Path, entity: str, day: date) -> pd.DataFrame:
    path = root / entity / f"dt={day.isoformat()}" / f"{entity}.csv"
    return pd.read_csv(path, keep_default_na=False)


def test_rerun_same_date_is_byte_identical(ctx: Context, tmp_path: Path) -> None:
    for name in ("a", "b"):
        generate_day(ctx, START, Sink(str(tmp_path / name)))
    assert _digests(tmp_path / "a") == _digests(tmp_path / "b")


def test_range_equals_single_days(ctx: Context, tmp_path: Path) -> None:
    generate_range(ctx, START, START + timedelta(days=3), Sink(str(tmp_path / "range")))
    for i in range(4):
        generate_day(ctx, START + timedelta(days=i), Sink(str(tmp_path / "single")))
    assert _digests(tmp_path / "range") == _digests(tmp_path / "single")


def test_different_seed_changes_output(cfg: Config, tmp_path: Path) -> None:
    other = build_context(cfg.model_copy(update={"seed": 7}))
    generate_day(build_context(cfg), START, Sink(str(tmp_path / "a")))
    generate_day(other, START, Sink(str(tmp_path / "b")))
    assert _digests(tmp_path / "a") != _digests(tmp_path / "b")


def test_manifest_row_counts_match_files(ctx: Context, tmp_path: Path) -> None:
    manifest = generate_day(ctx, START, Sink(str(tmp_path)))
    for entity in ("orders", "order_items", "order_changes"):
        assert manifest["rows"].get(entity, 0) == len(_read(tmp_path, entity, START))
    on_disk = json.loads((tmp_path / "_manifests" / f"dt={START}" / "manifest.json").read_text())
    assert on_disk == json.loads(json.dumps(manifest))


def test_clean_mode_has_no_injected_defects(clean_ctx: Context, tmp_path: Path) -> None:
    manifest = generate_day(clean_ctx, START, Sink(str(tmp_path)))
    assert manifest["injected"] == {}
    assert manifest["dropped_branch_ids"] == []
    orders = _read(tmp_path, "orders", START)
    assert orders["order_id"].is_unique
    assert (orders["order_ts"].str[:10] == START.isoformat()).all()


def test_injected_counts_match_detectable_defects(cfg: Config, tmp_path: Path) -> None:
    noisy = cfg.defects.model_copy(
        update={
            "duplicate_row_rate": 0.05,
            "total_mismatch_rate": 0.05,
            "unknown_menu_rate": 0.02,
            "null_platform_ref_rate": 0.1,
            "dirty_payment_rate": 0.1,
            "late_sync_branch_day_rate": 0.0,
            "branch_dropout_rate": 0.0,
        }
    )
    ctx = build_context(cfg.model_copy(update={"defects": noisy, "scale": 0.2}))
    manifest = generate_day(ctx, START, Sink(str(tmp_path)))
    injected = manifest["injected"]
    orders = _read(tmp_path, "orders", START)
    items = _read(tmp_path, "order_items", START)

    assert orders.duplicated().sum() == injected["duplicate_orders"]
    assert items.duplicated().sum() == injected["duplicate_item_rows"]

    orders, items = orders.drop_duplicates(), items.drop_duplicates()
    unknown = ~items["menu_item_id"].isin(ctx.dims.menu["menu_item_id"])
    assert unknown.sum() == injected["unknown_menu_item"]

    line_sum = items.groupby("order_id")["line_amount"].sum()
    mismatch = orders["gross_amount"].to_numpy() != line_sum.reindex(orders["order_id"]).to_numpy()
    assert mismatch.sum() == injected["gross_mismatch"] > 0

    is_online = orders["channel_id"].isin(["grabfood", "gofood", "shopeefood"])
    assert (is_online & (orders["platform_order_ref"] == "")).sum() == injected["platform_ref_null"]
    offline = orders[~is_online]
    assert (offline["payment_method"] == "").sum() == injected["payment_null"] > 0
    clean_values = {"cash", "qris", "ewallet", "card", ""}
    assert (~offline["payment_method"].isin(clean_values)).sum() == injected["payment_variant"] > 0


def test_late_orders_arrive_in_next_days_file(cfg: Config, tmp_path: Path) -> None:
    always_late = cfg.defects.model_copy(
        update={
            "late_sync_branch_day_rate": 1.0,
            "branch_dropout_rate": 0.0,
            "late_sync_cutoff_hour_min": 18,
            "late_sync_cutoff_hour_max": 18,
            "duplicate_row_rate": 0.0,
        }
    )
    ctx = build_context(cfg.model_copy(update={"defects": always_late, "scale": 0.2}))
    generate_range(ctx, START, START + timedelta(days=1), Sink(str(tmp_path)))
    day1 = _read(tmp_path, "orders", START)
    day2 = _read(tmp_path, "orders", START + timedelta(days=1))
    own_day = day1[day1["order_ts"].str[:10] == START.isoformat()]
    assert (own_day["order_ts"].str[11:13].astype(int) < 18).all()
    arrived = day2[day2["order_ts"].str[:10] == START.isoformat()]
    assert len(arrived) > 0
    assert (arrived["order_ts"].str[11:13].astype(int) >= 18).all()


def test_dropout_branch_writes_nothing(cfg: Config, tmp_path: Path) -> None:
    dropout = cfg.defects.model_copy(update={"branch_dropout_rate": 1.0})
    ctx = build_context(cfg.model_copy(update={"defects": dropout}))
    manifest = generate_day(ctx, START, Sink(str(tmp_path)))
    assert len(manifest["dropped_branch_ids"]) == manifest["expected_branches"]
    assert _read(tmp_path, "orders", START).empty


def test_every_refund_points_to_an_existing_order(clean_cfg: Config, tmp_path: Path) -> None:
    ctx = build_context(clean_cfg.model_copy(update={"scale": 0.2}))
    end = START + timedelta(days=12)
    generate_range(ctx, START, end, Sink(str(tmp_path)))
    orders = pd.concat([_read(tmp_path, "orders", START + timedelta(days=i)) for i in range(13)])
    changes = pd.concat(
        [_read(tmp_path, "order_changes", START + timedelta(days=i)) for i in range(13)]
    )
    in_window = changes[changes["order_id"].str[5:13] >= START.strftime("%Y%m%d")]
    assert len(in_window) > 0
    assert in_window["order_id"].isin(orders["order_id"]).all()
    assert changes["change_id"].is_unique


def test_cli_dims_and_generate(tmp_path: Path) -> None:
    out = str(tmp_path / "out")
    assert main(["dim", "all", "--out", out, "--branches", "5"]) == 0
    assert (
        main(
            [
                "generate",
                "--start",
                "2026-10-01",
                "--end",
                "2026-10-02",
                "--out",
                out,
                "--branches",
                "5",
                "--scale",
                "0.02",
                "--clean",
            ]
        )
        == 0
    )
    root = tmp_path / "out"
    assert (root / "dimensions" / "branches.csv").exists()
    assert (root / "orders" / "dt=2026-10-02" / "orders.csv").exists()
    assert (root / "_manifests" / "dt=2026-10-01" / "manifest.json").exists()


def test_cli_writes_a_single_dimension_only(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["dim", "menu_items", "--out", str(out)]) == 0
    assert sorted(p.name for p in (out / "dimensions").iterdir()) == ["menu_items.csv"]
