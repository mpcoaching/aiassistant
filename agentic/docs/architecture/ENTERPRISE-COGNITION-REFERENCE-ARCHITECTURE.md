# Enterprise Cognition Reference Architecture

> **Canonical source of truth.** This document consolidates the Enterprise Cognition design into one reference architecture. Every reasoning-core artifact links back to it. It is the locked anchor described in `.kilo/plans/1784184802270-agentic-cognition-centric-architecture-review.md` (Phase A). Companion artifacts (`ENTERPRISE-COGNITION.md`, `ENTERPRISE-CONTEXT-MODEL.md`, `REASONING-PATTERN-CATALOGUE.md`, `PATTERN-RECOGNITION-ASSIMILATION.md`, `SESSION-MODEL.md`, `RUNTIME-MAPPING.md`, `SCENARIO-VALIDATION.md`) remain valid and are now **mapped** to — not renamed for — this model.

## 0. Status & scope

- **Status:** Implementation-ready (architecture-alignment effort; documentation only, no source-code changes).
- **Audience:** architecture owner (Martin), Kilo Code / implementation agents.
- **Scope:** the *reasoning core* — Intent, Context, Strategy Selection, Reasoning Strategy, Reasoning Patterns, Enterprise Concepts / Knowledge, Session, Pattern Runtime, Capability, Learning Loop.
- **Map, don't rename:** existing implementation vocabulary (agent, workflow, tool, skill) is preserved. This doc introduces the cognition layer *above* it; artifacts add an alignment section rather than editing their bodies.

## 1a. Service vs Capability vs Workflow (terminology that drives AI design choices)

These three terms share **one execution substrate** (Strategy Selection → Pattern Runtime → Session). They differ only in *persistence posture* and *standing contract*. The model keeps both words precisely so the designing AI picks the right shape:

| Term | What it is | Owns durable state? | Standing API contract? | Built via |
|---|---|---|---|---|
| **Capability** | The durable, discoverable, governed noun in the registry (`kind=tool\|skill`). The *unit of invocation*. | May (a Service) or may not (a pure tool) | Yes — invoked via the internal Agent Bus / REST API | Same reasoning/planning pipeline as workflows (see §10a) |
| **Service** | A **Capability** whose implementation owns durable entity state (Work Session, Task, Lead Profile) and exposes a standing contract others depend on. | **Yes** | **Yes** | Service Authoring → Capability Registry |
| **Workflow / Session** | One **transient** execution of a Pattern pipeline that *invokes* Capabilities. | No (only its log) | No (composed on demand for one Intent) | Assistant Reasoning Service |

**Invocation seam (the single clean boundary):** every Capability is called through the **internal agentic API** — Agent Bus (Tier 3, Request-Reply) or in-process (Tier 2). A Capability's implementation behind that API may be a compiled module, a skill, *or a Session (workflow) exposed behind the API*. "Workflow calling workflow" is therefore just a Capability invocation of a `workflow`-implemented Capability — one mechanism, no second runtime.

**When the designing AI chooses one over the other:**
- Need a **repeatable, depended-upon operation with owned data** (e.g. "track tasks", "enrich a lead") → build a **Service** (a Capability with durable state + standing contract).
- Need a **one-off or ad-hoc composition** for a single Intent, with no durable asset others will reuse → run a **Session (workflow)** directly.
- Either way, the *creation* of the Capability/Service reuses the **same planning/reasoning pipeline** as running a workflow (§10a). The only added building blocks a Service needs beyond a workflow are **durable state ownership + a standing API contract**, already covered by `Workflow_Engine` + `Capability_Registry_Service` + `Event_Bus`.

This collapses the historical overlap (integration-platform "workflow-with-an-API = service") into one rule: **a Service is a Capability; a workflow is a transient run that calls Capabilities.**

## 1. Vocabulary mapping (used by every artifact's alignment section)

| Cognition model | Existing implementation term |
|---|---|
| Intent (origin-agnostic) | user request / scheduled job / bus event / alert |
| Problem Frame | resolved workflow context |
| Reasoning Strategy | (new — no prior term) |
| Reasoning Pattern | agent behaviour / role configuration |
| Enterprise Concept | stored definition / record |
| Concept Payload | Concept of kind=`solved_approach` |
| Capability | tool / skill (registry entry) |
| Knowledge (epistemic graph) | `KnowledgeChunkDiscovered` event + vector store |
| Session | workflow instance |
| Pattern Runtime | LangGraph runtime / workflow-runner |
| Learning Loop | pattern recognition & assimilation |

## 2. Conceptual architecture (the §13 diagram, verbatim)

The stable conceptual model, top to bottom. Everything below is derived from this chain:

```
Intent
  → Context
    → Problem Frame
      → Strategy Selection
        → Reasoning Strategy
          → Reasoning Patterns
            → Enterprise Concepts / Knowledge
              → Session
                → Pattern Runtime
                  → Capability
                    → Learning Loop
```

Plain-language reading:

1. **Intent** — an origin-agnostic stimulus enters the system (user request, scheduled job, bus event, alert). The system does not yet know *what* to do; it only knows *that* something arrived.
2. **Context** — the arriving intent is classified into orthogonal context dimensions (problem, environment, information, activity purpose, decision). See `ENTERPRISE-CONTEXT-MODEL.md`.
3. **Problem Frame** — the resolved, structured context that frames the problem. A Problem Frame = a fully resolved workflow context.
4. **Strategy Selection** — a first-class capability that maps a Problem Frame to a **Reasoning Strategy**. Its v1 seed is the existing Context→Pattern mapping table (see §6); it is evolvable into a learned selector.
5. **Reasoning Strategy** — the *level above* patterns. A Strategy is a named posture (e.g. *recognise-and-reuse*, *investigate-then-decide*, *deliberate-to-consensus*) that decides *how* reasoning is approached. Reasoning Patterns implement a Strategy.
6. **Reasoning Patterns** — composable, versioned behaviour bundles (`REASONING-PATTERN-CATALOGUE.md`). Patterns are *one level below* Strategy.
7. **Enterprise Concepts / Knowledge** — the enduring assets of the enterprise (decisions, playbooks, concepts, the epistemic Knowledge graph). Concepts are the central noun; a **Concept Payload** is one record *kind* (`kind=solved_approach`).
8. **Session** — a bounded execution of a pattern pipeline (a workflow instance). See `SESSION-MODEL.md`.
9. **Pattern Runtime** — the replaceable execution substrate. LangGraph is one adapter; the `workflow-runner` is another. See `RUNTIME-MAPPING.md`.
10. **Capability** — a tool / skill registry entry that a pattern step or session invokes. See `ENTERPRISE-CONTEXT-MODEL.md` and the Capability Registry mapping.
11. **Learning Loop** — pattern recognition & assimilation that converts reasoning into deterministic execution and updates Enterprise Concepts / Knowledge. See `PATTERN-RECOGNITION-ASSIMILATION.md`.

## 3. Working principles (first principles)

1. Recognition before reasoning.
2. Reason only when uncertainty exists.
3. Enterprise assets are first-class.
4. Context determines behaviour.
5. Reasoning patterns are composable.
6. Sessions define interaction rules.
7. Frameworks are runtimes, not architecture.
8. Continuously convert reasoning into deterministic execution.
9. Learning updates enterprise assets, not individual agents.
10. Preserve architectural freedom through stable abstractions rather than framework-specific concepts.

## 4. Enterprise Cognition — first principles (from `ENTERPRISE-COGNITION.md`)

The architecture begins with the nature of the problem, not with agents, workflows, graphs, or frameworks. Frameworks are implementation details. The objective is to model how an enterprise *thinks, learns, standardises, and executes*. Humans, AI agents, workflows, and services are transient participants that transform information; the enduring assets belong to the enterprise.

### 4.1 Enterprise assets

Information, taxonomy, policies, standards, decisions, ADRs, playbooks, processes, capabilities, contracts, systems, metrics, responsibilities. Agents are transient; knowledge remains with the enterprise.

### 4.2 Recognition before reasoning

```
Request → Recognise the problem
        → Have we solved this before?
            → Yes  → execute the known process
            → Similar → adapt an existing playbook
            → Novel → enter exploration
```

Reasoning is expensive and is reserved for uncertainty.

### 4.3 Capability

Capabilities describe *what the business does*. They are classification constructs and do not "think". People and AI execute work to realise capabilities. A Capability is a single record *kind* in the Enterprise Concept type system (`kind=tool|skill`).

### 4.4 Learning lifecycle

```
Novel Task → Heavy reasoning → Successful approach → Playbook → SOP → Deterministic workflow → Habit
```

As maturity increases, reasoning decreases.

## 5. Context model (kept as the Context spec — `ENTERPRISE-CONTEXT-MODEL.md`)

Context is structured, classifiable data — not prose. Five orthogonal dimensions:

- **Problem Context** — `routine_operation | incident | innovation | investigation | design | decision | optimisation | compliance | learning | unknown`
- **Environment Context** — `humans_only | ai_assisted | api_automated | workflow_driven | mcp_interop | multi_system`
- **Information Context** — `internal_only | customer_data | regulated | historic_decisions | enterprise_knowledge | external_systems`
- **Activity Purpose** — `explore | decide | approve | validate | review | execute | learn | optimise | monitor | investigate`
- **Decision Context** — `confidence_required | authority_model | reversibility | mandatory_policy_checks | human_approval_required | timebox_seconds | cost_vs_quality`

Context is mergeable: user declaration overrides automated classification at the field level. No Context field may reference a framework concept (Principle 10). Full schemas: `ENTERPRISE-CONTEXT-MODEL.md`.

## 6. Strategy Selection (new — first-class capability)

**Intent.** Strategy Selection replaces the static Context→Pattern mapping table as the *v1 seed* of a first-class capability. It takes a resolved **Problem Frame** (the classified Context) and returns a **Reasoning Strategy** — *how* to reason about this problem.

**Relationship to the mapping table.** `ENTERPRISE-CONTEXT-MODEL.md` ships a static `Context-to-Pattern Mapping Table` (Problem × ActivityPurpose → candidate pattern). That table is the *seed data* for Strategy Selection, not the architecture itself. Strategy Selection is the evolvable capability that may later learn its own mappings rather than consulting the static table.

**Seed mapping (v1).** The static table, preserved verbatim as Strategy Selection's initial knowledge:

| Problem | Activity Purpose | Candidate Pattern (Strategy seed) |
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

## 7. Reasoning Strategy layer (new — one level above patterns)

A **Reasoning Strategy** is a named reasoning posture. It is the output of Strategy Selection and the *selector* of Reasoning Patterns. Patterns are composable bundles; a Strategy is the posture that chooses which bundles (and in what order) apply.

Canonical Strategy enumeration (v1):

| Strategy | Trigger / posture | Pattern pipeline shape (illustrative) |
|---|---|---|
| `recognise_and_reuse` | Known SOP / direct-reuse pattern (Principle 1) | `SOP Execution` (+Verification) — no exploration |
| `investigate_then_fix` | Incident / unknown root cause | `Investigation → SOP Execution → Human Approval → Verification` |
| `deliberate_to_consensus` | Design / decision needing stakeholder agreement | `Debate → Consensus → Human Approval` |
| `research_to_synthesis` | Novel problem with no direct match (Level 3) | `Research → Exploration/Brainstorm → Validation` |
| `verify_and_assimilate` | Compliance / learning outcomes | `Verification → Reflection` (Learning hook) |

Strategies are stable; patterns beneath them evolve. A Strategy never encodes framework types (Principle 10).

## 8. Reasoning Patterns (kept — `REASONING-PATTERN-CATALOGUE.md`)

Patterns are the unit of composition for Sessions. Catalogue (v1): SOP Execution, Investigation, Exploration, Brainstorm, Debate, Consensus, Critique, Reflection, Research, Planning, Verification, Human Approval, Escalation, Learning. Each is a versioned bundle (`name@version`) declaring enabled/disabled pathways, roles, governance gates, inputs/outputs, and composability. Patterns are *one level below* Strategy (§7).

Stable abstraction boundary (no framework types in Context/Session/Pattern): `PathwayCallRequest`, `PathwayResponse`, `PathwayCapabilities`. Full catalogue and substrate mapping: `REASONING-PATTERN-CATALOGUE.md`.

## 9. Enterprise Concepts & Knowledge

### 9.1 Enterprise Concept — the central noun

An **Enterprise Concept** is the central noun of the type system. Every enduring enterprise asset is a Concept record with a `kind`. Two kinds matter most to the reasoning core:

- **Concept Payload** — `kind=solved_approach`. A reusable, proven solution approach (a distilled SOP, a playbook, a decision record). This is the "what we know works" asset.
- **Capability** — `kind=tool|skill`. A registry entry describing *what the business does* and how to invoke it (see §10).

Concept Payload and Capability share **one type system**: both are Enterprise Concept records distinguished by `kind`. This is the locked decision in the alignment plan (§3).

### 9.2 Knowledge — first-class epistemic graph

**Knowledge** is a first-class, evolving epistemic graph of the enterprise, not a side store. It is populated by `KnowledgeChunkDiscovered` events that a background subscriber routes into the appropriate store (Vector RAG / Capability Registry / Concept Payload library) based on semantic tags. The vector store (Qdrant) holds the semantic layer; Postgres holds structured concept records; repo markdown holds authored policy/design docs.

### 9.3 Concept Payload library vs Pattern template library

- **Concept Payload** (`kind=solved_approach`) — a *learned, proven* approach asset in the enterprise store.
- **Pattern template / manifest template** — a *reusable structural blueprint* for agents/sessions (see `agent_template_repository`, `solution_templating`). Distinct from the Concept Payload library: templates are scaffolds; payloads are conclusions.

### 9.4 Enterprise asset store

| Asset Type | Store | Rationale |
|---|---|---|
| Policy metadata, ADRs, pattern bundles, playbook structures, session summaries | Postgres (`db.py`) | Structured, queryable |
| Semantic memory, prior outputs, embeddings | Qdrant | Vector graph layer |
| Authored docs, policy, design guidelines, framework analyses | Repo markdown | Versioned, reviewable |

## 10. Capability (Capability Registry mapping)

A **Capability** is an Enterprise Concept record of `kind=tool|skill` — a registry entry describing a unit of executable work and how to invoke it. It is classification, not execution: the Pattern Runtime invokes a Capability on a pattern step's behalf.

- **Dual representation** (`execution_mode: ai_mediated | compiled`): an `ai_mediated` Capability reads an `ai_spec` (purpose/inputs/outputs/constraints); a `compiled` Capability points at a deterministic implementation. This is the `prompt | code | distilled` tier lineage from the workflow-runner ADR (`ai_orchestration_duality.md`), remapped to `ai_mediated | distilled | compiled`.
- **Transport** (Tier 2 in-process / Tier 3 bus-mediated per ADR §6.2): in-process Capability calls are direct; bus-mediated calls use Request-Reply envelopes. See `tooling_integration` alignment.
- **Single-registry intent.** ADR §7 item 11 (Tool Registry vs Agent Registry consolidation) is **open**; this model maps to the *single Capability Registry intent* (one registry, `kind: tool|skill`) without requiring that decision to be resolved. See `sbb/tool_registry.md` alignment.

### 10a. Capabilities are built using the same planning pipeline as workflows

There is **no separate "service-building" process.** Designing and creating a Capability (including a durable Service) reuses the *same* reasoning/planning pipeline that runs a workflow:

1. **Recognise / reason** — the Assistant Reasoning Service classifies the need into a Problem Frame and selects a Reasoning Strategy (§6–§7).
2. **Plan / design** — a `Planning` / `Research` / `Critique` Pattern pipeline produces the Capability's contract (`ai_spec` or compiled module, data entities, policy checks).
3. **Author & validate** — `Service_Authoring` scaffolds it and runs a validation Session.
4. **Register & promote** — it enters the Capability Registry (`kind=tool|skill`) at `ai_mediated`, and the Learning Loop may later promote it to `compiled` (§13).

Once registered, the Capability is invoked through the **internal agentic API** (Agent Bus Tier 3 / in-process Tier 2) exactly like any other step. Its implementation may be a compiled module, a skill, or a Session (workflow) exposed behind that API. A workflow "calling another workflow" is therefore just a Capability invocation of a `workflow`-implemented Capability — one mechanism. The only extras a *Service* (vs a pure workflow) requires are durable state ownership and a standing API contract, both already covered by `Workflow_Engine` + `Capability_Registry_Service` + `Event_Bus`. See §1a for the decision rule the designing AI uses to pick Service vs Session.

## 11. Session (kept — `SESSION-MODEL.md`)

A **Session** is a first-class, bounded execution construct: a pipeline of pattern steps executing against a Context. In implementation terms, a Session *is* a workflow instance (`WorkflowState`). Existing single-step workflows are Sessions with one `workflow-runner` step — a strict extension, not a fork. Full schema, lifecycle, and worked examples: `SESSION-MODEL.md`.

## 12. Pattern Runtime (kept — `RUNTIME-MAPPING.md`)

The **Pattern Runtime** is the replaceable execution substrate. **LangGraph is one adapter** (the designated substrate); the `workflow-runner` is another. Frameworks are runtimes, not architecture (Principle 7). The stable boundary (`PathwayRuntime`, `PathwayCallRequest`, `PathwayResponse`) carries zero framework types. Full framework analysis and degraded routing: `RUNTIME-MAPPING.md`.

## 13. Learning Loop (kept — `PATTERN-RECOGNITION-ASSIMILATION.md`)

The **Learning Loop** is pattern recognition & assimilation: Discovery → Classification → Validation → Documentation → Registration → Evolution. It is the mechanism that converts reasoning into deterministic execution and updates Enterprise Concepts / Knowledge (not individual agents). Three abstraction levels (Direct Reuse / Adaptation / Metaphorical Transfer) and three recognition levels (Level 1 retrieval, Level 2 adaptation, Level 3 synthesis) live here. Full spec: `PATTERN-RECOGNITION-ASSIMILATION.md`.

## 14. Validation suite — ten scenarios (S1–S10)

These scenarios are the permanent validation suite (merged from `SCENARIO-VALIDATION.md` §9.7). Each must be expressible using *only* this model + the mapped artifacts, with zero new framework assumptions. The first two (S1, S2) are traced in full in `SCENARIO-VALIDATION.md`; the remainder are framed here as model-level traces.

| ID | Intent (origin) | Problem Frame | Strategy | Pattern pipeline | Notes |
|----|------------|---------------|----------|------------------|-------|
| S1 | User alert: payment 5xx spike | `incident`, `investigate→execute`, `ai_assisted`, `human_approval` | `investigate_then_fix` | `Investigation → SOP Execution → Human Approval → Verification` | Full trace in `SCENARIO-VALIDATION.md` Trace A |
| S2 | ARB decision: adopt frontend framework | `design`, `decide`, `humans_and_agents`, `consensus` | `deliberate_to_consensus` | `Debate → Consensus → Human Approval` | Full trace in `SCENARIO-VALIDATION.md` Trace B |
| S3 | Scheduled compliance check | `compliance`, `validate`, `regulated` | `verify_and_assimilate` | `Verification` (direct SOP) | Level 1 direct reuse; no exploration |
| S4 | Known SOP re-run (PCI-DSS incident) | `incident`, `execute`, `enterprise_knowledge` | `recognise_and_reuse` | `SOP Execution → Verification` | Concept Payload (`solved_approach`) retrieved; Principle 1 short-circuit |
| S5 | Novel architecture problem, no prior art | `unknown`, `investigate` | `research_to_synthesis` | `Research → Exploration → Validation` | Level 3 synthesis; feeds Learning Loop |
| S6 | Routine report generation | `routine_operation`, `execute` | `recognise_and_reuse` | `SOP Execution` | Single-step Session = today's workflow |
| S7 | Innovation brainstorm | `innovation`, `explore` | `research_to_synthesis` | `Brainstorm` | Role-enriched via CrewAI analysis absorbed |
| S8 | Cross-domain metaphor transfer | `innovation`, `decide` | `deliberate_to_consensus` (metaphorical) | `Debate` (structure reused cross-domain) | Level 3 metaphorical transfer |
| S9 | Incident with >5 sequential tool calls | `incident`, `investigate`, `api_automated` | `investigate_then_fix` | `Investigation (CodeAct mode) → SOP Execution` | MAF/CodeAct pattern absorbed as step execution mode |
| S10 | Learning/retrospective after a Session | `learning`, `optimise` | `verify_and_assimilate` | `Reflection → Learning` | Distillation hook; writes Concept Payload to store |

**Self-containment check (validation gate F2).** Every scenario above is expressed using only: Intent → Context/Problem Frame → Strategy Selection → Reasoning Strategy → Reasoning Patterns → Enterprise Concept (Concept Payload / Capability) → Session → Pattern Runtime → Learning Loop. No scenario introduces a new framework concept; all framework references (LangGraph, CrewAI, MAF, ADK) are confined to the Pattern Runtime adapter layer (§12) and the pattern catalogue (§8), both of which already exist as mapped artifacts.

## 15. Traceability to working principles

| Principle | Where enforced |
|---|---|
| 1. Recognition before reasoning | Strategy Selection seed (§6); Learning Loop Level 1 (§13) |
| 2. Reason only when uncertainty | `recognise_and_reuse` vs `research_to_synthesis` (§7) |
| 3. Enterprise assets first-class | Enterprise Concept as central noun (§9) |
| 4. Context determines behaviour | Context model (§5) → Strategy Selection (§6) |
| 5. Patterns composable | Pattern catalogue (§8) |
| 6. Sessions define rules | Session model (§11) |
| 7. Frameworks are runtimes | Pattern Runtime (§12) |
| 8. Reasoning → deterministic | Learning Loop (§13); Concept Payload promotion |
| 9. Learning updates assets | Knowledge graph + Concept Payload (§9) |
| 10. Stable abstractions | Zero framework types in Context/Session/Pattern |

## 16. Alignment index (summary of mapped artifacts)

Full per-artifact status is in `ALIGNMENT-MATRIX.md`. Reasoning-core artifacts each carry a `## Cognition Alignment` section pointing back to this doc. Business-domain artifacts (Phase D) carry a one-line consumer note. SA workflow-runner specs (Phase E) carry cross-references.

- Reasoning-core SBBs: `agent_orchestrator`, `agent_registry`, `agent_runtime`, `agent_template_repository`, `tool_registry`, `agentic_observability_platform`.
- Reasoning-core ABBs: `agent_management`, `automated_task_execution`, `tooling_integration`, `solution_templating`, `operational_visibility`.
- Business-domain (consumers): `Workflow_Engine`, `Control_Center_UI`, `Work_Session_Service`, `Task_Tracking_Service`, `Lead_Enrichment_Service`, and their ABBs.
- SA specs: `sa/utilities/workflow-runner/*`.
