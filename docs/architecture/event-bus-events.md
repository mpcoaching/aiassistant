# Event Bus — Workflow Mode Events

This document defines the **workflow-mode** event taxonomy consumed and
published by the Workflow Engine service.  It supplements
`docs/SYSTEM_CONTEXT.md` (Agent Bus standards) by separating workflow-mode
events from agentic-mode events so that the two domains can evolve
independently.

---

## 1.  Modes

| Mode | Purpose | Exchange |
|------|---------|----------|
| `workflow.mode` | Workflow Engine lifecycle, scheduling, control | `workflow.mode` (topic) |
| `agentic.mode` | Agent-instance events (existing) | `agentic.mode` (topic) |

Both exchanges use durable queues with dead-letter routing for failed
message processing, following the idempotency rules in `SYSTEM_CONTEXT.md`.

---

## 2.  Topology

```
producer (Workflow Engine) ──►  workflow.mode exchange
                                      │
                                      ├────▶ queue: workflow.executions
                                      │          consumer: Workflow Engine
                                      │
                                      ├────▶ queue: workflow.lifecycle
                                      │          consumer: Control Center (SSE)
                                      │
                                      └────▶ queue: workflow.control
                                                 consumer: Workflow Engine

DLX: workflow.dead
```

---

## 3.  Event Schemas

All events share the envelope:

```json
{
  "event_id": "<uuid>",
  "event_type": "<string>",
  "timestamp": "<ISO-8601>",
  "workflow_id": "<execution id>",
  "correlation_id": "<optional parent correlation>",
  "payload": {}
}
```

### 3.1  `WorkflowRequested`

Request to start (or schedule) a workflow execution.

```json
{
  "event_type": "WorkflowRequested",
  "payload": {
    "workflow_name": "requirements.analysis.define-requirements",
    "initial_context": {},
    "role_override": null,
    "trigger": "manual" | "scheduled" | "event",
    "schedule_id": null
  }
}
```

### 3.2  `WorkflowStarted`

Emitted when the engine picks up a `WorkflowRequested` and begins execution.

```json
{
  "event_type": "WorkflowStarted",
  "payload": {
    "workflow_id": "abc123",
    "workflow_name": "requirements.analysis.define-requirements",
    "total_steps": 5
  }
}
```

### 3.3  `StepStarted`

Emitted before each step begins executing.

```json
{
  "event_type": "StepStarted",
  "payload": {
    "workflow_id": "abc123",
    "step_index": 2,
    "step_name": "draft-requirements",
    "step_type": "skill",
    "estimated_duration_seconds": null
  }
}
```

### 3.4  `StepCompleted`

Emitted after each step finishes (success or failure).

```json
{
  "event_type": "StepCompleted",
  "payload": {
    "workflow_id": "abc123",
    "step_index": 2,
    "step_name": "draft-requirements",
    "status": "completed" | "failed",
    "output": {},
    "error": null,
    "duration_seconds": 12.3
  }
}
```

### 3.5  `WorkflowCompleted`

Emits when all steps complete successfully.

```json
{
  "event_type": "WorkflowCompleted",
  "payload": {
    "workflow_id": "abc123",
    "final_context": {},
    "total_duration_seconds": 45.2
  }
}
```

### 3.6  `WorkflowFailed`

Emits when execution aborts due to a step failure or system error.

```json
{
  "event_type": "WorkflowFailed",
  "payload": {
    "workflow_id": "abc123",
    "error": "Step 'review' failed: …",
    "failed_step": "review",
    "completed_steps": 3
  }
}
```

### 3.7  `WorkflowPaused`

Emits when `POST /workflows/{id}/pause` is called or a `WorkflowControl`
event with action `pause` is received.

```json
{
  "event_type": "WorkflowPaused",
  "payload": {
    "workflow_id": "abc123",
    "paused_step_index": 3,
    "reason": "user_requested"
  }
}
```

### 3.8  `WorkflowResumed`

Emits when a paused workflow resumes.

```json
{
  "event_type": "WorkflowResumed",
  "payload": {
    "workflow_id": "abc123",
    "resuming_step_index": 3
  }
}
```

### 3.9  `WorkflowStopped`

Emits when execution is terminated (`stop` action or `exit` signal).

```json
{
  "event_type": "WorkflowStopped",
  "payload": {
    "workflow_id": "abc123",
    "reason": "user_requested" | "system_shutdown" | "timeout",
    "completed_steps": 2
  }
}
```

### 3.10  `ScheduleCreated` / `ScheduleRemoved`

Emitted when APScheduler creates or removes a scheduled workflow.

```json
{
  "event_type": "ScheduleCreated",
  "payload": {
    "schedule_id": "sched-001",
    "workflow_name": "reports.daily",
    "cron": "0 8 * * *",
    "next_fire_time": "2026-07-11T08:00:00Z"
  }
}
```

---

## 4.  Control Events

### 4.1  `WorkflowControl`

Synchronous control command routed to the engine's local consumer.

```json
{
  "event_type": "WorkflowControl",
  "payload": {
    "workflow_id": "abc123",
    "action": "pause" | "resume" | "stop"
  }
}
```

---

## 5.  Idempotency & Ordering Rules

Per `docs/SYSTEM_CONTEXT.md`:

1. **Idempotent consumers** — Every queue consumer deduplicates by `event_id`
   or `workflow_id` before applying side-effects.
2. **Out-of-order tolerance** — Control events (`pause`, `resume`, `stop`)
   are buffered and applied in chronological order per workflow.
3. **Dead-letter routing** — Poison messages are routed to `workflow.dead`
   after three failed attempts so they do not block the queue.

---

## 6.  RabbitMQ Configuration

| Exchange | Type | Durable | Auto-delete |
|----------|------|---------|-------------|
| `workflow.mode` | topic | yes | no |
| `agentic.mode` | topic | yes | no |
| `workflow.dead` | topic | yes | no |

Queues are declared with `durable=True` and bound with wildcard routing keys
(`workflow.*` for lifecycle, `workflow.control` for control).

---

## 7.  Routing Keys

| Event | Routing Key |
|-------|-------------|
| `WorkflowRequested` | `workflow.executions` |
| `WorkflowStarted` | `workflow.lifecycle` |
| `StepStarted` | `workflow.lifecycle` |
| `StepCompleted` | `workflow.lifecycle` |
| `WorkflowCompleted` | `workflow.lifecycle` |
| `WorkflowFailed` | `workflow.lifecycle` |
| `WorkflowPaused` | `workflow.lifecycle` |
| `WorkflowResumed` | `workflow.lifecycle` |
| `WorkflowStopped` | `workflow.lifecycle` |
| `ScheduleCreated` | `workflow.lifecycle` |
| `ScheduleRemoved` | `workflow.lifecycle` |
| `WorkflowControl` | `workflow.control` |
