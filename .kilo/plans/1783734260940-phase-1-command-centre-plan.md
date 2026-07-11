# Phase 1 — Command Centre & Workflow Engine: Implementation Plan

## 1. Where your documents live (the "phase 1" info you were looking for)

| Document | Path | What it says |
|---|---|---|
| Phase 1 ABBs (capabilities) | `docs/architecture/Phase-1-ABBs.md` | Control Center, Work Session Mgmt, Daily Task Tracking, Lead Enrichment |
| Phase 1 SBBs (services) | `docs/architecture/Phase-1-SBBs.md` | Control Center UI, Workflow Engine, Work Session Svc, Task Tracking Svc, Lead Enrichment Svc |
| Phase 1 Backlog | `docs/architecture/Phase-1-BACKLOG.md` | Discovery items, most still status `AD` |
| Control Center ABB | `agentic/docs/architecture/abb/Control_Center.md` | Trigger/schedule/monitor workflows, stop/pause/resume, suggestions, chat |
| Automated Task Execution ABB | `agentic/docs/architecture/abb/automated_task_execution.md` | Define/schedule/orchestrate/monitor |
| EA Roadmap | `agentic/docs/context/ea/ROADMAP.md` | Same Phase 1 goal, "placing requests onto the agentic bus" |
| System Context | `docs/SYSTEM_CONTEXT.md` | Single "Agent Bus" (Event Bus pattern); currently conflates workflow + agentic events |
| Existing Workflow Runner | `agentic/src/workflow-runner/` + `agentic/docs/architecture/sa/utilities/workflow-runner/` | Loader, composer, **executor**, **server.py (MCP stdio)**, state, handlers |

**Gap:** The docs say "use the agentic bus for workflow execution," but they never separate **workflow-mode events** from **agentic-mode (agent-instance) events**. Your Phase 1 command centre only needs the former. We close that gap below.

## 2. Resolved decisions

1. **Event bus = RabbitMQ** (canonical Agent Bus, already in `docker-compose.yml` under `profiles: ["disabled"]`). Workflow-mode events and agentic-mode events live on separate exchanges/topics. Redis (`redis-agents` on `ai_net`) is used for caching + live UI status streaming (pub/sub → SSE/WebSocket).
2. **Control Center UI = custom React/Vue SPA** behind nginx, talking to the Workflow Engine REST API and subscribing to live status.
3. **Scheduling IS in scope for Phase 1** — a Scheduler (APScheduler) that enqueues `WorkflowRequested` events onto RabbitMQ at configured times.
4. **Agentic roles maintain the Pattern Catalogue as a Phase 1 workstream** — patterns at EA/SA/design/dev/test levels, each a reusable role+skill+workflow template; roles update them via a `maintain-pattern` workflow. Goal: coding = pick a pattern.
5. **Skill-step execution binds to the LangGraph runtime** (already in stack, `:8000`) via the existing Runtime Interface (`start/send/add/drop/run/exit`). The Workflow Engine sends composed prompts to LangGraph so workflows run autonomously to completion.

## 3. Target architecture (all containers in your existing `ai_net` stack)

```
Control Center SPA (nginx)
   │  REST (trigger / status / schedule / pause / resume / stop)
   ▼
Workflow Engine  (FastAPI + RabbitMQ consumer/producer + APScheduler + LangGraph client)
   │  ├─ consumes workflow-mode events: WorkflowRequested, WorkflowControl(pause/resume/stop)
   │  ├─ executes via: loader → composer → handler → LangGraph runtime (skill steps)
   │  └─ publishes workflow-mode events: WorkflowStarted, StepStarted, StepCompleted,
   │       WorkflowCompleted, WorkflowFailed, WorkflowPaused, WorkflowStopped
   ▼                                            ▲
RabbitMQ (exchanges: workflow.mode / agentic.mode)   │ (status fan-out)
                                                    ▼
                                              Redis pub/sub → SSE → SPA (live status)
Postgres  ← Workflow Engine persistent state (instances, schedules, step results)
LangGraph  ← executes skill-step prompts
```

Promote `agentic/src/workflow-runner/` into the **Workflow Engine** service: keep `loader.py`, `composer.py`, `state.py`, `models.py`, `handlers/*`, `executor.py` as the core; add `api.py` (FastAPI), `bus.py` (RabbitMQ producer/consumer), `scheduler.py` (APScheduler), `runtime_client.py` (LangGraph binding), and `Dockerfile`. The MCP `server.py` stays as an alternate entrypoint for agent-driven invocation.

**Known limitation to fix:** `executor.execute_workflow` currently *composes* skill prompts and returns them for an external caller (`server.py` does this). For autonomous Phase 1 execution, `handle_skill_step` must send the composed prompt to the LangGraph runtime and await the result, then advance state — matching the technical-design Runtime Interface.

## 4. Implementation task list

1. **Event taxonomy doc** — create `docs/architecture/event-bus-events.md` defining workflow-mode vs agentic-mode event schemas, routing, exchanges/topics, and idempotency rules (reuse `docs/SYSTEM_CONTEXT.md` standards). Update `Phase-1-ABBs.md`, `Phase-1-SBBs.md`, `ROADMAP.md`, `SYSTEM_CONTEXT.md` to say "workflow-mode events on the Agent Bus" rather than the ambiguous "agentic bus for workflow execution."
2. **Enable RabbitMQ** — remove `profiles: ["disabled"]` from the `rabbitmq` service; add a default exchange/queue setup step (init container or bootstrapper). Add `RABBITMQ_*` env to `.env`.
3. **Workflow Engine REST API** (`api.py`) — endpoints: `GET /workflows`, `POST /workflows/{name}/run`, `POST /workflows/{id}/schedule`, `GET /workflows/{id}/status`, `POST /workflows/{id}/pause|resume|stop`, `GET /schedules`. Loads definitions from `agentic/docs/workflows` + `agentic/workflows` (reuse `loader.resolve_workflow_path`).
4. **Bus integration** (`bus.py`) — consume `WorkflowRequested`/`WorkflowControl`; publish lifecycle events; consumer is idempotent (dedupe by `workflow_id`), per `SYSTEM_CONTEXT.md`.
5. **Runtime binding** (`runtime_client.py`) — implement Runtime Interface against LangGraph `:8000`; `handle_skill_step` calls it instead of returning a prompt. Keep Aider runtime as a secondary adapter.
6. **Scheduler** (`scheduler.py`) — APScheduler persists schedules in Postgres; on fire, publishes `WorkflowRequested` with `trigger=scheduled`.
7. **State persistence** — move from file-based `.wf/*.json` to Postgres (new `workflow_instances`, `step_results`, `schedules` tables via `ai-assistant-infra/migrations`). Keep JSON-log append for audit. (Decision to confirm: Postgres now vs keep file-based + Redis for Phase 1.)
8. **Containerize Workflow Engine** — `agentic/src/workflow-runner/Dockerfile` + service entry in `docker-compose.yml` (`workflow-engine`, on `ai_net`, depends on `rabbitmq`, `postgres`, `langgraph`, `redis-agents`).
9. **Control Center SPA** — React/Vue app: workflow list/trigger, schedule editor, live status board (SSE from a small status adapter that subscribes to Redis), stop/pause/resume controls, suggestions/chat panel (stub for Phase 1). nginx route in `ai-assistant-infra/configs/nginx/nginx.conf`.
10. **Pattern Catalogue** — define schema (`agentic/__patterns/README.md` + `pattern.schema.yaml`) across EA/SA/design/dev/test; convert `data-mapper.md` to the new schema as the seed; add a `maintain-pattern` workflow + a role-owner field so each role (ea/sa/designer/developer/test-engineer) maintains its level; expose patterns so the SPA can "pick a pattern" to scaffold work.
11. **Update `Phase-1-BACKLOG.md`** — mark Workflow Engine / Control Center / scheduling items to `SD`/`C` with links to the new design docs; note deferred SBBs (Work Session, Task Tracking, Lead Enrichment) stay `AD`.

## 5. Documents to create / update

- **Create:** `docs/architecture/event-bus-events.md`, `agentic/__patterns/pattern.schema.yaml`, `agentic/__patterns/README.md`, `agentic/docs/workflows/maintain-pattern.yaml`, `agentic/src/workflow-runner/Dockerfile`, `agentic/src/workflow-runner/{api,bus,scheduler,runtime_client}.py`.
- **Update:** `docs/architecture/Phase-1-ABBs.md`, `Phase-1-SBBs.md`, `Phase-1-BACKLOG.md`, `docs/SYSTEM_CONTEXT.md`, `agentic/docs/context/ea/ROADMAP.md`, `agentic/docs/architecture/sa/utilities/workflow-runner/*` (reflect service + runtime binding), `docker-compose.yml`, `ai-assistant-infra/configs/nginx/nginx.conf`, role docs (`agentic/docs/roles/*`) to add pattern-ownership.

## 6. Open questions / elaboration still required

- **State store for Phase 1:** Postgres now (cleaner, persistent, multi-instance safe) vs keep `.wf/` JSON + Redis. Recommend Postgres.
- **Authn/z:** Control Center needs auth; backlog lists it as open. Reuse an existing mechanism in the stack if present, else defer to a thin API key for Phase 1.
- **Workflow discovery scope:** Phase 1 engine should load the existing `requirements.*` and `ea.*` workflows as the first runnable catalogue; confirm which workflows are "Phase 1 ready."
- **LangGraph graph:** Confirm LangGraph `:8000` exposes a prompt-in/result-out endpoint compatible with the Runtime Interface, or whether a thin adapter graph is needed.
- **Pattern Catalogue granularity:** define exactly how a "pattern" differs from a "workflow" + "skill" (a pattern = opinionated composition + rationale + when-to-use), so roles maintain it without overlap.

## 7. Validation

- `docker compose up rabbitmq postgres langgraph workflow-engine` starts cleanly; engine health endpoint green.
- `POST /workflows/{requirements.analysis.define-requirements}/run` with `-c` context → `WorkflowRequested` published → engine consumes → LangGraph executes skill steps → lifecycle events emitted → instance reaches `completed`; `GET /status` reflects each step.
- Scheduler: create a schedule, advance fake clock / wait, confirm a `scheduled` `WorkflowRequested` fires and runs.
- Control Center SPA lists workflows, triggers one, shows live step progress via SSE, and supports pause/resume/stop.
- Idempotency: republish a `WorkflowRequested` with same `workflow_id` → no duplicate execution.
- Pattern Catalogue: `maintain-pattern` workflow runs under the owning role and updates a pattern; SPA can list/select patterns.
