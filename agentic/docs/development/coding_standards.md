# Coding Standards

## Purpose

These standards exist to ensure that all code produced by humans and AI assistants is consistent, maintainable, testable and aligned with the solution architecture.

The primary objective is long-term maintainability rather than the fastest implementation.

---

# General Principles

- Prefer clarity over cleverness.
- Keep solutions as simple as possible.
- Avoid premature optimisation.
- Favour readability over reducing line count.
- Minimise technical debt.
- Follow existing patterns before introducing new ones.

---

# Architecture

Always follow the solution architecture.

Do not introduce new architectural patterns unless explicitly approved.

When architectural decisions are required:

- Check the ADRs first.
- If no ADR exists, stop and ask.
- If instructed to proceed, create a new ADR.

Never bypass capability boundaries.

---

# Code Organisation

Each module should have a single responsibility.

Keep files focused.

Avoid "utility" classes unless the behaviour genuinely belongs together.

Avoid circular dependencies.

Dependencies should point inward towards abstractions.

---

# Functions

Functions should:

- perform one logical task
- have descriptive names
- avoid excessive nesting
- return early where appropriate

Avoid excessively large functions.

If a function becomes difficult to understand, extract smaller functions.

---

# Classes

Classes should represent meaningful concepts or entities and be used at all times.

Avoid "God Objects".

Prefer composition over inheritance.

Inject dependencies rather than constructing them internally.

---

# Naming

Names should explain intent.

Names should be consistently defined, using all lower case with underscores, no capitalisation.

Avoid abbreviations unless they are universally understood.

Examples:

Good:

create_session()

calculate_next_tasks()

WorkflowRegistry

Poor:

proc()

util()

mgr()

---

# Type Safety

Use type hints throughout.

Avoid Any unless unavoidable.

Public APIs must be typed.

---

# Error Handling

Errors should be handled intentionally.

Do not silently ignore exceptions.

Provide meaningful error messages.

Raise domain-specific exceptions where appropriate.

---

# Logging

Log useful business events.

Avoid excessive debug logging.

Never log secrets.

Logging should used shared implementations, via a logging API.

---

# Comments

Code should explain itself.

Comments should explain **why**, not **what**.

Avoid redundant comments.

Good:

// Retry because provider APIs frequently return transient failures.

Poor:

// Increment i.

---

# Dependencies

Do not introduce new dependencies unless justified.

Reuse existing libraries where practical.

---

# Configuration

Avoid hard-coded values.

Configuration belongs in configuration files or environment variables.

---

# Documentation

Public interfaces should be documented.

Complex algorithms should include implementation notes.

Architecture changes require ADR updates.

---

# AI Development

AI assistants must:

- follow the architecture documents
- reuse existing abstractions
- avoid duplication
- implement incrementally
- explain significant design decisions
- ask for clarification when requirements are ambiguous

AI assistants must not invent architecture.