import pandas as pd

import generate_data as g


def test_same_seed_gives_identical_tables(small, small_cfg):
    again = g.generate(small_cfg)
    for name, df in small.items():
        pd.testing.assert_frame_equal(df, again[name], check_exact=True)


def test_other_seed_gives_other_sales(small, small_cfg):
    other = g.generate(g.Config(seed=12, start=small_cfg.start, end=small_cfg.end, n_customers=1500, n_business=60))
    assert not small["sales_lines"].net_revenue.equals(other["sales_lines"].net_revenue)


def test_structure(small):
    p, s = small["products"], small["sales_lines"]
    assert len(p) >= 40 and p.category.nunique() == 6
    assert s.region.nunique() == 5 and set(s.channel) == set(g.CHANNELS)
    assert not s.duplicated(["order_id", "line_no"]).any()


def test_line_arithmetic_and_ranges(small):
    s = small["sales_lines"]
    assert (s.quantity > 0).all() and (s.list_price > 0).all()
    assert s.discount_pct.between(0, 0.40).all()
    assert (s.unit_cost < s.list_price).all()
    expected = (s.quantity * s.list_price * (1 - s.discount_pct)).round(2)
    assert (expected - s.net_revenue).abs().max() < 0.0051
    assert (s[["shipping_cost", "payment_fee", "platform_fee"]] >= 0).all().all()


def test_stock_is_never_negative_and_reconciles(small):
    inv, s, po = small["inventory_daily"], small["sales_lines"], small["purchase_orders"]
    assert (inv.on_hand >= 0).all() and (inv.lost_units >= 0).all()
    sold = s.groupby(["sku", "order_date"]).quantity.sum()
    inv_sold = inv.set_index(["sku", "date"]).units_sold
    assert sold.rename_axis(["sku", "date"]).sort_index().equals(inv_sold[inv_sold > 0].sort_index())
    rec = po[po.received_date.notna()].groupby(["sku", "received_date"]).quantity.sum()
    rec.index.names = ["sku", "date"]
    inv = inv.sort_values(["sku", "date"]).reset_index(drop=True)
    inv["received"] = pd.Series(inv.set_index(["sku", "date"]).index.map(rec)).fillna(0).to_numpy()
    inv["prev"] = inv.groupby("sku").on_hand.shift()
    step = inv.dropna(subset=["prev"])
    assert (step.prev + step.received - step.units_sold - step.on_hand).abs().max() == 0


def test_orders_are_consistent(small):
    s, c = small["sales_lines"], small["customers"].set_index("customer_id")
    assert s.groupby("order_id")[["order_date", "customer_id", "region", "channel"]].nunique().max().max() == 1
    ident = s[s.customer_id != "GUEST"]
    assert ident.customer_id.isin(c.index).all()
    assert (ident.customer_id.map(c.region) == ident.region).all()
    assert (pd.to_datetime(ident.order_date) >= pd.to_datetime(ident.customer_id.map(c.signup_date))).all()
    assert (ident.channel == "Wholesale").eq(ident.customer_id.map(c.customer_type) == "Business").all()
    guest = s[s.customer_id == "GUEST"]
    assert (guest.channel != "Wholesale").all() and (s[s.channel == "Marketplace"].customer_id == "GUEST").all()


def test_returns_are_valid(small):
    s, r = small["sales_lines"], small["returns"]
    j = r.merge(s, on=["order_id", "line_no"])
    assert len(j) == len(r)
    assert (j.return_qty <= j.quantity).all() and (j.return_qty > 0).all()
    assert (pd.to_datetime(j.return_date) > pd.to_datetime(j.order_date)).all()
    assert (j.refund_amount <= j.net_revenue + 0.005).all()


def test_margins_are_believable(small):
    s = small["sales_lines"].merge(small["products"][["sku", "category"]], on="sku")
    s["gp"] = s.net_revenue - s.quantity * s.unit_cost
    by = s.groupby("category").apply(lambda d: d.gp.sum() / d.net_revenue.sum(), include_groups=False)
    assert by.between(0.25, 0.75).all()
    overall = s.gp.sum() / s.net_revenue.sum()
    assert 0.35 <= overall <= 0.60


def test_promotion_days_sell_more(small):
    s = small["sales_lines"].merge(small["products"][["sku", "category"]], on="sku")
    s = s[s.channel != "Wholesale"]
    promo = s.promo_id != ""
    daily = s.groupby(["category", "order_date", promo.rename("p")]).quantity.sum().reset_index()
    assert daily[daily.p].quantity.mean() > daily[~daily.p].quantity.mean()
