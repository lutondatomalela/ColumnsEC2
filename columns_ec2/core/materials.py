# -*- coding: utf-8 -*-
"""Material helper functions used by the ColumnsEC2 engines."""
from __future__ import annotations

import math
import re
from typing import Dict

from columns_ec2.app_info import DEFAULT_CONCRETE_CLASS


def parse_concrete_strength(material: str) -> float:
    """Return fck [MPa] from strings such as C30/37."""
    match = re.search(r"C\s*(\d+(?:[\.,]\d+)?)\s*/\s*(\d+(?:[\.,]\d+)?)", str(material), re.I)
    if match:
        return float(match.group(1).replace(",", "."))
    if str(material).strip() != DEFAULT_CONCRETE_CLASS:
        return parse_concrete_strength(DEFAULT_CONCRETE_CLASS)
    return 30.0


def concrete_props(fck: float, alpha_cc: float = 1.0, gamma_c: float = 1.5) -> Dict[str, float]:
    """Return practical EC2 concrete properties in MPa."""
    fcm = fck + 8.0
    fcd = alpha_cc * fck / gamma_c
    fctm = 0.30 * fck ** (2.0 / 3.0) if fck <= 50.0 else 2.12 * math.log(1.0 + fcm / 10.0)
    ecm = 22.0 * (fcm / 10.0) ** 0.3 * 1000.0
    return {"fck": fck, "fcm": fcm, "fcd": fcd, "fctm": fctm, "Ecm": ecm}


def steel_props(fyk: float = 500.0, gamma_s: float = 1.15) -> Dict[str, float]:
    return {"fyd": fyk / gamma_s, "Es": 210000.0}


def bar_area_mm2(phi_mm: float) -> float:
    return math.pi * phi_mm * phi_mm / 4.0
