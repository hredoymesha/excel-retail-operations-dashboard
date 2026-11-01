# Manual steps

Some things were done by hand in Excel, and some things were not tested. This page covers both.

## What the build script leaves out

`tools/build_workbook.py` writes the formulas, tables, named ranges, charts, drop-downs and conditional formats. It can't write a PivotTable, slicers or Power Query connections. I added those in Excel afterwards, on two sheets, `Pivot_Revenue` and `Power_Query`. If you build the workbook again with the script, they disappear, so either keep the saved file or repeat the steps below.

## The PivotTable and slicers

It sits on the table `tblMonthly` (sheet `Data_Monthly`), which has one row per month, SKU, region and channel.

1. Click a cell inside the table on `Data_Monthly`.
2. Insert tab, PivotTable, New Worksheet, OK.
3. Drag `category` to Rows, `year` to Columns and `net_revenue` to Values (it must say Sum of net_revenue).
4. Right-click a number, Number Format, and pick a euro format with no decimals.
5. Click inside the PivotTable, then PivotTable Analyze, Insert Slicer. Tick `region` and `channel`.
6. Click a slicer button to filter. Hold Ctrl to pick several. The funnel icon clears the filter.
7. For the chart, PivotTable Analyze, PivotChart, clustered column.

## Power Query

The `Power_Query` sheet has six queries: `sales_lines`, `returns`, `products`, `customers`, `promotions` and `sales_with_products` (sales joined to products on `sku`). They only make a connection. To load one, go to Data, Queries & Connections, right-click it and choose Load To.

The cell `DataFolder` on that sheet works out the data folder from where the workbook is saved, so the workbook has to stay in the project folder, next to `data`.

To build a query like these yourself:

1. Data tab, Get Data, From File, From Text/CSV, and pick `data\sales_lines.csv`.
2. Transform Data. Check that `order_date` is a Date and the money columns are Decimal Number.
3. Home, Close & Load, Close & Load To, then Only Create Connection.
4. Do the same for the other CSV files.
5. To join two, Data, Get Data, Combine Queries, Merge. Pick both queries, click `sku` in each and use a Left Outer join.
6. After the scripts write new CSV files, Data, Refresh All.

If Excel can't find the files after you move the project, edit the query and fix the path in the Source step.

## Screenshots

The ten images in `screenshots/` were taken from desktop Excel 16 with the formula bar and headings hidden. A few were scaled up by about 1.5 times, so they are slightly soft.

| File | Shows |
|---|---|
| `01_dashboard.png` | `Dashboard`, all drop-downs on All |
| `02_dashboard_filtered.png` | `Dashboard`, 2024, Tampere, Online, Apparel |
| `03_margin_bridge.png` | `Profit_Margin`, profit and loss and the bridge |
| `04_abc_xyz.png` | `Products`, the matrix and the scorecard |
| `05_inventory.png` | `Inventory`, summary and reorder list |
| `06_forecast.png` | `Forecast`, method table, chart and forecast |
| `07_scenarios.png` | `Scenarios`, assumptions, results and chart |
| `08_cohorts.png` | `Customers`, the cohort heat map |
| `09_checks.png` | `Checks`, all PASS |
| `10_pivot_table.png` | `Pivot_Revenue` |

To retake one: wait until the status bar stops saying Calculate, untick Formula Bar and Headings on the View tab, pick a zoom that fits, press Windows + Shift + S, drag around the sheet and save as PNG. Keep the title bar and taskbar out of the frame.

## What was and wasn't tested

I opened the workbook in desktop Excel 16 on Windows, recalculated it, counted error cells and read the Checks sheet. I also recalculated it in LibreOffice and compared it with pandas (`outputs/workbook_parity.csv`). Mac Excel, Excel for the web and Google Sheets were not tried, and neither was printing on paper.

Excel showed one problem LibreOffice had hidden. Text built with `TEXT()` and a number format breaks under some regional settings, so the workbook no longer uses it.

The workbook uses 39 functions: ABS, AND, AVERAGE, AVERAGEIF, AVERAGEIFS, CEILING, CHOOSE, COUNT, COUNTA, COUNTIF, COUNTIFS, DATE, EDATE, IF, IFERROR, INDEX, ISERROR, ISNUMBER, LN, MATCH, MAX, MIN, MOD, MONTH, NA, NOT, OR, RANK, SQRT, SUM, SUMIF, SUMIFS, SUMPRODUCT, TEXT, YEAR, NORM.S.DIST, NORM.S.INV, PERCENTILE.INC and STDEV.S. The last four need Excel 2010. Nothing needs Microsoft 365. I left out `FORECAST.ETS` because LibreOffice doesn't evaluate it the way Excel does, so the forecast uses a seasonal index you can follow cell by cell.

LibreOffice and Excel can differ in the last decimals of `PERCENTILE.INC`, `NORM.S.INV` and `STDEV.S`. The tolerances are in `outputs/workbook_parity.csv`.
