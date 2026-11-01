# Methodology

How I calculated each thing, in the order of the workbook. The same formulas are in `analysis/metrics.py`, written again in pandas, and the two are compared in `tools/verify_workbook.py`.

All data is synthetic. Where a rule matters only because the data is synthetic, I say so.

## Data

- `tools/generate_data.py` builds the CSV files. Demand per SKU, day, region and channel is a Poisson draw around a rate made of popularity, month, yearly growth, weekday, channel share, promotion lift and noise. Each SKU then runs through a day-by-day stock simulation, and demand that finds an empty shelf is lost. [`data-dictionary.md`](data-dictionary.md) lists every assumption.
- The sales export in `data/raw/` is deliberately dirty. `tools/clean_data.py` repairs it with ten rules and logs each change. After cleaning, the table equals the original.
- The workbook does not carry order lines. `Data_Monthly` sums them to month x SKU x region x channel (16,634 rows). Returns are placed on the month of the original order, so a return in January for a December sale reduces December.

## Profit and margin

- Gross profit = net revenue - cost of goods sold. Cost of goods is quantity x the unit cost on the sale date. It is not a FIFO or average cost.
- Contribution margin = gross profit - shipping - payment fees - marketplace fees - refunds + cost of goods put back on the shelf - return shipping.
- Average discount = discounts / list value, where list value = units x list price.

## Margin bridge

Between a year A and a year B, for each SKU *i* with units *U*, list price per unit *P*, discount rate *d*, unit cost *C*, fees per unit *F* and returns cost per unit *R*:

- Margin per unit, year A: `CMU_A = P_A (1 - d_A) - C_A - F_A - R_A`.
- Volume = (U_B total - U_A total) x average margin per unit in year A.
- Mix = sum of `U_B,i x CMU_A,i` minus U_B total x average margin per unit in year A.
- List price = sum of `U_B,i x (P_B - P_A) x (1 - d_A)`.
- Discount = sum of `-U_B,i x P_B x (d_B - d_A)`.
- Unit cost, fees and returns = sum of `-U_B,i x` the change in that unit value.

The seven effects add up exactly to the change in contribution margin. A SKU that did not sell in one year takes the other year's unit values, so it shows up as mix and not as a price or cost effect.

## ABC and XYZ

- Window: the trailing 12 months before the as-of date (an assumption).
- ABC: rank SKUs by revenue. A SKU is class A if the revenue share of all higher-ranked SKUs is below 80%, B if below 95%, else C. Using the share before the SKU means the SKU that crosses the line is still in the higher class. Version 1 used the share including the SKU, on a list that was not sorted.
- XYZ: coefficient of variation (sample standard deviation / mean) of monthly demand over the last 24 months. X up to 0.40, Y up to 0.70, Z above. Demand is units sold plus lost units.

## Inventory

- Daily demand = demand in the window / days in the window.
- Protection period = average lead time + review days.
- Daily SD = monthly SD of demand / square root of days in a month.
- Safety stock = z x square root of (protection period x daily SD squared + (daily demand x lead time SD) squared). z = `NORM.S.INV` of the service level.
- Reorder point = daily demand x protection period + safety stock.
- Economic order quantity = square root of (2 x yearly demand x order cost / (holding rate x unit cost)), rounded up to a multiple of the minimum order quantity and never below it.
- Days of cover = stock on hand / daily demand. Turns = yearly cost of goods / (average stock x unit cost). GMROI = yearly gross profit / (average stock x unit cost).
- Overstock units = stock on hand - (reorder point + economic order quantity). Overstock cost = those units x unit cost x holding rate.
- Estimated lost revenue = lost units x average net price in the window.
- Status, in this order: Obsolete stock or Discontinued if the SKU has a discontinued date; Reorder now if stock on hand plus on order is at or below the reorder point; Stock-out risk if days of cover are below the lead time; Overstock if cover is above the limit; else OK.
- Suggested order = the larger of the minimum order and (reorder point + economic order quantity - stock position), rounded up to the minimum order.

## Forecast

- Series: monthly demand per category, 36 months.
- Methods: naive (last month), moving average of the last N months, seasonal naive (same month a year earlier) and seasonal index with trend.
- Seasonal index: for each complete calendar year in the training window, each month divided by the year's average; averaged by calendar month.
- Seasonal index forecast for month h ahead = L x g^((h + 5.5)/12) x index. L is the average of the last 12 months, g is L divided by the average of the 12 months before, and 5.5 is half of 11, the distance from the middle of the window to its end.
- Test: hold back the last M months, forecast them from the data before, and score with WAPE = sum of absolute errors / sum of actuals. MAPE is also shown. Choose the lowest WAPE per category.
- Band: the final index, applied to the complete years, leaves a spread of monthly ratios. The band is the forecast x (1 +/- z x that spread). It leaves out the uncertainty in L and g, so it is narrow.

## Scenarios

- Base year = the trailing window by category: units, revenue, cost.
- Price factor = (1 + price change) x (1 - promotion discount x share of year on promotion).
- Units = base units x (1 + demand shock) x price factor ^ (-elasticity). Revenue = units x average price x price factor. Cost = units x average unit cost.
- Elasticity by category = average over promotions of ln(1 + lift) / -ln(1 - discount), unless overridden. Promotions cluster in busy months, so this is overstated.
- Stock-out risk per SKU = 1 - NORM.S.DIST((stock position - mean demand over the protection period) / SD, TRUE). The protection period includes the supplier delay. Mean demand and SD use the scenario's demand multiplier. The portfolio figure is weighted by revenue over active SKUs.
- Sensitivity grid: gross profit for a price change and a demand shock, with one formula per cell.

## Customers

- RFM runs on consumers with at least one order. Recency = days since the last order. Frequency = orders. Monetary = net revenue. Each is cut into five scores at the 20th, 40th, 60th and 80th percentiles. Ties fall into the lower score. Recency is reversed so that 5 means recent.
- Segments, in order: Champions (R and F at least 4), Loyal (both at least 3), New or recent (R at least 4, F at most 2), At risk (R at most 2, F at least 3), Lost or hibernating (both at most 2), Needs attention (the rest).
- Repeat rate = consumers with two or more orders / consumers with one or more.
- Cohort = month of the first order. Retention for month N = customers from that cohort who ordered N months later / cohort size. Only identified orders count.
- Lifetime value = order value x orders per active year x contribution margin on consumer channels x retention / (1 + discount rate - retention).

## Promotions

- Baseline = average daily units, revenue and cost over up to 56 days before the promotion, in the same category and channels, leaving out any promotion day and the ten days after a promotion with a discount of 20% or more. At least ten such days are needed.
- Lift = units in the promotion / (baseline units a day x days) - 1.
- Margin dilution = baseline gross margin - promotion gross margin.
- Break-even uplift = discount / (margin at list price - discount). Margin at list price = (list value - cost) / list value on the promotion's units.
- Extra gross profit = (net revenue - cost in the promotion) - baseline gross profit a day x days.
- Seasonality is not removed, so promotions in November and December look better than they were.

## Returns

- Return rate = units returned / units sold. Cost of returns = refunds + return shipping - cost of goods put back on the shelf.
- The problem-SKU list ranks SKUs with enough sales (an assumption) by return rate.

## Checks

The Checks sheet compares totals with the CSV files, adds the same figures up in a second way, tests that the bridge closes, that no stock is negative and that no formula returns an error. The error test leaves out the chart helper range on `Forecast`, where a missing value (`#N/A`) is deliberate so that a line chart skips it.
