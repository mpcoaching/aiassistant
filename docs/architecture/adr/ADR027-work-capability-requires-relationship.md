# ADR-027: Work-Capability "Requires" Relationship

Status: Accepted

Decision

Work references required capabilities but does NOT own capability lifecycle. The relationship is expressed as a list of capability references on Work, not as embedded capability definitions. Work owns the "what needs to be done"; People/Capability owns the "what capabilities exist to do it."

Context

Increment 6 introduced Work as an organisational record. The Increment 7 investigation revealed that Work must express its capability requirements without crossing into the People/Capability domain. Similarly, People/Capability must not own Work instances.

Decision

1. Work contains `required_capability_ids: list[str]` — references to existing Capability IDs, not embedded capability definitions.

2. Work contains `acceptance_criteria: list[str]` — operational outcomes expected from completion.

3. Work does NOT contain:
   - Capability definitions
   - Capability specifications
   - Capability matching logic
   - Capability execution logic

4. People/Capability does NOT contain:
   - Work instances
   - Work assignment logic
   - Work status tracking

5. The relationship is asymmetric:
   - Work -> requires -> Capability (Work declares what it needs)
   - Capability -> fulfils -> Work (Capability is used to satisfy Work requirements)
   - Work -> assigned to -> Role/Person/Agent (Organisation/Control decides who does the work)
   - Person/Agent -> possesses -> Capability (People/Capability tracks who has what skills)

6. When a Work item is created and no matching capability exists, the organisational response is a CapabilityRequest (transient governance artifact) to People/Capability, NOT direct capability definition in Work.

Relationship Diagram

    Work
      |
      | required_capability_ids
      v
    Capability (People/Capability domain)
      ^
      | possesses / fulfils
    Person / Agent (People/Capability domain)

    Work
      |
      | assigned to
      v
    Role / Person / Agent (Organisation/Control domain)

Rationale

1. Work is about effort allocation; Capability is about reusable ability. Mixing them collapses domain boundaries.
2. Referencing capabilities by ID keeps Work lightweight and decoupled.
3. The "requires" relationship is directional and explicit, avoiding circular dependencies.
4. When capabilities are missing, the gap flows through organisational channels (CapabilityRequest), not through Work self-definition.

Consequences

- Work model gains `required_capability_ids` and `acceptance_criteria` fields.
- Capability matching happens at the operational level, not embedded in Work.
- CapabilityRequest is triggered when Work requires a capability that does not exist.
- The CEO observes capability gaps but does not resolve them directly.

Related

- ADR-020: Capability Ownership by People/Capability
- ADR-026: People/Capability as Peer Domain Plane
- ADR-022: OrganisationControlPlane Abstraction
