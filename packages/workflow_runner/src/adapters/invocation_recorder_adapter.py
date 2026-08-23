"""
Operations plane — Invocation recorder adapter (Increment 18).

Translates ExecutionResult into ConceptStore.record_invocation() calls.
This is the only place in workflow_runner that knows about ConceptStore
for invocation telemetry.
"""

from __future__ import annotations

from typing import Any

from contracts.capability_execution import ExecutionResult
from contracts.capability_outcome_assessor import CapabilityOutcome, CapabilityOutcomeAssessor


class InvocationRecorderAdapter:
    """Records capability invocation telemetry to ConceptStore."""

    def __init__(
        self,
        store: Any | None = None,
        outcome_assessor: CapabilityOutcomeAssessor | None = None,
    ) -> None:
        self._store = store
        self._outcome_assessor = outcome_assessor

    def record_invocation(
        self,
        capability_id: str,
        result: ExecutionResult,
        actor_context: dict[str, Any] | None = None,
    ) -> None:
        if self._store is None:
            return

        if self._outcome_assessor is not None:
            outcome = self._outcome_assessor.assess(result)
            if outcome == CapabilityOutcome.NOT_EXECUTED:
                return
            store_outcome = "success" if outcome == CapabilityOutcome.EXECUTED else "failure"
        else:
            store_outcome = self._legacy_determine_outcome(result)

        try:
            self._store.record_invocation(capability_id, store_outcome)
        except KeyError:
            pass

    def _legacy_determine_outcome(self, result: ExecutionResult) -> str:
        telemetry = result.telemetry or {}
        outputs = result.outputs or {}
        if telemetry.get("error") or outputs.get("error") or "authorisation" in telemetry:
            return "failure"
        return "success"
