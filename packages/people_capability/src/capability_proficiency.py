"""
People/Capability domain — CapabilityProficiency model (Increment 14).

CapabilityProficiency records how well a Person or Agent can exercise a Capability.

Imports: pydantic, standard library only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProficiencyLevel(str, Enum):
    NOVICE = "novice"
    COMPETENT = "competent"
    PROFICIENT = "proficient"
    EXPERT = "expert"
    MASTER = "master"


class CapabilityProficiency(BaseModel):
    """Record of how well a Person/Agent can exercise a Capability."""

    id: str
    capability_id: str
    person_id: str | None = None
    agent_id: str | None = None
    proficiency_level: ProficiencyLevel = ProficiencyLevel.COMPETENT
    validated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime | None = None
    evidence: list[str] = Field(default_factory=list)
    assessed_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
