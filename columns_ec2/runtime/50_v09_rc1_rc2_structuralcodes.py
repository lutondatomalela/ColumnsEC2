# -*- coding: utf-8 -*-
# Auto-split from ColumnsEC2 v0.9 RC8.
# This module is executed in the shared runtime namespace by columns_ec2.runtime.loader.
# Keep execution order defined in columns_ec2/runtime/manifest.py.

APP_VERSION = "v0.9 RC1"
APP_XLSX_DESCRIPTION = (
    "Technical design and checking of reinforced concrete columns by column line and storey, including governing-case selection, "
    "N-My-Mz interaction, second-order effects, constructive detailing, technical reports and DXF column schedules. "
    "The PT engine remains the internal ColumnsEC2 engine; Eurocode 2:2004, Eurocode 2:2023 and fib Model Code 2010 use structuralcodes for the strict backend checks."
)


def _v091_force_prumada(row):
    """Column-line name used consistently in reports and exports."""
    for k in ["prumada", "Prumada", "name", "Name", "nome", "member"]:
        try:
            v = row.get(k, "")
            if str(v).strip() and str(v).strip().lower() not in ["nan", "none", "-"]:
                return str(v).strip()
        except Exception:
            pass
    return "-"


def _v091_sc_as_seed(self, n_ed_kN, my_ed_kNm, mz_ed_kNm, b_mm, h_mm, fyd, as_min):
    """As seed used only to order structuralcodes candidate layouts.

    This is not a normative verification and does not replace structuralcodes.
    It prevents the strict adapter from trying only very light layouts when
    the governing moments require much larger reinforcement.
    """
    try:
        seed = self.approx_required_as(n_ed_kN, my_ed_kNm, mz_ed_kNm, b_mm, h_mm, fyd, as_min)
    except Exception:
        z_y = max(0.80 * h_mm, 1e-9)
        z_z = max(0.80 * b_mm, 1e-9)
        seed = max(as_min,
                   0.10 * n_ed_kN * 1e3 / max(fyd, 1e-9)
                   + abs(my_ed_kNm) * 1e6 / max(0.87 * fyd * z_y, 1e-9)
                   + abs(mz_ed_kNm) * 1e6 / max(0.87 * fyd * z_z, 1e-9))
    return max(float(as_min), float(seed))


def _v091_layout_order_sc(candidates, as_seed, strategy="equilibrada"):
    strategy = str(strategy or "equilibrada").lower()
    if strategy.startswith("econ"):
        return sorted(candidates, key=lambda c: (float(c.as_prov_mm2), c.n_total, c.phi_long_mm))
    if strategy.startswith("rob"):
        # Robust: do not only start from the smallest area. Use stronger layouts early,
        # but the final choice is made after all tested layouts are evaluated.
        return sorted(candidates, key=lambda c: (-float(c.as_prov_mm2), c.n_total, c.phi_long_mm))
    # Balanced: start near the estimated need, then expand outwards.
    return sorted(candidates, key=lambda c: (abs(float(c.as_prov_mm2) - float(as_seed)), float(c.as_prov_mm2), c.n_total, c.phi_long_mm))


def _v091_pick_ok_candidate(ok_items, strategy="equilibrada"):
    """Selects the adopted solution among OK structuralcodes layouts."""
    strategy = str(strategy or "equilibrada").lower()
    if not ok_items:
        return None
    if strategy.startswith("econ"):
        return min(ok_items, key=lambda it: (it["as"], it["eta"], it["layout"].n_total, it["layout"].phi_long_mm))
    if strategy.startswith("rob"):
        return min(ok_items, key=lambda it: (it["eta"], it["as"], it["layout"].n_total, it["layout"].phi_long_mm))
    eta_target = float(globals().get("REBAR_TARGET_ETA_V64", 0.80))
    eta_min = float(globals().get("REBAR_ETA_MIN_V68", 0.70))
    eta_max = float(globals().get("REBAR_ETA_MAX_V68", 0.90))
    def key(it):
        eta = it["eta"]
        inside = 0 if eta_min <= eta <= eta_max else 1
        return (inside, abs(eta - eta_target), it["as"], it["layout"].n_total, it["layout"].phi_long_mm)
    return min(ok_items, key=key)


def _v091_shortlist_append(shortlist, ly, util=None, ok=False, note="", max_rows=80):
    """Keep the Excel shortlist informative but bounded."""
    if len(shortlist) < max_rows:
        shortlist.append({
            "solucao": f"{ly.n_total}Ø{int(ly.phi_long_mm)}",
            "as_prov_mm2": ly.as_prov_mm2,
            "utilizacao": "" if util is None or not math.isfinite(float(util)) else f"{float(util):.3f}",
            "status_short": "OK" if ok else "Falha",
            "failure_short": "" if ok else (note or "N-My-Mz"),
        })


def _strict_sc_design_one_v091(self, row: pd.Series, prebuilt_candidates=None):
    """Strict structuralcodes adapter with adaptive candidate search.

    The N-My-Mz capacity remains calculated by structuralcodes. ColumnsEC2 only
    generates constructible reinforcement alternatives, orders them and
    post-processes the utilisation factor.
    """
    backend = _backend_selected_v52(getattr(self, "code_backend", None))
    material = str(row.get("material", "") or "").strip()
    if not material or material.lower() in ["nan", "none", "-"]:
        reason = "Material não especificado; o backend structuralcodes exige classe de betão explícita na tabela."
        return {"member": row.get("member", ""), "case": row.get("case", ""), "name": row.get("name", ""),
                "prumada": _v091_force_prumada(row), "status": "Falha", "estado_global": "Falha",
                "failure_reason": reason, "failure_type": "dados_incompletos", "code_backend": backend,
                "normative_basis": backend, "backend_note": reason}

    globals()["ACTIVE_CODE_BACKEND_V48"] = backend
    globals()["_SC_STRICT_LAST_MATERIAL_V52"] = material
    globals()["_SC_STRICT_LAST_FYK_V52"] = float(getattr(self, "fyk", 500.0))

    try:
        mats = _sc_materials_v52(material, fyk=float(getattr(self, "fyk", 500.0)), backend=backend)
    except Exception as e:
        reason = f"structuralcodes não calculou as propriedades dos materiais: {e}"
        return {"member": row.get("member", ""), "case": row.get("case", ""), "name": row.get("name", ""),
                "prumada": _v091_force_prumada(row), "status": "Falha", "estado_global": "Falha",
                "failure_reason": reason, "failure_type": "backend_structuralcodes", "code_backend": backend,
                "normative_basis": backend}

    b_mm = cm_to_mm(row.get("hy", 0.0))
    h_mm = cm_to_mm(row.get("hz", 0.0))
    ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
    if b_mm <= 0 and ac_mm2 > 0:
        b_mm = math.sqrt(ac_mm2)
    if h_mm <= 0:
        h_mm = b_mm
    if not math.isfinite(ac_mm2) or ac_mm2 <= 0:
        ac_mm2 = b_mm * h_mm

    n_ed_kN = max(abs(safe_float(row.get("fx_i", row.get("fx", 0.0)), 0.0)),
                  abs(safe_float(row.get("fx_j", row.get("fx", 0.0)), 0.0)))
    my_ed_kNm = max(abs(safe_float(row.get("my_i", row.get("my", 0.0)), 0.0)),
                    abs(safe_float(row.get("my_j", row.get("my", 0.0)), 0.0)))
    mz_ed_kNm = max(abs(safe_float(row.get("mz_i", row.get("mz", 0.0)), 0.0)),
                    abs(safe_float(row.get("mz_j", row.get("mz", 0.0)), 0.0)))

    fyd = float(mats.get("fyd", 0.0) or 0.0)
    fck = float(mats.get("fck", parse_concrete_strength(material)) or parse_concrete_strength(material))
    fcd = float(mats.get("fcd", 0.0) or 0.0)
    Es = float(mats.get("Es", 210000.0) or 210000.0)

    as_min = max(0.10 * n_ed_kN * 1e3 / max(fyd, 1e-9), 0.002 * ac_mm2)
    as_max = 0.04 * ac_mm2
    as_seed = min(max(_v091_sc_as_seed(self, n_ed_kN, my_ed_kNm, mz_ed_kNm, b_mm, h_mm, fyd, as_min), as_min), as_max)

    is_circular = self.infer_is_circular(row, b_mm, h_mm)
    all_candidates = prebuilt_candidates if prebuilt_candidates is not None else self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)
    candidates = [c for c in list(all_candidates) if c.as_prov_mm2 >= as_min - 1e-9 and c.as_prov_mm2 <= as_max + 1e-9]

    strategy = str(getattr(self, "design_strategy", globals().get("ACTIVE_REBAR_STRATEGY_V64", "Equilibrada")) or "Equilibrada")
    ordered = _v091_layout_order_sc(candidates, as_seed, strategy)

    # Full adaptive search. No [:18] truncation. A hard safety cap is kept only for very large catalogues.
    hard_cap = int(globals().get("SC_MAX_LAYOUTS_V091", 600))
    if len(ordered) > hard_cap:
        # keep candidates around As_seed and also a tail of heavier layouts
        near = _v091_layout_order_sc(ordered, as_seed, "equilibrada")[:int(0.75 * hard_cap)]
        strong = sorted(ordered, key=lambda c: -float(c.as_prov_mm2))[:hard_cap - len(near)]
        seen = set()
        ordered2 = []
        for c in near + strong:
            key = (c.phi_long_mm, c.phi_st_mm, c.n_bars_y, c.n_bars_z, round(c.as_prov_mm2, 3))
            if key not in seen:
                seen.add(key)
                ordered2.append(c)
        ordered = ordered2

    shortlist = []
    ok_items = []
    best_failed = None
    capacity_errors = []
    tested = 0
    cap_src_last = "structuralcodes.sections"

    for ly in ordered:
        tested += 1
        try:
            caps, cap_src = _sc_nmm_capacities_v52(ly, n_ed_kN, material, float(getattr(self, "fyk", 500.0)), backend=backend)
            cap_src_last = cap_src
            ok, util, mycap, mzcap = self.biaxial_ok(my_ed_kNm, mz_ed_kNm, caps)
            eta = 999.0 if util is None or not math.isfinite(float(util)) else float(util)
            _v091_shortlist_append(shortlist, ly, util=eta, ok=bool(ok))
            item = {"layout": ly, "eta": eta, "as": float(ly.as_prov_mm2), "mycap": mycap, "mzcap": mzcap, "cap_src": cap_src}
            if ok:
                ok_items.append(item)
                # In economic mode, because candidates are sorted by As, the first OK is sufficient.
                if strategy.lower().startswith("econ"):
                    break
            if best_failed is None or eta < best_failed["eta"]:
                best_failed = item
        except Exception as e:
            msg = str(e)
            capacity_errors.append(msg)
            _v091_shortlist_append(shortlist, ly, util=None, ok=False, note=f"structuralcodes: {msg[:80]}")

    chosen_item = _v091_pick_ok_candidate(ok_items, strategy)
    chosen = chosen_item["layout"] if chosen_item else None
    chosen_util = chosen_item["eta"] if chosen_item else None
    chosen_caps = (chosen_item["mycap"], chosen_item["mzcap"]) if chosen_item else (None, None)
    cap_src_last = chosen_item.get("cap_src", cap_src_last) if chosen_item else cap_src_last

    if chosen is None:
        status = "Falha"
        sol = ""
        asprov = phil = phist = sst = nbary = nbarz = ntotal = None
        if not candidates:
            failure_reason = (
                f"Falha N-My-Mz: não existem layouts admissíveis entre As,min={as_min:.0f} mm² e As,max={as_max:.0f} mm²."
            )
        elif best_failed is not None:
            failure_reason = (
                f"Falha N-My-Mz: {tested} layout(s) structuralcodes testado(s), sem solução conforme. "
                f"Melhor η_NMyMz={best_failed['eta']:.3f} para As={best_failed['as']:.0f} mm². "
                f"As_seed={as_seed:.0f} mm²; As,max={as_max:.0f} mm²."
            )
        else:
            failure_reason = (
                f"Falha N-My-Mz: structuralcodes não devolveu capacidade útil para {tested} layout(s). "
                f"Primeiro erro: {capacity_errors[0] if capacity_errors else 'sem detalhe'}."
            )
    else:
        status = "OK"
        sst = self.choose_spacing(self.tie_spacing_max(b_mm, h_mm, chosen.phi_long_mm))
        sol = f"{chosen.n_total}Ø{int(chosen.phi_long_mm)} + estribos Ø{int(chosen.phi_st_mm)}//{sst/10:.1f} cm"
        asprov = chosen.as_prov_mm2
        phil = chosen.phi_long_mm
        phist = chosen.phi_st_mm
        nbary = chosen.n_bars_y
        nbarz = chosen.n_bars_z
        ntotal = chosen.n_total
        failure_reason = ""

    out = {
        "member": row.get("member", ""), "case": row.get("case", ""), "name": row.get("name", ""),
        "prumada": _v091_force_prumada(row), "story": row.get("story", row.get("Story", row.get("piso", row.get("Piso", "")))),
        "material": material, "fck_MPa": fck, "b_cm": b_mm / 10.0, "h_cm": h_mm / 10.0,
        "length_m": safe_float(row.get("length", 0.0), 0.0),
        "n_ed_kN": n_ed_kN, "my_ed_kNm": my_ed_kNm, "mz_ed_kNm": mz_ed_kNm,
        "as_min_mm2": as_min, "as_seed_sc_mm2": as_seed, "as_req_mm2": as_seed,
        "as_max_mm2": as_max, "as_prov_mm2": asprov,
        "phi_long_mm": phil, "n_total": ntotal, "n_bars_y": nbary, "n_bars_z": nbarz,
        "phi_st_mm": phist, "s_st_mm": sst,
        "mrd_y_kNm": chosen_caps[0], "mrd_z_kNm": chosen_caps[1],
        "utilizacao": chosen_util, "η_NMyMz": chosen_util, "solucao": sol, "status": status,
        "estado_resistente": "OK" if status == "OK" else "Falha", "estado_global": status,
        "failure_reason": failure_reason, "failure_type": "backend_structuralcodes" if status != "OK" else "",
        "shortlist_text": serialize_shortlist(shortlist),
        "layouts_admissiveis_sc": len(candidates), "layouts_testados_sc": tested,
        "search_policy_sc": "pesquisa adaptativa; sem corte [:18]; As_seed usa N+My+Mz apenas para ordenação",
        "code_backend": backend, "normative_basis": f"{backend} — modo strict; sem fallback para fórmulas normativas internas.",
        "materials_backend": mats.get("backend", ""), "materials_sources": mats.get("sources", ""),
        "nmm_capacity_source": cap_src_last,
        "second_order_status": "Não avaliado neste backend structuralcodes pelo ColumnsEC2; sem fallback interno.",
    }

    # Constructive detailing is not used as a normative substitute for structuralcodes; it is a drawing/detailing layer.
    if chosen is not None:
        out["cover_mm"] = getattr(self, "cover_mm", 35.0)
        try:
            d = _v68_layout_refinement(pd.Series(out)) if "_v68_layout_refinement" in globals() else (_v66_layout_refinement(pd.Series(out)) if "_v66_layout_refinement" in globals() else {})
            for k, v in d.items():
                out[k] = v
            out["detailing_status"] = out.get("estado_pormenorizacao", out.get("detailing_status", "OK"))
        except Exception as e:
            out["detailing_status"] = f"Aviso: pormenorização construtiva não gerada ({e})"
        _sc_shear_check_v52(out, row, chosen, mats, backend=backend)
        _sc_torsion_check_v52(out, row, chosen, mats, backend=backend)
        _sc_service_check_v52(out, row, chosen, mats, backend=backend)
    else:
        out["detailing_status"] = "Não avaliado: sem solução N-My-Mz por structuralcodes"
        out["estado_pormenorizacao"] = "Não avaliado"
        out["shear_status_y"] = out["shear_status_z"] = out["torsion_status"] = out["service_status"] = "Não avaliado: sem solução N-My-Mz por structuralcodes"

    aux_warnings = [
        str(out.get(k, "")) for k in ["shear_status_y", "shear_status_z", "torsion_status", "service_status", "second_order_status", "detailing_status"]
        if any(tag in str(out.get(k, "")) for tag in ["Aviso", "Não avaliado", "não exposta", "não calculado"])
    ]
    if status == "OK" and aux_warnings:
        out["status"] = "Aviso"
        out["estado_global"] = "Aviso"
        out["failure_type"] = "escopo_backend"
        out["failure_reason"] = "; ".join(aux_warnings[:4])
    else:
        out["estado_global"] = status

    try:
        out = _v65_apply_module_statuses(pd.DataFrame([out])).iloc[0].to_dict()
    except Exception:
        pass
    return out


# Final dispatch patch: PT keeps the current internal engine; structuralcodes uses v0.9 RC1 strict adapter.
_v091_previous_design_one = ColumnDesigner.design_one

def _design_one_v091(self, row: pd.Series, prebuilt_candidates=None):
    backend = _backend_selected_v52(getattr(self, "code_backend", None))
    if _sc_backend_active_v52(backend):
        return _strict_sc_design_one_v091(self, row, prebuilt_candidates=prebuilt_candidates)
    return _v091_previous_design_one(self, row, prebuilt_candidates=prebuilt_candidates)

ColumnDesigner.design_one = _design_one_v091
globals()["_strict_sc_design_one_v52"] = _strict_sc_design_one_v091


# Make the structuralcodes diagnostic explicitly show the adaptive search patch.
try:
    _old_sc_diag_v091 = globals().get("_v66_structuralcodes_diagnostics", None)
    def _v091_structuralcodes_diagnostics(app=None):
        if callable(_old_sc_diag_v091):
            df = _old_sc_diag_v091(app)
        else:
            df = pd.DataFrame(columns=["Item", "Estado", "Nota"])
        extra = pd.DataFrame([
            ["Structuralcodes layout search", "Activo", "Pesquisa adaptativa até As,max; removido corte artificial aos primeiros 18 layouts."],
            ["Structuralcodes As_seed", "Activo", "N+My+Mz usado apenas para ordenar layouts; verificação resistente continua a ser structuralcodes."],
        ], columns=list(df.columns[:3]) if len(df.columns) >= 3 else ["Item", "Estado", "Nota"])
        try:
            return pd.concat([df, extra], ignore_index=True)
        except Exception:
            return extra
    globals()["_v66_structuralcodes_diagnostics"] = _v091_structuralcodes_diagnostics
except Exception:
    pass


# Small bilingual polish for RC1 labels in the app title/status.
def _v091_apply_language_title(app):
    try:
        lang = _v69_lang(app) if "_v69_lang" in globals() else "PT"
        if lang == globals().get("LANG_EN", "EN-UK"):
            app.title("ColumnsEC2 - Reinforced Concrete Column Design")
        else:
            app.title("ColumnsEC2 - Dimensionamento de Pilares (EC2)")
    except Exception:
        pass

try:
    _old_apply_language_v091 = ColumnsEC2App.apply_language
    def _apply_language_v091(self):
        out = _old_apply_language_v091(self)
        _v091_apply_language_title(self)
        return out
    ColumnsEC2App.apply_language = _apply_language_v091
except Exception:
    pass


# Expose language application as a class method as well as the sidebar callback.
try:
    ColumnsEC2App.apply_language = _v69_apply_language
except Exception:
    pass




# ============================================================
# ColumnsEC2 v0.9 RC2 — performance patch for structuralcodes
# ============================================================
APP_VERSION = "v0.9 RC2"
SC_MAX_LAYOUTS_FAST_V092 = 120
SC_MAX_LAYOUTS_ROBUST_V092 = 180
SC_CAPACITY_CACHE_V092 = {}
SC_IMPORT_CACHE_V092 = {}

# Cache structuralcodes imports. Importing and setting the design code for every
# tested layout is unnecessarily expensive.
try:
    _old_sc_import_backend_v092 = _sc_import_backend_v52
    def _sc_import_backend_v52(backend=None):
        b = _backend_selected_v52(backend)
        if not _sc_backend_active_v52(b):
            return _old_sc_import_backend_v092(backend)
        key = str(b)
        if key not in SC_IMPORT_CACHE_V092:
            SC_IMPORT_CACHE_V092[key] = _old_sc_import_backend_v092(backend)
        return SC_IMPORT_CACHE_V092[key]
    globals()["_sc_import_backend_v52"] = _sc_import_backend_v52
except Exception:
    pass

# Cache N-My-Mz domains by backend/material/layout/NEd. The same layout is often
# checked in several cases with close axial force levels.
try:
    _old_sc_nmm_capacities_v092 = _sc_nmm_capacities_v52
    def _sc_nmm_capacities_v52(layout, n_ed_kN: float, material: str, fyk: float, backend=None):
        b = _backend_selected_v52(backend)
        key = (
            str(b), str(material).strip(), round(float(fyk), 1), round(float(n_ed_kN), 0),
            round(float(layout.b_mm), 1), round(float(layout.h_mm), 1),
            round(float(layout.cover_mm), 1), round(float(layout.phi_long_mm), 1),
            round(float(layout.phi_st_mm), 1), int(layout.n_bars_y), int(layout.n_bars_z),
        )
        if key in SC_CAPACITY_CACHE_V092:
            return SC_CAPACITY_CACHE_V092[key]
        val = _old_sc_nmm_capacities_v092(layout, n_ed_kN, material, fyk, backend=backend)
        if len(SC_CAPACITY_CACHE_V092) < 2500:
            SC_CAPACITY_CACHE_V092[key] = val
        return val
    globals()["_sc_nmm_capacities_v52"] = _sc_nmm_capacities_v52
except Exception:
    pass


def _strict_sc_design_one_v092(self, row: pd.Series, prebuilt_candidates=None):
    """Strict structuralcodes adapter with bounded adaptive search.

    RC1 removed the artificial [:18] truncation, but in balanced mode it could
    continue testing too many layouts after already finding a valid solution.
    RC2 keeps the correction but stops as soon as a technically acceptable
    solution is found, unless the user explicitly chooses the robust strategy.
    """
    backend = _backend_selected_v52(getattr(self, "code_backend", None))
    material = str(row.get("material", "") or "").strip()
    if not material or material.lower() in ["nan", "none", "-"]:
        reason = "Material não especificado; o backend structuralcodes exige classe de betão explícita na tabela."
        return {"member": row.get("member", ""), "case": row.get("case", ""), "name": row.get("name", ""),
                "prumada": _v091_force_prumada(row), "status": "Falha", "estado_global": "Falha",
                "failure_reason": reason, "failure_type": "dados_incompletos", "code_backend": backend,
                "normative_basis": backend, "backend_note": reason}

    globals()["ACTIVE_CODE_BACKEND_V48"] = backend
    globals()["_SC_STRICT_LAST_MATERIAL_V52"] = material
    globals()["_SC_STRICT_LAST_FYK_V52"] = float(getattr(self, "fyk", 500.0))

    try:
        mats = _sc_materials_v52(material, fyk=float(getattr(self, "fyk", 500.0)), backend=backend)
    except Exception as e:
        reason = f"structuralcodes não calculou as propriedades dos materiais: {e}"
        return {"member": row.get("member", ""), "case": row.get("case", ""), "name": row.get("name", ""),
                "prumada": _v091_force_prumada(row), "status": "Falha", "estado_global": "Falha",
                "failure_reason": reason, "failure_type": "backend_structuralcodes", "code_backend": backend,
                "normative_basis": backend}

    b_mm = cm_to_mm(row.get("hy", 0.0))
    h_mm = cm_to_mm(row.get("hz", 0.0))
    ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
    if b_mm <= 0 and ac_mm2 > 0:
        b_mm = math.sqrt(ac_mm2)
    if h_mm <= 0:
        h_mm = b_mm
    if not math.isfinite(ac_mm2) or ac_mm2 <= 0:
        ac_mm2 = b_mm * h_mm

    n_ed_kN = max(abs(safe_float(row.get("fx_i", row.get("fx", 0.0)), 0.0)),
                  abs(safe_float(row.get("fx_j", row.get("fx", 0.0)), 0.0)))
    my_ed_kNm = max(abs(safe_float(row.get("my_i", row.get("my", 0.0)), 0.0)),
                    abs(safe_float(row.get("my_j", row.get("my", 0.0)), 0.0)))
    mz_ed_kNm = max(abs(safe_float(row.get("mz_i", row.get("mz", 0.0)), 0.0)),
                    abs(safe_float(row.get("mz_j", row.get("mz", 0.0)), 0.0)))

    fyd = float(mats.get("fyd", 0.0) or 0.0)
    fck = float(mats.get("fck", parse_concrete_strength(material)) or parse_concrete_strength(material))
    as_min = max(0.10 * n_ed_kN * 1e3 / max(fyd, 1e-9), 0.002 * ac_mm2)
    as_max = 0.04 * ac_mm2
    as_seed = min(max(_v091_sc_as_seed(self, n_ed_kN, my_ed_kNm, mz_ed_kNm, b_mm, h_mm, fyd, as_min), as_min), as_max)

    is_circular = self.infer_is_circular(row, b_mm, h_mm)
    all_candidates = prebuilt_candidates if prebuilt_candidates is not None else self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)
    candidates = [c for c in list(all_candidates) if c.as_prov_mm2 >= as_min - 1e-9 and c.as_prov_mm2 <= as_max + 1e-9]

    strategy = str(getattr(self, "design_strategy", globals().get("ACTIVE_REBAR_STRATEGY_V64", "Equilibrada")) or "Equilibrada")
    strategy_l = strategy.lower()
    ordered = _v091_layout_order_sc(candidates, as_seed, strategy)

    if strategy_l.startswith("rob"):
        hard_cap = int(globals().get("SC_MAX_LAYOUTS_ROBUST_V092", 180))
    elif strategy_l.startswith("econ"):
        hard_cap = int(globals().get("SC_MAX_LAYOUTS_FAST_V092", 120))
    else:
        hard_cap = int(globals().get("SC_MAX_LAYOUTS_FAST_V092", 120))

    if len(ordered) > hard_cap:
        near_count = max(1, int(0.80 * hard_cap))
        near = _v091_layout_order_sc(ordered, as_seed, "equilibrada")[:near_count]
        strong = sorted(ordered, key=lambda c: -float(c.as_prov_mm2))[:hard_cap - len(near)]
        seen = set(); ordered2 = []
        for c in near + strong:
            k = (c.phi_long_mm, c.phi_st_mm, c.n_bars_y, c.n_bars_z, round(c.as_prov_mm2, 3))
            if k not in seen:
                seen.add(k); ordered2.append(c)
        ordered = ordered2

    shortlist = []
    ok_items = []
    best_failed = None
    capacity_errors = []
    tested = 0
    cap_src_last = "structuralcodes.sections"
    eta_target = float(globals().get("REBAR_TARGET_ETA_V64", 0.80))
    eta_min = float(globals().get("REBAR_ETA_MIN_V68", 0.70))
    eta_max = float(globals().get("REBAR_ETA_MAX_V68", 0.90))

    for ly in ordered:
        tested += 1
        try:
            caps, cap_src = _sc_nmm_capacities_v52(ly, n_ed_kN, material, float(getattr(self, "fyk", 500.0)), backend=backend)
            cap_src_last = cap_src
            ok, util, mycap, mzcap = self.biaxial_ok(my_ed_kNm, mz_ed_kNm, caps)
            eta = 999.0 if util is None or not math.isfinite(float(util)) else float(util)
            _v091_shortlist_append(shortlist, ly, util=eta, ok=bool(ok))
            item = {"layout": ly, "eta": eta, "as": float(ly.as_prov_mm2), "mycap": mycap, "mzcap": mzcap, "cap_src": cap_src}
            if ok:
                ok_items.append(item)
                if strategy_l.startswith("econ"):
                    break
                if not strategy_l.startswith("rob"):
                    # Balanced strategy: stop once a reasonable eta band is reached.
                    if eta_min <= eta <= eta_max:
                        break
                    if len(ok_items) >= 3:
                        break
                    if abs(eta - eta_target) <= 0.12:
                        break
            if best_failed is None or eta < best_failed["eta"]:
                best_failed = item
        except Exception as e:
            msg = str(e)
            capacity_errors.append(msg)
            _v091_shortlist_append(shortlist, ly, util=None, ok=False, note=f"structuralcodes: {msg[:80]}")

    chosen_item = _v091_pick_ok_candidate(ok_items, strategy)
    chosen = chosen_item["layout"] if chosen_item else None
    chosen_util = chosen_item["eta"] if chosen_item else None
    chosen_caps = (chosen_item["mycap"], chosen_item["mzcap"]) if chosen_item else (None, None)
    cap_src_last = chosen_item.get("cap_src", cap_src_last) if chosen_item else cap_src_last

    if chosen is None:
        status = "Falha"
        sol = ""
        asprov = phil = phist = sst = nbary = nbarz = ntotal = None
        if not candidates:
            failure_reason = f"Falha N-My-Mz: não existem layouts admissíveis entre As,min={as_min:.0f} mm² e As,max={as_max:.0f} mm²."
        elif best_failed is not None:
            failure_reason = (
                f"Falha N-My-Mz: {tested} layout(s) structuralcodes testado(s), sem solução conforme. "
                f"Melhor η_NMyMz={best_failed['eta']:.3f} para As={best_failed['as']:.0f} mm². "
                f"As_seed={as_seed:.0f} mm²; As,max={as_max:.0f} mm²."
            )
        else:
            failure_reason = (
                f"Falha N-My-Mz: structuralcodes não devolveu capacidade útil para {tested} layout(s). "
                f"Primeiro erro: {capacity_errors[0] if capacity_errors else 'sem detalhe'}."
            )
    else:
        status = "OK"
        sst = self.choose_spacing(self.tie_spacing_max(b_mm, h_mm, chosen.phi_long_mm))
        sol = f"{chosen.n_total}Ø{int(chosen.phi_long_mm)} + estribos Ø{int(chosen.phi_st_mm)}//{sst/10:.1f} cm"
        asprov = chosen.as_prov_mm2
        phil = chosen.phi_long_mm
        phist = chosen.phi_st_mm
        nbary = chosen.n_bars_y
        nbarz = chosen.n_bars_z
        ntotal = chosen.n_total
        failure_reason = ""

    out = {
        "member": row.get("member", ""), "case": row.get("case", ""), "name": row.get("name", ""),
        "prumada": _v091_force_prumada(row), "story": row.get("story", row.get("Story", row.get("piso", row.get("Piso", "")))),
        "material": material, "fck_MPa": fck, "b_cm": b_mm / 10.0, "h_cm": h_mm / 10.0,
        "length_m": safe_float(row.get("length", 0.0), 0.0),
        "n_ed_kN": n_ed_kN, "my_ed_kNm": my_ed_kNm, "mz_ed_kNm": mz_ed_kNm,
        "as_min_mm2": as_min, "as_seed_sc_mm2": as_seed, "as_req_mm2": as_seed,
        "as_max_mm2": as_max, "as_prov_mm2": asprov,
        "phi_long_mm": phil, "n_total": ntotal, "n_bars_y": nbary, "n_bars_z": nbarz,
        "phi_st_mm": phist, "s_st_mm": sst,
        "mrd_y_kNm": chosen_caps[0], "mrd_z_kNm": chosen_caps[1],
        "utilizacao": chosen_util, "η_NMyMz": chosen_util, "solucao": sol, "status": status,
        "estado_resistente": "OK" if status == "OK" else "Falha", "estado_global": status,
        "failure_reason": failure_reason, "failure_type": "backend_structuralcodes" if status != "OK" else "",
        "shortlist_text": serialize_shortlist(shortlist),
        "layouts_admissiveis_sc": len(candidates), "layouts_testados_sc": tested,
        "search_policy_sc": "RC2: pesquisa adaptativa limitada e paragem antecipada após solução aceitável; As_seed usa N+My+Mz apenas para ordenação",
        "code_backend": backend, "normative_basis": f"{backend} — modo strict; sem fallback para fórmulas normativas internas.",
        "materials_backend": mats.get("backend", ""), "materials_sources": mats.get("sources", ""),
        "nmm_capacity_source": cap_src_last,
        "second_order_status": "Não avaliado neste backend structuralcodes pelo ColumnsEC2; sem fallback interno.",
    }

    if chosen is not None:
        out["cover_mm"] = getattr(self, "cover_mm", 35.0)
        try:
            d = _v68_layout_refinement(pd.Series(out)) if "_v68_layout_refinement" in globals() else (_v66_layout_refinement(pd.Series(out)) if "_v66_layout_refinement" in globals() else {})
            for k, v in d.items():
                out[k] = v
            out["detailing_status"] = out.get("estado_pormenorizacao", out.get("detailing_status", "OK"))
        except Exception as e:
            out["detailing_status"] = f"Aviso: pormenorização construtiva não gerada ({e})"
        _sc_shear_check_v52(out, row, chosen, mats, backend=backend)
        _sc_torsion_check_v52(out, row, chosen, mats, backend=backend)
        _sc_service_check_v52(out, row, chosen, mats, backend=backend)
    else:
        out["detailing_status"] = "Não avaliado: sem solução N-My-Mz por structuralcodes"
        out["estado_pormenorizacao"] = "Não avaliado"
        out["shear_status_y"] = out["shear_status_z"] = out["torsion_status"] = out["service_status"] = "Não avaliado: sem solução N-My-Mz por structuralcodes"

    aux_warnings = [
        str(out.get(k, "")) for k in ["shear_status_y", "shear_status_z", "torsion_status", "service_status", "second_order_status", "detailing_status"]
        if any(tag in str(out.get(k, "")) for tag in ["Aviso", "Não avaliado", "não exposta", "não calculado"])
    ]
    if status == "OK" and aux_warnings:
        out["status"] = "Aviso"
        out["estado_global"] = "Aviso"
        out["failure_type"] = "escopo_backend"
        out["failure_reason"] = "; ".join(aux_warnings[:4])
    else:
        out["estado_global"] = status

    try:
        out = _v65_apply_module_statuses(pd.DataFrame([out])).iloc[0].to_dict()
    except Exception:
        pass
    return out


_v092_previous_design_one = ColumnDesigner.design_one

def _design_one_v092(self, row: pd.Series, prebuilt_candidates=None):
    backend = _backend_selected_v52(getattr(self, "code_backend", None))
    if _sc_backend_active_v52(backend):
        return _strict_sc_design_one_v092(self, row, prebuilt_candidates=prebuilt_candidates)
    return _v092_previous_design_one(self, row, prebuilt_candidates=prebuilt_candidates)

ColumnDesigner.design_one = _design_one_v092
globals()["_strict_sc_design_one_v52"] = _strict_sc_design_one_v092

# Give immediate UI feedback and progress updates by case. The first structuralcodes
# case can still take longer than the internal EC2 engine, but the run no longer looks frozen.
try:
    _old_design_dataframe_v092 = ColumnDesigner.design_dataframe
    def _design_dataframe_v092(self, df: pd.DataFrame, progress_callback=None):
        total = 0 if df is None else len(df)
        if progress_callback:
            try:
                progress_callback(0, max(total, 1))
            except Exception:
                pass
        results = []
        grouped_candidates = {}
        if df is None or df.empty:
            return pd.DataFrame()
        for _, row in df.iterrows():
            b_mm = cm_to_mm(row.get("hy", 0.0))
            h_mm = cm_to_mm(row.get("hz", 0.0))
            ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
            if b_mm <= 0 and ac_mm2 > 0:
                b_mm = math.sqrt(ac_mm2)
            if h_mm <= 0:
                h_mm = b_mm
            is_circular = self.infer_is_circular(row, b_mm, h_mm)
            sec_key = (round(b_mm, 1), round(h_mm, 1), bool(is_circular))
            if sec_key not in grouped_candidates:
                grouped_candidates[sec_key] = self.build_candidate_layouts(b_mm, h_mm, is_circular=is_circular)
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            b_mm = cm_to_mm(row.get("hy", 0.0))
            h_mm = cm_to_mm(row.get("hz", 0.0))
            ac_mm2 = safe_float(row.get("ax", float("nan"))) * 100.0
            if b_mm <= 0 and ac_mm2 > 0:
                b_mm = math.sqrt(ac_mm2)
            if h_mm <= 0:
                h_mm = b_mm
            is_circular = self.infer_is_circular(row, b_mm, h_mm)
            sec_key = (round(b_mm, 1), round(h_mm, 1), bool(is_circular))
            results.append(self.design_one(row, prebuilt_candidates=grouped_candidates[sec_key]))
            if progress_callback:
                try:
                    progress_callback(i, total)
                except Exception:
                    pass
        out = pd.DataFrame(results)
        if not out.empty and "utilizacao" in out.columns:
            out["sort_key"] = out["utilizacao"].fillna(999.0)
        return out
    ColumnDesigner.design_dataframe = _design_dataframe_v092
except Exception:
    pass

try:
    _old_sc_diag_v092 = globals().get("_v66_structuralcodes_diagnostics", None)
    def _v092_structuralcodes_diagnostics(app=None):
        if callable(_old_sc_diag_v092):
            df = _old_sc_diag_v092(app)
        else:
            df = pd.DataFrame(columns=["Item", "Estado", "Nota"])
        extra = pd.DataFrame([
            ["Structuralcodes performance", "Activo", "RC2: import/cache de domínios N-My-Mz e paragem antecipada após solução aceitável."],
            ["Structuralcodes layout cap", "Activo", f"Pesquisa limitada a {SC_MAX_LAYOUTS_FAST_V092} layouts em modo económico/equilibrado e {SC_MAX_LAYOUTS_ROBUST_V092} em robusto."],
        ], columns=list(df.columns[:3]) if len(df.columns) >= 3 else ["Item", "Estado", "Nota"])
        try:
            return pd.concat([df, extra], ignore_index=True)
        except Exception:
            return extra
    globals()["_v66_structuralcodes_diagnostics"] = _v092_structuralcodes_diagnostics
except Exception:
    pass



# ============================================================
# ColumnsEC2 v0.9 RC3 — English UI/report polish + robust PDF export
# ============================================================
