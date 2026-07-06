# -*- coding: utf-8 -*-
"""Reinforcement layouts and the currently validated column designer class."""
from __future__ import annotations

from .materials import bar_area_mm2
from columns_ec2.runtime.loader import runtime_object

# The Layout dataclass and ColumnDesigner are still loaded from the validated
# runtime sequence. They will be moved here after numerical regression testing.
Layout = runtime_object("Layout")
ColumnDesigner = runtime_object("ColumnDesigner")
