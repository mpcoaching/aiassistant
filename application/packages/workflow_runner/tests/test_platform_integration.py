"""
Layer 2 — Canonical platform integration smoke test — Assistant chat path (Increment 23).

Tests the real API code path end-to-end:
  document → understanding → validation → execution → investigation

This is NOT a unit test. It uses the real API app and real request/response
cycle. Infrastructure dependencies (EventBus, Scheduler, Database) are mocked
at the adapter boundary, but the AssistantChatService, context formation,
validation loop, and Work delegation are exercised with real code.

Run:
  pytest packages/workflow_runner/tests/test_platform_integration.py -v --tb=short
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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

_api_path = _packages_root / "workflow_runner" / "api.py"
_spec = importlib.util.spec_from_file_location("workflow_runner_api_platform", _api_path)
_api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api_mod)
sys.modules["workflow_runner_api_platform"] = _api_mod
app = _api_mod.app


@pytest.fixture()
def client():
    with pytest.MonkeyPatch.context() as m:
        m.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
        m.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        m.setenv("REDIS_URL", "redis://localhost:6379")
        m.setenv("OPENAI_API_BASE", "http://localhost:4000/v1")
        m.setenv("OPENAI_BASE_URL", "http://localhost:4000/v1")
        m.setenv("ENV_TIER", "test")
        with patch("workflow_runner_api_platform.EventBus") as MockBus, patch("workflow_runner_api_platform._build_scheduler") as mock_build:
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


from unittest.mock import MagicMock, patch


def _clear_assistant_state():
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None


def _inject_mock_ai():
    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "AI-generated response",
        {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None},
    )
    mock_ai.model = "llama-3.3-70b-versatile"
    _api_mod._assistant._ai_response = mock_ai
    return mock_ai


Q2_BUSINESS_REVIEW = (
    "Q2 revenue declined 12% compared with Q1. "
    "Customer retention fell from 84% to 76%. "
    "Support volume increased 31%. "
    "NPS declined from 45 to 28. "
    "Two new competitors entered the market. "
    "Headcount is frozen until Q4."
)


class TestAssistantAnalysisPlatformSmoke:
    """Canonical platform reliability test for the Assistant analysis vertical slice."""

    def test_platform_startup_and_chat_submission(self, client):
        """A. Platform startup: backend is available and accepts requests."""
        response = client.get("/health")
        assert response.status_code == 200

        response = client.post("/assistant/chat", json={"message": "hello"})
        assert response.status_code == 200

    def test_turn_1_analysis_request_reaches_validation(self, client):
        """B+C: Real chat → real context formation → awaiting_validation."""
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "session_id": "ses-platform-smoke",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "awaiting_validation"
        assert data["session_id"] == "ses-platform-smoke"
        assert data["human_input_request"] is not None
        assert data["human_input_request"]["validation_type"] == "analysis_understanding"

        proposed = data["human_input_request"]["question"]
        assert "i understand you want to" in proposed.lower()
        assert "revenue" in proposed.lower()
        assert "retention" in proposed.lower()

    def test_turn_2_validation_triggers_real_execution(self, client):
        """D+E: Real validation → real Work creation → real execution."""
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "session_id": "ses-platform-smoke-2",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        assert turn1.status_code == 200
        data = turn1.json()
        assert data["status"] == "awaiting_validation"
        session_id = data["session_id"]

        resume = client.post(
            f"/assistant/chat/{session_id}/resume",
            json={"response": "Yes, proceed."},
        )
        assert resume.status_code == 200
        data_resume = resume.json()
        assert data_resume["status"] == "completed"

        work_id = data_resume["telemetry"]["work_id"]
        work_response = client.get(f"/work/{work_id}")
        work_data = work_response.json()
        assert work_data["status"] == "completed"

        assert data_resume["execution_outputs"] is not None
        analysis_context = data_resume["execution_outputs"].get("analysis_context")
        assert analysis_context is not None

    def test_turn_3_followup_preserves_context(self, client):
        """F+G: Real continuation — follow-up against completed analysis."""
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "session_id": "ses-platform-smoke-3",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        assert turn1.status_code == 200
        data = turn1.json()
        assert data["status"] == "awaiting_validation"
        session_id = data["session_id"]

        resume = client.post(
            f"/assistant/chat/{session_id}/resume",
            json={"response": "Yes, proceed."},
        )
        assert resume.status_code == 200
        data_resume = resume.json()
        assert data_resume["status"] == "completed"

        followup = client.post(
            f"/assistant/chat/{session_id}/resume",
            json={"response": "Why is that the most important area?", "investigation": True},
        )
        assert followup.status_code == 200
        data_followup = followup.json()
        assert data_followup["status"] == "completed"
        assert "investigation" in data_followup["telemetry"]

    def test_output_contains_decision_sections(self, client):
        """Verify the real Worker output contains the expected decision-oriented sections."""
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "session_id": "ses-platform-smoke-4",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        data = turn1.json()
        session_id = data["session_id"]

        resume = client.post(
            f"/assistant/chat/{session_id}/resume",
            json={"response": "Yes, proceed."},
        )
        data_resume = resume.json()
        message = data_resume["message"]

        assert "Known Facts" in message or "What We Know" in message
        assert "Evidence" in message
        assert "Prioritised Focus" in message or "Possible Explanation" in message
        assert "Confidence" in message
        assert "12%" in message
        assert "retention" in message.lower() or "customer" in message.lower()

    def test_contradiction_revises_understanding(self, client):
        """Validation loop: contradict → revised understanding → awaiting_validation."""
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "session_id": "ses-platform-smoke-5",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        data = turn1.json()
        session_id = data["session_id"]

        contradict = client.post(
            f"/assistant/chat/{session_id}/resume",
            json={"response": "Actually, no — analyse this to improve growth"},
        )
        assert contradict.status_code == 200
        data_contradict = contradict.json()
        assert data_contradict["status"] == "awaiting_validation"
        assert "growth" in data_contradict["message"].lower() or "improve" in data_contradict["message"].lower()

    def test_update_extends_understanding(self, client):
        """Validation loop: update → extended understanding → awaiting_validation."""
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "session_id": "ses-platform-smoke-6",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        data = turn1.json()
        session_id = data["session_id"]

        update = client.post(
            f"/assistant/chat/{session_id}/resume",
            json={"response": "Also, we're currently trying to reduce churn"},
        )
        assert update.status_code == 200
        data_update = update.json()
        assert data_update["status"] == "awaiting_validation"


class TestAssistantAIPlatformIntegration:
    """Layer 2 — AI response path through the real API stack."""

    def test_ai_chat_returns_real_response_and_telemetry(self, client):
        """Conversational message routes to AI and returns telemetry."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={"message": "Tell me something interesting"},
        )
        assert response.status_code == 200
        data = response.json()

        print(data); assert data["status"] == "completed"
        assert data["message"] == "AI-generated response"
        assert data["telemetry"]["runtime"] == "ai_response_service"
        assert data["telemetry"]["ai_invoked"] is True
        assert data["telemetry"]["ai_model"] == "llama-3.3-70b-versatile"
        assert data["telemetry"]["ai_success"] is True
        assert data["telemetry"]["ai_latency_ms"] == 100
        mock_ai.generate.assert_called_once()

    def test_ai_chat_session_continuity_through_api(self, client):
        """Two turns with the same session_id pass conversation history to the LLM."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={"message": "My business sells coaching programs.", "session_id": "ses-ai-continuity"},
        )
        assert turn1.status_code == 200
        data1 = turn1.json()
        assert data1["status"] == "completed"
        assert data1["session_id"] == "ses-ai-continuity"

        turn2 = client.post(
            "/assistant/chat",
            json={"message": "What would you investigate first?", "session_id": "ses-ai-continuity"},
        )
        assert turn2.status_code == 200
        data2 = turn2.json()
        assert data2["status"] == "completed"
        assert data2["telemetry"]["runtime"] == "ai_response_service"

        assert mock_ai.generate.call_count == 2
        second_call_history = mock_ai.generate.call_args_list[1].kwargs["conversation_history"]
        assert second_call_history == [
            {"role": "user", "content": "My business sells coaching programs."},
            {"role": "assistant", "content": "AI-generated response"},
        ]

    def test_ai_chat_different_sessions_isolated(self, client):
        """Separate session_ids do not share conversation history."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        client.post("/assistant/chat", json={"message": "Session A", "session_id": "ses-ai-iso-a"})
        client.post("/assistant/chat", json={"message": "Session B", "session_id": "ses-ai-iso-b"})

        assert mock_ai.generate.call_count == 2
        assert mock_ai.generate.call_args_list[0].kwargs["conversation_history"] == []
        assert mock_ai.generate.call_args_list[1].kwargs["conversation_history"] == []

    def test_ai_chat_does_not_route_planning(self, client):
        """Planning messages still go through the deterministic path, not AI."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={"message": "Plan a birthday party for 20 people"},
        )
        assert response.status_code == 200
        data = response.json()
        print(data); assert data["status"] == "completed"
        mock_ai.generate.assert_not_called()


class TestCanonicalRealAISmoke:
    """Canonical acceptance test: can a user receive a real LLM response
    through the running platform?

    When REAL_AI_TESTS=1 and Portkey is reachable, this exercises the actual
    HTTP path. Otherwise it is skipped with a clear reason.
    """

    def _skip_if_no_real_ai(self):
        import os
        if os.getenv("REAL_AI_TESTS") != "1":
            pytest.skip("REAL_AI_TESTS != 1; skipping real-AI smoke test")
        if not os.getenv("PORTKEY_MASTER_KEY"):
            pytest.skip("PORTKEY_MASTER_KEY not configured; skipping real-AI smoke test")

    def test_real_ai_smoke_through_platform(self, client):
        """Send a distinctive question and verify AI provenance."""
        self._skip_if_no_real_ai()
        _clear_assistant_state()

        from ai.src.ai_response import AIResponseService
        _api_mod._assistant._ai_response = AIResponseService()

        response = client.post(
            "/assistant/chat",
            json={"message": "What is 7 multiplied by 8? Answer with just the number."},
        )
        assert response.status_code == 200
        data = response.json()

        print(data); assert data["status"] == "completed"
        assert data["telemetry"]["runtime"] == "ai_response_service"
        assert data["telemetry"]["ai_invoked"] is True
        assert data["telemetry"]["ai_success"] is True
        assert data["telemetry"]["ai_model"] is not None
        assert data["telemetry"]["ai_latency_ms"] > 0
        assert "56" in data["message"]


class TestConversationContinuityPlatform:
    """Three-turn conversation continuity through the real API stack."""

    def test_three_turn_conversation_retains_context_through_api(self, client):
        """Turn 2 and Turn 3 receive conversation history via the API."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        turn1 = client.post(
            "/assistant/chat",
            json={
                "message": "I have a dog called Merlin.",
                "session_id": "ses-continuity-3turn",
            },
        )
        assert turn1.status_code == 200

        turn2 = client.post(
            "/assistant/chat",
            json={
                "message": "What is my dog's name?",
                "session_id": "ses-continuity-3turn",
            },
        )
        assert turn2.status_code == 200
        data2 = turn2.json()
        assert data2["telemetry"]["runtime"] == "ai_response_service"

        turn3 = client.post(
            "/assistant/chat",
            json={
                "message": "Now give me one unusual fact about him.",
                "session_id": "ses-continuity-3turn",
            },
        )
        assert turn3.status_code == 200
        data3 = turn3.json()
        assert data3["telemetry"]["runtime"] == "ai_response_service"

        assert mock_ai.generate.call_count == 3
        third_call_history = mock_ai.generate.call_args_list[2].kwargs["conversation_history"]
        assert len(third_call_history) == 4
        assert third_call_history[0] == {"role": "user", "content": "I have a dog called Merlin."}
        assert third_call_history[2] == {"role": "user", "content": "What is my dog's name?"}

    def test_three_turn_different_sessions_do_not_leak(self, client):
        """Separate sessions receive independent history."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        for i in range(3):
            client.post(
                "/assistant/chat",
                json={"message": f"Session A message {i+1}", "session_id": "ses-leak-a"},
            )
            client.post(
                "/assistant/chat",
                json={"message": f"Session B message {i+1}", "session_id": "ses-leak-b"},
            )

        assert mock_ai.generate.call_count == 6
        session_a_history = _api_mod._assistant._conversation_history.get("ses-leak-a", [])
        session_b_history = _api_mod._assistant._conversation_history.get("ses-leak-b", [])
        assert all("Session A" in msg["content"] for msg in session_a_history if msg["role"] == "user")
        assert all("Session B" in msg["content"] for msg in session_b_history if msg["role"] == "user")


class TestSpecialisedPathIsolation:
    """Generic conversation routes to AI; specialised intents retain deterministic paths."""

    def test_analysis_request_does_not_route_to_ai(self, client):
        """Business analysis goes to deterministic analysis path, not AI."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={
                "message": "Analyse this and tell me what I should focus on",
                "context": {"input_text": Q2_BUSINESS_REVIEW},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "awaiting_validation"
        mock_ai.generate.assert_not_called()

    def test_planning_request_does_not_route_to_ai(self, client):
        """Planning goes to deterministic planning path, not AI."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={"message": "Plan a birthday party for 20 people"},
        )
        assert response.status_code == 200
        data = response.json()
        print(data); assert data["status"] == "completed"
        mock_ai.generate.assert_not_called()

    def test_generic_conversation_routes_to_ai(self, client):
        """Generic conversational message routes to AI, not deterministic patterns."""
        mock_ai = _inject_mock_ai()
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={"message": "Why do successful businesses become harder to manage as they grow?"},
        )
        assert response.status_code == 200
        data = response.json()
        print(data); assert data["status"] == "completed"
        assert data["telemetry"]["runtime"] == "ai_response_service"
        mock_ai.generate.assert_called_once()


class TestFailureBehaviour:
    """AI failure must not crash the platform or poison conversation history."""

    def test_ai_failure_returns_fallback_response(self, client):
        """When AI raises, the platform returns a graceful fallback."""
        mock_ai = MagicMock()
        mock_ai.generate.side_effect = RuntimeError("Portkey timeout")
        mock_ai.model = "llama-3.3-70b-versatile"
        _api_mod._assistant._ai_response = mock_ai
        _clear_assistant_state()

        response = client.post(
            "/assistant/chat",
            json={"message": "Tell me something interesting"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["telemetry"].get("runtime") != "ai_response_service"
        assert "ai_success" not in data["telemetry"]

    def test_ai_failure_does_not_poison_history(self, client):
        """A failed AI request does not append to conversation history."""
        mock_ai = MagicMock()
        mock_ai.generate.side_effect = RuntimeError("Portkey timeout")
        mock_ai.model = "llama-3.3-70b-versatile"
        _api_mod._assistant._ai_response = mock_ai
        _clear_assistant_state()

        client.post(
            "/assistant/chat",
            json={"message": "Tell me something interesting", "session_id": "ses-failure"},
        )

        assert mock_ai.generate.call_count == 1
        history = _api_mod._assistant._conversation_history.get("ses-failure", [])
        assert history == []

    def test_ai_recovery_after_failure(self, client):
        """After an AI failure, a subsequent request can succeed."""
        mock_ai = MagicMock()
        mock_ai.generate.side_effect = [
            RuntimeError("Portkey timeout"),
            ("Recovered response", {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None}),
        ]
        mock_ai.model = "llama-3.3-70b-versatile"
        _api_mod._assistant._ai_response = mock_ai
        _clear_assistant_state()

        response1 = client.post(
            "/assistant/chat",
            json={"message": "First question", "session_id": "ses-recovery"},
        )
        assert response1.status_code == 200
        assert response1.json()["telemetry"].get("runtime") != "ai_response_service"

        response2 = client.post(
            "/assistant/chat",
            json={"message": "Second question", "session_id": "ses-recovery"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "completed"
        assert data2["message"] == "Recovered response"
        assert data2["telemetry"]["runtime"] == "ai_response_service"
        assert data2["telemetry"]["ai_success"] is True
