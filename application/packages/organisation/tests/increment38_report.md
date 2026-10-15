# Increment 38 — Workflow Execution → Organisational Evidence Boundary

## Investigate whether workflow execution produces organisational evidence that the current architecture needs to retain, or whether WorkflowState/runtime telemetry is intentionally the correct endpoint for BAU workflow execution.

---

## A. Workflow Execution Output / Call Graph

The complete trace from WorkflowDefinition to ChatResponse:

```
WorkflowDefinition (YAML loaded via load_workflow)
  ↓ execute_workflow_from_file(workflow_path, initial_context, role_override)
executor.execute_workflow(workflow, workflow_path, initial_context, ...)
  ↓ create_workflow_state(workflow_name, workflow_path, steps, initial_context)
WorkflowState (pending → running)
  ↓ for each SKILL step: handle_skill_step(step, workflow, context, role_override)
  ↓   compose_skill_prompt(step, workflow, context, role_override) [YAML skill loading]
  ↓   runtime_client.run(prompt) [LangGraph HTTP]
  ↓ for each TOOL step: handle_tool_step(step, context)
  ↓ for each WORKFLOW step: handle_workflow_step(step, context, search_paths)
  ↓ advance_step / fail_workflow as needed
  ↓ WorkflowState (completed|failed, step_results, context)
  ↓ bus.publish_workflow_completed / publish_workflow_failed
  ↓ executor returns result_summary dict:
    {workflow_id, workflow_name, status, step_results, context,
     error, total_steps, completed_steps}
  ↓ WorkflowExecutionAdapter.execute_workflow converts to:
    WorkflowExecutionResult(status, workflow_name, output, error)
  ↓ ChatService._execute_workflow_response
  ↓ ChatResponse(message, status, reasoning, telemetry, execution_outputs)
```

**What exists after execution:**
- `WorkflowExecutionResult(status, workflow_name, output, error)` — returned to chat layer
- `WorkflowState(workflow_id, workflow_name, workflow_path, status, step_results, context, error)` — persisted in workflow_runner DB
- Bus lifecycle events (`WorkflowCompleted`/`WorkflowFailed` with workflow_id, error, context) — published to workflow_runner event bus

**What is lost at the boundary (not returned to caller):**
- `WorkflowState` instance itself (including `workflow_id`, `workflow_path`, `log_path`)
- Structured access to `step_results` (individual step status, output, error, duration)
- Execution `context` (intermediate outputs between steps)
- `total_steps`, `completed_steps`
- Bus events (consumed only within workflow_runner)

**Key observation:** `WorkflowExecutionResult.output` IS the raw executor summary dict, which contains `step_results`, `context`, etc. — but as an unstructured `dict[str, Any]` with no organisational schema.

**Evidence:** `WorkflowExecutionRequest` has `workflow_name`, `initial_context`, `role_override` — no actor fields. `WorkflowExecutionResult` has `status`, `workflow_name`, `output`, `error` — no evidence fields. (`ai/src/chat.py:1598-1602`, `contracts/workflow_execution.py:6-21`, `workflow_runner/src/adapters/workflow_execution_adapter.py:27-56`)

---

## B. WorkflowState Telemetry

`WorkflowState` (`workflow_runner/models.py:75-86`) represents execution progress:

- `workflow_id`: unique run identifier (UUID)
- `workflow_name`: name of the workflow
- `workflow_path`: path to YAML file
- `status`: pending/running/completed/failed/paused/stopped/scheduled
- `current_step_index`: execution progress
- `steps`: list of Step objects
- `step_results`: list of dicts — step_name, status, output, error, duration
- `context`: dict — inputs, intermediate outputs
- `error`: error message if failed
- `log_path`: path to execution logs

**WorkflowState is execution state, not organisational state.** It tracks a single run of a WorkflowDefinition. Each execution creates a new WorkflowState instance. It has no reference to Work, no organisational accountability, no outcome tracking.

---

## C. WorkflowExecutionResult Semantics

`WorkflowExecutionResult` (`contracts/workflow_execution.py:14-20`):

- `status`: execution status (completed/failed/unknown)
- `workflow_name`: name of the workflow
- `output`: dict — raw executor summary (step_results, context, total_steps, completed_steps)
- `error`: error message if failed

**Semantics:** Execution result — what the workflow produced, whether it succeeded or failed. This is execution output, not organisational outcome. It has no fields for: work reference, capability reference, actor provenance, evidence, assessment, learning, or accountability.

---

## D. Existing Organisational Evidence Mechanisms

### Mechanism 1: CapabilityInvocationRecorder

```
CapabilityExecutionPort.execute(capability_id, context, actor_context)
  ↓ CapabilityExecutionAdapter.execute
  ↓   _check_authorisation: ExecutionAuthorisationPort.is_authorised(actor_id, actor_type, capability_id)
  ↓   execute_capability(capability, context, deployment) → ExecutionResult
  ↓   InvocationRecorder.record_invocation(capability_id, result, actor_context)
ConceptStore.record_invocation(capability_id, outcome)
  → Updates MaturationHistory on Capability concept
    (invocation_count, correction_count, last_invoked_at)
```

**What constitutes evidence:** Capability execution attempts recorded in ConceptStore. `InvocationRecorder` requires `capability_id` — workflow execution has no capability_id.

### Mechanism 2: WorkOutcomeAssessment + EIMS Learning

```
Operations.complete_work(work_id, result)
  → Work.status = COMPLETED, Work.outcome = result
  ↓ assess_work_outcome(work, execution_result)
  → criteria_met, criteria_failed, accepted, rationale
  ↓ record_work_learning(work, assessment, store) [only for project/initiative]
  → EnterpriseConcept(SOLVED_APPROACH) in ConceptStore
```

**What constitutes evidence:** Work outcomes assessed against acceptance criteria, recorded as SOLVED_APPROACH concepts in EIMS. `record_work_learning` explicitly excludes BAU work (`work_type not in ("project", "initiative")`). `assess_work_outcome` requires a Work item with `acceptance_criteria`.

---

## E. Capability Evidence Boundary

**What constitutes capability evidence:** Recorded execution attempts (via `InvocationRecorder`), capability maturation (`MaturationHistory`), proficiency records, and SOLVED_APPROACH concepts from accepted development work.

**Key distinction:** Capability evidence requires a `capability_id` — a named domain capability with an interface contract. Workflow execution operates on skills (prompt templates loaded from YAML), not capabilities. `Step.uses` is a skill name (`workflow_runner/models.py:27`), not a `capability_id`. There is no mechanism to translate workflow execution into capability evidence.

**The composition root confirms the boundary:** `CapabilityExecutionAdapter` receives `invocation_recorder=invocation_recorder` (`workflow_runner/src/composition.py:182-187`). `WorkflowExecutionAdapter` receives zero arguments (`workflow_runner/src/composition.py:240`).

---

## F. Work/Evidence Boundary

**What constitutes Work evidence:** Work outcomes (`Work.outcome`), acceptance criteria assessment (`assess_work_outcome`), EIMS learning (`record_work_learning`), capability development assessment (`assess_capability_development`).

**Key distinction:** Work evidence requires a Work item — an organisational unit with `accountable_role_id`, `acceptance_criteria`, `outcome`. Workflow execution does not create Work items. The two are alternatives, not a sequence: when a workflow exists, no Work is created; when a workflow doesn't exist, Work is created for the capability path.

---

## G. Telemetry vs Evidence Distinction

**Execution telemetry** (WorkflowState, StepResults, bus events):
- Purpose: Execution monitoring, runtime debugging, operational visibility
- Scope: workflow_runner package only
- Lifetime: Ephemeral (per-execution records in database)
- Consumer: workflow_runner infrastructure

**Organisational evidence** (InvocationRecorder, Work.outcome, EIMS concepts):
- Purpose: Organisational learning, capability promotion, knowledge retention
- Scope: Across organisation/capability concepts
- Lifetime: Durable (ConceptStore persistence)
- Consumer: Organisation, capability_registry, EIMS

**The distinction is structural:** Execution telemetry is consumed by execution infrastructure. Organisational evidence is consumed by organisational learning mechanisms. No existing mechanism bridges these two domains.

**Can existing mechanisms consume workflow telemetry?**

| Mechanism | Requires | Available in Workflow Execution | Compatible? |
|-----------|----------|-------------------------------|-------------|
| InvocationRecorder.record_invocation | capability_id, ExecutionResult | No capability_id, no ExecutionResult type | No |
| CapabilityOutcomeAssessor.assess | ExecutionResult (typed) | WorkflowExecutionResult (different type) | No |
| assess_work_outcome | Work with acceptance_criteria | No Work, no criteria | No |
| record_work_learning | Work (project/initiative only) | No Work created | No |

**No existing mechanism can legitimately consume workflow telemetry without a purpose-built adapter that serves no organisational function.**

---

## H. Workflow Success Evidence

**Does successful workflow execution produce organisational evidence?** No.

Analysis against the three criteria for organisational evidence:

1. **Tied to identifiable organisational entity?** No. `WorkflowExecutionResult` has no `work_id`, `capability_id`, `actor_id`, or `organisation_id`. `WorkflowState` has no Work reference.
2. **Serves organisational purpose?** No. Successful execution confirms the procedure ran. BAU procedures are expected to succeed — success is not informative.
3. **Produces durable knowledge?** No. Success is recorded in `WorkflowState` (ephemeral execution record) and bus events (workflow_runner-internal). It does not create Concepts, update Work.outcome, or modify any organisational entity.

**Semantic threshold:** Execution data becomes organisational knowledge when it:
- Is tied to an organisational entity (capability, work item, role)
- Serves an organisational purpose (learning, promotion, accountability)
- Produces durable knowledge (Concepts in EIMS, outcomes on Work)

Successful workflow execution meets none of these criteria. It remains execution telemetry.

---

## I. Workflow Failure Evidence

**Does workflow failure produce organisational evidence?** No.

Workflow failure is an execution result, not an organisational outcome. The distinction:

| Failure Type | Owner | Consequence |
|-------------|-------|-------------|
| Workflow step fails | workflow_runner | WorkflowState.status = failed, error recorded, result returned to chat |
| Capability execution fails | CapabilityExecutionAdapter | ExecutionResult with error, InvocationRecorder records attempt |
| Work execution fails | Operations → Organisation | Work.status = FAILED, outcome recorded |
| Workflow definition invalid | workflow_runner | WorkflowExecutionResult with error |
| Capability gap | OCP | NEW_CAPABILITY_REQUIRED → Work created |

**Workflow failure is an execution/outcome problem, not an authority problem.** It does not create Work, does not trigger capability assessment, does not feed EIMS. If a workflow consistently fails for an intent, the OCP will eventually stop selecting it for that intent — the organisational course correction happens at the discovery/selection layer, not at the execution layer.

**WorkflowState.step_results can contain failure details** (step_name, error, duration), but these remain execution telemetry within workflow_runner. No organisational mechanism consumes them.

---

## J. Human Correction Evidence

**Does the architecture have organisational representation of correction during workflow execution?** No.

**What exists:** `MaturationHistory.correction_count` exists in `ConceptStore` on Capability concepts. It is incremented when `InvocationRecorder.record_invocation` records a failed capability execution (`concepts.py:117-118`).

**What doesn't exist:** No correction tracking in `WorkflowState`, `WorkflowExecutionResult`, `StepResult`, `WorkflowDefinition`, or `WorkflowExecutionRequest`. No `correction_count` or equivalent field in any workflow-related model.

**Assessment:** Workflow execution has no organisational representation of correction. However, this is not a gap because:
1. Workflow execution has no human-in-the-loop mechanism — skills run via LangGraph, tools run via tool registry
2. No code path in workflow execution involves human intervention or correction
3. `correction_count` in `MaturationHistory` serves a different purpose (capability maturation statistics)

**Adding a correction model is not justified.** The architecture has no organisational need for correction tracking in workflow execution. If human intervention were introduced (e.g., human-in-the-loop for certain steps), a new increment would be needed to evaluate it.

---

## K. BAU → Learning Implications

**Should BAU workflow execution feed back into the learning loop?** No.

The learning loop:
```
UNCERTAIN → WORK → CAPABILITY → EVIDENCE → UNDERSTANDING → WORKFLOW DEFINITION → BAU → [no feedback]
```

**Justification:**

1. **The learning loop exists to convert execution outcomes into organisational knowledge.** BAU execution is the consumption of already-established knowledge — it doesn't produce new knowledge.

2. **`record_work_learning` explicitly excludes BAU:** `if work.work_type not in ("project", "initiative"): return None` (`organisation/src/outcome.py:83-84`). BAU is routine execution, not innovation that needs organisational memory.

3. **If BAU execution consistently fails,** the organisational course correction is at the OCP selection layer: the workflow won't be selected for that intent → the intent goes through NEW_CAPABILITY_REQUIRED → WORK → CAPABILITY path. The feedback loop exists at a different level.

4. **The workflow definition IS the knowledge artifact.** Once a workflow exists, the organisation has already learned the procedure. Executing it doesn't add to that knowledge.

**Smallest existing concept that could own a feedback signal** (if any): `WorkflowDefinition`. But this increment does not implement such a mechanism — the scope is investigation only.

---

## L. EIMS Implications

**Increment 37 established:** Workflow execution currently does not call `record_work_learning` or create EIMS learning records.

**This is intentionally correct.** `record_work_learning` has two guardrails:
1. `if not outcome_assessment.get("accepted"): return None` — only accepted work enters EIMS
2. `if work.work_type not in ("project", "initiative"): return None` — only project/initiative work enters EIMS, BAU is excluded

Even if workflow execution DID create Work items, and even if those Work items were accepted, BAU-type work would be excluded from EIMS. This is architectural: BAU execution is not project/initiative learning. EIMS records durable enterprise knowledge from innovation work, not from routine procedure execution.

**Should this remain outside the current architecture?** Yes. Workflow execution should remain outside EIMS because:
1. It doesn't produce durable enterprise knowledge
2. BAU is explicitly excluded from the learning loop
3. EIMS is for innovation tracking, not BAU monitoring

**Do not redesign EIMS.**

---

## M. Workflow Reuse Implications

**Does successful repeated execution change anything about WorkflowDefinition?** No.

Analysis:
- Each execution creates a new `WorkflowState` instance (expected)
- `WorkflowDefinition` is never modified by execution
- `WorkflowDefinition` has no mutable fields (status, execution_count, last_executed, etc.)
- No execution count, maturity, confidence, or usage tracking exists on the definition

**Should it change?** No. `WorkflowDefinition` is a static execution definition loaded from YAML. Its authority derives from being a written procedure, not from execution history. Execution history belongs in `WorkflowState` instances (ephemeral execution records).

**No workflow maturity, confidence scores, usage thresholds, automatic promotion, optimisation, revision, or registry is needed.** Repeated successful execution does not require any change to `WorkflowDefinition` or any other organisational concept.

---

## N. Whether Work Should Ever Be Created from Workflow Execution

**No.**

Work and workflow execution are alternatives, not a sequence:
- When a workflow exists: intent → OCP → EXISTING_WORKFLOW → execute workflow → result → no Work created
- When a workflow doesn't exist: intent → OCP → CAPABILITY_PATH → create Work → Worker executes → Work tracked

**Why Work should not be created from workflow execution:**
1. **Redundant tracking:** The workflow IS the BAU procedure. Creating Work for every execution would track what is already tracked by the procedure itself.
2. **Wrong abstraction:** Work represents organisational effort with accountability, criteria, and outcome. Workflow execution is a technical procedure with execution telemetry. They serve different purposes.
3. **No organisational need:** There is no evidence that the organisation needs to track workflow execution as Work. `WorkflowState` provides sufficient execution monitoring.
4. **Breaks the alternative relationship:** If workflow execution created Work, it would collapse the two BAU paths into one, losing the architectural distinction between procedural execution and tracked effort.

---

## O. Whether Existing Concepts Can Represent Workflow Evidence

**No.** Analysis of each existing concept:

| Concept | Could it represent workflow evidence? | Why not |
|---------|---------------------------------------|---------|
| `InvocationRecorder` | No | Requires `capability_id` — workflow steps use skills, not capabilities |
| `CapabilityOutcomeAssessor` | No | Requires `ExecutionResult` type — `WorkflowExecutionResult` is a different type |
| `assess_work_outcome` | No | Requires `Work` with `acceptance_criteria` — workflow execution has no Work |
| `record_work_learning` | No | Requires `Work` (project/initiative) — workflow execution creates no Work |
| `Work.outcome` | No | No Work item is created by workflow execution |
| `MaturationHistory` | No | Tracks capability invocation/correction counts — no workflow analogue exists |
| `ConceptStore` | No | Stores EnterpriseConcepts — workflow execution creates no concepts |

**No existing concept can represent workflow evidence** because all existing concepts are designed for organisational entities (capabilities, work items) and workflow execution operates on a different abstraction (procedural execution).

---

## P. Whether a New Concept/Boundary Is Required

**No.**

**Justification:**
1. No existing mechanism requires evidence from workflow execution.
2. No organisational entity needs to track workflow execution outcomes.
3. `WorkflowState` provides sufficient execution telemetry.
4. The architecture correctly separates execution telemetry from organisational evidence.
5. No gap has been identified that would be filled by a new concept.

**If a future increment determines that workflow-derived evidence is needed**, the smallest next increment would need to establish:
- What specific evidence is needed (failure patterns? success metrics? efficiency?)
- Which organisational entity should own it (WorkflowDefinition? a new concept?)
- What purpose it serves (learning? monitoring? accountability?)

That increment would not be this one — this increment's evidence shows no such requirement exists.

---

## Q. Minimum Architectural Change, If Any

**None required.**

**Conclusion: A** — Workflow execution telemetry is sufficient and no organisational evidence boundary is required yet.

**Justification:**
1. `WorkflowState` tracks execution progress (status, step_results, context, error) — sufficient for execution monitoring.
2. `WorkflowExecutionResult` returns execution output to the chat layer — sufficient for user-facing feedback.
3. Bus events provide workflow_runner-internal lifecycle notifications — sufficient for operational coordination.
4. No organisational mechanism needs workflow execution data.
5. The separation between execution telemetry and organisational evidence is correct and internally consistent.

---

## R. Architectural Tests Added

33 tests in `packages/organisation/tests/test_increment38_execution_evidence_boundary.py`:

### A. Workflow Execution Output (5 tests)
1. `test_workflow_execution_result_has_only_status_name_output_error` — WorkflowExecutionResult has exactly 4 fields
2. `test_workflow_execution_result_has_no_organisational_fields` — No evidence anchor fields
3. `test_workflow_execution_result_output_contains_execution_telemetry` — Output dict contains step_results, context
4. `test_workflow_execution_result_output_is_unstructured` — Output is plain dict, not typed evidence
5. `test_workflowstate_is_not_in_workflow_execution_result` — WorkflowState fields not in result

### B. What Is Lost at the Boundary (3 tests)
6. `test_workflow_execution_adapter_does_not_return_workflowstate` — Adapter returns WorkflowExecutionResult, not WorkflowState
7. `test_workflow_execution_result_has_no_step_results_typed_field` — No step_results as typed field
8. `test_workflow_execution_result_output_contains_execution_telemetry` — Telemetry is in unstructured output

### C. Comparison with Evidence Mechanisms (5 tests)
9. `test_invocation_recorder_requires_capability_id` — InvocationRecorder needs capability_id
10. `test_invocation_recorder_records_on_capability_concepts` — Records on Capability concepts in ConceptStore
11. `test_invocation_recorder_is_wired_only_to_capability_execution` — Not wired to WorkflowExecutionAdapter
12. `test_record_work_learning_requires_work` — Requires Work item
13. `test_assess_work_outcome_requires_work_with_acceptance_criteria` — Requires Work with criteria

### D. Telemetry vs Evidence Distinction (5 tests)
14. `test_workflow_state_step_results_are_execution_telemetry` — StepResults are execution data
15. `test_step_results_have_no_organisational_metadata` — No organisational fields
16. `test_workflow_state_has_no_work_reference` — No Work reference
17. `test_workflow_definition_has_no_evidence_fields` — No evidence fields
18. `test_record_work_learning_excludes_bau` — BAU explicitly excluded from EIMS

### E. Capability Outcome Assessor (2 tests)
19. `test_capability_outcome_assessor_requires_execution_result_type` — Different type from WorkflowExecutionResult
20. `test_capability_outcome_assessor_is_not_in_workflow_execution_path` — Not referenced in adapter/executor

### F. EIMS Boundary (3 tests)
21. `test_workflow_execution_does_not_call_record_work_learning` — No EIMS learning calls
22. `test_workflow_execution_does_not_call_complete_work` — No Work lifecycle calls (word boundary)
23. `test_workflow_execution_does_not_call_fail_work` — No Work failure calls (word boundary)

### G. Human Correction (3 tests)
24. `test_correction_count_exists_only_in_maturation_history` — In MaturationHistory only
25. `test_workflow_execution_has_no_correction_tracking` — No correction in workflow models
26. `test_capability_correction_and_workflow_correction_are_separate` — Completely separate concepts

### H. Workflow Reuse (1 test)
27. `test_workflow_definition_is_immutable_to_execution` — No mutable execution state

### I. Bus Events (2 tests)
28. `test_publish_workflow_completed_is_workflow_runner_internal` — Publish methods exist on EventBus
29. `test_no_organisational_consumer_of_workflow_lifecycle_events` — No org code references lifecycle events

### J. Architectural Decision (5 tests)
30. `test_workflow_execution_telemetry_is_sufficient_for_execution_monitoring` — Status, step_results, context, error sufficient
31. `test_no_existing_mechanism_requires_workflow_evidence` — Evidence chain operates on different entities
32. `test_workflow_execution_does_not_satisfy_evidence_criteria` — Fails all three evidence criteria
33. `test_workflow_execution_produces_no_organisational_evidence` — Complete path produces no evidence

---

## S. Alternatives Explicitly Rejected

### Rejected: Creating an Evidence Entity for Workflow Execution
- Constraints explicitly forbid creating Evidence entities
- Would require a generic abstraction that serves no purpose
- WorkflowState.step_results provides sufficient execution telemetry
- Evidence belongs to capability execution, not workflow execution

### Rejected: Feeding Workflow Results into Work.outcome
- Workflow execution does not create Work, so there is no Work.outcome to feed
- Would require routing workflow results to a non-existent Work item
- Would create a phantom Work just to hold workflow output — conceptually wrong

### Rejected: Creating a WorkflowRun/WorkflowInstance Entity
- WorkflowState already serves this purpose
- WorkflowState IS the per-execution record
- Adding a separate entity would duplicate WorkflowState with organisational metadata

### Rejected: Connecting WorkflowState to Work for Traceability
- No organisational need to track which workflow produced a Work result
- Would conflate execution telemetry with organisational effort tracking
- Different packages, no cross-references — intentionally separate

### Rejected: Adding InvocationRecording to Workflow Execution
- Would create evidence for workflow executions that the organisation did not request
- Workflow execution is not Work execution — does not fit the Work→evidence→outcome lifecycle
- Would conflate workflow execution telemetry with organisational evidence

### Rejected: Feeding Workflow Telemetry into CapabilityOutcomeAssessor
- CapabilityOutcomeAssessor requires typed ExecutionResult (outputs, artifacts, telemetry)
- WorkflowExecutionResult is a different type with different fields
- Would require type adaptation that serves no organisational purpose

### Rejected: Creating a Workflow Evidence Consumer
- No existing organisational mechanism consumes workflow telemetry
- Creating a consumer without a producer need adds complexity without value
- The architecture is correct without it

### Rejected: Automatically Recording Workflow Corrections
- No human-in-the-loop mechanism exists in workflow execution
- No code path involves human intervention or correction
- correction_count in MaturationHistory serves a different purpose (capability maturation)

---

## T. Remaining Architectural Gaps

### Gap 1: No Organisational Representation of Workflow Failure Patterns
- Workflow failures are recorded in WorkflowState but not escalated to organisational level
- This is correct — if a workflow consistently fails, the OCP stops selecting it
- No evidence supports the need for failure pattern tracking at the organisational level
- **Resolution:** None required. If workflow failure patterns become an organisational concern, a future increment would be needed.

### Gap 2: No Feedback from BAU Execution to WorkflowDefinition
- BAU execution does not modify, rate, or evolve the workflow definition
- This is correct — the workflow definition is a static procedure, not a learning entity
- No evidence supports the need for execution-driven workflow evolution
- **Resolution:** None required at this increment.

### Gap 3: No Correction Tracking in Workflow Execution
- Workflow execution has no mechanism to track human intervention or correction
- This is acceptable because no human-in-the-loop mechanism exists in workflow execution
- If such a mechanism is introduced in the future, correction tracking would need evaluation
- **Resolution:** None required. Introduction of human-in-the-loop is a separate increment.

---

## Final Question

**"Does execution of an established WorkflowDefinition produce organisational evidence that the current architecture needs to retain, or is WorkflowState/runtime telemetry intentionally the correct endpoint for BAU workflow execution at this stage?"**

**Answer:** WorkflowState/runtime telemetry is intentionally the correct endpoint for BAU workflow execution at this stage.

### Justification

1. **Workflow execution produces execution telemetry, not organisational evidence.** `WorkflowState` tracks status, step_results, context, and error — all execution-level data with no organisational schema or purpose.

2. **No existing mechanism requires workflow execution data.** The evidence chain (InvocationRecorder → ConceptStore, record_work_learning → EIMS, assess_work_outcome → Work.outcome) all operate on different entities (capabilities, work items). None reference workflow execution.

3. **Workflow execution does not satisfy the three criteria for organisational evidence:**
   - Not tied to an identifiable organisational entity (no work_id, capability_id, actor_id)
   - Does not serve an organisational purpose (learning, promotion, accountability)
   - Does not produce durable knowledge (no Concepts, no outcomes)

4. **The architecture correctly separates execution telemetry from organisational evidence.** `WorkflowState` is execution infrastructure. `WorkflowExecutionResult` is execution output. Neither belongs in the organisational evidence domain.

5. **BAU execution is the consumption of established knowledge, not the production of new knowledge.** The learning loop operates on Work items (via `record_work_learning`), and BAU work is explicitly excluded. Workflow execution doesn't create Work items — it's an alternative to Work creation.

6. **If workflow execution needed organisational evidence, the smallest next increment would need to establish what evidence is needed and which entity should own it.** This increment's evidence shows no such requirement exists.

### Architectural Decision: **A** — Workflow execution telemetry is sufficient; no organisational evidence boundary is required yet.

### If Future Evidence Becomes Required

The smallest next increment would need to determine:
- What specific organisational evidence is needed from workflow execution (failure patterns? efficiency metrics? usage statistics?)
- Which organisational entity should own that evidence (WorkflowDefinition? a new concept? something else?)
- What organisational purpose the evidence serves (learning? monitoring? accountability?)

Until such evidence exists, the current architecture is correct and internally consistent.

---

## Summary

| Aspect | Finding |
|--------|---------|
| Workflow execution output | WorkflowExecutionResult (status, workflow_name, output, error) + WorkflowState |
| Evidence boundary | No boundary required |
| Existing mechanisms compatible | No — all require different entities/types |
| Telemetry vs evidence | Explicitly separated — telemetry is in workflow_runner |
| BAU → learning | No feedback — BAU is excluded from learning loop |
| Failure handling | Execution failure only, no organisational consequence |
| Human correction | No representation — not needed, no mechanism exists |
| Workflow reuse | No changes to WorkflowDefinition — correct |
| Work creation from workflow | No — alternatives, not sequence |
| Decision | A — telemetry sufficient |
