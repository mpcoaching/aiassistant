from enum import Enum
from typing import Protocol

from contracts.capability_execution import ExecutionResult


class CapabilityOutcome(str, Enum):
    EXECUTED = "executed"
    FAILED = "failed"
    NOT_EXECUTED = "not_executed"


class CapabilityOutcomeAssessor(Protocol):
    def assess(self, result: ExecutionResult) -> CapabilityOutcome: ...
