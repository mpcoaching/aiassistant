# Increment 44 — Organisational Change Semantics: Defect Fixes

Evidence-first increment. Three confirmed semantic defects identified during
investigation and fixed with minimum coherent changes.

## Investigation Findings

### Current state

`execute_organisational_change()` and `explain_implementation()` exist **only
in the working tree** — they are not present in the committed HEAD. The working
tree implementation adds four methods to `InMemoryOrganisationControlPlane`:

- `execute_organisational_change` (lines 629–709)
- `explain_implementation` (lines 711–759)
- `_has_organisational_authority` (lines 761–769)
- `_find_active_assignment` (lines 771–782)

All 37 Increment 43 tests pass, confirming the working tree implementation is
functionally operational. The Increment 43 pre-existing failure
(`test_ocp_delegated_registry_provides_capability_for_work`) is unrelated.

### WorkEvent construction/consumption trace

`WorkEvent` is constructed in three locations:

1. `packages/organisation/src/organisation_control_plane.py:791` — `_emit_work_event`
2. `packages/organisation_paperclip/src/organisation_paperclip.py:634` — `_emit_work_event`
3. Test files (10 construction sites in `test_operations.py`, `test_events.py`,
   `test_increment32_execution_boundary.py`)

`WorkEvent` is consumed in:

- `packages/workflow_runner/src/operations.py:163-174` — only reads `event.event_type`
  and `event.work_id`. Does NOT read `assignee_actor_id`, `assignee_role_id`, or
  `assignee_agent_id`.
- Paperclip `wait_for_execution` — emits COMPLETED/FAILED/CANCELLED events via
  `_emit_work_event` (was constructing inline, now uses the helper).

Adding `assignee_actor_id: str | None = None` as a new optional field is
backward-compatible: pydantic defaults to `None`, and no consumer reads it yet.

## Confirmed Defects

### Defect 1: `explain_implementation()` Actor/Role conflation

**Location:** `organisation_control_plane.py` (original working tree line 732)

The original code:
```python
if not actor_works and self.get_role(actor_id) is None:
    return None
```

`actor_id` is an Actor ID (e.g., `"specialist"`), but `get_role()` queries the
Role registry. Actor IDs and Role IDs are separate namespaces (ADR-037:
"Person/Agent/Actor records are owned by People/Capability"). If a Role
happened to be registered with an ID string matching an Actor ID, the method
would incorrectly return a non-None result for an Actor with no organisational
presence.

### Defect 2: `WorkEvent` dropped `assignee_actor_id`

**Location:** `organisational_events.py:73-89` (model), `organisation_control_plane.py:784-805`
and `organisation_paperclip.py:633-648` (emitters)

The `WorkEvent` model had `assignee_role_id` and `assignee_agent_id` but **no
`assignee_actor_id`** field. The `_emit_work_event()` methods accepted an
`assignee_id` parameter but never used it. When Work was assigned to a Person
Actor (ActorType.PERSON), `work.assignee_actor_id` was set but never emitted
in the event — the Actor identity was lost.

### Defect 3: `_has_organisational_authority()` checked authority existence, not delegation

**Location:** `organisation_control_plane.py:761-769` (original)

The original code checked only that an `Authority` record existed in
`self._authorities` for the role's `authority_ids`. It did **not** verify that
a `Delegation` record existed linking that authority to the role. A role could
claim authority merely by listing an authority ID, even if no delegation had
occurred.

## Exact Fixes

### Fix 1 — `explain_implementation()`

Removed the `self.get_role(actor_id)` fallback. An Actor has "no organisational
presence" when no Work is assigned to it — that is the only organisational
signal OCP can verify (OCP does not store Actor records).

```python
# Before:
if not actor_works and self.get_role(actor_id) is None:
    return None
# After:
if not actor_works:
    return None
```

### Fix 2 — `WorkEvent.assignee_actor_id`

1. Added `assignee_actor_id: str | None = None` field to `WorkEvent` in
   `packages/contracts/organisational_events.py`.
2. Updated `_emit_work_event` in `InMemoryOrganisationControlPlane` to pass
   `assignee_actor_id=work.assignee_actor_id`.
3. Updated `_emit_work_event` in `PaperclipOrganisationControlPlane` to pass
   `assignee_actor_id=work.assignee_actor_id`.

This is the minimum coherent change: the field is a new optional field (Pydantic
defaults to `None`), all existing construction sites remain valid, and no
consumer behavior changes.

### Fix 3 — `_has_organisational_authority()`

Changed from checking authority existence to checking for an actual
`Delegation` record:

```python
# Before: only checked authority exists
authority = self._authorities.get(authority_id)
if authority is not None:
    return True

# After: checks authority exists AND is delegated to this role
authority = self._authorities.get(authority_id)
if authority is None:
    continue
has_delegation = any(
    d for d in self._delegations.values()
    if d.authority_id == authority_id
    and d.to_role_id == role.id
)
if has_delegation:
    return True
```

This uses the existing `Delegation` model (`authority_id`, `from_role_id`,
`to_role_id`) — no new entities or abstractions.

## Why Each Fix Is the Minimum Coherent Change

1. **`explain_implementation`**: Removing one `and` condition from an `if`
   statement. No new state, no new lookups. The Actor namespace is never
   consulted through Role methods.

2. **`WorkEvent`**: Adding one optional field (default `None`) and one
   keyword argument in two emitter methods. Backward-compatible with all
   existing construction sites.

3. **`_has_organisational_authority`**: Replacing a simple existence check
   with a Delegation lookup using the existing `self._delegations` dict.
   No new model, no new storage.

## Tests

New file: `packages/organisation/tests/test_increment44_organisational_change_semantics.py`
(13 tests)

### Defect 1 tests (3 tests)
- `test_explain_implementation_actor_with_no_work_returns_none`
- `test_explain_implementation_role_id_collision_does_not_impersonate_actor`
  — explicit regression test for the namespace collision
- `test_explain_implementation_returns_explanation_when_work_assigned`

### Defect 2 tests (5 tests)
- `test_work_event_has_assignee_actor_id_field` — model has the new field
- `test_assign_work_to_person_actor_emits_event_with_actor_id` — Person Actor
- `test_assign_work_to_agent_actor_preserves_actor_id` — Agent Actor
- `test_assign_work_to_role_preserves_role_id_no_actor_id` — Role (no actor)
- `test_assign_work_to_person_directly_preserves_actor_id` — Person Actor direct

### Defect 3 tests (5 tests)
- `test_authority_exists_no_delegation_rejected`
- `test_authority_wrong_grantee_rejected`
- `test_valid_delegation_accepted`
- `test_unauthorised_role_rejected`
- `test_increment43_delegated_authority_still_succeeds`

## Regression Results

### Increment 44 tests
```
13 passed in 0.07s
```

### Increment 43 regression tests
```
37 passed in 0.08s
```

### Full organisation test suite
```
1 failed, 689 passed in 1.89s
```

The 1 failure is pre-existing and unrelated:
`test_increment30_capability_boundary.py::test_ocp_delegated_registry_provides_capability_for_work`
— `assert None is not None` on `registry.get("cap-ocp-delegated")`. This failure
exists before Increment 44 changes and is in the capability registry delegation
path, not the organisational authority path.

### Workflow runner operations tests
```
12 passed in 0.05s
```
All `WorkEvent` consumers in `test_operations.py` remain compatible.

### Existing event tests
```
21 passed in 0.07s
```

## Lint / Diff Check

```
ruff check: All checks passed (on changed files)
git diff --check: No whitespace errors in changed files
```

The `git diff --check` output includes pre-existing whitespace errors in
`packages/ai/src/chat.py` and `packages/workflow_runner/tests/test_platform_integration.py`
— files not modified in this increment.

## Files Changed

1. `packages/contracts/organisational_events.py` — added `assignee_actor_id` field to `WorkEvent`
2. `packages/organisation/src/organisation_control_plane.py` — fixed `explain_implementation`, fixed `_emit_work_event`, fixed `_has_organisational_authority`
3. `packages/organisation_paperclip/src/organisation_paperclip.py` — fixed `_emit_work_event` (pre-existing bug, same fix needed)
4. `packages/organisation/tests/test_increment44_organisational_change_semantics.py` — new test file (13 tests)

## Pre-existing Failures

- `test_increment30_capability_boundary.py::test_ocp_delegated_registry_provides_capability_for_work`
  — asserts `registry.get("cap-ocp-delegated")` is not None. This is in the
  capability registry delegation path, unrelated to the organisational authority
  fixes in this increment.

## Remaining Observations (Explicitly NOT Defects)

1. **`execute_organisational_change` does not create Actors/CapabilityAssignments/Paperclip agents**
   — By design. The method docstring states "Handles OCP responsibilities only."
   These are orchestrated by callers per Increment 43 architecture.

2. **No `CREATED` event emitted from `execute_organisational_change`**
   — The `assign_work` method emits an `ASSIGNED` event. `WorkEventType.CREATED`
   exists in the enum but is never emitted from OCP. This is a general absence
   across the codebase, not specific to this increment. Paperclip's `create_work`
   does emit `CREATED`.

3. **`_emit_work_event` accepts `assignee_id` parameter but never used it**
   — This was part of Defect 2. The parameter is retained for API compatibility
   (Paperclip's `assign_work` passes `assignee_id=assignee_id`) but the field
   is no longer dropped because `work.assignee_actor_id` is now read directly
   from the Work object.

4. **Authority's `grantee_role_id` not checked against Delegation**
   — The fix checks only the Delegation record. The Authority model has
   `grantee_role_id` but the Delegation's `to_role_id` is the authoritative
   proof of delegation. If data inconsistency exists where the Authority says
   grantee is X but a Delegation says to_role is Y, the Delegation wins. This
   is consistent with the domain model: Delegation is the act, Authority is
   the definition.

## Increment Complete?

Yes. All three defects fixed with minimum coherent changes. All tests pass
(689 + 13 new), pre-existing failure documented. No new entities or abstractions
introduced. OCP boundaries preserved.

## Recommended Next Increment

**Increment 45 — Operational work lifecycle completion tracking.**

The `WorkEvent` model now has `assignee_actor_id`, but `WorkEventType.CREATED`
is never emitted from OCP (only from Paperclip). When `execute_organisational_change`
introduces new Work, it should emit a `CREATED` event before `ASSIGNED`. This
would complete the organisational event lifecycle: CREATED → ASSIGNED → READY →
STARTED → COMPLETED.

Additionally, the `_emit_work_event` parameter `assignee_id` is now redundant
(the value is read from `work.assignee_actor_id`). The callers in
`assign_work` and `assign_work` (Paperclip) still pass it. Cleaning up this
redundant parameter would simplify the emission API.
