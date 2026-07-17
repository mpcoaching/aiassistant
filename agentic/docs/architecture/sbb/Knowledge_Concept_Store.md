# Knowledge & Concept Store (Solution Building Block)

## Definition
The Knowledge & Concept Store is the persistent home of the enterprise's enduring cognitive assets: the **Knowledge** epistemic graph and the **Enterprise Concept** library (including Concept Payloads of `kind=solved_approach`). It is where the Learning Loop writes what the enterprise has learned, and where Strategy Selection and the Assistant Reasoning Service read to recognise prior solutions.

## Purpose
To make enterprise knowledge first-class and durable (Principle 3 / 9): a structured, queryable, version-controlled store of concepts, decisions, playbooks, and the semantic knowledge graph — separate from transient Session state and from individual agent research stores (which are promoted *into* this store).

## Key Responsibilities
*   **Concept Storage**: Persist Enterprise Concept records by `kind` (e.g. `solved_approach` Concept Payload, `tool|skill` Capability metadata, ADRs, playbooks, policies).
*   **Knowledge Graph**: Maintain the semantic/epistemic graph (vector layer in Qdrant; structured layer in Postgres) and route `KnowledgeChunkDiscovered` events to the correct store by semantic tag.
*   **Retrieval**: Support Level 1 (direct) pattern/Concept lookup by ContextRecord and semantic similarity (Qdrant), feeding Pattern Recognition.
*   **Versioning & Governance**: Version concepts; gate Concept Payload promotion (`draft → active`) with audit sampling; record provenance (which Session produced it).
*   **Maturation Write-back**: Accept playbook deltas and SOP promotions from the Learning Loop with strict persistence.

## Interactions
*   **Exposes**: Query API (by kind, tag, similarity), write API (Learning Loop, Service Authoring).
*   **Consumes**: `KnowledgeChunkDiscovered` events (from the Event Bus subscriber), playbook deltas / Concept Payloads (from the Learning Loop), Service definitions (from Service Authoring).
*   **Publishes**: Concept-available events to the Capability Registry and Observability.
*   **Read by**: Assistant Reasoning Service (recognition), Strategy Selection (seed data), Pattern Recognition.

## Data Ownership
*   **Source of Truth for**: Enterprise Concepts, Concept Payloads, the semantic Knowledge graph, playbook/ADR/policy records.

## Cognition Alignment
*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** The realization of **Enterprise Concepts / Knowledge** (anchor doc §9) — the central noun of the type system. Concept Payload (`kind=solved_approach`) and Capability (`kind=tool|skill`) share this one store/type system.
- **Vocabulary map:** "vector store / Qdrant" → the semantic layer of the Knowledge graph; "playbook / SOP / decision record" → Concept Payload or ADR concepts; "knowledge chunk" → `KnowledgeChunkDiscovered` ingestion (§9.2).
- **Relationship to core:** This is the *enterprise* store (durable); distinct from an agent's *personal* research store (`AGENTIC-EXPERIENCE.md`). The Learning Loop writes here; Recognition reads here.
- **No rename:** "knowledge store" / "concept store" retained as implementation terminology.
