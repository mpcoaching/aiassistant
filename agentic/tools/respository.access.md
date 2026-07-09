# Tool Definition: Repository Access

## Tool Name

repository.access


## Purpose

Provides agents with the ability to discover and retrieve information from the organisation repository.

The tool abstracts repository access so that agents do not need to know whether they are operating through:

- Aider
- local filesystem access
- Git repository access
- vector search
- future knowledge management systems


## Agent Capability

The agent can:

- locate documents
- inspect repository structure
- read relevant artefacts
- identify related information
- retrieve source material required by a skill


## Agent Interface

Request:

```yaml
action:
  values:
    - search
    - read
    - list

path:
  optional: true

query:
  optional: true

filters:
  optional: true

## Response
documents:

  - path:
      string

    content:
      string

    metadata:
      type:
        string

      source:
        string