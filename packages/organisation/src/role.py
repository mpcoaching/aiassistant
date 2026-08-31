"""
Organisational role model (Increment 6, corrected Increment 9, Increment 14).

Defines the core domain records for the Organisation/Control plane:
Role, Authority, Delegation, Work, Assignment, OrgContext.

Person and Agent are imported from People/Capability plane (ADR-037).
Organisation/Control references Person/Agent by ID only and does not
store their lifecycle records.

Imports: pydantic only. No capability_registry, no concepts, no Paperclip.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from agent import Agent  # noqa: F401 — re-exported for organisation_control_plane
from person import Person  # noqa: F401 — re-exported for organisation_control_plane
from pydantic import BaseModel, Field


class RoleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    VACANT = "vacant"


class WorkStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class AssignmentStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"


class Role(BaseModel):
    """Abstract position with responsibilities, authority, constraints, information access, required capabilities.

    Owned by Organisation/Control plane. Not a person or agent.
    """

    id: str
    name: str
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    authority_ids: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    information_access: list[str] = Field(default_factory=list)
    reports_to: str | None = None
    status: RoleStatus = RoleStatus.ACTIVE
    required_capability_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Authority(BaseModel):
    """Permission grant within a scope."""

    id: str
    name: str
    description: str = ""
    scope: str
    grantor_role_id: str
    grantee_role_id: str
    constraints: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Delegation(BaseModel):
    """Record of an authority delegation from one role to another."""

    id: str
    authority_id: str
    from_role_id: str
    to_role_id: str
    delegated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""
    constraints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Work(BaseModel):
    """Instance of assigned effort.

    Accountable to a Role. Not a capability, not an execution unit.
    """

    id: str
    title: str
    description: str = ""
    work_type: str = "bau"
    status: WorkStatus = WorkStatus.PENDING
    priority: str = "normal"
    organisation_id: str = "default"
    accountable_role_id: str
    coordinating_role_id: str | None = None
    requested_by_role_id: str | None = None
    assignee_role_id: str | None = None
    assignee_person_id: str | None = None
    assignee_agent_id: str | None = None
    required_capability_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    parent_work_id: str | None = None
    deliverables: list[str] = Field(default_factory=list)
    outcome: dict[str, Any] | None = None
    constraints: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Assignment(BaseModel):
    """Link between Work and assignee."""

    id: str
    work_id: str
    organisation_id: str = "default"
    assignee_type: str
    assignee_id: str
    status: AssignmentStatus = AssignmentStatus.PROPOSED
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accepted_at: datetime | None = None
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrgContext(BaseModel):
    """Current organisational context for a request."""

    current_actor_id: str | None = None
    current_role_id: str | None = None
    reporting_relationships: list[str] = Field(default_factory=list)
    authority_scope: list[str] = Field(default_factory=list)
    organisational_relationships: dict[str, Any] = Field(default_factory=dict)
    capability_gaps: list[str] = Field(default_factory=list)
