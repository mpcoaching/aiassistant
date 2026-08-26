# Increment 21S — Paperclip / Enterprise-Plane Integration Assessment

**Date:** 2026-08-25  
**Author:** Kilo  
**Status:** Complete (integration deferred; Organisation usability improved)

## Objective

Connect the system to Paperclip if the existing architecture allows it, while preserving the Organisation boundary. If Paperclip is not yet available, identify what is missing and implement only the adapter/interface work necessary to make the next integration step straightforward.

## Key Finding: Paperclip Is Not Available

After exhaustive search of the repository, installed packages, running containers, and environment configuration:

- **Paperclip is not installed** as a Python package.
- **No Paperclip code exists** anywhere in the repository.
- **No Paperclip containers or services are running.**
- **Architecture Assessment (2026-08-21) explicitly rejected Paperclip** as an architectural component for the current implementation.
- **ADR-023** defers the Paperclip adapter to a future increment but has not been implemented.

### What the architecture says about Paperclip

| ADR | Status | Meaning |
|-----|--------|---------|
| ADR-023 | Accepted (deferred) | Paperclip will implement `OrganisationControlPlane` in a future increment |
| ADR-005 | Rejected | Paperclip is not adopted as a runtime substrate |
| Architecture Assessment | Rejected | Paperclip maps to `PathwayRuntime` adapter, not the Organisation |

**Conclusion:** Paperclip cannot be connected today because it is not present. Faking it would violate the architectural boundary and provide no real integration value.

## What Was Implemented Instead

Since Paperclip is unavailable, this increment improves the **existing Organisation** (`InMemoryOrganisationControlPlane`) to make it usable for team experimentation, and prepares the interface so that a future Paperclip adapter can be added without changing the Assistant.

### 1. `list_work()` added to `OrganisationControlPlane`

**File:** `packages/organisation/src/organisation_control_plane.py`

Added `list_work()` to the abstract interface and implemented it in `InMemoryOrganisationControlPlane`. This is the minimal interface work needed for:
- The API to enumerate all work
- Workers to discover their assigned work
- A future Paperclip adapter to expose Paperclip tasks

### 2. Worker becomes Organisation-aware

**File:** `packages/organisation/src/worker.py`

The worker now has a `pickup(org_plane)` method that queries the Organisation for work assigned to its agent ID (`worker-agent`). This means:

- The worker receives work **from the Organisation**, not from direct API invocation
- The worker is now an **Organisation citizen** rather than a utility function
- The API triggers the worker, but the worker decides what work to execute

### 3. New API endpoints

**File:** `packages/workflow_runner/api.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/roles` | GET | List all roles in the Organisation (team members) |
| `/worker/run` | POST | Trigger the worker to pick up and execute its assigned work |

### 4. Improved work visibility

**File:** `packages/workflow_runner/api.py`

- `GET /work` now uses `org_plane.list_work()` instead of accessing internal `_work` dict
- `_WorkResponse` surfaces `outcome` and `output_path`
- `GET /roles` exposes role names, statuses, and authority IDs

## Answers to the Architectural Questions

### Is Paperclip now connected?

**No.** Paperclip is not installed, not running, and not coded. The architecture explicitly deferred Paperclip integration (ADR-023) and later rejected it for the current substrate (Architecture Assessment 2026-08-21).

### What does the Assistant actually delegate to?

The Assistant delegates to **`WorkManagementPort`**. It knows nothing about the Organisation implementation. The `WorkManagementAdapter` translates `WorkCreateRequest` into `OrganisationControlPlane` operations.

### Where does the work live?

Work lives in the **`OrganisationControlPlane`** abstraction. Currently this is `InMemoryOrganisationControlPlane`, which stores work in a Python dict. A future Paperclip adapter would replace this implementation without changing the Assistant.

### How is work assigned?

Work is assigned through **`OrganisationControlPlane.assign_work(work, assignee)`**. The assignee can be a `Role`, `Person`, or `Agent`. The assignment sets `assignee_role_id`, `assignee_person_id`, or `assignee_agent_id` on the `Work` model and creates an `Assignment` record.

### How does a worker/agent receive it?

The worker uses **`Worker.pickup(org_plane)`** to query the Organisation for work assigned to its agent ID (`worker-agent`). The API endpoint `POST /worker/run` triggers this pickup. The worker:
1. Queries `org_plane.list_work()`
2. Filters for work where `assignee_agent_id == "worker-agent"` and status is `PENDING` or `ASSIGNED`
3. Executes the work
4. Updates the Organisation with the result

### How does the result get back?

The worker stores the result in **`work.outcome`** (a `dict[str, Any]`) and updates `work.status` via the Organisation. The API can retrieve this via `GET /work` or `GET /work/{work_id}`.

### What remains in-memory?

- **Enterprise plane state:** `InMemoryOrganisationControlPlane` stores roles, work, assignments, and delegations in Python dicts. Data is lost on process exit.
- **Worker output:** Artifacts are written to a local filesystem directory (`worker_outputs/`).
- **No event bus:** Work state changes are not published as events.
- **No persistence:** There is no database backing the Organisation.

### What remains simulated?

- **Worker execution:** The worker produces a markdown summary document. It does not execute real capabilities, run LLMs, or invoke tools.
- **No Paperclip:** There is no Paperclip integration. The architecture boundary is prepared but not connected.
- **No autonomous scheduling:** The worker only runs when manually triggered via the API.

### What is the smallest next step needed to start building the actual team?

**Make the worker execute a real capability through `CapabilityExecutionPort`.**

Currently the worker writes a markdown file. The next step is to:

1. Detect when a work item references a registered capability
2. Execute that capability via the existing `CapabilityExecutionPort`
3. Store the capability result in `work.outcome`

This would prove the full path: delegated work → capability lookup → execution → result storage. It keeps the worker simple (no planner, no multi-agent loop) and reuses existing contracts.

After that, the natural next steps are:

1. **Persist Organisation state** (replace in-memory with a database-backed implementation)
2. **Add event emission** on work lifecycle transitions
3. **Introduce a Paperclip-backed `OrganisationControlPlane` adapter** when Paperclip becomes available

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Existing 21R behaviour remains intact | Verified — all 21R tests pass |
| 2 | `AssistantChatService` still only knows about `WorkManagementPort` | Verified — no Paperclip or org-plane imports in `chat.py` |
| 3 | Paperclip accessed only behind Organisation boundary | Verified — Paperclip is not present; boundary is preserved |
| 4 | Real path for creating and inspecting work | Verified — `POST /assistant/chat` delegates; `GET /work` inspects |
| 5 | Assignment represented by Organisation | Verified — `assign_work()` in `OrganisationControlPlane` |
| 6 | Worker does not become a second orchestration system | Verified — worker queries Organisation, executes one task |
| 7 | Existing tests continue to pass | Verified — 206 passed in workflow_runner, 115 in organisation+ai |
| 8 | Focused integration tests for Organisation integration | Added — 6 new tests in `test_capability_execute.py` |
| 9 | Manual test demonstrating interaction | Documented below |
| 10 | Clear documentation of real vs simulated | This report |

## Manual Test

### Prerequisites

```bash
cd /home/martinp/Documents/projects/aiassistant/packages/workflow_runner
pip install fastapi uvicorn pydantic pyyaml  # if not already installed
```

### Start the API

```bash
uvicorn api:app --reload --port 8000
```

### Test the team interaction

```bash
# 1. Send a request with no matching capability (delegates to Organisation)
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Research X and produce a report", "session_id": "ses-team-1"}'

# Expected: status="delegated", message mentions work ID

# 2. List all roles (team members)
curl http://localhost:8000/roles

# Expected: JSON array with registered roles (may be empty initially)

# 3. List all work in the Organisation
curl http://localhost:8000/work

# Expected: JSON array with the delegated work item

# 4. Inspect specific work
curl http://localhost:8000/work/{work_id}

# Expected: Work details including assignee, status, outcome

# 5. Run the worker (picks up assigned work)
curl -X POST http://localhost:8000/worker/run

# Expected: {"work_id": "...", "status": "completed", "outcome": {...}}

# 6. Verify work is completed with result
curl http://localhost:8000/work/{work_id}

# Expected: status="completed", outcome populated with summary and output_path

# 7. List work again to see the completed item
curl http://localhost:8000/work

# Expected: Work item with status="completed" and outcome details
```

## Test Results

```
packages/organisation/tests/                      47 passed
packages/ai/tests/                                68 passed
packages/workflow_runner/tests/                  206 passed
-------------------------------------------------
Total                                            321 passed
```

### New tests added

| Test | Purpose |
|------|---------|
| `test_list_work_returns_empty_when_no_work` | API uses `list_work()` |
| `test_list_roles_returns_empty_when_no_roles` | Role listing works |
| `test_list_roles_returns_registered_roles` | Role listing returns data |
| `test_worker_pickup_returns_assigned_work` | Worker finds work assigned to its agent ID |
| `test_worker_pickup_returns_none_when_no_assigned_work` | Worker handles empty queue |
| `test_worker_run_endpoint_processes_assigned_work` | API triggers worker pickup |
| `test_worker_run_returns_404_when_no_work` | API handles empty worker queue |

## Files Changed

| File | Change |
|------|--------|
| `packages/organisation/src/organisation_control_plane.py` | Added `list_work()` to abstract interface and implementation |
| `packages/organisation/src/worker.py` | Added `pickup()` method; worker is now Organisation-aware |
| `packages/workflow_runner/api.py` | Added `/roles`, `/worker/run` endpoints; updated `/work` to use `list_work()`; added `_RoleResponse` model |
| `packages/workflow_runner/tests/test_capability_execute.py` | Added 6 new tests for roles, worker pickup, and worker run endpoint |

## What the Assistant Actually Delegates To

```
AssistantChatService
    ↓ (WorkManagementPort)
WorkManagementAdapter
    ↓ (OrganisationControlPlane)
InMemoryOrganisationControlPlane  (current)
    OR
PaperclipOrganisationControlPlane (future, not yet implemented)
```

The Assistant never knows which implementation is active. It delegates to `WorkManagementPort.create_work()`, and the adapter translates that to the Organisation.

## What Would Need to Change to Connect Paperclip

1. **Implement `PaperclipOrganisationControlPlane(OrganisationControlPlane)`** — map Paperclip Teams→Roles, Tasks→Work, Task assignments→Assignment records.
2. **Wire the adapter in composition** — replace `InMemoryOrganisationControlPlane` with the Paperclip adapter in `create_application()`.
3. **No changes to `AssistantChatService` or `WorkManagementPort`** — the boundary is already preserved.
4. **Potentially enrich `Work.outcome`** — Paperclip may need structured fields (logs, traces, token usage). This would be a schema evolution, not a breaking change.

These changes can be made **entirely within the Organisation package** without touching the AI or workflow-runner packages.
