# AI Compliance Rules
1. Before writing or modifying any source code files, use the `filesystem` tool to read the contents of `/docs/**/*.md`.
2. Strictly enforce all structural patterns and naming restrictions defined in that file.
3. If an adjustment breaks a convention laid out in our markdown documents, halt execution and flag the conflict to the developer.

# Architecture Context
4. Before making implementation decisions, read `.kilo/context/architecture.md` for authoritative architecture documents, key decisions, constraints, and current state.
5. For capability/assistant/workflow work, also read:
   - `agentic/docs/architecture/ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`
   - `agentic/docs/architecture/SESSION-MODEL.md`
   - `docs/architecture/adr/` (all ADRs)
6. If the context engine cannot answer a question, identify that as a capability gap rather than working around it indefinitely.
