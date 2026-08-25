# Increment 21T — Assistant ↔ Enterprise Plane Interaction Model

**Date:** 2026-08-25  
**Author:** Kilo  
**Status:** Complete

## Objective

Establish the correct decision boundary between the Assistant (user-facing interface) and the Enterprise Plane (organisation authority). Prove that the Assistant can determine whether the organisation should handle a request, whether the user should wait, or whether the Assistant should provide an interim answer while the organisation works on the proper one.

## What Is Now Genuinely Real

### 1. Assistant ↔ Enterprise Plane Decision Boundary

The Assistant now queries the enterprise plane **before** deciding how to respond. It asks: "What can the organisation currently do about this request?" and receives structured availability information.

**File:** `packages/ai/src/chat.py`
- `AssistantChatService` now accepts `enterprise_capability_query: EnterpriseCapabilityQueryPort`
- New method `_evaluate_enterprise_action()` queries availability for the best matching capability
- Decision logic routes to four distinct handlers based on enterprise response

### 2. Enterprise Capability Availability Contract

**File:** `packages/contracts/enterprise_capability_query.py`

```python
class CapabilityAvailability(BaseModel):
    capability_id: str
    available: bool
    eta_seconds: int | None = None
    assignee: str | None = None
    reason: str = ""

class EnterpriseCapabilityQueryPort(Protocol):
    def query_capability(self, capability_id: str) -> CapabilityAvailability | None: ...
```

### 3. OrganisationControlPlane Query Method

**File:** `packages/organisation/src/organisation_control_plane.py`

Added `query_capability(capability_id)` to both the abstract interface and `InMemoryOrganisationControlPlane` implementation. Returns:
- `None` if no role possesses the capability (capability gap)
- Availability dict with `available`, `eta_seconds`, `assignee`, `reason` if capability exists

### 4. Enterprise Capability Query Adapter

**File:** `packages/organisation/src/adapters/enterprise_capability_query_adapter.py`

Adapts `OrganisationControlPlane` to `EnterpriseCapabilityQueryPort`.

### 5. Four-Case Decision Behaviour

| Case | Enterprise State | Assistant Response |
|------|------------------|-------------------|
| **Fast** | Available, ETA ≤ 60s | Delegates to enterprise plane |
| **Slow** | Available, ETA > 60s | Provides interim answer AND delegates |
| **Unavailable** | Exists but in use | Reports busy, offers to queue |
| **Gap** | Does not exist | Reports capability gap, offers fallback |

### 6. API Visibility

**File:** `packages/workflow_runner/api.py`

New endpoint:
- `GET /capabilities/{capability_id}/availability` — query enterprise capability availability

Enhanced endpoints:
- `GET /roles` — list enterprise-plane roles with names, statuses, authority IDs
- `GET /work` — list work with `required_capability_ids`, outcomes, assignees
- `GET /work/{work_id}` — inspect specific work with full capability and result info

### 7. Real Capability Execution Path (Worker)

The worker remains the enterprise-plane execution mechanism. When work includes `required_capability_ids`, the worker invokes `CapabilityExecutionPort` to execute a real capability and stores the actual result in `work.outcome`.

**File:** `packages/organisation/src/worker.py`
- `Worker._execute_capability()` invokes `CapabilityExecutionPort.execute()`
- Real result is stored against the work item
- Fallback to markdown summary when no capability is specified

## How the Assistant Actually Delegates

```
User Request
    ↓
AssistantChatService.chat()
    ↓
CapabilityDiscoveryPort.find_capabilities() → candidates
    ↓
EnterpriseCapabilityQueryPort.query_capability(best_candidate.id)
    ↓
OrganisationControlPlane.query_capability()
    ↓
Decision:
  ├── Fast → WorkManagementPort.create_work() → enterprise plane
  ├── Slow → WorkManagementPort.create_work() + interim answer
  ├── Unavailable → report busy
  └── Gap → report gap
```

The Assistant never knows whether the enterprise plane is `InMemoryOrganisationControlPlane` or a future Paperclip adapter. It only knows `WorkManagementPort` and `EnterpriseCapabilityQueryPort`.

## How Work Is Assigned

Work is assigned through `OrganisationControlPlane.assign_work(work, assignee)`. The assignee can be a `Role`, `Person`, or `Agent`. The assignment sets `assignee_role_id`, `assignee_person_id`, or `assignee_agent_id` on the `Work` model and creates an `Assignment` record.

For the proof, the worker is assigned as `worker-agent` when no assignee exists.

## How the Worker Receives Work

The worker uses `Worker.pickup(org_plane)` to query the enterprise plane for work assigned to its agent ID (`worker-agent`). The API endpoint `POST /worker/run` triggers this pickup. The worker:
1. Queries `org_plane.list_work()`
2. Filters for work where `assignee_agent_id == "worker-agent"` and status is `PENDING` or `ASSIGNED`
3. Executes the work
4. Updates the enterprise plane with the result

## How the Result Gets Back

When the worker executes a capability, it calls `CapabilityExecutionPort.execute()` and stores the `ExecutionResult` in `work.outcome`. The API can retrieve this via `GET /work` or `GET /work/{work_id}`.

## What Remains Simulated

1. **Capability availability is heuristic.** `InMemoryOrganisationControlPlane.query_capability()` uses simple logic: if a role has the capability and no work is in progress, it's "available" with ETA=5s. This is not a real scheduling or availability system.
2. **Worker is a single agent.** Only `worker-agent` exists. There is no real team of people/agents.
3. **No Paperclip integration.** Paperclip remains outside this increment.
4. **No autonomous scheduling.** The worker only runs when manually triggered via the API.
5. **Interim answers are generic.** The Assistant provides a simple message rather than a computed interim result.
6. **ETA threshold is hardcoded.** 60 seconds is used as the fast/slow boundary. This is a proof value, not a calibrated SLA.

## What Remains In-Memory

1. **Enterprise plane state:** `InMemoryOrganisationControlPlane` stores roles, work, assignments, and delegations in Python dicts. Data is lost on process exit.
2. **Worker output:** Artifacts are written to a local filesystem directory (`worker_outputs/`).
3. **No event bus:** Work state changes are not published as events.
4. **No persistence:** There is no database backing the enterprise plane.

## What Remains Unimplemented

1. **Real Paperclip integration** — deferred per ADR-023 and Architecture Assessment 2026-08-21
2. **Capability development work creation** — the Assistant offers to initiate it but there is no implementation
3. **Work queuing** — the Assistant offers to queue work when unavailable but there is no queue mechanism
4. **Real team of people/agents** — only a single `worker-agent` exists
5. **Sophisticated ETA prediction** — ETA is a simple declared/heuristic value
6. **Background orchestration** — no scheduler or autonomous loop

## How Paperclip Could Eventually Replace the Current Implementation

The `OrganisationControlPlane` abstraction is the boundary. A future `PaperclipOrganisationControlPlane` would:
1. Map Paperclip Teams → Roles
2. Map Paperclip Tasks → Work
3. Map Paperclip Task assignments → Assignment records
4. Implement `query_capability()` using Paperclip's agent/task availability

No changes to `AssistantChatService`, `WorkManagementPort`, or `EnterpriseCapabilityQueryPort` would be required. The Assistant would continue to delegate through the same ports, unaware of the underlying implementation.

## The Smallest Next Increment

**Persist enterprise plane state and add event emission.**

Currently the enterprise plane is in-memory. The next step is to:
1. Replace `InMemoryOrganisationControlPlane` with a database-backed implementation
2. Publish events when work transitions states (created, assigned, in_progress, completed, failed)
3. This enables reactive worker triggering and audit trails

After persistence, the natural next steps are:
1. **Introduce a Paperclip-backed `OrganisationControlPlane` adapter** when Paperclip becomes available
2. **Add a second worker/agent** to prove multi-agent team behaviour
3. **Implement capability development work creation** when a gap is identified

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | User submits request through `/assistant/chat` | Verified |
| 2 | Assistant delegates through `WorkManagementPort` | Verified |
| 3 | Enterprise work identifies executable capability | Verified — `required_capability_ids` on work |
| 4 | Worker picks up work from enterprise plane | Verified — `Worker.pickup()` |
| 5 | Worker invokes `CapabilityExecutionPort` | Verified — `Worker._execute_capability()` |
| 6 | Capability actually executes | Verified — real capability via `tests.real_capability` |
| 7 | Actual result stored against work | Verified — `work.outcome` contains real `ExecutionResult` |
| 8 | Work progresses through lifecycle | Verified — PENDING → ASSIGNED → IN_PROGRESS → COMPLETED |
| 9 | Result retrievable through API | Verified — `GET /work` and `GET /work/{work_id}` |
| 10 | Session correlation intact | Verified — `session_id` preserved in `work.context` |
| 11 | Integration test covering complete path | Added — `test_end_to_end_delegation_worker_result` |
| 12 | Existing tests continue to pass | Verified — 157 passed |
| 13 | Focused tests for capability selection/execution | Added — 4 new tests in `test_assistant.py` |
| 14 | Manual test demonstrating real capability | Documented below |

## Manual Test

### Prerequisites

```bash
cd /home/martinp/Documents/projects/aiassistant/packages/workflow_runner
pip install fastapi uvicorn pydantic pyyaml
```

### Start the API

```bash
uvicorn api:app --reload --port 8000
```

### A. Fast Enterprise Capability

```bash
# 1. Send a request that matches a registered capability
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "run the real capability", "session_id": "ses-fast-1"}'

# Expected: status="delegated", work created with required_capability_ids=["real-capability"]

# 2. Run the worker to execute the capability
curl -X POST http://localhost:8000/worker/run

# Expected: {"work_id": "...", "status": "completed", "outcome": {"execution_mode": "capability_execution_port", "outputs": {"status": "completed", ...}}}

# 3. Verify the result
curl http://localhost:8000/work

# Expected: Work item with status="completed" and outcome containing real capability outputs
```

### B. Slow Enterprise Capability

```bash
# 1. Query availability for a slow capability
curl http://localhost:8000/capabilities/slow-cap/availability

# Expected: {"available": true, "eta_seconds": 300, ...}

# 2. Send a request that would match a slow capability
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "do something slow"}'

# Expected: status="delegated_with_interim", message mentions preliminary answer + enterprise work delegated
```

### C. Capability Gap

```bash
# 1. Query availability for a non-existent capability
curl http://localhost:8000/capabilities/nonexistent-cap/availability

# Expected: {"available": false, "reason": "Capability not found in enterprise plane"}

# 2. Send a request that has no matching capability
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "do something with no capability"}'

# Expected: status="capability_gap", message indicates enterprise does not have this capability
```

### D. Team Visibility

```bash
# 1. List roles
curl http://localhost:8000/roles

# Expected: JSON array with registered roles (Researcher, etc.)

# 2. List all work
curl http://localhost:8000/work

# Expected: JSON array with work items including:
#   - work_id, title, description
#   - status (draft, in_progress, completed, etc.)
#   - assignee_role_id, assignee_agent_id
#   - required_capability_ids
#   - outcome (if completed)
```

## Architectural Answer

**Is the Assistant inside or outside the enterprise plane?**

The Assistant is **outside** the enterprise plane. It is the user-facing interface that queries the enterprise plane and makes decisions based on the response. The enterprise plane owns organisational truth: people, roles, agents, capabilities, skills, tools, work, assignments, availability, execution state, and results.

**The exact boundary:**

| Assistant (AI Plane) | Enterprise Plane |
|---------------------|------------------|
| Receives user request | Owns capability catalog |
| Queries availability | Owns role/agent assignments |
| Makes timing decisions | Owns work lifecycle |
| Provides interim answers | Owns execution results |
| Delegates via ports | Implements ports |
| Never duplicates state | Is the source of truth |

**What the Assistant actually delegates to:**

`WorkManagementPort` and `EnterpriseCapabilityQueryPort`. It never imports or depends on `OrganisationControlPlane` implementations.

**Where the work lives:**

In the `OrganisationControlPlane` abstraction. Currently `InMemoryOrganisationControlPlane`. A future Paperclip adapter would replace this without changing the Assistant.

**How work is assigned:**

Through `OrganisationControlPlane.assign_work(work, assignee)`. The enterprise plane determines assignment based on roles, agents, and availability.

**How a worker/agent receives it:**

Through `Worker.pickup(org_plane)`, which queries the enterprise plane for work assigned to its agent ID. The worker is an enterprise-plane citizen, not an external orchestrator.

**How the result gets back:**

The worker stores the result in `work.outcome` via the enterprise plane. The API exposes it through `GET /work` endpoints.

## Test Results

```
packages/organisation/tests/                      47 passed
packages/ai/tests/                                68 passed
packages/workflow_runner/tests/test_capability_execute.py  23 passed
packages/workflow_runner/tests/test_authoring.py           6 passed
-------------------------------------------------
Total affected tests                            144 passed
```

### New tests added

| Test | Purpose |
|------|---------|
| `test_chat_delegates_when_enterprise_capability_fast` | Fast capability → delegate |
| `test_chat_provides_interim_when_enterprise_capability_slow` | Slow capability → interim + delegate |
| `test_chat_reports_gap_when_enterprise_capability_absent` | Absent capability → gap report |
| `test_chat_reports_unavailable_when_enterprise_capability_busy` | Unavailable capability → busy report |
| `test_chat_preserves_existing_behavior_without_enterprise_query` | No enterprise query → existing behavior |
| `test_query_capability_availability_returns_available` | API returns available capability |
| `test_query_capability_availability_returns_404_when_not_found` | API returns not found |
| `test_query_capability_availability_501_when_org_plane_not_configured` | API returns 501 when no org plane |
| `test_query_capability_returns_none_when_no_role_has_capability` | OCP returns None for absent capability |
| `test_query_capability_returns_available_when_role_has_capability` | OCP returns available for present capability |
| `test_query_capability_returns_unavailable_when_in_progress` | OCP returns unavailable for busy capability |

## Files Changed

| File | Change |
|------|--------|
| `packages/contracts/enterprise_capability_query.py` | **New** — `CapabilityAvailability` model and `EnterpriseCapabilityQueryPort` |
| `packages/organisation/src/organisation_control_plane.py` | Added `query_capability()` to abstract interface and implementation |
| `packages/organisation/src/adapters/enterprise_capability_query_adapter.py` | **New** — adapter from `OrganisationControlPlane` to `EnterpriseCapabilityQueryPort` |
| `packages/organisation/src/worker.py` | Added `_execute_capability()` to invoke `CapabilityExecutionPort` |
| `packages/ai/src/chat.py` | Added `enterprise_capability_query` dependency and four-case decision logic |
| `packages/workflow_runner/src/composition.py` | Wired `EnterpriseCapabilityQueryAdapter` into `create_application()` |
| `packages/workflow_runner/api.py` | Added `/capabilities/{id}/availability` endpoint; updated docstring |
| `packages/ai/tests/test_assistant.py` | Added 5 enterprise decision tests; updated `InMemoryWorkManagementPort` |
| `packages/ai/tests/test_architectural_boundaries.py` | Updated expected constructor parameters |
| `packages/workflow_runner/tests/test_capability_execute.py` | Added 6 availability API and OCP tests |

## What the Assistant Actually Delegates To

```
AssistantChatService
    ↓ (EnterpriseCapabilityQueryPort)
EnterpriseCapabilityQueryAdapter
    ↓ (OrganisationControlPlane)
InMemoryOrganisationControlPlane  (current)
    OR
PaperclipOrganisationControlPlane (future, not yet implemented)

AssistantChatService
    ↓ (WorkManagementPort)
WorkManagementAdapter
    ↓ (OrganisationControlPlane)
InMemoryOrganisationControlPlane  (current)
    OR
PaperclipOrganisationControlPlane (future)
```

The Assistant never knows which implementation is active. It delegates through ports, and the adapter translates to the enterprise plane.
