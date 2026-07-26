PAT-014: Capability Registry Pattern

You already have pieces of this.

The registry should not just say:

"these services exist."

It should say:

Capability:
    workflow.execution

Provided by:
    workflow-runner

Contract:
    WorkflowExecutionContract

Version:
    1.2

Status:
    Available

This becomes the foundation for:

discovery
orchestration
agents finding tools
self-healing