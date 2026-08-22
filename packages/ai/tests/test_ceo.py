"""
TDD tests for Increment 6 — CEO Orchestrator.

Contracts: ARCHITECTURE-ASSESSMENT-2026-08-21.md Increment 6.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from ceo import CEOAgent
from concepts import ConceptStore


# ---- CEOAgent boundary tests -------------------------------------------------


def test_ceo_agent_receives_org_plane_via_di() -> None:
    org_plane = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)
    assert ceo._org is org_plane


def test_ceo_agent_uses_org_plane_for_context(tmp_path) -> None:
    org_plane = MagicMock()
    store = ConceptStore(data_dir=str(tmp_path))
    ceo = CEOAgent(org_plane=org_plane, concept_store=store)

    org_context = MagicMock()
    org_plane.get_organisational_context.return_value = org_context

    ceo.orchestrate({"message": "Do something novel", "context": {}})
    org_plane.get_organisational_context.assert_called_once_with(
        {"message": "Do something novel", "context": {}}
    )


def test_ceo_agent_does_not_instantiate_capability_registry(tmp_path) -> None:
    org_plane = MagicMock()
    store = ConceptStore(data_dir=str(tmp_path))
    ceo = CEOAgent(org_plane=org_plane, concept_store=store)

    assert not hasattr(ceo, "_registry")


def test_ceo_agent_does_not_contain_match_capabilities() -> None:
    org_plane = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)
    assert not hasattr(ceo, "_match_capabilities")


def test_ceo_agent_escalates_when_confidence_low() -> None:
    org_plane = MagicMock()
    org_plane.get_organisational_context.return_value = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)

    response = ceo.orchestrate({"message": "xyzzy unknown nonsense", "context": {}})

    assert response["status"] == "awaiting_human_input"
    assert response["human_input_request"] is not None
    assert response["telemetry"]["ceo_escalated"] is True
    assert response["telemetry"]["delegated_to"] == "human"
    assert response["telemetry"]["escalation_reason"] == "low_confidence"


def test_ceo_agent_reuses_previous_solution(tmp_path) -> None:
    org_plane = MagicMock()
    org_plane.get_organisational_context.return_value = MagicMock()
    store = ConceptStore(data_dir=str(tmp_path))
    from concepts import ConceptKind, EnterpriseConcept

    concept = EnterpriseConcept(
        id="sol-1",
        kind=ConceptKind.CAPABILITY,
        name="previous-solution",
        description="A previous solution",
        tags=["solution", "strategy:recognise_and_reuse"],
        payload={
            "summary": "Ran daily report successfully",
            "maturation_history": {"invocation_count": 2, "correction_count": 0},
        },
    )
    store.upsert(concept)

    ceo = CEOAgent(org_plane=org_plane, concept_store=store)
    response = ceo.orchestrate({"message": "Run the daily report", "context": {}})

    assert response["status"] == "awaiting_confirmation"
    assert response["previous_solution"] is not None
    assert response["previous_solution"]["summary"] == "Ran daily report successfully"
    assert response["telemetry"]["ceo_reused"] is True
    assert response["telemetry"]["delegated_to"] == "cache"


def test_ceo_agent_delegates_execution_when_no_previous_solution() -> None:
    org_plane = MagicMock()
    org_plane.get_organisational_context.return_value = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)

    response = ceo.orchestrate({"message": "Do something novel", "context": {}})

    assert response["status"] == "pending"
    assert response["telemetry"]["ceo_delegated"] is True
    assert response["telemetry"]["step"] == "execute"


def test_ceo_agent_assigns_session_id() -> None:
    org_plane = MagicMock()
    org_plane.get_organisational_context.return_value = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)
    response = ceo.orchestrate({"message": "Hello", "context": {}})

    assert response["session_id"].startswith("ses-")
