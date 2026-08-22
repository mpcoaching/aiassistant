# Increment 15 — Assistant Boundary Correction: Investigation Report

## Goal

Correct the `AssistantChatService` architecture to respect the four-plane boundary, eliminate the "God service" pattern in the AI plane, and resolve the failing test `test_chat_service_returns_previous_solution` by addressing the underlying architectural defect rather than changing the assertion.

## Executive Summary

`AssistantChatService` (`packages/ai/src/chat.py`) has become a universal orchestrator that crosses all four plane boundaries. It directly imports and uses:

- **People/Capability**: `CapabilityRegistry`, `CapabilityMatcher`, `Capability`, `HumanSelectionMatcher`
- **Enterprise/EIMS**: `ConceptStore`, `EnterpriseConcept`, `ConceptKind`
- **Operations**: `PathwayRuntime`, `PathwayCallRequest`, `PathwayResponse`, `PathwayStatus`, `execute_capability`, `Session`, `create_session_from_decision`, `HumanInTheLoopMixin`
- **AI (own plane)**: `AssistantReasoningService`, `Intent`, `recognise`, `StrategyDecision`

This recreates the exact "God service" pattern that ADR-017 warned about and that ADR-031 corrected for CEO. The AI plane was intended to own intent recognition, strategy selection, and reasoning. It was never intended to own capability matching, EIMS access, session creation, runtime invocation, or execution.

The failing test `test_chat_service_returns_previous_solution` is a symptom, not the disease. The test expects `awaiting_confirmation` (previous solution found) but receives `awaiting_capability_selection` because capability matching runs first and short-circuits the flow. The test exposes that Assistant is doing capability matching itself, which violates the architecture.

---

## 1. What is Assistant Actually?

### Current Reality

`AssistantChatService` is an **application-layer orchestrator** masquerading as a chat interface. It is not:

- an organisational Role (no `Role` record, no `accountable_role_id`, no authority)
- an Agent (no `Agent` record, no lifecycle)
- a thin interface (it contains all routing logic)

It is a **God service** that:
1. Classifies intent
2. Matches capabilities
3. Looks up previous solutions in EIMS
4. Creates sessions
5. Invokes runtimes
6. Records solutions back to EIMS
7. Executes capabilities directly

### Architectural Re-evaluation Against Four-Plane Model

The four-plane architecture defines:

| Plane | Owns | Does NOT |
|---|---|---|
| Enterprise | strategy, durable knowledge, EIMS | run operations, execute work |
| Organisation/Control | roles, authority, work assignment mechanisms | execute work, own EIMS, own capabilities |
| People/Capability | capabilities, people records, capability lifecycle | own Work, execute work, coordinate |
| Operations | workflows, runtime, execution | define authority, own capabilities |

**Assistant does not fit cleanly into any plane.** It is an **application-layer entry point** that translates human interaction into plane-specific requests.

The correct identity is:

> **Assistant is an application-layer translation service, not a domain service.**
>
> It owns:
> - Natural language intake
> - Intent/strategy recognition (AI reasoning)
> - Translating recognised intent into structured requests for other planes
> - Presenting options/results back to the user
>
> It does NOT own:
> - Capability matching (People/Capability)
> - Capability execution (Operations)
> - EIMS read/write (Enterprise/EIMS)
> - Work creation/assignment (Organisation/Control)
> - Authority decisions (Organisation/Control)

This is consistent with ADR-025's intent ("thin interface, not hidden orchestrator") but corrects the implementation reality.

---

## 2. What Should Assistant Own?

### In Scope for Assistant

| Responsibility | Owner Plane | Rationale |
|---|---|---|
| Natural language message intake | Application/AI | User interaction boundary |
| Intent recognition (`recognise()`) | AI | Pure reasoning |
| Strategy selection (`select_strategy()`) | AI | Pure reasoning |
| Translating intent → Work request | Application | Thin translation |
| Translating intent → capability execution request | Application | Thin translation |
| Presenting candidates/results to user | Application | UI concern |
| Human-in-the-loop pause/resume | Application | Session state management |

### Out of Scope for Assistant (Current Violations)

| Responsibility | Current Location | Correct Owner | Violation |
|---|---|---|---|
| Capability matching | `chat.py::_match_capabilities()` | People/Capability | AI plane directly imports `CapabilityMatcher`, `CapabilityRegistry` |
| EIMS previous solution lookup | `chat.py::_find_previous_solution()` | Enterprise/EIMS | AI plane directly imports `ConceptStore` |
| EIMS solution recording | `chat.py::_record_solution()` | Enterprise/EIMS | AI plane directly imports `ConceptStore`, `EnterpriseConcept` |
| Session creation | `chat.py::chat()` | Operations | AI plane directly imports `create_session_from_decision` |
| Runtime invocation | `chat.py::chat()` | Operations | AI plane directly imports `PathwayRuntime` |
| Capability execution | `chat.py::execute_selected_capability()` | Operations | AI plane directly imports `execute_capability` |

### Specific Investigation Findings

#### Conversation/Session Handling
Currently: `AssistantChatService` creates `Session` objects directly via `create_session_from_decision()`.
Correct: Session creation is an Operations concern. Assistant should request session creation through an interface, or Operations should expose a session factory.

#### Interpreting User Intent
Currently: `recognise(intent)` and `select_strategy(frame)` — these are correct in the AI plane. No violation.

#### Determining What Work is Being Discussed
Currently: Not explicitly modelled. Assistant jumps straight to capability matching or strategy selection.
Correct: If the request implies organisational work, Assistant should translate it into a Work request for Organisation/Control. This is not implemented yet and should be deferred.

#### Capability Requests
Currently: `_match_capabilities()` directly calls `CapabilityRegistry.list_all()` and `HumanSelectionMatcher.match()`.
Correct: Capability matching belongs to People/Capability. Assistant should request matching through a port, not call it directly.

#### Capability Discovery/Matching
Currently: Direct import and call.
Correct: People/Capability owns `CapabilityMatcher`. Assistant should depend on a `CapabilityDiscoveryPort` interface.

#### Invoking Capabilities
Currently: `execute_selected_capability()` calls `execute_capability()` directly.
Correct: Operations owns `execute_capability()` and `PatternRuntime.invoke_step()`. Assistant should depend on a `CapabilityExecutionPort` interface.

#### Presenting Results
Currently: Builds `ChatResponse` directly.
Correct: This is fine — it's the application-layer translation concern.

#### Asking for Clarification
Currently: Returns `awaiting_human_input` or `awaiting_capability_selection` status strings.
Correct: This is fine as a UI concern, but the conditions that trigger each status should be delegated.

#### Authority/Approval
Currently: Not implemented in Assistant. Authority is implicit (any capability can be executed).
Correct: Authority checks belong to People/Capability (`ExecutionAuthorisationPort`) and Organisation/Control. Assistant should not make authority decisions.

#### Learning from Conversations
Currently: `_record_solution()` writes directly to `ConceptStore`.
Correct: Learning/outcome recording is an organisational/enterprise concern. Assistant should request recording through an interface.

---

## 3. The Current Bypass — Complete Trace

### `packages/ai/src/chat.py` Dependency Map

```
AssistantChatService
├── AI plane (own plane) — VALID
│   ├── AssistantReasoningService
│   ├── StrategyDecision
│   ├── Intent
│   ├── recognise()
│   └── ProblemFrame
│
├── People/Capability — VIOLATION
│   ├── CapabilityRegistry
│   ├── CapabilityMatcher
│   ├── HumanSelectionMatcher
│   └── Capability
│
├── Enterprise/EIMS — VIOLATION
│   ├── ConceptStore
│   ├── EnterpriseConcept
│   └── ConceptKind
│
├── Operations — VIOLATION
│   ├── PathwayRuntime
│   ├── PathwayCallRequest
│   ├── PathwayResponse
│   ├── PathwayStatus
│   ├── execute_capability
│   ├── ExecutionResult
│   ├── Session
│   └── create_session_from_decision
│
└── enterprise_context — VALID (AI plane owns context enums)
    └── ContextRecord
```

### Dependency Assessment

| Dependency | Valid? | Recommendation |
|---|---|---|
| `AssistantReasoningService` | ✅ Valid | Own plane |
| `StrategyDecision` | ✅ Valid | Own plane |
| `Intent`, `recognise()` | ✅ Valid | Own plane |
| `ProblemFrame` | ✅ Valid | Own plane |
| `ContextRecord` | ✅ Valid | Own plane |
| `CapabilityRegistry` | ❌ Violation | Replace with `CapabilityDiscoveryPort` |
| `CapabilityMatcher` | ❌ Violation | Move to People/Capability consumer |
| `HumanSelectionMatcher` | ❌ Violation | Move to People/Capability consumer |
| `Capability` | ❌ Violation | Replace with port interface |
| `ConceptStore` | ❌ Violation | Replace with `EnterpriseInformationPort` |
| `EnterpriseConcept` | ❌ Violation | Replace with port interface |
| `ConceptKind` | ❌ Violation | Replace with port interface |
| `PathwayRuntime` | ❌ Violation | Replace with `PatternExecutionPort` |
| `PathwayCallRequest` | ❌ Violation | Replace with port interface |
| `PathwayResponse` | ❌ Violation | Replace with port interface |
| `PathwayStatus` | ❌ Violation | Replace with port interface |
| `execute_capability` | ❌ Violation | Replace with `CapabilityExecutionPort` |
| `ExecutionResult` | ❌ Violation | Replace with port interface |
| `Session` | ❌ Violation | Replace with `SessionFactoryPort` |
| `create_session_from_decision` | ❌ Violation | Replace with port interface |
| `HumanInTheLoopMixin` | ❌ Violation | Move to Operations or application layer |

### The Bypass Mechanism

The "bypass" referred to in Increment 14 is not a single line of code. It is the **entire architecture of `AssistantChatService`**:

1. **Capability matching bypass**: `chat.py` calls `CapabilityMatcher` directly instead of asking People/Capability to match.
2. **EIMS bypass**: `chat.py` reads/writes `ConceptStore` directly instead of going through an enterprise information boundary.
3. **Execution bypass**: `chat.py` calls `execute_capability()` directly instead of asking Operations to execute.
4. **Session bypass**: `chat.py` creates sessions directly instead of asking Operations.

Each of these is a plane boundary violation. Together, they make AssistantChatService a God service.

---

## 4. The Correct Assistant Flow

### Scenario A: User asks a normal informational question

```
User → Assistant (AI plane: recognise + select_strategy)
     → No capability needed, no work needed
     → Assistant generates informational response
     → User receives answer
```

**No plane crossing beyond AI reasoning.** Assistant stays within its own plane for pure reasoning questions.

### Scenario B: User asks Assistant to perform an existing capability

```
User → Assistant (AI plane: recognise + select_strategy)
     → Assistant creates CapabilityExecutionRequest
     → Assistant calls CapabilityExecutionPort.execute(capability_id, context)
     → [Port implementation in Operations]
     → Operations: PatternRuntime.invoke_step() or execute_capability()
     → People/Capability: authorisation check via ExecutionAuthorisationPort
     → Result flows back through port
     → Assistant presents result to user
```

**Key**: Assistant does NOT know which capabilities exist. It does NOT match capabilities. It only forwards a capability execution request.

### Scenario C: User asks for something requiring multiple capabilities

```
User → Assistant (AI plane: recognise + select_strategy)
     → Assistant creates MultiCapabilityExecutionRequest
     → Assistant calls CapabilityExecutionPort.execute_many(...)
     → [Port implementation in Operations]
     → Operations: PatternRuntime or workflow orchestrates multiple invocations
     → People/Capability: authorisation for each capability
     → Results flow back
     → Assistant synthesises and presents
```

**Key**: Orchestration of multiple capabilities belongs to Operations (PatternRuntime/workflow), not Assistant.

### Scenario D: User asks for something with no existing capability

```
User → Assistant (AI plane: recognise + select_strategy)
     → Assistant determines no capability matches
     → Option 1: Generate response from reasoning (if AI can answer)
     → Option 2: Create Work request for Organisation/Control
     → Option 3: Create CapabilityRequest for People/Capability
```

**Key**: Assistant does NOT create capabilities itself. It requests creation through the appropriate plane.

### Scenario E: Actor not authorised or proficient

```
User → Assistant (AI plane: recognise)
     → Assistant calls CapabilityExecutionPort.execute(...)
     → Operations: checks ExecutionAuthorisationPort
     → People/Capability: returns NOT_AUTHORISED or NOT_PROFICIENT
     → Operations returns authorisation failure through port
     → Assistant presents "not authorised" message to user
```

**Key**: Authority is checked by People/Capability and enforced by Operations. Assistant merely presents the result.

### Scenario F: Assistant needs organisational context

```
User → Assistant (AI plane: recognise)
     → Assistant calls OrganisationalContextPort.get_context(actor_id, role_id)
     → [Port implementation in Organisation/Control]
     → OrganisationControlPlane returns OrgContext
     → Assistant uses context for intent classification
```

**Key**: Assistant reads context through a port. It does not instantiate `OrganisationControlPlane` directly.

### Scenario G: Assistant needs to create organisational Work

```
User → Assistant (AI plane: recognise + select_strategy)
     → Assistant determines Work is needed
     → Assistant creates WorkCreateRequest
     → Assistant calls WorkManagementPort.create_work(request)
     → [Port implementation in Organisation/Control]
     → OrganisationControlPlane creates Work, assigns to appropriate Role
     → Returns Work reference
     → Assistant may call WorkManagementPort.mark_ready(work_id)
     → Operations picks up ready Work
```

**Key**: Work creation and assignment belong to Organisation/Control. Assistant only translates.

### Scenario H: Assistant acting on behalf of a Role with delegated authority

```
User → Assistant (AI plane: recognise)
     → Assistant receives actor_id + role_id in context
     → Assistant calls OrganisationalContextPort.get_context(actor_id, role_id)
     → Organisation/Control returns OrgContext including delegated authority
     → Assistant includes context in all subsequent requests
     → CapabilityExecutionPort, WorkManagementPort, etc. use context for authorisation
```

**Key**: Delegated authority is resolved by Organisation/Control. Assistant carries the context but does not interpret it.

---

## 5. "Assistant as Orchestrator" — Critical Investigation

### The Risk

The architecture must NOT accidentally recreate the CEO God service mistake. The current `AssistantChatService` is exactly that: a God service in the AI plane.

### What Assistant Should NOT Do

Assistant must NOT:
- **Orchestrate capabilities**: It should not decide which capability to use or sequence multiple capabilities.
- **Orchestrate Work**: It should not create, assign, or coordinate Work.
- **Execute capabilities**: It should not call `execute_capability()` or construct `PatternRuntime`.
- **Own execution metadata**: It should not construct `CapabilityDeployment`.
- **Make authority decisions**: It should not determine whether an action is authorised.
- **Access EIMS directly**: It should not read/write `ConceptStore`.

### What Assistant Should Do

Assistant should:
- **Translate**: Convert natural language intent into structured requests for other planes.
- **Delegate**: Send requests through ports/interfaces to the owning plane.
- **Present**: Format responses from other planes for human consumption.
- **Reason**: Apply AI reasoning (intent recognition, strategy selection) to understand the request.

### The Difference Between Orchestration and Translation

| Aspect | Orchestration (WRONG) | Translation (CORRECT) |
|---|---|---|
| Capability selection | Assistant decides which capability to use | Assistant forwards a capability execution request; People/Capability/Operations decides |
| Work creation | Assistant creates Work directly | Assistant translates intent into a Work request; Organisation/Control creates Work |
| Execution | Assistant invokes `execute_capability()` | Assistant calls `CapabilityExecutionPort.execute()`; Operations executes |
| Authority | Assistant checks `is_authorised()` | Assistant forwards context; People/Capability enforces authorisation |
| Sequencing | Assistant sequences multiple capabilities | Assistant requests execution; Operations/PatternRuntime sequences |

### If Assistant is Allowed to Coordinate

If Assistant is ever allowed to coordinate anything, the exact boundary is:

> **Assistant may coordinate conversational flow only.**
>
> Conversational coordination includes:
> - Asking clarifying questions
> - Presenting options for human selection
> - Resuming paused conversations
> - Managing conversational state
>
> Conversational coordination does NOT include:
> - Selecting capabilities
> - Sequencing operational steps
> - Creating organisational Work
> - Making authority decisions
> - Executing capabilities

This preserves the distinction between:
- **Conversational orchestration**: Managing the dialogue with the human (Assistant's job)
- **Organisational coordination**: Managing work assignment and accountability (Roles' job)
- **Capability selection**: Determining which capability serves a need (People/Capability's job)
- **Operational execution**: Running capabilities and workflows (Operations' job)

---

## 6. Capability Matching Investigation

### Increment 14 Deliberate Non-Implementation

Increment 14 deliberately did NOT implement capability matching. `HumanSelectionMatcher` is a stub that returns all capabilities. The real matching algorithm is deferred.

### How Assistant Should Interact with Matching

Currently: Assistant calls `CapabilityMatcher.match()` directly.

Correct: Assistant should NOT interact with capability matching at all. The dependency should be:

```
Assistant → CapabilityDiscoveryPort (interface)
         → [implementation in People/Capability or Operations]
         → CapabilityMatcher (inside implementation)
```

Or, if capability matching is part of the execution request:

```
Assistant → CapabilityExecutionPort.execute(request)
         → Operations/People/Capability handles matching internally
```

**Recommendation**: Capability matching should be an internal concern of the execution port. Assistant should not see capabilities at all — it should only say "execute this" and let the implementation find the right capability.

### Why This Matters

If Assistant sees capabilities, it will eventually start making decisions about them. That is the path back to God service. The boundary should be:

> Assistant knows **what** the user wants to do.
> The implementation figures out **how** to do it.

---

## 7. Execution Investigation

### Current State

`AssistantChatService.execute_selected_capability()` calls `execute_capability(capability, context)` directly, bypassing `PatternRuntime` and `CapabilityDeployment`.

### Correct Interaction

The architecture defines:

| Component | Owner | Responsibility |
|---|---|---|
| `CapabilityDeployment` | Operations | Execution binding for a capability |
| `PatternRuntime.invoke_step()` | Operations | Executes a capability step with deployment |
| `execute_capability()` | Operations | Executes a compiled capability |
| `ExecutionAuthorisationPort` | People/Capability | Authorisation query |

Assistant must NOT:
- construct `PatternRuntime` internally
- own `CapabilityDeployment`
- contain execution metadata
- execute capabilities directly

### Correct Flow

```
Assistant → CapabilityExecutionPort.execute(capability_id, context, actor_context)
         → [Implementation in Operations]
         → Operations:
            1. Looks up CapabilityDeployment for capability_id
            2. Checks ExecutionAuthorisationPort
            3. Invokes PatternRuntime.invoke_step() or execute_capability()
         → Returns ExecutionResult through port
         → Assistant presents result
```

The `workflow_runner/api.py` endpoint `/assistant/capability/{capability_id}/execute` already calls `service.execute_selected_capability()`. This is the right seam. The implementation of that method should delegate to a port, not call `execute_capability()` directly.

---

## 8. Authority Investigation

### Current State

Authority is not enforced anywhere in the execution path. `AssistantChatService.execute_selected_capability()` executes any capability without checking who is authorised.

### Authority Model

The architecture distinguishes:

| Concept | Definition | Owner |
|---|---|---|
| **Capability** | What can be done | People/Capability |
| **Person/Agent** | Who can do it | People/Capability |
| **CapabilityAssignment** | Who is assigned to use a capability | People/Capability |
| **CapabilityProficiency** | How well someone can use a capability | People/Capability |
| **Role** | What position requires what capabilities | Organisation/Control |
| **Authority** | Permission grant within scope | Organisation/Control |
| **ExecutionAuthorisationPort** | Query: is this actor authorised? | People/Capability |

### Assistant's Authority Relationship

> **Assistant has no authority of its own.**
>
> Assistant acts on behalf of a Person (the user). The user's authority comes from:
> 1. Their Person record (People/Capability)
> 2. Their Role assignments (Organisation/Control)
> 3. Delegated authority chains (Organisation/Control)

Assistant should:
1. Receive `actor_id` and `role_id` from the user context
2. Pass this context through all ports
3. Let each plane enforce its own authority boundary

Assistant should NOT:
1. Decide whether an action is authorised
2. Bypass authority checks
3. Assume authority based on capability possession

### "Assistant is capable of X" vs "Assistant is authorised to do X on behalf of Y"

These are distinct:
- **Capability**: Does the system have the ability to perform X? (People/Capability)
- **Authority**: Is the current actor permitted to perform X? (People/Capability + Organisation/Control)
- **Proficiency**: Can the current actor perform X well? (People/Capability)

Assistant should never conflate these. It should merely forward the actor context and let the responsible plane answer.

---

## 9. Work Creation Investigation

### Current State

Assistant does NOT create Work. It creates sessions directly via `create_session_from_decision()`. This bypasses the organisational Work model entirely.

### Should Assistant Create Work?

**Yes, but through Organisation/Control.**

When a user request implies effort that needs to be tracked, assigned, and accounted for, Assistant should:

1. Translate the request into a Work description
2. Call `WorkManagementPort.create_work(request)` 
3. Organisation/Control creates the Work, assigns it to the appropriate Role
4. Operations picks up the Work via `mark_work_ready()`

### Conditions for Work Creation

Assistant should create Work when:
- The request implies bounded effort with a deliverable
- The request requires organisational accountability
- The request involves multiple steps or roles

Assistant should NOT create Work when:
- The request is a simple informational question
- The request is a direct capability execution with no organisational tracking needed
- The request is a routine operational task with no new accountability

### Authority for Work Creation

Work creation requires organisational authority. Assistant should:
1. Include the actor's `role_id` in the request
2. Let Organisation/Control determine whether that role is authorised to create the Work
3. Not assume creation authority

### Who Becomes Accountable?

Organisation/Control assigns `accountable_role_id` based on:
- The role that initiated the request
- The type of Work (BAU vs project)
- Escalation/approval rules

Assistant does not decide accountability.

---

## 10. EIMS / Learning Investigation

### Current State

`AssistantChatService` reads and writes `ConceptStore` directly:
- `_find_previous_solution()` reads `ConceptStore.list_by_tag()`
- `_record_solution()` writes `EnterpriseConcept` to `ConceptStore`

### Correct Boundary

| Data Type | Owner | Storage |
|---|---|---|
| Conversation memory | Application/Operations | Transient (session state) |
| Session state | Operations | Transient |
| User preferences | Enterprise | Durable (EIMS) |
| Capability outcomes | Enterprise | Durable (EIMS) |
| Organisational learning | Enterprise | Durable (EIMS) |
| Durable enterprise knowledge | Enterprise | Durable (EIMS) |

### What Assistant Should Do

Assistant should:
1. Request previous solutions through an `EnterpriseInformationPort`
2. Request solution recording through the same port
3. Never access `ConceptStore` directly

### What Should NOT Expand

- No `EnterpriseInformation` abstraction implementation (deferred per ADR-030)
- No ConceptStore relocation
- No EIMS expansion

The port can be a thin wrapper around `ConceptStore` for now, with the implementation detail hidden behind the interface.

---

## 11. The Failing Test — Deep Analysis

### Test: `test_chat_service_returns_previous_solution`

```python
def test_chat_service_returns_previous_solution(tmp_path: Path) -> None:
    store = ConceptStore(data_dir=str(tmp_path))
    reg = CapabilityRegistry(ConceptStoreCapabilityRepository(store))

    concept = EnterpriseConcept(
        id="sol-previous",
        kind=ConceptKind.CAPABILITY,
        name="previous-solution",
        description="A previous solution",
        tags=["solution", "strategy:deliberate_to_consensus"],
        payload={
            "summary": "Designed a task tracker with 3 interfaces",
            "strategy": "deliberate_to_consensus",
            "pattern_pipeline": ["debate@1.0.0", "consensus@1.0.0"],
            "maturation_history": {"invocation_count": 2, "correction_count": 0},
        },
    )
    store.upsert(concept)

    service = AssistantChatService(concept_store=store, capability_registry=reg)
    request = ChatRequest(message="Design a new task tracking service")
    response = service.chat(request)

    assert response.status == "awaiting_confirmation"
```

### Why It Fails

The test expects `awaiting_confirmation` but receives `awaiting_capability_selection`. The trace:

1. `chat()` creates `Intent` from message
2. `recognise(intent)` classifies as `DESIGN / DECIDE` → `DELIBERATE_TO_CONSENSUS`
3. **`_match_capabilities(intent, frame)` is called FIRST**
4. `_match_capabilities()` calls `self._registry.list_all()`
5. `list_all()` returns ALL `EnterpriseConcept` records with `kind=CAPABILITY` from ConceptStore
6. The test's "previous solution" concept has `kind=ConceptKind.CAPABILITY`, so it IS returned
7. `HumanSelectionMatcher.match()` returns all capabilities as candidates
8. Since `candidates is not None`, `_capability_selection_response()` is returned
9. Status = `awaiting_capability_selection`
10. `_find_previous_solution()` is **never called**

### What the Test Exposes

1. **Flow order defect**: Capability matching short-circuits previous solution lookup. The test expects previous solutions to be checked before capability matching, but the code does the opposite.

2. **Concept kind pollution**: "Previous solutions" are stored as `ConceptKind.CAPABILITY` alongside actual capabilities. This conflates two distinct concepts:
   - Capability: a reusable ability (tool, skill)
   - Solved approach: a previous solution to a problem
   
   These should be different `ConceptKind` values.

3. **Architectural defect**: AssistantChatService should not be doing capability matching OR EIMS lookups itself. The test is testing behaviour that belongs to other planes.

### Is the Test Obsolete, Defective, or Correct?

| Classification | Assessment |
|---|---|
| Obsolete | No. The behaviour it tests (reusing previous solutions) is still desired. |
| Defective | Partially. The assertion is correct, but the setup conflates concepts and tests the wrong implementation. |
| Correct boundary indicator | **Yes.** The test correctly identifies that Assistant should find previous solutions. But it incorrectly tests this through capability matching. |

### Conclusion

The test is **correctly identifying a missing Assistant boundary**. The fix is NOT to change the assertion or swap the order of `_match_capabilities` and `_find_previous_solution`. The fix is to:

1. Remove capability matching from AssistantChatService
2. Remove direct EIMS access from AssistantChatService
3. Make Assistant request previous solutions through a port
4. Let the appropriate plane handle capability matching and execution

---

## 12. Architectural Contradictions — Repository-Wide Search

### Contradiction 1: AI Plane Owns Application Orchestration

**Location**: `packages/ai/src/chat.py`
**Contradicts**: ADR-025 (Assistant as Role/interface, not orchestrator), ADR-017 (Three-Plane Architecture), ADR-031 (no God services)
**Severity**: Critical

### Contradiction 2: CEO Still Has EIMS Access

**Location**: `packages/ai/src/ceo.py` imports `ConceptStore`
**Contradicts**: ADR-030 (future EnterpriseInformation abstraction), ADR-031 (CEO should not own EIMS)
**Severity**: Medium (CEO is supposed to be strategic-only, but still reads EIMS directly)

### Contradiction 3: `workflow_runner/api.py` Is a God Service

**Location**: `packages/workflow_runner/api.py`
**Imports from**: `capability_registry`, `concepts`, `bus`, `chat` (AI plane), `langgraph_runtime`
**Contradicts**: Four-plane dependency rules, ADR-017
**Severity**: High

### Contradiction 4: ConceptStore Used Outside EIMS Boundary

**Locations**: `packages/ai/src/chat.py`, `packages/ai/src/ceo.py`, `packages/ai/tests/test_assistant.py`, `packages/ai/tests/test_ceo.py`
**Contradicts**: ADR-021 (ConceptStore as EIMS boundary)
**Severity**: Medium

### Contradiction 5: CapabilityMatcher Used Outside People/Capability

**Locations**: `packages/ai/src/chat.py`, `packages/ai/tests/test_assistant.py`
**Contradicts**: ADR-020 (capability ownership by People/Capability)
**Severity**: High

### Contradiction 6: Execution Outside Operations

**Locations**: `packages/ai/src/chat.py::execute_selected_capability()`
**Contradicts**: ADR-017 (Operations owns execution)
**Severity**: High

### Contradiction 7: Tests Cement Boundary Violations

**Locations**: `packages/ai/tests/test_assistant.py`
**Pattern**: Tests directly construct `CapabilityRegistry(ConceptStore(...))`, `Capability(execution_mode=...)`, etc.
**Contradicts**: All architectural boundary tests
**Severity**: High (tests enforce the wrong architecture)

### Contradiction 8: Architecture Context Lists "Assistant" as Future Role But Implementation Is Current

**Location**: `.kilo/context/architecture.md` lines 180, 404-408
**Contradicts**: The current `chat.py` implementation
**Severity**: Medium (documentation vs reality mismatch)

---

## 13. Smallest Defensible Increment 15

### Principle

Do NOT rewrite Assistant. Do NOT implement full capability matching. Do NOT implement CEO/COO/PM. Do NOT create a new orchestration engine.

### Scope: Prove the Correct Boundary

The smallest increment that proves the corrected Assistant boundary is:

#### MUST IMPLEMENT NOW

1. **Define Assistant as application-layer translation service**
   - Document that Assistant is NOT a domain service
   - Document the ports/interfaces Assistant depends on
   - No code changes to production yet — documentation first

2. **Create `AssistantPort` protocol (interface only)**
   - Location: `packages/ai/src/assistant_port.py` (new file)
   - Defines what Assistant provides TO other planes
   - Methods: `chat(request)`, `resume(session_id, response)`
   - This is the OUTBOUND interface from Assistant

3. **Create dependency ports (interfaces only)**
   - `CapabilityDiscoveryPort` — what Assistant needs from People/Capability
   - `CapabilityExecutionPort` — what Assistant needs from Operations
   - `EnterpriseInformationPort` — what Assistant needs from EIMS
   - `OrganisationalContextPort` — what Assistant needs from Organisation/Control
   - `SessionFactoryPort` — what Assistant needs from Operations
   - All locations: `packages/ai/src/ports/` (new directory)
   - All are Protocol/ABC definitions with NO implementations

4. **Create `InMemoryAssistantPorts` (test fixtures only)**
   - In-memory implementations of all ports for testing
   - Demonstrates how the ports would be consumed
   - NO production wiring

5. **Add architectural guardrail tests**
   - Test that `AssistantChatService` does not import from forbidden modules
   - Test that `ai` package does not cross plane boundaries
   - Test that ports are the ONLY dependency path

#### DEFER

| Item | Reason |
|---|---|
| Capability matching implementation | Increment 14 explicitly deferred |
| PatternRuntime authorisation enforcement | Increment 14 explicitly deferred |
| CEO/COO/PM implementation | Explicitly out of scope |
| Paperclip integration | Explicitly out of scope |
| ConceptStore relocation | Explicitly out of scope |
| EnterpriseInformation abstraction | ADR-030 deferred |
| Work creation by Assistant | Requires Organisation/Control role implementation first |
| Full routing logic | ADR-025 says Assistant must NOT implement universal routing |
| Fixing the failing test mechanically | We are fixing the architecture, not the assertion |

---

## 14. Proposed ADRs

### ADR-044: Assistant as Application-Layer Translation Service

**Status**: Proposed

**Decision**:

Assistant is an application-layer translation service, not a domain service. It translates natural language user intent into structured requests for domain planes (Organisation/Control, People/Capability, Operations, Enterprise). It does NOT own capability matching, EIMS access, session creation, runtime invocation, or execution.

**Context**:

ADR-025 correctly identified that Assistant should not be an orchestrator or implicit CEO. However, the current implementation of `AssistantChatService` is exactly that: a God service that crosses all four plane boundaries. The AI plane was intended to own intent recognition and strategy selection only. Application-layer translation belongs to a thin interface, not to a domain service.

**Decision**:

1. `AssistantChatService` is an application-layer service, not a domain service in any plane.
2. Assistant depends on ports/interfaces, not concrete implementations from other planes.
3. Assistant does NOT import from `capability_registry`, `concepts`, `workflow_runner.src.executor`, `workflow_runner.src.runtime`, `workflow_runner.src.session`, `bus`, or `pathway_runtime`.
4. Capability matching, EIMS access, session creation, and execution are delegated through ports.
5. The `ai` package owns only: intent recognition, strategy selection, reasoning, and the Assistant port interface.

**Consequences**:

- `AssistantChatService` must be refactored to depend on ports, not concrete implementations.
- Tests must be updated to use port implementations, not direct imports.
- The failing test `test_chat_service_returns_previous_solution` is resolved by removing capability matching from Assistant, not by changing the assertion.

---

### ADR-045: Assistant Port Interfaces

**Status**: Proposed

**Decision**:

Define explicit port interfaces between Assistant and each domain plane. Assistant depends on these ports; implementations live in the respective planes.

**Context**:

The current `AssistantChatService` has hard dependencies on concrete classes from four planes. This makes it impossible to test, impossible to swap implementations, and impossible to enforce architectural boundaries.

**Decision**:

Define the following ports in `packages/ai/src/ports/`:

1. `CapabilityDiscoveryPort` — query capabilities (People/Capability)
2. `CapabilityExecutionPort` — execute capabilities (Operations)
3. `EnterpriseInformationPort` — read/write enterprise knowledge (Enterprise/EIMS)
4. `OrganisationalContextPort` — get organisational context (Organisation/Control)
5. `WorkManagementPort` — create and manage Work (Organisation/Control)
6. `SessionFactoryPort` — create sessions (Operations)

Each port is a `Protocol` defining the minimal interface Assistant needs. Implementations live in the respective planes.

**Consequences**:

- Assistant has zero direct imports from other planes' `src/` directories.
- All cross-plane communication goes through ports.
- Test fixtures can provide in-memory port implementations.
- The architecture becomes enforceable via import checks.

---

## 15. Implementation Plan Path

### Files to Create

| File | Purpose |
|---|---|
| `packages/ai/src/ports/__init__.py` | Port package init |
| `packages/ai/src/ports/capability_discovery.py` | `CapabilityDiscoveryPort` protocol |
| `packages/ai/src/ports/capability_execution.py` | `CapabilityExecutionPort` protocol |
| `packages/ai/src/ports/enterprise_information.py` | `EnterpriseInformationPort` protocol |
| `packages/ai/src/ports/organisational_context.py` | `OrganisationalContextPort` protocol |
| `packages/ai/src/ports/work_management.py` | `WorkManagementPort` protocol |
| `packages/ai/src/ports/session_factory.py` | `SessionFactoryPort` protocol |
| `packages/ai/src/assistant_port.py` | `AssistantPort` protocol (what Assistant provides) |
| `packages/ai/tests/fixtures/in_memory_ports.py` | Test implementations of all ports |
| `packages/ai/tests/test_architectural_boundaries.py` | Guardrail tests for AI plane imports |

### Files to Modify

| File | Changes |
|---|---|
| `packages/ai/src/chat.py` | Replace direct imports with port dependencies; inject ports via constructor |
| `packages/ai/tests/test_assistant.py` | Update to use port fixtures instead of direct ConceptStore/CapabilityRegistry |
| `packages/ai/tests/test_ceo.py` | Update CEO tests similarly |
| `packages/workflow_runner/api.py` | Already calls `AssistantChatService` through interface; verify it works with port-based service |
| `.kilo/context/architecture.md` | Update Assistant section, add port definitions |

### Dependency Direction (After Increment 15)

```
Application Layer
├── Assistant (ai package)
│   ├── depends on: AssistantPort (outbound)
│   ├── depends on: CapabilityDiscoveryPort (inbound)
│   ├── depends on: CapabilityExecutionPort (inbound)
│   ├── depends on: EnterpriseInformationPort (inbound)
│   ├── depends on: OrganisationalContextPort (inbound)
│   ├── depends on: WorkManagementPort (inbound)
│   └── depends on: SessionFactoryPort (inbound)
│
├── Organisation/Control (implements OrganisationalContextPort, WorkManagementPort)
├── People/Capability (implements CapabilityDiscoveryPort, CapabilityExecutionPort.authorisation)
├── Operations (implements CapabilityExecutionPort, SessionFactoryPort)
└── Enterprise/EIMS (implements EnterpriseInformationPort)
```

### Tests Required

1. **Architectural guardrail**: `test_assistant_has_no_forbidden_imports` — verify `chat.py` does not import from forbidden modules
2. **Port contract**: `test_capability_discovery_port_interface` — verify the port protocol
3. **Port contract**: `test_capability_execution_port_interface` — verify the port protocol
4. **Port contract**: `test_enterprise_information_port_interface` — verify the port protocol
5. **Boundary**: `test_ai_plane_does_not_cross_plane_boundaries` — scan all `ai/src/*.py` for forbidden imports
6. **Behaviour**: `test_chat_with_previous_solution_via_port` — rewrite failing test using `EnterpriseInformationPort`
7. **Behaviour**: `test_chat_capability_selection_via_port` — rewrite capability matching test using `CapabilityDiscoveryPort`

### Validation Commands

```bash
# Tests
pytest packages/ai/tests/ -q

# Lint
ruff check packages/ai/src/ packages/ai/tests/

# Full validation (existing tests must still pass)
pytest packages/organisation/tests/ packages/ai/tests/test_ceo.py packages/capability_registry/tests/ packages/people_capability/tests/ packages/workflow_runner/tests/ -q
```

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing tests break | High | Medium | Update tests to use port fixtures |
| Port interface too narrow/wrong | Medium | Medium | Start minimal; expand in later increments |
| Resistance to "another layer of abstraction" | Medium | Low | Ports are interfaces only, not implementations |
| Workflow runner API needs changes | Low | Medium | API already uses `AssistantChatService` interface; verify compatibility |
| Scope creep to full rewrite | Medium | High | Explicitly defer: no capability matching, no Work creation, no CEO changes |

---

## 16. Deferred Work

- Capability matching implementation (Increment 14 deferred)
- PatternRuntime authorisation enforcement (Increment 14 deferred)
- CEO/COO/PM implementation (explicitly out of scope)
- Paperclip integration (explicitly out of scope)
- ConceptStore relocation (explicitly out of scope)
- EnterpriseInformation abstraction (ADR-030 deferred)
- Work creation by Assistant (requires Organisation/Control role implementation)
- Full routing logic (ADR-025: Assistant must NOT implement universal routing)
- Assistant as organisational Role (future — requires Role model expansion)
- Fixing the failing test mechanically (we fix the architecture, not the assertion)

---

## 17. Conclusion

The AssistantChatService bypass is not a single missing check or wrong import. It is the fundamental misplacement of an application-layer orchestrator inside the AI domain package, where it has become a God service crossing all four plane boundaries.

The correct architecture is:

> **Assistant is an application-layer translation service.**
>
> It owns natural language intake, AI reasoning (intent/strategy), and translation of recognised intent into structured requests. It does NOT own capability matching, EIMS access, session creation, runtime invocation, or execution.
>
> Assistant depends on ports/interfaces to other planes. It has zero direct imports from `capability_registry`, `concepts`, `workflow_runner.src.executor`, `workflow_runner.src.runtime`, `workflow_runner.src.session`, `bus`, or `pathway_runtime`.

The smallest defensible Increment 15 proves this boundary by:
1. Documenting the corrected identity
2. Creating port interfaces (no implementations)
3. Adding architectural guardrail tests
4. Updating the architecture context

This is an INVESTIGATION ONLY. No production code changes are made in this increment.
