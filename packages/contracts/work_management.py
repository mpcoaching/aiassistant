from typing import Protocol
from pydantic import BaseModel


class WorkCreateRequest(BaseModel):
    title: str
    description: str = ""
    accountable_role_id: str
    coordinating_role_id: str | None = None
    required_capability_ids: list[str] = []
    work_type: str = "bau"
    priority: str = "normal"
    organisation_id: str = "default"


class WorkReference(BaseModel):
    work_id: str
    status: str


class WorkManagementPort(Protocol):
    def create_work(self, request: WorkCreateRequest) -> WorkReference: ...
    def mark_ready(self, work_id: str) -> WorkReference | None: ...
    def get_work(self, work_id: str) -> WorkReference | None: ...
