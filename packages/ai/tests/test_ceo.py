"""
TDD tests for Increment 6 — CEO Orchestrator.

Contracts: ARCHITECTURE-ASSESSMENT-2026-08-21.md Increment 6.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from ceo import CEOAgent


# ---- CEOAgent boundary tests -------------------------------------------------


def test_ceo_agent_receives_org_plane_via_di() -> None:
    org_plane = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)
    assert ceo._org is org_plane


def test_ceo_agent_uses_org_plane_for_context(tmp_path) -> None:
    org_plane = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)

    org_context = MagicMock()
    org_plane.get_organisational_context.return_value = org_context

    ceo.orchestrate({"message": "Do something novel", "context": {}})
    org_plane.get_organisational_context.assert_called_once_with(
        {"message": "Do something novel", "context": {}}
    )


def test_ceo_agent_does_not_instantiate_capability_registry() -> None:
    org_plane = MagicMock()
    ceo = CEOAgent(org_plane=org_plane)

    assert not hasattr(ceo, "_registry")
    assert not hasattr(ceo, "_store")


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
    from ai.tests.fixtures.in_memory_ports import InMemoryEnterpriseInformationPort
    from ports.enterprise_information import PreviousSolution

    org_plane = MagicMock()
    org_plane.get_organisational_context.return_value = MagicMock()

    previous = PreviousSolution(
        concept_id="sol-1",
        name="strategy:recognise_and_reuse",
        summary="Ran daily report successfully",
        invocation_count=2,
        last_invoked=None,
    )
    enterprise_info = InMemoryEnterpriseInformationPort(solutions=[previous])

    ceo = CEOAgent(org_plane=org_plane, enterprise_information=enterprise_info)
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
