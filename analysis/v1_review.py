"""Check the claims and the logic of version 1 against its own data.

    python analysis/v1_review.py

Reads v1/ (the copy of version 1) and never writes to it. Writes outputs/v1_review.csv.
The version 1 workbook is opened read-only and is not saved.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import openpyxl  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "v1"


def main() -> None:
    sales = pd.read_csv(V1 / "data" / "sales_transactions_2025.csv")
    inv = pd.read_csv(V1 / "data" / "inventory_snapshot.csv")
    sales["d"] = pd.to_datetime(sales["Order Date"])
    sales["rev"] = sales["Units Sold"] * sales["Unit Price"] * (1 - sales["Discount %"])
    sales["gp"] = sales.rev - sales["Units Sold"] * sales["Unit Cost"]
    rows = []

    def add(finding, measure, value, note=""):
        rows.append(dict(finding=finding, measure=measure, value=value, note=note))

    # 1 margin over the year, by the Month label the workbook uses
    g = sales.groupby("Month", sort=False).agg(rev=("rev", "sum"), gp=("gp", "sum"), disc=("Discount %", "mean"))
    g["gm"] = g.gp / g.rev
    add("Margin story", "Lowest monthly gross margin (%)", round(g.gm.min() * 100, 2), g.gm.idxmin())
    add("Margin story", "Highest monthly gross margin (%)", round(g.gm.max() * 100, 2), g.gm.idxmax())
    add("Margin story", "Spread in percentage points", round((g.gm.max() - g.gm.min()) * 100, 2))
    add("Margin story", "Lowest monthly average discount (%)", round(g.disc.min() * 100, 2))
    add("Margin story", "Highest monthly average discount (%)", round(g.disc.max() * 100, 2))
    share = sales.assign(m=sales.Month).groupby(["m", "Category"]).rev.sum().unstack()
    share = share.div(share.sum(axis=1), axis=0)
    add("Margin story", "Electronics share of revenue, January (%)", round(share.loc["Jan 2025", "Electronics"] * 100, 2))
    add("Margin story", "Electronics share of revenue, December (%)", round(share.loc["Dec 2025", "Electronics"] * 100, 2))
    cat_gm = (sales.groupby("Category").gp.sum() / sales.groupby("Category").rev.sum())
    add("Margin story", "Electronics gross margin (%)", round(cat_gm["Electronics"] * 100, 2))
    add("Margin story", "Beauty gross margin (%)", round(cat_gm["Beauty"] * 100, 2))

    # 2 ABC in product order against revenue order
    wb = openpyxl.load_workbook(V1 / "Excel_Retail_Operations_Dashboard.xlsx", data_only=True, read_only=True)
    ws = wb["Category_ABC"]
    abc = pd.DataFrame([[c.value for c in r] for r in ws.iter_rows(min_row=4, max_row=21, min_col=7, max_col=13)],
                       columns=["SKU", "Product", "Category", "Revenue", "Share", "Cum", "Class"])
    abc_sorted = abc.sort_values("Revenue", ascending=False).copy()
    cum = abc_sorted.Revenue.cumsum() / abc_sorted.Revenue.sum()
    abc_sorted["right"] = np.where(cum <= 0.8, "A", np.where(cum <= 0.95, "B", "C"))
    merged = abc.merge(abc_sorted[["SKU", "right"]], on="SKU")
    add("ABC order", "SKUs in the workbook table", len(abc))
    add("ABC order", "Is the table sorted by revenue", bool(abc.Revenue.is_monotonic_decreasing))
    for c in "ABC":
        add("ABC order", f"Class {c} in the workbook", int((abc.Class == c).sum()))
        add("ABC order", f"Class {c} when sorted by revenue", int((merged.right == c).sum()))
    add("ABC order", "SKUs in the wrong class", int((merged.Class != merged.right).sum()))

    # 3 dates against the Month label
    wrong = sales.d.dt.strftime("%b %Y") != sales.Month
    add("Dates", "Rows whose date is in another month than the Month label", int(wrong.sum()), f"of {len(sales)}")
    add("Dates", "Earliest order date", sales.d.min().strftime("%Y-%m-%d"))
    ws2 = wb["Sales_Data"]
    wdates = pd.to_datetime([r[0] for r in ws2.iter_rows(min_row=2, min_col=2, max_col=2, values_only=True)])
    diff = (pd.Series(wdates) - sales.d.reset_index(drop=True)).dt.days
    add("Dates", "Workbook date minus CSV date, most common difference in days", int(diff.mode()[0]), f"{(diff == diff.mode()[0]).mean():.0%} of rows")

    # 4 reorder rule
    ltd = inv["Avg Monthly Demand"] / 30 * inv["Lead Time Days"] + inv["Safety Stock"]
    add("Reorder rule", "Warehouse rows with a reorder point below demand over the lead time plus safety stock", int((inv["Reorder Point"] < ltd).sum()), f"of {len(inv)}")
    add("Reorder rule", "Average shortfall of the reorder point in units", round(float((ltd - inv["Reorder Point"]).mean()), 2))
    avail = inv["On Hand"] + inv["In Transit"]
    add("Reorder rule", "Rows flagged Reorder Now", int((avail < inv["Reorder Point"]).sum()))

    # 5 forecast
    act = g.rev.values
    ma = np.array([act[t - 3:t].mean() for t in range(3, 12)])
    naive = act[2:11]
    mape = lambda a, f: float(np.mean(np.abs(a - f) / a))
    add("Forecast", "Three-month average, error on April to December (MAPE, %)", round(mape(act[3:], ma) * 100, 2))
    add("Forecast", "Last month as the forecast, same months (MAPE, %)", round(mape(act[3:], naive) * 100, 2))
    incl = np.array([act[t - 2:t + 1].mean() for t in range(2, 12)])
    add("Forecast", "Average that includes the month being forecast (MAPE, %)", round(mape(act[2:], incl) * 100, 2), "what the v1 table shows")
    add("Forecast", "Months of history", len(act))
    pd.DataFrame(rows).to_csv(ROOT / "outputs" / "v1_review.csv", index=False, float_format="%.2f")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
