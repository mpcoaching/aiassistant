# Technical Design

## Components

The Workflow Runner consists of:

- CLI
- Workflow Loader
- Workflow Executor
- Prompt Composer
- Runtime Interface
- Tool Executor
- Registry (catalog of skills/tools/workflows; name → artifact resolution)
- Compiler (promotes prompt skills to code/distilled modules)
- Choreographer (event-bus driven step progression)
- MCP Authoring Server (AI authoring: list/create skill, create workflow, compile)

See ai-orchestration-design.md for the prompt/code skill duality and
choreographed, async execution model.

# Workflow Execution
CLI

↓

Load Workflow

↓

Validate

↓

For each Step

↓

Workflow?

↓

Execute Workflow

↓

Skill?

↓

Compose Prompt

↓

Runtime

↓

Tool?

↓

Execute Tool

↓

Continue

↓

Finished

# Prompt composition
Role

+

Skill

+

Workflow Context

+

User Input

Role

+

Skill

+

Workflow Context

+

User Input

↓

Prompt

Nothing more.

# Tool Execution
↓

Prompt

Nothing more.

Execute executable.

Capture stdout.

Return output.

# Runtime

The Runtime Interface exposes:

start()

send()

add()

drop()

run()

exit()

The Aider Runtime implements this interface.

