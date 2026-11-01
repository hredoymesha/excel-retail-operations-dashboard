"""The workbook's calculations written again in pandas.

Nothing here reads the workbook. These functions start from the CSV files and give the
numbers the workbook should show. tools/verify_workbook.py compares the two.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm

from analysis import common
from analysis.common import AS_OF, CATEGORIES

# Same defaults as the Assumptions sheet.
A = dict(svc_level=0.95, review_days=7, order_cost=25.0, hold_rate=0.22, days_year=365, days_month=30, months_year=12,
         dem_window=12, cv_window=24, lost_in_demand=1, abc_a=0.80, abc_b=0.95, xyz_x=0.40, xyz_y=0.70, over_days=120,
         risk_cut=0.25, holdout=3, ma_months=3, band_conf=0.90, min_ret_units=100, rfm_bins=5, seg_hi=4, seg_mid=3,
         seg_lo=2, disc_rate=0.10)


def months_index(monthly: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(monthly.month.unique()))


def filter_monthly(m: pd.DataFrame, year="All", region="All", channel="All", category="All") -> pd.DataFrame:
    x = m
    if year != "All":
        x = x[x.year == int(year)]
    if region != "All":
        x = x[x.region == region]
    if channel != "All":
        x = x[x.channel == channel]
    if category != "All":
        x = x[x.category == category]
    return x


def pnl(x: pd.DataFrame) -> dict:
    s = x[["units", "order_lines", "list_value", "discount_value", "net_revenue", "cogs", "shipping", "payment_fee",
           "platform_fee", "refund_amount", "return_shipping", "restock_cogs"]].sum()
    gp = s.net_revenue - s.cogs
    cm = (s.net_revenue - s.cogs - s.shipping - s.payment_fee - s.platform_fee - s.refund_amount + s.restock_cogs
          - s.return_shipping)
    return dict(units=s.units, net_revenue=s.net_revenue, gross_profit=gp, contribution=cm,
                gm_pct=gp / s.net_revenue if s.net_revenue else 0, cm_pct=cm / s.net_revenue if s.net_revenue else 0,
                disc_pct=s.discount_value / s.list_value if s.list_value else 0, list_value=s.list_value,
                discount_value=s.discount_value, cogs=s.cogs, shipping=s.shipping, payment_fee=s.payment_fee,
                platform_fee=s.platform_fee, refund_amount=s.refund_amount, return_shipping=s.return_shipping,
                restock_cogs=s.restock_cogs)


def kpi_block(m: pd.DataFrame, year="All", region="All", channel="All", category="All") -> dict:
    x = filter_monthly(m, year, region, channel, category)
    cur = pnl(x)
    out = {f"cur_{k}": v for k, v in cur.items()}
    months = months_index(m)
    ref_month = months.max() if year == "All" else pd.Timestamp(int(year), 12, 1)
    base = filter_monthly(m, "All", region, channel, category)
    out.update({f"mom_{k}": v for k, v in pnl(base[base.month == ref_month]).items()})
    out.update({f"prevmonth_{k}": v for k, v in pnl(base[base.month == ref_month - pd.DateOffset(months=1)]).items()})
    if year != "All" and int(year) - 1 >= m.year.min():
        out.update({f"prior_{k}": v for k, v in pnl(filter_monthly(m, int(year) - 1, region, channel, category)).items()})
    return out


def demand_matrix(t: dict, monthly: pd.DataFrame) -> pd.DataFrame:
    sold = monthly.pivot_table(index="sku", columns="month", values="units", aggfunc="sum", fill_value=0)
    lost = common.stock_month_table(t).pivot_table(index="sku", columns="month", values="lost_units", aggfunc="sum", fill_value=0)
    lost = lost.reindex(index=sold.index, columns=sold.columns, fill_value=0)
    return sold + A["lost_in_demand"] * lost, sold, lost


def sku_stats(t: dict, monthly: pd.DataFrame) -> pd.DataFrame:
    dem, sold, lost = demand_matrix(t, monthly)
    win = monthly[(monthly.month >= pd.Timestamp("2025-01-01")) & (monthly.month <= AS_OF)]
    g = win.groupby("sku").agg(rev=("net_revenue", "sum"), cogs=("cogs", "sum"), units=("units", "sum"), ret=("returned_units", "sum"))
    g = g.reindex(dem.index).fillna(0)
    g["gp"] = g.rev - g.cogs
    g["rank"] = g.rev.rank(ascending=False, method="first").astype(int)
    total = g.rev.sum()
    g["cum_before"] = [g.rev[g["rank"] < r].sum() / total for r in g["rank"]]
    g["abc"] = np.where(g.cum_before < A["abc_a"], "A", np.where(g.cum_before < A["abc_b"], "B", "C"))
    last = dem.iloc[:, -A["cv_window"]:]
    g["cv"] = last.std(axis=1, ddof=1) / last.mean(axis=1)
    g["xyz"] = np.where(g.cv <= A["xyz_x"], "X", np.where(g.cv <= A["xyz_y"], "Y", "Z"))
    w = dem.iloc[:, -A["dem_window"]:]
    g["dem_window"] = w.sum(axis=1)
    g["dem_sd_month"] = w.std(axis=1, ddof=1)
    g["lost_window"] = lost.iloc[:, -A["dem_window"]:].sum(axis=1)
    g["mu"] = g.dem_window / 365
    g["gm"] = g.gp / g.rev
    g["ret_rate"] = g.ret / g.units
    return g


def inventory_rules(t: dict, monthly: pd.DataFrame) -> pd.DataFrame:
    g = sku_stats(t, monthly)
    p = common.product_table(t).set_index("sku")
    d = g.join(p)
    d["sd_day"] = d.dem_sd_month / math.sqrt(A["days_month"])
    z = norm.ppf(A["svc_level"])
    lt = d.lead_time_days_avg + A["review_days"]
    d["ss"] = z * np.sqrt(lt * d.sd_day ** 2 + (d.mu * d.lead_time_days_sd) ** 2)
    d["rop"] = d.mu * lt + d.ss
    raw = np.sqrt(2 * d.mu * A["days_year"] * A["order_cost"] / (A["hold_rate"] * d.unit_cost_now))
    d["eoq"] = np.maximum(d.min_order_qty, np.ceil(raw / d.min_order_qty - 1e-12) * d.min_order_qty)
    d["position"] = d.on_hand_end + d.on_order_end
    d["cover"] = np.where(d.mu > 0, d.on_hand_end / d.mu.replace(0, np.nan), np.nan)
    disc = d.discontinued_date.notna()
    status = []
    for sku, r in d.iterrows():
        if pd.notna(r.discontinued_date):
            status.append("Obsolete stock" if r.on_hand_end > 0 else "Discontinued")
        elif r.position <= r.rop:
            status.append("Reorder now")
        elif r.mu > 0 and r.cover < r.lead_time_days_avg:
            status.append("Stock-out risk")
        elif r.mu > 0 and r.cover > A["over_days"]:
            status.append("Overstock")
        else:
            status.append("OK")
    d["status"] = status
    d["overstock_units"] = np.maximum(0, d.on_hand_end - (d.rop + d.eoq))
    d["overstock_cost"] = d.overstock_units * d.unit_cost_now * A["hold_rate"]
    d["turns"] = d.cogs * A["months_year"] / A["dem_window"] / (d.avg_on_hand_12m * d.unit_cost_now)
    d["gmroi"] = d.gp * A["months_year"] / A["dem_window"] / (d.avg_on_hand_12m * d.unit_cost_now)
    d["qty"] = np.where(d.status == "Reorder now",
                        np.maximum(d.min_order_qty, np.ceil((d.rop + d.eoq - d.position) / d.min_order_qty - 1e-12) * d.min_order_qty), 0)
    return d


def category_demand(t: dict, monthly: pd.DataFrame) -> pd.DataFrame:
    dem, _, _ = demand_matrix(t, monthly)
    cat = common.product_table(t).set_index("sku").category
    return dem.groupby(cat).sum().T.reindex(columns=CATEGORIES)


def _season_index(series: pd.Series, train_n: int) -> np.ndarray:
    """Average ratio of each month to its calendar-year mean, complete years in training only."""
    tr = series.iloc[:train_n]
    yrs = tr.groupby(tr.index.year).count()
    complete = yrs[yrs == A["months_year"]].index
    ratios = {m: [] for m in range(1, 13)}
    for y in complete:
        part = tr[tr.index.year == y]
        mean = part.mean()
        for ts, v in part.items():
            ratios[ts.month].append(v / mean)
    return np.array([np.mean(ratios[m]) if ratios[m] else 1.0 for m in range(1, 13)])


def forecast_test(t: dict, monthly: pd.DataFrame) -> dict:
    cd = category_demand(t, monthly)
    n = len(cd)
    h = A["holdout"]
    cut = n - h
    out = {}
    z = norm.ppf((1 + A["band_conf"]) / 2)
    for cat in CATEGORIES:
        s = cd[cat]
        act = s.iloc[cut:].values
        idx_h = _season_index(s, cut)
        level = s.iloc[cut - 12:cut].mean()
        growth = level / s.iloc[cut - 24:cut - 12].mean()
        month_c = s.index[cut - 1].month
        forecasts = {
            "naive": np.repeat(s.iloc[cut - 1], h),
            "ma": np.repeat(s.iloc[cut - A["ma_months"]:cut].mean(), h),
            "snaive": np.array([s.iloc[cut + k - 12] for k in range(h)]),
            "index": np.array([level * growth ** ((k + 1 + 11 / 2) / 12) * idx_h[(month_c + k) % 12] for k in range(h)]),
        }
        wape = {k: np.abs(act - v).sum() / act.sum() for k, v in forecasts.items()}
        mape = {k: np.mean(np.abs(act - v) / act) for k, v in forecasts.items()}
        best = min(wape, key=wape.get)
        idx_f = _season_index(s, n)
        level_f = s.iloc[n - 12:n].mean()
        growth_f = level_f / s.iloc[n - 24:n - 12].mean()
        month_n = s.index[n - 1].month
        fut = {
            "naive": np.repeat(s.iloc[n - 1], 12),
            "ma": np.repeat(s.iloc[n - A["ma_months"]:n].mean(), 12),
            "snaive": np.array([s.iloc[n + k - 12] for k in range(12)]),
            "index": np.array([level_f * growth_f ** ((k + 1 + 11 / 2) / 12) * idx_f[(month_n + k) % 12] for k in range(12)]),
        }
        # residual spread of the final seasonal index over complete years
        res = []
        for y, part in s.groupby(s.index.year):
            if len(part) == 12:
                mean = part.mean()
                res += [v / mean / idx_f[ts.month - 1] - 1 for ts, v in part.items()]
        sigma = float(np.std(res, ddof=1))
        out[cat] = dict(wape=wape, mape=mape, best=best, forecast=fut[best], fut=fut, sigma=sigma, band=z * sigma,
                        level=level, growth=growth, idx_hold=idx_h, idx_final=idx_f)
    return out


def bridge(monthly: pd.DataFrame, ya: int, yb: int, region="All", channel="All", category="All") -> dict:
    def per_sku(y):
        x = filter_monthly(monthly, y, region, channel, category)
        g = x.groupby("sku").agg(u=("units", "sum"), l=("list_value", "sum"), d=("discount_value", "sum"), c=("cogs", "sum"),
                                 f=("shipping", "sum"), pf=("payment_fee", "sum"), pl=("platform_fee", "sum"),
                                 rf=("refund_amount", "sum"), rs=("return_shipping", "sum"), rc=("restock_cogs", "sum"))
        g["fees"] = g.f + g.pf + g.pl
        g["ret"] = g.rf + g.rs - g.rc
        return g
    skus = sorted(monthly.sku.unique())
    a = per_sku(ya).reindex(skus).fillna(0)
    b = per_sku(yb).reindex(skus).fillna(0)
    eff = dict(vol_mix=0.0, price=0.0, disc=0.0, cost=0.0, fee=0.0, ret=0.0)
    sum_ub_cmua = 0.0
    for k in skus:
        A_, B_ = a.loc[k], b.loc[k]

        def per(num, den):
            va = A_[num] / A_[den] if A_[den] > 0 else (B_[num] / B_[den] if B_[den] > 0 else 0.0)
            vb = B_[num] / B_[den] if B_[den] > 0 else va
            return va, vb
        pa, pb = per("l", "u")
        da, db = per("d", "l")
        ca, cb = per("c", "u")
        fa, fb = per("fees", "u")
        ra, rb = per("ret", "u")
        cmu_a = pa * (1 - da) - ca - fa - ra
        ub = B_["u"]
        sum_ub_cmua += ub * cmu_a
        eff["price"] += ub * (pb - pa) * (1 - da)
        eff["disc"] += -ub * pb * (db - da)
        eff["cost"] += -ub * (cb - ca)
        eff["fee"] += -ub * (fb - fa)
        eff["ret"] += -ub * (rb - ra)
    cm_a = (a.l - a.d - a.c - a.fees - a.ret).sum()
    cm_b = (b.l - b.d - b.c - b.fees - b.ret).sum()
    ua, ubt = a.u.sum(), b.u.sum()
    avg = cm_a / ua if ua else 0.0
    vol = (ubt - ua) * avg
    mix = sum_ub_cmua - ubt * avg
    gap = cm_b - (cm_a + vol + mix + eff["price"] + eff["disc"] + eff["cost"] + eff["fee"] + eff["ret"])
    return dict(cm_a=cm_a, cm_b=cm_b, volume=vol, mix=mix, price=eff["price"], discount=eff["disc"], cost=eff["cost"],
                fees=eff["fee"], returns=eff["ret"], gap=gap)


def rfm(t: dict) -> dict:
    c = common.customer_table(t)
    sc = c[(c.customer_type == "Consumer") & (c.orders > 0)].copy()
    sc["rec"] = (AS_OF - sc.last_order).dt.days
    bins = A["rfm_bins"]
    cuts = {k: [np.percentile(sc[k], 100 * j / bins) for j in range(1, bins)] for k in ["rec", "orders", "net_revenue"]}
    sc["R"] = bins - sc.rec.apply(lambda v: sum(1 for x in cuts["rec"] if x < v))
    sc["F"] = 1 + sc.orders.apply(lambda v: sum(1 for x in cuts["orders"] if x < v))
    sc["M"] = 1 + sc.net_revenue.apply(lambda v: sum(1 for x in cuts["net_revenue"] if x < v))
    hi, mid, lo = A["seg_hi"], A["seg_mid"], A["seg_lo"]

    def seg(r):
        if r.R >= hi and r.F >= hi:
            return "Champions"
        if r.R >= mid and r.F >= mid:
            return "Loyal"
        if r.R >= hi and r.F <= lo:
            return "New or recent"
        if r.R <= lo and r.F >= mid:
            return "At risk"
        if r.R <= lo and r.F <= lo:
            return "Lost or hibernating"
        return "Needs attention"
    sc["segment"] = sc.apply(seg, axis=1)
    cons = c[c.customer_type == "Consumer"]
    bought = cons[cons.orders > 0]
    repeat = (bought.orders >= 2).sum() / len(bought)
    aov = bought.net_revenue.sum() / bought.orders.sum()
    freq = bought.orders.sum() / (cons.active_2023.sum() + cons.active_2024.sum() + cons.active_2025.sum())
    ret = ((cons.active_2024 == 1) & (cons.active_2025 == 1)).sum() / (cons.active_2024 == 1).sum()
    return dict(scored=sc, cuts=cuts, repeat=repeat, aov=aov, freq=freq, retention=ret, bought=len(bought))


def cohort_matrix(t: dict) -> pd.DataFrame:
    co = common.cohort_table(t)
    size = co[co.months_since == 0].set_index("cohort_month").active_customers
    mat = co.pivot_table(index="cohort_month", columns="months_since", values="active_customers", aggfunc="sum")
    return mat.div(size, axis=0)


def promo_metrics(t: dict) -> pd.DataFrame:
    p = common.promo_table(t)
    p["base_units"] = p.baseline_units_pd * p.days
    p["lift"] = p.units / p.base_units - 1
    p["gm_promo"] = (p.net_revenue - p.cogs) / p.net_revenue
    p["gm_base"] = (p.baseline_net_pd - p.baseline_cogs_pd) / p.baseline_net_pd
    p["m_list"] = (p.list_value - p.cogs) / p.list_value
    p["breakeven"] = np.where(p.m_list > p.discount_pct, p.discount_pct / (p.m_list - p.discount_pct), np.nan)
    p["incr_gp"] = (p.net_revenue - p.cogs) - (p.baseline_net_pd - p.baseline_cogs_pd) * p.days
    with np.errstate(invalid="ignore", divide="ignore"):
        p["implied_e"] = np.where(p.lift > -1, np.log1p(p.lift) / -np.log(1 - p.discount_pct), np.nan)
    return p


def elasticities(t: dict) -> pd.Series:
    p = promo_metrics(t)
    return p.groupby("category").implied_e.mean().reindex(CATEGORIES)


def returns_view(t: dict, monthly: pd.DataFrame) -> dict:
    cat = monthly.groupby("category").agg(units=("units", "sum"), ret=("returned_units", "sum"), refund=("refund_amount", "sum"),
                                          ship=("return_shipping", "sum"), restock=("restock_cogs", "sum"), net=("net_revenue", "sum"))
    cat["rate"] = cat.ret / cat.units
    cat["cost"] = cat.refund + cat.ship - cat.restock
    sku = monthly.groupby("sku").agg(units=("units", "sum"), ret=("returned_units", "sum"), refund=("refund_amount", "sum"),
                                     ship=("return_shipping", "sum"), restock=("restock_cogs", "sum"), net=("net_revenue", "sum"))
    sku["rate"] = sku.ret / sku.units
    sku["cost"] = sku.refund + sku.ship - sku.restock
    top = sku[sku.units >= A["min_ret_units"]].sort_values("rate", ascending=False).head(10)
    return dict(cat=cat.reindex(CATEGORIES), sku=sku, top=top)


SCENARIOS = {
    "Base": (0.0, 0.0, 0.0, 0.0, 0),
    "Price change": (0.05, 0.0, 0.0, 0.0, 0),
    "Promotion": (0.0, 0.15, 0.25, 0.0, 0),
    "Supplier delay": (0.0, 0.0, 0.0, 0.0, 14),
    "Demand shock": (0.0, 0.0, 0.0, -0.15, 0),
}


def scenario_results(t: dict, monthly: pd.DataFrame) -> dict:
    inv = inventory_rules(t, monthly)
    e = elasticities(t)
    cat = inv.groupby("category").agg(U=("units", "sum"), rev=("rev", "sum"), cogs=("cogs", "sum")).reindex(CATEGORIES)
    out = {}
    for name, (dp, dd, ds, sh, delay) in SCENARIOS.items():
        phi = (1 + dp) * (1 - dd * ds)
        units = cat.U * (1 + sh) * phi ** (-e)
        rev = (units * (cat.rev / cat.U) * phi).sum()
        gp = rev - (units * (cat.cogs / cat.U)).sum()
        mult = inv.category.map(lambda c: (1 + sh) * phi ** (-e[c]))
        lt = inv.lead_time_days_avg + delay + A["review_days"]
        mean = inv.mu * mult * lt
        sd = np.sqrt(lt * (inv.sd_day * mult) ** 2 + (inv.mu * mult * inv.lead_time_days_sd) ** 2)
        risk = 1 - norm.cdf((inv.position - mean) / sd)
        active = (~inv.status.isin(["Obsolete stock", "Discontinued"])) & (inv.mu > 0)
        w = inv.rev * active
        out[name] = dict(rev=rev, gp=gp, gm=gp / rev, risk=(risk * w).sum() / w.sum(), n_over=int(((risk > A["risk_cut"]) & active).sum()))
    sens = {}
    for dp in (-0.10, -0.05, 0.0, 0.05, 0.10):
        for sh in (-0.20, -0.10, 0.0, 0.10, 0.20):
            units = cat.U * (1 + sh) * (1 + dp) ** (-e)
            sens[(dp, sh)] = float((units * ((cat.rev / cat.U) * (1 + dp) - cat.cogs / cat.U)).sum())
    return dict(scn=out, sens=sens, elasticity=e)
