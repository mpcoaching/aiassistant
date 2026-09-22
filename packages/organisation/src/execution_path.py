"""
Execution path result for organisational solution selection.

A small typed result returned by OrganisationControlPlane.select_execution_path().
Does not import from workflow_runner to preserve the organisational boundary.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecutionPath(str, Enum):
    """Possible execution paths selected by the Organisation Control Plane."""

    EXISTING_WORKFLOW = "existing_workflow"
    CAPABILITY_PATH = "capability_path"
    NEW_CAPABILITY_REQUIRED = "new_capability_required"
    HUMAN_TEAM_INVESTIGATION = "human_team_investigation"


class ExecutionPathResult(BaseModel):
    """Result of organisational solution selection."""

    path: ExecutionPath
    workflow: Any | None = Field(default=None, description="Matching workflow definition, if any")
    capability_id: str | None = Field(default=None, description="Matching capability ID, if any")
    reason: str = Field(default="", description="Explanation of the selection")
    metadata: dict[str, Any] = Field(default_factory=dict)
