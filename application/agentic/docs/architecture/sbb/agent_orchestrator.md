# Agent Orchestrator (Solution Building Block)

## Definition
The Agent Orchestrator is a core service responsible for managing the execution lifecycle of agent instances. It schedules agent tasks, initiates their execution within the Agent Execution Environment, monitors their progress, and handles task completion or failure.

## Purpose
To provide a robust and reliable mechanism for initiating and controlling agent activities, ensuring that agents are executed securely, efficiently, and in accordance with defined tasks and workflows.

## Key Responsibilities
*   **Task Scheduling**: Accepting requests to run agents and scheduling their execution.
*   **Agent Instantiation**: Requesting the Agent Execution Environment to start a new agent instance.
*   **Execution Monitoring**: Tracking the status and progress of running agents.
*   **Tool Invocation Coordination**: Directing the Agent Execution Environment to invoke specific tools as requested by an agent.
*   **Error Handling & Retries**: Implementing strategies for dealing with execution failures.
*   **State Management**: Maintaining the high-level state of ongoing agent tasks.

## Interactions
*   **Exposes**: RESTful API for initiating agent tasks, querying task status, and cancelling tasks.
*   **Consumes**:
    *   Events from Agent Registry (for agent definition updates).
    *   Events from Tool Registry (for tool availability updates).
    *   Events from Agent Execution Environment (execution results, errors, progress, tool invocation outcomes).
*   **Publishes**:
    *   Commands to Agent Execution Environment (start agent, execute step, invoke tool).
    *   Events to Observability Service (execution start/end, errors, warnings).
    *   Events to the Agent Bus (e.g., `AgentTaskStarted`, `AgentTaskCompleted`, `AgentTaskFailed`).

## Data Ownership
*   **Source of Truth for**: Active Agent Executions, Task Status, Agent Instance State (high-level).

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Strategy / Session dispatch. The Agent Orchestrator decides *that* a Session runs (it instantiates and supervises the execution of a pattern pipeline); it does **not** decide *how* — Strategy Selection does.
- **Vocabulary map:** "agent instance / agent task" → a **Pattern Runtime** execution of a pattern step or Capability call within a **Session** (workflow instance). "Task scheduling / execution monitoring" → Session lifecycle management (`SESSION-MODEL.md`).
- **Relationship to core:** The Orchestrator is the dispatch surface between Strategy Selection (which picks the Strategy + Pattern pipeline) and the Pattern Runtime (which executes it, `RUNTIME-MAPPING.md`). Events it publishes (`AgentTaskStarted/Completed/Failed`) are Session lifecycle events.
- **No rename:** the term "agent" is retained as implementation terminology; under the model it is a transient participant configured by a Strategy/Pattern.
