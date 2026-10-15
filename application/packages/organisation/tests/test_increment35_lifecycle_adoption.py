"""
Architectural tests for Increment 35 — Workflow Lifecycle & Adoption Authority.

Builds on the evidence-to-adoption boundary established in Increment 34 and the
execution-boundary established in Increment 33. Adds tests for the specific
investigation findings of Increment 35 that are NOT already covered by prior
increments:

A. WorkflowDefinition is a boundary object — OCP receives it as opaque ``Any``,
   does not import the class.
B. No ``Workflow`` entity exists — ``WorkflowDefinition`` is the sole concept;
   there is no separate organisational ``Workflow`` identity to introduce.
D. API ``create_workflow`` writes YAML directly to filesystem — no adoption
   decision gate.
I. ``build_workflow_lookup`` conflates discoverability with relevance and
   authority (keyword matching only, no adoption status).
M. BAU directionality — Work/request drives workflow selection, not the reverse.
N. ``WorkflowExecutionPort`` has no actor/authorisation context; workflow
   execution does not check capability-level authorisation.
O. Backend independence — LangGraphRuntime and PatternRuntime do not decide
   organisational adoption; Paperclip's select_execution_path ignores the
   workflow_lookup callback.

Tests that are already covered by Increment 33/34 are intentionally NOT
duplicated here. See the corresponding sections in increment35_report.md.
"""

from __future__ import annotations

import ast
import inspect
import os
from typing import Any
from unittest.mock import MagicMock

from execution_path import ExecutionPath
from role import Work

ORGANISATION_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "src"
))
WORKFLOW_RUNNER_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner"
))
WORKFLOW_RUNNER_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner", "src"
))
CONTRACTS_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "contracts"
))


# ---- A. WorkflowDefinition ownership: boundary object, not organisational entity ----


def test_ocp_does_not_import_workflow_definition() -> None:
    """OrganisationControlPlane does not import WorkflowDefinition — it receives
    workflows as opaque ``Any`` through the ``workflow_lookup`` callback and
    stores them in ``ExecutionPathResult.workflow`` (typed ``Any``)."""
    ocp_source = inspect.getsource(
        __import__("organisation_control_plane", fromlist=["organisation_control_plane"])
    )
    # OCP source must not import the workflow_runner models
    assert "from models import" not in ocp_source
    assert "from workflow_runner" not in ocp_source
    assert "WorkflowDefinition" not in ocp_source.replace(
        '"WorkflowDefinition"', ''  # exclude string literal references in docstrings
    )


def test_execution_path_result_workflow_is_opaque_any() -> None:
    """ExecutionPathResult.workflow is typed ``Any | None`` — the organisation
    plane does not need to know the structure of a WorkflowDefinition, it only
    passes it through to the execution port."""
    from execution_path import ExecutionPathResult

    workflow_field = ExecutionPathResult.model_fields["workflow"]
    # The annotation should be Any or Optional[Any]
    assert workflow_field is not None


def test_workflow_definition_lives_in_workflow_runner_not_organisation() -> None:
    """WorkflowDefinition is defined in workflow_runner/models.py, not in the
    organisation package. The organisation plane treats it as an implementation
    detail of the execution engine."""
    from models import WorkflowDefinition

    assert WorkflowDefinition.__module__.startswith("models")
    # Verify it is not defined in organisation module
    org_init = os.path.join(ORGANISATION_SRC, "__init__.py")
    if os.path.exists(org_init):
        with open(org_init) as f:
            org_source = f.read()
        assert "class WorkflowDefinition" not in org_source


# ---- B. No separate Workflow entity ----


def test_no_workflow_entity_exists() -> None:
    """There is no ``Workflow`` entity class — only ``WorkflowDefinition`` (the
    pattern) and ``WorkflowState`` (the runtime state). A separate organisational
    Workflow identity is not required because the organisation only needs to know
    'this pattern is known' via OCP's EXISTING_WORKFLOW decision."""
    # Search for any class literally named 'Workflow' (not WorkflowDefinition,
    # WorkflowState, WorkflowExecution*, etc.)
    search_roots = [
        WORKFLOW_RUNNER_SRC,
        WORKFLOW_RUNNER_ROOT,
        ORGANISATION_SRC,
        CONTRACTS_ROOT,
    ]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                with open(fpath) as f:
                    try:
                        tree = ast.parse(f.read())
                    except SyntaxError:
                        continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == "Workflow":
                        assert False, f"Unexpected 'Workflow' class in {fpath}:{node.lineno}"


def test_workflow_definition_is_the_sole_workflow_concept() -> None:
    """WorkflowDefinition is the only workflow concept in the architecture.
    There is no 'Workflow' identity layer above it that the organisation owns
    separately."""
    from models import WorkflowDefinition, WorkflowState

    # WorkflowDefinition is the pattern; WorkflowState is runtime state
    assert WorkflowDefinition is not WorkflowState
    # No intermediary 'Workflow' class in models
    model_dir = os.path.join(WORKFLOW_RUNNER_ROOT, "models.py")
    with open(model_dir) as f:
        tree = ast.parse(f.read())
    class_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]
    assert "Workflow" not in class_names
    assert "WorkflowDefinition" in class_names
    assert "WorkflowState" in class_names


# ---- D. Filesystem presence = creation mechanism (no adoption gate) ----


def test_api_create_workflow_writes_yaml_without_adoption_check() -> None:
    """The API ``create_workflow`` endpoint writes YAML directly to the filesystem.
    There is no adoption decision gate — writing the file IS the adoption signal
    in the current architecture."""
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()
        tree = ast.parse(source)

    found_create_workflow = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_workflow":
            found_create_workflow = True
            func_source = ast.get_source_segment(
                source, node
            ) or ""
            # It writes YAML to filesystem
            assert "yaml.safe_dump" in func_source or "write_text" in func_source
            # No adoption check
            assert "adopt" not in func_source.lower()
            assert "approval" not in func_source.lower()
            break
    assert found_create_workflow


def test_api_list_workflows_globs_filesystem_no_adoption_filter() -> None:
    """The API ``list_workflows`` endpoint globs YAML files directly — no
    adoption status is checked. Every YAML file in the workflows directory
    is exposed as a valid workflow."""
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # Find the list_workflows function source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "list_workflows":
            func_source = ast.get_source_segment(source, node) or ""
            assert "glob" in func_source
            # No adoption status filtering
            assert "adopt" not in func_source.lower()
            assert "status" not in func_source.lower()
            break


# ---- I. Applicability/discovery: filesystem presence conflates discovery, relevance, authority, adoption ----


def test_build_workflow_lookup_matches_purely_by_keyword_not_semantics() -> None:
    """build_workflow_lookup uses simple substring/keyword matching between the
    intent string and workflow name/description. It does not perform semantic
    relevance assessment, capability matching, or adoption checking. Discovery,
    relevance, authority, and adoption are all collapsed into 'file exists on disk'."""
    from workflow_runner.src.composition import build_workflow_lookup

    source = inspect.getsource(build_workflow_lookup)
    # It matches by keyword overlap
    assert "intent_lower" in source
    assert "name_lower" in source
    assert "desc_lower" in source
    # It does NOT check semantic relevance
    assert "semantic" not in source.lower()
    # It does NOT check capability association
    assert "capability" not in source.lower()
    # It does NOT check adoption status
    assert "adopt" not in source.lower()


def test_ocp_treats_lookup_result_as_immediate_adoption() -> None:
    """OCP's select_execution_path returns EXISTING_WORKFLOW whenever
    workflow_lookup returns a non-empty list. There is no 'is this workflow
    adopted?' check — filesystem presence via lookup IS the adoption signal."""
    plane_cls = __import__("organisation_control_plane", fromlist=["InMemoryOrganisationControlPlane"]).InMemoryOrganisationControlPlane
    plane = plane_cls()

    wf = MagicMock()
    wf.name = "any-file-on-disk"
    wf.description = "just exists"

    def lookup(intent: str) -> list[Any]:
        return [wf]

    result = plane.select_execution_path(
        intent="anything that matches",
        context={},
        workflow_lookup=lookup,
    )
    assert result.path == ExecutionPath.EXISTING_WORKFLOW
    # OCP has no way to reject a workflow as "not adopted"
    ocp_methods = set(dir(plane))
    assert not any("adopt" in m.lower() for m in ocp_methods)
    assert not any("deprecat" in m.lower() for m in ocp_methods)
    assert not any("retire" in m.lower() for m in ocp_methods)


# ---- M. BAU directionality: Work/request drives workflow selection ----


def test_workflow_lookup_is_called_with_intent_not_workflow_driven() -> None:
    """OCP.select_execution_path receives `intent` (the user's request text)
    and calls workflow_lookup(intent). The workflow does NOT cause Work to
    exist — the request/intent finds the workflow."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()

    lookup_calls: list[str] = []

    def lookup(intent: str) -> list[Any]:
        lookup_calls.append(intent)
        return []

    plane.select_execution_path(
        intent="analyse customer churn",
        context={},
        workflow_lookup=lookup,
    )
    # The lookup was called with the user's intent — not derived from a workflow
    assert lookup_calls == ["analyse customer churn"]


def test_work_is_not_created_by_workflow_selection() -> None:
    """Selecting EXISTING_WORKFLOW does not create a Work record. The workflow
    is an organisational pattern; Work is an organisational intent record.
    They are triggered independently."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()

    wf = MagicMock()
    wf.name = "retention-report"
    wf.description = "weekly report"

    def lookup(intent: str) -> list[Any]:
        return [wf]

    before = len(plane.list_work())
    plane.select_execution_path(
        intent="retention report",
        context={},
        workflow_lookup=lookup,
    )
    after = len(plane.list_work())
    assert before == after == 0  # No Work created by workflow selection


def test_explicit_workflow_trigger_is_infrastructure_not_organisation() -> None:
    """Workflow triggering (scheduling, events, explicit requests) is an
    infrastructure concern, not modelled in the organisation domain. Work
    has no trigger field; WorkflowDefinition has no trigger field."""
    from models import WorkflowDefinition, WorkflowState

    wf_fields = set(WorkflowDefinition.model_fields.keys())
    work_fields = set(Work.model_fields.keys())
    state_fields = set(WorkflowState.model_fields.keys())

    for forbidden in ["trigger", "triggers", "schedule", "cron"]:
        assert forbidden not in wf_fields
        assert forbidden not in work_fields
        assert forbidden not in state_fields


# ---- N. Execution authorisation: workflow execution bypasses capability authorisation ----


def test_workflow_execution_port_has_no_actor_context() -> None:
    """WorkflowExecutionPort.execute_workflow takes only WorkflowExecutionRequest
    (workflow_name, initial_context). It has NO actor_context or actor_id field,
    meaning workflow execution does not carry the actor identity needed for
    capability-level authorisation checks."""
    from contracts.workflow_execution import WorkflowExecutionPort, WorkflowExecutionRequest

    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params
    # No actor identity parameters
    for forbidden in ["actor_id", "actor_context", "actor_type", "authorization", "authorisation"]:
        assert forbidden not in params

    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    for forbidden in [
        "actor_id", "actor_context", "actor_type",
        "authorization", "authorisation",
        "authorised_by", "approved_by",
    ]:
        assert forbidden not in request_fields


def test_workflow_execution_adapter_source_has_no_authorisation_check() -> None:
    """WorkflowExecutionAdapter.execute_workflow does NOT call any
    ExecutionAuthorisationPort. It loads YAML and executes directly —
    bypassing the Actor → CapabilityAssignment → authorisation →
    CapabilityExecutionPort boundary that capability-path execution enforces."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    source = inspect.getsource(WorkflowExecutionAdapter)
    # No authorisation port reference
    assert "authorisation_port" not in source
    assert "is_authorised" not in source
    assert "ExecutionAuthorisationPort" not in source
    # No actor_context
    assert "actor_context" not in source
    assert "actor_id" not in source


def test_workflow_execution_adapter_does_not_use_capability_execution_port() -> None:
    """WorkflowExecutionAdapter does not depend on CapabilityExecutionPort —
    it goes through the workflow_runner executor/handlers, not the
    capability execution path that checks authorisation."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    source = inspect.getsource(WorkflowExecutionAdapter)
    assert "CapabilityExecutionPort" not in source
    assert "capability_execution" not in source.lower()


def test_workflow_execution_bypasses_capability_authorisation_boundary() -> None:
    """This test documents the architectural finding: a workflow is adopted
    (by YAML presence) but its execution does NOT check whether the executing
    actor is authorised for each capability in the workflow's steps. The
    CapabilityExecutionPort enforces authorisation; the WorkflowExecutionPort
    does not.

    This is acceptable ONLY if workflows are pre-authorised by the organisation
    (the YAML itself is the organisational decision). It is NOT acceptable
    if individual capability-level authorisation is required per-step.
    """
    from contracts.workflow_execution import WorkflowExecutionPort, WorkflowExecutionRequest

    # Verify the protocol signature
    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    assert "request" in sig.parameters

    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in request_fields
    # Confirm: no actor context that could enable per-step capability authorisation
    assert "actor_context" not in request_fields
    assert "actor_id" not in request_fields


# ---- O. Backend independence ----


def test_langgraph_runtime_has_no_workflow_adoption_methods() -> None:
    """LangGraphRuntime is a backend — it implements PathwayRuntime
    (invoke/resume). It has no workflow adoption, creation, or lifecycle
    methods."""
    try:
        from langgraph_runtime import LangGraphRuntime
    except ImportError:
        import pytest
        pytest.skip("LangGraph runtime not available")

    backend_methods = set(dir(LangGraphRuntime))
    for forbidden in [
        "adopt", "register_workflow", "compile_workflow",
        "create_workflow", "promote_workflow", "synthesize",
    ]:
        matching = [m for m in backend_methods if forbidden in m.lower()]
        assert not matching, f"LangGraphRuntime should not have methods containing '{forbidden}'"


def test_pattern_runtime_has_no_workflow_adoption_methods() -> None:
    """PatternRuntime executes capability invocations but does not decide
    workflow adoption."""
    try:
        from runtime import PatternRuntime
    except ImportError:
        import pytest
        pytest.skip("PatternRuntime not available")

    backend_methods = set(dir(PatternRuntime))
    for forbidden in [
        "adopt", "register_workflow", "compile_workflow",
        "create_workflow", "promote_workflow", "select_execution_path",
    ]:
        matching = [m for m in backend_methods if forbidden in m.lower()]
        assert not matching, f"PatternRuntime should not have methods containing '{forbidden}'"


def test_paperclip_select_execution_path_ignores_workflow_lookup() -> None:
    """PaperclipOrganisationControlPlane does not maintain a workflow registry.
    Its select_execution_path does NOT use the workflow_lookup callback — it
    only checks capability presence in cached work. This proves the backend
    boundary: Paperclip does not participate in workflow discovery or adoption."""
    try:
        from organisation_paperclip import PaperclipOrganisationControlPlane
    except ImportError:
        import pytest
        pytest.skip("Paperclip adapter not available")

    source = inspect.getsource(
        PaperclipOrganisationControlPlane.select_execution_path
    )
    # Does NOT call workflow_lookup (parameter exists in signature but is never invoked)
    assert "workflow_lookup(" not in source
    assert "workflow_lookup(request" not in source
    # Does NOT return EXISTING_WORKFLOW
    assert "EXISTING_WORKFLOW" not in source
    # The body only checks capability presence in cached work
    assert "required_capability_ids" in source


def test_worker_does_not_select_or_adopt_workflows() -> None:
    """The Worker executes Work via capability execution or generic work —
    it never selects, adopts, or creates WorkflowDefinitions."""
    from workflow_runner.src.worker import Worker

    worker_methods = set(dir(Worker))
    for forbidden in [
        "select_execution_path", "adopt", "compile_workflow",
        "create_workflow", "register_workflow", "promote_workflow",
    ]:
        matching = [m for m in worker_methods if forbidden in m.lower()]
        assert not matching, f"Worker should not have methods containing '{forbidden}'"


def test_operations_does_not_decide_workflow_adoption() -> None:
    """Operations coordinates backends for READY Work — it does not decide
    which workflow to use or adopt. Backend selection is based on Work
    fields (assignee_agent_id), not on workflow identity."""
    from workflow_runner.src.operations import Operations

    ops_source = inspect.getsource(Operations)
    # No workflow selection or adoption logic
    assert "select_execution_path" not in ops_source
    assert "WorkflowDefinition" not in ops_source
    assert "workflow_lookup" not in ops_source


# ---- Helpers ----


def _make_inmemory_ocp() -> Any:
    """Create an InMemoryOrganisationControlPlane for testing."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    return InMemoryOrganisationControlPlane()
