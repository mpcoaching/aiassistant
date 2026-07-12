# Session Model

## Purpose

This specification defines the first-class Session execution construct. A Session is a bounded execution of a pipeline of pattern steps. Existing `WorkflowState` is Session with a single step enabling only the `workflow-runner` pathway — so the Session Model is a strict extension, not a fork.

## Design Constraints

- Session must be embeddable inside current `WorkflowDefinition` YAML without changing the existing schema headroom. A new top-level `session:` block in YAML is the compatibility shim.
- `role_override` is currently passed top-down but not persisted. The Recognition layer needs a way to inject selected roles into the session context before executor dispatch. Role injection happens at Session creation, not at step execution.
- Session state is stored in `WorkflowState` via `db.py`. Session-specific fields are stored in `WorkflowState.context`; execution state (step index, results) stays in top-level `WorkflowState` fields.
- No framework-specific fields in Session or Context (Principle 10).
- Governance gates must be enforceable before and after each step execution via executor callbacks (`on_step_start`, `on_step_complete` in `agentic/src/workflow-runner/executor.py`).

## Typed Session Schema

```yaml
Session:
  id: string                     # uuid, unique per session
  created_at: datetime
  created_by: string             # user / system / recognition
  status: enum [draft | running | paused | completed | failed | stopped | escalated]
  purpose: string
  agenda: SummaryBlock           # human-readable agenda
  context: ContextRecord         # see ENTERPRISE-CONTEXT-MODEL.md
  pipeline: list[PatternStep]    # ordered execution plan
  participants: list[ParticipantRecord]
  policies: list[string]         # references to enterprise policy assets
  memory_scope:
    included_assets: list[string]
    excluded_assets: list[string]
    retention_policy: string     # e.g. session_lifetime, permanent
  success_criteria: list[Criterion]
  outputs: list[Artifact]        # populated during/after execution
  escalation_rules: list[EscalationRule]
  timebox:
    start: datetime
    end: datetime
  governance:
    gates: list[GateInstance]    # derived from patterns in pipeline
    approval_trail: list[ApprovalRecord]
  distillation_hook:
    enabled: bool
    target_store: enum [postgres | qdrant | repo_markdown]
```

### ContextRecord (embedded in Session)

```yaml
ContextRecord:
  problem_context: ProblemContext
  environment_context: EnvironmentContext
  information_context: InformationContext
  activity_purpose: ActivityPurpose
  decision_context: DecisionContext
  inferred_vs_declared: map   # field-level provenance: inferred | declared
```

### PatternStep (one step in the pipeline)

```yaml
PatternStep:
  id: string
  pattern_id: string           # e.g. investigation@1.0.0
  role_override: string | null # injected at session creation; top-down for steps
  participants: list[string]   # selected from session.participants
  config: map                  # inline pattern config
  enabled_pathways: list[PathwayId]
  disabled_pathways: list[PathwayId]
  status: enum [pending | running | completed | failed | skipped | paused]
```

### ParticipantRecord

```yaml
ParticipantRecord:
  id: string
  kind: enum [human | agent | api | mcp | system]
  role: string
  capabilities: list[string]
  agent_ref: string | null     # e.g. langgraph-agent-id, crewai-agent-id
```

### Criterion

```yaml
Criterion:
  id: string
  description: string
  metric: string
  threshold: string
  evidence_required: bool
```

### Artifact

```yaml
Artifact:
  id: string
  type: enum [document | decision | code | log | insight | playbook]
  content_ref: string          # path or id in enterprise asset store
  generated_by: string         # pattern step id
  version: string
```

### EscalationRule

```yaml
EscalationRule:
  trigger: string
  target: string
  timebox_seconds: int
  on_fail: enum [stop | notify | route]
```

### GateInstance (runtime)

```yaml
GateInstance:
  gate_id: string
  kind: GateKind
  status: enum [pending | passed | failed | skipped]
  record: string | null        # approval record id or policy check result
```

### ApprovalRecord

```yaml
ApprovalRecord:
  approver_id: string
  approved_at: datetime
  rationale: string
  decision: enum [approved | rejected | deferred]
```

## Lifecycle

```
create → run → (pause/resume) → (escalate) → close → distill
```

1. **create**: Recognition proposes context + pipeline. User edits. System injects roles. Persists `WorkflowState` with pipeline steps as workflow steps plus session metadata in `context`.
2. **run**: Executor dispatches each `PatternStep`. Between steps, governance gates are enforced via `on_step_complete` callback. Step results are recorded in `WorkflowState.step_results`.
3. **pause/resume**: User or gate request pauses execution. State transitions to `paused`. Resume restarts from current step.
4. **escalate**: When an `EscalationRule` triggers or a gate fails with `escalate`, the Session transitions to `escalated`. A new Session may be created by the escalation target.
5. **close**: All steps completed or final failure. `WorkflowState` transitions to `completed` or `failed`.
6. **distill**: If `distillation_hook.enabled` is true, the completed Session feeds the Learning lifecycle (see RUNTIME-MAPPING.md).

## Mapping to Existing Workflow-Runner State

`WorkflowState` fields used:

| `WorkflowState` field | Session Model use |
|-----------------------|-------------------|
| `workflow_id` | `session.id` |
| `workflow_name` | session purpose slug |
| `workflow_path` | path to YAML or bundle that created the session |
| `status` | session status (same enum) |
| `current_step_index` | pipeline step index |
| `steps` | `pipeline` steps normalised to `Step` objects |
| `step_results` | per-pattern-step results |
| `context` | context record + session metadata embedded here during transition |
| `error` | session error |
| `log_path` | session log |

Session-specific fields live in `WorkflowState.context` as structured sub-objects:
- `Session` block
- `ContextRecord`
- `Policies`
- `Participants`
- `DistillationHook`

Single-step Session = today's Workflow:

```yaml
workflow:
  name: incident-response
  kind: workflow
  role: [operator]
  intent:
    problem: incident
    activity_purpose: execute
  session:
    purpose: Restore service for incident INC-2024-001
    pipeline:
      - pattern_id: sop.execution@1.0.0
        enabled_pathways: [workflow-runner]
    timebox:
      end: "2024-01-01T03:00:00Z"
  steps:
    - type: skill
      name: incident-sop
      uses: incident-sop
```

This YAML is backward-compatible with `loader.py`: the `session:` block is parsed but optional, and `intent` is consumed by Recognition.

## Backward Compatibility

Existing `WorkflowDefinition` (from `agentic/src/workflow-runner/models.py:32`) gained a new optional field:

```python
class WorkflowDefinition(BaseModel):
    ...
    session: Optional[SessionBlock] = None  # new
```

`SessionBlock` does not affect existing validation because:
- It is optional.
- Existing `load_workflow` in `loader.py` ignores unknown keys only if they are not passed; a strict schema update adds `session` as a known optional field.
- `intent` already exists; no schema change there.

## Governance Enforceability

Governance gates are enforced at these points:

- **Pre-step**: `on_step_start` callback inspects the current `PatternStep`. If its enabled_pathways do not include the runtime that is about to execute, the step is skipped or routed to an alternate pathway.
- **Post-step**: `on_step_complete` callback evaluates gates for the just-completed step. Failure routes to `StopStep`, `EscalateStep`, or `PauseStep`.
- **Session creation**: Role injection and context override are validated against user permissions.

## Distillation Hook

When a Session closes with status `completed` and `distillation_hook.enabled` is true:

1. Execution log (`step_results`, `context`, pipeline definition) is packaged.
2. A `Learning@1.0.0` pattern pipeline is auto-created and scheduled.
3. The Learning pipeline outputs are stored in the enterprise asset store (postgres / qdrant / repo markdown).
4. If the Session produced a new deterministic artifact (e.g. a playbook that passes Verification), a new `SkillRecord` with `implementation: distilled` is created in `registry.py` and its manifest is persisted strictly (write failure raises, not ignored).

## Worked Examples

### Architecture Review Board Session

```yaml
session:
  id: arb-2024-001
  purpose: Validate architecture proposal for federated event mesh
  context:
    problem_context:
      class: design
      sub_category: architecture_review
    activity_purpose: decide
    decision_context:
      confidence_required: high
      authority_model: consensus
      reversibility: semi_reversible
      mandatory_policy_checks: [adr_required, security_review]
      human_approval_required: true
      cost_vs_quality: balanced
  pipeline:
    - pattern_id: debate@1.0.0
      role_override: moderator
      enabled_pathways: [langgraph]
    - pattern_id: consensus@1.0.0
      role_override: facilitator
      enabled_pathways: [langgraph]
    - pattern_id: human.approval@1.0.0
      role_override: approver
      enabled_pathways: [human]
  participants:
    - id: cto
      kind: human
      role: approver
    - id: architect-01
      kind: agent
      role: proposer
      agent_ref: langgraph/architect-01
  timebox:
    end: "2024-01-01T17:00:00Z"
```

Runtime today:
- Debate + Consensus = stub langgraph targets (unimplemented).
- Human Approval = executed via existing `on_step_complete` callback in `executor.py`.
- A degraded fallback wraps the entire pipeline as a single SOP-equivalent workflow using only `workflow-runner` when langgraph is unavailable.

### Incident Response Session

```yaml
session:
  id: incr-2024-001
  purpose: Restore service for payment gateway outage
  context:
    problem_context:
      class: incident
      sub_category: payment_gateway
    activity_purpose: execute
    decision_context:
      confidence_required: high
      reversibility: irreversible
      mandatory_policy_checks: [rollback_plan, customer_communication]
      human_approval_required: true
      timebox_seconds: 1800
  pipeline:
    - pattern_id: investigation@1.0.0
      enabled_pathways: [workflow-runner, langgraph]
    - pattern_id: sop.execution@1.0.0
      enabled_pathways: [workflow-runner]
    - pattern_id: human.approval@1.0.0
      enabled_pathways: [human]
    - pattern_id: verification@1.0.0
      enabled_pathways: [maf]
  participants:
    - id: ops-eng-01
      kind: human
      role: operator
    - id: se-oncall
      kind: human
      role: approver
```

Runtime today:
- Investigation + SOP Execution + Human Approval = fully implemented via workflow-runner.
- Verification = stub target (unimplemented; degraded to skipped with gate pass-through).

## Traceability to Working Principles

| Principle | Session Model Contract |
|-----------|------------------------|
| 2. Reason only when uncertainty exists | Pipeline is bypassed entirely if Recognition finds a known SOP — no session created |
| 4. Context determines behaviour | ContextRecord drives pattern selection and pathway activation |
| 5. Reasoning patterns are composable | Ordered PatternStep pipeline |
| 6. Sessions define interaction rules | Participants, policies, timebox, gates all inside session spec |
| 7. Frameworks are runtimes, not architecture | Session has no framework types; pathways are abstract IDs |
| 8. Convert reasoning to deterministic execution | Completed sessions feed distillation pipeline that produces SOPs |
| 9. Learning updates enterprise assets | Distillation hook writes to postgres / qdrant / repo |
| 10. Stable abstractions | Session maps onto WorkflowState, not a new persistence layer |
