"""Clean the raw sales export and write data/sales_lines.csv.

Input:  data/raw/sales_lines_dirty.csv  and data/customers.csv
Output: data/sales_lines.csv            the clean table used by every analysis
        data/raw/cleaning_log.csv       one line per kind of problem, with counts
        data/raw/cleaning_actions.csv   one line per changed value

Rules, in the order they run:

1. Remove test orders (order id starting with TEST).
2. Remove exact duplicate rows.
3. Trim spaces and fix the case of channel and SKU.
4. Read prices written with a decimal comma.
5. Make negative quantities positive (the net revenue is positive, so the sign is a typing error).
6. Read dates written as dd.mm.yyyy.
7. Repair dates outside the data period from the neighbouring order numbers.
   Order numbers run in date order, so the previous and next valid order give the day.
8. Fill a blank region from another line of the same order, else from the customer's home region.
9. Fill a blank customer from another line of the same order.
10. Rebuild a blank discount from list price, quantity and net revenue.

Nothing is guessed silently: each change is written to the action log, and a row that cannot be repaired stops the script.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = {"Online", "Retail", "Marketplace", "Wholesale"}
MONEY = ["list_price", "net_revenue", "unit_cost", "shipping_cost", "payment_fee", "platform_fee"]


class Log:
    def __init__(self) -> None:
        self.actions: list[dict] = []
        self.summary: list[dict] = []

    def record(self, rule: str, issue: str, action: str, rows: pd.DataFrame, column: str,
               old: pd.Series, new: pd.Series, method: str = "") -> None:
        for (_, r), o, n in zip(rows.iterrows(), old, new):
            self.actions.append({"rule": rule, "order_id": r["order_id"], "line_no": r["line_no"],
                                 "column": column, "old_value": o, "new_value": n, "method": method})
        ex_old = "" if len(old) == 0 else str(old.iloc[0])
        ex_new = "" if len(new) == 0 else str(new.iloc[0])
        self.summary.append({"rule": rule, "issue": issue, "rows_affected": len(rows), "action": action,
                             "example_before": ex_old, "example_after": ex_new})


def clean(raw: pd.DataFrame, customers: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, Log]:
    log = Log()
    df = raw.copy()
    df["line_no"] = df["line_no"].astype(str)

    # 1 test orders
    test = df.order_id.str.startswith("TEST")
    log.record("R01", "Test orders left in the export", "Rows removed", df[test], "order_id",
               df.loc[test, "order_id"], pd.Series([""] * int(test.sum()), index=df.index[test]))
    df = df[~test]

    # 2 exact duplicates
    dup = df.duplicated(keep="first")
    log.record("R02", "Exact duplicate rows", "Second copy removed", df[dup], "order_id",
               df.loc[dup, "order_id"], pd.Series([""] * int(dup.sum()), index=df.index[dup]))
    df = df[~dup].copy()

    # 3 channel and SKU text
    for col, fn, rule in [("channel", lambda s: s.str.strip().str.title(), "R03"),
                          ("sku", lambda s: s.str.strip().str.upper(), "R03")]:
        new = fn(df[col])
        changed = new != df[col]
        log.record(rule, f"{col} written with spaces or the wrong case", "Trimmed and standardised",
                   df[changed], col, df.loc[changed, col], new[changed])
        df[col] = new
    assert set(df.channel) <= CHANNELS, "unknown channel left after cleaning"

    # 4 decimal comma
    comma = df.list_price.str.contains(",", regex=False)
    new = df.list_price.str.replace(",", ".", regex=False)
    log.record("R04", "List price written with a decimal comma", "Converted to a number",
               df[comma], "list_price", df.loc[comma, "list_price"], new[comma])
    df["list_price"] = new

    # 5 negative quantity
    q = pd.to_numeric(df.quantity)
    neg = q < 0
    log.record("R05", "Negative quantity on a sale", "Sign removed", df[neg], "quantity",
               df.loc[neg, "quantity"], (-q[neg]).astype(str))
    df["quantity"] = q.abs().astype(int)

    # 6 and 7 dates
    iso = pd.to_datetime(df.order_date, format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(df.order_date, format="%d.%m.%Y", errors="coerce")
    use_dmy = iso.isna() & dmy.notna()
    new_dates = iso.fillna(dmy)
    log.record("R06", "Date written as dd.mm.yyyy", "Converted to yyyy-mm-dd", df[use_dmy], "order_date",
               df.loc[use_dmy, "order_date"], new_dates[use_dmy].dt.strftime("%Y-%m-%d"))
    out_of_range = new_dates.isna() | (new_dates < pd.Timestamp(start)) | (new_dates > pd.Timestamp(end))
    df["_num"] = df.order_id.str.slice(4).astype(int)
    known = (df[~out_of_range].assign(_d=new_dates[~out_of_range])
             .groupby("_num")["_d"].first().sort_index())
    nums = known.index.values
    vals = known.values
    fixed, methods = [], []
    for num in df.loc[out_of_range, "_num"]:
        if num in known.index:
            fixed.append(known.loc[num])
            methods.append("other line of the same order")
            continue
        pos = np.searchsorted(nums, num)
        prev_d = vals[pos - 1] if pos > 0 else None
        next_d = vals[pos] if pos < len(vals) else None
        if prev_d is not None and next_d is not None and prev_d == next_d:
            fixed.append(prev_d)
            methods.append("previous and next order are on the same day")
        else:
            fixed.append(prev_d if prev_d is not None else next_d)
            methods.append("estimated from the previous order")
    if fixed:
        fixed_s = pd.Series(pd.to_datetime(fixed), index=df.index[out_of_range])
        for m in sorted(set(methods)):
            idx = df.index[out_of_range][[x == m for x in methods]]
            log.record("R07", "Date outside the data period", "Date rebuilt from order numbers",
                       df.loc[idx], "order_date", df.loc[idx, "order_date"],
                       fixed_s.loc[idx].dt.strftime("%Y-%m-%d"), m)
        new_dates = new_dates.copy()
        new_dates[out_of_range] = fixed_s
    df["order_date"] = new_dates.dt.strftime("%Y-%m-%d")

    # 8 blank region
    cust_region = customers.set_index("customer_id").region
    blank_region = df.region.str.strip() == ""
    by_order = df[~blank_region].groupby("order_id").region.first()
    new_region = df.order_id.map(by_order).fillna(df.customer_id.map(cust_region))
    log.record("R08", "Region missing", "Taken from the same order, else the customer's home region", df[blank_region],
               "region", df.loc[blank_region, "region"], new_region[blank_region], "same order, else customers.csv")
    df.loc[blank_region, "region"] = new_region[blank_region]
    left = df.region.isna() | (df.region.str.strip() == "")
    if left.any():
        raise ValueError(f"{int(left.sum())} rows have no region and no way to recover it, first order {df.order_id[left].iloc[0]}")

    # 9 blank customer
    blank_cust = df.customer_id.str.strip() == ""
    sibling = (df[~blank_cust].groupby("order_id").customer_id.first())
    new_cust = df.order_id.map(sibling)
    log.record("R09", "Customer id missing", "Taken from another line of the same order", df[blank_cust],
               "customer_id", df.loc[blank_cust, "customer_id"], new_cust[blank_cust], "same order")
    df.loc[blank_cust, "customer_id"] = new_cust[blank_cust]
    left = df.customer_id.isna() | (df.customer_id.str.strip() == "")
    if left.any():
        raise ValueError(f"{int(left.sum())} rows have no customer id and no other line of the order to take it from, first order {df.order_id[left].iloc[0]}")

    # 10 blank discount
    blank_disc = df.discount_pct.str.strip() == ""
    gross = pd.to_numeric(df.list_price) * df.quantity
    rebuilt = (1 - pd.to_numeric(df.net_revenue) / gross).round(2)
    log.record("R10", "Discount missing", "Rebuilt from list price, quantity and net revenue",
               df[blank_disc], "discount_pct", df.loc[blank_disc, "discount_pct"], rebuilt[blank_disc].astype(str),
               "1 - net_revenue / (quantity * list_price)")
    df.loc[blank_disc, "discount_pct"] = rebuilt[blank_disc].astype(str)

    # types
    df["line_no"] = df.line_no.astype(int)
    df["discount_pct"] = pd.to_numeric(df.discount_pct).round(2)
    for col in MONEY:
        df[col] = pd.to_numeric(df[col]).round(2)
    df = df.drop(columns="_num").sort_values(["order_id", "line_no"]).reset_index(drop=True)
    return df, log


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    args = ap.parse_args()
    raw = pd.read_csv(args.data / "raw" / "sales_lines_dirty.csv", dtype=str, keep_default_na=False)
    customers = pd.read_csv(args.data / "customers.csv", dtype=str, keep_default_na=False)
    clean_df, log = clean(raw, customers, "2023-01-01", "2025-12-31")
    clean_df["promo_id"] = clean_df.promo_id.fillna("")
    clean_df.to_csv(args.data / "sales_lines.csv", index=False)
    pd.DataFrame(log.summary).to_csv(args.data / "raw" / "cleaning_log.csv", index=False)
    pd.DataFrame(log.actions).to_csv(args.data / "raw" / "cleaning_actions.csv", index=False)
    print(f"raw rows   {len(raw):>8,d}")
    print(f"clean rows {len(clean_df):>8,d}")
    for row in log.summary:
        print(f"  {row['rule']}  {row['rows_affected']:>5d}  {row['issue']}")


if __name__ == "__main__":
    main()
