# Plan: Enterprise Cognition — Design Specs (Phase 1)

## Goal
Expand `agentic/docs/architecture/ENTERPRISE-COGNITION.md` into four load-bearing
design specs that make the "context switches abilities in/out" model buildable.
This phase is **design-only** (no runtime code). It locks the abstractions so the
later executor extension does not paint us into a corner.

## Locked decisions (from interview)
1. **Scope**: design specs first, no implementation. Four docs:
   Context Model, Reasoning Pattern Catalogue, Session Model, Runtime Mapping.
2. **Pattern = prompt/config bundle** (incl. cached prompt templates) that
   **enables/disables framework "pathways"** (LangGraph | CrewAI | MAF |
   workflow-runner | human) based on context. Frameworks are swappable
   pathway implementations — honors "frameworks are runtimes".
3. **Recognition = hybrid**: automated classification (LLM/rules) of the request
   into the Context Model *suggests* a pattern/pipeline; **user declaration
   takes precedence** and can override or refine at Session creation.
4. **Session = a pipeline of pattern steps** (not one pattern). Each step is a
   bundle that toggles pathways + defines participants/governance gates.
   Existing sequential executor = Session with a single step enabling only the
   workflow-runner pathway.

## Honest current-state constraint (must be stated in every spec)
- Real engine today: `agentic/src/workflow-runner` (loader → executor →
  registry → composer). `docker-compose.yml` runs it as `workflow-engine`.
- `agents/langgraph` is an empty container (src only `.gitkeep`).
- CrewAI / Microsoft Agent Framework are **not present** — Runtime Mapping
  documents them as mapping *targets/stubs*, not implemented pathways.
- Enterprise assets (policies, ADRs, playbooks, standards): recommend
  **Postgres** for structured metadata (reuse `workflow-runner/db.py`),
  **Qdrant** for semantic retrieval, **repo markdown** for authored docs.
  State this as the recommended store; mark as open if user disagrees.

## Deliverables (author in this order)

### 1. `agentic/docs/architecture/ENTERPRISE-CONTEXT-MODEL.md`
Outline:
- The 4 orthogonal contexts from the theory, each as a **typed schema**
  (enum + free-text fields): Problem, Environment, Information, Activity Purpose,
  plus Decision Context (confidence, consensus vs authority, reversibility,
  mandatory policy checks, human approval, timebox).
- How contexts are *represented* as data (machine-readable record), not prose.
- How user declaration + inferred classification merge (declaration wins).
- Mapping tables: context tuple → candidate pattern(s) (from the theory's
  "fascinating" table: Innovation→Brainstorm, Incident→SOP, Architecture→Debate,
  Compliance→Checklist, Learning→Reflection, Unknown→Investigation).
- Open: metric definitions for maturity.

### 2. `agentic/docs/architecture/REASONING-PATTERN-CATALOGUE.md`
Outline:
- Pattern = prompt/config bundle (cached prompt templates + role + config)
  that **enables/disables framework pathways** per context.
- Canonical catalogue from the theory (SOP, Investigation, Exploration,
  Brainstorm, Debate, Consensus, Critique, Reflection, Research, Planning,
  Verification, Human Approval, Escalation, Learning).
- Per-pattern spec: enabled pathways, participant roles, governance gates,
  inputs/outputs, composability rules (how patterns chain in a pipeline).
- Versioning rule for patterns (semver on the bundle).
- Worked examples traced: Incident Response, Architecture Review Board,
  Brainstorm Workshop.

### 3. `agentic/docs/architecture/SESSION-MODEL.md`
Outline:
- Session = first-class bounded execution: purpose, agenda, participants,
  policies, **pipeline of pattern steps**, memory scope, success criteria,
  outputs, escalation rules, timebox.
- Lifecycle: create (Recognition suggests pipeline, user edits) → run
  (pattern steps execute in order, gates enforced) → close (outputs +
  distillation hook).
- How a Session maps onto the **existing** `workflow-runner` state model
  (`state.py`/`db.py`) — Session ≈ WorkflowState extended with pipeline +
  governance; single-step Session ≈ today's workflow.
- Distillation hook: successful Sessions feed the Learning lifecycle.

### 4. `agentic/docs/architecture/RUNTIME-MAPPING.md`
Outline:
- Pathway → framework mapping table. Today: `workflow-runner` = SOP/
  sequential pathway (implemented); `human` = approval gateway (implemented
  via existing handlers); LangGraph/CrewAI/MAF = **stub targets**.
- Why each framework fits which topology (LangGraph = graph/stateful meeting;
  CrewAI = collaborative role play; MAF = enterprise integration; workflow-runner
  = deterministic SOP). Keep them interchangeable behind the pathway interface.
- Stable abstraction boundary so no framework concept leaks into Context/Session
  models (principle 10).
- Learning & Knowledge Lifecycle section: novel → reasoning → playbook →
  SOP → deterministic workflow → habit; how a distilled Session becomes a
  new pattern bundle / disabled-pathway config.

## Cross-cutting requirements for all four docs
- Each must trace back to the 10 Working Principles in the theory.
- Each must include at least one **worked example** (Incident Response,
  Architecture Review Board) traced end-to-end across Context→Pattern→Session→Runtime.
- State explicitly what is **implemented today vs. target**, referencing the
  honest current-state constraint above.

## Validation
- User review of the four docs for internal consistency and principle traceability.
- A single incident/architecture scenario is walkable through all four docs
  without contradiction.
- No runtime code written in this phase; follow-up plan will implement the
  Recognition→pattern-select→pipeline executor on `workflow-runner`.

## Open questions carried forward (do NOT block Phase 1)
- Exact maturity metrics.
- Final enterprise-asset store (Postgres+Qdrant+repo recommended).
- How Recognition classification is evaluated/traced (Langfuse already in stack).
