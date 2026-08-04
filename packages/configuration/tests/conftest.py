"""
Shared pytest configuration for the configuration package tests.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

_packages_root = Path(__file__).parent.parent
_src = _packages_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def _redis_available() -> bool:
    try:
        with socket.create_connection(("localhost", 6379), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(autouse=True)
def _skip_redis_if_unavailable(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("redis") and not _redis_available():
        pytest.skip("Redis not available")
