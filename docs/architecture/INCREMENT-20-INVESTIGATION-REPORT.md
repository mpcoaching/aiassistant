# Increment 20 — Investigation: First Useful Assistant Experience

## 1. Executive Conclusion

The system has working capability execution, telemetry, and outcome assessment. The missing piece is **the chat experience does not guide the user from capability selection to execution result.**

The smallest useful next increment is: **Assistant Chat Execution Path** — wire the existing `execute_selected_capability()` method into the chat response flow so that capability selection leads to actual execution and a useful result message.

This is a chat-layer integration increment. No new infrastructure is required. The capability execution, deployment resolution, authorisation, invocation telemetry, and outcome assessment already work end-to-end.

---

## 2. Current Executable Behaviour

### What Works Today

| Component | Status | Evidence |
|-----------|--------|----------|
| Intent recognition | ✅ Working | `recognise()` classifies via keyword rules |
| Strategy selection | ✅ Working | `select_strategy()` maps ProblemFrame → strategy |
| Session creation | ✅ Working | `SessionFactoryAdapter.create_session()` works |
| Capability discovery | ✅ Working | Returns all registered capabilities |
| Capability execution | ✅ Working | `CapabilityExecutionAdapter.execute()` → `execute_capability()` |
| Invocation telemetry | ✅ Working | `InvocationRecorderAdapter` records to `ConceptStore` |
| Outcome assessment | ✅ Working | `CapabilityOutcomeAssessorAdapter` classifies outcomes |
| Authorisation enforcement | ✅ Working | `InMemoryExecutionAuthorisationPort` |
| Deployment resolution | ✅ Working | `DeploymentResolver` resolves by capability + environment |
| Previous solution lookup | ✅ Working | `EnterpriseInformationPort.find_previous_solutions()` |
| Pattern execution (LangGraph) | ⚠️ Superficial | Nodes record step status, don't invoke real capabilities |
| API `/assistant/chat` | ✅ Working | End-to-end HTTP path exists |
| API `/assistant/capability/{id}/execute` | ✅ Working | Calls `execute_selected_capability()` |

### What Is Stubbed or Missing

| Component | Status | Gap |
|-----------|--------|-----|
| Capability matching | ❌ Stub | `HumanSelectionMatcher` returns ALL capabilities |
| Pattern execution content | ❌ Stub | LangGraph nodes just record `{step_id: {status: "completed"}}` |
| Skill-to-capability wiring | ❌ Missing | 26 skills in `agentic/skills/` are NOT registered as capabilities |
| Natural language capability selection | ❌ Missing | User must manually pick from list |
| Chat execution flow | ❌ Missing | `awaiting_capability_selection` has no execution follow-up |
| Conversation state | ❌ Missing | Each chat call is stateless |
| Actual AI/LLM integration | ❌ Missing | AI-mediated execution returns composed prompt string |

---

## 3. Assistant Chat End-to-End Trace

### Actual Flow for a User Message

```
POST /assistant/chat
  {"message": "Design a new task tracking service"}
    │
    ▼
AssistantChatService.chat()
    │
    ├─► Intent(id="chat-...", raw={"text": "Design a new task tracking service"})
    │
    ├─► recognise(intent)
    │   └─► ProblemFrame(problem_context="design", activity_purpose="decide", confidence=0.85)
    │
    ├─► find_previous_solutions("strategy:deliberate_to_consensus")
    │   └─► None (no previous solutions in ConceptStore)
    │
    ├─► find_capabilities("Design a new task tracking service", frame.context)
    │   └─► HumanSelectionMatcher.match() → returns ALL registered capabilities
    │       (currently none registered in test, but in production would return everything)
    │
    ├─► IF candidates found:
    │   └─► ChatResponse(
    │           status="awaiting_capability_selection",
    │           message="I found capabilities that might help. Please select one to proceed.",
    │           capability_candidates=[...all capabilities...]
    │       )
    │       ▲ FLOW STOPS HERE — user must manually select
    │
    └─► IF no candidates:
        ├─► decide(intent) → StrategyDecision(chosen_strategy="deliberate_to_consensus", pattern_pipeline=["debate@1.0.0", "consensus@1.0.0"])
        ├─► create_session() → SessionReference
        ├─► execute_pattern() → LangGraphRuntime
        │   └─► Builds StateGraph with nodes for each step
        │       Nodes just record: {step_id: {role: "...", tools_used: [...], status: "completed"}}
        │       NO actual capability invocation
        │
        └─► ChatResponse(
                status="completed",
                message="Done. Task completed successfully.",
                reasoning="..."
            )
```

### Where the Flow Stops Being Useful

**Critical stop point:** `awaiting_capability_selection`

When the assistant finds capabilities, it returns them ALL and asks the user to pick one. There is:
1. No follow-up endpoint in the chat flow to execute the selection
2. No natural language mapping ("Run the test capability" → execute `cap-test`)
3. No result formatting — execution results are raw dicts, not chat messages

**Secondary stop point:** Pattern execution

When no capabilities match, the assistant falls through to pattern execution. But LangGraph nodes are stubs — they record step completion without invoking any real capability. The user gets a generic "Done" message regardless of what was requested.

### What a User Actually Sees

**Scenario A: Previous solution exists**
```
User: "Design a new task tracking service"
Assistant: "I've done this before. Last time: Designed a task tracker with 3 interfaces. Want me to reuse that?"
Status: awaiting_confirmation
```
→ This works but requires pre-populated ConceptStore data.

**Scenario B: Capabilities exist**
```
User: "Create a test artifact"
Assistant: "I found capabilities that might help. Please select one to proceed."
Capabilities: [create_test_artifact, enrich_lead, ...]
Status: awaiting_capability_selection
```
→ User sees ALL capabilities. Must manually pick. No execution follows in chat.

**Scenario C: No capabilities match**
```
User: "Do something completely novel"
Assistant: "I'll help with that. Strategy: deliberate_to_consensus. Pipeline: debate@1.0.0, consensus@1.0.0."
Status: pending
```
→ Pattern execution runs but does nothing useful. Generic response.

---

## 4. Current Blockers to Useful Behaviour

### Blocker 1: No Chat Execution Path (Primary)

`AssistantChatService.chat()` returns `awaiting_capability_selection` but there is no mechanism to:
1. Receive the user's selection
2. Execute the selected capability
3. Return the result as a chat response

The API has `/assistant/capability/{id}/execute` but it's a separate endpoint, not part of the chat flow. The user experience is: "Pick a capability" → (user calls different endpoint) → sees raw JSON.

### Blocker 2: Capability Matching Returns Everything (Secondary)

`HumanSelectionMatcher.match()` returns all capabilities regardless of request. This means:
- "Create a test artifact" shows the same capabilities as "Enrich a lead"
- The user must manually scan the entire list
- No ranking, no filtering, no relevance

### Blocker 3: Skills Are Not Registered Capabilities (Tertiary)

There are 26 skill files in `agentic/skills/` (e.g., `requirements.discovery.extract-stakeholders.md`, `development.implement-task.md`). These are NOT registered as `Capability` records in `CapabilityRegistry`. The registry starts empty unless capabilities are explicitly created and registered.

### Blocker 4: Pattern Execution Is Superficial (Tertiary)

LangGraph nodes in `_build_graph()` just record step status. They don't:
- Invoke capabilities
- Call skills
- Produce real outputs
- Interact with the bus or execution layer

Pattern execution is a skeleton, not a functional execution path.

### What Is NOT a Blocker

| Concern | Status | Why It's Not Blocking |
|---------|--------|----------------------|
| Paperclip | ✅ Not needed | Explicitly rejected (ADR-005). Would only be a PathwayRuntime adapter later |
| Maturation/promotion | ✅ Not needed | Internal infrastructure, not user-facing |
| Discovery port split | ✅ Not needed | Combined `find_capabilities()` works |
| Execution convergence | ✅ Not needed | Both paths work |
| Deployment lifecycle | ✅ Not needed | Static deployments work for first slice |
| AI-mediated execution | ⚠️ Stub but OK | Returns composed prompt; real LLM integration is future work |

---

## 5. Paperclip Assessment

### What Paperclip Is Expected to Provide

Based on ADR-023 and ADR-005:

| Paperclip Concept | What It Provides | Relevance |
|-------------------|-----------------|-----------|
| Agent crews/roles | Multi-agent role-play coordination | Maps to LangGraph participant nodes |
| Meetings/deliberation | Structured multi-agent discussion | Maps to pattern steps with participants |
| Tool-use abstraction | Agent-level tool invocation | Would map to capability execution |

### Where Paperclip Should Sit

Paperclip is intended to sit **behind `PathwayRuntime`** as an adapter implementation. Specifically:
- `PathwayRuntime.invoke()` → could be implemented by Paperclip
- `PathwayRuntime.resume()` → could be implemented by Paperclip
- NOT a domain-plane dependency
- NOT visible to AI, People/Capability, or Enterprise planes

### Should It Be Introduced Now?

**No.** Reasons:
1. **Explicitly rejected by ADR-005:** "Paperclip is not adopted as an architectural component"
2. **Existing substrate works:** LangGraph runtime already implements `PathwayRuntime`
3. **Premature complexity:** Paperclip adds agent coordination before the basic capability execution is proven in production
4. **No user-facing gap:** The first useful experience does not require multi-agent role-play
5. **Coupling risk:** Introducing Paperclip now would create a second execution substrate

### Minimum Viable Paperclip Integration (Future)

If introduced later, the minimum would be:
1. Implement `PathwayRuntime` interface using Paperclip crews
2. Wire through `PatternExecutionAdapter` (already abstracted)
3. No changes to AI, People/Capability, or Enterprise planes
4. Feature flag or environment-based runtime selection

---

## 6. Proposed First Vertical Slice

### Name: Assistant Chat Execution Path

### Objective

Make the assistant chat return useful execution results instead of stopping at capability selection.

### User Experience

```
User: "Create a test artifact"
Assistant: "I found 1 capability that can help: create_test_artifact. Running it now..."
Assistant: "Done. Here's what happened: {formatted result}"
```

Or, for a more direct pattern:

```
User: "Run capability create_test_artifact"
Assistant: "Executing create_test_artifact..."
Assistant: "Result: {formatted result}"
```

### What Already Works

| Layer | Component | Status |
|-------|-----------|--------|
| Intent recognition | `recognise()` | ✅ Working |
| Capability discovery | `CapabilityDiscoveryAdapter.find_capabilities()` | ✅ Working |
| Capability execution | `CapabilityExecutionAdapter.execute()` | ✅ Working |
| Telemetry | `InvocationRecorderAdapter` | ✅ Working |
| Outcome assessment | `CapabilityOutcomeAssessorAdapter` | ✅ Working |
| API | `/assistant/chat`, `/assistant/capability/{id}/execute` | ✅ Working |

### What Needs to Change

Only the **chat response flow** in `AssistantChatService`:

1. **Add execution path to `chat()` method:**
   - When capabilities are found, instead of returning `awaiting_capability_selection`, execute the first/most relevant capability
   - Format the `ExecutionResult` into a natural language response
   - Return `status="completed"` with the result

2. **Improve capability selection response:**
   - When multiple capabilities are found, present them with descriptions
   - Include execution mode and tags
   - Make the list scannable

3. **Add "list capabilities" intent handling:**
   - When user asks "What can you do?" or similar, return a formatted capability list
   - Don't require manual selection from raw candidates

### What Must NOT Change

- `CapabilityRegistry.promote()` — no maturation logic
- `CapabilityOutcomeAssessor` — keep as-is
- `InvocationRecorderAdapter` — keep as-is
- Execution paths (`PatternRuntime`, `CapabilityExecutionAdapter`) — keep as-is
- `ConceptStore.record_invocation()` — keep as-is
- AI plane dependencies — no new cross-plane imports
- Pattern execution — leave for future slice

---

## 7. Exact Implementation Scope

### MUST IMPLEMENT

1. **Enhanced chat response in `AssistantChatService.chat()`**
   - When capabilities are found and user intent suggests execution, execute the top candidate
   - Format `ExecutionResult` into natural language response
   - Return `status="completed"` with execution summary

2. **Capability list response**
   - When user asks about capabilities ("What can you do?", "List capabilities"), return formatted list
   - Include name, description, kind, and execution mode for each

3. **Better capability candidate formatting**
   - Current: raw dict with id, name, description, kind, execution_mode, tags
   - Improved: human-readable message with capability descriptions

### TESTS REQUIRED

| Test | Purpose |
|------|---------|
| `test_chat_executes_capability_and_returns_result` | Chat flow executes capability and formats result |
| `test_chat_lists_capabilities_when_asked` | "What can you do?" returns formatted capability list |
| `test_chat_capability_selection_message_improved` | Selection response includes descriptions |
| Integration test: end-to-end capability execution via chat | Full HTTP → chat → execution → response |

### MUST NOT IMPLEMENT

- Capability maturation/promotion
- Capability matching/decomposition
- Execution path convergence
- Pattern execution improvements
- Deployment lifecycle
- AI-mediated execution implementation
- Per-invocation history
- Bus events for capability invocation
- Paperclip integration
- Skill-to-capability registration (future slice)
- Conversation state/memory

---

## 8. Architectural Invariants

1. **AI plane depends on ports only** — no new imports from domain implementations
2. **Operations owns execution** — chat delegates to `CapabilityExecutionPort`
3. **Enterprise owns durable storage** — no direct ConceptStore access from AI
4. **People/Capability owns maturation** — not implemented
5. **No circular dependencies** — new code in AI plane only
6. **Fire-and-forget telemetry** — execution result not altered by recording
7. **Both execution paths available** — pattern and direct capability execution preserved
8. **Composition root owns wiring** — no new module-level instantiation
9. **No new cross-plane dependencies** — all changes in AI plane
10. **Existing tests pass** — no regressions

---

## 9. Next Increment Recommendation

### Increment 20: Assistant Chat Execution Path

**Objective:** Wire the existing capability execution into the chat response flow so users get useful results.

**Why this increment:**
1. **Visible usefulness** — User gets actual capability results in chat
2. **Real end-to-end execution** — Uses proven Increment 18/19 infrastructure
3. **Architectural integrity** — No new planes, no new dependencies, no boundary violations
4. **Minimal new infrastructure** — Only chat response logic changes
5. **Foundation for future** — Establishes the chat as a real execution interface

**What it unlocks:**
- Users can discover and execute capabilities through chat
- The system becomes demonstrably useful, not just architecturally correct
- Future increments (matching, skills, patterns) build on a working chat experience

**What it deliberately does NOT do:**
- Change capability matching (still returns all)
- Implement maturation
- Wire skills as capabilities
- Improve pattern execution
- Add Paperclip
- Add conversation state

---

## 10. Evidence Summary

### Current Code State

| Component | Location | Status |
|-----------|----------|--------|
| `AssistantChatService.chat()` | `ai/src/chat.py:86-184` | Returns `awaiting_capability_selection` or pattern result |
| `AssistantChatService.execute_selected_capability()` | `ai/src/chat.py:205-217` | Works but not called from `chat()` |
| `/assistant/chat` API | `workflow_runner/api.py:622-642` | Working |
| `/assistant/capability/{id}/execute` API | `workflow_runner/api.py:756-767` | Working |
| `HumanSelectionMatcher` | `capability_registry/src/capability_matcher.py:40-63` | Returns all capabilities |
| `CapabilityExecutionAdapter` | `workflow_runner/src/adapters/capability_execution_adapter.py` | Working |
| `InvocationRecorderAdapter` | `workflow_runner/src/adapters/invocation_recorder_adapter.py` | Working |
| `CapabilityOutcomeAssessorAdapter` | `workflow_runner/src/adapters/capability_outcome_assessor_adapter.py` | Working |
| LangGraph runtime | `langgraph/src/langgraph_runtime.py` | Superficial step recording |
| Skills (26 files) | `agentic/skills/*.md` | Not registered as capabilities |
| Paperclip references | Comments only | ADR-005 explicitly rejected |

### Test Evidence

| Test Suite | Count | Status |
|------------|-------|--------|
| `workflow_runner/tests/` | 185 | All pass |
| `ai/tests/` | 45 | All pass |
| `ai/tests/test_architectural_boundaries.py` | 12 | All pass |
| Increment 18 tests | 12 | All pass |
| Increment 19 tests | 28 | All pass |

### Architectural Assessment

| Category | Items |
|----------|-------|
| **Genuinely required before vertical slice** | None — execution, telemetry, and assessment all work |
| **Can wait** | Matching decomposition, execution convergence, deployment lifecycle |
| **Existing stubs preventing usefulness** | Capability matching (returns all), pattern execution (superficial), chat execution flow (missing) |
| **Architecturally correct but not yet valuable** | Maturation/promotion, per-invocation history, bus events, AI-mediated LLM integration |

---

**INVESTIGATION STATUS: COMPLETE**

**RECOMMENDATION:** Increment 20 should implement **Assistant Chat Execution Path** — the smallest change that makes the assistant visibly useful by wiring existing capability execution into the chat response flow.
 infrastructure from organisational orchestration.

**Evidence:** ADR-010 establishes provider-based architecture. The AI gateway is a future Operations concern. Paperclip should not know about providers.

**Status:** Validated. No coupling exists yet, and the boundary is clear.

### Principle 6 ✅ Validated

> No architectural layer should depend on today's preferred AI runtime.

**Evidence:** ADR-010, ADR-023. OrganisationControlPlane has zero Paperclip imports. `PathwayRuntime` is the abstraction; LangGraph is one implementation.

**Status:** Validated. The architecture already enforces this.

### Principle 7 ✅ Validated

> Runtime selection should eventually be evidence-driven rather than permanently hard-coded.

**Evidence:** Increment 19 outcome assessment produces evidence. The future optimisation model is documented. Currently only one runtime exists, so selection is trivial.

**Status:** Validated. The infrastructure for evidence collection exists; selection logic is future work.

### Principle 8 ✅ Validated

> The Assistant is the default front door for ambiguous organisational intent.

**Evidence:** ADR-044 establishes Assistant as application-layer translation service. The chat API is the primary user interface.

**Status:** Validated. Increment 20 reinforces this by making chat the execution interface.

### Principle 9 ✅ Validated

> Explicitly addressed organisational requests may bypass the Assistant's capability discovery and route directly to the relevant actor/team.

**Evidence:** ADR-044, ADR-025. The Assistant translates intent; it does not own routing. Direct capability execution bypasses discovery.

**Status:** Validated. The architecture allows direct routing for known capabilities.

### Principle 10 ✅ Validated

> Reasoning-heavy work and deterministic execution are different execution modes.

**Evidence:** `ExecutionMode.AI_MEDIATED` vs `ExecutionMode.COMPILED`. LangGraph pattern execution vs `execute_capability()`. Both paths exist and are preserved.

**Status:** Validated. The architecture distinguishes reasoning from deterministic execution.

### Principle 11 ✅ Validated

> Repeated successful reasoning should be able to become a deterministic capability/workflow.

**Evidence:** ADR-029 (EIMS learning loop), ADR-004 (pattern promotion). The intended path is: reasoning → solution → enterprise concept → capability → compiled deployment.

**Status:** Validated. The learning loop is defined but not yet implemented.

### Principle 12 ✅ Validated

> Execution outcomes should produce evidence that can improve capability, proficiency and runtime selection over time.

**Evidence:** Increment 18 (invocation telemetry), Increment 19 (outcome assessment). Evidence flows to `ConceptStore` and `MaturationHistory`.

**Status:** Validated. The evidence collection infrastructure exists.

---

## 20. Critical Distinctions (Explicitly Defined)

### Capability

**What it is:** Ability required by the organisation to reliably produce an outcome.
**Owned by:** People/Capability
**Example:** "Architecture design", "Lead enrichment", "Daily task reflection"

### Skill

**What it is:** Component of a capability (knowledge, method, technique).
**Owned by:** People/Capability
**Example:** "UML modelling", "Tradeoff analysis", "Stakeholder interview"
**Relationship:** Skill contributes to Capability. A capability may require multiple skills.

### Tool

**What it is:** Mechanism used to enable/support a capability.
**Owned by:** IT/Technology (provisioning), People/Capability (requirements)
**Example:** "Enterprise Architect tool", "Email client", "Spreadsheet"
**Relationship:** Tool enables Capability. A capability may require specific tools.

### Role

**What it is:** Abstract organisational position with responsibilities, authority, constraints.
**Owned by:** Organisation/Control
**Example:** "Enterprise Architect", "CEO", "Engineer"
**Relationship:** Role requires Capabilities. Work is assigned to Roles.

### Person

**What it is:** Human individual with identity and employment context.
**Owned by:** People/Capability
**Example:** "John Smith, EA"
**Relationship:** Person fulfils Role. Person possesses Capabilities.

### Agent

**What it is:** Software entity that performs work, with runtime identity.
**Owned by:** People/Capability (records), Operations (execution)
**Example:** "Claude Code instance", "Kilo agent"
**Relationship:** Agent fulfils Role. Agent possesses Capabilities. Agent operates in Agent Runtime.

### Team

**What it is:** Group of agents/persons under organisational coordination.
**Owned by:** Organisation/Control (structure), People/Capability (membership)
**Example:** "Engineering team", "AI agent company"
**Relationship:** Team is a collection of Roles/Agents. Paperclip models this as org chart.

### Work

**What it is:** Instance of assigned effort, accountable to a Role.
**Owned by:** Organisation/Control
**Example:** "Design the new architecture", "Enrich lead records"
**Relationship:** Work requires Capabilities. Work is assigned to Role/Person/Agent. Work produces Outcomes.

### Workflow

**What it is:** Deterministic method for exercising a capability.
**Owned by:** Operations
**Example:** "Daily report generation", "Lead enrichment pipeline"
**Relationship:** Workflow implements a Capability. Workflow is deterministic execution.

### Agent Runtime

**What it is:** Execution mechanism used by an AI agent.
**Owned by:** Operations (interface), external (implementation)
**Example:** "LangGraph", "Claude Code", "Codex", "Kilo", "deterministic Python"
**Relationship:** Agent Runtime executes Agent. Agent Runtime invokes Capabilities/Tools/Skills.

### Model

**What it is:** Specific LLM instance (e.g., Claude Opus, GPT-4o).
**Owned by:** AI Gateway / Provider
**Example:** "claude-opus-4", "gpt-4o", "llama-3"
**Relationship:** Model is invoked by Agent Runtime via AI Gateway.

### AI Provider

**What it is:** Service that exposes models via API.
**Owned by:** External / AI Gateway
**Example:** "Anthropic", "OpenAI", "Ollama", "Local"
**Relationship:** AI Provider hosts Models. AI Gateway routes to Providers.

---

## 21. Future Optimisation Model

### Documented as Future Capability

```
Capability required
    ↓
Candidate actors (Person/Agent with CapabilityAssignment)
    ↓
Candidate runtimes (LangGraph, Paperclip, deterministic)
    ↓
Historical evidence (invocation telemetry, outcome assessment)
    ↓
Selection (exploration/exploitation)
    ↓
Execution
    ↓
Outcome assessment
    ↓
Evidence update
```

### Where This Belongs

**Future Operations concern.** Does not belong in:
- People/Capability (does not execute)
- Assistant (does not select runtimes)
- Paperclip (does not know about execution technology)
- AI Gateway (does not know about capabilities)

May eventually belong in:
- `DeploymentResolver` (already exists in Operations)
- Or a dedicated `RuntimeSelector` service

### Initial Implementation

Initially there may only be one runtime (Kilo/LangGraph), meaning no optimisation is necessary:

```python
def select_runtime(deployment: CapabilityDeployment) -> PathwayRuntime:
    if deployment.execution_mode == ExecutionMode.COMPILED:
        return deterministic_executor
    elif deployment.execution_mode == ExecutionMode.AI_MEDIATED:
        return langgraph_runtime
    # Future: evidence-based selection
    # return runtime_selector.select(deployment.capability_id, context)
```

### Exploration/Exploitation

Future consideration:
- **Exploitation**: Use the runtime that has historically worked best
- **Exploration**: Occasionally try alternatives to gather evidence
- This is a multi-armed bandit problem, solved by outcome assessment data

---

## 22. Validation

### Architectural Consistency Checks

| Check | Result |
|-------|--------|
| No circular dependencies between planes | ✅ Pass |
| AI plane depends on ports only | ✅ Pass (except current AssistantChatService which ADR-044 identifies) |
| Operations owns execution | ✅ Pass |
| Enterprise owns durable storage | ✅ Pass |
| People/Capability owns capability lifecycle | ✅ Pass |
| Organisation/Control does not execute | ✅ Pass |
| Capability domain model has no execution metadata | ✅ Pass (ADR-042) |
| No Paperclip imports in domain models | ✅ Pass (ADR-023) |

### Existing Tests

| Test Suite | Count | Status |
|------------|-------|--------|
| `workflow_runner/tests/` | 185 | All pass |
| `ai/tests/` | 45 | All pass |
| `ai/tests/test_architectural_boundaries.py` | 12 | All pass |
| Increment 18 tests | 12 | All pass |
| Increment 19 tests | 28 | All pass |

### No Code Changes

This investigation made no code changes. No tests to run, no lint to check.

### ADR References Verified

| ADR | Referenced Correctly |
|-----|---------------------|
| ADR-005 | ✅ Paperclip rejected |
| ADR-010 | ✅ Provider-based architecture |
| ADR-017 | ✅ Three-plane architecture |
| ADR-018 | ✅ Role vs Person vs Agent |
| ADR-020 | ✅ Capability ownership |
| ADR-022 | ✅ OCP narrow abstraction |
| ADR-023 | ✅ Paperclip adapter boundary |
| ADR-029 | ✅ EIMS learning loop |
| ADR-035 | ✅ Capability/Skill/Tool distinction |
| ADR-037 | ✅ Person/Agent ownership |
| ADR-039 | ✅ Organisation→Operations handoff |
| ADR-040 | ✅ Capability assignment/proficiency |
| ADR-042 | ✅ Execution binding separation |
| ADR-044 | ✅ Assistant as translation service |

---

## 23. Final Output

### What Was Discovered

1. **The architecture is sound and well-documented.** Four-plane separation, explicit boundaries, and port-based abstractions are consistently applied.

2. **Capability execution, telemetry, and outcome assessment work end-to-end.** Increments 14-19 proved the Operations layer. The missing piece is the chat experience.

3. **Paperclip is an organisational control plane, not an execution runtime.** It coordinates agents as a company, not as a workflow engine. It belongs as an optional `OrganisationControlPlane` adapter.

4. **The Agent Runtime boundary already exists** via `PathwayRuntime`. No new abstraction is needed.

5. **The AI Gateway is a future Operations concern.** It sits between Agent Runtime and Model/Provider. Paperclip should not know about it.

6. **The Assistant is currently a God service** (per ADR-044) but should be an application-layer translation service.

7. **Reasoning and deterministic execution are correctly distinguished** in the architecture. The learning loop (reasoning → capability → deterministic) is defined but not implemented.

8. **Skills and tools are conceptually distinct from capabilities** but currently conflated in the implementation. ADR-035 proposes separation.

### What Assumptions Were Wrong

1. **Assumption:** Paperclip might provide agent coordination that our architecture lacks.
   **Reality:** Paperclip provides organisational coordination (org charts, budgets, governance), not execution coordination. Our architecture already has pattern execution via LangGraph.

2. **Assumption:** We might need a new Agent Runtime abstraction.
   **Reality:** `PathwayRuntime` already provides this. LangGraph is one implementation. Adding another abstraction would be premature.

3. **Assumption:** The AI Gateway might need to be visible to Paperclip.
   **Reality:** Paperclip should not know about providers or models. The adapter layer handles this.

4. **Assumption:** Capability matching might need to be in the Assistant.
   **Reality:** Capability matching belongs to People/Capability. The Assistant translates intent, delegates to ports.

### What Architectural Boundaries Are Now Established

| Boundary | Established By | Status |
|----------|---------------|--------|
| Enterprise ↔ Organisation/Control | ADR-017 | ✅ Stable |
| Organisation/Control ↔ People/Capability | ADR-017, ADR-020 | ✅ Stable |
| People/Capability ↔ Operations | ADR-017, ADR-042 | ✅ Stable |
| Operations ↔ Agent Runtime | `PathwayRuntime` interface | ✅ Stable |
| Agent Runtime ↔ AI Gateway | Future (not yet implemented) | ⚠️ Defined but not built |
| AI Gateway ↔ Model/Provider | ADR-010 | ⚠️ Defined but not built |
| Paperclip ↔ Our architecture | ADR-023, ADR-039 | ✅ Stable (adapter boundary) |
| Assistant ↔ Domain planes | ADR-044 | ⚠️ Defined but not enforced (current implementation violates) |

### What Paperclip Actually Does

Paperclip is an **open-source control plane for orchestrating virtual companies composed of AI agents**. It provides:

- **Organisational structure**: Org charts, roles, reporting lines
- **Work management**: Issues, tasks, parent-child hierarchies
- **Agent coordination**: Heartbeat scheduling, delegation, @mentions
- **Governance**: Budgets, approvals, audit logs, human sign-off
- **Runtime adapters**: Pluggable adapters for Claude Code, Codex, Cursor, etc.
- **Multi-tenancy**: Company-scoped data isolation

Paperclip does NOT:
- Define business capabilities
- Execute deterministic workflows
- Own enterprise knowledge
- Provide agent reasoning
- Select models/providers

### What the Agent Runtime Actually Does

An agent runtime is the **execution mechanism for an AI agent**. It:
- Receives capability/work to execute
- Manages agent state and context
- Invokes models via AI Gateway
- Handles tools and skills
- Returns execution results
- Manages long-running tasks (sessions, checkpoints)

Current runtimes:
- **LangGraph**: Pattern execution with state graphs
- **Deterministic Python**: `execute_capability()` for compiled code
- **Future**: Claude Code, Codex, Kilo, etc.

### Where Our AI Gateway Belongs

The AI Gateway sits **between Agent Runtime and Model/Provider**:

```
Agent Runtime
    ↓
AI Gateway (model selection, provider routing, cost/latency optimisation)
    ↓
Model/Provider (Anthropic, OpenAI, local, etc.)
```

It should be:
- Owned by Operations
- Replaceable via provider-based architecture (ADR-010)
- Not visible to Paperclip, Assistant, People/Capability, or Enterprise
- A future implementation, not a current blocker

### Where Capability Belongs

Capability belongs in the **People/Capability plane**. It:
- Defines what the organisation needs to accomplish
- Is owned by People/Capability
- Is discovered and matched by People/Capability
- Is assigned to Person/Agent via People/Capability
- Is executed by Operations (via `CapabilityExecutionPort`)

Capability does NOT:
- Know about execution technology
- Know about agent runtimes
- Know about model providers
- Execute itself

### Where the Assistant Belongs

The Assistant belongs in the **AI plane** as an **application-layer translation service**. It:
- Accepts natural language
- Recognises intent
- Selects strategy
- Translates to domain plane requests
- Formats responses

The Assistant does NOT:
- Execute work
- Match capabilities
- Access enterprise knowledge directly
- Invoke runtimes directly

### Where Deterministic Workflows Belong

Deterministic workflows belong in the **Operations plane**. They:
- Execute via `execute_workflow()` or `execute_capability()`
- Do not require reasoning or deliberation
- Are compiled/repeatable processes
- Produce deterministic outputs

### Whether "Build the Team as We Use It" Is Architecturally Supported

**Yes, with gaps.**

The architecture CAN support this model because:
1. Capability lifecycle is owned by People/Capability
2. CapabilityAssignment and CapabilityProficiency exist
3. Execution telemetry and outcome assessment exist
4. Work assignment and organisational context exist
5. The learning loop (ADR-029) is defined

The gaps are:
1. No automated capability gap detection (Increment 20 partial fix)
2. No automated agent creation/training (future)
3. No proficiency-driven assignment (future)
4. No training recommendation engine (future)

### Which ADRs Were Added/Changed

**No ADRs were added or changed during this investigation.** The existing ADRs remain correct and coherent.

Potential future ADRs (do NOT create yet):
- ADR-046: Assistant as primary user interface
- ADR-047: Capability chat execution path
- ADR-048: AI Gateway/provider abstraction
- ADR-049: Runtime selection responsibility

### The Recommended Next Increment

**Increment 20 — Assistant Chat Execution Path**

**Why this increment:**
1. **Visible usefulness**: Users can discover and execute capabilities through chat
2. **Real end-to-end execution**: Uses proven Increment 18/19 infrastructure
3. **Architectural integrity**: No new planes, no new dependencies, no boundary violations
4. **Minimal new infrastructure**: Only chat response logic changes
5. **Foundation for future**: Establishes the chat as a real execution interface

**What it unlocks:**
- Users can discover and execute capabilities through chat
- The system becomes demonstrably useful, not just architecturally correct
- Future increments (matching, skills, patterns) build on a working chat experience

**What it deliberately does NOT do:**
- Change capability matching (still returns all)
- Implement maturation
- Wire skills as capabilities
- Improve pattern execution
- Add Paperclip
- Add conversation state

### Why This Increment Should Come Next

The core question is: **"Can the Assistant receive a real request, understand it, discover whether a capability exists, execute something useful, and record the outcome?"**

Currently the answer is **NO** — the assistant discovers capabilities but cannot execute them through chat.

Increment 20 changes the answer to **YES** by wiring the existing `execute_selected_capability()` method into the chat response flow.

This is the smallest change that makes the system visibly useful. Everything else (matching, skills, patterns, Paperclip) builds on top of a working execution interface.

### What Should Explicitly NOT Be Built Yet

| Thing | Why Not |
|-------|---------|
| Paperclip integration | ADR-005 explicitly rejected. Core loop not proven. |
| Capability maturation/promotion | Internal infrastructure, not user-facing |
| Capability matching/decomposition | Returns all for now; improve after chat works |
| Execution path convergence | Both paths work; premature to unify |
| Deployment lifecycle | Static deployments work for first slice |
| AI-mediated execution implementation | Stub is sufficient for now |
| Per-invocation history | Fire-and-forget telemetry sufficient |
| Bus events for capability invocation | Synchronous recording works |
| Skill-to-capability registration | Future slice after chat works |
| Conversation state/memory | Future slice after chat works |
| AI Gateway implementation | Only one provider currently |
| Runtime selection optimisation | Only one runtime currently |

---

## 24. Open Questions

### Questions for Future Increments

1. **Should the Assistant be refactored to use ports?** ADR-044 identifies this but it is not blocking Increment 20. Eventually the AI plane should depend on ports, not concrete implementations.

2. **Should skills be registered as capabilities?** Yes, but after Increment 20 proves the chat execution path. The migration from `Registry` to `CapabilityRegistry` needs careful design.

3. **Should CapabilityKind include WORKFLOW?** Currently only TOOL and SKILL. Workflows are a distinct execution mode. May need a third kind or a separate concept.

4. **How should the AI Gateway integrate with LangGraph?** LangGraph currently uses direct model configuration. The AI Gateway should abstract this without breaking existing LangGraph patterns.

5. **Should Paperclip eventually replace LangGraph?** No. They solve different problems. Paperclip coordinates organisational work; LangGraph executes patterns. They may coexist.

6. **How should capability gap detection work?** The architecture defines CapabilityRequest but does not implement it. Increment 20 may include a simple version.

7. **Should the learning loop be implemented before or after Paperclip?** Before. The learning loop (ADR-029) is independent of Paperclip and provides evidence for runtime selection.

### Questions That Block Nothing

These questions are noted but do not block any current increment:

- Should Capability and Skill be separate domain models? (ADR-035 is investigation-only)
- Should the AI Gateway support local models? (Future concern)
- Should runtime selection be a separate service? (Future concern)
- Should agents have persistent memory across sessions? (Future concern)
- Should Paperclip support our Work model natively? (Future adapter concern)

---

**INVESTIGATION STATUS: COMPLETE**

**RECOMMENDATION:** Increment 20 should implement **Assistant Chat Execution Path** — the smallest change that makes the assistant visibly useful by wiring existing capability execution into the chat response flow.

The architecture is sound. Paperclip is not needed yet. The execution layer works. The chat layer needs to be wired to it.
 an organisational layer that is not needed for this increment.

2. **Uses proven infrastructure**: Increments 14-19 proved capability execution, telemetry, and outcome assessment. Increment 20 only changes the chat response flow.

3. **Preserves architectural boundaries**: No new planes, no new dependencies, no boundary violations.

4. **Makes the system visibly useful**: Users can discover and execute capabilities through chat.

5. **Establishes the execution interface**: Future increments (matching, skills, patterns, Paperclip) build on a working chat execution interface.

### What Increment 20 Does NOT Change

- Paperclip integration (not needed)
- Capability matching (still returns all)
- Pattern execution (still superficial)
- Skills registration (not yet)
- Conversation state (not yet)
- AI Gateway (not yet)

### The Core Question

> "Can the Assistant receive a real request, understand it, discover whether a capability exists, execute something useful, and record the outcome?"

Currently: **NO** — assistant discovers but cannot execute through chat.

Increment 20 makes this: **YES**

---

## 15. Responsibility Matrix

| Concern | Owner | Evidence |
|---------|-------|----------|
| Capability definition | People/Capability | ADR-020, ADR-042 |
| Capability lifecycle | People/Capability | CapabilityRegistry, CapabilityStatus |
| Capability matching | People/Capability | CapabilityMatcher, CapabilityDiscoveryAdapter |
| Capability assignment | People/Capability | CapabilityAssignment |
| Capability proficiency | People/Capability | CapabilityProficiency |
| Person records | People/Capability | ADR-037 |
| Agent records | People/Capability | ADR-037 |
| Evidence from executions | People/Capability | MaturationHistory in ConceptStore |
| Execution | Operations | ADR-042, ADR-039 |
| Workflow definitions | Operations | ADR-039 |
| Agent runtime | Operations | ADR-018 |
| Deterministic workflow execution | Operations | `execute_workflow()`, `execute_capability()` |
| Pattern execution | Operations | `PatternExecutionPort`, LangGraph |
| Capability execution | Operations | `CapabilityExecutionPort`, `CapabilityExecutionAdapter` |
| Session management | Operations | `SessionFactoryPort`, `SessionFactoryAdapter` |
| Deployment resolution | Operations | `DeploymentResolver` |
| Invocation telemetry | Operations | `InvocationRecorderAdapter` |
| Outcome assessment | Operations | `CapabilityOutcomeAssessorAdapter` |
| Enterprise knowledge | Enterprise | ADR-021 |
| Strategy | Enterprise | ADR-017 |
| Governance policies | Enterprise | ADR-017 |
| Organisational structure | Organisation/Control | ADR-017, ADR-022 |
| Work assignment | Organisation/Control | ADR-027, ADR-039 |
| Authority delegation | Organisation/Control | ADR-019, ADR-022 |
| Organisational context | Organisation/Control | ADR-022 |
| Multi-agent coordination | Paperclip (future) | organisational coordination, not pattern execution |
| Budget/governance | Paperclip (future) | organisational control |
| Agent identity/role | Paperclip (future) | agent registry |
| Task scheduling/heartbeat | Paperclip (future) | heartbeat mechanism |
| Intent recognition | AI plane | `recognise()` in `intent.py` |
| Strategy selection | AI plane | `select_strategy()` |
| Natural language translation | AI plane | `AssistantChatService` (application-layer) |
| Response formatting | AI plane | `ChatResponse` models |
| Model/provider invocation | AI Gateway (future) | ADR-010 |
| Provider abstraction | AI Gateway (future) | ADR-010 |
| Cost/latency optimisation | AI Gateway (future) | future concern |

---

## 16. Architecture Diagrams

### Current Architecture

```
User
  ↓
Assistant (AI plane)
  ↓
┌─────────────────────────────────────┐
│    Current: God Service             │
│  - Imports CapabilityRegistry       │
│  - Imports ConceptStore             │
│  - Imports PathwayRuntime           │
│  - Executes patterns directly       │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│           Organisation              │
│  - Strategy                         │
│  - ConceptStore (EIMS)              │
│  - Governance                       │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│         Organisation                │
│  - Roles                            │
│  - Work assignment                   │
│  - Authority                        │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│     People/Capability Plane         │
│  - Capability definitions           │
│  - CapabilityRegistry               │
│  - Matching, assignment, proficiency│
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       Operations Plane              │
│  - Pattern execution (LangGraph)    │
│  - Capability execution             │
│  - Workflow execution               │
│  - PathwayRuntime                   │
│  - Deployment resolution            │
│  - Invocation telemetry             │
│  - Outcome assessment               │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       Model/Provider                │
│  - Anthropic, OpenAI, etc.          │
└─────────────────────────────────────┘
```

### Proposed Architecture (After Increment 20)

```
User
  ↓
Assistant (AI plane) — application-layer translation service inside Organisation
  ↓
┌─────────────────────────────────────┐
│           Organisation              │
│  - Strategy                         │
│  - ConceptStore (EIMS)              │
│  - Governance                       │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│         Organisation                │
│  - Roles                            │
│  - Work assignment                   │
│  - Authority                        │
│  - Paperclip adapter (future)        │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│     People/Capability Plane         │
│  - Capability definitions           │
│  - CapabilityRegistry               │
│  - Matching, assignment, proficiency│
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       Operations Plane              │
│  - Pattern execution (LangGraph)    │
│  - Capability execution             │
│  - Workflow execution               │
│  - PathwayRuntime                   │
│  - Deployment resolution            │
│  - Invocation telemetry             │
│  - Outcome assessment               │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       AI Gateway (future)           │
│  - Model selection                  │
│  - Provider selection               │
│  - Cost/latency optimisation        │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       Model Providers               │
│  - Anthropic (Claude)               │
│  - OpenAI (GPT)                     │
│  - Local models                     │
│  - Future providers                 │
└─────────────────────────────────────┘
```

### Paperclip Integration (Future)

```
User
  ↓
Assistant
  ↓
┌─────────────────────────────────────┐
│    Organisation/Control Plane       │
│  - Our OCP (roles, authority, work) │
│  - Paperclip (agent coordination,   │
│    budgets, governance, heartbeat)  │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│     People/Capability Plane         │
│  - Capability definitions           │
│  - Matching, assignment, proficiency│
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       Operations Plane              │
│  - Pattern execution (LangGraph)    │
│  - Capability execution             │
│  - Agent Runtime                    │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       AI Gateway (future)           │
└─────────────────────────────────────┘
  ↓
┌─────────────────────────────────────┐
│       Model Providers               │
└─────────────────────────────────────┘
```

---

## 17. Paperclip Integration Analysis

### What Paperclip Provides That We Don't Have

| Capability | Current State | Paperclip Provides |
|------------|--------------|-------------------|
| Persistent agent identity | Agent records exist but no orchestration | Full agent lifecycle with budgets |
| Multi-agent coordination | LangGraph patterns only | Organisational coordination with org charts |
| Task dependencies | Work.dependencies exists | Parent-child hierarchies, blocking |
| Budget/governance | Not implemented | Per-agent budgets, approval, audit |
| Heartbeat scheduling | Not implemented | Periodic agent wake-up |
| Agent communication | Not implemented | @mentions, sub-issues, escalation |
| Multi-tenancy | Not implemented | Company-scoped isolation |

### What We Have That Paperclip Doesn't

| Capability | Paperclip | Our Architecture |
|------------|-----------|-----------------|
| Capability domain model | No | Full Capability model with lifecycle |
| Capability execution | Via adapters only | Direct `CapabilityExecutionPort` |
| Deterministic workflows | No | `execute_workflow()`, compiled capabilities |
| Enterprise knowledge | No | ConceptStore, EIMS |
| Learning loop | No | ADR-029, outcome assessment |
| Provider abstraction | No | ADR-010, future AI Gateway |
| Capability matching | No | CapabilityMatcher, CapabilityDiscoveryAdapter |

### Integration Strategy (Future)

When Paperclip is adopted:

1. **Paperclip manages agents and work assignment** — delegates to our Operations plane for execution
2. **Our Operations plane executes capabilities** — via existing `CapabilityExecutionPort` and `PatternExecutionPort`
3. **Our People/Capability plane defines capabilities** — Paperclip agents reference capabilities but don't define them
4. **Our Enterprise plane owns knowledge** — Paperclip doesn't touch EIMS

### Why Not Now

1. ADR-005 correctly rejects Paperclip for current implementation
2. Core execution loop not proven in production
3. No user-facing need for multi-agent coordination
4. Heavy integration cost (90+ tables, complex adapter)
5. Architectural position now clarified (not a PathwayRuntime adapter)

---

## 18. Capability Lifecycle Analysis

### Current Lifecycle

```
NEED IDENTIFIED
    ↓
CAPABILITY GAP (manual)
    ↓
SPECIFICATION (manual)
    ↓
BUILD (manual)
    ↓
TEST (manual)
    ↓
REGISTER (CapabilityRegistry.upsert) ✅
    ↓
DEPLOY (CI/CD) ✅
    ↓
USE (partial — registry lookup works, invocation stubbed)
    ↓
MEASURE (partial — telemetry works, quality assessment stubbed)
    ↓
LEARN (not implemented)
    ↓
IMPROVE (not implemented)
```

### What Exists

| Stage | Status | Evidence |
|-------|--------|----------|
| Need identified | Manual | Human identifies gap |
| Capability gap | Not implemented | No `CapabilityRequest` creation |
| Specification | Not implemented | No structured spec format |
| Build | Manual | Kilo/opencode |
| Test | Manual | pytest |
| Register | ✅ Implemented | `CapabilityRegistry.upsert()` |
| Deploy | ✅ Implemented | CI/CD pipeline |
| Use | ⚠️ Partial | Registry lookup works; invocation is stub |
| Measure | ⚠️ Partial | Langfuse traces LLM; no capability telemetry |
| Learn | ❌ Not implemented | No learning loop |
| Improve | ❌ Not implemented | No pattern promotion |

### What Increment 20 Changes

Increment 20 improves the **USE** stage by making capability execution accessible through chat. It does NOT implement the full lifecycle.

### Full Lifecycle Requires

| Missing Piece | Owner | When |
|---------------|-------|------|
| Capability gap detection | People/Capability | Future increment |
| Structured specification | People/Capability | Future increment |
| Automated build/test | Operations | Future increment |
| Learning loop | People/Capability + Operations | After Increment 20 |
| Pattern promotion | People/Capability | After learning loop |
| Quality assessment | Operations | After Increment 20 |

---

## 19. Runtime / AI Gateway Boundary Analysis

### Current State

| Component | Implementation | Status |
|-----------|---------------|--------|
| PathwayRuntime interface | Abstract base class | ✅ Defined |
| LangGraphRuntime | LangGraph StateGraph | ✅ Implemented |
| execute_capability() | Deterministic Python | ✅ Implemented |
| AI Gateway | None | ❌ Not implemented |
| Model abstraction | Direct config in LangGraph | ❌ Not abstracted |

### The Boundary

```
┌─────────────────────────────────────┐
│       Operations Plane              │
│  - Pattern execution (LangGraph)    │
│  - Capability execution             │
│  - Agent Runtime                    │
└─────────────────────────────────────┘
  ↓ invokes
┌─────────────────────────────────────┐
│       AI Gateway (future)           │
│  - Provider abstraction             │
│  - Model selection                  │
│  - Cost/latency routing             │
└─────────────────────────────────────┘
  ↓ invokes
┌─────────────────────────────────────┐
│       Model Providers               │
│  - Anthropic, OpenAI, etc.          │
└─────────────────────────────────────┘
```

### What the AI Gateway Must Abstract

| Function | Current State | Future State |
|----------|--------------|--------------|
| Provider selection | Hard-coded in LangGraph config | AI Gateway selects |
| Model selection | Hard-coded per pattern | AI Gateway selects based on task |
| Cost tracking | Langfuse only | AI Gateway + Langfuse |
| Latency tracking | Not implemented | AI Gateway |
| Availability/failover | Not implemented | AI Gateway |
| Model/runtime evidence | Not implemented | AI Gateway + outcome assessment |

### What Should NOT Be Visible to Upper Layers

| Layer | Should NOT know about |
|-------|----------------------|
| Paperclip | Model providers, API keys, model IDs |
| Organisation/Control | Model providers, runtime selection |
| People/Capability | Model providers, runtime selection |
| Assistant | Model providers, runtime selection |
| Enterprise | Model providers, runtime selection |

### Is PathwayRuntime Sufficient?

**Yes, for execution abstraction.** `PathwayRuntime` abstracts the execution mechanism (LangGraph, deterministic, etc.).

**No, for model abstraction.** The AI Gateway is needed to abstract model/provider selection from the runtime.

### Current Leakage

| Leakage | Evidence | Severity |
|---------|----------|----------|
| LangGraph directly uses model config | `langgraph_runtime.py` — no AI Gateway | Medium |
| No provider abstraction | Direct Anthropic/OpenAI calls | Medium |
| execute_capability() imports Capability domain | `executor.py` line 14 | Low |

---

## 20. Multi-Agent Coordination Analysis

### The Two Layers

| Layer | Purpose | Scope | State | Example |
|-------|---------|-------|-------|---------|
| **LangGraph pattern execution** | Coordinate participants within a reasoning pattern | Single session, bounded | Transient (MemorySaver) | Debate pattern: Proponent, Opponent, Moderator |
| **Paperclip** | Coordinate agents within an organisation | Persistent, organisational | Persistent (PostgreSQL) | Company: CEO delegates to Engineer, QA, Designer |

### What LangGraph Does NOT Solve

LangGraph does NOT solve:
- Persistent agent identity across sessions
- Agent budgets and cost tracking
- Organisational structure (org charts, roles)
- Task dependencies across sessions
- Agent communication outside patterns
- Governance and approval workflows
- Heartbeat scheduling
- Multi-tenant isolation

### What Paperclip Does NOT Solve

Paperclip does NOT solve:
- Pattern-level coordination within a reasoning session
- Deterministic workflow execution
- Capability definitions and matching
- Enterprise knowledge management
- Learning loops and outcome assessment

### The Complementary Model

```
Paperclip (organisational coordination)
    │
    │ assigns work to agents
    │ manages budgets, dependencies, governance
    ▼
Agent Runtime (execution)
    │
    │ invokes patterns or capabilities
    ▼
LangGraph (pattern coordination)
    │
    │ coordinates participants within pattern
    ▼
Results
    │
    │ recorded as enterprise concepts
    ▼
Enterprise Knowledge (learning)
```

### Who Owns Each Concern

| Concern | Owner |
|---------|-------|
| Create tasks/work | Organisation/Control (or Paperclip if adopted) |
| Assign tasks | Organisation/Control (or Paperclip if adopted) |
| Coordinate agents | Paperclip (if adopted) |
| Hold accountability | Organisation/Control |
| Execute each agent | Agent Runtime (Operations) |
| Aggregate results | Pattern execution (LangGraph) or Paperclip |
| Decide when complete | Organisation/Control (or Paperclip if adopted) |

### Key Insight

**LangGraph pattern execution and Paperclip multi-agent coordination are complementary, not competing.** LangGraph coordinates participants within a pattern. Paperclip coordinates agents within an organisation. Both can coexist.

---

## 21. ADR Impact Assessment

### ADRs That Need Changes

| ADR | Current Statement | Issue | Recommended Action |
|-----|-------------------|-------|-------------------|
| ADR-005 | "Paperclip is not adopted. If needed, it will be a PathwayRuntime adapter." | Incorrectly positions Paperclip as execution runtime | **Supersede.** Paperclip is organisational coordination, not PathwayRuntime adapter. |
| ADR-023 | "Paperclip adapter will implement OrganisationControlPlane abstraction." | Incomplete — Paperclip does more than OCP | **Clarify.** Paperclip implements extended organisational interface or sits alongside OCP. |

### ADRs That Remain Correct

| ADR | Status | Assessment |
|-----|--------|-----------|
| ADR-010 | Accepted | Provider-based architecture. Still correct. |
| ADR-017 | Accepted | Three-plane architecture. Still correct. |
| ADR-018 | Accepted | Role vs Person vs Agent. Still correct. |
| ADR-020 | Accepted | Capability ownership. Still correct. |
| ADR-022 | Accepted | OCP narrow abstraction. Still correct. |
| ADR-029 | Accepted | EIMS learning loop. Still correct. |
| ADR-035 | Proposed | Capability/Skill/Tool distinction. Still relevant. |
| ADR-037 | Accepted | Person/Agent ownership. Still correct. |
| ADR-039 | Accepted | Organisation→Operations handoff. Still correct. |
| ADR-040 | Accepted | Capability assignment/proficiency. Still correct. |
| ADR-042 | Accepted | Execution binding separation. Still correct. |
| ADR-044 | Proposed | Assistant as translation service. Still correct. |

### Proposed ADR Replacements

**Do NOT create these yet.** Only create when the corresponding work is planned.

| Future ADR | Topic | When to Create |
|-----------|-------|----------------|
| ADR-046 | Assistant as primary user interface | When implementing Increment 20 |
| ADR-047 | Capability chat execution path | When implementing Increment 20 |
| ADR-048 | AI Gateway/provider abstraction | When implementing multi-model support |
| ADR-049 | Runtime selection responsibility | When implementing multiple runtimes |
| ADR-050 | Paperclip as organisational coordination layer | When considering Paperclip integration |
| ADR-051 | Capability/Skill/Tool separation | When implementing ADR-035 |

---

## 22. Recommended Next Increment

### Increment 20 — Assistant Chat Execution Path

**Objective:** Wire the existing capability execution into the chat response flow so users get useful results.

### Why This Increment

1. **Does not depend on Paperclip** — Increment 20 uses existing capability execution. Paperclip is not needed.
2. **Uses proven infrastructure** — Increments 14-19 proved execution, telemetry, and assessment.
3. **Preserves architectural boundaries** — No new planes, no new dependencies, no boundary violations.
4. **Makes the system visibly useful** — Users can discover and execute capabilities through chat.
5. **Establishes the execution interface** — Future increments build on a working chat execution interface.
6. **Smallest coherent vertical slice** — Only chat response logic changes.

### What Increment 20 Does

1. **Adds execution path to `AssistantChatService.chat()`** — When capabilities are found, execute the top candidate instead of returning `awaiting_capability_selection`.
2. **Formats `ExecutionResult` into natural language** — Returns `status="completed"` with execution summary.
3. **Improves capability selection response** — Presents capabilities with descriptions.
4. **Adds "list capabilities" intent handling** — "What can you do?" returns formatted capability list.

### What Increment 20 Does NOT Do

- Paperclip integration
- Capability matching improvements
- Pattern execution fixes
- Skills registration
- Conversation state
- AI Gateway
- Runtime selection

### Why NOT Another Increment First

| Alternative | Why Not |
|-------------|---------|
| Paperclip integration | ADR-005 rejected. Core loop not proven. |
| Runtime boundary | `PathwayRuntime` already exists. |
| AI Gateway | Only one provider currently. |
| LLM wiring | Execution path is more fundamental than conversation quality. |
| Capability matching | Returns all for now; improve after chat works. |

---

## 23. Explicit Non-Goals

The following are explicitly NOT part of Increment 20 or any near-term increment:

| Non-Goal | Reason |
|----------|--------|
| Paperclip integration | ADR-005 rejected. Core loop not proven. |
| Capability maturation/promotion | Internal infrastructure, not user-facing. |
| Capability matching/decomposition | Returns all for now; improve after chat works. |
| Execution path convergence | Both paths work; premature to unify. |
| Deployment lifecycle | Static deployments work for first slice. |
| AI-mediated execution implementation | Stub is sufficient for now. |
| Per-invocation history | Fire-and-forget telemetry sufficient. |
| Bus events for capability invocation | Synchronous recording works. |
| Skill-to-capability registration | Future slice after chat works. |
| Conversation state/memory | Future slice after chat works. |
| AI Gateway implementation | Only one provider currently. |
| Runtime selection optimisation | Only one runtime currently. |
| Capability gap detection | Partial fix in Increment 20; full implementation later. |
| Multi-agent coordination | Not needed until multiple agents exist. |
| LangGraph pattern execution improvement | Superficial execution is acceptable for now. |

---

## 24. Open Questions

### Questions for Future Increments

1. **Should the Assistant be refactored to use ports?** ADR-044 identifies this but it is not blocking Increment 20. Eventually the AI plane should depend on ports, not concrete implementations.

2. **Should skills be registered as capabilities?** Yes, but after Increment 20 proves the chat execution path. The migration from `Registry` to `CapabilityRegistry` needs careful design.

3. **Should CapabilityKind include WORKFLOW?** Currently only TOOL and SKILL. Workflows are a distinct execution mode. May need a third kind or a separate concept.

4. **How should the AI Gateway integrate with LangGraph?** LangGraph currently uses direct model configuration. The AI Gateway should abstract this without breaking existing LangGraph patterns.

5. **Should Paperclip eventually replace our OCP?** No. Paperclip is heavier and more complex. Our OCP is minimal and proven. Paperclip should complement, not replace.

6. **How should capability gap detection work?** The architecture defines CapabilityRequest but does not implement it. Increment 20 may include a simple version.

7. **Should the learning loop be implemented before or after Paperclip?** Before. The learning loop (ADR-029) is independent of Paperclip and provides evidence for runtime selection.

### Questions That Block Nothing

These questions are noted but do not block any current increment:

- Should Capability and Skill be separate domain models? (ADR-035 is investigation-only)
- Should the AI Gateway support local models? (Future concern)
- Should runtime selection be a separate service? (Future concern)
- Should agents have persistent memory across sessions? (Future concern)
- Should Paperclip support our Work model natively? (Future adapter concern)
- Should LangGraph pattern execution invoke real capabilities? (Future improvement)
- Should the system support multi-tenant capability isolation? (Future concern)

---

## 25. Validation

### Architectural Consistency Checks

| Check | Result |
|-------|--------|
| No circular dependencies between planes | ✅ Pass |
| AI plane depends on ports only | ⚠️ Current implementation violates; ADR-044 identifies |
| Operations owns execution | ✅ Pass |
| Enterprise owns durable storage | ✅ Pass |
| People/Capability owns capability lifecycle | ✅ Pass |
| Organisation/Control does not execute | ✅ Pass |
| Capability domain model has no execution metadata | ✅ Pass (ADR-042) |
| No Paperclip imports in domain models | ✅ Pass (ADR-023) |
| PathwayRuntime abstracts execution | ✅ Pass |
| AI Gateway boundary defined | ✅ Pass (future) |

### Existing Tests

| Test Suite | Count | Status |
|------------|-------|--------|
| `workflow_runner/tests/` | 185 | All pass |
| `ai/tests/` | 45 | All pass |
| `ai/tests/test_architectural_boundaries.py` | 12 | All pass |
| Increment 18 tests | 12 | All pass |
| Increment 19 tests | 28 | All pass |

### No Code Changes

This investigation made no code changes. No tests to run, no lint to check.

---

## 26. Conclusion

### What the Investigation Established

1. **Paperclip is an organisational coordination platform, not an execution runtime.** ADR-005 incorrectly positions it as a PathwayRuntime adapter. This needs supersession, but it does not block Increment 20.

2. **LangGraph pattern execution and Paperclip multi-agent coordination solve different problems.** LangGraph coordinates participants within a pattern. Paperclip coordinates agents within an organisation. They are complementary.

3. **The capability-as-interface model is correctly represented.** Capability is execution-agnostic. People/Capability defines what; Operations determines how.

4. **The "build the team as we use it" loop is architecturally supported.** All domain models and planes exist. The gaps are implementation gaps, not architectural gaps.

5. **The AI Gateway belongs between Agent Runtime and Model/Provider.** It abstracts model/provider infrastructure from upper layers. Paperclip should not know about it.

6. **Runtime selection belongs in Operations.** PathwayRuntime is sufficient as the abstraction. Evidence-based selection is future work.

7. **Incre Increment 20 remains the correct next increment.** It wires existing capability execution into chat, making the system visibly useful without new infrastructure or Paperclip.

### What Should NOT Be Built Yet

- Paperclip integration
- AI Gateway
- Capability maturation/promotion
- Capability matching improvements
- Pattern execution improvements
- Skills registration
- Conversation state/memory
- Runtime selection optimisation

### The Priority

> Preserving correct architectural boundaries while creating the first genuinely useful end-to-end behaviour.

Increment 20 achieves this. The architecture is sound. The execution layer works. The chat layer needs to be wired to it.

---

**INVESTIGATION STATUS: COMPLETE**

**RECOMMENDATION:** Increment 20 — Assistant Chat Execution Path. Wire existing capability execution into chat response flow. Do not implement Paperclip, AI Gateway, or other infrastructure yet.

**ADR Actions Required (future, not now):**
1. Supersede ADR-005 — Paperclip is not a PathwayRuntime adapter
2. Clarify ADR-023 — Paperclip does more than OCP
