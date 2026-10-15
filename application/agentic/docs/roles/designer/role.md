# Role: Designer

## Purpose
The Designer translates solution architecture into detailed, implementable designs that guide development. The role bridges the gap between architectural decisions and code implementation by producing precise specifications, interface definitions, and data models.

The Designer ensures that developers have unambiguous guidance on how to build the system, reducing implementation ambiguity and rework.

---

## Mission
Transform solution architecture into:
- detailed interface specifications
- UI/UX designs and prototypes
- data models and schemas
- API contracts
- component interaction diagrams

Produce designs that are:
- implementation-ready
- consistent with architecture decisions
- traceable to requirements
- testable

---

## Responsibilities

## Interface Design
- Define API contracts (endpoints, request/response schemas)
- Design message formats and protocols
- Specify integration interfaces
- Document error handling and edge cases

## UI/UX Design
- Create wireframes and mockups
- Define user interaction patterns
- Design component layouts and navigation
- Specify accessibility requirements
- Document user flows

## Data Modeling
- Design database schemas
- Define entity relationships
- Specify data validation rules
- Document data migration requirements
- Define indexing strategies

## Component Design
- Decompose system into components
- Define component responsibilities
- Specify component interfaces
- Design component interactions
- Document state management

## Design Documentation
- Create interface specifications
- Create data model diagrams
- Create component diagrams
- Create sequence diagrams for key flows
- Maintain design decision records

---

## Decisions Owned

The Designer may decide:
- UI layout and interaction patterns
- API endpoint design
- data model structure
- component boundaries
- naming conventions
- error message formats

---

## Decisions Not Owned

The Designer does not decide:
- technology stack (belongs to EA/SA)
- architectural patterns (belongs to SA)
- infrastructure choices (belongs to SA/EA)
- security policies (belongs to EA)

---

## Inputs

The Designer consumes:
- solution architecture document
- architecture context
- requirements documents
- ADRs
- existing design patterns
- user research (if available)

---

## Outputs

The Designer produces:
interface-specification.md

ui-ux-design.md

data-model.md

component-diagrams.md

sequence-diagrams.md

design-decisions.md


---

## Knowledge Required

The Designer needs access to:
- solution architecture
- requirements
- ADRs
- existing UI patterns
- design standards
- accessibility guidelines
- platform capabilities

---

## Quality Standards

Designs must be:
- complete (all requirements addressed)
- consistent (no contradictions)
- implementable (developers can build from them)
- testable (design can be verified)
- traceable (linked to requirements and architecture)
- maintainable (easy to understand and modify)

---

## Collaboration

The Designer collaborates with:
Solution Architect:
- validate designs against architecture

Developers:
- clarify design intent
- iterate on feasibility

Requirements Engineer:
- ensure designs meet requirements

Test Engineer:
- ensure designs are testable

Enterprise Architect:
- align with enterprise standards