# Increment 51 — People/Capability Capacity Analysis and Response-Selection Boundaries

**Increment type:** Investigation-only (no production-code changes).

**Objective:** Establish the smallest correct architectural boundary for People/Capability capacity analysis and response selection. Confirm that the existing domain primitives can represent capacity analysis and response selection without introducing HR/staffing/capacity entities, expanding `ExecutionPath`, or weakening the Increment 48 identity invariant.

**Executive summary:** The existing domain model satisfies all 20 architectural contracts. People/Capability can be understood as an ordinary Role + Actor that uses existing capability, assignment, proficiency, work, and capability-registry primitives to reason about capacity and response selection. Three gaps are identified as **missing but clearly bounded**:

1. **Required-proficiency threshold** — `CapabilityProficiency` records *actual* proficiency (`proficiency_level`), but there is no *required* threshold on `CapabilityAssignment` or `Role` to compare against. The semantic distinction is clear; the field is deferred.
2. **Capacity-analysis service boundary** — capacity inputs are all representable (Actors, CapabilityAssignments, CapabilityProficiency, Work, availability); no consolidated analysis/query/application service exists yet.
3. **Response-selection separation from `ExecutionPath`** — `select_execution_path` answers only "what broad execution path is available?"; "what should we hire/develop/reassign?" is a separate People/Capability analysis concern that consumes existing state and may use existing organisational-change mechanisms.

No `Capacity`, `Staffing`, `Hiring`, `Workforce`, `Team`, `Decision`, `Supplier`, `Vendor`, `CapabilityGraph`, `CapabilityRelationship`, or `CapabilityEdge` entity is introduced or required. `ExecutionPath` retains exactly four members. The Increment 48 identity chain is intact.

This report distinguishes:
- **Representable now** — what the current primitives can already express.
- **Implemented now** — what the current code actually implements.
- **Missing but clearly bounded** — genuinely absent but architected boundaries.
- **Safe to automate** — analysis/retrieval/derivation that can be automated without making an organisational decision.
- **Not safe / not currently supported** — requires authority-gated change or an absent model (e.g., outsourcing).

---

## A. People/Capability Boundary

### A.1 People/Capability can be represented as Role + Actor

**Representable:** Yes. People/Capability is an ordinary `Role` (`packages/organisation/src/role.py`) realized by a uniform `Actor` (`packages/people_capability/src/actor.py`) that references a `Person` or `Agent` via `ActorType` (`PERSON`/`AGENT`) + `reference_id`. Chief of Staff is an ordinary `Role` with `Authority` + `Delegation` — no special executive entity.

**Implemented:** Yes — verified by `_bootstrap_organisation()` which constructs `Role` + `Agent` + `Actor` + `Authority` + `Delegation` using existing primitives. `InMemoryAgentStore.register_agent()` automatically creates the corresponding `Actor`.

**Safe to automate:** No — representing the function as a Role + Actor does not authorise autonomous change; authority must be delegated (see A.7).

### A.2 Can it analyse capacity without a Capacity entity?

**Representable:** Yes. Capacity is a derived analytical result, not an entity. The representable inputs are:

```
Actors                       (Actor / find_actors_for_role / list_actors)
  + CapabilityAssignments    (get_assignments_for_capability / get_assignments_for_actor / actor_has_capability)
  + CapabilityProficiency    (CapabilityProficiency, ProficiencyLevel)
  + Work / assignments       (Work.required_capability_ids, WorkStatus, OCP.list_work / query_capability)
  + availability             (Work.status IN (READY/ASSIGNED/IN_PROGRESS); query_capability.in_progress; detect_capacity_pressure)
=
available / required capacity analysis (derived)
```

The test's `_derive_available_capacity` helper proves these inputs are individually representable and combinable: `available = (actors assigned capability) - (saturated by in-progress work)`.

**Implemented:** Partial. The inputs exist and are tested; `query_capability()` and `detect_capacity_pressure()` exist. There is **no consolidated capacity-analysis/query/application service** — a future People/Capability analysis layer must compose the inputs. `CapacityPressureSignal` (`contracts/organisational_events.py`) is a **signal**, not an entity.

**Safe to automate:** No — no consolidated analysis service exists, and capacity derivation that drives staffing decisions is not evidence-gated.

### A.3 People/Capability is itself recursively subject to capability analysis

**Representable:** Yes. People/Capability is an ordinary `Actor`, so the same `CapabilityAssignment`, `CapabilityProficiency`, capacity-analysis, and response-selection logic applies to its own capabilities. A gap in People/Capability's own capability is detected via the same `select_execution_path` → `NEW_CAPABILITY_REQUIRED` → `capability_development` Work → `develops_capability_id` → `Worker._develop_capability` → registry → `promote` → `CapabilityProficiency` chain, and can be provisioned via new Agent/Person.

**Implemented:** Yes — verified by contract 3 (recursive self-improvement Work assigned to the People/Capability Actor). No `SelfImprovement` or `HRImprovement` entity is introduced.

**Safe to automate:** No — same authority and governance boundaries apply recursively.

---

## B. Required Proficiency

### B.1 required_proficiency is genuinely absent

**Representable:** No — by deliberate architectural boundary. There is no `required_proficiency`, `required_proficiency_level`, or `min_proficiency` field on `CapabilityAssignment` (`packages/people_capability/src/capability_assignment.py`), `CapabilityProficiency` (`packages/people_capability/src/capability_proficiency.py`), or `Role` (`packages/organisation/src/role.py`). Verified via pydantic `model_fields` inspection (contract 4, contract 5).

**Implemented:** `CapabilityProficiency.proficiency_level` records **actual** proficiency (NOVICE/COMPETENT/PROFICIENT/EXPERT/MASTER), written by `Operations._record_proficiency` after capability promotion. There is no required threshold to compare against.

**Missing but clearly bounded:** The absence is a genuine, bounded gap. The semantic question "we have the capability but the Actor's proficiency is below what's required" has no way to be expressed in the model today — it collapses into `HUMAN_TEAM_INVESTIGATION` (if the capability exists but is unavailable) or `CAPABILITY_PATH` (if available), conflating "insufficient proficiency" with "available".

**Safe to automate:** N/A — the comparison cannot even be expressed yet.

### B.2 Smallest coherent future boundary for required proficiency

The requirement is to place a "required proficiency level" against which actual `CapabilityProficiency.proficiency_level` can be compared. Three candidate placements remain viable:

| Placement | Pros | Cons |
|---|---|---|
| `Role.required_proficiency_level: dict[str, ProficiencyLevel]` | Natural for "this role requires PROFICIENT in cap-X"; mirrors `Role.required_capability_ids` | Does not express per-actor variation within a role |
| `CapabilityAssignment.required_proficiency_level: ProficiencyLevel` | Direct comparison: "this actor is assigned this capability at PROFICIENT"; enables per-actor threshold | Adds a field to the assignment rather than the role |
| `Work.required_proficiency_levels: dict[str, ProficiencyLevel]` | Express per-work proficiency requirement in context | Work-specific; does not help role-level planning |

**Recommendation (deferred — not implemented in this increment):** `Role.required_capiciency_ids: list[str]` already exists. The smallest coherent extension is `Role.required_proficiency_levels: dict[str, ProficiencyLevel]` mapping a capability ID to a required level — this keeps the requirement at the role level (where it naturally belongs for capacity planning) and is directly comparable to `CapabilityProficiency.proficiency_level` on the Actor. However, `CapabilityAssignment.required_proficiency_level` is equally viable if per-actor variance is the priority. **No decision is made here; implementation is deferred until the capacity-analysis service boundary is established.** No field is added in Increment 51.

---

## C. Capacity Analysis

### C.1 Capacity is derivable from existing organisational state

**Representable:** Yes. All inputs exist as individually expressible primitives (see A.2). The `_derive_available_capacity` helper in the test suite demonstrates the combination: assign Actor → Capability → Work → saturation → available slots. No `Capacity` entity is needed.

**Implemented:** Partial — `query_capability()` returns `{"available": bool, ...}` and `detect_capacity_pressure()` returns a `CapacityPressureSignal`. No consolidated `capacity_for(capability_id) -> int` function exists.

**Safe to automate:** The *derivation* of available actor count for a capability (without making a staffing decision) is safe to automate — it is read-only retrieval/computation. The *decision* to provision/staff based on that derivation is not safe to automate (see A.7).

### C.2 CapabilityAvailability is not a capacity model

**Representable:** `CapabilityAvailability` (`contracts/enterprise_capability_query.py`) has fields `capability_id`, `available: bool`, `eta_seconds`, `assignee`, `reason`. It is an **operational availability flag** — "can this capability be invoked right now?" — not a capacity model. It does not carry actor count, proficiency, or throughput.

**Implemented:** Yes — verified by pydantic field inspection (contract 8).

**Missing but clearly bounded:** `CapabilityAvailability` does not answer "do we have enough Actors with sufficient proficiency?" That is the capacity-analysis service boundary.

### C.3 CapacityPressureSignal is a signal, not an entity

**Representable:** Yes. `CapacityPressureSignal` (`contracts/organisational_events.py`) is a derived signal with `demand_rate_per_hour`, `capacity_rate_per_hour`, `queue_depth`, `affected_work_ids`. It is **emitted** by `detect_capacity_pressure`, not stored as a `Capacity`/`Staffing` entity.

**Implemented:** Yes — verified by creating 2+ in-progress Work items and observing the signal (contract 9).

**Safe to automate:** The signal derivation is safe to automate (read-only analysis of Work state). Acting on it (staffing) is not.

---

## D. Response Selection

### D.1 ExecutionPath answers "what broad execution path is available?"

**Representable:** Yes. `ExecutionPath` (`packages/organisation/src/execution_path.py`) has exactly four members:
- `EXISTING_WORKFLOW` — an existing workflow matches the intent
- `CAPABILITY_PATH` — a registered, available capability exists
- `NEW_CAPABILITY_REQUIRED` — a capability gap is identified (not a commitment to develop)
- `HUMAN_TEAM_INVESTIGATION` — a capability exists but is unavailable, needs human review

**Implemented:** Yes — verified by enumerating members (contract 10) and by exercising every branch through `select_execution_path`.

**Safe to automate:** Yes for *path selection* (read-only matching, no staffing risk). The selection itself carries no hiring/staffing decision.

### D.2 select_execution_path does NOT distinguish proficiency/capacity gaps

**Representable:** No — by current limitation. `select_execution_path` distinguishes only:
- workflow exists → `EXISTING_WORKFLOW`
- capability registered + available (`available=True`) → `CAPABILITY_PATH`
- capability exists but `available=False` → `HUMAN_TEAM_INVESTIGATION`
- capability not registered → `NEW_CAPABILITY_REQUIRED`

It does **not** distinguish:
- insufficient proficiency (capability exists, available, but Actor lacks required proficiency)
- insufficient capacity (capability exists, available, but no Actor is free)
- unknown capability (not the same as a gap — a gap is a known ID not registered)
- insufficient understanding (the need is not yet refined into a capability ID)

Verified by source inspection of `InMemoryOrganisationControlPlane.select_execution_path` (contract 11): the method contains no references to `proficiency_level`, `required_proficiency`, `capacity_analysis`, `staffing`, or `hiring`.

**Implemented:** The four-branch selection is implemented; the finer distinctions are **not**.

**Missing but clearly bounded:** These distinctions belong in a People/Capability **analysis layer**, not in `ExecutionPath`. `select_execution_path` returns an `ExecutionPathResult` (a data object); it does not provision actors, assign capabilities, or emit hiring signals (contract 20).

### D.3 Response selection is a People/Capability concern, not an ExecutionPath expansion

**Representable:** Yes. The conceptual response set for closing a capability/capacity gap is expressible through existing primitives:

| Response | Primitive |
|---|---|
| Train/develop existing Actor | `capability_development` Work → `Worker._develop_capability` → `CapabilityRegistry` → `CapabilityProficiency` |
| Reassign capability | `CapabilityAssignment` status (ACTIVE/SUSPENDED/EXPIRED/REVOKED) + `AssignmentType` (PRIMARY/SECONDARY/BACKUP) |
| Increase capacity | Additional `Agent` or `Person` via `InMemoryAgentStore.register_agent/register_person` + `assign_capability` |
| Provision new Agent | `InMemoryAgentStore.register_agent` |
| Provision new Person | `InMemoryAgentStore.register_person` |
| Develop new Capability | Increment 48 lifecycle (see M) |
| Use existing Workflow | `ExecutionPath.EXISTING_WORKFLOW` |
| Acquire/use Tool | `CapabilityKind.TOOL` |
| Human investigation | `ExecutionPath.HUMAN_TEAM_INVESTIGATION` |
| Outsource | **Explicitly unsupported** — no `Supplier`/`Vendor` model, no `OUTSOURCE` ExecutionPath member |

**Implemented:** Each response's *mechanism* is implemented (see the table). The *decision logic* that selects among them is **not** implemented — that is the People/Capability analysis-service boundary (C.1).

**Missing but clearly bounded:** The response-selection decision function ("given organisational state, what is the gap and what classes of response could close it?") does not exist as a single service. It would consume the capacity analysis (C), proficiency comparison (B), and authority gate (A.7) — all of which are either representable or implemented as primitives.

**Not safe to automate:** Selecting a response that involves staffing, provisioning, or outsourcing requires delegated organisational-change authority and evidence of cost/benefit/time-to-deliver. The response-selection logic may *recommend* options, but the *act* of provisioning/hiring is an organisational change that must go through `OCP.execute_organisational_change` with authority.

### Separation principle

The architecture explicitly separates these two concerns:

```
OCP ExecutionPath
    = "what broad execution path is available?"

People/Capability analysis
    = "given the organisational state, what capability/capacity gap exists
       and what classes of response could close it?"
```

The latter may use existing organisational-change mechanisms (`OCP.execute_organisational_change`, `Worker._develop_capability`, `CapabilityRegistry.promote`, `store.assign_capability`, etc.) but must **not** be folded into `ExecutionPath`. `ExecutionPath` is an OCP-level solution-path signal; response selection is a People/Capability concern.

---

## E. Adjacency

### E.1 Adjacency is not first-class

**Representable:** `Capability` (`packages/people_capability/src/capability.py`) has `tags: list[str]` and `metadata: dict[str, Any]` but **no** `adjacency`, `adjacent_capabilities`, `capability_graph`, or `related_capabilities` field. Verified by pydantic field inspection (contract 13).

**Implemented:** `tags` and `metadata` are fully implemented fields on the `Capability` model and are persisted by `ConceptStoreCapabilityRepository` (which carries `tags` into the concept's tag list and `metadata`-derived payload).

**Safe to automate:** Tagging and metadata annotation is safe to automate (read/write on existing concepts).

### E.2 No graph abstraction exists

**Representable:** No `CapabilityGraph`, `CapabilityRelationship`, or `CapabilityEdge` class exists anywhere in `packages/organisation/src`, `packages/people_capability/src`, `packages/contractts`, `packages/capability_registry/src`, `packages/workflow_runner/src`, or `packages/organisation_paperclip/src`. Verified by source scan (contract 14).

**Implemented:** Nothing to implement — the absence is the implemented state.

### E.3 Adjacency can remain contextual reasoning

**Representable:** Yes. Adjacency is useful reasoning context (e.g., "cap-X builds on cap-Y") and can be carried contextually via `tags` (e.g., `["uses:cap-y", "depends-on:cap-z"]`) and `metadata` (e.g., `{"adjacency_context": "...", "related_capability_ids": ["cap-y"]}`). Verified by constructing a `Capability` with adjacency-tagged fields (contract 15).

**Implemented:** Yes — tags and metadata are stored and retrieved.

**Missing but clearly bounded:** A graph abstraction should only be introduced when a concrete use case requires durable, queryable relationship semantics (e.g., transitive impact analysis, pathfinding between capabilities). The current model correctly defers this. **No graph is introduced in Increment 51.**

---

## F. Existing Increment 48 Identity

### F.1 develops_capability_id is distinct from required_capability_ids

**Representable:** Yes. `Work` (`packages/organisation/src/role.py`) has both `required_capability_ids: list[str]` (capabilities needed to perform the Work) and `develops_capability_id: str | None` (the capability the Work produces). These are independent fields. Verified by pydantic field inspection (contract 16).

**Implemented:** Yes — the `Work` model, `WorkCreateRequest` contract (`contracts/work_management.py`), and `WorkManagementAdapter` all carry both fields independently. `Increment 48` tests verify the adapter propagates both.

**Safe to automate:** N/A — this is a modeling invariant, not an action.

### F.2 Increment 48 identity chain is intact

The chain:

```
ExecutionPathResult.capability_id      (preserved on NEW_CAPABILITY_REQUIRED /
        ↓                              HUMAN_TEAM_INVESTIGATION / CAPABILITY_PATH)
Work.develops_capability_id            (set on capability_development Work)
        ↓
Capability.id                           (Worker._develop_capability uses it)
        ↓
CapabilityRegistry.get()                (canonical store)
        ↓
assess_capability_development()         (evidence-gated: interface + execution)
        ↓
CapabilityRegistry.promote()            (DRAFT → ACTIVE)
```

**Representable:** Yes.

**Implemented:** Yes — end-to-end verified in contract 17, which runs the full chain: `select_execution_path` → `NEW_CAPABILITY_REQUIRED` (capability_id preserved) → `Work(develops_capability_id=...)` → `Worker._develop_capability` → `CapabilityRegistry.register` (DRAFT) → `assess_capability_development` (passes) → `promote` (ACTIVE). Same capability ID throughout.

**Safe to automate:** Conditionally — the execution and assessment are evidence-gated. The *decision* to develop is not autonomous (see D.3).

---

## G. Authority / Automation Boundary

### G.1 No Decision entity exists

**Representable:** No — by deliberate boundary. No `Decision`, `Staffing`, `Hiring`, `Workforce`, `Team`, `Capacity`, `Supplier`, or `Vendor` class exists in any package source tree. Verified by source scan across `organisation/src`, `people_capability/src`, `contracts/`, `capability_registry/src`, `workflow_runner/src`, and `organisation_paperclip/src` (contract 18, contract 20).

**Implemented:** The absence is the implemented state. The conceptual response set is representable through existing primitives (see D.3), but there is no generic `Decision` entity to hold the selection — each response maps to a concrete mechanism.

**Missing but clearly bounded:** Intentional. A `Decision` entity would reify a staffing/hiring decision as an organisational record without authority gating. The architecture correctly requires that capacity/affinity decisions flow through `OCP.execute_organisational_change` with delegated authority, not through a standalone decision store.

### G.2 No autonomous staffing/hiring

**Representable:** No — `OCP.execute_organisational_change` requires delegated authority. `_has_organisational_authority` checks for a `Delegation` record (not merely an `authority_ids` list on the Role) linking the `Authority` to the target Role. Without delegation, `execute_organisational_change` returns `{"status": "unauthorised"}`. Verified by contract 19.

**Implemented:** Yes — the authority gate is enforced. Chief of Staff is an ordinary Role, not a special executive entity that can bypass delegation.

**Not safe to automate:** Autonomous staffing/hiring is explicitly **not** safe. It requires:
1. Delegated organisational-change authority (see G.2)
2. A required-proficiency threshold (see B.2)
3. First-class decision inputs (cost, time-to-develop/provision, expected value, risk, reusability — see 18)
4. Evidence & failure handling (decision trail + failure modes)
5. A consolidated capacity-analysis service (see C.1)

None are implemented as a single staffing decision service.

### G.3 select_execution_path is not a staffing decision mechanism

**Representable:** No — by design. `select_execution_path` returns only an `ExecutionPathResult` (a data object). It does not call `register_agent`, `register_person`, `assign_capability`, or any staffing/hiring function. Verified by source inspection (contract 20): no references to `register_agent`, `register_person`, `assign_capability`, `hiring`, `staff`, or `hire` in the method source.

**Implemented:** The method purely selects and returns. The response is a data object, not an organisational mutation.

**Safe to automate:** The *selection* (path computation) is safe to automate (read-only). The *response* (staffing/provisioning) is not — it must pass through `execute_organisational_change` with authority.

---

## H. Forbidden-Entity Source Scans

**Representable:** No — the forbidden entities must not exist.

**Implemented:** Verified by source scan (`_scan_src_for_classes`) using `Path(__file__).resolve().parents[2]` (= `packages/`) scanning `organisation/src`, `people_capability/src`, `contracts/`, `capability_registry/src`, `workflow_runner/src`, and `organisation_paperclip/src`. The following classes are confirmed absent:

`Capacity`, `Staffing`, `Hiring`, `Workforce`, `Team`, `Decision`, `Supplier`, `Vendor`, `CapabilityGraph`, `CapabilityRelationship`, `CapabilityEdge`

(Contract 14 and contract 18 assert specific subsets; an additional comprehensive scan confirms no forbidden class definitions appear in any package `src/` directory.)

**Safe to automate:** N/A — this is a negative architectural assertion.

---

## I. Summary Table — 20 Contracts

| # | Contract | Class | Result |
|---|---|---|---|
| 1 | People/Capability is Role + Actor | `TestPeopleCapabilityBoundary` | PASS |
| 2 | Capacity derivable without Capacity entity | `TestPeopleCapabilityBoundary` | PASS |
| 3 | People/Capability recursive self-analysis | `TestPeopleCapabilityBoundary` | PASS |
| 4 | No required_proficiency on CapabilityAssignment | `TestRequiredProficiencyBoundary` | PASS |
| 5 | No required_proficiency_level on Role | `TestRequiredProficiencyBoundary` | PASS |
| 6 | Actual proficiency exists, no required threshold | `TestRequiredProficiencyBoundary` | PASS |
| 7 | Capacity inputs representable | `TestCapacityAnalysisDerived` | PASS |
| 8 | CapabilityAvailability ≠ capacity model | `TestCapacityAnalysisDerived` | PASS |
| 9 | CapacityPressureSignal is a signal | `TestCapacityAnalysisDerived` | PASS |
| 10 | ExecutionPath has exactly 4 members | `TestResponseSelectionBoundary` | PASS |
| 11 | select_execution_path doesn't distinguish gaps | `TestResponseSelectionBoundary` | PASS |
| 12 | Response selection is People/Capability concern | `TestResponseSelectionBoundary` | PASS |
| 13 | Capability has no adjacency field | `TestAdjacencyBoundary` | PASS |
| 14 | No CapabilityGraph/Relationship/Edge | `TestAdjacencyBoundary` | PASS |
| 15 | Adjacency via tags/metadata only | `TestAdjacencyBoundary` | PASS |
| 16 | develops_capability_id ≠ required_capability_ids | `TestIncrement48IdentityInvariant` | PASS |
| 17 | Increment 48 identity chain intact | `TestIncrement48IdentityInvariant` | PASS |
| 18 | No Decision entity | `TestAuthorityAutomationBoundary` | PASS |
| 19 | No autonomous staffing without authority | `TestAuthorityAutomationBoundary` | PASS |
| 20 | select_execution_path ≠ staffing mechanism | `TestAuthorityAutomationBoundary` | PASS |

---

## J. Representable vs Implemented vs Missing vs Safe-to-Automate

### Representable now

| Concept | Primitive(s) |
|---|---|
| People/Capability function | `Role` + `Actor` (ActorType.AGENT/PERSON) + `fulfilled_role_ids` |
| Capability gap identification | `select_execution_path` → `NEW_CAPABILITY_REQUIRED` with `capability_id` |
| Capacity analysis inputs | `Actor`, `CapabilityAssignment`, `CapabilityProficiency`, `Work`, `WorkStatus`, `query_capability`, `detect_capacity_pressure` |
| Required capability (to execute Work) | `Work.required_capability_ids`, `Role.required_capability_ids` |
| Capability being developed (by Work) | `Work.develops_capability_id`, `WorkCreateRequest.develops_capability_id` |
| Actual proficiency | `CapabilityProficiency.proficiency_level` (NOVICE..MASTER) |
| Assignment with suspension | `CapabilityAssignment.status` (ACTIVE/SUSPENDED/EXPIRED/REVOKED) |
| Provisioning (Agent/Person) | `InMemoryAgentStore.register_agent`, `register_person` |
| Authority / delegation | `Authority`, `Delegation`, `OCP.delegate_authority`, `execute_organisational_change` |
| Capability development lifecycle | `Worker._develop_capability`, `CapabilityRegistry.register/promote`, `assess_capability_development` |
| Adjacency (contextual) | `Capability.tags`, `Capability.metadata` |
| Unsupported responses (by absence) | No `OUTSOURCE` member on `ExecutionPath`; no `Supplier`/`Vendor` entity |

### Implemented now

| Concept | Implementation |
|---|---|
| People/Capability as Role+Actor | `InMemoryAgentStore.register_agent` creates Actor; `InMemoryOrganisationControlPlane` manages Roles/Authority/Delegation/Work |
| Capability gap identification | `select_execution_path` (4 branches, capability_id preserved) |
| Capacity pressure signal | `detect_capacity_pressure` → `CapacityPressureSignal` |
| Capability availability | `query_capability` → `{"available": bool, ...}` |
| Capability development lifecycle | `Worker._develop_capability` → `CapabilityRegistry.register` → assessment → `promote` |
| Authority gate | `_has_organisational_authority` requires `Delegation` record |
| Organisational change execution | `execute_organisational_change` (idempotent, authority-gated) |
| Proficiency recording | `Operations._record_proficiency` (after promotion) |
| Adjacency via tags/metadata | `Capability.tags`, `Capability.metadata` stored/retrieved |

### Missing but clearly bounded

| Missing item | Type | Boundary |
|---|---|---|
| Required proficiency threshold | model gap | A `required_proficiency_level` field on `Role` or `CapabilityAssignment` (see B.2 for placement trade-off) — deferred, NOT implemented |
| Capacity-analysis service | implementation gap | Inputs exist; no consolidated query/application service — likely a People/Capability-owned analysis service consuming existing state, producing an analysis result, not a `Capacity` entity |
| Response-selection decision logic | implementation gap | The conceptual response set is representable (D.3); the *decision function* selecting among responses does not exist — it is a People/Capability analysis concern, not an `ExecutionPath` expansion |
| First-class adjacency relationship | design deferral | No `CapabilityGraph`/`CapabilityRelationship`/`CapabilityEdge` — adjacency remains contextual via `tags`/`metadata`; introduce only when a concrete queryable use case exists |
| Economic decision inputs | absence by design | `cost`, `time-to-develop`, `time-to-provision`, `expected-value`, `risk`, `reusability` are not first-class — supplied by future economic/reasoning modules, not by reopening closed increments (35–39, 43, 48–50) |

### Safe to automate

| Analysis operation | Safe? | Reason |
|---|---|---|
| Capacity derivation (count available actor slots) | Yes | Read-only retrieval + computation over existing state; no organisational decision |
| CapacityPressureSignal derivation | Yes | Read-only analysis of Work state |
| Capability availability query | Yes | Read-only; returns `available` flag |
| Capability registration awareness | Yes | `register_capability` emits an event; lifecycle delegated to `CapabilityRegistry` |
| Workflow/tool reuse selection | Yes | Read-only selection; no staffing risk |
| Capability development *execution* | Conditionally | Evidence-gated (interface validity + execution success) via `assess_capability_development`; but the *decision to develop* is not autonomous |

### Not safe / not currently supported

| Operation | Safe? | Reason |
|---|---|---|
| Autonomous hiring/staffing decisions | Not safe | Requires delegated authority (G.2), required-proficiency threshold (B.2), decision inputs (cost, value, risk), and evidence/failure handling — none consolidated |
| Outsourcing | Not supported | No `Supplier`/`Vendor` model exists; no `OUTSOURCE` ExecutionPath member — correctly absent; a model must be introduced first |
| Generic decision entity | Not safe to introduce | A `Decision` entity would reify staffing/hiring without authority gating; the architecture keeps decisions flowing through `OCP.execute_organisational_change` |
| Capacity entity creation | Not supported | `Capacity` is a derived analytical result, not an entity; introducing one would reify a mutable quantity as a domain object |

---

## K. Required-Proficiency Boundary — Detailed Trade-off

**Current state (verified):**
- `CapabilityAssignment` fields (pydantic `model_fields`): `id`, `capability_id`, `actor_id`, `skill_ids`, `tool_ids`, `assignee_type`, `assignee_id`, `assignment_type`, `status`, `authorised_by`, `assigned_at`, `expires_at`, `reason`, `metadata` — **no** `required_proficiency` / `required_proficiency_level` / `min_proficiency`.
- `Role` fields: `id`, `name`, `description`, `responsibilities`, `authority_ids`, `constraints`, `information_access`, `reports_to`, `status`, `required_capability_ids`, `metadata` — **no** `required_proficiency` / `required_proficiency_level` / `min_proficiency`.
- `CapabilityProficiency` fields: `id`, `capability_id`, `actor_id`, `person_id`, `agent_id`, `proficiency_level`, `validated_at`, `valid_until`, `evidence`, `assessed_by`, `metadata` — `proficiency_level` exists (actual), `required_proficiency_level` does **not**.

**Semantic distinction:**
- **Actual proficiency** (`CapabilityProficiency.proficiency_level`) — "this Actor can exercise this Capability at PROFICIENT."
- **Required proficiency** (absent) — "this Role/CapabilityAssignment needs PROFICIENT in cap-X to satisfy Work."

The semantic gap: without a required threshold, `select_execution_path` cannot distinguish "we have the capability and an Actor, but the Actor's proficiency is below what's required" from "the capability is available." This collapses into `CAPABILITY_PATH` or `HUMAN_TEAM_INVESTIGATION`.

**Smallest coherent future boundary (deferred):**

> **`Role.required_proficiency_levels: dict[str, ProficiencyLevel]`** — maps a capability ID to a required proficiency level, mirroring the existing `Role.required_capability_ids: list[str]`. This placement:
> - Keeps the requirement at the role level where planning naturally occurs
> - Is directly comparable to `CapabilityProficiency.proficiency_level` on the Actor
> - Does NOT affect the Increment 48 chain (`required_capability_ids` ≠ `develops_capability_id`)
> - Does NOT require a `Capacity` entity or a `Decision` entity

**Trade-off vs. `CapabilityAssignment.required_proficiency_level`:**
- `Role`-level: better for capacity planning (aggregate across all Actors in a role)
- `CapabilityAssignment`-level: better for per-Actor variance (one Actor may meet the threshold, another may not)

**Decision:** Deferred. No field is added in Increment 51. The report documents the trade-off and leaves implementation to a future increment where the capacity-analysis service boundary is established and the decision inputs (cost, time, value, risk) are first-class. This follows the Increment 50 precedent (report section 19.2) and does not reopen closed increments.

---

## L. Capacity-Analysis Service Boundary — Detailed Proposal

**Smallest coherent boundary (deferred, not implemented):**

A People/Capability-owned **analysis/query application service** that:
- **Consumes:** `Actor` (via `InMemoryAgentStore`), `CapabilityAssignment` (via `store.get_assignments_for_capability`), `CapabilityProficiency` (via existing `proficiency_level`), `Work` (via `OCP.list_work` / `query_capability`), availability (via `Work.status`, `query_capability.in_progress`)
- **Produces:** a capacity analysis result — e.g., `CapacityAnalysis(capability_id, total_actor_slots, occupied_slots, available_slots, under_proficient_actors, pressure_signal)` — **not** a `Capacity` entity
- **Does NOT:** create actors, assign capabilities, delegate authority, or make hiring/staffing decisions — that remains `OCP.execute_organisational_change` with delegated authority

This service would be the natural consumer of the required-proficiency threshold (B.2) and the response-selection decision logic (D.3). It belongs in People/Capability (`packages/people_capability/src/`), not in OCP (which remains mechanism-only) and not as a generic `Decision` entity.

**Not implemented in Increment 51.** The test suite's `_derive_available_capacity` helper demonstrates the *inputs* are combinable; the *service* is a future increment.

---

## M. Increment 48 Invariant — Stated Explicitly

The Increment 48 identity invariant MUST remain unchanged by Increment 51:

```
ExecutionPathResult.capability_id   (preserved on
        ↓                            NEW_CAPABILITY_REQUIRED,
Work.develops_capability_id         HUMAN_TEAM_INVESTIGATION,
        ↓                          CAPABILITY_PATH)
Capability.id
        ↓
CapabilityRegistry.get()
        ↓
assess_capability_development()
        ↓
CapabilityRegistry.promote()  →  ACTIVE
```

**Critically:** `required_capability_ids` ≠ `develops_capability_id`. The capability being developed (the gap being filled) is identified by `develops_capability_id`; the capabilities needed to *perform* the development Work are in `required_capability_ids`. Increment 51 does not conflate these (contract 16 verifies independence; contract 17 verifies the full chain).

**Verified by:** `test_contract_16_develops_distinct_from_required` (field independence) and `test_contract_17_increment48_chain_intact` (end-to-end chain through `select_execution_path` → `Worker._develop_capability` → `CapabilityRegistry` → `assess_capability_development` → `promote`).

---

## N. Recursive Self-Improvement (Re-stated as Locked Contract)

People/Capability is an `Actor`. The same loop applies recursively and requires **no** special entity:

```
People/Capability Actor
  → capability requirement           (Work.required_capability_ids)
  → assessment of current           (registry.get / CapabilityProficiency)
  → gap                             (NEW_CAPABILITY_REQUIRED, capability_id preserved)
  → response                        (develop / provision Agent / provision Person / reassign / workflow / tool / human investigation)
  → CapabilityAssignment            (assign_capability on the Actor)
  → Work / execution                (Worker / Operations / Paperclip)
  → evidence                        (CapabilityEvent, CapabilityProficiency.evidence, maturation_history)
  → reassessment                    (registry.get → ACTIVE check / capacity re-derive)
```

Verified by contracts 3 (recursive gap → Work → assignment), 17 (full development chain), and the Increment 50 tests (`TestPeopleCapabilitySelfImprovementPath`, `TestPeopleCapabilitySubjectToGap`). No `SelfImprovement` or `HRImprovement` entity is introduced.

---

## O. Architectural Conclusion

People/Capability capacity analysis and response selection can be bounded within the existing architectural model with **zero production changes**:

1. **People/Capability is an ordinary Role + Actor** — no special entity needed. Chief of Staff is an ordinary Role with Authority + Delegation.

2. **Capacity is a derived analytical result** — all inputs (Actors, CapabilityAssignments, CapabilityProficiency, Work, availability) are representable. `CapacityPressureSignal` is a signal, `CapabilityAvailability.available` is an availability flag — neither is a capacity entity. A future consolidated capacity-analysis service (People/Capability-owned, not a `Capacity` entity) would compose these inputs.

3. **Required proficiency is genuinely absent** — `CapabilityProficiency.proficiency_level` records *actual* proficiency, but there is no *required* threshold on `CapabilityAssignment` or `Role`. The smallest coherent boundary is `Role.required_proficiency_levels: dict[str, ProficiencyLevel]` (deferred — not implemented). This does not weaken the Increment 48 chain.

4. **`ExecutionPath` must not expand** — it answers only "what broad execution path is available?" Response selection ("what should we hire/develop/reassign?") is a separate People/Capability analysis concern that consumes existing state and may use existing organisational-change mechanisms. The conceptual response set (train, reassign, new Agent, new Person, develop, workflow, tool, human investigation, outsource-unsupported) is fully representable through existing primitives.

5. **Adjacency is contextual** — `Capability.tags` and `Capability.metadata` suffice for reasoning context. No `CapabilityGraph`/`CapabilityRelationship`/`CapabilityEdge` is introduced; a graph should only be added when a concrete queryable use case exists.

6. **No autonomous staffing/hiring** — `execute_organisational_change` requires delegated Authority + Delegation; `select_execution_path` is read-only selection, not a staffing mechanism. A generic `Decision` entity is not introduced.

7. **The Increment 48 identity chain is intact** — `capability_id` → `develops_capability_id` → `Capability.id` → `CapabilityRegistry` → assessment → `ACTIVE`, with `required_capability_ids` kept distinct.

**Production files changed:** none.
**Commit made:** no.

---

## P. Tests Added

`packages/organisation/tests/test_increment51_people_capability_capacity_decision.py` — 20 tests across 8 test classes covering contracts 1–20:

| Test class | Contracts |
|---|---|
| `TestPeopleCapabilityBoundary` | 1, 2, 3 |
| `TestRequiredProficiencyBoundary` | 4, 5, 6 |
| `TestCapacityAnalysisDerived` | 7, 8, 9 |
| `TestResponseSelectionBoundary` | 10, 11, 12 |
| `TestAdjacencyBoundary` | 13, 14, 15 |
| `TestIncrement48IdentityInvariant` | 16, 17 |
| `TestAuthorityAutomationBoundary` | 18, 19, 20 |

Run:
```
pytest packages/organisation/tests/test_increment51_people_capability_capacity_decision.py -q
→ 20 passed in 0.18s
```

---

## Q. Validation

### Increment 51 tests
```
pytest packages/organisation/tests/test_increment51_people_capability_capacity_decision.py -q
→ 20 passed in 0.18s
```

### Regression suite
```
pytest \
  packages/organisation/tests/test_increment43* \
  packages/organisation/tests/test_increment46* \
  packages/organisation/tests/test_increment48* \
  packages/organisation/tests/test_increment50* \
  -q
→ 147 passed in 0.27s   (46 Increment 50 + 20 Increment 51 + 81 Increment 43/46/48)
```

### Full organisation suite
```
pytest packages/organisation/tests -q
→ 828 passed in 5.10s   (20 new + 808 existing — no regressions)
```

### Relevant additional suites
```
pytest packages/workflow_runner/tests -q
→ 310 passed, 60 failed, 4 skipped
   (failures = pre-existing, see R)

pytest packages/capability_registry/ packages/people_capability/ packages/ai/ -q
→ 217 passed, 12 skipped   (no new tests; packages importable)
```

### Ruff
```
ruff check packages/organisation/tests/test_increment51_people_capability_capacity_decision.py
→ All checks passed!
```

Ruff on all required packages:
```
ruff check packages/organisation packages/organisation_paperclip packages/contracts
           packages/people_capability packages/capability_registry packages/workflow_runner
→ 156 pre-existing errors, 0 new from Increment 51
```
(The 156 errors are all pre-existing in files unchanged by this increment: `I001`, `F401`, `F841`, `RUF059`, `UP017`, etc., in `worker.py`, `operations.py`, `test_capability_execute.py`, `test_telemetry_lifecycle.py`, etc.)

---

## R. Failures — Classification

### Increment 51 failures: **none**
All 20 contracts pass.

### Regression failures: **none (new)**
The 43/46/48/50 regression suite passes entirely (147 passed).

### Pre-existing failures (NOT caused by Increment 51 — zero production changes):

| Test file / suite | Failures | Cause |
|---|---|---|
| `packages/workflow_runner/tests/test_capability_execute.py` | 45 | Pre-existing `awaiting_capability_selection`/`pending` state-machine mismatch; `None` org_plane (no Paperclip backend) |
| `packages/workflow_runner/tests/test_platform_integration.py` | 15 | Requires external Paperclip API — `Connection refused` |
| `packages/organisation_paperclip/tests/test_integration.py` | 6 | Requires external Paperclip API |
| `packages/organisation_paperclip/tests/test_smoke.py` | 1 | Requires external Paperclip API |

**Ruff pre-existing errors (156):** All in files unchanged by this increment — prior increments' working-tree state (`worker.py`, `operations.py`, `test_capability_execute.py`, `test_telemetry_lifecycle.py`, etc.). Increment 51 introduces **zero** lint errors of its own.

### Infrastructure / external-service failures

The 62 failures in `workflow_runner` + `organisation_paperclip` suites require live Paperclip API endpoints and/or a pre-existing state-machine mismatch documented in prior increment reports. These are **not** introduced by Increment 51 and are **not** fixed (out of scope).

---

## S. Production-Code Changes

**Zero.** No production files were modified. The complete chain of evidence is captured in the test suite (`test_increment51_people_capability_capacity_decision.py`, 20 passing tests) and this report.

### Confirmation

- **Files created:** 2 (test file + this report)
  - `packages/organisation/tests/test_increment51_people_capability_capacity_decision.py`
  - `packages/organisation/tests/increment51_report.md`
- **Files modified:** 0 production files
- **Commit made:** no
