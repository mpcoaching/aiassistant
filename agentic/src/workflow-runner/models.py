"""
Pydantic models for the Workflow Runner.

Defines the canonical schema for workflow definitions, steps, skills, and tools.
Schema is versioned to support future upgrades.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
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
    with_: Optional[Dict[str, Any]] = Field(None, alias="with", description="Input parameters for this step")

    model_config = ConfigDict(populate_by_name=True)


class WorkflowDefinition(BaseModel):
    """Canonical workflow definition matching workflow-schema.md."""
    version: str = Field(default="1", description="Schema version for future upgrades")
    name: str
    description: Optional[str] = None
    kind: str = Field(default="workflow", pattern="^(workflow)$")
    role: Optional[List[str]] = Field(default=None, description="Roles that can execute this workflow")
    intent: Optional[Dict[str, Any]] = None
    inputs: Optional[List[str]] = None
    outputs: Optional[List[str]] = None
    steps: List[Step]

    @field_validator("steps")
    @classmethod
    def steps_must_not_be_empty(cls, v: List[Step]) -> List[Step]:
        if not v:
            raise ValueError("Workflow must have at least one step")
        return v


class SkillDefinition(BaseModel):
    """Definition of a skill (prompt template)."""
    version: str = Field(default="1")
    name: str
    description: Optional[str] = None
    kind: str = Field(default="skill", pattern="^(skill)$")
    role: Optional[List[str]] = None
    intent: Optional[Dict[str, Any]] = None
    inputs: Optional[List[str]] = None
    outputs: Optional[List[str]] = None


class ToolDefinition(BaseModel):
    """Definition of a tool (executable command)."""
    version: str = Field(default="1")
    name: str
    description: Optional[str] = None
    kind: str = Field(default="tool", pattern="^(tool)$")
    inputs: Optional[Dict[str, Any]] = None
    action: Optional[Dict[str, Any]] = None


class WorkflowState(BaseModel):
    """Persistent state for a running workflow execution."""
    workflow_id: str
    workflow_name: str
    workflow_path: str
    status: str = Field(default="pending", pattern="^(pending|running|completed|failed|paused|stopped|scheduled)$")
    current_step_index: int = Field(default=0, ge=0)
    steps: List[Step]
    step_results: List[Optional[Dict[str, Any]]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    log_path: Optional[str] = None


class StepResult(BaseModel):
    """Result of executing a single step."""
    step_name: str
    step_type: StepType
    status: str = Field(default="pending", pattern="^(pending|running|completed|failed|skipped)$")
    output: Optional[Any] = None
    composed_prompt: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None