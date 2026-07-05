# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC13 — technical English pass and practical reinforcement rationalisation.

This is a transitional runtime patch. It does not change the structural
verification equations; it adjusts presentation, candidate layout priorities and
summary-level reinforcement rationalisation for practical column schedules.
"""

APP_VERSION = "v0.9 RC13 Modular"

# ---------------------------------------------------------------------------
# Technical English wording
# ---------------------------------------------------------------------------

def _rc13_lang(app=None):
    try:
        return str(app.var_language.get()).upper()
    except Exception:
        try:
            return str(globals().get("APP_LANGUAGE", "PT")).upper()
        except Exception:
            return "PT"


def _rc13_is_en(app=None):
    return "EN" in _rc13_lang(app)


_RC13_EN_TERMS = {
    # interface / headings
    "Instruções": "Instructions",
    "Colar": "Paste",
    "Tabela": "Input table",
    "Pares": "End-node pairs",
    "Validação": "Input validation",
    "Resultados": "Design results",
    "Resumo": "Column schedule",
    "Falhas": "Design issues",
    "Relatório": "Report",
    "Notas EC2": "EC2 notes",
    "Qualidade Importação": "Input quality",
    "Cobertura Backend": "Backend coverage",
    "Diagnóstico SC": "structuralcodes diagnostics",
    "Grupo": "Group",
    "Objeto": "Object",
    "Estado": "Status",
    "Detalhe": "Details",
    "Verificação": "Check",
    "Origem": "Source",
    "Nota": "Technical note",
    "Categoria": "Category",
    "Item": "Item",
    "Resultado": "Result",
    "Colunas obrigatórias": "Required input fields",
    "Pares de nós": "Member end-node pairing",
    "Consistência entre nós": "End-node data consistency",
    "Unidades": "Units check",
    "Materiais": "Materials",
    "Dados": "Input data",
    "Tabela": "Input table",
    "linhas importadas": "imported rows",
    "members": "members",
    "member vazio": "blank member identifier",
    "case vazio": "blank load case",
    "com 2 nós": "with two end nodes",
    "com 1 nó": "with one end node only",
    "com mais de 2 nós": "with more than two node rows",
    "dimensões HY/HZ": "HY/HZ dimensions",
    "classe de betão": "concrete strength class",
    "presente": "available",
    "necessária para ELU/ELS/V/T/DXF": "required for ULS/SLS/shear/torsion/DXF output",
    "corrigir cabeçalho da folha de importação": "check the input-table header",
    "linhas lidas": "rows read from the input table",
    "barras distintas": "distinct members identified",
    "member/node/case deve estar preenchido": "Member/Node/Case must be populated",
    "necessário para identificar combinação": "required to identify the design combination",
    "cada member/case deve ter exactamente duas linhas": "each member/case should contain exactly two end-node rows",
    "cada member/case deve ter exatamente duas linhas": "each member/case should contain exactly two end-node rows",
    "sem M01/M02 completo": "complete M01/M02 reconstruction is not possible",
    "verificar duplicados ou resultados intermédios": "check duplicate rows or intermediate output stations",
    "os dois nós do mesmo member/case devem ter dados geométricos compatíveis": "the two end-node rows of the same member/case must have consistent geometric data",
    "esperado em cm; verificar exportação": "expected in cm; check the analysis-model export settings",
    "esperado em m": "expected in metres",
    "a classe deve vir da coluna Material": "the strength class should be read from the Material column",
    # statuses / values
    "Disponível": "Available",
    "Indisponível": "Unavailable",
    "Calculado": "Calculated",
    "Calculado se API disponível": "Calculated when the API exposes the check",
    "Não avaliado se API ausente": "Not assessed when the API does not expose the check",
    "Informativo": "Informative",
    "Sem fallback interno": "No internal fallback is used",
    "Sem aviso relevante": "No significant warning",
    "Sem torção relevante": "No significant torsion",
    "OK sem armadura transversal resistente adicional": "OK without additional shear reinforcement",
    "Requer armadura de esforço transverso": "Shear reinforcement design required",
    "Requer armadura de torção": "Torsion reinforcement design required",
    "Não conforme": "Not compliant",
    "Aviso": "Warning",
    "Falha": "Failure",
    "Bloqueante": "Blocking design issue",
    "Dispensa 2.ª ordem": "Second-order effects not governing",
    "Considerar 2.ª ordem": "Second-order effects to be considered",
    "Dispensada": "Not required",
    "Sim": "Yes",
    "Não": "No",
    "dupla": "double curvature",
    "simples": "single curvature",
    "Sem reservas relevantes no âmbito das verificações efectuadas.": "No relevant reservation within the checks carried out.",
    "Sem reservas relevantes no âmbito das verificações efetuadas.": "No relevant reservation within the checks carried out.",
    "pormenorização construtiva a confirmar": "constructive detailing to be confirmed",
    "corte requer verificação/dimensionamento de reinforcement transversal": "shear requires a detailed transverse-reinforcement design check",
    "corte requer verificação/dimensionamento de armadura transversal": "shear requires a detailed transverse-reinforcement design check",
    "torsion requer verificação/dimensionamento complementar": "torsion requires a complementary torsion design check",
    "torção requer verificação/dimensionamento complementar": "torsion requires a complementary torsion design check",
    "ELS informativo/não conclusivo ou a verificar": "SLS check is informative/non-conclusive; detailed verification is required",
    "não conclusivo": "non-conclusive",
    # reinforcement wording
    "cantos": "corner bars",
    "faces b": "b-faces",
    "faces h": "h-faces",
    "distribuídos no perímetro": "distributed around the perimeter",
    "estribos": "links",
    "grampo(s) intermédio(s)": "intermediate cross-tie(s)",
    "por nível": "per link level",
    "sem grampos intermédios": "no intermediate cross-ties",
    "Solução": "Reinforcement arrangement",
    "Solução adoptada": "Adopted reinforcement arrangement",
    "Solução adotada": "Adopted reinforcement arrangement",
    "Prumada": "Column line",
    "Piso": "Storey",
    "Secção [cm]": "Section [cm]",
    "N.º combinações/tramo": "No. of combinations/segment",
    "Ordem na prumada": "Order in column line",
    "Tramo": "Segment",
}


def _rc13_rewrite_en_text(value):
    if value is None:
        return value
    try:
        if isinstance(value, float) and not math.isfinite(value):
            return ""
    except Exception:
        pass
    s = str(value)
    if not s:
        return s
    out = s
    # longer phrases first
    for pt, en in sorted(_RC13_EN_TERMS.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = out.replace(pt, en)
    # common fragments produced by older runtime patches
    out = out.replace(" | ", " | ")
    out = out.replace("verificação/dimensionamento", "detailed design check")
    out = out.replace("pormenorização", "detailing")
    out = out.replace("armadura", "reinforcement")
    out = out.replace("Armadura", "Reinforcement")
    out = out.replace("betão", "concrete")
    out = out.replace("Betão", "Concrete")
    out = out.replace("esforço transverso", "shear")
    out = out.replace("Esforço transverso", "Shear")
    out = out.replace("torção", "torsion")
    out = out.replace("Torção", "Torsion")
    out = out.replace("fluência", "creep")
    out = out.replace("Fluência", "Creep")
    out = out.replace("combinação", "combination")
    out = out.replace("Combinação", "Combination")
    out = out.replace("caso", "case")
    out = out.replace("Caso", "Case")
    out = out.replace("prumada", "column line")
    out = out.replace("Prumada", "Column line")
    out = out.replace("tramo", "segment")
    out = out.replace("Tramo", "Segment")
    out = out.replace("PISO", "STOREY")
    # clean bilingual leftovers
    out = out.replace("Reinforcement transversal", "transverse reinforcement")
    out = out.replace("reinforcement transversal", "transverse reinforcement")
    out = out.replace("calculation engine structuralcodes", "structuralcodes calculation engine")
    return out


# add/override exact phrases in previous localisation maps when present
try:
    _RC11_EXACT.update({
        "Instruções de utilização and tabela tipo": "User guidance and input-table format",
        "Instruções de utilização e tabela tipo": "User guidance and input-table format",
        "Estratégia de reinforcement": "Reinforcement strategy",
        "Diagnóstico and auditoria": "Diagnostics and audit trail",
        "Classe desenv.": "Development class",
        "Nível de detalhe": "Report detail level",
        "lido da tabela (coluna Material)": "Concrete grade detected from the Material column",
    })
except Exception:
    pass


# ---------------------------------------------------------------------------
# Practical reinforcement layout policy
# ---------------------------------------------------------------------------

def _rc13_layout_phi_max(layout):
    vals = []
    for attr in ["phi_long_mm", "phi_corner_mm", "phi_face_mm"]:
        try:
            v = float(getattr(layout, attr))
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    return max(vals) if vals else 0.0


def _rc13_layout_phi_min(layout):
    vals = []
    for attr in ["phi_long_mm", "phi_corner_mm", "phi_face_mm"]:
        try:
            v = float(getattr(layout, attr))
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    return min(vals) if vals else 0.0


def _rc13_practical_layout_score(layout, as_target: float, b_mm: float, h_mm: float):
    """Practical ranking for building column reinforcement.

    The score penalises very large bars and highly mixed arrangements. Ø32 is not
    part of the normal building-column catalogue; it should only be reached by a
    special user decision, not by the default automatic search.
    """
    asprov = float(getattr(layout, "as_prov_mm2", 0.0) or 0.0)
    n = int(getattr(layout, "n_total", 999) or 999)
    phi_max = _rc13_layout_phi_max(layout)
    phi_min = _rc13_layout_phi_min(layout)
    excess = max(0.0, asprov - float(as_target or 0.0))
    deficit = max(0.0, float(as_target or 0.0) - asprov)
    mixed = max(0.0, phi_max - phi_min)
    # practical penalties
    p32 = 100000.0 if phi_max >= 32.0 else 0.0
    p25 = 1200.0 if phi_max > 25.0 else 0.0
    p_large = max(0.0, phi_max - 20.0) * 180.0
    p_mixed = mixed * 90.0
    p_many = max(0, n - 12) * 25.0
    # prefer enough bars around the perimeter to avoid corner-only heavy layouts
    p_few_large = 600.0 if (phi_max >= 25.0 and n <= 4) else 0.0
    return (p32, deficit, p25 + p_large + p_mixed + p_few_large, excess, p_many, asprov, n, phi_max)

# Override the global score used by the v5.6/v6 design routine.
_v56_layout_score = _rc13_practical_layout_score


def _rc13_constructive_layouts(self, b_mm, h_mm, is_circular=False):
    """Default practical catalogue without Ø32.

    Ø32 is deliberately excluded from the automatic catalogue. For ordinary
    building columns, the automatic design should first try additional perimeter
    bars with Ø16/Ø20/Ø25 rather than jumping to Ø32 corner bars.
    """
    if is_circular:
        layouts = list(_old_build_candidate_layouts_v45_base(self, b_mm, h_mm, is_circular=True)) if "_old_build_candidate_layouts_v45_base" in globals() else []
        return [ly for ly in layouts if _rc13_layout_phi_max(ly) <= 25.0 + 1e-9]
    max_y, max_z = self.max_bars_per_face(b_mm, h_mm, is_circular=False)
    max_y = max(2, int(max_y)); max_z = max(2, int(max_z))
    corner_diams = [10.0, 12.0, 16.0, 20.0, 25.0]
    face_diams = [10.0, 12.0, 16.0, 20.0, 25.0]
    layouts = []
    seen = set()
    def _add(ly):
        try:
            if not ly.clear_spacing_ok():
                return
            ok_spacing, _clear, _req = _v56_clear_spacing_from_layout(ly)
            if not ok_spacing:
                return
            sig = _v56_layout_signature(ly)
            if sig in seen:
                return
            seen.add(sig); layouts.append(ly)
        except Exception:
            return
    for pc in corner_diams:
        _add(MixedLayout(pc, pc, 0, 0, b_mm, h_mm, self.cover_mm, self.choose_stirrup(pc)))
    for pc in corner_diams:
        for pf in face_diams:
            # allow slightly smaller face bars, but avoid very uneven layouts where possible
            if pf > pc:
                continue
            phi_st = self.choose_stirrup(pc)
            for ey in range(0, max_y - 1):
                for ez in range(0, max_z - 1):
                    if ey == 0 and ez == 0:
                        continue
                    ly = MixedLayout(pc, pf, ey, ez, b_mm, h_mm, self.cover_mm, phi_st)
                    if ly.n_bars_y > max_y or ly.n_bars_z > max_z:
                        continue
                    if ly.n_total > 20:
                        continue
                    _add(ly)
    # uniform alternatives, excluding Ø32
    try:
        for ly in list(_old_build_candidate_layouts_v45_base(self, b_mm, h_mm, is_circular=False)):
            if int(getattr(ly, "n_total", 0)) <= 20 and _rc13_layout_phi_max(ly) <= 25.0 + 1e-9:
                _add(ly)
    except Exception:
        pass
    layouts.sort(key=lambda ly: _rc13_practical_layout_score(ly, 0.0, b_mm, h_mm))
    return layouts

ColumnDesigner.build_candidate_layouts = _rc13_constructive_layouts

# Also keep the designer's base catalogue within the normal practical range.
_rc13_prev_designer_init = ColumnDesigner.__init__
def _rc13_designer_init(self, *args, **kwargs):
    _rc13_prev_designer_init(self, *args, **kwargs)
    try:
        self.long_diams = [10.0, 12.0, 16.0, 20.0, 25.0]
    except Exception:
        pass
ColumnDesigner.__init__ = _rc13_designer_init


# ---------------------------------------------------------------------------
# Summary-level rationalisation: same column line where practical
# ---------------------------------------------------------------------------

def _rc13_as_value(row):
    for c in ["as_prov_mm2", "As,prov", "As_prov"]:
        try:
            v = float(row.get(c, 0.0) or 0.0)
            if v > 0:
                return v
        except Exception:
            pass
    return 0.0


def _rc13_solution_value(row):
    for c in ["solucao_completa", "solucao", "Solução", "Reinforcement arrangement"]:
        try:
            v = str(row.get(c, "") or "").strip()
            if v:
                return v
        except Exception:
            pass
    return ""


def _rc13_rationalise_summary(summary):
    if summary is None or getattr(summary, "empty", True):
        return summary
    out = summary.copy()
    if "Prumada" not in out.columns:
        out["Prumada"] = out.apply(_rc12_prumada, axis=1) if "_rc12_prumada" in globals() else out.get("name", "")
    if "Piso" not in out.columns:
        out["Piso"] = out.apply(_rc12_storey, axis=1) if "_rc12_storey" in globals() else out.get("story", "")
    out["_section_signature_rc13"] = out.apply(_rc12_section_signature, axis=1) if "_rc12_section_signature" in globals() else out.apply(lambda r: f"{r.get('b_cm','')}x{r.get('h_cm','')}|{r.get('material','')}", axis=1)
    out["Solução local"] = out.apply(_rc13_solution_value, axis=1)
    out["As local [mm²]"] = out.apply(_rc13_as_value, axis=1)
    out["Solução adoptada"] = out["Solução local"]
    out["Critério de uniformização"] = "Solução local mantida."
    for _, idxs in out.groupby(["Prumada", "_section_signature_rc13"], dropna=False).groups.items():
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
            # unify only if the over-reinforcement is within a practical band;
            # otherwise keep a local change to avoid a wasteful column schedule.
            ratio = max_as / max(local_as, 1e-9)
            if ratio <= 1.60:
                out.at[idx, "Solução adoptada"] = max_sol
                out.at[idx, "Critério de uniformização"] = "Uniformizada com a solução governante da mesma prumada/secção."
                try:
                    out.at[idx, "Solução"] = max_sol
                    out.at[idx, "solucao"] = max_sol
                    out.at[idx, "solucao_completa"] = max_sol
                except Exception:
                    pass
            else:
                out.at[idx, "Critério de uniformização"] = "Solução local mantida para evitar excesso de armadura."
    return out.drop(columns=["_section_signature_rc13"], errors="ignore")

_rc13_prev_build_summary = ColumnsEC2App.build_summary_by_member
def _rc13_build_summary(self, results):
    base = _rc13_prev_build_summary(self, results) if callable(_rc13_prev_build_summary) else pd.DataFrame()
    return _rc13_rationalise_summary(base)
ColumnsEC2App.build_summary_by_member = _rc13_build_summary


# ---------------------------------------------------------------------------
# Display/report patches
# ---------------------------------------------------------------------------

def _rc13_display_df(app, df):
    if df is None or getattr(df, "empty", True) or not _rc13_is_en(app):
        return df
    out = df.copy()
    out.columns = [_rc13_rewrite_en_text(c) for c in out.columns]
    # Translate object cells only; keep numeric values untouched.
    for c in out.columns:
        try:
            if out[c].dtype == object:
                out[c] = out[c].map(_rc13_rewrite_en_text)
        except Exception:
            pass
    return out

_rc13_prev_show_df = ColumnsEC2App.show_df
def _rc13_show_df(self, tree, df):
    return _rc13_prev_show_df(self, tree, _rc13_display_df(self, df))
ColumnsEC2App.show_df = _rc13_show_df


def _rc13_report_lines_en(app, df):
    source = df if df is not None and not getattr(df, "empty", True) else getattr(app, "df_results", pd.DataFrame())
    if source is None or source.empty:
        return "No design results are available. Import the input table and run the design check."
    n_total = len(getattr(app, "df_results", source))
    try:
        n_fail = int(getattr(app, "df_results", source).get("estado_global", getattr(app, "df_results", source).get("status", pd.Series(dtype=str))).astype(str).str.contains("Falha|Failure|Não conforme|Not compliant", regex=True, na=False).sum())
        n_warn = int(getattr(app, "df_results", source).get("estado_global", getattr(app, "df_results", source).get("status", pd.Series(dtype=str))).astype(str).str.contains("Aviso|Warning|Verificar|Check", regex=True, na=False).sum())
    except Exception:
        n_fail = 0; n_warn = 0
    lines = [
        f"ColumnsEC2 {APP_VERSION}\n",
        "Technical report — reinforced-concrete column design results\n\n",
        f"Analysed design cases: {n_total} | Warnings: {n_warn} | Blocking failures: {n_fail}\n\n",
    ]
    for _, r in source.head(80).iterrows():
        col = r.get("Prumada", r.get("name", r.get("member", "")))
        storey = r.get("Piso", r.get("story", ""))
        member = r.get("member", "")
        case = r.get("case", "")
        eta = r.get("η_NMyMz", r.get("eta_NMyMz", r.get("utilizacao", "")))
        try:
            eta_txt = f"{float(eta):.3f}"
        except Exception:
            eta_txt = str(eta)
        sol = r.get("Solução adoptada", r.get("Solução", r.get("solucao_completa", r.get("solucao", ""))))
        decision = r.get("decisao_tecnica", r.get("design_decision", ""))
        warning = r.get("warning_reason", "")
        failure = r.get("failure_reason", "")
        lines.append(f"Column line {col} | Storey {storey} | Member {member} | Case {case}\n")
        lines.append(f"  NEd={_finite(r.get('n_ed_kN'),0):.2f} kN | My,Ed={_finite(r.get('my_ed_kNm'),0):.2f} kNm | Mz,Ed={_finite(r.get('mz_ed_kNm'),0):.2f} kNm | η_NMyMz={eta_txt}\n")
        lines.append(f"  Adopted reinforcement: {_rc13_rewrite_en_text(sol)}\n")
        if decision:
            lines.append(f"  Engineering decision: {_rc13_rewrite_en_text(decision)}\n")
        if warning:
            lines.append(f"  Technical warning: {_rc13_rewrite_en_text(warning)}\n")
        if failure:
            lines.append(f"  Blocking issue: {_rc13_rewrite_en_text(failure)}\n")
        lines.append("\n")
    return "".join(lines)

_rc13_prev_update_report = ColumnsEC2App.update_report
def _rc13_update_report(self):
    if not _rc13_is_en(self):
        return _rc13_prev_update_report(self)
    try:
        self.report_txt.config(state="normal")
        self.report_txt.delete("1.0", "end")
        src = self.df_summary if getattr(self, "df_summary", None) is not None and not self.df_summary.empty else getattr(self, "df_results", pd.DataFrame())
        self.report_txt.insert("1.0", _rc13_report_lines_en(self, src))
    except Exception:
        try:
            return _rc13_prev_update_report(self)
        except Exception:
            pass
ColumnsEC2App.update_report = _rc13_update_report

# keep language hook effective
_rc13_prev_apply_language = getattr(ColumnsEC2App, "apply_language", None)
def _rc13_apply_language(self):
    out = _rc13_prev_apply_language(self) if callable(_rc13_prev_apply_language) else None
    try:
        # refresh all visible tables with display-level English technical wording
        for attr, dfattr in [
            ("tree_validation", "df_validation"), ("tree_results", "df_results"), ("tree_summary", "df_summary"),
            ("tree_failures", "df_failures"), ("tree_shortlists", None), ("tree_notes", "df_notes")
        ]:
            if hasattr(self, attr):
                df = self.build_shortlists_df() if dfattr is None and hasattr(self, "build_shortlists_df") else getattr(self, dfattr, pd.DataFrame())
                self.show_df(getattr(self, attr), df)
        self.update_report()
    except Exception:
        pass
    return out
ColumnsEC2App.apply_language = _rc13_apply_language

# launcher hook
_prev_v092_hook = globals().get("_v092_apply_language_title")
def _v092_apply_language_title(app):
    try:
        if callable(_prev_v092_hook):
            _prev_v092_hook(app)
    except Exception:
        pass
    try:
        app.apply_language()
    except Exception:
        pass

