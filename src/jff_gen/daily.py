import logging
from collections import Counter
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .baskets import build_orders
from .context import BranchInfo, Context
from .defects import inject_row_defects, is_dropout, late_sync_cutoff
from .plan import format_timestamps, make_order_ids, plan_branch_day, plan_order_hours
from .schema import ORDER_CHANGES_COLUMNS
from .sinks import Sink

log = logging.getLogger(__name__)
EXTRA_LOOKBACK_DAYS = 2  # refund delay can spill past max lag by up to ~10 hours


def build_changes(ctx: Context, branch: BranchInfo, day: date) -> pd.DataFrame:
    """Refunds whose effective time falls on `day`, found by replaying earlier branch-day plans."""
    rows = []
    for back in range(ctx.cfg.lifecycle.refund_max_lag_days + EXTRA_LOOKBACK_DAYS):
        plan = plan_branch_day(ctx, branch, day - timedelta(days=back))
        if plan.size == 0:
            continue
        due = ~np.isnat(plan.refund_ts) & (
            plan.refund_ts.astype("datetime64[D]") == np.datetime64(day, "D")
        )
        positions = np.flatnonzero(due)
        if positions.size == 0:
            continue
        order_ids = make_order_ids(branch.branch_id, plan.business_date, positions + 1)
        rows.append(
            pd.DataFrame(
                {
                    "change_id": np.char.add(order_ids, "-RF"),
                    "order_id": order_ids,
                    "previous_status": "completed",
                    "new_status": "refunded",
                    "changed_at": format_timestamps(plan.refund_ts[positions]),
                }
            )
        )
    return (
        pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=ORDER_CHANGES_COLUMNS)
    )


def _split_late(
    orders: pd.DataFrame, items: pd.DataFrame, late: np.ndarray
) -> tuple[tuple[pd.DataFrame, pd.DataFrame], tuple[pd.DataFrame, pd.DataFrame]]:
    late_ids = orders["order_id"][late]
    is_late_item = items["order_id"].isin(late_ids)
    return (orders[~late], items[~is_late_item]), (orders[late], items[is_late_item])


def _branch_file_rows(
    ctx: Context, branch: BranchInfo, day: date, counters: Counter[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Branch export for `day`: its on-time orders plus yesterday's late ones."""
    plan = plan_branch_day(ctx, branch, day)
    orders, items = build_orders(ctx, branch, plan)
    cutoff = late_sync_cutoff(ctx, branch.branch_id, day)
    if cutoff is not None and plan.size:
        late = plan_order_hours(plan) >= cutoff
        (orders, items), _ = _split_late(orders, items, late)
        counters["late_orders_delayed_out"] += int(late.sum())

    previous = day - timedelta(days=1)
    previous_cutoff = late_sync_cutoff(ctx, branch.branch_id, previous)
    if previous_cutoff is not None:
        prev_plan = plan_branch_day(ctx, branch, previous)
        if prev_plan.size:
            prev_orders, prev_items = build_orders(ctx, branch, prev_plan)
            late = plan_order_hours(prev_plan) >= previous_cutoff
            _, (late_orders, late_items) = _split_late(prev_orders, prev_items, late)
            orders = pd.concat([orders, late_orders], ignore_index=True)
            items = pd.concat([items, late_items], ignore_index=True)
            counters["late_orders_delayed_in"] += int(late.sum())
    return inject_row_defects(ctx, orders, items, branch.branch_id, day, counters)


def generate_day(ctx: Context, day: date, sink: Sink) -> dict[str, Any]:
    """Write one day's files branch by branch (bounded memory), then the manifest."""
    injected: Counter[str] = Counter()
    rows: Counter[str] = Counter()
    dropped: list[int] = []
    open_branches = [b for b in ctx.branches if b.open_date <= day]
    with sink.open_day(day) as writer:
        for branch in open_branches:
            if is_dropout(ctx, branch.branch_id, day):
                dropped.append(branch.branch_id)
                continue
            orders, items = _branch_file_rows(ctx, branch, day, injected)
            changes = build_changes(ctx, branch, day)
            for entity, frame in (
                ("orders", orders),
                ("order_items", items),
                ("order_changes", changes),
            ):
                writer.write(entity, frame)
                rows[entity] += len(frame)
    manifest = {
        "date": day.isoformat(),
        "seed": ctx.cfg.seed,
        "scale": ctx.cfg.scale,
        "defects_enabled": ctx.cfg.defects.enabled,
        "expected_branches": len(open_branches),
        "dropped_branch_ids": dropped,
        "rows": dict(rows),
        "injected": dict(injected),
    }
    sink.write_manifest(day, manifest)
    log.info("%s: %s", day, dict(rows))
    return manifest


def generate_range(ctx: Context, start: date, end: date, sink: Sink) -> list[dict[str, Any]]:
    if end < start:
        raise ValueError("end date is before start date")
    days = (end - start).days + 1
    return [generate_day(ctx, start + timedelta(days=i), sink) for i in range(days)]


def write_dimensions(ctx: Context, sink: Sink) -> None:
    for name, frame in ctx.dims.as_files().items():
        sink.write_dimension(name, frame)
