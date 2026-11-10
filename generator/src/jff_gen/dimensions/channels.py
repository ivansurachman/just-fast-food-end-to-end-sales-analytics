import pandas as pd

from jff_gen.config import Config

COLUMNS = ["channel_id", "order_origin", "platform", "service_type", "commission_rate"]


def build_channels(cfg: Config) -> pd.DataFrame:
    """Five sales channels, split into origin, platform and service type."""
    return pd.DataFrame([c.model_dump() for c in cfg.channels])[COLUMNS]
