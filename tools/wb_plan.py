"""Forecast and scenario sheets."""
from __future__ import annotations

from xlsxwriter.utility import xl_col_to_name as cn

from analysis.common import CATEGORIES
from wb_core import DEC1, DEC2, EUR, INT, MONTH, PAL, PCT, PCT0, Ctx, absref
from wb_data import DEM_R0, NM, NSKU, SM_C0

NC = len(CATEGORIES)
METHODS = ["Naive (last month)", "Moving average", "Seasonal naive (same month last year)", "Seasonal index with trend"]


def build_forecast(ctx: Ctx) -> None:
    ws = ctx.ws["Forecast"]
    ctx.banner(ws, "Forecast", 12, "Monthly demand by category. Four methods are tested on the last months of data and the best one per category forecasts the next twelve.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 24)
    ws.set_column(1, 1, 30)
    ws.set_column(2, 29, 12)
    ws.set_column(5, 5, 26)
    cats = CATEGORIES
    # anchors (0-based rows)
    R_SEL, R_SUM, R_FC, R_HOLD, R_SEAS, R_LVL, R_DATA, R_GRID, R_CH = 3, 6, 35, 51, 85, 101, 111, 152, 216
    DR1, DR2 = R_DATA + 2, R_DATA + 1 + NM            # excel rows of the data grid
    dcol = lambda j: cn(5 + j)
    drng = lambda j: f"${dcol(j)}${DR1}:${dcol(j)}${DR2}"
    hdr = ctx.head()
    cell = ctx.cell()
    ws.write(R_SEL, 0, "Category shown in the chart", ctx.fmt(bold=True, font_color=PAL["navy"], align="right"))
    ws.write(R_SEL, 1, "Electronics", ctx.inp(None, bold=True, align="center"))
    ws.data_validation(R_SEL, 1, R_SEL, 1, {"validate": "list", "source": cats})
    ctx.name("sel_fc", absref("Forecast", R_SEL, 1))
    ws.merge_range(R_SEL, 2, R_SEL, 10, "Hold-out months, method test and final forecast are all live. Change the assumptions and they follow.", ctx.fmt(italic=True, font_color=PAL["slate"]))

    # ---- data grid
    ws.write(R_DATA - 1, 0, "Monthly demand by category (units sold plus lost units when the assumption says so)", ctx.h1())
    heads = ["Month no", "Month", "Year", "Month of year", "In training window"] + cats + ["All categories"] + \
            [f"Ratio to year, hold-out: {c}" for c in cats] + [f"Ratio to year, final: {c}" for c in cats] + [f"Residual: {c}" for c in cats]
    ws.write_row(R_DATA, 0, heads, hdr)
    ws.set_row(R_DATA, 58)
    for k in range(NM):
        r = R_DATA + 1 + k
        x = r + 1
        ws.write(r, 0, k + 1, ctx.cell("0", align="center"))
        ws.write_formula(r, 1, f"=INDEX(Calc_SkuMonth!$E$4:${cn(SM_C0+NM-1)}$4,A{x})", ctx.cell(MONTH))
        ws.write_formula(r, 2, f"=YEAR(B{x})", ctx.cell("0"))
        ws.write_formula(r, 3, f"=MONTH(B{x})", ctx.cell("0"))
        ws.write_formula(r, 4, f"=IF(A{x}<=n_months-holdout,1,0)", ctx.cell("0"))
        for j in range(NC):
            col = dcol(j)
            ws.write_formula(r, 5 + j, f"=SUMIF(Calc_SkuMonth!$C${DEM_R0+1}:$C${DEM_R0+NSKU},{col}${R_DATA+1},INDEX(Calc_SkuMonth!$E${DEM_R0+1}:${cn(SM_C0+NM-1)}${DEM_R0+NSKU},0,$A{x}))", ctx.cell(INT))
            ws.write_formula(r, 12 + j, (f'=IF(COUNTIFS($C${DR1}:$C${DR2},$C{x},$E${DR1}:$E${DR2},1)=months_year,IF($E{x}=1,{col}{x}/AVERAGEIFS({drng(j)},$C${DR1}:$C${DR2},$C{x},$E${DR1}:$E${DR2},1),""),"")'), ctx.cell(DEC2))
            ws.write_formula(r, 18 + j, f'=IF(COUNTIFS($C${DR1}:$C${DR2},$C{x})=months_year,{col}{x}/AVERAGEIFS({drng(j)},$C${DR1}:$C${DR2},$C{x}),"")', ctx.cell(DEC2))
            seas_final = f"${cn(8+j)}${R_SEAS+2}:${cn(8+j)}${R_SEAS+13}"
            ws.write_formula(r, 24 + j, f'=IF({cn(18+j)}{x}="","",{cn(18+j)}{x}/INDEX({seas_final},$D{x})-1)', ctx.cell(PCT))
        ws.write_formula(r, 11, f"=SUM(F{x}:K{x})", ctx.cell(INT))

    # ---- seasonal indexes
    ws.write(R_SEAS - 1, 0, "Seasonal index by calendar month: hold-out version (left) and final version (right). Complete calendar years only.", ctx.h1())
    ws.write(R_SEAS, 0, "Month of year", hdr)
    for j, c in enumerate(cats):
        ws.write(R_SEAS, 1 + j, c, hdr)
        ws.write(R_SEAS, 8 + j, c, hdr)
    ws.set_row(R_SEAS, 32)
    for m in range(12):
        r = R_SEAS + 1 + m
        x = r + 1
        ws.write(r, 0, m + 1, ctx.cell("0", align="center"))
        for j in range(NC):
            ws.write_formula(r, 1 + j, f"=IFERROR(AVERAGEIFS({cn(12+j)}${DR1}:{cn(12+j)}${DR2},$D${DR1}:$D${DR2},$A{x}),1)", ctx.cell(DEC2))
            ws.write_formula(r, 8 + j, f"=IFERROR(AVERAGEIFS({cn(18+j)}${DR1}:{cn(18+j)}${DR2},$D${DR1}:$D${DR2},$A{x}),1)", ctx.cell(DEC2))

    # ---- level and trend
    ws.write(R_LVL - 1, 0, "Level and yearly growth used by the seasonal index method", ctx.h1())
    ws.write_row(R_LVL, 0, ["Category", "Level, hold-out", "Growth, hold-out", "Level, final", "Growth, final", "Residual spread", "Band factor"], hdr)
    ws.set_row(R_LVL, 32)
    for j, c in enumerate(cats):
        r = R_LVL + 1 + j
        x = r + 1
        rng = drng(j)
        ws.write(r, 0, c, cell)
        ws.write_formula(r, 1, f"=AVERAGE(INDEX({rng},n_months-holdout-months_year+1):INDEX({rng},n_months-holdout))", ctx.cell(DEC1))
        ws.write_formula(r, 2, f"=B{x}/AVERAGE(INDEX({rng},n_months-holdout-months_year-months_year+1):INDEX({rng},n_months-holdout-months_year))", ctx.cell(DEC2))
        ws.write_formula(r, 3, f"=AVERAGE(INDEX({rng},n_months-months_year+1):INDEX({rng},n_months))", ctx.cell(DEC1))
        ws.write_formula(r, 4, f"=D{x}/AVERAGE(INDEX({rng},n_months-months_year-months_year+1):INDEX({rng},n_months-months_year))", ctx.cell(DEC2))
        ws.write_formula(r, 5, f"=STDEV.S({cn(24+j)}${DR1}:{cn(24+j)}${DR2})", ctx.cell(PCT))
        ws.write_formula(r, 6, f"=NORM.S.INV((1+band_conf)/2)*F{x}", ctx.cell(PCT))

    # ---- hold-out test
    ws.write(R_HOLD - 1, 0, "Hold-out test: each method forecasts the held-back months from the data before them", ctx.h1())
    ws.write_row(R_HOLD, 0, ["Category", "Series"] + [None] * 6 + ["Sum of absolute errors", "WAPE", "MAPE"], hdr)
    for h in range(6):
        ws.write(R_HOLD, 2 + h, h + 1, hdr)
    ws.set_row(R_HOLD, 32)
    series = ["Actual"] + METHODS
    cut = "(n_months-holdout)"
    for j, c in enumerate(cats):
        rng = drng(j)
        base = R_HOLD + 1 + 5 * j
        lvl = R_LVL + 2 + j
        seas = f"${cn(1+j)}${R_SEAS+2}:${cn(1+j)}${R_SEAS+13}"
        for s, name in enumerate(series):
            r = base + s
            x = r + 1
            ws.write(r, 0, c if s == 0 else "", cell)
            ws.write(r, 1, name, ctx.cell(bold=(s == 0)))
            for h in range(6):
                hc = f"{cn(2+h)}${R_HOLD+1}"
                if s == 0:
                    f = f"=IF({hc}<=holdout,INDEX({rng},{cut}+{hc}),0)"
                elif s == 1:
                    f = f"=IF({hc}<=holdout,INDEX({rng},{cut}),0)"
                elif s == 2:
                    f = f"=IF({hc}<=holdout,AVERAGE(INDEX({rng},{cut}-ma_months+1):INDEX({rng},{cut})),0)"
                elif s == 3:
                    f = f"=IF({hc}<=holdout,INDEX({rng},{cut}+{hc}-months_year),0)"
                else:
                    f = (f"=IF({hc}<=holdout,$B${lvl}*$C${lvl}^(({hc}+(months_year-1)/2)/months_year)"
                         f"*INDEX({seas},MOD(INDEX($D${DR1}:$D${DR2},{cut})+{hc}-1,months_year)+1),0)")
                ws.write_formula(r, 2 + h, f, ctx.cell(DEC1))
            if s > 0:
                a = f"$C${base+1}:$H${base+1}"
                m_ = f"$C{x}:$H{x}"
                ws.write_formula(r, 8, f"=SUMPRODUCT(ABS({a}-{m_}))", ctx.cell(DEC1))
                ws.write_formula(r, 9, f"=IFERROR(I{x}/SUM({a}),0)", ctx.cell(PCT))
                ws.write_formula(r, 10, f"=SUMPRODUCT(ABS({a}-{m_})/({a}+({a}=0)))/holdout", ctx.cell(PCT))

    # ---- summary and best method
    ws.write(R_SUM - 1, 0, "Which method forecasts best? WAPE on the held-back months (lower is better)", ctx.h1())
    ws.write_row(R_SUM, 0, ["Category"] + [m.split(" (")[0] for m in METHODS] + ["Best method", "Best method no", "Best WAPE", "Best MAPE"], hdr)
    ws.set_row(R_SUM, 32)
    for j, c in enumerate(cats):
        r = R_SUM + 1 + j
        x = r + 1
        base = R_HOLD + 1 + 5 * j
        ws.write(r, 0, c, cell)
        for m_ in range(4):
            ws.write_formula(r, 1 + m_, f"=J{base+2+m_}", ctx.cell(PCT))
        ws.write_formula(r, 5, f"=INDEX($B${R_SUM+1}:$E${R_SUM+1},G{x})", ctx.cell(bold=True))
        ws.write_formula(r, 6, f"=MATCH(MIN(B{x}:E{x}),B{x}:E{x},0)", ctx.cell("0", align="center"))
        ws.write_formula(r, 7, f"=MIN(B{x}:E{x})", ctx.cell(PCT))
        ws.write_formula(r, 8, f"=INDEX(K{base+2}:K{base+5},G{x})", ctx.cell(PCT))
    ws.conditional_format(R_SUM + 1, 1, R_SUM + NC, 4, {"type": "formula", "criteria": f"=B{R_SUM+2}=MIN($B{R_SUM+2}:$E{R_SUM+2})", "format": ctx.fmt(bold=True, bg_color=PAL["pass_fill"], font_color=PAL["pass_font"])})
    ctx.refs["fc_best_first"] = absref("Forecast", R_SUM + 1, 5)

    # ---- method grids (12 months ahead)
    G0 = [R_GRID + 15 * i for i in range(4)]
    for gi, g0 in enumerate(G0):
        ws.write(g0 - 1, 0, f"Next 12 months: {METHODS[gi]}", ctx.h1())
        ws.write_row(g0, 0, ["Month ahead", "Month"] + cats, hdr)
        ws.set_row(g0, 32)
        for h in range(12):
            r = g0 + 1 + h
            x = r + 1
            ws.write(r, 0, h + 1, ctx.cell("0", align="center"))
            ws.write_formula(r, 1, f"=EDATE(first_month,n_months+A{x}-1)", ctx.cell(MONTH))
            for j in range(NC):
                rng = drng(j)
                fin = R_LVL + 2 + j
                seas = f"${cn(8+j)}${R_SEAS+2}:${cn(8+j)}${R_SEAS+13}"
                if gi == 0:
                    f = f"=INDEX({rng},n_months)"
                elif gi == 1:
                    f = f"=AVERAGE(INDEX({rng},n_months-ma_months+1):INDEX({rng},n_months))"
                elif gi == 2:
                    f = f"=INDEX({rng},n_months+$A{x}-months_year)"
                else:
                    f = (f"=$D${fin}*$E${fin}^(($A{x}+(months_year-1)/2)/months_year)"
                         f"*INDEX({seas},MOD(INDEX($D${DR1}:$D${DR2},n_months)+$A{x}-1,months_year)+1)")
                ws.write_formula(r, 2 + j, f, ctx.cell(DEC1))

    # ---- selected forecast table
    ws.write(R_FC - 1, 0, "Forecast for the next 12 months, best method per category (units)", ctx.h1())
    ws.write_row(R_FC, 0, ["Month ahead", "Month"] + cats + ["All categories"], hdr)
    ws.set_row(R_FC, 32)
    for h in range(12):
        r = R_FC + 1 + h
        x = r + 1
        ws.write(r, 0, h + 1, ctx.cell("0", align="center"))
        ws.write_formula(r, 1, f"=EDATE(first_month,n_months+A{x}-1)", ctx.cell(MONTH))
        for j in range(NC):
            ref = lambda gi: f"{cn(2+j)}{G0[gi]+2+h}"
            idx = f"$G${R_SUM+2+j}"
            ws.write_formula(r, 2 + j, f"=CHOOSE({idx},{ref(0)},{ref(1)},{ref(2)},{ref(3)})", ctx.cell(DEC1))
        ws.write_formula(r, 2 + NC, f"=SUM(C{x}:{cn(1+NC)}{x})", ctx.cell(DEC1, bold=True))
    r = R_FC + 13
    ws.write(r, 1, "Total", ctx.cell(bold=True))
    for j in range(NC + 1):
        ws.write_formula(r, 2 + j, f"=SUM({cn(2+j)}{R_FC+2}:{cn(2+j)}{R_FC+13})", ctx.cell(INT, bold=True))
    ctx.refs["fc_total_next12"] = absref("Forecast", r, 2 + NC)
    ctx.refs["fc_first_cell"] = absref("Forecast", R_FC + 1, 2)

    # ---- chart data and chart
    ws.write(R_CH - 1, 0, "Chart data for the selected category", ctx.h1())
    ws.write_row(R_CH, 0, ["Month no", "Month", "Actual", "Forecast", "Lower band", "Upper band"], hdr)
    catpos = f"MATCH(sel_fc,$F${R_DATA+1}:$K${R_DATA+1},0)"
    for k in range(NM + 12):
        r = R_CH + 1 + k
        x = r + 1
        ws.write(r, 0, k + 1, ctx.cell("0", align="center"))
        if k < NM:
            ws.write_formula(r, 1, f"=INDEX($B${DR1}:$B${DR2},A{x})", ctx.cell(MONTH))
            ws.write_formula(r, 2, f"=INDEX($F${DR1}:$K${DR2},A{x},{catpos})", ctx.cell(INT))
            ws.write_formula(r, 3, f"=C{x}" if k == NM - 1 else "=NA()", ctx.cell(INT))
            ws.write_formula(r, 4, f"=C{x}" if k == NM - 1 else "=NA()", ctx.cell(INT))
            ws.write_formula(r, 5, f"=C{x}" if k == NM - 1 else "=NA()", ctx.cell(INT))
        else:
            h = k - NM
            ws.write_formula(r, 1, f"=EDATE(first_month,A{x}-1)", ctx.cell(MONTH))
            ws.write_formula(r, 2, "=NA()", ctx.cell(INT))
            ws.write_formula(r, 3, f"=INDEX($C${R_FC+2+h}:$H${R_FC+2+h},{catpos})", ctx.cell(INT))
            fac = f"INDEX($G${R_LVL+2}:$G${R_LVL+1+NC},{catpos})"
            ws.write_formula(r, 4, f"=D{x}*(1-{fac})", ctx.cell(INT))
            ws.write_formula(r, 5, f"=D{x}*(1+{fac})", ctx.cell(INT))
    c0, c1 = R_CH + 2, R_CH + 1 + NM + 12
    ch = ctx.wb.add_chart({"type": "line"})
    for nm_, col, color, w, dash in [("Actual demand", 2, PAL["navy"], 2.25, "solid"), ("Forecast", 3, PAL["teal"], 2.25, "solid"),
                                     ("Lower band", 4, PAL["sky"], 1.25, "dash"), ("Upper band", 5, PAL["sky"], 1.25, "dash")]:
        ch.add_series({"name": nm_, "categories": f"=Forecast!$B${c0}:$B${c1}", "values": f"=Forecast!${cn(col)}${c0}:${cn(col)}${c1}",
                       "line": {"color": color, "width": w, "dash_type": dash}})
    ch.set_title({"name": "Monthly demand and forecast (selected category)", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_x_axis({"num_format": "mmm yy", "num_font": {"size": 9, "rotation": -45}, "interval_unit": 3, "date_axis": False})
    ch.set_y_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ch.set_legend({"position": "bottom", "font": {"size": 9}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 880, "height": 330})
    ws.insert_chart(R_SUM + 8, 0, ch, {"x_offset": 4, "y_offset": 4})
    ctx.fc = dict(R_SUM=R_SUM, R_HOLD=R_HOLD, R_FC=R_FC, R_DATA=R_DATA, R_LVL=R_LVL, R_SEAS=R_SEAS, G0=G0, R_CH=R_CH)
    ctx.refs["fc_hold_actual_first"] = absref("Forecast", R_HOLD + 1, 2)


SCN = [
    # name, price change, promo discount, share of year on promotion, demand shock, delay days, description
    ("Base", 0.0, 0.0, 0.0, 0.0, 0, "Last twelve months repeated."),
    ("Price change", 0.05, 0.0, 0.0, 0.0, 0, "List prices rise 5%. Volume follows each category's elasticity."),
    ("Promotion", 0.0, 0.15, 0.25, 0.0, 0, "A 15% discount on a quarter of the year."),
    ("Supplier delay", 0.0, 0.0, 0.0, 0.0, 14, "Every supplier takes 14 days longer."),
    ("Demand shock", 0.0, 0.0, 0.0, -0.15, 0, "Demand falls 15% in every category."),
]


def build_scenarios(ctx: Ctx) -> None:
    ws = ctx.ws["Scenarios"]
    ctx.banner(ws, "Scenarios and sensitivity", 14, "Pick a scenario. Revenue, margin and stock-out risk are recomputed from the last twelve months and the current stock position.")
    ctx.back_link(ws)
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 28)
    ws.set_column(2, 14, 14)
    hdr = ctx.head()
    cell = ctx.cell()
    ws.write(3, 0, "Scenario", ctx.fmt(bold=True, font_color=PAL["navy"], align="right"))
    ws.merge_range(3, 1, 3, 2, "Base", ctx.inp(None, bold=True, align="center"))
    ws.data_validation(3, 1, 3, 1, {"validate": "list", "source": [s[0] for s in SCN]})
    ctx.name("sel_scn", absref("Scenarios", 3, 1))

    A0 = 6
    ws.write(A0 - 1, 0, "Assumptions by scenario (blue cells are inputs)", ctx.h1())
    ws.write_row(A0, 0, ["Scenario", "Price change", "Promotion discount", "Share of year on promotion", "Demand shock", "Supplier delay (days)", "What it means"], hdr)
    ws.set_row(A0, 32)
    for i, (n, dp, dd, ds, sh, dl, desc) in enumerate(SCN):
        r = A0 + 1 + i
        ws.write(r, 0, n, cell)
        ws.write(r, 1, dp, ctx.inp(PCT))
        ws.write(r, 2, dd, ctx.inp(PCT))
        ws.write(r, 3, ds, ctx.inp(PCT))
        ws.write(r, 4, sh, ctx.inp(PCT))
        ws.write(r, 5, dl, ctx.inp(INT))
        ws.merge_range(r, 6, r, 12, desc, cell)
    ws.merge_range(A0 + 6, 0, A0 + 6, 6, "Elasticity is taken from the Promotions sheet (or the override on the Assumptions sheet).", ctx.fmt(italic=True, font_color=PAL["slate"]))
    SA = A0 + 2                      # excel row of the first scenario
    P = lambda col, i: f"${col}${SA + i}"

    # category block
    C0 = A0 + 9
    ws.write(C0 - 1, 0, "Base year by category (trailing window)", ctx.h1())
    ws.write_row(C0, 0, ["Category", "Units", "Revenue", "Cost of goods", "Net price per unit", "Cost per unit", "Elasticity"], hdr)
    ws.set_row(C0, 32)
    cs = "Calc_Sku"
    for j, c in enumerate(CATEGORIES):
        r = C0 + 1 + j
        x = r + 1
        ws.write(r, 0, c, cell)
        ws.write_formula(r, 1, f"=SUMIF({cs}!$C$5:$C${4+NSKU},$A{x},{cs}!$F$5:$F${4+NSKU})", ctx.cell(INT))
        ws.write_formula(r, 2, f"=SUMIF({cs}!$C$5:$C${4+NSKU},$A{x},{cs}!$D$5:$D${4+NSKU})", ctx.cell(EUR))
        ws.write_formula(r, 3, f"=SUMIF({cs}!$C$5:$C${4+NSKU},$A{x},{cs}!$E$5:$E${4+NSKU})", ctx.cell(EUR))
        ws.write_formula(r, 4, f"=C{x}/B{x}", ctx.cell(DEC2))
        ws.write_formula(r, 5, f"=D{x}/B{x}", ctx.cell(DEC2))
        ws.write_formula(r, 6, f"=INDEX(el_used,{j+1})", ctx.cell(DEC2))
    c1, c2 = C0 + 2, C0 + 1 + NC
    U, E, PP, CC = f"$B${c1}:$B${c2}", f"$G${c1}:$G${c2}", f"$E${c1}:$E${c2}", f"$F${c1}:$F${c2}"

    # SKU block
    K0 = C0 + NC + 14
    ws.write(K0 - 1, 0, "Stock-out risk by SKU: chance that stock on hand and on order does not cover demand over lead time plus review period", ctx.h1())
    heads = ["SKU", "Product", "Category", "Active (1 yes)", "Stock position", "Demand per day", "SD daily demand", "Lead time", "Lead time SD", "Revenue (window)", "Elasticity"]
    for s in SCN:
        heads += [f"Demand multiplier: {s[0]}", f"Risk: {s[0]}"]
    ws.write_row(K0, 0, heads, hdr)
    ws.set_row(K0, 58)
    k1, k2 = K0 + 2, K0 + 1 + NSKU
    im = ctx.inv_main[0]
    for i in range(NSKU):
        r = K0 + 1 + i
        x = r + 1
        ir = im + 1 + i
        ws.write_formula(r, 0, f"=Inventory!$A${ir}", cell)
        ws.write_formula(r, 1, f"=Inventory!$B${ir}", cell)
        ws.write_formula(r, 2, f"=Inventory!$C${ir}", cell)
        ws.write_formula(r, 3, f'=IF(AND(Inventory!$X${ir}<>"Obsolete stock",Inventory!$X${ir}<>"Discontinued",Inventory!$L${ir}>0),1,0)', ctx.cell("0"))
        ws.write_formula(r, 4, f"=Inventory!$G${ir}", ctx.cell(INT))
        ws.write_formula(r, 5, f"=Inventory!$L${ir}", ctx.cell(DEC2))
        ws.write_formula(r, 6, f"=Inventory!$M${ir}", ctx.cell(DEC2))
        ws.write_formula(r, 7, f"=Inventory!$I${ir}", ctx.cell(INT))
        ws.write_formula(r, 8, f"=Inventory!$J${ir}", ctx.cell(DEC1))
        ws.write_formula(r, 9, f"={cs}!$D${5+i}", ctx.cell(EUR))
        ws.write_formula(r, 10, f"=INDEX($G${c1}:$G${c2},MATCH($C{x},$A${c1}:$A${c2},0))", ctx.cell(DEC2))
        for si in range(len(SCN)):
            mcol, rcol = 11 + 2 * si, 12 + 2 * si
            phi = f"((1+{P('B', si)})*(1-{P('C', si)}*{P('D', si)}))"
            ws.write_formula(r, mcol, f"=(1+{P('E', si)})*{phi}^(-$K{x})", ctx.cell(DEC2))
            m = f"{cn(mcol)}{x}"
            lt = f"($H{x}+{P('F', si)}+review_days)"
            ws.write_formula(r, rcol, (f"=IF($D{x}=1,1-NORM.S.DIST(($E{x}-$F{x}*{m}*{lt})/SQRT({lt}*($G{x}*{m})^2+($F{x}*{m}*$I{x})^2),TRUE),0)"), ctx.cell(PCT))

    # comparison
    S0 = C0 + NC + 3
    ws.write(S0 - 1, 0, "All scenarios side by side", ctx.h1())
    ws.write_row(S0, 0, ["Scenario", "Revenue", "Gross profit", "Gross margin %", "Revenue vs base", "Gross profit vs base", "Stock-out risk (revenue-weighted)", "SKUs above the risk limit"], hdr)
    ws.set_row(S0, 44)
    for si, s in enumerate(SCN):
        r = S0 + 1 + si
        x = r + 1
        phi = f"((1+{P('B', si)})*(1-{P('C', si)}*{P('D', si)}))"
        units = f"{U}*(1+{P('E', si)})*{phi}^(-{E})"
        ws.write(r, 0, s[0], cell)
        ws.write_formula(r, 1, f"=SUMPRODUCT({units}*{PP}*{phi})", ctx.cell(EUR))
        ws.write_formula(r, 2, f"=B{x}-SUMPRODUCT({units}*{CC})", ctx.cell(EUR))
        ws.write_formula(r, 3, f"=IFERROR(C{x}/B{x},0)", ctx.cell(PCT))
        ws.write_formula(r, 4, f"=B{x}/$B${S0+2}-1", ctx.cell("+0.0%;-0.0%;0.0%"))
        ws.write_formula(r, 5, f"=C{x}/$C${S0+2}-1", ctx.cell("+0.0%;-0.0%;0.0%"))
        rk = f"${cn(12+2*si)}${k1}:${cn(12+2*si)}${k2}"
        wt = f"$J${k1}:$J${k2}"
        ws.write_formula(r, 6, f"=SUMPRODUCT({rk},{wt},$D${k1}:$D${k2})/SUMPRODUCT({wt},$D${k1}:$D${k2})", ctx.cell(PCT))
        ws.write_formula(r, 7, f'=COUNTIF({rk},">"&risk_cut)', ctx.cell(INT))
    ws.conditional_format(S0 + 1, 0, S0 + len(SCN), 7, {"type": "formula", "criteria": f"=$A{S0+2}=sel_scn", "format": ctx.fmt(bold=True, bg_color=PAL["mid"])})
    ctx.refs["scn_base_rev"] = absref("Scenarios", S0 + 1, 1)
    ctx.refs["scn_cat_rev_sum"] = f"SUM(Scenarios!$C${c1}:$C${c2})"
    # selected scenario cards
    ws.write(3, 4, "Selected scenario", ctx.fmt(bold=True, font_color=PAL["navy"], align="right"))
    cards = [("Revenue", 1, EUR), ("Gross profit", 2, EUR), ("Gross margin", 3, PCT), ("Stock-out risk", 6, PCT), ("SKUs above limit", 7, INT)]
    for i, (lab, col, num) in enumerate(cards):
        ws.write(2, 5 + i, lab, ctx.fmt(bold=True, font_color=PAL["white"], bg_color=PAL["navy"], align="center"))
        ws.write_formula(3, 5 + i, f"=INDEX({cn(col)}${S0+2}:{cn(col)}${S0+1+len(SCN)},MATCH(sel_scn,$A${S0+2}:$A${S0+1+len(SCN)},0))",
                         ctx.fmt(bold=True, font_size=12, align="center", bg_color=PAL["light"], font_color=PAL["navy"], num_format=num))
    ctx.refs["scn_sel_rev"] = absref("Scenarios", 3, 5)

    # chart
    ch = ctx.wb.add_chart({"type": "column"})
    cats = f"=Scenarios!$A${S0+2}:$A${S0+1+len(SCN)}"
    ch.add_series({"name": "Revenue", "categories": cats, "values": f"=Scenarios!$B${S0+2}:$B${S0+1+len(SCN)}", "fill": {"color": PAL["navy"]}, "gap": 60})
    ch.add_series({"name": "Gross profit", "categories": cats, "values": f"=Scenarios!$C${S0+2}:$C${S0+1+len(SCN)}", "fill": {"color": PAL["teal"]}})
    ln = ctx.wb.add_chart({"type": "line"})
    ln.add_series({"name": "Stock-out risk (right axis)", "categories": cats, "values": f"=Scenarios!$G${S0+2}:$G${S0+1+len(SCN)}", "y2_axis": True,
                   "line": {"color": PAL["amber"], "width": 2.25}, "marker": {"type": "circle", "size": 7, "fill": {"color": PAL["amber"]}, "border": {"color": PAL["amber"]}}})
    ch.combine(ln)
    ch.set_title({"name": "Scenarios compared", "name_font": {"size": 11, "bold": True, "color": PAL["navy"]}})
    ch.set_y_axis({"num_format": "#,##0", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EE"}}})
    ln.set_y2_axis({"num_format": "0%", "min": 0})
    ch.set_legend({"position": "bottom", "font": {"size": 9}})
    ch.set_chartarea({"border": {"color": PAL["line"]}})
    ch.set_size({"width": 520, "height": 300})
    ws.insert_chart(C0 - 1, 8, ch)

    # sensitivity grid
    Z0 = K0 + NSKU + 4
    ws.write(Z0 - 1, 0, "Sensitivity: yearly gross profit for a price change (down) and a demand shock (across)", ctx.h1())
    ws.write(Z0, 0, "Built with explicit formulas, not an Excel Data Table. Edit the blue headers to try other steps.", ctx.note())
    shocks = [-0.20, -0.10, 0.0, 0.10, 0.20]
    prices = [-0.10, -0.05, 0.0, 0.05, 0.10]
    for gi, (title, kind) in enumerate([("Gross profit", "gp"), ("Change against the no-change cell", "chg")]):
        top = Z0 + 2 + gi * 9
        ws.write(top, 0, title, ctx.h1())
        ws.write(top + 1, 0, "Price change \\ Demand shock", hdr)
        for j, sv in enumerate(shocks):
            if gi == 0:
                ws.write(top + 1, 1 + j, sv, ctx.inp(PCT0, bold=True))
            else:
                ws.write_formula(top + 1, 1 + j, f"={cn(1+j)}{Z0+2+2}", ctx.cell(PCT0, bold=True, bg_color=PAL["mid"]))
        for i, pv in enumerate(prices):
            r = top + 2 + i
            x = r + 1
            if gi == 0:
                ws.write(r, 0, pv, ctx.inp(PCT0, bold=True, align="left"))
            else:
                ws.write_formula(r, 0, f"=A{Z0+5+i}", ctx.cell(PCT0, bold=True, bg_color=PAL["mid"], align="left"))
            for j in range(len(shocks)):
                hd = f"{cn(1+j)}${top+2}"
                if gi == 0:
                    f = f"=SUMPRODUCT({U}*(1+{hd})*(1+$A{x})^(-{E})*({PP}*(1+$A{x})-{CC}))"
                    ws.write_formula(r, 1 + j, f, ctx.cell(EUR))
                else:
                    src = f"{cn(1+j)}{Z0+5+i}"
                    base = f"$D${Z0+7}"
                    ws.write_formula(r, 1 + j, f"={src}/{base}-1", ctx.cell("+0.0%;-0.0%;0.0%"))
    ws.conditional_format(Z0 + 4, 1, Z0 + 8, 5, {"type": "3_color_scale", "min_color": "#F2D9D9", "mid_color": "#FFFFFF", "max_color": "#D3E6DA"})
    ws.conditional_format(Z0 + 13, 1, Z0 + 17, 5, {"type": "3_color_scale", "min_color": "#F2D9D9", "mid_color": "#FFFFFF", "max_color": "#D3E6DA"})
    ctx.refs["sens_centre"] = absref("Scenarios", Z0 + 6, 3)
    ctx.scn = dict(S0=S0, C0=C0, K0=K0, Z0=Z0)
    ws.freeze_panes(5, 1)
