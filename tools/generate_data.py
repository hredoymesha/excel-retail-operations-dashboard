"""Generate the synthetic data for the retail operations dashboard (v2).

Everything here is invented. The company, the products, the suppliers and
the customers are fictional and no real person, brand or business is
described. The generator is seeded, so the same seed and the same library
versions give byte-identical files.

Run from the project root:

    python tools/generate_data.py

It writes the clean reference tables to data/ and a deliberately dirty copy of
the sales lines to data/raw/. Run tools/clean_data.py next to produce
data/sales_lines.csv, then tools/check_data.py to test everything.

How the data is built, in short:

1. Demand per SKU, day, region and channel is a Poisson draw around a rate
   made of popularity, season, yearly trend, weekday, channel mix, promotion
   lift (price elasticity) and noise.
2. Each SKU then runs through a day-by-day stock simulation with its own
   reorder policy. Demand that arrives when the shelf is empty is lost, and
   the lost units are recorded. Suppliers deliver late now and then.
3. Sales lines are grouped into orders and given a customer who is active in
   that region on that day.
4. Returns are drawn per line with category and channel specific rates.
"""
from __future__ import annotations

import argparse
import calendar
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

REGIONS = {"Helsinki": 0.34, "Tampere": 0.22, "Turku": 0.17, "Oulu": 0.14, "Kuopio": 0.13}
CHANNELS = ["Online", "Retail", "Marketplace", "Wholesale"]
# share of sales events by channel, by year (Online and Marketplace grow, Retail shrinks)
CHANNEL_SHARE = {
    2023: [0.360, 0.407, 0.225, 0.008],
    2024: [0.400, 0.357, 0.235, 0.008],
    2025: [0.430, 0.317, 0.245, 0.008],
}
DOW = {  # Monday = 0
    "Online": [1.00, 1.00, 0.95, 0.95, 1.00, 1.10, 1.20],
    "Retail": [0.85, 0.85, 0.90, 1.00, 1.20, 1.55, 0.65],
    "Marketplace": [1.05, 1.00, 1.00, 1.00, 1.00, 0.95, 1.00],
    "Wholesale": [1.40, 1.30, 1.20, 1.20, 1.00, 0.00, 0.00],
}
SEASON = {  # relative demand by calendar month, January to December
    "Electronics": [0.85, 0.80, 0.85, 0.85, 0.90, 0.85, 0.80, 0.85, 0.95, 1.00, 1.25, 1.45],
    "Apparel": [0.80, 0.85, 0.95, 1.00, 1.05, 0.95, 0.80, 0.85, 1.05, 1.10, 1.25, 1.40],
    "Home & Kitchen": [0.90, 0.85, 0.90, 0.95, 1.00, 0.95, 0.80, 0.90, 1.00, 1.05, 1.25, 1.50],
    "Beauty & Care": [0.90, 0.90, 1.00, 1.00, 1.05, 1.00, 0.90, 0.90, 1.00, 1.05, 1.25, 1.40],
    "Office": [1.00, 0.95, 0.95, 0.95, 0.95, 0.80, 0.55, 1.15, 1.25, 1.00, 1.00, 0.80],
    "Sports & Outdoor": [1.10, 1.00, 0.95, 1.00, 1.20, 1.35, 1.25, 1.00, 0.90, 0.85, 1.00, 1.25],
}
DEMAND_GROWTH = {  # yearly growth of underlying demand
    "Electronics": 0.08, "Apparel": 0.05, "Home & Kitchen": 0.06,
    "Beauty & Care": 0.09, "Office": 0.02, "Sports & Outdoor": 0.07,
}
ELASTICITY = {  # demand multiplier on a discount d is (1 - d) ** -elasticity
    "Electronics": 2.0, "Apparel": 1.7, "Home & Kitchen": 1.3,
    "Beauty & Care": 1.0, "Office": 0.7, "Sports & Outdoor": 1.4,
}
PRICE_GROWTH = {  # change of list price every 1 January after 2023
    "Electronics": -0.03, "Apparel": 0.04, "Home & Kitchen": 0.03,
    "Beauty & Care": 0.03, "Office": 0.02, "Sports & Outdoor": 0.03,
}
COST_GROWTH = {  # change of unit cost every 1 January after 2023
    "Electronics": -0.02, "Apparel": 0.045, "Home & Kitchen": 0.035,
    "Beauty & Care": 0.02, "Office": 0.025, "Sports & Outdoor": 0.03,
}
QTY_PROBS = {  # units per retail line: 1, 2, 3
    "Electronics": [0.92, 0.07, 0.01], "Apparel": [0.70, 0.22, 0.08],
    "Home & Kitchen": [0.80, 0.15, 0.05], "Beauty & Care": [0.65, 0.25, 0.10],
    "Office": [0.60, 0.25, 0.15], "Sports & Outdoor": [0.82, 0.14, 0.04],
}
GUEST_SHARE = {"Online": 0.60, "Retail": 0.80, "Marketplace": 1.0, "Wholesale": 0.0}  # orders without a customer id
RETURN_RATE = {  # share of lines with a return, before channel and SKU factors
    "Electronics": 0.060, "Apparel": 0.150, "Home & Kitchen": 0.050,
    "Beauty & Care": 0.025, "Office": 0.020, "Sports & Outdoor": 0.070,
}
RETURN_CHANNEL_FACTOR = {"Online": 1.5, "Retail": 0.5, "Marketplace": 1.2, "Wholesale": 0.25}
RETURN_REASONS = {
    "Electronics": [("Defective", 0.40), ("Not as described", 0.20), ("Changed mind", 0.30), ("Arrived damaged", 0.10)],
    "Apparel": [("Wrong size", 0.55), ("Changed mind", 0.25), ("Not as described", 0.10), ("Arrived damaged", 0.10)],
    "Home & Kitchen": [("Arrived damaged", 0.30), ("Defective", 0.25), ("Changed mind", 0.30), ("Not as described", 0.15)],
    "Beauty & Care": [("Changed mind", 0.45), ("Allergic reaction", 0.25), ("Arrived damaged", 0.15), ("Not as described", 0.15)],
    "Office": [("Changed mind", 0.45), ("Wrong item", 0.25), ("Defective", 0.20), ("Arrived damaged", 0.10)],
    "Sports & Outdoor": [("Wrong size", 0.30), ("Defective", 0.25), ("Changed mind", 0.30), ("Not as described", 0.15)],
}
# share of a returned line that can be put back on the shelf, by reason
RESTOCK_PROB = {"Defective": 0.0, "Arrived damaged": 0.0, "Allergic reaction": 0.0}
RETURN_SHIPPING = {"Online": 4.50, "Marketplace": 4.50, "Retail": 0.0, "Wholesale": 0.0}

SUPPLIERS = [
    # id, name, country, avg lead time (days), sd of lead time, on-time reliability note
    ("SUP-01", "Baltic Tech Supply", "Estonia", 21, 4),
    ("SUP-02", "Harbour Lane Imports", "Netherlands", 28, 7),
    ("SUP-03", "Tideway Supply", "United Kingdom", 35, 8),
    ("SUP-04", "Linden Textiles", "Portugal", 30, 6),
    ("SUP-05", "Pohja Home Goods", "Finland", 18, 3),
    ("SUP-06", "Selka Cosmetics", "Sweden", 14, 2),
    ("SUP-07", "Marlow Office Wholesale", "Germany", 10, 2),
    ("SUP-08", "Fjord Outdoor Gear", "Norway", 25, 5),
]
DISRUPTED_SUPPLIER = "SUP-03"
DISRUPTION_WINDOW = ("2024-06-01", "2024-09-30")  # lead times stretch in this window
COST_SHOCK_SUPPLIER = "SUP-01"
COST_SHOCK_DATE = "2024-03-01"
COST_SHOCK = 0.07

# name, category, unit cost 2023, list price 2023, supplier, shelf life (days) or None
PRODUCTS = [
    ("Lumra Wireless Earbuds", "Electronics", 28.0, 49.0, "SUP-01", None),
    ("Veltix Smart Watch", "Electronics", 72.0, 119.0, "SUP-01", None),
    ("Norvi USB-C Hub", "Electronics", 14.0, 25.0, "SUP-02", None),
    ("Taivo Portable Speaker", "Electronics", 33.0, 54.0, "SUP-01", None),
    ("Kelmo Power Bank 20000", "Electronics", 16.0, 29.0, "SUP-02", None),
    ("Sorva 4K Action Camera", "Electronics", 96.0, 149.0, "SUP-01", None),
    ("Hylo Gaming Headset", "Electronics", 38.0, 62.0, "SUP-02", None),
    ("Tuuli Merino Base Layer", "Apparel", 18.0, 44.0, "SUP-04", None),
    ("Kaarna Insulated Jacket", "Apparel", 52.0, 129.0, "SUP-03", None),
    ("Selma Wool Beanie", "Apparel", 5.5, 17.0, "SUP-04", None),
    ("Vesi Rain Shell", "Apparel", 36.0, 89.0, "SUP-03", None),
    ("Pilvi Denim Jeans", "Apparel", 21.0, 59.0, "SUP-04", None),
    ("Ruska Fleece Pullover", "Apparel", 19.0, 52.0, "SUP-04", None),
    ("Kuura Thermal Socks 3-pack", "Apparel", 4.8, 15.0, "SUP-04", None),
    ("Hearth Cast Iron Pan", "Home & Kitchen", 17.0, 34.0, "SUP-03", None),
    ("Nimbo Electric Kettle", "Home & Kitchen", 14.0, 29.0, "SUP-05", None),
    ("Oravi Knife Set", "Home & Kitchen", 22.0, 49.0, "SUP-05", None),
    ("Lykke Ceramic Mug Set", "Home & Kitchen", 8.5, 19.0, "SUP-05", None),
    ("Harmaa Linen Throw", "Home & Kitchen", 15.0, 36.0, "SUP-03", None),
    ("Tammi Cutting Board", "Home & Kitchen", 7.0, 18.0, "SUP-05", None),
    ("Aava Air Purifier", "Home & Kitchen", 48.0, 95.0, "SUP-02", None),
    ("Lumo Moisturising Cream", "Beauty & Care", 4.2, 14.9, "SUP-06", 730),
    ("Nordlys Daily Sunscreen", "Beauty & Care", 3.8, 13.5, "SUP-06", 540),
    ("Koivu Hand Cream Trio", "Beauty & Care", 3.1, 11.9, "SUP-06", 900),
    ("Marja Berry Lip Balm", "Beauty & Care", 1.3, 4.9, "SUP-06", 720),
    ("Sauna Body Scrub", "Beauty & Care", 3.6, 12.9, "SUP-06", 540),
    ("Sade Repair Shampoo", "Beauty & Care", 3.3, 10.9, "SUP-06", 900),
    ("Havu Pine Shower Gel", "Beauty & Care", 2.2, 7.9, "SUP-06", 900),
    ("Valo LED Desk Lamp", "Office", 12.0, 26.0, "SUP-07", None),
    ("Linja A4 Notebook 5-pack", "Office", 5.5, 11.9, "SUP-07", None),
    ("Kirja Ergonomic Mouse", "Office", 9.0, 19.9, "SUP-02", None),
    ("Tolppa Desk Mat XL", "Office", 18.0, 36.0, "SUP-07", None),
    ("Paperi Copy Paper 2500", "Office", 11.0, 19.0, "SUP-07", None),
    ("Pinta Monitor Stand", "Office", 15.0, 31.0, "SUP-07", None),
    ("Kyna Gel Pen 12-pack", "Office", 2.6, 6.9, "SUP-07", None),
    ("Retki Daypack 30L", "Sports & Outdoor", 17.0, 39.0, "SUP-08", None),
    ("Polku Trekking Poles", "Sports & Outdoor", 14.0, 32.0, "SUP-08", None),
    ("Hiihto Ski Wax Kit", "Sports & Outdoor", 9.0, 21.0, "SUP-08", None),
    ("Kuntoa Yoga Mat", "Sports & Outdoor", 8.0, 21.0, "SUP-08", None),
    ("Rinne Insulated Bottle 750", "Sports & Outdoor", 7.5, 19.0, "SUP-08", None),
    ("Leiri Two-person Tent", "Sports & Outdoor", 58.0, 119.0, "SUP-08", None),
    ("Pyora Bike Light Set", "Sports & Outdoor", 6.5, 17.0, "SUP-03", None),
]
DISCONTINUED = {  # name -> date the range is discontinued
    "Taivo Portable Speaker": "2024-09-15",
    "Ruska Fleece Pullover": "2025-03-01",
    "Hylo Gaming Headset": "2025-06-30",
}
LAUNCHED = {  # name -> launch date inside the period
    "Aava Air Purifier": "2023-09-01",
    "Sorva 4K Action Camera": "2024-03-01",
    "Leiri Two-person Tent": "2024-05-01",
}
SLOW_MOVERS = {  # name -> popularity factor
    "Tolppa Desk Mat XL": 0.18, "Hiihto Ski Wax Kit": 0.15, "Oravi Knife Set": 0.25,
    "Harmaa Linen Throw": 0.22, "Pinta Monitor Stand": 0.30,
}
LEAN_POLICY = {
    "Lumra Wireless Earbuds", "Kelmo Power Bank 20000", "Tuuli Merino Base Layer",
    "Lumo Moisturising Cream", "Valo LED Desk Lamp", "Kuura Thermal Socks 3-pack",
    "Rinne Insulated Bottle 750", "Nimbo Electric Kettle", "Norvi USB-C Hub",
}
HEAVY_POLICY = set(SLOW_MOVERS) | {"Lykke Ceramic Mug Set", "Marja Berry Lip Balm", "Polku Trekking Poles"}
POLICIES = {  # safety factor z, review days, cover days per order
    "lean": (0.9, 3, 28),
    "good": (1.65, 7, 35),
    "heavy": (2.8, 14, 100),
}
RETURN_PRONE = {  # SKU return rate multiplier
    "Veltix Smart Watch": 2.5, "Pilvi Denim Jeans": 1.8,
    "Aava Air Purifier": 2.2, "Retki Daypack 30L": 1.8,
}

CAMPAIGNS = [
    # name, (start month, day), (end month, day), categories, discount, channel scope
    ("Winter Clearance", (1, 5), (1, 19), ["Apparel", "Sports & Outdoor"], 0.30, "All"),
    ("Valentine Beauty", (2, 7), (2, 14), ["Beauty & Care"], 0.15, "All"),
    ("Spring Home Refresh", (4, 10), (4, 24), ["Home & Kitchen"], 0.15, "All"),
    ("Midsummer Sale", (6, 15), (6, 25), ["Apparel", "Sports & Outdoor"], 0.25, "All"),
    ("Summer Clearance", (7, 15), (7, 31), ["Apparel", "Home & Kitchen"], 0.30, "All"),
    ("Back to Office", (8, 15), (8, 31), ["Office"], 0.12, "All"),
    ("Back to Office Tech", (8, 15), (8, 31), ["Electronics"], 0.10, "Online"),
    ("Singles Day", (11, 10), (11, 12), ["Electronics"], 0.15, "Online"),
    ("Gift Season", (12, 1), (12, 12), ["Beauty & Care", "Home & Kitchen"], 0.12, "All"),
    ("Boxing Day Sale", (12, 26), (12, 31), "ALL", 0.25, "All"),
]
BLACK_FRIDAY_DISCOUNT = {2023: 0.25, 2024: 0.30, 2025: 0.30}


@dataclass
class Config:
    seed: int = 20260101
    start: str = "2023-01-01"
    end: str = "2025-12-31"
    n_customers: int = 4000
    n_business: int = 60
    events_per_sku_day: float = 1.1


def charm(x: float) -> float:
    """Round to a shop-style price such as 48.99 or 14.99."""
    if x < 20:
        return round(round(x * 2) / 2 - 0.01, 2)
    return round(round(x) - 0.01, 2)


def black_friday(year: int) -> pd.Timestamp:
    thursdays = [d for d in calendar.Calendar().itermonthdates(year, 11)
                 if d.month == 11 and d.weekday() == 3]
    return pd.Timestamp(thursdays[3]) + pd.Timedelta(days=1)


def build_promotions(years: list[int], rng: np.random.Generator) -> pd.DataFrame:
    categories = sorted(SEASON)
    rows = []
    for year in years:
        for name, (sm, sd), (em, ed), cats, disc, scope in CAMPAIGNS:
            for cat in (categories if cats == "ALL" else cats):
                rows.append((name, pd.Timestamp(year, sm, sd), pd.Timestamp(year, em, ed), cat, disc, scope))
        bf = black_friday(year)
        for cat in categories:
            rows.append(("Black Friday Week", bf - pd.Timedelta(days=4), bf + pd.Timedelta(days=3),
                         cat, BLACK_FRIDAY_DISCOUNT.get(year, 0.25), "All"))
    promos = pd.DataFrame(rows, columns=["campaign", "start_date", "end_date", "category",
                                         "discount_pct", "channel_scope"])
    promos = promos.sort_values(["start_date", "category"]).reset_index(drop=True)
    promos.insert(0, "promo_id", [f"PRM-{i + 1:03d}" for i in range(len(promos))])
    # the promotion's own pull on top of the price effect, drawn once per promotion
    promos["buzz"] = rng.uniform(0.95, 1.25, len(promos)).round(3)
    return promos


def build_suppliers() -> pd.DataFrame:
    return pd.DataFrame(SUPPLIERS, columns=["supplier_id", "supplier_name", "country",
                                            "lead_time_days_avg", "lead_time_days_sd"])


def build_products(rng: np.random.Generator, cfg: Config) -> pd.DataFrame:
    sup = {s[0]: s for s in SUPPLIERS}
    rows = []
    for i, (name, cat, cost, price, sid, shelf) in enumerate(PRODUCTS):
        s = sup[sid]
        lt_avg = max(5, int(round(s[3] + rng.integers(-3, 4))))
        lt_sd = round(float(s[4]) * rng.uniform(0.8, 1.3), 1)
        moq = int(rng.choice([6, 12, 24, 48] if price < 20 else [4, 6, 12, 24]))
        pop = float(np.exp(rng.normal(0, 0.55))) * (price ** -0.35)
        if name in SLOW_MOVERS:
            pop = SLOW_MOVERS[name] * 0.6 * price ** -0.35
        policy = "heavy" if (name in HEAVY_POLICY or name in DISCONTINUED) else "lean" if name in LEAN_POLICY else "good"
        rows.append({
            "sku": f"SKU-{2001 + i}", "product_name": name, "category": cat,
            "supplier_id": sid, "unit_cost_2023": cost, "list_price_2023": charm(price),
            "lead_time_days_avg": lt_avg, "lead_time_days_sd": lt_sd, "min_order_qty": moq,
            "shelf_life_days": shelf if shelf else "",
            "launch_date": LAUNCHED.get(name, cfg.start), "discontinued_date": DISCONTINUED.get(name, ""),
            "stocking_policy": policy, "_pop": pop,
        })
    products = pd.DataFrame(rows)
    products["_pop"] = products["_pop"] / products["_pop"].mean()
    return products


def build_price_history(products: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    rows = []
    for _, p in products.iterrows():
        for year in years:
            k = year - years[0]
            price = charm(p.list_price_2023 * (1 + PRICE_GROWTH[p.category]) ** k) if k else p.list_price_2023
            cost = p.unit_cost_2023 * (1 + COST_GROWTH[p.category]) ** k
            shock = (1 + COST_SHOCK) if (p.supplier_id == COST_SHOCK_SUPPLIER and year > 2024) else 1.0
            rows.append((p.sku, pd.Timestamp(year, 1, 1), price, round(cost * shock, 2)))
            if p.supplier_id == COST_SHOCK_SUPPLIER and year == 2024:
                rows.append((p.sku, pd.Timestamp(COST_SHOCK_DATE), price, round(cost * (1 + COST_SHOCK), 2)))
    hist = pd.DataFrame(rows, columns=["sku", "effective_from", "list_price", "unit_cost"])
    return hist.sort_values(["sku", "effective_from"]).reset_index(drop=True)


def build_customers(cfg: Config, dates: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    n_cons = cfg.n_customers - cfg.n_business
    n_pre = int(n_cons * 0.33)
    pre = pd.Timestamp(cfg.start) - pd.to_timedelta(rng.integers(1, 1100, n_pre), unit="D")
    # signups in the period grow over time and bunch up before the holidays
    month_w = np.array([1 + 0.5 * (d.month in (11, 12)) + 0.8 * (d - dates[0]).days / 365 for d in dates])
    month_w = month_w / month_w.sum()
    new = dates[rng.choice(len(dates), n_cons - n_pre, p=month_w)]
    signup = list(pre) + list(new)
    business_signup = pd.Timestamp(cfg.start) - pd.to_timedelta(rng.integers(30, 900, cfg.n_business), unit="D")
    region_names = list(REGIONS)
    region_p = np.array(list(REGIONS.values()))
    cons_region = rng.choice(region_names, n_cons, p=region_p)
    biz_region = rng.choice(region_names, cfg.n_business, p=region_p)
    acq = rng.choice(["Online", "Retail", "Marketplace"], n_cons, p=[0.42, 0.36, 0.22])
    cust = pd.DataFrame({
        "signup_date": signup + list(business_signup),
        "region": list(cons_region) + list(biz_region),
        "customer_type": ["Consumer"] * n_cons + ["Business"] * cfg.n_business,
        "acquisition_channel": list(acq) + ["Wholesale"] * cfg.n_business,
    })
    cust = cust.sort_values(["signup_date", "customer_type"]).reset_index(drop=True)
    cust.insert(0, "customer_id", [f"C{i + 1:05d}" for i in range(len(cust))])
    return cust


def channel_matrix(dates: pd.DatetimeIndex) -> np.ndarray:
    """Share of events by day and channel, shape (T, 4)."""
    out = np.zeros((len(dates), 4))
    years = sorted(CHANNEL_SHARE)
    for i, d in enumerate(dates):
        y = min(max(d.year, years[0]), years[-1])
        out[i] = CHANNEL_SHARE[y]
    return out


def dow_matrix(dates: pd.DatetimeIndex) -> np.ndarray:
    out = np.zeros((len(dates), 4))
    for j, ch in enumerate(CHANNELS):
        w = np.array(DOW[ch], dtype=float)
        w = w / w.mean()
        out[:, j] = w[dates.dayofweek]
    return out


def promo_arrays(promos: pd.DataFrame, dates: pd.DatetimeIndex, rng: np.random.Generator):
    """For each category: discount, buzz and promo row index by day and channel,
    plus the post-promotion dip multiplier."""
    T = len(dates)
    out = {}
    for cat in SEASON:
        disc = np.zeros((T, 4))
        buzz = np.ones((T, 4))
        idx = np.full((T, 4), -1, dtype=int)
        dip = np.ones((T, 4))
        sub = promos[promos.category == cat]
        for pi, p in sub.iterrows():
            in_range = (dates >= p.start_date) & (dates <= p.end_date)
            chans = [0, 1, 2] if p.channel_scope == "All" else [0]
            for c in chans:
                better = in_range & (p.discount_pct > disc[:, c])
                disc[better, c] = p.discount_pct
                buzz[better, c] = p.buzz
                idx[better, c] = pi
            if p.discount_pct >= 0.20:
                after = np.where((dates > p.end_date) & (dates <= p.end_date + pd.Timedelta(days=10)))[0]
                for c in chans:
                    for k, t in enumerate(after):
                        dip[t, c] *= 1 - 0.20 * math.exp(-k / 4)
        out[cat] = (disc, buzz, idx, dip)
    return out


def simulate_sku(p, supplier, T, dates, rate_base, season_t, trend_t, week_noise, chan, dow, promo,
                 rng, cfg):
    """Demand and stock for one SKU. Returns sale lines, daily stock rows and purchase orders."""
    region_w = np.array(list(REGIONS.values()))
    disc, buzz, pidx, dip = promo
    launch = (pd.Timestamp(p.launch_date) - dates[0]).days
    active = np.ones(T)
    if launch > 0:
        t = np.arange(T)
        active = np.where(t < launch, 0.0, 0.3 + 0.7 * np.minimum(1.0, (t - launch) / 60.0))
    if p.discontinued_date:
        dd = (pd.Timestamp(p.discontinued_date) - dates[0]).days
        t = np.arange(T)
        active = active * np.where(t < dd, 1.0, np.maximum(0.0, 1 - (t - dd) / 90.0))
    elast = ELASTICITY[p.category]
    promo_mult = ((1 - disc) ** (-elast)) * buzz * dip
    day_rate = rate_base * p._pop * active * season_t * trend_t * week_noise            # (T,)
    lam = (day_rate[:, None, None] * chan[:, None, :] * dow[:, None, :] * promo_mult[:, None, :]
           * region_w[None, :, None])                                                    # (T, R, C)
    day_noise = rng.gamma(10, 1 / 10, size=(T, 1, 1))
    counts = rng.poisson(lam * day_noise)
    t_i, r_i, c_i = np.nonzero(counts)
    reps = counts[t_i, r_i, c_i]
    t_i, r_i, c_i = np.repeat(t_i, reps), np.repeat(r_i, reps), np.repeat(c_i, reps)
    n = len(t_i)
    qty = rng.choice([1, 2, 3], size=n, p=QTY_PROBS[p.category])
    wh = c_i == 3
    qty[wh] = rng.integers(1, 5, wh.sum()) * p.min_order_qty
    order = np.lexsort((rng.random(n), t_i))
    t_i, r_i, c_i, qty = t_i[order], r_i[order], c_i[order], qty[order]

    demand = np.bincount(t_i, weights=qty, minlength=T).astype(float)
    first_active = np.argmax(active > 0)
    fallback = max(demand[first_active:].mean(), 0.2)
    roll = pd.Series(demand).rolling(56, min_periods=14)
    d_hat = np.where(np.isnan(roll.mean().values), fallback, roll.mean().values)
    d_hat = np.maximum(d_hat, 0.25 * fallback)
    s_hat = np.where(np.isnan(roll.std().values), math.sqrt(fallback), roll.std().values)

    z, review, cover = POLICIES[p.stocking_policy]
    lt_avg, lt_sd, moq = float(p.lead_time_days_avg), float(p.lead_time_days_sd), int(p.min_order_qty)
    stop_order = T + 1
    if p.discontinued_date:
        stop_order = (pd.Timestamp(p.discontinued_date) - dates[0]).days - 30
    disrupt_lo = (pd.Timestamp(DISRUPTION_WINDOW[0]) - dates[0]).days
    disrupt_hi = (pd.Timestamp(DISRUPTION_WINDOW[1]) - dates[0]).days

    start_idx = np.searchsorted(t_i, np.arange(T), side="left")
    end_idx = np.searchsorted(t_i, np.arange(T), side="right")
    on_hand = int(math.ceil(fallback * 40 / moq) * moq)
    pipeline: list[tuple[int, int, int]] = []   # (arrival day, qty, po index)
    po_rows = []
    keep = np.ones(n, dtype=bool)
    stock_rows = np.zeros((T, 4), dtype=int)      # on_hand, on_order, sold, lost
    for t in range(T):
        if t < launch:
            continue
        if t == launch and launch > 0:
            on_hand = int(math.ceil(fallback * 45 / moq) * moq)
        arrived = [x for x in pipeline if x[0] <= t]
        if arrived:
            on_hand += sum(x[1] for x in arrived)
            pipeline = [x for x in pipeline if x[0] > t]
        s, e = start_idx[t], end_idx[t]
        sold = lost = 0
        if e > s:
            q = qty[s:e]
            if q.sum() <= on_hand:
                sold = int(q.sum())
            else:
                avail = on_hand
                for j in range(s, e):
                    if qty[j] <= avail:
                        avail -= qty[j]
                        sold += int(qty[j])
                    elif c_i[j] == 3 and avail > 0:      # a wholesale line is filled as far as stock goes
                        lost += int(qty[j]) - avail
                        qty[j] = avail
                        sold += avail
                        avail = 0
                    else:
                        keep[j] = False
                        lost += int(qty[j])
            on_hand -= sold
        on_order = sum(x[1] for x in pipeline)
        if t < stop_order:
            rp = d_hat[t] * (lt_avg + review) + z * s_hat[t] * math.sqrt(lt_avg + review)
            if on_hand + on_order <= rp:
                q_order = max(moq, int(math.ceil(d_hat[t] * cover / moq) * moq))
                lead = max(2, int(round(rng.normal(lt_avg, lt_sd))))
                if p.supplier_id == DISRUPTED_SUPPLIER and disrupt_lo <= t <= disrupt_hi and rng.random() < 0.7:
                    lead += int(rng.integers(10, 26))
                arrive = t + lead
                promised = t + int(round(lt_avg))
                po_rows.append((t, promised, arrive, q_order))
                pipeline.append((arrive, q_order, len(po_rows) - 1))
                on_order += q_order
        stock_rows[t] = (on_hand, on_order, sold, lost)

    lines = dict(t=t_i[keep], r=r_i[keep], c=c_i[keep], qty=qty[keep])
    chosen = pidx[lines["t"], lines["c"]]
    lines["promo_idx"] = np.where(lines["c"] == 3, -1, chosen)
    lines["disc"] = np.where(lines["promo_idx"] >= 0, disc[lines["t"], lines["c"]], 0.0)
    return lines, stock_rows, po_rows, launch


def assign_orders(lines: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Group lines of the same day, region and channel into orders and number them in date order."""
    lines = lines.sort_values(["t", "r", "c", "tie"], kind="stable").reset_index(drop=True)
    key = (lines.t.values * 10 + lines.r.values) * 4 + lines.c.values
    starts = np.r_[0, np.nonzero(np.diff(key))[0] + 1]
    counts = np.diff(np.r_[starts, len(lines)])
    next_order = 0
    order_idx = np.zeros(len(lines), dtype=np.int64)
    sizes_pool = np.array([1, 2, 3, 4, 5])
    for s, n in zip(starts, counts):
        if lines.c.values[s] == 3:
            ids = np.arange(n)
        else:
            sizes = rng.choice(sizes_pool, size=n, p=[0.60, 0.22, 0.10, 0.05, 0.03])
            ids = np.searchsorted(np.cumsum(sizes), np.arange(n), side="right")
        order_idx[s:s + n] = ids + next_order
        next_order += ids.max() + 1
    lines["order_idx"] = order_idx
    # number orders by date with a random order inside each day
    orders = lines.groupby("order_idx").agg(t=("t", "first"), r=("r", "first"), c=("c", "first")).reset_index()
    orders["rand"] = rng.random(len(orders))
    orders = orders.sort_values(["t", "rand"], kind="stable").reset_index(drop=True)
    orders["order_no"] = np.arange(1, len(orders) + 1)
    lines = lines.merge(orders[["order_idx", "order_no"]], on="order_idx")
    return lines.sort_values(["order_no", "sku"], kind="stable").reset_index(drop=True), orders


def assign_customers(orders: pd.DataFrame, customers: pd.DataFrame, dates: pd.DatetimeIndex,
                     rng: np.random.Generator) -> pd.DataFrame:
    region_names = list(REGIONS)
    start = dates[0]
    signup = (customers.signup_date - start).dt.days.values
    life = np.where(customers.customer_type == "Business", 10_000, rng.exponential(600, len(customers)).astype(int) + 30)
    end_day = signup + life
    weight = np.clip(rng.gamma(0.9, 1 / 0.9, len(customers)), 0.05, 2.5)
    biz = (customers.customer_type == "Business").values
    pref = customers.acquisition_channel.map({c: i for i, c in enumerate(CHANNELS)}).values
    cust_region = customers.region.map({r: i for i, r in enumerate(region_names)}).values
    cust_idx_by_region = [np.nonzero(cust_region == r)[0] for r in range(len(region_names))]
    chosen = np.empty(len(orders), dtype=np.int64)
    orders = orders.reset_index(drop=True)
    grouped = orders.groupby(["t", "r", "c"]).indices
    for (t, r, c), pos in grouped.items():
        cand = cust_idx_by_region[r]
        is_b = biz[cand]
        base_mask = is_b if c == 3 else ~is_b
        live = base_mask & (signup[cand] <= t) & (end_day[cand] >= t)
        if not live.any():
            live = base_mask & (signup[cand] <= t)
        if not live.any():
            live = base_mask
        age = np.maximum(t - signup[cand], 0)
        w = weight[cand] * live * (1 + 8 * np.exp(-age / 25)) * (1 + 1.5 * (pref[cand] == c))
        cdf = np.cumsum(w)
        draws = rng.random(len(pos)) * cdf[-1]
        chosen[pos] = cand[np.searchsorted(cdf, draws, side="right").clip(max=len(cand) - 1)]
    orders["cust_idx"] = chosen
    return orders


def generate(cfg: Config | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or Config()
    rng = np.random.default_rng(cfg.seed)
    dates = pd.date_range(cfg.start, cfg.end, freq="D")
    T = len(dates)
    years = sorted(set(dates.year))

    suppliers = build_suppliers()
    products = build_products(rng, cfg)
    price_hist = build_price_history(products, years)
    promos = build_promotions(years, rng)
    customers = build_customers(cfg, dates, rng)
    sup = {s[0]: s for s in SUPPLIERS}

    chan = channel_matrix(dates)
    dow = dow_matrix(dates)
    parr = promo_arrays(promos, dates, rng)
    t_years = (dates - dates[0]).days.values / 365.0

    # weekly wobble shared by all channels so that months do not look too smooth
    n_weeks = T // 7 + 2
    week_factor = np.exp(rng.normal(0, 0.10, n_weeks))
    week_noise_all = week_factor[(np.arange(T) // 7)]

    all_lines, stock_frames, po_frames = [], [], []
    for _, p in products.iterrows():
        cat = p.category
        s = np.array(SEASON[cat], dtype=float)
        s = s / s.mean()
        season_t = s[dates.month.values - 1]
        trend_t = (1 + DEMAND_GROWTH[cat]) ** t_years
        week_noise = week_noise_all * np.exp(rng.normal(0, 0.05, T))
        lines, stock_rows, po_rows, launch = simulate_sku(
            p, sup[p.supplier_id], T, dates, cfg.events_per_sku_day, season_t, trend_t,
            week_noise, chan, dow, parr[cat], rng, cfg)
        ldf = pd.DataFrame(lines)
        ldf["sku"] = p.sku
        ldf["tie"] = rng.random(len(ldf))
        all_lines.append(ldf)
        first = max(launch, 0)
        sf = pd.DataFrame(stock_rows[first:], columns=["on_hand", "on_order", "units_sold", "lost_units"])
        sf.insert(0, "date", dates[first:])
        sf.insert(1, "sku", p.sku)
        stock_frames.append(sf)
        for k, (t_order, t_prom, t_arr, q_order) in enumerate(po_rows):
            po_frames.append((p.sku, p.supplier_id, dates[0] + pd.Timedelta(days=t_order),
                              dates[0] + pd.Timedelta(days=t_prom),
                              dates[0] + pd.Timedelta(days=t_arr), q_order))

    lines = pd.concat(all_lines, ignore_index=True)
    lines, orders = assign_orders(lines, rng)
    orders = assign_customers(orders, customers, dates, rng)
    # guest orders carry no customer id: marketplace orders, most retail sales and half of online orders
    guest_rng = np.random.default_rng(cfg.seed + 7)
    p_guest = np.array([GUEST_SHARE[c] for c in CHANNELS])[orders.c.values]
    orders.loc[guest_rng.random(len(orders)) < p_guest, "cust_idx"] = -1
    lines = lines.merge(orders[["order_no", "cust_idx"]], on="order_no")
    lines = lines.sort_values(["order_no", "sku"], kind="stable").reset_index(drop=True)
    lines["line_no"] = lines.groupby("order_no").cumcount() + 1

    region_names = list(REGIONS)
    lines["order_date"] = dates[lines.t.values]
    lines["order_id"] = "ORD-" + lines.order_no.astype(str).str.zfill(6)
    lines["customer_id"] = np.where(lines.cust_idx.values < 0, "GUEST", customers.customer_id.values[lines.cust_idx.values.clip(min=0)])
    lines["region"] = np.array(region_names)[lines.r.values]
    lines["channel"] = np.array(CHANNELS)[lines.c.values]
    lines = lines.rename(columns={"qty": "quantity"})

    # list price and unit cost on the day of the sale
    lines = lines.sort_values("order_date", kind="stable")
    hist = price_hist.sort_values("effective_from")
    lines = pd.merge_asof(lines, hist, left_on="order_date", right_on="effective_from", by="sku")
    lines = lines.sort_values(["order_no", "line_no"]).reset_index(drop=True)

    # discounts: promotion first, then wholesale volume discount, then the odd coupon
    base_disc = lines.disc.values.copy()
    wholesale = lines.c.values == 3
    base_disc[wholesale] = np.round(0.10 + 0.0015 * np.minimum(lines.quantity.values[wholesale], 60), 2)
    coupon = (~wholesale) & (lines.promo_idx.values < 0) & (rng.random(len(lines)) < 0.06)
    base_disc[coupon] = rng.choice([0.05, 0.10], coupon.sum(), p=[0.6, 0.4])
    lines["discount_pct"] = np.round(base_disc, 2)
    lines["promo_id"] = np.where(lines.promo_idx.values >= 0, promos.promo_id.values[lines.promo_idx.values.clip(min=0)], "")
    lines["net_revenue"] = (lines.quantity * lines.list_price * (1 - lines.discount_pct)).round(2)

    # order level costs, spread over the lines by units
    order_units = lines.groupby("order_id").quantity.transform("sum")
    share = lines.quantity / order_units
    ch = lines.channel
    ship_order = np.where(ch == "Online", 5.20 + 0.60 * (order_units - 1),
                 np.where(ch == "Marketplace", 3.80, 0.0))
    ship = ship_order * share + np.where(ch == "Wholesale", 0.015 * lines.net_revenue, 0.0)
    lines["shipping_cost"] = np.round(ship, 2)
    fee_pct = ch.map({"Online": 0.018, "Retail": 0.009, "Marketplace": 0.015, "Wholesale": 0.0})
    fee_fixed = np.where(ch == "Online", 0.25 * share, 0.0)
    lines["payment_fee"] = np.round(lines.net_revenue * fee_pct + fee_fixed, 2)
    lines["platform_fee"] = np.round(np.where(ch == "Marketplace", 0.11 * lines.net_revenue, 0.0), 2)

    sales = lines[["order_id", "line_no", "order_date", "customer_id", "region", "channel", "sku",
                   "quantity", "list_price", "discount_pct", "promo_id", "net_revenue", "unit_cost",
                   "shipping_cost", "payment_fee", "platform_fee"]].copy()
    sales["order_date"] = sales.order_date.dt.strftime("%Y-%m-%d")

    returns = build_returns(lines, products, rng, dates)
    stock = pd.concat(stock_frames, ignore_index=True)
    stock["date"] = stock.date.dt.strftime("%Y-%m-%d")
    stock["stockout_flag"] = (stock.lost_units > 0).astype(int)
    pos = pd.DataFrame(po_frames, columns=["sku", "supplier_id", "order_date", "promised_date", "received_date", "quantity"])
    pos = pos.sort_values(["order_date", "sku"]).reset_index(drop=True)
    pos = pd.merge_asof(pos, hist.rename(columns={"effective_from": "order_date"})[["sku", "order_date", "unit_cost"]],
                        on="order_date", by="sku")
    pos["delay_days"] = (pos.received_date - pos.promised_date).dt.days
    pos.insert(0, "po_id", [f"PO-{i + 1:05d}" for i in range(len(pos))])
    # purchase orders that arrive after the last day are still open
    pos["received_date"] = pos.received_date.where(pos.received_date <= dates[-1])
    pos["delay_days"] = pos.delay_days.where(pos.received_date.notna())
    for col in ["order_date", "promised_date", "received_date"]:
        pos[col] = pos[col].dt.strftime("%Y-%m-%d")
    pos = pos[["po_id", "sku", "supplier_id", "order_date", "promised_date", "received_date",
               "quantity", "unit_cost", "delay_days"]]

    products_out = products.drop(columns=["_pop"])
    products_out["launch_date"] = products_out.launch_date.astype(str)
    customers_out = customers.copy()
    customers_out["signup_date"] = customers_out.signup_date.dt.strftime("%Y-%m-%d")
    promos_out = promos.drop(columns=["buzz"]).copy()
    for col in ["start_date", "end_date"]:
        promos_out[col] = promos_out[col].dt.strftime("%Y-%m-%d")
    hist_out = price_hist.copy()
    hist_out["effective_from"] = hist_out.effective_from.dt.strftime("%Y-%m-%d")

    return {
        "products": products_out, "suppliers": suppliers, "customers": customers_out,
        "promotions": promos_out, "price_history": hist_out, "sales_lines": sales,
        "returns": returns, "inventory_daily": stock, "purchase_orders": pos,
    }


def build_returns(lines: pd.DataFrame, products: pd.DataFrame, rng: np.random.Generator,
                  dates: pd.DatetimeIndex) -> pd.DataFrame:
    name_of = dict(zip(products.sku, products.product_name))
    cat_of = dict(zip(products.sku, products.category))
    cats = lines.sku.map(cat_of)
    prone = lines.sku.map(name_of).map(RETURN_PRONE).fillna(1.0)
    prob = cats.map(RETURN_RATE) * lines.channel.map(RETURN_CHANNEL_FACTOR) * prone
    hit = rng.random(len(lines)) < prob.values
    r = lines[hit].copy()
    r["category"] = cats[hit].values
    full = rng.random(len(r)) < 0.75
    r["return_qty"] = np.where(full | (r.quantity == 1), r.quantity, rng.integers(1, r.quantity.clip(lower=2)))
    gap = np.clip(np.round(rng.gamma(3.0, 4.0, len(r))).astype(int), 2, 45)
    r["return_date"] = r.order_date + pd.to_timedelta(gap, unit="D")
    reasons = []
    for cat in r.category:
        names, p = zip(*RETURN_REASONS[cat])
        reasons.append(rng.choice(names, p=p))
    r["reason"] = reasons
    r = r[r.return_date <= dates[-1]].copy()
    unit_net = r.net_revenue / r.quantity
    r["refund_amount"] = (unit_net * r.return_qty).round(2)
    r["restocked"] = [int(rng.random() < RESTOCK_PROB.get(x, 0.85)) for x in r.reason]
    r["return_shipping_cost"] = r.channel.map(RETURN_SHIPPING).values
    r = r.sort_values(["return_date", "order_id", "line_no"]).reset_index(drop=True)
    out = pd.DataFrame({
        "return_id": [f"RET-{i + 1:05d}" for i in range(len(r))],
        "order_id": r.order_id, "line_no": r.line_no, "sku": r.sku,
        "return_date": r.return_date.dt.strftime("%Y-%m-%d"), "return_qty": r.return_qty,
        "reason": r.reason, "refund_amount": r.refund_amount, "restocked": r.restocked,
        "return_shipping_cost": r.return_shipping_cost,
    })
    return out


def make_dirty(sales: pd.DataFrame, customers: pd.DataFrame, cfg: Config,
               rng: np.random.Generator) -> pd.DataFrame:
    """Copy the sales lines and spoil them in ways an analyst meets in real exports.

    Every defect can be repaired from the other columns or other rows, so the cleaning
    script can return the original table exactly. The test rows and duplicates are removed.
    """
    raw = sales.astype(object).copy()
    n = len(raw)
    pool = list(rng.permutation(n))

    def take(share: float, allowed=None) -> np.ndarray:
        k = int(round(n * share))
        out, rest = [], []
        for i in pool:
            if len(out) < k and (allowed is None or allowed[i]):
                out.append(i)
            else:
                rest.append(i)
        pool[:] = rest
        return np.array(out, dtype=int)

    multi = (sales.groupby("order_id").order_id.transform("size") >= 2).values
    order_dates = sales.groupby("order_id").order_date.first()
    ids = order_dates.index.values
    d = order_dates.values
    same = np.zeros(len(ids), dtype=bool)
    same[2:-2] = (d[1:-3] == d[2:-2]) & (d[2:-2] == d[3:-1]) & (d[0:-4] == d[2:-2]) & (d[4:] == d[2:-2])
    safe_order = pd.Series(same, index=ids)
    date_ok = sales.order_id.map(safe_order).fillna(False).values

    i = take(0.012)
    raw.loc[i, "channel"] = [rng.choice([lambda x: x.upper(), lambda x: x.lower(), lambda x: " " + x, lambda x: x + " "])(v)
                             for v in raw.loc[i, "channel"]]
    i = take(0.004)
    raw.loc[i, "sku"] = raw.loc[i, "sku"].str.lower()
    i = take(0.006)
    raw.loc[i, "list_price"] = raw.loc[i, "list_price"].map(lambda x: f"{x:.2f}".replace(".", ","))
    i = take(0.008)
    raw.loc[i, "order_date"] = pd.to_datetime(raw.loc[i, "order_date"]).dt.strftime("%d.%m.%Y")
    # a few year typos, one at a time and never next to another one
    cand = take(0.0025, allowed=date_ok & ~multi)
    cand = np.array(sorted(cand))
    last_order = -10
    for j in cand:
        o = int(raw.loc[j, "order_id"].split("-")[1])
        if o - last_order < 5:
            pool.append(j)
            continue
        last_order = o
        y = raw.loc[j, "order_date"][:4]
        raw.loc[j, "order_date"] = (y[0] + y[2] + y[1] + y[3] if rng.random() < 0.5 else "19" + y[2:]) + raw.loc[j, "order_date"][4:]
    i = take(0.005, allowed=(sales.customer_id != "GUEST").values | multi)
    first_of_order = ~raw.loc[i, "order_id"].duplicated().values
    pool.extend(i[~first_of_order])
    i = i[first_of_order]
    raw.loc[i, "region"] = ""
    i = take(0.004, allowed=multi)
    first_of_order = ~raw.loc[i, "order_id"].duplicated().values   # keep one blank per order
    pool.extend(i[~first_of_order])
    i = i[first_of_order]
    raw.loc[i, "customer_id"] = ""
    i = take(0.004)
    raw.loc[i, "discount_pct"] = ""
    i = take(0.002)
    raw.loc[i, "quantity"] = -raw.loc[i, "quantity"].astype(int)

    dup = rng.choice(n, int(round(n * 0.005)), replace=False)
    raw = pd.concat([raw, raw.iloc[dup]], ignore_index=True)
    tests = raw.iloc[:15].copy()
    tests["order_id"] = [f"TEST-{k + 1:04d}" for k in range(15)]
    tests["line_no"] = 1
    tests["quantity"] = 999
    tests["customer_id"] = "C00000"
    raw = pd.concat([raw, tests], ignore_index=True)
    raw["_k"] = raw.order_id.str.replace("TEST-", "ZZZ-")
    raw = raw.sort_values(["_k", "line_no"], kind="stable").drop(columns="_k").reset_index(drop=True)
    return raw


def write_tables(tables: dict[str, pd.DataFrame], dirty: pd.DataFrame, out: Path) -> None:
    (out / "raw").mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        if name == "sales_lines":
            continue  # written by tools/clean_data.py from the dirty export
        df.to_csv(out / f"{name}.csv", index=False)
    dirty.to_csv(out / "raw" / "sales_lines_dirty.csv", index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    ap.add_argument("--seed", type=int, default=Config.seed)
    args = ap.parse_args()
    cfg = Config(seed=args.seed)
    tables = generate(cfg)
    rng = np.random.default_rng(cfg.seed + 1)
    dirty = make_dirty(tables["sales_lines"], tables["customers"], cfg, rng)
    write_tables(tables, dirty, args.out)
    for name, df in tables.items():
        print(f"{name:16s} {len(df):>8,d} rows")
    print(f"{'sales_lines_dirty':16s} {len(dirty):>8,d} rows (data/raw)")


if __name__ == "__main__":
    main()
