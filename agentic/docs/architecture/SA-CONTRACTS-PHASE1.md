# Contracts Appendix — Phase 1 Implementation-Ready Specifications

**Purpose:** close the gap between the solution-architecture plan (`SA-NEXT-PHASE-REASONING-CORE.md`) and implementable code. This appendix contains the concrete **contracts** (record schemas, interfaces, envelopes, topologies) that Phase 1 must build. Where the existing `workflow-runner` code already defines a structure, this appendix maps onto it rather than inventing a parallel one.

**Scope of this appendix:** everything Phase 1 needs so an implementer makes **zero architectural decisions**. Phases 2–5 reference these contracts but add their own (documented separately when those phases start).

**Conventions:**
- Plain owned data only. No framework types (LangGraph/CrewAI/MAF) reach into these contracts (Principle 10).
- All persistence routes through `db.py` (Postgres stored procedures; `.wf/` file fallback). No inline SQL.
- Canonical anchor: `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`.

---

## C1. Enterprise Concept type system (the one type system)

Every durable enterprise asset is an `EnterpriseConcept` record, discriminated by `kind`. Two kinds are in scope for Phase 1: `capability` and `solved_approach`. (Others — `adr`, `playbook`, `policy` — reuse the same base and are added later.)

```yaml
EnterpriseConcept:
  id: uuid                         # unique per record
  kind: enum [capability | solved_approach | adr | playbook | policy]
  name: string                     # stable, human-readable; unique per (kind, version_major)
  version_major: int               # breaking change to shape/contract
  version_minor: int               # additive (new optional field)
  version_patch: int               # correction
  status: enum [draft | active | deprecated]
  description: string
  owner: string                    # service / persona accountable
  created_by: string               # user | system | assistant_reasoning
  created_at: datetime
  tags: list[string]               # semantic tags for Knowledge routing
  provenance:                     # how this concept came to exist
    source_session_id: uuid | null
    recognition_level: enum [direct_reuse | adaptation | synthesis] | null
  payload: ConceptPayload          # shape depends on `kind` (below)
```

**Discriminated payloads (Phase 1):**

```yaml
# kind = solved_approach  (a Concept Payload)
ConceptPayload:
  approach: string                 # the reusable, proven approach (markdown/reference)
  inputs: list[string]
  outputs: list[string]
  success_criteria: list[string]
  governance_gates: list[GateSpec]   # reuse GateSpec from SESSION-MODEL.md
  reuse_count: int                 # incremented on each direct reuse
  last_reused_at: datetime | null

# kind = capability  (see C2)
CapabilityPayload:
  <see C2 Capability record>
```

**Persistence:** `enterprise_concepts` table (Postgres, via `db.py` stored procedure `upsert_enterprise_concept`, `get_enterprise_concept`, `list_enterprise_concepts_by_kind`). Semantic tags indexed into Qdrant for similarity retrieval.

---

## C2. Capability record (unified Capability Registry)

A Capability is an `EnterpriseConcept` with `kind=capability`. Its payload is the `CapabilityPayload`. This is the single registry record shape (the single-registry intent; ADR §7 item 11 open on *service topology*, not on *record shape*).

```yaml
Capability:
  # --- EnterpriseConcept base fields (C1) ---
  id: uuid
  kind: const[capability]
  name: string                     # unique per (name, version_major)
  version_major: int
  version_minor: int
  version_patch: int
  status: enum [draft | active | deprecated]
  description: string
  owner: string
  created_by: string
  created_at: datetime
  tags: list[string]
  provenance: Provenance

  # --- Capability-specific ---
  capability_kind: enum [tool | skill]      # the `kind: tool|skill` from the anchor
  execution_mode: enum [ai_mediated | compiled]   # remap of prompt|code|distilled
  ai_spec: AiSpec | null              # present when execution_mode = ai_mediated
  compiled_ref: CompiledRef | null    # present when execution_mode = compiled
  transport: enum [tier2_inprocess | tier3_bus]   # how it is invoked (ADR §6.2)
  interface: CapabilityInterface      # input/output contract
  maturation_history: MaturationHistory   # drives promotion
  policy_checks: list[string]         # mandatory governance checks before invocation
  owns_durable_state: bool            # TRUE => this is a Service (anchor §1a)
  standing_contract: bool             # TRUE => has a stable API others depend on
```

```yaml
AiSpec:
  purpose: string
  inputs: list[Parameter]
  outputs: list[Parameter]
  constraints: list[string]
  prompt_template_ref: string | null  # markdown spec, e.g. agentic/skills/<name>.md

CompiledRef:
  module_path: string                 # importable module, e.g. agentic/skills/_compiled/<name>.py
  entrypoint: const[run]              # unified run(context) contract (ai-orchestration-design.md §3)
  tests_passed: bool                  # gating for promotion (distilled)

CapabilityInterface:
  inputs: list[Parameter]
  outputs: list[Parameter]
  errors: list[string]

Parameter:
  name: string
  type: string                       # json-schema-ish primitive name
  required: bool
  description: string

MaturationHistory:
  invocation_count: int
  correction_count: int              # failed/rolled-back invocations
  last_invoked_at: datetime | null
  promoted_at: datetime | null
  promotion_candidacy: bool          # set when maturation crosses threshold (compile gate)
```

**Mapping to existing code:** extends `registry.py`'s `SkillRecord` (`name, kind, implementation, spec_path, module_path, inputs, outputs, version`). `implementation: prompt|code|distilled` maps to `execution_mode: ai_mediated|compiled` as: `prompt→ai_mediated`, `code→compiled`, `distilled→compiled`. `KINDS=(skill,tool,workflow)` becomes `capability_kind: tool|skill` + the separate `EnterpriseConcept.kind=capability`. The existing `registry.py` functions (`register_skill`, `get_skill`, `resolve`) become `register_capability`, `get_capability`, `resolve_capability(name, capability_kind)`.

**Registry responsibilities (Phase 1):** `register_capability`, `get_capability(id)`, `resolve(name, capability_kind) -> Capability`, `list_capabilities(kind?, tag?)`, `record_invocation(id, outcome)`, `promote(id)` (sets `execution_mode=compiled` after gate). Strict persistence: write failure raises (per `RUNTIME-MAPPING.md` Registry Strictness — `_save_manifest` must raise, not ignore).

---

## C3. Intent intake contract (Assistant Reasoning Service entrypoint)

The first interface of the system. An Intent is origin-agnostic (user request / scheduled job / bus event / alert).

```yaml
Intent:
  id: uuid
  origin: enum [user_request | scheduled_job | bus_event | alert]
  received_at: datetime
  declared_context: ContextRecord | null   # optional user override (highest precedence)
  raw:                               # origin-specific payload
    type: enum [natural_language | structured | event_ref]
    text: string | null
    structured: map | null
    event_id: string | null
  requested_strategy: enum[ReasoningStrategy] | null   # optional hint
```

```yaml
# Response from intake + recognition (handed to Strategy Selection)
RecognitionResult:
  intent_id: uuid
  problem_frame: ProblemFrame        # resolved ContextRecord
  confidence: float                   # 0..1
  recognition_level: enum [direct_reuse | adaptation | synthesis]
  candidate_strategies: list[StrategyProposal]   # ranked
```

```yaml
ProblemFrame:                        # = resolved workflow context (anchor §1)
  context: ContextRecord             # from ENTERPRISE-CONTEXT-MODEL.md
  inferred_vs_declared: map          # field-level provenance
```

**Interface (plain function / API):**
```
recognise(intent: Intent) -> RecognitionResult
```
No LLM token cost at intake for classification where a rule/embedding path exists (anchor §10a / gap-analysis A.4 intent: recognition is cheap).

---

## C4. Strategy Selection interface (first-class capability, v1 seed)

```yaml
enum ReasoningStrategy:
  recognise_and_reuse        # known SOP / direct reuse; no exploration
  investigate_then_fix       # incident / unknown root cause
  deliberate_to_consensus    # design / decision needing stakeholders
  research_to_synthesis      # novel problem, no direct match
  verify_and_assimilate      # compliance / learning outcome
```

```yaml
StrategyProposal:
  strategy: ReasoningStrategy
  confidence: float
  seed_patterns: list[pattern_id]    # from the static mapping table (anchor §6)
  rationale: string
```

```yaml
# Interface
select_strategy(frame: ProblemFrame) -> list[StrategyProposal]   # ranked
```
**v1 seed data:** the static Context→Pattern table from anchor §6, encoded as a lookup keyed by `(problem_context, activity_purpose)`. Later versions replace the table with a learned selector; the interface is stable.

---

## C5. Capability invocation envelope (Tier 2 / Tier 3) + Event Bus topology

The single invocation seam. Every step in a Session that calls a Capability uses these envelopes.

```yaml
CapabilityRequest:
  request_id: uuid
  correlation_id: uuid               # for bus durability / step progression
  capability_id: uuid               # resolved Capability
  capability_name: string
  inputs: map                        # matches CapabilityInterface.inputs
  caller_session_id: uuid | null
  transport: enum [tier2_inprocess | tier3_bus]
  timeout_seconds: int
  context_ref: string | null        # WorkflowState.context key

CapabilityReply:
  request_id: uuid
  correlation_id: uuid
  status: enum [completed | approved | rejected | escalated | failed]
  outputs: map
  artifacts: list[string]            # enterprise asset store refs
  telemetry: map                     # duration, token_cost, provider_id
  error: string | null
```

**Event Bus topology (`Event_Bus` SBB, RC-8):**

| Exchange / Topic | Routing key | Payload | Publisher | Consumer |
|---|---|---|---|---|
| `workflow.mode` | `workflow.lifecycle.started` | `WorkflowLifecycleEvent` | Workflow Engine | UI, Observability, Learning |
| `workflow.mode` | `workflow.lifecycle.completed` | `WorkflowLifecycleEvent` | Workflow Engine | UI, Observability, Learning |
| `workflow.mode` | `workflow.lifecycle.failed` | `WorkflowLifecycleEvent` | Workflow Engine | Observability, Learning |
| `capability.mode` | `capability.request` | `CapabilityRequest` (Tier 3) | Session step | Capability worker |
| `capability.mode` | `capability.reply` | `CapabilityReply` (Tier 3) | Capability worker | Session step (correlation_id) |
| `knowledge.mode` | `knowledge.chunk.discovered` | `KnowledgeChunkDiscovered` | any producer | Knowledge subscriber → store router |
| `agent.mode` | `agent.task.started|completed|failed` | `AgentTaskEvent` | Agent Orchestrator | Observability |

```yaml
KnowledgeChunkDiscovered:
  chunk_id: uuid
  semantic_tags: list[string]        # routes to store
  payload_ref: string                # where the chunk lives
  source: enum [session | capability | external]
  source_ref: string
```

**Routing rule (Knowledge subscriber):** `semantic_tags` → store: `kind=solved_approach|adr|playbook|policy` → Postgres `enterprise_concepts`; `embedding|similarity` → Qdrant; `authored_doc` → repo markdown. (anchor §9.2)

**Tier 2 (in-process):** `CapabilityRequest` resolved directly to the module's `run(context)` (no bus). Tier 3 (bus-mediated): published to `capability.mode`, correlated reply consumed. Both use the identical envelope — the only difference is transport.

---

## C6. Knowledge & Concept Store schema (RC-9)

```yaml
# Postgres tables (via db.py stored procedures)
enterprise_concepts:                 # C1 base + C2 Capability fields, JSONB payload
  columns: id, kind, name, version_major, version_minor, version_patch,
           status, description, owner, created_by, created_at, tags(jsonb),
           provenance(jsonb), payload(jsonb)
  procedures: upsert_enterprise_concept, get_enterprise_concept,
              list_enterprise_concepts_by_kind, list_enterprise_concepts_by_tag

concept_relations:                   # the epistemic graph edges
  columns: from_id, to_id, relation_type, weight, created_at

maturation_history:                 # C2 MaturationHistory (own table or jsonb on capability)
  columns: capability_id, invocation_count, correction_count,
           last_invoked_at, promoted_at, promotion_candidacy

knowledge_chunks:                   # ingestion log for KnowledgeChunkDiscovered
  columns: chunk_id, semantic_tags(jsonb), payload_ref, source, source_ref, created_at
```

**Qdrant:** collection `enterprise_knowledge` — vectors of concept `description`+`tags`, payload = `concept_id`, enabling Level 1 similarity lookup during Recognition.

**Store procedures (Phase 1):** `upsert_enterprise_concept`, `get_enterprise_concept`, `list_enterprise_concepts_by_kind`, `list_enterprise_concepts_by_tag`, `record_invocation`, `upsert_concept_relation`, `insert_knowledge_chunk`.

---

## C7. The three business Services as Capabilities (BS-1/2/3) — Phase 1 data + API contracts

Each is a `Capability` with `owns_durable_state=true`, `standing_contract=true`, `capability_kind=tool` (a service), `transport=tier3_bus` (called via internal API). Their SBBs own the durable entity tables; the Capability record points at them.

### Work Session Service (BS-1)
```yaml
Data entity (Postgres, via db.py): work_sessions
  columns: session_id(uuid), user_id, objectives, start_time, end_time,
           outcomes, learnings, status
API (internal, on Agent Bus / REST):
  POST   /sessions              -> create Work Session (CapabilityReply.outputs.session_id)
  PUT    /sessions/{id}/close  -> close, capture outcomes/learnings
  GET    /sessions/{id}         -> retrieve
  GET    /sessions              -> list by user
Events: WorkSessionStarted, WorkSessionClosed (-> workflow.mode lifecycle or agent.mode)
```
Capability record: `name=work_session`, `owns_durable_state=true`, `standing_contract=true`.

### Task Tracking Service (BS-2)
```yaml
Data entity: tasks
  columns: task_id(uuid), user_id, description, status, priority, due_date, work_session_id
API:
  POST   /tasks
  GET    /tasks/{id}
  PUT    /tasks/{id}
  PATCH  /tasks/{id}/status
  DELETE /tasks/{id}
  GET    /tasks
Events: TaskCreated, TaskStatusUpdated, TaskCompleted
```
Capability record: `name=task_tracking`, `owns_durable_state=true`, `standing_contract=true`.

### Lead Enrichment Service (BS-3)
```yaml
Data entity: lead_profiles
  columns: lead_id(uuid), raw_data(jsonb), enriched_data(jsonb), suggestions(jsonb), created_at
API:
  POST   /leads/enrich        -> submit raw; returns lead_id (async, long-running)
  GET    /leads/{id}
  GET    /leads
Events: LeadEnriched, LeadSuggestionGenerated
Note: invokes EXTERNAL-tool Capabilities (Clearbit etc.) as tier3_capability calls; those externals are themselves Capabilities (capability_kind=tool, transport=tier3_bus to external gateway).
```
Capability record: `name=lead_enrichment`, `owns_durable_state=true`, `standing_contract=true`.

> These three are **registered in `Capability_Registry_Service`** (C2) at Phase 1 so the Assistant can discover and invoke them as Capabilities. Their durable tables are owned by their SBBs; the Capability record is the discovery/invocation handle.

---

## C8. Phase 1 build breakdown (fully specified — no decisions left)

Phase 1 delivers: `Capability_Registry_Service` (RC-6) + `Knowledge_Concept_Store` (RC-9) + `Event_Bus` (RC-8) + the three business Services registered as Capabilities (BS-1/2/3). No LangGraph import; pure data + ports.

| # | Task | Inputs (this appendix) | Output | Acceptance |
|---|---|---|---|---|
| P1.1 | `EnterpriseConcept` model + store procedures | C1, C6 | `db.py` procedures `upsert/get/list_enterprise_concepts_*` | round-trip upsert/get; `.wf/` fallback works |
| P1.2 | `Capability` record + Registry service | C2, C6 | `register/get/resolve/record_invocation/promote` | register a `tool` capability; resolve by name; strict-write raises on failure |
| P1.3 | `Capability` mapping from existing `SkillRecord` | C2 + `registry.py` | migration/adapter `SkillRecord→Capability` | existing skills load as `execution_mode=ai_mediated` capabilities |
| P1.4 | Event Bus topology | C5 | `bus.py` exchanges/routing keys + `KnowledgeChunkDiscovered` subscriber | publish/consume `capability.request/reply`; chunk routes to correct store by tag |
| P1.5 | Knowledge & Concept Store | C1, C6, C5 | Postgres tables + Qdrant collection + procedures | `KnowledgeChunkDiscovered` ingested; Level-1 similarity lookup returns concept |
| P1.6 | Three business Services as Capabilities | C7 | data tables + internal APIs + Capability registrations | each service registered; Assistant can resolve + invoke via internal API; durable entity persists |
| P1.7 | Contracts test harness | C1–C7 | TDD suite per contract (behaviour-based, externals mocked) | 100% contract coverage per test_standards.md |

**Exit criteria (Phase 1 done):** a Capability can be registered and resolved; a `KnowledgeChunkDiscovered` event routes to the correct store; the three business Services are discoverable Capabilities whose durable entities persist and whose internal API is callable. No implementer made an architectural decision — all shapes are in C1–C7.

---

## Open questions explicitly NOT blocking Phase 1
- ADR §7 item 11 (Tool vs Agent Registry *service topology*): record shape is unified in C2; topology deferred.
- Canonical `workflow-runner` home (A.0.2): Phase 1 uses `agentic/src/workflow-runner` (`db.py`, `registry.py`); `packages/workflow-runner` is the future canonical home — no code change needed now.
- `autogen`/`crewai` removal (A.0.1): enforced as a rule; no separate substrate in C2/C5.
