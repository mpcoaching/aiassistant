"""
Adapter: contracts.OrganisationalContextPort -> OrganisationControlPlane.

Translates actor_id/role_id into a request_context dict, delegates to
OrganisationControlPlane, and converts OrgContext/Role to contracts DTOs.
"""

from __future__ import annotations

from typing import Any

from contracts.organisational_context import OrganisationalContext, RoleReference

from organisation_control_plane import OrganisationControlPlane


class OrganisationalContextAdapter:
    def __init__(self, org_plane: OrganisationControlPlane) -> None:
        self._org = org_plane

    def get_context(self, actor_id: str | None, role_id: str | None) -> OrganisationalContext:
        request_context: dict[str, Any] = {}
        if actor_id is not None:
            request_context["actor_id"] = actor_id
        if role_id is not None:
            request_context["role_id"] = role_id
        org_context = self._org.get_organisational_context(request_context)
        return OrganisationalContext(
            current_actor_id=org_context.current_actor_id,
            current_role_id=org_context.current_role_id,
            reporting_relationships=list(org_context.reporting_relationships),
            authority_scope=list(org_context.authority_scope),
            organisational_relationships=dict(org_context.organisational_relationships),
            capability_gaps=list(org_context.capability_gaps),
        )

    def get_role(self, role_id: str) -> RoleReference | None:
        role = self._org.get_role(role_id)
        if role is None:
            return None
        return RoleReference(
            role_id=role.id,
            name=role.name,
            status=role.status.value,
        )
