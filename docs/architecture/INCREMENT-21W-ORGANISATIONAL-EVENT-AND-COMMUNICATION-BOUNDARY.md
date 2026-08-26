# Increment 21W — Organisational Event and Communication Boundary

**Date:** 2026-08-26  
**Author:** Kilo  
**Status:** Complete

## Executive Summary

This increment investigates and establishes the smallest viable foundation for an Organisational Event / Signal Boundary. The investigation confirms that Paperclip is **not present in the local codebase** — it remains a future, unimplemented backend behind the `OrganisationControlPlane` abstraction. Despite this, the increment defines:

1. A clear event/signal contract that is independent of any operational system
2. Tenant/organisation context carried explicitly through all events and work
3. A minimal capacity-pressure detection concept
4. Architectural rules preventing the event boundary from becoming an orchestration engine
5. Documentation of how Paperclip could eventually participate without owning the architecture

The result is an architecture that can evolve from single-user to multi-tenant platform without rewriting the Assistant, Organisation abstraction, capability model, or communication boundary.

## Paperclip Investigation

### Finding: Paperclip Is Not Available Locally

After exhaustive search of the repository, installed packages, running containers, and environment configuration:

- **No Paperclip source code exists** anywhere in the repository
- **No Paperclip Python package is installed**
- **No Paperclip containers or services are defined** in `docker-compose.*.yml`
- **Architecture explicitly defers integration** — ADR-023 (Accepted, deferred) states a Paperclip adapter will implement `OrganisationControlPlane` in a future increment, but it has **not been implemented**
- **Architecture explicitly rejects adoption** — ADR-005 (Rejected) and the Architecture Assessment 2026-08-21 state Paperclip is **not adopted as an architectural component** for the current implementation

### What This Means for the Event Boundary

Because Paperclip is not present, **all specific implementation details remain unverified**:

| Question | Status |
|----------|--------|
| How tasks are created in Paperclip | Unverified |
| How tasks enter an agent's mailbox/inbox | Unverified |
| How an agent is woken | Unverified |
| How heartbeat processing works | Unverified |
| What service performs task dispatch | Unverified |
| Whether there are internal events | Unverified |
| Whether those events are observable externally | Unverified |
| Whether there are webhooks, callbacks, APIs, queues, plugins, adapters or extension points | Unverified (adapter model documented conceptually only) |
| Whether task creation can be intercepted | Unverified |
| Whether task assignment can be intercepted | Unverified |
| Whether heartbeat processing can be observed or influenced | Unverified |
| Whether a task can be prevented from waking an agent | Unverified |
| Whether a task can be re-assigned before execution | Unverified |
| Whether mailbox state can be observed without modifying Paperclip | Unverified |
| Whether Paperclip supports multiple companies in one deployment | Partially documented (conceptual only) |
| Which resources are shared between companies | Unverified |
| Which components can be horizontally scaled | Unverified |
| Which components remain singleton | Unverified |
| Whether one tenant can create resource contention for another | Unverified |

### Architectural Decision

Given that Paperclip is unavailable, the event boundary must be designed to be **agnostic to the underlying operational system**. The boundary must:

1. Define its own event/signal contracts
2. Allow any operational system (Paperclip, custom, future) to emit events through an adapter
3. Keep the Organisation layer independent of operational implementation details

This is consistent with the existing `OrganisationControlPlane` abstraction, which already isolates the organisation from operational details.

## Organisational Event Model

### Core Principle

**Operational systems report what happened. The Organisation layer determines what it means.**

### Operational Events

Operational events are immutable facts reported by operational systems:

| Event | Origin | Meaning |
|-------|--------|---------|
| `work.created` | WorkManagement | A new work item was created |
| `work.assigned` | WorkManagement | Work was assigned to a role/agent |
| `work.queued` | WorkManagement | Work is waiting for capability availability |
| `work.started` | Operational | Work execution began |
| `work.completed` | Operational | Work execution finished successfully |
| `work.failed` | Operational | Work execution failed |
| `work.escalated` | Organisation | Work requires escalation |
| `work.cancelled` | WorkManagement | Work was cancelled |
| `capability.development.started` | Organisation | Capability development began |
| `capability.development.completed` | Organisation | Capability development finished |
| `capability.registered` | Organisation | New capability registered |
| `capability.bottleneck.detected` | Organisation | Capability is blocking workflow |
| `agent.heartbeat` | Operational | Agent is alive |
| `agent.available` | Operational | Agent has capacity |
| `agent.busy` | Operational | Agent is at capacity |
| `agent.overloaded` | Organisation | Agent is overloaded |

### Organisational Signals

Organisational signals are interpretations derived from operational events:

| Signal | Derived From | Meaning |
|--------|-------------|---------|
| `capacity.pressure.detected` | Multiple work.assigned + agent.busy | Demand exceeds capacity for a capability |
| `capacity.shortfall.detected` | work.queued + capability.bottleneck | No agent can fulfil pending work |
| `work.sla_risk.detected` | work.assigned + ETA analysis | Work may miss its SLA |
| `capability.bottleneck.detected` | work.queued + no agent available | Capability is blocking workflow progress |
| `agent.overloaded` | Multiple work.assigned to same agent | Agent has unsustainable workload |
| `capability.development.required` | capability.bottleneck + no resolution | Organisation needs to develop new capability |
| `work.escalation.required` | work.failed + retry exhausted | Human intervention needed |

### Key Distinction

```python
# Operational event: three delayed heartbeats
agent.heartbeat(delayed=True)
agent.heartbeat(delayed=True)
agent.heartbeat(delayed=True)

# Organisational signal: NOT automatically "agent is bad"
# Organisation may determine:
#   "Agent D is healthy, but Research capability is experiencing
#    sustained demand pressure from three concurrent requests."
capacity.pressure.detected(capability="research", ...)
```

## Tenant Context

### Explicit Organisation Identity

Every organisational event and piece of work carries an explicit `organisation_id`:

```python
class OrganisationalContext(BaseModel):
    organisation_id: str = "default"
    current_actor_id: str | None = None
    current_role_id: str | None = None
    ...

class Work(BaseModel):
    id: str
    title: str
    organisation_id: str = "default"
    ...

class Assignment(BaseModel):
    id: str
    work_id: str
    organisation_id: str = "default"
    ...
```

### Architectural Invariant

Every organisational event and piece of work that can eventually cross a tenant boundary must have an unambiguous organisation/tenant context. This is established now to avoid retrofitting later.

## Event Boundary Architecture

### Where the Boundary Sits

```
                         USER
                           │
                           ▼
                      ASSISTANT
                           │
                           ▼
                 ┌───────────────────┐
                 │ Organisation      │
                 │ Abstraction       │
                 │ / Control Layer   │
                 └─────────┬─────────┘
                           │
                ┌──────────▼──────────┐
                │ Communication /     │
                │ Event Boundary      │
                └──────────┬──────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         Paperclip                  Other systems
```

### What Belongs Inside/Outside Paperclip

| Concern | Inside Paperclip | Outside Paperclip (Our Boundary) |
|---------|------------------|----------------------------------|
| Task creation | Yes | WorkManagementAdapter translates to/from |
| Agent mailbox | Yes | Observable via events |
| Agent wake/sleep | Yes | Observable via events |
| Heartbeat scheduling | Yes | Observable via events |
| Task dispatch | Yes | WorkManagementAdapter translates to/from |
| Capability registry | No | Organisation layer owns this |
| Work assignment logic | No | Organisation layer decides |
| Capacity analysis | No | Organisation layer derives signals |
| SLA monitoring | No | Organisation layer derives signals |
| Capability development | No | Organisation layer initiates |
| Multi-tenant isolation | No | Organisation layer enforces |

### Event Boundary Contracts

```python
class OrganisationalEventEmitterPort(Protocol):
    def emit(self, event: OrganisationalEvent) -> None: ...

class OrganisationalSignalEmitterPort(Protocol):
    def emit_signal(self, signal: OrganisationalSignal) -> None: ...
```

Implementations may:
- Buffer events for later processing
- Publish to a message bus
- Stream to an external system
- Log to a file
- Do nothing (no-op)

The Organisation layer does not depend on any specific transport.

### In-Memory Implementation

`InMemoryOrganisationControlPlane` now supports:

```python
org = InMemoryOrganisationControlPlane()

# Register event handlers
org.on_event(lambda event: print(f"Event: {event.event_type}"))
org.on_signal(lambda signal: print(f"Signal: {signal.signal_type}"))

# Emit events directly
org.emit_event(WorkEvent(...))

# Emit signals directly
org.emit_signal(CapacityPressureSignal(...))

# Detect capacity pressure
signal = org.detect_capacity_pressure("research")
```

## Capacity Awareness

### Minimal Proof-of-Concept

The Organisation layer can now derive capacity pressure from observable work state:

```python
def detect_capacity_pressure(self, capability_id: str) -> CapacityPressureSignal | None:
    in_progress = [work for work in self._work.values()
                   if capability_id in work.required_capability_ids
                   and work.status in (IN_PROGRESS, ASSIGNED)]
    pending = [work for work in self._work.values()
               if capability_id in work.required_capability_ids
               and work.status == PENDING]
    
    if total_load > 1:
        return CapacityPressureSignal(
            capability_id=capability_id,
            demand_rate_per_hour=float(total_load),
            capacity_rate_per_hour=float(len(in_progress)),
            queue_depth=len(pending),
            ...
        )
```

### How This Supports Future Capacity Management

```
Capacity pressure detected
    ↓
Organisation layer may eventually:
    ├── Reassign work to another capable agent
    ├── Initiate capability development
    ├── Create/train additional agents
    └── Escalate to human stakeholders
```

This increment proves the **information flow**. The decision system is not yet implemented.

### The Assistant Does Not Manage Capacity

The Assistant queries organisational capability and may receive signals, but it does not:
- Make capacity decisions
- Reassign work
- Create agents
- Adjust scheduling

These remain Organisation layer responsibilities.

## Multi-Tenant Scaling Assessment

### Current State

The system currently uses `organisation_id = "default"` everywhere. Multi-tenancy is not implemented, but the architectural invariant is established.

### Investigated Concerns

| Concern | Status | Notes |
|---------|--------|-------|
| API saturation | Unverified | No Paperclip API available to test |
| Heartbeat scheduling | Unverified | No Paperclip available |
| Database contention | N/A | No database in current implementation |
| Queue contention | Unverified | No message queue in current implementation |
| Agent execution contention | Unverified | No Paperclip available |
| Model/LLM contention | Unverified | No LLM provider configuration |
| Memory/CPU contention | Unverified | Single-process in-memory implementation |
| Shared filesystem/object storage | Unverified | Worker outputs use local filesystem |
| Connection pool contention | Unverified | No external connections |
| Per-company isolation | Architectural invariant | `organisation_id` on all events/work |
| Horizontal scaling | Documented as future | Event boundary designed to support it |
| Worker scaling | Documented as future | Worker endpoints are stateless |
| Scheduler scaling | Documented as future | No scheduler in current implementation |

### Preferred Long-Term Architecture

```
Scale communication, execution and model resources independently
wherever possible, with the event/communication layer providing
buffering and distribution.
```

The event boundary is designed to support this:
- Events are immutable and carry tenant context
- Event emitters are pluggable
- No singleton assumptions in the event contract
- The Organisation layer remains the source of truth regardless of scale

## What the Event Boundary Is NOT

The event system is **not**:

- A second orchestration engine
- An agent that decides what everybody should do
- A replacement for Paperclip's mailbox
- A task-stealing mechanism
- A heartbeat suppressor
- An agent cloner

Its job is **communication, observation and distribution**.

The Organisation layer remains responsible for organisational decisions.

## Preservation of the Organisation Abstraction

The existing abstraction layer remains intact:

```
Assistant
   ↓
Ports
   ↓
Organisation abstraction
   ↓
Implementation
```

The Assistant does not:
- Import `OrganisationControlPlane`
- Know about Paperclip
- Manage work state
- Maintain capability state
- Maintain team state
- Directly invoke workers
- Decide who should perform work

The Organisation abstraction:
- Owns capability registration
- Owns work creation and assignment
- Owns capability availability
- Owns worker dispatch
- Owns execution results
- Owns event emission
- Owns signal derivation

## Final Architectural Test

**Question:** If I replaced the current Enterprise Plane implementation tomorrow, what code in the Assistant would have to change?

**Answer:** None.

The Assistant depends only on ports:
- `WorkManagementPort`
- `EnterpriseCapabilityQueryPort`
- `CapabilityDiscoveryPort`

It never imports or references `InMemoryOrganisationControlPlane` or any other concrete implementation. A future `PaperclipOrganisationControlPlane` would implement the same ports. The Assistant would continue to delegate through the same interfaces, unaware of the underlying implementation.

Similarly, the event boundary is defined through protocols (`OrganisationalEventEmitterPort`, `OrganisationalSignalEmitterPort`). Any implementation — in-memory, message bus, webhook, queue — can be plugged in without changing the Organisation layer or the Assistant.

## Files Changed

| File | Change |
|------|--------|
| `packages/contracts/organisational_events.py` | **New** — Event/signal contracts, ports, and models |
| `packages/contracts/organisational_context.py` | Added `organisation_id` to `OrganisationalContext` |
| `packages/contracts/work_management.py` | Added `organisation_id` to `WorkCreateRequest` |
| `packages/organisation/src/organisation_control_plane.py` | Added event/signal emission, `on_event`, `on_signal`, `detect_capacity_pressure`, `_emit_work_event` |
| `packages/organisation/src/role.py` | Added `organisation_id` to `Work` and `Assignment` |
| `packages/organisation/src/adapters/work_management_adapter.py` | Passes `organisation_id` through to `Work` model |
| `packages/organisation/src/worker.py` | No changes (worker remains execution-only) |
| `packages/ai/src/chat.py` | Passes `organisation_id="default"` in work creation |
| `packages/organisation/tests/test_events.py` | **New** — 19 tests covering event contracts, emission, and capacity detection |

## Test Results

```
packages/organisation/tests/                      66 passed (47 existing + 19 new)
packages/ai/tests/                                68 passed
packages/workflow_runner/tests/test_capability_execute.py  34 passed
packages/workflow_runner/tests/test_authoring.py           6 passed
-------------------------------------------------
Total                                            174 passed
```

### New tests added

| Test | Purpose |
|------|---------|
| `test_default_organisation_id` | Verifies default tenant context |
| `test_custom_organisation_id` | Verifies custom tenant context |
| `test_carry_actor_and_role` | Verifies context propagation |
| `test_created_event_defaults` | Verifies work.created event contract |
| `test_assigned_event_with_assignee` | Verifies work.assigned event contract |
| `test_completed_event_with_outcome` | Verifies work.completed event contract |
| `test_failed_event` | Verifies work.failed event contract |
| `test_registered_event` | Verifies capability.registered event contract |
| `test_development_completed_event` | Verifies capability.development.completed event contract |
| `test_heartbeat_event` | Verifies agent.heartbeat event contract |
| `test_overloaded_event` | Verifies agent.overloaded event contract |
| `test_pressure_detected` | Verifies capacity.pressure.detected signal contract |
| `test_no_pressure_when_below_capacity` | Verifies signal is not emitted when healthy |
| `test_bottleneck_detected` | Verifies capability.bottleneck.detected signal contract |
| `test_sla_risk_detected` | Verifies work.sla_risk.detected signal contract |
| `test_ocp_emits_work_assigned_event` | Verifies OCP emits event on work assignment |
| `test_ocp_emits_capability_registered_event` | Verifies OCP emits event on capability registration |
| `test_ocp_detects_capacity_pressure` | Verifies OCP detects capacity pressure |
| `test_ocp_returns_none_when_no_pressure` | Verifies OCP returns None when no pressure |

## What Remains Unimplemented

1. **Paperclip integration** — deferred, not available locally
2. **Database persistence** — subordinate to architecture
3. **Event bus** — boundary defined, implementation deferred
4. **Real team of people/agents** — only a single worker agent exists
5. **Sophisticated ETA prediction** — ETA is heuristic
6. **Autonomous worker loop** — worker runs only when triggered via API
7. **Capacity decision system** — signals are detected, decisions are not automated
8. **Multi-tenant data isolation** — organisation_id is carried but not enforced
9. **Horizontal scaling** — architecture supports it, implementation not started
10. **Message queue / webhook integration** — event boundary is defined, transport is not

## The Smallest Next Increment

**Persist organisational state and establish event streaming.**

Currently the organisation is in-memory. The next step is to:
1. Determine what needs to persist vs. what belongs in the event stream
2. Implement a minimal event stream that can be consumed by monitoring, capacity management, and future automation
3. This enables reactive worker triggering, audit trails, and observability

After establishing the stream, the natural next steps are:
1. Introduce a Paperclip-backed `OrganisationControlPlane` adapter when Paperclip becomes available
2. Add a second worker/agent to prove multi-agent team behaviour
3. Implement capacity decision logic (reassignment, capability development, agent creation)

## Most Important Question

**Can the system now evolve from single user to multi-tenant platform without rewriting the Assistant, Organisation abstraction, capability model, or communication boundary?**

**Yes.**

The event/signal boundary is:
- Defined through protocols (not concrete implementations)
- Tenant-context-aware (organisation_id on every event)
- Operationally agnostic (does not depend on Paperclip or any specific system)
- Non-orchestrating (communication only, no decision-making)
- Horizontally scalable by design (no singletons, pluggable transports)

The Organisation abstraction remains the architectural owner of organisational truth. The Assistant remains unaware of operational implementation details. Paperclip (or any future system) can participate by emitting events through adapters, without becoming the architectural owner of communication, observability, capacity management, or multi-tenant scaling.
