# System Context

## Overview
The Agentic system is designed to be a scalable and decoupled architecture, using an Event Bus pattern for cross‑service notifications. This allows for loose coupling between services, making it easier to develop, test, and maintain individual components.

## Communication Standards
All services must be idempotent when consuming events, meaning that they can handle duplicate or out‑of‑order events without affecting the system's overall state. This ensures that the system remains consistent and reliable, even in the presence of failures or network partitions.

## Event Bus Pattern
The Event Bus pattern is used to enable communication between services. Services publish events to the bus, which are then consumed by other services that have subscribed to those events. This decouples services from each other, allowing them to evolve independently without affecting the overall system.

## Agent Bus
The Agentic system uses an "agent bus" to facilitate communication between services. The agent bus is an implementation of the Event Bus pattern, providing a scalable and reliable way for services to publish and consume events. The agent bus also provides features such as tracability, logging, and observability, making it easier to monitor and debug the system.

## Prompt Optimisation
The agent bus can be used to optimise prompts using tools like Langfuse. By publishing events to the bus, services can trigger Langfuse to analyse and optimise prompts, improving the overall performance and efficiency of the system.

## Benefits
The use of the Event Bus pattern and the agent bus provides several benefits, including:

* Loose coupling between services, making it easier to develop and maintain individual components
* Scalability, as services can be added or removed without affecting the overall system
* Reliability, as the system can handle failures and network partitions without affecting the overall state
* Tracability, logging, and observability, making it easier to monitor and debug the system

## Core Agentic Services (Phase 1)

To support the core agent framework, the following services are introduced:

* **Agent Registry Service** – Manages agent manifests, their definitions, capabilities, and configurations. It acts as the central source of truth for agent metadata.
* **Tool Registry Service** – Manages available tools, their interfaces, and how they can be invoked by agents. It acts as the central source of truth for tool metadata.
* **Agent Orchestrator Service** – Responsible for scheduling, initiating, and managing the execution lifecycle of agent instances. It coordinates with the Agent Execution Environment.
* **Agent Execution Environment (Runtime)** – Provides the secure, isolated, and sandboxed environment where agent code runs and interacts with registered tools. This is a critical component for secure and controlled agent operation.
* **Observability Service** – Aggregates logs, traces, and metrics from all Agentic components, leveraging the Agent Bus, to provide comprehensive monitoring and debugging capabilities.
* **Agent Template Service** – Manages and provides access to pre‑defined agent templates, facilitating rapid agent development and deployment.

These services interact primarily via the Agent Bus for asynchronous communication, ensuring loose coupling. Direct API calls are used for synchronous requests where immediate responses are required (e.g., retrieving an agent manifest from the Agent Registry).

## Phase 1 Additional Subsystems

The Phase 1 roadmap introduces several business‑level capabilities that are realised as new technical subsystems (Solution‑Building Blocks, SBBs).  They are listed here to make the system‑wide context complete.

| Subsystem (SBB) | Primary Responsibility | Source‑of‑Truth Data Entity |
|-----------------|------------------------|-----------------------------|
| **Control Center UI** | Provides the dashboard for manual workflow triggering, monitoring, and chat interaction. | UI state is transient; persistent data lives in the underlying services (Workflow Engine, Task Service, etc.). |
| **Workflow Engine** | Accepts workflow requests from the UI, publishes them to the Agent Bus, tracks execution status, and handles pause/resume/stop. | Workflow Instance (id, status, timestamps). |
| **Work Session Service** | Manages the lifecycle of a “work session” (start, close, summary capture). | Work Session entity (session‑id, start‑time, end‑time, outcomes). |
| **Task Tracking Service** | Stores daily tasks, progress, and outcome metrics. | Task entity (task‑id, owner, status, timestamps). |
| **Lead Enrichment Service** | Enriches raw lead data from browser sessions, stores enriched profiles, and surfaces next‑step recommendations. | Lead Profile entity (lead‑id, enriched‑fields, last‑updated). |

All of the above publish domain events to the **Agent Bus** and subscribe to events they need to react to (e.g., `WorkflowCompleted`, `LeadEnriched`).  This keeps the architecture loosely coupled while preserving a clear source‑of‑truth for each data entity.

## Data Ownership & Interfaces

| Data Entity | Owner (Source‑of‑Truth) | Consumers (via Event Bus or API) |
|-------------|------------------------|----------------------------------|
| Agent Manifest | **Agent Registry Service** | Orchestrator, Execution Environment, UI |
| Tool Definition | **Tool Registry Service** | Agents, Orchestrator, UI |
| Workflow Instance | **Workflow Engine** | UI (monitoring), Observability Service, Agents (execution) |
| Work Session | **Work Session Service** | UI, Observability Service |
| Task | **Task Tracking Service** | UI, Reporting/Analytics |
| Lead Profile | **Lead Enrichment Service** | UI, Sales Automation, Reporting |

These ownership definitions will guide the high‑level contracts (interfaces) that the Strategic Decomposition and subsequent Architectural Discovery steps will flesh out.