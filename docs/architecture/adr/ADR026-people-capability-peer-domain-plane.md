# ADR-026: People/Capability as Peer Domain Plane

Status: Accepted

Decision

People/Capability is a peer domain plane alongside Enterprise, Organisation/Control, and Operations. It is NOT a sub-domain of Organisation/Control. It owns capability definitions, capability lifecycle, people records, skills, and capability development/acquisition/testing.

Context

Increment 6 established Organisation/Control as a distinct plane. The Increment 7 investigation revealed that capability ownership cannot remain loosely attached to Organisation/Control. Capabilities have their own lifecycle (identify -> specify -> develop/acquire -> test -> register -> assign -> operate -> measure -> learn -> retire), their own governance (CapabilityRequest), and their own quality attributes (maturation, promotion, correction tracking).

If People/Capability remains implicit within Organisation/Control, the Organisation/Control plane will grow to encompass capability lifecycle, capability matching, capability execution governance, and people management — becoming a God service.

Decision

1. People/Capability is a first-class domain plane, parallel to:
   - Enterprise (strategy, goals, governance, durable knowledge)
   - Organisation/Control (roles, authority, work assignment, delegation)
   - Operations (workflows, runtime execution, agents, tools)

2. People/Capability owns:
   - Person records (human individuals)
   - Capability definitions (tools, skills, services)
   - Capability lifecycle (registration, maturation, promotion, retirement)
   - Capability development and acquisition
   - Capability testing and validation
   - CapabilityRequest governance (transient -> EnterpriseConcept)
   - Capability matching coordination
   - People/role fulfilment tracking

3. Organisation/Control coordinates with People/Capability but does NOT own capability lifecycle.

4. Operations consumes capabilities through well-defined interfaces but does not define or govern them.

Plane Ownership Summary

| Concern | Owner |
|---|---|
| Role definitions | Organisation/Control |
| Person records | People/Capability |
| Capability definitions | People/Capability |
| Capability lifecycle | People/Capability |
| Capability matching | People/Capability |
| Work assignment | Organisation/Control |
| Work execution | Operations |
| Durable enterprise knowledge | EIMS (Enterprise plane) |
| Strategy | Enterprise plane |

Rationale

1. Capability lifecycle is complex enough to warrant its own domain boundary.
2. Separating People/Capability from Organisation/Control prevents the Organisation/Control plane from absorbing capability governance.
3. A peer plane can evolve independently (e.g., adding learning analytics, capability marketplaces) without changing Organisation/Control.
4. The three-plane model becomes a four-plane model, preserving the same architectural principles.

Consequences

- People/Capability is a new architectural boundary that must be documented, tested, and governed.
- OrganisationControlPlane must NOT grow capability lifecycle methods.
- CEO must NOT gain capability ownership through the People/Capability plane.
- Future implementations must respect this peer boundary.
- CapabilityRegistry and CapabilityRequest remain in People/Capability domain.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-020: Capability Ownership by People/Capability
- ADR-022: OrganisationControlPlane Abstraction
