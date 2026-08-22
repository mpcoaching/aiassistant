# ADR-025: Assistant as Organisational Role/Interface, not Implicit CEO

Status: Accepted

Decision

Assistant is a Role/interface, not an orchestrator. Assistant must NOT implicitly become CEO. AssistantChatService routes to the appropriate organisational role via OrganisationControlPlane, not through CEO capability matching.

Context

The Assistant currently risks becoming the universal entry point that delegates to CEO for everything. This creates an implicit CEO-as-central-AI-agent pattern that violates the three-plane architecture.

Decision

1. Chat -> Assistant interaction mechanism is retained.

2. Assistant determines/routes to the appropriate organisational role.

3. Assistant must NOT implicitly become CEO.

4. AssistantChatService does NOT implement universal routing logic.

5. Assistant is a Role/interface, not an orchestrator.

Intended Future Architecture

  Human
    |
    Assistant role/interface
    |
    OrganisationControlPlane
    |
    appropriate organisational role
    |
    work/delegation
    |
    Operations

Explicitly Excluded

- Assistant -> CEO -> everything pattern is out of scope for this increment.
- AssistantChatService does not implement universal routing logic.

Rationale

1. Assistant should be a thin interface, not a hidden orchestrator.
2. Routing logic belongs in the Organisation/Control plane, not in the human interface layer.
3. Keeping Assistant simple preserves the ability to swap interaction mechanisms.

Consequences

- Assistant changes are documentation-only in this increment.
- chat.py remains unchanged.
- Future increments may expand Assistant as an explicit Role in OrganisationControlPlane.

Related

- ADR-017: Three-Plane Architecture
- ADR-018: Role vs Person vs Agent
- ADR-024: CEO as Organisational Role
