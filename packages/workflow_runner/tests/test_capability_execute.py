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
        mock_org.list_roles.return_value = []
        response = client.get("/work")
        assert response.status_code == 200
        assert response.json() == []


def test_get_work_returns_404_when_missing(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        mock_org.get_work.return_value = None
        response = client.get("/work/missing-id")
        assert response.status_code == 404


def test_process_work_marks_completed(client):
    with patch("workflow_runner_api._org_plane") as mock_org:
        from organisation.src.role import Work, WorkStatus
        work = Work(id="w1", title="Test task", accountable_role_id="r1")
        mock_org.get_work.return_value = work
        mock_org._work = {"w1": work}

        response = client.post("/work/w1/process")
        assert response.status_code == 200
        data = response.json()
        assert data["work_id"] == "w1"
        assert data["status"] == "completed"
        assert work.status == WorkStatus.COMPLETED


def test_work_endpoints_501_when_org_plane_not_configured(client):
    with patch("workflow_runner_api._org_plane", None):
        response = client.get("/work")
        assert response.status_code == 501

        response = client.get("/work/w1")
        assert response.status_code == 501

        response = client.post("/work/w1/process")
        assert response.status_code == 501
