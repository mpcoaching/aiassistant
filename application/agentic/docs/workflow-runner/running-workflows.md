# Running Workflows

This document explains how to run workflows and workflow chains in this project, both from the command line and via the VS Code right-click menu.

## Overview

A **workflow** is a YAML file that defines a sequence of steps. Steps can be:

- **skill** steps: compose an AI prompt from a role + skill definition + context
- **tool** steps: execute a shell command directly
- **workflow** steps: run another workflow recursively

A **workflow chain** is a workflow whose steps are other workflows. For example, `delivery.chain.yaml` chains nine workflows from requirements through testing.

## Running a Single Workflow

### From VS Code

1. In the Explorer, navigate to `agentic/docs/workflows/`.
2. Right-click any `*.yaml` or `*.yml` workflow file.
3. Choose **Run Workflow**.
4. If the workflow declares `inputs`, VS Code prompts for each missing value.
5. Output streams to the **Workflow Runner** output channel.

### From the CLI

```bash
python3 agentic/src/workflow-runner/cli.py run agentic/docs/workflows/requirements.analysis.define-requirements.yaml
```

You can provide context values inline:

```bash
python3 agentic/src/workflow-runner/cli.py run agentic/docs/workflows/requirements.analysis.define-requirements.yaml \
  -c "business-vision=Build a customer portal" \
  -c "stakeholder-list=CEO,CTO"
```

## Running a Workflow Chain

### From VS Code

1. Right-click any workflow YAML file that is part of a chain.
2. Choose **Run Workflow Chain**.
3. The extension detects the downstream chain and runs each workflow in sequence.
4. Context from each workflow is carried forward to the next.
5. If the selected workflow is not part of a chain, it runs as a standalone workflow.

### From the CLI

```bash
python3 agentic/src/workflow-runner/cli.py run-chain agentic/docs/workflows/requirements.analysis.identify-stakeholders.yaml
```

This detects the full `delivery.chain` sequence starting from `requirements.analysis.identify-stakeholders` and runs each workflow in order.

## Validating Workflows

Check what inputs a workflow requires without running it:

```bash
python3 agentic/src/workflow-runner/cli.py validate agentic/docs/workflows/requirements.analysis.define-requirements.yaml
```

Output:

```json
{
  "status": "missing_inputs",
  "workflow": "requirements.analysis.define-requirements",
  "missing_inputs": [
    "business-vision",
    "stakeholder-list"
  ]
}
```

## How Chain Detection Works

The chain detector scans all workflow files under `agentic/docs/workflows/` and `agentic/workflows/`, builds a dependency graph, and traces forward from the selected workflow to the end of its containing chain.

- If a workflow is not referenced by any other workflow, it is treated as standalone.
- If multiple chains contain the workflow, the longest path to the end is chosen.
- Cycles are detected and broken safely.

## VS Code Extension Settings

| Setting | Default | Description |
|---|---|---|
| `workflowRunner.pythonPath` | `python3` | Path to the Python executable |
| `workflowRunner.workflowDirs` | `["agentic/docs/workflows", "agentic/workflows"]` | Directories to search for workflow files |

## Troubleshooting

- **"CLI not found"**: Ensure the workspace root contains `agentic/src/workflow-runner/cli.py`.
- **Python errors**: Verify `python3` is on PATH and `mcp`, `pydantic`, and `pyyaml` are installed.
- **No menu items**: Ensure the file path matches `workflows/*.yaml` or `workflows/*.yml`.