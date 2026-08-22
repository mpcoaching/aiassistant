"""
Shared pytest configuration for the packages/ monorepo.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).parent
if str(_packages_root) not in sys.path:
    sys.path.insert(0, str(_packages_root))
for _pkg in ["bus", "capability_registry", "ai", "api", "configuration", "contracts", "langgraph", "organisation", "people_capability"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
for _pkg in ["contracts"]:
    _root = _packages_root / _pkg
    if _root.exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

for _pkg in ["workflow_runner"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
    _root = _packages_root / _pkg
    if _root.exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
