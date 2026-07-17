"""
Shared pytest configuration for the packages/ monorepo.

Adds each package's src/ directory to sys.path so tests can use flat imports
matching the existing workflow-runner convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).parent
for _pkg in ["bus", "capability_registry", "ai", "api", "workflow-runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
