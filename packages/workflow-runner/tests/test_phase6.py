"""
TDD tests for Phase 6 — LangGraph runtime, Assistant chat, Human-in-the-loop.

Contracts: RUNTIME-MAPPING.md; REASONING-PATTERN-CATALOGUE.md §12.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chat import AssistantChatService, ChatRequest, ChatResponse
from pathway_runtime import (
    PathwayCallRequest,
    PathwayResponse,
    PathwayRuntime,
    PathwayStatus,
    RuntimeCapability,
)
from capabilities import Capability, CapabilityKind, CapabilityRegistry, ExecutionMode
from concepts import ConceptStore, ConceptKind, EnterpriseConcept
from langgraph_runtime import LangGraphRuntime
from session import Session, SessionStatus, create_session_from_decision
from strategy import ReasoningStrategy
from human_loop import HumanInTheLoopMixin, HumanInputRequest, HumanInputStatus


# ---- LangGraph runtime (RUNTIME-MAPPING.md) ---------------------------------

def test_langgraph_runtime_implements_interface() -> None:
    runtime = LangGraphRuntime()
    assert isinstance(runtime, PathwayRuntime)
    assert runtime.id == "langgraph"


def test_langgraph_runtime_capabilities() -> None:
    runtime = LangGraphRuntime()
    assert runtime.supports(RuntimeCapability.STATEFUL)
    assert runtime.supports(RuntimeCapability.INTERRUPTION)
    assert runtime.supports(RuntimeCapability.STREAMING)
    assert runtime.supports(RuntimeCapability.CONCURRENT_PARTICIPANTS)


def test_langgraph_runtime_invoke_completes(tmp_path: Path) -> None:
    runtime = LangGraphRuntime()
    request = PathwayCallRequest(
        session_id="ses-langgraph-1",
        pattern_step={
            "pattern_id": "debate@1.0.0",
            "ordered_steps": [
                {"step_id": "s1", "role": "proposer", "tools": [], "gate_condition": None},
                {"step_id": "s2", "role": "critic", "tools": [], "gate_condition": None},
            ],
        },
        context={"topic": "test"},
        participants=[{"role": "proposer"}, {"role": "critic"}],
        prompt="Test prompt",
    )
    response = runtime.invoke(request)
    assert isinstance(response, PathwayResponse)
    assert response.status == PathwayStatus.COMPLETED
    assert "s1" in response.outputs
    assert "s2" in response.outputs
    assert response.telemetry.get("runtime") == "langgraph"


def test_langgraph_runtime_invoke_human_approval_gate(tmp_path: Path) -> None:
    runtime = LangGraphRuntime()
    request = PathwayCallRequest(
        session_id="ses-langgraph-human",
        pattern_step={
            "pattern_id": "approval@1.0.0",
            "ordered_steps": [
                {"step_id": "s1", "role": "worker", "tools": [], "gate_condition": "human_approval"},
            ],
        },
        context={"topic": "test"},
        participants=[{"role": "worker"}],
        prompt="Test prompt",
    )
    response = runtime.invoke(request)
    assert response.status == PathwayStatus.WAITING
    assert response.human_input_request is not None
    assert "question" in response.human_input_request


def test_langgraph_runtime_resume(tmp_path: Path) -> None:
    runtime = LangGraphRuntime()
    request = PathwayCallRequest(
        session_id="ses-langgraph-resume",
        pattern_step={
            "pattern_id": "approval@1.0.0",
            "ordered_steps": [
                {"step_id": "s1", "role": "worker", "tools": [], "gate_condition": "human_approval"},
            ],
        },
        context={"topic": "test"},
        participants=[{"role": "worker"}],
        prompt="Test prompt",
    )
    response = runtime.invoke(request)
    assert response.status == PathwayStatus.WAITING

    resume_response = runtime.resume(
        session_id="ses-langgraph-resume",
        human_response={"response": "yes, proceed", "context": {}},
    )
    assert isinstance(resume_response, PathwayResponse)


# ---- Human-in-the-loop (Phase 6) -------------------------------------------

class _TestSession(HumanInTheLoopMixin):
    def __init__(self) -> None:
        self.id = "ses-htl-1"
        self.status = SessionStatus.RUNNING
        self.context: Dict[str, Any] = {}
        super().__init__()


def test_human_input_request_pauses_session() -> None:
    session = _TestSession()
    request = session.request_human_input("Do you approve this action?", context={"action": "deploy"})
    assert session.has_pending_human_input()
    assert request.status == HumanInputStatus.REQUESTED
    assert request.question == "Do you approve this action?"


def test_human_input_response_resumes_session() -> None:
    session = _TestSession()
    request = session.request_human_input("Approve?", context={"action": "deploy"})
    completed = session.provide_human_input(request.request_id, "yes")
    assert completed.status == HumanInputStatus.RECEIVED
    assert completed.response == "yes"
    assert not session.has_pending_human_input()


def test_human_response_applied_to_context() -> None:
    session = _TestSession()
    request = session.request_human_input("Approve?", context={"action": "deploy"})
    session.provide_human_input(request.request_id, "yes")
    updated = session.apply_human_response_to_context({"original": "data"})
    assert updated["human_response"] == "yes"
    assert "human_response_at" in updated


def test_human_input_history_tracked() -> None:
    session = _TestSession()
    session.request_human_input("Q1?")
    session.request_human_input("Q2?")
    assert len(session._human_input_history) == 2


# ---- Assistant chat service (Phase 6) ---------------------------------------

def test_chat_service_returns_previous_solution(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)

    concept = EnterpriseConcept(
        id="sol-previous",
        kind=ConceptKind.CAPABILITY,
        name="previous-solution",
        description="A previous solution",
        tags=["solution", "strategy:deliberate_to_consensus"],
        payload={
            "summary": "Designed a task tracker with 3 interfaces",
            "strategy": "deliberate_to_consensus",
            "pattern_pipeline": ["debate@1.0.0", "consensus@1.0.0"],
            "maturation_history": {"invocation_count": 2, "correction_count": 0},
        },
    )
    store.upsert(concept)

    service = AssistantChatService(concept_store=store, capability_registry=reg)
    request = ChatRequest(message="Design a new task tracking service")
    response = service.chat(request)

    assert response.status == "awaiting_confirmation"
    assert response.previous_solution is not None
    assert response.previous_solution["invocation_count"] == 2


def test_chat_service_creates_new_session_when_no_match(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    service = AssistantChatService(concept_store=store, capability_registry=reg)

    request = ChatRequest(message="Do something completely novel")
    response = service.chat(request)

    assert response.session_id.startswith("ses-")
    assert response.status == "pending"


def test_chat_service_resumes_with_human_input(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)
    runtime = MagicMock(spec=PathwayRuntime)
    runtime.invoke.return_value = PathwayResponse(
        status=PathwayStatus.WAITING,
        human_input_request={"question": "Approve?", "session_id": "ses-htl-1"},
    )
    runtime.resume.return_value = PathwayResponse(
        status=PathwayStatus.COMPLETED,
        outputs={"summary": "Completed after approval"},
    )

    service = AssistantChatService(concept_store=store, capability_registry=reg, runtime=runtime)
    request = ChatRequest(message="Deploy service", session_id="ses-htl-1")
    response = service.chat(request)
    assert response.status == "awaiting_human_input"

    resume_response = service.resume_with_human_input("ses-htl-1", {"response": "yes"})
    assert resume_response.status == "completed"
