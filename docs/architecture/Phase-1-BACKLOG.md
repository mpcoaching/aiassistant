# Phase 1: Control Center & Core Manual Workflows - Architectural Backlog

This document outlines the architectural backlog items for Phase 1 of the Agentic System roadmap, focusing on the Solution Architecture Building Blocks (SBBs) identified in `Phase-1-SBBs.md`. Each item represents a subsystem that requires a follow-up `architectural_discovery` session to define its detailed design, API contracts, data models, and technology choices.

## Backlog Item Status Legend
*   **Architectural Discovery (AD)**: Initial architectural session needed.
*   **System Design (SD)**: Detailed design document needed.
*   **Coding (C)**: Implementation in progress.
*   **Testing (T)**: Unit, integration, and system testing in progress.
*   **Completed (D)**: Deployed and verified.

---

## Phase 1 SBBs Requiring Architectural Discovery

### 1. Control Center UI
*   **Status**: AD
*   **Description**: The front-end application for user interaction.
*   **Key Discovery Areas**:
    *   Choice of front-end framework (e.g., React, Vue, Angular).
    *   UI/UX design principles and component library.
    *   State management strategy.
    *   Real-time communication strategy (e.g., WebSockets, SSE) for updates from the Agent Bus.
    *   Authentication and authorization integration.
    *   Deployment strategy (e.g., CDN, static hosting).

### 2. Workflow Engine
*   **Status**: C
*   **Description**: API‑first microservice managing workflow instance lifecycle (CRUD, pause, resume, stop, schedule).  Persists state in Postgres with `.wf/` file fallback, publishes lifecycle events to RabbitMQ, and binds to LangGraph via a Runtime Interface.
*   **Key Discovery Areas (completed)**:
    *   Microservice boundary definition: `workflow-engine`, `langgraph`, `postgres`, `rabbitmq`.
    *   Runtime Interface contract (`start`, `run`, `send`, `add`, `drop`, `stop`, `exit`, `get_status`).
    *   Bus topology and idempotent consumer design.
    *   State persistence strategy (Postgres primary, file fallback).
*   **Remaining Discovery Areas**:
    *   Horizontal scaling of workflow-engine workers (competing consumers on `workflow.executions`).
    *   Distributed locking to prevent duplicate workflow execution.

### 3. Work Session Service
*   **Status**: AD
*   **Description**: Manages the creation, update, and retrieval of work session data.
*   **Key Discovery Areas**:
    *   Detailed API contract definition for session management.
    *   Data model for the `Work Session` entity (fields, relationships).
    *   Persistence technology choice (e.g., PostgreSQL, NoSQL).
    *   Authentication and authorization for session ownership.
    *   Event publishing strategy to the Agent Bus.
    *   Consideration for linking with tasks from the Task Tracking Service.

### 4. Task Tracking Service
*   **Status**: AD
*   **Description**: Stores and manages daily tasks, their statuses, and associated metadata.
*   **Key Discovery Areas**:
    *   Detailed API contract definition for task CRUD operations.
    *   Data model for the `Task` entity (fields, relationships, status transitions).
    *   Persistence technology choice.
    *   Authentication and authorization for task ownership.
    *   Event publishing strategy to the Agent Bus.
    *   Filtering, sorting, and pagination for task retrieval.

### 5. Lead Enrichment Service
*   **Status**: AD
*   **Description**: Orchestrates the process of enriching lead data by integrating with external data sources and applying business logic.
*   **Key Discovery Areas**:
    *   Detailed API contract definition for lead enrichment requests and profile retrieval.
    *   Data model for the `Lead Profile` entity (raw data, enriched data, suggestions).
    *   Integration strategy for specific external data providers (e.g., API keys, rate limits, error handling).
    *   Definition of business rules or machine learning models for "interesting" lead identification and suggestion generation.
    *   Persistence technology choice for lead profiles.
    *   Security considerations for handling sensitive lead data.

---

## Future Phases (Placeholder)

*   **Phase 2 SBBs**: (To be identified and detailed in `Phase-2-BACKLOG.md` after Phase 2 decomposition).
*   **Phase 3 SBBs**: (To be identified and detailed in `Phase-3-BACKLOG.md` after Phase 3 decomposition).
*   **Phase 4 SBBs**: (To be identified and detailed in `Phase-4-BACKLOG.md` after Phase 4 decomposition).
