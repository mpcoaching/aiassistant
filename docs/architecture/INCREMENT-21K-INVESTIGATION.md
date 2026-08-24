# Increment 21K — Investigation: Real-Request Evidence & Feedback Loop

**Status:** Read-only investigation. No production code changes.  
**Prerequisites:** Increments 21A–21J implemented. Expanded evaluation corpus (70 examples, 16 capabilities). score_gap == 0.0 signal identified in synthetic corpus.

---

## A. Current Measurement Infrastructure

### What exists today

| Component | Location | What it captures |
|-----------|----------|-----------------|
| `ChatRequest` | `packages/ai/src/chat.py` | `message`, `session_id`, `user_id`, `context` |
| `ChatResponse` | `packages/ai/src/chat.py` | `message`, `status`, `capability_candidates`, `telemetry` |
| `telemetry` | `ChatResponse.telemetry` | `recognition_level`, `matcher`, `candidate_count`, `interaction` |
| `/assistant/chat` | `packages/workflow_runner/api.py:624` | Receives user requests, returns `ChatResponse` |
| `/assistant/capability/{id}/execute` | `packages/workflow_runner/api.py:760` | Executes selected capability |
| `/assistant/chat/{session_id}/resume` | `packages/workflow_runner/api.py:649` | Resumes paused session with human input |
| `ConceptStore` | `packages/capability_registry/src/concepts.py` | Persists `EnterpriseConcept` records, including `MaturationHistory` |
| `InvocationRecorderAdapter` | `packages/workflow_runner/src/adapters/invocation_recorder_adapter.py` | Records execution outcomes to `ConceptStore` |
| Evaluation corpus | `packages/capability_registry/tests/fixtures/evaluation_corpus.json` | 70 synthetic examples, 16 capabilities |

### What is NOT captured

| Signal | Why missing |
|--------|-------------|
| **User selection** | No mechanism records which candidate the user chose from `capability_candidates` |
| **User rejection** | No mechanism records when the user rejects all presented candidates |
| **User reformulation** | No mechanism records when the user re-queries after seeing candidates |
| **Request-to-selection correlation** | `session_id` exists but is not correlated with selection decisions |
| **Score gap at presentation time** | `candidate_confidences` is not exposed in `ChatResponse.telemetry` |
| **Match source at presentation time** | Not captured in telemetry |
| **Real request corpus** | No logging mechanism for production requests |

---

## B. Real-Request Collection Mechanism

### Option 1: Extend existing telemetry (LOW cost, LOW coverage)

Add matching metadata to the existing `ChatResponse.telemetry`:

```python
telemetry={
    "recognition_level": frame.recognition_level.value,
    "matcher": "relevance",
    "candidate_count": len(candidates),
    "interaction": interaction,
    "top_score": candidates[0].confidence if candidates else 0.0,
    "score_gap": candidates[0].confidence - candidates[1].confidence if len(candidates) > 1 else 0.0,
}
```

**Advantages:**
- Minimal code change (one response model)
- No new endpoints
- No new storage
- Data flows through existing API response

**Disadvantages:**
- Only captures data when the assistant is invoked via the API
- Does not persist data — client must log it
- No user-feedback correlation
- Telemetry is ephemeral (lost after response)

### Option 2: Log to ConceptStore (MEDIUM cost, HIGH coverage)

Create a new `CapabilitySelectionEvent` concept kind and persist request/response events:

```python
class CapabilitySelectionEvent(BaseModel):
    session_id: str
    request_text: str
    candidates_presented: list[dict]
    top_score: float
    score_gap: float
    interaction: str
    user_action: str | None = None  # "confirm", "reject", "select_alternative", None
    selected_capability_id: str | None = None
    timestamp: datetime
```

**Advantages:**
- Durable storage via existing `ConceptStore`
- Correlatable across sessions
- Can accumulate historical evidence
- No new infrastructure

**Disadvantages:**
- Requires new concept kind and schema
- Requires write path from `AssistantChatService` to `ConceptStore`
- `ConceptStore` is in People/Capability plane — AI plane currently cannot write to it directly
- Would require a new port or adapter

### Option 3: Structured application log (LOW cost, MEDIUM coverage)

Log structured JSON events from `AssistantChatService`:

```python
logger.info("capability_selection", extra={
    "session_id": session_id,
    "request": request.message,
    "candidates": [...],
    "top_score": top_score,
    "score_gap": score_gap,
    "interaction": interaction,
})
```

**Advantages:**
- Zero production code changes to contracts or ports
- No new storage dependencies
- Easy to implement
- Can be shipped to any log aggregation system

**Disadvantages:**
- Not queryable without external tooling
- No built-in retention policy
- Requires log aggregation infrastructure

### Option 4: Dedicated feedback endpoint (MEDIUM cost, HIGH coverage)

Add `/assistant/capability/feedback` endpoint:

```python
POST /assistant/capability/feedback
{
    "session_id": "ses-123",
    "action": "confirm" | "reject" | "select_alternative",
    "selected_capability_id": "cap-xyz" | null,
    "presented_candidates": ["cap-a", "cap-b", "cap-c"]
}
```

**Advantages:**
- Explicit, structured feedback
- Correlatable with request via `session_id`
- Can be implemented without changing matching or execution
- Client can call this when user makes a selection

**Disadvantages:**
- Requires new endpoint
- Requires client cooperation (must call feedback endpoint)
- Does not capture requests that never reach capability selection

### Recommendation: Option 3 + Option 1

**Smallest coherent approach:**

1. **Immediate (no production change):** Extend `ChatResponse.telemetry` with matching metadata (`top_score`, `score_gap`, `candidate_confidences`). This is observation-only — it exposes existing data through the existing response.

2. **Short-term (minimal production change):** Add structured logging from `AssistantChatService` for capability selection events. This requires no new ports, contracts, or storage — just `logger.info()` calls with structured data.

3. **Medium-term (requires design):** Add a lightweight feedback endpoint if/when the client needs to send structured user decisions back to the server.

**Why not Option 2 (ConceptStore)?** The AI plane cannot write to ConceptStore without a new port/adapter, which would be a cross-plane dependency that the architecture explicitly avoids.

**Why not Option 4 alone?** An endpoint without logging means we lose requests that don't reach capability selection. Logging is the prerequisite.

---

## C. User Feedback Mechanism

### What the client currently does

1. Client calls `POST /assistant/chat` with user message
2. Server returns `ChatResponse` with `status="awaiting_capability_selection"` and `capability_candidates`
3. Client renders candidates to user
4. User selects/rejects
5. **Currently nothing happens.** There is no endpoint for the client to report the user's decision.

### Existing execution path (not selection feedback)

The client can call `POST /assistant/capability/{capability_id}/execute` to execute a capability. But:
- This executes the capability, not just records selection
- There is no way to record rejection without execution
- There is no way to record "user selected a different candidate than the top-ranked one" without executing it

### Smallest feedback mechanism

**Add a new endpoint:** `POST /assistant/capability/selection`

```python
class CapabilitySelectionFeedback(BaseModel):
    session_id: str
    action: str  # "confirm", "reject", "select_alternative"
    selected_capability_id: str | None = None
```

This endpoint:
- Does NOT execute the capability
- Does NOT change matching or decision policy
- Simply records the user's decision
- Returns acknowledgement

**Implementation location:** `packages/workflow_runner/api.py`
**Storage:** Initially in-memory or log-structured; could be persisted to ConceptStore later if needed.
**Port impact:** None — this is a transport-layer endpoint, not a port change.

**But this is a production code change.** For 21K investigation, we only need to identify that this is the smallest mechanism. We do not implement it.

---

## D. Validating the score_gap == 0.0 Hypothesis

### What the corpus shows

| Corpus | gap=0.0 | Generic | Specific | Ambiguous |
|--------|---------|---------|----------|-----------|
| 21G (18 examples, 5 caps) | 5/5 generic | 0/9 | 0/2 | — |
| 21J (70 examples, 16 caps) | 10/10 generic | 0/43 | 0/6 | — |

**Within the synthetic corpus, gap=0.0 perfectly identifies under-specified requests.**

### What real data could show

| Hypothesis | Evidence needed |
|------------|----------------|
| gap=0.0 continues to predict user confusion/rejection | Log requests with gap=0.0 and track user behaviour |
| gap=0.0 misclassifies specific requests | Find specific requests where all candidates tie |
| Small gaps (0.05–0.175) are still specific | Find specific requests with gap in this range |
| Gap distribution changes with catalogue size | Measure gap distribution as capabilities grow |

### Counterexamples to watch for

1. **Specific request with gap=0.0**: A request like "create report" might tie between `create_report` and `generate_report` if both have identical metadata. This would be a false positive for the gap=0.0 signal.

2. **Generic request with gap>0**: A request like "create something for the test artifact" might score `create_test_artifact` higher than other `create_*` capabilities, producing a positive gap despite being under-specified.

3. **Single-candidate generic request**: "data" produces a single candidate with gap=0.0 (no second candidate). The gap signal is undefined for single-candidate cases.

### Validation design

For each real request, capture:

| Field | Source |
|-------|--------|
| `request_text` | `ChatRequest.message` |
| `session_id` | `ChatRequest.session_id` |
| `candidates_presented` | `ChatResponse.capability_candidates` |
| `top_score` | `candidates[0].confidence` |
| `score_gap` | `candidates[0].confidence - candidates[1].confidence` |
| `candidate_count` | `len(candidates)` |
| `user_action` | New feedback endpoint |
| `selected_capability_id` | New feedback endpoint |
| `reformulated` | Derived: new session_id with different request within N minutes |

Then compute:

| Metric | Definition |
|--------|-----------|
| gap=0.0 rejection rate | % of gap=0.0 requests where user rejected all candidates |
| gap=0.0 reformulation rate | % of gap=0.0 requests where user re-queried |
| gap>0 selection rate | % of gap>0 requests where user selected top candidate |
| top-1 selection rate | % of requests where user selected the top-ranked candidate |
| alternative selection rate | % of requests where user selected a non-top candidate |

---

## E. Measuring Actual Matcher Usefulness

### Production-oriented metrics

| Metric | Definition | What it tells us |
|--------|-----------|-----------------|
| **Top-1 selection rate** | User selects top-ranked candidate / total selections | Does the ranking match user intent? |
| **Alternative selection rate** | User selects non-top candidate / total selections | How often is the matcher wrong? |
| **Rejection rate** | User rejects all candidates / total presentations | How often is the match useless? |
| **Reformulation rate** | User re-queries after seeing candidates / total presentations | How often is the match misleading? |
| **Selection rate by score gap** | Top-1 selection rate broken down by gap buckets | Does gap predict selection accuracy? |
| **Selection rate by candidate count** | Top-1 selection rate broken down by candidate count | Does count predict selection accuracy? |
| **Confirmation rate** | User confirms single candidate / total confirmations | Are single-candidate matches reliable? |

### Limitations of user selection as ground truth

1. **Users may select the first option by default**, not because it's correct.
2. **Users may select a wrong option** and not realize it until later.
3. **Users may not know what they want** and select arbitrarily.
4. **Selection is a behavioural signal, not a correctness signal.**

**Conclusion:** User selection is the best available ground truth, but it should be treated as probabilistic evidence, not absolute correctness.

---

## F. The "create something" Case in Production

### What would happen today

1. User: "create something"
2. Matcher: produces 4 candidates (create_lead, create_customer, create_report, create_test_artifact), all with score=0.400, gap=0.0
3. Action policy: `AskUserToSelect(interaction="select")` — "I found 4 capabilities that might help. Please select one..."
4. User: sees 4 options, none of which match their intent (they wanted something not in the catalogue)
5. User: either rejects all, re-queries, or selects arbitrarily

### What we would learn

- **Rejection rate for gap=0.0**: How often do users reject all candidates when gap=0.0?
- **Reformulation rate for gap=0.0**: How often do users re-query?
- **Alternative selection rate for gap=0.0**: How often do users select a non-intended capability?

### What we would NOT learn

- **What the user actually wanted** (unless they tell us in the reformulation)
- **Whether the system should have returned no candidates** (we don't have ground truth)
- **Whether a different decision policy would have produced a better outcome** (we can only observe, not A/B test policies)

---

## G. Architectural Assessment

### Where does candidate-presentation decision belong?

**Current: `CapabilityActionPolicy` in AI plane.**

The policy already owns:
- `NoCapabilityMatch` (0 candidates)
- `AskUserToSelect(interaction="confirm")` (1 candidate)
- `AskUserToSelect(interaction="select")` (2+ candidates)

This is the correct location for any future candidate-presentation logic.

### Where does feedback recording belong?

**Not in `CapabilityActionPolicy`.**

Feedback recording is:
- Not a matching concern (People/Capability)
- Not a decision concern (AI plane)
- Not an execution concern (Operations)

It is a **measurement/telemetry concern** that belongs at the application layer or transport layer.

**Smallest location:** The API layer (`workflow_runner/api.py`) or a new lightweight telemetry service in the AI plane that records selection events without affecting the decision flow.

### Should a new assessment layer be created?

**No.**

Feedback recording is orthogonal to matching and decision. It does not require a new abstraction. It requires:
1. Logging (Option 3 above)
2. An optional feedback endpoint (Option 4 above)

Neither requires a new port, service, or architectural layer.

---

## H. Decision Models (Revisited with Evidence Lens)

| Model | Evidence needed | Current evidence | Verdict |
|-------|----------------|-----------------|---------|
| **A. Count only** (current) | None | Sufficient | **Keep** |
| **B. Absolute threshold** | Calibrated score distribution | Overlapping distributions | Defer |
| **C. Gap threshold (gap=0.0)** | Real-user validation | Perfect on synthetic corpus | **Investigate** |
| **D. Token coverage** | Real-user validation | Weak on synthetic corpus | Defer |
| **E. Match uniqueness** | Real-user validation | Untested | Defer |
| **F. Hybrid** | Calibrated weights | None | Defer |

### The gap=0.0 signal is promising but unvalidated

**What we know:**
- In the synthetic corpus, gap=0.0 perfectly identifies under-specified requests.
- The mechanism is principled: when all candidates tie, the request cannot discriminate between them.
- It does not require arbitrary thresholds — it is a mathematical property of the candidate set.

**What we don't know:**
- Does gap=0.0 generalize to real user requests?
- Does gap=0.0 correlate with user rejection/reformulation?
- Are there specific requests that legitimately produce gap=0.0?
- Does the signal hold as the catalogue grows?

**What we need:**
- Real request data with user behaviour
- At least 100–200 requests with selection feedback
- Validation that gap=0.0 predicts rejection/reformulation

---

## I. Explicit Deferrals

| Item | Why Deferred |
|------|--------|
| **Score thresholds** | No calibrated basis. Overlapping distributions. |
| **Gap thresholds (positive)** | gap=0.0 is principled, but gap>0 thresholds would be arbitrary. |
| **Token-coverage thresholds** | Weak signal on synthetic corpus. |
| **Match-uniqueness rule** | Untested. Requires larger corpus. |
| **Autonomous execution** | Matching does not provide authorisation. Deferred indefinitely. |
| **Evidence-informed matching** | Evidence too sparse. Deferred until invocation volume is meaningful. |
| **User-feedback endpoint** | Valuable but requires production change. Defer until measurement priority is established. |
| **ConceptStore feedback persistence** | AI plane cannot write to ConceptStore without new port/adapter. |
| **LLM matching / embeddings / Qdrant** | Out of scope. |
| **Agent abstraction / orchestrator** | Architecture explicitly rejects. |

---

## J. Recommended Next Increment

### Increment 21K: Real-Request Evidence & Feedback Loop

**Objective:** Establish whether the gap=0.0 signal and other observable properties predict actual user behaviour.

**Scope:**

1. **Real-request logging (no production change):**
   - Extend `ChatResponse.telemetry` with matching metadata (`top_score`, `score_gap`, `candidate_confidences`, `match_sources`)
   - Add structured logging from `AssistantChatService` for capability selection events
   - Capture: request_text, session_id, candidates_presented, top_score, score_gap, candidate_count, interaction

2. **User feedback capture (minimal production change):**
   - Add `POST /assistant/capability/feedback` endpoint to `workflow_runner/api.py`
   - Records: session_id, action ("confirm"/"reject"/"select_alternative"), selected_capability_id
   - Does NOT execute capability
   - Does NOT change matching or decision policy
   - Returns acknowledgement only

3. **Validation analysis:**
   - Collect 100–200 real requests with user feedback
   - Compute: gap=0.0 rejection rate, top-1 selection rate, reformulation rate
   - Validate whether gap=0.0 predicts under-specified requests in production
   - Identify counterexamples (specific requests with gap=0.0, generic requests with gap>0)

4. **No production behaviour changes:**
   - No changes to `RelevanceMatcher`
   - No changes to `CapabilityActionPolicy`
   - No thresholds introduced
   - No autonomous execution

### What this enables

- Validation of gap=0.0 signal on real data
- Measurement of actual selection accuracy
- Evidence to support or reject decision-model hypotheses
- Foundation for principled candidate-presentation rules

### What this does NOT do

- Does NOT introduce thresholds
- Does NOT change the action policy
- Does NOT auto-execute capabilities
- Does NOT expose scores to users

---

## K. Summary

### What we know

1. **The synthetic corpus provides a promising signal:** `score_gap == 0.0` perfectly identifies under-specified requests in the current evaluation corpus.
2. **The signal is principled:** It is a mathematical property of the candidate set, not an arbitrary threshold.
3. **The signal is unvalidated:** It has only been tested on 70 synthetic examples with 16 artificially constructed capabilities.
4. **User feedback is the missing evidence:** We cannot measure selection accuracy without capturing user decisions.

### What we cannot yet know

1. Whether gap=0.0 generalizes to real user requests.
2. Whether users reject or reformulate when gap=0.0.
3. Whether specific requests ever produce gap=0.0 in production.
4. Whether the signal holds as the capability catalogue grows.

### The honest conclusion

> The gap=0.0 signal is the most promising evidence we have found for distinguishing under-specified requests from specific requests. But it has only been validated on a synthetic corpus. The next step is to gather real user requests and user-feedback data to determine whether the signal survives contact with reality. Until then, the current count-only policy remains the most defensible approach.

---

## Acceptance Criteria

21K is complete when:

1. **Real-request logging mechanism is identified and documented.** The smallest practical mechanism for collecting production requests with matching metadata is specified.

2. **User feedback mechanism is identified and documented.** The smallest coherent production change for capturing user selection/rejection is specified.

3. **score_gap == 0.0 hypothesis is validated or refuted.** Either:
   - Real data confirms gap=0.0 predicts under-specified requests, OR
   - Real data shows gap=0.0 does not generalize, in which case we explicitly document why.

4. **Decision boundary evidence is assessed.** We determine whether the collected evidence justifies a principled candidate-presentation rule.

5. **If evidence supports a rule, define 21L.** Specify the smallest coherent implementation, including exactly which evidence supports it.

6. **If evidence does not support a rule, explicitly document what is missing.** State why additional logic would be premature and what evidence is needed next.

---

*No production code was modified during this investigation.*
