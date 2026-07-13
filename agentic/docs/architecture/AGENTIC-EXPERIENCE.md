# Agentic Experience

## Purpose

This specification defines how individual agents — whether AI workers or human contributors — develop, carry, and share specialised knowledge and experience. It treats each participant as a distinct professional whose personal research stores, reading history, and learned preferences shape how they perform tasks. This is not a “single RAG for everyone” model. It is a model of a collection of individuals whose combined expertise constitutes the enterprise’s cognitive capacity.

## Why This Exists

Standardisation improves predictability, quality, and speed. But the participants who outperform the system are those who notice where the system is wrong, who discover shortcuts, who remember failures that were never documented, and who cultivate deep intuition in a narrow domain. If the enterprise erases individual experience in favour of a single canonical source, it loses the very thing that drives breakthrough improvement.

Agentic Experience is the architectural commitment to both:
- the standardised, repeatable execution described in the other Enterprise Cognition specs, and
- the idiosyncratic, valuable, individual knowledge that pushes the envelope.

## Working Principle Alignment

| Principle | Agentic Experience Contract |
|-----------|-----------------------------|
| 2. Reason only when uncertainty exists | An agent’s personal research store is searched first before triggering expensive enterprise reasoning. |
| 3. Enterprise assets are first-class | Individual knowledge is captured as an enterprise asset at session boundaries. |
| 4. Context determines behaviour | An agent’s biography — what they have read, done, and learned — is part of their operating context. |
| 5. Reasoning patterns are composable | Individual and enterprise assets are composed into a single prompt bundle. |
| 6. Sessions define interaction rules | Session creation time is when individual experience can be selectively included or excluded. |
| 8. Continuously convert reasoning into deterministic execution | Personal discoveries that prove reliable are promoted to playbooks and SOPs. |
| 9. Learning updates enterprise assets, not individual agents | Individual stores are transient; enterprise stores are durable. |
| 10. Preserve architectural freedom | Agent identity and knowledge store are abstracted behind a stable interface. |

## Core Concept: Agent as a Person

Every participant in a Session — human or AI — is modelled as an *Agent Persona*. A persona is not a fixed role. It is a first-class record describing:

- capabilities and skill tiers
- active focus areas
- reading/research history
- known failures and avoidances
- personal prompt fragments and shortcuts
- trust relationships with other personas

A persona is to an agent what a CV and personal notebook are to a person: it explains *why* this participant behaves the way they do when asked to perform a task.

```yaml
AgentPersona:
  id: string
  name: string
  kind: enum [human | ai]
  description: string
  capabilities: list[CapabilityRecord]
  focus_areas: list[string]
  research_store: ResearchStoreRef
  biography:
    reading_history: list[ReadingRecord]
    failure_memory: list[FailureRecord]
    success_patterns: list[PatternRef]
    trusted_sources: list[SourceRef]
  prompt_overrides: map
  social_graph: list[AgentRef]
  status: enum [active | away | retired]
```

## Research Store

Each persona owns a *Research Store*. The store is partitioned by privacy scope:

- `private`: notes, half-formed ideas, readings, failures the agent has not chosen to publish.
- `team_shared`: research the agent has explicitly published to their immediate team or capability.
- `enterprise_shared`: research approved for enterprise-wide retrieval.

```yaml
ResearchStoreRef:
  persona_id: string
  scope: enum [private | team_shared | enterprise_shared]
  storage_backend: enum [postgres | qdrant | repo_markdown | local_file]
  index_policy: string
  retention_policy: string
```

A human researcher (or an authorised AI curator) can read across stores, cross-reference private and enterprise material, and propagate insights upward. The researcher persona is therefore a *meta-participant*: they observe, annotate, and update, but do not themselves execute business steps.

```yaml
ResearcherAccess:
  mode: enum [read | annotate | publish | admin]
  scope_filter: ScopeQuery
  persona_subset: list[string]
  justification: string
  audit: bool
```

Researcher access is governed by existing enterprise policy mechanisms. Any cross-persona read or write is recorded in the enterprise event log.

## Composition: Personal + Enterprise at Prompt Time

When a persona is selected for a Session step, the Composer (see `agentic/src/workflow-runner/composer.py`) assembles the prompt from layers in this order:

1. Enterprise shared assets (policies, standards, ADRs, playbooks).
2. Session-scoped context (workflow outputs, prior step results, ContextRecord).
3. Persona biography (focus areas, known failures, trusted sources, prompt overrides).
4. Session instructions (pattern-specific prompt template, role override).

The ordering matters. Enterprise structure and governance are non-negotiable; they sit at the foundation. The persona layer sits on top and modifies *how* the work is approached, not *what* must be achieved.

This is how a senior architect and a junior architect can both execute the same Debate pattern, but produce materially different reasoning because their personal stores differ. The enterprise does not want to collapse that difference into a single averaged output.

## Specialisation vs Generalisation

Not every agent needs a deep research store. The platform supports tiered experience:

- `foundational`: agent operates strictly from enterprise assets and session context. No personal store.
- `developing`: agent has a private research store; contributions are not yet published.
- `specialist`: agent has a peer-reviewed or curator-approved body of personal knowledge that augments enterprise assets.
- `reviewer`: agent is authorised to read and annotate across other personas’ stores.

Specialists are the primary source of “pushing the envelope.” A specialist’s personal store may contain:
- prior experiments that succeeded where the playbook failed
- heuristics that have not yet been distilled into an SOP
- scenario-specific prompts that outperform generic templates
- readings from outside the enterprise that challenge assumptions

General agents (foundational agents, routine SOP executors) should not be penalised for lacking depth. The point of the model is to *encourage* depth where it is valuable, not to mandate it everywhere.

## Individuality in a Standardised System

The enterprise benefits from standardised execution in exactly the cases where standardisation is correct. Agentic Experience does not weaken standardisation. It adds two mechanisms that make standardisation honest:

1. **Why did we follow the playbook?** — Because the agent’s personal store contained no contrary evidence and no superior shortcut.
2. **Who found the better way?** — The agent whose research store contains the new approach. Their personal success pattern will, through the Learning lifecycle, eventually become the new enterprise standard.

Standardisation is not the suppression of individuality. It is the reliable channel through which individual insight becomes collective capability.

## the Edge: Innovation Through Individual Experience

The greatest gains usually come from agents who *push the envelope*. This is not accidental. It is a direct consequence of:

- a large population of agents with diverse personal stores, and
- a system that reads those stores at execution time, and
- a learning pipeline that elevates successful individual behaviour to enterprise assets.

An agent who pushes the envelope is one whose personal research store contains:
- prior failures the rest of the team never investigated
- external readings the enterprise has not yet ingested
- experiments run outside the approved SOP boundary

The architecture must *protect* this behaviour, not flatten it. Mechanisms that encourage envelope-pushing:

- `sandbox_policy` on a persona: agent may deviate from SOP when in Investigation or Exploration patterns.
- `experiment_log` attached to a session: deviations and outcomes are recorded and feed the Learning lifecycle.
- `distillation_promotion`: successful experimental behaviour is offered back to the enterprise as a playbook or SOP delta.

## Cross-Store Research: The Meta-View

A researcher persona is a first-class participant with read-access across the organisation’s research landscape. Their value is synthesis.

The researcher can:

- spot that three specialists have independently observed the same failure mode in different contexts
- identify that a single trusted source is cited across multiple personas’ success patterns
- surface a pattern that no individual realised they were part of

This synthesis produces new enterprise assets: cross-cutting ADRs, updated risk registers, revised policy guidance.

```yaml
ResearcherView:
  persona_subset: list[string]
  focus_areas: list[string]
  temporal_window: TimeWindow
  output:
    - cross_reference_map
    - anomaly_report
    - promoted_playbook
    - deprecated_pattern_alert
```

## Privacy and Ownership

- Private research remains owned by the originating persona until explicitly published.
- Enterprise-shared research becomes an enterprise asset under existing governance.
- Team-shared research is subject to team governance.
- Resignation, role change, or persona retirement triggers a downstream policy: private material is archived, team material is reviewed by peers, enterprise material is retained.
- Researcher access does not grant edit rights to private stores without explicit authorisation.

## Cross-References

- **ENTERPRISE-CONTEXT-MODEL.md** — Defines `ContextRecord` and the context-to-pattern mapping. Context fields determine which agents participate, which research stores are consulted, and which patterns are proposed.
- **REASONING-PATTERN-CATALOGUE.md** — Defines the pattern bundles that Composer uses at prompt assembly time. Each pattern declares participants, roles, and governance gates.
- **SESSION-MODEL.md** — Defines `Session`, `PatternStep`, and `ParticipantRecord`. Session creation is when individual experience is selectively included or excluded.
- **PATTERN-RECOGNITION-ASSIMILATION.md** — Defines how Enterprise Cognition detects, classifies, and proposes patterns at three abstraction levels (direct reuse, adaptation, metaphorical transfer). The researcher persona's cross-store access is formalised here.
- **RUNTIME-MAPPING.md** — Defines LangGraph as the sole execution substrate. Framework competitive analysis (CrewAI, MAF/AutoGen, Google ADK, OpenAI Agents SDK, Smolagents) feeds the pattern library. See the framework deep-dive for absorption decisions.
- **SCENARIO-VALIDATION.md** — Validates Incident Response and Architecture Review Board scenarios across all five specs.

## Scenario Validation

### Scenario A: Payment Gateway Incident Response

Context: `problem=incident`, `activity_purpose=investigate → execute`, `environment=ai_assisted`, `human_approval_required=true`.

Pattern Recognition: `(incident, investigate)` maps to `investigation@1.0.0` at Level 1 (direct match). `(incident, execute)` maps to `sop_execution@1.0.0`. Pattern pipeline: `Investigation → SOP Execution → Human Approval → Verification`. Context sensitivity rules trigger timebox expiry at 3600s and mandatory human approval gates.

Agentic Experience: The investigator AI's personal research store is consulted first. If a prior similar incident record exists, it surfaces as a candidate pattern adjustment (Level 1 retrieval). If it is a novel failure mode, the pattern recommendation triggers the Learning lifecycle for Research -> Investigation synthesis.

Runtime: `investigation` runs on `langgraph` substrate with conditional branching. `sop_execution` runs on `workflow-runner` as a deterministic sequence. `human_approval` runs as a LangGraph interrupt node. `verification` runs on `workflow-runner` as primary; `maf` is unregistered and degraded fallback is logged.

### Scenario B: Architecture Review Board — Internal Platform Decision

Context: `problem=design`, `activity_purpose=decide`, `environment=humans_and_agents`, `authority_model=consensus`, `human_approval_required=true`.

Pattern Recognition: `(design, decide)` maps to `debate@1.0.0` → `consensus@1.0.0` → `human_approval@1.0.0`. If prior ARB debates exist for similar decisions, Level 2 adaptation proposes a variant including those prior propositions as evidence. The researcher persona cross-references prior debates across the enterprise store to populate Debate inputs.

Agentic Experience: The `chair_human` acts as the researcher persona. They access cross-store view (`ResearcherView`) to surface prior ARB decisions and dissent records from the `critic_ai` agent's personal store. The dissociation between researcher observation and business execution is maintained: the chair/judge shapes the session but does not execute business steps.

Runtime: `debate` runs as a cyclic LangGraph graph with proposer → critic → moderator nodes. `consensus` runs as a LangGraph node evaluating participant declarations via the `consensus` governance gate. `human_approval` interrupts for the chair's formal sign-off. All steps run on the `langgraph` substrate; no separate `crewai` substrate is used.

### Deterministic Framing: Escalation Pattern for Novel Scenarios

For both scenarios, an escalation safety net is built in. If a pattern step exceeds `max_turns` or a gate condition cannot be evaluated (e.g., confidence threshold never reached), the step escalates to the `Escalation` pattern, which routes to the human authority for manual resolution. Over time, repeated escalations of the same pattern-state combination produce an exception record that the Learning lifecycle converts into a new governance rule, reducing future escalation frequency.

For agentic systems, the deterministic framing requirement means that every Reasoning pattern must map to a deterministic policy that can be explained and executed without the agent's full reasoning state. This is ensured by:
- Pattern bundles carrying `implementation: distilled` metadata once validated.
- `Registry._save_manifest` strict persistence ensuring bundle metadata is never silently lost.
- Pattern bundles declaring `terminating` nodes with explicit output schema, so the Session composer can infer session termination without re-running the graph.

Versioning: Pattern bundles follow `semver`. Major: governance gate structure or pathway interface changes. Minor: new gate types, composability rules, or role definitions. Patch: prompt templates or config corrections.

## Traceability to Working Principles

| Principle | Agentic Experience Contract |
|-----------|-----------------------------|
| 1. Recognition before reasoning | Agent biography is consulted first to see if prior knowledge resolves the task before enterprise reasoning begins. |
| 2. Reason only when uncertainty exists | Personal + enterprise stores are read; reasoning is invoked only when both are inconclusive. |
| 3. Enterprise assets are first-class | Personal discoveries that prove stable are promoted to enterprise stores. |
| 4. Context determines behaviour | Agent biography is part of the execution context. |
| 5. Reasoning patterns are composable | Personal and enterprise knowledge layers are composed at prompt time. |
| 6. Sessions define interaction rules | Session creation selects which personas participate and which scope of their research store is visible. |
| 7. Frameworks are runtimes, not architecture | Agent identity and knowledge are framework-agnostic; they are data passed into any runtime. |
| 8. Convert reasoning to deterministic execution | Successful individual behaviour feeds playbooks and SOPs via the Learning lifecycle. |
| 9. Learning updates enterprise assets, not individual agents | Individual stores are transient; promotions become enterprise standard. |
| 10. Preserve architectural freedom | Agent Persona and Research Store are stable schemas with zero framework coupling. |
