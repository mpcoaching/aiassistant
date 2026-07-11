# Phase 1: Control Center & Core Manual Workflows - Solution Architecture Building Blocks (SBBs) Overview

This document outlines the Solution Architecture Building Blocks (SBBs) that realize the Enterprise Architecture Building Blocks (ABBs) for Phase 1 of the Agentic System roadmap. These SBBs represent the technical subsystems and services required to deliver the "Control Center & Core Manual Workflows (MVP)" capabilities.

## Phase 1 Goal
Establish a central interface for business operations, enabling manual execution of key workflows, monitoring, receiving suggestions and insights, and basic interaction with an assistant. This phase will leverage the agentic bus for workflow execution and scheduling, with robust control from the UI.

## Solution Architecture Building Blocks (SBBs)

The following SBBs are identified for Phase 1, mapping to the ABBs defined in `Phase-1-ABBs.md`:

1.  **Control Center UI**:
    *   **Realizes ABB**: Control Center
    *   **Description**: The front-end application providing the user interface for the Agentic system. It consumes data from various backend services and sends commands to initiate workflows and interact with the assistant.
    *   **Key Responsibilities**: User authentication, dashboard rendering, workflow triggering, status display, chat interface.

2.  **Workflow Engine**:
    *   **Realizes ABB**: (Supports Control Center, Work Session Management, Daily Task Tracking, Lead Enrichment)
    *   **Description**: An API‑first microservice that manages the lifecycle of workflow instances (create, run, pause, resume, stop, schedule).  It persists state in Postgres (with `.wf/` file fallback), publishes lifecycle events to RabbitMQ, and delegates skill execution to the LangGraph Runtime via a thin HTTP Runtime Interface.
    *   **Key Responsibilities**: Workflow definition loading, instance creation, state management, scheduling (APScheduler), event publishing (RabbitMQ), and Runtime Interface binding to LangGraph.

3.  **LangGraph Runtime**:
    *   **Realizes ABB**: (Supports Control Center, Work Session Management, Daily Task Tracking, Lead Enrichment)
    *   **Description**: The black‑box HTTP runtime that executes composed skill prompts.  The Workflow Engine interacts with it through a Runtime Interface (`start`, `run`, `send`, `add`, `drop`, `stop`, `exit`, `get_status`) so the runtime can be swapped without changing the engine.
    *   **Key Responsibilities**: Prompt execution, thread/run management, and returning normalised results to the Workflow Engine.

4.  **Agent Bus**:
    *   **Realizes ABB**: Communication substrate for all Phase 1 services.
    *   **Description**: RabbitMQ durable topic exchange with dead‑letter routing, consumer thread pools, and idempotent message handling per `docs/SYSTEM_CONTEXT.md`.
    *   **Key Responsibilities**: Reliable event delivery, decoupling producers from consumers, and enabling horizontal scaling.

5.  **Work Session Service**:
    *   **Realizes ABB**: Work Session Management
    *   **Description**: A dedicated backend service for managing the creation, update, and retrieval of work session data.
    *   **Key Responsibilities**: Persisting work session details, handling start/close session logic, providing session summaries.

4.  **Task Tracking Service**:
    *   **Realizes ABB**: Daily Task Tracking
    *   **Description**: A backend service responsible for storing and managing daily tasks, their statuses, and associated metadata.
    *   **Key Responsibilities**: Task CRUD operations, status updates, basic reporting on task completion.

5.  **Lead Enrichment Service**:
    *   **Realizes ABB**: Lead Enrichment
    *   **Description**: A backend service that orchestrates the process of enriching lead data by integrating with external data sources and applying business logic to suggest next steps.
    *   **Key Responsibilities**: Data fetching from external APIs, data transformation, lead scoring/analysis, storing enriched profiles.

## Core Agentic Services (Pre-existing / Foundational)

In addition to the above, Phase 1 leverages the following core Agentic services (as defined in `docs/SYSTEM_CONTEXT.md`):

*   **Agent Registry Service**: Manages agent manifests.
*   **Tool Registry Service**: Manages available tools.
*   **Agent Orchestrator Service**: Manages agent execution lifecycle.
*   **Agent Execution Environment (Runtime)**: Provides the sandboxed environment for agent code.
*   **Observability Service**: Aggregates logs, traces, and metrics.
*   **Agent Template Service**: Manages agent templates.
*   **Agent Bus**: The central eventing mechanism for inter-service communication.

## Interaction and Data Flow

The SBBs interact primarily via the **Agent Bus** for asynchronous communication. The Control Center UI makes synchronous API calls to backend services (e.g., Workflow Engine, Work Session Service) to initiate actions or retrieve data for display. Backend services publish events to the Agent Bus upon state changes (e.g., `WorkflowStarted`, `LeadEnriched`), which other interested services (e.g., Observability Service, Control Center UI via WebSockets) can consume.

## Next Steps

Each of these SBBs will require a dedicated `architectural_discovery` session to define their detailed design, API contracts, data models, and technology choices. These items are listed in `Phase-1-BACKLOG.md`.
