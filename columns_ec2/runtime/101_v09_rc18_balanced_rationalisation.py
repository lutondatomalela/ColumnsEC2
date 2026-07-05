# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC18 — balanced vertical rationalisation.

This patch replaces the aggressive RC17 full-arrangement propagation with a
more practical design-office rule:

- local design is still performed for every physical column segment;
- the schedule is consolidated as one row per Column line + Storey + Member +
  Section;
- the adopted reinforcement is expressed as a base column-line cage plus local
  additional bars where required;
- vertical continuity is primarily applied to corner/perimeter bars, not to all
  face-distribution bars;
- a full upper-storey arrangement is not propagated to weaker lower storeys when
  it would create disproportionate over-reinforcement;
- Ø10 is restricted as a principal/corner/perimeter bar. Ø12 is the preferred
  minimum for ordinary rectangular corners and circular perimeters, except for
  genuinely small and lightly loaded columns.
"""

APP_VERSION = "v0.9 RC18 Modular"

_RC18_FULL_PROPAGATION_RATIO = 1.35
_RC18_CORNER_PROPAGATION_RATIO = 1.60
_RC18_MAX_ACCEPTABLE_EXCESS_RATIO = 1.75
_RC18_LIGHT_ETA_LIMIT = 0.35
_RC18_LIGHT_N_RATIO_LIMIT = 0.25


def _rc18_num(x, default=0.0):
    try:
        v = safe_float(x, default)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _rc18_text(x, default=""):
    try:
        s = str(x if x is not None else "").strip()
        return s if s else default
    except Exception:
        return default


def _rc18_is_circular_row(row):
    try:
        shape = str(row.get("section_shape", "") or "").lower()
        if "circ" in shape:
            return True
        txt = " ".join(str(row.get(c, "") or "") for c in ["section_label", "Secção [cm]", "Section [cm]", "Section", "layout_type"]).lower()
        return ("d=" in txt) or ("circular" in txt)
    except Exception:
        return False


def _rc18_eta(row):
    for c in ["η_NMyMz", "eta_NMyMz", "utilizacao", "utilisation", "utilization"]:
        try:
            if c in row.index:
                v = _rc18_num(row.get(c), float("nan"))
                if math.isfinite(v):
                    return abs(v)
        except Exception:
            pass
    return 999.0


def _rc18_n_ratio(row):
    for c in ["biaxial_n_ratio", "n_ratio", "Nratio", "n_red", "ν"]:
        try:
            if c in row.index:
                v = _rc18_num(row.get(c), float("nan"))
                if math.isfinite(v):
                    return abs(v)
        except Exception:
            pass
    try:
        n = abs(_rc18_num(row.get("n_ed_kN"), 0.0))
        b = _rc18_num(row.get("b_cm", row.get("hy", 0.0)), 0.0) * 10.0
        h = _rc18_num(row.get("h_cm", row.get("hz", 0.0)), 0.0) * 10.0
        fcd = max(_rc18_num(row.get("fcd_MPa"), 0.0), 0.0)
        if fcd <= 0.0:
            mat = str(row.get("material", DEFAULT_CONCRETE_CLASS) or DEFAULT_CONCRETE_CLASS)
            fck = parse_concrete_strength(mat)
            fcd = concrete_props(fck).get("fcd", 0.0)
        ac = b * h
        if ac > 0 and fcd > 0:
            return n * 1e3 / (ac * fcd)
    except Exception:
        pass
    return 999.0


def _rc18_light_column(row):
    return _rc18_eta(row) < _RC18_LIGHT_ETA_LIMIT and _rc18_n_ratio(row) < _RC18_LIGHT_N_RATIO_LIMIT


def _rc18_phi_corner(row):
    for c in ["phi_corner_mm", "phi_long_mm"]:
        try:
            if c in row.index:
                v = _rc18_num(row.get(c), 0.0)
                if v > 0:
                    return v
        except Exception:
            pass
    return 0.0


def _rc18_phi_face(row):
    for c in ["phi_face_mm", "phi_long_mm"]:
        try:
            if c in row.index:
                v = _rc18_num(row.get(c), 0.0)
                if v > 0:
                    return min(v, 16.0)
        except Exception:
            pass
    return 0.0


def _rc18_n_total(row):
    try:
        n = int(round(_rc18_num(row.get("n_total"), 0.0)))
        if n > 0:
            return n
    except Exception:
        pass
    return 4


def _rc18_n_face(row):
    if _rc18_is_circular_row(row):
        return 0
    try:
        if "n_face_y_extra" in row.index or "n_face_z_extra" in row.index:
            return 2 * int(round(_rc18_num(row.get("n_face_y_extra"), 0.0))) + 2 * int(round(_rc18_num(row.get("n_face_z_extra"), 0.0)))
    except Exception:
        pass
    return max(0, _rc18_n_total(row) - 4)


def _rc18_local_as(row):
    for c in ["As local [mm²]", "as_prov_mm2", "As,prov [mm²]", "As prov [mm²]", "As adoptada [mm²]"]:
        try:
            if c in row.index:
                v = _rc18_num(row.get(c), float("nan"))
                if math.isfinite(v) and v > 0:
                    return v
        except Exception:
            pass
    # recompute from known bars
    if _rc18_is_circular_row(row):
        ph = _rc18_phi_corner(row) or _rc18_num(row.get("phi_long_mm"), 12.0)
        return _rc18_n_total(row) * bar_area_mm2(ph)
    pc = _rc18_phi_corner(row) or 12.0
    pf = _rc18_phi_face(row) or pc
    return 4 * bar_area_mm2(pc) + _rc18_n_face(row) * bar_area_mm2(pf)


def _rc18_practical_principal_phi(row):
    """Minimum preferred principal bar diameter for the adopted schedule."""
    ph = _rc18_phi_corner(row) or 12.0
    if ph <= 10.0 + 1e-9 and not _rc18_light_column(row):
        return 12.0
    return ph


def _rc18_adopted_as(row, principal_phi=None):
    if principal_phi is None:
        principal_phi = _rc18_practical_principal_phi(row)
    if _rc18_is_circular_row(row):
        n = max(6, _rc18_n_total(row))
        return n * bar_area_mm2(principal_phi)
    pf = _rc18_phi_face(row) or principal_phi
    pf = min(pf, 16.0)
    return 4.0 * bar_area_mm2(principal_phi) + _rc18_n_face(row) * bar_area_mm2(pf)


def _rc18_link_text(row):
    phi_st = _rc18_num(row.get("phi_st_mm"), 8.0)
    s_st = _rc18_num(row.get("s_st_mm"), 0.0)
    if s_st > 0:
        return f"estribos Ø{int(phi_st)}//{s_st:.0f} mm"
    return f"estribos Ø{int(phi_st)}"


def _rc18_link_text_en(row):
    phi_st = _rc18_num(row.get("phi_st_mm"), 8.0)
    s_st = _rc18_num(row.get("s_st_mm"), 0.0)
    if s_st > 0:
        return f"links Ø{int(phi_st)}//{s_st:.0f} mm"
    return f"links Ø{int(phi_st)}"


def _rc18_base_and_additional(row, principal_phi=None):
    if principal_phi is None:
        principal_phi = _rc18_practical_principal_phi(row)
    if _rc18_is_circular_row(row):
        n = max(6, _rc18_n_total(row))
        base_pt = f"{n}Ø{int(principal_phi)} no perímetro"
        base_en = f"{n}Ø{int(principal_phi)} perimeter bars"
        add_pt = "-"
        add_en = "-"
        sol_pt = f"{base_pt}; {_rc18_link_text(row)}"
        sol_en = f"{base_en}; {_rc18_link_text_en(row)}"
        return base_pt, add_pt, sol_pt, base_en, add_en, sol_en
    n_face = _rc18_n_face(row)
    pf = _rc18_phi_face(row) or principal_phi
    pf = min(pf, 16.0)
    base_pt = f"4Ø{int(principal_phi)} nos cantos"
    base_en = f"4Ø{int(principal_phi)} corner bars"
    if n_face > 0:
        add_pt = f"{n_face}Ø{int(pf)} distribuídos nas faces"
        add_en = f"{n_face}Ø{int(pf)} distributed face bars"
        sol_pt = f"{base_pt} + {add_pt}; {_rc18_link_text(row)}"
        sol_en = f"{base_en} + {add_en}; {_rc18_link_text_en(row)}"
    else:
        add_pt = "-"
        add_en = "-"
        sol_pt = f"{base_pt}; {_rc18_link_text(row)}"
        sol_en = f"{base_en}; {_rc18_link_text_en(row)}"
    return base_pt, add_pt, sol_pt, base_en, add_en, sol_en


def _rc18_section_signature(row):
    try:
        if "_rc17_section_signature" in globals():
            return _rc17_section_signature(row)
    except Exception:
        pass
    try:
        mat = str(row.get("material", "") or "").strip()
        if _rc18_is_circular_row(row):
            d = _rc16_diameter_mm(row) if "_rc16_diameter_mm" in globals() else max(_rc18_num(row.get("b_cm")), _rc18_num(row.get("h_cm"))) * 10.0
            return f"circular|D={d:.1f}|{mat}"
        return f"rectangular|{_rc18_num(row.get('b_cm')):.3f}x{_rc18_num(row.get('h_cm')):.3f}|{mat}"
    except Exception:
        return ""


def _rc18_story_sort_tuple(row):
    try:
        if "_rc17_story_sort_tuple" in globals():
            return _rc17_story_sort_tuple(row)
    except Exception:
        pass
    txt = str(row.get("Piso", row.get("story", row.get("Storey", ""))) or "")
    m = re.search(r"-?\d+(?:[\.,]\d+)?", txt)
    if m:
        return (0, float(m.group(0).replace(",", ".")), txt)
    return (0, 0.0, txt)


def _rc18_sort_key(value):
    if isinstance(value, tuple):
        if len(value) >= 2:
            return (value[0], value[1], str(value[-1]))
    return (0, 0.0, str(value))


def _rc18_governing_score_df(work):
    try:
        if "_rc15_governing_score_df" in globals():
            return _rc15_governing_score_df(work)
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


def _rc18_solution_value(row):
    for c in ["solucao_completa", "Solução", "solucao", "Solução local", "Solução adoptada", "layout_description"]:
        try:
            val = str(row.get(c, "") or "").strip()
            if val:
                return val
        except Exception:
            pass
    return ""


def _rc18_status_value(row):
    for c in ["estado_global", "status", "Estado", "Status"]:
        try:
            val = str(row.get(c, "") or "").strip()
            if val:
                return val
        except Exception:
            pass
    return ""


def _rc18_initial_schedule(results):
    """Build one row per physical segment before RC18 rationalisation.

    RC15/RC17 summary builders could still leave more than one row for the same
    Column line + Storey + Member + Section when several combinations were
    retained. RC18 rebuilds the physical schedule directly from the result set
    and selects one governing combination per segment.
    """
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
    if "member" not in work.columns:
        work["member"] = ""
    try:
        work["_rc18_section_signature"] = work.apply(_rc18_section_signature, axis=1)
    except Exception:
        work["_rc18_section_signature"] = ""
    work["_rc18_gov_score"] = _rc18_governing_score_df(work)

    rows = []
    for _, grp in work.groupby(["Prumada", "Piso", "member", "_rc18_section_signature"], dropna=False, sort=False):
        g = grp.sort_values("_rc18_gov_score", ascending=False)
        r = g.iloc[0].copy()
        r["N.º combinações/tramo"] = len(grp)
        try:
            if _rc18_is_circular_row(r):
                d = _rc16_diameter_mm(r) if "_rc16_diameter_mm" in globals() else max(_rc18_num(r.get("b_cm")), _rc18_num(r.get("h_cm"))) * 10.0
                r["Secção [cm]"] = f"D={d/10.0:.0f} cm"
                r["Section [cm]"] = f"D={d/10.0:.0f} cm"
            else:
                r["Secção [cm]"] = f"{_rc18_num(r.get('b_cm', r.get('hy',0)),0):.0f}x{_rc18_num(r.get('h_cm', r.get('hz',0)),0):.0f} cm"
                r["Section [cm]"] = r["Secção [cm]"]
        except Exception:
            pass
        r["Tramo"] = r.get("Piso", "") if str(r.get("Piso", "")).strip() else f"Tramo {len(rows)+1:02d}"
        r["Solução"] = _rc18_solution_value(r)
        r["Estado"] = _rc18_status_value(r)
        r["Solução local"] = _rc18_solution_value(r)
        r["As local [mm²]"] = _rc18_local_as(r)
        r["Solução adoptada"] = r["Solução local"]
        r["As adoptada [mm²]"] = r["As local [mm²]"]
        r["Critério de uniformização"] = "Solução local mantida; sem propagação integral da armadura de pisos superiores."
        r["Rationalisation criterion"] = "Local arrangement retained; full upper-storey reinforcement was not propagated."
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    try:
        if "_rc16_apply_section_labels_df" in globals():
            out = _rc16_apply_section_labels_df(out)
    except Exception:
        pass
    return out.copy()

def _rc18_prepare_schedule(out):
    if out is None or getattr(out, "empty", True):
        return pd.DataFrame()
    out = out.copy()
    try:
        if "Prumada" not in out.columns:
            out["Prumada"] = out.apply(_rc12_prumada, axis=1) if "_rc12_prumada" in globals() else out.get("name", out.get("member", ""))
    except Exception:
        out["Prumada"] = out.get("name", out.get("member", ""))
    try:
        if "Piso" not in out.columns:
            out["Piso"] = out.apply(_rc12_storey, axis=1) if "_rc12_storey" in globals() else out.get("story", "")
    except Exception:
        out["Piso"] = out.get("story", "")
    if "member" not in out.columns:
        out["member"] = ""
    if "Solução local" not in out.columns:
        out["Solução local"] = out.apply(lambda r: _rc17_solution(r) if "_rc17_solution" in globals() else _rc18_text(r.get("solucao", "")), axis=1)
    if "As local [mm²]" not in out.columns:
        out["As local [mm²]"] = out.apply(_rc18_local_as, axis=1)
    else:
        out["As local [mm²]"] = out.apply(lambda r: _rc18_local_as(r), axis=1)
    out["Solução adoptada"] = out.get("Solução adoptada", out["Solução local"])
    out["As adoptada [mm²]"] = out.get("As adoptada [mm²]", out["As local [mm²]"])
    out["As adopted [mm²]"] = out["As adoptada [mm²]"]
    out["Armadura base da prumada"] = ""
    out["Local additional reinforcement"] = ""
    out["Reforço local"] = ""
    out["Base column-line cage"] = ""
    out["Excesso de aço [%]"] = 0.0
    out["Over-reinforcement [%]"] = 0.0
    out["Critério de uniformização"] = "Solução local mantida; sem propagação integral da armadura de pisos superiores."
    out["Rationalisation criterion"] = "Local arrangement retained; full upper-storey reinforcement was not propagated."
    out["Nota de continuidade"] = out.get("Nota de continuidade", "")
    out["Continuity note"] = out.get("Continuity note", "")
    out["Vertical rationalisation"] = "Não"
    out["Vertical rationalisation applied"] = "No"
    out["_rc18_section_signature"] = out.apply(_rc18_section_signature, axis=1)
    out["_rc18_story_sort_tuple"] = out.apply(_rc18_story_sort_tuple, axis=1)
    out["_rc18_story_key"] = out["_rc18_story_sort_tuple"].map(_rc18_sort_key)
    return out


def _rc18_apply_practical_row(out, idx, principal_phi, criterion_pt, criterion_en):
    row = out.loc[idx]
    base_pt, add_pt, sol_pt, base_en, add_en, sol_en = _rc18_base_and_additional(row, principal_phi)
    as_ad = _rc18_adopted_as(row, principal_phi)
    as_local = max(_rc18_num(out.at[idx, "As local [mm²]"], as_ad), 1e-9)
    excess = max(0.0, (as_ad / as_local - 1.0) * 100.0)

    out.at[idx, "Armadura base da prumada"] = base_pt
    out.at[idx, "Base column-line cage"] = base_en
    out.at[idx, "Reforço local"] = add_pt
    out.at[idx, "Local additional reinforcement"] = add_en
    out.at[idx, "Solução adoptada"] = sol_pt
    out.at[idx, "Adopted arrangement"] = sol_en
    out.at[idx, "As adoptada [mm²]"] = as_ad
    out.at[idx, "As adopted [mm²]"] = as_ad
    out.at[idx, "Excesso de aço [%]"] = excess
    out.at[idx, "Over-reinforcement [%]"] = excess
    out.at[idx, "Critério de uniformização"] = criterion_pt
    out.at[idx, "Rationalisation criterion"] = criterion_en
    out.at[idx, "Vertical rationalisation"] = "Sim" if excess > 1e-6 else "Não"
    out.at[idx, "Vertical rationalisation applied"] = "Yes" if excess > 1e-6 else "No"

    if "phi_corner_mm" in out.columns:
        out.at[idx, "phi_corner_mm"] = principal_phi
    if "phi_long_mm" in out.columns:
        out.at[idx, "phi_long_mm"] = max(principal_phi, _rc18_phi_face(row) or principal_phi)
    if "phi_face_mm" in out.columns and not _rc18_is_circular_row(row):
        out.at[idx, "phi_face_mm"] = min(_rc18_phi_face(row) or principal_phi, 16.0)
    if "as_prov_mm2" in out.columns:
        out.at[idx, "as_prov_mm2"] = as_ad
    for c in ["Solução", "solucao", "solucao_completa", "layout_description"]:
        if c in out.columns:
            out.at[idx, c] = sol_pt


def _rc18_apply_balanced_rationalisation(schedule):
    out = _rc18_prepare_schedule(schedule)
    if out.empty:
        return out

    # Start with a practical local adoption: Ø10 principal bars are upgraded to
    # Ø12 unless the segment is genuinely light.
    for idx in list(out.index):
        ph = _rc18_practical_principal_phi(out.loc[idx])
        if ph > _rc18_phi_corner(out.loc[idx]) + 1e-9:
            crit_pt = "Armadura principal aumentada para o mínimo prático Ø12; Ø10 mantido apenas em pilares pequenos e pouco solicitados."
            crit_en = "Principal reinforcement increased to the practical Ø12 minimum; Ø10 is retained only for small and lightly loaded columns."
        else:
            crit_pt = "Solução local mantida; sem propagação integral da armadura de pisos superiores."
            crit_en = "Local arrangement retained; full upper-storey reinforcement was not propagated."
        _rc18_apply_practical_row(out, idx, ph, crit_pt, crit_en)

    # Apply vertical continuity primarily to corner/perimeter bars, not to all
    # face bars. The governing principal diameter is proposed downwards only
    # when it does not create excessive over-reinforcement.
    for _, idxs_raw in out.groupby(["Prumada", "_rc18_section_signature"], dropna=False, sort=False).groups.items():
        idxs = sorted(list(idxs_raw), key=lambda idx: _rc18_sort_key(out.at[idx, "_rc18_story_sort_tuple"]))
        if len(idxs) <= 1:
            continue
        governing_phi = 0.0
        # Process upper -> lower and remember the heaviest verified principal
        # diameter required above.
        for idx in reversed(idxs):
            current_phi = _rc18_phi_corner(out.loc[idx])
            status_txt = str(out.loc[idx].get("estado_global", out.loc[idx].get("status", "")) or "").lower()
            is_failed = any(k in status_txt for k in ["falha", "failure", "não conforme", "not compliant"])
            if not is_failed and current_phi > governing_phi:
                governing_phi = current_phi
            if governing_phi > current_phi + 1e-9:
                proposed_as = _rc18_adopted_as(out.loc[idx], governing_phi)
                local_as = max(_rc18_num(out.at[idx, "As local [mm²]"], proposed_as), 1e-9)
                ratio = proposed_as / local_as
                if ratio <= _RC18_CORNER_PROPAGATION_RATIO:
                    crit_pt = "Varões principais/cantos uniformizados por continuidade vertical; reforços de face mantidos apenas onde necessários."
                    crit_en = "Principal/corner bars rationalised for vertical continuity; face reinforcement remains local where required."
                    _rc18_apply_practical_row(out, idx, governing_phi, crit_pt, crit_en)
                else:
                    note_pt = "Não foi propagada a armadura principal do tramo superior porque o aumento de As seria desproporcionado. Confirmar continuidade das emendas/desenho."
                    note_en = "The upper-storey principal reinforcement was not propagated because the As increase would be disproportionate. Check lap/splice continuity and detailing."
                    old_pt = _rc18_text(out.at[idx, "Nota de continuidade"])
                    old_en = _rc18_text(out.at[idx, "Continuity note"])
                    out.at[idx, "Nota de continuidade"] = (old_pt + "; " + note_pt).strip("; ") if old_pt else note_pt
                    out.at[idx, "Continuity note"] = (old_en + "; " + note_en).strip("; ") if old_en else note_en

    # Explicit section-change notes in the same column line.
    for pr, idxs_raw in out.groupby("Prumada", dropna=False, sort=False).groups.items():
        idxs = sorted(list(idxs_raw), key=lambda idx: _rc18_sort_key(out.at[idx, "_rc18_story_sort_tuple"]))
        prev_sig = None
        for idx in idxs:
            sig = out.at[idx, "_rc18_section_signature"]
            if prev_sig is not None and sig != prev_sig:
                note_pt = "Mudança de secção na prumada. Confirmar continuidade, emendas e compatibilização dos varões."
                note_en = "Section change within the column line. Check bar continuity, lap/splice detailing and reinforcement compatibility."
                old_pt = _rc18_text(out.at[idx, "Nota de continuidade"])
                old_en = _rc18_text(out.at[idx, "Continuity note"])
                out.at[idx, "Nota de continuidade"] = (old_pt + "; " + note_pt).strip("; ") if old_pt else note_pt
                out.at[idx, "Continuity note"] = (old_en + "; " + note_en).strip("; ") if old_en else note_en
            prev_sig = sig

    try:
        if "_rc16_apply_section_labels_df" in globals():
            out = _rc16_apply_section_labels_df(out)
    except Exception:
        pass
    try:
        out["_rc18_prumada_sort"] = out["Prumada"].astype(str).map(_v682_natural_key) if "_v682_natural_key" in globals() else out["Prumada"].astype(str)
        out = out.sort_values(["_rc18_prumada_sort", "_rc18_story_key", "member"], kind="mergesort").reset_index(drop=True)
    except Exception:
        try:
            out = out.sort_values(["Prumada", "_rc18_story_key", "member"], kind="mergesort").reset_index(drop=True)
        except Exception:
            pass
    try:
        out["Ordem na prumada"] = out.groupby("Prumada").cumcount() + 1
    except Exception:
        pass
    drop_cols = [c for c in ["_rc18_section_signature", "_rc18_story_sort_tuple", "_rc18_story_key", "_rc18_prumada_sort"] if c in out.columns]
    return out.drop(columns=drop_cols, errors="ignore")


def _rc18_build_tramo_schedule(results: pd.DataFrame) -> pd.DataFrame:
    return _rc18_apply_balanced_rationalisation(_rc18_initial_schedule(results))


def _rc18_build_summary_by_member(self, results: pd.DataFrame) -> pd.DataFrame:
    return _rc18_build_tramo_schedule(results)

ColumnsEC2App.build_summary_by_member = _rc18_build_summary_by_member
_v682_build_tramo_schedule = _rc18_build_tramo_schedule
_v683_build_tramo_schedule = _rc18_build_tramo_schedule
_rc17_build_tramo_schedule = _rc18_build_tramo_schedule


_rc18_prev_write_excel = ColumnsEC2App._write_excel

def _rc18_write_excel(self, path: str):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc18_build_tramo_schedule(self.df_results)
            if hasattr(self, "tree_summary"):
                try:
                    self.show_df(self.tree_summary, self.df_summary)
                except Exception:
                    pass
    except Exception:
        pass
    return _rc18_prev_write_excel(self, path)

ColumnsEC2App._write_excel = _rc18_write_excel


_rc18_prev_export_dxf = ColumnsEC2App.export_dxf

def _rc18_export_dxf(self):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc18_build_tramo_schedule(self.df_results)
    except Exception:
        pass
    return _rc18_prev_export_dxf(self)

ColumnsEC2App.export_dxf = _rc18_export_dxf


try:
    _RC13_EN_TERMS.update({
        "Armadura base da prumada": "Base column-line cage",
        "Reforço local": "Local additional reinforcement",
        "Excesso de aço [%]": "Over-reinforcement [%]",
        "Solução local mantida; sem propagação integral da armadura de pisos superiores.": "Local arrangement retained; full upper-storey reinforcement was not propagated.",
        "Armadura principal aumentada para o mínimo prático Ø12; Ø10 mantido apenas em pilares pequenos e pouco solicitados.": "Principal reinforcement increased to the practical Ø12 minimum; Ø10 is retained only for small and lightly loaded columns.",
        "Varões principais/cantos uniformizados por continuidade vertical; reforços de face mantidos apenas onde necessários.": "Principal/corner bars rationalised for vertical continuity; face reinforcement remains local where required.",
        "Não foi propagada a armadura principal do tramo superior porque o aumento de As seria desproporcionado. Confirmar continuidade das emendas/desenho.": "The upper-storey principal reinforcement was not propagated because the As increase would be disproportionate. Check lap/splice continuity and detailing.",
        "Mudança de secção na prumada. Confirmar continuidade, emendas e compatibilização dos varões.": "Section change within the column line. Check bar continuity, lap/splice detailing and reinforcement compatibility.",
    })
except Exception:
    pass
