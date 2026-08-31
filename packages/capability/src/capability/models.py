"""
People/Capability domain — Capability model (Increment 14).

Capability is a reusable ability (tool, skill, service) identified by its interface
and governance properties. Execution metadata belongs to Operations (CapabilityDeployment).

Imports: pydantic, standard library only. No organisation, operations, EIMS, or capability_registry imports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CapabilityKind(str, Enum):
    TOOL = "tool"
    SKILL = "skill"


class CapabilityStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class Parameter(BaseModel):
    name: str
    type: str
    required: bool = True
    description: str = ""


class CapabilityInterface(BaseModel):
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[Parameter] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Capability(BaseModel):
    """Reusable ability owned by People/Capability plane.

    Domain model only — no execution metadata.
    Execution bindings live in Operations (CapabilityDeployment).
    """

    id: str
    name: str
    description: str = ""
    capability_kind: CapabilityKind = CapabilityKind.TOOL
    status: CapabilityStatus = CapabilityStatus.DRAFT
    interface: CapabilityInterface = Field(default_factory=CapabilityInterface)
    owns_durable_state: bool = False
    standing_contract: bool = False
    tags: list[str] = Field(default_factory=list)
    owner: str = "core"
    created_by: str = "system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
