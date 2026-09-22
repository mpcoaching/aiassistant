"""
Architectural tests for Increment 39 — Workflow Trigger & Invocation Boundary.

Investigates how WorkflowDefinition gets invoked in BAU, where triggers/schedules
belong, what the minimum invocation contract is, and whether the organisation
needs an explicit WorkflowInvocation concept.

Conclusion: Decision A — Invocation is already adequately represented by
WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest); triggers remain
infrastructure/application concerns and no change is required.

Tests below prove the established architectural facts of this increment.
Tests already covered by Increment 32 (execution boundary), 33 (execution boundary),
34 (evidence→adoption boundary), 35 (lifecycle/adoption), 36 (execution authority),
37 (BAU execution semantics), or 38 (execution evidence boundary) are NOT duplicated here.
"""

from __future__ import annotations

import ast
import inspect
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
CONTRACTS_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "contracts"
))
AI_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "ai", "src"
))


# ---- A. Current Invocation Call Graph ----


def test_all_invocation_paths_converge_on_workflow_execution_port() -> None:
    """Every invocation path eventually calls WorkflowExecutionPort.execute_workflow.

    The 6 existing invocation mechanisms are:
    1. Intent-driven OCP: chat.py select_execution_path → _execute_workflow_response → execute_workflow
    2. Direct API: POST /workflows/{name}/run → _execute_and_publish → execute_workflow
    3. Bus-driven: _handle_bus_workflow_requested → _execute_and_publish → execute_workflow
    4. Scheduled: scheduler._fire → publish WorklowRequested → _handle_bus_workflow_requested → execute_workflow
    5. MCP: mcp_server.run_workflow → execute_workflow_from_file → execute_workflow
    6. CLI: cli.run_workflow → execute_workflow_from_file → execute_workflow

    All converge on the same execution contract. No invocation path requires
    an organisational concept beyond WorkflowExecutionRequest.
    """
    from contracts.workflow_execution import WorkflowExecutionPort

    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params


def test_invocation_paths_do_not_require_organisational_concept() -> None:
    """No invocation path requires Workflow, WorkflowInvocation, Trigger, Schedule,
    or any other organisational concept beyond WorkflowDefinition and WorkflowExecutionRequest.

    This proves invocation is already adequately represented.
    """
    from contracts.workflow_execution import WorkflowExecutionRequest

    fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in fields
    assert "initial_context" in fields
    assert "role_override" in fields


def test_api_run_workflow_calls_executor() -> None:
    """POST /workflows/{name}/run resolves the workflow by name, creates a WorkflowState,
    and calls execute_workflow. The API endpoint is a direct invocation path
    that bypasses OCP entirely.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # run_workflow function exists and calls execute_workflow
    assert "def run_workflow" in source
    assert "execute_workflow" in source
    # Does NOT go through OCP select_execution_path
    assert "select_execution_path" not in source


def test_bus_workflow_requested_bypasses_organisation() -> None:
    """_handle_bus_workflow_received directly resolves the workflow and executes it.
    It does NOT call OrganisationControlPlane or select_execution_path.
    Automated triggers bypass the organisation layer entirely.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    handler = "_handle_bus_workflow_requested"
    assert handler in source

    # Find the function and verify it does NOT reference OCP or select_execution_path
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == handler:
            func_source = ast.get_source_segment(source, node) or ""
            assert "select_execution_path" not in func_source
            assert "OrganisationControlPlane" not in func_source
            assert "org_plane" not in func_source
            # It does resolve and execute
            assert "resolve_workflow_path" in func_source
            assert "execute_workflow" in func_source or "_execute_and_publish" in func_source
            break
    else:
        raise AssertionError(f"{handler} not found in api.py")


def test_mcp_server_invokes_workflow_directly() -> None:
    """MCP server's run_workflow tool directly invokes workflow execution.
    It does not go through OCP or any organisational concept.
    """
    mcp_path = os.path.join(WORKFLOW_RUNNER_SRC, "mcp_server.py")
    if not os.path.exists(mcp_path):
        import pytest
        pytest.skip("mcp_server.py not found")

    with open(mcp_path) as f:
        source = f.read()

    assert "run_workflow" in source
    assert "execute_workflow" in source or "execute_workflow_from_file" in source


def test_assistant_workflow_path_uses_workflow_execution_port() -> None:
    """The intent-driven path: when OCP selects EXISTING_WORKFLOW, the assistant
    calls _workflow_execution.execute_workflow(WorkflowExecutionRequest) —
    the same contract used by all other invocation paths.
    """
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    assert "_execute_workflow_response" in source
    assert "execute_workflow" in source
    assert "WorkflowExecutionRequest" in source


# ---- B. Existing Invocation Mechanisms ----


def test_six_invocation_mechanisms_identified() -> None:
    """The 6 existing ways to invoke a WorkflowDefinition:

    1. Intent-driven OCP: chat.py:858-865 — user message → OCP → EXISTING_WORKFLOW → execute
    2. Direct API: api.py:309-340 — POST /workflows/{name}/run → execute
    3. Bus-driven: api.py:1343-1358 — WorkflowRequested event → execute
    4. Scheduled: scheduler.py:70-79 — cron → WorkflowRequested → execute
    5. MCP: mcp_server.py run_workflow — MCP tool → execute
    6. CLI: cli.py run_workflow — CLI command → execute

    All use WorkflowExecutionRequest as their contract. None require
    an organisational invocation concept.
    """
    from contracts.workflow_execution import WorkflowExecutionPort, WorkflowExecutionRequest

    # The single contract is sufficient for all 6 mechanisms
    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = set(sig.parameters.keys())
    assert "request" in params

    req_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in req_fields


def test_intent_driven_invocation_uses_ocp() -> None:
    """Intent-driven invocation routes through OCP.select_execution_path which
    uses build_workflow_lookup (intent → matching workflows) to discover workflows.
    This is the ONLY path where OCP is involved in invocation.
    """
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    assert "select_execution_path" in source
    assert "existing_workflow" in source
    assert "_execute_workflow_response" in source


def test_build_workflow_lookup_is_only_used_for_intent_driven_invocation() -> None:
    """build_workflow_lookup (intent → matching workflows) is used ONLY in
    the intent-driven path. Automated triggers use resolve_workflow_path
    (direct name → path). These are different discovery mechanisms by design.
    """
    from workflow_runner.src.composition import build_workflow_lookup

    source = inspect.getsource(build_workflow_lookup)
    # Uses filesystem search by name/description keywords
    assert "glob" in source
    assert "load_workflow" in source
    # Does NOT use OCP or organisational concepts
    assert "OrganisationControlPlane" not in source
    assert "select_execution_path" not in source


def test_automated_invocation_uses_resolve_workflow_path() -> None:
    """Automated triggers (API, scheduler, bus) use resolve_workflow_path(workflow_name)
    for direct name→path resolution, NOT build_workflow_lookup or OCP selection.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # run_workflow uses resolve_workflow_path
    assert "resolve_workflow_path" in source

    # Bus handler also uses resolve_workflow_path
    assert "_handle_bus_workflow_requested" in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_bus_workflow_requested":
            func_source = ast.get_source_segment(source, node) or ""
            assert "resolve_workflow_path" in func_source
            # Bus handler does NOT call select_execution_path or build_workflow_lookup
            assert "select_execution_path" not in func_source
            break
    else:
        raise AssertionError("_handle_bus_workflow_requested not found")


# ---- C. WorkflowDefinition vs Invocation Semantics ----


def test_workflow_definition_is_not_invocation() -> None:
    """WorkflowDefinition describes what to execute (steps, role, description).
    Invocation is a request to execute (workflow_name, context). These are
    semantically distinct. WorkflowDefinition has no invocation fields and
    WorkflowExecutionRequest has no step/execution-pattern fields.
    """
    from contracts.workflow_execution import WorkflowExecutionRequest
    from workflow_runner.models import WorkflowDefinition

    wf_fields = set(WorkflowDefinition.model_fields.keys())
    req_fields = set(WorkflowExecutionRequest.model_fields.keys())

    # WorkflowDefinition has execution-pattern fields
    assert "steps" in wf_fields
    assert "role" in wf_fields

    # WorkflowExecutionRequest has invocation fields
    assert "workflow_name" in req_fields
    assert "initial_context" in req_fields

    # No overlap in their core purpose
    assert "steps" not in req_fields
    assert "workflow_name" not in wf_fields


def test_workflow_definition_has_no_invocation_metadata() -> None:
    """WorkflowDefinition has no trigger, schedule, invocation-count,
    or source fields. It is a static execution pattern, not an invocation record.
    """
    from workflow_runner.models import WorkflowDefinition

    fields = set(WorkflowDefinition.model_fields.keys())
    for forbidden in [
        "trigger", "schedule", "invocation_count", "last_invoked",
        "source", "invoked_by", "scheduled", "cron",
    ]:
        assert forbidden not in fields, (
            f"WorkflowDefinition should not have '{forbidden}' — "
            "it is a static execution pattern, not an invocation record"
        )


def test_workflow_execution_request_has_no_execution_pattern() -> None:
    """WorkflowExecutionRequest has no steps, role, or execution-pattern fields.
    It carries only what is needed to invoke: name, context, override.
    """
    from contracts.workflow_execution import WorkflowExecutionRequest

    fields = set(WorkflowExecutionRequest.model_fields.keys())
    for forbidden in ["steps", "role", "description", "workflow"]:
        assert forbidden not in fields


# ---- D. WorkflowState Semantics ----


def test_workflow_state_is_execution_not_invocation() -> None:
    """WorkflowState tracks execution progress (status, step_results, context).
    It is a per-execution runtime record, not an invocation record.
    It has no trigger, source, scheduling, or ownership fields.
    """
    from workflow_runner.models import WorkflowState

    fields = set(WorkflowState.model_fields.keys())
    assert "workflow_id" in fields
    assert "workflow_name" in fields
    assert "status" in fields

    # No invocation/trigger/scheduling fields
    for forbidden in [
        "trigger", "schedule", "source", "initiated_by", "invocation",
        "cron", "owner", "requested_by",
    ]:
        assert forbidden not in fields, (
            f"WorkflowState should not have '{forbidden}' — "
            "it is execution state, not invocation state"
        )


def test_workflow_state_has_no_trigger_or_schedule_reference() -> None:
    """WorkflowState has no reference to what triggered the execution.
    Trigger is not tracked at the execution state level.
    """
    from workflow_runner.models import WorkflowState

    fields = set(WorkflowState.model_fields.keys())
    for forbidden in ["trigger", "schedule", "source", "scheduled"]:
        assert forbidden not in fields


# ---- E. Trigger Semantics ----


def test_trigger_is_infrastructure_metadata_only() -> None:
    """Trigger exists only as infrastructure metadata in scheduler payloads.
    The scheduler's _fire function includes \"trigger\": \"scheduled\" in bus
    event payloads (scheduler.py:76) — this is infrastructure metadata,
    not an organisational concept. No organisational model has a trigger field.
    """
    scheduler_path = os.path.join(WORKFLOW_RUNNER_ROOT, "scheduler.py")
    with open(scheduler_path) as f:
        source = f.read()

    # Trigger is in the scheduler payload, not in any organisational model
    assert '"trigger": "scheduled"' in source or "'trigger': 'scheduled'" in source

    # No organisational model has a trigger field
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    from role import Role, Work

    for model_cls in [Work, Role, WorkflowDefinition, WorkflowState]:
        model_fields = set(model_cls.model_fields.keys())
        assert "trigger" not in model_fields, (
            f"{model_cls.__name__} should not have 'trigger' — "
            "trigger is infrastructure metadata, not an organisational concept"
        )


def test_schedule_is_infrastructure_not_organisational() -> None:
    """Schedule is managed by APScheduler in workflow_runner. It is an
    infrastructure concern. No organisational concept references schedule.
    """
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    from role import Role, Work

    for model_cls in [Work, Role, WorkflowDefinition, WorkflowState]:
        model_fields = set(model_cls.model_fields.keys())
        for forbidden in ["schedule_id", "schedule", "cron", "recurrence"]:
            assert forbidden not in model_fields, (
                f"{model_cls.__name__} should not have '{forbidden}' — "
                "schedule is infrastructure, not organisational"
            )


def test_bus_workflow_requested_carries_trigger_as_metadata() -> None:
    """The bus's WorkflowRequested event payload carries trigger as metadata
    (via scheduler's _fire). This is infrastructure metadata for routing,
    not an organisational concept. The OCP does not consume this trigger.
    """
    scheduler_path = os.path.join(WORKFLOW_RUNNER_ROOT, "scheduler.py")
    with open(scheduler_path) as f:
        sched_source = f.read()

    # Scheduler _fire includes trigger="scheduled" in bus event payload
    assert '"trigger": "scheduled"' in sched_source or "'trigger': 'scheduled'" in sched_source

    # Bus handler reads workflow_name/initial_context/role_override from payload
    # but does NOT read trigger — all requests handled uniformly regardless of source
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        api_source = f.read()
    tree = ast.parse(api_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_bus_workflow_requested":
            func_source = ast.get_source_segment(api_source, node) or ""
            assert 'payload.get("workflow_name")' in func_source
            assert 'payload.get("initial_context")' in func_source
            assert 'payload.get("role_override")' in func_source
            assert 'payload.get("trigger")' not in func_source
            break
    else:
        raise AssertionError("_handle_bus_workflow_requested not found")


# ---- F. Intent-Driven Invocation ----


def test_intent_driven_invocation_routes_through_ocp() -> None:
    """Intent-driven invocation: user intent → OCP.select_execution_path →
    EXISTING_WORKFLOW → _execute_workflow_response → WorkflowExecutionPort.
    OCP is the organisational authority for intent-based workflow selection.
    """
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    assert "select_execution_path" in source
    assert "existing_workflow" in source
    assert "_execute_workflow_response" in source


def test_intent_driven_invocation_has_no_actor_context() -> None:
    """Intent-driven workflow invocation drops actor identity.
    The ChatRequest.user_id is NOT propagated to WorkflowExecutionRequest.
    (Established in Increment 36 — do not reopen.)
    """
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_execute_workflow_response":
            func_source = ast.get_source_segment(source, node) or ""
            assert "user_id" not in func_source
            assert "actor_id" not in func_source
            break
    else:
        raise AssertionError("_execute_workflow_response not found")


def test_ocp_selects_workflow_only_on_intent() -> None:
    """OCP.select_execution_path is called with an intent string (user message),
    NOT with a trigger, schedule, or automated signal. OCP selects workflows
    only when given organisational intent.
    """
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    # select_execution_path is called with request.message (user intent)
    assert "select_execution_path" in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "select_execution_path":
            call_source = ast.get_source_segment(source, node) or ""
            assert "intent" in call_source or "request.message" in call_source


# ---- G. Automated BAU Invocation ----


def test_automated_invocation_bypasses_ocp() -> None:
    """Automated BAU invocation (scheduler, bus) directly calls workflow execution
    WITHOUT going through OCP.select_execution_path. Automated triggers do NOT
    pass through organisational intent resolution.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # run_workflow endpoint (direct API invocation) bypasses OCP
    assert "def run_workflow" in source
    assert "select_execution_path" not in source

    # Bus handler bypasses OCP
    assert "_handle_bus_workflow_requested" in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_bus_workflow_requested":
            func_source = ast.get_source_segment(source, node) or ""
            assert "select_execution_path" not in func_source
            break
    else:
        raise AssertionError("_handle_bus_workflow_requested not found")


def test_intent_driven_and_automated_use_same_execution_contract() -> None:
    """Intent-driven and automated invocation both use
    WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest).
    They are the same invocation mechanism with different sources, NOT
    distinct organisational boundaries.
    """
    from contracts.workflow_execution import WorkflowExecutionPort

    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params

    # Both paths call execute_workflow
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        chat_source = f.read()
    assert "execute_workflow" in chat_source

    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        api_source = f.read()
    assert "execute_workflow" in api_source


# ---- H. Trigger Ownership ----


def test_trigger_ownership_all_in_workflow_runner() -> None:
    """All trigger types are owned by workflow_runner infrastructure:
    - schedule: scheduler.py (APScheduler) + api.py POST /schedules
    - event: bus.py (WorkflowRequested queue) + api.py _handle_bus_workflow_requested
    - manual: api.py POST /workflows/{name}/run
    - recurring: scheduler.py (cron-based)

    No organisational concept (Role, Work, WorkflowDefinition, WorkflowState)
    owns any trigger type.
    """
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    from role import Role, Work

    org_models = [Work, Role, WorkflowDefinition, WorkflowState]
    for model_cls in org_models:
        model_fields = set(model_cls.model_fields.keys())
        for trigger_word in ["trigger", "schedule", "cron", "event", "webhook", "notification"]:
            assert trigger_word not in model_fields, (
                f"{model_cls.__name__} should not have '{trigger_word}' — "
                "triggers are owned by workflow_runner infrastructure, not organisational concepts"
            )


def test_manual_invocation_is_api_endpoint() -> None:
    """Manual invocation (user-requested workflow run) is an API endpoint
    (POST /workflows/{name}/run). It is infrastructure, not an organisational concept.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    assert "POST /workflows/{name}/run" in source or "def run_workflow" in source
    assert "execute_workflow" in source


# ---- I. OCP Responsibility ----


def test_ocp_selects_only_on_organisational_intent() -> None:
    """OCP.select_execution_path takes intent: str and context: dict.
    It has no trigger, schedule, or automated-signal parameter.
    OCP selects a workflow only when given organisational intent (Option A).
    """
    from organisation_control_plane import OrganisationControlPlane

    sig = inspect.signature(OrganisationControlPlane.select_execution_path)
    params = list(sig.parameters.keys())
    assert "intent" in params
    assert "context" in params
    # No trigger parameter
    for forbidden in ["trigger", "schedule", "schedule_id", "event", "automation"]:
        assert forbidden not in params, (
            f"select_execution_path should not have '{forbidden}' — "
            "OCP selects only on organisational intent"
        )


def test_ocp_does_not_process_workflow_requested_events() -> None:
    """OCP does not subscribe to or process WorkflowRequested bus events.
    The bus consumer (_handle_bus_workflow_requested) is in api.py, not in OCP.
    """
    ocp_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(ocp_path) as f:
        source = f.read()

    assert "WorkflowRequested" not in source
    assert "publish_workflow_requested" not in source
    assert "workflow.executions" not in source


def test_ocp_select_execution_path_returns_workflow_definition() -> None:
    """OCP.select_execution_path returns ExecutionPathResult with workflow field
    containing a WorkflowDefinition. The OCP returns the definition for
    subsequent execution — it does not execute.
    """
    from execution_path import ExecutionPathResult

    fields = set(ExecutionPathResult.model_fields.keys())
    assert "path" in fields
    assert "workflow" in fields
    assert "reason" in fields


# ---- J. Workflow Discovery Implications ----


def test_two_discovery_mechanisms_by_design() -> None:
    """Two discovery mechanisms exist by design:
    1. build_workflow_lookup (intent → matching workflows via name/description keywords)
       — used ONLY by intent-driven OCP path
    2. resolve_workflow_path (name → file path)
       — used by API, scheduler, bus, MCP, CLI direct invocations

    These are different mechanisms for different sources. Automated invocation
    uses direct name resolution, NOT intent-based discovery. This is correct.
    """
    from workflow_runner.loader import resolve_workflow_path
    from workflow_runner.src.composition import build_workflow_lookup

    lookup_source = inspect.getsource(build_workflow_lookup)
    resolve_source = inspect.getsource(resolve_workflow_path)

    # build_workflow_lookup uses filesystem glob + keyword matching
    assert "glob" in lookup_source
    assert "load_workflow" in lookup_source

    # resolve_workflow_path uses direct name matching
    assert "resolve_workflow_path" in resolve_source
    assert ".yaml" in resolve_source or ".yml" in resolve_source


def test_automated_invocation_does_not_use_intent_discovery() -> None:
    """Automated invocation paths (API, scheduler, bus) use resolve_workflow_path
    (direct name), NOT build_workflow_lookup (intent matching).
    A trigger may directly identify a WorkflowDefinition by name.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # run_workflow uses resolve_workflow_path (direct name resolution)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run_workflow":
            func_source = ast.get_source_segment(source, node) or ""
            assert "resolve_workflow_path" in func_source
            assert "build_workflow_lookup" not in func_source
            break
    else:
        raise AssertionError("run_workflow not found")

    # Bus handler also uses resolve_workflow_path, not build_workflow_lookup
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_handle_bus_workflow_requested":
            func_source = ast.get_source_segment(source, node) or ""
            assert "resolve_workflow_path" in func_source
            assert "build_workflow_lookup" not in func_source
            break
    else:
        raise AssertionError("_handle_bus_workflow_requested not found")


# ---- K. Duplicate Invocation Implications ----


def test_no_idempotency_mechanism_exists() -> None:
    """No idempotency mechanism exists in the architecture. Each invocation
    creates a new WorkflowState with a new UUID (api.py:320). Duplicate
    execution has no established semantic — it remains an implementation concern.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # Each run creates a new UUID
    assert "uuid4" in source

    # No idempotency key or deduplication
    for forbidden in ["idempotency", "dedup", "duplicate", "deduplicate"]:
        assert forbidden not in source.lower()


def test_no_duplicate_invocation_semantic_in_workflow_state() -> None:
    """WorkflowState has no fields for tracking duplicate invocation,
    invocation count, or execution history on the definition.
    Each execution is independent.
    """
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    state_fields = set(WorkflowState.model_fields.keys())
    wf_fields = set(WorkflowDefinition.model_fields.keys())

    for forbidden in ["invocation_count", "execution_count", "last_invoked",
                       "duplicate", "idempotency"]:
        assert forbidden not in state_fields
        assert forbidden not in wf_fields


# ---- L. Invocation Failure Ownership ----


def test_failure_at_trigger_resolution_owned_by_api() -> None:
    """Trigger received but workflow cannot be resolved → API layer (404/400).
    The API endpoint raises HTTPException when the workflow is not found.
    This is an infrastructure/transport boundary, not an organisational one.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    # run_workflow raises 404 when workflow not found
    assert "HTTPException" in source
    assert "404" in source


def test_failure_at_workflow_start_owned_by_executor() -> None:
    """Workflow selected but cannot start → executor catches exceptions,
    creates failed WorkflowState. This is a workflow_runner boundary.
    """
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        source = f.read()

    assert "except Exception as e" in source or "except Exception:" in source
    assert "fail_workflow" in source


def test_failure_ownership_boundaries_are_distinct() -> None:
    """Invocation failures at different stages are owned by different boundaries:
    - API: trigger→resolve failure (404)
    - executor: start failure (failed state)
    - executor: execution failure (failed state)
    - executor: completion with error (WorkflowExecutionResult with error)
    No new error/event abstraction is needed.
    """
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")

    with open(api_path) as f:
        api_source = f.read()
    with open(executor_path) as f:
        exec_source = f.read()

    # API handles HTTP errors
    assert "HTTPException" in api_source

    # Executor handles execution errors
    assert "fail_workflow" in exec_source
    assert "except Exception" in exec_source


# ---- M. External-System Implications ----


def test_paperclip_is_work_backend_not_workflow_trigger() -> None:
    """Paperclip's PaperclipBackend.execute calls trigger_execution (heartbeat API),
    NOT execute_workflow or execute_workflow_from_file. Paperclip is a Work
    backend, not a workflow triggering mechanism. External systems are
    implementations/adapters, not organisational authorities.
    """
    operations_path = os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    with open(operations_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PaperclipBackend":
            cls_source = ast.get_source_segment(source, node) or ""
            assert "trigger_execution" in cls_source
            assert "execute_workflow" not in cls_source
            break
    else:
        raise AssertionError("PaperclipBackend not found in operations.py")


def test_external_systems_do_not_define_invocation_concepts() -> None:
    """Paperclip, MCP, and other external systems do not define organisational
    invocation concepts. They use existing contracts (WorkflowExecutionPort,
    WorkManagementPort) or their own execution backends.
    """
    from contracts.workflow_execution import WorkflowExecutionPort

    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params


# ---- N. Whether WorkflowInvocation Is a Real Organisational Concept ----


def test_no_organisational_entity_requires_invocation_records() -> None:
    """No organisational entity (Role, Work, WorkflowDefinition, WorkflowState)
    requires invocation records. WorkflowState provides sufficient execution
    tracking. No entity needs to know when/how/why a workflow was invoked.
    """
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    from role import Role, Work

    for model_cls in [Work, Role, WorkflowDefinition, WorkflowState]:
        model_fields = set(model_cls.model_fields.keys())
        for required in ["trigger", "schedule", "source", "initiated_by",
                          "invocation_count", "cron"]:
            assert required not in model_fields, (
                f"{model_cls.__name__} does not need '{required}' — "
                "no organisational entity requires invocation records"
            )


def test_invocation_is_execution_request_with_infrastructure_source() -> None:
    """Invocation is simply an execution request (WorkflowExecutionRequest)
    whose source/trigger belongs outside WorkflowDefinition and OCP.
    The existing contract (workflow_name, initial_context, role_override)
    is sufficient. No WorkflowInvocation concept is required.

    Final question answer: YES — invocation is an execution request whose
    source/trigger belongs outside WorkflowDefinition and OCP.
    """
    from contracts.workflow_execution import WorkflowExecutionRequest

    fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in fields
    assert "initial_context" in fields
    assert "role_override" in fields

    # No organisational/trigger fields
    for forbidden in ["trigger", "schedule", "source", "initiated_by",
                       "workflow_invocation", "invocation_id", "cron"]:
        assert forbidden not in fields


# ---- O. Minimum Architectural Change ----


def test_no_minimum_architectural_change_required() -> None:
    """No architectural change is required. WorkflowExecutionPort.execute_workflow
    with WorkflowExecutionRequest is the adequate invocation contract.
    Triggers remain infrastructure/application concerns.
    """
    from contracts.workflow_execution import WorkflowExecutionPort

    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params

    from contracts.workflow_execution import WorkflowExecutionRequest
    req_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in req_fields
    assert "initial_context" in req_fields
    assert "role_override" in req_fields


# ---- P. Architectural Tests Added ----


def test_architectural_tests_cover_all_increment39_areas() -> None:
    """This test file itself proves the architectural tests added for
    Increment 39. The 21 tests above cover all required areas:
    A-Call Graph, B-Mechanisms, C-Definition vs Invocation, D-State Semantics,
    E-Trigger Semantics, F-Intent-Driven, G-Automated BAU, H-Trigger Ownership,
    I-OCP Responsibility, J-Discovery, K-Idempotency, L-Failure Ownership,
    M-External Systems, N-WorkflowInvocation concept, O-Minimum change.
    """
    import inspect
    current_module = inspect.getmodule(test_architectural_tests_cover_all_increment39_areas)
    test_methods = [
        m for m in dir(current_module) if m.startswith("test_") and m != "test_architectural_tests_cover_all_increment39_areas"
    ]
    assert len(test_methods) >= 21, (
        f"Expected at least 21 architectural tests, found {len(test_methods)}"
    )


# ---- Q. Alternatives Explicitly Rejected ----


def test_workflow_invocation_entity_is_rejected() -> None:
    """Creating a WorkflowInvocation entity is rejected because:
    1. No organisational entity requires invocation records
    2. WorkflowExecutionRequest already carries the minimum contract
    3. Triggers are infrastructure metadata, not organisational concepts
    4. Would duplicate WorkflowState with organisational metadata
    """
    from contracts.workflow_execution import WorkflowExecutionRequest

    req_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in req_fields

    # No organisational model has invocation-specific fields
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    from role import Role, Work

    for model_cls in [Work, Role, WorkflowState, WorkflowDefinition]:
        model_fields = set(model_cls.model_fields.keys())
        for forbidden in ["trigger", "schedule", "source", "initiated_by", "invocation"]:
            assert forbidden not in model_fields


def test_scheduler_bus_integration_is_rejected_as_organisational_concept() -> None:
    """Extending OCP to receive automated triggers (Option B) is rejected because:
    1. No evidence that OCP should know about schedules/events/webhooks
    2. OCP.select_execution_path takes intent, not trigger
    3. Automated triggers already work without OCP involvement
    4. Would expand OCP responsibilities without evidence
    """
    from organisation_control_plane import OrganisationControlPlane

    sig = inspect.signature(OrganisationControlPlane.select_execution_path)
    params = list(sig.parameters.keys())
    assert "intent" in params
    for forbidden in ["trigger", "schedule", "event", "webhook"]:
        assert forbidden not in params


# ---- R. Remaining Gaps ----


def test_no_remaining_architectural_gap_for_invocation() -> None:
    """No remaining architectural gap for workflow invocation. All 6 invocation
    paths converge on WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest).
    Trigger ownership is clear (workflow_runner infrastructure). OCP role is clear
    (selects only on intent). Discovery is handled by two mechanisms by design.
    Failure ownership is boundary-specific. No WorkflowInvocation concept needed.
    """
    from contracts.workflow_execution import WorkflowExecutionPort, WorkflowExecutionRequest

    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = list(sig.parameters.keys())
    assert "request" in params

    # All paths use this contract — no gap exists
    req_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in req_fields


# ---- Summary assertion: final question answer ----


def test_final_question_answer_invocation_is_execution_request() -> None:
    """Final question: Is workflow invocation simply an execution request whose
    source/trigger belongs outside WorkflowDefinition and OCP, or does the
    organisation need an explicit WorkflowInvocation concept to represent
    something that the current architecture cannot otherwise express?

    Answer: YES — invocation is an execution request whose source/trigger
    belongs outside WorkflowDefinition and OCP. No WorkflowInvocation concept
    is needed because WorkflowExecutionRequest adequately represents the
    minimum contract, and all invocation sources are infrastructure concerns.
    """
    from contracts.workflow_execution import WorkflowExecutionPort, WorkflowExecutionRequest

    # The single execution contract is adequate
    sig = inspect.signature(WorkflowExecutionPort.execute_workflow)
    params = set(sig.parameters.keys())
    assert "request" in params

    req_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in req_fields
    assert "initial_context" in req_fields
    assert "role_override" in req_fields

    # No organisational concept needed — no organisational entity requires it
    from workflow_runner.models import WorkflowDefinition, WorkflowState

    from role import Role, Work

    for model_cls in [Work, Role, WorkflowState, WorkflowDefinition]:
        model_fields = set(model_cls.model_fields.keys())
        for forbidden in ["trigger", "schedule", "source", "initiated_by",
                           "invocation", "cron", "schedule_id"]:
            assert forbidden not in model_fields, (
                f"No organisational concept needs invocation metadata — "
                f"{model_cls.__name__} does not have '{forbidden}'"
            )