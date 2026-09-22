"""
OrganisationControlPlane abstraction and in-memory implementation (Increment 6, corrected Increment 9, corrected Increment 11).

Defines the narrow interface for the Organisation/Control plane plus a
reference in-memory implementation for testing and local development.

OrganisationControlPlane is mechanism-only:
- provides role lookup, work assignment, authority delegation, organisational context
- provides work status transitions (mark_work_ready for operational handoff)
- emits operational events and organisational signals through dedicated ports
- does NOT store Person/Agent records (owned by People/Capability, ADR-037)
- does NOT coordinate work (belongs to roles)
- does NOT become the CEO/COO/PM
- does NOT execute capabilities or operational work

Imports: role module only. No capability_registry, no concepts, no Paperclip, no pathway_runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from role import (
    Agent,
    Assignment,
    AssignmentStatus,
    Authority,
    Delegation,
    OrgContext,
    Person,
    Role,
    RoleStatus,
    Work,
    WorkStatus,
)
from actor import Actor, ActorType
from contracts.organisational_events import WorkEventType


class OrganisationControlPlane(ABC):
    """Narrow abstraction for organisational mechanisms and context.

    Explicitly excluded:
    - find_capability()
    - match_capability()
    - execute_capability()
    - execute_work()
    - run_agent()
    - invoke_tool()
    - register_person()
    - register_agent()
    - store Person/Agent records
    - coordinate work
    - become the CEO/COO/PM
    """

    @abstractmethod
    def get_role(self, role_id: str) -> Role | None:
        """Retrieve a role by ID."""
        raise NotImplementedError

    @abstractmethod
    def list_roles(self) -> list[Role]:
        """List all active roles."""
        raise NotImplementedError

    @abstractmethod
    def get_organisational_context(
        self, request_context: dict[str, Any]
    ) -> OrgContext:
        """Derive organisational context from a request."""
        raise NotImplementedError

    @abstractmethod
    def assign_work(
        self, work: Work, assignee: Role | Person | Agent
    ) -> Assignment:
        """Assign work to a role, person, or agent.

        Reads the assignee's ID but does NOT store the Person/Agent record.
        Person/Agent records are owned by People/Capability (ADR-037).
        """
        raise NotImplementedError

    @abstractmethod
    def get_work(self, work_id: str) -> Work | None:
        """Retrieve work by ID."""
        raise NotImplementedError

    @abstractmethod
    def list_work(self) -> list[Work]:
        """List all work items."""
        raise NotImplementedError

    @abstractmethod
    def delegate_authority(
        self, from_role: Role, to_role: Role, authority: Authority
    ) -> Delegation:
        """Delegate authority from one role to another."""
        raise NotImplementedError

    @abstractmethod
    def mark_work_ready(self, work_id: str) -> Work | None:
        """Mark organisational Work as ready for operational execution.

        Transitions Work.status to READY. This is an organisational
        handoff signal, NOT operational execution. Operations is responsible
        for picking up ready Work and executing it via its own entry points
        (PathwayRuntime, execute_workflow, etc.).
        """
        raise NotImplementedError

    @abstractmethod
    def complete_work(self, work_id: str, outcome: dict[str, Any] | None = None) -> Work | None:
        """Mark organisational Work as completed with an execution outcome.

        Transitions Work.status to COMPLETED and records the outcome.
        This is an organisational state mutation based on operational facts.
        """
        raise NotImplementedError

    @abstractmethod
    def fail_work(self, work_id: str, outcome: dict[str, Any] | None = None) -> Work | None:
        """Mark organisational Work as failed with an execution outcome.

        Transitions Work.status to FAILED and records the outcome.
        This is an organisational state mutation based on operational facts.
        """
        raise NotImplementedError

    @abstractmethod
    def query_capability(self, capability_id: str) -> Any | None:
        """Query whether a capability is currently available.

        Returns minimal availability information: whether the capability
        exists, whether it is currently available, and a simple ETA.
        """
        raise NotImplementedError

    @abstractmethod
    def register_capability(self, capability: Any, work_id: str | None = None) -> None:
        """Register a capability in the organisational capability store.

        This is used for capability development: when a worker develops
        a new capability, it is registered here so the organisation
        can subsequently query and use it.
        """
        raise NotImplementedError

    @abstractmethod
    def get_capability(self, capability_id: str) -> Any | None:
        """Retrieve a registered capability by ID."""
        raise NotImplementedError

    @abstractmethod
    def select_execution_path(
        self,
        intent: str,
        context: dict[str, Any],
        capability_query: Any = None,
        workflow_lookup: Any = None,
    ) -> Any:
        """Select the organisational execution path for a request.

        Decision hierarchy:
        1. Existing workflow → EXISTING_WORKFLOW
        2. Capability available → CAPABILITY_PATH
        3. Capability exists but unavailable → HUMAN_TEAM_INVESTIGATION
        4. Capability gap → NEW_CAPABILITY_REQUIRED
        """
        raise NotImplementedError

    @abstractmethod
    def execute_organisational_change(
        self,
        work: Work,
        actor: Any,
        capability_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute an organisational change (e.g. capability assignment).

        Checks authority delegation before applying changes. Returns a
        result dict with status and details.
        """
        raise NotImplementedError

    @abstractmethod
    def emit_event(self, event: Any) -> None:
        """Emit an operational event through the organisation's event boundary.

        Implementations may buffer, publish, log, or ignore events.
        This is a communication mechanism, not an orchestration engine.
        """
        raise NotImplementedError

    @abstractmethod
    def emit_signal(self, signal: Any) -> None:
        """Emit an organisational signal derived from operational events.

        Signals represent organisational interpretation of operational facts.
        """
        raise NotImplementedError

    @abstractmethod
    def detect_capacity_pressure(
        self, capability_id: str
    ) -> Any | None:
        """Detect whether a capability is under sustained demand pressure.

        Returns a CapacityPressureSignal if pressure is detected, otherwise None.
        This is a minimal proof-of-concept; real implementations may use
        sliding windows, percentile analysis, or predictive models.
        """
        raise NotImplementedError


class InMemoryOrganisationControlPlane(OrganisationControlPlane):
    """Reference implementation using in-memory storage.

    Stores organisational mechanisms (roles, authorities, work, assignments,
    delegations). Does NOT store Person/Agent records (ADR-037).
    Does NOT execute operational work or invoke runtimes.
    """

    def __init__(self, capability_registry: Any = None) -> None:
        self._roles: dict[str, Role] = {}
        self._authorities: dict[str, Authority] = {}
        self._work: dict[str, Work] = {}
        self._assignments: dict[str, Assignment] = {}
        self._delegations: dict[str, Delegation] = {}
        self._capabilities: dict[str, Any] = {}
        self._capability_registry = capability_registry
        self._event_handlers: list[Any] = []
        self._signal_handlers: list[Any] = []
        self._processed_event_ids: set[str] = set()

    def get_role(self, role_id: str) -> Role | None:
        return self._roles.get(role_id)

    def list_roles(self) -> list[Role]:
        return [r for r in self._roles.values() if r.status == RoleStatus.ACTIVE]

    def get_organisational_context(
        self, request_context: dict[str, Any]
    ) -> OrgContext:
        actor_id = request_context.get("actor_id")
        role_id = request_context.get("role_id")
        reporting: list[str] = []
        authority_scope: list[str] = []
        if role_id and role_id in self._roles:
            role = self._roles[role_id]
            reporting = [role.reports_to] if role.reports_to else []
            authority_scope = list(role.authority_ids)
        return OrgContext(
            current_actor_id=actor_id,
            current_role_id=role_id,
            reporting_relationships=reporting,
            authority_scope=authority_scope,
        )

    def assign_work(
        self, work: Work, assignee: Role | Person | Agent | Actor
    ) -> Assignment:
        if isinstance(assignee, Role):
            work.assignee_role_id = assignee.id
        elif isinstance(assignee, Person):
            work.assignee_person_id = assignee.id
        elif isinstance(assignee, Agent):
            work.assignee_agent_id = assignee.id
        elif isinstance(assignee, Actor):
            work.assignee_actor_id = assignee.id
            if assignee.actor_type == ActorType.AGENT:
                work.assignee_agent_id = assignee.reference_id
            elif assignee.actor_type == ActorType.PERSON:
                work.assignee_person_id = assignee.reference_id
        work.status = WorkStatus.ASSIGNED
        work.updated_at = datetime.now(UTC)
        self._work[work.id] = work
        assignment = Assignment(
            id=str(uuid4()),
            work_id=work.id,
            assignee_type=type(assignee).__name__.lower(),
            assignee_id=assignee.id,
            status=AssignmentStatus.ACCEPTED,
        )
        self._assignments[assignment.id] = assignment
        self._emit_work_event(
            WorkEventType.ASSIGNED,
            work,
            assignee_id=assignee.id,
        )
        return assignment

    def get_work(self, work_id: str) -> Work | None:
        return self._work.get(work_id)

    def list_work(self) -> list[Work]:
        return list(self._work.values())

    def delegate_authority(
        self, from_role: Role, to_role: Role, authority: Authority
    ) -> Delegation:
        delegation = Delegation(
            id=str(uuid4()),
            authority_id=authority.id,
            from_role_id=from_role.id,
            to_role_id=to_role.id,
            reason=f"Delegated from {from_role.name} to {to_role.name}",
        )
        self._delegations[delegation.id] = delegation
        return delegation

    def register_role(self, role: Role) -> None:
        self._roles[role.id] = role

    def register_authority(self, authority: Authority) -> None:
        self._authorities[authority.id] = authority

    def mark_work_ready(self, work_id: str) -> Work | None:
        """Mark organisational Work as ready for operational execution.

        Transitions Work.status to READY. This is an organisational
        handoff signal, NOT operational execution.
        """
        work = self.get_work(work_id)
        if work is not None:
            work.status = WorkStatus.READY
            work.updated_at = datetime.now(UTC)
            self._work[work.id] = work
            self._emit_work_event(WorkEventType.READY, work)
        return work

    def complete_work(self, work_id: str, outcome: dict[str, Any] | None = None) -> Work | None:
        """Mark organisational Work as completed with an execution outcome.

        Transitions Work.status to COMPLETED and records the outcome.
        This is an organisational state mutation based on operational facts.
        """
        work = self.get_work(work_id)
        if work is not None:
            work.status = WorkStatus.COMPLETED
            work.outcome = outcome
            work.updated_at = datetime.now(UTC)
            self._work[work.id] = work
            self._emit_work_event(WorkEventType.COMPLETED, work)
        return work

    def fail_work(self, work_id: str, outcome: dict[str, Any] | None = None) -> Work | None:
        """Mark organisational Work as failed with an execution outcome.

        Transitions Work.status to FAILED and records the outcome.
        This is an organisational state mutation based on operational facts.
        """
        work = self.get_work(work_id)
        if work is not None:
            work.status = WorkStatus.FAILED
            work.outcome = outcome
            work.updated_at = datetime.now(UTC)
            self._work[work.id] = work
            self._emit_work_event(WorkEventType.FAILED, work)
        return work

    def query_capability(self, capability_id: str) -> dict[str, Any] | None:
        """Query whether a capability is currently available.

        Returns minimal availability information.
        """
        has_in_roles = any(
            capability_id in role.required_capability_ids
            for role in self._roles.values()
        )
        has_registered = capability_id in self._capabilities
        if not has_in_roles and not has_registered:
            return None

        in_progress = [
            work for work in self._work.values()
            if capability_id in work.required_capability_ids
            and work.status in (WorkStatus.IN_PROGRESS, WorkStatus.READY, WorkStatus.ASSIGNED)
        ]

        if in_progress:
            return {
                "capability_id": capability_id,
                "available": False,
                "eta_seconds": None,
                "assignee": in_progress[0].assignee_agent_id or in_progress[0].assignee_role_id,
                "reason": "Capability is currently in use",
            }

        return {
            "capability_id": capability_id,
            "available": True,
            "eta_seconds": 5,
            "assignee": None,
            "reason": "Capability is available",
        }

    def register_capability(self, capability: Any, work_id: str | None = None) -> None:
        """Register a capability in the organisational capability store."""
        if self._capability_registry is not None:
            self._capability_registry.register(capability)
        else:
            self._capabilities[capability.id] = capability
        from contracts.organisational_events import CapabilityEvent
        event = CapabilityEvent(
            event_type="capability.registered",
            organisation_id="default",
            capability_id=capability.id,
            capability_name=getattr(capability, "name", capability.id),
            capability_kind=getattr(getattr(capability, "capability_kind", None), "value", "skill"),
            status=getattr(getattr(capability, "status", None), "value", "active"),
            work_id=work_id,
        )
        self._emit(event)

    def get_capability(self, capability_id: str) -> Any | None:
        """Retrieve a registered capability by ID."""
        if self._capability_registry is not None:
            return self._capability_registry.get(capability_id)
        return self._capabilities.get(capability_id)

    def on_event(self, handler: Any) -> None:
        """Register a handler for operational events."""
        self._event_handlers.append(handler)

    def on_signal(self, handler: Any) -> None:
        """Register a handler for organisational signals."""
        self._signal_handlers.append(handler)

    def _emit(self, event: Any) -> None:
        event_id = getattr(event, "event_id", None)
        if event_id and event_id in self._processed_event_ids:
            return
        if event_id:
            self._processed_event_ids.add(event_id)
        for handler in self._event_handlers:
            handler(event)

    def _emit_signal(self, signal: Any) -> None:
        for handler in self._signal_handlers:
            handler(signal)

    def emit_event(self, event: Any) -> None:
        self._emit(event)

    def emit_signal(self, signal: Any) -> None:
        self._emit_signal(signal)

    def detect_capacity_pressure(
        self, capability_id: str
    ) -> Any | None:
        from contracts.organisational_events import CapacityPressureSignal
        in_progress = [
            work for work in self._work.values()
            if capability_id in work.required_capability_ids
            and work.status in (WorkStatus.IN_PROGRESS, WorkStatus.READY, WorkStatus.ASSIGNED)
        ]
        pending = [
            work for work in self._work.values()
            if capability_id in work.required_capability_ids
            and work.status == WorkStatus.PENDING
        ]
        if not in_progress and not pending:
            return None
        total_load = len(in_progress) + len(pending)
        if total_load > 1:
            return CapacityPressureSignal(
                capability_id=capability_id,
                capability_name=capability_id,
                demand_rate_per_hour=float(total_load),
                capacity_rate_per_hour=float(len(in_progress)),
                queue_depth=len(pending),
                average_eta_seconds=300.0 * total_load,
                affected_work_ids=[w.id for w in in_progress + pending],
                reason=f"{total_load} work items compete for this capability",
            )
        return None

    def _emit_work_event(
        self,
        event_type: Any,
        work: Work,
        assignee_id: str | None = None,
    ) -> None:
        from contracts.organisational_events import WorkEvent, WorkEventType
        event = WorkEvent(
            event_type=event_type,
            organisation_id="default",
            work_id=work.id,
            title=work.title,
            work_type=work.work_type,
            assignee_role_id=work.assignee_role_id,
            assignee_agent_id=work.assignee_agent_id,
            assignee_actor_id=work.assignee_actor_id,
            required_capability_ids=list(work.required_capability_ids),
            status=work.status.value,
            priority=work.priority,
            outcome=work.outcome,
            context=work.context,
        )
        self._emit(event)

    def select_execution_path(
        self,
        intent: str,
        context: dict[str, Any],
        capability_query: Any = None,
        workflow_lookup: Any = None,
    ) -> Any:
        """Select the organisational execution path for a request.

        Decision hierarchy:
        1. Existing workflow → EXISTING_WORKFLOW
        2. Capability available → CAPABILITY_PATH
        3. Capability exists but unavailable → HUMAN_TEAM_INVESTIGATION
        4. Capability gap → NEW_CAPABILITY_REQUIRED

        When required_capability_ids is non-empty and a specific capability
        is identified as missing, that capability_id is preserved on the
        ExecutionPathResult so it can flow through to Work.develops_capability_id.
        """
        from execution_path import ExecutionPath, ExecutionPathResult

        required_ids: list[str] = list(context.get("required_capability_ids", []) or [])
        candidate_capabilities: list[dict[str, Any]] = context.get("candidate_capabilities", []) or []
        candidate_ids: list[str] = [c.get("id") for c in candidate_capabilities if c.get("id")]

        all_ids = list(required_ids)

        if workflow_lookup is not None:
            try:
                workflows = workflow_lookup(intent)
            except TypeError:
                workflows = workflow_lookup(intent, context=context)
            if workflows:
                return ExecutionPathResult(
                    path=ExecutionPath.EXISTING_WORKFLOW,
                    workflow=workflows[0],
                    capability_id=None,
                    reason="Matching workflow found",
                )

        unavailable_id: str | None = None

        for cap_id in all_ids:
            cap = self.get_capability(cap_id)
            avail = capability_query(cap_id) if capability_query is not None else None

            if cap is not None:
                if avail is None or getattr(avail, "available", True) is not False:
                    return ExecutionPathResult(
                        path=ExecutionPath.CAPABILITY_PATH,
                        capability_id=cap_id,
                        reason="Capability is available",
                    )
                unavailable_id = cap_id
            else:
                if avail is None:
                    return ExecutionPathResult(
                        path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
                        capability_id=cap_id,
                        reason="Required capability not found in registry and not known to operational layer",
                    )
                if getattr(avail, "available", True):
                    return ExecutionPathResult(
                        path=ExecutionPath.CAPABILITY_PATH,
                        capability_id=cap_id,
                        reason="Capability is available via operational layer",
                    )
                return ExecutionPathResult(
                    path=ExecutionPath.HUMAN_TEAM_INVESTIGATION,
                    capability_id=cap_id,
                    reason="Capability exists but is unavailable",
                )

        for cand_id in candidate_ids:
            cap = self.get_capability(cand_id)
            avail = capability_query(cand_id) if capability_query is not None else None

            if cap is not None:
                if avail is None or getattr(avail, "available", True) is not False:
                    return ExecutionPathResult(
                        path=ExecutionPath.CAPABILITY_PATH,
                        capability_id=cand_id,
                        reason="Capability is available",
                    )
                if unavailable_id is None:
                    unavailable_id = cand_id
            else:
                if avail is None:
                    return ExecutionPathResult(
                        path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
                        capability_id=cand_id,
                        reason="Candidate capability not found in registry",
                    )
                if getattr(avail, "available", True):
                    return ExecutionPathResult(
                        path=ExecutionPath.CAPABILITY_PATH,
                        capability_id=cand_id,
                        reason="Capability is available via operational layer",
                    )
                if unavailable_id is None:
                    unavailable_id = cand_id
                else:
                    return ExecutionPathResult(
                        path=ExecutionPath.HUMAN_TEAM_INVESTIGATION,
                        capability_id=cand_id,
                        reason="Multiple capabilities exist but are unavailable",
                    )

        if unavailable_id is not None:
            return ExecutionPathResult(
                path=ExecutionPath.HUMAN_TEAM_INVESTIGATION,
                capability_id=unavailable_id,
                reason="Capability exists but is unavailable",
            )

        if required_ids:
            return ExecutionPathResult(
                path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
                capability_id=required_ids[0],
                reason="Required capability not found in registry",
            )

        if candidate_ids:
            return ExecutionPathResult(
                path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
                capability_id=candidate_ids[0],
                reason="Candidate capability not found in registry",
            )

        return ExecutionPathResult(
            path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
            capability_id=None,
            reason="No matching workflow or capability found",
        )

    def execute_organisational_change(
        self,
        work: Work,
        actor: Any,
        capability_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute an organisational change (e.g. capability assignment).

        Checks whether the actor's role has the authority to make
        organisational changes before applying them.
        """
        from role import Authority, Delegation

        actor_id = getattr(actor, "id", None) or str(actor)
        actor_role_ids: list[str] = []
        if hasattr(actor, "fulfilled_role_ids"):
            actor_role_ids = list(actor.fulfilled_role_ids)
        elif hasattr(actor, "role_ids"):
            actor_role_ids = list(actor.role_ids)

        authority_checked = False
        authorised = False

        for role_id in actor_role_ids:
            role = self._roles.get(role_id)
            if role is None:
                continue
            authority_checked = True
            for auth_id in role.authority_ids:
                auth = self._authorities.get(auth_id)
                if auth is None:
                    continue
                for delegation in self._delegations.values():
                    if (
                        delegation.authority_id == auth_id
                        and delegation.from_role_id == auth.grantor_role_id
                        and delegation.to_role_id == role_id
                    ):
                        authorised = True
                        break
                if authorised:
                    break
            if authorised:
                break

        if not authorised:
            return {
                "status": "unauthorised",
                "authority_checked": authority_checked,
                "assignee_actor_id": actor_id,
            }

        self._work[work.id] = work
        work.assignee_actor_id = actor_id
        work.status = WorkStatus.ASSIGNED
        work.updated_at = datetime.now(UTC)

        return {
            "status": "executed",
            "authority_checked": authority_checked,
            "assignee_actor_id": actor_id,
            "capability_ids": capability_ids or [],
        }
