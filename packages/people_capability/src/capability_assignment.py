"""
People/Capability domain — CapabilityAssignment model (Increment 14).

CapabilityAssignment records that a specific Person or Agent is assigned/authorised
to use a specific Capability.

Imports: pydantic, standard library only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AssignmentType(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    BACKUP = "backup"


class AssignmentStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CapabilityAssignment(BaseModel):
    """Record linking a Person/Agent to a Capability with status, type, and authorisation."""

    id: str
    capability_id: str
    assignee_type: str  # "person" | "agent"
    assignee_id: str
    assignment_type: AssignmentType = AssignmentType.PRIMARY
    status: AssignmentStatus = AssignmentStatus.ACTIVE
    authorised_by: str | None = None
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
