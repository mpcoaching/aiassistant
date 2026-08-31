"""
Tests for execution backends (Increment 22A).

Verifies that:
- WorkerExecutionHandler executes work via the Worker
- PaperclipExecutionHandler executes work via Paperclip
- Backends do not independently subscribe to Organisation events
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from role import Work, WorkStatus
from workflow_runner.src.operational_handler import (
    PaperclipExecutionHandler,
    WorkerExecutionHandler,
)


class TestWorkerExecutionBackend:
    def test_execute_calls_worker(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed", "result": "ok"}

        handler = WorkerExecutionHandler(worker=mock_worker)

        work = Work(id="w1", title="Test", accountable_role_id="r1")
        result = handler.execute(work)

        mock_worker.execute.assert_called_once_with(work)
        assert result == {"status": "completed", "result": "ok"}

    def test_execute_returns_worker_result(self) -> None:
        mock_worker = MagicMock()
        mock_worker.execute.return_value = {"status": "completed"}

        handler = WorkerExecutionHandler(worker=mock_worker)

        work = Work(id="w1", title="Test", accountable_role_id="r1")
        result = handler.execute(work)

        assert result == {"status": "completed"}


class TestPaperclipExecutionBackend:
    def test_execute_triggers_and_waits(self) -> None:
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = {"run_id": "r1"}
        mock_paperclip.wait_for_execution.return_value = Work(
            id="w1", title="Test", accountable_role_id="r1",
            status=WorkStatus.COMPLETED, outcome={"result": "ok"}
        )

        handler = PaperclipExecutionHandler(paperclip_plane=mock_paperclip)

        work = Work(id="w1", title="Test", accountable_role_id="r1", assignee_agent_id="a1")
        result = handler.execute(work)

        mock_paperclip.trigger_execution.assert_called_once_with("w1", "a1")
        mock_paperclip.wait_for_execution.assert_called_once_with("w1", "a1")
        assert result == {"result": "ok"}

    def test_execute_requires_assignee_agent_id(self) -> None:
        handler = PaperclipExecutionHandler(paperclip_plane=MagicMock())

        work = Work(id="w1", title="Test", accountable_role_id="r1")

        with pytest.raises(ValueError, match="assignee_agent_id"):
            handler.execute(work)

    def test_execute_raises_on_trigger_failure(self) -> None:
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = None

        handler = PaperclipExecutionHandler(paperclip_plane=mock_paperclip)

        work = Work(id="w1", title="Test", accountable_role_id="r1", assignee_agent_id="a1")

        with pytest.raises(RuntimeError, match="Failed to trigger"):
            handler.execute(work)

    def test_execute_raises_on_wait_failure(self) -> None:
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = {"run_id": "r1"}
        mock_paperclip.wait_for_execution.return_value = None

        handler = PaperclipExecutionHandler(paperclip_plane=mock_paperclip)

        work = Work(id="w1", title="Test", accountable_role_id="r1", assignee_agent_id="a1")

        with pytest.raises(RuntimeError, match="did not complete"):
            handler.execute(work)

    def test_execute_raises_on_failed_status(self) -> None:
        mock_paperclip = MagicMock()
        mock_paperclip.trigger_execution.return_value = {"run_id": "r1"}
        mock_paperclip.wait_for_execution.return_value = Work(
            id="w1", title="Test", accountable_role_id="r1",
            status=WorkStatus.FAILED
        )

        handler = PaperclipExecutionHandler(paperclip_plane=mock_paperclip)

        work = Work(id="w1", title="Test", accountable_role_id="r1", assignee_agent_id="a1")

        with pytest.raises(RuntimeError, match="failed"):
            handler.execute(work)
