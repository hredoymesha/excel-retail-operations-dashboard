"""The key findings quoted in the README, each computed from the CSV files.

    python analysis/findings.py

Writes outputs/key_findings.csv. Every sentence is built from numbers worked out here.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from analysis import common, metrics  # noqa: E402

OUT = common.ROOT / "outputs"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    t = common.load_tables()
    m = common.monthly_table(t)
    inv = metrics.inventory_rules(t, m)
    f = []

    # 1 margin by channel
    ch = {c: metrics.pnl(x) for c, x in m.groupby("channel")}
    low = min(ch, key=lambda c: ch[c]["cm_pct"])
    high = max(ch, key=lambda c: ch[c]["cm_pct"])
    tot = metrics.pnl(m)
    f.append(("Margin by channel",
              f"Gross margin is {tot['gm_pct']:.1%} over the three years, but contribution margin is {tot['cm_pct']:.1%} once shipping, fees and returns come off. "
              f"{low} earns {ch[low]['cm_pct']:.1%} against {ch[high]['cm_pct']:.1%} for {high}.", "analysis/kpis.py"))

    # 2 bridge
    b = metrics.bridge(m, 2024, 2025)
    parts = {k: b[k] for k in ["volume", "mix", "price", "discount", "cost", "fees", "returns"]}
    pos = max(parts, key=parts.get)
    neg = min(parts, key=parts.get)
    f.append(("Margin bridge 2024 to 2025",
              f"Contribution margin moved from {b['cm_a']:,.0f} to {b['cm_b']:,.0f} euros ({b['cm_b'] - b['cm_a']:+,.0f}). "
              f"The biggest help was {pos} ({parts[pos]:+,.0f}) and the biggest drag was {neg} ({parts[neg]:+,.0f}).", "analysis/kpis.py"))

    # 3 stock-outs
    lost_units = inv.lost_window.sum()
    dem = inv.dem_window.sum()
    lost_rev = (inv.lost_window * (inv.rev / inv.units)).sum()
    n_re = int((inv.status == "Reorder now").sum())
    n_so = int((inv.status == "Stock-out risk").sum())
    n_ov = int((inv.status == "Overstock").sum())
    obs = inv[inv.status == "Obsolete stock"]
    f.append(("Stock-outs",
              f"In 2025 stock-outs cost {lost_units:,.0f} units, {lost_units / dem:.1%} of demand, about {lost_rev:,.0f} euros of revenue. "
              f"On the last day {n_re} SKUs are at or below their reorder point, {n_so} more have less cover than their lead time, "
              f"{n_ov} are overstocked and {len(obs)} discontinued SKUs still hold {obs.on_hand_end.sum():,.0f} units.", "analysis/abc_xyz.py"))

    # 4 ABC
    a = inv[inv.abc == "A"]
    ax = inv[(inv.abc == "A") & (inv.xyz == "X")]
    cz = inv[(inv.abc == "C") & (inv.xyz == "Z")]
    f.append(("ABC and XYZ",
              f"{len(a)} of {len(inv)} SKUs make up the first 80% of 2025 revenue (class A). {len(ax)} of them have steady demand (AX) and {len(cz)} SKUs are small and erratic (CZ).",
              "analysis/abc_xyz.py"))

    # 5 promotions
    pm = metrics.promo_metrics(t).dropna(subset=["incr_gp"])
    adds = (pm.incr_gp > 0).sum()
    camp = pm.groupby("campaign").incr_gp.sum()
    f.append(("Promotions",
              f"{adds} of {len(pm)} promotions with a baseline added gross profit, {len(pm) - adds} lost it, and in total they changed gross profit by {pm.incr_gp.sum():+,.0f} euros. "
              f"The weakest campaign was {camp.idxmin()} ({camp.min():+,.0f}) and the strongest {camp.idxmax()} ({camp.max():+,.0f}). Baselines ignore seasonality.",
              "analysis/customers.py"))

    # 6 returns and customers
    rv = metrics.returns_view(t, m)
    cat = rv["cat"]
    top = rv["top"].iloc[0]
    names = t["products"].set_index("sku").product_name
    rf = metrics.rfm(t)
    sc = rf["scored"]
    guest = (t["sales_lines"].customer_id == "GUEST").mean()
    seg = sc.groupby("segment").net_revenue.sum() / sc.net_revenue.sum()
    cnt = sc.segment.value_counts(normalize=True)
    f.append(("Returns",
              f"{cat.rate.idxmax()} returns {cat.rate.max():.1%} of units against {cat.rate.min():.1%} for {cat.rate.idxmin()}. "
              f"Returns cost {cat.cost.sum():,.0f} euros, {cat.cost.sum() / cat.net.sum():.1%} of revenue. The worst SKU is {names[rv['top'].index[0]]} at {top.rate:.1%}.",
              "analysis/customers.py"))
    f.append(("Customers",
              f"{rf['repeat']:.0%} of the {rf['bought']:,} consumers who bought ordered twice or more, and {rf['retention']:.0%} of 2024 buyers ordered again in 2025. "
              f"Champions are {cnt['Champions']:.0%} of scored customers and {seg['Champions']:.0%} of their revenue. {guest:.0%} of order lines carry no customer id (guest checkout, marketplace, retail without a card).",
              "analysis/customers.py"))
    # forecast
    fc = metrics.forecast_test(t, m)
    label = {"naive": "naive", "ma": "moving average", "snaive": "seasonal naive", "index": "the seasonal index with trend"}
    wins = pd.Series({c: label[o["best"]] for c, o in fc.items()}).value_counts()
    f.append(("Forecast method", "On the last three months, " + "; ".join(f"{k} won {v}" for k, v in wins.items()) + " of 6 categories. Best method per category was chosen on the test, not by preference.", "analysis/forecast.py"))
    df = pd.DataFrame(f, columns=["topic", "finding", "script"])
    df.to_csv(OUT / "key_findings.csv", index=False)
    for _, r in df.iterrows():
        print(f"- {r.topic}: {r.finding} [{r.script}]")


if __name__ == "__main__":
    main()
