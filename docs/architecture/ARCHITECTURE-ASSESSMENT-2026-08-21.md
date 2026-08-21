# Architectural Assessment: Control Centre Assistant
**Date:** 2026-08-21  
**Status:** Pre-implementation review  
**Purpose:** Establish architectural direction for the Assistant before further implementation

---

## A. Current Architecture Assessment

### What exists and is proven

| Component | State | Evidence |
|---|---|---|
| **Infrastructure stack** | Production-grade, isolated 4-network Docker architecture | `docs/architecture.md` |
| **CI/CD** | Woodpecker CI builds, tests, pushes, and deploys all images | Pipelines #165+ passing |
| **Control Center UI** | Deployed, reachable at `https://control-center.local.test` | Live container `dev_control_center_ui` |
| **Workflow Engine API** | Deployed, reachable at `https://control-center.local.test/api` → `dev_workflow_engine:8000` | Live container |
| **LangGraph runtime** | Implemented as `PathwayRuntime` adapter (`packages/langgraph/src/langgraph_runtime.py`) | Importable, container starts |
| **Capability Registry** | Implemented with `SkillRecord`, `Registry`, strict persistence | 8 passing tests |
| **Concept Store** | Implemented with `EnterpriseConcept`, Qdrant + Postgres + file fallback | 7 passing tests |
| **Session model** | Implemented (`packages/workflow_runner/src/session.py`) | Importable |
| **Assistant Chat API** | Endpoint `POST /assistant/chat` returns JSON | Tested via curl |
| **Workflow routing boundary** | Proven with tests (`test_workflow_router.py`, etc.) | Test suite passes |
| **Configuration management** | Implemented with providers, validation, contracts | Tests pass |

### What is wired but not yet useful

| Component | State | Gap |
|---|---|---|
| **AssistantChatService** | Returns generic "Done" responses | No LLM integration, no real execution |
| **Intent classification** | Rule-based keyword matching | Low confidence, no learning |
| **Strategy selection** | Static lookup table | Not evolvable yet |
| **LangGraph runtime** | Invokes stub graphs | No real pattern bundles, no agent roles |
| **Concept store** | Empty, no seeded knowledge | No prior solutions to retrieve |
| **Memory tiers** | Working memory only (LangGraph checkpoints) | No episodic/semantic/insight layers |
| **Learning loop** | Not implemented | No pattern promotion, no playbook deltas |
| **C-Suite agents** | Not implemented | No CEO, COO, CTO, etc. |
| **Tool execution** | Not implemented | No `create_spreadsheet`, `send_email`, etc. |
| **Artifact creation** | Not implemented | No spreadsheets, docs, tickets |
| **Self-extension cycle** | Not implemented | No spec→code→deploy automation |

### What is documented but not built

The architecture documentation is extensive and high-quality:

- `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` — canonical reference
- `RUNTIME-MAPPING.md` — LangGraph substrate, framework analysis
- `ENTERPRISE-CONTEXT-MODEL.md` — 5 orthogonal context dimensions
- `REASONING-PATTERN-CATALOGUE.md` — 14 pattern types
- `SESSION-MODEL.md` — session lifecycle
- `PATTERN-RECOGNITION-ASSIMILATION.md` — learning loop
- `agentic/docs/context/ea/ARCHITECTURE.md` — C-Suite model, memory tiers, build order
- `docs/architecture/adr/` — ADR-011, ADR-012 (incomplete)

**Gap:** The architecture is 12–18 months ahead of the implementation. The risk is not architectural vision; it is implementation focus and incremental proof.

---

## B. Architectural Vision

### Consolidated model

The system is an **AI-enabled organisational operating system** with five conceptual layers:

```
HUMAN INTERFACE (Control Centre)
    ↓
ASSISTANT (Intent → Context → Strategy → Decision)
    ↓
CONTROL PLANE (Governance, priorities, delegation)
    ↓
WORKFORCE (Roles, capabilities, skills, tools, teams)
    ↓
EXECUTION (Deterministic workflows, AI patterns, agentic reasoning)
    ↓
INFORMATION & LEARNING (Concepts, knowledge, memory, insights)
```

### Core principles (from existing docs, consolidated)

1. **Recognition before reasoning** — have we solved this before?
2. **Reason only when uncertainty exists** — known patterns run deterministically
3. **Enterprise assets are first-class** — concepts, decisions, playbooks outlive agents
4. **Context determines behaviour** — five orthogonal dimensions drive everything
5. **Reasoning patterns are composable** — bundles, not monoliths
6. **Sessions define interaction rules** — bounded execution, not open-ended chat
7. **Frameworks are runtimes, not architecture** — LangGraph is a substrate
8. **Continuously convert reasoning into deterministic execution** — learning loop
9. **Learning updates enterprise assets, not individual agents** — organisational memory
10. **Preserve architectural freedom through stable abstractions** — no framework leakage

### The intended behaviour

When a human makes a request:

1. **Understand** — classify intent into problem frame
2. **Recall** — check concept store for prior solutions
3. **Decide** — select reasoning strategy (reuse / investigate / deliberate / research / verify)
4. **Discover** — check if a capability exists for this
5. **Execute** — run the appropriate pattern (workflow, agent, tool, or human)
6. **Record** — store the outcome as an enterprise concept
7. **Learn** — update patterns, capabilities, and knowledge

If capability is missing: **produce a structured capability request**, not a generic failure.

---

## C. Domain Boundaries

### 1. Human Interface / Assistant

**Responsibility:** Accept natural language, manage conversation state, render results.  
**Does NOT:** Execute work, decide strategy, own enterprise knowledge.  
**Boundary:** `AssistantChatService` + Control Center UI.  
**Interface:** `POST /assistant/chat` with `ChatRequest` / `ChatResponse`.

### 2. Enterprise / Operational Control Plane

**Responsibility:** Governance, priorities, delegation decisions, human approval gates, escalation.  
**Does NOT:** Execute individual tasks, own tools, run patterns.  
**Boundary:** `WorkflowConfirmationService`, `WorkflowAssistanceService`, governance gates in `PatternStep`.  
**Interface:** Approval/rejection/escalation events on Agent Bus.

### 3. Agent Workforce / People & Capability

**Responsibility:** Role definition, capability registry, skill discovery, tool provisioning, workload, performance.  
**Does NOT:** Execute deterministic workflows, own enterprise knowledge, govern decisions.  
**Boundary:** `CapabilityRegistry`, `ConceptStore` (capability metadata), `Registry` (skill/tool/workflow catalog).  
**Interface:** Capability lookup, registration, maturation/promotion.

### 4. Execution

**Responsibility:** Run the work — deterministic workflows, AI patterns, agentic reasoning, composite workflows.  
**Does NOT:** Decide what to run, own enterprise knowledge, govern.  
**Boundary:** `PatternRuntime` (LangGraph adapter + workflow-runner adapter), `Session`, `PatternStep`.  
**Interface:** `PathwayCallRequest` → `PathwayResponse`.

### 5. Enterprise Information & Learning System

**Responsibility:** Facts, decisions, playbooks, concepts, observations, hypotheses, learnings, relationships, provenance.  
**Does NOT:** Execute, govern, interface directly with humans.  
**Boundary:** `ConceptStore`, Qdrant (semantic layer), Postgres (structured), repo markdown (authored docs).  
**Interface:** Query API (by kind, tag, similarity), write API (learning loop).

### 6. Context Engine

**Responsibility:** Make architectural decisions, requirements, constraints, domain models, and implementation state retrievable by AI and humans.  
**Does NOT:** Execute, govern, own business knowledge.  
**Boundary:** Architecture docs, ADRs, context files in `.kilo/` and `agentic/docs/`.  
**Interface:** Structured markdown with back-references, indexed by topic.

### 7. Skills & Tools

**Responsibility:** Atomic executable units. Skills are prompt-based; tools are code-based.  
**Does NOT:** Compose into workflows, own state, govern.  
**Boundary:** Registry entries (`kind=skill|tool`), MCP server exposure.  
**Interface:** MCP protocol, internal agentic API.

### 8. AI / Agent Runtime

**Responsibility:** Execute LLM calls, manage agent state, run LangGraph graphs.  
**Does NOT:** Own architecture, govern, store enterprise knowledge.  
**Boundary:** LangGraph substrate, Portkey AI gateway.  
**Interface:** `PathwayRuntime` adapter interface.

---

## D. Paperclip Assessment

### What Paperclip provides

Based on public documentation and architectural analysis:

| Paperclip Concept | What it actually is | Fit |
|---|---|---|
| **Agent / Team** | YAML-defined role with prompt, tools, and model | Partial — maps to `ParticipantRecord` + `PatternStep` role config |
| **Task / Workflow** | YAML-defined sequence with agent assignments | Partial — maps to `Session` + `PatternStep` pipeline |
| **Tool exposure** | MCP server or inline function | Good — maps to `Capability` (`kind=tool`) |
| **Memory / Context** | Per-agent conversation history | Partial — maps to Session working memory |
| **Meetings / Coordination** | Structured multi-agent dialogue | Absorbed — Debate/Consensus patterns in catalogue |
| **Agent lifecycle** | Not present in Paperclip | Gap — our `CapabilityRegistry` + `ConceptStore` own this |
| **Deterministic workflows** | Not Paperclip's concern | Our `workflow-runner` substrate |
| **Enterprise knowledge** | Not Paperclip's concern | Our `ConceptStore` + Knowledge graph |
| **Governance** | Not Paperclip's concern | Our `PatternStep` governance gates |

### Assessment

**Paperclip is a candidate implementation for the `PathwayRuntime` adapter layer** — specifically for running multi-agent pattern steps where role-play and tool-use are needed.

It is **NOT** our domain model, our workforce abstraction, or our information system.

### Recommendation

**Do not integrate Paperclip yet.**

Reasons:
1. The `PathwayRuntime` interface already exists and LangGraph is the designated substrate.
2. Paperclip's agent model maps to LangGraph nodes + `ParticipantRecord` configuration.
3. Adding Paperclip now would introduce a second runtime substrate before the first is proven.
4. The architecture explicitly states: "Frameworks are runtimes, not architecture" (Principle 7).

**When to reconsider:** After the first vertical slice proves the Intent → Context → Strategy → Session → Execution → Learning loop, and if a specific pattern step requires role-play coordination that LangGraph nodes cannot express cleanly.

### ADR: Paperclip as Agent Workforce Implementation

**Status:** Rejected for current implementation.  
**Decision:** Paperclip is not adopted as an architectural component.  
**Rationale:** The existing `PathwayRuntime` abstraction + LangGraph substrate already covers the execution layer. Paperclip's value-add (role-based crews, meetings) maps to PatternStep configuration, not a separate runtime. Introducing it would violate Principle 7 and add operational complexity before the core loop is proven.  
**Consequence:** If a future pattern requires Paperclip-specific capabilities, it will be introduced as a `PathwayRuntime` adapter implementation, not as a domain dependency.

---

## E. Enterprise Information & Learning Architecture

### Conceptual model

The Enterprise Information & Learning System is a **relational epistemic graph**, not a vector database or document store.

**Core entities:**

| Entity | Description | Store |
|---|---|---|
| `EnterpriseConcept` | Central noun — every enduring asset | Postgres |
| `ConceptKind` | Discriminator: `solved_approach`, `tool`, `skill`, `adr`, `policy`, `playbook` | Postgres |
| `KnowledgeChunk` | Semantic unit — observation, hypothesis, learning | Qdrant + Postgres |
| `Relationship` | Directed edge: `Objective → depends_on → Capability → performed_by → Agent → uses → Skill` | Postgres |
| `Provenance` | Who/when/why something was created or changed | Postgres |
| `MaturationHistory` | Invocation count, corrections, promotions | Postgres |

### Relationship model

```
Objective
  └─ depends_on ──► Capability
                      ├─ performed_by ──► Role
                      ├─ uses ──► Skill
                      │              └─ uses ──► Tool
                      ├─ produces ──► Outcome
                      │                  └─ generates ──► Observation
                      │                                     └─ informs ──► Hypothesis
                      │                                                      └─ leads_to ──► Experiment
                      │                                                                          ──► Learning
                      └─ owned_by ──► Agent/Role
```

**Key queries the system must support:**
- "What is connected to this?" — graph traversal
- "Who owns this?" — ownership provenance
- "What capabilities are affected?" — dependency impact
- "What decisions led us here?" — decision lineage
- "What have we tried before?" — historical retrieval
- "What happened?" — session/outcome trace
- "What did we learn?" — learning loop outcomes
- "Where are similar problems occurring?" — semantic similarity
- "Where are the likely levers?" — capability influence analysis

### Hybrid storage architecture

| Data Type | Primary Store | Rationale |
|---|---|---|
| Structured concepts, relationships, provenance | Postgres | ACID, queryable, relational |
| Semantic memory, embeddings, similarity | Qdrant | Vector graph layer |
| Authored docs, ADRs, policies | Repo markdown | Versioned, reviewable |
| Session state, checkpoints | Postgres + LangGraph checkpoint | Durable execution state |
| Working memory | LangGraph state | Transient, per-session |

### Current state

- `ConceptStore` exists and is tested (7 tests pass)
- Qdrant is deployed on platform-network
- Postgres is deployed with per-environment databases
- **Gap:** No relationship/provenance layer beyond flat `tags` on `EnterpriseConcept`
- **Gap:** No graph traversal queries
- **Gap:** No `KnowledgeChunk` entity or `KnowledgeChunkDiscovered` event handler

---

## F. Capability Lifecycle

### End-to-end flow

```
NEED IDENTIFIED
    ↓
CAPABILITY GAP (structured request)
    ↓
SPECIFICATION (inputs, outputs, skills, tools, security, acceptance criteria)
    ↓
BUILD (scaffold, implement, test)
    ↓
TEST (contract tests, integration tests, acceptance tests)
    ↓
REGISTER (Capability Registry entry, `kind=tool|skill`)
    ↓
DEPLOY (immutable image tag, promote through environments)
    ↓
USE (invoked via PatternStep, Agent Bus, or REST API)
    ↓
MEASURE (telemetry: duration, token cost, success rate, governance violations)
    ↓
LEARN (pattern recognition, playbook deltas, Concept Payload promotion)
    ↓
IMPROVE (refined capability, updated skill, promoted to `compiled` tier)
```

### Current state

- **Need identification:** Manual (human identifies gap)
- **Gap detection:** Not implemented — Assistant returns generic failure
- **Specification:** Not implemented — no structured capability request format
- **Build:** Manual (Kilo / opencode)
- **Test:** Manual (pytest)
- **Register:** Implemented (`CapabilityRegistry.upsert()`)
- **Deploy:** Implemented (CI/CD pipeline)
- **Use:** Partial (registry lookup works; invocation is stub)
- **Measure:** Partial (Langfuse traces LLM calls; no capability-level telemetry)
- **Learn:** Not implemented (no learning loop)
- **Improve:** Not implemented (no pattern promotion)

### First vertical slice should prove

The system can: **detect a gap → produce a structured capability request → register a capability → invoke it → record the outcome.**

---

## G. Traceability Model

### Requirement → Outcome traceability

```
BUSINESS REQUIREMENT
    ↓
BUSINESS CAPABILITY (e.g. "Track daily tasks")
    ↓
OPERATING MODEL (how the capability is realised: Service, Workflow, Agent)
    ↓
DOMAIN MODEL (entities, relationships, invariants)
    ↓
ARCHITECTURE DECISION (ADR: why this approach)
    ↓
APPLICATION COMPONENT (which service/module implements it)
    ↓
IMPLEMENTATION (code, tests, deployment)
    ↓
TEST (contract, integration, acceptance)
    ↓
OBSERVATION (telemetry, Langfuse traces, session outcomes)
    ↓
LEARNING (playbook delta, Concept Payload, pattern promotion)
```

### Current state

- **Business requirements:** Not formally captured in architecture docs
- **Business capabilities:** Implied in ROADMAP.md (Phase 1 deliverables)
- **Operating model:** Partially defined (Service vs Workflow in REFERENCE ARCHITECTURE §1a)
- **Domain model:** Partially defined (Enterprise Concept, Context Record, Session)
- **Architecture decisions:** 2 ADRs (incomplete numbering)
- **Application components:** Implemented but not documented as architecture
- **Implementation:** In progress
- **Test:** Partial (34 tests pass for core reasoning/capability)
- **Observation:** Partial (Langfuse for LLM, no capability telemetry)
- **Learning:** Not implemented

---

## H. Architecture Decisions

### ADR-001: LangGraph as Single Execution Substrate
**Status:** Accepted (implicit in RUNTIME-MAPPING.md)  
**Decision:** LangGraph is the sole runtime substrate for all pattern execution. The `workflow-runner` is a degraded pathway for linear, deterministic steps.  
**Rationale:** Explicit state graph, checkpointing, conditional branching, human-in-the-loop, observability. No other framework matches.  
**Consequence:** All pattern bundles are LangGraph-configurable. Framework-specific concepts are confined to the adapter layer.

### ADR-002: Capability Registry as Single Registry
**Status:** Proposed  
**Decision:** One registry for tools, skills, and workflows. `kind=tool|skill|workflow`.  
**Rationale:** Eliminates registry duplication, enables unified capability discovery.  
**Consequence:** Tool Registry and Agent Registry consolidation (open in ADR-011 §7 item 11).

### ADR-003: Context-Driven Strategy Selection
**Status:** Accepted (implicit in REFERENCE ARCHITECTURE §6)  
**Decision:** Strategy Selection is a first-class capability, not a static table. The static table is seed data.  
**Rationale:** Enables learning and adaptation without schema changes.  
**Consequence:** Strategy Selection can evolve from seed lookup to learned selector.

### ADR-004: Learning Loop as Primary Improvement Mechanism
**Status:** Accepted (implicit in PATTERN-RECOGNITION-ASSIMILATION.md)  
**Decision:** Successful patterns graduate from `experimental` → `production_ready` → `compiled` → `habit`.  
**Rationale:** Continuously converts reasoning into deterministic execution (Principle 8).  
**Consequence:** Agents do not learn individually; the enterprise learns through asset promotion.

### ADR-005: Paperclip Rejected as Architectural Dependency
**Status:** Rejected (see Section D)  
**Decision:** Paperclip is not adopted. If needed, it will be a `PathwayRuntime` adapter.  
**Rationale:** Existing abstraction already covers the use case. Adding it now violates Principle 7 and adds premature complexity.

### ADR-006: Control Center UI as Single Human Interface
**Status:** Accepted (implicit in ROADMAP.md)  
**Decision:** One UI container (`dev_control_center_ui`) proxies to workflow engine.  
**Rationale:** Single pane of glass, no direct agent-to-UI coupling.  
**Consequence:** All human interaction flows through the Control Center.

### Missing ADRs

| Topic | Status |
|---|---|
| **AI Gateway / Portkey integration** | Not documented as ADR |
| **Event Bus topology** | ADR-012 is a stub (4 lines) |
| **Database per environment** | Plan exists (`1783822155715-database-per-env-users-plan.md`) but not ADR |
| **Capability lifecycle governance** | Not documented |
| **Information architecture / graph model** | Not documented |
| **Context engine for architectural knowledge** | Not documented |

---

## I. Context Engine Assessment

### Current state

The "context engine" currently consists of:

1. **Markdown files** in `agentic/docs/` and `docs/` — architecture, ADRs, context, prompts
2. **Kilo plans** in `.kilo/plans/` — implementation plans for specific features
3. **Kilo config** in `.kilo/` — instructions, agent manager, worktrees

**Capabilities:**
- Human-readable architecture documentation
- Kilo can read these files when working on the repo
- No structured retrieval, indexing, or search beyond file paths and grep

**Gaps:**
- No structured index of architectural decisions by topic
- No traceability links between requirements, capabilities, implementations
- No mechanism for Kilo to answer "what decisions have we made about X?" without reading all docs
- No mechanism to detect contradictions between docs
- No versioning or maturity tracking for architectural artefacts

### Context Engine Capability Gap

**The current context engine cannot reliably support the architectural loop described in this assessment.**

Specifically:
- Kilo cannot answer "What are we building?" without reading multiple docs
- Kilo cannot answer "What decisions have already been made?" without grep/search
- Kilo cannot answer "What constraints exist?" without reading CONSTRAINTS.md
- The human must repeatedly explain architectural context in new sessions

### Required capabilities

| Capability | Description | Implementation approach |
|---|---|---|
| **Structured index** | ADR index, capability index, decision index | Markdown with YAML frontmatter + grep |
| **Traceability links** | Requirement → Capability → Component → Test | Back-references in doc bodies |
| **Contradiction detection** | Alert when docs conflict | Linting / validation script |
| **Maturity tracking** | Proposed → Accepted → Implemented → Observed | ADR status field |
| **Retrieval by Kilo** | Structured context for implementation sessions | `.kilo/context/` directory with topic files |

### Recommendation

**Do not build a new context engine system.**

Instead:
1. **Standardise doc structure** — all ADRs and architecture docs use consistent YAML frontmatter with `status`, `decision`, `rationale`, `consequences`, `related`
2. **Create a context index** — `docs/architecture/INDEX.md` with tables of all artefacts by category
3. **Add traceability sections** — each implementation doc links back to the ADR that authorised it
4. **Add a context validation script** — CI job that checks for broken links, missing status fields, contradictions
5. **Use `.kilo/instructions.md`** — ensure it points Kilo to the right architecture docs for each task type

This is sufficient for the current team size. A graph database for architectural knowledge is over-engineering at this stage.

---

## J. First Vertical Slice

### Objective

Prove the core architectural loop with one genuinely useful capability in the Control Center.

### The slice

**"Daily Task Reflection"** — the Assistant helps the user reflect on their day, captures tasks, and records learnings.

### Why this slice

1. **Genuinely useful** — Martin can use it immediately
2. **Proves the full loop** — Intent → Context → Strategy → Capability lookup → Execution → Recording → Learning
3. **Small surface area** — one pattern, one capability, one UI flow
4. **No missing infrastructure** — uses existing Postgres, Capability Registry, Control Center UI
5. **Demonstrates gap detection** — if no "task tracking" capability exists, the system proposes one

### What it does

1. **Human** opens Control Center → Assistant tab → types: "Help me reflect on my day"
2. **Assistant** classifies intent: `routine_operation`, `execute`, `ai_assisted`
3. **Strategy Selection** returns: `recognise_and_reuse` (if a reflection SOP exists) or `investigate_then_fix` (first time)
4. **Capability lookup** checks registry for `daily_task_reflection` capability
   - **If found:** invokes it
   - **If not found:** produces a structured capability request:
     ```
     "I don't have a daily task reflection capability yet.
      I can create one that:
      - asks you for today's tasks and outcomes
      - records them in a task tracking service
      - produces a daily summary
      
      Would you like me to implement this?"
     ```
5. **Execution** — for the first iteration, the capability is a simple LLM-guided conversation that:
   - Asks structured questions
   - Captures responses
   - Stores them as an Enterprise Concept (`kind=solved_approach`)
6. **Result** — Assistant shows the summary and asks: "Want me to save this as your daily reflection pattern?"
7. **Learning** — if confirmed, the pattern is registered as a reusable capability

### What it proves

| Architectural claim | Proven by |
|---|---|
| Intent classification works | Rule-based matcher handles "reflect on my day" |
| Strategy selection works | Maps to `recognise_and_reuse` / `investigate_then_fix` |
| Capability discovery works | Registry lookup for `daily_task_reflection` |
| Gap detection works | Structured capability request when capability missing |
| Execution works | LLM-guided conversation produces concrete output |
| Learning works | Outcome stored as Enterprise Concept for future reuse |
| Human-in-the-loop works | Approval before promoting to reusable capability |

### What it does NOT need

- Paperclip
- C-Suite agents
- Full agent workforce
- Complete EIMS
- Autonomous skill creation
- Multi-agent coordination

---

## K. Implementation Plan

### Increment 1: Wire the LLM into the Assistant (1–2 days)

**Objective:** Replace generic "Done" responses with LLM-driven conversation.  
**Hypothesis:** A single LLM call with system prompt produces useful output.  
**Components affected:**
- `packages/ai/src/chat.py` — `AssistantChatService.chat()`
- `packages/workflow_runner/api.py` — `/assistant/chat` endpoint
- `.woodpecker.yml` — add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` secrets
- `environments/dev/compose.yml` — add AI gateway env vars

**Expected behaviour:**
- User sends message
- If intent confidence < 0.6 OR no capability found, route to LLM
- LLM returns structured response with reasoning, suggested actions, and artifact links
- Frontend renders markdown response

**Acceptance criteria:**
- Assistant gives contextually relevant responses, not generic "Done"
- LLM call is observable in Langfuse
- Fallback to rule-based response if LLM fails

**Tests:**
- Unit test: `AssistantChatService` routes to LLM when confidence low
- Unit test: `AssistantChatService` falls back gracefully on LLM error
- Integration test: `/assistant/chat` returns LLM response

**Observability:**
- Langfuse trace for every LLM call
- Token usage, latency, provider logged

**Architectural artefacts updated:**
- `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` — note LLM integration as `ai_mediated` capability execution mode

---

### Increment 2: Add structured capability gap detection (1–2 days)

**Objective:** When no capability matches, produce a structured request instead of generic failure.  
**Hypothesis:** Structured gap requests are more actionable than generic errors.  
**Components affected:**
- `packages/ai/src/chat.py` — gap detection logic
- `packages/capability_registry/src/registry.py` — add `find_gap()` method
- Control Center UI — render capability request with approve/reject buttons

**Expected behaviour:**
- User: "Create a spreadsheet of my leads"
- Assistant: "I don't have a spreadsheet creation capability. Here's what I would need: ..."
- Shows: capability name, purpose, inputs, outputs, required tools, security requirements
- Buttons: "Approve implementation", "Modify", "Reject"

**Acceptance criteria:**
- Gap detection triggers when registry returns no match
- Capability request includes all required fields
- Human can approve/reject/modify
- Approved requests are stored as Enterprise Concepts for implementation

**Tests:**
- Unit test: `CapabilityRegistry.find_gap()` returns structured request
- Unit test: `AssistantChatService` produces gap request when no match
- Integration test: UI renders gap request with action buttons

**Observability:**
- Gap request events published to Agent Bus
- Approval/rejection tracked in ConceptStore

**Architectural artefacts updated:**
- `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` — add gap detection to capability lifecycle

---

### Increment 3: Implement the first real capability — Daily Task Reflection (2–3 days)

**Objective:** Build the `daily_task_reflection` capability and prove end-to-end execution.  
**Hypothesis:** A simple LLM-guided conversation with structured output is useful and reusable.  
**Components affected:**
- New capability module: `packages/capabilities/daily_task_reflection/`
- `packages/capability_registry/src/registry.py` — register new capability
- `packages/workflow_runner/src/session.py` — invoke capability
- `packages/workflow_runner/api.py` — add capability invocation endpoint
- Control Center UI — render task reflection flow

**Expected behaviour:**
- User: "Help me reflect on my day"
- Assistant: invokes `daily_task_reflection` capability
- Asks 5 structured questions (wins, blockers, learnings, priorities, energy)
- Produces a markdown summary
- Stores summary as Enterprise Concept
- Asks: "Save this as a reusable pattern?"

**Acceptance criteria:**
- Conversation feels natural, not robotic
- Summary is structured and useful
- Result is stored in ConceptStore with provenance
- Pattern can be re-invoked on subsequent requests

**Tests:**
- Unit test: capability produces valid summary from mock conversation
- Unit test: summary is stored as Concept with correct kind
- Integration test: end-to-end from chat request to stored concept

**Observability:**
- Langfuse trace for capability invocation
- ConceptStore maturation history updated
- Session state persisted

**Architectural artefacts updated:**
- `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` — first production_ready pattern
- `REASONING-PATTERN-CATALOGUE.md` — add `daily_reflection` pattern

---

### Increment 4: Add artifact creation primitives (2–3 days)

**Objective:** Enable the Assistant to produce concrete artifacts (spreadsheets, checklists, drafts).  
**Hypothesis:** Concrete artifacts are more useful than text summaries for action-oriented requests.  
**Components affected:**
- New capability module: `packages/capabilities/artifact_creator/`
- Control Center UI — render artifact links inline
- `packages/workflow_runner/src/session.py` — handle artifact outputs

**Expected behaviour:**
- User: "Create a checklist for my weekly review"
- Assistant: produces a markdown checklist with checkboxes
- Renders as interactive checklist in UI
- User can check items, save state

**Acceptance criteria:**
- Artifacts are rendered inline in chat
- Checklist state persists across sessions
- Multiple artifact types supported (spreadsheet, checklist, draft)

**Tests:**
- Unit test: artifact creator produces valid markdown/CSV
- Integration test: UI renders artifact with interactivity

---

### Increment 5: Add the HR / Workforce abstraction (3–4 days)

**Objective:** Introduce the `WorkforceManager` that wraps `CapabilityRegistry` and manages roles, ownership, and capability requests.  
**Hypothesis:** A lightweight workforce abstraction enables the C-Suite model without Paperclip.  
**Components affected:**
- New module: `packages/workforce/src/`
- `WorkforceManager` — employs agents for tasks, manages context
- `Role` — lightweight record (name, capabilities, context)
- `CapabilityRequest` — structured request for new capability
- Integration with `AssistantChatService`

**Expected behaviour:**
- User: "I need to analyse our lead conversion rates"
- WorkforceManager: checks if `lead_analysis` capability exists
- If no: creates `CapabilityRequest` with full specification
- Routes to appropriate role (e.g. `analyst`)
- If role not available: asks human to assign or approve

**Acceptance criteria:**
- WorkforceManager can list available roles and capabilities
- CapabilityRequest includes purpose, inputs, outputs, tools, security, acceptance criteria
- CapabilityRequest can be approved/rejected/modified by human
- Approved requests are stored and available for implementation

**Tests:**
- Unit test: WorkforceManager discovers capabilities by role
- Unit test: CapabilityRequest contains all required fields
- Integration test: chat flow produces and stores CapabilityRequest

---

### Increment 6: Add the CEO orchestrator (2–3 days)

**Objective:** Replace direct `AssistantChatService` routing with a CEO node that delegates.  
**Hypothesis:** A lightweight orchestrator improves request routing without full C-Suite.  
**Components affected:**
- `packages/ai/src/chat.py` — introduce `CEOAgent` as first router
- `packages/langgraph/src/langgraph_runtime.py` — add CEO subgraph

**Expected behaviour:**
- All requests go to CEO first
- CEO classifies intent, checks context, delegates to appropriate role/capability
- CEO synthesises results back to user
- CEO escalates to human when uncertain or when capability gap detected

**Acceptance criteria:**
- CEO handles all request types
- Delegation is traceable (which role/capability handled it)
- Synthesis produces coherent multi-step responses
- Human escalation works for gaps and high-stakes decisions

---

### What comes after Increment 6

| Increment | Focus | Time |
|---|---|---|
| 7 | CTO + opencode integration (one manual build task) | 3–4 days |
| 8 | Reflection Agent (pattern mining from telemetry) | 3–4 days |
| 9 | Remaining C-Suite roles (COO, CMO, CFO) | 2–3 weeks |
| 10 | Full agent workforce with Paperclip adapter (if needed) | 2–4 weeks |
| 11 | Enterprise Information & Learning graph (relationships, provenance) | 2–4 weeks |
| 12 | Autonomous capability building (spec → code → deploy) | 4–6 weeks |

---

## Summary

### What we have

A production-grade infrastructure, a well-documented enterprise cognition architecture, and proven workflow routing. The Control Center UI is reachable and the Assistant endpoint is wired.

### What we don't have

A useful Assistant. The current implementation returns generic responses because it has no LLM, no real execution, no memory, and no learning.

### The path forward

1. **Do not build agents because they sound useful.** Build capabilities because they prove the architecture.
2. **Start with Increment 1** — wire the LLM. This is the smallest change that makes the Assistant useful.
3. **Prove the loop** — the Daily Task Reflection slice demonstrates Intent → Context → Strategy → Capability → Execution → Learning.
4. **Evolve the workforce** — add HR/WorkforceManager only after the first capability is proven.
5. **Add the CEO** only after there are multiple capabilities to orchestrate.
6. **Use architecture to drive implementation** — every increment updates the architecture docs, not the other way around.

### The first question to answer

> "Can the Assistant receive a real request, understand it, discover whether a capability exists, execute something useful, and record the outcome?"

If we cannot answer "yes" to this within the next week, the architecture is not proven regardless of how well it is documented.

**Recommended first action:** Implement Increment 1 (wire the LLM) and Increment 2 (capability gap detection) in parallel, then build Increment 3 (Daily Task Reflection) as the proof point.

---

*This assessment is the output of the architectural review requested. No code has been implemented. Implementation should proceed only after this document is reviewed and the first vertical slice is agreed.*
