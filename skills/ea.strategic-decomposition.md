# Skill: EA Strategic Decomposition

## Purpose
Map business-level roadmap phases to a stable technical foundation by decomposing into functional capabilities, subsystems, and enterprise building blocks.

## Inputs
- business-roadmap
- enterprise-architecture
- system-context

## Process

### 1. Read Roadmap
Read the business roadmap to understand:
- Phases and their scope
- Business objectives for each phase
- Timeline and dependencies
- Success criteria

### 2. Decompose into Functional Capabilities
For each roadmap phase:
- Identify the functional capabilities needed
- Break down capabilities into smaller, testable units
- Map capabilities to business objectives
- Identify capability dependencies

### 3. Identify Subsystem Topology
For each capability:
- Identify required subsystems/services
- Define subsystem boundaries
- Identify integration points
- Determine communication patterns (sync/async, event-driven, request-reply)

### 4. Update System Context
Update or create `docs/SYSTEM_CONTEXT.md` to show:
- How new subsystems fit into the existing ecosystem
- External dependencies
- Data flow boundaries
- User interactions

### 5. Define Interfaces
For each subsystem:
- Identify the Source of Truth for each data entity
- Define high-level contracts
- Specify integration patterns
- Document API boundaries

### 6. Identify Enterprise Building Blocks (ABBs)
For each significant capability, describe and define:
- **Agent Management** - How agents are registered, discovered, and orchestrated
- **Automated Task Execution** - How tasks are scheduled, executed, and monitored
- **Control Center** - How users interact with the system
- **Lead Enrichment** - How data is enhanced and enriched
- **Operational Visibility** - How the system is monitored and observed
- **Solution Templating** - How solutions are templated and instantiated
- **Task Tracking** - How tasks are tracked and managed
- **Tooling Integration** - How external tools are integrated
- **Work Session** - How work sessions are managed

Create one file per ABB in `/docs/architecture/abb/` with:
- Name and purpose
- Capabilities provided
- Relationships to other ABBs
- Implementation guidelines

### 7. Define Solution Building Blocks (SBBs)
For each ABB, identify the implementation components:
- Services
- APIs
- Data stores
- Message queues
- External integrations

Create one file per SBB in `/docs/architecture/sbb/` with:
- Name and purpose
- Technology choices
- Interfaces
- Deployment considerations

### 8. Create Phase Documentation
For each roadmap phase, create:
- **Phase-x-ABBs.md** - Overview of ABBs for the phase
- **Phase-x-SBBs.md** - Overview of SBBs for the phase
- **Phase-x-BACKLOG.md** - Backlog items with status:
  - Not started
  - Architecturally specified
  - System design complete
  - Coded
  - Tested
  - Complete

### 9. Identify Follow-up Work
List subsystems that require:
- Follow-up `architectural-discovery` sessions
- Detailed system design
- Implementation planning

## Output
- capability-map.md
- abb-definitions/ (directory with one file per ABB)
- sbb-definitions/ (directory with one file per SBB)
- phase-backlog.md
- updated system-context.md

## Quality Criteria
- **Completeness**: All roadmap phases are decomposed
- **Traceability**: Every capability maps to a business objective
- **Clarity**: Boundaries and interfaces are clearly defined
- **Reusability**: ABBs are generic and reusable across solutions
- **Technology Independence**: ABBs are business-focused, not implementation-focused