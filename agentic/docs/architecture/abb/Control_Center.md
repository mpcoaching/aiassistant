# Enterprise Architecture Building Block: Control Center

## Overview
The **Control Center** is a foundational Enterprise Architecture Building Block (ABB) for the Agentic system. It represents the primary user interface and interaction hub, providing a centralized dashboard for users to manage and interact with the system's capabilities. It is designed to offer robust control over workflows, display critical system information, and facilitate direct user interaction.

## Capabilities
*   **Workflow Management**:
    *   Manually trigger and schedule predefined workflows.
    *   Monitor the real-time execution status of running workflows.
    *   Ability to stop, pause, and resume active workflows.
*   **System Insights & Suggestions**:
    *   Display system-generated suggestions, recommendations, and insights.
*   **Assistant Interaction**:
    *   Provide a chat interface for direct interaction with a basic AI assistant (initially rule-based or simple LLM integration).

## Business Value
*   **Centralized Operations**: Offers a single pane of glass for all Agentic system interactions, improving user efficiency and reducing cognitive load.
*   **Enhanced Control**: Provides users with direct control over automated processes, ensuring oversight and intervention capabilities.
*   **Actionable Intelligence**: Surfaces system suggestions and insights, empowering users to make informed decisions.
*   **User Engagement**: Facilitates direct interaction with the system, making it more accessible and responsive to user needs.

## Data Entities (Owned)
The Control Center primarily deals with transient UI state. Persistent data related to workflows, tasks, and sessions are owned by their respective services.

## Interactions
*   **Triggers**: Initiates workflow execution requests to the Workflow Engine.
*   **Monitors**: Subscribes to status updates from the Workflow Engine and Observability Service.
*   **Displays**: Renders data from various services (e.g., Work Session Service, Task Tracking Service, Lead Enrichment Service) for user consumption.
*   **Communicates**: Sends user input to the Assistant Service and receives responses.

## Realization
This ABB will be realized by the `Control_Center_UI` Solution Building Block (SBB).

---

## Relationship to Cognition Model

Business-domain **consumer** of the reasoning core (ADR §7): consumes Concept Payloads / Capabilities via the bus; not part of the reasoning core. See `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §16.
