"""
Architectural tests for Increment 36 — Workflow Execution Authority & BAU Boundary.

Builds on Increment 35's evidence that WorkflowDefinition is an execution
boundary object and that workflow execution bypasses capability authorisation.

This increment investigates whether that bypass is intentional or a gap,
and maps where Actor identity exists and disappears across the BAU
execution chain.

Tests below prove the *established* architectural decisions of this
increment. Tests already covered by Increment 32 (execution boundary),
33 (execution boundary), 34 (evidence→adoption boundary), or 35
(lifecycle/adoption) are NOT duplicated here.
"""

from __future__ import annotations

import ast
import inspect
import os
import re

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


# ---- A. Workflow execution call graph: no actor identity at any layer ----


def test_workflow_execution_contract_has_no_actor_fields() -> None:
    """WorkflowExecutionRequest carries neither actor_id nor actor_context.

    This is the entry contract for workflow execution. Its field set
    (workflow_name, initial_context, role_override) deliberately omits
    any actor identity, meaning the contract cannot carry provenance
    from the originating request through to execution.
    """
    from contracts.workflow_execution import WorkflowExecutionRequest

    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in request_fields
    assert "initial_context" in request_fields
    assert "role_override" in request_fields

    forbidden = [
        "actor_id", "actor_type", "actor_context",
        "user_id", "initiated_by", "principal",
    ]
    for field in forbidden:
        assert field not in request_fields, (
            f"WorkflowExecutionRequest should not have '{field}'"
        )


def test_workflow_execution_adapter_init_has_no_authorisation_port() -> None:
    """WorkflowExecutionAdapter.__init__ does not accept an authorisation
    port, unlike CapabilityExecutionAdapter which does.

    The composition root instantiates `WorkflowExecutionAdapter()` with
    no arguments — it has no wiring point for authorisation even if one
    were wanted later.
    """
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    sig = inspect.signature(WorkflowExecutionAdapter.__init__)
    params = set(sig.parameters.keys())
    # authorisation_port is a constructor param of CapabilityExecutionAdapter,
    # not WorkflowExecutionAdapter
    assert "authorisation_port" not in params
    assert "authorisation" not in " ".join(params).lower()


def test_workflow_adapter_execute_workflow_has_no_actor_param() -> None:
    """WorkflowExecutionAdapter.execute_workflow takes only a request
    object — no actor_context parameter."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    sig = inspect.signature(WorkflowExecutionAdapter.execute_workflow)
    params = set(sig.parameters.keys())
    assert "request" in params
    for forbidden in ["actor_id", "actor_context", "actor_type", "authorisation"]:
        assert forbidden not in params


def test_workflow_executor_signature_has_no_actor_or_recorder() -> None:
    """executor.execute_workflow has no actor_context or invocation_recorder
    parameter — it cannot record evidence or enforce actor identity."""
    from workflow_runner.executor import execute_workflow

    sig = inspect.signature(execute_workflow)
    params = set(sig.parameters.keys())
    for forbidden in ["actor_context", "actor_id", "invocation_recorder",
                      "authorisation_port", "actor_type"]:
        assert forbidden not in params


def test_skill_handler_has_no_actor_or_authorisation() -> None:
    """handle_skill_step takes only step, workflow, context, role_override.
    No actor identity is available to pass to the runtime."""
    from handlers.skill_handler import handle_skill_step

    sig = inspect.signature(handle_skill_step)
    params = set(sig.parameters.keys())
    assert "step" in params
    assert "workflow" in params
    assert "context" in params
    assert "role_override" in params
    for forbidden in ["actor_id", "actor_context", "actor_type",
                      "authorisation_port", "invocation_recorder"]:
        assert forbidden not in params


# ---- B. Capability execution boundary with authorisation (contrast) ----


def test_capability_execution_port_protocol_carries_actor_context() -> None:
    """CapabilityExecutionPort.execute explicitly requires actor_context,
    contrasting with WorkflowExecutionPort which has none. This proves
    the two execution paths are structurally different by design."""
    from contracts.capability_execution import CapabilityExecutionPort

    sig = inspect.signature(CapabilityExecutionPort.execute)
    params = list(sig.parameters.keys())
    assert "capability_id" in params
    assert "context" in params
    assert "actor_context" in params


def test_capability_execution_adapter_init_accepts_authorisation_port() -> None:
    """CapabilityExecutionAdapter.__init__ accepts execution_authorisation
    port — this is the authorisation-enforced path that workflow execution
    bypasses."""
    from workflow_runner.src.adapters.capability_execution_adapter import (
        CapabilityExecutionAdapter,
    )

    sig = inspect.signature(CapabilityExecutionAdapter.__init__)
    params = set(sig.parameters.keys())
    assert "authorisation_port" in params


def test_execution_authorisation_port_contract_checks_actor_and_capability() -> None:
    """ExecutionAuthorisationPort.is_authorised takes actor_id, actor_type,
    capability_id. This is the authorisation mechanism that the workflow
    execution path structurally cannot invoke."""
    from people_capability.src.execution_authorisation import (
        ExecutionAuthorisationPort,
    )

    sig = inspect.signature(ExecutionAuthorisationPort.is_authorised)
    params = list(sig.parameters.keys())
    assert "actor_id" in params
    assert "actor_type" in params
    assert "capability_id" in params


# ---- C. Workflow steps are skills, not capabilities (authority distinction) ----


def test_workflow_step_uses_is_skill_name_not_capability_id() -> None:
    """A workflow Step.uses references a skill name (loaded from YAML via
    the composer), not a capability_id. The workflow execution path never
    consults the CapabilityRegistry or CapabilityExecutionPort.

    This means the capability-level authorisation bypass is structural, not
    accidental: the workflow executor operates on a different abstraction
    (skills) than the capability execution path (capabilities).
    """
    from models import Step, StepType

    # A workflow step is typed SKILL/TOOL/WORKFLOW — there is no CAPABILITY type
    step_types = [t.value for t in StepType]
    for forbidden in ["capability", "cap"]:
        assert not any(forbidden in t.lower() for t in step_types), (
            f"StepType should not contain '{forbidden}' — workflow steps are "
            f"skills/tools/workflows, not capabilities"
        )

    # Verify Step.uses is a plain string name, not a capability reference
    assert "capability_id" not in Step.model_fields
    assert "uses" in Step.model_fields  # references a skill/tool/workflow name


def test_composer_resolves_skill_name_from_yaml_not_capability_registry() -> None:
    """compose_skill_prompt loads skill content from YAML files via
    _load_skill_content — it does NOT consult CapabilityRegistry.
    The skill name (step.uses) is a filesystem path key, not a capability_id."""
    from composer import compose_skill_prompt

    source = inspect.getsource(compose_skill_prompt)
    # Loads skill content from filesystem (YAML skill definitions)
    assert "_load_skill_content" in source
    # Does NOT reference capability registry
    assert "capability_registry" not in source.lower()
    assert "CapabilityExecutionPort" not in source
    assert "is_authorised" not in source


def test_workflow_executor_does_not_import_capability_execution_port() -> None:
    """The workflow executor (executor.py) does not import or reference
    CapabilityExecutionPort, CapabilityExecutionAdapter, or
    ExecutionAuthorisationPort. The workflow execution path is structurally
    separated from the capability authorisation boundary."""
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        source = f.read()

    for forbidden in [
        "CapabilityExecutionPort",
        "CapabilityExecutionAdapter",
        "ExecutionAuthorisationPort",
        "is_authorised",
        "record_invocation",
    ]:
        assert forbidden not in source, (
            f"executor.py should not reference '{forbidden}' — "
            "the workflow execution path must not cross the capability "
            "authorisation boundary"
        )


def test_skill_handler_does_not_record_invocation() -> None:
    """handle_skill_step calls runtime_client.run (LangGraph HTTP) but
    never records an invocation via InvocationRecorder. Skill execution
    through a workflow produces no capability telemetry/evidence."""
    from handlers.skill_handler import handle_skill_step

    source = inspect.getsource(handle_skill_step)
    assert "record_invocation" not in source
    assert "InvocationRecorder" not in source


# ---- D. Actor identity dropped at the BAU boundary (assistant) ----


def test_assistant_drops_user_identity_when_executing_workflow() -> None:
    """When ChatResult.path == 'existing_workflow', the assistant calls
    _execute_workflow_response which builds an ad-hoc WorkflowExecutionRequest
    with only workflow_name and initial_context={} — the ChatRequest.user_id
    is NOT propagated."""
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    # Find _execute_workflow_response method
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_execute_workflow_response":
            func_source = ast.get_source_segment(source, node) or ""
            # It builds an ad-hoc request without user_id/actor_id
            assert "user_id" not in func_source
            assert "actor_id" not in func_source
            assert "actor_context" not in func_source
            # It calls execute_workflow
            assert "execute_workflow" in func_source
            break
    else:
        raise AssertionError("_execute_workflow_response not found in chat.py")


def test_assistant_workflow_response_does_not_create_work() -> None:
    """The _execute_workflow_response method does not create a Work item
    — unlike the capability path which creates Work for execution.
    Workflow execution bypasses the Work/evidence lifecycle entirely."""
    chat_path = os.path.join(AI_SRC, "chat.py")
    with open(chat_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_execute_workflow_response":
            func_source = ast.get_source_segment(source, node) or ""
            assert "create_work" not in func_source
            assert "complete_work" not in func_source
            assert "fail_work" not in func_source
            break
    else:
        raise AssertionError("_execute_workflow_response not found in chat.py")


# ---- E. API-level actor absence ----


def test_api_run_workflow_has_no_actor_context() -> None:
    """The REST API POST /workflows/{name}/run endpoint does not accept
    or forward any actor identity. RunRequest schema has no actor fields."""
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()
        tree = ast.parse(source)

    # Find RunRequest class
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RunRequest":
            cls_source = ast.get_source_segment(source, node) or ""
            for forbidden in ["actor_id", "actor_context", "user_id", "actor_type"]:
                assert forbidden not in cls_source, (
                    f"RunRequest should not have '{forbidden}' — no actor context in API"
                )
            break
    else:
        raise AssertionError("RunRequest class not found in api.py")

    # Find run_workflow function
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_workflow":
            func_source = ast.get_source_segment(source, node) or ""
            for forbidden in ["actor_id", "actor_context", "user_id", "actor_type"]:
                assert forbidden not in func_source
            break
    else:
        raise AssertionError("run_workflow function not found in api.py")


def test_api_execute_and_publish_has_no_actor() -> None:
    """_execute_and_publish calls executor.execute_workflow with no
    actor context whatsoever."""
    api_path = os.path.join(WORKFLOW_RUNNER_ROOT, "api.py")
    with open(api_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_execute_and_publish":
            func_source = ast.get_source_segment(source, node) or ""
            for forbidden in ["actor_id", "actor_context", "user_id", "actor_type"]:
                assert forbidden not in func_source
            break
    else:
        raise AssertionError("_execute_and_publish not found in api.py")


# ---- F. MCP and scheduler also lack actor identity ----


def test_mcp_run_workflow_has_no_actor() -> None:
    """The MCP server's run_workflow tool signature has no actor context."""
    mcp_path = os.path.join(WORKFLOW_RUNNER_SRC, "mcp_server.py")
    if not os.path.exists(mcp_path):
        import pytest
        pytest.skip("mcp_server.py not found")

    with open(mcp_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_workflow":
            func_source = ast.get_source_segment(source, node) or ""
            assert "actor_id" not in func_source
            assert "actor_context" not in func_source
            assert "user_id" not in func_source
            assert "actor_type" not in func_source
            # It calls execute_workflow_from_file (the workflow executor)
            assert "execute_workflow" in func_source
            break
    else:
        raise AssertionError("run_workflow not found in mcp_server.py")


def test_scheduler_workflow_payload_has_no_actor() -> None:
    """The scheduler's _fire payload contains no actor/actor_id/principal —
    system-triggered workflow execution has no identifying principal at all."""
    scheduler_path = os.path.join(WORKFLOW_RUNNER_ROOT, "scheduler.py")
    with open(scheduler_path) as f:
        source = f.read()

    # _fire is a nested function; check the source for payload fields
    assert "actor_id" not in source
    assert "actor_context" not in source
    assert "user_id" not in source

    # Verify the payload dict has no actor field
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_fire":
            func_source = ast.get_source_segment(source, node) or ""
            for forbidden in ["actor_id", "actor_context", "user_id", "principal"]:
                assert forbidden not in func_source
            break


# ---- G. Workflow-level authorisation: role field declared but not enforced ----


def test_workflow_definition_has_role_field_not_enforced() -> None:
    """WorkflowDefinition has a 'role' field — 'Roles that can execute this
    workflow'. But the executor and adapter never check it. The field is
    declarative metadata, not an enforced authorisation control."""
    from models import WorkflowDefinition

    assert "role" in WorkflowDefinition.model_fields, (
        "WorkflowDefinition should declare a role field for workflow-level authorisation"
    )

    # The executor does not check workflow.role before execution
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        executor_source = f.read()

    # execute_workflow does not reference the workflow's role field
    assert "workflow.role" not in executor_source

    # The adapter does not check role either
    adapter_path = os.path.join(WORKFLOW_RUNNER_SRC, "adapters", "workflow_execution_adapter.py")
    with open(adapter_path) as f:
        adapter_source = f.read()
    assert "workflow.role" not in adapter_source


def test_workflow_execution_result_has_no_actor_provenance() -> None:
    """WorkflowExecutionResult has workflow_name but no actor_id or
    provenance — execution results cannot be attributed to an actor."""
    from contracts.workflow_execution import WorkflowExecutionResult

    result_fields = set(WorkflowExecutionResult.model_fields.keys())
    assert "workflow_name" in result_fields
    assert "status" in result_fields
    for forbidden in ["actor_id", "actor_context", "actor_type", "executed_by", "principal"]:
        assert forbidden not in result_fields


# ---- H. Workflow execution bypasses the organisation evidence loop ----


def test_workflow_executor_does_not_record_work_outcome() -> None:
    """execute_workflow does not call complete_work, fail_work, or
    record_work_learning — workflow execution does not feed evidence
    back to the organisation."""
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        source = f.read()

    for forbidden in [
        "complete_work", "fail_work(", "record_work_learning",
        "assess_work_outcome",
    ]:
        assert forbidden not in source, (
            f"executor.py should not reference '{forbidden}' — "
            "workflow execution does not feed evidence back to the organisation"
        )


def test_workflow_execution_adapter_does_not_record_evidence() -> None:
    """WorkflowExecutionAdapter.execute_workflow does not call
    InvocationRecorder or any organisation-level outcome recording."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    source = inspect.getsource(WorkflowExecutionAdapter)
    for forbidden in [
        "record_invocation", "InvocationRecorder",
        "complete_work", "fail_work", "record_work_learning",
        "assess_work_outcome",
    ]:
        assert forbidden not in source


# ---- I. Composition root confirms structural separation ----


def test_composition_root_wires_authorisation_only_to_capability_path() -> None:
    """The composition root wires `authorisation_port` to CapabilityExecutionAdapter
    and PatternRuntime but NOT to WorkflowExecutionAdapter. This is the
    structural proof that the bypass is by design, not accident."""
    composition_path = os.path.join(WORKFLOW_RUNNER_SRC, "composition.py")
    with open(composition_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Find the create_application function
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "create_application":
            func_source = ast.get_source_segment(source, node) or ""

            # authorisation_port exists and is passed to CapabilityExecutionAdapter
            assert "authorisation_port" in func_source
            assert "CapabilityExecutionAdapter" in func_source

            # authorisation_port is NOT passed to WorkflowExecutionAdapter
            # (it's instantiated with no args: WorkflowExecutionAdapter())
            workflow_adapter_section = re.search(
                r"WorkflowExecutionAdapter\([^)]*\)", func_source
            )
            assert workflow_adapter_section is not None, (
                "WorkflowExecutionAdapter should be instantiated"
            )
            adapter_call = workflow_adapter_section.group()
            assert "authorisation_port" not in adapter_call, (
                "WorkflowExecutionAdapter is intentionally not wired with "
                "authorisation_port at the composition root"
            )
            break
    else:
        raise AssertionError("create_application not found in composition.py")


def test_workflow_execution_adapter_class_has_no_authorisation_attribute() -> None:
    """WorkflowExecutionAdapter class body does not store an
    _authorisation_port attribute — there is no hidden authorisation wiring."""
    from workflow_runner.src.adapters.workflow_execution_adapter import (
        WorkflowExecutionAdapter,
    )

    source = inspect.getsource(WorkflowExecutionAdapter)
    assert "_authorisation_port" not in source
    assert "authorisation" not in source.lower()


# ---- J. Paperclip backend independence (workflow execution is not paperclip) ----


def test_paperclip_trigger_execution_bypasses_workflow_executor() -> None:
    """PaperclipBackend.execute calls trigger_execution (heartbeat API), not
    execute_workflow_from_file or the workflow executor. Paperclip is a
    Work backend, not a workflow execution backend."""
    operations_path = os.path.join(WORKFLOW_RUNNER_SRC, "operations.py")
    with open(operations_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PaperclipBackend":
            cls_source = ast.get_source_segment(source, node) or ""
            # Paperclip calls trigger_execution, not workflow execution
            assert "trigger_execution" in cls_source
            assert "execute_workflow_from_file" not in cls_source
            assert "execute_workflow" not in cls_source
            break
    else:
        raise AssertionError("PaperclipBackend not found in operations.py")


def test_paperclip_select_execution_path_does_not_check_workflow_role() -> None:
    """Paperclip's select_execution_path does not reference workflow.role
    for authorisation — the role field is never enforced by any OCP variant."""
    try:
        from organisation_paperclip import PaperclipOrganisationControlPlane
    except ImportError:
        import pytest
        pytest.skip("Paperclip adapter not available")

    source = inspect.getsource(
        PaperclipOrganisationControlPlane.select_execution_path
    )
    # Paperclip checks required_capability_ids, not workflow.role
    assert "required_capability_ids" in source
    assert "workflow_role" not in source
    assert ".role" not in source.replace("role:", "").replace("'role'", "")


# ---- K. Summary test: the two execution paths are parallel, not bridged ----


def test_two_execution_paths_never_converge() -> None:
    """There is no code path where WorkflowExecutionAdapter invokes
    CapabilityExecutionPort, or where the capability path invokes
    WorkflowExecutionPort. The two execution paths are structurally
    separated by the contracts layer."""
    # WorkflowExecutionAdapter does not reference CapabilityExecutionPort
    adapter_path = os.path.join(WORKFLOW_RUNNER_SRC, "adapters", "workflow_execution_adapter.py")
    with open(adapter_path) as f:
        adapter_source = f.read()
    assert "CapabilityExecutionPort" not in adapter_source
    assert "capability_execution" not in adapter_source.lower()

    # executor.py does not reference WorkflowExecutionPort (it uses the
    # raw executor function, not the port contract)
    executor_path = os.path.join(WORKFLOW_RUNNER_ROOT, "executor.py")
    with open(executor_path) as f:
        executor_source = f.read()
    assert "WorkflowExecutionPort" not in executor_source

    # capability_execution_adapter.py does not reference WorkflowExecutionPort
    cap_adapter_path = os.path.join(
        WORKFLOW_RUNNER_SRC, "adapters", "capability_execution_adapter.py"
    )
    with open(cap_adapter_path) as f:
        cap_source = f.read()
    assert "WorkflowExecutionPort" not in cap_source
    assert "execute_workflow" not in cap_source

    # contracts layer: neither port references the other
    contracts_execution = os.path.join(CONTRACTS_ROOT, "workflow_execution.py")
    with open(contracts_execution) as f:
        wf_contract_source = f.read()
    assert "CapabilityExecutionPort" not in wf_contract_source
    assert "actor_context" not in wf_contract_source

    contracts_capability = os.path.join(CONTRACTS_ROOT, "capability_execution.py")
    with open(contracts_capability) as f:
        cap_contract_source = f.read()
    assert "WorkflowExecutionPort" not in cap_contract_source
