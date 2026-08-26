# Increment 21 — Investigation: Evidence-Aware Capability Matching

## 1. Executive Conclusion

The current capability discovery path returns **all registered capabilities** regardless of the user's request. `HumanSelectionMatcher.match()` returns every capability with `confidence=0.0` and the rationale "Human selection required — no automated matching in first slice."

This is an intentional stub, but it creates a poor user experience: the Assistant cannot distinguish "Create a test artifact" from "Enrich a lead" when both capabilities exist in the registry.

**The smallest next increment is Increment 21 — Evidence-Aware Capability Matching.**

This increment replaces the stub matcher with a deterministic, evidence-aware matcher that:
1. Filters capabilities by relevance to the request (name, description, tags, kind)
2. Ranks candidates by execution evidence (invocation count, correction count, maturity)
3. Returns a confidence score
4. Enables the Assistant to make execution decisions: auto-execute (high confidence), ask user (medium confidence), refuse/clarify (low confidence)

This is NOT merely a better search function. It is the first step in closing the learning loop defined in ADR-029: execution evidence (Increment 18/19) feeds back into capability quality assessment, which informs future matching decisions.

---

## 2. Current Capability Discovery Flow

### End-to-End Trace

```
User message
  ↓
AssistantChatService.chat()
  ↓
Intent = Intent(id=..., raw={"type": "natural_language", "text": request.message})
  ↓
frame = recognise(intent)  [rule-based keyword classification]
  ↓
if enterprise_information.find_previous_solutions(strategy_tag):
    return awaiting_confirmation
  ↓
candidates = capability_discovery.find_capabilities(request_text, frame.context)
  ↓
CapabilityDiscoveryAdapter.find_capabilities()
  ↓
capabilities = registry.list()  [returns ALL capabilities]
  ↓
match_result = matcher.match(request_text, ctx, capabilities)
  ↓
HumanSelectionMatcher.match()
  ↓
return MatchResult(candidates=list(capabilities), confidence=0.0, matcher_id="human_selection")
  ↓
if len(candidates) == 1:
    execute directly (Increment 20)
else:
    return awaiting_capability_selection with ALL candidates
```

### Current Behaviour

| Scenario | Capabilities in Registry | Result |
|----------|-------------------------|--------|
| User: "Create a test artifact" | 1 capability | Executes directly |
| User: "Do something" | 3 capabilities | Shows ALL 3, asks user to select |
| User: "Enrich lead Acme Corp" | 2 capabilities | Shows ALL 2, asks user to select |

### The Problem

When multiple capabilities exist, the user must manually scan the entire list. There is:
- No relevance filtering
- No ranking
- No confidence scoring
- No use of execution evidence
- No distinction between "create test artifact" and "send email"

---

## 3. Current Matching Implementation

### HumanSelectionMatcher

```python
class HumanSelectionMatcher:
    matcher_id = "human_selection"
    
    def match(self, request_text, context, capabilities):
        return MatchResult(
            candidates=list(capabilities),
            confidence=0.0,
            matcher_id=self.matcher_id,
            rationale="Human selection required — no automated matching in first slice"
        )
```

**Status**: Intentionally a temporary stub. The docstring and rationale explicitly state this is the "first implementation that presents available capabilities for human selection without performing automated semantic matching."

### CapabilityMatcher Protocol

```python
class CapabilityMatcher(Protocol):
    def match(self, request_text, context, capabilities) -> MatchResult:
        ...
```

The protocol is already designed for replacement. `MatchResult` includes:
- `candidates: list[Capability]`
- `confidence: float`
- `matcher_id: str`
- `rationale: str`

### CapabilityDiscoveryAdapter

```python
class CapabilityDiscoveryAdapter:
    def find_capabilities(self, request_text, context):
        capabilities = self._registry.list()
        ctx = ContextRecord(**context) if context else ContextRecord()
        match_result = self._matcher.match(request_text, ctx, capabilities)
        return [self._to_candidate(cap) for cap in match_result.candidates]
```

The adapter:
1. Lists ALL capabilities from the registry
2. Passes them to the matcher
3. Returns the matcher's candidates as `CapabilityCandidate` DTOs

### Current Tests

`test_capability_matcher.py` proves:
- `HumanSelectionMatcher` returns all capabilities for any input
- Confidence is always 0.0
- Empty catalog returns empty candidates
- `MatchResult` model works

No tests exist for relevance, ranking, or confidence-based selection.

---

## 4. Capability Model Assessment

### Available Metadata

| Field | Type | Available for Matching? |
|-------|------|------------------------|
| `id` | str | Yes (identifier, not semantic) |
| `name` | str | Yes (primary keyword source) |
| `description` | str | Yes (semantic source) |
| `capability_kind` | enum (tool/skill) | Yes (filtering) |
| `status` | enum (draft/active/deprecated) | Yes (filtering) |
| `interface` | CapabilityInterface | Partial (inputs/outputs not currently used) |
| `owns_durable_state` | bool | No (structural property) |
| `standing_contract` | bool | No (governance property) |
| `tags` | list[str] | Yes (keyword/category source) |
| `owner` | str | No (administrative) |
| `created_by` | str | No (administrative) |
| `created_at` | datetime | No (administrative) |
| `updated_at` | datetime | No (administrative) |
| `metadata` | dict | Partial (unstructured) |
| `payload` | dict | Partial (contains execution_mode, maturation_history) |

### Maturation History (in ConceptStore payload)

```python
MaturationHistory:
    invocation_count: int
    correction_count: int
    last_invoked_at: datetime | None
    promoted_at: datetime | None
    promotion_candidacy: bool
```

This is available via `ConceptStore.record_invocation()` and `InvocationRecorderAdapter`. It is currently:
- Updated after every execution (Increment 18)
- Used for promotion decisions (Increment 19)
- NOT used for capability matching

### What's Missing for Better Matching

| Missing Field | Why It Matters | How to Obtain |
|---------------|---------------|---------------|
| Explicit "purpose" or "outcome" | Capability describes *what outcome* it produces | Add to Capability model or derive from description |
| Historical success rate | invocation_count / (invocation_count + correction_count) | Derive from maturation_history |
| Context of use | When was this capability last used successfully? | Derive from last_invoked_at + correction_count |
| Semantic embeddings | Match on meaning, not just keywords | Requires embedding model + vector store |
| Capability requirements | What skills/tools does this capability need? | Not yet modelled (ADR-035) |

---

## 5. Available Metadata/Evidence

### From Capability Model
- `name`, `description`, `tags`, `capability_kind`, `status`
- `interface.inputs`, `interface.outputs` (defined but not used for matching)

### From ConceptStore (via maturation_history)
- `invocation_count` — how many times executed
- `correction_count` — how many times failed
- `last_invoked_at` — recency of use
- `promotion_candidacy` — whether considered for promotion

### From Organisation
- `PreviousSolution` — previous solutions for strategies (used for reuse, not matching)
- `ConceptKind.SOLVED_APPROACH` — stored solutions that could inform matching

### What Is NOT Available
- No capability embeddings or vector representations
- No semantic search index for capabilities
- No LLM-assisted relevance scoring
- No user feedback on capability selection
- No capability requirement specifications (skills, tools, roles)

---

## 6. Architectural Ownership Analysis

### Current Ownership

| Component | Owner | Evidence |
|-----------|-------|----------|
| Capability definition | People/Capability | ADR-020, ADR-042 |
| Capability registry | People/Capability | `CapabilityRegistry` in `capability_registry` package |
| Capability matching | People/Capability | `CapabilityMatcher` protocol in `capability_registry` |
| Capability discovery | People/Capability (via port) | `CapabilityDiscoveryAdapter` bridges to `CapabilityDiscoveryPort` |
| Execution evidence | Operations | `InvocationRecorderAdapter` records to ConceptStore |
| Outcome assessment | Operations | `CapabilityOutcomeAssessorAdapter` |
| Maturation history | Enterprise (stored) / People/Capability (owned) | `MaturationHistory` in `EnterpriseConcept.payload` |

### Key Boundaries

| Boundary | Status | Evidence |
|----------|--------|----------|
| AI plane → People/Capability | Port-based | `CapabilityDiscoveryPort` interface |
| AI plane → Operations | Port-based | `CapabilityExecutionPort` interface |
| People/Capability → Enterprise | Repository-based | `CapabilityRepository` protocol |
| Operations → Enterprise | Adapter-based | `InvocationRecorderAdapter` |

### Matching Ownership

**Capability matching belongs entirely in People/Capability.**

The `CapabilityMatcher` protocol is defined in `capability_registry` (People/Capability plane). The `CapabilityDiscoveryAdapter` bridges it to the AI plane via `CapabilityDiscoveryPort`. The Assistant never directly invokes the matcher.

This is architecturally correct. The Assistant should not decide which capability is relevant — that is a People/Capability domain decision.

---

## 7. Candidate Approaches for Matching

### Approach A: Deterministic Keyword Matching

**Description**: Match request text against capability `name`, `description`, and `tags` using keyword overlap, TF-IDF-style scoring, or rule-based patterns.

**How it works**:
1. Tokenise request text
2. Tokenise capability name, description, tags
3. Compute overlap score
4. Filter by kind, status, execution_mode
5. Rank by score

**Pros**:
- Simple, predictable, explainable
- No new infrastructure
- No LLM costs
- Easy to test
- Architecturally clean (stays in People/Capability)

**Cons**:
- Brittle (synonyms, paraphrases, misspellings)
- Requires manual tuning
- Doesn't understand intent or context

**Verdict**: Too limited as a long-term solution, but acceptable as a first step IF combined with evidence-based ranking.

### Approach B: Semantic/Embedding Matching

**Description**: Generate embeddings for capability descriptions and user requests, then use vector similarity (Qdrant) to find matches.

**How it works**:
1. Generate embedding for each capability's name + description
2. Generate embedding for user request
3. Query Qdrant for top-K similar capabilities
4. Rank by similarity score

**Pros**:
- Matches on meaning, not just keywords
- Handles synonyms and paraphrases
- Scalable to large capability catalogs

**Cons**:
- Requires embedding model (new infrastructure)
- Requires Qdrant integration (exists for KnowledgeChunks, not capabilities)
- Requires embedding generation pipeline
- Harder to test and debug
- More complex

**Verdict**: Too much infrastructure for the next increment. Should be a future enhancement.

### Approach C: LLM-Assisted Matching

**Description**: Send the request and capability catalog to an LLM, asking it to select the best match with reasoning.

**How it works**:
1. Format request + capability list as prompt
2. Call LLM (Claude, GPT, etc.)
3. Parse LLM response for selected capability + confidence
4. Return match result

**Pros**:
- Most flexible and accurate
- Can reason about context, constraints, outcomes
- Natural language explanation

**Cons**:
- Requires LLM integration (not yet available for matching)
- Expensive (API calls per request)
- Latency (seconds vs milliseconds)
- Non-deterministic (harder to test)
- Architecturally questionable (matching in AI plane?)

**Verdict**: Too heavy for the next increment. Should be a future enhancement after deterministic matching is proven.

### Approach D: Evidence-Aware Deterministic Matching (RECOMMENDED)

**Description**: Combine deterministic relevance scoring with execution evidence to rank and filter capabilities.

**How it works**:
1. **Relevance scoring** (deterministic):
   - Keyword overlap: request text vs capability name, description, tags
   - Kind filtering: prefer matching kind (tool vs skill)
   - Status filtering: prefer ACTIVE over DRAFT/DEPRECATED
2. **Evidence scoring** (from maturation_history):
   - Invocation count: more invocations = more proven
   - Correction count: fewer corrections = more reliable
   - Recency: recently invoked = currently maintained
   - Promotion candidacy: candidacy = maturing
3. **Confidence calculation**:
   - High confidence: strong keyword match + positive evidence
   - Medium confidence: moderate match OR mixed evidence
   - Low confidence: weak match OR negative evidence
4. **Return**:
   - Ranked candidates above confidence threshold
   - Confidence score
   - Rationale explaining ranking

**Pros**:
- Uses existing metadata (no new infrastructure)
- Incorporates execution evidence (learning loop)
- Deterministic and explainable
- Architecturally clean (stays in People/Capability)
- Establishes pattern for future LLM/embedding enhancement
- Small implementation scope

**Cons**:
- Still keyword-based (limited semantic understanding)
- Requires calibration of scoring weights

**Verdict**: **Best next increment.** It materially improves matching quality while staying within architectural boundaries and existing infrastructure.

---

## 8. Comparison of Approaches

| Criterion | A. Keyword | B. Semantic | C. LLM | D. Evidence-Aware (RECOMMENDED) |
|-----------|-----------|-------------|--------|-------------------------------|
| Implementation cost | Low | High | High | Medium |
| Infrastructure needed | None | Embeddings + Qdrant | LLM API | None |
| Architectural impact | Low | Medium | High | Low |
| Testability | High | Medium | Low | High |
| Explainability | High | Medium | Low | High |
| Uses execution evidence | No | No | No | Yes |
| Handles synonyms | No | Yes | Yes | No |
| Latency | Milliseconds | Milliseconds | Seconds | Milliseconds |
| Cost | Zero | Embedding costs | LLM API costs | Zero |
| Scalability | Medium | High | Low | Medium |
| Alignment with ADRs | High | Medium | Low | High |

---

## 9. Recommended Approach

**Evidence-Aware Deterministic Matching (Approach D)**

### Why This Approach

1. **It closes the learning loop**: Increment 18/19 collects execution evidence. This increment USES that evidence to improve matching. ADR-029 explicitly defines this loop.

2. **It is not merely search**: It reasons about capability quality (evidence-based ranking) and makes confidence-based execution decisions. The architecture treats capability matching as a domain decision, not a search problem.

3. **It is the smallest coherent increment**: No new infrastructure, no LLM calls, no embeddings. It extends the existing `CapabilityMatcher` protocol with a new implementation.

4. **It establishes the pattern for future enhancement**: The `MatchResult` already has `confidence` and `rationale` fields. Future matchers (semantic, LLM) can replace the implementation without changing the interface.

5. **It is architecturally correct**: Matching stays in People/Capability plane. The Assistant receives ranked candidates via `CapabilityDiscoveryPort` and makes execution decisions based on confidence.

---

## 10. Proposed User Behaviour

### Before Increment 21

```
User: "Create a test artifact"
Assistant: "I found 1 capability that might help. Running it now..." [executes]

User: "Do something with data"
Assistant: "I found 3 capabilities that might help. Please select one to proceed."
  [Shows: create_test_artifact, send_email, analyse_data]
```

### After Increment 21

```
User: "Create a test artifact"
Assistant: "I found 1 capability that might help. Running it now..." [executes]

User: "Do something with data"
Assistant: "I found 2 capabilities that might help, ranked by relevance:
  1. analyse_data (confidence: 0.85, 12 invocations, 1 correction)
  2. create_test_artifact (confidence: 0.30, 45 invocations, 0 corrections)
  
  Running analyse_data..."
  [executes top candidate if confidence > threshold]

User: "Send a notification"
Assistant: "I found 1 capability that might help. Running it now..." [executes]

User: "Do something completely unknown"
Assistant: "I couldn't find any capabilities that match your request. 
  Could you describe what you're trying to accomplish?"
```

### Confidence Thresholds

| Confidence | Action |
|------------|--------|
| >= 0.8 | Auto-execute top candidate |
| 0.5 - 0.8 | Present top 3 candidates, ask user |
| < 0.5 | Present top 5 candidates, ask user |
| 0.0 (no match) | Ask user to clarify or describe capability need |

---

## 11. Proposed Execution Decision Model

### Current Model (Increment 20)

```
1 candidate → execute
Multiple candidates → ask user
0 candidates → fall through to pattern execution
```

### Proposed Model (Increment 21)

```
candidates = find_capabilities(request_text, context)
if not candidates:
    return "I couldn't find any capabilities that match. Could you describe what you're trying to accomplish?"

ranked = rank_by_relevance_and_evidence(candidates, request_text)
top = ranked[0]

if top.confidence >= AUTO_EXECUTE_THRESHOLD (0.8):
    execute(top)
elif top.confidence >= ASK_USER_THRESHOLD (0.5):
    present_top_n(ranked, n=3)
else:
    present_top_n(ranked, n=5)
```

### Rationale

This model:
- Respects the user's intent (high confidence = execute automatically)
- Preserves human agency (medium/low confidence = ask)
- Handles unknown requests gracefully (no candidates = clarify)
- Uses evidence to inform confidence, not just keyword match

---

## 12. Proposed Confidence Model

### Confidence Components

```python
confidence = (
    relevance_score * 0.6 +
    evidence_score * 0.4
)
```

### Relevance Score (0.0 - 1.0)

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Name match | 0.4 | Exact match = 1.0, partial match = 0.5, no match = 0.0 |
| Description match | 0.3 | Keyword overlap ratio |
| Tag match | 0.2 | Exact tag match = 1.0, partial = 0.5 |
| Kind match | 0.1 | Implicit from context (e.g., "create" → tool) |

### Evidence Score (0.0 - 1.0)

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Invocation count | 0.3 | Normalised: min(invocations / 10, 1.0) |
| Success rate | 0.4 | (invocations - corrections) / invocations |
| Recency | 0.2 | Recently invoked = 1.0, never = 0.5, long ago = 0.0 |
| Maturity | 0.1 | promotion_candidacy = 1.0, ACTIVE = 0.8, DRAFT = 0.3 |

### Evidence Sources

Evidence comes from `EnterpriseConcept.payload["maturation_history"]`:
```python
{
    "invocation_count": 12,
    "correction_count": 1,
    "last_invoked_at": "2026-08-23T10:00:00Z",
    "promoted_at": null,
    "promotion_candidacy": false
}
```

This data is already collected by `InvocationRecorderAdapter` (Increment 18) and assessed by `CapabilityOutcomeAssessorAdapter` (Increment 19). It is stored in `ConceptStore` and accessible via `CapabilityRegistry` → `ConceptStoreCapabilityRepository`.

---

## 13. Required Interfaces/Changes

### New Implementation

| Component | Location | Change |
|-----------|----------|--------|
| `RelevanceMatcher` | `capability_registry/src/capability_matcher.py` | New class implementing `CapabilityMatcher` |
| `CapabilityEvidence` | `capability_registry/src/capability_evidence.py` | Helper to extract evidence from maturation_history |

### Modified Components

| Component | Change |
|-----------|--------|
| `CapabilityDiscoveryAdapter.__init__` | Accept `CapabilityMatcher` (already does) |
| `MatchResult` | No change — already has `candidates`, `confidence`, `matcher_id`, `rationale` |
| `AssistantChatService.chat()` | Use confidence to make execution decisions (already partially does for single candidate) |
| `_ChatResponse` | No change — already has `telemetry` field |

### New Interfaces

None required. The existing `CapabilityMatcher` protocol and `CapabilityDiscoveryPort` interface are sufficient.

### Composition Root

`create_application()` in `composition.py` needs to instantiate `RelevanceMatcher` instead of `HumanSelectionMatcher`:

```python
# Before
matcher = HumanSelectionMatcher()

# After
matcher = RelevanceMatcher()
```

---

## 14. Tests Required

### Unit Tests (capability_registry)

| Test | Purpose |
|------|---------|
| `test_relevance_matcher_filters_by_keyword` | Request "create test" matches capability with "create" in name/description |
| `test_relevance_matcher_filters_by_tag` | Request "email notification" matches capability with "email" tag |
| `test_relevance_matcher_filters_by_kind` | Request "run skill" matches SKILL kind, not TOOL |
| `test_relevance_matcher_filters_by_status` | DRAFT/DEPRECATED capabilities are excluded or downgraded |
| `test_relevance_matcher_ranks_by_evidence` | Capability with higher invocation count ranks higher |
| `test_relevance_matcher_returns_confidence` | Confidence score is between 0.0 and 1.0 |
| `test_relevance_matcher_returns_rationale` | Rationale explains ranking |
| `test_relevance_matcher_handles_empty_catalog` | Returns empty candidates |
| `test_relevance_matcher_handles_no_evidence` | Capability without maturation_history gets default evidence score |

### Integration Tests (workflow_runner)

| Test | Purpose |
|------|---------|
| `test_discovery_adapter_uses_relevance_matcher` | CapabilityDiscoveryAdapter returns ranked candidates |
| `test_chat_auto_executes_high_confidence` | Confidence >= 0.8 → execute directly |
| `test_chat_asks_user_medium_confidence` | Confidence 0.5-0.8 → present top 3 |
| `test_chat_presents_more_low_confidence` | Confidence < 0.5 → present top 5 |
| `test_chat_clarifies_no_match` | No candidates → ask for clarification |
| `test_evidence_from_concept_store` | Maturation history from ConceptStore influences ranking |

### Architectural Boundary Tests

| Test | Purpose |
|------|---------|
| `test_matcher_stays_in_people_capability_plane` | No imports from Operations/Enterprise/AI planes |
| `test_discovery_adapter_bridges_via_port` | Adapter converts Capability → CapabilityCandidate via port |

---

## 15. What Must NOT Change

| Constraint | Reason |
|------------|--------|
| `CapabilityMatcher` protocol | Stable interface; new implementation only |
| `CapabilityDiscoveryPort` interface | Stable interface; adapter unchanged |
| `MatchResult` model | Already has required fields |
| `Capability` domain model | No new fields; use existing metadata |
| `CapabilityRegistry` API | No new methods; use existing `list()` |
| AI plane imports | No new cross-plane imports |
| Execution path | Increment 20 execution flow unchanged |
| Capability execution | No changes to `CapabilityExecutionPort` or `CapabilityExecutionAdapter` |
| ConceptStore | No schema changes; use existing `maturation_history` in payload |

---

## 16. Architectural Invariants

1. **AI plane depends on ports only** — `AssistantChatService` uses `CapabilityDiscoveryPort`, not `CapabilityMatcher` directly.
2. **People/Capability owns capability matching** — `CapabilityMatcher` protocol and implementations live in `capability_registry` package.
3. **Operations owns execution** — matching does not invoke capabilities.
4. **Enterprise owns durable storage** — maturation history is stored in ConceptStore but owned by People/Capability.
5. **Capability is execution-agnostic** — matching uses capability metadata, not deployment metadata.
6. **No circular dependencies** — new code in People/Capability plane only.
7. **Learning loop is preserved** — execution evidence (Increment 18/19) feeds matching (Increment 21).
8. **Existing tests pass** — no regressions in capability_registry, ai, or workflow_runner tests.

---

## 17. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Over-tuning confidence thresholds | Medium | Medium | Use conservative thresholds; make them configurable |
| Keyword matching too brittle | Medium | Medium | Start with simple overlap; iterate based on real requests |
| Evidence data sparse (few invocations) | High | Low | Default evidence score for capabilities without history |
| Performance with large catalogs | Low | Low | Deterministic matching is fast; filter by kind/status first |
| Test fragility | Medium | Low | Use fixtures with realistic capability sets |

---

## 18. Future Extensions (Explicitly Deferred)

| Extension | Why Deferred |
|-----------|-------------|
| Semantic/embedding matching | Requires embedding model + Qdrant integration for capabilities |
| LLM-assisted matching | Requires LLM integration; use after deterministic matching is proven |
| Capability requirement modelling | ADR-035 investigation not complete |
| Skill/Tool separation | ADR-035 investigation not complete |
| Conversation state/memory | Explicitly excluded |
| AI Gateway | Explicitly excluded |
| Paperclip | Explicitly excluded |
| LangGraph pattern execution improvement | Not required for matching |
| Runtime selection optimisation | Not required for matching |
| Capability gap detection | Future increment after matching works |
| Register skills as capabilities | Future increment after matching works |
| User feedback on capability selection | Future increment; requires UI changes |

---

## 19. Exact Proposed Increment 21 Scope

### In Scope

| Component | Change |
|-----------|--------|
| `RelevanceMatcher` | New class in `capability_matcher.py` implementing `CapabilityMatcher` |
| `CapabilityEvidence` | New helper to extract evidence from maturation_history |
| `AssistantChatService.chat()` | Use confidence to make execution decisions |
| Tests | Unit tests for matcher, integration tests for chat flow |

### Out of Scope

| Component | Reason |
|-----------|--------|
| Semantic/embedding matching | Requires new infrastructure |
| LLM-assisted matching | Requires LLM integration |
| Capability model changes | Existing fields sufficient |
| CapabilityRegistry API changes | Existing API sufficient |
| New ports/interfaces | Existing `CapabilityMatcher` protocol sufficient |
| ConceptStore schema changes | Existing payload sufficient |
| AI Gateway | Explicitly excluded |
| Paperclip | Explicitly excluded |

---

## 20. Explicit Non-Goals

The following are explicitly NOT part of Increment 21:

| Non-Goal | Reason |
|----------|--------|
| Perfect capability matching | Deterministic matching is a stepping stone |
| Semantic search for capabilities | Future enhancement after deterministic matching |
| LLM-based capability selection | Future enhancement; requires AI Gateway |
| Capability model extension | Existing fields are sufficient for this increment |
| Conversation state/memory | Explicitly excluded |
| AI Gateway implementation | Explicitly excluded |
| Paperclip integration | Explicitly excluded |
| Capability gap detection | Future increment |
| Skill registration as capabilities | Future increment |
| Runtime selection optimisation | Not required for matching |

---

## 21. Evidence Summary

### Current State Evidence

| Evidence | Source | Current Use |
|----------|--------|-------------|
| Capability name/description/tags | Capability model | Available, not used for matching |
| Capability kind (tool/skill) | Capability model | Available, not used for matching |
| Capability status (draft/active) | Capability model | Available, not used for matching |
| Interface (inputs/outputs) | Capability model | Available, not used for matching |
| Invocation count | maturation_history (ConceptStore) | Used for promotion candidacy |
| Correction count | maturation_history (ConceptStore) | Used for promotion candidacy |
| Last invoked at | maturation_history (ConceptStore) | Not used for matching |
| Previous solutions | EnterpriseInformationPort | Used for strategy reuse |

### Increment 18/19 Evidence

| Increment | What It Proved | Relevance to Matching |
|-----------|---------------|----------------------|
| Increment 18 | Invocation telemetry recording works | Provides invocation_count, correction_count |
| Increment 19 | Outcome assessment works | Provides success/failure evidence |
| Both | Evidence flows to ConceptStore | MaturationHistory is available for matching |

### Test Evidence

| Test Suite | Count | Status |
|------------|-------|--------|
| `capability_registry/tests/` | 8 | All pass |
| `ai/tests/` | 47 | All pass |
| `workflow_runner/tests/` | 185 | All pass |
| Increment 18 tests | 12 | All pass |
| Increment 19 tests | 28 | All pass |
| Increment 20 tests | 18 | All pass |

---

## 22. Final Recommendation

### Increment 21 — Evidence-Aware Capability Matching

**Objective**: Replace `HumanSelectionMatcher` with `RelevanceMatcher` that filters, ranks, and scores capabilities by relevance and execution evidence.

**Why this increment:**

1. **Materially improves user experience**: Users no longer see ALL capabilities. They see ranked, relevant candidates with confidence scores.

2. **Closes the learning loop**: Execution evidence from Increments 18/19 feeds back into matching quality. This is the first operationalisation of ADR-029's learning loop.

3. **Smallest coherent increment**: No new infrastructure, no LLM calls, no embeddings. Extends the existing `CapabilityMatcher` protocol with a new implementation.

4. **Architecturally correct**: Matching stays in People/Capability plane. The Assistant receives ranked candidates via `CapabilityDiscoveryPort` and makes execution decisions based on confidence.

5. **Not merely search**: It reasons about capability quality (evidence-based ranking) and makes confidence-based execution decisions. The architecture treats capability matching as a domain decision, not a search problem.

6. **Establishes pattern for future enhancement**: The `MatchResult` interface already supports confidence and rationale. Future matchers (semantic, LLM) can replace the implementation without changing the interface.

### What Increment 21 Does NOT Change

- Capability model (no new fields)
- CapabilityRegistry API (no new methods)
- Execution path (Increment 20 unchanged)
- AI plane imports (no new cross-plane dependencies)
- ConceptStore schema (uses existing maturation_history)
- Existing ports/interfaces (CapabilityMatcher, CapabilityDiscoveryPort unchanged)

### What Increment 21 Unlocks

- Users see relevant capabilities, not all capabilities
- Execution decisions are confidence-based, not arbitrary
- Execution evidence improves matching quality over time
- Foundation for semantic/LLM matching in future increments
- First operationalisation of the ADR-029 learning loop

---

## 23. Answer to the Core Question

> "After Increment 20, what is the smallest next increment that materially increases the Assistant's ability to turn real user intent into useful execution?"

**Increment 21 — Evidence-Aware Capability Matching.**

Increment 20 made execution possible when exactly one capability is found. But when multiple capabilities exist, the user still sees an unfiltered, unranked list. This is the current bottleneck: the Assistant cannot distinguish relevant capabilities from irrelevant ones.

Increment 21 fixes this by:
1. **Filtering** capabilities by relevance to the user's request
2. **Ranking** candidates by execution evidence (invocation count, success rate, recency)
3. **Scoring** candidates with confidence values
4. **Deciding** whether to auto-execute, ask the user, or ask for clarification

This is the smallest increment that materially improves the system because:
- It uses existing metadata (no new infrastructure)
- It uses existing evidence from Increments 18/19 (no new telemetry)
- It keeps architectural boundaries intact (matching stays in People/Capability)
- It establishes the learning loop (evidence → matching quality)
- It is a single, coherent vertical slice

**Why this increment before alternatives:**

| Alternative | Why Not First |
|-------------|---------------|
| Semantic/embedding matching | Requires new infrastructure (embeddings, Qdrant for capabilities). Too heavy. |
| LLM-assisted matching | Requires LLM integration, API costs, latency. Too heavy. |
| Capability gap detection | Useful but doesn't help when capabilities exist but aren't matched. |
| Register skills as capabilities | Increases catalog size but doesn't improve matching. |
| Conversation state/memory | Explicitly excluded. |
| AI Gateway | Explicitly excluded. |
| Paperclip | Explicitly excluded. |

**Increment 21 is the next logical step because it completes the capability execution loop: discover → match → rank → execute → learn → improve matching.**
