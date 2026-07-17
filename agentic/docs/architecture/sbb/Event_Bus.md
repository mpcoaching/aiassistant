# Event Bus (Solution Building Block)

## Definition
The Event Bus is the asynchronous messaging backbone that connects the Agentic system's components. It carries lifecycle events (Session/workflow, task, lead, agent), Capability request/reply envelopes for Tier-3 (bus-mediated) invocations, and the `KnowledgeChunkDiscovered` events that feed the epistemic Knowledge graph.

## Purpose
To decouple producers from consumers so that Intents, Sessions, and Capability calls can be choreographed asynchronously and durably, without synchronous coupling between the reasoning core and the Services it invokes.

## Key Responsibilities
*   **Topic / Exchange Topology**: Manage exchanges (e.g. `workflow.mode`) and routing keys (`workflow.lifecycle.*`, `skill.requested`, `skill.completed`, `capability.request`/`capability.reply`, `knowledge.chunk.discovered`).
*   **Durable Delivery**: Durable queues + `correlation_id` for crash recovery and exactly-once-ish step progression.
*   **Tier-3 Capability Transport**: Carry Request-Reply envelopes for Capabilities invoked across process/service boundaries (ADR §6.2), distinct from Tier-2 in-process calls.
*   **Fallback Spooling**: Spool undeliverable events (bus fallback) for later replay.
*   **Lifecycle Broadcasting**: Surface `workflow.lifecycle.*` / `WorkSessionStarted` / `TaskStatusUpdated` / `LeadEnriched` to subscribers (UI, Observability, Learning Loop).

## Interactions
*   **Exposes**: Publish/subscribe API and AMQP-style topology management.
*   **Consumes**: Events from every SBB (Agent Orchestrator, Workflow Engine, Capability Registry, Services, Observability).
*   **Publishes**: All routed events to their subscribers.
*   **Underpins**: Choreographed execution in the workflow-runner; Tier-3 Capability invocation; Knowledge propagation.

## Data Ownership
*   **Source of Truth for**: In-flight message/event state and delivery guarantees (not business data — that stays with the owning Service).

## Cognition Alignment
*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** The transport layer for the **Knowledge** graph and for **Tier-3 Capability** invocations (anchor doc §9.2, §10). Frameworks are runtimes (Principle 7); the bus is a runtime transport concern handled by the adapter layer, never leaking into Context/Session/Pattern schemas.
- **Vocabulary map:** "agent bus / workflow.mode exchange" → the event backbone; `KnowledgeChunkDiscovered` → the epistemic-graph ingestion event (§9.2); capability request/reply → Tier-3 Capability envelope.
- **Relationship to core:** Every business Service (Work Session, Task Tracking, Lead Enrichment) publishes lifecycle events here; the Learning Loop and Observability consume them. The bus is how a transient **Session** reaches a durable **Service** Capability without synchronous coupling.
- **No rename:** "event bus" / "agent bus" retained as implementation terminology.
