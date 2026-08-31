"""
Execution backends and Operations registration (Increment 22A).

Execution backends are backend execution mechanisms.
They do not subscribe to Organisation events directly.

Operations is the coordination layer that:
- Subscribes to OrganisationControlPlane events
- Selects exactly one backend per READY Work
- Reports results back to the Organisation
"""

from __future__ import annotations

import logging
from typing import Any

from contracts.organisational_events import WorkEvent, WorkEventType
from role import Work, WorkStatus

logger = logging.getLogger("workflow_runner.operational")


class PaperclipExecutionHandler:
    """Paperclip execution backend.

    Wraps the Paperclip adapter as an execution backend.
    Does not subscribe to Organisation events.
    """

    def __init__(self, paperclip_plane: Any) -> None:
        self._paperclip = paperclip_plane

    def execute(self, work: Work) -> dict[str, Any]:
        """Execute work via Paperclip."""
        if not work.assignee_agent_id:
            raise ValueError("Paperclip execution requires assignee_agent_id")

        result = self._paperclip.trigger_execution(work.id, work.assignee_agent_id)
        if result is None:
            raise RuntimeError("Failed to trigger Paperclip execution")

        updated_work = self._paperclip.wait_for_execution(
            work.id, work.assignee_agent_id
        )
        if updated_work is None:
            raise RuntimeError("Paperclip execution did not complete")

        if updated_work.status == WorkStatus.COMPLETED:
            return updated_work.outcome or {"status": "completed"}
        if updated_work.status == WorkStatus.FAILED:
            raise RuntimeError("Paperclip execution failed")

        raise RuntimeError(f"Unexpected Paperclip status: {updated_work.status}")


class WorkerExecutionHandler:
    """Worker execution backend.

    Wraps the local Worker as an execution backend.
    Does not subscribe to Organisation events.
    """

    def __init__(self, worker: Any) -> None:
        self._worker = worker

    def execute(self, work: Work) -> dict[str, Any]:
        """Execute work via the Worker."""
        return self._worker.execute(work)


def register_operational_handlers(
    org_plane: Any,
    capability_execution: Any = None,
    capability_registry: Any = None,
) -> None:
    """Register Operations coordination layer on the Organisation control plane.

    This function is called during application startup. It creates the
    Operations coordination component which subscribes to Organisation
    events and dispatches execution to exactly one backend.

    The function imports operational backends internally so that the caller
    does not need to depend on them directly.
    """
    if org_plane is None:
        return

    try:
        from workflow_runner.src.operations import (
            ExecutionBackend,
            Operations,
            PaperclipBackend,
            WorkerBackend,
        )
        from workflow_runner.src.worker import Worker

        worker = Worker(
            capability_execution=capability_execution,
            capability_registry=capability_registry,
        )
        backends: list[ExecutionBackend] = [WorkerBackend(worker, org_plane)]

        try:
            from organisation_paperclip import PaperclipOrganisationControlPlane
            if isinstance(org_plane, PaperclipOrganisationControlPlane):
                backends.append(PaperclipBackend(org_plane))
        except ImportError:
            pass

        Operations(
            org_plane=org_plane,
            backends=backends,
        )
    except Exception:
        logger.exception("Failed to register Operations coordination layer")
