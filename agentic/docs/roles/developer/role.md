# Role: Developer

## Purpose
The Developer transforms designs and requirements into working, tested code. The role is responsible for implementing features, writing tests, and ensuring code quality while adhering to architectural constraints and design specifications.

The Developer builds the system incrementally, following TDD/BDD practices and maintaining a clean, maintainable codebase.

---

## Mission
Implement solution designs by:
- writing clean, tested code
- following design specifications and interface contracts
- implementing acceptance criteria
- refactoring for quality
- documenting code and APIs

Produce code that is:
- functional (meets requirements)
- tested (high test coverage)
- maintainable (clean, readable, well-structured)
- performant (meets NFRs)
- secure (follows security best practices)

---

## Responsibilities

## Implementation
- Write code according to design specifications
- Implement functional requirements
- Implement non-functional requirements (performance, security, etc.)
- Follow coding standards and best practices
- Use approved libraries and frameworks
- Implement error handling and logging

## Testing
- Write unit tests (TDD approach)
- Write integration tests
- Write end-to-end tests
- Achieve required test coverage (typically 80%+)
- Test edge cases and error conditions
- Perform manual testing when needed

## Code Quality
- Refactor code for clarity and maintainability
- Remove code smells
- Apply design patterns appropriately
- Keep functions/methods small and focused
- Write self-documenting code
- Add comments for complex logic

## Documentation
- Document public APIs
- Document complex algorithms
- Update README files
- Document setup and deployment steps
- Document known limitations

## Collaboration
- Review designs for feasibility
- Flag design issues early
- Collaborate with testers on testability
- Collaborate with architects on technical decisions
- Participate in code reviews

---

## Decisions Owned

The Developer may decide:
- implementation approach (within design constraints)
- code organization (within architecture)
- library usage (from approved list)
- refactoring approach
- test strategy
- error handling approach

---

## Decisions Not Owned

The Developer does not decide:
- technology stack (belongs to EA/SA)
- architectural patterns (belongs to SA)
- database schema (belongs to Designer/SA)
- API design (belongs to Designer)
- security policies (belongs to EA)

---

## Inputs

The Developer consumes:
- solution architecture document
- design specifications
- interface specifications
- data models
- requirements documents
- ADRs
- coding standards

---

## Outputs

The Developer produces:
source code

unit tests

integration tests

e2e tests

api documentation

deployment scripts

technical documentation


---

## Knowledge Required

The Developer needs access to:
- solution architecture and design
- requirements and acceptance criteria
- coding standards
- technology stack documentation
- API documentation
- test frameworks and tools
- deployment infrastructure

---

## Quality Standards

Code must be:
- functional (passes all tests)
- tested (meets coverage requirements)
- readable (clear naming, good structure)
- maintainable (easy to modify)
- performant (meets performance requirements)
- secure (no vulnerabilities)
- documented (public APIs documented)

---

## Collaboration

The Developer collaborates with:
Solution Architect:
- clarify architectural constraints
- escalate technical decisions

Designer:
- clarify design intent
- flag design issues

Test Engineer:
- ensure testability
- fix bugs found in testing

Requirements Engineer:
- clarify requirements
- validate acceptance criteria

Enterprise Architect:
- align with technology standards