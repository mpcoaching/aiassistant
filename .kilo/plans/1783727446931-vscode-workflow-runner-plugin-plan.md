# VS Code Workflow Runner Plugin — Review & Implementation Plan

> Scope: `agentic/vscode-workflow-runner/` (the VS Code extension) and its backend
> `agentic/src/workflow-runner/` (Python CLI / executor / MCP server). Goal: a
> production-ready VS Code plugin that automates configurable workflows for the
> custom agentic system, built with an AI auto-coding tool (Kilo Code / Cline).
>
> **Key architectural decision (confirmed with user):** the plugin is a **thin
> client to the Workflow Engine microservice**. It builds workflow requests and
> posts them to the Workflow Engine over HTTP; execution (skill prompts via
> LiteLLM, tool steps in the sandboxed Agent Execution Environment) happens on
> the server side. The plugin subscribes to Agent Bus events / polls status for
> progress. It does **not** execute skills or shells locally in production.

---

## Part A — Structured Code Review (current state)

### A0. Headline finding
The plugin today **does not automate anything**. It only *composes* skill prompts
and prints them. `run_aider.sh:2` literally says *"clear out all incoming arguments
sent by the broken extension,"* confirming skill execution was never wired.
`technical-design.md` specifies a `Runtime Interface` (start/send/add/drop/run/exit)
"implemented by an Aider Runtime," but **no runtime module exists** in
`agentic/src/workflow-runner/`. Skill steps return `status: completed` with
`output: {prompt, status: "ready_for_execution"}` (`skill_handler.py:47-55`) and the
executor marks the whole workflow `completed` (`executor.py:101-111`) — a misleading
status, since nothing was actually executed.

### A1. Functional gaps
- **Skill steps never execute.** `skill_handler.py:47` composes a prompt and returns;
  no LLM/Aider call. `extension.ts:70` just dumps the JSON to the output channel for a
  human to copy into an agent. Not automation.
- **Undefined Runtime.** The Runtime Interface from `technical-design.md` is absent in
  code. No `runtime.py`, no Aider/LiteLLM driver.
- **Skill outputs not captured into context.** `executor.py:103` stores the skill's
  `{prompt,…}` dict, not a real result, so downstream steps / chain context-carry-forward
  (`cli.py:192-194`) is meaningless.
- **Pause / resume / stop not wired.** `state.py` has a `paused` status but nothing sets
  it; `get_workflow_status` exists in `server.py` but the extension never calls it.
  `running-workflows.md` claims pause/resume/stop — unimplemented.
- **No MCP conformance.** `server.py` is hand-rolled stdio JSON-RPC: it emits a
  capabilities blob *before* `initialize`, never implements `tools/list`, and does not use
  the `mcp` package despite the README listing `mcp` as a prerequisite.

### A2. Missing required features
- **No role/authorization enforcement.** `WorkflowDefinition.role` is loaded
  (`models.py:38`) but never checked. Any workflow can be run by anyone.
- **`workflowDirs` setting is dead.** `package.json` declares it but `extension.ts` uses a
  hardcoded `agentic/src/workflow-runner/cli.py` path (`extension.ts:104`) and a fixed
  regex (`package.json:29,35`); the setting is ignored.
- **No workflow catalog / discovery UI.** Menus only appear for files matching
  `workflows/*.ya?ml`; there is no TreeView, no status panel, no run history.
- **No cancellation / concurrency control.** Spawned child (`extension.ts:111`) is never
  killed; no signal handling; no multiple simultaneous runs.
- **No structured artifact capture.** `outputs:` declared in workflows but never produced
  or surfaced.
- **No event publishing / observability.** Nothing emits to the Agent Bus or OTEL
  (despite `ai-assistant-infra/configs/otel/` existing).
- **No authentication** on the MCP server or CLI.
- **Extension has zero tests** — no `@vscode/test-electron` harness, no CI, no vsce
  publishing config (no icon/LICENSE/ categorization).

### A3. Security vulnerabilities (must-fix before any real use)
- **CRITICAL — command injection via tool steps.** `tool_handler.py:53` runs
  `subprocess.run(command, shell=True, …)` where `command = step.uses`
  (`composer.py:160`). `${key}` substitution (`composer.py:167-170`) expands context
  values into the shell string. Any `.yaml` in the repo can run arbitrary shell commands
  on the developer's machine when "Run Workflow" is clicked. **No allowlist / denylist.**
- **No trust / signature verification** of workflow or skill files before execution.
- **Unauthenticated RCE surface.** `server.py` runs `execute_workflow_from_file` which can
  shell out; anyone able to launch the MCP server can trigger it.
- **Arbitrary path traversal.** `workflow_handler.py:49` resolves `step.uses` as a direct
  filesystem path with no restriction.
- **Secret leakage.** Inputs/context are stored in cleartext in `.wf/*.json`
  (`state.py:64`) and printed by `cli.py`; no redaction/encryption, and `.wf/` may not be
  git-ignored.
- **No resource limits.** `tool_handler.py` has a 300s timeout but no memory/CPU caps or
  sandbox — host compromise / DoS risk.

### A4. Scalability limitations
- **File-based state, no locking.** `<wfdir>/.wf/*.json` (`state.py:27`); concurrent runs
  race/corrupt state.
- **Per-call full graph rebuild.** `chain.py:24-62` rescans & reloads every workflow file
  on each call; no caching.
- **No database / single-user, single-machine.** Contradicts the Workflow Engine SBB, which
  is a service tracking Workflow Instances.
- **Synchronous blocking model.** `server.py` blocks per request; `extension.ts` blocks on
  `spawn`. Chains of 9 workflows run serially with no streaming.
- **Unbounded recursion.** `workflow_handler.py:43` recurses into sub-workflows with no
  depth limit (chain detection guards cycles, but this path does not) → stack overflow /
  resource exhaustion.
- **Environment coupling.** Backend depends on a local `.venv`
  (`agentic/src/workflow-runner/.venv`); extension hardcodes `python3` and only
  `workspaceFolders[0]` (`extension.ts:103`).

### A5. Misalignment with the agentic system's core requirements
(`docs/SYSTEM_CONTEXT.md`, `docs/architecture/Phase-1-SBBs.md`)
- **Event Bus / Agent Bus not used.** System mandates idempotent event-driven comms;
  plugin uses local subprocess + hand-rolled stdio — no `WorkflowStarted`/`WorkflowCompleted`
  events.
- **No sandboxed execution.** System mandates a secure Agent Execution Environment; plugin
  runs `shell=True` on the host.
- **Workflow Engine SBB unmet.** Requires "state management (pause, resume, stop), event
  publishing" — none wired.
- **Observability Service unmet.** Local `.log` files only; no OTEL/trace export.
- **Idempotency unmet.** Re-running a workflow with tool steps has side effects.
- **Role model unmet.** `role` maps to Agent Registry permissions but is never enforced.
- **Data ownership unmet.** Workflow Instance is owned by the Workflow Engine, but the
  plugin persists state in the repo's `.wf/`.
- **Control Center UI is the intended trigger**, not a separate VS Code right-click menu.

---

## Part B — Implementation Plan (thin client to Workflow Engine)

### B0. Target architecture
```
VS Code Plugin (TS)                Agentic System
┌────────────────────┐   HTTP(S)   ┌──────────────────────┐
│ TreeView/catalog   │ ─────────▶  │ Workflow Engine (Svc) │
│ Run/Stop commands  │  POST /run  │  - validates, enforces│
│ Settings + token   │ ◀─────────  │    role via Agent Reg │
│ Status polling /   │  status+events│ - publishes events  │
│  Bus subscription  │            │    to Agent Bus       │
└────────────────────┘            │  - Orchestrator ──────┼─▶ Agent Execution
                                  │  - Observability(OTEL)│   Environment (sandbox)
                                  └──────────────────────┘   - skill→LiteLLM
                                                              - tool→sandbox shell
```
The plugin only: discovers workflows, collects inputs, calls `POST /workflows/run`,
polls `GET /workflows/{id}` (or consumes `WorkflowProgress` events via SSE/WebSocket),
and renders progress. **No skill/LLM or shell execution in the plugin.**

### B1. Prerequisites
- VS Code 1.85+, Node 18+, npm, `vsce`.
- Access to the agentic system: **Workflow Engine base URL**, an **API token**
  (OAuth2 bearer / mTLS), **Agent Bus** endpoint (Redis Streams/NATS), **OTEL** endpoint.
- A running **Workflow Engine** (or the dev stub below) and **LiteLLM** proxy.
- `.env` secrets live server-side only; the plugin stores its token in VS Code
  `SecretStorage`, never in `settings.json`.
- AI auto-coding tool configured (Kilo Code / Cline) with repo context loaded.

### B2. API contract the plugin must satisfy (define first, against the SBB)
OpenAPI `workflow-engine.yaml` (checkin under `agentic/vscode-workflow-runner/contract/`):
- `POST /workflows/run` → `{workflow_ref, inputs, role?, callback?, run_id}` → `202 {run_id, status}`
- `GET  /workflows/{run_id}` → `{status, current_step, total_steps, step_results[], outputs, error?}`
- `POST /workflows/{run_id}/stop` → `202`
- `GET  /workflows` (catalog) → `[{ref, name, role[], inputs[], outputs[]}]`
- `GET  /workflows/{run_id}/events` (SSE) → `WorkflowProgress` events.
Contract tests treat this as the source of truth for both plugin and engine.

### B3. Suggested prompt sequences for the auto-coding tool
Feed in order; each prompt references existing files to reuse (schemas from `models.py`,
discovery logic from `chain.py`/`loader.py`).

1. **Scaffold & contract**
   > "In `agentic/vscode-workflow-runner/`, add an OpenAPI spec `contract/workflow-engine.yaml`
   > with POST /workflows/run, GET /workflows/{run_id}, POST …/stop, GET /workflows (catalog),
   > and GET …/events (SSE) as described. Generate a typed `apiClient.ts` (fetch + bearer token
   > from `SecretStorage`) and `types.ts` matching the responses. Keep `extension.ts` activate()
   > entry but move logic into `src/client/`, `src/explorer/`, `src/commands/`."

2. **Catalog + TreeView + commands**
   > "Replace the regex context menu with a Workflow Explorer TreeView populated from
   > `GET /workflows`. Add commands `run`, `runChain`, `stop`, `refresh` and a status
   > `TreeItem`. Remove the hardcoded `agentic/src/workflow-runner/cli.py` path and the unused
   > `workflowDirs` setting; replace with `workflowRunner.engineUrl` (secret-managed token)."

3. **Run flow + progress + cancellation**
   > "On run: collect missing `inputs` via `showInputBox` (reuse validation shape from
   > `cli.py:cmd_validate`), POST /workflows/run, then poll `GET /workflows/{run_id}` every 1s
   > and stream `WorkflowProgress` SSE into an OutputChannel + progress notification. Wire Stop
   > to `POST …/stop` and kill any in-flight poll. Show a terminal-style stepper for steps."

4. **Trust, roles, secrets**
   > "Enforce `role` from the catalog response against the authenticated user (token claims);
   > disable Run when unauthorized. Add workflow signature/trust check before enabling Run.
   > Store the engine token in `SecretStorage`; never log inputs/values; redact secrets in all
   > OutputChannel writes."

5. **Observability + Bus subscription**
   > "Emit OTEL spans for run/stop via the VS Code OTEL hook; subscribe to Agent Bus
   > `WorkflowProgress` events and reconcile with polling. Add a `contributes.configuration`
   > block for `agentBusUrl` and `otelUrl`."

6. **Tests + packaging**
   > "Add `@vscode/test-electron` tests: (a) catalog renders from mocked engine, (b) run→poll→
   > complete updates TreeView, (c) stop cancels polling, (d) unauthorized role disables Run,
   > (e) secret redaction in logs. Add `vsce` packaging (icon, LICENSE, README, categories,
   > `engines.vscode`). Add GitHub Actions CI running `tsc`, ESLint, and the test harness."

> Optional dev stub (so the plugin is buildable before the real engine exists): a small
> FastAPI/Flask app in `agentic/vscode-workflow-runner/dev-stub/` implementing the contract
> and delegating to the **existing** `execute_workflow_from_file` for local testing — but
> with `shell=True` removed (see B5). Mark clearly as dev-only.

### B4. Phased testing checkpoints
- **Checkpoint 1 (unit):** `apiClient` + types compile; contract tests pass against a mock
  server (msw). No network to real engine.
- **Checkpoint 2 (integration, dev stub):** full run→progress→stop against `dev-stub`;
  TreeView + OutputChannel update correctly; stop cancels.
- **Checkpoint 3 (security):** injection test (malicious tool step must NOT execute locally —
  plugin never shells out), secret-redaction test, unauthorized-role test, signature check.
- **Checkpoint 4 (real engine):** run against the actual Workflow Engine + sandboxed
  execution env; verify `WorkflowStarted`/`WorkflowCompleted` events appear on the Agent Bus
  and traces in Observability.
- **Checkpoint 5 (e2e chain):** run `delivery.chain` end-to-end; confirm 9-step progress,
  outputs captured, pause/resume/stop honored by the engine and reflected in the UI.

### B5. Integration steps with the agentic system
1. **Register the plugin** as a Workflow Engine API client; issue a scoped token (Agent
   Registry / IAM), store in `SecretStorage`.
2. **Align role enforcement** with the Agent Registry: plugin sends the user's roles; engine
   authorizes per `WorkflowDefinition.role` (`models.py:38`).
3. **Wire events**: engine publishes `WorkflowStarted|Progress|Completed|Failed` to the Agent
   Bus; plugin consumes via SSE/WebSocket or polls.
4. **Observability**: plugin emits OTEL spans; engine exports traces/metrics to the existing
   OTEL collector (`ai-assistant-infra/configs/otel/`).
5. **Execution environment**: engine runs skill prompts through **LiteLLM** and tool steps in
   the **sandboxed Agent Execution Environment** — replacing the unsafe `shell=True` in
   `tool_handler.py:53` (keep only for the dev stub, if at all, behind an explicit allowlist).
6. **Control Center parity**: ensure the same API the plugin uses is what the Control Center UI
   calls, so both surfaces stay consistent.
7. **Data ownership**: Workflow Instance state lives in the Workflow Engine, not in repo `.wf/`
   (migrate/retire `state.py` file store for production; keep for local dev only).

### B6. Post-deployment maintenance & iteration
- **Schema versioning:** bump `WorkflowDefinition.version` (`models.py:34`) on contract change;
  engine + plugin negotiate version; keep backward-compat parsers (`loader.py`).
- **Telemetry:** track run volume, failure rate, step latency via Observability; feed
  Langfuse prompt-optimization on the skill prompts (per SYSTEM_CONTEXT "Prompt Optimisation").
- **Feedback loop:** surface a "refine workflow/skill" action in the plugin that opens the
  relevant YAML in the editor; use the agentic system's self-extension cycle to evolve skills.
- **Security hygiene:** rotate plugin tokens, re-verify workflow signatures on pull, keep
  `dev-stub` out of production builds, periodic dependency/CVE scans.
- **Iteration cadence:** treat plugin + contract as one versioned unit; add contract tests
  before any engine change; extend catalog/TreeView as new SBBs (Work Session, Task Tracking)
  expose APIs.

---

## Open questions / risks
- **Workflow Engine existence:** repo contains no Workflow Engine service implementation yet.
  Plan assumes it is built/owned by the agentic system; the `dev-stub` bridges the gap. Confirm
  the engine's transport (HTTP vs gRPC) and auth (bearer vs mTLS) before Checkpoint 4.
- **Event transport:** Agent Bus tech (Redis Streams vs NATS) determines the plugin's SSE vs
  WebSocket vs polling approach — finalize in B2 contract.
- **Local dev fallback:** decide whether the plugin keeps a "run locally" mode (using the
  existing Python runner) for offline use, clearly separated from the production thin-client path.
