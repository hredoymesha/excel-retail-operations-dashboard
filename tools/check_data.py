"""Check the data files against the rules a sensible retail dataset must obey.

Run after tools/generate_data.py and tools/clean_data.py:

    python tools/check_data.py

Prints one line per check and a short summary, and writes outputs/data_checks.csv.
The exit code is 1 if any check fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load(data: Path) -> dict[str, pd.DataFrame]:
    names = ["products", "suppliers", "customers", "promotions", "price_history", "sales_lines",
             "returns", "inventory_daily", "purchase_orders"]
    t = {n: pd.read_csv(data / f"{n}.csv", keep_default_na=False, na_values=[""]) for n in names}
    t["sales_lines"]["promo_id"] = t["sales_lines"].promo_id.fillna("")
    for name, cols in {"sales_lines": ["order_date"], "returns": ["return_date"],
                       "inventory_daily": ["date"], "customers": ["signup_date"],
                       "purchase_orders": ["order_date", "promised_date", "received_date"],
                       "promotions": ["start_date", "end_date"]}.items():
        for c in cols:
            t[name][c] = pd.to_datetime(t[name][c])
    return t


def run_checks(t: dict[str, pd.DataFrame], data: Path) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, bool(ok), detail))

    s, p, c, inv = t["sales_lines"], t["products"], t["customers"], t["inventory_daily"]
    r, po, promo = t["returns"], t["purchase_orders"], t["promotions"]
    cat = p.set_index("sku").category
    s = s.assign(category=s.sku.map(cat), year=s.order_date.dt.year)
    s["gross_profit"] = s.net_revenue - s.quantity * s.unit_cost

    # structure
    check("At least 40 SKUs in 6 categories", len(p) >= 40 and p.category.nunique() >= 6,
          f"{len(p)} SKUs, {p.category.nunique()} categories")
    check("At least 5 regions and 4 channels", s.region.nunique() >= 5 and s.channel.nunique() == 4,
          f"{s.region.nunique()} regions, {s.channel.nunique()} channels")
    check("About 4,000 customers, ids unique", c.customer_id.is_unique and 3900 <= len(c) <= 4100, f"{len(c)} customers")
    check("SKU ids unique", p.sku.is_unique)
    check("Order lines unique on order id and line number", not s.duplicated(["order_id", "line_no"]).any())

    # completeness and ranges
    check("No missing values in sales lines", int(s.drop(columns=["promo_id"]).isna().sum().sum()) == 0)
    check("Sales cover 2023-01-01 to 2025-12-31 with a sale on every day",
          s.order_date.min() == pd.Timestamp("2023-01-01") and s.order_date.max() == pd.Timestamp("2025-12-31")
          and s.order_date.nunique() == 1096, f"{s.order_date.nunique()} days")
    check("Quantity positive, price and cost positive", (s.quantity > 0).all() and (s.list_price > 0).all()
          and (s.unit_cost > 0).all())
    check("Discount between 0 and 40%", s.discount_pct.between(0, 0.40).all(), f"max {s.discount_pct.max():.0%}")
    check("Unit cost below list price on every line", (s.unit_cost < s.list_price).all())
    expected = (s.quantity * s.list_price * (1 - s.discount_pct)).round(2)
    check("Net revenue equals quantity x list price x (1 - discount) to the cent",
          (expected - s.net_revenue).abs().max() < 0.0051, f"max difference {(expected - s.net_revenue).abs().max():.4f}")
    check("Shipping and fees are not negative", (s[["shipping_cost", "payment_fee", "platform_fee"]] >= 0).all().all())

    # keys
    check("Every SKU on a sale exists in products", s.sku.isin(p.sku).all())
    check("Every customer on a sale exists in customers, or is GUEST", (s.customer_id.isin(c.customer_id) | (s.customer_id == "GUEST")).all())
    check("Every promotion id on a sale exists in promotions", s.promo_id[s.promo_id != ""].isin(promo.promo_id).all())
    one = s.groupby("order_id")[["order_date", "customer_id", "region", "channel"]].nunique().max().max()
    check("One date, customer, region and channel per order", one == 1)
    home = s.customer_id.map(c.set_index("customer_id").region)
    ident = s.customer_id != "GUEST"
    check("Sale region equals the customer's home region (guests have none)", (home[ident] == s.region[ident]).all())
    signup = s.customer_id.map(c.set_index("customer_id").signup_date)
    check("No order before the customer signed up", (s.order_date[ident] >= signup[ident]).all())
    biz = s.customer_id.map(c.set_index("customer_id").customer_type)
    check("Only business accounts buy wholesale", ((s.channel == "Wholesale") == (biz == "Business")).all())
    guest_share = (s.customer_id == "GUEST").groupby(s.channel).mean()
    check("Guest orders: all marketplace, no wholesale", guest_share["Marketplace"] == 1 and guest_share["Wholesale"] == 0,
          ", ".join(f"{k} {v:.0%}" for k, v in guest_share.items()))

    # margin
    gm = s.gross_profit.sum() / s.net_revenue.sum()
    cat_gm = s.groupby("category").apply(lambda d: d.gross_profit.sum() / d.net_revenue.sum(), include_groups=False)
    sku_gm = s.groupby("sku").apply(lambda d: d.gross_profit.sum() / d.net_revenue.sum(), include_groups=False)
    check("Overall gross margin between 35% and 60%", 0.35 <= gm <= 0.60, f"{gm:.1%}")
    check("Every category margin between 25% and 75%", cat_gm.between(0.25, 0.75).all(),
          f"{cat_gm.min():.1%} to {cat_gm.max():.1%}")
    check("Every SKU margin between 10% and 80%", sku_gm.between(0.10, 0.80).all(),
          f"{sku_gm.min():.1%} to {sku_gm.max():.1%}")
    fees = s[["shipping_cost", "payment_fee", "platform_fee"]].sum().sum()
    contribution = s.gross_profit.sum() - fees - r.refund_amount.sum()
    check("Contribution margin after fees and refunds is positive", contribution > 0,
          f"{contribution / s.net_revenue.sum():.1%} of revenue")

    # seasonality and promotions
    share = s[s.order_date.dt.month.isin([11, 12])].groupby("year").net_revenue.sum() / s.groupby("year").net_revenue.sum()
    check("November and December carry more than 20% of each year's revenue", (share > 0.20).all(),
          ", ".join(f"{y}: {v:.1%}" for y, v in share.items()))
    cat_month = s.assign(m=s.order_date.dt.month).groupby(["category", "m"]).net_revenue.sum().unstack()
    check("Office has a summer dip (July below its monthly average)",
          cat_month.loc["Office", 7] < cat_month.loc["Office"].mean() * 0.8)
    daily = s.groupby(["category", "order_date"]).quantity.sum().rename("units").reset_index()
    flag = daily.merge(promo.assign(d=1)[["category", "start_date", "end_date"]], on="category", how="left")
    flag["in"] = (flag.order_date >= flag.start_date) & (flag.order_date <= flag.end_date)
    in_promo = flag.groupby(["category", "order_date"])["in"].any().rename("in_promo").reset_index()
    daily = daily.merge(in_promo, on=["category", "order_date"])
    ratio = daily[daily.in_promo].units.mean() / daily[~daily.in_promo].units.mean()
    check("Units per category-day are higher on promotion days", ratio > 1.2, f"x{ratio:.2f}")
    promo_gm = s[s.promo_id != ""].pipe(lambda d: d.gross_profit.sum() / d.net_revenue.sum())
    base_gm = s[s.promo_id == ""].pipe(lambda d: d.gross_profit.sum() / d.net_revenue.sum())
    check("Promotion lines earn a lower margin than other lines", promo_gm < base_gm,
          f"{promo_gm:.1%} against {base_gm:.1%}")

    # returns
    line = s.set_index(["order_id", "line_no"])
    rl = r.set_index(["order_id", "line_no"])
    check("Every return points at a sale line", rl.index.isin(line.index).all())
    check("Return ids unique", r.return_id.is_unique)
    joined = r.merge(s[["order_id", "line_no", "order_date", "quantity", "net_revenue", "category", "channel"]],
                     on=["order_id", "line_no"])
    check("Returned units do not exceed sold units", (joined.return_qty <= joined.quantity).all())
    check("Return date is after the order date", (joined.return_date > joined.order_date).all())
    check("Refund does not exceed the line revenue", (joined.refund_amount <= joined.net_revenue + 0.005).all())
    rr = joined.groupby("category").size() / s.groupby("category").size()
    check("Return rate by category between 1% and 25%", rr.between(0.01, 0.25).all(),
          f"{rr.min():.1%} to {rr.max():.1%}")
    check("Apparel returns more than Office", rr["Apparel"] > rr["Office"])

    # inventory
    check("No negative stock on any day", (inv.on_hand >= 0).all() and (inv.on_order >= 0).all())
    check("Lost units are never negative", (inv.lost_units >= 0).all())
    sold = s.groupby(["sku", "order_date"]).quantity.sum()
    inv_sold = inv.set_index(["sku", "date"]).units_sold
    inv_sold = inv_sold[inv_sold > 0]
    check("Units sold in inventory_daily equal units on sales lines, day by day",
          sold.rename_axis(["sku", "date"]).sort_index().equals(inv_sold.sort_index()),
          f"{int(sold.sum()):,} units")
    rec = po[po.received_date.notna()].groupby(["sku", "received_date"]).quantity.sum()
    rec.index.names = ["sku", "date"]
    inv = inv.sort_values(["sku", "date"]).reset_index(drop=True)
    inv["received"] = inv.set_index(["sku", "date"]).index.map(rec).to_numpy()
    inv["received"] = inv.received.fillna(0)
    inv["prev"] = inv.groupby("sku").on_hand.shift()
    step = inv.dropna(subset=["prev"])
    gap = (step.prev + step.received - step.units_sold - step.on_hand).abs()
    check("Stock balance: yesterday + received - sold = today, for every SKU and day",
          (gap == 0).all(), f"max gap {int(gap.max())} units")
    check("Purchase orders respect the minimum order quantity",
          (po.quantity % po.sku.map(p.set_index("sku").min_order_qty) == 0).all()
          and (po.quantity >= po.sku.map(p.set_index("sku").min_order_qty)).all())
    check("Goods are received after the order date", (po.received_date.dropna() > po.order_date[po.received_date.notna()]).all())
    d = po.dropna(subset=["delay_days"])
    win = d[(d.supplier_id == "SUP-03") & d.order_date.between("2024-06-01", "2024-09-30")].delay_days.mean()
    out_win = d[(d.supplier_id == "SUP-03") & ~d.order_date.between("2024-06-01", "2024-09-30")].delay_days.mean()
    check("Supplier disruption shows up as longer delays", win > out_win + 3, f"{win:.1f} days against {out_win:.1f}")
    lost_share = inv.lost_units.sum() / (inv.lost_units.sum() + inv.units_sold.sum())
    check("Stock-outs cost between 0.5% and 8% of demand", 0.005 <= lost_share <= 0.08, f"{lost_share:.1%}")
    check("Some SKUs never stock out and some often do",
          (inv.groupby("sku").stockout_flag.sum() == 0).any() and (inv.groupby("sku").stockout_flag.sum() > 30).any())
    last = inv.groupby("sku").tail(1).set_index("sku")
    disc = p[p.discontinued_date.notna()].sku
    check("Discontinued SKUs leave obsolete stock on the shelf", (last.loc[disc].on_hand > 0).any(),
          ", ".join(f"{k}: {v}" for k, v in last.loc[disc].on_hand.items()))
    slow = inv.groupby("sku").apply(lambda d: d.on_hand.mean() / max(d.units_sold.mean(), 0.01), include_groups=False)
    check("Some slow-moving SKUs hold more than 150 days of stock", (slow > 150).any(), f"{int((slow > 150).sum())} SKUs")

    # cleaning
    raw = pd.read_csv(data / "raw" / "sales_lines_dirty.csv", dtype=str, keep_default_na=False)
    log = pd.read_csv(data / "raw" / "cleaning_log.csv")
    removed = int(log[log.rule.isin(["R01", "R02"])].rows_affected.sum())
    check("Raw rows minus test and duplicate rows equals clean rows", len(raw) - removed == len(s),
          f"{len(raw):,} - {removed} = {len(s):,}")
    check("Every cleaning rule fixed at least one row", (log.rows_affected > 0).all())
    return out


def summary(t: dict[str, pd.DataFrame]) -> str:
    s, p, r, inv = t["sales_lines"], t["products"], t["returns"], t["inventory_daily"]
    s = s.assign(year=s.order_date.dt.year, category=s.sku.map(p.set_index("sku").category))
    s["gp"] = s.net_revenue - s.quantity * s.unit_cost
    lines = []
    by_year = s.groupby("year").agg(revenue=("net_revenue", "sum"), gross_profit=("gp", "sum"),
                                    units=("quantity", "sum"), orders=("order_id", "nunique"))
    by_year["gross_margin"] = by_year.gross_profit / by_year.revenue
    lines.append("By year\n" + by_year.round(3).to_string())
    by_cat = s.groupby("category").agg(revenue=("net_revenue", "sum"), gp=("gp", "sum"))
    by_cat["gross_margin"] = by_cat.gp / by_cat.revenue
    lines.append("By category\n" + by_cat.round(3).to_string())
    by_ch = s.groupby("channel").agg(revenue=("net_revenue", "sum"), lines=("order_id", "size"))
    lines.append("By channel\n" + by_ch.round(0).to_string())
    ident = s[s.customer_id != "GUEST"]
    lines.append(f"Customers who bought: {ident.customer_id.nunique():,} of {len(t['customers']):,}; guest orders {(s.customer_id == 'GUEST').mean():.0%} of lines")
    lines.append(f"Return lines: {len(r):,} ({len(r) / len(s):.1%} of sale lines), refunds {r.refund_amount.sum():,.0f}")
    lost = inv.lost_units.sum()
    lines.append(f"Lost units from stock-outs: {int(lost):,} ({lost / (lost + inv.units_sold.sum()):.1%} of demand)")
    return "\n\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs")
    args = ap.parse_args()
    t = load(args.data)
    results = run_checks(t, args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results, columns=["check", "passed", "detail"]).to_csv(args.out / "data_checks.csv", index=False)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    failed = [x for x in results if not x[1]]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed\n")
    print(summary(t))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
