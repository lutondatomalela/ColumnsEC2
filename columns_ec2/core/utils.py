# -*- coding: utf-8 -*-
"""Small dependency-light utilities used by import and calculation modules."""
from __future__ import annotations

import math
import re
from typing import Any, Tuple

import pandas as pd


def normalize_text(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", text)


def safe_float(value: Any, default: float = float("nan")) -> float:
    """Parse numbers exported with either decimal dots or decimal commas."""
    try:
        if pd.isna(value):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return default
        text = text.replace("\u00a0", " ").replace(" ", "")
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+,\d+", text):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        result = float(text)
        return result if math.isfinite(result) else default
    except Exception:
        return default


def cm_to_mm(value: Any) -> float:
    return safe_float(value, 0.0) * 10.0


def m_to_mm(value: Any) -> float:
    return safe_float(value, 0.0) * 1000.0


def split_member_case(text: Any) -> Tuple[str, str, str]:
    raw = str(text or "").strip().replace("\\", "/")
    parts = [p.strip() for p in raw.split("/")]
    member = parts[0] if len(parts) > 0 else ""
    node = parts[1] if len(parts) > 1 else ""
    case = parts[2] if len(parts) > 2 else ""
    case = re.sub(r"\s*\([^)]*\)\s*$", "", case).strip()
    return member, node, case
