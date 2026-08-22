"""
OrganisationControlPlane abstraction and in-memory implementation (Increment 6).

Defines the narrow interface for the Organisation/Control plane plus a
reference in-memory implementation for testing and local development.

Imports: role module only. No capability_registry, no concepts, no Paperclip.
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


class OrganisationControlPlane(ABC):
    """Narrow abstraction for organisational coordination.

    Explicitly excluded:
    - find_capability()
    - match_capability()
    - execute_capability()
    - execute_work()
    - run_agent()
    - invoke_tool()
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
        """Assign work to a role, person, or agent."""
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


class InMemoryOrganisationControlPlane(OrganisationControlPlane):
    """Reference implementation using in-memory storage."""

    def __init__(self) -> None:
        self._roles: dict[str, Role] = {}
        self._persons: dict[str, Person] = {}
        self._agents: dict[str, Agent] = {}
        self._authorities: dict[str, Authority] = {}
        self._work: dict[str, Work] = {}
        self._assignments: dict[str, Assignment] = {}
        self._delegations: dict[str, Delegation] = {}

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

    def register_person(self, person: Person) -> None:
        self._persons[person.id] = person

    def register_agent(self, agent: Agent) -> None:
        self._agents[agent.id] = agent

    def register_authority(self, authority: Authority) -> None:
        self._authorities[authority.id] = authority
