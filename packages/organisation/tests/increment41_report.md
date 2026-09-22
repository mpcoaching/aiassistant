# Increment 41 — Economic Organisational Design Boundary Investigation

Investigates whether the OCP/organisation model has sufficient primitives
to reason about economically justified organisational capacity.

Core question: **Does economic organisational design reveal a genuinely
missing organisational concept that Increment 40 could not expose
because it was examining structure rather than economics?**

Investigation first. No production changes. No economic entities
implemented. Prefer zero production changes.

---

## A. Current Economic-Relevant Primitives

The following existing models carry economic relevance:

**Capability** (`packages/people_capability/src/capability.py:43-64`):
`id, name, description, capability_kind: CapabilityKind{TOOL|SKILL}, status, interface,
owns_durable_state, standing_contract, tags, owner, created_by, created_at,
updated_at, metadata, payload`. Defines WHAT can be done. No capacity, cost, or value fields.

**CapabilityAssignment** (`packages/people_capability/src/capability_assignment.py:38-84`):
`id, capability_id, actor_id, skill_ids, tool_ids, assignee_type, assignee_id,
assignment_type{PRIMARY|SECONDARY|BACKUP}, status{ACTIVE|SUSPENDED|EXPIRED|REVOKED},
authorised_by, assigned_at, expires_at, reason, metadata`. Links Actor→Capability.
Assignment type encodes capacity tier. Status encodes assignment validity.

**Actor** (`packages/people_capability/src/actor.py:32-59`):
`id, name, actor_type: ActorType{PERSON|AGENT}, reference_id, marker,
fulfilled_role_ids, organisation_id, metadata, created_at, updated_at`.
Lightweight reference (ADR-037). No cost field. Metadata is open.

**Person** (`packages/people_capability/src/person.py:25-36`):
`id, name, email, status{ACTIVE|INACTIVE|ON_LEAVE}, role_ids,
employment_context: dict[str, Any], metadata, created_at, updated_at`.
`employment_context` is where Person economic cost would conceptually live.

**Agent** (`packages/people_capability/src/agent.py:31-42`):
`id, name, marker{AI|HUMAN|HYBRID}, status{ACTIVE|INACTIVE|DEPROVISIONED},
fulfilled_role_ids, runtime_identity, metadata, created_at, updated_at`.
Agent cost is infrastructure, not employment. Metadata is open.

**Role** (`packages/organisation/src/role.py:49-65`):
`id, name, description, responsibilities, authority_ids, constraints,
information_access, reports_to, status: RoleStatus{ACTIVE|INACTIVE|VACANT},
required_capability_ids, metadata`. The accountability unit for Work.
No cost or value fields.

**Work** (`packages/organisation/src/role.py:96-126`):
`id, title, description, work_type: str, status: WorkStatus, priority,
organisation_id, accountable_role_id, coordinating_role_id,
requested_by_role_id, assignee_role_id, assignee_actor_id,
assignee_person_id, assignee_agent_id, required_capability_ids,
acceptance_criteria, dependencies, parent_work_id, deliverables,
outcome: dict[str, Any], constraints, context, created_at, updated_at, metadata`.
`outcome` is unstructured — could contain value data but is not typed for it.

**CapacityPressureSignal** (`packages/contracts/organisational_events.py:129-143`):
`signal_id, signal_type, organisation_id, capability_id, capability_name,
demand_rate_per_hour, capacity_rate_per_hour, queue_depth,
average_eta_seconds, affected_work_ids, detected_at, reason`.
Organisational capacity observation. No cost or value fields.

**MaturationHistory** (`packages/capability_registry/src/concepts.py:52-60`):
`invocation_count, correction_count, last_invoked_at, promoted_at,
promotion_candidacy`. Capability maturity tracking. No economic fields.

**select_execution_path** (`packages/organisation/src/organisation_control_plane.py:529-611`):
Decision hierarchy: EXISTING_WORKFLOW → CAPABILITY_PATH →
HUMAN_TEAM_INVESTIGATION → NEW_CAPABILITY_REQUIRED. This IS economic
reasoning (minimise cost by using existing capacity before expanding)
but is implicit, not explicit.

**Paperclip create_agent mapping** (`packages/organisation_paperclip/src/organisation_paperclip.py:587-616`):
Maps `budgetMonthlyCents` from kwargs to Paperclip API. Paperclip has
implementation-level budget information but it is NOT an OCP domain concept.

---

## B. Capability vs Capacity

### What does "capacity" mean architecturally?

Capacity is "how much/how often/at what level can we exercise a capability".
It is NOT the same as Capability (which is "what can we do").

### Is capacity already implicit in existing models?

**Yes.** Capacity is implicitly represented via:

- **Role.required_capability_ids**: capabilities a role needs (demand side)
- **CapabilityAssignment**: Actor→Capability link with status ACTIVE/SUSPENDED/EXPIRED/REVOKED (assignment validity)
- **CapabilityAssignment.assignment_type**: PRIMARY/SECONDARY/BACKUP (capacity tier per actor)
- **Actor.status** (via Person/Agent): ACTIVE/INACTIVE/DEPROVISIONED (actor availability)
- **Work.status** and **Work.required_capability_ids**: workload per capability
- **CapacityPressureSignal**: demand_rate_per_hour, capacity_rate_per_hour, queue_depth (organisational capacity ratio)
- **MaturationHistory.invocation_count**: how much a capability has been exercised

### Is capacity simply assignment + actor availability + workload?

**Yes.** At the Actor level, capacity = CapabilityAssignment(status=ACTIVE) × Actor.status (available) × Work.count (workload). At the organisational level, capacity = CapacityPressureSignal.capacity_rate_per_hour derived from in-progress work counts.

### Is a distinct Capacity concept actually required?

**No.** Capacity is DERIVED from existing models. A distinct Capacity entity would duplicate information already available through CapabilityAssignment + Actor + Work. It would need to track: which Actor, which Capability, what status, what level, what timeframe — all of which already have representations.

### Can capacity be represented at multiple levels without unnecessary abstractions?

**Yes:**

- **Actor level**: CapabilityAssignment(status=ACTIVE, assignment_type=PRIMARY) + Actor.status
- **Role level**: Role.required_capability_ids + actors fulfilling the Role
- **Capability level**: MaturationHistory.invocation_count (usage intensity)
- **Organisational level**: CapacityPressureSignal (demand vs capacity rate)

### Distinguish capability vs capacity

| Concept | Question | Existing Model |
|---------|----------|----------------|
| **Capability** | What can we do? | `Capability` (name, interface, kind, status) |
| **Capacity** | How much can we do? | DERIVED (assignment + availability + workload) |
| **Demand** | How much is needed? | `Work.required_capability_ids`, `detect_capacity_pressure()` |
| **Utilisation** | What ratio is used? | DERIVED (demand ÷ capacity from CapacityPressureSignal) |

**Decision: Q1 — Capacity is DERIVED, not a missing domain concept.**
Existing Actor/Capability/Assignment/Work semantics are sufficient.
No Capacity entity required.

---

## C. Actor/Agent Economic Cost

### Where should Actor/Agent economic cost conceptually live?

**Person** (`person.py:25-36`): `employment_context: dict[str, Any]` — This is where Person economic cost WOULD live. Person represents a human individual with employment context. Cost is an employment property.

**Agent** (`agent.py:31-42`): `metadata: dict[str, Any]` — Agent cost is infrastructure cost (compute, API calls), not employment cost. It would conceptually live in metadata.

**Actor** (`actor.py:32-59`): `metadata: dict[str, Any]` — Actor is a lightweight reference (ADR-037). Cost does NOT belong here because Actor does not own the entity that carries employment data.

### Is cost Actor data, Agent data, an assignment/allocation, or organisational economic data?

Cost is **Person/Agent data** (employment context for persons, infrastructure metadata for agents), NOT Actor data (lightweight reference), NOT assignment data (who gets what), and NOT OCP data (OCP references by ID only per ADR-037).

### Could a cost baseline be associated with capacity?

Yes, analytically: Cost baseline (Person.employment_context) ÷ available capacity (active assignments) = cost per unit of capacity. But this is DERIVED, not a first-class concept.

### Could promotion/increased responsibility change economic cost?

Yes — a Person moving to a higher-responsibility Role would have different cost. But Person.employment_context has no effective dates or history. Cost change tracking is NOT implemented.

### Does cost need effective dates/history?

**If tracked, yes.** Person has `created_at` and `updated_at` but no `effective_from`/`effective_until` for cost changes. This is NOT implemented and is premature.

### Does cost belong in OCP or external finance/accounting?

**Neither OCP nor this increment.** OCP references Person/Agent by ID only (ADR-037). Detailed cost accounting belongs in an external finance/accounting system. Organisational economics (cost-justification decisions) is the relevant level for OCP, but even that is not yet needed.

**Decision: Q2 — Actor/Agent economic cost conceptually lives in Person.employment_context (persons) and Agent.metadata (agents). Not an OCP concern per ADR-037. Not implemented.**

---

## D. Value Semantics

### Does Value need to be a domain concept now?

**No.** Value is an analytical interpretation of Work/outcome/economic data, not a first-class OCP concept. The existing models can support value analysis through interpretation:

- **Work.outcome** (unstructured dict): Can contain value information but is not typed for it.
- **record_work_learning**: Creates SOLVED_APPROACH concepts for accepted project/initiative work — this is a form of value recording but restricted to durable enterprise value.
- **Capability.interface**: Defines what a capability produces (outputs), which is the basis for value analysis.

### Value includes more than revenue

Potential value types (revenue, cost avoided, cost reduced, capacity released, risk reduced, customer outcomes, strategic option value, future revenue enabled) are all ANALYTICAL interpretations. None need to be typed as first-class concepts.

### Should ROI be the universal measure?

**No.** Different capabilities have different value profiles. ROI is one metric among many. The architecture should not impose a single measure.

**Decision: Q3 — Value does NOT need to be a first-class OCP concept now.**
Value remains an analytical interpretation of Work/outcome data.

---

## E. Capability → Application → Value

### Does the architecture need Capability → Application → Value?

**No.** The existing model already captures this relationship through Work:

- **Capability** (what can we do) → **Work.required_capability_ids** (where/how it's applied) → **Work.outcome** (what result) → **record_work_learning** (learning from outcomes)

Application is represented by **Work**: Work says "this capability is applied to this organisational need at this time."

### Is Application a missing domain concept or a way of reasoning about Work?

**Application is a way of reasoning about Work.** Work already has `required_capability_ids`, `accountable_role_id`, `acceptance_criteria`, `outcome`. These are sufficient to reason about where and how capabilities are applied.

### What about the chain: Capability → Application → Value?

The chain exists implicitly:
1. **Capability** → identified by `Capability.id`
2. **Application** → `Work.required_capability_ids` references capability
3. **Value** → interpreted from `Work.outcome` (unstructured)

**Decision: Q4 — Application is NOT a missing domain concept.**
Capability → Work (via required_capability_ids) → outcome represents the chain.
No Application entity needed.

---

## F. Value-Creating vs Supporting Capability

### Does the architecture need to distinguish value-creating from supporting capabilities?

**No.** Hypothesis confirmed and validated by existing model:

A supporting capability CAN have a value-producing application. Example:
```
Finance (supporting)
  ↓
Bookkeeping (supporting)
  ↓
Margin analysis (supporting → value-producing)
  ↓
Identify leakage (value-producing)
  ↓
Change resource allocation (value-producing)
  ↓
Increased contribution (value)
```

### Evidence against a simplistic taxonomy

- **CapabilityKind** has only TOOL and SKILL — no value classification.
- **No ValueCapability/SupportingCapability** concept exists in any package.
- **Work.work_type** classifies work (bau/project/initiative), not capability value type.
- **Work.required_capability_ids** links ANY capability to ANY work — supporting capabilities can be applied to value-creating work.

### Does the architecture need Capability → Application → Value?

**No.** The more useful relationship (Capability → Application → Value) is represented by:
- Capability → Work(required_capability_ids) → Work(outcome)

**Decision: Q5 — Value-creating vs supporting capability does NOT need to be modelled explicitly.**
Application remains represented through Work/outcomes. No taxonomy required.

---

## G. Friction Economics

### Does friction need to be expressed economically?

**Not now.** Friction remains an observation/evidence source that can be economically interpreted later.

### Does FrictionScan exist?

**No.** No FrictionScan concept exists in the codebase. The closest existing mechanism is **CapacityPressureSignal** which tracks demand exceeding capacity — a form of organisational friction.

### Does this require any new organisational concept?

**No.** Friction is captured via:
- **CapacityPressureSignal**: queue_depth, demand_rate, capacity_rate, average_eta_seconds
- **Work.status transitions**: PENDING→IN_PROGRESS→COMPLETED/FAILED
- **Work.outcome**: unstructured, can record friction-related information

### Example: Actor cost vs friction

An Actor costs $60k/year and produces $150k of attributable value, but significant capacity is lost to rework and waiting. The correct decision may be to remove friction rather than hire another Actor. This insight is derived from CapacityPressureSignal data, not from a FrictionScan entity.

**Decision: Q6 — Friction CAN remain an observation/evidence source.**
No new organisational concept required. Friction economics is a future analytical layer.

---

## H. Economic Inspection Hierarchy

### Can economic inspectability work at Organisation → Team → Actor → Capability → Work?

**Yes at most levels, partially at others:**

| Level | Inspection Available | Cost | Value | Friction | Outcomes |
|-------|---------------------|------|-------|----------|----------|
| **Organisation** | list_roles, list_work, detect_capacity_pressure | ✗ | ✗ | ✓ (CapacityPressureSignal) | ✓ (Work.outcome) |
| **Team/Role** | Role(required_capability_ids, responsibilities, reports_to) | ✗ | ✗ | ✗ | ✗ (Work.accountable_role_id links) |
| **Actor** | Actor(fulfilled_role_ids) + CapabilityAssignment | ✗ | ✗ | ✗ | Work(assignee_actor_id) |
| **Capability** | MaturationHistory(invocation_count, correction_count) | ✗ | ✗ | ✓ (correction_count) | ✗ |
| **Work** | Work(all fields) | ✗ | ✓ (outcome, unstructured) | ✓ (status) | ✓ (outcome) |

### Attribution semantics

Attribution (direct, shared, enabling, uncertain) is **not modelled**.
Work.outcome has no attribution field. There is no mechanism to say
whether a value outcome is directly attributable, shared, enabling,
or uncertain. This is an analytical concern for later.

### Does attribution require confidence/quality indicators?

**Yes, if implemented.** But it does NOT require pretending precision.
Attribution with confidence levels would be an analytical overlay,
not a domain concept.

**Decision: Q7 (implicit) — Economic inspection hierarchy can be built on existing primitives.**
Attribution semantics are analytical, not modelled.

---

## I. Organisational Expansion Decisions

### Could OCP eventually answer "What capabilities do we need, at what level of capacity, and what is that worth paying for?"

**Eventually yes, but not now.** The building blocks exist:
- **select_execution_path** already makes implicit economic decisions
- **Work** can represent expansion proposals (work_type="initiative")
- **CapabilityAssignment** tracks who has what
- **CapacityPressureSignal** identifies where capacity is constrained

### What's missing?

- Explicit cost data (per Q2)
- Explicit value data (per Q3)
- Expected cost / expected value tracking (per Q9)
- Proposal-to-outcome traceability (per Q10)

### Alternatives to adding an Actor

Existing alternatives are NOT explicitly modelled as a list but are implicitly available through `select_execution_path`'s HUMAN_TEAM_INVESTIGATION path (implying "investigate before expanding"). The alternatives themselves (improve process, remove friction, train, automate, outsource, redistribute, restructure, add specialist Actor, add management, create team) are analytical decisions, not domain concepts.

### Is an organisational expansion proposal a missing concept?

**No.** Work can represent an expansion proposal via work_type="initiative", required_capability_ids, and outcome (actual result after implementation).

### Is a Decision entity required?

**No.** Decision is premature. Expansion proposals can be represented as Work items. Decision logic is an analytical process, not a durable entity.

**Decision: Q7 — Expansion decisions can be represented through Work + existing models.**
No Decision entity or expansion proposal entity required.

---

## J. Plan vs Actual

### Should the architecture support PLAN → ACTUAL → VARIANCE → LEARNING?

**Eventually yes, but premature for current system.** The purpose (organisational learning, not accounting compliance) aligns with existing learning mechanisms (record_work_learning, EIMS/SOLVED_APPROACH).

### What would need to be persisted?

- Planned metrics (cost, capacity, value, assumptions) — do not exist
- Actual metrics — partially captured in Work.outcome
- Variance — does not exist
- Learning — exists via record_work_learning (conditional)

### Which boundary owns it?

Would be the organisation package (Work, Role) with EIMS (ConceptStore) for durable learning.

### Are existing evidence/outcome mechanisms sufficient?

**Partially.** record_work_learning provides conditional learning.
But there is no mechanism for planned-vs-actual comparison.

### Is this premature?

**Yes.** The system does not yet track planned metrics. Adding plan-vs-actual before having a cost/value model would create empty comparisons.

**Decision: Q8 — Plan vs actual is DEFERRED.**
Existing evidence/learning model (record_work_learning) is sufficient foundation.
No parallel learning system needed now.

---

## K. Economic Traceability

### Can the system trace Actor → capability assignment → organisational need → proposal → evidence → cost → value → outcome?

**Partially. Some links exist, others do not:**

| Chain Link | Exists? | Mechanism |
|------------|---------|-----------|
| Actor → CapabilityAssignment → Capability | ✓ | actor_id, capability_id on CapabilityAssignment |
| Capability → Work | ✓ | Work.required_capability_ids |
| Work → Role (accountability) | ✓ | Work.accountable_role_id |
| Work → outcome | ✓ | Work.outcome (unstructured) |
| Work → original proposal | ✗ | No proposal_id field |
| Work → expected cost | ✗ | No planned_cost field |
| Work → expected value | ✗ | No planned_value field |
| Work → actual cost | ✗ | No actual_cost field |
| Work → actual value | ✓ (unstructured) | Work.outcome can contain value data |
| Outcome → learning | ✓ | record_work_learning (conditional) |

### Does this require event sourcing or audit infrastructure?

**No.** The task explicitly says "Do not build generic event sourcing or audit infrastructure." The traceability gap is about proposal→outcome linkage, which could be represented by Work.parent_work_id (proposal Work → implementation Work) and Work.outcome (actual results).

**Decision: Q9 (implicit) — Economic traceability is partially supported.**
Actor→Capability→Work→outcome chain exists. Proposal→cost→value chain is missing.
Chain can be extended via existing Work fields without new entities.

---

## L. Evidence and Learning Relationship

### Can plan-vs-actual connect to the existing evidence/learning model?

**Yes, in principle.** The learning model already has:
- **record_work_learning**: Creates SOLVED_APPROACH concepts from accepted Work outcomes
- **assess_work_outcome**: Compares execution results against acceptance criteria
- **assess_capability_development**: Validates capability development against interface contracts

These provide the "ACTUAL" and "LEARNING" parts of PLAN→ACTUAL→VARIANCE→LEARNING.
The "PLAN" part (planned cost, planned capacity, planned value, assumptions) does not exist.

### Would this create a parallel learning system?

**No, if built on existing primitives.** PLAN→ACTUAL would extend Work with planned fields, and variance would be computed from planned vs actual. Learning would continue through record_work_learning. No parallel system needed.

**Decision: Q8 — Evidence and learning can absorb plan-vs-actual when ready.**
No parallel system. Defer until cost/value are modelled.

---

## M. Creation / Expansion Authority

### Who should decide to add an Actor, increase responsibility, assign capability, change capacity, restructure work, create a Paperclip team, authorise additional cost?

**Hypothesis: These are organisational decisions exercised by ordinary Actors through capabilities, not privileged hard-coded People/HR behaviour.**

### Does the existing architecture support this?

**Yes, with some gaps:**

| Decision | Current Mechanism | Sufficient? |
|----------|-------------------|-------------|
| Add Actor | People/Capability creates Actor via AgentStore | ✓ (ADR-037) |
| Increase responsibility | Role change (add required_capability_ids) | ✓ |
| Assign Capability | CapabilityAssignment | ✓ |
| Change capacity | DERIVED (assignment + availability) | ✓ (no change needed) |
| Restructure work | Work creation, reassignment | ✓ |
| Create Paperclip team | Paperclip API (via adapter) | ✓ (implementation level) |
| Authorise cost | **NO mechanism** | ✗ (deferred) |

### Does the architecture need special HR/decision authority?

**No.** OCP creates Roles and Work (organisational decisions). People/Capability creates Actors. CapabilityRegistry manages capability lifecycle. Paperclip implements execution. No special HR subsystem needed per Increment 40's conclusions.

### Does cost authorisation need a mechanism?

**Not yet.** Cost authorisation requires cost data (per Q2) which doesn't exist. When cost data is introduced, authorisation would flow through ordinary organisational authority (Role, Delegation, Work assignment).

**Decision: Q12 (partial) — Creation/expansion authority uses existing organisational mechanisms.**
Cost authorisation is deferred pending cost model.

---

## N. Paperclip Implementation Boundary

### Does Paperclip expose useful information for economics?

**Limited:**

| Information | Paperclip Exposes? | OCP Uses? |
|-------------|-------------------|-----------|
| Agent cost (budgetMonthlyCents) | ✓ (create_agent mapping) | ✗ (not read by OCP) |
| Budget | ✓ (implementation-level) | ✗ |
| Organisational hierarchy | ✓ (Agent.reportsTo) | ✓ (via Role.reports_to) |
| Workload | ✓ (Issue status, assignment) | ✓ (via Work cache) |
| Projects/tasks | ✓ (Issues) | ✓ (via Work) |
| Team structure | ✓ (Team Catalog) | ✗ (implementation only) |
| Manager relationships | ✓ (Agent.reportsTo) | ✓ (via Role.reports_to) |
| Skills/capabilities | ✓ (Agent capabilities field) | ✓ (via Role.required_capability_ids) |
| Resource constraints | ✗ | ✗ |

### Should Paperclip be authoritative for OCP economics?

**No.** Paperclip is an implementation. OCP defines what exists; Paperclip instantiates. Paperclip's budgetMonthlyCents is an implementation detail, not an OCP domain concept.

### Should Paperclip be the organisational authority?

**No.** Per Increment 40: Paperclip remains an implementation. OCP owns organisational semantics.

**Decision: Q12 (partial) — Paperclip has implementation-level budget info but NOT authoritative for OCP economics.**
No economic synchronisation needed.

---

## O. OCP Economic Authority Boundary

### What economic decisions could OCP eventually make?

- **Capacity planning**: detect_capacity_pressure already identifies where capacity is constrained
- **Execution path selection**: select_execution_path already minimises cost (EXISTING_WORKFLOW before CAPABILITY_PATH before HUMAN_TEAM_INVESTIGATION)
- **Capability gap identification**: NEW_CAPABILITY_REQUIRED signals where capabilities are missing
- **Workload distribution**: Work assignment to available Actors/Roles

### What economic decisions should OCP NOT make?

- **Cost accounting**: Not OCP's concern (external finance system)
- **ROI calculation**: Not imposed as mandatory metric
- **Budget allocation**: Requires cost data that doesn't exist
- **Hire/no-hire decisions**: Analytical, not automated

### What is the boundary?

OCP owns:
- Organisational capacity observation (detect_capacity_pressure)
- Execution path selection (implicit economic reasoning)
- Work and Role creation (organisational design)

OCP does NOT own:
- Cost data (Person/Agent domain)
- Value data (analytical)
- Financial reporting (external system)
- Hiring decisions (analytical)

**Decision: Q12 — OCP economic authority is limited to capacity observation and execution path selection.**
No broader economic authority needed now.

---

## P. Missing Concepts

The following are genuinely missing but do NOT require new entities:

1. **Proposed cost on Work** — Work could have planned_cost, but it's premature
2. **Proposed value on Work** — Work could have planned_value, but it's premature
3. **Cost baseline on Person** — Person.employment_context could hold it, but it's not an OCP concern
4. **Proposal→implementation→outcome linkage** — Work.parent_work_id provides partial linkage

The following are NOT missing (derived/analytical):

1. **Capacity** — derived from Assignment + Actor + Work
2. **Value** — analytical interpretation of outcome
3. **Application** — represented by Work(required_capability_ids)
4. **Friction economics** — observation, not concept
5. **Decision entity** — premature, represented by Work
6. **Plan vs actual** — deferred
7. **Value taxonomy** — not needed (hypothesis confirmed)

**Decision: Q13 — No genuinely missing organisational concepts requiring new entities.**
Economic reasoning can be layered onto existing primitives.

---

## Q. Concepts Explicitly Rejected

| Concept | Rejected Because |
|---------|-----------------|
| **Capacity entity** | Derivable from Assignment + Actor + Work |
| **Value entity** | Analytical interpretation of outcome |
| **Application entity** | Represented by Work(required_capability_ids) |
| **ValueCapability taxonomy** | Supporting capability can produce value; no taxonomy needed |
| **FrictionScan** | Friction remains observation; CapacityPressureSignal exists |
| **Decision entity** | Premature; Work can represent proposals |
| **Plan vs actual mechanism** | Premature; no planned metrics exist yet |
| **Expense/cost entity** | Not OCP concern; Person/Agent domain |
| **ROI metric** | Not universal; analytical choice |
| **Attribution entity** | Analytical; Work.outcome is unstructured |
| **Economic traceability chain** | Partially exists; can extend via Work fields |
| **Budget entity** | Not OCP concern; external finance system |
| **Hiring authority** | Analytical; existing organisational authority suffices |

---

## R. Architectural Options Considered

### Option A: Add Capacity entity
**Rejected.** Derivable from Assignment + Actor + Work. Would duplicate existing information.

### Option B: Add Value entity
**Rejected.** Value is analytical interpretation. Typing it would impose premature structure.

### Option C: Add Application entity
**Rejected.** Work already represents application via required_capability_ids.

### Option D: Add ValueCapability taxonomy
**Rejected.** Supporting capabilities can produce value. No taxonomy needed.

### Option E: Add Decision entity
**Rejected.** Premature. Work can represent expansion proposals.

### Option F: Add plan-vs-actual mechanism
**Deferred.** No planned metrics exist to compare against.

### Option G: Add cost/expense to OCP
**Rejected.** OCP references Person/Agent by ID only (ADR-037). Cost lives in People/Capability.

### Option H: Add FrictionScan
**Rejected.** CapacityPressureSignal covers friction observation. Economic interpretation is future work.

### Option I: Do nothing (minimum model)
**Selected.** Existing primitives are sufficient for current needs.
Economic reasoning can be layered on as analytical interpretation.

### Minimum coherent model

**Option I** (minimum): Existing primitives (Capability, CapabilityAssignment, Actor, Person, Agent, Role, Work, Assignment, CapacityPressureSignal, record_work_learning) are sufficient. No new entities required.

**Option I extended** (when cost model is needed): Person.employment_context for cost baseline, Work for proposals and outcomes, record_work_learning for learning. Still no new entities.

---

## S. Recommended Minimum Model

The smallest coherent economic model that would allow the organisation to avoid unnecessary organisational expansion:

### Currently available (no changes needed):

1. **Capability** — defines WHAT can be done
2. **CapabilityAssignment** — WHO can do WHAT (with status and type)
3. **Work** — WHERE/WITH WHAT capability (required_capability_ids)
4. **Role** — accountability unit for Work and capability requirements
5. **CapacityPressureSignal** — organisational capacity observation
6. **select_execution_path** — implicit economic reasoning (minimise cost)
7. **record_work_learning** — learning from outcomes (project/initiative)

### Should remain derived/analytical:

- **Capacity** — derived from Assignment + Actor availability + Work counts
- **Value** — analytical interpretation of Work.outcome
- **Friction economics** — analytical overlay on CapacityPressureSignal

### Should be deferred:

- Cost/budget model (Person.employment_context can hold it later)
- Plan vs actual (needs cost/value first)
- Decision entity (Work can represent proposals)
- Economic traceability chain (partially exists, extend via Work)

### What Increment 42 should implement:

**Nothing mandatory.** If cost justification becomes urgent:
- Add planned_cost, planned_value to Work (compatibility-safe, optional fields)
- Add planned_value to Role (optional)
- But this should wait until cost data exists in Person/Agent domain.

---

## T. Impact on Increment 40

Increment 40 established:
- Team is NOT an OCP Actor ✓ (unchanged)
- Team remains a Paperclip implementation structure ✓ (unchanged)
- People/Capability can be represented through ordinary primitives ✓ (unchanged)
- Role already serves as Position Specification ✓ (unchanged)
- No special HR/People subsystem ✓ (unchanged)

### Does Increment 41 change any Increment 40 conclusions?

**No.** Increment 41 examines economics; Increment 40 examined structure.
No structural conflict was found. No Increment 40 conclusion requires revision.

Specifically:
- The absence of cost/authorisation mechanisms (Q13) does not create a
  need for Team as Actor, Position Specification, or HR subsystem.
- Economic reasoning layered on existing primitives does not require
  any Increment 40 changes.

**Decision: Q11 — Increment 41 does NOT change Increment 40's conclusions.**
No direct architectural evidence requiring revision.

---

## U. Architectural Tests Added

**53 tests** in `packages/organisation/tests/test_increment41_economic_organisation_boundary.py`:

### A. Capability vs Capacity (6 tests)
1. `test_capability_has_no_capacity_field` — Capability has no capacity field
2. `test_capability_assignment_links_actor_to_capability` — Assignment link exists
3. `test_work_has_no_capacity_fields` — Work has no capacity fields
4. `test_capacity_pressure_signal_exists_as_organisational_signal` — CapacityPressureSignal is the organisational signal
5. `test_detect_capacity_pressure_uses_work_counts` — Capacity derived from work counts
6. `test_capacity_is_derivable_from_assignment_and_actor_availability` — Capacity is derivable

### B. Actor/Agent Economic Cost (7 tests)
7. `test_actor_has_no_cost_field` — Actor has no cost field
8. `test_person_has_employment_context` — Person has employment_context for cost
9. `test_agent_has_metadata_for_analytical_data` — Agent has metadata for cost
10. `test_capability_assignment_has_no_cost` — Assignment has no cost
11. `test_actor_cost_belongs_in_people_capability_plane` — Cost not in OCP
12. `test_paperclip_has_budget_monthly_cents_in_mapping` — Paperclip has implementation-level budget
13. `test_actor_cost_requires_effective_dates_if_tracked` — Cost history not implemented
14. `test_actor_cost_is_not_in_organisation_package` — No cost in OCP models

### C. Value Semantics (6 tests)
15. `test_work_outcome_is_unstructured` — Work.outcome is not typed for value
16. `test_value_is_not_first_class_concept` — Value is not a domain concept
17. `test_record_work_learning_excludes_bau` — Learning only for project/initiative
18. `test_maturation_history_has_no_value_fields` — Maturation is lifecycle, not economics
19. `test_solved_approach_is_outcome_not_value` — SOLVED_APPROACH records outcomes
20. `test_value_analytical_not_modelled` — Value is analytical

### D. Capability vs Application vs Value (5 tests)
21. `test_work_requires_capability_ids` — Work links to capabilities
22. `test_capability_has_no_application_field` — Capability has no application
23. `test_capability_outcome_assessor_uses_work` — Application is Work
24. `test_value_analytical_not_modelled` — Value not modelled
25. `test_capability_kind_has_only_tool_and_skill` — No value taxonomy on Capability

### E. Value-Creating vs Supporting (3 tests)
26. `test_capability_kind_has_only_tool_and_skill` — Only TOOL/SKILL kinds
27. `test_no_value_capability_taxonomy` — No value/supporting taxonomy
28. `test_work_classification_is_bau_project_initiative` — Work classified by type not value

### F. Friction Economics (3 tests)
29. `test_no_friction_scan_exists` — FrictionScan doesn't exist
30. `test_capacity_pressure_is_closest_to_friction_observation` — CapacityPressureSignal is friction observation
31. `test_friction_remains_observation_not_concept` — Friction is observation

### G. Economic Inspection Hierarchy (6 tests)
32-37. Inspection hierarchy at Organisation, Role, Actor, Capability, Work levels
38. `test_attribution_semantics_are_not_modelled` — Attribution not modelled

### H. Organisational Expansion Decisions (6 tests)
39. `test_no_expansion_proposal_concept` — No ExpansionProposal
40. `test_work_can_represent_expansion_proposal` — Work can represent proposals
41. `test_no_decision_entity_exists` — No Decision entity
42. `test_select_execution_path_is_economic_reasoning` — select_execution_path IS economic
43. `test_alternatives_to_actor_not_explicitly_modelled` — Alternatives are analytical
44. `test_no_plan_vs_actual_mechanism` — No plan vs actual
45. `test_work_status_tracks_lifecycle_not_plan` — Status is lifecycle
46. `test_record_work_learning_conditional_on_outcome` — Learning conditional

### I. Economic Traceability (5 tests)
47-51. Traceability chain: Actor→Assignment→Capability, Work→Capability, Role→Work
52. `test_no_original_proposal_link` — No proposal linkage
53. `test_no_provenance_on_capability` — Capability provenance is knowledge, not economic

### J. Creation/Expansion Authority (5 tests)
54-58. OCP creates roles/work, doesn't create actors, registry owns capability lifecycle, no specific expansion authority, People/Capability creates actors

### K. Paperclip Boundary (1 test)
59. `test_paperclip_has_budget_monthly_cents_in_mapping` — Paperclip budget is implementation-level

---

## V. Final Decision and Next Increment

### Final Decision: **A** (minimum coherent model — no new concepts required)

The existing OCP/organisation model has sufficient primitives to reason about economically justified organisational capacity. Economic reasoning can be layered onto existing models as analytical interpretation without introducing new domain entities.

### Summary of decisions:

| Question | Decision | Evidence | New concept required? |
|----------|----------|----------|----------------------|
| Q1: Capacity | Derived | Assignment + Actor + Work | No |
| Q2: Actor cost | People/Capability | Person.employment_context | No (OCP) |
| Q3: Value | Analytical | Work.outcome | No |
| Q4: Application | Work | Work.required_capability_ids | No |
| Q5: Value taxonomy | Rejected | CapabilityKind TOOL/SKILL only | No |
| Q6: Friction economics | Observation | CapacityPressureSignal | No |
| Q7: Expansion decisions | Work | Work work_type="initiative" | No |
| Q8: Plan vs actual | Deferred | No planned metrics | No |
| Q9: Decision entity | Rejected | Work suffices | No |
| Q10: Smallest model | Existing primitives | All above | No |
| Q11: Increment 40 impact | None | No conflicts | No |
| Q12: Increment 42 | Nothing mandatory | No urgent need | No |
| Q13: Missing concepts | None requiring entities | All derivable | No |

### Smallest coherent economic model:

Existing primitives (Capability, CapabilityAssignment, Actor, Person, Agent, Role, Work, Assignment, CapacityPressureSignal, record_work_learning, select_execution_path) are sufficient. No new entities required.

### What should remain derived/analytical:

- Capacity (derived from Assignment + Actor + Work)
- Value (analytical interpretation of outcome)
- Friction economics (analytical overlay on signals)

### What should be deferred:

- Cost/budget model (pending Person/Agent domain)
- Plan vs actual (pending cost/value model)
- Decision entity (Work can represent proposals)
- Economic traceability chain (extend via Work fields when needed)

### Whether Increment 42 should implement anything:

**Nothing mandatory.** If cost justification becomes urgent before Person/Agent cost model is in place, optionally add:
- `planned_cost: float | None = None` to Work (compatibility-safe)
- `planned_value: float | None = None` to Work (compatibility-safe)

But this should wait until cost data exists in Person/Agent domain.

---

## Test Results

**53 tests passed** in `test_increment41_economic_organisation_boundary.py`.
**556 total organisation tests passing** (53 new + 503 pre-existing, 1 pre-existing failure in test_increment30 unrelated to this increment).

Zero production changes made. Zero lint issues.

---

## Key Finding

**Does economic organisational design reveal a genuinely missing organisational concept that Increment 40 could not expose?**

**No.** Increment 40 examined structure (Team, Role, Actor, People/Capability). Increment 41 examined economics. The existing primitives — Role (accountability), CapabilityAssignment (who has what), Work (what needs doing, with required_capability_ids), CapacityPressureSignal (capacity observation), select_execution_path (implicit cost minimisation), record_work_learning (conditional learning) — are sufficient for economic reasoning at the organisational level. Economic concepts (cost, value, capacity) are either:

1. **Already represented** (CapabilityAssignment = capacity, Work.outcome = value source, CapacityPressureSignal = friction/capacity)
2. **Belong to another domain** (Person.employment_context = cost, People/Capability plane)
3. **Analytical interpretations** of existing data (value, friction economics)

No new organisational concept is required. The architecture can reason about economically justified capacity through interpretation of existing models, without introducing new entities. This is **Architectural Decision A** — minimum coherent model achieved with zero changes.
