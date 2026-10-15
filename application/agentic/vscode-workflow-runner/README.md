# Workflow Runner VS Code Extension

A **thin client** VS Code plugin for the agentic Workflow Engine. It discovers
runnable workflows from the engine's catalog, collects required inputs, submits
run requests, and observes progress (via Server-Sent Events, with polling
fallback). It does **not** execute skills or tools locally — execution happens
server-side in the sandboxed Agent Execution Environment.

See `contract/workflow-engine.yaml` for the API contract shared with the
Workflow Engine service.

## Architecture

```
VS Code Plugin (TS)                Agentic System
┌────────────────────┐   HTTP(S)   ┌──────────────────────┐
│ Workflows TreeView │ ─────────▶  │ Workflow Engine (Svc) │
│ Run / Stop / Refresh│  POST /run │  - validates + enforces│
│ Token (SecretStorage)│◀───────── │    role via Agent Reg │
│ Progress / Cancel  │  status+events│ - publishes Agent Bus │
└────────────────────┘            │  - Orchestrator ──────┼─▶ Agent Execution
                                 │  - Observability(OTEL)│   Environment (sandbox)
                                 └──────────────────────┘   - skill→LiteLLM
                                                             - tool→sandbox shell
```

## Features

- **Workflows view** in the Explorer showing the engine catalog.
- **Run Workflow** / **Run Workflow Chain**: collect missing inputs, submit, and
  watch progress with a cancellable notification (Cancel → engine `stop`).
- **Stop Workflow**: stop the active run for a workflow.
- **Refresh Catalog** and **Set Engine Token** from the view title.
- **Role gating**: workflows whose `role` excludes your token's roles are locked
  in the UI (the server remains the authoritative enforcer).
- **Secret redaction**: any input/context value whose name looks like a secret
  is masked before it is written to the output channel.

## Prerequisites

- VS Code 1.85+
- A reachable Workflow Engine (or the local dev-stub, see below)
- An API token scoped to the Workflow Engine

## Settings

| Setting | Default | Description |
|---|---|---|
| `workflowRunner.engineUrl` | `http://localhost:8000` | Base URL of the Workflow Engine |
| `workflowRunner.agentBusUrl` | `""` | Optional Agent Bus endpoint |
| `workflowRunner.otelUrl` | `""` | Optional OTEL endpoint |
| `workflowRunner.pollIntervalMs` | `1000` | Polling interval when SSE is unavailable |
| `workflowRunner.trustedOnly` | `false` | Only enable Run for trust-signed workflows |

## Build & run (Extension Development Host)

```bash
cd agentic/vscode-workflow-runner
npm install
npm run compile
```

Press `F5` to launch the Extension Development Host. Set the engine token via
**Workflow Runner: Set Engine Token**, then use the **Workflows** view.

## Tests

```bash
npm test
```

Runs `tsc` then `node --test` over the unit/integration tests (HTTP client
against an in-process mock engine, redaction, and role authorization).

## Local dev-stub

Before the real Workflow Engine exists, `dev-stub/server.py` implements the
contract locally (reusing `agentic/src/workflow-runner`). It is **dev-only** and
must never be deployed.

```bash
cd agentic/vscode-workflow-runner/dev-stub
../.venv/bin/python server.py 8000
```

Then set `workflowRunner.engineUrl` to `http://127.0.0.1:8000`.

## Security notes

- The token is stored in VS Code `SecretStorage`, never in `settings.json`.
- Local tool execution in `agentic/src/workflow-runner/handlers/tool_handler.py`
  was hardened to `shell=False` against an allowlist; this path is only used by
  the dev-stub. Production execution runs in the server-side sandbox.
