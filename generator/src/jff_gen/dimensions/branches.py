from datetime import timedelta

import numpy as np
import pandas as pd

from jff_gen.config import Config
from jff_gen.seeding import make_rng


def build_branches(cfg: Config) -> pd.DataFrame:
    """One row per branch: location, timezone, outlet type, size tier, opening date."""
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
