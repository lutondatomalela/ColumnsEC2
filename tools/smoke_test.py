# -*- coding: utf-8 -*-
"""Non-GUI smoke test for ColumnsEC2 RC26.

Run from the project root:
    python tools/smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from columns_ec2.api import DesignParameters, design_dataframe, prepare_input_table
from columns_ec2.core.materials import parse_concrete_strength, concrete_props


def main() -> None:
    assert parse_concrete_strength("C30/37") == 30.0
    assert concrete_props(30.0)["fcd"] > 0

    df = pd.DataFrame([
        {"Member/Node/Case": "1/1/101 (C)", "FX (kN)": "500", "FY (kN)": "0", "FZ (kN)": "0", "MX (kNm)": "0", "MY (kNm)": "20", "MZ (kNm)": "10", "Length (m)": "3.0", "Material": "C30/37", "HY (cm)": "30", "HZ (cm)": "30", "AX (cm2)": "900", "IY (cm4)": "67500", "IZ (cm4)": "67500", "Name": "P1", "Story": "Storey 0"},
        {"Member/Node/Case": "1/2/101 (C)", "FX (kN)": "510", "FY (kN)": "0", "FZ (kN)": "0", "MX (kNm)": "0", "MY (kNm)": "18", "MZ (kNm)": "12", "Length (m)": "3.0", "Material": "C30/37", "HY (cm)": "30", "HZ (cm)": "30", "AX (cm2)": "900", "IY (cm4)": "67500", "IZ (cm4)": "67500", "Name": "P1", "Story": "Storey 0"},
    ])
    prepared = prepare_input_table(df, reduce_cases=False)
    assert len(prepared) == 1
    res = design_dataframe(prepared, DesignParameters(calc_mode="pre_dimensionamento", reduce_cases=False))
    assert len(res) == 1
    assert "status" in res.columns
    print("ColumnsEC2 RC26 smoke test: OK")


if __name__ == "__main__":
    main()
