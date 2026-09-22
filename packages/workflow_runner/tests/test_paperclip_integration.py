"""
Layer 2 — Paperclip integration tests for the Assistant chat path.

Tests the real API code path end-to-end with Paperclip as the control plane:
  Browser → Paperclip → Assistant agent → AI runtime → Portkey → LLM

Layer 2 mocks Paperclip API responses to verify routing without requiring
a live Paperclip instance.

Layer 2B (opt-in via REAL_AI_TESTS=1) uses the live Paperclip instance
and real LLM to prove the full chain.
"""

from __future__ import annotations

import importlib.util
import os
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

for _pkg in ["workflow_runner"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
    _root = _packages_root / _pkg
    if _root.exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

os.environ.setdefault("PAPERCLIP_ASSISTANT_AGENT_ID", "agent-123")
os.environ.setdefault("PAPERCLIP_URL", "http://localhost:3101")
os.environ.setdefault("PAPERCLIP_COMPANY_ID", "test-company")

_api_path = _packages_root / "workflow_runner" / "api.py"
_spec = importlib.util.spec_from_file_location("workflow_runner_api_paperclip", _api_path)
_api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api_mod)
sys.modules["workflow_runner_api_paperclip"] = _api_mod
app = _api_mod.app


def _skip_if_no_real_ai() -> None:
    if os.getenv("REAL_AI_TESTS") != "1":
        pytest.skip("REAL_AI_TESTS != 1; set REAL_AI_TESTS=1 to run real Paperclip+AI integration tests")
    if not os.getenv("PORTKEY_MASTER_KEY"):
        pytest.skip("PORTKEY_MASTER_KEY not configured; skipping real integration test")


def _clear_assistant_state():
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None
    _api_mod._assistant._solution_selection = None
    _api_mod._assistant._workflow_execution = None


@pytest.fixture()
def client():
    with pytest.MonkeyPatch.context() as m:
        m.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
        m.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        m.setenv("REDIS_URL", "redis://localhost:6379")
        m.setenv("OPENAI_API_BASE", "http://localhost:4000/v1")
        m.setenv("OPENAI_BASE_URL", "http://localhost:4000/v1")
        m.setenv("ENV_TIER", "test")
        with patch("workflow_runner_api_paperclip.EventBus") as MockBus, patch("workflow_runner_api_paperclip._build_scheduler") as mock_build:
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

            mock_response = MagicMock()
            mock_response.message = "Mocked Paperclip response"
            mock_response.session_id = "ses-paperclip-1"
            mock_response.status = "completed"
            mock_response.reasoning = "Generated via Paperclip-managed Assistant agent"
            mock_response.previous_solution = None
            mock_response.human_input_request = None
            mock_response.capability_candidates = None
            mock_response.telemetry = {
                "runtime": "paperclip",
                "agent_id": "agent-123",
                "work_id": "work-1",
                "model": "qwen/qwen3.8-27b",
                "ai_invoked": True,
                "ai_success": True,
                "ai_latency_ms": 123,
            }
            mock_response.execution_outputs = None
            mock_response.execution_artifacts = []
            mock_response.chat.return_value = mock_response

            with patch.object(_api_mod, "_paperclip_assistant", mock_response), TestClient(app) as c:
                    yield c


class TestPaperclipChatRouting:
    """Layer 2 — Paperclip chat routing through the API."""

    def test_paperclip_chat_endpoint_exists(self, client: TestClient) -> None:
        response = client.post("/assistant/paperclip-chat", json={"message": "Hi"})
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "session_id" in data
        assert "status" in data

    def test_paperclip_chat_returns_paperclip_runtime_telemetry(self, client: TestClient) -> None:
        response = client.post("/assistant/paperclip-chat", json={"message": "Hi"})
        assert response.status_code == 200
        data = response.json()
        telemetry = data.get("telemetry", {})
        assert telemetry.get("runtime") == "paperclip"
        assert telemetry.get("agent_id") == "agent-123"

    def test_paperclip_chat_returns_ai_telemetry_when_live(self, client: TestClient) -> None:
        _skip_if_no_real_ai()
        response = client.post("/assistant/paperclip-chat", json={"message": "What is 5 plus 3?"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        telemetry = data.get("telemetry", {})
        assert telemetry.get("ai_invoked") is True
        assert telemetry.get("ai_success") is True
        assert telemetry.get("model") is not None
        assert telemetry.get("ai_latency_ms", 0) > 0


class TestCanonicalRealAISmoke:
    """Layer 2B — Real AI smoke test through Paperclip-managed Assistant."""

    def test_real_ai_smoke_through_paperclip(self, client: TestClient) -> None:
        _skip_if_no_real_ai()
        response = client.post("/assistant/paperclip-chat", json={"message": "What is 17 multiplied by 6?"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "102" in data["message"]
        telemetry = data.get("telemetry", {})
        assert telemetry["ai_invoked"] is True
        assert telemetry["ai_success"] is True
        assert telemetry["model"] is not None
        assert telemetry["ai_latency_ms"] > 0

    def test_multi_turn_conversation_through_paperclip(self, client: TestClient) -> None:
        _skip_if_no_real_ai()
        first = client.post("/assistant/paperclip-chat", json={"message": "My favourite number is 17."})
        assert first.status_code == 200
        first_data = first.json()
        assert first_data["status"] == "completed"

        second = client.post("/assistant/paperclip-chat", json={"message": "What number did I just tell you?"})
        assert second.status_code == 200
        second_data = second.json()
        assert second_data["status"] == "completed"
        assert "17" in second_data["message"]


class TestPaperclipExecutionBoundary:
    """Layer 3 — Paperclip is an execution backend below the Org Control Plane."""

    def test_solution_selection_boundary_is_independent_of_execution_backend(self):
        """The OCP select_execution_path decision does not depend on Paperclip."""
        from organisation_paperclip import PaperclipOrganisationControlPlane
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from execution_path import ExecutionPath

        in_memory = InMemoryOrganisationControlPlane()
        paperclip = PaperclipOrganisationControlPlane(base_url="http://localhost:3101")

        intent = "do the unknown thing"
        context = {"required_capability_ids": []}

        in_memory_result = in_memory.select_execution_path(intent, context)
        paperclip_result = paperclip.select_execution_path(intent, context)

        assert in_memory_result.path == paperclip_result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert in_memory_result.capability_id is None
        assert paperclip_result.capability_id is None

    def test_paperclip_ocp_implements_solution_selection_port(self):
        """PaperclipOrganisationControlPlane implements the solution selection boundary."""
        from organisation_paperclip import PaperclipOrganisationControlPlane

        plane = PaperclipOrganisationControlPlane(base_url="http://localhost:3101")
        assert hasattr(plane, "select_execution_path")
        result = plane.select_execution_path("test", {})
        assert result.path in (
            "existing_workflow",
            "capability_path",
            "new_capability_required",
            "human_team_investigation",
        )
