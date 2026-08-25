from typing import Protocol

from pydantic import BaseModel


class CapabilityAvailability(BaseModel):
    capability_id: str
    available: bool
    eta_seconds: int | None = None
    assignee: str | None = None
    reason: str = ""


class EnterpriseCapabilityQueryPort(Protocol):
    def query_capability(self, capability_id: str) -> CapabilityAvailability | None: ...
