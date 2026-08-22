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
OrganisationControlPlane is a narrow abstraction providing role lookup, work assignment, authority delegation, and organisational context retrieval. It provides organisational mechanisms and context through which roles operate. It does NOT coordinate work, become the project manager, or become the COO.

### ADR-023: Paperclip Adapter Boundary behind OrganisationControlPlane (Accepted)
The OrganisationControlPlane abstraction is defined independently of Paperclip. No Paperclip-specific types appear in the organisation domain.

### ADR-024: CEO as Organisational Role, not Universal Router (Accepted)
CEO is an organisational ROLE, not the central AI agent. CEO does not discover/select capabilities or own capability lifecycle. **Superseded by ADR-031 for CEO responsibilities scope.**

### ADR-025: Assistant as Organisational Role/Interface, not Implicit CEO (Accepted)
Assistant is a Role/interface, not an orchestrator. AssistantChatService routes to the appropriate organisational role via OrganisationControlPlane.

### ADR-026: People/Capability as Peer Domain Plane (Accepted)
People/Capability is a first-class domain plane alongside Enterprise, Organisation/Control, and Operations. It owns capability definitions, capability lifecycle, people records, and capability development/acquisition/testing. It does NOT own Work.

### ADR-027: Work-Capability "Requires" Relationship (Accepted)
Work references required capabilities via `required_capability_ids` but does NOT own capability lifecycle. People/Capability owns capability definitions and lifecycle. Work is about effort allocation; Capability is about reusable ability.

### ADR-028: Role Workflow Handoff Model for Specialist Roles (Accepted)
EA, SA, BA, Designer, Developer, QA are Roles in the Organisation/Control plane. Work flows between them through explicit Assignment and handoff. Each role produces durable enterprise assets consumed by downstream roles. **Superseded by ADR-033 for project coordination.**

### ADR-029: EIMS Learning Loop and Outcome Capture (Accepted)
Operational execution outcomes flow back into EIMS through a structured learning loop. Not all operational state becomes durable knowledge. The boundary between transient operational state and durable enterprise knowledge is explicit.

### ADR-030: Future EnterpriseInformation Abstraction for CEO (Proposed)
CEO should eventually consume an EnterpriseInformation abstraction rather than accessing ConceptStore directly. Do NOT implement until Increment 9+ unless immediately required.

### ADR-031: CEO as Strategic Role, Not Orchestrator (Accepted)
Supersedes ADR-024. The CEO is an organisational ROLE with strategic responsibilities only. The CEO makes strategic decisions, establishes strategic direction, observes organisational performance, and intervenes at the strategic level. The CEO does NOT organise day-to-day work, assign individual operational tasks, manage project delivery, coordinate specialist work, select capabilities, execute operational work, or act as a universal system router.

### ADR-032: COO as Organisational Role for BAU (Accepted)
The COO is an organisational ROLE accountable for Business-as-Usual (BAU) operational performance. The COO observes operational outcomes, manages operational capacity, handles exceptions, and coordinates functional managers. The COO does NOT become the Operations plane, micro-manage every task, or execute operational work.

### ADR-033: Project Management as Organisational Role (Accepted)
Project Manager / Delivery Manager is an organisational ROLE, not an operations engine. The PM coordinates project delivery, sequences work, tracks progress, manages dependencies, surfaces risks, and coordinates specialist roles. The PM does NOT become the Operations plane, execute every task, own every capability, or replace specialist roles.

### ADR-034: Work Accountability Model (Accepted)
Work is accountable to an appropriate Role, not owned by Organisation/Control. Work carries explicit accountability, coordination, assignment, and outcome fields. Every Work item has exactly one `accountable_role_id`. BAU work and project work have different accountability structures.

### ADR-035: Capability / Skill / Tool Distinction Investigation (Proposed)
Do NOT collapse Skill and Tool into Capability merely for implementation convenience. Investigate whether a cleaner model distinguishes Capability (ability), Skill (component), Tool (enabler), and Resource (supporting material). Do NOT implement until the domain boundary is understood.

### ADR-036: Distributed Organisational Coordination (Accepted)
Organisational coordination is distributed according to responsibility and authority. No single role, service, or plane coordinates all organisational activity. The OrganisationControlPlane provides mechanisms and context; actual coordination belongs to appropriate roles (CEO, COO, C-Suite executives, Project Managers, functional managers, specialist roles).

## Four-Plane Architecture (Corrected)

### Enterprise Plane
- **Owns:** strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning
- **Boundary:** Strategy interpretation, priority setting, escalation thresholds
- **Does NOT:** run operations, execute work, own capabilities, coordinate organisational work

### Organisation / Control Plane
- **Owns:** organisational structure, roles, relationships, authority, accountability, management mechanisms, organisational context
- **Boundary:** `OrganisationControlPlane` abstraction — provides mechanisms and context, NOT coordination
- **Does NOT:** execute operational work, own EIMS, own capability definitions/lifecycle, directly control runtime agents, own people records, coordinate work, become the CEO/COO/PM

### People / Capability Plane
- **Owns:** people records, capability definitions, capability lifecycle (registration, maturation, promotion, retirement), capability development/acquisition/testing, capability matching, CapabilityRequest governance, capability readiness
- **Boundary:** `CapabilityRegistry`, `CapabilityMatcher`, `CapabilityRequest`
- **Does NOT:** own Work, assign work, define organisational authority, execute operational work, own EIMS, coordinate organisational work

### Operations Plane
- **Owns:** workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work
- **Boundary:** `PathwayRuntime`, `Session`, `PatternStep`
- **Does NOT:** define organisational authority or strategy, own capability definitions, govern capability lifecycle, coordinate organisational work

## Role Model

### Core Concepts

| Concept | Description | Owner | Notes |
|---|---|---|---|
| **Role** | Abstract position with responsibilities, authority, constraints, information access, required capabilities | Organisation-Control | Template/blueprint; not a person or agent |
| **Person** | Human individual with identity and employment context | People/Capability | Occupies one or more Roles |
| **Agent** | Software entity marker/record — no runtime execution logic in domain model | Operations plane | Fulfils a Role at runtime |
| **Capability** | Reusable unit of work (tool, skill, service) | People/Capability | Has lifecycle (register -> operate -> measure -> learn -> retire) |
| **Skill** | Component of a capability (knowledge, method, technique) | People/Capability | Part of Capability; distinction under investigation (ADR-035) |
| **Tool** | Something used to enable/support a capability | IT/Technology or People/Capability | Ownership under investigation (ADR-035) |
| **Work** | Instance of assigned effort | Organisation-Control | Accountable to a Role; has status, assignments, deliverables, required_capability_ids |
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
Person / Agent
      |
      | fulfils
      v
    Role
      |
      | requires
      v
  Capability
      ^
      | possesses / fulfils
Person / Agent
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

## EIMS Boundary and Learning Loop

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

- **Transient operational state:** Session state, workflow execution state, runtime agent state, human-in-the-loop pending state.
- **Durable EIMS knowledge:** Strategy decisions, capability definitions, work outcomes, enterprise assets, governance decisions, institutional learning.
- **Capability maturation** is the first implemented learning loop: `execute_capability()` -> caller invokes `record_invocation()` -> `MaturationHistory` updated -> promotion threshold may trigger COMPILED mode.
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
- COO is an organisational ROLE accountable for Business-as-Usual operational performance.
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

## Four-Plane Dependency Rules

1. Enterprise may read from all planes but owns strategy and durable knowledge.
2. Organisation/Control may read from People/Capability and Operations but owns roles, authority, and work assignment mechanisms.
3. People/Capability may read from EIMS but owns capability definitions and lifecycle.
4. Operations may read from Organisation/Control and People/Capability but owns execution.
5. EIMS is written to by all planes but owned by Enterprise.
6. No plane may execute operational work on behalf of another plane.
7. No plane may own capability lifecycle except People/Capability.
8. No plane or role may coordinate work outside its authority boundary.
9. The OrganisationControlPlane provides mechanisms; roles provide coordination.

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

## Architectural Questions Answered

1. **What exactly is the organisational responsibility of the CEO?**
   Strategic decision-making, strategic direction, observing organisational performance, reviewing significant outcomes, intervening at strategic level, changing direction when necessary. The CEO does NOT organise day-to-day work or assign operational tasks.

2. **What exactly is the organisational responsibility of the COO?**
   BAU operational performance oversight, outcomes tracking, capacity management, exception handling, cross-functional coordination, reporting operational health to CEO. The COO does NOT execute operational work or micro-manage tasks.

3. **Where does a C-Suite executive's accountability begin and end?**
   A C-Suite executive is accountable for a business outcome resulting from a strategic initiative. They appoint/approve the Project Manager, receive outcome reports, and are answerable to the CEO. They do NOT coordinate project delivery details.

4. **Where does a Project Manager's authority begin and end?**
   A PM coordinates project delivery: sequencing, tracking, dependencies, risks, specialist coordination, reporting. The PM does NOT own the business outcome, execute tasks, or replace specialist roles.

5. **Is Work accountable to a Role rather than owned by Organisation/Control?**
   Yes. Work is accountable to an appropriate Role (`accountable_role_id`). Organisation/Control provides assignment mechanisms but does not own Work.

6. **How are BAU responsibilities represented differently from temporary project work?**
   BAU work has `work_type="bau"`, is accountable to COO/functional managers, and is ongoing. Project work has `work_type="project"`, is accountable to a C-Suite executive, coordinated by a PM, and is bounded.

7. **What is the relationship between Role, Person, Agent and Capability?**
   Person/Agent fulfils Role. Role requires Capability. Person/Agent possesses Capability. Capability is portable between roles.

8. **Can capabilities move between roles?**
   Yes. Capabilities are owned by People/Capability and are portable. The same capability may be required by different roles over time.

9. **Who determines whether a person/agent is capable of fulfilling a role?**
   People/Capability determines capability readiness: whether a person/agent has the required capabilities, needs training, or requires capability development/acquisition.

10. **Who identifies capability gaps?**
    CEO may identify capability gaps as organisational observations. People/Capability validates and resolves them through the capability lifecycle.

11. **Who develops/acquires/trains capabilities?**
    People/Capability develops, acquires, tests, and registers capabilities. Training/development is determined by People/Capability based on role requirements.

12. **Who decides when work actually happens?**
    The coordinating role (functional manager for BAU, Project Manager for projects) decides scheduling within their authority. Operations executes when scheduled.

13. **Who coordinates work?**
    Distributed by role: COO for BAU cross-functional, functional managers for functional BAU, Project Manager for projects, specialist roles for specialist work.

14. **Who executes work?**
    Operations plane executes operational work through workflows, pathways, sessions, and runtime agents.

15. **What is the exact responsibility of OrganisationControlPlane?**
    Provides organisational mechanisms and context: role definitions, relationships, reporting hierarchy, authority, delegation, organisational context, role assignment mechanisms. Does NOT coordinate work, become roles, or execute work.

16. **What belongs in People/Capability versus Organisation/Control?**
    People/Capability: people records, capability definitions, capability lifecycle, capability matching, capability readiness, CapabilityRequest governance. Organisation/Control: roles, authority, work assignment mechanisms, accountability relationships, organisational structure.

17. **What belongs in Operations versus organisational management?**
    Operations: execution, workflows, runtime, tools, agents, operational processes. Organisational management (roles): strategic decisions, BAU oversight, project coordination, specialist work direction, accountability.

18. **Does the current Work model reflect accountability and coordination correctly?**
    No. Current Work model lacks `accountable_role_id`, `coordinating_role_id`, `work_type`, `outcome`, and `acceptance_criteria`. These must be added.

19. **Does Paperclip fit naturally behind OrganisationControlPlane?**
    Yes. Paperclip implements organisational mechanisms (role/agent representation, work assignment, coordination, approvals, hierarchy) behind the OrganisationControlPlane abstraction.

20. **Does the architecture still work if there are humans, AI agents, or mixed teams?**
    Yes. The Role model is agnostic to fulfilment type. A Role may be fulfilled by human, AI agent, human+AI, or multiple people/agents. The domain model does not change.

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
- Four-plane architecture documented (Increment 7)
- Corrected role model with CEO/COO/PM/C-Suite distinctions (Increment 7 correction)

### Not Yet Implemented
- Work accountability model (`accountable_role_id`, `coordinating_role_id`, `work_type`, `outcome`, `acceptance_criteria`)
- People/Capability plane package and services
- Capability routing in `AssistantChatService`
- `CapabilityMatcher` interface (HumanSelectionMatcher exists but not formalised)
- Capability approval API
- Capability selection UI
- OutcomeRecorder / LearningService for EIMS promotion
- EnterpriseInformation abstraction for CEO-EIMS boundary
- Kilo handoff contract via `.kilo/plans/`
- Paperclip adapter
- Full CEO implementation as strategic role
- COO implementation
- C-Suite executive roles
- Project Manager implementation
- Specialist role implementations (EA, SA, BA, Developer, QA)
- Role workflow handoff enforcement
- Capability/Skill/Tool distinction (under investigation)

## Increment 8 Proposed Scope (Revised)

### In Scope
1. **Work model extension:** Add `work_type`, `accountable_role_id`, `coordinating_role_id`, `outcome`, `acceptance_criteria` to Work record in `packages/organisation/src/role.py`
2. **People/Capability plane documentation:** Formalise the peer domain boundary in architecture
3. **Architectural boundary tests:** Verify Work accountability model, verify plane boundaries
4. **Capability/Skill/Tool investigation documentation:** Document findings from ADR-035 investigation

### Out of Scope
- Full People/Capability service implementation
- Full CEO implementation as strategic role
- COO implementation
- C-Suite executive roles
- Project Manager implementation
- Paperclip integration
- EIMS expansion beyond ConceptStore
- EnterpriseInformation abstraction implementation
- All specialist role implementations
- Assistant redesign
- Capability matching implementation
- Capability execution in CEO
- Universal routing

## Test Baseline

```
pytest packages/capability_registry/tests/test_capabilities.py packages/ai/tests/test_assistant.py -q
Result: 18 passed
```

## Import Model

The repository uses **flat imports** from package `src/` directories:
- `packages/ai/src/assistant.py` exports `AssistantReasoningService`
- `packages/capability_registry/src/capabilities.py` exports `CapabilityRegistry`
- `packages/workflow_runner/src/session.py` exports `Session`
- `packages/organisation/src/organisation_control_plane.py` exports `OrganisationControlPlane`

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
- **OrganisationControlPlane**: Narrow abstraction providing organisational mechanisms and context. Does NOT coordinate work or become management roles.
- **Role**: Abstract position with responsibilities, authority, constraints, information access, required capabilities, accountabilities. Central organisational unit.
- **Person**: Human individual with identity and employment context. Occupies Roles.
- **Agent**: Software entity marker/record — no runtime execution logic in the domain model. Fulfils Roles.
- **EIMS**: Enterprise Information Management System. ConceptStore is the current implementation.
- **Work**: Instance of assigned effort. Accountable to a Role. Contains `required_capability_ids`, `accountable_role_id`, `coordinating_role_id`, `outcome`, `acceptance_criteria`.
- **People/Capability plane**: Peer domain plane owning capability definitions, lifecycle, people records, and capability governance. Does NOT own Work.
- **EnterpriseInformation**: Future abstraction between CEO and ConceptStore/EIMS. Proposed in ADR-030.
- **Outcome assessment**: Operational concern that decides which execution results become durable EIMS knowledge.
- **Learning loop**: Structured flow from operational execution -> outcome -> EIMS -> future decisions.
- **BAU**: Business-as-Usual. Ongoing operational work accountable to COO/functional managers.
- **Project**: Bounded initiative work accountable to C-Suite executive, coordinated by Project Manager.
- **Distributed coordination**: Coordination belongs to roles (CEO, COO, C-Suite, PM, functional managers, specialists), not to central services.
