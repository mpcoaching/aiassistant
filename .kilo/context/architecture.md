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

## Three-Plane Architecture

### Enterprise Plane
- **Owns:** strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning
- **Boundary:** Strategy interpretation, priority setting, escalation thresholds
- **Does NOT:** run operations, execute work, own capabilities

### Organisation / Control Plane
- **Owns:** organisational structure, roles, responsibilities, authority, delegation, relationships, allocation of organisational work, coordination between roles, organisational context, people/capability function
- **Boundary:** `OrganisationControlPlane` abstraction
- **Does NOT:** execute operational work, own EIMS, own capability definitions/lifecycle, directly control runtime agents

### Operations Plane
- **Owns:** workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work
- **Boundary:** `PathwayRuntime`, `Session`, `PatternStep`
- **Does NOT:** define organisational authority or strategy

## Role Model

| Concept | Description | Owner | Notes |
|---|---|---|---|
| **Role** | Abstract position with responsibilities, authority, constraints, information access | Organisation-Control | Template/blueprint; not a person or agent |
| **Person** | Human individual | People/Capability domain | Has identity, employment context |
| **Agent** | Software entity that performs work | Operations plane | Has runtime identity, executes patterns |
| **Capability** | Reusable unit of work (skill, tool, workflow) | People/Capability domain | Has lifecycle |
| **Work** | Instance of assigned effort | Organisation-Control | Has status, assignments, deliverables |
| **Authority** | Permission grant within scope | Organisation-Control | Can be delegated, has constraints |

### Distinctions

- **Role != Person:** A Role is an abstract position. A Person occupies a Role.
- **Role != Agent:** A Role defines what is needed. An Agent is a runtime executor that may fulfil a Role.
- **Capability != Agent:** A Capability is what can be done. An Agent is who/what does it.
- **Work != Capability:** Work is a specific assignment. Capability is reusable ability.

## EIMS Boundary

- **ConceptStore** is the current implementation of the Enterprise Information Management System (EIMS).
- EIMS owns: durable enterprise information, enterprise concepts, provenance, relationships, institutional knowledge, learning.
- EIMS does NOT own: runtime execution, orchestration, role assignment, authority, agent control, workflow execution, organisational control database.
- The eventual EIMS may expand beyond ConceptStore. Preserve architectural flexibility by treating ConceptStore as an implementation, not the complete EIMS.

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

## Domain Boundaries

| Domain | Responsibility | Key Types |
|---|---|---|
| Human Interface | Accept natural language, manage conversation state, render results | `AssistantChatService`, `ChatRequest`, `ChatResponse` |
| Recognition | Classify intent into structured context | `recognise()`, `ProblemFrame`, `ContextRecord` |
| Capability Discovery | Store and retrieve capability definitions | `CapabilityRegistry`, `Capability` |
| Capability Matching | Determine whether a capability satisfies a request | `CapabilityMatcher`, `HumanSelectionMatcher` |
| Capability Execution | Run capabilities deterministically | `execute_capability()`, `CompiledRef` |
| Capability Governance | Manage capability requests and approvals | `CapabilityRequest`, approval API |
| Enterprise Knowledge | Store concepts, outcomes, maturation | `ConceptStore`, `EnterpriseConcept`, `MaturationHistory` |
| Organisation/Control | Roles, authority, work assignment, delegation | `OrganisationControlPlane`, `Role`, `Work`, `Authority` |
| Execution (AI) | Run pattern pipelines via LangGraph | `PathwayRuntime`, `LangGraphRuntime` |
| Execution (Deterministic) | Run compiled workflows | `workflow-runner` substrate |

## Constraints

1. **Recognition before reasoning** — check capabilities before invoking LLM or reasoning patterns
2. **Enterprise assets are first-class** — concepts, decisions, playbooks outlive agents
3. **Frameworks are runtimes, not architecture** — LangGraph is a substrate, not the domain model
4. **Human-in-the-loop for governance** — capability specifications require human approval
5. **Deterministic execution first** — compile known patterns; reason only when uncertain
6. **Strict persistence** — write failures raise, never swallow
7. **No framework leakage** — Context, Session, and Capability schemas contain no framework-specific types
8. **Three-plane separation** — Enterprise, Organisation/Control, and Operations planes must not cross their boundaries
9. **Capability ownership stays in People/Capability** — CEO and OrganisationControlPlane must not own capability lifecycle
10. **Organisation domain import-clean** — no capability_registry, no concepts imports in organisation package

## Current Implementation State

### Implemented and Wired
- Infrastructure: Docker, Woodpecker CI, private registry
- CapabilityRegistry: register, get, list, resolve, record_invocation, promote
- ConceptStore: upsert, get, list_by_kind, list_by_tag, record_invocation
- Intent classification: rule-based regex keyword matching
- Strategy selection: static lookup table
- Session model: `create_session_from_decision()`
- AssistantChatService: wired but not yet using CapabilityRegistry
- Workflow Engine API: `/assistant/chat` endpoint exists
- Control Center UI: chat interface exists, handles `human_input_request`
- OrganisationControlPlane: ABC + InMemoryOrganisationControlPlane (Increment 6)
- Role model: Role, Person, Agent, Authority, Work, Assignment, OrgContext

### Not Yet Implemented
- Capability routing in `AssistantChatService`
- `CapabilityMatcher` interface
- `CapabilityExecutor`
- `CapabilityRequest` model
- Capability approval API
- Capability selection UI
- Kilo handoff contract via `.kilo/plans/`
- Paperclip adapter
- Complete People/Capability function
- Full CEO orchestration

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
