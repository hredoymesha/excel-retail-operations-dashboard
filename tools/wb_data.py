"""Data sheets, assumptions and the calculation sheets of the workbook."""
from __future__ import annotations

import datetime as dt

from xlsxwriter.utility import xl_col_to_name as cn

from analysis.common import CATEGORIES, CHANNELS
from wb_core import (DATE, DEC1, DEC2, EUR, EUR2, INT, MONTH, PCT, PCT0, Ctx, absrange, absref, write_table)

FILT = "m_region,reg_c,m_channel,ch_c,m_category,cat_c"
YEARSEL = 'm_year,">="&yr_lo,m_year,"<="&yr_hi'
NM = 36                      # months in the data
SM_C0 = 4                    # first month column (E) on Calc_SkuMonth
SOLD_R0, LOST_R0, DEM_R0 = 4, 50, 96
NSKU = 42
REGIONS = ["Helsinki", "Tampere", "Turku", "Oulu", "Kuopio"]


def sf(measure: str, *crit: str, filt: bool = True) -> str:
    parts = [f"m_{measure}", *crit]
    if filt:
        parts.append(FILT)
    return "SUMIFS(" + ",".join(parts) + ")"


def build_data_sheets(ctx: Ctx) -> None:
    d = ctx.data
    m = d["monthly"]
    ctx.nm = write_table(ctx, "Data_Monthly", m, "tblMonthly",
                         {"month": MONTH, "list_value": DEC2, "discount_value": DEC2, "net_revenue": DEC2, "cogs": DEC2,
                          "shipping": DEC2, "payment_fee": DEC2, "platform_fee": DEC2, "refund_amount": DEC2,
                          "return_shipping": DEC2, "restock_cogs": DEC2}, name_prefix="m_",
                         widths={"month": 11, "category": 17})
    p = d["products"].copy()
    ctx.np = write_table(ctx, "Data_Products", p, "tblProducts",
                         {"list_price_now": DEC2, "unit_cost_now": DEC2, "launch_date": DATE, "discontinued_date": DATE,
                          "avg_on_hand_12m": DEC2}, name_prefix="p_", widths={"product_name": 28, "supplier_name": 24, "category": 17})
    ctx.nsm = write_table(ctx, "Data_StockMonth", d["stock_month"], "tblStockMonth", {"month": MONTH}, name_prefix="sm_")
    ctx.ncu = write_table(ctx, "Data_Customers", d["customers"], "tblCustomers",
                          {"signup_date": DATE, "first_order": DATE, "last_order": DATE, "net_revenue": DEC2, "gross_profit": DEC2},
                          name_prefix="cu_")
    ctx.nco = write_table(ctx, "Data_Cohort", d["cohort"], "tblCohort", {"cohort_month": MONTH}, name_prefix="co_")
    ctx.npr = write_table(ctx, "Data_Promo", d["promo"], "tblPromo",
                          {"start_date": DATE, "end_date": DATE, "discount_pct": PCT0, "list_value": DEC2, "net_revenue": DEC2, "cogs": DEC2,
                           "baseline_units_pd": "0.0000", "baseline_net_pd": "0.0000", "baseline_cogs_pd": "0.0000"},
                          name_prefix="pr_", widths={"campaign": 24, "category": 17})
    ws = ctx.ws["Data_Control"]
    ctrl = d["control"]
    ws.write_row(0, 0, ["item", "csv_value"], ctx.head())
    for i, (item, v) in enumerate(ctrl.itertuples(index=False)):
        ws.write(i + 1, 0, item, ctx.cell())
        ws.write(i + 1, 1, v, ctx.cell(DEC2))
        ctx.refs[f"ct{i}"] = absref("Data_Control", i + 1, 1)
    ws.set_column(0, 0, 52)
    ws.set_column(1, 1, 16)
    ws.write(len(ctrl) + 2, 0, "Totals read from the CSV files when the workbook was built. The Checks sheet compares the workbook with them.",
             ctx.note())


ASSUMPTIONS = [
    # name, label, value, format, note
    ("as_of", "As-of date", dt.datetime(2025, 12, 31), DATE, "Last day in the data. Stock, customers and the forecast start from here."),
    ("svc_level", "Target service level", 0.95, PCT, "Probability of not running out during the protection period. Drives safety stock."),
    ("review_days", "Review period (days)", 7, INT, "Days between stock reviews. Added to the lead time."),
    ("order_cost", "Cost of placing one purchase order (EUR)", 25, EUR, "Used in the economic order quantity."),
    ("hold_rate", "Holding cost per year (share of unit cost)", 0.22, PCT, "Capital, storage and shrinkage. Used for EOQ and overstock cost."),
    ("days_year", "Days in a year", 365, INT, "Used to scale annual figures."),
    ("days_month", "Days in a month (for daily spread)", 30, INT, "Monthly standard deviation is divided by the square root of this to get a daily one."),
    ("months_year", "Months in a year", 12, INT, ""),
    ("dem_window", "Demand window for stock rules (months)", 12, INT, "Trailing months used for average demand, ABC revenue and turns."),
    ("cv_window", "Window for demand variability (months)", 24, INT, "Trailing months used for the coefficient of variation in XYZ."),
    ("lost_in_demand", "Count lost sales as demand (1 yes, 0 no)", 1, INT, "When 1, units customers wanted but could not buy are added to demand."),
    ("abc_a", "ABC: class A up to cumulative share", 0.80, PCT0, "A SKU is A if the share of revenue before it is below this."),
    ("abc_b", "ABC: class B up to cumulative share", 0.95, PCT0, "Same rule for B. The rest is C."),
    ("xyz_x", "XYZ: class X up to CV", 0.40, DEC2, "Coefficient of variation of monthly demand. Low means steady."),
    ("xyz_y", "XYZ: class Y up to CV", 0.70, DEC2, "Above this is Z (erratic)."),
    ("over_days", "Overstock when days of cover exceed", 120, INT, "Days of stock on hand at the recent demand rate."),
    ("risk_cut", "Stock-out risk flagged above", 0.25, PCT0, "Probability of running out before the next delivery in the scenario sheet."),
    ("holdout", "Forecast hold-out (months)", 3, INT, "Last months kept back to test each method. Between 1 and 6."),
    ("ma_months", "Moving average length (months)", 3, INT, "Used by the moving average benchmark."),
    ("band_conf", "Forecast band confidence", 0.90, PCT0, "Width of the band around the forecast."),
    ("min_ret_units", "Minimum units for the problem-SKU list", 100, INT, "Avoids ranking SKUs on a handful of sales."),
    ("min_rev_attn", "Minimum yearly revenue for the margin-drop list (EUR)", 5000, EUR, "SKUs below this in either year are left out."),
    ("rfm_bins", "RFM score bins", 5, INT, "Quintiles. Scores run from 1 to this number."),
    ("seg_hi", "RFM segments: high score at or above", 4, INT, ""),
    ("seg_mid", "RFM segments: medium score at or above", 3, INT, ""),
    ("seg_lo", "RFM segments: low score at or below", 2, INT, ""),
    ("disc_rate", "Customer value: yearly discount rate", 0.10, PCT0, "Used in the lifetime value estimate."),
    ("check_tol", "Tolerance for reconciliation checks (EUR or units)", 0.5, DEC2, "Rounding of cents across thousands of rows."),
    ("ratio_tol", "Tolerance for checks on shares", 0.0001, "0.0000", "Used where the check compares percentages."),
]


def build_assumptions(ctx: Ctx) -> None:
    ws = ctx.ws["Assumptions"]
    ctx.banner(ws, "Assumptions", 5, "Blue cells on yellow are inputs. Change them and every sheet updates. Nothing else in the workbook is typed in.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 50)
    ws.set_column(1, 1, 14)
    ws.set_column(2, 2, 90)
    ws.write_row(3, 0, ["Assumption", "Value", "What it does"], ctx.head())
    for i, (name, label, val, num, note) in enumerate(ASSUMPTIONS):
        r = 4 + i
        ws.write(r, 0, label, ctx.cell())
        if isinstance(val, dt.datetime):
            ws.write_datetime(r, 1, val, ctx.inp(num, align="right"))
        else:
            ws.write(r, 1, val, ctx.inp(num, align="right"))
        ws.write(r, 2, note, ctx.cell(text_wrap=True))
        ctx.name(name, absref("Assumptions", r, 1))
    r0 = 4 + len(ASSUMPTIONS) + 2
    ws.write(r0, 0, "Price elasticity override by category", ctx.h1())
    ws.write(r0 + 1, 0, "Leave blank to use the value implied by past promotions (Promotions sheet). Type a number to override it.", ctx.note())
    ws.write_row(r0 + 2, 0, ["Category", "Override"], ctx.head())
    for i, cat in enumerate(CATEGORIES):
        ws.write(r0 + 3 + i, 0, cat, ctx.cell())
        ws.write_blank(r0 + 3 + i, 1, None, ctx.inp(DEC2))
    ctx.name("el_override", absrange("Assumptions", r0 + 3, 1, r0 + 3 + len(CATEGORIES) - 1, 1))
    ws.data_validation(4 + [a[0] for a in ASSUMPTIONS].index("svc_level"), 1, 4 + [a[0] for a in ASSUMPTIONS].index("svc_level"), 1,
                       {"validate": "decimal", "criteria": "between", "minimum": 0.5, "maximum": 0.9999,
                        "error_title": "Service level", "error_message": "Enter a number between 0.5 and 0.9999."})
    for nm_, lo, hi in [("abc_a", 0.01, 0.99), ("abc_b", 0.01, 0.999), ("hold_rate", 0.0, 1.0), ("band_conf", 0.5, 0.999)]:
        rr = 4 + [a[0] for a in ASSUMPTIONS].index(nm_)
        ws.data_validation(rr, 1, rr, 1, {"validate": "decimal", "criteria": "between", "minimum": lo, "maximum": hi,
                                          "error_message": f"Enter a number between {lo} and {hi}."})
    for nm_, lo, hi in [("holdout", 1, 6), ("dem_window", 3, 24), ("cv_window", 6, 36), ("ma_months", 1, 6), ("rfm_bins", 3, 10)]:
        rr = 4 + [a[0] for a in ASSUMPTIONS].index(nm_)
        ws.data_validation(rr, 1, rr, 1, {"validate": "integer", "criteria": "between", "minimum": lo, "maximum": hi,
                                          "error_message": f"Enter a whole number from {lo} to {hi}."})
    ws.freeze_panes(4, 0)


def build_calc_dashboard(ctx: Ctx) -> None:
    ws = ctx.ws["Calc_Dashboard"]
    ctx.banner(ws, "Working sheet for the dashboard", 14, "Formulas only. Nothing here needs editing.")
    ws.set_column(0, 0, 34)
    ws.set_column(1, 14, 14)
    hdr = ctx.head()
    cell = ctx.cell()
    helpers = [
        ("yr_lo", "First year selected", '=IF(sel_year="All",MIN(m_year),--sel_year)', "0"),
        ("yr_hi", "Last year selected", '=IF(sel_year="All",MAX(m_year),--sel_year)', "0"),
        ("reg_c", "Region criterion", '=IF(sel_region="All","*",sel_region)', None),
        ("ch_c", "Channel criterion", '=IF(sel_channel="All","*",sel_channel)', None),
        ("cat_c", "Category criterion", '=IF(sel_category="All","*",sel_category)', None),
        ("ref_year", "Reference year for trend and bridge", "=yr_hi", "0"),
        ("ref_month", "Latest month in the selection", '=IF(sel_year="All",MAX(m_month),DATE(yr_hi,months_year,1))', MONTH),
        ("prev_month", "Month before that", "=EDATE(ref_month,-1)", MONTH),
        ("win_start", "Start of the trailing window", "=EDATE(as_of+1,-dem_window)", DATE),
        ("win_days", "Days in the trailing window", "=as_of-win_start+1", "0"),
        ("n_months", "Months of data", f"=COUNT(Calc_SkuMonth!$E$4:${cn(SM_C0 + NM - 1)}$4)", "0"),
        ("first_month", "First month of data", "=MIN(m_month)", MONTH),
        ("has_prior", "Prior year available (1 yes)", '=IF(sel_year="All",0,IF(yr_lo-1<MIN(m_year),0,1))', "0"),
    ]
    ws.write_row(2, 0, ["Helper", "Value"], hdr)
    for i, (nm_, label, f, num) in enumerate(helpers):
        r = 3 + i
        ws.write(r, 0, label, cell)
        ws.write_formula(r, 1, f, ctx.cell(num) if num else cell)
        ctx.name(nm_, absref("Calc_Dashboard", r, 1))

    # KPI block
    r0 = 18
    ws.write(r0, 0, "KPI inputs", ctx.h1())
    ws.write_row(r0 + 1, 0, ["Measure", "Selected period", "Same period a year earlier", "Latest month", "Month before"], hdr)
    measures = [("units", INT), ("order_lines", INT), ("list_value", EUR), ("discount_value", EUR), ("net_revenue", EUR),
                ("cogs", EUR), ("shipping", EUR), ("payment_fee", EUR), ("platform_fee", EUR), ("refund_amount", EUR),
                ("return_shipping", EUR), ("restock_cogs", EUR)]
    mrow = {}
    for i, (ms, num) in enumerate(measures):
        r = r0 + 2 + i
        mrow[ms] = r
        ws.write(r, 0, ms.replace("_", " "), cell)
        ws.write_formula(r, 1, "=" + sf(ms, YEARSEL), ctx.cell(num))
        ws.write_formula(r, 2, "=has_prior*" + sf(ms, 'm_year,">="&yr_lo-1,m_year,"<="&yr_hi-1'), ctx.cell(num))
        ws.write_formula(r, 3, "=" + sf(ms, "m_month,ref_month"), ctx.cell(num))
        ws.write_formula(r, 4, "=" + sf(ms, "m_month,prev_month"), ctx.cell(num))
    rd = r0 + 2 + len(measures)
    derived = [("gross_profit", "Gross profit", lambda c: f"={c}{mrow['net_revenue']+1}-{c}{mrow['cogs']+1}", EUR),
               ("contribution", "Contribution margin",
                lambda c: (f"={c}{mrow['net_revenue']+1}-{c}{mrow['cogs']+1}-{c}{mrow['shipping']+1}-{c}{mrow['payment_fee']+1}"
                           f"-{c}{mrow['platform_fee']+1}-{c}{mrow['refund_amount']+1}+{c}{mrow['restock_cogs']+1}-{c}{mrow['return_shipping']+1}"), EUR),
               ("gm_pct", "Gross margin %", lambda c: f"=IFERROR({c}{rd+1}/{c}{mrow['net_revenue']+1},0)", PCT),
               ("cm_pct", "Contribution margin %", lambda c: f"=IFERROR({c}{rd+2}/{c}{mrow['net_revenue']+1},0)", PCT),
               ("disc_pct", "Average discount %", lambda c: f"=IFERROR({c}{mrow['discount_value']+1}/{c}{mrow['list_value']+1},0)", PCT)]
    for i, (key, label, fn, num) in enumerate(derived):
        r = rd + i
        mrow[key] = r
        ws.write(r, 0, label, cell)
        for j, col in enumerate("BCDE"):
            ws.write_formula(r, 1 + j, fn(col), ctx.cell(num))
    ctx.kpi_rows = mrow

    # trend block
    t0 = rd + len(derived) + 2
    ws.write(t0, 0, "Monthly trend for the reference year", ctx.h1())
    ws.write_row(t0 + 1, 0, ["Month", "Revenue, reference year", "Revenue, year before", "Gross margin %, reference year"], hdr)
    for k in range(12):
        r = t0 + 2 + k
        ws.write(r, 0, ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][k], cell)
        ws.write_formula(r, 1, "=" + sf("net_revenue", f"m_year,ref_year,m_month_no,{k+1}"), ctx.cell(EUR))
        ws.write_formula(r, 2, "=" + sf("net_revenue", f"m_year,ref_year-1,m_month_no,{k+1}"), ctx.cell(EUR))
        ws.write_formula(r, 3, f"=IFERROR(1-{sf('cogs', f'm_year,ref_year,m_month_no,{k+1}')}/B{r+1},NA())", ctx.cell(PCT))
    ctx.trend_rows = (t0 + 2, t0 + 13)

    # category and channel blocks
    c0 = t0 + 16
    ws.write(c0, 0, "Gross margin by category and channel (selected period)", ctx.h1())
    ws.write_row(c0 + 1, 0, ["Group", "Revenue", "Cost of goods", "Gross margin %"], hdr)
    for i, cat in enumerate(CATEGORIES):
        r = c0 + 2 + i
        ws.write(r, 0, cat, cell)
        ws.write_formula(r, 1, "=SUMIFS(m_net_revenue," + YEARSEL + f",m_region,reg_c,m_channel,ch_c,m_category,$A{r+1},m_category,cat_c)", ctx.cell(EUR))
        ws.write_formula(r, 2, "=SUMIFS(m_cogs," + YEARSEL + f",m_region,reg_c,m_channel,ch_c,m_category,$A{r+1},m_category,cat_c)", ctx.cell(EUR))
        ws.write_formula(r, 3, f"=IF(B{r+1}=0,0,1-C{r+1}/B{r+1})", ctx.cell(PCT))
    ctx.cat_rows = (c0 + 2, c0 + 1 + len(CATEGORIES))
    ch0 = c0 + 2 + len(CATEGORIES)
    for i, ch in enumerate(CHANNELS):
        r = ch0 + i
        ws.write(r, 0, ch, cell)
        ws.write_formula(r, 1, "=SUMIFS(m_net_revenue," + YEARSEL + f",m_region,reg_c,m_channel,$A{r+1},m_channel,ch_c,m_category,cat_c)", ctx.cell(EUR))
        ws.write_formula(r, 2, "=SUMIFS(m_cogs," + YEARSEL + f",m_region,reg_c,m_channel,$A{r+1},m_channel,ch_c,m_category,cat_c)", ctx.cell(EUR))
        ws.write_formula(r, 3, f"=IF(B{r+1}=0,0,1-C{r+1}/B{r+1})", ctx.cell(PCT))
    ctx.chan_rows = (ch0, ch0 + len(CHANNELS) - 1)

    # SKU block
    s0 = ch0 + len(CHANNELS) + 2
    ws.write(s0, 0, "SKU measures under the selection", ctx.h1())
    heads = ["SKU", "Product", "Revenue (period)", "Gross profit (period)", "Rank high to low", "Rank low to high (sold only)",
             "Revenue, reference year", "Revenue, year before", "Cost, reference year", "Cost, year before",
             "Margin, reference year", "Margin, year before", "Margin change (pp)", "Eligible for margin list", "Rank of margin drop"]
    ws.write_row(s0 + 1, 0, heads, hdr)
    ws.set_row(s0 + 1, 42)
    first, last = s0 + 2, s0 + 1 + NSKU
    for i in range(NSKU):
        r = s0 + 2 + i
        x = r + 1
        ws.write_formula(r, 0, f"=Data_Products!$A${i+2}", cell)
        ws.write_formula(r, 1, f"=Data_Products!$B${i+2}", cell)
        ws.write_formula(r, 2, "=" + sf("net_revenue", YEARSEL, f"m_sku,$A{x}"), ctx.cell(EUR))
        ws.write_formula(r, 3, f"=C{x}-" + sf("cogs", YEARSEL, f"m_sku,$A{x}"), ctx.cell(EUR))
        ws.write_formula(r, 4, f"=RANK(C{x},$C${first+1}:$C${last+1},0)+COUNTIF($C${first+1}:C{x},C{x})-1", ctx.cell("0"))
        ws.write_formula(r, 5, f'=IF(C{x}>0,COUNTIFS($C${first+1}:$C${last+1},">0",$C${first+1}:$C${last+1},"<"&C{x})+COUNTIFS($C${first+1}:C{x},C{x}),"")', ctx.cell("0"))
        ws.write_formula(r, 6, "=" + sf("net_revenue", "m_year,ref_year", f"m_sku,$A{x}"), ctx.cell(EUR))
        ws.write_formula(r, 7, "=" + sf("net_revenue", "m_year,ref_year-1", f"m_sku,$A{x}"), ctx.cell(EUR))
        ws.write_formula(r, 8, "=" + sf("cogs", "m_year,ref_year", f"m_sku,$A{x}"), ctx.cell(EUR))
        ws.write_formula(r, 9, "=" + sf("cogs", "m_year,ref_year-1", f"m_sku,$A{x}"), ctx.cell(EUR))
        ws.write_formula(r, 10, f"=IF(G{x}=0,0,1-I{x}/G{x})", ctx.cell(PCT))
        ws.write_formula(r, 11, f"=IF(H{x}=0,0,1-J{x}/H{x})", ctx.cell(PCT))
        ws.write_formula(r, 12, f"=K{x}-L{x}", ctx.cell(PCT))
        ws.write_formula(r, 13, f"=IF(AND(G{x}>=min_rev_attn,H{x}>=min_rev_attn),1,0)", ctx.cell("0"))
        ws.write_formula(r, 14, f'=IF(N{x}=1,COUNTIFS($N${first+1}:$N${last+1},1,$M${first+1}:$M${last+1},"<"&M{x})+COUNTIFS($N${first+1}:N{x},1,$M${first+1}:M{x},M{x}),"")', ctx.cell("0"))
    ctx.sku_rows = (first, last)
    ws.freeze_panes(3, 1)


def build_calc_skumonth(ctx: Ctx) -> None:
    ws = ctx.ws["Calc_SkuMonth"]
    ctx.banner(ws, "Monthly units by SKU", SM_C0 + NM, "Sold units, lost units and demand (sold plus lost when the assumption says so).")
    ws.set_column(0, 0, 10)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 2, 17)
    ws.set_column(3, 3, 3)
    ws.set_column(SM_C0, SM_C0 + NM - 1, 9)
    hdr = ctx.head(num_format=MONTH)
    cell = ctx.cell(INT)
    blocks = [("Units sold", SOLD_R0, lambda x, col: f"=SUMIFS(m_units,m_sku,$A{x},m_month,{col}$4)"),
              ("Units lost to stock-outs", LOST_R0, lambda x, col: f"=SUMIFS(sm_lost_units,sm_sku,$A{x},sm_month,{col}$4)"),
              ("Demand", DEM_R0, None)]
    for title, r0, fn in blocks:
        ws.write(r0 - 2 if title != "Units sold" else 2, 0, title, ctx.h1())
        if title == "Units sold":
            ws.write_row(3, 0, ["SKU", "Product", "Category"], ctx.head())
            for k in range(NM):
                col = cn(SM_C0 + k)
                if k == 0:
                    ws.write_formula(3, SM_C0, "=first_month", hdr)
                else:
                    ws.write_formula(3, SM_C0 + k, f"=EDATE({cn(SM_C0 + k - 1)}4,1)", hdr)
        else:
            ws.write_row(r0 - 1, 0, ["SKU", "Product", "Category"], ctx.head())
            for k in range(NM):
                ws.write_formula(r0 - 1, SM_C0 + k, f"={cn(SM_C0 + k)}$4", hdr)
        for i in range(NSKU):
            r = r0 + i
            x = r + 1
            ws.write_formula(r, 0, f"=Data_Products!$A${i+2}", ctx.cell())
            ws.write_formula(r, 1, f"=Data_Products!$B${i+2}", ctx.cell())
            ws.write_formula(r, 2, f"=Data_Products!$C${i+2}", ctx.cell())
            for k in range(NM):
                col = cn(SM_C0 + k)
                if fn:
                    ws.write_formula(r, SM_C0 + k, fn(x, col) if title == "Units sold" else
                                     f"=SUMIFS(sm_lost_units,sm_sku,$A{x},sm_month,{col}${r0})", cell)
                else:
                    ws.write_formula(r, SM_C0 + k, f"={col}{SOLD_R0 + i + 1}+lost_in_demand*{col}{LOST_R0 + i + 1}", cell)
    ws.freeze_panes(4, 3)


def build_calc_sku(ctx: Ctx) -> None:
    ws = ctx.ws["Calc_Sku"]
    ctx.banner(ws, "Working sheet: SKU measures", 24, "Trailing-window revenue, ABC and XYZ classes, and demand statistics. Formulas only.")
    heads = ["SKU", "Product", "Category", "Revenue (window)", "Cost of goods (window)", "Units sold (window)",
             "Returned units (window)", "Gross profit (window)", "Revenue rank", "CV of monthly demand", "Mean monthly demand (window)",
             "SD monthly demand (window)", "Demand in window", "ABC class", "XYZ class", "ABC-XYZ", "Average net price",
             "Gross margin %", "Return rate", "Demand per day", "Share before this SKU", "Lost units (window)"]
    ws.write_row(3, 0, heads, ctx.head())
    ws.set_row(3, 42)
    ws.set_column(0, 0, 10)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 2, 17)
    ws.set_column(3, 21, 13)
    ctx.csku0 = 4
    last = 4 + NSKU
    wmin, wmax = 'm_month,">="&win_start', 'm_month,"<="&as_of'
    for i in range(NSKU):
        r = 4 + i
        x = r + 1
        dem = f"Calc_SkuMonth!$E{DEM_R0 + i + 1}:${cn(SM_C0 + NM - 1)}{DEM_R0 + i + 1}"
        cvr = f"INDEX({dem},n_months-cv_window+1):INDEX({dem},n_months)"
        wnd = f"INDEX({dem},n_months-dem_window+1):INDEX({dem},n_months)"
        lost = f"Calc_SkuMonth!$E{LOST_R0 + i + 1}:${cn(SM_C0 + NM - 1)}{LOST_R0 + i + 1}"
        ws.write_formula(r, 0, f"=Data_Products!$A${i+2}", ctx.cell())
        ws.write_formula(r, 1, f"=Data_Products!$B${i+2}", ctx.cell())
        ws.write_formula(r, 2, f"=Data_Products!$C${i+2}", ctx.cell())
        ws.write_formula(r, 3, f"=SUMIFS(m_net_revenue,m_sku,$A{x},{wmin},{wmax})", ctx.cell(EUR))
        ws.write_formula(r, 4, f"=SUMIFS(m_cogs,m_sku,$A{x},{wmin},{wmax})", ctx.cell(EUR))
        ws.write_formula(r, 5, f"=SUMIFS(m_units,m_sku,$A{x},{wmin},{wmax})", ctx.cell(INT))
        ws.write_formula(r, 6, f"=SUMIFS(m_returned_units,m_sku,$A{x},{wmin},{wmax})", ctx.cell(INT))
        ws.write_formula(r, 7, f"=D{x}-E{x}", ctx.cell(EUR))
        ws.write_formula(r, 8, f"=RANK(D{x},$D$5:$D${last},0)+COUNTIF($D$5:D{x},D{x})-1", ctx.cell("0"))
        ws.write_formula(r, 9, f"=IFERROR(STDEV.S({cvr})/AVERAGE({cvr}),0)", ctx.cell(DEC2))
        ws.write_formula(r, 10, f"=AVERAGE({wnd})", ctx.cell(DEC1))
        ws.write_formula(r, 11, f"=STDEV.S({wnd})", ctx.cell(DEC1))
        ws.write_formula(r, 12, f"=SUM({wnd})", ctx.cell(INT))
        ws.write_formula(r, 20, f"=SUMIFS($D$5:$D${last},$I$5:$I${last},\"<\"&I{x})/SUM($D$5:$D${last})", ctx.cell(PCT))
        ws.write_formula(r, 13, f'=IF(U{x}<abc_a,"A",IF(U{x}<abc_b,"B","C"))', ctx.cell(align="center"))
        ws.write_formula(r, 14, f'=IF(J{x}<=xyz_x,"X",IF(J{x}<=xyz_y,"Y","Z"))', ctx.cell(align="center"))
        ws.write_formula(r, 15, f"=N{x}&O{x}", ctx.cell(align="center"))
        ws.write_formula(r, 16, f"=IFERROR(D{x}/F{x},0)", ctx.cell(EUR2))
        ws.write_formula(r, 17, f"=IFERROR(H{x}/D{x},0)", ctx.cell(PCT))
        ws.write_formula(r, 18, f"=IFERROR(G{x}/F{x},0)", ctx.cell(PCT))
        ws.write_formula(r, 19, f"=M{x}/win_days", ctx.cell(DEC2))
        ws.write_formula(r, 21, f"=SUM(INDEX({lost},n_months-dem_window+1):INDEX({lost},n_months))", ctx.cell(INT))
    ws.freeze_panes(4, 2)
