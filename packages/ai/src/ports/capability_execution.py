from typing import Protocol, Any
from pydantic import BaseModel


class ExecutionResult(BaseModel):
    outputs: dict[str, Any]
    artifacts: list[str] = []
    telemetry: dict[str, Any] = {}


class CapabilityExecutionPort(Protocol):
    def execute(self, capability_id: str, context: dict[str, Any], actor_context: dict[str, Any]) -> ExecutionResult: ...
