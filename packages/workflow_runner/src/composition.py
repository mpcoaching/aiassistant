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
    capability_selection_telemetry: Any | None = None,
    enterprise_capability_query: Any | None = None,
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
        capability_selection_telemetry=capability_selection_telemetry,
        enterprise_capability_query=enterprise_capability_query,
    )


def create_application(capability_selection_telemetry: Any | None = None) -> dict[str, Any]:
    from adapters.capability_discovery_adapter import CapabilityDiscoveryAdapter
    from adapters.enterprise_capability_query_adapter import EnterpriseCapabilityQueryAdapter
    from adapters.organisational_context_adapter import OrganisationalContextAdapter
    from adapters.work_management_adapter import WorkManagementAdapter
    from capability_registry.src.adapters.execution_authorisation_adapter import InMemoryExecutionAuthorisationPort
    from capability_registry.src.capabilities import ConceptKind
    from capability_registry.src.concept_store_adapter import ConceptStoreCapabilityRepository
    from capabilities import CapabilityRegistry
    from capability import Capability
    from capability_matcher import RelevanceMatcher
    from concepts import ConceptStore
    from contracts.capability_outcome_assessor import CapabilityOutcomeAssessor
    from contracts.enterprise_capability_query import EnterpriseCapabilityQueryPort
    from contracts.organisational_context import OrganisationalContextPort
    from contracts.work_management import WorkManagementPort
    from execution_authorisation import ExecutionAuthorisationPort
    from invocation_recorder import InvocationRecorder
    from langgraph_runtime import LangGraphRuntime
    from organisation_control_plane import InMemoryOrganisationControlPlane
    from organisation.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from runtime import PatternRuntime
    from workflow_runner.src.adapters.capability_execution_adapter import (
        CapabilityExecutionAdapter,
    )
    from workflow_runner.src.adapters.capability_outcome_assessor_adapter import (
        CapabilityOutcomeAssessorAdapter,
    )
    from workflow_runner.src.adapters.invocation_recorder_adapter import (
        InvocationRecorderAdapter,
    )
    from workflow_runner.src.adapters.pattern_execution_adapter import (
        PatternExecutionAdapter,
    )
    from workflow_runner.src.adapters.session_factory_adapter import (
        SessionFactoryAdapter,
    )
    from capability_deployment import CapabilityDeployment
    from deployment_resolver import DeploymentNotFoundError, DeploymentResolver

    store = ConceptStore()
    repository = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repository)

    matcher = RelevanceMatcher()
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

    org_plane = InMemoryOrganisationControlPlane()
    org_plane.register_role(Role(id="researcher", name="Researcher", authority_ids=[]))
    org_context_port: OrganisationalContextPort = OrganisationalContextAdapter(org_plane)
    work_management_port: WorkManagementPort = WorkManagementAdapter(org_plane)
    enterprise_capability_query_port: EnterpriseCapabilityQueryPort = EnterpriseCapabilityQueryAdapter(org_plane)

    assistant = create_assistant(
        capability_discovery=discovery,
        capability_execution=execution_adapter,
        session_factory=session_factory,
        pattern_execution=pattern_execution,
        organisational_context=org_context_port,
        work_management=work_management_port,
        enterprise_capability_query=enterprise_capability_query_port,
        capability_selection_telemetry=capability_selection_telemetry,
    )

    return {
        "assistant": assistant,
        "org_plane": org_plane,
        "work_management": work_management_port,
    }
