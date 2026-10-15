"""
People/Capability domain — Agent model (Increment 14).

Agent represents a software entity with identity, marker, and fulfilled roles.
Owned by People/Capability plane. Organisation/Control references Agent by ID only.

Imports: pydantic, standard library only. No organisation, operations, EIMS, or capability_registry imports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentMarker(str, Enum):
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPROVISIONED = "deprovisioned"


class Agent(BaseModel):
    """Software entity marker/record."""

    id: str
    name: str
    marker: AgentMarker = AgentMarker.AI
    status: AgentStatus = AgentStatus.ACTIVE
    fulfilled_role_ids: list[str] = Field(default_factory=list)
    runtime_identity: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
