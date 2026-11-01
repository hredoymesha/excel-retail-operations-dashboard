import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
NUMBER = re.compile(r"[-+]?\d[\d,]*\.?\d*%?")


def numbers(text: str) -> set[str]:
    return {m.group(0).lstrip("+-").rstrip(".,") for m in NUMBER.finditer(text)}


@pytest.mark.skipif(not (ROOT / "outputs" / "key_findings.csv").exists(), reason="run analysis/run_all.py first")
def test_every_number_in_the_readme_findings_comes_from_the_scripts():
    findings = pd.read_csv(ROOT / "outputs" / "key_findings.csv")
    known = set()
    for text in findings.finding:
        known |= numbers(text)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## What came out")[1].split("## How it was built")[0]
    section = re.sub(r"`[^`]*`", "", section)                       # script names
    unknown = [n for n in numbers(section) if n not in known and n not in {"2024", "2025", "2023", "3"}]
    assert not unknown, unknown


def test_readme_is_short_and_has_the_notice():
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 150
    assert "made up" in " ".join(lines[:6]).lower()
