"""
Tests for ExecutionAuthorisationAdapter (Increment 17).
"""

from __future__ import annotations

from capability_assignment import AssignmentStatus, CapabilityAssignment
from capability_proficiency import CapabilityProficiency, ProficiencyLevel
from capability_registry.src.adapters.execution_authorisation_adapter import InMemoryExecutionAuthorisationPort


def _assignment(
    capability_id: str,
    assignee_id: str,
    assignee_type: str = "agent",
    status: AssignmentStatus = AssignmentStatus.ACTIVE,
) -> CapabilityAssignment:
    return CapabilityAssignment(
        id=f"asgn-{capability_id}-{assignee_id}",
        capability_id=capability_id,
        assignee_type=assignee_type,
        assignee_id=assignee_id,
        status=status,
    )


def _proficiency(
    capability_id: str,
    assignee_id: str,
    assignee_type: str = "agent",
    level: ProficiencyLevel = ProficiencyLevel.COMPETENT,
) -> CapabilityProficiency:
    if assignee_type == "person":
        return CapabilityProficiency(
            id=f"prof-{capability_id}-{assignee_id}",
            capability_id=capability_id,
            person_id=assignee_id,
            proficiency_level=level,
        )
    return CapabilityProficiency(
        id=f"prof-{capability_id}-{assignee_id}",
        capability_id=capability_id,
        agent_id=assignee_id,
        proficiency_level=level,
    )


def test_authorised_when_active_assignment_exists() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "agent-1")],
    )
    result = port.is_authorised("agent-1", "agent", "cap-1")
    assert result.authorised is True
    assert result.assignment is not None
    assert result.reason == "authorised"


def test_not_authorised_when_no_assignment() -> None:
    port = InMemoryExecutionAuthorisationPort()
    result = port.is_authorised("agent-1", "agent", "cap-1")
    assert result.authorised is False
    assert result.reason == "no_active_assignment"
    assert result.assignment is None


def test_not_authorised_when_assignment_revoked() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "agent-1", status=AssignmentStatus.REVOKED)],
    )
    result = port.is_authorised("agent-1", "agent", "cap-1")
    assert result.authorised is False
    assert result.reason == "assignment_status_revoked"


def test_not_authorised_when_assignment_expired() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "agent-1", status=AssignmentStatus.EXPIRED)],
    )
    result = port.is_authorised("agent-1", "agent", "cap-1")
    assert result.authorised is False
    assert result.reason == "assignment_status_expired"


def test_proficiency_is_included_when_authorised() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "agent-1")],
        proficiencies=[_proficiency("cap-1", "agent-1", level=ProficiencyLevel.EXPERT)],
    )
    result = port.is_authorised("agent-1", "agent", "cap-1")
    assert result.authorised is True
    assert result.proficiency is not None
    assert result.proficiency.proficiency_level == ProficiencyLevel.EXPERT


def test_proficiency_is_none_when_missing() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "agent-1")],
    )
    result = port.is_authorised("agent-1", "agent", "cap-1")
    assert result.authorised is True
    assert result.proficiency is None


def test_person_authorisation() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "person-1", assignee_type="person")],
        proficiencies=[_proficiency("cap-1", "person-1", assignee_type="person")],
    )
    result = port.is_authorised("person-1", "person", "cap-1")
    assert result.authorised is True
    assert result.proficiency is not None


def test_wrong_actor_type_not_authorised() -> None:
    port = InMemoryExecutionAuthorisationPort(
        assignments=[_assignment("cap-1", "agent-1", assignee_type="agent")],
    )
    result = port.is_authorised("agent-1", "person", "cap-1")
    assert result.authorised is False
    assert result.reason == "no_active_assignment"
