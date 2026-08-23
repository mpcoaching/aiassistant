# Increment 18 — Investigation

## 1. Executive Conclusion

The single most important architectural finding is:

**Invocation telemetry is dead code, and until it is wired, capability maturation cannot be implemented.**

`ConceptStore.record_invocation()` and `CapabilityRegistry.promote()` both exist in the codebase but are never called after capability execution. The execution path produces `ExecutionResult.telemetry` dicts that are returned to the caller and then discarded. This means:

1. No capability ever records an invocation
2. No capability ever matures
3. The learning loop defined in ADR-029 is entirely unimplemented
4. Any maturation logic implemented now would have no input data

The next architectural seam is **operational invocation telemetry recording** — a thin, explicit concern that translates execution outcomes into durable EIMS events. This is the smallest increment that makes subsequent maturation possible without creating another architectural correction later.

---

## 2. Current Architecture (As Implemented)

### Planes and Ownership

| Plane | Owns | Does NOT own |
|-------|------|--------------|
| **AI** | Intent recognition, strategy selection, AssistantChatService (translation) | Capability discovery, execution, session creation, EIMS access |
| **People/Capability** | Capability definitions, CapabilityRegistry, CapabilityMatcher, CapabilityAssignment, CapabilityProficiency, ExecutionAuthorisationPort | Work, execution, deployment, EIMS |
| **Operations** | CapabilityDeployment, DeploymentResolver, PatternRuntime, Session, execute_capability(), authorisation enforcement | Capability definitions, lifecycle, matching |
| **Enterprise/EIMS** | ConceptStore, EnterpriseConcept, durable knowledge | Runtime execution, capability lifecycle |

### Current Execution Paths

There are **two parallel execution paths** that have not been unified:

**Path A: Pattern execution**
```
AssistantChatService.chat()
  → PatternExecutionPort.execute_pattern()
    → PatternExecutionAdapter
      → LangGraphRuntime.invoke()
        → PatternRuntime.invoke_step(capability_id, inputs, deployment, actor_context)
          → _check_authorisation()
          → _invoke_with_deployment()
            → _invoke_tier2_deployment() or _invoke_tier3_deployment()
```

**Path B: Direct capability execution**
```
AssistantChatService.execute_selected_capability()
  → CapabilityExecutionPort.execute()
    → CapabilityExecutionAdapter.execute()
      → _check_authorisation()
      → deployment_factory(capability)
        → DeploymentResolver.resolve()
      → execute_capability(capability, context, deployment)
```

Neither path records invocation telemetry or triggers maturation.

---

## 3. End-to-End Execution Trace

### Current Trace (What Actually Happens)

```
User request (HTTP)
  │
  ▼
API (/assistant/chat)
  │
  ▼
create_application() [composition root]
  │
  ▼
AssistantChatService.chat(request)
  │
  ├─► Intent(raw=request.message)                    ← AI plane
  ├─► recognise(intent) → ProblemFrame                ← AI plane
  │
  ├─► EnterpriseInformationPort.find_previous_solutions()  ← Enterprise plane
  │     │
  │     └─► [HIT] → return "awaiting_confirmation"   ← EXITS HERE (cache reuse)
  │
  ├─► CapabilityDiscoveryPort.find_capabilities()     ← People/Capability plane
  │     │
  │     └─► CapabilityDiscoveryAdapter
  │           ├─► CapabilityRegistry.list()
  │           └─► HumanSelectionMatcher.match() → ALL capabilities
  │
  ├─► [candidates found] → return "awaiting_capability_selection"  ← EXITS HERE (human picks)
  │
  ├─► AssistantReasoningService.decide(intent)        ← AI plane
  │
  ├─► SessionFactoryPort.create_session()             ← Operations plane
  │     └─► SessionFactoryAdapter
  │           └─► create_session_from_decision() → Session
  │
  ├─► PatternExecutionPort.execute_pattern()          ← Operations plane
  │     │
  │     └─► PatternExecutionAdapter
  │           └─► LangGraphRuntime.invoke()
  │                 └─► PatternRuntime.invoke_step()
  │                       ├─► _check_authorisation() ← People/Capability rules, enforced in Operations
  │                       ├─► DeploymentResolver.resolve() ← Operations
  │                       └─► _invoke_with_deployment()
  │                             ├─► [COMPILED] → execute_capability()
  │                             ├─► [AI_MEDIATED] → composed prompt string
  │                             └─► [TIER3_BUS] → simulated reply
  │
  ├─► EnterpriseInformationPort.record_solution()     ← Enterprise plane (solution reuse, NOT invocation)
  │
  └─► return ChatResponse
```

### What Does NOT Happen

| Step | Status | Gap |
|------|--------|-----|
| Invocation telemetry recorded | **MISSING** | `record_invocation()` exists but is never called |
| Capability maturation | **MISSING** | `promote()` exists but is never called |
| Outcome assessment | **MISSING** | No evaluation of execution success/failure |
| Learning loop | **MISSING** | No translation from execution to domain state |
| Automated capability matching | **DEFERRED** | Human selection is current requirement |
| Deployment versioning/lifecycle | **NOT MODELLED** | Deployment is a static record |

---

## 4. Responsibility Map

| Concern | Current Owner | Correct Owner | Status |
|---------|---------------|---------------|--------|
| Intent recognition | AI (`assistant.py`) | AI | ✅ Correct |
| Strategy selection | AI (`assistant.py`) | AI | ✅ Correct |
| Previous solution lookup | Enterprise (`EnterpriseInformationPort`) | Enterprise | ✅ Correct |
| Solution recording | Enterprise (`EnterpriseInformationPort`) | Enterprise | ✅ Correct |
| Capability catalog | People/Capability (`CapabilityRegistry`) | People/Capability | ✅ Correct |
| Capability matching | People/Capability (`HumanSelectionMatcher`) | People/Capability | ⚠️ Stub — returns all |
| Capability selection | AI (`_capability_selection_response`) | AI (presentation) | ✅ Correct |
| Authorisation rules | People/Capability (`InMemoryExecutionAuthorisationPort`) | People/Capability | ✅ Correct |
| Authorisation enforcement | Operations (`PatternRuntime`, `CapabilityExecutionAdapter`) | Operations | ✅ Correct |
| Deployment resolution | Operations (`DeploymentResolver`) | Operations | ✅ Correct |
| Deployment records | Operations (`CapabilityDeployment`) | Operations | ✅ Correct |
| Session creation | Operations (`SessionFactoryAdapter`) | Operations | ✅ Correct |
| Pattern orchestration | Operations (`PatternRuntime`) | Operations | ✅ Correct |
| Capability execution | Operations (`execute_capability()`) | Operations | ✅ Correct |
| **Invocation telemetry** | **NONE — dead code** | **Operations (record) → Enterprise (store)** | ❌ **MISSING** |
| **Maturation/learning** | **NONE — dead code** | **People/Capability (decide) → Enterprise (store)** | ❌ **MISSING** |
| Outcome assessment | NONE | Organisation/Control | ❌ **MISSING** |

---

## 5. Architectural Gaps

### Critical

| Gap | Why It Matters |
|-----|---------------|
| **Invocation telemetry not recorded** | Without invocation data, maturation has no input. `record_invocation()` and `promote()` are dead code. The learning loop cannot start. |

### High

| Gap | Why It Matters |
|-----|---------------|
| **Maturation not triggered** | Capabilities never transition from DRAFT → ACTIVE. The lifecycle is frozen. |
| **No outcome assessment** | Execution results are returned but never evaluated. The system cannot distinguish success from failure at the domain level. |

### Medium

| Gap | Why It Matters |
|-----|---------------|
| **Discovery and matching collapsed** | `CapabilityDiscoveryAdapter.find_capabilities()` calls both `list()` and `match()` internally. The port exposes a single method for two concerns. |
| **PatternRuntime has dual responsibility** | `invoke_step()` handles both pattern orchestration AND capability execution. These should converge through `CapabilityExecutionPort`. |
| **Composition root has orphan instantiation** | `PatternRuntime(...)` is called at line 98 but the return value is discarded. The created instance is not wired into anything. |

### Low

| Gap | Why It Matters |
|-----|---------------|
| **Deployment has no lifecycle** | `DeploymentResolver` resolves static records. No versioning, status, or deprecation. |
| **No capability invocation events** | The bus has workflow lifecycle events but no `CapabilityInvoked`/`CapabilitySucceeded`/`CapabilityFailed`. |
| **AI-mediated execution is a stub** | Returns a composed prompt string. No actual LLM integration. |

---

## 6. Candidate Next Increments

### Candidate A: Invocation Telemetry Recording (Recommended)

**Objective:** Wire execution outcomes to `ConceptStore.record_invocation()` through an explicit `InvocationRecorder` port.

**Architectural seam:** Operations produces operational events → Enterprise stores them → People/Capability consumes them for maturation.

**Files/components affected:**
- `packages/contracts/src/invocation_recorder.py` — new port interface
- `packages/workflow_runner/src/adapters/invocation_recorder_adapter.py` — new adapter
- `packages/capability_registry/src/adapters/` — no changes
- `packages/workflow_runner/src/runtime.py` — call recorder after execution
- `packages/workflow_runner/src/executor.py` — call recorder after execution
- `packages/workflow_runner/src/composition.py` — wire recorder
- Tests: new unit + integration tests

**Dependencies:** Increment 17 (authorisation + deployment resolution) ✅ complete.

**Risks:**
- Low: thin adapter, no new domain logic
- `record_invocation()` already exists in ConceptStore
- `ExecutionResult.telemetry` already carries outcome data

**What it enables:**
- Capability maturation becomes possible
- Maturation history gets real data
- Subsequent increments can implement promotion logic
- Bus events can be added later without changing the recorder contract

**What it deliberately does NOT implement:**
- Maturation logic
- Outcome assessment
- Capability promotion
- Bus events

---

### Candidate B: Capability Discovery/Matching Decomposition

**Objective:** Split `CapabilityDiscoveryPort` into `list_capabilities()` and `match_capabilities()`.

**Architectural seam:** Discovery (catalog query) vs Matching (semantic/rule-based filtering).

**Files/components affected:**
- `packages/contracts/src/capability_discovery.py` — port split
- `packages/capability_registry/src/adapters/capability_discovery_adapter.py` — refactor
- `packages/ai/src/chat.py` — update call sites
- Tests: update all port consumers

**Dependencies:** None beyond Increment 17.

**Risks:**
- Medium: touches a port interface used by AI plane
- Requires updating all test fixtures
- Does not enable any new functionality — matching is still a stub

**Why it should wait:**
- `HumanSelectionMatcher` returns all capabilities regardless. Splitting the port before matching has real logic is premature.
- The current combined port is not causing harm.
- Better to implement matching first, then split if the interface proves insufficient.

---

### Candidate C: PatternRuntime / execute_capability() Convergence

**Objective:** Unify the two execution paths so both pattern execution and direct capability execution go through `CapabilityExecutionPort`.

**Architectural seam:** Single authoritative execution path.

**Files/components affected:**
- `packages/workflow_runner/src/runtime.py` — delegate to `CapabilityExecutionAdapter`
- `packages/workflow_runner/src/executor.py` — possibly absorb into adapter
- `packages/contracts/src/capability_execution.py` — no change
- Tests: update PatternRuntime tests

**Dependencies:** Increment 17 (authorisation + deployment) ✅ complete.

**Risks:**
- Medium: changes runtime dispatch semantics
- PatternRuntime currently handles transport (Tier 2/3) directly; moving this to `execute_capability()` changes the execution model
- `PatternRuntime` currently has no `CapabilityExecutionPort` dependency

**Why it should wait:**
- Both paths work correctly today
- Convergence is valuable but not blocking telemetry or maturation
- Better to record telemetry first, then unify execution paths

---

## 7. Recommended Increment 18

### Invocation Telemetry Recording

This is the smallest defensible increment because:

1. **It is genuinely missing.** Telemetry is not a "nice to have" — it is the input for maturation, which is the next architectural seam after this one.
2. **It is thin.** `record_invocation()` already exists in ConceptStore. `ExecutionResult.telemetry` already carries outcome data. The adapter is a simple translation.
3. **It has clear ownership.** Operations records the event; Enterprise stores it; People/Capability will later consume it.
4. **It does not change any existing behaviour.** It adds a side-effect after successful/failed execution.
5. **It unblocks maturation.** Without invocation data, maturation cannot be implemented cleanly.

### Why Candidate B (Discovery/Matching Split) Should Wait

Splitting the port before matching has real logic is premature. The current combined `find_capabilities()` works correctly with `HumanSelectionMatcher`. A port split without a matching implementation change is refactoring without benefit.

### Why Candidate C (Execution Convergence) Should Wait

Both execution paths are currently functional. Convergence is valuable but would be complicated by the fact that `PatternRuntime` handles transport dispatch (Tier 2 vs Tier 3) which `execute_capability()` does not. Better to record telemetry in both paths first, then unify.

---

## 8. Exact Implementation Scope

### MUST IMPLEMENT

1. **`InvocationRecorder` port** (`packages/contracts/src/invocation_recorder.py`)
   - Single method: `record_invocation(capability_id: str, result: ExecutionResult, actor_context: dict[str, Any] | None) -> None`
   - Does NOT return a value (fire-and-forget operational event)

2. **`InvocationRecorderAdapter`** (`packages/workflow_runner/src/adapters/invocation_recorder_adapter.py`)
   - Implements `InvocationRecorder`
   - Translates `ExecutionResult` into `ConceptStore.record_invocation()` call
   - Maps `result.telemetry` outcome to `"success"` / `"failure"` string

3. **Wire into execution paths**
   - `PatternRuntime.invoke_step()` — call recorder after `_invoke_with_deployment()` returns
   - `CapabilityExecutionAdapter.execute()` — call recorder after `execute_capability()` returns
   - Both paths must record, regardless of success or failure

4. **Wire through composition root**
   - Add `InvocationRecorder` to `create_application()`
   - Pass to `PatternRuntime` and `CapabilityExecutionAdapter`

5. **Tests**
   - Unit test: adapter translates `ExecutionResult` to `record_invocation()` call
   - Unit test: adapter handles missing outcome (defaults to `"success"`)
   - Integration test: `PatternRuntime.invoke_step()` records invocation
   - Integration test: `CapabilityExecutionAdapter.execute()` records invocation
   - Integration test: failed execution still records invocation

### MUST NOT IMPLEMENT

- Maturation logic
- Capability promotion
- Outcome assessment
- Bus events for capability invocation
- `CapabilityRegistry.promote()` integration
- Automated capability matching
- Execution path convergence
- Deployment lifecycle
- AI-mediated execution implementation

### TESTS REQUIRED

| Test | Location | Purpose |
|------|----------|---------|
| `test_invocation_recorder_adapter.py` | `packages/workflow_runner/tests/` | Adapter translates result to ConceptStore call |
| `test_increment18_integration.py` | `packages/workflow_runner/tests/` | PatternRuntime records invocation |
| `test_increment18_integration.py` | `packages/workflow_runner/tests/` | CapabilityExecutionAdapter records invocation |
| `test_increment18_integration.py` | `packages/workflow_runner/tests/` | Failed execution still records invocation |

### ARCHITECTURAL GUARDRAILS REQUIRED

1. **AI plane remains port-only** — no new imports from domain implementations
2. **Operations records, Enterprise stores** — adapter translates, does not decide maturation
3. **No circular dependencies** — `InvocationRecorder` port in `contracts`; adapter in `workflow_runner`
4. **Fire-and-forget semantics** — recorder does not block execution on persistence failure (consistent with existing `EventBus._write_fallback` pattern)
5. **Existing architectural boundary tests must pass** — `test_architectural_boundaries.py` must remain green

---

## 9. ADR Recommendations

### ADR-050: Invocation Telemetry Recording (Recommended)

**Subject:** Operational capability invocation events as input to maturation

**Rationale:** `ConceptStore.record_invocation()` exists but is never called. `ExecutionResult.telemetry` is populated but discarded. The architecture defines a learning loop (ADR-029) but the first step — recording operational events — is unimplemented.

**Decision needed:**
- Define `InvocationRecorder` port in `contracts`
- Operations adapter translates `ExecutionResult` → `ConceptStore.record_invocation()`
- Recorder is called after every execution (both PatternRuntime and CapabilityExecutionAdapter paths)
- Recorder is fire-and-forget; does not block execution on persistence failure

**Evidence:** `concepts.py:109-121` has `record_invocation()`; `executor.py:72-81` populates `telemetry`; neither is connected to the other.

---

## 10. Validation Strategy

### Commands

```bash
# Exact Woodpecker-equivalent lint
ruff check packages/ --output-format=github

# Exact Woodpecker-equivalent test loop
for pkg in packages/*/; do
  if [ -d "$pkg/tests" ] && [ -f "$pkg/pyproject.toml" ]; then
    echo "Testing $pkg"
    cd "$pkg"
    if [ "$(basename "$pkg")" = "workflow_runner" ]; then
      pytest tests/ -v --tb=short --ignore=tests/test_phase23.py 2>&1 | tail -5
    else
      pytest tests/ -v --tb=short 2>&1 | tail -5
    fi
    cd ../..
  fi
done

# Architectural boundary tests
pytest packages/ai/tests/test_architectural_boundaries.py -v

# Increment 18 specific tests
pytest packages/workflow_runner/tests/test_invocation_recorder_adapter.py -v
pytest packages/workflow_runner/tests/test_increment18_integration.py -v
```

### Expected Results

- `ruff check` → clean
- All existing tests → pass (308+)
- Architectural boundary tests → 12 passed
- Increment 18 tests → new tests pass

---

## 11. Architectural Invariants

Increment 18 must preserve:

1. **AI plane depends on ports only** — no new imports from domain implementations
2. **Operations records operational events** — does not decide maturation
3. **Enterprise stores durable knowledge** — does not decide what to store
4. **People/Capability owns maturation decisions** — does not implement them yet
5. **No circular dependencies** — new port in `contracts`, adapter in `workflow_runner`
6. **Fire-and-forget telemetry** — does not block or alter execution result
7. **Both execution paths record** — PatternRuntime and CapabilityExecutionAdapter both call recorder
8. **Composition root wires everything** — no new module-level instantiation
9. **No new cross-plane dependencies** — all new code in existing planes
10. **Existing tests pass** — no regressions in 308-test baseline

---

**INVESTIGATION STATUS: COMPLETE**

**RECOMMENDATION:** Increment 18 should implement invocation telemetry recording as the smallest defensible next increment. This creates the data flow that makes subsequent maturation possible without creating another architectural correction.
