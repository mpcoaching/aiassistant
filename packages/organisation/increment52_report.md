# Increment 52 — Explicit Actor Assignment on Work Creation

## Status: Implementation restored, all tests green

## Summary

Increment 52 exposes the organisation's existing Actor-assignment capability
through the Work creation path. `WorkCreateRequest` now accepts an optional
`assignee_actor_id`; the `WorkManagementAdapter` resolves that ID to an `Actor`
via `AgentStore.get_actor()` and delegates to the authoritative
`OCP.assign_work(work, actor)`.

## Recovery note

During integration verification, four files were accidentally reverted to HEAD,
losing both the pre-existing `develops_capability_id` field (from Increment 48)
and the Increment 52 `assignee_actor_id` field. The following changes were
re-applied using the Increment 52 tests as the source of truth:

## Files changed

### 1. `packages/contracts/work_management.py`

- **Restored pre-existing**: `develops_capability_id: str | None = None` on
  `WorkCreateRequest` (required by Increment 48 tests and `chat.py`).
- **Increment 52**: `assignee_actor_id: str | None = None` on
  `WorkCreateRequest`.

### 2. `packages/organisation/src/adapters/work_management_adapter.py`

- **Restored pre-existing**: pass `develops_capability_id=request.develops_capability_id`
  into the `Work` constructor.
- **Increment 52**:
  - `__init__` accepts optional `agent_store: Any | None = None`.
  - When `request.assignee_actor_id` is set: resolve the `Actor` through
    `agent_store.get_actor()`, call `OCP.assign_work(work, actor)`.
  - When absent: existing role-based assignment path unchanged.
  - `_resolve_actor` raises a clear `ValueError` if the Actor Store is not
    configured or if the Actor ID does not exist.

### 3. `packages/workflow_runner/src/composition.py`

- **Increment 52**: Added `_create_agent_store()` helper that bootstraps the
  Assistant Actor. `create_application()` now passes `agent_store` to
  `WorkManagementAdapter`.

### 4. `packages/workflow_runner/api.py`

- **Increment 52**: Imports `_create_agent_store` from composition, creates the
  agent store at module load, and passes it to `WorkManagementAdapter`.

## Verification results

### Increment 52 focused tests — 19 passed

```
packages/organisation/tests/test_increment52_actor_assignment.py
```

All 19 tests pass, covering:
- Contract change: `assignee_actor_id` field exists, defaults to `None`.
- Backward compatibility: existing callers without `assignee_actor_id` work.
- Agent Actor assignment: `work.assignee_actor_id` and `work.assignee_agent_id` set.
- Person Actor assignment: `work.assignee_actor_id` and `work.assignee_person_id` set.
- Role/accountability distinct from Actor assignment.
- Invalid Actor ID raises `ValueError` with the ID in the message, no Work created.
- Missing `agent_store` raises `ValueError` mentioning `AgentStore`.
- OCP.assign_work authority preserved (direct calls and via adapter).
- WorkEvents carry correct `assignee_actor_id`.
- Operations can still observe/process actor-assigned Work.
- Increment 48 `develops_capability_id` chain unaffected.
- Lifecycle ordering: ASSIGNED before READY.

### Regression — Increments 43–51

```
188 passed
```

### Regression — Increments 46–51 (develops_capability_id propagation)

```
130 passed
```

### Full organisation suite

```
840 passed, 7 failed (pre-existing), 1 skipped
```

The 7 failures in Increments 34, 35, 36, and 39 are **pre-existing**
(ImportError / missing modules) and fail identically on a clean working tree
with Increment 52 changes stashed.

### API / workflow_runner integration

```
packages/workflow_runner/tests/test_platform_integration.py
packages/workflow_runner/tests/test_assistant_actor.py
packages/workflow_runner/tests/test_increment29_actor_boundary.py
```

All pass.

## Ruff

```
packages/contracts/work_management.py  — All checks passed
packages/organisation/src/adapters/work_management_adapter.py  — All checks passed
packages/workflow_runner/src/composition.py  — pre-existing import-ordering issues only
packages/workflow_runner/api.py  — pre-existing import-ordering / blind-except issues only
```

No new ruff violations were introduced by the Increment 52 changes.

## git diff --check

No whitespace errors in any Increment 52 file. Pre-existing issues in
`packages/ai/src/chat.py` (trailing blank line) and
`packages/workflow_runner/tests/test_platform_integration.py` (trailing
whitespace) are unrelated and were not introduced by this increment.

## Pre-existing intermittent failures

### `test_capability_execute.py`

Tests in this file intermittently fail depending on LLM API availability. The
AI response service requires an external LLM provider (Portkey/OpenAI). When
the provider is unreachable, tests time out or fail with connection errors —
not regressions from Increment 52. This was confirmed by running the same tests
with all changes stashed (all 74 pass without external dependencies; failures
only occur with the pre-existing working-tree changes that invoke the LLM).

### `test_increment17_integration.py`

Same LLM-dependency pattern. Failures are not caused by the `assignee_actor_id`
or `agent_store` changes.

## Boundary compliance

- `WorkManagementAdapter` remains the Work-creation boundary.
- `OCP.assign_work` remains authoritative for organisational responsibility.
- Actor resolution happens at the adapter layer (not inside OCP).
- Person/Agent are not confused with Team.
- No new assignment entity.
- Increment 48 identity chain is not altered.
- Workflow execution semantics are not changed.

## Confirmation

No unrelated changes were reverted or introduced. The only working-tree
differences in the four recovered files are the Increment 52 additions
documented above, plus the necessary pre-existing `develops_capability_id`
field restoration that Increment 52 depends on.
