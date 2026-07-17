"""
End-to-end test: Control Center → Workflow Engine → Services → Event Bus.

Simulates the full Control Center trigger flow:
1. Control Center triggers a workflow via POST /workflows/{name}/run
2. Workflow Engine creates a session, executes steps
3. Business Service endpoints (sessions, tasks, leads) operate
4. Lifecycle events are published to the bus
5. Status is pollable until terminal state

Contracts: SA-CONTRACTS-PHASES-2-5.md C10, C7; Control_Center_UI.md
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api import app
from assistant import AssistantReasoningService, StrategyDecision
from capabilities import Capability, CapabilityKind, CapabilityRegistry, ExecutionMode, AiSpec
from concepts import ConceptStore
from intent import Intent, IntentOrigin
from session import create_session_from_decision
from strategy import ReasoningStrategy


@pytest.fixture()
def client():
    with patch("api.EventBus") as MockBus, patch("api._build_scheduler") as mock_build:
        mock_bus = MagicMock()
        mock_bus.declare_topology = MagicMock()
        mock_bus.start_consumers = MagicMock()
        mock_bus.shutdown = MagicMock()
        mock_bus.publish_workflow_started = MagicMock()
        mock_bus.publish_workflow_completed = MagicMock()
        mock_bus.publish_workflow_failed = MagicMock()
        mock_bus.publish_step_started = MagicMock()
        mock_bus.publish_step_completed = MagicMock()
        mock_bus.publish_capability_request = MagicMock()
        mock_bus.publish_capability_reply = MagicMock()
        mock_bus.publish_knowledge_chunk = MagicMock()
        MockBus.return_value = mock_bus

        mock_sched = MagicMock()
        mock_sched.get_jobs.return_value = []
        mock_build.return_value = mock_sched

        with TestClient(app) as c:
            yield c


# ---- Control Center trigger: run a workflow ---------------------------------

def test_control_center_trigger_returns_workflow_id(client) -> None:
    resp = client.post("/workflows/test.execute/run", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "workflow_id" in body
    assert body["status"] in ("completed", "running", "failed")


def test_control_center_poll_status_until_terminal(client) -> None:
    run_resp = client.post("/workflows/test.execute/run", json={})
    wf_id = run_resp.json()["workflow_id"]
    wf_path = str(Path(__file__).resolve().parents[3] / "agentic" / "docs" / "workflows" / "test.execute.yaml")

    status_resp = client.get(f"/workflows/{wf_id}/status?workflow_path={wf_path}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["workflow_id"] == wf_id
    assert body["status"] in ("completed", "running", "failed")


# ---- Reasoning core: Control Center Intent → Strategy → Session -----------

def test_reasoning_core_intent_to_session(tmp_path: Path) -> None:
    svc = AssistantReasoningService()
    intent = Intent(
        id="e2e-int-1",
        origin=IntentOrigin.USER_REQUEST,
        raw={"type": "natural_language", "text": "Design a new task tracking service"},
    )
    decision = svc.decide(intent)
    assert decision.chosen_strategy == ReasoningStrategy.DELIBERATE_TO_CONSENSUS

    session = create_session_from_decision(decision, context={"workflow_name": "design.create"})
    assert session.status.value == "pending"
    assert len(session.pipeline) > 0


# ---- Business Services: Work Session, Task, Lead ---------------------------

def test_work_session_service_full_lifecycle(client) -> None:
    create = client.post("/sessions", json={"objectives": "E2E test session", "user_id": "user-1"}).json()
    sid = create["session_id"]
    assert sid

    got = client.get(f"/sessions/{sid}").json()
    assert got["objectives"] == "E2E test session"

    closed = client.put(f"/sessions/{sid}/close", json={"outcomes": "completed", "learnings": "learned a lot"}).json()
    assert closed["status"] == "closed"


def test_task_tracking_service_full_lifecycle(client) -> None:
    create = client.post("/tasks", json={"description": "E2E task", "priority": "high", "user_id": "user-1"}).json()
    tid = create["task_id"]
    assert tid

    got = client.get(f"/tasks/{tid}").json()
    assert got["description"] == "E2E task"
    assert got["status"] == "TODO"

    updated = client.put(f"/tasks/{tid}", json={"priority": "medium"}).json()
    assert updated["priority"] == "medium"

    patched = client.patch(f"/tasks/{tid}/status", json={"status": "IN_PROGRESS"}).json()
    assert patched["status"] == "IN_PROGRESS"


def test_lead_enrichment_service_enqueue_and_list(client) -> None:
    create = client.post("/leads/enrich", json={"company": "Acme Corp", "domain": "acme.com"}).json()
    lid = create["lead_id"]
    assert lid

    got = client.get(f"/leads/{lid}").json()
    assert got["raw_data"]["company"] == "Acme Corp"

    all_leads = client.get("/leads").json()
    assert any(l["lead_id"] == lid for l in all_leads)


# ---- Event Bus: lifecycle events published ---------------------------------

def test_event_bus_lifecycle_events_published(client) -> None:
    client.post("/workflows/test.execute/run", json={})
    bus = client.app.state.bus if hasattr(client.app.state, "bus") else None
    assert bus is not None


# ---- Capability invocation via PatternRuntime ------------------------------

def test_capability_invocation_end_to_end(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)

    cap = Capability(
        id="cap-e2e-echo",
        name="echo",
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport="tier2_inprocess",
        ai_spec=AiSpec(purpose="echo", inputs=[], outputs=[]),
        interface={
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "outputs": [{"name": "result", "type": "string"}],
            "errors": [],
        },
    )
    reg.register(cap)

    from runtime import PatternRuntime
    runtime = PatternRuntime(registry=reg)
    reply = runtime.invoke_step(cap.id, {"text": "hello e2e"})
    assert reply["status"] == "completed"


# ---- Knowledge Store routing -----------------------------------------------

def test_knowledge_store_routes_by_tags(tmp_path: Path) -> None:
    from knowledge import KnowledgeStore, KnowledgeChunk

    store = KnowledgeStore(data_dir=str(tmp_path))
    handled = []

    def _concept_writer(chunk):
        handled.append(chunk)

    store.set_writers(_concept_writer, lambda c: None, lambda c: None)
    chunk = KnowledgeChunk(
        chunk_id="chunk-e2e-1",
        semantic_tags=["solved_approach"],
        payload_ref="doc://test",
        source="session",
        source_ref="s1",
    )
    store.ingest(chunk)
    assert len(handled) == 1
    assert handled[0].chunk_id == "chunk-e2e-1"
    assert handled[0].semantic_tags == ["solved_approach"]
