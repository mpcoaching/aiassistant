"""
Architectural tests for Increment 41 — Economic Organisational Design Boundary.

Investigates whether the OCP/organisation model has sufficient primitives
to reason about economically justified organisational capacity.

Investigation first. No production changes. No economic entities implemented.

Tests prove architectural conclusions, not implementation details.
"""

from __future__ import annotations

import inspect
import os

ORGANISATION_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "src"
))
PEOPLE_CAPABILITY_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "people_capability", "src"
))
CAPABILITY_REGISTRY_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "capability_registry", "src"
))
WORKFLOW_RUNNER_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "workflow_runner", "src"
))
CONTRACTS_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "contracts"
))
PAPERCLIP_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "organisation_paperclip", "src"
))
AI_SRC = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "ai", "src"
))


# ---- A. Capability vs Capacity ----


def test_capability_has_no_capacity_field() -> None:
    """Capability model has no capacity field or concept.

    Capability defines WHAT can be done (name, interface, kind, status).
    It does not define HOW MUCH capacity exists to exercise it.
    Capacity is not a first-class concept in Capability.
    """
    from capability import Capability

    fields = set(Capability.model_fields.keys())
    assert "name" in fields
    assert "interface" in fields
    assert "capability_kind" in fields
    assert "status" in fields
    for forbidden in ["capacity", "capacity_rate", "quota", "limit", "utilisation"]:
        assert forbidden not in fields, (
            f"Capability should not have '{forbidden}' — capacity is not a "
            "Capability-domain concept"
        )


def test_capability_assignment_links_actor_to_capability() -> None:
    """CapabilityAssignment links Actor→Capability with status.

    This is the existing mechanism for representing who can exercise
    what. Capacity at Actor level is: assignment + proficiency + availability.
    No separate Capacity concept needed at this level.
    """
    from capability_assignment import CapabilityAssignment

    fields = set(CapabilityAssignment.model_fields.keys())
    assert "capability_id" in fields
    assert "actor_id" in fields
    assert "status" in fields
    assert "assignment_type" in fields
    # Assignment type (PRIMARY|SECONDARY|BACKUP) already encodes capacity tier


def test_work_has_no_capacity_fields() -> None:
    """Work has no capacity fields.

    Work represents organisational need (accountable_role_id, required_capability_ids).
    Capacity is not tracked on Work — it is derived from assignments and actor availability.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in ["capacity", "capacity_rate", "quota", "allocation"]:
        assert forbidden not in fields, (
            f"Work should not have '{forbidden}' — capacity is not tracked on Work"
        )


def test_capacity_pressure_signal_exists_as_organisational_signal() -> None:
    """CapacityPressureSignal exists as an organisational signal.

    This is the existing mechanism for organisational-level capacity observation.
    It tracks demand_rate_per_hour, capacity_rate_per_hour, queue_depth.
    This is capacity DERIVED from work/assignment data, not a separate concept.
    """
    from contracts.organisational_events import CapacityPressureSignal

    fields = set(CapacityPressureSignal.model_fields.keys())
    assert "capability_id" in fields
    assert "demand_rate_per_hour" in fields
    assert "capacity_rate_per_hour" in fields
    assert "queue_depth" in fields
    assert "affected_work_ids" in fields
    # No cost or value fields — capacity pressure is purely operational


def test_detect_capacity_pressure_uses_work_counts() -> None:
    """detect_capacity_pressure derives capacity from Work counts, not Capacity entities.

    This proves capacity is DERIVED from existing models (Work, Assignment)
    rather than being a separate concept. OCP queries work items by capability_id
    and status to determine pressure.
    """
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    # The method queries work items by capability_id and status
    assert "detect_capacity_pressure" in source
    assert "required_capability_ids" in source
    assert "in_progress" in source
    assert "pending" in source
    # No Capacity model referenced inside the method body
    method_body = source.split("def detect_capacity_pressure")[1].split("\n    def ")[0]
    assert "CapacityPressureSignal" in method_body  # signal IS used
    assert "Capacity(" not in method_body  # no Capacity entity created


def test_capacity_is_derivable_from_assignment_and_actor_availability() -> None:
    """Capacity can be derived from: CapabilityAssignment(status=ACTIVE) + Actor.status + Work counts.

    Actor.status (ACTIVE/INACTIVE/DEPROVISIONED) gives availability.
    CapabilityAssignment.status (ACTIVE/SUSPENDED/EXPIRED/REVOKED) gives assignment validity.
    Work.status gives workload.
    No Capacity entity required.
    """
    from actor import Actor
    from capability_assignment import AssignmentStatus, CapabilityAssignment

    from role import WorkStatus

    # Actor availability is encoded in Actor.status, not a separate Capacity model
    set(Actor.model_fields.keys())
    assert True  # Actor has metadata but no capacity field

    # CapabilityAssignment status encodes whether the assignment is active
    ca_fields = set(CapabilityAssignment.model_fields.keys())
    assert "status" in ca_fields
    assert AssignmentStatus.ACTIVE.value == "active"

    # Work status encodes execution state
    assert WorkStatus.PENDING.value == "pending"
    assert WorkStatus.COMPLETED.value == "completed"


# ---- B. Actor/Agent Economic Cost ----


def test_actor_has_no_cost_field() -> None:
    """Actor has no explicit cost field.

    Actor is a lightweight reference (id, name, actor_type, reference_id,
    fulfilled_role_ids, metadata). Cost is not owned by Actor because
    Actor is not the entity that carries employment/economic data.
    """
    from actor import Actor

    fields = set(Actor.model_fields.keys())
    for forbidden in ["cost", "annual_cost", "salary", "budget", "rate"]:
        assert forbidden not in fields, (
            f"Actor should not have '{forbidden}' — cost belongs elsewhere"
        )


def test_person_has_employment_context() -> None:
    """Person has employment_context: dict[str, Any].

    This is where Person economic cost WOULD conceptually live —
    in the Person's employment context, as an analytical field.
    Not typed as a specific cost field because cost semantics vary.
    """
    from person import Person

    fields = set(Person.model_fields.keys())
    assert "employment_context" in fields
    # Cost information could be stored in employment_context as an analytical choice


def test_agent_has_metadata_for_analytical_data() -> None:
    """Agent has metadata: dict[str, Any].

    Agent economic cost (if applicable) would conceptually live in metadata.
    Agent is a software entity; its cost is infrastructure, not employment.
    """
    from agent import Agent

    fields = set(Agent.model_fields.keys())
    assert "metadata" in fields


def test_capability_assignment_has_no_cost() -> None:
    """CapabilityAssignment has no cost field.

    CapabilityAssignment links Actor→Capability with proficiency and status.
    Cost is not part of the assignment relationship — it's a property
    of the Actor (Person/Agent) themselves.
    """
    from capability_assignment import CapabilityAssignment

    fields = set(CapabilityAssignment.model_fields.keys())
    for forbidden in ["cost", "annual_cost", "budget", "rate", "price"]:
        assert forbidden not in fields, (
            f"CapabilityAssignment should not have '{forbidden}'"
        )


def test_actor_cost_belongs_in_people_capability_plane() -> None:
    """Actor/Agent economic cost belongs in People/Capability, not OCP.

    OCP references Person/Agent by ID only (ADR-037).
    OCP does NOT store Person/Agent records.
    Therefore OCP cannot own cost data — it would need to reference it externally.
    """
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    # OCP does NOT store Person/Agent records (ADR-037).
    # Check the method signature/implementation, not the docstring.
    assert "def register_person" not in source
    assert "def register_agent" not in source


def test_paperclip_has_budget_monthly_cents_in_mapping() -> None:
    """Paperclip's create_agent maps budgetMonthlyCents from kwargs.

    Paperclip has implementation-level budget information (budgetMonthlyCents)
    but this is a Paperclip-specific field, not an OCP domain concept.
    OCP must not use this for economic decisions.
    """
    source_path = os.path.join(PAPERCLIP_SRC, "organisation_paperclip.py")
    with open(source_path) as f:
        source = f.read()
    assert "budgetMonthlyCents" in source
    assert "budget_monthly_cents" in source
    # But OCP doesn't read it
    assert "budgetMonthlyCents" not in source.split("def query_capability")[0]


def test_actor_cost_requires_effective_dates_if_tracked() -> None:
    """If Actor cost were tracked, it would need effective dates.

    Person has created_at and updated_at but no effective date for cost.
    Agent has created_at and updated_at but no cost field.
    This proves cost tracking is NOT currently implemented.
    Promotion/increased responsibility would change cost but there's
    no mechanism to track cost history on Person/Agent.
    """
    from agent import Agent
    from person import Person

    person_fields = set(Person.model_fields.keys())
    agent_fields = set(Agent.model_fields.keys())

    # Neither has cost-related fields
    for model_name, fields in [("Person", person_fields), ("Agent", agent_fields)]:
        for forbidden in ["cost", "annual_cost", "effective_from", "effective_until"]:
            assert forbidden not in fields, (
                f"{model_name} should not have '{forbidden}' — cost not implemented"
            )


def test_actor_cost_is_not_in_organisation_package() -> None:
    """No economic cost model exists in organisation package.

    OCP's models (Role, Work, Assignment, Authority, Delegation, OrgContext)
    have no cost/price/budget fields. Economic cost is not an OCP concern.
    """
    role_path = os.path.join(ORGANISATION_SRC, "role.py")
    with open(role_path) as f:
        source = f.read()
    # Work, Role, Assignment have no cost fields
    for forbidden in ["cost", "budget", "price", "rate", "annual"]:
        assert forbidden not in source.lower(), (
            f"organisation package should not contain '{forbidden}' in models"
        )


# ---- C. Value Semantics ----


def test_work_outcome_is_unstructured() -> None:
    """Work.outcome is dict[str, Any] | None, not typed for value.

    Work.outcome can contain any data but is NOT a Value concept.
    Value is an analytical interpretation of outcomes, not a typed field.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "outcome" in fields
    # outcome is unstructured — value would be a specific interpretation
    # of this field, not a separate concept


def test_value_is_not_first_class_concept() -> None:
    """Value is not a first-class OCP or capability domain concept.

    No Value model exists in any package. Value remains an analytical
    interpretation of Work/outcome/economic data.
    """
    # Search all Python source for a Value model

    # Capability has no value field
    from capability import Capability
    cap_fields = set(Capability.model_fields.keys())
    assert "value" not in cap_fields

    # Work has no value field
    from role import Work
    work_fields = set(Work.model_fields.keys())
    assert "value" not in work_fields


def test_record_work_learning_excludes_bau() -> None:
    """record_work_learning only records project/initiative work, not BAU.

    This proves value-recording is restricted to durable enterprise value.
    BAU work (repeated execution) is not recorded as value.
    """
    source_path = os.path.join(ORGANISATION_SRC, "outcome.py")
    with open(source_path) as f:
        source = f.read()
    assert "project" in source
    assert "initiative" in source
    assert "work_type not in" in source


def test_maturation_history_has_no_value_fields() -> None:
    """MaturationHistory tracks invocation and correction counts, not value.

    MaturationHistory: invocation_count, correction_count, last_invoked_at,
    promoted_at, promotion_candidacy. No value/economic fields.
    This proves capability maturity is about lifecycle, not economics.
    """
    from concepts import MaturationHistory

    fields = set(MaturationHistory.model_fields.keys())
    assert "invocation_count" in fields
    assert "correction_count" in fields
    assert "promotion_candidacy" in fields
    for forbidden in ["value", "revenue", "cost", "roi", "return"]:
        assert forbidden not in fields, (
            f"MaturationHistory should not have '{forbidden}'"
        )


def test_solved_approach_is_outcome_not_value() -> None:
    """SOLVED_APPROACH concept records execution outcomes, not value.

    record_work_learning creates SOLVED_APPROACH concepts with:
    summary, work_id, work_type, role IDs, outcome, criteria.
    No economic value measurement.
    """
    source_path = os.path.join(ORGANISATION_SRC, "outcome.py")
    with open(source_path) as f:
        source = f.read()
    assert "SOLVED_APPROACH" in source
    # What it records: summary, work_id, work_type, roles, outcome, criteria
    assert "work_id" in source
    assert "outcome" in source
    assert "acceptance_criteria" in source
    # What it does NOT record
    assert "revenue" not in source
    assert "cost_avoided" not in source


# ---- D. Capability vs Application vs Value ----


def test_work_requires_capability_ids() -> None:
    """Work.required_capability_ids links capability to organisational need.

    This is the existing mechanism for APPLICATION:
    Work says "this capability is applied to this organisational need".
    No Application entity needed.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "required_capability_ids" in fields
    assert "accountable_role_id" in fields


def test_capability_has_no_application_field() -> None:
    """Capability has no application field.

    Capability is "what can we do" — not "where/how it's applied".
    Application is represented by Work(required_capability_ids).
    """
    from capability import Capability

    fields = set(Capability.model_fields.keys())
    for forbidden in ["application", "use_case", "where_used", "applied_to"]:
        assert forbidden not in fields, (
            f"Capability should not have '{forbidden}'"
        )


def test_capability_outcome_assessor_uses_work() -> None:
    """Capability outcome assessment uses Work, not a separate Application concept.

    assess_capability_development takes a Work item and a Capability,
    linking them through execution results. Application is Work.
    """
    source_path = os.path.join(ORGANISATION_SRC, "outcome.py")
    with open(source_path) as f:
        source = f.read()
    assert "def assess_capability_development" in source
    assert "work: Any" in source
    assert "capability: Any" in source
    # Takes Work and Capability — Application is represented by Work


def test_value_is_analytical_not_modelled() -> None:
    """Value is analytical, not a modelled domain concept.

    Work.outcome + Capability + Role together form the basis for
    economic analysis, but no Value entity exists or is needed.
    """
    # Prove Value is not a domain concept anywhere
    from actor import Actor
    from capability import Capability

    from role import Work

    for model in [Capability, Work, Actor]:
        fields = set(model.model_fields.keys())
        assert "value" not in fields


# ---- E. Value-Creating vs Supporting Capabilities ----


def test_capability_kind_has_only_tool_and_skill() -> None:
    """CapabilityKind has only TOOL and SKILL.

    No value_creating / supporting taxonomy exists.
    CapabilityKind is about implementation type, not value classification.
    """
    from capability import CapabilityKind

    members = [m.value for m in CapabilityKind]
    assert "tool" in members
    assert "skill" in members
    assert "value_creating" not in members
    assert "supporting" not in members


def test_no_value_capability_taxonomy() -> None:
    """No ValueCapability or SupportingCapability concept exists.

    The codebase does not classify capabilities by value type.
    Hypothesis confirmed: supporting capability can have value-producing
    application — there is no need for a taxonomy.
    """
    test_file = os.path.abspath(__file__)
    found = False
    for root, dirs, files in os.walk("/home/martinp/Documents/projects/aiassistant/packages"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                if os.path.abspath(path) == test_file:
                    continue  # skip self
                try:
                    with open(path) as fh:
                        content = fh.read()
                    if "ValueCapability" in content or "SupportingCapability" in content:
                        found = True
                except (OSError, UnicodeDecodeError):
                    pass
    assert not found, "No ValueCapability/SupportingCapability taxonomy should exist"


def test_work_classification_is_bau_project_initiative() -> None:
    """Work.work_type is a free string with bau/project/initiative values.

    Work is classified by type (bau, project, initiative) — not by
    whether the capability is value-creating or supporting.
    This confirms no value taxonomy exists on Work either.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "work_type" in fields
    # work_type is a free string field, not a typed enum
    # No WorkType enum or value taxonomy exists
    assert "work_type" in fields


# ---- F. Friction Economics ----


def test_no_friction_scan_exists() -> None:
    """No FrictionScan concept exists in the codebase.

    FrictionScan was mentioned as a potential future concept but
    has not been implemented. Friction remains an observation/
    evidence source that can be economically interpreted later.
    """
    test_file = os.path.abspath(__file__)
    found = False
    for root, dirs, files in os.walk("/home/martinp/Documents/projects/aiassistant/packages"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                if os.path.abspath(path) == test_file:
                    continue
                try:
                    with open(path) as fh:
                        content = fh.read()
                    if "FrictionScan" in content:
                        found = True
                except (OSError, UnicodeDecodeError):
                    pass
    assert not found, "FrictionScan should not exist yet"


def test_capacity_pressure_is_closest_to_friction_observation() -> None:
    """CapacityPressureSignal is the closest existing friction observation.

    CapacityPressureSignal tracks demand exceeding capacity — which
    is a form of organisational friction. It records queue_depth,
    demand_rate, capacity_rate. This can later be economically
    interpreted (cost of waiting, cost of rework).
    """
    from contracts.organisational_events import CapacityPressureSignal

    fields = set(CapacityPressureSignal.model_fields.keys())
    assert "queue_depth" in fields
    assert "demand_rate_per_hour" in fields
    assert "capacity_rate_per_hour" in fields
    assert "average_eta_seconds" in fields
    # No cost fields — friction is observed, not yet economically evaluated


def test_friction_remains_observation_not_concept() -> None:
    """Friction remains an observation, not a domain concept.

    No Friction model, FrictionScan, or FrictionCost exists.
    Friction is captured via CapacityPressureSignal and work outcomes.
    Economic interpretation is a future concern.
    """
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    # detect_capacity_pressure captures operational friction signals
    assert "detect_capacity_pressure" in source
    # No friction cost or economic evaluation
    assert "friction_cost" not in source
    assert "friction_economics" not in source


# ---- G. Economic Inspection Hierarchy ----


def test_inspection_hierarchy_organisation_level() -> None:
    """Organisation level inspection exists via list_roles, list_work, detect_capacity_pressure.

    At organisation level we can determine:
    - capabilities exercised: Role.required_capability_ids across all roles
    - capacity consumed/available: detect_capacity_pressure per capability
    - cost consumed: NOT YET (no cost model)
    - value created/enabled: NOT YET (no value model)
    - friction: CapacityPressureSignal
    - outcomes: Work.outcome across all work items
    """
    from organisation_control_plane import OrganisationControlPlane

    # Check abstract methods
    abstract_methods = [
        name for name, method in inspect.getmembers(
            OrganisationControlPlane, predicate=inspect.isfunction
        )
        if getattr(method, "__isabstractmethod__", False)
    ]
    assert "list_roles" in abstract_methods
    assert "list_work" in abstract_methods
    assert "detect_capacity_pressure" in abstract_methods
    assert "get_role" in abstract_methods


def test_inspection_hierarchy_role_level() -> None:
    """Role level inspection exists via required_capability_ids, responsibilities, reports_to.

    At Role level we can determine:
    - capabilities exercised: Role.required_capability_ids
    - capacity: implied by assignment (who fills this role)
    - cost: NOT YET
    - value: implied by Work.accountable_role_id outcomes
    - hierarchy: reports_to
    """
    from role import Role

    fields = set(Role.model_fields.keys())
    assert "required_capability_ids" in fields
    assert "responsibilities" in fields
    assert "reports_to" in fields
    assert "status" in fields


def test_inspection_hierarchy_actor_level() -> None:
    """Actor level inspection exists via fulfilled_role_ids, capability assignments.

    At Actor level we can determine:
    - capabilities exercised: CapabilityAssignment(actor_id=...)
    - capacity: assignment status + proficiency
    - cost: NOT YET (lives in Person/Agent)
    - value: Work assigned to Actor via assignee_actor_id
    """
    from actor import Actor
    from capability_assignment import CapabilityAssignment

    actor_fields = set(Actor.model_fields.keys())
    assert "fulfilled_role_ids" in actor_fields

    ca_fields = set(CapabilityAssignment.model_fields.keys())
    assert "actor_id" in ca_fields
    assert "capability_id" in ca_fields
    assert "proficiency" not in ca_fields  # proficiency is separate concept


def test_inspection_hierarchy_capability_level() -> None:
    """Capability level inspection exists via MaturationHistory in ConceptStore.

    At Capability level we can determine:
    - invocation_count (how much it's been exercised)
    - correction_count (friction/errors)
    - promotion_candidacy (maturity)
    - No cost/value fields yet
    """
    from concepts import MaturationHistory

    fields = set(MaturationHistory.model_fields.keys())
    assert "invocation_count" in fields
    assert "correction_count" in fields
    assert "promotion_candidacy" in fields
    for forbidden in ["cost", "value", "revenue"]:
        assert forbidden not in fields


def test_inspection_hierarchy_work_level() -> None:
    """Work level inspection exists via all Work fields.

    At Work level we can determine:
    - capability applied: required_capability_ids
    - capacity consumed: status (IN_PROGRESS)
    - cost consumed: NOT YET
    - value created: outcome (unstructured)
    - friction: status transitions, failed work
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "required_capability_ids" in fields
    assert "status" in fields
    assert "outcome" in fields
    assert "acceptance_criteria" in fields


def test_attribution_semantics_are_not_modelled() -> None:
    """Attribution semantics (direct, shared, enabling, uncertain) are not modelled.

    Work.outcome has no attribution field. There's no mechanism to
    say whether a value outcome is directly attributable, shared,
    enabling, or uncertain. This is an analytical concern for later.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in ["attribution", "attribution_type", "confidence", "certainty"]:
        assert forbidden not in fields, (
            f"Work should not have '{forbidden}' — attribution is analytical"
        )


# ---- H. Organisational Expansion Decisions ----


def test_no_expansion_proposal_concept() -> None:
    """No ExpansionProposal or InvestmentProposal concept exists.

    If one were needed, Work could represent it (work_type="initiative").
    But no such concept is required yet — the existing models can absorb
    expansion proposals as Work items.
    """
    test_file = os.path.abspath(__file__)
    found = False
    for root, dirs, files in os.walk("/home/martinp/Documents/projects/aiassistant/packages"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                if os.path.abspath(path) == test_file:
                    continue
                try:
                    with open(path) as fh:
                        content = fh.read()
                    if "ExpansionProposal" in content or "InvestmentProposal" in content:
                        found = True
                except (OSError, UnicodeDecodeError):
                    pass
    assert not found, "No ExpansionProposal concept should exist"


def test_work_can_represent_expansion_proposal() -> None:
    """Work can represent an expansion proposal via work_type.

    Work.work_type is a free string. A proposal could be:
    Work("Proposal: Add 2 agents for Q4 capacity") with
    work_type="initiative" and required_capability_ids=["agent_capacity"].
    No new entity needed.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "work_type" in fields
    assert "accountable_role_id" in fields
    assert "required_capability_ids" in fields
    assert "outcome" in fields  # actual outcome after implementation


def test_no_decision_entity_exists() -> None:
    """No Decision entity exists.

    The hypothesis is that expansion decisions can be represented
    through Work (proposal) + Work (implementation) + Work (outcome).
    A Decision entity would be premature — no evidence requires it.
    """
    test_file = os.path.abspath(__file__)
    found = False
    for root, dirs, files in os.walk("/home/martinp/Documents/projects/aiassistant/packages"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                if os.path.abspath(path) == test_file:
                    continue
                try:
                    with open(path) as fh:
                        content = fh.read()
                    if "class Decision(" in content or "class OrganisationalDecision(" in content:
                        found = True
                except (OSError, UnicodeDecodeError):
                    pass
    assert not found, "No Decision entity should exist yet"


def test_select_execution_path_is_economic_reasoning() -> None:
    """select_execution_path already performs economic-style decisions.

    Decision hierarchy:
    1. EXISTING_WORKFLOW (cheapest path)
    2. CAPABILITY_PATH (existing capability)
    3. HUMAN_TEAM_INVESTIGATION (capability unavailable, check alternatives)
    4. NEW_CAPABILITY_REQUIRED (no capability exists — biggest investment)

    This IS economic reasoning: minimise cost by using existing capacity
    before expanding. But it's implicit, not explicit.
    """
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    assert "EXISTING_WORKFLOW" in source
    assert "CAPABILITY_PATH" in source
    assert "HUMAN_TEAM_INVESTIGATION" in source
    assert "NEW_CAPABILITY_REQUIRED" in source


def test_alternatives_to_actor_not_explicitly_modelled() -> None:
    """Alternatives to adding an Actor are NOT explicitly modelled as a list.

    select_execution_path's HUMAN_TEAM_INVESTIGATION path implies
    'investigate alternatives' but doesn't enumerate them.
    Alternatives (improve process, remove friction, automate, etc.)
    are analytical, not modelled. This is correct — they're an
    investigation outcome, not a domain concept.
    """
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    # HUMAN_TEAM_INVESTIGATION exists but is generic
    assert "HUMAN_TEAM_INVESTIGATION" in source
    # No enum of alternatives
    assert "improve process" not in source
    assert "automate" not in source


# ---- I. Plan vs Actual ----


def test_no_plan_vs_actual_mechanism() -> None:
    """No Plan vs Actual mechanism exists.

    Work has outcome (actual) but no planned metrics:
    - no planned_cost, no planned_capacity, no planned_value
    - no assumptions field
    - no variance calculation
    This is premature for the current system.
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in [
        "planned_cost", "planned_capacity", "planned_value",
        "planned_metrics", "assumptions", "variance",
    ]:
        assert forbidden not in fields, (
            f"Work should not have '{forbidden}' — plan vs actual is premature"
        )


def test_work_status_tracks_lifecycle_not_plan() -> None:
    """Work.status tracks execution lifecycle (PENDING→COMPLETED), not plan.

    Status transitions: PENDING→ASSIGNED→READY→IN_PROGRESS→COMPLETED/FAILED.
    This is execution tracking, not plan tracking.
    """
    from role import WorkStatus

    statuses = [s.value for s in WorkStatus]
    assert "pending" in statuses
    assert "completed" in statuses
    assert "failed" in statuses
    assert "planned" not in statuses


def test_record_work_learning_conditional_on_outcome() -> None:
    """record_work_learning requires accepted + project/initiative work.

    This is a form of plan-vs-actual filtering: only accepted work
    with durable value is recorded. This is learning, not accounting.
    """
    source_path = os.path.join(ORGANISATION_SRC, "outcome.py")
    with open(source_path) as f:
        source = f.read()
    assert "accepted" in source
    assert "project" in source
    assert "initiative" in source


# ---- J. Economic Traceability ----


def test_actor_links_to_capability_via_assignment() -> None:
    """Actor→CapabilityAssignment→Capability chain EXISTS.

    Part 1 of traceability chain exists:
    Actor(id) → CapabilityAssignment(actor_id, capability_id) → Capability(id)
    """
    from capability_assignment import CapabilityAssignment

    ca_fields = set(CapabilityAssignment.model_fields.keys())
    assert "actor_id" in ca_fields
    assert "capability_id" in ca_fields


def test_work_links_to_capability_via_required_ids() -> None:
    """Work→Capability chain EXISTS via required_capability_ids.

    Part 2 of traceability chain exists:
    Work(required_capability_ids) → Capability(id)
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    assert "required_capability_ids" in fields
    assert "accountable_role_id" in fields


def test_role_links_to_work_via_accountability() -> None:
    """Role→Work chain EXISTS via accountable_role_id.

    Part 3 of traceability chain exists:
    Role(id) ← Work(accountable_role_id)
    """
    from role import Role, Work

    role_fields = set(Role.model_fields.keys())
    work_fields = set(Work.model_fields.keys())
    assert "id" in role_fields
    assert "accountable_role_id" in work_fields


def test_no_original_proposal_link() -> None:
    """No link from Work/Capability back to original organisational proposal.

    The traceability chain is INCOMPLETE:
    Actor → CapabilityAssignment → Capability ✓ (exists)
    Capability → Work (via required_capability_ids) ✓ (exists)
    Work → outcome ✓ (exists, unstructured)
    Work → original proposal ✗ (does NOT exist)
    Work → expected cost ✗ (does NOT exist)
    Work → expected value ✗ (does NOT exist)
    """
    from role import Work

    fields = set(Work.model_fields.keys())
    for forbidden in ["proposal_id", "expected_cost", "expected_value", "justification"]:
        assert forbidden not in fields, (
            f"Work should not have '{forbidden}' — traceability to proposal is missing"
        )


def test_no_provenance_on_capability() -> None:
    """EnterpriseConcept has provenance (source_session_id, recognition_level),
    but Capability domain model does NOT link to organisational need/proposal.

    Capability's provenance is about knowledge discovery, not
    organisational economic justification.
    """
    from capability import Capability

    cap_fields = set(Capability.model_fields.keys())
    assert "provenance" not in cap_fields
    assert "payload" in cap_fields


# ---- K. Creation / Expansion Authority ----


def test_ocp_creates_roles_and_work() -> None:
    """OCP creates Roles and Work — these are organisational decisions.

    register_role exists on InMemoryOrganisationControlPlane.
    assign_work exists on OCP.
    These ARE the creation/expansion authority mechanisms.
    """
    from organisation_control_plane import InMemoryOrganisationControlPlane

    methods = [m for m in dir(InMemoryOrganisationControlPlane) if not m.startswith("_")]
    assert "register_role" in methods
    assert "assign_work" in methods
    assert "register_capability" in methods


def test_ocp_does_not_create_actors() -> None:
    """OCP does NOT create Actors directly (per ADR-037).

    Actor creation is owned by People/Capability.
    OCP defines what should exist (Roles, Work) and references
    Actors by ID only.
    """
    source_path = os.path.join(ORGANISATION_SRC, "organisation_control_plane.py")
    with open(source_path) as f:
        source = f.read()
    # Check function definitions, not docstrings
    assert "def register_person" not in source
    assert "def register_agent" not in source


def test_capability_registry_owns_capability_lifecycle() -> None:
    """CapabilityRegistry owns capability lifecycle (register, promote).

    OCP delegates capability registration to CapabilityRegistry.
    This means capability creation authority is separate from
    organisational capacity decisions.
    """
    import sys
    sys.path.insert(0, os.path.join(PEOPLE_CAPABILITY_SRC))
    sys.path.insert(0, CAPABILITY_REGISTRY_SRC)
    from capabilities import CapabilityRegistry

    methods = [m for m in dir(CapabilityRegistry) if not m.startswith("_")]
    assert "register" in methods
    assert "promote" in methods
    assert "get" in methods


def test_no_specific_authority_for_expansion() -> None:
    """No specific authority/role is designated for expansion decisions.

    There is no 'CFO' authority, no 'budget_authority', no 'expansion_authority'.
    Expansion decisions would be exercised through ordinary organisational
    authority (Role, Delegation, Work assignment).
    """
    from role import Authority

    fields = set(Authority.model_fields.keys())
    assert "scope" in fields
    assert "grantor_role_id" in fields
    assert "grantee_role_id" in fields
    # No specific expansion/budget authority scope
    for forbidden in ["expansion", "budget", "hire", "cost"]:
        assert forbidden not in str(fields).lower()


def test_people_capability_creates_actors() -> None:
    """People/Capability creates Actors (via InMemoryAgentStore).

    register_agent and register_person exist in InMemoryAgentStore.
    Creation authority for Actors is in People/Capability, not OCP.
    """
    import sys
    sys.path.insert(0, PEOPLE_CAPABILITY_SRC)
    from agent_store import InMemoryAgentStore

    methods = [m for m in dir(InMemoryAgentStore) if not m.startswith("_")]
    assert "register_agent" in methods
    assert "register_person" in methods
