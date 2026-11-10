"""Profile a generated dataset (local path) and render the result as Markdown."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

CLEAN_PAYMENTS = {"cash", "qris", "ewallet", "card"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PERCENTILE_HIGH = 0.95


@dataclass(frozen=True)
class Dataset:
    root: Path
    orders: pd.DataFrame
    items: pd.DataFrame
    changes: pd.DataFrame
    branches: pd.DataFrame
    menu: pd.DataFrame
    channels: pd.DataFrame
    promos: pd.DataFrame
    manifests: list[dict[str, Any]]


def _read_daily(root: Path, entity: str) -> pd.DataFrame:
    frames = []
    for path in sorted((root / entity).glob("dt=*/*.csv")):
        frame = pd.read_csv(path, keep_default_na=False)
        frame["source_file_date"] = path.parent.name.removeprefix("dt=")
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"no {entity} files under {root}")
    return pd.concat(frames, ignore_index=True)


def load_dataset(root: Path) -> Dataset:
    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "_manifests").glob("dt=*/manifest.json"))
    ]
    if not manifests:
        raise FileNotFoundError(f"no manifests under {root}")
    dim = root / "dimensions"
    read = lambda name: pd.read_csv(dim / f"{name}.csv", keep_default_na=False)  # noqa: E731
    return Dataset(
        root=root,
        orders=_read_daily(root, "orders"),
        items=_read_daily(root, "order_items"),
        changes=_read_daily(root, "order_changes"),
        branches=read("branches"),
        menu=read("menu_items"),
        channels=read("channels"),
        promos=read("promos"),
        manifests=manifests,
    )


def _md_table(frame: pd.DataFrame) -> str:
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    divider = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, divider, *rows])


def _share(counts: pd.Series) -> pd.DataFrame:
    shares = (100 * counts / counts.sum()).round(1).astype(str) + "%"
    return pd.DataFrame({"count": counts.map("{:,}".format), "share": shares}).reset_index()


def _stats(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
        values = frame[column]
        rows.append(
            {
                "column": column,
                "min": f"{values.min():,.0f}",
                "mean": f"{values.mean():,.0f}",
                "median": f"{values.median():,.0f}",
                "p95": f"{values.quantile(PERCENTILE_HIGH):,.0f}",
                "max": f"{values.max():,.0f}",
            }
        )
    return pd.DataFrame(rows)


def _unique_orders(ds: Dataset) -> pd.DataFrame:
    orders = ds.orders.drop_duplicates()
    online_ids = set(ds.channels.loc[ds.channels["order_origin"] == "online", "channel_id"])
    return orders.assign(
        order_date=orders["order_ts"].str[:10],
        hour=orders["order_ts"].str[11:13].astype(int),
        is_online=orders["channel_id"].isin(online_ids),
    )


def _total_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def section_overview(ds: Dataset) -> str:
    orders = _unique_orders(ds)
    days = sorted(str(m["date"]) for m in ds.manifests)
    per_branch_day = orders.groupby(["order_date", "branch_id"]).size()
    rows = pd.DataFrame(
        [
            ("Date range (file dates)", f"{days[0]} to {days[-1]} ({len(days)} days)"),
            ("Seed / scale", f"{ds.manifests[0]['seed']} / {ds.manifests[0]['scale']}"),
            ("orders rows (raw / unique)", f"{len(ds.orders):,} / {len(orders):,}"),
            (
                "order_items rows (raw / unique)",
                f"{len(ds.items):,} / {len(ds.items.drop_duplicates()):,}",
            ),
            ("order_changes rows", f"{len(ds.changes):,}"),
            ("Orders per branch-day (mean / p5 / p95)", _spread(per_branch_day)),
            ("Size on disk", f"{_total_bytes(ds.root) / 1_048_576:,.1f} MB"),
        ],
        columns=["item", "value"],
    )
    return "## 1. Overview\n\n" + _md_table(rows)


def _spread(values: pd.Series) -> str:
    return f"{values.mean():,.0f} / {values.quantile(0.05):,.0f} / {values.quantile(0.95):,.0f}"


def section_dimensions(ds: Dataset) -> str:
    branches, menu = ds.branches, ds.menu
    by_region = branches.groupby("region").agg(
        branches=("branch_id", "count"),
        cloud_kitchens=("outlet_type", lambda s: int((s == "cloud_kitchen").sum())),
    )
    menu_summary = (
        menu.assign(margin=1 - menu["unit_cost"] / menu["unit_price"])
        .groupby("category")
        .agg(
            items=("menu_item_id", "count"),
            price_range=("unit_price", lambda s: f"{s.min():,} to {s.max():,}"),
            avg_margin=("margin", lambda s: f"{100 * s.mean():.0f}%"),
        )
    )
    opened_from, opened_to = branches["open_date"].min(), branches["open_date"].max()
    parts = [
        "## 2. Dimensions",
        f"**Branches:** {len(branches)}, opened {opened_from} to {opened_to}.",
        _md_table(by_region.reset_index()),
        _md_table(
            _share(branches["timezone"].value_counts()).rename(columns={"timezone": "timezone"})
        ),
        _md_table(_share(branches["size_tier"].value_counts())),
        "**Menu:**\n\n" + _md_table(menu_summary.reset_index()),
        "**Channels:**\n\n" + _md_table(ds.channels),
        "**Promos:**\n\n"
        + _md_table(
            ds.promos[
                [
                    "promo_id",
                    "promo_name",
                    "discount_type",
                    "discount_value",
                    "valid_from",
                    "valid_to",
                ]
            ]
        ),
    ]
    return "\n\n".join(parts)


def section_orders(ds: Dataset) -> str:
    orders = _unique_orders(ds)
    done = orders[orders["status"] == "completed"]
    daily = orders.groupby(["order_date", "branch_id"]).size().reset_index(name="n")
    daily["weekday"] = pd.to_datetime(daily["order_date"]).dt.dayofweek.map(
        dict(enumerate(WEEKDAYS))
    )
    weekday = daily.groupby("weekday")["n"].mean().reindex(WEEKDAYS).dropna().round(0).astype(int)
    hourly = (
        orders.groupby(["hour", "is_online"])
        .size()
        .unstack(fill_value=0)
        .rename(columns={False: "offline", True: "online"})
    )
    hourly = (100 * hourly / hourly.sum()).round(1).astype(str) + "%"
    channel = orders["channel_id"].value_counts()
    channel_sales = done.groupby("channel_id")["total_amount"].sum()
    channel_table = _share(channel).assign(
        net_sales_share=lambda t: (
            (100 * channel_sales.reindex(t["channel_id"]).to_numpy() / channel_sales.sum())
            .round(1)
            .astype(str)
            + "%"
        )
    )
    online_done = done[done["is_online"]]
    promo_use = (
        done[done["promo_id"] != ""]
        .groupby("promo_id")
        .agg(
            orders=("order_id", "count"),
            avg_discount=("discount_amount", lambda s: f"{s.mean():,.0f}"),
        )
    )
    discount_rate = 100 * done["discount_amount"].sum() / done["gross_amount"].sum()
    commission_rate = (
        100 * online_done["platform_commission_amount"].sum() / online_done["total_amount"].sum()
    )
    parts = [
        "## 3. Orders",
        "**Status:**\n\n" + _md_table(_share(orders["status"].value_counts())),
        "**Channel mix:**\n\n" + _md_table(channel_table),
        "**Average orders per branch-day by weekday:**\n\n"
        + _md_table(weekday.rename("orders").reset_index().rename(columns={"weekday": "weekday"})),
        "**Share of orders per local hour (each column sums to 100%):**\n\n"
        + _md_table(hourly.reset_index()),
        "**Amounts in Rp (all unique orders):**\n\n"
        + _md_table(
            _stats(
                orders,
                ["gross_amount", "discount_amount", "total_amount", "platform_commission_amount"],
            )
        ),
        f"**Discount rate (completed):** {discount_rate:.2f}%. "
        f"**Orders with a promo:** {100 * (done['promo_id'] != '').mean():.1f}%. "
        f"**Mean online commission rate (completed):** "
        f"{commission_rate:.1f}%.",
        "**Promo usage (completed):**\n\n" + _md_table(promo_use.reset_index()),
        "**Payment method labels as delivered (offline orders, includes dirty labels):**\n\n"
        + _md_table(
            _share(
                orders.loc[~orders["is_online"], "payment_method"]
                .replace("", "(empty)")
                .value_counts()
            )
        ),
    ]
    return "\n\n".join(parts)


def section_items(ds: Dataset) -> str:
    items = ds.items.drop_duplicates()
    orders = _unique_orders(ds)
    lines = items.groupby("order_id").size()
    category = items.merge(
        ds.menu[["menu_item_id", "item_name", "category"]], on="menu_item_id", how="left"
    )
    drink_orders = category.loc[category["category"] == "beverage", "order_id"].nunique()
    category_sales = (
        category.assign(category=category["category"].fillna("(unknown item)"))
        .groupby("category")["line_amount"]
        .sum()
    )
    top = category.groupby("item_name")["line_amount"].sum().sort_values(ascending=False).head(5)
    attach_rate = 100 * drink_orders / len(orders)
    parts = [
        "## 4. Order items",
        f"**Lines per order:** mean {lines.mean():.2f}, distribution:\n\n"
        + _md_table(_share(lines.value_counts().sort_index().rename_axis("lines"))),
        "**Quantity per line:**\n\n"
        + _md_table(_share(items["quantity"].value_counts().sort_index())),
        "**Sales share by category (line_amount):**\n\n"
        + _md_table(
            (100 * category_sales / category_sales.sum())
            .round(1)
            .astype(str)
            .add("%")
            .rename("share")
            .reset_index()
        ),
        "**Top 5 items by line_amount:**\n\n"
        + _md_table(top.map("{:,}".format).rename("line_amount").reset_index()),
        f"**Beverage attach rate:** {attach_rate:.1f}% of orders contain a beverage.",
        "**Amounts in Rp:**\n\n" + _md_table(_stats(items, ["unit_price", "line_amount"])),
    ]
    return "\n\n".join(parts)


def section_changes(ds: Dataset) -> str:
    changes = ds.changes
    order_day = pd.to_datetime(changes["order_id"].str[5:13], format="%Y%m%d")
    lag = (pd.to_datetime(changes["changed_at"].str[:10]) - order_day).dt.days
    parts = [
        "## 5. Order changes",
        _md_table(_share(changes["new_status"].value_counts())),
        "**Refund lag in days (order date to refund date):**\n\n"
        + _md_table(_share(lag.value_counts().sort_index().rename_axis("lag_days"))),
    ]
    return "\n\n".join(parts)


def section_empties(ds: Dataset) -> str:
    frames = {"orders": ds.orders, "order_items": ds.items}
    rows = []
    for name, frame in frames.items():
        for column in [c for c in frame.columns if c != "source_file_date"]:
            empty = int((frame[column].astype(str) == "").sum())
            rows.append((name, column, f"{empty:,}", f"{100 * empty / len(frame):.2f}%"))
    note = (
        "`promo_id` is empty when no promo applies, and `platform_order_ref` is empty for "
        "offline orders. Both are structural, not defects. An empty `payment_method`, or an "
        "empty `platform_order_ref` on an online order, is a defect."
    )
    table = _md_table(pd.DataFrame(rows, columns=["entity", "column", "empty", "empty %"]))
    return "## 6. Empty values\n\n" + table + "\n\n" + note


def _injected(ds: Dataset, key: str) -> int:
    return sum(int(m["injected"].get(key, 0)) for m in ds.manifests)


def defect_reconciliation(ds: Dataset) -> pd.DataFrame:
    """Defects found by inspecting the data versus defects the generator says it injected."""
    orders = _unique_orders(ds)
    items = ds.items.drop_duplicates()
    line_sum = items.groupby("order_id")["line_amount"].sum().reindex(orders["order_id"]).to_numpy()
    offline = orders[~orders["is_online"]]
    reporting = ds.orders[["source_file_date", "branch_id"]].drop_duplicates()
    expected = sum(int(m["expected_branches"]) for m in ds.manifests)
    dropped = sum(len(m["dropped_branch_ids"]) for m in ds.manifests)
    detected = {
        "duplicate order rows": (
            int(ds.orders.duplicated().sum()),
            _injected(ds, "duplicate_orders"),
        ),
        "duplicate item rows": (
            int(ds.items.duplicated().sum()),
            _injected(ds, "duplicate_item_rows"),
        ),
        "unknown menu item": (
            int((~items["menu_item_id"].isin(ds.menu["menu_item_id"])).sum()),
            _injected(ds, "unknown_menu_item"),
        ),
        "gross_amount differs from item sum": (
            int((orders["gross_amount"].to_numpy() != line_sum).sum()),
            _injected(ds, "gross_mismatch"),
        ),
        "empty payment_method (offline)": (
            int((offline["payment_method"] == "").sum()),
            _injected(ds, "payment_null"),
        ),
        "non-standard payment label": (
            int((~offline["payment_method"].isin(CLEAN_PAYMENTS | {""})).sum()),
            _injected(ds, "payment_variant"),
        ),
        "empty platform_order_ref (online)": (
            int((orders["is_online"] & (orders["platform_order_ref"] == "")).sum()),
            _injected(ds, "platform_ref_null"),
        ),
        "late-arriving orders": (
            int((orders["source_file_date"] > orders["order_date"]).sum()),
            _injected(ds, "late_orders_delayed_in"),
        ),
        "missing branch-days": (expected - len(reporting), dropped),
    }
    table = pd.DataFrame(
        [
            (name, found, said, "yes" if found == said else "NO")
            for name, (found, said) in detected.items()
        ],
        columns=["defect", "detected in data", "injected (manifest)", "match"],
    )
    return table


def section_defects(ds: Dataset) -> str:
    intro = (
        "Detected counts come from inspecting the CSV files. Injected counts come from the "
        "daily manifests. "
        "A mismatch means a data quality check built on this data would be wrong. "
        "Missing branch-days assume every open branch has at least one order per day, "
        "which holds at the default scale but not at very low scales."
    )
    return (
        "## 7. Defects: detected versus injected\n\n"
        + intro
        + "\n\n"
        + _md_table(defect_reconciliation(ds))
    )


def build_profile(root: Path) -> str:
    ds = load_dataset(root)
    sections = [
        section_overview(ds),
        section_dimensions(ds),
        section_orders(ds),
        section_items(ds),
        section_changes(ds),
        section_empties(ds),
        section_defects(ds),
    ]
    intro = (
        "Generated with `jff-gen profile`. Regenerate it after changing the seed, scale or config."
    )
    return "# Data profile\n\n" + intro + "\n\n" + "\n\n".join(sections) + "\n"
