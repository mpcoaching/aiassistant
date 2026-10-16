# Solution Architecture Building Block: Control Center UI

## Overview
The **Control Center UI** is the primary user-facing Solution Architecture Building Block (SBB) for the Agentic system. It is a web-based application that provides the dashboard and interactive elements for users to manage workflows, monitor system status, view insights, and interact with the assistant. It acts as the presentation layer for the "Control Center" Enterprise Architecture Building Block (ABB).

## Responsibilities
*   **User Interface Rendering**: Display dashboards, workflow lists, task trackers, lead enrichment results, and chat interfaces.
*   **User Input Handling**: Capture user actions such as triggering workflows, entering chat messages, pausing/stopping workflows.
*   **API Integration**: Make API calls to backend services (e.g., Workflow Engine, Work Session Service, Task Tracking Service, Lead Enrichment Service) to initiate actions or fetch data. Workflow triggers are **asynchronous and long-running**: `POST /workflows/{name}/run` returns a `workflow_id` immediately and does not block on completion. The Instances view polls `GET /workflows/{id}/status` until the run reaches a terminal state (completed | failed | stopped). Runs complete "as fast as they can" and may take seconds to minutes. Future phases may add push updates via `workflow.lifecycle.*` event subscriptions.
*   **Real-time Updates**: Subscribe to real-time events (e.g., via WebSockets) from the Agent Bus (potentially via a gateway service) to display live workflow status and system notifications.
*   **Authentication & Authorization**: Integrate with the system's identity provider for user login and access control.

## Data Ownership
The Control Center UI primarily handles transient UI state. It does not own any persistent business data. All persistent data is owned by the respective backend services.

## Interfaces
*   **Outbound (API Calls)**:
    *   `POST /workflows/trigger`: To Workflow Engine
    *   `GET /workflows/{id}/status`: To Workflow Engine
    *   `POST /workflows/{id}/pause`, `POST /workflows/{id}/resume`, `POST /workflows/{id}/stop`: To Workflow Engine
    *   `POST /sessions/start`, `POST /sessions/close`: To Work Session Service
    *   `POST /tasks`, `PUT /tasks/{id}/status`: To Task Tracking Service
    *   `POST /leads/enrich`: To Lead Enrichment Service
    *   `POST /assistant/chat`: To Assistant Service (future phase)
*   **Inbound (Real-time Events)**:
    *   Subscribes to events from the Agent Bus (e.g., `WorkflowStatusUpdated`, `LeadEnriched`, `SystemSuggestion`) for real-time display.

## Dependencies
*   **Workflow Engine**: For workflow management.
*   **Work Session Service**: For managing work sessions.
*   **Task Tracking Service**: For managing daily tasks.
*   **Lead Enrichment Service**: For lead data and suggestions.
*   **Observability Service**: For displaying aggregated system insights.
*   **Agent Bus**: Indirectly, for real-time updates via event subscriptions.
*   **Identity Provider**: For user authentication.

## Scalability & Reliability
*   Can be deployed as a stateless web application, allowing for horizontal scaling.
*   Relies on the scalability and reliability of its backend services.

## Backlog Items
*   Detailed UI/UX design.
*   Choice of front-end framework (e.g., React, Vue, Angular).
*   Integration strategy for real-time updates (e.g., WebSockets, Server-Sent Events).
*   Authentication flow implementation.

---

## Relationship to Cognition Model

Business-domain **consumer** of the reasoning core (ADR §7): consumes Concept Payloads / Capabilities via the bus; not part of the reasoning core. See `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §16.
