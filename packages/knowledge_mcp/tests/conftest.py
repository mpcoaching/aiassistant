"""
Pytest configuration for the knowledge_mcp test suite.

Adds the package src/ directory to sys.path so tests can use flat imports
matching the existing platform convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["configuration", "knowledge_mcp"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
