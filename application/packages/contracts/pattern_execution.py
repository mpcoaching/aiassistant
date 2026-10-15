from typing import Protocol, Any
from pydantic import BaseModel


class PatternExecutionRequest(BaseModel):
    session_id: str
    pattern_step: dict[str, Any]
    context: dict[str, Any]
    participants: list[dict[str, Any]]
    prompt: str


class PatternExecutionResult(BaseModel):
    status: str
    outputs: dict[str, Any] = {}
    artifacts: list[str] = []
    telemetry: dict[str, Any] = {}
    human_input_request: dict[str, Any] | None = None


class PatternExecutionPort(Protocol):
    def execute_pattern(self, request: PatternExecutionRequest) -> PatternExecutionResult: ...
    def resume_pattern(self, session_id: str, human_response: dict[str, Any]) -> PatternExecutionResult: ...
