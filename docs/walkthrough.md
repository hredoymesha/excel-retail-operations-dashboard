# Walkthrough

Seven questions I asked of the data. Each has the question, the data used, the method, what came out and what I would do about it. The data is made up, so the actions are examples, not advice for a real shop. The numbers come from the scripts in `analysis/` and are in `outputs/`.

## 1. Where does margin leak?

Question: Gross margin looks healthy. What is left after shipping, payment and marketplace fees, and returns?

Data: `sales_lines.csv` for revenue, cost, shipping and fees, and `returns.csv` for refunds, return labels and goods put back on the shelf. In the workbook: `Data_Monthly`.

Method: Contribution margin = net revenue - cost of goods - shipping - payment fees - marketplace fees - refunds + cost of restocked returns - return shipping. Shown by channel on `Dashboard` and `Profit_Margin`. `analysis/kpis.py`.

Finding: Gross margin is 52.1% over the three years and contribution margin 37.3%. By channel, contribution margin is 49.0% in retail, 46.7% in wholesale, 29.5% online and 24.2% on the marketplace. Gross margin is about the same in all four, so the gap is fees, shipping and returns.

Action: Look at online and marketplace delivery cost and return rates before looking at price. A marketplace sale at the same gross margin keeps half of what a store sale keeps.

## 2. What moved margin from one year to the next?

Question: Contribution margin rose from 314,713 to 317,479 euros between 2024 and 2025. Why so little?

Data: `Data_Monthly`, 2024 and 2025, by SKU.

Method: A bridge that splits each SKU's contribution per unit into list price, discount rate, unit cost, fees and returns, and values the change at this year's units. Volume and mix come from the change in units at last year's margin. The effects add up to the exact change. Waterfall chart on `Profit_Margin`. `analysis/kpis.py`.

Finding: Volume added 9,431 and price 19,333. Mix took away 5,895, unit cost 9,192, shipping and fees 6,253 and returns 4,306. Discounts cost 351. The price gain was mostly absorbed by cost, fees and returns. By category (`outputs/margin_bridge_by_category.csv`), Electronics fell from 33,219 to 24,130 euros, with fewer units after two products were discontinued and lower list prices. Apparel, Home & Kitchen and Sports & Outdoor carry most of the cost drag (3,221, 2,780 and 2,417 euros).

Action: Look at Electronics volume first, then at whether list prices in Apparel, Home & Kitchen and Sports & Outdoor can follow their costs.

## 3. Which SKUs matter, and which can be planned?

Question: Where should planning effort go?

Data: 2025 revenue by SKU and monthly demand (units sold plus lost units) for the last 24 months. `Products`, `Calc_Sku`.

Method: ABC by cumulative revenue share before each SKU (A below 80%, B below 95%). XYZ by the coefficient of variation of monthly demand (X up to 0.40, Y up to 0.70). `analysis/abc_xyz.py`.

Finding: 22 of 42 SKUs form class A and make 705,133 of 858,154 euros of 2025 revenue (82%). Eight of them are steady (AX). Three SKUs are small and erratic (CZ): the discontinued fleece pullover and speaker, and the ski wax kit.

Action: Plan AX SKUs on a fixed reorder point and review. Do not spend forecasting time on CZ.

## 4. What should be reordered, and what do stock-outs cost?

Question: Which SKUs need an order now, which tie up cash, and how much did empty shelves cost?

Data: `inventory_daily.csv` (stock, lost units), `purchase_orders.csv`, `products.csv` (lead time, minimum order). `Inventory`.

Method: Safety stock = z x square root of (protection period x daily variance + (demand x lead time SD) squared), with z from the 95% service level. Reorder point = demand over the protection period + safety stock. Order quantity = economic order quantity rounded up to the minimum order. Status flags use stock on hand and on order against the reorder point and days of cover. `analysis/abc_xyz.py`.

Finding: Stock-outs cost 2,088 units in 2025, 5.4% of demand, about 49,737 euros of revenue. Four SKUs are at or below their reorder point: the merino base layer, the gel pens, the daypack and the tent. Ten more have less cover than their lead time. Ten are overstocked, at a holding cost of about 5,904 euros a year, and three discontinued SKUs hold 690 units.

Action: Place the orders in the reorder list on `Inventory` (suggested quantities are there). Stop reordering the overstocked SKUs. Decide whether to mark down the 690 units of discontinued stock.

## 5. Which forecast method should be used?

Question: Which method predicts each category best, and what does 2026 look like?

Data: Monthly demand by category, 36 months.

Method: Hold back the last three months. Forecast them with four methods using only earlier data: naive, three-month average, seasonal naive and a seasonal index with trend. Pick the method with the lowest WAPE per category. Forecast twelve months with that method. `analysis/forecast.py`.

Finding: The seasonal index with trend wins in four categories (Electronics, Apparel, Beauty & Care and Sports & Outdoor), seasonal naive in Home & Kitchen and the moving average in Office. Next-year demand comes to 40,637 units. In 2025 customers bought 36,571 units and stock-outs lost another 2,088.

Action: Use the chosen method per category, and re-run the test each quarter. Three held-back months is a thin test, so I would not trust a small gap between methods.

## 6. Do promotions pay?

Question: Did the promotions earn back their discount?

Data: `promotions.csv` and the sales lines that carry a promotion id. `Promotions`.

Method: Baseline = average daily sales over up to 56 days before the promotion, without other promotion days. Lift = units in the promotion against the baseline. Break-even uplift = discount / (margin at list price - discount). Extra gross profit = promotion gross profit minus baseline gross profit over the same days. `analysis/customers.py`.

Finding: Of 73 promotions with a baseline, 35 added gross profit and 38 lost it, for a net change of -3,838 euros. Summer Clearance lost 4,124 euros over three years and Back to Office added 1,873. Black Friday week with a 30% discount in 2024 lost 1,679 euros; at 25% in 2023 it made 212.

Action: Cut the depth of clearance discounts or shorten them. Because the baseline ignores seasonality, treat the November and December lifts with care.

## 7. Who are the repeat customers?

Question: How loyal are customers, and what is one worth?

Data: Orders that carry a customer id (24% of order lines). `Customers`.

Method: RFM scores by quintile among consumers who bought. Cohorts by first-order month. Lifetime value = order value x orders a year x contribution margin x retention / (1 + discount rate - retention). `analysis/customers.py`.

Finding: 72% of 2,217 buyers ordered more than once. Champions are 19% of scored customers and 40% of their revenue. At risk customers (18%) hold 24% of revenue and have not ordered for about 644 days on average. Yearly retention is 47%.

Action: Contact the at-risk group first: they used to order often and carry a quarter of revenue. Collect customer ids at the till and at online checkout, because most orders cannot be tied to anyone.
