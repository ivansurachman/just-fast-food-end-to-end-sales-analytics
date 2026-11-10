from dataclasses import dataclass
from datetime import date

import numpy as np

from ._types import Arr
from .context import BranchInfo, Context
from .seeding import make_rng

SECONDS_PER_HOUR = 3600
NAT = np.datetime64("NaT", "s")


@dataclass(frozen=True)
class BranchDayPlan:
    """Cheap, stateless skeleton of one branch-day: when orders happen and their fate."""

    branch_id: int
    business_date: date
    order_ts: Arr  # datetime64[s], ascending; position + 1 is the order sequence number
    channel_idx: Arr
    cancelled: Arr
    refund_ts: Arr  # datetime64[s]; NaT when the order is never refunded

    @property
    def size(self) -> int:
        return int(self.order_ts.shape[0])


def _empty_plan(branch_id: int, day: date) -> BranchDayPlan:
    return BranchDayPlan(
        branch_id=branch_id,
        business_date=day,
        order_ts=np.array([], dtype="datetime64[s]"),
        channel_idx=np.array([], dtype=np.int64),
        cancelled=np.array([], dtype=bool),
        refund_ts=np.array([], dtype="datetime64[s]"),
    )


def expected_orders(ctx: Context, branch: BranchInfo, day: date) -> float:
    volume = ctx.cfg.volume
    expected = (
        volume.base_orders_per_branch_day
        * ctx.cfg.scale
        * branch.size_mult
        * ctx.region_volume[branch.region]
        * volume.weekday_factors[day.weekday()]
    )
    if branch.outlet_type == "cloud_kitchen":
        expected *= volume.cloud_kitchen_mult
    return expected


def _pick(idx: Arr, cum: Arr, uniform: Arr) -> Arr:
    pos = np.minimum(np.searchsorted(cum, uniform, side="right"), len(idx) - 1)
    return idx[pos]


def plan_branch_day(ctx: Context, branch: BranchInfo, day: date) -> BranchDayPlan:
    if day < branch.open_date:
        return _empty_plan(branch.branch_id, day)

    cfg = ctx.cfg
    rng = make_rng(cfg.seed, "plan", day.toordinal(), branch.branch_id)
    sigma = cfg.volume.noise_sigma
    size = int(round(expected_orders(ctx, branch, day) * rng.lognormal(-0.5 * sigma**2, sigma)))

    online_share = (
        1.0 if branch.outlet_type == "cloud_kitchen" else ctx.region_online[branch.region]
    )
    online = rng.random(size) < online_share
    channel_uniform = rng.random(size)
    channel_idx = np.where(
        online,
        _pick(ctx.online_idx, ctx.online_cum, channel_uniform),
        _pick(ctx.offline_idx, np.asarray(ctx.offline_cum), channel_uniform),
    )

    daytype = "weekend" if day.weekday() >= 5 else "weekday"
    hour_uniform = rng.random(size)
    hour_pos = np.where(
        online,
        np.searchsorted(ctx.hour_cum[f"online_{daytype}"], hour_uniform, side="right"),
        np.searchsorted(ctx.hour_cum[f"offline_{daytype}"], hour_uniform, side="right"),
    )
    hour_pos = np.minimum(hour_pos, len(ctx.hours) - 1)
    seconds = ctx.hours[hour_pos] * SECONDS_PER_HOUR + rng.integers(0, SECONDS_PER_HOUR, size)
    order_ts = np.datetime64(day, "s") + seconds.astype("timedelta64[s]")

    sort_order = np.argsort(order_ts, kind="stable")
    order_ts, channel_idx = order_ts[sort_order], channel_idx[sort_order]
    cancelled, refund_ts = _draw_fate(ctx, rng, order_ts, channel_idx)
    return BranchDayPlan(branch.branch_id, day, order_ts, channel_idx, cancelled, refund_ts)


def _draw_fate(
    ctx: Context, rng: np.random.Generator, order_ts: Arr, channel_idx: Arr
) -> tuple[Arr, Arr]:
    life = ctx.cfg.lifecycle
    size = order_ts.shape[0]
    is_online = ctx.channel_is_online[channel_idx]
    cancelled = rng.random(size) < np.where(
        is_online, life.cancel_prob_online, life.cancel_prob_offline
    )
    refund_p = np.where(is_online, life.refund_prob_online, life.refund_prob_offline)
    refunded = ~cancelled & (rng.random(size) < refund_p)
    lag_days = np.minimum(
        rng.geometric(life.refund_lag_geometric_p, size) - 1, life.refund_max_lag_days
    )
    extra_minutes = rng.integers(
        life.refund_extra_minutes_min, life.refund_extra_minutes_max + 1, size
    )
    delay = lag_days.astype("timedelta64[D]") + extra_minutes.astype("timedelta64[m]")
    return cancelled, np.where(refunded, order_ts + delay, NAT)


def plan_order_hours(plan: BranchDayPlan) -> Arr:
    since_midnight = plan.order_ts - plan.order_ts.astype("datetime64[D]")
    return since_midnight.astype("timedelta64[h]").astype(np.int64)


def make_order_ids(branch_id: int, day: date, sequence: Arr) -> Arr:
    prefix = f"B{branch_id:03d}-{day:%Y%m%d}-"
    return np.array([f"{prefix}{int(s):05d}" for s in sequence])


def format_timestamps(values: Arr) -> Arr:
    return np.char.replace(np.datetime_as_string(values, unit="s"), "T", " ")
