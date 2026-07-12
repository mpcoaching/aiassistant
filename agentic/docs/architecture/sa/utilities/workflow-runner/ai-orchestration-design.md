# AI-Assisted Orchestration — Design

This document is the implementation spec for the prompt/code skill duality and
event-bus choreography described in the ADR
`docs/context/ea/adr/ai_orchestration_duality.md`. Build work follows this
document, using TDD and the patterns defined in
`docs/development/test_standards.md`.

## 1. Mental Model

An **integration platform in miniature** (Boomi / Azure Logic Apps shaped):

- A **workflow** is a named, modular process: a list of typed steps with
  declared `inputs` / `outputs`.
- A **step** is one of:
  - `skill` — an AI/prompt operation (the LLM call).
  - `tool` — a code/shell operation.
  - `workflow` — a sub-process (reuse).
- A **skill** is the unit of reusable intelligence. It starts life as a prompt
  spec and can be promoted to a code module.

The user roughs a flow out with AI (via the Control Center UI or an MCP-powered
agent), then hardens skills from prompts into code where that is plausible.

## 2. Architecture

```
 AI Agent / Control Center UI
            │  (author)            │ (trigger / poll status)
            ▼                      ▼
   MCP Authoring Server      Workflow Engine API (api.py)
   (list/create/compile)            │
            │                       │ publishes WorkflowStarted
            ▼                       ▼
   Registry (catalog)        Event Bus (RabbitMQ, workflow.mode)
   Compiler (prompt→code)          │  skill.requested / skill.completed
                                   ▼
                            Choreographer  ──▶  Skill Workers
                                                   │  ├─ prompt  → LLM runtime (runtime_client)
                                                   │  ├─ code    → compiled module
                                                   └─ distilled→ deterministic impl
                                   ▼
                            workflow.lifecycle.* events  ──▶ UI / observers
```

## 3. Skill Lifecycle (the duality)

A skill moves through tiers. The **tier is metadata**, never encoded in the
workflow that calls it.

| Tier        | What it is                                  | When            |
|-------------|---------------------------------------------|-----------------|
| `prompt`    | Markdown spec run via LLM runtime           | Rough-out (default) |
| `code`      | Generated Python wrapper module (`run(ctx)`)| Plausible & stable |
| `distilled` | LLM-generated deterministic implementation  | Verified, promoted |

Promotion is one-way and gated: a `code`/`distilled` module replaces the prompt
path for execution but the prompt spec is retained as documentation/source.

### Skill Module Interface (Pattern: unified `run` contract)

Every skill — regardless of tier — exposes the same callable so the executor
and workers are tier-agnostic:

```python
def run(context: Dict[str, Any], *, role: Optional[str] = None) -> SkillResult:
    ...
```

`SkillResult` carries `status`, `output`, and `error`. The registry resolves a
skill name to its active implementation and returns a uniform callable.

## 4. Registry (catalog)

The Registry is the single source of truth for discoverable artifacts:
skills, tools, and workflows. It resolves a **name** to an artifact and tracks
each skill's `implementation` tier and compiled module path.

Responsibilities:
- `list_skills() -> List[SkillRecord]` — for discovery (MCP `list_skills`, UI).
- `get_skill(name) -> SkillRecord` — resolved metadata + active callable.
- `register_skill(record)` / `register_workflow(record)` — for authoring.
- `resolve(name, kind) -> Path` — back-compat with `loader.py` resolution.

`SkillRecord` fields: `name`, `description`, `kind`, `implementation`
(`prompt|code|distilled`), `spec_path` (markdown), `module_path` (optional
compiled), `inputs`, `outputs`, `version`.

The Registry is backed by the filesystem layout that already exists
(`agentic/skills/*.md`, `agentic/tools/*.yaml`,
`agentic/docs/workflows/*.yaml`) and a generated `manifest` for fast lookup.
No schema DDL changes are required (catalog is filesystem + manifest).

## 5. Compiler (prompt → code)

Promotes a `prompt` skill to `code` (Tier 1) and, later, `distilled`
(Tier 2).

- **Tier 1 (wrapper codegen):** generate `agentic/skills/_compiled/<name>.py`
  exposing `run(context)` that performs exactly what
  `composer.compose_skill_prompt` + `handlers.skill_handler` do today
  (compose prompt, call runtime). Deterministic, cheap, reusable, importable.
  Auto-registers as a bus consumer and an MCP tool.
- **Tier 2 (distilled):** an LLM takes the spec + observed runs and produces a
  deterministic implementation, verified by tests before promotion (future
  phase, gated by `test_standards.md`).

The Compiler is idempotent and records `module_path` + `implementation` in the
Registry; it never mutates the calling workflow.

## 6. Choreographed Execution

Replaces the fixed `while` loop in `executor.py` with bus-driven choreography:

- `run_workflow` (api.py) persists state, publishes
  `workflow.lifecycle.WorkflowStarted`, and returns `workflow_id` immediately.
- A **Choreographer** consumer:
  - on `WorkflowStarted` → emits `skill.requested` for step 0.
  - on `skill.completed` → advances state; if more steps, emits next
    `skill.requested`; else publishes `WorkflowCompleted`.
- **Skill Workers** consume `skill.requested`, resolve the skill via the
  Registry (tier-agnostic `run`), publish `skill.completed` with results.
- Routing keys: `skill.requested`, `skill.completed` (topic exchange
  `workflow.mode`, added to `bus.py` topology). Durable queues +
  `correlation_id` give crash recovery.

The synchronous `execute_workflow` loop is retained as `execute_workflow_sync`
for tests and as a fast-path.

## 7. MCP Authoring Surface

Extend `server.py` with tools (each a thin wrapper over Registry/Compiler):

- `list_skills()` — catalog discovery.
- `create_skill(spec)` — author a skill markdown + register.
- `create_workflow(spec)` — author a workflow YAML + register.
- `compile_skill(name)` — promote `prompt` → `code` via Compiler.

These let an AI scaffold flows and harden skills, fulfilling the "rough it out
with AI" requirement.

## 8. Async UI Contract

The Control Center UI (Phase 1) already has an Instances tab that polls
`GET /workflows/{id}/status`. With choreography:

- `POST /workflows/{name}/run` returns `{workflow_id, status:"running"}`
  immediately (does not block on completion).
- Instances tab polls status until terminal (`completed|failed|stopped`).
- Future: subscribe to `workflow.lifecycle.*` for push updates (SSE/WebSocket
  gateway) — not required for v1.

This satisfies "long-running process that may not immediately complete, but
completes as fast as it can."

## 9. Patterns (established as we build)

1. **Skill Module Interface** — name → tier-agnostic `run(context)`.
2. **Registry** — name → artifact resolution + manifest; single catalog.
3. **Compiler** — prompt-spec → code module, idempotent, tier-tracked.
4. **Choreography** — step progression driven by bus events, not a loop.
5. **TDD** — red/green/refactor; 100% unit coverage; behaviour-based; externals
   (bus, runtime, filesystem) mocked.

## 10. Phased Build Plan (TDD)

1. **Registry** (`registry.py`) + tests — catalog + resolution.
2. **Compiler** (`compiler.py`) + tests — Tier 1 wrapper codegen + tier tracking.
3. **Skill Module Interface** integration — `skill_handler` resolves via
   Registry; tier-agnostic `run`.
4. **MCP Authoring** tools on `server.py` + tests.
5. **Choreographed Executor** — bus router + skill worker + `skill.*` keys;
   retain sync path.
6. **Async UI hardening** — immediate run response, polling (already present).

Each phase ships with tests that pass before the next begins.
