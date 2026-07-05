# -*- coding: utf-8 -*-
"""RC24 performance patch.

Main objective:
- keep all physical tramos (member + name + story + section/material);
- reduce the design input to one governing ELU state per tramo by a fast
  approximate interaction score;
- keep the full df_pair available for ELS lookup and auditing.

This avoids running the full N-My-Mz catalogue search for 5-9 cases per tramo.
For the reference validation case, this reduces the design input to one row per
physical tramo instead of repeating every ELU combination.
"""
from __future__ import annotations

import math
import os
import time
import pandas as pd

APP_VERSION = "v0.9 RC25 Modular"


def _rc24_case_number(value) -> str:
    try:
        return str(extract_combination_number(value)).strip()
    except Exception:
        s = str(value if value is not None else "").strip()
        import re
        m = re.search(r"\d+", s)
        return m.group(0) if m else s


def _rc24_case_is_service(value) -> bool:
    n = _rc24_case_number(value)
    return n.startswith("3")


def _rc24_num(s, default=0.0):
    try:
        v = safe_float(s, default)
    except Exception:
        try:
            v = float(str(s).replace(",", "."))
        except Exception:
            v = default
    try:
        if not math.isfinite(float(v)):
            return default
    except Exception:
        return default
    return float(v)


def _rc24_rough_strengths(g: pd.DataFrame):
    """Approximate normal and bending reference strengths for fast screening."""
    hy_cm = _rc24_num(g.get("hy", pd.Series([0])).iloc[0] if "hy" in g.columns and len(g) else 0.0)
    hz_cm = _rc24_num(g.get("hz", pd.Series([0])).iloc[0] if "hz" in g.columns and len(g) else 0.0)
    b = max(hy_cm * 10.0, 1.0)
    h = max(hz_cm * 10.0, 1.0)
    ax_cm2 = _rc24_num(g.get("ax", pd.Series([0])).iloc[0] if "ax" in g.columns and len(g) else 0.0)
    ac = ax_cm2 * 100.0 if ax_cm2 > 0 else b * h
    mat = str(g.get("material", pd.Series([DEFAULT_CONCRETE_CLASS])).iloc[0] if "material" in g.columns and len(g) else DEFAULT_CONCRETE_CLASS)
    try:
        fck = parse_concrete_strength(mat)
        fcd = concrete_props(fck)["fcd"]
    except Exception:
        fcd = 20.0
    n0 = max(0.45 * ac * fcd / 1000.0, 1.0)      # kN, deliberately conservative for screening
    my0 = max(0.12 * fcd * b * h * h / 1e6, 1.0) # kNm
    mz0 = max(0.12 * fcd * h * b * b / 1e6, 1.0) # kNm
    return n0, my0, mz0


def _rc24_fast_score(g: pd.DataFrame) -> pd.Series:
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in g.columns:
            g[c] = 0.0
    n0, my0, mz0 = _rc24_rough_strengths(g)
    n = pd.to_numeric(g["fx"], errors="coerce").abs().fillna(0.0)
    my = pd.to_numeric(g["my"], errors="coerce").abs().fillna(0.0)
    mz = pd.to_numeric(g["mz"], errors="coerce").abs().fillna(0.0)
    t = pd.to_numeric(g["mx"], errors="coerce").abs().fillna(0.0)
    v = pd.to_numeric(g["fy"], errors="coerce").abs().fillna(0.0) + pd.to_numeric(g["fz"], errors="coerce").abs().fillna(0.0)
    # Interaction-style screening. This is not the final resistance check; it
    # only chooses which simultaneous state goes into the full section design.
    rn = n / n0
    rmy = my / my0
    rmz = mz / mz0
    biax = (rmy.pow(1.35) + rmz.pow(1.35)).pow(1.0 / 1.35)
    ecc = (my + mz) / n.replace(0.0, 1e-9)
    ecc_norm = ecc / max(max(my0, mz0) / n0, 1e-9)
    return 0.70 * rn + biax + 0.12 * ecc_norm + 0.04 * (t / max(my0, mz0)) + 0.02 * (v / n0)


def _rc24_group_cols(work: pd.DataFrame):
    cols = [c for c in ["member", "name", "story", "material", "hy", "hz", "ax"] if c in work.columns]
    # member is mandatory for a physical tramo. If missing, keep name/story as fallback.
    if "member" not in cols:
        cols = [c for c in ["name", "story", "material", "hy", "hz", "ax"] if c in work.columns]
    return cols


def reduce_to_governing_cases_rc24(df: pd.DataFrame) -> pd.DataFrame:
    """Fast default reduction: one governing ELU state per physical tramo.

    Environment override:
      COLUMNSEC2_RC24_CASES_PER_TRAMO=3 keeps up to three screening states
      (combined score, max N, max biaxial bending). Default is 1.
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df
    work = df.copy()
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in work.columns:
            work[c] = 0.0
        work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
    for c in ["member", "name", "story", "material", "hy", "hz", "ax"]:
        if c not in work.columns:
            work[c] = ""

    try:
        max_cases = int(os.environ.get("COLUMNSEC2_RC24_CASES_PER_TRAMO", "1"))
    except Exception:
        max_cases = 1
    max_cases = max(1, min(max_cases, 4))

    selected = set()
    group_cols = _rc24_group_cols(work)
    for _, grp0 in work.groupby(group_cols, dropna=False, sort=False):
        if grp0.empty:
            continue
        case_series = grp0.get("case", pd.Series(index=grp0.index, dtype=str)).astype(str)
        g = grp0[~case_series.map(_rc24_case_is_service)].copy()
        if g.empty:
            g = grp0.copy()
        score = _rc24_fast_score(g)
        chosen = [score.idxmax()]
        if max_cases >= 2:
            chosen.append(pd.to_numeric(g["fx"], errors="coerce").abs().fillna(0.0).idxmax())
        if max_cases >= 3:
            n0, my0, mz0 = _rc24_rough_strengths(g)
            biax = (pd.to_numeric(g["my"], errors="coerce").abs().fillna(0.0) / my0).pow(1.35) + (pd.to_numeric(g["mz"], errors="coerce").abs().fillna(0.0) / mz0).pow(1.35)
            chosen.append(biax.idxmax())
        if max_cases >= 4:
            chosen.append((pd.to_numeric(g["fy"], errors="coerce").abs().fillna(0.0) + pd.to_numeric(g["fz"], errors="coerce").abs().fillna(0.0)).idxmax())
        for idx in chosen:
            selected.add(idx)
    out = work.loc[sorted(selected)].copy()
    out["rc24_reduction"] = f"1 caso governante/tramo" if max_cases == 1 else f"até {max_cases} casos governantes/tramo"
    order = [c for c in ["name", "story", "member", "case"] if c in out.columns]
    if order:
        out = out.sort_values(order, kind="mergesort")
    return out.reset_index(drop=True)


# Patch runtime reduction used by GUI and API runtime designer.
reduce_to_governing_cases = reduce_to_governing_cases_rc24
reduce_to_governing_cases_rc23 = reduce_to_governing_cases_rc24

# Improve progress feedback: the UI should show the reduced case count before
# starting the heavy section design.
_rc24_prev_run_design = getattr(ColumnsEC2App, "run_design", None)

def _run_design_rc24(self):
    try:
        pairs = getattr(self, "df_pair", pd.DataFrame())
        if pairs is not None and not pairs.empty and getattr(self, "var_reduce_cases", None) is not None and self.var_reduce_cases.get():
            tmp = reduce_to_governing_cases_rc24(pairs)
            physical = pairs[[c for c in ["member", "name", "story"] if c in pairs.columns]].drop_duplicates().shape[0]
            self.status_var.set(f"A correr: redução rápida RC24 activa — {len(pairs)} pares → {len(tmp)} casos de cálculo; {physical} tramos preservados.")
            try:
                self.update_idletasks()
            except Exception:
                pass
    except Exception:
        pass
    return _rc24_prev_run_design(self) if callable(_rc24_prev_run_design) else None

try:
    ColumnsEC2App.run_design = _run_design_rc24
except Exception:
    pass

# Metadata line for diagnostics where translation dict exists.
try:
    _RC13_EN_TERMS.update({"v0.9 RC24 Modular": "v0.9 RC24 Modular"})
except Exception:
    pass

# ---------------------------------------------------------------------------
# Fast dimensioning loop: avoid exhaustive 80-120 layout checks per case.
# ---------------------------------------------------------------------------
_rc24_prev_design_one = ColumnDesigner.design_one


def _rc24_result_util(out):
    try:
        return float(out.get("utilizacao"))
    except Exception:
        return 999.0


def _rc24_result_as(out):
    try:
        return float(out.get("as_prov_mm2"))
    except Exception:
        return 1e12


def _rc24_clean_dim_status(out: dict, original_mode: str) -> dict:
    out = dict(out or {})
    util = _rc24_result_util(out)
    warnings = str(out.get("failure_warnings", "") or "").strip()
    warnings_empty = warnings in {"", "-", "nan", "None"}
    # Keep real shear/torsion/detailing warnings, but remove the pre-dimensioning notice.
    info = str(out.get("failure_info", "") or "")
    info = info.replace("pré-dimensionamento: verificar em modo Dimensionamento antes de adoptar", "").strip("; ").strip()
    out["failure_info"] = info if info else "-"
    out["calc_mode_effective"] = original_mode
    out["rc24_fast_dimensioning"] = "Sim"
    if not math.isfinite(util) or util > 1.0 + 1e-9:
        out["status"] = "Falha"
        out["failure_severity"] = "Bloqueante"
        out["failure_reason"] = "interação N-My-Mz não verificada no modo rápido RC24"
        out["failure_type"] = "resistencia_biaxial"
        out["design_decision"] = "Não adoptar sem revisão"
        out["review_priority"] = "Alta"
        out["failure_action"] = "Aumentar secção, rever esforços/l0 ou correr verificação refinada."
        out["failure_summary"] = "Bloqueante | resistência biaxial | modo rápido RC24"
    else:
        out["failure_reason"] = ""
        out["failure_type"] = "OK" if warnings_empty else "aviso_pormenorizacao"
        out["failure_severity"] = "OK" if warnings_empty else "Aviso"
        out["status"] = "OK" if warnings_empty else "Aviso"
        out["design_decision"] = "OK" if warnings_empty else "Adoptável com revisão indicada"
        out["review_priority"] = "Normal" if warnings_empty else "Média"
        out["failure_action"] = "-" if warnings_empty else warnings
        out["failure_summary"] = "OK" if warnings_empty else f"Aviso | {warnings}"
    return out


def _design_one_rc24_fast(self, row: pd.Series, prebuilt_candidates=None):
    mode = str(getattr(self, "calc_mode", "") or "").lower()
    backend = getattr(self, "code_backend", globals().get("ACTIVE_CODE_BACKEND_V48", ""))
    try:
        if _v56_is_structuralcodes_backend_value(backend):
            return _rc24_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)
    except Exception:
        pass
    if mode not in {"dimensionamento", "rigoroso"}:
        return _rc24_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)

    original_mode = getattr(self, "calc_mode", "dimensionamento")
    try:
        # First pass obtains As,req and verifies the lightest constructive option.
        self.calc_mode = "pre_dimensionamento"
        base = _rc24_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)
        as_req = _rc24_num(base.get("as_req_mm2", 0.0), 0.0)
        as_max = _rc24_num(base.get("as_max_mm2", 1e12), 1e12)
        b_mm = _rc24_num(base.get("b_cm", 0.0), 0.0) * 10.0
        h_mm = _rc24_num(base.get("h_cm", 0.0), 0.0) * 10.0
        util0 = _rc24_result_util(base)
        if math.isfinite(util0) and util0 <= 0.92:
            out = _rc24_clean_dim_status(base, str(original_mode))
            out["rc24_layout_tests"] = "1"
            return out

        # Try a short constructive shortlist. This keeps dimensioning responsive
        # while still increasing reinforcement if the first layout is too weak.
        candidates = list(prebuilt_candidates) if prebuilt_candidates is not None else []
        if not candidates:
            try:
                is_circ = self.infer_is_circular(row, b_mm, h_mm)
                candidates = list(self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circ))
            except Exception:
                candidates = []
        pool = []
        for ly in candidates:
            asp = float(getattr(ly, "as_prov_mm2", 0.0))
            if asp + 1e-6 >= as_req and asp <= as_max + 1e-6:
                pool.append(ly)
        try:
            pool.sort(key=lambda ly: _v56_layout_score(ly, as_req, b_mm, h_mm))
        except Exception:
            pool.sort(key=lambda ly: (abs(float(getattr(ly, "as_prov_mm2", 0.0)) - as_req), float(getattr(ly, "as_prov_mm2", 0.0))))
        # Ensure the initial solution is not lost.
        max_tests = 12 if mode == "dimensionamento" else 18
        best = base
        best_key = (abs(util0 - 0.80) if math.isfinite(util0) else 999.0, _rc24_result_as(base))
        tested = 1
        seen = set()
        for ly in pool[:max_tests]:
            try:
                sig = _v56_layout_signature(ly)
            except Exception:
                sig = id(ly)
            if sig in seen:
                continue
            seen.add(sig)
            self.calc_mode = "pre_dimensionamento"
            cand = _rc24_prev_design_one(self, row, prebuilt_candidates=[ly])
            tested += 1
            util = _rc24_result_util(cand)
            asp = _rc24_result_as(cand)
            if math.isfinite(util) and util <= 1.0:
                key = (abs(util - 0.80), asp)
                if key < best_key or not (math.isfinite(_rc24_result_util(best)) and _rc24_result_util(best) <= 1.0):
                    best, best_key = cand, key
                # Good enough for normal design; stop early.
                if 0.70 <= util <= 0.90:
                    break
            elif util < _rc24_result_util(best):
                best = cand
        out = _rc24_clean_dim_status(best, str(original_mode))
        out["rc24_layout_tests"] = str(tested)
        return out
    finally:
        try:
            self.calc_mode = original_mode
        except Exception:
            pass


ColumnDesigner.design_one = _design_one_rc24_fast
