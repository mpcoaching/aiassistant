"""
Adapter: contracts.PatternExecutionPort -> PathwayRuntime.

Translates PatternExecutionRequest/PatternExecutionResult to/from
PathwayCallRequest/PathwayResponse, delegating to an injected PathwayRuntime.
"""

from __future__ import annotations

from typing import Any

from contracts.pattern_execution import PatternExecutionRequest, PatternExecutionResult
from pathway_runtime import PathwayCallRequest, PathwayResponse, PathwayRuntime


class PatternExecutionAdapter:
    def __init__(self, runtime: PathwayRuntime) -> None:
        self._runtime = runtime

    def execute_pattern(self, request: PatternExecutionRequest) -> PatternExecutionResult:
        pathway_request = PathwayCallRequest(
            session_id=request.session_id,
            pattern_step=request.pattern_step,
            context=request.context,
            participants=request.participants,
            prompt=request.prompt,
        )
        response = self._runtime.invoke(pathway_request)
        return self._to_result(response)

    def resume_pattern(self, session_id: str, human_response: dict[str, Any]) -> PatternExecutionResult:
        response = self._runtime.resume(session_id, human_response)
        return self._to_result(response)

    def _to_result(self, response: PathwayResponse) -> PatternExecutionResult:
        return PatternExecutionResult(
            status=response.status.value,
            outputs=response.outputs,
            artifacts=response.artifacts,
            telemetry=response.telemetry,
            human_input_request=response.human_input_request,
        )
