"""
CapabilityRequest governance model (Increment 3).

A CapabilityRequest is a transient governance object. When approved,
it is persisted as an EnterpriseConcept (kind=capability, status=draft).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from capabilities import Parameter


class CapabilityRequest(BaseModel):
    """Governance object for requesting a new capability."""

    name: str
    purpose: str
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[Parameter] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    requester: str = "user"
    status: str = "pending"
    governance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str | None = None

    def approve(self, approver: str, rationale: str | None = None) -> None:
        """Transition to approved and record governance."""
        self.status = "approved"
        self.governance = {
            "action": "approved",
            "approved_by": approver,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "rationale": rationale or "",
        }

    def reject(self, rejector: str, rationale: str | None = None) -> None:
        """Transition to rejected and record governance."""
        self.status = "rejected"
        self.governance = {
            "action": "rejected",
            "rejected_by": rejector,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rationale": rationale or "",
        }

    def modify(
        self,
        name: str | None = None,
        purpose: str | None = None,
        inputs: list[Parameter] | None = None,
        outputs: list[Parameter] | None = None,
        acceptance_criteria: list[str] | None = None,
        modified_by: str = "user",
    ) -> None:
        """Update the specification before approval."""
        if name is not None:
            self.name = name
        if purpose is not None:
            self.purpose = purpose
        if inputs is not None:
            self.inputs = inputs
        if outputs is not None:
            self.outputs = outputs
        if acceptance_criteria is not None:
            self.acceptance_criteria = acceptance_criteria
        self.governance = {
            "action": "modified",
            "modified_by": modified_by,
            "modified_at": datetime.now(timezone.utc).isoformat(),
        }
