# Technical Design

## Components

The Workflow Runner consists of:

- CLI
- Workflow Loader
- Workflow Executor
- Prompt Composer
- Runtime Interface
- Tool Executor

No other components exist in Version 1.

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

