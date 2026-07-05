# -*- coding: utf-8 -*-
"""GUI facade.

The Tk application class is currently loaded from the validated RC8 runtime.
The facade keeps the public import stable while the internals are progressively
moved to conventional modules.
"""
from __future__ import annotations

from columns_ec2.runtime.loader import runtime_object


def get_app_class():
    return runtime_object("ColumnsEC2App")


def create_app():
    app_cls = get_app_class()
    app = app_cls()
    hook = runtime_object("_v092_apply_language_title")
    try:
        hook(app)
    except Exception:
        pass
    return app
