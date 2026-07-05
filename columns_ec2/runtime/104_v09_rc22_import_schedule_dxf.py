# -*- coding: utf-8 -*-
"""ColumnsEC2 v0.9 RC22 — robust import, tramo schedule and full DXF export.

RC22 fixes three practical issues found in RC21:

- CSV/XLSX imports now recognise Portuguese headers such as Barra/Nó/Caso and
  Comprimento (m), and also support separate Member/Node/Case columns;
- column schedules are rebuilt from member + storey + section, not collapsed to
  one row per column line when the member/case key was not parsed;
- DXF export no longer truncates the column schedule to the first 32 columns or
  24 storeys; it paginates the drawing into successive blocks.
"""

from __future__ import annotations

import csv
import io
import math
import os
import re
from pathlib import Path

import pandas as pd

APP_VERSION = "v0.9 RC22 Modular"

# ---------------------------------------------------------------------------
# Robust header aliases and import helpers
# ---------------------------------------------------------------------------

_RC22_MEMBER_CASE_ALIASES = [
    "member/node/case", "member/n/case", "member/node/caso", "member/nó/caso", "member/no/caso",
    "member/n", "member/node", "member/nó", "member/no",
    "barra/nó/caso", "barra/no/caso", "barra/n/caso", "barra/nó", "barra/no",
    "barra/nó/caso (c)", "barra/no/caso (c)", "barra no caso", "barra nó caso",
    "elemento/nó/caso", "elemento/no/caso", "elemento/n/caso",
]
_RC22_LENGTH_ALIASES = [
    "length (m)", "length(m)", "length", "comprimento (m)", "comprimento(m)", "comprimento", "l (m)", "l(m)", "l",
]
_RC22_STORY_ALIASES = ["story", "storey", "piso", "andar", "andares", "level", "floor", "pavimento", "nivel", "nível"]
_RC22_MEMBER_ALIASES = ["member", "barra", "elemento", "bar", "membro"]
_RC22_NODE_ALIASES = ["node", "nó", "no", "n", "nodo"]
_RC22_CASE_ALIASES = ["case", "caso", "combinação", "combinacao", "comb", "load case", "loadcase"]

try:
    # Do not use the single header "member" as a combined member/node/case field;
    # that was the source of the RC21 collapse to one result per prumada when a
    # CSV/XLSX used separate Member, Node and Case columns.
    COLUMN_ALIASES.update({
        "member_case": _RC22_MEMBER_CASE_ALIASES,
        "member": _RC22_MEMBER_ALIASES,
        "node": _RC22_NODE_ALIASES,
        "case": _RC22_CASE_ALIASES,
        "length": _RC22_LENGTH_ALIASES,
        "story": _RC22_STORY_ALIASES,
        "name": ["name", "nome", "prumada", "pilar", "column", "column line", "linha de pilar"],
    })
except Exception:
    pass


def _rc22_norm_header(value: object) -> str:
    try:
        s = normalize_text(value)
    except Exception:
        s = str(value or "").strip().lower()
    s = s.replace("º", "o").replace("ª", "a")
    s = s.replace("\ufeff", "").strip()
    return s


def _rc22_is_blank(value: object) -> bool:
    s = str(value if value is not None else "").strip()
    return s == "" or s.lower() in {"nan", "none", "null", "-"}


def _rc22_first_existing_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    lookup = {_rc22_norm_header(c): c for c in df.columns}
    for a in aliases:
        c = lookup.get(_rc22_norm_header(a))
        if c is not None:
            return c
    return None


_rc22_prev_rename_known_columns = globals().get("rename_known_columns", None)


def rename_known_columns_rc22(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known columns without confusing separate Member with Member/Node/Case."""
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    norm_to_original = {_rc22_norm_header(c): c for c in out.columns}
    rename_map = {}

    # Combined field first, but only for explicit combined headers.
    for alias in _RC22_MEMBER_CASE_ALIASES:
        src = norm_to_original.get(_rc22_norm_header(alias))
        if src is not None:
            rename_map[src] = "member_case"
            break

    alias_sets = {
        "member": _RC22_MEMBER_ALIASES,
        "node": _RC22_NODE_ALIASES,
        "case": _RC22_CASE_ALIASES,
        "length": _RC22_LENGTH_ALIASES,
        "story": _RC22_STORY_ALIASES,
        "name": ["name", "nome", "prumada", "pilar", "column", "column line", "linha de pilar"],
        "fx": ["fx (kn)", "fx", "n", "n (kn)", "ned", "ned (kn)"],
        "fy": ["fy (kn)", "fy"],
        "fz": ["fz (kn)", "fz"],
        "mx": ["mx (knm)", "mx", "m x", "torção", "torcao"],
        "my": ["my (knm)", "my", "m y", "my ed", "myed"],
        "mz": ["mz (knm)", "mz", "m z", "mz ed", "mzed"],
        "material": ["material", "betão", "betao", "concrete"],
        "hy": ["hy (cm)", "hy", "b (cm)", "b", "largura", "dim y", "dim_y"],
        "hz": ["hz (cm)", "hz", "h (cm)", "h", "altura", "dim z", "dim_z"],
        "vy": ["vy (cm)", "vy"], "vz": ["vz (cm)", "vz"],
        "vpy": ["vpy (cm)", "vpy"], "vpz": ["vpz (cm)", "vpz"],
        "ax": ["ax (cm2)", "ax", "a (cm2)", "area", "área"],
        "ay": ["ay (cm2)", "ay"], "az": ["az (cm2)", "az"],
        "ix": ["ix (cm4)", "ix"], "iy": ["iy (cm4)", "iy"], "iz": ["iz (cm4)", "iz"],
    }
    for target, aliases in alias_sets.items():
        if target == "member_case":
            continue
        if target in rename_map.values():
            continue
        for alias in aliases:
            src = norm_to_original.get(_rc22_norm_header(alias))
            if src is not None and src not in rename_map:
                rename_map[src] = target
                break
    return out.rename(columns=rename_map).copy()


rename_known_columns = rename_known_columns_rc22


_rc22_prev_clean_dataframe = globals().get("clean_dataframe", None)


def _rc22_split_member_case_value(value: object):
    s = str(value if value is not None else "").strip()
    s = s.replace("\\", "/")
    # Examples: "119/ 24/ 101 (C)", "119/24/101", "119 / 24".
    m = re.match(r"^\s*([^/]+?)\s*/\s*([^/]+?)\s*/\s*([^/]+?)(?:\s|$)", s)
    if m:
        case = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(3).strip())
        return m.group(1).strip(), m.group(2).strip(), case.strip()
    m = re.match(r"^\s*([^/]+?)\s*/\s*([^/]+?)(?:\s|$)", s)
    if m:
        return m.group(1).strip(), m.group(2).strip(), ""
    return s, "", ""


def clean_dataframe_rc22(df: pd.DataFrame) -> pd.DataFrame:
    """Robust import cleaning for combined and separate member/node/case fields."""
    if df is None:
        return pd.DataFrame()
    original = df.copy()
    out = rename_known_columns_rc22(original)
    out["__row_order"] = range(len(out))

    # Fill member/node/case from a combined field only where explicit values do not exist.
    if "member_case" in out.columns:
        triples = out["member_case"].map(_rc22_split_member_case_value)
        if "member" not in out.columns:
            out["member"] = triples.map(lambda x: x[0])
        else:
            mask = out["member"].astype(str).str.strip().isin(["", "nan", "None", "none"])
            out.loc[mask, "member"] = triples.map(lambda x: x[0]).loc[mask]
        if "node" not in out.columns:
            out["node"] = triples.map(lambda x: x[1])
        else:
            mask = out["node"].astype(str).str.strip().isin(["", "nan", "None", "none"])
            out.loc[mask, "node"] = triples.map(lambda x: x[1]).loc[mask]
        if "case" not in out.columns:
            out["case"] = triples.map(lambda x: x[2])
        else:
            mask = out["case"].astype(str).str.strip().isin(["", "nan", "None", "none"])
            out.loc[mask, "case"] = triples.map(lambda x: x[2]).loc[mask]
    else:
        for c in ["member", "node", "case"]:
            if c not in out.columns:
                out[c] = ""

    for c in ["member", "node", "case", "name", "story", "material"]:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].astype(str).str.strip()
        out.loc[out[c].str.lower().isin(["nan", "none", "null"]), c] = ""

    # Fallback for name/story from original headers that may not have been renamed.
    if original is not None and not original.empty:
        for target, aliases in [("story", _RC22_STORY_ALIASES), ("name", ["name", "nome", "prumada", "pilar", "column", "column line"]), ("length", _RC22_LENGTH_ALIASES)]:
            src = _rc22_first_existing_column(original, aliases)
            if src is not None:
                try:
                    mask = out[target].astype(str).str.strip().isin(["", "nan", "None", "none"]) if target in out.columns else pd.Series(True, index=out.index)
                    vals = original[src].reset_index(drop=True)
                    if target not in out.columns:
                        out[target] = ""
                    out.loc[mask, target] = vals.loc[mask].astype(str).values
                except Exception:
                    pass

    numeric_cols = ["fx", "fy", "fz", "mx", "my", "mz", "length", "hy", "hz", "vy", "vz", "vpy", "vpz", "ax", "ay", "az", "ix", "iy", "iz"]
    for c in numeric_cols:
        if c in out.columns:
            out[c] = out[c].map(lambda v: safe_float(v, float("nan")))
    # Length is needed for second-order checks; leave missing as 0 only after parsing.
    if "length" not in out.columns:
        out["length"] = 0.0
    out["length"] = out["length"].map(lambda v: safe_float(v, 0.0))

    return out


clean_dataframe = clean_dataframe_rc22


_rc22_prev_combine_member_end_actions = globals().get("combine_member_end_actions", None)


def combine_member_end_actions_rc22(df: pd.DataFrame) -> pd.DataFrame:
    """Build one member/case(/storey/name) row while preserving all physical tramos."""
    if df is None or df.empty:
        return df
    work = df.copy()
    for c in ["member", "node", "case", "name", "story"]:
        if c not in work.columns:
            work[c] = ""
    if "__row_order" not in work.columns:
        work["__row_order"] = range(len(work))

    # Never group only by name. If member/case were not parsed, use row pairs as
    # a last-resort key so the import quality report exposes the issue instead
    # of silently collapsing the whole column line.
    if work["member"].astype(str).str.strip().replace({"nan": ""}).eq("").all() and work["case"].astype(str).str.strip().replace({"nan": ""}).eq("").all():
        work["_rc22_pair_key"] = (pd.to_numeric(work["__row_order"], errors="coerce").fillna(0).astype(int) // 2).astype(str)
    else:
        work["_rc22_pair_key"] = work["member"].astype(str) + "|" + work["case"].astype(str) + "|" + work["name"].astype(str) + "|" + work["story"].astype(str)

    rows = []
    group_cols = ["member", "case", "name", "story"]
    if work["member"].astype(str).str.strip().eq("").all() and work["case"].astype(str).str.strip().eq("").all():
        group_cols = ["_rc22_pair_key", "name", "story"]

    for _, grp in work.groupby(group_cols, dropna=False, sort=False):
        grp = grp.sort_values("__row_order")
        r1 = grp.iloc[0]
        r2 = grp.iloc[1] if len(grp) >= 2 else grp.iloc[0]
        name = r1.get("name", "") if not _rc22_is_blank(r1.get("name", "")) else r2.get("name", "")
        story = r1.get("story", "") if not _rc22_is_blank(r1.get("story", "")) else r2.get("story", "")
        member = r1.get("member", "")
        case = r1.get("case", "")
        row = {
            "member": member,
            "case": case,
            "name": name,
            "prumada": _pillar_prumada_v42(r1) if "_pillar_prumada_v42" in globals() else (name if not _rc22_is_blank(name) else member),
            "story": story,
            "node_i": r1.get("node", ""),
            "node_j": r2.get("node", ""),
            "member_case_i": f"{member}/{r1.get('node','')}/{case}",
            "member_case_j": f"{r2.get('member', member)}/{r2.get('node','')}/{r2.get('case', case)}",
            "fx_i": safe_float(r1.get("fx", 0.0), 0.0), "fx_j": safe_float(r2.get("fx", 0.0), 0.0),
            "fy_i": safe_float(r1.get("fy", 0.0), 0.0), "fy_j": safe_float(r2.get("fy", 0.0), 0.0),
            "fz_i": safe_float(r1.get("fz", 0.0), 0.0), "fz_j": safe_float(r2.get("fz", 0.0), 0.0),
            "mx_i": safe_float(r1.get("mx", 0.0), 0.0), "mx_j": safe_float(r2.get("mx", 0.0), 0.0),
            "my_i": safe_float(r1.get("my", 0.0), 0.0), "my_j": safe_float(r2.get("my", 0.0), 0.0),
            "mz_i": safe_float(r1.get("mz", 0.0), 0.0), "mz_j": safe_float(r2.get("mz", 0.0), 0.0),
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
        row["fx"] = max(abs(row["fx_i"]), abs(row["fx_j"]))
        row["fy"] = max(abs(row["fy_i"]), abs(row["fy_j"]))
        row["fz"] = max(abs(row["fz_i"]), abs(row["fz_j"]))
        row["mx"] = max(abs(row["mx_i"]), abs(row["mx_j"]))
        row["my"] = max(abs(row["my_i"]), abs(row["my_j"]))
        row["mz"] = max(abs(row["mz_i"]), abs(row["mz_j"]))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["__row_order", "member", "case"], kind="mergesort").reset_index(drop=True)


combine_member_end_actions = combine_member_end_actions_rc22


def _rc22_read_csv_robust(path: str) -> pd.DataFrame:
    raw = Path(path).read_bytes()
    decoded = None
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            decoded = raw.decode(enc)
            break
        except Exception as err:
            last_err = err
    if decoded is None:
        raise last_err or UnicodeDecodeError("utf-8", raw, 0, 1, "could not decode CSV")
    text = decoded.replace("\x00", "")
    sample = "\n".join(text.splitlines()[:20])
    candidates = []
    try:
        sniffed = csv.Sniffer().sniff(sample, delimiters="\t;,|").delimiter
        candidates.append(sniffed)
    except Exception:
        pass
    candidates += ["\t", ";", ",", "|"]
    candidates = list(dict.fromkeys(candidates))
    best_df = None
    best_score = -1
    best_err = None
    for sep in candidates:
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, engine="python")
            cols = [_rc22_norm_header(c) for c in df.columns]
            recognised = sum(1 for c in cols for aliases in [_RC22_MEMBER_CASE_ALIASES, _RC22_MEMBER_ALIASES, _RC22_CASE_ALIASES, _RC22_LENGTH_ALIASES, _RC22_STORY_ALIASES] if c in [_rc22_norm_header(a) for a in aliases])
            score = len(df.columns) * 10 + recognised * 20 + min(len(df), 5)
            if len(df.columns) > 1 and score > best_score:
                best_df, best_score = df, score
        except Exception as err:
            best_err = err
    if best_df is not None:
        return best_df
    # Last fallback: try pandas automatic separator.
    try:
        return pd.read_csv(io.StringIO(text), sep=None, dtype=str, engine="python")
    except Exception as err:
        raise RuntimeError(f"CSV não reconhecido. Último erro: {best_err or err}") from err


def _rc22_read_table_file(path: str) -> pd.DataFrame:
    p = str(path)
    lower = p.lower()
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(p, dtype=str)
    if lower.endswith(".csv") or lower.endswith(".txt"):
        return _rc22_read_csv_robust(p)
    # Try Excel first for unknown extensions, then robust CSV.
    try:
        return pd.read_excel(p, dtype=str)
    except Exception:
        return _rc22_read_csv_robust(p)


def parse_pasted_table_rc22(text: str) -> pd.DataFrame:
    text = str(text or "").strip()
    if not text:
        return pd.DataFrame()
    # Try robust CSV/table delimiters first.
    for sep in ("\t", ";", ",", "|"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, engine="python")
            if len(df.columns) > 1 and len(df) > 0:
                return df
        except Exception:
            pass
    # Preserve the specialised space-aligned parser from v47 when available.
    try:
        df = _parse_space_aligned_structural_table_v47(text)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    try:
        df = _parse_whitespace_member_table_v46(text)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    # Generic fallback: split on repeated spaces.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return pd.DataFrame()
    rows = [re.split(r"\s{2,}", line) for line in lines]
    header, body = rows[0], rows[1:]
    width = len(header)
    body = [r[:width] + [""] * max(0, width - len(r)) for r in body]
    return pd.DataFrame(body, columns=header)


parse_pasted_table = parse_pasted_table_rc22


# GUI import hook.
def import_file_rc22(self):
    path = filedialog.askopenfilename(
        title="Importar tabela",
        filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv *.txt"), ("Excel", "*.xlsx *.xls"), ("CSV", "*.csv *.txt"), ("Todos", "*.*")],
    )
    if not path:
        return
    try:
        df = _rc22_read_table_file(path)
        self.input_file_path = path
        self.load_df(df, source=os.path.basename(path))
        # If the editable grid exists, show the imported table there as well.
        try:
            if hasattr(self, "populate_editable_grid"):
                self.populate_editable_grid(df)
        except Exception:
            pass
    except Exception as err:
        messagebox.showerror("Erro", f"Não foi possível importar o ficheiro.\n\n{err}")


try:
    ColumnsEC2App.import_file = import_file_rc22
except Exception:
    pass


# ---------------------------------------------------------------------------
# ELS missing-combination policy and text sanitation
# ---------------------------------------------------------------------------

_rc22_prev_apply_service_combination_override = globals().get("apply_service_combination_override_v4", None)


def apply_service_combination_override_v4(app, results: pd.DataFrame, input_df: pd.DataFrame) -> pd.DataFrame:
    out = _rc22_prev_apply_service_combination_override(app, results, input_df) if callable(_rc22_prev_apply_service_combination_override) else results
    if out is None or getattr(out, "empty", True):
        return out
    out = out.copy()
    mask = out.get("service_status", pd.Series("", index=out.index)).astype(str).str.contains("combina", case=False, na=False) & out.get("service_status", pd.Series("", index=out.index)).astype(str).str.contains("não encontrada|nao encontrada", case=False, na=False, regex=True)
    if mask.any():
        out.loc[mask, "service_status"] = "ELS não avaliado — combinação indicada não encontrada"
        out.loc[mask, "service_crack_status"] = "Não avaliado"
        out.loc[mask, "service_note"] = "A combinação ELS indicada não existe na tabela importada; o estado resistente ELU não é penalizado por este motivo."
    return out


_rc22_prev_v65_status_from_row = globals().get("_v65_status_from_row", None)


def _rc22_is_missing_els(row) -> bool:
    txt = str(row.get("service_status", "") or "").lower()
    src = str(row.get("service_case_source", "") or "").lower()
    blob = txt + " " + src
    return ("els" in blob or "combina" in blob) and ("não encontrada" in blob or "nao encontrada" in blob)


def _v65_status_from_row(row):
    base = _rc22_prev_v65_status_from_row(row) if callable(_rc22_prev_v65_status_from_row) else {}
    if not isinstance(base, dict):
        return base
    if not _rc22_is_missing_els(row):
        return base
    base = dict(base)
    base["estado_els"] = "Não avaliado"
    # Recompute global state without treating the absent ELS combination as a warning.
    resistant = base.get("estado_resistente", "Não avaliado")
    corte = base.get("estado_corte", "Não avaliado")
    tor = base.get("estado_torcao", "Não avaliado")
    det = base.get("estado_pormenorizacao", "OK")
    blocking = [resistant, corte, tor, det]
    warning = [resistant, corte, tor, det]
    if "Falha" in blocking:
        glob = "Falha"
    elif "Pré-dimensionado" in warning:
        glob = "Pré-dimensionado"
    elif "Aviso" in warning:
        glob = "Aviso"
    else:
        glob = "OK"
    base["estado_global"] = glob
    notes = []
    if resistant == "Falha":
        notes.append("resistência N-My-Mz não verificada")
    if corte == "Aviso":
        notes.append("corte requer verificação/dimensionamento de armadura transversal")
    if corte == "Falha":
        notes.append("corte excede limite resistente")
    if tor == "Aviso":
        notes.append("torção requer verificação/dimensionamento complementar")
    if tor == "Falha":
        notes.append("torção excede limite resistente")
    if det == "Aviso":
        notes.append("pormenorização construtiva a confirmar")
    if det == "Falha":
        notes.append("pormenorização bloqueante")
    if not notes:
        notes.append("Sem reservas relevantes no âmbito das verificações efectuadas. ELS não avaliado: combinação indicada não encontrada.")
    else:
        notes.append("ELS não avaliado: combinação indicada não encontrada")
    base["decisao_tecnica"] = "; ".join(notes)
    return base


_rc22_prev_v65_apply_module_statuses = globals().get("_v65_apply_module_statuses", None)


def _rc22_sanitise_text_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy()
    text_cols = [c for c in out.columns if out[c].dtype == object]
    for c in text_cols:
        try:
            out[c] = out[c].map(lambda v: re.sub(r"^(?:nan|None|null)\s*;\s*", "", str(v)) if not pd.isna(v) else v)
            out[c] = out[c].map(lambda v: re.sub(r"\s*;\s*(?:nan|None|null)\s*$", "", str(v)) if not pd.isna(v) else v)
        except Exception:
            pass
    return out


def _v65_apply_module_statuses(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or getattr(df, "empty", True):
        return pd.DataFrame() if df is None else df
    out = df.copy()
    try:
        if "_v64_eta_col" in globals():
            out = _v64_eta_col(out)
    except Exception:
        pass
    rows = []
    for _, r in out.iterrows():
        rows.append(_v65_status_from_row(r))
    st = pd.DataFrame(rows, index=out.index)
    for c in st.columns:
        out[c] = st[c]
    out["status"] = out["estado_global"]
    if "η_NMyMz" not in out.columns and "utilizacao" in out.columns:
        out["η_NMyMz"] = out["utilizacao"]
    if "eta_NMyMz" not in out.columns and "η_NMyMz" in out.columns:
        out["eta_NMyMz"] = out["η_NMyMz"]
    return _rc22_sanitise_text_df(out)


# ---------------------------------------------------------------------------
# Schedule builder: guarantee physical member+storey schedule after import fix
# ---------------------------------------------------------------------------

_rc22_prev_build_tramo_schedule = globals().get("_rc21_build_tramo_schedule", globals().get("_rc19_build_tramo_schedule", None))


def _rc22_build_initial_schedule(results: pd.DataFrame) -> pd.DataFrame:
    # RC18 already does the right physical grouping once member/case/story are parsed.
    if "_rc18_initial_schedule" in globals():
        base = _rc18_initial_schedule(results)
    elif callable(_rc22_prev_build_tramo_schedule):
        base = _rc22_prev_build_tramo_schedule(results)
    else:
        base = pd.DataFrame()
    return base


def _rc22_build_tramo_schedule(results: pd.DataFrame) -> pd.DataFrame:
    base = _rc22_build_initial_schedule(results)
    try:
        if "_rc19_postprocess_schedule" in globals():
            base = _rc19_postprocess_schedule(base)
    except Exception:
        pass
    try:
        if "_rc21_stack_rationalise" in globals():
            base = _rc21_stack_rationalise(base)
    except Exception:
        pass
    return _rc22_sanitise_text_df(base)


def _rc22_build_summary_by_member(self, results: pd.DataFrame) -> pd.DataFrame:
    return _rc22_build_tramo_schedule(results)


try:
    ColumnsEC2App.build_summary_by_member = _rc22_build_summary_by_member
    _v682_build_tramo_schedule = _rc22_build_tramo_schedule
    _v683_build_tramo_schedule = _rc22_build_tramo_schedule
    _rc17_build_tramo_schedule = _rc22_build_tramo_schedule
    _rc18_build_tramo_schedule = _rc22_build_tramo_schedule
    _rc19_build_tramo_schedule = _rc22_build_tramo_schedule
    _rc21_build_tramo_schedule = _rc22_build_tramo_schedule
except Exception:
    pass


# ---------------------------------------------------------------------------
# DXF export: paginate all prumadas/levels instead of truncating at 32/24
# ---------------------------------------------------------------------------


def _rc22_draw_schedule_block(parts, work: pd.DataFrame, prumadas: list[str], levels: list[str], ox0: float, oy0: float, lang: str, block_no: int, n_blocks: int):
    en = (lang == LANG_EN)
    cell_w, cell_h = 1450.0, 1180.0
    level_w = 420.0
    margin_x, base_y = ox0 + 480.0, oy0
    title_y = base_y + len(levels) * cell_h + 780.0
    header_y = base_y + len(levels) * cell_h + 420.0
    parts.append(_dxf_text(margin_x, title_y, ("COLUMN SCHEDULE" if en else "QUADRO DE PILARES") + f" — {block_no}/{n_blocks} — UNITS: mm", 52, "COLUMNS_TEXT"))
    parts.append(_dxf_text(margin_x, title_y - 130, "Columns = column lines; rows = storeys/segments." if en else "Colunas = prumadas; linhas = pisos/tramos.", 25, "COLUMNS_TEXT"))
    parts.append(_dxf_text(margin_x, title_y - 195, "Legend: concrete=outline | bars=circles | links=inner contour | dimensions in mm" if en else "Legenda: betão=contorno | varões=círculos | estribos=contorno interior | cotas em mm", 24, "COLUMNS_TEXT"))
    parts.append(_dxf_text(ox0, header_y, "Storey" if en else "Piso", 34, "COLUMNS_TABLE"))
    for c, pr in enumerate(prumadas):
        x0 = margin_x + c * cell_w
        parts.append(_dxf_text(x0 + cell_w * 0.38, header_y, str(pr), 42, "COLUMNS_TABLE"))
    total_w = level_w + len(prumadas) * cell_w
    total_h = len(levels) * cell_h
    left, bottom, top, right = ox0, base_y, base_y + total_h, ox0 + total_w
    parts += [_dxf_line(left, bottom, right, bottom, "COLUMNS_TABLE"), _dxf_line(right, bottom, right, top, "COLUMNS_TABLE"), _dxf_line(right, top, left, top, "COLUMNS_TABLE"), _dxf_line(left, top, left, bottom, "COLUMNS_TABLE"), _dxf_line(ox0 + level_w, bottom, ox0 + level_w, top, "COLUMNS_TABLE")]
    for c in range(len(prumadas) + 1):
        x = ox0 + level_w + c * cell_w
        parts.append(_dxf_line(x, bottom, x, top, "COLUMNS_TABLE"))
    for r in range(len(levels) + 1):
        y = base_y + r * cell_h
        parts.append(_dxf_line(left, y, right, y, "COLUMNS_TABLE"))
    lookup = {}
    for _, rr in work.iterrows():
        key = (str(rr.get("Prumada", "")), str(rr.get("Piso", "")))
        if key not in lookup:
            lookup[key] = rr
        else:
            try:
                old = pd.DataFrame([lookup[key]])
                new = pd.DataFrame([rr])
                if float(_v682_governing_score_df(new).iloc[0]) > float(_v682_governing_score_df(old).iloc[0]):
                    lookup[key] = rr
            except Exception:
                pass
    for r_i, level in enumerate(levels):
        y0 = base_y + r_i * cell_h
        parts.append(_dxf_text(ox0 + 25, y0 + cell_h * 0.47, str(level), 27, "COLUMNS_TABLE"))
        for c, pr in enumerate(prumadas):
            x0 = ox0 + level_w + c * cell_w
            row = lookup.get((str(pr), str(level)))
            if row is None:
                cx, cy = x0 + cell_w / 2.0, y0 + cell_h / 2.0
                parts.append(_dxf_line(cx - 120, cy, cx + 120, cy, "COLUMNS_TEXT"))
                continue
            b = _rc16_num(row.get("b_cm", row.get("hy", 0.0))) * 10.0
            h = _rc16_num(row.get("h_cm", row.get("hz", 0.0))) * 10.0
            d = _rc16_diameter_mm(row) if _rc16_is_circular_row(row) else max(b, h)
            if max(b, h, d) <= 0:
                parts.append(_dxf_text(x0 + 25, y0 + cell_h - 120, "No geometry" if en else "Sem geometria", 26, "COLUMNS_TEXT"))
                continue
            ox = x0 + cell_w / 2.0
            oy = y0 + cell_h / 2.0 + 70.0
            scale = min(1.0, 620.0 / max(b, h, d, 1.0))
            if _rc16_is_circular_row(row):
                _rc16_draw_circular_section(parts, row, ox, oy, scale)
            else:
                _rc16_draw_rect_section(parts, row, ox, oy, scale)
            member = str(row.get("member", ""))
            mat = str(row.get("material", ""))
            sec = _rc16_section_label(row, "mm")
            sol = str(row.get("Solução adoptada", row.get("solucao_completa", row.get("Solução", row.get("solucao", "")))))[:95]
            status = str(row.get("estado_global", row.get("Estado", row.get("status", ""))))
            parts.append(_dxf_text(x0 + 35, y0 + 125, f"{member} | {sec} | {mat}", 22, "COLUMNS_TEXT"))
            parts.append(_dxf_text(x0 + 35, y0 + 75, sol, 19, "COLUMNS_TEXT"))
            parts.append(_dxf_text(x0 + 35, y0 + 30, status, 19, "COLUMNS_TEXT"))


def write_columns_dxf_v22(path: str, df: pd.DataFrame, lang: str = LANG_PT):
    try:
        sched = _rc22_build_tramo_schedule(df)
    except Exception:
        sched = df.copy() if df is not None else pd.DataFrame()
    try:
        sched = _rc16_apply_section_labels_df(sched)
    except Exception:
        pass
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
        work["Prumada"] = work.apply(_v682_prumada_from_row, axis=1) if "_v682_prumada_from_row" in globals() else work.get("name", work.get("member", ""))
    if "Piso" not in work.columns:
        work["Piso"] = work.apply(_v683_story_label_from_row, axis=1) if "_v683_story_label_from_row" in globals() else work.get("story", "")
    if "_story_sort_tuple" not in work.columns:
        work["_story_sort_tuple"] = work.apply(_v683_story_sort_tuple, axis=1) if "_v683_story_sort_tuple" in globals() else [(0, 0.0, str(v)) for v in work.get("Piso", pd.Series("", index=work.index))]
    work["_story_rank"] = work["_story_sort_tuple"].map(lambda x: x[0] if isinstance(x, tuple) and x else 0)
    work["_story_rank_float"] = work["_story_sort_tuple"].map(lambda x: x[1] if isinstance(x, tuple) and len(x) > 1 else 0.0)
    prumadas_all = sorted(work["Prumada"].astype(str).unique(), key=_v682_natural_key)
    levels_df = work[["Piso", "_story_rank", "_story_rank_float", "_story_sort_tuple"]].drop_duplicates()
    levels_df = levels_df.sort_values(["_story_rank", "_story_rank_float"], kind="mergesort")
    levels_all = list(levels_df["Piso"].astype(str))
    max_cols, max_rows = 24, 24
    p_chunks = [prumadas_all[i:i + max_cols] for i in range(0, len(prumadas_all), max_cols)] or [[]]
    l_chunks = [levels_all[i:i + max_rows] for i in range(0, len(levels_all), max_rows)] or [[]]
    n_blocks = len(p_chunks) * len(l_chunks)
    block_no = 0
    x_gap = 2200.0
    y_gap = 2500.0
    for li, levels in enumerate(l_chunks):
        row_h = len(levels) * 1180.0 + 1400.0 + y_gap
        for pi, prumadas in enumerate(p_chunks):
            block_no += 1
            ox0 = pi * (420.0 + max_cols * 1450.0 + x_gap)
            oy0 = -li * row_h
            _rc22_draw_schedule_block(parts, work, prumadas, levels, ox0, oy0, lang, block_no, n_blocks)
    parts.append("0\nENDSEC\n0\nEOF\n")
    Path(path).write_text("".join(parts), encoding="utf-8")


write_columns_dxf_v16 = write_columns_dxf_v22
write_columns_dxf_v65 = write_columns_dxf_v22 if "write_columns_dxf_v65" in globals() else write_columns_dxf_v22


def _rc22_export_dxf(self):
    if getattr(self, "df_results", pd.DataFrame()) is None or self.df_results.empty:
        messagebox.showwarning("Warning" if _rc16_is_en(self) else "Aviso", "No results to export to DXF." if _rc16_is_en(self) else "Não há resultados para exportar em DXF.")
        return
    title = "Export full column schedule [DXF]" if _rc16_is_en(self) else "Exportar quadro completo de pilares [DXF]"
    path = filedialog.asksaveasfilename(title=title, defaultextension=".dxf", filetypes=[("DXF", "*.dxf")])
    if not path:
        return
    try:
        self.status_var.set("A exportar quadro completo de pilares..." if not _rc16_is_en(self) else "Exporting full column schedule...")
        self.update_idletasks()
        self.df_summary = _rc22_build_tramo_schedule(self.df_results)
        write_columns_dxf_v22(path, self.df_summary, lang=LANG_EN if _rc16_is_en(self) else LANG_PT)
        self.status_var.set(("DXF exported: " if _rc16_is_en(self) else "DXF exportado: ") + str(path))
    except Exception as err:
        messagebox.showerror("Error" if _rc16_is_en(self) else "Erro", ("Could not export the column schedule DXF.\n\n" if _rc16_is_en(self) else "Não foi possível exportar o quadro de pilares em DXF.\n\n") + str(err))


try:
    ColumnsEC2App.export_dxf = _rc22_export_dxf
except Exception:
    pass


# ---------------------------------------------------------------------------
# Excel writer hook: rebuild summary with RC22 and sanitise exported frames
# ---------------------------------------------------------------------------

_rc22_prev_write_excel = ColumnsEC2App._write_excel


def _rc22_write_excel(self, path: str):
    try:
        if getattr(self, "df_results", pd.DataFrame()) is not None and not self.df_results.empty:
            self.df_results = _rc22_sanitise_text_df(self.df_results)
            self.df_summary = _rc22_build_tramo_schedule(self.df_results)
            if hasattr(self, "tree_summary"):
                try:
                    self.show_df(self.tree_summary, self.df_summary)
                except Exception:
                    pass
    except Exception:
        pass
    return _rc22_prev_write_excel(self, path)


ColumnsEC2App._write_excel = _rc22_write_excel

try:
    _RC13_EN_TERMS.update({
        "ELS não avaliado — combinação indicada não encontrada": "SLS not assessed — selected combination not found",
        "A combinação ELS indicada não existe na tabela importada; o estado resistente ELU não é penalizado por este motivo.": "The selected SLS combination is not present in the imported table; the ULS resistance status is not penalised for this reason.",
        "Exportar quadro completo de pilares [DXF]": "Export full column schedule [DXF]",
    })
except Exception:
    pass

# Clean wording for square rectangular sections: avoid duplicated "por face de 50 cm".
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
    base = f"4Ø{int(opt.phi_corner)} corner bars" if lang == "en" else f"4Ø{int(opt.phi_corner)} nos cantos"
    parts = []
    if abs(b_cm - h_cm) <= 1e-6 and opt.ey == opt.ez and opt.ey > 0:
        parts.append(f"{int(opt.ey)}Ø{int(opt.phi_face)} on each {b_cm:.0f} cm face" if lang == "en" else f"{int(opt.ey)}Ø{int(opt.phi_face)} em cada face de {b_cm:.0f} cm")
    else:
        if opt.ey > 0:
            parts.append(f"{int(opt.ey)}Ø{int(opt.phi_face)} on each {b_cm:.0f} cm face" if lang == "en" else f"{int(opt.ey)}Ø{int(opt.phi_face)} por face de {b_cm:.0f} cm")
        if opt.ez > 0:
            parts.append(f"{int(opt.ez)}Ø{int(opt.phi_face)} on each {h_cm:.0f} cm face" if lang == "en" else f"{int(opt.ez)}Ø{int(opt.phi_face)} por face de {h_cm:.0f} cm")
    add = " + ".join(parts) if parts else "-"
    sol = f"{base}; {link}" if not parts else f"{base} + {add}; {link}"
    return sol, base, add

# DXF writer refinement: if a dataframe is already a column schedule, do not
# rebuild it as calculation results.
def _rc22_is_schedule_df(df: pd.DataFrame) -> bool:
    if df is None or getattr(df, "empty", True):
        return False
    cols = set(df.columns)
    return {"Prumada", "Piso"}.issubset(cols) and ("Solução adoptada" in cols or "Solução" in cols or "Adopted arrangement" in cols)


def write_columns_dxf_v22(path: str, df: pd.DataFrame, lang: str = LANG_PT):
    if _rc22_is_schedule_df(df):
        sched = df.copy()
    else:
        try:
            sched = _rc22_build_tramo_schedule(df)
        except Exception:
            sched = df.copy() if df is not None else pd.DataFrame()
    try:
        sched = _rc16_apply_section_labels_df(sched)
    except Exception:
        pass
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
        work["Prumada"] = work.apply(_v682_prumada_from_row, axis=1) if "_v682_prumada_from_row" in globals() else work.get("name", work.get("member", ""))
    if "Piso" not in work.columns:
        work["Piso"] = work.apply(_v683_story_label_from_row, axis=1) if "_v683_story_label_from_row" in globals() else work.get("story", "")
    if "_story_sort_tuple" not in work.columns:
        work["_story_sort_tuple"] = work.apply(_v683_story_sort_tuple, axis=1) if "_v683_story_sort_tuple" in globals() else [(0, 0.0, str(v)) for v in work.get("Piso", pd.Series("", index=work.index))]
    work["_story_rank"] = work["_story_sort_tuple"].map(lambda x: x[0] if isinstance(x, tuple) and x else 0)
    work["_story_rank_float"] = work["_story_sort_tuple"].map(lambda x: x[1] if isinstance(x, tuple) and len(x) > 1 else 0.0)
    prumadas_all = sorted(work["Prumada"].astype(str).unique(), key=_v682_natural_key)
    levels_df = work[["Piso", "_story_rank", "_story_rank_float", "_story_sort_tuple"]].drop_duplicates()
    levels_df = levels_df.sort_values(["_story_rank", "_story_rank_float"], kind="mergesort")
    levels_all = list(levels_df["Piso"].astype(str))
    max_cols, max_rows = 24, 24
    p_chunks = [prumadas_all[i:i + max_cols] for i in range(0, len(prumadas_all), max_cols)] or [[]]
    l_chunks = [levels_all[i:i + max_rows] for i in range(0, len(levels_all), max_rows)] or [[]]
    n_blocks = len(p_chunks) * len(l_chunks)
    block_no = 0
    x_gap = 2200.0
    y_gap = 2500.0
    for li, levels in enumerate(l_chunks):
        row_h = len(levels) * 1180.0 + 1400.0 + y_gap
        for pi, prumadas in enumerate(p_chunks):
            block_no += 1
            ox0 = pi * (420.0 + max_cols * 1450.0 + x_gap)
            oy0 = -li * row_h
            _rc22_draw_schedule_block(parts, work, prumadas, levels, ox0, oy0, lang, block_no, n_blocks)
    parts.append("0\nENDSEC\n0\nEOF\n")
    Path(path).write_text("".join(parts), encoding="utf-8")

write_columns_dxf_v16 = write_columns_dxf_v22
write_columns_dxf_v65 = write_columns_dxf_v22
