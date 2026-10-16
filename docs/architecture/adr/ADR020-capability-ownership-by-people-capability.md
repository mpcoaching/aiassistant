# ADR-020: Capability Ownership by People/Capability

Status: Accepted

Decision

Capabilities belong to the People/Capability function. The CEO and OrganisationControlPlane do not own capability definitions, matching, or execution lifecycle.

Context

If the CEO owns capability matching, the CEO becomes the universal router and the organisational boundary collapses. Capability ownership must remain explicit to preserve the three-plane architecture.

Decision

1. Capability lifecycle is owned by People/Capability domain: identify -> specify -> develop/acquire -> test -> register -> assign -> operate -> measure -> learn -> retire.

2. CEO may identify that a capability is missing (as an organisational observation) but does not search CapabilityRegistry or select capabilities.

3. OrganisationControlPlane coordinates with or invokes the People/Capability function but does not own capability lifecycle.

4. CapabilityMatcher, CapabilityRegistry, CapabilityRequest, CapabilityExecutor must NOT become CEO-owned services.

Explicitly Excluded from CEO

- find_capability()
- match_capability()
- execute_capability()
- execute_work()
- run_agent()
- invoke_tool()

These belong to:
- Capability discovery/matching -> People/Capability function
- Execution -> Operations plane

Rationale

1. Capability selection is a People/Capability domain decision, not an organisational control decision.
2. The CEO's role is to identify gaps and delegate work, not to operate capabilities.
3. Separating capability ownership prevents the CEO from becoming the universal request router.

Consequences

- CEO tests must verify absence of capability matching logic.
- Architectural boundary tests guard against capability imports in CEO and OrganisationControlPlane.
- CapabilityRegistry remains in capability_registry package; CEO imports it only for reference, not for matching.

Related

- ADR-017: Three-Plane Architecture
- ADR-022: OrganisationControlPlane Abstraction
- ADR-024: CEO as Organisational Role
