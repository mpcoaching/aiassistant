# Solution Architecture Building Block: Workflow Engine

## Overview
The **Workflow Engine** is a core Solution Architecture Building Block (SBB) responsible for the execution, orchestration, and lifecycle management of defined workflows within the Agentic system. It acts as the central component for processing requests to run workflows and tracking their progress. It supports the "Control Center" ABB and is a critical enabler for "Work Session Management", "Daily Task Tracking", and "Lead Enrichment" ABBs by executing their underlying processes.

## Responsibilities
*   **Workflow Definition Loading**: Load and interpret workflow definitions (e.g., from a Workflow Definition Repository, not explicitly defined yet but implied).
*   **Workflow Instance Management**: Create, manage, and persist the state of individual workflow instances.
*   **Execution Orchestration**: Coordinate the steps within a workflow, potentially by publishing tasks/events to the Agent Bus for agents or other services to pick up.
*   **Status Tracking**: Maintain and update the status of running workflows (e.g., `PENDING`, `RUNNING`, `PAUSED`, `COMPLETED`, `FAILED`).
*   **Control Operations**: Handle requests to pause, resume, or stop a running workflow instance.
*   **Event Publishing**: Publish workflow lifecycle events (e.g., `WorkflowStarted`, `WorkflowCompleted`, `WorkflowFailed`, `WorkflowStatusUpdated`) to the Agent Bus.

## Data Ownership
*   **Workflow Instance**: The Workflow Engine is the Source of Truth for the state and history of each running workflow instance.

## Interfaces
*   **Inbound (API)**:
    *   `POST /workflows`: To trigger a new workflow instance.
    *   `GET /workflows/{id}`: To retrieve the status and details of a workflow instance.
    *   `POST /workflows/{id}/pause`: To pause a workflow.
    *   `POST /workflows/{id}/resume`: To resume a paused workflow.
    *   `POST /workflows/{id}/stop`: To stop a running workflow.
*   **Outbound (Agent Bus Events)**:
    *   `WorkflowTriggered`: When a new workflow starts.
    *   `WorkflowStepCompleted`: When a step within a workflow finishes.
    *   `WorkflowCompleted`: When a workflow successfully finishes.
    *   `WorkflowFailed`: When a workflow encounters an unrecoverable error.
    *   `WorkflowStatusUpdated`: Generic status updates for monitoring.
*   **Outbound (API Calls)**: May make synchronous calls to other services if a workflow step requires an immediate response (e.g., to the Agent Orchestrator to initiate an agent task).

## Dependencies
*   **Control Center UI**: Receives workflow trigger and control requests.
*   **Agent Bus**: Publishes events for workflow steps and status updates, and potentially consumes events from agents/services indicating step completion.
*   **Observability Service**: Publishes events for monitoring and logging.
*   **Persistence Layer**: For storing workflow instance state.

## Scalability & Reliability
*   Should be designed for high availability and fault tolerance, potentially using a distributed transaction or saga pattern for long-running workflows.
*   Can be scaled horizontally to handle a large number of concurrent workflow instances.

## Backlog Items
*   Choice of workflow orchestration technology (e.g., Cadence, Temporal, Apache Airflow, custom state machine).
*   Detailed API contract definition.
*   Data model for workflow instances and their states.
*   Error handling and retry mechanisms for workflow steps.
*   Integration with Agent Orchestrator for agent-specific workflow steps.
