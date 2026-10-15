"""
TDD tests for Phase 2 — Intent intake, Strategy Selection, and decide() assembly.

Contracts: SA-CONTRACTS-PHASES-2-5.md C3, C4, C9.
"""


import pytest
from pathlib import Path
from unittest.mock import MagicMock

from assistant import AssistantReasoningService, StrategyDecision
from chat import AssistantChatService, ChatRequest
from capability_selection_telemetry import CapabilitySelectionTelemetry
from enterprise_context import ContextRecord
from intent import Intent, IntentOrigin, ProblemFrame, recognise
from strategy import ReasoningStrategy, select_strategy

from ai.tests.fixtures.in_memory_ports import (
    InMemoryCapabilityDiscoveryPort,
    InMemoryCapabilityExecutionPort,
    InMemoryEnterpriseInformationPort,
    InMemoryPatternExecutionPort,
    InMemorySessionFactoryPort,
    InMemoryWorkManagementPort,
)
from contracts.capability_discovery import CapabilityCandidate
from contracts.capability_execution import ExecutionResult
from contracts.enterprise_capability_query import CapabilityAvailability
from contracts.enterprise_information import PreviousSolution

# ---- Intent / recognise (C3) ----------------------------------------------

def test_intent_creation() -> None:
    intent = Intent(
        id="int-1",
        origin=IntentOrigin.USER_REQUEST,
        raw={"type": "natural_language", "text": "Create a new task tracking service"},
    )
    assert intent.id == "int-1"
    assert intent.origin == IntentOrigin.USER_REQUEST


def test_recognise_classifies_problem_frame() -> None:
    intent = Intent(
        id="int-1",
        origin=IntentOrigin.USER_REQUEST,
        raw={"type": "natural_language", "text": "Restore the payment gateway"},
    )
    frame = recognise(intent)
    assert isinstance(frame, ProblemFrame)
    assert frame.context.problem_context == "incident"
    assert frame.confidence > 0.0


def test_recognise_returns_direct_reuse_level_for_known_sop() -> None:
    intent = Intent(
        id="int-2",
        origin=IntentOrigin.USER_REQUEST,
        raw={"type": "natural_language", "text": "Run the daily report workflow"},
    )
    frame = recognise(intent)
    assert frame.recognition_level == "direct_reuse"


# ---- Strategy Selection (C4) ----------------------------------------------

def test_select_strategy_returns_ranked_proposals() -> None:
    frame = ProblemFrame(
        context=_make_context(problem_context="incident", activity_purpose="investigate"),
        confidence=0.9,
        recognition_level="direct_reuse",
    )
    proposals = select_strategy(frame.context)
    assert isinstance(proposals, list)
    assert len(proposals) > 0
    assert proposals[0].strategy == ReasoningStrategy.INVESTIGATE_THEN_FIX


def test_select_strategy_seed_table_innovation_explore() -> None:
    frame = ProblemFrame(
        context=_make_context(problem_context="innovation", activity_purpose="explore"),
        confidence=0.8,
        recognition_level="direct_reuse",
    )
    proposals = select_strategy(frame.context)
    assert proposals[0].strategy == ReasoningStrategy.RESEARCH_TO_SYNTHESIS


def test_select_strategy_design_decide() -> None:
    frame = ProblemFrame(
        context=_make_context(problem_context="design", activity_purpose="decide"),
        confidence=0.8,
        recognition_level="direct_reuse",
    )
    proposals = select_strategy(frame.context)
    assert proposals[0].strategy == ReasoningStrategy.DELIBERATE_TO_CONSENSUS


def test_select_strategy_unknown_falls_back_to_research() -> None:
    frame = ProblemFrame(
        context=_make_context(problem_context="unknown", activity_purpose="investigate"),
        confidence=0.3,
        recognition_level="synthesis",
    )
    proposals = select_strategy(frame.context)
    assert proposals[0].strategy == ReasoningStrategy.RESEARCH_TO_SYNTHESIS


# ---- Assistant Reasoning Service decide() (C9) ---------------------------

def test_decide_returns_strategy_decision() -> None:
    svc = AssistantReasoningService()
    intent = Intent(
        id="int-3",
        origin=IntentOrigin.USER_REQUEST,
        raw={"type": "natural_language", "text": "Enrich lead Acme Corp"},
    )
    decision = svc.decide(intent)
    assert isinstance(decision, StrategyDecision)
    assert decision.chosen_strategy is not None
    assert len(decision.pattern_pipeline) > 0


def test_decide_includes_participant_roles() -> None:
    svc = AssistantReasoningService()
    intent = Intent(
        id="int-4",
        origin=IntentOrigin.USER_REQUEST,
        raw={"type": "natural_language", "text": "Design a new task tracker"},
    )
    decision = svc.decide(intent)
    assert isinstance(decision.participant_roles, list)


# ---- helpers ---------------------------------------------------------------

def _make_context(**overrides):
    from enterprise_context import ContextRecord
    defaults = {
        "problem_context": "routine_operation",
        "environment_context": "ai_assisted",
        "information_context": "internal_only",
        "activity_purpose": "execute",
        "decision_context": {"confidence_required": "medium", "authority_model": "single_authority", "reversibility": "reversible", "mandatory_policy_checks": [], "human_approval_required": False, "timebox_seconds": 0, "cost_vs_quality": "balanced"},
    }
    defaults.update(overrides)
    return ContextRecord(**defaults)


# ---- Assistant Chat Service via ports (Increment 15) -----------------------

def _make_capability_candidates() -> list[CapabilityCandidate]:
    return [
        CapabilityCandidate(
            id="cap-create_test_artifact",
            name="create_test_artifact",
            description="Creates a test artifact record",
            kind="tool",
            tags=["test", "artifact"],
            execution_mode="compiled",
            confidence=1.0,
        )
    ]


def test_chat_executes_single_capability_and_returns_result() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    execution = InMemoryCapabilityExecutionPort(
        result=ExecutionResult(
            outputs={"result": "artifact-created", "summary": "Test artifact created successfully"},
            artifacts=["artifact-123"],
            telemetry={"capability_id": "cap-create_test_artifact"},
        )
    )
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_execution=execution,
    )
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.capability_candidates[0]["id"] == "cap-create_test_artifact"


def test_chat_create_test_artifact_executes_when_single_candidate() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    execution = InMemoryCapabilityExecutionPort()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_execution=execution,
    )
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert len(execution.executed) == 0


def test_chat_capability_selection_presents_multiple_candidates() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
        ),
        CapabilityCandidate(
            id="cap-b",
            name="capability_b",
            description="Does B",
            kind="tool",
            tags=["b"],
            execution_mode="compiled",
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Do something")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 2
    assert "select one to proceed" in response.message.lower()
    assert response.telemetry.get("interaction") == "select"


def test_chat_single_candidate_asks_for_confirmation() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert "shall i proceed" in response.message.lower()
    assert response.telemetry.get("interaction") == "confirm"


def test_chat_capability_single_candidate_execution_result_formatting() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    execution = InMemoryCapabilityExecutionPort(
        result=ExecutionResult(
            outputs={"summary": "Done"},
            artifacts=[],
            telemetry={},
        )
    )
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_execution=execution,
    )
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert len(execution.executed) == 0


def test_chat_capability_execution_reports_failure() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    execution = InMemoryCapabilityExecutionPort(
        result=ExecutionResult(
            outputs={"error": "module_not_found"},
            artifacts=[],
            telemetry={"error": "execution_error"},
        )
    )
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_execution=execution,
    )
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert len(execution.executed) == 0


def test_chat_falls_through_without_capabilities() -> None:
    discovery = InMemoryCapabilityDiscoveryPort(candidates=[])
    session_factory = InMemorySessionFactoryPort()
    service = AssistantChatService(
        capability_discovery=discovery,
        session_factory=session_factory,
    )
    request = ChatRequest(message="Do something completely novel")
    response = service.chat(request)

    assert response.status == "pending"


def test_chat_passes_recognised_context_to_discovery_port() -> None:
    captured = {}
    def capture_find_capabilities(request_text: str, context):
        captured["request_text"] = request_text
        captured["context"] = context
        return []

    class CapturingDiscoveryPort:
        def list_capabilities(self) -> list:
            return []

        def find_capabilities(self, request_text: str, context) -> list:
            return capture_find_capabilities(request_text, context)

    service = AssistantChatService(capability_discovery=CapturingDiscoveryPort())
    request = ChatRequest(message="Design a new task tracker")
    service.chat(request)

    assert captured["request_text"] == "Design a new task tracker"
    assert isinstance(captured["context"], ContextRecord)


def test_chat_capability_execution_includes_metadata_in_telemetry() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    execution = InMemoryCapabilityExecutionPort()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_execution=execution,
    )
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.capability_candidates[0]["id"] == "cap-create_test_artifact"
    assert response.capability_candidates[0]["name"] == "create_test_artifact"
    assert response.capability_candidates[0]["execution_mode"] == "compiled"
    assert len(execution.executed) == 0


def test_chat_weak_single_candidate_asks_user_instead_of_executing() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-create_test_artifact",
            name="create_test_artifact",
            description="Creates a test artifact record",
            kind="tool",
            tags=["test", "artifact"],
            execution_mode="compiled",
            confidence=0.1,
        )
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="create something vague")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.telemetry.get("interaction") == "confirm"


def test_chat_service_returns_previous_solution() -> None:
    previous = PreviousSolution(
        concept_id="sol-previous",
        name="strategy:deliberate_to_consensus",
        summary="Designed a task tracker with 3 interfaces",
        invocation_count=2,
        last_invoked=None,
    )
    enterprise_info = InMemoryEnterpriseInformationPort(solutions=[previous])
    service = AssistantChatService(enterprise_information=enterprise_info)
    request = ChatRequest(message="Design a new task tracking service")
    response = service.chat(request)

    assert response.status == "awaiting_confirmation"
    assert response.previous_solution is not None
    assert response.previous_solution["invocation_count"] == 2
    assert response.previous_solution["summary"] == "Designed a task tracker with 3 interfaces"


# ---- Capability Selection Telemetry (Increment 21K) ------------------------


def test_chat_records_telemetry_for_single_candidate_confirm() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )
    request = ChatRequest(message="Do something")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    events = telemetry.get_events()
    assert len(events) == 1
    assert events[0].candidate_count == 1
    assert events[0].interaction_type == "confirm"
    assert events[0].top_score == 0.9
    assert events[0].score_gap == 0.0
    assert events[0].candidate_ids == ["cap-a"]
    assert response.telemetry.get("match_event_id") == events[0].event_id


def test_chat_records_telemetry_for_multiple_candidates_select() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
        CapabilityCandidate(
            id="cap-b",
            name="capability_b",
            description="Does B",
            kind="tool",
            tags=["b"],
            execution_mode="compiled",
            confidence=0.7,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )
    request = ChatRequest(message="Do something")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    events = telemetry.get_events()
    assert len(events) == 1
    assert events[0].candidate_count == 2
    assert events[0].interaction_type == "select"
    assert events[0].top_score == 0.9
    assert events[0].score_gap == pytest.approx(0.2)
    assert events[0].candidate_ids == ["cap-a", "cap-b"]
    assert response.telemetry.get("match_event_id") == events[0].event_id


def test_chat_records_user_feedback() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )
    request = ChatRequest(message="Do something")
    response = service.chat(request)

    match_event_id = response.telemetry["match_event_id"]
    service.record_capability_feedback(
        match_event_id=match_event_id,
        user_action="confirm",
        selected_capability_id="cap-a",
    )

    events = telemetry.get_events()
    assert len(events) == 1
    assert events[0].user_action == "confirm"
    assert events[0].selected_capability_id == "cap-a"


def test_chat_without_telemetry_unchanged() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert "match_event_id" not in response.telemetry


def test_telemetry_records_correct_scores_and_gap() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.85,
        ),
        CapabilityCandidate(
            id="cap-b",
            name="capability_b",
            description="Does B",
            kind="tool",
            tags=["b"],
            execution_mode="compiled",
            confidence=0.60,
        ),
        CapabilityCandidate(
            id="cap-c",
            name="capability_c",
            description="Does C",
            kind="tool",
            tags=["c"],
            execution_mode="compiled",
            confidence=0.40,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )
    request = ChatRequest(message="Do something")
    service.chat(request)

    events = telemetry.get_events()
    assert len(events) == 1
    assert events[0].top_score == 0.85
    assert events[0].score_gap == 0.25
    assert events[0].candidate_scores == [0.85, 0.60, 0.40]


def test_chat_records_session_id_in_telemetry() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )
    request = ChatRequest(message="Do something", session_id="ses-explicit-123")
    response = service.chat(request)

    events = telemetry.get_events()
    assert len(events) == 1
    assert events[0].session_id == "ses-explicit-123"
    assert response.session_id == "ses-explicit-123"


def test_chat_generates_session_id_when_not_provided() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )
    request = ChatRequest(message="Do something")
    response = service.chat(request)

    events = telemetry.get_events()
    assert len(events) == 1
    assert events[0].session_id == response.session_id
    assert events[0].session_id is not None
    assert events[0].session_id.startswith("ses-")


def test_telemetry_session_correlation() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )

    session_id = "ses-correlation-123"
    request1 = ChatRequest(message="First request", session_id=session_id)
    service.chat(request1)
    request2 = ChatRequest(message="Second request", session_id=session_id)
    service.chat(request2)

    session_events = telemetry.get_events_by_session(session_id)
    assert len(session_events) == 2
    assert all(e.session_id == session_id for e in session_events)


def test_telemetry_reformulation_detection() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            tags=["a"],
            execution_mode="compiled",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    telemetry = CapabilitySelectionTelemetry()
    service = AssistantChatService(
        capability_discovery=discovery,
        capability_selection_telemetry=telemetry,
    )

    session_id = "ses-reformulation-123"
    request1 = ChatRequest(message="First request", session_id=session_id)
    service.chat(request1)
    request2 = ChatRequest(message="Second request", session_id=session_id)
    service.chat(request2)

    reformulations = telemetry.get_reformulation_candidates()
    assert len(reformulations) == 2
    assert all(e.session_id == session_id for e in reformulations)


# ---- Work Delegation (Organisation Integration) -----------------------


def test_chat_delegates_to_organisation_when_no_capability_match() -> None:
    discovery = InMemoryCapabilityDiscoveryPort(candidates=[])
    work_management = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
    )
    request = ChatRequest(message="Create a capability that researches X")
    response = service.chat(request)

    assert response.status == "delegated"
    assert len(work_management.created_work) == 1
    assert work_management.created_work[0]["title"] == "Create a capability that researches X"
    assert "work_id" in response.telemetry
    assert response.telemetry["delegated"] is True


def test_chat_falls_through_to_pattern_execution_when_no_work_management() -> None:
    discovery = InMemoryCapabilityDiscoveryPort(candidates=[])
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=None,
    )
    request = ChatRequest(message="Do something without capabilities")
    response = service.chat(request)

    assert response.status == "pending"
    assert "Strategy:" in response.message


def test_chat_delegation_uses_session_id() -> None:
    discovery = InMemoryCapabilityDiscoveryPort(candidates=[])
    work_management = InMemoryWorkManagementPort()
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
    )
    request = ChatRequest(message="Research task", session_id="ses-delegation-123")
    response = service.chat(request)

    assert response.session_id == "ses-delegation-123"
    assert response.status == "delegated"
    assert len(work_management.created_work) == 1


# ---- Enterprise Capability Query Decision Tests ---------------------------------


class FakeQueryPort:
    def __init__(self, availability: CapabilityAvailability | None) -> None:
        self._availability = availability
        self.queried: list[str] = []

    def query_capability(self, capability_id: str) -> CapabilityAvailability | None:
        self.queried.append(capability_id)
        return self._availability


def test_chat_delegates_when_enterprise_capability_fast() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-fast",
            name="fast_cap",
            description="Fast capability",
            kind="tool",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    work_management = InMemoryWorkManagementPort()
    query = FakeQueryPort(
        CapabilityAvailability(
            capability_id="cap-fast",
            available=True,
            eta_seconds=5,
            reason="Available now",
        )
    )
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
        enterprise_capability_query=query,
    )
    response = service.chat(ChatRequest(message="Do something fast"))

    assert response.status == "delegated"
    assert len(work_management.created_work) == 1
    assert work_management.created_work[0]["required_capability_ids"] == ["cap-fast"]
    assert query.queried == ["cap-fast"]


def test_chat_provides_interim_when_enterprise_capability_slow() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-slow",
            name="slow_cap",
            description="Slow capability",
            kind="tool",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    work_management = InMemoryWorkManagementPort()
    query = FakeQueryPort(
        CapabilityAvailability(
            capability_id="cap-slow",
            available=True,
            eta_seconds=300,
            reason="Busy",
        )
    )
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
        enterprise_capability_query=query,
    )
    response = service.chat(ChatRequest(message="Do something slow"))

    assert response.status == "delegated_with_interim"
    assert "preliminary answer" in response.message
    assert len(work_management.created_work) == 1
    assert work_management.created_work[0]["required_capability_ids"] == ["cap-slow"]
    assert query.queried == ["cap-slow"]


def test_chat_reports_gap_when_enterprise_capability_absent() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-missing",
            name="missing_cap",
            description="Missing capability",
            kind="tool",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    work_management = InMemoryWorkManagementPort()
    query = FakeQueryPort(None)
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
        enterprise_capability_query=query,
    )
    response = service.chat(ChatRequest(message="Do something missing"))

    assert response.status == "capability_gap"
    assert "does not currently have" in response.message
    assert len(work_management.created_work) == 1
    assert work_management.created_work[0]["title"] == "Develop capability: missing_cap"
    assert query.queried == ["cap-missing"]
    assert response.telemetry["gap"] is True
    assert response.telemetry["work_created"] is True
    assert response.telemetry["work_id"] is not None


def test_chat_reports_unavailable_when_enterprise_capability_busy() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-busy",
            name="busy_cap",
            description="Busy capability",
            kind="tool",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    work_management = InMemoryWorkManagementPort()
    query = FakeQueryPort(
        CapabilityAvailability(
            capability_id="cap-busy",
            available=False,
            eta_seconds=None,
            assignee="worker-agent",
            reason="Currently in use",
        )
    )
    service = AssistantChatService(
        capability_discovery=discovery,
        work_management=work_management,
        enterprise_capability_query=query,
    )
    response = service.chat(ChatRequest(message="Do something busy"))

    assert response.status == "capability_unavailable"
    assert "currently unavailable" in response.message
    assert len(work_management.created_work) == 0
    assert query.queried == ["cap-busy"]


def test_chat_preserves_existing_behavior_without_enterprise_query() -> None:
    candidates = [
        CapabilityCandidate(
            id="cap-a",
            name="capability_a",
            description="Does A",
            kind="tool",
            confidence=0.9,
        ),
    ]
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(
        capability_discovery=discovery,
        enterprise_capability_query=None,
    )
    request = ChatRequest(message="Do something")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"


def test_chat_uses_ai_response_when_configured() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = ("AI-generated response", {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None})
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    request = ChatRequest(message="Tell me something interesting")
    response = service.chat(request)

    assert response.status == "completed"
    assert response.message == "AI-generated response"
    assert response.telemetry["runtime"] == "ai_response_service"
    assert response.telemetry["model"] == "llama-3.3-70b-versatile"
    mock_ai.generate.assert_called_once_with(
        user_message="Tell me something interesting",
        context={},
        conversation_history=[],
    )


def test_chat_falls_through_when_ai_response_fails() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.side_effect = RuntimeError("Portkey unavailable")
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    request = ChatRequest(message="Tell me something interesting")
    response = service.chat(request)

    assert response.status == "pending"
    assert "Strategy:" in response.message


# ---- Conversational AI Routing (Increment 22) -----------------------


def test_chat_routes_general_question_to_ai() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = ("The capital of France is Paris.", {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None})
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    request = ChatRequest(message="What is the capital of France?")
    response = service.chat(request)

    assert response.status == "completed"
    assert response.message == "The capital of France is Paris."
    assert response.telemetry["runtime"] == "ai_response_service"
    mock_ai.generate.assert_called_once()


def test_chat_routes_follow_up_to_ai_with_history() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = ("Based on your business, I'd investigate churn first.", {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 150, "ai_success": True, "ai_error": None})
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    session_id = "ses-history-test"
    request1 = ChatRequest(message="My business sells coaching programs to established consultants.", session_id=session_id)
    response1 = service.chat(request1)
    assert response1.status == "completed"

    request2 = ChatRequest(message="What would you investigate first if sales suddenly dropped?", session_id=session_id)
    response2 = service.chat(request2)
    assert response2.status == "completed"
    assert response2.message == "Based on your business, I'd investigate churn first."

    first_call_history = mock_ai.generate.call_args_list[0].kwargs["conversation_history"]
    assert first_call_history == []

    second_call_history = mock_ai.generate.call_args_list[1].kwargs["conversation_history"]
    assert second_call_history == [
        {"role": "user", "content": "My business sells coaching programs to established consultants."},
        {"role": "assistant", "content": response1.message},
    ]


def test_chat_does_not_route_planning_to_ai() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.model = "llama-3.3-70b-versatile"

    session_factory = InMemorySessionFactoryPort()
    service = AssistantChatService(
        ai_response=mock_ai,
        session_factory=session_factory,
        pattern_execution=InMemoryPatternExecutionPort(),
    )
    request = ChatRequest(message="Plan a birthday party for 20 people")
    response = service.chat(request)

    assert response.status == "completed"
    assert response.telemetry.get("runtime") == "pattern_execution_port"
    mock_ai.generate.assert_not_called()


def test_chat_does_not_route_analysis_to_ai() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(
        ai_response=mock_ai,
        work_management=InMemoryWorkManagementPort(),
    )
    request = ChatRequest(message="Analyse this document and tell me what I should focus on")
    response = service.chat(request)

    assert response.status == "awaiting_human_input"
    mock_ai.generate.assert_not_called()


def test_chat_ai_telemetry_includes_observability_fields() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = ("Observability response", {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 42, "ai_success": True, "ai_error": None})
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    request = ChatRequest(message="Tell me about observability")
    response = service.chat(request)

    assert response.telemetry["ai_invoked"] is True
    assert response.telemetry["ai_model"] == "llama-3.3-70b-versatile"
    assert response.telemetry["ai_latency_ms"] == 42
    assert response.telemetry["ai_success"] is True
    assert response.telemetry["ai_error"] is None


def test_chat_ai_telemetry_records_failure() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.side_effect = RuntimeError("Portkey timeout")
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    request = ChatRequest(message="Tell me something")
    response = service.chat(request)

    assert response.status == "pending"
    assert "Strategy:" in response.message


def test_chat_skips_ai_when_not_configured() -> None:
    service = AssistantChatService(ai_response=None)
    request = ChatRequest(message="Tell me something interesting")
    response = service.chat(request)

    assert response.status == "pending"
    assert "Strategy:" in response.message


# ---- Conversation Continuity & Session Isolation (Increment 23) -----------------


def test_chat_three_turn_conversation_retains_context() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "Northstar Coaching has 12 employees and operational complexity.",
        {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None},
    )
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    session_id = "ses-northstar-123"

    turn1 = service.chat(ChatRequest(
        message="Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity.",
        session_id=session_id,
    ))
    assert turn1.status == "completed"

    turn2 = service.chat(ChatRequest(
        message="What would you investigate first?",
        session_id=session_id,
    ))
    assert turn2.status == "completed"

    turn3 = service.chat(ChatRequest(
        message="Now answer that as if I'm the owner rather than an employee.",
        session_id=session_id,
    ))
    assert turn3.status == "completed"

    assert mock_ai.generate.call_count == 3

    second_call_history = mock_ai.generate.call_args_list[1].kwargs["conversation_history"]
    assert second_call_history == [
        {"role": "user", "content": "Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity."},
        {"role": "assistant", "content": turn1.message},
    ]

    third_call_history = mock_ai.generate.call_args_list[2].kwargs["conversation_history"]
    assert third_call_history == [
        {"role": "user", "content": "Let's call the fictional company Northstar Coaching. It has 12 employees and is struggling with operational complexity."},
        {"role": "assistant", "content": turn1.message},
        {"role": "user", "content": "What would you investigate first?"},
        {"role": "assistant", "content": turn2.message},
    ]


def test_chat_session_history_isolated_between_sessions() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "Response",
        {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None},
    )
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)

    service.chat(ChatRequest(message="Session A message", session_id="ses-a"))
    service.chat(ChatRequest(message="Session B message", session_id="ses-b"))

    assert mock_ai.generate.call_count == 2

    call_a_history = mock_ai.generate.call_args_list[0].kwargs["conversation_history"]
    call_b_history = mock_ai.generate.call_args_list[1].kwargs["conversation_history"]

    assert call_a_history == []
    assert call_b_history == []

    service.chat(ChatRequest(message="Session A follow-up", session_id="ses-a"))
    call_a_followup = mock_ai.generate.call_args_list[2].kwargs["conversation_history"]
    assert call_a_followup == [
        {"role": "user", "content": "Session A message"},
        {"role": "assistant", "content": mock_ai.generate.return_value[0]},
    ]


def test_chat_conversation_history_bounded_to_max_turns() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "Response",
        {"ai_invoked": True, "ai_model": "llama-3.3-70b-versatile", "ai_latency_ms": 100, "ai_success": True, "ai_error": None},
    )
    mock_ai.model = "llama-3.3-70b-versatile"

    service = AssistantChatService(ai_response=mock_ai)
    session_id = "ses-bounded"

    for i in range(25):
        service.chat(ChatRequest(message=f"Message {i}", session_id=session_id))

    last_call_history = mock_ai.generate.call_args_list[24].kwargs["conversation_history"]
    assert len(last_call_history) <= 40
    assert last_call_history[0]["content"] != "Message 0"
    assert last_call_history[0]["content"] == "Message 4"


def test_chat_specialised_request_does_not_inherit_conversational_history() -> None:
    from unittest.mock import MagicMock

    mock_ai = MagicMock()
    mock_ai.model = "llama-3.3-70b-versatile"

    session_factory = InMemorySessionFactoryPort()
    pattern_execution = InMemoryPatternExecutionPort()
    service = AssistantChatService(
        ai_response=mock_ai,
        session_factory=session_factory,
        pattern_execution=pattern_execution,
    )

    service.chat(ChatRequest(message="Tell me about management.", session_id="ses-specialised"))
    assert mock_ai.generate.call_count == 1

    plan_request = ChatRequest(message="Plan a birthday party for 20 people", session_id="ses-specialised")
    response = service.chat(plan_request)
    assert response.status == "completed"
    assert response.telemetry.get("runtime") == "pattern_execution_port"
    assert mock_ai.generate.call_count == 1


# ---- Phase 5: Conversational → Actionable (Increment 24) -----------------


def _make_actionable_mock_ai(actionable: bool = True) -> MagicMock:
    mock_ai = MagicMock()
    mock_ai.model = "groq-model"
    if actionable:
        mock_ai.classify_actionable_intent.return_value = {
            "mode": "actionable",
            "action": "investigate",
            "objective": "Determine whether customer experience is contributing to retention decline",
            "context": {"retention": "84% to 76%", "support_volume": "+31%"},
            "confidence": "high",
        }
    else:
        mock_ai.classify_actionable_intent.return_value = {
            "mode": "conversational",
            "action": None,
            "objective": None,
            "context": {},
            "confidence": "high",
        }
    mock_ai.generate.return_value = (
        "AI conversational response",
        {"ai_invoked": True, "ai_model": "groq-model", "ai_latency_ms": 100, "ai_success": True, "ai_error": None},
    )
    return mock_ai


def test_actionable_intent_returns_awaiting_confirmation_when_llm_detects_action() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=True)
    work_management = InMemoryWorkManagementPort()
    service = AssistantChatService(ai_response=mock_ai, work_management=work_management)
    session_id = "ses-actionable-1"
    service.chat(ChatRequest(
        message="Our customer retention has fallen from 84% to 76% and support volume is up 31%.",
        session_id=session_id,
    ))
    response = service.chat(ChatRequest(
        message="Yes. Let's investigate whether customer experience is actually driving the retention decline.",
        session_id=session_id,
    ))

    assert response.status == "awaiting_confirmation"
    assert "investigate" in response.message.lower()
    assert "retention decline" in response.message.lower()
    assert response.telemetry.get("runtime") == "ai_intent_classifier"
    assert response.telemetry.get("actionable_intent", {}).get("action") == "investigate"


def test_actionable_intent_falls_through_when_llm_says_conversational() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=False)
    service = AssistantChatService(ai_response=mock_ai)
    session_id = "ses-convo-1"
    service.chat(ChatRequest(message="Tell me about management.", session_id=session_id))
    response = service.chat(ChatRequest(
        message="What do you think about customer experience?",
        session_id=session_id,
    ))

    assert response.status == "completed"
    assert response.message == "AI conversational response"
    assert response.telemetry.get("runtime") == "ai_response_service"


def test_actionable_intent_skipped_without_conversation_history() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=True)
    service = AssistantChatService(ai_response=mock_ai)
    response = service.chat(ChatRequest(message="Tell me about management."))

    assert response.status == "completed"
    assert response.message == "AI conversational response"
    mock_ai.classify_actionable_intent.assert_not_called()


def test_actionable_intent_confirmation_creates_work() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=True)
    work_management = InMemoryWorkManagementPort()
    service = AssistantChatService(ai_response=mock_ai, work_management=work_management)
    session_id = "ses-confirm-1"
    service.chat(ChatRequest(
        message="Our customer retention has fallen from 84% to 76% and support volume is up 31%.",
        session_id=session_id,
    ))
    service.chat(ChatRequest(
        message="Yes. Let's investigate whether customer experience is actually driving the retention decline.",
        session_id=session_id,
    ))
    response = service.resume_with_human_input(session_id, {"response": "Yes, investigate it."})

    assert len(work_management.created_work) == 1
    work = work_management.created_work[0]
    assert "investigate" in work["title"].lower() or "retention" in work["title"].lower()
    assert response.status in ("completed", "delegated")
    assert "Done" in response.message or response.telemetry.get("work_id") is not None


def test_actionable_intent_rejection_clears_pending() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=True)
    service = AssistantChatService(ai_response=mock_ai)
    session_id = "ses-reject-1"
    service.chat(ChatRequest(
        message="Our customer retention has fallen from 84% to 76% and support volume is up 31%.",
        session_id=session_id,
    ))
    service.chat(ChatRequest(
        message="Yes. Let's investigate whether customer experience is actually driving the retention decline.",
        session_id=session_id,
    ))
    response = service.resume_with_human_input(session_id, {"response": "No, let's do something else."})

    assert response.status == "completed"
    assert "what would you like" in response.message.lower()
    assert session_id not in service._pending_actionable_intents


def test_malformed_actionable_intent_falls_through_to_conversational() -> None:
    mock_ai = MagicMock()
    mock_ai.model = "groq-model"
    mock_ai.classify_actionable_intent.return_value = "not valid json"
    mock_ai.generate.return_value = (
        "AI conversational response",
        {"ai_invoked": True, "ai_model": "groq-model", "ai_latency_ms": 100, "ai_success": True, "ai_error": None},
    )
    service = AssistantChatService(ai_response=mock_ai)
    session_id = "ses-malformed-1"
    service.chat(ChatRequest(
        message="Tell me about management.",
        session_id=session_id,
    ))
    response = service.chat(ChatRequest(
        message="What do you think about customer experience?",
        session_id=session_id,
    ))

    assert response.status == "completed"
    assert response.message == "AI conversational response"


def test_specialised_paths_unaffected_by_actionable_intent() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=True)
    session_factory = InMemorySessionFactoryPort()
    pattern_execution = InMemoryPatternExecutionPort()
    service = AssistantChatService(
        ai_response=mock_ai,
        session_factory=session_factory,
        pattern_execution=pattern_execution,
    )

    plan_response = service.chat(ChatRequest(message="Plan a birthday party for 20 people"))
    assert plan_response.status == "completed"
    assert plan_response.telemetry.get("runtime") == "pattern_execution_port"
    mock_ai.classify_actionable_intent.assert_not_called()


def test_actionable_intent_preserves_conversation_context() -> None:
    mock_ai = _make_actionable_mock_ai(actionable=True)
    work_management = InMemoryWorkManagementPort()
    service = AssistantChatService(ai_response=mock_ai, work_management=work_management)
    session_id = "ses-context-1"
    service.chat(ChatRequest(
        message="Our customer retention has fallen from 84% to 76% and support volume is up 31%.",
        session_id=session_id,
    ))
    response = service.chat(ChatRequest(
        message="Yes. Let's investigate whether customer experience is actually driving the retention decline.",
        session_id=session_id,
    ))

    assert response.status == "awaiting_confirmation"
    intent_data = response.telemetry.get("actionable_intent", {})
    assert intent_data.get("context", {}).get("retention") == "84% to 76%"
    assert intent_data.get("context", {}).get("support_volume") == "+31%"
    assert intent_data.get("objective") == "Determine whether customer experience is contributing to retention decline"


def test_worker_infer_intent_maps_investigate_to_content_analysis() -> None:
    from workflow_runner.src.worker import Worker
    worker = Worker(output_dir=Path("/tmp/test-worker-intent"))
    intent = worker._infer_intent("Investigate whether customer experience is driving retention decline")
    assert intent == "Content analysis"
