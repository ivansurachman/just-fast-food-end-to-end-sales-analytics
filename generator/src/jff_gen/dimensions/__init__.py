from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from jff_gen.config import Config

from .branches import build_branches
from .channels import build_channels
from .menu import build_menu
from .promos import build_promos

# One independent generator per dimension table: output file name -> builder.
DIMENSION_BUILDERS: dict[str, Callable[[Config], pd.DataFrame]] = {
    "branches": build_branches,
    "menu_items": build_menu,
    "promos": build_promos,
    "channels": build_channels,
}


@dataclass(frozen=True)
class Dimensions:
    branches: pd.DataFrame
    menu: pd.DataFrame
    promos: pd.DataFrame
    channels: pd.DataFrame

    def as_files(self) -> dict[str, pd.DataFrame]:
        return {
            "branches": self.branches,
            "menu_items": self.menu,
            "promos": self.promos,
            "channels": self.channels,
        }


def build_dimensions(cfg: Config) -> Dimensions:
    return Dimensions(
        branches=build_branches(cfg),
        menu=build_menu(cfg),
        promos=build_promos(cfg),
        channels=build_channels(cfg),
    )
