# Solution Architecture — Next Phase: Build the Reasoning-Core Building Blocks

**Status:** Ready for solution-architecture execution (documentation + scaffolding plan; derived from the alignment work and the 2026-07-16 decisions).
**Audience:** Martin (architecture owner), Kilo Code / implementation agents.
**Source of truth:** `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` (anchor), the aligned SBB/ABB set, and `ALIGNMENT-MATRIX.md`.
**Companion decisions:** (1) business services elevated to first-class Capabilities; (2) a workflow = a Session, a service = a Capability; (3) capabilities are built via the same planning pipeline as workflows (anchor §1a, §10a).

---

## 0. Goal of this phase

Turn the *model* into a *buildable set of building blocks*. At the end of this phase we will have:

- A complete, non-overlapping **SBB/ABB inventory** covering the reasoning core AND the business services (now modeled as Capabilities).
- A clear **invocation seam**: everything is a Capability called via the internal agentic API (Agent Bus Tier 3 / in-process Tier 2).
- A **decision rule** (anchor §1a) the designing AI uses to pick Service vs Session vs pure Capability.
- A **phased build order** with explicit end-state per phase, ready to hand to implementation agents.
- **No source-code changes yet** — this phase produces/refines architecture docs and a scaffolding backlog. Code begins in the phase after.

---

## 1. Resolved building-block inventory

### 1.1 Reasoning core (already aligned + new)

| ID | Artifact | Type | Role |
|---|---|---|---|
| RC-1 | `Assistant_Reasoning_Service` | SBB | Intent → Context → Problem Frame → Strategy Selection → Reasoning Strategy → Patterns (the "brain") |
| RC-2 | `agent_orchestrator` | SBB | Strategy/Session dispatch (decides *that* a Session runs) |
| RC-3 | `agent_registry` | SBB | Role / Pattern participant definitions |
| RC-4 | `agent_runtime` | SBB | Pattern Runtime (sandboxed execution of a Capability / pattern step) |
| RC-5 | `agent_template_repository` | SBB | Reusable Pattern / manifest templates |
| RC-6 | `Capability_Registry_Service` | SBB | Unified Capability Registry (`kind: tool|skill`) |
| RC-7 | `Service_Authoring` | SBB | Design + create Services/Capabilities (shared planning pipeline) |
| RC-8 | `Event_Bus` | SBB | Tier-3 Capability transport + `KnowledgeChunkDiscovered` ingestion |
| RC-9 | `Knowledge_Concept_Store` | SBB | Enterprise Concepts / Knowledge graph |
| RC-10 | `Workflow_Engine` | SBB | Owns Session execution; calls Strategy Selection / Pattern Runtime |
| RC-11 | `agentic_observability_platform` | SBB | Token Economics / Learning Loop tracking |
| RC-12 | `Service_Composition` | ABB | Design/create/orchestrate Services & Capabilities |
| RC-13 | `Capability_Management` | ABB | Governance of the Capability catalog |
| RC-14 | `Knowledge_Management` | ABB | Governance of Enterprise Concepts / Knowledge |
| RC-15 | `agent_management` | ABB | Governance of reasoning participants |
| RC-16 | `automated_task_execution` | ABB | Deterministic Capability / SOP-execution |
| RC-17 | `tooling_integration` | ABB | Capability transport (Tier 2/Tier 3) |
| RC-18 | `solution_templating` | ABB | Pattern templates (≠ Concept Payload) |
| RC-19 | `operational_visibility` | ABB | Observability / Learning Loop |

### 1.2 Business services — now first-class Capabilities (re-framed)

| ID | Artifact | Type | Role | Implementation posture |
|---|---|---|---|---|
| BS-1 | `Work_Session_Service` (+ `Work_Session` ABB) | SBB/ABB | Durable Service = Capability (owns Work Session entities) | Service (durable state + standing contract) |
| BS-2 | `Task_Tracking_Service` (+ `Task_Tracking` ABB) | SBB/ABB | Durable Service = Capability (owns Task entities) | Service |
| BS-3 | `Lead_Enrichment_Service` (+ `Lead_Enrichment` ABB) | SBB/ABB | Durable Service = Capability (owns Lead Profile; calls external-tool Capabilities) | Service |
| BS-4 | `Control_Center_UI` (+ `Control_Center` ABB) | SBB/ABB | Trigger/observation surface; calls Services as Capabilities | Consumer-of-capabilities (UI only) |

> All three business services are realized as **Capabilities** in `Capability_Registry_Service`; their SBBs own durable state and expose a standing internal API. They are *not* separate runtimes — they execute as Sessions behind that API.

---

## 2. The single invocation seam (no overlap)

```
Intent ──▶ Assistant Reasoning Service (RC-1)
            ├─ Strategy Selection (§6) ─▶ Reasoning Strategy (§7)
            ├─ Plan/Design (Patterns: Planning/Research/Critique)  [shared pipeline, §10a]
            ├─ Service_Authoring (RC-7) ─▶ Capability_Registry (RC-6)   [create new Capability/Service]
            └─ Workflow_Engine (RC-10) launches a Session
                     └─ Pattern Runtime (RC-4) executes PatternSteps
                            └─ each step = Capability invocation via internal API
                                 • Tier 2 in-process  (tooling_integration)
                                 • Tier 3 Agent Bus  (Event_Bus, RC-8)
                                        └─ Capability impl: compiled module | skill | Session(workflow) behind API
            Learning Loop (§13) ─▶ Knowledge_Concept_Store (RC-9) + Capability promotion
```

Every participant — Assistant, Workflow Engine, a Session calling another — invokes Capabilities through **one API** (Bus/REST). A "service" differs from a "workflow" only by durable state + standing contract (anchor §1a).

---

## 3. Decision rule for the designing AI (anchor §1a, encoded for implementations)

| Need | Choose | Why |
|---|---|---|
| Repeatable, depended-upon operation **with owned data** (tasks, leads, work sessions) | **Service** (Capability + durable state + standing contract) | Others reuse it via stable API; state survives the run |
| One-off / ad-hoc composition for a single Intent, no reusable asset | **Session (workflow)** directly | Transient; nothing to own or depend on |
| A unit of executable work with **no durable entity** (a tool, a skill) | **pure Capability** (`kind=tool|skill`, `ai_mediated`→`compiled`) | Invocation only |
| Creating any of the above | **shared planning pipeline** (RC-1 → RC-7 → RC-6) | No separate service-building process (§10a) |

---

## 4. Phased build order (end-state per phase)

### Phase 1 — Foundation types & registry (no LangGraph import; mirror the earlier gap-analysis boundary)
- **End-state:** `Capability_Registry_Service` (RC-6) operational with the unified `Capability` record (`kind=tool|skill`, `execution_mode: ai_mediated|compiled`, `ai_spec`/`compiled_ref`, maturation history). `Knowledge_Concept_Store` (RC-9) persisting Enterprise Concepts by `kind` (Postgres + Qdrant). The `Event_Bus` (RC-8) topology defined (`workflow.lifecycle.*`, `capability.request/reply`, `knowledge.chunk.discovered`).
- **Deliverables:** registry contract, concept-store schema, bus topology spec.
- **Exit:** a capability can be registered and resolved; a `KnowledgeChunkDiscovered` event routes to the correct store.
- **Concrete contracts:** **`SA-CONTRACTS-PHASE1.md`** (C1 Enterprise Concept type system, C2 Capability record, C3 Intent intake, C4 Strategy Selection, C5 Capability invocation envelope + bus topology, C6 store schema, C7 three business Services as Capabilities, C8 Phase-1 task breakdown). This appendix contains every schema/interface/envelope needed — an implementer makes **zero architectural decisions** in Phase 1.

### Phase 2 — Reasoning entrypoint & Strategy Selection
- **End-state:** `Assistant_Reasoning_Service` (RC-1) accepts Intents, resolves Context → Problem Frame, and calls Strategy Selection (anchor §6) to pick a Reasoning Strategy (§7). `agent_registry` (RC-3) supplies participant definitions.
- **Deliverables:** Intent intake contract, Strategy Selection seed (the static mapping table from anchor §6), Strategy enum.
- **Concrete contracts:** `SA-CONTRACTS-PHASES-2-5.md` §C9 (Assistant Reasoning Service intake API, `StrategyDecision`, participant resolution).
- **Exit:** an Intent yields a Strategy + candidate Pattern pipeline without executing it.

### Phase 3 — Pattern Runtime & Session execution
- **End-state:** `agent_runtime` (RC-4) as a Pattern Runtime adapter; `Workflow_Engine` (RC-10) launches Sessions; pattern steps invoke Capabilities via Tier 2/Tier 3. `automated_task_execution` (RC-16) covers the deterministic SOP path.
- **Deliverables:** PathwayRuntime contract, Session→WorkflowState mapping, Capability invocation envelope.
- **Concrete contracts:** `SA-CONTRACTS-PHASES-2-5.md` §C10 (Session creation from StrategyDecision, PatternRuntime adapter, Capability invocation, Workflow Engine lifecycle).
- **Exit:** a Session runs a Pattern pipeline that calls a registered Capability end-to-end.

### Phase 4 — Service Authoring & business Services as Capabilities
- **End-state:** `Service_Authoring` (RC-7) designs+creates Capabilities via the shared planning pipeline (§10a). The three business Services (BS-1/2/3) are realized as Capabilities owning durable state behind a standing internal API. `Service_Composition` (RC-12) + `Capability_Management` (RC-13) govern them.
- **Deliverables:** authoring MCP tools (`design_service`, `create_service`, `compile_capability`), Service data-store schemas, API contracts for the three business Services.
- **Concrete contracts:** `SA-CONTRACTS-PHASES-2-5.md` §C11 (Service Authoring tools, shared planning-pipeline flow, compilation/promotion, business-Service callable check).
- **Exit:** the Assistant can *design and create* a new Service, register it, and a later Session can invoke it — proving the "reason, design, create, run" loop.

### Phase 5 — Learning Loop & Knowledge governance
- **End-state:** Learning Loop (anchor §13) writes playbook deltas / Concept Payloads to `Knowledge_Concept_Store` (RC-9); promotes `ai_mediated → compiled` Capabilities via `Capability_Management` (RC-13). `Knowledge_Management` (RC-14) governs concepts. `agentic_observability_platform` (RC-11) tracks cost-per-request-type, reuse hit-rate, exploration spend.
- **Concrete contracts:** `SA-CONTRACTS-PHASES-2-5.md` §C12 (Learning Loop pipeline, Knowledge governance, Token Economics telemetry).
- **Exit:** a successful novel Session becomes a reusable, promoted Capability; metrics show reuse vs exploration.

---

## 5. Open questions carried forward (not blockers)

1. **Single-registry service boundary (ADR §7 item 11):** modeled as one `Capability_Registry_Service` (RC-6) record type; the *service topology* question stays open.
2. **Canonical `workflow-runner` home (earlier gap analysis A.0.2):** pick one home before Phase 3 code; docs reference `Workflow_Engine` (RC-10) as the owner regardless.
3. **`autogen`/`crewai` removal (A.0.1):** enforce "no separate substrate" rule; CrewAI/MAF abstractions are absorbed as patterns only.

---

## 6. Validation (what "done" looks like at phase end)

- Every SBB/ABB in §1 carries an alignment/`Relationship to Cognition Model` section referencing the anchor.
- A reviewer can trace any scenario S1–S10 (anchor §14) from **Intent → Strategy → Pattern → Concept/Capability → Session → Pattern Runtime → Learning Loop** using only the anchor + these artifacts.
- The three business Services are demonstrably **Capabilities** (registered, invoked via the internal API, owning durable state) — not external consumers.
- No artifact defines a *second* service runtime; services reuse the Session/Pattern Runtime.
- The decision rule (§3) is encoded such that the designing AI selects Service vs Session vs pure Capability unambiguously.
