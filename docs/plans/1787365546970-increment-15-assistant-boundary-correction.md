# Increment 15 — Assistant Boundary Correction: Implementation Plan

## Goal

Prove the corrected Assistant boundary by introducing port interfaces, removing direct cross-plane dependencies from the AI plane, and adding architectural guardrail tests. Resolve the failing test `test_chat_service_returns_previous_solution` by addressing the underlying architectural defect (capability matching inside Assistant), not by changing the assertion.

## Architectural Decisions

- **ADR-044**: Assistant is an application-layer translation service, not a domain service.
- **ADR-045**: Assistant depends on port interfaces; implementations live in respective planes.

## Responsibilities by Plane

### AI Plane (`packages/ai/`)
- Owns: intent recognition, strategy selection, reasoning, Assistant port interface
- Does NOT own: capability matching, EIMS access, session creation, runtime invocation, execution, Work creation

### Application Layer (ports in `packages/ai/src/ports/`)
- Owns: translation interfaces between Assistant and domain planes
- Does NOT own: any domain logic or implementations

### People/Capability Plane
- Will implement: `CapabilityDiscoveryPort` (future increment)
- Does NOT change in this increment

### Operations Plane
- Will implement: `CapabilityExecutionPort`, `SessionFactoryPort` (future increment)
- Does NOT change in this increment

### Enterprise/EIMS Plane
- Will implement: `EnterpriseInformationPort` (future increment)
- Does NOT change in this increment

### Organisation/Control Plane
- Will implement: `OrganisationalContextPort`, `WorkManagementPort` (future increment)
- Does NOT change in this increment

## Dependency Direction

```
Assistant (ai package)
    │
    ├── depends on: ports (interfaces only)
    │
    ├── CapabilityDiscoveryPort ──────► People/Capability (future impl)
    ├── CapabilityExecutionPort ──────► Operations (future impl)
    ├── EnterpriseInformationPort ────► Enterprise/EIMS (future impl)
    ├── OrganisationalContextPort ────► Organisation/Control (future impl)
    ├── WorkManagementPort ───────────► Organisation/Control (future impl)
    └── SessionFactoryPort ───────────► Operations (future impl)
```

## Exact Files to Change

### New Files

| File | Purpose |
|---|---|
| `packages/ai/src/ports/__init__.py` | Port package init |
| `packages/ai/src/ports/capability_discovery.py` | `CapabilityDiscoveryPort` protocol |
| `packages/ai/src/ports/capability_execution.py` | `CapabilityExecutionPort` protocol + result types |
| `packages/ai/src/ports/enterprise_information.py` | `EnterpriseInformationPort` protocol + solution types |
| `packages/ai/src/ports/organisational_context.py` | `OrganisationalContextPort` protocol |
| `packages/ai/src/ports/work_management.py` | `WorkManagementPort` protocol + request/response types |
| `packages/ai/src/ports/session_factory.py` | `SessionFactoryPort` protocol |
| `packages/ai/src/assistant_port.py` | `AssistantPort` protocol (what Assistant provides externally) |
| `packages/ai/tests/fixtures/in_memory_ports.py` | In-memory port implementations for testing |
| `packages/ai/tests/test_architectural_boundaries.py` | Guardrail tests for AI plane imports |

### Modified Files

| File | Changes |
|---|---|
| `packages/ai/src/chat.py` | Replace direct imports with port dependencies; inject ports via constructor |
| `packages/ai/tests/test_assistant.py` | Update to use port fixtures instead of direct ConceptStore/CapabilityRegistry |
| `packages/ai/tests/test_ceo.py` | Update CEO tests similarly |
| `.kilo/context/architecture.md` | Already updated with ADR-044, ADR-045, port definitions, and new constraints |

## New Files Detail

### `packages/ai/src/ports/capability_discovery.py`

```python
from typing import Protocol, runtime_checkable
from capability import Capability
from enterprise_context import ContextRecord, MatchResult

class CapabilityDiscoveryPort(Protocol):
    def list_capabilities(self) -> list[Capability]: ...
    def find_capabilities(self, request_text: str, context: ContextRecord) -> MatchResult: ...
```

### `packages/ai/src/ports/capability_execution.py`

```python
from typing import Protocol
from pydantic import BaseModel

class ExecutionResult(BaseModel):
    outputs: dict[str, Any]
    artifacts: list[str] = []
    telemetry: dict[str, Any] = {}

class CapabilityExecutionPort(Protocol):
    def execute(self, capability_id: str, context: dict[str, Any], actor_context: dict[str, Any]) -> ExecutionResult: ...
```

### `packages/ai/src/ports/enterprise_information.py`

```python
from typing import Protocol
from pydantic import BaseModel

class PreviousSolution(BaseModel):
    concept_id: str
    name: str
    summary: str
    invocation_count: int
    last_invoked: str | None = None

class EnterpriseInformationPort(Protocol):
    def find_previous_solutions(self, strategy_tag: str) -> PreviousSolution | None: ...
    def record_solution(self, solution: "SolutionRecord") -> None: ...
```

### `packages/ai/src/ports/organisational_context.py`

```python
from typing import Protocol
from role import OrgContext

class OrganisationalContextPort(Protocol):
    def get_context(self, actor_id: str | None, role_id: str | None) -> OrgContext: ...
    def get_role(self, role_id: str) -> Role | None: ...
```

### `packages/ai/src/ports/work_management.py`

```python
from typing import Protocol
from pydantic import BaseModel

class WorkCreateRequest(BaseModel):
    title: str
    description: str = ""
    accountable_role_id: str
    coordinating_role_id: str | None = None
    required_capability_ids: list[str] = []
    # ...

class WorkReference(BaseModel):
    work_id: str
    status: str

class WorkManagementPort(Protocol):
    def create_work(self, request: WorkCreateRequest) -> WorkReference: ...
    def mark_ready(self, work_id: str) -> WorkReference | None: ...
    def get_work(self, work_id: str) -> WorkReference | None: ...
```

### `packages/ai/src/ports/session_factory.py`

```python
from typing import Protocol
from assistant import StrategyDecision

class SessionFactoryPort(Protocol):
    def create_session(self, decision: StrategyDecision, context: dict[str, Any]) -> Session: ...
```

### `packages/ai/src/assistant_port.py`

```python
from typing import Protocol
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    context: dict[str, Any] = {}

class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    reasoning: str | None = None
    previous_solution: dict[str, Any] | None = None
    human_input_request: dict[str, Any] | None = None
    capability_candidates: list[dict[str, Any]] | None = None
    telemetry: dict[str, Any] = {}

class AssistantPort(Protocol):
    def chat(self, request: ChatRequest) -> ChatResponse: ...
    def resume(self, session_id: str, human_response: dict[str, Any]) -> ChatResponse: ...
```

## Behavioural Scenarios

### A. Informational Question
- AI plane: recognise + select_strategy
- Assistant: no port calls needed
- Response: informational message

### B. Perform Existing Capability
- AI plane: recognise + select_strategy
- Assistant: `CapabilityExecutionPort.execute(capability_id, context, actor_context)`
- Operations: authorisation + execution
- Response: execution result

### C. Multiple Capabilities
- AI plane: recognise + select_strategy
- Assistant: `CapabilityExecutionPort.execute_many(...)`
- Operations: orchestrates multiple invocations
- Response: synthesised result

### D. No Capability Exists
- AI plane: recognise + select_strategy
- Assistant: no capability found → generate AI response or create Work request
- Response: "no capability available" or Work creation confirmation

### E. Not Authorised
- AI plane: recognise
- Assistant: `CapabilityExecutionPort.execute(...)`
- Operations/People/Capability: returns authorisation failure
- Response: "not authorised" message

### F. Needs Organisational Context
- AI plane: recognise
- Assistant: `OrganisationalContextPort.get_context(actor_id, role_id)`
- Organisation/Control: returns OrgContext
- Assistant uses context for downstream requests

### G. Create Organisational Work
- AI plane: recognise + select_strategy
- Assistant: `WorkManagementPort.create_work(request)`
- Organisation/Control: creates and assigns Work
- Response: Work reference

### H. Acting on Behalf of Role
- AI plane: recognise
- Assistant: `OrganisationalContextPort.get_context(actor_id, role_id)`
- Organisation/Control: returns context including delegated authority
- Assistant carries context in all subsequent port calls

## Tests Required

### Architectural Guardrail Tests

```python
# packages/ai/tests/test_architectural_boundaries.py

def test_assistant_chat_service_has_no_forbidden_imports():
    """chat.py must not import from domain plane implementations."""
    import ast
    import os
    source_path = os.path.join(os.path.dirname(__file__), "..", "src", "chat.py")
    with open(source_path) as f:
        tree = ast.parse(f.read())
    forbidden = {
        "capability_registry", "capability_matcher", "concepts",
        "workflow_runner.src.executor", "workflow_runner.src.runtime",
        "workflow_runner.src.session", "bus", "pathway_runtime",
        "langgraph_runtime",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for forbidden_mod in forbidden:
                assert forbidden_mod not in node.module, (
                    f"AssistantChatService must not import from {node.module}"
                )

def test_ai_package_has_no_cross_plane_imports():
    """Scan all ai/src/*.py for forbidden imports."""
    # Similar pattern to test_architectural_boundaries_no_forbidden_methods
    # in organisation tests
    pass

def test_ports_are_only_dependencies():
    """AssistantChatService constructor should accept ports, not concrete types."""
    from ports import (
        CapabilityDiscoveryPort,
        CapabilityExecutionPort,
        EnterpriseInformationPort,
        OrganisationalContextPort,
        WorkManagementPort,
        SessionFactoryPort,
    )
    from chat import AssistantChatService
    import inspect
    sig = inspect.signature(AssistantChatService.__init__)
    for param in sig.parameters.values():
        if param.name.startswith("_"):
            continue
        # All injected dependencies should be port types
        assert param.annotation in (
            CapabilityDiscoveryPort, CapabilityExecutionPort,
            EnterpriseInformationPort, OrganisationalContextPort,
            WorkManagementPort, SessionFactoryPort, type(None),
        ), f"Unexpected dependency type: {param.annotation}"
```

### Behavioural Tests (Updated)

```python
# packages/ai/tests/test_assistant.py

def test_chat_service_returns_previous_solution_via_port(tmp_path):
    """Previous solution lookup goes through EnterpriseInformationPort."""
    from ports.enterprise_information import InMemoryEnterpriseInformationPort
    port = InMemoryEnterpriseInformationPort()
    port._solutions.append(PreviousSolution(
        concept_id="sol-1",
        name="previous-solution",
        summary="Designed a task tracker",
        invocation_count=2,
        last_invoked=None,
    ))
    service = AssistantChatService(
        enterprise_information=port,
        # other ports = None or no-op
    )
    request = ChatRequest(message="Design a new task tracking service")
    response = service.chat(request)
    assert response.status == "awaiting_confirmation"
    assert response.previous_solution is not None
```

### Port Contract Tests

```python
# packages/ai/tests/test_ports.py

def test_capability_discovery_port_is_protocol():
    from ports.capability_discovery import CapabilityDiscoveryPort
    assert hasattr(CapabilityDiscoveryPort, "list_capabilities")
    assert hasattr(CapabilityDiscoveryPort, "find_capabilities")
```

## Validation Commands

```bash
# Unit tests for AI plane
pytest packages/ai/tests/ -q

# Lint AI plane
ruff check packages/ai/src/ packages/ai/tests/

# Full validation suite (must not regress)
pytest packages/organisation/tests/ packages/ai/tests/test_ceo.py packages/capability_registry/tests/ packages/people_capability/tests/ packages/workflow_runner/tests/ -q
```

## Architectural Guardrails

1. `chat.py` must not import from `capability_registry`, `concepts`, `workflow_runner.src.executor`, `workflow_runner.src.runtime`, `workflow_runner.src.session`, `bus`, or `pathway_runtime`.
2. All cross-plane dependencies must be port interfaces defined in `packages/ai/src/ports/`.
3. `AssistantChatService.__init__` must accept ports via dependency injection, not instantiate domain services.
4. The `ai` package must not write to `ConceptStore` directly.
5. The `ai` package must not call `execute_capability()` or `PatternRuntime.invoke_step()` directly.
6. The `ai` package must not create `Session` objects directly.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Existing tests break | High | Medium | Update tests to use port fixtures |
| Port interface too narrow | Medium | Medium | Start minimal; expand in later increments |
| Workflow runner API compatibility | Low | Medium | API already uses `AssistantChatService` interface; verify |
| Scope creep to full rewrite | Medium | High | Explicitly defer: no capability matching, no Work creation, no CEO changes |
| Port implementations not completed | Medium | Medium | Ports are interfaces only; implementations are future work |

## Explicitly Deferred Work

- Capability matching implementation (Increment 14 deferred)
- PatternRuntime authorisation enforcement (Increment 14 deferred)
- CEO/COO/PM implementation (explicitly out of scope)
- Paperclip integration (explicitly out of scope)
- ConceptStore relocation (explicitly out of scope)
- EnterpriseInformation abstraction (ADR-030 deferred)
- Work creation by Assistant (requires Organisation/Control role implementation)
- Universal routing (ADR-025: Assistant must NOT implement universal routing)
- Assistant as organisational Role (future — requires Role model expansion)
- Fixing the failing test mechanically (fix architecture, not assertion)
