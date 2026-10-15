from typing import Protocol, Any
from pydantic import BaseModel


class SessionReference(BaseModel):
    session_id: str
    status: str
    pipeline: list[dict[str, Any]] = []


class SessionFactoryPort(Protocol):
    def create_session(self, strategy: str, pattern_pipeline: list[str], context: dict[str, Any]) -> SessionReference: ...
