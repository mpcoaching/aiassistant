"""
Adapter: contracts.WorkflowExecutionPort -> workflow_runner executor.

Executes a workflow by name using the workflow_runner executor.
"""

from __future__ import annotations

from pathlib import Path

from contracts.workflow_execution import WorkflowExecutionRequest, WorkflowExecutionResult


class WorkflowExecutionAdapter:
    """Executes organisational workflows via the workflow_runner executor."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or self._find_repo_root()

    def _find_repo_root(self) -> Path:
        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists() or (parent / ".kilo").exists():
                return parent
        return current.parent

    def execute_workflow(self, request: WorkflowExecutionRequest) -> WorkflowExecutionResult:
        """Execute a workflow by name."""
        try:
            from executor import execute_workflow_from_file
            from loader import resolve_workflow_path
        except ImportError:
            return WorkflowExecutionResult(
                status="failed",
                workflow_name=request.workflow_name,
                error="workflow_runner executor not available",
            )

        workflow_path = resolve_workflow_path(request.workflow_name)
        if workflow_path is None:
            workflow_path = str(
                self._repo_root / "agentic" / "docs" / "workflows" / f"{request.workflow_name}.yaml"
            )

        result = execute_workflow_from_file(
            workflow_path=workflow_path,
            initial_context=request.initial_context,
            role_override=request.role_override,
        )

        return WorkflowExecutionResult(
            status=result.get("status", "unknown"),
            workflow_name=request.workflow_name,
            output=result,
            error=result.get("error"),
        )
