import numpy as np
import pandas as pd
import pytest

from analysis import common, metrics
from analysis.common import CATEGORIES


def test_monthly_table_matches_the_csv(tables, monthly):
    s = tables["sales_lines"]
    assert monthly.units.sum() == s.quantity.sum()
    assert monthly.net_revenue.sum() == pytest.approx(s.net_revenue.sum(), abs=0.01)
    assert monthly.refund_amount.sum() == pytest.approx(tables["returns"].refund_amount.sum(), abs=0.01)
    assert monthly.order_lines.sum() == len(s)


def test_kpi_pieces_add_up(monthly):
    p = metrics.pnl(monthly)
    assert p["gross_profit"] == pytest.approx(p["net_revenue"] - p["cogs"])
    parts = (p["net_revenue"] - p["cogs"] - p["shipping"] - p["payment_fee"] - p["platform_fee"] - p["refund_amount"]
             + p["restock_cogs"] - p["return_shipping"])
    assert p["contribution"] == pytest.approx(parts)
    by_channel = sum(metrics.pnl(x)["net_revenue"] for _, x in monthly.groupby("channel"))
    assert by_channel == pytest.approx(p["net_revenue"])


def test_filters_work(monthly):
    x = metrics.filter_monthly(monthly, 2024, "Tampere", "Online", "Apparel")
    assert set(x.year) == {2024} and set(x.region) == {"Tampere"} and set(x.channel) == {"Online"} and set(x.category) == {"Apparel"}
    assert metrics.filter_monthly(monthly).shape == monthly.shape


def test_abc_is_sorted_and_covers_every_sku(tables, monthly):
    g = metrics.sku_stats(tables, monthly)
    s = g.sort_values("rank")
    assert s.rev.is_monotonic_decreasing
    assert list(s.abc) == sorted(s.abc)                  # A first, then B, then C
    assert set(g.abc) == {"A", "B", "C"} and len(g) == 42
    assert s.cum_before.iloc[0] == 0 and s.cum_before.is_monotonic_increasing
    assert set(g.xyz) <= {"X", "Y", "Z"}
    assert (g.cv[g.xyz == "X"] <= metrics.A["xyz_x"]).all() and (g.cv[g.xyz == "Z"] > metrics.A["xyz_y"]).all()


def test_reorder_point_follows_the_formula(tables, monthly):
    inv = metrics.inventory_rules(tables, monthly)
    r = inv.iloc[0]
    from scipy.stats import norm
    lt = r.lead_time_days_avg + metrics.A["review_days"]
    ss = norm.ppf(metrics.A["svc_level"]) * np.sqrt(lt * r.sd_day ** 2 + (r.mu * r.lead_time_days_sd) ** 2)
    assert r.ss == pytest.approx(ss) and r.rop == pytest.approx(r.mu * lt + ss)
    assert (inv.eoq % inv.min_order_qty == 0).all() and (inv.eoq >= inv.min_order_qty).all()
    assert (inv.ss >= 0).all() and (inv.rop >= 0).all()
    assert set(inv.status) <= {"Reorder now", "Stock-out risk", "Overstock", "Obsolete stock", "Discontinued", "OK"}
    assert (inv.qty[inv.status != "Reorder now"] == 0).all()


def test_margin_bridge_closes_exactly(monthly):
    for filt in [(), ("Helsinki",), ("All", "Online"), ("All", "All", "Electronics")]:
        b = metrics.bridge(monthly, 2024, 2025, *filt)
        assert abs(b["gap"]) < 1e-6
        assert b["cm_a"] + sum(b[k] for k in ["volume", "mix", "price", "discount", "cost", "fees", "returns"]) == pytest.approx(b["cm_b"])


def test_forecast_picks_the_method_with_the_lowest_error(tables, monthly):
    fc = metrics.forecast_test(tables, monthly)
    for cat, o in fc.items():
        assert o["wape"][o["best"]] == min(o["wape"].values())
        assert len(o["forecast"]) == 12 and (o["forecast"] > 0).all()
        assert 0 < o["band"] < 1
    assert set(fc) == set(CATEGORIES)


def test_seasonal_index_averages_one(tables, monthly):
    cd = metrics.category_demand(tables, monthly)
    idx = metrics._season_index(cd["Electronics"], len(cd))
    assert idx.mean() == pytest.approx(1.0, abs=0.02)
    assert idx[11] > idx[6]                              # December above July


def test_rfm_scores_and_segments(tables):
    rf = metrics.rfm(tables)
    sc = rf["scored"]
    bins = metrics.A["rfm_bins"]
    for col in "RFM":
        assert sc[col].between(1, bins).all()
    assert set(sc.segment) <= {"Champions", "Loyal", "New or recent", "At risk", "Lost or hibernating", "Needs attention"}
    assert (sc.orders > 0).all() and (sc.rec >= 0).all()
    assert 0 < rf["repeat"] < 1 and 0 < rf["retention"] < 1


def test_cohort_retention_starts_at_one(tables):
    coh = metrics.cohort_matrix(tables)
    assert (coh[0] == 1.0).all()
    assert ((coh.fillna(0) >= 0) & (coh.fillna(0) <= 1)).all().all()


def test_promotion_break_even_is_consistent(tables):
    p = metrics.promo_metrics(tables).dropna(subset=["breakeven"])
    assert (p.breakeven > 0).all()
    d, m = p.discount_pct, p.m_list
    assert np.allclose((1 + p.breakeven) * (m - d), m)   # extra volume exactly pays for the discount


def test_returns_view(tables, monthly):
    rv = metrics.returns_view(tables, monthly)
    assert rv["cat"].ret.sum() == tables["returns"].return_qty.sum()
    assert (rv["top"].units >= metrics.A["min_ret_units"]).all()
    assert rv["top"].rate.is_monotonic_decreasing


def test_scenario_base_equals_the_window(tables, monthly):
    sc = metrics.scenario_results(tables, monthly)
    win = monthly[monthly.month >= "2025-01-01"].net_revenue.sum()
    assert sc["scn"]["Base"]["rev"] == pytest.approx(win)
    assert sc["scn"]["Demand shock"]["rev"] < sc["scn"]["Base"]["rev"]
    assert sc["scn"]["Supplier delay"]["risk"] > sc["scn"]["Base"]["risk"]
    assert sc["sens"][(0.0, 0.0)] == pytest.approx(sc["scn"]["Base"]["gp"])
