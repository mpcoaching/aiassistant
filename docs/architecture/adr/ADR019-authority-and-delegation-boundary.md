# ADR-019: Authority and Delegation Boundary

Status: Accepted

Decision

Authority is an explicit, delegatable grant within a defined scope. Authority records live in the Organisation/Control plane. Delegation is a first-class record that preserves the chain of grant.

Context

Without explicit authority records, the system cannot answer "who is allowed to do what" or "who delegated this decision." Implicit authority in capability matching or agent configuration creates governance gaps.

Decision

1. Authority is a permission grant within a scope. It has a grantor, a grantee, a scope, and constraints. It can be delegated.

2. Delegation is a record linking an Authority from one Role to another Role. It preserves the original grantor and records the delegation chain.

3. Authority and Delegation are owned by Organisation/Control plane. They are not embedded in Capability definitions or Agent configurations.

4. CEO may delegate authority but does not create authority grants de novo beyond its own granted scope.

Explicitly Excluded

- Authority is NOT embedded in Capability definitions.
- Authority is NOT stored in ConceptStore (EIMS).
- Authority is NOT determined at runtime by capability matching.
- Delegation is NOT performed by Operations plane executors.

Rationale

1. Governance requires auditable authority chains.
2. Delegation must be revocable and traceable.
3. Separating authority from execution prevents privilege escalation through capability chaining.

Consequences

- All operational actions must reference an Authority record.
- Authority checks happen before work assignment, not during execution.
- The OrganisationControlPlane is the sole authority registry.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-022: OrganisationControlPlane Abstraction
