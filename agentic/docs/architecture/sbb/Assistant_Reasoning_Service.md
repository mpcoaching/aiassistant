# Assistant Reasoning Service (Solution Building Block)

## Definition
The Assistant Reasoning Service is the primary reasoning entrypoint of the Agentic system. It is where an **Intent** (user request, scheduled job, bus event, or alert) arrives and is transformed into reasoned action: recognising the problem, selecting a Reasoning Strategy, designing a solution, and — when appropriate — creating or invoking the Services/Capabilities needed to execute it.

## Purpose
To provide a single, governable surface at which the enterprise's cognition is applied: the system **reasons about, designs, and creates** capabilities (including the business Services such as Work Session, Task Tracking, and Lead Enrichment), then composes them into a **Session** (workflow) that the Pattern Runtime executes. It is the "brain" that sits between an arriving Intent and a running Session.

## Key Responsibilities
*   **Intent Intake**: Accept Intents from any origin (Control Center UI, scheduler, Agent Bus, alerts).
*   **Context Resolution**: Classify the Intent into the orthogonal Context dimensions (Problem, Environment, Information, Activity Purpose, Decision) producing a **Problem Frame**.
*   **Strategy Selection**: Invoke the first-class Strategy Selection capability to map the Problem Frame to a **Reasoning Strategy** (e.g. `recognise_and_reuse`, `deliberate_to_consensus`, `research_to_synthesis`).
*   **Reasoning & Design**: Apply the selected Reasoning Patterns (Debate, Investigation, Planning, etc.) to reason about and, when needed, *design and create* new Services/Capabilities (via the Service Authoring and Capability Registry capabilities).
*   **Session Composition**: Assemble the chosen Pattern pipeline into a **Session** manifest and hand it to the Workflow Engine for execution.
*   **Capability Invocation**: Call durable Services (Work Session, Task Tracking, Lead Enrichment, tools) as **Capabilities** (`kind=tool|skill`) during reasoning or execution.
*   **Learning Hand-off**: On Session close, trigger the Learning Loop (pattern recognition & assimilation) so successful approaches become Enterprise Concepts / Knowledge.

## Interactions
*   **Exposes**: Reasoning API (submit Intent, query reasoning state, retrieve designed artifacts).
*   **Consumes**:
    *   Intents from Control Center UI, scheduler, and Agent Bus.
    *   Context/Strategy inputs from Strategy Selection.
    *   Capability metadata from the Capability Registry Service.
*   **Calls / Creates**:
    *   Services via `Service_Authoring` (design + create new Services/Capabilities).
    *   Capabilities through the Capability Registry Service.
    *   The Workflow Engine to launch a Session.
*   **Publishes**: `IntentReceived`, `StrategySelected`, `SessionProposed`, `CapabilityDesigned` events to the Agent Bus / Observability.

## Data Ownership
*   **Source of Truth for**: Reasoning session state (in-flight), designed-but-not-yet-deployed Capability drafts, Strategy-selection decisions.

## Cognition Alignment
*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** The realization of the **Intent → Context → Problem Frame → Strategy Selection → Reasoning Strategy → Reasoning Patterns** chain (anchor doc §2). This is where the enterprise *thinks, learns, standardises, and executes* (§4).
- **Vocabulary map:** "assistant / AI assistant" → the reasoning participant (an `AgentPersona`, `AGENTIC-EXPERIENCE.md`) acting under a selected Strategy/Pattern. "Design and create a service" → a Service Authoring action producing a **Capability** (`kind=tool|skill`, §10).
- **Relationship to core:** Distinct from `agent_orchestrator` (which *dispatches* an already-chosen Session) and from the `Workflow_Engine` (which *executes* the Session). The Assistant Reasoning Service *decides what to do*; the others run it.
- **No rename:** "assistant" / "reasoning service" retained as implementation terminology for this entrypoint.
