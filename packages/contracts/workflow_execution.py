from typing import Any, Protocol

from pydantic import BaseModel


class WorkflowExecutionRequest(BaseModel):
    """Request to execute a workflow."""

    workflow_name: str
    initial_context: dict[str, Any] | None = None
    role_override: str | None = None


class WorkflowExecutionResult(BaseModel):
    """Result of workflow execution."""

    status: str
    workflow_name: str
    output: dict[str, Any] | None = None
    error: str | None = None


class WorkflowExecutionPort(Protocol):
    """Port for executing organisational workflows."""

    def execute_workflow(self, request: WorkflowExecutionRequest) -> WorkflowExecutionResult:
        """Execute a workflow by name."""
        ...
