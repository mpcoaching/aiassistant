# Agentic System Roadmap

This document outlines the phased delivery of the Agentic system, focusing on achieving usable, MVP-ish outcomes at each stage. It will be used to track the decomposition and completion of its parts over time.

## Phase 1: Control Center & Core Manual Workflows (MVP)

**Goal:** Establish a central interface for business operations, enabling manual execution of key workflows, monitoring, receiving suggestions and insights, and basic interaction with an assistant. This phase will leverage the agentic bus for workflow execution and scheduling, with robust control from the UI.

**Key Deliverables:**
*   **User Interface / Control Center:** A dashboard or application providing:
    *   Ability to manually trigger, schedule, and run defined workflows by placing requests onto the agentic bus.
    *   Monitoring of workflow execution status, including the ability to **stop, pause, and start** running workflows.
    *   Display of system suggestions and insights.
    *   A chat interface for direct interaction with a basic "assistant" (initially rule-based or simple LLM integration).
*   **Core Workflows (Code-Based Building Blocks):**
    *   **Start Work Session:** A workflow to initiate a focused work session, helping to define priorities and biggest levers for the business.
    *   **Close Work Session:** A workflow for debriefing and downloading information after a work session, capturing achievements and learnings.
    *   **Daily Task Tracking:** A system to track daily tasks, allowing for analysis of wins, productivity, and progress.
    *   **Lead Enrichment:** An API-driven workflow to enrich lead information from a browser session, identifying interesting leads, gathering relevant data, and suggesting next steps (e.g., commenting opportunities, nurturing strategies).

## Phase 2: Basic Agentic System & Executive Assistant

**Goal:** Implement the foundational agentic system, starting with an executive assistant that learns and captures information, and introduce the C-Suite layer for strategic identification.

**Key Deliverables:**
*   **Executive Assistant (Chat Interface):**
    *   An AI-powered executive assistant accessible via chat (similar to current interaction).
    *   Ability to capture important information from conversations and store it for later use, enabling continuous learning and context retention.
*   **C-Suite Layer (Identification Only):**
    *   Basic implementation of C-Suite agents (CEO/Chief of Staff, COO, CTO, CMO, CFO/Admin) primarily for identifying tasks, needs, or strategic directions.
    *   At this stage, the identified tasks are surfaced to the user (Martin) for manual execution, as the autonomous execution capabilities are not yet in place.

## Phase 3: Automated Workflow Generation & One Agent Team

**Goal:** Enable the agentic system to autonomously generate, build, test, and deploy workflows, starting with one dedicated agent team, and introduce self-healing capabilities.

**Key Deliverables:**
*   **Automated Workflow Generation & Deployment:**
    *   Integration of one agent team (e.g., the CTO agent with `opencode`) to:
        *   Receive a spec for a new workflow or skill.
        *   Automatically generate the necessary code-based building blocks.
        *   Build, test, and deploy these new capabilities to the workflow system.
*   **Self-Healing Workflows:**
    *   The workflow execution system is enhanced to log errors in a structured format.
    *   An AI agent (e.g., a specialized monitoring or reflection agent) monitors these error logs.
    *   The AI agent can identify recurring errors, diagnose potential causes, and trigger the build loop (via the CTO agent) to propose and implement fixes.

## Phase 4: Full Agent Team Implementation

**Goal:** Implement the remaining C-Suite teams and fully develop their respective workflows, skills, and tools, leading to a comprehensive, self-extending agentic system.

**Key Deliverables:**
*   **Remaining C-Suite Agents:**
    *   Full implementation and integration of the COO, CMO, and CFO/Admin agents.
    *   Development of specific workflows, skills, and tools tailored to each C-Suite role's responsibilities.
*   **Enhanced Autonomous Operation:**
    *   The system moves towards more autonomous operation, with C-Suite agents identifying needs, triggering workflow generation, and overseeing execution with minimal human intervention.
*   **Continuous Improvement & Expansion:**
    *   Ongoing development of new skills and tools, driven by the Reflection Agent and the self-extension cycle.
    *   Refinement of existing workflows and agent interactions based on performance data and insights.
