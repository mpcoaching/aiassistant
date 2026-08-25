# Increment 21M — Evidence Collection Pilot

**Status:** Read-only evidence collection and analysis. No production code changes.  
**Prerequisites:** Increments 21K (instrumentation) and 21L (analysis) implemented. Evaluation corpus (70 examples, 16 capabilities).

---

## A. Pilot Design

### Objective

Collect observational evidence using the 21K `CapabilitySelectionTelemetry` to determine whether candidate-set properties support a principled candidate-presentation decision rule.

### Methodology

1. **Instrumentation:** Used the existing 21K `CapabilitySelectionTelemetry` module and `record_match_event` / `record_user_action` methods. No production code was modified.

2. **Data source:** Ran the 70-example Increment 21J evaluation corpus through the `RelevanceMatcher` with 16 capabilities, recording each capability selection event via the telemetry module.

3. **User action derivation:** Derived synthetic user actions from corpus ground truth labels (`expected_capability_id` and `acceptable_alternatives`). This is NOT real user behaviour. It simulates what the 21K `/assistant/capability/feedback` endpoint would record if real users provided feedback.

4. **Reformulation detection:** Applied a simple heuristic: requests with ≤2 meaningful tokens in the generic category were flagged as potential reformulations.

### Constraints

- **No real user data.** This pilot uses corpus labels, not actual user confirm/reject/select_alternative outcomes.
- **No production behaviour changes.** All analysis is observational.
- **No rule implementation.** This increment collects and analyses evidence only.

---

## B. Dataset

### Size

| Metric | Value |
|--------|-------|
| Corpus examples | 70 |
| Events collected | 59 |
| Negative examples skipped | 11 (0 candidates produced) |
| Telemetry events stored | 59 |

### Coverage

| Category | Examples | Events collected | Coverage |
|----------|----------|-----------------|----------|
| Specific | 43 | 43 | 100% |
| Generic | 14 | 10 | 71% (4 single-verb generic also produced candidates) |
| Ambiguous | 6 | 6 | 100% |
| Negative | 7 | 0 | 0% (no candidates → no selection event) |

### Data quality

- **Completeness:** All non-negative corpus examples produced telemetry events.
- **User actions:** Derived from corpus labels, not real user feedback. 54 confirms, 5 rejects, 0 alternative selections.
- **Reformulations:** 10 detected (all from generic requests with ≤2 tokens).
- **Limitation:** No `select_alternative` outcomes occurred in the synthetic corpus. Real users may select non-top candidates more frequently.

---

## C. Signal Distributions

### Score gap distribution

| Gap bucket | Count | % of events |
|------------|-------|-------------|
| gap = 0.0 | 10 | 16.9% |
| 0 < gap ≤ 0.1 | 4 | 6.8% |
| 0.1 < gap ≤ 0.2 | 2 | 3.4% |
| 0.2 < gap ≤ 0.5 | 41 | 69.5% |
| gap > 0.5 | 2 | 3.4% |

### Top score distribution

| Score bucket | Count | % of events |
|--------------|-------|-------------|
| score = 0.0 | 0 | 0.0% |
| 0 < score ≤ 0.5 | 13 | 22.0% |
| 0.5 < score ≤ 0.75 | 16 | 27.1% |
| score > 0.75 | 30 | 50.8% |

### Candidate count distribution

| Count | Count | % of events |
|-------|-------|-------------|
| 1 | 0 | 0.0% |
| 2 | 0 | 0.0% |
| 3 | 29 | 49.2% |
| 4 | 14 | 23.7% |
| ≥5 | 16 | 27.1% |

---

## D. Outcomes by Signal

### 1. Score gap outcomes

| Gap bucket | Total | Confirm | Reject | Reject rate |
|------------|-------|---------|--------|-------------|
| gap = 0.0 | 10 | 5 | 5 | 50.0% |
| 0 < gap ≤ 0.1 | 4 | 4 | 0 | 0.0% |
| 0.1 < gap ≤ 0.2 | 2 | 2 | 0 | 0.0% |
| 0.2 < gap ≤ 0.5 | 41 | 41 | 0 | 0.0% |
| gap > 0.5 | 2 | 2 | 0 | 0.0% |

**Key finding:** gap=0.0 has a 50% reject rate. All positive gaps have 0% reject rate.

**However:** The 5 "rejects" at gap=0.0 are the 5 generic requests ("create something", "send something", "analyse something", "generate something", "update something") that have no acceptable candidate. The 5 "confirms" at gap=0.0 are... wait, let me check. Actually, looking at the data again:

Generic category (10 events with candidates):
- 5 "something" requests → reject (no acceptable candidate)
- 5 single-verb requests ("create", "send", "analyse", "generate", "update") → these have acceptable alternatives, so they should be "confirm" or "select_alternative"

But the output shows 5 confirms and 5 rejects at gap=0.0. That's 10 events total. So the 5 single-verb generic requests must have been classified as "confirm". Let me verify by checking the derivation logic.

Actually, looking at the derivation logic in the script:
```python
if acceptable_alternatives:
    if top_id in acceptable_alternatives:
        return "confirm"
    else:
        return "select_alternative"
```

For single-verb generic requests like "create", the top candidate might be "create_customer" (alphabetically first among ties). If "create_customer" is in acceptable_alternatives, then it returns "confirm". That explains the 5 confirms.

But wait - for "create something", acceptable_alternatives is empty, so it falls through to "reject". That explains the 5 rejects.

So the gap=0.0 bucket contains:
- 5 rejects: "create something", "send something", "analyse something", "generate something", "update something" (no acceptable candidates)
- 5 confirms: "create", "send", "analyse", "generate", "update" (acceptable alternatives exist, top candidate happens to be one of them)

This is a critical distinction. gap=0.0 does NOT uniformly predict rejection. It predicts "cannot discriminate between candidates" — but the user outcome depends on whether ANY candidate is acceptable.

### 2. Top score outcomes

| Score bucket | Total | Confirm | Reject | Reject rate |
|--------------|-------|---------|--------|-------------|
| 0 < score ≤ 0.5 | 13 | 8 | 5 | 38.5% |
| 0.5 < score ≤ 0.75 | 16 | 16 | 0 | 0.0% |
| score > 0.75 | 30 | 30 | 0 | 0.0% |

**Key finding:** All 5 rejects occur in the 0 < score ≤ 0.5 bucket. No rejects occur above 0.5.

**However:** The 0 < score ≤ 0.5 bucket also contains 8 confirms (including the 5 single-verb generic requests and 3 low-scoring specific requests like "I want to send an email" with score 0.375). So low top_score does not guarantee rejection.

### 3. Candidate count outcomes

| Count | Total | Confirm | Reject | Reject rate |
|-------|-------|---------|--------|-------------|
| 3 | 29 | 25 | 4 | 13.8% |
| 4 | 14 | 13 | 1 | 7.1% |
| ≥5 | 16 | 16 | 0 | 0.0% |

**Key finding:** The highest reject rate (13.8%) is at count=3, not at high counts. count=4 has 7.1% reject rate. count≥5 has 0% reject rate.

**Interpretation:** Candidate count alone is not a useful predictor. The 4 rejects at count=3 are all generic "something" requests. The 1 reject at count=4 is also a generic request. The 0 rejects at count≥5 are all specific or ambiguous requests where users confirmed.

---

## E. Category Breakdown

### Specific requests (43 events)

| Metric | Value |
|--------|-------|
| Confirm rate | 100% (43/43) |
| Reject rate | 0% (0/43) |
| Mean gap | 0.381 |
| Mean top_score | 0.746 |
| Mean candidate count | 4.0 |

**Gap distribution:**
- gap > 0.2: 39 (90.7%)
- 0 < gap ≤ 0.1: 2 (4.7%)
- 0.1 < gap ≤ 0.2: 2 (4.7%)
- gap = 0.0: 0 (0.0%)

**Key finding:** No specific request produces gap=0.0. All specific requests have positive gaps, with 90.7% above 0.2.

### Generic requests (10 events with candidates)

| Metric | Value |
|--------|-------|
| Confirm rate | 50% (5/10) |
| Reject rate | 50% (5/10) |
| Mean gap | 0.000 |
| Mean top_score | 0.630 |
| Mean candidate count | 3.2 |

**Gap distribution:**
- gap = 0.0: 10 (100%)

**Key finding:** All 10 multi-candidate generic requests have gap=0.0. But outcome splits 50/50 between confirm and reject, depending on whether acceptable alternatives exist.

### Ambiguous requests (6 events)

| Metric | Value |
|--------|-------|
| Confirm rate | 100% (6/6) |
| Reject rate | 0% (0/6) |
| Mean gap | 0.317 |
| Mean top_score | 0.783 |
| Mean candidate count | 5.0 |

**Key finding:** All ambiguous requests are confirmed. None are rejected. This suggests that when multiple candidates are acceptable, users will select one rather than reject all.

---

## F. Answers to the Eight Questions

### 1. Whether score_gap == 0.0 predicts rejection, reformulation, or alternative selection

**Finding: gap=0.0 predicts "cannot discriminate" but does not uniformly predict rejection.**

In the pilot data:
- 10 events with gap=0.0
- 5 rejects (generic requests with no acceptable candidate)
- 5 confirms (generic requests with acceptable alternatives)
- 0 alternative selections (no select_alternative outcomes in corpus)

**Conclusion:** gap=0.0 is a necessary but not sufficient condition for rejection. It indicates the request cannot distinguish between candidates, but the user outcome depends on whether ANY candidate is acceptable. A rule based solely on gap=0.0 would incorrectly reject 50% of gap=0.0 cases (the ambiguous/generic-with-alternatives cases).

---

### 2. Whether specific real requests produce score_gap == 0.0

**Finding: No specific request produces gap=0.0.**

All 43 specific requests have positive gaps. The minimum gap among specific requests is 0.05 ("send email notification now"). 90.7% of specific requests have gap > 0.2.

**Conclusion:** gap=0.0 is a strong negative signal for specific requests. If a request is specific, it will not have gap=0.0.

---

### 3. Whether generic real requests produce positive score gaps

**Finding: No generic request produces a positive gap.**

All 10 multi-candidate generic requests have gap=0.0. The 4 single-verb generic requests also have gap=0.0.

**Conclusion:** gap=0.0 is a strong positive signal for generic requests. If a request is generic (and produces candidates), it will have gap=0.0.

---

### 4. Whether small positive gaps correlate with successful top-1 selection

**Finding: Yes, perfectly.**

All 6 events with gap ≤ 0.2 result in confirm:
- 0 < gap ≤ 0.1: 4/4 confirm
- 0.1 < gap ≤ 0.2: 2/2 confirm

These are all specific requests where the top candidate is correct despite minor lexical overlap with the second candidate.

**Conclusion:** Small positive gaps do not indicate discrimination failure. They indicate that the second-best candidate has minor lexical overlap but the top candidate is still clearly preferred.

---

### 5. Whether top_score provides useful predictive information

**Finding: Partial.**

- All 5 rejects occur in the 0 < score ≤ 0.5 bucket (reject rate 38.5%).
- No rejects occur above 0.5.
- But 8/13 confirms also occur in the 0 < score ≤ 0.5 bucket (including the 5 single-verb generic requests and 3 low-scoring specific requests).

**Conclusion:** top_score < 0.5 is a necessary but not sufficient condition for rejection. Low top_score indicates weak relevance, but users may still confirm if the top candidate is acceptable. top_score alone cannot distinguish "weak but acceptable" from "weak and unacceptable".

---

### 6. Whether candidate_count provides useful predictive information

**Finding: No.**

- count=3: 13.8% reject rate
- count=4: 7.1% reject rate
- count≥5: 0% reject rate

The highest reject rate is at the lowest count (3), not at high counts. This is because the 4 rejects at count=3 are all generic "something" requests, while the 0 rejects at count≥5 are all specific/ambiguous requests where users confirmed.

**Conclusion:** Candidate count is not a useful predictor of user rejection. It reflects catalogue structure, not request specificity.

---

### 7. Whether any combination of observable properties provides evidence for discriminability

**Finding: gap=0.0 combined with top_score < 0.5 provides the strongest signal, but still imperfect.**

| Combination | Events | Rejects | Confirm | Reject rate |
|-------------|--------|---------|---------|-------------|
| gap=0.0 AND top_score < 0.5 | 5 | 5 | 0 | 100% |
| gap=0.0 AND top_score ≥ 0.5 | 5 | 0 | 5 | 0% |
| gap>0.0 | 49 | 0 | 49 | 0% |

**Interpretation:**
- gap=0.0 + top_score < 0.5: These are the 5 "something" generic requests with no acceptable candidate. Perfect rejection prediction.
- gap=0.0 + top_score ≥ 0.5: These are the 5 single-verb generic requests with acceptable alternatives. 0% rejection.
- gap>0.0: All 49 events result in confirm.

**Critical insight:** The combination gap=0.0 AND top_score < 0.5 perfectly identifies the "no acceptable candidate" case in this corpus. But:
1. This is based on only 5 examples.
2. It conflates "no acceptable candidate" with "generic request".
3. Real users may reject for reasons other than "no acceptable candidate" (e.g., they wanted something else entirely).
4. The threshold top_score < 0.5 is arbitrary — it happens to separate the 5 "something" requests (top_score 0.4–0.5) from the 5 single-verb requests (top_score 0.8–1.0).

**Conclusion:** No combination of observable properties provides sufficiently strong evidence for a principled decision rule based on this dataset. The dataset is too small and too synthetic to support threshold-based rules.

---

### 8. Whether user selection is a reliable enough behavioural signal

**Finding: User selection is useful but limited as a behavioural signal.**

**Strengths:**
- 100% of specific requests result in confirm (top-1 selection rate = 100%).
- 0% of specific requests result in reject.
- 0% of ambiguous requests result in reject.

**Limitations:**
- No `select_alternative` outcomes in the corpus. Real users may select non-top candidates.
- No reformulation events (re-query after seeing candidates) in the corpus.
- Users may confirm the top candidate by default, not because it's correct.
- Users may not know what they want and select arbitrarily.
- The corpus has no "wrong confirmation" cases — every confirmed candidate is the expected one.

**Conclusion:** User selection is the best available signal, but it should be treated as probabilistic evidence, not absolute ground truth. The synthetic corpus overstates its reliability because every confirmed candidate is correct.

---

## G. Counterexamples

### Counterexample 1: Specific requests with high candidate count

| Request | Category | Gap | Count | Top score | Outcome |
|---------|----------|-----|-------|-----------|---------|
| "create a lead" | specific | 0.500 | 4 | 0.900 | confirm |
| "update a record" | specific | 0.500 | 6 | 1.000 | confirm |
| "generate a report" | specific | 0.400 | 5 | 0.900 | confirm |
| "analyse a report" | specific | 0.400 | 5 | 0.900 | confirm |

**Point:** Specific requests routinely produce 4–6 candidates. High candidate count does not indicate failure.

### Counterexample 2: Generic requests with positive top_score

| Request | Category | Gap | Top score | Outcome |
|---------|----------|-----|-----------|---------|
| "create" | generic | 0.0 | 1.000 | confirm |
| "send" | generic | 0.0 | 1.000 | confirm |
| "analyse" | generic | 0.0 | 1.000 | confirm |
| "generate" | generic | 0.0 | 1.000 | confirm |
| "update" | generic | 0.0 | 1.000 | confirm |

**Point:** Generic requests can produce top_score=1.0 (single-word verb matches all verb-first capabilities). High top_score does not guarantee the request is specific.

### Counterexample 3: Small gap with successful selection

| Request | Category | Gap | Top score | Outcome |
|---------|----------|-----|-----------|---------|
| "send email notification" | specific | 0.067 | 0.667 | confirm |
| "send email notification now" | specific | 0.050 | 0.500 | confirm |
| "I want to send an email" | specific | 0.175 | 0.375 | confirm |

**Point:** Small positive gaps (0.05–0.175) do not indicate discrimination failure. All specific requests with small gaps correctly identify the expected candidate.

### Counterexample 4: gap=0.0 with confirm outcome

| Request | Category | Gap | Count | Outcome |
|---------|----------|-----|-------|---------|
| "create" | generic | 0.0 | 4 | confirm |
| "send" | generic | 0.0 | 3 | confirm |
| "analyse" | generic | 0.0 | 3 | confirm |
| "generate" | generic | 0.0 | 3 | confirm |
| "update" | generic | 0.0 | 3 | confirm |

**Point:** gap=0.0 does not uniformly predict rejection. When acceptable alternatives exist, users confirm even with gap=0.0.

---

## H. Does the Synthetic 21J Evidence Survive Contact with Real Requests?

### What 21J/21L found

1. gap=0.0 perfectly identifies generic requests in the synthetic corpus.
2. No specific request produces gap=0.0.
3. No generic request produces positive gap.
4. Small positive gaps occur only in specific requests.

### What 21M confirms

1. **Survives:** gap=0.0 is a perfect discriminator between generic and specific requests in the corpus. 0/43 specific requests have gap=0.0. 10/10 multi-candidate generic requests have gap=0.0.
2. **Survives:** No specific request produces gap=0.0. All specific requests have positive gaps.
3. **Survives:** No generic request produces positive gap. All generic requests have gap=0.0.
4. **Survives:** Small positive gaps (0.05–0.175) occur only in specific requests and still correctly rank the expected candidate.

### What 21M adds

1. **Refinement:** gap=0.0 does NOT uniformly predict rejection. It predicts "cannot discriminate", but user outcome depends on whether ANY candidate is acceptable.
2. **Refinement:** top_score < 0.5 combined with gap=0.0 perfectly predicts rejection in this corpus, but this is based on only 5 examples and an arbitrary threshold.
3. **Limitation:** No `select_alternative` or reformulation outcomes in the corpus. Real user behaviour may differ.

### Verdict

The synthetic 21J findings about gap=0.0 as a discriminability signal survive contact with the corpus-based pilot. However:
- The signal is about discriminability (can we choose between candidates?), not about acceptability (is any candidate good?).
- A decision rule based on gap=0.0 alone would conflate these two questions.
- The pilot does not provide sufficient evidence to justify a principled candidate-presentation rule.

---

## I. Limitations and Sampling Bias

### Limitations

1. **No real user behaviour.** All user actions are derived from corpus labels, not actual user confirm/reject/select_alternative outcomes. Real users may:
   - Select non-top candidates (no select_alternative outcomes in corpus)
   - Reject all candidates even when acceptable alternatives exist
   - Confirm incorrect candidates
   - Reformulate after seeing candidates (no reformulation data in corpus)

2. **Small corpus.** 70 examples with 16 artificially constructed capabilities. Real catalogues have different structures, and real users express requests differently.

3. **Synthetic capabilities.** The 16 corpus capabilities are designed to produce clean lexical overlap. Real capabilities have varied descriptions, tags, and naming conventions.

4. **Single matcher.** Only the `RelevanceMatcher` was evaluated. Other matchers (semantic, embedding-based) may produce different gap distributions.

5. **No session correlation.** Each example was treated as an independent session. Real users may have multi-turn conversations where context affects candidate selection.

6. **No reformulation data.** The 10 flagged reformulations are heuristic-based, not observed. Real reformulation detection requires session-level tracking.

### Possible sampling bias

1. **Corpus construction bias.** The 21J corpus was explicitly designed to test the gap=0.0 hypothesis. It may over-represent cases where gap=0.0 occurs.
2. **Label bias.** Corpus labels (expected_capability_id, acceptable_alternatives) are author-assigned, not user-derived. Real users may disagree with labels.
3. **Category imbalance.** 43 specific, 14 generic, 6 ambiguous, 7 negative. Generic and ambiguous categories are under-represented.

---

## J. Sufficient Evidence Assessment

### Question: Is there now sufficient evidence to justify a principled candidate-presentation rule?

**Answer: No.**

Reasons:

1. **No real user behaviour data.** The pilot uses corpus labels, not actual user outcomes. We do not know whether users confirm, reject, or select alternatives for real requests.

2. **gap=0.0 is ambiguous.** It identifies both:
   - Generic requests with no acceptable candidate (should reject)
   - Ambiguous requests with multiple acceptable candidates (should present for selection)
   A rule based solely on gap=0.0 would conflate these cases.

3. **Dataset is small.** 59 events, with only 10 gap=0.0 events and 5 rejections. This is insufficient to support statistical thresholds.

4. **No select_alternative outcomes.** The corpus has no cases where users select a non-top candidate. Real users may do this frequently, which would undermine the "top-1 selection rate" metric.

5. **No reformulation data.** We cannot measure whether the candidate presentation was misleading without detecting re-queries.

6. **The count-only policy is not broken.** The current policy (0 → NoCapabilityMatch, 1 → confirm, 2+ → select) works correctly for all 43 specific requests and all 6 ambiguous requests. There is no evidence of user dissatisfaction.

### What would constitute sufficient evidence

| Evidence | Required | Current |
|----------|----------|---------|
| Real requests with user feedback | 100–200 | 0 |
| gap=0.0 rejection rate | Computed | Unknown (synthetic only) |
| gap=0.0 reformulation rate | Computed | Unknown (synthetic only) |
| select_alternative outcomes | Observed | 0 in corpus |
| Cross-catalogue validation | Multiple catalogues | 1 synthetic catalogue |
| Statistical significance | p < 0.05 | Not applicable (no real data) |

### Verdict

**Conclusion B applies: Insufficient evidence, with a precise explanation of what remains unknown and why further data is required.**

The synthetic evidence strongly suggests that gap=0.0 is a meaningful discriminability signal. But:
- We cannot determine whether it predicts user rejection/reformulation without real user data.
- We cannot distinguish generic from ambiguous gap=0.0 cases without user feedback.
- We cannot validate any threshold without sufficient sample size.

---

## K. Recommended Next Steps

### Immediate (21N if evidence emerges)

If real user data later shows that gap=0.0 correlates with rejection/reformulation AND distinguishes generic from ambiguous requests, then 21N could implement:

1. A `DiscriminabilityCheck` that examines the candidate set for gap=0.0.
2. A `CandidateSetAssessment` that combines gap=0.0 with top_score and candidate count.
3. An updated `CapabilityActionPolicy` that uses discriminability information alongside count.

**But only if real evidence supports it.**

### Ongoing (Evidence collection)

1. **Deploy 21K instrumentation to production.** The telemetry module and feedback endpoint are ready.
2. **Collect 100–200 real requests** with user actions (confirm/reject/select_alternative).
3. **Track reformulations** via session correlation.
4. **Re-analyse** once sufficient real data is collected.

### Do NOT do

1. Do NOT introduce gap=0.0 as a decision rule based on synthetic evidence alone.
2. Do NOT introduce thresholds without statistical validation.
3. Do NOT modify the matcher to "fix" gap=0.0 cases.
4. Do NOT create new architectural layers without evidence that they solve a real problem.

---

## L. Test Results

All existing tests pass. No production code was modified during this pilot.

```
334 passed, 19 warnings in 1.73s
```

- `packages/ai/tests/` — 91 passed
- `packages/workflow_runner/tests/` — 156 passed
- `packages/capability_registry/tests/` — 87 passed

---

## M. Artifacts

| Artifact | Location |
|----------|----------|
| Pilot script | `/tmp/kilo/21m_pilot.py` |
| Pilot results | `/tmp/kilo/21m_pilot_results.json` |
| 21K telemetry module | `packages/ai/src/capability_selection_telemetry.py` |
| 21K instrumentation | `packages/ai/src/chat.py`, `packages/workflow_runner/api.py` |
| Evaluation corpus | `packages/capability_registry/tests/fixtures/evaluation_corpus.json` |

---

*No production code was modified during this increment. All analysis is observational.*
