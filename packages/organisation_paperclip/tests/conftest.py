"""
Pytest configuration for organisation_paperclip tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).resolve().parent.parent.parent
if str(_packages_root) not in sys.path:
    sys.path.insert(0, str(_packages_root))

for _pkg in ["organisation", "contracts", "people_capability"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
