# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC21 — stack-level reinforcement optimiser.

RC21 changes the reinforcement rationalisation objective:

- a column line is optimised as a vertical stack, not as independent storeys;
- equal sections in the same stack are strongly encouraged to use the same
  practical cage;
- section transitions keep the dominant bar diameter where this is verified and
  not disproportionate;
- circular-to-rectangular transitions are translated into explicit corner/face
  layouts instead of copying the circular wording blindly;
- failed local attempts are clearly marked as non-adoptable.
"""

from dataclasses import dataclass
import math
import re
import pandas as pd

APP_VERSION = "v0.9 RC21 Modular"

_RC21_SAME_SECTION_CHANGE_PENALTY = 850.0
_RC21_SECTION_CHANGE_DIAM_PENALTY = 220.0
_RC21_SECTION_CHANGE_COUNT_PENALTY = 28.0
_RC21_MAX_OPTIONS_PER_ROW = 28
_RC21_UTIL_LIMIT = 1.000 + 1e-9


@dataclass(frozen=True)
class _RC21Option:
    text: str
    kind: str
    as_mm2: float
    util: float
    n_total: int
    phi_corner: float
    phi_face: float
    ey: int = 0  # bars per face with length b_cm, total contribution = 2*ey
    ez: int = 0  # bars per face with length h_cm, total contribution = 2*ez
    source: str = "shortlist"

    @property
    def face_total(self) -> int:
        return max(0, 2 * int(self.ey) + 2 * int(self.ez))

    @property
    def signature(self):
        if self.kind == "circular":
            return ("circular", int(self.n_total), int(round(self.phi_corner)))
        return ("rect", int(round(self.phi_corner)), int(round(self.phi_face)), int(self.ey), int(self.ez))


def _rc21_num(x, default=0.0):
    try:
        v = safe_float(x, default) if "safe_float" in globals() else float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _rc21_text(x, default=""):
    try:
        s = str(x if x is not None else "").strip()
        return s if s else default
    except Exception:
        return default


def _rc21_bar_area(phi):
    try:
        return bar_area_mm2(float(phi))
    except Exception:
        return math.pi * float(phi) ** 2 / 4.0


def _rc21_is_failed(row) -> bool:
    try:
        eta = _rc18_eta(row) if "_rc18_eta" in globals() else _rc21_num(row.get("utilizacao"), 999.0)
        if eta > 1.0 + 1e-9:
            return True
    except Exception:
        pass
    txt = " ".join(_rc21_text(row.get(c)) for c in ["Estado", "estado_global", "status", "estado_resistente"]).lower()
    return any(k in txt for k in ["falha", "failure", "não conforme", "not compliant"])


def _rc21_is_circular_row(row) -> bool:
    try:
        if "_rc19_is_circular_row" in globals():
            return bool(_rc19_is_circular_row(row))
        if "_rc18_is_circular_row" in globals():
            return bool(_rc18_is_circular_row(row))
    except Exception:
        pass
    txt = " ".join(_rc21_text(row.get(c)) for c in ["section_shape", "Secção [cm]", "Section [cm]", "section_label", "layout_type"]).lower()
    return ("circ" in txt) or ("d=" in txt)


def _rc21_dims_cm(row):
    b = _rc21_num(row.get("b_cm", row.get("hy", 0.0)), 0.0)
    h = _rc21_num(row.get("h_cm", row.get("hz", 0.0)), 0.0)
    if b <= 0.0 or h <= 0.0:
        txt = _rc21_text(row.get("Secção [cm]", row.get("Section [cm]", "")))
        m = re.search(r"(\d+(?:[\.,]\d+)?)\s*[xX]\s*(\d+(?:[\.,]\d+)?)", txt)
        if m:
            b = float(m.group(1).replace(",", ".")); h = float(m.group(2).replace(",", "."))
        else:
            m = re.search(r"D\s*=\s*(\d+(?:[\.,]\d+)?)", txt, flags=re.I)
            if m:
                b = h = float(m.group(1).replace(",", "."))
    return b, h


def _rc21_section_signature(row):
    try:
        if "_rc18_section_signature" in row.index:
            s = _rc21_text(row.get("_rc18_section_signature"))
            if s:
                return s
    except Exception:
        pass
    try:
        if "_rc18_section_signature" in globals():
            return _rc18_section_signature(row)
    except Exception:
        pass
    b, h = _rc21_dims_cm(row)
    mat = _rc21_text(row.get("material", ""))
    if _rc21_is_circular_row(row):
        return f"circular|D={max(b,h):.1f}|{mat}"
    return f"rectangular|{b:.1f}x{h:.1f}|{mat}"


def _rc21_story_key(row):
    try:
        if "_rc18_story_sort_tuple" in globals() and "_rc18_sort_key" in globals():
            return _rc18_sort_key(_rc18_story_sort_tuple(row))
    except Exception:
        pass
    txt = _rc21_text(row.get("Piso", row.get("story", row.get("Storey", ""))))
    m = re.search(r"-?\d+(?:[\.,]\d+)?", txt)
    val = float(m.group(0).replace(",", ".")) if m else 0.0
    return (0, val, txt)


def _rc21_allocate_extras_rect(n_total: int, b_cm: float, h_cm: float):
    """Convert a perimeter count into explicit bars per opposite pair of faces."""
    extras = max(0, int(round(n_total)) - 4)
    ey = ez = 0
    # Add bars in opposite pairs. Prefer the longer face when only one pair is
    # needed; then balance the distribution.
    pairs = extras // 2
    if pairs <= 0:
        return 0, 0
    longer_is_h = h_cm >= b_cm
    for _ in range(pairs):
        if longer_is_h:
            if ez <= ey:
                ez += 1
            else:
                ey += 1
        else:
            if ey <= ez:
                ey += 1
            else:
                ez += 1
    return ey, ez


def _rc21_make_option_from_parts(desc, as_mm2, util, n_total, pc, pf=None, ey=0, ez=0, kind="rect", source="shortlist"):
    pc = float(pc or 0.0)
    pf = float(pf if pf is not None and pf > 0 else pc)
    if as_mm2 <= 0.0:
        as_mm2 = (int(n_total) * _rc21_bar_area(pc)) if kind == "circular" else 4 * _rc21_bar_area(pc) + (2 * int(ey) + 2 * int(ez)) * _rc21_bar_area(pf)
    if n_total <= 0:
        n_total = int(4 + 2 * int(ey) + 2 * int(ez)) if kind != "circular" else 6
    return _RC21Option(_rc21_text(desc), kind, float(as_mm2), float(util), int(n_total), pc, pf, int(ey), int(ez), source)


def _rc21_parse_solution_text(desc, as_mm2=0.0, util=999.0, row=None):
    """Parse the program's shortlist wording into a normalised option."""
    s = _rc21_text(desc)
    s0 = s
    s = s.replace("φ", "Ø").replace("ø", "Ø")
    b_cm, h_cm = _rc21_dims_cm(row) if row is not None else (0.0, 0.0)
    row_is_circ = _rc21_is_circular_row(row) if row is not None else False

    # nØphi perimeter/circular alternative.
    m = re.search(r"(\d+)\s*Ø\s*(\d+(?:[\.,]\d+)?)\s*(?:distribu[ií]dos?|no)\s+(?:no\s+)?per[ií]metro", s, flags=re.I)
    if m:
        n = int(m.group(1)); phi = float(m.group(2).replace(",", "."))
        if row_is_circ:
            return _rc21_make_option_from_parts(s0, as_mm2, util, n, phi, phi, 0, 0, "circular")
        ey, ez = _rc21_allocate_extras_rect(n, b_cm, h_cm)
        return _rc21_make_option_from_parts(s0, as_mm2, util, n, phi, phi, ey, ez, "rect_from_perimeter")

    # 4Øpc (cantos) + ... faces b/h.
    m = re.search(r"4\s*Ø\s*(\d+(?:[\.,]\d+)?)\s*(?:\([^)]*cantos[^)]*\)|nos\s+cantos|cantos)?", s, flags=re.I)
    if m:
        pc = float(m.group(1).replace(",", "."))
        pf = pc
        ey = ez = 0
        for mf in re.finditer(r"(\d+)\s*Ø\s*(\d+(?:[\.,]\d+)?)\s*nas\s+faces\s*([bh])", s, flags=re.I):
            n_face_total = int(mf.group(1)); p = float(mf.group(2).replace(",", ".")); face = mf.group(3).lower()
            pf = p
            if face == "b":
                ey += max(0, int(round(n_face_total / 2.0)))
            else:
                ez += max(0, int(round(n_face_total / 2.0)))
        for mf in re.finditer(r"(\d+)\s*Ø\s*(\d+(?:[\.,]\d+)?)\s*por\s+face\s+de\s+(\d+(?:[\.,]\d+)?)", s, flags=re.I):
            n_pf = int(mf.group(1)); p = float(mf.group(2).replace(",", ".")); dim = float(mf.group(3).replace(",", "."))
            pf = p
            if abs(dim - b_cm) <= abs(dim - h_cm):
                ey = max(ey, n_pf)
            else:
                ez = max(ez, n_pf)
        n_total = 4 + 2 * ey + 2 * ez
        return _rc21_make_option_from_parts(s0, as_mm2, util, n_total, pc, pf, ey, ez, "rect")

    return None


def _rc21_parse_shortlist(row):
    txt = _rc21_text(row.get("shortlist_text", ""))
    opts = []
    if txt:
        chunks = re.split(r"\s*\|\|\s*", txt)
        for ch in chunks:
            m = re.search(r"^\s*\d+\)\s*(.*?)\s*\|\s*As\s*=\s*(\d+(?:[\.,]\d+)?)\s*mm", ch, flags=re.I)
            if not m:
                continue
            desc = m.group(1).strip()
            asv = float(m.group(2).replace(",", "."))
            mu = re.search(r"util\s*=\s*(\d+(?:[\.,]\d+)?)", ch, flags=re.I)
            util = float(mu.group(1).replace(",", ".")) if mu else 999.0
            ok = bool(re.search(r"(?:^|\|)\s*OK\s*$", ch.strip(), flags=re.I)) or (util <= _RC21_UTIL_LIMIT and "não verificada" not in ch.lower())
            if not ok:
                continue
            opt = _rc21_parse_solution_text(desc, asv, util, row)
            if opt is not None:
                opts.append(opt)

    # Current local/adopted solution as fallback if verified.
    if not _rc21_is_failed(row):
        desc = _rc21_text(row.get("Solução local", row.get("Solução adoptada", row.get("solucao", ""))))
        asv = _rc21_num(row.get("As local [mm²]", row.get("as_prov_mm2", row.get("As adoptada [mm²]", 0.0))), 0.0)
        util = _rc21_num(row.get("η_NMyMz", row.get("utilizacao", 999.0)), 999.0)
        opt = _rc21_parse_solution_text(desc, asv, util, row)
        if opt is None:
            pc = _rc21_num(row.get("phi_corner_mm", row.get("phi_long_mm", 12.0)), 12.0)
            pf = min(16.0, _rc21_num(row.get("phi_face_mm", pc), pc))
            if _rc21_is_circular_row(row):
                opt = _rc21_make_option_from_parts(desc, asv, util, int(_rc21_num(row.get("n_total", 6), 6)), pc, pc, 0, 0, "circular", "local")
            else:
                ey = int(round(_rc21_num(row.get("n_face_y_extra", 0), 0)))
                ez = int(round(_rc21_num(row.get("n_face_z_extra", 0), 0)))
                if ey == 0 and ez == 0:
                    n = int(round(_rc21_num(row.get("n_total", 4), 4)))
                    ey, ez = _rc21_allocate_extras_rect(n, *_rc21_dims_cm(row))
                opt = _rc21_make_option_from_parts(desc, asv, util, int(4 + 2 * ey + 2 * ez), pc, pf, ey, ez, "rect", "local")
        if opt is not None:
            opts.append(opt)

    # Reject options that create a disproportionate increase in a storey only
    # to make the stack uniform. This is the key guardrail against propagating a
    # heavy upper-storey cage into lightly loaded lower storeys.
    as_local_ref = _rc21_num(row.get("As local [mm²]", row.get("as_prov_mm2", row.get("As adoptada [mm²]", 0.0))), 0.0)
    local_failed = _rc21_is_failed(row)
    max_ratio = 1.65

    # Deduplicate by signature, keeping the lowest utilisation and then lowest area.
    best = {}
    for opt in opts:
        if opt.util > _RC21_UTIL_LIMIT:
            continue
        if (not local_failed) and as_local_ref > 0 and opt.as_mm2 / max(as_local_ref, 1e-9) > max_ratio:
            continue
        prev = best.get(opt.signature)
        if prev is None or (opt.util, opt.as_mm2) < (prev.util, prev.as_mm2):
            best[opt.signature] = opt
    out = list(best.values())
    out.sort(key=lambda o: _rc21_local_score(o))
    return out[:_RC21_MAX_OPTIONS_PER_ROW]


def _rc21_local_score(opt: _RC21Option):
    # Area is the primary economy criterion. Penalties guide the result away
    # from congested layouts without forcing larger bars unnecessarily.
    p = opt.as_mm2 / 6.0
    p += max(0, opt.n_total - 10) * 18.0
    p += max(0, opt.face_total - 4) * 26.0
    p += 75.0 if opt.phi_corner >= 20.0 - 1e-9 else 0.0
    p += 25.0 if opt.kind == "rect_from_perimeter" else 0.0
    p += max(0.0, 0.65 - min(opt.util, 0.65)) * 55.0  # avoid very oversized solutions
    return p


def _rc21_transition_score(prev: _RC21Option, curr: _RC21Option, same_section: bool):
    if prev is None:
        return 0.0
    if same_section:
        if prev.signature == curr.signature:
            return 0.0
        score = _RC21_SAME_SECTION_CHANGE_PENALTY
        score += abs(prev.phi_corner - curr.phi_corner) * 25.0
        score += abs(prev.n_total - curr.n_total) * 18.0
        return score
    # Section changes: keep the dominant diameter where reasonable, but do not
    # force the same number of bars or the same geometry.
    score = abs(prev.phi_corner - curr.phi_corner) * _RC21_SECTION_CHANGE_DIAM_PENALTY
    score += abs(prev.n_total - curr.n_total) * _RC21_SECTION_CHANGE_COUNT_PENALTY
    if prev.phi_corner == curr.phi_corner:
        score -= 120.0
    return max(0.0, score)


def _rc21_select_options_for_stack(group: pd.DataFrame):
    idxs = sorted(list(group.index), key=lambda i: _rc21_story_key(group.loc[i]))
    options = {i: _rc21_parse_shortlist(group.loc[i]) for i in idxs}
    # Rows without verified options are not part of the optimisation. They will
    # be marked explicitly as non-adoptable attempts.
    active = [i for i in idxs if options.get(i)]
    if not active:
        return {}
    dp = []
    back = []
    prev_active_idx = None
    for pos, idx in enumerate(active):
        row = group.loc[idx]
        opts = options[idx]
        sig = _rc21_section_signature(row)
        if pos == 0:
            dp.append([_rc21_local_score(o) for o in opts])
            back.append([-1 for _ in opts])
            prev_active_idx = idx
            continue
        prev_idx = active[pos - 1]
        prev_sig = _rc21_section_signature(group.loc[prev_idx])
        same_section = (sig == prev_sig)
        prev_opts = options[prev_idx]
        scores = []
        backs = []
        for o in opts:
            best_score = None
            best_j = -1
            for j, po in enumerate(prev_opts):
                sc = dp[pos - 1][j] + _rc21_transition_score(po, o, same_section) + _rc21_local_score(o)
                if best_score is None or sc < best_score:
                    best_score = sc; best_j = j
            scores.append(float(best_score if best_score is not None else _rc21_local_score(o)))
            backs.append(best_j)
        dp.append(scores); back.append(backs); prev_active_idx = idx
    # Backtrack.
    last_j = min(range(len(dp[-1])), key=lambda j: dp[-1][j])
    selected = {}
    for pos in reversed(range(len(active))):
        idx = active[pos]
        selected[idx] = options[idx][last_j]
        last_j = back[pos][last_j]
        if last_j < 0 and pos > 0:
            last_j = 0
    return selected


def _rc21_format_option_for_row(row, opt: _RC21Option, lang="pt"):
    b_cm, h_cm = _rc21_dims_cm(row)
    phi_st = int(round(_rc21_num(row.get("phi_st_mm", 8.0), 8.0)))
    s_st = _rc21_num(row.get("s_st_mm", 0.0), 0.0)
    if lang == "en":
        link = f"links Ø{phi_st}//{s_st:.0f} mm" if s_st > 0 else f"links Ø{phi_st}"
    else:
        link = f"estribos Ø{phi_st}//{s_st:.0f} mm" if s_st > 0 else f"estribos Ø{phi_st}"

    if opt.kind == "circular" or _rc21_is_circular_row(row):
        if lang == "en":
            return f"{int(opt.n_total)}Ø{int(opt.phi_corner)} perimeter bars; {link}", f"{int(opt.n_total)}Ø{int(opt.phi_corner)} perimeter bars", "-"
        return f"{int(opt.n_total)}Ø{int(opt.phi_corner)} no perímetro; {link}", f"{int(opt.n_total)}Ø{int(opt.phi_corner)} no perímetro", "-"

    if lang == "en":
        base = f"4Ø{int(opt.phi_corner)} corner bars"
    else:
        base = f"4Ø{int(opt.phi_corner)} nos cantos"
    parts = []
    if opt.ey > 0:
        if lang == "en":
            parts.append(f"{int(opt.ey)}Ø{int(opt.phi_face)} on each {b_cm:.0f} cm face")
        else:
            parts.append(f"{int(opt.ey)}Ø{int(opt.phi_face)} por face de {b_cm:.0f} cm")
    if opt.ez > 0:
        if lang == "en":
            parts.append(f"{int(opt.ez)}Ø{int(opt.phi_face)} on each {h_cm:.0f} cm face")
        else:
            parts.append(f"{int(opt.ez)}Ø{int(opt.phi_face)} por face de {h_cm:.0f} cm")
    add = " + ".join(parts) if parts else "-"
    sol = f"{base}; {link}" if not parts else f"{base} + {add}; {link}"
    return sol, base, add


def _rc21_apply_option(out, idx, opt: _RC21Option, criterion_pt, criterion_en, transition_note_pt="", transition_note_en=""):
    row = out.loc[idx]
    sol_pt, base_pt, add_pt = _rc21_format_option_for_row(row, opt, "pt")
    sol_en, base_en, add_en = _rc21_format_option_for_row(row, opt, "en")
    as_local = max(_rc21_num(out.at[idx, "As local [mm²]"] if "As local [mm²]" in out.columns else row.get("as_prov_mm2", opt.as_mm2), opt.as_mm2), 1e-9)
    excess = max(0.0, (opt.as_mm2 / as_local - 1.0) * 100.0)

    for c, v in {
        "Solução adoptada": sol_pt,
        "Adopted arrangement": sol_en,
        "Armadura base da prumada": base_pt,
        "Base column-line cage": base_en,
        "Reforço local": add_pt,
        "Local additional reinforcement": add_en,
        "As adoptada [mm²]": opt.as_mm2,
        "As adopted [mm²]": opt.as_mm2,
        "Excesso de aço [%]": excess,
        "Over-reinforcement [%]": excess,
        "Critério de uniformização": criterion_pt,
        "Rationalisation criterion": criterion_en,
        "Vertical rationalisation": "Sim" if (excess > 1e-6 or opt.source != "local") else "Não",
        "Vertical rationalisation applied": "Yes" if (excess > 1e-6 or opt.source != "local") else "No",
        "Taxa de armadura [%]": 100.0 * opt.as_mm2 / max(_rc19_area_row(row) if "_rc19_area_row" in globals() else 1.0, 1.0),
        "Reinforcement ratio [%]": 100.0 * opt.as_mm2 / max(_rc19_area_row(row) if "_rc19_area_row" in globals() else 1.0, 1.0),
        "N.º varões adicionais nas faces": opt.face_total,
        "Additional face bars": opt.face_total,
    }.items():
        out.at[idx, c] = v
    for c in ["Solução", "solucao", "solucao_completa", "layout_description"]:
        if c in out.columns:
            out.at[idx, c] = sol_pt
    for c, v in {
        "phi_corner_mm": opt.phi_corner,
        "phi_face_mm": opt.phi_face,
        "phi_long_mm": max(opt.phi_corner, opt.phi_face),
        "n_face_y_extra": opt.ey,
        "n_face_z_extra": opt.ez,
        "n_total": opt.n_total,
        "as_prov_mm2": opt.as_mm2,
        "utilizacao": opt.util,
        "η_NMyMz": opt.util,
        "eta_NMyMz": opt.util,
    }.items():
        if c in out.columns:
            out.at[idx, c] = v
    # The shortlist only provides verified candidates here. Keep global status as
    # warning if ELS/detailing require review, but mark resistant state as OK.
    if "estado_resistente" in out.columns:
        out.at[idx, "estado_resistente"] = "OK"
    if "Classificação construtiva" in out.columns or "_rc19_constructability_status" in globals():
        st_pt, st_en, note_pt, note_en = _rc19_constructability_status(out.loc[idx]) if "_rc19_constructability_status" in globals() else ("Normal", "Normal", "", "")
        out.at[idx, "Classificação construtiva"] = st_pt
        out.at[idx, "Constructability class"] = st_en
        out.at[idx, "Nota construtiva"] = note_pt
        out.at[idx, "Constructability note"] = note_en
    if transition_note_pt:
        old_pt = _rc21_text(out.at[idx, "Nota de continuidade"] if "Nota de continuidade" in out.columns else "")
        old_en = _rc21_text(out.at[idx, "Continuity note"] if "Continuity note" in out.columns else "")
        out.at[idx, "Nota de continuidade"] = (old_pt + "; " + transition_note_pt).strip("; ") if old_pt else transition_note_pt
        out.at[idx, "Continuity note"] = (old_en + "; " + transition_note_en).strip("; ") if old_en else transition_note_en


def _rc21_mark_non_adoptable(out, idx):
    row = out.loc[idx]
    best = _rc21_text(row.get("Solução local", row.get("Solução adoptada", row.get("solucao", ""))))
    asv = _rc21_num(row.get("As local [mm²]", row.get("as_prov_mm2", row.get("As adoptada [mm²]", 0.0))), 0.0)
    note_pt = "Melhor tentativa — NÃO ADOPTAR. A secção não verifica; aumentar a secção, rever esforços/comprimentos efectivos ou definir solução especial manual."
    note_en = "Best attempt — DO NOT ADOPT. The section does not verify; increase the section, review design actions/effective lengths or define a special manual solution."
    out.at[idx, "Solução adoptada"] = f"{note_pt} {best}".strip()
    out.at[idx, "Adopted arrangement"] = f"{note_en} {best}".strip()
    out.at[idx, "As adoptada [mm²]"] = asv
    out.at[idx, "As adopted [mm²]"] = asv
    out.at[idx, "Critério de uniformização"] = "Sem solução automática verificada para este tramo; a armadura indicada é apenas tentativa de cálculo."
    out.at[idx, "Rationalisation criterion"] = "No verified automatic solution for this segment; the shown reinforcement is a calculation attempt only."
    old_pt = _rc21_text(out.at[idx, "Nota de continuidade"] if "Nota de continuidade" in out.columns else "")
    old_en = _rc21_text(out.at[idx, "Continuity note"] if "Continuity note" in out.columns else "")
    out.at[idx, "Nota de continuidade"] = (old_pt + "; " + note_pt).strip("; ") if old_pt else note_pt
    out.at[idx, "Continuity note"] = (old_en + "; " + note_en).strip("; ") if old_en else note_en
    out.at[idx, "Classificação construtiva"] = "Não conforme"
    out.at[idx, "Constructability class"] = "Not compliant"
    out.at[idx, "Nota construtiva"] = note_pt
    out.at[idx, "Constructability note"] = note_en


def _rc21_stack_rationalise(schedule):
    if schedule is None or getattr(schedule, "empty", True):
        return schedule
    out = schedule.copy()
    # Ensure expected columns exist even if previous patches did not create them.
    defaults = {
        "Solução local": "", "As local [mm²]": 0.0, "Solução adoptada": "", "As adoptada [mm²]": 0.0,
        "Critério de uniformização": "", "Rationalisation criterion": "", "Nota de continuidade": "", "Continuity note": "",
        "Armadura base da prumada": "", "Base column-line cage": "", "Reforço local": "", "Local additional reinforcement": "",
    }
    for c, v in defaults.items():
        if c not in out.columns:
            out[c] = v
    try:
        out["_rc21_section_signature"] = out.apply(_rc21_section_signature, axis=1)
        out["_rc21_story_key"] = out.apply(_rc21_story_key, axis=1)
    except Exception:
        pass

    # Mark failures before optimisation; verified candidates can still replace a
    # local failure if the shortlist contains one.
    failed_idxs = set(i for i in out.index if _rc21_is_failed(out.loc[i]))

    for prumada, grp in out.groupby("Prumada", dropna=False, sort=False):
        selected = _rc21_select_options_for_stack(grp)
        ordered = sorted(list(grp.index), key=lambda i: _rc21_story_key(out.loc[i]))
        prev_idx = None
        for idx in ordered:
            if idx not in selected:
                if idx in failed_idxs:
                    _rc21_mark_non_adoptable(out, idx)
                continue
            opt = selected[idx]
            row = out.loc[idx]
            if prev_idx is not None:
                same_section = _rc21_section_signature(out.loc[prev_idx]) == _rc21_section_signature(row)
            else:
                same_section = False
            if same_section:
                crit_pt = "Solução optimizada por prumada: mesma secção com gaiola longitudinal uniforme sempre que verificada."
                crit_en = "Stack-level optimisation: equal section uses a uniform longitudinal cage whenever verified."
                note_pt = ""
                note_en = ""
            else:
                crit_pt = "Solução optimizada por prumada: diâmetro dominante mantido quando compatível; disposição ajustada à geometria da secção."
                crit_en = "Stack-level optimisation: dominant diameter kept when compatible; layout adjusted to the section geometry."
                note_pt = "Mudança de secção tratada por compatibilização geométrica da armadura; confirmar emendas/amarrações no desenho."
                note_en = "Section transition treated by geometric reinforcement compatibility; check laps/anchorage on drawings."
                if prev_idx is None:
                    note_pt = note_en = ""
            _rc21_apply_option(out, idx, opt, crit_pt, crit_en, note_pt, note_en)
            prev_idx = idx

    try:
        out = out.sort_values(["Prumada", "_rc21_story_key", "member"], kind="mergesort").reset_index(drop=True)
    except Exception:
        pass
    drop_cols = [c for c in ["_rc21_section_signature", "_rc21_story_key"] if c in out.columns]
    return out.drop(columns=drop_cols, errors="ignore")


# ---------------------------------------------------------------------------
# Publish RC21 schedule builder/export hooks
# ---------------------------------------------------------------------------

_rc21_prev_build_summary_by_member = ColumnsEC2App.build_summary_by_member
_rc21_prev_build_tramo_schedule = globals().get("_rc19_build_tramo_schedule", globals().get("_rc18_build_tramo_schedule", None))


def _rc21_build_summary_by_member(self, results: pd.DataFrame) -> pd.DataFrame:
    try:
        base = _rc21_prev_build_tramo_schedule(results) if callable(_rc21_prev_build_tramo_schedule) else _rc21_prev_build_summary_by_member(self, results)
    except RecursionError:
        base = _rc21_prev_build_summary_by_member(self, results)
    except Exception:
        base = _rc21_prev_build_summary_by_member(self, results)
    return _rc21_stack_rationalise(base)


ColumnsEC2App.build_summary_by_member = _rc21_build_summary_by_member


def _rc21_build_tramo_schedule(results: pd.DataFrame) -> pd.DataFrame:
    base = _rc21_prev_build_tramo_schedule(results) if callable(_rc21_prev_build_tramo_schedule) else pd.DataFrame()
    return _rc21_stack_rationalise(base)


_v682_build_tramo_schedule = _rc21_build_tramo_schedule
_v683_build_tramo_schedule = _rc21_build_tramo_schedule
_rc17_build_tramo_schedule = _rc21_build_tramo_schedule
_rc18_build_tramo_schedule = _rc21_build_tramo_schedule
_rc19_build_tramo_schedule = _rc21_build_tramo_schedule


_rc21_prev_write_excel = ColumnsEC2App._write_excel


def _rc21_write_excel(self, path: str):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc21_build_tramo_schedule(self.df_results)
            if hasattr(self, "tree_summary"):
                try:
                    self.show_df(self.tree_summary, self.df_summary)
                except Exception:
                    pass
    except Exception:
        pass
    return _rc21_prev_write_excel(self, path)


ColumnsEC2App._write_excel = _rc21_write_excel


_rc21_prev_export_dxf = ColumnsEC2App.export_dxf


def _rc21_export_dxf(self):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_summary = _rc21_build_tramo_schedule(self.df_results)
    except Exception:
        pass
    return _rc21_prev_export_dxf(self)


ColumnsEC2App.export_dxf = _rc21_export_dxf

try:
    _RC13_EN_TERMS.update({
        "Solução optimizada por prumada: mesma secção com gaiola longitudinal uniforme sempre que verificada.": "Stack-level optimisation: equal section uses a uniform longitudinal cage whenever verified.",
        "Solução optimizada por prumada: diâmetro dominante mantido quando compatível; disposição ajustada à geometria da secção.": "Stack-level optimisation: dominant diameter kept when compatible; layout adjusted to the section geometry.",
        "Mudança de secção tratada por compatibilização geométrica da armadura; confirmar emendas/amarrações no desenho.": "Section transition treated by geometric reinforcement compatibility; check laps/anchorage on drawings.",
        "Melhor tentativa — NÃO ADOPTAR. A secção não verifica; aumentar a secção, rever esforços/comprimentos efectivos ou definir solução especial manual.": "Best attempt — DO NOT ADOPT. The section does not verify; increase the section, review design actions/effective lengths or define a special manual solution.",
        "Sem solução automática verificada para este tramo; a armadura indicada é apenas tentativa de cálculo.": "No verified automatic solution for this segment; the shown reinforcement is a calculation attempt only.",
    })
except Exception:
    pass
