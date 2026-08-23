# Increment 21E Investigation: Ranked Candidate Presentation

**Status:** Read-only investigation. No code changes.  
**Prerequisites:** Increment 21D implemented — `AskUserToSelect` carries `interaction="confirm"` for single candidates and `interaction="select"` for multiple candidates. No confidence threshold introduced. Autonomous execution remains deferred.

---

## A. Current Candidate Presentation

The `ChatResponse` model exposes candidates through:

```python
capability_candidates: list[dict[str, Any]] | None = None
```

Each candidate dict currently contains:

```python
{
    "id": cap.id,
    "name": cap.name,
    "description": cap.description,
    "kind": cap.kind,
    "execution_mode": cap.execution_mode,
    "tags": cap.tags,
}
```

**What is NOT included:**
- `confidence` (relevance score)
- `rank` or position
- Any explicit indication that the list is ordered by relevance

**Ordering:** The list is ordered by `RelevanceMatcher`'s internal scoring (highest score first). This ordering is implicit in the array position but not explicitly labelled.

**Client:** The repository contains no frontend/client code. The response is served via FastAPI at `/assistant/chat`. The client is an external UI that consumes this API.

---

## B. Actual UX Problem

### What the client receives today

**Single candidate (confirm):**
```json
{
  "status": "awaiting_capability_selection",
  "message": "I found create_test_artifact. Shall I proceed with this capability?",
  "capability_candidates": [
    {
      "id": "cap-create_test_artifact",
      "name": "create_test_artifact",
      "description": "Creates a test artifact record",
      "kind": "tool",
      "execution_mode": "compiled",
      "tags": ["test", "artifact"]
    }
  ]
}
```

**Multiple candidates (select):**
```json
{
  "status": "awaiting_capability_selection",
  "message": "I found 2 capabilities that might help. Please select one to proceed...",
  "capability_candidates": [
    {
      "id": "cap-create_test_artifact",
      "name": "create_test_artifact",
      "description": "Creates a test artifact record",
      "kind": "tool",
      "execution_mode": "compiled",
      "tags": ["test", "artifact"]
    },
    {
      "id": "cap-send_email",
      "name": "send_email",
      "description": "Sends an email notification",
      "kind": "tool",
      "execution_mode": "compiled",
      "tags": ["email", "notification"]
    }
  ]
}
```

### Is there a real UX problem?

**For single candidates:** No. The user is asked to confirm a specific capability. The name, description, and tags are sufficient.

**For multiple candidates:** The user receives a list of capabilities with names, descriptions, and tags, ordered from most relevant to least relevant. This is functional. The user can read the names and descriptions to decide.

**The gap:** The client does not know the list is ordered by relevance. A UI rendering this list might show items in array order without indicating that the first item is the matcher's top choice.

**However:** This is a presentation concern, not a missing-information problem. The ranking is already present in the data. The client can choose to:
1. Render the first item as the default/top choice
2. Add a "Recommended" badge to the first item
3. Mention in the UI that candidates are ranked by relevance

None of these require backend changes.

### Is raw score exposure justified?

No. The investigation established that the relevance score is:
- Deterministic keyword overlap
- NOT calibrated probability
- NOT a measure of intent confidence
- NOT a measure of execution success probability

Exposing `0.82` to users would imply semantics the number does not have. A user might interpret `0.82` as "82% confident" or "82% likely to succeed" — both of which are false.

### Is ranking already visible?

Yes. The candidates are returned in relevance order. The first candidate in the array is the highest-scoring candidate. This is already visible to any client that renders the list in order.

---

## C. Score Semantics

| Term | What it represents | What it does NOT represent |
|------|--------------------|---------------------------|
| **Relevance score** | Weighted token overlap between request and capability metadata | Probability of correct selection |
| **Confidence** | (Already on `CapabilityCandidate`) — same as relevance score | Calibrated confidence |
| **0.8** | 80% of request tokens matched across name/description/tags | 80% chance this is the right capability |

**Conclusion:** Raw scores must NOT be exposed to users. They are internal matching metadata, not user-facing confidence.

---

## D. Ranking Semantics

The current ordering IS the ranking. `RelevanceMatcher.match()` sorts candidates by score descending before returning them. The `CapabilityDiscoveryAdapter` preserves this order. The `CapabilityActionPolicy` preserves this order. The chat service preserves this order in the response.

**The ranking is already end-to-end.** What is missing is an explicit label, but the data itself is already ordered.

---

## E. Candidate Information

### Currently available to the client

| Field | Type | Purpose |
|-------|------|---------|
| `id` | str | Capability identifier for selection/execution |
| `name` | str | Human-readable name |
| `description` | str | What the capability does |
| `kind` | str | Capability type (tool, service, etc.) |
| `execution_mode` | str | How it runs (compiled, ai_mediated, etc.) |
| `tags` | list[str] | Categorisation keywords |

### What is missing

| Field | Purpose | Needed? |
|-------|---------|---------|
| `confidence` | Internal relevance score | No — internal only |
| `rank` | Explicit position | No — implicit in list order |
| `rationale` | Why this matched | Nice-to-have, but requires matcher to generate human-readable explanations |
| `matcher_id` | Which matcher produced this | No — always `relevance` in current architecture |

**Assessment:** The client already has enough structured information to present a meaningful selection UI. The name, description, tags, kind, and execution_mode are sufficient for a user to make an informed choice.

---

## F. Future Decision Requirements

The architecture will eventually need to distinguish:

- dominant candidate
- ambiguous candidates
- weak candidates
- no meaningful match

For this, the system will eventually need:

| Signal | Current state | Future need |
|--------|--------------|-------------|
| `top_score` | Available in `MatchResult` | May need to flow through to action policy |
| `second_score` | Available in `MatchResult` | May need to flow through |
| `score_gap` | Computable from above | May need explicit field |
| `candidate_count` | Available | Already used |
| `request_specificity` | Not explicitly computed | May need heuristic or model |

**These are internal signals, not user-facing data.** They belong in the action policy or a future assessment layer, not in the client response.

---

## G. Options

### Option 1: Expose raw scores (REJECTED)

Add `confidence` to each candidate dict in the response.

**Why rejected:** Scores are not calibrated probabilities. Exposing `0.82` to users creates false precision and implies semantics the number does not have.

### Option 2: Expose ranked candidates only (current state)

Candidates are already ordered by relevance. No backend change needed.

**Pros:** Honest, simple, sufficient.  
**Cons:** The ranking is implicit, not explicit. A client may not realise the list is ordered by relevance.

### Option 3: Add explicit rank field

Add `rank: 1`, `rank: 2`, etc. to each candidate dict.

**Pros:** Makes ranking explicit.  
**Cons:** Redundant with array position. Adds a field that clients can already infer.

### Option 4: Add richer candidate descriptions

Include more metadata (e.g., interface signature, payload details).

**Pros:** More information for the user.  
**Cons:** Increases payload size. Most metadata is already present. The current fields are sufficient for selection.

### Option 5: Add qualitative relevance labels

Map scores to labels like "strong match", "possible match", "weak match".

**Pros:** More user-friendly than raw numbers.  
**Cons:** Requires calibration to define label boundaries. Currently impossible without arbitrary thresholds.

### Option 6: Do nothing

The current response is already sufficient.

**Pros:** No change needed. Honest. No false precision.  
**Cons:** Ranking is implicit, not explicit.

---

## H. Recommendation

**Recommend: Do nothing for 21E. Defer ranked presentation.**

The current candidate presentation is already sufficient:

1. **Ranking is already implicit.** Candidates are returned in relevance order. Any client that renders the list in order already presents them as ranked.

2. **Metadata is sufficient.** Name, description, tags, kind, and execution_mode give the user enough information to make a selection decision.

3. **Scores must not be exposed.** The relevance score is internal matching metadata, not user-facing confidence. Exposing it would create false precision.

4. **No demonstrated gap.** There is no evidence in the repository that the client or users are unable to make selections with the current information.

5. **Any future ranking/dominance work belongs in the action policy, not the presentation layer.** When the system is ready to distinguish dominant from ambiguous candidates, that distinction should be made in `CapabilityActionPolicy` (as a new action or mode), not by exposing raw scores to users.

### If a message change is desired

The only potential improvement is to update the selection message to indicate that candidates are ranked by relevance:

Current: "I found 2 capabilities that might help. Please select one to proceed..."
Proposed: "I found 2 capabilities that might help, ranked by relevance. Please select one to proceed..."

This is a one-line change in `chat.py` that makes the ranking explicit without exposing scores. However, this is optional and may be unnecessary if the client already renders the list in a way that implies ordering.

---

## I. Implementation Plan

If the message change is desired:

| File | Change |
|------|--------|
| `packages/ai/src/chat.py` | Update message in `_capability_selection_response()` to include "ranked by relevance" for multi-candidate cases |

If no change is desired:

No implementation required. Defer 21E until there is evidence of an actual UX gap.

---

## J. Explicit Non-Goals

| Item | Why Deferred |
|------|--------|
| **Raw score exposure** | Scores are not calibrated. Would create false precision. |
| **Confidence percentage displays** | Same reason. |
| **Qualitative relevance labels** | Requires arbitrary thresholds. No calibration basis. |
| **Rank field in response** | Redundant with list order. |
| **Dominance pre-selection** | Requires arbitrary gap threshold. Deferred until evidence-based. |
| **Separate assessment layer** | Premature abstraction. |
| **Evidence-informed ranking** | Evidence is too sparse. |
| **Calibration corpus** | Useful long-term but not the smallest next step. |

---

## Summary

The original 21E recommendation to "expose relevance scores in the selection response" should be rejected. The relevance score is internal matching metadata, not user-facing confidence. The current candidate presentation is already sufficient: candidates are returned in relevance order with rich metadata (name, description, tags, kind, execution_mode). The client has everything it needs to present a meaningful selection UI. The ranking is implicit in the list order. If any change is made, it should be at most a message wording update to indicate that candidates are ranked by relevance — not exposing the scores themselves.

The next meaningful architectural step is not presentation. It is to develop the decision model that can eventually distinguish dominant, ambiguous, and weak candidates — but that distinction belongs in `CapabilityActionPolicy` as internal logic, not in the client response.
