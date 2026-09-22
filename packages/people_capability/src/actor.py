"""
People/Capability domain — Actor model (Increment 24X).

Actor is a unified organisational identity for any entity that acts within
the organisation — whether human (Person) or software (Agent). It is a
lightweight reference that links to a Person or Agent without duplicating
their full records.

The organisation layer references actors by ID; the people_capability
plane owns the Actor records. Agent records and Person records remain
the authoritative lifecycle records.

Imports: pydantic, standard library only. No organisation, no Paperclip.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActorType(str, Enum):
    """Discriminator for the underlying entity type behind an Actor."""

    PERSON = "person"
    AGENT = "agent"


class Actor(BaseModel):
    """A unified organisational identity for any acting entity.

    An Actor references a Person or Agent by ``reference_id`` and carries
    organisational metadata (fulfilled roles, organisation context) needed
    by the Organisation/Control plane without owning the full Person/Agent
    record.

    The organisation layer uses Actor IDs for accountability, context,
    and assignment. Person/Agent full records remain owned by the
    people_capability plane.
    """

    id: str
    name: str
    actor_type: ActorType
    reference_id: str = Field(
        description="ID of the underlying Person or Agent record"
    )
    marker: str | None = Field(
        default=None,
        description="AgentMarker value ('ai' | 'human' | 'hybrid') if actor_type is AGENT, None otherwise",
    )
    fulfilled_role_ids: list[str] = Field(default_factory=list)
    organisation_id: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
