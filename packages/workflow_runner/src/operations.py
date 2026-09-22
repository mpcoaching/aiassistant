"""
Operations coordination layer (Increment 22B).

Operations is the execution coordination component between the Organisation
and execution backends.

Architecture:
  Organisation
      ↓ WorkEventType.READY
  Operations
      ↓ selects exactly ONE backend
      ├── WorkerBackend
      ├── PaperclipBackend
      └── PathwayRuntimeBackend (future)
      ↓
  Operations reports result
      ↓
  Organisation.complete_work() / fail_work()

Operations owns execution coordination and backend selection.
The Organisation owns organisational truth.
Execution backends own execution mechanics.

Design constraints:
- Operations depends on OrganisationControlPlane, not concrete implementations
- Operations depends on ExecutionBackend protocol, not concrete backends
- Execution backends do not subscribe to Organisation events directly
- Operations is the sole subscriber for execution coordination
- Backend selection is explicit and deterministic
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from contracts.organisational_events import WorkEvent, WorkEventType
from role import Work, WorkStatus

logger = logging.getLogger("workflow_runner.operations")


class ExecutionBackend(Protocol):
    """Protocol for execution backends.

    An execution backend is a mechanism that can execute a Work item
    and return a result. Operations depends on this protocol, not on
    concrete backend implementations.
    """

    def execute(self, work: Work) -> dict[str, Any]:
        """Execute the work and return the result.

        Raises an exception if execution fails.
        """
        ...

    def can_handle(self, work: Work) -> bool:
        """Return True if this backend can execute the given work."""
        ...


class WorkerBackend:
    """Worker execution backend.

    Wraps the local Worker as an execution backend for Operations.
    Does not subscribe to Organisation events.
    Implements ExecutionBackend protocol.
    """

    def __init__(self, worker: Any, org_plane: Any) -> None:
        self._worker = worker
        self._org_plane = org_plane

    def execute(self, work: Work) -> dict[str, Any]:
        """Execute work via the Worker."""
        return self._worker.execute(work, self._org_plane)

    def can_handle(self, work: Work) -> bool:
        """Worker handles work that has no assigned Paperclip agent."""
        return not work.assignee_agent_id


class PaperclipBackend:
    """Paperclip execution backend.

    Wraps the Paperclip adapter as an execution backend for Operations.
    Does not subscribe to Organisation events.
    Implements ExecutionBackend protocol.
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

    def can_handle(self, work: Work) -> bool:
        """Paperclip can handle work with an assigned agent."""
        return bool(work.assignee_agent_id)


class Operations:
    """Operational coordination layer.

    Subscribes to OrganisationControlPlane events.
    Selects exactly one execution backend per READY Work.
    Reports results back to the Organisation.

    Backend selection rule:
    1. If Paperclip backend is available AND work has assignee_agent_id → Paperclip
    2. Otherwise → Worker (if available)
    3. If no backend is available → log warning and skip

    This rule is deterministic, testable, and based on existing Work model fields.
    """

    def __init__(
        self,
        org_plane: Any,
        backends: list[ExecutionBackend] | None = None,
        capability_registry: Any = None,
    ) -> None:
        self._org_plane = org_plane
        self._backends = backends or []
        self._capability_registry = capability_registry
        self._processed_work_ids: set[str] = set()
        self._proficiencies: dict[str, Any] = {}
        org_plane.on_event(self._handle_event)

    def _handle_event(self, event: Any) -> None:
        if not isinstance(event, WorkEvent):
            return
        if event.event_type != WorkEventType.READY:
            return

        work_id = event.work_id
        if work_id in self._processed_work_ids:
            return
        self._processed_work_ids.add(work_id)

        work = self._org_plane.get_work(work_id)
        if work is None:
            logger.warning("Work %s not found for execution", work_id)
            return

        if work.work_type == "capability_development":
            if self._capability_registry is None:
                self._org_plane.fail_work(work_id, {"error": "capability_registry_not_configured"})
                return
            backend = self._select_backend(work)
            if backend is None:
                self._org_plane.fail_work(work_id, {"error": "no_execution_backend"})
                return
            try:
                result = backend.execute(work)
                self._assess_capability_development(work, result)
                self._org_plane.complete_work(work_id, result)
            except Exception as exc:
                logger.exception("Execution failed for work %s: %s", work_id, exc)
                self._org_plane.fail_work(work_id, {"error": str(exc)})
            return

        backend = self._select_backend(work)
        if backend is None:
            logger.warning(
                "No execution backend available for work %s", work_id
            )
            return

        try:
            result = backend.execute(work)
            self._org_plane.complete_work(work_id, result)
        except Exception as exc:
            logger.exception("Execution failed for work %s: %s", work_id, exc)
            self._org_plane.fail_work(work_id, {"error": str(exc)})

    def _assess_capability_development(self, work: Work, execution_result: dict[str, Any]) -> dict[str, Any]:
        """Assess a capability-development execution result.

        Does not emit capability-development lifecycle events.
        Records the assessment for proficiency tracking.
        """
        from organisation.src.outcome import assess_capability_development

        cap = None
        if self._capability_registry is not None:
            cap = self._capability_registry.get(work.develops_capability_id or f"cap-{work.id}")
        if cap is None:
            cap = self._org_plane.get_capability(work.develops_capability_id or f"cap-{work.id}")

        assessment = assess_capability_development(work, cap, execution_result)

        if assessment["passed"]:
            capability_id = assessment.get("capability_id")
            if capability_id and self._capability_registry is not None:
                promoted = self._capability_registry.promote(capability_id)
                self._record_proficiency(work, promoted, assessment)

        return assessment

    def _record_proficiency(self, work: Work, capability: Any, assessment: dict[str, Any]) -> None:
        """Record a CapabilityProficiency for the actor that developed the capability."""
        try:
            from capability_proficiency import CapabilityProficiency, ProficiencyLevel
        except ImportError:
            return

        actor_id = work.assignee_actor_id or work.assignee_agent_id or work.assignee_person_id
        if actor_id is None:
            return

        prof = CapabilityProficiency(
            id=f"prof-{actor_id}-{assessment.get('capability_id', '')}-{work.id}",
            capability_id=assessment.get("capability_id", ""),
            actor_id=actor_id,
            proficiency_level=ProficiencyLevel.PROFICIENT,
            evidence=assessment.get("evidence", []),
        )
        self._proficiencies[prof.id] = prof

    def _select_backend(self, work: Work) -> ExecutionBackend | None:
        """Select exactly one execution backend for the Work."""
        for backend in self._backends:
            if backend.can_handle(work):
                return backend
        return None
