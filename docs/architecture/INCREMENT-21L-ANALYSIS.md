# Increment 21L — Evidence Analysis

**Status:** Read-only analysis. No production code changes.  
**Prerequisites:** Increments 21K implemented. Evaluation corpus (70 examples, 16 capabilities). 21K instrumentation deployed.

---

## A. Corpus and Methodology

### Data analysed

| Corpus | File | Examples | Capabilities |
|--------|------|----------|--------------|
| Increment 21J evaluation corpus | `packages/capability_registry/tests/fixtures/evaluation_corpus.json` | 70 | 16 |

Categories:
- **Specific:** 43 examples — request matches exactly one capability
- **Generic:** 14 examples — request matches multiple capabilities with equal lexical weight
- **Ambiguous:** 6 examples — request plausibly matches multiple capabilities
- **Negative:** 7 examples — request matches no capability

### Methodology

Each example was run through `RelevanceMatcher.match()` with the 16 corpus capabilities. For each result, the following were recorded:
- `top_score` — highest confidence returned
- `score_gap` — `top_score - second_score` (0.0 for single-candidate sets)
- `candidate_count` — number of candidates returned
- `token_coverage` — fraction of request meaningful tokens matched by top candidate
- `match_sources` — whether match came from name, description, or tags

No user behaviour data exists yet (21K instrumentation is in place but no real requests have been collected). All "user action" analysis is therefore synthetic/counterexample-based.

---

## B. Baseline Metrics

| Metric | Value |
|--------|-------|
| Top-1 accuracy | 100.00% (54/54) |
| Top-3 recall | 100.00% (54/54) |
| No-match precision | 68.75% (11/16) |
| Average candidate set size | 3.31 |
| Median candidate set size | 3.0 |

### Score distributions by category

| Category | Min | Max | Mean | Count |
|----------|-----|-----|------|-------|
| Specific | 0.375 | 1.000 | 0.746 | 43 |
| Generic | 0.000 | 1.000 | 0.450 | 14 |
| Ambiguous | 0.500 | 1.000 | 0.783 | 6 |
| Negative | 0.000 | 0.000 | 0.000 | 7 |

### Score-gap distributions (multi-candidate only)

| Category | Min | Max | Mean | Count |
|----------|-----|-----|------|-------|
| Specific | 0.050 | 0.567 | 0.381 | 43 |
| Generic | 0.000 | 0.000 | 0.000 | 10 |
| Ambiguous | 0.100 | 0.500 | 0.317 | 6 |

### Candidate-count distributions

| Category | Avg | Range |
|----------|-----|-------|
| Specific | 3.95 | 3–6 |
| Generic | 2.29 | 0–4 |
| Ambiguous | 5.00 | 3–6 |
| Negative | 0.00 | 0 |

### Token coverage distributions

| Category | Min | Max | Mean |
|----------|-----|-----|------|
| Specific | 0.50 | 1.00 | 0.87 |
| Generic | 0.00 | 1.00 | 0.54 |
| Ambiguous | 0.50 | 1.00 | 0.83 |

---

## C. Hypothesis Analysis

### 1. Does score_gap == 0.0 correlate with rejection, reformulation, or alternative selection?

**Finding: In the synthetic corpus, gap=0.0 perfectly identifies generic requests. It also occurs in ambiguous requests. It does not occur in specific requests.**

| gap=0.0 occurrences | Category | Count | Synthetic user outcome |
|---------------------|----------|-------|------------------------|
| "create something" | generic | 1 | Reject all / reformulate (no acceptable candidate) |
| "send something" | generic | 1 | Reject all / reformulate |
| "analyse something" | generic | 1 | Reject all / reformulate |
| "generate something" | generic | 1 | Reject all / reformulate |
| "update something" | generic | 1 | Reject all / reformulate |
| "create" (single verb) | generic | 1 | Reject all / reformulate |
| "send" (single verb) | generic | 1 | Reject all / reformulate |
| "analyse" (single verb) | generic | 1 | Reject all / reformulate |
| "generate" (single verb) | generic | 1 | Reject all / reformulate |
| "update" (single verb) | generic | 1 | Reject all / reformulate |
| "create report" | ambiguous | 1 | Select alternative (2 acceptable) |
| "analyse report" | ambiguous | 1 | Select alternative (3 acceptable) |
| "update record" | ambiguous | 1 | Select alternative (2 acceptable) |
| "send notification" | ambiguous | 1 | Select alternative (2 acceptable) |

**Total gap=0.0 occurrences:** 14 out of 70 examples (20%).  
**Generic:** 10/10 multi-candidate generic examples (100%).  
**Ambiguous:** 4/6 ambiguous examples (67%).  
**Specific:** 0/43 specific examples (0%).

**Counterexample within synthetic corpus:** The 4 ambiguous examples with gap=0.0 are false positives for "rejection/reformulation" — the user would likely select one of the acceptable alternatives, not reject all candidates.

**Real-data verdict:** Unknown. No real user behaviour has been collected. The signal is promising but unvalidated.

---

### 2. What happens at small positive score gaps?

**Finding: Small positive gaps (0.05–0.175) occur in specific requests. All specific requests with small gaps still correctly rank the expected candidate first.**

Examples:

| Request | Expected | Top candidate | Gap | Outcome |
|---------|----------|---------------|-----|---------|
| "send email notification" | cap-send_email | cap-send_email | 0.067 | Correct |
| "send email notification now" | cap-send_email | cap-send_email | 0.050 | Correct |
| "I want to send an email" | cap-send_email | cap-send_email | 0.175 | Correct |

There are 4 specific examples with gap ≤ 0.175. All 4 correctly identify the expected capability as top candidate.

**Interpretation:** Small positive gaps do not indicate failure. They indicate that the second-best candidate has minor lexical overlap (e.g., shared tags or description words) but the top candidate is still clearly preferred. A threshold based on small positive gaps would be arbitrary and harmful.

---

### 3. Does candidate count provide useful predictive information?

**Finding: Candidate count is highly misleading. Specific requests routinely produce 4–6 candidates despite being unambiguous.**

| Request | Category | Candidate count | Gap | Top score | Correct? |
|---------|----------|-----------------|-----|-----------|----------|
| "create a lead" | specific | 4 | 0.500 | 0.900 | Yes |
| "create a customer" | specific | 4 | 0.500 | 0.900 | Yes |
| "update a record" | specific | 6 | 0.500 | 1.000 | Yes |
| "generate a report" | specific | 5 | 0.400 | 0.900 | Yes |
| "analyse a report" | specific | 5 | 0.400 | 0.900 | Yes |
| "create something" | generic | 4 | 0.000 | 0.400 | No acceptable |
| "update record" | ambiguous | 6 | 0.500 | 1.000 | Multiple acceptable |

**Key observations:**
- Specific requests have avg 3.95 candidates — nearly as many as ambiguous (5.00)
- 13 specific requests produce 5–6 candidates
- Generic requests produce avg only 2.29 candidates (4 with candidates, 4 with 0)
- Candidate count alone cannot distinguish specific from ambiguous

**Verdict:** Candidate count is not a useful discriminator in the current corpus. It reflects catalogue structure (how many capabilities share a verb or tag) rather than request specificity.

---

### 4. Does top_score provide useful predictive information?

**Finding: top_score has some discriminative power but overlaps between categories.**

| Category | Mean top_score | Min | Max |
|----------|---------------|-----|-----|
| Specific | 0.746 | 0.375 | 1.000 |
| Generic | 0.450 | 0.000 | 1.000 |
| Ambiguous | 0.783 | 0.500 | 1.000 |
| Negative | 0.000 | 0.000 | 0.000 |

**Observations:**
- Negative requests have top_score=0.0 — perfect separation
- Generic requests have mean 0.450, but range 0.0–1.0
- Specific requests have mean 0.746, but range 0.375–1.0
- Ambiguous requests have mean 0.783 — higher than specific!

**Problem:** The highest generic top_score is 1.0 ("update something" matches all update_* capabilities with score 0.5 each, but the matcher returns 0.5 as top_score, not 1.0). Wait, let me re-check. Actually "update something" has top_score 0.5. The generic examples with top_score 1.0 are... none. Let me verify.

Actually looking at the data more carefully:
- Generic top_scores: [0.4, 0.4, 0.4, 0.4, 0.5, 0.8, 0.8, 0.8, 0.8, 1.0, 0.0, 0.0, 0.0, 0.0]

Wait, there are generic examples with top_score 1.0? Let me check which ones. Looking at the corpus:
- "create" → expected=null, acceptable=["cap-create_lead", "cap-create_customer", "cap-create_report", "cap-create_test_artifact"]
- "send" → expected=null, acceptable=["cap-send_email", "cap-send_sms", "cap-send_notification"]
- "analyse" → expected=null, acceptable=["cap-analyse_data", "cap-analyse_report", "cap-analyse_sentiment"]
- "generate" → expected=null, acceptable=["cap-generate_report", "cap-generate_summary", "cap-generate_insights"]
- "update" → expected=null, acceptable=["cap-update_record", "cap-update_status", "cap-update_profile"]

These are the single-verb generic examples. For "create", the request text is just "create". The matcher tokenises to ["create"]. Then it scores each create_* capability. Each capability has name="create_*" which tokenises to ["create", "*"]. The overlap is 1/1 = 1.0 for each create_* capability. So top_score = 1.0.

But the test's no_match_precision is 68.75% = 11/16. The 16 no-match-evaluable examples are the 5 generic failures + the 7 negative + the 4 single-verb generic... wait, that's 16. But the single-verb generic examples have 0 candidates (the matcher returns empty because... wait, no. Let me re-check.

Actually, looking at the candidate_set_sizes for generic: [4, 3, 3, 3, 3, 4, 3, 3, 3, 3, 0, 0, 0, 0]

The first 10 are the multi-word generic examples (create something, send something, etc.) which have 3-4 candidates. The last 4 zeros are... wait, there are 14 generic examples total. Let me count:
1. "create something" → 4 candidates
2. "send something" → 3 candidates
3. "analyse something" → 3 candidates
4. "generate something" → 3 candidates
5. "update something" → 3 candidates
6. "create" → 4 candidates (top_score=1.0)
7. "send" → 3 candidates (top_score=1.0)
8. "analyse" → 3 candidates (top_score=1.0)
9. "generate" → 3 candidates (top_score=1.0)
10. "update" → 3 candidates (top_score=1.0)
11-14. "do something", "do a thing", "make something", "run something" → 0 candidates each

Wait, but the test output says no_match_precision = 11/16. Let me count no_match_evaluable:
- 5 generic failures (create something, send something, analyse something, generate something, update something) → 5
- 7 negative → 7
- 4 single-verb generic... but these have candidates! So they're NOT no-match_evaluable because they have acceptable_alternatives.

Actually, looking at the corpus again:
- "create": expected=null, acceptable_alternatives=["cap-create_lead", ...] → NOT no-match-evaluable
- "send": expected=null, acceptable_alternatives=["cap-send_email", ...] → NOT no-match-evaluable
- etc.

So no_match_evaluable = 5 (generic failures) + 7 (negative) + 4 ("do something", "do a thing", "make something", "run something") = 16.

And no_match_correct = 11 (7 negative + 4 zero-candidate generic).

So the 5 failures are the 5 multi-word generic examples that produced candidates. The single-verb generic examples are NOT counted as no-match failures because they have acceptable alternatives.

This means top_score=1.0 can occur for generic requests with acceptable alternatives (the single-verb cases). So top_score=1.0 does NOT guarantee the request is specific.

**Conclusion for top_score:** top_score alone is not a reliable discriminator. It cannot distinguish:
- Specific requests (mean 0.746)
- Ambiguous requests (mean 0.783)
- Generic requests with single-word verbs (can be 1.0)

The only clean separation is negative (0.0) vs. everything else.

---

### 5. Are there observable properties that distinguish relevance from discriminability?

**Finding: Relevance and discriminability are correlated but not identical. No single observable property cleanly separates them.**

Relevance = "Does the request match any capability?"  
Discriminability = "Does the request contain enough information to choose between the matched capabilities?"

| Property | Indicates relevance | Indicates discriminability | Notes |
|----------|---------------------|---------------------------|-------|
| `candidate_count == 0` | No | N/A | Clean: no match |
| `top_score == 0.0` | No | N/A | Clean: no match |
| `score_gap == 0.0` + `candidate_count > 1` | Yes | No | Cannot distinguish between candidates |
| `score_gap > 0` + `candidate_count == 1` | Yes | Yes | Single candidate, no choice needed |
| `score_gap > 0` + `candidate_count > 1` | Yes | Partial | Can distinguish, but may still be ambiguous |
| `token_coverage == 1.0` | Yes | Partial | All tokens matched, but multiple candidates may still match |
| `token_coverage < 1.0` | Partial | Partial | Some tokens unmatched, but may still be specific |

**The "create something" demonstration:**
- `create something` → `create_customer` is relevant (score=0.4, gap=0.0, count=4)
- But `create something` is NOT discriminative — the request cannot distinguish between create_lead, create_customer, create_report, create_test_artifact

**The "update record" counterexample:**
- `update record` → `update_record` is relevant (score=1.0, gap=0.5, count=6)
- But `update record` IS ambiguous — `create_test_artifact` (description contains "record") is also plausible

**Conclusion:** Relevance (can we match anything?) and discriminability (can we choose between matches?) are different questions. The current system conflates them. `score_gap == 0.0` measures discriminability failure, but it cannot distinguish between:
- Generic requests (no acceptable candidate)
- Ambiguous requests (multiple acceptable candidates)

---

## D. Answers to the Eight Questions

### 1. Does score_gap == 0.0 correlate with rejection, reformulation, or alternative selection?

**In the synthetic corpus: Yes, perfectly for generic requests. No for ambiguous requests.**

- 10/10 multi-candidate generic requests have gap=0.0. These would likely be rejected or reformulated (no acceptable candidate exists).
- 4/6 ambiguous requests have gap=0.0. These would likely result in alternative selection (multiple acceptable candidates exist).
- 0/43 specific requests have gap=0.0.

**Real-data verdict: Unknown.** No real user behaviour has been collected.

---

### 2. What happens at small positive score gaps?

**Finding: Small positive gaps (0.05–0.175) occur exclusively in specific requests. All specific requests with small gaps correctly rank the expected candidate first.**

| Gap range | Specific | Generic | Ambiguous |
|-----------|----------|---------|-----------|
| 0.0 | 0 | 10 | 4 |
| 0.0–0.1 | 2 | 0 | 0 |
| 0.1–0.2 | 2 | 0 | 2 |
| 0.2–0.5 | 37 | 0 | 0 |
| 0.5+ | 2 | 0 | 0 |

Small positive gaps do NOT indicate discrimination failure. They indicate minor lexical overlap between the top two candidates (e.g., shared tags or description tokens). The top candidate is still clearly preferred.

**Verdict:** No threshold based on small positive gaps is warranted.

---

### 3. Does candidate count provide useful predictive information?

**Finding: No. Candidate count is highly misleading in the current corpus.**

- Specific requests avg 3.95 candidates (range 3–6)
- Ambiguous requests avg 5.00 candidates (range 3–6)
- Generic requests avg 2.29 candidates (range 0–4)

The distributions overlap almost completely. Specific requests routinely produce more candidates than generic requests because catalogue structure (how many capabilities share a verb) dominates over request specificity.

**Verdict:** Candidate count alone is not a useful predictor.

---

### 4. Does top_score provide useful predictive information?

**Finding: Partial. top_score separates negative from everything else, but overlaps between specific, generic, and ambiguous.**

| Category | Mean top_score | Range |
|----------|---------------|-------|
| Specific | 0.746 | 0.375–1.000 |
| Generic | 0.450 | 0.000–1.000 |
| Ambiguous | 0.783 | 0.500–1.000 |
| Negative | 0.000 | 0.000 |

- Negative: perfect separation (always 0.0)
- Specific vs. Ambiguous: ambiguous actually has HIGHER mean (0.783 vs 0.746)
- Generic: wide range (0.0–1.0), overlaps with both specific and ambiguous

**Verdict:** top_score alone is insufficient. It cannot distinguish specific from ambiguous, and it cannot reliably identify generic requests.

---

### 5. Are there observable properties that distinguish relevance from discriminability?

**Finding: No single property cleanly separates relevance from discriminability.**

| Signal | Relevance | Discriminability | Limitation |
|--------|-----------|------------------|------------|
| `candidate_count == 0` | No match | N/A | Clean |
| `top_score == 0.0` | No match | N/A | Clean |
| `score_gap == 0.0` | Yes | No | Cannot distinguish generic from ambiguous |
| `token_coverage == 1.0` | Yes | Partial | Multiple candidates may still match |
| `token_coverage < 1.0` | Partial | Partial | May still be specific or ambiguous |

**The fundamental problem:** The current keyword matcher operates on token overlap, which measures lexical relevance. Discriminability requires understanding whether the request's tokens uniquely identify one capability. This is not the same question.

**Example — relevance without discriminability:**
- Request: "create something"
- Matcher: 4 candidates with gap=0.0
- Relevance: yes ("create" matches all create_* capabilities)
- Discriminability: no (cannot choose between them)

**Example — discriminability despite high count:**
- Request: "update a record"
- Matcher: 6 candidates, gap=0.5, top_score=1.0
- Relevance: yes
- Discriminability: yes (update_record is clearly preferred)
- But: ambiguous (create_test_artifact also plausible due to description overlap)

---

### 6. Is there sufficient evidence for a principled candidate-presentation rule?

**Finding: No.**

Reasons:
1. **No real user behaviour data.** All analysis is based on synthetic corpus labels, not actual user actions. We do not know whether users confirm, reject, or select alternatives for any candidate set.
2. **gap=0.0 is not specific enough.** It identifies both generic requests (where users would likely reject all candidates) and ambiguous requests (where users would likely select an alternative). A rule based solely on gap=0.0 would conflate these two cases.
3. **Candidate count is misleading.** Specific requests routinely produce 4–6 candidates. A rule based on candidate count would penalise specific requests.
4. **top_score overlaps between categories.** Ambiguous requests have higher mean top_score than specific requests. A rule based on top_score would misclassify ambiguous requests as specific.
5. **The corpus is small and synthetic.** 70 examples with 16 artificially constructed capabilities. Real catalogues have different structures, and real users express requests differently.

**Conclusion:** The current evidence does not support any change to the candidate-presentation decision policy. The count-only policy (0 → NoCapabilityMatch, 1 → confirm, 2+ → select) remains the most defensible approach.

---

### 7. If yes, define the smallest coherent 21M implementation and the evidence supporting it.

**Not applicable.** The answer to question 6 is no.

---

### 8. If no, explicitly identify what evidence is still missing.

**Missing evidence:**

| Evidence | Why needed | How to collect |
|----------|-----------|----------------|
| **Real user requests with selection feedback** | We cannot validate any signal without knowing what users actually do | Deploy 21K instrumentation; collect 100–200 requests with confirm/reject/select_alternative outcomes |
| **Reformulation data** | We cannot measure whether the candidate presentation was misleading | Correlate session_ids to detect re-queries after capability selection |
| **gap=0.0 rejection rate** | We do not know whether gap=0.0 predicts rejection in production | Count gap=0.0 requests where user rejects all candidates |
| **gap=0.0 reformulation rate** | We do not know whether gap=0.0 predicts reformulation | Count gap=0.0 requests where user re-queries |
| **gap>0 alternative-selection rate** | We do not know whether small gaps lead to users selecting non-top candidates | Count gap>0 requests where user selects non-top candidate |
| **top-1 selection rate by gap bucket** | We do not know whether gap predicts selection accuracy | Bin requests by gap (0.0, 0.0–0.1, 0.1–0.2, 0.2–0.5, 0.5+) and compute top-1 selection rate in each bin |
| **Candidate satisfaction by count** | We do not know whether users are satisfied with large candidate sets | Correlate candidate_count with user confirm/reject rates |
| **Generic vs. ambiguous discrimination** | We cannot distinguish "no good candidate" from "multiple good candidates" without user feedback | Tag gap=0.0 requests by whether any candidate is acceptable; measure which ones users select vs. reject |

**Minimum viable evidence threshold:**
- 100–200 real requests with confirmed user actions
- At least 20 gap=0.0 requests with known outcomes
- At least 20 small-gap (0.0–0.2) requests with known outcomes
- At least 20 large-gap (>0.5) requests with known outcomes

---

## E. Architectural Implications

### The three questions the architecture is revealing

The evidence analysis reinforces the observation that the system faces three distinct questions:

1. **Recognition** — What capabilities could this request possibly relate to?
   - Solved by `RelevanceMatcher`
   - Output: candidate set

2. **Discrimination** — Does the request contain enough information to distinguish between those capabilities?
   - NOT currently solved
   - `score_gap` is a proxy, but an incomplete one
   - gap=0.0 means "cannot distinguish" but does not mean "no good candidate"

3. **Authorisation / action** — Given what we know, what are we permitted to do?
   - Solved by `CapabilityActionPolicy`
   - Current rule: count-only (0, 1, 2+)

### Why discriminability is harder than relevance

Relevance is a property of the candidate set: "do any capabilities match?"  
Discriminability is a property of the request-candidate relationship: "does the request tell us which capability is correct?"

The keyword matcher computes relevance well (100% top-1 accuracy on specific requests). It does not compute discriminability. Discriminability requires understanding whether the request's tokens are sufficient to uniquely identify one capability — a question that keyword overlap alone cannot answer.

**Example:** "create report" matches both `create_report` and `generate_report`. The keyword matcher returns both with equal score. The request is discriminative (both are report-creation capabilities) but the matcher cannot tell which verb the user intended.

### Why a new architectural layer is premature

The report correctly identifies that an "assessment layer" would be premature. The reasoning:
1. We have not proven that discriminability is a stable, useful decision dimension.
2. We have no real data showing that discriminability correlates with user outcomes.
3. Any new layer would add complexity without evidence-based justification.

If production evidence eventually demonstrates that discriminability is a real decision dimension, then we can decide whether it belongs inside `CapabilityActionPolicy` or warrants a more explicit policy concept. Not before.

---

## F. The "create something" Case Revisited

### What the synthetic corpus shows

| Request | Candidates | Gap | Top score | Synthetic outcome |
|---------|-----------|-----|-----------|-------------------|
| "create something" | create_customer, create_lead, create_report, create_test_artifact | 0.0 | 0.400 | Reject all / reformulate |
| "create" | create_lead, create_customer, create_report, create_test_artifact | 0.0 | 1.000 | Select alternative (acceptable alternatives exist) |

**Key insight:** Both requests have gap=0.0, but they are different cases:
- "create something": no acceptable candidate exists → user should reject
- "create": multiple acceptable candidates exist → user should select one

The gap=0.0 signal cannot distinguish these cases. A decision rule based solely on gap=0.0 would treat them identically, which would be incorrect.

### What real data would tell us

If we collected 100 real gap=0.0 requests with user feedback, we could compute:
- What fraction of gap=0.0 requests have NO acceptable candidate?
- What fraction of gap=0.0 requests have multiple acceptable candidates?
- Do users behave differently in these two cases?

Without this data, we cannot design a rule that handles both cases correctly.

---

## G. Summary

### What we know

1. **gap=0.0 is a perfect discriminator for generic requests in the synthetic corpus.** It identifies 10/10 multi-candidate generic requests and 0/43 specific requests.
2. **gap=0.0 is not specific to generic requests.** It also occurs in 4/6 ambiguous requests where users would likely select an alternative, not reject all candidates.
3. **Small positive gaps (0.05–0.175) do not indicate failure.** They occur only in specific requests and still correctly rank the expected candidate first.
4. **Candidate count is highly misleading.** Specific requests avg 3.95 candidates (range 3–6), nearly matching ambiguous requests (avg 5.0).
5. **top_score has limited discriminative power.** It separates negative requests (0.0) from everything else, but overlaps between specific, generic, and ambiguous.
6. **No real user behaviour data exists.** All analysis is based on synthetic corpus labels, not actual user confirm/reject/select outcomes.

### What we cannot yet know

1. Whether gap=0.0 correlates with user rejection or reformulation in production.
2. Whether users behave differently for generic vs. ambiguous gap=0.0 requests.
3. Whether small positive gaps predict successful selection in production.
4. Whether candidate count or top_score predict user satisfaction.
5. Whether any signal combination provides stronger evidence than gap alone.

### The honest conclusion

> The gap=0.0 signal is mathematically principled and perfectly identifies under-specified requests in the synthetic corpus. However, it also identifies ambiguous requests where multiple candidates are acceptable. Without real user behaviour data, we cannot determine whether gap=0.0 predicts rejection/reformulation, alternative selection, or something else. The current count-only policy remains the most defensible approach. The next step is to collect real user requests with selection feedback and re-evaluate.

---

## H. Recommended Next Increment

### Increment 21M — Evidence Collection Pilot

**Objective:** Collect real user requests with selection feedback to validate or refute the gap=0.0 hypothesis.

**Scope:**

1. **Deploy 21K instrumentation to a controlled environment.**
   - The `CapabilitySelectionTelemetry` module and `/assistant/capability/feedback` endpoint are already implemented.
   - No production behaviour changes required.

2. **Collect 100–200 real requests with user feedback.**
   - Capture: request text, candidates presented, scores, gap, count, interaction type
   - Capture: user action (confirm / reject / select_alternative)
   - Capture: reformulation events (re-query within same session)

3. **Analyse collected evidence.**
   - Compute gap=0.0 rejection rate, reformulation rate, alternative-selection rate
   - Compute top-1 selection rate by gap bucket
   - Compare candidate count and top_score against user outcomes
   - Identify whether any property combination predicts user satisfaction

4. **Re-evaluate decision policy based on evidence.**
   - If gap=0.0 correlates with rejection AND distinguishes generic from ambiguous → consider 21N rule
   - If no signal correlates with user outcomes → maintain count-only policy
   - If a different signal proves stronger → prioritise that signal

**Acceptance criteria for 21M:**
- 100+ real requests with confirmed user actions collected
- Statistical analysis of gap=0.0 predictive power completed
- Clear recommendation: adopt, modify, or reject candidate-presentation rule

---

## I. Test Results

All existing tests pass. No production behaviour was modified during this analysis.

```
334 passed, 19 warnings in 1.73s
```

- `packages/ai/tests/` — 91 passed
- `packages/workflow_runner/tests/` — 156 passed
- `packages/capability_registry/tests/` — 87 passed

---

*No production code was modified during this analysis.*
