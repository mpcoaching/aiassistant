# Agent Template Repository (Solution Building Block)

## Definition
The Agent Template Repository is a service or component that stores, manages, and provides access to a collection of pre-defined agent templates. These templates serve as blueprints for creating new agents with common functionalities or configurations.

## Purpose
To streamline the development and deployment of agents by offering reusable, standardized starting points, thereby reducing development time, ensuring consistency, and promoting best practices.

## Key Responsibilities
*   **Template Storage**: Persisting agent template definitions (e.g., parameterized agent manifests).
*   **Template Versioning**: Managing different versions of templates.
*   **Template Discovery**: Providing APIs to list and retrieve available templates.
*   **Template Validation**: Ensuring templates adhere to structural and content standards.

## Interactions
*   **Exposes**: RESTful API for listing available templates and retrieving template details.
*   **Consumes**: (Potentially) updates from a content management system or internal source code repository for template definitions.
*   **Publishes**: (Potentially) events to the Agent Bus when new templates are added or updated.

## Data Ownership
*   **Source of Truth for**: Pre-defined Agent Templates.

---

## Cognition Alignment

*Maps existing terms to the canonical model in `ENTERPRISE-COGNITION-REFERENCE-ARCHITECTURE.md`. Do not rewrite responsibility bodies.*

- **Model role:** Reusable Pattern / manifest templates. The repository stores structural blueprints for agents/sessions — distinct from the **Concept Payload** library (which holds *learned, proven* approaches, `kind=solved_approach`).
- **Vocabulary map:** "agent template / parameterized manifest" → a **Pattern template** or **manifest template** (a scaffold a Strategy/Pattern instantiates into a Session). It is *not* an Enterprise Concept record.
- **Relationship to core:** Templates are the reusable starting points that Solution Templating and the pattern catalogue draw on; Concept Payloads are the conclusions the Learning Loop writes back. The two libraries must not be conflated (anchor doc §9.3).
- **No rename:** "template" terminology retained.
