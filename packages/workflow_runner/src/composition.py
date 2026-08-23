"""
Application composition root for the Assistant.

Wires concrete domain-plane implementations into the AI-plane ports
and exposes factory functions for the transport layer.

No DI framework. No service locator. Explicit constructor injection only.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("workflow_runner.composition")


def create_assistant(
    reasoning_service: Any | None = None,
    capability_discovery: Any | None = None,
    capability_execution: Any | None = None,
    enterprise_information: Any | None = None,
    organisational_context: Any | None = None,
    work_management: Any | None = None,
    session_factory: Any | None = None,
    pattern_execution: Any | None = None,
) -> Any:
    from chat import AssistantChatService

    return AssistantChatService(
        reasoning_service=reasoning_service,
        capability_discovery=capability_discovery,
        capability_execution=capability_execution,
        enterprise_information=enterprise_information,
        organisational_context=organisational_context,
        work_management=work_management,
        session_factory=session_factory,
        pattern_execution=pattern_execution,
    )


def create_ceo(
    org_context: Any,
    reasoning_service: Any | None = None,
    enterprise_information: Any | None = None,
    confidence_threshold: float = 0.5,
) -> Any:
    from ceo import CEOAgent

    return CEOAgent(
        org_context=org_context,
        reasoning_service=reasoning_service,
        enterprise_information=enterprise_information,
        confidence_threshold=confidence_threshold,
    )


def create_application() -> dict[str, Any]:
    from adapters.capability_discovery_adapter import CapabilityDiscoveryAdapter
    from capabilities import CapabilityRegistry
    from capability import Capability
    from capability_matcher import HumanSelectionMatcher
    from capability_registry.src.concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore
    from contracts.capability_outcome_assessor import CapabilityOutcomeAssessor
    from execution_authorisation import ExecutionAuthorisationPort
    from execution_authorisation_adapter import InMemoryExecutionAuthorisationPort
    from invocation_recorder import InvocationRecorder
    from langgraph_runtime import LangGraphRuntime

    from adapters.capability_execution_adapter import CapabilityExecutionAdapter
    from adapters.invocation_recorder_adapter import InvocationRecorderAdapter
    from adapters.pattern_execution_adapter import PatternExecutionAdapter
    from adapters.session_factory_adapter import SessionFactoryAdapter
    from capability_deployment import CapabilityDeployment
    from deployment_resolver import DeploymentNotFoundError, DeploymentResolver
    from runtime import PatternRuntime
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )

    store = ConceptStore()
    repository = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repository)

    matcher = HumanSelectionMatcher()
    discovery = CapabilityDiscoveryAdapter(registry=registry, matcher=matcher)

    authorisation_port: ExecutionAuthorisationPort = InMemoryExecutionAuthorisationPort()
    outcome_assessor: CapabilityOutcomeAssessor = CapabilityOutcomeAssessorAdapter()
    invocation_recorder: InvocationRecorder = InvocationRecorderAdapter(
        store=store,
        outcome_assessor=outcome_assessor,
    )
    resolver = DeploymentResolver()

    def deployment_factory(capability: Capability) -> CapabilityDeployment | None:
        try:
            return resolver.resolve(capability.id, "default")
        except (DeploymentNotFoundError, ValueError):
            return None

    execution_adapter = CapabilityExecutionAdapter(
        registry=registry,
        deployment_factory=deployment_factory,
        authorisation_port=authorisation_port,
        invocation_recorder=invocation_recorder,
    )

    PatternRuntime(
        registry=registry,
        authorisation_port=authorisation_port,
        invocation_recorder=invocation_recorder,
    )
    langgraph_runtime = LangGraphRuntime()
    pattern_execution = PatternExecutionAdapter(runtime=langgraph_runtime)
    session_factory = SessionFactoryAdapter()

    assistant = create_assistant(
        capability_discovery=discovery,
        capability_execution=execution_adapter,
        session_factory=session_factory,
        pattern_execution=pattern_execution,
    )

    return {"assistant": assistant}
