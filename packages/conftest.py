"""
Shared pytest configuration for the packages/ monorepo.

Adds each package's src/ directory to sys.path so tests can use flat imports
matching the existing workflow-runner convention. Production installs will
use proper package-qualified imports via pyproject.toml.
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).parent
for pkg in ["bus", "capability_registry", "ai", "api", "workflow-runner"]:
    src = _packages_root / pkg / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
