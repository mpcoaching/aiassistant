# ADR-044: Assistant as Application-Layer Translation Service

Status: Proposed

## Decision

Assistant is an application-layer translation service within the Organisation, not a domain service. It translates natural language user intent into structured requests for the Organisation Control Plane. The Chat/API/UI/Voice layer is outside the Organisation and is simply the interaction mechanism. The Assistant does NOT own capability matching, EIMS access, session creation, runtime invocation, or execution.

## Context

ADR-025 correctly identified that Assistant should not be an orchestrator or implicit CEO. However, the current implementation of `AssistantChatService` (`packages/ai/src/chat.py`) is exactly that: a God service that crosses all four plane boundaries. The AI plane was intended to own intent recognition and strategy selection only. Application-layer translation belongs to a thin interface, not to a domain service.

The current `AssistantChatService` directly imports and uses:

- `CapabilityRegistry`, `CapabilityMatcher`, `HumanSelectionMatcher`, `Capability` (People/Capability plane)
- `ConceptStore`, `EnterpriseConcept`, `ConceptKind` (Enterprise/EIMS)
- `PathwayRuntime`, `PathwayCallRequest`, `PathwayResponse`, `PathwayStatus` (Operations)
- `execute_capability`, `ExecutionResult` (Operations)
- `Session`, `create_session_from_decision` (Operations)
- `HumanInTheLoopMixin` (Operations)

This recreates the exact "God service" pattern that ADR-017 warned about and that ADR-031 corrected for CEO.

## Decision

1. `AssistantChatService` is an application-layer service, not a domain service in any plane.
2. Assistant depends on ports/interfaces, not concrete implementations from other planes.
3. Assistant does NOT import from `capability_registry`, `concepts`, `workflow_runner.src.executor`, `workflow_runner.src.runtime`, `workflow_runner.src.session`, `bus`, or `pathway_runtime`.
4. Capability matching, EIMS access, session creation, and execution are delegated through ports.
5. The `ai` package owns only: intent recognition, strategy selection, reasoning, and the Assistant port interface.

## Consequences

- `AssistantChatService` must be refactored to depend on ports, not concrete implementations.
- Tests must be updated to use port fixtures, not direct imports of `ConceptStore`, `CapabilityRegistry`, etc.
- The failing test `test_chat_service_returns_previous_solution` is resolved by removing capability matching from Assistant, not by changing the assertion.
- The `ai` package boundary becomes enforceable via import checks.
- Future increments can implement the port implementations in their respective planes without changing Assistant.

## Related

- ADR-017: Three-Plane Architecture
- ADR-025: Assistant as Organisational Role/Interface, not Implicit CEO
- ADR-031: CEO as Strategic Role, Not Orchestrator
- ADR-045: Assistant Port Interfaces
