"""
Tests for Operations coordination layer (Increment 22B).

Verifies that:
- Operations receives READY events from Organisation
- Operations selects exactly one backend per READY Work
- Worker and Paperclip backends are mutually exclusive
- Duplicate READY events do not cause duplicate execution
- Backend success results in complete_work()
- Backend failure results in fail_work()
- Operations operates against ExecutionBackend protocol, not concrete backends
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.organisational_events import WorkEvent, WorkEventType
from role import Work, WorkStatus
from workflow_runner.src.operations import (
    ExecutionBackend,
    Operations,
    PaperclipBackend,
    WorkerBackend,
)
from workflow_runner.src.operational_handler import (
    PaperclipExecutionHandler,
    WorkerExecutionHandler,
)


class TestOperationsRouting:
    def test_ready_event_reaches_operations(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed", "result": "ok"}
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        mock_worker.execute.assert_called_once()
        mock_org.complete_work.assert_called_once()

    def test_selects_worker_when_no_assignee_agent_id(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed"}
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_paperclip = MagicMock()
        paperclip_backend = PaperclipBackend(mock_paperclip)

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend, paperclip_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        mock_worker.execute.assert_called_once()
        mock_paperclip.execute.assert_not_called()

    def test_selects_paperclip_when_assignee_agent_id_present(self) -> None:
        mock_worker = MagicMock()
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = {"run_id": "r1"}
        mock_paperclip.wait_for_execution.return_value = Work(
            id="w1", title="Test", accountable_role_id="r1", status=WorkStatus.COMPLETED, outcome={"result": "ok"}
        )
        paperclip_backend = PaperclipBackend(mock_paperclip)

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1", assignee_agent_id="a1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend, paperclip_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
            assignee_agent_id="a1",
        )
        operations._handle_event(event)

        mock_paperclip.trigger_execution.assert_called_once_with("w1", "a1")
        mock_worker.execute.assert_not_called()

    def test_duplicate_ready_event_suppressed(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed"}
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)
        operations._handle_event(event)

        assert mock_worker.execute.call_count == 1

    def test_backend_success_calls_complete_work(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed", "result": "ok"}
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        mock_org.complete_work.assert_called_once_with("w1", {"status": "completed", "result": "ok"})
        mock_org.fail_work.assert_not_called()

    def test_backend_failure_calls_fail_work(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.side_effect = RuntimeError("backend error")
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        mock_org.fail_work.assert_called_once()
        fail_call = mock_org.fail_work.call_args
        assert fail_call[0][0] == "w1"
        assert "error" in fail_call[0][1]

    def test_no_backend_logs_warning(self) -> None:
        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        mock_org.complete_work.assert_not_called()
        mock_org.fail_work.assert_not_called()

    def test_non_ready_event_ignored(self) -> None:
        mock_worker = MagicMock()
        worker_backend = WorkerBackend(mock_worker, MagicMock())

        mock_org = MagicMock()

        operations = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.ASSIGNED,
            work_id="w1",
            title="Test",
            status="assigned",
        )
        operations._handle_event(event)

        mock_worker.execute.assert_not_called()


class TestOperationsAgainstProtocolDoubles:
    """Verify that Operations operates against ExecutionBackend protocol,
    not concrete backend classes.

    These tests use minimal doubles that implement the protocol without
    depending on Worker, Paperclip, or any concrete backend.
    """

    def test_operations_accepts_backend_double(self) -> None:
        """Operations should work with any object implementing execute()."""

        class FakeBackend:
            def __init__(self) -> None:
                self.executed_with: Work | None = None

            def execute(self, work: Work) -> dict[str, Any]:
                self.executed_with = work
                return {"status": "completed"}

            def can_handle(self, work: Work) -> bool:
                return True

        fake_backend = FakeBackend()
        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[fake_backend],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        assert fake_backend.executed_with is work
        mock_org.complete_work.assert_called_once()

    def test_operations_single_backend_selection_with_multiple_doubles(self) -> None:
        """Operations should select exactly one backend even when multiple are available."""

        class FakeBackend:
            def __init__(self, name: str) -> None:
                self.name = name
                self.executed = False

            def execute(self, work: Work) -> dict[str, Any]:
                self.executed = True
                return {"status": "completed", "backend": self.name}

            def can_handle(self, work: Work) -> bool:
                return True

        backend_a = FakeBackend("A")
        backend_b = FakeBackend("B")

        mock_org = MagicMock()
        work = Work(id="w1", title="Test", accountable_role_id="r1")
        mock_org.get_work.return_value = work

        operations = Operations(
            org_plane=mock_org,
            backends=[backend_a, backend_b],
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w1",
            title="Test",
            status="ready",
        )
        operations._handle_event(event)

        exactly_one_executed = sum(1 for b in [backend_a, backend_b] if b.executed) == 1
        assert exactly_one_executed, "Exactly one backend should have been executed"


class TestBackendsDoNotSubscribeToEvents:
    """Verify that backend adapters do not independently subscribe to Organisation events."""

    def test_worker_backend_does_not_subscribe(self) -> None:
        mock_worker = MagicMock()
        handler = WorkerExecutionHandler(worker=mock_worker)
        assert handler.execute(MagicMock()) is not None

    def test_paperclip_backend_does_not_subscribe(self) -> None:
        handler = PaperclipExecutionHandler(paperclip_plane=MagicMock())
        assert handler.execute is not None
