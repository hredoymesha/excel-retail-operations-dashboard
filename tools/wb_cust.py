"""Customers, promotions and returns sheets."""
from __future__ import annotations

from xlsxwriter.utility import xl_col_to_name as cn

from analysis.common import CATEGORIES
from wb_core import DATE, DEC1, DEC2, EUR, INT, MONTH, PAL, PCT, PCT0, Ctx, absrange, absref
from wb_data import NSKU, REGIONS

SEGMENTS = ["Champions", "Loyal", "New or recent", "At risk", "Lost or hibernating", "Needs attention"]


def build_calc_customers(ctx: Ctx, n: int) -> None:
    ws = ctx.ws["Calc_Customers"]
    ctx.banner(ws, "Working sheet: RFM scores", 10, "One row per customer, in the same order as Data_Customers. Formulas only.")
    ws.write_row(3, 0, ["Customer", "Scored (1 yes)", "Days since last order", "Orders", "Net revenue", "R score", "F score", "M score", "Segment", "RFM code"], ctx.head())
    ws.set_row(3, 32)
    ws.set_column(0, 9, 14)
    ws.set_column(8, 8, 22)
    for i in range(n):
        r = 4 + i
        x = r + 1
        d = i + 2
        ws.write_formula(r, 0, f"=Data_Customers!$A${d}")
        ws.write_formula(r, 1, f'=IF(AND(Data_Customers!$B${d}="Consumer",Data_Customers!$G${d}>0),1,0)')
        ws.write_formula(r, 2, f'=IF(B{x}=1,as_of-Data_Customers!$F${d},"")')
        ws.write_formula(r, 3, f'=IF(B{x}=1,Data_Customers!$G${d},"")')
        ws.write_formula(r, 4, f'=IF(B{x}=1,Data_Customers!$H${d},"")')
        ws.write_formula(r, 5, f'=IF(B{x}=1,rfm_bins-COUNTIF(rfm_cut_r,"<"&C{x}),"")')
        ws.write_formula(r, 6, f'=IF(B{x}=1,1+COUNTIF(rfm_cut_f,"<"&D{x}),"")')
        ws.write_formula(r, 7, f'=IF(B{x}=1,1+COUNTIF(rfm_cut_m,"<"&E{x}),"")')
        ws.write_formula(r, 8, (f'=IF(B{x}=0,"Not scored",IF(AND(F{x}>=seg_hi,G{x}>=seg_hi),"Champions",IF(AND(F{x}>=seg_mid,G{x}>=seg_mid),"Loyal",'
                                f'IF(AND(F{x}>=seg_hi,G{x}<=seg_lo),"New or recent",IF(AND(F{x}<=seg_lo,G{x}>=seg_mid),"At risk",'
                                f'IF(AND(F{x}<=seg_lo,G{x}<=seg_lo),"Lost or hibernating","Needs attention"))))))'))
        ws.write_formula(r, 9, f'=IF(B{x}=1,F{x}&G{x}&H{x},"")')
    ws.freeze_panes(4, 1)
    ctx.cc = (5, 4 + n)         # excel rows of the first and last customer on Calc_Customers


def build_customers(ctx: Ctx) -> None:
    n = len(ctx.data["customers"])
    build_calc_customers(ctx, n)
    ws = ctx.ws["Customers"]
    ctx.banner(ws, "Customers", 14, "RFM scores and segments, repeat purchase, monthly cohort retention and a simple lifetime value. Business accounts are left out of RFM.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 26)
    ws.set_column(1, 8, 13)
    ws.set_column(9, 14, 13)
    ws.set_column(15, 30, 7.5)
    hdr = ctx.head()
    cell = ctx.cell()
    cc1, cc2 = ctx.cc
    cr = lambda col: f"Calc_Customers!${col}${cc1}:${col}${cc2}"
    dr = lambda col: f"Data_Customers!${col}$2:${col}${n+1}"

    # RFM cutoffs
    K0 = 4
    ws.write(K0, 9, "Score cut-offs (percentiles of scored customers)", ctx.h1())
    ws.write_row(K0 + 1, 9, ["Step", "Recency (days)", "Orders", "Net revenue"], hdr)
    for j in range(9):
        r = K0 + 2 + j
        ws.write(r, 9, j + 1, ctx.cell("0", align="center"))
        for k, col in enumerate("CDE"):
            ws.write_formula(r, 10 + k, f'=IF($J{r+1}<rfm_bins,PERCENTILE.INC({cr(col)},$J{r+1}/rfm_bins),"")', ctx.cell(DEC1))
    ctx.name("rfm_cut_r", absrange("Customers", K0 + 2, 10, K0 + 10, 10))
    ctx.name("rfm_cut_f", absrange("Customers", K0 + 2, 11, K0 + 10, 11))
    ctx.name("rfm_cut_m", absrange("Customers", K0 + 2, 12, K0 + 10, 12))

    # segments
    S0 = 4
    ws.write(S0, 0, "RFM segments", ctx.h1())
    ws.write_row(S0 + 1, 0, ["Segment", "Customers", "Share of customers", "Revenue", "Share of revenue", "Orders per customer", "Days since last order"], hdr)
    ws.set_row(S0 + 1, 32)
    sg = cr("I")
    for i, seg in enumerate(SEGMENTS):
        r = S0 + 2 + i
        x = r + 1
        ws.write(r, 0, seg, cell)
        ws.write_formula(r, 1, f"=COUNTIF({sg},$A{x})", ctx.cell(INT))
        ws.write_formula(r, 2, f"=IFERROR(B{x}/B${S0+2+len(SEGMENTS)+1},0)", ctx.cell(PCT))
        ws.write_formula(r, 3, f"=SUMIF({sg},$A{x},{dr('H')})", ctx.cell(EUR))
        ws.write_formula(r, 4, f"=IFERROR(D{x}/D${S0+2+len(SEGMENTS)+1},0)", ctx.cell(PCT))
        ws.write_formula(r, 5, f"=IFERROR(SUMIF({sg},$A{x},{dr('G')})/B{x},0)", ctx.cell(DEC1))
        ws.write_formula(r, 6, f"=IFERROR(AVERAGEIF({sg},$A{x},{cr('C')}),0)", ctx.cell(INT))
    rt = S0 + 2 + len(SEGMENTS)
    ws.write(rt, 0, "All scored customers", ctx.cell(bold=True))
    ws.write_formula(rt, 1, f"=SUM(B{S0+3}:B{rt})", ctx.cell(INT, bold=True))
    ws.write_formula(rt, 2, f"=SUM(C{S0+3}:C{rt})", ctx.cell(PCT, bold=True))
    ws.write_formula(rt, 3, f"=SUM(D{S0+3}:D{rt})", ctx.cell(EUR, bold=True))
    ws.write_formula(rt, 4, f"=SUM(E{S0+3}:E{rt})", ctx.cell(PCT, bold=True))
    ctx.refs["rfm_total"] = absref("Customers", rt, 1)
    ws.write(rt + 1, 0, "Champions: recent and frequent. Loyal: good on both. New or recent: recent, few orders. At risk: quiet for a while but used to order often. Lost or hibernating: quiet and rare.", ctx.note())
    ws.set_row(rt + 1, 42)

    # repeat purchase
    P0 = rt + 4
    ws.write(P0 - 1, 0, "Repeat purchase, consumers", ctx.h1())
    ws.write_row(P0, 0, ["Region", "Bought at least once", "Bought twice or more", "Repeat rate"], hdr)
    ws.set_row(P0, 32)
    for i, reg in enumerate(REGIONS + ["All regions"]):
        r = P0 + 1 + i
        x = r + 1
        allr = reg == "All regions"
        crit = '' if allr else f',cu_region,$A{x}'
        ws.write(r, 0, reg, ctx.cell(bold=allr))
        ws.write_formula(r, 1, f'=COUNTIFS(cu_customer_type,"Consumer",cu_orders,">0"{crit})', ctx.cell(INT, bold=allr))
        ws.write_formula(r, 2, f'=COUNTIFS(cu_customer_type,"Consumer",cu_orders,">=2"{crit})', ctx.cell(INT, bold=allr))
        ws.write_formula(r, 3, f"=IFERROR(C{x}/B{x},0)", ctx.cell(PCT, bold=allr))
    ctx.refs["repeat_rate"] = absref("Customers", P0 + 6, 3)
    ctx.refs["consumers_bought"] = absref("Customers", P0 + 6, 1)

    # CLV
    V0 = P0 + 10
    ws.write(V0 - 1, 0, "Customer lifetime value, simple estimate", ctx.h1())
    ws.write_row(V0, 0, ["Item", "Value", "How it is worked out"], hdr)
    ws.merge_range(V0, 2, V0, 8, "How it is worked out", hdr)
    nonw = lambda m_: f'SUMIFS(m_{m_},m_channel,"<>Wholesale")'
    cm = (f"=({nonw('net_revenue')}-{nonw('cogs')}-{nonw('shipping')}-{nonw('payment_fee')}-{nonw('platform_fee')}"
          f"-{nonw('refund_amount')}+{nonw('restock_cogs')}-{nonw('return_shipping')})/{nonw('net_revenue')}")
    items = [
        ("Consumers who bought", '=COUNTIFS(cu_customer_type,"Consumer",cu_orders,">0")', INT, "Customers with at least one order."),
        ("Average order value", '=SUMIFS(cu_net_revenue,cu_customer_type,"Consumer")/SUMIFS(cu_orders,cu_customer_type,"Consumer")', EUR, "Net revenue divided by orders."),
        ("Orders per active customer-year", '=SUMIFS(cu_orders,cu_customer_type,"Consumer")/(SUMIFS(cu_active_2023,cu_customer_type,"Consumer")+SUMIFS(cu_active_2024,cu_customer_type,"Consumer")+SUMIFS(cu_active_2025,cu_customer_type,"Consumer"))', DEC2, "Orders divided by the number of years each customer ordered in."),
        ("Contribution margin on consumer channels", cm, PCT, "After shipping, payment and platform fees and returns. Wholesale left out."),
        ("Yearly retention", '=COUNTIFS(cu_customer_type,"Consumer",cu_active_2024,1,cu_active_2025,1)/COUNTIFS(cu_customer_type,"Consumer",cu_active_2024,1)', PCT, "Share of customers active in 2024 who ordered again in 2025."),
        ("Yearly discount rate", "=disc_rate", PCT, "From the Assumptions sheet."),
        ("Expected customer lifetime (years)", None, DEC1, "One divided by (1 - retention)."),
        ("Lifetime value (contribution)", None, EUR, "Order value x orders a year x margin x retention / (1 + discount rate - retention)."),
    ]
    for i, (lab, f, num, how) in enumerate(items):
        r = V0 + 1 + i
        x = r + 1
        ws.write(r, 0, lab, cell)
        if lab.startswith("Expected"):
            f = f"=1/(1-B{x-2})"
        elif lab.startswith("Lifetime"):
            f = f"=B{V0+3}*B{V0+4}*B{V0+5}*B{V0+6}/(1+B{V0+7}-B{V0+6})"
        ws.write_formula(r, 1, f, ctx.cell(num, bold=lab.startswith("Lifetime")))
        ws.merge_range(r, 2, r, 8, how, cell)
    ctx.refs["clv"] = absref("Customers", V0 + 8, 1)

    # cohort heat map
    H0 = V0 + 14
    NMON = 25
    ws.write(H0 - 2, 0, "Monthly cohort retention: share of each first-order cohort that ordered again N months later", ctx.h1())
    ws.write(H0 - 1, 0, "The January 2023 cohort includes everyone whose first order inside the data falls in that month, including customers who joined before 2023.", ctx.note())
    ws.write_row(H0, 0, ["Cohort (first order month)", "Customers"], hdr)
    for j in range(NMON):
        ws.write(H0, 2 + j, j, hdr)
    ws.set_row(H0, 24)
    for k in range(36):
        r = H0 + 1 + k
        x = r + 1
        ws.write_formula(r, 0, "=first_month" if k == 0 else f"=EDATE(A{x-1},1)", ctx.cell(MONTH, align="left"))
        ws.write_formula(r, 1, f"=SUMIFS(co_active_customers,co_cohort_month,$A{x},co_months_since,0)", ctx.cell(INT))
        for j in range(NMON):
            col = cn(2 + j)
            ws.write_formula(r, 2 + j, f'=IF(OR($B{x}=0,EDATE($A{x},{col}${H0+1})>as_of),"",SUMIFS(co_active_customers,co_cohort_month,$A{x},co_months_since,{col}${H0+1})/$B{x})', ctx.cell(PCT0, align="center", font_size=8))
    r = H0 + 37
    ws.write(r, 0, "All cohorts, weighted", ctx.cell(bold=True))
    ws.write_formula(r, 1, f"=SUM(B{H0+2}:B{H0+37})", ctx.cell(INT, bold=True))
    for j in range(NMON):
        col = cn(2 + j)
        ws.write_formula(r, 2 + j, f'=IFERROR(SUMIFS(co_active_customers,co_months_since,{col}${H0+1})/SUMPRODUCT(--({col}{H0+2}:{col}{H0+37}<>""),$B${H0+2}:$B${H0+37}),"")', ctx.cell(PCT0, align="center", font_size=8, bold=True))
    ws.conditional_format(H0 + 1, 3, H0 + 36, 1 + NMON, {"type": "2_color_scale", "min_color": "#FFFFFF", "max_color": "#2A7F8E", "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 0.5})
    ctx.refs["cohort_size_sum"] = absref("Customers", r, 1)
    ctx.cust = dict(S0=S0, P0=P0, V0=V0, H0=H0, K0=K0)

    ch = ctx.wb.add_chart({"type": "bar"})
    ch.add_series({"name": "Share of revenue", "categories": f"=Customers!$A${S0+3}:$A${S0+2+len(SEGMENTS)}", "values": f"=Customers!$E${S0+3}:$E${S0+2+len(SEGMENTS)}",
                   "fill": {"color": PAL["navy"]}, "data_labels": {"value": True, "num_format": "0%", "font": {"size": 9}}})
    ch.set_title({"name": "Share of revenue by RFM segment", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_legend({"none": True})
    ch.set_y_axis({"reverse": True})
    ch.set_x_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 470, "height": 270})
    ws.insert_chart(P0 - 1, 9, ch, {"x_offset": 10})
    ws.freeze_panes(3, 1)


def build_promotions(ctx: Ctx) -> None:
    ws = ctx.ws["Promotions"]
    ctx.banner(ws, "Promotions", 21, "Sales lift against a baseline, margin dilution and the uplift each promotion needed to break even.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 24)
    ws.set_column(1, 1, 24)
    ws.set_column(2, 2, 17)
    ws.set_column(3, 20, 12)
    hdr = ctx.head()
    cell = ctx.cell()
    n = len(ctx.data["promo"])
    camps = list(dict.fromkeys(ctx.data["promo"].campaign))
    # main table
    M0 = 34
    f, l = M0 + 2, M0 + 1 + n
    heads = ["Promotion", "Campaign", "Category", "Channels", "Start", "End", "Days", "Discount", "Units sold", "Baseline units", "Lift", "Extra units",
             "Gross margin in promotion", "Gross margin in baseline", "Margin dilution (pts)", "Margin at list price", "Break-even uplift",
             "Lift minus break-even", "Extra gross profit", "Verdict", "Implied elasticity"]
    ws.write(M0 - 1, 0, "Every promotion", ctx.h1())
    ws.write_row(M0, 0, heads, hdr)
    ws.set_row(M0, 44)
    for i in range(n):
        r = M0 + 1 + i
        x = r + 1
        d = i + 2
        dp = lambda c: f"Data_Promo!${c}${d}"
        ws.write_formula(r, 0, f"={dp('A')}", cell)
        ws.write_formula(r, 1, f"={dp('B')}", cell)
        ws.write_formula(r, 2, f"={dp('C')}", cell)
        ws.write_formula(r, 3, f"={dp('D')}", cell)
        ws.write_formula(r, 4, f"={dp('E')}", ctx.cell(DATE))
        ws.write_formula(r, 5, f"={dp('F')}", ctx.cell(DATE))
        ws.write_formula(r, 6, f"={dp('G')}", ctx.cell(INT))
        ws.write_formula(r, 7, f"={dp('H')}", ctx.cell(PCT0))
        ws.write_formula(r, 8, f"={dp('I')}", ctx.cell(INT))
        ws.write_formula(r, 9, f'=IF(ISNUMBER({dp("N")}),{dp("N")}*G{x},"")', ctx.cell(DEC1))
        ws.write_formula(r, 10, f'=IF(J{x}="","",I{x}/J{x}-1)', ctx.cell(PCT0))
        ws.write_formula(r, 11, f'=IF(J{x}="","",I{x}-J{x})', ctx.cell(DEC1))
        ws.write_formula(r, 12, f'=IFERROR(({dp("K")}-{dp("L")})/{dp("K")},"")', ctx.cell(PCT))
        ws.write_formula(r, 13, f'=IF(ISNUMBER({dp("O")}),IFERROR(({dp("O")}-{dp("P")})/{dp("O")},""),"")', ctx.cell(PCT))
        ws.write_formula(r, 14, f'=IF(OR(M{x}="",N{x}=""),"",N{x}-M{x})', ctx.cell(PCT))
        ws.write_formula(r, 15, f'=IFERROR(({dp("J")}-{dp("L")})/{dp("J")},"")', ctx.cell(PCT))
        ws.write_formula(r, 16, f'=IF(P{x}="","",IF(P{x}>H{x},H{x}/(P{x}-H{x}),"never"))', ctx.cell(PCT0))
        ws.write_formula(r, 17, f'=IF(OR(K{x}="",NOT(ISNUMBER(Q{x}))),"",K{x}-Q{x})', ctx.cell(PCT0))
        ws.write_formula(r, 18, f'=IF(J{x}="","",({dp("K")}-{dp("L")})-({dp("O")}-{dp("P")})*G{x})', ctx.cell(EUR))
        ws.write_formula(r, 19, f'=IF(S{x}="","No baseline",IF(S{x}>=0,"Adds profit","Loses profit"))', cell)
        ws.write_formula(r, 20, f'=IF(K{x}="","",IFERROR(LN(1+K{x})/-LN(1-H{x}),""))', ctx.cell(DEC2))
    ws.conditional_format(M0 + 1, 19, M0 + n, 19, {"type": "text", "criteria": "containing", "value": "Loses", "format": ctx.fmt(bg_color=PAL["fail_fill"], font_color=PAL["fail_font"])})
    ws.conditional_format(M0 + 1, 19, M0 + n, 19, {"type": "text", "criteria": "containing", "value": "Adds", "format": ctx.fmt(bg_color=PAL["pass_fill"], font_color=PAL["pass_font"])})
    col = lambda c: f"${c}${f}:${c}${l}"
    ctx.promo = dict(M0=M0, C0=4, n=n)
    ctx.refs["promo_incr_gp"] = f"SUM(Promotions!{col('S')})"
    ctx.refs["promo_n"] = f"COUNTA(Promotions!{col('A')})"

    # category summary
    C0 = 4
    ws.write(C0, 0, "By category: lift and price elasticity", ctx.h1())
    ws.write_row(C0 + 1, 0, ["Category", "Promotions", "Average lift", "Implied elasticity", "Override (Assumptions)", "Elasticity used", "Extra gross profit"], hdr)
    ws.set_row(C0 + 1, 32)
    for j, c in enumerate(CATEGORIES):
        r = C0 + 2 + j
        x = r + 1
        ws.write(r, 0, c, cell)
        ws.write_formula(r, 1, f"=COUNTIF({col('C')},$A{x})", ctx.cell(INT))
        ws.write_formula(r, 2, f"=IFERROR(AVERAGEIFS({col('K')},{col('C')},$A{x}),0)", ctx.cell(PCT0))
        ws.write_formula(r, 3, f"=IFERROR(AVERAGEIFS({col('U')},{col('C')},$A{x}),0)", ctx.cell(DEC2))
        ws.write_formula(r, 4, f'=IF(ISNUMBER(INDEX(el_override,{j+1})),INDEX(el_override,{j+1}),"")', ctx.cell(DEC2))
        ws.write_formula(r, 5, f"=IF(ISNUMBER(E{x}),E{x},D{x})", ctx.cell(DEC2, bold=True))
        ws.write_formula(r, 6, f"=SUMIFS({col('S')},{col('C')},$A{x})", ctx.cell(EUR))
    ctx.name("el_used", absrange("Promotions", C0 + 2, 5, C0 + 1 + len(CATEGORIES), 5))
    ws.merge_range(C0 + 8, 0, C0 + 8, 6, "Baseline: average daily sales of the same category and channels over up to 56 days before the promotion, leaving out other promotion days and the dip after big ones. Seasonality is not removed, so lifts in November and December are overstated.", ctx.note())
    ws.set_row(C0 + 8, 44)

    # campaign summary
    K0 = C0 + 11
    ws.write(K0, 0, "By campaign", ctx.h1())
    ws.write_row(K0 + 1, 0, ["Campaign", "Promotions", "Average lift", "Average margin dilution (pts)", "Promotions that add profit", "Extra gross profit"], hdr)
    ws.set_row(K0 + 1, 44)
    for i, cp in enumerate(camps):
        r = K0 + 2 + i
        x = r + 1
        ws.write(r, 0, cp, cell)
        ws.write_formula(r, 1, f"=COUNTIF({col('B')},$A{x})", ctx.cell(INT))
        ws.write_formula(r, 2, f"=IFERROR(AVERAGEIFS({col('K')},{col('B')},$A{x}),0)", ctx.cell(PCT0))
        ws.write_formula(r, 3, f"=IFERROR(AVERAGEIFS({col('O')},{col('B')},$A{x}),0)", ctx.cell(PCT))
        ws.write_formula(r, 4, f'=COUNTIFS({col("B")},$A{x},{col("T")},"Adds profit")', ctx.cell(INT))
        ws.write_formula(r, 5, f"=SUMIFS({col('S')},{col('B')},$A{x})", ctx.cell(EUR))
    ch = ctx.wb.add_chart({"type": "bar"})
    k1, k2 = K0 + 3, K0 + 2 + len(camps)
    ch.add_series({"name": "Extra gross profit", "categories": f"=Promotions!$A${k1}:$A${k2}", "values": f"=Promotions!$F${k1}:$F${k2}",
                   "fill": {"color": PAL["teal"]}, "invert_if_negative": True, "invert_if_negative_color": PAL["amber"], "gap": 40,
                   "data_labels": {"value": True, "num_format": "#,##0", "position": "outside_end", "font": {"size": 9}}})
    ch.set_title({"name": "Extra gross profit by campaign (all years)", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_legend({"none": True})
    ch.set_y_axis({"reverse": True, "label_position": "low", "num_font": {"size": 9}})
    ch.set_x_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 640, "height": 400})
    ws.insert_chart(C0, 8, ch, {"x_offset": 10})
    ws.freeze_panes(3, 1)


def build_returns(ctx: Ctx) -> None:
    ws = ctx.ws["Returns"]
    ctx.banner(ws, "Returns", 14, "Return rates and what returns cost: refunds and return shipping, less the cost of goods that went back on the shelf. All three years.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 11)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 2, 17)
    ws.set_column(3, 12, 13)
    hdr = ctx.head()
    cell = ctx.cell()
    # category table
    C0 = 4
    ws.write(C0, 0, "By category", ctx.h1())
    ws.write_row(C0 + 1, 0, ["", "Category", "", "Units sold", "Units returned", "Return rate", "Refunds", "Cost of returns", "Net revenue", "Cost of returns % of revenue"], hdr)
    ws.set_row(C0 + 1, 44)
    for j, cat in enumerate(CATEGORIES + ["All"]):
        r = C0 + 2 + j
        x = r + 1
        tot = cat == "All"
        crit = "m_category,$B" + str(x)
        ws.write(r, 1, cat if not tot else "All categories", ctx.cell(bold=tot))
        if tot:
            for cidx, m_ in [(3, "units"), (4, "returned_units"), (6, "refund_amount"), (8, "net_revenue")]:
                ws.write_formula(r, cidx, f"=SUM({cn(cidx)}{C0+3}:{cn(cidx)}{r})", ctx.cell(INT if cidx < 6 else EUR, bold=True))
            ws.write_formula(r, 7, f"=SUM(H{C0+3}:H{r})", ctx.cell(EUR, bold=True))
        else:
            ws.write_formula(r, 3, f"=SUMIFS(m_units,{crit})", ctx.cell(INT))
            ws.write_formula(r, 4, f"=SUMIFS(m_returned_units,{crit})", ctx.cell(INT))
            ws.write_formula(r, 6, f"=SUMIFS(m_refund_amount,{crit})", ctx.cell(EUR))
            ws.write_formula(r, 7, f"=SUMIFS(m_refund_amount,{crit})+SUMIFS(m_return_shipping,{crit})-SUMIFS(m_restock_cogs,{crit})", ctx.cell(EUR))
            ws.write_formula(r, 8, f"=SUMIFS(m_net_revenue,{crit})", ctx.cell(EUR))
        ws.write_formula(r, 5, f"=IFERROR(E{x}/D{x},0)", ctx.cell(PCT, bold=tot))
        ws.write_formula(r, 9, f"=IFERROR(H{x}/I{x},0)", ctx.cell(PCT, bold=tot))
    ctx.refs["ret_refund_total"] = absref("Returns", C0 + 2 + len(CATEGORIES), 6)
    ctx.ret = dict(C0=C0, T0=30, L0=C0 + 12)

    # SKU table
    T0 = 30
    f, l = T0 + 2, T0 + 1 + NSKU
    ws.write(T0 - 1, 0, "By SKU", ctx.h1())
    ws.write_row(T0, 0, ["SKU", "Product", "Category", "Units sold", "Units returned", "Return rate", "Refunds", "Cost of returns", "Net revenue", "Cost of returns % of revenue", "Enough sales (1 yes)", "Rank by return rate"], hdr)
    ws.set_row(T0, 44)
    for i in range(NSKU):
        r = T0 + 1 + i
        x = r + 1
        d = i + 2
        crit = f"m_sku,$A{x}"
        ws.write_formula(r, 0, f"=Data_Products!$A${d}", cell)
        ws.write_formula(r, 1, f"=Data_Products!$B${d}", cell)
        ws.write_formula(r, 2, f"=Data_Products!$C${d}", cell)
        ws.write_formula(r, 3, f"=SUMIFS(m_units,{crit})", ctx.cell(INT))
        ws.write_formula(r, 4, f"=SUMIFS(m_returned_units,{crit})", ctx.cell(INT))
        ws.write_formula(r, 5, f"=IFERROR(E{x}/D{x},0)", ctx.cell(PCT))
        ws.write_formula(r, 6, f"=SUMIFS(m_refund_amount,{crit})", ctx.cell(EUR))
        ws.write_formula(r, 7, f"=SUMIFS(m_refund_amount,{crit})+SUMIFS(m_return_shipping,{crit})-SUMIFS(m_restock_cogs,{crit})", ctx.cell(EUR))
        ws.write_formula(r, 8, f"=SUMIFS(m_net_revenue,{crit})", ctx.cell(EUR))
        ws.write_formula(r, 9, f"=IFERROR(H{x}/I{x},0)", ctx.cell(PCT))
        ws.write_formula(r, 10, f"=IF(D{x}>=min_ret_units,1,0)", ctx.cell("0"))
        ws.write_formula(r, 11, f'=IF(K{x}=1,COUNTIFS($K${f}:$K${l},1,$F${f}:$F${l},">"&F{x})+COUNTIFS($K${f}:K{x},1,$F${f}:F{x},F{x}),"")', ctx.cell("0"))
    ctx.refs["ret_sku_refunds"] = f"SUM(Returns!$G${f}:$G${l})"
    ctx.refs["ret_sku_revenue"] = f"SUM(Returns!$I${f}:$I${l})"

    # top 10
    L0 = C0 + 12
    ws.write(L0, 0, "Top 10 problem SKUs (highest return rate, with enough sales)", ctx.h1())
    ws.write_row(L0 + 1, 0, ["Rank", "Product", "Category", "Units sold", "Units returned", "Return rate", "Cost of returns", "Cost of returns % of revenue"], hdr)
    ws.set_row(L0 + 1, 44)
    for k in range(10):
        r = L0 + 2 + k
        x = r + 1
        ws.write(r, 0, k + 1, ctx.cell("0", align="center"))
        m = f"MATCH($A{x},$L${f}:$L${l},0)"
        for cidx, (col, num) in enumerate([("B", None), ("C", None), ("D", INT), ("E", INT), ("F", PCT), ("H", EUR), ("J", PCT)]):
            ws.write_formula(r, 1 + cidx, f'=IFERROR(INDEX(${col}${f}:${col}${l},{m}),"")', ctx.cell(num) if num else cell)
    t1, t2 = L0 + 3, L0 + 12
    ch = ctx.wb.add_chart({"type": "bar"})
    ch.add_series({"name": "Return rate", "categories": f"=Returns!$B${t1}:$B${t2}", "values": f"=Returns!$F${t1}:$F${t2}",
                   "fill": {"color": PAL["amber"]}, "data_labels": {"value": True, "num_format": "0%", "font": {"size": 9}}})
    ch.set_title({"name": "Highest return rates by SKU", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_legend({"none": True})
    ch.set_y_axis({"reverse": True, "num_font": {"size": 9}})
    ch.set_x_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 470, "height": 255})
    ws.insert_chart(L0, 9, ch, {"x_offset": 20})
    ch2 = ctx.wb.add_chart({"type": "column"})
    ch2.add_series({"name": "Return rate", "categories": f"=Returns!$B${C0+3}:$B${C0+2+len(CATEGORIES)}", "values": f"=Returns!$F${C0+3}:$F${C0+2+len(CATEGORIES)}",
                    "fill": {"color": PAL["teal"]}, "data_labels": {"value": True, "num_format": "0.0%", "font": {"size": 9}}, "gap": 60})
    ch2.set_title({"name": "Return rate by category (units)", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch2.set_legend({"none": True})
    ch2.set_y_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch2.set_chartarea({"border": {"color": PAL["line"]}})
    ch2.set_size({"width": 400, "height": 230})
    ws.insert_chart(C0, 10, ch2)
    ws.freeze_panes(3, 0)
