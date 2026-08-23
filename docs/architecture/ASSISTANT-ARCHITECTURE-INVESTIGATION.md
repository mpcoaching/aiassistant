# Assistant Architecture Investigation

**Date:** 2026-08-23  
**Purpose:** Establish the correct architectural boundary for the Assistant before Increment 21  
**Scope:** Read-only investigation. No code changes.

---

## Core Question

> "What should the Assistant actually be in this architecture?"

---

## 1. Complete Execution Path: User Message → Response

### Current Actual Flow

```
User message (HTTP POST /assistant/chat)
    │
    ▼
AssistantChatService.chat()                         [packages/ai/src/chat.py:88]
    │
    ├─► Intent creation                               [packages/ai/src/chat.py:90-95]
    │   └─► Intent(id, origin=USER_REQUEST, raw={text})
    │
    ├─► recognise(intent)                             [packages/ai/src/intent.py:70]
    │   └─► ProblemFrame(problem_context, activity_purpose, confidence)
    │       └─► Rule-based keyword matching (v1 seed)
    │
    ├─► _strategy_from_frame(frame)                   [packages/ai/src/chat.py:223-239]
    │   └─► Static mapping table: (problem, activity) → strategy tag
    │
    ├─► IF enterprise_information is configured:
    │   ├─► find_previous_solutions(strategy_tag)     [packages/ai/src/chat.py:99-110]
    │   │   └─► Returns PreviousSolution OR None
    │   └─► IF previous found → RETURN awaiting_confirmation
    │
    ├─► IF capability_discovery is configured:
    │   ├─► find_capabilities(request_text, context)  [packages/ai/src/chat.py:112-120]
    │   │   ├─► CapabilityDiscoveryAdapter.find_capabilities()
    │   │   │   ├─► registry.list() → ALL capabilities
    │   │   │   ├─► matcher.match(request_text, ctx, capabilities)
    │   │   │   │   └─► HumanSelectionMatcher → returns ALL capabilities (stub)
    │   │   │   └─► Returns CapabilityCandidate list
    │   │   │
    │   │   ├─► IF len(candidates) == 1:
    │   │   │   └─► _execute_capability_response()     [packages/ai/src/chat.py:241-296]
    │   │   │       ├─► execute_selected_capability()
    │   │   │       │   └─► CapabilityExecutionPort.execute()
    │   │   │       │       └─► CapabilityExecutionAdapter.execute()
    │   │   │       │           ├─► registry.get(capability_id)
    │   │   │       │           ├─► authorisation check
    │   │   │       │           ├─► deployment_factory(capability)
    │   │   │       │           └─► execute_capability()  [workflow_runner/src/executor.py:28]
    │   │   │       │               └─► Compiled module invocation
    │   │   │       │
    │   │   │       ├─► InvocationRecorderAdapter.record_invocation()
    │   │   │       │   └─► ConceptStore.record_invocation() (maturation_history)
    │   │   │       │
    │   │   │       └─► RETURN ChatResponse(status="completed", execution_outputs)
    │   │   │
    │   │   └─► ELSE (multiple candidates):
    │   │       └─► _capability_selection_response()   [packages/ai/src/chat.py:298-329]
    │   │           └─► RETURN awaiting_capability_selection with ALL candidates
    │   │
    ├─► IF NO candidates found:
    │   ├─► reasoning_service.decide(intent)            [packages/ai/src/assistant.py:28]
    │   │   ├─► recognise(intent) → ProblemFrame
    │   │   ├─► select_strategy(frame.context)          [packages/ai/src/strategy.py:50]
    │   │   │   └─► Static table lookup → StrategyProposal
    │   │   └─► StrategyDecision(chosen_strategy, pattern_pipeline, participant_roles)
    │   │
    │   ├─► IF session_factory is configured:
    │   │   └─► create_session(strategy, pipeline, ctx) [packages/ai/src/chat.py:124-131]
    │   │       └─► SessionFactoryAdapter.create_session()
    │   │           └─► create_session_from_decision()   [workflow_runner/src/session.py:50]
    │   │               └─► Session(id, pipeline, status=PENDING)
    │   │
    │   ├─► IF session + pattern_execution configured:
    │   │   └─► execute_pattern(pattern_request)        [packages/ai/src/chat.py:133-152]
    │   │       ├─► PatternExecutionAdapter.execute_pattern()
    │   │       │   ├─► PathwayCallRequest(...)
    │   │       │   └─► PathwayRuntime.invoke()
    │   │       │       └─► LangGraphRuntime.invoke()   [packages/langgraph/src/langgraph_runtime.py:60]
    │   │       │           └─► Builds StateGraph, executes nodes (stub)
    │   │       │
    │   │       └─► PatternExecutionResult(status, outputs)
    │   │
    │   └─► RETURN ChatResponse(status="completed" or "pending")
    │
    └─► (fallback) RETURN generic response
```

### Where the Flow Stops Being Useful

| Stop Point | Status | Why |
|------------|--------|-----|
| `awaiting_capability_selection` | Hard stop | User must manually pick; no execution follow-up in chat |
| Pattern execution | Superficial | LangGraph nodes just record step status, no real invocation |
| No candidates | Falls through | Generic "I'll help with that" response |

---

## 2. Responsibility Map

### Where Responsibilities Currently Live

| Responsibility | Current Location | Evidence |
|----------------|-----------------|----------|
| **Natural language intake** | `chat.py` (AI plane) | `ChatRequest` model, `chat()` entrypoint |
| **Intent recognition** | `intent.py` (AI plane) | `recognise()` function, keyword rules |
| **Strategy selection** | `strategy.py` (AI plane) | `select_strategy()`, static table |
| **Reasoning assembly** | `assistant.py` (AI plane) | `AssistantReasoningService.decide()` |
| **Previous solution lookup** | `chat.py` → port → adapter | `EnterpriseInformationPort.find_previous_solutions()` |
| **Capability discovery** | `chat.py` → port → adapter | `CapabilityDiscoveryPort.find_capabilities()` |
| **Capability matching** | `capability_registry` (People/Capability) | `CapabilityMatcher` protocol, `HumanSelectionMatcher` |
| **Capability selection logic** | `chat.py` (AI plane) | `if len(candidates) == 1` / else branches |
| **Capability execution** | `chat.py` → port → adapter → executor | `CapabilityExecutionPort.execute()` → `execute_capability()` |
| **Session creation** | `chat.py` → port → adapter | `SessionFactoryPort.create_session()` |
| **Pattern execution** | `chat.py` → port → adapter → runtime | `PatternExecutionPort.execute_pattern()` → `LangGraphRuntime` |
| **Authorisation** | `capability_execution_adapter` (Operations) | `_check_authorisation()` in adapter |
| **Invocation telemetry** | `invocation_recorder_adapter` (Operations) | `record_invocation()` → `ConceptStore.record_invocation()` |
| **Outcome assessment** | `capability_outcome_assessor_adapter` (Operations) | `CapabilityOutcomeAssessorAdapter` |
| **Response formatting** | `chat.py` (AI plane) | `ChatResponse` construction |
| **Human-in-the-loop** | `chat.py` (AI plane) + `human_loop.py` (Operations) | `resume_with_human_input()`, `HumanInTheLoopMixin` |
| **Capability definitions** | `people_capability/src/capability.py` | `Capability` domain model |
| **Capability registry** | `capability_registry/src/capabilities.py` | `CapabilityRegistry` class |
| **Agent records** | `people_capability/src/agent.py` | `Agent` domain model (marker/record only) |
| **Workflow execution** | `workflow_runner/src/runtime.py` | `PatternRuntime.invoke_step()` |
| **Deployment resolution** | `workflow_runner/src/deployment_resolver.py` | `DeploymentResolver` |
| **Enterprise knowledge** | `capability_registry/src/concepts.py` | `ConceptStore`, `EnterpriseConcept` |

---

## 3. The Eight Architectural Categories

### 1. The Assistant as an Architectural Role/Agent

**What the ADRs say:**
- ADR-025: "Assistant is a Role/interface, not an orchestrator."
- ADR-044: "Assistant is an application-layer translation service, not a domain service."
- ADR-031: "CEO does NOT become the universal system router" (by analogy, Assistant should not either).

**What the code shows:**
- `AssistantChatService` is a class in `packages/ai/src/chat.py`.
- `AssistantReasoningService` is a class in `packages/ai/src/assistant.py`.
- There is NO `Agent` subclass for Assistant, NO lifecycle, NO runtime identity.
- The `Agent` model in `people_capability/src/agent.py` is a simple domain record (id, name, marker, status) — not an orchestrator.

**Verdict:** The Assistant is **not** an agent/orchestrator in the architecture. It is explicitly defined as a thin application-layer translation service. However, the implementation in `chat.py` contains orchestration logic (procedural routing), which contradicts the intended thin boundary.

### 2. The Application Service That Receives a Chat Request

**Current implementation:** `AssistantChatService` in `packages/ai/src/chat.py`.

**What it does:**
- Receives `ChatRequest`
- Creates `Intent`
- Calls `recognise()` → `select_strategy()` → `decide()`
- Checks previous solutions
- Discovers capabilities
- Executes capabilities or patterns
- Builds `ChatResponse`

**Assessment:** This is an application service, but it has accreted orchestration responsibilities. It is the "God service" that ADR-044 warns about, partially mitigated by Increment 15's port-based injection.

### 3. Domain Services

**Current location:** `packages/ai/src/assistant.py` — `AssistantReasoningService`.

**What it does:**
- `decide(intent)` → `StrategyDecision`
- Combines intent recognition + strategy selection
- Resolves participant roles

**Assessment:** This is the closest thing to a domain service in the AI plane. It is correctly scoped to reasoning only.

### 4. Capability Discovery/Matching

**Current location:**
- Protocol: `packages/capability_registry/src/capability_matcher.py` — `CapabilityMatcher` (Protocol)
- Implementation: `HumanSelectionMatcher` (returns ALL capabilities)
- Adapter: `packages/capability_registry/src/adapters/capability_discovery_adapter.py` — `CapabilityDiscoveryAdapter`
- Port: `packages/contracts/capability_discovery.py` — `CapabilityDiscoveryPort`

**Assessment:** Matching belongs to People/Capability. The `CapabilityDiscoveryAdapter` correctly bridges to the AI plane via port. This boundary is clean.

### 5. Capability Execution

**Current location:**
- Port: `packages/contracts/capability_execution.py` — `CapabilityExecutionPort`
- Adapter: `packages/workflow_runner/src/adapters/capability_execution_adapter.py` — `CapabilityExecutionAdapter`
- Executor: `packages/workflow_runner/src/executor.py` — `execute_capability()`
- Runtime: `packages/workflow_runner/src/runtime.py` — `PatternRuntime.invoke_step()`

**Assessment:** Execution belongs to Operations. The adapter pattern correctly isolates the AI plane from execution details.

### 6. Planning/Reasoning

**Current location:**
- `packages/ai/src/intent.py` — `recognise()` (intent classification)
- `packages/ai/src/strategy.py` — `select_strategy()` (strategy selection)
- `packages/ai/src/assistant.py` — `AssistantReasoningService.decide()` (assembly)

**Assessment:** Reasoning is correctly scoped to the AI plane. However, there is NO planner/executor/reviewer decomposition. The reasoning is a single pass: intent → strategy → decision.

### 7. Response Generation

**Current location:** `packages/ai/src/chat.py` — `ChatResponse` construction, message formatting.

**Assessment:** Response generation is currently procedural string interpolation in `chat.py`. There is no LLM integration, no structured response generation, no conversational state.

### 8. Infrastructure/Adapters

**Current locations:**
- `packages/workflow_runner/src/adapters/` — 5 adapters (capability execution, pattern execution, session factory, invocation recorder, outcome assessor)
- `packages/capability_registry/src/adapters/` — 3 adapters (capability discovery, concept store, enterprise information)
- `packages/langgraph/src/langgraph_runtime.py` — `PathwayRuntime` implementation

**Assessment:** The adapter layer is well-structured. Ports are defined in `packages/contracts/`. Implementations are injected via composition root (`workflow_runner/src/composition.py`).

---

## 4. Existing Agent Abstractions

### What Exists

| Component | Location | Nature | Intended Role |
|-----------|----------|--------|---------------|
| `Agent` | `people_capability/src/agent.py` | Domain record | Software entity marker with identity, fulfilled roles |
| `CEOAgent` | `ai/src/ceo.py` | Application service | Lightweight strategic orchestrator |
| `AssistantReasoningService` | `ai/src/assistant.py` | Domain service | Intent → Strategy reasoning |
| `PathwayRuntime` | `bus/src/pathway_runtime.py` | Interface | Execution substrate abstraction |
| `LangGraphRuntime` | `langgraph/src/langgraph_runtime.py` | Implementation | LangGraph-based pattern execution |
| `PatternRuntime` | `workflow_runner/src/runtime.py` | Service | Capability step invocation |
| `Session` | `workflow_runner/src/session.py` | Model | Bounded pattern execution |

### What Does NOT Exist

| Component | Status | Gap |
|-----------|--------|-----|
| **Planner** | Not implemented | No decomposition of intent into executable steps |
| **Executor** | Partially implemented | `execute_capability()` exists but is not agent-like |
| **Reviewer** | Not implemented | No outcome review before responding |
| **Reasoning loop** | Not implemented | Single-pass: intent → strategy → execute |
| **Conversational agent** | Not implemented | No stateful dialogue, no context carry-over |
| **Assistant agent** | Not implemented | No `Agent` subclass, no lifecycle, no runtime identity |

### Key Finding

The architecture contains the **beginnings** of agent abstractions:
- `Agent` domain model (People/Capability)
- `PathwayRuntime` interface (Operations)
- `CEOAgent` as a role-specific service (AI plane)

But there is **no unified agent abstraction** that ties these together. Each component is independently implemented. The architecture does not have a `Planner` → `Executor` → `Reviewer` pipeline.

---

## 5. ADR Definitions of Key Terms

| Term | ADR Source | Definition |
|------|-----------|------------|
| **Assistant** | ADR-025, ADR-044 | Application-layer translation service. NOT an orchestrator, NOT a domain service. Depends on ports only. |
| **AI plane** | ADR-017 | Owns intent recognition, strategy selection, reasoning. Does NOT execute work or own capabilities. |
| **agent** | ADR-018 | Software entity that performs work. Owned by People/Capability (records) and Operations (execution). Has runtime identity. |
| **capability** | ADR-020, ADR-035 | Reusable ability (tool, skill) owned by People/Capability. Unit of invocation. |
| **workflow** | ADR-039, Enterprise Cognition §1a | Transient execution of a pattern pipeline. Owned by Operations. |
| **planner** | Not explicitly defined | Not implemented. Implied by "Plan / design" in Enterprise Cognition §10a. |
| **executor** | Not explicitly defined | `execute_capability()` in Operations. Not agent-like. |
| **reviewer** | Not explicitly defined | Not implemented. |
| **intent** | ADR-044, intent.py | Origin-agnostic stimulus (user request, event, alert). Classified into ProblemFrame. |
| **orchestration** | ADR-031, ADR-036 | Distributed according to responsibility. CEO is strategic-only. No universal orchestrator. |
| **ports/adapters** | ADR-045, ADR-010 | Stable interfaces between planes. Implementations injected via DI. |

---

## 6. Contradictions: Intended vs Current Architecture

### Contradiction 1: Assistant Identity

**Intended (ADR-044, ADR-025):** Assistant is a thin application-layer translation service.
**Current (`chat.py`):** Procedural orchestrator with if/elif/else routing for previous solutions, capability discovery, capability execution, and pattern execution.

**Evidence:**
```python
# chat.py:88-188 — procedural router
def chat(self, request: ChatRequest) -> ChatResponse:
    intent = Intent(...)
    frame = recognise(intent)
    
    if self._enterprise_information is not None:
        previous = self._enterprise_information.find_previous_solutions(...)
        if previous is not None:
            return ChatResponse(status="awaiting_confirmation", ...)  # ← branch 1
    
    if self._capability_discovery is not None:
        candidates = self._capability_discovery.find_capabilities(...)
        if candidates:
            if len(candidates) == 1:
                return self._execute_capability_response(...)  # ← branch 2
            return self._capability_selection_response(...)   # ← branch 3
    
    decision = self._reasoning.decide(intent)  # ← branch 4
    # ... session creation, pattern execution
```

### Contradiction 2: CEO vs Assistant Boundary

**Intended (ADR-031):** CEO is strategic-only. Does not orchestrate day-to-day work.
**Current:** `CEOAgent` in `ceo.py` also contains procedural routing (escalate, reuse, delegate). It is a second orchestrator alongside `AssistantChatService`.

**Evidence:** Both `chat.py` and `ceo.py` implement similar if/elif/else patterns for the same concerns (previous solutions, capability execution, escalation).

### Contradiction 3: Conversation State

**Intended (ARCHITECTURE-ASSESSMENT):** "Conversation state/memory" is explicitly deferred.
**Current:** `chat.py` is stateless between calls. `_sessions` dict exists but is not used for conversation context carry-over.

### Contradiction 4: Capability Matching Ownership

**Intended (ADR-020):** Capability matching belongs to People/Capability.
**Current:** `chat.py` makes the execution decision based on `len(candidates)`. The decision logic (auto-execute vs ask user) lives in the AI plane, not in People/Capability.

### Contradiction 5: Evidence Collection vs Use

**Intended (ADR-029):** Execution evidence feeds back into capability quality.
**Current:** Increments 18/19 collect evidence (invocation_count, correction_count) but Increment 20/21 do NOT use it for matching decisions. `HumanSelectionMatcher` ignores all evidence.

---

## 7. Procedural Router vs Agent Analysis

### Current: Procedural Router

```python
# chat.py is exactly this:
if previous_solution:
    return reuse_response
elif len(candidates) == 1:
    return execute_response
elif len(candidates) > 1:
    return selection_response
else:
    return pattern_execution_response
```

This is a **procedural router** — a sequence of conditional branches that decide what to do next based on immediate conditions.

### Intended: Agent with Reasoning Loop

```
understand → determine what is needed → discover capabilities → reason/select → execute → inspect outcome → decide next action → respond
```

**The architecture does NOT currently have this.** There is:
- No reasoning loop
- No outcome inspection before responding
- No "decide next action" — the response is final
- No learning from the current interaction

### Why the Disconnect?

The architecture documents (Enterprise Cognition Reference Architecture) describe a sophisticated reasoning loop. But the implementation is incrementally built:
- Increment 2: intent recognition (understand)
- Increment 4: strategy selection (determine what is needed)
- Increment 14: capability discovery (discover)
- Increment 15: port-based boundary (corrected but still procedural)
- Increment 20: execution path (execute)
- Increment 21 (proposed): matching (reason/select)

The reasoning loop is being assembled piece by piece, but each piece is a procedural branch in `chat.py`.

---

## 8. Explicit Answers to Questions

### 1. Is the current `AssistantChatService` actually an Assistant/agent, or is it an application-layer entry point?

**It is an application-layer entry point that has accreted orchestration responsibilities.** It is NOT an agent — it has no `Agent` record, no lifecycle, no runtime identity, no reasoning loop. But it is NOT thin either — it contains procedural routing logic for four distinct execution paths.

### 2. Where should the Assistant's reasoning/orchestration live?

**The architecture is ambiguous on this point.**

- ADR-044 says Assistant should be a thin translation service.
- But the Enterprise Cognition Reference Architecture (§10a) describes a "Plan / design" step that produces capability contracts — this is reasoning beyond simple intent recognition.
- The current implementation puts ALL reasoning in `AssistantReasoningService.decide()` (intent → strategy), but execution orchestration remains in `chat.py`.

**Recommended:** Reasoning should live in `AssistantReasoningService` (or a future `AssistantAgent` if the architecture evolves). Orchestration of execution should NOT live in the AI plane — it should be delegated to Operations via ports.

### 3. Should `chat.py` remain a thin application service?

**Yes, but it is currently NOT thin.** Increment 15 corrected the dependency direction (ports instead of direct imports), but the orchestration logic remains in `chat.py`. The method should be reduced to:
1. Create Intent
2. Call reasoning service
3. Delegate to appropriate port
4. Format response

### 4. Is there already an agent abstraction that we should be using?

**No unified agent abstraction exists.** There are separate pieces:
- `Agent` domain record (People/Capability)
- `PathwayRuntime` interface (Operations)
- `CEOAgent` service (AI plane)
- `AssistantReasoningService` (AI plane)

None of these form a coherent agent abstraction that the Assistant could use.

### 5. If there isn't one, what is the smallest architectural increment needed to introduce one?

**Do NOT introduce a new agent abstraction.** The architecture explicitly rejects a universal orchestrator pattern (ADR-031, ADR-036). Instead:

**Smallest increment:** Extract the procedural router in `chat.py` into a **`CapabilityExecutionFlow`** service that encapsulates the decision logic:
- Auto-execute if single high-confidence candidate
- Ask user if multiple candidates
- Fall through to pattern execution if no candidates

This is NOT a new agent — it is a domain service in the AI plane that encapsulates the execution decision flow.

### 6. What responsibilities should NOT belong to the Assistant?

| Responsibility | Current Location | Should Belong To |
|----------------|-----------------|-----------------|
| Capability matching | `capability_registry` | People/Capability (correct) |
| Capability execution | `chat.py` → `execute_capability()` | Operations (correct via port) |
| Capability selection decision | `chat.py` (len(candidates) check) | Operations or People/Capability |
| Session creation | `chat.py` | Operations (correct via port) |
| Pattern execution | `chat.py` | Operations (correct via port) |
| Previous solution lookup | `chat.py` | Enterprise (correct via port) |
| Solution recording | `chat.py` | Enterprise (correct via port) |
| Authorisation | `capability_execution_adapter` | People/Capability (correct) |
| Strategy selection | `assistant.py` | AI plane (correct) |
| Intent recognition | `intent.py` | AI plane (correct) |

### 7. Does Increment 20 put logic in the wrong place?

**Partially.** Increment 20 wired capability execution into the chat flow, which is necessary for usefulness. But it added the execution decision logic (`if len(candidates) == 1: execute`) to `chat.py` instead of to a domain service in the AI plane or to Operations.

The execution path itself is correct (via ports). The decision logic should be extracted.

### 8. Does the proposed Increment 21 still make sense after correcting the Assistant architecture?

**Yes, with modification.** Increment 21's core idea — replacing `HumanSelectionMatcher` with `RelevanceMatcher` — is architecturally correct because:
- Matching stays in People/Capability
- The `CapabilityMatcher` protocol is stable
- Evidence-based ranking closes the learning loop

However, Increment 21 as proposed puts the **confidence-based execution decision** in `chat.py`:
```python
if top.confidence >= 0.8:
    execute(top)
elif top.confidence >= 0.5:
    present_top_n(ranked, n=3)
```

This decision logic should NOT be in `chat.py`. It should be in a domain service (e.g., `CapabilityExecutionFlow`) or in Operations.

### 9. What should the architecture look like after the next 2–3 increments?

**Target Architecture:**

```
User
    │
    ▼
AssistantChatService (thin application service)
    │
    ├─► Intent → ProblemFrame (intent.py)
    ├─► StrategyDecision (assistant.py / AssistantReasoningService)
    │
    ├─► CapabilityExecutionFlow (NEW — AI plane domain service)
    │   ├─► CapabilityDiscoveryPort.find_capabilities()
    │   ├─► Confidence-based decision (auto-execute / ask / clarify)
    │   └─► CapabilityExecutionPort.execute()
    │
    ├─► PatternExecutionFlow (NEW — AI plane domain service, or keep in chat.py)
    │   ├─► SessionFactoryPort.create_session()
    │   └─► PatternExecutionPort.execute_pattern()
    │
    └─► EnterpriseInformationPort (previous solutions, recording)
```

**After 3 increments:**
1. **Extract `CapabilityExecutionFlow`** from `chat.py` — encapsulates capability discovery + selection + execution decision
2. **Extract `PatternExecutionFlow`** from `chat.py` — encapsulates session creation + pattern execution
3. **`chat.py` becomes** a 20-line method that creates Intent, calls flows, formats response

### 10. What is the smallest coherent next increment from the CURRENT architecture?

**NOT Increment 21 as proposed.** The smallest coherent increment is:

**Increment 21A: Extract CapabilityExecutionFlow**

**Objective:** Move the capability execution decision logic out of `chat.py` into a dedicated domain service, keeping the port-based boundaries intact.

**Scope:**
1. Create `CapabilityExecutionFlow` class in `packages/ai/src/`
2. Move the following FROM `chat.py` TO `CapabilityExecutionFlow`:
   - Capability discovery delegation
   - Single-candidate execution
   - Multi-candidate selection response
   - No-match fallback
3. `chat.py` calls `CapabilityExecutionFlow.execute(request, frame)` instead of inline logic
4. `chat.py` reduces to ~30 lines

**What this does NOT change:**
- No new ports
- No new cross-plane dependencies
- No changes to capability matching algorithm
- No changes to execution path
- `RelevanceMatcher` can still be introduced later as a `CapabilityMatcher` implementation

**Why this before Increment 21:**
- Increment 21 adds a new matcher implementation but leaves the procedural router in `chat.py`
- Extracting the flow FIRST makes Increment 21's confidence logic land in the right place
- It proves the Assistant boundary before adding matching behaviour

---

## 9. Increment 21 Recommendation

**Increment 21 should be MODIFIED.**

The `RelevanceMatcher` implementation is correct and should proceed. But the **confidence-based execution decision** proposed in Increment 21 should NOT go into `chat.py`. It should go into the extracted `CapabilityExecutionFlow` service.

**Modified Increment 21:**
1. **Part A (Required first):** Extract `CapabilityExecutionFlow` from `chat.py`
2. **Part B (Then):** Implement `RelevanceMatcher` in `capability_registry`
3. **Part C (Then):** Move confidence-based execution decisions to `CapabilityExecutionFlow`

This ensures that:
- The Assistant boundary is corrected BEFORE adding more behaviour
- Matching logic stays in People/Capability
- Execution decision logic lives in an AI-plane domain service, not in the application service
- Increment 21's value (evidence-based matching) is preserved

---

## 10. Summary Sections

### A. Current Architecture

```
User → AssistantChatService (God service / procedural router)
    ├─► Intent recognition (AI plane — correct)
    ├─► Strategy selection (AI plane — correct)
    ├─► Previous solution lookup (Enterprise — via port)
    ├─► Capability discovery (People/Capability — via port)
    ├─► Capability matching (People/Capability — via port)
    ├─► Capability selection decision (AI plane — WRONG: should be Operations or domain service)
    ├─► Capability execution (Operations — via port)
    ├─► Session creation (Operations — via port)
    ├─► Pattern execution (Operations — via port)
    └─► Response formatting (AI plane — correct)
```

**Characteristics:**
- Ports are correctly defined and injected (Increment 15)
- But orchestration logic remains in `chat.py` as procedural branches
- No agent abstraction exists
- No reasoning loop exists
- `chat.py` is 330 lines and growing

### B. Intended Architecture (from ADRs/documentation)

```
User → Assistant (application-layer translation service)
    │
    ├─► Intent recognition (AI plane)
    ├─► Strategy selection (AI plane)
    │
    ├─► CapabilityExecutionFlow (AI plane domain service)
    │   ├─► CapabilityDiscoveryPort → People/Capability matches
    │   ├─► Confidence-based decision
    │   └─► CapabilityExecutionPort → Operations executes
    │
    ├─► PatternExecutionFlow (AI plane domain service)
    │   ├─► SessionFactoryPort → Operations creates session
    │   └─► PatternExecutionPort → Operations executes pattern
    │
    └─► EnterpriseInformationPort → Enterprise reads/writes knowledge
```

**Characteristics:**
- `chat.py` is thin (~30 lines)
- Reasoning lives in `AssistantReasoningService`
- Execution decisions live in domain services
- No cross-plane imports from AI plane
- Assistant does NOT orchestrate — it translates and delegates

### C. Architectural Gaps/Contradictions

| Gap/Contradiction | Severity | Evidence |
|-------------------|----------|----------|
| `chat.py` is a procedural router, not a translation service | High | 330-line method with 4 execution branches |
| No agent abstraction for Assistant | Medium | No `Agent` subclass, no lifecycle, no reasoning loop |
| Execution decision logic in AI plane | Medium | `if len(candidates) == 1` in `chat.py` |
| No `CapabilityExecutionFlow` domain service | Medium | Logic scattered in `chat.py` |
| `CEOAgent` duplicates Assistant routing | Low | Both `chat.py` and `ceo.py` have similar procedural logic |
| Evidence collected but not used for matching | Low | Increments 18/19 collect data; Increment 21 would use it |
| No conversational state | Low | Explicitly deferred |
| No LLM integration | Low | Explicitly deferred |

### D. Recommended Target Boundary for the Assistant

**The Assistant should be:**
- An **application-layer translation service** (per ADR-044)
- NOT an agent/orchestrator
- NOT a domain service
- Thin: ~30 lines in `chat.py`
- Depends ONLY on ports and AI-plane reasoning services

**The Assistant should NOT:**
- Contain procedural routing logic
- Make capability selection decisions
- Create sessions directly
- Invoke runtimes directly
- Access enterprise knowledge directly

**The boundary:**
```
Assistant (AI plane)
    ├─► OWNS: intent recognition, strategy selection, response formatting
    ├─► DELEGATES: capability execution, pattern execution, knowledge access
    └─► DOES NOT OWN: matching, execution decisions, session management, runtime invocation
```

### E. Smallest Next Increment

**Increment 21A: Extract CapabilityExecutionFlow**

**Scope:**
1. Create `packages/ai/src/capability_execution_flow.py`
2. Move from `chat.py`:
   - Capability discovery call
   - Single-candidate execution path
   - Multi-candidate selection response
   - No-match fallback
3. `chat.py` calls `CapabilityExecutionFlow.execute(request, frame)`
4. No new ports, no new dependencies, no behaviour change

**Why this increment:**
- Proves the Assistant boundary BEFORE adding more behaviour
- Makes Increment 21's confidence logic land in the right place
- Reduces `chat.py` from 330 to ~30 lines
- No architectural risk — pure refactoring

### F. What Should Be Deferred

| Item | Reason |
|------|--------|
| Full agent abstraction for Assistant | Architecture explicitly rejects universal orchestrator (ADR-031, ADR-036) |
| LLM integration for response generation | Explicitly deferred in assessments |
| Conversation state/memory | Explicitly deferred |
| Paperclip integration | ADR-005 explicitly rejected |
| Semantic/embedding matching | Too heavy; use after deterministic matching proven |
| LLM-assisted matching | Requires AI Gateway; future enhancement |
| Capability gap detection | Useful but doesn't help when capabilities exist but aren't matched |
| Skill registration as capabilities | Increases catalog size but doesn't improve matching |
| Work creation by Assistant | Requires Organisation/Control role implementation first |

### G. Proposed Execution Flow After Increment 21A

```
POST /assistant/chat
    │
    ▼
AssistantChatService.chat(request)                    [~30 lines]
    │
    ├─► Intent = create_intent(request.message)
    ├─► frame = recognise(intent)
    │
    ├─► execution_flow = CapabilityExecutionFlow(
    │       capability_discovery=...,
    │       capability_execution=...,
    │       enterprise_information=...
    │   )
    │
    ├─► result = execution_flow.execute(request, frame)
    │   │
    │   ├─► IF previous_solution:
    │   │   └─► RETURN awaiting_confirmation
    │   │
    │   ├─► candidates = find_capabilities(request_text, context)
    │   │
    │   ├─► IF len(candidates) == 0:
    │   │   └─► delegate to PatternExecutionFlow OR clarify
    │   │
    │   ├─► ranked = RelevanceMatcher.rank(candidates, request_text)
    │   │
    │   ├─► IF top.confidence >= 0.8:
    │   │   └─► execute(top) → RETURN result
    │   │
    │   ├─► ELIF top.confidence >= 0.5:
    │   │   └─► present_top_n(ranked, 3) → RETURN selection
    │   │
    │   └─► ELSE:
    │       └─► present_top_n(ranked, 5) → RETURN selection
    │
    └─► RETURN ChatResponse(result)
```

---

## 11. Conclusion

The Assistant architecture is at a crossroads. The ADRs correctly define Assistant as a thin translation service, but the implementation has accreted orchestration logic into a procedural router in `chat.py`. Increment 20 added execution logic to this router. Increment 21 (as proposed) would add matching/confidence logic to the same router.

**The correct next step is NOT to add more logic to `chat.py`.** It is to extract the existing logic into domain services that live in the AI plane, reducing `chat.py` to a thin translation layer. Only then should Increment 21's `RelevanceMatcher` be introduced — into the extracted `CapabilityExecutionFlow` service, not into `chat.py`.

The architecture does not need a new agent framework, a new agent abstraction, or a rewrite. It needs a **boundary correction increment** that proves the intended architecture before adding more behaviour.

---

*No code changes were made during this investigation.*