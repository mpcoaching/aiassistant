"""
Architectural tests for Increment 51 — People/Capability capacity analysis and
response-selection boundaries.

Investigation-only increment. No production code is changed or added to satisfy
these tests. The tests assert architectural *contracts* that the existing
domain primitives already satisfy:

  A. People/Capability boundary (Role + Actor, capacity derivation, recursive)
  B. Required proficiency is genuinely absent (boundary identification)
  C. Capacity analysis is derivable from existing state (not an entity)
  D. Response selection is a People/Capability concern (not ExecutionPath expansion)
  E. Adjacency is contextual via tags/metadata (no graph abstraction)
  F. Increment 48 identity invariant remains intact
  G. Authority / automation boundary (no Decision entity, no autonomous staffing)

Contracts covered (20):

  1. People/Capability can be represented as Role + Actor.
  2. Capacity can be analysed/derived from existing state without a Capacity entity.
  3. People/Capability is itself recursively subject to capability analysis.
  4. No required_proficiency field exists on CapabilityAssignment.
  5. No required_proficiency_level field exists on Role.
  6. CapabilityProficiency has actual proficiency_level but no required threshold.
  7. Capacity inputs are representable: Actors + Assignments + Proficiency + Work + availability.
  8. CapabilityAvailability.available is an availability flag, not a capacity model.
  9. CapacityPressureSignal is a signal, not an entity.
  10. ExecutionPath has exactly four members — no expansion.
  11. select_execution_path does not distinguish proficiency/capacity gaps.
  12. Response selection is a People/Capability concern, not an ExecutionPath expansion.
  13. Capability has tags/metadata but no adjacency field.
  14. No CapabilityGraph / CapabilityRelationship / CapabilityEdge class exists.
  15. Adjacency is expressible contextually via tags/metadata, not a graph.
  16. Work.develops_capability_id is semantically distinct from required_capability_ids.
  17. Increment 48 identity chain is intact.
  18. No Decision entity exists in any package source tree.
  19. execute_organisational_change requires delegated authority (not autonomous).
  20. select_execution_path is not a staffing/hiring decision mechanism.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from actor import Actor, ActorType
from agent import Agent, AgentMarker, AgentStatus
from agent_store import InMemoryAgentStore
from capability import Capability, CapabilityKind, CapabilityStatus
from capability_assignment import CapabilityAssignment
from capability_proficiency import CapabilityProficiency, ProficiencyLevel

from execution_path import ExecutionPath, ExecutionPathResult
from organisation_control_plane import InMemoryOrganisationControlPlane
from role import (
    Authority,
    Role,
    Work,
    WorkStatus,
)

# --------------------------------------------------------------------------- #
# Shared bootstrap helpers (mirrors Increment 50)
# --------------------------------------------------------------------------- #

PEOPLE_FUNCTION_ROLE_ID = "people-capability-function"
CHIEF_OF_STAFF_ROLE_ID = "chief-of-staff"
ORG_CHANGE_AUTH_ID = "auth-organisational-change"

SRC_ROOT = Path(__file__).resolve().parents[2]  # packages/


def _bootstrap_organisation() -> tuple[InMemoryAgentStore, InMemoryOrganisationControlPlane, Agent, Actor]:
    """Build a minimal organisation where People/Capability is an ordinary Role
    whose Actor is backed by an Agent, and a Chief of Staff Role delegates the
    organisational-change authority to it."""
    store = InMemoryAgentStore()
    ocp = InMemoryOrganisationControlPlane()

    chief = Role(
        id=CHIEF_OF_STAFF_ROLE_ID,
        name="Chief of Staff",
        authority_ids=[],
        reports_to=None,
    )
    ocp.register_role(chief)

    pc_role = Role(
        id=PEOPLE_FUNCTION_ROLE_ID,
        name="People / Capability Function",
        description="Organisational capacity/capability function",
        authority_ids=[ORG_CHANGE_AUTH_ID],
        reports_to=CHIEF_OF_STAFF_ROLE_ID,
        required_capability_ids=["cap-analyse-capacity"],
    )
    ocp.register_role(pc_role)

    auth = Authority(
        id=ORG_CHANGE_AUTH_ID,
        name="Organisational change authority",
        scope="organisation",
        grantor_role_id=CHIEF_OF_STAFF_ROLE_ID,
        grantee_role_id=PEOPLE_FUNCTION_ROLE_ID,
    )
    ocp.register_authority(auth)
    ocp.delegate_authority(chief, pc_role, auth)

    pc_agent = Agent(
        id="agent-people-capability",
        name="People Capability Assistant",
        marker=AgentMarker.AI,
        status=AgentStatus.ACTIVE,
        fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
    )
    store.register_agent(pc_agent)
    pc_actor = store.get_actor(pc_agent.id)
    assert pc_actor is not None
    assert pc_actor.actor_type == ActorType.AGENT

    return store, ocp, pc_agent, pc_actor


def _make_work(
    work_id: str = "w-test",
    develops_capability_id: str | None = None,
    required_capability_ids: list[str] | None = None,
    work_type: str = "bau",
) -> Work:
    return Work(
        id=work_id,
        title="Test work",
        description="unit of organisational effort",
        work_type=work_type,
        accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
        required_capability_ids=required_capability_ids or [],
        develops_capability_id=develops_capability_id,
        status=WorkStatus.PENDING,
    )


def _derive_available_capacity(
    store: InMemoryAgentStore,
    required_capability_ids: list[str],
    in_progress_work_count: dict[str, int] | None = None,
) -> dict[str, int]:
    """Analytical capacity derivation — NOT an entity.

    available actor slots for a capability =
        (actors assigned that capability, ACTIVE proficiency assumed)
        minus (actors already saturated by in-progress work on that capability)

    This function exists only to prove the *inputs* are representable and
    combinable; it is the seed of a future capacity-analysis service, not a
    People/Capability domain entity.
    """
    in_progress_work_count = in_progress_work_count or {}
    available: dict[str, int] = {}
    for cap_id in required_capability_ids:
        assignments = store.get_assignments_for_capability(cap_id)
        actor_count = len({a.actor_id for a in assignments})
        saturated = in_progress_work_count.get(cap_id, 0)
        available[cap_id] = max(0, actor_count - saturated)
    return available


# --------------------------------------------------------------------------- #
# Source-scan helper
# --------------------------------------------------------------------------- #

_FORBIDDEN_CLASSES = frozenset({
    "Capacity", "Staffing", "Hiring", "Workforce", "Team", "Decision",
    "Supplier", "Vendor", "CapabilityGraph", "CapabilityRelationship",
    "CapabilityEdge",
})

_FORBIDDEN_FIELD_NAMES = frozenset({
    "required_proficiency", "required_proficiency_level", "min_proficiency",
    "capacity", "staffing", "team", "decision", "supplier", "vendor",
    "hire", "recruit",
})

# Packages to scan (organisation + people_capability own the relevant state)
_SCAN_PACKAGES = ["organisation", "people_capability", "capability_registry", "workflow_runner"]
# contracts lives at packages/contracts (no src/ subdirectory)
_CONTRACTS_DIR = SRC_ROOT / "contracts"


def _scan_src_for_classes(packages: list[str]) -> set[str]:
    """Scan package src directories and contracts for class definitions
    matching forbidden entity names."""
    found: set[str] = set()
    pattern = re.compile(r"class\s+(\w+)\b")

    for pkg in packages:
        pkg_src = SRC_ROOT / pkg / "src"
        if not pkg_src.exists():
            continue
        for path in pkg_src.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in pattern.finditer(text):
                name = match.group(1)
                if name in _FORBIDDEN_CLASSES:
                    found.add(name)

    if _CONTRACTS_DIR.exists():
        for path in _CONTRACTS_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in pattern.finditer(text):
                name = match.group(1)
                if name in _FORBIDDEN_CLASSES:
                    found.add(name)

    return found


# --------------------------------------------------------------------------- #
# A. People/Capability boundary (contracts 1–3)
# --------------------------------------------------------------------------- #


class TestPeopleCapabilityBoundary:
    """People/Capability can be represented as Role + Actor using existing
    primitives, analyse capacity without a Capacity entity, and is itself
    recursively subject to capability analysis."""

    def test_contract_1_people_capability_is_a_role_with_actor(self) -> None:
        """Contract 1: People/Capability can be represented as Role + Actor.

        The function is a Role whose execution identity is an Actor
        (ActorType.AGENT). No special executive entity is required."""
        _store, ocp, agent, actor = _bootstrap_organisation()

        role = ocp.get_role(PEOPLE_FUNCTION_ROLE_ID)
        assert role is not None
        assert role.name == "People / Capability Function"
        assert role.reports_to == CHIEF_OF_STAFF_ROLE_ID
        assert actor.actor_type == ActorType.AGENT
        assert actor.reference_id == agent.id

        # Chief of Staff is an ordinary Role, not a special executive entity
        chief = ocp.get_role(CHIEF_OF_STAFF_ROLE_ID)
        assert chief is not None
        assert chief.authority_ids == []

    def test_contract_2_capacity_analysable_without_capacity_entity(self) -> None:
        """Contract 2: Capacity can be analysed/derived from existing state
        without a Capacity entity.

        The derivation function consumes Actors, CapabilityAssignments, Work,
        and in-progress counts — all existing primitives. No Capacity class
        is involved."""
        store, _, _, _actor = _bootstrap_organisation()
        agent_a = Agent(
            id="agent-capacity-a",
            name="Analyst A",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent_a)
        actor_a = store.get_actor(agent_a.id)
        store.assign_capability(actor_a.id, "cap-analyse-capacity")

        # Actor B: assigned same capability, no in-progress work (available)
        agent_b = Agent(
            id="agent-capacity-b",
            name="Analyst B",
            marker=AgentMarker.AI,
            status=AgentStatus.ACTIVE,
            fulfilled_role_ids=[PEOPLE_FUNCTION_ROLE_ID],
        )
        store.register_agent(agent_b)
        actor_b = store.get_actor(agent_b.id)
        store.assign_capability(actor_b.id, "cap-analyse-capacity")

        in_progress = {"cap-analyse-capacity": 1}
        available = _derive_available_capacity(
            store, ["cap-analyse-capacity"], in_progress_work_count=in_progress
        )
        # 2 actors assigned, 1 saturated → 1 available
        assert available["cap-analyse-capacity"] == 1

    def test_contract_3_people_capability_itself_recursive(self) -> None:
        """Contract 3: People/Capability is itself recursively subject to
        capability analysis.

        The People/Capability Actor can be assessed for its own capability
        gaps via the same select_execution_path → NEW_CAPABILITY_REQUIRED
        → capability_development Work chain."""
        _store, ocp, _, actor = _bootstrap_organisation()

        gap_capability = "cap-people-can-analyse-gaps"
        result = ocp.select_execution_path(
            intent="people/capability function needs its own capability",
            context={"required_capability_ids": [gap_capability]},
        )
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert result.capability_id == gap_capability

        # The gap can lead to capability-development Work with develops_capability_id
        work = Work(
            id="w-self-develop-51",
            title=f"Develop capability: {gap_capability}",
            work_type="capability_development",
            accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
            develops_capability_id=result.capability_id,
        )
        assert work.develops_capability_id == gap_capability
        ocp.assign_work(work, actor)
        assert work.assignee_actor_id == actor.id


# --------------------------------------------------------------------------- #
# B. Required proficiency (contracts 4–6)
# --------------------------------------------------------------------------- #


class TestRequiredProficiencyBoundary:
    """Required proficiency is genuinely absent. Actual proficiency exists via
    CapabilityProficiency.proficiency_level, but there is no required threshold
    against which to compare it."""

    def test_contract_4_no_required_proficiency_on_capability_assignment(self) -> None:
        """Contract 4: No required_proficiency / required_proficiency_level /
        min_proficiency field exists on CapabilityAssignment."""
        assignment_fields = set(CapabilityAssignment.model_fields.keys())
        assert "required_proficiency" not in assignment_fields
        assert "required_proficiency_level" not in assignment_fields
        assert "min_proficiency" not in assignment_fields

    def test_contract_5_no_required_proficiency_on_role(self) -> None:
        """Contract 5: No required_proficiency / required_proficiency_level /
        min_proficiency field exists on Role."""
        role_fields = set(Role.model_fields.keys())
        assert "required_proficiency" not in role_fields
        assert "required_proficiency_level" not in role_fields
        assert "min_proficiency" not in role_fields

    def test_contract_6_actual_proficiency_has_no_required_threshold(self) -> None:
        """Contract 6: CapabilityProficiency has proficiency_level (actual),
        but no required threshold to compare against.

        Demonstrate that proficiency_level exists and is a real enum value,
        while the model has no 'required_proficiency_level' field."""
        proficiency_fields = set(CapabilityProficiency.model_fields.keys())
        assert "proficiency_level" in proficiency_fields
        assert "required_proficiency_level" not in proficiency_fields

        # Actual proficiency is recorded as a real value
        _store, _, _, actor = _bootstrap_organisation()
        proficiency = CapabilityProficiency(
            id="prof-51-1",
            capability_id="cap-analyse-capacity",
            actor_id=actor.id,
            proficiency_level=ProficiencyLevel.PROFICIENT,
        )
        assert proficiency.proficiency_level == ProficiencyLevel.PROFICIENT
        assert isinstance(proficiency.proficiency_level, ProficiencyLevel)


# --------------------------------------------------------------------------- #
# C. Capacity analysis (contracts 7–9)
# --------------------------------------------------------------------------- #


class TestCapacityAnalysisDerived:
    """Capacity is derivable from existing organisational state. CapabilityAvailability
    is an availability flag, not a capacity model. CapacityPressureSignal is a
    signal, not an entity."""

    def test_contract_7_capacity_inputs_are_representable(self) -> None:
        """Contract 7: Capacity inputs are representable from existing state:
        Actors, CapabilityAssignments, CapabilityProficiency, Work, availability.
        All of these are individually expressible without a Capacity entity."""
        store, ocp, _, actor = _bootstrap_organisation()

        # Actor with capability assignment
        store.assign_capability(actor.id, "cap-analyse-capacity")
        assert store.actor_has_capability(actor.id, "cap-analyse-capacity")

        # Proficiency record
        proficiency = CapabilityProficiency(
            id="prof-51-2",
            capability_id="cap-analyse-capacity",
            actor_id=actor.id,
            proficiency_level=ProficiencyLevel.COMPETENT,
        )
        assert proficiency.proficiency_level is ProficiencyLevel.COMPETENT

        # Work requiring the capability
        work = _make_work(
            work_id="w-cap-input-51",
            required_capability_ids=["cap-analyse-capacity"],
        )
        ocp.assign_work(work, actor)

        # Assignments for capability exist
        assignments = store.get_assignments_for_capability("cap-analyse-capacity")
        assert len(assignments) == 1

        # Work is tracked
        assert ocp.get_work("w-cap-input-51") is not None

    def test_contract_8_capability_availability_is_not_capacity_model(self) -> None:
        """Contract 8: CapabilityAvailability.available is an operational
        availability flag (can this capability be invoked right now?), NOT a
        capacity model (do we have enough actors/proficiency)."""
        from contracts.enterprise_capability_query import CapabilityAvailability

        availability = CapabilityAvailability(
            capability_id="cap-analyse-capacity",
            available=True,
            eta_seconds=5,
            assignee=None,
            reason="Capability is available",
        )
        assert availability.available is True
        assert "capacity" not in set(CapabilityAvailability.model_fields.keys())
        assert "required_capacity" not in set(CapabilityAvailability.model_fields.keys())

    def test_contract_9_capacity_pressure_is_a_signal_not_an_entity(self) -> None:
        """Contract 9: CapacityPressureSignal is a derived signal, not an
        organisational entity. It is emitted by detect_capacity_pressure,
        not stored as a Capacity/Staffing entity."""
        _, ocp, _, _ = _bootstrap_organisation()
        work = _make_work(
            work_id="w-pressure-1",
            required_capability_ids=["cap-analyse-capacity"],
        )
        ocp.assign_work(work, Role(id=PEOPLE_FUNCTION_ROLE_ID, name="People"))

        work2 = _make_work(
            work_id="w-pressure-2",
            required_capability_ids=["cap-analyse-capacity"],
        )
        ocp.assign_work(work2, Role(id=PEOPLE_FUNCTION_ROLE_ID, name="People"))

        pressure = ocp.detect_capacity_pressure("cap-analyse-capacity")
        assert pressure is not None
        assert pressure.signal_type == "capacity.pressure.detected"
        assert pressure.capability_id == "cap-analyse-capacity"

        # The signal is NOT a class named Capacity or Staffing
        assert type(pressure).__name__ == "CapacityPressureSignal"


# --------------------------------------------------------------------------- #
# D. Response selection (contracts 10–12)
# --------------------------------------------------------------------------- #


class TestResponseSelectionBoundary:
    """Response selection is a People/Capability concern. ExecutionPath must
    not be expanded into a general staffing/response decision mechanism."""

    def test_contract_10_execution_path_has_exactly_four_members(self) -> None:
        """Contract 10: ExecutionPath has exactly four members —
        EXISTING_WORKFLOW, CAPABILITY_PATH, NEW_CAPABILITY_REQUIRED,
        HUMAN_TEAM_INVESTIGATION. No OUTSOURCE, STAFF, HIRE, etc."""
        members = list(ExecutionPath)
        assert len(members) == 4
        member_values = {m.value for m in members}
        assert member_values == {
            "existing_workflow",
            "capability_path",
            "new_capability_required",
            "human_team_investigation",
        }
        for forbidden_attr in ("outsource", "staff", "hire", "reassign", "develop"):
            assert not hasattr(ExecutionPath, forbidden_attr.upper()), (
                f"ExecutionPath unexpectedly has {forbidden_attr.upper()}"
            )

    def test_contract_11_select_execution_path_does_not_distinguish_gaps(self) -> None:
        """Contract 11: select_execution_path does NOT distinguish between:
        - insufficient proficiency
        - insufficient capacity
        - unknown capability
        - insufficient understanding

        It only answers solution-path questions: workflow exists →
        EXISTING_WORKFLOW; registered + available → CAPABILITY_PATH; unavailable
        → HUMAN_TEAM_INVESTIGATION; not registered → NEW_CAPABILITY_REQUIRED."""
        ocp_source = inspect.getsource(InMemoryOrganisationControlPlane.select_execution_path)

        # The method does not inspect proficiency levels or capacity analysis
        assert "proficiency_level" not in ocp_source
        assert "required_proficiency" not in ocp_source
        assert "insufficient" not in ocp_source.lower()
        assert "capacity_analysis" not in ocp_source
        assert "staffing" not in ocp_source.lower()

        # It only contains the four execution paths
        assert "EXISTING_WORKFLOW" in ocp_source
        assert "CAPABILITY_PATH" in ocp_source
        assert "NEW_CAPABILITY_REQUIRED" in ocp_source
        assert "HUMAN_TEAM_INVESTIGATION" in ocp_source

    def test_contract_12_response_selection_is_people_capability_concern(self) -> None:
        """Contract 12: Response selection ("what should we hire/develop/reassign?")
        is a People/Capability analysis concern, not an ExecutionPath expansion.

        ExecutionPath answers "what broad execution path is available?";
        People/Capability analysis answers "what capability/capacity gap exists
        and what classes of response could close it?". The conceptual response set
        is covered by existing primitives without new ExecutionPath values."""
        _store, _ocp, _, _actor = _bootstrap_organisation()

        # The conceptual response set is expressible through existing primitives:
        # - Train/develop existing Actor → capability_development Work → Worker → registry
        # - Reassign → CapabilityAssignment status (SUSPENDED/ACTIVE)
        # - New Agent → store.register_agent
        # - New Person → store.register_person
        # - Workflow → EXISTING_WORKFLOW
        # - Tool → CapabilityKind.TOOL
        # - Human investigation → HUMAN_TEAM_INVESTIGATION
        # - Outsource → explicitly unsupported (no Supplier/Vendor model)

        # Verify no OUTSOURCE ExecutionPath member
        assert not hasattr(ExecutionPath, "OUTSOURCE")
        assert "outsource" not in [p.value for p in ExecutionPath]


# --------------------------------------------------------------------------- #
# E. Adjacency (contracts 13–15)
# --------------------------------------------------------------------------- #


class TestAdjacencyBoundary:
    """Adjacent capability is NOT first-class. Capability has tags/metadata
    but no explicit adjacency field. No CapabilityGraph/Relationship/Edge exists."""

    def test_contract_13_capability_has_no_adjacency_field(self) -> None:
        """Contract 13: Capability has tags and metadata but no adjacency field."""
        cap_fields = set(Capability.model_fields.keys())
        assert "tags" in cap_fields
        assert "metadata" in cap_fields
        assert "adjacency" not in cap_fields
        assert "adjacent_capabilities" not in cap_fields
        assert "capability_graph" not in cap_fields
        assert "related_capabilities" not in cap_fields

        cap = Capability(
            id="cap-adj-test",
            name="Adjacency Test",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.ACTIVE,
            tags=["adj:cap-a", "adj:cap-b"],
            metadata={"adjacency_context": "related to cap-a via shared interface"},
        )
        assert cap.tags == ["adj:cap-a", "adj:cap-b"]

    def test_contract_14_no_graph_abstraction_exists(self) -> None:
        """Contract 14: No CapabilityGraph / CapabilityRelationship /
        CapabilityEdge class exists in any package source tree."""
        found = _scan_src_for_classes(_SCAN_PACKAGES)
        assert "CapabilityGraph" not in found
        assert "CapabilityRelationship" not in found
        assert "CapabilityEdge" not in found

    def test_contract_15_adjacency_via_tags_metadata_only(self) -> None:
        """Contract 15: Adjacency is useful reasoning context but is not
        currently a first-class organisational relationship. It can be carried
        contextually via tags/metadata without requiring graph semantics."""
        cap = Capability(
            id="cap-adj-contextual",
            name="Contextual Adjacency",
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.ACTIVE,
            tags=["uses:cap-dependency", "depends-on:cap-foundation"],
            metadata={
                "adjacency_context": "This capability builds on cap-foundation",
                "related_capability_ids": ["cap-foundation"],
            },
        )
        assert "adjacency" not in set(Capability.model_fields.keys())
        assert "uses:cap-dependency" in cap.tags
        assert "related_capability_ids" in cap.metadata
        assert cap.metadata["related_capability_ids"] == ["cap-foundation"]


# --------------------------------------------------------------------------- #
# F. Existing Increment 48 identity (contracts 16–17)
# --------------------------------------------------------------------------- #


class TestIncrement48IdentityInvariant:
    """The Increment 48 identity chain remains intact:

      ExecutionPathResult.capability_id
          → Work.develops_capability_id
          → Capability.id
          → CapabilityRegistry
          → assessment
          → ACTIVE

    required_capability_ids ≠ develops_capability_id.
    Increment 51 must not weaken this invariant.
    """

    def test_contract_16_develops_distinct_from_required(self) -> None:
        """Contract 16: Work.develops_capability_id is semantically distinct from
        required_capability_ids. The capability being developed is NOT placed in
        required_capability_ids."""
        work_fields = set(Work.model_fields.keys())
        assert "required_capability_ids" in work_fields
        assert "develops_capability_id" in work_fields

        work = Work(
            id="w-sep-51",
            title="Develop capability: Separation",
            work_type="capability_development",
            accountable_role_id=PEOPLE_FUNCTION_ROLE_ID,
            required_capability_ids=["cap-required-to-execute"],
            develops_capability_id="cap-being-developed",
        )
        assert work.required_capability_ids == ["cap-required-to-execute"]
        assert work.develops_capability_id == "cap-being-developed"
        assert "cap-being-developed" not in work.required_capability_ids

    def test_contract_17_increment48_chain_intact(self, tmp_path) -> None:
        """Contract 17: The full Increment 48 identity chain is intact end-to-end."""
        from capabilities import CapabilityRegistry
        from concept_store_adapter import ConceptStoreCapabilityRepository
        from concepts import ConceptStore
        from workflow_runner.src.worker import Worker

        from outcome import assess_capability_development

        _store, ocp, _, actor = _bootstrap_organisation()

        concept_store = ConceptStore(data_dir=str(tmp_path / "concepts_51"))
        repo = ConceptStoreCapabilityRepository(concept_store)
        registry = CapabilityRegistry(repo)
        ocp._capability_registry = registry
        ocp.register_role(Role(id="default", name="Default"))

        capability_id = "cap-chain-51"

        # Hop 1: capability_id preserved on NEW_CAPABILITY_REQUIRED
        path_result = ocp.select_execution_path(
            intent="need a capability an actor can develop",
            context={"required_capability_ids": [capability_id]},
        )
        assert path_result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
        assert path_result.capability_id == capability_id

        # Hop 2: Work.develops_capability_id carries the identity
        work = Work(
            id="w-develop-51",
            title="Develop capability: Chain 51",
            work_type="capability_development",
            accountable_role_id="default",
            develops_capability_id=path_result.capability_id,
            status=WorkStatus.READY,
            assignee_actor_id=actor.id,
        )
        assert work.develops_capability_id == capability_id

        # Hop 3 + 4: Worker → CapabilityRegistry
        worker = Worker(
            output_dir=str(tmp_path / "worker_out_51"),
            capability_registry=registry,
        )
        result = worker._develop_capability(work, ocp)
        assert result["capability_id"] == capability_id

        cap = registry.get(capability_id)
        assert cap is not None
        assert cap.id == capability_id
        assert cap.status == CapabilityStatus.DRAFT

        # Hop: assessment → ACTIVE
        assessment = assess_capability_development(work, cap, result)
        assert assessment["passed"] is True
        registry.promote(capability_id)
        assert registry.get(capability_id).status == CapabilityStatus.ACTIVE


# --------------------------------------------------------------------------- #
# G. Authority / automation boundary (contracts 18–20)
# --------------------------------------------------------------------------- #


class TestAuthorityAutomationBoundary:
    """No autonomous staffing/hiring. No Decision entity. Analysis is
    separated from organisational action."""

    def test_contract_18_no_decision_entity_exists(self) -> None:
        """Contract 18: No Decision entity exists in any package source tree."""
        found = _scan_src_for_classes(_SCAN_PACKAGES)
        assert "Decision" not in found

    def test_contract_19_no_autonomous_staffing_without_authority(self) -> None:
        """Contract 19: execute_organisational_change requires delegated
        authority — it is not an autonomous staffing/hiring action."""
        _store, ocp, _, actor = _bootstrap_organisation()

        # Without delegated authority, change is blocked
        role_no_auth = Role(
            id="role-no-auth-51",
            name="No Authority",
            authority_ids=[ORG_CHANGE_AUTH_ID],  # listed but never delegated
        )
        ocp.register_role(role_no_auth)
        work = Work(
            id="w-no-auth-51",
            title="Unauthorised change",
            work_type="bau",
            accountable_role_id="role-no-auth-51",
            required_capability_ids=["cap-x"],
        )
        result = ocp.execute_organisational_change(work, actor)
        assert result["status"] == "unauthorised"
        assert result["authority_checked"] is True

        # With delegated authority, change proceeds
        work2 = _make_work(
            work_id="w-with-auth-51",
            required_capability_ids=["cap-y"],
        )
        result2 = ocp.execute_organisational_change(work2, actor)
        assert result2["status"] == "executed"

    def test_contract_20_select_execution_path_is_not_staffing_decision(self) -> None:
        """Contract 20: select_execution_path is NOT a staffing/hiring decision
        mechanism. It only produces ExecutionPathResult — it does not provision
        actors, assign capabilities, or emit hiring signals."""
        ocp_source = inspect.getsource(InMemoryOrganisationControlPlane.select_execution_path)

        # The method does not call register_agent, register_person, assign_capability,
        # or any staffing/hiring related operation
        assert "register_agent" not in ocp_source
        assert "register_person" not in ocp_source
        assert "assign_capability" not in ocp_source
        assert "hiring" not in ocp_source.lower()
        assert "staff" not in ocp_source.lower()
        assert "hire" not in ocp_source.lower()

        # It only returns an ExecutionPathResult (a data object)
        _, ocp, _, _ = _bootstrap_organisation()
        result = ocp.select_execution_path(
            intent="test task",
            context={"required_capability_ids": ["cap-missing-51"]},
        )
        assert isinstance(result, ExecutionPathResult)
        assert result.path == ExecutionPath.NEW_CAPABILITY_REQUIRED
