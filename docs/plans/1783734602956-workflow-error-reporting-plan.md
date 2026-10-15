# Phase 1 — Workflow Engine: Error Reporting & Step Events Gap

## Goal
Ensure workflow progress (step-level) flows to the event bus, errors are reliably reported, and failures are surfaced so they can be logged and fixed.

## What Already Works
- Workflow execution via `POST /workflows/{name}/run` (sync in Phase 1)
- `WorkflowStarted`, `WorkflowCompleted`, `WorkflowFailed`, `WorkflowPaused`, `WorkflowResumed`, `WorkflowStopped`, `ScheduleCreated`, `ScheduleRemoved` published to RabbitMQ
- State persisted to Postgres (`workflow_instances`, `step_results`, `schedules`) with JSON file fallback
- `GET /workflows/{id}/status` returns status, step_results, error
- Bus consumers for `WorkflowRequested` and `WorkflowControl`

## Gaps Blocking the Goal

| # | Gap | Impact |
|---|-----|--------|
| 1 | `StepStarted` / `StepCompleted` events defined in `bus.py` but **never emitted** during execution | No real-time progress tracking on the bus; Control Center cannot show live step status |
| 2 | `WorkflowFailed` payload misses `failed_step` per `event-bus-events.md` spec | Cannot easily identify which step caused failure from the bus event |
| 3 | `bus.publish()` swallows failures with bare `except Exception: pass` (lines 112-118) | If RabbitMQ is down, errors are NOT reported to the bus — the primary reporting path is lost with no alert |
| 4 | Same bare-exception pattern in `db.py` | Step results / state may silently not be persisted |
| 5 | Bus consumer threads set `self._running = False` only in `shutdown()`, not in their `_run()` loops | Threads may keep running after shutdown request; no cleanup confirmation |

## Implementation Plan

### Task 1: Emit step-level events from execution pipeline
**Files:**
- `agentic/src/workflow-runner/executor.py` — add optional `bus` parameter and callback hooks
- `agentic/src/workflow-runner/api.py` — pass bus into executor and emit events

Implementation:
1. Add `on_step_start(step, index)` and `on_step_complete(step, result, index)` optional callbacks to `execute_workflow()` (default `None`). Call them at lines 82-83 and lines 97-102 respectively.
2. In `_execute_and_publish()`, before calling `execute_workflow()`, construct callables that call `bus.publish_step_started()` and `bus.publish_step_completed()`.
3. Pass them through to `execute_workflow()`.

### Task 2: Include `failed_step` in `WorkflowFailed` events
**File:** `agentic/src/workflow-runner/api.py`

Implementation:
- In `_execute_and_publish()` catch block and the `summary["status"] == "failed"` block, include `failed_step: state.steps[state.current_step_index].name if state.current_step_index < len(state.steps) else None` in the payload.

### Task 3: Make bus publish failures visible (not silently dropped)
**File:** `agentic/src/workflow-runner/bus.py`

Implementation:
- Add a publish-failure counter or logger.warning (in addition to the existing logger.exception) so that failed publishes don't get completely swallowed.
- Add retry: on `pika.exceptions.AMQPConnectionError`, retry up to 3 times with backoff before giving up.
- If all retries fail, write the event to a local fallback file (`.events/` directory) so events survive bus outages and can be replayed.

### Task 4: Make db.py write failures visible
**File:** `agentic/src/workflow-runner/db.py`

Implementation:
- Replace bare `except Exception: pass` blocks with logging + re-raise or return error status.
- For insert failures, fall back to `.wf/` JSON file write (the existing fallback mechanism).

### Task 5: Fix consumer shutdown lifecycle
**File:** `agentic/src/workflow-runner/bus.py`

Implementation:
- Pass `self._running` into the consumer thread loop and check it in a `try/except KeyboardInterrupt` or connection-lost block.
- Set `self._running = False` when the consumer loop exits (not just in `shutdown()`).

## Validation
1. Run a workflow — `StepStarted` / `StepCompleted` events appear on the `workflow.lifecycle` queue
2. Make a workflow step fail — `WorkflowFailed` event includes `failed_step` and `error`
3. Stop RabbitMQ, run a workflow — events fall back to `.events/` files (not silently lost)
4. Restart RabbitMQ — `.events/` files are replayed on bus reconnect
5. `POST /stop` while running — consumer shuts down cleanly, `_running == False`

## Out of Scope
- Control Center UI wiring (existing `lifecycle` queue consumer is enough for the UI to subscribe)
- LangGraph graph definition and runtime_client.py (noted elsewhere)
