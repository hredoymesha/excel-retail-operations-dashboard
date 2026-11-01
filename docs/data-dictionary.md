# Data dictionary

All data in this project is synthetic. The company, products, suppliers and customers are made up, and no real person, e-mail address, phone number or brand appears anywhere. The retailer is a fictional multichannel shop in Finland. Any resemblance to a real business is by chance.

Three scripts build the files. Run them from the project root in this order:

```
python tools/generate_data.py    # reference tables, stock, purchase orders, returns, dirty sales export
python tools/clean_data.py       # data/raw/sales_lines_dirty.csv -> data/sales_lines.csv
python tools/check_data.py       # assertions, writes outputs/data_checks.csv
```

The generator is seeded (`20260101`). I ran it twice with the same library versions and every output file had the same checksum. A different numpy version can change the random stream, so the library versions are pinned in `requirements.txt`.

Money is in euros. Prices and costs are net of VAT. Dates are ISO (`yyyy-mm-dd`). Files use a comma as separator and a full stop as decimal mark.

## Files

| File | Rows | Grain |
|---|---:|---|
| `data/products.csv` | 42 | one row per SKU |
| `data/suppliers.csv` | 8 | one row per supplier |
| `data/customers.csv` | 4,000 | one row per customer (3,940 consumers, 60 business accounts) |
| `data/promotions.csv` | 75 | one row per promotion and category |
| `data/price_history.csv` | 130 | one row per SKU and price or cost change |
| `data/sales_lines.csv` | 56,249 | one row per order line (39,349 orders, 9,301 of them with a customer id) |
| `data/returns.csv` | 3,680 | one row per returned order line |
| `data/inventory_daily.csv` | 44,878 | one row per SKU and day while the SKU is listed |
| `data/purchase_orders.csv` | 869 | one row per purchase order to a supplier |
| `data/raw/sales_lines_dirty.csv` | 56,545 | the sales export before cleaning |
| `data/raw/cleaning_log.csv` | 11 | one row per cleaning rule |
| `data/raw/cleaning_actions.csv` | 2,961 | one row per changed value |
| `outputs/data_checks.csv` | 48 | one row per assertion in `tools/check_data.py` |

The three CSV files `sales_transactions_2025.csv`, `product_master.csv` and `inventory_snapshot.csv` in `data/` belong to version 1 and are not described here. A copy is in `v1/`.

## products.csv

| Column | Type | Meaning | Example |
|---|---|---|---|
| `sku` | text | Product key, `SKU-2001` to `SKU-2042` | `SKU-2004` |
| `product_name` | text | Invented product name | `Taivo Portable Speaker` |
| `category` | text | One of six categories: Electronics, Apparel, Home & Kitchen, Beauty & Care, Office, Sports & Outdoor | `Electronics` |
| `supplier_id` | text | Key into `suppliers.csv` | `SUP-01` |
| `unit_cost_2023` | number | Cost per unit at the start of 2023. Later costs are in `price_history.csv` | `33.0` |
| `list_price_2023` | number | List price at the start of 2023. Later prices are in `price_history.csv` | `53.99` |
| `lead_time_days_avg` | integer | Average days from purchase order to delivery | `18` |
| `lead_time_days_sd` | number | Standard deviation of that lead time in days | `3.7` |
| `min_order_qty` | integer | Smallest purchase order, and orders come in multiples of it | `12` |
| `shelf_life_days` | integer | Shelf life in days, only for Beauty & Care (7 SKUs). Blank otherwise | blank (`730` for `SKU-2022`) |
| `launch_date` | date | First day the SKU is on sale. Three SKUs launch after 2023-01-01 | `2023-01-01` |
| `discontinued_date` | date | Day the range is withdrawn, blank if still current. Three SKUs | `2024-09-15` |
| `stocking_policy` | text | Reorder behaviour used in the stock simulation: `lean` (9 SKUs), `good` (22), `heavy` (11) | `heavy` |

## suppliers.csv

| Column | Type | Meaning | Example |
|---|---|---|---|
| `supplier_id` | text | Supplier key | `SUP-04` |
| `supplier_name` | text | Invented supplier name | `Linden Textiles` |
| `country` | text | Country of dispatch | `Portugal` |
| `lead_time_days_avg` | integer | Typical lead time for this supplier | `30` |
| `lead_time_days_sd` | integer | Typical spread of that lead time | `6` |

## customers.csv

| Column | Type | Meaning | Example |
|---|---|---|---|
| `customer_id` | text | Customer key, ordered by sign-up date | `C00004` |
| `signup_date` | date | Day the customer registered. 33% of consumers signed up before 2023 | `2020-01-01` |
| `region` | text | Home region: Helsinki, Tampere, Turku, Oulu or Kuopio | `Turku` |
| `customer_type` | text | `Consumer` or `Business`. Only business accounts buy wholesale | `Consumer` |
| `acquisition_channel` | text | Channel the customer joined through, and the one they prefer | `Online` |

Names, e-mail addresses and phone numbers do not exist in the data.

## promotions.csv

| Column | Type | Meaning | Example |
|---|---|---|---|
| `promo_id` | text | Promotion key | `PRM-004` |
| `campaign` | text | Campaign name | `Spring Home Refresh` |
| `start_date`, `end_date` | date | First and last day, both included | `2023-04-10`, `2023-04-24` |
| `category` | text | Category the discount applies to | `Home & Kitchen` |
| `discount_pct` | number | Discount off list price, as a fraction | `0.15` |
| `channel_scope` | text | `All` means Online, Retail and Marketplace. `Online` means online only. Wholesale never takes part | `All` |

If two promotions cover the same category, channel and day, the larger discount applies.

## price_history.csv

A SKU's price or cost applies from `effective_from` until the next row for that SKU.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `sku` | text | Product key | `SKU-2001` |
| `effective_from` | date | First day the values apply | `2025-01-01` |
| `list_price` | number | List price per unit | `45.99` |
| `unit_cost` | number | Cost per unit | `28.77` |

## sales_lines.csv

This is the cleaned file. `data/raw/sales_lines_dirty.csv` has the same columns as text.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `order_id` | text | Order key. Numbers rise with the date | `ORD-000001` |
| `line_no` | integer | Line within the order | `4` |
| `order_date` | date | Day of the order | `2023-01-01` |
| `customer_id` | text | Key into `customers.csv`, or `GUEST` when the order has no customer id (see below) | `GUEST` |
| `region` | text | Region of the sale. For identified customers it is always their home region | `Kuopio` |
| `channel` | text | Online, Retail, Marketplace or Wholesale | `Retail` |
| `sku` | text | Key into `products.csv` | `SKU-2026` |
| `quantity` | integer | Units sold on the line | `1` |
| `list_price` | number | List price per unit on the day of the sale | `12.99` |
| `discount_pct` | number | Total discount off list price, as a fraction. Promotion, coupon or wholesale volume discount | `0.0` |
| `promo_id` | text | Promotion that gave the discount, blank if none | blank |
| `net_revenue` | number | `quantity x list_price x (1 - discount_pct)`, rounded to the cent | `12.99` |
| `unit_cost` | number | Cost per unit on the day of the sale | `3.6` |
| `shipping_cost` | number | Delivery cost the retailer pays, shared over the order's lines by units | `0.0` |
| `payment_fee` | number | Card or payment-provider fee | `0.12` |
| `platform_fee` | number | Marketplace commission, only on Marketplace lines | `0.0` |

Gross profit is `net_revenue - quantity x unit_cost`. Contribution margin takes off shipping, both fees and refunds from `returns.csv`.

## returns.csv

| Column | Type | Meaning | Example |
|---|---|---|---|
| `return_id` | text | Return key | `RET-00004` |
| `order_id`, `line_no` | text, integer | The sale line that came back | `ORD-000124`, `1` |
| `sku` | text | Product key | `SKU-2030` |
| `return_date` | date | Day the goods came back | `2023-01-10` |
| `return_qty` | integer | Units returned, at most the units sold | `2` |
| `reason` | text | Return reason | `Changed mind` |
| `refund_amount` | number | Money paid back, at the line's net price per unit | `23.98` |
| `restocked` | 0 or 1 | 1 if the goods could be sold again | `1` |
| `return_shipping_cost` | number | Cost of the return label. 4.50 online and marketplace, 0 otherwise | `4.5` |

## inventory_daily.csv

One central warehouse holds all stock. Rows start on the SKU's launch date.

| Column | Type | Meaning | Example |
|---|---|---|---|
| `date` | date | Day | `2023-01-04` |
| `sku` | text | Product key | `SKU-2001` |
| `on_hand` | integer | Units in the warehouse at the end of the day | `58` |
| `on_order` | integer | Units on open purchase orders at the end of the day | `0` |
| `units_sold` | integer | Units shipped that day. Equals the units on `sales_lines.csv` | `0` |
| `lost_units` | integer | Units customers wanted but the shelf could not supply | `0` |
| `stockout_flag` | 0 or 1 | 1 if `lost_units` is above 0 | `0` |

In a real company `lost_units` is never observed. The generator knows it because it creates demand first. In the workbook it stands for an estimate.

## purchase_orders.csv

| Column | Type | Meaning | Example |
|---|---|---|---|
| `po_id` | text | Purchase order key | `PO-00004` |
| `sku` | text | Product key | `SKU-2011` |
| `supplier_id` | text | Supplier key | `SUP-03` |
| `order_date` | date | Day the order is placed | `2023-01-01` |
| `promised_date` | date | Order date plus the SKU's average lead time | `2023-02-06` |
| `received_date` | date | Day the goods arrive. Blank for the 29 orders still open on 2025-12-31 | `2023-02-02` |
| `quantity` | integer | Units ordered, a multiple of the minimum order quantity | `48` |
| `unit_cost` | number | Cost per unit on the order date | `36.0` |
| `delay_days` | number | `received_date - promised_date`. Negative means early. Blank while open | `-4.0` |

## raw/cleaning_log.csv and raw/cleaning_actions.csv

`cleaning_log.csv` has one row per rule: `rule`, `issue`, `rows_affected`, `action`, `example_before`, `example_after`. `cleaning_actions.csv` lists every changed value with `rule`, `order_id`, `line_no`, `column`, `old_value`, `new_value` and `method`.

The dirty export has 56,545 rows. The cleaning script removes 15 test orders and 281 exact duplicates, which leaves 56,249 rows. It then repairs the following.

| Rule | Problem | Rows | Fix |
|---|---|---:|---|
| R03 | Channel written with spaces or other case | 675 | Trim and use title case |
| R03 | SKU written in lower case | 225 | Upper case |
| R04 | List price with a decimal comma (`7,99`) | 337 | Replace the comma |
| R05 | Negative quantity | 112 | Remove the sign |
| R06 | Date as `dd.mm.yyyy` | 450 | Convert |
| R07 | Date outside 2023 to 2025 (`2203-01-15`) | 140 | Take the date from the neighbouring order numbers |
| R08 | Region missing | 281 | Take it from another line of the same order, else the customer's home region |
| R09 | Customer missing | 221 | Take it from another line of the same order |
| R10 | Discount missing | 225 | Rebuild from list price, quantity and net revenue |

I injected every defect myself, so I know the right answer. After cleaning, `sales_lines.csv` matches the generator's own table exactly. In real exports some defects cannot be repaired this way. The cleaning script stops with an error when a region or customer id cannot be recovered, so a row is never guessed or dropped without you seeing it.

## Assumptions used to generate the data

Demand
- Each SKU has a popularity factor. Cheaper items sell more. Five SKUs are slow movers.
- Daily demand is a Poisson draw around a rate built from popularity, month, yearly growth, weekday, channel share, promotion effect and noise. A weekly shock and a daily gamma shock add variation beyond Poisson.
- Region shares: Helsinki 34%, Tampere 22%, Turku 17%, Oulu 14%, Kuopio 13%.
- Channel shares of sales lines move over time: Online 36% to 43%, Retail 41% to 32%, Marketplace 23% to 25%, Wholesale about 1%.
- Seasonality is set per category. November and December are strong for all. Office dips in July and recovers in August and September. Apparel and Home dip in July. Sports peaks in June and December.
- Yearly demand growth by category runs from 2% (Office) to 9% (Beauty & Care).
- Three SKUs launch late (ramp over 60 days) and three are discontinued (demand fades over 90 days).

Prices and costs
- List prices change each 1 January: Electronics falls 3%, other categories rise 2% to 4%.
- Costs change each 1 January. The Electronics supplier `SUP-01` adds a 7% cost increase on 2024-03-01 that stays.
- Cost of goods sold uses the unit cost on the sale date. It does not follow FIFO layers.

Promotions and elasticity
- Eleven campaigns repeat each year, plus Black Friday week with 25% off in 2023 and 30% in 2024 and 2025.
- A discount `d` multiplies demand by `(1 - d) ^ -e`. The elasticity `e` is 2.0 for Electronics, 1.7 Apparel, 1.4 Sports, 1.3 Home, 1.0 Beauty and 0.7 Office. Each promotion also gets a random extra pull of 0.95 to 1.25.
- After a promotion with a discount of 20% or more, demand dips for about ten days.
- Outside promotions, 6% of retail-type lines get a coupon of 5% or 10%. Wholesale lines get 10% to 19% depending on size.

Stock and suppliers
- Each SKU follows a reorder-point rule using the last 56 days of demand. The three policies differ in safety stock, review period and order cover: lean (low safety stock), good (service level of about 95%), heavy (large safety stock and 100 days of cover).
- Lead times are normal with the SKU's mean and standard deviation. `SUP-03` is disrupted from 2024-06-01 to 2024-09-30: 70% of its orders in that window take 10 to 25 extra days.
- Demand that finds an empty shelf is lost. A wholesale line is filled as far as stock allows. A retail line that does not fit is lost whole.
- Returned goods are not added back to stock in the simulation. The `restocked` flag is information only.
- Shelf life is a product attribute. Expiry write-offs are not simulated.

Customers and orders
- Customers are drawn into orders in their home region. Activity differs by customer, new customers buy soon after signing up, and consumers leave after a random lifetime with a mean of about 600 days. Business accounts never leave.
- Many orders carry no customer id and show `GUEST`: every marketplace order (the platform keeps the customer), 80% of retail orders (no loyalty card) and 60% of online orders (guest checkout). Wholesale orders always have an account. That is 76% of order lines. Repeat purchase, RFM and cohorts use only the identified orders.
- 2,271 of the 4,000 customers (2,217 consumers and 54 business accounts) place at least one identified order.
- An order has one to five lines. Wholesale orders have one line.

Costs and returns
- Shipping: online 5.20 plus 0.60 per extra unit, marketplace 3.80 per order, wholesale 1.5% of revenue, retail none. Shipping fees paid by customers are not in revenue.
- Payment fee: online 1.8% plus 0.25 per order, retail 0.9%, marketplace 1.5%, wholesale none. Marketplace commission is 11%.
- Return probability per line is a category rate (Apparel 15%, Sports 7%, Electronics 6%, Home 5%, Beauty 2.5%, Office 2%) times a channel factor (Online 1.5, Marketplace 1.2, Retail 0.5, Wholesale 0.25) times a SKU factor. Four SKUs return more often than normal.
- Returns that would arrive after 2025-12-31 are left out, so return rates for late December 2025 are too low.

Known limits
- One warehouse, so the data has no transfers between regions.
- The data period is fixed at three calendar years.
- Currency, tax and exchange rates are not modelled.
