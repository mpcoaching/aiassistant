# Increment 50 — People/Capability as an Organisational Capacity Function

**Increment type:** Investigation-only (no production-code changes).
**Objective:** Establish whether People/Capability can function as the organisational capacity function using existing primitives (Role / Authority / Delegation / Assignment / Work / Agent / Person / Actor / CapabilityAssignment / CapabilityProficiency / CapabilityExecution / CapabilityRegistry + OCP + Operations + Paperclip).
**Executive summary:** Yes — the existing domain model can express every facet of the People/Capability capacity function as an ordinary organisational function. No HR-specific entity (Employee, Workforce, Capacity, Hiring, Recruitment, Staffing, Team, Supplier, Vendor, Decision) is required. What is *representable* is largely *not* *implemented* as a single capacity-analysis service, and nothing is *safe to automate* yet. The gaps are implementation and governance gaps, not architectural gaps.

This report distinguishes three states for every finding:

- **Architecturally representable** — the existing domain model can express the concept/state/relationship.
- **Operationally implemented** — executable code currently supports the behaviour.
- **Safe to automate** — the architecture has enough authority, validation, evidence, failure handling and controls that autonomous execution would be appropriate.

A model being *representable* does NOT imply autonomous hiring/staffing is implemented or safe.

---

## A. Can People/Capability operate as an organisational capacity/capability function using existing primitives?

**Representable:** Yes. People/Capability is an ordinary `Role` (`packages/organisation/src/role.py`) reali

zed by a uniform `Actor` (`packages/people_capability/src/actor.py`) that references a `Person` or `Agent` via `ActorType` (`PERSON`/`AGENT`). The function's responsibilities map onto existing primitives:

| Responsibility | Primitive |
|---|---|
| hold required capability | `CapabilityAssignment` (`people_capability/src/capability_assignment.py`) |
| hold proficiency level | `CapabilityProficiency` (`people_capability/src/capability_proficiency.py`) |
| exercise capability | `Work` + `Assignment` (`role.py`) |
| register/promote capability lifecycle | `CapabilityRegistry` (`capability_registry/src/capabilities.py`) |
| organisational context / authority | `OrgContext`, `Authority`, `Delegation` |
| trigger organisational change | `OCP.execute_organisational_change()` |
| detect demand pressure | `OCP.detect_capacity_pressure()` → `CapacityPressureSignal` |

**Implemented:** The primitives above all have executable in-memory implementations (`InMemoryOrganisationControlPlane`, `InMemoryAgentStore`, `CapabilityRegistry` with a repository).

**Safe to automate:** No. There is no authority-validated, evidence-gated capacity-decision service. The function should not be autonomous.

## B. Can it identify capability gaps?

**Representable:** Yes. `OCP.select_execution_path()` returns `ExecutionPath.NEW_CAPABILITY_REQUIRED` with `capability_id` preserved when a required capability is not registered (the gap identity). This is the gap-identification label — **not** a commitment to develop.

**Implemented:** Yes — `InMemoryOrganisationControlPlane.select_execution_path` (with and without a `capability_query` callback). `Worker._develop_capability` generates `cap-{work.id}` only when no identity exists.

**Safe to automate:** No for gap identification alone (it is a detection signal); the *response* is not automated.

## C. Can it analyse capacity without a Capacity entity?

**Representable:** Yes. Capacity is a derived analytical result, not an entity. The representable inputs are:

```
Actors                       (Actor / find_actors_for_role / list_actors)
  + CapabilityAssignments    (get_assignments_for_actor / get_assignments_for_capability / actor_has_capability)
  + CapabilityProficiency    (ProficiencyLevel)
  + current Work / assignments (Work.required_capability_ids, WorkStatus, OCP.list_work / query_capability)
  + availability/allocation  (Work.status IN (READY/ASSIGNED/IN_PROGRESS) — query_capability.in_progress; detect_capacity_pressure)
  =
available / required capacity analysis
```

`CapacityPressureSignal` (`contracts/organisational_events.py`) is a **signal**, not an entity — it is a derived indicator.

**Implemented:** Partially. `query_capability()` and `detect_capacity_pressure()` exist and are tested, but there is **no consolidated capacity-analysis function**. A capacity analyst would have to compose the inputs above; the architecture provides the inputs, not the analysis service.

**Safe to automate:** No — the analysis service does not exist and is not evidence-gated.

## D. Can it assess proficiency?

**Representable:** Yes. `CapabilityProficiency` records `actor_id` + `capability_id` + `ProficiencyLevel` (NOVICE/COMPETENT/PROFICIENT/EXPERT/MASTER) + evidence + validity windows.

**Implemented:** Yes — the model exists and is written by `Operations._record_proficiency` (after an `ACTIVE` promotion). No assessment *service* exists to compare required vs current proficiency; that is a future analytical function.

**Safe to automate:** No — proficiency comparison is not implemented or gated.

## E. Can it determine whether an existing Actor should be developed?

**Representable:** Yes. "Develop" = `capability_development` `Work` with `develops_capability_id`, executed through `Worker._develop_capability` → `CapabilityRegistry.register` (DRAFT) → assessment → `promote` (ACTIVE) → `CapabilityProficiency` recorded for the developing Actor.

**Implemented:** Yes (the Increment 48 lifecycle is fully executable end-to-end with a `CapabilityRegistry`).

**Safe to automate:** No — the decision to develop (vs. reassign/provision) is not automated; only execution of a developer-chosen path is.

## F. Can it determine whether an existing Actor should be reassigned?

**Representable:** Yes. `CapabilityAssignment` has `AssignmentStatus` (ACTIVE/SUSPENDED/EXPIRED/REVOKED) and `AssignmentType` (PRIMARY/SECONDARY/BACKUP); `assign_capability` / `get_assignments_for_actor` enable reassign-by-suspend/activate.

**Implemented:** Yes — the assignment model and store operate; OCP `Assignment` links Work to assignees.

**Safe to automate:** No — no decision logic selects reassignment.

## G. Can it determine whether additional capacity is required?

**Representable:** Yes. A future decision function can consume: required capability + required proficiency + current proficiency + current capacity (derived per C) + workload (in-progress Work) + candidate Actors (Agents/Persons) + cost/effort (not yet represented — see M) + time-to-develop (not represented) + expected value / risk / reusability / adjacency (not represented — see M).

**Implemented:** No decision function exists.

**Safe to automate:** No.

## H. Can it provision a new Agent?

**Representable:** Yes. `Role` + `Agent` (registered via `InMemoryAgentStore.register_agent`) + automatically-created `Actor` (ActorType.AGENT) + `CapabilityAssignment`. Paperclip `create_agent` maps an Agent to a Role for execution.

**Implemented:** Yes — `InMemoryAgentStore.register_agent` / Paperclip `create_agent`.

**Safe to automate:** No — provisioning is not gated by authority evidence or cost analysis.

## I. Can it provision a new Person?

**Representable:** Yes. `Role` + `Person` (registered via `InMemoryAgentStore.register_person`) + automatically-created `Actor` (ActorType.PERSON) + `CapabilityAssignment`. Person and Agent are symmetric through the Actor boundary (see J).

**Implemented:** Yes — `InMemoryAgentStore.register_person`.

**Safe to automate:** No.

## J. Can it assign the required capability?

**Representable:** Yes. After provisioning, `store.assign_capability(actor_id, capability_id)` creates a `CapabilityAssignment`; the Actor exercises the capability through `Work` assigned to it.

**Implemented:** Yes.

**Safe to automate:** No — assignment is not authority-gated in a capacity-decision flow.

## K. Can it invoke existing organisational-change mechanisms?

**Representable:** Yes. `OCP.execute_organisational_change(work, assignee_actor, role=None, capability_ids=None)` drives `Work → Role → Actor → CapabilityAssignment` through the public OCP interface; `assign_work` accepts `Actor | Role | Person | Agent` uniformly.

**Implemented:** Yes — `InMemoryOrganisationControlPlane.execute_organisational_change` (with idempotency and idempotency-key behaviour).

**Safe to automate:** Only when authority is delegated (see L); never unconditionally.

## L. Can it respect Authority and Delegation?

**Representable:** Yes. `Authority` + `Delegation` gate `execute_organisational_change`: `_has_organisational_authority` requires a `Delegation` record (not merely an `authority_id` on the Role) linking the authority to the target Role.

**Implemented:** Yes — verified by `execute_organisational_change` returning `unauthorised` when no delegation exists, and `executed` when one does.

**Safe to automate:** Yes for the *gate* itself; the gate is the precondition for any safe automation.

## M. Can it develop a missing capability through the Increment 48 lifecycle?

**Representable:** Yes. The full chain is intact (see N).

**Implemented:** Yes (end-to-end tested in `test_increment48` and re-verified in Increment 50).

**Safe to automate:** Conditionally — a capability-development Work is fail-fast-failed by `Operations` when no `CapabilityRegistry` is wired; assessment (`assess_capability_development`) gates DRAFT→ACTIVE promotion on interface validity + successful execution. The lifecycle is evidence-gated, but the *decision to develop* is not autonomous.

## N. Can it use an existing Workflow or Tool where appropriate?

**Representable:** Yes. `ExecutionPath.EXISTING_WORKFLOW` (selected when `workflow_lookup` returns a match) and `ExecutionPath.CAPABILITY_PATH` with `CapabilityKind.TOOL` are first-class outcomes of `select_execution_path`.

**Implemented:** Yes — both branches are exercised by tests.

**Safe to automate:** Yes for *workflow/tool reuse* (it is read-only selection, no HR implication). The selection itself carries no hiring/staffing risk.

## O. Can it identify unsupported responses such as outsourcing?

**Representable:** Yes — by explicit *absence*. The supported set is `ExecutionPath = {EXISTING_WORKFLOW, CAPABILITY_PATH, NEW_CAPABILITY_REQUIRED, HUMAN_TEAM_INVESTIGATION}`. There is **no** `OUTSOURCE` member and **no** `Supplier`/`Vendor` entity anywhere in `organisation`, `people_capability`, or `contracts` source (verified by source scan in the test suite).

**Implemented:** Yes — the unsupported response is identifiable precisely because nothing represents it.

**Safe to automate:** N/A (it is correctly *not* automated; outsourcing requires a Supplier/Vendor model that does not exist).

---

## 1. Can People/Capability operate as an organisational capacity/capability function using existing primitives?

Yes. It is an ordinary `Role` + `Actor` exercising `CapabilityAssignment`/`CapabilityProficiency`/`Work`/`CapabilityRegistry`/`OCP.execute_organisational_change()`. See sections A and K. *Representable & implemented as primitives; not safe to automate.*

## 2. Can it identify capability gaps?

Yes — `select_execution_path` returns `NEW_CAPABILITY_REQUIRED` with the gap `capability_id` preserved (B).

## 3. Can it analyse capacity without a Capacity entity?

Yes, as a derived analytical result (C). `CapacityPressureSignal` is a signal, not an entity. No consolidated analysis service exists — that is a genuine implementation gap, not an architectural one.

## 4. Can it assess proficiency?

Yes via `CapabilityProficiency` (D). A proficiency-comparison service does not exist (implementation gap).

## 5. Can it determine whether an existing Actor should be developed?

Yes, representably and via the Increment 48 lifecycle (E, M). The *decision* to develop is not automated.

## 6. Can it determine whether an existing Actor should be reassigned?

Yes, representably via `CapabilityAssignment` status transitions (F). The *decision* is not automated.

## 7. Can it determine whether additional capacity is required?

Yes, representably — the inputs exist (G). The decision function does not (see M for missing inputs).

## 8. Can it provision a new Agent?

Yes (H).

## 9. Can it provision a new Person?

Yes (I).

## 10. Can it assign the required capability?

Yes (J).

## 11. Can it invoke existing organisational-change mechanisms?

Yes (K).

## 12. Can it respect Authority and Delegation?

Yes — delegation is required, not merely authority (L).

## 13. Can it develop a missing capability through the Increment 48 lifecycle?

Yes (M).

## 14. Can it use an existing Workflow or Tool where appropriate?

Yes (N).

## 15. Can it identify unsupported responses such as outsourcing?

Yes — outsourcing is explicitly absent: no `OUTSOURCE` path and no `Supplier`/`Vendor` entity (O).

## 16. Can People/Capability itself be subject to the same capability-development loop?

Yes (recursive self-improvement is representable). People/Capability is an ordinary `Actor`, so a gap in its own capability is detected by the same `select_execution_path` → `NEW_CAPABILITY_REQUIRED` → `capability_development` Work → `develops_capability_id` → `Worker._develop_capability` → registry → `promote` → `CapabilityProficiency` chain. No `SelfImprovement` or `HRImprovement` entity is introduced (see `TestPeopleCapabilitySelfImprovementPath`).

## 17. What is genuinely missing?

| Missing item | Type | Notes |
|---|---|---|
| Consolidated capacity-analysis service | implementation | Inputs exist (C); no function composes them. |
| Proficiency comparison service | implementation | `CapabilityProficiency` exists; no service compares required vs current. |
| "What should we hire?" decision function | not represented | Decision inputs (cost, time-to-develop/provision, expected value, risk, reusability, adjacency) are **not** first-class in the model. See 18. |
| Supplier/Vendor model | representable-as-absent | Outsourcing correctly has no model (O). |

## 18. What is merely not implemented yet?

All of the above decision services. Nothing requires reopening Increments 35–39 or adding HR/staffing/capacity entities. The "what to hire" reasoning is a future service over existing inputs plus a few missing economic inputs.

### Inputs the "what should we hire" question requires

| Input | Representable in current model? |
|---|---|
| required capability | Yes — `Work.required_capability_ids` / `Role.required_capability_ids` |
| required proficiency | Partially — `CapabilityAssignment` references a capability but not a *required* proficiency level (no field for "this role needs PROFICIENT in cap-X"). |
| current proficiency | Yes — `CapabilityProficiency` |
| current capacity | Derivable (C) |
| required capacity | Derivable only if "required" is expressed as demand (in-progress + queued Work per capability) — present as `detect_capacity_pressure` |
| workload | Yes — `Work.status` / `query_capability` in-progress |
| cost | **Not represented** |
| time to develop | **Not represented** |
| time to provision | **Not represented** |
| expected value | **Not represented** |
| risk | **Not represented** |
| reusability | **Not represented** |
| adjacent capabilities | **Not represented** |

Missing economic/decision inputs (cost, time, value, risk, reusability, adjacency) are genuine *absences* — they are absent by design at this layer and would be supplied by future economic/reasoning modules, not by reopening closed increments.

## 19. What would need to exist before automatic organisational staffing/hiring could safely be implemented?

Before safe autonomous staffing/hiring:

1. **Authority-gated decision authority.** A Role with delegated organisational-change authority and bounded scope (already representable, L) must *authorise* staffing decisions; autonomy without delegation is out.
2. **Required-proficiency expression.** `CapabilityAssignment` / `Role` need a "required proficiency level" field so "we have the capability but insufficient proficiency" is distinguishable from "we don't have the capability" (see capability-definition distinctions in section P).
3. **Decision inputs as first-class state.** Cost, time-to-develop/provision, expected value, risk, reusability, and adjacency must be representable on the entities the decision function consumes.
4. **Evidence & failure handling.** A decision trail that records *why* an Actor was hired/developed/reassigned, with failure modes (e.g., promotion failing, provisioning failing) handled explicitly rather than silently.
5. **Capacity-analysis service.** The derived capacity analysis (C) must be consolidated and authoritative, with SLA/queue signals feeding the decision.
6. **Outsourcing path.** A Supplier/Vendor model must exist before outsourcing is a *representable* (let alone automatable) response (O). It intentionally does not.

None of these require reopening Increments 35–39 or introducing a People/Capability subsystem. They extend existing primitives.

---

## P. Capability-definition distinctions

The architecture distinguishes the four cases through existing primitives:

- **"We don't have the capability"** → `select_execution_path` → `NEW_CAPABILITY_REQUIRED` (capability not in registry), `develops_capability_id` set (M).
- **"We don't yet understand what capability we need"** → `Work.description` + `Work.acceptance_criteria` + `Work.context` carry the unrefined need; once refined, a capability ID is allocated and the chain binds to it.
- **"We have the capability but insufficient proficiency"** → `Capability` exists (`CAPABILITY_PATH`), but no `CapabilityProficiency` (or a lower `ProficiencyLevel`) exists for the Actor → represented as a capability-development Work on proficiency/assignment, *not* a new capability.
- **"We have the capability and proficiency but insufficient capacity"** → `detect_capacity_pressure` / `query_capability` returns demand > capacity → `NEW_CAPABILITY_REQUIRED` is *not* the answer (capability exists); the answer is provisioning/reassignment, represented via additional `Agent`/`Person` + `CapabilityAssignment`.

The model does **not** introduce a `CapabilityDefinition` entity: `Capability`, `Work`, `context`, and `acceptance_criteria` already carry the semantics. Where a "required proficiency level" is not expressible on `CapabilityAssignment` (see 19.2), that is a genuine, bounded gap — not an excuse to invent a definition entity.

---

## Q. Authority / executive boundary

The executive/Chief of Staff layer establishes organisational requirements (e.g., "the organisation needs to be able to do X"). Chief of Staff is an **ordinary `Role`** (verified by `TestChiefOfStaffIsAnOrdinaryRole`), not an executive entity. It holds/derives authority through `Authority` + `Delegation` exactly like any Role. People/Capability *determines* what capability X means, what proficiency is required, what capacity is required, what exists, what the gap is, and what change is required — but it does so through the same mechanisms any Role uses. **OCP remains mechanism-only**; no executive reasoning was moved into OCP.

---

## R. Recursive self-improvement (re-stated as a locked contract)

People/Capability is an `Actor`. The same loop applies recursively and requires **no** special entity:

```
People/Capability Actor
  → capability requirement          (Work.required_capability_ids)
  → assessment of current           (registry.get / CapabilityProficiency)
  → gap                             (NEW_CAPABILITY_REQUIRED, capability_id preserved)
  → response                        (develop / provision Agent / provision Person / reassign / workflow / tool / human investigation)
  → CapabilityAssignment            (assign_capability on the Actor)
  → Work / execution                (Worker / Operations / Paperclip)
  → evidence                        (CapabilityEvent, CapabilityProficiency.evidence, maturation_history)
  → reassessment                    (registry.get → ACTIVE check / capacity re-derive)
```

Verified by `TestPeopleCapabilitySelfImprovementPath`, `TestPeopleCapabilitySubjectToGap`, and the Increment 48 invariant tests.

---

## S. Three-state summary

| Concern | Representable | Implemented | Safe to automate |
|---|---|---|---|
| People/Capability as Role+Actor | Yes | Yes | No |
| Capability-gap identification | Yes | Yes | No (signal only) |
| Capacity analysis (derived) | Yes | Partial (signals only) | No |
| Proficiency assessment/comparison | Yes (record) | Partial (record only) | No |
| Develop existing Actor (Increment 48) | Yes | Yes | Conditionally (execution only) |
| Reassign existing Actor | Yes | Yes | No (decision) |
| Provision new Agent | Yes | Yes | No |
| Provision new Person | Yes | Yes | No |
| Assign capability | Yes | Yes | No (decision) |
| Organisational change (OCP) | Yes | Yes | Only with delegated authority |
| Authority/Delegation gate | Yes | Yes | Yes (the gate) |
| Workflow / Tool reuse | Yes | Yes | Yes (read-only selection) |
| Outsourcing | Representable-as-absent | Yes (correctly absent) | N/A |

---

## T. Production-code changes in this increment

**Zero.** This is an investigation-only increment. No production files were modified. The full chain of evidence is captured in the test suite.

---

## U. Tests added

`packages/organisation/tests/test_increment50_people_capability_function.py` — 46 tests across 18 classes covering contracts 1–25 plus the executive boundary, recursive self-improvement, no-HR-entities source scan, and the Increment 48 identity invariant.

Run:
```
pytest packages/organisation/tests/test_increment50_people_capability_function.py
```

---

## V. Validation

### Increment 50 tests
```
pytest packages/organisation/tests/test_increment50_people_capability_function.py -q
→ 46 passed in 0.23s
```

### Regression suite
```
pytest packages/organisation/tests/test_increment48_capability_development_identity.py -q
→ passed

pytest packages/organisation/tests/test_increment46_capability_gap_people_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment45_work_event_lifecycle.py -q
→ passed

pytest packages/organisation/tests/test_increment44_organisational_change_semantics.py -q
→ passed

pytest packages/organisation/tests/test_increment43_organisation_change_execution.py -q
→ passed
```

Note on the requested `test_increment49_capability_gap_response.py` regression: **this file does not exist** in the repository. Per the Increment 48 report, Increment 49 was a *planning-only* increment (its report notes it was not implemented with tests); the corresponding file is absent (`find` returns nothing). The closest implemented capability-gap tests are `test_increment46_capability_gap_people_boundary.py`, which is included above and passes. `test_increment47_*` is likewise planning-only and absent.

### Full available suites
```
pytest packages/organisation/tests/ -q
→ 808 passed in 5.10s   (46 new + 762 existing — no regressions)

pytest packages/workflow_runner/tests/ -q
→ 310 passed, 60 failed, 4 skipped   (failures = pre-existing, see below)

pytest packages/capability_registry/ packages/people_capability/ packages/ai/ -q
→ 217 passed, 12 skipped   (no new tests; packages importable)
```

Note: `people_capability` and `capability_registry` have no dedicated `tests/` directories of their own; they are exercised transitively through the organisation and workflow_runner suites above. `packages/ai` has no dedicated test directory either.

### Pre-existing failures (NOT caused by Increment 50 — zero production changes)
These fail because they require live external services (Paperclip API / platform integrations) and a pre-existing state-machine mismatch in files modified by prior increments. None of these files were touched by Increment 50.

| Test file | Failures | Cause |
|---|---|---|
| `packages/workflow_runner/tests/test_capability_execute.py` | 45 | Pre-existing `awaiting_capability_selection`/`pending` state-machine mismatch in a file modified by prior increments; `None` org_plane (no Paperclip backend) |
| `packages/workflow_runner/tests/test_platform_integration.py` | 15 | Requires external Paperclip API — `Connection refused` |
| `packages/organisation_paperclip/tests/test_integration.py` | 6 | Requires external Paperclip API |
| `packages/organisation_paperclip/tests/test_smoke.py` | 1 | Requires external Paperclip API |

Increment 50 introduces **no new failures** and **no production changes**; the pre-existing failures are identical before and after.

---

## W. Ruff

```
ruff check packages/organisation packages/organisation_paperclip packages/contracts
             packages/people_capability packages/capability_registry packages/workflow_runner
```
Respects `line-length = 100`, `target-version = "py311"` (from `packages/organisation/pyproject.toml`).

Result: the new test file passes with **0 errors**. The 156 errors reported across the packages are **all pre-existing**, in files unchanged by this increment (prior increments' working-tree state — `I001`, `F401`, `F841`, `RUF059`, `UP017`, etc., in `worker.py`, `operations.py`, `test_capability_execute.py`, `test_telemetry_lifecycle.py`, etc.). Increment 50 introduces **zero production changes** and adds no lint errors of its own.

```
ruff check packages/organisation/tests/test_increment50_people_capability_function.py
→ All checks passed!
```

---

## X. Architectural conclusion (final)

People/Capability can function as the organisation's capacity function using only existing primitives:

- It is **representably** and **implemented-as-primitives** a `Role` + `Actor` that uses `CapabilityAssignment`, `CapabilityProficiency`, `Work`, `CapabilityRegistry`, and `OCP.execute_organisational_change()`.
- It can **identify gaps**, **develop existing Actors** (Increment 48 lifecycle), **reassign Actors**, **provision Agents/Persons**, **assign capabilities**, **invoke organisational change**, and **respect Authority/Delegation** — all without any HR/staffing/capacity entity.
- **Capacity is a derived analytical result**, not a first-class Capacity entity. The inputs exist; a consolidated analysis service does not.
- **Recursive self-improvement** is representable because People/Capability is an ordinary Actor — no special self-improvement entity is needed.
- **Outsourcing is correctly unsupported** — there is no `Supplier`/`Vendor` model, and the response set has no `OUTSOURCE` path. Adding one would be a deliberate future decision, not an Increment 50 obligation.

**What remains before safe autonomous staffing/hiring:** a required-proficiency field on assignments/roles, first-class decision inputs (cost, time, value, risk, reusability, adjacency), a consolidated capacity-analysis service, an authority-gated decision service with evidence/failure handling, and (for outsourcing) a Supplier/Vendor model. None of these reopen Increments 35–39 or require a People/Capability subsystem.

**Production files changed:** none.
**Increment 50 is complete** per its completion criteria.
