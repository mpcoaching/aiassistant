"""
People/Capability domain — ExecutionAuthorisationPort interface (Increment 14).

Narrow authorisation query for Operations. Does not confer execution ownership.
Enforcement in PatternRuntime is deferred to a later increment.

Imports: typing, standard library only.
"""

from __future__ import annotations

from typing import Protocol

from capability_assignment import CapabilityAssignment
from capability_proficiency import CapabilityProficiency


class AuthorisationResult:
    """Result of an execution authorisation check."""

    def __init__(
        self,
        authorised: bool,
        assignment: CapabilityAssignment | None = None,
        proficiency: CapabilityProficiency | None = None,
        reason: str | None = None,
    ) -> None:
        self.authorised = authorised
        self.assignment = assignment
        self.proficiency = proficiency
        self.reason = reason


class ExecutionAuthorisationPort(Protocol):
    """Narrow port for Operations to query execution authorisation."""

    def is_authorised(
        self,
        actor_id: str,
        actor_type: str,  # "person" | "agent"
        capability_id: str,
    ) -> AuthorisationResult:
        """Check whether an actor is authorised to execute a capability."""
        ...
