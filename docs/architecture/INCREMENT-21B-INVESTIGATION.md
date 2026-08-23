# Increment 21B — Investigation: RelevanceMatcher and the Matching → Assessment → Action Pipeline

**Status:** Read-only investigation. No code changes.  
**Prerequisite:** Increment 21A implemented (`CapabilityActionPolicy` extracted).

---

## A. Current State: The Actual Pipeline After 21A

```
User message (HTTP POST /assistant/chat)
    │
    ▼
AssistantChatService.chat()                           [packages/ai/src/chat.py:91]
    │
    ├─► Intent(id, origin=USER_REQUEST, raw={text})   [packages/ai/src/intent.py:34]
    │
    ├─► recognise(intent) → ProblemFrame               [packages/ai/src/intent.py:70]
    │   └─► Rule-based keyword classification
    │       confidence, recognition_level, ContextRecord
    │
    ├─► IF enterprise_information configured:
    │   └─► find_previous_solutions(strategy_tag)
    │       └─► RETURN awaiting_confirmation (if found)
    │
    ├─► IF capability_discovery configured:
    │   ├─► find_capabilities(request_text, frame.context)
    │   │   │                                       [packages/contracts/capability_discovery.py:14]
    │   │   │
    │   │   └─► CapabilityDiscoveryAdapter            [capability_registry/.../adapters/capability_discovery_adapter.py:27]
    │   │       ├─► registry.list() → ALL Capabilities
    │   │       ├─► matcher.match(request_text, ctx, capabilities)
    │   │       │   └─► HumanSelectionMatcher          [capability_registry/.../capability_matcher.py:40]
    │   │       │       └─► MatchResult(
    │   │       │           candidates=ALL capabilities,
    │   │       │           confidence=0.0,
    │   │       │           matcher_id="human_selection",
    │   │       │           rationale="Human selection required...")
    │   │       │
    │   │       └─► [_to_candidate(cap) for cap in match_result.candidates]
    │   │           └─► CapabilityCandidate[]  ← NOTE: confidence and rationale DROPPED HERE
    │   │
    │   ├─► CapabilityActionPolicy.decide(candidates)  [packages/ai/src/capability_action.py:39]
    │   │   ├─► 0 candidates → NoCapabilityMatch → fall through
    │   │   ├─► 1 candidate  → ExecuteCapability → execute via port
    │   │   └─► 2+ candidates → AskUserToSelect → awaiting_capability_selection
    │   │
    │   └─► (dispatch to execute or selection response)
    │
    ├─► IF no capability match:
    │   ├─► reasoning_service.decide(intent) → StrategyDecision
    │   ├─► SessionFactoryPort.create_session()
    │   ├─► PatternExecutionPort.execute_pattern()
    │   └─► RETURN completed/pending
    │
    └─► (fallback)
```

**Critical observation:** The `CapabilityDiscoveryAdapter.find_capabilities()` method currently returns `list[CapabilityCandidate]`. It calls `matcher.match()` which produces a `MatchResult` containing `confidence` and `rationale`, but those fields are **silently discarded** during the adapter's `_to_candidate()` conversion. The AI plane never sees confidence or rationale today.

---

## B. Responsibility Map

| Responsibility | Current Owner | Correct Owner | Evidence |
|----------------|--------------|---------------|----------|
| **Matching** (which capabilities are relevant?) | `CapabilityMatcher` in `capability_registry` | People/Capability | `capability_matcher.py:28` protocol; ADR-020 |
| **Ranking** (ordering candidates by quality) | `HumanSelectionMatcher` returns all in arbitrary order | People/Capability (or matcher implementation) | `HumanSelectionMatcher.match()` returns `list(capabilities)` — no ordering |
| **Confidence scoring** (how relevant is each candidate?) | `MatchResult.confidence` exists but is DROPPED by adapter | People/Capability produces it; AI plane should consume it | `MatchResult.confidence` in protocol; `find_capabilities()` returns flat list without confidence |
| **Action selection** (execute / ask / clarify) | `CapabilityActionPolicy` in AI plane | AI plane | `capability_action.py:39` — correctly extracted in 21A |
| **Execution** | `CapabilityExecutionPort` → Operations | Operations | `capability_execution.py:11`; adapter in `workflow_runner` |
| **Evidence collection** (invocation/correction counts) | `InvocationRecorderAdapter` → `ConceptStore.record_invocation()` | Operations records; Enterprise stores; People/Capability owns | `invocation_recorder_adapter.py:28`; `concepts.py:109` |
| **Evidence access** (can matcher read maturation history?) | `Capability.payload` contains `maturation_history` but matcher does NOT read it | People/Capability should expose it via matcher | `Capability.payload` is a dict; `ConceptStoreCapabilityRepository._concept_to_capability()` preserves payload |
| **Outcome assessment** | `CapabilityOutcomeAssessorAdapter` | Operations | Separate adapter; assesses execution results |

---

## C. Architectural Decision: What Should Increment 21B Actually Introduce?

### What Increment 21B Must Introduce

**A new `RelevanceMatcher` implementation of `CapabilityMatcher` that produces meaningful confidence scores.**

That is the entire scope. Nothing more.

### What Increment 21B Must NOT Introduce

- No changes to `CapabilityDiscoveryPort` contract
- No changes to `CapabilityCandidate` model
- No changes to `CapabilityActionPolicy`
- No confidence thresholds in action policy
- No execution behaviour changes
- No new ports
- No evidence-based scoring (deferred — see §G)

### Why This Scope

The `CapabilityMatcher` protocol already defines the right interface:

```python
class MatchResult(BaseModel):
    candidates: list[Capability]
    confidence: float
    matcher_id: str
    rationale: str
```

The `CapabilityDiscoveryAdapter` already calls `matcher.match()`. The gap is that the current implementation (`HumanSelectionMatcher`) always returns `confidence=0.0` and all candidates. Replacing it with a matcher that produces real confidence scores is the smallest possible improvement.

The confidence score produced by the matcher is **matching confidence** — "how well does this capability match the user's request?" It is NOT execution safety, NOT intent understanding, NOT a selection threshold. It is a pure relevance signal.

### Where Confidence Lives

Confidence belongs to **matching**, not to action policy. The matcher answers "how well does this match?" The action policy answers "what should we do given these candidates?" These are separate questions.

The current architecture almost gets this right: `MatchResult` has `confidence`. The bug is that the adapter drops it. Increment 21B should:

1. Make `RelevanceMatcher` produce real confidence values
2. Preserve confidence through the adapter into `CapabilityCandidate` (or at least make it available)

### Where Confidence Should Eventually Go

`CapabilityCandidate` currently has no confidence field. The cleanest path is:

- **Short term (21B):** `RelevanceMatcher` produces `MatchResult.confidence`. The adapter can include it in `CapabilityCandidate` via the existing `execution_mode` field's flexibility, OR we accept that confidence is only visible through the matcher's internal `MatchResult` for now.
- **Medium term:** Add `confidence: float` to `CapabilityCandidate` in `packages/contracts/capability_discovery.py`. This is a contract change but a minimal one.
- **Long term:** `CapabilityActionPolicy.decide()` can accept confidence information when making decisions.

But for 21B, the contract change is NOT required. The matcher improvement is valuable even if the confidence only lives in `MatchResult` — it proves the architectural boundary and gives us a replacement for `HumanSelectionMatcher`.

---

## D. Recommended Data Flow

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
    │   └─► RelevanceMatcher (NEW)
    │       ├─► Keyword relevance: name, description, tags
    │       ├─► Status filter: prefer ACTIVE
    │       └─► MatchResult(candidates=ranked, confidence=score, rationale=...)
    │
    └─► CapabilityCandidate[]  (confidence currently dropped — future: preserve)
    │
    ▼
CapabilityActionPolicy.decide(candidates)
    │
    ├─► 0 candidates → NoCapabilityMatch → fall through to pattern execution
    ├─► 1 candidate  → ExecuteCapability → CapabilityExecutionPort.execute()
    └─► 2+ candidates → AskUserToSelect → awaiting_capability_selection
```

**Stages that exist NOW:**
- Intent/ProblemFrame: ✅ exists
- Discovery: ✅ exists
- Matching: ✅ exists (stub)
- Action policy: ✅ exists (21A)
- Execution: ✅ exists

**Stages that do NOT need to exist yet:**
- Assessment/ranking as a separate stage: NOT needed — ranking is part of matching
- Confidence thresholds: NOT needed — action policy remains count-based
- Evidence-informed matching: deferred (see §G)

---

## E. Smallest Coherent Implementation

### What to Build

**One file: `packages/capability_registry/src/relevance_matcher.py`**

```python
class RelevanceMatcher:
    """Deterministic keyword-based capability matcher.
    
    Replaces HumanSelectionMatcher with a matcher that scores candidates
    by keyword relevance to the request text and returns ranked results
    with confidence scores.
    """
    
    matcher_id = "relevance"
    
    def match(self, request_text, context, capabilities):
        # 1. Filter: exclude DEPRECATED
        # 2. Score: keyword overlap on name, description, tags
        # 3. Sort: descending by score
        # 4. Return: MatchResult with confidence and rationale
```

### What Not to Touch

- `CapabilityDiscoveryPort` — no change
- `CapabilityCandidate` — no change (confidence stays in MatchResult for now)
- `CapabilityActionPolicy` — no change
- `chat.py` — no change
- No new contracts, no new ports

### Why This Is the Smallest Useful Implementation

1. **Proves the boundary:** Matching stays in People/Capability. The matcher is a drop-in replacement for `HumanSelectionMatcher`.
2. **Materially improves UX:** Instead of showing ALL capabilities, the user sees ranked, relevant ones.
3. **Zero infrastructure:** Uses existing metadata (name, description, tags, status). No embeddings, no LLM, no new stores.
4. **Establishes the pattern:** `MatchResult.confidence` is now meaningful. Future matchers (semantic, LLM) can replace the implementation without changing the interface.
5. **Preserves behaviour:** The adapter still returns `CapabilityCandidate[]`. The action policy still uses count-based decisions. Nothing downstream changes.

---

## F. Tests

### New Tests Required

| Test | Purpose |
|------|---------|
| `test_relevance_matcher_scores_by_name` | Request "create artifact" matches capability with "create" in name |
| `test_relevance_matcher_scores_by_description` | Request "send email" matches capability whose description contains "email" |
| `test_relevance_matcher_scores_by_tag` | Request "analyse data" matches capability with "data" or "analysis" tag |
| `test_relevance_matcher_filters_deprecated` | DEPRECATED capabilities are excluded or heavily penalised |
| `test_relevance_matcher_ranks_by_score` | Higher keyword overlap → higher confidence |
| `test_relevance_matcher_returns_confidence` | Confidence is between 0.0 and 1.0 |
| `test_relevance_matcher_returns_rationale` | Rationale explains the match |
| `test_relevance_matcher_handles_empty_catalog` | Returns empty candidates |
| `test_relevance_matcher_handles_no_match` | Weak match returns low confidence |
| `test_relevance_matcher_matcher_id` | `matcher_id == "relevance"` |

### Existing Tests That Must Still Pass

| Test Suite | Count | Status Required |
|------------|-------|-----------------|
| `ai/tests/test_capability_action.py` | 5 | All pass |
| `ai/tests/test_assistant.py` | 18 | All pass |
| `ai/tests/test_architectural_boundaries.py` | 12 | All pass |
| `workflow_runner/tests/` | 185 | All pass |
| `capability_registry/tests/test_capability_matcher.py` | 4 | All pass (HumanSelectionMatcher unchanged) |

### Integration Test to Add

| Test | Purpose |
|------|---------|
| `test_discovery_adapter_with_relevance_matcher` | Verify adapter works with new matcher; candidates are returned (confidence is dropped — document this) |

---

## G. Explicitly Deferred Work

| Item | Reason |
|------|--------|
| **Evidence-informed matching** | `MaturationHistory` exists but data is sparse. Using it now would create a fake learning loop. Defer until evidence is mature. |
| **Confidence thresholds in action policy** | `CapabilityActionPolicy` should remain count-based. Confidence-driven decisions (auto-execute ≥0.8, ask 0.5-0.8) come later. |
| **Confidence field in `CapabilityCandidate`** | Contract change. Defer to a subsequent increment that needs it. |
| **Semantic/embedding matching** | Requires embedding model + Qdrant for capabilities. Too heavy. |
| **LLM-assisted matching** | Requires LLM integration, costs, latency. Future enhancement. |
| **Capability gap detection** | Useful but doesn't help when capabilities exist but aren't matched. |
| **Skill registration as capabilities** | Increases catalog size but doesn't improve matching. |
| **Conversational memory** | Explicitly deferred. |
| **Agent abstraction** | Architecture explicitly rejects universal orchestrator. |
| **Paperclip integration** | ADR-005 explicitly rejected. |
| **Separate assessment/ranking stage** | Not needed — ranking is part of matching. |

---

## H. Implementation Prompt

```text
Implement Increment 21B: RelevanceMatcher.

## Context

Increment 21A extracted CapabilityActionPolicy from AssistantChatService.
Now we replace the stub HumanSelectionMatcher with a real RelevanceMatcher.

## What Exists

- CapabilityMatcher protocol in packages/capability_registry/src/capability_matcher.py
- HumanSelectionMatcher returns ALL capabilities with confidence=0.0
- MatchResult model has candidates, confidence, matcher_id, rationale
- Capability model (people_capability/src/capability.py) has: name, description, tags, status, payload
- CapabilityRegistry.list() returns all Capability records
- CapabilityDiscoveryAdapter calls matcher.match() and converts to CapabilityCandidate[]

## What to Build

Create packages/capability_registry/src/relevance_matcher.py with:

class RelevanceMatcher:
    matcher_id = "relevance"
    
    def match(self, request_text, context, capabilities):
        # 1. Filter out DEPRECATED capabilities
        # 2. For each remaining capability, compute a relevance score based on:
        #    - Keyword overlap between request_text and capability name
        #    - Keyword overlap between request_text and capability description
        #    - Keyword overlap between request_text and capability tags
        # 3. Normalise score to 0.0-1.0 range
        # 4. Sort candidates by descending score
        # 5. Return MatchResult with ranked candidates, confidence=top_score, rationale explaining match
        
        pass

## Scoring Rules (deterministic, no LLM)

1. Tokenise request_text into lowercase words
2. For each capability:
   - name_score: fraction of request tokens found in capability name (0.0-1.0)
   - description_score: fraction of request tokens found in description (0.0-1.0)
   - tag_score: fraction of request tokens found in tags (0.0-1.0)
   - combined = name_score * 0.5 + description_score * 0.3 + tag_score * 0.2
3. Capabilities with status == DEPRECATED get score = 0.0 (filtered out)
4. If combined == 0.0, exclude from candidates (no relevance)
5. Sort by combined descending
6. confidence = top_score if any candidates else 0.0
7. rationale = f"Matched {len(candidates)} capabilities by keyword relevance"

## Important Constraints

- This is a pure function. No side effects. No port calls. No database access.
- Do NOT change CapabilityMatcher protocol.
- Do NOT change CapabilityDiscoveryPort.
- Do NOT change CapabilityCandidate.
- Do NOT change CapabilityActionPolicy.
- Do NOT change chat.py.
- Do NOT use LLM, embeddings, or external services.
- Do NOT access ConceptStore or maturation_history yet.

## Tests

Create packages/capability_registry/tests/test_relevance_matcher.py with tests for:
- Name matching
- Description matching
- Tag matching
- Deprecated filtering
- Ranking by score
- Confidence in 0.0-1.0 range
- Rationale generation
- Empty catalog
- No match scenario
- matcher_id == "relevance"

Run: pytest packages/capability_registry/tests/ -q
All existing tests must pass.

## Wire Up

Update packages/capability_registry/src/composition.py (or wherever HumanSelectionMatcher is instantiated) to use RelevanceMatcher instead.

Run: pytest packages/ai/tests/ packages/workflow_runner/tests/ -q
All existing tests must pass.
```

---

## Summary of Key Findings

1. **The matcher contract already supports confidence** — `MatchResult.confidence` exists. The bug is that the adapter drops it.

2. **The discovery port returns flat `CapabilityCandidate[]`** — no confidence, no ranking. This is a known gap but NOT something to fix in 21B.

3. **Evidence IS available but NOT accessible to matching** — `Capability.payload` can contain `maturation_history`, but `HumanSelectionMatcher` (and the planned `RelevanceMatcher`) does not read it. This is intentional for 21B — evidence is too sparse.

4. **The cleanest pipeline is:** Matcher produces `MatchResult` with confidence → adapter converts to candidates (confidence dropped for now) → action policy uses count-based logic. Confidence-driven action policy comes later.

5. **The smallest implementation is a single new file:** `relevance_matcher.py` with deterministic keyword scoring. No contract changes, no port changes, no action policy changes.