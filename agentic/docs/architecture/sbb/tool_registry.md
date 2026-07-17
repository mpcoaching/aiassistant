# Tool Registry (Solution Building Block)

## Definition
The Tool Registry is a dedicated service responsible for cataloging, storing, and providing access to metadata about external tools, functions, and services that agents can utilize. It acts as the authoritative source of truth for tool definitions and invocation details.

## Purpose
To enable agents and the Agent Orchestrator to discover and securely invoke external capabilities without needing direct knowledge of their underlying implementation or connection details.

## Key Responsibilities
*   **Tool Definition Storage**: Persisting tool metadata, including names, descriptions, input/output schemas, and invocation methods.
*   **Capability Mapping**: Describing the functional capabilities provided by each tool.
*   **Discovery**: Providing APIs to search and retrieve tool information based on capabilities or names.
*   **Security Context**: Storing information required for secure tool invocation (e.g., API keys, authentication methods, if applicable).
*   **Lifecycle Events**: Publishing events (via Agent Bus) when tools are registered, updated, or deregistered.

## Interactions
*   **Exposes**: RESTful API for CRUD operations on tool definitions and for tool discovery.
*   **Consumes**: (Potentially) events from tool providers for dynamic updates or health checks.
*   **Publishes**: Events to the Agent Bus (e.g., `ToolRegistered`, `ToolUpdated`, `ToolDeregistered`).

## Data Ownership
*   **Source of Truth for**: Tool Definitions, Tool Interfaces, Tool Invocation details.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Capability Registry. A tool is one `kind` of **Capability** (`kind=tool|skill`) — an Enterprise Concept record describing *what the business does* and how to invoke it (anchor doc §10).
- **Vocabulary map:** "tool definition / capability mapping" → a **Capability** record with `execution_mode: ai_mediated | compiled` and the `prompt|code|distilled` → `ai_mediated|distilled|compiled` tier lineage. "Tool invocation" → Tier 2 (in-process) or Tier 3 (bus-mediated) Capability transport (ADR §6.2).
- **Open question (ADR §7 item 11):** whether Tool Registry and Agent Registry merge into one service is **open**. This alignment maps to the **single Capability Registry intent** (one registry, `kind: tool|skill`) without resolving that decision. The *record shape* is mandated regardless of the service boundary.
- **No rename:** "tool" retained as implementation terminology.
