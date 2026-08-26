"""
Tests for POST /assistant/capability/{capability_id}//execute (Increment 5).
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


# ---- Work Management / Enterprise Plane Integration -----------------------


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
    with patch("workflow_runner_api._org_plane") as mock_org:
        from organisation.src.role import Work, WorkStatus
        work = Work(id="w1", title="Test task", accountable_role_id="r1", description="Test description")
        mock_org.get_work.return_value = work
        mock_org._work = {"w1": work}

        with patch("workflow_runner_api.Worker") as MockWorker:
            mock_worker = MockWorker.return_value
            mock_worker.execute.return_value = {
                "status": "completed",
                "summary": "Worker processed: Test task",
                "output_path": "worker_outputs/w1-test-task.md",
                "output_type": "markdown",
                "work_id": "w1",
                "title": "Test task",
                "description": "Test description",
            }

            response = client.post("/work/w1/process")
            assert response.status_code == 200
            data = response.json()
            assert data["work_id"] == "w1"
            assert data["status"] == "completed"
            assert data["outcome"]["summary"] == "Worker processed: Test task"
            assert data["outcome"]["output_path"] == "worker_outputs/w1-test-task.md"
            mock_worker.execute.assert_called_once_with(work, mock_org)


def test_work_endpoints_501_when_org_plane_not_configured(client):
    with patch("workflow_runner_api._org_plane", None):
        response = client.get("/work")
        assert response.status_code == 501

        response = client.get("/work/w1")
        assert response.status_code == 501

        response = client.post("/work/w1/process")
        assert response.status_code == 501

        response = client.post("/worker/run")
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
    with patch("workflow_runner_api._org_plane") as mock_org:
        from organisation.src.role import Work, WorkStatus
        work = Work(id="w1", title="Worker task", accountable_role_id="default", assignee_agent_id="worker-agent")
        mock_org.list_work.return_value = [work]
        mock_org.get_work.return_value = work
        mock_org._work = {"w1": work}

        with patch("workflow_runner_api.Worker") as MockWorker:
            mock_worker = MockWorker.return_value
            mock_worker.pickup.return_value = work
            mock_worker.execute.return_value = {
                "status": "completed",
                "summary": "Worker pickup complete",
                "output_path": "worker_outputs/w1.md",
                "output_type": "markdown",
                "work_id": "w1",
            }

            response = client.post("/worker/run")
            assert response.status_code == 200
            data = response.json()
            assert data["work_id"] == "w1"
            assert data["status"] == "completed"
            mock_worker.pickup.assert_called_once_with(mock_org)
            mock_worker.execute.assert_called_once_with(work, mock_org)


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
    assert data["status"] == "delegated"
    work_id = data["telemetry"]["work_id"]

    work_response = client.get(f"/work/{work_id}")
    assert work_response.status_code == 200
    work_data = work_response.json()
    assert work_data["status"] == "assigned"


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
    wr_api_mod._assistant._capability_discovery = mock_discovery
    
    mock_availability = MagicMock()
    mock_availability.available = True
    mock_availability.eta_seconds = 300
    mock_availability.assignee = None
    mock_availability.reason = "Busy"
    wr_api_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
        return_value=mock_availability
    )

    response = client.post(
        "/assistant/chat",
        json={"message": "do something slow", "session_id": "ses-slow-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "delegated_with_interim"
    assert "preliminary answer" in data["message"]


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
    api_mod._assistant._capability_discovery = mock_discovery
    api_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
        return_value=None
    )

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
    wr_mod._assistant._capability_discovery = mock_discovery
    wr_mod._assistant._enterprise_capability_query.query_capability = MagicMock(
        return_value=None
    )

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

    process_response = client.post(f"/work/{work_id}/process")
    assert process_response.status_code == 200
    worker_data = process_response.json()
    assert worker_data["status"] == "completed"
    assert worker_data["outcome"]["execution_mode"] == "capability_development"

    developed_cap_id = worker_data["outcome"]["capability_id"]
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
    assert data2["status"] == "delegated"
    assert developed_cap_id in data2["telemetry"]["required_capability_ids"]
