"""
People/Capability domain — CapabilityRepository interface (Increment 14).

Protocol defining persistence operations for Capability domain records.
CapabilityRegistry depends on this interface, not on ConceptStore directly.

Imports: typing, standard library only. No EIMS imports.
"""

from __future__ import annotations

from typing import Any, Protocol

from capability import Capability


class CapabilityRepository(Protocol):
    """Protocol for capability definition persistence."""

    def upsert_capability(self, capability: Capability) -> None:
        """Create or update a capability definition."""
        ...

    def get_capability(self, capability_id: str) -> Capability | None:
        """Retrieve a capability definition by ID."""
        ...

    def list_capabilities(self, capability_kind: str | None = None) -> list[Capability]:
        """List capability definitions, optionally filtered by kind."""
        ...

    def delete_capability(self, capability_id: str) -> bool:
        """Delete a capability definition. Returns True if deleted."""
        ...


class CapabilityQuery(Protocol):
    """Protocol for capability availability queries."""

    def get_capability_holders(self, capability_id: str) -> list[dict[str, Any]]:
        """Who is authorised to use this capability?"""
        ...

    def get_person_capabilities(self, person_id: str) -> list[dict[str, Any]]:
        """What capabilities does this person possess?"""
        ...

    def get_agent_capabilities(self, agent_id: str) -> list[dict[str, Any]]:
        """What capabilities does this agent possess?"""
        ...

    def find_capability_gap(
        self,
        required_capability_ids: list[str],
        candidate_ids: list[str],
    ) -> dict[str, Any]:
        """Given required capabilities and candidates, what gaps exist?"""
        ...
