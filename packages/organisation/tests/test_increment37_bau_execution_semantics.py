"""
Architectural tests for Increment 37 — Workflow Boundary → BAU Execution Semantics.

Builds on Increment 36's evidence that WorkflowDefinition is sufficient,
workflow execution bypasses capability authorisation, and the two execution
paths are structurally separate. This increment investigates the boundary
between WorkflowDefinition, WorkflowState, Work, and BAU execution.

Tests below prove the established architectural facts. Tests already covered
by Increment 33 (execution boundary), 34 (evidence→adoption boundary),
35 (lifecycle/adoption), or 36 (execution authority) are NOT duplicated.
"""

from __future__ import annotations

import ast
import os

ORGANISATION_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "src"
))
WORKFLOW_RUNNER_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner"
))
WORKFLOW_RUNNER_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner", "src"
))
AI_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "ai", "src"
))


# ---- A. BAU Execution Call Graph ----


def test_workflow_execution_path_does_not_create_work() -> None:
    """The EXISTING_WORKFLOW path (_execute_workflow_response) does NOT call
    create_work, mark_ready, or any WorkManagementPort method."""
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_execute_workflow_response":
            func_source = ast.get_source_segment(source, node) or ""
            for forbidden in ["create_work", "mark_ready", "WorkManagementPort", "pickup"]:
                assert forbidden not in func_source, (
                    f"_execute_workflow_response should not reference '{forbidden}'"
                    " — workflow execution does not create Work"
                )
            break
    else:
        raise AssertionError("_execute_workflow_response not found")


def test_capability_path_creates_work() -> None:
    """CAPABILITY_PATH path (_delegate_work_response) DOES call create_work."""
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_delegate_work_response":
            func_source = ast.get_source_segment(source, node) or ""
            assert "create_work" in func_source, (
                "_delegate_work_response must call create_work — "
                "capability path creates Work"
            )
            break
    else:
        raise AssertionError("_delegate_work_response not found")


def test_workflow_execution_result_does_not_become_work_outcome() -> None:
    """WorkflowExecutionResult has no outcome, work_id, or work-related fields.

    It is an execution result, not an organisational outcome.
    """
    from contracts.workflow_execution import WorkflowExecutionResult

    fields = set(WorkflowExecutionResult.model_fields.keys())
    assert "status" in fields
    assert "workflow_name" in fields
    for forbidden in [
        "work_id", "work_ref", "outcome", "task_id", "job_id",
        "organisation_id", "accountable",
    ]:
        assert forbidden not in fields, (
            f"WorkflowExecutionResult should not have '{forbidden}'"
        )


def test_operations_does_not_execute_workflows() -> None:
    """Operations handles Work via execution backends (Worker, Paperclip).

    It does NOT call WorkflowExecutionPort, execute_workflow, or any
    workflow runner function."""
    ops_path = os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    with open(ops_path) as f:
        source = f.read()

    for forbidden in [
        "WorkflowExecutionPort", "execute_workflow", "WorkflowExecutionAdapter",
        "workflow_execution", "WorkflowDefinition",
    ]:
        assert forbidden not in source, (
            f"Operations should not reference '{forbidden}'"
            " — Operations executes Work, not workflows"
        )


# ---- B. WorkflowState vs Work ----


def test_workflow_state_has_no_work_reference() -> None:
    """WorkflowState has no work_id, work, or Work-related fields.

    Execution state does not reference organisational effort."""
    from workflow_runner.models import WorkflowState

    fields = set(WorkflowState.model_fields.keys())
    for forbidden in [
        "work_id", "work", "work_ref", "assignment", "assignee",
        "outcome", "accountable", "role_id",
    ]:
        assert forbidden not in fields, (
            f"WorkflowState should not have '{forbidden}'"
        )


def test_work_has_no_workflow_reference() -> None:
    """Work model has no workflow_id, workflow_name, or WorkflowDefinition reference.

    Organisational effort does not reference workflow execution."""
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in [
        "workflow_id", "workflow_name", "workflow_path", "workflow",
        "workflow_definition", "step_results", "execution_context",
    ]:
        assert forbidden not in fields, (
            f"Work should not have '{forbidden}'"
        )


def test_workflow_state_and_work_in_different_packages() -> None:
    """WorkflowState lives in workflow_runner, Work lives in organisation/role.

    They are in different packages with no import relationship."""
    from workflow_runner.models import WorkflowState

    from role import Work

    assert WorkflowState.__module__.startswith("workflow_runner")
    assert Work.__module__.startswith("role")

    # organisation package must not import workflow_runner models
    org_init = os.path.join(ORGANISATION_SRC, "__init__.py")
    if os.path.exists(org_init):
        with open(org_init) as f:
            org_init_source = f.read()
        for forbidden in ["WorkflowState", "WorkflowDefinition", "Step", "StepResult"]:
            assert forbidden not in org_init_source, (
                f"organisation __init__ should not import '{forbidden}'"
            )


def test_worker_has_no_workflow_reference() -> None:
    """Worker.execute handles Work via Worker methods only.

    It has no workflow/WorkflowDefinition handling."""
    worker_path = os.path.join(WORKFLOW_RUNNER_SRC, "worker.py")
    with open(worker_path) as f:
        source = f.read()

    for forbidden in [
        "WorkflowDefinition", "WorkflowState", "WorkflowExecutionPort",
        "execute_workflow", "workflow_execution",
    ]:
        assert forbidden not in source, (
            f"Worker should not reference '{forbidden}'"
        )


# ---- C. Who Creates What ----


def test_work_is_created_by_chat_not_workflow() -> None:
    """Work is created by chat service's create_work calls (CAPABILITY_PATH,
    NEW_CAPABILITY_REQUIRED, HUMAN_TEAM_INVESTIGATION). Not by workflow execution."""
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()
    tree = ast.parse(source)

    # Find all create_work calls
    create_work_locations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "create_work":
                create_work_locations.append(node.lineno)

    assert len(create_work_locations) > 0, "chat.py should have create_work calls"

    # _execute_workflow_response must NOT have create_work
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_execute_workflow_response":
            func_source = ast.get_source_segment(source, node) or ""
            assert "create_work" not in func_source
            break


def test_workflow_state_is_created_by_executor() -> None:
    """WorkflowState is created by create_workflow_state in executor/API.

    Not by Work creation, Worker, or Operations."""
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        source = f.read()

    assert "create_workflow_state" in source, (
        "executor should create WorkflowState"
    )

    worker_path = os.path.join(WORKFLOW_RUNNER_SRC, "worker.py")
    with open(worker_path) as f:
        worker_source = f.read()
    assert "WorkflowState" not in worker_source

    ops_path = os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    with open(ops_path) as f:
        ops_source = f.read()
    assert "WorkflowState" not in ops_source


def test_operations_selects_backend_by_assignee_not_workflow() -> None:
    """Operations._select_backend uses backend.can_handle(work) which
    checks assignee_agent_id — not workflow association."""
    import re as _re
    ops_path = os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    with open(ops_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_select_backend":
            func_source = ast.get_source_segment(source, node) or ""
            assert "can_handle" in func_source
            assert "workflow" not in func_source.lower()
            break
    else:
        raise AssertionError("_select_backend not found")

    # assignee_agent_id is checked in backend can_handle methods
    assert _re.search(r"\bassignee_agent_id\b", source)
    # _select_backend itself does not reference workflow
    assert "WorkflowExecutionPort" not in source
    assert "execute_workflow" not in source


# ---- D. BAU Semantics ----


def test_bau_work_type_is_classification_not_entity() -> None:
    """'bau' is a Work.work_type string value, not a separate entity or concept.

    No BAU entity, BAU class, or BAU module should exist."""
    from role import Work

    # Work.work_type defaults to "bau" — it's a classification string
    assert Work.model_fields["work_type"].default == "bau"

    # No BAU entity concept exists in organisation package
    org_src = os.path.join(ORGANISATION_SRC)
    for root, dirs, files in os.walk(org_src):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath) as fh:
                    content = fh.read()
                if "class BAU" in content or "class BAUEntity" in content:
                    assert False, f"BAU entity found in {fpath}"


def test_existing_workflow_does_not_require_work() -> None:
    """OCP.select_execution_path can return EXISTING_WORKFLOW without
    any Work being created. The workflow exists independently of Work."""
    ocp_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(ocp_path) as f:
        source = f.read()

    # select_execution_path returns EXISTING_WORKFLOW based on workflow_lookup
    assert "EXISTING_WORKFLOW" in source
    # It does NOT create Work
    assert "create_work" not in source
    assert "mark_ready" not in source


# ---- E. Evidence and Outcome ----


def test_workflow_execution_does_not_record_invocation() -> None:
    """Workflow execution path (WorkflowExecutionAdapter + executor) does NOT
    call InvocationRecorder.record_invocation. Capability execution does."""
    adapter_path = os.path.join(WORKFLOW_RUNNER_SRC, "adapters", "workflow_execution_adapter.py")
    with open(adapter_path) as f:
        adapter_source = f.read()
    assert "record_invocation" not in adapter_source
    assert "InvocationRecorder" not in adapter_source

    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        executor_source = f.read()
    assert "record_invocation" not in executor_source
    assert "InvocationRecorder" not in executor_source


def test_capability_execution_records_invocation() -> None:
    """Contrast: CapabilityExecutionAdapter DOES call InvocationRecorder.

    This proves the two paths are deliberately different in evidence handling."""
    cap_adapter_path = os.path.join(
        WORKFLOW_RUNNER_SRC, "adapters", "capability_execution_adapter.py"
    )
    with open(cap_adapter_path) as f:
        source = f.read()
    assert "record_invocation" in source
    assert "InvocationRecorder" in source


def test_workflow_state_step_results_are_execution_telemetry() -> None:
    """WorkflowState.step_results contains StepResult objects with execution
    data (output, error, duration). It does not contain organisational evidence."""
    from workflow_runner.models import StepResult

    fields = set(StepResult.model_fields.keys())
    assert "step_name" in fields
    assert "step_type" in fields
    assert "status" in fields
    assert "output" in fields
    assert "error" in fields
    assert "duration_seconds" in fields
    for forbidden in [
        "work_id", "outcome", "evidence", "author", "approval",
    ]:
        assert forbidden not in fields, (
            f"StepResult should not have '{forbidden}'"
        )


# ---- F. Failure Ownership ----


def test_workflow_failure_does_not_transition_work() -> None:
    """When a workflow fails, no Work is created or transitioned.

    Workflow failure is contained in WorkflowState."""
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        source = f.read()

    # Executor handles failure internally (fail_workflow)
    assert "fail_workflow" in source
    # Executor does NOT reference Work creation or transitions
    import re as _re
    for forbidden_pattern in [
        _re.compile(r"\bcreate_work\b"),
        _re.compile(r"\bmark_ready\b"),
        _re.compile(r"\bcomplete_work\b"),
        _re.compile(r"\bfail_work\b"),
    ]:
        assert not forbidden_pattern.search(source), (
            f"Executor should not match '{forbidden_pattern.pattern}'"
            " — workflow failure is not a Work event"
        )


def test_work_failure_records_outcome() -> None:
    """When Work fails, Operations records the outcome via fail_work.

    Work failure is an organisational event with consequence."""
    ops_path = os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    with open(ops_path) as f:
        source = f.read()

    # Operations handles Work failure via complete_work or fail_work
    assert "complete_work" in source or "fail_work" in source

    # Worker.execute catches exceptions and returns failed result
    worker_path = os.path.join(WORKFLOW_RUNNER_SRC, "worker.py")
    with open(worker_path) as f:
        worker_source = f.read()
    assert "status" in worker_source and "failed" in worker_source


# ---- G. Execution Context Boundaries ----


def test_workflow_definition_has_no_organisational_fields() -> None:
    """WorkflowDefinition has only execution-relevant fields (steps, role, etc.).

    No organisational fields (accountability, assignment, criteria)."""
    from workflow_runner.models import WorkflowDefinition

    fields = set(WorkflowDefinition.model_fields.keys())
    for forbidden in [
        "accountable_role_id", "assignee", "assignee_actor_id",
        "required_capability_ids", "acceptance_criteria",
        "outcome", "work_type", "priority", "constraints",
    ]:
        assert forbidden not in fields, (
            f"WorkflowDefinition should not have '{forbidden}'"
        )

    # WorkflowDefinition has execution-relevant fields
    assert "steps" in fields
    assert "role" in fields


def test_work_has_no_execution_state_fields() -> None:
    """Work has no execution state fields (step_results, current_step, context).

    It has outcome (result) but not execution progress."""
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in [
        "step_results", "current_step", "current_step_index",
        "workflow_id", "workflow_path", "execution_progress",
    ]:
        assert forbidden not in fields, (
            f"Work should not have '{forbidden}'"
        )

    # Work has outcome ( organisational) but not execution state
    assert "outcome" in fields
    assert "status" in fields


def test_workflow_execution_request_has_no_work_or_actor_fields() -> None:
    """WorkflowExecutionRequest has neither Work references nor Actor context.

    Confirms the execution request is minimal and execution-layer only."""
    from contracts.workflow_execution import WorkflowExecutionRequest

    fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in fields
    assert "initial_context" in fields
    assert "role_override" in fields
    for forbidden in [
        "work_id", "workflow_id", "actor_id", "actor_context", "actor_type",
        "user_id", "principal", "required_capability_ids",
    ]:
        assert forbidden not in fields, (
            f"WorkflowExecutionRequest should not have '{forbidden}'"
        )


# ---- H. Innovation → BAU Transition ----


def test_capability_development_workflow_relationship() -> None:
    """Capability development Work (work_type='capability_development') does
    NOT reference a workflow — it creates a Capability, which may later
    become a workflow. The relationship is indirect."""
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_new_capability_required_response":
            func_source = ast.get_source_segment(source, node) or ""
            # Creates Work with work_type="capability_development"
            assert "capability_development" in func_source
            # Does NOT reference a workflow
            assert "workflow" not in func_source.lower()
            break
    else:
        raise AssertionError("_handle_new_capability_required_response not found")


def test_ocp_selects_workflow_or_capability_not_both() -> None:
    """OCP.select_execution_path returns EXISTING_WORKFLOW OR CAPABILITY_PATH
    — they are alternatives, not a sequence. A request takes ONE path."""
    ocp_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(ocp_path) as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "select_execution_path":
            func_source = ast.get_source_segment(source, node) or ""
            # Returns EXISTING_WORKFLOW first (workflow found)
            assert "EXISTING_WORKFLOW" in func_source
            # Otherwise falls through to CAPABILITY_PATH
            assert "CAPABILITY_PATH" in func_source
            # Does NOT execute both — returns one result
            assert "execute_workflow" not in func_source
            break
    else:
        raise AssertionError("select_execution_path not found")
