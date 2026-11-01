"""Executive dashboard."""
from __future__ import annotations

from analysis.common import CATEGORIES, CHANNELS
from wb_core import EUR, INT, PAL, PCT, Ctx, absref
from wb_data import REGIONS

KPIS = [
    # label, row key on Calc_Dashboard, number format, kind (money, ratio)
    ("Revenue", "net_revenue", EUR, "money"),
    ("Gross profit", "gross_profit", EUR, "money"),
    ("Gross margin", "gm_pct", PCT, "ratio"),
    ("Contribution margin", "cm_pct", PCT, "ratio"),
    ("Units sold", "units", INT, "money"),
    ("Average discount", "disc_pct", PCT, "ratio"),
]


def build_dashboard(ctx: Ctx) -> None:
    ws = ctx.ws["Dashboard"]
    ws.set_column(0, 0, 2)
    ws.set_column(1, 12, 11.5)
    ws.set_column(13, 13, 2)
    ws.set_row(0, 30)
    ws.merge_range(0, 0, 0, 13, "  Retail operations dashboard", ctx.title())
    ws.merge_range(1, 0, 1, 13, "  Synthetic data for a fictional Finnish retailer, 2023 to 2025. Pick a year, region, channel or category and everything on this page follows.",
                   ctx.fmt(italic=True, font_color=PAL["slate"], bg_color=PAL["light"]))
    lab = ctx.fmt(bold=True, font_color=PAL["navy"], align="right")
    sel = ctx.inp(None, bold=True, align="center")
    ws.set_row(3, 22)
    specs = [(1, "Year", "sel_year", ["All", 2023, 2024, 2025]),
             (4, "Region", "sel_region", ["All"] + REGIONS),
             (7, "Channel", "sel_channel", ["All"] + CHANNELS),
             (10, "Category", "sel_category", ["All"] + CATEGORIES)]
    for col, label, nm, items in specs:
        ws.write(3, col, label, lab)
        ws.merge_range(3, col + 1, 3, col + 2, ctx.sel.get(nm, "All"), sel)
        ws.data_validation(3, col + 1, 3, col + 1, {"validate": "list", "source": [str(i) for i in items]})
        ctx.name(nm, absref("Dashboard", 3, col + 1))
    ws.merge_range(4, 1, 4, 12, "Pick from the yellow drop-downs. Wholesale sales are included unless you choose another channel.", ctx.fmt(italic=True, font_color=PAL["slate"], font_size=9))

    k = ctx.kpi_rows
    card_label = ctx.fmt(bold=True, font_color=PAL["white"], bg_color=PAL["navy"], align="center")
    for i, (label, key, num, kind) in enumerate(KPIS):
        c = 1 + 2 * i
        ws.merge_range(5, c, 5, c + 1, label, card_label)
        row = k[key] + 1
        ws.merge_range(6, c, 6, c + 1, "", ctx.fmt(bold=True, font_size=18, align="center", bg_color=PAL["light"], font_color=PAL["navy"], num_format=num))
        ws.write_formula(6, c, f"=Calc_Dashboard!$B${row}", ctx.fmt(bold=True, font_size=18, align="center", bg_color=PAL["light"], font_color=PAL["navy"], num_format=num))
        row_n = k["net_revenue"] + 1
        if kind == "money":
            chg = '+0.0%;-0.0%;0.0%'
            mom = f'=IF(Calc_Dashboard!$E${row}=0,"n/a",Calc_Dashboard!$D${row}/Calc_Dashboard!$E${row}-1)'
            yoy = f'=IF(Calc_Dashboard!$C${row}=0,"n/a",Calc_Dashboard!$B${row}/Calc_Dashboard!$C${row}-1)'
        else:
            chg = '+0.0%" pts";-0.0%" pts";0.0%" pts"'
            mom = f'=IF(Calc_Dashboard!$E${row_n}=0,"n/a",Calc_Dashboard!$D${row}-Calc_Dashboard!$E${row})'
            yoy = f'=IF(Calc_Dashboard!$C${row_n}=0,"n/a",Calc_Dashboard!$B${row}-Calc_Dashboard!$C${row})'
        left = ctx.fmt(font_size=9, align="right", bg_color=PAL["light"], font_color=PAL["navy"], bold=True, num_format=chg)
        right = ctx.fmt(font_size=9, align="left", bg_color=PAL["light"], font_color=PAL["slate"])
        ws.write_formula(7, c, mom, left)
        ws.write(7, c + 1, " vs last month", right)
        ws.write_formula(8, c, yoy, left)
        ws.write(8, c + 1, " vs year earlier", right)
        ctx.refs[f"kpi_{key}"] = absref("Dashboard", 6, c)
    ws.set_row(6, 34)
    ws.merge_range(9, 1, 9, 12, "", ctx.fmt(font_size=9, font_color=PAL["slate"]))
    ws.write_formula(9, 1, '="Showing "&IF(sel_year="All","all years",sel_year)&", latest month "&MONTH(ref_month)&"/"&YEAR(ref_month)&", region "&sel_region&", channel "&sel_channel&", category "&sel_category&". Contribution margin is after shipping, payment and platform fees and returns."',
                     ctx.fmt(font_size=9, font_color=PAL["slate"]))

    # chart data on Calc_Dashboard
    cd = "Calc_Dashboard"
    t1, t2 = ctx.trend_rows
    c1, c2 = ctx.cat_rows
    h1, h2 = ctx.chan_rows
    s1, s2 = ctx.sku_rows
    top0 = s2 + 4
    wsc = ctx.ws[cd]
    wsc.write(top0 - 1, 0, "Top and bottom five and attention lists", ctx.h1())
    wsc.write_row(top0, 0, ["Rank", "Top product", "Top revenue", "Bottom product", "Bottom revenue", "Margin-drop product", "Margin change", "Margin-drop revenue"], ctx.head())
    for j in range(5):
        r = top0 + 1 + j
        x = r + 1
        rk = j + 1
        wsc.write(r, 0, rk, ctx.cell("0"))
        rng = lambda col: f"${col}${s1+1}:${col}${s2+1}"
        wsc.write_formula(r, 1, f'=IFERROR(INDEX({rng("B")},MATCH($A{x},{rng("E")},0)),"")', ctx.cell())
        wsc.write_formula(r, 2, f'=IFERROR(INDEX({rng("C")},MATCH($A{x},{rng("E")},0)),NA())', ctx.cell(EUR))
        wsc.write_formula(r, 3, f'=IFERROR(INDEX({rng("B")},MATCH($A{x},{rng("F")},0)),"")', ctx.cell())
        wsc.write_formula(r, 4, f'=IFERROR(INDEX({rng("C")},MATCH($A{x},{rng("F")},0)),"")', ctx.cell(EUR))
        wsc.write_formula(r, 5, f'=IFERROR(INDEX({rng("B")},MATCH($A{x},{rng("O")},0)),"")', ctx.cell())
        wsc.write_formula(r, 6, f'=IFERROR(INDEX({rng("M")},MATCH($A{x},{rng("O")},0)),"")', ctx.cell(PCT))
        wsc.write_formula(r, 7, f'=IFERROR(INDEX({rng("G")},MATCH($A{x},{rng("O")},0)),"")', ctx.cell(EUR))
    ctx.top_rows = (top0 + 1, top0 + 5)

    def chart(kind, title, extra=None):
        ch = ctx.wb.add_chart({"type": kind, **(extra or {})})
        ch.set_title({"name": title, "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
        ch.set_legend({"position": "bottom", "font": {"size": 9}})
        ch.set_chartarea({"border": {"color": PAL["line"]}})
        return ch

    cats = f"='{cd}'!$A${t1+1}:$A${t2+1}"
    ch1 = chart("column", "Monthly revenue and gross margin")
    ch1.add_series({"name": "Revenue, reference year", "categories": cats, "values": f"='{cd}'!$B${t1+1}:$B${t2+1}",
                    "fill": {"color": PAL["navy"]}, "gap": 60})
    ch1.add_series({"name": "Revenue, year before", "categories": cats, "values": f"='{cd}'!$C${t1+1}:$C${t2+1}",
                    "fill": {"color": PAL["sky"]}})
    ln = ctx.wb.add_chart({"type": "line"})
    ln.add_series({"name": "Gross margin % (right axis)", "categories": cats, "values": f"='{cd}'!$D${t1+1}:$D${t2+1}",
                   "y2_axis": True, "line": {"color": PAL["amber"], "width": 2.25}})
    ch1.combine(ln)
    ch1.set_y_axis({"num_format": '#,##0', "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}, "num_font": {"size": 9}})
    ln.set_y2_axis({"num_format": "0%", "num_font": {"size": 9}, "min": 0, "max": 1})
    ch1.set_size({"width": 590, "height": 330})
    ws.insert_chart(11, 1, ch1, {"x_offset": 0, "y_offset": 4})

    ch2 = chart("bar", "Gross margin by category")
    ch2.add_series({"name": "Gross margin %", "categories": f"='{cd}'!$A${c1+1}:$A${c2+1}", "values": f"='{cd}'!$D${c1+1}:$D${c2+1}",
                    "fill": {"color": PAL["teal"]},
                    "data_labels": {"value": True, "font": {"size": 9},
                                    "custom": [{"value": f"='{cd}'!$E${r+1}"} for r in range(c1, c2 + 1)]}})
    ch2.set_legend({"none": True})
    ch2.set_x_axis({"num_format": "0%", "min": 0, "max": 1, "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch2.set_y_axis({"reverse": True})
    ch2.set_size({"width": 390, "height": 330})
    ws.insert_chart(11, 8, ch2, {"x_offset": 20, "y_offset": 4})

    ch3 = chart("column", "Gross margin by channel")
    ch3.add_series({"name": "Gross margin %", "categories": f"='{cd}'!$A${h1+1}:$A${h2+1}", "values": f"='{cd}'!$D${h1+1}:$D${h2+1}",
                    "fill": {"color": PAL["teal"]}, "gap": 80,
                    "data_labels": {"value": True, "font": {"size": 9},
                                    "custom": [{"value": f"='{cd}'!$E${r+1}"} for r in range(h1, h2 + 1)]}})
    ch3.set_legend({"none": True})
    ch3.set_y_axis({"num_format": "0%", "min": 0, "max": 1, "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch3.set_size({"width": 400, "height": 300})
    ws.insert_chart(28, 1, ch3, {"y_offset": 6})

    ch4 = chart("bar", "Top five products by revenue")
    ch4.add_series({"name": "Revenue", "categories": f"='{cd}'!$B${top0+2}:$B${top0+6}", "values": f"='{cd}'!$C${top0+2}:$C${top0+6}",
                    "fill": {"color": PAL["navy"]}, "data_labels": {"value": True, "num_format": "#,##0", "font": {"size": 9}}})
    ch4.set_legend({"none": True})
    ch4.set_y_axis({"reverse": True})
    ch4.set_x_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch4.set_size({"width": 570, "height": 300})
    ws.insert_chart(28, 6, ch4, {"x_offset": 16, "y_offset": 6})

    # tables
    head = ctx.head()
    cell = ctx.cell()

    def block(row, col, title, headers, widths):
        ws.merge_range(row, col, row, col + sum(widths) - 1, title, ctx.fmt(bold=True, font_color=PAL["navy"], bottom=1, bottom_color=PAL["navy"]))
        c = col
        for h, w in zip(headers, widths):
            if w > 1:
                ws.merge_range(row + 1, c, row + 1, c + w - 1, h, head)
            else:
                ws.write(row + 1, c, h, head)
            c += w

    def put(row, col, w, formula, fm):
        if w > 1:
            ws.merge_range(row, col, row, col + w - 1, "", fm)
        ws.write_formula(row, col, formula, fm)

    T = 45
    block(T, 1, "Top five products by revenue", ["#", "Product", "Revenue"], [1, 3, 2])
    block(T, 7, "Bottom five products by revenue (with sales)", ["#", "Product", "Revenue"], [1, 3, 2])
    for j in range(5):
        r = T + 2 + j
        src = ctx.top_rows[0] + j + 1
        ws.write(r, 1, j + 1, ctx.cell("0", align="center"))
        put(r, 2, 3, f"=Calc_Dashboard!$B${src}", cell)
        put(r, 5, 2, f"=Calc_Dashboard!$C${src}", ctx.cell(EUR))
        many = f'COUNTIF(Calc_Dashboard!$C${ctx.sku_rows[0]+1}:$C${ctx.sku_rows[1]+1},">0")>=bottom_min'
        ws.write_formula(r, 7, f'=IF({many},{j + 1},"")', ctx.cell("0", align="center"))
        if j == 0:
            note = '"Fewer than " & bottom_min & " products have sales"'
            put(r, 8, 3, f"=IF({many},Calc_Dashboard!$D${src},{note})", cell)
        elif j == 1:
            put(r, 8, 3, f'=IF({many},Calc_Dashboard!$D${src},"so it would repeat the top five.")', cell)
        else:
            put(r, 8, 3, f'=IF({many},Calc_Dashboard!$D${src},"")', cell)
        put(r, 11, 2, f'=IF({many},Calc_Dashboard!$E${src},"")', ctx.cell(EUR))
    A = T + 9
    block(A, 1, "Needs attention: stock (as of the last day of data)", ["#", "Product", "Status"], [1, 3, 2])
    block(A, 7, "Needs attention: biggest margin drops, reference year", ["#", "Product", "Margin change"], [1, 3, 2])
    for j in range(5):
        r = A + 2 + j
        ws.write(r, 1, j + 1, ctx.cell("0", align="center"))
        ws.write(r, 7, j + 1, ctx.cell("0", align="center"))
        il = getattr(ctx, "inv_list", None)
        if il:
            put(r, 2, 3, f'=IFERROR(Inventory!$B${il[0]+1+j},"")', cell)
            put(r, 5, 2, f'=IFERROR(Inventory!$C${il[0]+1+j},"")', cell)
        src = ctx.top_rows[0] + j + 1
        if j == 0:
            put(r, 8, 3, f'=IF(Calc_Dashboard!$F${src}="","No SKU has enough revenue in both years",Calc_Dashboard!$F${src})', cell)
        else:
            put(r, 8, 3, f"=Calc_Dashboard!$F${src}", cell)
        put(r, 11, 2, f"=Calc_Dashboard!$G${src}", ctx.cell(PCT))
    ws.merge_range(A + 8, 1, A + 8, 12, "", ctx.note())
    ws.write_formula(A + 8, 1, '="Workbook checks: "&Checks!$C$4&". The stock lists do not change with the drop-downs because stock is a snapshot at "&DAY(as_of)&"/"&MONTH(as_of)&"/"&YEAR(as_of)&"."', ctx.note())
    ws.freeze_panes(5, 0)
    ws.set_landscape()
    ws.set_paper(9)
    ws.fit_to_pages(1, 1)
    ws.print_area(0, 0, A + 8, 13)
    ws.set_margins(0.4, 0.4, 0.5, 0.5)
    ws.set_footer("&L&8Synthetic data&R&8&P of &N")
