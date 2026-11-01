"""RFM segments, repeat purchase, cohort retention and promotion and return summaries.

    python analysis/customers.py

Writes outputs/rfm_segments.csv, outputs/customer_summary.csv, outputs/cohort_retention.csv,
outputs/promotions.csv, outputs/returns_by_category.csv, outputs/returns_top_skus.csv and
the chart outputs/cohort_retention.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import common, metrics  # noqa: E402
from analysis.style import COLOURS, apply_style  # noqa: E402

OUT = common.ROOT / "outputs"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    t = common.load_tables()
    m = common.monthly_table(t)
    rf = metrics.rfm(t)
    sc = rf["scored"]
    seg = sc.groupby("segment").agg(customers=("customer_id", "size"), revenue=("net_revenue", "sum"),
                                    orders=("orders", "mean"), days_since_last_order=("rec", "mean"))
    seg["share_of_customers"] = seg.customers / seg.customers.sum()
    seg["share_of_revenue"] = seg.revenue / seg.revenue.sum()
    seg.sort_values("revenue", ascending=False).round(4).to_csv(OUT / "rfm_segments.csv")
    summary = pd.DataFrame([
        ("consumers_who_bought", rf["bought"]), ("repeat_purchase_rate", rf["repeat"]), ("average_order_value", rf["aov"]),
        ("orders_per_active_customer_year", rf["freq"]), ("yearly_retention", rf["retention"])], columns=["measure", "value"])
    summary.round(4).to_csv(OUT / "customer_summary.csv", index=False)
    coh = metrics.cohort_matrix(t)
    coh.round(4).to_csv(OUT / "cohort_retention.csv")
    pm = metrics.promo_metrics(t)
    pm[["promo_id", "campaign", "category", "start_date", "discount_pct", "units", "base_units", "lift", "gm_promo", "gm_base",
        "m_list", "breakeven", "incr_gp", "implied_e"]].round(4).to_csv(OUT / "promotions.csv", index=False)
    rv = metrics.returns_view(t, m)
    rv["cat"].round(4).to_csv(OUT / "returns_by_category.csv")
    names = t["products"].set_index("sku").product_name
    top = rv["top"].assign(product=names).round(4)
    top.to_csv(OUT / "returns_top_skus.csv")

    apply_style()
    show = coh.iloc[:, :13]
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(show.values, cmap="Blues", vmin=0, vmax=0.5, aspect="auto")
    ax.set_xticks(range(show.shape[1]))
    ax.set_yticks(range(0, len(show), 3))
    ax.set_yticklabels([d.strftime("%b %Y") for d in show.index[::3]])
    ax.set_xlabel("Months since first order")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Share of cohort still ordering", format=lambda v, _: f"{v:.0%}")
    ax.set_title("Monthly cohort retention, consumers (synthetic data)")
    fig.tight_layout()
    fig.savefig(OUT / "cohort_retention.png", dpi=170)
    print(seg.sort_values("revenue", ascending=False).round(3).to_string())
    print(summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
