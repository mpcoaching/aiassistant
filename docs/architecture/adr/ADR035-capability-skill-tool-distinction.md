# ADR-035: Capability / Skill / Tool Distinction Investigation

Status: Proposed

Decision

Do NOT collapse Skill and Tool into Capability merely for implementation convenience. Instead, investigate whether a cleaner model distinguishes:
- Capability = ability to reliably produce an outcome
- Skill = component of that ability (knowledge, method)
- Tool = something used to enable/support that ability

Do NOT implement this distinction until the domain boundary is understood.

Context

The current model treats both Skills and Tools as Capability kinds (`CapabilityKind.SKILL`, `CapabilityKind.TOOL`). This was a pragmatic choice in Increments 1-2. The Increment 7 investigation revealed that this conflation may obscure important distinctions in the People/Capability domain.

Proposed Conceptual Model

```
Capability
   ├── knowledge
   ├── skills
   ├── methods
   ├── tools
   └── supporting resources
```

Where:
- **Capability** = ability to reliably produce an outcome
- **Skill** = a component of that ability (knowledge, method, technique)
- **Tool** = something used to enable/support that ability
- **Resource** = supporting material or infrastructure

Key Distinctions

| Concept | Example | Owned By | Lifecycle |
|---|---|---|---|
| Capability | "Architecture design" | People/Capability | Full lifecycle |
| Skill | "UML modelling" | People/Capability | Part of capability |
| Tool | " modelling tool X" | IT / Technology | Technical lifecycle |
| Resource | "Architecture patterns library" | People/Capability or Enterprise | Depends on type |

Relationship Model

```
Role (EA)
   |
   | requires
   v
Capability (architecture_design)
   |
   | composed of
   v
Skill (uml_modelling) + Skill (tradeoff_analysis)
   |
   | enabled by
   v
Tool (enterprise_architect)
   |
   | supported by
   v
Resource (pattern_library)

Person / Agent
   |
   | fulfils
   v
Role (EA)
   |
   | possesses
   v
Skill (uml_modelling)
```

Investigation Required

Before implementing, determine:
1. Does the distinction between Capability, Skill, and Tool improve the domain model?
2. Does it clarify People/Capability responsibilities?
3. Does it simplify or complicate capability matching?
4. Does it affect the Work-Capability "requires" relationship?
5. Who owns Tool lifecycle — People/Capability or IT/Technology?

Alternatives Considered

1. **Keep current model** (Skill=Capability, Tool=Capability) — pragmatic, simple, but conflates distinct concepts.
2. **Introduce separate Skill and Tool types** — cleaner domain model, but requires migration and new APIs.
3. **Use tagging/labels within Capability** — middle ground, preserves single type but adds classification.

Rationale

1. The current unified Capability type served well for early exploration.
2. As the domain matures, conflating Skill and Tool may create confusion in capability matching, acquisition, and lifecycle.
3. The distinction between "what someone can do" (capability/skill) and "what they use to do it" (tool) is meaningful in real organisations.
4. People/Capability should own capability and skill definitions; IT/Technology should own tool provisioning.

Consequences

- No immediate code changes.
- Future Increment may introduce Skill and Tool as separate domain concepts.
- Capability matching logic may need to distinguish between capability requirements and tool requirements.
- People/Capability plane may split into capability management and tool/technology management.

Related

- ADR-026: People/Capability as Peer Domain Plane
- ADR-027: Work-Capability "Requires" Relationship
- ADR-029: EIMS Learning Loop and Outcome Capture
