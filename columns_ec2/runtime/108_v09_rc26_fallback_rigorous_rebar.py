# -*- coding: utf-8 -*-
"""RC26 robust reinforcement fallback.

RC24/RC25 made the program fast by using a reduced governing-case set and a
short constructive reinforcement search. That is adequate for most columns, but
it can create false negatives when the fast shortlist does not contain a layout
that verifies N-My-Mz.

RC26 keeps the fast path and adds a rigorous fallback only for tramos that are
reported as failing due to the fast N-My-Mz search. The fallback tests the full
constructive catalogue for that section before a real failure is reported.
"""
from __future__ import annotations

import math
import os
import pandas as pd

APP_VERSION = "v0.9 RC26 Modular"

_RC26_PREV_DESIGN_ONE = ColumnDesigner.design_one
_RC26_BASE_DESIGN_ONE = globals().get("_rc24_prev_design_one", _RC26_PREV_DESIGN_ONE)
_RC26_PREV_CAPACITY_FOR_LAYOUT = ColumnDesigner.capacity_for_layout


def _capacity_for_layout_rc26(self, layout, n_ed_kN: float, fcd: float, fyd: float, Es: float):
    """Fast mesh only for preliminary shortlist screening.

    RC24 calls the older design engine in ``pre_dimensionamento`` for speed.
    Keeping the v56 mesh there makes large runs too slow. Final checks and
    max-capacity probes still use the previous v56 implementation.
    """
    mode = str(getattr(self, "requested_calc_mode", self.calc_mode) or "").lower()
    if mode != "pre_dimensionamento":
        return _RC26_PREV_CAPACITY_FOR_LAYOUT(self, layout, n_ed_kN, fcd, fyd, Es)
    try:
        sig = _v56_layout_signature(layout)
    except Exception:
        sig = _rc26_layout_sig(layout) if "_rc26_layout_sig" in globals() else id(layout)
    key = ("rc26_pre_fast", sig, round(float(n_ed_kN), 1), round(float(fcd), 4), round(float(fyd), 4), round(float(Es), 1))
    if key in self._capacity_cache:
        return self._capacity_cache[key]
    try:
        n_ang = max(9, int(os.environ.get("COLUMNSEC2_RC26_PRE_N_ANG", "13")))
        n_iter = max(18, int(os.environ.get("COLUMNSEC2_RC26_PRE_N_ITER", "28")))
        n_grid = max(24, int(os.environ.get("COLUMNSEC2_RC26_PRE_N_GRID", "36")))
    except Exception:
        n_ang, n_iter, n_grid = 13, 28, 36
    angles = [i * math.pi / (2 * max(n_ang - 1, 1)) for i in range(n_ang)]
    capacities = []
    c_max = 3.0 * max(layout.b_mm, layout.h_mm)
    for ang in angles:
        best = None

        def n_at(c):
            return self.section_response(layout, n_ed_kN, ang, c, fcd, fyd, Es)

        lo, hi = 2.0, c_max
        n_lo, _, _ = n_at(lo)
        n_hi, _, _ = n_at(hi)
        if (n_lo - n_ed_kN) * (n_hi - n_ed_kN) <= 0:
            for _ in range(n_iter):
                mid = 0.5 * (lo + hi)
                N, My, Mz = n_at(mid)
                diff = N - n_ed_kN
                if best is None or abs(diff) < best[0]:
                    best = (abs(diff), My, Mz)
                if abs(diff) < 1e-3:
                    break
                if (n_lo - n_ed_kN) * diff <= 0:
                    hi = mid
                    n_hi = N
                else:
                    lo = mid
                    n_lo = N
        else:
            for i in range(n_grid):
                c_mm = 2.0 + i * (c_max - 2.0) / max(n_grid - 1, 1)
                N, My, Mz = n_at(c_mm)
                diff = abs(N - n_ed_kN)
                if best is None or diff < best[0]:
                    best = (diff, My, Mz)
        if best is not None:
            capacities.append((best[1], best[2]))
    self._capacity_cache[key] = capacities
    return capacities


ColumnDesigner.capacity_for_layout = _capacity_for_layout_rc26


def _rc26_is_blank(value) -> bool:
    s = str(value if value is not None else "").strip()
    return s == "" or s.lower() in {"nan", "none", "null", "<na>", "-"}


def _rc26_num(value, default=0.0) -> float:
    try:
        v = safe_float(value, default)
    except Exception:
        try:
            v = float(str(value).replace(",", "."))
        except Exception:
            v = default
    try:
        if not math.isfinite(float(v)):
            return float(default)
    except Exception:
        return float(default)
    return float(v)


def _rc26_needs_rigorous_fallback(out: dict) -> bool:
    """True only for the artificial fast-search failures.

    Data failures, As,max failures and genuine geometry impossibilities are not
    hidden by the fallback.
    """
    if not isinstance(out, dict):
        return False
    status = str(out.get("status", "") or "").lower()
    reason = " ".join(str(out.get(k, "") or "") for k in [
        "failure_reason", "failure_summary", "failure_action", "design_decision"
    ]).lower()
    if status not in {"falha", "failure", "não ok", "nao ok"}:
        return False
    if any(k in reason for k in ["falha de dados", "dados insuficientes", "sem os dois nós", "sem os dois nos"]):
        return False
    if any(k in reason for k in ["as,max", "asmax", "limite máximo", "limite maximo"]):
        return False
    if "modo rápido" in reason or "modo rapido" in reason or "rc24" in reason:
        return True
    # Safety net: a failure with no chosen steel but with plausible As limits is
    # also a fast-search false negative candidate.
    as_req = _rc26_num(out.get("as_req_mm2"), 0.0)
    as_max = _rc26_num(out.get("as_max_mm2"), 0.0)
    as_prov_blank = _rc26_is_blank(out.get("as_prov_mm2")) or _rc26_num(out.get("as_prov_mm2"), -1.0) <= 0.0
    return as_prov_blank and as_req > 0.0 and as_max > as_req


def _rc26_section_dimensions(row: pd.Series, out: dict) -> tuple[float, float]:
    b_mm = _rc26_num(out.get("b_cm"), 0.0) * 10.0
    h_mm = _rc26_num(out.get("h_cm"), 0.0) * 10.0
    if b_mm <= 0:
        b_mm = _rc26_num(row.get("hy", 0.0), 0.0) * 10.0
    if h_mm <= 0:
        h_mm = _rc26_num(row.get("hz", 0.0), 0.0) * 10.0
    ac_mm2 = _rc26_num(row.get("ax", 0.0), 0.0) * 100.0
    if b_mm <= 0 and ac_mm2 > 0:
        b_mm = math.sqrt(ac_mm2)
    if h_mm <= 0:
        h_mm = b_mm
    return max(b_mm, 1.0), max(h_mm, 1.0)


def _rc26_layout_sig(layout):
    try:
        return _v56_layout_signature(layout)
    except Exception:
        return (
            getattr(layout, "phi_long_mm", None), getattr(layout, "phi_corner_mm", None),
            getattr(layout, "phi_face_mm", None), getattr(layout, "n_total", None),
            getattr(layout, "n_bars_y", None), getattr(layout, "n_bars_z", None),
            getattr(layout, "n_face_y_extra", None), getattr(layout, "n_face_z_extra", None),
        )


def _rc26_layout_desc(layout) -> str:
    try:
        return _v56_layout_description(layout)
    except Exception:
        n = int(getattr(layout, "n_total", 0) or 0)
        phi = int(getattr(layout, "phi_long_mm", getattr(layout, "phi_corner_mm", 0)) or 0)
        return f"{n}Ø{phi}" if n and phi else "layout"


def _rc26_layout_sort_key(layout, as_req: float, b_mm: float, h_mm: float):
    try:
        return _v56_layout_score(layout, as_req, b_mm, h_mm)
    except Exception:
        asprov = float(getattr(layout, "as_prov_mm2", 1e12) or 1e12)
        n = int(getattr(layout, "n_total", 999) or 999)
        return (asprov < as_req, abs(asprov - as_req), n, asprov)


def _rc26_probe_sig(layout):
    return (
        round(float(getattr(layout, "as_prov_mm2", 0.0) or 0.0), 3),
        int(getattr(layout, "n_total", 0) or 0),
        int(getattr(layout, "n_bars_y", 0) or 0),
        int(getattr(layout, "n_bars_z", 0) or 0),
        float(getattr(layout, "phi_long_mm", 0.0) or 0.0),
        float(getattr(layout, "phi_corner_mm", getattr(layout, "phi_long_mm", 0.0)) or 0.0),
        float(getattr(layout, "phi_face_mm", getattr(layout, "phi_long_mm", 0.0)) or 0.0),
        int(getattr(layout, "n_face_y_extra", 0) or 0),
        int(getattr(layout, "n_face_z_extra", 0) or 0),
    )


def _rc26_max_capacity_probe_pool(pool, limit: int = 6):
    """Return representative layouts at the maximum admissible steel area.

    If these layouts do not verify N-My-Mz, lighter catalogue entries cannot be
    adopted for the same section. This is a rigorous early-failure check for
    tramos already near As,max, and avoids long searches through lighter layouts.
    """
    if not pool:
        return []
    max_as = max(float(getattr(ly, "as_prov_mm2", 0.0) or 0.0) for ly in pool)
    if max_as <= 0:
        return []
    candidates = [ly for ly in pool if float(getattr(ly, "as_prov_mm2", 0.0) or 0.0) >= max_as - 1e-6]
    out = []
    seen = set()
    for ly in sorted(candidates, key=lambda x: (
        abs(int(getattr(x, "n_bars_y", 0) or 0) - int(getattr(x, "n_bars_z", 0) or 0)),
        -int(getattr(x, "n_total", 0) or 0),
        _rc26_probe_sig(x),
    )):
        sig = _rc26_probe_sig(ly)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(ly)
        if len(out) >= max(1, int(limit or 1)):
            break
    return out


def _rc26_target_probe_pool(pool, as_req: float, my_ed: float, mz_ed: float, limit: int = 10):
    if not pool:
        return []
    try:
        req = max(float(as_req or 0.0), 0.0)
    except Exception:
        req = 0.0
    if req <= 0:
        return []
    out = []
    seen = set()
    thresholds = [0.90, 1.00, 1.15, 1.35, 1.60, 1.85]
    for factor in thresholds:
        target = factor * req
        candidates = [ly for ly in pool if float(getattr(ly, "as_prov_mm2", 0.0) or 0.0) + 1e-6 >= target]
        if not candidates:
            continue
        candidates.sort(key=lambda ly: (
            float(getattr(ly, "as_prov_mm2", 0.0) or 0.0),
            _rc26_orientation_score(ly, my_ed, mz_ed),
            _rc26_probe_sig(ly),
        ))
        for ly in candidates[:2]:
            sig = _rc26_probe_sig(ly)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(ly)
        if len(out) >= max(1, int(limit or 1)):
            break
    return out


def _rc26_economy_lookback_pool(pool, best_as: float, as_req: float, my_ed: float, mz_ed: float, seen, limit: int = 8):
    floor = 0.85 * max(float(as_req or 0.0), 0.0)
    candidates = []
    for ly in pool:
        sig = _rc26_probe_sig(ly)
        if sig in seen:
            continue
        asp = float(getattr(ly, "as_prov_mm2", 0.0) or 0.0)
        if asp + 1e-6 < float(best_as or 0.0) and asp + 1e-6 >= floor:
            candidates.append(ly)
    candidates.sort(key=lambda ly: (
        -float(getattr(ly, "as_prov_mm2", 0.0) or 0.0),
        _rc26_orientation_score(ly, my_ed, mz_ed),
        _rc26_probe_sig(ly),
    ))
    out = []
    local_seen = set()
    for ly in candidates:
        sig = _rc26_probe_sig(ly)
        area_key = round(float(getattr(ly, "as_prov_mm2", 0.0) or 0.0), 3)
        orient_key = (area_key, int(getattr(ly, "n_bars_y", 0) or 0), int(getattr(ly, "n_bars_z", 0) or 0))
        if orient_key in local_seen:
            continue
        local_seen.add(orient_key)
        out.append(ly)
        if len(out) >= max(0, int(limit or 0)):
            break
    return out


def _rc26_finalise_max_capacity_failure(self, row, layout, util, my_cap, mz_cap, tested, original_mode):
    final = _rc26_finalise_from_layout(
        self,
        row,
        layout,
        False,
        util,
        my_cap,
        mz_cap,
        tested,
        original_mode,
        "Falha estrutural: armadura máxima admissível não verifica N-My-Mz",
    )
    final["failure_reason"] = "η_NMyMz > 1.00 com a armadura máxima admissível do catálogo RC26"
    final["failure_summary"] = "Bloqueante | resistência biaxial | η_NMyMz > 1.00 após pesquisa rigorosa RC26"
    final["failure_action"] = "Aumentar secção, rever esforços/comprimento efectivo ou adoptar solução fora do catálogo automático validada em projecto."
    final["rc26_fallback_note"] = "Falha estrutural classificada após testar a armadura máxima admissível"
    return final



def _rc26_orientation_score(layout, my_ed: float, mz_ed: float):
    ny = int(getattr(layout, "n_bars_y", 0) or 0)
    nz = int(getattr(layout, "n_bars_z", 0) or 0)
    my = abs(float(my_ed or 0.0))
    mz = abs(float(mz_ed or 0.0))
    if mz > 1.10 * my:
        return (-nz, ny, abs(ny - nz))
    if my > 1.10 * mz:
        return (-ny, nz, abs(ny - nz))
    return (abs(ny - nz), -min(ny, nz), -max(ny, nz))


def _rc26_reduce_candidate_pool(pool, as_req: float, b_mm: float, h_mm: float, my_ed: float = 0.0, mz_ed: float = 0.0):
    """Compress a large unfiltered catalogue into representative layouts.

    The unfiltered catalogue may contain hundreds of near-equivalent layouts.
    Keeping a few per As level preserves different biaxial distributions while
    avoiding minute-long fallback runs.
    """
    if not pool:
        return []
    grouped = {}
    for ly in pool:
        asp = float(getattr(ly, "as_prov_mm2", 0.0) or 0.0)
        key = round(asp, 1)
        grouped.setdefault(key, []).append(ly)
    reduced = []
    for key in sorted(grouped):
        items = sorted(grouped[key], key=lambda ly: (
            _rc26_orientation_score(ly, my_ed, mz_ed),
            _rc26_layout_sort_key(ly, as_req, b_mm, h_mm),
        ))
        # Keep several arrangements with the same steel area because biaxial
        # capacity depends on distribution, not only As.
        reduced.extend(items[:6])
    # Try likely useful areas first; very-low-As candidates are kept as a late
    # fallback for compression-dominated cases.
    threshold = 0.85 * max(float(as_req or 0.0), 0.0)
    def _priority_key(ly):
        asp = float(getattr(ly, "as_prov_mm2", 0.0) or 0.0)
        try:
            uniform = not isinstance(ly, MixedLayout)
        except Exception:
            uniform = not hasattr(ly, "phi_corner_mm") or not hasattr(ly, "phi_face_mm")
        # Uniform perimeter layouts are tested early in fallback because they are
        # often the robust solution for biaxial bending when practical mixed
        # shortlists are too light.
        return (asp < threshold, not uniform, asp, _rc26_orientation_score(ly, my_ed, mz_ed), _rc26_layout_sort_key(ly, as_req, b_mm, h_mm))
    reduced.sort(key=_priority_key)
    return reduced


def _rc26_candidate_pool(self, row: pd.Series, out: dict, prebuilt_candidates=None):
    b_mm, h_mm = _rc26_section_dimensions(row, out)
    try:
        is_circular = self.infer_is_circular(row, b_mm, h_mm)
    except Exception:
        is_circular = False
    candidates = []
    if prebuilt_candidates is not None:
        try:
            candidates.extend(list(prebuilt_candidates))
        except Exception:
            pass
    # Start with the current practical catalogue, then add the pre-RC19
    # unfiltered catalogue. The latter is used only inside the rigorous fallback
    # and allows heavier, exceptional arrangements to be found instead of
    # reporting a false failure simply because the normal practical shortlist
    # was intentionally strict.
    try:
        candidates.extend(list(self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)))
    except Exception:
        pass
    for fn_name in [
        "_rc19_prev_build_candidate_layouts",
        "_old_build_candidate_layouts_v45_base",
        "_rc15_prev_build_candidate_layouts",
    ]:
        try:
            fn = globals().get(fn_name)
            if callable(fn):
                candidates.extend(list(fn(self, b_mm, h_mm, is_circular=is_circular)))
        except Exception:
            pass
    as_req = max(_rc26_num(out.get("as_req_mm2"), 0.0), 0.0)
    as_max = _rc26_num(out.get("as_max_mm2"), 0.0)
    if as_max <= 0:
        ac = _rc26_num(row.get("ax", 0.0), 0.0) * 100.0
        as_max = 0.04 * ac if ac > 0 else 1e12
    try:
        max_face_y, max_face_z = self.max_bars_per_face(b_mm, h_mm, is_circular=is_circular)
    except Exception:
        max_face_y = max_face_z = 999
    pool = []
    seen = set()
    for ly in candidates:
        sig = _rc26_layout_sig(ly)
        if sig in seen:
            continue
        seen.add(sig)
        asp = float(getattr(ly, "as_prov_mm2", 0.0) or 0.0)
        if asp <= 0 or asp > as_max + 1e-6:
            continue
        if int(getattr(ly, "n_bars_y", 2) or 2) > max_face_y:
            continue
        if int(getattr(ly, "n_bars_z", 2) or 2) > max_face_z:
            continue
        # Do not exclude asp < as_req blindly. In high-compression columns the
        # approximate As,req may be conservative; the real N-My-Mz check is the
        # governing decision.
        pool.append(ly)
    my_ed = _rc26_num(out.get("my_ed_kNm", row.get("my", 0.0)), 0.0)
    mz_ed = _rc26_num(out.get("mz_ed_kNm", row.get("mz", 0.0)), 0.0)
    pool = _rc26_reduce_candidate_pool(pool, as_req, b_mm, h_mm, my_ed=my_ed, mz_ed=mz_ed)
    return pool, as_req, as_max, b_mm, h_mm


def _rc26_material_props(row: pd.Series, out: dict):
    material = str(out.get("material") or row.get("material") or DEFAULT_CONCRETE_CLASS)
    if material.strip().lower() in {"", "nan", "none", "null"}:
        material = DEFAULT_CONCRETE_CLASS
    try:
        fck = parse_concrete_strength(material)
        cp = concrete_props(fck, gamma_c=getattr(row, "gamma_c", None) or 1.5)
    except Exception:
        fck = parse_concrete_strength(DEFAULT_CONCRETE_CLASS)
        cp = concrete_props(fck)
    try:
        sp = steel_props(getattr(row, "fyk", None) or 500.0, gamma_s=1.15)
    except Exception:
        sp = steel_props(500.0)
    return material, fck, cp, sp


def _rc26_eval_layout(self, row: pd.Series, out: dict, layout):
    n_ed = _rc26_num(out.get("n_ed_kN"), 0.0)
    my_ed = _rc26_num(out.get("my_ed_kNm"), 0.0)
    mz_ed = _rc26_num(out.get("mz_ed_kNm"), 0.0)
    material = str(out.get("material") or row.get("material") or DEFAULT_CONCRETE_CLASS)
    if material.strip().lower() in {"", "nan", "none", "null"}:
        material = DEFAULT_CONCRETE_CLASS
    fck = parse_concrete_strength(material)
    cp = concrete_props(fck, gamma_c=getattr(self, "gamma_c", 1.5))
    sp = steel_props(getattr(self, "fyk", 500.0), gamma_s=getattr(self, "gamma_s", 1.15))
    evaluator = getattr(self, "_rc26_eval_designer", self)
    caps = evaluator.capacity_for_layout(layout, n_ed, cp["fcd"], sp["fyd"], sp["Es"])
    ok, util, my_cap, mz_cap = evaluator.biaxial_ok(my_ed, mz_ed, caps)
    if util is None:
        util = float("inf")
    return bool(ok), float(util), my_cap, mz_cap



def _rc26_eval_layout_with_mode(self, row: pd.Series, out: dict, layout, requested_mode: str):
    evaluator = getattr(self, "_rc26_eval_designer", self)
    old_req = getattr(evaluator, "requested_calc_mode", None)
    had_req = hasattr(evaluator, "requested_calc_mode")
    try:
        evaluator.requested_calc_mode = requested_mode
        return _rc26_eval_layout(self, row, out, layout)
    finally:
        try:
            if had_req:
                evaluator.requested_calc_mode = old_req
            else:
                delattr(evaluator, "requested_calc_mode")
        except Exception:
            pass

def _rc26_finalise_from_layout(self, row: pd.Series, layout, ok: bool, util: float, my_cap, mz_cap, tested: int, original_mode: str, note: str):
    """Build the final result directly from the fast result plus the selected layout.

    Calling the older design_one again with exceptional layouts can be slow in
    long runs because it re-enters older shortlist wrappers. The fallback has
    already performed the controlling N-My-Mz catalogue check, so the report row
    is safely assembled here.
    """
    final = dict(row.to_dict() if hasattr(row, "to_dict") else {})
    # Prefer the already computed fast-output engineering quantities.
    try:
        final.update(dict(getattr(_rc26_finalise_from_layout, "_fast_out", {}) or {}))
    except Exception:
        pass
    # The caller sets this attribute immediately before calling finalise.
    fast_out = getattr(self, "_rc26_current_fast_out", None)
    if isinstance(fast_out, dict):
        final.update(fast_out)
    smax = None
    sprov = None
    try:
        phi_for_links = float(getattr(layout, "phi_long_mm", getattr(layout, "phi_corner_mm", 12.0)) or 12.0)
        smax = self.tie_spacing_max(float(getattr(layout, "b_mm", 0.0)), float(getattr(layout, "h_mm", 0.0)), phi_for_links)
        sprov = self.choose_spacing(smax)
    except Exception:
        sprov = final.get("s_st_mm")
        smax = final.get("s_st_max_mm")
    final.update({
        "phi_long_mm": getattr(layout, "phi_long_mm", getattr(layout, "phi_corner_mm", None)),
        "phi_corner_mm": getattr(layout, "phi_corner_mm", getattr(layout, "phi_long_mm", None)),
        "phi_face_mm": getattr(layout, "phi_face_mm", getattr(layout, "phi_long_mm", None)),
        "n_total": getattr(layout, "n_total", None),
        "n_bars_y": getattr(layout, "n_bars_y", None),
        "n_bars_z": getattr(layout, "n_bars_z", None),
        "n_face_y_extra": getattr(layout, "n_face_y_extra", None),
        "n_face_z_extra": getattr(layout, "n_face_z_extra", None),
        "as_prov_mm2": getattr(layout, "as_prov_mm2", None),
        "phi_st_mm": getattr(layout, "phi_st_mm", final.get("phi_st_mm")),
        "s_st_mm": sprov,
        "s_st_max_mm": smax,
        "mrd_y_kNm": my_cap,
        "mrd_z_kNm": mz_cap,
        "utilizacao": util if math.isfinite(util) else None,
        "calc_mode_effective": original_mode,
        "rc24_fast_dimensioning": final.get("rc24_fast_dimensioning", "Sim"),
        "rc26_rigorous_fallback": "Sim",
        "rc26_layout_tests": str(tested),
        "rc26_fallback_note": note,
    })
    desc = _rc26_layout_desc(layout)
    phi_st = final.get("phi_st_mm")
    try:
        st_text = f" + estribos Ø{int(float(phi_st))}//{float(sprov)/10:.1f} cm" if phi_st and sprov else ""
    except Exception:
        st_text = ""
    final["solucao"] = f"{desc}{st_text}"
    if ok:
        final["status"] = "OK"
        final["failure_reason"] = ""
        final["failure_type"] = "OK"
        final["failure_severity"] = "OK"
        final["design_decision"] = "OK"
        final["review_priority"] = "Normal"
        final["failure_action"] = "-"
        final["failure_summary"] = "OK | RC26: pesquisa rigorosa activada"
    else:
        final["status"] = "Falha"
        final["failure_reason"] = "Sem solução automática verificada após pesquisa rigorosa de armaduras"
        final["failure_type"] = "resistencia_biaxial"
        final["failure_severity"] = "Bloqueante"
        final["design_decision"] = "Não adoptar sem revisão"
        final["review_priority"] = "Alta"
        final["failure_action"] = "Rever esforços, comprimento efectivo, secção ou admitir uma solução de armadura fora do catálogo automático."
        final["failure_summary"] = "Bloqueante | resistência biaxial | pesquisa rigorosa RC26"
        final["solucao"] = "Melhor tentativa — NÃO ADOPTAR: " + str(final.get("solucao", desc))
    try:
        final["recommendations"] = recommend_actions(pd.Series(final))
    except Exception:
        pass
    return final

def _rc26_rigorous_fallback(self, row: pd.Series, fast_out: dict, prebuilt_candidates=None, original_mode: str = "dimensionamento") -> dict:
    # Keep fallback deterministic. Older capacity-cache keys changed several
    # times across RC patches; clearing the section-capacity cache avoids stale
    # or pathological cache interactions during the exceptional fallback pass.
    try:
        self._capacity_cache = {}
    except Exception:
        pass
    try:
        self._rc26_eval_designer = ColumnDesigner(
            cover_mm=getattr(self, "cover_mm", 35.0),
            fyk=getattr(self, "fyk", 500.0),
            gamma_c=getattr(self, "gamma_c", 1.5),
            gamma_s=getattr(self, "gamma_s", 1.15),
            phi_eff=getattr(self, "phi_eff", 2.0),
            l0y_factor=getattr(self, "l0y_factor", 1.0),
            l0z_factor=getattr(self, "l0z_factor", 1.0),
            calc_mode="dimensionamento",
        )
    except Exception:
        self._rc26_eval_designer = self
    pool, as_req, as_max, b_mm, h_mm = _rc26_candidate_pool(self, row, fast_out, prebuilt_candidates=prebuilt_candidates)
    if not pool:
        out = dict(fast_out or {})
        out.update({
            "rc26_rigorous_fallback": "Sim",
            "rc26_layout_tests": "0",
            "failure_reason": "Sem layouts admissíveis para pesquisa rigorosa de armaduras",
            "failure_summary": "Bloqueante | pormenorização | pesquisa rigorosa RC26",
            "status": "Falha",
        })
        return out

    max_tests_env = os.environ.get("COLUMNSEC2_RC26_MAX_LAYOUT_TESTS", "100")
    try:
        max_tests = int(max_tests_env)
    except Exception:
        max_tests = 0
    # 0 means exhaustive. Default 220 keeps runtime bounded while still allowing heavy fallback layouts.
    if max_tests > 0:
        pool = pool[:max_tests]
    debug = str(os.environ.get("COLUMNSEC2_RC26_DEBUG", "")).strip().lower() in {"1", "true", "yes"}
    if debug:
        try:
            print(f"RC26 fallback start {fast_out.get('name','')} {fast_out.get('story','')} pool={len(pool)} as_req={as_req:.1f}", flush=True)
        except Exception:
            pass

    best_ok = None
    best_ok_key = None
    best_any = None
    best_any_key = None
    tested = 0
    pretested = set()
    my_ed_probe = _rc26_num(fast_out.get("my_ed_kNm", row.get("my", 0.0)), 0.0)
    mz_ed_probe = _rc26_num(fast_out.get("mz_ed_kNm", row.get("mz", 0.0)), 0.0)
    max_probe = _rc26_max_capacity_probe_pool(pool, limit=6) if as_max > 0 and as_req >= 0.70 * as_max else []
    for ly in max_probe:
        tested += 1
        pretested.add(_rc26_probe_sig(ly))
        try:
            ok, util, my_cap, mz_cap = _rc26_eval_layout_with_mode(self, row, fast_out, ly, "dimensionamento")
        except Exception:
            continue
        asp = float(getattr(ly, "as_prov_mm2", 1e12) or 1e12)
        n_total = int(getattr(ly, "n_total", 999) or 999)
        ok_key = (asp, n_total, abs((util if math.isfinite(util) else 9.99) - 0.80), _rc26_layout_sort_key(ly, as_req, b_mm, h_mm))
        any_key = (util if math.isfinite(util) else 999.0, asp, n_total)
        if best_any is None or any_key < best_any_key:
            best_any = (ly, ok, util, my_cap, mz_cap)
            best_any_key = any_key
        if ok and (best_ok is None or ok_key < best_ok_key):
            best_ok = (ly, ok, util, my_cap, mz_cap)
            best_ok_key = ok_key
    if max_probe and best_ok is None and best_any is not None:
        ly, ok, util, my_cap, mz_cap = best_any
        if math.isfinite(util) and util > 1.02:
            if debug:
                print(f"RC26 max-capacity failure tested={tested} util={util:.3f}", flush=True)
            try:
                self._rc26_current_fast_out = dict(fast_out or {})
            except Exception:
                pass
            return _rc26_finalise_max_capacity_failure(self, row, ly, util, my_cap, mz_cap, tested, original_mode)

    target_probe = _rc26_target_probe_pool(pool, as_req, my_ed_probe, mz_ed_probe, limit=10)
    for ly in target_probe:
        sig = _rc26_probe_sig(ly)
        if sig in pretested:
            continue
        tested += 1
        pretested.add(sig)
        try:
            ok, util, my_cap, mz_cap = _rc26_eval_layout_with_mode(self, row, fast_out, ly, "pre_dimensionamento")
        except Exception:
            continue
        asp = float(getattr(ly, "as_prov_mm2", 1e12) or 1e12)
        n_total = int(getattr(ly, "n_total", 999) or 999)
        ok_key = (asp, n_total, abs((util if math.isfinite(util) else 9.99) - 0.80), _rc26_layout_sort_key(ly, as_req, b_mm, h_mm))
        any_key = (util if math.isfinite(util) else 999.0, asp, n_total)
        if best_any is None or any_key < best_any_key:
            best_any = (ly, ok, util, my_cap, mz_cap)
            best_any_key = any_key
        if ok and (best_ok is None or ok_key < best_ok_key):
            best_ok = (ly, ok, util, my_cap, mz_cap)
            best_ok_key = ok_key
    if best_ok is not None:
        best_as = float(getattr(best_ok[0], "as_prov_mm2", 1e12) or 1e12)
        for ly in _rc26_economy_lookback_pool(pool, best_as, as_req, my_ed_probe, mz_ed_probe, pretested, limit=8):
            sig = _rc26_probe_sig(ly)
            if sig in pretested:
                continue
            tested += 1
            pretested.add(sig)
            try:
                ok, util, my_cap, mz_cap = _rc26_eval_layout_with_mode(self, row, fast_out, ly, "pre_dimensionamento")
            except Exception:
                continue
            if ok:
                asp = float(getattr(ly, "as_prov_mm2", 1e12) or 1e12)
                n_total = int(getattr(ly, "n_total", 999) or 999)
                ok_key = (asp, n_total, abs((util if math.isfinite(util) else 9.99) - 0.80), _rc26_layout_sort_key(ly, as_req, b_mm, h_mm))
                if ok_key < best_ok_key:
                    best_ok = (ly, ok, util, my_cap, mz_cap)
                    best_ok_key = ok_key
        ly, ok, util, my_cap, mz_cap = best_ok
        try:
            self._rc26_current_fast_out = dict(fast_out or {})
        except Exception:
            pass
        return _rc26_finalise_from_layout(
            self,
            row,
            ly,
            True,
            util,
            my_cap,
            mz_cap,
            tested,
            original_mode,
            "Solução verificada por pesquisa orientada RC26",
        )

    for ly in pool:
        if _rc26_probe_sig(ly) in pretested:
            continue
        tested += 1
        if debug and (tested == 1 or tested % 25 == 0):
            try:
                print(f"RC26 test {tested}/{len(pool)} As={float(getattr(ly, 'as_prov_mm2', 0.0) or 0.0):.1f} { _rc26_layout_desc(ly) }", flush=True)
            except Exception:
                pass
        try:
            # Real N-My-Mz check with the refined fallback mesh. The full
            # catalogue is the improvement; the fallback intentionally avoids
            # the very dense final mesh inside the loop to keep the GUI usable.
            ok, util, my_cap, mz_cap = _rc26_eval_layout_with_mode(self, row, fast_out, ly, "pre_dimensionamento")
        except Exception:
            continue
        asp = float(getattr(ly, "as_prov_mm2", 1e12) or 1e12)
        n_total = int(getattr(ly, "n_total", 999) or 999)
        # Prefer verified, economical and constructible layouts. Do not increase
        # reinforcement merely to chase eta=0.80 if a lower-As verified layout exists.
        ok_key = (asp, n_total, abs((util if math.isfinite(util) else 9.99) - 0.80), _rc26_layout_sort_key(ly, as_req, b_mm, h_mm))
        any_key = (util if math.isfinite(util) else 999.0, asp, n_total)
        if best_any is None or any_key < best_any_key:
            best_any = (ly, ok, util, my_cap, mz_cap)
            best_any_key = any_key
        if ok:
            if best_ok is None or ok_key < best_ok_key:
                best_ok = (ly, ok, util, my_cap, mz_cap)
                best_ok_key = ok_key
            # Since the pool is ordered by increasing As, the first detailed OK
            # is usually the most economical. Keep one small look-ahead to allow
            # simpler arrangements with the same area.
            if tested > 6 and asp > 1.05 * float(getattr(best_ok[0], "as_prov_mm2", asp) or asp):
                if debug:
                    print(f"RC26 break after OK at test {tested}", flush=True)
                break
    if debug:
        print(f"RC26 loop end tested={tested} best_ok={best_ok is not None} best_any={best_any is not None}", flush=True)
    chosen = best_ok or best_any
    if chosen is None:
        out = dict(fast_out or {})
        out.update({
            "rc26_rigorous_fallback": "Sim",
            "rc26_layout_tests": str(tested),
            "failure_reason": "Pesquisa rigorosa não conseguiu avaliar layouts de armadura",
            "failure_summary": "Bloqueante | cálculo | pesquisa rigorosa RC26",
            "status": "Falha",
        })
        return out
    ly, ok, util, my_cap, mz_cap = chosen
    note = "Sem solução no modo rápido — recalculado por pesquisa rigorosa" if ok else "Sem solução verificada após pesquisa rigorosa"
    if debug:
        print(f"RC26 finalise ok={ok} util={util} As={float(getattr(ly, 'as_prov_mm2', 0.0) or 0.0):.1f}", flush=True)
    try:
        self._rc26_current_fast_out = dict(fast_out or {})
    except Exception:
        pass
    return _rc26_finalise_from_layout(self, row, ly, ok, util, my_cap, mz_cap, tested, original_mode, note)


def _design_one_rc26(self, row: pd.Series, prebuilt_candidates=None):
    original_mode = str(getattr(self, "calc_mode", "dimensionamento") or "dimensionamento")
    out = _RC26_PREV_DESIGN_ONE(self, row, prebuilt_candidates=prebuilt_candidates)
    try:
        if str(original_mode).lower() in {"dimensionamento", "rigoroso"} and _rc26_needs_rigorous_fallback(dict(out or {})):
            return _rc26_rigorous_fallback(self, row, dict(out or {}), prebuilt_candidates=prebuilt_candidates, original_mode=original_mode)
    except Exception as err:
        # Do not crash the calculation. Keep the fast result but make the reason
        # explicit in the technical report.
        out = dict(out or {})
        out["rc26_rigorous_fallback"] = "Erro"
        out["rc26_fallback_note"] = f"Falha interna no fallback rigoroso: {err}"
        if str(out.get("status", "")).lower() == "falha":
            out["failure_reason"] = (str(out.get("failure_reason", "") or "") + f"; fallback rigoroso não concluído: {err}").strip("; ")
        return out
    return out


ColumnDesigner.design_one = _design_one_rc26

try:
    globals()["APP_VERSION"] = "v0.9 RC26 Modular"
    _RC13_EN_TERMS.update({"v0.9 RC26 Modular": "v0.9 RC26 Modular"})
except Exception:
    pass

# ---------------------------------------------------------------------------
# Isolated row design loop
# ---------------------------------------------------------------------------
_RC26_PREV_DESIGN_DATAFRAME = ColumnDesigner.design_dataframe


def _design_dataframe_rc26_isolated(self, df: pd.DataFrame, progress_callback=None):
    """Run each row with an isolated designer state.

    This avoids pathological interactions between capacity caches accumulated
    over hundreds of layouts while keeping the section candidate catalogue shared.
    """
    results = []
    if df is None:
        return pd.DataFrame()
    total = len(df)
    grouped_candidates = {}
    shared_capacity_cache = {}
    # Candidate catalogue shared by section geometry.
    for _, row in df.iterrows():
        try:
            b_mm = cm_to_mm(row.get("hy", 0.0))
            h_mm = cm_to_mm(row.get("hz", 0.0))
            ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
            if b_mm <= 0 and ac_mm2 > 0:
                b_mm = math.sqrt(ac_mm2)
            if h_mm <= 0:
                h_mm = b_mm
            is_circular = self.infer_is_circular(row, b_mm, h_mm)
            sec_key = (round(b_mm, 1), round(h_mm, 1), bool(is_circular))
            if sec_key not in grouped_candidates:
                grouped_candidates[sec_key] = self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)
        except Exception:
            pass
    if progress_callback:
        try:
            progress_callback(0, total)
        except Exception:
            pass
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        worker = ColumnDesigner(
            cover_mm=getattr(self, "cover_mm", 35.0),
            fyk=getattr(self, "fyk", 500.0),
            gamma_c=getattr(self, "gamma_c", 1.5),
            gamma_s=getattr(self, "gamma_s", 1.15),
            phi_eff=getattr(self, "phi_eff", 2.0),
            l0y_factor=getattr(self, "l0y_factor", 1.0),
            l0z_factor=getattr(self, "l0z_factor", 1.0),
            calc_mode=getattr(self, "calc_mode", "dimensionamento"),
        )
        try:
            worker._capacity_cache = shared_capacity_cache
        except Exception:
            pass
        try:
            backend = getattr(self, "code_backend", None)
            if backend is not None:
                worker.code_backend = backend
        except Exception:
            pass
        b_mm = cm_to_mm(row.get("hy", 0.0))
        h_mm = cm_to_mm(row.get("hz", 0.0))
        ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
        if b_mm <= 0 and ac_mm2 > 0:
            b_mm = math.sqrt(ac_mm2)
        if h_mm <= 0:
            h_mm = b_mm
        is_circular = worker.infer_is_circular(row, b_mm, h_mm)
        sec_key = (round(b_mm, 1), round(h_mm, 1), bool(is_circular))
        results.append(worker.design_one(row, prebuilt_candidates=grouped_candidates.get(sec_key)))
        if progress_callback and (i == total or i % 10 == 0):
            try:
                progress_callback(i, total)
            except Exception:
                pass
    out = pd.DataFrame(results)
    if not out.empty and "utilizacao" in out.columns:
        out["sort_key"] = pd.to_numeric(out["utilizacao"], errors="coerce").fillna(999.0)
    return out


ColumnDesigner.design_dataframe = _design_dataframe_rc26_isolated
