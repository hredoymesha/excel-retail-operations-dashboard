"""Recalculate a workbook headlessly with LibreOffice."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SOFFICE_CANDIDATES = [r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                      "soffice", "libreoffice"]
REGISTRY = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>
"""


def find_soffice() -> str | None:
    for c in SOFFICE_CANDIDATES:
        if shutil.which(c) or Path(c).exists():
            return c
    return None


def recalc(src: Path, outdir: Path, timeout: int = 1800) -> Path:
    """Open src, recalculate every formula on load and save a copy in outdir/recalc."""
    exe = find_soffice()
    if exe is None:
        raise SystemExit("LibreOffice not found. Install it, or build without cached values.")
    profile = outdir / "lo_profile"
    (profile / "user").mkdir(parents=True, exist_ok=True)
    (profile / "user" / "registrymodifications.xcu").write_text(REGISTRY, encoding="utf-8")
    cmd = [exe, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--calc", "--convert-to", "xlsx",
           "--outdir", str(outdir / "recalc"), str(src)]
    subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    return outdir / "recalc" / src.name
