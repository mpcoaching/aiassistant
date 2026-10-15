"""
Increment 46 — Capability Gap → People Boundary Investigation Tests.

Architec-turally-focused tests verifying the NEW_CAPABILITY_REQUIRED
path and its People/Capability layer boundaries.

Scope:
- select_execution_path decision hierarchy
- capability_id propagation from path_result to Work
- Worker._develop_capability ID generation
- CapabilityEventType DEVELOPMENT_STARTED / DEVELOPMENT_COMPLETED emissions
- record_work_learning exclusion of capability_development work
- CapabilityRegistry role in the post-development lifecycle
- People/Capability boundary (no org-layer capability ownership)
- Paperclip OCP select_execution_path (no capability_id in fallback)
- capability_id preservation through the solution selection adapter

These tests are READ-ONLY observations: they verify current semantics
without modifying production code. They establish whether the
capability gap boundary is coherent or a latent defect exists.
"""

from __future__ import annotations

import inspect
import os
from unittest.mock import MagicMock

import pytest
from contracts.organisational_events import (
    CapabilityEvent,
    CapabilityEventType,
)

from execution_path import ExecutionPath, ExecutionPathResult
from organisation_control_plane import InMemoryOrganisationControlPlane
from role import Role, Work

# --------------------------------------------------------------------------- #
# Helpers / paths
# --------------------------------------------------------------------------- #

PEOPLE_CAPABILITY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "people_capability", "src")
)
CAPABILITY_REGISTRY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "capability_registry", "src")
)
WORKFLOW_RUNNER_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "workflow_runner", "src")
)


def _make_plane() -> InMemoryOrganisationControlPlane:
    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="default", name="Default"))
    return plane


# --------------------------------------------------------------------------- #
# A. select_execution_path decision hierarchy
# --------------------------------------------------------------------------- #


class TestSelectExecutionPathDecisionHierarchy:
    """Verify the OCP decision hierarchy: workflow → capability →
    human_team_investigation → new_capability_required."""

    def test_workflow_takes_precedence_over_capability(self) -> None:
        """When both a matching workflow and a required capability exist,
        EXISTING_WORKFLOW is selected."""
        plane = _make_plane()
        wf = MagicMock()
        wf.name = "test-wf"
        wf.description = "desc"
        wf.model_dump = MagicMock(return_value={"name": "test-wf", "description": "desc"})

        def lookup(intent: str) -> list:
            return [wf] if "specific" in intent.lower() else []

        result = plane.select_execution_path(
            intent="run the specific task",
            context={"required_capability_ids": ["cap-thing"]},
            workflow_lookup=lookup,
        )
        assert result.path == ExecutionPath.EXISTING_WORKFLOW
        assert result.workflow is wf

    def test_capability_path_selected_when_no_workflow_but_capability_exists(self) -> None:
        """If no workflow matches but a required capability exists in the
        local store, CAPABILITY_PATH is returned (fallback, no query port)."""
        plane = _make_plane()

        from capability import Capability, CapabilityKind

        cap = Capability(
            id="cap-existing",
            name="Existing Cap",
            capability_kind=CapabilityKind.SKILL,
        )
        plane.register_capability(cap)

        result = plane.select_execution_path(
            intent="use existing cap",
            context={"required_capability_ids": ["cap-existing"]},
        )
        assert result.path == ExecutionPath.CAPABILITY_PATH
        assert result.capability_id == "cap-existing"

    def test_human_team_investigation_when_capability_exists_but_unavailable(self) -> None:
        """When a capability exists but the query port says unavailable,
        HUMAN_TEAM_INVESTIGATION is selected."""
        from capability import Capability, CapabilityKind
        from contracts.enterprise_capability_query import CapabilityAvailability

        plane = _make_plane()
        cap = Capability(
            id="cap-busy",
            name="Busy Cap",
            capability_kind=CapabilityKind.SKILL,
        )
        plane.register_capability(cap)

        result = plane.select_execution_path(
            intent="use cap-busy",
            context={"required_capability_ids": ["cap-busy"]},
            capability_query=lambda cid: CapabilityAvailability(
                capability_id=cid,
                available=False,
                reason="Under maintenance",
            ),
        )
        assert result.path == ExecutionPath.HUMAN_TEAM_INVESTIGATION
        assert result.capability_id == "cap-busy"

    def test_new_capability_required_when_no_workflow_no_capability(self) -> None:
        """No workflow and no capability → NEW_CAPABILITY_REQUIRED
        with capability_id=None (no specific gap identified)."""
        plane = _make_plane()
        result = plane.select_execution_path(
            intent="do something entirely novel",
            context={"required_capability_ids": []},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id is None

    def test_new_capability_required_preserves_required_capability_id_without_query_port(self) -> None:
        """When a required_capability_id is unknown to the registry AND no
        capability_query is provided, OCP returns NEW_CAPABILITY_REQUIRED
        with capability_id preserved from the required list."""
        plane = _make_plane()
        result = plane.select_execution_path(
            intent="use missing cap",
            context={"required_capability_ids": ["cap-missing"]},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-missing", (
            "Missing capability_id from required_capability_ids IS now preserved "
            "when it is absent from the registry and no query_port is supplied"
        )

    def test_new_capability_required_preserves_capability_id_with_query_port(self) -> None:
        """When a required_capability_id is unknown to the query port
        (returns None), OCP returns NEW_CAPABILITY_REQUIRED with the specific
        capability_id."""
        plane = _make_plane()
        result = plane.select_execution_path(
            intent="use missing cap",
            context={
                "required_capability_ids": ["cap-missing"],
                "candidate_capabilities": [{"id": "cap-missing", "name": "Missing"}],
            },
            capability_query=lambda cid: None,
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == "cap-missing"

    def test_query_port_returns_none_treated_as_gap_not_unavailable(self) -> None:
        """When capability_query returns None (capability unknown to the
        operational layer), OCP treats it as NEW_CAPABILITY_REQUIRED,
        not HUMAN_TEAM_INVESTIGATION."""
        plane = _make_plane()
        result = plane.select_execution_path(
            intent="unknown task",
            context={"required_capability_ids": ["cap-unknown"]},
            capability_query=lambda cid: None,
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED


# --------------------------------------------------------------------------- #
# B. capability_id propagation from path_result to Work
# --------------------------------------------------------------------------- #


class TestCapabilityIdPropagation:
    """Verify how capability_id from ExecutionPathResult flows into
    Work.develops_capability_id at each Work-creation site in the
    chat layer."""

    def test_handle_new_capability_required_propagates_develops_capability_id(self) -> None:
        """_handle_new_capability_required_response creates a capability_development
        Work with develops_capability_id set from path_result.capability_id."""
        from ai.src.chat import AssistantChatService

        # Build a minimal chat service with only _work_management wired.
        work_port = MagicMock()
        result_ref = MagicMock()
        result_ref.work_id = "work-newcap-1"
        work_port.create_work.return_value = result_ref

        chat = AssistantChatService.__new__(AssistantChatService)
        chat._work_management = work_port
        chat._agent_id = None
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

        path_result = ExecutionPathResult(
            path=ExecutionPath.NEW_CAPABILITY_REQUIRED,
            capability_id="cap-gap-identified",
            reason="capability gap",
        )

        intent = MagicMock()
        intent.raw = {"text": "do the gap thing"}

        frame = MagicMock()
        frame.recognition_level = MagicMock()
        frame.recognition_level.value = "high"

        chat._handle_new_capability_required_response(path_result, intent, frame, "ses-x")

        work_port.create_work.assert_called_once()
        request = work_port.create_work.call_args[0][0]
        assert request.work_type == "capability_development"
        assert request.develops_capability_id == "cap-gap-identified", (
            "capability_id from path_result is propagated to "
            "Work.develops_capability_id"
        )
        assert request.required_capability_ids == [], (
            "develops_capability_id is NOT placed in required_capability_ids"
        )

    def test_handle_capability_gap_propagates_develops_capability_id(self) -> None:
        """_handle_capability_gap creates a capability_development Work with
        develops_capability_id set from candidate.id."""
        from ai.src.chat import AssistantChatService
        from contracts.capability_discovery import CapabilityCandidate

        work_port = MagicMock()
        result_ref = MagicMock()
        result_ref.work_id = "work-gap-1"
        work_port.create_work.return_value = result_ref

        chat = AssistantChatService.__new__(AssistantChatService)
        chat._work_management = work_port
        chat._agent_id = None
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

        chat._handle_capability_gap(intent, frame, "ses-x", candidate)

        work_port.create_work.assert_called_once()
        request = work_port.create_work.call_args[0][0]
        assert request.work_type == "capability_development"
        assert request.develops_capability_id == "cap-gap-candidate", (
            "_handle_capability_gap propagates candidate.id to "
            "Work.develops_capability_id"
        )
        assert request.required_capability_ids == [], (
            "develops_capability_id is NOT placed in required_capability_ids"
        )

    def test_human_team_investigation_does_propagate_capability_id(self) -> None:
        """For comparison: _handle_human_team_investigation_response DOES
        propagate capability_id into required_capability_ids."""
        from ai.src.chat import AssistantChatService

        work_port = MagicMock()
        result_ref = MagicMock()
        result_ref.work_id = "work-hti-1"
        work_port.create_work.return_value = result_ref

        chat = AssistantChatService.__new__(AssistantChatService)
        chat._work_management = work_port
        chat._agent_id = None
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

        path_result = ExecutionPathResult(
            path=ExecutionPath.HUMAN_TEAM_INVESTIGATION,
            capability_id="cap-needs-review",
            reason="under review",
        )

        intent = MagicMock()
        intent.raw = {"text": "review this"}

        frame = MagicMock()
        frame.recognition_level = MagicMock()
        frame.recognition_level.value = "medium"

        chat._handle_human_team_investigation_response(path_result, intent, frame, "ses-y")

        work_port.create_work.assert_called_once()
        request = work_port.create_work.call_args[0][0]
        assert request.required_capability_ids == ["cap-needs-review"], (
            "Human team investigation DOES propagate capability_id — "
            "contrast with capability_development paths"
        )


# --------------------------------------------------------------------------- #
# C. Worker._develop_capability generates ID from work.id
# --------------------------------------------------------------------------- #


class TestWorkerCapabilityIdGeneration:
    """Verify Worker._develop_capability identity rules:
    - When develops_capability_id is absent, generate cap-{work.id}
    - When develops_capability_id is present, preserve it as the Capability ID
    """

    def test_develop_capability_uses_cap_dash_work_id_pattern_when_anonymous(self) -> None:
        """The generated capability_id follows the pattern cap-{work.id}
        when no develops_capability_id is set."""
        from workflow_runner.src.worker import Worker

        work = Work(
            id="w-dev-test",
            title="Develop capability: Test Cap",
            work_type="capability_development",
            accountable_role_id="default",
        )

        worker = Worker(output_dir="/tmp/test_worker_caps_46")
        result = worker._develop_capability(work, MagicMock())

        assert result["capability_id"] == "cap-w-dev-test"
        assert result["status"] == "completed"
        assert result["execution_mode"] == "capability_development"

    def test_develop_capability_preserves_develops_capability_id(self) -> None:
        """When develops_capability_id is set on the Work, the Capability
        uses that exact identity instead of generating a new one."""
        from workflow_runner.src.worker import Worker

        work = Work(
            id="w-dev-preserve",
            title="Develop capability: Preserve Me",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id="cap-identified-gap",
        )

        worker = Worker(output_dir="/tmp/test_worker_caps_46c")
        result = worker._develop_capability(work, MagicMock())

        assert result["capability_id"] == "cap-identified-gap"
        assert result["status"] == "completed"
        assert result["execution_mode"] == "capability_development"


# --------------------------------------------------------------------------- #
# D. CapabilityEventType DEVELOPMENT_STARTED / DEVELOPMENT_COMPLETED never emitted
# --------------------------------------------------------------------------- #


class TestCapabilityDevelopmentEventsNeverEmitted:
    """Verify that DEVELOPMENT_STARTED and DEVELOPMENT_COMPLETED are defined
    but never emitted by any production code."""

    def test_development_completed_only_in_tests(self) -> None:
        """DEVELOPMENT_COMPLETED appears only in test files, not in src."""
        org_src = os.path.join(os.path.dirname(__file__), "..", "src")
        found_in_src = False
        for dirpath, _, filenames in os.walk(org_src):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                with open(fpath) as f:
                    if "DEVELOPMENT_COMPLETED" in f.read():
                        found_in_src = True
        assert not found_in_src, (
            "DEVELOPMENT_COMPLETED should not appear in organisation src"
        )

    def test_development_started_never_emitted(self) -> None:
        """DEVELOPMENT_STARTED is defined but never referenced outside its enum
        definition in any production source."""
        org_src = os.path.join(os.path.dirname(__file__), "..", "src")
        workflow_src = WORKFLOW_RUNNER_SRC
        paperclip_src = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "organisation_paperclip", "src")
        )

        found_refs = []
        for src_dir in [org_src, workflow_src, paperclip_src]:
            if not os.path.isdir(src_dir):
                continue
            for dirpath, _, filenames in os.walk(src_dir):
                for fname in filenames:
                    if not fname.endswith(".py"):
                        continue
                    fpath = os.path.join(dirpath, fname)
                    with open(fpath) as f:
                        content = f.read()
                    if "DEVELOPMENT_STARTED" in content:
                        found_refs.append(fpath)

        assert not found_refs, (
            f"DEVELOPMENT_STARTED referenced in src (should be enum-only): {found_refs}"
        )

    def test_only_registered_event_is_emitted_on_registration(self) -> None:
        """When register_capability is called, only REGISTERED event type
        is emitted, not DEVELOPMENT_STARTED or DEVELOPMENT_COMPLETED."""
        events: list = []
        plane = _make_plane()
        plane.on_event(events.append)

        from capability import Capability, CapabilityKind

        cap = Capability(
            id="cap-emit-test",
            name="Emit Test",
            capability_kind=CapabilityKind.SKILL,
        )
        plane.register_capability(cap)

        capability_events = [e for e in events if isinstance(e, CapabilityEvent)]
        assert len(capability_events) == 1
        assert capability_events[0].event_type == CapabilityEventType.REGISTERED

    def test_operations_does_not_emit_development_events(self) -> None:
        """Operations._assess_capability_development does not emit
        DEVELOPMENT_COMPLETED capability events."""
        from workflow_runner.src.operations import Operations

        source = inspect.getsource(Operations._assess_capability_development)
        assert "DEVELOPMENT_COMPLETED" not in source
        assert "DEVELOPMENT_STARTED" not in source

    def test_worker_does_not_emit_development_events(self) -> None:
        """Worker._develop_capability does not emit CapabilityEvent."""
        from workflow_runner.src.worker import Worker

        source = inspect.getsource(Worker._develop_capability)
        assert "CapabilityEvent" not in source
        assert "DEVELOPMENT_COMPLETED" not in source
        assert "DEVELOPMENT_STARTED" not in source


# --------------------------------------------------------------------------- #
# E. record_work_learning excludes capability_development work
# --------------------------------------------------------------------------- #


class TestRecordWorkLearningExcludesCapabilityDevelopment:
    """Verify that record_work_learning only records project/initiative
    work, not capability_development work."""

    def test_record_work_learning_excludes_capability_development(self) -> None:
        """record_work_learning returns None for capability_development work."""
        from concepts import ConceptStore

        from outcome import assess_work_outcome, record_work_learning

        store = ConceptStore()
        work = Work(
            id="w-cap-dev",
            title="Develop capability: Gap",
            work_type="capability_development",
            accountable_role_id="default",
            acceptance_criteria=["Should work"],
        )
        result = {
            "status": "completed",
            "outputs": {"summary": "Should work"},
        }
        assessment = assess_work_outcome(work, result)
        concept = record_work_learning(work, assessment, store)
        assert concept is None, (
            "record_work_learning excludes capability_development — "
            "knowledge of the developed capability is not recorded as EIMS learning"
        )

    def test_record_work_learning_records_project_but_not_cap_dev(self) -> None:
        """Contrast: project work is recorded, capability_development is not."""
        from concepts import ConceptStore

        from outcome import assess_work_outcome, record_work_learning

        store = ConceptStore()

        project_work = Work(
            id="w-proj",
            title="Project work",
            work_type="project",
            accountable_role_id="default",
            acceptance_criteria=["Done"],
        )
        cap_work = Work(
            id="w-capdev",
            title="Develop capability",
            work_type="capability_development",
            accountable_role_id="default",
            acceptance_criteria=["Done"],
        )
        result = {"status": "completed", "outputs": {"summary": "Done"}}

        project_concept = record_work_learning(
            project_work, assess_work_outcome(project_work, result), store
        )
        cap_concept = record_work_learning(
            cap_work, assess_work_outcome(cap_work, result), store
        )

        assert project_concept is not None
        assert cap_concept is None


# --------------------------------------------------------------------------- #
# F. CapabilityRegistry is the sole owner of capability lifecycle
# --------------------------------------------------------------------------- #


class TestCapabilityRegistryLifecycleOwnership:
    """Verify that CapabilityRegistry is the lifecycle authority and
    OCP delegates to it."""

    def test_registry_has_register_and_promote(self) -> None:
        """CapabilityRegistry exposes register and promote methods."""
        from capabilities import CapabilityRegistry

        assert hasattr(CapabilityRegistry, "register")
        assert hasattr(CapabilityRegistry, "promote")
        assert hasattr(CapabilityRegistry, "get")

    def test_ocp_register_capability_emits_event_without_registry(self) -> None:
        """Without a registry, OCP stores locally and emits REGISTERED event."""
        events: list = []
        plane = _make_plane()
        plane.on_event(events.append)

        from capability import Capability, CapabilityKind

        cap = Capability(
            id="cap-ocp-fallback",
            name="Fallback",
            capability_kind=CapabilityKind.SKILL,
        )
        plane.register_capability(cap)

        registered = [
            e for e in events
            if isinstance(e, CapabilityEvent)
            and e.event_type == CapabilityEventType.REGISTERED
        ]
        assert len(registered) == 1
        assert registered[0].capability_id == "cap-ocp-fallback"


# --------------------------------------------------------------------------- #
# G. People/Capability boundary — OCP does not own capability lifecycle
# --------------------------------------------------------------------------- #


class TestPeopleCapabilityBoundary:
    """Verify that OCP does not define or own capability domain concepts."""

    def test_ocp_source_does_not_define_capability_class(self) -> None:
        """organisation_control_plane.py must not define a Capability class."""
        ocp_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "organisation_control_plane.py"
        )
        with open(ocp_path) as f:
            source = f.read()
        assert "class Capability" not in source

    def test_people_capability_defines_capability(self) -> None:
        """Capability model lives in people_capability/src/capability.py."""
        cap_path = os.path.join(PEOPLE_CAPABILITY_SRC, "capability.py")
        assert os.path.isfile(cap_path), "Capability model must exist in people_capability"

    def test_actor_is_from_people_capability(self) -> None:
        """Actor model lives in people_capability/src/actor.py."""
        actor_path = os.path.join(PEOPLE_CAPABILITY_SRC, "actor.py")
        assert os.path.isfile(actor_path), "Actor model must exist in people_capability"


# --------------------------------------------------------------------------- #
# H. Paperclip OCP select_execution_path behaviour
# --------------------------------------------------------------------------- #


class TestPaperclipSelectExecutionPath:
    """Verify Paperclip OCP select_execution_path behaviour."""

    def test_paperclip_falls_back_to_new_capability_without_capability_id(self) -> None:
        """Paperclip OCP returns NEW_CAPABILITY_REQUIRED with capability_id=None
        when nothing matches — it does not extract a specific gap ID."""
        try:
            from organisation_paperclip import PaperclipOrganisationControlPlane
        except ImportError:
            pytest.skip("Paperclip adapter not available")

        plane = PaperclipOrganisationControlPlane(base_url="http://localhost:3101")
        result = plane.select_execution_path(
            intent="unknown task",
            context={"required_capability_ids": []},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id is None


# --------------------------------------------------------------------------- #
# I. SolutionSelectionAdapter propagates capability_id
# --------------------------------------------------------------------------- #


class TestSolutionSelectionAdapterPropagation:
    """Verify the SolutionSelectionAdapter faithfully propagates
    capability_id from OCP's ExecutionPathResult to SolutionSelectionResult."""

    def test_adapter_propagates_capability_id(self) -> None:
        """The adapter passes capability_id through the port — verified by
        inspecting the source since the import path is broken in this
        environment."""
        adapter_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "adapters",
            "solution_selection_adapter.py",
        )
        with open(adapter_path) as f:
            source = f.read()

        # The adapter maps org_result.capability_id to the SolutionSelectionResult
        assert "capability_id=org_result.capability_id" in source, (
            "Adapter should propagate capability_id from ExecutionPathResult"
        )

    def test_adapter_propagates_none_capability_id(self) -> None:
        """When path_result.capability_id is None, the adapter propagates
        None (no filtering or default replacement)."""
        adapter_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "adapters",
            "solution_selection_adapter.py",
        )
        with open(adapter_path) as f:
            source = f.read()

        # The adapter does not replace None with a default
        assert "capability_id=org_result.capability_id" in source
        assert '"' in source  # sanity
        assert "capability_id=" not in source.replace(
            "capability_id=org_result.capability_id", ""
        )


# --------------------------------------------------------------------------- #
# J. Capability identity discontinuity: cap-{work.id} vs original capability_id
# --------------------------------------------------------------------------- #


class TestCapabilityIdentityContinuity:
    """Verify that capability identity is preserved through the development
    lifecycle when an identity was available, and generated when it was not."""

    def test_worker_preserves_develops_capability_id(self) -> None:
        """When Work.develops_capability_id is set, the Worker uses that
        exact identity for the Capability."""
        from workflow_runner.src.worker import Worker

        work = Work(
            id="w-continue-46",
            title="Develop capability: Something",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id="cap-original-id",
        )

        worker = Worker(output_dir="/tmp/test_worker_cont_46")
        result = worker._develop_capability(work, MagicMock())

        assert result["capability_id"] == "cap-original-id"
