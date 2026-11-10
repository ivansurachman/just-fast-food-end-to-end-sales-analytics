from datetime import date, timedelta

import numpy as np

from jff_gen.baskets import build_orders
from jff_gen.config import Config
from jff_gen.context import Context, build_context
from jff_gen.plan import plan_branch_day, plan_order_hours

DAY = date(2026, 10, 7)


def test_plan_is_stateless_and_deterministic(ctx: Context) -> None:
    branch = ctx.branches[0]
    first = plan_branch_day(ctx, branch, DAY)
    plan_branch_day(ctx, ctx.branches[1], DAY)  # other calls must not disturb it
    second = plan_branch_day(ctx, branch, DAY)
    assert np.array_equal(first.order_ts, second.order_ts)
    assert np.array_equal(first.cancelled, second.cancelled)


def test_orders_are_sorted_and_inside_opening_hours(ctx: Context) -> None:
    plan = plan_branch_day(ctx, ctx.branches[0], DAY)
    assert plan.size > 0
    assert (np.diff(plan.order_ts.astype("int64")) >= 0).all()
    hours = plan_order_hours(plan)
    assert hours.min() >= ctx.cfg.time.open_hour
    assert hours.max() < ctx.cfg.time.close_hour
    assert (plan.order_ts.astype("datetime64[D]") == np.datetime64(DAY, "D")).all()


def test_volume_scales_with_scale_factor(cfg: Config) -> None:
    small = build_context(cfg.model_copy(update={"scale": 0.05}))
    large = build_context(cfg.model_copy(update={"scale": 0.5}))
    total_small = sum(plan_branch_day(small, b, DAY).size for b in small.branches)
    total_large = sum(plan_branch_day(large, b, DAY).size for b in large.branches)
    assert 7 < total_large / total_small < 13


def test_lunch_and_dinner_peaks_beat_midafternoon(cfg: Config) -> None:
    ctx = build_context(cfg.model_copy(update={"scale": 0.5, "n_branches": 20}))
    hours = np.concatenate([plan_order_hours(plan_branch_day(ctx, b, DAY)) for b in ctx.branches])
    counts = np.bincount(hours, minlength=24)
    assert counts[12] > counts[15]
    assert counts[19] > counts[15]
    assert counts[19] > counts[10]


def test_cloud_kitchen_has_no_offline_orders(cfg: Config) -> None:
    ctx = build_context(cfg.model_copy(update={"n_branches": 40, "scale": 0.1}))
    kitchens = [b for b in ctx.branches if b.outlet_type == "cloud_kitchen"]
    assert kitchens
    for branch in kitchens:
        plan = plan_branch_day(ctx, branch, DAY)
        assert ctx.channel_is_online[plan.channel_idx].all()


def test_refunds_only_for_completed_orders_and_after_order_time(ctx: Context) -> None:
    for branch in ctx.branches:
        for offset in range(5):
            plan = plan_branch_day(ctx, branch, DAY + timedelta(days=offset))
            refunded = ~np.isnat(plan.refund_ts)
            assert not (refunded & plan.cancelled).any()
            assert (plan.refund_ts[refunded] > plan.order_ts[refunded]).all()


def test_clean_orders_reconcile(clean_ctx: Context) -> None:
    ctx = clean_ctx
    branch = ctx.branches[0]
    orders, items = build_orders(ctx, branch, plan_branch_day(ctx, branch, DAY))
    assert orders["order_id"].is_unique
    assert set(items["order_id"]) == set(orders["order_id"])
    line_sum = items.groupby("order_id")["line_amount"].sum()
    merged = orders.set_index("order_id")
    assert (merged["gross_amount"] == line_sum.reindex(merged.index)).all()
    assert (merged["total_amount"] == merged["gross_amount"] - merged["discount_amount"]).all()
    assert (merged["discount_amount"] <= merged["gross_amount"]).all()
    assert (items["line_amount"] == items["quantity"] * items["unit_price"]).all()
    assert set(items["menu_item_id"]) <= set(ctx.dims.menu["menu_item_id"])


def test_commission_only_on_online_non_cancelled(clean_ctx: Context) -> None:
    ctx = clean_ctx
    branch = ctx.branches[0]
    orders, _ = build_orders(ctx, branch, plan_branch_day(ctx, branch, DAY))
    paid_commission = orders["platform_commission_amount"] > 0
    is_online = orders["channel_id"].isin(["grabfood", "gofood", "shopeefood"])
    assert not (paid_commission & ~is_online).any()
    assert not (paid_commission & (orders["status"] == "cancelled")).any()
    assert (
        orders.loc[is_online & (orders["status"] == "completed"), "platform_order_ref"] != ""
    ).all()
