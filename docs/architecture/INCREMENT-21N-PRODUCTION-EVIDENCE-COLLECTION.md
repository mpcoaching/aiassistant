# Increment 21N — Production Evidence Collection

**Status:** Implementation complete. No production behaviour changes.  
**Prerequisites:** Increments 21K (instrumentation), 21L (analysis), 21M (pilot) implemented.

---

## A. Objective

Move from synthetic evidence to real production user behaviour by deploying production-ready telemetry infrastructure that can collect, persist, and analyse capability-selection events with actual user outcomes.

---

## B. What Was Implemented

### 1. Persistent Telemetry Storage

**File:** `packages/ai/src/capability_selection_telemetry.py`

The `CapabilitySelectionTelemetry` class now supports:

- **File-based persistence:** Events are appended to a JSONL file as they occur.
- **Persistence path:** Configurable via `CAPABILITY_TELEMETRY_PATH` environment variable (default: `data/capability_selection_telemetry.jsonl`).
- **Load on startup:** Events are loaded from disk when the telemetry store is initialised.
- **Thread-safe:** All operations remain protected by the existing lock.

### 2. Session Correlation

**File:** `packages/ai/src/chat.py`

The `chat()` method now:
- Generates a single `session_id` at the start of the request
- Passes it to both `_execute_capability_response` and `_capability_selection_response`
- Passes it to `CapabilitySelectionTelemetry.record_match_event`

This enables:
- Tracking all capability-selection events within a single session
- Detecting when a user re-queries after seeing candidates (reformulation)

### 3. Reformulation Detection

**File:** `packages/ai/src/capability_selection_telemetry.py`

Added `get_reformulation_candidates()` method:
- Returns all events from sessions that contain multiple capability-selection events
- A session with 2+ events indicates the user re-queried after seeing candidates
- This is the primary signal for measuring whether candidate presentation was misleading

### 4. Admin / Export Endpoints

**File:** `packages/workflow_runner/api.py`

Added the following read-only endpoints for evidence collection:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/assistant/telemetry/events` | GET | List all recorded events |
| `/assistant/telemetry/sessions/{session_id}` | GET | List events for a specific session |
| `/assistant/telemetry/reformulations` | GET | List potential reformulation events |
| `/assistant/telemetry/stats` | GET | Summary statistics (outcomes, distributions) |
| `/assistant/telemetry/export` | POST | Export all events to JSON file |

**No behaviour changes:** These endpoints are observational only. They do not modify matching, scoring, candidate presentation, or execution.

### 5. Existing Feedback Endpoint

The `/assistant/capability/feedback` endpoint from 21K remains unchanged and continues to record user actions (confirm, reject, select_alternative).

---

## C. Files Changed

### Modified files

| File | Changes |
|------|---------|
| `packages/ai/src/capability_selection_telemetry.py` | Added persistence, session correlation, reformulation detection, export |
| `packages/ai/src/chat.py` | Session ID generation and propagation to telemetry |
| `packages/workflow_runner/src/composition.py` | No changes required |
| `packages/workflow_runner/api.py` | Telemetry persistence path, admin endpoints |
| `packages/ai/tests/test_assistant.py` | Added 4 new tests for session correlation and reformulation |
| `packages/workflow_runner/tests/test_capability_execute.py` | Added 5 new tests for admin endpoints |

### New files

None. All changes are additive to existing files.

---

## D. What Remains Unchanged

- `RelevanceMatcher` scoring algorithm
- `CapabilityActionPolicy` behaviour (0 → NoCapabilityMatch, 1 → confirm, 2+ → select)
- Candidate presentation rules
- Execution behaviour
- Architectural boundaries
- No new thresholds
- No new decision logic

---

## E. Production Deployment Checklist

To deploy 21N instrumentation to production:

1. **Set environment variable:**
   ```bash
   export CAPABILITY_TELEMETRY_PATH="/var/log/assistant/telemetry/capability_selection.jsonl"
   ```

2. **Ensure directory exists:**
   ```bash
   mkdir -p /var/log/assistant/telemetry
   ```

3. **Verify endpoints are accessible:**
   ```bash
   curl http://localhost:8000/assistant/telemetry/stats
   ```

4. **Collect events:** The system automatically records match events and user feedback via the existing `/assistant/capability/feedback` endpoint.

5. **Monitor reformulations:** Check `/assistant/telemetry/reformulations` periodically to detect users re-querying after seeing candidates.

6. **Export for analysis:** Use `/assistant/telemetry/export` to dump events for offline analysis.

---

## F. Evidence Collection Protocol

### Minimum viable dataset

| Requirement | Target |
|-------------|--------|
| Total requests | 100–200 |
| Requests with user feedback | 100–200 |
| gap=0.0 requests | ≥20 |
| Small gap (0.0–0.2) requests | ≥20 |
| Large gap (>0.5) requests | ≥20 |
| Reformulation events | As many as occur naturally |

### What to measure

1. **gap=0.0 rejection rate** — % of gap=0.0 requests where user rejects all candidates
2. **gap=0.0 reformulation rate** — % of gap=0.0 requests where user re-queries
3. **gap=0.0 alternative-selection rate** — % of gap=0.0 requests where user selects non-top candidate
4. **Top-1 selection rate** — % of requests where user selects top-ranked candidate
5. **Alternative selection rate** — % of requests where user selects non-top candidate
6. **Rejection rate** — % of requests where user rejects all candidates
7. **Reformulation rate** — % of requests where user re-queries after seeing candidates

### What NOT to do

1. Do NOT convert observed correlations into rules during data collection
2. Do NOT introduce thresholds based on preliminary data
3. Do NOT tune the matcher to "improve" signals
4. Do NOT treat user selection as absolute ground truth
5. Do NOT stop collection early based on suggestive patterns

---

## G. Analysis Readiness

The following analyses become possible once real data is collected:

### By score_gap
- Does gap=0.0 predict rejection/reformulation/alternative selection?
- Do specific requests ever produce gap=0.0?
- Do generic requests ever produce positive gaps?
- What happens at small positive gaps?

### By top_score
- Does top_score predict user satisfaction?
- Is there a score threshold below which users always reject?

### By candidate_count
- Does candidate count predict rejection?
- Do users reject large candidate sets?

### By combination
- Does gap=0.0 + top_score < 0.5 predict rejection?
- Does gap>0 + candidate_count ≥ 5 predict successful selection?

### By reformulation
- Do users reformulate after gap=0.0 presentations?
- Do users reformulate after seeing large candidate sets?

---

## H. Decision Framework

### When to stop collecting

Stop collecting and move to 21O (rule implementation) when ANY of the following is true:

1. **100+ requests collected** with confirmed outcomes AND
2. **Statistical significance achieved** (p < 0.05) for at least one signal predicting user outcome AND
3. **Counterexamples are explainable** (not systematic)

### When to continue collecting

Continue collecting when ANY of the following is true:

1. **Dataset < 100 requests**
2. **No signal reaches statistical significance**
3. **Counterexamples are systematic** (not random noise)
4. **The evidence is contradictory** (different signals point in different directions)

### Default assumption

**No behaviour change unless real evidence demonstrates one is warranted.**

---

## I. Test Results

All tests pass. No production behaviour was modified.

```
344 passed, 19 warnings in 1.96s
```

- `packages/ai/tests/` — 95 passed
- `packages/workflow_runner/tests/` — 156 passed
- `packages/capability_registry/tests/` — 93 passed

### New tests added

**`packages/ai/tests/test_assistant.py`:**
- `test_chat_records_session_id_in_telemetry` — Verifies explicit session_id is recorded
- `test_chat_generates_session_id_when_not_provided` — Verifies generated session_id is recorded
- `test_telemetry_session_correlation` — Verifies multiple events in same session are correlated
- `test_telemetry_reformulation_detection` — Verifies sessions with multiple events are detected

**`packages/workflow_runner/tests/test_capability_execute.py`:**
- `test_telemetry_events_endpoint_returns_empty_when_no_events` — Verifies empty events list
- `test_telemetry_events_endpoint_returns_events` — Verifies events are returned correctly
- `test_telemetry_session_endpoint_returns_session_events` — Verifies session filtering
- `test_telemetry_reformulations_endpoint_returns_reformulation_candidates` — Verifies reformulation detection
- `test_telemetry_stats_endpoint_returns_statistics` — Verifies statistics aggregation
- `test_telemetry_export_endpoint_exports_events` — Verifies JSON export

---

## J. Next Steps

### Immediate

1. Deploy 21N to a staging/production environment
2. Set `CAPABILITY_TELEMETRY_PATH` environment variable
3. Begin collecting real user requests with outcomes
4. Monitor reformulation rate as an early indicator

### After 100+ requests collected

1. Export telemetry data via `/assistant/telemetry/export`
2. Run the analysis from 21L/21M against real data
3. Determine whether evidence supports a principled candidate-presentation rule
4. If yes → proceed to 21O with the smallest behaviour change justified by evidence
5. If no → continue collection or accept that current policy is optimal

---

*No production behaviour was modified during this increment. All changes are additive instrumentation and observation infrastructure.*
