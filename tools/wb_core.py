"""Helpers shared by the workbook builder modules."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

PAL = dict(navy="#1F3A5F", teal="#2A7F8E", slate="#5B6B7B", light="#EEF2F6", mid="#D5DEE8", line="#B8C4D0",
           input_fill="#FFF4D6", input_font="#1F4E9E", pass_fill="#DDEFE3", pass_font="#1B5E32",
           fail_fill="#F8DDDD", fail_font="#8A1C1C", warn_fill="#FCEFCF", warn_font="#7A5200",
           amber="#C98B2B", grey="#8895A3", white="#FFFFFF", text="#1B2631", sky="#A3B4C6")

EUR = '#,##0 "€";-#,##0 "€"'
EUR2 = '#,##0.00 "€";-#,##0.00 "€"'
INT = "#,##0"
DEC1 = "#,##0.0"
DEC2 = "#,##0.00"
PCT = "0.0%"
PCT0 = "0%"
DATE = "dd mmm yyyy"
MONTH = "mmm yyyy"

SHEETS = [
    ("Start_Here", PAL["navy"]), ("Dashboard", PAL["navy"]), ("Profit_Margin", PAL["teal"]),
    ("Products", PAL["teal"]), ("Inventory", PAL["teal"]), ("Forecast", PAL["teal"]),
    ("Scenarios", PAL["teal"]), ("Customers", PAL["teal"]), ("Promotions", PAL["teal"]),
    ("Returns", PAL["teal"]), ("Checks", PAL["teal"]), ("Assumptions", PAL["teal"]), ("Notes", PAL["teal"]),
    ("Calc_SkuMonth", PAL["grey"]), ("Calc_Sku", PAL["grey"]), ("Calc_Dashboard", PAL["grey"]),
    ("Calc_Customers", PAL["grey"]), ("Data_Monthly", PAL["grey"]), ("Data_Products", PAL["grey"]),
    ("Data_StockMonth", PAL["grey"]), ("Data_Customers", PAL["grey"]), ("Data_Cohort", PAL["grey"]),
    ("Data_Promo", PAL["grey"]), ("Data_Control", PAL["grey"]),
]


def absref(sheet: str, row: int, col: int) -> str:
    return f"{sheet}!{xl_rowcol_to_cell(row, col, row_abs=True, col_abs=True)}"


def absrange(sheet: str, r1: int, c1: int, r2: int, c2: int) -> str:
    a = xl_rowcol_to_cell(r1, c1, row_abs=True, col_abs=True)
    b = xl_rowcol_to_cell(r2, c2, row_abs=True, col_abs=True)
    return f"{sheet}!{a}:{b}"


def py(v):
    """Convert pandas and numpy values to something XlsxWriter writes cleanly."""
    if v is None:
        return None
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return None if pd.isna(v) else v.to_pydatetime() if isinstance(v, pd.Timestamp) else v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else float(v)
    if v is pd.NaT:
        return None
    return v


class Ctx:
    def __init__(self, path: str, data: dict[str, pd.DataFrame]):
        self.wb = xlsxwriter.Workbook(path, {"use_future_functions": True})
        self.data = data
        self._fmt: dict = {}
        self.ws = {}
        for name, colour in SHEETS:
            w = self.wb.add_worksheet(name)
            w.set_tab_color(colour)
            if name.startswith(("Calc_", "Data_")):
                w.hide()
            w.hide_gridlines(2)
            self.ws[name] = w
            w.write_formula = self._with_cached_value(name, w.write_formula)
        self.refs: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.charts_n = 0
        self.sel = {}
        self.cache: dict = {}

    def _with_cached_value(self, sheet, original):
        def write_formula(row, col, formula, cell_format=None, value=None):
            v = self.cache.get((sheet, row, col)) if self.cache else None
            if v is None:
                v = 0 if not self.cache else ""
            return original(row, col, formula, cell_format, v)
        return write_formula

    def fmt(self, **kw):
        base = dict(font_name="Calibri", font_size=10, font_color=PAL["text"], valign="vcenter")
        base.update(kw)
        key = tuple(sorted(base.items()))
        if key not in self._fmt:
            self._fmt[key] = self.wb.add_format(base)
        return self._fmt[key]

    def name(self, name: str, ref: str) -> None:
        self.wb.define_name(name, "=" + ref)
        self.names[name] = ref

    # common formats
    def title(self):
        return self.fmt(bold=True, font_size=16, font_color=PAL["white"], bg_color=PAL["navy"])

    def h1(self):
        return self.fmt(bold=True, font_size=12, font_color=PAL["navy"], bottom=1, bottom_color=PAL["navy"])

    def head(self, **kw):
        return self.fmt(bold=True, font_color=PAL["white"], bg_color=PAL["navy"], text_wrap=True, align="center",
                        border=1, border_color=PAL["line"], **kw)

    def cell(self, num=None, **kw):
        d = dict(border=1, border_color=PAL["line"])
        if num:
            d["num_format"] = num
        d.update(kw)
        return self.fmt(**d)

    def inp(self, num=None, **kw):
        d = dict(border=1, border_color=PAL["line"], bg_color=PAL["input_fill"], font_color=PAL["input_font"])
        if num:
            d["num_format"] = num
        d.update(kw)
        return self.fmt(**d)

    def note(self):
        return self.fmt(italic=True, font_color=PAL["slate"], text_wrap=True, valign="top")

    def banner(self, ws, text: str, width_cols: int, sub: str | None = None):
        ws.set_row(0, 28)
        ws.merge_range(0, 0, 0, width_cols - 1, "  " + text, self.title())
        if sub:
            ws.merge_range(1, 0, 1, width_cols - 1, "  " + sub, self.fmt(italic=True, font_color=PAL["slate"], bg_color=PAL["light"]))

    def back_link(self, ws, col: int = 0, row: int = 2):
        ws.write_url(row, col, "internal:'Start_Here'!A1", self.fmt(font_color=PAL["teal"], underline=1), "Back to Start here")


def write_table(ctx: Ctx, sheet: str, df: pd.DataFrame, table_name: str, col_formats: dict[str, str] | None = None,
                widths: dict[str, float] | None = None, name_prefix: str | None = None, style="Table Style Light 1"):
    """Write df as an Excel table starting at A1 and define a name per column when name_prefix is set."""
    ws = ctx.ws[sheet]
    col_formats = col_formats or {}
    widths = widths or {}
    cols = []
    for c in df.columns:
        spec = {"header": c}
        if c in col_formats:
            spec["format"] = ctx.fmt(num_format=col_formats[c])
        cols.append(spec)
    data = [[py(v) for v in row] for row in df.itertuples(index=False, name=None)]
    n = len(df)
    ws.add_table(0, 0, n, len(df.columns) - 1, {"name": table_name, "columns": cols, "data": data,
                                                  "style": style, "autofilter": True})
    for j, c in enumerate(df.columns):
        ws.set_column(j, j, widths.get(c, max(10, min(26, len(c) + 3))))
        if name_prefix:
            ctx.name(f"{name_prefix}{c}", absrange(sheet, 1, j, n, j))
    ws.freeze_panes(1, 0)
    return n
