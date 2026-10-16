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

---

## Cognition Alignment

Canonical model: `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`.

- A workflow YAML is a **Session** manifest; `steps` are **pattern steps / Capability calls** (`kind=tool|skill`, anchor doc §10).
- The skill `implementation` tier (`prompt|code|distilled`) maps to Capability `execution_mode: ai_mediated|distilled|compiled` (anchor doc §10).
- The `intent` field on a workflow definition now denotes an **Intent** subtype (origin-agnostic stimulus — user request / scheduled job / bus event / alert; anchor doc §1, §2). Strategy Selection consumes the resolved Intent/Problem Frame to choose the Reasoning Strategy + Pattern pipeline.
- The Registry is the **Capability Registry**; see `sbb/tool_registry.md` alignment and the single-registry intent (ADR §7 item 11, open).