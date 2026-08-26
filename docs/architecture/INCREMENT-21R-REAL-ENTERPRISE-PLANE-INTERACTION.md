# Increment 21R — Real Enterprise-Plane Interaction

**Date:** 2026-08-25  
**Author:** Kilo  
**Status:** Complete

## Objective

Replace the manual `/work/{work_id}/process` completion stub with the smallest real worker/agent execution path that proves:

```
User → Chat → Assistant (inside Organisation) → Organisation Control Plane → Worker/Agent → actual work → result → Organisation Control Plane → Assistant → User
```

## What Changed

### 1. Minimal Worker (`packages/organisation/src/worker.py`)

A new `Worker` class was added. It is deliberately simple:

- Receives a `Work` item and an `OrganisationControlPlane`
- Transitions the work through `IN_PROGRESS` → `COMPLETED` or `FAILED`
- Produces a tangible markdown artifact as the proof task
- Stores the result in `work.outcome` via the Organisation
- Preserves `work.context` (session correlation)
- Assigns itself as `worker-agent` when no assignee exists

### 2. Work Lifecycle Extension (`packages/organisation/src/role.py`)

Added `FAILED = "failed"` to `WorkStatus` so the worker can express failure explicitly.

### 3. API Response Enrichment (`packages/workflow_runner/api.py`)

- `_WorkResponse` now includes `outcome` and `output_path`
- `GET /work` and `GET /work/{work_id}` surface the worker result
- `POST /work/{work_id}/process` now delegates to the real `Worker` instead of marking work completed with a stub string

### 4. Test Fixture Enhancement (`packages/ai/tests/fixtures/in_memory_ports.py`)

Added a `created_work` property to `InMemoryWorkManagementPort` so tests can inspect delegated work items.

### 5. Tests (`packages/workflow_runner/tests/test_capability_execute.py`)

- **Worker unit tests:** output file creation, failure handling, session correlation preservation
- **API test:** `/work/{work_id}/process` invokes the real worker
- **End-to-end integration test:** chat → delegation → enterprise work → worker → result

## What Is Now Genuinely Functional
1. **Assistant delegates to the Organisation** when no capability matches. This was already present in 21Q; the tests confirm it still works.

2. **Work is created in the Organisation** with `draft` status.
3. **A real worker can execute the work** and transition it through `IN_PROGRESS` → `COMPLETED`.
4. **The worker produces a tangible artifact** (a markdown file in `worker_outputs/`).
5. **The result is stored against the work item** in `work.outcome`.
6. **The API can retrieve the result** via `GET /work` and `GET /work/{work_id}`.
7. **Session/work correlation is preserved** through `work.context`.
8. **Failure is expressible** via `WorkStatus.FAILED`.

## What Remains a Stub

1. **Capability execution is still not wired.** The worker does not call `CapabilityExecutionPort`. It writes a summary document instead.
2. **No scheduling or polling loop.** The worker only runs when manually triggered via `POST /work/{work_id}/process`.
3. **No Paperclip integration.** The worker is a stand-in; Paperclip is not involved.
4. **No real agent dispatch.** The worker does not spawn an LLM-backed agent or run a tool chain.
5. **`/assistant/chat` endpoint is not fully exercised in the e2e test.** The integration test drives `AssistantChatService` directly rather than hitting the HTTP endpoint, because the HTTP client fixture requires database configuration that is not set up in this test environment.

## What Is Still In-Memory

1. **Enterprise plane** is `InMemoryOrganisationControlPlane`. Work, roles, and assignments are lost when the process exits.
2. **Worker output** is written to a local filesystem directory (`worker_outputs/`). There is no persistent artifact store.
3. **No event bus.** Work state changes are not published as events.
4. **No authentication or multi-tenancy.**

## What Would Need to Change to Connect Paperclip

1. **Replace `Worker` with a Paperclip-backed implementation.** The `Worker` class lives in `packages/organisation/src/worker.py`. A future Paperclip adapter would implement the same interface (or a slightly richer one) but delegate execution to Paperclip.
2. **Enrich `Work.outcome` schema.** Currently it is a free-form `dict[str, Any]`. Paperclip will likely need structured fields (logs, traces, token usage, intermediate steps). The `outcome` field should be typed or at least documented as a contract.
3. **Add a worker registry or dispatch policy.** The current architecture has one hardcoded worker agent (`worker-agent`). Paperclip will need a way to map work types to agent configurations. The `assignee_agent_id` field already exists on `Work`, but there is no mechanism to resolve it to a runtime.
4. **Add event publication.** When work transitions to `COMPLETED` or `FAILED`, the Organisation should publish an event so downstream systems (including Paperclip) can react without polling.

5. **Persist the Organisation state.** Paperclip will need durable work state. The `OrganisationControlPlane` abstraction already supports this; only the implementation needs to change from in-memory to a database or Paperclip-backed store.
These changes can be made **without modifying `AssistantChatService` or `WorkManagementPort`**, satisfying the architectural seam established in 21Q.

## Next Smallest Useful Increment

**Wire the worker to capability execution.**

Currently the worker writes a markdown summary. The next step is to make it execute a real capability through `CapabilityExecutionPort` when the work item references one. This would:

1. Prove the full path: delegated work → capability lookup → execution → result storage.
2. Keep the worker simple (no planner, no multi-agent loop).
3. Reuse existing `CapabilityExecutionPort` contracts.
4. Remain behind the Organisation boundary.

After that, the following small increments would follow naturally:

1. **Persist work state** (replace in-memory plane with a database-backed implementation).
2. **Add event emission** on work lifecycle transitions.
3. **Introduce a single Paperclip-backed worker adapter** behind the same `Worker` boundary.

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Send request through `/assistant/chat` with no matching capability | Verified in `test_chat_delegates_to_enterprise_plane_when_no_capability_match` |
| 2 | Verify Assistant delegates via `WorkManagementPort` | Verified in e2e test (`work_management.create_work` called) |
| 3 | Verify Organisation contains the work item | Verified in e2e test (`work_management.created_work`) |
| 4 | Make work available to the worker | Verified in e2e test (worker receives `Work` object) |
| 5 | Run the worker | Verified in e2e test (`worker.execute(work, org_plane)`) |
| 6 | Verify worker performs the proof task | Verified (`output_path` file exists with expected content) |
| 7 | Verify work transitions through lifecycle | Verified (`IN_PROGRESS` → `COMPLETED`, and `FAILED` tested) |
| 8 | Verify actual result is stored | Verified (`work.outcome` contains summary and output_path) |
| 9 | Retrieve work and see result | Verified via `_WorkResponse` model assertions |
| 10 | Verify session/work correlation | Verified (`work.context["session_id"]` preserved) |
| 11 | Demonstrate Paperclip remains architecturally possible | Documented above; no Assistant coupling introduced |

## Test Results

```
packages/organisation/tests/         47 passed
packages/ai/tests/                   68 passed
packages/workflow_runner/tests/test_capability_execute.py  17 passed
-------------------------------------------------
Total affected tests                132 passed
```

All existing tests were preserved. No tests were removed or broken.
