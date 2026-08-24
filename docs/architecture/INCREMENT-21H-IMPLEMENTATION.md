# Increment 21H — Implementation: Stop-Word Filtering and Token Deduplication

**Status:** Implemented.  
**Prerequisites:** Increments 21A–21G implemented. 21G evaluation corpus established baseline metrics.

---

## 1. Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `packages/capability_registry/src/relevance_matcher.py` | Modified | Added stop-word filtering and request-token deduplication |
| `packages/capability_registry/tests/test_relevance_matcher.py` | Modified | Added 8 new tests proving 21H behaviour |

No other production files, contracts, ports, services, or tests were modified.

---

## 2. Stop-Word Set

```python
_STOP_WORDS = frozenset(
    {
        "a", "an", "the",
        "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had",
        "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "must", "shall", "can",
        "to", "of", "in", "for", "on", "with", "as", "by", "at", "from",
        "through", "during", "before", "after", "above", "below", "between",
        "out", "off", "over", "under", "again", "further", "then", "once",
    }
)
```

### Rationale

- **Articles:** `a`, `an`, `the` — grammatically required but carry no capability semantics.
- **Auxiliary verbs:** `is`, `are`, `was`, `were`, `be`, `been`, `being`, `have`, `has`, `had`, `do`, `does`, `did`, `will`, `would`, `could`, `should`, `may`, `might`, `must`, `shall`, `can` — modal and tense markers. None of these appear in capability names, descriptions, or tags as content words.
- **Common prepositions/conjunctions:** `to`, `of`, `in`, `for`, `on`, `with`, `as`, `by`, `at`, `from`, `through`, `during`, `before`, `after`, `above`, `below`, `between`, `out`, `off`, `over`, `under`, `again`, `further`, `then`, `once` — relationship words that do not identify capabilities.

### Deliberately excluded

Words that could legitimately appear in capability metadata are NOT stop words:
- **Content verbs:** `create`, `send`, `analyse`, `generate`, `process`, `run`, `manage`, `update`, `delete`
- **Nouns:** `data`, `email`, `report`, `lead`, `artifact`, `test`, `notification`, `record`, `information`
- **Adjectives/adverbs:** `new`, `successfully`, `automatically`

---

## 3. Implementation Details

### Stop-word filtering

Applied **only** to request/query tokens inside `RelevanceMatcher._tokenise()`:

```python
@staticmethod
def _tokenise(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9]+", lowered)
    filtered = [token for token in tokens if token not in RelevanceMatcher._STOP_WORDS]
    return list(dict.fromkeys(filtered))
```

### Token deduplication

Also inside `_tokenise()`, using `dict.fromkeys()` to preserve insertion order while removing duplicates:

```python
return list(dict.fromkeys(filtered))
```

### What is NOT changed

- Capability metadata tokenisation (`capability.name`, `capability.description`, `capability.tags`) is unchanged.
- Scoring formula (`name_score * 0.5 + description_score * 0.3 + tag_score * 0.2`) is unchanged.
- Candidate inclusion threshold (`combined > 0.0`) is unchanged.
- Sorting/ranking logic is unchanged.
- `MatchResult` structure is unchanged.
- `CapabilityActionPolicy` is unchanged.
- All contracts and ports are unchanged.

---

## 4. Tests Added

| Test | Purpose |
|------|---------|
| `test_stop_words_are_filtered_from_request` | `"send the email"` and `"send email"` produce identical relevance scores |
| `test_stop_words_do_not_affect_ranking` | Stop-word removal does not change candidate ordering |
| `test_duplicate_request_tokens_do_not_change_score` | `"create create test artifact"` and `"create test artifact"` produce identical scores |
| `test_duplicate_request_tokens_do_not_change_ranking` | Token duplication does not change candidate ordering |
| `test_meaningful_capability_terms_are_not_stop_words` | Content words (`create`, `send`, `data`, `email`, etc.) are not in `_STOP_WORDS` |
| `test_matching_remains_deterministic` | Repeated runs with the same input produce identical results |
| `test_candidate_ordering_remains_deterministic` | Candidate ordering is stable across repeated runs |
| `test_specific_matches_remain_correctly_ranked` | Existing specific matches are still correctly ranked after normalisation |

---

## 5. Before/After Metrics

| Metric | 21G Baseline | 21H After | Change |
|--------|-------|-------|--------|
| Top-1 accuracy | 100.00% (12/12) | 100.00% (12/12) | No change |
| Top-3 recall | 100.00% (12/12) | 100.00% (12/12) | No change |
| No-match precision | 50.00% (3/6) | **83.33% (5/6)** | **+33.33%** |
| Average candidate set size | 1.44 | **1.06** | **-0.38** |
| Median candidate set size | 1.0 | 1.0 | No change |

### Requirement check

| Metric | Requirement | Result |
|--------|------------|--------|
| Top-1 accuracy | Must not decrease | **100% → 100%** ✓ |
| Top-3 recall | Must not decrease | **100% → 100%** ✓ |
| No-match precision | Should improve | **50% → 83.33%** ✓ |
| Avg candidate set size | Should not increase | **1.44 → 1.06** ✓ |
| Median candidate set size | Should not increase | **1.0 → 1.0** ✓ |

---

## 6. Before/After: Three Known False Positives

| Request | Category | 21G Top | 21G Score | 21G Count | 21H Top | 21H Score | 21H Count | Changed? |
|---------|----------|---------|-----------|-----------|---------|-----------|-----------|----------|
| `"create something"` | generic | cap-create_lead | 0.400 | 2 | cap-create_lead | 0.400 | 2 | **No** |
| `"write a novel"` | negative | cap-create_lead | 0.100 | 3 | — | — | **0** | **Yes — fixed** |
| `"design a building"` | negative | cap-create_lead | 0.100 | 3 | — | — | **0** | **Yes — fixed** |

### Analysis

- **`"write a novel"` and `"design a building"`** were caused by the stop word `"a"` matching the word `"a"` in capability descriptions. After stop-word filtering, the request tokens no longer overlap with any capability metadata, so these correctly return zero candidates.
- **`"create something"`** remains a false positive because `"create"` is a meaningful content word that legitimately matches two capabilities (`create_test_artifact` and `create_lead`). This is not a stop-word issue. The underlying problem is that `combined > 0.0` accepts any non-zero lexical overlap. As anticipated in the investigation, this requires a future decision-policy change, not a matcher change.

---

## 7. New or Changed Failure Modes

No new failure modes were introduced.

The only remaining failure mode is `"create something"`, which was already present in the 21G baseline. This failure mode demonstrates that:

1. Stop-word filtering and token deduplication improve signal quality where the problem is genuinely about semantically insignificant tokens.
2. They do NOT solve failures where a meaningful content word produces weak-but-non-zero overlap with multiple capabilities.
3. The remaining issue belongs to the decision layer (`CapabilityActionPolicy`), not the matcher.

---

## 8. Regression Test Results

| Suite | Result |
|-------|--------|
| `packages/capability_registry/tests/test_relevance_matcher.py` | **23 passed** (15 existing + 8 new) |
| `packages/capability_registry/tests/test_relevance_matcher_evaluation.py` | **1 passed** |
| `packages/capability_registry/tests/` (all) | **77 passed, 2 failed** (pre-existing `test_knowledge_bus.py` failures) |
| `packages/ai/tests/` | **55 passed** |
| `packages/workflow_runner/tests/` | **185 passed** |

### Architectural boundaries preserved

- **Matching** remains in People/Capability (`RelevanceMatcher`)
- **Decision** remains in AI (`CapabilityActionPolicy`)
- **Execution** remains in Operations (`CapabilityExecutionPort`)
- No new ports, services, abstractions, agents, or orchestrators introduced
- No changes to contracts, chat behaviour, telemetry, or user-feedback infrastructure

---

## 9. Next Increment Recommendation

The evidence from 21G + 21H points to one unresolved issue:

> `"create something"` produces a weak but non-zero match because a meaningful content word (`"create"`) overlaps with multiple capabilities. The `combined > 0.0` threshold accepts this as a valid candidate.

This is **not** a matcher problem. The matcher correctly reflects that the request contains a word present in multiple capability descriptions. It is a **decision-policy** problem: the system has no criterion to distinguish "weak generic overlap" from "strong specific match."

The next meaningful question is **not** "improve the matcher further." It is:

> **What is the smallest honest decision-policy change that can reduce spurious candidate presentations without introducing arbitrary thresholds?**

Possible directions to investigate (NOT implement yet):
- Minimum relevance criterion for single-candidate confirmation
- Request-specificity heuristic (token count, generic-vs-specific language)
- User-feedback capture to measure actual selection accuracy
- Calibration corpus expansion to cover more generic/ambiguous request patterns

**Recommended next step:** Investigation only. Do not implement thresholds or policy changes until there is evidence (from the evaluation corpus or real usage) that justifies a specific approach.

---

## 10. Explicit Deferrals

| Item | Why Deferred |
|------|--------|
| **Stemming/lemmatisation** | Requires evaluation corpus to validate. May change scores unpredictably. |
| **Phrase matching** | Requires evaluation corpus to determine whether phrases should outweigh tokens. |
| **Score calibration** | Requires larger corpus and labelled ground truth. |
| **Minimum relevance threshold** | Would be arbitrary without calibrated scores. The current `combined > 0.0` is honest about what the score means. |
| **Dominance/ambiguous/weak decision model** | Requires calibrated thresholds. Deferred from 21F. |
| **Evidence-informed matching** | Evidence is too sparse. Deferred until invocation volume is meaningful. |
| **User-feedback capture** | Requires new endpoint/storage. Deferred until measurement priority is established. |
| **Telemetry enrichment** | Requires API contract change. Deferred. |
| **LLM matching / embeddings / Qdrant** | Out of scope. |
| **Agent abstraction / orchestrator** | Architecture explicitly rejects. |
