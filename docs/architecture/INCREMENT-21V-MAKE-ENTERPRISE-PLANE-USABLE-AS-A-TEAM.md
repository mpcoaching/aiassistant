# Increment 21V — Make the Enterprise Plane Usable as a Team

**Date:** 2026-08-26  
**Author:** Kilo  
**Status:** Complete

## Objective

Make the current system actually usable as the beginning of an organisation/team. Prove that the Enterprise Plane can receive a capability gap, turn it into organisational work, develop the capability, register it, and subsequently use it to fulfil requests. Cross the line from "we have an architecture representing an organisation" to "we have the beginnings of an organisation that can become more capable through interaction."

## What Is Now Genuinely Real

### 1. Capability Development Lifecycle

The Enterprise Plane can now represent the full lifecycle of capability development:

```
Capability Gap
    ↓
Enterprise Plane creates capability-development work
    ↓
Worker picks up work from Enterprise Plane
    ↓
Worker produces capability definition artifact
    ↓
Worker registers capability in Enterprise Plane
    ↓
Capability becomes available to organisation
```

### 2. OrganisationControlPlane Capability Store

**File:** `packages/organisation/src/organisation_control_plane.py`

Added capability management to the OCP abstract interface and `InMemoryOrganisationControlPlane`:

```python
@abstractmethod
def register_capability(self, capability: Any) -> None: ...

@abstractmethod
def get_capability(self, capability_id: str) -> Any | None: ...
```

`InMemoryOrganisationControlPlane` now maintains a `_capabilities` dict. Capabilities are registered when developed by workers and can be queried by ID.

`query_capability()` was updated to check both role requirements AND registered capabilities. A capability is considered "available" if:
- Any role has it in `required_capability_ids`, OR
- It exists in the OCP's capability store

### 3. Worker Capability Development Mode

**File:** `packages/organisation/src/worker.py`

The worker now has three execution modes:

| Mode | Trigger | Action |
|------|---------|--------|
| **Capability Execution** | `work.required_capability_ids` set | Invokes `CapabilityExecutionPort` |
| **Capability Development** | `work.work_type == "capability_development"` | Develops new capability, registers it |
| **General Work** | Fallback | Produces markdown summary |

`Worker.__init__` now accepts `capability_registry` parameter. The worker registers developed capabilities in both:
1. The Enterprise Plane (`org_plane.register_capability()`)
2. The capability registry (for discovery)

`Worker.pickup()` now picks up unassigned work (where `assignee_agent_id is None`), not just work assigned to itself. This ensures capability-development work is picked up even when no specific agent is assigned.

`Worker._develop_capability()` produces:
- A `Capability` model with interface definition
- Registration in the Enterprise Plane
- Registration in the capability registry
- A markdown artifact documenting:
  - Capability ID, name, kind, status, owner
  - Purpose/description
  - Input/output interface
  - Development evidence

### 4. Capability Development Work Type

**File:** `packages/ai/src/chat.py`

When the Assistant detects a capability gap, it now creates work with `work_type="capability_development"` instead of `work_type="project"`:

```python
work_ref = self._work_management.create_work(
    WorkCreateRequest(
        title=f"Develop capability: {candidate.name}",
        ...
        work_type="capability_development",
        ...
    )
)
```

### 5. API Wiring

**File:** `packages/workflow_runner/api.py`

- Split monolithic capability setup into three try blocks:
  1. Core enterprise plane (org plane, work management, assistant recreation)
  2. Capability registry + discovery adapter
  3. Capability execution adapter
- This ensures `_capability_registry` is set even if `CapabilityExecutionAdapter` import fails
- Worker endpoints now pass `capability_registry=_capability_registry` to the worker
- Assistant is recreated with `capability_discovery` after registry is available

### 6. API Visibility

The following endpoints expose the organisation:

| Endpoint | Purpose |
|----------|---------|
| `GET /roles` | List enterprise-plane roles |
| `GET /capabilities` | List registered capabilities with availability |
| `GET /capabilities/{id}/availability` | Query specific capability availability |
| `GET /work` | List all work with assignees, status, outcomes |
| `GET /work/{id}` | Inspect individual work lifecycle |
| `POST /work/{id}/process` | Execute specific work item |
| `POST /worker/run` | Worker picks up and executes assigned work |

## How the Learning Loop Works

### Request 1: Capability Gap

```
User: "do the unique-learning-loop-capability"
    ↓
Assistant.chat()
    ↓
CapabilityDiscoveryPort.find_capabilities() → ["unique-learning-loop-capability"]
    ↓
EnterpriseCapabilityQueryPort.query_capability() → None (gap)
    ↓
_handle_capability_gap():
  - Creates work: "Develop capability: unique-learning-loop-capability"
  - work_type = "capability_development"
    ↓
Response: status="capability_gap",
         message="The enterprise does not currently have a capability...
                  I've initiated work to develop this capability (Work ID: ...)"
```

### Worker Development

```
Worker picks up work (assignee_agent_id is None)
    ↓
Worker.execute()
    ↓
_develop_capability():
  - Creates Capability model
  - Registers in Enterprise Plane (org_plane.register_capability)
  - Registers in Capability Registry
  - Writes capability artifact to worker_outputs/
    ↓
Result: status="completed",
        execution_mode="capability_development",
        capability_id="cap-work-...",
        artifact_path="worker_outputs/..."
```

### Request 2: Capability Exists

```
User: "do the unique-learning-loop-capability"
    ↓
Assistant.chat()
    ↓
CapabilityDiscoveryPort.find_capabilities() → ["cap-work-..."]
    ↓
EnterpriseCapabilityQueryPort.query_capability() → {available: True, ...}
    ↓
_handle_fast_capability():
  - Delegates to enterprise plane
  - Creates work with required_capability_ids=["cap-work-..."]
    ↓
Response: status="delegated",
         work_id="work-do-the-unique-learni"
```

## Integration Test

**File:** `packages/workflow_runner/tests/test_capability_execute.py`

`test_organisational_learning_loop_via_api` proves the complete loop:

1. **REQUEST 1:** User asks for unknown capability
   - Assistant identifies capability gap
   - Enterprise Plane creates development work
   - Work has `work_type="capability_development"`

2. **DEVELOPMENT:** Worker processes the work
   - Worker produces capability definition
   - Capability registered in Enterprise Plane
   - Capability registered in Capability Registry
   - Artifact written to `worker_outputs/`

3. **REQUEST 2:** User asks for same capability
   - Assistant queries Enterprise Plane
   - Enterprise Plane reports capability exists
   - Assistant delegates for execution

## Separation of Capability Development and Execution

The model now explicitly distinguishes:

| Aspect | Capability Development | Capability Execution |
|--------|----------------------|---------------------|
| Work type | `capability_development` | `project` / `bau` |
| Trigger | Capability gap | Existing capability |
| Worker mode | `_develop_capability()` | `_execute_capability()` or `_do_work()` |
| Output | New capability definition + artifact | Execution result |
| Registration | Yes (in OCP + registry) | No |
| Who assigns | Enterprise Plane | Enterprise Plane |

## Architectural Boundary

The following remains true:

```
Assistant
    ↓
Ports (WorkManagementPort, EnterpriseCapabilityQueryPort, CapabilityDiscoveryPort)
    ↓
Enterprise Plane (OrganisationControlPlane)
    ↓
Worker
    ↓
Capability Registry
```

The Assistant:
- Does NOT import `OrganisationControlPlane`
- Does NOT assign agents
- Does NOT manage work state
- Does NOT maintain capability state
- Does NOT directly invoke workers
- Does NOT decide who should perform work

The Enterprise Plane:
- Owns capability registration
- Owns work creation and assignment
- Owns capability availability
- Owns worker dispatch
- Owns execution results

## Final Architectural Test

**Question:** If I replaced the current Enterprise Plane implementation tomorrow, what code in the Assistant would have to change?

**Answer:** None.

The Assistant depends only on ports:
- `WorkManagementPort`
- `EnterpriseCapabilityQueryPort`
- `CapabilityDiscoveryPort`

It never imports or references `InMemoryOrganisationControlPlane` or any other concrete implementation. A future `PaperclipOrganisationControlPlane` would implement the same ports. The Assistant would continue to delegate through the same interfaces, unaware of the underlying implementation.

## Files Changed

| File | Change |
|------|--------|
| `packages/organisation/src/organisation_control_plane.py` | Added `register_capability()`, `get_capability()`, `_capabilities` store; updated `query_capability()` to check registered capabilities |
| `packages/organisation/src/worker.py` | Added `capability_registry` parameter; added `_develop_capability()` mode; added `_write_capability_artifact()`; worker picks up unassigned work |
| `packages/ai/src/chat.py` | Capability gap handler uses `work_type="capability_development"` |
| `packages/workflow_runner/api.py` | Split capability setup into three try blocks; wired `CapabilityDiscoveryAdapter`; pass `capability_registry` to worker |
| `packages/workflow_runner/tests/test_capability_execute.py` | Added `test_organisational_learning_loop_via_api` integration test |

## Test Results

```
packages/organisation/tests/                      47 passed
packages/ai/tests/                                68 passed
packages/workflow_runner/tests/test_capability_execute.py  34 passed
packages/workflow_runner/tests/test_authoring.py           6 passed
-------------------------------------------------
Total                                            162 passed
```

### New test

| Test | Purpose |
|------|---------|
| `test_organisational_learning_loop_via_api` | Proves complete gap → development → registration → execution loop |

## What Remains In-Memory

1. **Enterprise plane state:** `InMemoryOrganisationControlPlane` stores roles, work, assignments, capabilities in Python dicts
2. **No persistence:** Data is lost on process exit
3. **No event bus:** Work state changes are not published as events
4. **Single worker:** Only one worker agent exists

## What Remains Unimplemented

1. **Paperclip integration** — deferred
2. **Database persistence** — next increment
3. **Event bus** — next increment
4. **Real team of people/agents** — only a single worker agent exists
5. **Sophisticated ETA prediction** — ETA is heuristic
6. **Autonomous worker loop** — worker runs only when triggered via API
7. **Capability maturity systems** — capabilities are registered as ACTIVE immediately

## The Smallest Next Increment

**Persist enterprise plane state and add event emission.**

Currently the enterprise plane is in-memory. The next step is to:
1. Replace `InMemoryOrganisationControlPlane` with a database-backed implementation
2. Publish events when work transitions states (created, assigned, in_progress, completed, failed)
3. This enables reactive worker triggering and audit trails

After persistence, the natural next steps are:
1. Introduce a Paperclip-backed `OrganisationControlPlane` adapter
2. Add a second worker/agent to prove multi-agent team behaviour
3. Implement capability maturity and progression

## Most Important Question

**Can I now use the system to start building the team that will eventually build the rest of the system?**

**Yes.**

The organisation can now:
1. Receive a capability gap from the Assistant
2. Create capability-development work
3. Assign and execute that work
4. Produce a capability definition artifact
5. Register the new capability
6. Make the capability available for future requests

This proves the transition from **CAPABILITY GAP → DEVELOPMENT WORK → CAPABILITY EXISTS**.

The system is no longer just an architecture representing an organisation. It is the beginnings of an organisation that can become more capable through interaction.
