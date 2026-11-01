"""Recalculate the workbook headlessly and compare it with the pandas calculations.

    python tools/verify_workbook.py

Needs LibreOffice. The workbook is built twice, once with every drop-down on All and once
with a narrow selection, so that the filters are tested too. Each build is recalculated by
LibreOffice (soffice --headless --convert-to xlsx), read back with openpyxl and compared with
analysis/metrics.py. Every comparison, with its tolerance, goes to outputs/workbook_parity.csv.
Takes a few minutes.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import openpyxl  # noqa: E402
import pandas as pd  # noqa: E402

import build_workbook  # noqa: E402
from analysis import common, metrics as M  # noqa: E402
from analysis.common import CATEGORIES, CHANNELS  # noqa: E402

import lo  # noqa: E402

METHOD_KEY = {"Naive": "naive", "Moving average": "ma", "Seasonal naive": "snaive", "Seasonal index with trend": "index"}


class Compare:
    def __init__(self, label: str):
        self.label = label
        self.rows: list[dict] = []

    def num(self, name, wb, pd_val, tol=0.01, rel=False):
        w = float("nan") if wb in (None, "") else float(wb)
        p = float(pd_val)
        diff = abs(w - p)
        lim = tol * max(1.0, abs(p)) if rel else tol
        self.rows.append(dict(run=self.label, figure=name, workbook=w, pandas=p, difference=diff, tolerance=lim,
                              passed=bool(diff <= lim)))

    def text(self, name, wb, pd_val):
        self.rows.append(dict(run=self.label, figure=name, workbook=wb, pandas=pd_val, difference=0 if wb == pd_val else 1,
                              tolerance=0, passed=bool(wb == pd_val)))


def verify(label: str, selections: dict, data: dict, t: dict, monthly: pd.DataFrame, full: bool, tmp: Path) -> list[dict]:
    path = tmp / f"{label}.xlsx"
    ctx = build_workbook.build(path, selections, data)
    out = lo.recalc(path, tmp)
    wb = openpyxl.load_workbook(out, data_only=True)
    V = lambda sh, r, c: wb[sh].cell(row=r + 1, column=c + 1).value
    C = Compare(label)
    y, rg, ch, ct = selections.get("sel_year", "All"), selections.get("sel_region", "All"), selections.get("sel_channel", "All"), selections.get("sel_category", "All")
    K = M.kpi_block(monthly, y, rg, ch, ct)
    kr = ctx.kpi_rows
    keys = ["units", "net_revenue", "gross_profit", "contribution", "gm_pct", "cm_pct", "disc_pct"]
    for k in keys:
        C.num(f"Dashboard {k}, selected period", V("Calc_Dashboard", kr[k], 1), K[f"cur_{k}"], 0.005 if "pct" in k else 0.01)
        C.num(f"Dashboard {k}, latest month", V("Calc_Dashboard", kr[k], 3), K[f"mom_{k}"], 0.005 if "pct" in k else 0.01)
        C.num(f"Dashboard {k}, month before", V("Calc_Dashboard", kr[k], 4), K[f"prevmonth_{k}"], 0.005 if "pct" in k else 0.01)
        if f"prior_{k}" in K:
            C.num(f"Dashboard {k}, a year earlier", V("Calc_Dashboard", kr[k], 2), K[f"prior_{k}"], 0.005 if "pct" in k else 0.01)
    # P&L on Profit_Margin
    pl = ctx.pl_rows
    cur = M.pnl(M.filter_monthly(monthly, y, rg, ch, ct))
    for key, sign in [("list_value", 1), ("discount_value", -1), ("net_revenue", 1), ("cogs", -1), ("gross_profit", 1), ("shipping", -1),
                      ("payment_fee", -1), ("platform_fee", -1), ("refund_amount", -1), ("restock_cogs", 1), ("return_shipping", -1), ("contribution", 1)]:
        C.num(f"Profit and loss: {key}", V("Profit_Margin", pl[key], 1), sign * cur[key])
    # trend, category, channel
    ref_year = monthly.year.max() if y == "All" else int(y)
    t1, _ = ctx.trend_rows
    for mth in range(12):
        x = M.filter_monthly(monthly, ref_year, rg, ch, ct)
        C.num(f"Trend revenue {ref_year}-{mth+1:02d}", V("Calc_Dashboard", t1 + mth, 1), x[x.month_no == mth + 1].net_revenue.sum())
        xp = M.filter_monthly(monthly, ref_year - 1, rg, ch, ct)
        C.num(f"Trend revenue {ref_year-1}-{mth+1:02d}", V("Calc_Dashboard", t1 + mth, 2), xp[xp.month_no == mth + 1].net_revenue.sum())
    base = M.filter_monthly(monthly, y, rg, ch, ct)
    for i, c in enumerate(CATEGORIES):
        b = base[base.category == c]
        gm = 1 - b.cogs.sum() / b.net_revenue.sum() if b.net_revenue.sum() else 0
        if b.net_revenue.sum() == 0:
            C.text(f"Gross margin, category {c} (no sales)", V("Calc_Dashboard", ctx.cat_rows[0] + i, 3), "#N/A")
        else:
            C.num(f"Gross margin, category {c}", V("Calc_Dashboard", ctx.cat_rows[0] + i, 3), gm, 0.0005)
    for i, c in enumerate(CHANNELS):
        b = base[base.channel == c]
        gm = 1 - b.cogs.sum() / b.net_revenue.sum() if b.net_revenue.sum() else 0
        if b.net_revenue.sum() == 0:
            C.text(f"Gross margin, channel {c} (no sales)", V("Calc_Dashboard", ctx.chan_rows[0] + i, 3), "#N/A")
        else:
            C.num(f"Gross margin, channel {c}", V("Calc_Dashboard", ctx.chan_rows[0] + i, 3), gm, 0.0005)
    sku_rev = base.groupby("sku").net_revenue.sum()
    s1, _ = ctx.sku_rows
    for i, sku in enumerate(sorted(monthly.sku.unique())):
        C.num(f"Revenue by SKU {sku}", V("Calc_Dashboard", s1 + i, 2), sku_rev.get(sku, 0.0))
    # bridge
    yb = ref_year
    br = M.bridge(monthly, yb - 1, yb, rg, ch, ct)
    s0 = ctx.bridge_s0
    for i, k in enumerate(["cm_a", "volume", "mix", "price", "discount", "cost", "fees", "returns", "cm_b"]):
        C.num(f"Margin bridge: {k}", V("Profit_Margin", s0 + 1 + i, 1), br[k])
    # checks sheet
    first, last = ctx.checks_range
    fails = [V("Checks", r, 1) for r in range(first, last) if V("Checks", r, 5) != "PASS"]
    C.rows.append(dict(run=label, figure=f"Checks sheet: {last - first} checks, failures: {fails or 'none'}", workbook=len(fails), pandas=0,
                       difference=len(fails), tolerance=0, passed=not fails))
    if not full:
        return C.rows

    # ---- ABC, XYZ, inventory
    inv = M.inventory_rules(t, monthly)
    skus = list(inv.index)
    m0 = ctx.inv_main[0]
    for i, sku in enumerate(skus):
        r = inv.loc[sku]
        cs = 4 + i
        C.num(f"ABC revenue {sku}", V("Calc_Sku", cs, 3), r.rev)
        C.num(f"Revenue rank {sku}", V("Calc_Sku", cs, 8), r["rank"], 0)
        C.text(f"ABC class {sku}", V("Calc_Sku", cs, 13), r.abc)
        C.num(f"CV of demand {sku}", V("Calc_Sku", cs, 9), r.cv, 1e-6)
        C.text(f"XYZ class {sku}", V("Calc_Sku", cs, 14), r.xyz)
        C.num(f"Safety stock {sku}", V("Inventory", m0 + i, 13), r.ss, 1e-6)
        C.num(f"Reorder point {sku}", V("Inventory", m0 + i, 14), r.rop, 1e-6)
        C.num(f"Economic order quantity {sku}", V("Inventory", m0 + i, 15), r.eoq, 0)
        wc = V("Inventory", m0 + i, 16)
        if pd.notna(r.cover):
            C.num(f"Days of cover {sku}", wc, r.cover, 1e-6)
        C.num(f"Inventory turns {sku}", V("Inventory", m0 + i, 17), r.turns, 1e-6)
        C.num(f"GMROI {sku}", V("Inventory", m0 + i, 18), r.gmroi, 1e-6)
        C.num(f"Overstock cost {sku}", V("Inventory", m0 + i, 20), r.overstock_cost, 1e-4)
        C.text(f"Stock status {sku}", V("Inventory", m0 + i, 23), r.status)
        C.num(f"Suggested order qty {sku}", V("Inventory", m0 + i, 24), r.qty, 0)
    counts = inv.groupby(["abc", "xyz"]).size()
    for a in "ABC":
        for z in "XYZ":
            C.num(f"ABC-XYZ count {a}{z}", V("Products", 6 + "ABC".index(a), 3 + "XYZ".index(z)), counts.get((a, z), 0), 0)

    # ---- forecast
    fc = M.forecast_test(t, monthly)
    f = ctx.fc
    for j, cat in enumerate(CATEGORIES):
        o = fc[cat]
        for k, name in enumerate(["naive", "ma", "snaive", "index"]):
            C.num(f"Forecast WAPE {cat} {name}", V("Forecast", f["R_SUM"] + 1 + j, 1 + k), o["wape"][name], 1e-6)
        C.text(f"Forecast best method {cat}", METHOD_KEY.get(V("Forecast", f["R_SUM"] + 1 + j, 5)), o["best"])
        C.num(f"Forecast band factor {cat}", V("Forecast", f["R_LVL"] + 1 + j, 6), o["band"], 1e-6)
        for h in range(12):
            C.num(f"Forecast {cat} month +{h+1}", V("Forecast", f["R_FC"] + 1 + h, 2 + j), o["forecast"][h], 1e-4, rel=True)

    # ---- scenarios and sensitivity
    sc = M.scenario_results(t, monthly)
    sd = ctx.scn
    for i, (name, o) in enumerate(sc["scn"].items()):
        r = sd["S0"] + 1 + i
        C.num(f"Scenario {name}: revenue", V("Scenarios", r, 1), o["rev"], 1e-6, rel=True)
        C.num(f"Scenario {name}: gross profit", V("Scenarios", r, 2), o["gp"], 1e-6, rel=True)
        C.num(f"Scenario {name}: stock-out risk", V("Scenarios", r, 6), o["risk"], 1e-6)
        C.num(f"Scenario {name}: SKUs above the risk limit", V("Scenarios", r, 7), o["n_over"], 0)
    for i, dp in enumerate((-0.10, -0.05, 0.0, 0.05, 0.10)):
        for j, sh in enumerate((-0.20, -0.10, 0.0, 0.10, 0.20)):
            C.num(f"Sensitivity price {dp:+.0%} demand {sh:+.0%}", V("Scenarios", sd["Z0"] + 4 + i, 1 + j), sc["sens"][(dp, sh)], 1e-6, rel=True)

    # ---- customers
    rf = M.rfm(t)
    cu = ctx.cust
    segs = rf["scored"].segment.value_counts()
    for i, s in enumerate(["Champions", "Loyal", "New or recent", "At risk", "Lost or hibernating", "Needs attention"]):
        C.num(f"RFM customers in {s}", V("Customers", cu["S0"] + 2 + i, 1), segs.get(s, 0), 0)
    C.num("Repeat purchase rate", V("Customers", cu["P0"] + 6, 3), rf["repeat"], 1e-9)
    C.num("Average order value", V("Customers", cu["V0"] + 2, 1), rf["aov"], 1e-6)
    C.num("Orders per active customer-year", V("Customers", cu["V0"] + 3, 1), rf["freq"], 1e-9)
    C.num("Yearly retention", V("Customers", cu["V0"] + 5, 1), rf["retention"], 1e-9)
    for j in range(4):
        C.num(f"RFM recency cut-off {j+1}", V("Customers", cu["K0"] + 2 + j, 10), rf["cuts"]["rec"][j], 1e-9)
    coh = M.cohort_matrix(t)
    for k, (cm, row) in enumerate(coh.iterrows()):
        for j in (0, 1, 3, 6, 12):
            if j in row.index and not np.isnan(row[j]):
                C.num(f"Cohort retention {cm:%Y-%m} month {j}", V("Customers", cu["H0"] + 1 + k, 2 + j), row[j], 1e-9)

    # ---- promotions
    pm = M.promo_metrics(t)
    pr = ctx.promo
    for i, r in pm.iterrows():
        row = pr["M0"] + 1 + i
        if pd.notna(r.lift):
            C.num(f"Promotion {r.promo_id} lift", V("Promotions", row, 10), r.lift, 1e-9)
            C.num(f"Promotion {r.promo_id} extra gross profit", V("Promotions", row, 18), r.incr_gp, 0.01)
        if pd.notna(r.breakeven):
            C.num(f"Promotion {r.promo_id} break-even uplift", V("Promotions", row, 16), r.breakeven, 1e-9)
    el = M.elasticities(t)
    for j, c in enumerate(CATEGORIES):
        C.num(f"Implied elasticity {c}", V("Promotions", pr["C0"] + 2 + j, 3), el[c], 1e-9)

    # ---- returns
    rv = M.returns_view(t, monthly)
    rt = ctx.ret
    for j, c in enumerate(CATEGORIES):
        C.num(f"Return rate {c}", V("Returns", rt["C0"] + 2 + j, 5), rv["cat"].loc[c, "rate"], 1e-9)
        C.num(f"Cost of returns {c}", V("Returns", rt["C0"] + 2 + j, 7), rv["cat"].loc[c, "cost"], 0.01)
    pname = t["products"].set_index("sku").product_name
    for k, (sku, r) in enumerate(rv["top"].iterrows()):
        C.text(f"Top problem SKU #{k+1}", V("Returns", rt["L0"] + 2 + k, 1), pname[sku])
    return C.rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "workbook_parity.csv")
    ap.add_argument("--keep", action="store_true", help="keep the temporary workbooks")
    args = ap.parse_args()
    t = common.load_tables()
    data = build_workbook.load_all()
    monthly = data["monthly"]
    tmp = Path(tempfile.mkdtemp(prefix="wbverify_"))
    rows = []
    try:
        rows += verify("all_selected", {}, data, t, monthly, True, tmp)
        rows += verify("narrow_selection", {"sel_year": 2024, "sel_region": "Tampere", "sel_channel": "Online", "sel_category": "Apparel"},
                       data, t, monthly, False, tmp)
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    bad = df[~df.passed]
    print(f"{len(df)} figures compared, {len(bad)} outside tolerance")
    print(df.groupby("run").passed.agg(["count", "sum"]).rename(columns={"sum": "passed"}))
    if len(bad):
        print(bad.head(40).to_string())
    return 1 if len(bad) else 0


if __name__ == "__main__":
    sys.exit(main())
