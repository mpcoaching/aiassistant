# Increment 21C — Investigation: Confidence Preservation and the Matching → Action Safety Boundary

**Status:** Read-only investigation. No code changes.  
**Prerequisites:** Increment 21A (CapabilityActionPolicy) and 21B (RelevanceMatcher) implemented.

---

## A. Current Pipeline

```
User request
    │
    ▼
Intent / ProblemFrame
    │
    ▼
CapabilityDiscoveryPort.find_capabilities(request_text, context)
    │
    ▼
CapabilityDiscoveryAdapter
    ├─► registry.list() → Capability[]
    ├─► matcher.match(request_text, context, capabilities)
    │   └─► RelevanceMatcher
    │       └─► MatchResult(
    │           candidates=[capA, capB, ...],
    │           confidence=0.75,
    │           matcher_id="relevance",
    │           rationale="Matched 2 capabilities by keyword relevance")
    │
    └─► [_to_candidate(cap) for cap in match_result.candidates]
        └─► CapabilityCandidate[]   ← confidence DROPPED HERE
    │
    ▼
CapabilityActionPolicy.decide(candidates)
    ├─► 0 → NoCapabilityMatch
    ├─► 1 → ExecuteCapability
    └─► 2+ → AskUserToSelect
```

---

## B. Confidence Loss

`MatchResult.confidence` is created in `RelevanceMatcher.match()` at:
- `packages/capability_registry/src/relevance_matcher.py:69` — `confidence = scored[0][0] if scored else 0.0`

It is discarded in `CapabilityDiscoveryAdapter._to_candidate()` at:
- `packages/capability_registry/src/adapters/capability_discovery_adapter.py:33-41` — `_to_candidate()` builds `CapabilityCandidate` without any confidence field.

The adapter's `find_capabilities()` at line 30-31 calls `matcher.match()` and receives `MatchResult`, then immediately discards `MatchResult.confidence` and `MatchResult.rationale` when converting to the flat `CapabilityCandidate[]` list.

The AI plane (`CapabilityActionPolicy` and `AssistantChatService`) never sees confidence or rationale.

---

## C. Candidate Contract

**CapabilityCandidate** (`packages/contracts/capability_discovery.py:5-11`):

```python
class CapabilityCandidate(BaseModel):
    id: str
    name: str
    description: str
    kind: str
    tags: list[str] = []
    execution_mode: str = "ai_mediated"
```

**Producers:**
- `CapabilityDiscoveryAdapter._to_candidate()` — converts `Capability` → `CapabilityCandidate`

**Consumers:**
- `AssistantChatService._execute_capability_response()` — uses `id`, `name`, `description`, `kind`, `execution_mode`, `tags`
- `AssistantChatService._capability_selection_response()` — uses `id`, `name`, `description`, `kind`, `execution_mode`, `tags`
- `InMemoryCapabilityDiscoveryPort` (test fixture) — returns `CapabilityCandidate` directly

**Assessment:**
- It is a shared contract in `packages/contracts/`, used across planes.
- Adding `confidence: float = 0.0` would be backwards-compatible (new field with default).
- `execution_mode` is NOT a suitable carrier for confidence — it has a specific operational meaning.
- `tags` is NOT a suitable carrier — it's a list of strings.
- There is no existing field that legitimately carries matching metadata.
- **If confidence is to be preserved, `CapabilityCandidate` is the correct place for it.**

---

## D. Safety Risk

### Concrete Weak Match Example

Using the actual `RelevanceMatcher` algorithm against a realistic three-capability catalogue:

| Capability | Name | Description | Tags |
|------------|------|-------------|------|
| `create_test_artifact` | `create_test_artifact` | `Creates a test artifact record` | `test`, `artifact` |
| `send_email` | `send_email` | `Sends an email notification` | `email`, `notification` |
| `analyse_data` | `analyse_data` | `Analyse data` | `data`, `analysis` |

**Request: "create something"**

| Capability | name_score | desc_score | tag_score | combined |
|------------|-----------|-----------|----------|---------|
| `create_test_artifact` | 0.333 (1/3) | 0.0 | 0.0 | **0.167** |
| `send_email` | 0.0 | 0.0 | 0.0 | 0.0 |
| `analyse_data` | 0.0 | 0.0 | 0.0 | 0.0 |

**Result:** `create_test_artifact` is the **only** candidate with `confidence=0.167`.

**Consequence:** `CapabilityActionPolicy` sees 1 candidate → `ExecuteCapability` → system executes `create_test_artifact` with a weak keyword match.

### More Examples

| Request | Top Candidate | Score | Relevant Count | Action |
|---------|--------------|-------|---------------|--------|
| `"create something"` | `create_test_artifact` | 0.167 | 1 | **Execute** (weak match) |
| `"create anything"` | `create_test_artifact` | 0.167 | 1 | **Execute** (weak match) |
| `"do a creation"` | `create_test_artifact` | 0.100 | 1 | **Execute** (very weak match) |
| `"handle data"` | `analyse_data` | 0.500 | 1 | **Execute** (medium match) |
| `"work with data"` | `analyse_data` | 0.333 | 1 | **Execute** (weak-medium match) |
| `"send notification"` | `send_email` | 0.500 | 1 | **Execute** (medium match) |
| `"process data"` | `analyse_data` | 0.500 | 1 | **Execute** (medium match) |
| `"make something"` | (none) | 0.0 | 0 | Fall through |

### Analysis

The safety problem is real but bounded:

1. **Generic single-word requests** like "create something" produce a weak single candidate that auto-executes.
2. **Generic multi-word requests** like "make something" produce zero candidates and fall through (safe).
3. **Partially matching requests** like "handle data" produce a single medium-strength candidate that auto-executes.

The risk is **not** that the matcher is wrong — it is deterministic and predictable. The risk is that **the action policy has no way to distinguish a strong single candidate from a weak single candidate**. A count of 1 is treated identically regardless of relevance score.

### Is This a Real Safety Problem?

**Yes, but it is bounded:**

- The capability is executed, not arbitrarily chosen. It is at least *somewhat* related to the request.
- The user can see the result and correct.
- The worst case is executing a tangentially-related capability, not executing something completely unrelated.
- The matcher excludes DEPRECATED capabilities.
- The scoring is deterministic and explainable.

**However**, the architecture should not auto-execute on weak matches without at least presenting the match to the user. The current `CapabilityActionPolicy` makes no distinction between:
- "Create a test artifact" → 1 candidate, score 1.0 → Execute (correct)
- "Create something" → 1 candidate, score 0.167 → Execute (questionable)

---

## E. Meaning of the Score

The current `RelevanceMatcher` confidence is:

```
combined = name_score * 0.5 + description_score * 0.3 + tag_score * 0.2
```

This is a **keyword relevance score**, not a probability. Specifically:

| Term | What it represents | What it does NOT represent |
|------|--------------------|---------------------------|
| **Relevance score** | Fraction of request tokens found in capability metadata | Probability of correct selection |
| **Match score** | Weighted keyword overlap | User intent confidence |
| **Matching confidence** | Strength of keyword correspondence | Execution safety |
| **0.8** | 80% of request tokens matched across name/description/tags | 80% chance this is the right capability |

**The score is NOT suitable for threshold-based action decisions** without calibration because:

1. **It is request-dependent:** A very specific request ("create test artifact") produces a high score (0.75-1.0). A vague request ("create something") produces a low score (0.167). The score reflects request specificity as much as capability relevance.

2. **It is catalogue-dependent:** With more capabilities, the same request may produce different top scores due to competition.

3. **It has no ground truth:** There is no "correct answer" to calibrate against. The score is a heuristic, not a measured accuracy.

4. **The distribution is sparse:** From the simulation above, scores cluster at 0.0, 0.167, 0.25, 0.333, 0.5, 0.75, 0.9. There is no smooth distribution where thresholds like 0.5 or 0.8 have natural meaning.

---

## F. Multiple Candidate Analysis

### Current Behaviour

All multi-candidate cases go to `AskUserToSelect`:

```
candidate A = 0.91, candidate B = 0.42  → AskUserToSelect
candidate A = 0.61, candidate B = 0.59  → AskUserToSelect
```

### Should the Architecture Distinguish These?

**Yes, eventually — but NOT in this increment.**

The architecture should eventually distinguish:

| Scenario | Current Behaviour | Desired Behaviour |
|----------|------------------|-------------------|
| One strong candidate (0.9) | Execute | Execute |
| One weak candidate (0.2) | Execute | **Ask user or clarify** |
| Dominant + weak (0.9 vs 0.3) | Ask user | **Execute dominant** |
| Ambiguous (0.6 vs 0.55) | Ask user | Ask user (correct) |
| All weak (< 0.3) | Ask user | **Clarify or fall through** |

**Where should this distinction live?**

It belongs in **`CapabilityActionPolicy`**, not in `RelevanceMatcher`. The matcher's job is to produce candidates with relevance scores. The action policy's job is to decide what to do with those candidates. Merging them would make the matcher responsible for execution policy, which violates the architectural boundary established in 21A.

**But the action policy cannot make this distinction until it receives confidence data.** Currently it receives only `CapabilityCandidate[]` with no confidence.

---

## G. Responsibility Boundary

| Responsibility | Owner | Evidence |
|----------------|-------|----------|
| **Matching** (keyword relevance) | People/Capability (`RelevanceMatcher`) | `relevance_matcher.py` — deterministic keyword scoring |
| **Ranking** (ordering by score) | People/Capability (`RelevanceMatcher`) | Sorting happens inside `match()` — correct, because the matcher knows the scores |
| **Confidence production** | People/Capability (`RelevanceMatcher`) | `MatchResult.confidence` — already produced |
| **Confidence preservation** | Adapter (`CapabilityDiscoveryAdapter`) | Currently drops confidence — **this is the gap** |
| **Action selection** | AI plane (`CapabilityActionPolicy`) | `capability_action.py` — count-based decisions |
| **Execution** | Operations (`CapabilityExecutionPort`) | `capability_execution.py` + adapter chain |

**Assessment:** The boundary between matching and action is correct. The gap is that confidence does not cross the boundary. The adapter is the seam where confidence is lost.

---

## H. Evidence Readiness

### What Evidence Exists

| Evidence | Location | Status |
|----------|----------|--------|
| `MaturationHistory` | `ConceptStore` payload on `EnterpriseConcept` | Defined, partially populated |
| `invocation_count` | `MaturationHistory` in ConceptStore | Collected by `InvocationRecorderAdapter` |
| `correction_count` | `MaturationHistory` in ConceptStore | Collected by `InvocationRecorderAdapter` |
| `last_invoked_at` | `MaturationHistory` in ConceptStore | Collected by `InvocationRecorderAdapter` |
| `promotion_candidacy` | `MaturationHistory` in ConceptStore | Defined but not actively used |
| Outcome assessment | `CapabilityOutcomeAssessorAdapter` | Implemented, assesses success/failure |

### How Much Evidence Exists

**Very little.** The evidence system was implemented in Increments 18/19 but the actual capability execution volume in the current repository is minimal. Most capabilities are test fixtures. The maturation history for real capabilities is sparse or empty.

### Is Evidence Reliable Enough?

**No, not yet.** Using invocation counts or correction counts for matching decisions would create a **fake learning loop** — the system would appear to learn from evidence, but the evidence is too sparse to be meaningful. A capability with 1 invocation and 0 corrections would rank equally with a capability that has never been invoked.

### Should Evidence Influence Matching or Action Safety?

**Neither — yet.** Evidence should remain deferred until:
1. Real capabilities have meaningful invocation histories
2. The learning loop (ADR-029) is formally implemented
3. Evidence quality is validated

---

## I. Recommended Increment 21C

### Objective

Preserve matching confidence through the discovery adapter so that `CapabilityActionPolicy` can make confidence-aware action decisions.

### Exact Architectural Boundary

The boundary between People/Capability and AI plane is the `CapabilityDiscoveryPort`. The adapter (`CapabilityDiscoveryAdapter`) sits on the People/Capability side of this boundary. The action policy (`CapabilityActionPolicy`) sits on the AI side.

The change is:
1. **`CapabilityCandidate`** gains a `confidence: float = 0.0` field (contract change, backwards-compatible).
2. **`CapabilityDiscoveryAdapter._to_candidate()`** preserves `match_result.confidence` in the candidate.
3. **`CapabilityActionPolicy.decide()`** uses confidence to distinguish strong single candidates from weak single candidates.

### Exact Behaviour Change

| Scenario | Current (21B) | After 21C |
|----------|--------------|-----------|
| 0 candidates | `NoCapabilityMatch` | Unchanged |
| 1 candidate, confidence ≥ threshold | `ExecuteCapability` | **Same** (execute) |
| 1 candidate, confidence < threshold | `ExecuteCapability` | **`AskUserToSelect`** (present the candidate, ask user) |
| 2+ candidates | `AskUserToSelect` | Unchanged |

### Threshold

The threshold should be **configurable** and **conservative**. A value of `0.5` is suggested as the initial default, but this is a configuration detail, not an architectural decision. The threshold represents: "below this score, the match is too weak to auto-execute."

### Why This Is the Smallest Coherent Increment

1. **One contract change:** Add `confidence: float = 0.0` to `CapabilityCandidate`. Backwards-compatible.
2. **One adapter change:** Preserve `match_result.confidence` in `_to_candidate()`.
3. **One policy change:** `CapabilityActionPolicy` uses confidence for single-candidate decisions.
4. **No new abstractions:** No new ports, no new services, no new stages.
5. **Directly addresses the safety problem:** Weak single candidates no longer auto-execute.
6. **Preserves architectural boundaries:** Matching stays in People/Capability, action policy stays in AI, execution stays in Operations.

### Files Likely to Change

| File | Change |
|------|--------|
| `packages/contracts/capability_discovery.py` | Add `confidence: float = 0.0` to `CapabilityCandidate` |
| `packages/capability_registry/src/adapters/capability_discovery_adapter.py` | Pass `confidence` to `CapabilityCandidate` |
| `packages/ai/src/capability_action.py` | Use confidence in `decide()` for single-candidate logic |
| `packages/ai/tests/test_capability_action.py` | Add tests for confidence-aware decisions |
| `packages/capability_registry/tests/test_relevance_matcher.py` | Add test verifying confidence flows through adapter |

### Tests Required

| Test | Purpose |
|------|---------|
| `test_capability_candidate_has_confidence_field` | Verify contract change |
| `test_adapter_preserves_confidence` | Verify adapter passes confidence through |
| `test_action_policy_asks_user_for_weak_single_candidate` | confidence < threshold → AskUserToSelect |
| `test_action_policy_executes_strong_single_candidate` | confidence >= threshold → ExecuteCapability |
| `test_action_policy_multiple_candidates_unchanged` | 2+ candidates → AskUserToSelect regardless of confidence |
| `test_relevance_matcher_confidence_flows_to_policy` | End-to-end: matcher → adapter → policy |

---

## J. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Threshold calibration** | Medium | Medium | Make threshold configurable; start conservative (0.5) |
| **Confidence inflation** | Medium | Medium | RelevanceMatcher score is bounded by 1.0 and represents keyword overlap, not probability |
| **Contract churn** | Low | Low | Adding a field with default is backwards-compatible |
| **Test coupling to count-based policy** | Medium | Low | Update tests that assume single candidate always executes |
| **False negatives** (strong match treated as weak) | Low | Medium | Conservative threshold minimizes this; user can always select |

---

## K. Explicitly Deferred Work

| Item | Why Deferred |
|------|--------|
| **LLM matching** | Requires LLM integration, costs, latency. Future enhancement. |
| **Semantic/embedding matching** | Requires embedding model + Qdrant for capabilities. Too heavy. |
| **Evidence-informed matching** | Evidence is too sparse. Would create fake learning loop. |
| **Evidence-informed action policy** | Same — evidence not mature enough. |
| **Capability gap detection** | Useful but doesn't help when capabilities exist but aren't matched. |
| **Skill registration as capabilities** | Increases catalog size but doesn't improve matching or safety. |
| **Conversational memory** | Explicitly deferred across all increments. |
| **Agent abstraction** | Architecture explicitly rejects universal orchestrator. |
| **Paperclip integration** | ADR-005 explicitly rejected. |
| **Separate assessment/ranking stage** | Ranking belongs in matching. Separation is premature abstraction. |
| **Confidence thresholds for multi-candidate cases** | Multi-candidate always asks user. Thresholds for dominant vs ambiguous candidates come later. |

---

## Summary

The investigation confirms a real but bounded safety gap: `RelevanceMatcher` produces meaningful relevance scores, but `CapabilityDiscoveryAdapter` discards them, leaving `CapabilityActionPolicy` unable to distinguish strong matches from weak ones. The smallest correct next step is to preserve confidence through the adapter into `CapabilityCandidate`, and make `CapabilityActionPolicy` confidence-aware for single-candidate decisions. This requires one contract change, one adapter change, and one policy change — no new abstractions, no new ports, no infrastructure changes.

---

## Implementation Status

**Completed:** Increment 21C implemented.

### Files Changed

| File | Action |
|------|--------|
| `packages/contracts/capability_discovery.py` | Added `confidence: float = 0.0` to `CapabilityCandidate` |
| `packages/capability_matcher.py` | Added `candidate_confidences: dict[str, float] = {}` to `MatchResult` |
| `packages/capability_registry/src/relevance_matcher.py` | Populates `candidate_confidences` from internal scored list |
| `packages/capability_registry/src/adapters/capability_discovery_adapter.py` | `_to_candidate()` accepts confidence; `find_capabilities()` maps per-candidate scores |
| `packages/ai/src/capability_action.py` | `CapabilityActionPolicy` now confidence-aware with configurable threshold (default 0.5) |
| `packages/ai/tests/test_capability_action.py` | Updated existing tests; added 5 new tests for confidence-aware behaviour |
| `packages/ai/tests/test_assistant.py` | Updated `_make_capability_candidates()` with confidence=1.0; added weak-candidate integration test |
| `packages/capability_registry/tests/test_relevance_matcher.py` | Added 3 tests for `candidate_confidences` preservation |

### Test Results

| Suite | Result |
|-------|--------|
| `packages/capability_registry/tests/` | 76 passed, 2 failed (pre-existing `test_knowledge_bus.py` failures unrelated to this change) |
| `packages/ai/tests/` | 58 passed |
| `packages/workflow_runner/tests/` | 185 passed |

### Confidence Now Preserved

```
RelevanceMatcher.match()
    → MatchResult(
        candidates=[capA, capB],
        candidate_confidences={"cap-a": 0.75, "cap-b": 0.30}
    )
    ↓
CapabilityDiscoveryAdapter
    → CapabilityCandidate(confidence=0.75)
    → CapabilityCandidate(confidence=0.30)
    ↓
CapabilityActionPolicy.decide(candidates)
    → single candidate, confidence >= 0.5 → ExecuteCapability
    → single candidate, confidence < 0.5 → AskUserToSelect
    → multiple candidates → AskUserToSelect
```

### Behaviour Confirmed

- Weak single candidate (confidence < 0.5) no longer auto-executes. It is presented to the user via `AskUserToSelect`.
- Strong single candidate (confidence >= 0.5) executes as before.
- Multiple candidates remain `AskUserToSelect` regardless of confidence.
- Legacy `CapabilityCandidate` construction without confidence defaults to 0.0 and is treated conservatively.