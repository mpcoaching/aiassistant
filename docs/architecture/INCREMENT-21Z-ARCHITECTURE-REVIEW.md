# Increment 21Z — Validate Organisation/Operations Boundary and Establish the Next Architectural Seam

## 1. Architecture Assessment

### Current Architecture

```
Chat/API/UI
    ↓
API layer (FastAPI transport)
    ↓
Organisation composition boundary (create_organisation_control_plane)
    ↓
OrganisationControlPlane interface
    ↓
InMemoryOrganisationControlPlane  OR  PaperclipOrganisationControlPlane
    ↓
Operational backend (Paperclip, Workflow Engine, etc.)
```

### Assessment Against Principles

| Principle | Status | Evidence |
|-----------|--------|----------|
| Chat/API/UI is external interface | **PARTIAL** | API contains organisational decisions (direct `_org_plane` access, Worker instantiation, capability approval logic) |
| Assistant is inside Organisation | **PARTIAL** | Depends on ports only (good), but embeds organisational policy (thresholds, strategy mapping, work creation defaults) |
| Organisation owns organisational truth | **PASS** | `OrganisationControlPlane` ABC defines the boundary; domain models in `role.py` |
| Paperclip is operational backend | **PASS** | Adapter translates; Paperclip concepts do not leak upward |
| Workflows are operational infrastructure | **PASS** | `PathwayRuntime` abstraction exists; `LangGraphRuntime` is one implementation |
| AI should not execute BAU work | **PARTIAL** | Compiled capability execution exists, but not the default path for workflow steps |
| System should support "AI designs once, system runs many" | **PASS** | `ExecutionMode.COMPILED`, `CompiledRef`, `PathwayRuntime` all support this |
| Operational backend should be replaceable | **PASS** | Switching requires only composition root change; no Assistant changes needed |

## 2. Current Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   Chat / API / UI (transport layer)                                    │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ FastAPI endpoints                                            │   │
│   │  - /assistant/chat                                            │   │
│   │  - /capabilities                                              │   │
│   │  - /work, /work/{id}/process, /worker/run                    │   │
│   │  - (also contains: capability approval, Worker instantiation) │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ create_organisation_control_plane()                          │   │
│   │  - Reads PAPERCLIP_URL env var                               │   │
│   │  - Returns PaperclipOrganisationControlPlane OR              │   │
│   │    InMemoryOrganisationControlPlane                          │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ OrganisationControlPlane (ABC)                               │   │
│   │  - get_role, list_roles                                      │   │
│   │  - get_work, list_work, assign_work, mark_work_ready         │   │
│   │  - delegate_authority                                        │   │
│   │  - get_organisational_context                                 │   │
│   │  - register_capability, query_capability (People/Capability) │   │
│   │  - emit_event, emit_signal, detect_capacity_pressure         │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ Adapter layer                                                 │   │
│   │  - WorkManagementAdapter                                      │   │
│   │  - OrganisationalContextAdapter                               │   │
│   │  - EnterpriseCapabilityQueryAdapter                           │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ Operational backends                                          │   │
│   │  ┌─────────────────┐  ┌──────────────────────────────────┐  │   │
│   │  │ Paperclip       │  │ InMemoryOrganisationControlPlane │  │   │
│   │  │ - Company       │  │ - Python dicts                   │  │   │
│   │  │ - Agent         │  │ - No external dependencies       │  │   │
│   │  │ - Issue         │  │ - For tests/dev                  │  │   │
│   │  │ - HeartbeatRun  │  └──────────────────────────────────┘  │   │
│   │  └─────────────────┘                                          │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. Proposed Future Architecture (Compiled Workflows)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   Chat / API / UI (thin transport)                                     │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ create_organisation_control_plane()                          │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ OrganisationControlPlane (ABC)                               │   │
│   │  - get_role, list_roles                                      │   │
│   │  - get_work, list_work, assign_work, mark_work_ready         │   │
│   │  - delegate_authority                                        │   │
│   │  - get_organisational_context                                 │   │
│   │  - emit_event, emit_signal                                    │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ Operational Control Plane (NEW)                              │   │
│   │  - Selects execution backend                                 │   │
│   │  - Routes work to appropriate executor                       │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌───────────────────────────────────────────────────────────────┐   │
│   │ Execution backends                                            │   │
│   │  ┌─────────────────┐  ┌──────────────────────────────────┐  │   │
│   │  │ Paperclip       │  │ CompiledWorkflowEngine            │  │   │
│   │  │ - Agents        │  │ (PathwayRuntime implementation)   │  │   │
│   │  │ - HeartbeatRun  │  │ - Deterministic step execution   │  │   │
│   │  │ - Process exec  │  │ - Sub-workflow support            │  │   │
│   │  └─────────────────┘  │ - Event/schedule triggers         │  │   │
│   │                       └──────────────────────────────────┘  │   │
│   └───────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key insight:** The current `PathwayRuntime` abstraction already supports this. A `CompiledWorkflowEngine` would be a third `PathwayRuntime` implementation alongside `LangGraphRuntime`. No new orchestration layer is needed.

## 4. Confirmed Architectural Strengths

1. **OrganisationControlPlane is a genuine boundary.** It is defined independently of any operational backend and has a narrow, mechanism-only interface.

2. **Paperclip adapter correctly translates.** Domain concepts flow upward; Paperclip concepts do not leak into the Organisation or Assistant layers.

3. **Backend interchangeability is proven.** The smoke test and composition root demonstrate that `InMemoryOrganisationControlPlane` and `PaperclipOrganisationControlPlane` are interchangeable through the interface.

4. **Assistant depends on ports only.** No direct imports of concrete implementations from other planes.

5. **PathwayRuntime is the right seam for compiled workflows.** It already supports multiple substrates (workflow-runner, langgraph) and is explicitly designed for extension.

6. **Compiled capability execution already works.** `ExecutionMode.COMPILED` + `CompiledRef` + `execute_capability` is end-to-end functional.

7. **Composition root correctly isolates deployment configuration.** `PAPERCLIP_URL` selection happens in `organisation/src/composition.py`, not in the API or Assistant.

## 5. Concrete Architectural Weaknesses

### HIGH severity

| # | Weakness | Location | Evidence |
|---|----------|----------|----------|
| 1 | **API directly manipulates Organisation state** | `api.py:1119-1244` | API calls `_org_plane.query_capability()`, `_org_plane.list_roles()`, `_org_plane.list_work()`, `_org_plane.get_work()` directly; instantiates `Worker` |
| 2 | **Worker accesses private implementation attribute** | `worker.py:84,96,106` | `org_plane._work[work.id] = work` bypasses interface; works only for in-memory impl |
| 3 | **API contains governance logic** | `api.py:790-874` | `_approve_capability_request()` implements CapabilityRequest approval — People/Capability plane concern |

### MEDIUM severity

| # | Weakness | Location | Evidence |
|---|----------|----------|----------|
| 4 | **OrganisationControlPlane leaks other-plane methods** | `organisation_control_plane.py:116-137` | `register_capability()`, `query_capability()`, `detect_capacity_pressure()` belong to People/Capability plane (ADR-020) |
| 5 | **Paperclip adapter has non-ABC methods** | `organisation_paperclip.py:456-527` | `create_company()`, `create_agent()`, `trigger_execution()`, `wait_for_execution()`, `get_heartbeat_run()` are Paperclip-specific and not on the ABC |
| 6 | **Assistant embeds organisational policy** | `chat.py:43,262-278,428-434` | Hardcoded ETA threshold (60s), strategy mapping, work creation defaults |
| 7 | **Unscoped Paperclip endpoints in adapter** | `organisation_paperclip.py:134,239,502` | `GET /api/agents/{id}`, `GET /api/issues/{id}`, `GET /api/heartbeat-runs/{id}` have no company scope |
| 8 | **No execution triggering in Organisation abstraction** | `organisation_control_plane.py` | `trigger_execution` exists only on Paperclip adapter, not on ABC or `WorkManagementPort` |
| 9 | **Event system is handler-based, not persistent** | `organisation_paperclip.py:512-528` | `on_event(handler)` accepts single callback; no event stream, replay, or bus integration |

### LOW severity

| # | Weakness | Location | Evidence |
|---|----------|----------|----------|
| 10 | **Terminology inconsistency** | Multiple files | `EnterpriseCapabilityQueryPort` queries Organisation; "enterprise" in chat.py messages and docs |
| 11 | **Integration tests leak state** | `test_smoke.py:94-96`, `test_integration.py:42-50` | No cleanup of created Paperclip companies/agents/issues |
| 12 | **PatternRuntime is orphaned** | `composition.py:116-120` | Constructed but never injected into `PatternExecutionAdapter` |

## 6. Assumptions That Remain Unverified

1. **Multi-tenancy model.** The current architecture assumes "one process = one tenant." Whether this is acceptable depends on deployment topology, which is not yet defined.

2. **Event delivery guarantees.** The handler-based event system works for synchronous observation, but it is unverified whether it can support reliable async workflows triggered by Paperclip completion.

3. **Worker/Paperclip compatibility.** The `Worker` class directly manipulates `org_plane._work`, which is an in-memory implementation detail. It has not been verified against `PaperclipOrganisationControlPlane`.

4. **Retry/reassignment semantics.** There is no retry logic, no reassignment flow, and no `ESCALATED` status handling. This is a lifecycle gap.

5. **Compiled workflow substrate selection.** The `PathwayRuntime` abstraction supports multiple substrates, but substrate selection by `pathway_preference` is not implemented.

## 7. Smallest Recommended Next Increment

**Title:** Move execution triggering into the Organisation boundary and make the API a pure transport layer.

**Rationale:** The most concrete architectural gap is that execution triggering (`trigger_execution`) lives on the Paperclip adapter, not on the `OrganisationControlPlane` interface. This means:
- The Organisation cannot trigger execution through its own interface
- The API must know about operational execution to trigger it
- The Worker bypasses the interface by accessing private state

**Minimal changes:**

1. **Add `trigger_execution(work_id, assignee_id)` to `OrganisationControlPlane` ABC** with a default implementation that raises `NotImplementedError`. This establishes the contract without forcing immediate implementation in all backends.

2. **Add `execute_work(work_id)` to `OrganisationControlPlane` ABC** — a single method that encapsulates "trigger execution and observe result." This is the minimal primitive for the Organisation to delegate work to an operational backend.

3. **Make the API a pure transport layer:** Remove direct `_org_plane` access from API endpoints. Instead, route through the Assistant or a thin organisational service. This is the most impactful architectural cleanup.

4. **Fix Worker to use public interface:** Replace `org_plane._work[work.id] = work` with `org_plane.get_work(work.id)` followed by proper update methods, or add an `update_work()` method to the ABC.

5. **Add architectural tests proving:** API doesn't import Paperclip, Assistant doesn't import Paperclip, OrganisationControlPlane has no execution-shaped methods.

**What this does NOT do:**
- Does not add a workflow engine
- Does not add an event bus
- Does not add persistence
- Does not change the Assistant
- Does not redesign the capability model

**What it enables:**
- Organisation can trigger execution through its own interface
- API becomes a thin transport layer
- Operational backends become truly interchangeable
- Future compiled workflow engine can be added as another `OrganisationControlPlane` implementation or as a new execution backend selected by the Organisation

## 8. Test Results

### Before this increment
- Unit tests: 201 passed
- Paperclip smoke test: 1 passed
- Paperclip integration tests: 6 passed
- Total: 208 passed

### After this increment
- Unit tests: **205 passed** (+4 new architectural boundary tests)
- Paperclip smoke test: 1 passed
- Paperclip integration tests: 6 passed
- Total: **212 passed**

### New tests added
| Test | Purpose |
|------|---------|
| `test_api_does_not_import_paperclip` | Verifies API layer has no Paperclip imports |
| `test_assistant_does_not_import_operational_backends` | Verifies Assistant has no operational backend imports |
| `test_organisation_control_plane_has_no_execution_methods` | Verifies ABC is mechanism-only |
| `test_composition_boundary_exists` | Verifies composition root creates valid OrganisationControlPlane |

## 9. Component Responsibility Map (Current)

| Step | Component | Responsibility |
|------|-----------|----------------|
| 1. HTTP request | FastAPI API layer | Transport, request validation |
| 2. Backend selection | `organisation/src/composition.py` | Deployment config → implementation |
| 3. Chat processing | `AssistantChatService` | Intent recognition, capability matching, delegation |
| 4. Work creation | `WorkManagementAdapter` → `OrganisationControlPlane` | Domain work creation |
| 5. Work assignment | `OrganisationControlPlane.assign_work()` | Domain assignment |
| 6. Execution trigger | `PaperclipOrganisationControlPlane.trigger_execution()` | **Currently in adapter, should be in ABC** |
| 7. Agent execution | Paperclip process adapter | Operational execution |
| 8. Result observation | `PaperclipOrganisationControlPlane.wait_for_execution()` | Polls Paperclip, translates result |
| 9. Result propagation | `Work.outcome`, `WorkEvent` | Domain state update |
| 10. Response | API layer | Returns ChatResponse to caller |

## 10. Files Changed This Increment

| File | Change |
|------|--------|
| `packages/organisation/src/composition.py` | **NEW** — bootstrap boundary for OrganisationControlPlane selection |
| `packages/workflow_runner/src/composition.py` | Uses `create_organisation_control_plane()` |
| `packages/workflow_runner/api.py` | Removed inline Paperclip selection; renamed `_enterprise_capability_query` → `_capability_query` |
| `packages/organisation/tests/test_architectural_boundary.py` | **NEW** — 4 architectural boundary tests |
| `packages/organisation/tests/test_organisation_control_plane.py` | Added backend interchangeability test |
| `packages/ai/tests/test_assistant.py` | Renamed test to use `organisation` terminology |
