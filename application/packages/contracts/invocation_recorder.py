from typing import Protocol, Any

from contracts.capability_execution import ExecutionResult


class InvocationRecorder(Protocol):
    def record_invocation(
        self,
        capability_id: str,
        result: ExecutionResult,
        actor_context: dict[str, Any] | None = None,
    ) -> None: ...
