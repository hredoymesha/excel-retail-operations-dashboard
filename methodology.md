# Methodology

## Scenario

The workbook models a fictional multi-channel retail company selling products across electronics, office, home and kitchen, apparel, and beauty categories. The business operates across four Finnish regions and three sales channels.

The project combines sales performance, product profitability, inventory risk, and forecasting into one Excel decision-support workbook.

## Data Model

The workbook uses three input datasets:

- `sales_transactions_2025.csv`: transaction-level sales records by month, region, channel, SKU, units, price, discount, revenue, and profit.
- `product_master.csv`: SKU-level product metadata, including category, unit cost, unit price, supplier, lead time, reorder point, and safety stock.
- `inventory_snapshot.csv`: SKU and warehouse-level on-hand stock, in-transit stock, average monthly demand, and replenishment assumptions.

## Sales Analysis

Revenue is calculated as:

`Units Sold x Unit Price x (1 - Discount %)`

Gross profit is calculated as:

`Net Revenue - (Units Sold x Unit Cost)`

Gross margin is calculated as:

`Gross Profit / Net Revenue`

The monthly summary sheet uses formula-backed calculations to aggregate units, revenue, gross profit, margin, discount rate, order count, and revenue per order.

## Inventory Risk Logic

Available stock is calculated as:

`On Hand + In Transit`

Days of cover is calculated as:

`Available Stock / (Average Monthly Demand / 30)`

Inventory status uses the following logic:

- `Reorder Now`: available stock is below the reorder point
- `Stockout Risk`: days of cover is below the low-stock threshold
- `Overstock Watch`: days of cover is above the healthy cover threshold
- `Healthy`: stock level is within the expected range

The low-stock and healthy-cover thresholds are editable in the `Assumptions` sheet.

## ABC Analysis

The ABC analysis estimates each SKU's revenue contribution to total sales.

Revenue share is calculated as:

`SKU Revenue / Total Revenue`

Cumulative share is used to classify products:

- `A`: top products contributing to the first 80% of revenue
- `B`: products contributing from 80% to 95% of revenue
- `C`: remaining products

The cutoff percentages are editable in the `Assumptions` sheet.

## Forecast Model

The forecast model uses a three-month moving average for units and revenue.

Base forecast revenue is calculated from the average of the latest three months. Scenario revenue applies the demand uplift assumption:

`Base Forecast Revenue x (1 + Scenario Demand Uplift)`

This keeps the model simple, transparent, and easy to explain during interviews.

## Dashboard Design

The dashboard is built for executive scanning:

- KPI cards summarize the most important metrics.
- Trend charts show monthly revenue and gross profit movement.
- Bar charts compare region and category performance.
- Inventory status counts highlight operational risk.
- A short executive takeaway converts the numbers into business language.

## Limitations

The dataset is synthetic, so the analysis is designed to demonstrate method and structure rather than predict a real business outcome.

The forecast uses a simple moving average rather than advanced statistical modeling. This is intentional: the goal is to keep the workbook explainable and recruiter-friendly.
