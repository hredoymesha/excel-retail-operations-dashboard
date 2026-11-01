import numpy as np
import pandas as pd
import pytest

import clean_data as cd
import generate_data as g


def as_text(df: pd.DataFrame, path) -> pd.DataFrame:
    df.to_csv(path, index=False)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def dirty_and_truth(small, small_cfg, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("clean")
    rng = np.random.default_rng(small_cfg.seed + 1)
    dirty = g.make_dirty(small["sales_lines"], small["customers"], small_cfg, rng)
    return as_text(dirty, tmp / "d.csv"), as_text(small["sales_lines"], tmp / "t.csv"), small["customers"].astype(str)


def test_cleaning_restores_the_original_table(dirty_and_truth, tmp_path):
    dirty, truth, customers = dirty_and_truth
    cleaned, log = cd.clean(dirty, customers, "2023-01-01", "2023-12-31")
    got = as_text(cleaned, tmp_path / "c.csv")
    pd.testing.assert_frame_equal(got.reset_index(drop=True), truth.reset_index(drop=True))


def test_every_rule_fires_and_is_logged(dirty_and_truth):
    dirty, _, customers = dirty_and_truth
    _, log = cd.clean(dirty, customers, "2023-01-01", "2023-12-31")
    summary = pd.DataFrame(log.summary)
    assert set(summary.rule) == {f"R{i:02d}" for i in range(1, 11)}
    assert (summary.rows_affected > 0).all()
    assert len(log.actions) == summary.rows_affected.sum()


def test_test_orders_and_duplicates_are_gone(dirty_and_truth):
    dirty, truth, customers = dirty_and_truth
    cleaned, _ = cd.clean(dirty, customers, "2023-01-01", "2023-12-31")
    assert not cleaned.order_id.str.startswith("TEST").any()
    assert not cleaned.duplicated(["order_id", "line_no"]).any()
    assert len(cleaned) == len(truth)


def test_cleaned_values_have_the_right_types(dirty_and_truth):
    dirty, _, customers = dirty_and_truth
    cleaned, _ = cd.clean(dirty, customers, "2023-01-01", "2023-12-31")
    assert (cleaned.quantity > 0).all()
    assert cleaned.discount_pct.between(0, 1).all()
    assert set(cleaned.channel) <= cd.CHANNELS
    assert cleaned.sku.str.match(r"^SKU-\d{4}$").all()
    assert pd.to_datetime(cleaned.order_date).between("2023-01-01", "2023-12-31").all()
    assert not (cleaned.region.str.strip() == "").any() and not (cleaned.customer_id.str.strip() == "").any()


def test_one_row_with_every_kind_of_dirt(dirty_and_truth):
    dirty, truth, customers = dirty_and_truth
    named = truth[truth.customer_id != "GUEST"].index[0]
    base = truth.iloc[[named, named + 1, named + 2]].copy()
    row = base.iloc[[0]].copy()
    row["channel"] = " ONLINE "
    row["sku"] = row.sku.str.lower()
    row["list_price"] = row.list_price.str.replace(".", ",", regex=False)
    row["quantity"] = "-" + row.quantity
    row["discount_pct"] = ""
    row["region"] = ""
    row["order_date"] = pd.to_datetime(row.order_date).dt.strftime("%d.%m.%Y")
    mixed = pd.concat([row, base.iloc[1:]], ignore_index=True)
    cleaned, log = cd.clean(mixed, customers, "2023-01-01", "2023-12-31")
    want = base.iloc[0]
    got = cleaned.iloc[0]
    assert got.channel == "Online" and got.sku == want.sku
    assert float(got.list_price) == float(want.list_price) and got.quantity == int(want.quantity)
    assert got.order_date == want.order_date
    assert abs(got.discount_pct - float(want.discount_pct)) < 0.011
    assert got.region == want.region


def test_unknown_channel_is_refused(dirty_and_truth):
    _, truth, customers = dirty_and_truth
    bad = truth.iloc[:3].copy()
    bad.loc[bad.index[0], "channel"] = "Telephone"
    with pytest.raises(AssertionError):
        cd.clean(bad, customers, "2023-01-01", "2023-12-31")


def test_clean_input_passes_through_unchanged(dirty_and_truth, tmp_path):
    _, truth, customers = dirty_and_truth
    cleaned, log = cd.clean(truth, customers, "2023-01-01", "2023-12-31")
    assert sum(r["rows_affected"] for r in log.summary) == 0
    pd.testing.assert_frame_equal(as_text(cleaned, tmp_path / "x.csv").reset_index(drop=True), truth.reset_index(drop=True))


def test_a_row_that_cannot_be_repaired_stops_the_script(dirty_and_truth):
    _, truth, customers = dirty_and_truth
    guest = truth[(truth.customer_id == "GUEST") & ~truth.order_id.duplicated(keep=False)].iloc[[0]].copy()
    guest["region"] = ""
    with pytest.raises(ValueError):
        cd.clean(pd.concat([guest, truth[~truth.order_id.isin(guest.order_id)].iloc[:3]], ignore_index=True), customers, "2023-01-01", "2023-12-31")
