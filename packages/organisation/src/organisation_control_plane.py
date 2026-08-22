"""
OrganisationControlPlane abstraction and in-memory implementation (Increment 6, corrected Increment 9, extended Increment 10).

Defines the narrow interface for the Organisation/Control plane plus a
reference in-memory implementation for testing and local development.

OrganisationControlPlane is mechanism-only:
- provides role lookup, work assignment, authority delegation, organisational context
- provides operational handoff via execute_work()
- does NOT store Person/Agent records (owned by People/Capability, ADR-037)
- does NOT coordinate work (belongs to roles)
- does NOT become the CEO/COO/PM
- does NOT execute capabilities

Imports: role module only. No capability_registry, no concepts, no Paperclip.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pathway_runtime import PathwayCallRequest, PathwayRuntime

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


class OrganisationControlPlane(ABC):
    """Narrow abstraction for organisational mechanisms and context.

    Explicitly excluded:
    - find_capability()
    - match_capability()
    - execute_capability()
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
    def delegate_authority(
        self, from_role: Role, to_role: Role, authority: Authority
    ) -> Delegation:
        """Delegate authority from one role to another."""
        raise NotImplementedError

    @abstractmethod
    def execute_work(self, work_id: str, execution_context: dict[str, Any]) -> dict[str, Any]:
        """Hand off organisational Work to operational execution.

        Retrieves the Work, creates an operational execution request,
        delegates to the runtime substrate, and returns the execution result.

        This is the organisational -> operational handoff boundary.
        It does NOT store Person/Agent records or perform capability matching.
        """
        raise NotImplementedError


class InMemoryOrganisationControlPlane(OrganisationControlPlane):
    """Reference implementation using in-memory storage.

    Stores organisational mechanisms (roles, authorities, work, assignments,
    delegations). Does NOT store Person/Agent records (ADR-037).

    Optional PathwayRuntime can be provided for execute_work() handoff.
    """

    def __init__(self, runtime: PathwayRuntime | None = None) -> None:
        self._roles: dict[str, Role] = {}
        self._authorities: dict[str, Authority] = {}
        self._work: dict[str, Work] = {}
        self._assignments: dict[str, Assignment] = {}
        self._delegations: dict[str, Delegation] = {}
        self._runtime = runtime

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
        self, work: Work, assignee: Role | Person | Agent
    ) -> Assignment:
        if isinstance(assignee, Role):
            work.assignee_role_id = assignee.id
        elif isinstance(assignee, Person):
            work.assignee_person_id = assignee.id
        elif isinstance(assignee, Agent):
            work.assignee_agent_id = assignee.id
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
        return assignment

    def get_work(self, work_id: str) -> Work | None:
        return self._work.get(work_id)

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

    def execute_work(self, work_id: str, execution_context: dict[str, Any]) -> dict[str, Any]:
        """Hand off organisational Work to operational execution.

        If a PathwayRuntime is configured, creates a PathwayCallRequest and invokes it.
        Otherwise returns a simulated execution result for testing.

        The execution result is evidence. It is NOT automatically an accepted
        organisational outcome. The caller must assess the result against
        acceptance_criteria and update Work.outcome and Work.status accordingly.
        """
        work = self.get_work(work_id)
        if work is None:
            return {"status": "failed", "error": f"Work not found: {work_id}"}

        if self._runtime is not None:
            request = PathwayCallRequest(
                session_id=f"ops-{work_id}",
                pattern_step={
                    "pattern_id": work.title,
                    "ordered_steps": [
                        {
                            "step_id": work.title,
                            "role": work.assignee_role_id or "operator",
                            "tools": [],
                            "gate_condition": None,
                        }
                    ],
                },
                context=execution_context,
                participants=[{"role": work.assignee_role_id or "operator"}],
                prompt=work.description or work.title,
            )
            response = self._runtime.invoke(request)
            return {
                "status": response.status.value,
                "outputs": response.outputs or {},
                "artifacts": response.artifacts or [],
                "telemetry": response.telemetry or {},
            }

        return {
            "status": "completed",
            "outputs": {"simulated": True, "work_id": work_id},
            "artifacts": [],
            "telemetry": {"runtime": "none", "reason": "no_runtime_configured"},
        }
