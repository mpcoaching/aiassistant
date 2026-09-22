# Next Vertical Slice Review

## A. Current Usable Organisational Behaviours

1. **Intent → Solution Selection**: The assistant chat service (`packages/ai/src/chat.py:819`) receives natural-language requests, recognises them into a `ProblemFrame` (via `intent.recognise`), and routes them through `OrganisationControlPlane.select_execution_path()`.

2. **Four Execution Paths** (exactly four, no expansion):
   - `EXISTING_WORKFLOW` — a matching workflow definition exists and is executed
   - `CAPABILITY_PATH` — a registered capability is available and executed
   - `NEW_CAPABILITY_REQUIRED` — a capability gap is identified, Work is created
   - `HUMAN_TEAM_INVESTIGATION` — capability exists but is unavailable (overloaded)

3. **Work Creation via Chat**: If no capability/workflow matches, the assistant delegates to the Organisation via `WorkManagementPort.create_work()` (`chat.py:2070`), creating a Work item assigned to the "default" role and immediately marked ready.

4. **Operational Execution**: `Operations` (`packages/workflow_runner/src/operations.py:136`) subscribes to `WorkEventType.READY`, selects an execution backend (`WorkerBackend` or `PaperclipBackend`), executes the work, and reports results back to the OCP via `complete_work()` / `fail_work()`.

5. **Worker Execution**: `Worker` (`packages/workflow_runner/src/worker.py`) picks up work, classifies intent (planning, summarisation, analysis, etc.), generates structured output, and writes artifacts to `worker_outputs/`.

6. **Role/Authority Management**: `InMemoryOrganisationControlPlane` supports role registration, authority delegation, and work assignment via the existing Role/Authority/Delegation/Work/Assignment model.

7. **Capability Development**: When `NEW_CAPABILITY_REQUIRED` fires, the Work is typed as `capability_development`, executed by the Worker (which creates a draft `Capability`), assessed by `outcome.assess_capability_development()`, and promoted to ACTIVE in the CapabilityRegistry.

## B. Existing Application Entry Points

1. **POST `/assistant/chat`** (`api.py:823`) — Natural language chat; routes through `AssistantChatService.chat()`.

2. **POST `/assistant/chat/{session_id}/resume`** (`api.py:848`) — Resume a paused session with human input.

3. **POST `/assistant/paperclip-chat`** (`api.py:865`) — Paperclip-backed chat (external agent).

4. **POST `/workflows/{name}/run`** (`api.py:309`) — Direct workflow execution by name.

5. **POST `/worker/run`** (`api.py` docstring line 22, declared but not implemented) — Worker picks up assigned work.

6. **GET `/roles`**, **GET `/work`**, **GET `/work/{work_id}`** (`api.py:1270-1310`) — Organisation inspection endpoints.

7. **POST `/assistant/capability-request/{request_id}/approve`** (`api.py:939`) — Approve a capability request, creating a draft `EnterpriseConcept`.

8. **POST `/assistant/capability/{capability_id}/execute`** (`api.py:994`) — Execute a specific capability on demand.

9. **POST `/sessions`, POST `/tasks`** — Session and task management endpoints.

10. **MCP tools** (`mcp_server.py`) — `list_skills`, `run_workflow`, `design_service`, `create_service`, `compile_capability`, `list_services`.

## C. Concrete Missing Behaviours Identified

### Candidate 1: Capability Gap → Development Work (already exists, but limited)
- **What user wants**: "We need to be able to analyse customer feedback."
- **Current flow**: `select_execution_path` → `NEW_CAPABILITY_REQUIRED` → `_handle_new_capability_required_response` → `_delegate_work_response` → creates Work.
- **Gap**: The Work is created with `accountable_role_id="default"` and assigned to the "default" role — not to any actual People/Capability function actor. The Worker picks it up and develops a capability, but there's no mechanism to route it to a designated capability-development agent or role.
- **Classification**: Missing orchestration.

### Candidate 2: Chief of Staff identifies a capability gap and assigns investigation Work
- **What user wants**: "We're missing a capability for X. Assign someone to investigate."
- **Current flow**: Only happens implicitly via chat → NEW_CAPABILITY_REQUIRED → generic Work creation.
- **Gap**: No way for a user (acting as Chief of Staff or similar) to explicitly identify a capability gap, create an investigation Work item, and assign it to a specific Actor/Role — e.g., the People/Capability function agent.
- **Classification**: Requires a concrete caller.

### Candidate 3: Explicit Work assignment to a specific Actor
- **What user wants**: "Assign this work to agent X" or "Assign this work to the People/Capability function."
- **Current flow**: `WorkManagementAdapter.create_work` auto-assigns to the role looked up by `accountable_role_id` (defaulting to "default" role). No API endpoint to assign work to a specific Actor.
- **Gap**: No way to route work to a specific person or agent. The `agent_store` exists and can create/register agents, but nothing exposes this through the Work assignment path.
- **Classification**: Missing orchestration / new API endpoint.

### Candidate 4: Agent provisioning for an existing capability
- **What user wants**: "We need a dedicated agent for capability Y."
- **Current flow**: `agent_store.bootstrap_assistant()` creates an Agent with capability assignments, but this is only called once during composition for the default "assistant" agent. No runtime API to provision additional agents.
- **Gap**: No caller invokes this for runtime agent provisioning.
- **Classification**: Requires a concrete caller.

### Candidate 5: Work outcome causes capability reassessment and next-step determination
- **What user wants**: "A capability was developed and passed assessment. What should we do next?"
- **Current flow**: After capability development, `Operations._assess_capability_development` promotes the capability and records proficiency. But no organisational Work is created or assigned to the People/Capability function to assess broader capability/capacity implications.
- **Gap**: The assessment result sits local to Operations; nothing triggers follow-up organisational reasoning.
- **Classification**: Missing orchestration.

## D. Candidate Vertical Slices

| # | Candidate | Classification |
|---|-----------|----------------|
| 1 | Capability gap → development Work with explicit role assignment | REQUIRES A CONCRETE CALLER |
| 2 | Chief of Staff identifies gap, assigns investigation Work to People/Capability agent | REQUIRES A CONCRETE CALLER |
| 3 | Explicit Work assignment to a specific Actor via API | ACTIONABLE NOW |
| 4 | Runtime agent provisioning for an existing capability | REQUIRES A CONCRETE CALLER |
| 5 | Work outcome triggers capability reassessment and next-step Work | REQUIRES A CONCRETE CALLER |

## E. Existing Primitives Each Candidate Can Reuse

All candidates can leverage:

- **Work** (`role.py:96`) — already has `assignee_actor_id`, `assignee_agent_id`, `assignee_person_id`, `accountable_role_id`, `required_capability_ids`, `develops_capability_id`
- **Agent/Actor** (`agent.py`, `actor.py`) — Person and Agent models, Actor unifies them
- **InMemoryAgentStore** (`agent_store.py`) — `register_agent`, `register_person`, `get_actor`, `assign_capability`
- **OrganisationControlPlane.assign_work()** (`organisation_control_plane.py:291`) — accepts Actor, Role, Person, or Agent
- **WorkManagementAdapter** (`work_management_adapter.py`) — `create_work` → `assign_work` → returns WorkReference
- **CapabilityAssignment** (`capability_assignment.py`) — links Actor ↔ Capability
- **CapabilityProficiency** (`capability_proficiency.py`) — records actual proficiency
- **CapabilityRegistry** — manages capability lifecycle
- **Operations** (`operations.py`) — observes READY work and executes it
- **WorkEventType / WorkEvent** — event emission for work lifecycle
- **Authority / Delegation** — for authority-gated organisational changes
- **CapabilityOutcomeAssessorAdapter** — assesses capability development outcomes

## F. Exact Point Where the Current System Stops

Taking **Candidate 3** (Explicit Work assignment to a specific Actor) as the strongest candidate:

```
User (Chief of Staff)
  ↓ HTTP POST /work or POST /assistant/chat with assignment intent
  ↓ AssistantChatService.chat() → ProblemFrame
  ↓ SolutionSelectionAdapter.select_execution_path()
  ↓ If NEW_CAPABILITY_REQUIRED or generic delegation
  ↓ _delegate_work_response() → WorkManagementPort.create_work()
  ↓ WorkManagementAdapter.create_work()
       WorkCreateRequest has NO assignee_actor_id / assignee_agent_id field
       ↓
       create_work() auto-assigns to Role (accountable_role_id or "default")
       ↓
       WorkManagementAdapter has NO method to assign work to a specific Actor
       ↓
       NO WAY to route specific work to a specific Agent or Person
  ↓ System stops: Work is created but not assigned to the right actor
  ↓ User cannot say "this work should go to agent-X" or "to the People/Capability function agent"
```

**The exact stop point**: `WorkCreateRequest` (`contracts/work_management.py:5`) has no `assignee_actor_id`/`assignee_agent_id`/`assignee_person_id` fields. `WorkManagementAdapter.create_work()` (`work_management_adapter.py:22`) always assigns to a Role. There is no API endpoint to assign or reassign Work to a specific Actor.

## G. New Boundary Required

**No new domain entity or service is required.** The system already has:
- `Actor` model (unifies Person and Agent)
- `Work` model with `assignee_actor_id` field
- `assign_work()` accepting Actor
- `AgentStore` for agent provisioning

The gap is purely **missing orchestration**: the Work creation path does not expose the ability to assign Work to a specific Actor, and there is no API endpoint for it.

The **only** new boundary needed is a new API endpoint or chat intent handler that:
1. Accepts an actor/agent/person ID in the work creation request
2. Calls `OCP.assign_work(work, actor)` with the correct Actor

No new domain entity. No new port. No new architectural boundary. Just wiring existing primitives through a new entry path.

## H. Smallest End-to-End Vertical Slice

### Scenario: User assigns a capability-gaps analysis Work to the People/Capability function agent

```
User / Executive intent:
  "We need to investigate our capability for customer feedback analysis.
   Assign this to the People/Capability function."

  ↓

Current application entry point:
  POST /assistant/chat (or a new POST /work endpoint)

  ↓

Chat service recognises intent → select_execution_path → NEW_CAPABILITY_REQUIRED

  ↓

WorkManagementAdapter.create_work() creates Work with:
  - title: "Investigate customer feedback analysis capability"
  - develops_capability_id: "cap-customer-feedback-analysis"
  - accountable_role_id: "people-capability-function"
  - assignee_actor_id: <agent ID of the People/Capability function agent>

  ↓

OCP.assign_work(work, actor) → Work is ASSIGNED to the specific Agent

  ↓

Operations picks up READY work → WorkerBackend → Worker.execute()

  ↓

Worker generates capability gap analysis → writes artifact → returns result

  ↓

Operations.complete_work(work_id, result) → records outcome

  ↓

Next organisational state:
  - Work is COMPLETED with capability gap analysis as outcome
  - CapabilityRegistry has capability-development Work linked via develops_capability_id
  - The People/Capability function agent was the actual assignee, not a default role
```

### What needs to exist at the stop point:

1. `WorkCreateRequest` gains optional `assignee_actor_id: str | None` field
2. `WorkManagementAdapter.create_work()` accepts and honours `assignee_actor_id` — looks up the Actor and calls `org_plane.assign_work(work, actor)` instead of falling back to a Role
3. A new API endpoint `POST /work` or chat intent parser that maps "assign to [function/agent]" to the actor ID

All three reuse existing primitives (`Work.assignee_actor_id`, `AgentStore.get_actor`, `OCP.assign_work`).

## I. Explicitly Deferred Increment 51 Items

| Deferred Item | Reason |
|---------------|--------|
| **Required proficiency field on CapabilityAssignment** | No production caller needs proficiency-based capability matching. Current system uses availability (in-progress count), not proficiency thresholds. |
| **Capacity-analysis service (entity)** | Capacity is analysable from existing state (Actors + Assignments + Work). No concrete use case currently requires a dedicated service. `_derive_available_capacity` in test code proves the inputs are combinable. |
| **Response-selection logic (staffing/hiring decisions)** | Not expanded — ExecutionPath remains exactly 4 members. The conceptual response set (train, reassign, provision agent, provision person, workflow, tool) is expressible through existing primitives. |
| **CapabilityGraph / Relationship / Edge** | Adjacency is expressible contextually via tags/metadata. No caller requires graph traversal. |
| **Autonomous hiring/staffing mechanism** | Explicitly unsupported — no Supplier/Vendor model. Staffing requires explicit human authority (Chief of Staff → People/Capability function delegation). |

## J. Recommended Next Vertical Slice

**Recommended Increment: Explicit Actor Assignment for Work**

The organisation can already create Work, assign it to Roles, and execute it. What it **cannot** do is let a user assign a Work item to a **specific Actor** (Person or Agent). This is the smallest gap that materially changes the vertical slice: it moves from "Work goes to a default role" to "Work goes to the right person or agent."

This slice:
1. Extends `WorkCreateRequest` with optional `assignee_actor_id`
2. Updates `WorkManagementAdapter.create_work()` to resolve and assign to the Actor when provided
3. Adds a chat intent pattern or API endpoint that accepts actor assignment (e.g., "Assign this to the People/Capability function" or "Give this to agent-X")

**Production boundaries involved:**
- `packages/contracts/work_management.py` — `WorkCreateRequest` model
- `packages/organisation/src/adapters/work_management_adapter.py` — assignment logic
- `packages/workflow_runner/api.py` — new `/work` POST endpoint (or chat intent handling in `packages/ai/src/chat.py`)

No new entities, no new ports, no new services.

## K. Architectural Invariants to Preserve

- OCP remains mechanism-only (no Person/Agent records, no execution, no orchestration beyond event emission).
- ExecutionPath remains exactly four members. No `STAFF`, `REASSIGN`, `DEVELOP`, `OUTSOURCE`.
- NEW_CAPABILITY_REQUIRED = gap identification, not "develop capability."
- People/Capability is an ordinary organisational function (Role + Actor). No Team entity.
- No Capacity entity. No Supplier/Vendor. No Decision entity.
- CapabilityAssignment links Actor ↔ Capability. CapabilityProficiency records actual proficiency.
- No autonomous hiring/staffing. Authority/Delegation required for organisational change.
- Increment 48 identity chain intact: `ExecutionPathResult.capability_id` → `Work.develops_capability_id` → `Capability.id` → CapabilityRegistry → assessment → ACTIVE.
- `required_capability_ids` ≠ `develops_capability_id`.