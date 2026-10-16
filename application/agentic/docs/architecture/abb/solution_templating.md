# Solution Templating (Enterprise Building Block)

## Definition
Solution Templating is the enterprise capability to create, manage, and provide access to pre-configured patterns, blueprints, or templates for common agent-based solutions or specific agent types.

## Purpose
To accelerate the development and deployment of new agents and agentic solutions by providing reusable starting points, ensuring consistency, adherence to standards, and reducing the effort required for repetitive setup tasks.

## Key Responsibilities
*   **Template Creation**: Designing and developing standardized agent and solution templates.
*   **Template Management**: Storing, versioning, and organizing available templates.
*   **Template Provisioning**: Making templates easily discoverable and usable by developers and system administrators.
*   **Standard Enforcement**: Ensuring templates embody best practices and architectural standards.

## Relationship to Other ABBs
*   **Agent Management**: Provides foundational definitions that can be used to instantiate new agents under the Agent Management ABB.
*   **Automated Task Execution**: Templates can define common task execution patterns for agents.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Pattern templates (scaffolds), distinct from the **Concept Payload** library (learned conclusions, `kind=solved_approach`). See anchor doc §9.3.
- **Vocabulary map:** "template / blueprint" → a **Pattern template** or **manifest template** a Strategy/Pattern instantiates into a Session. It is *not* an Enterprise Concept record.
- **Relationship to core:** Links to `sbb/agent_template_repository.md`. Templates seed new agents/sessions; the Learning Loop writes the *results* back as Concept Payloads. The two libraries must not be conflated.
- **No rename:** "solution templating" retained.
