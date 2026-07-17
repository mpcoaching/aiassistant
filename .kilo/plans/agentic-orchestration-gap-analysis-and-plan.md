# Pattern-Driven Agentic System — Gap Analysis & Phased Plan of Action

**Status:** Draft for review (this document, not yet slotted into the ADR/SPEC sequence)
**Audience:** Martin (architecture owner), Kilo Code (implementation)
**Source doc:** "Agentic Orchestration Architecture — Pattern-Driven Agentic System (Single LangGraph Substrate)" (the ADR-level input)
**Companion docs reviewed:** `docs/SYSTEM_CONTEXT.md`, `agentic/docs/context/ea/adr/ai_orchestration_duality.md`, `agentic/docs/architecture/sbb/{tool,agent}_registry.md`, `agentic/docs/architecture/REASONING-PATTERN-CATALOGUE.md`, `PATTERN-RECOGNITION-ASSIMILATION.md`, existing `agentic/src/workflow-runner`, `.kilo/plans/capability-architecture-plan.md`.

---

## 0. How to read this document

The source ADR is strong on *shape* and *boundaries* but deliberately punts on two things:

1. **Tuning surfaces** — named defaults it expects to move once real data exists (confidence thresholds, audit sample size, exploration curve shape, compilation threshold, fast/slow timeout).
2. **Genuinely open decisions** — the five flagged in §17: interrupt resume (7), registry consolidation (11), fast/slow threshold (12), no-provider fallback (14), compilation threshold (17).

This document does **not** try to resolve those. It does two jobs:

- **Part A — Detail gaps:** what must be specified *before* a component SPEC can be written to the standard the source doc demands (Core-first, typed-contract, injectable config). These are the missing schemas, interfaces, and envelopes without which a SPEC would have to invent architecture.
- **Part B — Plan of action:** which components to build, in what order, grouped into phases, with a rationale tied to the dependency graph in the source doc (§4 Core/Adapter split, §7 service topology, §18 handoff notes).

Two concrete conflicts with existing repo material are flagged in §A.0 — they should be resolved before any SPEC is authored, because they change where code lives.

---

## A. Detail Gaps — what needs more detail before SPECs can be completed

Each item below names the *missing artifact*, the *why-now* (why a SPEC can't be written without it), and the *proposed owner artifact* (what to produce). Every artifact should be produced as a **Core-first plain-data contract** per §4/§18 — no LangGraph type reaches into it.

### A.0 Repo conflicts to resolve first (blockers, not gaps)

These aren't "more detail" — they're contradictions between the new ADR and existing plans/code. A SPEC author will hit them immediately.

- **A.0.1 `capability-architecture-plan.md` still lists an `autogen/` capability package.** The source ADR §3 and §18 are explicit and absolute: *no `autogen` or `crewai` package anywhere in this codebase.* The Deliberation pattern is implemented natively in the `langgraph` package. **Action:** strike `autogen` from the capability layout. The `agents/autogen/` dir found in the tree should not be carried forward. This is a real conflict, not a tuning surface.
- **A.0.2 Three parallel code homes.** `agentic/src/workflow-runner`, `agents/workflow-runner`, and `packages/workflow-runner` (per the capability plan) overlap. The existing `workflow-runner` already implements the `prompt | code | distilled` duality from the accepted ADR (`ai_orchestration_duality.md`) — it is the natural seed for the new Core Domain Layer's Capability execution path. **Action:** pick one canonical home and a migration step *before* authoring the Capability Registry / Assembly Line SPECs, or those SPECs will be written against a moving target. The source ADR §7 maps the Workflow Engine to "one execution of a Concept Payload's manifest" — that is the `workflow-runner`, so it should be the first thing lifted into the Core/Adapter split.

### A.1 Canonical type system for the Core Domain Layer (BLOCKER for every SPEC)

**Missing:** a single module of plain owned dataclasses/Pydantic models — `SystemState`, `ConceptPayload`, `Capability`, `ScoringRubric`, `Interrupt`, `KnowledgeChunk`, `CapabilityRequest`/`CapabilityReply` envelopes. The source doc *describes* these inline (§9.3, §12, §5.1, §5.3, §6.2) but never defines them as a contract.

**Why now:** §18 says "every component SPEC should define its own minimal state contract." A SPEC cannot define a minimal contract against types that don't exist yet — it would either invent them (violating the ADR's intent) or reach for framework types (violating §4). The cross-cutting types (`Capability`, `ConceptPayload`, request/reply envelopes) are imported by *every* component SPEC.

**Proposed owner artifact:** `core_types.md` (or a typed `.py`/`.proto` equivalent) declaring each model, fields, and invariants. This is the first artifact to produce and the only hard prerequisite for the rest.

### A.2 Capability Registry dual-representation contract (BLOCKER for §9, §7, item 11)

**Missing:** the persisted `kind: tool | skill` + `execution_mode: ai_mediated | compiled` record shape, the `ai_spec` schema (purpose/inputs/outputs/constraints — what Deliberation reads), and the two impl-ref shapes (`ai_mediated_impl_ref`, `compiled_impl_ref` with the Tier-2 pointer vs Tier-3 Capability-type distinction from §6.2). Plus `maturation_history[]` field semantics (invocation count, correction rate, compilation candidacy).

**Why now:** §9.4 discovery and §9.3 promotion *both* depend on these fields being queryable by `kind`, `execution_mode`, and `eip_role`. Item 11 (registry consolidation) is OPEN, but its resolution only changes whether `Tool Registry Service` and `Agent Registry Service` merge — it does **not** change this record shape, because §9 already mandates a single dual-representation shape regardless. So this can be specced now; the service boundary is orthogonal.

**Proposed owner artifact:** `capability_registry_contract.md` extending A.1's `Capability`.

### A.3 Interrupt Port abstraction & event envelopes (BLOCKER for §5.1, §4 swap test)

**Missing:** the abstract `InterruptPort` interface (Core-only, no RabbitMQ import), the triage classifier's input/output contract (event-in → tier-out), and the in-state `interrupt_queue` / `active_interrupt` fields. The classifier itself is rule/keyword-first then optional cheap-LLM — but the *shape* of "an event" and "a tier decision" is undefined.

**Why now:** §4's swap test requires Core to depend only on the abstract port. Without the port's method signatures, the Adapter Layer and Core cannot be written against the same boundary. This is also the literal example the ADR uses for "Core never knows RabbitMQ exists."

**Proposed owner artifact:** `interrupt_port_contract.md` + `event_envelopes.md` (covers §5.2 lifecycle and §5.3 `KnowledgeChunkDiscovered` too, since all three ride the same bus).

### A.4 Confidence Router I/O + embedding injectability (BLOCKER for §8, item 8)

**Missing:** the router's pure function signature `route(request_embedding, library) -> Band` and the embedding-model **Port** (injectable, defaults to local/self-hosted). The §8 bands (≥0.92 / 0.55–0.92 / <0.55) must be config, not literals — but there is no named config schema yet for "the intake routing thresholds" and "the embedding provider endpoint."

**Why now:** §8's hard rule — recognition costs zero LLM tokens — depends on the embedding Port defaulting to local. The SPEC cannot enforce this without the Port + config keys existing. The three bands are tuning surfaces, but the *keys* that hold them are not.

**Proposed owner artifact:** `confidence_router_contract.md` (function signature + config key names + embedding Port).

### A.5 Scoring rubric as versioned config object (BLOCKER for §10 convergence, §17 item 2)

**Missing:** the rubric's formal schema — weighted attributes (constraint fit, prior-art alignment, est. cost, risk/reversibility, preference alignment) with weights as named, versioned config, and the deterministic `score(candidate, rubric, constraints) -> float` selector + tie-margin constant. §10 says the rubric is "first-class, versioned config, not buried in a prompt" but no envelope exists.

**Why now:** "Convergence is scored, not argued" (§10 DECIDED) is enforced by code that reads a config object. The SPEC for the Deliberation subgraph's convergence node needs that object's shape. Weights are a tuning surface; the object + tie-margin key are not.

**Proposed owner artifact:** `scoring_rubric_contract.md`.

### A.6 Exploration / headroom function as a tuning contract (needed for §14, item 5)

**Missing:** the `reopen_probability(quality_score) -> float` function *interface* and the config keys for its tunable parts (floor, curve shape). §14 is explicit that the exact shape and floor are open tuning surfaces — but the SPEC needs to know *which knobs exist* so it can wire them, even if their default values are placeholders.

**Why now:** the Exploration mechanism (§14) is referenced by both payload-level (§13) and capability-level (§9.3) reopening. The function must be injectable so it can be tuned without code change (§17 closing note).

**Proposed owner artifact:** `exploration_policy_contract.md` — interface + named config keys, default values flagged `TUNE`.

### A.7 EIP composition grammar — concrete vocabulary & validation (needed for §9.4, §12 manifest)

**Missing:** the fixed set of allowed EIP patterns (Content-Based Router, Filter, Splitter/Aggregator, Message Translator, Pipes-and-Filters, Endpoint) expressed as a typed manifest grammar, plus the **static validator** that rejects a manifest step that isn't a resolved `Capability.id` + concrete parameters (the §17 item 8 guard, and §18's Assembly Line guard).

**Why now:** §12 says the manifest is "a resolved sequence of `Capability.id` + parameters wired per an EIP shape." Without the closed EIP vocabulary and the validator, the Assembly Line SPEC cannot implement the zero-token enforcement the ADR calls "enforced, not just documented." `REASONING-PATTERN-CATALOGUE.md` already defines a `PathwayCallRequest`/`PathwayResponse` boundary — reuse it rather than inventing a new one.

**Proposed owner artifact:** `eip_manifest_grammar.md` + `manifest_validator_contract.md`.

### A.8 Capability Compilation pipeline interface to opencode roster (needed for §9.3, §18)

**Missing:** the *trigger* contract — what an `ai_mediated` Capability's `maturation_history` must contain to *propose* compilation (distinct from the open compilation-threshold number, item 17), and the handoff shape into the existing Test Writer → Reviewer → Implementer pipeline. The source ADR §18 says this is a *consumer* of the existing roster, not new AI — but the input/output envelope between the Capability Registry and that roster is undefined.

**Why now:** §9.3 and item 16 are DECIDED (compilation goes through review, not auto-deploy). The SPEC can be written once the trigger signal and roster input envelope exist; the actual threshold number (item 17) is a tuning surface that slots into the same envelope later.

**Proposed owner artifact:** `capability_compilation_contract.md`.

### A.9 Knowledge Propagation subscriber contract (needed for §5.3)

**Missing:** the `KnowledgeChunkDiscovered` event schema (semantic tags, payload reference) and the subscriber's routing rules (which store — Vector RAG, Capability Registry, Concept Payload library — receives which chunk). §5.3 says "a background subscriber picks these up" but doesn't define how it decides destination.

**Why now:** this is the mechanism that makes cross-workflow reuse real. It's a SPEC in its own right (§18 lists it) and needs the event envelope from A.3 plus the semantic-tag taxonomy.

**Proposed owner artifact:** extends `event_envelopes.md` (A.3) + `knowledge_propagation_contract.md`.

### A.10 Deliberation & Scoped-Task subgraph *template* interfaces (needed for §3, §10, §11)

**Missing:** the two reusable subgraph templates' minimal state contracts — what a Deliberation "turn" node receives/returns, the round-counter field and its router-edge check, and the Scoped-Task node's fixed-tool-input / single-result contract. These are the two patterns everything else composes from (§3).

**Why now:** §18 lists both as SPEC outputs. The templates must be specced *before* the phases that instantiate them (Deliberation Room, Role-Limited Research, Assembly Line), because those higher phases are "specific instantiations," not new integrations.

**Proposed owner artifact:** `subgraph_templates_contract.md` (two templates).

### Summary of gap severity

| ID | Artifact | Gates which SPECs | Severity |
|----|----------|-------------------|----------|
| A.0.1 | Drop `autogen` from capability plan | All (repo structure) | Blocker |
| A.0.2 | Pick canonical workflow-runner home | Capability/Assembly SPECs | Blocker |
| A.1 | Core type system | Every SPEC | Blocker |
| A.2 | Capability Registry contract | §9, discovery, promotion | Blocker |
| A.3 | Interrupt Port + envelopes | §5, Core/Adapter swap test | Blocker |
| A.4 | Confidence Router + embedding Port | §8 intake | Blocker |
| A.5 | Scoring rubric config object | §10 convergence | Blocker |
| A.6 | Exploration policy interface | §14 reopening | Needed |
| A.7 | EIP grammar + manifest validator | §9.4, §12, Assembly guard | Needed |
| A.8 | Compilation pipeline trigger/roster | §9.3 | Needed |
| A.9 | Knowledge Propagation contract | §5.3 | Needed |
| A.10 | Subgraph template interfaces | §3 phases | Blocker |

---

## B. Plan of Action — phased implementation

Phases are ordered by the **dependency graph**, not by document section order. Foundation first (types + ports), then the two reusable patterns, then the phases that instantiate them, then the cross-cutting subscribers, then the genuinely-open tuning work.

### Phase 0 — Repo reconciliation (do before any code) — ~0.5 day
- **P0.1** Resolve A.0.1: remove `autogen` from `capability-architecture-plan.md` and `agents/autogen/`. Add an explicit repo rule: no `autogen`/`crewai` dependency or package (mirror §18 into `AGENTS.md`/contributing).
- **P0.2** Resolve A.0.2: declare `workflow-runner` (the one already implementing prompt/code/distilled duality) as the canonical Core seed; define the migration of `agentic/src` + `agents` into `packages/` per the capability plan, leaving one home.
- **Deliverable:** a one-page repo decision note; no SPEC blocked after this.

### Phase 1 — Core type system & ports (the §4 boundary) — ~3–4 days
Build the framework-agnostic Core Domain Layer contracts. **No `langgraph` import anywhere in this phase.**
- **P1.1** Author `core_types` (A.1): `SystemState`, `ConceptPayload`, `Capability`, `ScoringRubric`, `Interrupt`, `KnowledgeChunk`, request/reply envelopes. With unit tests on invariants only.
- **P1.2** Author `interrupt_port` + `event_envelopes` (A.3, A.9): abstract `InterruptPort`, triage I/O, lifecycle + `KnowledgeChunkDiscovered` envelopes.
- **P1.3** Author `capability_registry_contract` (A.2), `confidence_router_contract` (A.4), `scoring_rubric_contract` (A.5), `exploration_policy_contract` (A.6), `eip_manifest_grammar` + `manifest_validator_contract` (A.7), `capability_compilation_contract` (A.8).
- **Exit criterion:** every model is a plain typed object; a grep for `langgraph`/`rabbitmq` in the Core layer returns nothing.

### Phase 2 — Two reusable subgraph templates (the §3 patterns) — ~4–5 days
These are the only "graph-shaped" Core logic; the Adapter wraps them later.
- **P2.1** Deliberation subgraph template (A.10): agenda node, role-turn node with bounded round-counter, deterministic Scoring convergence node, condenser node. Core logic only.
- **P2.2** Scoped-Task subgraph template (A.10): single fixed-tool-input node, single typed result, no transcript access.
- **Exit criterion:** both templates are testable as pure functions over `SystemState` slices with no LLM calls in the routing/loop logic (only in the role/LLM call sites, which are injected).

### Phase 3 — LangGraph Adapter Layer (the only place `langgraph` is imported) — ~3–4 days
- **P3.1** `StateGraph` spine wiring Core functions into nodes; edges call Core routers and translate to LangGraph routing format.
- **P3.2** Checkpointing/resume bound to the bus (§5.1, §6.1) — the *one* place urgent interrupts are handled at node boundaries.
- **P3.3** Runtime Interface adapter (`start/run/send/add/drop/stop/exit/get_status`) per SYSTEM_CONTEXT §7 mapping to the Workflow Engine.
- **Exit criterion:** the §4 swap test is demonstrable — Core layer untouched if the Adapter is swapped.

### Phase 4 — Concrete phase instantiations (build on P2 templates) — ~5–7 days
- **P4.1** Confidence Router (§8) over `confidence_router_contract` + embedding Port (local default) — zero-token intake.
- **P4.2** Deliberation Room (§10) — full form: agenda, role assignment, bounded rounds, multi-candidate, scored convergence, condenser → `ConceptPayload`.
- **P4.3** Role-Limited Research (§11) — Scoped-Task instance.
- **P4.4** Assembly Line (§12/§9) — executes a frozen `manifest`, with the **A.7 validator guard** rejecting unresolved steps. Tier-2 direct calls; Tier-3 via Request-Reply (A.9 of §6.2).
- **P4.5** Concept Payload store + Muscle-Memory write-back & audit gate (§12, §13) — `draft`→`active` after N=3 (config), random audit sampling.

### Phase 5 — Cross-cutting subscribers & maturation — ~4–5 days
- **P5.1** Knowledge Propagation subscriber (§5.3, A.9): routes `KnowledgeChunkDiscovered` to RAG/Registry/Payload library.
- **P5.2** Capability promotion & compilation pipeline (§9.3, A.8): `ai_mediated`→`compiled` via maturation history → proposes through opencode Test Writer/Reviewer/Implementer roster; never auto-deploys.
- **P5.3** Exploration/headroom reopening (§14, A.6) wired into both payload and capability levels.
- **P5.4** Token Economics instrumentation (§16) into Observability/Langfuse — cost-per-request-type bands.

### Phase 6 — Genuinely-open decisions & tuning (calibration, not architecture) — ongoing
These are explicitly **not** blockers (§17). Each gets a SPEC *shell* now (config keys from Phases 1–5) and a calibration pass once real data exists:
- **Item 7** interrupt auto-resume — ship default auto-resume + `interrupted_by` tag; watch §14 quality tracking.
- **Item 11** registry consolidation — default to ONE Capability Registry (Tool+Skill in one service); confirm against System Context service boundaries.
- **Item 12** fast/slow threshold — ship a configurable per-Capability timeout (start ~3–5s); measure.
- **Item 14** no-provider fallback — default fail-fast to Observability; measure frequency.
- **Item 17** compilation threshold — default higher than N=3 (e.g. propose at 10 clean runs); tune with usage.

### Suggested SPEC authoring order (one SPEC per component, Core-first)
1. Core type system (P1.1) — *the SPEC all others reference*
2. Interrupt Port + envelopes (P1.2)
3. Capability Registry contract (P1.3)
4. Confidence Router (P1.3/P4.1)
5. Scoring rubric (P1.3/P4.2)
6. Subgraph templates (P2)
7. LangGraph Adapter (P3)
8. Deliberation Room / Role-Limited Research / Assembly Line (P4)
9. Concept Payload store + write-back (P4.5)
10. Knowledge Propagation / Compilation / Exploration / Token Economics (P5)

---

## C. Open questions this analysis surfaced (for Martin)

1. **A.0.1 vs capability-architecture-plan:** the existing plan still scaffolds `autogen`. Confirm we drop it and treat Deliberation as a native `langgraph` template? (I recommend yes — it directly contradicts §3/§18.)
2. **A.0.2 canonical home:** which of `agentic/src`, `agents`, `packages` is the single source for `workflow-runner` going forward?
3. **Port technology for Core↔Adapter and Core↔Bus:** the ADR says "ports and adapters" but the concrete port *style* (abstract base class vs protocol vs interface) isn't pinned. Recommend Python `Protocol` for the Core layer given the stack.
4. **Graph store for linked preferences (§12):** flat vector store + edge layer, or invest in GraphRAG now? ADR leaves this open; recommend the lighter option initially since it's orthogonal to the reasoning core.

None of these block Phase 1 except A.0.1/A.0.2 — those should be settled first.
