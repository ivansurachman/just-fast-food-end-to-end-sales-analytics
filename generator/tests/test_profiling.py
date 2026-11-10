from datetime import date, timedelta
from pathlib import Path

import pytest

from jff_gen.cli import main
from jff_gen.config import Config
from jff_gen.context import build_context
from jff_gen.daily import generate_range, write_dimensions
from jff_gen.profiling import build_profile, defect_reconciliation, load_dataset
from jff_gen.sinks import Sink

START = date(2026, 10, 1)


def _generate(cfg: Config, root: Path, days: int = 4) -> None:
    ctx = build_context(cfg)
    sink = Sink(str(root))
    write_dimensions(ctx, sink)
    generate_range(ctx, START, START + timedelta(days=days - 1), sink)


def test_detected_defects_match_injected_counts(cfg: Config, tmp_path: Path) -> None:
    noisy = cfg.defects.model_copy(
        update={
            "duplicate_row_rate": 0.05,
            "total_mismatch_rate": 0.05,
            "unknown_menu_rate": 0.02,
            "null_platform_ref_rate": 0.1,
            "dirty_payment_rate": 0.1,
            "late_sync_branch_day_rate": 0.3,
            "branch_dropout_rate": 0.1,
        }
    )
    _generate(cfg.model_copy(update={"defects": noisy, "scale": 0.2}), tmp_path)
    table = defect_reconciliation(load_dataset(tmp_path))
    assert (table["match"] == "yes").all(), table
    assert table["detected in data"].gt(0).all(), table


def test_clean_dataset_reports_zero_defects(clean_cfg: Config, tmp_path: Path) -> None:
    _generate(clean_cfg.model_copy(update={"scale": 0.2}), tmp_path)
    table = defect_reconciliation(load_dataset(tmp_path))
    assert (table["detected in data"] == 0).all(), table
    assert (table["match"] == "yes").all()


def test_profile_has_all_sections(cfg: Config, tmp_path: Path) -> None:
    _generate(cfg.model_copy(update={"scale": 0.1}), tmp_path)
    text = build_profile(tmp_path)
    for heading in ("## 1. Overview", "## 3. Orders", "## 5. Order changes", "## 7. Defects"):
        assert heading in text


def test_cli_profile_writes_file(cfg: Config, tmp_path: Path) -> None:
    _generate(cfg.model_copy(update={"scale": 0.1}), tmp_path / "data")
    out = tmp_path / "profile.md"
    assert main(["profile", "--data", str(tmp_path / "data"), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Data profile")


def test_profile_fails_clearly_without_data(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path)


def test_cli_profile_reports_missing_data_as_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["profile", "--data", str(tmp_path)])
    assert exc.value.code == 2
