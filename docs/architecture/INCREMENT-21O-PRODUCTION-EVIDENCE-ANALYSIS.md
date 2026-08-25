# Increment 21O — Real Production Evidence Analysis

**Status:** Cannot complete — insufficient real-world data.  
**Prerequisites:** Increments 21K, 21L, 21M, 21N implemented.  
**Required:** 100+ real requests with actual user outcomes (confirm/reject/select_alternative).

---

## A. Current State

### Telemetry infrastructure readiness

The 21N production evidence collection infrastructure is fully deployed:

| Component | Status | Location |
|-----------|--------|----------|
| `CapabilitySelectionTelemetry` | Deployed | `packages/ai/src/capability_selection_telemetry.py` |
| File-based persistence | Deployed | `CAPABILITY_TELEMETRY_PATH` env var (default: `data/capability_selection_telemetry.jsonl`) |
| Session correlation | Deployed | `chat.py` propagates `session_id` to telemetry |
| Reformulation detection | Deployed | `get_reformulation_candidates()` method |
| Feedback endpoint | Deployed | `POST /assistant/capability/feedback` |
| Admin endpoints | Deployed | `/assistant/telemetry/events`, `/sessions/{id}`, `/reformulations`, `/stats`, `/export` |

### Data availability

**No real production telemetry data exists.**

- No `data/capability_selection_telemetry.jsonl` file found
- No telemetry export files found
- No production request logs with user outcomes

The only data available is:
1. **Synthetic corpus** (70 examples, 16 capabilities) — used in 21L/21M analysis
2. **Unit test fixtures** — mocked events, not real user behaviour

**Conclusion:** Increment 21O cannot be completed because its primary input (real production telemetry) does not yet exist.

---

## B. What 21O Would Analyse If Data Were Available

### Required dataset

| Requirement | Target | Current |
|-------------|--------|---------|
| Total requests with outcomes | 100–200 | 0 |
| gap=0.0 requests | ≥20 | 0 (real) |
| Small gap (0.0–0.2) requests | ≥20 | 0 (real) |
| Large gap (>0.5) requests | ≥20 | 0 (real) |
| Reformulation events | Natural occurrence | 0 (real) |
| select_alternative outcomes | Natural occurrence | 0 (real) |

### Analysis framework

If real data were available, 21O would compute:

#### 1. gap=0.0 predictive power

| Metric | Calculation |
|--------|-------------|
| gap=0.0 rejection rate | reject count / gap=0.0 total |
| gap=0.0 reformulation rate | reformulations with gap=0.0 / gap=0.0 total |
| gap=0.0 alternative-selection rate | select_alternative with gap=0.0 / gap=0.0 total |
| gap=0.0 confirm rate | confirm with gap=0.0 / gap=0.0 total |

#### 2. Score-gap bucket outcomes

| Bucket | Analysis |
|--------|----------|
| gap=0.0 | Primary hypothesis test |
| 0 < gap ≤ 0.1 | Discrimination failure? |
| 0.1 < gap ≤ 0.2 | Borderline cases |
| 0.2 < gap ≤ 0.5 | Normal operation |
| gap > 0.5 | Strong discrimination |

#### 3. top_score predictive power

| Bucket | Analysis |
|--------|----------|
| score = 0.0 | No match (expected 0 outcomes) |
| 0 < score ≤ 0.5 | Weak relevance — rejection rate? |
| 0.5 < score ≤ 0.75 | Moderate relevance — confirmation rate? |
| score > 0.75 | Strong relevance — confirmation rate? |

#### 4. candidate_count predictive power

| Count | Analysis |
|-------|----------|
| 1 | Confirm rate (should be high) |
| 2 | Confirm/reject split |
| 3 | Confirm/reject split |
| 4 | Confirm/reject split |
| ≥5 | Does large count cause rejection? |

#### 5. Reformulation analysis

| Metric | Calculation |
|--------|-------------|
| Overall reformulation rate | Sessions with 2+ events / total sessions |
| Reformulation by gap | gap=0.0 reformulation rate vs. gap>0 reformulation rate |
| Reformulation by count | Does high candidate count cause reformulation? |
| Time-to-reformulation | How quickly do users re-query after seeing candidates? |

#### 6. Selection accuracy

| Metric | Calculation |
|--------|-------------|
| Top-1 selection rate | User selects top candidate / total selections |
| Alternative selection rate | User selects non-top candidate / total selections |
| Rejection rate | User rejects all / total presentations |
| Confirm rate | User confirms single candidate / total confirms |

#### 7. Counterexample classification

| Counterexample | What it would look like |
|----------------|-------------------------|
| Specific request + gap=0.0 | A specific request where multiple candidates tie |
| Generic request + positive gap | A generic request where one candidate scores higher |
| gap=0.0 + accepted candidate | User confirms despite equal scores |
| Positive gap + rejected candidate | User rejects despite clear top candidate |
| Non-top candidate selected | User chooses candidate #2 or #3 |

---

## C. Why the Current Evidence Is Insufficient

### The synthetic corpus is not real user behaviour

The 21L/21M analysis used the Increment 21J evaluation corpus, which has critical limitations for evidence analysis:

1. **Labels are author-assigned, not user-derived.** `expected_capability_id` and `acceptable_alternatives` are corpus annotations, not observed user actions.
2. **No actual confirm/reject/select_alternative outcomes.** The 21M pilot derived outcomes from labels, simulating what users might do.
3. **No reformulation data.** The corpus has no multi-turn sessions.
4. **No select_alternative outcomes.** The corpus has no cases where users prefer non-top candidates.
5. **No negative outcomes for specific requests.** Every specific request in the corpus is "correct" — there are no cases where users confirm the wrong candidate.

### The synthetic corpus overstates reliability

| Issue | Synthetic corpus | Real production |
|-------|------------------|-----------------|
| User actions | Derived from labels | Actual user clicks/selections |
| Reformulations | None (single-turn) | Natural multi-turn conversations |
| Wrong confirmations | None (all correct) | Users may confirm incorrect candidates |
| Select_alternative | None | Users may prefer non-top candidates |
| Rejection reasons | Unknown | Users may reject for many reasons |

### What would constitute sufficient evidence

| Criterion | Requirement | Current |
|-----------|-------------|---------|
| Sample size | 100+ real requests | 0 |
| Outcome diversity | Confirm, reject, select_alternative all present | 0 real |
| Statistical power | Ability to detect medium effect sizes | Not calculable |
| Counterexamples | Systematic patterns, not noise | Cannot assess |
| Reformulation data | Multi-turn sessions with user re-queries | 0 |
| Cross-catalogue validation | Multiple capability catalogues | 1 synthetic |

---

## D. Honest Assessment

### Question: Is there sufficient evidence to justify a principled candidate-presentation rule?

**Answer: No.**

The evidence chain is:

1. **21J corpus** shows gap=0.0 perfectly identifies generic requests in a synthetic corpus.
2. **21L analysis** confirms this pattern but identifies ambiguous requests as a confound.
3. **21M pilot** simulates user outcomes from corpus labels — this is not real user behaviour.
4. **21N infrastructure** is deployed but has collected zero real production events.
5. **21O analysis** cannot proceed without real data.

### What remains unknown

| Unknown | Why it matters | How to resolve |
|---------|----------------|----------------|
| Does gap=0.0 predict real rejection? | Core hypothesis | Collect 100+ requests with feedback |
| Do users reformulate after gap=0.0? | Measures misleading presentation | Track multi-turn sessions |
| Do users select alternatives? | Measures matcher accuracy | Record select_alternative outcomes |
| Do specific requests ever produce gap=0.0? | Validates discriminability signal | Collect diverse real requests |
| Does top_score predict satisfaction? | Alternative signal | Correlate scores with outcomes |
| Does candidate count matter? | Current policy uses count | Compare count vs. outcomes |
| What is the reformulation rate? | Early indicator of problems | Monitor sessions over time |
| What is the top-1 selection rate? | Measures matcher accuracy | Record all user selections |

### Why we cannot extrapolate from synthetic evidence

The 21J corpus has properties that make it unsuitable as a proxy for real user behaviour:

1. **Capabilities are designed for clean lexical overlap.** Real capabilities have varied descriptions, tags, and naming conventions that may produce different gap distributions.

2. **Requests are author-written to test specific hypotheses.** Real users express needs in unpredictable ways, using domain jargon, abbreviations, and contextual references.

3. **No capability is "wrong" in the corpus.** Every candidate that matches is potentially correct. In production, users may have preferences that no capability satisfies.

4. **No session context.** Real users may reference prior requests, use pronouns ("that one"), or build on previous context. The corpus has no multi-turn examples.

5. **No failure modes.** The corpus has no cases where the matcher returns a candidate that looks plausible but is wrong. Real users may confirm incorrect candidates and only discover the error later.

---

## E. Recommended Action

### Continue evidence collection via 21N

The 21N infrastructure is ready. The next steps are:

1. **Deploy to production** — Set `CAPABILITY_TELEMETRY_PATH` and verify endpoints
2. **Collect naturally** — Let 100–200 real requests accumulate with actual user outcomes
3. **Monitor reformulations** — Use `/assistant/telemetry/reformulations` as an early indicator
4. **Export periodically** — Use `/assistant/telemetry/export` to checkpoint data
5. **Re-run 21O analysis** — Once the dataset reaches 100+ requests with outcomes

### Do not implement 21P yet

There is no evidence-based justification for any behaviour change. The current count-only policy remains the most defensible approach.

### What would trigger 21P

21P would be justified if ANY of the following are observed in real data:

1. **gap=0.0 rejection rate > 80%** with ≥20 gap=0.0 samples
2. **gap=0.0 + top_score < 0.5 rejection rate = 100%** with ≥10 samples
3. **Statistical significance** (p < 0.05) for any signal predicting user rejection
4. **Systematic counterexamples** to the current policy that cause demonstrable user harm

---

## F. Analysis Script for Future Use

When real data is available, the following script can be used to analyse telemetry:

```bash
# Export telemetry data
curl -X POST http://localhost:8000/assistant/telemetry/export \
  -H "Content-Type: application/json" \
  -d '{"output_path": "data/telemetry_analysis.json"}'

# Run analysis (script to be provided)
python packages/ai/src/analyse_telemetry.py data/telemetry_analysis.json
```

The analysis script would:
1. Load exported telemetry events
2. Filter to events with user_action populated
3. Compute outcome distributions by gap, score, count
4. Compute reformulation rates
5. Identify counterexamples
6. Perform statistical significance tests where sample sizes permit
7. Generate a report with evidence-based recommendations

---

## G. Test Results

All tests pass. No production behaviour was modified.

```
344 passed, 19 warnings in 1.96s
```

- `packages/ai/tests/` — 95 passed
- `packages/workflow_runner/tests/` — 156 passed
- `packages/capability_registry/tests/` — 93 passed

---

## H. Conclusion

**Increment 21O cannot be completed at this time.**

The 21N production evidence collection infrastructure is deployed and ready. However, no real production telemetry data exists yet. The synthetic corpus and 21M pilot provide suggestive but not conclusive evidence. Without real user behaviour data, any analysis would be speculative.

**Decision: Continue evidence collection.**

The path forward is:
1. Deploy 21N to production
2. Collect 100–200 real requests with user outcomes
3. Re-run 21O analysis with real data
4. If evidence is sufficient, define 21P with the smallest principled behaviour change
5. If evidence is insufficient, document what remains unknown and decide whether continued collection is warranted

**The default assumption remains: no behaviour change unless real evidence demonstrates one is warranted.**

---

*This document was produced without access to real production telemetry data. All conclusions are based on the current state of the codebase and the absence of collected evidence.*
