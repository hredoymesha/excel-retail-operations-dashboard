"""Shared data preparation for the workbook builder and the analysis scripts.

Every table the workbook carries as data is built here from the CSV files in data/,
so the workbook and the Python checks start from the same numbers.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHANNELS = ["Online", "Retail", "Marketplace", "Wholesale"]
CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Beauty & Care", "Office", "Sports & Outdoor"]
AS_OF = pd.Timestamp("2025-12-31")
PROMO_BASE_DAYS = 56
PROMO_MIN_BASE_DAYS = 10
DIP_DAYS = 10


def load_tables(data: Path = DATA) -> dict[str, pd.DataFrame]:
    names = ["products", "suppliers", "customers", "promotions", "price_history", "sales_lines",
             "returns", "inventory_daily", "purchase_orders"]
    t = {n: pd.read_csv(data / f"{n}.csv", keep_default_na=False, na_values=[""]) for n in names}
    t["sales_lines"]["promo_id"] = t["sales_lines"].promo_id.fillna("")
    for name, cols in {"sales_lines": ["order_date"], "returns": ["return_date"], "inventory_daily": ["date"],
                       "customers": ["signup_date"], "promotions": ["start_date", "end_date"],
                       "purchase_orders": ["order_date", "promised_date", "received_date"],
                       "price_history": ["effective_from"], "products": ["launch_date", "discontinued_date"]}.items():
        for c in cols:
            t[name][c] = pd.to_datetime(t[name][c])
    return t


def sales_enriched(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s = t["sales_lines"].copy()
    s["category"] = s.sku.map(t["products"].set_index("sku").category)
    s["month"] = s.order_date.dt.to_period("M").dt.to_timestamp()
    s["year"] = s.order_date.dt.year
    s["list_value"] = (s.quantity * s.list_price).round(2)
    s["discount_value"] = (s.list_value - s.net_revenue).round(2)
    s["cogs"] = (s.quantity * s.unit_cost).round(2)
    return s


def monthly_table(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Sales aggregated to month x SKU x region x channel, with returns on the order month."""
    s = sales_enriched(t)
    r = t["returns"].merge(s[["order_id", "line_no", "month", "region", "channel", "unit_cost"]],
                           on=["order_id", "line_no"])
    r["restock_cogs"] = (r.return_qty * r.unit_cost * r.restocked).round(2)
    keys = ["month", "sku", "region", "channel"]
    a = s.groupby(keys).agg(units=("quantity", "sum"), order_lines=("order_id", "size"),
                            list_value=("list_value", "sum"), discount_value=("discount_value", "sum"),
                            net_revenue=("net_revenue", "sum"), cogs=("cogs", "sum"),
                            shipping=("shipping_cost", "sum"), payment_fee=("payment_fee", "sum"),
                            platform_fee=("platform_fee", "sum"))
    b = r.groupby(keys).agg(returned_units=("return_qty", "sum"), refund_amount=("refund_amount", "sum"),
                            return_shipping=("return_shipping_cost", "sum"), restock_cogs=("restock_cogs", "sum"))
    m = a.join(b, how="left").fillna(0).reset_index()
    m.insert(1, "year", m.month.dt.year)
    m.insert(2, "month_no", m.month.dt.month)
    m.insert(5, "category", m.sku.map(t["products"].set_index("sku").category))
    m = m[["month", "year", "month_no", "sku", "category", "region", "channel", "units", "order_lines",
           "list_value", "discount_value", "net_revenue", "cogs", "shipping", "payment_fee", "platform_fee",
           "returned_units", "refund_amount", "return_shipping", "restock_cogs"]]
    for c in ["list_value", "discount_value", "net_revenue", "cogs", "shipping", "payment_fee", "platform_fee",
              "refund_amount", "return_shipping", "restock_cogs"]:
        m[c] = m[c].round(2)
    for c in ["units", "order_lines", "returned_units"]:
        m[c] = m[c].astype(int)
    return m.sort_values(["month", "sku", "region", "channel"]).reset_index(drop=True)


def product_table(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    p = t["products"].merge(t["suppliers"][["supplier_id", "supplier_name"]], on="supplier_id")
    last = t["price_history"].sort_values("effective_from").groupby("sku").tail(1).set_index("sku")
    p["list_price_now"] = p.sku.map(last.list_price)
    p["unit_cost_now"] = p.sku.map(last.unit_cost)
    inv = t["inventory_daily"]
    end = inv[inv.date == AS_OF].set_index("sku")
    last12 = inv[inv.date > AS_OF - pd.DateOffset(years=1)]
    g = last12.groupby("sku")
    p["on_hand_end"] = p.sku.map(end.on_hand)
    p["on_order_end"] = p.sku.map(end.on_order)
    p["avg_on_hand_12m"] = p.sku.map(g.on_hand.mean()).round(2)
    p["lost_units_12m"] = p.sku.map(g.lost_units.sum())
    p["stockout_days_12m"] = p.sku.map(g.stockout_flag.sum())
    p = p.sort_values("sku").reset_index(drop=True)
    cols = ["sku", "product_name", "category", "supplier_id", "supplier_name", "list_price_now", "unit_cost_now",
            "lead_time_days_avg", "lead_time_days_sd", "min_order_qty", "shelf_life_days", "launch_date",
            "discontinued_date", "stocking_policy", "on_hand_end", "on_order_end", "avg_on_hand_12m",
            "lost_units_12m", "stockout_days_12m"]
    return p[cols]


def stock_month_table(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    inv = t["inventory_daily"].copy()
    inv["month"] = inv.date.dt.to_period("M").dt.to_timestamp()
    g = inv.groupby(["month", "sku"]).agg(lost_units=("lost_units", "sum"),
                                          stockout_days=("stockout_flag", "sum")).reset_index()
    return g.sort_values(["month", "sku"]).reset_index(drop=True)


def customer_table(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s = sales_enriched(t)
    s["gp"] = s.net_revenue - s.cogs
    g = s.groupby("customer_id").agg(first_order=("order_date", "min"), last_order=("order_date", "max"),
                                     orders=("order_id", "nunique"), net_revenue=("net_revenue", "sum"),
                                     gross_profit=("gp", "sum"))
    act = s.groupby(["customer_id", "year"]).size().unstack(fill_value=0).gt(0).astype(int)
    c = t["customers"].set_index("customer_id").join(g)
    for y in (2023, 2024, 2025):
        c[f"active_{y}"] = act[y].reindex(c.index).fillna(0).astype(int)
    c["orders"] = c.orders.fillna(0).astype(int)
    c["net_revenue"] = c.net_revenue.fillna(0).round(2)
    c["gross_profit"] = c.gross_profit.fillna(0).round(2)
    c = c.reset_index()
    return c[["customer_id", "customer_type", "region", "signup_date", "first_order", "last_order", "orders",
              "net_revenue", "gross_profit", "active_2023", "active_2024", "active_2025"]]


def cohort_table(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s = sales_enriched(t)
    cons = set(t["customers"].loc[t["customers"].customer_type == "Consumer", "customer_id"])
    s = s[s.customer_id.isin(cons)]
    first = s.groupby("customer_id").month.min().rename("cohort")
    a = s.drop_duplicates(["customer_id", "month"]).merge(first, on="customer_id")
    a["months_since"] = (a.month.dt.year - a.cohort.dt.year) * 12 + (a.month.dt.month - a.cohort.dt.month)
    g = a.groupby(["cohort", "months_since"]).customer_id.nunique().rename("active_customers").reset_index()
    return g.rename(columns={"cohort": "cohort_month"})


def promo_table(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s = sales_enriched(t)
    s = s[s.channel != "Wholesale"]
    promos = t["promotions"]
    rows = []
    for _, p in promos.iterrows():
        same_cat = promos[promos.category == p.category]
        blocked = pd.Series(False, index=pd.date_range("2022-10-01", "2026-01-31"))
        for _, q in same_cat.iterrows():
            blocked[q.start_date:q.end_date] = True
            if q.discount_pct >= 0.20:
                blocked[q.end_date + pd.Timedelta(days=1):q.end_date + pd.Timedelta(days=DIP_DAYS)] = True
        scope = ["Online"] if p.channel_scope == "Online" else ["Online", "Retail", "Marketplace"]
        cat = s[(s.category == p.category) & s.channel.isin(scope)]
        days = (p.end_date - p.start_date).days + 1
        inp = cat[cat.promo_id == p.promo_id]
        base_days = pd.date_range(p.start_date - pd.Timedelta(days=PROMO_BASE_DAYS), p.start_date - pd.Timedelta(days=1))
        base_days = [d for d in base_days if d >= pd.Timestamp("2023-01-01") and not blocked[d]]
        if len(base_days) >= PROMO_MIN_BASE_DAYS:
            b = cat[cat.order_date.isin(base_days)]
            bu, bn, bc = b.quantity.sum() / len(base_days), b.net_revenue.sum() / len(base_days), b.cogs.sum() / len(base_days)
        else:
            bu = bn = bc = None
        rows.append({
            "promo_id": p.promo_id, "campaign": p.campaign, "category": p.category,
            "channel_scope": p.channel_scope, "start_date": p.start_date, "end_date": p.end_date, "days": days,
            "discount_pct": p.discount_pct, "units": int(inp.quantity.sum()), "list_value": round(inp.list_value.sum(), 2),
            "net_revenue": round(inp.net_revenue.sum(), 2), "cogs": round(inp.cogs.sum(), 2),
            "baseline_days": len(base_days),
            "baseline_units_pd": None if bu is None else round(bu, 4),
            "baseline_net_pd": None if bn is None else round(bn, 4),
            "baseline_cogs_pd": None if bc is None else round(bc, 4),
        })
    return pd.DataFrame(rows)


def control_totals(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    s = t["sales_lines"]
    rows = [
        ("Sales lines in sales_lines.csv", len(s)),
        ("Units in sales_lines.csv", int(s.quantity.sum())),
        ("Net revenue in sales_lines.csv", round(float(s.net_revenue.sum()), 2)),
        ("Cost of goods in sales_lines.csv", round(float((s.quantity * s.unit_cost).sum()), 2)),
        ("Shipping in sales_lines.csv", round(float(s.shipping_cost.sum()), 2)),
        ("Rows in products.csv", len(t["products"])),
        ("Rows in customers.csv", len(t["customers"])),
        ("Rows in returns.csv", len(t["returns"])),
        ("Refunds in returns.csv", round(float(t["returns"].refund_amount.sum()), 2)),
        ("Rows in promotions.csv", len(t["promotions"])),
        ("Units lost to stock-outs in inventory_daily.csv", int(t["inventory_daily"].lost_units.sum())),
    ]
    return pd.DataFrame(rows, columns=["item", "csv_value"])


def save_csv(df: pd.DataFrame, path: Path, percent=(), index: bool = False, rename: bool = True) -> None:
    """Write df with every number rounded to two decimals.

    Columns listed in percent hold fractions. They are multiplied by 100 and, unless rename is
    False, get a _pct suffix, so 0.5253 is written as 52.53 in a column called ..._pct.
    """
    out = df.copy()
    names = {}
    for c in percent:
        out[c] = out[c] * 100
        if rename and not str(c).endswith("_pct"):
            names[c] = f"{c}_pct"
    out = out.rename(columns=names)
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(2)
    for c in num:
        if out[c].notna().all() and (out[c] == out[c].round(0)).all():
            out[c] = out[c].astype("int64")
    out.to_csv(path, index=index, float_format="%.2f")
