# -*- coding: utf-8 -*-
"""Public programmatic API for the transitional modular build.

The GUI is still loaded through the validated runtime sequence, but this module
provides a stable import surface for scripts, tests and future refactoring.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Optional

import pandas as pd

from .app_info import DEFAULT_CONCRETE_CLASS
from .core.import_data import (
    parse_pasted_table,
    clean_dataframe,
    combine_member_end_actions,
    reduce_to_governing_cases,
)
from .core.materials import parse_concrete_strength, concrete_props
from .core.reinforcement import ColumnDesigner
from .core.utils import safe_float
from .runtime.loader import runtime_object


@dataclass(slots=True)
class DesignParameters:
    cover_mm: float = 35.0
    fyk: float = 500.0
    gamma_c: float = 1.5
    gamma_s: float = 1.15
    phi_eff: float = 2.0
    l0y_factor: float = 1.0
    l0z_factor: float = 1.0
    calc_mode: str = "dimensionamento"
    reduce_cases: bool = True
    service_case: str = ""


def prepare_input_table(df: pd.DataFrame, *, reduce_cases: bool = True) -> pd.DataFrame:
    """Clean an imported nodal-force table and return member/case design rows."""
    clean = clean_dataframe(df)
    pairs = combine_member_end_actions(clean)
    return reduce_to_governing_cases(pairs) if reduce_cases else pairs


class _HeadlessVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class _HeadlessServiceApp:
    def __init__(self, pairs: pd.DataFrame, service_case: str, fyk: float):
        self.df_pair = pairs
        self.var_service_case = _HeadlessVar(service_case)
        self.var_fyk = _HeadlessVar(str(fyk))


def _apply_service_case_override(
    results: pd.DataFrame,
    design_input: pd.DataFrame,
    all_pairs: pd.DataFrame,
    params: DesignParameters,
) -> pd.DataFrame:
    service_case = str(params.service_case or "").strip()
    if not service_case or results is None or results.empty or all_pairs is None or all_pairs.empty:
        return results
    out = results.copy()
    pairs = all_pairs.copy()

    def combination_number(value: object) -> str:
        try:
            return str(runtime_object("extract_combination_number")(value)).strip()
        except Exception:
            match = re.search(r"\d+", str(value if value is not None else ""))
            return match.group(0) if match else str(value if value is not None else "").strip()

    pairs["_case_str"] = pairs.get("case", pd.Series(index=pairs.index, dtype=str)).astype(str).str.strip()
    pairs["_comb_str"] = pairs.get("case", pd.Series(index=pairs.index, dtype=str)).map(combination_number).astype(str)
    pair_sel = pairs[(pairs["_case_str"] == service_case) | (pairs["_comb_str"] == service_case)].copy()
    if pair_sel.empty:
        out["service_case_source"] = f"combinação ELS {service_case} não encontrada"
        out["service_status"] = "ELS não avaliado — combinação indicada não encontrada"
        return out

    elastic_service_check = runtime_object("elastic_service_check_v4")
    pair_by_member = {str(r.get("member", "")).strip(): r for _, r in pair_sel.iterrows()}
    pair_by_tramo = {}
    for _, pair in pair_sel.iterrows():
        pair_by_tramo.setdefault((str(pair.get("name", "")), str(pair.get("story", ""))), pair)

    for idx, row in out.iterrows():
        pair = pair_by_member.get(str(row.get("member", "")).strip())
        if pair is None:
            pair = pair_by_tramo.get((str(row.get("name", "")), str(row.get("story", ""))))
        if pair is None:
            out.at[idx, "service_case_source"] = f"combinação {service_case} sem linha para o tramo"
            out.at[idx, "service_status"] = "ELS não avaliado — tramo sem combinação indicada"
            continue
        material = str(row.get("material", DEFAULT_CONCRETE_CLASS) or DEFAULT_CONCRETE_CLASS)
        if material.strip().lower() in {"", "nan", "none", "null", "<na>"}:
            material = DEFAULT_CONCRETE_CLASS
        fck = parse_concrete_strength(material)
        cp = concrete_props(fck)
        b_mm = safe_float(row.get("b_cm", row.get("hy", 0.0)), 0.0) * 10.0
        h_mm = safe_float(row.get("h_cm", row.get("hz", 0.0)), 0.0) * 10.0
        iy = safe_float(pair.get("iy"), 0.0) * 10000.0
        iz = safe_float(pair.get("iz"), 0.0) * 10000.0
        if iy <= 0 and b_mm > 0 and h_mm > 0:
            iy = b_mm * h_mm**3 / 12.0
        if iz <= 0 and b_mm > 0 and h_mm > 0:
            iz = h_mm * b_mm**3 / 12.0
        n = max(abs(safe_float(pair.get("fx_i"), 0.0)), abs(safe_float(pair.get("fx_j"), 0.0)))
        my = max(abs(safe_float(pair.get("my_i"), 0.0)), abs(safe_float(pair.get("my_j"), 0.0)))
        mz = max(abs(safe_float(pair.get("mz_i"), 0.0)), abs(safe_float(pair.get("mz_j"), 0.0)))
        els = elastic_service_check(
            n,
            my,
            mz,
            b_mm,
            h_mm,
            iy,
            iz,
            safe_float(row.get("as_prov_mm2"), 0.0),
            fck,
            params.fyk,
            cp["Ecm"],
            cp["fctm"],
        )
        for key, value in els.items():
            out.at[idx, key] = value
        out.at[idx, "service_combination"] = service_case
        out.at[idx, "service_case_source"] = f"combinação indicada pelo utilizador: {service_case}"
        out.at[idx, "service_n_kN"] = n
        out.at[idx, "service_my_kNm"] = my
        out.at[idx, "service_mz_kNm"] = mz
    return out


def design_dataframe(
    df: pd.DataFrame,
    params: Optional[DesignParameters] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """Run the current validated design engine on a dataframe.

    `df` may be either the original imported nodal table or an already prepared
    member/case table. The function detects the format from its columns.
    """
    params = params or DesignParameters()
    if {"fx_i", "fx_j", "my_i", "my_j"}.issubset(set(df.columns)):
        all_pairs = df.copy()
        design_input = reduce_to_governing_cases(all_pairs) if params.reduce_cases else all_pairs.copy()
    else:
        if {"member", "node", "case", "__row_order"}.issubset(set(df.columns)):
            clean = df.copy()
        else:
            clean = clean_dataframe(df)
        all_pairs = combine_member_end_actions(clean)
        design_input = reduce_to_governing_cases(all_pairs) if params.reduce_cases else all_pairs.copy()

    designer = ColumnDesigner(
        cover_mm=params.cover_mm,
        fyk=params.fyk,
        gamma_c=params.gamma_c,
        gamma_s=params.gamma_s,
        phi_eff=params.phi_eff,
        l0y_factor=params.l0y_factor,
        l0z_factor=params.l0z_factor,
        calc_mode=params.calc_mode,
    )
    results = designer.design_dataframe(design_input, progress_callback=progress_callback)
    return _apply_service_case_override(results, design_input, all_pairs, params)
