# Increment 21Q — Organisation Vertical Slice

**Status:** Implementation complete.  
**Objective:** Prove the end-to-end path: User → Chat → Assistant (inside Organisation) → Organisation Control Plane → delegated task → worker/agent → result → Assistant → User.

---

## A. What Was Found

### Existing integration points

| Component | Location | Status |
|-----------|----------|--------|
| `WorkManagementPort` | `packages/contracts/work_management.py` | Defined — `create_work()`, `mark_ready()`, `get_work()` |
| `OrganisationControlPlane` | `packages/organisation/src/organisation_control_plane.py` | Implemented — `InMemoryOrganisationControlPlane` with `assign_work()`, `get_work()`, `mark_work_ready()` |
| `OrganisationalContextPort` | `packages/contracts/organisational_context.py` | Defined — `get_context()`, `get_role()` |
| `OrganisationalContextAdapter` | `packages/organisation/src/adapters/organisational_context_adapter.py` | Implemented |
| `InMemoryWorkManagementPort` | `packages/ai/tests/fixtures/in_memory_ports.py` | Test fixture only |
| `/tasks` endpoints | `packages/workflow_runner/api.py` | In-memory only, not connected to org plane |
| Paperclip | **Not implemented** | Future integration behind `OrganisationControlPlane` |

### What was missing

1. **No `WorkManagementAdapter`** — `OrganisationControlPlane` had no adapter implementing `WorkManagementPort`.
2. **Assistant never delegates** — `AssistantChatService` accepted `work_management` but never called it.
3. **No wiring in composition** — `create_application()` did not wire `work_management` or `organisational_context`.
4. **No work visibility endpoints** — The API had no way to inspect work in the Organisation.
5. **No worker/agent** — No component to process delegated work.

---

## B. What Was Implemented

### 1. WorkManagementAdapter

**File:** `packages/organisation/src/adapters/work_management_adapter.py`

Adapts `OrganisationControlPlane` to `WorkManagementPort`:
- `create_work()` → creates `Work`, assigns to a role, returns `WorkReference`
- `mark_ready()` → calls `mark_work_ready()`
- `get_work()` → retrieves work by ID

### 2. Composition wiring

**File:** `packages/workflow_runner/src/composition.py`

Added `create_application()` that wires:
- `InMemoryOrganisationControlPlane`
- `OrganisationalContextAdapter`
- `WorkManagementAdapter`
- `create_assistant()` with all ports injected

### 3. Delegation path in Assistant

**File:** `packages/ai/src/chat.py`

Added `_delegate_work_response()` method. Triggered when:
- No capability matches (`NoCapabilityMatch`)
- AND `WorkManagementPort` is available

The Assistant creates work via `WorkManagementPort.create_work()` and returns a `delegated` status response with the work ID.

### 4. Work visibility API endpoints

**File:** `packages/workflow_runner/api.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/work` | GET | List all work items from Organisation |
| `/work/{work_id}` | GET | Get specific work item |
| `/work/{work_id}/process` | POST | Minimal worker stub — marks work as completed |

### 5. Minimal worker stub

**File:** `packages/workflow_runner/api.py` (`POST /work/{work_id}/process`)

A manual worker trigger that:
1. Retrieves work from the Organisation
2. Sets status to `COMPLETED`
3. Records an outcome dict
4. Returns the result

This is the simplest possible worker — a manual API trigger rather than an autonomous background process. It proves the handoff without requiring a full agent runtime.

### 6. Tests

**Added to `packages/ai/tests/test_assistant.py`:**
- `test_chat_delegates_to_enterprise_plane_when_no_capability_match`
- `test_chat_falls_through_to_pattern_execution_when_no_work_management`
- `test_chat_delegation_uses_session_id`

**Added to `packages/workflow_runner/tests/test_capability_execute.py`:**
- `test_list_work_returns_empty_when_no_work`
- `test_get_work_returns_404_when_missing`
- `test_process_work_marks_completed`
- `test_work_endpoints_501_when_org_plane_not_configured`

---

## C. The Exact Interaction Path

```
User → POST /assistant/chat {"message": "Create a capability that researches X"}
       ↓
AssistantChatService.chat()
       ↓
 recognise() → ProblemFrame
       ↓
 CapabilityDiscoveryPort.find_capabilities() → [] (no match)
       ↓
 WorkManagementPort.create_work({
         title: "Create a capability that researches X",
         description: "...",
         accountable_role_id: "default",
         work_type: "project",
         priority: "normal"
       })
       ↓
OrganisationControlPlane.assign_work(work, role)
       ↓
 WorkReference(work_id="work-create-a-capability-that-researches-x", status="draft")
       ↓
 ChatResponse({
     status: "delegated",
     message: "I've delegated this to the Organisation. Work ID: work-... Status: draft.",
     telemetry: {work_id: "...", work_status: "draft", delegated: true}
   })
       ↓
User → GET /work
       ↓
Sees: [{"work_id": "work-create-a-capability-that-researches-x", "status": "draft", ...}]
       ↓
User → POST /work/work-create-a-capability-that-researches-x/process
       ↓
Work marked COMPLETED with outcome
       ↓
User → GET /work/work-create-a-capability-that-researches-x
       ↓
Sees: {"status": "completed", "outcome": {"result": "Processed: ...", "status": "completed"}}
```

---

## D. How to Manually Test

### Prerequisites

```bash
cd /home/martinp/Documents/projects/aiassistant/packages/workflow_runner
pip install fastapi uvicorn pydantic pyyaml  # if not already installed
```

### Start the API

```bash
uvicorn api:app --reload --port 8000
```

### Test the delegation path

```bash
# 1. Send a request that has no capability match
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a capability that researches X and reports back what tools and skills an agent would need."}'

# Expected: status="delegated", message mentions work ID, telemetry contains work_id

# 2. List all work in the Organisation
curl http://localhost:8000/work

# Expected: JSON array with the delegated work item

# 3. Get the specific work item
curl http://localhost:8000/work/work-create-a-capability-that-researches-x

# Expected: Work details with status="draft"

# 4. Process the work (simulate worker/agent)
curl -X POST http://localhost:8000/work/work-create-a-capability-that-researches-x/process

# Expected: {"work_id": "...", "status": "completed", "outcome": {...}}

# 5. Verify work is completed
curl http://localhost:8000/work/work-create-a-capability-that-researches-x

# Expected: status="completed", outcome populated
```

### Test with capability match (existing behaviour)

```bash
# If capabilities exist and match, the Assistant still uses the original
# capability execution path. Delegation only happens when no capability matches.
```

---

## E. Remaining Limitations

| Limitation | Why it exists | Next step |
|------------|--------------|-----------|
| **No real Paperclip integration** | Paperclip is a future integration behind `OrganisationControlPlane` | Implement Paperclip adapter when Paperclip is available |
| **Worker is a manual API trigger** | Autonomous worker requires agent runtime infrastructure | Add background worker or event-driven processor |
| **Single default role** | `create_application()` registers only `researcher` role | Populate roles from Paperclip or configuration |
| **No capability-to-work mapping** | Work is created with generic title/description | Map recognised intent to structured work templates |
| **No multi-turn delegation** | Each request creates independent work | Implement session-level work correlation |
| **No Paperclip-specific types** | Architecture keeps Paperclip behind org plane | Add Paperclip adapter when boundary is ready |

---

## F. What Remains Unchanged

- `RelevanceMatcher` scoring
- `CapabilityActionPolicy` behaviour
- Capability presentation rules
- Execution behaviour
- Existing `/assistant/chat` behaviour when capabilities DO match
- Existing `/assistant/capability/execute` behaviour
- Existing `/assistant/capability/feedback` behaviour
- Existing telemetry collection

---

## G. Test Results

All relevant tests pass.

```
92 passed, 4 warnings in 0.60s
```

- `packages/ai/tests/test_assistant.py` — 32 passed (including 3 new delegation tests)
- `packages/workflow_runner/tests/test_capability_execute.py` — 9 passed (including 4 new work endpoint tests)
- `packages/organisation/tests/` — 51 passed

**Note:** `packages/workflow_runner/tests/test_telemetry_lifecycle.py` has pre-existing module-reload issues that cause failures when run alongside other tests. This is unrelated to the Organisation changes.

---

## H. Files Changed

| File | Change |
|------|--------|
| `packages/organisation/src/adapters/work_management_adapter.py` | **New** — `WorkManagementAdapter` |
| `packages/workflow_runner/src/composition.py` | Added `create_application()` wiring org plane + work management |
| `packages/ai/src/chat.py` | Added `_delegate_work_response()`, triggered on `NoCapabilityMatch` |
| `packages/workflow_runner/api.py` | Added `/work` endpoints, wired org plane, added worker stub |
| `packages/ai/tests/test_assistant.py` | Added 3 delegation tests |
| `packages/workflow_runner/tests/test_capability_execute.py` | Added 4 work endpoint tests |

---

## I. What You Can See Now

1. **Chat delegation** — Send a message with no capability match → see `delegated` status with work ID
2. **Enterprise plane state** — `GET /work` shows all work items created by the Assistant
3. **Work lifecycle** — Create → inspect → process → complete
4. **Session correlation** — Delegated work preserves the session ID from the chat request
5. **No capability selection** — The Assistant does NOT build its own orchestration; it uses the Organisation interface

---

*The vertical slice is functional. Paperclip remains a future integration behind `OrganisationControlPlane` per ADR-023.*
