"""
Adapter: contracts.SolutionSelectionPort -> OrganisationControlPlane.

Translates solution selection requests into OrganisationControlPlane
select_execution_path calls and converts the result to a contracts model.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from contracts.solution_selection import SolutionSelectionResult
from organisation.execution_path import ExecutionPathResult

from organisation_control_plane import OrganisationControlPlane


class SolutionSelectionAdapter:
    """Wraps OrganisationControlPlane as a SolutionSelectionPort."""

    def __init__(
        self,
        org_plane: OrganisationControlPlane,
        workflow_lookup: Callable[[str], list[Any]] | None = None,
        capability_query: Callable[[str], Any] | None = None,
    ) -> None:
        self._org = org_plane
        self._workflow_lookup = workflow_lookup
        self._capability_query = capability_query

    def select_execution_path(
        self,
        intent: str,
        context: dict[str, Any],
    ) -> SolutionSelectionResult | None:
        """Select how an intent should be executed."""
        org_result: ExecutionPathResult = self._org.select_execution_path(
            intent=intent,
            context=context,
            workflow_lookup=self._workflow_lookup,
            capability_query=self._capability_query,
        )

        workflow_dict = None
        if org_result.workflow is not None:
            try:
                workflow_dict = org_result.workflow.model_dump()
            except AttributeError:
                workflow_dict = {
                    "name": getattr(org_result.workflow, "name", str(org_result.workflow)),
                    "description": getattr(org_result.workflow, "description", None),
                }

        return SolutionSelectionResult(
            path=org_result.path.value,
            workflow=workflow_dict,
            capability_id=org_result.capability_id,
            reason=org_result.reason,
            metadata=org_result.metadata,
        )
