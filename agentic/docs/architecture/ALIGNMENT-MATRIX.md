# Alignment Matrix — Engineering Artifacts ↔ Cognition Model

> Evidence that every engineering artifact agrees with the canonical **Enterprise Cognition Reference Architecture** (`.kilo/.../agentic/docs/architecture/ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`). Produced as the Phase F consistency gate (validation F1–F3).
>
> Convention: every reasoning-core artifact (Phases B/C) carries a `## Cognition Alignment` section; business-domain artifacts (Phase D) carry a one-line `## Relationship to Cognition Model` note; SA specs (Phase E) carry cross-references.

## Status legend

- **Aligned** — section added; terms mapped; no responsibility bodies rewritten.
- **Anchor** — the canonical source of truth itself.
- **Re-framed** — classification changed (e.g. consumer → first-class Capability) per the 2026-07-16 decision.

## Reasoning-core SBBs (Phase B)

| Artifact | Model role | Section added | Status |
|---|---|---|---|
| `sbb/agent_orchestrator.md` | Strategy / Session dispatch (decides *that* a session runs) | `## Cognition Alignment` | Aligned |
| `sbb/agent_registry.md` | Role / Pattern participant definitions ("who's in the meeting") | `## Cognition Alignment` | Aligned |
| `sbb/agent_runtime.md` | Pattern Runtime (sandboxed execution of a Capability / pattern step) | `## Cognition Alignment` | Aligned |
| `sbb/agent_template_repository.md` | Reusable Pattern / manifest templates (≠ Concept Payload library) | `## Cognition Alignment` | Aligned |
| `sbb/tool_registry.md` | Capability Registry (`kind: tool|skill`; single-registry intent; ADR §7 item 11 open) | `## Cognition Alignment` | Aligned |
| `sbb/agentic_observability_platform.md` | Token Economics / Learning Loop tracking (cost-per-request-type, reuse, exploration) | `## Cognition Alignment` | Aligned |

## Reasoning-core ABBs (Phase C)

| Artifact | Model role | Section added | Status |
|---|---|---|---|
| `abb/agent_management.md` | Governance of reasoning participants (configured by Strategy/Pattern) | `## Cognition Alignment` | Aligned |
| `abb/automated_task_execution.md` | Deterministic Capability / SOP-execution posture | `## Cognition Alignment` | Aligned |
| `abb/tooling_integration.md` | Capability transport (Tier 2 in-process / Tier 3 bus-mediated, ADR §6.2) | `## Cognition Alignment` | Aligned |
| `abb/solution_templating.md` | Pattern templates (≠ Concept Payload library) | `## Cognition Alignment` | Aligned |
| `abb/operational_visibility.md` | Observability / Learning Loop instrumentation | `## Cognition Alignment` | Aligned |

## New reasoning-core building blocks added for solution-architecture readiness (2026-07-16)

| Artifact | Type | Model role | Status |
|---|---|---|---|
| `sbb/Assistant_Reasoning_Service.md` | SBB | Intent → Context → Problem Frame → Strategy Selection → Reasoning Strategy → Patterns (the "brain") | Aligned |
| `sbb/Capability_Registry_Service.md` | SBB | Unified Capability Registry (`tool\|skill`; single-registry intent) | Aligned |
| `sbb/Service_Authoring.md` | SBB | Design + create Services/Capabilities (extends MCP authoring beyond workflows) | Aligned |
| `sbb/Event_Bus.md` | SBB | Tier-3 Capability transport + `KnowledgeChunkDiscovered` ingestion | Aligned |
| `sbb/Knowledge_Concept_Store.md` | SBB | Enterprise Concepts / Knowledge graph (central noun) | Aligned |
| `abb/Service_Composition.md` | ABB | Design/create/orchestrate Services & Capabilities | Aligned |
| `abb/Capability_Management.md` | ABB | Governance of the Capability catalog | Aligned |
| `abb/Knowledge_Management.md` | ABB | Governance of Enterprise Concepts / Knowledge | Aligned |

## Business services — re-classified as first-class Capabilities (2026-07-16 decision)

Previously tagged "consumers". Per the decision, the reasoning core **designs, creates, and invokes** these as durable **Services = Capabilities** (`kind=tool|skill`); a "run" against them is a transient **Session** (workflow). The SBB/ABB `Relationship to Cognition Model` notes are updated to first-class status.

| Artifact | Model role | Status |
|---|---|---|
| `sbb/Workflow_Engine.md` | Owns Session (workflow instance) execution; calls Strategy Selection / Pattern Runtime; publishes lifecycle events | Aligned (full note, unchanged) |
| `sbb/Work_Session_Service.md` | Durable Service = Capability the core composes into Sessions | Re-framed |
| `sbb/Task_Tracking_Service.md` | Durable Service = Capability the core composes into Sessions | Re-framed |
| `sbb/Lead_Enrichment_Service.md` | Durable Service = Capability the core composes into Sessions | Re-framed |
| `sbb/Control_Center_UI.md` | Trigger/observation surface; calls Services as Capabilities | Aligned (consumer-of-capabilities note) |
| `abb/Control_Center.md` | Trigger/observation surface | Aligned |
| `abb/Work_Session.md` | Business capability realized as a Service/Capability | Re-framed |
| `abb/Task_Tracking.md` | Business capability realized as a Service/Capability | Re-framed |
| `abb/Lead_Enrichment.md` | Business capability realized as a Service/Capability | Re-framed |

## SA workflow-runner specs (Phase E)

| Artifact | Change | Status |
|---|---|---|
| `sa/utilities/workflow-runner/functional-specification.md` | `## Cognition Alignment`: workflow=Session, steps=pattern steps/Capability, `prompt|code|distilled` → `ai_mediated|distilled|compiled` | Aligned |
| `sa/utilities/workflow-runner/ai-orchestration-design.md` | Cross-reference + mapping | Aligned |
| `sa/utilities/workflow-runner/technical-design.md` | Cross-reference (Pattern Runtime adapter) | Aligned |
| `sa/utilities/workflow-runner/workflow-schema.md` | Cross-reference + `intent` field = **Intent** subtype | Aligned |
| `sa/utilities/workflow-runner/runtime-interface.md` | Cross-reference (Pattern Runtime adapter contract) | Aligned |
| `sa/utilities/workflow-runner/implementation-plan.md` | Cross-reference (Additional Runtimes = further adapters) | Aligned |

## Canonical sources (mapped, not rewritten)

| Artifact | Role in model | Status |
|---|---|---|
| `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` | **Anchor** — canonical source of truth | Anchor |
| `ENTERPRISE-COGNITION.md` | First principles (consolidated into anchor §4) | Aligned |
| `ENTERPRISE-CONTEXT-MODEL.md` | Context spec (anchor §5) | Aligned |
| `REASONING-PATTERN-CATALOGUE.md` | Pattern catalogue, one level below Strategy (anchor §8) | Aligned |
| `PATTERN-RECOGNITION-ASSIMILATION.md` | Learning Loop (anchor §13) | Aligned |
| `SESSION-MODEL.md` | Session (anchor §11) | Aligned |
| `RUNTIME-MAPPING.md` | Pattern Runtime (anchor §12) | Aligned |
| `SCENARIO-VALIDATION.md` | Validation suite S1–S10 (anchor §14) | Aligned |
| `SA-NEXT-PHASE-REASONING-CORE.md` | Solution-architecture build plan for the next phase | Anchor (plan) |
| `SA-CONTRACTS-PHASE1.md` | Phase-1 implementation-ready contracts (C1–C8): Concept type system, Capability record, Intent/Strategy interfaces, invocation envelope + bus topology, store schema, 3 business Services as Capabilities, Phase-1 task breakdown | Anchor (contracts) |
| `SA-CONTRACTS-PHASES-2-5.md` | Phases 2–5 implementation-ready contracts (C9–C13): Reasoning entrypoint, Pattern Runtime/Session execution, Service Authoring + promotion, Learning Loop/Knowledge governance, cross-phase end-to-end trace | Anchor (contracts) |

## Key clarifications added to the anchor (2026-07-16)

- **§1a Service vs Capability vs Workflow** — the terminology that drives AI design choices: one execution substrate, differentiated only by durable state + standing contract. Includes the decision rule (Service vs Session vs pure Capability).
- **§10a Capabilities built via the same planning pipeline as workflows** — no separate service-building process; designing a Capability/Service reuses recognise → Strategy → Planning/Research/Critique patterns → author → register.

## Validation gate summary (F1–F3)

- **F1 — header convention:** all reasoning-core SBBs (Phase B + the 5 new) and reasoning-core ABBs contain a `## Cognition Alignment` section referencing the anchor doc. ✅
- **F2 — scenario self-containment:** S1–S10 (anchor §14) are expressible using only the anchor model + mapped artifacts, with zero new framework assumptions. ✅
- **F3 — everything agrees:** this matrix shows every artifact Aligned/Anchor/Re-framed; a reviewer can trace any scenario S1–S10 along `Intent → Strategy → Pattern → Concept/Capability → Session → Pattern Runtime → Learning Loop` using only the anchor doc + mapped artifacts. ✅

## Locked decisions reflected

- Canonical anchor = `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`; all others reference it.
- Map existing terms; do not rename. System Context doc and `packages/workflow-runner` references stay valid.
- Business-domain artifacts: **re-classified as first-class Capabilities** (not passive consumers) per 2026-07-16 decision.
- Concept Payload = one `Enterprise Concept` record `kind` (`solved_approach`); Capability = another `kind` (`tool|skill`). Same type system.
- Strategy Selection replaces the static Context→Pattern table as its v1 seed (evolvable later).
- **A workflow = a Session; a service = a Capability** (anchor §1a). Capabilities are built via the same planning pipeline as workflows (§10a). The internal agentic API (Agent Bus/REST) is the single invocation seam.
