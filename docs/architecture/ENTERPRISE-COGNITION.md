## Enterprise Agentic System Design – Working Theory (Draft)
Purpose
This document captures the architectural thinking developed during our discussion. It is intentionally a design exploration rather than a specification. The goal is to derive an enterprise agentic operating model from first principles rather than from the assumptions of existing frameworks.

# Core Premise

The architecture should not begin with agents, workflows, graphs, or frameworks. It should begin with the nature of the problem being solved. Frameworks are implementation details.

# Enterprise Cognition

The objective is to model how an enterprise thinks, learns, standardises, and executes. Humans, AI agents, workflows and software services are all participants that transform information. The enduring assets belong to the enterprise, not to the participants.

# Enterprise assets include:
- Information
- Taxonomy
- Policies
- Standards
- Decisions
- ADRs
- Playbooks
- Processes
- Capabilities
- Contracts
- Systems
- Metrics
- Responsibilities

Agents are transient. People are transient. Knowledge should remain with the enterprise.

Recognition Before Reasoning

The first decision should never be "reason". Instead:

Request
→ Recognise the problem
→ Have we solved this before?
→ If yes, execute the known process.
→ If similar, adapt an existing playbook.
→ If genuinely novel, enter exploration.

Reasoning is expensive and should be reserved for uncertainty.

# Capability

Capabilities describe what the business does. They are classification constructs and should not 'think'. People and AI execute work to realise capabilities.

# Contexts

The discussion identified several orthogonal contexts that together determine how work should be executed.

1. Problem Context
Examples:
- Routine operation
- Incident
- Innovation
- Investigation
- Design
- Decision
- Optimisation
- Compliance
- Learning

2. Environment Context
Defines who and what can participate:
- Humans
- AI agents
- Teams
- APIs
- MCP servers
- Workflows
- Databases
- External systems

3. Information Context
Defines the information required:
- Policies
- Standards
- ADRs
- Previous decisions
- Customer data
- Enterprise knowledge
- Regulations
- Metrics

4. Activity Purpose
Examples:
- Explore
- Decide
- Approve
- Validate
- Review
- Execute
- Learn
- Optimise
- Monitor
- Investigate

This is distinct from the business outcome. The activity purpose determines the style of interaction; the business outcome is the result being sought.

# Decision Context

The governance surrounding a decision:
- Required confidence
- Consensus vs single authority
- Time constraints
- Mandatory policy checks
- Human approval
- Cost vs quality
- Reversible vs irreversible decisions

# Reasoning Patterns

Rather than one reasoning engine, the platform should support pluggable reasoning patterns.

Candidate pattern catalogue:
- SOP Execution
- Investigation
- Exploration
- Brainstorm
- Debate
- Consensus
- Critique
- Reflection
- Research
- Planning
- Verification
- Human Approval
- Escalation
- Learning

Patterns should be composable. Example:
Recognition → Research → Brainstorm → Debate → Consensus → Critique → ADR → Learning

# Sessions

A session is a first-class execution construct.

A session contains:
- Purpose
- Agenda
- Participants
- Policies
- Reasoning pattern(s)
- Memory scope
- Success criteria
- Outputs
- Escalation rules
- Timebox

Agents adapt their behaviour based on the session rather than carrying fixed behaviour.

Examples:
Architecture Review Board:
- Purpose: Validate architecture
- Pattern: Debate + Consensus
- Output: ADR / approval

Brainstorm Workshop:
- Purpose: Generate options
- Pattern: Exploration
- Output: Candidate ideas

Incident Response:
- Purpose: Restore service
- Pattern: SOP + Investigation
- Output: Resolution

Learning Lifecycle

Novel Task
→ Heavy reasoning
→ Successful approach
→ Playbook
→ SOP
→ Deterministic workflow
→ Habit

As maturity increases, reasoning decreases.

Execution Runtime

The runtime should be replaceable.

Architecture:
Enterprise Assets
→ Recognition
→ Context Analysis
→ Pattern Selection
→ Runtime
→ Models / Tools / APIs

LangGraph appears well suited because it provides execution primitives without imposing a reasoning style. CrewAI can be viewed as a collaborative reasoning pattern rather than the architectural foundation. Microsoft's agent framework provides enterprise integration capabilities but should remain an interchangeable runtime rather than the architectural model.

# Open Questions

- How should contexts be represented?
- How are patterns versioned?
- How are successful sessions distilled into playbooks?
- How does recognition classify new work?
- What metrics define maturity?
- How are enterprise assets governed?

# Working Principles

1. Recognition before reasoning.
2. Reason only when uncertainty exists.
3. Enterprise assets are first-class.
4. Context determines behaviour.
5. Reasoning patterns are composable.
6. Sessions define interaction rules.
7. Frameworks are runtimes, not architecture.
8. Organisations should continuously convert reasoning into deterministic execution.
9. Learning updates enterprise assets, not individual agents.
10. Preserve architectural freedom through stable abstractions rather than framework-specific concepts.

Enterprise Agentic System Design – Working Theory (Draft)
Purpose
This document captures the architectural thinking developed during our discussion. It is intentionally a design exploration rather than a specification. The goal is to derive an enterprise agentic operating model from first principles rather than from the assumptions of existing frameworks.

Core Premise

The architecture should not begin with agents, workflows, graphs, or frameworks. It should begin with the nature of the problem being solved. Frameworks are implementation details.

Enterprise Cognition

The objective is to model how an enterprise thinks, learns, standardises, and executes. Humans, AI agents, workflows and software services are all participants that transform information. The enduring assets belong to the enterprise, not to the participants.

Enterprise assets include:
- Information
- Taxonomy
- Policies
- Standards
- Decisions
- ADRs
- Playbooks
- Processes
- Capabilities
- Contracts
- Systems
- Metrics
- Responsibilities

Agents are transient. People are transient. Knowledge should remain with the enterprise.

Recognition Before Reasoning

The first decision should never be "reason". Instead:

Request
→ Recognise the problem
→ Have we solved this before?
→ If yes, execute the known process.
→ If similar, adapt an existing playbook.
→ If genuinely novel, enter exploration.

Reasoning is expensive and should be reserved for uncertainty.

Capability

Capabilities describe what the business does. They are classification constructs and should not 'think'. People and AI execute work to realise capabilities.

Contexts

The discussion identified several orthogonal contexts that together determine how work should be executed.

1. Problem Context
Examples:
- Routine operation
- Incident
- Innovation
- Investigation
- Design
- Decision
- Optimisation
- Compliance
- Learning

2. Environment Context
Defines who and what can participate:
- Humans
- AI agents
- Teams
- APIs
- MCP servers
- Workflows
- Databases
- External systems

3. Information Context
Defines the information required:
- Policies
- Standards
- ADRs
- Previous decisions
- Customer data
- Enterprise knowledge
- Regulations
- Metrics

4. Activity Purpose
Examples:
- Explore
- Decide
- Approve
- Validate
- Review
- Execute
- Learn
- Optimise
- Monitor
- Investigate

This is distinct from the business outcome. The activity purpose determines the style of interaction; the business outcome is the result being sought.

Decision Context

The governance surrounding a decision:
- Required confidence
- Consensus vs single authority
- Time constraints
- Mandatory policy checks
- Human approval
- Cost vs quality
- Reversible vs irreversible decisions

Reasoning Patterns

Rather than one reasoning engine, the platform should support pluggable reasoning patterns.

Candidate pattern catalogue:
- SOP Execution
- Investigation
- Exploration
- Brainstorm
- Debate
- Consensus
- Critique
- Reflection
- Research
- Planning
- Verification
- Human Approval
- Escalation
- Learning

Patterns should be composable. Example:
Recognition → Research → Brainstorm → Debate → Consensus → Critique → ADR → Learning

Sessions

A session is a first-class execution construct.

A session contains:
- Purpose
- Agenda
- Participants
- Policies
- Reasoning pattern(s)
- Memory scope
- Success criteria
- Outputs
- Escalation rules
- Timebox

Agents adapt their behaviour based on the session rather than carrying fixed behaviour.

Examples:
Architecture Review Board:
- Purpose: Validate architecture
- Pattern: Debate + Consensus
- Output: ADR / approval

Brainstorm Workshop:
- Purpose: Generate options
- Pattern: Exploration
- Output: Candidate ideas

Incident Response:
- Purpose: Restore service
- Pattern: SOP + Investigation
- Output: Resolution

Learning Lifecycle

Novel Task
→ Heavy reasoning
→ Successful approach
→ Playbook
→ SOP
→ Deterministic workflow
→ Habit

As maturity increases, reasoning decreases.

Execution Runtime

The runtime should be replaceable.

Architecture:
Enterprise Assets
→ Recognition
→ Context Analysis
→ Pattern Selection
→ Runtime
→ Models / Tools / APIs

LangGraph appears well suited because it provides execution primitives without imposing a reasoning style. CrewAI can be viewed as a collaborative reasoning pattern rather than the architectural foundation. Microsoft's agent framework provides enterprise integration capabilities but should remain an interchangeable runtime rather than the architectural model.

Open Questions

- How should contexts be represented?
- How are patterns versioned?
- How are successful sessions distilled into playbooks?
- How does recognition classify new work?
- What metrics define maturity?
- How are enterprise assets governed?

Working Principles

1. Recognition before reasoning.
2. Reason only when uncertainty exists.
3. Enterprise assets are first-class.
4. Context determines behaviour.
5. Reasoning patterns are composable.
6. Sessions define interaction rules.
7. Frameworks are runtimes, not architecture.
8. Organisations should continuously convert reasoning into deterministic execution.
9. Learning updates enterprise assets, not individual agents.
10. Preserve architectural freedom through stable abstractions rather than framework-specific concepts.

# Now something fascinating happens

These contexts naturally determine the reasoning pattern.

For example

Problem	Outcome	Pattern
Innovation	Generate	Brainstorm
Incident	Restore	SOP
Architecture	Decide	Debate
Compliance	Verify	Checklist
Learning	Improve	Reflection
Unknown	Understand	Investigation

So instead of caring about a framework, we allow agents to have meetings if the situation requires is, so we switch on how they resolve the situation.  


# I think there are several documents hiding inside this

If we continue this work, I'd probably expect this to become something like:

Theory of Enterprise Cognition (the philosophy and first principles)
Enterprise Agentic Reference Architecture (logical architecture)
Enterprise Context Model (the contexts we've identified today)
Reasoning Pattern Catalogue (your equivalent of Enterprise Integration Patterns)
Session Model Specification (how work is bounded and governed)
Capability Execution Model (how capabilities become work)
Learning & Knowledge Lifecycle (how reasoning becomes habits/SOPs)
Runtime Mapping (how LangGraph, MAF, CrewAI, n8n etc. implement the model)