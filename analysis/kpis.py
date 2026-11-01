"""Headline KPIs, margin by category and channel, and the margin bridge.

    python analysis/kpis.py

Writes outputs/kpis_by_year.csv, kpis_by_category.csv, kpis_by_channel.csv, monthly_trend.csv,
margin_bridge.csv, margin_bridge_by_category.csv and the chart outputs/revenue_margin_trend.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import common, metrics  # noqa: E402
from analysis.style import apply_style, COLOURS  # noqa: E402

OUT = common.ROOT / "outputs"


def table_by(monthly: pd.DataFrame, key: str) -> pd.DataFrame:
    rows = []
    for k, x in monthly.groupby(key):
        p = metrics.pnl(x)
        rows.append({key: k, "revenue": p["net_revenue"], "gross_profit": p["gross_profit"], "gross_margin": p["gm_pct"],
                     "contribution_margin": p["contribution"], "contribution_margin_pct": p["cm_pct"], "units": p["units"],
                     "average_discount": p["disc_pct"]})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    t = common.load_tables()
    m = common.monthly_table(t)
    pct = ["gross_margin", "contribution_margin_pct", "average_discount"]
    for key in ("year", "category", "channel"):
        common.save_csv(table_by(m, key), OUT / f"kpis_by_{key}.csv", percent=pct)
    trend = table_by(m.assign(month_start=m.month), "month_start")
    common.save_csv(trend, OUT / "monthly_trend.csv", percent=pct)
    br = metrics.bridge(m, 2024, 2025)
    common.save_csv(pd.DataFrame([{"step": k, "euro": float(v)} for k, v in br.items()]), OUT / "margin_bridge.csv")
    cats = pd.DataFrame({c: metrics.bridge(m, 2024, 2025, "All", "All", c) for c in common.CATEGORIES}).T.astype(float)
    cats.index.name = "category"
    common.save_csv(cats, OUT / "margin_bridge_by_category.csv", index=True)

    apply_style()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(trend.month_start, trend.revenue, width=25, color=COLOURS["navy"], label="Revenue")
    ax.set_ylabel("Revenue, EUR")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax2 = ax.twinx()
    ax2.plot(trend.month_start, trend.contribution_margin_pct, color=COLOURS["amber"], lw=2, label="Contribution margin")
    ax2.plot(trend.month_start, trend.gross_margin, color=COLOURS["teal"], lw=2, label="Gross margin")
    ax2.set_ylim(0, 0.8)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax2.grid(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False, ncol=3)
    ax.set_title("Monthly revenue and margin (synthetic data)")
    fig.tight_layout()
    fig.savefig(OUT / "revenue_margin_trend.png", dpi=170)
    print(table_by(m, "year").to_string(index=False))
    print(table_by(m, "channel").to_string(index=False))


if __name__ == "__main__":
    main()
