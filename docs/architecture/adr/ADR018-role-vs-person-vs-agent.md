# ADR-018: Role vs Person vs Agent

Status: Accepted

Decision

The domain model distinguishes three concepts: Role, Person, and Agent. They are separate types with separate lifecycles and ownership.

Context

The system needs to model "who does what" but currently conflates organisational positions, human individuals, and runtime executors. This makes authority delegation, capability assignment, and accountability ambiguous.

Decision

1. Role is an abstract position with responsibilities, authority, constraints, and information access. Owned by Organisation-Control. It is a template/blueprint; not a person or agent.

2. Person is a human individual. Owned by People/Capability domain. Has identity and employment context.

3. Agent is a software entity that performs work. Owned by Operations plane. Has runtime identity and executes patterns.

Distinctions

- Role != Person: A Role is an abstract position. A Person occupies a Role.
- Role != Agent: A Role defines what is needed. An Agent is a runtime executor that may fulfil a Role.
- Person != Agent: A Person is human. An Agent is software.

A role may be fulfilled by:
- a human Person
- an AI Agent
- potentially a combination of human and agent

Rationale

1. Authority and accountability flow through Roles, not through runtime agents.
2. The same Role can be occupied by different Persons over time.
3. Agents can fulfil Roles without the Role knowing the Agent's implementation details.
4. Capabilities are assigned to Roles, not to specific runtime agents.

Consequences

- Role records must not contain runtime execution logic.
- Person records must not contain capability definitions.
- Agent records must not contain authority grants.
- The OrganisationControlPlane coordinates Roles; it does not execute via Agents.

Related

- ADR-017: Three-Plane Architecture
- ADR-019: Authority and Delegation Boundary
- ADR-022: OrganisationControlPlane Abstraction
