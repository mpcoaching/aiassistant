# Agent Registry (Solution Building Block)

## Definition
The Agent Registry is a dedicated service responsible for the persistent storage, retrieval, and management of agent definitions, manifests, capabilities, and configurations. It acts as the authoritative source of truth for all registered agents within the Agentic system.

## Purpose
To provide a centralized, discoverable, and version-controlled repository for agent metadata, enabling other services (e.g., Agent Orchestrator) to dynamically understand and interact with available agents.

## Key Responsibilities
*   **Agent Manifest Storage**: Persisting agent definitions (e.g., JSON manifests).
*   **Agent Metadata Management**: Storing agent names, versions, descriptions, and declared capabilities.
*   **Validation**: Ensuring agent manifests conform to the defined schema.
*   **Querying**: Providing APIs to search and retrieve agent information based on various criteria (e.g., by ID, by capability).
*   **Lifecycle Events**: Publishing events (via Agent Bus) when agents are registered, updated, or deregistered.

## Interactions
*   **Exposes**: RESTful API for CRUD operations on agent definitions.
*   **Consumes**: (Potentially) events from an internal configuration management system for updates.
*   **Publishes**: Events to the Agent Bus (e.g., `AgentRegistered`, `AgentUpdated`, `AgentDeregistered`).

## Data Ownership
*   **Source of Truth for**: Agent Definitions, Agent Capabilities, Agent Configurations.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Role / Pattern participant definitions — the "who's in the meeting" list (ADR §7). It holds the participant metadata that a Strategy/Pattern selects into a Session.
- **Vocabulary map:** "agent definition / manifest / capability" → a **ParticipantRecord** role configuration and a **Capability** registry entry (`kind=tool|skill`, `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §10). "Agent capabilities" declared here are the classification metadata that Strategy Selection and patterns consult.
- **Relationship to core:** The registry supplies the *participant definitions* a Pattern step or Strategy references; it is not the reasoning engine. Links to `agent_runtime` (execution) and `tool_registry` (Capability Registry intent).
- **No rename:** "agent" stays as implementation terminology; under the model it is one `kind` of participant.
