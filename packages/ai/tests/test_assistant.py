"""
TDD tests for Phase 2 — Intent intake, Strategy Selection, and decide() assembly.

Contracts: SA-CONTRACTS-PHASES-2-5.md C3, C4, C9.
"""


from pathlib import Path

from assistant import AssistantReasoningService, StrategyDecision
from capability_matcher import MatchResult
from capabilities import Capability, CapabilityKind, CapabilityRegistry, CompiledRef, ExecutionMode
from chat import AssistantChatService, ChatRequest
from concepts import ConceptStore
from enterprise_context import ContextRecord
from intent import Intent, IntentOrigin, ProblemFrame, recognise
from strategy import ReasoningStrategy, select_strategy

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


# ---- Capability-First Routing (Increment 4) --------------------------------

def _register_create_test_artifact(tmp_path: Path):
    """Register create_test_artifact as a compiled capability."""
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    cap = Capability(
        id="cap-create_test_artifact",
        name="create_test_artifact",
        description="Creates a test artifact record",
        owner="core",
        created_by="test",
        tags=["test", "artifact"],
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.COMPILED,
        compiled_ref=CompiledRef(
            module_path="packages.capabilities.create_test_artifact.run",
            entrypoint="run",
            tests_passed=True,
        ),
    )
    reg.register(cap)
    return reg, cap


def test_chat_exposes_capability_candidates_before_decide(tmp_path: Path) -> None:
    reg, _ = _register_create_test_artifact(tmp_path)
    service = AssistantChatService(concept_store=reg._store, capability_registry=reg)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.capability_candidates[0]["name"] == "create_test_artifact"


def test_chat_create_test_artifact_in_candidates(tmp_path: Path) -> None:
    reg, _ = _register_create_test_artifact(tmp_path)
    service = AssistantChatService(concept_store=reg._store, capability_registry=reg)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    candidate_names = [c["name"] for c in response.capability_candidates or []]
    assert "create_test_artifact" in candidate_names


def test_chat_capability_selection_does_not_execute(tmp_path: Path) -> None:
    reg, cap = _register_create_test_artifact(tmp_path)
    service = AssistantChatService(concept_store=reg._store, capability_registry=reg)
    request = ChatRequest(message="Create a test artifact")
    response = service.chat(request)

    assert response.status == "awaiting_capability_selection"
    assert response.capability_candidates is not None
    assert len(response.capability_candidates) == 1
    assert response.capability_candidates[0]["id"] == cap.id


def test_chat_falls_through_without_capabilities(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    service = AssistantChatService(concept_store=store, capability_registry=reg)
    request = ChatRequest(message="Do something completely novel")
    response = service.chat(request)

    assert response.status == "pending"


def test_chat_passes_recognised_context_to_matcher(tmp_path: Path) -> None:
    from unittest.mock import patch

    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    reg.register(Capability(
        id="cap-1",
        name="test-cap",
        description="test",
        capability_kind=CapabilityKind.TOOL,
        execution_mode=ExecutionMode.AI_MEDIATED,
    ))

    service = AssistantChatService(concept_store=store, capability_registry=reg)
    request = ChatRequest(message="Design a new task tracker")

    captured = {}
    def capture_match(**kwargs):
        captured.update(kwargs)
        return MatchResult(candidates=[], confidence=0.0, matcher_id="human_selection")

    with patch("ceo.HumanSelectionMatcher") as MockMatcher:
        MockMatcher.return_value.match.side_effect = capture_match
        service.chat(request)

    assert "context" in captured
    assert isinstance(captured["context"], ContextRecord)
    assert captured["request_text"] == "Design a new task tracker"


def test_chat_capability_candidates_contain_metadata(tmp_path: Path) -> None:
    reg, cap = _register_create_test_artifact(tmp_path)
    service = AssistantChatService(concept_store=reg._store, capability_registry=reg)
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
