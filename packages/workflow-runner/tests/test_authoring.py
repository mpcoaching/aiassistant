"""
TDD tests for Phase 4 — Service Authoring MCP tools + Validation Session flow.

Contracts: SA-CONTRACTS-PHASES-2-5.md C11; Service_Authoring.md.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_server import mcp
from session import Session, SessionStatus, create_session_from_decision
from assistant import StrategyDecision
from strategy import ReasoningStrategy
from capabilities import AiSpec, Capability, CapabilityKind, CapabilityRegistry, ExecutionMode, ConceptStore
from runtime import PatternRuntime


# ---- Service Authoring MCP tools (C11) -------------------------------------

def _text(result) -> str:
    content_blocks, _meta = result
    return content_blocks[0].text if content_blocks else ""


@pytest.mark.asyncio
async def test_design_service_returns_spec() -> None:
    text = _text(await mcp.call_tool("design_service", {"name": "test-service", "description": "A test service"}))
    spec = json.loads(text)
    assert "service_id" in spec
    assert spec["name"] == "test-service"
    assert "inputs" in spec
    assert "outputs" in spec


@pytest.mark.asyncio
async def test_design_service_includes_steps() -> None:
    text = _text(await mcp.call_tool("design_service", {"name": "invoice-svc", "description": "Invoice processing"}))
    spec = json.loads(text)
    assert "steps" in spec
    assert len(spec["steps"]) > 0


@pytest.mark.asyncio
async def test_create_service_registers_capability(tmp_path: Path) -> None:
    design = {
        "service_id": "svc-e2e-1",
        "name": "echo-svc",
        "description": "Echo service for testing",
        "inputs": [{"name": "text", "type": "string"}],
        "outputs": [{"name": "result", "type": "string"}],
        "steps": [],
    }
    text = _text(await mcp.call_tool("create_service", {"design": design}))
    result = json.loads(text)
    assert "capability_id" in result
    assert result["status"] == "created"


@pytest.mark.asyncio
async def test_compile_capability_returns_module_path(tmp_path: Path) -> None:
    design = {
        "service_id": "cap-compile-test",
        "name": "compile-test",
        "description": "Test compilation",
        "inputs": [],
        "outputs": [],
        "steps": [],
    }
    create_result = json.loads(_text(await mcp.call_tool("create_service", {"design": design})))
    assert create_result["status"] == "created"
    cap_id = create_result["capability_id"]

    text = _text(await mcp.call_tool("compile_capability", {"capability_id": cap_id, "entrypoint": "run"}))
    result = json.loads(text)
    assert "module_path" in result
    assert result["status"] == "compiled"


@pytest.mark.asyncio
async def test_list_services_returns_empty_initially() -> None:
    text = _text(await mcp.call_tool("list_services", {}))
    result = json.loads(text)
    assert isinstance(result, list)


# ---- Validation Session flow -------------------------------------------------

def test_validation_session_creation(tmp_path: Path) -> None:
    decision = StrategyDecision(
        intent_id="val-1",
        chosen_strategy=ReasoningStrategy.VERIFY_AND_ASSIMILATE,
        pattern_pipeline=["architecture_review@1.0.0", "compliance_check@1.0.0"],
    )
    session = create_session_from_decision(decision, context={"validation_target": "new-service"})
    assert session.status == SessionStatus.PENDING
    assert len(session.pipeline) == 2


def test_validation_session_invokes_architecture_review(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(store)

    cap = Capability(
        id="cap-arch-review",
        name="architecture_review",
        capability_kind=CapabilityKind.SKILL,
        execution_mode=ExecutionMode.AI_MEDIATED,
        transport="tier2_inprocess",
        ai_spec=AiSpec(purpose="review architecture", inputs=[], outputs=[]),
        interface={
            "inputs": [{"name": "design", "type": "object"}],
            "outputs": [{"name": "findings", "type": "array"}],
            "errors": [],
        },
    )
    reg.register(cap)

    runtime = PatternRuntime(registry=reg)
    reply = runtime.invoke_step(cap.id, {"design": {"name": "test"}})
    assert reply["status"] == "completed"
    assert "composed_prompt" in reply["outputs"]


def test_validation_session_status_transitions() -> None:
    decision = StrategyDecision(
        intent_id="val-2",
        chosen_strategy=ReasoningStrategy.VERIFY_AND_ASSIMILATE,
        pattern_pipeline=["compliance_check@1.0.0"],
    )
    session = create_session_from_decision(decision)
    assert session.status == SessionStatus.PENDING
