# Increment 21K — Measurement Instrumentation

## Scope

Implementation of the measurement instrumentation described in `INCREMENT-21K-INVESTIGATION.md`.

**What was built:** Observational telemetry for capability matching and selection events.

**What was explicitly not built:**
- No decision policy changes
- No thresholds
- No `score_gap == 0.0` rule
- No new architectural layer (no "assessment layer")
- No ConceptStore dependencies for measurement
- No changes to `RelevanceMatcher` scoring
- No changes to `CapabilityActionPolicy` behaviour

## Files Changed

### New files

- `packages/ai/src/capability_selection_telemetry.py` — Thread-safe in-memory telemetry store and event model.

### Modified files

- `packages/ai/src/chat.py` — Added optional `capability_selection_telemetry` dependency to `AssistantChatService`. Instrumented `_capability_selection_response` and `_execute_capability_response` to record match events. Added `record_capability_feedback` method.
- `packages/workflow_runner/src/composition.py` — Wired `capability_selection_telemetry` through `create_assistant`.
- `packages/workflow_runner/api.py` — Created `CapabilitySelectionTelemetry` instance, passed it to `create_assistant`, and added `POST /assistant/capability/feedback` endpoint.
- `packages/ai/tests/test_assistant.py` — Added 5 telemetry integration tests.
- `packages/workflow_runner/tests/test_capability_execute.py` — Added API test for feedback endpoint.
- `packages/ai/tests/test_architectural_boundaries.py` — Updated constructor parameter check to include new dependency.

## What is Instrumented

### Match events (recorded at candidate presentation time)

When `AssistantChatService` presents capability candidates to the user, it now records:

| Field | Source | Description |
|-------|--------|-------------|
| `event_id` | Generated UUID | Correlates match event with later user action |
| `timestamp` | `datetime.now(timezone.utc)` | When candidates were presented |
| `request_text` | `intent.raw["text"]` | Original user request |
| `session_id` | Currently `None` | Placeholder for future session correlation |
| `candidate_ids` | `[c.id for c in candidates]` | Ordered list of candidate IDs |
| `candidate_scores` | `[c.confidence for c in candidates]` | Ordered list of confidence scores |
| `top_score` | `candidate_scores[0]` | Highest confidence |
| `score_gap` | `top_score - second_score` (or `0.0` for single candidate) | Gap between top two |
| `candidate_count` | `len(candidates)` | Number of candidates |
| `interaction_type` | `"confirm"` or `"select"` | How candidates are presented |
| `user_action` | `None` until feedback received | `"confirm"`, `"reject"`, `"select_alternative"` |
| `selected_capability_id` | `None` until feedback received | ID of chosen capability |

### User feedback (recorded via endpoint)

`POST /assistant/capability/feedback` accepts:

```json
{
  "match_event_id": "uuid",
  "action": "confirm | reject | select_alternative",
  "selected_capability_id": "cap-id"  // optional
}
```

This updates the corresponding `CapabilitySelectionEvent` with the user's eventual action.

### Structured logging

Every match event and user action is also emitted as a structured log record via `logger.info` with the event fields as `extra` data, using the logger name `ai.capability_selection_telemetry`.

## Where Events Can Be Retrieved

1. **In-process:** `CapabilitySelectionTelemetry.get_events()` returns all recorded events. The API holds a single instance at module scope (`_capability_selection_telemetry`).
2. **Logs:** Structured log records with `event_id`, `request_text`, `candidate_scores`, etc. can be collected from the `ai.capability_selection_telemetry` logger.
3. **Response telemetry:** Each capability selection response includes `match_event_id` in its `telemetry` dict, allowing clients to correlate responses with later feedback submissions.

## Behaviour Preservation

The following behaviours are **unchanged**:

- 0 candidates → `NoCapabilityMatch` → falls through to pattern execution
- 1 candidate → `AskUserToSelect` with `interaction="confirm"`
- 2+ candidates → `AskUserToSelect` with `interaction="select"`
- Capability execution behaviour unchanged
- Response structure unchanged (only `telemetry` dict gains optional `match_event_id`)
- All existing tests pass (247 passed)

## Tests Added

### `packages/ai/tests/test_assistant.py`

- `test_chat_records_telemetry_for_single_candidate_confirm` — Verifies match event recorded with `interaction_type="confirm"`, `score_gap=0.0`, and `match_event_id` in response telemetry.
- `test_chat_records_telemetry_for_multiple_candidates_select` — Verifies match event recorded with `interaction_type="select"`, correct `score_gap`, and `match_event_id` in response telemetry.
- `test_chat_records_user_feedback` — Verifies `record_capability_feedback` updates the event with user action and selected capability.
- `test_chat_without_telemetry_unchanged` — Verifies existing behaviour when no telemetry dependency is provided.
- `test_telemetry_records_correct_scores_and_gap` — Verifies candidate scores and gap are recorded correctly for 3 candidates.

### `packages/workflow_runner/tests/test_capability_execute.py`

- `test_capability_feedback_endpoint_records_action` — Verifies the API endpoint correctly delegates to `record_capability_feedback` and returns the expected response.

## What Analysis Becomes Possible

With this instrumentation in place, the following correlations can be made:

1. **Request → Candidate relationship properties:** For each user request, we can see `candidate_count`, `top_score`, `score_gap`, and the full `candidate_scores` distribution.
2. **User outcome correlation:** By submitting feedback via `/assistant/capability/feedback`, we can correlate those request/candidate properties with whether the user confirmed, rejected, or selected an alternative.
3. **Discriminability signals:** We can now observe whether `score_gap == 0.0`, low `top_score`, high `candidate_count`, or other properties predict user rejection or reformulation.

## Next Step

**Increment 21L — Evidence Analysis.**

After collecting 100–200 real requests with user feedback, analyse which observable properties predict whether the presented candidates were useful. The hypothesis to test: `score_gap == 0.0` predicts rejection/reformulation, but it must compete against `candidate_count`, `top_score`, and other properties.

**Do not modify decision policy until evidence is collected.**
