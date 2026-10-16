# ADR-038: Work Decomposition and Dependency Model

Status: Accepted

Decision

Work supports parent/child decomposition and dependency tracking for project coordination. Work decomposition is an organisational/management concern, not an operational workflow concern.

Context

Strategic initiatives and complex BAU work require breaking large efforts into smaller, assignable pieces. The current Work model has no mechanism for decomposition or dependencies. This forces project coordination logic into ad-hoc code or into the OrganisationControlPlane, creating a God service risk.

Decision

1. Work contains `parent_work_id: str | None` for decomposition.

2. Work contains `dependencies: list[str]` listing Work IDs this work depends on.

3. Work decomposition is created by the coordinating role (Project Manager for projects, functional manager for BAU).

4. Dependencies express sequencing requirements: Work B cannot start until Work A completes.

5. Work decomposition and dependencies are organisational/management concerns. Operations does not interpret them; Operations executes individual Work items when directed.

6. The `work_type` field distinguishes BAU ("bau") from project/initiative ("project", "initiative").

7. Every Work item has exactly one `accountable_role_id`.

Work Hierarchy Example

```
Initiative: "Enter Market X"
    ↓ parent_work_id
Project: "Market Entry Delivery"
    ↓ parent_work_id
    ├── Work: "Architecture Design" (accountable: EA, coordinating: PM)
    ├── Work: "Business Analysis" (accountable: BA, coordinating: PM)
    ├── Work: "Solution Architecture" (accountable: SA, coordinating: PM)
    ├── Work: "Implementation" (accountable: Dev, coordinating: PM)
    └── Work: "QA Validation" (accountable: QA, coordinating: PM)
```

Dependency Example

```
Work: "Implementation" depends_on: ["Architecture Design", "Business Analysis"]
Work: "QA Validation" depends_on: ["Implementation"]
```

OrganisationControlPlane Responsibility

OrganisationControlPlane:
- Provides mechanism to create Work with parent_work_id and dependencies
- Provides mechanism to query work hierarchy
- Does NOT enforce dependency sequencing (that is a PM/coordination concern)
- Does NOT become the project manager

Rationale

1. Work decomposition is a management coordination activity, not an operational execution activity.
2. Dependencies express management intent; Operations executes individual work items.
3. The model supports project coordination without making OrganisationControlPlane the project manager.
4. Parent/child relationships enable accountability to flow from strategic initiatives down to operational tasks.

Consequences

- Work model gains `parent_work_id`, `dependencies`, `work_type`, `accountable_role_id`, `coordinating_role_id`.
- Project Manager creates decomposition; OrganisationControlPlane stores it.
- Operations receives individual Work items for execution, not the hierarchy.
- Future PM implementations can traverse work hierarchies without changing the domain model.

Related

- ADR-027: Work-Capability "Requires" Relationship
- ADR-031: CEO as Strategic Role, Not Orchestrator
- ADR-033: Project Management as Organisational Role
- ADR-034: Work Accountability Model
- ADR-036: Distributed Organisational Coordination
- ADR-037: Person/Agent Ownership by People/Capability
