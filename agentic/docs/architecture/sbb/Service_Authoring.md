# Service Authoring (Solution Building Block)

## Definition
Service Authoring is the capability that lets the Agentic system **design and create** new Services and Capabilities — not just run existing workflows. It is the authoring surface through which the Assistant Reasoning Service materialises a reasoned design into a deployable, registered Capability.

## Purpose
To close the loop between *reasoning* and *execution assets*: the system can conceive a new business Service (e.g. a Work Session or Lead Enrichment capability), scaffold it, validate it, and register it in the Capability Registry so future Sessions can invoke it. This is the "rough it out with AI, then harden" flow extended from skills to full Services.

## Key Responsibilities
*   **Service Design**: Given a reasoned need, propose a Service shape (data entities, API surface, Capability contract, policy checks).
*   **Scaffolding**: Generate Service/Workflow manifests, Capability `ai_spec` records, and the durable data-store schema needed to own the Service's assets.
*   **Compilation / Promotion**: Promote `ai_mediated` Capabilities toward `compiled` deterministic implementations (reuses the Compiler from the workflow-runner ADR).
*   **Validation**: Dry-run / sandbox a new Service against acceptance criteria before registration.
*   **Registration**: Persist the new Capability in the Capability Registry Service (strict persistence; write failure raises).
*   **MCP Surface**: Expose `design_service`, `create_service`, `compile_capability` tools so an AI can author autonomously.

## Interactions
*   **Exposes**: Authoring API + MCP tools (`design_service`, `create_service`, `compile_capability`).
*   **Consumes**: Design intent from the Assistant Reasoning Service; prior patterns/templates from the pattern catalogue and template repositories.
*   **Calls**: Capability Registry Service (to register), Workflow Engine (to run validation Sessions), Enterprise asset store (to persist Service definitions).
*   **Publishes**: `CapabilityDesigned`, `ServiceCreated` events to the Agent Bus / Observability.

## Data Ownership
*   **Source of Truth for**: Service/ Capability *drafts* and authored manifests pending promotion (the deployed asset's ownership transfers to the realized Service SBB, e.g. `Work_Session_Service`).

## Cognition Alignment
*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** The **design + create** arm of the reasoning core — the mechanism by which the Learning Loop and the Assistant Reasoning Service turn a reasoned need into a first-class **Capability** (`kind=tool|skill`, §10). A created Service is durable; the Session that validated it is transient. **Capabilities/Services are built via the *same* reasoning/planning pipeline used to run workflows** (anchor doc §10a): recognise → select Strategy → `Planning`/`Research`/`Critique` patterns → scaffold → validate Session → register. No separate service-building process exists.
- **Vocabulary map:** "create a service / workflow" → authoring a Capability and (for workflows) a **Session** manifest; "compile a skill" → promote `ai_mediated → compiled` (§10 tier lineage).
- **Relationship to core:** Extends `ai-orchestration-design.md` (MCP authoring) from *skills/workflows* to *Services/Capabilities*. Links to `Assistant_Reasoning_Service` (demand) and `Capability_Registry_Service` (supply).
- **No rename:** "authoring" / "service creation" retained as implementation terminology.
