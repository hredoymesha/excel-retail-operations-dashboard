"""ABC-XYZ classification and reorder points.

    python analysis/abc_xyz.py

Writes outputs/abc_xyz.csv, outputs/reorder_points.csv and the chart outputs/pareto.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analysis import common, metrics  # noqa: E402
from analysis.style import COLOURS, apply_style  # noqa: E402

OUT = common.ROOT / "outputs"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    t = common.load_tables()
    m = common.monthly_table(t)
    inv = metrics.inventory_rules(t, m)
    names = t["products"].set_index("sku").product_name
    inv["product"] = names
    cols = ["product", "category", "rev", "rank", "cum_before", "abc", "cv", "xyz"]
    abc = inv[cols].rename(columns={"rev": "revenue_2025", "rank": "revenue_rank", "cum_before": "share_before", "cv": "cv_monthly_demand"})
    abc["abc_xyz"] = abc.abc + abc.xyz
    abc.sort_values("revenue_rank").round(4).to_csv(OUT / "abc_xyz.csv")
    rp = inv[["product", "mu", "lead_time_days_avg", "lead_time_days_sd", "ss", "rop", "eoq", "on_hand_end", "on_order_end",
              "cover", "turns", "gmroi", "overstock_units", "overstock_cost", "lost_window", "status", "qty"]].rename(
        columns={"mu": "demand_per_day", "ss": "safety_stock", "rop": "reorder_point", "eoq": "economic_order_qty",
                 "cover": "days_of_cover", "qty": "suggested_order_qty", "lost_window": "lost_units_2025"})
    rp.round(3).to_csv(OUT / "reorder_points.csv")

    apply_style()
    s = abc.sort_values("revenue_rank")
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(range(len(s)), s.revenue_2025, color=COLOURS["navy"])
    ax.set_xticks(range(len(s)))
    ax.set_xticklabels(s.index, rotation=90, fontsize=7)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.set_ylabel("Revenue 2025, EUR")
    ax2 = ax.twinx()
    ax2.plot(range(len(s)), s.revenue_2025.cumsum() / s.revenue_2025.sum(), color=COLOURS["amber"], lw=2)
    ax2.set_ylim(0, 1.02)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax2.grid(False)
    ax.set_title("Pareto chart: revenue by SKU, 2025 (synthetic data)")
    fig.tight_layout()
    fig.savefig(OUT / "pareto.png", dpi=170)
    print(abc.groupby(["abc", "xyz"]).size().unstack(fill_value=0))
    print(rp.status.value_counts().to_string())


if __name__ == "__main__":
    main()
