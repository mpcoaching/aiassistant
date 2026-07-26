PAT-011: Command / Event Separation Pattern

This is the pattern that stops the event bus becoming a mess.

Because there is a danger:

"Everything is an event"

becomes chaos.

Separate:

Commands

"Please do something."

Example:

DeployWorkflowRunner
Events

"Something happened."

Example:

WorkflowRunnerDeployed

Flow:

Command

   |

Handler

   |

State Change

   |

Event Published