import numpy as np
import pandas as pd

from ._types import Arr
from .config import Promo
from .context import BranchInfo, Context
from .plan import BranchDayPlan, format_timestamps, make_order_ids
from .schema import ONLINE_PAYMENT, ORDER_ITEMS_COLUMNS, ORDERS_COLUMNS
from .seeding import make_rng


def _empty_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.DataFrame(columns=ORDERS_COLUMNS), pd.DataFrame(columns=ORDER_ITEMS_COLUMNS)


def _draw_lines(ctx: Context, rng: np.random.Generator, plan: BranchDayPlan) -> tuple[Arr, Arr]:
    """Return (order index, menu position) per line, ordered by order then food before drink."""
    basket = ctx.cfg.basket
    size = plan.size
    online = ctx.channel_is_online[plan.channel_idx]
    extra_food = np.minimum(
        rng.poisson(basket.food_extra_lines_lambda, size), basket.max_food_lines - 1
    )
    food_per_order = 1 + extra_food
    attach = np.where(online, basket.beverage_attach_online, basket.beverage_attach_offline)
    has_drink = rng.random(size) < attach

    food_order = np.repeat(np.arange(size), food_per_order)
    first_food_line = np.arange(food_order.size) == np.repeat(
        np.cumsum(food_per_order) - food_per_order, food_per_order
    )
    main_pick = rng.choice(ctx.main_pos, food_order.size, p=ctx.main_p)
    food_pick = rng.choice(ctx.food_pos, food_order.size, p=ctx.food_p)
    drink_order = np.flatnonzero(has_drink)
    drink_pick = rng.choice(ctx.bev_pos, drink_order.size, p=ctx.bev_p)

    order_idx = np.concatenate([food_order, drink_order])
    menu_pos = np.concatenate([np.where(first_food_line, main_pick, food_pick), drink_pick])
    stable = np.argsort(order_idx, kind="stable")
    return order_idx[stable], menu_pos[stable]


def _promo_discount(promo: Promo, gross: Arr) -> Arr:
    if promo.discount_type == "percent":
        return np.minimum(gross * promo.discount_value // 100, promo.max_discount_amount)
    return np.minimum(promo.discount_value, gross)


def _apply_promos(
    ctx: Context, rng: np.random.Generator, plan: BranchDayPlan, gross: Arr
) -> tuple[Arr, Arr]:
    """Return (promo_id per order, discount per order). One draw per promo keeps streams stable."""
    day = plan.business_date
    channel_ids = ctx.channel_ids[plan.channel_idx]
    chosen = np.full(plan.size, -1)
    for j, promo in enumerate(ctx.cfg.promos):
        draw = rng.random(plan.size)
        if not promo.valid_from <= day <= promo.valid_to:
            continue
        if promo.weekdays and day.weekday() not in promo.weekdays:
            continue
        eligible = np.isin(channel_ids, promo.channels) & (gross >= promo.min_order_amount)
        chosen[(chosen < 0) & eligible & (draw < promo.use_probability)] = j

    discount = np.zeros(plan.size, dtype=np.int64)
    for j, promo in enumerate(ctx.cfg.promos):
        mask = chosen == j
        discount[mask] = _promo_discount(promo, gross)[mask]
    promo_ids = np.array([p.promo_id for p in ctx.cfg.promos] + [""])
    return promo_ids[chosen], discount


def _payment_and_ref(
    ctx: Context, rng: np.random.Generator, plan: BranchDayPlan
) -> tuple[Arr, Arr]:
    online = ctx.channel_is_online[plan.channel_idx]
    mix = ctx.cfg.payment_mix_offline
    methods = list(mix)
    probs = np.array([mix[m] for m in methods])
    offline_payment = rng.choice(methods, plan.size, p=probs / probs.sum())
    payment = np.where(online, ONLINE_PAYMENT, offline_payment)
    number = rng.integers(10_000_000, 99_999_999, plan.size).astype(str)
    prefix = ctx.channel_prefix[plan.channel_idx]
    reference = np.char.add(np.char.add(prefix, "-"), number)
    return payment, np.where(online, reference, "")


def build_orders(
    ctx: Context, branch: BranchInfo, plan: BranchDayPlan
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean orders and order items for one branch-day (business-date view, no defects)."""
    if plan.size == 0:
        return _empty_frames()
    rng = make_rng(ctx.cfg.seed, "basket", plan.business_date.toordinal(), branch.branch_id)
    line_order, line_menu = _draw_lines(ctx, rng, plan)
    first_line = np.searchsorted(line_order, line_order, side="left")
    line_no = np.arange(line_order.size) - first_line + 1
    quantity = rng.choice(np.array([1, 2, 3]), line_order.size, p=ctx.cfg.basket.qty_probs)
    unit_price = ctx.menu_prices[line_menu]
    line_amount = quantity * unit_price
    gross = np.bincount(line_order, weights=line_amount, minlength=plan.size).astype(np.int64)

    promo_id, discount = _apply_promos(ctx, rng, plan, gross)
    payment, platform_ref = _payment_and_ref(ctx, rng, plan)
    total = gross - discount
    online = ctx.channel_is_online[plan.channel_idx]
    commission_rate = ctx.channel_commission[plan.channel_idx]
    commission = np.where(online & ~plan.cancelled, np.rint(total * commission_rate), 0)

    order_ids = make_order_ids(branch.branch_id, plan.business_date, np.arange(1, plan.size + 1))
    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "branch_id": branch.branch_id,
            "channel_id": ctx.channel_ids[plan.channel_idx],
            "order_ts": format_timestamps(plan.order_ts),
            "status": np.where(plan.cancelled, "cancelled", "completed"),
            "gross_amount": gross,
            "discount_amount": discount,
            "promo_id": promo_id,
            "total_amount": total,
            "platform_commission_amount": commission.astype(np.int64),
            "payment_method": payment,
            "platform_order_ref": platform_ref,
        }
    )
    items = pd.DataFrame(
        {
            "order_id": order_ids[line_order],
            "line_no": line_no,
            "menu_item_id": ctx.menu_ids[line_menu],
            "quantity": quantity,
            "unit_price": unit_price,
            "line_amount": line_amount,
        }
    )
    return orders, items
