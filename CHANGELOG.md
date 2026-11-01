# Changelog

## 2.0, November 2026

A new workbook on a new, larger data set, plus Python scripts that rebuild the numbers. Version 1 is kept as it was in `v1/`.

What is new: three years of synthetic daily data (42 SKUs, 6 categories, 5 regions, 4 channels, 4,000 customers) with promotions, returns, shipping and payment fees, supplier delays and stock-outs. A messy sales export with a cleaning script and a log of every change. A workbook with 24 sheets built by script: a dashboard with selectors, contribution margin and a margin bridge, ABC-XYZ, reorder points, a forecast tested on held-back months, scenarios, RFM and cohorts, promotion lift, returns, and a Checks sheet with 42 tests. Two more sheets, `Pivot_Revenue` and `Power_Query`, were added by hand in Excel. The `analysis/` scripts, 39 tests and `tools/verify_workbook.py` check the numbers. The docs are in `docs/`.

### What was wrong in version 1

I went back over version 1 with `analysis/v1_review.py`. The results are in `outputs/v1_review.csv`.

The ABC analysis worked out cumulative share in product-code order, not revenue order. The workbook showed 13 A, 3 B and 2 C SKUs. Sorted by revenue it is 11, 4 and 3, so four of the 18 SKUs were in the wrong class.

The dashboard text said margin pressure showed in heavy-discount months. It didn't. Monthly gross margin ran from 60.05% in November to 60.51% in January, a spread of 0.46 points, and the average discount stayed between 5.4% and 5.8%. The small drift was mix: Electronics, which has a 56.9% margin, grew from 21.5% of revenue in January to 28.6% in December.

98 of the 2,592 sales rows had an order date in a different month from their Month label, and the earliest date was 31 December 2024. In the workbook every date was a day later than in the CSV.

The reorder rule could not fire. In all 54 warehouse rows the reorder point was below demand over the lead time plus safety stock, by 50.7 units on average, and no row was flagged Reorder Now.

The forecast looked better than it was. Its three-month average included the month being forecast (error 2.8%). Forecasting April to December from the three months before gives 5.2%, against 3.7% for just repeating last month. Twelve months of data is also too short to show seasonality.

Smaller things: the Assumptions sheet called stock above the upper cover limit healthy while the formula called it Overstock Watch, and the dashboard counted warehouse rows as SKUs.

### Still open in 2.0

- The workbook was recalculated and compared in LibreOffice, and opened in desktop Excel 16 on Windows, where all 42 checks pass. Mac Excel, Excel for the web and Google Sheets were not tried. Opening it in Excel did turn up one bug LibreOffice had hidden: the month-on-month text on the dashboard used `TEXT()` format codes that fail under some regional settings. It is fixed.
- Building the workbook again with the script drops `Pivot_Revenue` and `Power_Query`. `docs/manual-steps.md` shows how to add them.
- The promotion baseline and the elasticity estimates do not remove seasonality.
- About three quarters of sales lines have no customer id, so customer figures cover identified customers only.
- The data is synthetic and the analysis finds rules the generator put there. It shows the method works, not that the findings hold for a real business.
