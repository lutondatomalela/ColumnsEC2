# -*- coding: utf-8 -*-
"""Import and normalisation of structural-analysis result tables."""
from __future__ import annotations

import io
import re
from typing import Dict, List

import pandas as pd

from .utils import normalize_text, safe_float, split_member_case
from .materials import DEFAULT_CONCRETE_CLASS, parse_concrete_strength, concrete_props

COLUMN_ALIASES: Dict[str, List[str]] = {
    "member_case": ["member/node/case", "member/n/case", "member/n", "member/node", "barra/nó/caso", "barra/no/caso", "barra/n/caso", "barra/nó", "barra/no", "elemento/nó/caso", "elemento/no/caso"],
    "member": ["member", "barra", "elemento", "bar", "membro"],
    "node": ["node", "nó", "no", "n", "nodo"],
    "case": ["case", "caso", "combinação", "combinacao", "comb", "load case", "loadcase"],
    "fx": ["fx (kn)", "fx"],
    "fy": ["fy (kn)", "fy"],
    "fz": ["fz (kn)", "fz"],
    "mx": ["mx (knm)", "mx"],
    "my": ["my (knm)", "my"],
    "mz": ["mz (knm)", "mz"],
    "length": ["length (m)", "length(m)", "length", "comprimento", "comprimento (m)", "comprimento(m)", "l (m)", "l"],
    "material": ["material", "concrete", "betao", "betão", "classe de betao", "classe de betão"],
    "hy": ["hy (cm)", "hy"],
    "hz": ["hz (cm)", "hz"],
    "vy": ["vy (cm)", "vy"],
    "vz": ["vz (cm)", "vz"],
    "vpy": ["vpy (cm)", "vpy"],
    "vpz": ["vpz (cm)", "vpz"],
    "ax": ["ax (cm2)", "ax", "ax (cm²)"],
    "ay": ["ay (cm2)", "ay", "ay (cm²)"],
    "az": ["az (cm2)", "az", "az (cm²)"],
    "ix": ["ix (cm4)", "ix", "ix (cm⁴)"],
    "iy": ["iy (cm4)", "iy", "iy (cm⁴)"],
    "iz": ["iz (cm4)", "iz", "iz (cm⁴)"],
    "name": ["name", "nome", "column", "pillar", "prumada", "pilar", "linha de pilar"],
    "story": [
        "story", "storey", "piso", "piso/andar", "andar", "andares", "level", "floor",
        "floor level", "pavimento", "cota", "nível", "nivel", "storey name", "nome do piso",
        "nome piso", "piso estrutural",
    ],
}

NUMERIC_COLUMNS = [
    "fx", "fy", "fz", "mx", "my", "mz", "length", "hy", "hz", "vy", "vz", "vpy", "vpz",
    "ax", "ay", "az", "ix", "iy", "iz",
]


def parse_pasted_table(text: str) -> pd.DataFrame:
    text = str(text or "").strip()
    if not text:
        return pd.DataFrame()
    for sep in ("\t", ";", ",", "|"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python", dtype=str)
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return pd.DataFrame()
    rows = [re.split(r"\s{2,}", line) for line in lines]
    header = rows[0]
    width = len(header)
    body = [row[:width] + [""] * max(0, width - len(row)) for row in rows[1:]]
    return pd.DataFrame(body, columns=header)


def rename_known_columns(df: pd.DataFrame) -> pd.DataFrame:
    norm_to_original = {normalize_text(c): c for c in df.columns}
    rename_map = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in norm_to_original:
                rename_map[norm_to_original[alias]] = target
                break
    return df.rename(columns=rename_map).copy()


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = rename_known_columns(df)
    out["__row_order"] = range(len(out))
    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(safe_float)
    if "member_case" in out.columns:
        split_vals = out["member_case"].map(split_member_case)
        for col, pos in [("member", 0), ("node", 1), ("case", 2)]:
            vals = split_vals.map(lambda x, p=pos: x[p])
            if col not in out.columns:
                out[col] = vals
            else:
                mask = out[col].astype(str).str.strip().str.lower().isin(["", "nan", "none", "<na>"])
                out.loc[mask, col] = vals.loc[mask]
    else:
        for col in ["member", "node", "case"]:
            if col not in out.columns:
                out[col] = ""
    for col in ["name", "story"]:
        if col not in out.columns:
            out[col] = ""
    if "material" not in out.columns:
        out["material"] = DEFAULT_CONCRETE_CLASS
    mask = out["material"].astype(str).str.strip().str.lower().isin(["", "nan", "none", "<na>"])
    out.loc[mask, "material"] = DEFAULT_CONCRETE_CLASS
    return out


def combine_member_end_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Convert nodal rows into member/case rows while preserving end moments."""
    if df is None or df.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["member", "case", "name", "story"]
    for _, grp in df.groupby(group_cols, dropna=False):
        grp = grp.sort_values("__row_order")
        r1 = grp.iloc[0]
        r2 = grp.iloc[1] if len(grp) >= 2 else grp.iloc[0]
        row = {
            "member": r1.get("member", ""),
            "case": r1.get("case", ""),
            "name": r1.get("name", ""),
            "story": r1.get("story", ""),
            "node_i": r1.get("node", ""),
            "node_j": r2.get("node", ""),
            "member_case_i": f"{r1.get('member','')}/{r1.get('node','')}/{r1.get('case','')}",
            "member_case_j": f"{r2.get('member','')}/{r2.get('node','')}/{r2.get('case','')}",
            "length": safe_float(r1.get("length", 0.0), 0.0),
            "material": r1.get("material", "") or DEFAULT_CONCRETE_CLASS,
            "hy": safe_float(r1.get("hy", float("nan"))),
            "hz": safe_float(r1.get("hz", float("nan"))),
            "ax": safe_float(r1.get("ax", float("nan"))),
            "iy": safe_float(r1.get("iy", float("nan"))),
            "iz": safe_float(r1.get("iz", float("nan"))),
            "__row_order": safe_float(r1.get("__row_order", 0), 0),
            "n_nodes_found": len(grp),
        }
        for force in ["fx", "fy", "fz", "mx", "my", "mz"]:
            row[f"{force}_i"] = safe_float(r1.get(force, 0.0), 0.0)
            row[f"{force}_j"] = safe_float(r2.get(force, 0.0), 0.0)
            row[force] = max(abs(row[f"{force}_i"]), abs(row[f"{force}_j"]))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["__row_order", "member", "case"]).reset_index(drop=True)


def reduce_to_governing_cases(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    for col in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if col not in work.columns:
            work[col] = 0.0
        work[f"_abs_{col}"] = work[col].abs().fillna(0.0)
    work["_score"] = work["_abs_fx"] * 0.20 + work["_abs_my"] + work["_abs_mz"] + 0.35 * work["_abs_mx"] + 0.10 * (work["_abs_fy"] + work["_abs_fz"])
    selected_idx = set()
    for _, grp in work.groupby(["member", "name"], dropna=False):
        if grp.empty:
            continue
        for col in ["_score", "_abs_fx", "_abs_fy", "_abs_fz", "_abs_mx", "_abs_my", "_abs_mz"]:
            selected_idx.add(grp[col].idxmax())
        ratio_grp = grp.assign(
            _my_over_n=grp["_abs_my"] / grp["_abs_fx"].replace(0.0, 1e-9),
            _mz_over_n=grp["_abs_mz"] / grp["_abs_fx"].replace(0.0, 1e-9),
            _v_over_n=(grp["_abs_fy"] + grp["_abs_fz"]) / grp["_abs_fx"].replace(0.0, 1e-9),
        )
        for col in ["_my_over_n", "_mz_over_n", "_v_over_n"]:
            selected_idx.add(ratio_grp[col].idxmax())
    reduced = work.loc[sorted(selected_idx)].copy().sort_values(["member", "name", "case"]).reset_index(drop=True)
    reduced.drop(columns=[c for c in reduced.columns if c.startswith("_")], inplace=True, errors="ignore")
    return reduced

# ---------------------------------------------------------------------------
# v0.9 RC23 compatibility patch: UTF-16/BOM-safe headers and tramo grouping.
# ---------------------------------------------------------------------------
import csv
from pathlib import Path


def _rc23_norm_header_core(value: object) -> str:
    s = str(value if value is not None else "")
    s = s.replace("\ufeff", "").replace("\ufffe", "").replace("\x00", "")
    s = s.replace("ÿþ", "").replace("þÿ", "")
    s = normalize_text(s).replace("º", "o").replace("ª", "a")
    return s.strip()


def _rc23_decode_bytes_core(raw: bytes) -> str:
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    best = None
    best_score = None
    last_err = None
    for enc in ("utf-16", "utf-16-le", "utf-16-be", "utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            txt = raw.decode(enc)
        except Exception as err:
            last_err = err
            continue
        score = txt.count("\x00") / max(len(txt), 1) * 100 + txt[:200].count("ÿþ") * 10 + txt[:200].count("þÿ") * 10
        if best is None or score < best_score:
            best, best_score = txt, score
        if score < 0.01:
            return txt
    if best is not None:
        return best
    raise last_err or UnicodeDecodeError("utf-8", raw, 0, 1, "could not decode table")


def read_table_file(path: str) -> pd.DataFrame:
    lower = str(path).lower()
    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str)
    else:
        raw = Path(path).read_bytes()
        text = _rc23_decode_bytes_core(raw).replace("\x00", "")
        sample = "\n".join(text.splitlines()[:30])
        delims = []
        try:
            delims.append(csv.Sniffer().sniff(sample, delimiters="\t;,|").delimiter)
        except Exception:
            pass
        delims += [";", "\t", ",", "|"]
        best, best_score = None, -1
        for sep in list(dict.fromkeys(delims)):
            try:
                cand = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, engine="python")
                score = len(cand.columns) * 10 + sum(1 for c in cand.columns if _rc23_norm_header_core(c) in {"barra/nó/caso", "barra/no/caso", "member/node/case", "fx (kn)", "nome", "andar", "material"}) * 100
                if len(cand.columns) > 1 and score > best_score:
                    best, best_score = cand, score
            except Exception:
                pass
        if best is None:
            df = pd.read_csv(io.StringIO(text), sep=None, dtype=str, engine="python")
        else:
            df = best
    df.columns = [str(c).replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip() for c in df.columns]
    return df


# Expand aliases without treating standalone "member" as a combined key.
COLUMN_ALIASES["member_case"] = [
    "member/node/case", "member/no/case", "member/nó/case", "member/n/case",
    "barra/nó/caso", "barra/no/caso", "barra/n/caso", "barra/nó/caso (c)", "barra/no/caso (c)",
    "barra nó caso", "barra no caso", "elemento/nó/caso", "elemento/no/caso", "elemento/n/caso",
]


def rename_known_columns(df: pd.DataFrame) -> pd.DataFrame:
    norm_to_original = {_rc23_norm_header_core(c): c for c in df.columns}
    rename_map = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            src = norm_to_original.get(_rc23_norm_header_core(alias))
            if src is not None and src not in rename_map:
                rename_map[src] = target
                break
    return df.rename(columns=rename_map).copy()


def _rc23_blank_core(value: object) -> bool:
    s = str(value if value is not None else "").strip()
    return s == "" or s.lower() in {"nan", "none", "null", "<na>", "-"}


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = rename_known_columns(df.copy())
    out["__row_order"] = range(len(out))
    if "member_case" in out.columns:
        split_vals = out["member_case"].map(split_member_case)
        for col, pos in [("member", 0), ("node", 1), ("case", 2)]:
            vals = split_vals.map(lambda x, p=pos: x[p])
            if col not in out.columns:
                out[col] = vals
            else:
                mask = out[col].map(_rc23_blank_core)
                out.loc[mask, col] = vals.loc[mask]
    else:
        for col in ["member", "node", "case"]:
            if col not in out.columns:
                out[col] = ""
    for col in ["name", "story"]:
        if col not in out.columns:
            out[col] = ""
    if "material" not in out.columns:
        out["material"] = DEFAULT_CONCRETE_CLASS
    for col in ["member", "node", "case", "name", "story", "material"]:
        out[col] = out[col].astype(str).map(lambda x: x.replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip())
        out.loc[out[col].str.lower().isin(["nan", "none", "null", "<na>"]), col] = ""
    out.loc[out["material"].map(_rc23_blank_core), "material"] = DEFAULT_CONCRETE_CLASS
    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(safe_float)
    if len(out) and ((out["member"].astype(str).str.strip() != "").sum() == 0 or (out["case"].astype(str).str.strip() != "").sum() == 0):
        raise ValueError("Não foi possível extrair Barra/Nó/Caso. Verifique o cabeçalho e o encoding do ficheiro CSV.")
    return out


def combine_member_end_actions(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["member", "case", "name", "story"]
    for _, grp in df.groupby(group_cols, dropna=False, sort=False):
        grp = grp.sort_values("__row_order")
        r1 = grp.iloc[0]
        r2 = grp.iloc[1] if len(grp) >= 2 else grp.iloc[0]
        row = {
            "member": r1.get("member", ""), "case": r1.get("case", ""), "name": r1.get("name", ""), "story": r1.get("story", ""),
            "node_i": r1.get("node", ""), "node_j": r2.get("node", ""),
            "member_case_i": f"{r1.get('member','')}/{r1.get('node','')}/{r1.get('case','')}",
            "member_case_j": f"{r2.get('member','')}/{r2.get('node','')}/{r2.get('case','')}",
            "length": safe_float(r1.get("length", 0.0), 0.0), "material": r1.get("material", "") or DEFAULT_CONCRETE_CLASS,
            "hy": safe_float(r1.get("hy", float("nan"))), "hz": safe_float(r1.get("hz", float("nan"))),
            "ax": safe_float(r1.get("ax", float("nan"))), "iy": safe_float(r1.get("iy", float("nan"))), "iz": safe_float(r1.get("iz", float("nan"))),
            "__row_order": safe_float(r1.get("__row_order", 0), 0), "n_nodes_found": len(grp),
        }
        for force in ["fx", "fy", "fz", "mx", "my", "mz"]:
            row[f"{force}_i"] = safe_float(r1.get(force, 0.0), 0.0)
            row[f"{force}_j"] = safe_float(r2.get(force, 0.0), 0.0)
            row[force] = max(abs(row[f"{force}_i"]), abs(row[f"{force}_j"]))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["__row_order", "member", "case"], kind="mergesort").reset_index(drop=True)


def reduce_to_governing_cases(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in work.columns:
            work[c] = 0.0
        work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
    for c in ["member", "name", "story", "material", "hy", "hz"]:
        if c not in work.columns:
            work[c] = ""
    selected = set()
    for _, grp0 in work.groupby(["member", "name", "story", "material", "hy", "hz"], dropna=False, sort=False):
        if grp0.empty:
            continue
        g = grp0[~grp0.get("case", pd.Series(index=grp0.index, dtype=str)).astype(str).str.startswith("3")]
        if g.empty:
            g = grp0
        fx = g["fx"].abs().replace(0, 1e-9)
        score = 0.25 * g["fx"].abs() + g["my"].abs() + g["mz"].abs() + 0.20 * g["mx"].abs() + 0.08 * (g["fy"].abs() + g["fz"].abs())
        for ser in [score, g["fx"].abs(), g["my"].abs(), g["mz"].abs(), g["mx"].abs(), g["fy"].abs()+g["fz"].abs(), (g["my"].abs()+g["mz"].abs())/fx, g["my"].abs()/fx, g["mz"].abs()/fx]:
            if not ser.empty:
                selected.add(ser.idxmax())
    out = work.loc[sorted(selected)].copy()
    return out.sort_values([c for c in ["name", "story", "member", "case"] if c in out.columns], kind="mergesort").reset_index(drop=True)


# ---------------------------------------------------------------------------
# v0.9 RC24: fast governing-case reduction by physical tramo.
# ---------------------------------------------------------------------------
def _rc24_case_is_service_core(value: object) -> bool:
    import re
    s = str(value if value is not None else "").strip()
    m = re.search(r"\d+", s)
    n = m.group(0) if m else s
    return n.startswith("3")


def _rc24_fast_score_core(g: pd.DataFrame) -> pd.Series:
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in g.columns:
            g[c] = 0.0
    b = max(safe_float(g["hy"].iloc[0] if "hy" in g.columns and len(g) else 0.0, 0.0) * 10.0, 1.0)
    h = max(safe_float(g["hz"].iloc[0] if "hz" in g.columns and len(g) else 0.0, 0.0) * 10.0, 1.0)
    ax = safe_float(g["ax"].iloc[0] if "ax" in g.columns and len(g) else 0.0, 0.0) * 100.0
    ac = ax if ax > 0 else b*h
    try:
        fck = parse_concrete_strength(g["material"].iloc[0] if "material" in g.columns and len(g) else DEFAULT_CONCRETE_CLASS)
        fcd = concrete_props(fck)["fcd"]
    except Exception:
        fcd = 20.0
    n0 = max(0.45 * ac * fcd / 1000.0, 1.0)
    my0 = max(0.12 * fcd * b * h * h / 1e6, 1.0)
    mz0 = max(0.12 * fcd * h * b * b / 1e6, 1.0)
    n = pd.to_numeric(g["fx"], errors="coerce").abs().fillna(0.0)
    my = pd.to_numeric(g["my"], errors="coerce").abs().fillna(0.0)
    mz = pd.to_numeric(g["mz"], errors="coerce").abs().fillna(0.0)
    t = pd.to_numeric(g["mx"], errors="coerce").abs().fillna(0.0)
    v = pd.to_numeric(g["fy"], errors="coerce").abs().fillna(0.0) + pd.to_numeric(g["fz"], errors="coerce").abs().fillna(0.0)
    rn = n / n0
    rmy = my / my0
    rmz = mz / mz0
    biax = (rmy.pow(1.35) + rmz.pow(1.35)).pow(1.0/1.35)
    ecc = (my + mz) / n.replace(0.0, 1e-9)
    ecc_norm = ecc / max(max(my0, mz0) / n0, 1e-9)
    return 0.70*rn + biax + 0.12*ecc_norm + 0.04*(t/max(my0, mz0)) + 0.02*(v/n0)


def reduce_to_governing_cases(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df
    work = df.copy()
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in work.columns:
            work[c] = 0.0
        work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
    for c in ["member", "name", "story", "material", "hy", "hz", "ax"]:
        if c not in work.columns:
            work[c] = ""
    import os
    try:
        max_cases = int(os.environ.get("COLUMNSEC2_RC24_CASES_PER_TRAMO", "1"))
    except Exception:
        max_cases = 1
    max_cases = max(1, min(max_cases, 4))
    selected = set()
    group_cols = [c for c in ["member", "name", "story", "material", "hy", "hz", "ax"] if c in work.columns]
    for _, grp0 in work.groupby(group_cols, dropna=False, sort=False):
        if grp0.empty:
            continue
        case_series = grp0.get("case", pd.Series(index=grp0.index, dtype=str)).astype(str)
        g = grp0[~case_series.map(_rc24_case_is_service_core)].copy()
        if g.empty:
            g = grp0.copy()
        score = _rc24_fast_score_core(g)
        selected.add(score.idxmax())
        if max_cases >= 2:
            selected.add(pd.to_numeric(g["fx"], errors="coerce").abs().fillna(0.0).idxmax())
        if max_cases >= 3:
            bscore = pd.to_numeric(g["my"], errors="coerce").abs().fillna(0.0) + pd.to_numeric(g["mz"], errors="coerce").abs().fillna(0.0)
            selected.add(bscore.idxmax())
        if max_cases >= 4:
            vscore = pd.to_numeric(g["fy"], errors="coerce").abs().fillna(0.0) + pd.to_numeric(g["fz"], errors="coerce").abs().fillna(0.0)
            selected.add(vscore.idxmax())
    out = work.loc[sorted(selected)].copy()
    out["rc24_reduction"] = f"1 caso governante/tramo" if max_cases == 1 else f"até {max_cases} casos governantes/tramo"
    order = [c for c in ["name", "story", "member", "case"] if c in out.columns]
    if order:
        out = out.sort_values(order, kind="mergesort")
    return out.reset_index(drop=True)
