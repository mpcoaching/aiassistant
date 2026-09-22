from typing import Any, Protocol

from pydantic import BaseModel, Field


class SolutionSelectionResult(BaseModel):
    """Result of organisational solution selection."""

    path: str = Field(description="One of: existing_workflow, capability_path, new_capability_required, human_team_investigation")
    workflow: dict | None = Field(default=None, description="Matching workflow definition, if any")
    capability_id: str | None = Field(default=None, description="Matching capability ID, if any")
    reason: str = Field(default="", description="Explanation of the selection")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SolutionSelectionPort(Protocol):
    """Port for organisational solution selection."""

    def select_execution_path(
        self,
        intent: str,
        context: dict[str, Any],
    ) -> SolutionSelectionResult | None:
        """Select how an intent should be executed.

        Returns None if the implementation cannot determine a path.
        """
        ...
