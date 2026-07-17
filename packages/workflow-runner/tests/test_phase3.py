"""
TDD tests for Phase 3 — Session execution, Pattern Runtime, and Service invocation.

Contracts: SA-CONTRACTS-PHASES-2-5.md C10, C7.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assistant import AssistantReasoningService, StrategyDecision
from capabilities import Capability, CapabilityKind, CapabilityRegistry, ExecutionMode, AiSpec
from concepts import ConceptStore, EnterpriseConcept
from intent import Intent, IntentOrigin
from session import Session, SessionStatus, create_session_from_decision
from runtime import PatternRuntime, invoke_step
from strategy import ReasoningStrategy


# ---- create_session (C10) -------------------------------------------------

def test_create_session_from_decision(tmp_path: Path) -> None:
    decision = StrategyDecision(
        intent_id="int-1",
        chosen_strategy=ReasoningStrategy.INVESTIGATE_THEN_FIX,
        pattern_pipeline=["investigation@1.0.0", "sop_execution@1.0.0"],
        participant_roles=["investigator", "operator"],
    )
    session = create_session_from_decision(decision, context={})
    assert session.status == SessionStatus.PENDING
    assert len(session.pipeline) == 2
    assert session.pipeline[0].pattern_id == "investigation@1.0.0"


def test_create_session_sets_intent_and_strategy(tmp_path: Path) -> None:
    decision = StrategyDecision(
        intent_id="int-2",
        chosen_strategy=ReasoningStrategy.DELIBERATE_TO_CONSENSUS,
        pattern_pipeline=["debate@1.0.0"],
    )
    session = create_session_from_decision(decision, context={"workflow_name": "arb-test"})
    assert session.intent_id == "int-2"
    assert session.strategy == ReasoningStrategy.DELIBERATE_TO_CONSENSUS


# ---- PatternRuntime + invoke_step (C10) -----------------------------------

def test_invoke_step_tier2_calls_run_directly(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    cap = Capability(
        id="cap-echo",
        name="echo",
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport="tier2_inprocess",
        ai_spec=AiSpec(purpose="echo back the input", inputs=[], outputs=[]),
        interface={
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "outputs": [{"name": "result", "type": "string"}],
            "errors": [],
        },
    )
    reg.register(cap)

    runtime = PatternRuntime(registry=reg)
    reply = runtime.invoke_step(cap.id, {"text": "hello"})
    assert reply["status"] == "completed"
    assert "echo back the input" in reply["outputs"]["composed_prompt"]


def test_invoke_step_tier3_returns_capability_reply(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    cap = Capability(
        id="cap-bus",
        name="bus_tool",
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.COMPILED,
        transport="tier3_bus",
        compiled_ref={"module_path": "agentic/skills/_compiled/bus_tool.py", "entrypoint": "run", "tests_passed": True},
    )
    reg.register(cap)

    runtime = PatternRuntime(registry=reg)
    # tier3_bus returns a reply dict (simulated bus hand-off)
    reply = runtime.invoke_step(cap.id, {"x": 1})
    assert reply["status"] == "completed"
    assert "correlation_id" in reply


# ---- Workflow Engine lifecycle ---------------------------------------------

def test_run_workflow_returns_workflow_id(client) -> None:
    resp = client.post("/workflows/design.create/run", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "workflow_id" in body


def test_workflow_status_after_run(client) -> None:
    run_resp = client.post("/workflows/design.create/run", json={})
    wf_id = run_resp.json()["workflow_id"]
    wf_path = str(Path(__file__).resolve().parents[3] / "agentic" / "docs" / "workflows" / "design.create.yaml")
    status_resp = client.get(f"/workflows/{wf_id}/status?workflow_path={wf_path}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["workflow_id"] == wf_id
    assert body["status"] in ("completed", "running", "failed")


# ---- business Service data-layer (C7) -------------------------------------

def test_work_session_service_crud(client) -> None:
    create = client.post("/sessions", json={"objectives": "Test session"}).json()
    assert "session_id" in create
    sid = create["session_id"]
    got = client.get(f"/sessions/{sid}").json()
    assert got["objectives"] == "Test session"
    closed = client.put(f"/sessions/{sid}/close", json={"outcomes": "done"}).json()
    assert closed["status"] == "closed"


def test_task_tracking_service_crud(client) -> None:
    create = client.post("/tasks", json={"description": "Test task", "priority": "high"}).json()
    assert "task_id" in create
    tid = create["task_id"]
    got = client.get(f"/tasks/{tid}").json()
    assert got["description"] == "Test task"
    patched = client.patch(f"/tasks/{tid}/status", json={"status": "DONE"}).json()
    assert patched["status"] == "DONE"


def test_lead_enrichment_service_enqueue(client) -> None:
    create = client.post("/leads/enrich", json={"company": "Acme"}).json()
    assert "lead_id" in create
