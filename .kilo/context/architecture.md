# Architecture Context

## Purpose

This file provides Kilo with the architectural context needed to make consistent implementation decisions without repeatedly asking the human to restate constraints.

## Authoritative Architecture Documents

| Document | Location | Authority |
|---|---|---|
| Enterprise Cognition Reference Architecture | `agentic/docs/architecture/ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` | Canonical |
| Runtime Mapping | `agentic/docs/architecture/RUNTIME-MAPPING.md` | LangGraph substrate |
| Enterprise Context Model | `agentic/docs/architecture/ENTERPRISE-CONTEXT-MODEL.md` | 5 context dimensions |
| Reasoning Pattern Catalogue | `agentic/docs/architecture/REASONING-PATTERN-CATALOGUE.md` | 14 pattern types |
| Session Model | `agentic/docs/architecture/SESSION-MODEL.md` | Session lifecycle |
| Pattern Recognition & Assimilation | `agentic/docs/architecture/PATTERN-RECOGNITION-ASSIMILATION.md` | Learning loop |
| ADRs | `docs/architecture/adr/` | Accepted decisions |
| Architecture Assessment | `docs/architecture/ARCHITECTURE-ASSESSMENT-2026-08-21.md` | Current state analysis |
| Increment 8 Investigation Report | `docs/architecture/INCREMENT-8-INVESTIGATION-REPORT.md` | Validation findings |
| Increment 10 Proposal | `docs/architecture/INCREMENT-10-PROPOSAL.md` | Implementation proposal |

## Key Decisions

### ADR-010: Provider-Based Architecture
All platform capabilities must be designed around stable contracts with replaceable implementations. Consumers depend on interfaces, not concrete implementations.

### ADR-011: Platform Runtime Foundation
LangGraph is the single execution substrate for all pattern execution. Framework-specific concepts are confined to the adapter layer.

### ADR-013: Capability-Oriented Repository Structure
Platform code is organised around capabilities rather than technical layers. Each capability owns its contracts, providers, implementations, metadata, and tests.

### ADR-014: Capability-First Routing (Proposed)
`AssistantChatService` MUST check `CapabilityRegistry` before invoking any reasoning pattern or LLM. Deterministic capabilities are the first-class execution path. Reasoning occurs only when capability is absent or insufficient.

### ADR-015: Human-as-Approval-Layer for Capability Specifications (Proposed)
New capabilities require explicit human approval of their specification before implementation. Specification approval and implementation approval are separate governance decisions.

### ADR-016: CapabilityRequest as Governance Artifact (Proposed)
`CapabilityRequest` is a transient governance object. Once approved, it is persisted as an `EnterpriseConcept` (`kind=capability`, `status=draft`). Governance decisions are durable in the EnterpriseConcept payload and provenance.

### ADR-017: Three-Plane Architecture (Accepted)
The system is partitioned into three orthogonal planes: Enterprise, Organisation/Control, and Operations. Each plane owns a distinct set of concerns and has explicit prohibitions against crossing into adjacent planes.

### ADR-018: Role vs Person vs Agent (Accepted)
The domain model distinguishes Role (abstract position), Person (human individual), and Agent (software entity). They are separate types with separate lifecycles and ownership.

### ADR-019: Authority and Delegation Boundary (Accepted)
Authority is an explicit, delegatable grant within a defined scope. Authority records live in the Organisation/Control plane. Delegation is a first-class record that preserves the chain of grant.

### ADR-020: Capability Ownership by People/Capability (Accepted)
Capabilities belong to the People/Capability function. The CEO and OrganisationControlPlane do not own capability definitions, matching, or execution lifecycle.

### ADR-021: EIMS Boundary and ConceptStore as Current Implementation (Accepted)
ConceptStore is the current implementation of the Enterprise Information Management System (EIMS) boundary. The eventual EIMS may expand beyond ConceptStore.

### ADR-022: OrganisationControlPlane Abstraction (Accepted)
OrganisationControlPlane is a narrow abstraction providing role lookup, work assignment, authority delegation, organisational context retrieval, and operational handoff via `execute_work()`. It provides organisational mechanisms and context through which roles operate. It does NOT store Person/Agent records, coordinate work, become the project manager, or become the COO. **Updated by ADR-037 and Increment 10.**

### ADR-023: Paperclip Adapter Boundary behind OrganisationControlPlane (Accepted)
The OrganisationControlPlane abstraction is defined independently of Paperclip. No Paperclip-specific types appear in the organisation domain.

### ADR-024: CEO as Organisational Role, not Universal Router (Accepted)
CEO is an organisational ROLE, not the central AI agent. CEO does not discover/select capabilities or own capability lifecycle. **Superseded by ADR-031 for CEO responsibilities scope.**

### ADR-025: Assistant as Organisational Role/Interface, not Implicit CEO (Accepted)
Assistant is a Role/interface, not an orchestrator. AssistantChatService routes to the appropriate organisational role via OrganisationControlPlane.

### ADR-026: People/Capability as Peer Domain Plane (Accepted)
People/Capability is a first-class domain plane alongside Enterprise, Organisation/Control, and Operations. It owns capability definitions, capability lifecycle, people records, and capability development/acquisition/testing. It does NOT own Work. **Updated by ADR-037.**

### ADR-027: Work-Capability "Requires" Relationship (Accepted)
Work references required capabilities via `required_capability_ids` but does NOT own capability lifecycle. People/Capability owns capability definitions and lifecycle. Work is about effort allocation; Capability is about reusable ability. Role also has `required_capability_ids`.

### ADR-028: Role Workflow Handoff Model for Specialist Roles (Accepted)
EA, SA, BA, Designer, Developer, QA are Roles in the Organisation/Control plane. Work flows between them through explicit Assignment and handoff. Each role produces durable enterprise assets consumed by downstream roles. **Superseded by ADR-033 for project coordination and ADR-038 for decomposition.**

### ADR-029: EIMS Learning Loop and Outcome Capture (Accepted)
Operational execution outcomes flow back into EIMS through a structured learning loop. Not all operational state becomes durable knowledge. The boundary between transient operational state and durable enterprise knowledge is explicit.

### ADR-030: Future EnterpriseInformation Abstraction for CEO (Proposed)
CEO should eventually consume an `EnterpriseInformation` interface rather than accessing ConceptStore directly. Do NOT implement until Increment 9+ unless immediately required.

### ADR-031: CEO as Strategic Role, Not Orchestrator (Accepted)
Supersedes ADR-024. The CEO is an organisational ROLE with strategic responsibilities only. The CEO makes strategic decisions, establishes strategic direction, observes organisational performance, and intervenes at the strategic level. The CEO does NOT organise day-to-day work, assign individual operational tasks, manage project delivery, coordinate specialist work, select capabilities, execute operational work, or act as a universal system router.

### ADR-032: COO as Organisational Role for BAU (Accepted)
The COO is an organisational ROLE accountable for Business-as-Usual (BAU) operational performance. The COO observes operational outcomes, manages operational capacity, handles exceptions, and coordinates functional managers. The COO does NOT become the Operations plane, micro-manage every task, or execute operational work.

### ADR-033: Project Management as Organisational Role (Accepted)
Project Manager / Delivery Manager is an organisational ROLE, not an operations engine. The PM coordinates project delivery, sequences work, tracks progress, manages dependencies, surfaces risks, and coordinates specialist roles. The PM does NOT become the Operations plane, execute every task, own every capability, or replace specialist roles.

### ADR-034: Work Accountability Model (Accepted)
Work is accountable to an appropriate Role, not owned by Organisation/Control. Work carries explicit accountability, coordination, assignment, and outcome fields. Every Work item has exactly one `accountable_role_id`. BAU work and project work have different accountability structures.

### ADR-035: Capability / Skill / Tool Distinction Investigation (Proposed)
Do NOT collapse Skill and Tool into Capability merely for implementation convenience. Investigate whether a cleaner model distinguishes Capability (ability), Skill (component), Tool (enabler), and Resource (supporting material). Do NOT implement until the domain boundary is understood. **Finding: Keep unified Capability type for now; express distinctions through metadata and tags.**

### ADR-036: Distributed Organisational Coordination (Accepted)
Organisational coordination is distributed according to responsibility and authority. No single role, service, or plane coordinates all organisational activity. The OrganisationControlPlane provides mechanisms and context; actual coordination belongs to appropriate roles (CEO, COO, C-Suite executives, Project Managers, functional managers, specialist roles).

### ADR-037: Person/Agent Ownership by People/Capability (Accepted)
Person and Agent domain records belong to People/Capability plane. Organisation/Control references them by ID only. OrganisationControlPlane does not store Person or Agent records.

### ADR-038: Work Decomposition and Dependency Model (Accepted)
Work supports parent/child decomposition and dependency tracking for project coordination. Work decomposition is an organisational/management concern, not an operational workflow concern.

## Four-Plane Architecture (Validated)

### Enterprise Plane
- **Owns:** strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning
- **Boundary:** Strategy interpretation, priority setting, escalation thresholds
- **Does NOT:** run operations, execute work, own capabilities, coordinate organisational work

### Organisation / Control Plane
- **Owns:** organisational structure, roles, relationships, authority, accountability, management mechanisms, organisational context, operational handoff
- **Boundary:** `OrganisationControlPlane` abstraction — provides mechanisms and context, NOT coordination, NOT storage of Person/Agent records
- **Does NOT:** execute operational work, own EIMS, own capability definitions/lifecycle, directly control runtime agents, own people records, coordinate work, become the CEO/COO/PM, store Person/Agent records

### People / Capability Plane
- **Owns:** people records (Person, Agent), capability definitions, capability lifecycle (registration, maturation, promotion, retirement), capability development/acquisition/testing, capability matching, CapabilityRequest governance, capability readiness
- **Boundary:** `CapabilityRegistry`, `CapabilityMatcher`, `CapabilityRequest`, Person/Agent records
- **Does NOT:** own Work, assign work, define organisational authority, execute operational work, own EIMS, coordinate organisational work

### Operations Plane
- **Owns:** workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work
- **Boundary:** `PathwayRuntime`, `Session`, `PatternStep`, `execute_workflow()`
- **Does NOT:** define organisational authority or strategy, own capability definitions, govern capability lifecycle, coordinate organisational work

## Role Model

### Core Concepts

| Concept | Description | Owner | Notes |
|---|---|---|---|
| **Role** | Abstract position with responsibilities, authority, constraints, information access, required capabilities, accountabilities | Organisation-Control | Central organisational unit; not a person or agent |
| **Person** | Human individual with identity and employment context | People/Capability | Occupies one or more Roles; Organisation/Control references by ID |
| **Agent** | Software entity marker/record — no runtime execution logic in domain model | People/Capability | Fulfils a Role at runtime; Organisation/Control references by ID |
| **Capability** | Reusable unit of work (tool, skill, service) | People/Capability | Has lifecycle (register -> operate -> measure -> learn -> retire) |
| **Skill** | Component of a capability (knowledge, method, technique) | People/Capability | Expressed through Capability metadata/tags for now |
| **Tool** | Something used to enable/support a capability | IT/Technology or People/Capability | Expressed through Capability metadata/tags for now |
| **Work** | Instance of assigned effort | Organisation-Control | Accountable to a Role; has status, assignments, deliverables, required_capability_ids, dependencies, outcome |
| **Authority** | Permission grant within scope | Organisation-Control | Can be delegated, has constraints |

### Distinctions

- **Role != Person:** A Role is an abstract position. A Person occupies a Role.
- **Role != Agent:** A Role defines what is needed. An Agent is a runtime executor that may fulfil a Role.
- **Capability != Agent:** A Capability is what can be done. An Agent is who/what does it.
- **Work != Capability:** Work is a specific assignment. Capability is reusable ability.
- **Work requires Capability:** Work declares required capabilities by ID. Capability lifecycle remains in People/Capability.
- **Person/Agent fulfils Role:** A Person or Agent occupies/fulfils a Role. The Role has authority and requirements; the Person/Agent brings capability.

### Agent -> Role -> Capability Chain

```
Person / Agent (People/Capability plane)
      |
      | fulfils
      v
    Role (Organisation/Control plane)
      |
      | requires
      v
  Capability (People/Capability plane)
      ^
      | possesses / fulfils
Person / Agent (People/Capability plane)
```

Capabilities are portable. The same capability may be required by multiple roles over time. People/Capability determines whether a Person/Agent has, needs, or can develop the capabilities required to fulfil a Role.

### Specialist Roles (Future)

These are organisational Roles, not necessarily separate AI agents:
- CEO (strategic)
- COO (BAU operational performance)
- C-Suite executives (accountable for business outcomes)
- Project Manager / Delivery Manager (project coordination)
- Assistant (role/interface)
- Enterprise Architect, Solution Architect, Business Analyst, Designer, Developer, QA (specialist)
- People/Capability (capability lifecycle)

A role may be fulfilled by human, AI agent, human+AI, or multiple people/agents.

### Work-Capability Relationship

```
Work
  | required_capability_ids
  v
Capability (People/Capability domain)
  ^
  | possesses / fulfils
Person / Agent

Work
  | assigned to / accountable to
  v
Role / Person / Agent (Organisation/Control domain)
```

When Work requires a capability that does not exist, a CapabilityRequest is created (transient governance artifact) to People/Capability.

### BAU vs Project Work

| Aspect | BAU Work | Project / Initiative Work |
|---|---|---|
| work_type | "bau" | "project" or "initiative" |
| accountable_role | COO or functional manager | C-Suite executive |
| coordinating_role | Functional manager | Project Manager |
| assignee_role | Operational role | Specialist role |
| duration | ongoing | bounded |
| outcome | operational performance | business outcome |
| decomposition | ongoing operational tasks | bounded project deliverables |

### Work Decomposition Model

```
Initiative Work (accountable: C-Suite executive)
    ↓ parent_work_id
Project Work (accountable: C-Suite executive, coordinating: PM)
    ↓ parent_work_id
    ├── Specialist Work A (accountable: EA, coordinating: PM)
    ├── Specialist Work B (accountable: BA, coordinating: PM)
    ├── Specialist Work C (accountable: Dev, coordinating: PM)
    └── Specialist Work D (accountable: QA, coordinating: PM)
```

Dependencies express sequencing: `Work C depends_on: [Work A, Work B]`.

### Work Lifecycle

```
DRAFT
  ↓
ASSIGNED (organisational handoff)
  ↓
IN_PROGRESS (operational execution begins)
  ↓
COMPLETED (execution finished)
  ↓
ACCEPTED (outcome assessed against acceptance_criteria)
```

Status transitions:
- `ASSIGNED` → `IN_PROGRESS`: organisational responsibility established, Operations begins execution
- `IN_PROGRESS` → `COMPLETED`: execution finished, result returned to organisation
- `COMPLETED` → `ACCEPTED`: outcome assessed against acceptance_criteria
- Any status → `CANCELLED` or `ESCALATED`: organisational decision

## Operational Handoff

The boundary between organisational Work and operational execution is:

```
Organisation/Control plane:
    - Creates Work
    - Sets accountable_role_id, coordinating_role_id
    - Assigns Work via OrganisationControlPlane.assign_work()
    - Calls OrganisationControlPlane.mark_work_ready() to hand off to Operations
    - Receives execution result
    - Assesses outcome against acceptance_criteria
    - Updates Work.outcome and Work.status

Operations plane:
    - Receives Work for execution via execute_work()
    - Creates operational execution request (PathwayCallRequest, Session, or Workflow)
    - Invokes PathwayRuntime or execute_workflow()
    - Returns execution result (PathwayResponse, ExecutionResult, StepResult)
```

Key principle: **Work is organisational. Execution is operational.**
- OrganisationControlPlane.mark_work_ready() is the handoff seam
- Execution result is evidence, not automatic organisational acceptance
- Organisation assesses outcome and decides acceptance

## Outcome Assessment

Outcome assessment is an organisational concern:
- Takes execution result + Work.acceptance_criteria
- Produces assessed outcome (accepted / not accepted)
- Updates Work.outcome and Work.status
- Optionally records durable learning in EIMS

Outcome assessment is NOT:
- automatic acceptance of execution results
- an operational concern
- a capability matching exercise

## EIMS Learning Loop

- **ConceptStore** is the current implementation of the Enterprise Information Management System (EIMS).
- EIMS owns: durable enterprise information, enterprise concepts, provenance, relationships, institutional knowledge, learning.
- EIMS does NOT own: runtime execution, orchestration, role assignment, authority, agent control, workflow execution, organisational control database.
- The eventual EIMS may expand beyond ConceptStore. Preserve architectural flexibility by treating ConceptStore as an implementation, not the complete EIMS.

### Learning Loop

```
operational execution
    |
    | produces
    v
execution result
    |
    | evaluated by
    v
outcome assessment
    |
    | creates/updates
    v
EnterpriseConcept (EIMS)
    |
    | informs
    v
future organisational decisions
```

- **Transient operational state:** Session state, workflow execution state, runtime agent state, human-in-the-loop pending state, operations monitoring state (KPIs, alerts).
- **Durable EIMS knowledge:** Strategy decisions, capability definitions, work outcomes, enterprise assets, governance decisions, institutional learning.
- **Work outcome learning:** Only project/initiative work with accepted outcomes becomes EIMS knowledge. Routine BAU does not.
- **Future:** A formal OutcomeRecorder or LearningService may promote operational outcomes to EIMS.

### Future CEO-EIMS Abstraction

CEO should eventually use an `EnterpriseInformation` interface rather than accessing ConceptStore directly. This is a future increment (ADR-030). Current Increment 6/8 CEO continues to use ConceptStore directly for reads.

## CEO and Management Roles

### CEO (Strategic Role)
- CEO is an organisational ROLE, not the central AI agent.
- CEO responsibilities:
  - Interprets enterprise information and strategy
  - Makes strategic decisions
  - Establishes strategic direction
  - Makes strategic pronouncements
  - Observes organisational performance and outcomes
  - Reviews significant outcomes
  - Intervenes when necessary at strategic level
  - Changes strategic direction when necessary
  - Escalates or resolves matters within CEO authority
- CEO does NOT:
  - Organise day-to-day work
  - Assign individual operational tasks
  - Determine who does every piece of work
  - Manage project delivery
  - Coordinate specialist work
  - Select capabilities for individual work
  - Execute operational work
  - Orchestrate agents
  - Become the universal system router
- CEO decision flow: strategic decision -> "We should do X." -> Hand to accountable executive / management structure.

### COO (BAU Management Role)
- COO is an organisational ROLE accountable for Business-as-Usual (BAU) operational performance.
- COO responsibilities:
  - Operational performance oversight
  - BAU outcomes tracking
  - Operational capacity management
  - Significant exception handling
  - Cross-functional operational coordination
  - Reporting operational health to CEO
- COO does NOT:
  - Micro-manage every operational task
  - Execute operational work
  - Become the Operations plane
  - Own capability lifecycle
  - Own EIMS
  - Replace functional managers

### C-Suite Executive (Accountable Role)
- C-Suite executive is an organisational ROLE accountable for a business outcome resulting from a strategic initiative.
- C-Suite executive responsibilities:
  - Owns the business outcome
  - Accountable to CEO for results
  - Appoints / approves Project Manager
  - Receives outcome reports
  - Escalates to CEO when necessary
- C-Suite executive does NOT:
  - Coordinate project delivery details
  - Execute specialist work
  - Replace the Project Manager

### Project Manager (Coordination Role)
- Project Manager is an organisational ROLE coordinating project delivery.
- PM responsibilities:
  - Coordinate project work
  - Sequence work activities
  - Track progress against plan
  - Manage dependencies between work items
  - Surface risks and issues
  - Coordinate specialist roles
  - Report outcomes to accountable executive
  - Escalate issues appropriately
- PM does NOT:
  - Become the Operations plane
  - Execute every task
  - Own every capability
  - Replace specialist roles
  - Become CEO
  - Own the business outcome (that belongs to the accountable C-Suite executive)

### Assistant
- Assistant is a Role/interface, not an orchestrator.
- AssistantChatService routes to the appropriate organisational role via OrganisationControlPlane.
- Assistant does NOT implicitly become CEO.

## Distributed Coordination Model

Organisational coordination is distributed according to responsibility and authority. No single role, service, or plane coordinates all organisational activity.

```
Enterprise
   ↓
strategic intent
   ↓
CEO
   ↓
strategic decision
   ↓
accountable executive / management
   ↓
management / project coordination
   ↓
organisational roles
   ↓
operations
   ↓
outcomes
   ↓
enterprise learning
```

| Role | Coordinates | Does NOT |
|---|---|---|
| CEO | Strategic direction, major interventions | Day-to-day work, project delivery, operational tasks |
| COO | BAU operational performance, cross-functional coordination | Strategic decisions, project delivery, execution |
| C-Suite executive | Business outcome accountability for initiatives | Project coordination details, specialist work |
| Project Manager | Project delivery coordination, dependencies, risks | Business outcomes, strategic decisions, execution |
| Functional manager | Functional responsibility, team performance | Cross-functional strategy, project delivery |
| Specialist role (EA, SA, BA, Dev, QA) | Specialist work products, quality | Project coordination, business outcomes |
| Operations | Workflow execution, runtime, tools | Strategic decisions, role accountability |

## Paperclip Boundary (Future)

Paperclip remains behind OrganisationControlPlane. Future adapter should implement:
- Role/Agent representation
- Work assignment and task tracking
- Coordination and meetings
- Approvals
- Organisational hierarchy
- Agent lifecycle
- Cost tracking

Paperclip does NOT provide:
- Capability definitions or lifecycle
- Enterprise information / EIMS
- Governance semantics
- Enterprise strategy
- Domain model types

### Paperclip Conceptual Mapping

| Our Domain | Paperclip Concept | Mapping Quality |
|---|---|---|
| Role | Agent / Team | Clean |
| Work | Task / work mechanism | Clean |
| Authority | Permissions / approvals | Clean |
| Assignment | Task assignment | Clean |
| Delegation | Delegation / chain | Clean |
| Reporting relationships | Hierarchy | Clean |
| Coordination | Meetings / coordination | Partial |
| Required capabilities | Not modelled | Missing |
| Accountability model | Not modelled | Missing |
| Enterprise assets | Not modelled | Missing |
| Governance | Not modelled | Missing |
| EIMS | Not modelled | Missing |

**Conclusion:** Paperclip fits naturally behind OrganisationControlPlane for organisational mechanisms. What Paperclip does NOT provide (capabilities, EIMS, governance, enterprise assets, accountability semantics) must remain ours.

## Four-Plane Dependency Rules

1. Enterprise may read from all planes but owns strategy and durable knowledge.
2. Organisation/Control may read from People/Capability and Operations but owns roles, authority, and work assignment mechanisms.
3. People/Capability may read from EIMS but owns capability definitions and lifecycle, people records.
4. Operations may read from Organisation/Control and People/Capability but owns execution.
5. EIMS is written to by all planes but owned by Enterprise.
6. No plane may execute operational work on behalf of another plane.
7. No plane may own capability lifecycle except People/Capability.
8. No plane or role may coordinate work outside its authority boundary.
9. The OrganisationControlPlane provides mechanisms; roles provide coordination.
10. Organisation/Control references Person/Agent by ID; People/Capability owns their records.
11. Work is organisational; execution is operational. The handoff is via OrganisationControlPlane.mark_work_ready().
12. Execution result is evidence; organisational outcome is assessed against acceptance_criteria.

## Constraints

1. **Recognition before reasoning** — check capabilities before invoking LLM or reasoning patterns
2. **Enterprise assets are first-class** — concepts, decisions, playbooks outlive agents
3. **Frameworks are runtimes, not architecture** — LangGraph is a substrate, not the domain model
4. **Human-in-the-loop for governance** — capability specifications require human approval
5. **Deterministic execution first** — compile known patterns; reason only when uncertain
6. **Strict persistence** — write failures raise, never swallow
7. **No framework leakage** — Context, Session, and Capability schemas contain no framework-specific types
8. **Four-plane separation** — Enterprise, Organisation/Control, People/Capability, and Operations planes must not cross their boundaries
9. **Capability ownership stays in People/Capability** — CEO and OrganisationControlPlane must not own capability lifecycle
10. **Organisation domain import-clean** — no capability_registry, no concepts imports in organisation package
11. **Work references capabilities, does not define them** — Work contains required_capability_ids, not capability definitions
12. **EIMS is write-accessible but Enterprise-owned** — all planes may write durable knowledge, but EIMS does not become a runtime database
13. **Transient vs durable state** — operational execution state remains transient; only evaluated outcomes become EIMS knowledge
14. **No God services** — OrganisationControlPlane, CEO, People/Capability, and Operations must remain narrow and focused
15. **CEO is strategic only** — CEO does not coordinate day-to-day work, assign tasks, or manage projects
16. **Distributed coordination** — coordination belongs to roles (COO, C-Suite, PM, functional managers), not to planes or central services
17. **Work has accountable role** — every Work item has exactly one accountable_role_id; Organisation/Control does not own Work
18. **Role is central** — Role carries responsibilities, authority, required capabilities, and accountabilities; Person/Agent fulfils Role
19. **Person/Agent owned by People/Capability** — Organisation/Control references by ID; does not store Person/Agent records
20. **Work decomposition is management, not execution** — Work hierarchy and dependencies express management intent; Operations executes individual items
21. **Work is organisational; execution is operational** — Work.status ASSIGNED→IN_PROGRESS is the handoff boundary; execution result is evidence, not automatic acceptance

## Current Implementation State

### Implemented and Wired
- Infrastructure: Docker, Woodpecker CI, private registry
- CapabilityRegistry: register, get, list, resolve, record_invocation, promote
- ConceptStore: upsert, get, list_by_kind, list_by_tag, record_invocation
- Intent classification: rule-based regex keyword matching
- Strategy selection: static lookup table
- Session model: `create_session_from_decision()`
- PathwayRuntime abstraction: `PathwayRuntime` interface + `LangGraphRuntime` implementation
- Pattern execution: state graph from `PathwayCallRequest.pattern_step.ordered_steps`
- Workflow execution: `execute_workflow()` with skill/tool/workflow handlers
- Capability execution: `execute_capability()` (compiled mode only) + `PatternRuntime.invoke_step()` (tier2/tier3)
- CapabilityRequest: transient governance model (pending -> approved/rejected)
- AssistantChatService: wired with capability matching and session creation
- OrganisationControlPlane: ABC + InMemoryOrganisationControlPlane (Increment 6)
- Role model: Role, Person, Agent, Authority, Work, Assignment, OrgContext, Delegation
- Work accountability model: work_type, accountable_role_id, coordinating_role_id, required_capability_ids, acceptance_criteria, dependencies, parent_work_id, outcome
- Role required capabilities: required_capability_ids
- Operational handoff: OrganisationControlPlane.mark_work_ready() with PathwayRuntime integration
- Outcome assessment: assess_work_outcome() helper
- EIMS learning: record_work_learning() helper
- Four-plane architecture documented (Increment 7)
- Corrected role model with CEO/COO/PM/C-Suite distinctions (Increment 7 correction)
- Domain model corrected to match architecture (Increment 9)
- Organisational workflow proof with behavioural tests (Increment 10)

### Not Yet Implemented
- People/Capability plane package and services
- Full CEO implementation as strategic role
- COO implementation
- C-Suite executive roles
- Project Manager implementation
- Paperclip adapter
- EIMS expansion beyond ConceptStore
- EnterpriseInformation abstraction for CEO-EIMS boundary
- Kilo handoff contract via `.kilo/plans/`
- Capability routing in `AssistantChatService`
- Capability matching implementation
- Capability execution in CEO
- Universal routing
- Capability/Skill/Tool distinction (under investigation)
- OutcomeRecorder / LearningService (prototype proven)

## Increment 11 Proposed Scope

### In Scope
1. People/Capability plane package skeleton
2. Capability lifecycle hooks in existing CapabilityRegistry
3. AssistantChatService capability routing (if architecture permits)

### Out of Scope
- Full CEO/COO/PM implementation
- Paperclip integration
- EIMS expansion
- EnterpriseInformation abstraction
- All specialist role implementations
- Universal routing

## Test Baseline

```
pytest packages/capability_registry/tests/test_capabilities.py packages/ai/tests/test_assistant.py -q
Result: 18 passed
```

```
pytest packages/organisation/tests/ -q
Result: 46 passed
```

## Import Model

The repository uses **flat imports** from package `src/` directories:
- `packages/ai/src/assistant.py` exports `AssistantReasoningService`
- `packages/capability_registry/src/capabilities.py` exports `CapabilityRegistry`
- `packages/workflow_runner/src/session.py` exports `Session`
- `packages/organisation/src/organisation_control_plane.py` exports `OrganisationControlPlane`
- `packages/organisation/src/outcome.py` exports `assess_work_outcome`, `record_work_learning`

pytest supports this via `conftest.py` which adds each package's `src/` to `sys.path`. Runtime environments must set `PYTHONPATH` to include all package `src/` directories.

Current Docker PYTHONPATH:
```
/app:/app/src:/packages/configuration/src:/packages/ai/src:/packages/bus/src:/packages/langgraph/src:/packages/capability_registry/src:/packages/organisation/src
```

## Glossary

- **Capability**: An `EnterpriseConcept` with `kind=capability`. Represents a tool, skill, or service. Owned by People/Capability plane.
- **CapabilityRequest**: Transient governance object for requesting new capabilities. Becomes `EnterpriseConcept` on approval.
- **HumanSelectionMatcher**: First implementation of `CapabilityMatcher`. Returns all capabilities as candidates; human selects.
- **MatchResult**: Output of `CapabilityMatcher.match()`. Contains candidates, confidence, matcher_id.
- **ExecutionMode**: `ai_mediated` (LLM-based) or `compiled` (deterministic code).
- **MaturationHistory**: Tracks invocation count, corrections, promotion status for capabilities.
- **OrganisationControlPlane**: Narrow abstraction providing organisational mechanisms and context, plus operational handoff via `execute_work()`. Does NOT store Person/Agent records, coordinate work, or become management roles.
- **Role**: Abstract position with responsibilities, authority, constraints, information access, required capabilities, accountabilities. Central organisational unit.
- **Person**: Human individual with identity and employment context. Owned by People/Capability plane. Occupies Roles.
- **Agent**: Software entity marker/record — no runtime execution logic in the domain model. Owned by People/Capability plane. Fulfils Roles.
- **EIMS**: Enterprise Information Management System. ConceptStore is the current implementation.
- **Work**: Instance of assigned effort. Accountable to a Role. Contains `required_capability_ids`, `accountable_role_id`, `coordinating_role_id`, `outcome`, `acceptance_criteria`, `dependencies`, `parent_work_id`.
- **People/Capability plane**: Peer domain plane owning capability definitions, lifecycle, people records, and capability governance. Does NOT own Work.
- **EnterpriseInformation**: Future abstraction between CEO and ConceptStore/EIMS. Proposed in ADR-030.
- **Outcome assessment**: Organisational concern that decides which execution results become accepted organisational outcomes.
- **Learning loop**: Structured flow from operational execution -> outcome -> EIMS -> future decisions.
- **BAU**: Business-as-Usual. Ongoing operational work accountable to COO/functional managers.
- **Project**: Bounded initiative work accountable to C-Suite executive, coordinated by Project Manager.
- **Distributed coordination**: Coordination belongs to roles (CEO, COO, C-Suite, PM, functional managers, specialists), not to central services.
- **Work decomposition**: Breaking large Work into smaller Work items via `parent_work_id` and `dependencies`. Management concern, not execution concern.
- **Accountability**: Role answerable for outcome. Explicitly modelled via `accountable_role_id` on Work.
- **Coordination**: Role sequencing and managing work. Explicitly modelled via `coordinating_role_id` on Work.
- **Operational handoff**: Transition from organisational Work to operational execution via `OrganisationControlPlane.mark_work_ready()`. Work.status ASSIGNED→IN_PROGRESS marks the boundary.
- **Execution result**: Evidence from Operations. NOT automatically an accepted organisational outcome.
- **Outcome assessment**: Process of evaluating execution result against acceptance_criteria to determine acceptance.
