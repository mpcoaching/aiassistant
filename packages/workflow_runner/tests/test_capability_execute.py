"""
Tests for POST /assistant/capability/{capability_id}//execute (Increment 5).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["bus", "capability_registry", "ai", "workflow_runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

_api_path = _packages_root / "workflow_runner" / "api.py"
_spec = importlib.util.spec_from_file_location("workflow_runner_api", _api_path)
_api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api_mod)
sys.modules["workflow_runner_api"] = _api_mod
app = _api_mod.app


@pytest.fixture()
def client():
    with patch("workflow_runner_api.EventBus") as MockBus, patch("workflow_runner_api._build_scheduler") as mock_build:
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


def test_execute_capability_endpoint_returns_result(client):
    with patch("workflow_runner_api._get_chat_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.execute_selected_capability.return_value = MagicMock(
            outputs={"artifact_id": "art-123"},
            artifacts=[],
            telemetry={"capability_name": "create_test_artifact"},
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/assistant/capability/cap-exec-1/execute",
            json={"context": {"label": "foo"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["outputs"]["artifact_id"] == "art-123"
        assert data["telemetry"]["capability_name"] == "create_test_artifact"
        mock_service.execute_selected_capability.assert_called_once_with(
            capability_id="cap-exec-1", context={"label": "foo"}
        )


def test_execute_capability_endpoint_defaults_context_to_empty(client):
    with patch("workflow_runner_api._get_chat_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.execute_selected_capability.return_value = MagicMock(
            outputs={}, artifacts=[], telemetry={}
        )
        mock_get_service.return_value = mock_service

        response = client.post("/assistant/capability/cap-1/execute", json={})
        assert response.status_code == 200
        mock_service.execute_selected_capability.assert_called_once_with(
            capability_id="cap-1", context={}
        )
