# Increment 45 — Work Event Lifecycle Boundary: Investigation Report

## Objective

Determine whether the organisational Work event lifecycle is semantically incomplete because newly created Work emits `ASSIGNED` without first emitting `CREATED`, and determine whether `_emit_work_event(assignee_id=...)` can safely be simplified.

## 1. Current Event Lifecycle (Traced from Code)

### Event Emission Sites

| Event Type | Emitted From | Trigger |
|-----------|-------------|---------|
| `WorkEventType.CREATED` | `PaperclipOrganisationControlPlane.create_work()` (line 197) | When a Paperclip Issue is created and mapped to Work |
| `WorkEventType.ASSIGNED` | `InMemoryOrganisationControlPlane.assign_work()` (line 324) | Work status transitions to ASSIGNED |
| `WorkEventType.ASSIGNED` | `PaperclipOrganisationControlPlane.assign_work()` (line 247) | Work status transitions to ASSIGNED |
| `WorkEventType.READY` | `InMemoryOrganisationControlPlane.mark_work_ready()` (line 367) | Work status transitions to READY (organisational handoff) |
| `WorkEventType.READY` | `PaperclipOrganisationControlPlane.mark_work_ready()` (line 286) | Work status transitions to READY |
| `WorkEventType.COMPLETED` | `InMemoryOrganisationControlPlane.complete_work()` (line 382) | Work marked completed |
| `WorkEventType.COMPLETED` | `PaperclipOrganisationControlPlane.complete_work()` (line 297) | Work marked completed |
| `WorkEventType.COMPLETED` | `PaperclipOrganisationControlPlane.wait_for_execution()` (line 390) | Paperclip run reaches terminal "completed" |
| `WorkEventType.FAILED` | `InMemoryOrganisationControlPlane.fail_work()` (line 397) | Work marked failed |
| `WorkEventType.FAILED` | `PaperclipOrganisationControlPlane.fail_work()` (line 308) | Work marked failed |
| `WorkEventType.FAILED` | `PaperclipOrganisationControlPlane.wait_for_execution()` (line 399) | Paperclip run reaches terminal "failed" |
| `WorkEventType.CANCELLED` | `InMemoryOrganisationControlPlane.cancel_work()` (line 408) | Work cancelled |
| `WorkEventType.CANCELLED` | `PaperclipOrganisationControlPlane.cancel_work()` (line 319) | Work cancelled |

### Events Defined but Never Emitted

| Event Type | Status |
|-----------|--------|
| `WorkEventType.QUEUED` | Defined in enum, never emitted from any source |
| `WorkEventType.STARTED` | Defined in enum, never emitted from any source |
| `WorkEventType.ESCALATED` | Defined in enum, never emitted from any source |

### Event Consumers

| Consumer | What It Reads |
|----------|--------------|
| `Operations._handle_event()` (`workflow_runner/src/operations.py:163-166`) | Only `event.event_type` — acts only on `WorkEventType.READY` |
| `test_events.py` test assertions | Various event types in assertions |
| `test_operations.py` test assertions | `READY` and `ASSIGNED` event construction for tests |

**No production consumer reads `CREATED`, `ASSIGNED`, `COMPLETED`, `FAILED`, `CANCELLED`, `QUEUED`, `STARTED`, or `ESCALATED` events.** Operations only acts on `READY`.

---

## 2. Investigation of `CREATED` Specifically

### Architectural Origin Model

`INCREMENT-21W-ORGANISATIONAL-EVENT-AND-COMMUNICATION-BOUNDARY.md` (lines 77-94) defines the origin of each event type:

| Event | Origin | Meaning |
|-------|--------|---------|
| `work.created` | **WorkManagement** | A new work item was created |
| `work.assigned` | **WorkManagement** | Work was assigned to a role/agent |
| `work.queued` | **WorkManagement** | Work is waiting for capability availability |
| `work.started` | **Operational** | Work execution began |
| `work.completed` | **Operational** | Work execution finished successfully |
| `work.failed` | **Operational** | Work execution failed |
| `work.escalated` | **Organisation** | Work requires escalation |
| `work.cancelled` | **WorkManagement** | Work was cancelled |

The key distinction: `CREATED`, `ASSIGNED`, `QUEUED`, `CANCELLED` are **WorkManagement-layer** events (organisational layer). `STARTED`, `COMPLETED`, `FAILED` are **Operational-layer** events (execution backend).

### The DRAFT Lifecycle vs Event Lifecycle

`architecture.md` (lines 240-250) defines the Work status lifecycle:

```
DRAFT → ASSIGNED (organisational handoff) → IN_PROGRESS (operational execution begins) → COMPLETED → ACCEPTED
```

The Work model's default status is `WorkStatus.PENDING` (line 106 of `role.py`). There is no "DRAFT" status in the `WorkStatus` enum — the architecture document's "DRAFT" is conceptual, representing the moment Work is constructed before it enters organisational state.

### `CREATED` Emission Analysis

**Paperclip path:** `PaperclipOrganisationControlPlane.create_work()` (line 197) emits `CREATED` when creating a Paperclip Issue and translating it to a Work object. This is correct — Paperclip has a creation boundary that our domain doesn't control.

**InMemory path:** `InMemoryOrganisationControlPlane` has **no `create_work` method**. Work is constructed by external callers (`WorkManagementAdapter.create_work()` at `work_management_adapter.py:22-42`). The Work object is passed into `assign_work`, which emits `ASSIGNED`. There is no creation boundary inside InMemory OCP — creation happens outside OCP entirely.

**The `execute_organisational_change` path:** This method receives a pre-constructed `Work` object (line 631: `work: Work`), verifies authority, and calls `self.assign_work(work, assignee)` (line 699). It does not create Work — the caller creates it. Emitting `CREATED` here would be **incorrect**: it would claim the organisation created something that was actually constructed by the caller.

### Is `CREATED` an Established Part of the Intended Contract?

**No.** Evidence:

1. The `WorkEvent` type string for `CREATED` is `"work.created"` (line 48 of `organisational_events.py`).
2. The `INCREMENT-21W` event origin table lists `work.created` as originating from **WorkManagement**, meaning the layer that *manages* work creation (the Assistant/Chat layer), not the OrganisationControlPlane itself.
3. `InMemoryOrganisationControlPlane` has no Work creation method — Work is constructed outside OCP and passed in.
4. `Operations._handle_event()` only acts on `READY` events. A `CREATED` event would be consumed by nobody in production.
5. The architecture doc's Work lifecycle (DRAFT → ASSIGNED → IN_PROGRESS → COMPLETED → ACCEPTED) has no `CREATED` step.
6. Only Paperclip's `create_work()` emits `CREATED` — because Paperclip has a creation boundary that the Organisation layer doesn't own.

**Conclusion:** `WorkEventType.CREATED` is an established part of the event contract for **backends that create work** (like Paperclip), but it is **not** an expected emission from `InMemoryOrganisationControlPlane` or from `execute_organisational_change()`. The absence of `CREATED` from OCP is by architectural design, not a defect. The `WorkLifecycle` is not incomplete — `CREATED` belongs to the WorkManagement layer (Assistant/Chat), not the OCP layer.

---

## 3. Investigation of `_emit_work_event(assignee_id=...)` Redundancy

### Current State

Both `_emit_work_event` implementations accept `assignee_id: str | None = None` but never use it:

**InMemoryOrganisationControlPlane** (`organisation_control_plane.py:797-819`):
```python
def _emit_work_event(
    self,
    event_type: Any,
    work: Work,
    assignee_id: str | None = None,  # ← accepted but never used
) -> None:
    event = WorkEvent(
        ...
        assignee_actor_id=work.assignee_actor_id,  # ← reads from Work
        assignee_role_id=work.assignee_role_id,
        assignee_agent_id=work.assignee_agent_id,
        ...
    )
    self._emit(event)
```

**PaperclipOrganisationControlPlane** (`organisation_paperclip.py:633-649`):
```python
def _emit_work_event(self, event_type: Any, work: Work, assignee_id: str | None = None) -> None:
    event = WorkEvent(
        ...
        assignee_actor_id=work.assignee_actor_id,  # ← reads from Work
        assignee_role_id=work.assignee_role_id,
        assignee_agent_id=work.assignee_agent_id,
        ...
    )
    self.emit_event(event)
```

### Call Sites

| Call Site | Passes `assignee_id`? |
|----------|----------------------|
| `InMemoryOrganisationControlPlane.assign_work()` (line 324-328) | Yes: `assignee_id=assignee.id` |
| `PaperclipOrganisationControlPlane.assign_work()` (line 247) | Yes: `assignee_id=assignee_id` |

### History

The `assignee_id` parameter was originally intended to populate `assignee_actor_id` on the `WorkEvent`. However:
- The `WorkEvent` model originally had no `assignee_actor_id` field (Defect 2, Increment 44).
- The `_emit_work_event` method was always reading assignee data from the `Work` object.
- The `assignee_id` parameter was accepted but silently ignored — a latent bug.
- Increment 44 added `assignee_actor_id` to `WorkEvent` and updated both emitters to read `work.assignee_actor_id` directly, which made the parameter definitively redundant.

### Safety Assessment

**Removal is safe:**
1. The parameter is internal (method prefixed with `_`).
2. Only two call sites pass it (both in `assign_work` methods).
3. All data the parameter was meant to carry is already available on the `Work` object.
4. No consumer reads `assignee_id` from `_emit_work_event` — the value only ever flowed into the `WorkEvent` through `work.assignee_actor_id`.
5. The `assignee_id` value passed by callers is `assignee.id`, which is the same value that gets set on `work.assignee_actor_id` in `assign_work` before the event is emitted.

**However:** The parameter is not actively harmful. It's dead code, but removing it is a cleanup, not a semantic fix. The risk of leaving it is zero; the risk of removing it is minimal (two internal call sites to update).

---

## 4. Work Creation Paths

### Path 1: WorkManagementAdapter → InMemoryOCP

```
WorkManagementAdapter.create_work()  →  constructs Work(PENDING)
    → InMemoryOrganisationControlPlane.assign_work()  →  emits ASSIGNED
```
No `CREATED` event. Work is constructed outside OCP.

### Path 2: PaperclipOrganisationControlPlane.create_work()

```
PaperclipOrganisationControlPlane.create_work()  →  POST /api/companies/issues
    → maps response to Work(PENDING)
    → emits CREATED  ← only Paperclip does this
    → (caller then calls assign_work → emits ASSIGNED)
```

### Path 3: execute_organisational_change()

```
Caller constructs Work(PENDING)
    → execute_organisational_change(work=work, assignee=actor)
        → verifies authority
        → calls assign_work(work, assignee)  →  emits ASSIGNED
```
No `CREATED` event. Work is pre-constructed by caller.

### Common Boundary

All three paths converge on `assign_work()`, which emits `ASSIGNED`. There is no common `CREATED` emission boundary in InMemory OCP because InMemory has no Work creation method — creation happens outside OCP.

---

## 5. Hypothesis Assessment

| Hypothesis | Verdict | Evidence |
|-----------|---------|----------|
| `execute_organisational_change` should emit `CREATED` before `ASSIGNED` | **Rejected** | Work is pre-constructed by caller; OCP doesn't create it. `CREATED` origin is "WorkManagement" (Assistant layer), not OCP. No consumer acts on it. Architecture lifecycle (DRAFT→ASSIGNED→IN_PROGRESS→COMPLETED) has no CREATED step. |
| The event lifecycle is semantically incomplete (missing CREATED) | **Rejected** | The lifecycle is: ASSIGNED (org handoff) → READY (org handoff to Ops) → COMPLETED/FAILED (operational). CREATED is a WorkManagement-layer event for backends with creation boundaries (Paperclip only). InMemory OCP has no creation boundary. |
| `_emit_work_event(assignee_id=...)` can be safely simplified | **Confirmed** | Parameter is accepted but never used in either implementation. All assignee data read from `Work` object. Only 2 internal call sites pass it. Removal is safe but is a cleanup, not a semantic fix. |
| Paperclip and InMemory have equivalent lifecycle semantics | **Partially confirmed** | Both emit ASSIGNED, READY, COMPLETED, FAILED, CANCELLED. Paperclip uniquely emits CREATED via its `create_work()` method because it has a Work creation boundary. InMemory has no creation boundary. |
| Consumers rely on the current absence of CREATED | **Confirmed (by non-reliance)** | `Operations._handle_event()` only processes `READY` events. No production code subscribes to `CREATED`. |

---

## 6. Increment Decisions

### Hypothesis 1 — `execute_organisational_change` should emit `CREATED` before `ASSIGNED`

**Rejected.**

Work is pre-constructed by the caller and passed into `execute_organisational_change(work, assignee)`. The OCP does not create Work — it only assigns it. The `INCREMENT-21W` event origin model assigns `work.created` origin to the **WorkManagement** layer (Assistant/Chat), not the OrganisationControlPlane. Emitting `CREATED` from OCP would falsely claim the organisation created work that was constructed externally. No production consumer (`Operations._handle_event`) acts on `CREATED`. Do not add `CREATED` emission to OCP methods.

### Hypothesis 2 — The event lifecycle is semantically incomplete (missing CREATED)

**Rejected.**

The intended organisational control-plane lifecycle is:

```
ASSIGNED → READY → COMPLETED / FAILED / CANCELLED
```

`CREATED` is a WorkManagement-layer event emitted by backends with a creation boundary (Paperclip only, via `create_work()`). `InMemoryOrganisationControlPlane` has no creation boundary — Work is constructed outside OCP and passed in. The `STARTED`, `QUEUED`, and `ESCALATED` events are contract capabilities for future operational integration and are not wired speculatively.

### Hypothesis 3 — `_emit_work_event(assignee_id=...)` can be safely simplified

**Confirmed.**

The `assignee_id` parameter is accepted but never read in either implementation. All assignee data is read from the `Work` object directly. Only two internal call sites (`assign_work` in each OCP implementation) pass it. Removing the parameter does not alter event payloads, deduplication, or Work state transitions.

---

## 7. Cleanup Performed

Removed the redundant `assignee_id` parameter from `_emit_work_event` in both implementations:

### Files Changed

| File | Method | Change |
|------|--------|--------|
| `packages/organisation/src/organisation_control_plane.py` | `InMemoryOrganisationControlPlane._emit_work_event` | Removed `assignee_id: str \| None = None` parameter |
| `packages/organisation/src/organisation_control_plane.py` | `InMemoryOrganisationControlPlane.assign_work` (call site) | Removed `assignee_id=assignee.id` argument |
| `packages/organisation_paperclip/src/organisation_paperclip.py` | `PaperclipOrganisationControlPlane._emit_work_event` | Removed `assignee_id: str \| None = None` parameter |
| `packages/organisation_paperclip/src/organisation_paperclip.py` | `PaperclipOrganisationControlPlane.assign_work` (call site) | Removed `assignee_id=assignee_id` argument |

### What Was NOT Changed

- **Event payloads**: `WorkEvent` field values are identical — `assignee_actor_id`, `assignee_role_id`, `assignee_agent_id` are all still read from `Work`.
- **Event types**: No new emissions added. No existing emissions removed.
- **Lifecycle semantics**: `ASSIGNED → READY → COMPLETED/FAILED/CANCELLED` is unchanged.
- **Work state transitions**: `WorkStatus` mutations are unchanged.
- **Deduplication**: `_processed_event_ids` mechanism is unchanged.
- **Paperclip `create_work()`**: Still emits `CREATED` — that path is unaffected.
- **Assignment construction**: The `assignee_id` local variable in `assign_work` (used to build `Assignment` records) is retained; only the `_emit_work_event` parameter was removed.

### Regression Tests

File: `packages/organisation/tests/test_increment45_work_event_lifecycle.py`

| Test | Verifies |
|------|----------|
| `test_inmemory_emit_work_event_no_longer_accepts_assignee_id` | `inspect.signature` confirms parameter is gone |
| `test_inmemory_assigned_event_carries_actor_id_from_work` | ASSIGNED event for Role assignment carries `assignee_role_id` from `Work` |
| `test_inmemory_assigned_event_carries_actor_id_when_assigned_to_actor` | ASSIGNED event for Actor assignment carries `assignee_actor_id` from `Work` |
| `test_inmemory_ready_event_payload_unchanged` | READY event payload unaffected |
| `test_inmemory_completed_event_payload_unchanged` | COMPLETED event payload unaffected |
| `test_paperclip_emit_work_event_no_longer_accepts_assignee_id` | Signature confirms parameter is gone |
| `test_paperclip_assigned_event_carries_assignee_from_work` | Paperclip ASSIGNED event carries `assignee_agent_id` from `Work` |
| `test_paperclip_created_event_payload_unchanged` | Paperclip CREATED event (from `create_work`) unaffected |

### No Lifecycle Production Behaviour Changed

**Explicit statement:** No production behaviour related to the Work event lifecycle, Work state transitions, event payloads, or event consumers was changed. The only modification is removing a dead parameter from two internal method signatures and their two internal call sites.

---

## 8. Validation

```
$ python -m pytest packages/organisation/tests/test_increment45_work_event_lifecycle.py -v --tb=short
# 8 passed

$ python -m pytest packages/organisation/tests/test_increment44_organisational_change_semantics.py -v --tb=short
# 13 passed

$ python -m pytest packages/organisation/tests/test_increment43_organisation_change_execution.py -v --tb=short
# 37 passed

$ python -m pytest packages/organisation -v --tb=short
# 698 passed

$ python -m pytest packages/workflow_runner/tests -v --tb=short
# 310 passed, 60 failed, 4 skipped
# Note: 60 failures are pre-existing integration test failures requiring
# external services (Paperclip instance, AI API). Tests directly related
# to this change (test_operations.py, test_operational_handler.py,
# test_paperclip_integration.py) all pass: 23 passed, 3 skipped.

$ python -m ruff check packages/organisation packages/workflow_runner packages/organisation_paperclip packages/contracts
# Pre-existing lint errors in workflow_runner tests.
# Changed files pass ruff check:
#   packages/organisation/src/organisation_control_plane.py
#   packages/organisation_paperclip/src/organisation_paperclip.py
#   packages/organisation/tests/test_increment45_work_event_lifecycle.py
```

### git diff --stat (changed files only)

```
 packages/organisation/src/organisation_control_plane.py    |  4 +--  (removed assignee_id param + call site arg)
 packages/organisation_paperclip/src/organisation_paperclip.py | 4 +--  (removed assignee_id param + call site arg)
 packages/organisation/tests/test_increment45_work_event_lifecycle.py | (new, 8 tests)
 packages/organisation/tests/increment45_report.md              | (updated)
```


## Files Investigated

- `packages/contracts/organisational_events.py` — `WorkEventType` enum and `WorkEvent` model
- `packages/organisation/src/organisation_control_plane.py` — InMemory implementation with all event emissions
- `packages/organisation_paperclip/src/organisation_paperclip.py` — Paperclip adapter with all event emissions
- `packages/organisation/src/adapters/work_management_adapter.py` — Work creation via port adapter
- `packages/workflow_runner/src/operations.py` — Event consumer (only processes READY)
- `packages/workflow_runner/src/operational_handler.py` — Execution backends
- `packages/organisation/tests/test_events.py` — Event emission tests
- `packages/workflow_runner/tests/test_operations.py` — Operations event handling tests
- `packages/organisation_paperclip/tests/test_smoke.py` — Smoke test showing event flow
- `packages/organisation_paperclip/tests/test_integration.py` — Integration tests
- `docs/architecture/INCREMENT-21W-ORGANISATIONAL-EVENT-AND-COMMUNICATION-BOUNDARY.md` — Event contract and origin model
- `docs/architecture/INCREMENT-21Y-PAPERCLIP-VERTICAL-SLICE.md` — Paperclip event propagation
- `docs/architecture/INCREMENT-21X-PAPERCLIP-INTEGRATION.md` — Paperclip concept mapping
- `.kilo/context/architecture.md` — Work lifecycle and handoff architecture
- `packages/organisation/src/role.py` — Work and WorkStatus model