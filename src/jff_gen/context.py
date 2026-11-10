from dataclasses import dataclass
from datetime import date

import numpy as np

from ._types import Arr
from .config import Config
from .dimensions import Dimensions, build_dimensions

PEAK_KEYS = ("offline_weekday", "offline_weekend", "online_weekday", "online_weekend")


@dataclass(frozen=True)
class BranchInfo:
    branch_id: int
    region: str
    outlet_type: str
    size_mult: float
    open_date: date


@dataclass(frozen=True)
class Context:
    """Everything derived from config once, so per-day code stays small and cheap."""

    cfg: Config
    dims: Dimensions
    branches: tuple[BranchInfo, ...]
    region_volume: dict[str, float]
    region_online: dict[str, float]
    channel_ids: Arr
    channel_is_online: Arr
    channel_commission: Arr
    channel_prefix: Arr
    offline_idx: Arr
    offline_cum: Arr
    online_idx: Arr
    online_cum: Arr
    hours: Arr
    hour_cum: dict[str, Arr]
    menu_ids: Arr
    menu_prices: Arr
    main_pos: Arr
    main_p: Arr
    food_pos: Arr
    food_p: Arr
    bev_pos: Arr
    bev_p: Arr


def _cumulative(weights: Arr) -> Arr:
    cum = np.cumsum(weights / weights.sum())
    cum[-1] = 1.0
    return cum


def _hour_cumulative(cfg: Config, hours: Arr) -> dict[str, Arr]:
    result = {}
    for key in PEAK_KEYS:
        mid = hours + 0.5
        density = np.zeros(len(hours))
        for peak in cfg.time.peaks[key]:
            density += peak.weight * np.exp(-0.5 * ((mid - peak.center) / peak.sigma) ** 2)
        result[key] = _cumulative(density)
    return result


def _channel_groups(cfg: Config, online: bool) -> tuple[Arr, Arr]:
    idx = np.array(
        [i for i, c in enumerate(cfg.channels) if (c.order_origin == "online") == online]
    )
    weights = np.array([cfg.channels[i].mix_weight for i in idx], dtype=float)
    return idx, _cumulative(weights)


def _menu_group(cfg: Config, categories: set[str]) -> tuple[Arr, Arr]:
    pos = np.array([i for i, m in enumerate(cfg.menu) if m.category in categories])
    weights = np.array([cfg.menu[i].popularity for i in pos], dtype=float)
    return pos, weights / weights.sum()


def build_context(cfg: Config) -> Context:
    dims = build_dimensions(cfg)
    table = dims.branches
    branches = tuple(
        BranchInfo(
            branch_id=branch_id,
            region=region,
            outlet_type=outlet_type,
            size_mult=cfg.volume.size_tiers[size_tier],
            open_date=open_date,
        )
        for branch_id, region, outlet_type, size_tier, open_date in zip(
            table["branch_id"].tolist(),
            table["region"].tolist(),
            table["outlet_type"].tolist(),
            table["size_tier"].tolist(),
            table["open_date"].tolist(),
            strict=True,
        )
    )
    offline_idx, offline_cum = _channel_groups(cfg, online=False)
    online_idx, online_cum = _channel_groups(cfg, online=True)
    hours = np.arange(cfg.time.open_hour, cfg.time.close_hour)
    main_pos, main_p = _menu_group(cfg, {"main"})
    food_pos, food_p = _menu_group(cfg, {"main", "side", "dessert"})
    bev_pos, bev_p = _menu_group(cfg, {"beverage"})
    return Context(
        cfg=cfg,
        dims=dims,
        branches=branches,
        region_volume={k: v.volume_mult for k, v in cfg.regions.items()},
        region_online={k: v.online_share for k, v in cfg.regions.items()},
        channel_ids=np.array([c.channel_id for c in cfg.channels]),
        channel_is_online=np.array([c.order_origin == "online" for c in cfg.channels]),
        channel_commission=np.array([c.commission_rate for c in cfg.channels]),
        channel_prefix=np.array([c.platform_ref_prefix for c in cfg.channels]),
        offline_idx=offline_idx,
        offline_cum=offline_cum,
        online_idx=online_idx,
        online_cum=online_cum,
        hours=hours,
        hour_cum=_hour_cumulative(cfg, hours),
        menu_ids=np.array([m.menu_item_id for m in cfg.menu]),
        menu_prices=np.array([m.unit_price for m in cfg.menu], dtype=np.int64),
        main_pos=main_pos,
        main_p=main_p,
        food_pos=food_pos,
        food_p=food_p,
        bev_pos=bev_pos,
        bev_p=bev_p,
    )
