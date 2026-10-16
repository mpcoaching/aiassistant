# Contracts Appendix — Phases 2–5 Implementation-Ready Specifications

**Purpose:** the concrete contracts that make Phases 2–5 of `SA-NEXT-PHASE-REASONING-CORE.md` implementable with **zero architectural decisions**. Phase 1 contracts live in `SA-CONTRACTS-PHASE1.md` (C1–C8); this appendix continues the numbering (C9+) and reuses C1–C8 types.

**Grounding:** built on real `workflow-runner` code — `executor.py` (`execute_workflow`, `execute_workflow_from_file`, `get_workflow_status`), `registry.py` (`Registry`, `SkillRecord`, `resolve`, `set_implementation`, `_save_manifest`), `composer.py` (`compose_skill_prompt`, `compose_tool_command`), `scheduler.py` (`schedule_workflow`, `start_scheduler`), `models.py` (`WorkflowDefinition`, `Step`, `StepType`), `db.py` (stored-procedure persistence). Pattern/Session schemas from `SESSION-MODEL.md` / `REASONING-PATTERN-CATALOGUE.md` are reused verbatim.

**Conventions:** plain owned data; no framework types in contracts (Principle 10); all persistence via `db.py`.

---

## C9. Phase 2 — Reasoning entrypoint & Strategy Selection (RC-1, RC-3)

Builds on C3 (`recognise`) and C4 (`select_strategy`). This phase assembles the `Assistant Reasoning Service` (RC-1) intake→recognise→select pipeline and wires `agent_registry` (RC-3) participant definitions.

### C9.1 Assistant Reasoning Service — intake API
```yaml
AssistantReasoningAPI:
  POST /intents                      -> create Intent (C3); returns intent_id
  POST /intents/{id}/recognise      -> RecognitionResult (C3) — classify + candidate strategies
  POST /intents/{id}/select         -> StrategyDecision (below)
  GET  /intents/{id}                -> Intent + RecognitionResult + StrategyDecision
```
```yaml
StrategyDecision:
  intent_id: uuid
  chosen_strategy: ReasoningStrategy          # C4 enum
  pattern_pipeline: list[pattern_id]          # ordered, from StrategySelection seed / adaptation
  participant_roles: list[string]             # resolved from agent_registry (RC-3)
  proposed_session_id: uuid | null           # handed to Workflow Engine (Phase 3)
  rationale: string
```
**Interface (plain):** `decide(intent_id) -> StrategyDecision` — calls `recognise(intent)` then `select_strategy(frame)`, returns a proposed pipeline. No execution.

### C9.2 Participant resolution (agent_registry → ParticipantRecord)
```yaml
resolve_participants(roles: list[string]) -> list[ParticipantRecord]
```
Maps `agent_registry` agent definitions to `SESSION-MODEL.md` `ParticipantRecord` (`id, kind: human|agent|api|mcp|system, role, capabilities, agent_ref`). Registry functions `get_skill/get_tool/get_workflow` become `get_capability`; participant metadata lives on the Capability's `interface` + `AiSpec`.

### C9.3 Phase-2 task breakdown
| # | Task | Inputs | Output | Acceptance |
|---|---|---|---|---|
| P2.1 | Intent API + `recognise()` | C3 | `/intents` endpoints; classification to ProblemFrame | Intent → RecognitionResult with confidence + candidate strategies |
| P2.2 | `select_strategy()` + seed table | C4 | ranked `StrategyProposal` | `(incident, investigate)` → `investigate_then_fix` pipeline |
| P2.3 | `decide()` assembly | C9.1, C9.2 | `StrategyDecision` + proposed pipeline | chosen strategy yields ordered pattern ids + participants |
| P2.4 | Participant resolution | C9.2, RC-3 | `resolve_participants` | role → ParticipantRecord |
| P2.5 | Tests | C3, C4, C9 | TDD suite | 100% coverage of recognise/select/decide |

**Exit (Phase 2 done):** an Intent yields a Strategy + candidate Pattern pipeline + participants, without executing anything.

---

## C10. Phase 3 — Pattern Runtime & Session execution (RC-4, RC-10, RC-16)

Executes a `StrategyDecision` as a Session. Reuses `SESSION-MODEL.md` schema and `executor.py`.

### C10.1 Session creation from StrategyDecision
```yaml
create_session(decision: StrategyDecision) -> Session    # SESSION-MODEL.md schema
```
The `Session.pipeline` is built from `decision.pattern_pipeline` (each `pattern_id` → a `PatternStep`). Persisted via `db.py` into `WorkflowState.context` (Session block) — backward compatible with `WorkflowDefinition` (`models.py`, optional `session:` block).

### C10.2 Pattern Runtime adapter (agent_runtime, RC-4)
```yaml
PatternRuntime:
  configure_graph(step: PatternStep, context: ContextRecord) -> GraphConfig
  build(config: GraphConfig) -> CompiledGraph
  supports(step: PatternStep) -> bool
  invoke(step: PatternStep, capability_reply: CapabilityReply) -> StepStatus
```
Each `PatternStep` (`SESSION-MODEL.md`) declares `enabled_pathways` / `disabled_pathways`. The runtime resolves each step to a Capability invocation via the **C5 envelope** (`CapabilityRequest`/`CapabilityReply`); Tier 2 in-process calls `run(context)` directly (existing `handlers`/`skill_runtime`), Tier 3 publishes to `capability.mode` (C5).

### C10.3 Capability invocation during a Session
```yaml
invoke_step(step: PatternStep, session: Session) -> CapabilityReply
  # builds CapabilityRequest (C5) from step.config + session.context
  # transport = step's resolved pathway (tier2_inprocess | tier3_bus)
  # on governance gate fail -> Escalation pattern (SESSION-MODEL.md lifecycle)
```
Maps onto `executor.py`: `on_step_start` (pre-step gate: pathway check), `on_step_complete` (post-step gate) — unchanged callback hooks. `execute_workflow_from_file` remains the SOP/linear path; `execute_workflow` the generic loop.

### C10.4 Workflow Engine (RC-10) lifecycle
```yaml
POST /workflows/{name}/run  -> workflow_id (async, immediate)   # Control Center contract
GET  /workflows/{id}/status -> terminal state (completed|failed|stopped)
```
Publishes `workflow.lifecycle.started|completed|failed` (C5 topology) to `workflow.mode`. `automated_task_execution` (RC-16) = the deterministic SOP path (no exploration) used when `recognise_and_reuse` is chosen.

### C10.5 Phase-3 task breakdown
| # | Task | Inputs | Output | Acceptance |
|---|---|---|---|---|
| P3.1 | `create_session` from decision | C9.1, SESSION-MODEL | Session persisted in WorkflowState | decision → runnable Session |
| P3.2 | PatternRuntime adapter | C10.2, C5 | `invoke_step` via Tier2/Tier3 | step runs a registered Capability end-to-end |
| P3.3 | Capability invocation envelope wiring | C5, executor callbacks | `on_step_start/complete` gates | gate fail → Escalation |
| P3.4 | Workflow Engine lifecycle + events | C5, RC-10 | run/status + lifecycle events | async run returns id; events published |
| P3.5 | SOP deterministic path | RC-16, executor | `recognise_and_reuse` executes without exploration | known SOP runs, no reasoning |
| P3.6 | Tests | C10 | TDD suite | Session→Capability invocation covered |

**Exit (Phase 3 done):** a Session runs a Pattern pipeline that calls a registered Capability end-to-end; governance gates enforced; lifecycle events published.

---

## C11. Phase 4 — Service Authoring & business Services as Capabilities (RC-7, BS-1/2/3, RC-12, RC-13)

Designs and creates new Capabilities using the **shared planning pipeline** (anchor §10a). The three business Services were registered as Capabilities in Phase 1 (C7); Phase 4 adds the *authoring* path that lets the Assistant *create* new ones, plus the governance ABBs.

### C11.1 Service Authoring MCP/tools (RC-7)
```yaml
ServiceAuthoringAPI / MCP:
  design_service(need: ServiceNeed) -> ServiceDraft
  create_service(draft: ServiceDraft) -> Capability            # registers via C2
  compile_capability(capability_id: uuid) -> CompiledRef       # ai_mediated -> compiled (C2)
```
```yaml
ServiceNeed:
  intent_id: uuid                  # links to the reasoned need (C3/C9)
  description: string
  owns_data: bool                  # TRUE -> Service (durable state); FALSE -> pure Capability
  suggested_capability_kind: enum [tool | skill]
ServiceDraft:
  name: string
  capability_kind: enum [tool | skill]
  ai_spec: AiSpec                  # C2
  data_entity: DataTable | null    # if owns_data: Postgres table def (C6/C7 shape)
  api_contract: ApiContract | null # if standing_contract
  policy_checks: list[string]
```

### C11.2 Authoring flow (shared planning pipeline, anchor §10a)
```
design_service -> Planning/Research/Critique patterns produce ServiceDraft
create_service -> register_capability (C2) at execution_mode=ai_mediated, status=draft
validate      -> a validation SESSION runs the draft (Phase 3 machinery) against acceptance criteria
promote       -> status=active; Learning Loop may later compile (C11.3)
```
No separate service-building runtime — authoring reuses `decide()` (C9) + `create_session` (C10) for validation.

### C11.3 Compilation / promotion (Capability_Management, RC-13)
```yaml
compile_capability(id) -> CompiledRef       # writes module_path; tests_passed gating (distilled)
promote(id)                                # execution_mode: ai_mediated -> compiled; maturation_history.promoted_at set
```
Strict persistence: `_save_manifest` raises on failure (RUNTIME-MAPPING.md Registry Strictness). Compilation routes through the opencode Test Writer/Reviewer/Implementer roster (gap-analysis A.8) — never auto-deploy.

### C11.4 Phase-4 task breakdown
| # | Task | Inputs | Output | Acceptance |
|---|---|---|---|---|
| P4.1 | `design_service` | C11.1, C9 | ServiceDraft via Planning patterns | need → draft with ai_spec + (optional) data_entity |
| P4.2 | `create_service` | C2, C11.1 | registered Capability (draft) | new Capability discoverable in registry |
| P4.3 | validation Session | C10, C11.2 | draft exercised against acceptance | draft passes/fails validation |
| P4.4 | `compile_capability` + promotion | C2, C11.3, RC-13 | CompiledRef; status→active | compiled module imported; tests pass |
| P4.5 | Business Services callable | C7, C5 | BS-1/2/3 invoked as Capabilities via internal API | Assistant creates a Service, later Session invokes it |
| P4.6 | Governance ABBs | RC-12, RC-13 | Service_Composition + Capability_Management docs linked | governance rules encoded |
| P4.7 | Tests | C11 | TDD suite | design→create→validate→promote covered |

**Exit (Phase 4 done):** the Assistant can *design and create* a new Service, register it, and a later Session invokes it — proving the "reason, design, create, run" loop end-to-end.

---

## C12. Phase 5 — Learning Loop & Knowledge governance (anchor §13, RC-9, RC-11, RC-14)

Converts successful Sessions into reusable, promoted Capabilities/Concepts; tracks Token Economics.

### C12.1 Learning Loop pipeline (PATTERN-RECOGNITION-ASSIMILATION.md)
```
Session close (distillation_hook.enabled) -> Learning pattern
  -> playbook_delta / ConceptPayload (kind=solved_approach, C1)
  -> register via C2 (status=draft) or update existing
  -> if >=3 successful executions + eval pass + no governance violations:
       promote to production_ready / compiled (C11.3)
```
```yaml
LearningEvent:
  session_id: uuid
  outcome: enum [success | failure]
  pattern_usage: list[pattern_id]
  playbook_delta: ConceptPayload | null     # C1
  proposed_capability: uuid | null
```

### C12.2 Knowledge governance (Knowledge_Management, RC-14)
```yaml
upsert_concept(concept: EnterpriseConcept) -> id          # C1
promote_concept(id, to_status)                            # draft -> active (audit sampling)
route_knowledge_chunk(chunk: KnowledgeChunkDiscovered)     # C5 -> store by semantic_tags
```
Routes `KnowledgeChunkDiscovered` (C5) to Postgres (`enterprise_concepts`), Qdrant (embeddings), or repo markdown (authored docs) per C6 routing rule.

### C12.3 Token Economics (agentic_observability_platform, RC-11)
```yaml
TelemetryEvent:
  request_type: enum [recognition | strategy_select | pattern_step | capability_call | exploration]
  token_cost: int
  duration_ms: int
  reuse_hit: bool                  # direct reuse vs novel
  exploration_spend: int           # tokens on Level 3 synthesis
```
Dashboards: **cost-per-request-type**, **reuse hit-rate**, **exploration spend** (ADR §16). Feeds the exploration/headroom policy (gap-analysis A.6).

### C12.4 Phase-5 task breakdown
| # | Task | Inputs | Output | Acceptance |
|---|---|---|---|---|
| P5.1 | Learning pipeline on Session close | C12.1, C1, C2 | ConceptPayload / Capability draft written | successful Session → enterprise asset |
| P5.2 | Promotion gate | C11.3, C12.1 | production_ready / compiled | >=3 successes → promotion |
| P5.3 | Knowledge governance | C12.2, C6 | concept upsert + chunk routing | chunk routes to correct store |
| P5.4 | Token Economics | C12.3, RC-11 | telemetry capture + dashboards | cost/reuse/exploration visible |
| P5.5 | Tests | C12 | TDD suite | learning + promotion + routing covered |

**Exit (Phase 5 done):** a successful novel Session becomes a reusable, promoted Capability; Knowledge graph grows; metrics show reuse vs exploration.

---

## C13. Cross-phase consistency & full end-to-end trace

**One invocation seam (C5):** every Capability — tool, skill, Service, or a `workflow`-implemented Capability — is called through `CapabilityRequest`/`CapabilityReply` (Tier 2 in-process or Tier 3 bus). "Workflow calling workflow" = a Capability invocation of a `workflow`-implemented Capability. No second runtime.

**End-to-end trace (S1 incident, anchor §14):**
```
Intent(user alert) -> C3 recognise -> ProblemFrame(incident, investigate)
  -> C4 select_strategy -> investigate_then_fix -> pipeline [Investigation, SOP, HumanApproval, Verification]
  -> C9 decide -> StrategyDecision + participants
  -> C10 create_session + invoke_step (each step = C5 CapabilityRequest to a registered Capability)
       Investigation (tier3 bus -> capability worker) -> SOP (tier2 inprocess) -> HumanApproval (interrupt) -> Verification
  -> C12 Session close -> LearningEvent -> ConceptPayload(solved_approach) registered (C2)
  -> future: same incident -> C3 Level-1 reuse -> recognise_and_reuse (no exploration)
```

**Locked decisions honoured throughout:**
- Workflow = Session; Service = Capability (anchor §1a).
- Capabilities built via the same planning pipeline as workflows (§10a).
- Single Capability type system; Concept Payload and Capability share `EnterpriseConcept` (C1).
- Map, don't rename — existing `workflow-runner` modules extended, not forked.
- No framework types in contracts (Principle 10).

**Open questions NOT blocking (carried forward):** ADR §7 item 11 (registry *topology*), A.0.2 (canonical `workflow-runner` home), A.0.1 (`autogen`/`crewai` removal rule). All are out of scope for contracts; record shapes (C1/C2) are mandated regardless.
