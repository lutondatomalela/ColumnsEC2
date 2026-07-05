# -*- coding: utf-8 -*-
"""Backend facade.

Actual backend selection is still performed by the validated runtime GUI/state.
This module exists to give the project a stable import boundary for the next
refactor phase.
"""
from columns_ec2.runtime.loader import runtime_object

ColumnDesigner = runtime_object("ColumnDesigner")
