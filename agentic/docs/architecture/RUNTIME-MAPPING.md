# Runtime Mapping

## Purpose

This specification defines how framework-specific runtimes map to the stable Enterprise Cognition abstractions. It documents the current runtime map, the boundary that prevents framework concepts from leaking into Context/Session/Pattern models, and the Learning & Knowledge Lifecycle that converts reasoning outcomes into permanent enterprise assets.

## Design Constraints

- Context, Session, and Pattern schemas contain zero framework concepts (Principle 10). The stable abstraction boundary is one-direction.
- Frameworks adapt to the pathway interface; the interface never adapts to a framework.
- Runtime changes must not alter Context or Session schemas. A new pathway is registered as an implementation of the interface, not a new schema field.
- All runtime state remains in `WorkflowState` via `db.py` (`agentic/src/workflow-runner/db.py`). No framework has direct schema access.

## Stable Abstraction Boundary

```yaml
# Boundary contract (Framework -> Ecosystem)

PathwayRuntime:
  id: string                  # e.g. workflow-runner | langgraph | crewai | maf | human
  supports_stateful: bool
  supports_concurrent_participants: bool
  supports_streaming: bool
  supports_interruption: bool

# Call contract (Ecosystem -> Framework)
PathwayCallRequest:
  session_id: string
  pattern_step: PatternStep
  context: ContextRecord
  participants: list[ParticipantRecord]
  prompt: string
  max_turns: int
  timeout_seconds: int

# Response contract (Framework -> Ecosystem)
PathwayResponse:
  status: enum [completed | approved | rejected | escalated | failed]
  outputs: map
  artifacts: list[string]     # references to enterprise asset store
  telemetry: map              # duration, token_cost, provider_id
```

## Honest Current-State Constraint

Real engine today: `agentic/src/workflow-runner` (loader → executor → registry → composer). `docker-compose.yml` runs it as `workflow-engine`.

- `agents/langgraph/` contains only `.gitkeep`. Any LangGraph pathway is entirely unimplemented; the container starts from scratch.
- CrewAI / Microsoft Agent Framework (MAF) are **not present** in this repo. They are documented as mapping targets/stubs.
- `workflow-runner` is the only implemented pathway.
- `human` approval gateway is partially implemented via executor callbacks and external handlers.

## Pathway → Framework Mapping Table

| Pathway | Framework | Topology Fit | Implemented |
|---------|-----------|-------------|-------------|
| workflow-runner | Python executor + handlers | Deterministic SOP | **Yes** |
| langgraph | LangGraph | Stateful graph / meeting | Target (stub) |
| crewai | CrewAI | Collaborative role-play | Target (unimplemented) |
| maf | Microsoft Agent Framework | Enterprise integration | Target (unimplemented) |
| human | External approval gateway | Human-in-the-loop | **Yes** (partial) |

### Topology rationale

- **langgraph**: Best fit for patterns where state must be maintained across multiple turns (Debate, Consensus, Investigation). The graph maps naturally to the ordered `PatternStep` pipeline while allowing conditional loops within a single pattern.
- **crewai**: Best fit for patterns where participants have defined role behaviours and delegation (Brainstorm, Critique, Exploration). The crew model is a multi-agent collaboration topology.
- **maf**: Best fit for enterprise integration patterns (Research, Verification, Learning) where tools and APIs must be orchestrated with enterprise security and identity.
- **workflow-runner**: Best fit for deterministic, linear SOPs and policy-gated sequential patterns (SOP Execution, Planning, Escalation). The existing executor is the lowest friction target.
- **human**: Not a framework but a pathway that interrupts execution for human decision.

## Pathway Registration

A pathway is registered as a pluggable strategy:

```python
# Conceptual adapter entrypoint (schema, not runtime code)

class PathwayAdapter:
    def call(self, request: PathwayCallRequest) -> PathwayResponse: ...
    def supports(self, pattern: PatternStep) -> bool: ...
```

The executor (in `executor.py`) maintains a registry of adapters keyed by pathway ID. At session creation, each `PatternStep.enabled_pathways` list is matched to registered adapters. If no adapter is registered for a listed pathway, the runtime falls back to `workflow-runner` and logs a degraded-pathway event.

## Executor Degraded Routing

Existing `execute_workflow` in `agentic/src/workflow-runner/executor.py` dispatches by `StepType` inside a sequential loop. For Session support:

1. The Session pipeline is flattened to a list of Step objects. Each `PatternStep` becomes a `Step` with a synthetic `type: pattern` and metadata in `with_`.
2. If a `PatternStep` lists a pathway without a registered adapter, the executor runs the step as a `SKILL` or `TOOL` equivalent (degraded mode).
3. `on_step_start` and `on_step_complete` callbacks are the governance enforcement points. Gates are checked between steps.

## Human Approval Runtime

Today, human approval is implemented via:
- `on_step_complete` callback in `executor.py` invoked after steps marked as requiring approval.
- External handlers (see `handlers/` directory) perform the approval request via MCP server or external API.
- The callback blocks local execution and resumes from `pause` when approved.

Future: a dedicated `human` pathway adapter that manages the full approval lifecycle (notify → wait → resume/escalate) independent of executor loop.

## Registry Strictness

Pattern bundles are stored in the registry as `SkillRecord` with `implementation: distilled`. Today, `_save_manifest` in `agentic/src/workflow-runner/registry.py:198-205` silently ignores OSError on write failure. For pattern bundle metadata — which encodes enabled/disabled pathway configuration — this is unacceptable. Pattern metadata persistence must be strict: write failure raises, and the caller decides retry policy.

## Learning & Knowledge Lifecycle

Novel → reasoning → playbook → SOP → deterministic workflow → habit

1. **Novel**: Session runs with high-reasoning patterns (Investigation, Exploration, Debate).
2. **Reasoning**: Pattern steps execute; telemetry and outputs captured in `WorkflowState`.
3. **Playbook**: If the Session closes successfully and `distillation_hook.enabled` is true, the Learning pipeline analyses step outputs and produces a playbook delta.
4. **SOP**: If the same pattern sequence is executed repeatedly with stable outcomes, the Learning pipeline proposes a deterministic SOP bundle (`implementation: distilled` skill record).
5. **Deterministic workflow**: SOPs are registered in `registry.py` as workflows that `workflow-runner` can execute without oversight.
6. **Habit**: Outstanding SOPs are eventually migrated to native handlers (`handle_skill_step`, `handle_tool_step`) for zero-LLM execution.

## Enterprise Asset Store

Recommended store for authored enterprise assets:

| Asset Type | Store | Rationale |
|-----------|-------|-----------|
| Policy metadata, ADRs, playbook structures, session summaries | Postgres (existing `db.py`) | Structured, queryable |
| Semantic memory, prior outputs, embeddings | Qdrant | Existing container in platform |
| Authored docs, policy documents, design guidelines | Repo markdown | Versioned, reviewable |
| Patterns (prompt bundles) | Postgres + repo | Metadata in postgres; templates in repo |

This is the recommended configuration. Open to user override.

## Worked Trace: Incident Response

1. **Context** (ENTERPRISE-CONTEXT-MODEL): Problem = incident, ActivityPurpose = execute, Environment = ai_assisted, DecisionContext = human_approval_required, timebox.
2. **Pattern** (REASONING-PATTERN-CATALOGUE): Pipeline = Investigation → SOP Execution → Human Approval → Verification.
3. **Session** (SESSION-MODEL): Pipeline `PatternStep`s inject roles (investigator, operator, approver, validator). All steps have enabled_pathways set; Verification lists `maf` (unimplemented today → falls back to skipped).
4. **Runtime** (this doc):
   - Investigation runs via `workflow-runner` (primary target).
   - SOP Execution runs via `workflow-runner` executor loop.
   - Human Approval routes to the `human` pathway adapter (implemented via callback).
   - Verification falls back to `workflow-runner` degraded step because no `maf` adapter is registered; gate passes with a logging event.

## Worked Trace: Architecture Review Board

1. **Context**: Problem = design, ActivityPurpose = decide, DecisionContext = consensus + human_approval, Environment = humans_and_agents.
2. **Pattern**: Pipeline = Debate → Consensus → Human Approval.
3. **Session**: `moderator`, `proposer`, `approver` roles injected. `langgraph` pathways enabled for Debate and Consensus; `human` enabled for approval.
4. **Runtime**:
   - Debate: langgraph pathway adapter not registered today → degraded to SOP-equivalent skill invocations via `executor.py`.
   - Consensus: same degraded fallback.
   - Human Approval: `human` pathway adapter invoked via existing callback.

## Traceability to Working Principles

| Principle | Runtime Mapping Contract |
|-----------|--------------------------|
| 7. Frameworks are runtimes, not architecture | Frameworks are pluggable adapters to the pathway interface |
| 10. Preserve architectural freedom | Context/Session schemas have zero framework concepts |
