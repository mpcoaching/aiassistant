# ADR-021: EIMS Boundary and ConceptStore as Current Implementation

Status: Accepted

Decision

ConceptStore is the current implementation of the Enterprise Information Management System (EIMS) boundary. It is documented as an implementation, not the complete EIMS. Future EIMS capabilities should be additive.

Context

The system needs durable enterprise knowledge storage. ConceptStore exists today but is not declared as the definitive EIMS. Without explicit documentation, future developers may over-extend or replace it without understanding the boundary.

Decision

1. ConceptStore / EnterpriseConcept is the current implementation of an emerging EIMS boundary.

2. EIMS owns: durable enterprise information, enterprise concepts, provenance, relationships, institutional knowledge, learning, historical organisational knowledge where appropriate.

3. EIMS does NOT own: runtime execution, orchestration, role assignment, authority, agent control, workflow execution, organisational control database.

4. The eventual EIMS may expand beyond ConceptStore. Preserve architectural flexibility by treating ConceptStore as an implementation, not the complete EIMS.

5. New EIMS capabilities should be additive. Existing ConceptStore APIs remain stable.

Rationale

1. ConceptStore already provides the core durable storage mechanism.
2. Declaring it as the current EIMS implementation prevents scope creep into adjacent planes.
3. Additive expansion allows the EIMS to evolve without breaking existing consumers.

Consequences

- CEO may retain ConceptStore as an EIMS reference.
- OrganisationControlPlane does not own ConceptStore.
- Capability definitions may reference EnterpriseConcept but ConceptStore is owned by EIMS plane.

Related

- ADR-017: Three-Plane Architecture
- ADR-022: OrganisationControlPlane Abstraction
