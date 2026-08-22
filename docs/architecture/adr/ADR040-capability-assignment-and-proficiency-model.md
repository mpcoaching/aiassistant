# ADR-040: Capability Assignment and Proficiency Model

Status: Accepted

Decision

Capability possession by Person/Agent is modelled through explicit records, not implied by
role occupancy or capability requirement declarations.

Context

The current model has `required_capability_ids: list[str]` on Role and Work, but no model
for who actually possesses/possessed a capability, at what proficiency, with what authorisation.
This makes it impossible to determine capability availability, gaps, or transfer history.

Decision

1. **CapabilityAssignment** links a Person/Agent to a Capability:
   - `person_id` or `agent_id`
   - `capability_id`
   - `assignment_type` (primary, secondary, backup)
   - `status` (active, suspended, expired)
   - `assigned_at`, `expires_at`
   - `authorised_by` (role or person who authorised)

2. **CapabilityProficiency** describes how well a Person/Agent can exercise a Capability:
   - `person_id` or `agent_id`
   - `capability_id`
   - `proficiency_level` (novice, competent, proficient, expert, master)
   - `validated_at`, `valid_until`
   - `evidence` (certifications, test results, observed performance)

3. These records live in the People/Capability plane.

4. Operations may read them for authorisation checks but does not create/update them.

5. Capability transfer is modelled as:
   - Create new CapabilityAssignment for new holder
   - Retire old CapabilityAssignment (status = expired/revoked)
   - Preserve history (assignments are never deleted)
   - Re-evaluate CapabilityProficiency for new holder

Rationale

1. A capability is a portable organisational asset. Its assignment history is enterprise knowledge.
2. "Requires" and "Possesses" are distinct relationships with different semantics.
3. Explicit records enable gap analysis, capability transfer, and proficiency tracking.
4. This preserves the four-plane separation: People/Capability owns assignment/proficiency;
   Operations consumes; Organisation/Control references.

Consequences

- `required_capability_ids` on Role and Work remains a declaration only.
- Capability availability is determined by CapabilityAssignment records, not by role occupancy.
- People/Capability is responsible for maintaining assignment and proficiency records.
- Operations may eventually check CapabilityAssignment before executing a capability.

Related

- ADR-018: Role vs Person vs Agent
- ADR-020: Capability Ownership by People/Capability
- ADR-026: People/Capability as Peer Domain Plane
- ADR-027: Work-Capability "Requires" Relationship
- ADR-037: Person/Agent Ownership by People/Capability
