# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC23 — CSV UTF-16, member/node/case parsing and tramo-preserving envelope.

Main corrections over RC22:
- reads Robot/SAP-style CSV exported as UTF-16 LE/BE with BOM;
- removes BOM/null artefacts from headers before alias matching;
- extracts member, node and case from Portuguese "Barra/Nó/Caso" fields;
- refuses silent calculation when member/case parsing failed;
- reduces governing cases by physical tramo, not by prumada only;
- keeps the ELS combination available through app.df_pair for the selected
  service case.
"""
from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

import pandas as pd

APP_VERSION = "v0.9 RC23 Modular"

# ---------------------------------------------------------------------------
# Encoding/header normalisation
# ---------------------------------------------------------------------------

_RC23_ENCODINGS = (
    "utf-16",      # honours FF FE / FE FF BOM
    "utf-16-le",
    "utf-16-be",
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin1",
)


def _rc23_norm_header(value):
    """Normalise CSV/XLSX headers, including BOM and wrongly decoded BOM artefacts."""
    s = str(value if value is not None else "")
    s = s.replace("\ufeff", "")
    s = s.replace("\ufffe", "")
    s = s.replace("\x00", "")
    # Common symptom when UTF-16 LE is decoded as cp1252/latin1.
    s = s.replace("ÿþ", "").replace("þÿ", "")
    try:
        s = normalize_text(s)
    except Exception:
        s = re.sub(r"\s+", " ", s.strip().lower())
    s = s.replace("º", "o").replace("ª", "a")
    return s.strip()


_RC23_MEMBER_CASE_ALIASES = [
    "member/node/case", "member/no/case", "member/nó/case", "member/n/case",
    "barra/nó/caso", "barra/no/caso", "barra/n/caso", "barra/nó/caso (c)", "barra/no/caso (c)",
    "barra nó caso", "barra no caso", "barra/nó", "barra/no",
    "elemento/nó/caso", "elemento/no/caso", "elemento/n/caso",
]
_RC23_MEMBER_ALIASES = ["member", "barra", "elemento", "bar", "membro"]
_RC23_NODE_ALIASES = ["node", "nó", "no", "n", "nodo"]
_RC23_CASE_ALIASES = ["case", "caso", "combinação", "combinacao", "comb", "load case", "loadcase"]
_RC23_STORY_ALIASES = ["story", "storey", "piso", "andar", "andares", "level", "floor", "pavimento", "nivel", "nível"]
_RC23_NAME_ALIASES = ["name", "nome", "prumada", "pilar", "column", "column line", "linha de pilar"]
_RC23_LENGTH_ALIASES = ["length (m)", "length(m)", "length", "comprimento (m)", "comprimento(m)", "comprimento", "l (m)", "l(m)", "l"]


def _rc23_decode_bytes(raw: bytes) -> str:
    if raw is None:
        return ""
    # Explicit BOM handling first. This avoids the RC22 failure where UTF-16 LE
    # was accepted as cp1252/latin1 and produced the header "ÿþBarra/Nó/Caso".
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    last_err = None
    best_text = None
    best_score = None
    for enc in _RC23_ENCODINGS:
        try:
            txt = raw.decode(enc)
        except Exception as err:
            last_err = err
            continue
        # Penalise wrong decodes with many nulls or replacement-like artefacts.
        null_ratio = txt.count("\x00") / max(len(txt), 1)
        artefacts = txt[:200].count("ÿþ") + txt[:200].count("þÿ")
        score = null_ratio * 100.0 + artefacts * 10.0
        if best_text is None or score < best_score:
            best_text, best_score = txt, score
        if score < 0.01:
            return txt
    if best_text is not None:
        return best_text
    raise last_err or UnicodeDecodeError("utf-8", raw, 0, 1, "could not decode table")


def _rc23_detect_delimiters(text: str):
    sample = "\n".join(str(text or "").splitlines()[:30])
    candidates = []
    try:
        sniffed = csv.Sniffer().sniff(sample, delimiters="\t;,|").delimiter
        candidates.append(sniffed)
    except Exception:
        pass
    candidates += [";", "\t", ",", "|"]
    # keep order, remove duplicates
    return list(dict.fromkeys(candidates))


def _rc23_score_table(df: pd.DataFrame) -> int:
    if df is None or df.empty or len(df.columns) <= 1:
        return -1
    aliases = set(_rc23_norm_header(x) for group in [
        _RC23_MEMBER_CASE_ALIASES, _RC23_MEMBER_ALIASES, _RC23_NODE_ALIASES,
        _RC23_CASE_ALIASES, _RC23_STORY_ALIASES, _RC23_NAME_ALIASES, _RC23_LENGTH_ALIASES,
        ["fx (kn)", "fy (kn)", "fz (kn)", "mx (knm)", "my (knm)", "mz (knm)", "material", "hy (cm)", "hz (cm)"],
    ] for x in group)
    cols = [_rc23_norm_header(c) for c in df.columns]
    recognised = sum(1 for c in cols if c in aliases)
    return recognised * 100 + len(df.columns) * 10 + min(len(df), 10)


def _rc23_read_csv_robust(path: str) -> pd.DataFrame:
    raw = Path(path).read_bytes()
    text = _rc23_decode_bytes(raw)
    # Remove embedded nulls only after correct decoding/fallback.
    text = text.replace("\x00", "")
    best_df = None
    best_score = -1
    best_err = None
    for sep in _rc23_detect_delimiters(text):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, engine="python")
            # Clean decoded header artefacts before scoring/returning.
            df.columns = [str(c).replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip() for c in df.columns]
            score = _rc23_score_table(df)
            if score > best_score:
                best_df, best_score = df, score
        except Exception as err:
            best_err = err
    if best_df is not None and best_score > 0:
        return best_df
    try:
        df = pd.read_csv(io.StringIO(text), sep=None, dtype=str, engine="python")
        df.columns = [str(c).replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip() for c in df.columns]
        return df
    except Exception as err:
        raise RuntimeError(f"CSV não reconhecido. Último erro: {best_err or err}") from err


def _rc23_read_table_file(path: str) -> pd.DataFrame:
    lower = str(path).lower()
    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str)
        df.columns = [str(c).replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip() for c in df.columns]
        return df
    if lower.endswith((".csv", ".txt")):
        return _rc23_read_csv_robust(path)
    try:
        df = pd.read_excel(path, dtype=str)
        df.columns = [str(c).replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip() for c in df.columns]
        return df
    except Exception:
        return _rc23_read_csv_robust(path)


# Re-export the robust reader under the previous RC22 names so GUI hooks and
# external scripts that already call them benefit from the fix.
_rc22_read_csv_robust = _rc23_read_csv_robust
_rc22_read_table_file = _rc23_read_table_file

# ---------------------------------------------------------------------------
# Robust column rename and member/node/case parsing
# ---------------------------------------------------------------------------


def _rc23_first_col(df: pd.DataFrame, aliases):
    lookup = {_rc23_norm_header(c): c for c in df.columns}
    for a in aliases:
        src = lookup.get(_rc23_norm_header(a))
        if src is not None:
            return src
    return None


def rename_known_columns_rc23(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    rename_map = {}
    mapping = {
        "member_case": _RC23_MEMBER_CASE_ALIASES,
        "member": _RC23_MEMBER_ALIASES,
        "node": _RC23_NODE_ALIASES,
        "case": _RC23_CASE_ALIASES,
        "story": _RC23_STORY_ALIASES,
        "name": _RC23_NAME_ALIASES,
        "length": _RC23_LENGTH_ALIASES,
        "fx": ["fx (kn)", "fx"],
        "fy": ["fy (kn)", "fy"],
        "fz": ["fz (kn)", "fz"],
        "mx": ["mx (knm)", "mx"],
        "my": ["my (knm)", "my"],
        "mz": ["mz (knm)", "mz"],
        "material": ["material", "betão", "betao", "concrete"],
        "hy": ["hy (cm)", "hy", "b (cm)", "b", "largura"],
        "hz": ["hz (cm)", "hz", "h (cm)", "h", "altura"],
        "vy": ["vy (cm)", "vy"],
        "vz": ["vz (cm)", "vz"],
        "vpy": ["vpy (cm)", "vpy"],
        "vpz": ["vpz (cm)", "vpz"],
        "ax": ["ax (cm2)", "ax", "ax (cm²)", "area", "área"],
        "ay": ["ay (cm2)", "ay", "ay (cm²)"],
        "az": ["az (cm2)", "az", "az (cm²)"],
        "ix": ["ix (cm4)", "ix", "ix (cm⁴)"],
        "iy": ["iy (cm4)", "iy", "iy (cm⁴)"],
        "iz": ["iz (cm4)", "iz", "iz (cm⁴)"],
    }
    used = set()
    for target, aliases in mapping.items():
        src = _rc23_first_col(out, aliases)
        if src is not None and src not in used:
            rename_map[src] = target
            used.add(src)
    return out.rename(columns=rename_map).copy()


rename_known_columns = rename_known_columns_rc23
rename_known_columns_rc22 = rename_known_columns_rc23


def _rc23_blank(value) -> bool:
    s = str(value if value is not None else "").strip()
    return s == "" or s.lower() in {"nan", "none", "null", "<na>", "-"}


def _rc23_split_member_case(value):
    s = str(value if value is not None else "").strip()
    s = s.replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "")
    s = s.replace("\\", "/")
    # "119/ 24/ 101 (C)" -> member=119 node=24 case=101
    m = re.match(r"^\s*([^/]+?)\s*/\s*([^/]+?)\s*/\s*([^/]+?)(?:\s|$)", s)
    if m:
        member = m.group(1).strip()
        node = m.group(2).strip()
        case = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(3).strip()).strip()
        return member, node, case
    m = re.match(r"^\s*([^/]+?)\s*/\s*([^/]+?)(?:\s|$)", s)
    if m:
        return m.group(1).strip(), m.group(2).strip(), ""
    return "", "", ""


def _rc23_parse_number_text(value):
    # Defer to existing safe_float, but first remove invisible BOM/nulls.
    if isinstance(value, str):
        value = value.replace("\ufeff", "").replace("\x00", "").strip()
    return safe_float(value, float("nan"))


def clean_dataframe_rc23(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    original = df.copy()
    original.columns = [str(c).replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip() for c in original.columns]
    out = rename_known_columns_rc23(original)
    out["__row_order"] = range(len(out))

    if "member_case" in out.columns:
        triples = out["member_case"].map(_rc23_split_member_case)
        for col, pos in [("member", 0), ("node", 1), ("case", 2)]:
            vals = triples.map(lambda x, p=pos: x[p])
            if col not in out.columns:
                out[col] = vals
            else:
                mask = out[col].map(_rc23_blank)
                out.loc[mask, col] = vals.loc[mask]
    else:
        for col in ["member", "node", "case"]:
            if col not in out.columns:
                out[col] = ""

    # Fallback for odd headers that are still present in original.
    for target, aliases in [("story", _RC23_STORY_ALIASES), ("name", _RC23_NAME_ALIASES), ("length", _RC23_LENGTH_ALIASES)]:
        if target not in out.columns:
            out[target] = ""
        src = _rc23_first_col(original, aliases)
        if src is not None:
            mask = out[target].map(_rc23_blank)
            try:
                out.loc[mask, target] = original.loc[mask, src].astype(str).values
            except Exception:
                pass

    if "material" not in out.columns:
        out["material"] = DEFAULT_CONCRETE_CLASS
    for c in ["member", "node", "case", "name", "story", "material"]:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].astype(str).map(lambda x: x.replace("\ufeff", "").replace("\x00", "").replace("ÿþ", "").replace("þÿ", "").strip())
        out.loc[out[c].str.lower().isin(["nan", "none", "null", "<na>"]), c] = ""
    mat_blank = out["material"].map(_rc23_blank)
    out.loc[mat_blank, "material"] = DEFAULT_CONCRETE_CLASS

    numeric_cols = ["fx", "fy", "fz", "mx", "my", "mz", "length", "hy", "hz", "vy", "vz", "vpy", "vpz", "ax", "ay", "az", "ix", "iy", "iz"]
    for c in numeric_cols:
        if c in out.columns:
            out[c] = out[c].map(_rc23_parse_number_text)
    if "length" not in out.columns:
        out["length"] = 0.0
    out["length"] = out["length"].map(lambda v: safe_float(v, 0.0))

    # Explicit fail-fast. It is safer to stop than to collapse the whole table by
    # prumada with blank member/case keys.
    if len(out) > 0:
        member_ok = int((out["member"].astype(str).str.strip() != "").sum()) if "member" in out.columns else 0
        case_ok = int((out["case"].astype(str).str.strip() != "").sum()) if "case" in out.columns else 0
        if member_ok == 0 or case_ok == 0:
            available = ", ".join(map(str, original.columns[:12]))
            raise ValueError(
                "Não foi possível extrair Barra/Nó/Caso. "
                "Verifique se a tabela tem a coluna 'Barra/Nó/Caso' ou colunas separadas Member/Node/Case. "
                f"Cabeçalhos detectados: {available}"
            )
    return out


clean_dataframe = clean_dataframe_rc23
clean_dataframe_rc22 = clean_dataframe_rc23

# ---------------------------------------------------------------------------
# Combine rows and reduce governing cases preserving every physical tramo
# ---------------------------------------------------------------------------


def combine_member_end_actions_rc23(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    for c in ["member", "node", "case", "name", "story", "material"]:
        if c not in work.columns:
            work[c] = ""
        work[c] = work[c].astype(str).str.strip()
    if "__row_order" not in work.columns:
        work["__row_order"] = range(len(work))

    # This grouping preserves a physical tramo and a simultaneous state at both
    # nodes. Do not group by name alone.
    group_cols = ["member", "case", "name", "story"]
    rows = []
    for _, grp in work.groupby(group_cols, dropna=False, sort=False):
        grp = grp.sort_values("__row_order")
        r1 = grp.iloc[0]
        r2 = grp.iloc[1] if len(grp) >= 2 else grp.iloc[0]
        row = {
            "member": r1.get("member", ""),
            "case": r1.get("case", ""),
            "name": r1.get("name", ""),
            "prumada": _pillar_prumada_v42(r1) if "_pillar_prumada_v42" in globals() else (r1.get("name", "") or r1.get("member", "")),
            "story": r1.get("story", ""),
            "node_i": r1.get("node", ""),
            "node_j": r2.get("node", ""),
            "member_case_i": f"{r1.get('member','')}/{r1.get('node','')}/{r1.get('case','')}",
            "member_case_j": f"{r2.get('member','')}/{r2.get('node','')}/{r2.get('case','')}",
            "length": safe_float(r1.get("length", r2.get("length", 0.0)), 0.0),
            "material": r1.get("material", "") or r2.get("material", "") or DEFAULT_CONCRETE_CLASS,
            "hy": safe_float(r1.get("hy", r2.get("hy", float("nan"))), float("nan")),
            "hz": safe_float(r1.get("hz", r2.get("hz", float("nan"))), float("nan")),
            "ax": safe_float(r1.get("ax", r2.get("ax", float("nan"))), float("nan")),
            "iy": safe_float(r1.get("iy", r2.get("iy", float("nan"))), float("nan")),
            "iz": safe_float(r1.get("iz", r2.get("iz", float("nan"))), float("nan")),
            "__row_order": safe_float(r1.get("__row_order", 0), 0),
            "n_nodes_found": int(len(grp)),
        }
        for force in ["fx", "fy", "fz", "mx", "my", "mz"]:
            row[f"{force}_i"] = safe_float(r1.get(force, 0.0), 0.0)
            row[f"{force}_j"] = safe_float(r2.get(force, 0.0), 0.0)
            row[force] = max(abs(row[f"{force}_i"]), abs(row[f"{force}_j"]))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["__row_order", "member", "case"], kind="mergesort").reset_index(drop=True)


combine_member_end_actions = combine_member_end_actions_rc23
combine_member_end_actions_rc22 = combine_member_end_actions_rc23


def _rc23_case_is_service(case_value) -> bool:
    s = str(case_value or "").strip()
    # In this workflow, 3xx combinations are treated as ELS/service combinations
    # and are not used for ULS reinforcement reduction. They remain available in
    # app.df_pair for the explicit ELS verification.
    if s.startswith("3"):
        return True
    try:
        if "extract_combination_number" in globals():
            cs = str(extract_combination_number(case_value)).strip()
            if cs.startswith("3"):
                return True
    except Exception:
        pass
    try:
        if "_case_is_service_v45" in globals():
            return bool(_case_is_service_v45(case_value))
    except Exception:
        pass
    return False


def _rc23_score_df(df: pd.DataFrame) -> pd.Series:
    vals = pd.DataFrame(index=df.index)
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        vals[c] = pd.to_numeric(df.get(c, pd.Series(index=df.index, dtype=float)), errors="coerce").abs().fillna(0.0)
    return 0.25 * vals["fx"] + vals["my"] + vals["mz"] + 0.20 * vals["mx"] + 0.08 * (vals["fy"] + vals["fz"])


def reduce_to_governing_cases_rc23(df: pd.DataFrame) -> pd.DataFrame:
    """Select governing ELU cases by physical tramo, preserving all members/storeys.

    The full df_pair remains available for ELS checks. The calculation input is
    reduced only after grouping by the physical member/story/section/material.
    """
    if df is None or df.empty:
        return df
    work = df.copy()
    for c in ["fx", "fy", "fz", "mx", "my", "mz"]:
        if c not in work.columns:
            work[c] = 0.0
        work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
    for c in ["member", "name", "story", "material", "hy", "hz"]:
        if c not in work.columns:
            work[c] = ""

    selected = set()
    group_cols = ["member", "name", "story", "material", "hy", "hz"]
    for _, grp0 in work.groupby(group_cols, dropna=False, sort=False):
        if grp0.empty:
            continue
        # Keep only ELU-type cases for the dimensioning reduction, but the full
        # service case remains in app.df_pair for apply_service_combination_override.
        case_series = grp0.get("case", pd.Series(index=grp0.index, dtype=str)).astype(str)
        g = grp0[~case_series.map(_rc23_case_is_service)].copy()
        if g.empty:
            g = grp0.copy()
        score = _rc23_score_df(g)
        selected.add(score.idxmax())
        fx = g["fx"].abs().replace(0, 1e-9)
        selectors = [
            g["fx"].abs(),
            g["my"].abs(),
            g["mz"].abs(),
            g["mx"].abs(),
            g["fy"].abs() + g["fz"].abs(),
            (g["my"].abs() + g["mz"].abs()) / fx,
            g["my"].abs() / fx,
            g["mz"].abs() / fx,
        ]
        for ser in selectors:
            try:
                if not ser.empty:
                    selected.add(ser.idxmax())
            except Exception:
                pass
    out = work.loc[sorted(selected)].copy()
    order = [c for c in ["name", "story", "member", "case"] if c in out.columns]
    if order:
        out = out.sort_values(order, kind="mergesort")
    return out.reset_index(drop=True)


reduce_to_governing_cases = reduce_to_governing_cases_rc23

# ---------------------------------------------------------------------------
# GUI/file-import hooks and quality feedback
# ---------------------------------------------------------------------------


def import_file_rc23(self):
    path = filedialog.askopenfilename(
        title="Importar tabela",
        filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv *.txt"), ("Excel", "*.xlsx *.xls"), ("CSV", "*.csv *.txt"), ("Todos", "*.*")],
    )
    if not path:
        return
    try:
        df = _rc23_read_table_file(path)
        self.input_file_path = path
        self.load_df(df, source=os.path.basename(path))
        try:
            if hasattr(self, "populate_editable_grid"):
                self.populate_editable_grid(df)
        except Exception:
            pass
    except Exception as err:
        messagebox.showerror("Erro", f"Não foi possível importar o ficheiro.\n\n{err}")


try:
    ColumnsEC2App.import_file = import_file_rc23
except Exception:
    pass


_rc23_prev_load_df = getattr(ColumnsEC2App, "load_df", None)


def _load_df_rc23(self, df: pd.DataFrame, source: str = ""):
    if callable(_rc23_prev_load_df):
        _rc23_prev_load_df(self, df, source)
    else:
        self.df_raw = df.copy()
        self.df_clean = clean_dataframe(df)
        self.df_pair = combine_member_end_actions(self.df_clean)
    # Additional status line with physical tramo count and ELS availability.
    try:
        pairs = getattr(self, "df_pair", pd.DataFrame())
        if pairs is not None and not pairs.empty:
            physical = pairs[[c for c in ["member", "name", "story"] if c in pairs.columns]].drop_duplicates().shape[0]
            cases = set(pairs.get("case", pd.Series(dtype=str)).astype(str).str.strip())
            selected_case = ""
            try:
                v = getattr(self, "var_service_case", None)
                selected_case = str(v.get() if hasattr(v, "get") else (v or "")).strip()
            except Exception:
                selected_case = ""
            selected_case_found = bool(selected_case and selected_case in cases)
            bad_pairs = int((pairs.get("n_nodes_found", pd.Series(dtype=float)).fillna(0).astype(float) < 2).sum()) if "n_nodes_found" in pairs.columns else 0
            msg = f"Tabela carregada ({source}): {len(getattr(self, 'df_clean', pd.DataFrame()))} linhas; {len(pairs)} pares member/case; {physical} tramos físicos"
            if selected_case_found:
                msg += f"; combinacao ELS {selected_case} detectada"
            if bad_pairs:
                msg += f"; {bad_pairs} pares sem dois nós"
            self.status_var.set(msg + ".")
    except Exception:
        pass


try:
    ColumnsEC2App.load_df = _load_df_rc23
except Exception:
    pass

# ---------------------------------------------------------------------------
# ELS lookup refinement: map by member first; fallback by name/story if needed
# ---------------------------------------------------------------------------

_rc23_prev_apply_service_combination_override = globals().get("apply_service_combination_override_v4", None)


def apply_service_combination_override_v4(app, results: pd.DataFrame, input_df: pd.DataFrame) -> pd.DataFrame:
    selected = getattr(app, "var_service_case", tk.StringVar(value="")).get().strip() if hasattr(app, "var_service_case") else ""
    if results is None or results.empty or not selected:
        return _rc23_prev_apply_service_combination_override(app, results, input_df) if callable(_rc23_prev_apply_service_combination_override) else results
    pairs = getattr(app, "df_pair", pd.DataFrame())
    if pairs is None or pairs.empty:
        return _rc23_prev_apply_service_combination_override(app, results, input_df) if callable(_rc23_prev_apply_service_combination_override) else results
    pairs = pairs.copy()
    pairs["_case_str"] = pairs.get("case", pd.Series(index=pairs.index, dtype=str)).astype(str).str.strip()
    try:
        pairs["_comb_str"] = pairs["case"].map(extract_combination_number).astype(str)
    except Exception:
        pairs["_comb_str"] = pairs["_case_str"]
    target = str(selected).strip()
    pair_sel = pairs[(pairs["_case_str"] == target) | (pairs["_comb_str"] == target)].copy()
    if pair_sel.empty:
        out = results.copy()
        out["service_case_source"] = f"combinação ELS {target} não encontrada"
        out["service_status"] = "ELS não avaliado — combinação indicada não encontrada"
        return out
    # Reuse the validated v4 implementation now that df_pair is parsed, then
    # clean any missed rows using the name/story fallback.
    out = _rc23_prev_apply_service_combination_override(app, results, input_df) if callable(_rc23_prev_apply_service_combination_override) else results.copy()
    if out is None or out.empty:
        return out
    out = out.copy()
    missing = out.get("service_status", pd.Series("", index=out.index)).astype(str).str.contains("sem linha|não encontrada|nao encontrada", case=False, na=False, regex=True)
    if not missing.any():
        return out
    pair_by_tramo = {}
    for _, p in pair_sel.iterrows():
        key = (str(p.get("name", "")), str(p.get("story", "")))
        pair_by_tramo.setdefault(key, p)
    for idx, r in out[missing].iterrows():
        key = (str(r.get("name", "")), str(r.get("story", "")))
        p = pair_by_tramo.get(key)
        if p is None:
            continue
        try:
            material = str(r.get("material", DEFAULT_CONCRETE_CLASS) or DEFAULT_CONCRETE_CLASS)
            fck = parse_concrete_strength(material)
            cp = concrete_props(fck)
            b_mm = _finite(r.get("b_cm"))*10.0
            h_mm = _finite(r.get("h_cm"))*10.0
            iy = _finite(p.get("iy"), 0.0)*10000.0
            iz = _finite(p.get("iz"), 0.0)*10000.0
            if iy <= 0: iy = b_mm*h_mm**3/12.0
            if iz <= 0: iz = h_mm*b_mm**3/12.0
            n = max(abs(_finite(p.get("fx_i"))), abs(_finite(p.get("fx_j"))))
            my = max(abs(_finite(p.get("my_i"))), abs(_finite(p.get("my_j"))))
            mz = max(abs(_finite(p.get("mz_i"))), abs(_finite(p.get("mz_j"))))
            els = elastic_service_check_v4(n, my, mz, b_mm, h_mm, iy, iz, _finite(r.get("as_prov_mm2")), fck, _finite(app.var_fyk.get(),500), cp["Ecm"], cp["fctm"])
            for k, v in els.items():
                out.at[idx, k] = v
            out.at[idx, "service_combination"] = target
            out.at[idx, "service_case_source"] = f"combinação indicada pelo utilizador: {target}"
            out.at[idx, "service_n_kN"] = n
            out.at[idx, "service_my_kNm"] = my
            out.at[idx, "service_mz_kNm"] = mz
        except Exception:
            pass
    return out

# Translation/update metadata labels where available.
try:
    _RC13_EN_TERMS.update({"v0.9 RC23 Modular": "v0.9 RC23 Modular"})
except Exception:
    pass
