# Functional Specification

## Purpose

Execute a workflow from beginning to end.

---

## Inputs

- Workflow YAML
- Skill files
- Role files
- Tool definitions

---

## Outputs

- Commands executed
- Files modified
- Execution log
- Exit code

---

## Functional Requirements

### FR-001

Load a workflow YAML.

---

### FR-002

Validate the workflow.

---

### FR-003

Execute each step sequentially.

---

### FR-004

Support step types:

- workflow
- skill
- tool

---

### FR-005

When executing a Skill:

- Load the Role.
- Load the Skill.
- Compose the prompt.
- Send the prompt to the Runtime.

---

### FR-006

When executing a Tool:

Execute the tool.

Collect the output.

Make the output available to subsequent steps.

---

### FR-007

When executing a Workflow:

Load the referenced workflow.

Execute it recursively.

Return to the parent workflow.

---

### FR-008

Stop execution on unrecoverable error.

---

### FR-009

Write execution logs.

---

### FR-010

Return success or failure.

---

## Cognition Alignment

Canonical model: `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`.

- A **workflow** = a **Session** executing a **Pattern** pipeline (workflow instance, `SESSION-MODEL.md`).
- Workflow **steps** = pattern steps / **Capability** calls (`kind=tool|skill`, anchor doc §10).
- The existing skill tier duality `prompt | code | distilled` maps to the model's Capability `execution_mode`: **`ai_mediated | distilled | compiled`** (anchor doc §10; ADR `ai_orchestration_duality.md`).
- The Workflow Engine (SBB) owns Session execution and calls Strategy Selection + the Pattern Runtime; this spec describes one Pattern Runtime adapter (the `workflow-runner`).
- No rename of step types (`workflow | skill | tool`) — they are retained as implementation terminology.