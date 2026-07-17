# Knowledge Management (Enterprise Building Block)

## Overview
**Knowledge Management** is the enterprise capability to capture, structure, version, and evolve the enterprise's enduring cognitive assets — the **Knowledge** epistemic graph and the **Enterprise Concept** library (including Concept Payloads of `kind=solved_approach`). It is the governance and stewardship layer over the Learning Loop's outputs.

## Capabilities
*   **Concept Stewardship**: Define, version, and retire Enterprise Concepts by `kind` (Concept Payload, Capability metadata, ADR, playbook, policy).
*   **Knowledge Graph Governance**: Maintain the semantic/epistemic graph; route `KnowledgeChunkDiscovered` events to the correct store by semantic tag; manage Qdrant + Postgres layers.
*   **Promotion & Audit**: Gate Concept Payload promotion (`draft → active`) with random audit sampling; record provenance (producing Session).
*   **Retrieval & Reuse**: Serve Level 1 (direct) recognition lookups to Strategy Selection and the Assistant Reasoning Service.

## Business Value
*   **Durable enterprise memory**: knowledge outlives individual agents and Sessions (Principle 3 / 9).
*   **Learning as asset update**: successful reasoning becomes reusable, governed assets rather than ephemeral outputs.
*   **Recognition before reasoning**: a rich, queryable store lets known solutions short-circuit exploration (Principle 1).

## Data Entities (Owned)
*   **Enterprise Concept**: the central noun — Concept Payload (`solved_approach`), Capability metadata, ADR, playbook, policy records, and the semantic Knowledge graph.

## Interactions
*   **Realized via**: `Knowledge_Concept_Store` SBB (persistence), the Event Bus (ingestion of `KnowledgeChunkDiscovered`), the Learning Loop (write-back).
*   **Consumed by**: Assistant Reasoning Service, Strategy Selection, Pattern Recognition (read), Service Authoring (prior-art lookup).
*   **Distinct from**: individual agent research stores (`AGENTIC-EXPERIENCE.md`) — those are transient and promoted *into* this enterprise store.

## Relationship to Cognition Model
First-class reasoning-core ABB. Realizes **Enterprise Concepts / Knowledge** in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §9. Concept Payload and Capability share one type system; this ABB governs the Concept half, while `Capability_Management` governs the Capability half, both persisting through `Knowledge_Concept_Store`.
