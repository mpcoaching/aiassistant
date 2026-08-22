# Increment 11 — Organisation → Operations Handoff: Investigation Report

## Executive Summary

`OrganisationControlPlane.execute_work()` is a **boundary violation**. It makes the Organisation/Control plane aware of and responsible for operational execution. The fix is to remove execution capability from OCP and replace it with an implicit state-transition handoff.

**Current state:** OCP imports `PathwayRuntime`, creates `PathwayCallRequest`, invokes `PathwayRuntime.invoke()`, and returns operational results. This crosses the four-plane boundary.

**Recommended state:** OCP marks Work as ready. Operations executes Work via its own entry points (`PathwayRuntime`, `execute_workflow()`, etc.). The handoff is a Work state transition, not an OCP method call.

---

## 1. Current Execution Call Graph

```
OrganisationControlPlane.execute_work(work_id, execution_context)
    ↓
InMemoryOrganisationControlPlane.execute_work()
    ↓
self.get_work(work_id)                    # organisational lookup ✓
    ↓
from pathway_runtime import PathwayCallRequest, PathwayRuntime  # ✗ Operations import
    ↓
request = PathwayCallRequest(...)         # ✗ operational contract creation
    ↓
self._runtime.invoke(request)             # ✗ operational execution
    ↓
return {status, outputs, artifacts}       # ✗ operational result in OCP
```

## 2. Current Ownership of Each Step

| Step | Current Owner | Correct Owner | Violation? |
|---|---|---|---|
| Work lookup | OrganisationControlPlane | Organisation/Control | No |
| Work status update | OrganisationControlPlane | Organisation/Control | No |
| Creating execution request | OrganisationControlPlane | Operations | **YES** |
| Invoking runtime | OrganisationControlPlane | Operations | **YES** |
| Returning execution result | OrganisationControlPlane | Operations → Organisation | **YES** |

## 3. Does execute_work() Violate the Architecture?

**Yes.** Specifically:

1. **OCP imports from `pathway_runtime` package** — `pathway_runtime` is an Operations substrate (`packages/bus/src/pathway_runtime.py`). Organisation/Control must not depend on Operations internals.

2. **OCP creates `PathwayCallRequest`** — this is an operational execution contract defined by the Operations plane. Organisation/Control should not construct operational contracts.

3. **OCP invokes `PathwayRuntime.invoke()`** — this is actual operational execution. Organisation/Control should not execute operational work.

4. **OCP knows about `PathwayStatus`** — operational state is an Operations concern.

5. **Method name is `execute_work()`** — the name itself signals execution, which belongs to Operations.

## 4. Options Considered

### Option A — Current model (REJECTED)

`OrganisationControlPlane.execute_work(work)`

- OCP directly invokes operational execution
- OCP imports and depends on `PathwayRuntime`
- OCP knows HOW Work executes
- **Verdict: Boundary violation. OCP becomes an execution facade.**

### Option B — Explicit Operations boundary (REJECTED)

`OperationsRuntime.execute(work)` — new abstraction on Operations side

- Clean boundary: Operations owns execution interface
- But creates a new abstraction that duplicates `PathwayRuntime`
- OCP would still need to call it, creating coupling
- **Verdict: Unnecessary abstraction. Existing `PathwayRuntime` is sufficient.**

### Option C — Event/handoff model (ACCEPTED)

```
Organisation
    ↓
Work becomes READY (status transition)
    ↓
Operations observes/accepts Work
    ↓
execution
```

- OCP provides `mark_work_ready(work_id)` — changes status, no execution
- Operations has its own entry point to execute Work
- Handoff is implicit through Work state
- OCP is ignorant of HOW Work executes
- **Verdict: Cleanest boundary. Minimal new code.**

### Option D — Existing runtime mechanism (ACCEPTED)

Reuse existing `PathwayRuntime` and `execute_workflow()` directly from Operations consumers (e.g., `AssistantChatService`, workflow runner, future PM services).

- No new abstractions needed
- Operations already has execution entry points
- Organisation just marks Work ready
- **Verdict: Preferred. Leverages existing infrastructure.**

## 5. Recommended Boundary

### Organisation/Control Plane

Provides mechanisms for:
- Role lookup
- Work creation/assignment
- Authority/delegation
- Organisational context
- **Marking Work as ready for execution** (`mark_work_ready()` or status update)

Does NOT provide:
- Operational execution
- Runtime invocation
- Capability matching
- Workflow execution

### Operations Plane

Provides mechanisms for:
- `PathwayRuntime.invoke()` — pattern execution
- `execute_workflow()` — workflow execution
- Session management
- Agent execution
- Tool invocation
- Accepting Work from Organisation for execution

### The Handoff

```
OrganisationControlPlane:
    work = get_work(work_id)
    work.status = "ready"  # or ASSIGNED with additional flag
    update_work(work)

Operations:
    # Somewhere in Operations code (AssistantChatService, workflow runner, etc.)
    ready_work = ocp.get_work_by_status("ready")
    for work in ready_work:
        result = runtime.invoke(build_request_from_work(work))
        # Return result to Organisation for outcome assessment
```

The key insight: **Operations pulls Work, Organisation does not push execution.**

## 6. Exact Interface Changes

### Remove from OrganisationControlPlane

```python
# REMOVE these imports:
from pathway_runtime import PathwayCallRequest, PathwayRuntime

# REMOVE this method:
def execute_work(self, work_id: str, execution_context: dict[str, Any]) -> dict[str, Any]:
    ...
```

### Remove from InMemoryOrganisationControlPlane

```python
# REMOVE:
self._runtime = runtime  # constructor parameter

# REMOVE:
def execute_work(self, work_id: str, execution_context: dict[str, Any]) -> dict[str, Any]:
    ...
```

### Add to OrganisationControlPlane (if needed)

```python
def mark_work_ready(self, work_id: str) -> Work | None:
    """Mark organisational Work as ready for operational execution.
    
    This is a status transition only. It does NOT execute the Work.
    Operations is responsible for picking up ready Work and executing it.
    """
    work = self.get_work(work_id)
    if work is not None:
        work.status = WorkStatus.IN_PROGRESS  # or a new READY status
        work.updated_at = datetime.now(UTC)
        self._work[work.id] = work
    return work
```

Actually, `WorkStatus.IN_PROGRESS` already exists and semantically means "execution has begun." This is the right status for the handoff. No new status needed.

### Keep in outcome.py

`assess_work_outcome()` and `record_work_learning()` remain as organisational helpers. They assess execution results and record durable learning. These are organisational concerns, not operational concerns.

## 7. Impact on Increment 10 Tests

### Tests to remove/modify:

1. **`test_execute_work_without_runtime_returns_simulated_result`** — REMOVE (tests execution on OCP)
2. **`test_execute_work_with_runtime_delegates_to_runtime`** — REMOVE (tests execution on OCP)
3. **`test_execute_work_missing_work_returns_failure`** — REMOVE (tests execution on OCP)
4. **`test_operational_handoff_work_to_execution`** — MODIFY to test status transition only
5. **`test_architectural_boundary_no_forbidden_methods`** — REMOVE `execute_work` from forbidden list (it won't exist anymore), ADD `mark_work_ready` to allowed methods

### Tests to add:

1. **`test_mark_work_ready_transitions_status`** — OCP can mark Work as IN_PROGRESS (ready for execution)
2. **`test_operations_executes_work_independently`** — Operations can execute Work via its own entry points without OCP involvement
3. **`test_ocp_ignorant_of_execution_mechanism`** — OCP does not import PathwayRuntime

### Tests to keep:

- All BAU and strategic project accountability tests
- All decomposition and dependency tests
- All capability declaration and portability tests
- All outcome assessment tests
- All EIMS learning tests
- All CEO boundary tests
- All architectural boundary tests (with updates)

## 8. Impact on Future Paperclip Integration

Paperclip maps to OrganisationControlPlane for organisational mechanisms (role representation, work assignment, coordination). Paperclip does NOT map to operational execution.

Removing `execute_work()` from OCP makes the Paperclip boundary cleaner:
- Paperclip implements OCP mechanisms (roles, work assignment, authority)
- Paperclip does NOT implement execution
- Execution remains in Operations

This aligns with the existing Paperclip mapping in the architecture docs.

## 9. Impact on Operations

Operations already has execution entry points:
- `PathwayRuntime.invoke()` — pattern execution
- `execute_workflow()` — workflow execution
- `PatternRuntime.invoke_step()` — capability execution
- `AssistantChatService` — already invokes runtime directly

No changes needed in Operations. Operations will simply observe Work status and execute when Work is ready.

## 10. Deferred Concerns

1. **How does Operations know when Work is ready?** 
   - Deferred to future increment. Options: polling, events, explicit handoff API on Operations side.
   - For now, the architecture proves the boundary; implementation can choose the trigger mechanism.

2. **Does Work need a "ready" status?**
   - `WorkStatus.IN_PROGRESS` already means execution has begun. This is sufficient for the handoff.
   - If a separate "ready" state is needed later, it can be added without architectural change.

3. **Who updates Work.status after execution?**
   - The organisational layer (coordinating role or accountable role) assesses outcome and updates Work.status.
   - This is already modelled in `outcome.py`.

4. **What about the `outcome` field on Work?**
   - `Work.outcome` is populated by the organisational layer after outcome assessment.
   - Operations returns execution result; Organisation decides what it means.

## 11. Key Architectural Finding

The current `execute_work()` method conflates two distinct responsibilities:

1. **Handoff** — Organisation saying "this Work is ready for execution" (legitimate OCP concern)
2. **Execution** — actually running the Work through a runtime (NOT an OCP concern)

These must be separated. The handoff is a status transition or readiness signal. The execution belongs to Operations.

The corrected architecture:

```
OrganisationControlPlane:
    create_work() → Work
    assign_work() → Assignment
    mark_work_ready() → Work (status = IN_PROGRESS)
    get_work() → Work
    assess_outcome() → assessed outcome (via outcome.py helpers)

Operations:
    observe_ready_work() → Work[]
    execute(work) → ExecutionResult
    return result to Organisation

Organisation:
    assess(result) → accepted/rejected
    update Work.outcome and Work.status
    record_learning() if significant
```

## 12. Conclusion

`OrganisationControlPlane.execute_work()` is a boundary violation that must be removed. The replacement is a simple status transition (`mark_work_ready` or equivalent) that makes Work available for Operations execution. Operations executes Work through its own existing entry points (`PathwayRuntime`, `execute_workflow()`). The handoff is implicit through Work state, not explicit through OCP method calls.

This correction makes the Organisation → Operations boundary genuinely clean: OCP is completely ignorant of HOW Work executes, and Operations executes Work without knowing organisational structure or authority delegation.
