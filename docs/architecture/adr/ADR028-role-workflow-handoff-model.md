# ADR-028: Role Workflow Handoff Model for Specialist Roles

Status: Accepted

Decision

Specialist roles (EA, SA, BA, Designer, Developer, QA) are modelled as Roles in the Organisation/Control plane. Work flows between them through explicit assignment and handoff, not through implicit CEO routing. Each role produces durable enterprise assets consumed by downstream roles.

Context

The Increment 7 investigation explored how EA/SA/BA/Designer/Developer/QA roles fit into the organisational model. The critical distinction is between:
- organisational role (position with authority and responsibilities)
- capability (reusable ability to perform work)
- workflow/pathway (sequence of operational steps)
- work product / enterprise asset (durable output of work)

These must remain distinct concepts. Collapsing them for implementation convenience creates God roles and unmaintainable workflows.

Decision

1. EA, SA, BA, Designer, Developer, QA are all Roles in the Organisation/Control plane.

2. Work flows between roles through explicit Assignment records:
   - BA produces requirements (enterprise asset)
   - EA/S A produces architecture/design (enterprise asset)
   - Developer produces implementation (enterprise asset)
   - QA produces verification results (enterprise asset)

3. Each role may require specific capabilities to fulfil its work:
   - Developer requires coding, testing capabilities
   - QA requires verification, validation capabilities
   - BA requires elicitation, modelling capabilities

4. The CEO coordinates role assignments and escalations but does NOT execute role-specific work.

5. Handoff between roles is a Work transition:
   - Work.status moves from ASSIGNED to IN_PROGRESS to COMPLETED
   - New Work is created for the next role with references to the previous Work's outputs
   - Assignment links Work to the receiving role

Role-Capability-Work Model

    Role (EA)
      |
      | requires
      v
    Capability (architecture_modelling)
      |
      | fulfils
      v
    Work (Design system architecture)
      |
      | produces
      v
    EnterpriseConcept (architecture_decision)
      |
      | becomes input to
      v
    Work (Implement architecture)
      |
      | assigned to
      v
    Role (Developer)

Rationale

1. Explicit role definitions make authority, accountability, and information access auditable.
2. Work handoffs create traceable chains of responsibility.
3. Enterprise assets as Work outputs make institutional learning possible.
4. Separating role, capability, workflow, and work product prevents architectural collapse.

Consequences

- Organisation/Control plane manages role lifecycle and work assignment.
- People/Capability plane manages capability definitions and matching.
- Operations plane executes Work through workflows/sessions.
- EIMS stores durable Work outputs as EnterpriseConcepts.
- CEO observes and coordinates but does not execute role-specific logic.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-026: People/Capability as Peer Domain Plane
- ADR-027: Work-Capability "Requires" Relationship
