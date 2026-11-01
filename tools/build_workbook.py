"""Build Excel_Retail_Operations_Dashboard_v2.xlsx from the CSV files in data/.

    python tools/build_workbook.py

The workbook holds live formulas. Open it in Excel and it calculates on load.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis import common  # noqa: E402
import lo  # noqa: E402
import wb_core  # noqa: E402
import wb_data  # noqa: E402
import wb_ops  # noqa: E402
import wb_dash  # noqa: E402
import wb_plan  # noqa: E402
import wb_cust  # noqa: E402
import wb_meta  # noqa: E402

OUT = ROOT / "Excel_Retail_Operations_Dashboard_v2.xlsx"


def load_all() -> dict:
    t = common.load_tables()
    return {
        "monthly": common.monthly_table(t), "products": common.product_table(t),
        "stock_month": common.stock_month_table(t), "customers": common.customer_table(t),
        "cohort": common.cohort_table(t), "promo": common.promo_table(t), "control": common.control_totals(t),
    }


def build(path: Path = OUT, selections: dict | None = None, data: dict | None = None, cache: dict | None = None) -> wb_core.Ctx:
    ctx = wb_core.Ctx(str(path), data or load_all())
    ctx.sel = selections or {}
    ctx.cache = cache or {}
    wb_data.build_data_sheets(ctx)
    wb_data.build_assumptions(ctx)
    wb_data.build_calc_skumonth(ctx)
    wb_data.build_calc_sku(ctx)
    wb_data.build_calc_dashboard(ctx)
    wb_ops.build_profit(ctx)
    wb_ops.build_inventory(ctx)
    wb_ops.build_products(ctx)
    wb_plan.build_forecast(ctx)
    wb_plan.build_scenarios(ctx)
    wb_cust.build_customers(ctx)
    wb_cust.build_promotions(ctx)
    wb_cust.build_returns(ctx)
    wb_dash.build_dashboard(ctx)
    wb_meta.build_checks(ctx)
    wb_meta.build_start(ctx)
    wb_meta.build_notes(ctx)
    ctx.wb.close()
    return ctx


def read_cache(recalculated: Path) -> dict:
    """Formula results from a LibreOffice-recalculated copy, keyed by (sheet, row, column), zero-based."""
    import openpyxl
    wb = openpyxl.load_workbook(recalculated, data_only=True)
    cache = {}
    epoch = dt.datetime(1899, 12, 30)
    for ws in wb.worksheets:
        if ws.title.startswith("Data_"):
            continue
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if v is None:
                    continue
                if isinstance(v, dt.datetime):
                    v = (v - epoch).total_seconds() / 86400
                elif isinstance(v, dt.time):
                    v = 0
                cache[(ws.title, c.row - 1, c.column - 1)] = v
    return cache


def build_with_values(path: Path = OUT) -> wb_core.Ctx:
    """Build, recalculate with LibreOffice, then build again with the results stored as cached values.

    Excel still recalculates on opening. The stored values are for viewers that do not calculate.
    """
    data = load_all()
    tmp = Path(tempfile.mkdtemp(prefix="wbcache_"))
    try:
        first = tmp / path.name
        build(first, data=data)
        cache = read_cache(lo.recalc(first, tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return build(path, data=data, cache=cache)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-values", action="store_true", help="skip the LibreOffice pass that stores calculated values")
    a = ap.parse_args()
    if a.no_values or lo.find_soffice() is None:
        build(a.out)
    else:
        build_with_values(a.out)
    print("written", a.out)
