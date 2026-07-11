# Phase 1 — Command Centre & Workflow Engine: Implementation Plan

## 1. Where your documents live

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

**Gap:** The docs say "use the agentic bus for workflow execution," but they never separate **workflow-mode events** from **agentic-mode (agent-instance) events**. We need a clear microservice decomposition where each bounded context runs in its own container and communicates via APIs.

---

## 2. Service Decomposition — PHASE 1 ACTIVE SERVICES ONLY

These are the containers that must exist for Phase 1. Each is independently deployable and communicates via API boundaries.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        docker-compose.yml                           │
│                                                                     │
│  ┌──────────────┐      ┌───────────────┐      ┌────────────────┐  │
│  │   nginx      │──────▶│  control-    │      │                │  │
│  │  (proxy +    │      │  center-ui   │      │                │  │
│  │   SPA static)│      │  (stub)      │      │                │  │
│  └──────────────┘      └───────────────┘      │                │  │
│        │                                      │                │  │
│        │ HTTP REST                            │   postgres     │  │
│        │                                      │  (state store) │  │
│        │                                      │                │  │
│        │                                      │   rabbitmq     │  │
│        │                                      │  (event bus)   │  │
│        │                                      │                │  │
│  ┌────▼──────────┐      ┌──────────▼───────┐  │                │  │
│  │ langgraph     │      │ workflow-engine  │  │                │  │
│  │ (runtime)     │◄─────│  (orchestrator)  │  │                │  │
│  │  :8000        │HTTP  │     :8000        │  │                │  │
│  └───────────────┘      └──────────────────┘  │   redis-agents │  │
│        ▲                                      │  (pub/sub)    │  │
│  execs skill prompts                       └────────────────┘  │
│  (another bounded context)                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 Service: `langgraph` (Runtime)
- **Bounded context:** AI prompt execution for skill steps
- **Current location:** `agents/langgraph/`
- **Interfaces:** HTTP API on :8000 (POST /threads, POST /threads/{id}/runs, etc.)
- **Swappability:** High — only `runtime_client.py` in the Workflow Engine needs to change to swap to a different runtime (e.g., Aider, OpenCode, custom)

### 2.2 Service: `workflow-engine` (Orchestrator)
- **Bounded context:** Workflow loading, orchestration, state management, API exposure
- **Source code location:** `agentic/src/workflow-runner/` (library) + service layer modules
- **Container:** Own Dockerfile + docker-compose service entry
- **Interfaces:**
  - REST API on :8000 (POST /workflows/{name}/run, GET /workflows/{id}/status, etc.)
  - RabbitMQ consumer/producer (workflow execution events)
  - Postgres client (workflow state persistence)
  - HTTP client to `langgraph` (skill execution)
- **Swappability:** Medium — can swap orchestrator runtime, event store, or scheduler independently

### 2.3 Service: `control-center-ui` (Frontend)
- **Bounded context:** User interface for workflow management
- **Phase 1:** Static SPA served via nginx, calling Workflow Engine REST API + SSE from Redis
- **Later:** Full React/Vue app with real-time updates

### 2.4 Services: `postgres`, `rabbitmq`, `redis-agents`
- **Bounded context:** Infrastructure (state, events, pub/sub)
- **Standard containers** — already in docker-compose (rabbitmq needs profile removal)

---

## 3. Library vs Service — Code Layout

The key principle: **library code is reusable business logic; service code is infrastructure glue.**

### 3.1 Library: `agentic/src/workflow-runner/`
Pure Python library — framework-agnostic, container-aware, no Flask/FastAPI/pika/SQLAlchemy imports at the top level.

| Module | Type | Responsibility |
|--------|------|----------------|
| `models.py` | Library | Pydantic schemas for workflow/skill/tool/step |
| `loader.py` | Library | YAML loading, path resolution, normalization |
| `composer.py` | Library | Prompt composition from Role + Skill + Context |
| `executor.py` | Library | Step dispatch loop, state transitions |
| `handlers/*.py` | Library | Per-step-type execution logic |
| `state.py` | Library interface | State CRUD operations (delegates to adapter) |

### 3.2 Service adapters (runnable inside Workflow Engine container only)
These are infrastructure adapters — they import heavy frameworks and should be lazy-importable.

| Module | Type | Responsibility | Swappable? |
|--------|------|----------------|------------|
| `runtime_client.py` | Adapter | LangGraph HTTP API binding | Yes (swap runtime) |
| `db.py` | Adapter | Postgres + file-fallback persistence | Yes (swap state store) |
| `bus.py` | Adapter | RabbitMQ producer/consumer | Yes (swap message broker) |
| `api.py` | Service | FastAPI REST endpoints | Yes (swap API framework) |
| `scheduler.py` | Service | APScheduler with Postgres job store | Yes (swap scheduler) |

### 3.3 Entrypoint
The Workflow Engine container runs ONLY `api.py` (which starts FastAPI + bus consumer + APScheduler). The MCP `server.py` remains as an alternate entrypoint for agent-driven invocation.

---

## 4. Key Design Decisions

### 4.1 Microservice Boundaries
- **Workflow Engine** owns workflow loading, orchestration, state management, API exposure, scheduling, and bus consumption.
- **LangGraph** owns AI prompt execution. It does NOT know about workflows, states, or events.
- **Postgres** owns persistent state. Workflow instances and schedules live here.
- **RabbitMQ** owns event routing. Workflow lifecycle events go here.
- **Redis** owns pub/sub for live status streaming to the UI.

### 4.2 Communication Contracts
| From | To | Mechanism | Contract |
|------|----|-----------|----------|
| Workflow Engine | LangGraph | HTTP (sync) | POST /threads/{id}/runs with `{"input": {"prompt": str}}`, returns `{"status":..., "output":...}` |
| Workflow Engine | Postgres | SQL (sync) | `workflow_instances`, `step_results`, `schedules` tables |
| Workflow Engine | RabbitMQ | AMQP (async) | `workflow.mode` exchange, topic queues |
| Control Center UI | Workflow Engine | HTTP REST | JSON API |
| Control Center UI | Redis | Pub/Sub | SSE/WebSocket channel |

### 4.3 State Ownership
- **Workflow Engine** is the sole writer of `workflow_instances` and `schedules` tables.
- **LangGraph** owns its own thread/run state in Postgres (it has its own schema).
- **RabbitMQ** is ephemeral — consumers must be idempotent.
- **Redis** is transient pub/sub for live UI updates only.

### 4.4 Swappability Strategy
To swap one component for another:
1. **Swap runtime (LangGraph → Aider/OpenCode/Custom):** Change `runtime_client.py` only. The function signature `run(prompt, execution_id)` stays the same.
2. **Swap event store (RabbitMQ → Kafka/Redis Streams):** Change `bus.py` only. The `EventBus` class interface stays the same.
3. **Swap state store (Postgres → Redis/SQLite):** Change `db.py` only. The state CRUD functions stay the same.
4. **Swap API framework (FastAPI → Flask/Quart):** Change `api.py` only. The HTTP contract stays the same.

---

## 5. Implementation Task List (Revised for Microservice Boundaries)

### 5.1 Event Taxonomy
- **Create:** `docs/architecture/event-bus-events.md` — workflow-mode event schemas, routing, exchanges/topics, idempotency rules.

### 5.2 Enable RabbitMQ
- **Update:** `docker-compose.yml` — remove `profiles: ["disabled"]` from `rabbitmq`.
- **Update:** `.env.template` — add `RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/`.

### 5.3 Library Code (in `agentic/src/workflow-runner/`)
- **Update:** `models.py` — extend `WorkflowState.status` regex to include `stopped`, `scheduled`.
- **Update:** `state.py` — replace file-only persistence with a clean interface (`create_workflow_state`, `load_workflow_state`, `advance_step`, etc.) that delegates to the active adapter.
- **Update:** `handlers/skill_handler.py` — import `runtime_client` lazily; if unavailable, return composed prompt as fallback (backward-compatible).

### 5.4 Service Adapters
- **Create:** `agentic/src/workflow-runner/runtime_client.py` — LangGraph HTTP binding. Methods: `start`, `run`, `send`, `add`, `drop`, `stop`, `exit`, `get_status`.
- **Create:** `agentic/src/workflow-runner/db.py` — Postgres persistence with file fallback. Schema: `workflow_instances`, `step_results`, `schedules`, `workflow_events`.
- **Create:** `agentic/src/workflow-runner/bus.py` — RabbitMQ topology + producer/consumer. Separate declare topology from consume.
- **Create:** `agentic/src/workflow-runner/scheduler.py` — APScheduler with SQLAlchemy job store. Fire `WorkflowRequested` events on schedule.

### 5.5 Service API Layer
- **Create:** `agentic/src/workflow-runner/api.py` — FastAPI app with endpoints:
  - `GET /health`
  - `GET /workflows` (list definitions)
  - `POST /workflows/{name}/run`
  - `GET /workflows/{id}/status`
  - `POST /workflows/{id}/pause`
  - `POST /workflows/{id}/resume`
  - `POST /workflows/{id}/stop`
  - `POST /schedules`
  - `DELETE /schedules/{id}`
  - `GET /schedules`

### 5.6 Container Definition
- **Create:** `agentic/src/workflow-runner/Dockerfile` — lean Python service image. Installs only `fastapi`, `uvicorn`, `psycopg2-binary`, `pika`, `apscheduler`, `sqlalchemy`. Does NOT include LangGraph.
- **Update:** `docker-compose.yml` — add `workflow-engine` service with `build: agentic/src/workflow-runner`, `depends_on: [postgres, rabbitmq, langgraph, redis-agents]`.
- **Update:** `ai-assistant-infra/configs/nginx/nginx.conf` — add location for Control Center UI and proxy for Workflow Engine (if needed externally).

### 5.7 Database Migration
- **Create:** `ai-assistant-infra/migrations/003_workflow_engine.sql` — create `workflow_instances`, `step_results`, `schedules`, `workflow_events` tables in the `aiassistant` database.

### 5.8 Documentation Updates
- **Update:** `docs/architecture/Phase-1-ABBs.md` — clarify that "agentic bus" means “workflow-mode events on separate routing from agentic-mode events.”
- **Update:** `docs/architecture/Phase-1-SBBs.md` — document Workflow Engine as a standalone service with HTTP + RabbitMQ interfaces.
- **Update:** `docs/architecture/Phase-1-BACKLOG.md` — mark Workflow Engine items to `SD`/`C`; note other Phase 1 SBBs stay `AD`.
- **Update:** `docs/SYSTEM_CONTEXT.md` — add workflow-mode event ownership.
- **Update:** `agentic/docs/context/ea/ROADMAP.md` — reference the event taxonomy.

### 5.9 Pattern Catalogue (Phase 1 Stub)
- **Create:** `agentic/__patterns/README.md` + `agentic/__patterns/pattern.schema.yaml`.
- **Create:** `agentic/docs/workflows/maintain-pattern.yaml` — workflow for pattern upkeep.

---

## 6. Critical Interfaces (Source of Truth for Implementation)

### 6.1 Runtime Interface Contract
```python
class RuntimeClient:
    def start(self) -> str: ...                          # create thread, return id
    def run(self, prompt: str, execution_id: str = None) -> dict: ...  # execute, return result
    def send(self, message: str, execution_id: str) -> dict: ...
    def add(self, execution_id: str, files: list) -> dict: ...
    def drop(self, execution_id: str, files: list) -> dict: ...
    def stop(self, execution_id: str, run_id: str) -> dict: ...
    def exit(self, execution_id: str) -> dict: ...
    def get_status(self, execution_id: str) -> dict: ...
```

### 6.2 Persistence Adapter Interface
```python
def create_workflow_state(name, path, steps, ctx) -> WorkflowState
def load_workflow_state(workflow_id, workflow_path) -> WorkflowState | None
def advance_step(state, result) -> WorkflowState
def fail_workflow(state, error) -> WorkflowState
def pause_workflow(state) -> WorkflowState
def resume_workflow(state) -> WorkflowState
def stop_workflow(state) -> WorkflowState
def list_workflow_states(path) -> list[dict]
```

### 6.3 Event Bus Interface
```python
class EventBus:
    def declare_topology(self) -> None
    def publish(self, routing_key, event_type, workflow_id, payload) -> None
    def consume(self, queue, callback, prefetch=1) -> None
    def start_consumers(self, requested_cb, control_cb) -> None
    def shutdown(self) -> None
```

---

## 7. Validation Plan

1. `docker compose up postgres rabbitmq langgraph workflow-engine` — all services start independently.
2. `POST /workflows/{requirements.analysis.define-requirements}/run` — Workflow Engine loads YAML, executes skill steps via HTTP to LangGraph, publishes `StepStarted`/`StepCompleted`/`WorkflowCompleted` to RabbitMQ, persists state in Postgres.
3. Scheduler: create cron schedule, wait for fire, confirm `WorkflowRequested` event is published and workflow runs.
4. Control: `POST /workflows/{id}/pause` then `POST /workflows/{id}/resume` — state transitions work; events published.
5. Idempotency: republish same `WorkflowRequested` twice — second is deduplicated by database or bus consumer logic.
6. Swap test: temporarily point `runtime_client.py` to a mock server — Workflow Engine still functions.

---

## 8. Explicitly Out of Scope

- LangGraph container modifications (it is a black-box runtime service)
- Control Center SPA implementation (React/Vue stub is Phase 1 only)
- Work Session, Task Tracking, Lead Enrichment services (backlog, status `AD`)
- Workflow-level authn/z (deferred; API key stub acceptable)
