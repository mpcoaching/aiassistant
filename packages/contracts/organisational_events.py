"""Organisational event and signal contracts (Increment 21W).

Defines the distinction between:

Operational events
    What happened inside the organisation.
    Reported by operational systems (Paperclip, workers, runtime).

Organisational signals
    What the organisation interprets from operational events.
    Derived by the Organisation layer.

Design principles:
- Events are immutable facts.
- Signals are organisational interpretations.
- The event boundary is a communication mechanism, not an orchestration engine.
- Tenant/organisation context is preserved on every event.
- Paperclip remains replaceable behind the Organisation abstraction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


# ---- Tenant / Organisation Context ------------------------------------------

class OrganisationContext(BaseModel):
    """Explicit organisational/tenant identity preserved across boundaries."""

    organisation_id: str = "default"
    actor_id: str | None = None
    role_id: str | None = None
    reporting_relationships: list[str] = []
    authority_scope: list[str] = []
    organisational_relationships: dict[str, Any] = {}
    capability_gaps: list[str] = []


# ---- Operational Events -----------------------------------------------------

class WorkEventType(str, Enum):
    CREATED = "work.created"
    ASSIGNED = "work.assigned"
    READY = "work.ready"
    QUEUED = "work.queued"
    STARTED = "work.started"
    COMPLETED = "work.completed"
    FAILED = "work.failed"
    ESCALATED = "work.escalated"
    CANCELLED = "work.cancelled"


class CapabilityEventType(str, Enum):
    DEVELOPMENT_STARTED = "capability.development.started"
    DEVELOPMENT_COMPLETED = "capability.development.completed"
    REGISTERED = "capability.registered"
    BOTTLENECK_DETECTED = "capability.bottleneck.detected"


class AgentEventType(str, Enum):
    HEARTBEAT = "agent.heartbeat"
    AVAILABLE = "agent.available"
    BUSY = "agent.busy"
    OVERLOADED = "agent.overloaded"


class WorkEvent(BaseModel):
    """Operational event describing a work lifecycle transition."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: WorkEventType
    organisation_id: str = "default"
    work_id: str
    title: str
    work_type: str = "bau"
    assignee_role_id: str | None = None
    assignee_agent_id: str | None = None
    required_capability_ids: list[str] = []
    status: str
    priority: str = "normal"
    outcome: dict[str, Any] | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CapabilityEvent(BaseModel):
    """Operational event describing a capability lifecycle transition."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: CapabilityEventType
    organisation_id: str = "default"
    capability_id: str
    capability_name: str
    capability_kind: str = "skill"
    status: str = "active"
    assignee_id: str | None = None
    work_id: str | None = None
    reason: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentEvent(BaseModel):
    """Operational event describing an agent state transition."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: AgentEventType
    organisation_id: str = "default"
    agent_id: str
    agent_name: str = ""
    status: str = "active"
    current_work_count: int = 0
    capability_ids: list[str] = []
    context: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


OrganisationalEvent = WorkEvent | CapabilityEvent | AgentEvent


# ---- Organisational Signals -------------------------------------------------

class CapacityPressureSignal(BaseModel):
    """Organisational signal indicating sustained demand exceeds capacity."""

    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    signal_type: str = "capacity.pressure.detected"
    organisation_id: str = "default"
    capability_id: str
    capability_name: str
    demand_rate_per_hour: float = 0.0
    capacity_rate_per_hour: float = 0.0
    queue_depth: int = 0
    average_eta_seconds: float = 0.0
    affected_work_ids: list[str] = []
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""


class CapabilityBottleneckSignal(BaseModel):
    """Organisational signal indicating a capability is blocking workflow."""

    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    signal_type: str = "capability.bottleneck.detected"
    organisation_id: str = "default"
    capability_id: str
    capability_name: str
    blocked_work_count: int = 0
    blocked_work_ids: list[str] = []
    waiting_agents: list[str] = []
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""


class WorkSLARiskSignal(BaseModel):
    """Organisational signal indicating work may miss its SLA."""

    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    signal_type: str = "work.sla_risk.detected"
    organisation_id: str = "default"
    work_id: str
    title: str
    priority: str = "normal"
    eta_seconds: float = 0.0
    sla_threshold_seconds: float = 0.0
    assignee_id: str | None = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str = ""


OrganisationalSignal = CapacityPressureSignal | CapabilityBottleneckSignal | WorkSLARiskSignal


# ---- Event Boundary Ports ---------------------------------------------------

class OrganisationalEventEmitterPort(Protocol):
    """Boundary for emitting operational events from the Organisation layer.

    Implementations may:
    - Buffer events for later processing
    - Publish to a message bus
    - Stream to an external system
    - Log to a file
    - Do nothing (no-op)

    The Organisation layer does not depend on any specific transport.
    """

    def emit(self, event: OrganisationalEvent) -> None: ...


class OrganisationalSignalEmitterPort(Protocol):
    """Boundary for emitting organisational signals.

    Signals are derived by the Organisation layer from operational events.
    They represent organisational interpretation, not raw facts.
    """

    def emit_signal(self, signal: OrganisationalSignal) -> None: ...
