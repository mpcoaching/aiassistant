# Increment 21I — Investigation: Capability Candidate Presentation / Decision Boundary

**Status:** Read-only investigation. No code changes.  
**Prerequisites:** Increments 21A–21H implemented. 21G evaluation corpus established. 21H implemented stop-word filtering and token deduplication.

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
    │   └─► RelevanceMatcher (21H: stop-word filtering + token deduplication)
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
    candidates: list[CapabilityCandidate],  # list of candidate capabilities with confidence scores
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
| `confidence` | float = 0.0 | **No** — preserved but unused |

The policy currently uses ONLY `len(candidates)`.

### What the policy does NOT know

- `MatchResult.confidence` (top score aggregate)
- `MatchResult.candidate_confidences` (per-candidate scores dict)
- `MatchResult.rationale`
- `MatchResult.matcher_id`
- Score gap between top and second candidate
- Request token count or specificity
- Whether matches come from name, description, or tags
- Any maturation/invocation/outcome evidence

### Architectural placement

The policy lives in the **AI plane** (`packages/ai/src/capability_action.py`). It is a pure decision function with no side effects. It does not call ports, execute capabilities, or manage state.

The matcher lives in **People/Capability** (`packages/capability_registry/src/relevance_matcher.py`). It produces relevance scores and rankings.

The current separation is architecturally correct:
- **Matching** answers: "Which capabilities are lexically relevant?"
- **Decision** answers: "What should the system do given those candidates?"
- **Execution** answers: "Can and should this capability actually be executed?"

---

## C. Score Distribution Analysis (21H Baseline)

### Corpus: 18 examples, 5 capabilities

| Category | Count | Score Range | Mean Score |
|----------|-------|-------------|------------|
| Specific | 9 | 0.667 – 0.900 | 0.811 |
| Generic | 4 | 0.000 – 1.000 | 0.350 |
| Negative | 3 | 0.000 – 0.000 | 0.000 |
| Ambiguous | 2 | 0.500 – 0.800 | 0.650 |

### Critical observation

The score distributions **overlap significantly**:

- **Specific** scores: 0.667–0.900
- **Ambiguous** scores: 0.500–0.800
- **Generic** scores: 0.000–1.000

There is **no clean numerical boundary** between these categories. Any threshold between 0.5 and 0.9 would misclassify examples from at least two categories.

### Top-score vs second-score (gap) analysis

| Request | Category | Top Score | 2nd Score | Gap | Count |
|---------|----------|-----------|-----------|-----|-------|
| create test artifact | specific | 0.833 | 0.267 | **0.567** | 2 |
| create artifact | specific | 0.750 | 0.400 | **0.350** | 2 |
| create a new lead | specific | 0.700 | 0.167 | **0.533** | 2 |
| create lead | specific | 0.900 | 0.250 | **0.650** | 2 |
| create something | generic | 0.400 | 0.250 | **0.150** | 2 |
| create | ambiguous | 0.800 | 0.500 | **0.300** | 2 |
| send notification | ambiguous | 0.500 | — | — | 1 |

**Gap distribution observations:**
- Specific multi-candidate gaps: 0.350–0.650 (wide)
- Generic multi-candidate gap: 0.150 (narrow)
- Ambiguous multi-candidate gaps: 0.300 (moderate)

The gap for "create something" (0.150) is clearly smaller than specific gaps. But "create" (ambiguous) has gap=0.300, which falls within the specific range. There is no natural gap threshold that separates all specific from all generic/ambiguous cases.

### Candidate count analysis

| Category | Avg Count | Distribution |
|----------|-----------|--------------|
| Specific | 1.44 | [2, 2, 1, 1, 1, 1, 2, 2, 1] |
| Generic | 0.75 | [2, 0, 0, 1] |
| Negative | 0.00 | [0, 0, 0] |
| Ambiguous | 1.50 | [2, 1] |

**Observations:**
- Negative requests correctly produce 0 candidates (after 21H stop-word filtering).
- Specific requests produce 1–2 candidates.
- Generic requests produce 0–2 candidates.
- Ambiguous requests produce 1–2 candidates.

Candidate count alone does not distinguish specific from generic. "create something" (generic) produces 2 candidates, same as "create test artifact" (specific).

---

## D. Specificity vs Relevance

### Can we measure request specificity independently of relevance?

**Partially, but not cleanly.**

#### What we can measure

1. **Meaningful token count**: Number of non-stop-word tokens in the request.
2. **Matched token count**: Number of meaningful tokens that overlap with any capability metadata.
3. **Token coverage**: `matched_tokens / meaningful_tokens`.
4. **Match source**: Whether the overlap comes primarily from capability name, description, or tags.
5. **Score gap**: Separation between top and next candidate.

#### What the data shows

| Request | Meaningful Tokens | Matched Tokens | Coverage | Match Source | Category |
|---------|-------------------|----------------|----------|--------------|----------|
| create test artifact | 3 | 3 | **100%** | name + desc + tags | specific |
| send email | 2 | 2 | **100%** | name | specific |
| analyse data | 2 | 2 | **100%** | name + tags | specific |
| create something | 2 | 1 | **50%** | name only | generic |
| do something | 1 | 0 | **0%** | none | generic |
| data | 1 | 1 | **100%** | tags only | generic |
| create | 1 | 1 | **100%** | name only | ambiguous |
| send notification | 2 | 2 | **100%** | name + desc + tags | ambiguous |

#### Key finding

**Token coverage does NOT cleanly distinguish specific from generic:**
- "data" has 100% coverage but is generic.
- "create" has 100% coverage but is ambiguous.
- "create something" has 50% coverage and is generic.

**Match source is not a reliable discriminator:**
- Specific requests match via name, description, and tags.
- Generic requests can match via name only ("create something") or tags only ("data").
- There is no structural difference in match source between specific and generic requests that have matches.

**Meaningful token count is not a reliable discriminator:**
- Specific requests: 2–3 meaningful tokens.
- Generic requests: 1–2 meaningful tokens.
- Ambiguous requests: 1–2 meaningful tokens.
- Overlap is significant.

### The fundamental limitation

The matcher operates on **lexical overlap**. It cannot distinguish:

- `"create [specific thing]"` — user has specific intent
- `"create something"` — user is vague
- `"create"` — user provides minimal information

Because in all three cases, the lexical signal is the same: the word `"create"` appears in capability metadata.

The matcher is **correct** that `"create"` is lexically relevant to `create_lead` and `create_test_artifact`. But lexical relevance is not the same as intent specificity. The matcher has no information about **what the user actually wants** — only what words they used.

---

## E. What the Corpus Tells Us

### Facts (observed from the corpus)

1. **Negative requests** (completely unrelated): All produce 0 candidates after 21H stop-word filtering. The matcher correctly identifies no lexical overlap.
2. **Specific requests** (clear intent): All produce 1–2 candidates with scores 0.667–0.900. The top candidate is always the intended one.
3. **Generic requests** (vague intent): Produce 0–2 candidates with scores 0.000–1.000. The range overlaps completely with specific requests.
4. **Ambiguous requests** (could match multiple): Produce 1–2 candidates with scores 0.500–0.800. Overlaps with specific range.
5. **Stop-word filtering** (21H) eliminated 2 of 3 observed false positives ("write a novel", "design a building").
6. **Token deduplication** (21H) had no effect on the corpus (no repeated tokens in any example).

### Assumptions (not proven by corpus)

1. The corpus is representative of real user requests. (It is not — it is a small, manually constructed set of 18 examples.)
2. The 5 capabilities in the corpus are representative of a real capability catalogue. (They are test fixtures, not production capabilities.)
3. The scoring distribution would remain stable with a larger catalogue. (It would likely change as more capabilities are added.)
4. Users would behave consistently when presented with candidates. (Unknown — no user-feedback data exists.)

### Signals (potentially useful, not yet actionable)

1. **Token coverage** (matched/meaningful tokens) is low for "create something" (50%) and high for specific requests (100%). But "data" and "create" also have 100% coverage despite being generic/ambiguous.
2. **Score gap** is narrow for "create something" (0.150) and wide for specific multi-candidate cases (0.350–0.650). But "create" (ambiguous) has gap=0.300, which is in the specific range.
3. **Match concentration** (name-only vs name+desc+tags) is not a reliable discriminator.

### Unknowns

1. Whether a larger corpus would reveal natural breakpoints in score or gap distributions.
2. Whether real users would consistently select the top-ranked candidate.
3. Whether request specificity can be reliably measured from text alone.
4. Whether the current scoring weights (0.5/0.3/0.2) are optimal.
5. Whether stemming, phrase matching, or other improvements would change distributions.

---

## F. The "create something" Case

### What the matcher does

1. Tokenises: `["create", "something"]` (after stop-word filtering)
2. Scores each capability:
   - `create_test_artifact`: name matches `"create"` → name_score=0.5, desc_score=0.0, tag_score=0.0 → combined=0.250
   - `create_lead`: name matches `"create"` → name_score=0.5, desc_score=0.0, tag_score=0.0 → combined=0.250
   - `send_email`: no matches → 0.0
   - `analyse_data`: no matches → 0.0
   - `generate_report`: no matches → 0.0
3. Returns: `create_lead` (0.250) and `create_test_artifact` (0.250), sorted alphabetically. `create_lead` wins the tie-break.

**The matcher is correct.** The word `"create"` is present in both capability names. The matcher faithfully reports lexical relevance.

### What the user meant

Unknown. The user said `"create something"`. This could mean:
- "Create a test artifact" (specific)
- "Create a new lead" (specific)
- "Create something entirely different not in this catalogue" (no match)

The matcher cannot distinguish these possibilities from the text alone.

### Why this is a decision problem, not a matcher problem

The matcher's job is to identify lexically relevant capabilities. It has done that correctly. The problem is that the **action policy** has no criterion to decide whether the lexical overlap is strong enough to present as a meaningful candidate.

The current policy presents all non-empty matches to the user. This is honest but potentially noisy. The question is whether we can introduce a **principled** criterion to filter weak matches without introducing an **arbitrary** threshold.

---

## G. Candidate Decision Models

### Model A — Count only (current)

```
0 → NoCapabilityMatch
1 → AskUserToSelect(interaction="confirm")
2+ → AskUserToSelect(interaction="select")
```

**Advantages:** Simple, honest, no thresholds.  
**Disadvantages:** Ignores all relevance information. Treats "create test artifact" (score 0.900) identically to "create something" (score 0.400).  
**Assessment:** Sufficient for current state. No arbitrary thresholds.

### Model B — Absolute relevance threshold

```
0 → NoCapabilityMatch
1, confidence >= X → ExecuteCapability or special action
1, confidence < X  → AskUserToSelect(interaction="confirm")
2+ → AskUserToSelect(interaction="select")
```

**Advantages:** Uses the relevance score.  
**Disadvantages:** Score is NOT calibrated probability. Any threshold X is arbitrary. The score distributions overlap significantly across categories.  
**Assessment:** Not defensible without calibration. Rejected.

### Model C — Relative dominance

```
0 → NoCapabilityMatch
1 → AskUserToSelect(interaction="confirm")
2+, gap >= Y → some different action (e.g., pre-select top candidate)
2+, gap < Y → AskUserToSelect(interaction="select")
```

**Advantages:** Uses relative information, which is more meaningful than absolute scores.  
**Disadvantages:** Gap distribution is sparse and catalogue-dependent. "create" (ambiguous) has gap=0.300, same as some specific cases. Any threshold Y is arbitrary.  
**Assessment:** Premature without calibration. Rejected.

### Model D — Token coverage

```
0 → NoCapabilityMatch
1, coverage >= Z → AskUserToSelect(interaction="confirm")
1, coverage < Z  → NoCapabilityMatch or Clarify
2+ → AskUserToSelect(interaction="select")
```

Where coverage = `matched_tokens / meaningful_tokens`.

**Advantages:** Measures how much of the user's actual input matched capability metadata.  
**Disadvantages:** 
- "data" has 100% coverage but is generic.
- "create" has 100% coverage but is ambiguous.
- "create something" has 50% coverage and is generic — but 50% is an arbitrary boundary.
- A single-token request like `"data"` would always have 100% coverage, even though it's vague.  
**Assessment:** Partially useful but still requires arbitrary thresholds. Not defensible.

### Model E — Minimum matched tokens

```
0 → NoCapabilityMatch
1, matched_tokens >= N → AskUserToSelect(interaction="confirm")
1, matched_tokens < N  → NoCapabilityMatch
2+ → AskUserToSelect(interaction="select")
```

**Advantages:** Simple, interpretable.  
**Disadvantages:** 
- "data" has 1 matched token — would be rejected under N=2, but the user might legitimately want data analysis.
- "send email" has 2 matched tokens — would be accepted.
- "create something" has 1 matched token — would be rejected.
- The boundary between N=1 and N=2 is arbitrary.  
**Assessment:** Arbitrary threshold. Rejected.

### Model F — Match source weighting

Prefer name matches over description matches over tag matches.

**Advantages:** Name matches are more specific than tag matches.  
**Disadvantages:** 
- "send email" matches via name (specific) — good.
- "send notification" matches via name + description + tags (ambiguous) — but the scoring formula already weights name at 50%, description at 30%, tags at 20%.
- Changing weights would be arbitrary.  
**Assessment:** Current weights are already a heuristic. Changing them would be a guess.

### Model G — Hybrid

Combine several signals with learned weights.

**Advantages:** Could theoretically produce nuanced decisions.  
**Disadvantages:** Most signals are not yet available or reliable. Combining uncalibrated signals does not make them calibrated. Would create complex, hard-to-reason-about policy logic.  
**Assessment:** Not justified. Violates explicitness principle.

---

## H. Where the Decision Belongs Architecturally

### Current architecture

```
People/Capability           AI Plane                    Operations
─────────────────          ─────────                   ──────────
RelevanceMatcher            CapabilityActionPolicy       CapabilityExecutionPort
  - matching                  - count-based decision       - execution
  - ranking                   - confirm/select             - authorisation
  - relevance scoring         - no thresholds              - outcome recording
```

### Should `CapabilityActionPolicy` become more sophisticated?

**Yes, eventually — but not yet.**

The policy is the correct architectural location for candidate-presentation decisions. It already owns the decision between `NoCapabilityMatch`, `confirm`, and `select`. Adding more nuanced decisions (e.g., `clarify`, `suggest`) would be a natural extension of this role.

However, the policy currently has **no defensible basis** for more nuanced decisions:
- Confidence scores are uncalibrated.
- Score gaps are sparse and catalogue-dependent.
- Token coverage is not a reliable discriminator.
- No evaluation corpus exists with enough examples to establish natural thresholds.
- No user-feedback data exists to validate any policy change.

### Should the matcher make presentation decisions?

**No.**

The matcher's role is to produce relevance scores and rankings. Introducing presentation logic into the matcher would:
- Conflate matching with decision-making.
- Make the matcher responsible for UX/policy concerns.
- Violate the architectural boundary established in 21A.

### Should a new assessment layer be created?

**No.**

A separate "assessment" or "ranking" layer would be a premature abstraction. The current boundary (matching → contract → action policy) is clean and sufficient. Adding another layer would:
- Introduce new interfaces and dependencies.
- Not solve the fundamental problem (lack of calibrated evidence).
- Create architectural complexity without corresponding value.

---

## I. Evidence and Calibration Readiness

### Current corpus size

- **18 examples** across **5 capabilities**
- Categories: 9 specific, 4 generic, 3 negative, 2 ambiguous
- This is a **seed corpus**, not a statistically significant sample.

### Is the corpus sufficient for calibration?

**No.**

Calibration requires:
1. A representative sample of real user requests.
2. Ground-truth labels for correct capabilities.
3. Enough examples to establish statistical distributions.
4. Coverage of edge cases and ambiguous requests.

The current corpus covers basic scenarios but is too small to establish natural thresholds. Any threshold derived from it would be overfitted to the examples.

### Is evidence mature enough for decision policy changes?

**No.**

| Evidence type | Status |
|---------------|--------|
| Invocation counts | Sparse (mostly test fixtures) |
| Correction counts | Sparse |
| Execution outcomes | Low volume, not correlated with matching |
| User selection feedback | Not captured |
| Calibration corpus | 18 examples, 5 capabilities — insufficient |

### Can we build a principled rule from current evidence?

**No.**

The current evidence does not support any principled, non-arbitrary decision rule for candidate presentation. The score distributions overlap across categories. Any numerical threshold would cut through the middle of the distribution and misclassify examples.

---

## J. The Honest Answer

### What should happen when a request is relevant but not discriminative?

**The current policy handles this correctly: present the candidates and ask the user to choose.**

The user has more context than the matcher. The user knows what they actually want. The matcher's job is to narrow the options to the lexically relevant ones. The user's job is to select the one they meant.

This is not a failure of the architecture. It is a correct separation of concerns:
- **Matcher**: "Here are the capabilities that match your words."
- **Action policy**: "Please choose which one you meant."
- **Execution**: "Running the capability you selected."

### Can we make this decision using a principled rule?

**No — not with the current evidence.**

A principled rule would require:
1. A calibrated relevance score (does not exist).
2. A statistically significant corpus (does not exist — 18 examples is insufficient).
3. User-feedback data to validate any rule (does not exist).
4. Natural breakpoints in score/gap distributions (not observed in current corpus).

Any rule we introduce today would be **arbitrary** — a guess dressed up as a threshold.

### Why not introduce an arbitrary threshold?

1. **It would masquerade as calibrated confidence.** A threshold like `score >= 0.5` implies that 0.5 has special meaning. It does not. It is just a number in the middle of an overlapping distribution.
2. **It would be brittle.** Adding more capabilities or changing scoring weights would shift the distribution, making the threshold meaningless.
3. **It would create false confidence.** Users might trust the system more than it deserves, leading to incorrect capability executions.
4. **It would be hard to reverse.** Once a threshold is in production code, it becomes "the way things work" even if it is arbitrary.

---

## K. Candidate Decision Models (Ranked by Evidence)

| Model | Evidence Basis | Arbitrariness | Architectural Fit | Recommendation |
|-------|---------------|---------------|-------------------|----------------|
| **Count only** (current) | None needed | None | Perfect | **Keep** |
| **Absolute threshold** | None | High | Poor | Defer indefinitely |
| **Relative dominance** | None | High | Moderate | Defer until calibration |
| **Token coverage** | Weak | Medium | Moderate | Investigate later |
| **Minimum matched tokens** | Weak | High | Moderate | Defer |
| **Match source weighting** | Weak | Medium | Moderate | Defer |
| **Hybrid/learned** | None | High | Poor | Defer indefinitely |

**The current count-only model is the only one that is honest about what the system knows.**

---

## L. What Would Actually Help

### 1. Expand the evaluation corpus (high value, low cost)

Add more examples covering:
- More capabilities (beyond 5 test fixtures)
- More request patterns (commands, questions, fragments)
- Edge cases (single-token, multi-token, mixed specific/generic)
- Realistic user language (not just capability names)

**This does not change production behaviour.** It only improves measurement.

### 2. Capture user selection feedback (high value, medium cost)

Record:
- Which candidate the user selected (or rejected).
- Whether the user confirmed or rejected a single candidate.
- Whether the user re-queried after seeing candidates.

**This would allow measurement of actual selection accuracy**, which is the only ground truth that matters.

### 3. Measure actual score/gap distributions at scale (medium value, medium cost)

Run the matcher against a large sample of real requests and record:
- Score distribution
- Gap distribution
- Candidate count distribution
- Category-stratified accuracy

**This would reveal whether the current corpus patterns hold at scale.**

### 4. Expand the corpus BEFORE changing the policy (prerequisite)

Any policy change should be:
1. Proposed as a hypothesis.
2. Tested against the expanded corpus.
3. Validated against user-feedback data.
4. Implemented only if evidence supports it.

---

## M. Explicit Deferrals

| Item | Why Deferred |
|------|--------|
| **Arbitrary score thresholds** | No calibrated basis. Would masquerade as confidence. |
| **Relative dominance thresholds** | Gap distribution is sparse. No natural breakpoint. |
| **Autonomous execution based on relevance** | Matching does not provide authorisation. Deferred indefinitely. |
| **Token-coverage heuristics** | Would require arbitrary minimum-coverage threshold. |
| **Minimum matched tokens** | Arbitrary boundary between N=1 and N=2. |
| **Match-source weighting changes** | Current weights are arbitrary. Any change would be a guess. |
| **Evidence-informed matching/action** | Evidence is too sparse. Deferred until invocation volume is meaningful. |
| **Separate assessment/ranking layer** | Premature abstraction. Current boundary is correct. |
| **LLM matching / embeddings / Qdrant** | Out of scope. |
| **Agent abstraction / orchestrator** | Architecture explicitly rejects (ADR-031, ADR-036, ADR-044). |
| **User-feedback infrastructure** | Valuable but requires new endpoint/storage. Defer until measurement priority is established. |

---

## N. Recommended Next Increment

### Increment 21J: Expand Evaluation Corpus and Capture Baseline Distributions

**Objective:** Gather enough evidence to eventually support principled decision-policy changes, without implementing any policy changes yet.

**Scope:**

1. **Expand the evaluation corpus** from 18 to ~50–100 examples:
   - Add more capabilities (beyond 5 test fixtures).
   - Add more request patterns (commands, questions, fragments, conversational language).
   - Add edge cases (single-token, multi-token, mixed specific/generic).
   - Add realistic user language from actual support tickets or user research if available.

2. **Compute and document full score/gap distributions:**
   - Score distribution histogram by category.
   - Gap distribution for multi-candidate cases.
   - Candidate count distribution.
   - Token coverage distribution.
   - These are measurement outputs, not policy changes.

3. **Add corpus validation tests:**
   - Verify every expected/alternative capability ID exists in the corpus.
   - Verify no duplicate requests.
   - Verify categories are correctly assigned.
   - Verify the corpus remains loadable and parseable.

4. **No production changes:**
   - No changes to `RelevanceMatcher`.
   - No changes to `CapabilityActionPolicy`.
   - No changes to contracts.
   - No changes to chat response.
   - No changes to telemetry.

**What this enables:**
- A statistically more robust understanding of score distributions.
- Identification of whether natural breakpoints exist in the data.
- A foundation for future calibration.
- Evidence to support or reject specific decision-model hypotheses.

**What this does NOT do:**
- It does NOT introduce thresholds.
- It does NOT change the action policy.
- It does NOT auto-execute capabilities.
- It does NOT expose scores to users.

---

## O. Summary

### What the corpus tells us

1. **The matcher correctly identifies lexical relevance.** Top-1 accuracy is 100% for specific and ambiguous examples.
2. **Stop-word filtering (21H) eliminated false positives caused by functional words.** No-match precision improved from 50% to 83.33%.
3. **The remaining false positive ("create something") is NOT a matcher problem.** It is a limitation of lexical matching: the matcher cannot distinguish specific intent from generic intent when the same content word appears in multiple capabilities.
4. **Score distributions overlap significantly across categories.** Specific (0.667–0.900), ambiguous (0.500–0.800), and generic (0.000–1.000) scores overlap. Any numerical threshold would misclassify examples.
5. **Token coverage, score gaps, and match sources do not provide clean discriminative boundaries** within the current corpus.

### What we cannot responsibly do yet

1. **Introduce a minimum relevance threshold.** Any number would be arbitrary.
2. **Distinguish dominant from ambiguous candidates.** Gap thresholds would be arbitrary without calibration.
3. **Distinguish specific from generic requests.** Token coverage and token count are unreliable discriminators.
4. **Auto-execute based on relevance.** Matching does not provide authorisation.
5. **Change the action policy.** There is no evidence-based basis for a change.

### What we should do instead

1. **Expand the evaluation corpus** to ~50–100 examples with more capabilities and realistic requests.
2. **Compute full score/gap distributions** to identify whether natural breakpoints exist at scale.
3. **Capture user selection feedback** to measure actual selection accuracy.
4. **Re-evaluate decision models** only after evidence exists to support them.

### The honest conclusion

> The current architecture is correct. The matcher does its job (lexical relevance). The action policy does its job (require user interaction). The remaining gap is not a matcher problem or a policy problem — it is an **evidence problem**. We do not yet have enough data to make principled decisions about candidate presentation. The smallest next step is to gather more evidence, not to introduce more logic.

---

## Acceptance Criteria

21I is complete when we can answer, with evidence:

1. **What should happen when a request is relevant but not discriminative?**
   - Answer: Present the candidates and ask the user to choose. The current policy handles this correctly.

2. **Can we make that decision using a principled rule derived from observable properties?**
   - Answer: **No, not with the current evidence.** The score distributions overlap across categories. Any threshold would be arbitrary. The corpus is too small (18 examples, 5 capabilities) to establish natural breakpoints.

3. **If yes, define the smallest coherent 21J implementation.**
   - Answer: **No implementation is justified.** The next step is measurement: expand the corpus and compute distributions. Only after evidence exists should we consider policy changes.

4. **If no, explicitly document why the system needs more evidence rather than more logic.**
   - Answer: The system needs a larger, more representative evaluation corpus and user-feedback data. The current corpus does not provide statistically significant distributions. Introducing logic without evidence would create arbitrary thresholds that masquerade as calibrated confidence.

---

*No production code was modified during this investigation.*
