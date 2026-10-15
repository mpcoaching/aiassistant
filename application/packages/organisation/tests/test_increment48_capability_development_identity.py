"""
Architectural tests for Increment 48 — Capability Development Identity & Lifecycle Fixes.

Proves that:
- Work.develops_capability_id is a distinct semantic field from required_capability_ids
- WorkCreateRequest propagates develops_capability_id through WorkManagementAdapter
- ExecutionPathResult.capability_id is preserved on NEW_CAPABILITY_REQUIRED (all three cases)
- Worker preserves develops_capability_id as the Capability ID (identified case)
- Worker generates cap-{work.id} when no identity exists (anonymous case)
- CapabilityEvent.work_id is populated when capability registration is triggered by Work
- Operations fails fast (fail_work) for capability-development Work without a registry
- DRAFT → ACTIVE promotion works through the full lifecycle
- Duplicate/retry uses existing registry idempotency (upsert_capability)
- End-to-end: identified capability ID == final Capability ID
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from capability import Capability, CapabilityKind, CapabilityStatus
from contracts.capability_discovery import CapabilityCandidate
from contracts.organisational_events import (
    CapabilityEvent,
    CapabilityEventType,
    WorkEvent,
    WorkEventType,
)
from contracts.work_management import WorkCreateRequest

from execution_path import ExecutionPath, ExecutionPathResult
from role import Work, WorkStatus

# --------------------------------------------------------------------------- #
# A. Work.develops_capability_id field existence and semantics
# --------------------------------------------------------------------------- #


class TestWorkDevelopsCapabilityId:
    """Work has develops_capability_id, semantically distinct from
    required_capability_ids."""

    def test_work_has_develops_capability_id_field(self) -> None:
        """Work model includes develops_capability_id as an optional field."""
        work = Work(
            id="w-1",
            title="Develop capability: Test",
            work_type="capability_development",
            accountable_role_id="default",
        )
        assert hasattr(work, "develops_capability_id")
        assert work.develops_capability_id is None

    def test_work_develops_capability_id_can_be_set(self) -> None:
        """develops_capability_id accepts a string identity."""
        work = Work(
            id="w-2",
            title="Develop capability: Test",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id="cap-identified",
        )
        assert work.develops_capability_id == "cap-identified"

    def test_develops_capability_id_is_distinct_from_required_capability_ids(self) -> None:
        """required_capability_ids and develops_capability_id are independent
        fields. A capability_development Work carries the capability it develops
        in develops_capability_id, NOT in required_capability_ids."""
        work = Work(
            id="w-3",
            title="Develop capability: Test Cap",
            work_type="capability_development",
            accountable_role_id="default",
            required_capability_ids=["cap-required-to-execute"],
            develops_capability_id="cap-being-developed",
        )
        assert work.required_capability_ids == ["cap-required-to-execute"]
        assert work.develops_capability_id == "cap-being-developed"
        assert "cap-being-developed" not in work.required_capability_ids

    def test_bau_work_develops_capability_id_is_none_by_default(self) -> None:
        """Ordinary BAU Work does not develop a capability — field defaults to None."""
        work = Work(
            id="w-4",
            title="Run report",
            work_type="bau",
            accountable_role_id="default",
        )
        assert work.develops_capability_id is None


# --------------------------------------------------------------------------- #
# B. WorkCreateRequest propagation
# --------------------------------------------------------------------------- #


class TestWorkCreateRequestPropagation:
    """WorkCreateRequest carries develops_capability_id and the adapter
    propagates it to the Work model."""

    def test_work_create_request_has_develops_capability_id(self) -> None:
        """WorkCreateRequest includes develops_capability_id."""
        assert "develops_capability_id" in WorkCreateRequest.model_fields

    def test_work_create_request_develops_capability_id_defaults_none(self) -> None:
        """WorkCreateRequest.develops_capability_id is None by default."""
        req = WorkCreateRequest(
            title="Test",
            accountable_role_id="default",
        )
        assert req.develops_capability_id is None

    def test_work_create_request_accepts_develops_capability_id(self) -> None:
        """WorkCreateRequest accepts a capability identity to develop."""
        req = WorkCreateRequest(
            title="Develop capability: Test",
            accountable_role_id="default",
            work_type="capability_development",
            develops_capability_id="cap-from-request",
        )
        assert req.develops_capability_id == "cap-from-request"

    def test_work_management_adapter_propagates_develops_capability_id(self) -> None:
        """WorkManagementAdapter.create_work maps develops_capability_id onto Work."""
        from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="default", name="Default"))
        adapter = WorkManagementAdapter(plane)

        req = WorkCreateRequest(
            title="Develop capability: Gap Cap",
            accountable_role_id="default",
            work_type="capability_development",
            develops_capability_id="cap-gap-1",
        )
        ref = adapter.create_work(req)
        work = plane.get_work(ref.work_id)
        assert work is not None
        assert work.develops_capability_id == "cap-gap-1"
        assert work.required_capability_ids == []

    def test_work_management_adapter_propagates_required_capability_ids(self) -> None:
        """WorkManagementAdapter still propagates required_capability_ids
        independently from develops_capability_id."""
        from organisation.src.adapters.work_management_adapter import WorkManagementAdapter

        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="default", name="Default"))
        adapter = WorkManagementAdapter(plane)

        req = WorkCreateRequest(
            title="Develop capability: Gap Cap",
            accountable_role_id="default",
            work_type="capability_development",
            required_capability_ids=["cap-helper"],
            develops_capability_id="cap-gap-2",
        )
        ref = adapter.create_work(req)
        work = plane.get_work(ref.work_id)
        assert work is not None
        assert work.required_capability_ids == ["cap-helper"]
        assert work.develops_capability_id == "cap-gap-2"


# --------------------------------------------------------------------------- #
# C. ExecutionPathResult.capability_id preservation (OCP)
# --------------------------------------------------------------------------- #


class TestExecutionPathCapabilityIdPreservation:
    """OCP select_execution_path preserves capability_id for all three
    capability-gap cases."""

    def _make_plane(self) -> Any:
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="default", name="Default"))
        return plane

    def test_case_a_user_identifies_capability(self) -> None:
        """Case A — user provides required_capability_ids, capability not in
        registry, no capability_query → NEW_CAPABILITY_REQUIRED with
        capability_id preserved."""
        plane = self._make_plane()
        result = plane.select_execution_path(
            intent="do the gap thing",
            context={"required_capability_ids": ["cap-user-identified"]},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-user-identified"

    def test_case_a_with_query_port_returns_none(self) -> None:
        """Case A — capability_query returns None (capability not operational)
        → NEW_CAPABILITY_REQUIRED with capability_id preserved."""
        plane = self._make_plane()
        result = plane.select_execution_path(
            intent="do the gap thing",
            context={"required_capability_ids": ["cap-user-identified"]},
            capability_query=lambda cid: None,
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-user-identified"

    def test_case_b_ocp_derives_capability_from_candidates(self) -> None:
        """Case B — OCP identifies a capability from candidate_capabilities,
        capability_query returns None → NEW_CAPABILITY_REQUIRED with
        capability_id preserved."""
        plane = self._make_plane()
        result = plane.select_execution_path(
            intent="use derived cap",
            context={
                "required_capability_ids": ["cap-ocp-derived"],
                "candidate_capabilities": [{"id": "cap-ocp-derived", "name": "Derived"}],
            },
            capability_query=lambda cid: None,
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-ocp-derived"

    def test_case_b_without_required_ids_uses_candidate(self) -> None:
        """Case B — capability_query returns None for a candidate that was
        not in required_capability_ids → NEW_CAPABILITY_REQUIRED with
        capability_id preserved."""
        plane = self._make_plane()
        result = plane.select_execution_path(
            intent="use candidate cap",
            context={
                "required_capability_ids": [],
                "candidate_capabilities": [{"id": "cap-from-candidate", "name": "Cand"}],
            },
            capability_query=lambda cid: None,
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-from-candidate"

    def test_case_c_no_identity_returns_none_capability_id(self) -> None:
        """Case C — no required_capability_ids and no candidate_capabilities
        → NEW_CAPABILITY_REQUIRED with capability_id=None."""
        plane = self._make_plane()
        result = plane.select_execution_path(
            intent="totally novel task",
            context={"required_capability_ids": []},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id is None

    def test_registered_capability_yields_capability_path(self) -> None:
        """When a required capability IS in the registry and no
        capability_query is provided, CAPABILITY_PATH is returned."""
        plane = self._make_plane()
        cap = Capability(
            id="cap-registered-test",
            name="Registered",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.ACTIVE,
        )
        plane.register_capability(cap)

        result = plane.select_execution_path(
            intent="use existing cap",
            context={"required_capability_ids": ["cap-registered-test"]},
        )
        assert result.path == ExecutionPath.CAPABILITY_PATH
        assert result.capability_id == "cap-registered-test"


# --------------------------------------------------------------------------- #
# D. Chat-layer capability-gap handlers propagate develops_capability_id
# --------------------------------------------------------------------------- #


class TestChatGapHandlerPropagation:
    """Both chat-layer gap handlers set develops_capability_id, not
    required_capability_ids."""

    def _make_chat(self) -> Any:
        from ai.src.chat import AssistantChatService

        chat = AssistantChatService.__new__(AssistantChatService)
        chat._work_management = MagicMock()
        chat._agent_id = None
        ref = MagicMock()
        ref.work_id = "work-test-48"
        chat._work_management.create_work.return_value = ref
        chat._work_management.mark_ready = MagicMock()
        chat._capability_discovery = None
        chat._enterprise_capability_query = None
        chat._solution_selection = None
        chat._ai_response = None
        chat._action_policy = None
        chat._workflow_runner = None
        chat._session_factory = None
        chat._organisational_context = None
        chat._enterprise_info = None
        chat._pattern_execution = None
        chat._intent_classifier = None
        return chat

    def test_handle_new_capability_required_sets_develops_capability_id(self) -> None:
        """_handle_new_capability_required_response propagates capability_id as
        develops_capability_id on capability_development Work."""
        chat = self._make_chat()
        path_result = ExecutionPathResult(
            path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
            capability_id="cap-chat-gap",
            reason="capability gap",
        )
        intent = MagicMock()
        intent.raw = {"text": "do the gap thing"}
        frame = MagicMock()
        frame.recognition_level = MagicMock()
        frame.recognition_level.value = "high"

        chat._handle_new_capability_required_response(path_result, intent, frame, "ses-48")

        request = chat._work_management.create_work.call_args[0][0]
        assert request.work_type == "capability_development"
        assert request.develops_capability_id == "cap-chat-gap"
        assert request.required_capability_ids == []

    def test_handle_new_capability_required_anonymous_sets_none(self) -> None:
        """When path_result.capability_id is None (Case C), develops_capability_id
        is None."""
        chat = self._make_chat()
        path_result = ExecutionPathResult(
            path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
            capability_id=None,
            reason="no gap identified",
        )
        intent = MagicMock()
        intent.raw = {"text": "do something novel"}
        frame = MagicMock()
        frame.recognition_level = MagicMock()
        frame.recognition_level.value = "medium"

        chat._handle_new_capability_required_response(path_result, intent, frame, "ses-48b")

        request = chat._work_management.create_work.call_args[0][0]
        assert request.work_type == "capability_development"
        assert request.develops_capability_id is None

    def test_handle_capability_gap_sets_develops_capability_id(self) -> None:
        """_handle_capability_gap propagates candidate.id as develops_capability_id."""
        chat = self._make_chat()
        candidate = CapabilityCandidate(
            id="cap-gap-candidate",
            name="Gap Candidate",
            description="A gap candidate",
            kind="skill",
            confidence=0.9,
        )
        intent = MagicMock()
        intent.raw = {"text": "do the gap thing"}
        frame = MagicMock()
        frame.recognition_level = MagicMock()
        frame.recognition_level.value = "high"

        chat._handle_capability_gap(intent, frame, "ses-48c", candidate)

        request = chat._work_management.create_work.call_args[0][0]
        assert request.work_type == "capability_development"
        assert request.develops_capability_id == "cap-gap-candidate"
        assert request.required_capability_ids == []


# --------------------------------------------------------------------------- #
# E. Worker capability identity preservation
# --------------------------------------------------------------------------- #


class TestWorkerCapabilityIdentity:
    """Worker._develop_capability:
    - Preserves develops_capability_id when present
    - Generates cap-{work.id} when absent
    """

    def test_worker_preserves_develops_capability_id(self) -> None:
        """When develops_capability_id is set, the Capability uses that identity."""
        from workflow_runner.src.worker import Worker

        work = Work(
            id="w-identified-48",
            title="Develop capability: Identified Cap",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id="cap-identified-48",
            status=WorkStatus.READY,
        )
        mock_org = MagicMock()
        worker = Worker(output_dir="/tmp/test_worker_48_identified")
        result = worker._develop_capability(work, mock_org)

        assert result["capability_id"] == "cap-identified-48"
        assert result["status"] == "completed"
        assert result["execution_mode"] == "capability_development"

        mock_org.register_capability.assert_called_once()
        registered_cap = mock_org.register_capability.call_args[0][0]
        assert registered_cap.id == "cap-identified-48"
        # work_id is passed to register_capability
        assert mock_org.register_capability.call_args.kwargs["work_id"] == "w-identified-48"

    def test_worker_generates_id_when_anonymous(self) -> None:
        """When develops_capability_id is None, the Worker generates cap-{work.id}."""
        from workflow_runner.src.worker import Worker

        work = Work(
            id="w-anonymous-48",
            title="Develop capability: Anonymous Cap",
            work_type="capability_development",
            accountable_role_id="default",
            status=WorkStatus.READY,
        )
        mock_org = MagicMock()
        worker = Worker(output_dir="/tmp/test_worker_48_anon")
        result = worker._develop_capability(work, mock_org)

        assert result["capability_id"] == "cap-w-anonymous-48"
        mock_org.register_capability.assert_called_once()
        registered_cap = mock_org.register_capability.call_args[0][0]
        assert registered_cap.id == "cap-w-anonymous-48"


# --------------------------------------------------------------------------- #
# F. CapabilityEvent work_id provenance
# --------------------------------------------------------------------------- #


class TestCapabilityEventProvenance:
    """CapabilityEvent carries work_id when registration is triggered by Work."""

    def test_ocp_register_capability_populates_work_id(self) -> None:
        """InMemoryOrganisationControlPlane.register_capability emits
        CapabilityEvent with work_id when provided."""
        events: list = []
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="default", name="Default"))
        plane.on_event(events.append)

        cap = Capability(
            id="cap-event-test",
            name="Event Cap",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        plane.register_capability(cap, work_id="w-event-source")

        capability_events = [e for e in events if isinstance(e, CapabilityEvent)]
        assert len(capability_events) == 1
        assert capability_events[0].event_type == CapabilityEventType.REGISTERED
        assert capability_events[0].work_id == "w-event-source"

    def test_ocp_register_capability_work_id_none_when_not_provided(self) -> None:
        """When work_id is not passed, CapabilityEvent.work_id is None."""
        events: list = []
        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        plane = InMemoryOrganisationControlPlane()
        plane.register_role(Role(id="default", name="Default"))
        plane.on_event(events.append)

        cap = Capability(
            id="cap-event-none",
            name="Event None",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        plane.register_capability(cap)

        capability_events = [e for e in events if isinstance(e, CapabilityEvent)]
        assert len(capability_events) == 1
        assert capability_events[0].work_id is None

    def test_worker_registration_passes_work_id(self) -> None:
        """Worker._develop_capability calls org_plane.register_capability
        with work_id=work.id, so the event carries provenance."""
        from workflow_runner.src.worker import Worker

        work = Work(
            id="w-provenance-48",
            title="Develop capability: Provenance",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id="cap-prov-48",
        )
        mock_org = MagicMock()
        worker = Worker(output_dir="/tmp/test_worker_48_prov")
        worker._develop_capability(work, mock_org)

        assert mock_org.register_capability.call_args.kwargs["work_id"] == "w-provenance-48"

    def test_development_event_types_not_emitted(self) -> None:
        """DEVELOPMENT_STARTED and DEVELOPMENT_COMPLETED are defined but
        never emitted — the lifecycle is represented by register + promote."""
        import os

        src_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "src")
        )
        wf_src = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "workflow_runner", "src")
        )
        for src_dir in [src_root, wf_src]:
            for dirpath, _, filenames in os.walk(src_dir):
                for fname in filenames:
                    if not fname.endswith(".py"):
                        continue
                    fpath = os.path.join(dirpath, fname)
                    with open(fpath) as f:
                        content = f.read()
                    assert "DEVELOPMENT_STARTED" not in content, (
                        f"DEVELOPMENT_STARTED emitted in {fpath}"
                    )
                    assert "DEVELOPMENT_COMPLETED" not in content, (
                        f"DEVELOPMENT_COMPLETED emitted in {fpath}"
                    )


# --------------------------------------------------------------------------- #
# G. Operations registry fail-fast
# --------------------------------------------------------------------------- #


class TestOperationsRegistryFailFast:
    """Operations must not silently bypass capability-development assessment."""

    def test_capability_development_fails_without_registry(self) -> None:
        """When Operations has no CapabilityRegistry, capability-development
        Work is failed — not silently completed."""
        from workflow_runner.src.operations import Operations

        mock_org = MagicMock()
        work = Work(
            id="w-no-registry-48",
            title="Develop capability: No Registry",
            work_type="capability_development",
            accountable_role_id="default",
        )
        mock_org.get_work.return_value = work

        worker_backend = MagicMock()
        worker_backend.can_handle.return_value = True
        worker_backend.execute.return_value = {"status": "completed"}

        ops = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
            capability_registry=None,
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w-no-registry-48",
            title="Develop capability: No Registry",
            work_type="capability_development",
            required_capability_ids=[],
            status="ready",
            priority="normal",
        )
        ops._handle_event(event)

        # The worker should NOT have been executed
        worker_backend.execute.assert_not_called()
        # The work should be failed, not completed
        mock_org.fail_work.assert_called_once()
        fail_args = mock_org.fail_work.call_args[0]
        assert fail_args[0] == "w-no-registry-48"
        assert fail_args[1]["error"] == "capability_registry_not_configured"
        # complete_work should NOT have been called
        mock_org.complete_work.assert_not_called()

    def test_bau_work_executes_without_registry(self) -> None:
        """BAU Work executes normally even without a CapabilityRegistry."""
        from workflow_runner.src.operations import Operations

        mock_org = MagicMock()
        work = Work(
            id="w-bau-48",
            title="BAU Task",
            work_type="bau",
            accountable_role_id="default",
        )
        mock_org.get_work.return_value = work

        worker_backend = MagicMock()
        worker_backend.can_handle.return_value = True
        worker_backend.execute.return_value = {"status": "completed"}

        ops = Operations(
            org_plane=mock_org,
            backends=[worker_backend],
            capability_registry=None,
        )

        event = WorkEvent(
            event_type=WorkEventType.READY,
            work_id="w-bau-48",
            title="BAU Task",
            work_type="bau",
            required_capability_ids=[],
            status="ready",
            priority="normal",
        )
        ops._handle_event(event)

        worker_backend.execute.assert_called_once()
        mock_org.complete_work.assert_called_once()


# --------------------------------------------------------------------------- #
# H. Capability registration idempotency
# --------------------------------------------------------------------------- #


class TestCapabilityRegistrationIdempotency:
    """CapabilityRegistry.register is idempotent (upsert) — duplicate
    registration preserves one canonical identity."""

    def test_register_upsert_preserves_identity(self, tmp_path) -> None:
        """Registering a capability with the same ID twice does not create
        a duplicate — the registry uses upsert semantics."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)

        cap = Capability(
            id="cap-idempotent-48",
            name="Idempotent",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        registry.register(cap)
        registry.register(cap)  # second registration

        retrieved = registry.get("cap-idempotent-48")
        assert retrieved is not None
        assert retrieved.id == "cap-idempotent-48"
        assert retrieved.status == CapabilityStatus.DRAFT

    def test_register_with_same_id_updates_in_place(self, tmp_path) -> None:
        """Re-registering a capability with the same ID but different field
        values updates in place — single canonical identity."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)

        cap_v1 = Capability(
            id="cap-update-48",
            name="Update Me",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        registry.register(cap_v1)

        cap_v2 = Capability(
            id="cap-update-48",
            name="Updated Name",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        registry.register(cap_v2)

        retrieved = registry.get("cap-update-48")
        assert retrieved is not None
        assert retrieved.name == "Updated Name"
        assert retrieved.id == "cap-update-48"


# --------------------------------------------------------------------------- #
# I. DRAFT → ACTIVE promotion
# --------------------------------------------------------------------------- #


class TestCapabilityLifecyclePromotion:
    """CapabilityRegistry.promote transitions DRAFT → ACTIVE."""

    def test_promote_transitions_draft_to_active(self, tmp_path) -> None:
        """promote() moves a capability from DRAFT to ACTIVE."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)

        cap = Capability(
            id="cap-promote-48",
            name="Promote Me",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        registry.register(cap)
        assert registry.get("cap-promote-48").status == CapabilityStatus.DRAFT

        promoted = registry.promote("cap-promote-48")
        assert promoted.status == CapabilityStatus.ACTIVE

    def test_promote_records_maturation_history(self, tmp_path) -> None:
        """promote() records promoted_at in the capability payload."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)

        cap = Capability(
            id="cap-history-48",
            name="History",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.DRAFT,
        )
        registry.register(cap)
        registry.promote("cap-history-48")

        retrieved = registry.get("cap-history-48")
        assert retrieved is not None
        history = retrieved.payload.get("maturation_history") or {}
        assert "promoted_at" in history


# --------------------------------------------------------------------------- #
# J. End-to-end traceability
# --------------------------------------------------------------------------- #


class TestEndToEndTraceability:
    """Full lifecycle: identified capability → Work → Capability → registry →
    assessment → promotion. Same ID throughout."""

    def test_identified_capability_id_survives_full_lifecycle(self, tmp_path) -> None:
        """original capability ID == final Capability ID when identity was
        available at the beginning."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from organisation_control_plane import InMemoryOrganisationControlPlane
        from outcome import assess_capability_development
        from role import Role

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)
        plane = InMemoryOrganisationControlPlane(capability_registry=registry)
        plane.register_role(Role(id="default", name="Default"))

        # Step 1: identified missing capability
        original_capability_id = "cap-e2e-identified-48"

        # Step 2: OCP returns NEW_CAPABILITY_REQUIRED with capability_id
        path_result = plane.select_execution_path(
            intent="do task requiring missing cap",
            context={"required_capability_ids": [original_capability_id]},
        )
        assert path_result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert path_result.capability_id == original_capability_id

        # Step 3: Work created with develops_capability_id
        work = Work(
            id="w-e2e-48",
            title="Develop capability: E2E Test",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=path_result.capability_id,
            status=WorkStatus.READY,
        )

        # Step 4: Worker develops capability, preserving identity
        worker = Worker(
            output_dir=str(tmp_path / "worker_out"),
            capability_registry=registry,
        )
        result = worker._develop_capability(work, plane)
        assert result["capability_id"] == original_capability_id

        # Step 5: Capability exists in registry with same ID
        cap = registry.get(original_capability_id)
        assert cap is not None
        assert cap.id == original_capability_id
        assert cap.status == CapabilityStatus.DRAFT

        # Step 6: Assessment passes
        assessment = assess_capability_development(work, cap, result)
        assert assessment["passed"] is True
        assert assessment["source_work_id"] == "w-e2e-48"

        # Step 7: Promotion to ACTIVE
        promoted = registry.promote(original_capability_id)
        assert promoted.status == CapabilityStatus.ACTIVE
        assert promoted.id == original_capability_id

    def test_anonymous_capability_generates_new_id(self, tmp_path) -> None:
        """No capability ID → develops_capability_id=None → new generated
        Capability ID (cap-{work.id})."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)
        plane = InMemoryOrganisationControlPlane(capability_registry=registry)
        plane.register_role(Role(id="default", name="Default"))

        # Case C: no capability identity
        path_result = plane.select_execution_path(
            intent="totally novel task",
            context={"required_capability_ids": []},
        )
        assert path_result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert path_result.capability_id is None

        work = Work(
            id="w-anon-e2e-48",
            title="Develop capability: Anonymous Cap",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=None,  # Case C
            status=WorkStatus.READY,
        )

        worker = Worker(
            output_dir=str(tmp_path / "worker_out_anon"),
            capability_registry=registry,
        )
        result = worker._develop_capability(work, plane)

        generated_id = f"cap-{work.id}"
        assert result["capability_id"] == generated_id

        cap = registry.get(generated_id)
        assert cap is not None
        assert cap.id == generated_id


# --------------------------------------------------------------------------- #
# K. Duplicate development attempts
# --------------------------------------------------------------------------- #


class TestDuplicateDevelopment:
    """Two development attempts for the same identified capability."""

    def test_duplicate_registration_preserves_canonical_id(self, tmp_path) -> None:
        """If the same identified capability is already registered (DRAFT),
        a second development Work targeting the same develops_capability_id
        should not create a second Capability — the registry's upsert
        semantics preserve one canonical identity."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)
        plane = InMemoryOrganisationControlPlane(capability_registry=registry)
        plane.register_role(Role(id="default", name="Default"))

        cap_id = "cap-duplicate-48"

        # First development attempt
        work1 = Work(
            id="w-dup-1-48",
            title="Develop capability: Dup Cap",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=cap_id,
        )
        worker = Worker(
            output_dir=str(tmp_path / "worker_out_dup1"),
            capability_registry=registry,
        )
        worker._develop_capability(work1, plane)
        cap1 = registry.get(cap_id)
        assert cap1 is not None
        assert cap1.id == cap_id

        # Second development attempt with same identity
        work2 = Work(
            id="w-dup-2-48",
            title="Develop capability: Dup Cap Again",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=cap_id,
        )
        worker._develop_capability(work2, plane)

        # Still only one capability in the registry
        cap2 = registry.get(cap_id)
        assert cap2 is not None
        assert cap2.id == cap_id
        assert cap1.id == cap2.id

    def test_anonymous_retries_create_separate_capabilities(self, tmp_path) -> None:
        """Two anonymous development Works create two separate capabilities
        (different cap-{work.id} IDs) — no identity to deduplicate against."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from organisation_control_plane import InMemoryOrganisationControlPlane
        from role import Role

        store = ConceptStore(data_dir=str(tmp_path))
        repo = ConceptStoreCapabilityRepository(store)
        registry = CapabilityRegistry(repo)
        plane = InMemoryOrganisationControlPlane(capability_registry=registry)
        plane.register_role(Role(id="default", name="Default"))

        worker = Worker(
            output_dir=str(tmp_path / "worker_out_anon_dup"),
            capability_registry=registry,
        )

        work1 = Work(
            id="w-anon-a-48",
            title="Develop capability: Anon A",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=None,
        )
        result1 = worker._develop_capability(work1, plane)
        assert result1["capability_id"] == "cap-w-anon-a-48"

        work2 = Work(
            id="w-anon-b-48",
            title="Develop capability: Anon B",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=None,
        )
        result2 = worker._develop_capability(work2, plane)
        assert result2["capability_id"] == "cap-w-anon-b-48"
        assert result1["capability_id"] != result2["capability_id"]


# --------------------------------------------------------------------------- #
# L. Semantic separation summary
# --------------------------------------------------------------------------- #


class TestSemanticSeparation:
    """required_capability_ids = capabilities needed to perform Work
    develops_capability_id = capability produced/developed by Work"""

    def test_required_capability_ids_and_develops_are_independent(self) -> None:
        """Both fields can coexist on the same Work with different semantics."""
        work = Work(
            id="w-sep-1",
            title="Develop capability: Sep Test",
            work_type="capability_development",
            accountable_role_id="default",
            required_capability_ids=["cap-needed-to-work"],
            develops_capability_id="cap-being-built",
        )
        # required = capabilities the work needs to execute
        assert work.required_capability_ids == ["cap-needed-to-work"]
        # develops = the capability this work produces
        assert work.develops_capability_id == "cap-being-built"
        # They are not the same value in general
        assert "cap-being-built" not in work.required_capability_ids

    def test_develops_capability_id_none_for_bau_work(self) -> None:
        """BAU Work has develops_capability_id=None."""
        work = Work(
            id="w-sep-2",
            title="Run analysis",
            work_type="bau",
            accountable_role_id="default",
            required_capability_ids=["cap-analysis"],
        )
        assert work.required_capability_ids == ["cap-analysis"]
        assert work.develops_capability_id is None
