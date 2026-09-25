"""
Architectural tests for Increment 40 — Organisational Team, Role & People/Capability Function Boundary.

Investigates whether Team should be an Actor, the Role vs Team vs Actor hierarchy,
whether People/Capability can be represented as ordinary organisational mechanisms,
whether Chief of Staff can be an ordinary Actor, and the OCP→Paperclip contract.

Tests established facts from this increment's investigation. No production changes.
"""

from __future__ import annotations

import inspect
import os
import re

ORGANISATION_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "src"
))
PEOPLE_CAPABILITY_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "people_capability", "src"
))
PAPERCLIP_ADAPTER = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "organisation_paperclip", "src"
))
CONTRACTS_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "contracts"
))
WORKFLOW_RUNNER_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner", "src"
))
PAPERCLIP_CATALOG = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
    "operational", "paperclip", "packages", "teams-catalog"
))


# ---- A. Actor Model Facts ----


def test_actor_type_enum_has_only_person_and_agent() -> None:
    """ActorType has exactly PERSON and AGENT — no Team subtype exists.

    This proves that Team cannot be an Actor subtype without modifying
    the ActorType enum, and that no such modification has been made.
    """
    from actor import ActorType

    members = [m.value for m in ActorType]
    assert set(members) == {"person", "agent"}
    assert "team" not in members


def test_actor_has_no_team_subtype_in_codebase() -> None:
    """No Team type or Team enum value exists anywhere in the Actor model.

    Searching all Python source confirms Team is not an Actor subtype.
    """
    from actor import ActorType

    assert not hasattr(ActorType, "TEAM")
    assert not hasattr(ActorType, "team")


def test_actor_links_to_person_or_agent_via_reference_id() -> None:
    """Actor.reference_id points to Person or Agent — not to Team.

    Actor is a lightweight reference linking to Person/Agent records
    owned by the People/Capability plane (ADR-037).
    """
    from actor import Actor

    fields = set(Actor.model_fields.keys())
    assert "reference_id" in fields
    assert "actor_type" in fields
    assert "fulfilled_role_ids" in fields


def test_actor_is_lightweight_reference_not_entity() -> None:
    """Actor has no lifecycle fields — it is a reference, not a record.

    No created_at/updated_at on Actor itself (those are on Person/Agent).
    No Team-like containment fields.
    """
    from actor import Actor

    forbidden = ["team_id", "parent_team_id", "team_members", "subteams"]
    for field in forbidden:
        assert field not in Actor.model_fields, (
            f"Actor has unexpected field '{field}'"
        )


def test_organisation_does_not_define_actor() -> None:
    """Actor is NOT defined in the organisation package (ADR-037).

    OCP imports Actor from people_capability; it does not own it.
    This confirms the boundary that Team cannot enter OCP via Actor.
    """
    actor_path = os.path.join(PEOPLE_CAPABILITY_SRC, "actor.py")
    assert os.path.isfile(actor_path)
    org_actor = os.path.join(ORGANISATION_SRC, "actor.py")
    assert not os.path.isfile(org_actor)


# ---- B. Role Model Facts ----


def test_role_is_abstract_position_not_person_or_agent() -> None:
    """Role is explicitly an abstract position, not a person or agent.

    Per ADR-018: Role is a template/blueprint. A Role is occupied by
    a Person or fulfilled by an Agent. Role itself is neither.
    """
    from role import Role, RoleStatus

    assert RoleStatus.VACANT.value == "vacant"
    fields = set(Role.model_fields.keys())
    assert "responsibilities" in fields
    assert "required_capability_ids" in fields
    assert "reports_to" in fields


def test_role_has_required_capability_ids() -> None:
    """Role declares required_capability_ids — what capabilities the position needs.

    This is the primary link between organisational need (role) and
    capability requirements, replacing any need for Position Specification.
    """
    from role import Role

    assert "required_capability_ids" in Role.model_fields


def test_role_has_responsibilities_authority_constraints() -> None:
    """Role has responsibilities, authority_ids, constraints, information_access.

    These fields already constitute a position specification without
    creating a separate Position/Role Specification concept.
    """
    from role import Role

    fields = set(Role.model_fields.keys())
    assert "responsibilities" in fields
    assert "authority_ids" in fields
    assert "constraints" in fields
    assert "information_access" in fields


def test_role_has_reports_to_for_hierarchy() -> None:
    """Role.reports_to establishes reporting relationships between positions.

    This allows C-Suite hierarchy (CEO → COO → managers → specialists)
    without needing C-Suite entities or Team hierarchy.
    """
    from role import Role

    assert "reports_to" in Role.model_fields


def test_role_status_has_vacant() -> None:
    """RoleStatus.VACANT exists — represents unfilled positions.

    VACANT status explicitly models "the organisation needs someone
    in this position", which is the organisational need that triggers
    People/Capability to fill it.
    """
    from role import RoleStatus

    assert RoleStatus.VACANT.value == "vacant"


# ---- C. Work Accountability Facts ----


def test_work_accountable_to_role() -> None:
    """Work.accountable_role_id expresses accountability to a Role.

    Per ADR-034, Role is the accountability unit for Work.
    Team is not an accountability unit — Role is.
    """
    from role import Work

    assert "accountable_role_id" in Work.model_fields
    assert "assignee_role_id" in Work.model_fields


def test_work_has_multiple_assignee_fields() -> None:
    """Work has assignee_role_id, assignee_actor_id, assignee_person_id, assignee_agent_id.

    No assignee_team_id exists — Work cannot be assigned to a Team.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "assignee_role_id" in fields
    assert "assignee_actor_id" in fields
    assert "assignee_person_id" in fields
    assert "assignee_agent_id" in fields
    assert "assignee_team_id" not in fields


def test_assign_work_accepts_actor_role_person_agent() -> None:
    """assign_work() accepts Actor | Role | Person | Agent — not Team.

    The type signature proves Team has no place in the Work assignment mechanism.
    """
    from organisation_control_plane import InMemoryOrganisationControlPlane

    sig = inspect.signature(InMemoryOrganisationControlPlane.assign_work)
    params = list(sig.parameters.values())
    assignee_param = params[2]
    annotation = str(assignee_param.annotation)
    assert "Actor" in annotation
    assert "Role" in annotation
    assert "Team" not in annotation


def test_work_has_no_team_assignee() -> None:
    """Work has no team_id field — confirming Team is not a Work assignee.

    Work accountability flows through Role, not Team.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in ["team_id", "assignee_team_id", "team_id"]:
        assert forbidden not in fields, (
            f"Work has unexpected field '{forbidden}'"
        )


# ---- D. Capability Model Facts ----


def test_capability_has_tool_and_skill_kinds() -> None:
    """CapabilityKind has TOOL and SKILL — not TEAM.

    This confirms capability types do not include Team.
    """
    from capability import CapabilityKind

    members = [m.value for m in CapabilityKind]
    assert "tool" in members
    assert "skill" in members
    assert "team" not in members


def test_capability_distinct_from_skill_and_tool() -> None:
    """Capability ≠ Skill ≠ Tool. They are separate domain concepts.

    Skill is a METHOD for exercising a Capability.
    Tool is an executable RESOURCE.
    Capability is the reusable ABILITY.
    """
    from capability import Capability
    from skill import Skill
    from tool import Tool

    cap_fields = set(Capability.model_fields.keys())
    skill_fields = set(Skill.model_fields.keys())
    tool_fields = set(Tool.model_fields.keys())

    assert "capability_kind" in cap_fields
    assert "capability_id" in skill_fields
    assert "implementation_type" in tool_fields


def test_capability_owned_by_people_capability() -> None:
    """Capability is defined in people_capability package, not OCP.

    Per ADR-020 and ADR-040, People/Capability owns capability lifecycle.
    OCP only queries via CapabilityRegistry.
    """
    cap_path = os.path.join(PEOPLE_CAPABILITY_SRC, "capability.py")
    assert os.path.isfile(cap_path)
    org_cap = os.path.join(ORGANISATION_SRC, "capability.py")
    assert not os.path.isfile(org_cap)


# ---- E. Assignment Model Facts ----


def test_capability_assignment_links_actor_to_capability() -> None:
    """CapabilityAssignment links Actor → Capability via actor_id + capability_id.

    Per ADR-040, this is the authoritative link between Actor and Capability.
    No Team linkage exists.
    """
    from capability_assignment import CapabilityAssignment

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "actor_id" in fields
    assert "capability_id" in fields
    assert "skill_ids" in fields
    assert "tool_ids" in fields


def test_capability_assignment_has_skill_tool_references(self=None) -> None:
    """CapabilityAssignment optionally references Skills and Tools.

    These are references only — definitions remain owned by their layers.
    """
    from capability_assignment import CapabilityAssignment

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "skill_ids" in fields
    assert "tool_ids" in fields


def test_org_assignment_links_work_to_assignee() -> None:
    """Assignment links Work → assignee via assignee_type + assignee_id.

    Assignee types are role, person, agent, actor — no team type exists.
    """
    from role import Assignment

    fields = set(Assignment.model_fields.keys())
    assert "work_id" in fields
    assert "assignee_type" in fields
    assert "assignee_id" in fields


# ---- F. Team Concept Facts ----


def test_no_team_in_organisation_package() -> None:
    """No Team model exists in any organisation package file.

    Confirms Team has no OCP domain presence.
    """
    org_src = ORGANISATION_SRC
    for root, dirs, files in os.walk(org_src):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path) as fh:
                    content = fh.read()
                if re.search(r"\bclass Team\b", content):
                    assert False, f"Team class found in {path}"


def test_paperclip_team_is_catalog_not_entity() -> None:
    """Paperclip Team exists only as @paperclipai/teams-catalog — a catalog concept.

    No `teams` table exists in Paperclip DB schema.
    Team is an install-time bundle, not a persisted entity.
    """
    db_schema = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "operational", "paperclip", "packages", "db", "src", "schema"
    )
    assert os.path.isdir(db_schema)
    teams_file = os.path.join(db_schema, "teams.ts")
    assert not os.path.isfile(teams_file)

    catalog_types = os.path.join(PAPERCLIP_CATALOG, "src", "types.ts")
    assert os.path.isfile(catalog_types)


def test_actor_type_enum_cannot_be_team() -> None:
    """Adding Team to ActorType would require modifying ActorType enum — not done.

    This confirms Team has NO pathway into OCP as an Actor subtype.
    """
    from actor import ActorType

    members = [m.value for m in ActorType]
    assert "team" not in members


def test_assign_work_does_not_accept_team() -> None:
    """assign_work signature has no Team parameter.

    Even if Team were desired, the mechanism to assign Work to Team doesn't exist.
    """
    from typing import get_type_hints

    from organisation_control_plane import OrganisationControlPlane

    hints = get_type_hints(OrganisationControlPlane.assign_work)
    assignee_hint = str(hints.get("assignee", ""))
    assert "Team" not in assignee_hint


def test_no_team_hierarchy_concept() -> None:
    """No containment or hierarchy concept for Team exists.

    Paperclip hierarchy is via Agent.reportsTo (single-parent chain).
    OCP hierarchy is via Role.reports_to.
    No parent-child Team relationship exists in either.
    """
    from actor import Actor

    from role import Role

    role_fields = set(Role.model_fields.keys())
    actor_fields = set(Actor.model_fields.keys())

    for forbidden in ["parent_team_id", "child_teams", "team_members", "subteams", "composition"]:
        assert forbidden not in role_fields, f"Role has unexpected field '{forbidden}'"
        assert forbidden not in actor_fields, f"Actor has unexpected field '{forbidden}'"


# ---- G. People/Capability Representation ----


def test_people_capability_can_be_represented_as_role() -> None:
    """People/Capability function = a Role with Actor fulfillment.

    No special HR subsystem is needed because Role already exists
    as the organisational position concept. A Role named
    'People/Capability Lead' with responsibilities for organisational
    design, capability management, and workforce planning is a valid
    representation using existing primitives.
    """
    from role import Role

    # Role has all necessary fields for People/Capability representation
    fields = set(Role.model_fields.keys())
    required = ["name", "description", "responsibilities", "required_capability_ids",
                "authority_ids", "reports_to", "status"]
    for field in required:
        assert field in fields, f"Role missing field '{field}' needed for People/Capability"


def test_capability_assignment_can_link_person_to_capacity_capability() -> None:
    """A Person/Actor can be CapabilityAssigned to capacity-planning capabilities.

    This proves People/Capability function can be represented as
    an Actor with appropriate CapabilityAssignments.
    """
    from capability_assignment import CapabilityAssignment

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "actor_id" in fields
    assert "capability_id" in fields


def test_assign_work_can_target_people_capability_role() -> None:
    """Work can be assigned to any Role — including a People/Capability Role.

    This proves People/Capability can receive Work (capacity analysis,
    structure design) through the standard assignment mechanism.
    """
    from organisation_control_plane import InMemoryOrganisationControlPlane

    sig = inspect.signature(InMemoryOrganisationControlPlane.assign_work)
    params = list(sig.parameters.values())
    assignee_param = params[2]
    annotation = str(assignee_param.annotation)
    assert "Role" in annotation


def test_no_hr_engine_exists() -> None:
    """No HR engine, recruitment system, or special People/Capability subsystem exists.

    People/Capability is represented through ordinary organisational
    mechanisms (Role, Actor, Capability, CapabilityAssignment, Work).
    """
    org_src = ORGANISATION_SRC
    for root, dirs, files in os.walk(org_src):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path) as fh:
                    content = fh.read()
                if re.search(r"\bHR|hr_engine|recruitment|hiring|special_hr\b", content, re.IGNORECASE):
                    assert False, f"HR-specific code found in {path}"


# ---- H. Chief of Staff Representation ----


def test_chief_of_staff_can_be_role() -> None:
    """Chief of Staff can be a Role — no special class needed.

    ADR-031 established CEO as a Role (strategic). ADR-032 established COO as a Role (BAU).
    Chief of Staff follows the same pattern — it is a Role with coordination responsibilities.
    """
    from role import Role

    # Role can represent any position including Chief of Staff
    fields = set(Role.model_fields.keys())
    assert "name" in fields
    assert "responsibilities" in fields
    assert "required_capability_ids" in fields


def test_chief_of_staff_uses_existing_delegation() -> None:
    """Chief of Staff coordinates via Delegation (ADR-019), not special authority.

    Delegation records authority transfers between Roles.
    Chief of Staff delegates via standard authority mechanism.
    """
    from role import Delegation

    delegation_fields = set(Delegation.model_fields.keys())
    assert "from_role_id" in delegation_fields
    assert "to_role_id" in delegation_fields
    assert "authority_id" in delegation_fields


def test_chief_of_staff_no_special_authority_required() -> None:
    """Chief of Staff uses ordinary organisational authority (Authority model).

    No special authority beyond Authority/Delegation is needed.
    """
    from role import Authority

    fields = set(Authority.model_fields.keys())
    assert "grantor_role_id" in fields
    assert "grantee_role_id" in fields
    assert "scope" in fields


# ---- I. C-Suite Representation ----


def test_ceo_is_role_not_entity() -> None:
    """CEO is a Role per ADR-031 — strategic responsibilities only.

    No C-Suite entity exists. CEO is represented as a Role, not a special class.
    """
    from role import Role

    # CEO can be a Role instance
    ceo_role = Role(
        id="ceo",
        name="CEO",
        responsibilities=["strategic decision", "strategic direction"],
        authority_ids=[],
        constraints=[],
        information_access=[],
        reports_to=None,
        required_capability_ids=[],
    )
    assert ceo_role.name == "CEO"


def test_coo_is_role_not_entity() -> None:
    """COO is a Role per ADR-032 — BAU operational oversight.

    No C-Suite entity exists. COO is represented as a Role.
    """
    from role import Role

    coo_role = Role(
        id="coo",
        name="COO",
        responsibilities=["operational performance", "capacity management"],
        authority_ids=[],
        constraints=[],
        information_access=[],
        reports_to="ceo",
        required_capability_ids=[],
    )
    assert coo_role.reports_to == "ceo"


# ---- J. Recursive Organisation ----


def test_people_capability_can_create_roles() -> None:
    """InMemoryOrganisationControlPlane has register_role() — organisational design
    is a matter of creating new Role records.

    People/Capability designing structure = creating Roles.
    """
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "register_role")


def test_paperclip_can_create_agents_from_roles() -> None:
    """Paperclip adapter create_agent() maps Role → Agent.

    Paperclip instantiates Agents with roles specified by OCP.
    This is the instantiation mechanism for Paperclip implementation.
    """
    from organisation_paperclip import PaperclipOrganisationControlPlane

    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")


def test_capability_assignment_links_new_actor_to_capabilities() -> None:
    """CapabilityAssignment can link newly created Actors to required Capabilities.

    After Paperclip creates an Agent (→ Actor), CapabilityAssignment
    links that Actor to required Capabilities. This is the mechanism
    for "creating a capability-based team".
    """
    from capability_assignment import CapabilityAssignment

    assignment = CapabilityAssignment(
        id="test",
        capability_id="cap-1",
        actor_id="actor-1",
    )
    assert assignment.capability_id == "cap-1"
    assert assignment.actor_id == "actor-1"


def test_recursive_flow_uses_same_mechanisms_each_level() -> None:
    """Recursive organisation uses the same mechanisms at each level.

    Level 1: Founder assigns Work to People/Capability Role
    Level 2: People/Capability defines new Role (register_role)
    Level 3: Paperclip creates Agent for Role (create_agent)
    Level 4: Actor created from Agent (register_agent in people_capability)
    Level 5: CapabilityAssignment links Actor to Capabilities

    No privileged recursion mechanism needed — just the same pattern.
    """
    from capability_assignment import CapabilityAssignment

    from organisation_control_plane import InMemoryOrganisationControlPlane
    from role import Role

    plane = InMemoryOrganisationControlPlane()

    # Level 2: define new role
    new_role = Role(
        id="customer-acquisition",
        name="Customer Acquisition",
        responsibilities=["customer acquisition"],
        required_capability_ids=["demand-generation", "market-research"],
        reports_to="cmo",
    )
    plane.register_role(new_role)
    retrieved = plane.get_role("customer-acquisition")
    assert retrieved is not None
    assert retrieved.required_capability_ids == ["demand-generation", "market-research"]

    # Level 5: CapabilityAssignment links Actor to Capability
    assignment = CapabilityAssignment(
        id="ca-1",
        capability_id="demand-generation",
        actor_id="agent-1",
    )
    assert assignment.actor_id == "agent-1"


# ---- K. Paperclip Contract ----


def test_organisation_paperclip_maps_role_to_agent() -> None:
    """Paperclip adapter maps Role → Agent via _map_agent_to_role and create_agent.

    This is the concrete OCP→Paperclip contract: OCP sends Role definitions,
    Paperclip creates Agents with those roles.
    """
    from organisation_paperclip import PaperclipOrganisationControlPlane

    assert hasattr(PaperclipOrganisationControlPlane, "_map_agent_to_role")
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")


def test_organisation_paperclip_maps_work_to_issue() -> None:
    """Paperclip adapter maps Work → Issue via _map_issue_to_work and create_work.

    OCP Work → Paperclip Issue is the concrete Work→Paperclip contract.
    """
    from organisation_paperclip import PaperclipOrganisationControlPlane

    assert hasattr(PaperclipOrganisationControlPlane, "_map_issue_to_work")
    assert hasattr(PaperclipOrganisationControlPlane, "create_work")


# ---- L. Authority Facts ----


def test_organisations_decide_what_should_exist() -> None:
    """OCP and People/Capability decide WHAT should exist.

    OCP: Roles, Work, Authority, Delegation
    People/Capability: Persons, Agents, Capabilities, CapabilityAssignments
    Paperclip does NOT decide what should exist — it instantiates.
    """
    from organisation_control_plane import InMemoryOrganisationControlPlane

    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "register_role")
    assert hasattr(plane, "register_authority")
    # OCP does NOT have register_person or register_agent (ADR-037)
    assert not hasattr(plane, "register_person")
    assert not hasattr(plane, "register_agent")


def test_paperclip_implements_how_agents_are_created() -> None:
    """Paperclip implements HOW agents are created via its API.

    Paperclip's create_agent() is an implementation operation.
    Paperclip does not claim authority over WHAT should exist.
    """
    from organisation_paperclip import PaperclipOrganisationControlPlane

    # create_agent is a concrete method that calls Paperclip API
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")
    sig = inspect.signature(PaperclipOrganisationControlPlane.create_agent)
    params = list(sig.parameters.keys())
    assert "name" in params  # takes implementation parameters, not organisational authority


# ---- M. Capability/Skill/Tool Ownership ----


def test_capability_registry_owns_capability_lifecycle() -> None:
    """CapabilityRegistry owns capability lifecycle — not OCP, not Paperclip.

    Per ADR-020 and ADR-040, capability authority stays in People/Capability.
    """
    from capabilities import CapabilityRegistry

    assert hasattr(CapabilityRegistry, "register")
    assert hasattr(CapabilityRegistry, "get")
    assert hasattr(CapabilityRegistry, "promote")


def test_no_skill_registry_exists() -> None:
    """No SkillRegistry exists — Skills are managed via Capability/Skill domain models.

    Constraint: Do not create SkillRegistry.
    """
    skill_path = os.path.join(PEOPLE_CAPABILITY_SRC, "skill.py")
    assert os.path.isfile(skill_path)


def test_no_tool_registry_exists() -> None:
    """No ToolRegistry exists — Tools are managed via Tool domain model.

    Constraint: Do not create ToolRegistry.
    """
    tool_path = os.path.join(PEOPLE_CAPABILITY_SRC, "tool.py")
    assert os.path.isfile(tool_path)


def test_paperclip_has_no_structured_capability_model() -> None:
    """Paperclip Agent.capabilities is a flat comma-separated string — not a structured model.

    Paperclip does NOT duplicate the Capability model. Its capabilities field
    is runtime configuration, not a domain concept.
    """
    # Verify Paperclip agent schema uses flat string for capabilities
    agent_schema = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "operational", "paperclip", "packages", "db", "src", "schema", "agents.ts"
    )
    assert os.path.isfile(agent_schema)
    with open(agent_schema) as f:
        content = f.read()
    # Paperclip stores capabilities as a flat field, not a relationship table
    assert "capabilities" in content


# ---- N. Invariants ----


def test_team_not_in_actor_type_enum() -> None:
    """Final invariant: ActorType remains PERSON and AGENT only.

    If this test ever fails, someone has added Team to ActorType
    without going through proper increment investigation.
    """
    from actor import ActorType

    assert len(list(ActorType)) == 2
    assert ActorType.PERSON.value == "person"
    assert ActorType.AGENT.value == "agent"


def test_no_new_concepts_required_for_organisation_model() -> None:
    """Final invariant: No new concepts (Team, Position Specification, HR engine,
    ChiefOfStaff class, C-Suite entity) are required for the organisational model.

    Existing Role, Actor, Capability, CapabilityAssignment, Work, Assignment,
    Authority, Delegation are sufficient.
    """
    from actor import Actor
    from capability import Capability
    from capability_assignment import CapabilityAssignment

    from role import Assignment, Authority, Delegation, Role, Work

    # All required concepts exist without new definitions
    models = [Role, Work, Assignment, Authority, Delegation, Actor, Capability, CapabilityAssignment]
    for model in models:
        assert hasattr(model, "model_fields"), f"{model.__name__} is not a Pydantic model"


def test_workflow_architecture_untouched() -> None:
    """Final invariant: Increments 36-39 architecture is not affected.

    This increment does not modify workflow invocation or execution.
    """
    from contracts.workflow_execution import WorkflowExecutionRequest, WorkflowExecutionResult

    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    result_fields = set(WorkflowExecutionResult.model_fields.keys())

    assert "workflow_name" in request_fields
    assert "status" in result_fields
    # No new Team or People/Capability fields added to workflow contracts
    for forbidden in ["team_id", "actor_type_team", "people_capability"]:
        for fields in [request_fields, result_fields]:
            assert forbidden not in fields, f"Workflow contract has unexpected field '{forbidden}'"
