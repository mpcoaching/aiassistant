# Increment 21U — Prove the real Assistant ↔ Enterprise interaction

**Date:** 2026-08-26  
**Author:** Kilo  
**Status:** Complete

## Objective

Prove the actual interaction model between the Assistant (a role inside the Organisation) and the Organisation Control Plane visibly and end-to-end. Make the system usable enough that the user can interact with it as a team. Establish the correct decision boundary: the Assistant queries the Organisation for capability and availability, and the Organisation owns all organisational truth, scheduling, and assignment.

## What Is Now Genuinely Real

### 1. Three Interaction Paths Proven

The Assistant (as an organisational role) now handles three distinct interactions through the Organisation Control Plane:

| Path | Trigger | Assistant Response | Organisation Action |
|------|---------|-------------------|-------------------|
| **Fast** | Capability exists, ETA ≤ threshold | Delegates immediately | Accepts, assigns, executes |
| **Slow** | Capability exists, ETA > threshold | Provides explicitly labelled interim answer + delegates | Accepts, assigns, executes |
| **Gap** | Capability does not exist | Reports gap + initiates capability development work | Creates work item for capability development |

### 2. Assistant Queries Enterprise Before Deciding

**File:** `packages/ai/src/chat.py`
- `AssistantChatService.chat()` calls `_evaluate_enterprise_action()` when capability discovery returns candidates
- `_evaluate_enterprise_action()` queries `EnterpriseCapabilityQueryPort` for the best matching capability
- Decision logic routes to four handlers: fast, slow, unavailable, gap
- Capability gap handler creates enterprise work for capability development via `WorkManagementPort`

### 3. Organisation Is Source of Truth

**File:** `packages/organisation/src/organisation_control_plane.py`
- `query_capability(capability_id)` returns availability information
- Returns `None` if no role has the capability (gap)
- Returns availability dict with `available`, `eta_seconds`, `assignee`, `reason` if capability exists

### 4. API Visibility Into the Organisation

**File:** `packages/workflow_runner/api.py`

New and enhanced endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /capabilities` | List all registered capabilities with enterprise availability |
| `GET /capabilities/{id}/availability` | Query availability for a specific capability |
| `GET /roles` | List organisational roles |
| `GET /work` | List all work with assignees, capabilities, status, outcomes |
| `GET /work/{id}` | Inspect individual work lifecycle |

### 5. Enterprise Capability Query Wired Through Composition

**File:** `packages/workflow_runner/src/composition.py`
- `create_assistant()` accepts `enterprise_capability_query` parameter
- `create_application()` wires `EnterpriseCapabilityQueryAdapter` into the assistant

### 6. Module Loading Resilience

**File:** `packages/workflow_runner/api.py`
- Split monolithic `try/except` into two blocks
- Core Organisation setup (org plane, work management, assistant recreation) is isolated from optional capability registry setup
- If capability registry imports fail, core enterprise functionality still works
- `_capability_registry` initialized to `None` before try blocks to prevent `NameError`

## How the Interaction Works

### Fast Capability

```
User: "run the real capability"
    ↓
Assistant.chat()
    ↓
CapabilityDiscoveryPort.find_capabilities() → ["real-capability"]
    ↓
EnterpriseCapabilityQueryPort.query_capability("real-capability")
    ↓
OrganisationControlPlane.query_capability()
    ↓
Returns: {available: True, eta_seconds: 5, ...}
    ↓
ETA (5s) ≤ threshold (60s)
    ↓
WorkManagementPort.create_work(required_capability_ids=["real-capability"])
    ↓
Organisation assigns and executes
    ↓
Response: status="delegated", work_id="work-run-the-real-capabil"
```

### Slow Capability

```
User: "do something slow"
    ↓
Assistant.chat()
    ↓
CapabilityDiscoveryPort.find_capabilities() → ["slow-cap"]
    ↓
EnterpriseCapabilityQueryPort.query_capability("slow-cap")
    ↓
Returns: {available: True, eta_seconds: 300, ...}
    ↓
ETA (300s) > threshold (60s)
    ↓
_handle_slow_capability():
  1. Delegates work to Organisation
  2. Returns interim response
    ↓
Response: status="delegated_with_interim",
         message="The enterprise can produce the proper answer... 
                  I can give you a preliminary answer now..."
```

### Capability Gap

```
User: "do something impossible"
    ↓
Assistant.chat()
    ↓
CapabilityDiscoveryPort.find_capabilities() → ["gap-cap"]
    ↓
EnterpriseCapabilityQueryPort.query_capability("gap-cap")
    ↓
Returns: None (no role has this capability)
    ↓
_handle_capability_gap():
  1. Reports gap to user
  2. Creates work item: "Develop capability: gap-cap"
    ↓
Response: status="capability_gap",
         message="The enterprise does not currently have a capability for 'gap-cap'...
                  I've initiated work to develop this capability (Work ID: work-...)"
```

## API Exposure

The user can now inspect the organisation through the API:

```bash
# See the team
curl http://localhost:8000/roles

# See what the team can do
curl http://localhost:8000/capabilities

# See if a specific capability is available
curl http://localhost:8000/capabilities/real-capability/availability

# See all work
curl http://localhost:8000/work

# See a specific work item
curl http://localhost:8000/work/{work_id}

# Interact with the assistant
curl -X POST http://localhost:8000/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "run the real capability", "session_id": "ses-1"}'
```

## Final Architectural Test

**Question:** Where does the Assistant sit relative to the Organisation?

**Answer:** The Assistant is **inside** the Organisation. It is one role/agent within the organisation, not the organisation's interface to the user. The Chat/API/UI/Voice layer is outside the Organisation and is simply the interaction mechanism through which the user communicates with the Assistant.

**Question:** If I replaced the current Organisation implementation tomorrow, what code in the Assistant would have to change?

**Answer:** None.

The Assistant depends only on ports:
- `EnterpriseCapabilityQueryPort`
- `WorkManagementPort`

It never imports or references `InMemoryOrganisationControlPlane` or any other concrete implementation. A future `PaperclipOrganisationControlPlane` would implement the same ports. The Assistant would continue to delegate through the same interfaces, unaware of the underlying implementation.

The Assistant expresses intent; the Organisation Control Plane determines the operational mechanism.

## Files Changed

| File | Change |
|------|--------|
| `packages/ai/src/chat.py` | Added `_FAST_ENTERPRISE_ETA_THRESHOLD_SECONDS` constant; capability gap handler now creates enterprise work via `WorkManagementPort` |
| `packages/ai/tests/test_assistant.py` | Updated gap test to verify work creation and telemetry |
| `packages/workflow_runner/api.py` | Added `/capabilities` endpoint; wired `EnterpriseCapabilityQueryAdapter`; split try/except blocks; initialized `_capability_registry = None` |
| `packages/workflow_runner/tests/test_capability_execute.py` | Added 4 end-to-end integration tests for fast, slow, gap, and capabilities list paths |

## Test Results

```
packages/organisation/tests/                      47 passed
packages/ai/tests/                                68 passed
packages/workflow_runner/tests/test_capability_execute.py  46 passed
packages/workflow_runner/tests/test_authoring.py           6 passed
-------------------------------------------------
Total                                            167 passed
```

### New tests added

| Test | Purpose |
|------|---------|
| `test_fast_capability_end_to_end_via_api` | User asks → Assistant delegates → Work created in Organisation → retrievable via API |
| `test_slow_capability_produces_interim_via_api` | User asks → Enterprise reports slow ETA → Assistant provides interim answer + delegates |
| `test_capability_gap_creates_development_work_via_api` | User asks → No capability exists → Assistant reports gap + creates development work |
| `test_capabilities_list_endpoint_returns_capabilities` | API exposes capabilities with availability information |

## What Remains In-Memory

1. **Enterprise plane state:** `InMemoryOrganisationControlPlane` stores roles, work, assignments in Python dicts
2. **No persistence:** Data is lost on process exit
3. **No event bus:** Work state changes are not published as events
4. **Single worker:** Only conceptual; no autonomous worker loop yet

## What Remains Unimplemented

1. **Paperclip integration** — deferred
2. **Database persistence** — next increment
3. **Event bus** — next increment
4. **Real team of people/agents** — only a single researcher role exists
5. **Sophisticated ETA prediction** — ETA is heuristic
6. **Autonomous worker loop** — worker runs only when triggered via API

## The Smallest Next Increment

**Persist Organisation state and add event emission.**

Currently the Organisation is in-memory. The next step is to:
1. Replace `InMemoryOrganisationControlPlane` with a database-backed implementation
2. Publish events when work transitions states (created, assigned, in_progress, completed, failed)
3. This enables reactive worker triggering and audit trails

After persistence, the natural next steps are:
1. Introduce a Paperclip-backed `OrganisationControlPlane` adapter
2. Add a second worker/agent to prove multi-agent team behaviour
3. Implement capability development work tracking
