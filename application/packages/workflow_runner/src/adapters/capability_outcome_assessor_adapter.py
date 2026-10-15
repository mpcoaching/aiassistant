"""
Operations plane — Capability outcome assessor adapter (Increment 19).

Evaluates ExecutionResult to determine whether a capability was actually
executed, failed during execution, or never executed at all.

This is the single classification point for capability invocation outcomes.
Pre-execution rejections (authorisation, missing deployment, capability not found)
are distinguished from execution failures to prevent pollution of maturation
telemetry.
"""

from __future__ import annotations

from contracts.capability_execution import ExecutionResult
from contracts.capability_outcome_assessor import CapabilityOutcome


class CapabilityOutcomeAssessorAdapter:
    """Assesses capability execution outcomes."""

    _PRE_EXECUTION_ERRORS = frozenset(
        {
            "capability_not_found",
            "execution_not_authorised",
            "no_deployment",
        }
    )

    def assess(self, result: ExecutionResult) -> CapabilityOutcome:
        telemetry = result.telemetry or {}
        outputs = result.outputs or {}

        if "authorisation" in telemetry:
            return CapabilityOutcome.NOT_EXECUTED
        if telemetry.get("error") in self._PRE_EXECUTION_ERRORS:
            return CapabilityOutcome.NOT_EXECUTED

        if telemetry.get("error") or outputs.get("error"):
            return CapabilityOutcome.FAILED

        return CapabilityOutcome.EXECUTED
