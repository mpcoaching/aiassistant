# Workflow Runner

## Purpose

The Workflow Runner is a command-line utility responsible for executing engineering workflows.

A workflow consists of ordered steps that execute:

- Skills
- Tools
- Nested Workflows

The Workflow Runner composes prompts from Roles and Skills and sends them to an AI Runtime.

The first supported runtime is Aider.

The design deliberately separates orchestration from AI implementation so additional runtimes may be supported later.

This package specifies the implementation of the Workflow Runner.