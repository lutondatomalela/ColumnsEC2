# -*- coding: utf-8 -*-
from columns_ec2.runtime.loader import runtime_object

# Facade over the validated RC8 exporter implementation.
try:
    export_impl = runtime_object("write_columns_dxf_v4")
except Exception:
    export_impl = None
