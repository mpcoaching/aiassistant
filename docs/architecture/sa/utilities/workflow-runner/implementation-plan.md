## Implementation Plan

Exactly what Aider will build.

# Phase 1

CLI

↓

Load YAML

↓

Validate

↓

Execute Skills

↓

Exit

# Phase 2

Nested Workflows

↓

Tool Execution

↓

Variables

# Phase 3

Context Discovery

↓

Automatic /add

↓

Prompt Templates

# Phase 4

Additional Runtimes

---

## Cognition Alignment

Canonical model: `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. This plan builds one **Pattern Runtime** adapter (the `workflow-runner`); "Additional Runtimes" (Phase 4) corresponds to adding further adapters such as LangGraph (anchor doc §12, `RUNTIME-MAPPING.md`). All runtimes execute **Sessions** (workflows) composed of **pattern steps / Capability calls** selected by Strategy Selection (§6).