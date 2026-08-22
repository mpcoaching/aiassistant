"""
Tests for CapabilityRequest governance model and approval API (Increment 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from capability_request import CapabilityRequest
from capability import Parameter
from concepts import (
    ConceptKind,
    ConceptStore,
    EnterpriseConcept,
    Provenance,
    RecognitionLevel,
)


# ---- CapabilityRequest model tests ----

def test_capability_request_defaults():
    req = CapabilityRequest(name="test", purpose="test purpose")
    assert req.status == "pending"
    assert req.requester == "user"
    assert req.inputs == []
    assert req.outputs == []
    assert req.acceptance_criteria == []
    assert req.governance == {}


def test_capability_request_approve():
    req = CapabilityRequest(name="test", purpose="test purpose")
    req.approve(approver="alice", rationale="needed")
    assert req.status == "approved"
    assert req.governance["approved_by"] == "alice"
    assert req.governance["rationale"] == "needed"
    assert "approved_at" in req.governance


def test_capability_request_reject():
    req = CapabilityRequest(name="test", purpose="test purpose")
    req.reject(rejector="bob", rationale="out of scope")
    assert req.status == "rejected"
    assert req.governance["rejected_by"] == "bob"
    assert req.governance["rationale"] == "out of scope"


def test_capability_request_modify():
    req = CapabilityRequest(
        name="old",
        purpose="old purpose",
        inputs=[Parameter(name="x", type="string")],
    )
    req.modify(
        name="new",
        purpose="new purpose",
        inputs=[Parameter(name="y", type="int")],
        modified_by="charlie",
    )
    assert req.name == "new"
    assert req.purpose == "new purpose"
    assert req.inputs[0].name == "y"
    assert req.governance["action"] == "modified"
    assert req.governance["modified_by"] == "charlie"


def test_capability_request_lifecycle_sequence():
    req = CapabilityRequest(name="test", purpose="test")
    assert req.status == "pending"
    req.modify(name="test-v2", modified_by="alice")
    assert req.name == "test-v2"
    req.approve(approver="bob", rationale="ok")
    assert req.status == "approved"
    with pytest.raises(AssertionError):
        req.reject(rejector="charlie")


# ---- EnterpriseConcept promotion tests ----

def _approved_concept(tmp_path: Path) -> EnterpriseConcept:
    req = CapabilityRequest(
        name="create_test_artifact",
        purpose="Creates a test artifact",
        inputs=[Parameter(name="label", type="string")],
        outputs=[Parameter(name="artifact_id", type="string")],
        acceptance_criteria=["creates concept", "returns artifact_id"],
        requester="test_user",
        request_id="req-123",
    )
    req.approve(approver="test_approver", rationale="prove lifecycle")
    from datetime import datetime, timezone
    concept = EnterpriseConcept(
        id=f"cap-{req.name.lower().replace(' ', '-')}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        kind=ConceptKind.CAPABILITY,
        name=req.name,
        description=req.purpose,
        owner=req.requester,
        created_by="test_approver",
        status="draft",
        tags=["capability-request", "draft"],
        provenance=Provenance(
            source_session_id=req.request_id,
            recognition_level=RecognitionLevel.SYNTHESIS,
        ),
        payload={
            "capability_request": req.model_dump(mode="json"),
            "governance": req.governance,
        },
    )
    return concept, req


def test_approved_concept_has_correct_status(tmp_path: Path):
    concept, req = _approved_concept(tmp_path)
    assert concept.kind == ConceptKind.CAPABILITY
    assert concept.status == "draft"


def test_approved_concept_preserves_governance(tmp_path: Path):
    concept, req = _approved_concept(tmp_path)
    assert concept.payload["governance"]["approved_by"] == "test_approver"
    assert concept.payload["governance"]["rationale"] == "prove lifecycle"
    assert concept.payload["governance"]["action"] == "approved"


def test_approved_concept_preserves_specification(tmp_path: Path):
    concept, req = _approved_concept(tmp_path)
    stored_req = concept.payload["capability_request"]
    assert stored_req["name"] == "create_test_artifact"
    assert stored_req["purpose"] == "Creates a test artifact"
    assert len(stored_req["inputs"]) == 1
    assert stored_req["inputs"][0]["name"] == "label"


def test_approved_concept_persists(tmp_path: Path):
    concept, req = _approved_concept(tmp_path)
    store = ConceptStore(data_dir=str(tmp_path))
    store.upsert(concept)
    retrieved = store.get(concept.id)
    assert retrieved is not None
    assert retrieved.name == "create_test_artifact"
    assert retrieved.status == "draft"


def test_rejection_does_not_create_active_capability():
    req = CapabilityRequest(name="bad", purpose="bad")
    req.reject(rejector="alice", rationale="nope")
    assert req.status == "rejected"
    assert req.governance["action"] == "rejected"


# ---- API endpoint tests ----

def _client():
    from workflow_runner.api import app
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock, patch

    with patch("workflow_runner.api.EventBus") as MockBus, \
         patch("workflow_runner.api._build_scheduler") as mock_build:
        mock_bus = MagicMock()
        mock_bus.declare_topology = MagicMock()
        mock_bus.start_consumers = MagicMock()
        mock_bus.shutdown = MagicMock()
        MockBus.return_value = mock_bus

        mock_sched = MagicMock()
        mock_sched.get_jobs.return_value = []
        mock_build.return_value = mock_sched

        with TestClient(app) as c:
            yield c


def test_approve_endpoint_creates_draft_concept():
    client = next(_client())
    req_payload = {
        "name": "api_test_cap",
        "purpose": "API test capability",
        "inputs": [{"name": "x", "type": "string", "required": True, "description": "input"}],
        "outputs": [{"name": "result", "type": "string", "required": True, "description": "output"}],
        "acceptance_criteria": ["returns result"],
        "requester": "api_tester",
        "request_id": "req-api-1",
    }
    resp = client.post(
        "/assistant/capability-request/req-api-1/approve",
        json={
            "request_id": "req-api-1",
            "action": "approve",
            "capability_request": req_payload,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "approved"
    assert data["status"] == "draft"
    assert data["concept_id"] is not None
    assert data["message"] == "Capability request approved. Implementation pending."
    assert data["governance"]["approved_by"] == "api_tester"


def test_reject_endpoint_does_not_create_concept():
    client = next(_client())
    req_payload = {
        "name": "reject_cap",
        "purpose": "should be rejected",
        "requester": "api_tester",
        "request_id": "req-api-2",
    }
    resp = client.post(
        "/assistant/capability-request/req-api-2/approve",
        json={
            "request_id": "req-api-2",
            "action": "reject",
            "capability_request": req_payload,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "rejected"
    assert data["concept_id"] is None
    assert data["status"] == "rejected"


def test_modify_endpoint_updates_specification():
    client = next(_client())
    original = {
        "name": "original_name",
        "purpose": "original purpose",
        "inputs": [{"name": "x", "type": "string", "required": True, "description": ""}],
        "outputs": [{"name": "y", "type": "string", "required": True, "description": ""}],
        "acceptance_criteria": ["old"],
        "requester": "api_tester",
        "request_id": "req-api-3",
    }
    modified = {
        "name": "modified_name",
        "purpose": "modified purpose",
        "inputs": [{"name": "z", "type": "int", "required": True, "description": ""}],
        "outputs": [{"name": "w", "type": "int", "required": True, "description": ""}],
        "acceptance_criteria": ["new"],
        "requester": "api_tester",
    }
    resp = client.post(
        "/assistant/capability-request/req-api-3/approve",
        json={
            "request_id": "req-api-3",
            "action": "modify",
            "capability_request": original,
            "modified_spec": modified,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "approved"
    assert data["status"] == "draft"
    concept_id = data["concept_id"]
    assert concept_id is not None
    assert "modified_name" in concept_id


def test_approve_without_server_side_state():
    """Stateless approval: server has no prior copy of the request."""
    client = next(_client())
    req_payload = {
        "name": "stateless_cap",
        "purpose": "proves stateless approval",
        "inputs": [{"name": "label", "type": "string", "required": True, "description": ""}],
        "outputs": [{"name": "artifact_id", "type": "string", "required": True, "description": ""}],
        "acceptance_criteria": ["creates concept"],
        "requester": "stateless_user",
        "request_id": "req-stateless-1",
    }
    resp = client.post(
        "/assistant/capability-request/req-stateless-1/approve",
        json={
            "request_id": "req-stateless-1",
            "action": "approve",
            "capability_request": req_payload,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "approved"
    assert data["concept_id"] is not None
    assert "stateless_cap" in data["concept_id"]


def test_approve_request_id_mismatch():
    client = next(_client())
    req_payload = {
        "name": "mismatch",
        "purpose": "test",
        "requester": "user",
        "request_id": "req-1",
    }
    resp = client.post(
        "/assistant/capability-request/req-2/approve",
        json={
            "request_id": "req-1",
            "action": "approve",
            "capability_request": req_payload,
        },
    )
    assert resp.status_code == 400
    assert "mismatch" in resp.json()["detail"]


def test_approve_invalid_capability_request():
    client = next(_client())
    resp = client.post(
        "/assistant/capability-request/req-bad/approve",
        json={
            "request_id": "req-bad",
            "action": "approve",
            "capability_request": {"invalid": "payload"},
        },
    )
    assert resp.status_code == 400
    assert "Invalid CapabilityRequest" in resp.json()["detail"]


def test_approve_missing_capability_request():
    client = next(_client())
    resp = client.post(
        "/assistant/capability-request/req-empty/approve",
        json={
            "request_id": "req-empty",
            "action": "approve",
            "capability_request": None,
        },
    )
    assert resp.status_code == 400
    assert "capability_request is required" in resp.json()["detail"]


def test_modify_without_modified_spec():
    client = next(_client())
    req_payload = {
        "name": "mod",
        "purpose": "test",
        "requester": "user",
        "request_id": "req-mod",
    }
    resp = client.post(
        "/assistant/capability-request/req-mod/approve",
        json={
            "request_id": "req-mod",
            "action": "modify",
            "capability_request": req_payload,
            "modified_spec": None,
        },
    )
    assert resp.status_code == 400
    assert "modified_spec required" in resp.json()["detail"]


def test_unsupported_action():
    client = next(_client())
    req_payload = {
        "name": "bad",
        "purpose": "test",
        "requester": "user",
        "request_id": "req-bad-action",
    }
    resp = client.post(
        "/assistant/capability-request/req-bad-action/approve",
        json={
            "request_id": "req-bad-action",
            "action": "delete",
            "capability_request": req_payload,
        },
    )
    assert resp.status_code == 400
    assert "Unsupported action" in resp.json()["detail"]
