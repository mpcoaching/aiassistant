# ADR-037: Person/Agent Ownership by People/Capability

Status: Accepted

Decision

Person and Agent domain records belong to the People/Capability plane, not the Organisation/Control plane. Organisation/Control references Person and Agent by ID only. OrganisationControlPlane does not store Person or Agent records.

Context

Increment 6 placed Person and Agent in `packages/organisation/src/role.py` (Organisation/Control plane). Increment 7's ADR-026 established that Person records belong to People/Capability. This creates a contradiction: the current code conflates domain ownership with reference mechanisms.

The OrganisationControlPlane needs to assign Work to Person/Agent, but it does not need to own Person/Agent lifecycle. People/Capability owns person records, employment context, agent runtime identity, and capability possession.

Decision

1. Person and Agent domain records are owned by People/Capability plane.

2. Organisation/Control references Person and Agent by ID (`assignee_person_id`, `assignee_agent_id`, `fulfilled_role_ids` on Agent).

3. OrganisationControlPlane does NOT store Person or Agent records.

4. People/Capability determines:
   - Whether a Person/Agent has the capabilities required to fulfil a Role
   - Whether training, recruitment, or acquisition is needed
   - Capability readiness for role fulfilment

5. The Assignment record uses `assignee_type` ("role", "person", "agent") and `assignee_id` to reference the assignee without embedding the full record.

Reference Model

```
People/Capability plane:
    Person (id, name, email, role_ids, employment_context)
    Agent (id, name, marker, fulfilled_role_ids, runtime_identity)

Organisation/Control plane:
    Work (assignee_person_id: str | None, assignee_agent_id: str | None)
    Assignment (assignee_type: str, assignee_id: str)
    Role (required_capability_ids: list[str])

Person/Agent fulfils Role:
    Person.role_ids contains Role.id
    Agent.fulfilled_role_ids contains Role.id
```

Rationale

1. Person records contain employment context, which is a People/Capability concern.
2. Agent records contain runtime identity and capability possession, which are People/Capability and Operations concerns.
3. Organisation/Control needs only IDs to create assignments and accountability relationships.
4. Separating ownership from reference prevents the Organisation/Control plane from absorbing people management.

Consequences

- Person and Agent records will eventually move to a People/Capability package.
- Organisation/Control uses string IDs for Person/Agent references.
- OrganisationControlPlane API does not include `register_person` or `register_agent`.
- Future InMemoryOrganisationControlPlane implementations should not store Person/Agent dictionaries.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-022: OrganisationControlPlane Abstraction
- ADR-026: People/Capability as Peer Domain Plane
- ADR-027: Work-Capability "Requires" Relationship
