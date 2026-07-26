"""
Stable abstraction boundary for Pattern Runtimes (Phase 6 / RUNTIME-MAPPING.md).

No framework concepts leak across this boundary. LangGraph, workflow_runner,
and any future runtime implement this interface.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class RuntimeCapability(str, Enum):
    STATEFUL = "supports_stateful"
    CONCURRENT_PARTICIPANTS = "supports_concurrent_participants"
    STREAMING = "supports_streaming"
    INTERRUPTION = "supports_interruption"


class PathwayStatus(str, Enum):
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    FAILED = "failed"
    PAUSED = "paused"
    WAITING = "waiting"


class PathwayCallRequest:
    """Invocation contract from Ecosystem -> Framework."""

    def __init__(
        self,
        session_id: str,
        pattern_step: dict[str, Any],
        context: dict[str, Any],
        participants: list[dict[str, Any]],
        prompt: str,
        max_turns: int = 10,
        timeout_seconds: int = 300,
    ) -> None:
        self.session_id = session_id
        self.pattern_step = pattern_step
        self.context = context
        self.participants = participants
        self.prompt = prompt
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds


class PathwayResponse:
    """Response contract from Framework -> Ecosystem."""

    def __init__(
        self,
        status: PathwayStatus,
        outputs: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        telemetry: dict[str, Any] | None = None,
        human_input_request: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.outputs = outputs or {}
        self.artifacts = artifacts or []
        self.telemetry = telemetry or {}
        self.human_input_request = human_input_request


class PathwayRuntime:
    """Stable interface for all pattern execution substrates."""

    @property
    def id(self) -> str:
        raise NotImplementedError

    @property
    def capabilities(self) -> list[RuntimeCapability]:
        raise NotImplementedError

    def supports(self, capability: RuntimeCapability) -> bool:
        return capability in self.capabilities

    def invoke(self, request: PathwayCallRequest) -> PathwayResponse:
        raise NotImplementedError

    def resume(self, session_id: str, human_response: dict[str, Any]) -> PathwayResponse:
        raise NotImplementedError
