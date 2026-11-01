import csv
import re
from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[1] / "outputs"
LONG_DECIMAL = re.compile(r"^-?\d+\.\d{3,}$")


@pytest.mark.skipif(not OUT.exists(), reason="run analysis/run_all.py first")
def test_numbers_in_outputs_have_two_decimals():
    """The comparison file keeps full precision on purpose, because it records tiny differences."""
    bad = []
    for path in sorted(OUT.glob("*.csv")):
        if path.name == "workbook_parity.csv":
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                bad += [(path.name, cell) for cell in row if LONG_DECIMAL.match(cell)]
    assert not bad, bad[:5]
