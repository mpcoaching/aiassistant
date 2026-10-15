"""
Unit tests for CapabilityOutcomeAssessorAdapter (Increment 19).
"""

from __future__ import annotations

import sys
from pathlib import Path

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["bus", "capability_registry", "ai", "workflow_runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from contracts.capability_execution import ExecutionResult
from contracts.capability_outcome_assessor import CapabilityOutcome

from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
    CapabilityOutcomeAssessorAdapter,
)


def test_assess_executed_when_no_errors() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"composed_prompt": "purpose: inputs"},
        artifacts=[],
        telemetry={"mode": "ai_mediated"},
    )
    assert adapter.assess(result) == CapabilityOutcome.EXECUTED


def test_assess_failed_on_output_error() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"error": "ModuleNotFoundError"},
        artifacts=[],
        telemetry={},
    )
    assert adapter.assess(result) == CapabilityOutcome.FAILED


def test_assess_failed_on_telemetry_error() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"result": "ok"},
        artifacts=[],
        telemetry={"error": "execution_error"},
    )
    assert adapter.assess(result) == CapabilityOutcome.FAILED


def test_assess_not_executed_on_authorisation() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"error": "Execution not authorised: no_active_assignment"},
        artifacts=[],
        telemetry={"authorisation": "no_active_assignment"},
    )
    assert adapter.assess(result) == CapabilityOutcome.NOT_EXECUTED


def test_assess_not_executed_on_capability_not_found() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"error": "Capability not found: cap-x"},
        artifacts=[],
        telemetry={"error": "capability_not_found"},
    )
    assert adapter.assess(result) == CapabilityOutcome.NOT_EXECUTED


def test_assess_not_executed_on_execution_not_authorised() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"error": "Execution not authorised: x"},
        artifacts=[],
        telemetry={"error": "execution_not_authorised"},
    )
    assert adapter.assess(result) == CapabilityOutcome.NOT_EXECUTED


def test_assess_not_executed_on_no_deployment() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"error": "No deployment for capability: cap-x"},
        artifacts=[],
        telemetry={"error": "no_deployment"},
    )
    assert adapter.assess(result) == CapabilityOutcome.NOT_EXECUTED


def test_assess_handles_none_outputs_and_telemetry() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(outputs={}, artifacts=[], telemetry={})
    assert adapter.assess(result) == CapabilityOutcome.EXECUTED


def test_assess_pre_execution_takes_priority_over_output_error() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"error": "Execution not authorised: x"},
        artifacts=[],
        telemetry={"authorisation": "no_active_assignment"},
    )
    assert adapter.assess(result) == CapabilityOutcome.NOT_EXECUTED


def test_assess_unknown_telemetry_error_treated_as_failure() -> None:
    adapter = CapabilityOutcomeAssessorAdapter()
    result = ExecutionResult(
        outputs={"result": "partial"},
        artifacts=[],
        telemetry={"error": "unknown_error_code"},
    )
    assert adapter.assess(result) == CapabilityOutcome.FAILED
