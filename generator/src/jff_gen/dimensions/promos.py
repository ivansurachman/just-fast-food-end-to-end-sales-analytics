import pandas as pd

from jff_gen.config import Config


def build_promos(cfg: Config) -> pd.DataFrame:
    """Order-level promotions. Usage probability stays in config, it is not a business attribute."""
    rows = []
    for promo in cfg.promos:
        row = promo.model_dump(exclude={"use_probability", "channels", "weekdays"})
        row["channel_scope"] = "|".join(promo.channels)
        row["weekday_scope"] = "|".join(str(d) for d in promo.weekdays)
        rows.append(row)
    return pd.DataFrame(rows)
