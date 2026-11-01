"""Forecast back-test and the next twelve months by category.

    python analysis/forecast.py

Writes outputs/forecast_backtest.csv, outputs/forecast_next12.csv and outputs/forecast_backtest.png.
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
from analysis.common import CATEGORIES  # noqa: E402
from analysis.style import COLOURS, apply_style  # noqa: E402

OUT = common.ROOT / "outputs"
LABEL = {"naive": "Naive", "ma": "Moving average", "snaive": "Seasonal naive", "index": "Seasonal index with trend"}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    t = common.load_tables()
    m = common.monthly_table(t)
    res = metrics.forecast_test(t, m)
    rows, fut = [], {}
    first_future = common.AS_OF + pd.Timedelta(days=1)
    months = pd.date_range(first_future, periods=12, freq="MS")
    for cat in CATEGORIES:
        o = res[cat]
        row = {"category": cat}
        for k in LABEL:
            row[f"wape_{k}"] = o["wape"][k]
            row[f"mape_{k}"] = o["mape"][k]
        row["best_method"] = LABEL[o["best"]]
        rows.append(row)
        fut[cat] = o["forecast"]
    pd.DataFrame(rows).round(4).to_csv(OUT / "forecast_backtest.csv", index=False)
    f = pd.DataFrame(fut, index=months).round(1)
    f["all_categories"] = f.sum(axis=1)
    f.index.name = "month"
    f.to_csv(OUT / "forecast_next12.csv")

    apply_style()
    cd = metrics.category_demand(t, m)
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.4), sharex=True)
    for ax, cat in zip(axes.ravel(), CATEGORIES):
        ax.plot(cd.index, cd[cat], color=COLOURS["navy"], lw=1.6)
        ax.plot(months, f[cat], color=COLOURS["teal"], lw=1.6)
        z = res[cat]["band"]
        ax.fill_between(months, f[cat] * (1 - z), f[cat] * (1 + z), color=COLOURS["sky"], alpha=0.45, lw=0)
        ax.set_title(f"{cat}: {LABEL[res[cat]['best']]}", fontsize=9)
    fig.suptitle("Monthly demand and 12-month forecast with the method chosen on the hold-out (synthetic data)", fontsize=10, color=COLOURS["navy"])
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT / "forecast_backtest.png", dpi=170)
    print(pd.DataFrame(rows)[["category", "wape_naive", "wape_ma", "wape_snaive", "wape_index", "best_method"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
