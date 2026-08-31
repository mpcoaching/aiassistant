"""
Layer 2 — Application Integration tests for POST /assistant/capability/{capability_id}//execute (Increment 5).

Uses the real FastAPI app with TestClient. Infrastructure dependencies
(EventBus, Scheduler, Database, LLM) are mocked at the adapter boundary,
but the AssistantChatService, context formation, validation loop, and
Work delegation are exercised with real code.

Run:
  pytest packages/workflow_runner/tests/test_capability_execute.py -v --tb=short
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_packages_root = Path(__file__).resolve().parent.parent.parent
for _pkg in ["bus", "capability_registry", "ai", "workflow_runner", "langgraph"]:
    _src = _packages_root / _pkg / "src"
    if _src.exists() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

_ai_tests_fixtures = _packages_root / "ai" / "tests" / "fixtures"
if str(_ai_tests_fixtures) not in sys.path:
    sys.path.insert(0, str(_ai_tests_fixtures))

_api_path = _packages_root / "workflow_runner" / "api.py"
_spec = importlib.util.spec_from_file_location("workflow_runner_api", _api_path)
_api_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api_mod)
sys.modules["workflow_runner_api"] = _api_mod
app = _api_mod.app


@pytest.fixture()
def client():
    with pytest.MonkeyPatch.context() as m:
        m.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
        m.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        m.setenv("REDIS_URL", "redis://localhost:6379")
        m.setenv("OPENAI_API_BASE", "http://localhost:4000/v1")
        m.setenv("OPENAI_BASE_URL", "http://localhost:4000/v1")
        m.setenv("ENV_TIER", "test")
        with patch("workflow_runner_api.EventBus") as MockBus, patch("workflow_runner_api._build_scheduler") as mock_build:
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


def test_execute_capability_endpoint_returns_result(client):
    with patch("workflow_runner_api._assistant") as mock_assistant:
        mock_assistant.execute_selected_capability.return_value = MagicMock(
            outputs={"artifact_id": "art-123"},
            artifacts=[],
            telemetry={"capability_name": "create_test_artifact"},
        )

        response = client.post(
            "/assistant/capability/cap-exec-1/execute",
            json={"context": {"label": "foo"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["outputs"]["artifact_id"] == "art-123"
        assert data["telemetry"]["capability_name"] == "create_test_artifact"
        mock_assistant.execute_selected_capability.assert_called_once_with(
            capability_id="cap-exec-1", context={"label": "foo"}
        )


def test_execute_capability_endpoint_defaults_context_to_empty(client):
    with patch("workflow_runner_api._assistant") as mock_assistant:
        mock_assistant.execute_selected_capability.return_value = MagicMock(
            outputs={}, artifacts=[], telemetry={}
        )

        response = client.post("/assistant/capability/cap-1/execute", json={})
        assert response.status_code == 200
        mock_assistant.execute_selected_capability.assert_called_once_with(
            capability_id="cap-1", context={}
        )


def test_capability_feedback_endpoint_records_action(client):
    with patch("workflow_runner_api._assistant") as mock_assistant:
        response = client.post(
            "/assistant/capability/feedback",
            json={
                "match_event_id": "event-123",
                "action": "confirm",
                "selected_capability_id": "cap-a",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["match_event_id"] == "event-123"
        assert data["action"] == "confirm"
        assert data["status"] == "recorded"
        mock_assistant.record_capability_feedback.assert_called_once_with(
            match_event_id="event-123",
            user_action="confirm",
            selected_capability_id="cap-a",
        )


def test_telemetry_events_endpoint_returns_empty_when_no_events(client):
    with patch("workflow_runner_api._capability_selection_telemetry") as mock_telemetry:
        mock_telemetry.get_events.return_value = []
        response = client.get("/assistant/telemetry/events")
        assert response.status_code == 200
        assert response.json() == []


def test_telemetry_events_endpoint_returns_events(client):
    from capability_selection_telemetry import CapabilitySelectionEvent

    mock_events = [
        CapabilitySelectionEvent(
            event_id="event-1",
            timestamp=datetime.now(timezone.utc),
            request_text="create something",
            session_id="ses-1",
            candidate_ids=["cap-a"],
            candidate_scores=[0.9],
            top_score=0.9,
            score_gap=0.0,
            candidate_count=1,
            interaction_type="confirm",
            user_action="confirm",
            selected_capability_id="cap-a",
        ),
    ]
    with patch("workflow_runner_api._capability_selection_telemetry") as mock_telemetry:
        mock_telemetry.get_events.return_value = mock_events
        response = client.get("/assistant/telemetry/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_id"] == "event-1"
        assert data[0]["request_text"] == "create something"
        assert data[0]["user_action"] == "confirm"


def test_telemetry_session_endpoint_returns_session_events(client):
    from capability_selection_telemetry import CapabilitySelectionEvent

    mock_events = [
        CapabilitySelectionEvent(
            event_id="event-1",
            timestamp=datetime.now(timezone.utc),
            request_text="first request",
            session_id="ses-123",
            candidate_ids=["cap-a"],
            candidate_scores=[0.9],
            top_score=0.9,
            score_gap=0.0,
            candidate_count=1,
            interaction_type="confirm",
        ),
        CapabilitySelectionEvent(
            event_id="event-2",
            timestamp=datetime.now(timezone.utc),
            request_text="second request",
            session_id="ses-123",
            candidate_ids=["cap-a", "cap-b"],
            candidate_scores=[0.9, 0.7],
            top_score=0.9,
            score_gap=0.2,
            candidate_count=2,
            interaction_type="select",
        ),
    ]
    with patch("workflow_runner_api._capability_selection_telemetry") as mock_telemetry:
        mock_telemetry.get_events_by_session.return_value = mock_events
        response = client.get("/assistant/telemetry/sessions/ses-123")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(e["session_id"] == "ses-123" for e in data)


def test_telemetry_reformulations_endpoint_returns_reformulation_candidates(client):
    from capability_selection_telemetry import CapabilitySelectionEvent

    mock_events = [
        CapabilitySelectionEvent(
            event_id="event-1",
            timestamp=datetime.now(timezone.utc),
            request_text="first request",
            session_id="ses-123",
            candidate_ids=["cap-a"],
            candidate_scores=[0.9],
            top_score=0.9,
            score_gap=0.0,
            candidate_count=1,
            interaction_type="confirm",
        ),
    ]
    with patch("workflow_runner_api._capability_selection_telemetry") as mock_telemetry:
        mock_telemetry.get_reformulation_candidates.return_value = mock_events
        response = client.get("/assistant/telemetry/reformulations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_id"] == "event-1"


def test_telemetry_stats_endpoint_returns_statistics(client):
    from capability_selection_telemetry import CapabilitySelectionEvent

    mock_events = [
        CapabilitySelectionEvent(
            event_id="event-1",
            timestamp=datetime.now(timezone.utc),
            request_text="request 1",
            session_id="ses-1",
            candidate_ids=["cap-a"],
            candidate_scores=[0.9],
            top_score=0.9,
            score_gap=0.0,
            candidate_count=1,
            interaction_type="confirm",
            user_action="confirm",
        ),
        CapabilitySelectionEvent(
            event_id="event-2",
            timestamp=datetime.now(timezone.utc),
            request_text="request 2",
            session_id="ses-2",
            candidate_ids=["cap-a", "cap-b"],
            candidate_scores=[0.9, 0.7],
            top_score=0.9,
            score_gap=0.2,
            candidate_count=2,
            interaction_type="select",
            user_action="reject",
        ),
    ]
    with patch("workflow_runner_api._capability_selection_telemetry") as mock_telemetry:
        mock_telemetry.get_events.return_value = mock_events
        mock_telemetry.get_reformulation_candidates.return_value = []
        response = client.get("/assistant/telemetry/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 2
        assert data["total_sessions"] == 2
        assert data["reformulation_candidates"] == 0
        assert data["outcomes"] == {"confirm": 1, "reject": 1}
        assert "gap=0.0" in data["gap_distribution"]
        assert "0.1<gap<=0.2" in data["gap_distribution"]


def test_telemetry_export_endpoint_exports_events(client):
    with patch("workflow_runner_api._capability_selection_telemetry") as mock_telemetry:
        mock_telemetry.export_to_json.return_value = None
        response = client.post(
            "/assistant/telemetry/export",
            json={"output_path": "data/telemetry_export.json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "exported"
        assert data["path"] == "data/telemetry_export.json"
        mock_telemetry.export_to_json.assert_called_once_with("data/telemetry_export.json")


# ---- Work Management / Organisation Integration -----------------------


def test_list_work_returns_empty_when_no_work(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        mock_org.list_work.return_value = []
        response = client.get("/work")
        assert response.status_code == 200
        assert response.json() == []


def test_get_work_returns_404_when_missing(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        mock_org.get_work.return_value = None
        response = client.get("/work/missing-id")
        assert response.status_code == 404


def test_process_work_executes_real_worker_and_creates_output(client, tmp_path):
    from workflow_runner.src.worker import Worker
    from organisation.src.role import Work, WorkStatus

    work = Work(id="w1", title="Test task", accountable_role_id="r1", description="Test description")
    mock_org = MagicMock()
    mock_org.get_work.return_value = work
    mock_org._work = {"w1": work}

    worker = Worker(output_dir=str(tmp_path))
    result = worker.execute(work, mock_org)

    assert result["status"] == "completed"
    assert result["title"] == "Test task"
    assert result["output_type"] == "markdown"
    assert tmp_path.joinpath("w1-test-task.md").exists()
    mock_org.complete_work.assert_not_called()


def test_work_endpoints_501_when_org_plane_not_configured(client):
    with patch("workflow_runner_api._org_plane", None):
        response = client.get("/work")
        assert response.status_code == 501

        response = client.get("/work/w1")
        assert response.status_code == 501

        response = client.get("/roles")
        assert response.status_code == 501


# ---- Role Visibility --------------------------------------------------------


def test_list_roles_returns_empty_when_no_roles(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        mock_org.list_roles.return_value = []
        response = client.get("/roles")
        assert response.status_code == 200
        assert response.json() == []


def test_list_roles_returns_registered_roles(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        from organisation.src.role import Role, RoleStatus
        mock_org.list_roles.return_value = [
            Role(id="r1", name="Researcher", status=RoleStatus.ACTIVE, authority_ids=["auth-1"]),
            Role(id="r2", name="Writer", status=RoleStatus.ACTIVE, authority_ids=["auth-2"]),
        ]
        response = client.get("/roles")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role_id"] == "r1"
        assert data[0]["name"] == "Researcher"
        assert data[1]["role_id"] == "r2"


# ---- Worker Pickup ---------------------------------------------------------


def test_worker_pickup_returns_assigned_work(tmp_path):
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Agent, Work, WorkStatus
    from organisation.src.worker import Worker

    org_plane = InMemoryOrganisationControlPlane()
    work = Work(id="w1", title="Pickup task", accountable_role_id="default", description="Test")
    worker_agent = Agent(id=Worker.DEFAULT_AGENT_ID, name="Worker")
    org_plane.assign_work(work, worker_agent)

    worker = Worker()
    picked = worker.pickup(org_plane)
    assert picked is not None
    assert picked.id == "w1"
    assert picked.status == WorkStatus.ASSIGNED


def test_worker_pickup_returns_none_when_no_assigned_work(tmp_path):
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.worker import Worker

    org_plane = InMemoryOrganisationControlPlane()
    worker = Worker()
    assert worker.pickup(org_plane) is None


def test_worker_run_endpoint_processes_assigned_work(client, tmp_path):
    from workflow_runner.src.worker import Worker
    from organisation.src.role import Work, WorkStatus

    work = Work(id="w1", title="Worker task", accountable_role_id="default", assignee_agent_id="worker-agent")
    mock_org = MagicMock()
    mock_org.list_work.return_value = [work]
    mock_org.get_work.return_value = work
    mock_org._work = {"w1": work}

    worker = Worker(output_dir=str(tmp_path))
    picked = worker.pickup(mock_org)
    assert picked == work

    result = worker.execute(work, mock_org)
    assert result["status"] == "completed"
    mock_org.complete_work.assert_not_called()


def test_worker_run_returns_404_when_no_work(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        with patch("workflow_runner_api.Worker") as MockWorker:
            mock_worker = MockWorker.return_value
            mock_worker.pickup.return_value = None

            response = client.post("/worker/run")
            assert response.status_code == 404


# ---- Worker Tests ---------------------------------------------------------


def test_worker_creates_output_file(tmp_path):
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Work, WorkStatus
    from organisation.src.worker import Worker

    org_plane = InMemoryOrganisationControlPlane()
    work = Work(id="w1", title="Research task", accountable_role_id="r1", description="Research X")

    worker = Worker(output_dir=str(tmp_path))
    result = worker.execute(work, org_plane)

    assert result["status"] == "completed"
    assert result["output_type"] == "markdown"
    assert result["work_id"] == "w1"
    assert Path(result["output_path"]).exists()
    content = Path(result["output_path"]).read_text(encoding="utf-8")
    assert "Research task" in content
    assert "Work Summary" in content
    assert work.outcome == result
    assert work.status == WorkStatus.COMPLETED
    assert work.assignee_agent_id == "worker-agent"


def test_worker_handles_failure(tmp_path):
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Work, WorkStatus
    from organisation.src.worker import Worker

    org_plane = InMemoryOrganisationControlPlane()
    work = Work(id="w1", title="Failing task", accountable_role_id="r1", description="Will fail")

    worker = Worker(output_dir=str(tmp_path))
    original_do_work = worker._do_work
    worker._do_work = lambda w: (_ for _ in ()).throw(RuntimeError("Simulated failure"))

    result = worker.execute(work, org_plane)

    assert result["status"] == "failed"
    assert "error" in result
    assert work.status == WorkStatus.FAILED
    assert work.outcome == result


def test_worker_preserves_session_correlation(tmp_path):
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Work, WorkStatus
    from organisation.src.worker import Worker

    org_plane = InMemoryOrganisationControlPlane()
    work = Work(
        id="w1",
        title="Session task",
        accountable_role_id="r1",
        context={"session_id": "ses-123"},
    )

    worker = Worker(output_dir=str(tmp_path))
    result = worker.execute(work, org_plane)

    assert result["status"] == "completed"
    assert work.context.get("session_id") == "ses-123"
    assert work.outcome is not None


# ---- End-to-End Integration Test ------------------------------------------


def test_end_to_end_delegation_worker_result(client, tmp_path):
    from chat import ChatRequest
    from chat import AssistantChatService
    from in_memory_ports import InMemoryCapabilityDiscoveryPort, InMemoryWorkManagementPort
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Role, Work, WorkStatus
    from organisation.src.worker import Worker

    discovery = InMemoryCapabilityDiscoveryPort(candidates=[])
    work_management = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
    )

    response = service.chat(ChatRequest(message="Research X and report back", session_id="ses-e2e-1"))
    assert response.status == "delegated"
    assert len(work_management.created_work) == 1
    work_id = work_management.created_work[0]["work_id"]

    org_plane = InMemoryOrganisationControlPlane()
    work = Work(
        id=work_id,
        title=response.telemetry.get("work_title", "Research X"),
        accountable_role_id="default",
        description="Research X and report back",
        context={"session_id": "ses-e2e-1"},
    )
    org_plane.register_role(Role(id="default", name="Default", authority_ids=[]))
    org_plane.assign_work(work, org_plane.get_role("default"))

    worker = Worker(output_dir=str(tmp_path))
    result = worker.execute(work, org_plane)

    assert result["status"] == "completed"
    assert Path(result["output_path"]).exists()

    from api import _WorkResponse
    work_response = _WorkResponse(
        work_id=work.id,
        title=work.title,
        description=work.description,
        status=work.status.value,
        priority=work.priority,
        work_type=work.work_type,
        accountable_role_id=work.accountable_role_id,
        assignee_role_id=work.assignee_role_id,
        assignee_person_id=work.assignee_person_id,
        assignee_agent_id=work.assignee_agent_id,
        outcome=work.outcome,
        output_path=work.outcome.get("output_path") if work.outcome else None,
    )
    assert work_response.outcome["summary"].startswith("# Work Summary: Research X")
    assert work_response.status == "completed"
    assert "Research X and report back" in work_response.outcome["summary"]


# ---- Enterprise Capability Query API Tests -----------------------------------


def test_query_capability_availability_returns_available(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        mock_org.query_capability.return_value = {
            "capability_id": "cap-1",
            "available": True,
            "eta_seconds": 5,
            "assignee": None,
            "reason": "Available now",
        }
        response = client.get("/capabilities/cap-1/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["capability_id"] == "cap-1"
        assert data["available"] is True
        assert data["eta_seconds"] == 5
        assert data["reason"] == "Available now"


def test_query_capability_availability_returns_404_when_not_found(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        mock_org.query_capability.return_value = None
        response = client.get("/capabilities/cap-missing/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["capability_id"] == "cap-missing"
        assert data["available"] is False
        assert "not found" in data["reason"]


def test_query_capability_availability_501_when_org_plane_not_configured(client):
    with patch("workflow_runner_api._org_plane", None):
        response = client.get("/capabilities/cap-1/availability")
        assert response.status_code == 501


# ---- OrganisationControlPlane query_capability tests -------------------------


def test_query_capability_returns_none_when_no_role_has_capability():
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane

    org_plane = InMemoryOrganisationControlPlane()
    result = org_plane.query_capability("cap-missing")
    assert result is None


def test_query_capability_returns_available_when_role_has_capability():
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Role, Work, WorkStatus

    org_plane = InMemoryOrganisationControlPlane()
    org_plane.register_role(Role(id="r1", name="Researcher", authority_ids=[], required_capability_ids=["cap-1"]))
    result = org_plane.query_capability("cap-1")
    assert result is not None
    assert result["available"] is True
    assert result["eta_seconds"] == 5
    assert result["reason"] == "Capability is available"


def test_query_capability_returns_unavailable_when_in_progress():
    from organisation.src.organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.role import Role, Work, WorkStatus

    org_plane = InMemoryOrganisationControlPlane()
    org_plane.register_role(Role(id="r1", name="Researcher", authority_ids=[], required_capability_ids=["cap-1"]))
    work = Work(id="w1", title="Busy work", accountable_role_id="r1", required_capability_ids=["cap-1"])
    work.status = WorkStatus.IN_PROGRESS
    org_plane._work[work.id] = work

    result = org_plane.query_capability("cap-1")
    assert result is not None
    assert result["available"] is False
    assert result["eta_seconds"] is None
    assert "in use" in result["reason"]


# ---- 21U End-to-End Integration Tests ---------------------------------------


def test_fast_capability_end_to_end_via_api(client):
    response = client.post(
        "/assistant/chat",
        json={"message": "run the real capability", "session_id": "ses-fast-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"


def test_slow_capability_produces_interim_via_api(client):
    import workflow_runner_api as wr_api_mod
    from contracts.capability_discovery import CapabilityCandidate

    slow_candidate = CapabilityCandidate(
        id="slow-cap",
        name="Slow Capability",
        description="A slow capability",
        kind="tool",
        confidence=0.9,
    )
    mock_discovery = MagicMock()
    mock_discovery.find_capabilities.return_value = [slow_candidate]
    original_discovery = wr_api_mod._assistant._capability_discovery
    original_query = wr_api_mod._assistant._enterprise_capability_query
    wr_api_mod._assistant._capability_discovery = mock_discovery

    mock_availability = MagicMock()
    mock_availability.available = True
    mock_availability.eta_seconds = 300
    mock_availability.assignee = None
    mock_availability.reason = "Busy"
    wr_api_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
        return_value=mock_availability
    )

    try:
        response = client.post(
            "/assistant/chat",
            json={"message": "do something slow", "session_id": "ses-slow-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "delegated_with_interim"
        assert "preliminary answer" in data["message"]
    finally:
        wr_api_mod._assistant._capability_discovery = original_discovery
        wr_api_mod._assistant._enterprise_capability_query = original_query


def test_capability_gap_creates_development_work_via_api(client):
    import workflow_runner_api as api_mod
    from contracts.capability_discovery import CapabilityCandidate

    gap_candidate = CapabilityCandidate(
        id="gap-cap",
        name="Gap Capability",
        description="A capability that does not exist",
        kind="tool",
        confidence=0.9,
    )
    mock_discovery = MagicMock()
    mock_discovery.find_capabilities.return_value = [gap_candidate]
    original_discovery = api_mod._assistant._capability_discovery
    original_query = api_mod._assistant._enterprise_capability_query
    api_mod._assistant._capability_discovery = mock_discovery
    api_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
        return_value=None
    )

    try:
        response = client.post(
            "/assistant/chat",
            json={"message": "do something impossible", "session_id": "ses-gap-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "capability_gap"
        assert "does not currently have" in data["message"]
        assert data["telemetry"]["gap"] is True
        assert data["telemetry"]["work_created"] is True
        assert data["telemetry"]["work_id"] is not None

        work_id = data["telemetry"]["work_id"]
        work_response = client.get(f"/work/{work_id}")
        assert work_response.status_code == 200
        work_data = work_response.json()
        assert work_data["title"] == "Develop capability: Gap Capability"
        assert work_data["status"] == "assigned"
    finally:
        api_mod._assistant._capability_discovery = original_discovery
        api_mod._assistant._enterprise_capability_query = original_query


def test_capabilities_list_endpoint_returns_capabilities(client):
    import workflow_runner_api as api_mod
    from capability import Capability, CapabilityKind

    mock_cap = Capability(
        id="cap-1",
        name="Test Capability",
        description="A test capability",
        capability_kind=CapabilityKind.SKILL,
        tags=["skill"],
    )
    api_mod._capability_registry = MagicMock()
    api_mod._capability_registry.list_all.return_value = [mock_cap]
    api_mod._org_plane.query_capability = MagicMock(
        return_value={
            "capability_id": "cap-1",
            "available": True,
            "eta_seconds": 5,
            "assignee": None,
            "reason": "Available now",
        }
    )

    response = client.get("/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["capability_id"] == "cap-1"
    assert data[0]["name"] == "Test Capability"
    assert data[0]["available"] is True
    assert data[0]["eta_seconds"] == 5


def test_organisational_learning_loop_via_api(client):
    import workflow_runner_api as wr_mod
    from contracts.capability_discovery import CapabilityCandidate

    org_plane = wr_mod._org_plane
    capability_registry = wr_mod._capability_registry
    assert org_plane is not None
    assert capability_registry is not None

    capability_name = "unique-learning-loop-capability"
    request_message = f"do the {capability_name}"

    gap_candidate = CapabilityCandidate(
        id=f"cap-{capability_name}",
        name=capability_name,
        description=f"A capability for {capability_name}",
        kind="skill",
        confidence=0.9,
    )
    mock_discovery = MagicMock()
    mock_discovery.find_capabilities.return_value = [gap_candidate]
    original_discovery = wr_mod._assistant._capability_discovery
    original_query = wr_mod._assistant._enterprise_capability_query
    wr_mod._assistant._capability_discovery = mock_discovery
    wr_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
        return_value=None
    )

    try:
        response1 = client.post(
            "/assistant/chat",
            json={"message": request_message, "session_id": "ses-loop-1"},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "capability_gap"
        assert "does not currently have" in data1["message"]
        work_id = data1["telemetry"]["work_id"]
        assert work_id is not None

        work = org_plane.get_work(work_id)
        assert work is not None
        assert work.work_type == "capability_development"

        from workflow_runner.src.worker import Worker
        worker = Worker()
        worker_data = worker.execute(work, org_plane)
        assert worker_data["status"] == "completed"
        assert worker_data["execution_mode"] == "capability_development"

        developed_cap_id = worker_data["capability_id"]
        assert org_plane.get_capability(developed_cap_id) is not None
        assert capability_registry.get(developed_cap_id) is not None

        mock_discovery.find_capabilities.return_value = [
            CapabilityCandidate(
                id=developed_cap_id,
                name=capability_name,
                description=f"A capability for {capability_name}",
                kind="skill",
                confidence=0.9,
            )
        ]
        wr_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
            return_value=MagicMock(
                capability_id=developed_cap_id,
                available=True,
                eta_seconds=5,
                assignee=None,
                reason="Available now",
            )
        )

        response2 = client.post(
            "/assistant/chat",
            json={"message": request_message, "session_id": "ses-loop-2"},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "completed"
        assert developed_cap_id in data2["telemetry"]["required_capability_ids"]
    finally:
        wr_mod._assistant._capability_discovery = original_discovery
        wr_mod._assistant._enterprise_capability_query = original_query


def test_chat_creates_work_executes_it_and_returns_result(client):
    """End-to-end: user message → work created → executed → result returned."""
    response = client.post(
        "/assistant/chat",
        json={"message": "Summarise the quarterly report", "session_id": "ses-mvp-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]
    assert work_id is not None

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    assert work_data["outcome"] is not None
    assert "summary" in work_data["outcome"]
    assert work_data["outcome"]["output_type"] == "markdown"


def test_chat_birthday_party_plan_is_specific(client):
    response = client.post(
        "/assistant/chat",
        json={"message": "Plan a birthday party for 20 people", "session_id": "ses-party-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "Event" in summary or "party" in summary.lower()
    assert "20" in summary


def test_chat_hiking_trip_plan_is_specific(client):
    response = client.post(
        "/assistant/chat",
        json={"message": "Plan a 3-day hiking trip for two people", "session_id": "ses-hike-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "Travel" in summary or "hiking" in summary.lower()
    assert "2" in summary or "two" in summary.lower()


def test_chat_product_launch_plan_is_specific(client):
    response = client.post(
        "/assistant/chat",
        json={"message": "Create a launch plan for a new coaching program", "session_id": "ses-launch-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "Product Launch" in summary or "launch" in summary.lower()
    assert "marketing" in summary.lower() or "campaign" in summary.lower()


COACHING_PROGRAM_DOC = """
The new coaching program is designed to help mid-career professionals transition into leadership roles.
The program spans 12 weeks and includes weekly group coaching sessions, one-to-one mentoring,
and practical assignments focused on real workplace challenges.
Participants will develop skills in strategic thinking, stakeholder communication, and team motivation.
The program is delivered by certified coaches with experience in Fortune 500 companies.
Assessment is continuous, with feedback provided after each module.
Graduates receive a recognised leadership certification and access to an alumni network.
"""

HIKING_TRIP_DOC = """
A 3-day hiking trip for two people in the Swiss Alps.
Day 1: Arrive in Interlaken, collect equipment, and begin the hike to Obersteinberg.
Distance: 12 km. Elevation gain: 800 m. Overnight in a mountain hut.
Day 2: Hike from Obersteinberg to Kleine Scheidegg via the alpine trail.
Distance: 15 km. Elevation gain: 600 m. Overnight at a guesthouse in Grindelwald.
Day 3: Optional glacier hike or rest day. Return to Interlaken by train.
Total distance: approximately 40 km. Difficulty: moderate.
Required gear includes hiking boots, waterproof jacket, day pack, and trekking poles.
The best months for this trip are June through September.
"""

PRODUCT_LAUNCH_DOC = """
Our mobile app launch has three distinct phases.
Phase 1 focuses on user acquisition through social media campaigns and influencer partnerships.
We expect to reach 50,000 downloads in the first two weeks.
Phase 2 is about retention: we will introduce personalised recommendations and weekly challenges.
Our target is a 40% day-30 retention rate.
Phase 3 covers monetisation via a premium subscription tier priced at $9.99 per month.
The engineering team has completed beta testing with 2,000 users and fixed 147 bugs.
Marketing will launch with a $200,000 budget, primarily targeting North America and Europe.
Customer support will be available 24/7 from launch day.
"""


def test_chat_summarise_document_produces_coherent_summary(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Summarise this document.",
            "session_id": "ses-summary-1",
            "context": {"input_text": COACHING_PROGRAM_DOC},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Summary:" in summary
    assert "coaching" in summary.lower() or "leadership" in summary.lower()
    assert "compression" in summary.lower()
    summary_text_start = summary.index("## Summary") + len("## Summary")
    summary_text = summary[summary_text_start:]
    summary_text = summary_text.split("## Result")[0].strip()
    summary_words = len(summary_text.split())
    input_words = len(COACHING_PROGRAM_DOC.split())
    assert summary_words < input_words


def test_chat_summarise_different_documents_produce_different_summaries(client):
    response_a = client.post(
        "/assistant/chat",
        json={
            "message": "Summarise this document.",
            "session_id": "ses-summary-a",
            "context": {"input_text": COACHING_PROGRAM_DOC},
        },
    )
    assert response_a.status_code == 200
    data_a = response_a.json()
    work_id_a = data_a["telemetry"]["work_id"]
    work_response_a = client.get(f"/work/{work_id_a}")
    work_data_a = work_response_a.json()
    summary_a = work_data_a["outcome"]["summary"]

    response_b = client.post(
        "/assistant/chat",
        json={
            "message": "Summarise this document.",
            "session_id": "ses-summary-b",
            "context": {"input_text": HIKING_TRIP_DOC},
        },
    )
    assert response_b.status_code == 200
    data_b = response_b.json()
    work_id_b = data_b["telemetry"]["work_id"]
    work_response_b = client.get(f"/work/{work_id_b}")
    work_data_b = work_response_b.json()
    summary_b = work_data_b["outcome"]["summary"]

    assert summary_a != summary_b
    assert "hiking" in summary_b.lower() or "alps" in summary_b.lower()
    assert "km" in summary_b.lower()


def test_chat_summarise_longer_document_compresses_content(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Summarise this document.",
            "session_id": "ses-summary-long",
            "context": {"input_text": PRODUCT_LAUNCH_DOC},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Summary:" in summary

    summary_text_start = summary.index("## Summary") + len("## Summary")
    summary_text = summary[summary_text_start:]
    summary_text = summary_text.split("## Result")[0].strip()

    input_words = len(PRODUCT_LAUNCH_DOC.split())
    summary_words = len(summary_text.split())
    assert summary_words < input_words * 0.7

    summary_lower = summary.lower()
    input_tokens = set(
        w.strip(".,!?;:\"'()[]{}").lower()
        for w in PRODUCT_LAUNCH_DOC.split()
        if len(w.strip(".,!?;:\"'()[]{}")) > 4
    )
    summary_tokens = set(summary_lower.split())
    overlap = input_tokens & summary_tokens
    assert len(overlap) >= 3


def test_chat_summarise_uploaded_document(client):
    document_text = (
        "The new coaching program is designed to help mid-career professionals "
        "transition into leadership roles. The program spans 12 weeks and includes "
        "weekly group coaching sessions, one-to-one mentoring, and practical assignments. "
        "Participants will develop skills in strategic thinking, stakeholder communication, "
        "and team motivation. The program is delivered by certified coaches with experience "
        "in Fortune 500 companies. Assessment is continuous, with feedback provided after "
        "each module. Graduates receive a recognised leadership certification and access to "
        "an alumni network."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Summarise this",
            "session_id": "ses-upload-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-report.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Summary:" in summary
    assert "coaching" in summary.lower() or "leadership" in summary.lower()
    assert "compression" in summary.lower()
    assert outcome.get("output_path") is not None
    assert "worker_outputs" in outcome.get("output_path", "")


def test_chat_create_proposal_generates_proposal_structure(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Create a proposal for a coaching program",
            "session_id": "ses-proposal-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Project Proposal" in summary
    assert "Objectives" in summary
    assert "Deliverables" in summary
    assert "Timeline" in summary


def test_chat_meeting_notes_generate_actions(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Convert these meeting notes into action items: We discussed the Q4 roadmap. Action: Sarah to finalise budget by Friday. Action: Mike to schedule client reviews. Follow up on vendor selection.",
            "session_id": "ses-actions-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_human_input"
    assert data["human_input_request"] is not None
    question = data["human_input_request"].get("question", "")
    assert "analyse" in question.lower() or "area" in question.lower()


def test_chat_brainstorm_generates_ideas(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Brainstorm ideas for improving client onboarding",
            "session_id": "ses-ideas-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Brainstorm" in summary
    assert "onboarding" in summary.lower()
    assert "1." in summary


def test_chat_compare_generates_comparison(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Compare weekly coaching and self-paced learning",
            "session_id": "ses-compare-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Comparison" in summary
    assert "Weekly Coaching" in summary or "Self-Paced Learning" in summary
    assert "|" in summary


def test_chat_analyse_generates_analysis(client):
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse the quarterly report: Revenue increased 15% but churn rose to 8%.",
            "session_id": "ses-analyse-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    session_id = data["session_id"]

    resume = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume.status_code == 200
    data_resume = resume.json()
    assert data_resume["status"] == "completed"
    work_id = data_resume["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "revenue" in summary.lower() or "churn" in summary.lower()


def test_chat_plan_birthday_party_executes_with_assumptions(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Plan a birthday party for 20 people",
            "session_id": "ses-plan-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "Assumptions" in summary
    assert "birthday" in summary.lower() or "party" in summary.lower()
    assert "20" in summary
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_plan_underspecified_asks_clarification(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Plan the party",
            "session_id": "ses-clarify-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    print("DEBUG TEST: response status =", data["status"])
    assert data["status"] == "awaiting_human_input"
    assert data["human_input_request"] is not None
    question = data["human_input_request"].get("question", "")
    assert "party" in question.lower() or "event" in question.lower()
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_plan_with_explicit_constraints_executes(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Plan a birthday party for 20 people at home with a $500 budget",
            "session_id": "ses-plan-constraints-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "home" in summary.lower()
    assert "500" in summary
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_plan_clarification_then_execution(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None
    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Plan the party",
            "session_id": "ses-clarify-then-exec-1",
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_human_input"
    session_id = data1["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "A birthday party for 20 people"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "completed"
    work_id = data2["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "birthday" in summary.lower() or "party" in summary.lower()
    assert "20" in summary
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_plan_document_provides_context(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "3-day hiking trip in the Swiss Alps for two people. "
        "Accommodation in Grindelwald. Approximately 15 km hiking per day. "
        "Planned for June."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Plan this",
            "session_id": "ses-doc-plan-1",
            "context": {
                "input_text": document_text,
                "document_name": "hiking-trip.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "hiking" in summary.lower() or "trip" in summary.lower()
    assert "Assumptions" in summary
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_plan_document_missing_subject_asks_clarification(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Venue available for 50 people. Budget is $1000. " +
        "Scheduled for next month."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Plan this",
            "session_id": "ses-doc-clarify-1",
            "context": {
                "input_text": document_text,
                "document_name": "event-details.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_human_input"
    assert data["human_input_request"] is not None
    question = data["human_input_request"].get("question", "")
    assert "event" in question.lower() or "activity" in question.lower()
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "A birthday party for 50 people"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "completed"
    work_id = data2["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "birthday" in summary.lower() or "party" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_plan_indirect_document_infers_activity(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "We're planning to arrive in Interlaken on Tuesday and spend three days walking "
        "through the Bernese Oberland. There are two of us. We've booked two nights in "
        "Grindelwald. We'd like to keep the longest walking day around 15km. We have "
        "hiking boots and packs but still need to sort weather protection and food."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Plan this",
            "session_id": "ses-indirect-1",
            "context": {
                "input_text": document_text,
                "document_name": "alpine-trip-notes.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    print("DEBUG INDIRECT:", data["status"], data.get("telemetry", {}).get("work_id"))
    assert data["status"] == "completed"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Action Plan" in summary
    assert "hiking" in summary.lower() or "walking" in summary.lower()
    assert "Interlaken" in summary or "Grindelwald" in summary
    assert "15" in summary
    assert "Assumptions" in summary
    _api_mod._assistant._pending_planning_contexts.clear()


def test_chat_analyse_business_document(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-analysis-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, that's correct."},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "completed"
    work_id = data2["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "What We Know" in summary
    assert "Prioritised Focus" in summary
    assert "What Appears Connected" in summary
    assert "Why this matters" in summary
    assert "Confidence" in summary
    assert "What would validate this" in summary
    assert "12%" in summary or "retention" in summary.lower() or "support" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_unknown_focus_asks_clarification(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "The team enjoyed the offsite. We visited three locations. "
        "The weather was good. Everyone had fun."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-analysis-clarify-1",
            "context": {
                "input_text": document_text,
                "document_name": "offsite-notes.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_human_input"
    assert data["human_input_request"] is not None
    question = data["human_input_request"].get("question", "")
    assert "analyse" in question.lower() or "determine" in question.lower() or "area" in question.lower()
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Focus on team productivity and operational efficiency"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_clarification_then_execution(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-analysis-clarify-exec-1",
            "context": {
                "input_text": "The project is behind schedule.",
                "document_name": "project-status.txt",
            },
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_human_input"
    session_id = data1["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Focus on delivery risk and resource constraints"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()



def test_chat_analyse_generic_asks_clarification(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this",
            "session_id": "ses-analysis-generic-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_human_input"
    assert data["human_input_request"] is not None
    question = data["human_input_request"].get("question", "")
    assert "determine" in question.lower()
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "What should we focus on to improve growth?"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "retention" in summary.lower() or "support" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


# ---- Acceptance Criteria A-E: Four-level analysis validation -----------------


def test_acceptance_a_goal_changes_outcome(client):
    """Acceptance A: Goal validated by user materially changes output."""
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year. "
        "Customer retention fell from 84% to 76%. "
        "Support volume increased 31%."
    )
    response_a = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-goal-a",
            "context": {"input_text": document_text},
        },
    )
    assert response_a.status_code == 200
    data_a = response_a.json()
    assert data_a["status"] == "awaiting_validation"

    resume_a = client.post(
        f"/assistant/chat/{data_a['session_id']}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume_a.status_code == 200
    data_resume_a = resume_a.json()
    assert data_resume_a["status"] == "completed"
    work_id_a = data_resume_a["telemetry"]["work_id"]
    work_response_a = client.get(f"/work/{work_id_a}")
    work_data_a = work_response_a.json()
    summary_a = work_data_a["outcome"]["summary"]

    response_b = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and determine why we're losing customers",
            "session_id": "ses-goal-b",
            "context": {"input_text": document_text},
        },
    )
    assert response_b.status_code == 200
    data_b = response_b.json()
    assert data_b["status"] == "awaiting_validation"

    resume_b = client.post(
        f"/assistant/chat/{data_b['session_id']}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume_b.status_code == 200
    data_resume_b = resume_b.json()
    assert data_resume_b["status"] == "completed"
    work_id_b = data_resume_b["telemetry"]["work_id"]
    work_response_b = client.get(f"/work/{work_id_b}")
    work_data_b = work_response_b.json()
    summary_b = work_data_b["outcome"]["summary"]

    assert summary_a != summary_b
    assert "focus on" in summary_a.lower() or "management attention" in summary_a.lower()
    assert "losing customers" in summary_b.lower() or "customer" in summary_b.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()


def test_acceptance_b_hypothesis_never_presented_as_fact(client):
    """Acceptance B: Hypotheses are labelled and never presented as known facts."""
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year. "
        "Customer retention fell from 84% to 76%. "
        "Support volume increased 31%."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-hyp-b",
            "context": {"input_text": document_text},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"

    resume = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume.status_code == 200
    data_resume = resume.json()
    assert data_resume["status"] == "completed"
    work_id = data_resume["telemetry"]["work_id"]
    work_response = client.get(f"/work/{work_id}")
    work_data = work_response.json()
    summary = work_data["outcome"]["summary"]

    assert "HYPOTHESIS" in summary or "INFERRED" in summary or "KNOWN" in summary
    assert "may indicate" in summary.lower() or "suggests" in summary.lower() or "appears" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()


def test_acceptance_c_evidence_path_present(client):
    """Acceptance C: Every hypothesis has an evidence path and validation criteria."""
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year. "
        "Customer retention fell from 84% to 76%. "
        "Support volume increased 31%."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-evidence-c",
            "context": {"input_text": document_text},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"

    resume = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume.status_code == 200
    data_resume = resume.json()
    assert data_resume["status"] == "completed"
    work_id = data_resume["telemetry"]["work_id"]
    work_response = client.get(f"/work/{work_id}")
    work_data = work_response.json()
    summary = work_data["outcome"]["summary"]

    assert "Evidence Path" in summary or "Evidence:" in summary
    assert "What would validate this" in summary or "validation" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()


def test_acceptance_d_followup_uses_existing_context(client):
    """Acceptance D: Follow-up investigation reuses existing analysis context."""
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year. "
        "Customer retention fell from 84% to 76%. "
        "Support volume increased 31%."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-followup-d",
            "context": {"input_text": document_text},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"

    resume = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume.status_code == 200
    data_resume = resume.json()
    assert data_resume["status"] == "completed"
    work_id = data_resume["telemetry"]["work_id"]
    work_response = client.get(f"/work/{work_id}")
    work_data = work_response.json()
    assert work_data["status"] == "completed"

    followup = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "Why?", "investigation": True},
    )
    assert followup.status_code == 200
    data_followup = followup.json()
    assert data_followup["status"] == "completed"
    assert "investigation" in data_followup["telemetry"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()


def test_acceptance_e_progressive_questioning_supported(client):
    """Acceptance E: Progressive follow-up questioning via existing context."""
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year. "
        "Customer retention fell from 84% to 76%. "
        "Support volume increased 31%."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-progressive-e",
            "context": {"input_text": document_text},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"

    resume = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "Yes, proceed."},
    )
    assert resume.status_code == 200
    data_resume = resume.json()
    assert data_resume["status"] == "completed"
    work_id = data_resume["telemetry"]["work_id"]
    work_response = client.get(f"/work/{work_id}")
    work_data = work_response.json()
    assert work_data["status"] == "completed"

    followup1 = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "Why?", "investigation": True},
    )
    assert followup1.status_code == 200
    assert followup1.json()["status"] == "completed"

    followup2 = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "What would prove it?", "investigation": True},
    )
    assert followup2.status_code == 200
    assert followup2.json()["status"] == "completed"

    followup3 = client.post(
        f"/assistant/chat/{data['session_id']}/resume",
        json={"response": "What should I investigate next?", "investigation": True},
    )
    assert followup3.status_code == 200
    assert followup3.json()["status"] == "awaiting_validation"

    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._analysis_contexts.clear()


def test_chat_analyse_specific_goal_changes_understanding(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this to identify the biggest risks",
            "session_id": "ses-analysis-risks-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, that's correct."},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "completed"
    work_id = data2["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "biggest risks" in summary.lower() or "risks" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_incremental_context_across_turns(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )

    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this",
            "session_id": "ses-incremental-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_human_input"
    session_id = data1["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Focus on customer retention and support capacity"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "retention" in summary.lower() or "support" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_contradicts_previous_assumption(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )

    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this to identify the biggest risks",
            "session_id": "ses-contradict-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_validation"
    session_id = data1["session_id"]

    response1c = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, that's correct."},
    )
    assert response1c.status_code == 200
    data1c = response1c.json()
    assert data1c["status"] == "completed"
    work_id_1 = data1c["telemetry"]["work_id"]

    work_response_1 = client.get(f"/work/{work_id_1}")
    assert work_response_1.status_code == 200
    summary_1 = work_response_1.json()["outcome"]["summary"]
    assert "biggest risks" in summary_1.lower() or "risks" in summary_1.lower()

    response2 = client.post(
        "/assistant/chat",
        json={
            "message": "Actually, no — analyse this to improve growth",
            "session_id": "ses-contradict-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response2c = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response2c.status_code == 200
    data2c = response2c.json()
    assert data2c["status"] == "completed"
    work_id_2 = data2c["telemetry"]["work_id"]

    work_response_2 = client.get(f"/work/{work_id_2}")
    assert work_response_2.status_code == 200
    summary_2 = work_response_2.json()["outcome"]["summary"]
    assert "improve growth" in summary_2.lower() or "growth" in summary_2.lower()
    assert "biggest risks" not in summary_2.lower() or "risks" not in summary_2.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_two_turn_accumulates_document_and_goal(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )

    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this",
            "session_id": "ses-accumulate-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_human_input"
    session_id = data1["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "What should I focus on to improve growth?"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "improve growth" in summary.lower() or "growth" in summary.lower()
    assert "retention" in summary.lower() or "revenue" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


# ---- Context Validation Loop Tests (6 new tests) -----------------------------


def test_chat_analyse_validation_confirm_proceeds_to_execution(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-val-confirm-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    assert "I understand you want to" in data["message"]
    assert data["human_input_request"]["validation_type"] == "analysis_understanding"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "completed"
    work_id = data2["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_validation_update_revises_understanding(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-val-update-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Also consider the impact on employee morale."},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    assert "Updated understanding" in data2["message"]
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_validation_contradict_replaces_interpretation(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this to identify the biggest risks",
            "session_id": "ses-val-contradict-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Actually, no — analyse this to improve growth"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    assert "Revised understanding" in data2["message"]
    assert "improve growth" in data2["message"].lower()
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "completed"
    work_id = data3["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    summary = work_data["outcome"]["summary"]
    assert "improve growth" in summary.lower() or "growth" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_validation_clarify_returns_to_pending(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this and tell me what I should focus on",
            "session_id": "ses-val-clarify-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_validation"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Can you clarify what you mean by focus areas?"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_human_input"
    assert "clarify" in data2["message"].lower() or "What would you like me to clarify" in data2["message"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_contradiction_via_new_message_replaces_understanding(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this to identify the biggest risks",
            "session_id": "ses-val-msg-contradict-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_validation"
    session_id = data1["session_id"]

    response1c = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response1c.status_code == 200
    data1c = response1c.json()
    assert data1c["status"] == "completed"
    work_id_1 = data1c["telemetry"]["work_id"]

    work_response_1 = client.get(f"/work/{work_id_1}")
    assert work_response_1.status_code == 200
    summary_1 = work_response_1.json()["outcome"]["summary"]
    assert "biggest risks" in summary_1.lower() or "risks" in summary_1.lower()

    response2 = client.post(
        "/assistant/chat",
        json={
            "message": "Actually, no — analyse this to improve growth",
            "session_id": "ses-val-msg-contradict-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    assert "improve growth" in data2["message"].lower()
    session_id = data2["session_id"]

    response2c = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response2c.status_code == 200
    data2c = response2c.json()
    assert data2c["status"] == "completed"
    work_id_2 = data2c["telemetry"]["work_id"]

    work_response_2 = client.get(f"/work/{work_id_2}")
    assert work_response_2.status_code == 200
    summary_2 = work_response_2.json()["outcome"]["summary"]
    assert "improve growth" in summary_2.lower() or "growth" in summary_2.lower()
    assert "biggest risks" not in summary_2.lower() or "risks" not in summary_2.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_three_turn_context_evolution(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    response1 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this",
            "session_id": "ses-three-turn-1",
        },
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "awaiting_human_input"
    session_id = data1["session_id"]

    response2 = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this, revenue declined 12% and retention fell from 84% to 76%",
            "session_id": session_id,
        },
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_human_input"
    session_id = data2["session_id"]

    response3 = client.post(
        "/assistant/chat",
        json={
            "message": "What should I focus on?",
            "session_id": session_id,
        },
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "awaiting_validation"
    session_id = data3["session_id"]

    response4 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response4.status_code == 200
    data4 = response4.json()
    assert data4["status"] == "completed"
    work_id = data4["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "revenue" in summary.lower()
    assert "retention" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()


def test_chat_analyse_validation_full_loop_with_document_and_update(client):
    import sys
    _api_mod = sys.modules["workflow_runner_api"]
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
    _api_mod._assistant._capability_discovery = None
    _api_mod._assistant._enterprise_capability_query = None

    document_text = (
        "Q3 revenue declined 12% year-on-year, driven by lower enterprise renewals. "
        "Customer retention fell from 84% to 76%. Support volume increased 31%, "
        "with average response time rising from 2 hours to 8 hours. "
        "NPS dropped from 45 to 28. Two new competitors entered the market last quarter. "
        "Headcount is frozen until Q4."
    )
    response = client.post(
        "/assistant/chat",
        json={
            "message": "Analyse this",
            "session_id": "ses-val-loop-1",
            "context": {
                "input_text": document_text,
                "document_name": "quarterly-business-review.txt",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_human_input"
    session_id = data["session_id"]

    response2 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Focus on customer retention and support capacity"},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "awaiting_validation"
    session_id = data2["session_id"]

    response3 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Also include the impact on employee morale."},
    )
    assert response3.status_code == 200
    data3 = response3.json()
    assert data3["status"] == "awaiting_validation"
    assert "Updated understanding" in data3["message"]
    session_id = data3["session_id"]

    response4 = client.post(
        f"/assistant/chat/{session_id}/resume",
        json={"response": "Yes, proceed."},
    )
    assert response4.status_code == 200
    data4 = response4.json()
    assert data4["status"] == "completed"
    work_id = data4["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "completed"
    outcome = work_data["outcome"]
    assert outcome is not None
    summary = outcome.get("summary", "")
    assert "Analysis" in summary
    assert "retention" in summary.lower() or "support" in summary.lower()
    _api_mod._assistant._pending_planning_contexts.clear()
    _api_mod._assistant._validation_contexts.clear()
