# Automated Task Execution (Enterprise Building Block)

## Definition
Automated Task Execution is the enterprise capability to define, schedule, orchestrate, and monitor the execution of tasks and workflows that are performed autonomously by agents.

## Purpose
To enable the reliable and efficient automation of business processes and operational tasks, reducing manual effort, improving consistency, and accelerating response times across the enterprise.

## Key Responsibilities
*   **Task Definition**: Specifying the objectives, inputs, and expected outputs of an automated task.
*   **Execution Orchestration**: Managing the sequence of steps, agent assignments, and tool invocations required to complete a task.
*   **Scheduling**: Initiating tasks based on predefined schedules or triggers.
*   **Progress Monitoring**: Tracking the status and progress of executing tasks.
*   **Error Handling**: Defining strategies for managing failures and exceptions during task execution.

## Relationship to Other ABBs
*   **Agent Management**: Relies on agents defined and managed by the Agent Management ABB.
*   **Tooling Integration**: Agents performing tasks will utilize tools integrated via the Tooling Integration ABB.
*   **Operational Visibility**: Provides critical data points (task status, agent actions) for the Operational Visibility ABB.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Deterministic **Capability** / SOP-execution. This ABB realises the `recognise_and_reuse` / `SOP Execution` posture (anchor doc §7) — execution of known, deterministic work.
- **Vocabulary map:** "task / workflow execution" → a **Session** (workflow instance) running a **Pattern** pipeline; "execution orchestration / scheduling" → Session lifecycle (`SESSION-MODEL.md`); "tool invocations" → **Capability** calls (`kind=tool|skill`, §10).
- **Relationship to core:** When Strategy Selection returns a known SOP (Principle 1), this ABB drives deterministic execution with no exploration. The Learning Loop promotes successful reasoning into exactly this kind of deterministic task (§13).
- **No rename:** "automated task execution" retained.
