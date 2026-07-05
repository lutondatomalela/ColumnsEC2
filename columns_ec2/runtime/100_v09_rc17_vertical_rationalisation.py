# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC17 — vertical rationalisation of column reinforcement.

This patch introduces a practical column-schedule step after the local design:
- one physical segment remains one row in the schedule;
- within the same column line and compatible section, lower storeys are not
  allowed to adopt less longitudinal reinforcement than upper storeys;
- the governing upper-storey arrangement is propagated downwards where needed,
  while the original local arrangement remains available for audit;
- section changes are not forced, but they receive a continuity/detailing note;
- DXF export uses the rationalised schedule so the drawing matches the adopted
  reinforcement rather than isolated local checks.
"""

APP_VERSION = "v0.9 RC17 Modular"

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _rc17_num(x, default=0.0):
    try:
        v = safe_float(x, default)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _rc17_col(df, name, default=""):
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index)


def _rc17_is_failure_text(value) -> bool:
    txt = str(value or "").strip().lower()
    return any(k in txt for k in ["falha", "failure", "não conforme", "not compliant"])


def _rc17_solution(row):
    for c in ["Solução adoptada", "Solução", "solucao_completa", "solucao", "Reinforcement arrangement", "Adopted arrangement"]:
        try:
            v = str(row.get(c, "") or "").strip()
            if v:
                return v
        except Exception:
            pass
    return ""


def _rc17_as(row):
    for c in ["As adoptada [mm²]", "As adopted [mm²]", "As local [mm²]", "as_prov_mm2", "As,prov [mm²]", "As prov [mm²]"]:
        try:
            v = _rc17_num(row.get(c, float("nan")), float("nan"))
            if math.isfinite(v) and v > 0:
                return v
        except Exception:
            pass
    return 0.0


def _rc17_status(row):
    for c in ["estado_global", "status", "Estado", "Status"]:
        try:
            v = str(row.get(c, "") or "").strip()
            if v:
                return v
        except Exception:
            pass
    return ""


def _rc17_section_signature(row):
    """Geometry/material-only signature for vertical rationalisation.

    Some earlier schedule signatures included the reinforcement arrangement. For
    vertical continuity that is not appropriate, because the objective is exactly
    to compare different local arrangements in the same physical section.
    """
    try:
        mat = str(row.get("material", "") or "").strip()
        shape = str(row.get("section_shape", "") or "").lower().strip()
        if not shape:
            txt = " ".join(str(row.get(c, "") or "") for c in ["section_label", "Secção [cm]", "Section [cm]", "Section"]).lower()
            shape = "circular" if "d=" in txt or "circular" in txt else "rectangular"
        if shape.startswith("circ"):
            if "_rc16_diameter_mm" in globals():
                d = _rc16_diameter_mm(row)
            else:
                b = _rc17_num(row.get("b_cm", row.get("hy", 0.0))) * 10.0
                h = _rc17_num(row.get("h_cm", row.get("hz", 0.0))) * 10.0
                d = (b + h) / 2.0 if b > 0 and h > 0 else max(b, h)
            return f"circular|D={d:.1f}|{mat}"
        b = _rc17_num(row.get("b_cm", row.get("hy", 0.0)))
        h = _rc17_num(row.get("h_cm", row.get("hz", 0.0)))
        return f"rectangular|{b:.3f}x{h:.3f}|{mat}"
    except Exception:
        return ""


def _rc17_story_sort_tuple(row):
    try:
        if "_rc12_story_sort" in globals():
            v = _rc12_story_sort(row)
            if isinstance(v, tuple):
                return v
    except Exception:
        pass
    try:
        if "_v683_story_sort_tuple" in globals():
            v = _v683_story_sort_tuple(row)
            if isinstance(v, tuple):
                return v
    except Exception:
        pass
    txt = str(row.get("Piso", row.get("story", row.get("Storey", ""))) or "")
    m = re.search(r"-?\d+(?:[\.,]\d+)?", txt)
    if m:
        try:
            val = float(m.group(0).replace(",", "."))
            return (0, val, txt)
        except Exception:
            pass
    return (0, 0.0, txt)


def _rc17_sort_key_from_tuple(value):
    if isinstance(value, tuple):
        if len(value) >= 2:
            return (value[0], value[1], str(value[-1]))
        if len(value) == 1:
            return (value[0], 0.0, "")
    return (0, 0.0, str(value))


def _rc17_arrangement_columns(df):
    candidates = [
        "phi_long_mm", "phi_corner_mm", "phi_face_mm", "phi_st_mm", "s_st_mm", "s_st_max_mm",
        "n_total", "n_bars_y", "n_bars_z", "n_face_y_extra", "n_face_z_extra",
        "as_prov_mm2", "numero_grampos_por_nivel", "grampos_intermedios", "links_y", "links_z",
        "solucao", "solucao_completa", "Solução", "Solução adoptada", "Reinforcement arrangement",
        "section_shape", "layout_type",
    ]
    return [c for c in candidates if c in df.columns]


def _rc17_copy_adopted_arrangement(out, target_idx, source_idx, reason_pt, reason_en):
    """Copy reinforcement geometry/description from the governing row.

    Loads, utilisation and local status are intentionally not copied; the row
    remains the local governing design case, but the adopted detailing is
    rationalised for the column schedule.
    """
    try:
        source = out.loc[source_idx]
        source_sol = _rc17_solution(source)
        source_as = _rc17_as(source)
        for col in _rc17_arrangement_columns(out):
            if col in ["section_shape", "layout_type"]:
                # Shape is part of the physical segment and must not be altered
                # by copying reinforcement details.
                continue
            try:
                out.at[target_idx, col] = source.get(col)
            except Exception:
                pass
        if source_sol:
            out.at[target_idx, "Solução adoptada"] = source_sol
            out.at[target_idx, "Solução"] = source_sol
            if "solucao" in out.columns:
                out.at[target_idx, "solucao"] = source_sol
            if "solucao_completa" in out.columns:
                out.at[target_idx, "solucao_completa"] = source_sol
        if source_as > 0:
            out.at[target_idx, "As adoptada [mm²]"] = source_as
            out.at[target_idx, "As adopted [mm²]"] = source_as
            if "as_prov_mm2" in out.columns:
                out.at[target_idx, "as_prov_mm2"] = source_as
        out.at[target_idx, "Critério de uniformização"] = reason_pt
        out.at[target_idx, "Rationalisation criterion"] = reason_en
        out.at[target_idx, "Vertical rationalisation"] = "Sim"
        out.at[target_idx, "Vertical rationalisation applied"] = "Yes"
    except Exception:
        pass


def _rc17_initial_schedule(results):
    """Build the consolidated physical-segment schedule before vertical checks."""
    if results is None or getattr(results, "empty", True):
        return pd.DataFrame()
    # Prefer the RC15 physical-segment summary because it already consolidates
    # Prumada + Piso + Member + Section and applies local arrangement logic.
    try:
        if "_rc15_build_summary" in globals():
            base = _rc15_build_summary(None, results)
        else:
            base = _v683_build_tramo_schedule(results)
    except Exception:
        try:
            base = _v683_build_tramo_schedule(results)
        except Exception:
            base = results.copy()
    try:
        if "_rc16_apply_section_labels_df" in globals():
            base = _rc16_apply_section_labels_df(base)
    except Exception:
        pass
    return base.copy()


def _rc17_prepare_schedule_columns(out):
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
        out["Solução local"] = out.apply(_rc17_solution, axis=1)
    if "As local [mm²]" not in out.columns:
        out["As local [mm²]"] = out.apply(_rc17_as, axis=1)
    if "Solução adoptada" not in out.columns:
        out["Solução adoptada"] = out["Solução local"]
    if "As adoptada [mm²]" not in out.columns:
        out["As adoptada [mm²]"] = out["As local [mm²]"]
    if "As adopted [mm²]" not in out.columns:
        out["As adopted [mm²]"] = out["As adoptada [mm²]"]
    if "Critério de uniformização" not in out.columns:
        out["Critério de uniformização"] = "Solução local mantida."
    if "Rationalisation criterion" not in out.columns:
        out["Rationalisation criterion"] = "Local arrangement retained."
    if "Nota de continuidade" not in out.columns:
        out["Nota de continuidade"] = ""
    if "Continuity note" not in out.columns:
        out["Continuity note"] = ""
    if "Vertical rationalisation" not in out.columns:
        out["Vertical rationalisation"] = "Não"
    if "Vertical rationalisation applied" not in out.columns:
        out["Vertical rationalisation applied"] = "No"
    out["_rc17_section_signature"] = out.apply(_rc17_section_signature, axis=1)
    out["_rc17_story_sort_tuple"] = out.apply(_rc17_story_sort_tuple, axis=1)
    out["_rc17_story_key"] = out["_rc17_story_sort_tuple"].map(_rc17_sort_key_from_tuple)
    out["_rc17_status_text"] = out.apply(_rc17_status, axis=1)
    return out


def _rc17_apply_vertical_rationalisation(schedule):
    """Enforce practical vertical continuity within each column line.

    For each column line and compatible section, the adopted reinforcement is
    processed from top to bottom. If an upper segment requires a heavier valid
    arrangement, that arrangement is adopted downwards for the lower compatible
    segments. This prevents a lower storey from showing less reinforcement than
    an upper storey in the same column line/section.
    """
    out = _rc17_prepare_schedule_columns(schedule)
    if out.empty:
        return out

    # Same section: propagate governing upper-storey arrangement downward.
    group_cols = ["Prumada", "_rc17_section_signature"]
    for _, idxs_raw in out.groupby(group_cols, dropna=False, sort=False).groups.items():
        idxs = list(idxs_raw)
        if len(idxs) <= 1:
            continue
        # lower -> upper, then process upper -> lower
        idxs_sorted = sorted(idxs, key=lambda idx: _rc17_sort_key_from_tuple(out.at[idx, "_rc17_story_sort_tuple"]))
        governing_idx = None
        governing_as = 0.0
        for idx in reversed(idxs_sorted):
            local_as = _rc17_num(out.at[idx, "As local [mm²]"], 0.0)
            adopted_as = _rc17_num(out.at[idx, "As adoptada [mm²]"], local_as)
            current_as = max(local_as, adopted_as)
            status_txt = str(out.at[idx, "_rc17_status_text"] or "")
            valid_candidate = current_as > 0.0 and not _rc17_is_failure_text(status_txt)
            if governing_idx is not None and governing_as > current_as + 1e-6:
                src_status = str(out.at[governing_idx, "_rc17_status_text"] or "")
                reason_pt = "Solução adoptada aumentada por continuidade vertical: o tramo superior compatível governa a prumada/secção."
                reason_en = "Adopted arrangement increased for vertical continuity: the compatible upper segment governs the column line/section."
                if _rc17_is_failure_text(src_status):
                    reason_pt += " O tramo governante superior não está verificado; rever a secção/esforços."
                    reason_en += " The governing upper segment is not verified; review the section/design actions."
                _rc17_copy_adopted_arrangement(out, idx, governing_idx, reason_pt, reason_en)
            # A failed row is not used as a preferred governing arrangement, but
            # the current local As is still kept on the row for diagnostics.
            if valid_candidate:
                new_as = _rc17_num(out.at[idx, "As adoptada [mm²]"], current_as)
                if new_as >= governing_as - 1e-6:
                    governing_idx = idx
                    governing_as = new_as

    # Section changes in a column line are not forced, but must be explicit.
    for pr, idxs_raw in out.groupby("Prumada", dropna=False, sort=False).groups.items():
        idxs = sorted(list(idxs_raw), key=lambda idx: _rc17_sort_key_from_tuple(out.at[idx, "_rc17_story_sort_tuple"]))
        if len(idxs) <= 1:
            continue
        previous_sig = None
        for idx in idxs:
            sig = out.at[idx, "_rc17_section_signature"]
            if previous_sig is not None and sig != previous_sig:
                note_pt = "Mudança de secção na prumada. Confirmar continuidade, emendas e compatibilização dos varões."
                note_en = "Section change within the column line. Check bar continuity, lap/splice detailing and reinforcement compatibility."
                old_pt = str(out.at[idx, "Nota de continuidade"] or "")
                old_en = str(out.at[idx, "Continuity note"] or "")
                out.at[idx, "Nota de continuidade"] = (old_pt + "; " + note_pt).strip("; ") if old_pt else note_pt
                out.at[idx, "Continuity note"] = (old_en + "; " + note_en).strip("; ") if old_en else note_en
            previous_sig = sig

    # Keep adopted solution mirrored in the legacy columns used by PDF/XLSX/DXF.
    for idx in out.index:
        sol = str(out.at[idx, "Solução adoptada"] or "")
        if sol:
            out.at[idx, "Solução"] = sol
            if "solucao" in out.columns:
                out.at[idx, "solucao"] = sol
            if "solucao_completa" in out.columns:
                out.at[idx, "solucao_completa"] = sol
        as_ad = _rc17_num(out.at[idx, "As adoptada [mm²]"], 0.0)
        if as_ad > 0 and "as_prov_mm2" in out.columns:
            out.at[idx, "as_prov_mm2"] = as_ad

    # Re-apply D=... labels after any manipulation.
    try:
        if "_rc16_apply_section_labels_df" in globals():
            out = _rc16_apply_section_labels_df(out)
    except Exception:
        pass

    # Final order: column line, then lower -> upper.
    try:
        out["_rc17_prumada_sort"] = out["Prumada"].astype(str).map(_v682_natural_key) if "_v682_natural_key" in globals() else out["Prumada"].astype(str)
        out = out.sort_values(["_rc17_prumada_sort", "_rc17_story_key", "member"], kind="mergesort").reset_index(drop=True)
    except Exception:
        try:
            out = out.sort_values(["Prumada", "_rc17_story_key", "member"], kind="mergesort").reset_index(drop=True)
        except Exception:
            pass
    try:
        out["Ordem na prumada"] = out.groupby("Prumada").cumcount() + 1
    except Exception:
        pass
    drop_cols = [c for c in ["_rc17_section_signature", "_rc17_story_sort_tuple", "_rc17_story_key", "_rc17_status_text", "_rc17_prumada_sort"] if c in out.columns]
    return out.drop(columns=drop_cols, errors="ignore")


# ---------------------------------------------------------------------------
# Public schedule builders / GUI hooks
# ---------------------------------------------------------------------------

def _rc17_build_tramo_schedule(results: pd.DataFrame) -> pd.DataFrame:
    return _rc17_apply_vertical_rationalisation(_rc17_initial_schedule(results))


def _rc17_build_summary_by_member(self, results: pd.DataFrame) -> pd.DataFrame:
    return _rc17_build_tramo_schedule(results)

ColumnsEC2App.build_summary_by_member = _rc17_build_summary_by_member
_v682_build_tramo_schedule = _rc17_build_tramo_schedule
_v683_build_tramo_schedule = _rc17_build_tramo_schedule


# Ensure Excel exports and the schedule sheet use the rationalised adopted
# arrangement rather than the raw local design rows.
_rc17_prev_write_excel = ColumnsEC2App._write_excel

def _rc17_write_excel(self, path: str):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc17_build_tramo_schedule(self.df_results)
            if hasattr(self, "tree_summary"):
                try:
                    self.show_df(self.tree_summary, self.df_summary)
                except Exception:
                    pass
    except Exception:
        pass
    return _rc17_prev_write_excel(self, path)

ColumnsEC2App._write_excel = _rc17_write_excel


# DXF must use the final rationalised column schedule, not the isolated local
# result list. This keeps the drawing consistent with the adopted reinforcement.
_rc17_prev_export_dxf = ColumnsEC2App.export_dxf

def _rc17_export_dxf(self):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc17_build_tramo_schedule(self.df_results)
    except Exception:
        pass
    return _rc17_prev_export_dxf(self)

ColumnsEC2App.export_dxf = _rc17_export_dxf


# ---------------------------------------------------------------------------
# EN-UK wording for the new technical fields/messages
# ---------------------------------------------------------------------------
try:
    _RC13_EN_TERMS.update({
        "Solução adoptada aumentada por continuidade vertical: o tramo superior compatível governa a prumada/secção.": "Adopted arrangement increased for vertical continuity: the compatible upper segment governs the column line/section.",
        "O tramo governante superior não está verificado; rever a secção/esforços.": "The governing upper segment is not verified; review the section/design actions.",
        "Mudança de secção na prumada. Confirmar continuidade, emendas e compatibilização dos varões.": "Section change within the column line. Check bar continuity, lap/splice detailing and reinforcement compatibility.",
        "Critério de uniformização": "Rationalisation criterion",
        "Nota de continuidade": "Continuity note",
        "Solução adoptada": "Adopted arrangement",
        "As adoptada [mm²]": "As adopted [mm²]",
        "Vertical rationalisation": "Vertical rationalisation",
        "Sim": "Yes",
        "Não": "No",
    })
except Exception:
    pass
