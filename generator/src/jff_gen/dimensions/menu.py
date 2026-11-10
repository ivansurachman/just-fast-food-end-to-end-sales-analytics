import pandas as pd

from jff_gen.config import Config

COLUMNS = ["menu_item_id", "item_name", "category", "unit_price", "unit_cost"]


def build_menu(cfg: Config) -> pd.DataFrame:
    """Static menu with a fixed unit cost (COGS) per item."""
    return pd.DataFrame([m.model_dump() for m in cfg.menu])[COLUMNS].assign(is_active=True)
