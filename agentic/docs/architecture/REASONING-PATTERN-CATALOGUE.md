# Reasoning Pattern Catalogue

## Purpose

This specification defines the canonical reasoning patterns of the Enterprise Cognition system. Each pattern is a reusable prompt/config bundle that enables and disables framework "pathways". Patterns are the unit of composition for Sessions, analogous to design patterns in integration architecture.

## Design Constraints

- Pattern bundles are versioned (`semver`). A bundle id is `name@version`.
- Each pattern declares enabled pathways. Pathways are pluggable runtime targets.
- Pathways are toggled; a pattern may disable a pathway that conflicts with its governance rules.
- Pattern metadata is persisted in Postgres (via existing `db.py` infrastructure) as `SkillRecord` entries with `implementation` tier `distilled`. Persistence must be strict, not best-effort.
- Pattern composites are ordered. The Session Model defines the pipeline.
- No pattern may encode framework-specific types into Context or Session.

## Pattern Structure

```yaml
pattern:
  id: string            # e.g. investigation@1.0.0
  name: string          # e.g. investigation
  version: string       # semver
  description: string
  enabled_pathways: list[PathwayId]
  disabled_pathways: list[PathwayId]
  roles: list[string]
  governance_gates: list[GateSpec]
  inputs: list[string]
  outputs: list[string]
  composability:        # how this pattern chains with others
    - allowed_next: list[string]
    - terminal: bool
  prompt_template: string | null   # inline or reference to asset store
  config: map             # pathway-specific config (without framework types)
```

### GovernanceGateSpec (inline in pattern)

```yaml
gate:
  kind: enum [policy_check | human_approval | confidence_threshold | consensus | timeout]
  condition: string      # machine-readable rule reference
  on_fail: enum [stop | escalate | pause_for_input | retry]
  description: string
```

## Pathway Interface (Stable Abstraction Boundary)

Before any framework integration, the pathway interface is defined as a pure contract:

```yaml
PathwayResponse:
  status: enum [completed | approved | rejected | escalated | failed]
  outputs: map
  artifacts: list[string]
  telemetry: map

PathwayCallRequest:
  context: Context record
  participants: list[ParticipantRecord]
  prompt: string
  max_turns: int

PathwayCapabilities:
  supports_stateful: bool
  supports_concurrent_participants: bool
  supports_streaming: bool
  supports_interruption: bool
```

No framework concept (e.g. `StateGraph`, `Crew`, `Agent`, `Thread`) appears inside Context, Session, or Pattern. The boundary is one-direction: frameworks may adapt to the interface, but the interface never adapts to a framework.

## Canonical Pattern Catalogue

### 1. SOP Execution

Sequential, deterministic execution of a known procedure.

- enabled_pathways: [workflow-runner]
- disabled_pathways: [langgraph, crewai, maf]
- roles: [operator, reviewer]
- governance_gates:
  - kind: policy_check
    condition: mandatory_compliance_check
    on_fail: stop
  - kind: human_approval
    condition: irreversible_action
    on_fail: pause_for_input
- inputs: [procedure_id, parameters, context]
- outputs: [execution_log, outcome]
- composability: terminal true, allowed_next []
- Runtime today: Implemented via `execute_workflow_from_file` in `agentic/src/workflow-runner/executor.py`. Single-step sessions are today's workflow.

### 2. Investigation

Exploratory information gathering when a root cause is unknown.

- enabled_pathways: [workflow-runner, langgraph]
- disabled_pathways: [crewai, maf]
- roles: [investigator, analyst]
- governance_gates:
  - kind: timeout
    condition: max_investigation_time
    on_fail: escalate
  - kind: human_approval
    condition: system_changes_required
    on_fail: pause_for_input
- inputs: [incident_id, initial_hypothesis, data_sources]
- outputs: [findings, root_cause, recommendations]
- composability: terminal false, allowed_next [SOP Execution, Debrief]

### 3. Exploration

Generative ideation without commitment.

- enabled_pathways: [langgraph, crewai]
- disabled_pathways: [workflow-runner, maf]
- roles: [facilitator, brainstormer, critic]
- governance_gates:
  - kind: consensus
    condition: idea_convergence_threshold
    on_fail: extend_timebox
- inputs: [problem_statement, constraints, prior_ideas]
- outputs: [candidate_ideas, evaluation_matrix]
- composability: terminal false, allowed_next [Debate, Planning]

### 4. Brainstorm

Rapid divergent generation of options.

- enabled_pathways: [langgraph, crewai]
- disabled_pathways: [workflow-runner, maf]
- roles: [facilitator, brainstormer]
- governance_gates:
  - kind: timeout
    condition: brainstorm_duration
    on_fail: converge
- inputs: [seed_prompt, constraints]
- outputs: [idea_list, tagged_concepts]
- composability: terminal false, allowed_next [Critique, Planning]

### 5. Debate

Structured adversarial reasoning to stress-test options.

- enabled_pathways: [langgraph, crewai]
- disabled_pathways: [workflow-runner, maf]
- roles: [devils_advocate, proposer, moderator]
- governance_gates:
  - kind: confidence_threshold
    condition: debate_consensus_confidence > 0.8
    on_fail: continue_debate
  - kind: human_approval
    condition: high_stakes_decision
    on_fail: pause_for_input
- inputs: [propositions, evidence, criteria]
- outputs: [adjudication, winner_proposition, dissent_record]
- composability: terminal false, allowed_next [Consensus, Critique]

### 6. Consensus

Structured agreement-seeking across participants with defined authority model.

- enabled_pathways: [langgraph, crewai, human]
- disabled_pathways: [workflow-runner]
- roles: [facilitator, stakeholder, approver]
- governance_gates:
  - kind: consensus
    condition: authority_model_met
    on_fail: escalate
- inputs: [propositions, participant_definitions, authority_rules]
- outputs: [agreed_outcome, dissent_record, audit_trail]
- composability: terminal false, allowed_next [Planning, Verification]

### 7. Critique

Iterative refinement of an artifact by adversarial review.

- enabled_pathways: [langgraph, crewai]
- disabled_pathways: [workflow-runner, maf]
- roles: [critic, author]
- governance_gates:
  - kind: confidence_threshold
    condition: quality_score > 0.85
    on_fail: iterate_again
- inputs: [artifact, criteria, rubric]
- outputs: [refined_artifact, review_comments]
- composability: terminal false, allowed_next [Verification, Critique]

### 8. Reflection

Post-execution learning and playbook update.

- enabled_pathways: [workflow-runner, maf]
- disabled_pathways: [langgraph, crewai]
- roles: [learner, historian]
- governance_gates:
  - kind: policy_check
    condition: playbook_approval_policy
    on_fail: escalate
- inputs: [execution_log, outcome, comfort_zone]
- outputs: [lessons_learned, playbook_delta]
- composability: terminal true, allowed_next []
- Runtime today: Not yet implemented. Stub target via maf integration.

### 9. Research

Deep-dive knowledge gathering from enterprise assets and external sources.

- enabled_pathways: [langgraph, maf]
- disabled_pathways: [workflow-runner, crewai]
- roles: [researcher, librarian]
- governance_gates:
  - kind: timebox
    condition: research_window
    on_fail: escalate
- inputs: [question, sources, scope]
- outputs: [research_report, citations, gaps]
- composability: terminal false, allowed_next [Planning, Debate, Brainstorm]

### 10. Planning

Decomposition of a goal into executable steps.

- enabled_pathways: [workflow-runner, langgraph]
- disabled_pathways: [crewai, maf]
- roles: [planner, estimator]
- governance_gates:
  - kind: human_approval
    condition: plan_approved
    on_fail: revise_plan
- inputs: [goal, constraints, capabilities]
- outputs: [plan, step_list, risk_assessment]
- composability: terminal false, allowed_next [SOP Execution]

### 11. Verification

Executable validation of an outcome against acceptance criteria.

- enabled_pathways: [workflow-runner, maf]
- disabled_pathways: [langgraph, crewai]
- roles: [validator, auditor]
- governance_gates:
  - kind: consensus
    condition: all_criteria_met
    on_fail: reject
- inputs: [artifact, acceptance_criteria, test_results]
- outputs: [verification_report, pass_fail_status]
- composability: terminal false, allowed_next [SOP Execution, Reflection]

### 12. Human Approval

Explicit human-in-the-loop gate with documented rationale.

- enabled_pathways: [human, workflow-runner]
- disabled_pathways: [langgraph, crewai, maf]
- roles: [approver]
- governance_gates:
  - kind: human_approval
    condition: action_requires_human
    on_fail: stop
- inputs: [proposal, options, risk_statement]
- outputs: [approved_plan | rejected_plan, rationale]
- composability: terminal false, allowed_next []
- Runtime today: Implemented via `on_step_complete` callback in `executor.py`; handlers invoke external approval integrations.

### 13. Escalation

Route to higher authority or alternate capability when current context cannot proceed.

- enabled_pathways: [workflow-runner, human]
- disabled_pathways: [langgraph, crewai, maf]
- roles: [escalation_manager, approver]
- governance_gates:
  - kind: timeout
    condition: max_escalation_wait
    on_fail: notify_and_pause
- inputs: [blocker, attempted_actions, context]
- outputs: [routing_decision, new_owner, timebound_commitment]
- composability: terminal false, allowed_next []

### 14. Learning

Self-assessment and knowledge distillation from completed Sessions.

- enabled_pathways: [workflow-runner, maf]
- disabled_pathways: [langgraph, crewai]
- roles: [learner, historian]
- governance_gates:
  - kind: policy_check
    condition: playbook_approval_policy
    on_fail: escalate
- inputs: [session_log, outcome, pattern_usage_stats]
- outputs: [playbook_delta, pattern_bundle_update, lessons_learned]
- composability: terminal true, allowed_next []
- Runtime today: Not yet implemented. Stub target via maf integration.

## Diagram: Pattern to Pathway Matrix

| Pattern | workflow-runner | langgraph | crewai | maf | human |
|---------|:--------------:|:---------:|:------:|:---:|:-----:|
| SOP Execution       | primary   |          |        |     |       |
| Investigation       | primary   | alternate |        |     |       |
| Exploration         |           | primary  | alt.   |     |       |
| Brainstorm          |           | primary  | alt.   |     |       |
| Debate              |           | primary  | alt.   |     |       |
| Consensus           |           | primary  | alt.   |     | gate  |
| Critique            |           | primary  | alt.   |     |       |
| Reflection          | primary   |          |        |     |       |
| Research            |           |          |        | alt.|       |
| Planning            | primary   | alternate |        |     |       |
| Verification        | primary   |          |        | alt.|       |
| Human Approval      | alternate |          |        |     | primary|
| Escalation          | primary   |          |        |     | gate  |
| Learning            | primary   |          |        | alt.|       |

## Worked Examples

### Architecture Review Board Session

Worked trace (see also SESSION-MODEL.md and RUNTIME-MAPPING.md):

1. Context: Problem=design, ActivityPurpose=decide, DecisionContext.human_approval_required=true
2. Pattern Sequence: Debate@1.0.0 → Consensus@1.0.0 → Human Approval@1.0.0
3. Pathways toggled: Debate/Consensus enable langgraph; Human Approval switches to human gateway; all other pathways disabled.
4. Roles injected: moderator, proposer, approver.
5. Executed today: Debate and Consensus run via langgraph (stub target). Human Approval runs via workflow-runner callback (implemented). SOP can wrap the whole pipeline as a single sequential session if langgraph is unavailable.

### Incident Response Session

1. Context: Problem=incident, ActivityPurpose=execute, DecisionContext.human_approval_required=true (for irreversible changes)
2. Pattern Sequence: Investigation@1.0.0 → SOP Execution@1.0.0 → Human Approval@1.0.0 → Verification@1.0.0
3. Pathways toggled: Investigation enables langgraph Research; SOP Execution enables workflow-runner; Human Approval switches to human; Verification enables maf (future).
4. Roles injected: investigator, operator, approver, validator.
5. Executed today: Investigation + SOP Execution + Human Approval run via workflow-runner today. Verification and Reflection stubs exist as unimplemented pathways.

## Versioning Rule

Pattern bundles follow `semver`:
- Major: governance gate structure change or pathway interface breaking change.
- Minor: new gate type, new composability rule.
- Patch: prompt template or config correction.

A `SkillRecord` entry with `implementation: distilled` stores the pattern bundle metadata. Pattern bundle metadata persistence must be strict — `_save_manifest` in `registry.py` must raise on write failure rather than pass, so pattern metadata is not silently lost.

## Traceability to Working Principles

| Principle | Pattern Catalogue Contract |
|-----------|-----------------------------|
| 1. Recognition before reasoning | Context → Pattern mapping table |
| 4. Context determines behaviour | Enabled_pathways per pattern |
| 5. Reasoning patterns are composable | Composability rules |
| 7. Frameworks are runtimes, not architecture | Stable PathwayInterface boundary |
| 8. Convert reasoning to deterministic execution | SOP is terminal pattern |
| 10. Stable abstractions | PathwayInterface has zero framework types |
