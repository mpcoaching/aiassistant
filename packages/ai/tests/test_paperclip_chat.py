"""
Layer 1 — Unit tests for PaperclipChatService.

Tests the adapter boundary between Paperclip and the existing AI runtime.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ai.src.paperclip_chat import PaperclipChatService


pytestmark = pytest.mark.unit


def _make_work(work_id: str, status_value: str = "pending", outcome: dict | None = None) -> MagicMock:
    work = MagicMock()
    work.id = work_id
    work.status.value = status_value
    work.outcome = outcome
    return work


def test_chat_returns_error_when_agent_id_missing() -> None:
    service = PaperclipChatService(assistant_agent_id="")
    response = service.chat("Hello")
    assert response.status == "error"
    assert "not configured" in response.message


def test_chat_returns_error_when_org_plane_missing() -> None:
    service = PaperclipChatService(org_plane=None, assistant_agent_id="agent-1")
    response = service.chat("Hello")
    assert response.status == "error"
    assert "control plane" in response.message


def test_chat_creates_work_and_waits_for_execution() -> None:
    org_plane = MagicMock()
    org_plane.list_work.return_value = []
    org_plane.create_work.return_value = _make_work("work-1")
    org_plane.wait_for_execution.return_value = _make_work(
        "work-1",
        status_value="completed",
        outcome={
            "stdout": json.dumps({
                "response": "The answer is 42.",
                "model": "qwen/qwen3.8-27b",
                "aiInvoked": True,
                "aiSuccess": True,
                "latencyMs": 123,
            })
        },
    )

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("What is the answer?", session_id="ses-test")

    org_plane.create_work.assert_called_once_with(
        title="chat:ses-test",
        description="What is the answer?",
        assignee_agent_id="agent-1",
        priority="medium",
    )
    org_plane.trigger_execution.assert_called_once_with("work-1", "agent-1")
    org_plane.wait_for_execution.assert_called_once_with("work-1")

    assert response.status == "completed"
    assert response.message == "The answer is 42."
    assert response.telemetry["runtime"] == "paperclip"
    assert response.telemetry["model"] == "qwen/qwen3.8-27b"
    assert response.telemetry["ai_invoked"] is True
    assert response.telemetry["ai_success"] is True
    assert response.telemetry["ai_latency_ms"] == 123


def test_chat_handles_failed_execution() -> None:
    org_plane = MagicMock()
    org_plane.list_work.return_value = []
    org_plane.create_work.return_value = _make_work("work-1")
    org_plane.wait_for_execution.return_value = _make_work(
        "work-1",
        status_value="failed",
        outcome={"stdout": json.dumps({"response": "Error occurred", "aiSuccess": False})},
    )

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("Hello", session_id="ses-fail")

    assert response.status == "completed"
    assert response.message == "Error occurred"
    assert response.telemetry["ai_success"] is False


def test_chat_handles_timeout() -> None:
    org_plane = MagicMock()
    org_plane.list_work.return_value = []
    org_plane.create_work.return_value = _make_work("work-1")
    org_plane.wait_for_execution.return_value = None

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("Hello", session_id="ses-timeout")

    assert response.status == "timeout"
    assert "did not complete" in response.message


def test_chat_handles_create_work_failure() -> None:
    org_plane = MagicMock()
    org_plane.list_work.return_value = []
    org_plane.create_work.side_effect = RuntimeError("Paperclip down")

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("Hello", session_id="ses-fail-create")

    assert response.status == "error"
    assert "Failed to create or locate" in response.message


def test_chat_handles_malformed_stdout() -> None:
    org_plane = MagicMock()
    org_plane.list_work.return_value = []
    org_plane.create_work.return_value = _make_work("work-1")
    org_plane.wait_for_execution.return_value = _make_work(
        "work-1",
        status_value="completed",
        outcome={"stdout": "not-json"},
    )

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("Hello", session_id="ses-malformed")

    assert response.status == "completed"
    assert response.message == "not-json"


def test_chat_handles_empty_stdout() -> None:
    org_plane = MagicMock()
    org_plane.list_work.return_value = []
    org_plane.create_work.return_value = _make_work("work-1")
    org_plane.wait_for_execution.return_value = _make_work(
        "work-1",
        status_value="completed",
        outcome={"stdout": ""},
    )

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("Hello", session_id="ses-empty")

    assert response.status == "completed"
    assert "no response" in response.message


def test_chat_reuses_existing_work_for_same_session() -> None:
    existing = _make_work("work-existing", status_value="in_progress")
    existing.title = "chat:ses-multi"
    existing.description = "First message"
    existing.assignee_agent_id = "agent-1"

    org_plane = MagicMock()
    org_plane.list_work.return_value = [existing]
    org_plane.update_work.return_value = existing
    org_plane.wait_for_execution.return_value = _make_work(
        "work-existing",
        status_value="completed",
        outcome={
            "stdout": json.dumps({
                "response": "Follow-up answer",
                "model": "qwen/qwen3.8-27b",
                "aiInvoked": True,
                "aiSuccess": True,
                "latencyMs": 200,
            })
        },
    )

    service = PaperclipChatService(org_plane=org_plane, assistant_agent_id="agent-1")
    response = service.chat("Second message", session_id="ses-multi")

    org_plane.create_work.assert_not_called()
    org_plane.update_work.assert_called_once_with("work-existing", description="Second message")
    org_plane.trigger_execution.assert_called_once_with("work-existing", "agent-1")
    assert response.status == "completed"
    assert response.message == "Follow-up answer"
    assert response.session_id == "ses-multi"
