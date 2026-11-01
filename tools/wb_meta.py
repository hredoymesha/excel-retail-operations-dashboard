"""Checks, start page and notes sheets."""
from __future__ import annotations

import datetime as dt

from analysis.common import CATEGORIES, CHANNELS
from wb_core import DEC2, EUR, INT, PAL, PCT, Ctx, absref
from wb_data import NSKU, REGIONS


def _sumif_parts(measure: str, rng: str, items: list[str]) -> str:
    return "+".join(f'SUMIFS({measure},{rng},"{i}")' for i in items)


def build_checks(ctx: Ctx) -> None:
    ws = ctx.ws["Checks"]
    ctx.banner(ws, "Checks", 7, "Every row compares the workbook with something independent: the CSV files, another formula path, or a rule that must hold.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 5)
    ws.set_column(1, 1, 84)
    ws.set_column(2, 4, 16)
    ws.set_column(5, 5, 10)
    ws.set_column(6, 6, 56)
    ws.write(3, 1, "Overall result", ctx.fmt(bold=True, font_size=12, align="right", font_color=PAL["navy"]))
    hdr = ctx.head()
    ws.write_row(5, 0, ["#", "Check", "Workbook", "Expected", "Difference", "Status", "Note"], hdr)
    ct = lambda i: ctx.refs[f"ct{i}"]
    r = ctx.refs
    fc = ctx.fc
    total = "SUM(m_net_revenue)"
    dash = ("SUMPRODUCT((m_year>=yr_lo)*(m_year<=yr_hi)*(((sel_region=\"All\")+(m_region=sel_region))>0)"
            "*(((sel_channel=\"All\")+(m_channel=sel_channel))>0)*(((sel_category=\"All\")+(m_category=sel_category))>0)*m_net_revenue)")
    pl = ctx.pl_rows
    plcell = lambda k: f"Profit_Margin!$B${pl[k]+1}"
    cm_lines = "+".join(plcell(k) for k in ["net_revenue", "cogs", "shipping", "payment_fee", "platform_fee", "refund_amount", "restock_cogs", "return_shipping"])
    last_err = {
        "Dashboard": "$A$1:$N$62", "Profit_Margin": "$A$1:$AG$130", "Products": "$A$1:$P$70", "Inventory": "$A$1:$AA$80",
        "Forecast": f"$A$1:$AD${fc['R_CH']-1}", "Scenarios": "$A$1:$X$150", "Customers": "$A$1:$AA$110", "Promotions": "$A$1:$U$120",
        "Returns": "$A$1:$M$80", "Calc_Dashboard": "$A$1:$O$130", "Calc_Sku": "$A$1:$V$50", "Calc_SkuMonth": "$A$1:$AN$140",
        "Calc_Customers": f"$A$1:$J${4 + len(ctx.data['customers']) + 1}",
    }
    rows = [
        # label, workbook formula, expected formula, number format, mode, note
        ("Net revenue in the workbook equals the CSV total", f"={total}", f"={ct(2)}", EUR, "eq", "Control totals are on Data_Control."),
        ("Units sold equal the CSV total", "=SUM(m_units)", f"={ct(1)}", INT, "eq", ""),
        ("Order lines equal the CSV row count", "=SUM(m_order_lines)", f"={ct(0)}", INT, "eq", "Row counts of sales_lines.csv."),
        ("Cost of goods equals the CSV total", "=SUM(m_cogs)", f"={ct(3)}", EUR, "eq", ""),
        ("Shipping equals the CSV total", "=SUM(m_shipping)", f"={ct(4)}", EUR, "eq", ""),
        ("Refunds equal the CSV total", "=SUM(m_refund_amount)", f"={ct(8)}", EUR, "eq", "Refunds sit on the month of the order."),
        ("Lost units equal the CSV total", "=SUM(sm_lost_units)", f"={ct(10)}", INT, "eq", ""),
        ("Products table has as many rows as products.csv", "=COUNTA(p_sku)", f"={ct(5)}", INT, "eq", ""),
        ("Customers table has as many rows as customers.csv", "=COUNTA(cu_customer_id)", f"={ct(6)}", INT, "eq", ""),
        ("Promotions table has as many rows as promotions.csv", "=COUNTA(pr_promo_id)", f"={ct(9)}", INT, "eq", ""),
        ("Regions add up to the total", "=" + _sumif_parts("m_net_revenue", "m_region", REGIONS), f"={total}", EUR, "eq", ""),
        ("Channels add up to the total", "=" + _sumif_parts("m_net_revenue", "m_channel", CHANNELS), f"={total}", EUR, "eq", ""),
        ("Categories add up to the total", "=" + _sumif_parts("m_net_revenue", "m_category", CATEGORIES), f"={total}", EUR, "eq", ""),
        ("SKUs add up to the total (Returns sheet)", f"={r['ret_sku_revenue']}", f"={total}", EUR, "eq", ""),
        ("Dashboard revenue equals an independent SUMPRODUCT with the same drop-downs", f"={r['kpi_net_revenue']}", f"={dash}", EUR, "eq", "Changes with the selectors, so test it with other selections too."),
        ("Contribution margin equals the sum of the profit and loss lines", f"={r['pl_cm']}", f"={cm_lines}", EUR, "eq", ""),
        ("Margin bridge closes: reference year equals year before plus all effects", f"={r['bridge_cm_ref']}", f"={r['bridge_cm_ref']}-{r['bridge_gap']}", EUR, "eq", ""),
        ("Bridge end point equals the SKU working table total", f"={r['bridge_cm_ref']}", f"={r['bridge_cm_work']}", EUR, "eq", ""),
        ("ABC-XYZ matrix counts every SKU", f"={r['abc_total']}", "=COUNTA(p_sku)", INT, "eq", ""),
        ("ABC-XYZ revenue shares add up to 100%", f"={r['abc_share_total']}", "=1", PCT, "ratio", ""),
        ("Inventory status counts add up to the number of SKUs", f"={r['inv_status_total']}", "=COUNTA(p_sku)", INT, "eq", ""),
        ("No negative stock on hand or on order", "=MIN(MIN(p_on_hand_end),MIN(p_on_order_end))", "=0", INT, "ge", "Must be zero or more."),
        ("Hold-out months in the forecast test equal the assumption", f'=COUNTIF({r["fc_hold_actual_first"].split("!")[0]}!$C${fc["R_HOLD"]+2}:$H${fc["R_HOLD"]+2},">0")', "=holdout", INT, "eq", ""),
        ("Forecast for the next 12 months is not negative", f"={r['fc_total_next12']}", "=0", INT, "ge", ""),
        ("Cohort sizes add up to consumers who bought", f"={r['cohort_size_sum']}", f"={r['consumers_bought']}", INT, "eq", ""),
        ("RFM segments add up to consumers who bought", f"={r['rfm_total']}", f"={r['consumers_bought']}", INT, "eq", ""),
        ("Base scenario revenue equals trailing-window revenue", f"={r['scn_base_rev']}", f"=SUM(Calc_Sku!$D$5:$D${4+NSKU})", EUR, "eq", ""),
        ("Refunds by SKU add up to total refunds", f"={r['ret_sku_refunds']}", "=SUM(m_refund_amount)", EUR, "eq", ""),
        ("Refunds by category add up to total refunds", f"={r['ret_refund_total']}", "=SUM(m_refund_amount)", EUR, "eq", ""),
    ]
    for sheet, rng in last_err.items():
        rows.append((f"No formula errors on {sheet}", f"=SUMPRODUCT(--ISERR({sheet}!{rng}))", "=0", INT, "eq", ""))
    first = 6
    for i, (label, wbf, exp, num, mode, note) in enumerate(rows):
        rr = first + i
        x = rr + 1
        ws.write(rr, 0, i + 1, ctx.cell("0", align="center"))
        ws.write(rr, 1, label, ctx.cell(text_wrap=True))
        ws.write_formula(rr, 2, wbf, ctx.cell(num))
        ws.write_formula(rr, 3, exp, ctx.cell(num))
        ws.write_formula(rr, 4, f"=C{x}-D{x}", ctx.cell(DEC2 if num != PCT else "0.0000"))
        if mode == "eq":
            st = f'=IF(ABS(E{x})<=check_tol,"PASS","FAIL")'
        elif mode == "ratio":
            st = f'=IF(ABS(E{x})<=ratio_tol,"PASS","FAIL")'
        else:
            st = f'=IF(C{x}>=D{x},"PASS","FAIL")'
        ws.write_formula(rr, 5, st, ctx.cell(bold=True, align="center"))
        ws.write(rr, 6, note, ctx.cell(text_wrap=True, font_color=PAL["slate"]))
    last = first + len(rows)
    ws.merge_range(3, 2, 3, 4, "", ctx.fmt(bold=True, font_size=12, align="center"))
    ws.write_formula(3, 2, f'=IF(COUNTIF($F$7:$F${last},"FAIL")=0,"All "&COUNTA($F$7:$F${last})&" checks pass",COUNTIF($F$7:$F${last},"FAIL")&" of "&COUNTA($F$7:$F${last})&" checks fail")',
                     ctx.fmt(bold=True, font_size=12, align="center", border=1, border_color=PAL["line"]))
    good = ctx.fmt(bold=True, bg_color=PAL["pass_fill"], font_color=PAL["pass_font"], align="center")
    bad = ctx.fmt(bold=True, bg_color=PAL["fail_fill"], font_color=PAL["fail_font"], align="center")
    ws.conditional_format(first, 5, last - 1, 5, {"type": "cell", "criteria": "==", "value": '"PASS"', "format": good})
    ws.conditional_format(first, 5, last - 1, 5, {"type": "cell", "criteria": "==", "value": '"FAIL"', "format": bad})
    ws.conditional_format(3, 2, 3, 2, {"type": "text", "criteria": "containing", "value": "All", "format": good})
    ws.conditional_format(3, 2, 3, 2, {"type": "text", "criteria": "containing", "value": "fail", "format": bad})
    ws.freeze_panes(6, 2)
    ctx.checks_range = (first, last)
    ctx.n_checks = len(rows)
    ctx.refs["checks_overall"] = absref("Checks", 3, 2)


DESC = {
    "sheets": [
        ("Dashboard", "Drop-downs for year, region, channel and category drive the KPI cards, trend and margin charts, top and bottom products and attention lists."),
        ("Profit_Margin", "Profit and loss to contribution margin, and a bridge from the year before showing volume, mix, price, discount, cost, fee and return effects."),
        ("Products", "ABC by revenue, XYZ by demand variability, the 3 x 3 matrix, Pareto chart and a scorecard for every SKU."),
        ("Inventory", "Safety stock, reorder point, economic order quantity, cover, turns, GMROI, overstock cost, lost sales, status flags and a sorted reorder list."),
        ("Forecast", "Monthly demand by category, four methods tested on held-back months, the best one forecasting twelve months with a band."),
        ("Scenarios", "Five scenarios with an assumptions table, revenue, margin and stock-out risk, and a two-way sensitivity grid."),
        ("Customers", "RFM scores and segments, repeat purchase, monthly cohort retention heat map and a lifetime value estimate."),
        ("Promotions", "Lift against a baseline, margin dilution and break-even uplift for every promotion."),
        ("Returns", "Return rates by category and SKU, cost of returns and the top problem SKUs."),
        ("Checks", "Reconciliations with the CSV files and internal consistency tests, each with a pass or fail."),
        ("Assumptions", "Every input in one place. Change a blue cell and the workbook updates."),
        ("Notes", "Methodology, assumptions, data dictionary and change log."),
        ("Calc_SkuMonth", "Working sheet: monthly units by SKU."),
        ("Calc_Sku", "Working sheet: SKU measures for ABC, XYZ and stock rules."),
        ("Calc_Dashboard", "Working sheet: everything the Dashboard needs."),
        ("Calc_Customers", "Working sheet: RFM scores per customer."),
        ("Data_Monthly", "Table tblMonthly: sales by month, SKU, region and channel. Ready for a PivotTable."),
        ("Data_Products", "Table tblProducts: SKU attributes and the stock position on the last day."),
        ("Data_StockMonth", "Table tblStockMonth: lost units and stock-out days by SKU and month."),
        ("Data_Customers", "Table tblCustomers: one row per customer with order history."),
        ("Data_Cohort", "Table tblCohort: customers active by first-order month and months since."),
        ("Data_Promo", "Table tblPromo: one row per promotion with baseline sales."),
        ("Data_Control", "Totals read from the CSV files, used by the Checks sheet."),
    ],
}


def build_start(ctx: Ctx) -> None:
    ws = ctx.ws["Start_Here"]
    ws.set_column(0, 0, 2)
    ws.set_column(1, 1, 24)
    ws.set_column(2, 2, 110)
    ws.set_row(0, 34)
    ws.merge_range(0, 0, 0, 2, "  Retail operations dashboard, version 2", ctx.title())
    ws.merge_range(1, 1, 1, 2, "All data in this workbook is synthetic. The company, products, suppliers and customers are made up. No real person, brand or business is described.",
                   ctx.fmt(bold=True, font_color=PAL["fail_font"], bg_color=PAL["fail_fill"], text_wrap=True, valign="vcenter"))
    ws.set_row(1, 34)
    wrap = ctx.fmt(text_wrap=True, valign="top")
    lab = ctx.fmt(bold=True, font_color=PAL["navy"], valign="top")
    rows = [
        ("Purpose", "A workbook for a made-up Finnish shop that sells online, in stores, on a marketplace and wholesale. It shows where margin comes from and where it leaks, which products matter, what to reorder, what next year might look like, and what changes if prices, promotions, suppliers or demand move."),
        ("How to use it", "Start on the Dashboard and try the yellow drop-downs. The sheet map below says what is where. Change the yellow input cells on Assumptions or Scenarios and watch the numbers move. Checks tells you whether everything still adds up."),
        ("Excel versions", "Works in Excel 2010 or later and needs nothing from Microsoft 365. LibreOffice opens it too. It has only been tried in desktop Excel on Windows and in LibreOffice."),
        ("Calculation", "Every number is a formula over the Data_ sheets. The first open can take a few seconds. If nothing updates, press F9, because Excel may be on manual calculation."),
        ("Version", f"2.0, built {dt.date.today():%d %B %Y}. Version 1 is kept in the folder v1."),
    ]
    r = 3
    for k, v in rows:
        ws.write(r, 1, k, lab)
        ws.write(r, 2, v, wrap)
        ws.set_row(r, 48 if len(v) > 200 else 34)
        r += 1
    r += 1
    ws.write(r, 1, "Colour legend", ctx.h1())
    ws.write(r, 2, "", ctx.h1())
    legend = [
        (ctx.inp(None, bold=True, align="center"), "Input", "Yellow cell with blue text. Safe to change."),
        (ctx.cell(bold=True, align="center"), "Formula", "White cell with dark text. Do not overwrite."),
        (ctx.fmt(bold=True, bg_color=PAL["pass_fill"], font_color=PAL["pass_font"], align="center"), "Pass", "Check passed or healthy status."),
        (ctx.fmt(bold=True, bg_color=PAL["warn_fill"], font_color=PAL["warn_font"], align="center"), "Warning", "Reorder or watch."),
        (ctx.fmt(bold=True, bg_color=PAL["fail_fill"], font_color=PAL["fail_font"], align="center"), "Fail or risk", "Check failed or stock-out risk."),
    ]
    for i, (fm, name, text) in enumerate(legend):
        ws.write(r + 1 + i, 1, name, fm)
        ws.write(r + 1 + i, 2, text, ctx.fmt(valign="vcenter"))
    r += len(legend) + 2
    ws.write(r, 1, "Tab colours", ctx.h1())
    ws.write(r, 2, "", ctx.h1())
    for i, (n, t) in enumerate([("Dark blue", "Start and dashboard"), ("Teal", "Analysis sheets, checks, assumptions and notes"), ("Grey", "Helper sheets (Calc_ and Data_), hidden")]):
        ws.write(r + 1 + i, 1, n, ctx.cell())
        ws.write(r + 1 + i, 2, t, ctx.fmt())
    r += 7
    ws.write(r, 1, "Sheet map", ctx.h1())
    ws.write(r, 2, "", ctx.h1())
    link = ctx.fmt(font_color=PAL["teal"], underline=1)
    for i, (name, text) in enumerate(DESC["sheets"]):
        if name.startswith(("Calc_", "Data_")):
            ws.write(r + 1 + i, 1, name, ctx.fmt(font_color=PAL["slate"]))
        else:
            ws.write_url(r + 1 + i, 1, f"internal:'{name}'!A1", link, name)
        ws.write(r + 1 + i, 2, text, ctx.fmt(text_wrap=True, valign="top"))
    r += len(DESC["sheets"]) + 1
    ws.write(r, 2, "Sheets that start with Calc_ or Data_ are hidden. Right-click any sheet tab and choose Unhide to see them.", ctx.note())
    r += 2
    ws.write(r, 1, "Workbook checks", ctx.h1())
    ws.write(r, 2, "", ctx.h1())
    ws.write_formula(r + 1, 2, "=Checks!$C$4", ctx.fmt(bold=True))
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.set_first_sheet()
    ws.activate()


def build_notes(ctx: Ctx) -> None:
    ws = ctx.ws["Notes"]
    ws.set_column(0, 0, 3)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 2, 120)
    ctx.banner(ws, "Notes: methodology, assumptions, data dictionary and change log", 3)
    ctx.back_link(ws, 1)
    wrap = ctx.fmt(text_wrap=True, valign="top")
    lab = ctx.fmt(bold=True, font_color=PAL["navy"], valign="top", text_wrap=True)
    r = 4

    def section(title):
        nonlocal r
        ws.write(r, 1, title, ctx.h1())
        ws.write(r, 2, "", ctx.h1())
        r += 1

    def item(k, v):
        nonlocal r
        ws.write(r, 1, k, lab)
        ws.write(r, 2, v, wrap)
        ws.set_row(r, max(18, 14 * (len(v) // 125 + 1)))
        r += 1

    section("Methodology")
    item("Data", "Three years of daily sales for an invented retailer, made by a seeded script, cleaned, then added up to month x SKU x region x channel for this workbook. Customers, promotions, stock and purchase orders come from the same run. The scripts and CSV files are in the project folder.")
    item("Margin", "Gross profit is net revenue minus cost of goods sold at the unit cost on the sale date. Contribution margin takes off shipping, payment fees, marketplace fees and returns. Returns cost the refund and the return label, and give back the cost of goods that went back on the shelf. Returns sit on the month of the original order.")
    item("Margin bridge", "Between two years, each SKU's contribution per unit is split into list price, discount rate, unit cost, fees per unit and returns per unit. Volume and mix come from the change in units valued at last year's margin. The effects add up to the exact change in contribution margin. A SKU that did not sell in a year borrows the other year's unit values, so it adds mix but no price or cost effect.")
    item("ABC and XYZ", "ABC ranks SKUs by revenue in the trailing window. A SKU is A if the share of revenue before it is below the A limit, B below the B limit, else C. XYZ uses the coefficient of variation of monthly demand over the trailing window: X steady, Y moderate, Z erratic. Demand is units sold plus lost units unless the assumption is switched off.")
    item("Inventory", "Protection period = lead time + review days. Safety stock = z x square root of (protection period x daily variance + (daily demand x lead time SD) squared), with z from NORM.S.INV of the service level. Reorder point = demand over the protection period + safety stock. Economic order quantity = square root of (2 x yearly demand x order cost / (holding rate x unit cost)), rounded up to a multiple of the minimum order. Daily SD is the monthly SD divided by the square root of days in a month. Status: Reorder now when stock on hand plus on order is at or below the reorder point; Stock-out risk when days of cover are below the lead time; Overstock above the cover limit; Obsolete stock for discontinued SKUs that still hold units.")
    item("Forecast", "Demand by category and month. Four methods are tested on the last N months (hold-out): naive (last month), moving average, seasonal naive (same month last year) and a seasonal index with trend. The seasonal index is the average of each month's ratio to its calendar-year mean over complete years. The forecast is the average of the last 12 months, grown at the last year-on-year ratio, times the index. The best method per category by WAPE forecasts the next 12 months. The band uses the spread of the seasonal-index residuals and ignores uncertainty in level and trend, so it is on the narrow side.")
    item("Scenarios", "Each scenario sets a price change, a promotion discount and share of the year, a demand shock and a supplier delay. Volume moves by the demand shock and by (effective price factor) to the power of minus elasticity. Elasticity comes from past promotions (Promotions sheet) unless overridden. Those estimates are rough: promotions cluster in busy months, so seasonal lift is counted as price response and elasticity is overstated. Treat the price scenario as a direction, and override the elasticities on the Assumptions sheet if you have better numbers. Stock-out risk is the chance that stock on hand and on order does not cover normally distributed demand over the longer protection period.")
    item("Customers", "RFM scores use quintiles of days since last order, number of orders and net revenue, among consumers who bought. Business accounts are excluded. Cohorts are the month of the first order. Lifetime value = order value x orders per year x contribution margin x retention / (1 + discount rate - retention).")
    item("Promotions", "Baseline = average daily sales over up to 56 days before the promotion, leaving out other promotion days and the dip after big promotions. Lift = promotion units / (baseline per day x days) - 1. Break-even uplift = discount / (margin at list price - discount). Seasonality is not removed.")
    r += 1
    section("Main assumptions")
    item("Where they live", "The Assumptions sheet holds every threshold and rate. Scenario parameters sit on the Scenarios sheet and the sensitivity steps on the grid headers. All are blue-on-yellow cells.")
    item("Stock snapshot", "Stock on hand and on order are the values on the as-of date. Reorder rules use trailing 12-month demand, which understates the need before a peak.")
    item("Lost sales", "In this made-up data the lost units are known exactly. A real company would have to estimate them.")
    r += 1
    section("Data dictionary (workbook tables)")
    dd = [
        ("Data_Monthly", "month (first day), year, month_no, sku, category, region, channel; units, order_lines, list_value (units x list price), discount_value, net_revenue, cogs, shipping, payment_fee, platform_fee; returned_units, refund_amount, return_shipping, restock_cogs (cost of goods put back on the shelf). Returns are on the order month."),
        ("Data_Products", "sku, product_name, category, supplier, current list price and unit cost, lead time mean and SD, minimum order quantity, shelf life, launch and discontinued dates, stocking policy; on_hand_end and on_order_end on the as-of date; avg_on_hand_12m, lost_units_12m, stockout_days_12m."),
        ("Data_StockMonth", "month, sku, lost_units (demand the shelf could not serve) and stockout_days."),
        ("Data_Customers", "customer_id, customer_type (Consumer or Business), region, signup_date, first_order, last_order, orders, net_revenue, gross_profit and a 0 or 1 flag for being active in each year."),
        ("Data_Cohort", "cohort_month (month of first order), months_since (0, 1, 2 ...), active_customers (customers from that cohort who ordered in that month). Consumers only."),
        ("Data_Promo", "One row per promotion and category: dates, discount, units, list value, net revenue and cost during the promotion, and baseline units, net revenue and cost per day from the days before it."),
        ("Data_Control", "Totals from the CSV files for the Checks sheet."),
    ]
    for k, v in dd:
        item(k, v)
    item("Full dictionary", "The CSV files and every column are described in docs/data-dictionary.md in the project folder.")
    r += 1
    section("Change log")
    item("2.0", "New data set (three years, 42 SKUs, 6 categories, 5 regions, 4 channels, 4,000 customers) with promotions, returns, stock-outs and supplier delays. New workbook with selectors, contribution margin, a margin bridge, ABC-XYZ, reorder points, a tested forecast, scenarios, RFM and cohorts, promotion lift, returns and a Checks sheet. A Python version of the calculations backs it up. The PivotTable and Power Query sheets were added by hand afterwards.")
    item("Corrections to 1.0", "Version 1 worked out the ABC cumulative share in product-code order instead of revenue order, so some SKUs were in the wrong class. Its month labels disagreed with the order dates on some rows. Its dashboard text about margin pressure was typed in and the data did not support it: monthly gross margin moved less than half a point, and that drift came from the product mix. Its reorder rule could never fire because the reorder points sat below demand over the lead time. Its forecast included the month being forecast in its own average. CHANGELOG.md has the figures.")
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
