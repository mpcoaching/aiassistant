# ADR-041: People/Capability Plane Package Structure

Status: Accepted

Decision

The People/Capability plane is implemented as a first-class package alongside the other
three planes (Enterprise, Organisation/Control, Operations).

Context

ADR-026 established People/Capability as a peer domain plane. ADR-037 established that
Person and Agent records belong to People/Capability. However, Person and Agent classes
are currently defined in `packages/organisation/src/role.py`, and `Capability` is defined
in `packages/capability_registry/src/capabilities.py`. This violates the plane boundaries.

Decision

1. **New package:** `packages/people_capability/src/`

2. **Module structure:**
   - `__init__.py` — package exports
   - `person.py` — `Person` record (moved from organisation)
   - `agent.py` — `Agent` record (moved from organisation)
   - `capability.py` — `Capability` record (moved from capability_registry)
   - `capability_assignment.py` — `CapabilityAssignment` record
   - `capability_proficiency.py` — `CapabilityProficiency` record
   - `people_capability_service.py` — `PeopleCapabilityService` interface + in-memory impl

3. **Organisation/Control references Person/Agent by ID only:**
   - `packages/organisation/src/role.py` imports Person/Agent from people_capability
   - `OrganisationControlPlane.assign_work()` accepts `Role | Person | Agent` but does not
     store Person/Agent records

4. **capability_registry depends on people_capability:**
   - `CapabilityRegistry` imports `Capability` from people_capability
   - `capability_registry` does NOT define the Capability domain model

5. **Import rules:**
   - `people_capability` imports only pydantic (no organisational, operational, or EIMS imports)
   - `organisation` imports `Person`, `Agent` from `people_capability` (for type hints and IDs)
   - `capability_registry` imports `Capability` from `people_capability`
   - `operations` imports `Capability` from `people_capability` (read-only for execution)

Rationale

1. Domain models must live in the plane that owns them.
2. Person/Agent are People/Capability domain records, not Organisation/Control mechanism records.
3. Capability is a People/Capability domain record, not an operational registry record.
4. Clear package boundaries prevent accidental boundary crossing.

Consequences

- `packages/organisation/src/role.py` will lose Person/Agent class definitions
- `packages/capability_registry/src/capabilities.py` will lose Capability class definition
- Existing tests that import from these modules will need updated import paths
- The capability_registry package becomes a registry service, not a domain model owner

Related

- ADR-013: Capability-Oriented Repository Structure
- ADR-017: Three-Plane Architecture
- ADR-026: People/Capability as Peer Domain Plane
- ADR-037: Person/Agent Ownership by People/Capability
- ADR-040: Capability Assignment and Proficiency Model
