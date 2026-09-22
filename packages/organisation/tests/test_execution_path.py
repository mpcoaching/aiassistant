"""
Layer 1 — Solution selection boundary tests (Increment 24).

Tests the Org Control Plane's select_execution_path decision boundary:
- known workflow selected when suitable
- capability path selected when no workflow exists but capability exists
- capability-gap path selected when neither exists
- workflow selection does not invoke capability development
- capability existence does not falsely imply a workflow exists
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from organisation_control_plane import InMemoryOrganisationControlPlane
from role import Role, Work
from execution_path import ExecutionPath, ExecutionPathResult

try:
    from capability import Capability, CapabilityKind, CapabilityStatus
except ImportError:
    Capability = None
    CapabilityKind = None
    CapabilityStatus = None


# ---- Helpers ----

def _make_plane() -> InMemoryOrganisationControlPlane:
    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    return plane


def _make_workflow(name: str, description: str = "") -> MagicMock:
    wf = MagicMock()
    wf.name = name
    wf.description = description
    wf.model_dump = MagicMock(return_value={"name": name, "description": description})
    return wf


# ---- Test: known workflow selected ----

def test_existing_workflow_selected_when_matching() -> None:
    """If a workflow matches the intent, EXISTING_WORKFLOW is returned."""
    plane = _make_plane()
    wf = _make_workflow("customer-retention-report", "Run the weekly customer retention report")

    def lookup(intent: str) -> list[Any]:
        intent_lower = intent.lower()
        if "retention" in intent_lower or "customer" in intent_lower:
            return [wf]
        return []

    result = plane.select_execution_path(
        intent="Run the weekly customer retention report",
        context={},
        workflow_lookup=lookup,
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    assert result.workflow is wf
    assert "retention" in result.reason.lower() or "workflow" in result.reason.lower()


def test_no_workflow_returns_non_workflow_path() -> None:
    """If no workflow matches, a non-workflow path is returned."""
    plane = _make_plane()

    def lookup(intent: str) -> list[Any]:
        return []

    result = plane.select_execution_path(
        intent="unknown task xyz",
        context={},
        workflow_lookup=lookup,
    )
    assert result.path != ExecutionPath.EXISTING_WORKFLOW


# ---- Test: capability path selected ----

def test_capability_path_selected_when_no_workflow_but_capability_exists() -> None:
    """If no workflow matches but a required capability exists, CAPABILITY_PATH is returned."""
    if Capability is None:
        pytest.skip("capability module not available")

    plane = _make_plane()
    capability = Capability(
        id="cap-retention-analysis",
        name="Customer Retention Analysis",
        description="Analyse customer retention metrics",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(capability)

    result = plane.select_execution_path(
        intent="Analyse customer retention",
        context={"required_capability_ids": ["cap-retention-analysis"]},
    )
    assert result.path == ExecutionPath.CAPABILITY_PATH
    assert result.capability_id == "cap-retention-analysis"


# ---- Test: new capability required ----

def test_new_capability_required_when_neither_exists() -> None:
    """If no workflow and no capability, NEW_CAPABILITY_REQUIRED is returned."""
    plane = _make_plane()

    result = plane.select_execution_path(
        intent="unknown task xyz",
        context={"required_capability_ids": []},
    )
    assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED


def test_new_capability_required_when_capability_not_in_context() -> None:
    """Existing capabilities not listed in required_capability_ids do not match."""
    if Capability is None:
        pytest.skip("capability module not available")

    plane = _make_plane()
    capability = Capability(
        id="cap-coding",
        name="Coding",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(capability)

    result = plane.select_execution_path(
        intent="write some code",
        context={"required_capability_ids": []},
    )
    assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED


# ---- Test: workflow wins over capability ----

def test_workflow_selected_even_when_capability_exists() -> None:
    """Workflow takes precedence over capability when both match."""
    if Capability is None:
        pytest.skip("capability module not available")

    plane = _make_plane()
    capability = Capability(
        id="cap-retention-analysis",
        name="Customer Retention Analysis",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(capability)

    wf = _make_workflow("customer-retention-report")

    def lookup(intent: str) -> list[Any]:
        return [wf]

    result = plane.select_execution_path(
        intent="Run customer retention report",
        context={"required_capability_ids": ["cap-retention-analysis"]},
        workflow_lookup=lookup,
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    assert result.capability_id is None


# ---- Test: workflow selection does not invoke capability development ----

def test_workflow_selection_does_not_invoke_capability_development() -> None:
    """Selecting a workflow does not create capability-development work."""
    plane = _make_plane()
    wf = _make_workflow("test-workflow")

    def lookup(intent: str) -> list[Any]:
        return [wf]

    result = plane.select_execution_path(
        intent="execute test workflow",
        context={},
        workflow_lookup=lookup,
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    assert result.capability_id is None

    work_count = len(plane.list_work())
    assert work_count == 0


# ---- Test: Paperclip implementation ----

def test_paperclip_control_plane_has_select_execution_path() -> None:
    """PaperclipOrganisationControlPlane implements select_execution_path."""
    try:
        from organisation_paperclip import PaperclipOrganisationControlPlane
    except ImportError:
        pytest.skip("Paperclip adapter not available")

    plane = PaperclipOrganisationControlPlane(base_url="http://localhost:3100")
    assert hasattr(plane, "select_execution_path")
    assert callable(plane.select_execution_path)


def test_paperclip_select_execution_path_returns_new_capability_when_none_found() -> None:
    """Paperclip OCP returns NEW_CAPABILITY_REQUIRED when nothing matches."""
    try:
        from organisation_paperclip import PaperclipOrganisationControlPlane
    except ImportError:
        pytest.skip("Paperclip adapter not available")

    plane = PaperclipOrganisationControlPlane(base_url="http://localhost:3100")
    result = plane.select_execution_path(
        intent="unknown task",
        context={"required_capability_ids": []},
    )
    assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED


# ---- Test: ExecutionPathResult is a small typed model ----

def test_execution_path_result_is_pydantic_model() -> None:
    """ExecutionPathResult is a small Pydantic model with expected fields."""
    result = ExecutionPathResult(
        path=ExecutionPath.EXISTING_WORKFLOW,
        reason="test",
    )
    assert result.path == "existing_workflow"
    assert result.reason == "test"
    assert result.workflow is None
    assert result.capability_id is None
    assert result.metadata == {}


def test_execution_path_result_serialises() -> None:
    """ExecutionPathResult serialises to a clean dict."""
    result = ExecutionPathResult(
        path=ExecutionPath.CAPABILITY_PATH,
        capability_id="cap-1",
        reason="capability exists",
    )
    data = result.model_dump()
    assert data["path"] == "capability_path"
    assert data["capability_id"] == "cap-1"
    assert data["reason"] == "capability exists"


# ---- Test: workflow_lookup callback is optional ----

def test_select_execution_path_without_workflow_lookup() -> None:
    """select_execution_path works without a workflow_lookup callback."""
    plane = _make_plane()
    result = plane.select_execution_path(
        intent="something",
        context={},
    )
    assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
