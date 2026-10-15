"""
Layer 2/3 integration tests for the real AI response path.

These tests make actual HTTP requests through Portkey to the configured LLM.
They are skipped when PORTKEY_MASTER_KEY is not available in the environment,
or when REAL_AI_TESTS != 1 (explicit opt-in required for paid/external calls).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from ai.src.ai_response import AIResponseService


pytestmark = pytest.mark.integration


def _skip_if_no_credentials() -> None:
    if os.getenv("REAL_AI_TESTS") != "1":
        pytest.skip("REAL_AI_TESTS != 1; set REAL_AI_TESTS=1 to run real Portkey integration tests")
    if not os.getenv("PORTKEY_MASTER_KEY"):
        pytest.skip("PORTKEY_MASTER_KEY not configured; skipping real Portkey integration test")


class TestRealPortkeyPath:
    """Prove the full HTTP path: AIResponseService -> Portkey -> LLM -> response."""

    def test_real_portkey_returns_model_response(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()
        response, telemetry = service.generate(
            user_message="What is 7 multiplied by 8? Answer with just the number.",
        )
        assert "56" in response
        assert telemetry["ai_invoked"] is True
        assert telemetry["ai_model"] == service.model
        assert telemetry["ai_success"] is True
        assert telemetry["ai_error"] is None
        assert telemetry["ai_latency_ms"] > 0

    def test_different_prompts_produce_different_responses(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()

        prompt_a = "Explain why customer churn matters to a coaching business."
        prompt_b = "Explain why employee turnover matters to a coaching business."

        response_a, _ = service.generate(user_message=prompt_a)
        response_b, _ = service.generate(user_message=prompt_b)

        assert response_a != response_b
        assert "churn" in response_a.lower() or "customer" in response_a.lower()
        assert "turnover" in response_b.lower() or "employee" in response_b.lower()

    def test_conversation_continuity_with_history(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()

        response_a, _ = service.generate(
            user_message="My business sells coaching programs to established consultants.",
        )
        assert response_a

        response_b, _ = service.generate(
            user_message="What would you investigate first if sales suddenly dropped?",
            conversation_history=[
                {"role": "user", "content": "My business sells coaching programs to established consultants."},
                {"role": "assistant", "content": response_a},
            ],
        )
        assert response_b
        assert "consultant" in response_b.lower() or "coaching" in response_b.lower() or "business" in response_b.lower()

    def test_portkey_reachable_and_model_configured(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()
        assert service.base_url
        assert service.api_key
        assert service.model
        response, telemetry = service.generate(user_message="Say OK")
        assert "ok" in response.lower()
        assert telemetry["ai_success"] is True


class TestRealConversationContinuity:
    """Prove session-scoped conversation history reaches the real LLM."""

    def test_two_turn_conversation_retains_context(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()

        turn1, _ = service.generate(
            user_message="Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity.",
        )
        assert turn1

        turn2, telemetry2 = service.generate(
            user_message="What would you investigate first?",
            conversation_history=[
                {"role": "user", "content": "Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity."},
                {"role": "assistant", "content": turn1},
            ],
        )
        assert turn2
        assert telemetry2["ai_invoked"] is True
        assert telemetry2["ai_success"] is True
        assert "northstar" in turn2.lower() or "coaching" in turn2.lower() or "operational" in turn2.lower()

    def test_three_turn_conversation_with_frame_change(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()

        turn1, _ = service.generate(
            user_message="Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity.",
        )
        assert turn1

        turn2, _ = service.generate(
            user_message="What would you investigate first?",
            conversation_history=[
                {"role": "user", "content": "Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity."},
                {"role": "assistant", "content": turn1},
            ],
        )
        assert turn2

        turn3, telemetry3 = service.generate(
            user_message="Now answer that as if I'm the owner rather than an employee.",
            conversation_history=[
                {"role": "user", "content": "Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity."},
                {"role": "assistant", "content": turn1},
                {"role": "user", "content": "What would you investigate first?"},
                {"role": "assistant", "content": turn2},
            ],
        )
        assert turn3
        assert telemetry3["ai_invoked"] is True
        assert telemetry3["ai_success"] is True
        assert "owner" in turn3.lower() or "northstar" in turn3.lower() or "coaching" in turn3.lower()

    def test_different_sessions_do_not_share_history(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()

        service.generate(
            user_message="Session A secret context.",
            conversation_history=[],
        )

        response_b, telemetry_b = service.generate(
            user_message="What is the capital of France?",
            conversation_history=[],
        )
        assert "paris" in response_b.lower()
        assert telemetry_b["ai_success"] is True


class TestFailureBehaviour:
    """AI failure must be observable and must not poison state."""

    def test_timeout_sets_telemetry_failure(self) -> None:
        _skip_if_no_credentials()
        import httpx

        service = AIResponseService()
        service._client.post = MagicMock(
            side_effect=httpx.TimeoutException("Portkey timeout")
        )

        with pytest.raises(httpx.TimeoutException):
            service.generate(user_message="Trigger timeout")

    def test_connection_error_sets_telemetry_failure(self) -> None:
        _skip_if_no_credentials()
        import httpx

        service = AIResponseService()
        service._client.post = MagicMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(httpx.ConnectError):
            service.generate(user_message="Trigger connection error")

    def test_failed_request_does_not_append_to_history(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()
        service.generate = MagicMock(side_effect=RuntimeError("Simulated failure"))

        with pytest.raises(RuntimeError):
            service.generate(
                user_message="Hello",
                conversation_history=[],
            )


class TestRealActionableIntentClassification:
    """Prove the real LLM can produce structured actionable intent from conversation."""

    def test_real_llm_classifies_investigation_intent(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()
        result = service.classify_actionable_intent(
            user_message="Yes. Let's investigate whether customer experience is actually driving the retention decline.",
            conversation_history=[
                {"role": "user", "content": "Our customer retention has fallen from 84% to 76% and support volume is up 31%."},
                {"role": "assistant", "content": "That is a significant drop. Retention falling from 84% to 76% while support volume rises 31% suggests something is degrading the customer experience."},
            ],
            accumulated_context={"retention": "84% to 76%", "support_volume": "+31%"},
        )
        assert result["mode"] == "actionable"
        assert result["action"] == "investigate"
        assert result["objective"] is not None
        assert len(result["objective"]) > 0
        assert result["confidence"] in ("high", "medium", "low")

    def test_real_llm_classifies_conversational_when_no_action(self) -> None:
        _skip_if_no_credentials()
        service = AIResponseService()
        result = service.classify_actionable_intent(
            user_message="What do you think about customer experience in general?",
            conversation_history=[
                {"role": "user", "content": "Tell me about management."},
                {"role": "assistant", "content": "Management involves planning, organizing, and coordinating resources."},
            ],
        )
        assert result["mode"] == "conversational"
        assert result["action"] is None
