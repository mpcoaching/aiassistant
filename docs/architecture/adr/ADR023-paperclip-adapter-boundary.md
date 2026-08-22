# ADR-023: Paperclip Adapter Boundary behind OrganisationControlPlane

Status: Accepted

Decision

The OrganisationControlPlane abstraction is defined independently of Paperclip. A Paperclip adapter will implement the abstraction in a future increment. No Paperclip-specific types appear in the organisation domain.

Context

Paperclip is a future backend for organisational data. Introducing Paperclip types into the domain model would couple the organisation plane to a specific implementation, violating ADR-010 (Provider-Based Architecture).

Decision

1. OrganisationControlPlane is defined with pure Python types (Role, Person, Agent, Authority, Work, Assignment, OrgContext).

2. No Paperclip imports exist in: Role, Work, Authority, OrganisationControlPlane, or CEO domain logic.

3. The abstraction must be independently testable without Paperclip.

4. Future mapping:
   - Role definitions -> Paperclip Agent/Team
   - Work assignments -> Paperclip Task
   - Coordination -> Paperclip meetings

Rationale

1. The abstraction outlives any single implementation.
2. Independent testability enables TDD.
3. Paperclip can subsequently implement the abstraction without changing the domain model.

Consequences

- Organisation domain has zero dependency on Paperclip.
- Adapter implementation is deferred to a future increment.
- The interface remains stable regardless of backend changes.

Related

- ADR-017: Three-Plane Architecture
- ADR-022: OrganisationControlPlane Abstraction
- ADR-010: Provider-Based Architecture
