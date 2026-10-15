# Increment 37 — Workflow Boundary → BAU Execution Semantics

## Investigate the boundary between WorkflowDefinition, WorkflowState, Work, and BAU execution. Determine whether BAU is simply repeated WorkflowDefinition execution with WorkflowState as execution state, or whether the architecture requires an additional relationship or concept.

---

## A. Current BAU Execution Call Graph

Two parallel BAU execution paths exist. They never converge.

### Path 1: BAU via EXISTING_WORKFLOW (workflow execution)

```
ChatRequest(user_id)
  ↓ AssistantChatService.__call__
Intent + Frame
  ↓ SolutionSelectionPort.select_execution_path (via SolutionSelectionAdapter)
ExecutionPathResult.EXISTING_WORKFLOW (workflow=WorkflowDefinition)
  ↓ ChatService._execute_workflow_response
WorkflowExecutionRequest(workflow_name, initial_context={})
  [actor identity dropped — user_id NOT propagated]
  ↓ WorkflowExecutionPort.execute_workflow (contract)
WorkflowExecutionAdapter.execute_workflow(request)
  [no actor_context, no authorisation_port, no recorder]
  ↓ execute_workflow_from_file(workflow_path, initial_context, role_override)
executor.execute_workflow(workflow, workflow_path, ...)
  ↓ create_workflow_state(...) — WorkflowState created (pending → running)
  ↓ for each SKILL step: handle_skill_step(step, workflow, context, role_override)
  ↓   compose_skill_prompt(step, workflow, context, role_override) [YAML skill loading]
  ↓   runtime_client.run(prompt) [LangGraph HTTP]
  ↓ for each TOOL step: handle_tool_step(step, context)
  ↓ for each WORKFLOW step: handle_workflow_step(step, context)
  ↓ advance_step, fail_workflow as needed
  ↓ WorkflowState (completed|failed, step_results, context)
  ↓ bus.publish_workflow_completed / publish_workflow_failed
  ↓ WorkflowExecutionResult(status, workflow_name, output, error)
  ↓ ChatResponse returned to user
[NO Work created]
[NO evidence recorded (no InvocationRecorder, no complete_work, no record_work_learning)]
[NO return to OCP]
```

### Path 2: BAU via CAPABILITY_PATH (Work execution)

```
ChatRequest(user_id)
  ↓ AssistantChatService.__call__
Intent + Frame
  ↓ SolutionSelectionPort.select_execution_path
ExecutionPathResult.CAPABILITY_PATH (capability_id=...)
  ↓ ChatService._handle_capability_path_response
  ↓ _delegate_work_response
  ↓ WorkManagementPort.create_work(WorkCreateRequest(...))
Work (status=PENDING, work_type="project", required_capability_ids=[cap_id])
  ↓ WorkManagementPort.mark_ready(work_id)
Work.status = READY
  ↓ Operations._handle_event(WorkEvent(READY))
Operations._select_backend(work) → WorkerBackend
  ↓ WorkerBackend.execute(work)
Worker.execute(work, org_plane)
  ↓ work.status = IN_PROGRESS
  ↓ Worker._execute_capability(work)
  ↓ CapabilityExecutionPort.execute(capability_id, context, actor_context)
  ↓ CapabilityExecutionAdapter.execute(capability_id, context, actor_context)
  ↓   _check_authorisation: ExecutionAuthorisationPort.is_authorised(actor_id, actor_type, capability_id)
  ↓   deployment = deployment_factory(capability)
  ↓   execute_capability(capability, context, deployment)
  ↓   InvocationRecorder.record_invocation(capability_id, result, actor_context)
  ↓ ExecutionResult(outputs, artifacts, telemetry)
  ↓ Worker returns result (status=completed, execution_mode=capability_execution_port)
Operations.complete_work(work_id, result)
  ↓ Work.status = COMPLETED, Work.outcome = result
```

### Where These Two Models Converge

**They do not converge.** The two paths share only the initial intent→OCP selection stage. After that they diverge completely:
- EXISTING_WORKFLOW → WorkflowExecutionPort → WorkflowExecutionAdapter → executor → skills (LangGraph) → WorkflowExecutionResult → ChatResponse
- CAPABILITY_PATH → Work → Worker → CapabilityExecutionPort → CapabilityExecutionAdapter → deployment → ExecutionResult → complete_work → Work.outcome

---

## B. Current Work Execution Call Graph

```
Work (status=READY, created via WorkManagementPort.create_work)
  ↓ Operations._handle_event(WorkEvent.READY)
Operations._handle_event filters:
  - event_type == WorkEventType.READY
  - work_id not already processed
  ↓ Operations._select_backend(work)
  → WorkerBackend (if no assignee_agent_id)
  → PaperclipBackend (if assignee_agent_id set and Paperclip available)
  ↓ WorkerBackend.execute(work) or PaperclipBackend.execute(work)
Worker.execute(work, org_plane):
  if work.work_type == "capability_development":
    → Worker._develop_capability(work)
      → Capability created and registered
      → artifact written
      → result (status=completed, execution_mode=capability_development)
  elif work.required_capability_ids and capability_execution available:
    → Worker._execute_capability(work)
      → actor_context = {actor_id: self._agent_id, actor_type: "agent"}
      → CapabilityExecutionPort.execute(capability_id, context, actor_context)
      → ExecutionAuthorisationPort.is_authorised check
      → result (status=completed, execution_mode=capability_execution_port)
  else:
    → Worker._do_work(work)
      → intent inference from work title/description
      → route to content-specific generator (summary, plan, proposal, etc.)
      → result (status=completed, summary, output_path)
  ↓ Exception caught → outcome = {status: "failed", error: ...}
Operations (caller):
  result = backend.execute(work)
  Operations.complete_work(work_id, result) [Work.status = COMPLETED, Work.outcome = result]
  OR
  Operations.fail_work(work_id, {"error": str(exc)}) [Work.status = FAILED]
  if capability_development: Operations._assess_capability_development(work, result)
```

**Key observation**: Worker.execute has three paths:
1. Capability development (work_type="capability_development")
2. Capability execution (work.required_capability_ids → CapabilityExecutionPort)
3. Generic work (_do_work — text generation)

**None of these paths reference WorkflowDefinition, WorkflowState, or workflow execution.**

---

## C. WorkflowDefinition Semantics

`WorkflowDefinition` (`workflow_runner/models.py:33-50`) describes WHAT to execute:

- `version`: schema version ("1")
- `name`: workflow name
- `description`: human-readable description
- `kind`: always "workflow"
- `role`: roles that can execute this workflow (declarative, not enforced)
- `intent`: intent mapping for discovery
- `inputs`: input parameter names
- `outputs`: output parameter names
- `steps`: ordered list of steps (SKILL, TOOL, WORKFLOW types)

**WorkflowDefinition is an execution definition.** It tells the executor what steps to run and in what order. It does not describe organisational authority, work allocation, or outcome expectations.

**WorkflowDefinition lives in `workflow_runner` package.** It is not imported by `organisation`, `ai`, or any organisational package. The OCP receives it as opaque `Any` through the `workflow_lookup` callback.

---

## D. WorkflowState Semantics

`WorkflowState` (`workflow_runner/models.py:75-86`) represents execution progress:

- `workflow_id`: unique run identifier
- `workflow_name`: name of the workflow being executed
- `workflow_path`: path to the YAML file
- `status`: pending/running/completed/failed/paused/stopped
- `current_step_index`: execution progress
- `steps`: list of Step objects
- `step_results`: results of each step execution
- `context`: execution context (inputs, intermediate outputs)
- `error`: error message if failed

**WorkflowState is execution state.** It tracks a single run of a WorkflowDefinition. Each execution creates a new WorkflowState instance. It is persisted in the workflow_runner's database (if configured).

**WorkflowState has no reference to Work.** It does not know about organisational effort, assignments, or outcomes.

---

## E. Work Semantics

`Work` (`organisation/src/role.py:96-126`) represents organisational effort:

- `id`: unique work identifier
- `title`, `description`: human-readable
- `work_type`: "bau", "project", "initiative", "capability_development"
- `status`: PENDING/ASSIGNED/READY/IN_PROGRESS/COMPLETED/FAILED
- `accountable_role_id`: organisational accountability
- `coordinating_role_id`: coordination role
- `assignee_actor_id`: executing actor
- `required_capability_ids`: capabilities needed
- `acceptance_criteria`: success criteria
- `outcome`: execution result (dict or None)
- `context`: execution context
- `created_at`, `updated_at`: timestamps

**Work is an organisational outcome/effort record.** It represents something the organisation has agreed to do. It has accountability, assignment, criteria, and outcome. It is NOT an execution unit — it is an organisational unit.

**Work lives in `organisation` package.** It is imported by `workflow_runner/src/operations.py` and `workflow_runner/src/worker.py` to execute work, but Work does not reference workflow_runner.

---

## F. WorkflowState ↔ Work Relationship

### Cross-Reference Analysis

| Direction | Evidence |
|-----------|----------|
| WorkflowState → Work | **No reference.** WorkflowState has no `work_id`, no `work` field, no Work import |
| Work → WorkflowState | **No reference.** Work has no `workflow_id`, no `workflow_name`, no WorkflowState import |
| WorkflowDefinition → Work | **No reference.** WorkflowDefinition has no Work-related fields |
| Work → WorkflowDefinition | **No reference.** Work has no workflow-related fields |
| Operations → Workflow execution | **No reference.** Operations handles Work via backends only |
| Worker → Workflow execution | **No reference.** Worker.execute has no workflow path |

### Answers to Specific Questions

**Does every BAU workflow execution represent Work?**
**No.** EXISTING_WORKFLOW path executes a workflow without creating Work. The workflow execution result is returned directly as a ChatResponse. No Work item is created, assigned, or tracked.

**Does every Work execution use a workflow?**
**No.** Worker.execute has three paths (capability_development, capability_execution, generic_work). None reference workflows. Work is executed by Worker or PaperclipBackend, not by the workflow executor.

**Can WorkflowState exist without Work?**
**Yes.** Workflow execution via API (`/workflows/{name}/run`), MCP, or scheduler creates WorkflowState without any Work involvement.

**Can Work exist without WorkflowState?**
**Yes.** Work is created via `WorkManagementPort.create_work` and executed by Worker/Operations. No WorkflowState is created.

**Is a workflow run an organisational unit of work?**
**No.** A workflow run produces a `WorkflowExecutionResult` — an execution output, not an organisational record. It has no accountability, no assignment, no acceptance criteria, no outcome field. It is an implementation execution, not an organisational unit.

**Does Work need to reference WorkflowDefinition?**
**No.** Work and WorkflowDefinition are in different packages with no cross-references. Work has `required_capability_ids` — it references capabilities, not workflows.

**Does Work need to reference WorkflowState?**
**No.** Work.outcome is a dict that may contain any result data. It does not reference a specific WorkflowState/run. The two are independent.

**Is keeping them completely separate the correct architecture?**
**Yes.** They represent different classes of organisational activity:
- WorkflowState = execution progress of a predefined procedure
- Work = organisational effort with accountability, criteria, and outcome

---

## G. Who/What Creates Work

**Work is created by:**

1. `WorkManagementPort.create_work()` called from chat service:
   - `_delegate_work_response` (CAPABILITY_PATH, NEW_CAPABILITY_REQUIRED, HUMAN_TEAM_INVESTIGATION paths)
   - `_handle_new_capability_required_response` (capability gap → capability_development Work)
   - `_handle_human_team_investigation_response` (human investigation → project Work)
   - Various other chat handlers for delegation scenarios

**Work is NOT created by:**
- Workflow execution (EXISTING_WORKFLOW path)
- Worker.execute
- Operations
- WorkflowExecutionAdapter
- executor.execute_workflow
- The scheduler

**Directionality: intent → Work creation (when Work is needed)**

The chat service creates Work when the OCP determines a capability path is needed. Workflow execution is an alternative to Work creation — when a workflow exists, no Work is created. They are alternatives, not a sequence.

---

## H. Who/what Creates WorkflowState

**WorkflowState is created by:**

1. `create_workflow_state()` called from:
   - `executor.execute_workflow()` — when execution starts
   - `_execute_and_publish()` in API — before execution begins
   - `_handle_bus_workflow_requested()` in API — when scheduled/MCP triggered

2. `execute_workflow_from_file()` → `execute_workflow()` → `create_workflow_state()`

**WorkflowState is NOT created by:**
- Work creation (WorkManagementPort.create_work)
- Worker.execute
- Operations
- Any organisational process

**WorkflowState is execution infrastructure, not organisational state.**

---

## I. BAU Semantics

### Is BAU simply repeated execution of an existing workflow?

**Partially, but not exclusively.** There are two BAU execution models:

1. **Workflow BAU**: A known intent matches an existing workflow (EXISTING_WORKFLOW). The workflow executes. No Work is created. This is the purest form of BAU — repeated execution of a known procedure.

2. **Capability BAU**: An intent matches a capability. Work is created, assigned, and executed via Worker/Operations. This is BAU with organisational tracking — the effort is recorded as Work.

Both are BAU. The distinction is whether the organisation needs to track the effort (Work) or the procedure is self-evident (workflow execution).

### Is BAU a distinct organisational state?

**No.** BAU is a `work_type` field value on Work (`work_type="bau"`). It is a classification, not a state. Work.status is the state (PENDING → COMPLETED). BAU is what kind of work, not where in the lifecycle.

### Does BAU require a new domain concept?

**No.** BAU is already represented by `Work.work_type="bau"` when organisational tracking is needed, and by workflow execution (EXISTING_WORKFLOW) when it is not. No new concept is required.

### Or is "BAU" merely a mode/context of execution?

**Yes.** BAU is a mode/context:
- On Work: `work_type="bau"` classifies the effort
- On workflow execution: no explicit BAU marker — the workflow itself represents the understood procedure

---

## J. Innovation → BAU Transition

Using the established learning model:

```
UNCERTAIN (new request, no understanding)
  ↓
WORK (capability_development Work item created)
  ↓
CAPABILITY (capability developed, registered, promoted)
  ↓
EVIDENCE (CapabilityOutcomeAssessor, InvocationRecorder, proficiency)
  ↓
UNDERSTANDING (organisation understands how to handle this)
  ↓
WORKFLOW DEFINITION (YAML created, workflow exists for the intent)
  ↓
BAU (subsequent requests match EXISTING_WORKFLOW → execute workflow)
```

### What Changes Semantically

Before workflow exists:
- Request → OCP → no matching workflow → CAPABILITY_PATH → Work created → Worker executes → Work tracked

After workflow exists:
- Request → OCP → EXISTING_WORKFLOW → workflow executes → result returned → no Work created

**The semantic shift is: from organisational effort tracking to procedural execution.** Once a workflow exists, the organisation no longer needs to track the effort — the procedure is self-executing.

**The workflow definition IS the artifact of innovation becoming BAU.** The transition is marked by the existence of the YAML file, not by any state change in the workflow itself.

---

## K. Outcome Ownership

### Workflow Execution Outcome

- `WorkflowExecutionResult(status, workflow_name, output, error)` — returned to chat service
- `WorkflowState.status`, `WorkflowState.step_results`, `WorkflowState.context` — persisted in workflow_runner DB
- `bus.publish_workflow_completed/failed` — event with workflow_id, error, context

**These are execution outcomes, not organisational outcomes.** They describe what the workflow produced, not what the organisation achieved.

### Work Outcome

- `Work.outcome` (dict or None) — set by `Operations.complete_work(work_id, result)`
- `Work.status` = COMPLETED/FAILED — set by Operations

**This is the organisational outcome.** It records what was achieved in terms of organisational effort.

### Does Work.outcome Remain the Correct Organisational Outcome Mechanism?

**Yes.** Work.outcome is set by Operations.complete_work() and represents the organisational result of a tracked work item. Workflow execution results are execution telemetry, not organisational outcomes. They do not need to flow into Work.outcome because workflow execution does not create Work.

### Where Success/Failure Is Recorded

| Mechanism | Where | Scope |
|-----------|-------|-------|
| Workflow success | WorkflowState.status = "completed" | Execution |
| Workflow failure | WorkflowState.status = "failed", WorkflowState.error | Execution |
| Workflow step success | WorkflowState.step_results[].status = "completed" | Execution |
| Work success | Work.status = COMPLETED, Work.outcome = result | Organisational |
| Work failure | Work.status = FAILED, Work.outcome = error | Organisational |
| Capability execution success | ExecutionResult, InvocationRecorder | Execution + Evidence |

---

## L. Evidence Ownership

### Workflow Execution Evidence

Workflow execution produces **no organisational evidence**:
- No `InvocationRecorder.record_invocation()` call
- No `complete_work()` call
- No `record_work_learning()` call
- No `assess_work_outcome()` call
- No EIMS/ConceptStore interaction

**What it produces instead:**
- `WorkflowState.step_results` — execution telemetry (step names, status, output, error, duration)
- Bus events (`publish_workflow_completed/failed`) — runtime events for workflow_runner
- These are implementation-level telemetry, not organisational evidence

### Capability Execution Evidence

Capability execution produces **organisational evidence**:
- `InvocationRecorder.record_invocation(capability_id, result, actor_context)` — every execution attempt is recorded
- `InvocationRecorder` stores in ConceptStore
- `CapabilityOutcomeAssessor` assesses development work
- `record_work_learning()` records SOLVED_APPROACH concepts for accepted work
- Proficiency records are created

### Can Workflow Execution Feed the Learning Loop?

**Not currently, and not by design.** The learning loop operates on Work items (via `record_work_learning` in `outcome.py`). Workflow execution does not create Work, so it does not enter the learning loop. This is correct because:
1. BAU workflow execution is procedural — it does not produce new organisational knowledge
2. The learning loop is for innovating (developing capabilities from work outcomes)
3. BAU is the end-state of learning, not an input to it

### Is WorkflowState Sufficient for Execution Telemetry?

**Yes.** WorkflowState tracks step results, context, status, and errors. This is sufficient for execution monitoring. It does not need to carry organisational evidence because it is not an organisational record.

---

## M. Failure Ownership

### Workflow Execution Failure

- Owned by: **workflow_runner**
- Recorded in: `WorkflowState.status = "failed"`, `WorkflowState.error`, `WorkflowState.step_results`
- Communicated via: bus events (`publish_workflow_failed`), `WorkflowExecutionResult.error`
- Returned to: chat service → user
- **No organisational consequence**: Work is not created or transitioned, no OCP notification

### Capability/Work Execution Failure

- Owned by: **Operations → Organisation**
- Worker catches exception → returns `{status: "failed", error: ...}`
- Operations.fail_work(work_id, {"error": str(exc)}) → Work.status = FAILED
- Work.outcome = {"error": ...} — recorded as organisational outcome
- **Organisational consequence**: Work tracked, outcome recorded, possible capability assessment

### Distinction

| Failure Type | Owner | Consequence |
|-------------|-------|-------------|
| Workflow step fails | workflow_runner | WorkflowState marked failed, result returned to chat |
| Capability execution fails | CapabilityExecutionAdapter | ExecutionResult with error, InvocationRecorder records attempt |
| Work execution fails | Operations → Organisation | Work marked FAILED, outcome recorded |
| Workflow definition invalid | workflow_runner | WorkflowExecutionResult with error |
| Capability gap | OCP | NEW_CAPABILITY_REQUIRED → Work created |

### Is Failure an Authority Problem or an Execution/Outcome Problem?

**Execution/outcome problem.** Workflow execution failure is an execution result. Work execution failure is an organisational outcome. Neither creates an authority gap. Capability execution failure is an execution boundary event (handled by CapabilityExecutionAdapter's authorisation check). No failure mode requires a new authority concept.

---

## N. Repeatability Implications

### Repeated Successful Workflow Execution

Each execution creates a new WorkflowState:
- New `workflow_id` (UUID)
- New `WorkflowState` instance
- New `step_results`
- `WorkflowDefinition` unchanged

### Does Repeated Execution Create Additional Architectural State?

**No.** Repeated successful execution:
- Creates new WorkflowState instances (execution state — expected)
- Does NOT modify WorkflowDefinition
- Does NOT create Work items
- Does NOT accumulate evidence on the definition
- Does NOT change any organisational state

### Should Evidence Change the Workflow's Status or Representation?

**No.** WorkflowDefinition has no status field that could change. It is a static definition (YAML file). Repeated successful execution does not:
- Promote the workflow
- Score the workflow
- Add confidence/maturity metadata
- Modify the definition

**This is correct.** The workflow definition is the organisational procedure. Its authority derives from being a written procedure, not from execution history. Execution history belongs in WorkflowState instances, which are ephemeral execution records.

---

## O. Trigger Implications

### Where Triggering Belongs

Triggers/schedules are infrastructure concerns, handled by:
- `scheduler.schedule_workflow()` — creates cron trigger in APScheduler
- On trigger fire → publishes `WorkflowRequested` event via bus
- Bus consumer → `_handle_bus_workflow_requested()` → creates WorkflowState → executes workflow

### Does a Triggered Execution Differ Semantically from Intent-Selected Execution?

**No.** Both produce the same result:
- Intent-selected: ChatRequest → OCP → EXISTING_WORKFLOW → WorkflowExecutionRequest → execute_workflow
- Scheduled: Scheduler → WorkflowRequested event → _handle_bus_workflow_requested → execute_workflow

Both:
- Create WorkflowState
- Execute the same WorkflowDefinition
- Produce WorkflowExecutionResult
- Create no Work
- Carry no actor identity

The only difference is the trigger mechanism (user intent vs cron schedule). The execution semantics are identical.

### Triggers on WorkflowDefinition?

**No trigger/schedule fields on WorkflowDefinition.** Confirmed — neither `WorkflowDefinition` nor `Work` has trigger/schedule/cron fields. Triggering is an infrastructure concern handled outside the domain.

---

## P. Execution Context Boundaries

### What Belongs Where

| Concept | Belongs In | Evidence |
|---------|-----------|----------|
| WHAT to execute (steps, skills, tools) | WorkflowDefinition | `workflow_runner/models.py:33-50` |
| Execution progress (current step, results) | WorkflowState | `workflow_runner/models.py:75-86` |
| Execution request (which workflow, initial context) | WorkflowExecutionRequest | `contracts/workflow_execution.py:6-12` |
| Organisational accountability | Work | `organisation/src/role.py:96-126` |
| Execution result (what was produced) | WorkflowExecutionResult | `contracts/workflow_execution.py:14-20` |
| Organisational outcome | Work.outcome | `organisation/src/role.py:121` |
| Execution telemetry | WorkflowState.step_results | `workflow_runner/models.py:83` |
| Actor identity (for execution) | CapabilityExecutionPort.actor_context | `contracts/capability_execution.py:11-12` |
| Actor identity (NOT for workflow) | — | WorkflowExecutionRequest has no actor fields |

### No Duplication

- Organisational semantics (accountability, assignment, criteria) are NOT in WorkflowState or WorkflowExecutionRequest
- Execution semantics (step results, context) are NOT in Work
- Each concept carries only what is relevant to its layer

---

## Q. Whether a New Organisational Concept Is Required

### Analysis

**No new concept is required.** The current architecture handles all observed needs:

| Need | Current Mechanism | Sufficient? |
|------|-------------------|-------------|
| Track BAU effort | Work.work_type="bau" | Yes |
| Execute known procedure | WorkflowDefinition → executor | Yes |
| Track execution progress | WorkflowState | Yes |
| Track organisational outcome | Work.outcome | Yes |
| Evidence from execution | Capability: InvocationRecorder; Workflow: none needed | Yes |
| Learning from outcomes | record_work_learning (on accepted Work) | Yes |
| Innovation tracking | Work (capability_development) → Capability | Yes |
| Trigger/schedule | Infrastructure (scheduler) | Yes |

### Why No New Concept Is Needed

1. **Workflow execution and Work execution are alternatives, not a sequence.** When a workflow exists, the organisation does NOT create Work. The workflow IS the BAU procedure. Creating Work for every workflow execution would be redundant — it would track what is already tracked by the procedure itself.

2. **WorkflowState is execution state, not organisational state.** It tracks a run, not an effort. Adding Work references to WorkflowState would conflate execution telemetry with organisational effort.

3. **Work does not need to know about workflows.** Work references capabilities (required_capability_ids), not workflows. The capability is what matters organisationally — the workflow is an implementation detail of how a known procedure is executed.

---

## R. Minimum Architectural Change, If Any

**No change required.** The current separation is correct and internally consistent.

### Conclusion: **A** — Current separation is correct; no change required.

### Justification

1. **BAU is executed via EXISTING_WORKFLOW when a workflow exists** — no Work created, no organisational tracking needed, the workflow IS the procedure.

2. **BAU is executed via Work when no workflow exists** — Work is created, tracked, executed by Worker, completed by Operations.

3. **WorkflowState represents execution progress**, independent of Work. This is correct — execution progress is not an organisational concern.

4. **Work represents organisational effort**, independent of WorkflowState. This is correct — effort tracking is not an execution concern.

5. **The two models converge only at OCP selection** — both paths start with intent→OCP but diverge immediately after.

6. **No cross-referencing is needed** — the two models serve different purposes and there is no organisational need to link them.

7. **Repeated execution does not require new state** — each execution creates a new WorkflowState; WorkflowDefinition and Work remain unchanged.

8. **Failure ownership is clear** — workflow failures are execution results, Work failures are organisational outcomes.

---

## S. Architectural Tests Added

18 tests in `packages/organisation/tests/test_increment37_bau_execution_semantics.py`:

### A. BAU Execution Call Graph (4 tests)
1. `test_workflow_execution_path_does_not_create_work` — EXISTING_WORKFLOW path does not call create_work
2. `test_capability_path_creates_work` — CAPABILITY_PATH path does call create_work
3. `test_workflow_execution_result_does_not_become_work_outcome` — WorkflowExecutionResult has no outcome/work fields
4. `test_operations_does_not_execute_workflows` — Operations executes Work via backends, not workflows

### B. WorkflowState vs Work (4 tests)
5. `test_workflow_state_has_no_work_reference` — WorkflowState has no work_id/work fields
6. `test_work_has_no_workflow_reference` — Work model has no workflow_id/workflow_name fields
7. `test_workflow_state_and_work_in_different_packages` — WorkflowState in workflow_runner, Work in organisation/role
8. `test_worker_has_no_workflow_reference` — Worker.execute has no workflow/WorkflowDefinition handling

### C. Who Creates What (3 tests)
9. `test_work_is_created_by_chat_not_workflow` — Work is created by create_work in chat, not by workflow execution
10. `test_workflow_state_is_created_by_executor` — WorkflowState is created by create_workflow_state in executor/API
11. `test_operations_selects_backend_by_assignee_not_workflow` — Operations backend selection uses assignee_agent_id, not workflow

### D. BAU Semantics (2 tests)
12. `test_bau_work_type_is_classification_not_entity` — "bau" is a work_type value, not a separate entity
13. `test_existing_workflow_does_not_require_work` — OCP can select EXISTING_WORKFLOW without creating Work

### E. Evidence and Outcome (3 tests)
14. `test_workflow_execution_does_not_record_invocation` — workflow execution has no InvocationRecorder calls
15. `test_capability_execution_records_invocation` — capability execution does record invocations (contrast)
16. `test_workflow_state_step_results_are_execution_telemetry` — step_results contain execution data, not organisational evidence

### F. Failure Ownership (2 tests)
17. `test_workflow_failure_does_not_transition_work` — workflow failure does not create or modify Work
18. `test_work_failure_records_outcome` — work failure records outcome via complete_work/fail_work

---

## T. Alternatives Explicitly Rejected

### Rejected: Linking Work to WorkflowExecution
- Would require adding workflow_id to Work or Work references to WorkflowState
- No evidence of an organisational need to track which workflow produced a Work result
- Work references capabilities, not workflows — this is the correct abstraction level
- Would conflate execution telemetry with organisational effort tracking

### Rejected: Creating a BAU Entity
- BAU is already represented as `work_type="bau"` on Work
- Creating a BAU entity would add a classification layer that serves no purpose
- BAU is a context, not a distinct organisational concept

### Rejected: Creating a WorkflowRun/WorkflowInstance Entity
- WorkflowState already serves this purpose
- WorkflowState IS the per-execution record (workflow_id, status, step_results, context)
- Adding a separate entity would duplicate WorkflowState with organisational metadata
- Would blur the line between execution state and organisational state

### Rejected: Feeding Workflow Results into Work.outcome
- Workflow execution does not create Work, so there is no Work.outcome to feed
- Would require routing workflow results to a non-existent Work item
- Would create a phantom Work just to hold workflow output — conceptually wrong

### Rejected: Creating an Evidence Entity for Workflow Execution
- The constraints explicitly forbid creating Evidence entities
- WorkflowState.step_results provides sufficient execution telemetry
- Organisational evidence (InvocationRecorder, EIMS concepts) belongs to capability execution, not workflow execution

### Rejected: Adding Workflow References to Work
- Work has `required_capability_ids` — the correct abstraction is capabilities, not workflows
- A workflow is an implementation detail; capabilities are organisational concepts
- Adding workflow_id to Work would couple organisational tracking to implementation

### Rejected: Promoting WorkflowState to an Organisational Concept
- WorkflowState is execution state (pending → running → completed/failed)
- It tracks execution progress, not organisational effort
- Promoting it would violate the execution/organisation boundary

---

## Final Conclusion

**"Is BAU simply the repeated execution of an already-understood WorkflowDefinition, with WorkflowState representing execution and Work representing organisational effort/outcomes where applicable — or does the architecture require an additional relationship or concept to make that distinction explicit?"**

**Answer: BAU IS the repeated execution of an already-understood WorkflowDefinition, with WorkflowState representing execution and Work representing organisational effort/outcomes where applicable. The architecture requires NO additional relationship or concept.**

### Justification

1. **Two BAU paths exist and are both valid:**
   - Workflow BAU: intent → EXISTING_WORKFLOW → execute workflow → result. No Work created.
   - Capability BAU: intent → CAPABILITY_PATH → create Work → Worker executes → complete Work.

2. **WorkflowState and Work are correctly separate:**
   - WorkflowState tracks execution progress (a run of a known procedure)
   - Work tracks organisational effort (accountability, criteria, outcome)
   - They serve different purposes and have no cross-references

3. **BAU does not require a new concept:**
   - BAU via workflow: the WorkflowDefinition IS the BAU procedure
   - BAU via Work: `work_type="bau"` classifies the effort
   - Both are sufficient

4. **The innovation → BAU transition is implicit:**
   - Innovation produces WorkflowDefinition (YAML file)
   - Once a workflow exists, subsequent executions are BAU (EXISTING_WORKFLOW)
   - No state change marks the transition — the existence of the workflow IS the transition

5. **Evidence and outcomes are correctly owned:**
   - Capability execution produces InvocationRecorder evidence → feeds learning loop
   - Workflow execution produces WorkflowState telemetry → sufficient for execution monitoring
   - Work.outcome → organisational outcome for tracked work

6. **Failure ownership is clear:**
   - Workflow failures: execution results in WorkflowState
   - Work failures: organisational outcomes in Work.outcome

**Architectural Decision: A** — Current separation is correct; no change required.
