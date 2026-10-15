"""
People/Capability domain — Skill model (Increment 28).

A Skill is a learned, reusable *method* for exercising a Capability.

It is deliberately lightweight: no execution binding, no prompt template,
no LangGraph node reference, no Paperclip skill reference. Those are
implementation concerns that live in execution layers (workflow_runner,
capability_registry adapters, Paperclip adapters).

Imports: pydantic, standard library only. No organisation, no Paperclip, no LangGraph.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Skill(BaseModel):
    """A learned, reusable method for exercising a Capability.

    A Skill represents an organisational technique or approach — not a prompt,
    a Python function, a LangGraph node, a Paperclip skill, or a workflow.
    Those are concrete *implementations* of a skill.

    The organisation references skills by ID; implementation adapters resolve
    the actual executable from their own registries.
    """

    id: str
    capability_id: str = Field(
        description="The Capability this Skill supports"
    )
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    method: str | None = Field(
        default=None,
        description="Human-readable description of the learned method/technique",
    )
    tool_ids: list[str] = Field(
        default_factory=list,
        description="Optional list of Tool IDs the Skill requires or can use (references by ID only)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
