# Data dictionary

Describes the files written by `jff-gen` (the raw layer). All data is synthetic. Row counts below are from the 45-day development window (`--scale 0.1`, seed 42), see `data-profile.md`.

## Conventions

| Topic | Rule |
|---|---|
| Format | CSV, UTF-8, comma separated, one header row, LF line endings |
| Missing value | Empty string. There is no `NULL` marker |
| Money | Integer Indonesian rupiah (Rp), no decimals, no thousands separator |
| Timestamps | `YYYY-MM-DD HH:MM:SS` in the **branch's local time**, no offset. The zone is `branches.timezone` |
| Dates | `YYYY-MM-DD` |
| Booleans | `True` or `False` |
| Partition | Daily files sit in `<entity>/dt=YYYY-MM-DD/`. `dt` is the file date, which is not always the order date (see late-arriving orders) |
| Derived later | `source_file_date` (the `dt` of the file a row arrived in) is not a column in the CSV. It is added when the files are loaded |

The example values in the `orders` table describe one online order. Every column below can also carry the defects described in the last section. A "Required" column marked **yes** means the value is expected on every row of clean data.

## Entities

| Entity | File | Grain | Primary key | Rows (dev window) |
|---|---|---|---|---|
| orders | `orders/dt=*/orders.csv` | one row per order | order_id | 541,139 |
| order_items | `order_items/dt=*/order_items.csv` | one row per order line | order_id, line_no | 1,317,011 |
| order_changes | `order_changes/dt=*/order_changes.csv` | one row per refund | change_id | 4,159 |
| branches | `dimensions/branches.csv` | one row per branch | branch_id | 120 |
| menu_items | `dimensions/menu_items.csv` | one row per menu item | menu_item_id | 21 |
| promos | `dimensions/promos.csv` | one row per promotion | promo_id | 6 |
| channels | `dimensions/channels.csv` | one row per sales channel | channel_id | 5 |
| manifest | `_manifests/dt=*/manifest.json` | one document per generated day | date | 45 |

Row counts for the three daily entities include injected duplicate rows.

## Transaction tables

### `orders`

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `order_id` | string | yes | Unique order identifier. The sequence number follows order time within the branch and day | `B<branch_id, 3 digits>-<YYYYMMDD>-<sequence, 5 digits>` | `B001-20260916-00001` |
| `branch_id` | integer | yes | Branch that fulfilled the order | Foreign key to `branches.branch_id` | `1` |
| `channel_id` | string | yes | Sales channel | Foreign key to `channels.channel_id` | `grabfood` |
| `order_ts` | timestamp | yes | When the order was placed, branch local time | Between 09:00:00 and 21:59:59 | `2026-09-16 10:04:14` |
| `status` | string | yes | Status when first exported. Refunds are not shown here, they arrive in `order_changes` | `completed`, `cancelled` | `completed` |
| `gross_amount` | integer | yes | Sum of the order's `line_amount` before discount | Rp, greater than 0 | `62000` |
| `discount_amount` | integer | yes | Order-level discount. 0 when no promo applies | Rp, between 0 and `gross_amount` | `12400` |
| `promo_id` | string | no | Promotion applied. Empty when none | Foreign key to `promos.promo_id`, or empty | `PRM-03` |
| `total_amount` | integer | yes | Amount the customer pays, `gross_amount` minus `discount_amount` | Rp | `49600` |
| `platform_commission_amount` | integer | yes | Delivery platform commission. Greater than 0 only for online orders that are not cancelled, otherwise 0 | Rp | `9920` |
| `payment_method` | string | yes | How the order was paid | Offline: `cash`, `qris`, `ewallet`, `card`. Online: `platform_settlement` | `platform_settlement` |
| `platform_order_ref` | string | no | Reference given by the delivery platform. Empty for offline orders | `GRB-`, `GOF-` or `SHF-` followed by 8 digits | `GRB-67504013` |

### `order_items`

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `order_id` | string | yes | Order this line belongs to | Foreign key to `orders.order_id` | `B001-20260916-00001` |
| `line_no` | integer | yes | Position of the line within the order, starting at 1 | 1 to 5 in the current data | `1` |
| `menu_item_id` | string | yes | Item sold | Foreign key to `menu_items.menu_item_id` | `MI-003` |
| `quantity` | integer | yes | Units sold on this line | 1, 2 or 3 | `2` |
| `unit_price` | integer | yes | Menu price per unit, before the order-level discount | Rp | `26000` |
| `line_amount` | integer | yes | `quantity` times `unit_price` | Rp | `52000` |

### `order_changes`

Only refunds exist today. A refund appears in the file of the day it happens, which can be up to 8 days after the order date. If the order itself arrived late, the refund can arrive before the order.

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `change_id` | string | yes | Unique change identifier | `<order_id>-RF` | `B001-20260916-00007-RF` |
| `order_id` | string | yes | Order that changed | Foreign key to `orders.order_id` | `B001-20260916-00007` |
| `previous_status` | string | yes | Status before the change | `completed` | `completed` |
| `new_status` | string | yes | Status after the change | `refunded` | `refunded` |
| `changed_at` | timestamp | yes | When the change happened, branch local time. Always after the order time | `YYYY-MM-DD HH:MM:SS` | `2026-09-18 14:30:05` |

## Dimension tables

### `branches`

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `branch_id` | integer | yes | Branch identifier | 1 to the number of branches (default 120) | `1` |
| `branch_code` | string | yes | Short code | `B` plus 3 digits | `B001` |
| `branch_name` | string | yes | Display name | `Just Fast Food <city> <nn>` | `Just Fast Food Bandung 01` |
| `city` | string | yes | City | One of 23 configured cities | `Bandung` |
| `region` | string | yes | Region used for volume and online share | `Jabodetabek`, `Jawa Lainnya`, `Sumatera`, `Kalimantan`, `Sulawesi`, `Bali-Nusa Tenggara`, `Maluku-Papua` | `Jawa Lainnya` |
| `timezone` | string | yes | IANA zone of the branch (WIB, WITA or WIT). Used to read `order_ts` | `Asia/Jakarta`, `Asia/Pontianak`, `Asia/Makassar`, `Asia/Jayapura` | `Asia/Jakarta` |
| `outlet_type` | string | yes | Kind of outlet. A cloud kitchen only takes online orders | `restaurant`, `cloud_kitchen` | `restaurant` |
| `size_tier` | string | yes | Demand tier that scales order volume | `small`, `medium`, `large` | `medium` |
| `open_date` | date | yes | Opening date. A branch has no orders before it | 2019-01-01 to 2026-06-30 | `2025-12-15` |

### `menu_items`

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `menu_item_id` | string | yes | Item identifier | `MI-` plus 3 digits | `MI-001` |
| `item_name` | string | yes | Item name (fictional menu) | Free text | `Ayam Geprek Klasik` |
| `category` | string | yes | Menu category | `main`, `side`, `dessert`, `beverage` | `main` |
| `unit_price` | integer | yes | Selling price per unit | Rp | `28000` |
| `unit_cost` | integer | yes | Cost of goods per unit. Static, it does not change over time | Rp, less than `unit_price` | `11000` |
| `is_active` | boolean | yes | Whether the item is on the menu | `True`, `False` | `True` |

### `promos`

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `promo_id` | string | yes | Promotion identifier | `PRM-` plus 2 digits | `PRM-01` |
| `promo_name` | string | yes | Display name | Free text | `Diskon Akhir Pekan 10%` |
| `discount_type` | string | yes | How `discount_value` is read | `percent`, `fixed` | `percent` |
| `discount_value` | integer | yes | Percent (for `percent`) or Rp (for `fixed`) | Positive integer | `10` |
| `min_order_amount` | integer | yes | Minimum `gross_amount` for the promo to apply | Rp | `40000` |
| `max_discount_amount` | integer | yes | Cap on the discount | Rp | `15000` |
| `valid_from` | date | yes | First day the promo applies | `YYYY-MM-DD` | `2026-01-01` |
| `valid_to` | date | yes | Last day the promo applies | `YYYY-MM-DD` | `2026-12-31` |
| `channel_scope` | string | yes | Channels where the promo applies, joined with `\|` | Channel ids | `offline_dine_in\|offline_takeaway` |
| `weekday_scope` | string | no | Weekdays where it applies, `0` is Monday and `6` is Sunday, joined with `\|`. Empty means every day | `0` to `6` | `5\|6` |

### `channels`

| Column | Type | Required | Description | Allowed values or format | Example |
|---|---|---|---|---|---|
| `channel_id` | string | yes | Channel identifier | `offline_dine_in`, `offline_takeaway`, `grabfood`, `gofood`, `shopeefood` | `grabfood` |
| `order_origin` | string | yes | Where the order came from | `offline`, `online` | `online` |
| `platform` | string | yes | Delivery platform, `none` for offline | `none`, `grabfood`, `gofood`, `shopeefood` | `grabfood` |
| `service_type` | string | yes | How the customer receives the order | `dine_in`, `takeaway`, `delivery` | `delivery` |
| `commission_rate` | decimal | yes | Share of `total_amount` kept by the platform. Synthetic placeholder values, verify against real terms before quoting | 0 to 1, `0` for offline | `0.2` |

## Run metadata

### `manifest.json`

One file per generated day, written after the CSV files. Its presence means the day is complete. It is ground truth for the generator, not business data.

| Field | Type | Description |
|---|---|---|
| `date` | date | File date of the run |
| `seed` | integer | Seed used |
| `scale` | decimal | Volume multiplier used |
| `defects_enabled` | boolean | `false` when run with `--clean` |
| `expected_branches` | integer | Branches open on that date |
| `dropped_branch_ids` | list of integers | Branches that sent no files that day |
| `rows.orders` | integer | Rows written to `orders.csv` |
| `rows.order_items` | integer | Rows written to `order_items.csv` |
| `rows.order_changes` | integer | Rows written to `order_changes.csv` |
| `injected.duplicate_orders` | integer | Order rows sent twice |
| `injected.duplicate_item_rows` | integer | Item rows sent twice |
| `injected.late_orders_delayed_out` | integer | Orders held back from this day's file (arrive the next day) |
| `injected.late_orders_delayed_in` | integer | Orders in this file that belong to the previous day |
| `injected.payment_null` | integer | Offline orders with an empty `payment_method` |
| `injected.payment_variant` | integer | Offline orders with a non-standard payment label |
| `injected.platform_ref_null` | integer | Online orders with an empty `platform_order_ref` |
| `injected.gross_mismatch` | integer | Orders whose `gross_amount` differs from the item sum |
| `injected.unknown_menu_item` | integer | Item lines with a `menu_item_id` not in `menu_items` |

An `injected.*` field is absent when that defect did not occur that day.

## Relationships

| Child column | Parent column | Notes |
|---|---|---|
| `orders.branch_id` | `branches.branch_id` | |
| `orders.channel_id` | `channels.channel_id` | |
| `orders.promo_id` | `promos.promo_id` | Empty means no promo |
| `order_items.order_id` | `orders.order_id` | Many lines per order |
| `order_items.menu_item_id` | `menu_items.menu_item_id` | Can break (unknown menu item) |
| `order_changes.order_id` | `orders.order_id` | Can arrive before the order |

## Business rules

- `total_amount = gross_amount - discount_amount` and `gross_amount` equals the sum of the order's `line_amount`, in clean data.
- `line_amount = quantity * unit_price`, and `unit_price` equals the menu price.
- Commission is `total_amount` times the channel's `commission_rate`, rounded, for online orders that are not cancelled. It is 0 for offline and cancelled orders.
- Cancelled orders keep their amounts, so exclude them when summing sales.
- A refunded order still shows `status = completed` in `orders`. The refund is only visible in `order_changes`.
- Refunds and cancellations are attributed to the order date, not the date they happened.
- The discount exists only at order level. Item lines carry gross prices.

## Defects that can occur

These simulate problems seen in production systems. Turn them all off with `--clean`. The data profile shows detected versus injected counts.

| Defect | Where | What it looks like | Expected handling |
|---|---|---|---|
| Duplicate rows | `orders`, `order_items` | Exact copy of a row in the same file | Deduplicate on the key |
| Late-arriving orders | `orders`, `order_items` | `order_ts` date earlier than the file's `dt` | Partition by order date, not file date |
| Missing branch-day | all daily files | A branch has no rows for an open day | Detect by coverage check, cannot be repaired |
| Empty or inconsistent payment label | `orders.payment_method` | Empty, or labels such as `QRIS`, `Cash `, `tunai`, `kartu`, `E-Wallet` | Standardize, map empty to `unknown` |
| Empty platform reference | `orders.platform_order_ref` | Empty on an online order | Flag the row |
| Total does not match items | `orders.gross_amount`, `total_amount` | `gross_amount` differs from the item sum by Rp100 to Rp1,000 | Recompute from items |
| Unknown menu item | `order_items.menu_item_id` | Id such as `MI-X123` not in `menu_items` | Map to an unknown member or quarantine |
| Refund before its order | `order_changes` | Change row exists but the order row is in a later file | Apply once the order exists |
