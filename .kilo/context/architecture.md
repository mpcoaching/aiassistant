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
OrganisationControlPlane is a narrow abstraction providing role lookup, work assignment, authority delegation, and organisational context retrieval. It is explicitly not a God service.

### ADR-023: Paperclip Adapter Boundary behind OrganisationControlPlane (Accepted)
The OrganisationControlPlane abstraction is defined independently of Paperclip. No Paperclip-specific types appear in the organisation domain.

### ADR-024: CEO as Organisational Role, not Universal Router (Accepted)
CEO is an organisational ROLE, not the central AI agent. CEOAgent consumes OrganisationControlPlane via DI and does not discover or select capabilities.

### ADR-025: Assistant as Organisational Role/Interface, not Implicit CEO (Accepted)
Assistant is a Role/interface, not an orchestrator. AssistantChatService routes to the appropriate organisational role via OrganisationControlPlane.

### ADR-026: People/Capability as Peer Domain Plane (Accepted)
People/Capability is a first-class domain plane alongside Enterprise, Organisation/Control, and Operations. It owns capability definitions, capability lifecycle, people records, and capability development/acquisition/testing.

### ADR-027: Work-Capability "Requires" Relationship (Accepted)
Work references required capabilities via `required_capability_ids` but does NOT own capability lifecycle. People/Capability owns capability definitions and lifecycle. Work is about effort allocation; Capability is about reusable ability.

### ADR-028: Role Workflow Handoff Model for Specialist Roles (Accepted)
EA, SA, BA, Designer, Developer, QA are Roles in the Organisation/Control plane. Work flows between them through explicit Assignment and handoff. Each role produces durable enterprise assets consumed by downstream roles.

### ADR-029: EIMS Learning Loop and Outcome Capture (Accepted)
Operational execution outcomes flow back into EIMS through a structured learning loop. Not all operational state becomes durable knowledge. The boundary between transient operational state and durable enterprise knowledge is explicit.

### ADR-030: Future EnterpriseInformation Abstraction for CEO (Proposed)
CEO should eventually consume an EnterpriseInformation abstraction rather than accessing ConceptStore directly. Do NOT implement until Increment 9+ unless immediately required.

## Four-Plane Architecture (Increment 7)

### Enterprise Plane
- **Owns:** strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning
- **Boundary:** Strategy interpretation, priority setting, escalation thresholds
- **Does NOT:** run operations, execute work, own capabilities

### Organisation / Control Plane
- **Owns:** organisational structure, roles, responsibilities, authority, delegation, relationships, allocation of organisational work, coordination between roles, organisational context
- **Boundary:** `OrganisationControlPlane` abstraction
- **Does NOT:** execute operational work, own EIMS, own capability definitions/lifecycle, directly control runtime agents, own people records

### People / Capability Plane
- **Owns:** people records, capability definitions, capability lifecycle (registration, maturation, promotion, retirement), capability development/acquisition/testing, capability matching, CapabilityRequest governance
- **Boundary:** `CapabilityRegistry`, `CapabilityMatcher`, `CapabilityRequest`
- **Does NOT:** own Work, assign work, define organisational authority, execute operational work, own EIMS

### Operations Plane
- **Owns:** workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work
- **Boundary:** `PathwayRuntime`, `Session`, `PatternStep`
- **Does NOT:** define organisational authority or strategy, own capability definitions, govern capability lifecycle

## Role Model

| Concept | Description | Owner | Notes |
|---|---|---|---|
| **Role** | Abstract position with responsibilities, authority, constraints, information access | Organisation-Control | Template/blueprint; not a person or agent |
| **Person** | Human individual with identity and employment context | People/Capability | Occupies one or more Roles |
| **Agent** | Software entity marker/record — no runtime execution logic in domain model | Operations plane | Fulfils a Role at runtime |
| **Capability** | Reusable unit of work (tool, skill, service) | People/Capability | Has lifecycle (register -> operate -> measure -> learn -> retire) |
| **Work** | Instance of assigned effort | Organisation-Control | Has status, assignments, deliverables, required_capability_ids |
| **Authority** | Permission grant within scope | Organisation-Control | Can be delegated, has constraints |

### Distinctions

- **Role != Person:** A Role is an abstract position. A Person occupies a Role.
- **Role != Agent:** A Role defines what is needed. An Agent is a runtime executor that may fulfil a Role.
- **Capability != Agent:** A Capability is what can be done. An Agent is who/what does it.
- **Work != Capability:** Work is a specific assignment. Capability is reusable ability.
- **Work requires Capability:** Work declares required capabilities by ID. Capability lifecycle remains in People/Capability.

### Specialist Roles (Future)

These are organisational Roles, not necessarily separate AI agents:
- CEO, Assistant, Enterprise Architect, Solution Architect, Business Analyst, Designer, Developer, QA, People/Capability

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
  | assigned to
  v
Role / Person / Agent (Organisation/Control domain)
```

When Work requires a capability that does not exist, a CapabilityRequest is created (transient governance artifact) to People/Capability.

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

## CEO and Assistant Roles

### CEO
- CEO is an organisational ROLE, not the central AI agent.
- CEO receives organisational context via OrganisationControlPlane.
- CEO does NOT discover/select capabilities or own capability lifecycle.
- CEOAgent is a lightweight orchestrator that classifies intent, checks for previous solutions, and delegates execution.

### Assistant
- Assistant is a Role/interface, not an orchestrator.
- AssistantChatService routes to the appropriate organisational role via OrganisationControlPlane.
- Assistant does NOT implicitly become CEO.

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

### Four-Plane Dependency Rules

1. Enterprise may read from all planes but owns strategy and durable knowledge.
2. Organisation/Control may read from People/Capability and Operations but owns roles, authority, and work assignment.
3. People/Capability may read from EIMS but owns capability definitions and lifecycle.
4. Operations may read from Organisation/Control and People/Capability but owns execution.
5. EIMS is written to by all planes but owned by Enterprise.
6. No plane may execute operational work on behalf of another plane.
7. No plane may own capability lifecycle except People/Capability.

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

### Not Yet Implemented
- Work-Capability relationship in data model (`required_capability_ids` on Work)
- People/Capability plane package and services
- Capability routing in `AssistantChatService`
- `CapabilityMatcher` interface (HumanSelectionMatcher exists but not formalised)
- Capability approval API
- Capability selection UI
- OutcomeRecorder / LearningService for EIMS promotion
- EnterpriseInformation abstraction for CEO-EIMS boundary
- Kilo handoff contract via `.kilo/plans/`
- Paperclip adapter
- Full CEO orchestration
- Specialist role implementations (EA, SA, BA, Developer, QA)
- Role workflow handoff enforcement

## Increment 8 Proposed Scope

### In Scope
1. **Work model extension:** Add `required_capability_ids: list[str]` and `acceptance_criteria: list[str]` to Work record in `packages/organisation/src/role.py`
2. **People/Capability plane documentation:** Formalise the peer domain boundary in architecture and create package skeleton (no production services yet)
3. **Capability lifecycle hooks:** Add optional callback/observer hooks to `CapabilityRegistry.record_invocation()` for future learning service integration
4. **Outcome capture prototype:** Simple prototype showing execution result -> EnterpriseConcept promotion flow
5. **Architectural boundary tests:** Verify Work does not import capability definitions, verify People/Capability does not import Work

### Out of Scope
- Full People/Capability service implementation
- Full CEO orchestration
- Paperclip integration
- EIMS expansion beyond ConceptStore
- EnterpriseInformation abstraction implementation
- All specialist role implementations
- Assistant redesign
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

- **Capability**: An `EnterpriseConcept` with `kind=capability`. Represents a tool, skill, or service.
- **CapabilityRequest**: Transient governance object for requesting new capabilities. Becomes `EnterpriseConcept` on approval.
- **HumanSelectionMatcher**: First implementation of `CapabilityMatcher`. Returns all capabilities as candidates; human selects.
- **MatchResult**: Output of `CapabilityMatcher.match()`. Contains candidates, confidence, matcher_id.
- **ExecutionMode**: `ai_mediated` (LLM-based) or `compiled` (deterministic code).
- **MaturationHistory**: Tracks invocation count, corrections, promotion status for capabilities.
- **OrganisationControlPlane**: Narrow abstraction for organisational coordination. Explicitly excludes capability execution.
- **Role**: Abstract position with responsibilities, authority, constraints, information access.
- **Person**: Human individual with identity and employment context.
- **Agent**: Software entity marker/record — no runtime execution logic in the domain model.
- **EIMS**: Enterprise Information Management System. ConceptStore is the current implementation.
- **Work**: Instance of assigned effort. Contains `required_capability_ids` referencing Capability IDs.
- **People/Capability plane**: Peer domain plane owning capability definitions, lifecycle, people records, and capability governance.
- **EnterpriseInformation**: Future abstraction between CEO and ConceptStore/EIMS. Proposed in ADR-030.
- **Outcome assessment**: Operational concern that decides which execution results become durable EIMS knowledge.
- **Learning loop**: Structured flow from operational execution -> outcome -> EIMS -> future decisions.
