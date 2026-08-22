"""
Operations plane — CapabilityDeployment and execution types (Increment 14).

CapabilityDeployment is the execution binding for a capability in a specific environment.
It is keyed by (capability_id, environment).

These types belong to Operations, not to the People/Capability domain model.
People/Capability defines the shape; Operations owns the records and runtime dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from capability import Parameter
from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    AI_MEDIATED = "ai_mediated"
    COMPILED = "compiled"


class Transport(str, Enum):
    TIER2_INPROCESS = "tier2_inprocess"
    TIER3_BUS = "tier3_bus"


class AiSpec(BaseModel):
    """Present when execution_mode = ai_mediated."""

    purpose: str = ""
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[Parameter] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    prompt_template_ref: str | None = None


class CompiledRef(BaseModel):
    """Present when execution_mode = compiled."""

    module_path: str
    entrypoint: str = "run"
    tests_passed: bool = False


class CapabilityDeployment(BaseModel):
    """Execution binding for a capability in a specific environment."""

    capability_id: str
    environment: str
    execution_mode: ExecutionMode
    transport: Transport
    ai_spec: AiSpec | None = None
    compiled_ref: CompiledRef | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
