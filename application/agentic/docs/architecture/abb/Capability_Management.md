# Capability Management (Enterprise Building Block)

## Overview
**Capability Management** is the enterprise capability to define, register, govern, discover, and evolve the Catalog of **Capabilities** the Agentic system can invoke — every `kind=tool|skill` Enterprise Concept, including business Services, tools, and skills. It is the governance wrapper around the Capability Registry.

## Capabilities
*   **Capability Definition**: Establish the structure and metadata for new Capabilities (name, kind, `execution_mode`, `ai_spec`/compiled ref, inputs/outputs, version).
*   **Registry Governance**: Single source of truth for Capability discovery and resolution; enforce access policy and versioning.
*   **Maturation & Promotion**: Track invocation/correction history; promote `ai_mediated → compiled` via the Learning Loop (never auto-deploy — review gate).
*   **Lifecycle Control**: Deprecate, retire, and audit Capabilities.

## Business Value
*   **Discoverability**: any participant (human or AI) finds and invokes a Capability without knowing its implementation.
*   **Stable abstractions**: Capabilities are classification constructs, not "thinking" components (Principle 10); they decouple reasoning from execution.
*   **Controlled evolution**: promotion and retirement are governed, not ad hoc.

## Data Entities (Owned)
*   **Capability**: an Enterprise Concept record (`kind=tool|skill`) with `execution_mode`, interfaces, and maturation history.

## Interactions
*   **Realized via**: `Capability_Registry_Service` SBB (storage/resolution), `Service_Authoring` SBB (creation), `Knowledge_Concept_Store` SBB (persistence of promoted assets).
*   **Consumed by**: Assistant Reasoning Service, Workflow Engine, Agent Orchestrator (Capability resolution at Session execution).
*   **Feeds**: Strategy Selection (seed data) and the Learning Loop (promotion).

## Relationship to Cognition Model
First-class reasoning-core ABB. Realizes the **Capability** layer of `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §10 — the single type system where Concept Payload (`solved_approach`) and Capability (`tool|skill`) coexist. The single-registry intent (ADR §7 item 11, open) is modeled here as one governed catalog; the open question is flagged, not resolved.
