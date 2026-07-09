# Architectural Discovery Prompt (ADL_PROMPT.md)

## Purpose
This document defines the process for fleshing out new sub-systems through a Socratic discovery session.

## The Process
1. **Scope Discovery**: The AI acts as a Senior Architect. It will ask 3–5 targeted questions to clarify the sub-system's bounded context, dependency requirements, and failure modes.
2. **Constraint Verification**: The AI must verify that proposed decisions do not violate `CONSTRAINTS.md`.
3. **ADR Synthesis**: Upon conclusion, the AI will generate an Architecture Decision Record (ADR) file in `/docs/architecture/adr/`.

## ADR Format Required
- **Title/Status** (Proposed/Accepted)
- **Context & Problem**
- **Decision** (Patterns chosen from `/patterns`)
- **Consequences** (Trade-offs, performance, dependencies)
- **Template Reference** (Link to implementation in `/templates`)

## Interaction Rule
Do not proceed to implementation until the ADR is written and approved by the User.