from typing import Protocol, Any
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    context: dict[str, Any] = {}


class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    reasoning: str | None = None
    previous_solution: dict[str, Any] | None = None
    human_input_request: dict[str, Any] | None = None
    capability_candidates: list[dict[str, Any]] | None = None
    telemetry: dict[str, Any] = {}


class AssistantPort(Protocol):
    def chat(self, request: ChatRequest) -> ChatResponse: ...
    def resume(self, session_id: str, human_response: dict[str, Any]) -> ChatResponse: ...
