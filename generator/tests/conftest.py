from datetime import date
from pathlib import Path

import pytest

from jff_gen.config import Config, load_config
from jff_gen.context import Context, build_context
from jff_gen.sinks import Sink

START = date(2026, 10, 1)


@pytest.fixture
def cfg() -> Config:
    return load_config().model_copy(update={"n_branches": 8, "scale": 0.05})


@pytest.fixture
def clean_cfg(cfg: Config) -> Config:
    return cfg.model_copy(update={"defects": cfg.defects.model_copy(update={"enabled": False})})


@pytest.fixture
def ctx(cfg: Config) -> Context:
    return build_context(cfg)


@pytest.fixture
def clean_ctx(clean_cfg: Config) -> Context:
    return build_context(clean_cfg)


@pytest.fixture
def sink(tmp_path: Path) -> Sink:
    return Sink(str(tmp_path / "out"))
