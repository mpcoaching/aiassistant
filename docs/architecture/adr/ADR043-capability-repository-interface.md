# ADR-043: Capability Repository Interface

Status: Accepted

Decision

CapabilityRegistry must not depend on ConceptStore (EIMS implementation) directly.

Context

`CapabilityRegistry` currently takes a `ConceptStore` instance in `__init__` and delegates
all persistence directly to it. This conflates the domain registry with the EIMS
implementation.

ConceptStore is the current implementation of the Enterprise Information Management System
(EIMS) boundary (ADR-021). EIMS is owned by Enterprise, not by People/Capability. While
CapabilityRegistry may use EIMS for persistence, it must not depend on the EIMS
implementation directly.

Decision

1. Define `CapabilityRepository` protocol:
   - `upsert(capability: Capability) -> None`
   - `get(capability_id: str) -> Capability | None`
   - `list_by_kind(kind: ConceptKind) -> list[Capability]`
   - `record_invocation(concept_id: str, outcome: str) -> None`

2. `CapabilityRegistry.__init__` accepts `CapabilityRepository | None = None`.

3. `ConceptStoreCapabilityRepository` adapter wraps `ConceptStore` and implements
   `CapabilityRepository`.

4. Future: EIMS can provide its own `CapabilityRepository` implementation without changing
   `CapabilityRegistry`.

5. `CapabilityRegistry` no longer imports `ConceptStore` directly.

Rationale

1. Dependency inversion — domain depends on abstraction, not on EIMS implementation.
2. EIMS can evolve (expand beyond ConceptStore) without breaking People/Capability.
3. Preserves plane boundaries — People/Capability does not own EIMS.
4. Enables future `EnterpriseInformation` abstraction (ADR-030).

Consequences

- `packages/capability_registry/src/capabilities.py` loses `from concepts import ...`
- `ConceptStoreCapabilityRepository` adapter added to `capability_registry` package
- All tests that create `CapabilityRegistry(ConceptStore(...))` must use the adapter
- `conftest.py` may need updated path configuration

Related

- ADR-010: Provider-Based Architecture
- ADR-021: EIMS Boundary and ConceptStore
- ADR-030: Future EnterpriseInformation Abstraction
- ADR-041: People/Capability Plane Package Structure
- ADR-042: Capability Execution Binding Separation
