PAT-012: Self-Describing Component Pattern

This comes from your "application knows the config version it supports" idea.

Every component exposes:

Component Metadata

Example:

{
 "name": "workflow-runner",
 "version": "0.4.1",
 "configurationContract": "WorkflowRunnerConfiguration",
 "configurationVersion": "2",
 "capabilities": [
    "workflow.execution"
 ]
}

This enables:

validation before startup
compatibility checks
automated discovery
future self-healing