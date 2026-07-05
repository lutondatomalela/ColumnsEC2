# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC14 — practical rebar policy and circular-section detection.

This patch keeps the calculation workflow of RC13 and adjusts the automatic
reinforcement catalogue to reflect common building-column detailing practice:
- Ø25 and Ø32 are not selected automatically;
- corner bars are preferably Ø12 or Ø16, with Ø10 kept for small/light columns;
- face distribution bars may start from Ø10;
- column-line summaries rationalise corner bars and, where practical, the full
  reinforcement arrangement across the same column line/section;
- circular sections are inferred from name, area and second moments of area.
"""

APP_VERSION = "v0.9 RC14 Modular"

# ---------------------------------------------------------------------------
# Section shape inference
# ---------------------------------------------------------------------------

def _rc14_relerr(actual, expected):
    try:
        actual = float(actual)
        expected = float(expected)
        if expected <= 1e-12:
            return 9e9
        return abs(actual - expected) / abs(expected)
    except Exception:
        return 9e9


def _rc14_infer_circular_from_geometry(row, b_mm: float, h_mm: float) -> bool:
    """Infer circular sections from the imported geometric properties.

    Many analysis packages export circular columns with HY≈HZ equal to the
    diameter, AX≈πD²/4 and IY≈IZ≈πD⁴/64. Rectangular/square columns instead have
    AX≈b·h and I≈b·h³/12. This function uses those ratios and remains conservative
    to avoid misclassifying ordinary square sections.
    """
    try:
        b = float(b_mm or 0.0)
        h = float(h_mm or 0.0)
    except Exception:
        return False
    if b <= 0 or h <= 0:
        return False
    d = max(b, h)
    square_like = abs(b - h) / max(d, 1e-9) <= 0.035
    if not square_like:
        return False

    ax_cm2 = safe_float(row.get("ax", float("nan")), float("nan"))
    iy_cm4 = safe_float(row.get("iy", float("nan")), float("nan"))
    iz_cm4 = safe_float(row.get("iz", float("nan")), float("nan"))
    ax = ax_cm2 * 100.0 if math.isfinite(ax_cm2) else float("nan")
    iy = iy_cm4 * 10000.0 if math.isfinite(iy_cm4) else float("nan")
    iz = iz_cm4 * 10000.0 if math.isfinite(iz_cm4) else float("nan")

    a_rect = b * h
    a_circ = math.pi * d * d / 4.0
    i_rect = b * h**3 / 12.0
    i_circ = math.pi * d**4 / 64.0

    area_circular = math.isfinite(ax) and _rc14_relerr(ax, a_circ) <= 0.060 and _rc14_relerr(ax, a_rect) >= 0.100
    area_ratio_circular = math.isfinite(ax) and 0.735 <= ax / max(a_rect, 1e-9) <= 0.825

    i_avg = None
    if math.isfinite(iy) and math.isfinite(iz) and max(abs(iy), abs(iz)) > 0:
        if abs(iy - iz) / max(abs(iy), abs(iz), 1e-9) <= 0.060:
            i_avg = 0.5 * (iy + iz)
    inertia_circular = i_avg is not None and _rc14_relerr(i_avg, i_circ) <= 0.085 and _rc14_relerr(i_avg, i_rect) >= 0.150
    inertia_ratio_circular = i_avg is not None and 0.535 <= i_avg / max(i_rect, 1e-9) <= 0.645

    # Two independent indicators, or a very strong area/inertia match, are required.
    score = int(area_circular or area_ratio_circular) + int(inertia_circular or inertia_ratio_circular)
    return score >= 2 or (area_circular and inertia_circular)


_rc14_prev_infer_is_circular = ColumnDesigner.infer_is_circular

def _rc14_infer_is_circular(self, row, b_mm: float, h_mm: float) -> bool:
    try:
        name = str(row.get("name", "") or "").lower()
        mat = str(row.get("material", "") or "").lower()
        if any(k in name for k in ["circ", "circular", "ø", "phi", "diam", "diameter"]):
            return abs(float(b_mm) - float(h_mm)) / max(float(b_mm), float(h_mm), 1e-9) <= 0.05
        if any(k in mat for k in ["circ", "circular"]):
            return abs(float(b_mm) - float(h_mm)) / max(float(b_mm), float(h_mm), 1e-9) <= 0.05
    except Exception:
        pass
    try:
        if _rc14_infer_circular_from_geometry(row, b_mm, h_mm):
            return True
    except Exception:
        pass
    try:
        return bool(_rc14_prev_infer_is_circular(self, row, b_mm, h_mm))
    except Exception:
        return False

ColumnDesigner.infer_is_circular = _rc14_infer_is_circular


# ---------------------------------------------------------------------------
# Circular reinforcement layouts and section response
# ---------------------------------------------------------------------------

@dataclass
class CircularLayout:
    phi_long_mm: float
    phi_st_mm: float
    n_total: int
    b_mm: float
    h_mm: float
    cover_mm: float

    @property
    def phi_corner_mm(self) -> float:
        return float(self.phi_long_mm)

    @property
    def phi_face_mm(self) -> float:
        return float(self.phi_long_mm)

    @property
    def n_bars_y(self) -> int:
        return max(2, int(math.ceil(self.n_total / 4.0)) + 1)

    @property
    def n_bars_z(self) -> int:
        return max(2, int(math.ceil(self.n_total / 4.0)) + 1)

    @property
    def as_prov_mm2(self) -> float:
        return int(self.n_total) * bar_area_mm2(self.phi_long_mm)

    @property
    def layout_type(self) -> str:
        return "circular"

    @property
    def description(self) -> str:
        return f"{int(self.n_total)}Ø{int(self.phi_long_mm)} distribuídos no perímetro"

    def clear_spacing_ok(self, agg_mm: float = 20.0, min_clear_mm: float = 20.0) -> bool:
        d = min(float(self.b_mm), float(self.h_mm))
        r = d / 2.0 - float(self.cover_mm) - float(self.phi_st_mm) - float(self.phi_long_mm) / 2.0
        if r <= 0:
            return False
        clear_arc = 2.0 * math.pi * r / max(int(self.n_total), 1) - float(self.phi_long_mm)
        req = max(float(min_clear_mm), float(self.phi_long_mm), float(agg_mm) + 5.0)
        return clear_arc >= req


def _rc14_circular_bar_points(layout):
    d = min(float(layout.b_mm), float(layout.h_mm))
    phi = float(layout.phi_long_mm)
    r = d / 2.0 - float(layout.cover_mm) - float(layout.phi_st_mm) - phi / 2.0
    n = max(6, int(layout.n_total))
    pts = []
    for i in range(n):
        # start at top, then distribute clockwise. This gives stable DXF/report output.
        ang = math.pi / 2.0 - 2.0 * math.pi * i / n
        pts.append((float(r * math.cos(ang)), float(r * math.sin(ang)), phi))
    return pts


_rc14_prev_layout_bar_points = globals().get("_layout_bar_points_v45")

def _layout_bar_points_v45(layout):
    if isinstance(layout, CircularLayout) or bool(getattr(layout, "is_circular", False)):
        return _rc14_circular_bar_points(layout)
    return _rc14_prev_layout_bar_points(layout)

globals()["_layout_bar_points_v45"] = _layout_bar_points_v45


def _rc14_section_response(self, layout, n_ed_kN: float, angle_rad: float, c_mm: float, fcd: float, fyd: float, Es: float):
    """Section response with an explicit circular concrete mask when required."""
    if not (isinstance(layout, CircularLayout) or bool(getattr(layout, "is_circular", False))):
        return _section_response_v45(self, layout, n_ed_kN, angle_rad, c_mm, fcd, fyd, Es)

    eps_cu = 0.0035
    pts = _layout_bar_points_v45(layout)
    ca = math.cos(angle_rad)
    sa = math.sin(angle_rad)

    def ucoord(y, z):
        return y * ca + z * sa

    d = min(float(layout.b_mm), float(layout.h_mm))
    radius = d / 2.0
    u_max = radius
    u_na = u_max - float(c_mm)
    ny = max(14, int(d / 28.0))
    nz = max(14, int(d / 28.0))
    dy = d / ny
    dz = d / nz
    dA = dy * dz
    N = My = Mz = 0.0
    for iy in range(ny):
        y = -radius + (iy + 0.5) * dy
        for iz in range(nz):
            z = -radius + (iz + 0.5) * dz
            if y*y + z*z > radius*radius:
                continue
            u = ucoord(y, z)
            if u <= u_na:
                continue
            eps = eps_cu * (u - u_na) / max(float(c_mm), 1e-9)
            sig = 0.0 if eps <= 0.0 else min(float(fcd), float(fcd) * eps / 0.002)
            Fc = sig * dA
            N += Fc
            My += Fc * z
            Mz += Fc * y
    for y, z, phi in pts:
        u = ucoord(y, z)
        eps_s = eps_cu * (u - u_na) / max(float(c_mm), 1e-9)
        sig_s = max(-float(fyd), min(float(fyd), float(Es) * eps_s))
        Fs = sig_s * bar_area_mm2(phi)
        N += Fs
        My += Fs * z
        Mz += Fs * y
    return N / 1000.0, abs(My) / 1e6, abs(Mz) / 1e6

ColumnDesigner.section_response = _rc14_section_response


# ---------------------------------------------------------------------------
# Automatic reinforcement catalogue policy
# ---------------------------------------------------------------------------

def _rc14_layout_corner_phi(layout):
    try:
        return float(getattr(layout, "phi_corner_mm"))
    except Exception:
        try:
            return float(getattr(layout, "phi_long_mm"))
        except Exception:
            return 0.0


def _rc14_layout_face_phi(layout):
    try:
        return float(getattr(layout, "phi_face_mm"))
    except Exception:
        try:
            return float(getattr(layout, "phi_long_mm"))
        except Exception:
            return 0.0


def _rc14_practical_layout_score(layout, as_target: float, b_mm: float, h_mm: float):
    """Rank layouts for normal building-column detailing.

    Automatic search excludes Ø25/Ø32. The score favours Ø12/Ø16 corner bars,
    allows Ø10 at the corners for small/light columns only, and uses Ø10+ face
    bars for distribution along the faces.
    """
    asprov = float(getattr(layout, "as_prov_mm2", 0.0) or 0.0)
    n = int(getattr(layout, "n_total", 999) or 999)
    pc = _rc14_layout_corner_phi(layout)
    pf = _rc14_layout_face_phi(layout)
    phi_max = max(pc, pf)
    excess = max(0.0, asprov - float(as_target or 0.0))
    deficit = max(0.0, float(as_target or 0.0) - asprov)
    ac = max(float(b_mm or 0.0) * float(h_mm or 0.0), 1.0)
    small_light = (min(float(b_mm or 0.0), float(h_mm or 0.0)) <= 300.0 and float(as_target or 0.0) <= max(700.0, 0.0045 * ac))

    # Hard practical exclusion for automatic catalogue items above Ø20.
    p_forbidden = 1_000_000.0 if phi_max > 20.0 + 1e-9 else 0.0
    # Preference policy for corner bars.
    p_corner10 = 0.0 if (pc <= 10.0 + 1e-9 and small_light) else (1800.0 if pc <= 10.0 + 1e-9 else 0.0)
    p_corner20 = 260.0 if pc >= 20.0 - 1e-9 else 0.0
    p_corner_preferred = 0.0 if 12.0 - 1e-9 <= pc <= 16.0 + 1e-9 else 140.0
    # Avoid very mixed arrangements unless they solve a real As demand.
    p_mixed = abs(pc - pf) * 70.0
    imbalance = abs(int(getattr(layout, "n_bars_y", 2)) - int(getattr(layout, "n_bars_z", 2)))
    p_many = max(0, n - 16) * 25.0
    return (p_forbidden, deficit, p_corner10 + p_corner20 + p_corner_preferred + p_mixed, excess / 80.0, p_many, imbalance, n, asprov)

# Override the score used by design routines and structuralcodes candidate sorting.
_v56_layout_score = _rc14_practical_layout_score


def _rc14_build_candidate_layouts(self, b_mm, h_mm, is_circular=False):
    """Practical automatic catalogue with Ø10/Ø12/Ø16/Ø20 only."""
    key = ("rc14", round(float(b_mm), 1), round(float(h_mm), 1), round(float(self.cover_mm), 1), bool(is_circular))
    if key in self._layout_cache:
        return self._layout_cache[key]

    layouts = []
    seen = set()

    def _add(ly):
        try:
            if _rc14_layout_phi_max(ly) > 20.0 + 1e-9:
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
                sig = (type(ly).__name__, round(float(getattr(ly, "as_prov_mm2", 0.0)), 1), int(getattr(ly, "n_total", 0)), _rc14_layout_corner_phi(ly), _rc14_layout_face_phi(ly))
            if sig in seen:
                return
            seen.add(sig)
            layouts.append(ly)
        except Exception:
            return

    if is_circular:
        d = min(float(b_mm), float(h_mm))
        for phi in [10.0, 12.0, 16.0, 20.0]:
            phi_st = self.choose_stirrup(phi)
            # Common circular-column arrangements; includes larger counts to avoid Ø25/Ø32.
            for n in [6, 8, 10, 12, 14, 16, 18, 20, 24, 28]:
                ly = CircularLayout(phi, phi_st, n, d, d, self.cover_mm)
                _add(ly)
        layouts.sort(key=lambda ly: _rc14_practical_layout_score(ly, 0.0, b_mm, h_mm))
        self._layout_cache[key] = layouts
        return layouts

    max_y, max_z = self.max_bars_per_face(b_mm, h_mm, is_circular=False)
    max_y = max(2, int(max_y))
    max_z = max(2, int(max_z))
    corner_diams = [10.0, 12.0, 16.0, 20.0]
    face_diams = [10.0, 12.0, 16.0, 20.0]

    # Corner-only and mixed alternatives.
    for pc in corner_diams:
        _add(MixedLayout(pc, pc, 0, 0, b_mm, h_mm, self.cover_mm, self.choose_stirrup(pc)))
    for pc in corner_diams:
        for pf in face_diams:
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
                    # allow more perimeter bars so Ø20 can replace former Ø25/Ø32 solutions.
                    if ly.n_total > 28:
                        continue
                    _add(ly)

    # Uniform legacy alternatives, filtered to Ø20 max.
    try:
        for ly in list(_old_build_candidate_layouts_v45_base(self, b_mm, h_mm, is_circular=False)):
            if int(getattr(ly, "n_total", 0)) <= 28 and _rc14_layout_phi_max(ly) <= 20.0 + 1e-9:
                _add(ly)
    except Exception:
        pass

    layouts.sort(key=lambda ly: _rc14_practical_layout_score(ly, 0.0, b_mm, h_mm))
    self._layout_cache[key] = layouts
    return layouts

ColumnDesigner.build_candidate_layouts = _rc14_build_candidate_layouts


# Keep the base designer catalogue aligned with the automatic policy.
_rc14_prev_designer_init = ColumnDesigner.__init__

def _rc14_designer_init(self, *args, **kwargs):
    _rc14_prev_designer_init(self, *args, **kwargs)
    try:
        self.long_diams = [10.0, 12.0, 16.0, 20.0]
    except Exception:
        pass

ColumnDesigner.__init__ = _rc14_designer_init


# ---------------------------------------------------------------------------
# Result-level annotation and column-line rationalisation
# ---------------------------------------------------------------------------

_rc14_prev_design_one = ColumnDesigner.design_one

def _rc14_design_one(self, row, prebuilt_candidates=None):
    is_circ = False
    try:
        b_mm = cm_to_mm(row.get("hy", 0.0))
        h_mm = cm_to_mm(row.get("hz", 0.0))
        ax = safe_float(row.get("ax", float("nan"))) * 100.0
        if b_mm <= 0 and math.isfinite(ax) and ax > 0:
            b_mm = math.sqrt(ax)
        if h_mm <= 0:
            h_mm = b_mm
        is_circ = bool(self.infer_is_circular(row, b_mm, h_mm))
    except Exception:
        is_circ = False
    out = _rc14_prev_design_one(self, row, prebuilt_candidates=prebuilt_candidates)
    if isinstance(out, dict):
        out["section_shape"] = "circular" if is_circ else "rectangular"
        out["circular_geometry_detected"] = "Sim" if is_circ else "Não"
        if out.get("phi_long_mm") and float(out.get("phi_long_mm") or 0.0) > 20.0:
            out["warning_reason"] = (str(out.get("warning_reason", "") or "") + "; automatic catalogue should not select Ø25/Ø32 in RC14").strip("; ")
    return out

ColumnDesigner.design_one = _rc14_design_one


def _rc14_layout_phi_max(layout):
    vals = []
    for attr in ["phi_long_mm", "phi_corner_mm", "phi_face_mm"]:
        try:
            v = float(getattr(layout, attr))
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    return max(vals) if vals else 0.0


def _rc14_as_with_corner(row, corner_phi):
    face_phi = safe_float(row.get("phi_face_mm", row.get("phi_long_mm", corner_phi)), corner_phi)
    n_total = int(safe_float(row.get("n_total", 4), 4))
    n_face = max(0, n_total - 4)
    return 4.0 * bar_area_mm2(corner_phi) + n_face * bar_area_mm2(face_phi)


def _rc14_solution_with_corner(row, corner_phi):
    face_phi = safe_float(row.get("phi_face_mm", row.get("phi_long_mm", corner_phi)), corner_phi)
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


def _rc14_rationalise_summary(summary):
    if summary is None or getattr(summary, "empty", True):
        return summary
    out = summary.copy()
    if "Prumada" not in out.columns:
        out["Prumada"] = out.apply(_rc12_prumada, axis=1) if "_rc12_prumada" in globals() else out.get("name", "")
    if "Piso" not in out.columns:
        out["Piso"] = out.apply(_rc12_storey, axis=1) if "_rc12_storey" in globals() else out.get("story", "")
    out["_section_signature_rc14"] = out.apply(_rc12_section_signature, axis=1) if "_rc12_section_signature" in globals() else out.apply(lambda r: f"{r.get('b_cm','')}x{r.get('h_cm','')}|{r.get('material','')}", axis=1)
    out["Solução local"] = out.apply(_rc13_solution_value, axis=1) if "_rc13_solution_value" in globals() else out.get("solucao_completa", out.get("solucao", ""))
    out["As local [mm²]"] = out.apply(_rc13_as_value, axis=1) if "_rc13_as_value" in globals() else out.get("as_prov_mm2", 0.0)
    out["Solução adoptada"] = out.get("Solução adoptada", out["Solução local"])
    out["Critério de uniformização"] = out.get("Critério de uniformização", "Solução local mantida.")
    out["Corner-bar policy"] = "Local corner bars maintained."

    for _, idxs in out.groupby(["Prumada", "_section_signature_rc14"], dropna=False).groups.items():
        idxs = list(idxs)
        if len(idxs) <= 1:
            continue
        grp = out.loc[idxs]
        # Circular sections: keep uniform perimeter bar diameter where practical.
        is_circ_group = grp.get("section_shape", pd.Series([""]*len(grp), index=grp.index)).astype(str).str.lower().str.contains("circ", na=False).any()
        if is_circ_group:
            max_phi = float(grp.get("phi_long_mm", pd.Series([0]*len(grp), index=grp.index)).map(lambda v: safe_float(v, 0.0)).max())
            max_phi = min(max_phi, 20.0)
            for idx in idxs:
                local_as = float(out.at[idx, "As local [mm²]"] or 0.0)
                n_total = int(safe_float(out.at[idx, "n_total"] if "n_total" in out.columns else 0, 0))
                adopted_as = n_total * bar_area_mm2(max_phi) if n_total > 0 else local_as
                ratio = adopted_as / max(local_as, 1e-9)
                if ratio <= 1.75:
                    sol = _rc14_solution_with_corner(out.loc[idx], max_phi)
                    out.at[idx, "Solução adoptada"] = sol
                    out.at[idx, "Critério de uniformização"] = "Diâmetro perimetral uniformizado na mesma prumada/secção circular."
                    out.at[idx, "Corner-bar policy"] = f"Circular perimeter bars rationalised to Ø{int(max_phi)}."
                    for c in ["Solução", "solucao", "solucao_completa"]:
                        if c in out.columns:
                            out.at[idx, c] = sol
                else:
                    out.at[idx, "Corner-bar policy"] = "Local perimeter bars maintained to avoid excessive reinforcement."
            continue

        # Rectangular/square sections: keep corner bars consistent where practical.
        pc_series = grp.get("phi_corner_mm", grp.get("phi_long_mm", pd.Series([0]*len(grp), index=grp.index))).map(lambda v: safe_float(v, 0.0))
        governing_pc = min(20.0, float(pc_series.max() or 0.0))
        if governing_pc <= 0:
            continue
        # First try full arrangement uniformisation if not wasteful.
        max_idx = grp["As local [mm²]"].astype(float).idxmax()
        max_as = float(out.at[max_idx, "As local [mm²]"] or 0.0)
        max_sol = str(out.at[max_idx, "Solução local"] or "")
        for idx in idxs:
            local_as = float(out.at[idx, "As local [mm²]"] or 0.0)
            full_ratio = max_as / max(local_as, 1e-9)
            corner_as = _rc14_as_with_corner(out.loc[idx], governing_pc)
            corner_ratio = corner_as / max(local_as, 1e-9)
            if max_sol and full_ratio <= 1.35:
                out.at[idx, "Solução adoptada"] = max_sol
                out.at[idx, "Critério de uniformização"] = "Solução completa uniformizada com o tramo governante da mesma prumada/secção."
                out.at[idx, "Corner-bar policy"] = f"Full arrangement rationalised; corner bars Ø{int(governing_pc)}."
                for c in ["Solução", "solucao", "solucao_completa"]:
                    if c in out.columns:
                        out.at[idx, c] = max_sol
            elif corner_ratio <= 1.75:
                sol = _rc14_solution_with_corner(out.loc[idx], governing_pc)
                out.at[idx, "Solução adoptada"] = sol
                out.at[idx, "Critério de uniformização"] = "Varões de canto uniformizados na prumada; distribuição de face local mantida."
                out.at[idx, "Corner-bar policy"] = f"Corner bars rationalised to Ø{int(governing_pc)} within this column line/section."
                for c in ["Solução", "solucao", "solucao_completa"]:
                    if c in out.columns:
                        out.at[idx, c] = sol
            else:
                out.at[idx, "Critério de uniformização"] = "Solução local mantida para evitar excesso de armadura."
                out.at[idx, "Corner-bar policy"] = "Local corner bars maintained because uniformisation would be excessive."
    return out.drop(columns=["_section_signature_rc14"], errors="ignore")

# Override RC13 summary rationalisation.
def _rc14_build_summary(self, results):
    base = _rc13_prev_build_summary(self, results) if "_rc13_prev_build_summary" in globals() and callable(_rc13_prev_build_summary) else pd.DataFrame()
    return _rc14_rationalise_summary(base)

ColumnsEC2App.build_summary_by_member = _rc14_build_summary


# ---------------------------------------------------------------------------
# Technical English wording additions
# ---------------------------------------------------------------------------
try:
    _RC13_EN_TERMS.update({
        "Diâmetro perimetral uniformizado na mesma prumada/secção circular.": "Perimeter bar diameter rationalised within the same circular column line/section.",
        "Solução completa uniformizada com o tramo governante da mesma prumada/secção.": "Full reinforcement arrangement rationalised to match the governing segment of the same column line/section.",
        "Varões de canto uniformizados na prumada; distribuição de face local mantida.": "Corner bars rationalised within the column line; local face-bar distribution retained.",
        "Solução local mantida para evitar excesso de armadura.": "Local reinforcement arrangement retained to avoid excessive over-reinforcement.",
        "distribuídos no perímetro": "evenly distributed around the perimeter",
        "distribuídos nas faces": "distributed along the faces",
        "Varões de canto": "Corner bars",
        "varões de canto": "corner bars",
        "Diâmetro perimetral": "perimeter bar diameter",
        "secção circular": "circular section",
        "circular_geometry_detected": "circular_geometry_detected",
        "section_shape": "section_shape",
        "Solução adoptada": "Adopted reinforcement arrangement",
        "Critério de uniformização": "Rationalisation criterion",
        "As local [mm²]": "Local As [mm²]",
        "Solução local": "Local reinforcement arrangement",
        "estribos": "links",
    })
except Exception:
    pass

# Make language hook refresh with new report text and tables.
_prev_v092_hook_rc14 = globals().get("_v092_apply_language_title")
def _v092_apply_language_title(app):
    try:
        if callable(_prev_v092_hook_rc14):
            _prev_v092_hook_rc14(app)
    except Exception:
        pass
    try:
        app.apply_language()
    except Exception:
        pass

# Circular layouts need explicit signatures/descriptions for cache and reports.
_rc14_prev_v56_layout_signature = globals().get("_v56_layout_signature")
def _v56_layout_signature(layout):
    if isinstance(layout, CircularLayout):
        return (
            "circular",
            round(float(layout.b_mm), 1), round(float(layout.h_mm), 1), round(float(layout.cover_mm), 1),
            round(float(layout.phi_long_mm), 3), int(layout.n_total), round(float(layout.phi_st_mm), 3),
        )
    if callable(_rc14_prev_v56_layout_signature):
        return _rc14_prev_v56_layout_signature(layout)
    return (type(layout).__name__, round(float(getattr(layout, "as_prov_mm2", 0.0)), 1), int(getattr(layout, "n_total", 0)))

globals()["_v56_layout_signature"] = _v56_layout_signature

_rc14_prev_v56_layout_description = globals().get("_v56_layout_description")
def _v56_layout_description(layout):
    if isinstance(layout, CircularLayout):
        return layout.description
    if callable(_rc14_prev_v56_layout_description):
        return _rc14_prev_v56_layout_description(layout)
    return str(getattr(layout, "description", ""))

globals()["_v56_layout_description"] = _v56_layout_description
