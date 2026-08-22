# ADR-017: Enterprise / Organisation-Control / Operations Three-Plane Architecture

Status: Accepted

Decision

The system is partitioned into three orthogonal planes: Enterprise, Organisation/Control, and Operations. Each plane owns a distinct set of concerns and has explicit prohibitions against crossing into adjacent planes.

Context

The current architecture mixes organisational concerns, capability execution, and enterprise knowledge into a single routing layer (CEO). This creates a God service that knows about strategy, capability matching, execution, and governance simultaneously. Separation of concerns requires explicit boundaries.

Decision

1. Enterprise Plane owns strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning. Boundary: strategy interpretation, priority setting, escalation thresholds. Does NOT run operations, execute work, or own capabilities.

2. Organisation/Control Plane owns organisational structure, roles, responsibilities, authority, delegation, relationships, allocation of organisational work, coordination between roles, organisational context, people/capability function. Boundary: OrganisationControlPlane abstraction. Does NOT execute operational work, own EIMS, own capability definitions/lifecycle, or directly control runtime agents.

3. Operations Plane owns workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work. Boundary: PathwayRuntime, Session, PatternStep. Does NOT define organisational authority or strategy.

Rationale

1. Each plane has a single, coherent responsibility.
2. Cross-plane dependencies flow through well-defined interfaces only.
3. The Organisation/Control plane can be implemented independently of the Operations substrate (e.g., Paperclip adapter).
4. Testing each plane in isolation becomes possible.

Consequences

- CEO is a consumer of the Organisation/Control plane, not the plane itself.
- Capability discovery and execution are explicitly Operations-plane concerns.
- Enterprise knowledge (EIMS) is accessed by all planes but owned only by Enterprise.

Related

- ADR-018: Role vs Person vs Agent
- ADR-022: OrganisationControlPlane abstraction
- ADR-024: CEO as organisational Role
