"""
TDD tests for Phase 2 — Intent intake, Strategy Selection, and decide() assembly.

Contracts: SA-CONTRACTS-PHASES-2-5.md C3, C4, C9.
"""


from assistant import AssistantReasoningService, StrategyDecision
from chat import AssistantChatService, ChatRequest
from enterprise_context import ContextRecord
from intent import Intent, IntentOrigin, ProblemFrame, recognise
from strategy import ReasoningStrategy, select_strategy

from ai.tests.fixtures.in_memory_ports import (
    InMemoryCapabilityDiscoveryPort,
    InMemoryEnterpriseInformationPort,
    InMemorySessionFactoryPort,
)
from ports.capability_discovery import CapabilityCandidate
from ports.enterprise_information import PreviousSolution

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
        )
    ]


def test_chat_exposes_capability_candidates_before_decide() -> None:
    discovery = InMemoryCapabilityDiscoveryPort(candidates=_make_capability_candidates())
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.capability_candidates[0]["name"] == "create_test_artifact"


def test_chat_create_test_artifact_in_candidates() -> None:
    discovery = InMemoryCapabilityDiscoveryPort(candidates=_make_capability_candidates())
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    candidate_names = [c["name"] for c in response.capability_candidates or []]
    assert "create_test_artifact" in candidate_names


def test_chat_capability_selection_does_not_execute() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.capability_candidates[0]["id"] == "cap-create_test_artifact"


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


def test_chat_capability_candidates_contain_metadata() -> None:
    candidates = _make_capability_candidates()
    discovery = InMemoryCapabilityDiscoveryPort(candidates=candidates)
    service = AssistantChatService(capability_discovery=discovery)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    candidate = response.capability_candidates[0]
    assert candidate["id"] == "cap-create_test_artifact"
    assert candidate["name"] == "create_test_artifact"
    assert candidate["description"] == "Creates a test artifact record"
    assert candidate["kind"] == "tool"
    assert candidate["execution_mode"] == "compiled"
    assert "tags" in candidate


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
