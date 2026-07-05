# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC19 — constructability-driven reinforcement optimisation.

RC18 solved the vertical rationalisation problem, but some automatic solutions
still used too many small face bars. RC19 adds a design-office constructability
filter and clearer detailing language:

- rectangular automatic layouts are limited to practical face-bar counts;
- face bars remain Ø10/Ø12/Ø16, but no longer grow into long sequences such as
  10Ø/12Ø distributed along the faces;
- candidate scoring penalises congestion, high reinforcement ratios and
  excessive face bars;
- adopted arrangements are described explicitly as bars per face, not as a
  generic "distributed along the faces" statement;
- congested but numerically valid solutions are flagged as exceptional and the
  user is advised to increase the section or review the forces rather than to
  keep adding bars.
"""

APP_VERSION = "v0.9 RC19 Modular"

_RC19_MAX_FACE_EXTRA_TOTAL = 8          # total additional bars on all faces
_RC19_MAX_FACE_EXTRA_PER_FACE = 2       # per individual side in automatic catalogue
_RC19_NORMAL_FACE_EXTRA_TOTAL = 4
_RC19_WARNING_FACE_EXTRA_TOTAL = 6
_RC19_RHO_NORMAL_LIMIT = 2.0            # %
_RC19_RHO_WARNING_LIMIT = 3.0           # %
_RC19_FACE_DIAMS = [10.0, 12.0, 16.0]
_RC19_CORNER_DIAMS = [10.0, 12.0, 16.0, 20.0]


def _rc19_num(x, default=0.0):
    try:
        v = safe_float(x, default)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _rc19_is_circular_layout(layout):
    try:
        if "_rc15_is_circular_layout" in globals():
            return _rc15_is_circular_layout(layout)
    except Exception:
        pass
    try:
        return isinstance(layout, CircularLayout) or str(getattr(layout, "layout_type", "")).lower().startswith("circ")
    except Exception:
        return False


def _rc19_phi_corner_layout(layout):
    try:
        if "_rc15_phi_corner" in globals():
            return float(_rc15_phi_corner(layout))
    except Exception:
        pass
    return float(getattr(layout, "phi_corner_mm", getattr(layout, "phi_long_mm", 0.0)) or 0.0)


def _rc19_phi_face_layout(layout):
    try:
        if "_rc15_phi_face" in globals():
            return float(_rc15_phi_face(layout))
    except Exception:
        pass
    return float(getattr(layout, "phi_face_mm", getattr(layout, "phi_long_mm", 0.0)) or 0.0)


def _rc19_face_extras_layout(layout):
    if _rc19_is_circular_layout(layout):
        return 0, 0, 0
    try:
        ey = int(round(float(getattr(layout, "n_face_y_extra", 0) or 0)))
        ez = int(round(float(getattr(layout, "n_face_z_extra", 0) or 0)))
        return ey, ez, 2 * ey + 2 * ez
    except Exception:
        try:
            n_total = int(round(float(getattr(layout, "n_total", 4) or 4)))
            return 0, 0, max(0, n_total - 4)
        except Exception:
            return 0, 0, 0


def _rc19_layout_allowed(layout):
    """Automatic-catalogue hard filter for normal building-column detailing."""
    if _rc19_is_circular_layout(layout):
        # Circular perimeter layouts are still allowed, but Ø10 perimeter bars
        # are penalised later unless the column is genuinely light.
        try:
            return float(getattr(layout, "phi_long_mm", 0.0) or 0.0) <= 20.0 + 1e-9
        except Exception:
            return True

    pc = _rc19_phi_corner_layout(layout)
    pf = _rc19_phi_face_layout(layout)
    ey, ez, n_face = _rc19_face_extras_layout(layout)
    try:
        n_total = int(round(float(getattr(layout, "n_total", 0) or 0)))
    except Exception:
        n_total = 0

    if pc not in _RC19_CORNER_DIAMS:
        return False
    if n_face > 0 and pf not in _RC19_FACE_DIAMS:
        return False
    if pc > 20.0 + 1e-9 or pf > 16.0 + 1e-9:
        return False
    if n_face > _RC19_MAX_FACE_EXTRA_TOTAL:
        return False
    if ey > _RC19_MAX_FACE_EXTRA_PER_FACE or ez > _RC19_MAX_FACE_EXTRA_PER_FACE:
        return False
    if n_total > 4 + _RC19_MAX_FACE_EXTRA_TOTAL:
        return False
    return True


def _rc19_section_area_layout(layout, b_mm, h_mm):
    try:
        if _rc19_is_circular_layout(layout):
            d = min(float(b_mm), float(h_mm))
            return math.pi * d * d / 4.0
        return max(float(b_mm) * float(h_mm), 1.0)
    except Exception:
        return 1.0


def _rc19_layout_score(layout, as_target: float, b_mm: float, h_mm: float):
    """Rank candidate layouts by resistance demand and constructability.

    The score still allows the solver to find a valid layout, but it strongly
    favours simple arrangements with a moderate number of face bars. Heavy
    congestion is therefore reported as a section-design issue instead of being
    hidden behind long strings of small bars.
    """
    asprov = float(getattr(layout, "as_prov_mm2", 0.0) or 0.0)
    as_t = float(as_target or 0.0)
    ac = max(_rc19_section_area_layout(layout, b_mm, h_mm), 1.0)
    rho = 100.0 * asprov / ac
    deficit = max(0.0, as_t - asprov)
    excess = max(0.0, asprov - as_t)
    excess_ratio = excess / max(as_t, 1.0)
    try:
        n = int(round(float(getattr(layout, "n_total", 999) or 999)))
    except Exception:
        n = 999

    hard = 0.0 if _rc19_layout_allowed(layout) else 2_000_000.0

    if _rc19_is_circular_layout(layout):
        pc = float(getattr(layout, "phi_long_mm", 0.0) or 0.0)
        small_light = (min(float(b_mm), float(h_mm)) <= 300.0 and as_t <= max(450.0, 0.0040 * ac))
        p10 = 0.0 if (pc <= 10.0 + 1e-9 and small_light) else (3500.0 if pc <= 10.0 + 1e-9 else 0.0)
        p_pref = 0.0 if 12.0 - 1e-9 <= pc <= 16.0 + 1e-9 else 220.0
        p20 = 650.0 if pc >= 20.0 - 1e-9 and as_t < 0.012 * ac else 120.0 if pc >= 20.0 - 1e-9 else 0.0
        p_many = max(0, n - 14) * 45.0
        p_rho = 0.0 if rho <= _RC19_RHO_NORMAL_LIMIT else (rho - _RC19_RHO_NORMAL_LIMIT) * 400.0
        return (hard, deficit, p10 + p_pref + p20 + p_many + p_rho, excess_ratio, excess / 100.0, n, asprov)

    pc = _rc19_phi_corner_layout(layout)
    pf = _rc19_phi_face_layout(layout)
    ey, ez, n_face = _rc19_face_extras_layout(layout)
    small_light = (min(float(b_mm or 0.0), float(h_mm or 0.0)) <= 300.0 and as_t <= max(450.0, 0.0035 * ac))

    p_corner10 = 0.0 if (pc <= 10.0 + 1e-9 and small_light) else (3600.0 if pc <= 10.0 + 1e-9 else 0.0)
    p_corner_pref = 0.0 if 12.0 - 1e-9 <= pc <= 16.0 + 1e-9 else 260.0
    p_corner20 = 850.0 if pc >= 20.0 - 1e-9 and as_t < 0.012 * ac else 140.0 if pc >= 20.0 - 1e-9 else 0.0
    p_mixed = abs(pc - pf) * 35.0
    p_face_many = max(0, n_face - _RC19_NORMAL_FACE_EXTRA_TOTAL) * 260.0 + max(0, n_face - _RC19_WARNING_FACE_EXTRA_TOTAL) * 700.0
    p_face_balance = abs(ey - ez) * 60.0
    p_bars = max(0, n - 12) * 220.0
    p_rho = 0.0 if rho <= _RC19_RHO_NORMAL_LIMIT else (rho - _RC19_RHO_NORMAL_LIMIT) * 650.0
    # Prefer adding a few larger, well-positioned bars over many small ones.
    p_small_face = max(0, n_face - 4) * (120.0 if pf <= 12.0 + 1e-9 else 60.0)

    return (hard, deficit, p_corner10 + p_corner_pref + p_corner20 + p_mixed + p_face_many + p_face_balance + p_bars + p_rho + p_small_face, excess_ratio, excess / 100.0, n_face, n, asprov)


# Make all existing design routines that call the historical score use the RC19
# constructability-driven ranking.
_v56_layout_score = _rc19_layout_score


_rc19_prev_build_candidate_layouts = ColumnDesigner.build_candidate_layouts

def _rc19_build_candidate_layouts(self, b_mm, h_mm, is_circular=False):
    key = ("rc19", round(float(b_mm), 1), round(float(h_mm), 1), round(float(self.cover_mm), 1), bool(is_circular))
    try:
        if key in self._layout_cache:
            return self._layout_cache[key]
    except Exception:
        pass
    base = list(_rc19_prev_build_candidate_layouts(self, b_mm, h_mm, is_circular=is_circular))
    filtered = [ly for ly in base if _rc19_layout_allowed(ly)]
    filtered.sort(key=lambda ly: _rc19_layout_score(ly, 0.0, b_mm, h_mm))
    try:
        self._layout_cache[key] = filtered
    except Exception:
        pass
    return filtered

ColumnDesigner.build_candidate_layouts = _rc19_build_candidate_layouts


# ---------------------------------------------------------------------------
# Constructability annotations
# ---------------------------------------------------------------------------

def _rc19_is_circular_row(row):
    try:
        return _rc18_is_circular_row(row) if "_rc18_is_circular_row" in globals() else str(row.get("section_shape", "")).lower().startswith("circ")
    except Exception:
        return False


def _rc19_face_extras_row(row):
    if _rc19_is_circular_row(row):
        return 0, 0, 0
    try:
        ey = int(round(_rc19_num(row.get("n_face_y_extra"), 0.0)))
        ez = int(round(_rc19_num(row.get("n_face_z_extra"), 0.0)))
        if ey > 0 or ez > 0:
            return ey, ez, 2 * ey + 2 * ez
    except Exception:
        pass
    try:
        n_total = int(round(_rc19_num(row.get("n_total"), 4.0)))
        return 0, 0, max(0, n_total - 4)
    except Exception:
        return 0, 0, 0


def _rc19_phi_corner_row(row):
    try:
        if "_rc18_phi_corner" in globals():
            return _rc18_phi_corner(row)
    except Exception:
        pass
    return _rc19_num(row.get("phi_corner_mm", row.get("phi_long_mm", 12.0)), 12.0)


def _rc19_phi_face_row(row):
    try:
        if "_rc18_phi_face" in globals():
            return _rc18_phi_face(row)
    except Exception:
        pass
    return min(16.0, _rc19_num(row.get("phi_face_mm", row.get("phi_long_mm", _rc19_phi_corner_row(row))), _rc19_phi_corner_row(row)))


def _rc19_area_row(row):
    try:
        if _rc19_is_circular_row(row):
            d = _rc16_diameter_mm(row) if "_rc16_diameter_mm" in globals() else max(_rc19_num(row.get("b_cm")), _rc19_num(row.get("h_cm"))) * 10.0
            return math.pi * d * d / 4.0
        return max(_rc19_num(row.get("b_cm"), 0.0) * 10.0 * _rc19_num(row.get("h_cm"), 0.0) * 10.0, 1.0)
    except Exception:
        return 1.0


def _rc19_as_adopted_row(row):
    for c in ["As adoptada [mm²]", "As adopted [mm²]", "as_prov_mm2", "As local [mm²]"]:
        try:
            v = _rc19_num(row.get(c), float("nan"))
            if math.isfinite(v) and v > 0:
                return v
        except Exception:
            pass
    return 0.0


def _rc19_reinforcement_ratio_pct(row):
    return 100.0 * _rc19_as_adopted_row(row) / max(_rc19_area_row(row), 1.0)


def _rc19_constructability_status(row):
    rho = _rc19_reinforcement_ratio_pct(row)
    ey, ez, n_face = _rc19_face_extras_row(row)
    eta = _rc18_eta(row) if "_rc18_eta" in globals() else _rc19_num(row.get("utilizacao", 0.0), 0.0)
    if eta > 1.0 + 1e-9:
        return "Não conforme", "Not compliant", "A secção não verifica no catálogo automático; aumentar secção, rever esforços/comprimentos efectivos ou adoptar solução especial manual.", "The section does not verify within the automatic catalogue; increase the section, review forces/effective lengths or adopt a special manual arrangement."
    if rho > _RC19_RHO_WARNING_LIMIT or n_face > _RC19_MAX_FACE_EXTRA_TOTAL:
        return "Solução excepcional", "Exceptional arrangement", "Armadura elevada/congestionada; recomenda-se aumentar a secção ou rever os esforços antes de adoptar esta solução.", "High/congested reinforcement; increasing the section or reviewing the design forces is recommended before adopting this arrangement."
    if rho > _RC19_RHO_NORMAL_LIMIT or n_face > _RC19_WARNING_FACE_EXTRA_TOTAL:
        return "Aceitável com aviso", "Acceptable with warning", "Solução resistente mas com densidade de armadura elevada; confirmar pormenorização, grampos e emendas.", "Resistant but relatively dense reinforcement; check detailing, cross-ties and lap/splice arrangement."
    if n_face > _RC19_NORMAL_FACE_EXTRA_TOTAL:
        return "Aceitável", "Acceptable", "Solução resistente com reforço local de faces; confirmar a disposição no desenho de pormenor.", "Resistant arrangement with local face reinforcement; confirm the detailed bar layout on drawings."
    return "Normal", "Normal", "Solução construtiva corrente dentro do catálogo automático.", "Standard constructible arrangement within the automatic catalogue."


def _rc19_explicit_face_parts(row, phi_face=None, lang="pt"):
    if _rc19_is_circular_row(row):
        return []
    if phi_face is None:
        phi_face = _rc19_phi_face_row(row)
    ey, ez, _n_face = _rc19_face_extras_row(row)
    b_cm = _rc19_num(row.get("b_cm", row.get("hy", 0.0)), 0.0)
    h_cm = _rc19_num(row.get("h_cm", row.get("hz", 0.0)), 0.0)
    parts = []
    if ey > 0:
        if lang == "en":
            parts.append(f"{ey}Ø{int(phi_face)} on each {b_cm:.0f} cm face")
        else:
            parts.append(f"{ey}Ø{int(phi_face)} por face de {b_cm:.0f} cm")
    if ez > 0:
        if lang == "en":
            parts.append(f"{ez}Ø{int(phi_face)} on each {h_cm:.0f} cm face")
        else:
            parts.append(f"{ez}Ø{int(phi_face)} por face de {h_cm:.0f} cm")
    return parts


def _rc19_link_text(row, lang="pt"):
    phi_st = _rc19_num(row.get("phi_st_mm"), 8.0)
    s_st = _rc19_num(row.get("s_st_mm"), 0.0)
    if lang == "en":
        return f"links Ø{int(phi_st)}//{s_st:.0f} mm" if s_st > 0 else f"links Ø{int(phi_st)}"
    return f"estribos Ø{int(phi_st)}//{s_st:.0f} mm" if s_st > 0 else f"estribos Ø{int(phi_st)}"


def _rc19_base_and_additional(row, principal_phi=None):
    if principal_phi is None:
        principal_phi = _rc18_practical_principal_phi(row) if "_rc18_practical_principal_phi" in globals() else _rc19_phi_corner_row(row)
    if _rc19_is_circular_row(row):
        n = max(6, int(round(_rc19_num(row.get("n_total"), 6.0))))
        base_pt = f"{n}Ø{int(principal_phi)} no perímetro"
        base_en = f"{n}Ø{int(principal_phi)} perimeter bars"
        add_pt = "-"
        add_en = "-"
        sol_pt = f"{base_pt}; {_rc19_link_text(row, 'pt')}"
        sol_en = f"{base_en}; {_rc19_link_text(row, 'en')}"
        return base_pt, add_pt, sol_pt, base_en, add_en, sol_en

    pf = min(_rc19_phi_face_row(row), 16.0)
    base_pt = f"4Ø{int(principal_phi)} nos cantos"
    base_en = f"4Ø{int(principal_phi)} corner bars"
    parts_pt = _rc19_explicit_face_parts(row, pf, "pt")
    parts_en = _rc19_explicit_face_parts(row, pf, "en")
    if parts_pt:
        add_pt = " + ".join(parts_pt)
        add_en = " + ".join(parts_en)
        sol_pt = f"{base_pt} + {add_pt}; {_rc19_link_text(row, 'pt')}"
        sol_en = f"{base_en} + {add_en}; {_rc19_link_text(row, 'en')}"
    else:
        add_pt = "-"
        add_en = "-"
        sol_pt = f"{base_pt}; {_rc19_link_text(row, 'pt')}"
        sol_en = f"{base_en}; {_rc19_link_text(row, 'en')}"
    return base_pt, add_pt, sol_pt, base_en, add_en, sol_en

# RC18 calls this global name during schedule rationalisation; replacing it here
# is enough to remove the generic "distributed along the faces" text.
_rc18_base_and_additional = _rc19_base_and_additional


_rc19_prev_design_one = ColumnDesigner.design_one

def _rc19_design_one(self, row, prebuilt_candidates=None):
    if prebuilt_candidates is not None:
        try:
            prebuilt_candidates = [ly for ly in list(prebuilt_candidates) if _rc19_layout_allowed(ly)]
            b_mm = _rc19_num(row.get("hy", 0.0), 0.0) * 10.0
            h_mm = _rc19_num(row.get("hz", 0.0), 0.0) * 10.0
            prebuilt_candidates.sort(key=lambda ly: _rc19_layout_score(ly, 0.0, b_mm, h_mm))
        except Exception:
            pass
    out = _rc19_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)
    if not isinstance(out, dict):
        return out
    try:
        rho = _rc19_reinforcement_ratio_pct(pd.Series(out))
        ey, ez, n_face = _rc19_face_extras_row(pd.Series(out))
        st_pt, st_en, note_pt, note_en = _rc19_constructability_status(pd.Series(out))
        out["rho_longitudinal_%"] = rho
        out["n_face_bars_total"] = n_face
        out["constructability_status"] = st_pt
        out["constructability_status_en"] = st_en
        out["constructability_note"] = note_pt
        out["constructability_note_en"] = note_en
        if st_pt != "Normal":
            prev = str(out.get("warning_reason", "") or "").strip()
            out["warning_reason"] = (prev + "; " + note_pt).strip("; ") if prev else note_pt
        # If the automatic catalogue no longer offers the former long face-bar
        # sequences, failures need to explain that this is a deliberate design
        # decision and not a parser error.
        status_txt = str(out.get("status", "") or "").lower()
        if any(k in status_txt for k in ["falha", "failure", "não conforme", "not compliant"]):
            fr = str(out.get("failure_reason", "") or "").strip()
            add = "Não foi encontrada solução automática construtivamente prática com máximo de 8 varões adicionais nas faces, Ø≤20 nos cantos/perímetro e Ø≤16 nas faces. Recomenda-se aumentar a secção, rever esforços/comprimentos efectivos ou adoptar solução especial/manual."
            out["failure_reason"] = (fr + "; " + add).strip("; ") if fr and add not in fr else (fr or add)
    except Exception:
        pass
    return out

ColumnDesigner.design_one = _rc19_design_one


# ---------------------------------------------------------------------------
# Summary/export schedule post-processing
# ---------------------------------------------------------------------------

def _rc19_postprocess_schedule(df):
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy()
    for idx in list(out.index):
        row = out.loc[idx]
        st_pt, st_en, note_pt, note_en = _rc19_constructability_status(row)
        rho = _rc19_reinforcement_ratio_pct(row)
        ey, ez, n_face = _rc19_face_extras_row(row)
        out.at[idx, "Taxa de armadura [%]"] = rho
        out.at[idx, "Reinforcement ratio [%]"] = rho
        out.at[idx, "N.º varões adicionais nas faces"] = n_face
        out.at[idx, "Additional face bars"] = n_face
        out.at[idx, "Classificação construtiva"] = st_pt
        out.at[idx, "Constructability class"] = st_en
        out.at[idx, "Nota construtiva"] = note_pt
        out.at[idx, "Constructability note"] = note_en
        # Rebuild arrangement text using explicit per-face wording.
        ph = _rc18_practical_principal_phi(row) if "_rc18_practical_principal_phi" in globals() else _rc19_phi_corner_row(row)
        base_pt, add_pt, sol_pt, base_en, add_en, sol_en = _rc19_base_and_additional(row, ph)
        out.at[idx, "Armadura base da prumada"] = base_pt
        out.at[idx, "Base column-line cage"] = base_en
        out.at[idx, "Reforço local"] = add_pt
        out.at[idx, "Local additional reinforcement"] = add_en
        out.at[idx, "Solução adoptada"] = sol_pt
        out.at[idx, "Adopted arrangement"] = sol_en
        for c in ["Solução", "solucao", "solucao_completa", "layout_description"]:
            if c in out.columns:
                out.at[idx, c] = sol_pt
        if st_pt in ["Aceitável com aviso", "Solução excepcional", "Não conforme"]:
            old_pt = str(out.at[idx, "Nota de continuidade"] if "Nota de continuidade" in out.columns else "" or "").strip()
            old_en = str(out.at[idx, "Continuity note"] if "Continuity note" in out.columns else "" or "").strip()
            out.at[idx, "Nota de continuidade"] = (old_pt + "; " + note_pt).strip("; ") if old_pt else note_pt
            out.at[idx, "Continuity note"] = (old_en + "; " + note_en).strip("; ") if old_en else note_en
    return out


_rc19_prev_build_summary_by_member = ColumnsEC2App.build_summary_by_member
# Keep an immutable reference to the RC18 scheduler before publishing RC19 aliases.
# Without this snapshot, _rc18_build_tramo_schedule is later rebound to RC19 and
# RC19 ends up calling itself until Python raises "maximum recursion depth exceeded".
_rc19_prev_build_tramo_schedule = globals().get("_rc18_build_tramo_schedule", None)

def _rc19_build_summary_by_member(self, results: pd.DataFrame) -> pd.DataFrame:
    try:
        if callable(_rc19_prev_build_tramo_schedule):
            base = _rc19_prev_build_tramo_schedule(results)
        else:
            base = _rc19_prev_build_summary_by_member(self, results)
    except RecursionError:
        base = _rc19_prev_build_summary_by_member(self, results)
    except Exception:
        base = _rc19_prev_build_summary_by_member(self, results)
    return _rc19_postprocess_schedule(base)

ColumnsEC2App.build_summary_by_member = _rc19_build_summary_by_member


def _rc19_build_tramo_schedule(results: pd.DataFrame) -> pd.DataFrame:
    if callable(_rc19_prev_build_tramo_schedule):
        base = _rc19_prev_build_tramo_schedule(results)
    else:
        base = pd.DataFrame()
    return _rc19_postprocess_schedule(base)

_v682_build_tramo_schedule = _rc19_build_tramo_schedule
_v683_build_tramo_schedule = _rc19_build_tramo_schedule
_rc17_build_tramo_schedule = _rc19_build_tramo_schedule
_rc18_build_tramo_schedule = _rc19_build_tramo_schedule


_rc19_prev_write_excel = ColumnsEC2App._write_excel

def _rc19_write_excel(self, path: str):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc19_build_tramo_schedule(self.df_results)
            if hasattr(self, "tree_summary"):
                try:
                    self.show_df(self.tree_summary, self.df_summary)
                except Exception:
                    pass
    except Exception:
        pass
    return _rc19_prev_write_excel(self, path)

ColumnsEC2App._write_excel = _rc19_write_excel


_rc19_prev_export_dxf = ColumnsEC2App.export_dxf

def _rc19_export_dxf(self):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc19_build_tramo_schedule(self.df_results)
    except Exception:
        pass
    return _rc19_prev_export_dxf(self)

ColumnsEC2App.export_dxf = _rc19_export_dxf


try:
    _RC13_EN_TERMS.update({
        "Solução construtiva corrente dentro do catálogo automático.": "Standard constructible arrangement within the automatic catalogue.",
        "Solução resistente mas com densidade de armadura elevada; confirmar pormenorização, grampos e emendas.": "Resistant but relatively dense reinforcement; check detailing, cross-ties and lap/splice arrangement.",
        "Armadura elevada/congestionada; recomenda-se aumentar a secção ou rever os esforços antes de adoptar esta solução.": "High/congested reinforcement; increasing the section or reviewing the design forces is recommended before adopting this arrangement.",
        "A secção não verifica no catálogo automático; aumentar secção, rever esforços/comprimentos efectivos ou adoptar solução especial manual.": "The section does not verify within the automatic catalogue; increase the section, review forces/effective lengths or adopt a special manual arrangement.",
        "Classificação construtiva": "Constructability class",
        "Nota construtiva": "Constructability note",
        "N.º varões adicionais nas faces": "Additional face bars",
        "Taxa de armadura [%]": "Reinforcement ratio [%]",
        "por face de": "on each face of",
    })
except Exception:
    pass
