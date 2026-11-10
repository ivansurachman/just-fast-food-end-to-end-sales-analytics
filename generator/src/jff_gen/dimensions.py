from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import Config
from .seeding import make_rng


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


def build_branches(cfg: Config) -> pd.DataFrame:
    rng = make_rng(cfg.seed, "dim_branch")
    count = cfg.n_branches
    weights = np.array([c.weight for c in cfg.cities], dtype=float)
    city_idx = rng.choice(len(cfg.cities), size=count, p=weights / weights.sum())
    tiers = list(cfg.volume.size_tier_probs)
    tier_p = np.array([cfg.volume.size_tier_probs[t] for t in tiers])
    size_tier = rng.choice(tiers, size=count, p=tier_p / tier_p.sum())
    is_cloud = rng.random(count) < cfg.volume.cloud_kitchen_share
    span_days = (cfg.branch_open_end - cfg.branch_open_start).days
    open_offsets = rng.integers(0, span_days + 1, size=count)

    seen_per_city: dict[str, int] = {}
    rows = []
    for i in range(count):
        city = cfg.cities[int(city_idx[i])]
        seen_per_city[city.name] = seen_per_city.get(city.name, 0) + 1
        rows.append(
            {
                "branch_id": i + 1,
                "branch_code": f"B{i + 1:03d}",
                "branch_name": f"Just Fast Food {city.name} {seen_per_city[city.name]:02d}",
                "city": city.name,
                "region": city.region,
                "timezone": city.timezone,
                "outlet_type": "cloud_kitchen" if is_cloud[i] else "restaurant",
                "size_tier": str(size_tier[i]),
                "open_date": cfg.branch_open_start + timedelta(days=int(open_offsets[i])),
            }
        )
    return pd.DataFrame(rows)


def build_menu(cfg: Config) -> pd.DataFrame:
    columns = ["menu_item_id", "item_name", "category", "unit_price", "unit_cost"]
    return pd.DataFrame([m.model_dump() for m in cfg.menu])[columns].assign(is_active=True)


def build_promos(cfg: Config) -> pd.DataFrame:
    rows = []
    for promo in cfg.promos:
        row = promo.model_dump(exclude={"use_probability", "channels", "weekdays"})
        row["channel_scope"] = "|".join(promo.channels)
        row["weekday_scope"] = "|".join(str(d) for d in promo.weekdays)
        rows.append(row)
    return pd.DataFrame(rows)


def build_channels(cfg: Config) -> pd.DataFrame:
    columns = ["channel_id", "order_origin", "platform", "service_type", "commission_rate"]
    return pd.DataFrame([c.model_dump() for c in cfg.channels])[columns]


def build_dimensions(cfg: Config) -> Dimensions:
    return Dimensions(
        branches=build_branches(cfg),
        menu=build_menu(cfg),
        promos=build_promos(cfg),
        channels=build_channels(cfg),
    )


def is_branch_open(open_date: date, day: date) -> bool:
    return open_date <= day
