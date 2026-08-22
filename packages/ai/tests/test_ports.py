"""
Port contract tests for Assistant cross-plane interfaces.
"""

from __future__ import annotations

import inspect


from ports.capability_discovery import CapabilityCandidate, CapabilityDiscoveryPort
from ports.capability_execution import CapabilityExecutionPort, ExecutionResult
from ports.enterprise_information import EnterpriseInformationPort, PreviousSolution, SolutionRecord
from ports.organisational_context import OrganisationalContextPort
from ports.pattern_execution import PatternExecutionPort, PatternExecutionRequest, PatternExecutionResult
from ports.session_factory import SessionFactoryPort, SessionReference
from ports.work_management import WorkManagementPort, WorkReference


def test_capability_discovery_port_contract() -> None:
    methods = {"list_capabilities", "find_capabilities"}
    for method in methods:
        assert hasattr(CapabilityDiscoveryPort, method), f"CapabilityDiscoveryPort missing {method}"


def test_capability_execution_port_contract() -> None:
    methods = {"execute"}
    for method in methods:
        assert hasattr(CapabilityExecutionPort, method), f"CapabilityExecutionPort missing {method}"


def test_enterprise_information_port_contract() -> None:
    methods = {"find_previous_solutions", "record_solution"}
    for method in methods:
        assert hasattr(EnterpriseInformationPort, method), f"EnterpriseInformationPort missing {method}"


def test_organisational_context_port_contract() -> None:
    methods = {"get_context", "get_role"}
    for method in methods:
        assert hasattr(OrganisationalContextPort, method), f"OrganisationalContextPort missing {method}"


def test_work_management_port_contract() -> None:
    methods = {"create_work", "mark_ready", "get_work"}
    for method in methods:
        assert hasattr(WorkManagementPort, method), f"WorkManagementPort missing {method}"


def test_session_factory_port_contract() -> None:
    methods = {"create_session"}
    for method in methods:
        assert hasattr(SessionFactoryPort, method), f"SessionFactoryPort missing {method}"


def test_pattern_execution_port_contract() -> None:
    methods = {"execute_pattern", "resume_pattern"}
    for method in methods:
        assert hasattr(PatternExecutionPort, method), f"PatternExecutionPort missing {method}"


def test_port_dtos_are_pydantic_models() -> None:
    from pydantic import BaseModel

    for model in [
        CapabilityCandidate,
        ExecutionResult,
        PreviousSolution,
        SolutionRecord,
        SessionReference,
        PatternExecutionRequest,
        PatternExecutionResult,
        WorkReference,
    ]:
        assert issubclass(model, BaseModel), f"{model.__name__} is not a pydantic BaseModel"


def test_ports_contain_no_implementation_logic() -> None:
    for port in [
        CapabilityDiscoveryPort,
        CapabilityExecutionPort,
        EnterpriseInformationPort,
        OrganisationalContextPort,
        PatternExecutionPort,
        SessionFactoryPort,
        WorkManagementPort,
    ]:
        source = inspect.getsource(port)
        method_count = len([
            name for name, _ in inspect.getmembers(port, predicate=inspect.isfunction)
            if not name.startswith("_")
        ])
        assert source.count("...") >= method_count, (
            f"{port.__name__} contains implementation logic"
        )
