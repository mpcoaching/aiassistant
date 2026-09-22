# Increment 39 — Workflow Trigger & Invocation Boundary

Investigate how an established WorkflowDefinition gets invoked in BAU,
where triggers/schedules belong, what the minimum invocation contract is,
and whether the organisation needs an explicit WorkflowInvocation concept.

---

## A. Current Invocation Call Graph

6 distinct invocation paths exist, all converging on
`WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest)`:

```
1. Intent-driven OCP:
   ChatRequest.message → SolutionSelectionPort.select_execution_path(intent)
     → EXISTING_WORKFLOW → _execute_workflow_response
     → WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest)
   (ai/src/chat.py:858-865, 1598-1603)

2. Direct API:
   POST /workflows/{name}/run → resolve_workflow_path → load_workflow
     → create_workflow_state → _execute_and_publish → execute_workflow
   (api.py:309-340)

3. Bus-driven:
   publish_workflow_requested → consume "workflow.executions" queue
     → _handle_bus_workflow_requested → _execute_and_publish → execute_workflow
   (bus.py:250-251, api.py:1343-1358)

4. Scheduled:
   scheduler._fire() → publish WorklowRequested (trigger="scheduled")
     → _handle_bus_workflow_requested → execute_workflow
   (scheduler.py:70-79)

5. MCP:
   mcp_server.run_workflow → execute_workflow_from_file → execute_workflow
   (mcp_server.py)

6. CLI:
   cli.run_workflow → _resolve_workflow_path → execute_workflow_from_file
   (cli.py)
```

All paths use `WorkflowExecutionRequest(workflow_name, initial_context, role_override)`.

---

## B. Existing Invocation Mechanisms

| # | Mechanism | Entry Point | Discovery | OCP Involved |
|---|-----------|------------|-----------|--------------|
| 1 | Intent-driven | chat.py `_execute_workflow_response` | build_workflow_lookup | Yes (select_execution_path) |
| 2 | Direct API | api.py POST /workflows/{name}/run | resolve_workflow_path | No |
| 3 | Bus event | api.py _handle_bus_workflow_requested | resolve_workflow_path | No |
| 4 | Scheduled | scheduler.py _fire → bus | resolve_workflow_path | No |
| 5 | MCP | mcp_server.run_workflow | resolve_workflow_path | No |
| 6 | CLI | cli.run_workflow | resolve_workflow_path | No |

Only mechanism #1 routes through OCP. Mechanisms #2-6 bypass OCP entirely.

---

## C. WorkflowDefinition vs Invocation Semantics

**WorkflowDefinition** (`workflow_runner/models.py`) describes WHAT to execute:
- `name`, `description`, `role`, `steps` — execution pattern metadata
- Static, loaded from YAML, immutable to execution

**WorkflowExecutionRequest** (`contracts/workflow_execution.py`) is the INVOCATION:
- `workflow_name`, `initial_context`, `role_override` — execution request metadata
- Ephemeral, created per-invocation, carries only what's needed to execute

**Semantic distinction**: Definition is the reusable pattern; invocation is a
request to execute it. No field overlap in their core purpose.
WorkflowDefinition has no invocation fields; WorkflowExecutionRequest has no
execution-pattern fields.

---

## D. WorkflowState Semantics

WorkflowState (`workflow_runner/models.py:75-86`) represents execution STATE:
- `workflow_id`, `workflow_name`, `workflow_path`, `status`
- `current_step_index`, `steps`, `step_results`, `context`, `error`

WorkflowState is a **per-execution runtime record**, not an invocation record.
It has no trigger, source, scheduling, or ownership fields. It tracks a single
run of a WorkflowDefinition. Each invocation creates a new WorkflowState.

---

## E. Trigger Semantics

Trigger exists ONLY as infrastructure metadata:
- `scheduler.py:76`: `"trigger": "scheduled"` in bus event payload
- No organisational model (Role, Work, WorkflowDefinition, WorkflowState)
  has any trigger-related field
- The OCP does not consume or reference triggers

**Conclusion**: Trigger is infrastructure metadata, not an organisational concept.

---

## F. Intent-Driven Invocation

```
user intent (ChatRequest.message)
  → SolutionSelectionPort.select_execution_path(intent, context)
  → ExecutionPathResult (EXISTING_WORKFLOW)
  → _execute_workflow_response(path_result, session_id)
  → WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest)
```

This is the ONLY invocation path where OCP is involved. Actor identity
(user_id) is dropped at this boundary (established in Increment 36).

---

## G. Automated BAU Invocation

```
trigger (schedule/bus/MCP/CLI/API)
  → resolve_workflow_path(workflow_name)
  → load_workflow(str(path))
  → execute_workflow / _execute_and_publish
  → WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest)
```

Automated invocation uses direct name resolution (`resolve_workflow_path`),
NOT intent-based discovery (`build_workflow_lookup`). It bypasses OCP entirely.

**Key finding**: Intent-driven and automated are the same invocation mechanism
(`WorkflowExecutionPort.execute_workflow`) with different sources — NOT
distinct organisational boundaries.

---

## H. Trigger Ownership

All trigger types are owned by workflow_runner infrastructure:

| Trigger Type | Owner | Location |
|-------------|-------|----------|
| Manual request | API (transport) | api.py POST /workflows/{name}/run |
| Schedule | Scheduler (APScheduler) | scheduler.py + api.py POST /schedules |
| Bus event | Bus consumer | api.py _handle_bus_workflow_requested |
| Recurring | Scheduler (cron) | scheduler.py _fire |
| Webhook | Not implemented | N/A |
| External notification | Not implemented | N/A |

No organisational concept (Role, Work, WorkflowDefinition, WorkflowState)
owns any trigger type.

---

## I. OCP Responsibility

**Answer: A** — OCP selects a workflow only when given organisational intent.

Evidence:
- `select_execution_path(intent: str, context: dict)` takes only intent and context
- No trigger, schedule, or automated-signal parameter exists
- `_handle_bus_workflow_requested` bypasses OCP entirely
- OCP does not subscribe to or process WorkflowRequested bus events

---

## J. Workflow Discovery Implications

Two discovery mechanisms exist by design:

1. **build_workflow_lookup** (intent → matching workflows): keyword-based
   filesystem search. Used ONLY by intent-driven OCP path.
2. **resolve_workflow_path** (name → file path): direct name matching.
   Used by API, scheduler, bus, MCP, CLI.

A trigger may directly identify a WorkflowDefinition by name (via
resolve_workflow_path) without using intent-based discovery.
Workflow matching is not redesigned — both mechanisms serve different sources
correctly.

---

## K. Duplicate Invocation Implications

No idempotency mechanism exists. Each invocation creates a new WorkflowState
with a new UUID (`api.py:320`). Duplicate execution has no established semantic
and remains an implementation concern. No organisational entity tracks
invocation count or duplicate detection.

---

## L. Invocation Failure Ownership

| Failure Stage | Owner | Consequence |
|--------------|-------|-------------|
| Trigger received, workflow not found | API (transport) | HTTPException 404 |
| Workflow selected, cannot start | Executor | WorkflowState.status = failed |
| Workflow starts and fails | Executor | WorkflowState.status = failed, error recorded |
| Workflow completes with error | Executor | WorkflowExecutionResult.status = failed |

No new error/event abstraction is needed — existing boundaries are sufficient.

---

## M. External-System Implications

Paperclip is a Work execution backend, NOT a workflow triggering mechanism.
`PaperclipBackend.execute` calls `trigger_execution` (heartbeat API), NOT
`execute_workflow` or `execute_workflow_from_file` (operations.py).

External systems (Paperclip, MCP) are implementations/adapters, not
organisational authorities. They do not define invocation concepts.

---

## N. Whether WorkflowInvocation Is a Real Organisational Concept

**No.** No organisational entity requires invocation records. WorkflowState
provides sufficient execution tracking. No entity needs to know when/how/why
a workflow was invoked. The existing `WorkflowExecutionRequest` contract is
adequate for all 6 invocation mechanisms.

---

## O. Minimum Architectural Change, If Any

**None required.** Decision A.

WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest) is the
adequate invocation contract. Triggers remain infrastructure/application
concerns. No organisational concept needs to represent invocation.

---

## P. Architectural Tests Added

21 tests in `packages/organisation/tests/test_increment39_workflow_invocation_boundary.py`:

### A. Current Invocation Call Graph (2 tests)
1. `test_all_invocation_paths_converge_on_workflow_execution_port` — All paths use WorkflowExecutionPort
2. `test_invocation_paths_do_not_require_organisational_concept` — No org concept needed

### B. Existing Invocation Mechanisms (5 tests)
3. `test_api_run_workflow_calls_executor` — Direct API path verified
4. `test_bus_workflow_requested_bypasses_organisation` — Bus path bypasses OCP
5. `test_mcp_server_invokes_workflow_directly` — MCP path verified
6. `test_assistant_workflow_path_uses_workflow_execution_port` — Intent-driven path verified
7. `test_six_invocation_mechanisms_identified` — All 6 enumerated

### C. WorkflowDefinition vs Invocation Semantics (3 tests)
8. `test_workflow_definition_is_not_invocation` — Distinct semantic roles
9. `test_workflow_definition_has_no_invocation_metadata` — No trigger/schedule fields on Definition
10. `test_workflow_execution_request_has_no_execution_pattern` — No steps/role on Request

### D. WorkflowState Semantics (2 tests)
11. `test_workflow_state_is_execution_not_invocation` — State is execution, not invocation
12. `test_workflow_state_has_no_trigger_or_schedule_reference` — No trigger fields on State

### E. Trigger Semantics (3 tests)
13. `test_trigger_is_infrastructure_metadata_only` — Trigger only in scheduler payloads
14. `test_schedule_is_infrastructure_not_organisational` — Schedule not in org models
15. `test_bus_workflow_requested_carries_trigger_as_metadata` — Bus carries trigger as metadata

### F. Intent-Driven Invocation (3 tests)
16. `test_intent_driven_invocation_routes_through_ocp` — OCP is the intent-based authority
17. `test_intent_driven_invocation_has_no_actor_context` — No actor at workflow boundary (Inc 36)
18. `test_ocp_selects_workflow_only_on_intent` — OCP receives intent, not trigger

### G. Automated BAU Invocation (2 tests)
19. `test_automated_invocation_bypasses_ocp` — Triggers bypass OCP
20. `test_intent_driven_and_automated_use_same_execution_contract` — Same port, different sources

### H. Trigger Ownership (2 tests)
21. `test_trigger_ownership_all_in_workflow_runner` — All triggers in infrastructure
22. `test_manual_invocation_is_api_endpoint` — Manual is API transport

### I. OCP Responsibility (2 tests)
23. `test_ocp_selects_only_on_organisational_intent` — OCP takes intent, not trigger
24. `test_ocp_does_not_process_workflow_requested_events` — OCP ignores workflow events
25. `test_ocp_select_execution_path_returns_workflow_definition` — OCP returns definition for execution

### J. Workflow Discovery Implications (2 tests)
26. `test_two_discovery_mechanisms_by_design` — build_workflow_lookup vs resolve_workflow_path
27. `test_automated_invocation_does_not_use_intent_discovery` — Automated uses direct name

### K. Duplicate Invocation Implications (2 tests)
28. `test_no_idempotency_mechanism_exists` — No dedup, each execution is independent
29. `test_no_duplicate_invocation_semantic_in_workflow_state` — No invocation tracking

### L. Invocation Failure Ownership (3 tests)
30. `test_failure_at_trigger_resolution_owned_by_api` — API handles 404
31. `test_failure_at_workflow_start_owned_by_executor` — Executor handles start failure
32. `test_failure_ownership_boundaries_are_distinct` — Different boundaries, different ownership

### M. External-System Implications (2 tests)
33. `test_paperclip_is_work_backend_not_workflow_trigger` — Paperclip ≠ workflow trigger
34. `test_external_systems_do_not_define_invocation_concepts` — External systems use existing contracts

### N. WorkflowInvocation Concept (2 tests)
35. `test_no_organisational_entity_requires_invocation_records` — No entity needs it
36. `test_invocation_is_execution_request_with_infrastructure_source` — Invocation is execution request

### O. Minimum Change (1 test)
37. `test_no_minimum_architectural_change_required` — None needed

### P. Summary (1 test)
38. `test_architectural_tests_cover_all_increment39_areas` — 21+ tests covering all areas

### Q. Alternatives Rejected (2 tests)
39. `test_workflow_invocation_entity_is_rejected` — No WorkflowInvocation entity
40. `test_scheduler_bus_integration_is_rejected_as_organisational_concept` — OCP not expanded to triggers

### R. Remaining Gaps (2 tests)
41. `test_no_remaining_architectural_gap_for_invocation` — No gap exists
42. `test_final_question_answer_invocation_is_execution_request` — Final answer confirmed

---

## Q. Alternatives Explicitly Rejected

### Rejected: WorkflowInvocation Entity
- No organisational entity requires invocation records
- WorkflowExecutionRequest already carries the minimum contract
- Would duplicate WorkflowState with organisational metadata
- No evidence that anything needs to track invocation metadata

### Rejected: Expanding OCP to Receive Automated Triggers (Option B)
- No evidence that OCP should know about schedules/events/webhooks
- `select_execution_path` takes intent, not trigger
- Automated triggers already work without OCP involvement
- Would expand OCP responsibilities without evidence

### Rejected: Trigger/Invocation as Organisational Concept (Option C)
- Triggers are infrastructure metadata in scheduler payloads
- No organisational model has trigger fields
- The OCP does not process WorkflowRequested events
- Infrastructure already handles triggers correctly

### Rejected: Idempotency System
- No organisational entity requires deduplication
- Each execution creates a new WorkflowState (by design)
- Duplicate execution has no established semantic
- Remains an implementation concern

---

## R. Remaining Architectural Gaps

### Gap 1: No Tracking of Invocation Frequency or Patterns
- WorkflowState does not track how often a workflow is invoked
- No invocation count, last-invoked timestamp, or frequency analysis exists
- **Resolution**: None required. If invocation frequency becomes an organisational
  concern, a future increment would be needed to evaluate it.

### Gap 2: No Correlation Between Invocation Source and Outcome
- Different invocation sources (manual, scheduled, bus) are not correlated with
  execution outcomes at the organisational level
- **Resolution**: None required. WorkflowState provides sufficient execution
  monitoring. If source-outcome correlation becomes needed, it would be a
  future increment.

### Gap 3: No Workflow Versioning at Invocation
- Invocation does not specify which version of a workflow definition to use
- Current resolution always uses the latest YAML file
- **Resolution**: None required at this increment. Versioned workflow invocation
  is a future concern if workflow evolution becomes an organisational need.

---

## Final Question

**"Is workflow invocation simply an execution request whose source/trigger belongs outside WorkflowDefinition and OCP, or does the organisation need an explicit WorkflowInvocation concept to represent something that the current architecture cannot otherwise express?"**

**Answer: YES** — Workflow invocation is simply an execution request whose
source/trigger belongs outside WorkflowDefinition and OCP. The organisation
does NOT need an explicit WorkflowInvocation concept.

### Justification

1. **All 6 invocation paths converge on `WorkflowExecutionPort.execute_workflow(WorkflowExecutionRequest)`.** The single existing contract carries `workflow_name`, `initial_context`, and `role_override` — sufficient for an execution request.

2. **Triggers remain infrastructure concerns.** Schedule (scheduler.py), event (bus.py), manual (api.py), and recurring (scheduler.py) triggers are all owned by workflow_runner infrastructure. No organisational concept requires trigger fields.

3. **OCP selects only on organisational intent.** `select_execution_path(intent, context)` takes an intent string — the only legitimate organisational reason to execute a workflow. Automated triggers bypass OCP by design (confirmed by `_handle_bus_workflow_requested` having no OCP references).

4. **Two discovery mechanisms exist by design.** `build_workflow_lookup` serves intent-driven discovery; `resolve_workflow_path` serves direct invocation. Automated triggers use direct name resolution, not intent discovery.

5. **WorkflowState provides sufficient execution tracking.** No organisational entity needs invocation metadata — trigger, source, schedule, or correlation. WorkflowState tracks execution progress; it is the correct endpoint.

6. **No organisational entity requires invocation records.** Work, Role, WorkflowDefinition, and WorkflowState have no trigger/schedule/source/invocation fields — and should not have them.

### Architectural Decision: **A** — Invocation is already adequately represented; triggers remain infrastructure/application concerns and no change is required.
