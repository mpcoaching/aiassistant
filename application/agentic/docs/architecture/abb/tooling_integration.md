# Tooling Integration (Enterprise Building Block)

## Definition
Tooling Integration is the enterprise capability to discover, register, and securely integrate external tools, functions, and services, making them available for use by autonomous agents and other system components.

## Purpose
To enable agents to extend their capabilities beyond their core logic by interacting with a diverse set of external resources, thereby increasing their utility and problem-solving scope within the enterprise.

## Key Responsibilities
*   **Tool Discovery**: Identifying potential external tools and services.
*   **Tool Registration**: Cataloging tools with their interfaces, capabilities, and access requirements.
*   **Secure Access**: Providing mechanisms for agents to securely invoke external tools.
*   **Interface Standardization**: Abstracting tool-specific invocation details behind a common interface for agents.
*   **Capability Mapping**: Describing what a tool can do in a way that agents can understand and utilize.

## Relationship to Other ABBs
*   **Agent Management**: Agents managed by the Agent Management ABB will consume tools provided by this ABB.
*   **Automated Task Execution**: Tools are essential components for agents to perform complex tasks as part of Automated Task Execution.
*   **Operational Visibility**: Tool invocations and their outcomes will be monitored by the Operational Visibility ABB.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Capability transport. This ABB realises the **Capability** invocation layer (`kind=tool|skill`, anchor doc §10) — making Capabilities callable by pattern steps.
- **Vocabulary map:** "tool discovery / registration / secure access" → Capability Registry discovery + invocation (links to `sbb/tool_registry.md`). "Interface standardization" → the Capability request/reply envelope.
- **Transport tiers (ADR §6.2):** Tier 2 = in-process Capability calls (direct); Tier 3 = bus-mediated Capability calls (Request-Reply envelopes over the Agent Bus). Both are Capability invocations under the model; the tier is a transport concern, not a reasoning concern.
- **No rename:** "tooling integration" retained.
