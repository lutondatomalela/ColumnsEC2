# -*- coding: utf-8 -*-
# ColumnsEC2 v0.9 RC12 — UI organisation, summary consolidation, metadata and warning hygiene.
# Numerical design/check routines are intentionally left unchanged.

APP_VERSION = "v0.9 RC12 Modular"

_RC12_REPO_URL = globals().get("GITHUB_URL", "https://github.com/lutondatomalela/ColumnsEC2")

# ---------------------------------------------------------------------------
# Small localisation helpers
# ---------------------------------------------------------------------------
def _rc12_lang(app=None):
    try:
        app = app or globals().get("_RC6_ACTIVE_APP", None)
        return LANG_EN if str(app.var_language.get()).upper().startswith("EN") else LANG_PT
    except Exception:
        return LANG_PT


def _rc12_is_en(app=None):
    return _rc12_lang(app) == LANG_EN


def _rc12_t(app, pt, en):
    return en if _rc12_is_en(app) else pt


def _rc12_apply_en(text):
    try:
        return _rc11_to_technical_en(str(text))
    except Exception:
        return str(text)


def _rc12_clean_label(text, app=None):
    s = str(text)
    if _rc12_is_en(app):
        return _rc12_apply_en(s)
    return s

# Extend RC11 technical wording for the new areas.
try:
    _RC11_EXACT.update({
        "Modelo de tabela tipo": "Input table template",
        "Carregar tabela tipo": "Load built-in example table",
        "Guardar modelo Excel": "Save Excel template",
        "Guardar modelo CSV": "Save CSV template",
        "Quadro de pilares .DXF": "Column schedule .DXF",
        "Quadro de pilares": "Column schedule",
        "1. Entrada": "1. Input data",
        "1. Entrada de dados": "1. Input data",
        "2. Parâmetros EC2": "2. Design parameters",
        "2. Parâmetros de dimensionamento": "2. Design parameters",
        "3. Norma e motor de cálculo": "3. Design standard and calculation engine",
        "4. Fluência e ELS": "4. Creep and SLS",
        "4A. Fluência": "4A. Creep",
        "5. Estratégia de armadura": "5. Reinforcement strategy",
        "6. Cálculo e exportação": "6. Calculation and outputs",
        "6A. Definições do relatório": "6A. Report settings",
        "7. Diagnóstico e auditoria": "7. Diagnostics and audit",
        "8. Estado": "8. Status",
        "9. Notas rápidas": "9. Quick notes",
        "Detected concrete classes": "Detected concrete grades",
        "Betão detectado": "Detected concrete grade",
        "Warning reason": "Warning reason",
        "warning_reason": "Warning reason",
        "backend_scope_note": "Backend scope note",
    })
    _RC11_PHRASES.extend([
        ("Tabela tipo carregada na grelha", "Built-in example table loaded into the editable grid"),
        ("Modelo de tabela Excel guardado", "Excel input-table template saved"),
        ("Modelo de tabela CSV guardado", "CSV input-table template saved"),
        ("Classe de betão detectada", "Detected concrete grade"),
        ("Classes de betão detectadas", "Detected concrete grades"),
        ("Não detectado — confirme a classe de betão", "Not detected — confirm the concrete strength class"),
        ("Quadro de pilares exportado", "Column schedule exported"),
        ("DXF exportado", "Column schedule exported"),
        ("Relatório PDF", "PDF report"),
        ("Definições do relatório", "Report settings"),
    ])
    _RC11_COLUMNS.update({
        "warning_reason": "Warning reason",
        "backend_scope_note": "Backend scope note",
        "N.º combinações/tramo": "No. of combinations/segment",
        "Secção [cm]": "Section [cm]",
        "Ordem na prumada": "Order within column line",
    })
except Exception:
    pass

# ---------------------------------------------------------------------------
# Backend/reference metadata
# ---------------------------------------------------------------------------
def _rc12_backend_key(app=None):
    try:
        if app is not None and hasattr(app, "var_code_backend"):
            val = app.var_code_backend.get()
        else:
            val = globals().get("ACTIVE_CODE_BACKEND_V48", "")
        if "_backend_selected_v52" in globals():
            return _backend_selected_v52(val)
        if "_backend_selected_v59" in globals():
            return _backend_selected_v59(val)
        return str(val)
    except Exception:
        return str(globals().get("ACTIVE_CODE_BACKEND_V48", ""))


def _rc12_norm_reference(app=None):
    b = _rc12_backend_key(app)
    s = str(b).lower()
    if "model code" in s or "mc2010" in s or "fib" in s:
        return "fib Model Code 2010 via structuralcodes"
    if "2004" in s:
        return "Eurocode 2:2004 via structuralcodes"
    if "2023" in s:
        return "Eurocode 2:2023 via structuralcodes"
    return "NP EN 1992-1-1:2010 + AC:2012 + A1:2019 (Portugal)"

# Override the old reference helpers used by PDF/XLSX.
def _v59_norm_reference(app=None):
    return _rc12_norm_reference(app)

def _backend_reference_v59(app=None):
    return _rc12_norm_reference(app)

# ---------------------------------------------------------------------------
# Concrete classes shown in sidebar and parameter tables
# ---------------------------------------------------------------------------
def _rc12_detect_concrete_classes(app):
    vals = []
    for df in [getattr(app, "df_clean", pd.DataFrame()), getattr(app, "df_results", pd.DataFrame()), getattr(app, "df_pair", pd.DataFrame())]:
        try:
            if df is not None and not df.empty and "material" in df.columns:
                vals += [str(x).strip().replace(" ", "") for x in df["material"].dropna().tolist()]
        except Exception:
            pass
    mats = []
    for v in vals:
        try:
            m = re.search(r"C\s*\d+\s*/\s*\d+", str(v), re.I)
            if m:
                vv = m.group(0).upper().replace(" ", "")
                if vv not in mats:
                    mats.append(vv)
        except Exception:
            pass
    return mats


def _rc12_concrete_display(app):
    mats = _rc12_detect_concrete_classes(app)
    if not mats:
        return _rc12_t(app, "Não detectado — confirme a classe de betão", "Not detected — confirm the concrete strength class")
    if len(mats) == 1:
        return _rc12_t(app, f"Detectado: {mats[0]}", f"Detected: {mats[0]}")
    if len(mats) <= 4:
        return _rc12_t(app, "Detectados: " + ", ".join(mats), "Detected concrete grades: " + ", ".join(mats))
    return _rc12_t(app, f"{len(mats)} classes detectadas: " + ", ".join(mats[:4]) + "...", f"{len(mats)} concrete grades detected: " + ", ".join(mats[:4]) + "...")


def _rc12_update_concrete_widget(app):
    try:
        if not hasattr(app, "var_concrete_detected"):
            app.var_concrete_detected = tk.StringVar(master=app, value=_rc12_concrete_display(app))
        else:
            app.var_concrete_detected.set(_rc12_concrete_display(app))
    except Exception:
        return
    # Attach textvariable to the old static label when found.
    try:
        for w in _rc12_walk_widgets(app):
            try:
                txt = str(w.cget("text"))
            except Exception:
                continue
            low = txt.lower()
            if ("lido da tabela" in low or "read from" in low or "coluna material" in low or "material column" in low) and isinstance(w, ttk.Label):
                try:
                    w.configure(textvariable=app.var_concrete_detected, text="")
                except Exception:
                    pass
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Built-in template/sample table
# ---------------------------------------------------------------------------
def _rc12_template_df():
    rows = [
        ["P1/01/101 (C)", "850,00", "4,20", "-12,50", "0,20", "45,00", "18,00", "3,20", "C30/37", "40,0", "40,0", "20,0", "20,0", "20,0", "20,0", "1600,00", "1333,33", "1333,33", "426666,67", "213333,33", "213333,33", "P1", "PISO -1"],
        ["P1/02/101 (C)", "842,00", "-3,80", "10,60", "0,18", "-38,00", "16,50", "3,20", "C30/37", "40,0", "40,0", "20,0", "20,0", "20,0", "20,0", "1600,00", "1333,33", "1333,33", "426666,67", "213333,33", "213333,33", "P1", "PISO -1"],
        ["P1/03/201 (CQC)", "620,00", "3,10", "-8,20", "0,14", "26,00", "12,00", "3,00", "C30/37", "35,0", "35,0", "17,5", "17,5", "17,5", "17,5", "1225,00", "1020,83", "1020,83", "250104,17", "125052,08", "125052,08", "P1", "PISO 1"],
        ["P1/04/201 (CQC)", "615,00", "-2,90", "7,80", "0,13", "-24,50", "11,70", "3,00", "C30/37", "35,0", "35,0", "17,5", "17,5", "17,5", "17,5", "1225,00", "1020,83", "1020,83", "250104,17", "125052,08", "125052,08", "P1", "PISO 1"],
    ]
    cols = [
        "Member/Node/Case", "FX (kN)", "FY (kN)", "FZ (kN)", "MX (kNm)", "MY (kNm)", "MZ (kNm)",
        "Length (m)", "Material", "HY (cm)", "HZ (cm)", "VY (cm)", "VZ (cm)", "VPY (cm)", "VPZ (cm)",
        "AX (cm2)", "AY (cm2)", "AZ (cm2)", "IX (cm4)", "IY (cm4)", "IZ (cm4)", "Name", "Story"
    ]
    return pd.DataFrame(rows, columns=cols)

_rc12_prev_export_template = getattr(ColumnsEC2App, "export_template", None)

def _rc12_save_template_xlsx(app):
    path = filedialog.asksaveasfilename(
        title=_rc12_t(app, "Guardar modelo Excel", "Save Excel input-table template"),
        defaultextension=".xlsx",
        filetypes=[("Excel workbook", "*.xlsx")],
    )
    if not path:
        return
    if not path.lower().endswith(".xlsx"):
        path += ".xlsx"
    df = _rc12_template_df()
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="INPUT_TABLE_TEMPLATE", index=False)
            notes = pd.DataFrame([
                ["Member/Node/Case", "member / end-node / load case identifier"],
                ["FX, FY, FZ", "nodal forces in kN; FX is the column axial force"],
                ["MX, MY, MZ", "nodal moments in kNm; MY and MZ are bending moments"],
                ["Length", "member length in metres"],
                ["Material", "concrete strength class, e.g. C30/37"],
                ["HY, HZ", "cross-section dimensions in centimetres"],
                ["Name", "column line identifier"],
                ["Story", "storey/level label used to order segments"],
            ], columns=["Field", "Technical note"])
            notes.to_excel(writer, sheet_name="NOTES", index=False)
        app.status_var.set(_rc12_t(app, f"Modelo Excel guardado: {path}", f"Excel input-table template saved: {path}"))
    except Exception as err:
        messagebox.showerror(_rc12_t(app, "Erro", "Error"), _rc12_t(app, f"Não foi possível guardar o modelo.\n\n{err}", f"Could not save the template.\n\n{err}"))


def _rc12_save_template_csv(app):
    path = filedialog.asksaveasfilename(
        title=_rc12_t(app, "Guardar modelo CSV", "Save CSV input-table template"),
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"
    try:
        _rc12_template_df().to_csv(path, index=False, sep=";", encoding="utf-8-sig")
        app.status_var.set(_rc12_t(app, f"Modelo CSV guardado: {path}", f"CSV input-table template saved: {path}"))
    except Exception as err:
        messagebox.showerror(_rc12_t(app, "Erro", "Error"), _rc12_t(app, f"Não foi possível guardar o modelo.\n\n{err}", f"Could not save the template.\n\n{err}"))


def _rc12_load_builtin_template(app):
    df = _rc12_template_df()
    try:
        # Show the same text in the paste box, for transparency.
        text = df.to_csv(index=False, sep="\t")
        if hasattr(app, "txt_paste"):
            app.txt_paste.delete("1.0", "end")
            app.txt_paste.insert("1.0", text)
    except Exception:
        pass
    app.load_df(df, source=_rc12_t(app, "tabela tipo embutida", "built-in example table"))
    app.status_var.set(_rc12_t(app, "Tabela tipo carregada na grelha.", "Built-in example table loaded into the editable grid."))


def _rc12_template_menu(self):
    win = tk.Toplevel(self)
    win.title(_rc12_t(self, "Tabela tipo", "Input table template"))
    win.transient(self)
    win.grab_set()
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=_rc12_t(self, "Escolha como pretende usar a tabela tipo.", "Choose how to use the input-table template."), wraplength=360, justify="left").pack(fill="x", pady=(0, 8))
    ttk.Button(frm, text=_rc12_t(self, "Carregar tabela tipo na grelha", "Load built-in example into the grid"), command=lambda: (win.destroy(), _rc12_load_builtin_template(self))).pack(fill="x", pady=4)
    ttk.Button(frm, text=_rc12_t(self, "Guardar modelo Excel", "Save Excel template"), command=lambda: (win.destroy(), _rc12_save_template_xlsx(self))).pack(fill="x", pady=4)
    ttk.Button(frm, text=_rc12_t(self, "Guardar modelo CSV", "Save CSV template"), command=lambda: (win.destroy(), _rc12_save_template_csv(self))).pack(fill="x", pady=4)
    ttk.Button(frm, text=_rc12_t(self, "Cancelar", "Cancel"), command=win.destroy).pack(fill="x", pady=(8, 0))
    try:
        win.geometry(f"420x220+{self.winfo_rootx()+120}+{self.winfo_rooty()+120}")
    except Exception:
        pass

ColumnsEC2App.export_template = _rc12_template_menu

# ---------------------------------------------------------------------------
# Widget tree helpers and sidebar cleanup/reorganisation
# ---------------------------------------------------------------------------
def _rc12_walk_widgets(widget):
    try:
        children = widget.winfo_children()
    except Exception:
        children = []
    for child in children:
        yield child
        yield from _rc12_walk_widgets(child)


def _rc12_find_labelframes(parent):
    frames = []
    try:
        for w in parent.winfo_children():
            if isinstance(w, ttk.LabelFrame):
                frames.append(w)
    except Exception:
        pass
    return frames


def _rc12_label_frame_text(widget):
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _rc12_clear_frame_children(frame):
    try:
        for child in frame.winfo_children():
            child.destroy()
    except Exception:
        pass


def _rc12_header_text(app):
    if _rc12_is_en(app):
        return (
            "Engineering tool for reinforced-concrete column design and verification to Eurocode 2. "
            "It imports analysis results from structural models, checks ULS/SLS, second-order effects, "
            "N-My-Mz interaction and detailing requirements, supports structuralcodes backends, and exports "
            "technical XLSX, PDF and DXF deliverables."
        )
    return (
        "Ferramenta para dimensionamento e verificação de pilares de betão armado segundo o Eurocódigo 2. "
        "Importa esforços de modelos estruturais, avalia ELU/ELS, efeitos de 2.ª ordem, interacção N-My-Mz "
        "e pormenorização, suporta backends structuralcodes e exporta relatórios técnicos em XLSX, PDF e DXF."
    )


def _rc12_rebuild_header_frame(app, frame):
    _rc12_clear_frame_children(frame)
    try:
        frame.configure(text="ColumnsEC2")
    except Exception:
        pass
    link = ttk.Label(frame, text="ColumnsEC2", style="Header.TLabel", cursor="hand2")
    link.pack(anchor="w")
    link.bind("<Button-1>", lambda _e: webbrowser.open_new(_RC12_REPO_URL))
    ttk.Label(frame, text=_rc12_t(app, "Dimensionamento e verificação técnica de pilares de betão armado", "Reinforced concrete column analysis and design"), style="Header.TLabel", wraplength=330, justify="left").pack(anchor="w", pady=(4, 0))
    ttk.Label(frame, text=_rc12_header_text(app), style="Subtle.TLabel", wraplength=330, justify="left").pack(anchor="w", pady=(4, 0))


def _rc12_relabel_sidebar_frames(app, parent):
    frames = _rc12_find_labelframes(parent)
    # Find the top hero frame and rebuild it.
    try:
        if frames:
            _rc12_rebuild_header_frame(app, frames[0])
    except Exception:
        pass
    # Rename/reorder side bar groups. This is intentionally conservative: it
    # keeps existing widgets/variables but gives the sidebar a clean structure.
    mapping_pt = {
        "1. Entrada": "1. Entrada de dados",
        "1. Input": "1. Entrada de dados",
        "2. Parâmetros EC2": "2. Parâmetros de dimensionamento",
        "2. Design parameters": "2. Parâmetros de dimensionamento",
        "4. Cálculo e exportação": "6. Cálculo e exportação",
        "4. Design and export": "6. Cálculo e exportação",
        "4. Calculation and outputs": "6. Cálculo e exportação",
        "5. Estado": "8. Estado",
        "5. Status": "8. Estado",
        "6. Notas rápidas": "9. Notas rápidas",
        "6. Quick notes": "9. Notas rápidas",
        "7. Verificações avançadas v4": "4. Fluência e ELS",
        "7. Advanced checks": "4. Fluência e ELS",
        "9. Design standard / calculation engine": "3. Norma e motor de cálculo",
        "Design standard / calculation engine": "3. Norma e motor de cálculo",
        "Creep": "4A. Fluência",
        "Reinforcement strategy": "5. Estratégia de armadura",
        "Estratégia de reinforcement": "5. Estratégia de armadura",
        "Estratégia de armadura": "5. Estratégia de armadura",
        "Diagnóstico e auditoria": "7. Diagnóstico e auditoria",
        "Diagnóstico and auditoria": "7. Diagnóstico e auditoria",
        "Critérios da estratégia equilibrada": "5A. Critérios da estratégia equilibrada",
        "PDF report": "6A. Definições do relatório",
        "Relatório PDF": "6A. Definições do relatório",
        "Language": "Idioma",
    }
    mapping_en = {pt: en for pt, en in [
        ("1. Entrada de dados", "1. Input data"),
        ("2. Parâmetros de dimensionamento", "2. Design parameters"),
        ("3. Norma e motor de cálculo", "3. Design standard and calculation engine"),
        ("4. Fluência e ELS", "4. Creep and SLS"),
        ("4A. Fluência", "4A. Creep"),
        ("5. Estratégia de armadura", "5. Reinforcement strategy"),
        ("5A. Critérios da estratégia equilibrada", "5A. Balanced-strategy criteria"),
        ("6. Cálculo e exportação", "6. Calculation and outputs"),
        ("6A. Definições do relatório", "6A. Report settings"),
        ("7. Diagnóstico e auditoria", "7. Diagnostics and audit"),
        ("8. Estado", "8. Status"),
        ("9. Notas rápidas", "9. Quick notes"),
        ("Idioma", "Language"),
    ]}
    for fr in frames[1:]:
        try:
            old = _rc12_label_frame_text(fr)
            new_pt = mapping_pt.get(old, old)
            new = mapping_en.get(new_pt, new_pt) if _rc12_is_en(app) else new_pt
            fr.configure(text=new)
        except Exception:
            pass
    # Repack frames in a more logical order without destroying content.
    def _rank(fr):
        txt = _rc12_label_frame_text(fr)
        order = [
            "ColumnsEC2", "1.", "2.", "3.", "4. Creep and SLS", "4. Fluência e ELS",
            "4A.", "5. Reinforcement", "5. Estratégia", "5A.", "6. Calculation", "6. Cálculo",
            "6A.", "7.", "8.", "9.", "Language", "Idioma"
        ]
        if txt == "ColumnsEC2":
            return 0
        for i, key in enumerate(order, start=1):
            if key in txt:
                return i
        return 99
    try:
        for fr in frames:
            fr.pack_forget()
        for fr in sorted(frames, key=_rank):
            fr.pack(fill="x", pady=(0, 8))
    except Exception:
        pass


def _rc12_patch_buttons(app):
    # Make all template buttons open the RC12 template dialog.
    # Add the DXF button to the outputs frame and remove it from advanced checks.
    for w in _rc12_walk_widgets(app):
        try:
            txt = str(w.cget("text"))
        except Exception:
            continue
        low = txt.lower()
        if isinstance(w, ttk.Button) and ("modelo" in low or "template" in low) and ("tabela" in low or "table" in low):
            try:
                w.configure(text=_rc12_t(app, "Tabela tipo", "Input table template"), command=app.export_template)
            except Exception:
                pass
        if isinstance(w, ttk.Button) and ("dxf" in low) and ("quadro" in low or "schedule" in low or "export column" in low):
            # Destroy old DXF button if it is inside advanced/SLS frame; a clean one is added below.
            try:
                parent = w.master
                ptxt = _rc12_label_frame_text(parent)
                if "Advanced" in ptxt or "Verific" in ptxt or "Fluência" in ptxt or "Creep" in ptxt:
                    w.destroy()
            except Exception:
                pass
    # Add DXF button under calculation/output frame if not already present there.
    for fr in _rc12_find_labelframes(app.sidebar_canvas.children.get('!frame', app) if hasattr(app, 'sidebar_canvas') else app):
        pass
    # More robust: scan every LabelFrame.
    for fr in [w for w in _rc12_walk_widgets(app) if isinstance(w, ttk.LabelFrame)]:
        txt = _rc12_label_frame_text(fr)
        if "Calculation and outputs" in txt or "Cálculo e exportação" in txt or "Design and export" in txt:
            exists = False
            for ch in fr.winfo_children():
                try:
                    exists = exists or ("dxf" in str(ch.cget("text")).lower())
                except Exception:
                    pass
            if not exists:
                try:
                    max_row = 0
                    for ch in fr.winfo_children():
                        try:
                            max_row = max(max_row, int(ch.grid_info().get("row", 0)))
                        except Exception:
                            pass
                    ttk.Button(fr, text=_rc12_t(app, "Quadro de pilares .DXF", "Column schedule .DXF"), command=app.export_dxf).grid(row=max_row+1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
                except Exception:
                    pass

# ---------------------------------------------------------------------------
# Warnings/failures split and summary consolidation
# ---------------------------------------------------------------------------
def _rc12_status_value(row):
    for c in ["estado_global", "status", "Estado", "Overall status", "Status"]:
        try:
            v = row.get(c, "")
            if str(v).strip():
                return str(v).strip()
        except Exception:
            pass
    return ""


def _rc12_is_failure_status(value):
    s = str(value or "").lower()
    return "falha" in s or "failure" in s or "não conforme" in s or "not compliant" in s


def _rc12_is_warning_text(text):
    s = str(text or "").lower()
    keys = ["aviso", "warning", "não avaliado", "not assessed", "não exposto", "not exposed", "els", "sls", "torção", "torsion", "corte", "shear", "informativo", "informative"]
    return any(k in s for k in keys)


def _rc12_normalise_result_df(df):
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy()
    if "warning_reason" not in out.columns:
        out["warning_reason"] = ""
    if "backend_scope_note" not in out.columns:
        out["backend_scope_note"] = ""
    for idx, row in out.iterrows():
        status = _rc12_status_value(row)
        fr = str(row.get("failure_reason", "") or "").strip()
        fw = str(row.get("failure_warnings", "") or "").strip()
        wr = str(row.get("warning_reason", "") or "").strip()
        notes = [x for x in [wr, fw] if x]
        # Structuralcodes scope messages and non-blocking module notes should not be in failure_reason.
        if fr and (not _rc12_is_failure_status(status)) and _rc12_is_warning_text(fr):
            notes.append(fr)
            out.at[idx, "failure_reason"] = ""
            if "failure_type" in out.columns:
                out.at[idx, "failure_type"] = ""
        if notes:
            # Deduplicate while preserving order.
            dedup = []
            for item in "; ".join(notes).split(";"):
                it = item.strip()
                if it and it not in dedup:
                    dedup.append(it)
            out.at[idx, "warning_reason"] = "; ".join(dedup)
        try:
            bnote = str(row.get("backend_note", "") or row.get("backend_scope", "") or "").strip()
            if bnote:
                out.at[idx, "backend_scope_note"] = bnote
        except Exception:
            pass
    return out


def _rc12_section_signature(row):
    try:
        if "_v682_section_signature" in globals():
            return _v682_section_signature(row)
    except Exception:
        pass
    b = _finite(row.get("b_cm", row.get("hy", 0)), 0)
    h = _finite(row.get("h_cm", row.get("hz", 0)), 0)
    mat = str(row.get("material", ""))
    return f"{b:.3f}x{h:.3f}|{mat}"


def _rc12_prumada(row):
    try:
        if "_v682_prumada_from_row" in globals():
            return _v682_prumada_from_row(row)
    except Exception:
        pass
    return row.get("Prumada", row.get("prumada", row.get("name", row.get("member", ""))))


def _rc12_storey(row):
    try:
        if "_v683_story_label_from_row" in globals():
            return _v683_story_label_from_row(row)
    except Exception:
        pass
    return row.get("Piso", row.get("story", row.get("Story", "")))


def _rc12_story_sort(row):
    try:
        if "_v683_story_sort_tuple" in globals():
            return _v683_story_sort_tuple(row)
    except Exception:
        pass
    return (0, 0.0, str(_rc12_storey(row)))


def _rc12_governing_score(work):
    if work is None or work.empty:
        return pd.Series(dtype=float)
    try:
        eta = pd.to_numeric(work.get("η_NMyMz", work.get("eta_NMyMz", work.get("utilizacao", 0))), errors="coerce").fillna(0.0)
        n = pd.to_numeric(work.get("n_ed_kN", 0), errors="coerce").abs().fillna(0.0)
        my = pd.to_numeric(work.get("my_ed_kNm", 0), errors="coerce").abs().fillna(0.0)
        mz = pd.to_numeric(work.get("mz_ed_kNm", 0), errors="coerce").abs().fillna(0.0)
        st = work.get("estado_global", work.get("status", pd.Series("", index=work.index))).astype(str).str.lower()
        fail_boost = st.str.contains("falha|failure|não conforme|not compliant", regex=True, na=False).astype(float) * 1e6
        warn_boost = st.str.contains("aviso|warning|verificar|check", regex=True, na=False).astype(float) * 1e4
        return fail_boost + warn_boost + eta * 1000.0 + n * 0.01 + my + mz
    except Exception:
        return pd.Series(0.0, index=work.index)


def _rc12_build_summary(self, results: pd.DataFrame) -> pd.DataFrame:
    if results is None or results.empty:
        return pd.DataFrame()
    work = _rc12_normalise_result_df(results)
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
    work = _rc12_normalise_result_df(work)
    work["Prumada"] = work.apply(_rc12_prumada, axis=1)
    work["Piso"] = work.apply(_rc12_storey, axis=1)
    work["_story_sort_tuple"] = work.apply(_rc12_story_sort, axis=1)
    work["_section_signature"] = work.apply(_rc12_section_signature, axis=1)
    if "member" not in work.columns:
        work["member"] = ""
    group_cols = ["Prumada", "Piso", "member", "_section_signature"]
    work["_gov_score_rc12"] = _rc12_governing_score(work)
    rows = []
    for _, grp in work.groupby(group_cols, dropna=False, sort=False):
        g = grp.sort_values("_gov_score_rc12", ascending=False)
        r = g.iloc[0].copy()
        r["N.º combinações/tramo"] = len(grp)
        r["Secção [cm]"] = f"{_finite(r.get('b_cm', r.get('hy',0)),0):.0f}x{_finite(r.get('h_cm', r.get('hz',0)),0):.0f}"
        r["Tramo"] = r.get("Piso", "") if str(r.get("Piso", "")).strip() else f"Tramo {len(rows)+1:02d}"
        r["Solução"] = r.get("solucao_completa", r.get("solucao", r.get("Solução", "")))
        r["Estado"] = r.get("estado_global", r.get("status", r.get("Estado", "")))
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    def sort_key(v):
        try:
            if isinstance(v, tuple): return v
            return (0, 0.0, str(v))
        except Exception:
            return (0, 0.0, str(v))
    out["_sort_prumada"] = out["Prumada"].astype(str)
    out["_sort_story"] = out["_story_sort_tuple"].map(sort_key)
    try:
        out = out.sort_values(["_sort_prumada", "_sort_story", "member", "_section_signature"], kind="mergesort")
    except Exception:
        out = out.sort_values(["Prumada", "Piso", "member"], kind="mergesort")
    out["Ordem na prumada"] = out.groupby("Prumada").cumcount() + 1
    return out.drop(columns=[c for c in ["_sort_prumada", "_sort_story", "_gov_score_rc12", "_section_signature"] if c in out.columns], errors="ignore")

ColumnsEC2App.build_summary_by_member = _rc12_build_summary

# ---------------------------------------------------------------------------
# Export/report/metadata patches
# ---------------------------------------------------------------------------
def _rc12_metadata_df(self) -> pd.DataFrame:
    if _rc12_is_en(self):
        return pd.DataFrame([
            ["Program", APP_NAME],
            ["Version", APP_VERSION],
            ["Author / Repository", _RC12_REPO_URL],
            ["Export date", datetime.now().strftime("%Y-%m-%d %H:%M")],
            ["Source file", self.input_file_path or "-"],
            ["Reference standard", _rc12_norm_reference(self)],
            ["Scope", "Reinforced-concrete column design/checking by column line, storey and cross-section."],
            ["Description", "ColumnsEC2 imports member end actions, checks ULS/SLS, second-order effects and N-My-Mz interaction, proposes constructible reinforcement detailing and exports XLSX, PDF and DXF deliverables."],
            ["Technical limitations", "The programme checks imported analysis results; it does not generate load combinations. Critical columns and backend-specific warnings must be reviewed by the responsible engineer."],
        ], columns=["Field", "Value"])
    return pd.DataFrame([
        ["Programa", APP_NAME],
        ["Versão", APP_VERSION],
        ["Autor / Repositório", _RC12_REPO_URL],
        ["Data de exportação", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Ficheiro de origem", self.input_file_path or "-"],
        ["Norma de referência", _rc12_norm_reference(self)],
        ["Âmbito", "Dimensionamento/verificação de pilares de betão armado por prumada, piso e secção."],
        ["Descrição", "O ColumnsEC2 importa esforços de extremidade, verifica ELU/ELS, 2.ª ordem e interacção N-My-Mz, propõe pormenorização construtiva e exporta XLSX, PDF e DXF."],
        ["Limitações", "O programa verifica esforços importados; não gera combinações de acções. Pilares críticos e avisos de backend devem ser revistos pelo engenheiro responsável."],
    ], columns=["Campo", "Valor"])

ColumnsEC2App._metadata_df = _rc12_metadata_df


def _rc12_parameters_df(self) -> pd.DataFrame:
    concrete = _rc12_concrete_display(self)
    try:
        strategy = self.var_rebar_strategy.get()
    except Exception:
        strategy = globals().get("ACTIVE_REBAR_STRATEGY_V64", "Equilibrada")
    if _rc12_is_en(self):
        return pd.DataFrame([
            ["Nominal cover [mm]", self.var_cover.get()],
            ["Steel grade", f"B{self.var_fyk.get()}" if str(self.var_fyk.get()).replace('.', '', 1).isdigit() else self.var_fyk.get()],
            ["Concrete grade", concrete],
            ["Design mode", _rc12_apply_en(self.var_calc_mode.get())],
            ["Reinforcement strategy", _rc12_apply_en(strategy)],
            ["Calculation engine", _rc12_norm_reference(self)],
            ["Reduction to governing cases", "Yes" if self.var_reduce_cases.get() else "No"],
            ["l0y/L", self.var_l0y.get()],
            ["l0z/L", self.var_l0z.get()],
            ["Relative humidity RH [%]", getattr(self, "var_rh", tk.StringVar(value="70")).get() if hasattr(self, "var_rh") else "70"],
            ["Concrete age at loading t0 [days]", getattr(self, "var_t0", tk.StringVar(value="28")).get() if hasattr(self, "var_t0") else "28"],
            ["h0 / hn", "calculated automatically"],
            ["φef", "calculated automatically where applicable"],
        ], columns=["Parameter", "Value"])
    return pd.DataFrame([
        ["Recobrimento nominal [mm]", self.var_cover.get()],
        ["Classe de aço", f"B{self.var_fyk.get()}" if str(self.var_fyk.get()).replace('.', '', 1).isdigit() else self.var_fyk.get()],
        ["Betão", concrete],
        ["Modo de cálculo", self.var_calc_mode.get()],
        ["Estratégia de armadura", strategy],
        ["Norma / motor", _rc12_norm_reference(self)],
        ["Redução para casos governantes", "Sim" if self.var_reduce_cases.get() else "Não"],
        ["l0y/L", self.var_l0y.get()],
        ["l0z/L", self.var_l0z.get()],
        ["Humidade relativa RH [%]", getattr(self, "var_rh", tk.StringVar(value="70")).get() if hasattr(self, "var_rh") else "70"],
        ["Idade do betão no carregamento t0 [dias]", getattr(self, "var_t0", tk.StringVar(value="28")).get() if hasattr(self, "var_t0") else "28"],
        ["h0 / hn", "calculado automaticamente"],
        ["φef", "calculado automaticamente quando aplicável"],
    ], columns=["Parâmetro", "Valor"])

ColumnsEC2App._parameters_df = _rc12_parameters_df

# Wrap the Excel writer so exported sheets use cleaned results/summary and no comparison sheet is added.
_rc12_prev_write_excel = getattr(ColumnsEC2App, "_write_excel", None)

def _write_excel_rc12(self, path: str):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_results = _rc12_normalise_result_df(self.df_results)
            self.df_summary = self.build_summary_by_member(self.df_results) if getattr(self, "var_summary", tk.BooleanVar(value=True)).get() else pd.DataFrame()
    except Exception:
        pass
    if callable(_rc12_prev_write_excel):
        _rc12_prev_write_excel(self, path)
    try:
        if "_rc7_apply_workbook_links" in globals():
            import openpyxl
            wb = openpyxl.load_workbook(path)
            _rc7_apply_workbook_links(wb)
            wb.properties.title = "ColumnsEC2"
            wb.properties.subject = _rc12_norm_reference(self)
            wb.properties.description = "ColumnsEC2 technical calculation workbook."
            wb.save(path)
    except Exception:
        pass

ColumnsEC2App._write_excel = _write_excel_rc12

# Wrap run/load/export callbacks to refresh RC12 UI and clean result data.
_rc12_prev_load_df = getattr(ColumnsEC2App, "load_df", None)
def _load_df_rc12(self, df: pd.DataFrame, source: str = ""):
    out = _rc12_prev_load_df(self, df, source) if callable(_rc12_prev_load_df) else None
    try:
        _rc12_update_concrete_widget(self)
        _rc12_patch_buttons(self)
        if _rc12_is_en(self):
            self.apply_language()
    except Exception:
        pass
    return out
ColumnsEC2App.load_df = _load_df_rc12

_rc12_prev_run_design = getattr(ColumnsEC2App, "run_design", None)
def _run_design_rc12(self):
    out = _rc12_prev_run_design(self) if callable(_rc12_prev_run_design) else None
    def poll_clean():
        try:
            if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty and float(self.progress_var.get()) >= 99:
                self.df_results = _rc12_normalise_result_df(self.df_results)
                self.df_summary = self.build_summary_by_member(self.df_results) if getattr(self, "var_summary", tk.BooleanVar(value=True)).get() else pd.DataFrame()
                self.df_failures = self.df_results[self.df_results.get("estado_global", self.df_results.get("status", pd.Series(dtype=str))).astype(str).str.contains("Falha|Failure|Não conforme|Not compliant", case=False, regex=True, na=False)].copy() if not self.df_results.empty else pd.DataFrame()
                try:
                    self.show_df(self.tree_results, self.df_results)
                    self.show_df(self.tree_summary, self.df_summary)
                    self.show_df(self.tree_failures, self.df_failures)
                    if hasattr(self, "tree_shortlists") and hasattr(self, "build_shortlists_df"):
                        self.show_df(self.tree_shortlists, self.build_shortlists_df())
                except Exception:
                    pass
                try:
                    self.update_report()
                except Exception:
                    pass
                try:
                    _rc12_update_concrete_widget(self)
                    if _rc12_is_en(self):
                        self.apply_language()
                except Exception:
                    pass
                return
        except Exception:
            return
        try:
            self.after(700, poll_clean)
        except Exception:
            pass
    try:
        self.after(1000, poll_clean)
    except Exception:
        pass
    return out
ColumnsEC2App.run_design = _run_design_rc12

_rc12_prev_export_dxf = getattr(ColumnsEC2App, "export_dxf", None)
def _export_dxf_rc12(self):
    if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
        try:
            self.df_results = _rc12_normalise_result_df(self.df_results)
            self.df_summary = self.build_summary_by_member(self.df_results)
        except Exception:
            pass
    out = _rc12_prev_export_dxf(self) if callable(_rc12_prev_export_dxf) else None
    try:
        if self.status_var:
            txt = str(self.status_var.get())
            if _rc12_is_en(self):
                txt = txt.replace("DXF exported", "Column schedule exported").replace("DXF exportado", "Column schedule exported")
            else:
                txt = txt.replace("DXF exportado", "Quadro de pilares exportado")
            self.status_var.set(txt)
    except Exception:
        pass
    return out
ColumnsEC2App.export_dxf = _export_dxf_rc12

# ---------------------------------------------------------------------------
# Sidebar construction wrapper
# ---------------------------------------------------------------------------
_rc12_prev_build_sidebar = getattr(ColumnsEC2App, "_build_sidebar", None)
def _build_sidebar_rc12(self, parent):
    # Ensure vars exist before labels are built.
    if not hasattr(self, "var_concrete_detected"):
        self.var_concrete_detected = tk.StringVar(master=self, value=_rc12_concrete_display(self))
    out = _rc12_prev_build_sidebar(self, parent) if callable(_rc12_prev_build_sidebar) else None
    try:
        _rc12_relabel_sidebar_frames(self, parent)
        _rc12_update_concrete_widget(self)
        _rc12_patch_buttons(self)
        if _rc12_is_en(self):
            # Use the existing RC11 localiser after the structural changes.
            try:
                _rc11_set_widget_texts(self)
            except Exception:
                pass
    except Exception:
        pass
    return out
ColumnsEC2App._build_sidebar = _build_sidebar_rc12

# Initial language hook, extending RC11's hook if present.
_rc12_prev_apply_language = getattr(ColumnsEC2App, "apply_language", None)
def _apply_language_rc12(self):
    out = _rc12_prev_apply_language(self) if callable(_rc12_prev_apply_language) else None
    try:
        # parent of direct sidebar frames is the window item inside the canvas
        side_parent = None
        if hasattr(self, "sidebar_canvas"):
            for child in self.sidebar_canvas.winfo_children():
                side_parent = child
                break
        if side_parent is not None:
            _rc12_relabel_sidebar_frames(self, side_parent)
        _rc12_update_concrete_widget(self)
        _rc12_patch_buttons(self)
        if _rc12_is_en(self):
            _rc11_refresh_known_trees(self)
            self.update_report()
    except Exception:
        pass
    return out
ColumnsEC2App.apply_language = _apply_language_rc12

# Update instruction title/text when possible by replacing mixed-language title created in previous layers.
try:
    _RC11_EXACT["Instruções de utilização and tabela tipo"] = "User guide and input-table format"
    _RC11_EXACT["Instruções de utilização e tabela tipo"] = "User guide and input-table format"
except Exception:
    pass

# End-of-runtime hook used by GUI launcher.
def _v092_apply_language_title(app):
    try:
        app.apply_language()
    except Exception:
        pass
    try:
        if "_rc7_bind_repository_links" in globals():
            _rc7_bind_repository_links(app)
    except Exception:
        pass
