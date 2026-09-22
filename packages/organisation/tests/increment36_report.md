# Increment 36 — Workflow Execution Authority & BAU Boundary

## Investigate whether workflow execution bypassing capability authorisation is a valid architectural boundary or an authorisation gap, and whether WorkflowDefinition remains sufficient.

---

## A. Workflow Execution Call Graph

```
ChatRequest (user_id present)
  ↓ ChatService.__call__
Intent + Frame + ChatRequest.user_id
  ↓ SolutionSelectionPort.select_execution_path
ExecutionPathResult (EXISTING_WORKFLOW, workflow=WorkflowDefinition)
  ↓ ChatService._execute_workflow_response
WorkflowExecutionRequest(workflow_name=..., initial_context={})
  [NOTE: user_id is NOT propagated — ad-hoc request built at line 1598-1602 of ai/src/chat.py]
  ↓ WorkflowExecutionPort.execute_workflow (contract)
WorkflowExecutionAdapter.execute_workflow (no actor_context param, no authorisation_port in constructor)
  ↓ execute_workflow_from_file(workflow_path, initial_context, role_override)
executor.execute_workflow(workflow, workflow_path, initial_context, role_override, ...)
  [NOTE: no actor_context, no invocation_recorder, no authorisation_port]
  ↓ handle_skill_step(step, workflow, context, role_override) [for SKILL steps]
  ↓ compose_skill_prompt(step, workflow, context, role_override)
  ↓ runtime_client.run(prompt) [LangGraph HTTP call]
  ↓ StepResult
```

For TOOL steps: `handle_tool_step(step, context)` — no actor, no authorisation.
For nested WORKFLOW steps: `handle_workflow_step(step, context, search_paths)` — no actor, no authorisation.

**Evidence:**
- `WorkflowExecutionRequest` fields: `workflow_name`, `initial_context`, `role_override` — no actor fields (`ai/src/chat.py:1598-1602`, `contracts/workflow_execution.py:6-12`)
- `WorkflowExecutionAdapter.__init__` takes only `repo_root` — no `authorisation_port` (`workflow_runner/src/adapters/workflow_execution_adapter.py:17`)
- `executor.execute_workflow` params: `workflow`, `workflow_path`, `initial_context`, `role_override`, `search_paths`, `initial_state`, `on_step_start`, `on_step_complete`, `database_url` — no actor or recorder (`workflow_runner/executor.py:31-41`)
- `handle_skill_step` params: `step`, `workflow`, `context`, `role_override` — no actor (`workflow_runner/handlers/skill_handler.py:18-23`)

---

## B. Capability Execution Call Graph

```
Work (created by OCP, has assignee_actor_id, required_capability_ids)
  ↓ Operations.select_backend(work)
WorkerBackend.execute(work) or PaperclipBackend.execute(work)
  ↓ Worker.execute(work, org_plane)
Worker.execute_capability(capability_id, context, actor_context)
  ↓ CapabilityExecutionPort.execute(capability_id, context, actor_context) (contract)
CapabilityExecutionAdapter.execute(capability_id, context, actor_context)
  ├─→ CapabilityExecutionAdapter._check_authorisation(capability_id, actor_context)
  │    └─→ ExecutionAuthorisationPort.is_authorised(actor_id, actor_type, capability_id)
  │         └─→ AuthorisationResult(authorised, assignment, proficiency, reason)
  ├─→ DeploymentResolver.resolve(capability_id, "default") → CapabilityDeployment
  └─→ execute_capability(capability, context, deployment)
  ↓ ExecutionResult(outputs, artifacts, telemetry)
  ↓ InvocationRecorder.record_invocation(capability_id, result, actor_context)
```

**Evidence:**
- `CapabilityExecutionPort.execute` signature: `(self, capability_id: str, context: dict[str, Any], actor_context: dict[str, Any])` (`contracts/capability_execution.py:11-12`)
- `CapabilityExecutionAdapter.__init__` accepts `authorisation_port: ExecutionAuthorisationPort | None` (`workflow_runner/src/adapters/capability_execution_adapter.py:24-30`)
- `CapabilityExecutionAdapter._check_authorisation` calls `self._authorisation_port.is_authorised(actor_id, actor_type, capability_id)` (`workflow_runner/src/adapters/capability_execution_adapter.py:74-83`)
- `ExecutionAuthorisationPort.is_authorised` takes `actor_id`, `actor_type`, `capability_id` (`people_capability/src/execution_authorisation.py:37-42`)
- `CapabilityExecutionAdapter.execute` calls `self._invocation_recorder.record_invocation(capability_id, result, actor_context)` at every return path (`workflow_runner/src/adapters/capability_execution_adapter.py:45, 56, 67, 71`)

---

## C. Actor Identity Flow

### Where Actor Identity Exists

| Location | Identity Field | Evidence |
|----------|---------------|----------|
| Incoming HTTP request | `ChatRequest.user_id` | Chat transport layer receives actor identity |
| Capability execution (actor_context) | `actor_id`, `actor_type` | `CapabilityExecutionAdapter.execute(actor_context)` |
| ExecutionAuthorisationPort | `actor_id`, `actor_type` | `is_authorised(actor_id, actor_type, capability_id)` |
| Work.assignee_actor_id | `assignee_actor_id` | `Work` model line 113 |
| OrgContext | `current_actor_id` | `get_organisational_context` line 270 |

### Where Actor Identity Disappears

| Transition | What Happens | Evidence |
|------------|-------------|----------|
| `_execute_workflow_response` | `WorkflowExecutionRequest` built ad-hoc with only `workflow_name` and `initial_context={}` — `user_id` NOT propagated | `ai/src/chat.py:1598-1602` — `assert "user_id" not in func_source` (test) |
| `WorkflowExecutionAdapter.execute_workflow` | No actor_context parameter | `workflow_runner/src/adapters/workflow_execution_adapter.py:27-56` |
| `executor.execute_workflow` | No actor_context, no invocation_recorder parameter | `workflow_runner/executor.py:31-41` |
| `handle_skill_step` | No actor parameter at all | `workflow_runner/handlers/skill_handler.py:18-23` |
| `runtime_client.run(prompt)` | Only prompt string passed — no actor identity | `workflow_runner/handlers/skill_handler.py:76` |
| REST API `/workflows/{name}/run` | `RunRequest` has no actor fields | `workflow_runner/api.py:RunRequest` (test confirms no actor_id/context) |
| Scheduler `_fire` payload | No actor_id, actor_context, user_id, principal | `workflow_runner/scheduler.py:71-79` |
| MCP `run_workflow` tool | No actor fields in signature | `workflow_runner/src/mcp_server.py:run_workflow` (test confirms) |

### Summary

Actor identity enters the system at the chat transport layer and terminates at `_execute_workflow_response`. From that point forward, **no actor identity exists anywhere in the workflow execution path**. The identity is not passed, stored, or referenced. For scheduled/MCP-triggered execution, there is no actor identity from the start.

---

## D. Authority Flow

### Organisation Authority (OCP)

The OCP exercises authority through:
- `select_execution_path` — decides which path an intent should take (EXISTING_WORKFLOW, CAPABILITY_PATH, NEW_CAPABILITY_REQUIRED, HUMAN_TEAM_INVESTIGATION)
- `assign_work` — assigns Work to roles/actors
- `complete_work` / `fail_work` — transitions Work state
- `register_capability` — registers capabilities (delegates to CapabilityRegistry)
- `delegate_authority` — delegates authority between roles

### OCP Authority Over Workflow Selection

`select_execution_path` selects a workflow based on intent matching only — no actor authorisation is checked before selection. The OCP does not ask "is this actor authorised to execute this workflow?" It asks "does a matching workflow exist?"

### OCP Has No Authority Over Workflow Execution

The OCP returns the workflow definition. After that, the workflow execution path does not return to the OCP. There is no callback, no evidence recording, no status update. `_execute_workflow_response` does not call `complete_work`, `fail_work`, or `record_work_learning`.

### Capability Authority (ExecutionAuthorisationPort)

Capability execution authority is exercised by `ExecutionAuthorisationPort.is_authorised(actor_id, actor_type, capability_id)`. This is checked inside `CapabilityExecutionAdapter._check_authorisation` before any deployment or execution occurs.

### Authority Gap

The workflow execution path does not consult `ExecutionAuthorisationPort` at any point. No code in the workflow execution path calls `is_authorised`. The `WorkflowDefinition.role` field exists but is never checked against any actor.

---

## E. Exact Point at Which Capability Authorisation Is Bypassed

**The bypass occurs at the OCP selection boundary, specifically at `_execute_workflow_response` in `ai/src/chat.py:1598-1602`.**

When `ExecutionPathResult.path == EXISTING_WORKFLOW`, the assistant:
1. Does NOT check whether the initiating actor is authorised to execute the workflow
2. Does NOT check whether the workflow requires any role/authorisation
3. Builds a `WorkflowExecutionRequest` with no actor fields
4. Calls `WorkflowExecutionPort.execute_workflow` — which has no actor parameter
5. Never returns to the OCP for authority validation

The bypass is not at a single line — it is a **structural separation** confirmed by:
- `WorkflowExecutionAdapter.__init__` has no `authorisation_port` parameter
- `executor.execute_workflow` has no actor/recorder parameter
- `handle_skill_step` has no actor parameter
- `composition.py` wires `authorisation_port` only to `CapabilityExecutionAdapter`, not `WorkflowExecutionAdapter`

**The composition root is the architectural proof:** `WorkflowExecutionAdapter()` is instantiated with zero arguments at `composition.py:240`, while `CapabilityExecutionAdapter` receives `authorisation_port=authorisation_port` at `composition.py:182-187`.

---

## F. Whether That Bypass Is Intentional, Valid, or a Defect

**The bypass is intentional by composition root design** (authorisation_port is wired only to the capability path) **and is architecturally valid** for the following reasons:

### Why It Is Intentional
1. The composition root explicitly wires `authorisation_port` only to `CapabilityExecutionAdapter` — not to `WorkflowExecutionAdapter`
2. The `WorkflowExecutionPort` contract has no actor fields — it was designed without them
3. `WorkflowExecutionAdapter` has no hidden authorisation attribute — confirmed by test `test_workflow_execution_adapter_class_has_no_authorisation_attribute`

### Why It Is Valid
1. **Workflow steps execute skills, not capabilities.** `StepType` has values `WORKFLOW`, `SKILL`, `TOOL` — no `CAPABILITY` type. A skill is a prompt template executed via LangGraph, not a domain capability with an interface contract.
2. **The two paths are structurally non-convergent.** There is no code path where `WorkflowExecutionAdapter` calls `CapabilityExecutionPort`, or vice versa. Confirmed by test `test_two_execution_paths_never_converge`.
3. **Capability execution and workflow execution serve different organisational purposes.** Capability execution exercises a domain capability with actor-specific authorisation. Workflow execution runs an organisational procedure whose authority derives from the workflow itself.

### Why It Is Not a Defect
1. The bypass is not accidental — the composition root deliberately separates the paths
2. The architecture does not claim workflow execution goes through capability authorisation
3. `CapabilityExecutionPort` and `WorkflowExecutionPort` are distinct contracts with different signatures

### Caveat
The architecture supports the bypass **passively** (by not checking) rather than **actively** (by having an explicit model of workflow-level pre-authorisation). `WorkflowDefinition.role` is declared but never enforced. This is a design choice of this increment, documented in section G.

---

## G. Workflow-Level Authority Semantics

### WorkflowDefinition Has a `role` Field

```python
class WorkflowDefinition(BaseModel):
    role: list[str] | None = Field(default=None, description="Roles that can execute this workflow")
```
(`workflow_runner/models.py:39`)

### This Field Is Declared but Never Enforced

- `executor.execute_workflow` does not reference `workflow.role` (`workflow_runner/executor.py` — test `test_workflow_definition_has_role_field_not_enforced` confirms)
- `WorkflowExecutionAdapter.execute_workflow` does not check `role` (`workflow_runner/src/adapters/workflow_execution_adapter.py` — test confirms)
- `PaperclipOrganisationControlPlane.select_execution_path` checks `required_capability_ids`, not `workflow_role` (test `test_paperclip_select_execution_path_does_not_check_workflow_role` confirms)
- The OCP `select_execution_path` does not check `workflow.role` before selecting a workflow path — it only checks intent matching against workflow lookup (`organisation/src/organisation_control_plane.py:547-557`)

### The `role` Field's Semantic Purpose

The `role` field on `WorkflowDefinition` serves as **descriptive metadata** — it records which roles the workflow was designed for. It does not function as an authorisation control. No code path consults it before execution.

### Workflow-Level Authority Model

The existing architecture supports an **implicit** model: **a workflow authored by the organisation and selected by the OCP as a valid procedure for an intent constitutes the authority to execute its prescribed steps**. This model is:
- **Passive**: No enforcement mechanism exists
- **Implicit**: Not documented as a policy, derived from the structural separation
- **Declarative**: `WorkflowDefinition.role` records intended roles but does not gate execution

---

## H. Capability-Level Authority Semantics

### Explicit Authorisation Model

Capability execution uses an **explicit, enforced** authorisation model:

1. `CapabilityExecutionPort.execute(actor_context)` — actor context is a required parameter
2. `CapabilityExecutionAdapter._check_authorisation` — calls `ExecutionAuthorisationPort.is_authorised(actor_id, actor_type, capability_id)`
3. If not authorised → returns `ExecutionResult` with `telemetry: {"error": "execution_not_authorised"}`
4. `InvocationRecorder.record_invocation` is called at every return path — every capability execution attempt is recorded

### Key Difference

| Aspect | Workflow Execution | Capability Execution |
|--------|-------------------|---------------------|
| Actor context in contract | No | Yes (`actor_context`) |
| Authorisation check | None | `ExecutionAuthorisationPort.is_authorised` |
| Invocation recording | None | `InvocationRecorder.record_invocation` |
| Role field on definition | Declared, not enforced | N/A |
| Authorisation port wiring | Not wired | Wired at composition root |
| Evidence of execution | None | Invocation records |

---

## I. Skill/Tool Implications

### Skills (in workflow context)

- `Step.uses` references a **skill name**, not a `capability_id` (`workflow_runner/models.py:27`)
- `handle_skill_step` calls `compose_skill_prompt` which loads skill content from YAML via `_load_skill_content` — does NOT consult `CapabilityRegistry` (`test_test_composer_resolves_skill_name_from_yaml_not_capability_registry`)
- `handle_skill_step` does NOT call `record_invocation` or reference `InvocationRecorder` (`test_skill_handler_does_not_record_invocation`)
- Skills executed through workflows produce **no capability telemetry or evidence**

### Tools (in workflow context)

- `handle_tool_step(step, context)` — no actor context, no authorisation
- Tools are executed directly via the tool registry, not through capability deployment

### Implication

Skill and Tool execution within a workflow are **not** capability exercise. They do not cross the capability authorisation boundary. `CapabilityExecutionPort` is never invoked for workflow steps. This is the structural reason the bypass is valid — the workflow execution path operates on a different abstraction (skills/tools) than the capability execution path (capabilities).

---

## J. BAU Semantics

### Complete BAU Path

```
intent (ChatRequest with user_id)
  ↓ AssistantChatService.__call__
ProblemFrame + Intent
  ↓ SolutionSelectionPort.select_execution_path (via SolutionSelectionAdapter)
ExecutionPathResult.EXISTING_WORKFLOW (workflow=WorkflowDefinition)
  ↓ ChatService._execute_workflow_response
[actor identity dropped here — user_id not propagated]
WorkflowExecutionRequest(workflow_name, initial_context={})
  ↓ WorkflowExecutionPort.execute_workflow
WorkflowExecutionAdapter.execute_workflow(request)
  ↓ execute_workflow_from_file(workflow_path, initial_context, role_override)
executor.execute_workflow(workflow, workflow_path, ...)
  ↓ for each SKILL step: handle_skill_step(step, workflow, context, role_override)
  ↓ compose_skill_prompt(step, workflow, context, role_override)
  ↓ runtime_client.run(prompt) [LangGraph]
  ↓ StepResult
  ↓ for each TOOL step: handle_tool_step(step, context)
  ↓ for each WORKFLOW step: handle_workflow_step(step, context)
WorkflowExecutionResult(status, workflow_name, output, error)
  ↓ ChatResponse returned to user
```

### Where Authority Is Established

- **OCP selection** — the organisation determines that a workflow matches the intent. This is an organisational authority decision (intent → workflow discovery → selection).

### Where Authority Is Merely Assumed

- **Workflow execution** — no actor is identified, no authorisation check is performed, no evidence is recorded. The workflow is assumed to have authority because it was selected by the OCP.
- **Skill execution** — no actor, no capability authorisation, no invocation recording. Skills are prompt templates, not domain capabilities.
- **Tool execution** — no actor, no authorisation, no evidence.

### No Return to OCP

Workflow execution does not feed back to the OCP. `_execute_workflow_response` does not call `complete_work`, `fail_work`, `record_work_learning`, or `assess_work_outcome`. There is no evidence trail.

---

## K. Human vs Agent Execution Implications

### Human Execution

- A human initiates a chat request → `ChatRequest.user_id` is present
- OCP selects workflow → actor identity is dropped at `_execute_workflow_response`
- The workflow executes without any identification of who is running it
- This is consistent whether the human or an agent initiated the request

### Agent Execution

- An agent (e.g., assistant) can also trigger workflow execution (via MCP or scheduler)
- MCP `run_workflow` has no actor fields
- Scheduler `_fire` payload has no actor fields
- System-triggered execution has no actor identity at all

### Implication

The architecture makes **no distinction** between human and agent execution for workflow paths. Both follow the same path with the same absence of actor identity. This is consistent with ADR-037 (organisation does not store Person/Agent records). The workflow execution path operates independently of who initiated it.

---

## L. System-Triggered Execution Implications

### Scheduler

- `scheduler.schedule_workflow` creates a cron trigger that fires `_fire`
- `_fire` publishes a `WorkflowRequested` event with payload: `{event_id, workflow_name, initial_context, role_override, trigger: "scheduled", schedule_id, correlation_id}`
- **No actor fields** in the payload
- The bus consumer handles this like any other workflow request — no actor context

### MCP Server

- `mcp_server.py:run_workflow` takes `workflow_name` and optional parameters — no actor context
- Calls `execute_workflow_from_file` directly — no actor context

### Implication

System-triggered workflow execution (scheduled, MCP) has **zero actor identity**. This is acceptable because:
1. Scheduled workflows represent organisational procedures that run autonomously
2. MCP-triggered workflows are organisational tool calls
3. Neither requires actor-specific capability authorisation because they execute skills, not capabilities

---

## M. Paperclip Implications

### Paperclip Is Not a Workflow Execution Backend

- `PaperclipBackend.execute(work)` calls `trigger_execution(work.id, work.assignee_agent_id)` — this is the heartbeat API, not workflow execution (`workflow_runner/src/operations.py:100`)
- `PaperclipBackend` handles `Work` items, not `WorkflowDefinition`
- `PaperclipBackend` does NOT call `execute_workflow_from_file` or `execute_workflow` (confirmed by test `test_paperclip_trigger_execution_bypasses_workflow_executor`)

### Paperclip OCP select_execution_path

- Checks `required_capability_ids` for capability availability (`organisation_paperclip/src/organisation_paperclip.py`)
- Does NOT check `workflow.role` (confirmed by test `test_paperclip_select_execution_path_does_not_check_workflow_role`)
- Consistent with InMemory OCP — neither enforces workflow-level authorisation

### Implication

Paperclip is a Work execution backend. It does not execute workflows. Workflow execution is a separate path that Paperclip is not involved in. Paperclip's independence from workflow execution reinforces the structural separation.

---

## N. LangGraph/WorkflowRunner Implications

### LangGraph Runtime

- `runtime_client.run(prompt)` is called by `handle_skill_step` with only a prompt string (`workflow_runner/handlers/skill_handler.py:76`)
- The LangGraph runtime receives a composed prompt — no actor, no capability context, no authorisation
- LangGraph is an **execution implementation**, not an authority

### WorkflowRunner

- `executor.execute_workflow` walks workflow steps and dispatches to handlers — no actor, no authorisation, no evidence recording
- `execute_workflow_from_file` loads YAML and calls `execute_workflow` — no actor
- The WorkflowRunner is an **execution implementation**, not an authority

### Structural Separation Confirmed

- `WorkflowExecutionAdapter` does not reference `CapabilityExecutionPort` (`test_two_execution_paths_never_converge`)
- `executor.py` does not reference `CapabilityExecutionPort`, `CapabilityExecutionAdapter`, `ExecutionAuthorisationPort`, `is_authorised`, or `record_invocation`
- `CapabilityExecutionAdapter` does not reference `WorkflowExecutionPort`
- The two execution paths are **parallel and never converge**

---

## O. Whether WorkflowDefinition Remains Sufficient

### Current Fields

```python
class WorkflowDefinition(BaseModel):
    version: str = "1"
    name: str
    description: str | None = None
    kind: str = "workflow"
    role: list[str] | None = None          # Declarative, not enforced
    intent: dict[str, Any] | None = None
    inputs: list[str] | None = None
    outputs: list[str] | None = None
    steps: list[Step]
```

### Does It Need Organisational Ownership/Authority?

**No.** The workflow's authority derives from being authored and selected by the organisation through the OCP. The `WorkflowDefinition` itself does not need an explicit ownership field — the OCP's selection decision IS the organisational authority. Adding an `owner` or `authority` field would be redundant.

### Does It Need Capability References?

**No.** Workflow steps reference skills by name (`Step.uses`), not capabilities by ID. Adding capability references would conflate two distinct execution abstractions. Skill execution and capability execution are structurally separate paths.

### Does It Need Actor/Authorisation Information?

**No.** Adding actor or authorisation fields to `WorkflowDefinition` would incorrectly turn an execution definition into an organisational authority model. `WorkflowDefinition` describes WHAT to execute, not WHO may execute it. Actor/authorisation context belongs to the execution request, not the definition. The current architecture handles this correctly by not including actor fields in `WorkflowExecutionRequest` — there is no runtime actor to authorise.

### Would Adding Those Fields Incorrectly Turn It Into an Organisational Authority Model?

**Yes.** A `WorkflowDefinition` with `required_capability_ids`, `required_actor_ids`, or `authorisation_rules` would become an organisational authority model. That is a distinct concept (a workflow specification as a policy document) that the architecture does not need. `WorkflowDefinition` remains an **execution definition** — it tells the runner what to do, not who may do it.

### Verdict

`WorkflowDefinition` **remains sufficient**. It accurately represents what needs to be executed. The authority to execute it is established by the OCP selection, not by metadata on the definition.

---

## P. Whether a Workflow Entity Is Justified

### Analysis

A "Workflow entity" (distinct from `WorkflowDefinition`) would need to represent a genuinely distinct organisational concept. Consider what it would add:

- Organisational ownership metadata — already captured by OCP selection
- Approval/status lifecycle — already captured by Work items when capabilities are developed
- Capability references — not needed (workflows reference skills)
- Actor/authorisation information — not needed (no runtime actor)
- Version/approval tracking — not currently needed for BAU execution

### Verdict

**A Workflow entity is NOT justified.** No evidence demonstrates a distinct organisational concept that `WorkflowDefinition` cannot represent. Adding a Workflow entity would be creating a modelling layer that serves no architectural purpose. `WorkflowDefinition` is an execution boundary object — it is sufficient for its role.

---

## Q. Minimum Change Required, If Any

### Conclusion: No change required for Increment 36.

The investigation confirms that:

1. The current boundary is **correct** — workflow execution is structurally separate from capability execution
2. Workflow execution **can legitimately execute as BAU** without carrying runtime Actor/authorisation context
3. `WorkflowDefinition` **remains sufficient** as an execution definition
4. The bypass is **intentional** (composition root design) and **valid** (skills ≠ capabilities)
5. No enforcement mechanism is missing — the architecture intentionally does not enforce workflow-level authorisation because workflow execution operates on a different abstraction (skills) than capability execution

The `WorkflowDefinition.role` field is **declarative metadata**, not a missing enforcement mechanism. Its absence of enforcement is by design — the field records which roles a workflow is intended for, not which roles are authorised to execute it. Enforcing it would require an actor context that the workflow execution path deliberately does not carry.

**If a future increment determines that workflow-level authorisation enforcement is needed**, the smallest required change would be adding actor context to `WorkflowExecutionRequest` and wiring an authorisation check. But this is NOT required in Increment 36 — the current architecture is internally consistent and the boundary is correct.

---

## R. Architectural Tests Added

27 tests in `packages/organisation/tests/test_increment36_execution_authority.py`:

### A. Workflow Execution Call Graph (6 tests)
1. `test_workflow_execution_contract_has_no_actor_fields` — `WorkflowExecutionRequest` has no actor fields
2. `test_workflow_execution_adapter_init_has_no_authorisation_port` — `WorkflowExecutionAdapter.__init__` has no `authorisation_port`
3. `test_workflow_adapter_execute_workflow_has_no_actor_param` — `execute_workflow` has no actor context
4. `test_workflow_executor_signature_has_no_actor_or_recorder` — `executor.execute_workflow` has no actor/recorder
5. `test_skill_handler_has_no_actor_or_authorisation` — `handle_skill_step` has no actor
6. `test_workflow_execution_result_has_no_actor_provenance` — `WorkflowExecutionResult` has no actor fields

### B. Capability Execution Boundary (3 tests)
7. `test_capability_execution_port_protocol_carries_actor_context` — `CapabilityExecutionPort.execute` requires `actor_context`
8. `test_capability_execution_adapter_init_accepts_authorisation_port` — `CapabilityExecutionAdapter.__init__` accepts `authorisation_port`
9. `test_execution_authorisation_port_contract_checks_actor_and_capability` — `is_authorised` takes `actor_id`, `actor_type`, `capability_id`

### C. Workflow Steps Are Skills, Not Capabilities (4 tests)
10. `test_workflow_step_uses_is_skill_name_not_capability_id` — `Step.uses` is a skill name, no `capability_id` field
11. `test_composer_resolves_skill_name_from_yaml_not_capability_registry` — composer loads from YAML, not CapabilityRegistry
12. `test_workflow_executor_does_not_import_capability_execution_port` — executor has no capability/authorisation references
13. `test_skill_handler_does_not_record_invocation` — skill handler produces no invocation evidence

### D. Actor Identity Dropped at BAU Boundary (2 tests)
14. `test_assistant_drops_user_identity_when_executing_workflow` — `_execute_workflow_response` does not propagate user_id
15. `test_assistant_workflow_response_does_not_create_work` — workflow path does not create Work

### E. API-Level Actor Absence (2 tests)
16. `test_api_run_workflow_has_no_actor_context` — RunRequest has no actor fields
17. `test_api_execute_and_publish_has_no_actor` — `_execute_and_publish` has no actor context

### F. MCP and Scheduler Actor Absence (2 tests)
18. `test_mcp_run_workflow_has_no_actor` — MCP `run_workflow` has no actor context
19. `test_scheduler_workflow_payload_has_no_actor` — scheduler payload has no actor fields

### G. Workflow-Level Authorisation (2 tests)
20. `test_workflow_definition_has_role_field_not_enforced` — `role` field exists but never checked
21. `test_workflow_execution_result_has_no_actor_provenance` — result has no actor fields

### H. Workflow Bypasses Organisation Evidence Loop (2 tests)
22. `test_workflow_executor_does_not_record_work_outcome` — executor does not call complete_work/fail_work/record_work_learning
23. `test_workflow_execution_adapter_does_not_record_evidence` — adapter does not record evidence

### I. Composition Root Structural Separation (2 tests)
24. `test_composition_root_wires_authorisation_only_to_capability_path` — `authorisation_port` wired only to `CapabilityExecutionAdapter`
25. `test_workflow_execution_adapter_class_has_no_authorisation_attribute` — no hidden authorisation wiring

### J. Paperclip Backend Independence (2 tests)
26. `test_paperclip_trigger_execution_bypasses_workflow_executor` — Paperclip calls trigger_execution, not execute_workflow
27. `test_paperclip_select_execution_path_does_not_check_workflow_role` — Paperclip does not enforce workflow.role

### K. Path Separation (1 test)
28. `test_two_execution_paths_never_converge` — no code path bridges WorkflowExecutionPort and CapabilityExecutionPort

---

## S. Alternatives Explicitly Rejected

### Rejected: Adding Actor Context to WorkflowExecutionRequest
- Would require modifying the contract
- Would imply workflow execution needs an actor, which contradicts the finding that workflow execution has no runtime actor
- Would turn the execution request into an authorisation carrier, conflating execution with authority

### Rejected: Enforcing WorkflowDefinition.role
- Would require adding actor context to the execution path
- Would require an actor to be identified at execution time
- The current architecture has no mechanism to identify an actor for workflow execution (scheduled, MCP, chat all lack actor context at execution time)
- Would conflate the descriptive `role` field (which roles the workflow is for) with an enforcement mechanism (which roles are authorised)

### Rejected: Creating a Workflow Entity / WorkflowRegistry
- No evidence demonstrates a distinct organisational concept
- `WorkflowDefinition` already serves its purpose as an execution definition
- Would add complexity without resolving any identified gap

### Rejected: Creating a WorkflowAdoptionPort
- No evidence that workflow adoption needs a separate authorisation port
- Capability adoption is handled by CapabilityRegistry; workflow "adoption" is handled by OCP selection
- Would duplicate capability lifecycle patterns without justification

### Rejected: Bridging WorkflowExecutionPort and CapabilityExecutionPort
- Would collapse two structurally separate execution paths
- Would force skill execution through capability authorisation, which is architecturally incorrect (skills ≠ capabilities)
- Would create coupling between execution implementations that should be independent

### Rejected: Adding InvocationRecording to Workflow Execution
- Would create evidence for workflow executions that the organisation did not request
- Workflow execution is not Work execution — it does not fit the Work→evidence→outcome lifecycle
- Would conflate workflow execution telemetry with organisational evidence

### Rejected: Adding Authorisation to WorkflowExecutionAdapter
- No actor context exists at the execution boundary to authorise
- Would require identifying an actor at a point where the architecture deliberately does not identify one
- Would solve a problem that does not exist (skills, not capabilities, are executed)

---

## T. Remaining Architectural Gaps

### Gap 1: WorkflowDefinition.role Has No Enforcement Mechanism
- The `role` field is declared but never enforced
- This is not a defect — it is descriptive metadata — but there is no mechanism to gate workflow execution by role if such a mechanism is needed in the future
- **Resolution**: None required in this increment. If future requirements demand enforcement, adding actor context to the execution path would be required, but that is a separate increment.

### Gap 2: No Evidence Trail for Workflow Execution
- Workflow execution produces no evidence (`record_invocation`, `complete_work`, `fail_work`, `record_work_learning`)
- This is by design — workflow execution is not Work execution and does not feed the evidence lifecycle
- **Resolution**: None required. If workflow execution results need to be tracked, a separate evidence mechanism would be needed, but that is outside this increment's scope.

### Gap 3: No Explicit "Pre-Authorised Workflow" Policy
- The architecture implicitly treats workflows as pre-authorised but does not have an explicit policy document or enforcement
- The `role` field on `WorkflowDefinition` could serve this purpose if adopted as policy, but currently it is purely descriptive
- **Resolution**: None required in this increment. The architecture is internally consistent without an explicit policy.

---

## Final Conclusion

**"Can an existing WorkflowDefinition legitimately execute as BAU without carrying runtime Actor/authorisation context, or does the current execution path cross an organisational authority boundary that must be made explicit?"**

**Answer: An existing WorkflowDefinition can legitimately execute as BAU without carrying runtime Actor/authorisation context. The current execution path does NOT cross an organisational authority boundary that must be made explicit.**

### Justification

1. **Workflow execution and capability execution are structurally separate paths** confirmed by composition root wiring, contract design, and absence of bridging code.

2. **Workflow steps execute skills, not capabilities.** `StepType` has no CAPABILITY type. `Step.uses` references skill names loaded from YAML, not capability IDs from the registry. Skill execution via LangGraph is not capability exercise and does not require actor-specific authorisation.

3. **The workflow itself constitutes the authority.** A workflow selected by the OCP as a valid procedure for an intent represents an organisational decision that this procedure should execute. The authority to execute the workflow's prescribed steps derives from the workflow's existence and selection, not from runtime actor authorisation.

4. **No runtime actor exists in the workflow execution path.** Chat requests drop user_id at the assistant boundary. Scheduled and MCP triggers have no actor from the start. There is no actor to authorise.

5. **The composition root deliberately separates the paths.** `authorisation_port` is wired to `CapabilityExecutionAdapter` but not to `WorkflowExecutionAdapter`. This is not an oversight — it is an architectural decision confirmed by zero-argument instantiation of `WorkflowExecutionAdapter()`.

6. **`WorkflowDefinition.role` is descriptive metadata, not an enforcement mechanism.** Its purpose is to record which roles a workflow is intended for, not to gate execution. Adding enforcement would require actor context that the path deliberately does not carry.

### Architectural Decision: **A** — Current boundary is correct; workflow execution is legitimately pre-authorised and no change is required.

The smallest next increment is not required. The architecture is internally consistent. If future requirements demand explicit workflow-level authorisation enforcement, that would require adding actor context to the workflow execution path — but this is not required by current evidence.
