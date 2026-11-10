ORDERS_COLUMNS = [
    "order_id",
    "branch_id",
    "channel_id",
    "order_ts",
    "status",
    "gross_amount",
    "discount_amount",
    "promo_id",
    "total_amount",
    "platform_commission_amount",
    "payment_method",
    "platform_order_ref",
]
ORDER_ITEMS_COLUMNS = [
    "order_id",
    "line_no",
    "menu_item_id",
    "quantity",
    "unit_price",
    "line_amount",
]
ORDER_CHANGES_COLUMNS = ["change_id", "order_id", "previous_status", "new_status", "changed_at"]

DAILY_ENTITIES: dict[str, list[str]] = {
    "orders": ORDERS_COLUMNS,
    "order_items": ORDER_ITEMS_COLUMNS,
    "order_changes": ORDER_CHANGES_COLUMNS,
}

PAYMENT_VARIANTS: dict[str, list[str]] = {
    "cash": ["CASH", "Cash ", "tunai"],
    "qris": ["QRIS", "Qris", " qris"],
    "ewallet": ["e-wallet", "E-Wallet", "EWALLET"],
    "card": ["CARD", "Card", "kartu"],
}
ONLINE_PAYMENT = "platform_settlement"
