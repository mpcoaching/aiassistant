# Increment 21F — Investigation: Capability Action Decision Model

**Status:** Read-only investigation. No code changes.  
**Prerequisites:** Increments 21A–21E implemented. `CapabilityActionPolicy` is conservative; any match returns `AskUserToSelect` with `interaction="confirm"` (1 candidate) or `"select"` (2+ candidates). Confidence is preserved but not used for execution. 21E (ranked presentation) is deferred.

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
        └─► CapabilityCandidate[]  ← confidence preserved
    │
    ▼
CapabilityActionPolicy.decide(candidates, context)
    ├─► 0 candidates → NoCapabilityMatch
    ├─► 1 candidate  → AskUserToSelect(interaction="confirm")
    └─► 2+ candidates → AskUserToSelect(interaction="select")
    │
    ▼
AssistantChatService
    └─► status="awaiting_capability_selection"
        message varies by interaction
        capability_candidates=[{id, name, description, kind, execution_mode, tags}]
        telemetry={..., interaction="confirm"|"select"}
        ↓
    explicit user confirmation / selection
        ↓
    CapabilityExecutionPort.execute()
        ↓
    Operations
```

---

## B. Current Decision Boundary

### What `CapabilityActionPolicy` knows today

`CapabilityActionPolicy.decide()` receives:

```python
def decide(
    self,
    candidates: list[CapabilityCandidate],  # list of candidate capabilities
    context: dict[str, Any] | None = None,  # raw request context
) -> CapabilityAction:
```

Each `CapabilityCandidate` contains:

| Field | Type | Currently used by policy? |
|-------|------|--------------------------|
| `id` | str | No |
| `name` | str | No |
| `description` | str | No |
| `kind` | str | No |
| `tags` | list[str] | No |
| `execution_mode` | str | No |
| `confidence` | float = 0.0 | **No** — preserved but not used |

The policy currently uses ONLY `len(candidates)`.

### What `CapabilityActionPolicy` does NOT know

- `MatchResult.confidence` (top score aggregate)
- `MatchResult.candidate_confidences` (per-candidate scores dict)
- `MatchResult.rationale`
- `MatchResult.matcher_id`
- Score gap between top and second candidate
- Request token count or specificity
- Any maturation/invocation/outcome evidence
- Any execution history

### What `context` contains

The `context` parameter is the raw `request.context` from `ChatRequest`. It is a `dict[str, Any]` that originates from `frame.context` (a `ContextRecord` from intent recognition). It contains structured enterprise context fields (problem_context, activity_purpose, decision_context, etc.) but the policy does not currently inspect it.

---

## C. Available Signals

### Available now

| Signal | Location | Currently used? |
|--------|----------|----------------|
| `candidate_count` | `len(candidates)` | Yes — determines confirm vs select |
| `candidate.confidence` | Per-candidate relevance score | **No** — preserved but unused |
| `candidate.name` | Capability name | No |
| `candidate.description` | Capability description | No |
| `candidate.tags` | Capability tags | No |
| `candidate.kind` | Capability type | No |
| `candidate.execution_mode` | How capability runs | No |
| `context` | Request context dict | No |
| Candidate ordering | Already sorted by relevance | Implicit — list is ordered |

### Potentially available later (small changes)

| Signal | What would be needed | Current barrier |
|--------|---------------------|-----------------|
| `top_score` | Pass `MatchResult.confidence` through adapter to policy | Already computed, just not passed |
| `score_gap` | Compute `top_score - second_score` in adapter or policy | Simple arithmetic on `candidate_confidences` |
| `candidate_count_below_threshold` | Already available | None |
| `request_specificity` | Token count or similar from request text | Not currently computed |

### Not currently available (requires new infrastructure)

| Signal | Why unavailable |
|--------|----------------|
| `invocation_count` | Stored in `MaturationHistory` in ConceptStore payload. Not wired to matcher or policy. |
| `correction_count` | Same — stored in `MaturationHistory`. Not accessible to policy. |
| `last_invoked_at` | Same — stored in `MaturationHistory`. |
| `outcome_history` | `InvocationRecorderAdapter` records to ConceptStore. Not fed back to matching. |
| `promotion_candidacy` | Defined in `MaturationHistory` but not actively used. |
| User correction feedback | No mechanism exists to capture "user selected different capability than top match" as structured feedback. |
| Calibrated thresholds | No evaluation corpus exists. |
| Execution success rate | `CapabilityOutcomeAssessorAdapter` exists but outcomes are not correlated with matching decisions. |

---

## D. Signal Semantics

### What each signal CAN legitimately mean

| Signal | Legitimate meaning | Cannot mean |
|--------|-------------------|-------------|
| `confidence` (relevance score) | Weighted keyword overlap (0.0–1.0). Higher = more request tokens matched in capability metadata. | Probability of correct selection. Intent confidence. Execution success likelihood. |
| `candidate_count` | Number of capabilities with non-zero relevance to the request. | Quality of match. Specificity of request. |
| `score_gap` | Difference in relevance between top two candidates. | Calibrated dominance measure. Statistical significance. |
| `ordering` | Candidates sorted by relevance descending. | Authoritative ranking. Guaranteed correctness. |
| `invocation_count` | How many times this capability has been executed. | Quality of match. Relevance to current request. |
| `correction_count` | How many times execution was corrected/failed. | Relevance to current request. |

### What each signal CANNOT legitimately mean (without calibration)

| Signal | Cannot mean | Why |
|--------|------------|-----|
| `confidence >= 0.5` | "50% chance this is correct" | Score is keyword overlap, not probability |
| `score_gap >= 0.3` | "Clearly dominant candidate" | Gap is catalogue-dependent and arbitrary |
| `invocation_count > 10` | "High quality capability" | Could be frequently invoked because it's the only option, not because it's correct |
| `correction_count == 0` | "Never fails" | Could be rarely invoked |

---

## E. Decision Problem

The policy must answer:

> "Given the capabilities that appear relevant to the request, what is the safest and most useful next action?"

The current answer is:

```
0 candidates → NoCapabilityMatch
1 candidate  → AskUserToSelect(interaction="confirm")
2+ candidates → AskUserToSelect(interaction="select")
```

This is honest and safe. But it ignores all the information the policy receives.

**The unresolved problem is:** Can the policy use the available signals (count, confidence, ordering, gap) to make better decisions **without pretending those signals are calibrated probabilities or authorisation signals**?

This is not about making the policy "more intelligent." It is about determining whether there is a **defensible** way to use the available information that:

1. Does not introduce arbitrary thresholds
2. Does not masquerade relevance as confidence
3. Does not auto-execute based on uncalibrated signals
4. Actually improves the user experience or system safety
5. Is justified by the current evidence

---

## F. Candidate Decision Models

### Model A — Count only (current)

```
0 → NoCapabilityMatch
1 → AskUserToSelect(interaction="confirm")
2+ → AskUserToSelect(interaction="select")
```

**Advantages:**
- Simple, deterministic, honest
- No thresholds needed
- No calibration required
- Already improved by 21D (confirm vs select)

**Disadvantages:**
- Ignores all relevance information
- Single weak candidate gets same treatment as single strong candidate
- Multi-candidate cases with clear dominance get same treatment as ambiguous cases

**Verdict:** Sufficient for current state. No compelling reason to change.

---

### Model B — Absolute relevance thresholds

```
0 → NoCapabilityMatch
1, confidence >= X → ExecuteCapability  (or special action)
1, confidence < X  → AskUserToSelect(interaction="confirm")
2+ → AskUserToSelect(interaction="select")
```

**Advantages:**
- Uses the relevance score
- Could theoretically distinguish strong from weak single candidates

**Disadvantages:**
- Score is NOT calibrated probability
- Any threshold X is arbitrary
- "data" → 1.0 would auto-execute on a vague single keyword
- "create something" → 0.167 would require user interaction
- The gap between these is request-dependent, not capability-dependent
- **This was explicitly rejected in 21C**

**Verdict:** Not defensible. Rejected.

---

### Model C — Relative dominance

```
0 → NoCapabilityMatch
1 → AskUserToSelect(interaction="confirm")
2+, gap >= Y → some different action (e.g., pre-select top candidate)
2+, gap < Y → AskUserToSelect(interaction="select")
```

**Advantages:**
- Uses relative information, which is more meaningful than absolute scores
- Gap reflects catalogue competition, not just request specificity

**Disadvantages:**
- Still requires arbitrary threshold Y
- Gap distribution is catalogue-dependent and sparse
- Current catalogue: gaps are 0.567, 0.400, 0.300, 0.150, 0.100 — no natural breakpoint
- Would change the user interaction model (from "select" to "confirm-or-override")
- Requires evidence that users want/need this

**Verdict:** Premature. No natural threshold exists in current data. Would require calibration or user research.

---

### Model D — Specificity + relevance

```
if request is generic AND match is weak → NoCapabilityMatch or Clarify
if request is specific AND match is strong → confirm/execute
```

**Advantages:**
- Could reduce false positives from generic requests

**Disadvantages:**
- Token count is a crude proxy for specificity
- "create test artifact" (3 tokens) is specific; "do a creation" (3 tokens) is generic
- The relevance score already captures how well tokens match
- Adding token count doesn't cleanly separate specificity from relevance
- Would require heuristics that are themselves arbitrary

**Verdict:** Not justified. The relevance score already encodes the useful information.

---

### Model E — Calibrated relevance

Build an evaluation corpus, measure score distributions, find natural thresholds.

**Advantages:**
- Could produce defensible thresholds
- Would make absolute and relative relevance meaningful

**Disadvantages:**
- Requires significant work: labelled corpus, evaluation runs, statistical analysis
- May not find clear natural breakpoints
- Defers immediate improvements
- The corpus itself would need ongoing maintenance as capabilities change

**Verdict:** Worthwhile long-term, but not the smallest next step.

---

### Model F — Evidence-informed relevance

Combine current matching with invocation/outcome history.

**Advantages:**
- Could improve matching quality over time
- Would eventually allow execution success prediction

**Disadvantages:**
- Evidence is too sparse for reliable learning
- Would create a fake learning loop if implemented now
- Requires correlation between matching decisions and outcomes
- `MaturationHistory` is not currently accessible to the matcher or policy
- Would require significant infrastructure changes

**Verdict:** Deferred until evidence is mature enough.

---

### Model G — Hybrid

Combine several of the above.

**Advantages:**
- Could theoretically produce nuanced decisions

**Disadvantages:**
- Most components are not yet available or justified
- Combining uncalibrated signals does not make them calibrated
- Would create complex, hard-to-reason-about policy logic
- Violates the principle of explicitness

**Verdict:** Not justified at this stage.

---

## G. Evidence and Calibration

### Evidence readiness

| Evidence type | Location | Volume | Quality | Accessible to policy? |
|---------------|----------|--------|---------|----------------------|
| `invocation_count` | `MaturationHistory` in ConceptStore payload | Very low (mostly test fixtures) | Unreliable | No |
| `correction_count` | `MaturationHistory` in ConceptStore payload | Very low | Unreliable | No |
| `last_invoked_at` | `MaturationHistory` in ConceptStore payload | Very low | Unreliable | No |
| `promotion_candidacy` | `MaturationHistory` in ConceptStore payload | None observed | N/A | No |
| Execution outcomes | `CapabilityOutcomeAssessorAdapter` | Low | Unreliable | No |
| User selection feedback | Not collected | None | N/A | No |

**Assessment:** Evidence is NOT mature enough to use. The infrastructure exists (Increments 18/19) but the actual data volume is too low for reliable learning. Using it now would create a fake learning loop.

### Calibration readiness

| Calibration component | Status |
|----------------------|--------|
| Evaluation corpus | Does not exist |
| Labelled (request, correct_capability) pairs | Do not exist |
| Top-1 accuracy measurement | Not possible |
| Top-k recall measurement | Not possible |
| False-positive rate measurement | Not possible |
| Score distribution analysis | Possible but sparse (only test fixtures) |

**Assessment:** Calibration is NOT currently possible. Building an evaluation corpus would be the first step, but it is a data/measurement activity, not an architectural change.

---

## H. Autonomous Execution Question

### Should matching ever independently authorise execution?

**No — not based on matching alone.**

The architecture explicitly separates:

- **Matching** (People/Capability): "Which capabilities are relevant?"
- **Decision** (AI plane): "What should the system do?"
- **Authorisation** (Operations/People/Capability): "Can this capability be executed?"
- **Execution** (Operations): "Run the capability."

Matching provides relevance. It does NOT provide:
- Execution authority
- Safety assessment
- Outcome prediction
- User intent confirmation

### What would execution authorisation require?

| Requirement | Current state | Needed for autonomous execution |
|-------------|--------------|-------------------------------|
| Calibrated relevance | Not available | Evaluation corpus + calibration |
| Outcome history | Sparse/unreliable | Significant real invocation data |
| User intent confirmation | Explicit (user confirms) | Could be implicit if confidence is calibrated |
| Safety/authorisation | Handled by `ExecutionAuthorisationPort` | Independent of matching |
| Correction/feedback loop | Not implemented | ADR-029 infrastructure exists but unused |

**Conclusion:** Autonomous execution based on matching alone should remain deferred indefinitely. Execution authority should eventually depend on a combination of:
- Calibrated relevance
- Outcome history
- Explicit user confirmation or policy-based authorisation
- Safety/authorisation checks (already exist in `ExecutionAuthorisationPort`)

None of these are currently satisfied by matching alone.

---

## I. Recommendation

### Do not implement any new decision model for 21F.

The current `CapabilityActionPolicy` is correct for the current state of the system:

1. **The policy is honest.** It does not pretend that candidate count is a proxy for confidence.
2. **The policy is safe.** It never auto-executes. All matches require explicit user interaction.
3. **The policy is simple.** It has one input (candidate count) and three outputs (no match, confirm, select). This is easy to reason about and test.
4. **The available signals are not yet actionable.** Confidence is uncalibrated. Evidence is sparse. No thresholds are defensible.
5. **The "dominant/ambiguous/weak" hypothesis is premature.** The current catalogue does not produce enough ambiguous cases to justify complex decision logic. Any threshold would be arbitrary.
6. **The user experience is already adequate.** Single candidates get confirmation. Multiple candidates get selection. This is correct behaviour.

### What should happen instead

The next valuable step is NOT a policy change. It is one of:

1. **Build an evaluation corpus** for the `RelevanceMatcher`. This would:
   - Provide labelled (request, correct_capability) pairs
   - Allow measurement of top-1 accuracy, top-k recall, false-positive rate
   - Provide the data needed for future calibration
   - Not change any production behaviour

2. **Gather real usage data.** Let the system run with the current policy and collect:
   - Which candidates users select when given multiple options
   - Whether users confirm or reject single candidates
   - Whether the top-ranked candidate is consistently selected
   - This data can eventually inform decision models

3. **Improve the `RelevanceMatcher` scoring function.** The current keyword overlap model is simple. Improvements could include:
   - Better tokenisation (stemming, stop words, phrase matching)
   - Weight tuning based on observed user behaviour
   - Interface/parameter matching (not just name/description/tags)
   - These are matching improvements, not decision policy changes

4. **Wire maturation evidence to the matcher** (long-term). When invocation data is sufficiently mature:
   - Use `invocation_count` and `correction_count` as bias factors in scoring
   - This would be a matching improvement, not a decision policy change

### If a policy change becomes justified later

The eventual policy should distinguish:

| Situation | Action | Basis |
|-----------|--------|-------|
| No candidates | `NoCapabilityMatch` | Count |
| One strong candidate | `AskUserToSelect(interaction="confirm")` | Count + calibrated confidence |
| One weak candidate | `AskUserToSelect(interaction="confirm")` or `Clarify` | Count + calibrated confidence |
| Dominant + weak alternatives | `AskUserToSelect(interaction="confirm")` or `Suggest` | Gap + calibrated threshold |
| Ambiguous candidates | `AskUserToSelect(interaction="select")` | Gap below threshold |
| All weak candidates | `Clarify` or `NoCapabilityMatch` | Absolute score below threshold |

But this requires:
- Calibrated confidence thresholds
- Evidence-informed scoring
- User research on acceptable interaction patterns
- Possibly new action types (`Clarify`, `Suggest`)

None of these are currently available or justified.

---

## J. Explicit Deferrals

| Item | Why Deferred |
|------|--------|
| **Absolute relevance thresholds** | Score is not calibrated. Any threshold is arbitrary. |
| **Relative dominance thresholds** | Gap distribution is sparse and catalogue-dependent. No natural breakpoint. |
| **Autonomous execution based on confidence** | Matching does not provide authorisation. Would violate architectural separation. |
| **Evidence-informed matching/action** | Evidence is too sparse. Would create fake learning loop. |
| **Calibration corpus** | Does not exist. Building one is a data activity, not an architectural change. |
| **"Dominant candidate" action type** | Premature without calibrated gap thresholds and user research. |
| **"Weak candidate" / "Clarify" action type** | Cannot reliably distinguish weak from specific single-keyword matches. |
| **Request specificity heuristic** | Token count is crude. Relevance score already captures token match quality. |
| **Separate assessment/ranking layer** | Ranking belongs in matching. Separation is premature abstraction. |
| **Maturation history in matching** | Evidence volume too low. Would create fake learning loop. |
| **New ports or services** | Not needed. Current policy is sufficient. |
| **LLM matching / embeddings / Qdrant** | Out of scope. |
| **Agent abstraction / orchestrator** | Architecture explicitly rejects (ADR-031, ADR-036, ADR-044). |

---

## K. Proposed Next Increment

**No implementation increment is justified at this time.**

The current architecture is in a good state:

- Matching produces relevance scores (21B)
- Confidence is preserved through contracts (21C)
- Action policy is conservative and honest (21C correction)
- Clarification semantics distinguish confirm from select (21D)
- Candidate presentation is sufficient (21E deferred)

The next valuable work is NOT an architectural increment. It is:

1. **Operational: gather usage data.** Run the system with real users and observe:
   - How often users confirm single candidates
   - How often users reject and re-query
   - Whether the top-ranked candidate is consistently selected in multi-candidate cases
   - Whether users express confusion or frustration

2. **Measurement: build an evaluation corpus.** Create a labelled dataset of:
   - Representative user requests
   - Correct capability for each request
   - This enables future calibration without changing architecture

3. **Matching improvement (optional):** Enhance `RelevanceMatcher` scoring:
   - Better tokenisation
   - Stop word filtering
   - Phrase matching
   - These are matching improvements, not decision policy changes

If, after gathering data, the evidence shows that:
- Users consistently want the top candidate to be pre-selected when the gap is large
- Users are confused by "confirm" prompts for obvious matches
- The current "select" interaction is burdensome for dominant cases

THEN a future increment can introduce dominance assessment with defensible thresholds derived from actual usage data.

Until then, the current policy is the correct one: **simple, honest, safe, and explicit about what it does not know.**

---

## Summary

The investigation finds that the current `CapabilityActionPolicy` is architecturally correct for the current state of the system. The available signals (candidate count, relevance scores, ordering) are not yet actionable in a defensible way. The relevance score is uncalibrated. Evidence is too sparse. There are no natural thresholds in the score gap distribution. The "dominant/ambiguous/weak" hypothesis is interesting but premature — it requires calibration data that does not yet exist.

**No implementation is recommended for 21F.** The next step is operational: gather real usage data and build an evaluation corpus. These are data/measurement activities, not architectural changes. When enough evidence exists, the decision model can be revisited with defensible thresholds derived from actual usage rather than arbitrary numbers.
