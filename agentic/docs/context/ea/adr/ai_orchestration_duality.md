# ADR: AI-Assisted Orchestration with Prompt/Code Skill Duality

## Status

Accepted — Phase 2 direction for the Workflow Runner.

## Context

The Workflow Runner today executes workflows as a fixed sequential loop
(`executor.py:execute_workflow`). A skill step is a prompt spec (markdown in
`agentic/skills/`) composed with role + context and run through an LLM runtime
(`handlers/skill_handler.py`). The user wants to:

- Rough out integration-style processes quickly with AI assistance, in the
  style of Boomi / Azure Logic Apps / Power Automate — a modular set of
  composable processes.
- Harden them over time: where a skill can be deterministic it should become a
  **reused code module** callable from many workflows; where it needs judgment
  it stays an **AI call**.
- Keep execution **asynchronous and long-running** (a run returns an id
  immediately and completes as fast as it can), not a blocking request.

The event bus (`bus.py`, RabbitMQ `workflow.mode` exchange) was introduced
early precisely to support this choreographed, async model.

## Decision

1. **AI-assisted low-code orchestration.** Workflows are modular, named
   processes composed of skills (AI/prompt), tools (code), and sub-workflows
   (processes). This is the integration-platform mental model.

2. **Skill implementation duality.** Every skill has an `implementation` tier:
   `prompt` (LLM call), `code` (compiled/reusable module), or `distilled`
   (LLM-generated deterministic implementation). Workflows reference skills
   **by name only**; the tier is resolved at execution time and may change
   without editing any workflow. This is the core "duality" that makes the
   system powerful: the same skill is both an AI prompt and, where plausible, a
   code module.

3. **Event bus as choreography backbone.** A choreographer consumes
   `workflow.lifecycle.WorkflowStarted` and emits `skill.requested` per step;
   skill workers consume and emit `skill.completed`; the next step is triggered
   by the bus, not a fixed `while` loop. The existing `executor.py` loop is
   retained as a legacy fast-path and test harness.

4. **AI authoring via MCP.** The MCP server (`server.py`) gains
   `list_skills`, `create_skill`, `create_workflow`, `compile_skill` tools so
   an AI can discover the catalog, scaffold flows, and promote skills to code.

5. **Async, long-running UI.** A run returns a `workflow_id` immediately.
   Clients poll `GET /workflows/{id}/status` or subscribe to
   `workflow.lifecycle.*` events. Runs may take seconds to minutes.

## Consequences

- Workflows become stable contracts decoupled from skill internals.
- Skills are reusable across many workflows and promotable
  (prompt → code / distilled) without breaking callers.
- Execution is asynchronous, durable (`state.py` / `db.py`), and
  crash-recoverable via `correlation_id` plus the bus fallback spooling in
  `bus.py`.
- New components: **Registry**, **Compiler**, **Choreographer**, **MCP
  Authoring** tools.
- The synchronous executor remains as a legacy fast-path / test harness.
- Testing must follow `docs/development/test_standards.md` (TDD, 100% unit
  coverage, behaviour-based, mocked externals).

## References

- `docs/architecture/sa/utilities/workflow-runner/ai-orchestration-design.md`
- `docs/architecture/sa/utilities/workflow-runner/technical-design.md`
- `docs/architecture/sa/utilities/workflow-runner/workflow-schema.md`
- `docs/development/test_standards.md`
