# Capability Registry Service (Solution Building Block)

## Definition
The Capability Registry Service is the unified, authoritative catalog of every **Capability** the Agentic system can discover and invoke. A Capability is an Enterprise Concept record of `kind=tool|skill` describing *what the business does* and how to invoke it. It subsumes the prior Tool Registry and Agent Registry into one registry of record (the single-registry intent of ADR §7 item 11).

## Purpose
To let the reasoning core — and any participant, human or AI — discover, version, and securely invoke Capabilities without knowing their implementation. It is the bridge between the *durable Services* the enterprise operates and the *transient Sessions* that call them.

## Key Responsibilities
*   **Capability Storage**: Persist Capability records (`name`, `kind`, `description`, `execution_mode`, `ai_spec` / `compiled_ref`, `inputs`, `outputs`, `version`).
*   **Unified Resolution**: Resolve a Capability `name` (+`kind`) to its active implementation — Tier 2 (in-process) or Tier 3 (bus-mediated) transport (ADR §6.2).
*   **Discovery**: Search by capability, kind, or semantic tag; surface to the Assistant Reasoning Service and to MCP authoring.
*   **Lifecycle & Promotion**: Track maturation history (invocation count, correction rate, compilation candidacy); support `ai_mediated → compiled` promotion via the Learning Loop.
*   **Governance**: Enforce access policy and publish `CapabilityRegistered`/`Updated`/`Deregistered` events.

## Interactions
*   **Exposes**: RESTful API for Capability CRUD, resolution, and discovery (including MCP `list_skills`/`list_capabilities`).
*   **Consumes**: Capability definitions from authoring (Service Authoring, Compiler) and from the Learning Loop (promoted Skills / Concept Payloads).
*   **Publishes**: `CapabilityRegistered`, `CapabilityUpdated`, `CapabilityDeregistered` to the Agent Bus.
*   **Called by**: Assistant Reasoning Service, Workflow Engine, Agent Orchestrator (to resolve a step's Capability at Session execution time).

## Data Ownership
*   **Source of Truth for**: Capability Definitions, Capability Interfaces, Invocation metadata, Maturation history.

## Cognition Alignment
*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** The **Capability Registry** — one registry holding Enterprise Concept records of `kind=tool|skill` (anchor doc §10). This is the unified home for Tools *and* Skills *and* the business Services (Work Session, Task Tracking, Lead Enrichment) once they are modeled as Capabilities.
- **Vocabulary map:** "tool definition" / "skill record" / "agent capability" → a **Capability** record with `execution_mode: ai_mediated | compiled` (the `prompt|code|distilled` → `ai_mediated|distilled|compiled` lineage, §10). "Tool invocation" → Tier 2 / Tier 3 Capability transport.
- **Relationship to core:** Replaces the separate `sbb/tool_registry.md` and `sbb/agent_registry.md` boundaries. The *service boundary* question (ADR §7 item 11) remains open, but the **record shape and single type system are mandated**; this SBB is written to the single-registry intent.
- **No rename:** "registry" terminology retained; it is now explicitly the Capability Registry.
