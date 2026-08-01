"""
Shared pytest configuration for the configuration package tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).parent.parent
_src = _packages_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
