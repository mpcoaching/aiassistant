# Enterprise Context Model

## Purpose

This specification defines the canonical representations for the contexts that determine how work is executed in the Enterprise Cognition system. Context is not prose — it is structured data that can be classified, passed to prompt composers, and stored in session state.

## Design Constraints

- Context data lives in `WorkflowState.context` (see `agentic/src/workflow-runner/db.py`) and is persisted via Postgres with `.wf/` file fallback.
- Context must be mergeable: user declaration overrides automated classification at every field.
- Context tuples are used by the pattern catalogue to select candidate patterns. Context does not contain policy decisions; those live in Session.
- No Context field may reference a specific framework concept (Principle 10).

## Typed Context Schemas

### ProblemContext

Identifies the nature of the work.

```yaml
problem_context:
  class: enum
  values:
    - routine_operation
    - incident
    - innovation
    - investigation
    - design
    - decision
    - optimisation
    - compliance
    - learning
    - unknown
  free_text_fields:
    - sub_category
    - urgency
    - description
  source_of_record: enterprise taxonomy + user declaration
```

### EnvironmentContext

Identifies who and what can participate.

```yaml
environment_context:
  class: enum
  values:
    - humans_only
    - ai_assisted
    - api_automated
    - workflow_driven
    - mcp_interop
    - multi_system
  free_text_fields:
    - participants
    - constraints
    - integrations
  source_of_record: session configuration + user overrides
```

### InformationContext

Identifies the information assets required.

```yaml
information_context:
  class: enum
  values:
    - internal_only
    - customer_data
    - regulated
    - historic_decisions
    - enterprise_knowledge
    - external_systems
  free_text_fields:
    - required_assets
    - classifications
    - data_sensitivity
  source_of_record: session configuration + policy engine
```

### ActivityPurpose

Identifies the style of interaction.

```yaml
activity_purpose:
  class: enum
  values:
    - explore
    - decide
    - approve
    - validate
    - review
    - execute
    - learn
    - optimise
    - monitor
    - investigate
  free_text_fields:
    - intent
    - expected_interaction_shape
  source_of_record: session configuration + workflow intent
```

### DecisionContext

Identifies governance requirements for any decision-producing step.

```yaml
decision_context:
  class: object
  fields:
    confidence_required: enum [low | medium | high | exhaustive]
    authority_model: enum [single_authority | consensus | democratic]
    reversibility: enum [reversible | semi_reversible | irreversible]
    mandatory_policy_checks: list[string]
    human_approval_required: bool
    timebox_seconds: int
    cost_vs_quality: enum [fast_cheap | balanced | thorough]
```

## Representation Rules

1. Every field has a structured enum value for classification; free_text_fields are not used for matching — they are carried in session state for display and prompt composition only.
2. Context records are serialised to JSON and stored in `WorkflowState.context`.
3. A Context record is a flat map with no embedded framework objects.

## Merging: Declaration vs Inferred

Classification into Context is produced by three sources, merged in this order:

1. Workflow-level intent metadata (from `WorkflowDefinition.intent`)
2. Automated classification result (LLM or rules-based)
3. User declaration at Session creation (highest precedence)

`user_declaration` wins at the field level. If the user specifies `activity_purpose: investigate`, that value is stored even if the workflow intent says `execute`.

## Context-to-Pattern Mapping Table

The following table maps the orthogonal tuple (Problem, ActivityPurpose) to candidate patterns. The tuples are used by Recognition to propose a pattern bundle; user declaration can override the proposal.

| Problem | Activity Purpose | Candidate Pattern |
|---------|------------------|-------------------|
| innovation | explore | Brainstorm |
| incident | execute | SOP |
| incident | investigate | Investigation |
| design | decide | Debate |
| decision | decide | Consensus |
| compliance | validate | Checklist (Verification) |
| learning | optimise | Reflection |
| unknown | investigate | Investigation |
| routine_operation | execute | SOP |
| innovation | decide | Debate |
| compliance | investigate | Investigation |

Multiple candidates are possible for a single tuple. Recognition returns a ranked list of candidates. Session creation selects the ordered pipeline. The existing `intent` field on `WorkflowDefinition` may map to a single pattern pipeline today. A future `patterns` list in `WorkflowDefinition` will list multiple patterns in order.

## Open: Maturity Metrics

Metric definitions for maturity are deferred to a follow-up session. Preliminary candidates: skill reuse rate, human intervention rate, mean time to resolution, reasoning step cost.

## Traceability to Working Principles

| Principle | Context Model Contract |
|-----------|------------------------|
| 1. Recognition before reasoning | Context tuple is the input to recognition classification |
| 4. Context determines behaviour | Context fields map to pattern/pathway choices |
| 10. Stable abstractions | Context schema has zero framework concepts |
