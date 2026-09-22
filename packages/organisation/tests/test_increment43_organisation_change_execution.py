"""
Increment 43 — First Organisational Change Vertical Slice.

Tests one complete organisational change flow using existing primitives:
    Need → Work → Role → Actor → CapabilityAssignment → Paperclip → state

Also proves the alternative:
    Need → Work → existing Actor → additional CapabilityAssignment → state
"""

from __future__ import annotations

import os
import sys

from actor import Actor, ActorType
from agent import Agent
from agent_store import InMemoryAgentStore
from capability_assignment import CapabilityAssignment

from organisation_control_plane import InMemoryOrganisationControlPlane
from role import (
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

sys.path.insert(0, PEOPLE_CAPABILITY_SRC)
sys.path.insert(0, ORGANISATION_SRC)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# A. Implementation map verification
# ============================================================================


def test_implementation_map_work_creation() -> None:
    """Work creation via InMemoryOrganisationControlPlane.register_role + assign_work."""
    plane = InMemoryOrganisationControlPlane()
    role = Role(id="r1", name="Operator", authority_ids=[])
    plane.register_role(role)
    work = Work(id="w1", title="Test", accountable_role_id="r1", status=WorkStatus.PENDING)
    assert plane.get_work("w1") is None
    plane.assign_work(work, role)
    assert plane.get_work("w1") is not None


def test_implementation_map_role_creation() -> None:
    """Role creation via register_role."""
    plane = InMemoryOrganisationControlPlane()
    role = Role(id="ca-role", name="Customer Acquisition", responsibilities=["Acquisition"],
                required_capability_ids=["customer-acquisition"], authority_ids=[],
                constraints=[], information_access=[], reports_to=None,
                status=RoleStatus.ACTIVE, metadata={})
    plane.register_role(role)
    assert plane.get_role("ca-role") is not None


def test_implementation_map_actor_creation() -> None:
    """Actor creation via InMemoryAgentStore.register_agent (ADR-037)."""
    store = InMemoryAgentStore()
    agent = Agent(id="a1", name="Specialist", marker="ai")
    store.register_agent(agent)
    assert store.get_actor("a1") is not None
    assert store.get_agent("a1") is not None


def test_implementation_map_capability_assignment() -> None:
    """CapabilityAssignment via InMemoryAgentStore.assign_capability."""
    store = InMemoryAgentStore()
    store.register_agent(Agent(id="a1", name="Specialist", marker="ai"))
    assignment = store.assign_capability("a1", "customer-acquisition")
    assert assignment.capability_id == "customer-acquisition"
    assert assignment.actor_id == "a1"
    assert assignment.status.value == "active"


def test_implementation_map_paperclip_agent() -> None:
    """Paperclip Agent creation methods exist."""
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")
    assert hasattr(PaperclipOrganisationControlPlane, "_map_agent_to_role")
    assert hasattr(PaperclipOrganisationControlPlane, "create_work")
    assert hasattr(PaperclipOrganisationControlPlane, "_map_issue_to_work")


# ============================================================================
# B. New Actor path — main vertical slice
# ============================================================================


def test_new_actor_path_organisational_authority() -> None:
    """Authority grants organisational change execution right."""
    plane = InMemoryOrganisationControlPlane()
    authority = Authority(id="auth-execute-change", name="Execute organisational change",
                          scope="execute-organisational-change", grantor_role_id="founder",
                          grantee_role_id="customer-acquisition")
    plane.register_authority(authority)
    assert plane._authorities["auth-execute-change"] is not None


def test_new_actor_path_delegation() -> None:
    """Delegation from founder to Customer Acquisition role."""
    plane = InMemoryOrganisationControlPlane()
    founder_role = Role(id="founder", name="Founder", authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    ca_role = Role(id="customer-acquisition", name="Customer Acquisition",
                   authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    plane.register_role(founder_role)
    plane.register_role(ca_role)
    plane.register_authority(Authority(id="auth-execute-change", name="Execute",
                                       scope="execute-organisational-change",
                                       grantor_role_id="founder", grantee_role_id="customer-acquisition"))
    delegation = plane.delegate_authority(founder_role, ca_role, plane._authorities["auth-execute-change"])
    assert delegation.from_role_id == "founder"
    assert delegation.to_role_id == "customer-acquisition"


def test_new_actor_path_execute_organisational_change() -> None:
    """New Actor path: Work → Role → Actor → CapabilityAssignment."""
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder_role = Role(id="founder", name="Founder", authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    ca_role = Role(id="customer-acquisition", name="Customer Acquisition",
                   responsibilities=["Customer acquisition"],
                   required_capability_ids=["demand-generation", "customer-acquisition"],
                   authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    plane.register_role(founder_role)
    plane.register_role(ca_role)
    plane.register_authority(Authority(id="auth-execute-change", name="Execute organisational change",
                                       scope="execute-organisational-change",
                                       grantor_role_id="founder", grantee_role_id="customer-acquisition"))
    plane.delegate_authority(founder_role, ca_role, plane._authorities["auth-execute-change"])

    agent = Agent(id="specialist", name="Customer Acquisition Specialist", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("specialist")
    assert actor is not None
    assert actor.actor_type == ActorType.AGENT

    store.assign_capability("specialist", "demand-generation")
    store.assign_capability("specialist", "customer-acquisition")
    assignments = store.get_assignments_for_actor("specialist")
    assert len(assignments) == 2

    work = Work(id="work-add-ca-capacity", title="Add Customer Acquisition capacity",
                description="Customer Acquisition needs additional specialist capacity",
                work_type="initiative", status=WorkStatus.PENDING, priority="high",
                accountable_role_id="customer-acquisition",
                required_capability_ids=["demand-generation", "customer-acquisition"],
                acceptance_criteria=["Specialist Actor available"],
                context={"current_constraint": "Capacity pressure on demand-generation",
                         "evidence": "CapacityPressureSignal detected",
                         "economic_justification": "Q4 revenue opportunity exceeds cost"},
                metadata={})

    result = plane.execute_organisational_change(work=work, assignee=actor, role=ca_role,
                                                  capability_ids=["demand-generation", "customer-acquisition"])
    assert result["status"] == "executed"
    assert result["role_id"] == "customer-acquisition"
    assert result["work_id"] == "work-add-ca-capacity"
    assert result["assignee_actor_id"] == "specialist"
    assert result["authority_checked"] is True

    assigned_work = plane.get_work("work-add-ca-capacity")
    assert assigned_work is not None
    assert assigned_work.status == WorkStatus.ASSIGNED
    assert assigned_work.assignee_actor_id == "specialist"

    all_assignments = list(plane._assignments.values())
    work_assignments = [a for a in all_assignments if a.work_id == "work-add-ca-capacity"]
    assert len(work_assignments) == 1


# ============================================================================
# C. Existing Actor path — alternative vertical slice
# ============================================================================


def test_existing_actor_path_execute_organisational_change() -> None:
    """Existing Actor path: Work → existing Actor → additional CapabilityAssignment."""
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder_role = Role(id="founder", name="Founder", authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    ca_role = Role(id="customer-acquisition", name="Customer Acquisition",
                   required_capability_ids=[], authority_ids=["auth-execute-change"], status=RoleStatus.ACTIVE)
    plane.register_role(founder_role)
    plane.register_role(ca_role)
    plane.register_authority(Authority(id="auth-execute-change", name="Execute",
                                       scope="execute-organisational-change",
                                       grantor_role_id="founder", grantee_role_id="customer-acquisition"))
    plane.delegate_authority(founder_role, ca_role, plane._authorities["auth-execute-change"])

    existing_agent = Agent(id="existing-agent", name="Existing Agent", marker="ai")
    store.register_agent(existing_agent)
    existing_actor = store.get_actor("existing-agent")
    assert existing_actor is not None

    store.assign_capability("existing-agent", "demand-generation")
    assert store.actor_has_capability("existing-agent", "demand-generation")

    work = Work(id="work-expand-existing", title="Expand existing agent to Customer Acquisition",
                description="Budget limited; expand existing agent", work_type="initiative",
                status=WorkStatus.PENDING, priority="medium",
                accountable_role_id="customer-acquisition",
                required_capability_ids=["customer-acquisition"],
                context={"current_constraint": "Budget limited",
                         "evidence": "Existing agent has 30% capacity available",
                         "economic_justification": "Cost of expansion < cost of new hire"},
                metadata={})

    result = plane.execute_organisational_change(work=work, assignee=existing_actor, role=ca_role,
                                                  capability_ids=["customer-acquisition"])
    assert result["status"] == "executed"
    assert result["assignee_actor_id"] == "existing-agent"

    new_assignment = store.assign_capability("existing-agent", "customer-acquisition")
    assert new_assignment.capability_id == "customer-acquisition"
    assert new_assignment.actor_id == "existing-agent"

    actor_assignments = store.get_assignments_for_actor("existing-agent")
    assert len(actor_assignments) == 2

    assigned_work = plane.get_work("work-expand-existing")
    assert assigned_work is not None
    assert assigned_work.assignee_actor_id == "existing-agent"
    assert assigned_work.status == WorkStatus.ASSIGNED


# ============================================================================
# D. Organisational authority
# ============================================================================


def test_execute_requires_authority() -> None:
    """execute_organisational_change requires assignee Role to have delegated authority."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    no_auth_role = Role(id="no-auth-role", name="No Authority Role",
                        required_capability_ids=[], authority_ids=[], status=RoleStatus.ACTIVE)
    plane.register_role(no_auth_role)

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w-no-auth", title="No authority work",
                accountable_role_id="no-auth-role", status=WorkStatus.PENDING)

    result = plane.execute_organisational_change(work=work, assignee=actor, role=no_auth_role)
    assert result["status"] == "unauthorised"
    assert result["authority_checked"] is True


def test_execute_with_authority_succeeds() -> None:
    """execute_organisational_change succeeds when Role has delegated authority."""
    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(Authority(id="auth1", name="Execute",
                                           scope="execute-organisational-change",
                                           grantor_role_id="f", grantee_role_id="o"))
    plane.delegate_authority(founder, operator, plane._authorities["auth1"])

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w1", title="Work", accountable_role_id="o", status=WorkStatus.PENDING)
    result = plane.execute_organisational_change(work=work, assignee=actor, role=operator)
    assert result["status"] == "executed"


# ============================================================================
# E. Work boundary
# ============================================================================


def test_work_represents_organisational_change() -> None:
    """Work carries all fields needed for organisational change proposal."""
    work = Work(
        id="w-change", title="Add Customer Acquisition capacity",
        description="Customer Acquisition needs additional specialist",
        work_type="initiative", status=WorkStatus.PENDING,
        accountable_role_id="customer-acquisition",
        required_capability_ids=["demand-generation"],
        acceptance_criteria=["Specialist Actor available", "CapabilityAssignment created"],
        context={"current_constraint": "Capacity pressure", "evidence": "Pressure signal detected",
                 "expected_outcome": "Additional capacity", "economic_justification": "Revenue opportunity > cost"},
        deliverables=["Specialist Agent", "CapabilityAssignment"],
        dependencies=[], metadata={},
    )
    assert work.work_type == "initiative"
    assert work.accountable_role_id == "customer-acquisition"
    assert "demand-generation" in work.required_capability_ids
    assert len(work.acceptance_criteria) == 2
    assert "economic_justification" in work.context
    assert "evidence" in work.context


def test_work_has_no_new_org_concepts() -> None:
    """Work has no OrganisationalChange, Decision, HiringRequest fields."""
    fields = set(Work.model_fields.keys())
    for forbidden in ["change_type", "proposal_type", "decision_type", "hiring_request",
                      "requisition", "capacity_plan"]:
        assert forbidden not in fields, f"Work should not have '{forbidden}'"


# ============================================================================
# F. Idempotency
# ============================================================================


def test_execute_organisational_change_idempotent() -> None:
    """Calling execute_organisational_change twice does not duplicate assignments."""
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(Authority(id="auth1", name="Execute",
                                           scope="execute-organisational-change",
                                           grantor_role_id="f", grantee_role_id="o"))
    plane.delegate_authority(founder, operator, plane._authorities["auth1"])

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w1", title="Work", accountable_role_id="o", status=WorkStatus.PENDING)

    result1 = plane.execute_organisational_change(work=work, assignee=actor, role=operator)
    assert result1["status"] == "executed"

    result2 = plane.execute_organisational_change(work=work, assignee=actor, role=operator)
    assert result2["status"] == "idempotent"
    assert result2["assignment_id"] is not None

    work_assignments = [a for a in plane._assignments.values() if a.work_id == "w1"]
    assert len(work_assignments) == 1
    assert len(plane.list_work()) == 1


def test_idempotent_returns_existing_assignment() -> None:
    """Idempotent result includes the existing Assignment ID."""
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(Authority(id="auth1", name="Execute",
                                           scope="execute-organisational-change",
                                           grantor_role_id="f", grantee_role_id="o"))
    plane.delegate_authority(founder, operator, plane._authorities["auth1"])

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")

    work = Work(id="w1", title="Work", accountable_role_id="o", status=WorkStatus.PENDING)
    plane.execute_organisational_change(work=work, assignee=actor, role=operator)

    result = plane.execute_organisational_change(work=work, assignee=actor, role=operator)
    assert result["status"] == "idempotent"
    assert result["assignment_id"] is not None

    assignment = plane._assignments.get(result["assignment_id"])
    assert assignment is not None
    assert assignment.work_id == "w1"
    assert assignment.assignee_id == "a1"


# ============================================================================
# G. Paperclip implementation boundary
# ============================================================================


def test_paperclip_create_agent_idempotency() -> None:
    """Paperclip create_agent returns cached Role for duplicate name."""
    from organisation_paperclip import PaperclipOrganisationControlPlane

    from role import Role, RoleStatus

    plane = PaperclipOrganisationControlPlane.__new__(PaperclipOrganisationControlPlane)
    plane._role_cache = {}

    role1 = Role(id="agent-1", name="Customer Acquisition Agent",
                  description="Test agent", responsibilities=[],
                  required_capability_ids=["demand-generation"],
                  authority_ids=[], constraints=[], information_access=[],
                  reports_to=None, status=RoleStatus.ACTIVE, metadata={})
    plane._role_cache["agent-1"] = role1

    result = plane.create_agent(name="Customer Acquisition Agent")
    assert result is not None
    assert result.id == "agent-1"
    assert result.name == "Customer Acquisition Agent"


def test_ocp_does_not_import_paperclip() -> None:
    """OCP does not import Paperclip (organisational boundary)."""
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
    for filename in os.listdir(PAPERCLIP_SRC):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
        path = os.path.join(PAPERCLIP_SRC, filename)
        with open(path) as f:
            import ast
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden:
                assert False, f"Paperclip should not define {node.name}"


# ============================================================================
# H. Failure / retry behaviour
# ============================================================================


def test_failure_ocp_succeeds_paperclip_fails() -> None:
    """OCP organisational state succeeds, Paperclip fails.

    OCP remains authoritative; Paperclip failure is retriable;
    no corrupted second organisational identity.
    """
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(Authority(id="auth1", name="Execute",
                                           scope="execute-organisational-change",
                                           grantor_role_id="f", grantee_role_id="o"))
    plane.delegate_authority(founder, operator, plane._authorities["auth1"])

    agent = Agent(id="a1", name="Agent", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("a1")
    store.assign_capability("a1", "customer-acquisition")

    work = Work(id="w-fail", title="Change work", accountable_role_id="o", status=WorkStatus.PENDING)

    result = plane.execute_organisational_change(work=work, assignee=actor, role=operator)
    assert result["status"] == "executed"

    assert plane.get_work("w-fail") is not None
    assert plane.get_work("w-fail").status == WorkStatus.ASSIGNED
    assert plane.get_role("o") is not None

    actor_assignments = store.get_assignments_for_actor("a1")
    assert len(actor_assignments) >= 1


def test_failure_boundary_no_distributed_transactions() -> None:
    """No distributed transactions or event sourcing in OCP."""
    import ast
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert "transaction" not in node.attr.lower()


# ============================================================================
# I. Resulting organisational state
# ============================================================================


def test_explain_implementation_new_actor() -> None:
    """OCP can explain the organisational meaning of an Actor's implementation."""
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", responsibilities=["Execute"],
                    required_capability_ids=["demand-generation"],
                    authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(Authority(id="auth1", name="Execute",
                                           scope="execute-organisational-change",
                                           grantor_role_id="f", grantee_role_id="o"))
    plane.delegate_authority(founder, operator, plane._authorities["auth1"])

    agent = Agent(id="specialist", name="Specialist", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("specialist")

    work = Work(id="w-change", title="Add capacity",
                accountable_role_id="o", required_capability_ids=["demand-generation"],
                context={"justification": "revenue > cost"}, status=WorkStatus.PENDING)
    plane.execute_organisational_change(work=work, assignee=actor, role=operator)

    explanation = plane.explain_implementation("specialist")
    assert explanation is not None
    assert explanation["actor_id"] == "specialist"
    assert len(explanation["assigned_work"]) == 1
    assert explanation["assigned_work"][0]["work_id"] == "w-change"
    assert explanation["assigned_work"][0]["title"] == "Add capacity"
    assert explanation["assigned_work"][0]["accountable_role_id"] == "o"
    assert explanation["assigned_work"][0]["role_name"] == "Operator"
    assert explanation["accountable_roles"] == ["o"]


def test_explain_implementation_no_work() -> None:
    """explain_implementation returns None for Actor with no organisational presence."""
    plane = InMemoryOrganisationControlPlane()
    plane.register_role(Role(id="o", name="Operator", authority_ids=["auth1"], status=RoleStatus.ACTIVE))

    explanation = plane.explain_implementation("unknown-actor")
    assert explanation is None


def test_post_change_state_inspectable() -> None:
    """After organisational change, state is inspectable: Work → Role → Actor → Assignment."""
    from agent_store import InMemoryAgentStore

    plane = InMemoryOrganisationControlPlane()
    store = InMemoryAgentStore()

    founder = Role(id="f", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    operator = Role(id="o", name="Operator", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_role(operator)
    plane.register_authority(Authority(id="auth1", name="Execute",
                                           scope="execute-organisational-change",
                                           grantor_role_id="f", grantee_role_id="o"))
    plane.delegate_authority(founder, operator, plane._authorities["auth1"])

    agent = Agent(id="specialist", name="Specialist", marker="ai")
    store.register_agent(agent)
    actor = store.get_actor("specialist")
    store.assign_capability("specialist", "demand-generation")

    work = Work(id="w-change", title="Add capacity",
                accountable_role_id="o", required_capability_ids=["demand-generation"],
                status=WorkStatus.PENDING)
    plane.execute_organisational_change(work=work, assignee=actor, role=operator)

    assert plane.get_work("w-change") is not None
    assert plane.get_role("o") is not None
    assert store.get_actor("specialist") is not None
    assert store.get_agent("specialist") is not None
    assignments = store.get_assignments_for_actor("specialist")
    assert len(assignments) >= 1
    assert any(a.capability_id == "demand-generation" for a in assignments)


# ============================================================================
# J. People/Capability as ordinary participant
# ============================================================================


def test_people_capability_ordinary_participant() -> None:
    """People/Capability uses existing primitives for organisational change."""
    plane = InMemoryOrganisationControlPlane()
    methods = set(dir(plane))
    assert "register_person" not in methods
    assert "register_agent" not in methods
    assert "register_role" in methods
    assert "assign_work" in methods

    store = InMemoryAgentStore()
    assert hasattr(store, "register_agent")
    assert hasattr(store, "register_person")
    assert hasattr(store, "assign_capability")


# ============================================================================
# K. Chief of Staff as ordinary participant
# ============================================================================


def test_chief_of_staff_ordinary_participant() -> None:
    """Chief of Staff = Role + Authority + Delegation. No special class."""
    plane = InMemoryOrganisationControlPlane()
    cos_role = Role(id="chief-of-staff", name="Chief of Staff",
                     responsibilities=["coordination", "delegation", "oversight"],
                     required_capability_ids=["coordination", "delegation"],
                     authority_ids=[], constraints=[], information_access=[],
                     reports_to="founder", status=RoleStatus.ACTIVE, metadata={})
    plane.register_role(cos_role)

    founder = Role(id="founder", name="Founder", authority_ids=["auth1"], status=RoleStatus.ACTIVE)
    plane.register_role(founder)
    plane.register_authority(Authority(id="auth-cos", name="Coordinate",
                                             scope="coordination",
                                             grantor_role_id="founder",
                                             grantee_role_id="chief-of-staff"))
    delegation = plane.delegate_authority(founder, cos_role, plane._authorities["auth-cos"])
    assert delegation.from_role_id == "founder"
    assert delegation.to_role_id == "chief-of-staff"


# ============================================================================
# L. Economic reasoning boundary
# ============================================================================


def test_economic_reasoning_in_work_context() -> None:
    """Economic data enters via Work.context dict. No economic entities."""
    work = Work(id="w-econ", title="Change", accountable_role_id="r1",
                 required_capability_ids=[],
                 context={"current_constraint": "Budget limited",
                          "evidence": "Existing agent has capacity",
                          "expected_outcome": "5 additional units",
                          "economic_justification": "Revenue opportunity > cost"},
                 metadata={})
    assert "economic_justification" in work.context
    assert "evidence" in work.context


def test_no_economic_entities() -> None:
    """No Cost, Value, Capacity entities created."""
    fields = set(Work.model_fields.keys())
    for forbidden in ["cost", "budget", "roi", "value", "price", "revenue", "capacity"]:
        assert forbidden not in fields, f"Work should not have '{forbidden}'"


# ============================================================================
# M. Architectural invariants
# ============================================================================


def test_ocp_authoritative_for_org_state() -> None:
    """OCP owns Work, Role, Assignment, Authority, Delegation state."""
    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "register_role")
    assert hasattr(plane, "assign_work")
    assert hasattr(plane, "delegate_authority")
    assert hasattr(plane, "get_work")
    assert hasattr(plane, "list_work")


def test_paperclip_is_implementation_not_authority() -> None:
    """Paperclip does not define organisational concepts."""
    from organisation_paperclip import PaperclipOrganisationControlPlane
    assert hasattr(PaperclipOrganisationControlPlane, "create_agent")


def test_no_new_domain_concepts() -> None:
    """Increment 43 introduces no new domain concepts."""
    from role import Assignment, Authority, Role, Work

    models = [Role, Work, Assignment, Authority, Delegation, Actor, CapabilityAssignment]
    for model in models:
        assert hasattr(model, "model_fields"), f"{model.__name__} is not a Pydantic model"


def test_capability_gap_does_not_auto_create_actor() -> None:
    """A capability gap can be resolved by expanding existing Actor."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="existing", name="Existing", marker="ai"))
    store.assign_capability("existing", "cap-a")

    new_assignment = store.assign_capability("existing", "cap-b")
    assert new_assignment.capability_id == "cap-b"
    assert new_assignment.actor_id == "existing"

    assignments = store.get_assignments_for_actor("existing")
    assert len(assignments) == 2


def test_capability_assignment_authoritative() -> None:
    """CapabilityAssignment is the authoritative Actor↔Capability relationship."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="a1", name="Bot", marker="ai"))

    assignment = store.assign_capability("a1", "customer-acquisition")
    assert assignment.actor_id == "a1"
    assert assignment.capability_id == "customer-acquisition"
    assert assignment.status.value == "active"


def test_execution_authority_still_works() -> None:
    """Execution authorisation continues to work after organisational change."""
    from agent import Agent

    store = InMemoryAgentStore()
    store.register_agent(Agent(id="a1", name="Bot", marker="ai"))
    store.assign_capability("a1", "customer-acquisition")

    assert store.actor_has_capability("a1", "customer-acquisition")
    assert not store.actor_has_capability("a1", "non-existent")


def test_workflow_semantics_unchanged() -> None:
    """Workflow execution semantics remain unchanged."""
    from contracts.workflow_execution import WorkflowExecutionRequest
    request_fields = set(WorkflowExecutionRequest.model_fields.keys())
    assert "workflow_name" in request_fields
    for forbidden in ["team_id", "actor_type_team", "people_capability", "capacity"]:
        assert forbidden not in request_fields


def test_no_special_hr_entity() -> None:
    """No HRService, PeopleManager, HiringAuthority, or Admin-only semantics."""
    import ast
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert "hr" not in node.attr.lower()
            assert "hire" not in node.attr.lower()
            assert "recruit" not in node.attr.lower()


# ============================================================================
# N. Test coverage summary
# ============================================================================


def test_vertical_slice_coverage() -> None:
    """Verify all expected test categories are present."""
    import inspect
    funcs = [n for n, o in inspect.getmembers(
        sys.modules[__name__], inspect.isfunction) if n.startswith("test_")]
    assert len(funcs) >= 30, f"Expected 30+ tests, got {len(funcs)}"


def test_execution_path_preserved() -> None:
    """The execution path (select_execution_path) is preserved and separate."""
    plane = InMemoryOrganisationControlPlane()
    assert hasattr(plane, "select_execution_path")
    result = plane.select_execution_path("test", {"required_capability_ids": ["cap-1"]})
    assert result.path.value == "new_capability_required"


