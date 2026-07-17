# Service Composition (Enterprise Building Block)

## Overview
**Service Composition** is the enterprise capability to *design, create, and orchestrate* the Services and Capabilities the Agentic system operates — including the business Services (Work Session, Task Tracking, Lead Enrichment) and the tools/skills they expose. It is the enterprise-facing expression of the reasoning core's ability to not just run processes, but to **reason about and build** the things it runs.

## Capabilities
*   **Service Design**: Conceive a new or adapted Service from a reasoned need (data entities, API surface, Capability contract, policy checks).
*   **Service Creation**: Scaffold, validate, and register a Service as a durable **Capability** (`kind=tool|skill`) in the Capability Registry.
*   **Session Composition**: Assemble a transient **Session** (workflow) that orchestrates one or more Services/Capabilities to achieve an Intent.
*   **Lifecycle Governance**: Version, deprecate, and retire Services; manage promotion of `ai_mediated` → `compiled` Capabilities.

## Business Value
*   **Self-improving enterprise**: the system grows its own capability surface rather than only consuming a fixed set.
*   **Reuse over rebuild**: designed Services become discoverable Capabilities, composed into many Sessions.
*   **Alignment**: every created Service is a first-class, governed enterprise asset (Principle 3).

## Data Entities (Owned)
*   **Service Definition**: a registered Capability describing a durable business Service and its owned assets.

## Interactions
*   **Initiated by**: Assistant Reasoning Service (reasoned demand).
*   **Realized via**: `Service_Authoring` SBB (design/create), `Capability_Registry_Service` SBB (registration), `Knowledge_Concept_Store` SBB (persistence), `Workflow_Engine` SBB (Session execution).
*   **Consumes**: pattern/template libraries and the Enterprise Concept store for proven designs.

## Relationship to Cognition Model
First-class reasoning-core ABB. Under `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` it is the enterprise capability behind **Strategy Selection → design → Capability creation → Session composition** (§2, §6, §10). A *Service* is a durable Capability; a *workflow* is the transient Session that calls it. This ABB exists precisely because the system must be able to reason, design, and create the Services it later runs.
