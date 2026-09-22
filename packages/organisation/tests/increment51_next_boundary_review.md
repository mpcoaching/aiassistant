# Increment 51 — Next Boundary Review

## A. Review Scope and Constraints

This is an investigation-only post-increment architectural review. It examines what Increment 51 established and determines whether any concrete architectural boundary now requires implementation.

- Investigation-only: no production code changes, no test additions/changes, no refactoring.
- Evidence-based: conclusions are drawn from source inspection and existing test behaviour, not from conceptual reasoning or speculative future needs.
- The only filesystem change permitted by this review is creation of this artifact (`increment51_next_boundary_review.md`).
- No commit is made.

## B. Increment 51 Contract Reviewed

Increment 51 (investigation-only, zero production changes) established 20 architectural contracts, all passing, confirming:

1. **People/Capability is Role + Actor.** The People/Capability function is represented as an ordinary `Role` (`packages/organisation/src/role.py:49`) whose execution identity is an `Actor` (`packages/people_capability/src/actor.py:32`) referencing a `Person` or `Agent` via `ActorType` + `reference_id`. Chief of Staff is an ordinary `Role` — no special executive entity. Verified by `_bootstrap_organisation()` constructing `Role` + `Agent` + `Actor` + `Authority` + `Delegation` via existing primitives (`test_increment51_people_capability_capacity_decision.py:74`).

2. **Capacity is analytically derivable.** All inputs exist: `Actor` (`agent_store.find_actors_for_role`), `CapabilityAssignment` (`store.get_assignments_for_capability`), `CapabilityProficiency` (`proficiency_level`), `Work` (`Work.required_capability_ids`, `WorkStatus`), availability (`query_capability`, `detect_capacity_pressure`). No `Capacity` entity exists or is required. The test's `_derive_available_capacity` helper proves the inputs are combinable.

3. **Required proficiency is genuinely absent.** `CapabilityProficiency.proficiency_level` records *actual* proficiency (NOVICE/COMPETENT/PROFICIENT/EXPERT/MASTER). No `required_proficiency` / `required_proficiency_level` / `min_proficiency` field exists on `CapabilityAssignment`, `CapabilityProficiency`, or `Role` (verified via pydantic `model_fields` inspection).

4. **`ExecutionPath` has exactly 4 members.** `EXISTING_WORKFLOW`, `CAPABILITY_PATH`, `NEW_CAPABILITY_REQUIRED`, `HUMAN_TEAM_INVESTIGATION`. No expansion. `select_execution_path` does not inspect proficiency, capacity, or staffing (verified via source inspection of `InMemoryOrganisationControlPlane.select_execution_path` at `organisation_control_plane.py:546`).

5. **Response selection is a People/Capability concern, not an `ExecutionPath` expansion.** The conceptual response set (train, reassign, new Agent, new Person, develop, workflow, tool, human investigation, outsource-unsupported) is representable through existing primitives. No response-selection decision function exists.

6. **`CapabilityAvailability` is an availability flag, not a capacity model.** Fields: `capability_id`, `available`, `eta_seconds`, `assignee`, `reason` (`contracts/enterprise_capability_query.py:6`).

7. **`CapacityPressureSignal` is a derived signal, not an entity.** Emitted by `detect_capacity_pressure`; has `demand_rate_per_hour`, `capacity_rate_per_hour`, `queue_depth` (`contracts/organisational_events.py:130`).

8. **The Increment 48 identity chain is intact.** `ExecutionPathResult.capability_id` → `Work.develops_capability_id` → `Capability.id` → `CapabilityRegistry` → `assess_capability_development` → `promote` → ACTIVE. `required_capability_ids` ≠ `develops_capability_id`.

9. **No `Decision` entity and no autonomous staffing.** `execute_organisational_change` requires delegated authority via a `Delegation` record; `select_execution_path` does not call `register_agent`, `register_person`, or `assign_capability`.

## C. Required Proficiency

**Inspected representations:**
- `CapabilityAssignment` (`packages/people_capability/src/capability_assignment.py:38`): fields are `id`, `capability_id`, `actor_id`, `skill_ids`, `tool_ids`, `assignee_type`, `assignee_id`, `assignment_type`, `status`, `authorised_by`, `assigned_at`, `expires_at`, `reason`, `metadata`. No proficiency threshold field.
- `CapabilityProficiency` (`packages/people_capability/src/capability_proficiency.py:30`): fields are `id`, `capability_id`, `actor_id`, `person_id`, `agent_id`, `proficiency_level`, `validated_at`, `valid_until`, `evidence`, `assessed_by`, `metadata`. `proficiency_level` is *actual* (NOVICE..MASTER). No `required_proficiency_level`.
- `Role` (`packages/organisation/src/role.py:49`): fields are `id`, `name`, `description`, `responsibilities`, `authority_ids`, `constraints`, `information_access`, `reports_to`, `status`, `required_capability_ids`, `metadata`. No proficiency threshold field.

**Callers/usages:**
- `InMemoryExecutionAuthorisationPort.is_authorised` (`packages/capability_registry/src/adapters/execution_authorisation_adapter.py:38`) returns the `CapabilityProficiency` record as `AuthorisationResult.proficiency` but **does not compare it against any required threshold** (line 10: "Proficiency is recorded but does not block authorisation"). It only checks assignment status (ACTIVE vs EXPIRED/REVOKED).
- `select_execution_path` (`organisation_control_plane.py:546`) does not reference any proficiency field.
- `query_capability` (`organisation_control_plane.py:411`) returns availability based on in-progress work, not proficiency.

**Current behaviour:**
An Actor with an ACTIVE assignment is authorised to execute a capability regardless of proficiency level. There is no mechanism to say "this Role requires PROFICIENT but this Actor is only COMPETENT."

**Concrete need or lack thereof:**
No current caller, workflow, or test requires a proficiency threshold. The `is_authorised` port explicitly ignores proficiency for authorisation decisions. No production code path distinguishes "capability exists but proficiency insufficient" — it collapses into `CAPABILITY_PATH` (if `query_capability` says available) or `HUMAN_TEAM_INVESTIGATION` (if unavailable). No caller has filed a gap report for this; the absence is architectural, not behavioural.

**Classification: NOT JUSTIFIED**

There is no concrete current behaviour that requires a proficiency threshold. The `is_authorised` implementation deliberately does not use proficiency to gate execution (line 10 of the adapter docstring). Introducing a threshold now would be speculative — there is no caller that needs to differentiate "insufficient proficiency" from "available capability."

## D. Capacity Analysis

**Existing queries:**
1. `OCP.query_capability(capability_id)` (`organisation_control_plane.py:411`) — returns `{"available": bool, "eta_seconds", "assignee", "reason"}`. Answers "can this capability be invoked right now?" Based on in-progress Work count only.
2. `OCP.detect_capacity_pressure(capability_id)` (`organisation_control_plane.py:516`) — returns a `CapacityPressureSignal` if `total_load > 1`. Answers "is this capability under demand pressure?" Based on in-progress + pending Work counts.
3. `InMemoryAgentStore.find_actors_for_role(role_id)` (`agent_store.py:121`) — returns all Actors fulfilling a Role.
4. `InMemoryAgentStore.get_assignments_for_capability(capability_id)` (`agent_store.py:178`) — returns all active assignments for a capability.

**Callers:**
- `query_capability` is consumed by `EnterpriseCapabilityQueryAdapter` (`adapters/enterprise_capability_query_adapter.py:19`), which is used by `ai/src/chat.py`:1633 (`_handle_capability_path_response`) and `:1760` to check if a selected capability is available before execution.
- `detect_capacity_pressure` is called only in tests (`test_increment51`, `test_increment50`, `test_events.py`) — **no production caller**.
- `find_actors_for_role` is called only in tests (`test_actor.py:103`) — **no production caller**.
- `get_assignments_for_capability` is called in tests and in the test-only `_derive_available_capacity` helper, but **no production service composes it with Work/proficiency/availability**.

**Overlap / duplication:**
The three queries (`query_capability`, `detect_capacity_pressure`, `find_actors_for_role`) answer different questions:
- `query_capability`: per-capability operational availability (in-use or not).
- `detect_capacity_pressure`: per-capability aggregate demand vs capacity signal.
- `find_actors_for_role`: per-role actor membership.

They do not overlap. No current caller needs to compose them into a single result.

**Consolidated service justified?**
A consolidated capacity-analysis service would answer: "Given a capability_id, how many Actors hold it, what are their proficiency levels, how much in-progress Work saturates them, and what is the available headroom?" 

However:
- No production caller requests this. `chat.py` uses `query_capability` only to gate execution (available/not-available + ETA), not to count actors or assess proficiency.
- The `_derive_available_capacity` helper in the test suite demonstrates the *inputs* are combinable, but it is a test helper — not a production service with a real caller.
- `detect_capacity_pressure` already provides aggregate demand/capacity signaling without needing actor counts.

**Missing boundary:** A People/Capability-owned analysis service that composes Actors + Assignments + Proficiency + Work + availability into a capacity result. No production caller requires it yet.

**Classification: NOT JUSTIFIED**

While the inputs are representable and a consolidated service is architecturally coherent, there is no production caller that needs it. `chat.py` consumes only the availability flag from `query_capability`. `detect_capacity_pressure` is only invoked in tests. No workflow, handler, or service currently requires a consolidated capacity-analysis result to make a decision.

## E. Response Selection

**Current four-branch behaviour** (`select_execution_path`, `organisation_control_plane.py:546`):
1. If a matching workflow exists → `EXISTING_WORKFLOW` (with workflow definition).
2. If a capability is registered and `available=True` → `CAPABILITY_PATH`.
3. If a capability is registered but `available=False` → `HUMAN_TEAM_INVESTIGATION`.
4. If a capability is not registered → `NEW_CAPABILITY_REQUIRED` (capability_id preserved on the result).

**Existing response semantics:**
The four branches are solution-path selectors, not response-class selectors. They answer "what broad execution mechanism is available?" not "what should the organisation do about a gap?"

**Current caller: `chat.py`** (`ai/src/chat.py:858`):
The `_solution_selection.select_execution_path` call dispatches to one of four handlers:
- `_execute_workflow_response` (EXISTING_WORKFLOW → workflow execution)
- `_handle_capability_path_response` (CAPABILITY_PATH → query availability → execute capability)
- `_handle_new_capability_required_response` (NEW_CAPABILITY_REQUIRED → create capability-development Work)
- `_handle_human_team_investigation_response` (HUMAN_TEAM_INVESTIGATION → create investigation Work)

Each handler maps directly to an existing mechanism. There is no missing handler, no unhandled branch, and no point where the caller needs to choose "reassign vs develop vs provision" — `_handle_new_capability_required_response` always creates a capability-development Work; `_handle_human_team_investigation_response` always creates an investigation Work.

**Whether response classes are currently justified:**
No. The current caller (`chat.py`) handles all four branches with concrete, distinct actions. The "what response class to pick" logic (train vs reassign vs provision vs outsource) would only be needed if a caller needed to choose among multiple organisational-change actions for the same gap. No such caller exists. `execute_organisational_change` is the only mechanism for organisational change, and it is called directly by `chat.py` via `mark_ready` when creating capability-development Work — it does not consult any response-selection service.

**Classification: NOT JUSTIFIED**

No production caller requires response-class modelling. The four `ExecutionPath` branches are fully handled by `chat.py` with direct mapping to existing mechanisms. Adding response classes would anticipate a caller that does not exist.

## F. Organisational Change Entry Points

**`execute_organisational_change`** (`organisation_control_plane.py:651`):
- **Actual boundary:** Full method. Takes `Work`, `Actor`, optional `Role`, optional `capability_ids`. Checks delegated authority via `_has_organisational_authority`. Assigns work via `assign_work`. Returns `{"status": "executed"|"idempotent"|"unauthorised"}`.
- **Usable?** Yes — actively called by `chat.py` indirectly (via `WorkManagementAdapter.create_work` + `mark_ready`) and directly tested in `test_increment43`, `test_increment44`, `test_increment50`, `test_increment51`.
- **Limitation:** It only assigns Work to an Actor. It does not provision new Agents/Persons (those are created via `InMemoryAgentStore.register_agent`/`register_person`, which are outside OCP — ADR-037). The caller must supply an existing Actor.

**`assign_capability`** (`agent_store.py:127`):
- **Actual boundary:** People/Capability store method. Creates a `CapabilityAssignment` linking Actor → Capability.
- **Usable?** Yes — called in tests and bootstraps (`_bootstrap_organisation`), and by `execute_organisational_change` indirectly via Work assignment.
- **Limitation:** Not called by `execute_organisational_change` directly — the OCP method does not record capability assignments as part of organisational change. It only assigns Work.

**`register_agent`** (`agent_store.py:47`):
- **Actual boundary:** People/Capability store method. Creates Agent + Actor.
- **Usable?** Yes — called in tests and bootstraps.
- **Limitation:** No production caller outside tests/bootstrap. No workflow invokes this as part of a capacity-gap response.

**`register_person`** (`agent_store.py:69`):
- **Actual boundary:** People/Capability store method. Creates Person + Actor.
- **Usable?** Yes — called in tests.
- **Limitation:** No production caller outside tests.

**`assign_work`** (`organisation_control_plane.py:291`):
- **Actual boundary:** OCP core method. Assigns Work to Actor/Role/Person/Agent.
- **Usable?** Yes — actively called by `execute_organisational_change`, `WorkManagementAdapter`, and tests.

**Conclusion:** The entry points exist and are usable, but they are primitives, not an orchestrated capacity-gap-response workflow. No production caller composes them into a "detect gap → choose response → execute change" loop.

## G. Capability and Gap Detection

**`_detect_capability_gap`** / **`identify_capability_gaps`**:
- **Not found.** Grep for `_detect_capability_gap` and `identify_capability_gaps` across all packages returned zero results. These names appear only in the Increment 51 report as conceptual descriptions, not as implemented functions.

**What actually exists:**
- `select_execution_path` (`organisation_control_plane.py:546`) — identifies a capability gap only in the narrow sense: if a `capability_id` in `required_capability_ids` is not registered in the registry and not available → returns `NEW_CAPABILITY_REQUIRED` with that `capability_id` preserved. This is a "capability not found" check, not a systemic "scan all Work for missing capabilities" function.
- `detect_capacity_pressure` (`organisation_control_plane.py:516`) — detects demand pressure on a *specific* capability ID, not capability gaps.
- `query_capability` (`organisation_control_plane.py:411`) — checks availability of a *specific* capability ID.

**What they can determine:**
They can answer "is capability X registered and available?" and "is capability X under demand pressure?" They cannot answer "which of the required capabilities across all Work items are unregistered?" There is no batch gap-detection function that scans `Work.required_capability_ids` against `CapabilityRegistry` to enumerate all missing capabilities.

**What they cannot:**
No systemic gap scan. No capacity-based gap (capability exists but no Actor has it). No proficiency-based gap (capability exists, Actor assigned, proficiency below threshold — because no threshold exists, see Section C).

## H. Chief-of-Staff Representation

**Actual representation:**
Chief of Staff is represented as an ordinary `Role` with `id="chief-of-staff"`. It is constructed in `_bootstrap_organisation()` (`test_increment51_people_capability_capacity_decision.py:81`):

```python
chief = Role(
    id="chief-of-staff",
    name="Chief of Staff",
    authority_ids=[],
    reports_to=None,
)
```

It is NOT:
- A special executive entity or class.
- A subclass of `Role` or any other model.
- Given any special authority directly.

The People/Capability function Role has `authority_ids=["auth-organisational-change"]` and `reports_to="chief-of-staff"`. An `Authority` record is registered with `grantor_role_id="chief-of-staff"` and `grantee_role_id="people-capability-function"`, and `_has_organisational_authority` checks for a `Delegation` record linking them (`organisation_control_plane.py:783`).

**Is the current model sufficient for the next slice?**
Yes, for any organisational change that requires delegated authority. The Chief of Staff Role delegates authority via the standard `Authority` + `Delegation` mechanism. The gap is not in representation — it is in the *absence of a caller* that needs to orchestrate a capacity-gap response. The Chief of Staff boundary is usable; it simply has no workflow to drive.

## I. Candidate Next Vertical Slices

### Candidate 1: Required-Proficiency Threshold on Role

- **Name:** Add `Role.required_proficiency_levels: dict[str, ProficiencyLevel]`.
- **Concrete behaviour:** Allow comparison of `CapabilityProficiency.proficiency_level` against a role-level threshold to distinguish "insufficient proficiency" from "available."
- **Existing caller:** None. `is_authorised` deliberately ignores proficiency (line 10 of adapter docstring). `select_execution_path` ignores proficiency. No production caller requests this comparison.
- **Relevant port/query:** `is_authorised` (returns proficiency but does not compare).
- **Relevant state:** `CapabilityProficiency.proficiency_level` exists; `Role.required_proficiency_levels` does not.
- **Workflow:** No existing workflow requires this distinction.
- **Missing capability/boundary:** The field itself.
- **Classification: NOT JUSTIFIED**
- **Evidence:** No production code path differentiates "insufficient proficiency" from "available." The `is_authorised` implementation explicitly states proficiency does not block authorisation. No test asserts a proficiency threshold is needed. Introducing the field would be speculative completion of a model that no caller requires.

### Candidate 2: Consolidated Capacity-Analysis Service

- **Name:** A People/Capability-owned query/application service that composes Actors + Assignments + Proficiency + Work + availability into a capacity-analysis result.
- **Concrete behaviour:** Answer "given capability_id, what is total actor capacity, occupied slots, available slots, and proficiency distribution?"
- **Existing caller:** None in production. `chat.py` uses only `query_capability` (availability flag). `detect_capacity_pressure` is test-only.
- **Relevant port/query:** `query_capability` and `detect_capacity_pressure` exist but answer different questions. `find_actors_for_role` and `get_assignments_for_capability` are store-level primitives with no production composition.
- **Relevant state:** All inputs exist as individual primitives.
- **Workflow:** No workflow needs a consolidated capacity result.
- **Missing capability/boundary:** A service that composes the primitives. The `_derive_available_capacity` test helper proves inputs are combinable but is not a production service.
- **Classification: NOT JUSTIFIED**
- **Evidence:** No production caller needs a consolidated capacity-analysis result. `detect_capacity_pressure` already provides aggregate demand/capacity signaling. `chat.py` consumes only the availability flag. The only "caller" is a test helper, which is not architectural evidence.

### Candidate 3: Response-Selection Decision Function

- **Name:** A function that, given organisational state (required capability, proficiency, capacity, availability, constraints), returns which response class to select (train, reassign, provision Agent, provision Person, develop, workflow, tool, human investigation).
- **Concrete behaviour:** Choose among multiple organisational-change actions for a capability gap.
- **Existing caller:** None. `chat.py` maps each `ExecutionPath` branch to a single concrete action — no caller needs to choose among multiple response classes for the same gap.
- **Relevant port/query:** None. Response classes are not modelled anywhere.
- **Relevant state:** `ExecutionPath` (4 branches), `ExecutionPathResult` (data object).
- **Workflow:** `chat.py` handlers dispatch each branch directly. `_handle_new_capability_required_response` always creates capability-development Work. `_handle_human_team_investigation_response` always creates investigation Work. No ambiguity exists.
- **Missing capability/boundary:** The response-class decision function.
- **Classification: NOT JUSTIFIED**
- **Evidence:** No production caller needs to choose among multiple response classes. The four `ExecutionPath` branches are each handled by a single, unambiguous action in `chat.py`. Adding response-class modelling would anticipate a workflow that does not exist.

### Candidate 4: Systemic Capability-Gap Detection

- **Name:** A service that scans all Work items' `required_capability_ids` against the capability registry to enumerate all missing capabilities.
- **Concrete behaviour:** Batch-enumerate capability gaps across the organisation.
- **Existing caller:** None. `select_execution_path` only checks the specific `required_capability_ids` passed in context.
- **Relevant port/query:** None exists for batch gap scanning.
- **Relevant state:** `Work.required_capability_ids`, `CapabilityRegistry`.
- **Workflow:** No workflow needs batch gap enumeration.
- **Missing capability/boundary:** The scan function itself.
- **Classification: NOT JUSTIFIED**
- **Evidence:** No production caller requires batch gap detection. The per-request `select_execution_path` is sufficient for current usage. The function names `_detect_capability_gap`/`identify_capability_gaps` do not exist in source.

### Candidate 5: Authority-Gated Capacity-to-Provision Translation

- **Name:** A service that translates a capacity-analysis result into a concrete organisational change (provision Agent/Person, reassign, etc.) through `execute_organisational_change` with delegated authority.
- **Concrete behaviour:** Close a capacity gap by provisioning a new Actor or reassigning Work.
- **Existing caller:** None. `chat.py` creates capability-development Work on `NEW_CAPABILITY_REQUIRED` but does not provision Actors or reassign assignments based on capacity.
- **Relevant port/query:** `execute_organisational_change` exists as the mutation mechanism.
- **Relevant state:** `Work`, `CapabilityAssignment`, `Actor`, `Delegation`.
- **Workflow:** No workflow currently requests Actor provisioning or reassignment based on capacity analysis.
- **Missing capability/boundary:** The orchestration logic that translates a capacity finding into a provisioning/reassignment action.
- **Classification: NOT JUSTIFIED**
- **Evidence:** No production caller requests Actor provisioning as a response to capacity analysis. `register_agent`/`register_person` are only called in tests and bootstraps.

## J. Recommended Boundary and Sequencing

**No new increment is currently justified.**

Increment 51 is the current architectural stopping point. The evidence shows:

- All three candidate missing boundaries (required proficiency, capacity analysis, response selection) are **architecturally coherent but lack a production caller**. No existing workflow, service, or code path requires them.
- The `chat.py` caller handles all four `ExecutionPath` branches with direct, unambiguous dispatch to existing mechanisms. No gap exists in the current decision pipeline.
- The chief-of-staff/authority boundary is fully usable — the limitation is the absence of a caller that needs it for capacity-gap responses, not a missing representation.

**Sequencing dependency:** If a future vertical slice emerges that requires the People/Capability function to autonomously or semi-autonomously respond to capacity gaps (e.g., "if capability X runs out of available Actors, provision a new one"), then three boundaries would become relevant in this order:
1. Required-proficiency threshold (needed to express "insufficient proficiency" as distinct from "unavailable").
2. Consolidated capacity-analysis service (needed to compute available slots).
3. Response-selection decision (needed to choose among train/reprovision/reassign options).

But **none of these have a current caller**. Until a concrete use case emerges — a workflow that detects a capacity/proficiency gap and needs to choose an organisational response — these remain speculative abstractions.

## K. Conclusion and Explicit Non-Changes

**Final classifications:**

| Candidate | Classification |
|---|---|
| Required-proficiency threshold on Role | **NOT JUSTIFIED** |
| Consolidated capacity-analysis service | **NOT JUSTIFIED** |
| Response-selection decision function | **NOT JUSTIFIED** |
| Systemic capability-gap detection | **NOT JUSTIFIED** |
| Authority-gated capacity-to-provision translation | **NOT JUSTIFIED** |

**What is required now:** Nothing. No architectural boundary currently lacks a production caller that requires it.

**What is deferred:** All three Increment 51 identified gaps (required-proficiency threshold, capacity-analysis service, response-selection logic) remain deferred indefinitely until a concrete use case emerges.

**What is not justified:** Any implementation work on the above candidates. No new abstraction, interface, or model field is warranted by current evidence.

**Explicit confirmation of zero changes:**
- No production code modified.
- No test code modified or added.
- No generated files created.
- No new interfaces, models, services, or fields introduced.
- No commit made.

The only filesystem change from this review is the creation of this artifact: `packages/organisation/tests/increment51_next_boundary_review.md`.
