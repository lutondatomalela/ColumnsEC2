# -*- coding: utf-8 -*-
"""ColumnsEC2 modular package."""
__version__ = "v0.9 RC26 Modular"


def get_app_class():
    from .runtime.loader import runtime_object
    return runtime_object("ColumnsEC2App")
