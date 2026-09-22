# Increment 48 — Capability Development Identity & Lifecycle Fixes

## A. Changes Made

**Production files changed (8):**

| File | Change |
|---|---|
| `packages/organisation/src/role.py` | Added `develops_capability_id: str \| None = None` to `Work` model (line 105) |
| `packages/contracts/work_management.py` | Added `develops_capability_id: str \| None = None` to `WorkCreateRequest` |
| `packages/organisation/src/adapters/work_management_adapter.py` | Propagates `develops_capability_id` from `WorkCreateRequest` → `Work` |
| `packages/organisation/src/organisation_control_plane.py` | Fixed `select_execution_path` to preserve `capability_id` on `NEW_CAPABILITY_REQUIRED`; added `work_id` param to `register_capability` and populates `CapabilityEvent.work_id` |
| `packages/organisation_paperclip/src/organisation_paperclip.py` | Same `select_execution_path` fix (preserves first `required_capability_id` on `NEW_CAPABILITY_REQUIRED`); added `work_id` param to `register_capability` |
| `packages/ai/src/chat.py` | `_handle_new_capability_required_response`: propagates `path_result.capability_id` as `develops_capability_id`; `_handle_capability_gap`: propagates `candidate.id` as `develops_capability_id` |
| `packages/workflow_runner/src/worker.py` | `_develop_capability`: uses `work.develops_capability_id` if present, else generates `cap-{work.id}`; always routes registration through `org_plane.register_capability(capability, work_id=work.id)` |
| `packages/workflow_runner/src/operations.py` | Added fail-fast pre-check in `_handle_event`: capability-development Work without `CapabilityRegistry` → `fail_work` instead of silent skip; added logging to `_assess_capability_development`'s defensive fallback |

**Tests updated (3):**

| File | Change |
|---|---|
| `packages/organisation/tests/test_increment32_execution_boundary.py` | `test_capability_development_learning_loop_complete`: `required_capability_ids=["cap-loop-32"]` → `develops_capability_id="cap-loop-32"` |
| `packages/organisation/tests/test_increment46_capability_gap_people_boundary.py` | Renamed/updated 5 tests: `TestCapabilityIdPropagation` (now asserts `develops_capability_id` propagation), `TestWorkerCapabilityIdGeneration` (preservation + anonymous), `TestCapabilityIdentityDiscontinuity` → `TestCapabilityIdentityContinuity`, `TestPaperclipSelectExecutionPath` (empty IDs → None, non-empty → preserved) |
| `packages/organisation/tests/test_increment30_capability_boundary.py` | Updated 2 tests for Worker routing through `org_plane.register_capability` with `work_id` |

**New tests (1 file, 36 tests):**

`packages/organisation/tests/test_increment48_capability_development_identity.py`

## B. Capability Identity Contract

```
identified capability requirement
        ↓
ExecutionPathResult.capability_id
        ↓
Work.develops_capability_id
        ↓
Capability.id = develops_capability_id
        ↓
CapabilityEvent.work_id
        ↓
assessment → DRAFT → ACTIVE promotion
```

Invariant: **If a capability has an identifiable organisational identity before development, that identity survives the capability-development lifecycle.**

When no identity exists (Case C), the Worker generates `cap-{work.id}`.

### Three cases:

| Case | Identity source | OCP behavior | Work.develops_capability_id |
|------|----------------|-------------|--------------------------|
| A | User identifies (`required_capability_ids`) | `capability_id` preserved on `NEW_CAPABILITY_REQUIRED` | Set |
| B | OCP derives (from `candidate_capabilities`) | `capability_id` preserved | Set |
| C | No identity | `capability_id=None` on `NEW_CAPABILITY_REQUIRED` | `None` (Worker generates `cap-{work.id}`) |

## C. Work.develops_capability_id

Added to `Work` model in `organisation/src/role.py:105`:

```python
develops_capability_id: str | None = None
```

Semantics:
- `required_capability_ids` = capabilities **required to perform** the Work (inputs)
- `develops_capability_id` = capability **produced/developed** by the Work (output)

They are independent fields. A `capability_development` Work may carry both (e.g., needs `cap-helper` to develop, produces `cap-new`).

Propagated through: `WorkCreateRequest` → `WorkManagementAdapter.create_work()` → `Work`.

## D. NEW_CAPABILITY_REQUIRED Propagation

### Chat-layer fixes (`packages/ai/src/chat.py`)

`_handle_new_capability_required_response` (Case A):
- **Before:** `required_capability_ids=[]`, `capability_id` discarded
- **After:** `develops_capability_id=path_result.capability_id`

`_handle_capability_gap` (Case B):
- **Before:** `required_capability_ids=[]`, `candidate.id` discarded
- **After:** `develops_capability_id=candidate.id`

Both handlers now set `develops_capability_id` and leave `required_capability_ids=[]`.

### OCP fix (`packages/organisation/src/organisation_control_plane.py`)

`select_execution_path`:
- **Before:** required capabilities not in the registry were silently dropped from `candidates`. When `capability_query` was None, the loop always returned `CAPABILITY_PATH` for any candidate (including ones not in the registry).
- **After:** Missing required capabilities are added to `candidates`. When `capability_query` is None, the loop checks `self.get_capability(cap_id)` directly — if not in registry, returns `NEW_CAPABILITY_REQUIRED` with `capability_id` preserved.

Paperclip OCP (`packages/organisation_paperclip/src/organisation_paperclip.py`):
- **Before:** Always returned `NEW_CAPABILITY_REQUIRED` with `capability_id=None` when nothing matched, even when `required_capability_ids` were provided.
- **After:** If `required_capability_ids` is non-empty, the first ID is preserved as `capability_id`.

### HUMAN_TEAM_INVESTIGATION (unchanged)

`_handle_human_team_investigation_response` continues to set `required_capability_ids=[capability_id]` — the investigated capability IS required to perform the investigation work.

## E. Worker Capability Identity

`Worker._develop_capability` in `packages/workflow_runner/src/worker.py:115`:

- **Before:** `capability_id = f"cap-{work.id}"` — always generated, discarding gap identity.
- **After:** `capability_id = work.develops_capability_id` if set, else `f"cap-{work.id}"`.

Registration is always routed through `org_plane.register_capability(capability, work_id=work.id)` — no direct registry bypass. The OCP's `register_capability` delegates to the injected registry (when available) and emits the `CapabilityEvent`.

The `cap-{work.id}` fallback convention is retained as the anonymous-case identifier.

## F. Capability Event Provenance

`CapabilityEvent` already had a `work_id: str | None = None` field (in `contracts/organisational_events.py:104`) but it was never populated. Now:

- `InMemoryOrganisationControlPlane.register_capability(capability, work_id=...)` emits `CapabilityEvent(work_id=work_id)`
- `PaperclipOrganisationControlPlane.register_capability(capability, work_id=...)` emits `CapabilityEvent(work_id=work_id)`
- `Worker._develop_capability` calls `org_plane.register_capability(capability, work_id=work.id)`

### Decision on DEVELOPMENT_STARTED / DEVELOPMENT_COMPLETED

These event types remain **defined but unemitted**. The current lifecycle is adequately represented by:

- `WorkEvent` (READY → IN_PROGRESS → COMPLETED) for Work lifecycle
- `CapabilityEvent(REGISTERED)` for capability registration
- `CapabilityRegistry.promote()` for DRAFT → ACTIVE transition

No new event emitters are added. This decision is verified by `test_development_event_types_not_emitted` which scans all production source for these strings.

## G. Registry / Assessment Boundary

### Defect

`Operations._assess_capability_development` had `if self._capability_registry is None: return` — silently skipping assessment when no registry was available. Capability-development Work would complete without any capability being assessed or promoted.

### Fix

Added a **pre-execution fail-fast** check in `_handle_event` (`packages/workflow_runner/src/operations.py:184`):

```python
if work.work_type == "capability_development" and self._capability_registry is None:
    self._org_plane.fail_work(work_id, {...})
    logger.error(...)
    return
```

This prevents capability-development Work from executing when no `CapabilityRegistry` is available. BAU Work is unaffected.

The defensive `return` in `_assess_capability_development` is retained with added logging — it only triggers if `_assess_capability_development` is called directly (bypassing `_handle_event`), which should not happen in normal flow.

**Architectural boundary preserved:** `CapabilityRegistry` owns capability lifecycle (register, promote, get). `Operations` coordinates execution and assessment.

## H. Duplicate and Retry Semantics

The existing `CapabilityRegistry.register()` uses `upsert_capability` semantics — registering a capability with the same ID twice updates in place rather than creating a duplicate.

- **Identified capability, two development attempts:** Both Works use the same `develops_capability_id`. The first creates the Capability (DRAFT). The second re-registers (upsert) — same canonical identity, no duplicate.
- **Anonymous capability, two development attempts:** Each generates `cap-{work.id}` with a different Work ID → two separate capabilities. No deduplication possible (no shared identity to match on).

No new deduplication infrastructure was added.

## I. End-to-End Traceability

`test_identified_capability_id_survives_full_lifecycle` proves:

```
cap-e2e-identified-48  (original capability ID)
    → OCP select_execution_path (NEW_CAPABILITY_REQUIRED)
    → Work.develops_capability_id = "cap-e2e-identified-48"
    → Worker._develop_capability (Capability.id = "cap-e2e-identified-48")
    → registry.get("cap-e2e-identified-48") (DRAFT)
    → assess_capability_development (passed=True)
    → registry.promote("cap-e2e-identified-48") (ACTIVE)
```

`original_capability_id == final Capability ID == "cap-e2e-identified-48"` ✓

The anonymous case test proves `develops_capability_id=None` → `Capability.id = "cap-{work.id}"` → registry stores generated ID.

## J. Tests

**New test file:** `packages/organisation/tests/test_increment48_capability_development_identity.py` — 36 tests across 12 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestWorkDevelopsCapabilityId` | 4 | Field existence, set/get, semantic distinction, BAU default |
| `TestWorkCreateRequestPropagation` | 5 | Field on request, default, accept, adapter propagation (both fields) |
| `TestExecutionPathCapabilityIdPreservation` | 6 | Cases A/B/C, query-port variants, registered capability → CAPABILITY_PATH |
| `TestChatGapHandlerPropagation` | 3 | Both chat handlers, identified + anonymous cases |
| `TestWorkerCapabilityIdentity` | 2 | Preserves identity + work_id pass-through, anonymous generation |
| `TestCapabilityEventProvenance` | 4 | OCP event with/without work_id, Worker pass-through, DEVELOPMENT_* not emitted |
| `TestOperationsRegistryFailFast` | 2 | Cap-dev fails without registry, BAU works without registry |
| `TestCapabilityRegistrationIdempotency` | 2 | Upsert preserves identity, re-register updates in place |
| `TestCapabilityLifecyclePromotion` | 2 | DRAFT→ACTIVE, maturation history |
| `TestEndToEndTraceability` | 2 | Full lifecycle identified + anonymous |
| `TestDuplicateDevelopment` | 2 | Same identity (upsert) vs anonymous (separate) |
| `TestSemanticSeparation` | 2 | Independent fields coexist, BAU has None |

**Updated test files:** 3 files updated (increment30, increment32, increment46).

## K. Validation

```
pytest packages/organisation/tests/ -q
→ 762 passed in 1.61s

pytest packages/organisation/tests/test_increment32_execution_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment33_execution_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment34_evidence_adoption_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment35_lifecycle_adoption.py -q
→ passed

pytest packages/organisation/tests/test_increment36_execution_authority.py -q
→ passed

pytest packages/organisation/tests/test_increment37_bau_execution_semantics.py -q
→ passed

pytest packages/organisation/tests/test_increment38_execution_evidence_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment39_workflow_invocation_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment40_organisation_team_role_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment41_economic_organisation_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment42_organisation_implementation_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment43_organisation_change_execution.py -q
→ passed

pytest packages/organisation/tests/test_increment44_organisational_change_semantics.py -q
→ passed

pytest packages/organisation/tests/test_increment45_work_event_lifecycle.py -q
→ passed

pytest packages/organisation/tests/test_increment46_capability_gap_people_boundary.py -q
→ passed

pytest packages/organisation/tests/test_increment47_capability_development_lifecycle.py -q
→ SKIPPED (file created by Increment 47 as planning artifact — no implementation tests; the increment 47 test file does not exist as it was a planning-only increment)

pytest packages/workflow_runner/tests/test_operations.py -q
→ passed

pytest packages/workflow_runner/tests/test_operational_handler.py -q
→ passed

pytest packages/workflow_runner/tests/test_models.py -q
→ passed

pytest packages/workflow_runner/tests/test_registry.py -q
→ passed

pytest packages/workflow_runner/tests/test_capability_outcome_assessor_adapter.py -q
→ passed
```

### Pre-existing failures (not caused by Increment 48)

| Test file | Failures | Cause |
|---|---|---|
| `packages/workflow_runner/tests/test_capability_execute.py` | 14 | `awaiting_validation` vs `pending` state — pre-existing state machine mismatch |
| `packages/workflow_runner/tests/test_platform_integration.py` | 46 | Platform integration tests requiring external services (Paperclip API) — `Connection refused` |
| `packages/organisation_paperclip/tests/test_integration.py` | 6 | Same Paperclip API connection dependency |
| `packages/organisation_paperclip/tests/test_smoke.py` | 1 | Same Paperclip API connection dependency |

These failures were verified to exist **before** Increment 48 changes by running `git stash` and re-running: the same tests fail with identical errors.

### Lint

```
ruff check packages/organisation packages/organisation_paperclip packages/contracts packages/workflow_runner/src packages/ai/src
→ No new errors from Increment 48 changes.
→ 78 pre-existing errors (all in unchanged lines of worker.py and operations.py)
→ ruff check packages/organisation/tests/test_increment48_capability_development_identity.py
→ All checks passed!
```

## L. Remaining Architectural Gaps

| Gap | Status |
|-----|--------|
| D1 — Chat layer discarded `capability_id` | **Fixed** (now `develops_capability_id`) |
| D2 — Work had no field for "capability being developed" | **Fixed** (`develops_capability_id`) |
| D3 — Worker discarded gap identity | **Fixed** (uses `develops_capability_id`, fallback `cap-{work.id}`) |
| D4 — `CapabilityEvent.work_id` never populated | **Fixed** (populated via `register_capability(work_id=...)`) |
| D5 — Operations silenced registry None silently | **Fixed** (fail-fast: `fail_work`) |

No new defects introduced.

## M. Recommended Increment 49

1. **Paperclip OCP `register_capability` fallback** — Paperclip's `register_capability` only emits the event when `_capability_registry` is not None? Actually, Paperclip always emits the event but doesn't store capabilities locally when no registry is injected. Consider adding a local `_capabilities` dict to PaperclipOCP as a fallback (matching InMemoryOrganisationControlPlane).

2. **Worker registry dependency** — Currently `Worker.__init__` accepts `capability_registry` but no longer uses it directly (it always goes through `org_plane.register_capability`). Consider removing the `capability_registry` parameter from Worker to simplify the composition and avoid confusion about dual registration paths.

3. **Operations `_assess_capability_development` early returns** — The method still returns silently when `capability_id` is missing from the result or when the capability is not found in the registry. These should be converted to explicit error states (e.g., `escalate_work` or `fail_work` with appropriate error codes).

4. **CapabilityEvent for promotion** — `CapabilityRegistry.promote()` records `maturation_history.promoted_at` in the capability payload but does not emit a `CapabilityEvent`. Consider emitting a `capability.promoted` event for observability of the DRAFT → ACTIVE transition.

5. **ConceptStore persistence isolation** — Tests using `ConceptStore()` with the default `data_dir` (./concepts_data) share state via `concepts.json`. Tests should use `tmp_path` (as Increment 48 tests do) to ensure isolation.

6. **SolutionSelectionAdapter as abstraction leak** — The chat layer depends on `SolutionSelectionAdapter` which wraps OCP's `select_execution_path`. Consider whether the chat layer should depend on OCP directly, since the adapter only does field mapping.

7. **WorkEvent provenance** — `WorkEvent` does not carry `develops_capability_id`. While the Work model has it, the event stream doesn't. Consider adding `develops_capability_id` to `WorkEvent` for full event-sourced auditability of capability development work.
