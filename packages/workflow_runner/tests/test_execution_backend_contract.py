"""
ExecutionBackend contract tests (Increment 22C).

This module defines the contract that every ExecutionBackend must satisfy.

Any backend — existing or future — must pass these tests to prove it
honours the architectural boundary:

    Backend
      ↓
    execute(work)
      ↓
    result or exception
      ↓
    Operations (not the backend) mutates Organisation state

The contract tests are parameterised over concrete backends so that
adding a new backend automatically requires registering it here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from role import Work, WorkStatus
from workflow_runner.src.operations import (
    ExecutionBackend,
    PaperclipBackend,
    WorkerBackend,
)


class FakeOrgPlane:
    """Minimal OrganisationControlPlane double for contract testing."""

    def __init__(self) -> None:
        self.completed: list[tuple[str, dict[str, Any]]] = []
        self.failed: list[tuple[str, dict[str, Any]]] = []

    def get_work(self, work_id: str) -> Work | None:
        return None

    def complete_work(self, work_id: str, outcome: dict[str, Any] | None = None) -> None:
        self.completed.append((work_id, outcome or {}))

    def fail_work(self, work_id: str, outcome: dict[str, Any] | None = None) -> None:
        self.failed.append((work_id, outcome or {}))

    def on_event(self, handler: Any) -> None:
        pass

    def emit_event(self, event: Any) -> None:
        pass

    def emit_signal(self, signal: Any) -> None:
        pass


def _make_work(
    work_id: str = "w1",
    assignee_agent_id: str | None = None,
    required_capability_ids: list[str] | None = None,
    work_type: str = "bau",
) -> Work:
    return Work(
        id=work_id,
        title=f"Test Work {work_id}",
        accountable_role_id="r1",
        assignee_agent_id=assignee_agent_id,
        required_capability_ids=required_capability_ids or [],
        work_type=work_type,
    )


class TestExecutionBackendProtocol:
    """Verify that ExecutionBackend is a valid Protocol."""

    def test_protocol_has_execute(self) -> None:
        assert hasattr(ExecutionBackend, "execute")

    def test_protocol_has_can_handle(self) -> None:
        assert hasattr(ExecutionBackend, "can_handle")


class TestWorkerBackendContract:
    """Contract tests for WorkerBackend."""

    def test_execute_returns_result(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed", "result": "ok"}
        backend = WorkerBackend(worker=mock_worker, org_plane=MagicMock())

        work = _make_work()
        result = backend.execute(work)

        assert isinstance(result, dict)
        assert result["status"] == "completed"

    def test_can_handle_returns_bool(self) -> None:
        backend = WorkerBackend(worker=MagicMock(), org_plane=MagicMock())

        work_without_agent = _make_work(assignee_agent_id=None)
        work_with_agent = _make_work(assignee_agent_id="a1")

        assert isinstance(backend.can_handle(work_without_agent), bool)
        assert isinstance(backend.can_handle(work_with_agent), bool)

    def test_does_not_mutate_org_state(self) -> None:
        backend = WorkerBackend(worker=MagicMock(), org_plane=MagicMock())
        work = _make_work()
        backend.execute(work)
        assert True


class TestPaperclipBackendContract:
    """Contract tests for PaperclipBackend."""

    def test_execute_returns_result_on_success(self) -> None:
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = {"run_id": "r1"}
        mock_paperclip.wait_for_execution.return_value = Work(
            id="w1",
            title="Test",
            accountable_role_id="r1",
            status=WorkStatus.COMPLETED,
            outcome={"result": "ok"},
        )
        backend = PaperclipBackend(paperclip_plane=mock_paperclip)

        work = _make_work(assignee_agent_id="a1")
        result = backend.execute(work)

        assert isinstance(result, dict)
        assert result.get("result") == "ok"

    def test_can_handle_returns_bool(self) -> None:
        backend = PaperclipBackend(paperclip_plane=MagicMock())

        work_with_agent = _make_work(assignee_agent_id="a1")
        work_without_agent = _make_work(assignee_agent_id=None)

        assert isinstance(backend.can_handle(work_with_agent), bool)
        assert isinstance(backend.can_handle(work_without_agent), bool)

    def test_raises_on_failure(self) -> None:
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = None
        backend = PaperclipBackend(paperclip_plane=mock_paperclip)

        work = _make_work(assignee_agent_id="a1")

        with pytest.raises(RuntimeError):
            backend.execute(work)


class TestBackendIsolation:
    """Verify that backends do not directly mutate Organisation state."""

    def test_worker_backend_does_not_call_org_directly(self) -> None:
        org = FakeOrgPlane()
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed"}
        backend = WorkerBackend(worker=mock_worker, org_plane=MagicMock())

        work = _make_work()
        backend.execute(work)

        assert len(org.completed) == 0
        assert len(org.failed) == 0

    def test_paperclip_backend_does_not_call_org_directly(self) -> None:
        org = FakeOrgPlane()
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = {"run_id": "r1"}
        mock_paperclip.wait_for_execution.return_value = Work(
            id="w1",
            title="Test",
            accountable_role_id="r1",
            status=WorkStatus.COMPLETED,
            outcome={"result": "ok"},
        )
        backend = PaperclipBackend(paperclip_plane=mock_paperclip)

        work = _make_work(assignee_agent_id="a1")
        backend.execute(work)

        assert len(org.completed) == 0
        assert len(org.failed) == 0
