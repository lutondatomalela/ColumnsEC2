# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC16 — circular DXF drawing and diameter labels.

This patch improves the presentation layer for circular columns:
- circular sections are drawn as circles in the DXF column schedule, including
  circular links and perimeter reinforcement;
- circular section labels are reported as D=<diameter> instead of b x h;
- schedule/summary tables receive explicit section labels that distinguish
  rectangular and circular geometries;
- PT and EN-UK wording is kept technical and output-oriented.
"""

APP_VERSION = "v0.9 RC16 Modular"

# ---------------------------------------------------------------------------
# Circular section helpers
# ---------------------------------------------------------------------------

def _rc16_num(x, default=0.0):
    try:
        v = safe_float(x, default)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _rc16_is_circular_row(row) -> bool:
    """Return True when a result/schedule row represents a circular section."""
    try:
        txt = " ".join(str(row.get(c, "") or "") for c in [
            "section_shape", "layout_type", "Secção [cm]", "Section [cm]", "Secção", "Section", "solucao", "Solução"
        ]).lower()
        if "circular" in txt or " d=" in f" {txt}" or txt.startswith("d="):
            return True
    except Exception:
        pass
    try:
        b = _rc16_num(row.get("b_cm", row.get("hy", 0.0))) * 10.0
        h = _rc16_num(row.get("h_cm", row.get("hz", 0.0))) * 10.0
        if "_rc14_infer_circular_from_geometry" in globals() and _rc14_infer_circular_from_geometry(row, b, h):
            return True
    except Exception:
        pass
    return False


def _rc16_diameter_mm(row) -> float:
    """Best estimate of circular-section diameter in mm."""
    b = _rc16_num(row.get("b_cm", row.get("hy", 0.0))) * 10.0
    h = _rc16_num(row.get("h_cm", row.get("hz", 0.0))) * 10.0
    vals = [v for v in [b, h] if v > 0]
    if vals:
        d = sum(vals) / len(vals)
        # If the imported dimensions are square-like, keep the common value.
        if max(vals) / max(min(vals), 1e-9) <= 1.08:
            return d
    # Fallback from area, if available.
    ax_cm2 = _rc16_num(row.get("ax", row.get("AX (cm2)", 0.0)), 0.0)
    if ax_cm2 > 0:
        return math.sqrt(4.0 * ax_cm2 * 100.0 / math.pi)
    return vals[0] if vals else 0.0


def _rc16_section_label(row, unit="cm") -> str:
    """Return 'D=30 cm' for circular rows or '25x40 cm' for rectangular rows."""
    circ = _rc16_is_circular_row(row)
    if circ:
        d_mm = _rc16_diameter_mm(row)
        if unit == "mm":
            return f"D={d_mm:.0f} mm" if d_mm else "D=? mm"
        return f"D={d_mm/10.0:.0f} cm" if d_mm else "D=? cm"
    b_cm = _rc16_num(row.get("b_cm", row.get("hy", 0.0)), 0.0)
    h_cm = _rc16_num(row.get("h_cm", row.get("hz", 0.0)), 0.0)
    if unit == "mm":
        return f"{b_cm*10.0:.0f}x{h_cm*10.0:.0f} mm"
    return f"{b_cm:.0f}x{h_cm:.0f} cm"


def _rc16_apply_section_labels_df(df):
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy()
    try:
        labels_cm = out.apply(lambda r: _rc16_section_label(r, "cm"), axis=1)
        labels_mm = out.apply(lambda r: _rc16_section_label(r, "mm"), axis=1)
        out["Secção [cm]"] = labels_cm
        out["Section [cm]"] = labels_cm
        out["Secção"] = labels_cm
        out["Section"] = labels_cm
        out["Section label"] = labels_cm
        out["section_label"] = labels_cm
        out["section_label_mm"] = labels_mm
        if "section_shape" not in out.columns:
            out["section_shape"] = "rectangular"
        out.loc[out.apply(_rc16_is_circular_row, axis=1), "section_shape"] = "circular"
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Summary / schedule table labels
# ---------------------------------------------------------------------------

_rc16_prev_build_summary = ColumnsEC2App.build_summary_by_member

def _rc16_build_summary_by_member(self, results):
    return _rc16_apply_section_labels_df(_rc16_prev_build_summary(self, results))

ColumnsEC2App.build_summary_by_member = _rc16_build_summary_by_member


# Annotate individual design rows with a clean section label as early as possible.
_rc16_prev_design_one = ColumnDesigner.design_one

def _rc16_design_one(self, row, prebuilt_candidates=None):
    out = _rc16_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)
    if isinstance(out, dict):
        try:
            out["section_shape"] = "circular" if _rc16_is_circular_row(out) or _rc16_infer_from_design_row(row, out) else str(out.get("section_shape", "rectangular") or "rectangular")
            out["section_label"] = _rc16_section_label(out, "cm")
            out["section_label_mm"] = _rc16_section_label(out, "mm")
            out["Secção [cm]"] = out["section_label"]
            out["Section [cm]"] = out["section_label"]
        except Exception:
            pass
    return out


def _rc16_infer_from_design_row(row, out) -> bool:
    try:
        b = _rc16_num(out.get("b_cm", row.get("hy", 0.0))) * 10.0
        h = _rc16_num(out.get("h_cm", row.get("hz", 0.0))) * 10.0
        return "_rc14_infer_circular_from_geometry" in globals() and _rc14_infer_circular_from_geometry(row, b, h)
    except Exception:
        return False

ColumnDesigner.design_one = _rc16_design_one


# Ensure main outputs exported to Excel carry D=... labels as well.
_rc16_prev_write_excel = ColumnsEC2App._write_excel

def _rc16_write_excel(self, path: str):
    try:
        for attr in ["df_results", "df_summary", "df_failures", "df_ok", "df_filtered"]:
            df = getattr(self, attr, None)
            if df is not None and not getattr(df, "empty", True):
                setattr(self, attr, _rc16_apply_section_labels_df(df))
    except Exception:
        pass
    return _rc16_prev_write_excel(self, path)

ColumnsEC2App._write_excel = _rc16_write_excel


# ---------------------------------------------------------------------------
# DXF writer with circular sections
# ---------------------------------------------------------------------------

def _rc16_circular_bar_points_from_row(row, scale=1.0):
    d = _rc16_diameter_mm(row)
    if d <= 0:
        return []
    phi = _rc16_num(row.get("phi_long_mm", row.get("phi_corner_mm", 12.0)), 12.0)
    phi_st = _rc16_num(row.get("phi_st_mm"), 8.0)
    cover = _rc16_num(row.get("cover_mm"), 35.0)
    n = max(6, int(_rc16_num(row.get("n_total"), 8)))
    r = d/2.0 - cover - phi_st - phi/2.0
    if r <= 0:
        r = max(0.30*d, 1.0)
    pts = []
    for i in range(n):
        ang = math.pi/2.0 - 2.0*math.pi*i/n
        pts.append((r*math.cos(ang)*scale, r*math.sin(ang)*scale, max(phi*scale/2.0, 3.0)))
    return pts


def _rc16_draw_rect_section(parts, row, ox, oy, scale):
    b = _rc16_num(row.get("b_cm", row.get("hy", 0.0)), 0.0) * 10.0
    h = _rc16_num(row.get("h_cm", row.get("hz", 0.0)), 0.0) * 10.0
    bs, hs = b*scale, h*scale
    lft, rgt = ox-bs/2, ox+bs/2
    bot, tp = oy-hs/2, oy+hs/2
    parts += [_dxf_line(lft,bot,rgt,bot,"COLUMNS_CONCRETE"), _dxf_line(rgt,bot,rgt,tp,"COLUMNS_CONCRETE"), _dxf_line(rgt,tp,lft,tp,"COLUMNS_CONCRETE"), _dxf_line(lft,tp,lft,bot,"COLUMNS_CONCRETE")]
    cov = _rc16_num(row.get("cover_mm"), 35.0)*scale
    l2, r2, b2, t2 = lft+cov, rgt-cov, bot+cov, tp-cov
    parts += [_dxf_line(l2,b2,r2,b2,"COLUMNS_STIRRUPS"), _dxf_line(r2,b2,r2,t2,"COLUMNS_STIRRUPS"), _dxf_line(r2,t2,l2,t2,"COLUMNS_STIRRUPS"), _dxf_line(l2,t2,l2,b2,"COLUMNS_STIRRUPS")]
    try:
        pts = _bar_points_for_result(row)
    except Exception:
        pts = []
    phi = _rc16_num(row.get("phi_long_mm"), 10.0)*scale
    for item in pts:
        try:
            yy, zz = item[0], item[1]
        except Exception:
            continue
        parts.append(_dxf_circle(ox+yy*scale, oy+zz*scale, max(phi/2.0, 3.0), "COLUMNS_REBAR"))
    nlinks = int(_rc16_num(row.get("numero_grampos_por_nivel", row.get("grampos_intermedios", 0)), 0))
    if nlinks > 0:
        if _rc16_num(row.get("n_bars_y"), 0) > 2:
            parts.append(_dxf_line(l2, oy, r2, oy, "COLUMNS_LINKS"))
        if _rc16_num(row.get("n_bars_z"), 0) > 2:
            parts.append(_dxf_line(ox, b2, ox, t2, "COLUMNS_LINKS"))
    try:
        _dxf_dim_text_v66(parts, lft, bot-45, rgt, bot-45, f"{b:.0f}", off=-35)
        _dxf_dim_text_v66(parts, rgt+45, bot, rgt+45, tp, f"{h:.0f}", off=0)
    except Exception:
        pass


def _rc16_draw_circular_section(parts, row, ox, oy, scale):
    d = _rc16_diameter_mm(row)
    if d <= 0:
        return
    r = d*scale/2.0
    parts.append(_dxf_circle(ox, oy, r, "COLUMNS_CONCRETE"))
    cov = _rc16_num(row.get("cover_mm"), 35.0)*scale
    phi_st = _rc16_num(row.get("phi_st_mm"), 8.0)*scale
    inner_r = max(r - cov - phi_st/2.0, 1.0)
    parts.append(_dxf_circle(ox, oy, inner_r, "COLUMNS_STIRRUPS"))
    for yy, zz, rr in _rc16_circular_bar_points_from_row(row, scale):
        parts.append(_dxf_circle(ox+yy, oy+zz, rr, "COLUMNS_REBAR"))
    nlinks = int(_rc16_num(row.get("numero_grampos_por_nivel", row.get("grampos_intermedios", 0)), 0))
    if nlinks > 0 or int(_rc16_num(row.get("n_total"), 0)) >= 10:
        parts.append(_dxf_line(ox-inner_r*0.92, oy, ox+inner_r*0.92, oy, "COLUMNS_LINKS"))
        parts.append(_dxf_line(ox, oy-inner_r*0.92, ox, oy+inner_r*0.92, "COLUMNS_LINKS"))
    # Diameter indication; a text label is clearer than two rectangular dimensions for circular sections.
    parts.append(_dxf_text(ox-r, oy-r-55, f"D={d:.0f}", 22, "COLUMNS_DIMENSIONS"))


def write_columns_dxf_v16(path: str, df: pd.DataFrame, lang: str = LANG_PT):
    try:
        sched = _v683_build_tramo_schedule(df)
    except Exception:
        sched = df.copy() if df is not None else pd.DataFrame()
    sched = _rc16_apply_section_labels_df(sched)
    try:
        sched = _v66_apply_constructive_detailing(sched) if "_v66_apply_constructive_detailing" in globals() else sched
    except Exception:
        pass

    en = (lang == LANG_EN)
    parts = ["0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n", _dxf_layer_table_v66() if "_dxf_layer_table_v66" in globals() else "0\nSECTION\n2\nTABLES\n0\nENDSEC\n", "0\nSECTION\n2\nENTITIES\n"]
    if sched is None or sched.empty:
        parts.append(_dxf_text(0, 0, "No results" if en else "Sem resultados", 50, "COLUMNS_TEXT"))
        parts.append("0\nENDSEC\n0\nEOF\n")
        Path(path).write_text("".join(parts), encoding="utf-8")
        return

    work = sched.copy()
    if "Prumada" not in work.columns:
        try:
            work["Prumada"] = work.apply(_v682_prumada_from_row, axis=1)
        except Exception:
            work["Prumada"] = work.get("name", work.get("member", ""))
    if "Piso" not in work.columns:
        try:
            work["Piso"] = work.apply(_v683_story_label_from_row, axis=1)
        except Exception:
            work["Piso"] = work.get("story", "")
    if "_story_sort_tuple" not in work.columns:
        try:
            work["_story_sort_tuple"] = work.apply(_v683_story_sort_tuple, axis=1)
        except Exception:
            work["_story_sort_tuple"] = [(0, 0.0, str(v)) for v in work.get("Piso", pd.Series("", index=work.index))]
    work["_story_rank"] = work["_story_sort_tuple"].map(lambda x: x[0] if isinstance(x, tuple) and x else 0)
    work["_story_rank_float"] = work["_story_sort_tuple"].map(lambda x: x[1] if isinstance(x, tuple) and len(x) > 1 else 0.0)

    prumadas = sorted(work["Prumada"].astype(str).unique(), key=_v682_natural_key)[:32]
    levels_df = work[["Piso", "_story_rank", "_story_rank_float", "_story_sort_tuple"]].drop_duplicates()
    levels_df = levels_df.sort_values(["_story_rank", "_story_rank_float"], kind="mergesort")
    levels = list(levels_df["Piso"].astype(str))[:24]

    cell_w, cell_h = 1450.0, 1180.0
    level_w = 420.0
    margin_x, base_y = 480.0, 0.0
    title_y = base_y + len(levels)*cell_h + 780.0
    header_y = base_y + len(levels)*cell_h + 420.0

    parts.append(_dxf_text(margin_x, title_y, "COLUMN SCHEDULE - UNITS: mm" if en else "QUADRO DE PILARES - UNIDADES: mm", 52, "COLUMNS_TEXT"))
    parts.append(_dxf_text(margin_x, title_y-130, "Column-line and storey layout: columns = column lines; rows = storeys in ascending order from lower to upper." if en else "Organização por prumada e piso: colunas = prumadas; linhas = pisos em ordem ascendente, do inferior para o superior.", 25, "COLUMNS_TEXT"))
    parts.append(_dxf_text(margin_x, title_y-195, "Legend: concrete=outline | bars=circles | links=inner contour | cross-ties=internal lines | dimensions in mm" if en else "Legenda: betão=contorno | varões=círculos | estribos=contorno interior | grampos=linhas interiores | cotas em mm", 24, "COLUMNS_TEXT"))

    parts.append(_dxf_text(0, header_y, "Storey" if en else "Piso", 34, "COLUMNS_TABLE"))
    for c, pr in enumerate(prumadas):
        x0 = margin_x + c * cell_w
        parts.append(_dxf_text(x0 + cell_w*0.38, header_y, str(pr), 42, "COLUMNS_TABLE"))

    total_w = level_w + len(prumadas)*cell_w
    total_h = len(levels)*cell_h
    left = 0.0
    bottom = base_y
    top = base_y + total_h
    right = left + total_w
    parts += [_dxf_line(left, bottom, right, bottom, "COLUMNS_TABLE"), _dxf_line(right, bottom, right, top, "COLUMNS_TABLE"), _dxf_line(right, top, left, top, "COLUMNS_TABLE"), _dxf_line(left, top, left, bottom, "COLUMNS_TABLE"), _dxf_line(level_w, bottom, level_w, top, "COLUMNS_TABLE")]
    for c in range(len(prumadas)+1):
        x = level_w + c*cell_w
        parts.append(_dxf_line(x, bottom, x, top, "COLUMNS_TABLE"))
    for r in range(len(levels)+1):
        y = base_y + r*cell_h
        parts.append(_dxf_line(left, y, right, y, "COLUMNS_TABLE"))

    lookup = {}
    for _, r in work.iterrows():
        key = (str(r.get("Prumada", "")), str(r.get("Piso", "")))
        if key not in lookup:
            lookup[key] = r
        else:
            try:
                old = pd.DataFrame([lookup[key]])
                new = pd.DataFrame([r])
                if float(_v682_governing_score_df(new).iloc[0]) > float(_v682_governing_score_df(old).iloc[0]):
                    lookup[key] = r
            except Exception:
                pass

    for r_i, level in enumerate(levels):
        y0 = base_y + r_i*cell_h
        parts.append(_dxf_text(25, y0 + cell_h*0.47, str(level), 27, "COLUMNS_TABLE"))
        for c, pr in enumerate(prumadas):
            x0 = level_w + c*cell_w
            row = lookup.get((str(pr), str(level)))
            if row is None:
                cx = x0 + cell_w/2.0
                cy = y0 + cell_h/2.0
                parts.append(_dxf_line(cx-120, cy, cx+120, cy, "COLUMNS_TEXT"))
                continue
            b = _rc16_num(row.get("b_cm", row.get("hy", 0.0))) * 10.0
            h = _rc16_num(row.get("h_cm", row.get("hz", 0.0))) * 10.0
            d = _rc16_diameter_mm(row) if _rc16_is_circular_row(row) else max(b, h)
            if max(b, h, d) <= 0:
                parts.append(_dxf_text(x0 + 25, y0 + cell_h - 120, "No geometry" if en else "Sem geometria", 26, "COLUMNS_TEXT"))
                continue
            ox = x0 + cell_w/2.0
            oy = y0 + cell_h/2.0 + 70.0
            scale = min(1.0, 620.0/max(b, h, d, 1.0))
            if _rc16_is_circular_row(row):
                _rc16_draw_circular_section(parts, row, ox, oy, scale)
            else:
                _rc16_draw_rect_section(parts, row, ox, oy, scale)

            member = str(row.get("member", ""))
            mat = str(row.get("material", ""))
            sec = _rc16_section_label(row, "mm")
            sol = str(row.get("Solução adoptada", row.get("solucao_completa", row.get("Solução", row.get("solucao", "")))))[:95]
            status = str(row.get("estado_global", row.get("Estado", row.get("status", ""))))
            eta = _rc16_num(row.get("η_NMyMz", row.get("eta_NMyMz", row.get("utilizacao", 0.0))), 0.0)
            parts.append(_dxf_text(x0+25, y0+cell_h-70, f"{level} | Member {member} | {mat}", 22, "COLUMNS_TEXT"))
            parts.append(_dxf_text(x0+25, y0+cell_h-105, ("Section: " if en else "Secção: ") + sec, 21, "COLUMNS_TEXT"))
            parts.append(_dxf_text(x0+25, y0+cell_h-140, sol, 20, "COLUMNS_TEXT"))
            parts.append(_dxf_text(x0+25, y0+cell_h-175, (f"Status: {status} | eta={eta:.2f}" if en else f"Estado: {status} | eta={eta:.2f}"), 20, "COLUMNS_TEXT"))
            nlinks = int(_rc16_num(row.get("numero_grampos_por_nivel", row.get("grampos_intermedios", 0)), 0))
            if nlinks > 0:
                parts.append(_dxf_text(x0+25, y0+cell_h-210, (f"Cross-ties: {nlinks} per level" if en else f"Grampos: {nlinks} por nível"), 19, "COLUMNS_TEXT"))

    parts.append("0\nENDSEC\n0\nEOF\n")
    Path(path).write_text("".join(parts), encoding="utf-8")


write_columns_dxf_v4 = write_columns_dxf_v16
write_columns_dxf_v66 = write_columns_dxf_v16
write_columns_dxf_v682 = write_columns_dxf_v16
write_columns_dxf_v683 = write_columns_dxf_v16
write_columns_dxf_v69 = write_columns_dxf_v16


def _rc16_export_dxf(self):
    src = getattr(self, "df_results", pd.DataFrame())
    if src is None or src.empty:
        src = getattr(self, "df_summary", pd.DataFrame())
    is_en = False
    try:
        is_en = _v69_is_en(self)
    except Exception:
        pass
    if src is None or src.empty:
        messagebox.showwarning("Warning" if is_en else "Aviso", "No results to export to DXF." if is_en else "Não há resultados para exportar em DXF.")
        return
    title = "Export column schedule [DXF]" if is_en else "Exportar quadro de pilares [DXF]"
    path = filedialog.asksaveasfilename(title=title, defaultextension=".dxf", filetypes=[("DXF", "*.dxf")])
    if not path:
        return
    try:
        self.status_var.set("Exporting column schedule [mm]..." if is_en else "A exportar quadro de pilares [mm]...")
        self.update_idletasks()
        write_columns_dxf_v16(path, src, LANG_EN if is_en else LANG_PT)
        self.status_var.set(("Column schedule exported: " if is_en else "Quadro de pilares exportado: ") + str(path))
    except Exception as err:
        messagebox.showerror("Error" if is_en else "Erro", ("Could not export the column schedule DXF.\n\n" if is_en else "Não foi possível exportar o quadro de pilares em DXF.\n\n") + str(err))

ColumnsEC2App.export_dxf = _rc16_export_dxf


# ---------------------------------------------------------------------------
# EN-UK technical wording for new labels
# ---------------------------------------------------------------------------
try:
    _RC13_EN_TERMS.update({
        "Secção [cm]": "Section [cm]",
        "Secção": "Section",
        "D=" : "D=",
        "Quadro de pilares exportado:": "Column schedule exported:",
        "A exportar quadro de pilares [mm]...": "Exporting column schedule [mm]...",
        "Sem geometria": "No geometry",
    })
except Exception:
    pass
