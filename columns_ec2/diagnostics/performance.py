# -*- coding: utf-8 -*-
"""Diagnostics facade for the transitional modular release."""
from columns_ec2.runtime.loader import load_runtime


def runtime_namespace():
    return load_runtime()
