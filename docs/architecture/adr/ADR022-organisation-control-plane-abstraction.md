# ADR-022: OrganisationControlPlane Abstraction

Status: Accepted

Decision

OrganisationControlPlane is a narrow abstraction that provides role lookup, work assignment, authority delegation, and organisational context retrieval. It is explicitly not a God service.

Context

The system needs a single point to query organisational structure, assign work, and delegate authority. Without a narrow abstraction, this responsibility accretes into the CEO or into ad-hoc code scattered across the operations plane.

Decision

1. OrganisationControlPlane is an abstract interface (ABC) with the following methods:
   - get_role(role_id: str) -> Role | None
   - list_roles() -> list[Role]
   - get_organisational_context(request_context: dict) -> OrgContext
   - assign_work(work: Work, assignee: Role | Person | Agent) -> Assignment
   - get_work(work_id: str) -> Work | None
   - delegate_authority(from_role: Role, to_role: Role, authority: Authority) -> Delegation

2. InMemoryOrganisationControlPlane is the reference implementation for testing and local development.

3. The abstraction must be independently testable without Paperclip or any specific backend.

Explicitly Excluded

The following must NOT be on OrganisationControlPlane:
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

1. A narrow interface is easier to implement, test, and reason about.
2. The Organisation/Control plane must not become the execution engine.
3. Independence from Paperclip preserves architectural flexibility.

Consequences

- All organisational queries go through OrganisationControlPlane.
- CEO receives OrganisationControlPlane via dependency injection.
- Tests mock OrganisationControlPlane to verify CEO boundaries.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-019: Authority and Delegation Boundary
- ADR-024: CEO as Organisational Role
