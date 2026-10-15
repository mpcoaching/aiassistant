"""Organisation composition/bootstrap boundary.

Selects and configures the OrganisationControlPlane implementation
based on deployment configuration. The API and Assistant remain
unaware of which operational backend is in use.
"""

from __future__ import annotations

import os


def create_organisation_control_plane():
    """Create the Organisation control plane based on deployment configuration.

    If PAPERCLIP_URL is set, creates a Paperclip-backed control plane.
    Otherwise, creates an in-memory control plane with a default researcher role.

    This is the only place where deployment configuration determines the
    operational backend. All other code depends only on the
    OrganisationControlPlane interface.
    """
    paperclip_url = os.getenv("PAPERCLIP_URL")
    if paperclip_url:
        from organisation_paperclip import PaperclipOrganisationControlPlane
        return PaperclipOrganisationControlPlane(
            base_url=paperclip_url,
            api_key=os.getenv("PAPERCLIP_API_KEY", ""),
            company_id=os.getenv("PAPERCLIP_COMPANY_ID", "default"),
        )
    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role
    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="researcher", name="Researcher", authority_ids=[]))
    return plane
