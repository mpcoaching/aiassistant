"""
Unit tests for InvocationRecorderAdapter (Increment 18 / 19).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["bus", "capability_registry", "ai", "workflow_runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from contracts.capability_execution import ExecutionResult
from contracts.capability_outcome_assessor import CapabilityOutcome

from workflow_runner.src.adapters.invocation_recorder_adapter import InvocationRecorderAdapter


class StubAssessor:
    def __init__(self, outcome: CapabilityOutcome) -> None:
        self._outcome = outcome
        self.calls: list[ExecutionResult] = []

    def assess(self, result: ExecutionResult) -> CapabilityOutcome:
        self.calls.append(result)
        return self._outcome


def test_record_invocation_calls_store_with_success() -> None:
    assessor = StubAssessor(CapabilityOutcome.EXECUTED)
    store = MagicMock()
    adapter = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)
    result = ExecutionResult(outputs={"ok": True}, artifacts=[], telemetry={})

    adapter.record_invocation("cap-1", result, {"actor_id": "agent-1"})

    store.record_invocation.assert_called_once_with("cap-1", "success")
    assert len(assessor.calls) == 1


def test_record_invocation_calls_store_with_failure() -> None:
    assessor = StubAssessor(CapabilityOutcome.FAILED)
    store = MagicMock()
    adapter = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)
    result = ExecutionResult(outputs={}, artifacts=[], telemetry={"error": "something failed"})

    adapter.record_invocation("cap-1", result, None)

    store.record_invocation.assert_called_once_with("cap-1", "failure")
    assert len(assessor.calls) == 1


def test_record_invocation_skips_not_executed() -> None:
    assessor = StubAssessor(CapabilityOutcome.NOT_EXECUTED)
    store = MagicMock()
    adapter = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)
    result = ExecutionResult(
        outputs={"error": "Execution not authorised: x"},
        artifacts=[],
        telemetry={"authorisation": "no_active_assignment"},
    )

    adapter.record_invocation("cap-1", result, None)

    store.record_invocation.assert_not_called()
    assert len(assessor.calls) == 1


def test_record_invocation_handles_missing_store_gracefully() -> None:
    assessor = StubAssessor(CapabilityOutcome.EXECUTED)
    adapter = InvocationRecorderAdapter(store=None, outcome_assessor=assessor)
    result = ExecutionResult(outputs={"ok": True}, artifacts=[], telemetry={})

    adapter.record_invocation("cap-1", result, None)

    assert len(assessor.calls) == 0


def test_record_invocation_handles_concept_not_found_gracefully() -> None:
    assessor = StubAssessor(CapabilityOutcome.EXECUTED)
    store = MagicMock()
    store.record_invocation.side_effect = KeyError("Concept not found: cap-1")
    adapter = InvocationRecorderAdapter(store=store, outcome_assessor=assessor)
    result = ExecutionResult(outputs={"ok": True}, artifacts=[], telemetry={})

    adapter.record_invocation("cap-1", result, None)

    store.record_invocation.assert_called_once_with("cap-1", "success")


def test_legacy_determine_outcome_success_when_no_error() -> None:
    adapter = InvocationRecorderAdapter(store=MagicMock())
    assert adapter._legacy_determine_outcome(ExecutionResult(outputs={"ok": True}, artifacts=[], telemetry={})) == "success"


def test_legacy_determine_outcome_failure_on_telemetry_error() -> None:
    adapter = InvocationRecorderAdapter(store=MagicMock())
    assert adapter._legacy_determine_outcome(ExecutionResult(outputs={}, artifacts=[], telemetry={"error": "x"})) == "failure"


def test_legacy_determine_outcome_failure_on_output_error() -> None:
    adapter = InvocationRecorderAdapter(store=MagicMock())
    assert adapter._legacy_determine_outcome(ExecutionResult(outputs={"error": "x"}, artifacts=[], telemetry={})) == "failure"
