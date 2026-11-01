# Manual steps

The build script cannot do everything. This page covers the steps done by hand in Excel, the screenshots, and what was and was not tested.

## What a script cannot create reliably

The workbook builder (XlsxWriter) writes formulas, tables, named ranges, charts, drop-downs and conditional formats. It cannot write PivotTables, slicers or Power Query connections. The data is laid out as Excel tables so you can add them yourself in a few minutes. Nothing in the workbook depends on them.

## 1. Add a PivotTable with slicers

Use the table `tblMonthly` on the sheet `Data_Monthly`. It has one row per month, SKU, region and channel.

1. Click any cell inside the table on `Data_Monthly`.
2. On the **Insert** tab choose **PivotTable**. Pick **New Worksheet** and press **OK**.
3. In the field list drag `category` to **Rows**, `year` to **Columns** and `net_revenue` to **Values**. Check that it says Sum of net_revenue.
4. Right-click a number, choose **Number Format**, pick **Currency** with 0 decimals and euro sign.
5. Click inside the PivotTable. On the **PivotTable Analyze** tab choose **Insert Slicer**. Tick `region` and `channel`, press **OK**.
6. Click a slicer button to filter. Hold Ctrl to pick several. The button with the crossed funnel clears the filter.
7. Optional: on the **PivotTable Analyze** tab choose **PivotChart** and pick a clustered column chart.
8. Optional margin view: add a calculated field. On the **PivotTable Analyze** tab choose **Fields, Items & Sets** and then **Calculated Field**. Name it `gross_margin` with the formula `=(net_revenue-cogs)/net_revenue`.

Rename the new sheet to `Pivot_Revenue` and move it after `Returns` if you want it near the analysis sheets.

## 2. Load the CSV files with Power Query

This gives the workbook a refreshable link to the raw files.

1. Make sure the CSV files are in the `data` folder next to the workbook.
2. On the **Data** tab choose **Get Data**, then **From File**, then **From Text/CSV**.
3. Browse to `data\sales_lines.csv` and press **Import**. Excel shows a preview.
4. Press **Transform Data**. In the Power Query window check that `order_date` is a Date and that the money columns are Decimal Number. Fix any type that Excel guessed wrong.
5. On the **Home** tab choose **Close & Load**, then **Close & Load To...**. Pick **Only Create Connection** and tick **Add this data to the Data Model**. Press **OK**.
6. Repeat steps 2 to 5 for `returns.csv`, `products.csv`, `customers.csv` and `promotions.csv`.
7. To join them: **Data** tab, **Get Data**, **Combine Queries**, **Merge**. Choose `sales_lines` and `products` and click `sku` in both. Use a **Left Outer** join. Expand the `category` and `product_name` columns.
8. To refresh after the scripts write new CSV files: **Data** tab, **Refresh All**.

If Excel cannot find the file after you move the project, open **Data**, **Queries & Connections**, right-click the query, choose **Edit**, then open **Source** under Applied Steps and correct the path.

## 3. Screenshots

Nine screenshots are in `screenshots/`. They were taken from desktop Excel 16 with the formula bar and headings hidden. Each is at least 1600 pixels wide, and some were scaled up by about 1.5 times from the Excel capture. The data is synthetic.

| File | What it shows |
|---|---|
| `01_dashboard.png` | `Dashboard`, all drop-downs on All |
| `02_dashboard_filtered.png` | `Dashboard` with Year 2024, Region Tampere, Channel Online, Category Apparel |
| `03_margin_bridge.png` | `Profit_Margin`, the profit and loss, the bridge and their charts |
| `04_abc_xyz.png` | `Products`, the matrix and the start of the scorecard |
| `05_inventory.png` | `Inventory`, the summary and the reorder list |
| `06_forecast.png` | `Forecast`, the method table, the chart and the forecast |
| `07_scenarios.png` | `Scenarios`, assumptions, results and chart |
| `08_cohorts.png` | `Customers`, the cohort heat map |
| `09_checks.png` | `Checks`, every row PASS |

To retake one: open the workbook, wait for the status bar to stop saying Calculate, untick Formula Bar and Headings on the **View** tab, pick a zoom that fits the sheet, press Windows + Shift + S, drag a rectangle around the sheet only and save as PNG. Keep the title bar, taskbar, your user name and any file path out of the frame.

## 4. Testing notes

- The workbook was opened in desktop Excel 16 on Windows (recalculated, error cells counted, Checks sheet read) and in LibreOffice (recalculated and compared with pandas, see `outputs/workbook_parity.csv`). It was not tested in Mac Excel, Excel for the web or Google Sheets, and printing to paper was not tested.
- Opening the file in Excel showed one problem LibreOffice had hidden: text built with `TEXT()` and a number format breaks under some regional settings. The workbook no longer uses it.
- The workbook uses 39 functions: ABS, AND, AVERAGE, AVERAGEIF, AVERAGEIFS, CEILING, CHOOSE, COUNT, COUNTA, COUNTIF, COUNTIFS, DATE, EDATE, IF, IFERROR, INDEX, ISERROR, ISNUMBER, LN, MATCH, MAX, MIN, MOD, MONTH, NA, NOT, OR, RANK, SQRT, SUM, SUMIF, SUMIFS, SUMPRODUCT, TEXT, YEAR, NORM.S.DIST, NORM.S.INV, PERCENTILE.INC and STDEV.S (the last four need Excel 2010 or later). LibreOffice evaluated every one of them, and no formula returned an error. None of them needs Microsoft 365. `FORECAST.ETS` is not used, because LibreOffice does not evaluate it the same way as Excel, so the forecast uses an explicit seasonal index that you can read cell by cell. Every function was evaluated, but evaluating in LibreOffice is not the same as evaluating in Excel.
- LibreOffice and Excel can differ in the last decimal places of `PERCENTILE.INC`, `NORM.S.INV` and `STDEV.S`. The parity tolerances are in `outputs/workbook_parity.csv`.
- The first open in Excel recalculates the whole workbook. It took LibreOffice a few minutes. Excel was not timed.
