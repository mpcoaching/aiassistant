# Increment 21D Investigation: Clarification Semantics and the Decision Boundary

**Status:** Read-only investigation. No code changes.  
**Prerequisites:** Increment 21C corrected — `CapabilityActionPolicy` is now conservative; any match returns `AskUserToSelect`; autonomous execution is deferred until the relevance score is calibrated.

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
    │           candidate_confidences={"cap-a": 0.75, "cap-b": 0.30},
    │           confidence=0.75,
    │           matcher_id="relevance",
    │           rationale="Matched 2 capabilities by keyword relevance")
    │
    └─► [_to_candidate(cap, match_result.candidate_confidences.get(cap.id, 0.0))
        for cap in match_result.candidates]
        └─► CapabilityCandidate[]  ← confidence now PRESERVED
    │
    ▼
CapabilityActionPolicy.decide(candidates)
    ├─► 0 candidates → NoCapabilityMatch
    ├─► 1+ candidates → AskUserToSelect(candidates=candidates)
    │
    ▼
AssistantChatService
    └─► status="awaiting_capability_selection"
        message="I found N capabilities that might help. Please select one to proceed..."
        capability_candidates=[{id, name, description, kind, execution_mode, tags, confidence}]
```

**Key change from 21C:** `CapabilityActionPolicy` no longer uses confidence thresholds for execution. Any match returns `AskUserToSelect`. The confidence field is preserved and flows through the contract, but does not yet authorize execution.

---

## B. What We Know

### Facts

- `RelevanceMatcher` produces deterministic keyword relevance scores (0.0–1.0) for each candidate.
- `MatchResult` now carries `candidate_confidences: dict[str, float]` mapping capability IDs to individual scores.
- `CapabilityCandidate` now carries `confidence: float = 0.0`.
- `CapabilityDiscoveryAdapter` preserves per-candidate confidence from `MatchResult` into `CapabilityCandidate`.
- `CapabilityActionPolicy` currently treats all matches identically: any non-empty candidate list returns `AskUserToSelect`.
- The relevance score is **not** calibrated probability. It represents weighted token overlap (name 50%, description 30%, tags 20%).
- Single generic keywords can produce perfect scores (e.g., "data" → 1.0 for `analyse_data`).
- Generic multi-word requests can produce multiple weak candidates (e.g., "create something" → 0.400, 2 candidates in current catalogue).
- The repository has invocation/outcome evidence infrastructure (`MaturationHistory`, `InvocationRecorderAdapter`, `CapabilityOutcomeAssessorAdapter`), but evidence volume is too sparse for reliable learning.

### Assumptions

- The user expects the system to eventually execute capabilities autonomously when confidence is justified.
- The user expects the system to ask for clarification when confidence is insufficient.
- The user expects the system to distinguish between "select from these options" and "confirm this one" when presenting matches.
- The architectural boundary between matching (People/Capability), decision (AI), and execution (Operations) should remain intact.

### Signals

- The simulation in 21C showed that with the current 4-capability catalogue:
  - All generic requests either produce no match or multiple candidates (not single weak candidates).
  - Single-candidate cases are mostly strong matches (0.5–1.0) or single-keyword perfect matches.
  - The "work with data" case (0.333, 1 candidate) is the clearest example of a weak single candidate.
- The `AskUserToSelect` response message is the same regardless of whether there is 1 candidate or 10 candidates.
- `AssistantChatService._capability_selection_response()` builds the message: "I found N capabilities that might help. Please select one to proceed..."
- For a single candidate, this message is confusing: there is nothing to select.

### Unknowns

- Whether the score distribution has natural breakpoints that could support calibrated thresholds.
- Whether request specificity can be reliably detected from the current scoring model.
- Whether invocation/outcome evidence will become reliable enough to inform decisions.
- Whether users expect confirmation prompts for single candidates or find them annoying.
- Whether the gap between top and next candidate carries meaningful signal for multi-candidate cases.

---

## C. Decision Problem

`CapabilityActionPolicy` must map candidate sets to actions. After 21C, the mapping is trivial:

```
[] → NoCapabilityMatch
[1+] → AskUserToSelect
```

This is honest but unhelpful. The policy ignores all the information it receives:
- `confidence` on each candidate
- `candidate_count`
- score separation between candidates
- `matcher_id` and `rationale`

The decision problem is:

**Given a set of candidates with relevance scores, what is the smallest honest step toward using that information?**

Not "build an intelligent decision system." Not "add arbitrary thresholds." But "use what we actually know to make the user experience better while keeping the architecture honest."

---

## D. Candidate Decision Models

### 1. Count-based (current)

| Candidates | Action |
|------------|--------|
| 0 | NoCapabilityMatch |
| 1+ | AskUserToSelect |

**Pros:** Simple, honest, no arbitrary thresholds.  
**Cons:** Ignores all relevance information. Single-candidate UX is poor ("select one" when there is only one).

### 2. Absolute relevance threshold

| Candidates | Condition | Action |
|------------|-----------|--------|
| 0 | — | NoCapabilityMatch |
| 1 | confidence >= X | ExecuteCapability |
| 1 | confidence < X | AskUserToSelect |
| 2+ | — | AskUserToSelect |

**Pros:** Uses the score.  
**Cons:** The score is not calibrated probability. Any threshold X is arbitrary. "data" → 1.0 would auto-execute on a vague single keyword.

### 3. Relative dominance (multi-candidate only)

| Top Gap | Action |
|---------|--------|
| gap >= Y | Execute dominant candidate |
| gap < Y | AskUserToSelect |

**Pros:** Uses relative information.  
**Cons:** Still requires arbitrary threshold Y. Does not address single-candidate UX.

### 4. Clarification semantics

Introduce explicit modes for "ask user" based on candidate structure:

| Candidates | Top Confidence | Mode |
|------------|---------------|------|
| 0 | — | NoCapabilityMatch |
| 1 | any | Confirm (present the candidate, ask for confirmation) |
| 2+ | any | Select (present candidates, ask for selection) |

**Pros:** 
- No arbitrary thresholds.
- Improves UX by distinguishing "confirm" from "select."
- Honest: does not use confidence to authorize execution.
- Small change: adds a `mode` or `reason` field to `AskUserToSelect`.

**Cons:**
- Does not yet use confidence for execution decisions.
- Adds a small amount of complexity to the action hierarchy.

### 5. Request specificity heuristic

Use token count or other signals to detect generic requests and suppress weak matches.

**Pros:** Could reduce false positives.  
**Cons:** Token count is a crude proxy. "create test artifact" (3 tokens) is specific; "do a creation" (3 tokens) is generic but has the same token count. The relevance score already captures how well tokens match; adding token count doesn't cleanly separate specificity from relevance.

### 6. Calibrated confidence

Build an evaluation corpus, measure score distribution, find natural thresholds.

**Pros:** Defensible thresholds.  
**Cons:** Significant work. May not find clear natural breakpoints. Defers the immediate UX improvement.

### 7. Evidence-informed matching

Use invocation/outcome history to bias matching.

**Pros:** Could improve matching quality over time.  
**Cons:** Evidence is too sparse. Would create a fake learning loop. Requires major infrastructure changes.

---

## E. Recommendation

**Recommend Increment 21D: Clarification Semantics.**

The smallest coherent next increment is to formalize the distinction between:

- **Confirm**: a single candidate matched; the user should confirm whether to proceed.
- **Select**: multiple candidates matched; the user should select one.

This addresses the immediate UX regression introduced by the conservative 21C policy (single-candidate cases now show "select one" when there is nothing to select) without:

- introducing arbitrary thresholds,
- using uncalibrated confidence for execution,
- creating new ports or services,
- collapsing the matching/decision/execution boundaries.

### Why this is the right next step

1. **It fixes a real UX problem.** After 21C, a user who says "create test artifact" gets: "I found 1 capability that might help. Please select one to proceed." This is confusing. The user wants confirmation, not selection.

2. **It is the smallest change that creates value.** Adding a `mode` field to `AskUserToSelect` is a one-field change that immediately improves the user experience.

3. **It preserves architectural honesty.** The policy still does not auto-execute. It only distinguishes how it asks the user. Confidence is still not used to authorize execution.

4. **It sets up future increments.** Once we have "confirm" vs "select" semantics, the next step can be:
   - "clarify" for weak/uncertain matches
   - confidence thresholds for "confirm" → "execute"
   - dominance assessment for "select" → "confirm dominant"

5. **It does not require arbitrary thresholds.** The distinction is based on candidate count, which is exact and unambiguous.

---

## F. Explicit Non-Goals

| Item | Why Deferred |
|------|--------|
| **Autonomous execution based on confidence** | Score is not calibrated. Will be deferred until a defensible basis exists. |
| **Absolute relevance thresholds** | No natural breakpoints in score distribution. Arbitrary thresholds would masquerade as calibrated confidence. |
| **Relative dominance thresholds** | Gap distribution is sparse and catalogue-dependent. Would require calibration. |
| **Request specificity heuristic** | Token count is a crude proxy. The relevance score already captures token match quality. |
| **Evidence-informed matching** | Evidence is too sparse. Would create a fake learning loop. |
| **Calibration corpus** | Useful long-term but not the smallest next step. |
| **Separate assessment layer** | Premature abstraction. Current boundary (matching → contract → action) is correct. |
| **New ports or services** | Not needed for clarification semantics. |
| **LLM matching / embeddings / Qdrant** | Out of scope. Too heavy for this stage. |
| **Conversational memory / agent abstraction** | Explicitly deferred across all increments. |

---

## G. Implementation Plan

### Files likely to change

| File | Change |
|------|--------|
| `packages/ai/src/capability_action.py` | Add `mode` parameter to `AskUserToSelect`. Policy sets `mode="confirm"` for 1 candidate, `mode="select"` for 2+ candidates. |
| `packages/ai/src/chat.py` | `_capability_selection_response()` uses `mode` to build different messages: "I found X. Shall I proceed?" vs "I found N capabilities. Please select one." |
| `packages/ai/tests/test_capability_action.py` | Add tests for `mode` on `AskUserToSelect`. |
| `packages/ai/tests/test_assistant.py` | Update/verify response messages for single-candidate and multi-candidate cases. |

### Expected behaviour

| Scenario | Action | Mode | Response Message |
|----------|--------|------|------------------|
| 0 candidates | `NoCapabilityMatch` | — | Fall through to pattern execution |
| 1 candidate | `AskUserToSelect` | `"confirm"` | "I found create_test_artifact. Shall I proceed?" |
| 2+ candidates | `AskUserToSelect` | `"select"` | "I found 2 capabilities that might help. Please select one to proceed." |

### Tests required

| Test | Purpose |
|------|---------|
| `test_single_candidate_sets_confirm_mode` | Verify 1 candidate → `mode="confirm"` |
| `test_multiple_candidates_set_select_mode` | Verify 2+ candidates → `mode="select"` |
| `test_no_candidates_returns_no_match` | Verify empty list → `NoCapabilityMatch` (unchanged) |
| `test_chat_single_candidate_asks_for_confirmation` | Verify chat response message for single candidate |
| `test_chat_multiple_candidates_asks_for_selection` | Verify chat response message for multiple candidates |
| `test_chat_no_candidates_falls_through` | Verify no-match behaviour (unchanged) |

---

## H. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **UX inconsistency** | Low | Low | `confirm` mode is a strict improvement over current "select one" for single candidates. |
| **Mode proliferation** | Medium | Low | Limit modes to `confirm` and `select` for now. Do not add `clarify` until there is a defensible basis. |
| **Threshold creep** | Medium | Medium | Explicitly document that modes are based on candidate count, not confidence. Do not add confidence-based modes until calibrated. |
| **Test coupling** | Low | Low | Update tests that assert specific message strings. Keep assertions focused on intent, not exact wording. |
| **False confidence in architecture** | Low | Medium | Document that `confirm` does NOT mean "execute." It means "ask user to confirm." Execution remains deferred. |

---

## Summary

Increment 21C correctly made the action policy conservative, but created a UX regression: single-candidate matches now show "select one to proceed" when there is nothing to select. Increment 21D should introduce **clarification semantics** — distinguishing `confirm` (single candidate) from `select` (multiple candidates) in the `AskUserToSelect` action. This is the smallest coherent step that improves the user experience while preserving the honest boundary that confidence does not yet authorize execution.

---

## Implementation Status

**Completed:** Increment 21D implemented.

### Files Changed

| File | Change |
|------|--------|
| `packages/ai/src/capability_action.py` | Added `interaction` parameter to `AskUserToSelect`. Policy sets `interaction="confirm"` for 1 candidate, `interaction="select"` for 2+ candidates. |
| `packages/ai/src/chat.py` | `_capability_selection_response()` accepts `interaction` parameter. Single candidate builds "I found X. Shall I proceed?" message. Multiple candidates build "I found N capabilities. Please select one..." message. Telemetry includes `interaction` field. |
| `packages/ai/tests/test_capability_action.py` | Added assertions for `interaction` field on `AskUserToSelect`. |
| `packages/ai/tests/test_assistant.py` | Added `test_chat_single_candidate_asks_for_confirmation`. Updated `test_chat_capability_selection_presents_multiple_candidates` and `test_chat_weak_single_candidate_asks_user_instead_of_executing` to verify `interaction` telemetry. |

### Test Results

| Suite | Result |
|-------|--------|
| `packages/ai/tests/` | 56 passed |
| `packages/workflow_runner/tests/` | 185 passed |
| `packages/capability_registry/tests/test_relevance_matcher.py` | 15 passed |

### Behaviour After 21D

| Scenario | Action | Interaction | Response |
|----------|--------|-------------|----------|
| 0 candidates | `NoCapabilityMatch` | — | Fall through to pattern execution |
| 1 candidate | `AskUserToSelect` | `"confirm"` | "I found create_test_artifact. Shall I proceed with this capability?" |
| 2+ candidates | `AskUserToSelect` | `"select"` | "I found N capabilities that might help. Please select one to proceed..." |

### What Remains Unchanged

- No confidence threshold introduced.
- No autonomous execution.
- Matching remains in People/Capability.
- Decision remains in AI.
- Execution remains in Operations.
- No new ports, services, or abstractions.
