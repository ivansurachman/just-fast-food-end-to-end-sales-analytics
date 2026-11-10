from collections import Counter
from datetime import date

import numpy as np
import pandas as pd

from ._types import Arr
from .context import Context
from .schema import ONLINE_PAYMENT, PAYMENT_VARIANTS
from .seeding import make_rng

MISMATCH_DELTAS = np.array([-500, -100, 100, 500, 1000])
VARIANTS_PER_METHOD = 3


def is_dropout(ctx: Context, branch_id: int, day: date) -> bool:
    """Branch sent no files at all for this day (POS or network outage)."""
    defects = ctx.cfg.defects
    if not defects.enabled:
        return False
    rng = make_rng(ctx.cfg.seed, "dropout", day.toordinal(), branch_id)
    return bool(rng.random() < defects.branch_dropout_rate)


def late_sync_cutoff(ctx: Context, branch_id: int, day: date) -> int | None:
    """Hour from which the day's orders only reach us in the next day's file."""
    defects = ctx.cfg.defects
    if not defects.enabled or is_dropout(ctx, branch_id, day):
        return None
    rng = make_rng(ctx.cfg.seed, "late", day.toordinal(), branch_id)
    if rng.random() >= defects.late_sync_branch_day_rate:
        return None
    low, high = defects.late_sync_cutoff_hour_min, defects.late_sync_cutoff_hour_max
    return int(rng.integers(low, high + 1))


def _pick(rng: np.random.Generator, size: int, rate: float) -> Arr:
    return np.flatnonzero(rng.random(size) < rate)


def _mismatch_gross(
    rng: np.random.Generator, orders: pd.DataFrame, rate: float, log: Counter[str]
) -> pd.DataFrame:
    rows = _pick(rng, len(orders), rate)
    gross = orders["gross_amount"].to_numpy(copy=True)
    total = orders["total_amount"].to_numpy(copy=True)
    gross[rows] += rng.choice(MISMATCH_DELTAS, rows.size)
    total[rows] = gross[rows] - orders["discount_amount"].to_numpy()[rows]
    log["gross_mismatch"] += int(rows.size)
    return orders.assign(gross_amount=gross, total_amount=total)


def _null_platform_ref(
    rng: np.random.Generator, orders: pd.DataFrame, rate: float, log: Counter[str]
) -> pd.DataFrame:
    ref = orders["platform_order_ref"].to_numpy(dtype=object, copy=True)
    rows = _pick(rng, len(orders), rate)
    rows = rows[ref[rows] != ""]
    ref[rows] = ""
    log["platform_ref_null"] += int(rows.size)
    return orders.assign(platform_order_ref=ref)


def _dirty_payment(
    rng: np.random.Generator, orders: pd.DataFrame, rate: float, log: Counter[str]
) -> pd.DataFrame:
    payment = orders["payment_method"].to_numpy(dtype=object, copy=True)
    rows = _pick(rng, len(orders), rate)
    rows = rows[payment[rows] != ONLINE_PAYMENT]
    use_null = rng.random(rows.size) < 0.5
    variant = rng.integers(0, VARIANTS_PER_METHOD, rows.size)
    for row, is_null, pick in zip(rows, use_null, variant, strict=True):
        payment[row] = "" if is_null else PAYMENT_VARIANTS[payment[row]][int(pick)]
        log["payment_null" if is_null else "payment_variant"] += 1
    return orders.assign(payment_method=payment)


def _unknown_menu(
    rng: np.random.Generator, items: pd.DataFrame, rate: float, log: Counter[str]
) -> pd.DataFrame:
    menu_ids = items["menu_item_id"].to_numpy(dtype=object, copy=True)
    rows = _pick(rng, len(items), rate)
    codes = rng.integers(100, 999, rows.size)
    for row, code in zip(rows, codes, strict=True):
        menu_ids[row] = f"MI-X{int(code)}"
    log["unknown_menu_item"] += int(rows.size)
    return items.assign(menu_item_id=menu_ids)


def _duplicate_rows(
    rng: np.random.Generator,
    orders: pd.DataFrame,
    items: pd.DataFrame,
    rate: float,
    log: Counter[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    resent = orders.iloc[_pick(rng, len(orders), rate)]
    resent_items = items[items["order_id"].isin(resent["order_id"])]
    log["duplicate_orders"] += len(resent)
    log["duplicate_item_rows"] += len(resent_items)
    return (
        pd.concat([orders, resent], ignore_index=True),
        pd.concat([items, resent_items], ignore_index=True),
    )


def inject_row_defects(
    ctx: Context,
    orders: pd.DataFrame,
    items: pd.DataFrame,
    branch_id: int,
    day: date,
    log: Counter[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return defective copies of the frames. Counts per defect type go into `log`."""
    defects = ctx.cfg.defects
    if not defects.enabled or orders.empty:
        return orders, items
    rng = make_rng(ctx.cfg.seed, "defects", day.toordinal(), branch_id)
    orders = _mismatch_gross(rng, orders, defects.total_mismatch_rate, log)
    orders = _null_platform_ref(rng, orders, defects.null_platform_ref_rate, log)
    orders = _dirty_payment(rng, orders, defects.dirty_payment_rate, log)
    items = _unknown_menu(rng, items, defects.unknown_menu_rate, log)
    return _duplicate_rows(rng, orders, items, defects.duplicate_row_rate, log)
