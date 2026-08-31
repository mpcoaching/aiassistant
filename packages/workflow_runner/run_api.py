#!/usr/bin/env python3
"""Run the Workflow Engine API with correct module paths."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
_packages_root = Path(__file__).resolve().parent.parent
if str(_packages_root) not in sys.path:
    sys.path.insert(0, str(_packages_root))

for _pkg in ["bus", "capability", "capabilities", "capability_registry", "ai", "langgraph", "organisation", "contracts", "api", "configuration", "people_capability", "organisation_paperclip"]:
    _src = _packages_root / _pkg / "src"
    _pkg_dir = _packages_root / _pkg
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
    elif _pkg_dir.exists() and str(_pkg_dir) not in sys.path:
        sys.path.insert(0, str(_pkg_dir))

for _pkg in ["workflow_runner"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
    _root = _packages_root / _pkg
    if _root.exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

_paperclip = _packages_root / "organisation_paperclip" / "src"
if _paperclip.exists() and str(_paperclip) not in sys.path:
    sys.path.insert(0, str(_paperclip))

_api_path = _packages_root / "workflow_runner" / "api.py"
_spec = importlib.util.spec_from_file_location("workflow_runner_api", _api_path)
_api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api_mod)
sys.modules["workflow_runner_api"] = _api_mod

import uvicorn

if __name__ == "__main__":
    uvicorn.run(_api_mod.app, host="0.0.0.0", port=8000)
