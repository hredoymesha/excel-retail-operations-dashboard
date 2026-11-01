"""Run every analysis script and write all files in outputs/.

    python analysis/run_all.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis import abc_xyz, customers, findings, forecast, kpis, v1_review  # noqa: E402

if __name__ == "__main__":
    for mod in (kpis, abc_xyz, forecast, customers, v1_review, findings):
        print(f"--- {mod.__name__}")
        mod.main()
