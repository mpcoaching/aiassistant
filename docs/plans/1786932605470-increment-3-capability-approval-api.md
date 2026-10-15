# Increment 3 — Capability Approval API (Option C): Completion Fixes

**Status:** Architecture approved as Option C. Implementation is mostly complete; 6 of 19 tests fail due to two missing imports. This plan provides the exact fix instructions and completion criteria.

## Execution order

1. Fix `test_capability_request.py` imports.
2. Fix `api.py` datetime import.
3. Run targeted test suite.
4. Run broader regression suite.
5. Report results.

## Step 1 — Fix test imports

**File:** `packages/capability_registry/tests/test_capability_request.py`

Replace the current single-line import block:

```python
from concepts import ConceptKind, ConceptStore, EnterpriseConcept
```

With:

```python
from concepts import (
    ConceptKind,
    ConceptStore,
    EnterpriseConcept,
    Provenance,
    RecognitionLevel,
)
```

**Why:** `Provenance` and `RecognitionLevel` are used in the `_approved_concept` helper (lines ~100) to construct `EnterpriseConcept` objects in tests. Without them, four promotion tests fail with `NameError: name 'Provenance' is not defined`.

**Affected tests:**
- `test_approved_concept_has_correct_status`
- `test_approved_concept_preserves_governance`
- `test_approved_concept_preserves_specification`
- `test_approved_concept_persists`

## Step 2 — Fix api.py datetime import

**File:** `packages/workflow_runner/api.py`

Add to the existing import section:

```python
from datetime import datetime, timezone
```

**Where:** Check whether `datetime` or `timezone` is already imported in `api.py`. If either is already present, do not duplicate. Add both only if neither is imported.

**Why:** The endpoint function `assistant_capability_request_approve` (around line 725) uses `datetime.now(timezone.utc).isoformat()` inside the `modify` action branch, but these names are not in scope. The helper function `_approve_capability_request` has a local `from datetime import datetime, timezone`, which masks the issue for `approve` but not for `modify`.

**Affected test:**
- `test_modify_endpoint_updates_specification`

## Step 3 — Run targeted tests

```bash
python3 -m pytest packages/capability_registry/tests/test_capability_request.py -v
```

**Expected:** 19 passed, 0 failed.

## Step 4 — Run broader regression suite

```bash
python3 -m pytest packages/capability_registry/tests/ packages/ai/tests/test_assistant.py -v
```

**Expected:** All pre-existing tests remain green. Increment 3 tests pass alongside.

## Completion criteria

Increment 3 is complete only when **all** of the following are true:

- [ ] `19/19` capability-request tests pass
- [ ] `test_approve_without_server_side_state` passes (Option C proof point)
- [ ] Broader regression suite (`packages/capability_registry/tests/` + `packages/ai/tests/test_assistant.py`) is green
- [ ] No unrelated files changed
- [ ] `CapabilityRegistry.register()` is still not involved
- [ ] Approved requests still become `EnterpriseConcept(kind=capability, status=draft)`

## Report format

After running the suites, report:

1. Final test counts for both runs (e.g., `19 passed, 0 failed` and `X passed, Y failed`).
2. Whether `test_approve_without_server_side_state` passed.
3. Any unexpected issues (import conflicts, new failures, etc.).
4. Explicit confirmation that Increment 3 is complete or, if not, which criteria failed.

## Constraints

- Do not begin Increment 4 until these results are reported.
- Do not change architecture, add new modules, or modify files outside the two imports listed above.
