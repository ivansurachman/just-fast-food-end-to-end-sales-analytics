# Data profile

Generated with `jff-gen profile`. Regenerate it after changing the seed, scale or config.

## 1. Overview

| item | value |
|---|---|
| Date range (file dates) | 2026-09-16 to 2026-10-30 (45 days) |
| Seed / scale | 42 / 0.1 |
| orders rows (raw / unique) | 541,139 / 538,399 |
| order_items rows (raw / unique) | 1,317,011 / 1,310,401 |
| order_changes rows | 4,159 |
| Orders per branch-day (mean / p5 / p95) | 100 / 56 / 173 |
| Size on disk | 109.0 MB |

## 2. Dimensions

**Branches:** 120, opened 2019-02-07 to 2026-06-07.

| region | branches | cloud_kitchens |
|---|---|---|
| Bali-Nusa Tenggara | 6 | 0 |
| Jabodetabek | 50 | 5 |
| Jawa Lainnya | 31 | 3 |
| Kalimantan | 2 | 0 |
| Maluku-Papua | 3 | 1 |
| Sulawesi | 9 | 2 |
| Sumatera | 19 | 3 |

| timezone | count | share |
|---|---|---|
| Asia/Jakarta | 100 | 83.3% |
| Asia/Makassar | 17 | 14.2% |
| Asia/Jayapura | 3 | 2.5% |

| size_tier | count | share |
|---|---|---|
| medium | 57 | 47.5% |
| small | 41 | 34.2% |
| large | 22 | 18.3% |

**Menu:**

| category | items | price_range | avg_margin |
|---|---|---|---|
| beverage | 6 | 5,000 to 18,000 | 75% |
| dessert | 2 | 13,000 to 14,000 | 65% |
| main | 8 | 24,000 to 38,000 | 60% |
| side | 5 | 6,000 to 22,000 | 66% |

**Channels:**

| channel_id | order_origin | platform | service_type | commission_rate |
|---|---|---|---|---|
| offline_dine_in | offline | none | dine_in | 0.0 |
| offline_takeaway | offline | none | takeaway | 0.0 |
| grabfood | online | grabfood | delivery | 0.2 |
| gofood | online | gofood | delivery | 0.2 |
| shopeefood | online | shopeefood | delivery | 0.18 |

**Promos:**

| promo_id | promo_name | discount_type | discount_value | valid_from | valid_to |
|---|---|---|---|---|---|
| PRM-01 | Diskon Akhir Pekan 10% | percent | 10 | 2026-01-01 | 2026-12-31 |
| PRM-02 | Potongan 10rb | fixed | 10000 | 2026-01-01 | 2026-12-31 |
| PRM-03 | Promo Grab 20% | percent | 20 | 2026-01-01 | 2026-12-31 |
| PRM-04 | Promo Gofood Hemat | fixed | 8000 | 2026-01-01 | 2026-12-31 |
| PRM-05 | Promo Shopee 15% | percent | 15 | 2026-01-01 | 2026-12-31 |
| PRM-06 | Gebyar Ulang Tahun 25% | percent | 25 | 2026-10-01 | 2026-10-14 |

## 3. Orders

**Status:**

| status | count | share |
|---|---|---|
| completed | 519,632 | 96.5% |
| cancelled | 18,767 | 3.5% |

**Channel mix:**

| channel_id | count | share | net_sales_share |
|---|---|---|---|
| offline_dine_in | 174,533 | 32.4% | 33.9% |
| grabfood | 107,710 | 20.0% | 18.9% |
| gofood | 102,516 | 19.0% | 18.4% |
| offline_takeaway | 94,270 | 17.5% | 18.3% |
| shopeefood | 59,370 | 11.0% | 10.5% |

**Average orders per branch-day by weekday:**

| weekday | orders |
|---|---|
| Mon | 92 |
| Tue | 93 |
| Wed | 95 |
| Thu | 97 |
| Fri | 108 |
| Sat | 112 |
| Sun | 102 |

**Share of orders per local hour (each column sums to 100%):**

| hour | offline | online |
|---|---|---|
| 9 | 0.1% | 0.3% |
| 10 | 1.4% | 3.1% |
| 11 | 8.3% | 10.2% |
| 12 | 15.8% | 11.1% |
| 13 | 11.8% | 4.4% |
| 14 | 6.6% | 1.0% |
| 15 | 6.0% | 0.2% |
| 16 | 5.8% | 1.1% |
| 17 | 8.7% | 5.4% |
| 18 | 14.1% | 14.7% |
| 19 | 13.6% | 21.4% |
| 20 | 6.3% | 18.1% |
| 21 | 1.4% | 9.0% |

**Amounts in Rp (all unique orders):**

| column | min | mean | median | p95 | max |
|---|---|---|---|---|---|
| gross_amount | 23,500 | 69,139 | 62,000 | 140,000 | 354,000 |
| discount_amount | 0 | 2,780 | 0 | 17,100 | 30,000 |
| total_amount | 23,500 | 66,359 | 58,000 | 135,000 | 354,000 |
| platform_commission_amount | 0 | 5,995 | 0 | 21,800 | 63,200 |

**Discount rate (completed):** 4.00%. **Orders with a promo:** 21.1%. **Mean online commission rate (completed):** 19.6%.

**Promo usage (completed):**

| promo_id | orders | avg_discount |
|---|---|---|
| PRM-01 | 11639 | 7,979 |
| PRM-02 | 21721 | 10,000 |
| PRM-03 | 19656 | 13,790 |
| PRM-04 | 15214 | 8,000 |
| PRM-05 | 12329 | 10,426 |
| PRM-06 | 28897 | 20,919 |

**Payment method labels as delivered (offline orders, includes dirty labels):**

| payment_method | count | share |
|---|---|---|
| qris | 100,472 | 37.4% |
| cash | 79,491 | 29.6% |
| ewallet | 45,127 | 16.8% |
| card | 39,658 | 14.8% |
| (empty) | 2,017 | 0.8% |
|  qris | 263 | 0.1% |
| QRIS | 253 | 0.1% |
| Qris | 245 | 0.1% |
| Cash  | 229 | 0.1% |
| CASH | 211 | 0.1% |
| tunai | 203 | 0.1% |
| EWALLET | 124 | 0.0% |
| e-wallet | 113 | 0.0% |
| Card | 104 | 0.0% |
| kartu | 104 | 0.0% |
| E-Wallet | 100 | 0.0% |
| CARD | 89 | 0.0% |

## 4. Order items

**Lines per order:** mean 2.43, distribution:

| lines | count | share |
|---|---|---|
| 1 | 98,528 | 18.3% |
| 2 | 208,951 | 38.8% |
| 3 | 148,330 | 27.6% |
| 4 | 63,969 | 11.9% |
| 5 | 18,621 | 3.5% |

**Quantity per line:**

| quantity | count | share |
|---|---|---|
| 1 | 1,113,611 | 85.0% |
| 2 | 131,682 | 10.0% |
| 3 | 65,108 | 5.0% |

**Sales share by category (line_amount):**

| category | share |
|---|---|
| (unknown item) | 0.1% |
| beverage | 9.9% |
| dessert | 1.1% |
| main | 83.4% |
| side | 5.5% |

**Top 5 items by line_amount:**

| item_name | line_amount |
|---|---|
| Ayam Geprek Klasik | 5,406,800,000 |
| Paket Hemat Geprek | 4,723,476,000 |
| Nasi Ayam Crispy | 4,640,662,000 |
| Ayam Geprek Keju | 4,521,297,000 |
| Rice Bowl Rendang | 3,365,460,000 |

**Beverage attach rate:** 54.9% of orders contain a beverage.

**Amounts in Rp:**

| column | min | mean | median | p95 | max |
|---|---|---|---|---|---|
| unit_price | 5,000 | 23,677 | 26,000 | 38,000 | 38,000 |
| line_amount | 5,000 | 28,406 | 28,000 | 66,000 | 114,000 |

## 5. Order changes

| new_status | count | share |
|---|---|---|
| refunded | 4,159 | 100.0% |

**Refund lag in days (order date to refund date):**

| lag_days | count | share |
|---|---|---|
| 0 | 1,032 | 24.8% |
| 1 | 1,243 | 29.9% |
| 2 | 752 | 18.1% |
| 3 | 478 | 11.5% |
| 4 | 254 | 6.1% |
| 5 | 149 | 3.6% |
| 6 | 100 | 2.4% |
| 7 | 110 | 2.6% |
| 8 | 41 | 1.0% |

## 6. Empty values

| entity | column | empty | empty % |
|---|---|---|---|
| orders | order_id | 0 | 0.00% |
| orders | branch_id | 0 | 0.00% |
| orders | channel_id | 0 | 0.00% |
| orders | order_ts | 0 | 0.00% |
| orders | status | 0 | 0.00% |
| orders | gross_amount | 0 | 0.00% |
| orders | discount_amount | 0 | 0.00% |
| orders | promo_id | 426,251 | 78.77% |
| orders | total_amount | 0 | 0.00% |
| orders | platform_commission_amount | 0 | 0.00% |
| orders | payment_method | 2,028 | 0.37% |
| orders | platform_order_ref | 272,787 | 50.41% |
| order_items | order_id | 0 | 0.00% |
| order_items | line_no | 0 | 0.00% |
| order_items | menu_item_id | 0 | 0.00% |
| order_items | quantity | 0 | 0.00% |
| order_items | unit_price | 0 | 0.00% |
| order_items | line_amount | 0 | 0.00% |

`promo_id` is empty when no promo applies, and `platform_order_ref` is empty for offline orders. Both are structural, not defects. An empty `payment_method`, or an empty `platform_order_ref` on an online order, is a defect.

## 7. Defects: detected versus injected

Detected counts come from inspecting the CSV files. Injected counts come from the daily manifests. A mismatch means a data quality check built on this data would be wrong. Missing branch-days assume every open branch has at least one order per day, which holds at the default scale but not at very low scales.

| defect | detected in data | injected (manifest) | match |
|---|---|---|---|
| duplicate order rows | 2740 | 2740 | yes |
| duplicate item rows | 6610 | 6610 | yes |
| unknown menu item | 1324 | 1324 | yes |
| gross_amount differs from item sum | 2709 | 2709 | yes |
| empty payment_method (offline) | 2017 | 2017 | yes |
| non-standard payment label | 2038 | 2038 | yes |
| empty platform_order_ref (online) | 2629 | 2629 | yes |
| late-arriving orders | 4919 | 4919 | yes |
| missing branch-days | 9 | 9 | yes |
