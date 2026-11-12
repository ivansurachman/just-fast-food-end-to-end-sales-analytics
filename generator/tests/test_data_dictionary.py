import json
from datetime import date
from pathlib import Path

import pandas as pd

from jff_gen.config import Config
from jff_gen.context import build_context
from jff_gen.daily import generate_day, write_dimensions
from jff_gen.sinks import Sink

DOC = Path(__file__).resolve().parents[2] / "docs" / "data-dictionary.md"
DAY = date(2026, 10, 5)


def _documented_columns() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("### `"):
            current = line.split("`")[1]
            sections[current] = []
        elif line.startswith("#"):
            current = None
        elif current and line.startswith("| `"):
            sections[current].append(line.split("`")[1])
    return sections


def _header(path: Path) -> list[str]:
    return list(pd.read_csv(path, nrows=0).columns)


def test_dictionary_lists_exactly_the_columns_in_the_csv_files(cfg: Config, tmp_path: Path) -> None:
    ctx = build_context(cfg)
    sink = Sink(str(tmp_path))
    write_dimensions(ctx, sink)
    generate_day(ctx, DAY, sink)
    documented = _documented_columns()
    actual = {
        "orders": _header(tmp_path / "orders" / f"dt={DAY}" / "orders.csv"),
        "order_items": _header(tmp_path / "order_items" / f"dt={DAY}" / "order_items.csv"),
        "order_changes": _header(tmp_path / "order_changes" / f"dt={DAY}" / "order_changes.csv"),
        "branches": _header(tmp_path / "dimensions" / "branches.csv"),
        "menu_items": _header(tmp_path / "dimensions" / "menu_items.csv"),
        "promos": _header(tmp_path / "dimensions" / "promos.csv"),
        "channels": _header(tmp_path / "dimensions" / "channels.csv"),
    }
    for entity, columns in actual.items():
        assert documented[entity] == columns, entity


def test_dictionary_covers_every_manifest_field(cfg: Config, tmp_path: Path) -> None:
    noisy = cfg.defects.model_copy(
        update={
            "duplicate_row_rate": 0.1,
            "total_mismatch_rate": 0.1,
            "unknown_menu_rate": 0.05,
            "null_platform_ref_rate": 0.3,
            "dirty_payment_rate": 0.3,
            "late_sync_branch_day_rate": 1.0,
        }
    )
    ctx = build_context(cfg.model_copy(update={"defects": noisy, "scale": 0.3}))
    generate_day(ctx, DAY, Sink(str(tmp_path)))
    manifest = json.loads((tmp_path / "_manifests" / f"dt={DAY}" / "manifest.json").read_text())
    flat = {k for k, v in manifest.items() if not isinstance(v, dict)}
    flat |= {f"{k}.{inner}" for k, v in manifest.items() if isinstance(v, dict) for inner in v}
    documented = set(_documented_columns()["manifest.json"])
    assert flat <= documented, flat - documented
    assert {k for k in documented if "." not in k} == {
        k for k, v in manifest.items() if not isinstance(v, dict)
    }
