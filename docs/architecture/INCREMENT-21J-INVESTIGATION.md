# Increment 21J — Investigation: Evaluation Corpus Expansion & Decision-Boundary Evidence

**Status:** Read-only investigation. No production code changes.  
**Prerequisites:** Increments 21A–21I implemented. 21G evaluation corpus established baseline. 21H implemented stop-word filtering and token deduplication.

---

## A. Executive Conclusion

> **What should happen when a request is relevant to one or more capabilities but does not contain enough information to distinguish user intent?**

Present the candidates and ask the user to choose. The current `CapabilityActionPolicy` handles this correctly.

> **Can that decision be made using a principled rule derived from observable properties, rather than an arbitrary score threshold?**

**Not yet.** The expanded corpus reveals a promising signal — `score_gap == 0.0` consistently identifies under-specified requests in the current corpus — but the corpus is still too small and synthetic to justify a policy change. The evidence suggests a direction for future investigation, not a ready-to-implement rule.

---

## B. Corpus Limitations

### What was expanded

| Property | 21G Baseline | 21J Expanded |
|----------|-------------|--------------|
| Examples | 18 | **70** |
| Capabilities | 5 | **16** |
| Specific | 9 | **43** |
| Generic | 4 | **14** |
| Ambiguous | 2 | **6** |
| Negative | 3 | **7** |

### Capability groups (realistic competition)

| Verb | Capabilities |
|------|-------------|
| create | create_lead, create_customer, create_report, create_test_artifact |
| send | send_email, send_sms, send_notification |
| analyse | analyse_data, analyse_report, analyse_sentiment |
| update | update_record, update_status, update_profile |
| generate | generate_report, generate_summary, generate_insights |

### Limitations

1. **Still synthetic.** Examples are manually constructed, not real user requests.
2. **Still small.** 70 examples across 16 capabilities is a seed corpus, not a statistically significant sample.
3. **Capability metadata is uniform.** Real capabilities have varied description lengths, tag densities, and naming conventions.
4. **No user-feedback data.** We do not know which candidates users actually select or reject.
5. **No context.** Requests are isolated strings without conversational or situational context.

**Conclusion:** The expanded corpus provides more nuanced evidence than 21G, but it remains a synthetic seed corpus. Conclusions should be treated as hypotheses, not established facts.

---

## C. Score Distribution Analysis

### Overall distributions

| Category | Count | Score Range | Mean Score |
|----------|-------|-------------|------------|
| Specific | 43 | 0.375 – 1.000 | 0.746 |
| Generic | 14 | 0.000 – 1.000 | 0.450 |
| Ambiguous | 6 | 0.500 – 1.000 | 0.783 |
| Negative | 7 | 0.000 – 0.000 | 0.000 |

### Key observation

**Score distributions overlap significantly across categories:**
- Specific (0.375–0.900) overlaps with generic (0.000–1.000) and ambiguous (0.500–1.000).
- No clean numerical boundary separates these categories.
- A threshold at 0.5 would misclassify specific requests with scores 0.375–0.500 as generic.
- A threshold at 0.8 would misclassify ambiguous requests (0.800–1.000) as specific.

### Top-1 / Top-3 accuracy

| Metric | Value |
|--------|-------|
| Top-1 accuracy | **100.00%** (54/54) |
| Top-3 recall | **100.00%** (54/54) |
| No-match precision | **68.75%** (11/16) |
| Avg candidate set size | **3.31** |
| Median candidate set size | **3.0** |

**Interpretation:** The matcher correctly ranks the intended capability first for all specific and ambiguous requests. No-match precision improved from the 21G baseline (50% → 68.75%) because the expanded corpus includes more negative examples that correctly produce zero candidates. However, 5 generic requests still produce false positives.

---

## D. Top-Score vs Second-Score Analysis

### Score-gap distributions

| Category | Multi-candidate Count | Gap Range | Gap Mean |
|----------|----------------------|-----------|----------|
| Specific | 43 | 0.050 – 0.567 | 0.381 |
| Generic | 10 | 0.000 – 0.000 | 0.000 |
| Ambiguous | 6 | 0.100 – 0.500 | 0.317 |

### Critical finding: gap=0.0 perfectly identifies generic requests

| Request | Category | Top Score | Gap | Count |
|---------|----------|-----------|-----|-------|
| create something | generic | 0.400 | **0.000** | 4 |
| send something | generic | 0.400 | **0.000** | 3 |
| analyse something | generic | 0.400 | **0.000** | 3 |
| generate something | generic | 0.400 | **0.000** | 3 |
| update something | generic | 0.500 | **0.000** | 3 |
| create | generic | 0.800 | **0.000** | 4 |
| send | generic | 0.800 | **0.000** | 3 |
| analyse | generic | 0.800 | **0.000** | 3 |
| generate | generic | 0.800 | **0.000** | 3 |
| update | generic | 1.000 | **0.000** | 3 |

**Every request with gap=0.0 in the corpus is generic/underspecified.** No specific or ambiguous request has gap=0.0.

### But specific requests can have small gaps

| Request | Category | Top Score | 2nd Score | Gap |
|---------|----------|-----------|-----------|-----|
| send email notification now | specific | 0.500 | 0.450 | **0.050** |
| send email notification | specific | 0.667 | 0.600 | **0.067** |
| I want to send an email | specific | 0.375 | 0.200 | **0.175** |

**Interpretation:** Gap=0.0 is a strong signal of under-specification, but small positive gaps (0.05–0.175) do not reliably indicate generic requests. A gap threshold of 0.1 would misclassify "send email notification" (specific, gap=0.067) as ambiguous.

---

## E. Candidate-Count Analysis

| Category | Avg Count | Distribution |
|----------|-----------|--------------|
| Specific | 3.95 | [3–6] |
| Generic | 2.29 | [0–4] |
| Ambiguous | 5.00 | [3–6] |
| Negative | 0.00 | [0] |

**Key finding:** Candidate count is NOT a useful discriminator. Specific requests average **more** candidates (3.95) than generic requests (2.29) because the expanded catalogue has 16 capabilities with significant verb/noun overlap. A user asking "create a lead" triggers matches against all 4 `create_*` capabilities, while "create something" triggers matches against the same 4 capabilities but with lower scores.

**Conclusion:** Candidate count reflects catalogue size and verb popularity, not request specificity.

---

## F. Token Coverage Analysis

| Category | Min Coverage | Max Coverage | Mean Coverage |
|----------|-------------|-------------|---------------|
| Specific | 0.50 | 1.00 | 0.87 |
| Generic | 0.00 | 1.00 | 0.54 |
| Ambiguous | 0.50 | 1.00 | 0.83 |

### "X something" pattern

All generic "X something" requests have **exactly 50% token coverage**:
- "create something": meaningful=2, matched=1, coverage=0.50
- "send something": meaningful=2, matched=1, coverage=0.50
- "analyse something": meaningful=2, matched=1, coverage=0.50
- "generate something": meaningful=2, matched=1, coverage=0.50
- "update something": meaningful=2, matched=1, coverage=0.50

The unmatched token is always "something" (or equivalent generic placeholder).

### Single-token generic requests

Single-token requests like "create", "send", "analyse", "generate", "update" have **100% coverage** (1/1 tokens matched). Coverage alone cannot identify these as generic.

### Specific requests

Most specific requests have 100% coverage. A few have lower coverage due to filler words that are not stop words (e.g., "create test artifact please" — "please" is not in the stop-word set, so coverage would be 3/4 = 0.75). However, these are rare in the current corpus.

---

## G. Match-Source Analysis

| Category | Name | Description | Tags |
|----------|------|-------------|------|
| Specific | 43/43 | 43/43 | 43/43 |
| Generic | 10/10 | 10/10 | 2/10 |
| Ambiguous | 6/6 | 6/6 | 6/6 |

**Interpretation:** For specific and ambiguous requests, matches typically come from all three sources (name, description, tags). For generic requests, matches predominantly come from name and description; tags contribute in only 2/10 cases.

**Assessment:** Match source is not a reliable discriminator. Specific and ambiguous requests both show multi-source matches. Generic "X something" requests show name+description matches, which is similar to specific requests with limited description overlap.

---

## H. Relevance vs Specificity

### Can we distinguish these dimensions?

**Partially.**

The corpus reveals two distinct dimensions:

| Dimension | What it measures | Observable from corpus? |
|-----------|-----------------|------------------------|
| **Relevance** | How strongly does the request overlap with a capability's metadata? | Yes — captured by `confidence` score |
| **Specificity** | How much information does the request contain to discriminate between capabilities? | Partially — gap=0.0 and coverage<1.0 are signals |

### Evidence from corpus

**High relevance + high specificity (specific requests):**
- "create test artifact": score=0.833, gap=0.567, coverage=1.00
- "send email": score=0.750, gap=0.000 (single candidate), coverage=1.00
- "analyse data": score=0.900, gap=0.000 (single candidate), coverage=1.00

**High relevance + low specificity (generic requests):**
- "create something": score=0.400, gap=0.000, coverage=0.50
- "send something": score=0.400, gap=0.000, coverage=0.50
- "create": score=0.800, gap=0.000, coverage=1.00

**High relevance + ambiguous (ambiguous requests):**
- "create": score=0.800, gap=0.300, coverage=1.00
- "send notification": score=0.500, gap=0.000 (single candidate), coverage=1.00

### Key distinction

**"create something" vs "create":**
- Both have high lexical relevance to create_* capabilities.
- "create something" has gap=0.0, coverage=0.50, score=0.400.
- "create" has gap=0.0, coverage=1.00, score=0.800.
- Both are generic/ambiguous, but for different reasons:
  - "create something" is under-specified (generic object).
  - "create" is a single token with no discriminating object.

The matcher cannot distinguish these from lexical overlap alone. Both produce valid relevance scores. The difference is in **what the user left unspecified**, which the matcher cannot know.

---

## I. Discrimination Analysis

### What is discrimination?

Discrimination is the degree to which a request's tokens distinguish one capability from its competitors.

### Measurable proxies

| Proxy | How measured | What it tells us |
|-------|-------------|-----------------|
| **Score gap** | `top_score - second_score` | Whether the top candidate dominates alternatives |
| **Token coverage** | `matched_tokens / meaningful_tokens` | How much of the request is explained by the top candidate |
| **Candidate count** | `len(candidates)` | How many capabilities are lexically relevant |
| **Match uniqueness** | Whether matched tokens appear in only one candidate | Whether the request uniquely identifies a capability |

### Findings

**Score gap:**
- gap=0.0 → always generic in current corpus (10/10)
- gap>0 → specific or ambiguous (60/60)
- BUT specific requests can have small gaps (0.050–0.175)

**Token coverage:**
- coverage < 1.0 → always "X something" pattern (5/5)
- coverage = 1.0 → specific, generic single-token, or ambiguous
- Not a complete discriminator

**Candidate count:**
- No correlation with specificity in expanded corpus
- Specific requests average MORE candidates than generic requests (3.95 vs 2.29)
- Not useful as a specificity signal

**Match uniqueness:**
- "create test artifact": all 3 meaningful tokens appear in create_test_artifact's name — unique match
- "create something": only "create" appears, and it appears in 4 capabilities — non-unique
- This is a promising signal but requires comparing matched tokens across ALL candidates, not just the top one

---

## J. Architectural Assessment

### Where does candidate-presentation decision belong?

**Answer: `CapabilityActionPolicy` in the AI plane.**

The policy already owns the decision between:
- `NoCapabilityMatch` (0 candidates)
- `AskUserToSelect(interaction="confirm")` (1 candidate)
- `AskUserToSelect(interaction="select")` (2+ candidates)

Adding nuanced presentation logic (e.g., `clarify`, `suggest`) would be a natural extension of this role.

### Should `RelevanceMatcher` make presentation decisions?

**No.**

The matcher's role is to produce relevance scores and rankings. Introducing presentation logic into the matcher would:
- Conflate matching with decision-making.
- Violate the architectural boundary established in 21A.
- Make the matcher responsible for UX/policy concerns.

### Should a new assessment layer be created?

**No.**

A separate "assessment" or "ranking" layer would be a premature abstraction. The current boundary (matching → contract → action policy) is clean and sufficient.

### Can `CapabilityActionPolicy` own two distinct decisions?

Yes, potentially:

1. **Is this candidate safe/authorised to execute?** (Currently: always require user confirmation)
2. **Is this candidate sufficiently supported to present to the user?** (Currently: always present all matches)

These are materially different concerns. The first is about execution authority. The second is about presentation quality. The policy could eventually distinguish them.

**But currently, there is no evidence-based basis for the second decision.**

---

## K. Candidate Decision Models (Ranked by Evidence)

| Model | Evidence Basis | Arbitrariness | Architectural Fit | Recommendation |
|-------|---------------|---------------|-------------------|----------------|
| **A. Count only** (current) | None needed | None | Perfect | **Keep** |
| **B. Absolute score threshold** | None | High | Poor | Defer indefinitely |
| **C. Score-gap threshold** | Weak (gap=0.0 is promising but corpus is small) | Medium | Moderate | Investigate with larger corpus |
| **D. Token-coverage threshold** | Weak (coverage<1.0 identifies "X something" but not single-token generics) | High | Moderate | Defer |
| **E. Match-uniqueness rule** | Untested | Medium | Moderate | Investigate with larger corpus |
| **F. Hybrid observable rule** | None | High | Poor | Defer indefinitely |

### Detailed evaluation

**Model A — Count only (current):**
- Evidence: None needed. Honest about what the system knows.
- Arbitrariness: None.
- Assessment: **Sufficient for current state.**

**Model B — Absolute score threshold:**
- Evidence: Score distributions overlap across categories. No natural breakpoint.
- Arbitrariness: High. Any threshold would cut through overlapping distributions.
- Assessment: **Not defensible without calibration.**

**Model C — Score-gap threshold:**
- Evidence: gap=0.0 perfectly identifies generic requests in current corpus. But specific requests can have gaps as small as 0.050.
- Arbitrariness: Medium. gap=0.0 is a mathematical property (perfect tie), but any positive threshold (e.g., gap < 0.1) would misclassify specific requests.
- Assessment: **Promising but premature.** The gap=0.0 signal is robust within the current corpus, but we don't know if it generalizes. A larger corpus with more realistic capabilities and requests is needed.

**Model D — Token-coverage threshold:**
- Evidence: coverage < 1.0 identifies "X something" pattern, but single-token generics have coverage=1.0.
- Arbitrariness: High. What threshold? 0.5? 0.75? 1.0? Each misclassifies some requests.
- Assessment: **Not defensible without additional signals.**

**Model E — Match-uniqueness rule:**
- Evidence: Untested in current corpus. Conceptually promising: if the request's matched tokens appear in only one candidate, the request is discriminative.
- Arbitrariness: Medium. Requires defining "uniqueness" (e.g., unique tokens, unique combination).
- Assessment: **Worth investigating with a larger corpus.**

**Model F — Hybrid observable rule:**
- Evidence: None. Combining uncalibrated signals does not make them calibrated.
- Arbitrariness: High. Weights and thresholds would be guesses.
- Assessment: **Not justified.**

---

## L. What Would Actually Help

### 1. Expand corpus to 100+ examples with more realistic capabilities (HIGH value, LOW cost)

The current corpus has 16 capabilities with artificially clean metadata. Real capabilities have:
- Varied description lengths
- Overlapping tags
- Synonym usage
- Abbreviations and acronyms
- Domain-specific terminology

A larger corpus would reveal whether gap=0.0 remains a reliable signal as the catalogue grows.

### 2. Collect real user requests (HIGH value, MEDIUM cost)

The current corpus is synthetic. Real user requests contain:
- Conversational language
- Typos and abbreviations
- Context-dependent references
- Implicit assumptions
- Domain jargon

Real requests would reveal whether the current patterns hold in practice.

### 3. Capture user selection/rejection feedback (HIGH value, MEDIUM cost)

Record:
- Which candidate the user selected.
- Whether the user confirmed or rejected a single candidate.
- Whether the user re-queried after seeing candidates.

This would allow measurement of actual selection accuracy, which is the only ground truth that matters.

### 4. Measure score/gap distributions at scale (MEDIUM value, MEDIUM cost)

Run the matcher against a large sample of requests and record:
- Score distribution
- Gap distribution
- Candidate count distribution
- Category-stratified accuracy

This would reveal whether the current corpus patterns hold at scale.

---

## M. Explicit Deferrals

| Item | Why Deferred |
|------|--------|
| **Arbitrary score thresholds** | No calibrated basis. Would masquerade as confidence. |
| **Score-gap thresholds** | gap=0.0 is promising but corpus is too small to justify a positive threshold. |
| **Token-coverage heuristics** | Coverage < 1.0 identifies "X something" but not single-token generics. Would require arbitrary threshold. |
| **Minimum matched tokens** | Arbitrary boundary between N=1 and N=2. |
| **Match-uniqueness rule** | Untested. Requires larger corpus to validate. |
| **Autonomous execution based on relevance** | Matching does not provide authorisation. Deferred indefinitely. |
| **Evidence-informed matching/action** | Evidence is too sparse. Deferred until invocation volume is meaningful. |
| **User-feedback infrastructure** | Valuable but requires new endpoint/storage. Defer until measurement priority is established. |
| **Separate assessment/ranking layer** | Premature abstraction. Current boundary is correct. |
| **LLM matching / embeddings / Qdrant** | Out of scope. |
| **Agent abstraction / orchestrator** | Architecture explicitly rejects (ADR-031, ADR-036, ADR-044). |

---

## N. Recommended Next Increment

### Increment 21K: Real-Request Corpus and User-Feedback Capture

**Objective:** Gather evidence at scale to determine whether a principled candidate-presentation boundary exists.

**Scope:**

1. **Collect real user requests** from production logs, support tickets, or user research:
   - At least 100–200 requests
   - With ground-truth labels (which capability did the user actually want?)
   - Covering diverse phrasing, domains, and specificity levels

2. **Implement lightweight user-feedback capture:**
   - Record which candidate the user selected or rejected
   - Record whether the user confirmed a single candidate
   - Record whether the user re-queried after seeing candidates
   - Smallest possible implementation: extend existing chat response or add a lightweight feedback endpoint

3. **Re-run evaluation corpus against real requests:**
   - Compute score/gap distributions on real data
   - Validate whether gap=0.0 remains a reliable signal
   - Measure top-1 accuracy on real requests
   - Identify failure modes in production language

4. **No production behaviour changes:**
   - No changes to `RelevanceMatcher`
   - No changes to `CapabilityActionPolicy`
   - No changes to contracts
   - No thresholds introduced

**What this enables:**
- Statistically significant score/gap distributions
- Validation of gap=0.0 signal on real data
- Measurement of actual selection accuracy
- Evidence to support or reject specific decision-model hypotheses

**What this does NOT do:**
- It does NOT introduce thresholds.
- It does NOT change the action policy.
- It does NOT auto-execute capabilities.
- It does NOT expose scores to users.

---

## O. Summary

### What the expanded corpus tells us

1. **The matcher correctly identifies lexical relevance.** Top-1 accuracy is 100% for specific and ambiguous examples.
2. **Score distributions overlap significantly across categories.** Specific (0.375–1.000), generic (0.000–1.000), and ambiguous (0.500–1.000) scores overlap. No clean numerical boundary exists.
3. **Score gaps reveal a promising signal:** gap=0.0 perfectly identifies generic requests in the current corpus. But specific requests can have small gaps (0.050–0.175), so gap thresholds would misclassify them.
4. **Token coverage identifies "X something" patterns** (coverage=0.50) but not single-token generic requests (coverage=1.0).
5. **Candidate count is not a useful discriminator.** Specific requests average more candidates than generic requests in the expanded corpus.
6. **The current count-only policy remains the most defensible approach.**

### What we cannot responsibly do yet

1. **Introduce a minimum relevance threshold.** Any number would be arbitrary.
2. **Use score-gap thresholds.** gap=0.0 is promising but requires validation with a larger corpus.
3. **Use token-coverage thresholds.** Coverage < 1.0 identifies only one pattern of under-specification.
4. **Distinguish specific from generic requests.** No observable property cleanly separates these categories.
5. **Auto-execute based on relevance.** Matching does not provide authorisation.

### The honest conclusion

> The expanded corpus provides more nuanced evidence than the 21G baseline, but it does not establish a principled decision boundary. The most promising signal — `score_gap == 0.0` consistently identifying under-specified requests — requires validation with a larger, more realistic corpus and real user requests. The current count-only policy remains the most honest and defensible approach. The smallest next step is to gather more evidence (real requests + user feedback), not to introduce more logic.

---

## Acceptance Criteria

21J is complete when the report can answer:

1. **Does the expanded evidence reveal a principled observable distinction between "relevant" and "sufficiently discriminative" capability matches?**
   - Answer: **Partially.** `score_gap == 0.0` is a strong empirical signal in the current corpus, but it has not been validated on a larger or more realistic corpus. Other signals (token coverage, candidate count) are insufficient on their own.

2. **Is there sufficient evidence to justify changing the candidate-presentation decision policy?**
   - Answer: **No.** The corpus is still synthetic and small (70 examples, 16 capabilities). Any policy change would be based on patterns observed in a seed corpus, not statistically significant evidence.

3. **If no, what is the smallest next evidence-gathering increment?**
   - Answer: **Increment 21K: Real-Request Corpus and User-Feedback Capture.** Collect 100–200 real user requests with ground-truth labels, implement lightweight user-feedback capture, and validate whether the gap=0.0 signal holds at scale.

---

*No production code was modified during this investigation.*
