"""Tests for organisational event and signal contracts (Increment 21W)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from contracts.organisational_events import (
    AgentEvent,
    AgentEventType,
    CapabilityBottleneckSignal,
    CapabilityEvent,
    CapabilityEventType,
    CapacityPressureSignal,
    OrganisationalSignal,
    WorkEvent,
    WorkEventType,
    WorkSLARiskSignal,
)
from contracts.organisational_context import OrganisationalContext
from role import Work, WorkStatus


# ---- OrganisationalContext --------------------------------------------------

class TestOrganisationalContext:
    def test_default_organisation_id(self) -> None:
        ctx = OrganisationalContext()
        assert ctx.organisation_id == "default"

    def test_custom_organisation_id(self) -> None:
        ctx = OrganisationalContext(organisation_id="org-123")
        assert ctx.organisation_id == "org-123"

    def test_carry_actor_and_role(self) -> None:
        ctx = OrganisationalContext(
            organisation_id="org-456",
            current_actor_id="agent-1",
            current_role_id="role-1",
        )
        assert ctx.organisation_id == "org-456"
        assert ctx.current_actor_id == "agent-1"
        assert ctx.current_role_id == "role-1"


# ---- WorkEvent --------------------------------------------------------------

class TestWorkEvent:
    def test_created_event_defaults(self) -> None:
        event = WorkEvent(
            event_type=WorkEventType.CREATED,
            work_id="work-1",
            title="Test Work",
            status="pending",
        )
        assert event.event_id is not None
        assert event.event_type == WorkEventType.CREATED
        assert event.organisation_id == "default"
        assert event.work_id == "work-1"
        assert event.status == "pending"
        assert event.occurred_at is not None

    def test_assigned_event_with_assignee(self) -> None:
        event = WorkEvent(
            event_type=WorkEventType.ASSIGNED,
            work_id="work-2",
            title="Assigned Work",
            assignee_agent_id="agent-1",
            status="assigned",
        )
        assert event.assignee_agent_id == "agent-1"
        assert event.status == "assigned"

    def test_completed_event_with_outcome(self) -> None:
        outcome = {"status": "completed", "result": "ok"}
        event = WorkEvent(
            event_type=WorkEventType.COMPLETED,
            work_id="work-3",
            title="Done Work",
            status="completed",
            outcome=outcome,
        )
        assert event.outcome == outcome

    def test_failed_event(self) -> None:
        event = WorkEvent(
            event_type=WorkEventType.FAILED,
            work_id="work-4",
            title="Failed Work",
            status="failed",
        )
        assert event.event_type == WorkEventType.FAILED


# ---- CapabilityEvent --------------------------------------------------------

class TestCapabilityEvent:
    def test_registered_event(self) -> None:
        event = CapabilityEvent(
            event_type=CapabilityEventType.REGISTERED,
            capability_id="cap-1",
            capability_name="Research",
        )
        assert event.event_type == CapabilityEventType.REGISTERED
        assert event.capability_id == "cap-1"

    def test_development_completed_event(self) -> None:
        event = CapabilityEvent(
            event_type=CapabilityEventType.DEVELOPMENT_COMPLETED,
            capability_id="cap-2",
            capability_name="New Cap",
            work_id="work-dev-1",
        )
        assert event.work_id == "work-dev-1"


# ---- AgentEvent -------------------------------------------------------------

class TestAgentEvent:
    def test_heartbeat_event(self) -> None:
        event = AgentEvent(
            event_type=AgentEventType.HEARTBEAT,
            agent_id="agent-1",
            agent_name="Worker One",
            current_work_count=2,
        )
        assert event.current_work_count == 2

    def test_overloaded_event(self) -> None:
        event = AgentEvent(
            event_type=AgentEventType.OVERLOADED,
            agent_id="agent-2",
            agent_name="Worker Two",
            current_work_count=10,
        )
        assert event.event_type == AgentEventType.OVERLOADED


# ---- CapacityPressureSignal -------------------------------------------------

class TestCapacityPressureSignal:
    def test_pressure_detected(self) -> None:
        signal = CapacityPressureSignal(
            capability_id="research",
            capability_name="Research",
            demand_rate_per_hour=15.0,
            capacity_rate_per_hour=10.0,
            queue_depth=5,
            average_eta_seconds=600.0,
            affected_work_ids=["w1", "w2", "w3"],
        )
        assert signal.signal_type == "capacity.pressure.detected"
        assert signal.demand_rate_per_hour == 15.0
        assert signal.queue_depth == 5

    def test_no_pressure_when_below_capacity(self) -> None:
        signal = CapacityPressureSignal(
            capability_id="analysis",
            capability_name="Analysis",
            demand_rate_per_hour=5.0,
            capacity_rate_per_hour=10.0,
            queue_depth=0,
        )
        assert signal.demand_rate_per_hour < signal.capacity_rate_per_hour


# ---- CapabilityBottleneckSignal ---------------------------------------------

class TestCapabilityBottleneckSignal:
    def test_bottleneck_detected(self) -> None:
        signal = CapabilityBottleneckSignal(
            capability_id="review",
            capability_name="Review",
            blocked_work_count=3,
            blocked_work_ids=["w1", "w2", "w3"],
            waiting_agents=[],
            reason="No agent available with review capability",
        )
        assert signal.signal_type == "capability.bottleneck.detected"
        assert signal.blocked_work_count == 3


# ---- WorkSLARiskSignal ------------------------------------------------------

class TestWorkSLARiskSignal:
    def test_sla_risk_detected(self) -> None:
        signal = WorkSLARiskSignal(
            work_id="work-1",
            title="Urgent Analysis",
            priority="high",
            eta_seconds=7200.0,
            sla_threshold_seconds=3600.0,
            reason="ETA exceeds SLA",
        )
        assert signal.signal_type == "work.sla_risk.detected"
        assert signal.eta_seconds > signal.sla_threshold_seconds


# ---- Event Emission Through OCP ---------------------------------------------

class TestOrganisationEventEmission:
    def test_ocp_emits_work_assigned_event(self) -> None:
        from organisation.src.organisation_control_plane import (
            InMemoryOrganisationControlPlane,
        )
        from role import Role, Work, WorkStatus

        events: list[Any] = []
        org = InMemoryOrganisationControlPlane()
        org.on_event(events.append)

        work = Work(
            id="work-emit-1",
            title="Emit Test",
            accountable_role_id="role-1",
        )
        role = Role(id="role-1", name="Tester", authority_ids=[])
        org.register_role(role)
        org.assign_work(work, role)

        assert len(events) == 1
        assert events[0].event_type == WorkEventType.ASSIGNED
        assert events[0].work_id == "work-emit-1"

    def test_ocp_emits_capability_registered_event(self) -> None:
        from organisation.src.organisation_control_plane import (
            InMemoryOrganisationControlPlane,
        )
        from people_capability.src.capability import Capability, CapabilityKind

        events: list[Any] = []
        org = InMemoryOrganisationControlPlane()
        org.on_event(events.append)

        cap = Capability(
            id="cap-emit-1",
            name="Emit Cap",
            capability_kind=CapabilityKind.SKILL,
        )
        org.register_capability(cap)

        assert len(events) == 1
        assert events[0].event_type == CapabilityEventType.REGISTERED
        assert events[0].capability_id == "cap-emit-1"

    def test_ocp_detects_capacity_pressure(self) -> None:
        from organisation.src.organisation_control_plane import (
            InMemoryOrganisationControlPlane,
        )
        from role import Work

        signals: list[Any] = []
        org = InMemoryOrganisationControlPlane()
        org.on_signal(signals.append)

        w1 = Work(id="w1", title="Pressure 1", accountable_role_id="r1", required_capability_ids=["research"])
        w2 = Work(id="w2", title="Pressure 2", accountable_role_id="r1", required_capability_ids=["research"])
        w1.status = WorkStatus.ASSIGNED
        w2.status = WorkStatus.PENDING
        org._work[w1.id] = w1
        org._work[w2.id] = w2

        signal = org.detect_capacity_pressure("research")
        assert signal is not None
        assert signal.signal_type == "capacity.pressure.detected"
        assert signal.queue_depth == 1
        assert len(signals) == 0  # detect only, does not emit

    def test_ocp_returns_none_when_no_pressure(self) -> None:
        from organisation.src.organisation_control_plane import (
            InMemoryOrganisationControlPlane,
        )
        from role import Work

        org = InMemoryOrganisationControlPlane()
        signal = org.detect_capacity_pressure("nonexistent")
        assert signal is None
