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
