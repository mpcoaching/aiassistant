"""
Pytest configuration for the workflow_runner test suite.

Pre-loads the canonical bus module into sys.modules so that flat imports
like `from bus import EventBus` resolve to the full-featured bus implementation
even when pytest's rootdir places workflow_runner/ ahead of bus/src on sys.path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_packages_root = Path(__file__).resolve().parent.parent.parent


def _preload_module(name: str, file_path: Path) -> None:
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, str(file_path))
        if spec is not None:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)


_preload_module("bus", _packages_root / "bus" / "src" / "bus.py")


@pytest.fixture()
def client():
    from unittest.mock import MagicMock, patch

    from api import app

    with patch("api.EventBus") as MockBus, patch("api._build_scheduler") as mock_build:
        mock_bus = MagicMock()
        mock_bus.declare_topology = MagicMock()
        mock_bus.start_consumers = MagicMock()
        mock_bus.shutdown = MagicMock()
        mock_bus.publish_workflow_started = MagicMock()
        mock_bus.publish_workflow_completed = MagicMock()
        mock_bus.publish_workflow_failed = MagicMock()
        mock_bus.publish_step_started = MagicMock()
        mock_bus.publish_step_completed = MagicMock()
        mock_bus.publish_capability_request = MagicMock()
        mock_bus.publish_capability_reply = MagicMock()
        mock_bus.publish_knowledge_chunk = MagicMock()
        MockBus.return_value = mock_bus

        mock_sched = MagicMock()
        mock_sched.get_jobs.return_value = []
        mock_build.return_value = mock_sched

        with TestClient(app) as c:
            yield c
