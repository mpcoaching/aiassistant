"""
Architectural boundary tests for the AI plane.

Verifies that the AI package does not cross plane boundaries via
direct imports from domain-plane implementations.
"""

from __future__ import annotations

import ast
import os


from chat import AssistantChatService
from contracts import (
    CapabilityCandidate,
    CapabilityDiscoveryPort,
    CapabilityExecutionPort,
    EnterpriseInformationPort,
    ExecutionResult,
    OrganisationalContextPort,
    PatternExecutionPort,
    PreviousSolution,
    SessionFactoryPort,
    WorkManagementPort,
)

from ai.tests.fixtures.in_memory_ports import (
    InMemoryCapabilityDiscoveryPort,
    InMemoryCapabilityExecutionPort,
    InMemoryEnterpriseInformationPort,
)


def _source_path(*parts: str) -> str:
    return os.path.join(os.path.dirname(__file__), "..", "src", *parts)


def _read_source(*parts: str) -> str:
    path = os.path.normpath(_source_path(*parts))
    with open(path) as f:
        return f.read()


def _forbidden_imports(*parts: str) -> set[str]:
    source = _read_source(*parts)
    tree = ast.parse(source)
    forbidden = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for forbidden_mod in _FORBIDDEN_MODULES:
                if forbidden_mod in node.module:
                    forbidden.add(node.module)
    return forbidden


_FORBIDDEN_MODULES = {
    "capability_registry",
    "capability_matcher",
    "concepts",
    "workflow_runner.src.executor",
    "workflow_runner.src.runtime",
    "workflow_runner.src.session",
    "bus",
    "pathway_runtime",
    "langgraph_runtime",
}


def test_chat_service_has_no_forbidden_imports() -> None:
    forbidden = _forbidden_imports("chat.py")
    assert not forbidden, f"chat.py contains forbidden imports: {forbidden}"


def test_ai_src_has_no_cross_plane_imports() -> None:
    src_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
    forbidden_files = {}
    for filename in os.listdir(src_dir):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(src_dir, filename)
        with open(path) as f:
            source = f.read()
        tree = ast.parse(source)
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for forbidden_mod in _FORBIDDEN_MODULES:
                    if forbidden_mod in node.module:
                        found.add(node.module)
        if found:
            forbidden_files[filename] = found
    assert not forbidden_files, f"AI src contains forbidden imports: {forbidden_files}"


def test_assistant_chat_service_depends_on_ports() -> None:
    sig = AssistantChatService.__init__.__code__
    param_names = set(sig.co_varnames[:sig.co_argcount])
    expected = {
        "self",
        "reasoning_service",
        "capability_discovery",
        "capability_execution",
        "enterprise_information",
        "organisational_context",
        "work_management",
        "session_factory",
        "pattern_execution",
    }
    assert param_names == expected, f"Unexpected constructor parameters: {param_names}"


def test_assistant_chat_service_does_not_instantiate_domain_services() -> None:
    import inspect

    source = inspect.getsource(AssistantChatService.__init__)
    forbidden = ["CapabilityRegistry(", "CapabilityMatcher(", "ConceptStore(", "PathwayRuntime("]
    for phrase in forbidden:
        assert phrase not in source, f"AssistantChatService instantiates {phrase}"


def test_assistant_chat_service_does_not_instantiate_session() -> None:
    import inspect

    source = inspect.getsource(AssistantChatService)
    assert "create_session_from_decision" not in source
    assert "Session(" not in source


def test_assistant_does_not_call_execute_capability() -> None:
    import inspect

    source = inspect.getsource(AssistantChatService)
    assert "execute_capability" not in source


def test_assistant_does_not_call_pattern_runtime_invoke() -> None:
    import inspect

    source = inspect.getsource(AssistantChatService)
    assert "invoke_step" not in source
    assert "PatternRuntime" not in source


def test_assistant_does_not_directly_access_concept_store() -> None:
    import inspect

    source = inspect.getsource(AssistantChatService)
    assert "ConceptStore" not in source
    assert "EnterpriseConcept" not in source
    assert "ConceptKind" not in source


def test_previous_solution_lookup_through_port() -> None:
    port = InMemoryEnterpriseInformationPort(
        solutions=[
            PreviousSolution(
                concept_id="sol-1",
                name="strategy:deliberate_to_consensus",
                summary="Designed a task tracker",
                invocation_count=2,
                last_invoked=None,
            )
        ]
    )
    result = port.find_previous_solutions("strategy:deliberate_to_consensus")
    assert result is not None
    assert result.summary == "Designed a task tracker"


def test_capability_discovery_through_port() -> None:
    port = InMemoryCapabilityDiscoveryPort(
        candidates=[
            CapabilityCandidate(
                id="cap-1",
                name="test-cap",
                description="test",
                kind="tool",
                tags=[],
                execution_mode="ai_mediated",
            )
        ]
    )
    result = port.find_capabilities("test request", {})
    assert len(result) == 1
    assert result[0].id == "cap-1"


def test_execution_through_port() -> None:
    port = InMemoryCapabilityExecutionPort(
        result=ExecutionResult(outputs={"ok": True}, artifacts=[], telemetry={})
    )
    result = port.execute("cap-1", {"x": 1}, {"actor_id": "a1"})
    assert result.outputs["ok"] is True
    assert len(port.executed) == 1


def test_ports_are_protocols() -> None:
    for port in [
        CapabilityDiscoveryPort,
        CapabilityExecutionPort,
        EnterpriseInformationPort,
        OrganisationalContextPort,
        PatternExecutionPort,
        SessionFactoryPort,
        WorkManagementPort,
    ]:
        assert hasattr(port, "list_capabilities") or hasattr(port, "execute") or hasattr(port, "find_previous_solutions") or hasattr(port, "get_context") or hasattr(port, "create_work") or hasattr(port, "create_session") or hasattr(port, "execute_pattern")
