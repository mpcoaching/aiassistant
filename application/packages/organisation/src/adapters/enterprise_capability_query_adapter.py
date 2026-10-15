"""
Adapter: contracts.EnterpriseCapabilityQueryPort -> OrganisationControlPlane.

Translates capability availability queries into OrganisationControlPlane
operations and converts the result into CapabilityAvailability.
"""

from __future__ import annotations

from contracts.enterprise_capability_query import CapabilityAvailability

from organisation_control_plane import OrganisationControlPlane


class EnterpriseCapabilityQueryAdapter:
    def __init__(self, org_plane: OrganisationControlPlane) -> None:
        self._org = org_plane

    def query_capability(self, capability_id: str) -> CapabilityAvailability | None:
        result = self._org.query_capability(capability_id)
        if result is None:
            return None
        return CapabilityAvailability(
            capability_id=result["capability_id"],
            available=result["available"],
            eta_seconds=result.get("eta_seconds"),
            assignee=result.get("assignee"),
            reason=result.get("reason", ""),
        )
