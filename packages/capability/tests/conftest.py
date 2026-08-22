"""
Pytest configuration for the capability test suite.

Adds the package src/ directory to sys.path so tests can use flat imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).resolve().parent.parent.parent
_src = _packages_root / "capability" / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
