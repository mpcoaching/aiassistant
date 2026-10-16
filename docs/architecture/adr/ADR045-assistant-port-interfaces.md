# ADR-045: Assistant Port Interfaces

Status: Proposed

## Decision

Define explicit port interfaces between Assistant and each domain plane. Assistant depends on these ports; implementations live in the respective planes.

## Context

The current `AssistantChatService` has hard dependencies on concrete classes from four planes. This makes it impossible to test, impossible to swap implementations, and impossible to enforce architectural boundaries.

The `ai` package currently imports from:
- `capability_registry` (People/Capability)
- `concepts` (Enterprise/EIMS)
- `workflow_runner.src.executor` (Operations)
- `workflow_runner.src.runtime` (Operations)
- `workflow_runner.src.session` (Operations)
- `bus` (Operations)
- `pathway_runtime` (Operations)

Each of these is a plane boundary violation.

## Decision

Define the following ports in `packages/ai/src/ports/`:

1. **`CapabilityDiscoveryPort`** — query capabilities (People/Capability)
   - Methods: `list_capabilities()`, `find_capabilities(request_text, context)`

2. **`CapabilityExecutionPort`** — execute capabilities (Operations)
   - Methods: `execute(capability_id, context, actor_context)`, `execute_many(request, actor_context)`

3. **`EnterpriseInformationPort`** — read/write enterprise knowledge (Enterprise/EIMS)
   - Methods: `find_previous_solutions(strategy_tag)`, `record_solution(solution)`

4. **`OrganisationalContextPort`** — get organisational context (Organisation/Control)
   - Methods: `get_context(actor_id, role_id)`, `get_role(role_id)`

5. **`WorkManagementPort`** — create and manage Work (Organisation/Control)
   - Methods: `create_work(request)`, `mark_ready(work_id)`, `get_work(work_id)`

6. **`SessionFactoryPort`** — create sessions (Operations)
   - Methods: `create_session_from_decision(decision, context)`

Each port is a `Protocol` defining the minimal interface Assistant needs. Implementations live in the respective planes and are injected via dependency injection.

## Port Package Structure

```
packages/ai/src/ports/
├── __init__.py
├── capability_discovery.py
├── capability_execution.py
├── enterprise_information.py
├── organisational_context.py
├── work_management.py
└── session_factory.py
```

## Dependency Direction (After Increment 15)

```
Application Layer
├── Assistant (ai package)
│   ├── depends on: ports (interfaces)
│   └── does NOT depend on: any other plane's src/
│
├── Organisation/Control (implements OrganisationalContextPort, WorkManagementPort)
├── People/Capability (implements CapabilityDiscoveryPort, CapabilityExecutionPort.authorisation)
├── Operations (implements CapabilityExecutionPort, SessionFactoryPort)
└── Enterprise/EIMS (implements EnterpriseInformationPort)
```

## Consequences

- Assistant has zero direct imports from other planes' `src/` directories.
- All cross-plane communication goes through ports.
- Test fixtures can provide in-memory port implementations.
- The architecture becomes enforceable via import checks.
- Each plane can evolve its implementation without changing Assistant.
- Port interfaces are minimal — only what Assistant actually needs.

## Related

- ADR-017: Three-Plane Architecture
- ADR-010: Provider-Based Architecture
- ADR-044: Assistant as Application-Layer Translation Service
