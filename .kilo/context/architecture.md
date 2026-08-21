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

### Not Yet Implemented
- Capability routing in `AssistantChatService`
- `CapabilityMatcher` interface
- `CapabilityExecutor`
- `CapabilityRequest` model
- Capability approval API
- Capability selection UI
- Kilo handoff contract via `.kilo/plans/`

## First Vertical Slice

**Objective:** Prove the capability lifecycle: request → recognise → capability check → execute OR gap → governance → implementation → registration → execution → reuse.

**First capability:** `create_test_artifact` — deterministic, creates an `EnterpriseConcept`, returns artifact_id.

**Experiment boundary:**
- Human selects capability from available list (HumanSelectionMatcher)
- Human fills CapabilityRequest template for missing capabilities
- Human approves specification before implementation
- Kilo implements from approved specification
- New capability registered and executable

**Not proven in first slice:** semantic matching, automatic gap specification, LLM integration, agent workforce, CEO orchestration.

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

pytest supports this via `conftest.py` which adds each package's `src/` to `sys.path`. Runtime environments must set `PYTHONPATH` to include all package `src/` directories.

Current Docker PYTHONPATH:
```
/app:/app/src:/packages/configuration/src:/packages/ai/src:/packages/bus/src:/packages/langgraph/src:/packages/capability_registry/src
```

## Glossary

- **Capability**: An `EnterpriseConcept` with `kind=capability`. Represents a tool, skill, or service.
- **CapabilityRequest**: Transient governance object for requesting new capabilities. Becomes `EnterpriseConcept` on approval.
- **HumanSelectionMatcher**: First implementation of `CapabilityMatcher`. Returns all capabilities as candidates; human selects.
- **MatchResult**: Output of `CapabilityMatcher.match()`. Contains candidates, confidence, matcher_id.
- **ExecutionMode**: `ai_mediated` (LLM-based) or `compiled` (deterministic code).
- **MaturationHistory**: Tracks invocation count, corrections, promotion status for capabilities.
