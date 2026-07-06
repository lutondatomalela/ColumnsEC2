# -*- coding: utf-8 -*-
"""Runtime loader for the transitional modular ColumnsEC2 package.

The original RC8 file used sequential patches. To keep the validated behaviour,
these patch blocks are executed in a single shared namespace, but they are now
physically separated by responsibility/version. This allows the next refactor
step to move stable functions into conventional imports without changing
calculation output in this RC.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace, ModuleType
from typing import Dict, Any
import sys

from .manifest import RUNTIME_MODULES

_RUNTIME_CACHE: Dict[str, Any] | None = None


def load_runtime(force_reload: bool = False) -> Dict[str, Any]:
    """Load all runtime modules into one namespace and return it."""
    global _RUNTIME_CACHE
    if _RUNTIME_CACHE is not None and not force_reload:
        return _RUNTIME_CACHE

    runtime_dir = Path(__file__).resolve().parent
    module_name = "columns_ec2.runtime.shared"
    shared_module = ModuleType(module_name)
    shared_module.__package__ = "columns_ec2.runtime"
    shared_module.__file__ = str(runtime_dir / "loader.py")
    sys.modules[module_name] = shared_module
    ns: Dict[str, Any] = shared_module.__dict__
    ns.update({
        "__name__": module_name,
        "__package__": "columns_ec2.runtime",
        "__file__": str(runtime_dir / "loader.py"),
    })
    for module_name in RUNTIME_MODULES:
        module_path = runtime_dir / module_name
        source = module_path.read_text(encoding="utf-8")
        code = compile(source, str(module_path), "exec")
        ns["__file__"] = str(module_path)
        exec(code, ns)
    ns["__file__"] = str(runtime_dir / "loader.py")
    # Modular release identifier;
    ns["APP_VERSION"] = "v0.1"
    _RUNTIME_CACHE = ns
    return ns


def runtime_object(name: str):
    ns = load_runtime()
    try:
        return ns[name]
    except KeyError as exc:
        raise AttributeError(f"Runtime object not found: {name}") from exc


def as_namespace() -> SimpleNamespace:
    return SimpleNamespace(**load_runtime())
