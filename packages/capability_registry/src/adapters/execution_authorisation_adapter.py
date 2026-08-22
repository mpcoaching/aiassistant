"""
People/Capability plane — Execution authorisation implementation (Increment 17).

Implements ExecutionAuthorisationPort using CapabilityAssignment and
CapabilityProficiency records.

Authorisation rules:
- Actor must have an ACTIVE CapabilityAssignment for the capability
- Actor must not have an EXPIRED or REVOKED assignment
- Proficiency is recorded but does not block authorisation

This is the single source of truth for authorisation domain rules.
Operations enforces the result; it does not replicate the rules.
"""

from __future__ import annotations

from capability_assignment import CapabilityAssignment, AssignmentStatus
from capability_proficiency import CapabilityProficiency
from execution_authorisation import AuthorisationResult


class InMemoryExecutionAuthorisationPort:
    """In-memory authorisation implementation for tests and simple deployments."""

    def __init__(
        self,
        assignments: list[CapabilityAssignment] | None = None,
        proficiencies: list[CapabilityProficiency] | None = None,
    ) -> None:
        self._assignments = list(assignments or [])
        self._proficiencies = list(proficiencies or [])

    def is_authorised(
        self,
        actor_id: str,
        actor_type: str,
        capability_id: str,
    ) -> AuthorisationResult:
        assignment = self._find_assignment(actor_id, actor_type, capability_id)
        if assignment is None:
            return AuthorisationResult(
                authorised=False,
                reason="no_active_assignment",
            )
        if assignment.status in (AssignmentStatus.EXPIRED, AssignmentStatus.REVOKED):
            return AuthorisationResult(
                authorised=False,
                assignment=assignment,
                reason=f"assignment_status_{assignment.status.value}",
            )
        proficiency = self._find_proficiency(actor_id, actor_type, capability_id)
        return AuthorisationResult(
            authorised=True,
            assignment=assignment,
            proficiency=proficiency,
            reason="authorised",
        )

    def _find_assignment(
        self,
        actor_id: str,
        actor_type: str,
        capability_id: str,
    ) -> CapabilityAssignment | None:
        for assignment in self._assignments:
            if (
                assignment.capability_id == capability_id
                and assignment.assignee_type == actor_type
                and assignment.assignee_id == actor_id
            ):
                return assignment
        return None

    def _find_proficiency(
        self,
        actor_id: str,
        actor_type: str,
        capability_id: str,
    ) -> CapabilityProficiency | None:
        for proficiency in self._proficiencies:
            if (
                proficiency.capability_id == capability_id
                and (
                    (actor_type == "person" and proficiency.person_id == actor_id)
                    or (actor_type == "agent" and proficiency.agent_id == actor_id)
                )
            ):
                return proficiency
        return None
