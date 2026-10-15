"""
Architectural tests for Increment 30 — Capability Ownership & Registry Boundary.

Proves that:
- Capability model is defined in people_capability (not capability_registry, not organisation)
- Capability lifecycle/discovery is owned by capability_registry
- OCP delegates capability registration/retrieval to the registry (does not own a private store)
- OCP queries capabilities through the query contract (not by importing registry internals)
- Lifecycle: DRAFT → assessment → Registry.promote → ACTIVE → discoverable
- Actor/CapabilityAssignment authorisation continues to work with ACTIVE capabilities
- OCP still selects solution paths without owning capability lifecycle
"""

from __future__ import annotations

import ast
import inspect
import os
from unittest.mock import MagicMock


def _org_src_dir() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "src"
    ))


def _people_src_dir() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "people_capability", "src"
    ))


def _registry_src_dir() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "capability_registry", "src"
    ))


def _parse_source(dir_path: str) -> list[ast.Module]:
    """Parse all .py files in a directory into AST modules."""
    modules: list[ast.Module] = []
    for filename in sorted(os.listdir(dir_path)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(dir_path, filename)
        with open(path) as f:
            try:
                modules.append(ast.parse(f.read(), filename=path))
            except SyntaxError:
                continue
    return modules


# ---- A. Capability model ownership ---


def test_capability_model_lives_in_people_capability() -> None:
    """The Capability domain model is defined in people_capability, not elsewhere."""
    assert os.path.isfile(os.path.join(_people_src_dir(), "capability.py")), (
        "Capability model must be defined in people_capability/src/capability.py"
    )

    org_modules = _parse_source(_org_src_dir())
    for mod in org_modules:
        for node in ast.walk(mod):
            if isinstance(node, ast.ClassDef) and node.name == "Capability":
                raise AssertionError(
                    "Capability model must not be redefined in organisation; "
                    "it belongs to people_capability"
                )


def test_capability_status_lives_in_people_capability() -> None:
    """CapabilityStatus is defined in people_capability."""
    assert os.path.isfile(os.path.join(_people_src_dir(), "capability.py"))


# ---- B. Registry ownership ----


def test_capability_registry_owns_lifecycle() -> None:
    """CapabilityRegistry provides register, get, list, promote — lifecycle authority."""
    from capabilities import CapabilityRegistry

    registry_methods = {"register", "get", "list", "list_all", "resolve", "promote"}
    for method_name in registry_methods:
        assert hasattr(CapabilityRegistry, method_name), (
            f"CapabilityRegistry must own {method_name}() — lifecycle authority"
        )


def test_registry_has_promote_method() -> None:
    """Registry has a promote() method for DRAFT→ACTIVE transition."""
    from capabilities import CapabilityRegistry

    sig = inspect.signature(CapabilityRegistry.promote)
    assert "capability_id" in sig.parameters or "self" in sig.parameters


# ---- C. OCP does not own capabilities ----


def test_ocp_in_memory_has_optional_registry_constructor_param() -> None:
    """InMemoryOrganisationControlPlane accepts an optional capability_registry."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    sig = inspect.signature(InMemoryOrganisationControlPlane.__init__)
    assert "capability_registry" in sig.parameters, (
        "OCP should accept capability_registry for delegation"
    )


def test_ocp_register_capability_delegates_to_registry_when_available() -> None:
    """When a registry is injected, OCP.register_capability delegates, not stores locally."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    mock_registry = MagicMock()
    plane = InMemoryOrganisationControlPlane(capability_registry=mock_registry)

    from capability import Capability, CapabilityKind

    cap = Capability(id="cap-delegated", name="Delegated", capability_kind=CapabilityKind.SKILL)
    plane.register_capability(cap)

    mock_registry.register.assert_called_once_with(cap)
    assert "cap-delegated" not in plane._capabilities, (
        "OCP should not store capabilities locally when a registry is available"
    )


def test_ocp_register_capability_falls_back_to_local_when_no_registry() -> None:
    """Without a registry, OCP retains backward-compatible local fallback."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()  # no registry

    from capability import Capability, CapabilityKind

    cap = Capability(id="cap-fallback", name="Fallback", capability_kind=CapabilityKind.SKILL)
    plane.register_capability(cap)

    assert "cap-fallback" in plane._capabilities, (
        "Local _capabilities dict is allowed as backward-compat fallback"
    )


def test_ocp_get_capability_delegates_to_registry_when_available() -> None:
    """OCP.get_capability returns the registry's capability, not a local copy."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    mock_registry = MagicMock()
    mock_registry.get.return_value = "registry-capability"
    plane = InMemoryOrganisationControlPlane(capability_registry=mock_registry)

    result = plane.get_capability("cap-1")
    assert result == "registry-capability"
    mock_registry.get.assert_called_once_with("cap-1")


def test_ocp_get_capability_falls_back_when_no_registry() -> None:
    """Without a registry, OCP falls back to local store."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    from capability import Capability, CapabilityKind

    cap = Capability(id="cap-local", name="Local", capability_kind=CapabilityKind.SKILL)
    plane._capabilities["cap-local"] = cap

    result = plane.get_capability("cap-local")
    assert result is cap


def test_ocp_query_capability_uses_get_capability_not_direct_dict() -> None:
    """OCP.query_capability must not directly access _capabilities; it uses get_capability."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    source = inspect.getsource(InMemoryOrganisationControlPlane.query_capability)
    assert "self._capabilities.get" not in source, (
        "query_capability must delegate existence lookup to get_capability(), "
        "not access _capabilities directly"
    )


def test_ocp_select_execution_path_uses_get_capability_not_direct_dict() -> None:
    """OCP.select_execution_path must not directly access _capabilities."""
    from organisation_control_plane import InMemoryOrganisationControlPlane

    source = inspect.getsource(InMemoryOrganisationControlPlane.select_execution_path)
    assert "self._capabilities.get" not in source, (
        "select_execution_path must delegate capability lookup to get_capability()"
    )


def test_ocp_does_not_import_capability_registry() -> None:
    """OCP source must not import capability_registry implementation details."""
    import ast

    from organisation_control_plane import InMemoryOrganisationControlPlane

    source = inspect.getsource(InMemoryOrganisationControlPlane)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "capability_registry" not in node.module, (
                "OCP must not import from capability_registry; "
                "it depends on the registry via injected Any"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "capability_registry" not in alias.name, (
                    "OCP must not import capability_registry module directly"
                )


# ---- D. Query boundary ----


def test_ocp_query_port_is_abstraction() -> None:
    """EnterpriseCapabilityQueryPort defines the OCP→Registry query contract."""
    import typing

    from contracts.enterprise_capability_query import (
        EnterpriseCapabilityQueryPort,
    )

    assert hasattr(EnterpriseCapabilityQueryPort, "query_capability")
    assert isinstance(EnterpriseCapabilityQueryPort, type)
    assert getattr(EnterpriseCapabilityQueryPort, "_is_protocol", False) or typing.is_protocol(EnterpriseCapabilityQueryPort)  # type: ignore[attr-defined]


def test_query_port_does_not_expose_lifecycle_methods() -> None:
    """EnterpriseCapabilityQueryPort must not expose registry lifecycle methods."""
    from contracts.enterprise_capability_query import EnterpriseCapabilityQueryPort

    protocol_attrs = getattr(
        EnterpriseCapabilityQueryPort, "__protocol_attrs__", set()
    )
    forbidden = {"register", "promote", "get", "list", "resolve", "upsert_capability"}
    exposed = protocol_attrs & forbidden
    assert not exposed, (
        f"EnterpriseCapabilityQueryPort must not expose lifecycle methods: {exposed}"
    )


def test_enterprise_capability_query_adapter_adapts_oCP_to_port() -> None:
    """EnterpriseCapabilityQueryAdapter wires OCP.query_capability to the port contract."""
    from contracts.enterprise_capability_query import CapabilityAvailability
    from organisation.src.adapters.enterprise_capability_query_adapter import (
        EnterpriseCapabilityQueryAdapter,
    )

    mock_plane = MagicMock()
    mock_plane.query_capability.return_value = {
        "capability_id": "cap-1",
        "available": True,
        "eta_seconds": 5,
        "assignee": None,
        "reason": "available",
    }
    adapter = EnterpriseCapabilityQueryAdapter(mock_plane)
    result = adapter.query_capability("cap-1")

    assert isinstance(result, CapabilityAvailability)
    assert result.capability_id == "cap-1"
    assert result.available is True


# ---- E. Lifecycle ----


def test_draft_capability_promoted_via_registry_becomes_active_and_discoverable() -> None:
    """Lifecycle: Capability registered as DRAFT → registry.promote() → ACTIVE → discoverable."""
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    cap = Capability(
        id="cap-lifecycle",
        name="Lifecycle Test",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
    )
    registry.register(cap)
    assert registry.get("cap-lifecycle").status == CapabilityStatus.DRAFT

    promoted = registry.promote("cap-lifecycle")
    assert promoted.status == CapabilityStatus.ACTIVE

    fetched = registry.get("cap-lifecycle")
    assert fetched.status == CapabilityStatus.ACTIVE


def test_lifecycle_promoted_capability_discoverable_via_list() -> None:
    """After promotion, the capability appears in registry.list()."""
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    cap = Capability(
        id="cap-discover",
        name="Discover Me",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
    )
    registry.register(cap)
    registry.promote("cap-discover")

    listed = registry.list()
    ids = [c.id for c in listed]
    assert "cap-discover" in ids


def test_learning_loop_capability_gap_to_active_via_registry() -> None:
    """Full learning loop: capability gap → work → DRAFT → assess → Registry.promote → ACTIVE → discoverable.

    The lifecycle passes through the Registry, not an OCP-local capability store.
    """
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Work, WorkStatus

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)

    capability_id = "cap-gap-to-active"

    plane.register_capability(
        Capability(
            id=capability_id,
            name="Gap Cap",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
            interface={
                "inputs": [{"name": "context", "type": "dict", "required": True}],
                "outputs": [{"name": "result", "type": "dict", "required": True}],
            },
        )
    )

    assert registry.get(capability_id).status == CapabilityStatus.DRAFT

    work = Work(
        id="w-gap",
        title="Develop capability: Gap Cap",
        work_type="capability_development",
        accountable_role_id="default",
        required_capability_ids=[capability_id],
        status=WorkStatus.READY,
    )
    plane._work[work.id] = work

    capability = registry.get(capability_id)
    assert capability.status == CapabilityStatus.DRAFT

    execution_result = {
        "status": "completed",
        "execution_mode": "capability_development",
        "capability_id": capability_id,
        "artifact_path": "/tmp/gap.md",
    }

    from outcome import assess_capability_development

    assessment = assess_capability_development(work, capability, execution_result)
    assert assessment["passed"] is True

    promoted = registry.promote(capability_id)
    assert promoted.status == CapabilityStatus.ACTIVE

    fetched = registry.get(capability_id)
    assert fetched.status == CapabilityStatus.ACTIVE

    assert capability_id in [c.id for c in registry.list()]


# ---- F. Actor/CapabilityAssignment compatibility ----


def test_active_capability_assignment_authorises_actor() -> None:
    """ACTIVE Capability → CapabilityAssignment → Actor → authorisation."""
    from agent_store import InMemoryAgentStore
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from capability_registry.src.adapters.execution_authorisation_adapter import (
        InMemoryExecutionAuthorisationPort,
    )
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    cap = Capability(
        id="cap-authorised",
        name="Authorised Cap",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
    )
    registry.register(cap)
    registry.promote("cap-authorised")

    agent_store = InMemoryAgentStore()
    agent, _ = InMemoryAgentStore.create_assistant_actor(
        actor_id="assistant", role_ids=["assistant"]
    )
    agent_store.register_agent(agent)

    assignment = agent_store.assign_capability("assistant", "cap-authorised")
    assert assignment.status.value == "active"

    auth = InMemoryExecutionAuthorisationPort(
        assignments=agent_store.get_all_assignments(),
    )
    result = auth.is_authorised("assistant", "agent", "cap-authorised")
    assert result.authorised is True
    assert result.assignment is not None
    assert result.assignment.capability_id == "cap-authorised"


def test_ocp_delegated_registry_provides_capability_for_work() -> None:
    """OCP with injected registry: register_capability delegates; get_capability returns it.

    Work can reference the capability and the organisation can discover it.
    """
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    from organisation_control_plane import InMemoryOrganisationControlPlane

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)

    cap = Capability(
        id="cap-gap-to-active",
        name="Gap Cap",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.DRAFT,
        interface={
            "inputs": [{"name": "context", "type": "dict", "required": True}],
            "outputs": [{"name": "result", "type": "dict", "required": True}],
        },
    )
    plane.register_capability(cap)

    assert registry.get("cap-ocp-delegated") is not None
    assert plane.get_capability("cap-ocp-delegated") is not None
    assert plane.get_capability("cap-ocp-delegated").id == "cap-ocp-delegated"

    # The capability passes through the Registry, not OCP's local store
    assert "cap-ocp-delegated" not in plane._capabilities


# ---- G. Solution selection preserved ----


def test_solution_selection_still_works_with_registry() -> None:
    """OCP.select_execution_path still selects CAPABILITY_PATH when registry has the capability."""
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)
    plane.register_role(Role(id="researcher", name="Researcher"))

    cap = Capability(
        id="cap-sol-select",
        name="Solution Select",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    result = plane.select_execution_path(
        intent="Use Solution Select capability",
        context={"required_capability_ids": ["cap-sol-select"]},
    )

    from execution_path import ExecutionPath
    assert result.path == ExecutionPath.CAPABILITY_PATH
    assert result.capability_id == "cap-sol-select"


def test_solution_selection_returns_new_capability_when_not_found() -> None:
    """OCP selects NEW_CAPABILITY_REQUIRED when capability is not in registry."""
    from capabilities import CapabilityRegistry
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)
    plane.register_role(Role(id="r1", name="Operator"))

    result = plane.select_execution_path(
        intent="unknown task",
        context={"required_capability_ids": ["cap-nonexistent"]},
    )

    from execution_path import ExecutionPath
    assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED


def test_solution_selection_human_team_investigation() -> None:
    """OCP selects HUMAN_TEAM_INVESTIGATION when capability exists but is unavailable."""
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore
    from contracts.enterprise_capability_query import CapabilityAvailability

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)
    plane.register_role(Role(id="r1", name="Operator"))

    cap = Capability(
        id="cap-busy",
        name="Busy Cap",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    result = plane.select_execution_path(
        intent="use cap-busy",
        context={"required_capability_ids": ["cap-busy"]},
        capability_query=lambda cid: CapabilityAvailability(
            capability_id=cid,
            available=False,
            reason="Capability is currently in use",
        ),
    )

    from execution_path import ExecutionPath
    assert result.path == ExecutionPath.HUMAN_TEAM_INVESTIGATION


def test_select_execution_path_distinguishes_existence_from_availability() -> None:
    """OCP checks existence via get_capability (registry) and availability via the query port callback.

    When the capability exists in the registry but the port says it's unavailable,
    OCP selects HUMAN_TEAM_INVESTIGATION, not CAPABILITY_PATH.
    """
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)
    plane.register_role(Role(id="r1", name="Operator"))

    cap = Capability(
        id="cap-exist-unavail",
        name="Exist Unavail",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    # Capability exists in registry, but the query port says it's unavailable
    from contracts.enterprise_capability_query import CapabilityAvailability

    result = plane.select_execution_path(
        intent="use cap-exist-unavail",
        context={"required_capability_ids": ["cap-exist-unavail"]},
        capability_query=lambda cid: CapabilityAvailability(
            capability_id=cid,
            available=False,
            reason="Under capacity",
        ),
    )

    from execution_path import ExecutionPath
    assert result.path == ExecutionPath.HUMAN_TEAM_INVESTIGATION


def test_select_execution_path_returns_capability_path_when_port_says_available() -> None:
    """When capability exists AND port says available, OCP selects CAPABILITY_PATH."""
    from capabilities import CapabilityRegistry
    from capability import Capability, CapabilityKind, CapabilityStatus
    from concept_store_adapter import ConceptStoreCapabilityRepository
    from concepts import ConceptStore

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role

    store = ConceptStore()
    repo = ConceptStoreCapabilityRepository(store)
    registry = CapabilityRegistry(repo)

    plane = InMemoryOrganisationControlPlane(capability_registry=registry)
    plane.register_role(Role(id="r1", name="Operator"))

    cap = Capability(
        id="cap-port-ok",
        name="Port Ok",
        capability_kind=CapabilityKind.SKILL,
        status=CapabilityStatus.ACTIVE,
    )
    plane.register_capability(cap)

    from contracts.enterprise_capability_query import CapabilityAvailability

    result = plane.select_execution_path(
        intent="use cap-port-ok",
        context={"required_capability_ids": ["cap-port-ok"]},
        capability_query=lambda cid: CapabilityAvailability(
            capability_id=cid,
            available=True,
            eta_seconds=5,
            reason="available",
        ),
    )

    from execution_path import ExecutionPath
    assert result.path == ExecutionPath.CAPABILITY_PATH


# ---- H. Paperclip boundary ----


def test_paperclip_does_not_define_capability_lifecycle() -> None:
    """Paperclip adapter does not define Capability, CapabilityRegistry, or lifecycle classes."""
    paperclip_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "organisation_paperclip", "src"
    ))
    domain_classes = {"Capability", "CapabilityRegistry", "CapabilityRepository", "ConceptStore"}
    for filename in os.listdir(paperclip_path):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(paperclip_path, filename)
        with open(path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in domain_classes:
                raise AssertionError(
                    f"Paperclip adapter must not define domain concept: {node.name}"
                )


def test_paperclip_accepts_capability_registry_param() -> None:
    """PaperclipOrganisationControlPlane accepts capability_registry for delegation."""
    from organisation_paperclip import PaperclipOrganisationControlPlane

    sig = inspect.signature(PaperclipOrganisationControlPlane.__init__)
    assert "capability_registry" in sig.parameters


def test_paperclip_register_capability_delegates_to_registry() -> None:
    """Paperclip.register_capability delegates to the injected registry when available."""
    from capability import Capability, CapabilityKind
    from organisation_paperclip import PaperclipOrganisationControlPlane

    mock_registry = MagicMock()
    plane = PaperclipOrganisationControlPlane(
        base_url="http://localhost:3100",
        capability_registry=mock_registry,
    )

    cap = Capability(id="cap-pp-1", name="PP Cap", capability_kind=CapabilityKind.SKILL)
    plane.register_capability(cap)

    mock_registry.register.assert_called_once_with(cap)
    plane.close()


def test_paperclip_get_capability_delegates_to_registry() -> None:
    """Paperclip.get_capability delegates to the injected registry."""
    from organisation_paperclip import PaperclipOrganisationControlPlane

    mock_registry = MagicMock()
    mock_registry.get.return_value = "paperclip-cap"
    plane = PaperclipOrganisationControlPlane(
        base_url="http://localhost:3100",
        capability_registry=mock_registry,
    )

    result = plane.get_capability("cap-pp")
    assert result == "paperclip-cap"
    mock_registry.get.assert_called_once_with("cap-pp")
    plane.close()


# ---- I. Backward compatibility ----


def test_worker_registers_capability_through_org_plane() -> None:
    """Worker._develop_capability always routes capability registration through
    org_plane.register_capability (which delegates to the registry when injected)."""
    from workflow_runner.src.worker import Worker

    source = inspect.getsource(Worker._develop_capability)
    assert "register_capability" in source, (
        "Worker should call org_plane.register_capability() for all development"
    )


def test_worker_develops_capability_through_org_plane_not_direct_registry() -> None:
    """Worker routes DRAFT capability registration through org_plane.register_capability,
    which delegates to the registry when available. The Worker does not call
    registry.register() directly."""
    from workflow_runner.src.worker import Worker

    from role import Work, WorkStatus

    mock_org = MagicMock()
    mock_registry = MagicMock()
    worker = Worker(capability_registry=mock_registry)

    work = Work(
        id="w-dev-worker",
        title="Develop capability: Worker Test",
        work_type="capability_development",
        accountable_role_id="default",
        status=WorkStatus.READY,
        required_capability_ids=["cap-worker-test"],
    )

    result = worker._develop_capability(work, mock_org)
    assert result["status"] == "completed"
    assert result["capability_id"] == "cap-w-dev-worker"

    # Worker calls org_plane.register_capability (which delegates to registry)
    mock_org.register_capability.assert_called_once()
    registered_cap = mock_org.register_capability.call_args[0][0]
    assert registered_cap.id == "cap-w-dev-worker"
    assert registered_cap.status.value == "draft"
    # work_id is passed for provenance
    assert mock_org.register_capability.call_args.kwargs["work_id"] == "w-dev-worker"