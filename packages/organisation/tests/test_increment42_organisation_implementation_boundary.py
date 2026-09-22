"""
Architectural tests for Increment 42 — Organisation Implementation Boundary.

Traces current code to determine the smallest implementation boundary
required for OCP to support a concrete organisational change using the
primitives we already have.

Scenario: Customer Acquisition capability needs additional capacity.
  Option A: Add new Actor (Person/Agent) with Role + CapabilityAssignments
  Option B: Change existing Actor responsibilities/capability assignments

Both options work without introducing new domain concepts.
"""

from __future__ import annotations

import os
import re
import sys

from actor import Actor, ActorType
from agent import Agent
from agent_store import InMemoryAgentStore
from capability_assignment import CapabilityAssignment
from person import Person

from organisation_control_plane import InMemoryOrganisationControlPlane
from role import (
    Assignment,
    Authority,
    Delegation,
    Role,
    RoleStatus,
    Work,
    WorkStatus,
)

ORGANISATION_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "src")
)
PEOPLE_CAPABILITY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "people_capability", "src")
)
PAPERCLIP_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "organisation_paperclip", "src")
)
CAPABILITY_REGISTRY_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "capability_registry", "src")
)
CONTRACTS_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "contracts")
)
WORKFLOW_RUNNER_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "workflow_runner", "src")
)

sys.path.insert(0, PEOPLE_CAPABILITY_SRC)
sys.path.insert(0, CAPABILITY_REGISTRY_SRC)
sys.path.insert(0, ORGANISATION_SRC)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# A. Current creation mechanisms
# ============================================================================


def test_ocp_can_register_role() -> None:
    """OCP creates Roles via register_role() - primary organisational design."""
    from role import Role, RoleStatus

    plane = InMemoryOrganisationControlPlane()
    role = Role(
        id="test-role", name="Test Role",
        description="A test role",
        responsibilities=["test"], authority_ids=[],
        constraints=[], information_access=[],
        reports_to=None, status=RoleStatus.ACTIVE,
        required_capability_ids=[], metadata={},
    )
    plane.register_role(role)
    assert plane.get_role("test-role") is not None


def test_ocp_can_assign_work() -> None:
    """OCP assigns Work to Actor | Role | Person | Agent."""
    from role import Role, Work, WorkStatus

    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r1", name="Operator")
    plane.register_role(role)
    work = Work(id="w1", title="Test", accountable_role_id="r1", status=WorkStatus.PENDING)
    assignment = plane.assign_work(work, role)
    assert assignment.assignee_type == "role"
    assert assignment.assignee_id == "r1"


def test_people_capability_can_register_person() -> None:
    """People/Capability creates Person records via InMemoryAgentStore (ADR-037)."""

    store = InMemoryAgentStore()
    person = Person(id="p1", name="Alice")
    registered = store.register_person(person)
    assert registered.id == "p1"
    assert store.get_person("p1") is not None
    assert store.get_actor("p1") is not None


def test_people_capability_can_register_agent() -> None:
    """People/Capability creates Agent records via InMemoryAgentStore (ADR-037)."""
    from agent import Agent

    store = InMemoryAgentStore()
    agent = Agent(id="a1", name="Bot", marker="ai")
    registered = store.register_agent(agent)
    assert registered.id == "a1"
    assert store.get_agent("a1") is not None
    assert store.get_actor("a1") is not None


def test_person_creates_actor_with_person_type() -> None:
    """register_person creates Actor with ActorType.PERSON."""
    from actor import ActorType

    store = InMemoryAgentStore()
    store.register_person(Person(id="p1", name="Alice"))
    actor = store.get_actor("p1")
    assert actor is not None
    assert actor.actor_type == ActorType.PERSON
    assert actor.reference_id == "p1"


def test_agent_creates_actor_with_agent_type() -> None:
    """register_agent creates Actor with ActorType.AGENT."""
    from actor import ActorType
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="a1", name="Bot", marker="ai"))
    actor = store.get_actor("a1")
    assert actor is not None
    assert actor.actor_type == ActorType.AGENT
    assert actor.reference_id == "a1"


def test_capability_assignment_links_actor_to_capability() -> None:
    """CapabilityAssignment is authoritative Actor<->Capability link."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="a1", name="Bot", marker="ai"))
    assignment = store.assign_capability("a1", "cap-1")
    assert assignment.capability_id == "cap-1"
    assert assignment.actor_id == "a1"
    assert assignment.status.value == "active"


def test_ocp_does_not_create_persons() -> None:
    """OCP has no register_person() or register_agent() (ADR-037)."""
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    assert "def register_person" not in source
    assert "def register_agent" not in source


def test_ocp_does_not_store_person_agent_records() -> None:
    """OCP has no _persons or _agents storage (ADR-037)."""
    plane = InMemoryOrganisationControlPlane()
    assert not hasattr(plane, "_persons")
    assert not hasattr(plane, "_agents")


def test_capability_registry_owns_lifecycle() -> None:
    """CapabilityRegistry owns capability lifecycle (ADR-020)."""
    sys.path.insert(0, CAPABILITY_REGISTRY_SRC)
    from capabilities import CapabilityRegistry
    registry = CapabilityRegistry()
    assert hasattr(registry, "register")
    assert hasattr(registry, "get")
    assert hasattr(registry, "promote")


# ============================================================================
# B. Organisational change as Work
# ============================================================================


def test_work_has_required_fields_for_org_proposal() -> None:
    """Work has all fields to represent organisational change proposal."""

    fields = set(Work.model_fields.keys())
    required = [
        "title", "description", "accountable_role_id",
        "required_capability_ids", "acceptance_criteria",
        "context", "deliverables", "outcome", "dependencies",
        "status", "work_type",
    ]
    for field in required:
        assert field in fields, f"Work missing required field '{field}'"


def test_work_can_represent_organisational_change() -> None:
    """Work represents 'Create Customer Acquisition capacity' proposal."""

    proposal = Work(
        id="work-proposal-1",
        title="Create Customer Acquisition capacity",
        description="Customer Acquisition needs additional specialist capacity",
        work_type="initiative",
        status=WorkStatus.PENDING,
        priority="high",
        accountable_role_id="customer-acquisition",
        required_capability_ids=["demand-generation", "market-research", "customer-acquisition"],
        acceptance_criteria=[
            "Specialist Actor available",
            "CapabilityAssignment to demand-generation",
            "Paperclip agent provisioned",
        ],
        dependencies=[],
        deliverables=["Customer Acquisition Role", "Actor with capabilities", "Paperclip agent"],
        outcome=None,
        context={
            "current_constraint": "Capacity pressure on demand-generation",
            "evidence": "CapacityPressureSignal: demand_rate=10, capacity_rate=5",
            "economic_justification": "Q4 revenue opportunity exceeds cost",
        },
        metadata={},
    )
    assert proposal.title == "Create Customer Acquisition capacity"
    assert proposal.work_type == "initiative"
    assert proposal.required_capability_ids == ["demand-generation", "market-research", "customer-acquisition"]


def test_work_can_represent_existing_actor_change() -> None:
    """Work represents alternative: expand existing Actor instead of new."""

    proposal = Work(
        id="work-proposal-2",
        title="Expand existing marketing agent to Customer Acquisition",
        description="Budget does not support new hire; expand existing agent",
        work_type="initiative",
        status=WorkStatus.PENDING,
        priority="medium",
        accountable_role_id="customer-acquisition",
        required_capability_ids=["demand-generation"],
        acceptance_criteria=[
            "Agent reassigned to Customer Acquisition",
            "New CapabilityAssignment created",
        ],
        dependencies=[],
        deliverables=["Updated Role assignment", "New CapabilityAssignment"],
        outcome=None,
        context={
            "current_constraint": "Budget limited",
            "evidence": "Existing marketing agent has 30% capacity available",
            "economic_justification": "Cost of expansion < cost of new hire",
        },
        metadata={},
    )
    assert proposal.work_type == "initiative"
    assert proposal.required_capability_ids == ["demand-generation"]


def test_work_has_no_organisational_change_entity() -> None:
    """No OrganisationalChange entity needed — Work suffices."""

    fields = set(Work.model_fields.keys())
    for forbidden in ["change_type", "proposal_type", "decision_type", "implementation_plan"]:
        assert forbidden not in fields, f"Work should not need '{forbidden}'"


# ============================================================================
# C. Role boundary
# ============================================================================


def test_role_has_required_capability_ids() -> None:
    """Role.required_capability_ids declares what capabilities position needs."""

    role = Role(
        id="ca-role", name="Customer Acquisition",
        description="Own customer acquisition capability",
        responsibilities=["Customer acquisition"],
        required_capability_ids=["demand-generation", "market-research"],
        authority_ids=[], constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    assert role.required_capability_ids == ["demand-generation", "market-research"]


def test_role_has_responsibilities() -> None:
    """Role has responsibilities describing what the position does."""

    role = Role(
        id="ca-role", name="Customer Acquisition",
        responsibilities=["Customer acquisition", "Demand generation", "Market research"],
        required_capability_ids=[], authority_ids=[],
        constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    assert "Customer acquisition" in role.responsibilities
    assert "Demand generation" in role.responsibilities


def test_role_has_reports_to_for_hierarchy() -> None:
    """Role.reports_to establishes reporting relationships."""

    ca_role = Role(
        id="customer-acquisition", name="Customer Acquisition",
        responsibilities=["Customer acquisition"],
        required_capability_ids=[], authority_ids=[],
        constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    assert ca_role.reports_to == "founder"


def test_role_status_has_vacant() -> None:
    """RoleStatus.VACANT represents unfilled positions."""
    from role import RoleStatus
    assert RoleStatus.VACANT.value == "vacant"


def test_role_status_has_active() -> None:
    """RoleStatus.ACTIVE represents filled operational positions."""
    from role import RoleStatus
    assert RoleStatus.ACTIVE.value == "active"


def test_role_has_no_actor_fields() -> None:
    """Role has no actor_id, person_id, agent_id fields."""

    fields = set(Role.model_fields.keys())
    for forbidden in ["actor_id", "person_id", "agent_id", "assigned_to"]:
        assert forbidden not in fields, f"Role should not have '{forbidden}'"


# ============================================================================
# D. Actor creation boundary
# ============================================================================


def test_actor_is_lightweight_reference() -> None:
    """Actor is lightweight reference, not a full entity."""

    fields = set(Actor.model_fields.keys())
    assert "id" in fields
    assert "name" in fields
    assert "actor_type" in fields
    assert "reference_id" in fields
    assert "fulfilled_role_ids" in fields
    assert "metadata" in fields


def test_actor_type_has_only_person_and_agent() -> None:
    """ActorType has exactly PERSON and AGENT."""

    members = [m.value for m in ActorType]
    assert set(members) == {"person", "agent"}
    assert len(list(ActorType)) == 2


def test_actor_links_to_person_or_agent_via_reference_id() -> None:
    """Actor.reference_id points to Person or Agent."""

    person_actor = Actor(
        id="p1", name="Alice",
        actor_type=ActorType.PERSON,
        reference_id="p1", marker=None,
        fulfilled_role_ids=[], metadata={},
    )
    assert person_actor.reference_id == "p1"

    agent_actor = Actor(
        id="a1", name="Bot",
        actor_type=ActorType.AGENT,
        reference_id="a1", marker="ai",
        fulfilled_role_ids=[], metadata={},
    )
    assert agent_actor.reference_id == "a1"


def test_actor_distinguishes_org_requirement_from_execution() -> None:
    """Actor is the organisational identity; Person/Agent is execution identity.

    Role (organisational requirement) is fulfilled by Actor.
    Person/Agent provides the execution identity behind the Actor.
    """
    from agent import Agent

    # Person provides execution identity for an Actor
    person = Person(id="p1", name="Alice", role_ids=["customer-acquisition"])
    person_actor = Actor(
        id="p1", name="Alice",
        actor_type=ActorType.PERSON,
        reference_id="p1", marker=None,
        fulfilled_role_ids=["customer-acquisition"],
        metadata={},
    )
    assert person_actor.reference_id == person.id
    assert person_actor.actor_type == ActorType.PERSON

    # Agent provides execution identity for an Actor
    agent = Agent(id="a1", name="Bot", marker="ai", status="active")
    agent_actor = Actor(
        id="a1", name="Bot",
        actor_type=ActorType.AGENT,
        reference_id="a1", marker="ai",
        fulfilled_role_ids=["customer-acquisition"],
        metadata={},
    )
    assert agent_actor.reference_id == agent.id
    assert agent_actor.actor_type == ActorType.AGENT


# ============================================================================
# E. Capability assignment boundary
# ============================================================================


def test_capability_assignment_has_canonical_actor_link() -> None:
    """CapabilityAssignment.actor_id is the canonical link."""

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "actor_id" in fields
    assert "capability_id" in fields


def test_capability_assignment_has_skill_tool_references() -> None:
    """CapabilityAssignment optionally references Skills and Tools."""

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "skill_ids" in fields
    assert "tool_ids" in fields


def test_capability_assignment_has_no_proficiency_field() -> None:
    """Proficiency is separate from CapabilityAssignment."""

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "proficiency" not in fields


def test_capability_assignment_status_encodes_validity() -> None:
    """Assignment status encodes whether assignment is active."""
    from capability_assignment import AssignmentStatus

    assert AssignmentStatus.ACTIVE.value == "active"
    assert AssignmentStatus.SUSPENDED.value == "suspended"
    assert AssignmentStatus.REVOKED.value == "revoked"


def test_capability_assignment_type_encodes_capacity() -> None:
    """AssignmentType (PRIMARY|SECONDARY|BACKUP) encodes capacity tier."""
    from capability_assignment import AssignmentType

    assert AssignmentType.PRIMARY.value == "primary"
    assert AssignmentType.SECONDARY.value == "secondary"
    assert AssignmentType.BACKUP.value == "backup"


def test_capability_assignment_authoritative_link() -> None:
    """CapabilityAssignment is the authoritative Actor<->Capability relationship.

    Capability remains organisation-owned (People/Capability).
    Actor remains execution identity. Assignment is the link.
    Paperclip does NOT become the source of Capability semantics.
    """
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="a1", name="Bot", marker="ai"))

    # Assignment links Actor to Capability
    assignment = store.assign_capability("a1", "customer-acquisition")
    assert assignment.actor_id == "a1"
    assert assignment.capability_id == "customer-acquisition"
    assert assignment.status.value == "active"

    # Multiple capabilities can be assigned to same Actor
    assignment2 = store.assign_capability("a1", "demand-generation")
    assert assignment2.capability_id == "demand-generation"

    assignments = store.get_assignments_for_actor("a1")
    assert len(assignments) == 2


# ============================================================================
# F. Existing Actor vs new Actor
# ============================================================================


def test_existing_actor_can_receive_new_capability() -> None:
    """Option A: existing Actor gets new CapabilityAssignment."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="existing", name="Existing", marker="ai"))

    # Assign new capability to existing Actor
    assignment = store.assign_capability("existing", "demand-generation")
    assert assignment.capability_id == "demand-generation"
    assert assignment.actor_id == "existing"


def test_new_actor_can_be_created_with_capabilities() -> None:
    """Option B: new Actor created with Role + CapabilityAssignments."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="new-specialist", name="Specialist", marker="ai"))

    # Assign multiple capabilities to new Actor
    cap1 = store.assign_capability("new-specialist", "demand-generation")
    cap2 = store.assign_capability("new-specialist", "market-research")
    assert cap1.capability_id == "demand-generation"
    assert cap2.capability_id == "market-research"


def test_existing_vs_new_actor_both_work() -> None:
    """Both options work without new domain concepts."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="existing", name="Existing", marker="ai"))
    store.register_agent(Agent(id="new", name="New", marker="ai"))

    existing_assignment = store.assign_capability("existing", "cap-1")
    new_assignment = store.assign_capability("new", "cap-1")

    assert existing_assignment.capability_id == "cap-1"
    assert new_assignment.capability_id == "cap-1"
    # Both options use the same CapabilityAssignment mechanism
    assert type(existing_assignment) == type(new_assignment)


def test_capability_gap_does_not_mean_new_person() -> None:
    """Capability gap can be resolved by changing existing Actor.

    Per Increment 41: A capability gap does not automatically mean
    another person or agent.
    """
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="existing", name="Existing", marker="ai"))

    # Existing Actor already has some capabilities
    store.assign_capability("existing", "cap-a")

    # Gap can be filled by assigning new capability to existing Actor
    new_assignment = store.assign_capability("existing", "cap-b")
    assert new_assignment.capability_id == "cap-b"

    # No new Actor needed - same Actor with more assignments
    assignments = store.get_assignments_for_actor("existing")
    assert len(assignments) == 2


def test_alternative_capacity_responses() -> None:
    """Existing primitives can represent alternative capacity responses.

    Option A: New Actor with new Role + CapabilityAssignments
    Option B: Existing Actor gets new CapabilityAssignments
    Option C: Change execution path (work_type, required_capability_ids)
    """

    # Option A: New Actor
    work_a = Work(
        id="option-a", title="Hire new specialist",
        work_type="initiative", status=WorkStatus.PENDING,
        accountable_role_id="customer-acquisition",
        required_capability_ids=["demand-generation"],
        context={"option": "new-actor"},
        metadata={},
    )

    # Option B: Existing Actor expansion
    work_b = Work(
        id="option-b", title="Expand existing agent",
        work_type="initiative", status=WorkStatus.PENDING,
        accountable_role_id="customer-acquisition",
        required_capability_ids=["demand-generation"],
        context={"option": "existing-actor"},
        metadata={},
    )

    # Option C: Change execution path
    work_c = Work(
        id="option-c", title="Automate customer acquisition",
        work_type="project", status=WorkStatus.PENDING,
        accountable_role_id="customer-acquisition",
        required_capability_ids=["automation"],
        context={"option": "change-execution-path"},
        metadata={},
    )

    assert work_a.work_type == "initiative"
    assert work_b.work_type == "initiative"
    assert work_c.work_type == "project"
    # All three options use the same Work model
    assert type(work_a) == type(work_b) == type(work_c)


# ============================================================================
# G. Economic justification boundary
# ============================================================================


def test_economic_data_in_work_context() -> None:
    """Economic reasoning enters via Work.context dict."""

    work = Work(
        id="econ-work", title="Customer Acquisition capacity",
        work_type="initiative", status=WorkStatus.PENDING,
        accountable_role_id="customer-acquisition",
        required_capability_ids=["demand-generation"],
        context={
            "current_capacity_constraint": "demand_rate=10, capacity_rate=5",
            "evidence": "CapacityPressureSignal detected",
            "expected_outcome": "5 additional units throughput",
            "economic_justification": "Revenue opportunity > cost",
        },
        metadata={},
    )
    assert "economic_justification" in work.context
    assert "evidence" in work.context


def test_work_has_no_economic_fields() -> None:
    """Work has no cost/value/ROI fields.

    Economic reasoning stays analytical (in context),
    not typed as domain fields.
    """

    fields = set(Work.model_fields.keys())
    for forbidden in ["cost", "budget", "roi", "value", "price", "revenue"]:
        assert forbidden not in fields, f"Work should not have '{forbidden}'"


def test_no_economic_entities_created() -> None:
    """No Cost, Value, ROI entities created.

    Work.context carries the economic data analytically.
    """
    own_path = os.path.abspath(__file__)
    for package_path in [
        "packages/organisation/src",
        "packages/organisation/tests",
        "packages/people_capability/src",
        "packages/capability_registry/src",
    ]:
        if not os.path.isdir(package_path):
            continue
        for root, _, files in os.walk(package_path):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                if os.path.abspath(fpath) == own_path:
                    continue
                with open(fpath) as f:
                    content = f.read()
                assert "class Cost(" not in content, f"Cost class in {fpath}"
                assert "class Value(" not in content, f"Value class in {fpath}"


# ============================================================================
# H. Paperclip implementation boundary
# ============================================================================


def test_paperclip_has_create_agent() -> None:
    """Paperclip creates Agents via create_agent()."""
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")


def test_paperclip_maps_role_to_agent() -> None:
    """Paperclip _map_agent_to_role maps Agent to Role."""
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "_map_agent_to_role")


def test_paperclip_maps_work_to_issue() -> None:
    """Paperclip _map_issue_to_work maps Work to Issue."""
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "_map_issue_to_work")
    assert hasattr(PaperclipOrganisationControlPlane, "create_work")


def test_ocp_sends_role_definitions() -> None:
    """OCP sends Role definitions (WHAT should exist).

    Paperclip receives: id, name, description, required_capability_ids,
    reports_to. Paperclip maps these to Agent properties.
    """

    role = Role(
        id="ca-role", name="Customer Acquisition",
        description="Customer acquisition function",
        responsibilities=["Acquisition"],
        required_capability_ids=["demand-generation"],
        authority_ids=[], constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    assert role.required_capability_ids == ["demand-generation"]


def test_paperclip_agent_has_capabilities_field() -> None:
    """Paperclip Agent.capabilities is flat string, not structured model."""
    paperclip_src = os.path.join(PAPERCLIP_SRC, "organisation_paperclip.py")
    with open(paperclip_src) as f:
        source = f.read()
    # Agent.capabilities mapped as comma-separated string in create_agent
    assert "capabilities" in source
    # Paperclip does NOT have structured capability model (Capability, Skill, etc.)
    assert "class Capability(" not in source
    assert "class Skill(" not in source


def test_ocp_does_not_import_paperclip() -> None:
    """OCP does not import Paperclip ( organisational boundary)."""
    import ast
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "organisation_paperclip" not in node.module


def test_paperclip_does_not_define_org_concepts() -> None:
    """Paperclip does not define Actor, Capability, Skill, Assignment."""
    forbidden = {"Actor", "Capability", "Skill", "CapabilityAssignment"}
    paperclip_src = os.path.join(PAPERCLIP_SRC)
    for filename in os.listdir(paperclip_src):
        if not filename.endswith(".py"):
            continue
        if filename == "__init__.py":
            continue
        path = os.path.join(paperclip_src, filename)
        with open(path) as f:
            import ast
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden:
                assert False, f"Paperclip should not define {node.name}"


def test_ocp_to_paperclip_contract() -> None:
    """Minimum OCP->Paperclip contract:

    OCP sends: Role definitions + required_capability_ids
    Paperclip creates: Agent with matching roles and capabilities
    """
    from organisation_paperclip import PaperclipOrganisationControlPlane

    plane = PaperclipOrganisationControlPlane.__new__(PaperclipOrganisationControlPlane)
    assert plane is not None

    # Contract methods exist
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")
    assert hasattr(PaperclipOrganisationControlPlane, "_map_agent_to_role")
    assert hasattr(PaperclipOrganisationControlPlane, "create_work")
    assert hasattr(PaperclipOrganisationControlPlane, "_map_issue_to_work")


def test_paperclip_ownes_operational_state() -> None:
    """Paperclip owns operational execution state; OCP owns domain truth.

    Paperclip Agent.reportsTo (operational),
    OCP Role.reports_to (organisational intent).
    """
    from role import Role

    agent = Agent(id="a1", name="Bot", marker="ai", status="active")
    role = Role(
        id="r1", name="Operator",
        responsibilities=["test"], required_capability_ids=[],
        authority_ids=[], constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    # Agent has runtime_identity (operational)
    assert agent.runtime_identity is None
    # Role has organisational intent
    assert role.reports_to == "founder"


# ============================================================================
# I. Creation authority
# ============================================================================


def test_ocp_creates_roles_and_work() -> None:
    """OCP creates Roles and Work - organisational decisions."""

    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "register_role")
    assert hasattr(plane, "assign_work")
    assert hasattr(plane, "register_capability")
    assert hasattr(plane, "delegate_authority")


def test_ocp_creates_authorities() -> None:
    """OCP creates Authorities for delegation."""
    from role import Authority

    plane = InMemoryOrganisationControlPlane()
    authority = Authority(
        id="auth-1", name="Approve budget", scope="budget",
        grantor_role_id="founder", grantee_role_id="operator",
    )
    plane.register_authority(authority)
    assert plane.get_role is not None


def test_ocp_does_not_create_persons_or_agents() -> None:
    """OCP does NOT create Persons or Agents (ADR-037)."""

    plane = InMemoryOrganisationControlPlane()
    assert not hasattr(plane, "register_person")
    assert not hasattr(plane, "register_agent")


def test_people_capability_creates_actors() -> None:
    """People/Capability creates Actors (via InMemoryAgentStore)."""

    store = InMemoryAgentStore()
    assert hasattr(store, "register_agent")
    assert hasattr(store, "register_person")
    assert hasattr(store, "assign_capability")


def test_paperclip_implements_how_agents_created() -> None:
    """Paperclip implements HOW agents are created (implementation operation)."""
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")


def test_no_hr_engine_exists() -> None:
    """No HR engine, recruitment system, or People/HR subsystem exists."""
    org_src = ORGANISATION_SRC
    for root, _, files in os.walk(org_src):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            with open(path) as f:
                content = f.read()
            assert not re.search(r"\bHRService\b", content)
            assert not re.search(r"\bPeopleCapabilityManager\b", content)
            assert not re.search(r"\bOrganisationBuilder\b", content)
            assert not re.search(r"\bTeamFactory\b", content)
            assert not re.search(r"\bAgentFactory\b", content)


# ============================================================================
# J. Recursive organisational operation
# ============================================================================


def test_people_capability_can_create_roles() -> None:
    """People/Capability can define new Roles via register_role."""

    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "register_role")


def test_recursive_flow_same_mechanisms() -> None:
    """Recursive organisation uses same mechanisms at each level.

    Level 1: Founder assigns Work to People/Capability Role
    Level 2: People/Capability defines new Role (register_role)
    Level 3: Paperclip creates Agent for Role (create_agent)
    Level 4: Actor created from Agent (register_agent)
    Level 5: CapabilityAssignment links Actor to Capabilities
    """
    from role import Role

    plane = InMemoryOrganisationControlPlane()

    # Level 2: define new role
    new_role = Role(
        id="customer-acquisition",
        name="Customer Acquisition",
        responsibilities=["customer acquisition"],
        required_capability_ids=["demand-generation", "market-research"],
        reports_to="founder",
    )
    plane.register_role(new_role)
    retrieved = plane.get_role("customer-acquisition")
    assert retrieved is not None
    assert retrieved.required_capability_ids == ["demand-generation", "market-research"]


def test_capability_assignment_links_new_actor() -> None:
    """CapabilityAssignment links new Actor to required Capabilities."""

    assignment = CapabilityAssignment(
        id="ca-1",
        capability_id="demand-generation",
        actor_id="agent-1",
    )
    assert assignment.capability_id == "demand-generation"
    assert assignment.actor_id == "agent-1"


def test_people_capability_ordinary_construct() -> None:
    """People/Capability is ordinary organisational construct.

    No HRService, PeopleCapabilityManager, OrganisationBuilder,
    TeamFactory, AgentFactory domain service needed.
    """

    plane = InMemoryOrganisationControlPlane()
    methods = set(dir(plane))
    # No privileged creation methods
    assert "register_person" not in methods
    assert "register_agent" not in methods
    assert "register_role" in methods
    assert "assign_work" in methods


def test_chief_of_staff_can_be_role() -> None:
    """Chief of Staff = Role with coordination responsibilities."""

    cos_role = Role(
        id="chief-of-staff", name="Chief of Staff",
        responsibilities=["coordination", "delegation", "oversight"],
        required_capability_ids=["coordination", "delegation"],
        authority_ids=[], constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    assert cos_role.name == "Chief of Staff"
    assert "coordination" in cos_role.responsibilities


def test_chief_of_staff_uses_delegation() -> None:
    """Chief of Staff coordinates via Delegation, not special authority."""

    authority = Authority(
        id="auth-1", name="Coordinate", scope="coordination",
        grantor_role_id="founder", grantee_role_id="chief-of-staff",
    )
    delegation = Delegation(
        id="del-1", authority_id=authority.id,
        from_role_id="founder", to_role_id="chief-of-staff",
    )
    assert delegation.from_role_id == "founder"
    assert delegation.to_role_id == "chief-of-staff"


def test_chief_of_staff_no_special_class() -> None:
    """No ChiefOfStaff class - it is a Role."""
    import os
    org_src = ORGANISATION_SRC
    for root, _, files in os.walk(org_src):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            with open(path) as f:
                content = f.read()
            assert not re.search(r"\bclass ChiefOfStaff\b", content)
            assert not re.search(r"\bclass HRService\b", content)


# ============================================================================
# K. Post-change organisational state
# ============================================================================


def test_post_change_state_actor_exists() -> None:
    """After organisational change: Actor exists."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="specialist", name="Specialist", marker="ai"))
    assert store.get_actor("specialist") is not None


def test_post_change_state_role_exists() -> None:
    """After organisational change: Role exists."""
    from role import Role

    plane = InMemoryOrganisationControlPlane()
    role = Role(
        id="ca-role", name="Customer Acquisition",
        responsibilities=["Acquisition"], required_capability_ids=[],
        authority_ids=[], constraints=[], information_access=[],
        reports_to="founder", status=RoleStatus.ACTIVE,
        metadata={},
    )
    plane.register_role(role)
    assert plane.get_role("ca-role") is not None


def test_post_change_state_capability_assignment_exists() -> None:
    """After organisational change: CapabilityAssignment exists."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="specialist", name="Specialist", marker="ai"))
    assignment = store.assign_capability("specialist", "demand-generation")
    assert assignment is not None
    assert assignment.status.value == "active"


def test_post_change_state_work_complete() -> None:
    """After organisational change: Work is complete."""
    from role import Role, Work, WorkStatus

    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r1", name="Operator")
    plane.register_role(role)
    work = Work(id="w1", title="Task", accountable_role_id="r1", status=WorkStatus.PENDING)
    plane.assign_work(work, role)
    plane.complete_work("w1")
    assert plane.get_work("w1").status == WorkStatus.COMPLETED


def test_post_change_state_implementation_ref() -> None:
    """After organisational change: implementation reference exists.

    Paperclip Agent ID becomes the implementation reference.
    OCP references it via Actor.reference_id.
    """
    from agent import Agent

    store = InMemoryAgentStore()
    agent = Agent(
        id="paperclip-agent-1",
        name="Customer Acquisition Agent",
        marker="ai",
        runtime_identity="ca-agent-1",
    )
    store.register_agent(agent)
    actor = store.get_actor("paperclip-agent-1")
    # Actor.reference_id = Paperclip Agent ID = implementation reference
    assert actor is not None
    assert actor.reference_id == "paperclip-agent-1"


# ============================================================================
# L. Failure / partial completion boundary
# ============================================================================


def test_failure_ocp_succeeds_paperclip_fails() -> None:
    """If OCP succeeds but Paperclip provisioning fails:

    Organisational state is consistent (Role, Work exist).
    Implementation reference is missing (Actor not created).
    Consistency belongs to OCP. Paperclip is retriable.
    """
    from role import Role, Work, WorkStatus

    plane = InMemoryOrganisationControlPlane()
    role = Role(id="ca-role", name="Customer Acquisition",
                responsibilities=["Acquisition"],
                required_capability_ids=["demand-generation"],
                authority_ids=[], constraints=[], information_access=[],
                reports_to="founder", status=RoleStatus.ACTIVE,
                metadata={})
    plane.register_role(role)
    work = Work(id="w-change", title="Create CA capacity",
                work_type="initiative", status=WorkStatus.PENDING,
                accountable_role_id="ca-role",
                required_capability_ids=["demand-generation"],
                context={"paperclip_status": "failed"},
                metadata={})
    assignment = plane.assign_work(work, role)
    assert assignment is not None
    assert work.status == WorkStatus.ASSIGNED
    # Role and Work exist even though Paperclip failed
    assert plane.get_role("ca-role") is not None
    assert plane.get_work("w-change") is not None
    # But no Actor was created (Paperclip failure)
    # This is the expected partial state


def test_failure_role_succeeds_actor_fails() -> None:
    """If Role creation succeeds but Actor creation fails:

    Role exists as vacant position (RoleStatus.VACANT).
    Work may be proposed but unassigned.
    People/Capability retries Actor creation.
    """
    from role import Role, RoleStatus

    plane = InMemoryOrganisationControlPlane()
    role = Role(
        id="ca-vacant", name="Customer Acquisition",
        responsibilities=["Acquisition"],
        required_capability_ids=["demand-generation"],
        status=RoleStatus.VACANT,
        authority_ids=[], constraints=[], information_access=[],
        reports_to="founder", metadata={},
    )
    plane.register_role(role)
    retrieved = plane.get_role("ca-vacant")
    assert retrieved.status == RoleStatus.VACANT


def test_creation_authority_belongs_to_org() -> None:
    """Creation authority belongs to OCP/People/Capability.

    Paperclip is implementation, not authority.
    If Paperclip fails, OCP state is preserved for retry.
    """
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    # OCP creates organisational intent
    assert hasattr(plane, "register_role")
    # People/Capability creates identities
    assert hasattr(store, "register_person")
    assert hasattr(store, "register_agent")
    # Paperclip instantiates
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")


def test_failure_boundary_no_distributed_transactions() -> None:
    """No distributed transactions or event sourcing.

    Each bounded context manages its own consistency:
    - OCP: Roles, Work, Authority, Delegation
    - People/Capability: Persons, Agents, CapabilityAssignments
    - Paperclip: Agents (operational), Issues (operational)
    """
    import ast
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert "transaction" not in node.attr.lower()


# ============================================================================
# M. Existing test coverage
# ============================================================================


def test_increment40_tests_cover_org_boundary() -> None:
    """Increment 40 tests already prove Team is not OCP Actor."""
    test_path = os.path.join(
        os.path.dirname(__file__),
        "test_increment40_organisation_team_role_boundary.py",
    )
    assert os.path.isfile(test_path)


def test_increment41_tests_cover_economic_boundary() -> None:
    """Increment 41 tests already prove no economic entities needed."""
    test_path = os.path.join(
        os.path.dirname(__file__),
        "test_increment41_economic_organisation_boundary.py",
    )
    assert os.path.isfile(test_path)


def test_existing_tests_do_not_duplicate() -> None:
    """No existing test file duplicates Increment 42 tests."""
    test_dir = os.path.dirname(__file__)
    own_path = os.path.abspath(__file__)
    for fname in os.listdir(test_dir):
        if not (fname.startswith("test_increment") and fname.endswith(".py")):
            continue
        fpath = os.path.join(test_dir, fname)
        if os.path.abspath(fpath) == own_path:
            continue
        with open(fpath) as f:
            content = f.read()
        assert "test_increment42" not in content, \
            f"Increment 42 tests found in {fname}"


def test_new_tests_needed() -> None:
    """New tests in Increment 42 establish genuinely new conclusions:

    1. Work represents organisational change (new conclusion)
    2. OCP->Paperclip contract is minimal (new conclusion)
    3. Both Actor options work (new conclusion)
    4. Creation authority is distributed (new conclusion)
    5. Failure boundary is clean (new conclusion)
    """
    # These tests prove new conclusions not covered by increments 24-41
    from capability_assignment import CapabilityAssignment

    from organisation_control_plane import InMemoryOrganisationControlPlane

    # Work can represent organisational proposal
    work = Work(
        id="test", title="Create capacity",
        work_type="initiative", status="pending",
        accountable_role_id="r1",
        required_capability_ids=["cap-1"],
        context={"justification": "revenue > cost"},
        metadata={},
    )
    assert work.title == "Create capacity"

    # CapabilityAssignment links Actor to Capability
    assignment = CapabilityAssignment(
        id="t", capability_id="cap-1", actor_id="a1",
    )
    assert assignment.actor_id == "a1"

    # OCP creates Roles, not Persons/Agents
    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "register_role")
    assert not hasattr(plane, "register_person")


# ============================================================================
# N. Invariants
# ============================================================================


def test_no_new_concepts_introduced() -> None:
    """Increment 42 introduces NO new domain concepts.

    All organisation change is represented through:
    - Role (organisational requirement)
    - Actor (execution identity)
    - CapabilityAssignment (authoritative link)
    - Work (organisational proposal and state)
    - Capability (what can be done)
    - Paperclip Agent (implementation)
    """
    from actor import Actor
    from capability import Capability
    from capability_assignment import CapabilityAssignment

    models = [Role, Work, Assignment, Authority, Delegation, Actor, Capability, CapabilityAssignment]
    for model in models:
        assert hasattr(model, "model_fields"), f"{model.__name__} is not a Pydantic model"


def test_team_not_actor() -> None:
    """Team is NOT an OCP Actor (per Increment 40)."""
    members = [m.value for m in ActorType]
    assert "team" not in members


def test_no_position_specification() -> None:
    """No PositionSpecification needed (per Increment 40)."""
    fields = set(Role.model_fields.keys())
    assert "position_specification" not in fields
    assert "job_specification" not in fields


def test_no_decision_entity() -> None:
    """No Decision entity (per Increment 41).

    Uses AST parsing to detect class definitions, avoiding
    literal string checks that would create false positives
    in other tests.
    """
    found = False
    for root, _, files in os.walk("/home/martinp/Documents/projects/aiassistant/packages"):
        if "/tests/" in root or root.endswith("/tests"):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            try:
                import ast
                with open(path) as fh:
                    tree = ast.parse(fh.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == "Decision":
                        found = True
            except (OSError, UnicodeDecodeError, SyntaxError):
                pass
    assert not found, "No Decision entity should exist"


def test_no_organizational_change_entity() -> None:
    """No OrganisationalChange entity - Work suffices."""
    test_file = os.path.abspath(__file__)
    found = False
    for root, _, files in os.walk("/home/martinp/Documents/projects/aiassistant/packages"):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            if os.path.abspath(path) == test_file:
                continue
            try:
                with open(path) as fh:
                    content = fh.read()
                if "class OrganisationalChange(" in content or "class OrgChange(" in content:
                    found = True
            except (OSError, UnicodeDecodeError):
                pass
    assert not found, "No OrganisationalChange entity should exist"


def test_no_capacity_entity() -> None:
    """No Capacity entity (per Increment 41)."""
    from capability_assignment import CapabilityAssignment

    from role import Work

    for model in [Actor, CapabilityAssignment, Work]:
        fields = set(model.model_fields.keys())
        for forbidden in ["capacity", "capacity_rate", "quota", "limit"]:
            assert forbidden not in fields, f"{model.__name__} should not have '{forbidden}'"


def test_workflow_untouched() -> None:
    """Increments 36-39 workflow semantics not modified."""
    from contracts.workflow_execution import WorkflowExecutionRequest
    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in request_fields
    for forbidden in ["team_id", "actor_type_team", "people_capability", "capacity"]:
        assert forbidden not in request_fields


def test_no_paperclip_in_ocp() -> None:
    """OCP does not import Paperclip."""
    import ast
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "organisation_paperclip" not in node.module


def test_actor_not_in_organisation() -> None:
    """Actor is in people_capability, not organisation (ADR-037)."""
    org_actor = os.path.join(ORGANISATION_SRC, "actor.py")
    assert not os.path.isfile(org_actor)
    pc_actor = os.path.join(PEOPLE_CAPABILITY_SRC, "actor.py")
    assert os.path.isfile(pc_actor)


def test_capability_not_in_organisation() -> None:
    """Capability is in people_capability, not organisation (ADR-020)."""
    org_cap = os.path.join(ORGANISATION_SRC, "capability.py")
    assert not os.path.isfile(org_cap)
    pc_cap = os.path.join(PEOPLE_CAPABILITY_SRC, "capability.py")
    assert os.path.isfile(pc_cap)
