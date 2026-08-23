# Increment 19 — Capability Maturation Investigation

## 1. Executive Conclusion

Increment 18 successfully wired execution outcomes to durable telemetry. The system now records every capability invocation. However, **the recorded data is insufficient to support legitimate maturation decisions** because outcome assessment does not exist for capabilities.

The single most important architectural finding is:

**Execution success ≠ Capability success, and the system currently treats them as identical.**

`InvocationRecorderAdapter._determine_outcome()` collapses all non-error outcomes into `"success"`, including:
- Authorisation failures (actor not permitted)
- Missing deployments (capability not executable)
- Capability-not-found (invalid ID)
- Operational success (capability ran)

All of these are stored identically in `MaturationHistory`, which means:
1. `invocation_count` is inflated by events that are not actual executions
2. `correction_count` is the only differentiator, but it only tracks errors, not quality
3. No threshold or candidacy logic can make meaningful decisions from this data
4. `promotion_candidacy` exists in `MaturationHistory` but is never set and never checked

The smallest defensible next increment is **Outcome Assessment for Capability Invocations** — an explicit evaluation step that distinguishes execution outcomes from capability outcomes before they reach maturation.

---

## 2. Capability Lifecycle Analysis

### States

| State | Meaning | Transitions |
|-------|---------|-------------|
| `DRAFT` | Capability exists but has not been validated through use | → `ACTIVE` (via `promote()`) |
| `ACTIVE` | Capability is available for execution | → `DEPRECATED` (not implemented) |
| `DEPRECATED` | Capability should no longer be used | No transitions implemented |

### What `promote()` Actually Does

`CapabilityRegistry.promote()` (`capabilities.py:84-94`):

```python
def promote(self, capability_id: str) -> Capability:
    cap = self.get(capability_id)
    if cap is None:
        raise KeyError(f"Capability not found: {capability_id}")
    history = cap.payload.get("maturation_history") or {}
    history["promoted_at"] = datetime.now(timezone.utc).isoformat()
    cap.payload["maturation_history"] = history
    cap.status = CapabilityStatus.ACTIVE
    if self._repository is not None:
        self._repository.upsert_capability(cap)
    return cap
```

**It is a stub.** It:
- Checks nothing
- Reads no thresholds
- Consults no invocation history
- Ignores `promotion_candidacy`
- Unconditionally sets status to `ACTIVE`

### What `MaturationHistory` Tracks

`MaturationHistory` (`concepts.py:52-59`):

| Field | Type | Purpose | Currently Updated? |
|-------|------|---------|-------------------|
| `invocation_count` | `int` | Total invocations | ✅ By `ConceptStore.record_invocation()` |
| `correction_count` | `int` | Failed invocations | ✅ By `ConceptStore.record_invocation()` |
| `last_invoked_at` | `datetime` | Most recent invocation | ✅ By `ConceptStore.record_invocation()` |
| `promoted_at` | `datetime` | When promotion occurred | ✅ By `CapabilityRegistry.promote()` |
| `promotion_candidacy` | `bool` | Whether capability meets promotion criteria | ❌ Never set, never checked |

### Promotion Scope

Promotion is **capability-level**. It applies to the `Capability` domain record, not to:
- A specific deployment (`CapabilityDeployment`)
- A specific person/agent (`CapabilityProficiency`)
- A specific environment

`CapabilityRegistry.promote()` changes `Capability.status` from `DRAFT` to `ACTIVE`. This represents **maturity/availability** — the capability has been validated sufficiently to be considered production-ready.

### Proficiency vs Maturity

| Concept | Model | Plane | Purpose |
|---------|-------|-------|---------|
| **Maturity** | `Capability.status` + `MaturationHistory` | People/Capability | How well the capability itself performs |
| **Proficiency** | `CapabilityProficiency` | People/Capability | How well a person/agent can exercise the capability |

These are distinct. A capability can be `ACTIVE` (mature) while a specific agent is still `NOVICE` at using it. Maturation is about the capability, not the user.

### Existing Lifecycle Tests

| Test | What It Proves | Gap |
|------|---------------|-----|
| `test_promote_sets_active_status` | `promote()` changes status to ACTIVE | Does not test any conditions or thresholds |
| `test_learning_loop_promotes_capability_after_threshold` | Aspirational name; calls `promote()` directly | **No threshold is actually checked** |
| `test_capability_payload_carries_maturation` | `MaturationHistory` round-trips through ConceptStore | Does not test promotion logic |

---

## 3. Invocation Telemetry State

### Complete Data Path (Increment 18)

```
ExecutionResult
  → InvocationRecorder.record_invocation(capability_id, result, actor_context)
    → InvocationRecorderAdapter.record_invocation()
      → _determine_outcome(result) → "success" | "failure"
      → ConceptStore.record_invocation(concept_id, outcome)
        → MaturationHistory updated in EnterpriseConcept.payload
```

### What Is Stored

`ConceptStore.record_invocation()` (`concepts.py:109-121`) updates `MaturationHistory`:

```python
history_obj.invocation_count += 1
if outcome != "success":
    history_obj.correction_count += 1
history_obj.last_invoked_at = datetime.now(timezone.utc)
concept.payload["maturation_history"] = history_obj.model_dump()
```

**What is persisted:**
- `invocation_count` — aggregated total
- `correction_count` — aggregated failures
- `last_invoked_at` — timestamp of most recent invocation

**What is NOT persisted:**
- Per-invocation timestamps (only the latest)
- Actor context (who invoked it)
- Deployment identifier (which environment/transport)
- Execution metadata (module path, execution mode)
- Individual outcome details
- Invocation sequence/history

### Can the System Retrieve Meaningful Invocation History?

**Partially, but insufficiently for maturation.**

You can retrieve the current aggregated state via:
```python
concept = store.get(capability_id)
history = concept.payload.get("maturation_history", {})
invocation_count = history.get("invocation_count")
correction_count = history.get("correction_count")
last_invoked_at = history.get("last_invoked_at")
```

But you **cannot**:
- Retrieve a chronological list of invocations
- Filter invocations by actor, deployment, or time range
- Calculate success rate over a specific window
- Determine whether recent invocations are successful (only latest timestamp exists)
- Distinguish between different failure modes

### What `InvocationRecorderAdapter` Determines

`_determine_outcome()` (`invocation_recorder_adapter.py:36-41`):

```python
def _determine_outcome(self, result: ExecutionResult) -> str:
    telemetry = result.telemetry or {}
    outputs = result.outputs or {}
    if telemetry.get("error") or outputs.get("error") or "authorisation" in telemetry:
        return "failure"
    return "success"
```

**This is the critical problem.** The outcome determination conflates:

| Scenario | Current Outcome | Should Be |
|----------|----------------|-----------|
| Execution completed successfully | `"success"` | `"success"` |
| Execution raised an exception | `"failure"` | `"failure"` (execution failure) |
| Actor not authorised | `"failure"` | `"not_executed"` (not a capability quality issue) |
| Capability not found | `"failure"` | `"not_executed"` (not a capability quality issue) |
| No deployment available | `"failure"` | `"not_executed"` (not a capability quality issue) |
| Execution completed but output is empty/garbage | `"success"` | `"failure"` (outcome failure — needs assessment) |

The current logic treats `"not_executed"` scenarios identically to `"failure"` scenarios, which corrupts `correction_count`. And it treats all operational successes identically, with no quality assessment.

---

## 4. Outcome Assessment Gap

### What Exists for Work

The `organisation` plane has `assess_work_outcome()` (`outcome.py:15-57`):

```python
def assess_work_outcome(work, execution_result) -> dict[str, Any]:
    criteria = work.acceptance_criteria or []
    outputs = execution_result.get("outputs", {})
    output_summary = str(outputs.get("summary", outputs))
    
    criteria_met = []
    criteria_failed = []
    for criterion in criteria:
        if criterion.lower() in output_summary.lower():
            criteria_met.append(criterion)
        else:
            criteria_failed.append(criterion)
    
    accepted = len(criteria_failed) == 0 and execution_result.get("status") == "completed"
    
    return {
        "accepted": accepted,
        "execution_result": execution_result,
        "criteria_met": criteria_met,
        "criteria_failed": criteria_failed,
        "rationale": ...,
    }
```

This is used by `record_work_learning()` to create `EnterpriseConcept` records for completed work.

### What Does NOT Exist for Capabilities

There is **no** equivalent `assess_capability_outcome()` anywhere in the codebase. The search for `assess.*capability`, `evaluate.*capability`, `capability.*assess` returns zero results.

### The Critical Distinction

The existing test in `test_workflow_proof.py:227` states it explicitly:

> **"Execution result is evidence; does not automatically equal accepted outcome."**

This principle is implemented for **work** but completely absent for **capabilities**.

For capabilities today:
- Execution succeeded → `"success"` → `invocation_count += 1`
- Execution failed → `"failure"` → `correction_count += 1`
- Not executed (auth, missing deployment, etc.) → `"failure"` → `correction_count += 1`

All three paths are treated identically, which means:
1. `invocation_count` is inflated by non-executions
2. `correction_count` is inflated by non-quality failures
3. No quality signal exists for maturation

---

## 5. Architectural Seams

### Current Boundary: Operations → Enterprise

```
Operations (InvocationRecorderAdapter)
  → Enterprise (ConceptStore.record_invocation)
```

This seam is correctly established. Operations records operational events; Enterprise stores them.

### Missing Boundary: Operations → Outcome Assessment

```
Operations (ExecutionResult)
  → ??? (Outcome Assessment)
  → Enterprise (ConceptStore with assessed outcome)
```

There is **no** outcome assessment layer. `InvocationRecorderAdapter` determines outcome directly from raw `ExecutionResult` without any evaluation.

### Existing Pattern to Follow

The `organisation` plane already demonstrates outcome assessment:
- `assess_work_outcome()` evaluates execution results against acceptance criteria
- `record_work_learning()` creates durable knowledge only for accepted outcomes
- The pattern is: assess → decide → record

This same pattern is needed for capabilities, but it does not exist.

---

## 6. Why `promote()` Cannot Be Called Today

Even though invocation telemetry now exists, calling `CapabilityRegistry.promote()` after every successful invocation would be wrong because:

1. **No quality gate:** `promote()` unconditionally sets `ACTIVE`. It does not check invocation count, correction rate, or candidacy.
2. **Inflated counts:** `invocation_count` includes authorisation failures, missing deployments, and capability-not-found errors. These are not quality data points.
3. **No recency bias:** `last_invoked_at` is updated, but there's no way to distinguish "10 successes 2 years ago" from "10 successes this week."
4. **No outcome quality:** A capability can return `"success"` while producing empty or wrong outputs. There's no assessment of whether the capability actually solved the problem.
5. **`promotion_candidacy` is dead code:** It exists in `MaturationHistory` but is never computed or checked.

---

## 7. Candidate Next Increments

### Candidate A: Capability Outcome Assessment (Recommended)

**Objective:** Introduce an explicit outcome assessment step between execution and telemetry recording that distinguishes execution outcomes from capability outcomes.

**Architectural seam:** Operations produces `ExecutionResult` → Outcome Assessment evaluates → Enterprise stores assessed outcome.

**Why this is the smallest defensible increment:**

1. **It is genuinely missing.** Without outcome assessment, maturation has no quality input. `correction_count` is polluted by non-quality failures.
2. **It is thin.** It follows the existing `assess_work_outcome()` pattern. It does not require new persistence, new domain models, or new execution paths.
3. **It unblocks maturation.** Once outcomes are properly assessed, maturation thresholds become meaningful.
4. **It does not change execution behaviour.** It adds an evaluation step after recording, not during execution.
5. **It corrects existing data quality.** The current `invocation_count` and `correction_count` are wrong; outcome assessment fixes the input data.

**What it would implement:**
- A new `CapabilityOutcomeAssessor` (port + adapter) that evaluates `ExecutionResult`
- Three outcome categories: `executed` (success), `failed` (execution error), `not_executed` (auth, missing deployment, etc.)
- Optionally: `assessed_success` vs `assessed_failure` based on output quality heuristics
- `InvocationRecorderAdapter` would use assessed outcomes instead of raw error detection

**What it would NOT implement:**
- Threshold-based promotion
- `promotion_candidacy` logic
- Capability `promote()` changes
- Bus events for maturation
- Per-invocation history storage

---

### Candidate B: Threshold-Based Promotion

**Objective:** Make `CapabilityRegistry.promote()` check conditions before promoting.

**Why it should wait:**
- The input data (`invocation_count`, `correction_count`) is currently corrupted by non-quality events
- Implementing thresholds on bad data would produce wrong results
- Requires outcome assessment first (Candidate A)
- `promote()` is currently a stub, but making it conditional without quality data is premature

---

### Candidate C: Invocation History Query/Retrieval

**Objective:** Add methods to retrieve per-invocation history for a capability.

**Why it should wait:**
- The current aggregated view is sufficient for threshold-based promotion
- Per-invocation history is valuable for audit and analysis, but it is not blocking maturation
- Would require new persistence structures (list of invocation records)
- Better to implement after maturation is working with aggregated data

---

### Candidate D: Execution Path Convergence

**Objective:** Unify `PatternRuntime.invoke_step()` and `CapabilityExecutionAdapter.execute()` through `CapabilityExecutionPort`.

**Why it should wait:**
- Both paths work correctly today
- Convergence would complicate the recorder wiring
- Better to have outcome assessment in both paths first, then unify

---

## 8. Recommended Increment 19

### Capability Outcome Assessment

This is the smallest defensible next increment because:

1. **It fixes data quality.** The current `invocation_count` and `correction_count` are wrong. Authorisation failures, missing deployments, and capability-not-found errors are counted as `"failure"` when they should be `"not_executed"`. Outcome assessment corrects this.

2. **It creates the maturation precondition.** Maturation needs to know:
   - How many times was the capability *actually executed*? (not `invocation_count` today)
   - How many times did it *fail*? (not `correction_count` today — which includes non-failures)
   - How many times did it *succeed with good outcomes*?
   
   Without outcome assessment, these questions cannot be answered.

3. **It follows an existing pattern.** `assess_work_outcome()` in the `organisation` plane demonstrates the same concern: evaluating execution results against criteria before creating durable knowledge.

4. **It is thin.** It adds a translation layer between raw `ExecutionResult` and `ConceptStore.record_invocation()`. No new persistence, no new domain models, no changes to execution paths.

5. **It does not change existing behaviour.** It refines what gets recorded, not how execution works.

### What Increment 19 Must NOT Implement

- Capability maturation / promotion logic
- Threshold checks in `promote()`
- `promotion_candidacy` evaluation
- Bus events for maturation
- Per-invocation history storage
- Execution path convergence
- Deployment lifecycle
- AI-mediated execution implementation

---

## 9. Exact Scope for Increment 19

### MUST IMPLEMENT

1. **`CapabilityOutcomeAssessor` port** (`packages/contracts/src/capability_outcome_assessor.py`)
   - Single method: `assess(result: ExecutionResult) -> CapabilityOutcome`
   - Returns one of: `"executed"`, `"failed"`, `"not_executed"`

2. **`CapabilityOutcomeAssessorAdapter`** (`packages/workflow_runner/src/adapters/capability_outcome_assessor_adapter.py`)
   - Implements `CapabilityOutcomeAssessor`
   - Evaluates `ExecutionResult` to determine outcome category
   - Rules:
     - `"not_executed"` — no `error` key, but status is not `"completed"` or `"failed"` is present for auth/missing deployment/capability not found
     - Actually, simpler: `"not_executed"` when there was no actual execution attempt (status missing or auth error)
     - `"failed"` — execution attempted but returned error
     - `"executed"` — execution completed without error

3. **Wire into `InvocationRecorderAdapter`**
   - Use `CapabilityOutcomeAssessor` instead of raw `_determine_outcome()`
   - Record `"executed"` as `"success"`, `"failed"` as `"failure"`, `"not_executed"` as... what?
   - Actually, `ConceptStore.record_invocation()` only accepts `"success"` or `"failure"`. So we need to decide:
     - Option A: Only record `"executed"` and `"failed"`; skip `"not_executed"` entirely
     - Option B: Store `"not_executed"` as a separate field or skip recording for non-executions
   - **Option A is correct:** Non-executions should not affect `invocation_count` or `correction_count` at all. They are not capability quality data.

4. **Update `InvocationRecorder` contract**
   - Possibly add an `outcome_assessor` dependency
   - Or keep `InvocationRecorder` simple and have the adapter handle assessment internally

### TESTS REQUIRED

| Test | Purpose |
|------|---------|
| Unit test: assessor returns `"executed"` for clean success | Execution completed without errors |
| Unit test: assessor returns `"failed"` for execution error | Execution raised exception |
| Unit test: assessor returns `"not_executed"` for auth failure | Actor not permitted |
| Unit test: assessor returns `"not_executed"` for missing deployment | No deployment found |
| Unit test: assessor returns `"not_executed"` for capability not found | Invalid capability ID |
| Integration test: `PatternRuntime` + assessor records correct outcome | End-to-end through pattern path |
| Integration test: `CapabilityExecutionAdapter` + assessor records correct outcome | End-to-end through direct path |
| Integration test: non-execution does NOT increment `invocation_count` | Proves data quality improvement |

### WHAT MUST NOT CHANGE

- `ConceptStore.record_invocation()` signature
- `CapabilityRegistry.promote()` implementation
- Execution paths (`PatternRuntime`, `CapabilityExecutionAdapter`)
- `ExecutionResult` model
- Existing tests must pass

---

## 10. Evidence Summary

### Existing Code References

| Component | Location | Status |
|-----------|----------|--------|
| `CapabilityStatus` (DRAFT, ACTIVE, DEPRECATED) | `people_capability/src/capability.py:24-28` | Defined |
| `CapabilityRegistry.promote()` | `capability_registry/src/capabilities.py:84-94` | Stub — unconditional |
| `MaturationHistory` | `capability_registry/src/concepts.py:52-59` | Defined, partially used |
| `ConceptStore.record_invocation()` | `capability_registry/src/concepts.py:109-121` | Implemented |
| `InvocationRecorderAdapter._determine_outcome()` | `workflow_runner/src/adapters/invocation_recorder_adapter.py:36-41` | Too simplistic |
| `assess_work_outcome()` | `organisation/src/outcome.py:15-57` | Exists for work, not capabilities |
| `promotion_candidacy` | `capability_registry/src/concepts.py:59` | Dead code — never set/checked |
| `test_learning_loop_promotes_capability_after_threshold` | `workflow_runner/tests/test_phase5.py:33-47` | Misleading name — no threshold checked |

### ADR References

| ADR | Relevance |
|-----|-----------|
| ADR-029 | Defines learning loop; says outcome assessment is an operational concern |
| ADR-040 | Defines CapabilityAssignment and CapabilityProficiency (person-level, not capability-level) |
| ADR-042 | Execution metadata belongs to Operations, not Capability domain |
| ADR-043 | CapabilityRegistry must not depend on ConceptStore directly |

---

## 11. Validation Strategy

### Commands

```bash
# Ruff lint
ruff check packages/ --output-format=github

# Full test loop
for pkg in packages/*/; do
  if [ -d "$pkg/tests" ] && [ -f "$pkg/pyproject.toml" ]; then
    cd "$pkg"
    pytest tests/ -q --tb=short
    cd ../..
  fi
done

# Increment 19 specific tests
pytest packages/workflow_runner/tests/test_capability_outcome_assessor_adapter.py -v
pytest packages/workflow_runner/tests/test_increment19_integration.py -v
```

### Expected Results

- All existing tests pass (165+ workflow_runner, 45+ ai)
- Increment 19 tests pass
- Ruff clean on all new files

---

## 12. Architectural Invariants

Increment 19 must preserve:

1. **AI plane depends on ports only** — no new imports from domain implementations
2. **Operations records operational events** — does not decide maturation
3. **Enterprise stores durable knowledge** — does not decide what to store
4. **People/Capability owns maturation decisions** — does not implement them yet
5. **No circular dependencies** — new port in `contracts`, adapter in `workflow_runner`
6. **Fire-and-forget telemetry** — does not block execution on assessment failure
7. **Non-executions do not pollute maturation data** — `invocation_count` only increments for actual executions
8. **Both execution paths use the same assessor** — `PatternRuntime` and `CapabilityExecutionAdapter` both benefit
9. **No new cross-plane dependencies** — all new code in existing planes
10. **Existing tests pass** — no regressions

---

**INVESTIGATION STATUS: COMPLETE**

**RECOMMENDATION:** Increment 19 should implement **Capability Outcome Assessment** — an explicit evaluation step that distinguishes execution outcomes (`executed`, `failed`, `not_executed`) before they reach `ConceptStore.record_invocation()`. This is the smallest defensible increment that creates meaningful maturation input data without implementing maturation itself.
