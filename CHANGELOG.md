# Changelog

## 2.0 (November 2026)

A new workbook, a new data set and a Python companion. Version 1 is kept untouched in `v1/`.

### Added

- Three years of synthetic daily data (2023 to 2025) for 42 SKUs, 6 categories, 5 regions, 4 channels and 4,000 customers, with a promotion calendar, returns, shipping and payment fees, supplier delays and stock-outs. It is built by `tools/generate_data.py` from a seed.
- A dirty sales export with a cleaning script and a log of every change (`tools/clean_data.py`, `data/raw/`).
- `Excel_Retail_Operations_Dashboard_v2.xlsx`: 24 sheets with live formulas over Excel tables, named ranges, drop-downs, conditional formats and native charts. It covers a dashboard with year, region, channel and category selectors, contribution margin and a margin bridge, ABC-XYZ, reorder points and economic order quantities, a tested forecast, scenarios with a sensitivity grid, RFM, cohorts and lifetime value, promotion lift and break-even, returns, and a Checks sheet with 42 tests.
- `analysis/`: the same calculations in pandas, writing CSV files and charts to `outputs/`.
- `tests/`: 37 pytest tests on the generator, the cleaning script, the calculations and the workbook structure. A parity test reads the comparison file written by `tools/verify_workbook.py`.
- `tools/verify_workbook.py`: recalculates the workbook in LibreOffice and compares 1,415 figures with pandas.
- Documentation: README, walkthrough, methodology, data dictionary and manual steps.

### What was wrong in version 1

I checked version 1 against its own data with `analysis/v1_review.py`. The results are in `outputs/v1_review.csv`.

- **ABC classes were wrong.** The cumulative share was worked out in product-code order, not in revenue order. The workbook showed 13 A, 3 B and 2 C SKUs. Sorted by revenue the split is 11 A, 4 B and 3 C. Four of the 18 SKUs were in the wrong class.
- **The margin story was not supported.** The dashboard said margin pressure was visible in heavy-discount months. Monthly gross margin ran from 60.05% (November) to 60.51% (January), a spread of 0.46 points, and the average discount stayed between 5.4% and 5.8%. The small drift came from mix: Electronics, with a 56.9% margin, grew from 21.5% of revenue in January to 28.6% in December.
- **Dates and months disagreed.** 98 of 2,592 sales rows had an order date in a different month from the Month label, and the earliest date was 31 December 2024. In the workbook every date was one day later than in the CSV file.
- **The reorder rule could not fire.** For all 54 warehouse rows the reorder point was below demand over the lead time plus safety stock, by 50.7 units on average. No row was flagged Reorder Now.
- **The forecast looked better than it was.** The three-month average in the table included the month being forecast (error 2.8%). Used properly, forecasting April to December from the three months before, it was wrong by 5.2%, against 3.7% for simply repeating last month. Twelve months of data also cannot show a seasonal pattern.
- **Inventory wording disagreed.** The Assumptions sheet called stock above the upper cover limit healthy, while the formula and the methodology called it Overstock Watch. The dashboard counted warehouse rows as SKUs.

### Known limits of 2.0

- The workbook was recalculated and compared in LibreOffice, and opened in desktop Excel 16 on Windows, where all 42 checks pass. Mac Excel, Excel for the web and Google Sheets were not tested. Opening it in Excel found a bug that LibreOffice had hidden: the month-on-month text on the dashboard used `TEXT()` format codes that fail in Excel with a non-English regional setting. It is fixed and no longer uses `TEXT()` for numbers.
- PivotTables, slicers and Power Query are not in the file. `docs/manual-steps.md` shows how to add them.
- The promotion baseline and the elasticity estimates do not remove seasonality.
- Three quarters of sales lines carry no customer id, so customer measures cover identified customers only.
- The data is synthetic and the analysis finds rules the generator put there. It shows that the method works, not that the findings hold for a real business.
