"""
People/Capability domain — Person model (Increment 14).

Person represents a human individual with identity and employment context.
Owned by People/Capability plane. Organisation/Control references Person by ID only.

Imports: pydantic, standard library only. No organisation, operations, EIMS, or capability_registry imports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PersonStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class Person(BaseModel):
    """Human individual with identity and employment context."""

    id: str
    name: str
    email: str | None = None
    status: PersonStatus = PersonStatus.ACTIVE
    role_ids: list[str] = Field(default_factory=list)
    employment_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
