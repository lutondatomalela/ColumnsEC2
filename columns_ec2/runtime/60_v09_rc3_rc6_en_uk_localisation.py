# -*- coding: utf-8 -*-
# Auto-split from ColumnsEC2 v0.9 RC8.
# This module is executed in the shared runtime namespace by columns_ec2.runtime.loader.
# Keep execution order defined in columns_ec2/runtime/manifest.py.

APP_VERSION = "v0.9 RC3"

_RC3_UI_EXTRA_PT_EN = {
    "Estado:": "Status:",
    "Estado": "Status",
    "Linguagem": "Language",
    "Aplicar": "Apply",
    "Análise e dimensionamento de pilares de betão armado": "Reinforced concrete column analysis and design",
    "Dimensionamento de pilares em betão armado: ELU, ELS, interacção N-My-Mz, pormenorização e relatórios técnicos.": "Reinforced concrete column design: ULS, SLS, N-My-Mz interaction, detailing and technical reports.",
    "Cole a tabela, interprete-a e confirme/edite na grelha antes do cálculo.": "Paste the table, parse it and confirm/edit it in the grid before running the calculation.",
    "Texto colado": "Pasted text",
    "Tabela editável reconhecida": "Recognised editable table",
    "Adicionar linha": "Add row",
    "Remover linha": "Remove row",
    "Ler grelha": "Read grid",
    "Interpretar texto": "Parse text",
    "Limpar": "Clear",
    "Concreto": "Concrete",
    "Aço": "Steel",
    "Classe de aço": "Steel grade",
    "Recobrimento nominal [mm]": "Nominal cover [mm]",
    "Capa nominal [mm]": "Nominal cover [mm]",
    "Modo": "Mode",
    "Dimensionamento": "Design/check",
    "Pré-dimensionamento": "Preliminary design",
    "Rigoroso": "Rigorous",
    "Reduzir para casos governantes": "Reduce to governing cases",
    "Resumo por membro": "Member summary",
    "Abrir repositório": "Open repository",
    "Exportar Excel": "Export Excel",
    "Exportar .xlsx": "Export .xlsx",
    "Relatório PDF": "PDF report",
    "Relatório .pdf": "PDF report",
    "A exportar PDF...": "Exporting PDF...",
    "A exportar Excel...": "Exporting Excel...",
    "A exportar XLSX...": "Exporting XLSX...",
    "A exportar quadro de pilares por prumada/piso [mm]...": "Exporting column schedule by column line/storey [mm]...",
    "Não há resultados para exportar.": "There are no results to export.",
    "Não foi possível exportar PDF.": "PDF export failed.",
    "Exportar relatório PDF": "Export PDF report",
    "Excel exportado": "Excel exported",
    "PDF exportado": "PDF exported",
    "A calcular": "Calculating",
    "Cálculo concluído": "Calculation completed",
    "Sem dados.": "No data.",
    "Sem colunas aplicáveis.": "No applicable columns.",
}

try:
    _V69_UI_MAP_PT_EN.update(_RC3_UI_EXTRA_PT_EN)
    _V69_UI_MAP_EN_PT.update({v: k for k, v in _RC3_UI_EXTRA_PT_EN.items()})
except Exception:
    pass

_RC3_STATUS_PT_EN = {
    "OK": "OK",
    "Aviso": "Warning",
    "Falha": "Failure",
    "Pré-dimensionado": "Preliminary",
    "Não avaliado": "Not assessed",
    "Verificar": "Check",
    "Não conforme": "Not compliant",
    "Dispensada": "Waived",
    "Sim": "Yes",
    "Não": "No",
    "Sem aviso relevante": "No relevant warning",
    "Torção desprezável — não condicionante": "Negligible torsion — not governing",
    "Não avaliado neste backend structuralcodes pelo ColumnsEC2; sem fallback interno.": "Not assessed in this structuralcodes backend by ColumnsEC2; no internal fallback used.",
}


def _rc3_lang(app):
    try:
        return LANG_EN if str(app.var_language.get()).upper().startswith("EN") else LANG_PT
    except Exception:
        return LANG_PT


def _v69_lang(app):
    return _rc3_lang(app)


def _v69_is_en(app):
    return _rc3_lang(app) == LANG_EN


def _v69_status_text(value, lang):
    if lang != LANG_EN:
        return value
    s = str(value)
    for pt, en in sorted(_RC3_STATUS_PT_EN.items(), key=lambda kv: len(kv[0]), reverse=True):
        if s == pt:
            return en
    for pt, en in sorted(_RC3_STATUS_PT_EN.items(), key=lambda kv: len(kv[0]), reverse=True):
        s = s.replace(pt, en)
    s = s.replace("Aviso:", "Warning:").replace("Falha:", "Failure:").replace("Não avaliado:", "Not assessed:")
    s = s.replace("sem solução N-My-Mz por structuralcodes", "no N-My-Mz solution from structuralcodes")
    s = s.replace("pormenorização construtiva", "constructive detailing")
    s = s.replace("esforço transverso", "shear")
    s = s.replace("torção", "torsion")
    s = s.replace("não gerada", "not generated")
    return s


def _v69_tr_text(text, target_lang):
    s = str(text)
    if target_lang == LANG_EN:
        if s in _V69_UI_MAP_PT_EN:
            return _V69_UI_MAP_PT_EN[s]
        if s in _V69_CELL_MAP_PT_EN:
            return _V69_CELL_MAP_PT_EN[s]
        if s in _RC3_STATUS_PT_EN:
            return _RC3_STATUS_PT_EN[s]
        # common sentence fragments used by labels/status messages
        repl = [
            ("Análise e dimensionamento de pilares de betão armado", "Reinforced concrete column analysis and design"),
            ("Dimensionamento de pilares em betão armado", "Reinforced concrete column design"),
            ("betão armado", "reinforced concrete"),
            ("relatórios técnicos", "technical reports"),
            ("interacção N-My-Mz", "N-My-Mz interaction"),
            ("pormenorização", "detailing"),
            ("prumada", "column line"),
            ("piso", "storey"),
            ("A exportar", "Exporting"),
            ("exportado", "exported"),
            ("Não foi possível", "Could not"),
        ]
        out = s
        for a, b in repl:
            out = out.replace(a, b)
        return out
    return _V69_UI_MAP_EN_PT.get(s, s)


def _rc3_walk_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _rc3_walk_widgets(child)


def _rc3_set_widget_text(widget, text):
    try:
        widget.configure(text=text)
    except Exception:
        pass


def _rc3_backend_quick_note(app, lang):
    try:
        norm = _v59_norm_reference(app) if "_v59_norm_reference" in globals() else "Eurocode 2"
    except Exception:
        norm = "Eurocode 2"
    try:
        backend = _v59_backend_key(app) if "_v59_backend_key" in globals() else "pt2010"
    except Exception:
        backend = "pt2010"
    if lang == LANG_EN:
        if backend == "pt2010":
            return (
                f"Standard: {norm}\n"
                "Engine: internal Portuguese EC2 engine. ULS, second-order effects, N-My-Mz interaction, shear/torsion checks, detailing and reports are handled by ColumnsEC2."
            )
        return (
            f"Standard: {norm}\n"
            "Engine: structuralcodes. Materials, creep/shrinkage, N-My-Mz, shear, torsion, SLS and bond are evaluated where available in the installed API. Items not exposed by the backend are reported as not assessed."
        )
    if backend == "pt2010":
        return (
            f"Norma: {norm}\n"
            "Motor: EC2 português interno. ELU, 2.ª ordem, N-My-Mz, corte/torção, pormenorização e relatórios são tratados pelo ColumnsEC2."
        )
    return (
        f"Norma: {norm}\n"
        "Motor: structuralcodes. Materiais, fluência/retracção, N-My-Mz, esforço transverso, torção, ELS e aderência são avaliados quando disponíveis na API instalada."
    )


def _rc3_apply_language(self):
    lang = _rc3_lang(self)
    try:
        self.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if lang == LANG_EN else APP_TITLE)
    except Exception:
        pass

    # Labels, buttons, labelframes and checkbuttons.
    for w in _rc3_walk_widgets(self):
        try:
            txt = str(w.cget("text"))
        except Exception:
            continue
        new = _v69_tr_text(txt, lang)
        if new != txt:
            _rc3_set_widget_text(w, new)

    # Notebook tabs.
    try:
        for nb in [w for w in _rc3_walk_widgets(self) if isinstance(w, ttk.Notebook)]:
            for tab_id in nb.tabs():
                txt = nb.tab(tab_id, "text")
                nb.tab(tab_id, text=_v69_tr_text(txt, lang))
    except Exception:
        pass

    # Descriptive labels that can be long and not exactly matched by the dictionary.
    for w in _rc3_walk_widgets(self):
        try:
            txt = str(w.cget("text"))
        except Exception:
            continue
        if "Análise e dimensionamento" in txt or "Reinforced concrete column analysis" in txt:
            _rc3_set_widget_text(w, "Reinforced concrete column analysis and design" if lang == LANG_EN else "Análise e dimensionamento de pilares de betão armado")
        elif "Dimensionamento de pilares" in txt and "ELU" in txt:
            _rc3_set_widget_text(w, "Reinforced concrete column design: ULS, SLS, N-My-Mz interaction, detailing and technical reports." if lang == LANG_EN else "Dimensionamento de pilares em betão armado: ELU, ELS, interacção N-My-Mz, pormenorização e relatórios técnicos.")
        elif ("Norma:" in txt or "Standard:" in txt) and ("Motor:" in txt or "Engine:" in txt):
            _rc3_set_widget_text(w, _rc3_backend_quick_note(self, lang))

    # Instructions tab.
    try:
        _v69_refresh_instructions(self)
    except Exception:
        pass

    # Button that applies the language, and the language frame itself.
    try:
        for w in _rc3_walk_widgets(self):
            try:
                txt = str(w.cget("text"))
            except Exception:
                continue
            if txt in ["Linguagem", "Language"]:
                w.configure(text="Language" if lang == LANG_EN else "Linguagem")
            if txt in ["Aplicar", "Apply"]:
                w.configure(text="Apply" if lang == LANG_EN else "Aplicar")
    except Exception:
        pass

    try:
        self.status_var.set("Language set to English (UK)." if lang == LANG_EN else "Idioma definido para Português.")
    except Exception:
        pass

ColumnsEC2App.apply_language = _rc3_apply_language
_v69_apply_language = _rc3_apply_language


def _v091_apply_language_title(app):
    # Kept for the main block; now applies the full current language, not only the window title.
    try:
        _rc3_apply_language(app)
    except Exception:
        try:
            app.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if _rc3_lang(app) == LANG_EN else APP_TITLE)
        except Exception:
            pass




def _rc3_get_var(obj, name, default=""):
    try:
        var = getattr(obj, name, None)
        if var is None:
            return default
        if hasattr(var, "get"):
            return var.get()
        return var
    except Exception:
        return default

def _rc3_is_scalar_nan(v):
    try:
        r = pd.isna(v)
        if isinstance(r, (pd.Series, pd.DataFrame, list, tuple)):
            return False
        return bool(r)
    except Exception:
        return False


def _rc3_scalar(v):
    # Prevents pandas Series truth-value errors when a dataframe has duplicate column names.
    try:
        if isinstance(v, pd.Series):
            if v.empty:
                return ""
            return v.iloc[0]
        if isinstance(v, pd.DataFrame):
            if v.empty:
                return ""
            return v.iloc[0, 0]
    except Exception:
        return ""
    return v


def _rc3_cell_text(v, lang=LANG_PT):
    v = _rc3_scalar(v)
    if isinstance(v, float):
        txt = "" if not math.isfinite(v) else f"{v:.2f}"
    else:
        if _rc3_is_scalar_nan(v):
            txt = ""
        else:
            txt = str(v)
    if lang == LANG_EN:
        txt = _v69_status_text(txt, lang)
        # Frequent terms in free text fields.
        replacements = [
            ("Falha", "Failure"), ("Aviso", "Warning"), ("Não avaliado", "Not assessed"),
            ("estribos", "links"), ("grampos", "cross-ties"), ("pormenorização", "detailing"),
            ("esforço transverso", "shear"), ("torção", "torsion"), ("fendilhação", "cracking"),
            ("sem fallback interno", "no internal fallback"), ("não gerada", "not generated"),
            ("não calculado", "not calculated"), ("não exposta", "not exposed"),
        ]
        for a, b in replacements:
            txt = txt.replace(a, b)
    return txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rc3_deduplicate_columns(df):
    if df is None or df.empty:
        return df
    out = df.copy()
    seen = {}
    new_cols = []
    for c in out.columns:
        s = str(c)
        if s in seen:
            seen[s] += 1
            new_cols.append(f"{s}__{seen[s]}")
        else:
            seen[s] = 0
            new_cols.append(s)
    out.columns = new_cols
    return out


def _rc3_prepare_display_df(df, lang):
    if df is None or df.empty:
        return pd.DataFrame()
    out = _rc3_deduplicate_columns(df.copy())
    # Add common aliases so the PDF tables work regardless of legacy/PT/internal headers.
    aliases = {
        "prumada": "Prumada", "story": "Piso", "piso": "Piso", "Storey": "Piso", "Story": "Piso",
        "section_cm": "Secção [cm]", "secção": "Secção [cm]", "seccao": "Secção [cm]",
        "solucao": "Solução", "reinforcement_solution": "Solução", "estado_global": "Estado", "status": "Estado",
        "n_ed_kN": "N_Ed_kN", "my_ed_kNm": "My_Ed_kNm", "mz_ed_kNm": "Mz_Ed_kNm",
    }
    for src, dst_col in aliases.items():
        if src in out.columns and dst_col not in out.columns:
            try:
                out[dst_col] = out[src]
            except Exception:
                pass
    if "Secção [cm]" not in out.columns and "b_cm" in out.columns and "h_cm" in out.columns:
        try:
            out["Secção [cm]"] = out.apply(lambda r: f"{_finite(r.get('b_cm')):.0f}×{_finite(r.get('h_cm')):.0f}", axis=1)
        except Exception:
            pass
    if "η_NMyMz" not in out.columns and "utilizacao" in out.columns:
        out["η_NMyMz"] = out["utilizacao"]
    if lang == LANG_EN:
        out = out.rename(columns={**_V69_HEADER_MAP_PT_EN, "Piso": "Storey", "Secção [cm]": "Section [cm]", "Solução": "Reinforcement solution", "Estado": "Status", "Case": "Case", "Critério": "Criterion"})
        for c in list(out.columns):
            cname = str(c).lower()
            if "status" in cname or "estado" in cname or c in ["Status", "Overall status", "Resistance status"]:
                try:
                    out[c] = out[c].map(lambda x: _v69_status_text(x, lang))
                except Exception:
                    pass
    return _rc3_deduplicate_columns(out)


def _rc3_col_series(df, names):
    if df is None or df.empty:
        return pd.Series(dtype=str)
    for name in names:
        if name in df.columns:
            val = df[name]
            if isinstance(val, pd.DataFrame):
                return val.iloc[:, 0]
            return val
    return pd.Series(dtype=str)


def _rc3_pdf_table(df, cols, style, max_rows=40, lang=LANG_PT):
    from reportlab.platypus import Table, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import TableStyle
    if df is None or df.empty:
        return Paragraph("No data." if lang == LANG_EN else "Sem dados.", style)
    df = _rc3_deduplicate_columns(df)
    present = []
    for c in cols:
        if c in df.columns:
            present.append(c)
    if not present:
        return Paragraph("No applicable columns." if lang == LANG_EN else "Sem colunas aplicáveis.", style)
    data = [[Paragraph(str(c), style) for c in present]]
    for _, r in df.head(max_rows).iterrows():
        row = []
        for c in present:
            try:
                v = r.get(c, "")
            except Exception:
                v = ""
            row.append(Paragraph(_rc3_cell_text(v, lang), style))
        data.append(row)
    widths = [270 * mm / max(1, len(present))] * len(present)
    tbl = Table(data, colWidths=widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl

# Keep legacy calls safe as well.
def _v68_table(df, cols, style, max_rows=40):
    return _rc3_pdf_table(df, cols, style, max_rows=max_rows, lang=LANG_PT)


def _write_pdf_rc3(self, path: str):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    import tempfile, shutil
    lang = _rc3_lang(self)
    styles = _v68_pdf_styles() if "_v68_pdf_styles" in globals() else _pdf_styles_v3()
    level = _rc3_get_var(self, "var_pdf_level", "Relatório técnico" if lang == LANG_PT else "Technical report")
    if lang == LANG_EN and level in ["Resumo executivo", "Relatório técnico", "Memória de cálculo"]:
        level = {"Resumo executivo": "Executive summary", "Relatório técnico": "Technical report", "Memória de cálculo": "Detailed calculation note"}.get(level, level)
    if lang == LANG_PT and level in ["Executive summary", "Technical report", "Detailed calculation note"]:
        level = {"Executive summary": "Resumo executivo", "Technical report": "Relatório técnico", "Detailed calculation note": "Memória de cálculo"}.get(level, level)

    res = getattr(self, "df_results", pd.DataFrame())
    if res is None:
        res = pd.DataFrame()
    try:
        if "_v68_apply_constructive_detailing" in globals() and not res.empty:
            res = _v68_apply_constructive_detailing(res)
    except Exception:
        pass

    summ_src = getattr(self, "df_summary", pd.DataFrame())
    if summ_src is None or summ_src.empty:
        summ_src = res
    try:
        if "_v683_build_tramo_schedule" in globals():
            summ = _v683_build_tramo_schedule(summ_src)
        elif "_v681_decision_by_prumada" in globals():
            summ = _v681_decision_by_prumada(summ_src)
        else:
            summ = summ_src
    except Exception:
        summ = summ_src
    try:
        inter = _v68_interaction_summary(summ_src) if "_v68_interaction_summary" in globals() else pd.DataFrame()
    except Exception:
        inter = pd.DataFrame()
    try:
        module = _v65_module_status_table(res) if "_v65_module_status_table" in globals() and not res.empty else pd.DataFrame()
    except Exception:
        module = pd.DataFrame()
    try:
        gov = _v681_governing_cases_for_pdf(self) if "_v681_governing_cases_for_pdf" in globals() else getattr(self, "df_calc_input", pd.DataFrame())
    except Exception:
        gov = getattr(self, "df_calc_input", pd.DataFrame())
    try:
        perf = _v68_performance_df(self) if "_v68_performance_df" in globals() else pd.DataFrame()
    except Exception:
        perf = pd.DataFrame()

    summ_d = _rc3_prepare_display_df(summ, lang)
    inter_d = _rc3_prepare_display_df(inter, lang)
    module_d = _rc3_prepare_display_df(module, lang)
    gov_d = _rc3_prepare_display_df(gov, lang)
    perf_d = _rc3_prepare_display_df(perf, lang)

    n_total = len(res)
    st_series = _rc3_col_series(res, ["estado_global", "status", "Estado", "Status"]).astype(str)
    n_fail = int((st_series == "Falha").sum()) if not st_series.empty else 0
    n_warn = int((st_series == "Aviso").sum()) if not st_series.empty else 0
    pr_series = _rc3_col_series(summ_d, ["Column line", "Prumada", "prumada", "name", "Name"]).astype(str)
    n_pr = int(pr_series.nunique()) if not pr_series.empty else 0

    if lang == LANG_EN:
        subtitle = "Technical report for reinforced concrete column design/checking"
        section_decision = "1. Design decision by column line / segment"
        section_inter = "2. N-My-Mz interaction"
        section_module = "3. Module status"
        section_gov = "4. Governing cases"
        section_perf = "5. Performance"
        meta = pd.DataFrame([
            {"Field": "Reference standard", "Value": _v59_norm_reference(self) if "_v59_norm_reference" in globals() else "Eurocode 2"},
            {"Field": "Report level", "Value": level},
            {"Field": "Reinforcement strategy", "Value": _rc3_get_var(self, "var_rebar_strategy", "Balanced")},
            {"Field": "Column lines", "Value": n_pr},
            {"Field": "Analysed cases", "Value": n_total},
            {"Field": "Failures / Warnings", "Value": f"{n_fail} / {n_warn}"},
        ])
        meta_cols = ["Field", "Value"]
        decision_cols = ["Column line", "Storey", "Section [cm]", "material", "N_Ed_kN", "My_Ed_kNm", "Mz_Ed_kNm", "η_NMyMz", "Reinforcement solution", "Status"]
        inter_cols = ["Column line", "Case", "N_Ed [kN]", "My_Ed [kNm]", "Mz_Ed [kNm]", "MRd_y [kNm]", "MRd_z [kNm]", "η_NMyMz", "Resistance status"]
        mod_cols = ["Column line", "case", "overall_status", "resistance_status", "shear_status", "torsion_status", "sls_status", "detailing_status", "technical_decision"]
        gov_cols = ["Column line", "Case", "Criterion", "NEd [kN]", "My [kNm]", "Mz [kNm]", "Vy [kN]", "Vz [kN]", "T [kNm]"]
        perf_cols = ["Item", "Value", "Note"]
        page_word = "Page"
    else:
        subtitle = "Relatório técnico de dimensionamento/verificação de pilares de betão armado"
        section_decision = "1. Decisão por prumada / tramo"
        section_inter = "2. Interacção N-My-Mz"
        section_module = "3. Estados por módulo"
        section_gov = "4. Casos governantes"
        section_perf = "5. Performance"
        meta = pd.DataFrame([
            {"Campo": "Norma/Motor", "Valor": _v59_norm_reference(self) if "_v59_norm_reference" in globals() else "Eurocódigo 2"},
            {"Campo": "Nível do relatório", "Valor": level},
            {"Campo": "Estratégia de armadura", "Valor": _rc3_get_var(self, "var_rebar_strategy", "Equilibrada")},
            {"Campo": "Prumadas", "Valor": n_pr},
            {"Campo": "Casos analisados", "Valor": n_total},
            {"Campo": "Falhas / Avisos", "Valor": f"{n_fail} / {n_warn}"},
        ])
        meta_cols = ["Campo", "Valor"]
        decision_cols = ["Prumada", "Piso", "Secção [cm]", "material", "N_Ed_kN", "My_Ed_kNm", "Mz_Ed_kNm", "η_NMyMz", "Solução", "Estado"]
        inter_cols = ["Prumada", "Case", "N_Ed [kN]", "My_Ed [kNm]", "Mz_Ed [kNm]", "MRd_y [kNm]", "MRd_z [kNm]", "η_NMyMz", "Estado resistente"]
        mod_cols = ["Prumada", "case", "estado_global", "estado_resistente", "estado_corte", "estado_torcao", "estado_els", "estado_pormenorizacao", "decisao_tecnica"]
        gov_cols = ["Prumada", "Case", "Critério", "NEd [kN]", "My [kNm]", "Mz [kNm]", "Vy [kN]", "Vz [kN]", "T [kNm]"]
        perf_cols = ["Item", "Valor", "Nota"]
        page_word = "Página"

    tmp_path = path
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmp.name
        tmp.close()
    except Exception:
        pass
    doc = SimpleDocTemplate(tmp_path, pagesize=landscape(A4), rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    doc.title = "Columns EC2"
    story = [Paragraph("Columns EC2", styles["T68"]), Paragraph(subtitle, styles["B68"]), Spacer(1, 4*mm)]
    story.append(_rc3_pdf_table(meta, meta_cols, styles["C68"], max_rows=10, lang=lang))
    story.append(Paragraph(section_decision, styles["H68"]))
    story.append(_rc3_pdf_table(summ_d, decision_cols, styles["C68"], max_rows=100, lang=lang))
    if level in ["Relatório técnico", "Memória de cálculo", "Technical report", "Detailed calculation note"]:
        story.append(PageBreak())
        story.append(Paragraph(section_inter, styles["H68"]))
        story.append(_rc3_pdf_table(inter_d, inter_cols, styles["C68"], max_rows=100, lang=lang))
        story.append(Paragraph(section_module, styles["H68"]))
        story.append(_rc3_pdf_table(module_d, mod_cols, styles["C68"], max_rows=100, lang=lang))
    if level in ["Memória de cálculo", "Detailed calculation note"]:
        story.append(PageBreak())
        story.append(Paragraph(section_gov, styles["H68"]))
        story.append(_rc3_pdf_table(gov_d, gov_cols, styles["C68"], max_rows=120, lang=lang))
        story.append(PageBreak())
        story.append(Paragraph(section_perf, styles["H68"]))
        story.append(_rc3_pdf_table(perf_d, perf_cols, styles["C68"], max_rows=80, lang=lang))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Courier", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(12*mm, 7*mm, f"Columns EC2 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        canvas.drawRightString(285*mm, 7*mm, f"{page_word} {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    if tmp_path != path:
        try:
            shutil.move(tmp_path, path)
        except Exception:
            root, ext = os.path.splitext(path)
            alt = root + ("_new" if lang == LANG_EN else "_novo") + ext
            shutil.move(tmp_path, alt)

ColumnsEC2App._write_pdf = _write_pdf_rc3
_write_pdf_v69 = _write_pdf_rc3


def _export_pdf_report_rc3(self):
    lang = _rc3_lang(self)
    if getattr(self, "df_results", pd.DataFrame()) is None or self.df_results.empty:
        messagebox.showwarning("Warning" if lang == LANG_EN else "Aviso", "There are no results to export." if lang == LANG_EN else "Não há resultados para exportar.")
        return
    path = filedialog.asksaveasfilename(
        title="Export PDF report" if lang == LANG_EN else "Exportar relatório PDF",
        defaultextension=".pdf",
        filetypes=[("PDF", "*.pdf")],
    )
    if not path:
        return
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    try:
        self.status_var.set("Exporting PDF..." if lang == LANG_EN else "A exportar PDF...")
        self.progress_var.set(5)
        self.update_idletasks()
        tmp = str(Path(path).with_suffix(".tmp.pdf"))
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        self._write_pdf(tmp)
        try:
            if os.path.exists(path):
                os.remove(path)
            os.replace(tmp, path)
        except Exception:
            alt_suffix = "_new.pdf" if lang == LANG_EN else "_novo.pdf"
            alt = str(Path(path).with_name(Path(path).stem + alt_suffix))
            os.replace(tmp, alt)
            path = alt
        self.progress_var.set(100)
        self.status_var.set(("PDF exported: " if lang == LANG_EN else "PDF exportado: ") + path)
    except Exception as err:
        self.progress_var.set(0)
        messagebox.showerror("Error" if lang == LANG_EN else "Erro", ("PDF export failed.\n\n" if lang == LANG_EN else "Não foi possível exportar PDF.\n\n") + str(err))

ColumnsEC2App.export_pdf_report = _export_pdf_report_rc3

# Make the existing language selector button call the patched implementation, even if the
# old widget was created before this patch.
try:
    ColumnsEC2App.apply_language = _rc3_apply_language
except Exception:
    pass



# ============================================================
# ColumnsEC2 v0.9 RC4 — Technical EN-UK polish
# - Mode values use technical English: Design / Preliminary sizing.
# - Status/progress messages are translated live when EN-UK is active.
# - Quick notes and backend notes are language-aware.
# - Filter display values are translated without breaking internal status logic.
# ============================================================
APP_VERSION = "v0.9 RC4"

_RC4_UI_PT_EN = {
    "Pré-dimensionamento": "Preliminary sizing",
    "Pre-dimensionamento": "Preliminary sizing",
    "Dimensionamento": "Design",
    "Rigoroso": "Rigorous verification",
    "Modo": "Mode",
    "Estado:": "Status:",
    "Estado": "Status",
    "Todos": "All",
    "Aviso": "Warning",
    "Falha": "Failure",
    "Pré-dimensionado": "Preliminary sizing",
    "A calcular": "Calculating",
    "A calcular...": "Calculating...",
    "casos de envolvente": "governing cases",
    "casos member/case": "member/case pairs",
    "Cálculo concluído": "Calculation complete",
    "Cálculo v4 concluído": "Calculation complete",
    "Cálculo concluído:": "Calculation complete:",
    "Tabela carregada": "Table loaded",
    "linhas": "rows",
    "pares member/case": "member/case pairs",
    "sem dois nós": "without two end nodes",
    "Betão lido da coluna Material": "Concrete grade read from the Material column",
    "Norma:": "Standard:",
    "Motor:": "Engine:",
    "Modo:": "Mode:",
    "Verificação:": "Checks:",
    "Os esforços devem corresponder a combinações reais da análise.": "The design actions must correspond to actual analysis combinations.",
    "fluência/retracção": "creep/shrinkage",
    "esforço transverso": "shear",
    "torção": "torsion",
    "aderência": "bond",
    "avaliados quando disponíveis na API instalada": "checked where available in the installed API",
}
try:
    _V69_UI_MAP_PT_EN.update(_RC4_UI_PT_EN)
    _V69_UI_MAP_EN_PT.update({v: k for k, v in _RC4_UI_PT_EN.items()})
except Exception:
    pass

_RC4_STATUS_VALUE_EN_TO_PT = {
    "All": "Todos",
    "OK": "OK",
    "Warning": "Aviso",
    "Failure": "Falha",
    "Preliminary sizing": "Pré-dimensionado",
    "Preliminary": "Pré-dimensionado",
    "Check": "Verificar",
}


def _rc4_lang(app):
    try:
        return LANG_EN if str(app.var_language.get()).upper().startswith("EN") else LANG_PT
    except Exception:
        return LANG_PT


def _rc4_is_en(app):
    return _rc4_lang(app) == LANG_EN


def _v53_mode_to_internal(mode_value) -> str:
    """Language-safe conversion of the GUI mode label into the calculation mode."""
    s = str(mode_value or "").strip().lower()
    if any(k in s for k in ["pre", "pré", "sizing", "preliminary"]):
        return "pre_dimensionamento"
    return "dimensionamento"


def _v53_mode_to_label(mode_value) -> str:
    return "Pré-dimensionamento" if _v53_mode_to_internal(mode_value) == "pre_dimensionamento" else "Dimensionamento"


def _rc4_mode_label(app=None, lang=None):
    if lang is None:
        lang = _rc4_lang(app) if app is not None else LANG_PT
    internal = _v53_mode_to_internal(_v59_getvar(app, "var_calc_mode", "Dimensionamento") if "_v59_getvar" in globals() else getattr(app, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get())
    if lang == LANG_EN:
        return "Preliminary sizing" if internal == "pre_dimensionamento" else "Design"
    return "Pré-dimensionamento" if internal == "pre_dimensionamento" else "Dimensionamento"


def _rc4_translate_status_text(text, lang):
    if lang != LANG_EN:
        return str(text)
    s = str(text)
    # Full common messages first.
    full_map = {
        "Cole ou importe a tabela de esforços.": "Paste or import the design-action table.",
        "A exportar PDF...": "Exporting PDF...",
        "A exportar Excel...": "Exporting Excel...",
        "Falha na análise.": "Calculation failed.",
        "Filtros removidos.": "Filters cleared.",
    }
    if s in full_map:
        return full_map[s]
    repl = [
        ("A calcular...", "Calculating..."),
        ("Análise em curso...", "Calculation in progress..."),
        ("Análise v4 em curso...", "Calculation in progress..."),
        ("casos de envolvente", "governing cases"),
        ("casos member/case", "member/case pairs"),
        ("Cálculo v4 concluído", "Calculation complete"),
        ("Cálculo concluído", "Calculation complete"),
        ("Tabela carregada", "Table loaded"),
        ("linhas", "rows"),
        ("pares member/case", "member/case pairs"),
        ("sem dois nós", "without two end nodes"),
        ("Betão lido da coluna Material", "Concrete grade read from the Material column"),
        ("Resultados exportados para", "Results exported to"),
        ("Excel exportado", "Excel exported"),
        ("PDF exportado", "PDF exported"),
        ("DXF exportado", "DXF exported"),
        ("Filtros aplicados", "Filters applied"),
        ("linhas visíveis", "visible rows"),
        ("Aviso", "Warning"),
        ("Falha", "Failure"),
        ("Prumada", "Column line"),
        ("Piso", "Storey"),
        ("Não há resultados para exportar", "There are no results to export"),
    ]
    for a, b in repl:
        s = s.replace(a, b)
    return s


def _rc4_install_status_translator(app):
    try:
        if getattr(app, "_rc4_status_translator_installed", False):
            return
        app._rc4_status_translator_installed = True
        app._rc4_status_translating = False
        def _cb(*_):
            try:
                if getattr(app, "_rc4_status_translating", False):
                    return
                if not _rc4_is_en(app):
                    return
                old = app.status_var.get()
                new = _rc4_translate_status_text(old, LANG_EN)
                if new != old:
                    app._rc4_status_translating = True
                    app.status_var.set(new)
                    app._rc4_status_translating = False
            except Exception:
                try:
                    app._rc4_status_translating = False
                except Exception:
                    pass
        app.status_var.trace_add("write", _cb)
    except Exception:
        pass


def _rc4_quick_notes(app=None):
    lang = _rc4_lang(app) if app is not None else LANG_PT
    try:
        b = _v59_get_backend(app)
    except Exception:
        b = globals().get("BACKEND_EC2_PT_2010", "pt2010")
    mode = _rc4_mode_label(app, lang)
    try:
        norm = _backend_display_v59(b) if "_backend_display_v59" in globals() else (_v59_norm_reference(app) if "_v59_norm_reference" in globals() else "Eurocode 2")
    except Exception:
        norm = "Eurocode 2"
    if lang == LANG_EN:
        if b == globals().get("BACKEND_EC2_PT_2010", "pt2010"):
            return (
                f"Standard: {norm}\n"
                f"Mode: {mode}\n"
                "Checks: N-My-Mz interaction, slenderness, second-order effects, shear, torsion, SLS and constructive detailing. "
                "The design actions must correspond to actual analysis combinations."
            )
        if b == globals().get("BACKEND_SC_EC2_2004", "ec2_2004"):
            return (
                "Standard: Eurocode 2:2004\n"
                "Engine: structuralcodes. Materials, creep/shrinkage, N-My-Mz interaction, shear and crack-control routines are checked where available in the installed API."
            )
        if b == globals().get("BACKEND_SC_EC2_2023", "ec2_2023"):
            return (
                "Standard: Eurocode 2:2023\n"
                "Engine: structuralcodes. Materials, creep/shrinkage, N-My-Mz interaction, crack control and deflection routines are checked where available in the installed API."
            )
        return (
            "Standard: fib Model Code 2010\n"
            "Engine: structuralcodes. Materials, creep/shrinkage, N-My-Mz interaction, shear, torsion, SLS and bond routines are checked where available in the installed API."
        )
    # Portuguese original, but normalised.
    if b == globals().get("BACKEND_EC2_PT_2010", "pt2010"):
        return (
            f"Norma: {norm}\n"
            f"Modo: {mode}\n"
            "Verificação: N-My-Mz, esbelteza, 2.ª ordem, V, T, ELS e pormenorização construtiva. "
            "Os esforços devem corresponder a combinações reais da análise."
        )
    if b == globals().get("BACKEND_SC_EC2_2004", "ec2_2004"):
        return (
            "Norma: Eurocode 2:2004\n"
            "Motor: structuralcodes. Materiais, fluência/retracção, N-My-Mz, V e fendilhação são avaliados quando disponíveis na API instalada."
        )
    if b == globals().get("BACKEND_SC_EC2_2023", "ec2_2023"):
        return (
            "Norma: Eurocode 2:2023\n"
            "Motor: structuralcodes. Materiais, fluência/retracção, N-My-Mz, fendilhação e deformação são avaliados quando disponíveis na API instalada."
        )
    return (
        "Norma: fib Model Code 2010\n"
        "Motor: structuralcodes. Materiais, fluência/retracção, N-My-Mz, esforço transverso, torção, ELS e aderência são avaliados quando disponíveis na API instalada."
    )


def _v60_quick_notes(app=None) -> str:
    return _rc4_quick_notes(app)


def _v59_update_quick_notes(app):
    try:
        if hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(_rc4_quick_notes(app))
    except Exception:
        pass


def _rc3_backend_quick_note(app, lang):
    # Keep compatibility with the RC3 language walker.
    return _rc4_quick_notes(app)


def _rc4_set_mode_combobox(app, lang):
    try:
        cur_internal = _v53_mode_to_internal(app.var_calc_mode.get())
        if lang == LANG_EN:
            values = ["Preliminary sizing", "Design"]
            app.var_calc_mode.set("Preliminary sizing" if cur_internal == "pre_dimensionamento" else "Design")
        else:
            values = ["Pré-dimensionamento", "Dimensionamento"]
            app.var_calc_mode.set("Pré-dimensionamento" if cur_internal == "pre_dimensionamento" else "Dimensionamento")
        for w in _rc3_walk_widgets(app):
            try:
                if isinstance(w, ttk.Combobox) and str(w.cget("textvariable")) == str(app.var_calc_mode):
                    w.configure(values=values, state="readonly", width=20)
            except Exception:
                pass
    except Exception:
        pass


def _rc4_set_filter_comboboxes(app, lang):
    try:
        for w in _rc3_walk_widgets(app):
            try:
                tv = str(w.cget("textvariable"))
                if hasattr(app, "var_filter_status") and tv == str(app.var_filter_status):
                    if lang == LANG_EN:
                        old = _RC4_STATUS_VALUE_EN_TO_PT.get(app.var_filter_status.get(), app.var_filter_status.get())
                        m = {"Todos": "All", "OK": "OK", "Aviso": "Warning", "Falha": "Failure", "Pré-dimensionado": "Preliminary sizing"}
                        w.configure(values=["All", "OK", "Warning", "Failure", "Preliminary sizing"], state="readonly")
                        app.var_filter_status.set(m.get(old, "All"))
                    else:
                        old = _RC4_STATUS_VALUE_EN_TO_PT.get(app.var_filter_status.get(), app.var_filter_status.get())
                        w.configure(values=["Todos", "OK", "Aviso", "Falha", "Pré-dimensionado"], state="readonly")
                        app.var_filter_status.set(old if old in ["Todos", "OK", "Aviso", "Falha", "Pré-dimensionado"] else "Todos")
            except Exception:
                pass
    except Exception:
        pass


def _rc4_refresh_long_labels(app, lang):
    # Some labels are content strings rather than keys; force technical EN-UK replacements.
    try:
        for w in _rc3_walk_widgets(app):
            try:
                txt = str(w.cget("text"))
            except Exception:
                continue
            if lang == LANG_EN:
                if "Standard:" in txt or "Norma:" in txt:
                    try:
                        if "Engine:" in txt or "Motor:" in txt:
                            w.configure(text=_rc4_quick_notes(app))
                    except Exception:
                        pass
                if "Análise e dimensionamento" in txt or "Reinforced concrete column analysis" in txt:
                    w.configure(text="Reinforced concrete column analysis and design")
                if "Dimensionamento de pilares" in txt or "Reinforced concrete column design:" in txt:
                    w.configure(text="Reinforced concrete column design: ULS, SLS, N-My-Mz interaction, detailing and technical reports.")
            else:
                if "Standard:" in txt or "Engine:" in txt:
                    try:
                        w.configure(text=_rc4_quick_notes(app))
                    except Exception:
                        pass
    except Exception:
        pass


def _rc4_translate_widget_text(app, lang):
    # General recursive label translation.
    try:
        for w in _rc3_walk_widgets(app):
            try:
                txt = str(w.cget("text"))
            except Exception:
                continue
            if lang == LANG_EN:
                new = _v69_tr_text(txt, LANG_EN)
                new = _rc4_translate_status_text(new, LANG_EN)
            else:
                new = _V69_UI_MAP_EN_PT.get(txt, txt)
            if new != txt:
                try:
                    w.configure(text=new)
                except Exception:
                    pass
    except Exception:
        pass
    # Notebook tabs.
    try:
        for nb in [w for w in _rc3_walk_widgets(app) if isinstance(w, ttk.Notebook)]:
            for tab_id in nb.tabs():
                txt = nb.tab(tab_id, "text")
                if lang == LANG_EN:
                    nb.tab(tab_id, text=_v69_tr_text(txt, LANG_EN))
                else:
                    nb.tab(tab_id, text=_V69_UI_MAP_EN_PT.get(txt, txt))
    except Exception:
        pass


_old_rc3_apply_language_for_rc4 = globals().get("_rc3_apply_language", None)

def _rc4_apply_language(self):
    lang = _rc4_lang(self)
    try:
        if callable(_old_rc3_apply_language_for_rc4):
            _old_rc3_apply_language_for_rc4(self)
    except Exception:
        pass
    try:
        self.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if lang == LANG_EN else APP_TITLE)
    except Exception:
        pass
    _rc4_install_status_translator(self)
    _rc4_translate_widget_text(self, lang)
    _rc4_set_mode_combobox(self, lang)
    _rc4_set_filter_comboboxes(self, lang)
    _rc4_refresh_long_labels(self, lang)
    try:
        if hasattr(self, "quick_notes_var"):
            self.quick_notes_var.set(_rc4_quick_notes(self))
    except Exception:
        pass
    try:
        _v69_refresh_instructions(self)
    except Exception:
        pass
    try:
        self.status_var.set("Language set to English (UK)." if lang == LANG_EN else "Idioma definido para Português.")
    except Exception:
        pass

ColumnsEC2App.apply_language = _rc4_apply_language
try:
    _rc3_apply_language = _rc4_apply_language
except Exception:
    pass

_old_apply_filters_rc4 = getattr(ColumnsEC2App, "apply_filters", None)
def _apply_filters_rc4(self):
    # Map English filter display values back to the internal Portuguese status values before filtering.
    try:
        if hasattr(self, "var_filter_status"):
            shown = self.var_filter_status.get()
            internal = _RC4_STATUS_VALUE_EN_TO_PT.get(shown, shown)
            if shown != internal:
                self.var_filter_status.set(internal)
                try:
                    if callable(_old_apply_filters_rc4):
                        _old_apply_filters_rc4(self)
                finally:
                    self.var_filter_status.set(shown)
                return
    except Exception:
        pass
    if callable(_old_apply_filters_rc4):
        return _old_apply_filters_rc4(self)
ColumnsEC2App.apply_filters = _apply_filters_rc4

# Language-aware wrappers for calculation start/end status where older routines still emit PT text.
_old_run_design_rc4 = getattr(ColumnsEC2App, "run_design", None)
def _run_design_rc4(self):
    _rc4_install_status_translator(self)
    try:
        if hasattr(self, "quick_notes_var"):
            self.quick_notes_var.set(_rc4_quick_notes(self))
    except Exception:
        pass
    if callable(_old_run_design_rc4):
        return _old_run_design_rc4(self)
ColumnsEC2App.run_design = _run_design_rc4

# Initial title/language application.
def _v091_apply_language_title(app):
    try:
        app.apply_language()
    except Exception:
        try:
            app.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if _rc4_is_en(app) else APP_TITLE)
        except Exception:
            pass


# ============================================================
# ColumnsEC2 v0.9 RC5 — Complete EN-UK interface pass
# - Strong live localisation pass for all visible widgets.
# - Mode values remain technical: Design / Preliminary sizing.
# - Dynamic status/progress and quick notes are forced to EN-UK when selected.
# - Existing PT/internal status values remain unchanged for calculations.
# ============================================================
APP_VERSION = "v0.9 RC5"

_RC5_EXACT_PT_EN = {
    "Pré-dimensionamento": "Preliminary sizing",
    "Pre-dimensionamento": "Preliminary sizing",
    "Dimensionamento": "Design",
    "Rigoroso": "Rigorous verification",
    "Estado:": "Status:",
    "Estado": "Status",
    "Todos": "All",
    "Aviso": "Warning",
    "Falha": "Failure",
    "Verificar": "Check",
    "Não avaliado": "Not assessed",
    "Não conforme": "Not compliant",
    "Pré-dimensionado": "Preliminary sizing",
    "Notas rápidas": "Quick notes",
    "9. Norma / motor de cálculo": "9. Design standard / calculation engine",
    "Norma / motor de cálculo": "Design standard / calculation engine",
    "Fluência": "Creep",
    "Fluência / φef": "Creep / φef",
    "Calcular φef automaticamente": "Calculate φef automatically",
    "Humidade relativa RH [%]": "Relative humidity RH [%]",
    "Idade do betão t0 [dias]": "Concrete age t0 [days]",
    "t0 [dias]": "t0 [days]",
    "h0 e φef são calculados automaticamente.": "h0 and φef are calculated automatically.",
    "h0=0 ⇒ estimado pela secção.": "h0 = 0 ⇒ estimated from the section.",
    "Classe de Aço": "Steel grade",
    "Betão": "Concrete",
    "lido da tabela (coluna Material)": "read from table (Material column)",
    "lido da coluna Material": "read from the Material column",
    "4. Cálculo e exportação": "4. Design and export",
    "Calcular": "Design/check",
    "Relatório .pdf": "PDF report",
    "Exportar .xlsx": "Export .xlsx",
    "Abrir repositório": "Open repository",
    "Reduzir para casos governantes": "Reduce to governing cases",
    "Resumo por membro": "Member summary",
    "Combinação ELS": "SLS combination",
    "em branco = ELS simplificado por defeito": "blank = simplified SLS check",
    "Linguagem": "Language",
    "Aplicar": "Apply",
    "Limpar": "Clear",
    "Adicionar linha": "Add row",
    "Remover linha": "Remove row",
    "Interpretar texto": "Parse text",
    "Ler grelha": "Read grid",
    "Texto colado": "Pasted text",
    "Tabela editável reconhecida": "Recognised editable table",
    "A exportar PDF...": "Exporting PDF...",
    "A exportar Excel...": "Exporting Excel...",
    "A exportar DXF...": "Exporting DXF...",
    "Sem resultados.": "No results.",
}

_RC5_FRAGMENT_PT_EN = [
    ("A calcular...", "Calculating..."),
    ("A calcular", "Calculating"),
    ("Análise em curso", "Calculation in progress"),
    ("Análise v4 em curso", "Calculation in progress"),
    ("Cálculo concluído", "Calculation complete"),
    ("Cálculo v4 concluído", "Calculation complete"),
    ("Tabela carregada", "Table loaded"),
    ("Resultados exportados para", "Results exported to"),
    ("Excel exportado", "Excel exported"),
    ("PDF exportado", "PDF exported"),
    ("DXF exportado", "DXF exported"),
    ("Falha na análise", "Calculation failed"),
    ("Não foi possível exportar PDF", "PDF export failed"),
    ("Não há resultados para exportar", "There are no results to export"),
    ("casos de envolvente", "governing cases"),
    ("casos member/case", "member/case pairs"),
    ("casos analisados", "analysed cases"),
    ("Casos analisados", "Analysed cases"),
    ("Casos de cálculo", "Design cases"),
    ("falhas bloqueantes", "blocking failures"),
    ("Falhas bloqueantes", "Blocking failures"),
    ("falhas", "failures"),
    ("Falhas", "Failures"),
    ("avisos", "warnings"),
    ("Avisos", "Warnings"),
    ("prumadas", "column lines"),
    ("Prumadas", "Column lines"),
    ("prumada", "column line"),
    ("Prumada", "Column line"),
    ("membros", "members"),
    ("Membros", "Members"),
    ("membro", "member"),
    ("Membro", "Member"),
    ("linhas visíveis", "visible rows"),
    ("linhas", "rows"),
    ("sem dois nós", "without two end nodes"),
    ("dois nós", "two end nodes"),
    ("Betão lido da coluna Material", "Concrete grade read from the Material column"),
    ("lido da coluna Material", "read from the Material column"),
    ("Norma:", "Standard:"),
    ("Motor:", "Engine:"),
    ("Modo:", "Mode:"),
    ("Verificação:", "Checks:"),
    ("Dimensionamento", "Design"),
    ("Pré-dimensionamento", "Preliminary sizing"),
    ("Não indicada", "Not specified"),
    ("não indicada", "not specified"),
    ("verificação simplificada", "simplified check"),
    ("combinação", "combination"),
    ("Combinação", "Combination"),
    ("esforço transverso", "shear"),
    ("Esforço transverso", "Shear"),
    ("torção", "torsion"),
    ("Torção", "Torsion"),
    ("fluência/retracção", "creep/shrinkage"),
    ("fendilhação", "crack control"),
    ("deformação", "deflection"),
    ("aderência", "bond"),
    ("avaliados quando disponíveis na API instalada", "checked where available in the installed API"),
    ("avaliadas quando disponíveis na API instalada", "checked where available in the installed API"),
    ("Os esforços devem corresponder a combinações reais da análise.", "The design actions must correspond to actual analysis combinations."),
    ("ELS", "SLS"),
    ("2.ª ordem", "second-order effects"),
    ("pormenorização construtiva", "constructive detailing"),
    ("Pormenorização", "Detailing"),
    ("armadura", "reinforcement"),
    ("Armadura", "Reinforcement"),
    ("estribos", "ties"),
    ("Estribos", "Ties"),
    ("Piso", "Storey"),
    ("Secção", "Section"),
    ("Solução", "Solution"),
]

try:
    _V69_UI_MAP_PT_EN.update(_RC5_EXACT_PT_EN)
    _V69_UI_MAP_EN_PT.update({v: k for k, v in _RC5_EXACT_PT_EN.items()})
    _V69_CELL_MAP_PT_EN.update(_RC5_EXACT_PT_EN)
except Exception:
    pass


def _rc5_lang(app):
    try:
        return LANG_EN if str(app.var_language.get()).upper().startswith("EN") else LANG_PT
    except Exception:
        return LANG_PT


def _rc5_is_en(app):
    return _rc5_lang(app) == LANG_EN


def _rc5_to_en_text(value):
    s = str(value)
    if not s:
        return s
    if s in _RC5_EXACT_PT_EN:
        return _RC5_EXACT_PT_EN[s]
    try:
        s = _v69_tr_text(s, LANG_EN)
    except Exception:
        pass
    if s in _RC5_EXACT_PT_EN:
        s = _RC5_EXACT_PT_EN[s]
    # Ordered fragment replacements, longest first to avoid partial clashes.
    for old, new in sorted(_RC5_FRAGMENT_PT_EN, key=lambda x: len(x[0]), reverse=True):
        s = s.replace(old, new)
    return s


def _rc5_walk_widgets(w):
    yield w
    try:
        children = w.winfo_children()
    except Exception:
        children = []
    for c in children:
        yield from _rc5_walk_widgets(c)


def _rc5_mode_internal(value):
    try:
        return _v53_mode_to_internal(value)
    except Exception:
        s = str(value or "").lower()
        return "pre_dimensionamento" if any(k in s for k in ["pre", "pré", "sizing"]) else "dimensionamento"


def _rc5_mode_display(app, lang=None):
    if lang is None:
        lang = _rc5_lang(app)
    cur = _rc5_mode_internal(getattr(app, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get())
    if lang == LANG_EN:
        return "Preliminary sizing" if cur == "pre_dimensionamento" else "Design"
    return "Pré-dimensionamento" if cur == "pre_dimensionamento" else "Dimensionamento"


def _rc5_status_display_to_internal(value):
    return {
        "All": "Todos",
        "Warning": "Aviso",
        "Failure": "Falha",
        "Preliminary sizing": "Pré-dimensionado",
        "Preliminary": "Pré-dimensionado",
        "Check": "Verificar",
        "Not assessed": "Não avaliado",
        "Not compliant": "Não conforme",
    }.get(str(value), str(value))


def _rc5_backend_key(app):
    try:
        return _v59_backend_key(app)
    except Exception:
        try:
            return _v59_get_backend(app)
        except Exception:
            return globals().get("BACKEND_EC2_PT_2010", "pt2010")


def _rc5_backend_standard_en(app):
    b = _rc5_backend_key(app)
    if b == globals().get("BACKEND_EC2_PT_2010", "pt2010"):
        return "NP EN 1992-1-1:2010 + AC:2012 + A1:2019 (Portugal)"
    if b == globals().get("BACKEND_SC_EC2_2004", "ec2_2004"):
        return "Eurocode 2:2004"
    if b == globals().get("BACKEND_SC_EC2_2023", "ec2_2023"):
        return "Eurocode 2:2023"
    return "fib Model Code 2010"


def _rc5_quick_notes_en(app):
    b = _rc5_backend_key(app)
    mode = _rc5_mode_display(app, LANG_EN)
    std = _rc5_backend_standard_en(app)
    if b == globals().get("BACKEND_EC2_PT_2010", "pt2010"):
        return (
            f"Standard: {std}\n"
            f"Engine: internal ColumnsEC2 design engine\n"
            f"Mode: {mode}\n"
            "Checks: N-My-Mz interaction, slenderness, second-order effects, shear, torsion, SLS and constructive detailing. "
            "The design actions must correspond to actual analysis combinations."
        )
    if b == globals().get("BACKEND_SC_EC2_2004", "ec2_2004"):
        return (
            f"Standard: {std}\n"
            "Engine: structuralcodes\n"
            f"Mode: {mode}\n"
            "Scope: materials, creep/shrinkage and N-My-Mz interaction are checked where available in the installed API. "
            "Unavailable modules are reported as not assessed."
        )
    if b == globals().get("BACKEND_SC_EC2_2023", "ec2_2023"):
        return (
            f"Standard: {std}\n"
            "Engine: structuralcodes\n"
            f"Mode: {mode}\n"
            "Scope: materials, creep/shrinkage, SLS-related routines and N-My-Mz interaction are checked where available in the installed API. "
            "Unavailable modules are reported as not assessed."
        )
    return (
        f"Standard: {std}\n"
        "Engine: structuralcodes\n"
        f"Mode: {mode}\n"
        "Scope: material, time-dependent effects, N-My-Mz interaction, shear, torsion, SLS and bond routines are checked where available in the installed API. "
        "Unavailable modules are reported as not assessed."
    )


def _rc5_translate_status_var(app):
    if not _rc5_is_en(app):
        return
    try:
        old = app.status_var.get()
        new = _rc5_to_en_text(old)
        if new != old:
            app.status_var.set(new)
    except Exception:
        pass


def _rc5_translate_quick_notes(app):
    if not _rc5_is_en(app):
        return
    try:
        if hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(_rc5_quick_notes_en(app))
    except Exception:
        pass


def _rc5_translate_widget_tree(app):
    lang = _rc5_lang(app)
    try:
        app.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if lang == LANG_EN else APP_TITLE)
    except Exception:
        pass
    for w in list(_rc5_walk_widgets(app)):
        # text labels and labelframes
        try:
            txt = str(w.cget("text"))
            new = _rc5_to_en_text(txt) if lang == LANG_EN else _V69_UI_MAP_EN_PT.get(txt, txt)
            if new != txt:
                w.configure(text=new)
        except Exception:
            pass
        # combobox values / current values
        try:
            if isinstance(w, ttk.Combobox):
                tv = str(w.cget("textvariable"))
                if hasattr(app, "var_calc_mode") and tv == str(app.var_calc_mode):
                    if lang == LANG_EN:
                        w.configure(values=["Preliminary sizing", "Design"], state="readonly", width=20)
                        desired = _rc5_mode_display(app, LANG_EN)
                        if app.var_calc_mode.get() != desired:
                            app.var_calc_mode.set(desired)
                    else:
                        w.configure(values=["Pré-dimensionamento", "Dimensionamento"], state="readonly", width=20)
                        desired = _rc5_mode_display(app, LANG_PT)
                        if app.var_calc_mode.get() != desired:
                            app.var_calc_mode.set(desired)
                if hasattr(app, "var_filter_status") and tv == str(app.var_filter_status):
                    if lang == LANG_EN:
                        w.configure(values=["All", "OK", "Warning", "Failure", "Preliminary sizing"], state="readonly")
                        cur = app.var_filter_status.get()
                        cur_internal = _rc5_status_display_to_internal(cur)
                        m = {"Todos":"All", "OK":"OK", "Aviso":"Warning", "Falha":"Failure", "Pré-dimensionado":"Preliminary sizing"}
                        app.var_filter_status.set(m.get(cur_internal, cur if cur in m.values() else "All"))
                    else:
                        cur = _rc5_status_display_to_internal(app.var_filter_status.get())
                        w.configure(values=["Todos", "OK", "Aviso", "Falha", "Pré-dimensionado"], state="readonly")
                        app.var_filter_status.set(cur if cur in ["Todos", "OK", "Aviso", "Falha", "Pré-dimensionado"] else "Todos")
        except Exception:
            pass
    # Notebook tabs
    try:
        for nb in [w for w in _rc5_walk_widgets(app) if isinstance(w, ttk.Notebook)]:
            for tab_id in nb.tabs():
                txt = nb.tab(tab_id, "text")
                new = _rc5_to_en_text(txt) if lang == LANG_EN else _V69_UI_MAP_EN_PT.get(txt, txt)
                if new != txt:
                    nb.tab(tab_id, text=new)
    except Exception:
        pass
    if lang == LANG_EN:
        _rc5_translate_status_var(app)
        _rc5_translate_quick_notes(app)


def _rc5_install_live_localisation(app):
    if getattr(app, "_rc5_live_localisation_installed", False):
        return
    app._rc5_live_localisation_installed = True
    app._rc5_localising = False
    try:
        def _trace_status(*_):
            if getattr(app, "_rc5_localising", False):
                return
            if not _rc5_is_en(app):
                return
            try:
                app._rc5_localising = True
                _rc5_translate_status_var(app)
            finally:
                app._rc5_localising = False
        app.status_var.trace_add("write", _trace_status)
    except Exception:
        pass
    try:
        def _trace_language(*_):
            try:
                _rc5_translate_widget_tree(app)
            except Exception:
                pass
        app.var_language.trace_add("write", _trace_language)
    except Exception:
        pass
    # Poller catches labels/status text changed by older callbacks after the language pass.
    def _poll():
        try:
            if _rc5_is_en(app):
                _rc5_translate_widget_tree(app)
        except Exception:
            pass
        try:
            app.after(350, _poll)
        except Exception:
            pass
    try:
        app.after(150, _poll)
    except Exception:
        pass


# Replace quick-note updaters with a language-aware implementation.
def _v59_update_quick_notes(app):
    try:
        if _rc5_is_en(app):
            if hasattr(app, "quick_notes_var"):
                app.quick_notes_var.set(_rc5_quick_notes_en(app))
            return
    except Exception:
        pass
    try:
        if hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(_rc4_quick_notes(app) if "_rc4_quick_notes" in globals() else "")
    except Exception:
        pass


def _v60_quick_notes(app=None) -> str:
    try:
        return _rc5_quick_notes_en(app) if app is not None and _rc5_is_en(app) else (_rc4_quick_notes(app) if "_rc4_quick_notes" in globals() else "")
    except Exception:
        return ""


_old_rc4_apply_language_for_rc5 = getattr(ColumnsEC2App, "apply_language", None)
def _rc5_apply_language(self):
    try:
        if callable(_old_rc4_apply_language_for_rc5):
            _old_rc4_apply_language_for_rc5(self)
    except Exception:
        pass
    _rc5_install_live_localisation(self)
    _rc5_translate_widget_tree(self)
    try:
        self.status_var.set("Language set to English (UK)." if _rc5_is_en(self) else "Idioma definido para Português.")
    except Exception:
        pass

ColumnsEC2App.apply_language = _rc5_apply_language
try:
    _rc3_apply_language = _rc5_apply_language
except Exception:
    pass


_old_run_design_rc5_base = getattr(ColumnsEC2App, "run_design", None)
def _run_design_rc5(self):
    _rc5_install_live_localisation(self)
    # Convert English GUI display value to a value accepted by legacy routines only if needed.
    # The old routines can parse both; after they start, the live localiser restores EN labels.
    if callable(_old_run_design_rc5_base):
        result = _old_run_design_rc5_base(self)
    else:
        result = None
    try:
        if _rc5_is_en(self):
            _rc5_translate_widget_tree(self)
            _rc5_translate_status_var(self)
    except Exception:
        pass
    return result

ColumnsEC2App.run_design = _run_design_rc5


_old_export_excel_rc5_base = getattr(ColumnsEC2App, "export_excel", None)
def _export_excel_rc5(self):
    _rc5_install_live_localisation(self)
    return _old_export_excel_rc5_base(self) if callable(_old_export_excel_rc5_base) else None
ColumnsEC2App.export_excel = _export_excel_rc5

_old_export_pdf_rc5_base = getattr(ColumnsEC2App, "export_pdf_report", None)
def _export_pdf_report_rc5(self):
    _rc5_install_live_localisation(self)
    return _old_export_pdf_rc5_base(self) if callable(_old_export_pdf_rc5_base) else None
ColumnsEC2App.export_pdf_report = _export_pdf_report_rc5

_old_export_dxf_rc5_base = getattr(ColumnsEC2App, "export_dxf", None)
def _export_dxf_rc5(self):
    _rc5_install_live_localisation(self)
    return _old_export_dxf_rc5_base(self) if callable(_old_export_dxf_rc5_base) else None
ColumnsEC2App.export_dxf = _export_dxf_rc5


# Initial title/language application.
def _v091_apply_language_title(app):
    try:
        _rc5_install_live_localisation(app)
        app.apply_language()
        _rc5_translate_widget_tree(app)
    except Exception:
        try:
            app.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if _rc5_is_en(app) else APP_TITLE)
        except Exception:
            pass


# RC5 additional technical vocabulary used by legacy status/notes.
try:
    _RC5_FRAGMENT_PT_EN.extend([
        ("esbelteza", "slenderness"),
        ("Esbelteza", "Slenderness"),
        ("construtiva", "constructive"),
        ("construtivo", "constructive"),
        ("Cálculo completo pelo motor interno", "Full calculation by the internal engine"),
        ("motor interno", "internal engine"),
        ("sem fórmulas internas", "without internal formula fallback"),
        ("Só são calculadas verificações expostas pela API local", "Only checks exposed by the local API are calculated"),
        ("não avaliados", "not assessed"),
        ("não avaliadas", "not assessed"),
        ("disponíveis", "available"),
        ("disponível", "available"),
        ("secções", "sections"),
        ("materiais", "materials"),
        ("Materiais", "Materials"),
        ("fórmulas internas", "internal formulae"),
    ])
except Exception:
    pass


# RC5 final translator override: apply phrase fragments before legacy single-word mappings.
def _rc5_to_en_text(value):
    s = str(value)
    if not s:
        return s
    if s in _RC5_EXACT_PT_EN:
        return _RC5_EXACT_PT_EN[s]
    for old, new in sorted(_RC5_FRAGMENT_PT_EN, key=lambda x: len(x[0]), reverse=True):
        s = s.replace(old, new)
    try:
        s = _v69_tr_text(s, LANG_EN)
    except Exception:
        pass
    if s in _RC5_EXACT_PT_EN:
        s = _RC5_EXACT_PT_EN[s]
    return s.replace(" e ", " and ").replace(" SLS e ", " SLS and ").replace("V, T,", "shear, torsion,")



# ============================================================
# ColumnsEC2 v0.9 RC6 — EN-UK technical localisation and
# preliminary-sizing workflow correction
# ============================================================
APP_VERSION = "v0.9 RC6"

_RC6_ACTIVE_APP = None

_RC6_EXACT_PT_EN = {
    "Instruções de utilização and tabela tipo": "User instructions and input table format",
    "Estratégia de reinforcement": "Reinforcement strategy",
    "Estratégia de armadura": "Reinforcement strategy",
    "Estratégia armadura": "Reinforcement strategy",
    "Critério de escolha": "Selection criterion",
    "Económica": "Minimum reinforcement",
    "Equilibrada": "Balanced",
    "Robusta": "Robust",
    "Económica — menor área de aço que verifica": "Minimum reinforcement — lowest compliant steel area",
    "Equilibrada — η_NMyMz alvo 0.70–0.85": "Balanced — target η_NMyMz = 0.70–0.85",
    "Robusta — menor η_NMyMz": "Robust — lowest η_NMyMz",
    "Económica: menor As; Equilibrada: η≈0.80; Robusta: menor η.": "Minimum reinforcement: lowest compliant As; Balanced: target η≈0.80; Robust: lowest η.",
    "Diagnóstico and auditoria": "Diagnostics and audit",
    "Diagnóstico e auditoria": "Diagnostics and audit",
    "Diagnóstico structuralcodes": "structuralcodes diagnostics",
    "Tentativas de correcção": "Correction trials",
    "As tentativas detalhadas são exportadas apenas no ficheiro .xlsx.": "Detailed correction-trial logs are written to the XLSX workbook only.",
    "Critérios da estratégia equilibrada": "Balanced-strategy criteria",
    "Aplicado apenas quando a estratégia seleccionada é Equilibrada.": "Only applies when the Balanced strategy is selected.",
    "η alvo": "Target η",
    "η mínimo": "Minimum η",
    "η máximo": "Maximum η",
    "Excesso máx. As": "Maximum As excess",
    "Nível de detalhe": "Report level",
    "Relatório técnico": "Technical report",
    "Resumo executivo": "Executive summary",
    "Memória de cálculo": "Detailed calculation note",
    "Classe desenv.": "Exposure class",
    "t_ref / t0 [dias]": "t_ref / t0 [days]",
    "Concrete age t0 [days]": "Concrete age t0 [days]",
    "Idade betão t0 [dias]": "Concrete age t0 [days]",
    "Betão": "Concrete",
    "betão": "concrete grade",
    "lido da tabela (coluna Material)": "read from the Material column",
    "Tabela editável reconhecida": "Recognised editable table",
    "tabela editável": "editable grid",
    "Falhas bloqueantes detectadas": "Blocking design issues detected",
    "Foram detectadas falhas bloqueantes.": "Blocking design issues were detected.",
    "Pretende gerar propostas de correcção?": "Generate correction proposals?",
    "Correcção iterativa": "Iterative correction",
    "Correcção interactiva": "Interactive correction",
    "Verificação": "Check",
    "Não foram detectadas falhas bloqueantes.": "No blocking design issues were detected.",
    "Não há falhas bloqueantes a corrigir.": "There are no blocking design issues to correct.",
    "Pré-dimensionamento": "Preliminary sizing",
    "Dimensionamento": "Design",
    "Falha": "Failure",
    "Aviso": "Warning",
    "Bloqueante": "Blocking",
    "bloqueantes": "blocking issues",
    "avisos": "warnings",
    "prumadas": "column lines",
    "Prumadas": "Column lines",
    "membros": "members",
    "Membros": "Members",
    "casos": "cases",
    "Casos": "Cases",
}

_RC6_FRAGMENT_PT_EN = [
    ("Estratégia de reinforcement", "Reinforcement strategy"),
    ("Estratégia de armadura", "Reinforcement strategy"),
    ("Critérios da estratégia equilibrada", "Balanced-strategy criteria"),
    ("Critério de escolha", "Selection criterion"),
    ("Económica: menor As; Equilibrada: η≈0.80; Robusta: menor η.", "Minimum reinforcement: lowest compliant As; Balanced: target η≈0.80; Robust: lowest η."),
    ("Económica — menor área de aço que verifica", "Minimum reinforcement — lowest compliant steel area"),
    ("Equilibrada — η_NMyMz alvo 0.70–0.85", "Balanced — target η_NMyMz = 0.70–0.85"),
    ("Robusta — menor η_NMyMz", "Robust — lowest η_NMyMz"),
    ("pre-dimensionamento", "preliminary sizing"),
    ("pré-dimensionamento", "preliminary sizing"),
    ("Pré-dimensionamento", "Preliminary sizing"),
    ("Dimensionamento", "Design"),
    ("Diagnóstico and auditoria", "Diagnostics and audit"),
    ("Diagnóstico e auditoria", "Diagnostics and audit"),
    ("Diagnóstico structuralcodes", "structuralcodes diagnostics"),
    ("Tentativas de correcção", "Correction trials"),
    ("As tentativas detalhadas são exportadas apenas no ficheiro .xlsx.", "Detailed correction-trial logs are written to the XLSX workbook only."),
    ("Nível de detalhe", "Report level"),
    ("Relatório técnico", "Technical report"),
    ("Resumo executivo", "Executive summary"),
    ("Memória de cálculo", "Detailed calculation note"),
    ("Classe desenv.", "Exposure class"),
    ("t_ref / t0 [dias]", "t_ref / t0 [days]"),
    ("Idade betão t0 [dias]", "Concrete age t0 [days]"),
    ("lido da tabela (coluna Material)", "read from the Material column"),
    ("Tabela carregada (tabela editável)", "Table loaded (editable grid)"),
    ("tabela editável", "editable grid"),
    ("Betão lido da coluna Material", "Concrete grade read from the Material column"),
    ("betão read from the Material column", "concrete grade read from the Material column"),
    ("betão", "concrete grade"),
    ("Betão", "Concrete"),
    ("Falhas bloqueantes detectadas", "Blocking design issues detected"),
    ("Foram detectadas falhas bloqueantes", "Blocking design issues were detected"),
    ("falhas bloqueantes", "blocking design issues"),
    ("Falhas bloqueantes", "Blocking design issues"),
    ("bloqueantes", "blocking issues"),
    ("Bloqueante", "Blocking"),
    ("Pretende gerar propostas de correcção?", "Generate correction proposals?"),
    ("verificar em modo Design antes de adoptar", "run Design mode before adopting the reinforcement"),
    ("verificar em modo Dimensionamento antes de adoptar", "run Design mode before adopting the reinforcement"),
    ("antes de adoptar", "before adopting the reinforcement"),
    ("Cálculo concluído", "Calculation complete"),
    ("A calcular", "Calculating"),
    ("casos de envolvente", "governing cases"),
    ("casos member/case", "member/case pairs"),
    ("pares member/case", "member/case pairs"),
    ("linhas", "rows"),
    ("prumadas", "column lines"),
    ("Prumadas", "Column lines"),
    ("avisos", "warnings"),
    ("Avisos", "Warnings"),
    ("membros", "members"),
    ("Membros", "Members"),
    ("Falha", "Failure"),
    ("Aviso", "Warning"),
]


def _rc6_lang(app):
    try:
        return LANG_EN if str(app.var_language.get()).upper().startswith("EN") else LANG_PT
    except Exception:
        return LANG_PT


def _rc6_is_en(app):
    return _rc6_lang(app) == LANG_EN


def _rc6_get_var(app, name, default=""):
    try:
        v = getattr(app, name)
        return v.get() if hasattr(v, "get") else v
    except Exception:
        return default


def _rc6_is_preliminary(app):
    try:
        val = _rc6_get_var(app, "var_calc_mode", "")
        return _v53_mode_to_internal(val) == "pre_dimensionamento"
    except Exception:
        s = str(_rc6_get_var(app, "var_calc_mode", "")).lower()
        return "pre" in s or "pré" in s or "sizing" in s


def _rc6_strategy_key(value):
    s = str(value or "").strip().lower()
    if any(k in s for k in ["econ", "minimum", "mín", "min", "lowest"]):
        return "economica"
    if any(k in s for k in ["rob", "robust"]):
        return "robusta"
    return "equilibrada"


def _rc6_strategy_display(value, lang=LANG_EN):
    k = _rc6_strategy_key(value)
    if lang == LANG_EN:
        return {"economica": "Minimum reinforcement", "equilibrada": "Balanced", "robusta": "Robust"}.get(k, "Balanced")
    return {"economica": "Económica", "equilibrada": "Equilibrada", "robusta": "Robusta"}.get(k, "Equilibrada")


def _rc6_pdf_level_key(value):
    s = str(value or "").strip().lower()
    if "executive" in s or "resumo" in s:
        return "summary"
    if "memory" in s or "detailed" in s or "memória" in s or "memoria" in s:
        return "calc_note"
    return "technical"


def _rc6_pdf_level_display(value, lang=LANG_EN):
    k = _rc6_pdf_level_key(value)
    if lang == LANG_EN:
        return {"summary": "Executive summary", "technical": "Technical report", "calc_note": "Detailed calculation note"}.get(k, "Technical report")
    return {"summary": "Resumo executivo", "technical": "Relatório técnico", "calc_note": "Memória de cálculo"}.get(k, "Relatório técnico")


# Override strategy key to make the design engine understand technical English GUI values.
def _v64_strategy_key(value: str) -> str:
    return _rc6_strategy_key(value)


def _v64_strategy_label(value: str) -> str:
    k = _rc6_strategy_key(value)
    if k == "economica":
        return "Económica — menor área de aço que verifica"
    if k == "robusta":
        return "Robusta — menor η_NMyMz"
    return "Equilibrada — η_NMyMz alvo 0.70–0.85"


def _rc6_technical_en_text(value):
    s = str(value)
    if not s:
        return s
    if s in _RC6_EXACT_PT_EN:
        return _RC6_EXACT_PT_EN[s]
    # Use the previous v6.9 dictionary for broad UI strings, then apply technical clean-up.
    try:
        s = _v69_tr_text(s, LANG_EN)
    except Exception:
        pass
    if s in _RC6_EXACT_PT_EN:
        return _RC6_EXACT_PT_EN[s]
    for old, new in sorted(_RC6_FRAGMENT_PT_EN, key=lambda x: len(x[0]), reverse=True):
        s = s.replace(old, new)
    # Technical clean-up for mixed strings created by earlier fragment translators.
    cleanups = [
        ("Estratégia de reinforcement", "Reinforcement strategy"),
        ("Reinforcement estratégia", "Reinforcement strategy"),
        ("Diagnóstico and auditoria", "Diagnostics and audit"),
        ("diagnóstico", "diagnostics"),
        ("Diagnóstico", "Diagnostics"),
        ("correcção", "correction"),
        ("Correcção", "Correction"),
        ("Prumadas", "Column lines"),
        ("prumadas", "column lines"),
        ("Membros", "Members"),
        ("membros", "members"),
        ("Casos", "Cases"),
        ("casos", "cases"),
        ("Avisos", "Warnings"),
        ("avisos", "warnings"),
        ("Falhas", "Failures"),
        ("falhas", "failures"),
        ("bloqueantes", "blocking issues"),
        ("Betão", "Concrete"),
        ("betão", "concrete grade"),
        ("Tabela", "Table"),
        ("tabela", "table"),
        ("grelha", "grid"),
        ("Piso", "Storey"),
        ("piso", "storey"),
        ("Nível", "Level"),
        ("nível", "level"),
        ("Relatório", "Report"),
        ("relatório", "report"),
        ("armadura", "reinforcement"),
        ("Armadura", "Reinforcement"),
        ("pormenorização", "detailing"),
        ("Pormenorização", "Detailing"),
        ("adoptar", "adopt"),
    ]
    for old, new in cleanups:
        s = s.replace(old, new)
    # More exact technical phrasing after generic replacements.
    s = s.replace("Minimum reinforcement: menor As; Balanced: η≈0.80; Robust: menor η.", "Minimum reinforcement: lowest compliant As; Balanced: target η≈0.80; Robust: lowest η.")
    s = s.replace("Balanced — η_NMyMz alvo 0.70–0.85", "Balanced — target η_NMyMz = 0.70–0.85")
    s = s.replace("Preliminary sizing: verificar em modo Design before adopting", "Preliminary sizing: run Design mode before adopting the reinforcement")
    s = s.replace("preliminary sizing: verificar em modo Design before adopting", "preliminary sizing: run Design mode before adopting the reinforcement")
    s = s.replace("Design before adopting", "Design mode before adopting the reinforcement")
    s = s.replace("concrete grade read from the Material column", "concrete grade read from the Material column")
    s = s.replace("and tabela tipo", "and input table format")
    s = s.replace("utilização", "utilisation")
    s = s.replace("Utilização", "Utilisation")
    # Preliminary sizing is not a final compliance check; avoid presenting its verification flags as final blocking failures.
    if "Preliminary sizing" in s or "preliminary sizing" in s:
        s = s.replace("blocking design issues", "items requiring Design-mode verification")
        s = s.replace("blocking failures", "items requiring Design-mode verification")
        s = s.replace("blocking issues", "items requiring Design-mode verification")
    # Normalise double replacements.
    while "  " in s:
        s = s.replace("  ", " ")
    return s

# Replace the previous live translator with the RC6 technical translator.
_rc5_to_en_text = _rc6_technical_en_text


def _rc6_instructions_en():
    return (
        "USER INSTRUCTIONS AND INPUT TABLE FORMAT\n\n"
        "PROGRAMME PURPOSE\n"
        "ColumnsEC2 designs and checks reinforced concrete columns using nodal actions and member geometric properties. "
        "The workflow includes governing-case selection, ULS verification, second-order effects, N-My-Mz interaction, complementary shear/torsion/SLS checks, constructive detailing, technical PDF reporting, Excel output and a DXF column schedule.\n\n"
        "WORKFLOW\n"
        "1. Prepare the input table using the template columns.\n"
        "2. Paste the table or import the Excel file.\n"
        "3. Check the recognised columns, materials, column lines and storeys.\n"
        "4. Select the design standard/calculation engine, design mode and reinforcement strategy.\n"
        "5. Run the calculation.\n"
        "6. Review the summary by column line/storey, module status and warnings.\n"
        "7. Export the PDF report, Excel workbook and DXF column schedule.\n\n"
        "INPUT TABLE FORMAT\n"
        "Member/Node/Case | FX (kN) | FY (kN) | FZ (kN) | MX (kNm) | MY (kNm) | MZ (kNm) | Length (m) | Material | HY (cm) | HZ (cm) | VY (cm) | VZ (cm) | VPY (cm) | VPZ (cm) | AX (cm2) | AY (cm2) | AZ (cm2) | IX (cm4) | IY (cm4) | IZ (cm4) | Name | Story\n\n"
        "MAIN COLUMNS\n"
        "Member/Node/Case — member, node and load case/combination identifier.\n"
        "FX, FY, FZ — nodal forces in kN in the member local coordinate system.\n"
        "MX, MY, MZ — nodal moments in kNm in the member local coordinate system.\n"
        "Length — member length in metres.\n"
        "Material — concrete grade for the member, for example C30/37.\n"
        "HY, HZ — main cross-section dimensions in centimetres.\n"
        "AX, IY, IZ — area and second moments of area in the stated units.\n"
        "Name — column line name. Elements with the same Name are grouped in the same vertical alignment.\n"
        "Story — storey/segment associated with the element. Equivalent headings accepted: Storey, Piso, Andar, Floor, Level, Pavimento, Nível.\n\n"
        "AXES AND ACTION CONVENTION\n"
        "The local X axis is assumed to be the column longitudinal axis. FX is treated as the axial design action. MY and MZ are treated as bending moments. Ideally, each Member/Case has two rows, one for each end node.\n\n"
        "COLUMN LINE AND STOREY ORGANISATION\n"
        "The Name column defines the column line. The Story/Storey column is used to order column segments from lower to upper storeys and to preserve changes in cross-section or reinforcement within the same column line.\n\n"
        "EXPECTED UNITS\n"
        "FX, FY, FZ: kN; MX, MY, MZ: kNm; Length: m; HY/HZ/VY/VZ/VPY/VPZ: cm; AX/AY/AZ: cm²; IX/IY/IZ: cm⁴.\n\n"
        "AUTOMATIC VALIDATION\n"
        "The programme checks required columns, Member/Case pairs, material definition, geometry consistency and possible unit inconsistencies. Lines with insufficient data are flagged for review.\n\n"
        "RECOMMENDATIONS\n"
        "For final design, check the governing columns, effective lengths, material classes, load combinations and detailing assumptions. The Excel workbook keeps the full calculation record by case; the PDF presents the technical summary by column line/segment."
    )


def _rc6_instructions_pt():
    return (
        "INSTRUÇÕES DE UTILIZAÇÃO E TABELA TIPO\n\n"
        "OBJECTIVO DO PROGRAMA\n"
        "O ColumnsEC2 dimensiona e verifica pilares de betão armado a partir de esforços nodais e propriedades geométricas dos elementos. "
        "O fluxo inclui selecção de casos governantes, verificação ELU, efeitos de 2.ª ordem, interacção N-My-Mz, verificações complementares, pormenorização construtiva, relatório PDF, workbook Excel e quadro de pilares em DXF.\n\n"
        "FLUXO DE UTILIZAÇÃO\n"
        "1. Preparar a tabela de entrada com as colunas tipo.\n"
        "2. Colar a tabela ou importar o ficheiro Excel.\n"
        "3. Confirmar colunas, materiais, prumadas e pisos reconhecidos.\n"
        "4. Seleccionar norma/motor de cálculo, modo e estratégia de armadura.\n"
        "5. Executar o cálculo.\n"
        "6. Rever o resumo por prumada/piso, estados por módulo e avisos.\n"
        "7. Exportar PDF, Excel e DXF.\n\n"
        "FORMATO DA TABELA\n"
        "Member/Node/Case | FX (kN) | FY (kN) | FZ (kN) | MX (kNm) | MY (kNm) | MZ (kNm) | Length (m) | Material | HY (cm) | HZ (cm) | VY (cm) | VZ (cm) | VPY (cm) | VPZ (cm) | AX (cm2) | AY (cm2) | AZ (cm2) | IX (cm4) | IY (cm4) | IZ (cm4) | Name | Story\n\n"
        "A coluna Name identifica a prumada. A coluna Story/Piso/Andar/Floor/Level identifica o piso/tramo e permite ordenar os elementos do piso inferior para o superior."
    )


def _rc6_update_instruction_texts(app):
    try:
        lang = _rc6_lang(app)
        target = _rc6_instructions_en() if lang == LANG_EN else _rc6_instructions_pt()
        for w in _rc5_walk_widgets(app):
            if isinstance(w, tk.Text):
                try:
                    current = w.get("1.0", "end")
                except Exception:
                    continue
                probe = current[:3000]
                if any(k in probe for k in ["PROGRAMME PURPOSE", "OBJECTIVO", "USER INSTRUCTIONS", "Instruções de utilização", "INSTRUÇÕES DE UTILIZAÇÃO"]):
                    state = str(w.cget("state"))
                    try:
                        w.config(state="normal")
                    except Exception:
                        pass
                    w.delete("1.0", "end")
                    w.insert("1.0", target)
                    try:
                        w.config(state=state)
                    except Exception:
                        pass
    except Exception:
        pass


def _rc6_quick_notes_en(app=None):
    try:
        b = _v59_get_backend(app)
    except Exception:
        b = globals().get("BACKEND_EC2_PT_2010", "pt2010")
    try:
        norm = _backend_display_v59(b) if "_backend_display_v59" in globals() else "Eurocode 2"
    except Exception:
        norm = "Eurocode 2"
    mode = "Preliminary sizing" if _rc6_is_preliminary(app) else "Design"
    if b == globals().get("BACKEND_EC2_PT_2010", "pt2010"):
        return (
            f"Standard: {norm}\n"
            "Calculation engine: internal ColumnsEC2 design engine\n"
            f"Mode: {mode}\n"
            "Scope: ULS N-My-Mz interaction, slenderness, second-order effects, shear, torsion, SLS screening and constructive detailing. "
            "Design actions are assumed to come from valid structural-analysis combinations."
        )
    return (
        f"Standard: {norm}\n"
        "Calculation engine: structuralcodes backend, without internal formula fallback for backend-specific checks\n"
        f"Mode: {mode}\n"
        "Scope: materials, creep/shrinkage, N-My-Mz interaction and complementary checks are evaluated where exposed by the installed API. "
        "Unavailable modules are reported as not assessed rather than replaced by internal formulae."
    )


def _rc6_translate_comboboxes(app):
    lang = _rc6_lang(app)
    for w in list(_rc5_walk_widgets(app)):
        if not isinstance(w, ttk.Combobox):
            continue
        try:
            tv = str(w.cget("textvariable"))
        except Exception:
            continue
        try:
            if hasattr(app, "var_calc_mode") and tv == str(app.var_calc_mode):
                if lang == LANG_EN:
                    val = "Preliminary sizing" if _v53_mode_to_internal(app.var_calc_mode.get()) == "pre_dimensionamento" else "Design"
                    w.configure(values=["Preliminary sizing", "Design"], state="readonly", width=max(18, int(w.cget("width"))))
                    app.var_calc_mode.set(val)
                else:
                    val = "Pré-dimensionamento" if _v53_mode_to_internal(app.var_calc_mode.get()) == "pre_dimensionamento" else "Dimensionamento"
                    w.configure(values=["Pré-dimensionamento", "Dimensionamento"], state="readonly")
                    app.var_calc_mode.set(val)
            elif hasattr(app, "var_rebar_strategy") and tv == str(app.var_rebar_strategy):
                if lang == LANG_EN:
                    val = _rc6_strategy_display(app.var_rebar_strategy.get(), LANG_EN)
                    w.configure(values=["Minimum reinforcement", "Balanced", "Robust"], state="readonly", width=max(18, int(w.cget("width"))))
                    app.var_rebar_strategy.set(val)
                else:
                    val = _rc6_strategy_display(app.var_rebar_strategy.get(), LANG_PT)
                    w.configure(values=["Económica", "Equilibrada", "Robusta"], state="readonly")
                    app.var_rebar_strategy.set(val)
            elif hasattr(app, "var_pdf_level") and tv == str(app.var_pdf_level):
                if lang == LANG_EN:
                    val = _rc6_pdf_level_display(app.var_pdf_level.get(), LANG_EN)
                    w.configure(values=["Executive summary", "Technical report", "Detailed calculation note"], state="readonly", width=max(20, int(w.cget("width"))))
                    app.var_pdf_level.set(val)
                else:
                    val = _rc6_pdf_level_display(app.var_pdf_level.get(), LANG_PT)
                    w.configure(values=["Resumo executivo", "Relatório técnico", "Memória de cálculo"], state="readonly")
                    app.var_pdf_level.set(val)
        except Exception:
            pass


def _rc6_translate_tree_headings(app):
    try:
        for w in _rc5_walk_widgets(app):
            if isinstance(w, ttk.Treeview):
                for col in w.get("columns"):
                    try:
                        txt = w.heading(col, "text") or str(col)
                        if _rc6_is_en(app):
                            w.heading(col, text=_rc6_technical_en_text(txt))
                    except Exception:
                        pass
    except Exception:
        pass


_rc6_prev_translate_widget_tree = globals().get("_rc5_translate_widget_tree")
def _rc5_translate_widget_tree(app):
    global _RC6_ACTIVE_APP
    _RC6_ACTIVE_APP = app
    lang = _rc6_lang(app)
    try:
        if callable(_rc6_prev_translate_widget_tree):
            _rc6_prev_translate_widget_tree(app)
    except Exception:
        pass
    try:
        app.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if lang == LANG_EN else APP_TITLE)
    except Exception:
        pass
    for w in list(_rc5_walk_widgets(app)):
        try:
            txt = str(w.cget("text"))
        except Exception:
            txt = None
        if txt is not None:
            try:
                if lang == LANG_EN:
                    new = _rc6_technical_en_text(txt)
                else:
                    new = _V69_UI_MAP_EN_PT.get(txt, txt)
                if new != txt:
                    w.configure(text=new)
            except Exception:
                pass
    if lang == LANG_EN:
        try:
            for nb in [w for w in _rc5_walk_widgets(app) if isinstance(w, ttk.Notebook)]:
                for tab_id in nb.tabs():
                    txt = nb.tab(tab_id, "text")
                    new = _rc6_technical_en_text(txt)
                    if new != txt:
                        nb.tab(tab_id, text=new)
        except Exception:
            pass
    _rc6_translate_comboboxes(app)
    _rc6_update_instruction_texts(app)
    _rc6_translate_tree_headings(app)
    try:
        if lang == LANG_EN and hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(_rc6_quick_notes_en(app))
    except Exception:
        pass
    try:
        if lang == LANG_EN:
            old = app.status_var.get()
            new = _rc6_technical_en_text(old)
            if _rc6_is_preliminary(app) and ("blocking" in new.lower() or "failure" in new.lower()):
                new = new.replace("blocking design issues", "items requiring Design-mode verification")
                new = new.replace("blocking failures", "items requiring Design-mode verification")
                new = new.replace("blocking issues", "items requiring Design-mode verification")
            if new != old:
                app.status_var.set(new)
    except Exception:
        pass


def _v59_update_quick_notes(app):
    try:
        if _rc6_is_en(app) and hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(_rc6_quick_notes_en(app))
            return
    except Exception:
        pass
    try:
        if hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(_rc4_quick_notes(app) if "_rc4_quick_notes" in globals() else "")
    except Exception:
        pass


def _v60_quick_notes(app=None) -> str:
    try:
        return _rc6_quick_notes_en(app) if app is not None and _rc6_is_en(app) else (_rc4_quick_notes(app) if "_rc4_quick_notes" in globals() else "")
    except Exception:
        return ""


# Message boxes: suppress the correction prompt in preliminary sizing and translate remaining legacy messages.
_rc6_orig_askyesno = getattr(messagebox, "askyesno")
_rc6_orig_showinfo = getattr(messagebox, "showinfo")
_rc6_orig_showwarning = getattr(messagebox, "showwarning")
_rc6_orig_showerror = getattr(messagebox, "showerror")


def _rc6_messagebox_text(title, message):
    app = _RC6_ACTIVE_APP
    if app is not None and _rc6_is_en(app):
        return _rc6_technical_en_text(title), _rc6_technical_en_text(message)
    return title, message


def _rc6_askyesno(title, message=None, *args, **kwargs):
    app = _RC6_ACTIVE_APP
    msg = "" if message is None else str(message)
    ttl = str(title)
    if app is not None and _rc6_is_preliminary(app) and ("Falhas bloqueantes" in ttl or "falhas bloqueantes" in msg or "Blocking" in ttl):
        # Preliminary sizing is not a final compliance check; do not launch correction workflow.
        try:
            if _rc6_is_en(app):
                app.status_var.set("Preliminary sizing complete: some column segments require Design-mode verification before adoption.")
            else:
                app.status_var.set("Pré-dimensionamento concluído: alguns tramos requerem verificação em modo Dimensionamento antes de adoptar.")
        except Exception:
            pass
        return False
    ttl, msg = _rc6_messagebox_text(ttl, msg)
    return _rc6_orig_askyesno(ttl, msg, *args, **kwargs)


def _rc6_showinfo(title, message=None, *args, **kwargs):
    ttl, msg = _rc6_messagebox_text(str(title), "" if message is None else str(message))
    return _rc6_orig_showinfo(ttl, msg, *args, **kwargs)


def _rc6_showwarning(title, message=None, *args, **kwargs):
    ttl, msg = _rc6_messagebox_text(str(title), "" if message is None else str(message))
    return _rc6_orig_showwarning(ttl, msg, *args, **kwargs)


def _rc6_showerror(title, message=None, *args, **kwargs):
    ttl, msg = _rc6_messagebox_text(str(title), "" if message is None else str(message))
    return _rc6_orig_showerror(ttl, msg, *args, **kwargs)

messagebox.askyesno = _rc6_askyesno
messagebox.showinfo = _rc6_showinfo
messagebox.showwarning = _rc6_showwarning
messagebox.showerror = _rc6_showerror


# Keep table headings translated after each refresh.
_rc6_prev_show_df = getattr(ColumnsEC2App, "show_df", None)
def _rc6_show_df(self, tree, df):
    global _RC6_ACTIVE_APP
    _RC6_ACTIVE_APP = self
    if callable(_rc6_prev_show_df):
        out = _rc6_prev_show_df(self, tree, df)
    else:
        out = None
    try:
        if _rc6_is_en(self):
            _rc6_translate_tree_headings(self)
    except Exception:
        pass
    return out
ColumnsEC2App.show_df = _rc6_show_df


# Wrap actions to keep the active language context available to callbacks launched later by Tk.
_rc6_prev_apply_language = getattr(ColumnsEC2App, "apply_language", None)
def _rc6_apply_language(self):
    global _RC6_ACTIVE_APP
    _RC6_ACTIVE_APP = self
    try:
        if callable(_rc6_prev_apply_language):
            _rc6_prev_apply_language(self)
    except Exception:
        pass
    _rc5_install_live_localisation(self)
    _rc5_translate_widget_tree(self)
    try:
        self.status_var.set("Language set to English (UK)." if _rc6_is_en(self) else "Idioma definido para Português.")
    except Exception:
        pass
ColumnsEC2App.apply_language = _rc6_apply_language
try:
    _rc3_apply_language = _rc6_apply_language
except Exception:
    pass

_rc6_prev_run_design = getattr(ColumnsEC2App, "run_design", None)
def _rc6_run_design(self):
    global _RC6_ACTIVE_APP
    _RC6_ACTIVE_APP = self
    _rc5_install_live_localisation(self)
    # Ensure the calculation engine receives understandable strategy labels.
    try:
        globals()["ACTIVE_REBAR_STRATEGY_V64"] = _rc6_strategy_key(_rc6_get_var(self, "var_rebar_strategy", "Balanced"))
    except Exception:
        pass
    result = _rc6_prev_run_design(self) if callable(_rc6_prev_run_design) else None
    try:
        if _rc6_is_en(self):
            _rc5_translate_widget_tree(self)
    except Exception:
        pass
    return result
ColumnsEC2App.run_design = _rc6_run_design


# Improve status translation function explicitly used by older traces.
def _rc5_translate_status_var(app):
    if not _rc6_is_en(app):
        return
    try:
        old = app.status_var.get()
        new = _rc6_technical_en_text(old)
        if _rc6_is_preliminary(app):
            new = new.replace("blocking design issues", "items requiring Design-mode verification")
            new = new.replace("blocking failures", "items requiring Design-mode verification")
            new = new.replace("blocking issues", "items requiring Design-mode verification")
        if new != old:
            app.status_var.set(new)
    except Exception:
        pass


# Initial title/language application with RC6 translation pass.
def _v091_apply_language_title(app):
    global _RC6_ACTIVE_APP
    _RC6_ACTIVE_APP = app
    try:
        _rc5_install_live_localisation(app)
        app.apply_language()
        _rc5_translate_widget_tree(app)
    except Exception:
        try:
            app.title("ColumnsEC2 - Reinforced Concrete Column Design (EC2)" if _rc6_is_en(app) else APP_TITLE)
        except Exception:
            pass


