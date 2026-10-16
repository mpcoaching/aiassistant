# Agent Management (Enterprise Building Block)

## Definition
Agent Management is the enterprise capability to define, configure, deploy, and oversee the lifecycle of autonomous agents within the organization's ecosystem. This includes managing agent identities, capabilities, configurations, and their operational status.

## Purpose
To provide a centralized and standardized approach for handling all aspects related to the agents operating within the enterprise, ensuring governance, security, and efficient utilization of agent resources.

## Key Responsibilities
*   **Agent Definition**: Establishing the structure and metadata for new agents.
*   **Configuration Management**: Storing and applying operational parameters for agents.
*   **Lifecycle Control**: Managing agent states (e.g., deployed, active, suspended, retired).
*   **Capability Declaration**: Documenting and making discoverable the functions an agent can perform.
*   **Access Control**: Defining who or what can interact with or modify agent definitions.

## Relationship to Other ABBs
*   **Tooling Integration**: Agents managed by this ABB will utilize tools integrated via the Tooling Integration ABB.
*   **Automated Task Execution**: Agents will be deployed to execute tasks defined by the Automated Task Execution ABB.
*   **Operational Visibility**: Agent activities will contribute to the data collected by the Operational Visibility ABB.
*   **Solution Templating**: Agent definitions can be derived from templates provided by the Solution Templating ABB.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Governance of reasoning **participants**. "Agents" are reasoning participants *configured by* a Strategy/Pattern, not autonomous decision-makers.
- **Vocabulary map:** "agent definition / capability declaration" → **ParticipantRecord** role configuration + **Capability** registry entry (`kind=tool|skill`, anchor doc §10). "Lifecycle control / access control" → participant governance within a Session (`SESSION-MODEL.md`).
- **Relationship to core:** Links to `sbb/agent_registry.md` (participant definitions) and `sbb/agent_runtime.md` (Pattern Runtime execution). This ABB governs *who* can participate; Strategy Selection + the pattern catalogue decide *how* they participate.
- **No rename:** "agent management" retained as implementation terminology.
