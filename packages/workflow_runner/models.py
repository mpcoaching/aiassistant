"""
Pydantic models for the Workflow Runner.

Defines the canonical schema for workflow definitions, steps, skills, and tools.
Schema is versioned to support future upgrades.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StepType(str, Enum):
    """Supported step types in a workflow."""
    WORKFLOW = "workflow"
    SKILL = "skill"
    TOOL = "tool"


class Step(BaseModel):
    """A single step within a workflow."""
    type: StepType
    name: str
    uses: str = Field(..., description="Reference to the skill, tool, or sub-workflow to execute")
    with_: dict[str, Any] | None = Field(None, alias="with", description="Input parameters for this step")

    model_config = ConfigDict(populate_by_name=True)


class WorkflowDefinition(BaseModel):
    """Canonical workflow definition matching workflow-schema.md."""
    version: str = Field(default="1", description="Schema version for future upgrades")
    name: str
    description: str | None = None
    kind: str = Field(default="workflow", pattern="^(workflow)$")
    role: list[str] | None = Field(default=None, description="Roles that can execute this workflow")
    intent: dict[str, Any] | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None
    steps: list[Step]

    @field_validator("steps")
    @classmethod
    def steps_must_not_be_empty(cls, v: list[Step]) -> list[Step]:
        if not v:
            raise ValueError("Workflow must have at least one step")
        return v


class SkillDefinition(BaseModel):
    """Definition of a skill (prompt template)."""
    version: str = Field(default="1")
    name: str
    description: str | None = None
    kind: str = Field(default="skill", pattern="^(skill)$")
    role: list[str] | None = None
    intent: dict[str, Any] | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None


class ToolDefinition(BaseModel):
    """Definition of a tool (executable command)."""
    version: str = Field(default="1")
    name: str
    description: str | None = None
    kind: str = Field(default="tool", pattern="^(tool)$")
    inputs: dict[str, Any] | None = None
    action: dict[str, Any] | None = None


class WorkflowState(BaseModel):
    """Persistent state for a running workflow execution."""
    workflow_id: str
    workflow_name: str
    workflow_path: str
    status: str = Field(default="pending", pattern="^(pending|running|completed|failed|paused|stopped|scheduled)$")
    current_step_index: int = Field(default=0, ge=0)
    steps: list[Step]
    step_results: list[dict[str, Any] | None] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    log_path: str | None = None


class StepResult(BaseModel):
    """Result of executing a single step."""
    step_name: str
    step_type: StepType
    status: str = Field(default="pending", pattern="^(pending|running|completed|failed|skipped)$")
    output: Any | None = None
    composed_prompt: str | None = None
    error: str | None = None
    duration_seconds: float | None = None