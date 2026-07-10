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