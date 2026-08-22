from typing import Protocol, Any
from pydantic import BaseModel


class OrganisationalContext(BaseModel):
    current_actor_id: str | None = None
    current_role_id: str | None = None
    reporting_relationships: list[str] = []
    authority_scope: list[str] = []
    organisational_relationships: dict[str, Any] = {}
    capability_gaps: list[str] = []


class RoleReference(BaseModel):
    role_id: str
    name: str
    status: str = "active"


class OrganisationalContextPort(Protocol):
    def get_context(self, actor_id: str | None, role_id: str | None) -> OrganisationalContext: ...
    def get_role(self, role_id: str) -> RoleReference | None: ...
