# ADR-017: Organisation / Operations Architecture

Status: Accepted

Decision

The system is partitioned into two orthogonal boundaries: Organisation and Operations. The Organisation owns strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning, organisational structure, roles, responsibilities, authority, delegation, relationships, allocation of organisational work, coordination between roles, organisational context, people/capability function, and the organisational event/signal boundary. The Organisation Control Plane is the implementation mechanism inside the Organisation. Operations owns workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, and operational work. The Chat/API/UI/Voice layer is outside the Organisation and is simply the interaction mechanism through which the user communicates with the Assistant (a role inside the Organisation).

Context

The current architecture mixes organisational concerns, capability execution, and enterprise knowledge into a single routing layer (CEO). This creates a God service that knows about strategy, capability matching, execution, and governance simultaneously. Separation of concerns requires explicit boundaries.

Decision

1. Organisation owns strategy, enterprise goals, durable enterprise knowledge/information, governance policies, enterprise priorities, institutional learning, organisational structure, roles, responsibilities, authority, delegation, relationships, allocation of organisational work, coordination between roles, organisational context, people/capability function, and the organisational event/signal boundary. The Organisation Control Plane is the implementation mechanism inside the Organisation. Boundary: strategy interpretation, priority setting, escalation thresholds, work assignment, capability registration, capacity management. Does NOT run operations or execute operational work directly.

2. Operations Plane owns workflows, pathways, sessions, deterministic execution, agent execution, tools, runtime orchestration, operational work. Boundary: PathwayRuntime, Session, PatternStep. Does NOT define organisational authority or strategy.

3. The Chat/API/UI/Voice layer is outside the Organisation. The Assistant is a role inside the Organisation. The Assistant understands user intent, queries organisational capability through ports, delegates to the Organisation Control Plane when organisational action is needed, and returns outcomes to the user.

Rationale

1. The Organisation has a single, coherent responsibility for all organisational truth and decisions.
2. Cross-boundary dependencies flow through well-defined interfaces only.
3. The Organisation Control Plane can be implemented independently of the Operations substrate (e.g., Paperclip adapter).
4. Testing each boundary in isolation becomes possible.
5. The Assistant remains lightweight and tenant-scoped, while organisational state, capacity, work routing, events and execution infrastructure can scale independently.

Consequences

- CEO is a consumer of the Organisation, not the Organisation itself.
- Capability discovery and execution are explicitly Operations-plane concerns.
- Enterprise knowledge (EIMS) is accessed by the Organisation but owned by the Organisation.
- The Assistant is inside the Organisation, not outside it.
- The Chat/API/UI/Voice layer is outside the Organisation.

Related

- ADR-018: Role vs Person vs Agent
- ADR-022: OrganisationControlPlane abstraction
- ADR-024: CEO as organisational Role
- ADR-025: Assistant as Organisational Role/Interface, not Implicit CEO
