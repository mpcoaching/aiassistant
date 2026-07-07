# Create Complete Solution Architecture Documents

## Objective

You are acting as a Senior Enterprise Solution Architect.

Your responsibility is to transform the existing enterprise architecture into a complete implementation-ready Solution Architecture.

The output must be sufficiently detailed that either:

- a senior software engineer
- or an AI coding agent (Aider, Claude Code, OpenHands, etc.)

can implement the solution without making architectural decisions.

You are **not** writing production code.

You are writing the documents that define exactly what code should be written.

---

# Architecture Governance

This repository follows Architecture Decision Records (ADRs).

All architectural decisions MUST be governed by the ADRs.

Before creating any Solution Architecture documentation:

1. Read every ADR located in

```
/docs/architecture/adr/
```

2. Treat every accepted ADR as mandatory.

3. Ensure all generated Solution Architecture documents comply with the ADRs.

4. Do not introduce architectural patterns that conflict with an existing ADR.

5. If multiple ADRs apply, follow all of them.

6. If an ADR conflicts with another architecture document, record the conflict in

```
/docs/architecture/OPEN_QUESTIONS.md
```

Do not silently choose one over another.

---

# Creating New ADRs

While expanding the Solution Architecture, you may discover implementation decisions that have not yet been formally documented.

Whenever you make a significant architectural decision that is not already covered by an existing ADR, you MUST create a new ADR.

Create it under

```
/docs/architecture/adr/
```

using the next available ADR number.

Follow the standard ADR format.

Each ADR should include

- Title
- Status
- Context
- Decision
- Consequences
- Alternatives Considered
- Related Documents
- Related Components

Only create ADRs for significant architectural decisions.

Examples include

- architectural patterns
- messaging strategies
- persistence approaches
- authentication methods
- deployment topology
- technology selections
- integration patterns
- API standards
- testing strategies
- error handling strategies
- security models
- event design
- versioning approaches

Do NOT create ADRs for implementation details.

---

# ADR Compliance

Before completing the Solution Architecture, perform an ADR compliance review.

Verify that every Solution Architecture document

- follows existing ADRs
- references applicable ADRs
- does not introduce conflicting patterns

Every generated component document should contain an "Architecture Decisions" section listing the ADRs that apply.

Example

```
## Architecture Decisions

- ADR-0003 Event Driven Communication
- ADR-0007 Repository Pattern
- ADR-0012 API Versioning
```

---

# Source Documents

Treat the following documents as the source of truth.

Read completely before producing any output.

Required documents:

```
/docs/architecture.md
/docs/system_context.md
/docs/system_design.md
/docs/roadmap.md
```

Read every document located in

```
/docs/architecture/sa/
```

This folder contains:

- ABBs
- SBBs
- domain models
- interface specifications
- existing design decisions

These are authoritative.

Do not contradict them.

---

# Goal

Produce a complete Solution Architecture package.

The package should remove ambiguity from implementation.

Every functional requirement should be represented.

Every architectural decision should be documented.

Every interface should be defined.

Every dependency should be explicit.

Every behaviour should be testable.

---

# Continuous Architecture Improvement

While producing the Solution Architecture, continuously evaluate whether the existing architecture can be improved.

If improvements are identified:

- preserve backwards compatibility where possible
- document the rationale
- create or update the relevant ADR
- update affected Solution Architecture documents
- never silently change an architectural pattern

Where improvements are merely suggestions rather than required decisions, record them in

```
/docs/architecture/FUTURE_ADRS.md
```

These should describe architectural opportunities that may be adopted later without affecting the current implementation.
