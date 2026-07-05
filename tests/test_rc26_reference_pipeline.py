# -*- coding: utf-8 -*-
from pathlib import Path
from functools import lru_cache
from types import SimpleNamespace

import openpyxl
import pandas as pd

from columns_ec2.api import DesignParameters, design_dataframe
from columns_ec2.core.import_data import (
    read_table_file,
    clean_dataframe,
    combine_member_end_actions,
    reduce_to_governing_cases,
)
from columns_ec2.runtime.loader import runtime_object


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "tests" / "data" / "ESFORCOS_PILARES.csv"


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


@lru_cache(maxsize=1)
def _reference_frames():
    clean = clean_dataframe(read_table_file(str(CSV_PATH)))
    pairs = combine_member_end_actions(clean)
    reduced = reduce_to_governing_cases(pairs)
    return clean, pairs, reduced


def test_reference_csv_preserves_tramos_and_els_302():
    clean, pairs, reduced = _reference_frames()
    tramo_cols = ["member", "name", "story", "material", "hy", "hz", "ax"]

    assert len(clean) == 16388
    assert len(pairs) == 8194
    assert len(reduced) == 241
    assert clean[tramo_cols].drop_duplicates().shape[0] == 241
    assert pairs["case"].astype(str).str.extract(r"(\d+)")[0].eq("302").sum() == 241


def test_headless_api_evaluates_service_case_302():
    clean, _, _ = _reference_frames()

    result = design_dataframe(
        clean.head(200),
        DesignParameters(calc_mode="pre_dimensionamento", reduce_cases=True, service_case="302"),
    )

    assert not result.empty
    assert set(result["service_combination"].astype(str)) == {"302"}
    assert result["service_case_source"].astype(str).str.contains("302").all()


def test_pf51_piso1_is_real_biaxial_failure_not_empty_solution():
    _, _, reduced = _reference_frames()
    row = reduced[(reduced["name"].astype(str) == "PF51") & (reduced["story"].astype(str) == "PISO 1")]

    result = design_dataframe(
        row,
        DesignParameters(calc_mode="dimensionamento", reduce_cases=False, service_case=""),
    )
    pf51 = result.iloc[0]

    assert pf51["status"] == "Falha"
    assert float(pf51["as_prov_mm2"]) > 0.0
    assert float(pf51["utilizacao"]) > 1.0
    assert "η_NMyMz > 1.00" in str(pf51["failure_reason"])
    assert str(pf51["rc26_rigorous_fallback"]) == "Sim"


def test_headless_exports_do_not_emit_nan_or_none_text(tmp_path):
    clean, pairs, reduced = _reference_frames()
    calc_input = reduced.head(5)
    results = design_dataframe(
        calc_input,
        DesignParameters(calc_mode="pre_dimensionamento", reduce_cases=False, service_case="302"),
    )
    schedule = runtime_object("_rc22_build_tramo_schedule")(results)

    app = SimpleNamespace(
        df_results=results,
        df_summary=schedule,
        df_pair=pairs.head(20),
        df_calc_input=calc_input,
        df_validation=pd.DataFrame(),
        df_notes=pd.DataFrame(),
        df_failures=pd.DataFrame(),
        df_warnings=pd.DataFrame(),
        input_file_path=str(CSV_PATH),
        var_service_case=Var("302"),
        var_rebar_strategy=Var("Equilibrada"),
        var_pdf_level=Var("Relatorio tecnico"),
        var_fyk=Var("500"),
        var_language=Var("pt"),
    )
    app.build_summary_by_member = lambda data: runtime_object("_rc22_build_tramo_schedule")(data)
    app.build_data_validation = lambda pre_calc=False: pd.DataFrame()
    app.build_normative_notes = lambda: pd.DataFrame()
    app.build_shortlists_df = lambda: pd.DataFrame()

    xlsx_path = tmp_path / "rc26.xlsx"
    pdf_path = tmp_path / "rc26.pdf"
    dxf_path = tmp_path / "rc26.dxf"

    runtime_object("_write_excel_rc25")(app, str(xlsx_path))
    runtime_object("_write_pdf_rc25")(app, str(pdf_path))
    runtime_object("_write_columns_dxf_rc25")(str(dxf_path), schedule, lang=runtime_object("LANG_PT"))

    assert xlsx_path.stat().st_size > 0
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert dxf_path.stat().st_size > 0

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    cell_text = "\n".join(str(cell) for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for cell in row if cell is not None)
    exported_text = "\n".join([
        cell_text,
        pdf_path.read_bytes().decode("latin-1", errors="ignore"),
        dxf_path.read_text(encoding="utf-8", errors="ignore"),
    ])
    lowered = exported_text.lower()

    assert "nan;" not in lowered
    assert "\nnone\n" not in lowered
    assert " none " not in lowered
