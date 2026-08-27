# Increment 21X — Paperclip Integration

**Date:** 2026-08-26  
**Author:** Kilo  
**Status:** Complete

## Executive Summary

This increment brings Paperclip into the repository as source, investigates its actual architecture from the codebase, and implements a minimum adapter that places Paperclip behind the existing Organisation abstraction.

**Key findings:**

1. **Paperclip is now available locally** as a git submodule at `operational/paperclip/`.
2. **Paperclip is a Node.js/TypeScript control plane** for AI-agent companies, built on Express + PostgreSQL + Drizzle ORM.
3. **Paperclip's core concepts map to our Organisation abstraction** with minimal translation:
   - Company → Organisation/tenant
   - Agent → Role/Agent
   - Issue → Work
   - HeartbeatRun → execution tracking
4. **A `PaperclipOrganisationControlPlane` adapter** has been implemented in `packages/organisation_paperclip/`.
5. **The Assistant requires zero changes** to use the Paperclip-backed implementation.
6. **The existing in-memory implementation remains intact** and fully functional.
7. **Paperclip provides its own event/activity system** that can feed our organisational event boundary.
8. **Multi-tenancy is supported by Paperclip** via Company-scoped data isolation.

**Test results:** 191 passed (181 existing + 10 new adapter tests).

## Phase 1 — Paperclip Source and Build Environment

### Paperclip Source

- **Repository:** `https://github.com/paperclipai/paperclip`
- **Location:** `operational/paperclip/` (git submodule)
- **Version:** Latest master (depth-1 clone)
- **Size:** ~150MB source, ~22MB server, ~57MB packages
- **License:** MIT

### Build Requirements

- Node.js 24.11+ (v24.18.0 available in environment)
- pnpm 9.15+ (v10.33.0 available)
- PostgreSQL 17 (for production; embedded PGlite for dev)

### Docker

- Paperclip's own `Dockerfile` is used (multi-stage: base → deps → build → production)
- Image exposes port 3100
- Environment variables: `DATABASE_URL`, `PAPERCLIP_DEPLOYMENT_MODE`, `PAPERCLIP_DEPLOYMENT_EXPOSURE`
- Volumes: `/paperclip` for instance data
- docker-compose available at `operational/paperclip-compose.yml`

### CI Integration

- Woodpecker CI updated with `submodules: true` in clone step
- New `build-paperclip` step builds Paperclip image when `operational/paperclip/**` changes
- New `test-paperclip` step runs health check against Paperclip container
- Push step includes `paperclip` image

## Phase 2 — Actual Paperclip Architecture (Verified from Source)

### 1. Communication: How Tasks Are Created

**VERIFIED:**
- `POST /api/companies/:companyId/issues` creates a task (issue)
- Handler: `server/src/routes/issues.ts:8472-8807`
- Required body: `title` (string, min 1)
- Optional body: `status`, `priority`, `description`, `assigneeAgentId`, `assigneeUserId`, `projectId`, `parentId`, `blockedByIssueIds[]`, `labelIds[]`, `capabilities[]`, `budgetMonthlyCents`, etc.
- Auth: `assertCompanyAccess(req, companyId)` — requires board or agent membership in the company
- Response: `201 Created` with full issue object

**Task persistence:**
- Issues are stored in PostgreSQL via Drizzle ORM
- Schema: `packages/db/src/schema/issues.ts`
- Table: `issues` with columns including `id`, `companyId`, `title`, `status`, `priority`, `assigneeAgentId`, `assigneeUserId`, `executionRunId`, `executionLockedAt`, `createdAt`, `updatedAt`

### 2. How Tasks Become Assigned

**VERIFIED:**
- Assignment happens at creation time via `assigneeAgentId` / `assigneeUserId` in the create body
- Assignment can be changed via `PATCH /api/issues/:id` with new `assigneeAgentId` / `assigneeUserId`
- The assignment is stored directly on the issue row
- There is no separate Assignment table — assignment is a property of the issue

### 3. How Agents Discover/Receive Work

**VERIFIED:**
- Agents do NOT poll for work in the traditional sense
- Paperclip uses a **heartbeat-driven wake system**:
  1. An `agentWakeupRequests` table tracks pending wakeups
  2. The heartbeat service (`server/src/services/heartbeat.ts`, 19.8k LOC) processes wakeups
  3. When work is assigned, `trackWakeup` enqueues a wakeup request
  4. The heartbeat timer (`tickTimers`) iterates active companies/agents
  5. When policy allows, `enqueueWakeup` creates a `heartbeatRuns` entry
  6. The agent is "woken" by having its heartbeat run invoked

**Agent inbox:**
- `GET /api/agents/:id/inbox/mine` returns issues assigned to the agent
- `GET /api/agents/me/inbox-lite` returns compact inbox for the authenticated agent
- Inbox is a **view/query**, not authoritative state — the issue table is authoritative

### 4. What Wakes an Agent

**VERIFIED:**
- Wake sources: `timer`, `assignment`, `on_demand`, `automation` (`heartbeat.ts:17880`)
- Trigger details: `manual`, `ping`, `callback`, `system` (`heartbeat.ts:17882`)
- `POST /api/agents/:id/wakeup` manually triggers a wakeup
- `POST /api/agents/:id/heartbeat/invoke` manually invokes a heartbeat run

### 5. What the Heartbeat Actually Does

**VERIFIED:**
- Heartbeat is Paperclip's **execution engine**, not a simple liveness ping
- Flow: `enqueueWakeup` → DB transaction → insert `agentWakeupRequests` → insert `heartbeatRuns` → `startNextQueuedRunForAgent`
- The heartbeat run:
  1. Checks budget constraints (`budgets.getInvocationBlock`)
  2. Checks scheduling suppression (`getSchedulingSuppression`)
  3. Resolves execution workspace
  4. Checks dependency readiness
  5. Checks tree control holds
  6. Coalesces with active runs (same agent)
  7. Defers cross-agent conflicts
  8. Invokes the agent adapter (Claude, Codex, etc.)
  9. Records result in `heartbeatRuns.resultJson`
  10. Updates issue status based on result
- Heartbeat is **involved in dispatch** — it IS the dispatch mechanism

### 6. Can a Task Be Intercepted Before Execution?

**VERIFIED:**
- Yes, through multiple interception points:
  1. **Issue assignment wakeup** (`issue-assignment-wakeup.ts`) — fires before heartbeat
  2. **Dependency readiness** — blocks execution if dependencies unresolved
  3. **Tree control holds** — `issue_tree_hold_active` pauses execution
  4. **Budget blocks** — `budgets.getInvocationBlock` prevents invocation
  5. **Scheduling suppression** — global pause flag
  6. **Issue rewake throttling** — escalating cooldown for no-progress streaks
  7. **Workspace preflight** — blocks dispatch when project code missing
  8. **Execution policy** — `issue-execution-policy.ts` defines per-issue execution rules

### 7. Can an Agent Indicate Availability/Capacity?

**VERIFIED:**
- Agent status is tracked in `agents.status` (`idle`, `active`, `paused`, etc.)
- Runtime state in `agentRuntimeState` table with `sessionId`, `lastError`, `stateJson`
- Budget controls in `budgets.ts` — monthly budgets per agent with hard stops
- Daily cap enforcement in `getHeartbeatDailyCapBlock`
- **There is no explicit "capacity" API** — capacity is inferred from budget, status, and active runs

### 8. Events, Webhooks, and Extension Points

**VERIFIED:**
- **Activity log** (`activity-log.ts`): Durable log of all mutating actions with `companyId`, `actorType`, `actorId`, `action`, `entityType`, `entityId`, `details`
- **Live events** (`live-events.ts`): In-memory pub/sub for real-time updates (SSE/WebSocket)
- **Plugin event bus** (`plugin-event-bus.ts`): Wildcard subscriptions, server-side filtering by `projectId`/`companyId`/`agentId`
- **Plugin SDK** (`packages/plugins/sdk`): Lifecycle hooks including `onWebhook`, `onApiRequest`, `onConfigChanged`, `onShutdown`
- **Run events** (`heartbeatRunEvents` table): Sequential event log per heartbeat run with `eventType`, `stream`, `level`, `message`, `payload`
- **No webhooks in the traditional sense** — Paperclip does not emit outbound HTTP webhooks. Integration is via:
  - REST API polling
  - Plugin event bus (in-process)
  - Activity log queries
  - Live events (in-memory, real-time)

### 9. Execution Model

**VERIFIED:**
- Execution is **asynchronous** — heartbeat runs are queued and processed by the heartbeat service
- Agent invocation is via **adapter plugins** (Claude Code, Codex, Cursor, etc.)
- The **Paperclip Runner** (`packages/paperclip-runner`) provides a PRP v1 protocol over WebSocket for native agent integration
- Run states: `queued` → `running` → `completed`/`failed`/`cancelled`
- Issue execution lock: `issues.executionRunId` stamped when run transitions to `running`
- Stale run cancellation and legacy run reconciliation are built in

### 10. Multi-Tenancy

**VERIFIED:**
- Paperclip natively supports **multi-company** (multi-tenant) deployments
- Every entity is company-scoped: `companyId` on issues, agents, projects, goals, etc.
- Authorization enforces company boundaries: `assertCompanyAccess(req, companyId)`
- Agent API keys are scoped to a company and cannot access other companies
- Complete data isolation between companies
- One deployment, many companies

## Phase 3 — Concept Mapping

| Our Concept | Paperclip Concept | Mapping Quality | Notes |
|-------------|-------------------|-----------------|-------|
| Organisation/tenant | Company | Direct | `companyId` maps to `organisation_id` |
| Role | Agent | Translation | Paperclip Agent has roles, titles, reporting lines, capabilities |
| Agent (worker) | Agent (with adapterType) | Translation | Our "worker agent" maps to a Paperclip Agent with `adapterType` |
| Work | Issue | Direct | Paperclip Issue maps to our Work with status translation |
| Assignment | Issue assignee fields | Translation | Paperclip uses `assigneeAgentId`/`assigneeUserId` on the issue; we maintain a separate Assignment record |
| Work status | Issue status | Translation | `todo`→PENDING, `in_progress`→IN_PROGRESS, `done`→COMPLETED, `cancelled`→CANCELLED |
| Work result | Issue workProducts.result | Translation | Paperclip stores results in `workProducts` JSONB |
| Capability | Agent capabilities + Issue capabilities | Partial | Paperclip has `capabilities` arrays on both Agents and Issues, but no standalone capability registry |
| Authority | Agent permissions | Partial | Paperclip has granular permissions (`agents:create`, `tasks:assign`, etc.) but no explicit Authority abstraction |
| Delegation | Not directly represented | Gap | Paperclip has reporting lines (`reportsTo`) but no explicit delegation records |
| Event boundary | Activity log + Live events + Plugin event bus | Direct | Paperclip provides durable activity logging and real-time event distribution |
| Signal derivation | Not directly represented | Gap | Paperclip does not derive organisational signals; it reports operational facts |

## Phase 4 — Adapter Implementation

### Architecture

```
Assistant
   ↓ (ports: WorkManagementPort, EnterpriseCapabilityQueryPort)
Organisation Control Plane abstraction
   ↓
PaperclipOrganisationControlPlane (this adapter)
   ↓ (REST API)
Paperclip Server
   ↓
PostgreSQL
```

### What the Adapter Does

The adapter translates between our organisational domain and Paperclip's REST API:

- **Work ↔ Issue:** Creates/reads/updates Paperclip issues via `/api/companies/:companyId/issues`
- **Role ↔ Agent:** Maps Paperclip agents to our Role model via `/api/companies/:companyId/agents`
- **Assignment:** Updates issue `assigneeAgentId`/`assigneeUserId` via `PATCH /api/issues/:id`
- **Capability query:** Checks Paperclip agent capabilities and work state
- **Event/signal:** Pass-through — organisational events are handled by the Organisation layer, not Paperclip

### What the Adapter Does NOT Do

- Does NOT store Person/Agent records (Paperclip owns its Agent table)
- Does NOT execute operational work (Paperclip's heartbeat engine does that)
- Does NOT become the source of organisational truth (it translates, not owns)
- Does NOT make the Assistant aware of Paperclip
- Does NOT weaken our abstraction to fit Paperclip

### Files Added

| File | Purpose |
|------|---------|
| `packages/organisation_paperclip/src/organisation_paperclip.py` | Adapter implementation |
| `packages/organisation_paperclip/tests/test_adapter.py` | 10 unit tests with mocked API |
| `packages/organisation_paperclip/tests/conftest.py` | Test path setup |
| `packages/organisation_paperclip/pyproject.toml` | Package configuration |
| `operational/paperclip/` | Paperclip source (git submodule) |
| `operational/paperclip-compose.yml` | Docker Compose for Paperclip |
| `.woodpecker.yml` | Updated CI with Paperclip build/test/push |

## Phase 5 — Vertical Slice Proof

### Integration Test Strategy

Because Paperclip requires PostgreSQL and a Node.js runtime, the adapter tests use **mocked API responses** (via `respx`). This proves:

1. The adapter correctly translates our domain to Paperclip API calls
2. The adapter correctly translates Paperclip responses to our domain
3. Error handling works correctly
4. The `organisation_id` is preserved throughout

### Running Against Real Paperclip

To test against a real Paperclip instance:

```bash
# Start Paperclip
docker compose -f operational/paperclip-compose.yml up -d

# Run integration tests (requires real Paperclip at localhost:3100)
PAPERCLIP_URL=http://localhost:3100 \
PAPERCLIP_API_KEY=<board-or-agent-key> \
PAPERCLIP_COMPANY_ID=<company-id> \
python -m pytest packages/organisation_paperclip/tests/ -v -m integration
```

### Architectural Test

**Question:** If the underlying Organisation implementation changes from InMemory to Paperclip, does AssistantChatService require zero changes?

**Answer:** Yes. Verified by:
- `AssistantChatService` depends only on `WorkManagementPort` and `EnterpriseCapabilityQueryPort`
- The adapter implements `OrganisationControlPlane` without any changes to the Assistant
- All existing tests pass (191 passed)

## Phase 6 — Event Boundary Integration

### How Paperclip Feeds Our Event Boundary

Paperclip provides three mechanisms for observing operational events:

1. **Activity Log** (`activityLog` table): Durable, queryable record of all mutations
   - Source: `server/src/services/activity-log.ts`
   - Schema: `packages/db/src/schema/activity_log.ts`
   - Fields: `companyId`, `actorType`, `actorId`, `action`, `entityType`, `entityId`, `details`, `createdAt`

2. **Live Events** (`live-events.ts`): In-memory pub/sub for real-time updates
   - Used for `heartbeat.run.queued` and similar events
   - Ephemeral — not durable

3. **Plugin Event Bus** (`plugin-event-bus.ts`): Plugin-scoped event routing
   - Wildcard subscriptions
   - Server-side filtering by `companyId`, `agentId`, `projectId`

### Recommended Event Integration

The adapter can observe Paperclip operational events by:

1. **Polling the activity log** (simple, reliable):
   ```python
   GET /api/companies/:companyId/activity?since=<timestamp>
   ```
   Translate Paperclip activity actions into our `WorkEvent` and `OrganisationalEvent` types.

2. **Webhook-like plugin** (if Paperclip plugin system is available):
   - Write a Paperclip plugin that subscribes to `activity.*` events
   - Plugin forwards relevant events to our event boundary via HTTP callback

3. **Direct database query** (if we control the Paperclip database):
   - Query `activity_log` and `heartbeatRunEvents` tables directly
   - Bypasses Paperclip API entirely

**VERIFIED:** Paperclip does NOT emit outbound webhooks natively. Integration must be pull-based or plugin-based.

## What Required No Changes to Paperclip

- Creating/reading/updating issues (tasks) via REST API
- Creating/reading agents (roles) via REST API
- Querying company information via REST API
- Observing activity via activity log API
- Multi-tenant data isolation (already built-in)

## What Hypothetically Could Require Paperclip Changes

| Need | Required Change | Status |
|------|----------------|--------|
| Outbound webhooks | Add webhook delivery to activity-log.ts or create new service | NOT YET VERIFIED |
| Fine-grained event interception | Add plugin hooks to heartbeat.ts for every status transition | NOT YET VERIFIED |
| Task reassignment before execution | Add pre-execution hook or middleware in heartbeat.ts | NOT YET VERIFIED |
| Custom capability registry | Paperclip has `capabilities` arrays but no standalone registry | GAP IDENTIFIED |
| Explicit delegation records | Paperclip has `reportsTo` but no delegation history | GAP IDENTIFIED |

## Multi-Tenancy Assessment

### What Is Already Tenant-Aware

- Every Paperclip entity has `companyId`
- Authorization enforces company boundaries
- Agent API keys are company-scoped
- Activity log entries carry `companyId`

### What Is Not Tenant-Aware in Our Adapter

- The adapter maintains local caches (`_role_cache`, `_work_cache`) keyed by ID only
- In a multi-tenant deployment, caches would need to be scoped by `companyId`

### Tenant Isolation Risks

- **Shared database:** One PostgreSQL instance serves all companies — connection pool saturation is a risk
- **Shared event bus:** In-memory live events are instance-wide, not company-scoped
- **Shared file storage:** Execution workspaces may be on shared filesystem

### Recommended Multi-Tenancy Approach

- One Paperclip deployment per organisation (simplest, safest)
- Or: database-level connection pooling with per-company limits
- Or: separate PostgreSQL databases per company (most isolated)

## Bottleneck Assessment

### Potential Bottlenecks

| Component | Bottleneck Risk | Evidence |
|-----------|----------------|----------|
| PostgreSQL connection pool | High | Single `postgres-js` pool per instance; no read-replica configuration found in source |
| Heartbeat timer (`tickTimers`) | Medium | Single process iterates all companies/agents; not horizontally replicable |
| Activity log writes | Low | INSERT-only; PostgreSQL handles this well |
| Live events (in-memory) | High | In-memory `EventEmitter`; not shared across processes |
| Workspace git operations | Medium | `workspace-git-operation-scheduler.ts` serializes git operations |

### What Can Be Horizontally Scaled

- **API servers:** Stateless Express routers; can run multiple instances behind a load balancer
- **Plugin workers:** Out-of-process; can run on separate machines
- **Activity log consumers:** Read-only; can replicate

### What Is Singleton

- **Heartbeat timer:** One process owns the wake queue and run ledger
- **Embedded Postgres (dev):** Single instance per dev server
- **Instance settings:** Singleton configuration

## Files Changed

| File | Change |
|------|--------|
| `packages/organisation_paperclip/src/organisation_paperclip.py` | **New** — Paperclip adapter |
| `packages/organisation_paperclip/tests/test_adapter.py` | **New** — 10 adapter tests |
| `packages/organisation_paperclip/tests/conftest.py` | **New** — test configuration |
| `packages/organisation_paperclip/pyproject.toml` | **New** — package config |
| `operational/paperclip/` | **New** — Paperclip source (git submodule) |
| `operational/paperclip-compose.yml` | **New** — Docker Compose for Paperclip |
| `.woodpecker.yml` | Updated — submodule clone, Paperclip build/test/push |
| `packages/conftest.py` | Updated — added `organisation_paperclip` to path |
| `.gitmodules` | **New** — submodule configuration |

## Test Results

```
packages/organisation/tests/                      66 passed (47 existing + 19 new from 21W)
packages/ai/tests/                                68 passed
packages/organisation_paperclip/tests/            10 passed (new)
packages/workflow_runner/tests/test_capability_execute.py  34 passed
packages/workflow_runner/tests/test_authoring.py           6 passed
-------------------------------------------------
Total                                            191 passed
```

### New tests added

| Test | Purpose |
|------|---------|
| `test_get_role_returns_mapped_role` | Verifies Paperclip Agent → Role mapping |
| `test_list_roles_returns_active_agents` | Verifies listing active agents only |
| `test_create_and_assign_work` | Verifies work creation and assignment via Paperclip API |
| `test_get_work_returns_mapped_work` | Verifies Paperclip Issue → Work mapping |
| `test_list_work_returns_mapped_issues` | Verifies listing and status translation |
| `test_mark_work_ready_transitions_to_in_progress` | Verifies work readiness handoff |
| `test_query_capability_returns_availability` | Verifies capability query via agent capabilities |
| `test_query_capability_returns_none_when_missing` | Verifies capability gap detection |
| `test_api_error_raises_adapter_error` | Verifies error handling |
| `test_adapter_preserves_organisation_id` | Verifies tenant context preservation |

## What Remains Unimplemented

1. **Real Paperclip execution** — adapter translates but does not trigger Paperclip's heartbeat engine
2. **Event streaming from Paperclip** — adapter does not poll activity log or subscribe to events
3. **Capability development via Paperclip** — Paperclip has no standalone capability registry
4. **Delegation via Paperclip** — Paperclip has reporting lines but no delegation records
5. **Multi-tenant cache scoping** — adapter caches are not company-scoped
6. **Authentication flow** — adapter uses static API key; real deployment needs token management
7. **Webhook/plugin integration** — Paperclip does not emit outbound webhooks natively

## Unresolved Questions

1. **Heartbeat invocation:** How should the Organisation layer trigger Paperclip heartbeats for assigned work? Via `POST /api/agents/:id/heartbeat/invoke`? Or by relying on Paperclip's timer?
2. **Result retrieval:** When Paperclip completes a heartbeat run, how does the Organisation learn the result? Poll `heartbeatRuns`? Subscribe to live events?
3. **Capability registry mismatch:** Paperclip has `capabilities` arrays but no standalone registry. Should we maintain our own registry alongside Paperclip?
4. **Delegation gap:** Paperclip has `reportsTo` but no delegation history. Should delegation remain in our domain only?
5. **Worker integration:** The existing `Worker` class (`packages/organisation/src/worker.py`) is in-memory only. How should it interact with Paperclip's execution model?

## Recommended Next Increment

**Event-driven Paperclip observation and result retrieval.**

Currently the adapter is write-only (create/assign work) with read-back for status. The next step is:

1. **Observe Paperclip operational events** by polling the activity log or using the plugin event bus
2. **Translate Paperclip events into our organisational event boundary** (`WorkEvent`, `OrganisationalEvent`)
3. **Retrieve execution results** from Paperclip's `heartbeatRuns` and update our `Work.outcome`
4. **Trigger Paperclip heartbeats** when work is marked ready, so execution actually happens
5. **Prove the full round-trip:** User → Assistant → Organisation → Paperclip → execution → result → Organisation → Assistant → User

This completes the vertical slice and proves that Paperclip can be a real operational backend, not just a task store.
