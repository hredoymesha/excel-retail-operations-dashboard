import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import generate_data as g  # noqa: E402


@pytest.fixture(scope="session")
def small_cfg():
    return g.Config(seed=11, start="2023-01-01", end="2023-12-31", n_customers=1500, n_business=60)


@pytest.fixture(scope="session")
def small(small_cfg):
    return g.generate(small_cfg)


@pytest.fixture(scope="session")
def tables():
    from analysis import common
    return common.load_tables()


@pytest.fixture(scope="session")
def monthly(tables):
    from analysis import common
    return common.monthly_table(tables)
