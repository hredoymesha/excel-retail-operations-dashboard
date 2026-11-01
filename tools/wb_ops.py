"""Profit and margin, products and inventory sheets."""
from __future__ import annotations

from xlsxwriter.utility import xl_col_to_name as cn

from wb_core import DEC1, DEC2, EUR, EUR2, INT, PAL, PCT, Ctx, absrange, absref
from wb_data import NSKU, sf

NS = NSKU


def waterfall(ctx: Ctx, ws, sheet: str, top: int, left: int, rows: list[tuple[str, str, bool]], title: str,
              chart_at: tuple[int, int], size=(640, 330), y_min: float | None = None):
    """Write the helper table for a waterfall and insert the chart.

    rows: (label, value formula, is_total). Totals restart the bar from zero; other rows float.
    """
    heads = ["Step", "Value", "Running total", "Base", "Total", "Increase", "Decrease"]
    ws.write_row(top, left, heads, ctx.head())
    for i, (label, f, tot) in enumerate(rows):
        r = top + 1 + i
        x = r + 1
        c = lambda k: cn(left + k)
        ws.write(r, left, label, ctx.cell())
        ws.write_formula(r, left + 1, f, ctx.cell(EUR))
        if tot:
            ws.write_formula(r, left + 2, f"={c(1)}{x}", ctx.cell(EUR))
            ws.write_formula(r, left + 3, "=0", ctx.cell(EUR))
            ws.write_formula(r, left + 4, f"={c(1)}{x}", ctx.cell(EUR))
            ws.write_formula(r, left + 5, "=0", ctx.cell(EUR))
            ws.write_formula(r, left + 6, "=0", ctx.cell(EUR))
        else:
            ws.write_formula(r, left + 2, f"={c(2)}{x-1}+{c(1)}{x}", ctx.cell(EUR))
            ws.write_formula(r, left + 3, f"=MIN({c(2)}{x-1},{c(2)}{x})", ctx.cell(EUR))
            ws.write_formula(r, left + 4, "=0", ctx.cell(EUR))
            ws.write_formula(r, left + 5, f"=MAX({c(1)}{x},0)", ctx.cell(EUR))
            ws.write_formula(r, left + 6, f"=MAX(-{c(1)}{x},0)", ctx.cell(EUR))
    first, last = top + 2, top + 1 + len(rows)
    ch = ctx.wb.add_chart({"type": "column", "subtype": "stacked"})
    cats = f"='{sheet}'!${cn(left)}${first}:${cn(left)}${last}"
    for k, (nm_, col, fill) in enumerate([("Base", 3, None), ("Total", 4, PAL["navy"]), ("Increase", 5, PAL["teal"]), ("Decrease", 6, PAL["amber"])]):
        s = {"name": nm_, "categories": cats, "values": f"='{sheet}'!${cn(left+col)}${first}:${cn(left+col)}${last}", "gap": 40}
        s["fill"] = {"none": True} if fill is None else {"color": fill}
        s["border"] = {"none": True}
        ch.add_series(s)
    ch.set_title({"name": title, "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_legend({"position": "bottom", "delete_series": [0], "font": {"size": 9}})
    y_axis = {"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}, "num_font": {"size": 9}}
    if y_min is not None:
        y_axis["min"] = y_min
    ch.set_y_axis(y_axis)
    ch.set_x_axis({"num_font": {"size": 8, "rotation": -35}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": size[0], "height": size[1]})
    ws.insert_chart(chart_at[0], chart_at[1], ch)
    return first, last


def build_profit(ctx: Ctx) -> None:
    ws = ctx.ws["Profit_Margin"]
    ctx.banner(ws, "Profit and margin", 14, "Contribution margin after discounts, returns, shipping and payment fees. Follows the Dashboard drop-downs.")
    ctx.back_link(ws)
    ws.write_formula(2, 2, '="Showing "&IF(sel_year="All","all years",sel_year)&", region "&sel_region&", channel "&sel_channel&", category "&sel_category', ctx.fmt(italic=True, font_color=PAL["slate"]))
    ws.set_column(0, 0, 54)
    ws.set_column(1, 4, 15)
    ws.set_column(5, 5, 12)
    ws.set_column(6, 13, 14)
    ws.set_column(14, 33, 12)
    k = ctx.kpi_rows
    cd = "Calc_Dashboard"
    ws.write(4, 0, "Profit and loss for the selected period", ctx.h1())
    ws.write_row(5, 0, ["Item", "Selected period", "% of net revenue", "A year earlier", "Change"], ctx.head())
    items = [
        ("List value (units x list price)", "list_value", 1, False),
        ("Discounts", "discount_value", -1, False),
        ("Net revenue", "net_revenue", 1, True),
        ("Cost of goods sold", "cogs", -1, False),
        ("Gross profit", "gross_profit", 1, True),
        ("Shipping", "shipping", -1, False),
        ("Payment fees", "payment_fee", -1, False),
        ("Marketplace fees", "platform_fee", -1, False),
        ("Refunds", "refund_amount", -1, False),
        ("Cost recovered on restocked returns", "restock_cogs", 1, False),
        ("Return shipping", "return_shipping", -1, False),
        ("Contribution margin", "contribution", 1, True),
    ]
    rowof = {}
    for i, (label, key, sign, bold) in enumerate(items):
        r = 6 + i
        rowof[key] = r
        src = k[key] + 1
        fm = ctx.cell(EUR, bold=bold, bg_color=PAL["light"] if bold else PAL["white"])
        ws.write(r, 0, label, ctx.cell(bold=bold, bg_color=PAL["light"] if bold else PAL["white"]))
        sg = "" if sign == 1 else "-"
        ws.write_formula(r, 1, f"={sg}{cd}!$B${src}", fm)
        ws.write_formula(r, 2, f"=IFERROR(B{r+1}/B${rowof.get('net_revenue', 8) + 1},0)", ctx.cell(PCT, bold=bold, bg_color=PAL["light"] if bold else PAL["white"]))
        ws.write_formula(r, 3, f"={sg}{cd}!$C${src}", fm)
        ws.write_formula(r, 4, f"=B{r+1}-D{r+1}", fm)
    ctx.pl_rows = rowof
    ctx.refs["pl_cm"] = absref("Profit_Margin", rowof["contribution"], 1)
    ctx.refs["pl_net"] = absref("Profit_Margin", rowof["net_revenue"], 1)
    ctx.refs["pl_gp"] = absref("Profit_Margin", rowof["gross_profit"], 1)
    r = 6 + len(items) + 1
    ws.merge_range(r, 0, r, 4, "Reading it: costs are negative. A year earlier is zero when All years is selected or when no earlier year exists.", ctx.fmt(italic=True, font_color=PAL["slate"]))

    pl = lambda key: f"B{rowof[key]+1}"
    wf = [("List value", f"={pl('list_value')}", True), ("Discounts", f"={pl('discount_value')}", False),
          ("Net revenue", f"={pl('net_revenue')}", True), ("Cost of goods", f"={pl('cogs')}", False),
          ("Gross profit", f"={pl('gross_profit')}", True), ("Shipping", f"={pl('shipping')}", False),
          ("Payment fees", f"={pl('payment_fee')}", False), ("Marketplace fees", f"={pl('platform_fee')}", False),
          ("Returns (net)", f"={pl('refund_amount')}+{pl('restock_cogs')}+{pl('return_shipping')}", False),
          ("Contribution margin", f"={pl('contribution')}", True)]
    waterfall(ctx, ws, "Profit_Margin", 22, 0, wf, "From list value to contribution margin", (4, 6), (700, 330))

    # bridge
    b0 = 36
    ws.write(b0, 0, "Margin bridge: reference year against the year before", ctx.h1())
    ws.write(b0 + 1, 0, "Reference year", ctx.cell())
    ws.write_formula(b0 + 1, 1, "=ref_year", ctx.cell("0"))
    ctx.name("br_yb", absref("Profit_Margin", b0 + 1, 1))
    ws.write(b0 + 2, 0, "Year before", ctx.cell())
    ws.write_formula(b0 + 2, 1, "=ref_year-1", ctx.cell("0"))
    ctx.name("br_ya", absref("Profit_Margin", b0 + 2, 1))
    ws.write_formula(b0 + 3, 0, '=IF(br_ya<MIN(m_year),"No earlier year in the data, so the bridge shows everything as mix.","")', ctx.fmt(font_color=PAL["fail_font"], italic=True))

    W0 = b0 + 40          # header row of the working table
    fr, lr = W0 + 2, W0 + 1 + NS
    heads = ["SKU", "Product", "Units, year before", "Units, reference", "List value, before", "List value, ref",
             "Discounts, before", "Discounts, ref", "Cost of goods, before", "Cost of goods, ref", "Fees, before", "Fees, ref",
             "Returns cost, before", "Returns cost, ref", "List price per unit, before", "List price per unit, ref",
             "Discount rate, before", "Discount rate, ref", "Unit cost, before", "Unit cost, ref", "Fees per unit, before",
             "Fees per unit, ref", "Returns per unit, before", "Returns per unit, ref", "Margin per unit, before",
             "Price effect", "Discount effect", "Cost effect", "Fee effect", "Returns effect", "Ref units at old margin",
             "Contribution, before", "Contribution, ref"]
    ws.write(W0 - 1, 0, "Working table, one row per SKU (formulas only)", ctx.h1())
    ws.write_row(W0, 0, heads, ctx.head())
    ws.set_row(W0, 44)

    def yr(measure, which):
        return sf(measure, f"m_year,br_y{which}", "m_sku,$A{x}")

    for i in range(NS):
        r = W0 + 1 + i
        x = r + 1
        ws.write_formula(r, 0, f"=Data_Products!$A${i+2}", ctx.cell())
        ws.write_formula(r, 1, f"=Data_Products!$B${i+2}", ctx.cell())
        def wr(col, f, num=INT):
            ws.write_formula(r, col, f, ctx.cell(num))
        for j, which in enumerate(["a", "b"]):
            wr(2 + j, "=" + sf("units", f"m_year,br_y{which}", f"m_sku,$A{x}"))
            wr(4 + j, "=" + sf("list_value", f"m_year,br_y{which}", f"m_sku,$A{x}"), EUR)
            wr(6 + j, "=" + sf("discount_value", f"m_year,br_y{which}", f"m_sku,$A{x}"), EUR)
            wr(8 + j, "=" + sf("cogs", f"m_year,br_y{which}", f"m_sku,$A{x}"), EUR)
            wr(10 + j, "=" + "+".join(sf(m_, f"m_year,br_y{which}", f"m_sku,$A{x}") for m_ in ("shipping", "payment_fee", "platform_fee")), EUR)
            wr(12 + j, "=" + sf("refund_amount", f"m_year,br_y{which}", f"m_sku,$A{x}") + "+" + sf("return_shipping", f"m_year,br_y{which}", f"m_sku,$A{x}")
               + "-" + sf("restock_cogs", f"m_year,br_y{which}", f"m_sku,$A{x}"), EUR)
        C, D, E, F, G, H, I, J, K, L, M, N = [f"{cn(c)}{x}" for c in range(2, 14)]
        # per unit values, with the other year as fallback when a SKU did not sell
        pairs = [(14, E, C, F, D), (18, I, C, J, D), (20, K, C, L, D), (22, M, C, N, D)]
        for col, a_n, a_d, b_n, b_d in pairs:
            ws.write_formula(r, col, f"=IF({a_d}>0,{a_n}/{a_d},IF({b_d}>0,{b_n}/{b_d},0))", ctx.cell(DEC2))
            ws.write_formula(r, col + 1, f"=IF({b_d}>0,{b_n}/{b_d},{cn(col)}{x})", ctx.cell(DEC2))
        ws.write_formula(r, 16, f"=IF({E}>0,{G}/{E},IF({F}>0,{H}/{F},0))", ctx.cell(PCT))
        ws.write_formula(r, 17, f"=IF({F}>0,{H}/{F},{cn(16)}{x})", ctx.cell(PCT))
        pA, pB, dA, dB, cA, cB, fA, fB, rA, rB = [f"{cn(c)}{x}" for c in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23)]
        ws.write_formula(r, 24, f"={pA}*(1-{dA})-{cA}-{fA}-{rA}", ctx.cell(DEC2))
        ws.write_formula(r, 25, f"={D}*({pB}-{pA})*(1-{dA})", ctx.cell(EUR))
        ws.write_formula(r, 26, f"=-{D}*{pB}*({dB}-{dA})", ctx.cell(EUR))
        ws.write_formula(r, 27, f"=-{D}*({cB}-{cA})", ctx.cell(EUR))
        ws.write_formula(r, 28, f"=-{D}*({fB}-{fA})", ctx.cell(EUR))
        ws.write_formula(r, 29, f"=-{D}*({rB}-{rA})", ctx.cell(EUR))
        ws.write_formula(r, 30, f"={D}*{cn(24)}{x}", ctx.cell(EUR))
        ws.write_formula(r, 31, f"={E}-{G}-{I}-{K}-{M}", ctx.cell(EUR))
        ws.write_formula(r, 32, f"={F}-{H}-{J}-{L}-{N}", ctx.cell(EUR))
    tot = lr + 1
    ws.write(lr, 0, "Total", ctx.cell(bold=True))
    for col in [2, 3] + list(range(4, 14)) + list(range(25, 33)):
        ws.write_formula(lr, col, f"=SUM({cn(col)}{fr}:{cn(col)}{lr})", ctx.cell(EUR if col > 3 else INT, bold=True))

    s0 = b0 + 5
    ctx.bridge_s0 = s0
    ws.write_row(s0, 0, ["Bridge step", "Effect"], ctx.head())
    ua, ub = f"C{tot}", f"D{tot}"
    steps = [
        ("Contribution margin, year before", f"=AF{tot}", True),
        ("Volume (more or fewer units at the old average margin)", f"=({ub}-{ua})*IFERROR(AF{tot}/{ua},0)", False),
        ("Mix (shift between SKUs)", f"=AE{tot}-{ub}*IFERROR(AF{tot}/{ua},0)", False),
        ("List price", f"=Z{tot}", False),
        ("Discounts", f"=AA{tot}", False),
        ("Unit cost", f"=AB{tot}", False),
        ("Shipping and fees per unit", f"=AC{tot}", False),
        ("Returns per unit", f"=AD{tot}", False),
        ("Contribution margin, reference year", f"=AG{tot}", True),
    ]
    for i, (label, f, total) in enumerate(steps):
        ws.write(s0 + 1 + i, 0, label, ctx.cell(bold=total, bg_color=PAL["light"] if total else PAL["white"]))
        ws.write_formula(s0 + 1 + i, 1, f, ctx.cell(EUR, bold=total, bg_color=PAL["light"] if total else PAL["white"]))
    ws.write(s0 + 10, 0, "Difference: reference minus (before + all effects)", ctx.cell(italic=True))
    ws.write_formula(s0 + 10, 1, f"=B{s0+10}-SUM(B{s0+2}:B{s0+9})", ctx.cell(EUR2, italic=True))
    ctx.refs["bridge_gap"] = absref("Profit_Margin", s0 + 10, 1)
    ctx.refs["bridge_cm_ref"] = absref("Profit_Margin", s0 + 9, 1)
    ctx.refs["bridge_cm_work"] = absref("Profit_Margin", lr, 32)
    ws.merge_range(s0 + 11, 0, s0 + 11, 4, "Volume + mix = change in units valued at last year's margin per SKU. The other lines are changes in price, discount, cost, fee and return rates per unit, valued at this year's units.", ctx.note())
    ws.set_row(s0 + 11, 40)
    ws.set_row(s0 + 11, 40)
    bw = [(label.split(" (")[0] if i not in (0, 8) else ("Year before" if i == 0 else "Reference year"), f"=B{s0+2+i}", i in (0, 8)) for i, (label, f, t) in enumerate(steps)]
    waterfall(ctx, ws, "Profit_Margin", s0 + 13, 0, bw, "Contribution margin bridge (axis starts at 300,000)", (b0, 6), (700, 340), y_min=300000)
    ws.freeze_panes(3, 1)


def build_products(ctx: Ctx) -> None:
    ws = ctx.ws["Products"]
    ctx.banner(ws, "Products: ABC and XYZ", 16, "ABC ranks SKUs by revenue in the trailing window. XYZ ranks them by how steady their monthly demand is.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 8)
    ws.set_column(1, 1, 11)
    ws.set_column(2, 2, 28)
    ws.set_column(3, 3, 17)
    ws.set_column(4, 15, 12)
    cs = "Calc_Sku"
    f5, l5 = 5, 4 + NS
    rng = lambda col: f"{cs}!${col}${f5}:${col}${l5}"
    ws.write(3, 0, "ABC-XYZ matrix: number of SKUs, and share of revenue", ctx.h1())
    ws.write(4, 2, "Count of SKUs", ctx.head())
    ws.write(4, 8, "Share of revenue", ctx.head())
    for blk, c0 in (("n", 3), ("s", 9)):
        ws.write(5, c0 - 1, "", ctx.head())
        for j, z in enumerate("XYZ"):
            ws.write(5, c0 + j, z, ctx.head())
        for i, a in enumerate("ABC"):
            ws.write(6 + i, c0 - 1, a, ctx.head())
            for j, z in enumerate("XYZ"):
                if blk == "n":
                    ws.write_formula(6 + i, c0 + j, f'=COUNTIFS({rng("N")},"{a}",{rng("O")},"{z}")', ctx.cell(INT, align="center"))
                else:
                    ws.write_formula(6 + i, c0 + j, f'=SUMIFS({rng("D")},{rng("N")},"{a}",{rng("O")},"{z}")/SUM({rng("D")})', ctx.cell(PCT, align="center"))
    ws.write(9, 2, "Total", ctx.cell(bold=True))
    ws.write_formula(9, 3, "=SUM(D7:F9)", ctx.cell(INT, bold=True, align="center"))
    ws.write_formula(9, 9, "=SUM(J7:L9)", ctx.cell(PCT, bold=True, align="center"))
    ctx.refs["abc_total"] = absref("Products", 9, 3)
    ctx.refs["abc_share_total"] = absref("Products", 9, 9)
    ws.conditional_format(6, 3, 8, 5, {"type": "2_color_scale", "min_color": "#FFFFFF", "max_color": PAL["sky"]})
    ws.conditional_format(6, 9, 8, 11, {"type": "2_color_scale", "min_color": "#FFFFFF", "max_color": PAL["sky"]})
    ws.merge_range(3, 13, 9, 15, "A: first 80% of revenue. X: monthly CV up to 0.40. AX items are big and steady: keep them in stock. CZ items are small and erratic: hold little.",
                   ctx.fmt(text_wrap=True, font_size=9, font_color=PAL["slate"], valign="top", italic=True))

    T0 = 12
    heads = ["Rank", "SKU", "Product", "Category", "Revenue (window)", "Share", "Cumulative share", "ABC", "XYZ", "Class",
             "Gross margin %", "Return rate", "Lost units", "Days of cover", "Stock status", "Row in Calc_Sku"]
    ws.write(T0 - 1, 0, "SKU scorecard, sorted by revenue", ctx.h1())
    ws.write_row(T0, 0, heads, ctx.head())
    ws.set_row(T0, 32)
    fr = T0 + 2
    lr = T0 + 1 + NS
    for k_ in range(NS):
        r = T0 + 1 + k_
        x = r + 1
        ws.write(r, 0, k_ + 1, ctx.cell("0", align="center"))
        ws.write_formula(r, 15, f"=MATCH($A{x},{rng('I')},0)", ctx.cell("0", font_color=PAL["grey"]))
        pos = f"$P{x}"
        pick = lambda col: f"=INDEX({rng(col)},{pos})"
        ws.write_formula(r, 1, pick("A"), ctx.cell())
        ws.write_formula(r, 2, pick("B"), ctx.cell())
        ws.write_formula(r, 3, pick("C"), ctx.cell())
        ws.write_formula(r, 4, pick("D"), ctx.cell(EUR))
        ws.write_formula(r, 5, f"=E{x}/SUM($E${fr}:$E${lr})", ctx.cell(PCT))
        ws.write_formula(r, 6, f"=SUM($F${fr}:F{x})", ctx.cell(PCT))
        ws.write_formula(r, 7, pick("N"), ctx.cell(align="center"))
        ws.write_formula(r, 8, pick("O"), ctx.cell(align="center"))
        ws.write_formula(r, 9, f"=H{x}&I{x}", ctx.cell(align="center"))
        ws.write_formula(r, 10, pick("R"), ctx.cell(PCT))
        ws.write_formula(r, 11, pick("S"), ctx.cell(PCT))
        ws.write_formula(r, 12, pick("V"), ctx.cell(INT))
        ws.write_formula(r, 13, f"=INDEX(Inventory!$Q${ctx.inv_main[0]+1}:$Q${ctx.inv_main[1]+1},{pos})", ctx.cell(DEC1, align="right"))
        ws.write_formula(r, 14, f"=INDEX(Inventory!$X${ctx.inv_main[0]+1}:$X${ctx.inv_main[1]+1},{pos})", ctx.cell())
    ws.conditional_format(T0 + 1, 7, lr - 1, 7, {"type": "cell", "criteria": "==", "value": '"A"', "format": ctx.fmt(bold=True, font_color=PAL["navy"], bg_color=PAL["mid"])})
    ws.conditional_format(T0 + 1, 14, lr - 1, 14, {"type": "text", "criteria": "containing", "value": "Reorder", "format": ctx.fmt(bg_color=PAL["warn_fill"], font_color=PAL["warn_font"])})
    ws.conditional_format(T0 + 1, 14, lr - 1, 14, {"type": "text", "criteria": "containing", "value": "Stock-out", "format": ctx.fmt(bg_color=PAL["fail_fill"], font_color=PAL["fail_font"])})
    ws.freeze_panes(T0 + 1, 3)
    ctx.refs["abc_first"] = absref("Products", T0 + 1, 7)
    ctx.sc_rows = (T0 + 1, lr - 1)

    ch = ctx.wb.add_chart({"type": "column"})
    ch.add_series({"name": "Revenue", "categories": f"=Products!$B${fr}:$B${lr}", "values": f"=Products!$E${fr}:$E${lr}",
                   "fill": {"color": PAL["navy"]}, "gap": 40})
    ln = ctx.wb.add_chart({"type": "line"})
    ln.add_series({"name": "Cumulative share (right axis)", "categories": f"=Products!$B${fr}:$B${lr}", "values": f"=Products!$G${fr}:$G${lr}",
                   "y2_axis": True, "line": {"color": PAL["amber"], "width": 2.25}})
    ch.combine(ln)
    ch.set_title({"name": "Pareto chart: revenue by SKU", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_y_axis({"num_format": "#,##0", "num_font": {"size": 9}, "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ln.set_y2_axis({"num_format": "0%", "min": 0, "max": 1, "num_font": {"size": 9}})
    ch.set_x_axis({"num_font": {"size": 7, "rotation": -90}})
    ch.set_legend({"position": "bottom", "font": {"size": 9}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 900, "height": 360})
    ws.insert_chart(lr + 2, 1, ch)


def build_inventory(ctx: Ctx) -> None:
    ws = ctx.ws["Inventory"]
    ctx.banner(ws, "Inventory", 27, "Reorder points from lead-time demand plus safety stock, economic order quantity, cover, turns and GMROI. Stock is the snapshot on the as-of date.")
    ctx.back_link(ws)
    cols = list(ctx.data["products"].columns)
    pc = lambda name: cn(cols.index(name))
    ws.set_column(0, 0, 16)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 2, 17)
    ws.set_column(3, 26, 11.5)
    cs = "Calc_Sku"

    # main table first (so the list above can point at it)
    M0 = 34
    heads = ["SKU", "Product", "Category", "Stocking policy", "On hand", "On order", "Stock position", "Unit cost", "Lead time (days)",
             "Lead time SD", "Min order qty", "Demand per day", "SD of daily demand", "Safety stock", "Reorder point", "Economic order qty",
             "Days of cover", "Inventory turns", "GMROI", "Overstock units", "Overstock cost per year", "Lost units (window)",
             "Estimated lost revenue", "Status", "Suggested order qty", "Urgency (cover / lead time)", "Urgency rank"]
    ws.write(M0 - 1, 0, "All SKUs", ctx.h1())
    ws.write_row(M0, 0, heads, ctx.head())
    ws.set_row(M0, 44)
    f, l = M0 + 2, M0 + 1 + NS
    ctx.inv_main = (M0 + 1, M0 + NS)
    for i in range(NS):
        r = M0 + 1 + i
        x = r + 1
        crow = 5 + i
        g = lambda name: f"=Data_Products!${pc(name)}${i+2}"
        ws.write_formula(r, 0, g("sku"), ctx.cell())
        ws.write_formula(r, 1, g("product_name"), ctx.cell())
        ws.write_formula(r, 2, g("category"), ctx.cell())
        ws.write_formula(r, 3, g("stocking_policy"), ctx.cell())
        ws.write_formula(r, 4, g("on_hand_end"), ctx.cell(INT))
        ws.write_formula(r, 5, g("on_order_end"), ctx.cell(INT))
        ws.write_formula(r, 6, f"=E{x}+F{x}", ctx.cell(INT))
        ws.write_formula(r, 7, g("unit_cost_now"), ctx.cell(EUR2))
        ws.write_formula(r, 8, g("lead_time_days_avg"), ctx.cell(INT))
        ws.write_formula(r, 9, g("lead_time_days_sd"), ctx.cell(DEC1))
        ws.write_formula(r, 10, g("min_order_qty"), ctx.cell(INT))
        ws.write_formula(r, 11, f"={cs}!$T${crow}", ctx.cell(DEC2))
        ws.write_formula(r, 12, f"={cs}!$L${crow}/SQRT(days_month)", ctx.cell(DEC2))
        ws.write_formula(r, 13, f"=NORM.S.INV(svc_level)*SQRT((I{x}+review_days)*M{x}^2+(L{x}*J{x})^2)", ctx.cell(DEC1))
        ws.write_formula(r, 14, f"=L{x}*(I{x}+review_days)+N{x}", ctx.cell(DEC1))
        ws.write_formula(r, 15, f"=MAX(K{x},CEILING(SQRT(2*L{x}*days_year*order_cost/(hold_rate*H{x})),K{x}))", ctx.cell(INT))
        ws.write_formula(r, 16, f'=IF(L{x}>0,E{x}/L{x},"no demand")', ctx.cell(DEC1, align="right"))
        ws.write_formula(r, 17, f"=IFERROR({cs}!$E${crow}*months_year/dem_window/(Data_Products!${pc('avg_on_hand_12m')}${i+2}*H{x}),0)", ctx.cell(DEC2))
        ws.write_formula(r, 18, f"=IFERROR({cs}!$H${crow}*months_year/dem_window/(Data_Products!${pc('avg_on_hand_12m')}${i+2}*H{x}),0)", ctx.cell(DEC2))
        ws.write_formula(r, 19, f"=MAX(0,E{x}-(O{x}+P{x}))", ctx.cell(INT))
        ws.write_formula(r, 20, f"=T{x}*H{x}*hold_rate", ctx.cell(EUR))
        ws.write_formula(r, 21, f"={cs}!$V${crow}", ctx.cell(INT))
        ws.write_formula(r, 22, f"=V{x}*{cs}!$Q${crow}", ctx.cell(EUR))
        disc = f"Data_Products!${pc('discontinued_date')}${i+2}"
        ws.write_formula(r, 23, (f'=IF(ISNUMBER({disc}),IF(E{x}>0,"Obsolete stock","Discontinued"),IF(G{x}<=O{x},"Reorder now",'
                                 f'IF(AND(ISNUMBER(Q{x}),Q{x}<I{x}),"Stock-out risk",IF(AND(ISNUMBER(Q{x}),Q{x}>over_days),"Overstock","OK"))))'), ctx.cell())
        ws.write_formula(r, 24, f'=IF(X{x}="Reorder now",MAX(K{x},CEILING(O{x}+P{x}-G{x},K{x})),0)', ctx.cell(INT))
        ws.write_formula(r, 25, f'=IF(OR(X{x}="Reorder now",X{x}="Stock-out risk"),IF(ISNUMBER(Q{x}),Q{x}/I{x},0),"")', ctx.cell(DEC2))
        ws.write_formula(r, 26, f'=IF(Z{x}="","",COUNTIF($Z${f}:$Z${l},"<"&Z{x})+COUNTIF($Z${f}:Z{x},Z{x}))', ctx.cell("0"))
    ws.conditional_format(M0 + 1, 23, M0 + NS, 23, {"type": "text", "criteria": "containing", "value": "Reorder", "format": ctx.fmt(bg_color=PAL["warn_fill"], font_color=PAL["warn_font"])})
    ws.conditional_format(M0 + 1, 23, M0 + NS, 23, {"type": "text", "criteria": "containing", "value": "Stock-out", "format": ctx.fmt(bg_color=PAL["fail_fill"], font_color=PAL["fail_font"])})
    ws.conditional_format(M0 + 1, 23, M0 + NS, 23, {"type": "text", "criteria": "containing", "value": "Overstock", "format": ctx.fmt(bg_color=PAL["mid"], font_color=PAL["navy"])})
    ws.conditional_format(M0 + 1, 23, M0 + NS, 23, {"type": "text", "criteria": "containing", "value": "Obsolete", "format": ctx.fmt(bg_color=PAL["mid"], font_color=PAL["navy"])})
    ctx.refs["inv_status_rng"] = absrange("Inventory", M0 + 1, 23, M0 + NS, 23)
    ctx.refs["inv_onhand_rng"] = absrange("Inventory", M0 + 1, 4, M0 + NS, 4)
    ctx.refs["inv_cost_rng"] = absrange("Inventory", M0 + 1, 7, M0 + NS, 7)
    ctx.refs["inv_rop_rng"] = absrange("Inventory", M0 + 1, 14, M0 + NS, 14)
    ctx.inv_cols = dict(sku=0, name=1, cat=2, onhand=4, onorder=5, pos=6, cost=7, lt=8, ltsd=9, moq=10, mu=11, sd=12, rop=14, eoq=15,
                        cover=16, status=23, qty=24)

    # summary
    ws.write(3, 0, "Summary", ctx.h1())
    ws.write_row(4, 0, ["Status", "SKUs"], ctx.head())
    sts = ["Reorder now", "Stock-out risk", "Overstock", "Obsolete stock", "Discontinued", "OK"]
    for i, s_ in enumerate(sts):
        ws.write(5 + i, 0, s_, ctx.cell())
        ws.write_formula(5 + i, 1, f'=COUNTIF({ctx.refs["inv_status_rng"]},A{6+i})', ctx.cell(INT))
    ctx.refs["inv_status_total"] = absref("Inventory", 5 + len(sts), 1)
    ws.write(5 + len(sts), 0, "Total", ctx.cell(bold=True))
    ws.write_formula(5 + len(sts), 1, f"=SUM(B6:B{5+len(sts)})", ctx.cell(INT, bold=True))
    ws.merge_range(4, 3, 4, 5, "Measure", ctx.head())
    ws.write(4, 6, "Value", ctx.head())
    meas = [("Stock value at cost", f"=SUMPRODUCT({ctx.refs['inv_onhand_rng']},{ctx.refs['inv_cost_rng']})", EUR),
            ("Overstock cost per year", f"=SUM(Inventory!$U${l-NS+1}:$U${l})", EUR),
            ("Estimated lost revenue in the window", f"=SUM(Inventory!$W${l-NS+1}:$W${l})", EUR),
            ("Service level used", "=svc_level", PCT),
            ("Order-up-to rule", '="ROP + EOQ"', None)]
    for i, (lab, fm, num) in enumerate(meas):
        ws.merge_range(5 + i, 3, 5 + i, 5, lab, ctx.cell())
        ws.write_formula(5 + i, 6, fm, ctx.cell(num) if num else ctx.cell(align="right"))
    ctx.refs["inv_value"] = absref("Inventory", 5, 6)

    # reorder list
    L0 = 15
    ws.merge_range(12, 0, 13, 9, "Stock position is stock on hand plus stock on order. A SKU can show zero or very low days of cover and still have a high stock position: the stock is on its way. It is flagged Stock-out risk, but it needs no new order, so the suggested order is 0. A suggested order appears only for Reorder now, when the stock position is at or below the reorder point.",
                   ctx.fmt(italic=True, font_color=PAL["slate"], text_wrap=True, valign="top"))
    ws.write(L0 - 1, 0, "Reorder list, most urgent first", ctx.h1())
    ws.write_row(L0, 0, ["Rank", "Product", "Status", "Days of cover", "On hand", "On order", "Stock position", "Reorder point", "Suggested order qty", "Lead time (days)", "Supplier"], ctx.head())
    ws.set_row(L0, 32)
    ctx.inv_list = (L0 + 1,)
    for j in range(15):
        r = L0 + 1 + j
        x = r + 1
        ws.write_formula(r, 0, f'=IF(ROWS($A${L0 + 2}:A{x})<=COUNT($AA${f}:$AA${l}),ROWS($A${L0 + 2}:A{x}),"-")', ctx.cell("0", align="center"))
        m = f"MATCH($A{x},$AA${f}:$AA${l},0)"
        pick = lambda col: f'=IFERROR(INDEX(${col}${f}:${col}${l},{m}),"-")'
        ws.write_formula(r, 1, pick("B"), ctx.cell())
        ws.write_formula(r, 2, pick("X"), ctx.cell())
        ws.write_formula(r, 3, pick("Q"), ctx.cell(DEC1, align="right"))
        ws.write_formula(r, 4, pick("E"), ctx.cell(INT, align="right"))
        ws.write_formula(r, 5, pick("F"), ctx.cell(INT, align="right"))
        ws.write_formula(r, 6, pick("G"), ctx.cell(INT, align="right"))
        ws.write_formula(r, 7, pick("O"), ctx.cell(INT, align="right"))
        ws.write_formula(r, 8, pick("Y"), ctx.cell(INT, align="right"))
        ws.write_formula(r, 9, pick("I"), ctx.cell(INT, align="right"))
        ws.write_formula(r, 10, f'=IFERROR(INDEX(Data_Products!$E$2:$E${NS+1},{m}),"-")', ctx.cell())
    ws.conditional_format(L0 + 1, 2, L0 + 15, 2, {"type": "text", "criteria": "containing", "value": "Reorder", "format": ctx.fmt(bg_color=PAL["warn_fill"], font_color=PAL["warn_font"])})
    ws.conditional_format(L0 + 1, 2, L0 + 15, 2, {"type": "text", "criteria": "containing", "value": "Stock-out", "format": ctx.fmt(bg_color=PAL["fail_fill"], font_color=PAL["fail_font"])})
    ws.freeze_panes(M0 + 1, 2)
    ch = ctx.wb.add_chart({"type": "column"})
    ch.add_series({"name": "SKUs by status", "categories": f"=Inventory!$A$6:$A${5+len(sts)}", "values": f"=Inventory!$B$6:$B${5+len(sts)}",
                   "fill": {"color": PAL["teal"]}, "data_labels": {"value": True, "font": {"size": 9}}, "gap": 60})
    ch.set_title({"name": "SKUs by stock status", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_legend({"none": True})
    ch.set_y_axis({"major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 430, "height": 230})
    ws.insert_chart(3, 12, ch, {"x_offset": 10})
