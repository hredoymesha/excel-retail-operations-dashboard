import collections
import html
import os
import re
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import build_workbook
from analysis import common

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("wb") / "v2.xlsx"
    ctx = build_workbook.build(path)
    return path, ctx


def formulas(path):
    z = zipfile.ZipFile(path)
    names = {}
    wbxml = z.read("xl/workbook.xml").decode()
    for m in re.finditer(r'<sheet name="([^"]+)" sheetId="\d+"(?: state="\w+")? r:id="(rId\d+)"', wbxml):
        names[m.group(2)] = m.group(1)
    rels = z.read("xl/_rels/workbook.xml.rels").decode()
    target = {m.group(1): m.group(2) for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels)}
    target.update({m.group(2): m.group(1) for m in re.finditer(r'Target="([^"]+)"[^>]*Id="(rId\d+)"', rels)})
    out = {}
    for rid, sheet in names.items():
        xml = z.read("xl/" + target[rid].lstrip("/").replace("xl/", "")).decode("utf-8")
        out[sheet] = [html.unescape(f) for f in re.findall(r"<f>(.*?)</f>", xml, re.S)]
    return out


def test_sheets_and_names(built):
    path, ctx = built
    z = zipfile.ZipFile(path)
    wbxml = z.read("xl/workbook.xml").decode()
    sheets = re.findall(r'<sheet name="([^"]+)"', wbxml)
    for s in ["Start_Here", "Dashboard", "Profit_Margin", "Products", "Inventory", "Forecast", "Scenarios", "Customers",
              "Promotions", "Returns", "Checks", "Assumptions", "Notes", "Data_Monthly", "Data_Products"]:
        assert s in sheets
    for n in ["sel_year", "sel_region", "sel_channel", "sel_category", "svc_level", "m_net_revenue", "as_of", "el_used"]:
        assert f'name="{n}"' in wbxml
    assert wbxml.count("<definedName") > 100
    tables = [n for n in z.namelist() if n.startswith("xl/tables/")]
    assert len(tables) == 6


def test_formulas_are_live_and_plentiful(built):
    path, _ = built
    f = formulas(path)
    total = sum(len(v) for v in f.values())
    assert total > 40000
    for sheet in ["Dashboard", "Profit_Margin", "Products", "Inventory", "Forecast", "Scenarios", "Customers", "Promotions", "Returns", "Checks"]:
        assert len(f[sheet]) > 20, sheet
    assert len(f["Data_Monthly"]) == 0                      # data sheets hold values only


def test_dashboard_has_selectors_charts_and_print_setup(built):
    path, _ = built
    z = zipfile.ZipFile(path)
    names = z.namelist()
    sheet_xml = {n: z.read(n).decode() for n in names if n.startswith("xl/worksheets/sheet")}
    assert any(x.count("<dataValidation ") >= 4 for x in sheet_xml.values())
    assert len([n for n in names if n.startswith("xl/charts/chart")]) >= 14
    assert any("fitToPage" in x and 'orientation="landscape"' in x for x in sheet_xml.values())
    assert any("<conditionalFormatting" in x for x in sheet_xml.values())
    assert any("<pane " in x and 'state="frozen"' in x for x in sheet_xml.values())


ALLOWED = {str(i) for i in range(13)}


def test_no_hard_coded_assumptions_in_formulas(built):
    """Numbers in formulas may only be lookup positions, month numbers or counts that define the layout."""
    path, _ = built
    seen = collections.Counter()
    for sheet, fs in formulas(path).items():
        for f in fs:
            g = re.sub(r'"[^"]*"', '""', f)
            g = re.sub(r"'[^']*'!", "", g)
            g = re.sub(r"\$?[A-Z]{1,3}\$?\d+", "REF", g)
            g = re.sub(r"[A-Za-z_][A-Za-z_0-9.]*", "N", g)
            for m in re.findall(r"(?<![\w.])\d+\.?\d*", g):
                seen[m] += 1
    bad = {k: v for k, v in seen.items() if k not in ALLOWED}
    assert not bad, bad


def test_assumptions_are_named_and_on_one_sheet(built):
    _, ctx = built
    for n in ["svc_level", "review_days", "order_cost", "hold_rate", "abc_a", "abc_b", "xyz_x", "xyz_y", "holdout", "band_conf",
              "rfm_bins", "disc_rate", "check_tol", "over_days", "risk_cut"]:
        assert n in ctx.names
        assert ctx.names[n].startswith("Assumptions!")


@pytest.mark.skipif(not (ROOT / "outputs" / "workbook_parity.csv").exists(), reason="run tools/verify_workbook.py first (needs LibreOffice)")
def test_workbook_matches_pandas():
    df = pd.read_csv(ROOT / "outputs" / "workbook_parity.csv")
    assert len(df) > 1000
    bad = df[~df.passed]
    assert bad.empty, bad.head(10).to_string()
    assert set(df.run) == {"all_selected", "narrow_selection"}


@pytest.mark.skipif(os.environ.get("RUN_LIBREOFFICE") != "1", reason="set RUN_LIBREOFFICE=1 to recalculate with LibreOffice (several minutes)")
def test_recalculation_with_libreoffice(tmp_path):
    import verify_workbook
    rows = verify_workbook.verify("narrow", {"sel_year": 2024, "sel_region": "Tampere", "sel_channel": "Online", "sel_category": "Apparel"},
                                  build_workbook.load_all(), common.load_tables(), common.monthly_table(common.load_tables()), False, tmp_path)
    assert all(r["passed"] for r in rows)
