# System Context

## Overview
The Agentic system is designed to be a scalable and decoupled architecture, using an Event Bus pattern for cross-service notifications. This allows for loose coupling between services, making it easier to develop, test, and maintain individual components.

## Communication Standards
All services must be idempotent when consuming events, meaning that they can handle duplicate or out-of-order events without affecting the system's overall state. This ensures that the system remains consistent and reliable, even in the presence of failures or network partitions.

## Event Bus Pattern
The Event Bus pattern is used to enable communication between services. Services publish events to the bus, which are then consumed by other services that have subscribed to those events. This decouples services from each other, allowing them to evolve independently without affecting the overall system.

## Agent Bus
The Agentic system uses an "agent bus" to facilitate communication between services. The agent bus is an implementation of the Event Bus pattern, providing a scalable and reliable way for services to publish and consume events. The agent bus also provides features such as tracability, logging, and observability, making it easier to monitor and debug the system.

## Prompt Optimisation
The agent bus can be used to optimize prompts using tools like Langfuse. By publishing events to the bus, services can trigger Langfuse to analyze and optimize prompts, improving the overall performance and efficiency of the system.

## Benefits
The use of the Event Bus pattern and the agent bus provides several benefits, including:

* Loose coupling between services, making it easier to develop and maintain individual components
* Scalability, as services can be added or removed without affecting the overall system
* Reliability, as the system can handle failures and network partitions without affecting the overall state
* Tracability, logging, and observability, making it easier to monitor and debug the system

## Core Agentic Services (Phase 1)

To support the core agent framework, the following services are introduced:

*   **Agent Registry Service**: Manages agent manifests, their definitions, capabilities, and configurations. It acts as the central source of truth for agent metadata.
*   **Tool Registry Service**: Manages available tools, their interfaces, and how they can be invoked by agents. It acts as the central source of truth for tool metadata.
*   **Agent Orchestrator Service**: Responsible for scheduling, initiating, and managing the execution lifecycle of agent instances. It coordinates with the Agent Execution Environment.
*   **Agent Execution Environment (Runtime)**: Provides the secure, isolated, and sandboxed environment where agent code runs and interacts with registered tools. This is a critical component for secure and controlled agent operation.
*   **Observability Service**: Aggregates logs, traces, and metrics from all Agentic components, leveraging the Agent Bus, to provide comprehensive monitoring and debugging capabilities.
*   **Agent Template Service**: Manages and provides access to pre-defined agent templates, facilitating rapid agent development and deployment.

These services interact primarily via the Agent Bus for asynchronous communication, ensuring loose coupling. Direct API calls are used for synchronous requests where immediate responses are required (e.g., retrieving an agent manifest from the Agent Registry).
