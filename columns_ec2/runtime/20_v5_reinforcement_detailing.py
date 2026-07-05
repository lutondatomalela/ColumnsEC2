# -*- coding: utf-8 -*-
# Auto-split from ColumnsEC2 v0.9 RC8.
# This module is executed in the shared runtime namespace by columns_ec2.runtime.loader.
# Keep execution order defined in columns_ec2/runtime/manifest.py.

APP_VERSION = "v4.5"
APP_XLSX_DESCRIPTION = (
    "Workbook de cálculo com entrada de dados, validação, envolvente ELU, resultados por prumada, "
    "ELU/ELS/V/T/pormenorização, shortlists inteligentes, correcções interactivas, DXF e metadados."
)

# --------------------------- aço ---------------------------
def steel_props(fyk: float = 500.0, gamma_s: float = 1.15) -> Dict[str, float]:
    """Propriedades de cálculo do aço. Es fixado em 210 GPa conforme opção do programa."""
    return {"fyd": fyk / gamma_s, "Es": 210000.0}

globals()["steel_props"] = steel_props


# --------------------------- materiais obrigatórios ---------------------------
def _valid_concrete_class_v45(value) -> bool:
    return bool(re.search(r"C\s*\d+\s*/\s*\d+", str(value or ""), re.I))


def _ask_material_for_missing_v45(self, df: pd.DataFrame) -> pd.DataFrame:
    """Se a classe de betão estiver ausente/inválida, pergunta ao utilizador em vez de assumir silenciosamente."""
    from tkinter import simpledialog
    out = df.copy()
    if "material" not in out.columns:
        out["material"] = ""
    mask = ~out["material"].astype(str).map(_valid_concrete_class_v45)
    n_bad = int(mask.sum())
    if n_bad <= 0:
        out["material_user_supplied"] = "Não"
        return out
    prompt = (
        f"Foram encontradas {n_bad} linhas sem classe de betão válida na coluna Material.\n\n"
        "Indique a classe de betão a adoptar para essas linhas, no formato C30/37, C40/50, etc."
    )
    cls = simpledialog.askstring("Classe de betão em falta", prompt, initialvalue="C30/37", parent=self)
    if cls is None:
        raise ValueError("A classe de betão é obrigatória quando a coluna Material está vazia/inválida.")
    cls = cls.strip().upper().replace(" ", "")
    if not _valid_concrete_class_v45(cls):
        raise ValueError(f"Classe de betão inválida: {cls}. Use o formato C30/37, C40/50, etc.")
    out.loc[mask, "material"] = cls
    out["material_user_supplied"] = "Não"
    out.loc[mask, "material_user_supplied"] = "Sim"
    return out


_old_load_df_v45_base = ColumnsEC2App.load_df

def _load_df_v45(self, df: pd.DataFrame, source: str = ""):
    df = _ask_material_for_missing_v45(self, df)
    _old_load_df_v45_base(self, df, source)
    try:
        supplied = int((self.df_input.get("material_user_supplied", pd.Series(dtype=str)).astype(str) == "Sim").sum())
        if supplied:
            self.status_var.set(f"Dados carregados. Classe de betão especificada pelo utilizador em {supplied} linhas.")
    except Exception:
        pass

ColumnsEC2App.load_df = _load_df_v45


# --------------------------- layouts mistos práticos ---------------------------
@dataclass
class MixedLayout:
    phi_corner_mm: float
    phi_face_mm: float
    n_face_y_extra: int
    n_face_z_extra: int
    b_mm: float
    h_mm: float
    cover_mm: float
    phi_st_mm: float = 8.0

    @property
    def phi_long_mm(self) -> float:
        return max(self.phi_corner_mm, self.phi_face_mm)

    @property
    def n_bars_y(self) -> int:
        return 2 + int(self.n_face_y_extra)

    @property
    def n_bars_z(self) -> int:
        return 2 + int(self.n_face_z_extra)

    @property
    def n_total(self) -> int:
        return 4 + 2 * int(self.n_face_y_extra) + 2 * int(self.n_face_z_extra)

    @property
    def as_prov_mm2(self) -> float:
        return 4 * bar_area_mm2(self.phi_corner_mm) + max(0, self.n_total - 4) * bar_area_mm2(self.phi_face_mm)

    @property
    def layout_type(self) -> str:
        return "mixed"

    @property
    def description(self) -> str:
        n_face = max(0, self.n_total - 4)
        if n_face:
            return f"4Ø{int(self.phi_corner_mm)} + {n_face}Ø{int(self.phi_face_mm)}"
        return f"4Ø{int(self.phi_corner_mm)}"

    def clear_spacing_ok(self, agg_mm: float = 20.0, min_clear_mm: float = 20.0) -> bool:
        req = max(min_clear_mm, self.phi_long_mm, agg_mm + 5.0)
        edge = self.cover_mm + self.phi_st_mm + self.phi_long_mm / 2.0
        ok_y = True
        ok_z = True
        if self.n_bars_y > 1:
            span = self.b_mm - 2.0 * edge
            ctc = span / max(self.n_bars_y - 1, 1)
            ok_y = (ctc - self.phi_long_mm) >= req
        if self.n_bars_z > 1:
            span = self.h_mm - 2.0 * edge
            ctc = span / max(self.n_bars_z - 1, 1)
            ok_z = (ctc - self.phi_long_mm) >= req
        return bool(ok_y and ok_z)


def _layout_bar_points_v45(layout) -> List[Tuple[float, float, float]]:
    """Devolve (y,z,phi) para layouts uniformes e mistos."""
    edge = layout.cover_mm + layout.phi_st_mm + layout.phi_long_mm / 2.0
    y_left = -layout.b_mm / 2.0 + edge
    y_right = layout.b_mm / 2.0 - edge
    z_bot = -layout.h_mm / 2.0 + edge
    z_top = layout.h_mm / 2.0 - edge
    if isinstance(layout, MixedLayout):
        pts = [
            (y_left, z_top, layout.phi_corner_mm),
            (y_right, z_top, layout.phi_corner_mm),
            (y_left, z_bot, layout.phi_corner_mm),
            (y_right, z_bot, layout.phi_corner_mm),
        ]
        if layout.n_face_y_extra > 0:
            for i in range(layout.n_face_y_extra):
                y = y_left + (i + 1) * (y_right - y_left) / (layout.n_face_y_extra + 1)
                pts.append((y, z_top, layout.phi_face_mm))
                pts.append((y, z_bot, layout.phi_face_mm))
        if layout.n_face_z_extra > 0:
            for i in range(layout.n_face_z_extra):
                z = z_bot + (i + 1) * (z_top - z_bot) / (layout.n_face_z_extra + 1)
                pts.append((y_left, z, layout.phi_face_mm))
                pts.append((y_right, z, layout.phi_face_mm))
        return [(float(y), float(z), float(phi)) for y, z, phi in pts]
    # Layout uniforme existente
    ys = [y_left] if layout.n_bars_y == 1 else [
        y_left + i * (y_right - y_left) / max(layout.n_bars_y - 1, 1)
        for i in range(layout.n_bars_y)
    ]
    zs = [z_bot] if layout.n_bars_z == 1 else [
        z_bot + i * (z_top - z_bot) / max(layout.n_bars_z - 1, 1)
        for i in range(layout.n_bars_z)
    ]
    pts = []
    for y in ys:
        pts.append((float(y), float(z_top), float(layout.phi_long_mm)))
        pts.append((float(y), float(z_bot), float(layout.phi_long_mm)))
    for z in zs[1:-1]:
        pts.append((float(y_left), float(z), float(layout.phi_long_mm)))
        pts.append((float(y_right), float(z), float(layout.phi_long_mm)))
    unique = []
    seen = set()
    for p in pts:
        key = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _section_response_v45(self, layout, n_ed_kN: float, angle_rad: float, c_mm: float, fcd: float, fyd: float, Es: float):
    eps_cu = 0.0035
    pts = _layout_bar_points_v45(layout)
    ca = math.cos(angle_rad)
    sa = math.sin(angle_rad)

    def ucoord(y, z):
        return y * ca + z * sa

    corners = [
        (-layout.b_mm / 2.0, -layout.h_mm / 2.0),
        (-layout.b_mm / 2.0,  layout.h_mm / 2.0),
        ( layout.b_mm / 2.0, -layout.h_mm / 2.0),
        ( layout.b_mm / 2.0,  layout.h_mm / 2.0),
    ]
    u_max = max(ucoord(y, z) for y, z in corners)
    u_na = u_max - c_mm
    ny = max(10, int(layout.b_mm / 35.0))
    nz = max(10, int(layout.h_mm / 35.0))
    dy = layout.b_mm / ny
    dz = layout.h_mm / nz
    dA = dy * dz
    N = My = Mz = 0.0
    for iy in range(ny):
        y = -layout.b_mm / 2.0 + (iy + 0.5) * dy
        for iz in range(nz):
            z = -layout.h_mm / 2.0 + (iz + 0.5) * dz
            u = ucoord(y, z)
            if u <= u_na:
                continue
            eps = eps_cu * (u - u_na) / max(c_mm, 1e-9)
            sig = 0.0 if eps <= 0.0 else min(fcd, fcd * eps / 0.002)
            Fc = sig * dA
            N += Fc
            My += Fc * z
            Mz += Fc * y
    for y, z, phi in pts:
        u = ucoord(y, z)
        eps_s = eps_cu * (u - u_na) / max(c_mm, 1e-9)
        sig_s = max(-fyd, min(fyd, Es * eps_s))
        Fs = sig_s * bar_area_mm2(phi)
        N += Fs
        My += Fs * z
        Mz += Fs * y
    return N / 1000.0, abs(My) / 1e6, abs(Mz) / 1e6

ColumnDesigner.section_response = _section_response_v45


_old_build_candidate_layouts_v45_base = ColumnDesigner.build_candidate_layouts

def _layout_practical_score_v45(ly, as_target=0.0):
    mixed_penalty = 20 if isinstance(ly, MixedLayout) else 0
    # Prático: cantos mais fortes + varões menores nas faces é aceitável; demasiados varões penaliza.
    return (
        abs(float(getattr(ly, "as_prov_mm2", 0.0)) - float(as_target or 0.0)),
        mixed_penalty,
        getattr(ly, "n_total", 999),
        getattr(ly, "phi_long_mm", 999),
        float(getattr(ly, "as_prov_mm2", 0.0)),
    )


def _build_candidate_layouts_v45(self, b_mm, h_mm, is_circular=False):
    base = list(_old_build_candidate_layouts_v45_base(self, b_mm, h_mm, is_circular=is_circular))
    if is_circular:
        return base
    max_y, max_z = self.max_bars_per_face(b_mm, h_mm, is_circular=False)
    mixed = []
    corner_diams = [16.0, 20.0, 25.0, 32.0]
    face_diams = [10.0, 12.0, 16.0, 20.0]
    for pc in corner_diams:
        for pf in face_diams:
            if pf > pc:
                continue
            phi_st = self.choose_stirrup(pc)
            for ey in range(0, max(0, max_y - 2) + 1):
                for ez in range(0, max(0, max_z - 2) + 1):
                    if ey == 0 and ez == 0:
                        continue
                    ly = MixedLayout(pc, pf, ey, ez, b_mm, h_mm, self.cover_mm, phi_st)
                    if ly.n_total < 4:
                        continue
                    if ly.clear_spacing_ok():
                        mixed.append(ly)
    # remove duplicados por descrição/área/nº varões
    all_layouts = base + mixed
    unique = []
    seen = set()
    for ly in all_layouts:
        key = (round(float(getattr(ly, "as_prov_mm2", 0.0)), 2), getattr(ly, "n_total", None), getattr(ly, "phi_long_mm", None), getattr(ly, "description", ""))
        if key not in seen:
            seen.add(key)
            unique.append(ly)
    unique.sort(key=lambda x: (float(getattr(x, "as_prov_mm2", 0.0)), getattr(x, "n_total", 999), getattr(x, "phi_long_mm", 999)))
    return unique

ColumnDesigner.build_candidate_layouts = _build_candidate_layouts_v45


def smart_shortlist_v45(candidates: List, as_req_mm2: float, max_n: int = 30) -> List:
    """Shortlist prática: próxima de As_req, com alternativas uniformes e mistas, e sem ficar limitada a 8 soluções."""
    if not candidates:
        return []
    as_req = float(as_req_mm2 or 0.0)
    above = [c for c in candidates if float(getattr(c, "as_prov_mm2", 0.0)) >= as_req]
    pool = above if above else list(candidates)
    pool = sorted(pool, key=lambda ly: _layout_practical_score_v45(ly, as_req))
    # garantir diversidade: inclui soluções uniformes e mistas, e diâmetros diferentes
    selected = []
    seen = set()
    for ly in pool:
        sig = (isinstance(ly, MixedLayout), getattr(ly, "phi_long_mm", None), getattr(ly, "n_total", None), round(float(getattr(ly, "as_prov_mm2", 0.0)), 1))
        if sig in seen:
            continue
        selected.append(ly)
        seen.add(sig)
        if len(selected) >= max_n:
            break
    return selected

globals()["smart_shortlist_v45"] = smart_shortlist_v45


# --------------------------- descrição de armadura nos resultados ---------------------------
_old_design_one_v45_base = ColumnDesigner.design_one

def _design_one_v45(self, row: pd.Series, prebuilt_candidates=None):
    out = _old_design_one_v45_base(self, row, prebuilt_candidates=prebuilt_candidates)
    if not isinstance(out, dict):
        return out
    # Se a solução corresponder a uma área mista conhecida, tentar melhorar a descrição textual.
    try:
        b_mm = _finite(out.get("b_cm"), 0.0) * 10.0
        h_mm = _finite(out.get("h_cm"), 0.0) * 10.0
        asprov = _finite(out.get("as_prov_mm2"), 0.0)
        n_total = int(_finite(out.get("n_total"), 0))
        if b_mm > 0 and h_mm > 0 and asprov > 0:
            layouts = self.build_candidate_layouts(b_mm, h_mm, is_circular=False)
            close = [ly for ly in layouts if abs(_finite(getattr(ly, "as_prov_mm2", 0.0)) - asprov) < 0.75 and int(getattr(ly, "n_total", 0)) == n_total]
            # Preferir descrição mista se existir; senão manter a existente.
            close_mixed = [ly for ly in close if isinstance(ly, MixedLayout)]
            ly = close_mixed[0] if close_mixed else (close[0] if close else None)
            if ly is not None and hasattr(ly, "description"):
                s = _finite(out.get("s_st_mm"), 0.0)
                phi_st = _finite(out.get("phi_st_mm"), 8.0)
                out["solucao"] = f"{ly.description} + estribos Ø{int(phi_st)}//{s/10:.1f} cm"
                out["layout_type"] = "misto" if isinstance(ly, MixedLayout) else "uniforme"
                out["layout_description"] = ly.description
    except Exception:
        pass
    return out

ColumnDesigner.design_one = _design_one_v45


# --------------------------- envolvente ELU prática ---------------------------
def _case_is_service_v45(case_value) -> bool:
    s = str(case_value or "").lower()
    return any(k in s for k in ["els", "serv", "service", "sls", "freq", "quase", "qp", "rare", "rara"])


def _governing_envelope_score_v45(df: pd.DataFrame) -> pd.Series:
    vals = pd.DataFrame(index=df.index)
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        vals[c] = pd.to_numeric(df.get(c, pd.Series(index=df.index, dtype=float)), errors="coerce").abs().fillna(0.0)
    # score de interacção para seleccionar combinações críticas sem calcular todas
    return vals["fx"] * 0.20 + vals["my"] + vals["mz"] + 0.35 * vals["mx"] + 0.10 * (vals["fy"] + vals["fz"])


def reduce_to_governing_cases(df: pd.DataFrame) -> pd.DataFrame:
    """Redução por envolvente: conserva apenas combinações ELU governantes por member/prumada."""
    if df is None or df.empty:
        return df
    work = df.copy()
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in work.columns:
            work[c] = 0.0
    work["_score_v45"] = _governing_envelope_score_v45(work)
    selected = set()
    group_cols = [c for c in ["member", "name"] if c in work.columns]
    if not group_cols:
        group_cols = ["member"] if "member" in work.columns else []
    groups = work.groupby(group_cols, dropna=False) if group_cols else [(None, work)]
    for _, grp in groups:
        if grp.empty:
            continue
        # descartar ELS se houver casos claramente ELU no mesmo grupo; ELS é tratado pelo módulo ELS.
        non_service = grp[~grp.get("case", pd.Series(index=grp.index, dtype=str)).map(_case_is_service_v45)] if "case" in grp.columns else grp
        g = non_service if not non_service.empty else grp
        selected.add(g["_score_v45"].idxmax())
        for c in ["fx", "my", "mz", "mx", "fy", "fz"]:
            vals = pd.to_numeric(g[c], errors="coerce").abs().fillna(0.0)
            if not vals.empty:
                selected.add(vals.idxmax())
        # excentricidades grandes
        fx = pd.to_numeric(g["fx"], errors="coerce").abs().replace(0, 1e-9)
        for c in ["my", "mz"]:
            vals = pd.to_numeric(g[c], errors="coerce").abs() / fx
            if not vals.empty:
                selected.add(vals.idxmax())
    out = work.loc[sorted(selected)].copy().drop(columns=["_score_v45"], errors="ignore")
    out = out.sort_values([c for c in ["name", "member", "case"] if c in out.columns]).reset_index(drop=True)
    return out

globals()["reduce_to_governing_cases"] = reduce_to_governing_cases


# --------------------------- pormenorização: distinguir falha bloqueante de aviso ---------------------------
_old_detailing_check_v45_base = detailing_check_v4

def detailing_check_v4(result: dict) -> dict:
    det = _old_detailing_check_v45_base(result)
    issues = str(det.get("detailing_issues", "") or "")
    # Grampos/estribos intermédios são recomendação construtiva, não falha bloqueante automática.
    if det.get("detailing_status") == "Não conforme" and issues and all(k in issues.lower() for k in ["prever", "interm"]):
        det["detailing_status"] = "Verificar"
    # Notas adicionais para layouts mistos.
    if str(result.get("layout_type", "")).lower() == "misto":
        note = "layout misto com varões de canto e de face; confirmar simetria e amarração em projecto"
        det["detailing_issues"] = (det.get("detailing_issues", "-") if det.get("detailing_issues") != "-" else "")
        det["detailing_issues"] = "; ".join([x for x in [det.get("detailing_issues", "").strip("; "), note] if x])
        if det.get("detailing_status") == "OK":
            det["detailing_status"] = "OK"
    return det

globals()["detailing_check_v4"] = detailing_check_v4


# --------------------------- política de falhas: avisos vs bloqueantes ---------------------------
_old_enrich_failures_v45_base = enrich_failures_v43

def enrich_failures_v43(df: pd.DataFrame) -> pd.DataFrame:
    out = _old_enrich_failures_v45_base(df)
    if out is None or out.empty:
        return out
    # VEd > VRdc mas VEd <= VRdmax: dimensiona estribos; não é falha bloqueante.
    shear_txt = out.get("shear_status", pd.Series(index=out.index, dtype=str)).astype(str)
    shear_y = out.get("shear_status_y", pd.Series(index=out.index, dtype=str)).astype(str)
    shear_z = out.get("shear_status_z", pd.Series(index=out.index, dtype=str)).astype(str)
    tors_txt = out.get("torsion_status", pd.Series(index=out.index, dtype=str)).astype(str)
    non_blocking_v = (shear_txt.str.contains("Verificar|Requer", case=False, na=False) | shear_y.str.contains("Requer", case=False, na=False) | shear_z.str.contains("Requer", case=False, na=False)) & ~(shear_y.str.contains("Não conforme", case=False, na=False) | shear_z.str.contains("Não conforme", case=False, na=False))
    non_blocking_t = tors_txt.str.contains("Requer", case=False, na=False) & ~tors_txt.str.contains("Não conforme", case=False, na=False)
    mask_warn = (non_blocking_v | non_blocking_t) & ~out.get("failure_type", pd.Series(index=out.index, dtype=str)).astype(str).isin(["dados_incompletos", "armadura_insuficiente", "resistencia_biaxial"])
    if mask_warn.any():
        out.loc[mask_warn, "failure_severity"] = "Aviso"
        out.loc[mask_warn, "review_priority"] = "Média"
        out.loc[mask_warn, "design_decision"] = "Aceitável apenas após dimensionamento/revisão das verificações complementares"
        out.loc[mask_warn, "failure_action"] = "Dimensionar/rever estribos, torção e pormenorização complementar; não é falha resistente bloqueante se VRd,max/TRd,max verificarem."
        # manter status Falha se existir outra razão bloqueante; caso contrário converter em Aviso.
        reason = out.get("failure_reason", pd.Series(index=out.index, dtype=str)).astype(str)
        only_complementary = ~reason.str.contains("biaxial|armadura|dados|As,req|pormenorização impossível", case=False, na=False)
        out.loc[mask_warn & only_complementary, "status"] = "Aviso"
    out["failure_summary"] = out.apply(lambda r: f"{r.get('failure_severity','')} | {r.get('failure_type','')} | {r.get('failure_action','')}", axis=1)
    return out

globals()["enrich_failures_v43"] = enrich_failures_v43


# --------------------------- correcção interactiva com barra de estado ---------------------------
def _repair_failures_interactive_v45(self):
    if self.df_results is None or self.df_results.empty:
        messagebox.showwarning("Aviso", "Execute o cálculo antes de corrigir falhas.")
        return
    if getattr(self, "df_calc_input", None) is None or self.df_calc_input.empty:
        messagebox.showwarning("Aviso", "Não existe tabela de cálculo associada aos resultados actuais.")
        return
    res = enrich_failures_v43(self.df_results.copy())
    targets = res[res.apply(_status_is_unresolved_v44, axis=1)].copy()
    if targets.empty:
        messagebox.showinfo("Correcção interactiva", "Não há falhas bloqueantes a corrigir.")
        return
    total = len(targets)
    self.progress_value.set(0)
    self.progress_var.set(f"0 / {total}")
    self.status_var.set(f"Correcção interactiva em curso... 0/{total}")
    self.update_idletasks()
    corrected = []
    corrected_count = warning_count = unresolved_count = 0
    processed = 0
    target_index = set(targets.index)
    for idx, row in res.iterrows():
        if idx not in target_index:
            r = dict(row)
            r.setdefault("auto_repair_applied", "")
            corrected.append(r)
            continue
        processed += 1
        self.progress_var.set(f"{processed} / {total}")
        self.progress_value.set(100.0 * processed / max(total, 1))
        self.status_var.set(f"Correcção interactiva em curso... {processed}/{total} | member {row.get('member','')} caso {row.get('case','')}")
        self.update_idletasks()
        repaired = _try_repair_result_v44(self, row)
        repaired["_original_index"] = idx
        if str(repaired.get("auto_repair_applied", "")) == "Sim" and str(repaired.get("status", "")) == "OK":
            corrected_count += 1
        elif str(repaired.get("status", "")) == "Aviso":
            warning_count += 1
        else:
            unresolved_count += 1
        corrected.append(repaired)
    self.df_results = enrich_failures_v43(pd.DataFrame(corrected))
    _refresh_after_repair_v44(self)
    self.progress_value.set(100)
    self.progress_var.set(f"{total} / {total}")
    self.status_var.set(f"Correcção concluída: {corrected_count} corrigidas; {warning_count} avisos/propostas; {unresolved_count} sem solução automática.")
    messagebox.showinfo("Correcção interactiva concluída", f"Corrigidas: {corrected_count}\nAvisos/propostas: {warning_count}\nSem solução automática: {unresolved_count}")

ColumnsEC2App.repair_failures_interactive = _repair_failures_interactive_v45


# --------------------------- estado final por prumada ---------------------------
_old_run_design_v45_base = ColumnsEC2App.run_design

def _run_design_v45(self):
    _old_run_design_v45_base(self)
    def watcher(tries=0):
        try:
            if getattr(self, "analysis_thread", None) is not None and self.analysis_thread.is_alive() and tries < 600:
                self.after(250, lambda: watcher(tries + 1))
                return
            if self.df_results is not None and not self.df_results.empty:
                res = enrich_failures_v43(self.df_results)
                self.df_results = res
                prumadas = res.get("prumada", res.get("name", res.get("member", pd.Series(dtype=str)))).astype(str).nunique()
                members = res.get("member", pd.Series(dtype=str)).astype(str).nunique()
                n_cases = len(res)
                n_block = int((res.get("failure_severity", pd.Series(dtype=str)).astype(str) == "Bloqueante").sum())
                n_warn = int((res.get("failure_severity", pd.Series(dtype=str)).astype(str) == "Aviso").sum())
                self.status_var.set(f"Cálculo concluído: {n_cases} casos de envolvente; {members} membros; {prumadas} prumadas; {n_block} bloqueantes; {n_warn} avisos.")
                try:
                    self.show_df(self.tree_results, self.df_results)
                    self.update_report()
                except Exception:
                    pass
        except Exception as err:
            self.status_var.set(f"Cálculo concluído com aviso: {err}")
    self.after(700, watcher)

ColumnsEC2App.run_design = _run_design_v45


# --------------------------- notas actualizadas ---------------------------
_old_build_normative_notes_v45_base = ColumnsEC2App.build_normative_notes

def _build_normative_notes_v45(self) -> pd.DataFrame:
    notes = _old_build_normative_notes_v45_base(self).copy()
    extra = pd.DataFrame([
        ("Aço", "Es", "Módulo de elasticidade do aço adoptado: Es = 210 GPa."),
        ("Materiais", "Classe de betão", "A classe de betão deve vir da tabela. Se estiver ausente/inválida, o programa pede a classe ao utilizador antes do cálculo."),
        ("ELU", "Envolvente", "Quando a redução está activa, o programa calcula uma envolvente prática por member/prumada: N, My, Mz, V, T e excentricidades governantes."),
        ("Armaduras", "Shortlist inteligente", "A shortlist considera mais soluções e inclui layouts práticos com varões de canto e varões de face, por exemplo 4Ø25 + 4Ø16."),
        ("Falhas", "Avisos vs bloqueantes", "VEd>VRdc ou torção que requer armadura passam a aviso se VRd,max/TRd,max verificarem; apenas violações resistentes/dados/pormenorização impossível ficam bloqueantes."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True)

ColumnsEC2App.build_normative_notes = _build_normative_notes_v45



# ============================================================
# ColumnsEC2 v4.6 — leitura robusta de texto colado e validação correcta do Material
# ============================================================
APP_VERSION = "v5.3"
APP_XLSX_DESCRIPTION = (
    "Workbook de cálculo com entrada de dados, validação, envolvente ELU, resultados por prumada, "
    "ELU/ELS/V/T/pormenorização, shortlists inteligentes, correcções interactivas, DXF, metadados "
    "e leitura robusta de tabelas coladas."
)

STANDARD_IMPORT_COLUMNS_V46 = [
    "member_case", "fx", "fy", "fz", "mx", "my", "mz", "length", "material",
    "hy", "hz", "vy", "vz", "vpy", "vpz", "ax", "ay", "az", "ix", "iy", "iz", "name"
]

DISPLAY_IMPORT_COLUMNS_V46 = [
    "Member/Node/Case", "FX (kN)", "FY (kN)", "FZ (kN)", "MX (kNm)", "MY (kNm)", "MZ (kNm)",
    "Length (m)", "Material", "HY (cm)", "HZ (cm)", "VY (cm)", "VZ (cm)", "VPY (cm)", "VPZ (cm)",
    "AX (cm2)", "AY (cm2)", "AZ (cm2)", "IX (cm4)", "IY (cm4)", "IZ (cm4)", "Name"
]


def _looks_like_member_case_v46(token: str) -> bool:
    return bool(re.search(r"\d+\s*/\s*\d+\s*/\s*\d+", str(token or "")))


def _parse_whitespace_member_table_v46(text: str) -> pd.DataFrame:
    """
    Parser específico para tabelas copiadas como texto alinhado por espaços.
    Resolve casos do tipo:
        14/  1/ 101 (C) 132,28 -2,38 ... 1,00 C30/37 25,0 40,0 ...
    onde a primeira coluna contém espaços internos.
    """
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "member/node/case" in line.lower() or line.lower().startswith("member/n"):
            continue
        if not re.search(r"^\d+\s*/\s*\d+\s*/\s*\d+", line):
            continue

        m = re.match(r"^\s*(?P<mc>\d+\s*/\s*\d+\s*/\s*\d+(?:\s*\([^)]*\))?)\s+(?P<rest>.+?)\s*$", line)
        if not m:
            continue
        mc = re.sub(r"\s*/\s*", "/", m.group("mc").strip())
        rest = m.group("rest").strip()
        tokens = rest.split()
        if len(tokens) < 8:
            continue

        values = [mc] + tokens
        # Preenche até ao comprimento do modelo.
        values = values[:len(STANDARD_IMPORT_COLUMNS_V46)] + [""] * max(0, len(STANDARD_IMPORT_COLUMNS_V46) - len(values))
        rows.append(values)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=STANDARD_IMPORT_COLUMNS_V46)


def parse_pasted_table_v46(text: str) -> pd.DataFrame:
    """
    Leitura robusta para três cenários:
    1) tabela copiada do Excel com tabs;
    2) CSV/semicolon;
    3) texto alinhado por espaços, comum quando se cola em caixas de texto simples.
    """
    text = str(text or "").strip()
    if not text:
        return pd.DataFrame()

    # 1) Excel/folha de cálculo: tabs preservam a estrutura real.
    for sep in ("\t", ";"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python", dtype=str)
            if len(df.columns) > 1:
                return df
        except Exception:
            pass

    # 2) Parser específico para texto alinhado por espaços.
    df_fixed = _parse_whitespace_member_table_v46(text)
    if not df_fixed.empty:
        return df_fixed

    # 3) Fallback antigo: separação por 2+ espaços.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame()
    rows = [re.split(r"\s{2,}", line) for line in lines]
    if len(rows) < 2:
        return pd.DataFrame()
    header = rows[0]
    body = rows[1:]
    width = len(header)
    body = [r[:width] + [""] * max(0, width - len(r)) for r in body]
    return pd.DataFrame(body, columns=header)


globals()["parse_pasted_table"] = parse_pasted_table_v46


def _normalise_material_string_v46(value) -> str:
    s = str(value or "").strip().upper().replace(" ", "")
    m = re.search(r"C(\d{2,3})/(\d{2,3})", s)
    if m:
        return f"C{m.group(1)}/{m.group(2)}"
    return s


def _valid_concrete_class_v46(value) -> bool:
    return bool(re.fullmatch(r"C\d{2,3}/\d{2,3}", _normalise_material_string_v46(value)))


def _ask_material_for_missing_v46(self, df_clean: pd.DataFrame) -> pd.DataFrame:
    """Pergunta apenas quando a coluna material já foi normalizada e realmente está vazia/inválida."""
    from tkinter import simpledialog
    out = df_clean.copy()
    if "material" not in out.columns:
        out["material"] = ""

    out["material"] = out["material"].map(_normalise_material_string_v46)
    invalid_tokens = {"", "NAN", "NONE", "NULL", "-"}
    mask = out["material"].astype(str).str.upper().isin(invalid_tokens) | ~out["material"].map(_valid_concrete_class_v46)
    n_bad = int(mask.sum())
    out["material_user_supplied"] = "Não"
    if n_bad <= 0:
        return out

    prompt = (
        f"Foram encontradas {n_bad} linhas sem classe de betão válida na coluna Material.\n\n"
        "Indique a classe de betão a adoptar apenas para essas linhas, no formato C30/37, C40/50, etc."
    )
    cls = simpledialog.askstring("Classe de betão em falta", prompt, initialvalue="C30/37", parent=self)
    if cls is None:
        raise ValueError("A classe de betão é obrigatória quando a coluna Material está vazia/inválida.")
    cls = _normalise_material_string_v46(cls)
    if not _valid_concrete_class_v46(cls):
        raise ValueError(f"Classe de betão inválida: {cls}. Use o formato C30/37, C40/50, etc.")
    out.loc[mask, "material"] = cls
    out.loc[mask, "material_user_supplied"] = "Sim"
    return out


def _load_df_v46(self, df: pd.DataFrame, source: str = ""):
    """
    Substitui a rotina v4.5: primeiro normaliza nomes de colunas, só depois valida Material.
    Isto evita pedir a classe de betão quando a tabela tem a coluna Material correctamente preenchida.
    """
    try:
        self.df_raw = df.copy()
        self.df_clean = clean_dataframe(df)
        self.df_clean = _ask_material_for_missing_v46(self, self.df_clean)
        self.df_pair = combine_member_end_actions(self.df_clean)
        self.df_calc_input = pd.DataFrame()
        self.df_results = pd.DataFrame()
        self.df_summary = pd.DataFrame()
        self.df_failures = pd.DataFrame()
        self.df_ok = pd.DataFrame()
        self.df_filtered = pd.DataFrame()
        self.df_validation = self.build_data_validation(pre_calc=True)
        self.df_notes = self.build_normative_notes()
        self.show_df(self.tree_input, self.df_clean)
        self.show_df(self.tree_pairs, self.df_pair)
        self.show_df(self.tree_validation, self.df_validation)
        self.show_df(self.tree_results, self.df_results)
        self.show_df(self.tree_summary, self.df_summary)
        self.show_df(self.tree_failures, self.df_failures)
        self.show_df(self.tree_shortlists, pd.DataFrame())
        self.show_df(self.tree_notes, self.df_notes)
        self.update_report()
        try:
            self.progress_var.set(0.0)
        except Exception:
            pass
        bad_pairs = int((self.df_pair.get("n_nodes_found", pd.Series(dtype=float)).fillna(0).astype(float) < 2).sum()) if not self.df_pair.empty else 0
        supplied = int((self.df_clean.get("material_user_supplied", pd.Series(dtype=str)).astype(str) == "Sim").sum())
        warn = f"; {bad_pairs} pares sem dois nós" if bad_pairs else ""
        mat_msg = f"; betão especificado pelo utilizador em {supplied} linhas" if supplied else "; betão lido da coluna Material"
        self.status_var.set(f"Tabela carregada ({source}): {len(self.df_clean)} linhas; {len(self.df_pair)} pares member/case{warn}{mat_msg}.")
    except Exception as err:
        messagebox.showerror("Erro", f"Não foi possível carregar a tabela.\n\n{err}")
        self.status_var.set("Erro ao carregar a tabela.")


ColumnsEC2App.load_df = _load_df_v46


def _build_normative_notes_v46(self) -> pd.DataFrame:
    try:
        notes = _build_normative_notes_v45(self).copy()
    except Exception:
        notes = pd.DataFrame(columns=["Tema", "Referência", "Nota"])
    extra = pd.DataFrame([
        ("Importação", "Texto colado", "A leitura da caixa de texto suporta tabelas coladas com separadores de tabulação, ponto e vírgula ou texto alinhado por espaços."),
        ("Materiais", "Classe de betão", "A validação da classe de betão é feita depois de normalizar a coluna Material; o programa só pede a classe se a coluna estiver realmente vazia ou inválida."),
        ("Interface", "Tabela", "Após ler a caixa de texto, a pré-visualização deve ser verificada no separador Tabela/Dados importados antes do cálculo."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True).drop_duplicates()

ColumnsEC2App.build_normative_notes = _build_normative_notes_v46



# ============================================================
# v4.7 - grelha editável para tabela colada + parser robusto
# ============================================================
DEFAULT_IMPORT_COLUMNS_V47 = [
    "Member/Node/Case", "FX (kN)", "FY (kN)", "FZ (kN)", "MX (kNm)", "MY (kNm)", "MZ (kNm)",
    "Length (m)", "Material", "HY (cm)", "HZ (cm)", "VY (cm)", "VZ (cm)", "VPY (cm)", "VPZ (cm)",
    "AX (cm2)", "AY (cm2)", "AZ (cm2)", "IX (cm4)", "IY (cm4)", "IZ (cm4)", "Name", "Story"
]


def _is_data_line_v47(line: str) -> bool:
    return bool(re.match(r"^\s*\d+\s*/\s*\d+\s*/\s*\d+", str(line)))


def _normalise_member_case_v47(value: str) -> str:
    s = str(value or "").strip()
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)(.*)$", s)
    if not m:
        return s
    tail = re.sub(r"\s+", " ", m.group(4).strip())
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}" + (f" {tail}" if tail else "")


def _parse_space_aligned_structural_table_v47(text: str) -> pd.DataFrame:
    """
    Parser específico para tabelas copiadas como texto alinhado por espaços.
    Resolve casos do tipo:
        14/ 1/ 101 (C) 132,28 ... C30/37 25,0 40,0 ...
    em que Member/Node/Case tem espaços internos e a linha de cabeçalho tem unidades.
    """
    lines = [ln.rstrip() for ln in str(text).splitlines() if ln.strip()]
    data_lines = [ln for ln in lines if _is_data_line_v47(ln)]
    if not data_lines:
        return pd.DataFrame()

    rows = []
    for ln in data_lines:
        m = re.match(r"^\s*(\d+\s*/\s*\d+\s*/\s*\d+(?:\s*\([^)]*\))?)\s+(.*)$", ln)
        if not m:
            continue
        member_case = _normalise_member_case_v47(m.group(1))
        rest = m.group(2).strip()
        toks = rest.split()
        if not toks:
            continue

        mat_idx = None
        for i, tok in enumerate(toks):
            if re.fullmatch(r"C\s*\d{2,3}\s*/\s*\d{2,3}", tok, re.I):
                mat_idx = i
                break

        # Antes do Material esperam-se 7 campos: FX,FY,FZ,MX,MY,MZ,Length.
        # Se o Material não for encontrado, mantém os primeiros 7 campos e deixa Material vazio.
        if mat_idx is None:
            pre = toks[:7]
            material = ""
            post = toks[7:]
        else:
            pre = toks[:mat_idx]
            material = toks[mat_idx]
            post = toks[mat_idx + 1:]

        pre = pre[:7] + [""] * max(0, 7 - len(pre))
        row = [member_case] + pre + [material] + post
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    max_len = max(len(r) for r in rows)
    cols = DEFAULT_IMPORT_COLUMNS_V47[:max_len]
    if len(cols) < max_len:
        cols += [f"Extra_{i}" for i in range(len(cols) + 1, max_len + 1)]

    rows = [r[:max_len] + [""] * max(0, max_len - len(r)) for r in rows]
    return pd.DataFrame(rows, columns=cols)


def parse_pasted_table_v47(text: str) -> pd.DataFrame:
    text = str(text or "").strip()
    if not text:
        return pd.DataFrame()

    # 1) Preferir tabulações, que preservam melhor as colunas quando vem de Excel/folhas.
    for sep in ("\t", ";"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python", dtype=str)
            if len(df.columns) > 1 and len(df) > 0:
                return df
        except Exception:
            pass

    # 2) Parser específico para exportações alinhadas por espaços.
    df_struct = _parse_space_aligned_structural_table_v47(text)
    if not df_struct.empty:
        return df_struct

    # 3) Fallback genérico por múltiplos espaços.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame()
    rows = [re.split(r"\s{2,}", line) for line in lines]
    if len(rows) < 2:
        return pd.DataFrame()
    header = rows[0]
    body = rows[1:]
    width = len(header)
    body = [r[:width] + [""] * max(0, width - len(r)) for r in body]
    return pd.DataFrame(body, columns=header)


globals()["parse_pasted_table"] = parse_pasted_table_v47
ColumnsEC2App.TEMPLATE_COLUMNS = DEFAULT_IMPORT_COLUMNS_V47[:-1]


def _build_paste_tab_v47(self, parent):
    parent.rowconfigure(1, weight=1)
    parent.columnconfigure(0, weight=1)

    top = ttk.Frame(parent, padding=6)
    top.grid(row=0, column=0, sticky="ew")
    top.columnconfigure(0, weight=1)
    ttk.Label(top, text="Cole a tabela, interprete-a e confirme/edite na grelha antes do cálculo.").grid(row=0, column=0, sticky="w")
    ttk.Button(top, text="Interpretar texto", command=self.update_editable_table_from_text).grid(row=0, column=1, sticky="e", padx=(6, 0))
    ttk.Button(top, text="Ler grelha", command=self.load_from_editable_grid).grid(row=0, column=2, sticky="e", padx=(6, 0))
    ttk.Button(top, text="Adicionar linha", command=self.add_editable_row).grid(row=0, column=3, sticky="e", padx=(6, 0))
    ttk.Button(top, text="Remover linha", command=self.delete_editable_rows).grid(row=0, column=4, sticky="e", padx=(6, 0))
    ttk.Button(top, text="Limpar", command=self.clear_paste_area).grid(row=0, column=5, sticky="e", padx=(6, 0))

    paned = ttk.Panedwindow(parent, orient="vertical")
    paned.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

    text_frame = ttk.LabelFrame(paned, text="Texto colado")
    text_frame.rowconfigure(0, weight=1)
    text_frame.columnconfigure(0, weight=1)
    self.txt_paste = tk.Text(text_frame, wrap="none", undo=True, height=7, font=("Courier New", 9))
    vsb = ttk.Scrollbar(text_frame, orient="vertical", command=self.txt_paste.yview)
    hsb = ttk.Scrollbar(text_frame, orient="horizontal", command=self.txt_paste.xview)
    self.txt_paste.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    self.txt_paste.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    grid_frame = ttk.LabelFrame(paned, text="Tabela editável reconhecida")
    grid_frame.rowconfigure(0, weight=1)
    grid_frame.columnconfigure(0, weight=1)
    self.tree_paste_grid = ttk.Treeview(grid_frame, show="headings", selectmode="extended")
    gvsb = ttk.Scrollbar(grid_frame, orient="vertical", command=self.tree_paste_grid.yview)
    ghsb = ttk.Scrollbar(grid_frame, orient="horizontal", command=self.tree_paste_grid.xview)
    self.tree_paste_grid.configure(yscrollcommand=gvsb.set, xscrollcommand=ghsb.set)
    self.tree_paste_grid.grid(row=0, column=0, sticky="nsew")
    gvsb.grid(row=0, column=1, sticky="ns")
    ghsb.grid(row=1, column=0, sticky="ew")
    self.tree_paste_grid.bind("<Double-1>", self._edit_paste_grid_cell)

    paned.add(text_frame, weight=1)
    paned.add(grid_frame, weight=4)

    self.df_editable = pd.DataFrame(columns=DEFAULT_IMPORT_COLUMNS_V47[:-1])
    self._show_editable_grid(self.df_editable)


def _show_editable_grid_v47(self, df: pd.DataFrame):
    if not hasattr(self, "tree_paste_grid"):
        return
    tree = self.tree_paste_grid
    tree.delete(*tree.get_children())
    if df is None or df.empty:
        cols = DEFAULT_IMPORT_COLUMNS_V47[:-1]
        df = pd.DataFrame(columns=cols)
    cols = list(df.columns)
    tree["columns"] = cols
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=max(85, min(150, len(str(c)) * 9)), anchor="center")
    for _, row in df.head(MAX_PREVIEW_ROWS).iterrows():
        vals = ["" if pd.isna(row.get(c, "")) else str(row.get(c, "")) for c in cols]
        tree.insert("", "end", values=vals)
    self.df_editable = df.copy()


def _editable_grid_to_df_v47(self) -> pd.DataFrame:
    if not hasattr(self, "tree_paste_grid"):
        return pd.DataFrame()
    tree = self.tree_paste_grid
    cols = list(tree["columns"])
    rows = []
    for iid in tree.get_children(""):
        vals = list(tree.item(iid, "values"))
        vals = vals[:len(cols)] + [""] * max(0, len(cols) - len(vals))
        rows.append(dict(zip(cols, vals)))
    return pd.DataFrame(rows, columns=cols)


def _update_editable_table_from_text_v47(self):
    text = self.txt_paste.get("1.0", "end").strip() if hasattr(self, "txt_paste") else ""
    if not text:
        messagebox.showwarning("Aviso", "Cole primeiro a tabela na caixa de texto.")
        return
    df = parse_pasted_table_v47(text)
    if df.empty:
        messagebox.showwarning("Aviso", "A tabela colada não foi reconhecida.")
        return
    self._show_editable_grid(df)
    self.status_var.set(f"Tabela interpretada na grelha: {len(df)} linhas. Confirme as colunas antes de calcular.")


def _load_from_editable_grid_v47(self):
    df = self._editable_grid_to_df()
    if df.empty:
        # fallback: tenta interpretar o texto, para manter compatibilidade com o botão antigo
        text = self.txt_paste.get("1.0", "end").strip() if hasattr(self, "txt_paste") else ""
        if not text:
            messagebox.showwarning("Aviso", "Cole ou importe uma tabela primeiro.")
            return
        df = parse_pasted_table_v47(text)
    if df.empty:
        messagebox.showwarning("Aviso", "A grelha está vazia ou a tabela não foi reconhecida.")
        return
    self.load_df(df, source="tabela editável")


def _load_from_textbox_v47(self):
    # Mantém o nome antigo, mas agora lê preferencialmente a grelha editável.
    if hasattr(self, "tree_paste_grid") and self.tree_paste_grid.get_children(""):
        return self.load_from_editable_grid()
    self.update_editable_table_from_text()
    if hasattr(self, "tree_paste_grid") and self.tree_paste_grid.get_children(""):
        return self.load_from_editable_grid()


def _paste_clipboard_v47(self):
    try:
        text = self.clipboard_get()
    except Exception:
        messagebox.showwarning("Aviso", "Não foi possível ler a área de transferência.")
        return
    self.txt_paste.delete("1.0", "end")
    self.txt_paste.insert("1.0", text)
    df = parse_pasted_table_v47(text)
    if df.empty:
        messagebox.showwarning("Aviso", "A tabela colada não foi reconhecida.")
        return
    self._show_editable_grid(df)
    self.load_df(df, source="área de transferência")


def _clear_paste_area_v47(self):
    if hasattr(self, "txt_paste"):
        self.txt_paste.delete("1.0", "end")
    self._show_editable_grid(pd.DataFrame(columns=DEFAULT_IMPORT_COLUMNS_V47[:-1]))
    self.status_var.set("Área de colagem limpa.")


def _add_editable_row_v47(self):
    if not hasattr(self, "tree_paste_grid"):
        return
    tree = self.tree_paste_grid
    cols = list(tree["columns"]) or DEFAULT_IMPORT_COLUMNS_V47[:-1]
    if not list(tree["columns"]):
        self._show_editable_grid(pd.DataFrame(columns=cols))
    tree.insert("", "end", values=[""] * len(cols))


def _delete_editable_rows_v47(self):
    if not hasattr(self, "tree_paste_grid"):
        return
    sel = self.tree_paste_grid.selection()
    if not sel:
        return
    for iid in sel:
        self.tree_paste_grid.delete(iid)


def _edit_paste_grid_cell_v47(self, event):
    tree = self.tree_paste_grid
    region = tree.identify("region", event.x, event.y)
    if region != "cell":
        return
    row_id = tree.identify_row(event.y)
    col_id = tree.identify_column(event.x)
    if not row_id or not col_id:
        return
    col_index = int(col_id.replace("#", "")) - 1
    cols = list(tree["columns"])
    if col_index < 0 or col_index >= len(cols):
        return
    bbox = tree.bbox(row_id, col_id)
    if not bbox:
        return
    x, y, w, h = bbox
    values = list(tree.item(row_id, "values"))
    values = values[:len(cols)] + [""] * max(0, len(cols) - len(values))
    current = values[col_index]

    editor = ttk.Entry(tree)
    editor.insert(0, current)
    editor.select_range(0, "end")
    editor.focus_set()
    editor.place(x=x, y=y, width=w, height=h)

    def save(_event=None):
        values[col_index] = editor.get()
        tree.item(row_id, values=values)
        editor.destroy()

    def cancel(_event=None):
        editor.destroy()

    editor.bind("<Return>", save)
    editor.bind("<FocusOut>", save)
    editor.bind("<Escape>", cancel)


ColumnsEC2App._build_paste_tab = _build_paste_tab_v47
ColumnsEC2App._show_editable_grid = _show_editable_grid_v47
ColumnsEC2App._editable_grid_to_df = _editable_grid_to_df_v47
ColumnsEC2App.update_editable_table_from_text = _update_editable_table_from_text_v47
ColumnsEC2App.load_from_editable_grid = _load_from_editable_grid_v47
ColumnsEC2App.load_from_textbox = _load_from_textbox_v47
ColumnsEC2App.paste_clipboard = _paste_clipboard_v47
ColumnsEC2App.clear_paste_area = _clear_paste_area_v47
ColumnsEC2App.add_editable_row = _add_editable_row_v47
ColumnsEC2App.delete_editable_rows = _delete_editable_rows_v47
ColumnsEC2App._edit_paste_grid_cell = _edit_paste_grid_cell_v47


def _build_normative_notes_v47(self) -> pd.DataFrame:
    try:
        notes = _build_normative_notes_v46(self).copy()
    except Exception:
        notes = pd.DataFrame(columns=["Tema", "Referência", "Nota"])
    extra = pd.DataFrame([
        ("Interface", "Grelha editável", "A tabela colada é agora interpretada para uma grelha editável antes do cálculo, permitindo corrigir Material, dimensões e esforços antes de carregar os dados."),
        ("Importação", "Texto alinhado por espaços", "O parser reconhece Member/Node/Case com espaços internos, por exemplo 14/ 1/ 101 (C), e preserva Material como C30/37 quando presente."),
        ("Materiais", "Classe de betão", "A classe de betão é lida da coluna Material; o programa só pede uma classe ao utilizador quando essa coluna está efectivamente vazia ou inválida depois da leitura em grelha."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True).drop_duplicates()

ColumnsEC2App.build_normative_notes = _build_normative_notes_v47




# ============================================================
# ColumnsEC2 v4.8 — backend opcional EC2 2023 via structuralcodes
# ============================================================
APP_VERSION = "v4.8"
APP_XLSX_DESCRIPTION = (
    "Workbook de cálculo com backend por norma: EC2 Portugal 2010 por defeito e "
    "Eurocode 2:2023 via structuralcodes como opção. Inclui entrada de dados, validação, "
    "envolvente ELU, ELU/ELS/V/T/pormenorização, DXF, relatórios e metadados."
)

BACKEND_EC2_PT_2010 = "NP EN 1992-1-1:2010 PT (default)"
BACKEND_EC2_2023_SC = "Eurocode 2:2023 | structuralcodes"
ACTIVE_CODE_BACKEND_V48 = BACKEND_EC2_PT_2010
EC2_2023_DEFAULTS_V48 = {
    "t_ref": 28.0,
    "t0": 28.0,
    "strength_dev_class": "CN",
    "gamma_c": 1.50,
    "gamma_s": 1.15,
}


def _backend_selected_v48(value=None) -> str:
    if value is None:
        value = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    s = str(value or "").strip()
    if "2023" in s and "structuralcodes" in s.lower():
        return BACKEND_EC2_2023_SC
    return BACKEND_EC2_PT_2010


def _is_ec2_2023_backend_v48(value=None) -> bool:
    return _backend_selected_v48(value) == BACKEND_EC2_2023_SC


def _get_ec2_2023_module_v48():
    try:
        import structuralcodes.codes.ec2_2023 as ec23
        return ec23, None
    except Exception as err:
        return None, err


def _require_ec2_2023_structuralcodes_v48():
    ec23, err = _get_ec2_2023_module_v48()
    if ec23 is None:
        raise RuntimeError(
            "O backend Eurocode 2:2023 requer o pacote structuralcodes.\n\n"
            "Instale com:\npython -m pip install structuralcodes\n\n"
            f"Erro original: {err}"
        )
    return ec23


# Guardar as propriedades do motor por defeito antes de redireccionar.
_default_concrete_props_v48 = concrete_props
_default_steel_props_v48 = steel_props


def concrete_props(fck: float, alpha_cc: float = 1.0, gamma_c: float = 1.5) -> Dict[str, float]:
    """Propriedades do betão conforme o backend seleccionado.

    Backend por defeito: mantém a formulação usada pelo ColumnsEC2 para EC2 Portugal 2010.
    Backend EC2:2023: usa as funções oficiais expostas pelo pacote structuralcodes.
    """
    if _is_ec2_2023_backend_v48():
        ec23 = _require_ec2_2023_structuralcodes_v48()
        defaults = globals().get("EC2_2023_DEFAULTS_V48", {})
        gamma_c_eff = float(defaults.get("gamma_c", gamma_c))
        t_ref = float(defaults.get("t_ref", 28.0))
        t0 = float(defaults.get("t0", 28.0))
        strength_dev_class = str(defaults.get("strength_dev_class", "CN"))
        fcm_val = float(ec23.fcm(float(fck)))
        eta_cc_val = float(ec23.eta_cc(float(fck)))
        k_tc_val = float(ec23.k_tc(t_ref=t_ref, t0=t0, strength_dev_class=strength_dev_class))
        fcd_val = float(ec23.fcd(float(fck), eta_cc=eta_cc_val, k_tc=k_tc_val, gamma_c=gamma_c_eff))
        fctm_val = float(ec23.fctm(float(fck)))
        ecm_val = float(ec23.Ecm(fcm_val))
        return {
            "fck": float(fck),
            "fcm": fcm_val,
            "fcd": fcd_val,
            "fctm": fctm_val,
            "Ecm": ecm_val,
            "eta_cc": eta_cc_val,
            "k_tc": k_tc_val,
            "backend": BACKEND_EC2_2023_SC,
        }
    return _default_concrete_props_v48(fck, alpha_cc=alpha_cc, gamma_c=gamma_c)

globals()["concrete_props"] = concrete_props


def steel_props(fyk: float = 500.0, gamma_s: float = 1.15) -> Dict[str, float]:
    """Propriedades do aço conforme o backend seleccionado.

    No EC2:2023 usa-se structuralcodes.codes.ec2_2023.fyd e Es().
    No motor por defeito mantém-se Es = 210 GPa, conforme opção anterior do programa.
    """
    if _is_ec2_2023_backend_v48():
        ec23 = _require_ec2_2023_structuralcodes_v48()
        defaults = globals().get("EC2_2023_DEFAULTS_V48", {})
        gamma_s_eff = float(defaults.get("gamma_s", gamma_s))
        return {
            "fyd": float(ec23.fyd(float(fyk), gamma_s_eff)),
            "Es": float(ec23.Es()),
            "backend": BACKEND_EC2_2023_SC,
        }
    return _default_steel_props_v48(fyk=fyk, gamma_s=gamma_s)

globals()["steel_props"] = steel_props


# Guardar init original para associar o backend ao designer.
_old_cd_init_v48 = ColumnDesigner.__init__

def _cd_init_v48(self, *args, **kwargs):
    code_backend = kwargs.pop("code_backend", None)
    _old_cd_init_v48(self, *args, **kwargs)
    self.code_backend = _backend_selected_v48(code_backend or globals().get("ACTIVE_CODE_BACKEND_V48"))

ColumnDesigner.__init__ = _cd_init_v48


_old_design_one_v48 = ColumnDesigner.design_one

def _design_one_v48(self, row: pd.Series, prebuilt_candidates=None):
    # Garante que concrete_props/steel_props sabem qual backend está activo neste cálculo.
    old_backend = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    globals()["ACTIVE_CODE_BACKEND_V48"] = getattr(self, "code_backend", old_backend)
    try:
        out = _old_design_one_v48(self, row, prebuilt_candidates=prebuilt_candidates)
    finally:
        globals()["ACTIVE_CODE_BACKEND_V48"] = old_backend
    if not isinstance(out, dict):
        return out
    out["code_backend"] = getattr(self, "code_backend", BACKEND_EC2_PT_2010)
    out["normative_basis"] = (
        "Eurocode 2:2023 por structuralcodes: propriedades de materiais e funções EC2:2023 disponíveis no pacote; "
        "motor seccional ColumnsEC2 para N-My-Mz, pormenorização, DXF e envolvente."
        if _is_ec2_2023_backend_v48(getattr(self, "code_backend", ""))
        else "NP EN 1992-1-1:2010 + AC:2012 + A1:2019, Anexo Nacional português"
    )
    try:
        # Regista as propriedades realmente usadas para auditoria.
        fck = parse_concrete_strength(str(row.get("material", "C30/37")))
        cp = concrete_props(fck)
        sp = steel_props(float(getattr(self, "fyk", 500.0)) if hasattr(self, "fyk") else 500.0)
        out["mat_fcd_used_MPa"] = cp.get("fcd")
        out["mat_fctm_used_MPa"] = cp.get("fctm")
        out["mat_Ecm_used_MPa"] = cp.get("Ecm")
        out["steel_fyd_used_MPa"] = sp.get("fyd")
        out["steel_Es_used_MPa"] = sp.get("Es")
        if _is_ec2_2023_backend_v48(getattr(self, "code_backend", "")):
            out["ec2_2023_eta_cc"] = cp.get("eta_cc")
            out["ec2_2023_k_tc"] = cp.get("k_tc")
    except Exception as err:
        out["backend_note"] = f"Não foi possível registar propriedades do backend: {err}"
    return out

ColumnDesigner.design_one = _design_one_v48


# Sidebar: mantém default actual e acrescenta selector de backend.
_old_build_sidebar_v48 = ColumnsEC2App._build_sidebar

def _build_sidebar_v48(self, parent):
    if not hasattr(self, "var_code_backend"):
        self.var_code_backend = tk.StringVar(value=BACKEND_EC2_PT_2010)
    if not hasattr(self, "var_ec23_strength_class"):
        self.var_ec23_strength_class = tk.StringVar(value="CN")
    if not hasattr(self, "var_ec23_tref"):
        self.var_ec23_tref = tk.StringVar(value="28")
    if not hasattr(self, "var_ec23_t0"):
        self.var_ec23_t0 = tk.StringVar(value="28")
    _old_build_sidebar_v48(self, parent)
    frame = ttk.LabelFrame(parent, text="9. Norma / motor de cálculo")
    frame.pack(fill="x", pady=(0, 8))
    ttk.Label(frame, text="Backend").grid(row=0, column=0, sticky="w", padx=6, pady=4)
    ttk.Combobox(
        frame,
        textvariable=self.var_code_backend,
        values=[BACKEND_EC2_PT_2010, BACKEND_EC2_2023_SC],
        state="readonly",
        width=32,
    ).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
    ttk.Label(frame, text="Classe desenv.").grid(row=1, column=0, sticky="w", padx=6, pady=3)
    ttk.Combobox(frame, textvariable=self.var_ec23_strength_class, values=["CS", "CN", "CR"], state="readonly", width=8).grid(row=1, column=1, sticky="w", padx=6, pady=3)
    ttk.Label(frame, text="t_ref / t0 [dias]").grid(row=2, column=0, sticky="w", padx=6, pady=3)
    sub = ttk.Frame(frame)
    sub.grid(row=2, column=1, sticky="ew", padx=6, pady=3)
    ttk.Entry(sub, textvariable=self.var_ec23_tref, width=6).pack(side="left")
    ttk.Label(sub, text=" / ").pack(side="left")
    ttk.Entry(sub, textvariable=self.var_ec23_t0, width=6).pack(side="left")
    ttk.Label(
        frame,
        text="Default = EC2 Portugal 2010. EC2:2023 exige: python -m pip install structuralcodes",
        style="Subtle.TLabel",
        wraplength=300,
    ).grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))
    frame.columnconfigure(1, weight=1)

ColumnsEC2App._build_sidebar = _build_sidebar_v48


# Validação: se o utilizador escolher EC2 2023, não deixar calcular sem structuralcodes.
_old_validate_inputs_v48 = ColumnsEC2App.validate_inputs

def _validate_inputs_v48(self):
    err = _old_validate_inputs_v48(self)
    if err:
        return err
    backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    if _is_ec2_2023_backend_v48(backend):
        ec23, import_err = _get_ec2_2023_module_v48()
        if ec23 is None:
            return (
                "O backend Eurocode 2:2023 requer o pacote structuralcodes.\n\n"
                "Instale com:\npython -m pip install structuralcodes\n\n"
                f"Erro original: {import_err}"
            )
        try:
            tref = float(self.var_ec23_tref.get().replace(",", "."))
            t0 = float(self.var_ec23_t0.get().replace(",", "."))
            strength_class = self.var_ec23_strength_class.get().strip() or "CN"
            # chamada de validação real da API structuralcodes
            _ = ec23.k_tc(t_ref=tref, t0=t0, strength_dev_class=strength_class)
        except Exception as ve:
            return f"Parâmetros EC2:2023 inválidos para structuralcodes: {ve}"
    return None

ColumnsEC2App.validate_inputs = _validate_inputs_v48


_old_run_design_v48 = ColumnsEC2App.run_design

def _run_design_v48(self):
    backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    globals()["ACTIVE_CODE_BACKEND_V48"] = backend
    try:
        EC2_2023_DEFAULTS_V48["t_ref"] = float(getattr(self, "var_ec23_tref", tk.StringVar(value="28")).get().replace(",", "."))
        EC2_2023_DEFAULTS_V48["t0"] = float(getattr(self, "var_ec23_t0", tk.StringVar(value="28")).get().replace(",", "."))
        EC2_2023_DEFAULTS_V48["strength_dev_class"] = getattr(self, "var_ec23_strength_class", tk.StringVar(value="CN")).get().strip() or "CN"
    except Exception:
        pass
    return _old_run_design_v48(self)

ColumnsEC2App.run_design = _run_design_v48


# Caso algum run_design antigo crie directamente ColumnDesigner sem passar backend, o global activo assegura o valor.
# Excel/PDF recebem automaticamente as novas colunas nos dataframes. Acrescentamos notas normativas.
_old_build_normative_notes_v48 = ColumnsEC2App.build_normative_notes

def _build_normative_notes_v48(self) -> pd.DataFrame:
    try:
        notes = _old_build_normative_notes_v48(self).copy()
    except Exception:
        notes = pd.DataFrame(columns=["Tema", "Referência", "Nota"])
    extra = pd.DataFrame([
        ("Backend", "Selecção de norma", "O motor por defeito permanece NP EN 1992-1-1:2010 PT. O backend Eurocode 2:2023 via structuralcodes é opcional e deve ser instalado separadamente."),
        ("Eurocode 2:2023", "structuralcodes", "Quando seleccionado, o programa usa structuralcodes.codes.ec2_2023 para fcd, eta_cc, k_tc, fctm, Ecm, fyd e Es, respeitando a API da biblioteca."),
        ("Eurocode 2:2023", "limitação de âmbito", "A biblioteca structuralcodes disponibiliza funções EC2:2023 para materiais, fendilhação, deformação e fluência/retracção. O motor de superfície N-My-Mz, pormenorização, DXF e envolvente continua a ser do ColumnsEC2."),
        ("Parâmetros EC2:2023", "k_tc", "Para o backend EC2:2023 são usados t_ref, t0 e classe de desenvolvimento indicados no painel da GUI; por defeito: t_ref=28 dias, t0=28 dias, classe CN."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True).drop_duplicates()

ColumnsEC2App.build_normative_notes = _build_normative_notes_v48


# Acrescentar metadados/resumo com o backend quando possível.
_old_build_summary_text_v48 = getattr(ColumnsEC2App, "build_summary_text", None)
if _old_build_summary_text_v48 is not None:
    def _build_summary_text_v48(self):
        txt = _old_build_summary_text_v48(self)
        try:
            backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
            txt += f"\nBackend de cálculo: {backend}\n"
            if _is_ec2_2023_backend_v48(backend):
                txt += f"Parâmetros EC2:2023: t_ref={self.var_ec23_tref.get()} dias; t0={self.var_ec23_t0.get()} dias; classe={self.var_ec23_strength_class.get()}\n"
        except Exception:
            pass
        return txt
    ColumnsEC2App.build_summary_text = _build_summary_text_v48



# ============================================================
# ColumnsEC2 v4.9 — PDF export robusto contra ficheiros bloqueados/read-only
# ============================================================
APP_VERSION = "v4.9"


def _v49_safe_var_get(obj, attr, default=""):
    try:
        v = getattr(obj, attr, None)
        if v is None:
            return default
        if hasattr(v, "get"):
            return str(v.get())
        return str(v)
    except Exception:
        return default


def _v49_safe_pdf_text(x):
    try:
        if x is None:
            return ""
        if isinstance(x, float):
            if not math.isfinite(x):
                return ""
            return f"{x:.2f}"
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x)
    # ReportLab Paragraph markup-safe
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _v49_pdf_table_style(header=True):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E2E7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ]
    return TableStyle(cmds)


def _write_pdf_v49(self, path: str):
    """PDF sintético e robusto. Não escreve metadados dentro do callback do canvas
    para evitar erros de destino read-only em alguns ambientes Windows/PDF viewers.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak

    res = enrich_failures_v43(self.df_results) if self.df_results is not None else pd.DataFrame()
    summary = self.df_summary if self.df_summary is not None and not self.df_summary.empty else res
    summary = enrich_failures_v43(summary) if summary is not None and not summary.empty else pd.DataFrame()
    failures = res[res.get("failure_severity", pd.Series(dtype=str)).astype(str) == "Bloqueante"].copy() if not res.empty else pd.DataFrame()
    warnings_df = res[res.get("failure_severity", pd.Series(dtype=str)).astype(str) == "Aviso"].copy() if not res.empty else pd.DataFrame()

    doc = SimpleDocTemplate(
        path,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    # Metadados apenas no documento. Não repetir no canvas por página.
    try:
        doc.title = f"{APP_NAME} {APP_VERSION}"
        doc.author = APP_AUTHOR
        doc.subject = APP_SUBJECT
        doc.creator = APP_NAME
    except Exception:
        pass

    styles = getSampleStyleSheet()
    for sty in ["ReportTitle", "ReportSubtitle", "BodyCourier", "Small", "Cell", "Section"]:
        if sty in styles.byName:
            continue
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, fontName="Courier-Bold", fontSize=14, leading=21, spaceAfter=10))
    styles.add(ParagraphStyle(name="ReportSubtitle", parent=styles["Normal"], alignment=TA_CENTER, fontName="Courier", fontSize=10, leading=15, textColor=colors.darkgrey, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyCourier", parent=styles["Normal"], fontName="Courier", fontSize=10, leading=15, spaceAfter=6))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontName="Courier", fontSize=8, leading=12))
    styles.add(ParagraphStyle(name="Cell", parent=styles["Small"], alignment=TA_LEFT, fontName="Courier", fontSize=7, leading=10.5))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Courier-Bold", fontSize=12, leading=18, spaceBefore=10, spaceAfter=12))

    def df_table(df, cols, max_rows=25, widths=None):
        if df is None or df.empty:
            df = pd.DataFrame(columns=cols)
        present = [c for c in cols if c in df.columns]
        if not present:
            present = ["nota"]
            df = pd.DataFrame([{"nota": "sem dados"}])
        data = [[Paragraph(_v49_safe_pdf_text(c), styles["Cell"]) for c in present]]
        for _, r in df.head(max_rows).iterrows():
            data.append([Paragraph(_v49_safe_pdf_text(r.get(c, "")), styles["Cell"]) for c in present])
        if widths is None:
            widths = [270 * mm / max(1, len(present))] * len(present)
        tb = Table(data, colWidths=widths, repeatRows=1)
        tb.setStyle(_v49_pdf_table_style(header=True))
        return tb

    n_total = len(res)
    n_ok = int((res.get("status", pd.Series(dtype=str)) == "OK").sum()) if not res.empty else 0
    n_warn = int((res.get("failure_severity", pd.Series(dtype=str)) == "Aviso").sum()) if not res.empty else 0
    n_block = int((res.get("failure_severity", pd.Series(dtype=str)) == "Bloqueante").sum()) if not res.empty else 0
    n_members = int(res.get("member", pd.Series(dtype=str)).astype(str).nunique()) if not res.empty and "member" in res.columns else 0
    n_prumadas = int(res.get("prumada", pd.Series(dtype=str)).astype(str).nunique()) if not res.empty and "prumada" in res.columns else 0
    n_assumed = int((res.get("material_assumed", pd.Series(dtype=str)).astype(str) == "Sim").sum()) if not res.empty and "material_assumed" in res.columns else 0

    backend = _v49_safe_var_get(self, "var_code_backend", BACKEND_EC2_PT_2010)
    els_case = _v49_safe_var_get(self, "var_service_case", "").strip() or "simplificado"
    input_name = os.path.basename(str(getattr(self, "input_file_path", "") or "-"))

    story = []
    story.append(Paragraph(f"{APP_NAME} {APP_VERSION}", styles["ReportTitle"]))
    story.append(Paragraph("Síntese de dimensionamento de pilares segundo o Eurocódigo 2", styles["ReportSubtitle"]))

    meta = [
        ["Programa", f"{APP_NAME} {APP_VERSION}", "Autor", APP_AUTHOR],
        ["Data", datetime.now().strftime("%Y-%m-%d %H:%M"), "Backend", backend],
        ["Casos", str(n_total), "Membros/Prumadas", f"{n_members}/{n_prumadas}"],
        ["OK", str(n_ok), "Bloqueantes", str(n_block)],
        ["Avisos", str(n_warn), "Materiais assumidos", str(n_assumed)],
        ["ELS", els_case, "Ficheiro", input_name],
    ]
    t = Table(meta, colWidths=[38 * mm, 90 * mm, 38 * mm, 90 * mm])
    t.setStyle(_v49_pdf_table_style(header=False))
    story.append(t)
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("1. Resumo executivo por prumada/nome", styles["Section"]))
    exec_cols = ["prumada", "member", "material", "b_cm", "h_cm", "n_ed_kN", "as_req_mm2", "as_prov_mm2", "solucao", "status", "failure_severity"]
    story.append(df_table(summary, exec_cols, max_rows=32))

    story.append(Paragraph("2. Verificações condicionantes", styles["Section"]))
    cond_cols = ["prumada", "member", "case", "utilizacao", "service_status", "shear_status", "torsion_status", "detailing_status", "design_decision"]
    story.append(df_table(summary, cond_cols, max_rows=28))

    if failures is not None and not failures.empty:
        story.append(PageBreak())
        story.append(Paragraph("3. Falhas bloqueantes — decisão e acção recomendada", styles["Section"]))
        fail_cols = ["prumada", "member", "case", "failure_type", "failure_severity", "design_decision", "failure_action"]
        story.append(df_table(failures, fail_cols, max_rows=45, widths=[25*mm, 22*mm, 18*mm, 34*mm, 25*mm, 58*mm, 88*mm]))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Critério: qualquer falha bloqueante não deve ser aceite sem correcção dos dados, revisão da solução ou validação independente do pilar crítico.", styles["BodyCourier"]))

    if warnings_df is not None and not warnings_df.empty:
        story.append(Paragraph("4. Avisos principais", styles["Section"]))
        warn_cols = ["prumada", "member", "case", "failure_type", "design_decision", "failure_action"]
        story.append(df_table(warnings_df, warn_cols, max_rows=25, widths=[28*mm, 22*mm, 18*mm, 38*mm, 68*mm, 96*mm]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Notas: este PDF é uma síntese executiva. A memória completa permanece no ficheiro XLSX exportado.", styles["Small"]))

    def footer(pdf_canvas, doc_obj):
        pdf_canvas.saveState()
        pdf_canvas.setFont("Courier", 7)
        pdf_canvas.setFillColor(colors.grey)
        pdf_canvas.drawString(12 * mm, 7 * mm, f"{APP_NAME} {APP_VERSION} | {APP_AUTHOR}")
        pdf_canvas.drawRightString(285 * mm, 7 * mm, f"Página {doc_obj.page}")
        pdf_canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


ColumnsEC2App._write_pdf = _write_pdf_v49


def _export_pdf_report_v49(self):
    if self.df_results is None or self.df_results.empty:
        messagebox.showwarning("Aviso", "Não há resultados para exportar.")
        return
    path = filedialog.asksaveasfilename(title="Exportar relatório PDF", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    if not path:
        return
    root, ext = os.path.splitext(path)
    if ext.lower() != ".pdf":
        path = root + ".pdf" if ext else path + ".pdf"

    out_dir = os.path.dirname(os.path.abspath(path)) or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = os.path.join(out_dir, f".__columns_ec2_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.pdf")
    final_path = path
    try:
        self._write_pdf(tmp_path)
        try:
            if os.path.exists(final_path):
                # Se o ficheiro existir e estiver bloqueado/read-only, esta operação pode falhar.
                os.replace(tmp_path, final_path)
            else:
                os.rename(tmp_path, final_path)
        except Exception:
            alt_path = os.path.join(out_dir, f"{root.split(os.sep)[-1]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            os.rename(tmp_path, alt_path)
            final_path = alt_path
            messagebox.showwarning(
                "PDF guardado com novo nome",
                "O ficheiro de destino parecia estar bloqueado, aberto ou protegido contra escrita.\n\n"
                f"O relatório foi guardado como:\n{final_path}"
            )
        self.status_var.set(f"Relatório PDF exportado para: {final_path}")
    except Exception as err:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        messagebox.showerror("Erro", f"Não foi possível exportar PDF.\n\n{err}")


ColumnsEC2App.export_pdf_report = _export_pdf_report_v49


# ============================================================
# ColumnsEC2 v5.0 — modo EC2:2023 estrito via structuralcodes
# ============================================================
APP_VERSION = "v5.0"
BACKEND_EC2_2023_SC = "Eurocode 2:2023 | structuralcodes"


def _sc2023_active(value=None) -> bool:
    try:
        return _is_ec2_2023_backend_v48(value)
    except Exception:
        s = str(value or globals().get("ACTIVE_CODE_BACKEND_V48", "")).lower()
        return "2023" in s and "structuralcodes" in s


def _sc2023_import_all_v50():
    """Importa os blocos estruturais do structuralcodes necessários ao modo estrito.

    O modo EC2:2023 não deve chamar silenciosamente o motor seccional interno para
    N-My-Mz. Se structuralcodes ou shapely não estiverem disponíveis, o cálculo deve
    parar na validação ou devolver uma nota explícita.
    """
    try:
        from shapely import Polygon
        from structuralcodes import set_design_code
        from structuralcodes.geometry import SurfaceGeometry, add_reinforcement
        from structuralcodes.materials.concrete import create_concrete
        from structuralcodes.materials.reinforcement import create_reinforcement
        from structuralcodes.sections import BeamSection
        import structuralcodes.codes.ec2_2023 as ec23
        try:
            set_design_code("ec2_2023")
        except Exception:
            # Algumas versões podem usar outro alias. Tentamos apenas não interromper
            # aqui; a criação de materiais acusará o erro se o alias não existir.
            pass
        return {
            "Polygon": Polygon,
            "SurfaceGeometry": SurfaceGeometry,
            "add_reinforcement": add_reinforcement,
            "create_concrete": create_concrete,
            "create_reinforcement": create_reinforcement,
            "BeamSection": BeamSection,
            "ec23": ec23,
        }, None
    except Exception as err:
        return None, err


def _flatten_numeric_v50(value):
    try:
        import numpy as np
        arr = np.asarray(value, dtype=float).ravel()
        return arr
    except Exception:
        try:
            return pd.to_numeric(pd.Series(value), errors="coerce").to_numpy(dtype=float)
        except Exception:
            return None


def _extract_nmm_arrays_v50(result):
    """Extrai arrays N, My, Mz de resultados do structuralcodes, com tolerância
    a pequenas alterações de nomes entre versões.
    """
    candidates = []
    if result is None:
        return None, None, None

    # 1) atributos directos mais prováveis
    direct_names = [
        ("n", "m_y", "m_z"),
        ("n", "my", "mz"),
        ("N", "M_y", "M_z"),
        ("N", "My", "Mz"),
        ("n_i", "m_y_i", "m_z_i"),
    ]
    for names in direct_names:
        if all(hasattr(result, name) for name in names):
            candidates.append(tuple(getattr(result, name) for name in names))

    # 2) __dict__ ou dataclass
    try:
        d = dict(vars(result))
    except Exception:
        d = {}
    if d:
        lower = {str(k).lower(): k for k in d.keys()}
        name_sets = [
            ("n", "m_y", "m_z"),
            ("n", "my", "mz"),
            ("n_i", "m_y_i", "m_z_i"),
        ]
        for a, b, c in name_sets:
            if a in lower and b in lower and c in lower:
                candidates.append((d[lower[a]], d[lower[b]], d[lower[c]]))

    # 3) objecto com dataframe exportável
    for method_name in ["to_dataframe", "as_dataframe"]:
        if hasattr(result, method_name):
            try:
                df = getattr(result, method_name)()
                cols = {normalize_text(c).replace(" ", ""): c for c in df.columns}
                ncol = cols.get("n") or cols.get("axialforce") or cols.get("normalforce")
                mycol = cols.get("m_y") or cols.get("my")
                mzcol = cols.get("m_z") or cols.get("mz")
                if ncol and mycol and mzcol:
                    candidates.append((df[ncol], df[mycol], df[mzcol]))
            except Exception:
                pass

    for n_raw, my_raw, mz_raw in candidates:
        n = _flatten_numeric_v50(n_raw)
        my = _flatten_numeric_v50(my_raw)
        mz = _flatten_numeric_v50(mz_raw)
        if n is None or my is None or mz is None:
            continue
        m = min(len(n), len(my), len(mz))
        if m >= 3:
            return n[:m], my[:m], mz[:m]
    return None, None, None


def _call_sc_method_v50(method, **kwargs):
    import inspect
    sig = inspect.signature(method)
    accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
    if accepts_kwargs:
        return method(**kwargs)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return method(**filtered)


def _sc2023_section_from_layout_v50(layout, fck: float, fyk: float, Es: float):
    sc, err = _sc2023_import_all_v50()
    if sc is None:
        raise RuntimeError(f"structuralcodes/shapely indisponível: {err}")

    Polygon = sc["Polygon"]
    SurfaceGeometry = sc["SurfaceGeometry"]
    add_reinforcement = sc["add_reinforcement"]
    create_concrete = sc["create_concrete"]
    create_reinforcement = sc["create_reinforcement"]
    BeamSection = sc["BeamSection"]

    concrete = create_concrete(fck=float(fck))
    # Valores conservadores por defeito para criar o material no structuralcodes.
    # O valor fyd é calculado por structuralcodes.codes.ec2_2023.fyd noutra fase.
    reinforcement = create_reinforcement(
        fyk=float(fyk),
        Es=float(Es),
        ftk=max(1.08 * float(fyk), float(fyk) + 1.0),
        epsuk=0.05,
    )

    b = float(getattr(layout, "b_mm", 0.0))
    h = float(getattr(layout, "h_mm", 0.0))
    poly = Polygon([
        (-b / 2.0, -h / 2.0),
        ( b / 2.0, -h / 2.0),
        ( b / 2.0,  h / 2.0),
        (-b / 2.0,  h / 2.0),
    ])
    geometry = SurfaceGeometry(poly=poly, material=concrete)

    # Usa exactamente as posições e diâmetros do layout corrente do ColumnsEC2,
    # incluindo layouts mistos 4Ø25 + nØ16.
    try:
        bar_points = _layout_bar_points_v45(layout)
    except Exception:
        bar_points = []
        for y, z in ColumnDesigner.layout_coordinates(ColumnDesigner, layout):
            bar_points.append((y, z, float(getattr(layout, "phi_long_mm", 12.0))))

    for y, z, phi in bar_points:
        geometry = add_reinforcement(geometry, (float(y), float(z)), float(phi), reinforcement)

    # Recentrar na origem se a versão disponibilizar gross_properties/translate.
    try:
        section0 = BeamSection(geometry=geometry)
        gp = section0.gross_properties
        cy = float(getattr(gp, "cy", 0.0)) if hasattr(gp, "cy") else 0.0
        cz = float(getattr(gp, "cz", 0.0)) if hasattr(gp, "cz") else 0.0
        if abs(cy) > 1e-9 or abs(cz) > 1e-9:
            geometry = geometry.translate(dy=-cy, dz=-cz)
    except Exception:
        pass
    return BeamSection(geometry=geometry)


def _sc2023_nmm_capacities_v50(layout, n_ed_kN: float, fcd: float, fyd: float, Es: float):
    """Obtém capacidade biaxial a partir do SectionCalculator do structuralcodes.

    Se a API não estiver disponível/compatível, devolve erro explícito. Não recorre
    ao motor interno para o backend EC2:2023.
    """
    fck = getattr(layout, "_sc_fck", None)
    fyk = getattr(layout, "_sc_fyk", None)
    if fck is None:
        fck = globals().get("_SC2023_LAST_FCK", 30.0)
    if fyk is None:
        fyk = globals().get("_SC2023_LAST_FYK", 500.0)

    section = _sc2023_section_from_layout_v50(layout, float(fck), float(fyk), float(Es))
    calc = section.section_calculator
    if not hasattr(calc, "calculate_nmm_interaction_domain"):
        raise RuntimeError("A instalação do structuralcodes não expõe calculate_nmm_interaction_domain().")

    method = calc.calculate_nmm_interaction_domain
    attempts = [
        {},
        {"num_theta": 48},
        {"n_theta": 48},
        {"theta_res": 48},
        {"num_theta": 48, "num_axial": 80},
        {"n_theta": 48, "n_axial": 80},
    ]
    last_err = None
    result = None
    for kwargs in attempts:
        try:
            result = _call_sc_method_v50(method, **kwargs)
            break
        except Exception as err:
            last_err = err
            result = None
    if result is None:
        raise RuntimeError(f"Falha ao chamar calculate_nmm_interaction_domain(): {last_err}")

    n_arr, my_arr, mz_arr = _extract_nmm_arrays_v50(result)
    if n_arr is None:
        raise RuntimeError("Não foi possível extrair arrays N, My, Mz do resultado do structuralcodes.")

    import numpy as np
    n_arr = np.asarray(n_arr, dtype=float)
    my_arr = np.asarray(my_arr, dtype=float)
    mz_arr = np.asarray(mz_arr, dtype=float)
    mask = np.isfinite(n_arr) & np.isfinite(my_arr) & np.isfinite(mz_arr)
    n_arr, my_arr, mz_arr = n_arr[mask], my_arr[mask], mz_arr[mask]
    if len(n_arr) < 3:
        raise RuntimeError("A superfície N-My-Mz do structuralcodes devolveu pontos insuficientes.")

    # structuralcodes pode usar compressão com sinal oposto. Trabalhamos por nível
    # absoluto de esforço normal, porque o ColumnsEC2 recebe NEd de compressão por módulo.
    target_n = abs(float(n_ed_kN) * 1e3)
    absn = np.abs(n_arr)
    tol = max(0.05 * target_n, 25e3)
    close = np.abs(absn - target_n) <= tol
    if not np.any(close):
        order = np.argsort(np.abs(absn - target_n))[:max(12, min(60, len(absn)))]
    else:
        order = np.where(close)[0]

    caps = []
    for i in order:
        # Momentos structuralcodes em Nmm, convertidos para kNm.
        my_kNm = abs(float(my_arr[i])) / 1e6
        mz_kNm = abs(float(mz_arr[i])) / 1e6
        if my_kNm > 1e-9 and mz_kNm > 1e-9:
            caps.append((my_kNm, mz_kNm))
    if not caps:
        raise RuntimeError("Não foram obtidos pontos resistentes úteis na superfície N-My-Mz do structuralcodes.")
    return caps


# Guardar o método final antes do modo estrito.
_old_capacity_for_layout_v50 = ColumnDesigner.capacity_for_layout


def _capacity_for_layout_v50(self, layout, n_ed_kN: float, fcd: float, fyd: float, Es: float):
    if _sc2023_active(getattr(self, "code_backend", None)):
        try:
            caps = _sc2023_nmm_capacities_v50(layout, n_ed_kN, fcd, fyd, Es)
            self._last_sc2023_capacity_error = ""
            self._last_sc2023_capacity_source = "structuralcodes.sections.BeamSection.calculate_nmm_interaction_domain"
            return caps
        except Exception as err:
            self._last_sc2023_capacity_error = str(err)
            self._last_sc2023_capacity_source = "structuralcodes — falha"
            return []
    return _old_capacity_for_layout_v50(self, layout, n_ed_kN, fcd, fyd, Es)

ColumnDesigner.capacity_for_layout = _capacity_for_layout_v50


# Pós-processamento do design: no EC2:2023 estrito, marcar todos os módulos que
# não foram calculados pelo structuralcodes como avisos, em vez de usar resultados
# internos sem rastreabilidade.
_old_design_one_v50 = ColumnDesigner.design_one


def _design_one_v50(self, row: pd.Series, prebuilt_candidates=None):
    old_backend = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    globals()["ACTIVE_CODE_BACKEND_V48"] = getattr(self, "code_backend", old_backend)
    try:
        # Valores usados pelo construtor de secções structuralcodes.
        try:
            globals()["_SC2023_LAST_FCK"] = parse_concrete_strength(str(row.get("material", "C30/37")))
            globals()["_SC2023_LAST_FYK"] = float(getattr(self, "fyk", 500.0))
        except Exception:
            pass
        out = _old_design_one_v50(self, row, prebuilt_candidates=prebuilt_candidates)
    finally:
        globals()["ACTIVE_CODE_BACKEND_V48"] = old_backend

    if not isinstance(out, dict):
        return out

    if _sc2023_active(getattr(self, "code_backend", None)):
        cap_err = getattr(self, "_last_sc2023_capacity_error", "")
        cap_src = getattr(self, "_last_sc2023_capacity_source", "")
        out["code_backend"] = BACKEND_EC2_2023_SC
        out["ec2_2023_strict_mode"] = "Sim"
        out["nmm_capacity_source"] = cap_src or "structuralcodes.sections"
        out["normative_basis"] = (
            "Eurocode 2:2023 — modo estrito via structuralcodes. Materiais e secção N-My-Mz são calculados "
            "por structuralcodes; módulos sem API EC2:2023 exposta no pacote são assinalados como Aviso, sem fallback interno."
        )
        if cap_err:
            out["backend_note"] = f"Falha no cálculo seccional structuralcodes: {cap_err}"
            out["status"] = "Aviso" if out.get("status") != "Falha" else out.get("status")
            out["failure_type"] = out.get("failure_type") or "backend_structuralcodes"
            out["failure_reason"] = (str(out.get("failure_reason", "") or "") + "; " + out["backend_note"]).strip("; ")

        # EC2 2023 no structuralcodes documentado para materiais, secções, fendilhação/deflexão/fluência.
        # A documentação pública não lista shear/torsion EC2:2023; não usar fórmulas internas como se fossem structuralcodes.
        out["shear_status_y"] = "Aviso: esforço transverso não calculado pelo structuralcodes EC2:2023 nesta versão"
        out["shear_status_z"] = "Aviso: esforço transverso não calculado pelo structuralcodes EC2:2023 nesta versão"
        out["torsion_status"] = "Aviso: torção não calculada pelo structuralcodes EC2:2023 nesta versão"
        for k in ["v_rd_c_y_kN", "v_rd_c_z_kN", "v_rd_max_y_kN", "v_rd_max_z_kN", "asw_s_y_req_mm2_per_m", "asw_s_z_req_mm2_per_m", "t_rd_max_kNm", "asw_s_t_req_mm2_per_m", "asl_t_req_mm2"]:
            if k in out:
                out[k] = None
        # Mantém estado global resistente por N-My-Mz. V/T ficam como aviso, não falha.
        if str(out.get("status", "")).lower() == "falha" and not str(out.get("failure_reason", "")).strip():
            out["status"] = "Aviso"
        rec = str(out.get("recommendations", "") or "")
        add = "validar V/T por outro módulo EC2:2023 ou aguardar função structuralcodes correspondente"
        if add not in rec:
            out["recommendations"] = (rec + "; " + add).strip("; ")
    return out

ColumnDesigner.design_one = _design_one_v50


# ELS/fendilhação em EC2:2023 usando structuralcodes quando possível.
_old_elastic_service_check_v50 = elastic_service_check


def _sc2023_service_check_v50(n_kN, my_kNm, mz_kNm, b_mm, h_mm, iy_mm4, iz_mm4, as_mm2, fck, fyk, ecm, fctm, exposure="XC3"):
    base = _old_elastic_service_check_v50(n_kN, my_kNm, mz_kNm, b_mm, h_mm, iy_mm4, iz_mm4, as_mm2, fck, fyk, ecm, fctm)
    if not _sc2023_active():
        return base
    try:
        ec23 = _require_ec2_2023_structuralcodes_v48()
        Es = float(ec23.Es())
        alphae = Es / max(float(ecm), 1e-9)
        sigma_s = abs(float(base.get("service_sigma_s_max_MPa", 0.0) or 0.0))
        if sigma_s <= 1e-9:
            base.update({
                "service_backend": "structuralcodes EC2:2023",
                "service_wk_mm": 0.0,
                "service_status": base.get("service_status", "OK"),
            })
            return base
        # Dados equivalentes simplificados para chamar a API EC2:2023 de fendilhação.
        phi_eq = 16.0
        try:
            phi_eq = float(base.get("service_phi_eq_mm", phi_eq) or phi_eq)
        except Exception:
            pass
        c_nom = 35.0
        rho_eff = max(float(as_mm2) / max(float(b_mm) * max(0.25 * float(h_mm), 1.0), 1e-9), 1e-5)
        x = 0.45 * float(h_mm)
        hceff = min(2.5 * (float(h_mm) - x), float(h_mm) / 2.0)
        hceff = max(hceff, 1.0)
        try:
            kfl_ = float(ec23.kfl(float(h_mm), float(h_mm) / 2.0, hceff))
        except Exception:
            kfl_ = 1.0
        try:
            wk, invr, srm, epsdiff = ec23.wk_cal(
                kw=1.0,
                h=float(h_mm),
                xg=float(h_mm) / 2.0,
                hc_eff=hceff,
                c=c_nom,
                kb=1.0,
                phi=phi_eq,
                rho_eff=rho_eff,
                x=x,
                sigma_s=sigma_s,
                kt=0.6,
                fct_eff=float(fctm),
                alphae=alphae,
                Es=Es,
            )
        except Exception:
            epsdiff = ec23.epssm_epscm(sigma_s=sigma_s, kt=0.6, fct_eff=float(fctm), rho_eff=rho_eff, alphae=alphae, Es=Es)
            srm = ec23.srm_cal(c=c_nom, kfl_=kfl_, kb=1.0, phi=phi_eq, rho_eff=rho_eff, kw=1.0, h=float(h_mm), x=x)
            invr = 0.0
            wk = ec23.wk_cal2(kw=1.0, k_1_r=1.0, srm_cal=srm, epssm_epscm=epsdiff)
        base.update({
            "service_backend": "structuralcodes EC2:2023",
            "service_wk_mm": float(wk),
            "service_srm_mm": float(srm),
            "service_epssm_epscm": float(epsdiff),
            "service_curvature_factor": float(invr),
        })
        # Limites de w_k não são impostos sem classe/exigência indicada; fica informativo.
        if float(wk) > 0.30:
            base["service_status"] = "Aviso: w_k > 0.30 mm"
        return base
    except Exception as err:
        base.update({
            "service_backend": "structuralcodes EC2:2023 — falha",
            "service_status": "Aviso: ELS structuralcodes não calculado",
            "service_note": str(err),
        })
        return base


def elastic_service_check(n_kN, my_kNm, mz_kNm, b_mm, h_mm, iy_mm4, iz_mm4, as_mm2, fck, fyk, ecm, fctm):
    return _sc2023_service_check_v50(n_kN, my_kNm, mz_kNm, b_mm, h_mm, iy_mm4, iz_mm4, as_mm2, fck, fyk, ecm, fctm)

globals()["elastic_service_check"] = elastic_service_check

# Também redirecciona a versão v4, quando chamada depois deste patch.
_old_elastic_service_check_v4_v50 = globals().get("elastic_service_check_v4", None)
if _old_elastic_service_check_v4_v50 is not None:
    def elastic_service_check_v4(n_kN, my_kNm, mz_kNm, b_mm, h_mm, iy_mm4, iz_mm4, as_mm2, fck, fyk, ecm, fctm, exposure="XC3"):
        return _sc2023_service_check_v50(n_kN, my_kNm, mz_kNm, b_mm, h_mm, iy_mm4, iz_mm4, as_mm2, fck, fyk, ecm, fctm, exposure=exposure)
    globals()["elastic_service_check_v4"] = elastic_service_check_v4


# Melhorar validação/GUI: deixar claro que EC2:2023 é estrito e depende do structuralcodes.
_old_validate_inputs_v50 = ColumnsEC2App.validate_inputs


def _validate_inputs_v50(self):
    err = _old_validate_inputs_v50(self)
    if err:
        return err
    backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    if _sc2023_active(backend):
        sc, sc_err = _sc2023_import_all_v50()
        if sc is None:
            return (
                "O modo Eurocode 2:2023 estrito requer structuralcodes e shapely.\n\n"
                "Instale com:\npython -m pip install structuralcodes shapely\n\n"
                f"Erro original: {sc_err}"
            )
        calc_ok = hasattr(sc["BeamSection"], "__init__")
        if not calc_ok:
            return "Instalação structuralcodes inválida: BeamSection indisponível."
    return None

ColumnsEC2App.validate_inputs = _validate_inputs_v50


_old_build_normative_notes_v50 = ColumnsEC2App.build_normative_notes


def _build_normative_notes_v50(self) -> pd.DataFrame:
    try:
        notes = _old_build_normative_notes_v50(self).copy()
    except Exception:
        notes = pd.DataFrame(columns=["Tema", "Referência", "Nota"])
    extra = pd.DataFrame([
        ("EC2:2023 strict", "structuralcodes", "Quando seleccionado, o cálculo seccional N-My-Mz é efectuado pelo SectionCalculator do structuralcodes. Não é usado fallback interno para a resistência seccional."),
        ("EC2:2023 strict", "V/T", "Se a versão instalada do structuralcodes não disponibilizar funções EC2:2023 para esforço transverso/torção, estes módulos são assinalados como Aviso e não são substituídos por fórmulas internas."),
        ("EC2:2023 strict", "ELS", "A fendilhação em ELS usa funções structuralcodes.codes.ec2_2023.wk_cal/epssm_epscm/srm_cal quando disponíveis."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True).drop_duplicates()

ColumnsEC2App.build_normative_notes = _build_normative_notes_v50



# ============================================================
# ColumnsEC2 v5.1 — separação rígida de backends
# ============================================================
APP_VERSION = "v5.1"
APP_XLSX_DESCRIPTION = (
    "Workbook de cálculo com separação rígida de backends: EC2 Portugal 2010 por defeito "
    "e Eurocode 2:2023 estrito via structuralcodes quando seleccionado. O backend EC2:2023 "
    "não usa fórmulas internas para verificações normativas; módulos não expostos pelo pacote "
    "são reportados como não avaliados."
)

SC2023_STRICT_NOT_AVAILABLE = "Não avaliado neste backend: função EC2:2023 não exposta pelo structuralcodes instalado"


def _sc2023_backend_map_v51() -> pd.DataFrame:
    """Mapa explícito do que é calculado por cada backend.

    No modo EC2:2023, este mapa é a regra: não há fallback interno para módulos
    normativos. O programa pode organizar dados, gerar candidatos geométricos e
    exportar relatórios, mas a verificação normativa fica limitada às funções
    expostas pelo structuralcodes.
    """
    return pd.DataFrame([
        ["Materiais - betão", BACKEND_EC2_PT_2010, "motor ColumnsEC2 / NP EN 1992-1-1 PT", "fck, fcd, fctm, Ecm"],
        ["Materiais - aço", BACKEND_EC2_PT_2010, "motor ColumnsEC2 / NP EN 1992-1-1 PT", "fyd, Es"],
        ["2.ª ordem", BACKEND_EC2_PT_2010, "motor ColumnsEC2", "método interno já existente"],
        ["Resistência N-My-Mz", BACKEND_EC2_PT_2010, "motor ColumnsEC2", "superfície interna discreta"],
        ["Esforço transverso", BACKEND_EC2_PT_2010, "motor ColumnsEC2", "verificação interna EC2 PT"],
        ["Torção", BACKEND_EC2_PT_2010, "motor ColumnsEC2", "verificação interna EC2 PT"],
        ["ELS", BACKEND_EC2_PT_2010, "motor ColumnsEC2", "verificação interna/simplificada ou combinação indicada"],
        ["Pormenorização", BACKEND_EC2_PT_2010, "motor ColumnsEC2", "regras internas EC2 PT"],
        ["Materiais - betão", BACKEND_EC2_2023_SC, "structuralcodes.codes.ec2_2023", "obrigatório; sem fallback"],
        ["Materiais - aço", BACKEND_EC2_2023_SC, "structuralcodes.codes.ec2_2023", "obrigatório; sem fallback"],
        ["Resistência N-My-Mz", BACKEND_EC2_2023_SC, "structuralcodes.sections.BeamSection / SectionCalculator", "obrigatório; sem fallback"],
        ["ELS/fendilhação", BACKEND_EC2_2023_SC, "structuralcodes.codes.ec2_2023", "quando API disponível; sem fallback"],
        ["2.ª ordem", BACKEND_EC2_2023_SC, "não calculado pelo ColumnsEC2", SC2023_STRICT_NOT_AVAILABLE],
        ["Esforço transverso", BACKEND_EC2_2023_SC, "não calculado pelo ColumnsEC2", SC2023_STRICT_NOT_AVAILABLE],
        ["Torção", BACKEND_EC2_2023_SC, "não calculado pelo ColumnsEC2", SC2023_STRICT_NOT_AVAILABLE],
        ["Pormenorização normativa", BACKEND_EC2_2023_SC, "não calculada pelo ColumnsEC2", SC2023_STRICT_NOT_AVAILABLE],
        ["DXF/PDF/XLSX", "ambos", "ColumnsEC2", "exportação e apresentação; não altera o backend normativo"],
        ["Shortlist geométrica", "ambos", "ColumnsEC2", "geração de alternativas geométricas de armadura; verificação EC2:2023 só por structuralcodes"],
    ], columns=["Modulo", "Backend", "Origem", "Nota"])


def _sc2023_api_capabilities_v51() -> pd.DataFrame:
    rows = []
    sc, err = _sc2023_import_all_v50()
    if sc is None:
        return pd.DataFrame([["structuralcodes", "indisponível", str(err)]], columns=["Objeto", "Estado", "Nota"])
    ec23 = sc.get("ec23")
    checks = [
        ("ec2_2023.fcd", hasattr(ec23, "fcd")),
        ("ec2_2023.fctm", hasattr(ec23, "fctm")),
        ("ec2_2023.Ecm", hasattr(ec23, "Ecm")),
        ("ec2_2023.fyd", hasattr(ec23, "fyd")),
        ("ec2_2023.Es", hasattr(ec23, "Es")),
        ("ec2_2023.wk_cal", hasattr(ec23, "wk_cal")),
        ("ec2_2023.epssm_epscm", hasattr(ec23, "epssm_epscm")),
        ("ec2_2023.srm_cal", hasattr(ec23, "srm_cal")),
        ("geometry.SurfaceGeometry", sc.get("SurfaceGeometry") is not None),
        ("sections.BeamSection", sc.get("BeamSection") is not None),
    ]
    try:
        dummy = sc.get("BeamSection")
        rows.append(["BeamSection", "disponível" if dummy is not None else "indisponível", "classe importada"])
    except Exception as e:
        rows.append(["BeamSection", "erro", str(e)])
    for name, ok in checks:
        rows.append([name, "disponível" if ok else "indisponível", ""])
    return pd.DataFrame(rows, columns=["Objeto", "Estado", "Nota"])


def _sc2023_safe_props_v51(fck: float, fyk: float, gamma_c: float, gamma_s: float) -> Tuple[Dict[str, float], Dict[str, float]]:
    old_backend = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    globals()["ACTIVE_CODE_BACKEND_V48"] = BACKEND_EC2_2023_SC
    try:
        cp = concrete_props(float(fck), gamma_c=float(gamma_c))
        sp = steel_props(float(fyk), gamma_s=float(gamma_s))
    finally:
        globals()["ACTIVE_CODE_BACKEND_V48"] = old_backend
    return cp, sp


def _base_output_keys_v51(row, material, b_mm, h_mm, n_ed_kN, my_i, my_j, mz_i, mz_j, my_ed, mz_ed):
    return {
        "member": row.get("member", ""),
        "case": row.get("case", ""),
        "name": row.get("name", ""),
        "story": row.get("story", ""),
        "prumada": row.get("name", "") or row.get("member", ""),
        "node_i": row.get("node_i", ""),
        "node_j": row.get("node_j", ""),
        "member_case_i": row.get("member_case_i", ""),
        "member_case_j": row.get("member_case_j", ""),
        "material": material,
        "b_cm": b_mm / 10.0 if b_mm else None,
        "h_cm": h_mm / 10.0 if h_mm else None,
        "length_m": safe_float(row.get("length", 0.0), 0.0),
        "n_nodes_found": int(safe_float(row.get("n_nodes_found", 0), 0)),
        "n_ed_kN": n_ed_kN,
        "my_i_kNm": my_i,
        "my_j_kNm": my_j,
        "mz_i_kNm": mz_i,
        "mz_j_kNm": mz_j,
        "my_ed_kNm": my_ed,
        "mz_ed_kNm": mz_ed,
        "lambda_y": None,
        "lambda_z": None,
        "lambda_lim_y": None,
        "lambda_lim_z": None,
        "lambda_check_y": "Não calculado no backend EC2:2023 structuralcodes estrito",
        "lambda_check_z": "Não calculado no backend EC2:2023 structuralcodes estrito",
        "m0e_y_kNm": None,
        "m0e_z_kNm": None,
        "m2_y_kNm": None,
        "m2_z_kNm": None,
        "second_order_y": "Não avaliado pelo backend EC2:2023 structuralcodes",
        "second_order_z": "Não avaliado pelo backend EC2:2023 structuralcodes",
        "as_min_mm2": None,
        "as_req_mm2": None,
        "as_max_mm2": None,
        "max_bars_face_y": None,
        "max_bars_face_z": None,
        "phi_long_mm": None,
        "n_total": None,
        "n_bars_y": None,
        "n_bars_z": None,
        "as_prov_mm2": None,
        "phi_st_mm": None,
        "s_st_mm": None,
        "s_st_max_mm": None,
        "mrd_y_kNm": None,
        "mrd_z_kNm": None,
        "utilizacao": None,
        "solucao": "",
        "shortlist_text": "",
        "code_backend": BACKEND_EC2_2023_SC,
        "ec2_2023_strict_mode": "Sim",
        "normative_basis": "Eurocode 2:2023 — structuralcodes estrito; sem fallback para fórmulas internas.",
        "backend_scope": "Apenas verificações expostas pelo pacote structuralcodes são calculadas neste modo.",
    }


def _sc2023_util_from_caps_v51(my_ed_kNm: float, mz_ed_kNm: float, capacities: List[Tuple[float, float]]):
    """Utilização geométrica da superfície devolvida pelo structuralcodes.

    Não é uma fórmula normativa interna; apenas compara o vector solicitante com
    os pontos resistentes N-My-Mz fornecidos pelo backend.
    """
    if not capacities:
        return False, None, None, None
    import math as _math
    my_req = abs(float(my_ed_kNm or 0.0))
    mz_req = abs(float(mz_ed_kNm or 0.0))
    r_req = _math.hypot(my_req, mz_req)
    if r_req <= 1e-9:
        # Qualquer capacidade axial compatível é suficiente para flexão nula.
        my_cap, mz_cap = capacities[0]
        return True, 0.0, my_cap, mz_cap
    theta_req = _math.atan2(mz_req, my_req)
    best = None
    for my_cap, mz_cap in capacities:
        myc = abs(float(my_cap or 0.0)); mzc = abs(float(mz_cap or 0.0))
        r_cap = _math.hypot(myc, mzc)
        if r_cap <= 1e-9:
            continue
        theta_cap = _math.atan2(mzc, myc)
        dtheta = abs(theta_cap - theta_req)
        dtheta = min(dtheta, abs(_math.pi - dtheta))
        # penalização suave por desalinhamento angular; evita aprovar com ponto longe da direcção solicitante
        util = r_req / max(r_cap * max(_math.cos(dtheta), 0.15), 1e-9)
        cand = (util, myc, mzc, dtheta)
        if best is None or cand[0] < best[0]:
            best = cand
    if best is None:
        return False, None, None, None
    return best[0] <= 1.0, best[0], best[1], best[2]


_old_design_one_v51 = ColumnDesigner.design_one


def _design_one_v51(self, row: pd.Series, prebuilt_candidates=None):
    # Backend Portugal/default: não alterar o comportamento existente.
    if not _sc2023_active(getattr(self, "code_backend", None)):
        return _old_design_one_v51(self, row, prebuilt_candidates=prebuilt_candidates)

    old_backend = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    globals()["ACTIVE_CODE_BACKEND_V48"] = BACKEND_EC2_2023_SC
    try:
        material = str(row.get("material", "") or "").strip()
        if not re.search(r"C\s*\d+\s*/\s*\d+", material, re.I):
            reason = "Classe de betão ausente ou inválida; no backend EC2:2023 strict não é usado material por defeito."
            return {
                **_base_output_keys_v51(row, material, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                "status": "Falha",
                "failure_type": "dados_incompletos",
                "failure_reason": reason,
                "failure_severity": "Bloqueante",
                "design_decision": "Corrigir a coluna Material antes de calcular com EC2:2023 strict.",
                "review_priority": "Alta",
                "failure_action": "Indicar classe Cxx/yy na tabela de entrada.",
                "recommendations": "Preencher a coluna Material; não há fallback no backend EC2:2023 strict.",
            }

        fck = parse_concrete_strength(material)
        cp, sp = _sc2023_safe_props_v51(fck, float(getattr(self, "fyk", 500.0)), float(getattr(self, "gamma_c", 1.5)), float(getattr(self, "gamma_s", 1.15)))
        fyd = float(sp.get("fyd")); Es = float(sp.get("Es")); fcd = float(cp.get("fcd"))

        b_mm = cm_to_mm(row.get("hy", 0.0))
        h_mm = cm_to_mm(row.get("hz", 0.0))
        ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
        if b_mm <= 0 and ac_mm2 > 0 and math.isfinite(ac_mm2):
            b_mm = math.sqrt(ac_mm2)
        if h_mm <= 0:
            h_mm = b_mm
        if b_mm <= 0 or h_mm <= 0:
            reason = "Geometria da secção ausente ou inválida."
            return {**_base_output_keys_v51(row, material, b_mm, h_mm, 0, 0, 0, 0, 0, 0), "status": "Falha", "failure_type": "dados_incompletos", "failure_reason": reason, "failure_severity": "Bloqueante", "design_decision": "Corrigir geometria da tabela.", "review_priority": "Alta", "failure_action": "Verificar HY/HZ/AX.", "recommendations": "Corrigir HY/HZ/AX."}

        n_nodes = int(safe_float(row.get("n_nodes_found", 0), 0))
        n_ed_kN = max(abs(safe_float(row.get("fx_i", 0.0), 0.0)), abs(safe_float(row.get("fx_j", 0.0), 0.0)))
        my_i = safe_float(row.get("my_i", 0.0), 0.0); my_j = safe_float(row.get("my_j", 0.0), 0.0)
        mz_i = safe_float(row.get("mz_i", 0.0), 0.0); mz_j = safe_float(row.get("mz_j", 0.0), 0.0)
        # No modo strict, os efeitos de 2.ª ordem não são calculados internamente.
        # Usam-se os esforços importados como efeitos de cálculo já definidos pelo utilizador.
        my_ed = max(abs(my_i), abs(my_j))
        mz_ed = max(abs(mz_i), abs(mz_j))
        base = _base_output_keys_v51(row, material, b_mm, h_mm, n_ed_kN, my_i, my_j, mz_i, mz_j, my_ed, mz_ed)
        base.update({
            "mat_fcd_used_MPa": fcd,
            "mat_fctm_used_MPa": cp.get("fctm"),
            "mat_Ecm_used_MPa": cp.get("Ecm"),
            "steel_fyd_used_MPa": fyd,
            "steel_Es_used_MPa": Es,
            "ec2_2023_eta_cc": cp.get("eta_cc"),
            "ec2_2023_k_tc": cp.get("k_tc"),
            "shear_status_y": SC2023_STRICT_NOT_AVAILABLE,
            "shear_status_z": SC2023_STRICT_NOT_AVAILABLE,
            "torsion_status": SC2023_STRICT_NOT_AVAILABLE,
            "service_status": "ELS/fendilhação: calculado por structuralcodes apenas se a API estiver disponível; caso contrário, não avaliado.",
            "detailing_status": "Pormenorização normativa não avaliada no modo EC2:2023 strict, excepto geometria da solução desenhada.",
        })
        if n_nodes < 2:
            reason = "Dados incompletos: member/case sem os dois nós necessários."
            base.update({"status": "Falha", "failure_type": "dados_incompletos", "failure_reason": reason, "failure_severity": "Bloqueante", "design_decision": "Corrigir a tabela antes de calcular.", "review_priority": "Alta", "failure_action": "Confirmar duas linhas por member/case.", "recommendations": "Corrigir os dados de entrada."})
            return base

        is_circular = self.infer_is_circular(row, b_mm, h_mm)
        candidates = prebuilt_candidates if prebuilt_candidates is not None else self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)
        # Geração de candidatos é geométrica; a verificação resistente é estruturalcodes.
        candidates = [c for c in candidates if getattr(c, "as_prov_mm2", 0.0) > 0 and c.clear_spacing_ok()]
        # Shortlist prática: diâmetros correntes, menos varões, menor área, soluções mistas depois das simples equivalentes.
        candidates = sorted(candidates, key=lambda c: (
            0 if getattr(c, "layout_type", "uniform") == "uniform" else 1,
            abs(getattr(c, "as_prov_mm2", 0.0) - max(0.002 * b_mm * h_mm, 0.0)),
            getattr(c, "as_prov_mm2", 0.0),
            getattr(c, "n_total", 999),
            getattr(c, "phi_long_mm", 99),
        ))[:80]
        if not candidates:
            reason = "Não foi possível gerar soluções geométricas de armadura para a secção."
            base.update({"status": "Falha", "failure_type": "pormenorizacao", "failure_reason": reason, "failure_severity": "Bloqueante", "design_decision": "Rever secção/recobrimento/diâmetros.", "review_priority": "Alta", "failure_action": "Ajustar secção ou parâmetros geométricos.", "recommendations": "Rever secção, recobrimento e catálogo de armaduras."})
            return base

        shortlist_rows = []
        chosen = None; chosen_util = None; chosen_caps = (None, None); last_err = ""
        for layout in candidates:
            try:
                setattr(layout, "_sc_fck", float(fck)); setattr(layout, "_sc_fyk", float(getattr(self, "fyk", 500.0)))
                caps = self.capacity_for_layout(layout, n_ed_kN, fcd, fyd, Es)
                ok, util, my_cap, mz_cap = _sc2023_util_from_caps_v51(my_ed, mz_ed, caps)
                desc = getattr(layout, "description", f"{layout.n_total}Ø{int(layout.phi_long_mm)}")
                shortlist_rows.append({"solucao": desc, "as_prov_mm2": layout.as_prov_mm2, "utilizacao": "" if util is None else f"{util:.3f}", "status_short": "OK" if ok else "Falha", "failure_short": "" if ok else "N-My-Mz structuralcodes"})
                if ok:
                    chosen = layout; chosen_util = util; chosen_caps = (my_cap, mz_cap)
                    break
            except Exception as err:
                last_err = str(err)
                desc = getattr(layout, "description", f"{getattr(layout, 'n_total', '')}Ø{int(getattr(layout, 'phi_long_mm', 0))}")
                shortlist_rows.append({"solucao": desc, "as_prov_mm2": getattr(layout, "as_prov_mm2", 0.0), "utilizacao": "", "status_short": "Erro", "failure_short": last_err[:80]})

        base["shortlist_text"] = serialize_shortlist(shortlist_rows[:20])
        if chosen is None:
            reason = "Nenhuma solução verificada pela superfície N-My-Mz do structuralcodes."
            if last_err:
                reason += f" Último erro: {last_err}"
            base.update({"status": "Falha", "failure_type": "resistencia_nmm_structuralcodes", "failure_reason": reason, "failure_severity": "Bloqueante", "design_decision": "Não aceitar sem nova secção/armadura ou validação do backend.", "review_priority": "Alta", "failure_action": "Aumentar secção/armadura ou verificar instalação/API do structuralcodes.", "recommendations": "Rever esforços, secção e armadura; confirmar versão do structuralcodes."})
            return base

        smax = None; sprov = None
        try:
            smax = self.tie_spacing_max(b_mm, h_mm, chosen.phi_long_mm)
            sprov = self.choose_spacing(smax)
        except Exception:
            pass
        sol_desc = getattr(chosen, "description", f"{chosen.n_total}Ø{int(chosen.phi_long_mm)}")
        if sprov:
            sol_desc += f" + estribos Ø{int(chosen.phi_st_mm)}//{sprov/10:.1f} cm"
        base.update({
            "phi_long_mm": getattr(chosen, "phi_long_mm", None),
            "n_total": getattr(chosen, "n_total", None),
            "n_bars_y": getattr(chosen, "n_bars_y", None),
            "n_bars_z": getattr(chosen, "n_bars_z", None),
            "as_prov_mm2": getattr(chosen, "as_prov_mm2", None),
            "phi_st_mm": getattr(chosen, "phi_st_mm", None),
            "s_st_mm": sprov,
            "s_st_max_mm": smax,
            "mrd_y_kNm": chosen_caps[0],
            "mrd_z_kNm": chosen_caps[1],
            "utilizacao": chosen_util,
            "solucao": sol_desc,
            "nmm_capacity_source": "structuralcodes.sections.BeamSection/SectionCalculator",
            "capacity_status": "OK",
            # Mantém Aviso porque há módulos que o backend não expôs e não foram substituídos por fórmulas internas.
            "status": "Aviso",
            "failure_type": "backend_structuralcodes_scope",
            "failure_reason": "Resistência N-My-Mz verificada por structuralcodes; 2.ª ordem, esforço transverso, torção e pormenorização normativa não foram calculados porque não há fallback interno no modo EC2:2023 strict.",
            "failure_severity": "Aviso",
            "design_decision": "Aceitável apenas para as verificações efectivamente calculadas pelo structuralcodes; restantes módulos requerem verificação externa ou backend PT.",
            "review_priority": "Média",
            "failure_action": "Validar módulos não disponíveis no backend EC2:2023 structuralcodes.",
            "recommendations": "Usar este modo como verificação EC2:2023 estrita das funções disponíveis; para projecto completo, validar módulos não disponíveis separadamente.",
        })
        return base
    finally:
        globals()["ACTIVE_CODE_BACKEND_V48"] = old_backend


ColumnDesigner.design_one = _design_one_v51


_old_design_dataframe_v51 = ColumnDesigner.design_dataframe


def _design_dataframe_v51(self, df: pd.DataFrame, progress_callback=None):
    # Para EC2:2023 strict, não reutilizar caches internos antigos de resistência.
    if _sc2023_active(getattr(self, "code_backend", None)):
        try:
            self._capacity_cache = {}
        except Exception:
            pass
    return _old_design_dataframe_v51(self, df, progress_callback=progress_callback)


ColumnDesigner.design_dataframe = _design_dataframe_v51


# Validação: EC2:2023 strict exige structuralcodes/shapely e deixa explícito o âmbito.
_old_validate_inputs_v51 = ColumnsEC2App.validate_inputs


def _validate_inputs_v51(self):
    err = _old_validate_inputs_v51(self)
    if err:
        return err
    backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    if _sc2023_active(backend):
        sc, sc_err = _sc2023_import_all_v50()
        if sc is None:
            return (
                "O modo Eurocode 2:2023 strict requer structuralcodes e shapely.\n\n"
                "Instale com:\npython -m pip install structuralcodes shapely\n\n"
                "Neste modo não há fallback para fórmulas internas.\n\n"
                f"Erro original: {sc_err}"
            )
        # Verificação mínima de API de secção. Se não existir, o modo strict não pode correr.
        try:
            BeamSection = sc.get("BeamSection")
            if BeamSection is None:
                return "Modo EC2:2023 strict indisponível: BeamSection não foi importado do structuralcodes."
        except Exception as e:
            return f"Modo EC2:2023 strict indisponível: {e}"
    return None


ColumnsEC2App.validate_inputs = _validate_inputs_v51


# Acrescentar mapa de backend ao Excel, sem interferir com o exportador principal.
_old_write_excel_v51 = ColumnsEC2App._write_excel


def _write_excel_v51(self, path: str):
    _old_write_excel_v51(self, path)
    try:
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            _sc2023_backend_map_v51().to_excel(writer, sheet_name="30_Mapa_Backend", index=False)
            _sc2023_api_capabilities_v51().to_excel(writer, sheet_name="31_API_structuralcodes", index=False)
            # Folha sintética do âmbito real por resultado.
            cols = [c for c in [
                "prumada", "member", "case", "code_backend", "ec2_2023_strict_mode", "normative_basis",
                "nmm_capacity_source", "capacity_status", "shear_status_y", "shear_status_z",
                "torsion_status", "service_status", "detailing_status", "failure_reason"
            ] if self.df_results is not None and c in self.df_results.columns]
            if cols:
                self.df_results[cols].to_excel(writer, sheet_name="32_Escopo_Resultados", index=False)
    except Exception as err:
        # Não falhar a exportação principal por uma folha auxiliar.
        try:
            self.status_var.set(f"Excel exportado; aviso ao escrever mapa backend: {err}")
        except Exception:
            pass


ColumnsEC2App._write_excel = _write_excel_v51


_old_metadata_df_v51 = ColumnsEC2App._metadata_df


def _metadata_df_v51(self) -> pd.DataFrame:
    df = _old_metadata_df_v51(self).copy()
    try:
        backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
        extra = pd.DataFrame([
            ["Backend seleccionado", backend],
            ["Separação de backends", "Rígida: EC2:2023 usa apenas structuralcodes nas verificações disponíveis; sem fallback interno."],
            ["Modo EC2 Portugal", "Mantém o motor ColumnsEC2 existente."],
        ], columns=["Campo", "Valor"])
        return pd.concat([df, extra], ignore_index=True)
    except Exception:
        return df


ColumnsEC2App._metadata_df = _metadata_df_v51


_old_parameters_df_v51 = ColumnsEC2App._parameters_df


def _parameters_df_v51(self) -> pd.DataFrame:
    df = _old_parameters_df_v51(self).copy()
    try:
        backend = _backend_selected_v48(getattr(self, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
        rows = [["Backend", backend]]
        if _sc2023_active(backend):
            rows += [
                ["EC2:2023 strict", "Sim; sem fallback para fórmulas internas"],
                ["Classe desenvolvimento", getattr(self, "var_ec23_strength_class", tk.StringVar(value="CN")).get()],
                ["t_ref [dias]", getattr(self, "var_ec23_tref", tk.StringVar(value="28")).get()],
                ["t0 [dias]", getattr(self, "var_ec23_t0", tk.StringVar(value="28")).get()],
            ]
        return pd.concat([df, pd.DataFrame(rows, columns=["Parâmetro", "Valor"])], ignore_index=True)
    except Exception:
        return df


ColumnsEC2App._parameters_df = _parameters_df_v51


_old_build_normative_notes_v51 = ColumnsEC2App.build_normative_notes


def _build_normative_notes_v51(self) -> pd.DataFrame:
    try:
        notes = _old_build_normative_notes_v51(self).copy()
    except Exception:
        notes = pd.DataFrame(columns=["Tema", "Referência", "Nota"])
    extra = pd.DataFrame([
        ("Backend", "v5.1", "Separação rígida: o backend EC2 Portugal usa o motor interno; o backend EC2:2023 usa apenas structuralcodes para verificações normativas disponíveis."),
        ("EC2:2023 strict", "structuralcodes", "Não há fallback para fórmulas internas. Verificações não expostas pelo pacote são assinaladas como não avaliadas."),
        ("EC2:2023 strict", "relatórios", "PDF/XLSX/DXF continuam a ser gerados pelo ColumnsEC2, mas o relatório identifica o backend e o âmbito efectivamente calculado."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True).drop_duplicates()


ColumnsEC2App.build_normative_notes = _build_normative_notes_v51


# PDF: manter exportador, mas inserir nota de âmbito no relatório sintético quando possível.
_old_write_pdf_v51 = ColumnsEC2App._write_pdf


def _write_pdf_v51(self, path: str):
    # O exportador existente já é sintético. A informação de backend é disponibilizada no XLSX
    # e nas colunas dos resultados. Mantemos o PDF estável para evitar regressões.
    return _old_write_pdf_v51(self, path)


ColumnsEC2App._write_pdf = _write_pdf_v51



# ============================================================
# ColumnsEC2 v5.2 — structuralcodes strict para EC2 2004, EC2 2023 e fib MC2010
# ============================================================
APP_VERSION = "v5.2"
APP_XLSX_DESCRIPTION = (
    "Workbook de cálculo com backends rigidamente separados: NP EN 1992-1-1:2010 PT por defeito; "
    "Eurocode 2:2004, Eurocode 2:2023 e fib Model Code 2010 via structuralcodes em modo strict. "
    "Nos backends structuralcodes não há fallback para fórmulas internas."
)

BACKEND_SC_EC2_2004 = "Eurocode 2:2004 | structuralcodes"
BACKEND_SC_EC2_2023 = "Eurocode 2:2023 | structuralcodes"
BACKEND_SC_MC2010 = "fib Model Code 2010 | structuralcodes"
SC_BACKENDS_V52 = [BACKEND_SC_EC2_2004, BACKEND_SC_EC2_2023, BACKEND_SC_MC2010]
BACKEND_CHOICES_V52 = [BACKEND_EC2_PT_2010] + SC_BACKENDS_V52
SC_NOT_AVAILABLE_V52 = "Não avaliado neste backend: função não exposta pelo structuralcodes instalado"


def _backend_selected_v52(value=None) -> str:
    s0 = str(value or globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)).strip()
    s = s0.lower()
    if "fib" in s and ("2010" in s or "model" in s) and "structuralcodes" in s:
        return BACKEND_SC_MC2010
    if "2004" in s and "structuralcodes" in s:
        return BACKEND_SC_EC2_2004
    if "2023" in s and "structuralcodes" in s:
        return BACKEND_SC_EC2_2023
    return BACKEND_EC2_PT_2010

# Substitui a função de selecção usada por patches anteriores.
globals()["_backend_selected_v48"] = _backend_selected_v52


def _sc_backend_active_v52(value=None) -> bool:
    return _backend_selected_v52(value) in SC_BACKENDS_V52


def _sc_backend_key_v52(value=None) -> str:
    b = _backend_selected_v52(value)
    if b == BACKEND_SC_EC2_2004:
        return "ec2_2004"
    if b == BACKEND_SC_EC2_2023:
        return "ec2_2023"
    if b == BACKEND_SC_MC2010:
        return "mc2010"
    return "pt_2010"

# Patches antigos perguntam por _sc2023_active. Mantém verdadeiro apenas para EC2:2023.
def _sc2023_active(value=None) -> bool:
    return _backend_selected_v52(value) == BACKEND_SC_EC2_2023

globals()["_sc2023_active"] = _sc2023_active


def _sc_import_backend_v52(backend=None):
    """Importa structuralcodes para o backend seleccionado.

    O contrato é rígido: se não existir structuralcodes ou a API necessária, o
    backend devolve erro; não há fallback para fórmulas internas.
    """
    b = _backend_selected_v52(backend)
    key = _sc_backend_key_v52(b)
    if key == "pt_2010":
        return None, "Backend interno PT não usa structuralcodes."
    try:
        import importlib
        from structuralcodes import set_design_code
        from structuralcodes.geometry import SurfaceGeometry, add_reinforcement
        from structuralcodes.materials.concrete import create_concrete
        from structuralcodes.materials.reinforcement import create_reinforcement
        from structuralcodes.sections import BeamSection
        try:
            from shapely import Polygon
        except Exception:
            from shapely.geometry import Polygon

        code_aliases = {
            "ec2_2004": ["ec2_2004", "EC2_2004", "eurocode_2_2004"],
            "ec2_2023": ["ec2_2023", "EC2_2023", "eurocode_2_2023"],
            "mc2010": ["mc2010", "fib_mc2010", "fib_model_code_2010"],
        }
        for alias in code_aliases.get(key, [key]):
            try:
                set_design_code(alias)
                break
            except Exception:
                pass
        modname = {
            "ec2_2004": "structuralcodes.codes.ec2_2004",
            "ec2_2023": "structuralcodes.codes.ec2_2023",
            "mc2010": "structuralcodes.codes.mc2010",
        }[key]
        code_module = importlib.import_module(modname)
        return {
            "backend": b,
            "key": key,
            "module": code_module,
            "Polygon": Polygon,
            "SurfaceGeometry": SurfaceGeometry,
            "add_reinforcement": add_reinforcement,
            "create_concrete": create_concrete,
            "create_reinforcement": create_reinforcement,
            "BeamSection": BeamSection,
        }, None
    except Exception as err:
        return None, err


def _call_sc_func_v52(func, *positional, **kwargs):
    """Chamada tolerante à assinatura, mas sem substituir fórmulas.

    A função tenta passar só os parâmetros aceites pela API instalada. Se a
    função recusar as entradas, o erro é propagado para ser reportado no backend.
    """
    import inspect
    sig = inspect.signature(func)
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        return func(*positional, **kwargs)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
    try:
        return func(**accepted)
    except TypeError:
        # algumas funções usam nomes ligeiramente diferentes; tenta posicional curto
        if positional:
            return func(*positional)
        raise


def _safe_sc_call_v52(module, names, *positional, **kwargs):
    last = None
    for name in names:
        fn = getattr(module, name, None)
        if fn is None:
            continue
        try:
            return _call_sc_func_v52(fn, *positional, **kwargs), name
        except Exception as err:
            last = err
    if last:
        raise RuntimeError(str(last))
    raise RuntimeError("Função não disponível: " + ", ".join(names))


def _sc_materials_v52(material: str, fyk=500.0, backend=None):
    sc, err = _sc_import_backend_v52(backend)
    if sc is None:
        raise RuntimeError(f"structuralcodes indisponível: {err}")
    mod = sc["module"]
    key = sc["key"]
    fck = parse_concrete_strength(material)
    gamma_c = 1.5
    gamma_s = 1.15
    # Betão: usar funções do módulo, com nomes documentados por backend.
    fcd_val, fcd_src = _safe_sc_call_v52(
        mod, ["fcd"], fck=fck, f_ck=fck, alpha_cc=1.0, gamma_c=gamma_c,
        eta_cc=1.0, k_tc=1.0, t_ref=28, t0=28, strength_dev_class="CN"
    )
    fctm_val, fctm_src = _safe_sc_call_v52(mod, ["fctm"], fck=fck, f_ck=fck)
    if key == "mc2010":
        E_val, E_src = _safe_sc_call_v52(mod, ["Eci", "Ecm"], fck=fck, f_ck=fck, fcm=fck + 8.0, f_cm=fck + 8.0)
    else:
        E_val, E_src = _safe_sc_call_v52(mod, ["Ecm", "Eci"], fck=fck, f_ck=fck, fcm=fck + 8.0, f_cm=fck + 8.0)
    fyd_val, fyd_src = _safe_sc_call_v52(mod, ["fyd"], fyk=float(fyk), f_yk=float(fyk), gamma_s=gamma_s)
    try:
        Es_val, Es_src = _safe_sc_call_v52(mod, ["Es"], )
        Es_val = float(Es_val)
    except Exception:
        Es_val, Es_src = 210000.0, "ColumnsEC2 input: Es=210000 MPa, apenas porque o módulo structuralcodes não expôs Es()"
    return {
        "fck": float(fck),
        "fcm": float(fck) + 8.0,
        "fcd": float(fcd_val),
        "fctm": float(fctm_val),
        "Ecm": float(E_val),
        "fyd": float(fyd_val),
        "Es": float(Es_val),
        "backend": sc["backend"],
        "sources": f"fcd:{fcd_src}; fctm:{fctm_src}; E:{E_src}; fyd:{fyd_src}; Es:{Es_src}",
    }

# Override material functions for structuralcodes strict backends.
_old_concrete_props_v52 = concrete_props
_old_steel_props_v52 = steel_props

def concrete_props(fck: float, alpha_cc: float = 1.0, gamma_c: float = 1.5):
    backend = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    if _sc_backend_active_v52(backend):
        mat = globals().get("_SC_STRICT_LAST_MATERIAL_V52", f"C{int(round(float(fck)))}/{int(round(float(fck)+8))}")
        m = _sc_materials_v52(mat, fyk=globals().get("_SC_STRICT_LAST_FYK_V52", 500.0), backend=backend)
        return {k: m[k] for k in ["fck", "fcm", "fcd", "fctm", "Ecm", "backend", "sources"] if k in m}
    return _old_concrete_props_v52(fck, alpha_cc=alpha_cc, gamma_c=gamma_c)

def steel_props(fyk: float = 500.0, gamma_s: float = 1.15):
    backend = globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010)
    if _sc_backend_active_v52(backend):
        mat = globals().get("_SC_STRICT_LAST_MATERIAL_V52", "C30/37")
        m = _sc_materials_v52(mat, fyk=fyk, backend=backend)
        return {"fyd": m["fyd"], "Es": m["Es"], "backend": m["backend"], "sources": m["sources"]}
    return _old_steel_props_v52(fyk, gamma_s=gamma_s)

globals()["concrete_props"] = concrete_props
globals()["steel_props"] = steel_props


def _layout_points_v52(layout):
    try:
        return _layout_bar_points_v45(layout)
    except Exception:
        try:
            pts = []
            edge = layout.cover_mm + layout.phi_st_mm + layout.phi_long_mm / 2.0
            y_left = -layout.b_mm / 2.0 + edge
            y_right = layout.b_mm / 2.0 - edge
            z_bot = -layout.h_mm / 2.0 + edge
            z_top = layout.h_mm / 2.0 - edge
            ys = [y_left + i*(y_right-y_left)/(layout.n_bars_y-1) for i in range(layout.n_bars_y)] if layout.n_bars_y > 1 else [0.0]
            zs = [z_bot + i*(z_top-z_bot)/(layout.n_bars_z-1) for i in range(layout.n_bars_z)] if layout.n_bars_z > 1 else [0.0]
            for y in ys:
                pts.append((float(y), float(z_top), float(layout.phi_long_mm)))
                pts.append((float(y), float(z_bot), float(layout.phi_long_mm)))
            for z in zs[1:-1]:
                pts.append((float(y_left), float(z), float(layout.phi_long_mm)))
                pts.append((float(y_right), float(z), float(layout.phi_long_mm)))
            # remove duplicates
            out=[]; seen=set()
            for p in pts:
                k=(round(p[0],6),round(p[1],6),round(p[2],6))
                if k not in seen:
                    seen.add(k); out.append(p)
            return out
        except Exception:
            return []


def _sc_section_from_layout_v52(layout, material: str, fyk: float, backend=None):
    sc, err = _sc_import_backend_v52(backend)
    if sc is None:
        raise RuntimeError(f"structuralcodes indisponível: {err}")
    try:
        concrete = sc["create_concrete"](fck=float(parse_concrete_strength(material)))
    except Exception as e:
        raise RuntimeError(f"create_concrete falhou: {e}")
    try:
        reinforcement = sc["create_reinforcement"](
            fyk=float(fyk), Es=210000.0, ftk=max(float(fyk)*1.08, float(fyk)+1.0), epsuk=0.05
        )
    except Exception:
        try:
            reinforcement = sc["create_reinforcement"](fyk=float(fyk))
        except Exception as e:
            raise RuntimeError(f"create_reinforcement falhou: {e}")
    b = float(getattr(layout, "b_mm", 0.0)); h = float(getattr(layout, "h_mm", 0.0))
    poly = sc["Polygon"]([(-b/2,-h/2),(b/2,-h/2),(b/2,h/2),(-b/2,h/2)])
    geometry = sc["SurfaceGeometry"](poly=poly, material=concrete)
    for y,z,phi in _layout_points_v52(layout):
        geometry = sc["add_reinforcement"](geometry, (float(y), float(z)), float(phi), reinforcement)
    return sc["BeamSection"](geometry=geometry)


def _extract_nmm_arrays_v52(result):
    # Reutiliza extractor anterior se existir.
    try:
        return _extract_nmm_arrays_v50(result)
    except Exception:
        pass
    return None, None, None


def _sc_nmm_capacities_v52(layout, n_ed_kN: float, material: str, fyk: float, backend=None):
    section = _sc_section_from_layout_v52(layout, material, fyk, backend=backend)
    calc = getattr(section, "section_calculator", None)
    if calc is None:
        raise RuntimeError("BeamSection não expõe section_calculator.")
    method = None
    for name in ["calculate_nmm_interaction_domain", "nmm_interaction_domain", "calculate_nm_interaction_domain"]:
        if hasattr(calc, name):
            method = getattr(calc, name); method_name = name; break
    if method is None:
        raise RuntimeError("SectionCalculator não expõe função de domínio N-My-Mz.")
    attempts = [{}, {"num_theta":48}, {"n_theta":48}, {"num_theta":48,"num_axial":80}, {"n_theta":48,"n_axial":80}]
    last = None; result = None
    for kw in attempts:
        try:
            result = _call_sc_func_v52(method, **kw)
            break
        except Exception as err:
            last = err
    if result is None:
        raise RuntimeError(f"{method_name} falhou: {last}")
    n, my, mz = _extract_nmm_arrays_v52(result)
    if n is None:
        raise RuntimeError("Não foi possível extrair arrays N, My, Mz do resultado do structuralcodes.")
    import numpy as np
    n=np.asarray(n,dtype=float); my=np.asarray(my,dtype=float); mz=np.asarray(mz,dtype=float)
    mask=np.isfinite(n)&np.isfinite(my)&np.isfinite(mz)
    n=n[mask]; my=my[mask]; mz=mz[mask]
    if len(n)<3:
        raise RuntimeError("Domínio N-My-Mz devolveu pontos insuficientes.")
    target=abs(float(n_ed_kN)*1e3)
    absn=np.abs(n)
    order=np.argsort(np.abs(absn-target))[:max(12, min(80, len(absn)))]
    caps=[]
    for i in order:
        myk=abs(float(my[i]))/1e6; mzk=abs(float(mz[i]))/1e6
        if myk>1e-9 and mzk>1e-9:
            caps.append((myk,mzk))
    if not caps:
        raise RuntimeError("Domínio N-My-Mz sem pontos resistentes úteis para o nível de NEd.")
    return caps, f"structuralcodes.sections.{method_name}"


def _sc_service_check_v52(out, row, layout, mats, backend=None):
    sc, err = _sc_import_backend_v52(backend)
    if sc is None:
        out["service_status"] = f"Aviso: structuralcodes indisponível ({err})"
        return out
    mod = sc["module"]
    if not any(hasattr(mod, n) for n in ["wk", "wk_cal", "wk_cal2"]):
        out["service_status"] = "Aviso: fendilhação/ELS não exposto neste backend structuralcodes"
        out["service_backend"] = sc["backend"]
        return out
    # Sem combinar com fórmulas internas: se faltarem parâmetros de fendilhação, reporta o âmbito.
    out["service_backend"] = sc["backend"]
    out["service_status"] = "Aviso: ELS disponível no backend, mas requer parâmetros específicos de fendilhação para cálculo directo"
    out["service_note"] = "Sem fallback interno; indicar parâmetros ELS adicionais para chamada completa da API structuralcodes."
    return out


def _sc_shear_check_v52(out, row, layout, mats, backend=None):
    sc, err = _sc_import_backend_v52(backend)
    if sc is None:
        out["shear_status_y"] = out["shear_status_z"] = f"Aviso: structuralcodes indisponível ({err})"
        return out
    mod = sc["module"]; key=sc["key"]
    fck=mats["fck"]; Es=mats.get("Es",210000.0); As=out.get("as_prov_mm2") or getattr(layout,"as_prov_mm2",0.0)
    b=float(getattr(layout,"b_mm",0.0)); h=float(getattr(layout,"h_mm",0.0))
    z_y=0.8*h; z_z=0.8*b
    fy=abs(safe_float(row.get("fy_i", row.get("fy",0.0)),0.0)); fz=abs(safe_float(row.get("fz_i", row.get("fz",0.0)),0.0))
    fy=max(fy, abs(safe_float(row.get("fy_j", fy),fy)))
    fz=max(fz, abs(safe_float(row.get("fz_j", fz),fz)))
    if key == "ec2_2023":
        out["shear_status_y"] = out["shear_status_z"] = "Aviso: esforço transverso não exposto no módulo structuralcodes EC2:2023"
        return out
    try:
        if key == "ec2_2004":
            # Funções documentadas: VRdc, VRdmax, Asw_s_required.
            vrdc_y,src1 = _safe_sc_call_v52(mod, ["VRdc"], fck=fck, d=z_y, bw=b, rho_l=max(As/(b*z_y),1e-6), sigma_cp=0.0, gamma_c=1.5)
            vrdmax_y,src2 = _safe_sc_call_v52(mod, ["VRdmax"], fck=fck, bw=b, z=z_y, theta=45.0, alpha=90.0, gamma_c=1.5)
            vrdc_z,src3 = _safe_sc_call_v52(mod, ["VRdc"], fck=fck, d=z_z, bw=h, rho_l=max(As/(h*z_z),1e-6), sigma_cp=0.0, gamma_c=1.5)
            vrdmax_z,src4 = _safe_sc_call_v52(mod, ["VRdmax"], fck=fck, bw=h, z=z_z, theta=45.0, alpha=90.0, gamma_c=1.5)
        else:
            loads_y={"ned": abs(safe_float(row.get("fx",0.0),0.0))*1e3, "med": abs(safe_float(row.get("my",0.0),0.0))*1e6, "ved": fy*1e3}
            loads_z={"ned": abs(safe_float(row.get("fx",0.0),0.0))*1e3, "med": abs(safe_float(row.get("mz",0.0),0.0))*1e6, "ved": fz*1e3}
            vrdc_y,src1 = _safe_sc_call_v52(mod, ["v_rdc_approx1", "v_rdc"], approx_lvl=1, fck=fck, z=z_y, bw=b, dg=16.0, E_s=Es, As=As, loads=loads_y, gamma_c=1.5)
            vrdmax_y,src2 = _safe_sc_call_v52(mod, ["v_rd_max_approx1", "v_rd_max_approx2"], fck=fck, f_ck=fck, bw=b, theta=45.0, z=z_y, E_s=Es, As=As, loads=loads_y, gamma_c=1.5)
            vrdc_z,src3 = _safe_sc_call_v52(mod, ["v_rdc_approx1", "v_rdc"], approx_lvl=1, fck=fck, z=z_z, bw=h, dg=16.0, E_s=Es, As=As, loads=loads_z, gamma_c=1.5)
            vrdmax_z,src4 = _safe_sc_call_v52(mod, ["v_rd_max_approx1", "v_rd_max_approx2"], fck=fck, f_ck=fck, bw=h, theta=45.0, z=z_z, E_s=Es, As=As, loads=loads_z, gamma_c=1.5)
        # Interpretar unidades: structuralcodes pode devolver N; converter para kN se valor grande.
        def tokN(v):
            v=float(v)
            return v/1000.0 if abs(v)>1e4 else v
        out["v_rd_c_y_kN"] = tokN(vrdc_y); out["v_rd_c_z_kN"] = tokN(vrdc_z)
        out["v_rd_max_y_kN"] = tokN(vrdmax_y); out["v_rd_max_z_kN"] = tokN(vrdmax_z)
        out["shear_backend"] = sc["backend"]
        out["shear_status_y"] = "OK" if fy <= out["v_rd_max_y_kN"] else "Falha: VEd,y > VRd,max"
        out["shear_status_z"] = "OK" if fz <= out["v_rd_max_z_kN"] else "Falha: VEd,z > VRd,max"
    except Exception as e:
        out["shear_status_y"] = out["shear_status_z"] = f"Aviso: esforço transverso não calculado por structuralcodes ({e})"
    return out


def _sc_torsion_check_v52(out, row, layout, mats, backend=None):
    sc, err = _sc_import_backend_v52(backend)
    if sc is None:
        out["torsion_status"] = f"Aviso: structuralcodes indisponível ({err})"
        return out
    mod=sc["module"]; key=sc["key"]
    if key != "mc2010":
        out["torsion_status"] = "Aviso: torção não exposta neste backend structuralcodes"
        return out
    try:
        b=float(getattr(layout,"b_mm",0.0)); h=float(getattr(layout,"h_mm",0.0)); z=0.8*min(b,h)
        d_k=max(1.0, min(b,h)-2.0*(getattr(layout,"cover_mm",35.0)+getattr(layout,"phi_st_mm",8.0)))
        a_k=max(1.0, (b-2*getattr(layout,"cover_mm",35.0))*(h-2*getattr(layout,"cover_mm",35.0)))
        t_ed=max(abs(safe_float(row.get("mx_i", row.get("mx",0.0)),0.0)), abs(safe_float(row.get("mx_j", row.get("mx",0.0)),0.0))) * 1e6
        loads={"ned": abs(safe_float(row.get("fx",0.0),0.0))*1e3, "med": abs(safe_float(row.get("my",0.0),0.0))*1e6, "ved": abs(safe_float(row.get("fy",0.0),0.0))*1e3}
        trdmax, src = _safe_sc_call_v52(mod, ["t_rd_max"], f_ck=mats["fck"], fck=mats["fck"], d_k=d_k, a_k=a_k, theta=45.0, approx_lvl=1, z=z, E_s=mats.get("Es",210000.0), As=out.get("as_prov_mm2") or getattr(layout,"as_prov_mm2",0.0), loads=loads, gamma_c=1.5)
        out["t_rd_max_kNm"] = float(trdmax)/1e6 if abs(float(trdmax))>1e4 else float(trdmax)
        out["torsion_backend"] = sc["backend"]
        out["torsion_status"] = "OK" if (t_ed/1e6) <= out["t_rd_max_kNm"] else "Falha: TEd > TRd,max"
    except Exception as e:
        out["torsion_status"] = f"Aviso: torção não calculada por structuralcodes ({e})"
    return out


def _strict_sc_design_one_v52(self, row: pd.Series, prebuilt_candidates=None):
    backend = _backend_selected_v52(getattr(self,"code_backend",None))
    material = str(row.get("material", "") or "").strip()
    if not material:
        reason="Material não especificado; backend structuralcodes strict exige classe de betão explícita na tabela."
        return {"member": row.get("member",""), "case": row.get("case",""), "name": row.get("name",""), "status":"Falha", "failure_reason":reason, "failure_type":"dados_incompletos", "code_backend":backend, "normative_basis":backend, "backend_note":reason}
    globals()["ACTIVE_CODE_BACKEND_V48"] = backend
    globals()["_SC_STRICT_LAST_MATERIAL_V52"] = material
    globals()["_SC_STRICT_LAST_FYK_V52"] = float(getattr(self,"fyk",500.0))
    try:
        mats = _sc_materials_v52(material, fyk=float(getattr(self,"fyk",500.0)), backend=backend)
    except Exception as e:
        return {"member": row.get("member",""), "case": row.get("case",""), "name": row.get("name",""), "status":"Falha", "failure_reason":f"structuralcodes não calculou materiais: {e}", "failure_type":"backend_structuralcodes", "code_backend":backend, "normative_basis":backend}

    b_mm = cm_to_mm(row.get("hy",0.0)); h_mm = cm_to_mm(row.get("hz",0.0))
    ac_mm2 = safe_float(row.get("ax", float('nan'))) * 100.0
    if b_mm <= 0 and ac_mm2 > 0: b_mm = math.sqrt(ac_mm2)
    if h_mm <= 0: h_mm = b_mm
    if not math.isfinite(ac_mm2) or ac_mm2 <= 0: ac_mm2 = b_mm*h_mm
    n_ed_kN=max(abs(safe_float(row.get("fx_i", row.get("fx",0.0)),0.0)), abs(safe_float(row.get("fx_j", row.get("fx",0.0)),0.0)))
    my_ed_kNm=max(abs(safe_float(row.get("my_i", row.get("my",0.0)),0.0)), abs(safe_float(row.get("my_j", row.get("my",0.0)),0.0)))
    mz_ed_kNm=max(abs(safe_float(row.get("mz_i", row.get("mz",0.0)),0.0)), abs(safe_float(row.get("mz_j", row.get("mz",0.0)),0.0)))
    fyd=mats["fyd"]; Es=mats["Es"]; fck=mats["fck"]; fcd=mats["fcd"]
    as_min=max(0.10*n_ed_kN*1e3/max(fyd,1e-9), 0.002*ac_mm2)
    as_max=0.04*ac_mm2
    as_req=max(as_min, 0.10*n_ed_kN*1e3/max(fyd,1e-9))
    is_circular=self.infer_is_circular(row,b_mm,h_mm)
    candidates=prebuilt_candidates if prebuilt_candidates is not None else self.build_candidate_layouts(b_mm,h_mm,is_circular=is_circular)
    candidates=[c for c in candidates if c.as_prov_mm2 >= as_req and c.as_prov_mm2 <= as_max]
    candidates=sorted(candidates, key=lambda c: (c.as_prov_mm2, c.n_total, c.phi_long_mm))[:100]
    chosen=None; chosen_util=None; chosen_caps=(None,None); failure_reason=""; shortlist=[]; best_ok=None
    for ly in candidates:
        try:
            caps, cap_src = _sc_nmm_capacities_v52(ly,n_ed_kN,material,float(getattr(self,"fyk",500.0)),backend=backend)
            ok, util, mycap, mzcap = self.biaxial_ok(my_ed_kNm,mz_ed_kNm,caps)
            shortlist.append({"solucao":f"{ly.n_total}Ø{int(ly.phi_long_mm)}", "as_prov_mm2":ly.as_prov_mm2, "utilizacao":"" if util is None else f"{util:.3f}", "status_short":"OK" if ok else "Falha", "failure_short":"" if ok else "N-My-Mz"})
            if ok:
                _eta = 999.0 if util is None else float(util)
                _as = float(getattr(ly, "as_prov_mm2", 0.0))
                _strategy = str(getattr(self, "design_strategy", globals().get("ACTIVE_REBAR_STRATEGY_V64", "equilibrada"))).lower()
                if _strategy.startswith("econ"):
                    _key = (_as, _eta, ly.n_total)
                elif _strategy.startswith("rob"):
                    _key = (_eta, _as, ly.n_total)
                else:
                    _target = float(globals().get("REBAR_TARGET_ETA_V64", 0.80))
                    _inside = 0 if 0.70 <= _eta <= 0.85 else 1
                    _key = (_inside, abs(_eta - _target), _as, ly.n_total)
                item = (_key, ly, util, mycap, mzcap)
                if best_ok is None or item[0] < best_ok[0]:
                    best_ok = item
        except Exception as e:
            shortlist.append({"solucao":f"{ly.n_total}Ø{int(ly.phi_long_mm)}", "as_prov_mm2":ly.as_prov_mm2, "utilizacao":"", "status_short":"Aviso", "failure_short":f"structuralcodes: {e}"})
            failure_reason=str(e)
    if best_ok is not None:
        _key, chosen, chosen_util, _mycap, _mzcap = best_ok
        chosen_caps=(_mycap,_mzcap)
    if chosen is None:
        status="Falha" if candidates else "Falha"
        if not candidates:
            failure_reason="Sem candidato geométrico com As,min/As,max antes da verificação structuralcodes."
        sol=""
        asprov=None; phil=None; phist=None; sst=None; nbary=None; nbarz=None; ntotal=None
    else:
        status="OK"; sol=f"{chosen.n_total}Ø{int(chosen.phi_long_mm)} + estribos Ø{int(chosen.phi_st_mm)}//{self.choose_spacing(self.tie_spacing_max(b_mm,h_mm,chosen.phi_long_mm))/10:.1f} cm"
        asprov=chosen.as_prov_mm2; phil=chosen.phi_long_mm; phist=chosen.phi_st_mm; sst=self.choose_spacing(self.tie_spacing_max(b_mm,h_mm,chosen.phi_long_mm)); nbary=chosen.n_bars_y; nbarz=chosen.n_bars_z; ntotal=chosen.n_total
    out={
        "member": row.get("member",""), "case": row.get("case",""), "name": row.get("name",""), "prumada": row.get("prumada", row.get("name",row.get("member",""))),
        "material":material, "b_cm":b_mm/10.0, "h_cm":h_mm/10.0, "length_m":safe_float(row.get("length",0.0),0.0),
        "n_ed_kN":n_ed_kN, "my_ed_kNm":my_ed_kNm, "mz_ed_kNm":mz_ed_kNm,
        "as_min_mm2":as_min, "as_req_mm2":as_req, "as_max_mm2":as_max, "as_prov_mm2":asprov,
        "phi_long_mm":phil, "n_total":ntotal, "n_bars_y":nbary, "n_bars_z":nbarz, "phi_st_mm":phist, "s_st_mm":sst,
        "mrd_y_kNm":chosen_caps[0], "mrd_z_kNm":chosen_caps[1], "utilizacao":chosen_util, "solucao":sol, "status":status,
        "failure_reason":failure_reason if status!="OK" else "", "failure_type":"backend_structuralcodes" if status!="OK" else "", "shortlist_text":serialize_shortlist(shortlist),
        "code_backend":backend, "normative_basis":f"{backend} — modo strict; sem fallback para fórmulas internas.",
        "materials_backend":mats.get("backend",""), "materials_sources":mats.get("sources",""), "nmm_capacity_source":"structuralcodes.sections.SectionCalculator",
        "second_order_status":"Não avaliado neste backend structuralcodes pelo ColumnsEC2; sem fallback interno.",
        "detailing_status":"Não avaliado normativamente neste backend; a armadura é uma geometria candidata verificada por structuralcodes em N-My-Mz.",
    }
    if chosen is not None:
        _sc_shear_check_v52(out,row,chosen,mats,backend=backend)
        _sc_torsion_check_v52(out,row,chosen,mats,backend=backend)
        _sc_service_check_v52(out,row,chosen,mats,backend=backend)
    else:
        out["shear_status_y"]=out["shear_status_z"]=out["torsion_status"]=out["service_status"]="Não avaliado: sem solução N-My-Mz por structuralcodes"
    # Se V/T/ELS não estiverem expostos, não converter em Falha; manter Aviso se N-My-Mz passou.
    aux_warnings = [str(out.get(k,"")) for k in ["shear_status_y","shear_status_z","torsion_status","service_status","second_order_status","detailing_status"] if "Aviso" in str(out.get(k,"")) or "Não avaliado" in str(out.get(k,""))]
    if status == "OK" and aux_warnings:
        out["status"]="Aviso"
        out["failure_type"]="escopo_backend"
        out["failure_reason"]="; ".join(aux_warnings[:4])
    return out

# Substituir design_one de forma rígida: Portugal usa o motor existente; structuralcodes usa apenas o adaptador strict.
_old_design_one_v52 = ColumnDesigner.design_one

def _design_one_v52(self, row: pd.Series, prebuilt_candidates=None):
    backend=_backend_selected_v52(getattr(self,"code_backend",None))
    if _sc_backend_active_v52(backend):
        return _strict_sc_design_one_v52(self,row,prebuilt_candidates=prebuilt_candidates)
    return _old_design_one_v52(self,row,prebuilt_candidates=prebuilt_candidates)

ColumnDesigner.design_one = _design_one_v52

# Capacity também fica strict se for chamado por alguma rota antiga.
_old_capacity_for_layout_v52 = ColumnDesigner.capacity_for_layout

def _capacity_for_layout_v52(self, layout, n_ed_kN: float, fcd: float, fyd: float, Es: float):
    backend=_backend_selected_v52(getattr(self,"code_backend",None))
    if _sc_backend_active_v52(backend):
        material=globals().get("_SC_STRICT_LAST_MATERIAL_V52","C30/37")
        fyk=globals().get("_SC_STRICT_LAST_FYK_V52",500.0)
        caps, src = _sc_nmm_capacities_v52(layout,n_ed_kN,material,fyk,backend=backend)
        self._last_sc2023_capacity_source=src
        self._last_sc2023_capacity_error=""
        return caps
    return _old_capacity_for_layout_v52(self,layout,n_ed_kN,fcd,fyd,Es)

ColumnDesigner.capacity_for_layout = _capacity_for_layout_v52

# Validação strict para qualquer backend structuralcodes.
_old_validate_inputs_v52 = ColumnsEC2App.validate_inputs

def _validate_inputs_v52(self):
    err=_old_validate_inputs_v52(self)
    if err:
        return err
    backend=_backend_selected_v52(getattr(self,"var_code_backend",tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    if _sc_backend_active_v52(backend):
        sc, sc_err = _sc_import_backend_v52(backend)
        if sc is None:
            return (
                f"O backend {backend} requer structuralcodes e shapely.\n\n"
                "Instale com:\npython -m pip install structuralcodes shapely\n\n"
                "Neste modo não há fallback para fórmulas internas.\n\n"
                f"Erro original: {sc_err}"
            )
    return None

ColumnsEC2App.validate_inputs = _validate_inputs_v52

# Actualizar GUI para listar todos os backends.
_old_build_ui_v52 = ColumnsEC2App._build_ui

def _build_ui_v52(self):
    _old_build_ui_v52(self)
    try:
        if hasattr(self,"var_code_backend") and self.var_code_backend.get() not in BACKEND_CHOICES_V52:
            self.var_code_backend.set(BACKEND_EC2_PT_2010)
        def walk(w):
            yield w
            for c in w.winfo_children():
                yield from walk(c)
        varname = str(getattr(self,"var_code_backend","")).split('.')[-1]
        for w in walk(self):
            try:
                if isinstance(w, ttk.Combobox):
                    tv=str(w.cget("textvariable"))
                    if "var_code_backend" in tv or (hasattr(self,"var_code_backend") and tv == str(self.var_code_backend)):
                        w["values"] = BACKEND_CHOICES_V52
            except Exception:
                pass
    except Exception:
        pass

ColumnsEC2App._build_ui = _build_ui_v52

# Melhorar notas e folhas Excel com mapa de cobertura dos três backends structuralcodes.
def _sc_backend_map_v52() -> pd.DataFrame:
    rows=[]
    rows += [["Todos", BACKEND_EC2_PT_2010, "ColumnsEC2", "Motor interno existente; default."]]
    rows += [["Materiais", BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004", "fcd, fctm, Ecm, fyd; sem fallback."]]
    rows += [["N-My-Mz", BACKEND_SC_EC2_2004, "structuralcodes.sections", "BeamSection/SectionCalculator; sem fallback."]]
    rows += [["Esforço transverso", BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004", "VRdc, VRdmax, Asw_s_required quando API disponível."]]
    rows += [["ELS/fendilhação", BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004", "wk/As_min/crack API quando parâmetros disponíveis."]]
    rows += [["Torção", BACKEND_SC_EC2_2004, "structuralcodes", "Não exposta no índice EC2 2004; sem fallback."]]
    rows += [["Materiais", BACKEND_SC_EC2_2023, "structuralcodes.codes.ec2_2023", "fcd, eta_cc, k_tc, fctm, Ecm, fyd, Es; sem fallback."]]
    rows += [["N-My-Mz", BACKEND_SC_EC2_2023, "structuralcodes.sections", "BeamSection/SectionCalculator; sem fallback."]]
    rows += [["ELS/fendilhação/deformação", BACKEND_SC_EC2_2023, "structuralcodes.codes.ec2_2023", "wk_cal, delta_simpl, creep/shrinkage quando API/parâmetros disponíveis."]]
    rows += [["Esforço transverso", BACKEND_SC_EC2_2023, "structuralcodes", "Não exposto no índice EC2 2023; sem fallback."]]
    rows += [["Torção", BACKEND_SC_EC2_2023, "structuralcodes", "Não exposto no índice EC2 2023; sem fallback."]]
    rows += [["Materiais", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "fcd, fctm, Eci, fyd; sem fallback."]]
    rows += [["N-My-Mz", BACKEND_SC_MC2010, "structuralcodes.sections", "BeamSection/SectionCalculator; sem fallback."]]
    rows += [["Esforço transverso", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "v_rd, v_rdc, v_rd_max; sem fallback."]]
    rows += [["Torção", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "t_rd, t_rd_max; sem fallback."]]
    rows += [["Pormenorização", "structuralcodes backends", "não substituído por fórmulas internas", "A armadura gerada é uma geometria candidata; só a verificação structuralcodes é normativa."]]
    return pd.DataFrame(rows, columns=["Modulo","Backend","Origem","Nota"])

_old_write_excel_v52 = ColumnsEC2App._write_excel

def _write_excel_v52(self, path: str):
    _old_write_excel_v52(self,path)
    try:
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            _sc_backend_map_v52().to_excel(writer, sheet_name="30_Mapa_Backend", index=False)
            rows=[]
            for b in SC_BACKENDS_V52:
                sc,err=_sc_import_backend_v52(b)
                if sc is None:
                    rows.append([b,"structuralcodes", "indisponível", str(err)])
                else:
                    mod=sc["module"]
                    for fn in ["fcd","fctm","Ecm","Eci","fyd","Es","VRdc","VRdmax","Asw_s_required","wk","wk_cal","delta_simpl","v_rd","v_rdc","v_rd_max_approx1","t_rd","t_rd_max"]:
                        rows.append([b, fn, "Sim" if hasattr(mod,fn) else "Não", ""])
                    rows.append([b,"BeamSection", "Sim" if sc.get("BeamSection") is not None else "Não", "structuralcodes.sections"])
            pd.DataFrame(rows, columns=["Backend","Objeto","Disponível","Nota"]).to_excel(writer, sheet_name="31_API_structuralcodes", index=False)
            if self.df_results is not None and not self.df_results.empty:
                cols=[c for c in ["prumada","member","case","code_backend","normative_basis","materials_backend","materials_sources","nmm_capacity_source","shear_backend","torsion_backend","service_backend","second_order_status","detailing_status","status","failure_reason"] if c in self.df_results.columns]
                if cols:
                    self.df_results[cols].to_excel(writer, sheet_name="32_Escopo_Resultados", index=False)
    except Exception as err:
        try: self.status_var.set(f"Excel exportado; aviso no mapa structuralcodes: {err}")
        except Exception: pass

ColumnsEC2App._write_excel = _write_excel_v52

_old_metadata_df_v52 = ColumnsEC2App._metadata_df

def _metadata_df_v52(self) -> pd.DataFrame:
    df=_old_metadata_df_v52(self).copy()
    try:
        backend=_backend_selected_v52(getattr(self,"var_code_backend",tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
        extra=pd.DataFrame([
            ["Versão", APP_VERSION],
            ["Backend seleccionado", backend],
            ["Backends structuralcodes", "; ".join(SC_BACKENDS_V52)],
            ["Regra strict", "Nos backends structuralcodes não são usadas fórmulas internas para substituir verificações não expostas pelo pacote."],
        ], columns=["Campo","Valor"])
        return pd.concat([df,extra], ignore_index=True)
    except Exception:
        return df

ColumnsEC2App._metadata_df = _metadata_df_v52

_old_build_normative_notes_v52 = ColumnsEC2App.build_normative_notes

def _build_normative_notes_v52(self) -> pd.DataFrame:
    try: notes=_old_build_normative_notes_v52(self).copy()
    except Exception: notes=pd.DataFrame(columns=["Tema","Referência","Nota"])
    extra=pd.DataFrame([
        ("Backends", "v5.2", "Default: NP EN 1992-1-1:2010 PT pelo motor interno. Alternativos: EC2 2004, EC2 2023 e fib MC2010 por structuralcodes em modo strict."),
        ("structuralcodes strict", "v5.2", "Sem fallback para fórmulas internas. Quando a API não expõe uma verificação, o relatório assinala 'não avaliado neste backend'."),
        ("N-My-Mz", "structuralcodes.sections", "Nos backends structuralcodes, a resistência seccional é obtida por BeamSection/SectionCalculator quando disponível."),
        ("Esforço transverso", "structuralcodes", "EC2 2004 e fib MC2010 usam funções documentadas do pacote quando disponíveis; EC2 2023 só calcula se a API instalada expuser funções próprias."),
    ], columns=["Tema","Referência","Nota"])
    return pd.concat([notes,extra], ignore_index=True).drop_duplicates()

ColumnsEC2App.build_normative_notes = _build_normative_notes_v52


# ============================================================
# ColumnsEC2 v5.3 — GUI profissional, modo pré/dimensionamento,
# φef automático, notas dinâmicas, reparação apenas quando há
# falhas bloqueantes, progresso de exportação e redução acelerada
# ============================================================
APP_VERSION = "v5.3"


def _v53_get_backend(app=None):
    try:
        return _backend_selected_v52(getattr(app, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    except Exception:
        try:
            return _backend_selected_v52(globals().get("ACTIVE_CODE_BACKEND_V48", BACKEND_EC2_PT_2010))
        except Exception:
            return BACKEND_EC2_PT_2010


def _v53_is_structural_backend(backend):
    try:
        return _sc_backend_active_v52(backend)
    except Exception:
        return str(backend) != BACKEND_EC2_PT_2010


def _v53_mode_to_internal(mode_value) -> str:
    s = str(mode_value or "").strip().lower()
    if "pre" in s or "pré" in s:
        return "pre_dimensionamento"
    return "dimensionamento"


def _v53_mode_to_label(mode_value) -> str:
    return "Pré-dimensionamento" if _v53_mode_to_internal(mode_value) == "pre_dimensionamento" else "Dimensionamento"


def _v53_estimate_h0_from_df(df: pd.DataFrame) -> float:
    try:
        if df is None or df.empty:
            return 200.0
        r = df.iloc[0]
        b = cm_to_mm(r.get("hy", 0.0))
        h = cm_to_mm(r.get("hz", 0.0))
        ac = safe_float(r.get("ax", float("nan"))) * 100.0
        if b <= 0 or h <= 0:
            if math.isfinite(ac) and ac > 0:
                b = h = math.sqrt(ac)
        if b <= 0 or h <= 0:
            return 200.0
        # h0 = 2 Ac / u, para secção rectangular u = 2(b+h)
        return max(50.0, min(1000.0, (b * h) / max(b + h, 1e-9)))
    except Exception:
        return 200.0


def _v53_ec2_creep_phi(fck: float, RH: float = 70.0, t0: float = 28.0, h0_mm: float = 200.0) -> float:
    """Estimativa automática prática de φef baseada na estrutura do Anexo B do EC2.
    É usada no backend interno PT; nos backends structuralcodes tenta-se primeiro a API do pacote.
    """
    try:
        fcm = float(fck) + 8.0
        RH = max(40.0, min(100.0, float(RH)))
        t0 = max(1.0, float(t0))
        h0 = max(50.0, float(h0_mm))
        if fcm <= 35.0:
            phi_RH = 1.0 + (1.0 - RH / 100.0) / (0.1 * h0 ** (1.0 / 3.0))
        else:
            alpha1 = (35.0 / fcm) ** 0.7
            alpha2 = (35.0 / fcm) ** 0.2
            phi_RH = (1.0 + (1.0 - RH / 100.0) / (0.1 * h0 ** (1.0 / 3.0)) * alpha1) * alpha2
        beta_fcm = 16.8 / math.sqrt(fcm)
        beta_t0 = 1.0 / (0.1 + t0 ** 0.20)
        phi0 = phi_RH * beta_fcm * beta_t0
        return max(0.2, min(5.0, float(phi0)))
    except Exception:
        return 2.0


def _v53_try_structuralcodes_phi(backend: str, fck: float, RH: float, t0: float, h0: float):
    """Tenta calcular φ/fluência apenas através de structuralcodes, se a API local expuser função compatível."""
    try:
        if not _v53_is_structural_backend(backend):
            return None, ""
        sc, err = _sc_import_backend_v52(backend)
        if sc is None:
            return None, f"structuralcodes indisponível: {err}"
        mod = sc.get("module")
        # A API pode evoluir; tentar nomes usuais sem assumir fallback normativo.
        candidate_names = [
            "phi", "phi_50y_t0", "phi_RH", "beta_H", "creep_coefficient",
            "calc_phi", "phi_correction_factor"
        ]
        for name in candidate_names:
            fn = getattr(mod, name, None)
            if not callable(fn):
                continue
            try:
                import inspect
                sig = inspect.signature(fn)
                kwargs = {}
                for p in sig.parameters:
                    pl = p.lower()
                    if pl in ["fck", "f_ck"]:
                        kwargs[p] = float(fck)
                    elif pl in ["fcm", "f_cm"]:
                        kwargs[p] = float(fck) + 8.0
                    elif pl in ["rh", "relative_humidity"]:
                        kwargs[p] = float(RH)
                    elif pl in ["t0", "t_0"]:
                        kwargs[p] = float(t0)
                    elif pl in ["h0", "h_0"]:
                        kwargs[p] = float(h0)
                    elif pl in ["t", "t_ref"]:
                        kwargs[p] = 36500.0
                    elif pl in ["cement_class", "strength_dev_class"]:
                        kwargs[p] = "CN"
                val = fn(**kwargs)
                if isinstance(val, (list, tuple)):
                    val = val[0]
                val = float(val)
                if math.isfinite(val) and val > 0:
                    return max(0.2, min(8.0, val)), f"structuralcodes.{sc.get('key','')}.{name}"
            except Exception:
                continue
        return None, "API de fluência não encontrada no backend seleccionado"
    except Exception as e:
        return None, str(e)


def _v53_compute_phi_eff_for_app(app) -> Tuple[float, str]:
    backend = _v53_get_backend(app)
    RH = safe_float(getattr(app, "var_creep_RH", tk.StringVar(value="70")).get(), 70.0)
    t0 = safe_float(getattr(app, "var_creep_t0", tk.StringVar(value="28")).get(), 28.0)
    h0 = safe_float(getattr(app, "var_creep_h0", tk.StringVar(value="0")).get(), 0.0)
    if h0 <= 0:
        h0 = _v53_estimate_h0_from_df(getattr(app, "df_pair", pd.DataFrame()))
    fck = 30.0
    try:
        df = getattr(app, "df_pair", pd.DataFrame())
        if df is not None and not df.empty and "material" in df.columns:
            valid = df["material"].astype(str).str.extract(r"C\s*(\d+(?:[\.,]\d+)?)\s*/", expand=False).dropna()
            if not valid.empty:
                fck = float(str(valid.iloc[0]).replace(",", "."))
    except Exception:
        pass
    if _v53_is_structural_backend(backend):
        val, src = _v53_try_structuralcodes_phi(backend, fck, RH, t0, h0)
        if val is not None:
            return val, src
        # Em backend strict, φef só é usado para visualização, porque 2.ª ordem interna não é aplicada.
        return 0.0, f"Não aplicado: {src}; backend structuralcodes strict sem 2.ª ordem interna"
    val = _v53_ec2_creep_phi(fck, RH=RH, t0=t0, h0_mm=h0)
    return val, f"EC2 interno: RH={RH:.0f}%, t0={t0:.0f} d, h0={h0:.0f} mm, fck={fck:.0f} MPa"


def _v53_reduced_envelope(df: pd.DataFrame, mode: str = "dimensionamento") -> pd.DataFrame:
    """Envolvente mais agressiva para acelerar: mantém casos axial, biaxiais e esforços complementares por membro/prumada."""
    if df is None or df.empty:
        return df
    try:
        work = df.copy()
        for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
            if c not in work.columns:
                work[c] = 0.0
            work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
        case_series = work.get("case", pd.Series(index=work.index, dtype=str)).astype(str)
        non_service = ~case_series.map(_case_is_service_v45) if "_case_is_service_v45" in globals() else pd.Series(True, index=work.index)
        work_elu = work[non_service].copy()
        if work_elu.empty:
            work_elu = work
        selected = set()
        group_cols = [c for c in ["name", "member"] if c in work_elu.columns]
        groups = work_elu.groupby(group_cols, dropna=False) if group_cols else [(None, work_elu)]
        pre = _v53_mode_to_internal(mode) == "pre_dimensionamento"
        for _, grp in groups:
            if grp.empty:
                continue
            fx = grp["fx"].abs().replace(0, 1e-9)
            score = 0.25 * grp["fx"].abs() + grp["my"].abs() + grp["mz"].abs() + 0.20 * grp["mx"].abs() + 0.08 * (grp["fy"].abs() + grp["fz"].abs())
            selected.add(score.idxmax())
            selected.add(grp["fx"].abs().idxmax())
            selected.add(((grp["my"].abs() + grp["mz"].abs()) / fx).idxmax())
            if not pre:
                selected.add(grp["my"].abs().idxmax())
                selected.add(grp["mz"].abs().idxmax())
                selected.add(grp["mx"].abs().idxmax())
                selected.add((grp["fy"].abs() + grp["fz"].abs()).idxmax())
        out = work.loc[sorted(selected)].copy()
        order = [c for c in ["name", "member", "case"] if c in out.columns]
        if order:
            out = out.sort_values(order)
        return out.reset_index(drop=True)
    except Exception:
        try:
            return reduce_to_governing_cases(df)
        except Exception:
            return df


def _v53_blocking_failures(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    tmp = enrich_failures_v43(df.copy()) if "enrich_failures_v43" in globals() else df.copy()
    sev = tmp.get("failure_severity", pd.Series("", index=tmp.index)).astype(str)
    status = tmp.get("status", pd.Series("", index=tmp.index)).astype(str)
    return tmp[(sev == "Bloqueante") | (status == "Falha")].copy()


def _v53_failure_summary_text(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df is None or df.empty:
        return ""
    cols = [c for c in ["prumada", "name", "member", "case", "failure_type", "failure_summary", "failure_reason"] if c in df.columns]
    lines = []
    for _, r in df.head(max_rows).iterrows():
        pr = str(r.get("prumada", r.get("name", r.get("member", ""))))
        case = str(r.get("case", ""))
        typ = str(r.get("failure_type", ""))
        reason = str(r.get("failure_summary", r.get("failure_reason", "")))
        if len(reason) > 150:
            reason = reason[:147] + "..."
        lines.append(f"• {pr} | caso {case} | {typ}: {reason}")
    if len(df) > max_rows:
        lines.append(f"... + {len(df)-max_rows} ocorrências. Ver detalhe no XLSX.")
    return "\n".join(lines)


def _v53_update_quick_notes(app):
    try:
        backend = _v53_get_backend(app)
        mode = _v53_mode_to_label(getattr(app, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get())
        if backend == BACKEND_EC2_PT_2010:
            txt = (
                f"Backend: {backend}\n"
                f"Modo: {mode}.\n"
                "Cálculo completo pelo motor interno: ELU, 2.ª ordem, N-My-Mz, V, T, ELS e pormenorização.\n"
                "PDF sintético; XLSX completo."
            )
        elif backend == BACKEND_SC_MC2010:
            txt = (
                "Backend: fib Model Code 2010 | structuralcodes.\n"
                "Modo strict: sem fórmulas internas. Só são calculadas verificações expostas pela API local.\n"
                "V/T podem ser avaliados se a API mc2010 instalada expuser as funções necessárias."
            )
        elif backend == BACKEND_SC_EC2_2004:
            txt = (
                "Backend: Eurocode 2:2004 | structuralcodes.\n"
                "Modo strict: materiais, secções, N-My-Mz e funções disponíveis no pacote.\n"
                "Sem fallback para o motor PT."
            )
        else:
            txt = (
                "Backend: Eurocode 2:2023 | structuralcodes.\n"
                "Modo strict: materiais, secções, ELS/fendilhação/deformação quando a API disponibilizar.\n"
                "V/T/2.ª ordem ficam não avaliados se não estiverem expostos no pacote."
            )
        if hasattr(app, "quick_notes_var"):
            app.quick_notes_var.set(txt)
        if hasattr(app, "df_notes"):
            app.df_notes = app.build_normative_notes()
            if hasattr(app, "tree_notes"):
                app.show_df(app.tree_notes, app.df_notes)
    except Exception:
        pass


_old_build_sidebar_v53_base = ColumnsEC2App._build_sidebar

def _build_sidebar_v53(self, parent):
    # variáveis novas antes de construir a UI
    if not hasattr(self, "var_phi_eff_auto"):
        self.var_phi_eff_auto = tk.BooleanVar(value=True)
    if not hasattr(self, "var_creep_RH"):
        self.var_creep_RH = tk.StringVar(value="70")
    if not hasattr(self, "var_creep_t0"):
        self.var_creep_t0 = tk.StringVar(value="28")
    if not hasattr(self, "var_creep_h0"):
        self.var_creep_h0 = tk.StringVar(value="0")
    _old_build_sidebar_v53_base(self, parent)

    # Modo com linguagem comercial.
    try:
        if _v53_mode_to_internal(self.var_calc_mode.get()) == "pre_dimensionamento":
            self.var_calc_mode.set("Pré-dimensionamento")
        else:
            self.var_calc_mode.set("Dimensionamento")
    except Exception:
        pass

    # Remover painel permanente de correcção; agora só aparece quando há falhas bloqueantes.
    def walk(w):
        for c in w.winfo_children():
            yield c
            yield from walk(c)
    for w in list(walk(parent)):
        try:
            txt = str(w.cget("text")) if isinstance(w, ttk.LabelFrame) else ""
            if "Correc" in txt or "correc" in txt or "Notas rápidas" in txt or "Notas rapidas" in txt:
                w.destroy()
        except Exception:
            pass

    # Actualizar combobox de modo.
    for w in walk(parent):
        try:
            if isinstance(w, ttk.Combobox) and str(w.cget("textvariable")) == str(self.var_calc_mode):
                w.configure(values=["Pré-dimensionamento", "Dimensionamento"], width=20)
        except Exception:
            pass

    # Painel compacto de fluência.
    creep = ttk.LabelFrame(parent, text="Fluência / φef")
    creep.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(creep, text="Calcular φef automaticamente", variable=self.var_phi_eff_auto).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=3)
    ttk.Label(creep, text="RH [%]").grid(row=1, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(creep, textvariable=self.var_creep_RH, width=8).grid(row=1, column=1, sticky="ew", padx=6, pady=2)
    ttk.Label(creep, text="t0 [dias]").grid(row=2, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(creep, textvariable=self.var_creep_t0, width=8).grid(row=2, column=1, sticky="ew", padx=6, pady=2)
    ttk.Label(creep, text="h0 [mm]").grid(row=3, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(creep, textvariable=self.var_creep_h0, width=8).grid(row=3, column=1, sticky="ew", padx=6, pady=2)
    ttk.Label(creep, text="h0=0 ⇒ estimado pela secção.", style="Subtle.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=(0,4))
    creep.columnconfigure(1, weight=1)

    # Notas rápidas dinâmicas no fim da barra lateral.
    self.quick_notes_var = tk.StringVar(value="")
    quick = ttk.LabelFrame(parent, text="Notas rápidas")
    quick.pack(fill="x", pady=(0, 8))
    ttk.Label(quick, textvariable=self.quick_notes_var, style="Subtle.TLabel", wraplength=300, justify="left").pack(fill="x", padx=6, pady=6)
    try:
        self.var_code_backend.trace_add("write", lambda *_: _v53_update_quick_notes(self))
        self.var_calc_mode.trace_add("write", lambda *_: _v53_update_quick_notes(self))
    except Exception:
        pass
    _v53_update_quick_notes(self)

ColumnsEC2App._build_sidebar = _build_sidebar_v53


_old_build_ui_v53_base = ColumnsEC2App._build_ui

def _build_ui_v53(self):
    _old_build_ui_v53_base(self)
    try:
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1360x820")
        self.minsize(1120, 680)
    except Exception:
        pass
    try:
        # Sidebar mais compacta.
        for w in self.winfo_children():
            pass
        self.after(200, lambda: _v53_update_quick_notes(self))
    except Exception:
        pass

ColumnsEC2App._build_ui = _build_ui_v53


_old_validate_inputs_v53 = ColumnsEC2App.validate_inputs

def _validate_inputs_v53(self):
    err = _old_validate_inputs_v53(self)
    if err:
        return err
    try:
        if getattr(self, "var_phi_eff_auto", tk.BooleanVar(value=False)).get():
            phi, src = _v53_compute_phi_eff_for_app(self)
            if phi and phi > 0:
                self.var_phi_eff.set(f"{phi:.3f}")
            self._phi_eff_source_v53 = src
    except Exception as e:
        self._phi_eff_source_v53 = f"φef automático não calculado: {e}"
    return None

ColumnsEC2App.validate_inputs = _validate_inputs_v53


# Aceleração: substituir redução global por envolvente v5.3.
def reduce_to_governing_cases(df: pd.DataFrame) -> pd.DataFrame:
    return _v53_reduced_envelope(df, mode="dimensionamento")

globals()["reduce_to_governing_cases"] = reduce_to_governing_cases


# Reparação iterativa com progresso correcto e apenas após confirmação.
def _repair_failures_interactive_v53(self):
    if self.df_results is None or self.df_results.empty:
        messagebox.showwarning("Aviso", "Execute primeiro o cálculo.")
        return
    backend = _v53_get_backend(self)
    if _v53_is_structural_backend(backend):
        messagebox.showinfo(
            "Correcção iterativa",
            "A correcção automática de soluções não é executada nos backends structuralcodes em modo strict.\n\n"
            "Nesse modo, o programa não pode usar fórmulas internas para substituir o pacote."
        )
        return
    targets = _v53_blocking_failures(self.df_results)
    if targets.empty:
        messagebox.showinfo("Correcção iterativa", "Não foram detectadas falhas bloqueantes.")
        return
    if not messagebox.askyesno(
        "Falhas bloqueantes detectadas",
        "Foram detectadas falhas bloqueantes.\n\n"
        + _v53_failure_summary_text(targets, max_rows=10)
        + "\n\nPretende tentar a correcção iterativa automática?"
    ):
        return
    total = len(targets)
    self.progress_var.set(0.0)
    self.status_var.set(f"Correcção iterativa em curso... 0/{total}")
    self.update_idletasks()
    res = enrich_failures_v43(self.df_results.copy())
    target_index = set(targets.index)
    corrected = []
    corrected_count = warning_count = unresolved_count = 0
    processed = 0
    for idx, row in res.iterrows():
        if idx not in target_index:
            d = dict(row)
            d.setdefault("auto_repair_applied", "")
            corrected.append(d)
            continue
        processed += 1
        self.progress_var.set(100.0 * processed / max(total, 1))
        self.status_var.set(f"Correcção iterativa... {processed}/{total} | pilar {row.get('prumada', row.get('member',''))}")
        self.update_idletasks()
        try:
            repaired = _try_repair_result_v44(self, row)
        except Exception as e:
            repaired = dict(row)
            repaired["repair_result"] = "Sem solução automática"
            repaired["repair_note"] = str(e)
        repaired["_original_index"] = idx
        if str(repaired.get("auto_repair_applied", "")) == "Sim" and str(repaired.get("status", "")) == "OK":
            corrected_count += 1
        elif str(repaired.get("status", "")) == "Aviso":
            warning_count += 1
        else:
            unresolved_count += 1
        corrected.append(repaired)
    self.df_results = enrich_failures_v43(pd.DataFrame(corrected))
    try:
        _refresh_after_repair_v44(self)
    except Exception:
        pass
    self.progress_var.set(100.0)
    self.status_var.set(f"Correcção concluída: {corrected_count} corrigidas; {warning_count} avisos; {unresolved_count} sem solução automática.")
    messagebox.showinfo("Correcção concluída", f"Corrigidas: {corrected_count}\nAvisos/propostas: {warning_count}\nSem solução automática: {unresolved_count}")

ColumnsEC2App.repair_failures_interactive = _repair_failures_interactive_v53


# Run design final: normaliza modo, calcula φef auto, reduz casos e pergunta por correcção se necessário.
def _run_design_v53(self):
    err = self.validate_inputs()
    if err:
        messagebox.showwarning("Aviso", err)
        return
    backend = _v53_get_backend(self)
    globals()["ACTIVE_CODE_BACKEND_V48"] = backend
    mode_internal = _v53_mode_to_internal(self.var_calc_mode.get())
    try:
        # manter a GUI com linguagem clara.
        self.var_calc_mode.set(_v53_mode_to_label(mode_internal))
    except Exception:
        pass
    try:
        if backend == BACKEND_SC_EC2_2023:
            EC2_2023_DEFAULTS_V48["t_ref"] = float(getattr(self, "var_ec23_tref", tk.StringVar(value="28")).get().replace(",", "."))
            EC2_2023_DEFAULTS_V48["t0"] = float(getattr(self, "var_ec23_t0", tk.StringVar(value="28")).get().replace(",", "."))
            EC2_2023_DEFAULTS_V48["strength_dev_class"] = getattr(self, "var_ec23_strength_class", tk.StringVar(value="CN")).get().strip() or "CN"
    except Exception:
        pass
    designer = ColumnDesigner(
        cover_mm=safe_float(self.var_cover.get(), 35.0),
        fyk=safe_float(self.var_fyk.get(), 500.0),
        phi_eff=safe_float(self.var_phi_eff.get(), 2.0),
        l0y_factor=safe_float(self.var_l0y.get(), 1.0),
        l0z_factor=safe_float(self.var_l0z.get(), 1.0),
        calc_mode=mode_internal,
        code_backend=backend,
    )
    designer.service_case_override = self.var_service_case.get().strip() if hasattr(self, "var_service_case") else ""
    if getattr(self, "var_reduce_cases", tk.BooleanVar(value=True)).get():
        input_df = _v53_reduced_envelope(self.df_pair, mode=mode_internal)
    else:
        input_df = self.df_pair.copy()
    self.df_calc_input = input_df.copy()
    self.progress_var.set(0.0)
    self.status_var.set(f"A calcular ({_v53_mode_to_label(mode_internal)}) — {backend}...")

    def progress(done, total):
        pct = 0.0 if total <= 0 else 100.0 * done / total
        self.after(0, lambda p=pct: self.progress_var.set(p))
        self.after(0, lambda d=done, t=total: self.status_var.set(f"A calcular... {d}/{t} casos de envolvente"))

    def worker():
        try:
            results = designer.design_dataframe(input_df, progress_callback=progress)
            try:
                results = apply_service_combination_override_v4(self, results, input_df)
            except Exception:
                pass
            try:
                results = enrich_failures_v43(results)
            except Exception:
                pass
            summary = self.build_summary_by_member(results) if getattr(self, "var_summary", tk.BooleanVar(value=True)).get() else pd.DataFrame()
            failures = results[results.get("status", pd.Series(index=results.index, dtype=str)).astype(str).eq("Falha")].copy() if not results.empty else pd.DataFrame()
            ok = results[results.get("status", pd.Series(index=results.index, dtype=str)).astype(str).eq("OK")].copy() if not results.empty else pd.DataFrame()
            validation = self.build_data_validation(pre_calc=False)

            def finish():
                self.df_results = results
                self.df_summary = summary
                self.df_failures = failures
                self.df_ok = ok
                self.df_filtered = pd.DataFrame()
                self.df_validation = validation
                self.df_notes = self.build_normative_notes()
                for tree, df in [
                    (self.tree_results, self.df_results),
                    (self.tree_summary, self.df_summary),
                    (self.tree_failures, self.df_failures),
                    (self.tree_shortlists, self.build_shortlists_df()),
                    (self.tree_validation, self.df_validation),
                    (self.tree_notes, self.df_notes),
                ]:
                    try:
                        self.show_df(tree, df)
                    except Exception:
                        pass
                try:
                    self.update_report()
                except Exception:
                    pass
                self.progress_var.set(100.0)
                blockers = _v53_blocking_failures(self.df_results)
                prumadas = self.df_results.get("prumada", self.df_results.get("name", self.df_results.get("member", pd.Series(dtype=str)))).astype(str).nunique() if not self.df_results.empty else 0
                self.status_var.set(f"Cálculo concluído: {len(results)} casos de envolvente; {prumadas} prumadas; {len(blockers)} falhas bloqueantes.")
                _v53_update_quick_notes(self)
                # Popup só se existirem bloqueantes.
                if not blockers.empty:
                    if _v53_is_structural_backend(backend):
                        messagebox.showwarning(
                            "Falhas/limitações detectadas",
                            "Foram detectadas falhas ou verificações não avaliadas no backend seleccionado.\n\n"
                            + _v53_failure_summary_text(blockers, max_rows=10)
                            + "\n\nNos backends structuralcodes strict não é aplicada correcção automática com fórmulas internas."
                        )
                    else:
                        if messagebox.askyesno(
                            "Falhas bloqueantes detectadas",
                            "Foram detectadas falhas bloqueantes.\n\n"
                            + _v53_failure_summary_text(blockers, max_rows=10)
                            + "\n\nPretende tentar a correcção iterativa automática?"
                        ):
                            self.repair_failures_interactive()
            self.after(0, finish)
        except Exception as err:
            msg = str(err)
            self.after(0, lambda m=msg: messagebox.showerror("Erro", m))
            self.after(0, lambda: self.status_var.set("Falha na análise."))
            self.after(0, lambda: self.progress_var.set(0.0))

    self.analysis_thread = threading.Thread(target=worker, daemon=True)
    self.analysis_thread.start()

ColumnsEC2App.run_design = _run_design_v53


# Notas normativas dinâmicas por backend.
def _build_normative_notes_v53(self) -> pd.DataFrame:
    backend = _v53_get_backend(self)
    rows = []
    if backend == BACKEND_EC2_PT_2010:
        rows += [
            ("Backend", "NP EN 1992-1-1:2010 PT", "Motor interno completo mantido como default."),
            ("Base normativa", "NP EN 1992-1-1:2010 + AC:2012 + A1:2019", "Aplicação com Anexo Nacional português."),
            ("Modo de cálculo", _v53_mode_to_label(getattr(self, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get()), "Pré-dimensionamento acelera; Dimensionamento executa verificação resistente e pormenorização."),
            ("Fluência", "φef", getattr(self, "_phi_eff_source_v53", "Automático se activado; manual caso contrário.")),
            ("Relatórios", "PDF/XLSX/DXF", "PDF sintético; XLSX mantém memória completa; DXF mantém quadro de pilares."),
        ]
    elif backend == BACKEND_SC_EC2_2004:
        rows += [
            ("Backend", backend, "Modo strict com structuralcodes; sem fallback para fórmulas internas."),
            ("Cálculo", "structuralcodes", "Materiais, secção e verificações disponíveis na API local."),
            ("Fora do âmbito", "Sem fallback", "Módulos não expostos pelo pacote ficam assinalados como não avaliados."),
        ]
    elif backend == BACKEND_SC_EC2_2023:
        rows += [
            ("Backend", backend, "Modo strict com structuralcodes; sem fallback para fórmulas internas."),
            ("Parâmetros", "EC2:2023", f"t_ref={getattr(self,'var_ec23_tref',tk.StringVar(value='28')).get()} d; t0={getattr(self,'var_ec23_t0',tk.StringVar(value='28')).get()} d; classe={getattr(self,'var_ec23_strength_class',tk.StringVar(value='CN')).get()}."),
            ("Fora do âmbito", "API local", "V/T/2.ª ordem só são avaliados se existirem funções próprias no pacote instalado."),
        ]
    else:
        rows += [
            ("Backend", backend, "Modo strict com structuralcodes; sem fallback para fórmulas internas."),
            ("Cálculo", "fib Model Code 2010", "Materiais, secção, V/T e ELS são tentados apenas através do pacote."),
            ("Fora do âmbito", "API local", "Quando a API não expõe a função necessária, a verificação fica não avaliada."),
        ]
    rows += [("Desempenho", "Envolvente v5.3", "O cálculo usa casos de envolvente por membro/prumada para reduzir tempo sem perder os casos críticos principais.")]
    return pd.DataFrame(rows, columns=["Tema", "Referência", "Nota"])

ColumnsEC2App.build_normative_notes = _build_normative_notes_v53


# Metadados: acrescentar modo e φef.
_old_metadata_df_v53 = ColumnsEC2App._metadata_df

def _metadata_df_v53(self) -> pd.DataFrame:
    try:
        df = _old_metadata_df_v53(self).copy()
    except Exception:
        df = pd.DataFrame(columns=["Campo", "Valor"])
    extra = pd.DataFrame([
        ["Versão", APP_VERSION],
        ["Modo de cálculo", _v53_mode_to_label(getattr(self, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get())],
        ["φef", getattr(self, "var_phi_eff", tk.StringVar(value="")).get()],
        ["Origem φef", getattr(self, "_phi_eff_source_v53", "manual/não avaliado")],
        ["Backend", _v53_get_backend(self)],
    ], columns=["Campo", "Valor"])
    return pd.concat([df, extra], ignore_index=True)

ColumnsEC2App._metadata_df = _metadata_df_v53


# Exportações com barra de estado/progresso.
_old_export_excel_v53 = ColumnsEC2App.export_excel

def _export_excel_v53(self):
    try:
        self.progress_var.set(5.0)
        self.status_var.set("A preparar exportação XLSX...")
        self.update_idletasks()
        _old_export_excel_v53(self)
        self.progress_var.set(100.0)
        self.status_var.set("Exportação XLSX concluída.")
    except Exception as err:
        self.progress_var.set(0.0)
        messagebox.showerror("Erro", f"Não foi possível exportar XLSX.\n\n{err}")

ColumnsEC2App.export_excel = _export_excel_v53

_old_export_pdf_v53 = ColumnsEC2App.export_pdf_report

def _export_pdf_report_v53(self):
    try:
        self.progress_var.set(5.0)
        self.status_var.set("A preparar relatório PDF...")
        self.update_idletasks()
        _old_export_pdf_v53(self)
        self.progress_var.set(100.0)
        self.status_var.set("Exportação PDF concluída.")
    except Exception as err:
        self.progress_var.set(0.0)
        messagebox.showerror("Erro", f"Não foi possível exportar PDF.\n\n{err}")

ColumnsEC2App.export_pdf_report = _export_pdf_report_v53


# Folha XLSX adicional com as opções v5.3.
_old_write_excel_v53 = ColumnsEC2App._write_excel

def _write_excel_v53(self, path: str):
    _old_write_excel_v53(self, path)
    try:
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            pd.DataFrame([
                ["Versão", APP_VERSION],
                ["Backend", _v53_get_backend(self)],
                ["Modo", _v53_mode_to_label(getattr(self, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get())],
                ["φef automático", "Sim" if getattr(self, "var_phi_eff_auto", tk.BooleanVar(value=False)).get() else "Não"],
                ["φef adoptado", getattr(self, "var_phi_eff", tk.StringVar(value="")).get()],
                ["Origem φef", getattr(self, "_phi_eff_source_v53", "")],
                ["Redução por envolvente", "Sim" if getattr(self, "var_reduce_cases", tk.BooleanVar(value=True)).get() else "Não"],
            ], columns=["Campo", "Valor"]).to_excel(writer, sheet_name="33_Opcoes_v5_3", index=False)
    except Exception as err:
        try:
            self.status_var.set(f"XLSX exportado; aviso folha v5.3: {err}")
        except Exception:
            pass

ColumnsEC2App._write_excel = _write_excel_v53




# ============================================================
# ColumnsEC2 v5.4 — diagnóstico structuralcodes, cobertura por
# backend, cálculo automático de h0/φef, filtros pós-cálculo,
# PDF por nível de detalhe, DXF com secções-tipo e optimização
# por prumada/cache.
# ============================================================
APP_VERSION = "v5.4"
APP_XLSX_DESCRIPTION = (
    "Workbook ColumnsEC2 v5.4: backends separados, diagnóstico structuralcodes, mapa de cobertura, "
    "cálculo por prumada/envolvente, cache, relatórios por nível de detalhe, DXF por secções-tipo, "
    "h0 e φef automáticos."
)


def _v54_backend(app=None):
    try:
        return _backend_selected_v52(getattr(app, "var_code_backend", tk.StringVar(value=BACKEND_EC2_PT_2010)).get())
    except Exception:
        return BACKEND_EC2_PT_2010


def _v54_is_sc_backend(backend: str) -> bool:
    try:
        return _sc_backend_active_v52(backend)
    except Exception:
        return str(backend) != BACKEND_EC2_PT_2010


def _v54_walk_widgets(widget):
    try:
        for child in widget.winfo_children():
            yield child
            yield from _v54_walk_widgets(child)
    except Exception:
        return


def _v54_safe_widget_text(widget) -> str:
    try:
        return str(widget.cget("text"))
    except Exception:
        return ""


def _v54_structuralcodes_diagnostics() -> pd.DataFrame:
    """Diagnóstico local do pacote structuralcodes e das APIs relevantes.
    Não falha se o pacote não estiver instalado.
    """
    rows = []
    try:
        import importlib
        import importlib.metadata as importlib_metadata
    except Exception as err:
        return pd.DataFrame([["Python", "importlib", "Erro", str(err)]], columns=["Grupo", "Objeto", "Estado", "Detalhe"])

    def add(group, obj, state, detail=""):
        rows.append([group, obj, state, detail])

    try:
        sc = importlib.import_module("structuralcodes")
        try:
            ver = importlib_metadata.version("structuralcodes")
        except Exception:
            ver = getattr(sc, "__version__", "desconhecida")
        add("Pacote", "structuralcodes", "Disponível", str(ver))
    except Exception as err:
        add("Pacote", "structuralcodes", "Indisponível", str(err))
        try:
            import shapely  # noqa: F401
            try:
                sh_ver = importlib_metadata.version("shapely")
            except Exception:
                sh_ver = "desconhecida"
            add("Dependência", "shapely", "Disponível", sh_ver)
        except Exception as e:
            add("Dependência", "shapely", "Indisponível", str(e))
        return pd.DataFrame(rows, columns=["Grupo", "Objeto", "Estado", "Detalhe"])

    try:
        import shapely  # noqa: F401
        try:
            sh_ver = importlib_metadata.version("shapely")
        except Exception:
            sh_ver = "desconhecida"
        add("Dependência", "shapely", "Disponível", sh_ver)
    except Exception as err:
        add("Dependência", "shapely", "Indisponível", str(err))

    modules = [
        (BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004"),
        (BACKEND_SC_EC2_2023, "structuralcodes.codes.ec2_2023"),
        (BACKEND_SC_MC2010, "structuralcodes.codes.mc2010"),
        ("Sections", "structuralcodes.sections"),
        ("Materials", "structuralcodes.materials"),
        ("Geometry", "structuralcodes.geometry"),
    ]
    function_candidates = [
        "fcd", "fctm", "Ecm", "Eci", "fyd", "Es", "eps_cu", "eps_ud",
        "VRdc", "VRdmax", "Asw_s_required", "v_rd", "v_rdc", "v_rd_max", "v_rd_max_approx1",
        "t_rd", "t_rd_max", "wk", "wk_cal", "delta_simpl", "phi", "creep_coefficient",
        "shrinkage", "eps_cs", "beta_H", "BeamSection", "SectionCalculator", "GenericSection",
    ]
    for label, modname in modules:
        try:
            mod = importlib.import_module(modname)
            add("Módulo", label, "Disponível", modname)
            available = set(dir(mod))
            for fn in function_candidates:
                if fn in available:
                    add("API", f"{label}.{fn}", "Disponível", modname)
        except Exception as err:
            add("Módulo", label, "Indisponível", f"{modname}: {err}")

    return pd.DataFrame(rows, columns=["Grupo", "Objeto", "Estado", "Detalhe"])


def _v54_backend_coverage_df() -> pd.DataFrame:
    rows = [
        ["Materiais", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Motor interno existente; default."],
        ["2.ª ordem", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Método interno actual."],
        ["N-My-Mz", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Superfície interna discreta."],
        ["Esforço transverso", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Verificação interna actual."],
        ["Torção", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Verificação interna actual."],
        ["ELS", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Combinação indicada ou simplificada."],
        ["Pormenorização", BACKEND_EC2_PT_2010, "ColumnsEC2", "Calculado", "Regras internas de pormenorização."],
        ["Materiais", BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004", "Calculado se API disponível", "Sem fallback interno."],
        ["N-My-Mz", BACKEND_SC_EC2_2004, "structuralcodes.sections", "Calculado se API disponível", "Sem fallback interno."],
        ["Esforço transverso", BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004", "Calculado se API disponível", "Sem fallback interno."],
        ["Torção", BACKEND_SC_EC2_2004, "structuralcodes", "Não avaliado se API ausente", "Sem fallback interno."],
        ["ELS/fendilhação", BACKEND_SC_EC2_2004, "structuralcodes.codes.ec2_2004", "Calculado se API disponível", "Sem fallback interno."],
        ["Pormenorização", BACKEND_SC_EC2_2004, "ColumnsEC2 geométrico", "Informativo", "A geometria candidata é gerada pelo programa; a aceitação normativa depende das APIs disponíveis."],
        ["Materiais", BACKEND_SC_EC2_2023, "structuralcodes.codes.ec2_2023", "Calculado se API disponível", "Sem fallback interno."],
        ["N-My-Mz", BACKEND_SC_EC2_2023, "structuralcodes.sections", "Calculado se API disponível", "Sem fallback interno."],
        ["ELS/fendilhação/deformação", BACKEND_SC_EC2_2023, "structuralcodes.codes.ec2_2023", "Calculado se API disponível", "Sem fallback interno."],
        ["2.ª ordem", BACKEND_SC_EC2_2023, "structuralcodes", "Não avaliado se API ausente", "Sem fallback interno."],
        ["Esforço transverso", BACKEND_SC_EC2_2023, "structuralcodes", "Não avaliado se API ausente", "Sem fallback interno."],
        ["Torção", BACKEND_SC_EC2_2023, "structuralcodes", "Não avaliado se API ausente", "Sem fallback interno."],
        ["Materiais", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "Calculado se API disponível", "Sem fallback interno."],
        ["N-My-Mz", BACKEND_SC_MC2010, "structuralcodes.sections", "Calculado se API disponível", "Sem fallback interno."],
        ["Esforço transverso", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "Calculado se API disponível", "Sem fallback interno."],
        ["Torção", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "Calculado se API disponível", "Sem fallback interno."],
        ["ELS", BACKEND_SC_MC2010, "structuralcodes.codes.mc2010", "Calculado se API disponível", "Sem fallback interno."],
    ]
    return pd.DataFrame(rows, columns=["Verificação", "Backend", "Origem", "Estado", "Nota"])


def _v54_estimate_h0_from_row(row) -> float:
    try:
        b = cm_to_mm(row.get("hy", 0.0))
        h = cm_to_mm(row.get("hz", 0.0))
        ac = safe_float(row.get("ax", float("nan"))) * 100.0
        if (b <= 0 or h <= 0) and math.isfinite(ac) and ac > 0:
            b = h = math.sqrt(ac)
        if b <= 0 or h <= 0:
            return 200.0
        # h0 = 2Ac/u; rectangular u = 2(b+h) -> h0 = bh/(b+h)
        return max(50.0, min(1000.0, (b * h) / max(b + h, 1e-9)))
    except Exception:
        return 200.0


def _v54_estimate_h0_for_app(app) -> float:
    try:
        df = getattr(app, "df_pair", pd.DataFrame())
        if df is None or df.empty:
            return 200.0
        vals = []
        for _, r in df.head(200).iterrows():
            vals.append(_v54_estimate_h0_from_row(r))
        vals = [v for v in vals if math.isfinite(v) and v > 0]
        if not vals:
            return 200.0
        return float(pd.Series(vals).median())
    except Exception:
        return 200.0


def _v54_compute_phi_eff_for_app(app) -> Tuple[float, str]:
    backend = _v54_backend(app)
    RH = safe_float(getattr(app, "var_creep_RH", tk.StringVar(value="70")).get(), 70.0)
    t0 = safe_float(getattr(app, "var_creep_t0", tk.StringVar(value="28")).get(), 28.0)
    h0 = _v54_estimate_h0_for_app(app)
    fck = 30.0
    try:
        df = getattr(app, "df_pair", pd.DataFrame())
        if df is not None and not df.empty and "material" in df.columns:
            valid = df["material"].astype(str).str.extract(r"C\s*(\d+(?:[\.,]\d+)?)\s*/", expand=False).dropna()
            if not valid.empty:
                fck = float(str(valid.iloc[0]).replace(",", "."))
    except Exception:
        pass
    if _v54_is_sc_backend(backend):
        val, src = _v53_try_structuralcodes_phi(backend, fck, RH, t0, h0) if "_v53_try_structuralcodes_phi" in globals() else (None, "")
        if val is not None:
            return val, f"{src}; h0 automático={h0:.0f} mm"
        # Strict: não usar fórmula interna como valor normativo para o backend externo.
        return 0.0, f"Backend strict: φef não aplicado por fórmula interna; h0 automático={h0:.0f} mm; {src or 'API não detectada'}"
    val = _v53_ec2_creep_phi(fck, RH=RH, t0=t0, h0_mm=h0) if "_v53_ec2_creep_phi" in globals() else 2.0
    return val, f"EC2 PT interno: RH={RH:.0f}%, t0={t0:.0f} d, h0 automático={h0:.0f} mm, fck={fck:.0f} MPa"


def _v54_hide_filter_panel(app):
    try:
        if getattr(app, "_filters_visible_v54", False):
            return
        for w in _v54_walk_widgets(app):
            try:
                if isinstance(w, ttk.LabelFrame) and "Filtro" in _v54_safe_widget_text(w):
                    if not hasattr(app, "_filter_frames_v54"):
                        app._filter_frames_v54 = []
                    if w not in [x[0] for x in app._filter_frames_v54]:
                        app._filter_frames_v54.append((w, w.pack_info() if w.winfo_manager() == "pack" else None))
                    if w.winfo_manager() == "pack":
                        w.pack_forget()
            except Exception:
                pass
        app._filters_visible_v54 = False
    except Exception:
        pass


def _v54_show_filter_panel(app):
    try:
        frames = getattr(app, "_filter_frames_v54", [])
        for w, info in frames:
            try:
                if w.winfo_exists() and not w.winfo_manager():
                    if info:
                        w.pack(**info)
                    else:
                        w.pack(fill="x", pady=(0, 8))
            except Exception:
                pass
        app._filters_visible_v54 = True
    except Exception:
        pass


def _v54_hide_phi_h0_controls(app):
    """Remove da GUI os campos editáveis de φef e h0. Mantém RH/t0 porque são dados físicos de fluência."""
    try:
        for w in list(_v54_walk_widgets(app)):
            txt = _v54_safe_widget_text(w)
            cls = w.__class__.__name__
            # Remover linha φef no painel de parâmetros.
            if "φef" in txt or "phi_ef" in txt:
                parent = w.master
                try:
                    row = int(w.grid_info().get("row", -1))
                    for c in parent.winfo_children():
                        try:
                            if int(c.grid_info().get("row", -2)) == row:
                                c.grid_remove()
                        except Exception:
                            pass
                except Exception:
                    try: w.pack_forget()
                    except Exception: pass
            # Remover checkbutton automático, porque agora é sempre automático.
            if cls in ("Checkbutton", "TCheckbutton") and ("Calcular φef" in txt or "Calcular phi" in txt):
                try: w.grid_remove()
                except Exception:
                    try: w.pack_forget()
                    except Exception: pass
            # Remover campo h0 e nota h0.
            if "h0" in txt or "h₀" in txt:
                parent = w.master
                try:
                    row = int(w.grid_info().get("row", -1))
                    for c in parent.winfo_children():
                        try:
                            if int(c.grid_info().get("row", -2)) == row:
                                c.grid_remove()
                        except Exception:
                            pass
                except Exception:
                    try: w.pack_forget()
                    except Exception: pass
        if hasattr(app, "var_phi_eff_auto"):
            app.var_phi_eff_auto.set(True)
        if hasattr(app, "var_creep_h0"):
            app.var_creep_h0.set("0")
    except Exception:
        pass


def _v54_add_pdf_level_control(app):
    try:
        if not hasattr(app, "var_pdf_level"):
            app.var_pdf_level = tk.StringVar(value="Resumo executivo")
        # Acrescentar apenas se ainda não existir.
        for w in _v54_walk_widgets(app):
            if isinstance(w, ttk.LabelFrame) and _v54_safe_widget_text(w) == "Relatório PDF":
                return
        parent = getattr(app, "sidebar_canvas", app).winfo_children()[0] if hasattr(app, "sidebar_canvas") and app.sidebar_canvas.winfo_children() else None
        # O parent real da barra lateral é difícil de obter; procurar o último frame dentro do canvas.
        candidates = []
        for w in _v54_walk_widgets(app):
            if isinstance(w, ttk.Frame) and str(w.winfo_manager()) in ("grid", "pack"):
                candidates.append(w)
        host = None
        for w in candidates:
            try:
                # Preferir frames com LabelFrames filhos da sidebar.
                if any(isinstance(c, ttk.LabelFrame) and "Entrada" in _v54_safe_widget_text(c) for c in w.winfo_children()):
                    host = w
                    break
            except Exception:
                pass
        if host is None:
            return
        box = ttk.LabelFrame(host, text="Relatório PDF")
        box.pack(fill="x", pady=(0, 8))
        ttk.Label(box, text="Nível de detalhe").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(box, textvariable=app.var_pdf_level, values=["Resumo executivo", "Relatório técnico", "Memória detalhada"], state="readonly", width=20).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        box.columnconfigure(1, weight=1)
    except Exception:
        pass


def _v54_add_diagnostic_tab(app):
    try:
        if hasattr(app, "tab_backend_coverage"):
            return
        nb = None
        for w in _v54_walk_widgets(app):
            if isinstance(w, ttk.Notebook):
                nb = w
                break
        if nb is None:
            return
        app.tab_backend_coverage = ttk.Frame(nb)
        app.tab_structuralcodes_diag = ttk.Frame(nb)
        nb.add(app.tab_backend_coverage, text="Cobertura Backend")
        nb.add(app.tab_structuralcodes_diag, text="Diagnóstico SC")
        app.tree_backend_coverage = app._make_tree(app.tab_backend_coverage)
        app.tree_structuralcodes_diag = app._make_tree(app.tab_structuralcodes_diag)
        app.df_backend_coverage = _v54_backend_coverage_df()
        app.df_structuralcodes_diag = _v54_structuralcodes_diagnostics()
        app.show_df(app.tree_backend_coverage, app.df_backend_coverage)
        app.show_df(app.tree_structuralcodes_diag, app.df_structuralcodes_diag)
    except Exception:
        pass


def _v54_update_gui_after_backend(app):
    try:
        if hasattr(app, "df_backend_coverage"):
            app.df_backend_coverage = _v54_backend_coverage_df()
            if hasattr(app, "tree_backend_coverage"):
                app.show_df(app.tree_backend_coverage, app.df_backend_coverage)
        if hasattr(app, "df_structuralcodes_diag"):
            app.df_structuralcodes_diag = _v54_structuralcodes_diagnostics()
            if hasattr(app, "tree_structuralcodes_diag"):
                app.show_df(app.tree_structuralcodes_diag, app.df_structuralcodes_diag)
        _v53_update_quick_notes(app) if "_v53_update_quick_notes" in globals() else None
    except Exception:
        pass


# --- Cálculo por prumada / envolvente v5.4 ---
def _v54_reduced_envelope(df: pd.DataFrame, mode: str = "dimensionamento") -> pd.DataFrame:
    if df is None or df.empty:
        return df
    try:
        work = df.copy()
        for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
            if c not in work.columns:
                work[c] = 0.0
            work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
        # Excluir ELS da envolvente ELU, mas reter a combinação ELS se indicada noutra rotina.
        case_series = work.get("case", pd.Series(index=work.index, dtype=str)).astype(str)
        non_service = ~case_series.map(_case_is_service_v45) if "_case_is_service_v45" in globals() else pd.Series(True, index=work.index)
        elu = work[non_service].copy()
        if elu.empty:
            elu = work.copy()
        # A prumada é o primeiro agrupador: name/prumada; fallback member.
        if "prumada" not in elu.columns:
            elu["prumada"] = elu.get("name", elu.get("member", pd.Series("", index=elu.index))).astype(str).replace("", pd.NA).fillna(elu.get("member", pd.Series("", index=elu.index)).astype(str))
        selected = set()
        pre = _v53_mode_to_internal(mode) == "pre_dimensionamento"
        for _, grp in elu.groupby("prumada", dropna=False):
            if grp.empty:
                continue
            abs_fx = grp["fx"].abs()
            abs_my = grp["my"].abs()
            abs_mz = grp["mz"].abs()
            abs_v = grp["fy"].abs() + grp["fz"].abs()
            abs_t = grp["mx"].abs()
            score_biax = 0.20 * abs_fx + abs_my + abs_mz
            idxs = [score_biax.idxmax(), abs_fx.idxmax(), abs_my.idxmax(), abs_mz.idxmax()]
            if not pre:
                idxs += [abs_v.idxmax(), abs_t.idxmax()]
                # casos combinados: axial elevado + flexão dominante
                idxs += [(0.5 * abs_fx + abs_my).idxmax(), (0.5 * abs_fx + abs_mz).idxmax(), (0.3 * abs_fx + abs_my + abs_mz).idxmax()]
                # reter pelo menos um caso por member dentro da prumada quando possível.
                if "member" in grp.columns:
                    for _, g2 in grp.groupby("member", dropna=False):
                        if not g2.empty:
                            score2 = 0.25 * g2["fx"].abs() + g2["my"].abs() + g2["mz"].abs()
                            idxs.append(score2.idxmax())
            for idx in idxs:
                try: selected.add(idx)
                except Exception: pass
        if not selected:
            return elu.head(0)
        out = work.loc[sorted(selected)].copy().sort_values([c for c in ["prumada", "member", "case"] if c in work.columns]).reset_index(drop=True)
        out["envelope_v54"] = True
        return out
    except Exception:
        return _v53_reduced_envelope(df, mode=mode) if "_v53_reduced_envelope" in globals() else df

# Fazer o run_design v5.3 usar a nova envolvente, pois consulta o nome global.
globals()["_v53_reduced_envelope"] = _v54_reduced_envelope


# Cache de design por combinação de dados essenciais.
_old_design_one_v54 = ColumnDesigner.design_one

def _design_one_v54(self, row: pd.Series, prebuilt_candidates=None):
    try:
        if not hasattr(self, "_v54_design_cache"):
            self._v54_design_cache = {}
        cols = ["member", "case", "name", "material", "hy", "hz", "ax", "iy", "iz", "length", "fx_i", "fx_j", "fy_i", "fy_j", "fz_i", "fz_j", "mx_i", "mx_j", "my_i", "my_j", "mz_i", "mz_j"]
        key = tuple([getattr(self, "calc_mode", "")] + [round(safe_float(row.get(c, 0.0), 0.0), 4) if c not in ["member","case","name","material"] else str(row.get(c, "")) for c in cols])
        if key in self._v54_design_cache:
            cached = self._v54_design_cache[key].copy()
            cached["cache_v54"] = "Sim"
            return cached
        out = _old_design_one_v54(self, row, prebuilt_candidates=prebuilt_candidates)
        try:
            out["cache_v54"] = "Não"
            if len(self._v54_design_cache) < 5000:
                self._v54_design_cache[key] = out.copy()
        except Exception:
            pass
        return out
    except Exception:
        return _old_design_one_v54(self, row, prebuilt_candidates=prebuilt_candidates)

ColumnDesigner.design_one = _design_one_v54


# --- GUI v5.4 ---
_old_build_ui_v54 = ColumnsEC2App._build_ui

def _build_ui_v54(self):
    _old_build_ui_v54(self)
    try:
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1320x800")
        self.minsize(1080, 660)
    except Exception:
        pass
    try:
        if not hasattr(self, "var_pdf_level"):
            self.var_pdf_level = tk.StringVar(value="Resumo executivo")
        if not hasattr(self, "var_phi_eff_auto"):
            self.var_phi_eff_auto = tk.BooleanVar(value=True)
        self.var_phi_eff_auto.set(True)
        if hasattr(self, "var_creep_h0"):
            self.var_creep_h0.set("0")
        _v54_hide_phi_h0_controls(self)
        _v54_add_pdf_level_control(self)
        _v54_add_diagnostic_tab(self)
        _v54_hide_filter_panel(self)
        try:
            self.var_code_backend.trace_add("write", lambda *_: _v54_update_gui_after_backend(self))
        except Exception:
            pass
        self.after(300, lambda: _v54_update_gui_after_backend(self))
    except Exception:
        pass

ColumnsEC2App._build_ui = _build_ui_v54


# Validação: φef e h0 sempre automáticos.
_old_validate_inputs_v54 = ColumnsEC2App.validate_inputs

def _validate_inputs_v54(self):
    try:
        if hasattr(self, "var_phi_eff_auto"):
            self.var_phi_eff_auto.set(True)
        if hasattr(self, "var_creep_h0"):
            self.var_creep_h0.set("0")
        phi, src = _v54_compute_phi_eff_for_app(self)
        if phi and phi > 0:
            self.var_phi_eff.set(f"{phi:.3f}")
        else:
            self.var_phi_eff.set("0.000")
        self._phi_eff_source_v53 = src
        self._h0_auto_v54 = _v54_estimate_h0_for_app(self)
    except Exception as e:
        self._phi_eff_source_v53 = f"φef automático não calculado: {e}"
    return _old_validate_inputs_v54(self)

ColumnsEC2App.validate_inputs = _validate_inputs_v54


# Filtros só aparecem depois de concluído cálculo.
_old_run_design_v54 = ColumnsEC2App.run_design

def _run_design_v54(self):
    try:
        _v54_hide_filter_panel(self)
        self.df_backend_coverage = _v54_backend_coverage_df()
        self.df_structuralcodes_diag = _v54_structuralcodes_diagnostics()
        if hasattr(self, "tree_backend_coverage"):
            self.show_df(self.tree_backend_coverage, self.df_backend_coverage)
        if hasattr(self, "tree_structuralcodes_diag"):
            self.show_df(self.tree_structuralcodes_diag, self.df_structuralcodes_diag)
    except Exception:
        pass
    _old_run_design_v54(self)

    def _monitor():
        try:
            # Mostrar filtros quando houver resultados ou a análise terminar.
            if getattr(self, "df_results", pd.DataFrame()) is not None and not getattr(self, "df_results", pd.DataFrame()).empty:
                _v54_show_filter_panel(self)
                return
            self.after(700, _monitor)
        except Exception:
            pass
    self.after(900, _monitor)

ColumnsEC2App.run_design = _run_design_v54


# Metadados e notas.
_old_metadata_df_v54 = ColumnsEC2App._metadata_df

def _metadata_df_v54(self) -> pd.DataFrame:
    try:
        df = _old_metadata_df_v54(self).copy()
    except Exception:
        df = pd.DataFrame(columns=["Campo", "Valor"])
    extra = pd.DataFrame([
        ["Versão", APP_VERSION],
        ["Backend", _v54_backend(self)],
        ["h0", f"{getattr(self, '_h0_auto_v54', _v54_estimate_h0_for_app(self)):.0f} mm (automático)"],
        ["φef", f"{getattr(self, 'var_phi_eff', tk.StringVar(value='')).get()} (automático)"],
        ["Origem φef", getattr(self, "_phi_eff_source_v53", "")],
        ["PDF", getattr(self, "var_pdf_level", tk.StringVar(value="Resumo executivo")).get()],
        ["Filtros", "apresentados apenas depois do cálculo"],
    ], columns=["Campo", "Valor"])
    return pd.concat([df, extra], ignore_index=True)

ColumnsEC2App._metadata_df = _metadata_df_v54

_old_build_normative_notes_v54 = ColumnsEC2App.build_normative_notes

def _build_normative_notes_v54(self) -> pd.DataFrame:
    try:
        notes = _old_build_normative_notes_v54(self).copy()
    except Exception:
        notes = pd.DataFrame(columns=["Tema", "Referência", "Nota"])
    extra = pd.DataFrame([
        ("v5.4", "Diagnóstico", "A GUI e o XLSX incluem diagnóstico do structuralcodes e mapa de cobertura por backend."),
        ("v5.4", "Fluência", "h0 e φef são sempre calculados automaticamente; não são editáveis na GUI."),
        ("v5.4", "Desempenho", "A envolvente é feita por prumada/member e o cálculo usa cache para casos repetidos."),
        ("v5.4", "Relatório", "O PDF pode ser emitido como resumo executivo, relatório técnico ou memória detalhada."),
        ("v5.4", "DXF", "Exportação por secções-tipo com layers finais."),
    ], columns=["Tema", "Referência", "Nota"])
    return pd.concat([notes, extra], ignore_index=True).drop_duplicates()

ColumnsEC2App.build_normative_notes = _build_normative_notes_v54


def _v54_summary_source(app) -> pd.DataFrame:
    try:
        if getattr(app, "df_summary", pd.DataFrame()) is not None and not app.df_summary.empty:
            return app.df_summary.copy()
        if getattr(app, "df_results", pd.DataFrame()) is not None and not app.df_results.empty:
            return app.df_results.copy()
    except Exception:
        pass
    return pd.DataFrame()


def _v54_table_data_from_df(df: pd.DataFrame, cols: List[str], max_rows: int = 25):
    present = [c for c in cols if c in df.columns]
    if not present:
        return [["Sem dados"]]
    data = [present]
    for _, r in df.head(max_rows).iterrows():
        row = []
        for c in present:
            v = r.get(c, "")
            if isinstance(v, float):
                row.append("" if not math.isfinite(v) else f"{v:.2f}")
            else:
                s = str(v)
                row.append(s if len(s) <= 40 else s[:37] + "...")
        data.append(row)
    return data


# PDF v5.4 com níveis de detalhe.
def _write_pdf_v54(self, path: str):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    except Exception as err:
        raise RuntimeError("Instale reportlab para exportar PDF: pip install reportlab") from err

    level = getattr(self, "var_pdf_level", tk.StringVar(value="Resumo executivo")).get()
    df = _v54_summary_source(self)
    results = getattr(self, "df_results", pd.DataFrame())
    blockers = _v53_blocking_failures(results) if "_v53_blocking_failures" in globals() else pd.DataFrame()
    coverage = _v54_backend_coverage_df()
    backend = _v54_backend(self)

    doc = SimpleDocTemplate(path, pagesize=landscape(A4), rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    doc.title = f"{APP_NAME} {APP_VERSION}"
    doc.author = APP_AUTHOR
    doc.subject = APP_SUBJECT

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitleV54", parent=styles["Title"], alignment=TA_CENTER, fontName="Courier-Bold", fontSize=14, leading=21, spaceAfter=10))
    styles.add(ParagraphStyle(name="ReportSubtitleV54", parent=styles["Normal"], alignment=TA_CENTER, fontName="Courier", fontSize=9, leading=13, textColor=colors.darkgrey, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyCourierV54", parent=styles["Normal"], fontName="Courier", fontSize=8, leading=12, spaceAfter=4))
    styles.add(ParagraphStyle(name="SmallV54", parent=styles["Normal"], fontName="Courier", fontSize=7, leading=10))
    styles.add(ParagraphStyle(name="SectionV54", parent=styles["Heading2"], fontName="Courier-Bold", fontSize=11, leading=16, spaceBefore=8, spaceAfter=8))

    def tbl(data, repeat=1):
        t = Table(data, repeatRows=repeat)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), "Courier", 7),
            ("FONT", (0,0), (-1,0), "Courier-Bold", 7),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e8edf3")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 3),
            ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ]))
        return t

    story = []
    story.append(Paragraph(f"{APP_NAME} {APP_VERSION}", styles["ReportTitleV54"]))
    story.append(Paragraph(f"Dimensionamento de pilares | {backend} | {level}", styles["ReportSubtitleV54"]))
    meta = [
        ["Programa", f"{APP_NAME} {APP_VERSION}", "Autor", APP_AUTHOR],
        ["Data", datetime.now().strftime("%Y-%m-%d %H:%M"), "Backend", backend],
        ["Modo", _v53_mode_to_label(getattr(self, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get()), "Casos", str(len(results)) if results is not None else "0"],
        ["h0", f"{getattr(self, '_h0_auto_v54', _v54_estimate_h0_for_app(self)):.0f} mm", "φef", getattr(self, "var_phi_eff", tk.StringVar(value="")).get()],
    ]
    story.append(tbl(meta, repeat=0))
    story.append(Spacer(1, 5*mm))

    # Resumo executivo
    n_total = len(results) if results is not None else 0
    n_prum = df.get("prumada", df.get("name", df.get("member", pd.Series(dtype=str)))).astype(str).nunique() if df is not None and not df.empty else 0
    n_fail = len(blockers) if blockers is not None else 0
    story.append(Paragraph("Resumo executivo", styles["SectionV54"]))
    story.append(tbl([["Casos calculados", "Prumadas", "Falhas bloqueantes", "Observação"], [str(n_total), str(n_prum), str(n_fail), "XLSX contém a memória completa"]]))
    story.append(Spacer(1, 4*mm))

    main_cols = ["prumada", "member", "case", "status", "solucao", "utilizacao", "failure_summary", "failure_reason"]
    story.append(Paragraph("Resultados governantes por prumada", styles["SectionV54"]))
    story.append(tbl(_v54_table_data_from_df(df, main_cols, max_rows=30)))

    if blockers is not None and not blockers.empty:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("Falhas bloqueantes", styles["SectionV54"]))
        story.append(tbl(_v54_table_data_from_df(blockers, ["prumada", "member", "case", "failure_type", "failure_summary", "failure_reason", "failure_action"], max_rows=20)))

    if level in ["Relatório técnico", "Memória detalhada"]:
        story.append(PageBreak())
        story.append(Paragraph("Mapa de cobertura por backend", styles["SectionV54"]))
        cov = coverage[coverage["Backend"].astype(str).eq(backend) | coverage["Backend"].astype(str).eq(BACKEND_EC2_PT_2010)].copy()
        story.append(tbl(_v54_table_data_from_df(cov, ["Verificação", "Backend", "Origem", "Estado", "Nota"], max_rows=60)))
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Parâmetros e notas", styles["SectionV54"]))
        notes = self.build_normative_notes()
        story.append(tbl(_v54_table_data_from_df(notes, ["Tema", "Referência", "Nota"], max_rows=40)))

    if level == "Memória detalhada":
        story.append(PageBreak())
        story.append(Paragraph("Memória detalhada — resultados por caso de envolvente", styles["SectionV54"]))
        detail_cols = ["prumada", "member", "case", "n_ed_kN", "my_ed_kNm", "mz_ed_kNm", "lambda_y", "lambda_z", "as_req_mm2", "as_prov_mm2", "mrd_y_kNm", "mrd_z_kNm", "status", "failure_reason"]
        story.append(tbl(_v54_table_data_from_df(results, detail_cols, max_rows=80)))

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Nota: o PDF é formatado conforme o nível seleccionado. O ficheiro XLSX conserva os dados completos, diagnóstico, cobertura por backend e resultados detalhados.", styles["SmallV54"]))

    def _footer(pdf_canvas, doc_obj):
        pdf_canvas.saveState()
        pdf_canvas.setFont("Courier", 7)
        pdf_canvas.setFillColor(colors.grey)
        pdf_canvas.drawString(12*mm, 7*mm, f"{APP_NAME} {APP_VERSION} | {APP_AUTHOR}")
        pdf_canvas.drawRightString(285*mm, 7*mm, f"Página {doc_obj.page}")
        pdf_canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)

ColumnsEC2App._write_pdf = _write_pdf_v54


# XLSX v5.4: diagnóstico/cobertura/parâmetros automáticos.
_old_write_excel_v54 = ColumnsEC2App._write_excel

def _write_excel_v54(self, path: str):
    _old_write_excel_v54(self, path)
    try:
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            _v54_backend_coverage_df().to_excel(writer, sheet_name="34_Cobertura_Backend", index=False)
            _v54_structuralcodes_diagnostics().to_excel(writer, sheet_name="35_Diagnostico_SC", index=False)
            pd.DataFrame([
                ["Versão", APP_VERSION],
                ["Backend", _v54_backend(self)],
                ["Modo", _v53_mode_to_label(getattr(self, "var_calc_mode", tk.StringVar(value="Dimensionamento")).get())],
                ["h0", f"{getattr(self, '_h0_auto_v54', _v54_estimate_h0_for_app(self)):.0f} mm"],
                ["φef", getattr(self, "var_phi_eff", tk.StringVar(value="")).get()],
                ["Origem φef", getattr(self, "_phi_eff_source_v53", "")],
                ["PDF nível", getattr(self, "var_pdf_level", tk.StringVar(value="Resumo executivo")).get()],
                ["Cache", "design_one por chave de esforços/geometria"],
                ["Envolvente", "por prumada/member"],
            ], columns=["Campo", "Valor"]).to_excel(writer, sheet_name="36_Parametros_v5_4", index=False)
    except Exception as err:
        try:
            self.status_var.set(f"XLSX exportado; aviso folhas v5.4: {err}")
        except Exception:
            pass

ColumnsEC2App._write_excel = _write_excel_v54


# DXF v5.4: secções-tipo e layers finais.
def _v54_dxf_header():
    layers = [
        ("COLUMN_CONCRETE", 7), ("COLUMN_REBAR", 1), ("COLUMN_STIRRUP", 3),
        ("COLUMN_TEXT", 2), ("COLUMN_TABLE", 8), ("COLUMN_AXIS", 6)
    ]
    s = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "0", "ENDSEC"]
    s += ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layers))]
    for name, color in layers:
        s += ["0", "LAYER", "2", name, "70", "0", "62", str(color), "6", "CONTINUOUS"]
    s += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    return s


def _v54_dxf_text(lines, x, y, text, h=2.5, layer="COLUMN_TEXT"):
    lines += ["0", "TEXT", "8", layer, "10", f"{x:.3f}", "20", f"{y:.3f}", "30", "0", "40", f"{h:.3f}", "1", str(text)]


def _v54_dxf_rect(lines, x, y, w, h, layer="COLUMN_CONCRETE"):
    pts = [(x,y), (x+w,y), (x+w,y+h), (x,y+h), (x,y)]
    for (x1,y1),(x2,y2) in zip(pts[:-1], pts[1:]):
        lines += ["0","LINE","8",layer,"10",f"{x1:.3f}","20",f"{y1:.3f}","30","0","11",f"{x2:.3f}","21",f"{y2:.3f}","31","0"]


def _v54_dxf_circle(lines, x, y, r=1.2, layer="COLUMN_REBAR"):
    lines += ["0","CIRCLE","8",layer,"10",f"{x:.3f}","20",f"{y:.3f}","30","0","40",f"{r:.3f}"]


def _v54_parse_phi_solution(sol: str):
    # devolve diâmetro dominante; suporte simples para 4Ø25 + 4Ø16
    vals = re.findall(r"Ø\s*(\d+)", str(sol))
    return float(vals[0]) if vals else 16.0


def _export_dxf_v54(self):
    df = _v54_summary_source(self)
    if df is None or df.empty:
        messagebox.showwarning("Aviso", "Não há resultados para exportar em DXF.")
        return
    path = filedialog.asksaveasfilename(title="Exportar DXF — secções-tipo", defaultextension=".dxf", filetypes=[("DXF", "*.dxf")])
    if not path:
        return
    try:
        self.status_var.set("A preparar DXF por secções-tipo...")
        self.progress_var.set(10.0)
        self.update_idletasks()
        work = df.copy()
        for c in ["b_cm", "h_cm", "solucao", "material"]:
            if c not in work.columns:
                work[c] = ""
        work["_tipo_key"] = work[["b_cm", "h_cm", "solucao", "material"]].astype(str).agg("|".join, axis=1)
        tipos = work.drop_duplicates("_tipo_key").reset_index(drop=True)
        tipos["sec_tipo"] = [f"S{i+1}" for i in range(len(tipos))]
        key_to_tipo = dict(zip(tipos["_tipo_key"], tipos["sec_tipo"]))
        work["sec_tipo"] = work["_tipo_key"].map(key_to_tipo)
        lines = _v54_dxf_header()
        _v54_dxf_text(lines, 0, 0, f"{APP_NAME} {APP_VERSION} - Quadro de pilares / secções-tipo", 3.5)
        x0, y0 = 0.0, -12.0
        cell_w, cell_h = 55.0, 55.0
        scale = 0.45
        for i, (_, r) in enumerate(tipos.iterrows()):
            col = i % 4
            row = i // 4
            x = x0 + col * cell_w
            y = y0 - row * cell_h
            b = safe_float(r.get("b_cm", 30), 30.0) * 10.0 * scale / 10.0
            h = safe_float(r.get("h_cm", 30), 30.0) * 10.0 * scale / 10.0
            b = max(12.0, min(45.0, b)); h = max(12.0, min(45.0, h))
            _v54_dxf_rect(lines, x, y-h, b, h, "COLUMN_CONCRETE")
            _v54_dxf_rect(lines, x+1.5, y-h+1.5, b-3, h-3, "COLUMN_STIRRUP")
            phi = _v54_parse_phi_solution(r.get("solucao", ""))
            rr = max(0.8, min(1.8, phi/16.0))
            for px, py in [(x+3,y-3),(x+b-3,y-3),(x+3,y-h+3),(x+b-3,y-h+3)]:
                _v54_dxf_circle(lines, px, py, rr, "COLUMN_REBAR")
            _v54_dxf_text(lines, x, y+4, f"{r.get('sec_tipo','')} | {r.get('b_cm','')}x{r.get('h_cm','')} cm", 2.2)
            _v54_dxf_text(lines, x, y-h-5, str(r.get("solucao", ""))[:42], 1.8)
            _v54_dxf_text(lines, x, y-h-9, str(r.get("material", ""))[:20], 1.8)
        # Quadro de correspondência prumada -> secção-tipo
        y_table = y0 - ((len(tipos)+3)//4)*cell_h - 12
        _v54_dxf_text(lines, 0, y_table+5, "Quadro de correspondência", 2.5, "COLUMN_TABLE")
        headers = ["Prumada", "Member", "Secção-tipo", "Solução", "Estado"]
        xs = [0, 35, 60, 90, 150]
        for x, htxt in zip(xs, headers):
            _v54_dxf_text(lines, x, y_table, htxt, 1.8, "COLUMN_TABLE")
        for i, (_, r) in enumerate(work.head(120).iterrows(), start=1):
            yy = y_table - i*5
            vals = [r.get("prumada", r.get("name", "")), r.get("member", ""), r.get("sec_tipo", ""), r.get("solucao", ""), r.get("status", "")]
            for x, val in zip(xs, vals):
                _v54_dxf_text(lines, x, yy, str(val)[:32], 1.6, "COLUMN_TABLE")
        lines += ["0", "ENDSEC", "0", "EOF"]
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.progress_var.set(100.0)
        self.status_var.set(f"DXF por secções-tipo exportado para: {path}")
    except Exception as err:
        self.progress_var.set(0.0)
        messagebox.showerror("Erro", f"Não foi possível exportar DXF.\n\n{err}")

ColumnsEC2App.export_dxf = _export_dxf_v54



# ============================================================
# ColumnsEC2 v5.5 — correcções de classificação e procura de soluções
# - pormenorização: deixa de tratar distância >300 mm entre varões de canto como falha bloqueante;
# - torção: introduz limiar de relevância; TEd muito pequeno deixa de exigir armadura de torção;
# - biaxial: quando a shortlist inicial falha, pesquisa o catálogo completo admissível antes de devolver falha;
# - resultados: utilização passa a representar utilização biaxial quando houver falha biaxial.
# ============================================================
APP_VERSION = "v5.5"


def _v55_layout_description(layout) -> str:
    try:
        if hasattr(layout, "description"):
            return str(layout.description)
        return f"{int(getattr(layout, 'n_total', 0))}Ø{int(getattr(layout, 'phi_long_mm', 0))}"
    except Exception:
        return "layout"


def _v55_torsion_relevance(t_ed_kNm, trdmax_kNm, my_kNm=0.0, mz_kNm=0.0) -> tuple:
    """Classificação prática de relevância de torção.
    A verificação resistente só é condicionante quando TEd se aproxima de TRd,max.
    Para valores muito pequenos, a torção é registada como não condicionante.
    """
    t = abs(safe_float(t_ed_kNm, 0.0))
    trd = abs(safe_float(trdmax_kNm, 0.0))
    mref = max(abs(safe_float(my_kNm, 0.0)), abs(safe_float(mz_kNm, 0.0)), 1.0)
    ratio_res = t / trd if trd > 1e-9 else 0.0
    ratio_bend = t / mref
    if t <= 1e-9:
        return "Sem torção relevante", ratio_res, ratio_bend
    if trd > 0 and ratio_res <= 0.05:
        return "Torção desprezável — não condicionante", ratio_res, ratio_bend
    if ratio_bend <= 0.05:
        return "Torção pequena — verificar apenas se for torção de equilíbrio", ratio_res, ratio_bend
    if trd > 0 and t <= trd:
        return "Requer verificação/dimensionamento de torção", ratio_res, ratio_bend
    return "Não conforme: TEd > TRd,max", ratio_res, ratio_bend


# Substitui a função global chamada pelo motor interno.
def torsion_check_ec2_v4(t_ed_kNm, b_mm, h_mm, cover_mm, fck, fcd, fyd):
    t_ed = abs(safe_float(t_ed_kNm, 0.0)) * 1e6  # Nmm
    if b_mm <= 0 or h_mm <= 0:
        return {"TRdmax_kNm": None, "Asw_s_t_req_mm2_per_m": None, "Asl_t_req_mm2": None, "torsion_status": "Dados insuficientes"}
    tef = max(2.0 * cover_mm, min(b_mm, h_mm) / 6.0, 50.0)
    bk = max(b_mm - tef, 1.0)
    hk = max(h_mm - tef, 1.0)
    Ak = bk * hk
    uk = 2.0 * (bk + hk)
    cot = 1.0
    nu1 = 0.6 * (1.0 - fck / 250.0)
    trdmax_Nmm = 2.0 * nu1 * fcd * Ak * tef / (cot + 1.0 / cot)
    trdmax_kNm = trdmax_Nmm / 1e6
    status, ratio_res, _ratio_bend = _v55_torsion_relevance(t_ed_kNm, trdmax_kNm)
    if "desprezável" in status.lower() or "sem torção" in status.lower() or "pequena" in status.lower():
        asw_s = 0.0
        asl = 0.0
    else:
        asw_s = t_ed / max(2.0 * Ak * fyd * cot, 1e-9) * 1000.0
        asl = t_ed * uk / max(2.0 * Ak * fyd, 1e-9)
    return {
        "TRdmax_kNm": trdmax_kNm,
        "Asw_s_t_req_mm2_per_m": asw_s,
        "Asl_t_req_mm2": asl,
        "torsion_status": status,
        "torsion_utilization_TRdmax": ratio_res,
    }


def detailing_check_v4(result: dict) -> dict:
    """Pormenorização de pilares — política corrigida v5.5.
    A regra de 300 mm foi usada antes como bloqueante para qualquer lado da secção.
    Isso é demasiado severo para pilares com varões de canto; passa a ser aviso de travamento,
    não falha resistente.
    """
    b = _finite(result.get("b_cm"), 0.0) * 10.0
    h = _finite(result.get("h_cm"), 0.0) * 10.0
    phi = _finite(result.get("phi_long_mm"), 0.0)
    phi_st = _finite(result.get("phi_st_mm"), 0.0)
    s = _finite(result.get("s_st_mm"), 0.0)
    n_total = int(_finite(result.get("n_total"), 0))
    n_y = int(_finite(result.get("n_bars_y"), 0))
    n_z = int(_finite(result.get("n_bars_z"), 0))
    cover = _finite(result.get("cover_mm", 35.0), 35.0)
    issues_block = []
    issues_warn = []
    min_bars = 6 if abs(b - h) < 1e-6 and "circ" in str(result.get("name", "")).lower() else 4
    if n_total and n_total < min_bars:
        issues_block.append(f"número mínimo de varões não cumprido ({n_total}<{min_bars})")
    if phi and phi < 10:
        issues_block.append("diâmetro longitudinal inferior a Ø10")
    if phi and phi_st and phi_st < max(6.0, phi / 4.0):
        issues_block.append("diâmetro dos estribos inferior a max(6 mm; Øl/4)")
    # Anexo Nacional: espaçamento das cintas entre nós não excede 15φmin,long, menor dimensão e 300 mm.
    smax = min(15.0 * phi if phi else 999.0, min(b, h) if b and h else 999.0, 300.0)
    if s and s > smax + 1e-6:
        issues_block.append(f"espaçamento dos estribos superior ao limite ({s:.0f}>{smax:.0f} mm)")
    edge = cover + phi_st + phi / 2.0
    max_ctc = 0.0
    min_clear = 1e9
    if b > 0 and n_y > 1:
        ctc = (b - 2 * edge) / max(n_y - 1, 1)
        max_ctc = max(max_ctc, ctc)
        min_clear = min(min_clear, ctc - phi)
    if h > 0 and n_z > 1:
        ctc = (h - 2 * edge) / max(n_z - 1, 1)
        max_ctc = max(max_ctc, ctc)
        min_clear = min(min_clear, ctc - phi)
    if min_clear < max(20.0, phi, 25.0):
        issues_block.append("espaçamento livre entre varões insuficiente")
    if max_ctc > 300:
        issues_warn.append("distância entre varões longitudinais >300 mm; não bloqueante para varões de canto, confirmar travamento por cintas/grampos")
    if n_y > 4 or n_z > 4:
        issues_warn.append("prever estribos/grampos intermédios para travar varões comprimidos")
    if issues_block:
        status = "Não conforme"
    elif issues_warn:
        status = "Verificar"
    else:
        status = "OK"
    issues = issues_block + issues_warn
    return {
        "detailing_status": status,
        "detailing_issues": "; ".join(issues) if issues else "-",
        "detailing_min_bars": min_bars,
        "detailing_smax_ties_mm": smax if smax < 998 else None,
        "detailing_max_long_ctc_mm": max_ctc if max_ctc else None,
        "detailing_min_clear_mm": None if min_clear == 1e9 else min_clear,
    }


def _v55_clean_recommendations(text: str, torsion_non_conditioning: bool = False, detailing_ok: bool = False) -> str:
    parts = [p.strip() for p in str(text or "").split(";") if p.strip()]
    cleaned = []
    for p in parts:
        low = p.lower()
        if torsion_non_conditioning and "torção" in low:
            continue
        if detailing_ok and "pormenor" in low:
            continue
        cleaned.append(p)
    return "; ".join(dict.fromkeys(cleaned))


def _v55_apply_layout_to_result(self, out: dict, layout, util, my_cap, mz_cap, status="OK", failure_reason="") -> dict:
    smax = self.tie_spacing_max(_finite(out.get("b_cm")) * 10.0, _finite(out.get("h_cm")) * 10.0, layout.phi_long_mm)
    sprov = self.choose_spacing(smax)
    desc = _v55_layout_description(layout)
    out.update({
        "phi_long_mm": float(getattr(layout, "phi_long_mm", 0.0)),
        "n_total": int(getattr(layout, "n_total", 0)),
        "n_bars_y": int(getattr(layout, "n_bars_y", 0)),
        "n_bars_z": int(getattr(layout, "n_bars_z", 0)),
        "as_prov_mm2": float(getattr(layout, "as_prov_mm2", 0.0)),
        "phi_st_mm": float(getattr(layout, "phi_st_mm", self.choose_stirrup(getattr(layout, "phi_long_mm", 10.0)))),
        "s_st_mm": sprov,
        "s_st_max_mm": smax,
        "mrd_y_kNm": my_cap,
        "mrd_z_kNm": mz_cap,
        "status": status,
        "utilizacao": util,
        "solucao": f"{desc} + estribos Ø{int(getattr(layout, 'phi_st_mm', 8))}//{sprov / 10:.1f} cm",
        "layout_type": "misto" if isinstance(layout, MixedLayout) else "uniforme",
        "layout_description": desc,
        "failure_reason": failure_reason,
        "failure_type": classify_failure_reason(failure_reason),
    })
    return out


def _v55_biaxial_catalogue_search(self, row: pd.Series, out: dict) -> dict:
    """Pesquisa adicional quando a shortlist inicial falha.
    Não altera esforços; só procura armaduras admissíveis adicionais antes de declarar falha biaxial.
    """
    try:
        if str(out.get("failure_type", "")) != "resistencia_biaxial":
            return out
        material = str(row.get("material", out.get("material", DEFAULT_CONCRETE_CLASS)) or DEFAULT_CONCRETE_CLASS)
        fck = parse_concrete_strength(material)
        cp = concrete_props(fck, gamma_c=self.gamma_c)
        sp = steel_props(self.fyk, gamma_s=self.gamma_s)
        fyd = sp["fyd"]
        Es = sp["Es"]
        b_mm = cm_to_mm(row.get("hy", out.get("b_cm", 0.0)))
        h_mm = cm_to_mm(row.get("hz", out.get("h_cm", 0.0)))
        if b_mm <= 0:
            b_mm = _finite(out.get("b_cm")) * 10.0
        if h_mm <= 0:
            h_mm = _finite(out.get("h_cm")) * 10.0
        ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
        if not math.isfinite(ac_mm2) or ac_mm2 <= 0:
            ac_mm2 = b_mm * h_mm
        n_ed = _finite(out.get("n_ed_kN"), max(abs(safe_float(row.get("fx_i", 0.0), 0.0)), abs(safe_float(row.get("fx_j", 0.0), 0.0))))
        as_req = _finite(out.get("as_req_mm2"), 0.0)
        as_max = self.max_longitudinal_as(ac_mm2)
        is_circular = self.infer_is_circular(row, b_mm, h_mm)
        max_face_y, max_face_z = self.max_bars_per_face(b_mm, h_mm, is_circular=is_circular)
        candidates = [
            ly for ly in self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)
            if float(getattr(ly, "as_prov_mm2", 0.0)) >= as_req
            and float(getattr(ly, "as_prov_mm2", 0.0)) <= as_max
            and int(getattr(ly, "n_bars_y", 99)) <= max_face_y
            and int(getattr(ly, "n_bars_z", 99)) <= max_face_z
        ]
        if not candidates:
            return out
        # Primeiro tenta o catálogo completo por ordem prática. Limita por desempenho, mas inclui soluções pesadas até Asmax.
        candidates = sorted(candidates, key=lambda ly: _layout_practical_score_v45(ly, as_req) if "_layout_practical_score_v45" in globals() else (abs(float(getattr(ly,"as_prov_mm2",0))-as_req), float(getattr(ly,"as_prov_mm2",0))))
        best_fail = None
        ok_solution = None
        shortlist_rows = []
        for ly in candidates[:160]:
            capacities = self.capacity_for_layout(ly, n_ed, cp["fcd"], fyd, Es)
            ok, util, my_cap, mz_cap = self.biaxial_ok(_finite(out.get("my_ed_kNm")), _finite(out.get("mz_ed_kNm")), capacities)
            desc = _v55_layout_description(ly)
            shortlist_rows.append({
                "solucao": desc,
                "as_prov_mm2": float(getattr(ly, "as_prov_mm2", 0.0)),
                "utilizacao": "" if util is None else f"{util:.3f}",
                "status_short": "OK" if ok else "Falha",
                "failure_short": "" if ok else "biaxial",
            })
            item = (999.0 if util is None else float(util), float(getattr(ly, "as_prov_mm2", 0.0)), ly, my_cap, mz_cap)
            if best_fail is None or item[0] < best_fail[0]:
                best_fail = item
            if ok:
                ok_solution = (ly, util, my_cap, mz_cap)
                break
        if ok_solution is not None:
            ly, util, my_cap, mz_cap = ok_solution
            out = _v55_apply_layout_to_result(self, out, ly, util, my_cap, mz_cap, status="OK", failure_reason="")
            out["failure_severity"] = "OK"
            out["design_decision"] = "Solução resistente encontrada no catálogo completo v5.5"
            out["review_priority"] = "Normal"
            out["failure_action"] = "-"
            out["failure_summary"] = "OK | catálogo completo v5.5"
        elif best_fail is not None:
            util, _as, ly, my_cap, mz_cap = best_fail
            out = _v55_apply_layout_to_result(self, out, ly, util, my_cap, mz_cap, status="Falha", failure_reason="Falha de resistência biaxial: catálogo completo testado, sem solução admissível com η≤1,0")
            out["failure_severity"] = "Bloqueante"
            out["design_decision"] = "Solução resistente não encontrada no catálogo admissível"
            out["review_priority"] = "Alta"
            out["failure_action"] = "Aumentar secção, rever l0/combinação governante ou validar com superfície N-My-Mz refinada."
            out["failure_summary"] = "Bloqueante | resistencia_biaxial | catálogo completo v5.5 sem η≤1,0"
        out["shortlist_text"] = serialize_shortlist(shortlist_rows[:40])
        out["biaxial_catalogue_v55"] = f"testadas {min(len(candidates), 160)} soluções admissíveis"
        return out
    except Exception as e:
        out["biaxial_catalogue_v55"] = f"erro na pesquisa adicional: {e}"
        return out


_old_design_one_v55 = ColumnDesigner.design_one

def _design_one_v55(self, row: pd.Series, prebuilt_candidates=None):
    out = _old_design_one_v55(self, row, prebuilt_candidates=prebuilt_candidates)
    if not isinstance(out, dict):
        return out
    backend = str(out.get("code_backend", BACKEND_EC2_PT_2010 if "BACKEND_EC2_PT_2010" in globals() else ""))
    if "structuralcodes" in backend.lower():
        return out
    out = _v55_biaxial_catalogue_search(self, row, out)
    # Pós-processamento de torção para eliminar falsos avisos por TEd muito pequeno.
    try:
        status_t, ratio_res, ratio_bend = _v55_torsion_relevance(out.get("mx_ed_kNm", 0.0), out.get("t_rd_max_kNm", 0.0), out.get("my_ed_kNm", 0.0), out.get("mz_ed_kNm", 0.0))
        out["torsion_status"] = status_t
        out["torsion_utilization_TRdmax"] = ratio_res
        out["torsion_ratio"] = ratio_bend
        if any(k in status_t.lower() for k in ["desprez", "sem torção", "pequena"]):
            out["asw_s_t_req_mm2_per_m"] = 0.0
            out["asl_t_req_mm2"] = 0.0
            out["recommendations"] = _v55_clean_recommendations(out.get("recommendations", ""), torsion_non_conditioning=True)
    except Exception:
        pass
    # Se a única razão de falha era pormenorização e a nova pormenorização não é bloqueante, converter para Aviso/OK.
    try:
        det_status = str(out.get("detailing_status", ""))
        fr = str(out.get("failure_reason", "") or "")
        if "pormenorização" in fr.lower() and det_status != "Não conforme":
            out["status"] = "Aviso" if det_status == "Verificar" else "OK"
            out["failure_reason"] = "" if det_status == "OK" else "Pormenorização a confirmar em desenho: " + str(out.get("detailing_issues", ""))
            out["failure_type"] = "" if det_status == "OK" else "pormenorizacao"
            out["failure_severity"] = "Aviso" if det_status == "Verificar" else "OK"
            out["design_decision"] = "Aceitável com revisão de pormenorização" if det_status == "Verificar" else "OK"
            out["review_priority"] = "Média" if det_status == "Verificar" else "Normal"
            out["failure_action"] = "Confirmar travamento por cintas/grampos no desenho." if det_status == "Verificar" else "-"
            out["failure_summary"] = f"{out.get('failure_severity','')} | {out.get('failure_type','')} | {out.get('failure_action','')}"
            out["recommendations"] = _v55_clean_recommendations(out.get("recommendations", ""), detailing_ok=(det_status == "OK"))
    except Exception:
        pass
    try:
        if str(out.get("status", "")) == "OK" and str(out.get("detailing_status", "")) == "Verificar":
            out["status"] = "Aviso"
            out["failure_reason"] = ""
            out["failure_type"] = ""
            out["failure_severity"] = "Aviso"
            out["design_decision"] = "Solução resistente; pormenorização a confirmar em desenho"
            out["review_priority"] = "Média"
            out["failure_action"] = "Confirmar travamento por cintas/grampos no desenho."
            out["failure_summary"] = "Aviso | pormenorização | confirmar travamento por cintas/grampos"
    except Exception:
        pass
    return out

ColumnDesigner.design_one = _design_one_v55


# Ajuste final da política de falhas: só status=Falha ou severity=Bloqueante contam como bloqueante.
if "_v53_blocking_failures" in globals():
    def _v53_blocking_failures(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        tmp = enrich_failures_v43(df.copy()) if "enrich_failures_v43" in globals() else df.copy()
        sev = tmp.get("failure_severity", pd.Series("", index=tmp.index)).astype(str)
        status = tmp.get("status", pd.Series("", index=tmp.index)).astype(str)
        return tmp[(sev == "Bloqueante") | (status == "Falha")].copy()


def _metadata_df_v55(self) -> pd.DataFrame:
    try:
        df = _old_metadata_df_v54(self).copy() if "_old_metadata_df_v54" in globals() else _metadata_df_v3(self).copy()
    except Exception:
        df = pd.DataFrame(columns=["Campo", "Valor"])
    extra = pd.DataFrame([
        ["Versão de correcção", APP_VERSION],
        ["Correcção biaxial", "catálogo completo admissível antes de declarar falha"],
        ["Correcção torção", "limiar de relevância por TEd/TRd,max"],
        ["Correcção pormenorização", "distância >300 mm entre varões de canto deixa de ser falha bloqueante"],
    ], columns=["Campo", "Valor"])
    return pd.concat([df, extra], ignore_index=True)

try:
    ColumnsEC2App._metadata_df = _metadata_df_v55
except Exception:
    pass



# ============================================================
# ColumnsEC2 v5.6 — revisão meticulosa do motor default PT
# - layouts construtivos explícitos para pilares rectangulares;
# - capacidade N-My-Mz com cache corrigida para layouts mistos;
# - dimensionamento por catálogo completo admissível, não apenas shortlist;
# - pormenorização separada em bloqueante / aviso / informativo;
# - torção desprezável não condicionante;
# - decisão final mais coerente e auditável.
# ============================================================
