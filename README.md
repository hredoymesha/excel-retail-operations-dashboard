# Excel Retail Operations Dashboard

> **All data in this project is synthetic.** The company, products, suppliers and customers are made up, and no real person, brand or business is described. The numbers say nothing about any real retailer.

This is an Excel workbook for a fictional Finnish retailer that sells through four channels: online, retail stores, a marketplace and wholesale. A Python companion rebuilds the numbers from the CSV files, so every figure can be checked.

Version 1 was a single-year workbook. Version 2 uses three years of daily data, adds the analysis a retail analyst is usually asked for, and tests the workbook against pandas. Version 1 is kept in [`v1/`](v1/). Where version 1 was wrong, [`CHANGELOG.md`](CHANGELOG.md) says so.

## Business questions

- Where does margin come from, and where does it leak once shipping, fees, discounts and returns are counted?
- What moved contribution margin between two years: volume, mix, price, discounts, cost or returns?
- Which SKUs carry the revenue, and which are steady enough to plan around?
- What should be reordered now, what is overstocked, and what do stock-outs cost?
- Which forecasting method works for each category, and what does next year look like?
- Do promotions pay for themselves? What happens if prices, suppliers or demand change?
- Who are the repeat customers, how fast do cohorts fade, and what is a customer worth?

## Key findings

Each figure is computed by the script named next to it. The numbers are for synthetic data and show what the workbook can do, not what retail is like.

- **Margin by channel.** Gross margin is 52.1% over the three years, but contribution margin is 37.3% once shipping, fees and returns come off. Marketplace earns 24.2% against 49.0% for retail. `analysis/kpis.py`
- **Margin bridge.** From 2024 to 2025 contribution margin moved from 314,713 to 317,479 euros (+2,766). List prices added 19,333 and unit costs took away 9,192. `analysis/kpis.py`
- **Stock-outs.** In 2025 stock-outs cost 2,088 units, 5.4% of demand, about 49,737 euros of revenue. On the last day 4 SKUs are at or below their reorder point, 10 more have less cover than their lead time and 10 are overstocked. `analysis/abc_xyz.py`
- **Promotions.** 35 of 73 promotions that have a baseline added gross profit and 38 lost it. Together they changed gross profit by -3,838 euros. Baselines do not remove seasonality, so this is an estimate. `analysis/customers.py`
- **Returns.** Apparel returns 12.6% of units against 2.0% for office goods. Returns cost 139,089 euros, 5.8% of revenue. The worst SKU is a pair of jeans at 21.6%. `analysis/customers.py`
- **Customers.** 72% of the 2,217 consumers who bought ordered twice or more, and 47% of 2024 buyers ordered again in 2025. Champions are 19% of scored customers and 40% of their revenue. `analysis/customers.py`

The full list is in `outputs/key_findings.csv`.

## How it was built

- **Data.** `tools/generate_data.py` builds three years of daily sales for 42 SKUs in 6 categories, 5 regions, 4 channels and 4,000 customers. It includes a promotion calendar with price elasticity, seasonality, returns, shipping and payment fees, supplier delays and stock-outs. It is seeded, so it gives the same files every time.
- **Dirty data and cleaning.** A separate export in `data/raw/` carries duplicates, missing values and wrong dates. `tools/clean_data.py` repairs them and logs every change. The cleaned file matches the original exactly.
- **Workbook.** `tools/build_workbook.py` writes `Excel_Retail_Operations_Dashboard_v2.xlsx` with XlsxWriter: 24 sheets, live formulas over Excel tables, named ranges, drop-downs, conditional formats and native charts. Every input is on the Assumptions sheet.
- **Checks.** The Checks sheet has 42 tests that compare the workbook with the CSV files and with itself. `tools/verify_workbook.py` recalculates the workbook in LibreOffice and compares 1,415 figures with pandas. `tests/` holds the pytest suite.

## What I would do next

- Replace the synthetic data with a real extract and see which assumptions break first.
- Remove seasonality from the promotion baseline, and estimate elasticity with a model instead of averaging promotion lifts.
- Give the forecast a band that includes uncertainty in level and trend, and test more than three held-back months.
- Model stock by region and return flows into stock.
- Add the PivotTable and Power Query layer described in [`docs/manual-steps.md`](docs/manual-steps.md).

## Limits

- The data is synthetic and was built from the very rules the analysis then finds again. It shows that the method works. It does not show that the method works on real data.
- I opened the workbook in desktop Excel 16 on Windows, recalculated it there and took the screenshots from it. I did not test Mac Excel, Excel for the web or Google Sheets. See [`docs/manual-steps.md`](docs/manual-steps.md).
- The workbook keeps sales at month, SKU, region and channel level. Order-level detail is in the CSV files.
- Three quarters of order lines have no customer id, so the customer analysis describes identified customers only.
- Pivot tables, slicers and Power Query are not in the file. A script cannot write them reliably.

## Folder map

```
Excel_Retail_Operations_Dashboard_v2.xlsx   the workbook
README.md  CHANGELOG.md  LICENSE  requirements.txt
data/        CSV files (clean) and data/raw/ (dirty export and cleaning log)
tools/       generate_data.py, clean_data.py, check_data.py, build_workbook.py, verify_workbook.py
analysis/    pandas versions of the workbook's calculations, one script per topic
tests/       pytest suite
docs/        walkthrough.md, methodology.md, data-dictionary.md, manual-steps.md
outputs/     CSV results, charts, data checks and the workbook parity table
screenshots/ images you add yourself (see docs/manual-steps.md)
v1/          version 1, untouched
```

## How to open it

Open `Excel_Retail_Operations_Dashboard_v2.xlsx` in Excel 2010 or later. If Excel asks, choose Enable Editing. Start on `Start_Here`, then go to `Dashboard` and use the yellow drop-downs. Change inputs on `Assumptions`. `Checks` should show every row as PASS.

## How to reproduce

```
pip install -r requirements.txt
python tools/generate_data.py
python tools/clean_data.py
python tools/check_data.py
python analysis/run_all.py
python tools/build_workbook.py
python -m pytest tests
```

`tools/verify_workbook.py` needs LibreOffice and takes several minutes. `python tools/build_workbook.py --no-values` skips the LibreOffice step that stores calculated values in the file.
