"""
Adapter: contracts.WorkManagementPort -> OrganisationControlPlane.

Translates WorkCreateRequest into Work model, delegates to
OrganisationControlPlane, and converts Work back to WorkReference.
"""

from __future__ import annotations

from contracts.work_management import WorkCreateRequest, WorkReference

from organisation_control_plane import OrganisationControlPlane
from role import Work


class WorkManagementAdapter:
    def __init__(self, org_plane: OrganisationControlPlane) -> None:
        self._org = org_plane

    def create_work(self, request: WorkCreateRequest) -> WorkReference:
        work = Work(
            id=f"work-{request.title.lower().replace(' ', '-')[:20]}",
            title=request.title,
            description=request.description,
            work_type=request.work_type,
            priority=request.priority,
            organisation_id=request.organisation_id,
            accountable_role_id=request.accountable_role_id,
            coordinating_role_id=request.coordinating_role_id,
            required_capability_ids=list(request.required_capability_ids),
        )
        assignee = self._org.get_role(request.accountable_role_id)
        if assignee is None:
            assignee = self._org.get_role("default")
        if assignee is None:
            assignee = type("Role", (), {"id": request.accountable_role_id})()
        self._org.assign_work(work, assignee)
        return WorkReference(work_id=work.id, status=work.status.value)

    def mark_ready(self, work_id: str) -> WorkReference | None:
        work = self._org.mark_work_ready(work_id)
        if work is None:
            return None
        return WorkReference(work_id=work.id, status=work.status.value)

    def get_work(self, work_id: str) -> WorkReference | None:
        work = self._org.get_work(work_id)
        if work is None:
            return None
        return WorkReference(work_id=work.id, status=work.status.value)
