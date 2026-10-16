# Solution Architecture Building Block: Task Tracking Service

## Overview
The **Task Tracking Service** is a Solution Architecture Building Block (SBB) responsible for the persistent storage and management of daily tasks. It provides the backend capabilities for the "Daily Task Tracking" Enterprise Architecture Building Block (ABB). This service allows users to record, update, and retrieve their tasks, facilitating productivity analysis.

## Responsibilities
*   **Task CRUD Operations**: Create, Read, Update, and Delete individual task records.
*   **Status Management**: Update the status of tasks (e.g., `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`).
*   **Task Listing**: Provide APIs to retrieve lists of tasks, potentially filtered by user, status, or associated work session.
*   **Event Publishing**: Publish events related to task lifecycle (e.g., `TaskCreated`, `TaskStatusUpdated`, `TaskCompleted`) to the Agent Bus.

## Data Ownership
*   **Task**: The Task Tracking Service is the Source of Truth for all data related to individual tasks (e.g., `task_id`, `user_id`, `description`, `status`, `priority`, `due_date`, `work_session_id`).

## Interfaces
*   **Inbound (API)**:
    *   `POST /tasks`: To create a new task.
    *   `GET /tasks/{id}`: To retrieve details of a specific task.
    *   `PUT /tasks/{id}`: To update an existing task (e.g., description, priority).
    *   `PATCH /tasks/{id}/status`: To update the status of a task.
    *   `DELETE /tasks/{id}`: To delete a task.
    *   `GET /tasks`: To retrieve a list of tasks (with filters).
*   **Outbound (Agent Bus Events)**:
    *   `TaskCreated`: When a new task is added.
    *   `TaskStatusUpdated`: When a task's status changes.
    *   `TaskCompleted`: When a task is marked as done.

## Dependencies
*   **Control Center UI**: Initiates task CRUD operations and displays task lists.
*   **Agent Bus**: Publishes task lifecycle events.
*   **Observability Service**: Consumes task events for logging and monitoring.
*   **Persistence Layer**: For storing task data.
*   **Work Session Service**: Potentially consumes `WorkSessionClosed` events to summarize tasks completed within a session, or provides an API to link tasks to sessions.

## Scalability & Reliability
*   Can be scaled independently as a microservice.
*   Should ensure data consistency for task status updates.

## Backlog Items
*   Detailed API contract definition.
*   Data model for the `Task` entity, including potential links to `Work Session`.
*   Implementation of filtering and sorting for task retrieval.
*   Consideration for recurring tasks or sub-tasks.

---

## Relationship to Cognition Model

**First-class Capability, not a passive consumer.** Per the elevated modeling decision, the Task Tracking Service is a durable **Service** = a **Capability** (`kind=tool|skill`) in the canonical model (`ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md` §10). The reasoning core designs, creates, and invokes it; a "track tasks" **workflow** is a transient **Session** that calls this Capability. See the `Service_Composition` ABB and `Capability_Registry_Service` SBB. (Previously tagged a consumer; reclassified by decision 2026-07-16.)
