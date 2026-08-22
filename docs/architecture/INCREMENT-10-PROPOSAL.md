# Increment 10 — Organisational Workflow Proof: Implementation Proposal

## 1. Existing Mechanisms to Reuse

| Mechanism | Location | What it provides |
|---|---|---|
| `Work` | `packages/organisation/src/role.py` | Accountability, coordination, required_capability_ids, acceptance_criteria, outcome, status, dependencies, parent_work_id |
| `Role` | `packages/organisation/src/role.py` | responsibilities, authority_ids, required_capability_ids, reports_to |
| `Person` / `Agent` | `packages/organisation/src/role.py` | Workforce identity references (owned by People/Capability) |
| `Assignment` | `packages/organisation/src/role.py` | Link between Work and assignee |
| `OrganisationControlPlane` | `packages/organisation/src/organisation_control_plane.py` | Role lookup, work assignment, authority delegation, organisational context |
| `InMemoryOrganisationControlPlane` | `packages/organisation/src/organisation_control_plane.py` | Test implementation of OCP |
| `PathwayRuntime` | `packages/bus/src/pathway_runtime.py` | Stable interface for pattern execution (invoke, resume) |
| `PathwayCallRequest` / `PathwayResponse` | `packages/bus/src/pathway_runtime.py` | Execution contract |
| `execute_workflow()` | `packages/workflow_runner/executor.py` | Synchronous workflow execution |
| `ExecutionResult` | `packages/capability_registry/src/executor.py` | Capability execution result model |
| `EnterpriseConcept` / `ConceptStore` | `packages/capability_registry/src/concepts.py` | Durable enterprise knowledge |
| `Session` / `create_session_from_decision()` | `packages/workflow_runner/src/session.py` | Session model for pattern execution |

## 2. Missing Mechanisms

| Missing | Why needed | Proposed approach |
|---|---|---|
| Operational handoff seam | How Work becomes execution | Reuse `PathwayRuntime.invoke()` or `execute_workflow()` as the handoff point |
| Outcome assessment | How execution result becomes organisational outcome | Use `Work.outcome` + `Work.acceptance_criteria` + status transition |
| EIMS learning from work | How completed work becomes durable knowledge | Use `ConceptStore.upsert(EnterpriseConcept)` for significant outcomes |
| Work status lifecycle enforcement | Minimum valid state transitions | Document, don't enforce rigidly — keep it simple |

## 3. Exact Boundary: Organisational vs Operational

```
Organisation/Control plane:
    - Creates Work
    - Sets accountable_role_id, coordinating_role_id
    - Assigns Work via OrganisationControlPlane
    - Reviews outcomes
    - Updates Work.status and Work.outcome
    - Determines if outcome meets acceptance_criteria

Operations plane:
    - Receives Work for execution
    - Creates Session / PathwayCallRequest from Work
    - Invokes PathwayRuntime or execute_workflow()
    - Returns execution result (PathwayResponse / ExecutionResult / StepResult)

Boundary:
    Work.status = ASSIGNED → IN_PROGRESS  (organisational → operational handoff)
    Execution result returned              (operational → organisational feedback)
    Work.status = COMPLETED                (organisational acceptance)
```

## 4. Where Work Changes from Organisational to Operational

The transition point is **assignment + status change to IN_PROGRESS**.

When a coordinating role assigns Work and the assignee begins execution:
- Work transitions from `ASSIGNED` to `IN_PROGRESS`
- This is the organisational handoff to Operations
- Operations does NOT change Work accountability
- Operations returns evidence; Organisation assesses outcome

## 5. Where Execution Outcomes Return to Organisational Responsibility

After execution:
- Operations returns `PathwayResponse` or `ExecutionResult`
- The coordinating role or accountable role assesses the result
- `Work.outcome` is populated with the assessed result
- `Work.status` transitions to `COMPLETED` (accepted) or remains `IN_PROGRESS` / back to `ASSIGNED` (revision needed)
- If the outcome has durable enterprise value, an `EnterpriseConcept` is created in EIMS

## 6. What Becomes EIMS Knowledge

Only evaluated organisational outcomes with durable enterprise value:
- Strategic decisions and rationale
- Significant work outcomes (especially project outcomes)
- Enterprise assets produced by roles
- Capability definitions and maturation
- Governance decisions

NOT EIMS:
- Runtime execution state
- Transient session state
- Intermediate workflow step results
- Pending operational state

## 7. What Remains Transient

- Session state (running context, step outputs)
- Workflow execution state (current step, intermediate results)
- Runtime agent state (in-flight tool calls)
- Human-in-the-loop pending state
- Operations monitoring state (KPIs, alerts)

## 8. Implementation Scope

### In Scope (minimum proof)

1. **Add `execute_work()` method to `OrganisationControlPlane` ABC and `InMemoryOrganisationControlPlane`**
   - Signature: `execute_work(work_id: str, execution_context: dict[str, Any]) -> dict[str, Any]`
   - This is the organisational → operational handoff
   - It retrieves Work, creates a `PathwayCallRequest` or workflow execution call, and returns the execution result
   - It does NOT store Person/Agent records
   - It does NOT perform capability matching
   - It delegates actual execution to existing `PathwayRuntime` or `execute_workflow()`

2. **Add `assess_outcome()` helper**
   - Takes `Work`, `execution_result`, and `acceptance_criteria`
   - Returns assessed outcome dict
   - Does NOT change Work.status directly (caller decides)

3. **Add `record_learning()` helper**
   - Takes `Work` and creates `EnterpriseConcept` in `ConceptStore` if outcome is significant
   - Keeps EIMS write simple and explicit

4. **Add behavioural tests**
   - Test 1: Strategic work flow (CEO decision → C-Suite accountable → PM coordinating → specialist Work)
   - Test 2: BAU work flow (functional manager accountable → operational execution)
   - Test 3: Work decomposition (parent/child)
   - Test 4: Work dependencies
   - Test 5: Capability declaration (Work.required_capability_ids without matching)
   - Test 6: Capability portability
   - Test 7: Operational handoff (Work → execution → result)
   - Test 8: Outcome assessment (execution result ≠ automatic acceptance)
   - Test 9: EIMS learning (completed work → EnterpriseConcept)
   - Test 10: CEO boundary (no capability matching, no execution, no PM coordination)

### Out of Scope

- Full People/Capability implementation
- CEO/COO/PM role implementations
- Paperclip adapter
- EIMS expansion
- Capability matching/execution in organisation
- Universal routing
- Assistant redesign
- Workflow engine changes
- LangGraph runtime changes

## 9. Migration/Compatibility

- All changes are additive to existing `OrganisationControlPlane` ABC
- `InMemoryOrganisationControlPlane` gains new methods but retains existing ones
- `Work` model unchanged (already has required fields)
- Existing tests unchanged
- New methods can be mocked in existing CEO/chat tests if needed

## 10. Proposed Interface

```python
class OrganisationControlPlane(ABC):
    # Existing methods...
    def get_role(self, role_id: str) -> Role | None: ...
    def list_roles(self) -> list[Role]: ...
    def get_organisational_context(self, request_context: dict[str, Any]) -> OrgContext: ...
    def assign_work(self, work: Work, assignee: Role | Person | Agent) -> Assignment: ...
    def get_work(self, work_id: str) -> Work | None: ...
    def delegate_authority(self, from_role: Role, to_role: Role, authority: Authority) -> Delegation: ...

    # New: operational handoff
    def execute_work(self, work_id: str, execution_context: dict[str, Any]) -> dict[str, Any]: ...
```

```python
# Helper functions (not on OCP, to keep OCP narrow)
def assess_work_outcome(work: Work, execution_result: dict[str, Any]) -> dict[str, Any]:
    """Assess execution result against acceptance_criteria."""
    ...

def record_work_learning(work: Work, store: ConceptStore) -> EnterpriseConcept | None:
    """Record durable learning from completed work, if significant."""
    ...
```

## 11. Test Strategy

- Unit tests for `execute_work()` using `InMemoryOrganisationControlPlane`
- Mock `PathwayRuntime` or `execute_workflow` to avoid real execution
- Test Work status transitions: ASSIGNED → IN_PROGRESS → COMPLETED
- Test that execution result does not automatically set Work.outcome
- Test that `assess_work_outcome()` produces assessed outcome
- Test that `record_work_learning()` creates EnterpriseConcept only for significant outcomes
- Test CEO boundary: CEO does not call `execute_work()`, does not match capabilities
- Test OCP boundary: OCP does not execute capabilities, does not become PM/COO

## 12. Architectural Guardrails to Test

- OrganisationControlPlane != Operations
- OrganisationControlPlane != People/Capability
- OrganisationControlPlane != EIMS
- CEO != OrganisationControlPlane
- CEO != COO
- CEO != ProjectManager
- Work != Capability
- Work != Workflow
- Role != Person
- Role != Agent
- Capability != Agent
- ExecutionResult != OrganisationalOutcome
