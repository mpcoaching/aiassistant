# Plan: Align Engineering Artifacts to the Cognition-Centric Architecture

**Status:** Implementation-ready (documentation/architecture-alignment plan; no source-code changes)
**Audience:** Martin (architecture owner), Kilo Code / implementation agents
**Source of truth:** the conceptual architecture from the prior review (`1784184802270-agentic-cognition-centric-architecture-review.md`, Part 2 §13) — Intent → Context → Problem Frame → Strategy Selection → Reasoning Strategy → Reasoning Patterns → Enterprise Concepts / Knowledge → Session → Pattern Runtime → Capability → Learning Loop.
**Companion docs (existing, to be consolidated/mapped, not rewritten):** `ENTERPRISE-COGNITION.md`, `ENTERPRISE-CONTEXT-MODEL.md`, `REASONING-PATTERN-CATALOGUE.md`, `PATTERN-RECOGNITION-ASSIMILATION.md`, `SESSION-MODEL.md`, `RUNTIME-MAPPING.md`, `SCENARIO-VALIDATION.md`, the `abb/` and `sbb/` artifacts, and the `sa/utilities/workflow-runner/` specs.

---

## 0. Purpose & principle

The conceptual architecture is now stable (prior review, Part 2). This plan makes the **engineering artifacts agree with it**, so that any implementation — now or later — moves in one known direction.

Two decisions are locked from interview:
1. **Anchor doc first.** A single consolidated `Enterprise Cognition Reference Architecture` is created and becomes the canonical source of truth; all other artifacts align to it.
2. **Map, don't rename.** Existing vocabulary (agent, workflow, tool) is preserved as *implementation* terminology; each artifact gets a "Cognition Alignment" section mapping its terms to the model. This avoids breaking System Context references and the `packages/workflow-runner` code.

No source code is changed by this plan. It produces/updates **documents only**.

---

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

---

## 2. Task list (ordered; each task is a documentation deliverable)

### Phase A — Establish the canonical anchor
- **A1.** Create `agentic/docs/architecture/ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` consolidating:
  - The existing `ENTERPRISE-COGNITION.md` (first principles) — trimmed of duplicates.
  - `ENTERPRISE-CONTEXT-MODEL.md` (Context schemas + mapping table, kept as the Context spec).
  - `REASONING-PATTERN-CATALOGUE.md` (patterns) — now explicitly *one level below* Strategy.
  - The Part 2 additions: **Intent** entry abstraction, **Reasoning Strategy** layer + enum, **Enterprise Concept** as central noun (Concept Payload = one record kind), **Knowledge** as first-class epistemic graph, **Strategy Selection** as first-class capability (replacing the static mapping table as its v1 seed), **Pattern Runtime** terminology (LangGraph = one adapter).
  - The §13 conceptual diagram and the §9.7 ten validation scenarios (S1–S10) as the permanent validation suite.
  - This doc is the single source of truth all other artifacts reference.

### Phase B — Reconcile reasoning-core SBBs (map, don't rename)
For each, add a "Cognition Alignment" section mapping its terms via §1, and note its role in the model. Do **not** rewrite function/responsibility bodies.
- **B1.** `sbb/agent_orchestrator.md` → align to "Strategy/Session dispatch" (decides *that* a session runs; Strategy Selection decides *how*).
- **B2.** `sbb/agent_registry.md` → align to "Role/Pattern participant definitions" (the "who's in the meeting" list; ADR §7).
- **B3.** `sbb/agent_runtime.md` → align to "Pattern Runtime (sandboxed execution of a Capability / pattern step)".
- **B4.** `sbb/agent_template_repository.md` → align to "reusable Pattern / manifest templates" (distinct from Concept Payload library).
- **B5.** `sbb/tool_registry.md` → align to "Capability Registry" (one registry, `kind: tool|skill`, `execution_mode`; ADR §7/§9). Note the open question (§7 item 11) but map to the single-registry intent.
- **B6.** `sbb/agentic_observability_platform.md` → align to Token Economics / Learning Loop tracking (cost-per-request-type, reuse hit-rate, exploration spend; ADR §16).

### Phase C — Reconcile reasoning-core ABBs
- **C1.** `abb/agent_management.md` → reframe "agents" as reasoning participants configured by Strategy/Pattern; link to B2/B3.
- **C2.** `abb/automated_task_execution.md` → align to deterministic Capability / SOP-execution pattern.
- **C3.** `abb/tooling_integration.md` → align to Tier 2 (in-process) / Tier 3 (bus-mediated) Capability transport (ADR §6.2).
- **C4.** `abb/solution_templating.md` → align to Pattern templates (B4) vs Concept Payload library.
- **C5.** `abb/operational_visibility.md` → align to Observability/Learning Loop (B6).

### Phase D — Reconcile business-domain artifacts (consumers only; minimal notes)
Per ADR §7 these are **consumers**, not part of the reasoning core — add a short "Relationship to Cognition Model" note, no rewrite.
- **D1.** `sbb/Workflow_Engine.md` — note: owns the Session (workflow instance) execution; calls Strategy Selection / Pattern Runtime; publishes lifecycle events (ADR §5.2).
- **D2.** `sbb/Control_Center_UI.md`, `sbb/Work_Session_Service.md`, `sbb/Task_Tracking_Service.md`, `sbb/Lead_Enrichment_Service.md` — one-line note each: "consumes Concept Payloads / Capabilities via the bus; not part of the reasoning core."
- **D3.** `abb/Control_Center.md`, `abb/Work_Session.md`, `abb/Task_Tracking.md`, `abb/Lead_Enrichment.md` — same one-line consumer note.

### Phase E — Reconcile SA workflow-runner specs
- **E1.** `sa/utilities/workflow-runner/functional-specification.md` — add a "Cognition Alignment" note: a workflow = a Session executing a Pattern pipeline; steps = pattern steps / Capability calls; the existing `prompt|code|distilled` duality maps to `ai_mediated|distilled|compiled`.
- **E2.** `sa/utilities/workflow-runner/ai-orchestration-design.md`, `technical-design.md`, `workflow-schema.md`, `runtime-interface.md`, `implementation-plan.md` — add cross-references to the anchor doc; update the schema doc to note `intent` field now denotes an **Intent** subtype.

### Phase F — Validation & consistency gate
- **F1.** Add a `## Cognition Alignment` header convention: every reasoning-core artifact (Phase B/C) MUST contain one, referencing the anchor doc.
- **F2.** Verify the ten scenarios (S1–S10) can be expressed using **only** the anchor doc's model + the mapped artifacts, with zero new framework assumptions.
- **F3.** Produce a one-page `ALIGNMENT-MATRIX.md` (or appendix in the anchor doc) listing each artifact → its model role → status (aligned/pending). This is the "everything agrees" evidence.

---

## 3. Decisions locked
- Canonical anchor = `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` (Phase A). All others reference it.
- Map existing terms; do not rename. System Context doc and `packages/workflow-runner` code references stay valid.
- Business-domain artifacts (Phase D) get consumer notes only — they are not the reasoning core.
- Concept Payload = one `Enterprise Concept` record kind; Capability = another kind. Same type system.
- Strategy Selection replaces the static Context→Pattern table as its v1 seed (evolvable later).

## 4. Risks
- **R1** Anchor doc drift from the prior review's §13 if written carelessly. Mitigation: A1 copies §13 verbatim as the diagram; sections 9.1–9.7 summarised, not reinterpreted.
- **R2** An SBB/ABB author "helps" by rewriting functions in new vocabulary, re-introducing the rename churn we explicitly avoided. Mitigation: tasks say "add a Cognition Alignment section; do not rewrite responsibility bodies."
- **R3** `tool_registry` vs single Capability Registry open question (ADR §7 item 11) could block B5. Mitigation: B5 maps to the single-registry *intent* and flags the open question; does not require resolving it.

## 5. Validation
- After Phase A: anchor doc exists and is self-contained (expresses S1–S10 without external docs).
- After Phase B/C: every reasoning-core artifact contains a `## Cognition Alignment` section referencing the anchor doc.
- After Phase D: business-domain artifacts contain a one-line consumer note.
- After Phase F: `ALIGNMENT-MATRIX.md` shows all artifacts aligned; a reviewer can trace any scenario S1–S10 from Intent → Strategy → Pattern → Concept/Capability using only the anchor doc + mapped artifacts.

## 6. Open questions (not blockers)
1. Where should the anchor doc and `ALIGNMENT-MATRIX.md` live — `agentic/docs/architecture/` (current cognition docs) or a new `docs/architecture/cognition/`? Recommend current location to keep cognition docs together.
2. Should `SCENARIO-VALIDATION.md` be merged into the anchor doc (as its validation suite) or kept separate and cross-referenced? Recommend merge (it already validates the model).
3. The `tool_registry` vs single Capability Registry decision (ADR §7 item 11) remains open; B5 proceeds on the single-registry intent regardless.
