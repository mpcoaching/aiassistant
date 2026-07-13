# Pattern Recognition & Assimilation

## Purpose

This specification defines how the enterprise recognises, reuses, adapts, and evolves reasoning patterns across contexts. Patterns are not fixed scripts. They are living knowledge units — analogous to a person's repertoire of "ways to approach a problem" — that exist at multiple levels of abstraction and evolve through use.

Pattern Recognition & Assimilation sits at the intersection of:
- **Research** (discovering that a pattern exists),
- **Problem Solving** (selecting and applying a pattern),
- **Explanation** (articulating why a pattern fits),
- **Documentation** (recording the pattern as an enterprise asset),
- **Implementation** (encoding the pattern as a runtime-executable bundle).

It is the connective tissue between the Enterprise Context Model, the Reasoning Pattern Catalogue, and the Session runtime.

## Why Patterns Are Not Just Workflows

A workflow describes *what to do* in a specific sequence. A pattern describes *how to think about a class of problems*. The difference is abstraction level and transferability:

- A workflow is a specific instance of a pattern under a specific context.
- A pattern is the reusable chunk that can be applied to many workflows, mutated to new contexts, or composed into larger pipelines.
- A framework (LangGraph, CrewAI, etc.) is an implementation substrate for executing patterns. The pattern itself is framework-agnostic.

If the enterprise assets are first-class (Principle 3), then patterns are the most valuable assets because they encode *proven ways of thinking*.

## Pattern Abstraction Levels

Patterns exist on a spectrum from concrete to abstract. This spectrum maps directly to how the pattern is reused.

### 1. Direct Reuse (Concrete Pattern)

A proven, documented, tested approach that can be executed without modification.

- **Characteristics**: Fixed inputs, fixed participants, fixed governance, validated outputs, versioned prompt bundle.
- **Analogy**: A standard operating procedure that a senior engineer runs without thinking.
- **Enterprise asset type**: `implementation: distilled` skill record in the registry; registered workflow in `workflow-runner`.
- **Example**: "PCI-DSS incident response SOP" — exact steps, exact approvals, exact verification criteria.

### 2. Adaptation (Pattern Mutation)

A known pattern that is modified for a new but related context. The core structure is preserved; parameters, roles, and governance are adjusted.

- **Characteristics**: Same backbone (sequence of reasoning steps), different data shapes, different participant set, relaxed or tightened gates.
- **Analogy**: An experienced architect who knows a standard reference architecture and adapts it to a new domain by swapping components.
- **Enterprise asset type**: Pattern bundle with `variant_of` reference to the parent pattern; versioned separately.
- **Example**: "SOP Execution" adapted from payment gateway incident to identity provider incident. Same investigation → fix → verify backbone, but different tools, different approvers.

### 3. Metaphorical Transfer (Abstract Pattern)

A pattern from one domain that inspires or scaffolds an approach in a *different* domain. This is the highest-value reuse because it pushes the envelope.

- **Characteristics**: Domain-agnostic reasoning shape applied to a novel problem. No direct workflow exists. The pattern provides *structure*, not steps.
- **Analogy**: A designer who applies a biological swarm pattern to a logistics routing problem.
- **Enterprise asset type**: Research note + pattern sketch in the researcher's store; may not yet be an enterprise asset until validated.
- **Example**: Applying "Debate" (from architecture review) to a pricing strategy decision. The adversarial structure is reused; the substance is new.

### The Abstraction Spectrum

```
Metaphorical Transfer (Brainstorm / Research)
         ▲
         │  pattern mutated, cross-domain
         │
Adaptation (Investigation / Planning)
         ▲
         │  pattern adjusted, same domain
         │
Direct Reuse (SOP / Verification / Reflection)
```

## Pattern Recognition Process

Pattern Recognition is the activity that detects, classifies, and proposes patterns for a given context. It operates at three levels:

### Level 1: Retrieval (Existing Pattern Match)

The system checks whether the current context map (from ENTERPRISE-CONTEXT-MODEL) matches a known direct-reuse pattern.
- Input: ContextRecord
- Output: Ranked list of candidate patterns with confidence scores
- Mechanism: Lookup table + semantic similarity against enterprise store (Qdrant)
- If confidence > threshold: pattern is proposed for direct reuse in Session creation

### Level 2: Adaptation (Near-Match Detection)

The system finds patterns that are structurally similar but require mutation.
- Input: ContextRecord + pattern catalogue
- Output: Candidate parent pattern + adaptation delta
- Mechanism: Graph traversal over pattern composability rules + LLM-assisted delta generation
- The delta becomes a new pattern bundle marked `variant_of: parent_pattern_id`

### Level 3: Synthesis (Novel Pattern Discovery)

The system has no match. It must synthesise a new pattern from scratch.
- Input: ContextRecord + enterprise assets + external research
- Output: New pattern sketch + confidence estimate
- Mechanism: Research pattern (deep-dive knowledge gathering) → Exploration/Brainstorm → Validation against acceptance criteria
- Output feeds the Learning lifecycle, which may promote the novel pattern to a reusable asset after sufficient validation

## Context-Aware Pattern Injection

A pattern is not static. The same "Debate" pattern behaves differently when:
- The problem context is `design` vs `decision`
- The environment context is `humans_and_agents` vs `ai_assisted`
- The decision context requires `consensus` vs `single_authority`

Patterns carry **context sensitivity rules**: metadata that describe how the pattern's governance, participants, and pathway toggles shift as context fields change.

```yaml
pattern_context_sensitivity:
  pattern_id: debate@1.0.0
  sensitivity_rules:
    - if decision_context.authority_model == consensus:
        governance_gates:
          - kind: consensus
            condition: authority_model_met
    - if environment_context == humans_only:
        disabled_pathways: [langgraph, crewai, maf]
        enabled_pathways: [human]
```

This makes patterns *context-aware tools* rather than fixed scripts. The same pattern bundle can produce materially different executions depending on the Session context.

## Pattern Assimilation Pipeline

New patterns enter the enterprise through assimilation:

```
Discovery → Classification → Validation → Documentation → Registration → Evolution
```

1. **Discovery**: A researcher persona, a completed session, or a manual author identifies a candidate pattern.
2. **Classification**: The pattern is assigned an abstraction level (direct / adapted / metaphorical), mapped to the pattern catalogue taxonomy, and tagged with context sensitivity rules.
3. **Validation**: The pattern is executed in a sandbox session against acceptance criteria (from the Verification pattern). If it passes, it is eligible for promotion.
4. **Documentation**: The pattern is recorded as an enterprise asset. Prompt templates, role definitions, governance gates, and pathway toggles are stored in the enterprise asset store.
5. **Registration**: The pattern is registered in `registry.py` as a `SkillRecord` with `implementation: distilled`. Its manifest entry is persisted strictly (write failure raises).
6. **Evolution**: As the pattern is executed across Sessions, telemetry feeds the Learning lifecycle. Successful executions reinforce the pattern. Failures trigger mutation or deprecation.

## Pattern Composition Rules

Patterns compose according to rules encoded in the pattern bundle itself (see REASONING-PATTERN-CATALOGUE.md). The additional rule for assimilation is:

- **Horizontal composition**: Patterns at the same abstraction level can be chained (e.g., SOP → Verification).
- **Vertical composition**: A concrete pattern can be replaced by an abstract pattern when context changes (e.g., SOP → Investigation when the SOP fails).
- **Cross-domain transfer**: Abstract patterns (Level 3) can seed new pattern families in unrelated domains. This is the primary mechanism for "pushing the envelope."

## The Researcher Persona as Pattern Canon

The researcher persona (defined in AGENTIC-EXPERIENCE.md) is the privileged participant who:
- observes pattern usage across Sessions,
- identifies transfer opportunities,
- synthesises novel patterns from cross-domain analogies,
- maintains the pattern catalogue as a living document,
- promotes or retires patterns based on empirical evidence.

Unlike other personas, the researcher has read-across access to individual research stores. This is intentional: pattern recognition requires seeing the whole forest, not just one tree.

## Traceability to Working Principles

| Principle | Pattern Recognition Contract |
|-----------|------------------------------|
| 1. Recognition before reasoning | Pattern retrieval happens before any reasoning pattern is selected; known patterns short-circuit exploration. |
| 2. Reason only when uncertainty exists | Novel contexts (Level 3 synthesis) trigger reasoning; known contexts bypass it. |
| 3. Enterprise assets are first-class | Patterns are enterprise assets encoded as versioned bundles. |
| 4. Context determines behaviour | Context sensitivity rules adapt pattern execution to context fields. |
| 5. Reasoning patterns are composable | Horizontal, vertical, and cross-domain composition rules. |
| 6. Sessions define interaction rules | Session creation selects and configures patterns. |
| 7. Frameworks are runtimes, not architecture | Patterns are framework-agnostic; frameworks execute them. |
| 8. Convert reasoning into deterministic execution | Successful Level 3 patterns are distilled into Level 1 patterns via the Learning lifecycle. |
| 9. Learning updates enterprise assets | Pattern evolution is a continuous enterprise learning process. |
| 10. Preserve architectural freedom | Pattern abstraction levels and context sensitivity rules are stable schemas. |
