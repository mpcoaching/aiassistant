# Increment 6: Organisational Boundary — Revised Plan

**Status:** Ready for implementation  
**Date:** 2026-08-22  
**Scope:** Establish the organisational boundary with a narrow, non-God OrganisationControlPlane and a CEO that consumes it without capability matching

---

## 1. Three-Plane Architecture (Revised)

### 1.1 Enterprise Plane
- **Owns:** strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning
- **Boundary:** Strategy interpretation, priority setting, escalation thresholds
- **Does NOT:** run operations, execute work, own capabilities

### 1.2 Organisation / Control Plane
- **Owns:** organisational structure, roles, responsibilities, authority, delegation, relationships, allocation of organisational work, coordination between roles, organisational context, people/capability function
- **Boundary:** `OrganisationControlPlane` abstraction
- **Does NOT:** execute operational work, own EIMS, own capability definitions/lifecycle, directly control runtime agents

### 1.3 Operations Plane
- **Owns:** workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work
- **Boundary:** `PathwayRuntime`, `Session`, `PatternStep`
- **Does NOT:** define organisational authority or strategy

---

## 2. Critical Distinction: CEO is Inside the Organisation Plane

The CEO is an organisational ROLE, not the central AI agent.

### CEO Responsibilities
- Receives organisational context
- Interprets enterprise strategy
- Establishes/coordinates priorities
- Allocates work
- Delegates responsibility
- Coordinates organisational roles
- Identifies organisational gaps
- Identifies capability gaps
- Reviews outcomes
- Escalates when necessary

### CEO Does NOT
- Execute operational tasks
- Directly orchestrate runtime agents
- Discover/select capabilities
- Own capability lifecycle
- Own EIMS
- Become the universal request router
- Replace the OrganisationControlPlane
- Become the system's central AI agent

### Correct CEO Flow

```
request / organisational situation
        ↓
enterprise context
        ↓
organisational context
        ↓
CEO role judgement
        ↓
organisational decision
        ↓
work / delegation / escalation
        ↓
appropriate organisational role
        ↓
operations when required
```

**NOT:** `request → CEO → capability matching → capability execution`

---

## 3. Capability Ownership Must Remain Explicit

Capabilities belong to the **People / Capability** function.

### Lifecycle

```
identify → specify → develop/acquire → test → register → assign → operate → measure → learn → retire
```

### Boundaries
- The CEO may **identify** that a capability is missing (as an organisational observation)
- The CEO creates/assigns organisational work to resolve that gap
- The CEO does **NOT** search the `CapabilityRegistry` and select a capability
- `CapabilityMatcher`, `CapabilityRegistry`, `CapabilityRequest`, `CapabilityExecutor` must NOT become CEO-owned services
- The existing capability architecture remains intact

### Interaction Pattern
OrganisationControlPlane **coordinates with** or **invokes** the People/Capability function, but does not own capability lifecycle.

---

## 4. OrganisationControlPlane Interface (Revised)

### 4.1 Must Remain Narrow

```python
class OrganisationControlPlane(ABC):
    @abstractmethod
    def get_role(self, role_id: str) -> Role | None: ...

    @abstractmethod
    def list_roles(self) -> list[Role]: ...

    @abstractmethod
    def get_organisational_context(self, request_context: dict) -> OrgContext: ...

    @abstractmethod
    def assign_work(self, work: Work, assignee: Role | Person | Agent) -> Assignment: ...

    @abstractmethod
    def get_work(self, work_id: str) -> Work | None: ...

    @abstractmethod
    def delegate_authority(self, from_role: Role, to_role: Role, authority: Authority) -> Delegation: ...
```

### 4.2 Explicitly Excluded

The following must NOT be on `OrganisationControlPlane`:

- `find_capability()`
- `match_capability()`
- `execute_capability()`
- `execute_work()`
- `run_agent()`
- `invoke_tool()`

These belong to:
- Capability discovery/matching → People/Capability function
- Execution → Operations plane

### 4.3 Potentially Appropriate

`identify_capability_gap(...)` may be appropriate if it represents an **organisational observation/request**, not a capability lookup.

---

## 5. EIMS Boundary (Explicit)

### 5.1 Current Implementation
- `ConceptStore` / `EnterpriseConcept` is the **current implementation** of an emerging EIMS boundary
- Document it as such; do not declare it the complete EIMS

### 5.2 EIMS Owns
- durable enterprise information
- enterprise concepts
- provenance
- relationships
- institutional knowledge
- learning
- historical organisational knowledge where appropriate

### 5.3 EIMS Does NOT Own
- runtime execution
- orchestration
- role assignment
- authority
- agent control
- workflow execution
- organisational control database

### 5.4 Future Flexibility
- The eventual EIMS may expand beyond ConceptStore
- Preserve architectural flexibility by treating ConceptStore as an implementation, not the complete EIMS
- New EIMS capabilities should be additive

---

## 6. Paperclip Boundary (Preserved)

### 6.1 Conceptually

```
Our domain
    ↓
OrganisationControlPlane
    ↓
Paperclip adapter
    ↓
Paperclip
```

### 6.2 Constraints
- Define the abstraction independently of Paperclip
- Do not introduce Paperclip-specific types into the organisation domain
- Do not import Paperclip into: Role, Work, Authority, OrganisationControlPlane, CEO domain logic
- The abstraction must be independently testable
- Paperclip can subsequently implement that abstraction

### 6.3 Mapping (for future adapter)
- Role definitions → Paperclip Agent/Team
- Work assignments → Paperclip Task
- Coordination → Paperclip meetings

---

## 7. Role Model (Domain Boundaries)

### 7.1 Core Concepts

| Concept | Description | Owner | Notes |
|---|---|---|---|
| **Role** | Abstract position with responsibilities, authority, constraints, information access | Organisation-Control | Template/blueprint; not a person or agent |
| **Person** | Human individual | People/Capability domain | Has identity, employment context |
| **Agent** | Software entity that performs work | Operations plane | Has runtime identity, executes patterns |
| **Capability** | Reusable unit of work (skill, tool, workflow) | People/Capability domain | Has lifecycle |
| **Work** | Instance of assigned effort | Organisation-Control | Has status, assignments, deliverables |
| **Authority** | Permission grant within scope | Organisation-Control | Can be delegated, has constraints |

### 7.2 Distinctions

- **Role ≠ Person:** A Role is an abstract position. A Person occupies a Role.
- **Role ≠ Agent:** A Role defines what is needed. An Agent is a runtime executor that may fulfil a Role.
- **Capability ≠ Agent:** A Capability is what can be done. An Agent is who/what does it.
- **Work ≠ Capability:** Work is a specific assignment. Capability is reusable ability.

### 7.3 Anticipated Roles (Do Not Implement All)

Document these as the intended direction:
- CEO
- Assistant
- Enterprise Architect
- Solution Architect
- Business Analyst / Requirements
- Designer
- Developer
- QA
- People / Capability

A role may be fulfilled by:
- a human Person
- an AI Agent
- potentially a combination of human and agent

---

## 8. Assistant Boundary

### 8.1 Current Relationship
- Chat → Assistant interaction mechanism is retained
- Assistant determines/routes to the appropriate organisational role

### 8.2 Constraints
- Assistant must NOT implicitly become CEO
- Do NOT implement universal routing logic inside `AssistantChatService`
- Assistant is a Role/interface, not an orchestrator

### 8.3 Intended Future Architecture

```
Human
  ↓
Assistant role/interface
  ↓
OrganisationControlPlane
  ↓
appropriate organisational role
  ↓
work/delegation
  ↓
Operations
```

Do NOT implement `Assistant → CEO → everything` in this increment.

---

## 9. Increment 6 Implementation Scope (Revised)

### 9.1 What to Implement

| Component | Description |
|---|---|
| **Role model** | Minimal `Role` record with responsibilities, authority, constraints, information access |
| **Person/Agent distinction** | Define at domain level; minimal implementation |
| **Work model** | Lightweight `Work` record |
| **Assignment model** | `Assignment` record linking Work to assignee |
| **Authority/delegation model** | `Authority` grant and `Delegation` records |
| **OrgContext** | Current actor, current role, reporting relationships, authority scope, organisational relationships |
| **OrganisationControlPlane protocol** | Abstract interface + in-memory implementation |
| **Unit tests** | Tests for all above |
| **CEO consuming the abstraction** | CEOAgent receives OrganisationControlPlane via DI; uses it for role lookup, work assignment, authority checks |
| **Architectural documentation/ADRs** | Required before/during implementation |

### 9.2 What NOT to Implement

| Component | Reason |
|---|---|
| Paperclip adapter | Out of scope — preserve abstraction boundary |
| Complete EIMS | Out of scope — ConceptStore is sufficient |
| Complete People/Capability function | Out of scope — prove the boundary first |
| Capability matching in CEO | **Explicitly excluded** — capability discovery belongs to People/Capability |
| Capability execution in CEO | **Explicitly excluded** — execution belongs to Operations |
| Universal Assistant routing | Out of scope — Assistant changes are out of scope |
| Full CEO orchestration | Out of scope — prove the boundary first |
| All organisational roles | Out of scope — prove the boundary first |
| Agent workforce management | Out of scope — prove the boundary first |

---

## 10. CEO Implementation (Revised)

### 10.1 Constructor

```python
class CEOAgent:
    def __init__(
        self,
        org_plane: OrganisationControlPlane,  # NEW: injected dependency
        reasoning_service: AssistantReasoningService | None = None,
        concept_store: ConceptStore | None = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._org = org_plane  # NEW
        self._reasoning = reasoning_service or AssistantReasoningService()
        self._store = concept_store or ConceptStore()
        self._confidence_threshold = confidence_threshold
```

### 10.2 Orchestrate Method (High-Level)

```python
def orchestrate(self, request: dict[str, Any]) -> dict[str, Any]:
    intent = self._build_intent(request)
    frame = recognise(intent)
    
    # Get organisational context from the plane
    org_context = self._org.get_organisational_context(request)
    
    # CEO role judgement happens here.
    # Possible outcomes:
    # - create organisational work
    # - assign work to a role
    # - delegate authority
    # - identify a capability gap
    # - escalate
    # - review an outcome
    
    # ... decision logic using org_context ...
    
    return result
```

### 10.3 Explicitly Removed from CEO
- `_match_capabilities()` — **must be removed entirely**
- Direct `CapabilityRegistry` instantiation for matching
- Direct capability selection/execution logic
- Universal routing logic

### 10.4 What CEO Can Do Regarding Capabilities
- Identify that a capability gap exists (as an organisational observation)
- Create organisational work to address the gap
- Delegate work to the People/Capability role
- Request capability development through organisational channels

---

## 11. Proposed File Changes

### 11.1 New Files

| File | Purpose |
|---|---|
| `packages/organisation/src/__init__.py` | Package init |
| `packages/organisation/src/organisation_control_plane.py` | Abstract interface + in-memory implementation |
| `packages/organisation/src/role.py` | Role, Person, Agent, Authority, Work, Assignment, OrgContext records |
| `packages/organisation/tests/test_organisation_control_plane.py` | Tests for the abstraction |
| `packages/organisation/tests/test_role_model.py` | Tests for role boundaries |

### 11.2 Modified Files

| File | Change |
|---|---|
| `packages/ai/src/ceo.py` | CEOAgent receives OrganisationControlPlane; uses it for role lookup, work assignment, authority checks; **removes `_match_capabilities()`** |
| `packages/ai/tests/test_ceo.py` | Update tests to mock OrganisationControlPlane; verify no capability matching in CEO |
| `docs/architecture/adr/` | Add new ADRs |

### 11.3 Files NOT Changed

| File | Reason |
|---|---|
| `packages/ai/src/chat.py` | Already reverted; Assistant changes are out of scope |
| `packages/capabilities/` | Capability lifecycle ownership stays in People/Capability domain |
| `packages/concept_store/` | EIMS boundary documented but not expanded |

---

## 12. Architectural Documentation Required

Create/update BEFORE or DURING implementation:

### 12.1 New ADRs

| ADR | Topic |
|---|---|
| ADR-017 | Enterprise / Organisation-Control / Operations three-plane architecture |
| ADR-018 | Role vs Person vs Agent |
| ADR-019 | Authority and delegation boundary |
| ADR-020 | Capability ownership by People/Capability |
| ADR-021 | EIMS boundary and ConceptStore as current implementation |
| ADR-022 | OrganisationControlPlane abstraction (not God service) |
| ADR-023 | Paperclip adapter boundary behind OrganisationControlPlane |
| ADR-024 | CEO as organisational Role, not universal router |
| ADR-025 | Assistant as organisational Role/interface, not implicit CEO |

### 12.2 Update Existing Docs
- `.kilo/context/architecture.md` — add the three-plane model, role model, EIMS boundary, CEO/Assistant roles

### 12.3 Documentation Requirements
Each ADR must explain not only what each component DOES, but what it explicitly MUST NOT do.

---

## 13. Validation Plan

### 13.1 Functional Tests
- All existing 311+ tests continue to pass
- New tests for `OrganisationControlPlane`:
  - Role lookup
  - Role listing
  - Work assignment
  - Work retrieval
  - Authority delegation
  - Organisational context retrieval
- Updated CEO tests:
  - CEO receives OrganisationControlPlane via DI
  - CEO uses org plane for role lookup
  - CEO uses org plane for work assignment
  - CEO uses org plane for authority checks
  - CEO does NOT directly instantiate CapabilityRegistry
  - CEO does NOT invoke `execute_capability()`
  - CEO does NOT contain `_match_capabilities()`

### 13.2 Architectural Boundary Tests (Guardrails)
- `OrganisationControlPlane` does not execute capabilities
- `OrganisationControlPlane` does not own EIMS
- `OrganisationControlPlane` does not perform capability matching
- CEO does not instantiate `CapabilityRegistry`
- CEO does not invoke `execute_capability()`
- CEO does not contain capability matching logic
- CapabilityRegistry remains outside CEO ownership
- ConceptStore remains outside `OrganisationControlPlane` ownership
- No Paperclip imports exist in the domain model
- `chat.py` remains unchanged in this increment

### 13.3 Proof Statements
Increment 6 is successful if we can demonstrate:

```
Enterprise
   │
   │ strategy/context
   ↓
Organisation
   │
   ├── CEO Role
   ├── Assistant Role
   ├── EA Role
   ├── SA Role
   ├── BA Role
   ├── Developer Role
   ├── QA Role
   └── People/Capability Role
   │
   │ work/delegation
   ↓
Operations
   │
   ├── workflows
   ├── agents
   ├── capabilities
   └── tools
```

with:

```
EIMS
   ↕
Enterprise / organisational information
```

and:

```
OrganisationControlPlane
   ↓
[future Paperclip adapter]
```

**Key architectural test:**

> "Can the organisation coordinate itself without the CEO becoming the organisation, and can operations execute work without the organisation becoming the operations engine?"

---

## 14. Open Questions (Resolved)

| Question | Resolution |
|---|---|
| Should `OrgContext` include capability discovery? | **No.** Only role/authority/work context. Capability discovery stays in People/Capability domain. |
| Should `Work` be a first-class aggregate or lightweight record? | **Lightweight record** for now. Full aggregate can come when work tracking is needed. |
| Should `Person` be in scope for Increment 6? | **Define the record, minimal implementation.** Person is needed for authority delegation chains. |
| Should `identify_capability_gap()` be on OrganisationControlPlane? | **Potentially appropriate** if it represents an organisational observation/request, not a capability lookup. Keep it out of scope for Increment 6; add only if CEO needs it. |

---

## 15. Step-by-Step Implementation Tasks

1. **Create ADRs** — Write ADR-017 through ADR-025
2. **Create organisation package** — `packages/organisation/src/__init__.py`
3. **Implement role model** — `role.py` with `Role`, `Person`, `Agent`, `Authority`, `Work`, `Assignment`, `OrgContext`
4. **Implement OrganisationControlPlane** — Abstract interface + in-memory implementation in `organisation_control_plane.py`
5. **Write organisation tests** — Tests for all records and the in-memory implementation
6. **Update CEOAgent** — Inject `OrganisationControlPlane`; remove `_match_capabilities()`; use org plane for role lookup, work assignment, authority checks
7. **Update CEO tests** — Mock `OrganisationControlPlane`; verify boundaries
8. **Run full CI** — Ensure all 311+ tests pass; ruff clean; build passes
9. **Update architecture docs** — `.kilo/context/architecture.md` with three-plane model

---

## 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| OrganisationControlPlane grows into a God service | Architectural boundary tests; explicit exclusion list in interface |
| CEO re-acquires capability matching through backdoor | Remove `_match_capabilities()` entirely; boundary tests verify absence |
| Paperclip influences domain model | No Paperclip imports in domain; abstraction defined independently |
| Increment scope creep | Strictly bounded; out-of-scope items listed explicitly |
| Existing tests break | Run full CI after each change; revert immediately if regressions |
