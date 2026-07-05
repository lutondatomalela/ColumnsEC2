# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC15 — practical reinforcement catalogue and summary consolidation.

This patch refines the RC14 automatic reinforcement policy:
- Ø25 and Ø32 remain outside the automatic catalogue;
- rectangular-column corner bars are selected from Ø10/Ø12/Ø16/Ø20,
  with Ø12/Ø16 preferred and Ø20 used only when necessary;
- face-distribution bars are selected from Ø10/Ø12/Ø16 only;
- Ø10 is discouraged as a main/corner/perimeter bar unless the column is small
  and lightly reinforced;
- candidate generation is spacing-based rather than limited by an arbitrary
  100 mm bar pitch, allowing more Ø16 face bars before declaring failure;
- the summary is rebuilt as one row per physical segment and the adopted
  arrangement is rationalised by column line where practical.
"""

APP_VERSION = "v0.9 RC15 Modular"

# ---------------------------------------------------------------------------
# Reinforcement catalogue policy
# ---------------------------------------------------------------------------

_RC15_CORNER_DIAMS = [10.0, 12.0, 16.0, 20.0]
_RC15_FACE_DIAMS = [10.0, 12.0, 16.0]
_RC15_CIRC_DIAMS = [10.0, 12.0, 16.0, 20.0]
_RC15_MAX_AUTO_PHI = 20.0
_RC15_MAX_FACE_PHI = 16.0


def _rc15_phi_corner(layout):
    try:
        return float(getattr(layout, "phi_corner_mm"))
    except Exception:
        try:
            return float(getattr(layout, "phi_long_mm"))
        except Exception:
            return 0.0


def _rc15_phi_face(layout):
    try:
        return float(getattr(layout, "phi_face_mm"))
    except Exception:
        try:
            return float(getattr(layout, "phi_long_mm"))
        except Exception:
            return 0.0


def _rc15_phi_max(layout):
    vals = []
    for attr in ("phi_long_mm", "phi_corner_mm", "phi_face_mm"):
        try:
            v = float(getattr(layout, attr))
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    return max(vals) if vals else 0.0


def _rc15_is_circular_layout(layout):
    try:
        return isinstance(layout, CircularLayout) or str(getattr(layout, "layout_type", "")).lower().startswith("circ") or bool(getattr(layout, "is_circular", False))
    except Exception:
        return False


def _rc15_spacing_max_bars(dim_mm, cover_mm, phi_st_mm, phi_ref_mm):
    """Maximum number of bars along one face from spacing constraints.

    This replaces the earlier rough 100 mm pitch cap. It is still conservative:
    it uses the largest automatic bar diameter as reference, then the existing
    clear-spacing check is applied to every generated layout.
    """
    try:
        dim = float(dim_mm)
        c = float(cover_mm)
        st = float(phi_st_mm)
        ph = float(phi_ref_mm)
        edge = c + st + ph / 2.0
        span = dim - 2.0 * edge
        req_clear = max(20.0, ph, 25.0)
        pitch_min = ph + req_clear
        if span <= 0 or pitch_min <= 0:
            return 2
        n = int(math.floor(span / pitch_min)) + 1
        return max(2, min(n, 8))
    except Exception:
        return 2


def _rc15_max_bars_per_face(self, b_mm, h_mm, is_circular=False):
    if is_circular:
        try:
            d = min(float(b_mm), float(h_mm))
            phi_ref = 16.0
            phi_st = self.choose_stirrup(phi_ref)
            r = d / 2.0 - float(self.cover_mm) - phi_st - phi_ref / 2.0
            if r <= 0:
                return 6, 6
            req_clear = max(20.0, phi_ref, 25.0)
            pitch_min = phi_ref + req_clear
            n = int(math.floor(2.0 * math.pi * r / pitch_min))
            n = max(6, min(n, 32))
            return n, n
        except Exception:
            return 8, 8
    phi_ref = _RC15_MAX_AUTO_PHI
    phi_st = self.choose_stirrup(phi_ref)
    ny = _rc15_spacing_max_bars(b_mm, self.cover_mm, phi_st, phi_ref)
    nz = _rc15_spacing_max_bars(h_mm, self.cover_mm, phi_st, phi_ref)
    return ny, nz

ColumnDesigner.max_bars_per_face = _rc15_max_bars_per_face


def _rc15_layout_allowed(layout):
    """Hard filter for the automatic catalogue."""
    pc = _rc15_phi_corner(layout)
    pf = _rc15_phi_face(layout)
    pmax = _rc15_phi_max(layout)
    if pmax > _RC15_MAX_AUTO_PHI + 1e-9:
        return False
    if _rc15_is_circular_layout(layout):
        return pmax <= _RC15_MAX_AUTO_PHI + 1e-9
    # Face-distribution bars are limited to Ø16. Corner-only 4Ø20 remains valid.
    try:
        n_total = int(getattr(layout, "n_total", 0))
    except Exception:
        n_total = 0
    if n_total > 4 and pf > _RC15_MAX_FACE_PHI + 1e-9:
        return False
    if pc > _RC15_MAX_AUTO_PHI + 1e-9:
        return False
    return True


def _rc15_layout_score(layout, as_target: float, b_mm: float, h_mm: float):
    """Rank practical layouts for ordinary building columns.

    The score deliberately avoids literal minimum-As selection when it would
    lead to poor detailing. Ø12/Ø16 are preferred for corner/perimeter bars,
    Ø20 is allowed when demanded by resistance, and Ø10 corners/perimeter bars
    are strongly discouraged except for genuinely light columns.
    """
    asprov = float(getattr(layout, "as_prov_mm2", 0.0) or 0.0)
    n = int(getattr(layout, "n_total", 999) or 999)
    pc = _rc15_phi_corner(layout)
    pf = _rc15_phi_face(layout)
    pmax = _rc15_phi_max(layout)
    ac = max(float(b_mm or 0.0) * float(h_mm or 0.0), 1.0)
    as_t = float(as_target or 0.0)
    deficit = max(0.0, as_t - asprov)
    excess = max(0.0, asprov - as_t)
    excess_ratio = excess / max(as_t, 1.0)
    small_light = (min(float(b_mm or 0.0), float(h_mm or 0.0)) <= 300.0 and as_t <= max(450.0, 0.0035 * ac))

    # Hard constraints are represented as the first tuple item so they always win.
    hard = 0.0
    if not _rc15_layout_allowed(layout):
        hard += 1_000_000.0

    if _rc15_is_circular_layout(layout):
        p10 = 0.0 if (pc <= 10.0 + 1e-9 and small_light) else (2500.0 if pc <= 10.0 + 1e-9 else 0.0)
        preferred = 0.0 if 12.0 - 1e-9 <= pc <= 16.0 + 1e-9 else 180.0
        p20 = 420.0 if pc >= 20.0 - 1e-9 and as_t < 0.010 * ac else 80.0 if pc >= 20.0 - 1e-9 else 0.0
        p_many = max(0, n - 18) * 18.0
        return (hard, deficit, p10 + preferred + p20, excess_ratio, excess / 100.0, p_many, n, asprov)

    p_face20 = 10_000.0 if (n > 4 and pf > _RC15_MAX_FACE_PHI + 1e-9) else 0.0
    p_corner10 = 0.0 if (pc <= 10.0 + 1e-9 and small_light) else (2400.0 if pc <= 10.0 + 1e-9 else 0.0)
    p_corner_preferred = 0.0 if 12.0 - 1e-9 <= pc <= 16.0 + 1e-9 else 160.0
    p_corner20 = 500.0 if pc >= 20.0 - 1e-9 and as_t < 0.010 * ac else 90.0 if pc >= 20.0 - 1e-9 else 0.0
    p_mixed = abs(pc - pf) * 42.0
    # More bars are acceptable when this avoids Ø25/Ø32; penalise only excessive congestion.
    p_many = max(0, n - 18) * 16.0
    imbalance = abs(int(getattr(layout, "n_bars_y", 2)) - int(getattr(layout, "n_bars_z", 2)))
    return (hard, deficit, p_face20 + p_corner10 + p_corner_preferred + p_corner20 + p_mixed, excess_ratio, excess / 100.0, p_many, imbalance, n, asprov)

_v56_layout_score = _rc15_layout_score


def _rc15_build_candidate_layouts(self, b_mm, h_mm, is_circular=False):
    key = ("rc15", round(float(b_mm), 1), round(float(h_mm), 1), round(float(self.cover_mm), 1), bool(is_circular))
    if key in self._layout_cache:
        return self._layout_cache[key]

    layouts = []
    seen = set()

    def _add(ly):
        try:
            if not _rc15_layout_allowed(ly):
                return
            if int(getattr(ly, "n_total", 0)) <= 0:
                return
            if not ly.clear_spacing_ok():
                return
            try:
                ok_spacing, _clear, _req = _v56_clear_spacing_from_layout(ly)
                if not ok_spacing:
                    return
            except Exception:
                pass
            try:
                sig = _v56_layout_signature(ly)
            except Exception:
                sig = (type(ly).__name__, round(float(getattr(ly, "as_prov_mm2", 0.0)), 1), int(getattr(ly, "n_total", 0)), _rc15_phi_corner(ly), _rc15_phi_face(ly))
            if sig in seen:
                return
            seen.add(sig)
            layouts.append(ly)
        except Exception:
            return

    if is_circular:
        d = min(float(b_mm), float(h_mm))
        for phi in _RC15_CIRC_DIAMS:
            phi_st = self.choose_stirrup(phi)
            for n in [6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32]:
                _add(CircularLayout(phi, phi_st, n, d, d, self.cover_mm))
        layouts.sort(key=lambda ly: _rc15_layout_score(ly, 0.0, b_mm, h_mm))
        self._layout_cache[key] = layouts
        return layouts

    max_y, max_z = self.max_bars_per_face(b_mm, h_mm, is_circular=False)
    max_y = max(2, int(max_y))
    max_z = max(2, int(max_z))

    # Corner-only alternatives.
    for pc in _RC15_CORNER_DIAMS:
        _add(MixedLayout(pc, pc, 0, 0, b_mm, h_mm, self.cover_mm, self.choose_stirrup(pc)))

    # Mixed alternatives: face bars limited to Ø10/Ø12/Ø16.
    for pc in _RC15_CORNER_DIAMS:
        for pf in _RC15_FACE_DIAMS:
            if pf > pc:
                continue
            phi_st = self.choose_stirrup(max(pc, pf))
            for ey in range(0, max_y - 1):
                for ez in range(0, max_z - 1):
                    if ey == 0 and ez == 0:
                        continue
                    ly = MixedLayout(pc, pf, ey, ez, b_mm, h_mm, self.cover_mm, phi_st)
                    if ly.n_bars_y > max_y or ly.n_bars_z > max_z:
                        continue
                    if int(getattr(ly, "n_total", 0)) > 32:
                        continue
                    _add(ly)

    # Legacy uniform layouts are retained only when they respect the RC15 policy.
    try:
        for ly in list(_old_build_candidate_layouts_v45_base(self, b_mm, h_mm, is_circular=False)):
            if int(getattr(ly, "n_total", 0)) <= 32 and _rc15_layout_allowed(ly):
                _add(ly)
    except Exception:
        pass

    layouts.sort(key=lambda ly: _rc15_layout_score(ly, 0.0, b_mm, h_mm))
    self._layout_cache[key] = layouts
    return layouts

ColumnDesigner.build_candidate_layouts = _rc15_build_candidate_layouts


_rc15_prev_designer_init = ColumnDesigner.__init__
def _rc15_designer_init(self, *args, **kwargs):
    _rc15_prev_designer_init(self, *args, **kwargs)
    try:
        self.long_diams = [10.0, 12.0, 16.0, 20.0]
    except Exception:
        pass
ColumnDesigner.__init__ = _rc15_designer_init


# ---------------------------------------------------------------------------
# Result annotation and clearer catalogue-failure messages
# ---------------------------------------------------------------------------

_rc15_prev_design_one = ColumnDesigner.design_one

def _rc15_design_one(self, row, prebuilt_candidates=None):
    out = _rc15_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)
    if not isinstance(out, dict):
        return out
    try:
        pc = safe_float(out.get("phi_corner_mm", out.get("phi_long_mm", 0.0)), 0.0)
        pf = safe_float(out.get("phi_face_mm", out.get("phi_long_mm", 0.0)), 0.0)
        shape = str(out.get("section_shape", "") or "").lower()
        eta = safe_float(out.get("η_NMyMz", out.get("eta_NMyMz", out.get("utilizacao", 0.0))), 0.0)
        nratio = safe_float(out.get("biaxial_n_ratio", 0.0), 0.0)
        if pf > _RC15_MAX_FACE_PHI + 1e-9 and not shape.startswith("circ"):
            out["warning_reason"] = (str(out.get("warning_reason", "") or "") + "; RC15 policy: face-distribution bars should not exceed Ø16 in the automatic catalogue").strip("; ")
        if pc <= 10.0 + 1e-9 and (eta > 0.35 or nratio > 0.20):
            out["warning_reason"] = (str(out.get("warning_reason", "") or "") + "; RC15 policy: Ø10 main/corner bars retained only for lightly loaded columns").strip("; ")
        if str(out.get("status", "")).lower().startswith("falha") or str(out.get("status", "")).lower().startswith("failure"):
            fr = str(out.get("failure_reason", "") or "")
            if "catálogo" in fr.lower() or "catalogue" in fr.lower() or "interação" in fr.lower() or "interaction" in fr.lower():
                extra = "Não foi encontrada solução automática com Ø≤20 nos cantos/perímetro, Ø≤16 nas faces e As≤As,max. Recomenda-se aumentar a secção, rever esforços/comprimentos efectivos ou activar uma solução especial fora do catálogo automático."
                out["failure_reason"] = (fr + "; " + extra).strip("; ") if fr else extra
                out["failure_action"] = "Aumentar secção, rever esforços/comprimentos efectivos ou activar catálogo especial de armaduras."
    except Exception:
        pass
    return out

ColumnDesigner.design_one = _rc15_design_one


# ---------------------------------------------------------------------------
# Robust physical-segment summary and column-line rationalisation
# ---------------------------------------------------------------------------

def _rc15_as_value(row):
    for c in ["as_prov_mm2", "As,prov [mm²]", "As prov [mm²]", "As local [mm²]"]:
        try:
            if c in row and math.isfinite(safe_float(row.get(c), float("nan"))):
                return safe_float(row.get(c), 0.0)
        except Exception:
            pass
    return 0.0


def _rc15_solution_value(row):
    for c in ["solucao_completa", "Solução", "solucao", "Solução local", "Solução adoptada"]:
        try:
            val = str(row.get(c, "") or "").strip()
            if val:
                return val
        except Exception:
            pass
    return ""


def _rc15_status_value(row):
    for c in ["estado_global", "status", "Estado"]:
        try:
            val = str(row.get(c, "") or "").strip()
            if val:
                return val
        except Exception:
            pass
    return ""


def _rc15_solution_with_corner(row, corner_phi):
    face_phi = min(_RC15_MAX_FACE_PHI, safe_float(row.get("phi_face_mm", row.get("phi_long_mm", corner_phi)), corner_phi))
    n_total = int(safe_float(row.get("n_total", 4), 4))
    n_face = max(0, n_total - 4)
    phi_st = safe_float(row.get("phi_st_mm", 8.0), 8.0)
    s_st = safe_float(row.get("s_st_mm", 0.0), 0.0)
    if str(row.get("section_shape", "")).lower().startswith("circ"):
        core = f"{n_total}Ø{int(max(corner_phi, face_phi))} distribuídos no perímetro"
    elif n_face > 0:
        core = f"4Ø{int(corner_phi)} nos cantos + {n_face}Ø{int(face_phi)} distribuídos nas faces"
    else:
        core = f"4Ø{int(corner_phi)} nos cantos"
    links = f"estribos Ø{int(phi_st)}//{s_st:.0f} mm" if s_st else f"estribos Ø{int(phi_st)}"
    return f"{core}; {links}"


def _rc15_as_with_corner(row, corner_phi):
    face_phi = min(_RC15_MAX_FACE_PHI, safe_float(row.get("phi_face_mm", row.get("phi_long_mm", corner_phi)), corner_phi))
    n_total = int(safe_float(row.get("n_total", 4), 4))
    n_face = max(0, n_total - 4)
    return 4.0 * bar_area_mm2(corner_phi) + n_face * bar_area_mm2(face_phi)


def _rc15_governing_score_df(work):
    try:
        if "_rc12_governing_score" in globals():
            return _rc12_governing_score(work)
    except Exception:
        pass
    eta = pd.to_numeric(work.get("η_NMyMz", work.get("eta_NMyMz", work.get("utilizacao", 0))), errors="coerce").fillna(0.0)
    n = pd.to_numeric(work.get("n_ed_kN", 0), errors="coerce").abs().fillna(0.0)
    my = pd.to_numeric(work.get("my_ed_kNm", 0), errors="coerce").abs().fillna(0.0)
    mz = pd.to_numeric(work.get("mz_ed_kNm", 0), errors="coerce").abs().fillna(0.0)
    st = work.get("estado_global", work.get("status", pd.Series("", index=work.index))).astype(str).str.lower()
    fail_boost = st.str.contains("falha|failure|não conforme|not compliant", regex=True, na=False).astype(float) * 1e6
    warn_boost = st.str.contains("aviso|warning|verificar|check", regex=True, na=False).astype(float) * 1e4
    return fail_boost + warn_boost + eta * 1000.0 + n * 0.01 + my + mz


def _rc15_build_summary(self, results):
    if results is None or getattr(results, "empty", True):
        return pd.DataFrame()
    work = results.copy()
    try:
        if "_rc12_normalise_result_df" in globals():
            work = _rc12_normalise_result_df(work)
    except Exception:
        pass
    try:
        if "_v65_apply_module_statuses" in globals():
            work = _v65_apply_module_statuses(work)
    except Exception:
        pass
    try:
        if "_v68_apply_constructive_detailing" in globals():
            work = _v68_apply_constructive_detailing(work)
    except Exception:
        pass
    try:
        if "_rc12_normalise_result_df" in globals():
            work = _rc12_normalise_result_df(work)
    except Exception:
        pass

    try:
        work["Prumada"] = work.apply(_rc12_prumada, axis=1) if "_rc12_prumada" in globals() else work.get("name", work.get("member", ""))
    except Exception:
        work["Prumada"] = work.get("name", work.get("member", ""))
    try:
        work["Piso"] = work.apply(_rc12_storey, axis=1) if "_rc12_storey" in globals() else work.get("story", "")
    except Exception:
        work["Piso"] = work.get("story", "")
    try:
        work["_story_sort_tuple"] = work.apply(_rc12_story_sort, axis=1) if "_rc12_story_sort" in globals() else [(0,0.0,str(v)) for v in work["Piso"]]
    except Exception:
        work["_story_sort_tuple"] = [(0,0.0,str(v)) for v in work.get("Piso", pd.Series("", index=work.index))]
    try:
        work["_section_signature"] = work.apply(_rc12_section_signature, axis=1) if "_rc12_section_signature" in globals() else work.apply(lambda r: f"{r.get('b_cm','')}x{r.get('h_cm','')}|{r.get('material','')}", axis=1)
    except Exception:
        work["_section_signature"] = ""
    if "member" not in work.columns:
        work["member"] = ""
    work["_gov_score_rc15"] = _rc15_governing_score_df(work)

    rows = []
    group_cols = ["Prumada", "Piso", "member", "_section_signature"]
    for _, grp in work.groupby(group_cols, dropna=False, sort=False):
        g = grp.sort_values("_gov_score_rc15", ascending=False)
        r = g.iloc[0].copy()
        r["N.º combinações/tramo"] = len(grp)
        r["Secção [cm]"] = f"{safe_float(r.get('b_cm', r.get('hy',0)),0):.0f}x{safe_float(r.get('h_cm', r.get('hz',0)),0):.0f}"
        r["Tramo"] = r.get("Piso", "") if str(r.get("Piso", "")).strip() else f"Tramo {len(rows)+1:02d}"
        r["Solução"] = _rc15_solution_value(r)
        r["Estado"] = _rc15_status_value(r)
        r["Solução local"] = _rc15_solution_value(r)
        r["As local [mm²]"] = _rc15_as_value(r)
        r["Solução adoptada"] = r["Solução local"]
        r["Critério de uniformização"] = "Solução local mantida."
        r["Rebar policy note"] = "RC15 automatic catalogue: corner/perimeter bars Ø10–Ø20; face-distribution bars Ø10–Ø16."
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # Full arrangement rationalisation by same column line + same section.
    for _, idxs in out.groupby(["Prumada", "_section_signature"], dropna=False, sort=False).groups.items():
        idxs = list(idxs)
        if len(idxs) <= 1:
            continue
        grp = out.loc[idxs]
        max_idx = grp["As local [mm²]"].astype(float).idxmax()
        max_as = float(out.at[max_idx, "As local [mm²]"] or 0.0)
        max_sol = str(out.at[max_idx, "Solução local"] or "")
        if max_as <= 0 or not max_sol:
            continue
        for idx in idxs:
            local_as = float(out.at[idx, "As local [mm²]"] or 0.0)
            ratio = max_as / max(local_as, 1e-9)
            if ratio <= 1.35:
                out.at[idx, "Solução adoptada"] = max_sol
                out.at[idx, "Critério de uniformização"] = "Solução completa uniformizada com o tramo governante da mesma prumada/secção."
                for c in ["Solução", "solucao", "solucao_completa"]:
                    if c in out.columns:
                        out.at[idx, c] = max_sol

    # Corner/perimeter bar rationalisation across the column line. It is applied
    # only when it does not create excessive over-reinforcement in weaker tramos.
    for pr, idxs in out.groupby("Prumada", dropna=False, sort=False).groups.items():
        idxs = list(idxs)
        if len(idxs) <= 1:
            continue
        grp = out.loc[idxs]
        try:
            is_circ = grp.get("section_shape", pd.Series("", index=grp.index)).astype(str).str.lower().str.contains("circ", na=False)
        except Exception:
            is_circ = pd.Series(False, index=grp.index)
        # Rectangular corner bars.
        rect_idxs = [idx for idx in idxs if not bool(is_circ.get(idx, False))]
        if rect_idxs:
            pc_vals = []
            for idx in rect_idxs:
                pc = safe_float(out.at[idx, "phi_corner_mm"] if "phi_corner_mm" in out.columns else out.at[idx, "phi_long_mm"] if "phi_long_mm" in out.columns else 0.0, 0.0)
                if pc > 0:
                    pc_vals.append(min(_RC15_MAX_AUTO_PHI, pc))
            governing_pc = max(pc_vals) if pc_vals else 0.0
            if governing_pc > 0:
                for idx in rect_idxs:
                    local_as = float(out.at[idx, "As local [mm²]"] or 0.0)
                    adopted_as = _rc15_as_with_corner(out.loc[idx], governing_pc)
                    ratio = adopted_as / max(local_as, 1e-9)
                    if ratio <= 1.75 and str(out.at[idx, "Solução adoptada"] or "") == str(out.at[idx, "Solução local"] or ""):
                        sol = _rc15_solution_with_corner(out.loc[idx], governing_pc)
                        out.at[idx, "Solução adoptada"] = sol
                        out.at[idx, "Critério de uniformização"] = "Varões de canto uniformizados na prumada; distribuição de face local mantida."
                        for c in ["Solução", "solucao", "solucao_completa"]:
                            if c in out.columns:
                                out.at[idx, c] = sol
        # Circular perimeter bars.
        circ_idxs = [idx for idx in idxs if bool(is_circ.get(idx, False))]
        if circ_idxs:
            phi_vals = []
            for idx in circ_idxs:
                ph = safe_float(out.at[idx, "phi_long_mm"] if "phi_long_mm" in out.columns else 0.0, 0.0)
                if ph > 0:
                    phi_vals.append(min(_RC15_MAX_AUTO_PHI, ph))
            governing_phi = max(phi_vals) if phi_vals else 0.0
            if governing_phi > 0:
                for idx in circ_idxs:
                    local_as = float(out.at[idx, "As local [mm²]"] or 0.0)
                    n_total = int(safe_float(out.at[idx, "n_total"] if "n_total" in out.columns else 0, 0))
                    adopted_as = n_total * bar_area_mm2(governing_phi) if n_total > 0 else local_as
                    ratio = adopted_as / max(local_as, 1e-9)
                    if ratio <= 1.75 and str(out.at[idx, "Solução adoptada"] or "") == str(out.at[idx, "Solução local"] or ""):
                        sol = _rc15_solution_with_corner(out.loc[idx], governing_phi)
                        out.at[idx, "Solução adoptada"] = sol
                        out.at[idx, "Critério de uniformização"] = "Diâmetro perimetral uniformizado na mesma prumada/secção circular."
                        for c in ["Solução", "solucao", "solucao_completa"]:
                            if c in out.columns:
                                out.at[idx, c] = sol

    def _sort_tuple(v):
        if isinstance(v, tuple):
            return v
        return (0, 0.0, str(v))
    out["_sort_prumada"] = out["Prumada"].astype(str)
    out["_sort_story"] = out["_story_sort_tuple"].map(_sort_tuple)
    try:
        out = out.sort_values(["_sort_prumada", "_sort_story", "member", "_section_signature"], kind="mergesort")
    except Exception:
        out = out.sort_values(["Prumada", "Piso", "member"], kind="mergesort")
    out["Ordem na prumada"] = out.groupby("Prumada").cumcount() + 1
    return out.drop(columns=[c for c in ["_sort_prumada", "_sort_story", "_gov_score_rc15", "_section_signature", "_story_sort_tuple"] if c in out.columns], errors="ignore")

ColumnsEC2App.build_summary_by_member = _rc15_build_summary


# ---------------------------------------------------------------------------
# EN-UK wording for new RC15 messages
# ---------------------------------------------------------------------------
try:
    _RC13_EN_TERMS.update({
        "Não foi encontrada solução automática com Ø≤20 nos cantos/perímetro, Ø≤16 nas faces e As≤As,max. Recomenda-se aumentar a secção, rever esforços/comprimentos efectivos ou activar uma solução especial fora do catálogo automático.": "No automatic arrangement was found with Ø≤20 corner/perimeter bars, Ø≤16 face-distribution bars and As≤As,max. Increase the section, review the design actions/effective lengths, or enable a special reinforcement arrangement outside the automatic catalogue.",
        "Aumentar secção, rever esforços/comprimentos efectivos ou activar catálogo especial de armaduras.": "Increase the section, review the design actions/effective lengths, or enable a special reinforcement catalogue.",
        "RC15 policy: face-distribution bars should not exceed Ø16 in the automatic catalogue": "RC15 policy: face-distribution bars are limited to Ø16 in the automatic catalogue",
        "RC15 policy: Ø10 main/corner bars retained only for lightly loaded columns": "RC15 policy: Ø10 main/corner bars should be retained only for lightly loaded columns",
        "RC15 automatic catalogue: corner/perimeter bars Ø10–Ø20; face-distribution bars Ø10–Ø16.": "RC15 automatic catalogue: corner/perimeter bars Ø10–Ø20; face-distribution bars Ø10–Ø16.",
        "Solução completa uniformizada com o tramo governante da mesma prumada/secção.": "Full reinforcement arrangement rationalised to match the governing segment of the same column line/section.",
        "Varões de canto uniformizados na prumada; distribuição de face local mantida.": "Corner bars rationalised along the column line; local face-bar distribution retained.",
        "Diâmetro perimetral uniformizado na mesma prumada/secção circular.": "Perimeter bar diameter rationalised within the same circular column line/section.",
        "Solução local mantida.": "Local arrangement retained.",
        "cantos/perímetro": "corner/perimeter bars",
        "faces": "faces",
    })
except Exception:
    pass
