##Workflow Schema

Only the YAML.

name:

description:

version:

role:

inputs:

outputs:

(repeating section) steps:

Step

type:

name:

uses:

with:

Supported types

workflow

skill

tool

Nothing else.

# Skill implementation tier

A skill has an `implementation` tier (metadata, never in the calling workflow):

prompt

- Markdown spec run via the LLM runtime (default, rough-out).

code

- Generated, reusable Python module exposing `run(context)`.

distilled

- LLM-generated deterministic implementation, verified before promotion.

Workflows reference skills by `uses:` name only; the tier is resolved at
execution time by the Registry. See ai-orchestration-design.md.

# Registry and manifest

The Registry is the catalog of skills, tools, and workflows. It resolves a name
to an artifact and tracks each skill's `implementation` tier and compiled module
path. Backed by the filesystem (agentic/skills, agentic/tools,
agentic/docs/workflows) plus a generated manifest for fast lookup.