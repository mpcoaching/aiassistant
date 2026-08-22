from typing import Protocol, Any
from pydantic import BaseModel


class CapabilityCandidate(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    tags: list[str] = []
    execution_mode: str = "ai_mediated"


class CapabilityDiscoveryPort(Protocol):
    def list_capabilities(self) -> list[CapabilityCandidate]: ...
    def find_capabilities(self, request_text: str, context: dict[str, Any]) -> list[CapabilityCandidate]: ...
