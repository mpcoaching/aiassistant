# Increment 53 — Investigation: Next Justified Vertical Slice

## Status: Investigation complete — next vertical slice identified

## Current-State Trace (End-to-End)

### Entry points

**Production entry: `packages/workflow_runner/api.py`** (module-level, lines 662-680):
- Creates `_org_plane` via `create_organisation_control_plane()`
- Creates `_agent_store` via `_create_agent_store()` (bootstraps Assistant Agent with `actor_id="assistant"`)
- Creates `_work_management` as `WorkManagementAdapter(_org_plane, agent_store=_agent_store)`
- Creates `_assistant` via `create_assistant(work_management=_work_management, ...)`

**Key asymmetry:** `_agent_store` exists at the module level but is NOT passed to `AssistantChatService`. The service receives only `work_management` (a `WorkManagementPort`).

### Work creation paths

`packages/ai/src/chat.py` has **4 `WorkCreateRequest(...)` call sites**, all in `AssistantChatService`:

1. **`_handle_new_capability_required_response`** (line 1665) — creates capability-development Work
2. **`_handle_human_team_investigation_response`** (line 1717) — creates investigation Work
3. **`_handle_capability_gap`** (line 1860) — creates capability-development Work (alternative path)
4. **`_delegate_work_response`** (line 2086) — creates project Work for CAPABILITY_PATH, planning, and analysis-confirmation flows

**None of these 4 call sites pass `assignee_actor_id`.** Every Work item is created with `accountable_role_id="default"` and assigned to the Role "default" via the fallback path in `WorkManagementAdapter.create_work()`.

### Work execution path

1. `AssistantChatService` creates Work → assigned to "default" Role
2. `Operations` subscribes to `WorkEventType.READY` → picks up work
3. `PaperclipBackend` checks `work.assignee_agent_id` (line 133) — **is None** for all assistant-created Work
4. Falls through to `WorkerBackend` (line 93: `not work.assignee_agent_id` → True)
5. `Worker.execute()` assigns work to `DEFAULT_AGENT_ID = "worker-agent"` (line 69) if `assignee_agent_id is None`

### What this means

The Assistant Agent ("assistant"), which is bootstrapped in `_create_agent_store()`, is **never assigned any Work**. All Work created through the chat service flows to the in-process `Worker` (with a synthetic `worker-agent`), bypassing Paperclip execution entirely. The `_agent_store` wired in Increment 52 sits unused by the assistant — it is only used by tests that explicitly pass `agent_store` to `WorkManagementAdapter`.

### What exists (domain primitives)

- `Work.assignee_actor_id`, `Work.assignee_agent_id`, `Work.assignee_person_id` — all on the Work model (`role.py:113-115`)
- `Agent` model with `id`, `name`, `marker`, `status`, `fulfilled_role_ids` (`agent.py`)
- `Actor` model with `actor_type` (PERSON/AGENT), `reference_id` (`actor.py`)
- `InMemoryAgentStore.get_actor()`, `get_agent()`, `list_agents()`, `actor_fulfills_role()` (`agent_store.py`)
- `WorkCreateRequest.assignee_actor_id` — added in Increment 52 (`contracts/work_management.py:16`)
- `WorkManagementAdapter(agent_store=...)` — accepts agent_store, resolves Actor, calls `OCP.assign_work(work, actor)` (`work_management_adapter.py:21-70`)
- `OCP.assign_work(work, actor)` — sets `work.assignee_actor_id`, `work.assignee_agent_id`, `work.assignee_person_id` based on actor_type (`organisation_control_plane.py:291-329`)
- `_create_agent_store()` — bootstraps Assistant Agent with `actor_id="assistant"` (`composition.py:45-54`)
- Operations backend selection: `PaperclipBackend.can_handle` requires `work.assignee_agent_id` (`operations.py:133`); `WorkerBackend.can_handle` requires `not work.assignee_agent_id` (`operations.py:93`)

## Candidates Considered

### Candidate 1: Wire Assistant Actor to the Chat Service for Work Assignment

**Concrete behaviour:** When `AssistantChatService` creates Work, pass the Assistant Agent's ID as `assignee_actor_id`, so Work is explicitly assigned to the Assistant Actor rather than the "default" Role.

- **Existing caller:** YES — all 4 `WorkCreateRequest(...)` call sites in `chat.py`
- **Required domain primitives:** ALL PRESENT — `Agent` exists, `AgentStore.get_actor()` exists, `assignee_actor_id` field exists, `OCP.assign_work(work, actor)` exists
- **Missing boundary:** The Assistant Actor identity is not propagated from composition to the chat service. `AssistantChatService.__init__` has no `agent_id` or `agent_store` parameter. The conversation root (`create_assistant` / `create_application`) does not pass the agent ID through.
- **Small vertical slice:** YES — add an `agent_id` parameter to `AssistantChatService.__init__`, pass it to `WorkCreateRequest` in all 4 call sites. Wire it through `create_assistant()` and `create_application()`.
- **Unlocks next behaviour:** Work delegated through the chat service would be assigned to the Assistant Agent, enabling Paperclip execution backends to pick it up (currently `PaperclipBackend.can_handle` returns False because `assignee_agent_id` is None).

**Classification: JUSTIFIED**

### Candidate 2: Required-Proficiency Threshold on Role

- **Existing caller:** NO — `is_authorised` explicitly ignores proficiency; no production caller differentiates "insufficient proficiency" from "available"
- **Classification: NOT JUSTIFIED** — no production caller requires it (carried forward from Increment 51 review)

### Candidate 3: Consolidated Capacity-Analysis Service

- **Existing caller:** NO — `chat.py` uses only `query_capability` (availability flag); no production caller needs a consolidated capacity result
- **Classification: NOT JUSTIFIED** — no production caller requires it (carried forward from Increment 51 review)

### Candidate 4: Response-Selection Decision Function

- **Existing caller:** NO — each `ExecutionPath` branch maps to a single unambiguous action in `chat.py`
- **Classification: NOT JUSTIFIED** — no production caller requires it (carried forward from Increment 51 review)

### Candidate 5: Autonomous Agent Provisioning

- **Existing caller:** NO — `register_agent`/`register_person` are only called in tests and bootstraps
- **Classification: NOT JUSTIFIED** — no production caller requests Actor provisioning as a response to capacity analysis

## Chosen Next Vertical Slice

**Subject: Wire the Assistant Agent identity into Work creation so delegated Work is explicitly assigned to the Assistant Actor.**

### Rationale

Increment 52 established the mechanism: `WorkCreateRequest.assignee_actor_id` + `WorkManagementAdapter(agent_store=...)` + `OCP.assign_work(work, actor)`. However, no production caller uses it. The `_create_agent_store()` helper bootstraps the Assistant Agent in production, and the `WorkManagementAdapter` receives the agent_store — but `AssistantChatService` never passes `assignee_actor_id` when creating Work.

This is not speculation — it is the direct next step that makes Increment 52's infrastructure actually used in the production path:

1. The Assistant Agent exists (bootstrapped in `_create_agent_store()`)
2. The agent_store is wired into `WorkManagementAdapter` (Increment 52)
3. The `assignee_actor_id` field exists on `WorkCreateRequest` (Increment 52)
4. `Operations` already routes work with `assignee_agent_id` to `PaperclipBackend` (operations.py:131-133)
5. But all Work from `AssistantChatService` has `assignee_agent_id=None`, so it falls through to `WorkerBackend`

Wiring the Assistant Actor ID into Work creation changes the execution path from in-process Worker to Paperclip-managed execution — a real, observable behavioural change with an actual production caller.

### Exact production files that would need changing

1. **`packages/ai/src/chat.py`** — `AssistantChatService.__init__`: add `agent_id: str | None = None` parameter; pass `assignee_actor_id=self._agent_id` in all 4 `WorkCreateRequest(...)` call sites (lines 1665, 1717, 1860, 2086)
2. **`packages/workflow_runner/src/composition.py`** — `create_assistant()`: add `agent_id: str | None = None` parameter; pass to `AssistantChatService()`; in `create_application()`: pass `agent_id="assistant"` from `_create_agent_store()` output
3. **`packages/workflow_runner/api.py`** — line 656 and line 766: pass `agent_id="assistant"` to both `create_assistant()` calls

### Test plan

- Verify `assignee_actor_id` is set on all Work created through `AssistantChatService`
- Verify Work is assigned to Agent-backed Actor (not Role)
- Verify `_delegate_work_response` sets `assignee_actor_id`
- Verify backward compatibility: `agent_id=None` → no `assignee_actor_id` passed (existing Role-based path)
- Verify Operations routes assistant-assigned work to PaperclipBackend when available
- Regression: all existing platform integration tests still pass
- Regression: all 19 Increment 52 tests still pass

## Explicit Non-Goals

- Do NOT add `required_proficiency` fields to Role or CapabilityAssignment
- Do NOT create a `Capacity` entity
- Do NOT add a `Decision` entity or response-selection function
- Do NOT add a `CapabilityGraph`/relationship model
- Do NOT implement autonomous agent provisioning/staffing
- Do NOT add Supplier/Vendor concepts
- Do NOT add new Team/OCP concepts
- Do NOT modify Paperclip integration
- Do NOT change ExecutionPath branches or select_execution_path logic

## Architectural Rationale

The boundary is small and well-defined:

- **What exists:** The full chain from Actor identity (AgentStore) through Work creation (WorkManagementAdapter) to Work assignment (OCP.assign_work) is already implemented and tested (Increment 52). The only missing piece is propagating the Assistant's agent_id from the composition root to the chat service so it can be used in WorkCreateRequest.
- **What is missing:** A single parameter (`agent_id`) threaded through 3 files, used in 4 WorkCreateRequest call sites.
- **Why it is the next slice:** It transforms Increment 52 from infrastructure-with-no-caller into infrastructure-with-production-caller. Work delegated by the Assistant will flow through the PaperclipBackend execution path rather than being intercepted by the in-process Worker.
- **Why other candidates are still deferred:** Every other candidate (proficiency thresholds, capacity analysis, response selection) requires inventing a new decision-maker or analysis service with no existing caller. This candidate has 4 existing call sites that would immediately use the new parameter.

## Confirmation

No production code changes made in this investigation. No commit made. The only artifact created is `packages/organisation/increment53_report.md`.
