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
