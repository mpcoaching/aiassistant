# Increment 43 — First Organisational Change Vertical Slice

First production implementation proving one complete organisational-change
vertical slice using existing primitives. No new domain concepts introduced.

Scenario: Customer Acquisition needs additional capacity.
Option A: Add new specialist Actor.
Option B: Expand existing Actor.

Production changes made. Investigation complete.

---

## A. Existing implementation map

The following primitives exist and are sufficient for the vertical slice:

| Entity | Creation mechanism | Owner |
|---|---|---|
| Role | `InMemoryOrganisationControlPlane.register_role()` | OCP |
| Work | `Work()` instantiation + `assign_work()` | OCP |
| Authority | `register_authority()` | OCP |
| Delegation | `delegate_authority()` | OCP |
| Person | `InMemoryAgentStore.register_person()` | People/Capability |
| Agent | `InMemoryAgentStore.register_agent()` | People/Capability |
| Actor | Auto-created from Person/Agent in InMemoryAgentStore | People/Capability |
| Capability | `CapabilityRegistry.register()` | People/Capability |
| CapabilityAssignment | `InMemoryAgentStore.assign_capability()` | People/Capability |
| Paperclip Agent | `PaperclipOrganisationControlPlane.create_agent()` | Paperclip (implementation) |
| Paperclip Issue | `PaperclipOrganisationControlPlane.create_work()` | Paperclip (implementation) |

Key discovery: `execute_organisational_change()` was NOT an existing method.
It is the new production method that coordinates the known-good sequence:
Role → Work → Assignment → (CapabilityAssignment via People/Capability) → (Paperclip via create_agent).

`explain_implementation()` was NOT an existing method. It is the new
production method that traces Actor → Work → Role for inspectable state.

Paperclip's `create_agent()` already had `_map_agent_to_role()` and
`_map_issue_to_work()` from Increment 21Y. The only change was adding
idempotency (cache lookup by name before creating).

---

## B. Vertical-slice scope

Two paths proven with the same primitives:

**New Actor path:**
```
Need → Work → Role → Person/Agent → Actor → CapabilityAssignment → Paperclip Agent
```

**Existing Actor path:**
```
Need → Work → Role → existing Actor → new CapabilityAssignment
```

Both paths use: `execute_organisational_change()` (OCP) + `assign_capability()` (People/Capability).

No separate models for "hire", "promotion", "reorganisation", etc.

---

## C. Organisational change flow

The production flow via `execute_organisational_change()`:

1. OCP: verify assignee Role has delegated authority (via `_has_organisational_authority()`)
2. OCP: register Role if not already registered
3. OCP: check idempotency (existing active assignment for Work+Actor)
4. OCP: assign Work to Actor via `assign_work()`
5. People/Capability: create Actor via `register_agent()` (Agent + Actor)
6. People/Capability: create CapabilityAssignment via `assign_capability()`
7. Paperclip: create Agent via `create_agent()` (implementation)

Order rationale: OCP handles organisational intent first. People/Capability
creates the execution identity. Paperclip instantiates implementation last.
This preserves the invariant: Paperclip is never the authority for Actor existence.

---

## D. Work boundary

Work represents the organisational change. Existing fields are sufficient:

| Proposal element | Work field |
|---|---|
| Title | `title` |
| Description | `description` |
| Accountable entity | `accountable_role_id` |
| Required capabilities | `required_capability_ids` |
| Success criteria | `acceptance_criteria` |
| Current constraint/evidence | `context` (dict) |
| Economic justification | `context` (dict) |
| Expected outcome | `outcome` (after implementation) |
| Dependencies | `dependencies` |
| Deliverables | `deliverables` |
| Work type | `work_type` ("initiative") |

No OrganisationalChange, Decision, HiringRequest, or Requisition entity needed.

---

## E. Role boundary

Role represents the organisational responsibility. Existing fields suffice:

- `name`, `description` — identity and purpose
- `responsibilities` — what the position does
- `required_capability_ids` — what capabilities it needs
- `authority_ids` — what it can do (used for authority verification)
- `status` — ACTIVE|INACTIVE|VACANT

No PositionSpecification needed (per Increment 40).

---

## F. Actor creation boundary

New Actor creation sequence:

```
OCP register_role() → People/Capability register_agent()
  → Actor created (id=Agent.id, reference_id=Agent.id)
  → CapabilityAssignment via assign_capability()
```

Key invariant preserved: Paperclip never becomes the authority for Actor
existence. Actor is created in People/Capability before Paperclip Agent
creation. Paperclip Agent ID becomes `Actor.reference_id` (implementation reference).

Existing Actor expansion: simply `assign_capability()` on existing Actor.

---

## G. Existing Actor expansion

Proven via `test_existing_actor_path_execute_organisational_change()`:

```
Existing Actor → assign_capability("customer-acquisition") → new authority
```

Same `assign_capability()` mechanism as new Actor path. No "promotion" concept.

Existing Actor gets additional CapabilityAssignment, additional Work assignment,
and Paperclip Agent already provisioned (or provisioned via separate call).

---

## H. CapabilityAssignment boundary

CapabilityAssignment remains the authoritative Actor↔Capability relationship:

- Capability remains organisation-owned (People/Capability)
- Actor remains execution identity
- Assignment is the authoritative link
- Proficiency is separate (not confused with assignment)
- Execution authorisation continues to work via `ExecutionAuthorisationPort`
- Paperclip does not become a second Capability registry

---

## I. Authority/Delegation boundary

Organisational change requires delegated authority:

1. `Authority` with scope "execute-organisational-change" granted by grantor Role
2. `Delegation` from grantor Role to grantee Role
3. `execute_organisational_change()` verifies assignee Role has delegated authority
4. `_has_organisational_authority()` checks Role.authority_ids against OCP authorities

No HR authority, PeopleManager, HiringAuthority, or Admin-only semantics.
Ordinary Actor with appropriate Role + Authority can execute the change.

---

## J. Paperclip implementation boundary

Paperclip boundary proven via existing mapping/creation methods:

- `create_agent()` — creates Paperclip Agent, maps to Role via `_map_agent_to_role()`
- `create_work()` — creates Paperclip Issue, maps to Work via `_map_issue_to_work()`
- `assign_work()` — assigns Paperclip Issue via assigneeAgentId/assigneeUserId

Smallest adapter change: added idempotency check in `create_agent()` —
returns cached Role if one with same name exists. Prevents duplicate Paperclip
Agents on retry without a generic framework.

Paperclip does not define Actor, Capability, Skill, or Assignment (verified by test).
OCP does not import Paperclip (verified by test).

---

## K. Idempotency

Two levels of idempotency:

**OCP level** (`execute_organisational_change()`):
- Checks for existing active Assignment for (Work ID, Actor ID) via `_find_active_assignment()`
- If found, returns `status: "idempotent"` with existing `assignment_id`
- No duplicate Work items created
- No duplicate Assignment records created

**Paperclip level** (`create_agent()`):
- Checks role cache for existing Role with same name
- If found, returns cached Role instead of creating duplicate
- Prevents duplicate Paperclip Agents on retry

Test: `test_execute_organisational_change_idempotent` — calls twice,
verifies single Assignment and single Work.
Test: `test_paperclip_create_agent_idempotency` — verifies cache lookup.

---

## L. Failure/retry behaviour

**Case A: OCP succeeds, Paperclip fails**

Verified by `test_failure_ocp_succeeds_paperclip_fails`:
- OCP state is consistent (Role, Work, Assignment exist)
- Paperclip failure is implementation failure (not organisational)
- No corrupted second organisational identity created
- Operation can be retried (OCP returns idempotent on second call)

**Case B: Paperclip succeeds but OCP recording fails**

Current architecture: OCP and Paperclip are separate bounded contexts.
Paperclip owns operational execution state; OCP owns organisational truth.
If Paperclip succeeds but OCP doesn't record, OCP can catch up via:
- Re-running `execute_organisational_change()` (idempotent)
- Paperclip Agent ID stored as `Actor.reference_id` for future correlation

No distributed transactions introduced. No event sourcing introduced.

---

## M. People/Capability test case

People/Capability is an ordinary organisational participant:

- Uses existing `register_agent()` → Actor creation
- Uses existing `assign_capability()` → CapabilityAssignment
- Uses existing `InMemoryAgentStore` for identity management
- No HRService, PeopleCapabilityManager, or OrganisationBuilder
- No special People/Capability class
- Receives Work, identifies capacity issues, delegates investigation

---

## N. Chief of Staff test case

Chief of Staff is an ordinary Actor with appropriate Role + Authority:

- Chief of Staff = a Role with coordination responsibilities
- Uses Delegation for coordination authority (not special routing)
- No ChiefOfStaff class, no special privileges
- Can execute organisational changes via `execute_organisational_change()`
- No special code path or hard-coded executive privileges

---

## O. Resulting organisational state

After successful execution, state is inspectable via `explain_implementation()`:

```
explain_implementation(actor_id) →
  actor_id: str
  assigned_work: [{work_id, title, status, work_type, accountable_role_id,
                   required_capability_ids, role_name, ...}]
  accountable_roles: [str]
```

The important thing is not merely that Paperclip contains an Agent.
OCP can explain the organisational meaning: which Role, which Work,
which capabilities, which authority.

Full chain verified by `test_post_change_state_inspectable`:
Work → Role → Actor → CapabilityAssignment → implementation reference.

---

## P. Architectural invariants

1. OCP remains authoritative for organisational state ✓
2. Paperclip is an implementation, not an authority ✓
3. Work can represent organisational change ✓
4. Role represents the organisational responsibility ✓
5. Actor represents execution identity ✓
6. Capability belongs to the organisation ✓
7. CapabilityAssignment is the Actor↔Capability authority ✓
8. Existing Actors can receive additional capabilities ✓
9. New Actors can be introduced without a new domain concept ✓
10. No special HR/People/ChiefOfStaff entity is required ✓
11. Economic justification does not require economic domain entities ✓
12. A capability gap does not automatically create an Actor ✓
13. The implementation boundary remains retryable without distributed transactions ✓
14. Workflow semantics remain unchanged ✓

---

## Q. Production changes made

**`packages/organisation/src/organisation_control_plane.py`:**
- Added `execute_organisational_change()` to `InMemoryOrganisationControlPlane`
- Added `explain_implementation()` to `InMemoryOrganisationControlPlane`
- Added `_has_organisational_authority()` helper
- Added `_find_active_assignment()` helper
- Did NOT modify `OrganisationControlPlane` abstract interface (kept narrow)

**`packages/organisation_paperclip/src/organisation_paperclip.py`:**
- Added idempotency check in `create_agent()` (cache lookup by name)

**`packages/organisation/tests/test_increment43_organisation_change_execution.py`:**
- 37 new tests covering the full vertical slice

**No changes to:**
- Role model
- Actor model
- Capability model
- Work model
- CapabilityAssignment model
- Authority/Delegation model
- Paperclip mapping methods (`_map_agent_to_role`, `_map_issue_to_work`)
- Workflow execution semantics

---

## R. Concepts deliberately not added

| Concept | Reason |
|---|---|
| OrganisationalChange | Work suffices |
| Decision | Work (proposal + implementation + outcome) suffices |
| PositionSpecification | Role suffices |
| Vacancy/Requisition | RoleStatus.VACANT suffices |
| HiringAuthority | Ordinary Authority + Delegation suffices |
| HRService | Ordinary organisational function |
| OrganisationBuilder | `execute_organisational_change()` handles the flow |
| AgentFactory | `register_agent()` + Paperclip `create_agent()` suffice |
| CapacityPlan | Work + CapacityPressureSignal suffice |
| Value entity | Per Increment 41 |
| Cost entity | Per Increment 41 |
| Generic provisioning framework | `create_agent()` is sufficient |
| Distributed transaction | OCP/Paperclip bounded contexts manage own consistency |
| Event sourcing | Not needed for retriable boundary |
| Team as OCP Actor | Per Increment 40 |

---

## S. Test coverage

**37 tests** in `test_increment43_organisation_change_execution.py`, all passing.

### Sections covered:
- A. Implementation map verification (5 tests)
- B. New Actor path (3 tests)
- C. Existing Actor path (1 test)
- D. Organisational authority (2 tests)
- E. Work boundary (2 tests)
- F. Idempotency (2 tests)
- G. Paperclip boundary (3 tests)
- H. Failure/retry behaviour (2 tests)
- I. Resulting organisational state (3 tests)
- J. People/Capability as ordinary participant (1 test)
- K. Chief of Staff as ordinary participant (1 test)
- L. Economic reasoning boundary (2 tests)
- M. Architectural invariants (7 tests)

**Total organisation tests:** 676 passed + 1 pre-existing failure = 677 total
(37 new Increment 43 tests + 640 prior tests including the 1 pre-existing failure)

**Pre-existing failure:** `test_ocp_delegated_registry_provides_capability_for_work`
in `test_increment30_capability_boundary.py` — unrelated to Increments 35–43.

**Lint:** All changed files pass ruff.

---

## T. Final architectural assessment

**The vertical slice proves that existing primitives fully support organisational
change execution without new domain concepts.**

The complete flow works end-to-end:
```
Organisational need
    ↓ (in Work)
Role (organisational requirement)
    ↓ (via execute_organisational_change)
Work (change proposal + execution record)
    ↓ (via assign_work)
Actor (execution identity from People/Capability)
    ↓ (via CapabilityAssignment)
Capability (what the Actor can do)
    ↓ (via Paperclip create_agent)
Paperclip Agent (implementation)
    ↓ (via explain_implementation)
Inspectable organisational state
```

Both paths work:
- New Actor: Person/Agent → Actor → CapabilityAssignment → Paperclip Agent
- Existing Actor: CapabilityAssignment on existing Actor → Paperclip Agent

Key architectural invariants preserved:
- OCP owns organisational truth
- Paperclip is implementation (retryable)
- No new domain concepts introduced
- Authority via existing Authority/Delegation mechanism
- Idempotency at OCP and Paperclip levels
- Failure boundary is clean

---

## U. Recommended Increment 44

Increment 44 should extend the vertical slice to cover:

1. **Multiple sequential organisational changes** — prove that the flow
   works for a chain of changes (e.g., add capacity → execute → evaluate →
   adjust) using the same primitives.

2. **Capability gap resolution via select_execution_path** — connect
   `select_execution_path()`'s HUMAN_TEAM_INVESTIGATION and
   NEW_CAPABILITY_REQUIRED paths to the organisational change flow,
   proving that a detected capability gap can trigger Work representing
   an organisational change (not automatic Actor creation).

3. **Delegation chain for organisational authority** — prove that
   authority can be delegated through multiple Role levels
   (founder → COO → Chief of Staff → Operator) and the change flows
   through the chain correctly.

Do NOT:
- Turn it into a platform-wide refactor
- Create generic orchestration frameworks
- Add new domain entities
- Reopen Increments 40–43
