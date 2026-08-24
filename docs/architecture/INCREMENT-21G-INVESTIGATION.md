# Increment 21G — Investigation: RelevanceMatcher Evaluation & Measurement

**Status:** Read-only investigation. No code changes.  
**Prerequisites:** Increments 21A–21F implemented. `CapabilityActionPolicy` is conservative. No autonomous execution. Relevance scores preserved but uncalibrated.

---

## A. Current Measurement Capabilities

### What the matcher produces today

`RelevanceMatcher.match()` returns `MatchResult`:

```python
class MatchResult(BaseModel):
    candidates: list[Capability]           # ranked by relevance
    confidence: float                      # top score (0.0–1.0)
    matcher_id: str                        # "relevance"
    rationale: str                         # human-readable explanation
    candidate_confidences: dict[str, float]  # per-capability scores
```

### What tests currently verify

| Test file | What it measures |
|-----------|-----------------|
| `test_relevance_matcher.py` (15 tests) | Basic behaviour: name matching, description matching, tag matching, deprecation exclusion, ranking, confidence range, stronger match produces higher confidence, rationale, empty catalogue, no match, matcher_id, deterministic ordering, candidate_confidences populated/aligned/excluded |
| `test_capability_matcher.py` (2 tests) | `HumanSelectionMatcher` returns all capabilities with confidence=0.0 |
| `test_capabilities.py` | Registry operations, maturation history, promotion — not matcher accuracy |

### What tests do NOT measure

- **Top-1 accuracy**: Does the highest-ranked candidate match the intended capability?
- **Top-k recall**: Does the correct capability appear anywhere in the top-k results?
- **No-match precision**: When the matcher returns no candidates, was that correct?
- **False-positive rate**: How often does the matcher return candidates when none are relevant?
- **Score distribution**: What scores does the matcher produce across representative requests?
- **Score-gap distribution**: How large is the gap between top and second candidate?
- **Failure modes**: Which request types produce wrong rankings?

### Current telemetry

| Signal | Captured? | Where |
|--------|-----------|-------|
| Which candidates were presented | Yes | `ChatResponse.capability_candidates` |
| Which candidate user selected | **No** | Not captured |
| Whether user confirmed or rejected | **No** | Not captured |
| Top-ranked candidate was selected | **No** | Not captured |
| Requests with no useful capability | Implicit | Falls through to `NoCapabilityMatch` → pattern execution, but not logged |
| Capabilities presented but rarely selected | **No** | Not captured |
| Interaction type (confirm/select) | Yes | `ChatResponse.telemetry["interaction"]` |
| Candidate count | Yes | `ChatResponse.telemetry["candidate_count"]` |
| Matcher ID | Yes | `ChatResponse.telemetry["matcher"]` (always `"human_selection"` — appears to be stale/incorrect) |

### Assessment

The system has **minimal measurement infrastructure**. The matcher is tested for basic correctness (it scores and ranks) but not for accuracy (does it rank the *right* capability first). There is no evaluation corpus, no ground-truth labels, and no mechanism to measure whether the matcher's top choice matches user intent.

---

## B. Existing Useful Test Fixtures

### Request→capability mappings already encoded in tests

The repository already contains implicit labelled examples:

**From `test_relevance_matcher.py`:**

| Request | Expected top candidate | Implicit label |
|---------|----------------------|----------------|
| `"create artifact"` | `create_test_artifact` | Yes |
| `"send email"` | `send_email` | Yes |
| `"analyse data"` | `analyse_data` | Yes |
| `"create test artifact"` | `create_test_artifact` | Yes |
| `"alpha beta"` | `alpha` then `beta` (ordered) | Yes |

**From `test_capabilities.py`:**

| Request | Expected | Notes |
|---------|----------|-------|
| `"enrich"` | `enrich` capability | Via `resolve()` |
| `"summarise"` | `summarise` capability | Via `resolve()` |

**From `test_assistant.py`:**

| Request | Expected candidate | Notes |
|---------|-------------------|-------|
| `"Create a test artifact"` | `create_test_artifact` | Single candidate in fixture |
| `"Do something"` | None (falls through) | No candidates |

### What is missing

- No explicit ground-truth mapping of `request_text → expected_capability_id`
- No "acceptable alternatives" list
- No ambiguous or edge-case examples
- No negative examples (requests that should produce no match)
- No coverage of generic requests like `"create something"` with expected weak/no match

### Reusability assessment

The existing test fixtures can be **reused as a seed corpus** without duplicating knowledge. Each `_capability()` helper + `matcher.match("request", ...)` call already encodes a labelled example. Extracting these into a structured corpus would be a data reorganization, not new work.

---

## C. Recommended Evaluation Corpus Structure

### Location

`packages/capability_registry/tests/fixtures/evaluation_corpus.json`

### Format

```json
{
  "capabilities": [
    {
      "id": "cap-create_test_artifact",
      "name": "create_test_artifact",
      "description": "Creates a test artifact record",
      "tags": ["test", "artifact"]
    }
  ],
  "examples": [
    {
      "request": "create a test artifact",
      "expected_capability_id": "cap-create_test_artifact",
      "acceptable_alternatives": [],
      "category": "specific",
      "notes": "Exact name match"
    },
    {
      "request": "create something",
      "expected_capability_id": null,
      "acceptable_alternatives": [],
      "category": "generic",
      "notes": "Too vague — should not confidently match any specific capability"
    },
    {
      "request": "send email notification",
      "expected_capability_id": "cap-send_email",
      "acceptable_alternatives": [],
      "category": "specific",
      "notes": "Name and description both match"
    }
  ]
}
```

### Why this format

- **JSON**: No new dependencies, human-readable, version-controllable
- **Separate `capabilities` section**: Allows the corpus to define the catalogue independently of the production registry. Tests can load this catalogue and run the matcher against it.
- **`expected_capability_id: null`**: Explicitly marks requests that should produce no match (negative examples)
- **`acceptable_alternatives`**: Supports cases where multiple capabilities could reasonably match (e.g., `"create"` could match `create_test_artifact` or `create_lead`)
- **`category`**: Enables stratified evaluation (specific vs generic vs ambiguous)
- **`notes`**: Documents the rationale for each example

### Why this location

- `packages/capability_registry/tests/fixtures/` is the natural home — the corpus is a test fixture for the People/Capability plane
- It travels with the matcher tests
- It does not pollute production code
- It can be loaded by both unit tests and evaluation scripts

---

## D. Recommended Minimum Metrics

### Tier 1 — Essential (implement now)

| Metric | Definition | What it tells us | How to compute |
|--------|-----------|-----------------|----------------|
| **Top-1 accuracy** | Fraction of examples where `candidates[0].id == expected_capability_id` | Does the matcher put the right capability first? | Count correct / total non-null examples |
| **Top-3 recall** | Fraction of examples where `expected_capability_id` appears in top 3 | Is the correct capability reachable even if not first? | Count present in top-3 / total non-null examples |
| **No-match precision** | Fraction of null-expectation requests that correctly return 0 candidates | Does the matcher avoid false positives on vague requests? | Count correct no-match / total null examples |
| **Candidate set size** | Average and distribution of `len(candidates)` | How many options does the user typically see? | Mean, median, max over all examples |

### Tier 2 — Useful (implement later)

| Metric | Definition | What it tells us | When to add |
|--------|-----------|-----------------|-------------|
| **Score distribution** | Histogram of `confidence` values across examples | Are scores spread meaningfully, or clustered at extremes? | After building corpus |
| **Score-gap distribution** | Histogram of `confidence - candidates[1].confidence` for multi-candidate cases | Are there natural breakpoints between dominant and ambiguous? | After building corpus |
| **Category-stratified accuracy** | Top-1 accuracy broken down by `category` (specific, generic, ambiguous) | Does the matcher perform differently on different request types? | After building corpus with categories |

### Tier 3 — Deferred

| Metric | Why deferred |
|--------|-------------|
| **Mean Reciprocal Rank (MRR)** | Requires ranking evaluation. Useful but complex. Top-1 and top-3 recall are sufficient for current needs. |
| **NDCG** | Overkill for binary correct/incorrect capability matching. |
| **False-positive rate** | Already covered by no-match precision for the current binary task. |
| **Execution success correlation** | Requires execution data, which is sparse. Defer until evidence is mature. |

---

## E. Current Scoring Weaknesses

### Ranked by likely impact and ease of validation

#### 1. Stop words dilute scores (HIGH impact, LOW complexity)

**Problem:** Common words like "the", "a", "an", "is", "of" are tokenised and included in the denominator of `_overlap()`, inflating the token count and reducing scores for otherwise good matches.

**Evidence:**
- `"send email"` → score 0.750
- `"send the email"` → score 0.500 (25% drop from one stop word)
- `"analyse data"` → score 0.900
- `"analyse the data"` → score 0.600 (33% drop)

**Fix type:** A. Objectively reasonable from matching semantics. Stop words carry no semantic content for capability matching.

#### 2. Token repetition dilutes scores (HIGH impact, LOW complexity)

**Problem:** Repeated tokens are counted multiple times in `request_tokens`, inflating the denominator of `_overlap()`.

**Evidence:**
- `"create test artifact"` → score 0.833
- `"create create create test artifact"` → score 0.700 (16% drop from repetition)

**Fix type:** A. Objectively reasonable. A token that appears 3 times should not count as 3 distinct query terms for keyword overlap.

#### 3. Singular/plural mismatch (MEDIUM impact, LOW complexity)

**Problem:** No stemming or plural handling. `"artifacts"` does not match `"artifact"`. `"emails"` does not match `"email"`.

**Evidence:**
- `"create test artifact"` → score 0.833
- `"create test artifacts"` → score 0.500 (40% drop)

**Fix type:** A. Objectively reasonable for English keyword matching. Plural forms are semantically equivalent to singular for capability lookup.

#### 4. Phrase matching is order-insensitive (LOW impact, MEDIUM complexity)

**Problem:** `"test artifact creation"` matches `create_test_artifact` at 0.667, same as `"create artifact test"` at 0.833. The algorithm treats all tokens as a bag, so word order doesn't matter. This is sometimes correct (flexible matching) and sometimes wrong (phrases like "send email notification" should match better when the phrase is preserved).

**Evidence:**
- `"create test artifact"` → 0.833
- `"test artifact creation"` → 0.667
- `"artifact test create"` → 0.833 (order irrelevant)

**Fix type:** B. Would require arbitrary weight tuning. Order-insensitive matching is a deliberate design choice (bag-of-words). Adding phrase weighting requires deciding phrase importance, which is a guess.

#### 5. Description dilution (LOW impact, MEDIUM complexity)

**Problem:** Description tokens are weighted at 30%, but a long description with many unmatched tokens dilutes the description score. For example, `"Creates a test artifact record"` has 5 tokens. If the request matches only 2 of them, the description score is 0.4, not 1.0.

**Evidence:**
- `"create test artifact"` against description `"Creates a test artifact record"`: 3/5 = 0.6 description score
- If description were shorter (`"Creates test artifact"`): 3/3 = 1.0 description score

**Fix type:** B. Changing description weighting would be a guess. The current 30% weight is arbitrary but defensible as a heuristic.

#### 6. Single-keyword requests produce perfect scores (MEDIUM impact, LOW complexity)

**Problem:** A single generic keyword like `"data"` produces a perfect score (1.0) for any capability containing `"data"` in any field. This is technically correct (100% of request tokens matched) but semantically misleading — the user's intent is unclear.

**Evidence:**
- `"data"` → 1.0 against `analyse_data` (tag match)
- `"email"` → 1.0 against `send_email` (name match)

**Fix type:** Cannot be fixed in the matcher alone. This is a property of the scoring model. The action policy already handles this correctly by requiring user confirmation for all single candidates.

---

## F. Scoring Improvements Without Calibration

### Implement now (objectively reasonable)

| Improvement | Impact | Complexity | Validation |
|-------------|--------|-----------|------------|
| **Stop-word filtering** | High | Low | Filter known English stop words before tokenisation. Validate that `"send the email"` scores identically to `"send email"`. |
| **Token deduplication** | High | Low | Deduplicate request tokens before scoring. Validate that `"create create test artifact"` scores identically to `"create test artifact"`. |

These two improvements are **objectively reasonable from the semantics of keyword matching**. A stop word is not a query term. A repeated token is not multiple distinct query terms. Both changes make the score more accurately reflect what the user actually specified, without introducing arbitrary weights or thresholds.

### Investigate later (require evidence)

| Improvement | Why later |
|-------------|-----------|
| Simple stemming (plural → singular) | Needs evaluation corpus to validate that it improves accuracy without creating false positives |
| Phrase matching | Needs evaluation corpus to determine whether phrase matches should outweigh token matches |
| Stop-word list tuning | Needs evaluation corpus to determine which words are stop words in the capability-matching domain |
| Weight re-tuning (0.5/0.3/0.2) | Currently arbitrary. Any change would be a guess without calibration data |

### Do not change

| Aspect | Why |
|--------|-----|
| Core scoring formula (weighted overlap) | Works correctly for what it is. Changes would be arbitrary. |
| Tokenisation method (`re.findall(r"[a-z0-9]+", ...)`) | Simple, deterministic, appropriate for current capability names. |
| Threshold for including candidates (`combined > 0.0`) | Correct: include anything with non-zero relevance. |
| Sorting by score descending | Correct: highest relevance first. |

---

## G. Telemetry Opportunities

### Currently captured

| Signal | Location | Format |
|--------|----------|--------|
| Candidate list | `ChatResponse.capability_candidates` | `list[dict[str, Any]]` with `id`, `name`, `description`, `kind`, `execution_mode`, `tags` |
| Interaction type | `ChatResponse.telemetry["interaction"]` | `"confirm"` or `"select"` |
| Candidate count | `ChatResponse.telemetry["candidate_count"]` | `int` |
| Matcher ID | `ChatResponse.telemetry["matcher"]` | `str` (currently hardcoded to `"human_selection"` — appears stale) |

### Missing but needed for measurement

| Signal | Why needed | Where to capture |
|--------|-----------|------------------|
| **User selection/confirmation result** | Which candidate did the user actually choose? Did they confirm or reject? | `AssistantChatService` when handling user response to `awaiting_capability_selection` |
| **Top-ranked candidate ID** | Was the matcher's first choice the user's choice? | Telemetry on the selection/confirmation response |
| **Request text** | Correlation: which requests produce good vs bad matches? | Already in `ChatRequest.message` — just needs to be logged alongside the response |
| **Matcher confidence** | What was the relevance score for the presented candidates? | Already on `CapabilityCandidate.confidence` — needs to be included in response telemetry |
| **Score gap** | How large was the separation between top candidates? | Computable from `candidate_confidences` — needs to be added to telemetry |
| **Execution outcome** | When a capability is executed, did it succeed? | Already captured by `InvocationRecorderAdapter` → `MaturationHistory` — but not correlated with matching decision |

### Smallest future instrumentation change

If telemetry enhancement is desired, the **smallest change** would be to enrich `ChatResponse.telemetry` when returning `awaiting_capability_selection`:

```python
telemetry={
    "recognition_level": frame.recognition_level.value,
    "matcher": "relevance",  # fix stale "human_selection"
    "candidate_count": len(candidates),
    "interaction": interaction,
    "top_score": candidates[0].confidence if candidates else 0.0,
    "score_gap": (candidates[0].confidence - candidates[1].confidence) 
                 if len(candidates) > 1 else 0.0,
}
```

This is a **response-model change only** — no new ports, no new services, no production behaviour change. It simply exposes information that already exists but is currently discarded.

**Do not implement this in 21G.** It is noted here as the smallest future instrumentation change if measurement becomes a priority.

---

## H. User-Feedback Signals

### What is NOT currently captured

| Signal | Consequence |
|--------|-------------|
| User selected a different candidate than the top-ranked one | Cannot measure top-1 accuracy in production |
| User rejected a single candidate (confirmed=False) | Cannot measure false-positive rate in production |
| User re-queried after seeing candidates | Cannot measure whether the initial match was useful |
| User explicitly chose "none of these" | Cannot measure no-match precision in production |
| User confirmed a single candidate | Cannot measure true-positive rate in production |

### Why this matters

Without user selection/rejection feedback, we cannot:
- Measure whether the matcher's ranking matches user intent
- Calibrate relevance scores against actual user behaviour
- Identify which request types produce misleading matches
- Determine whether the current "confirm" interaction is appropriate

### Smallest mechanism to capture it

The **smallest change** would be to extend the existing `execute_selected_capability()` endpoint or add a lightweight feedback endpoint that records:
- `capability_id` selected (or `null` for rejection)
- `request_text` or `session_id` for correlation
- `action`: `"confirm"`, `"reject"`, `"select_alternative"`

This would require:
- A new endpoint or extension of the existing chat resume mechanism
- Storage for the feedback (could be a simple log or ConceptStore record)
- No changes to matching or execution logic

**Do not implement this in 21G.** It is noted as the smallest mechanism for future feedback capture.

---

## I. Recommended Next Increment

### Increment 21G: RelevanceMatcher Evaluation Corpus

**Objective:** Make the RelevanceMatcher measurable by introducing a labelled evaluation corpus and baseline metrics, WITHOUT changing production behaviour.

**Scope:**

1. **Create evaluation corpus** at `packages/capability_registry/tests/fixtures/evaluation_corpus.json`
   - Define the capability catalogue used for evaluation
   - Include labelled examples: request → expected_capability_id
   - Include negative examples: requests that should produce no match
   - Include ambiguous examples: requests where multiple capabilities could match
   - Include categories: specific, generic, ambiguous

2. **Create evaluation test** at `packages/capability_registry/tests/test_relevance_matcher_evaluation.py`
   - Load corpus
   - Instantiate RelevanceMatcher
   - Run matcher against each example
   - Compute and assert Tier 1 metrics:
     - Top-1 accuracy
     - Top-3 recall
     - No-match precision
     - Candidate set size (mean/median)

3. **Seed corpus from existing tests**
   - Extract labelled examples from `test_relevance_matcher.py`
   - Add edge cases: stop words, singular/plural, generic requests, no-match cases

4. **No production changes**
   - No changes to `RelevanceMatcher`
   - No changes to `CapabilityActionPolicy`
   - No changes to contracts
   - No changes to chat response
   - No changes to telemetry

### What this enables

- **Baseline metrics:** We will know the current matcher's accuracy before making any changes
- **Regression detection:** Future matcher improvements can be measured against the corpus
- **Calibration data:** The corpus provides the labelled examples needed for future score calibration
- **Failure analysis:** We can identify which request types produce poor rankings

### What this does NOT do

- It does NOT change matcher behaviour
- It does NOT introduce thresholds
- It does NOT wire evidence into matching
- It does NOT change the action policy
- It does NOT expose scores to users

---

## J. Explicit Deferrals

| Item | Why Deferred |
|------|--------|
| **Score calibration** | Requires evaluation corpus first (21G), then statistical analysis. Not a single increment. |
| **Autonomous execution thresholds** | Requires calibrated scores + evidence. Deferred indefinitely. |
| **Evidence-informed matching** | Evidence is too sparse. Deferred until invocation volume is meaningful. |
| **Stop-word filtering** | A clear improvement but changes scoring behaviour. Should be implemented AFTER baseline metrics exist, so we can measure the improvement. |
| **Token deduplication** | Same — implement after baseline, so improvement is measurable. |
| **Stemming/lemmatisation** | Requires evaluation corpus to validate. Defer to later increment. |
| **User-feedback capture** | Requires new endpoint/storage. Defer until measurement priority is established. |
| **Telemetry enrichment** | Requires API contract change. Defer until measurement priority is established. |
| **Dominance/ambiguous/weak decision model** | Requires calibrated thresholds. Deferred (21F). |
| **LLM matching / embeddings / Qdrant** | Out of scope. |
| **Separate assessment layer** | Premature abstraction. |
| **Agent abstraction / orchestrator** | Architecture explicitly rejects (ADR-031, ADR-036, ADR-044). |

---

## K. Files Likely to Change

| File | Change |
|------|--------|
| `packages/capability_registry/tests/fixtures/evaluation_corpus.json` | **NEW** — labelled evaluation corpus |
| `packages/capability_registry/tests/test_relevance_matcher_evaluation.py` | **NEW** — evaluation tests computing Tier 1 metrics |

### What does NOT change

| File | Reason |
|------|--------|
| `packages/capability_registry/src/relevance_matcher.py` | No production changes |
| `packages/ai/src/capability_action.py` | No policy changes |
| `packages/ai/src/chat.py` | No response changes |
| `packages/contracts/capability_discovery.py` | No contract changes |

---

## L. Verification Plan

Because this is investigation-only, verification is:

1. **Confirm no production files are modified** — only new test files under `tests/`
2. **Confirm evaluation tests pass** — baseline metrics must be computable
3. **Confirm corpus is loadable and valid** — JSON must parse, all referenced capability IDs must exist in the corpus
4. **Confirm metrics are meaningful** — top-1 accuracy should be > 0% (matcher works for trivial cases), no-match precision should be 100% (negative examples should return no candidates)

---

## Summary

The current RelevanceMatcher is tested for basic correctness but not for accuracy. There is no evaluation corpus, no ground-truth labels, and no mechanism to measure whether the matcher ranks the right capability first. The simplest way to make the matcher measurable is to introduce a labelled evaluation corpus as a test fixture and compute baseline metrics (top-1 accuracy, top-3 recall, no-match precision, candidate set size). This requires no production code changes and enables future improvements to be measured objectively.

Two objectively reasonable scoring improvements (stop-word filtering and token deduplication) have been identified but should be implemented AFTER the baseline corpus exists, so their impact can be measured. The most important missing signal is user selection/rejection feedback, which would allow production measurement of matcher accuracy — but capturing that requires a new endpoint/storage mechanism and is deferred.

**The smallest coherent next increment is 21G: RelevanceMatcher Evaluation Corpus.** It creates the evidence required for the NEXT architectural decision (calibration, thresholds, or improved scoring) without changing any production behaviour.

---

## Implementation Status

**Completed:** Increment 21G implemented.

### Files Changed

| File | Action |
|------|--------|
| `packages/capability_registry/tests/fixtures/evaluation_corpus.json` | **NEW** — 5 capabilities, 18 labelled examples |
| `packages/capability_registry/tests/test_relevance_matcher_evaluation.py` | **NEW** — evaluation test computing baseline metrics |

### Corpus Breakdown

| Category | Count | Examples |
|----------|-------|---------|
| Specific | 9 | "create test artifact", "send email", "analyse data", etc. |
| Generic | 4 | "create something", "do something", "run something", "data" |
| Negative | 3 | "cook dinner", "write a novel", "design a building" |
| Ambiguous | 2 | "create", "send notification" |

### Actual Baseline Metrics

| Metric | Value |
|--------|-------|
| Top-1 accuracy | **100.00%** (12/12) |
| Top-3 recall | **100.00%** (12/12) |
| No-match precision | **50.00%** (3/6) |
| Average candidate set size | **1.44** |
| Median candidate set size | **1.0** |

### Notable Failure Modes

| Request | Category | Expected | Actual Top | Score | Count | Issue |
|---------|----------|----------|------------|-------|-------|-------|
| "create something" | generic | None | cap-create_lead | 0.400 | 2 | False positive: generic verb "create" matches two capabilities |
| "write a novel" | negative | None | cap-create_lead | 0.100 | 3 | False positive: unrelated request produces weak matches |
| "design a building" | negative | None | cap-create_lead | 0.100 | 3 | False positive: unrelated request produces weak matches |

### Key Findings from Baseline

1. **The matcher correctly ranks relevant capabilities first.** Top-1 accuracy is 100% for specific and ambiguous examples.
2. **The matcher has poor no-match precision (50%).** Generic and negative requests often produce weak but non-zero matches. This is because the scoring threshold is `combined > 0.0` — any token overlap produces a candidate.
3. **The current `CapabilityActionPolicy` mitigates this safety issue.** All matches require user confirmation, so weak false positives do not auto-execute.
4. **The most impactful improvements are stop-word filtering and token deduplication.** These are objectively reasonable changes that would reduce false positives without introducing arbitrary thresholds.

### Test Results

| Suite | Result |
|-------|--------|
| `packages/capability_registry/tests/test_relevance_matcher_evaluation.py` | **1 passed** |
| `packages/capability_registry/tests/test_relevance_matcher.py` | **15 passed** |
| `packages/ai/tests/test_capability_action.py` | **10 passed** |
| `packages/ai/tests/test_assistant.py` | **17 passed** |

### Next Increment Recommendation

**Increment 21H: Stop-Word Filtering and Token Deduplication.**

The baseline reveals that stop words and token repetition dilute scores and contribute to false positives. The smallest evidence-backed improvement is to:
1. Filter common English stop words before tokenisation
2. Deduplicate request tokens before scoring

These changes are:
- Objectively reasonable from keyword-matching semantics
- Low complexity
- Measurable against the 21G corpus
- Likely to improve no-match precision without changing the scoring formula

After implementing 21H, re-run the evaluation corpus to measure improvement.
