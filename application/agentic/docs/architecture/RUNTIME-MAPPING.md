# Runtime Mapping

## Purpose

This specification defines how Enterprise Cognition reasoning patterns are executed at runtime. It disambiguates two layers often confused: patterns are *what to do*, frameworks are *how to run it*. All framework approaches in this document—CrewAI's role-based crews, AutoGen's conversation loops, Microsoft Agent Framework's CodeAct sandboxes, Google ADK's orchestration hierarchies, OpenAI Agents SDK's handoffs—are treated as candidate pattern implementations to be studied, adapted, and ultimately encoded as declarative `PatternStep` bundles executed on a single LangGraph substrate. This document includes a deep-dive comparative analysis of every major 2025-2026 framework and an honest account of which ideas are absorbed, which are discarded, and why.

## Design Constraints

- Context, Session, and Pattern schemas contain zero framework concepts (Principle 10). The stable abstraction boundary is one-direction.
- Frameworks are substrates; the pathway interface never adapts to a framework.
- Runtime changes must not alter Context or Session schemas. A new pathway is registered as an implementation of the interface, not a new schema field.
- All runtime state remains in `WorkflowState` via `db.py` (`agentic/src/workflow-runner/db.py`). No framework has direct schema access.
- LangGraph is the execution substrate. Pattern bundles declare their execution requirements; the substrate maps those requirements to graph configurations at Session creation.
- Framework competitive analysis feeds the pattern catalogue. Patterns are *not* copied wholesale from frameworks; their underlying abstractions are evaluated and selectively absorbed.

## Stable Abstraction Boundary

```yaml
# Boundary contract (Framework -> Ecosystem)

PathwayRuntime:
  id: string                  # e.g. workflow-runner | langgraph
  supports_stateful: bool
  supports_concurrent_participants: bool
  supports_streaming: bool
  supports_interruption: bool

# Call contract (Ecosystem -> Framework)
PathwayCallRequest:
  session_id: string
  pattern_step: PatternStep
  context: ContextRecord
  participants: list[ParticipantRecord]
  prompt: string
  max_turns: int
  timeout_seconds: int

# Response contract (Framework -> Ecosystem)
PathwayResponse:
  status: enum [completed | approved | rejected | escalated | failed]
  outputs: map
  artifacts: list[string]     # references to enterprise asset store
  telemetry: map              # duration, token_cost, provider_id
```

The `PatternStep` is the unit of runtime dispatch. Each `PatternStep` carries:
- `pattern_id` linking to the Reasoning Pattern Catalogue
- `enabled_pathways` — a priority-ordered list of runtime substrates that can execute this step
- `pathway_preference` — the caller's intended substrate; the runtime honours it if available, otherwise falls back

## LangGraph as Execution Substrate

LangGraph is the single runtime substrate for all pattern execution in this system. The choice is architectural, not accidental.

### Why LangGraph

LangGraph (`langgraph` Python package, part of the LangChain ecosystem) is a graph-based state machine runtime for LLM workflows. It provides:

- **Explicit state graph**: execution is a graph of nodes and edges; state flows between nodes; cycles are first-class.
- **Persistent checkpoints**: every graph transition can be persisted and resumed, enabling durable long-running sessions.
- **Conditional branching**: edges can be conditional on state, enabling adaptive pattern execution.
- **Human-in-the-loop**: graph pauses on interruptible nodes and resumes when external state is written.
- **Observability**: every node execution is an observable event with inputs, outputs, and duration.
- **Multi-agent coordination**: subgraphs and fan-out/fan-in patterns are native constructs.

LangGraph implements the substrate pattern interface defined above. Pattern bundles remain framework-agnostic; the execution substrate interprets `PatternStep` metadata and configures the graph at runtime.

```python
# Conceptual translation: PatternStep -> LangGraph state graph

def build_pattern_graph(pattern_step: PatternStep, context: ContextRecord) -> CompiledGraph:
    state_schema = pattern_step.state_schema or GlobalState
    nodes = {}

    for step_pattern in pattern_step.ordered_steps:
        nodes[step_pattern.step_id] = {
            "agent": step_pattern.role,
            "tools": step_pattern.tools,
            "condition": step_pattern.gate_condition,
        }

    edges = build_conditional_edges(pattern_step.composability_rules)

    return StateGraph(state_schema).add_nodes(nodes).add_edges(edges).compile(
        checkpointer=PostgresCheckpoint(db.connection),
        interrupt_before=[g.step_id for g in pattern_step.governance_gates],
    )
```

### What LangGraph Does Not Provide

LangGraph is a substrate, not a pattern library. It does not ship with:
- pre-built Debate, Brainstorm, or Investigation nodes,
- role definitions or prompt templates,
- governance gate logic,
- Learning lifecycle hooks.

Those belong to the pattern catalogue. LangGraph provides the graph execution engine; the pattern catalogue provides the graph contents.

### Degraded Routing

Only `workflow-runner` and `langgraph` are true substrate pathways today. All other framework pathways (CrewAI, MAF, human) are implemented as `PatternStep` features configurable within the LangGraph substrate:

- **workflow-runner**: Used when a pattern step is fully determined, linear, and requires no branching. Executed as a LangGraph node wrapping the existing deterministic executor loop.
- **langgraph**: Default substrate for all branching, stateful, or multi-agent patterns. Full graph execution.
- **human**: Implemented as a LangGraph interrupt node. The graph pauses; an external handler writes approval/rejection to `WorkflowState`; the graph resumes.
- **CrewAI, MAF, OpenAI Agents SDK, Google ADK**: Not registered as substrates. Their patterns are studied in the framework analysis and absorbed as `PatternStep` configurations where their abstractions offer clear value over plain LangGraph nodes.

## Competitive Framework Analysis

This section is a living document. Every major agent framework observed in production or significant research use during 2025-2026 is evaluated for patterns worth absorbing into the Enterprise Cognition system. Frameworks are assessed by: (1) the underlying abstraction they introduce, (2) the concrete production value that abstraction enables, (3) its limitations, and (4) whether and how the Enterprise Cognition system can benefit from studying it.

Framework analysis is a specialist function; the researcher persona maintains this section as new frameworks emerge and existing ones evolve.

### Evaluation Criteria

Before any pattern is promoted from a framework analysis into the Enterprise Cognition catalogue, it must pass:

| Criterion | What it guards against |
|---|---|
| **Abstraction durability** | Pattern must survive a model swap or a substrate change |
| **Declarative encodeability** | Pattern must be expressible in YAML without runtime code |
| **Governance compatibility** | Pattern must support readable governance gates and interruption points |
| **Telemetry clarity** | Pattern execution must produce structured trace and cost data |
| **Learning hookability** | Pattern outcomes must feed the Learning & Knowledge Lifecycle |

Not every interesting framework idea clears these bars. Some are discarded.

---

## LangGraph (LangChain)

**Abstraction**: Explicit state machine as a directed graph. Nodes are agents or tools; edges are control flow; state is a typed schema passed between nodes.

**Strength in production**: The graph model makes execution deterministic and traceable in ways that no other framework matches. You can replay any failed session node-by-node. Conditional edges enable adaptive branching without implicit control flow. Checkpointing enables durable long-running workflows that survive process restarts. The multi-agent supervisor pattern (one node orchestrating subgraphs) is the most studied production architecture in 2025-2026.

**Weakness**: Steep learning curve. The graph metaphor is powerful but requires the developer to think in terms of state transitions, not natural task descriptions. Tool management is manual. Small, linear workflows carry unnecessary overhead compared to a simple chain of function calls.

**What to absorb**: Explicit state schema, conditional branching, interruptible nodes for governance, checkpoint-based resume. These map directly to `PatternStep` configuration and governance gates in the Enterprise Cognition system.

**What to discard**: The entire LangChain prompt-template ecosystem (LCEL chains, Runnable lambdas, etc.). LangGraph is a substrate; LangChain's prompt chains are an implementation detail. The substrate uses direct LLM calls via the participant record.

**Current status**: Designated as the sole execution substrate.

---

## CrewAI

**Abstraction**: Role-specialized agents (defined via YAML role dictionaries or Python class hierarchies) cooperating in a "crew." Roles have backstories, goals, and tools. The crew has a `process` (sequential, hierarchical, or consensus).

**Strength in production**: Rapid prototyping of role-based multi-agent workflows. A new crew can be defined in under 100 lines of YAML. The role definition format is expressive enough to drive strong agent specialization. Built-in delegation via hierarchical process creates emergent role-play behaviours without graph design. Training data shows CrewAI excels at exploratory tasks where breadth of role perspective matters more than deterministic output.

**Weakness**: Role definitions are prompts dressed as configuration. They are not typed, cannot be statically validated, and drift silently as models change. Sequential process is the enforced default; cyclic workflows require custom graph hacks. Observability is tracing-dependent and not structurally enforced. Memory is append-only and grows unbounded unless managed externally. CrewAI's role abstraction does not map cleanly to the `ParticipantRecord` model, which separates identity from behaviour.

**What to absorb**: The role-specialization pattern. The Enterprise Cognition `ParticipantRecord` already encodes role identity; CrewAI's contribution is demonstrating that rich role descriptions (not just titles) materially improve agent output quality. The pattern catalogue should carry role enrichment templates.

**What to discard**: The crew-as-container concept. Crews are not first-class entities in Enterprise Cognition; Sessions are. CrewAI's hierarchical process is replaced by Session-controlled pattern step ordering and graph-based routing.

**Current status**: Analysed. Role-enrichment patterns absorbed. Crew container and process models discarded.

---

## Microsoft Agent Framework (MAF, formerly AutoGen + Semantic Kernel, GA April 2026)

**Abstraction**: Three primitives — `Agent` (LLM + instructions + tools), `ChatHistory` (durable message streaming), and `Workflow` (directed join of agents). CodeAct with Hyperlight micro-VM sandbox is a first-class execution mode. Protocol support includes MCP, A2A, and ACP.

**Strength in production**: CodeAct is the most significant agent architecture contribution of 2025-2026. By collapsing multi-turn tool chains into a single code block executed in a sandbox, MAF achieves:
- ~50% end-to-end latency reduction on multi-step data tasks
- >60% token reduction
- Deterministic tool composition (loops, branching, variable binding) inside one model turn

The enterprise integration story is unmatched: Azure identity, Durable Functions, and .NET-native observability make MAF the natural choice for Azure-stack enterprises. The A2A v1 support (April 2026) enables cross-framework agent communication.

**Weakness**: The dual heritage (AutoGen's conversation model + Semantic Kernel's plugin model) creates conceptual friction. CodeAct requires a sandbox runtime; enforcing isolation for every tool call adds operational overhead. .NET is the primary language; Python support is present but not the primary development surface for enterprise features.

**What to absorb**: CodeAct as a `PatternStep` execution mode for high-volume tool composition. The sandbox isolation model maps to governance gate enforcement: a CodeAct step runs in a sandboxed graph node; its output is gated before influencing subsequent steps. The durable execution story (Durable Functions) reinforces the LangGraph checkpoint argument.

**What to discard**: The conversation-as-default-control-flow model. Enterprise Cognition uses explicit `PatternStep` pipelines with governance gates between steps, not open-ended conversation loops. The chat history is managed via `WorkflowState`, not as a first-class runtime concept.

**Current status**: Analysed. CodeAct pattern abstracted as a high-volume tool execution mode. Sandbox model feeds governance gate design.

---

## AutoGen (pre-MAF; still in use as research substrate)

**Abstraction**: Two-agent conversation loop. Agents are configurable LLM personas. The conversation is the orchestration mechanism. Supports nested conversations, human-in-loop via `human_input`, and code generation/execution via `UserProxyAgent` and `CodeExecutor`.

**Strength in research**: Emergent multi-agent conversation is a genuine research tool. AutoGen's conversation replay and multi-party dialogue models are useful for studying how agent roles negotiate solution spaces. The conversation format is the most human-readable agent trace.

**Weakness**: Open-ended conversation is hard to govern. Every step requires a model turn; there is no code-as-action compression step. Conversation history grows linearly with task complexity. Controlling termination is fragile; the agent can continue beyond the task boundary without a structured exit gate.

**What to absorb**: Multi-party dialogue as a Debate pattern variant. AutoGen's conversation replay maps to Session observability: an entire agent conversation can be replayed from `WorkflowState` checkpoints.

**What to discard**: Conversation as orchestration primitive. Spontaneous multi-turn dialogue is not a governance-compatible control flow. Enterprise Cognition requires explicit step ordering and gates between steps.

**Current status**: Absorbed into Debate pattern. Framework itself deprecated in favour of MAF.

---

## Google Agent Development Kit (ADK 1.0 GA April 2026)

**Abstraction**: Four-language SDK (Python, TS, Java, Go) defining `Agent` + `Runner` + event-driven `SessionService` + `ArtifactService`. Multi-agent composition via `SequentialAgent`, `ParallelAgent`, `LoopAgent`, `HierarchicalAgent`. Native A2A support. Evaluation framework with evalsets and LLM-as-judge scoring built in.

**Strength in production**: Cross-language parity (Python, TS, Java, Go) is unique. The evaluation framework is the most mature of any framework studied: you can define an evalset, run an agent, and get scored outcomes in a single command. The multi-agent composition types (sequential, parallel, loop, hierarchical) are well-designed primitives that map directly to `PatternStep.composability_rules`. The service-registry pattern (`services.yaml`) enables runtime swap of session, artifact, and memory backends without code changes.

**Weakness**: Documentation quality is uneven across languages. The graph-based workflow runtime shipped in ADK 2.0 (May 2026) is promising but the API surface is still evolving. Vertex AI Agent Engine is the primary deployment target; deployment to non-Google runtimes requires manual containerisation. Gemini optimization is real but introduces provider bias.

**What to absorb**: The four composition types (`Sequential`, `Parallel`, `Loop`, `Hierarchical`) are exactly the primitive abstractions needed for `PatternStep.composability_rules`. The evaluation framework (evalsets + LLM-as-judge + scoring) should be adopted verbatim for pattern validation and the Learning lifecycle. The service-registry pattern informs how `PathwayRuntime` adapters are registered and swapped.

**What to discard**: The agent-as-class hierarchy. Enterprise Cognition patterns are data bundles (`PatternStep`), not class instances. The service-registry concept is absorbed; the service implementation details are not.

**Current status**: Composition primitives absorbed; evaluation framework under design review for integration into pattern validation pipeline.

---

## OpenAI Agents SDK (production successor to Swarm, GA 2025)

**Abstraction**: Five primitives — `Agent`, `Runner`, `function_tool`, `handoff`, `Guardrails`. Agents-as-tools enable composition. Sessions via `session=` parameter built in.

**Strength in production**: Lowest-friction lightweight multi-agent path. Handoffs are a clean, minimal abstraction for peer-to-peer delegation that avoids the overhead of a supervisor. Provider-agnostic tooling via LiteLLM. Built-in tracing and safety guardrails ship with `pip install openai-agents`. Replaced the Swarm experimental framework in production environments in under six months.

**Weakness**: Handoffs are the *only* multi-agent pattern. Parallel execution requires custom orchestration. Human-in-the-loop is limited to tripwire-style guardrails; true multi-step approval requires custom code. TypeScript support is incomplete. The SDK abstracts away token tracking per step; post-hoc trace inspection is the only cost visibility.

**What to absorb**: The handoff primitive as a lightweight `PatternStep` variant. OpenAI's insight that peer-to-peer delegation with conversation state preservation is a distinct coordination pattern (not just a pipeline under another name) should be encoded as a `HandoffPatternStep` subtype. The guardrail primitives map directly to governance gate pre-conditions.

**What to discard**: The abstraction that agents are the primary building block. In Enterprise Cognition, patterns and context are primary; agents (as `ParticipantRecord`) are configuration. The Agent-as-object pattern should not leak into platform code.

**Current status**: Handoff pattern variant under design. Guardrail pattern mapped to governance gates.

---

## Smolagents (HuggingFace)

**Abstraction**: Agents that write Python code instead of emitting JSON tool calls. `CodeAct` is the default; tools are Python functions. Multiple sandbox runtimes (E2B, Modal, Pyodide). Built-in web-search agent primitive.

**Strength in research**: CodeAct directly validated at scale across 17 LLMs. ICML 2024 paper shows +20% success rate, -30% steps vs JSON tool calling. HuggingFace hub integration makes it trivially accessible. The minimal-abstraction philosophy (no state management, no prompt templates, no orchestration primitives beyond the code loop) is the cleanest possible code-as-action substrate.

**Weakness**: No built-in multi-agent coordination. Sandbox security must be managed independently for each runtime. Observability is minimal. Production hardening requires significant infrastructure investment around the sandbox.

**What to absorb**: CodeAct as a tool execution mode within a `PatternStep`. The principle that code is a universal action space should inform how high-volume tool composition steps are designed within LangGraph nodes. The statistical validation of CodeAct's efficiency gains should be cited in pattern selection guidance.

**What to discard**: The minimalism as an architecture. Smolagents is a research scaffold, not a production runtime. The Enterprise Cognition substrate provides what Smolagents lacks (state management, governance, observability) while retaining the CodeAct execution model as an option within pattern steps.

**Current status**: CodeAct execution mode planned for high-volume tool composition pattern steps.

---

## DSPy

**Abstraction**: Declarative programming over LLM prompts. `Module` classes declare signatures (input fields, output fields). `ChainOfThought`, `ReAct`, `ProgramOfThought` are built-in modules. The `BootstrapFinetune` optimizer compiles a module into a fine-tuned model.

**Strength in research**: Separates prompt design from model selection. Enables automatic optimization of prompt pipelines against metric functions. The bootstrap-from-few-examples approach is the most studied prompt engineering methodology in 2025-2026.

**Weakness**: Optimization is expensive (many model calls during bootstrap). Compiled modules are opaque; debugging requires understanding the optimizer's decisions. Restricted to single-model fine-tuning workflows; not a multi-agent orchestration framework.

**What to absorb**: The signature-as-contract pattern for defining `PatternStep` input/output schemas. DSPy's `Module` abstraction maps to `PatternStep` bundles. The optimizer concept informs Learning pipeline design: pattern bundles should be optimizable against a metric function.

**What to discard**: Fine-tuning as a primary optimization mechanism. The Learning lifecycle improves patterns through telemetry feedback and conversation data; it does not fine-tune the underlying LLM.

**Current status**: Signature design pattern under consideration for `PatternStep` schema definitions.

---

## Protocol Layer: MCP and A2A

**MCP (Model Context Protocol, Anthropic)**: Open wire format and runtime for agent-to-tool communication. Defines tool/resource discovery, structured tool calling, and session transport. As of mid-2026, 200+ MCP server implementations exist across the ecosystem.

**A2A (Agent-to-Agent, Google/Linux Foundation)**: Open protocol for agent-to-agent discovery, capability publication, task lifecycle, and multi-modal message exchange. 150+ organizations supporting. A2A agents publish `AgentCard` documents describing skills and endpoints.

**Integration**: The Enterprise Cognition system adopts MCP as the standard instrumentaton layer for tool calls across all pattern steps. Tools exposed to agents are MCP-compatible regardless of runtime substrate. A2A is under evaluation for cross-System agent communication in multi-tenant deployments. Neither protocol leaks into Context/Session/Pattern schemas; they are runtime transport concerns handled by the pathway adapter layer.

## Framework Deep-Dive Comparison

### Orchestration Philosophy

| Framework | Core Metaphor | Control Flow | Governance Model |
|---|---|---|---|
| LangGraph | State machine graph | Explicit graph edges | Interruptible nodes |
| CrewAI | Theatre / role-play | Role delegation | Informal (role instructions) |
| MAF (AutoGen+) | Conversation + sandbox | Conversation loop + CodeAct | Approval middleware |
| Google ADK | Agent orchestra | Hierarchical / parallel / loop | Callback-based |
| OpenAI Agents SDK | Handoff chain | Peer handoffs | Guardrails |
| Smolagents | Code interpreter | Code execution loop | External to framework |

### State Management

| Feature | LangGraph | CrewAI | MAF | ADK | OpenAI SDK | Smolagents |
|---|---|---|---|---|---|---|
| Explicit state schema | Yes | No | Partial | Yes | No | No |
| Persistent checkpoint | Yes | Via external store | Yes | Yes | Via session | No |
| Concurrent state writes | No (single-threaded) | No | No | No | No | No |
| State queryability | Full | None | Partial | Partial | None | None |

### Multi-Agent Topology

| Topology | LangGraph | CrewAI | MAF | ADK | OpenAI SDK |
|---|---|---|---|---|---|
| Supervisor / orchestrator | Native subgraph | Hierarchical process | Manager agent | HierarchicalAgent | Orchestrator + subagents pattern |
| Peer handoff | Conditional edge | Peer delegation in process | Handoff tool | Not native | First-class `handoff()` |
| Parallel fan-out | Native `Send` | Partial (parallel process) | Fan-out via topics | ParallelAgent | Custom required |
| Conversation loop | Via cycle | Default process | Default mode | LoopAgent | Not native |
| Nested hierarchies | Recursive subgraphs | Crew of crews | Nested agent groups | HierarchicalAgent | Subagents nested |

### Tool Calling

| Feature | LangGraph | CrewAI | MAF | ADK | OpenAI SDK | Smolagents |
|---|---|---|---|---|---|---|
| Tool format | OpenAI function schema | JSON schema | OpenAI function schema | OpenAPI / function / code | OpenAI function schema | Python function |
| Code as action | No | No | Yes (CodeAct) | Partial (ContainerCodeExecutor) | No | Yes (default) |
| Sandbox isolation | No (caller-managed) | No | Yes (Hyperlight) | Yes (Container) | No | No |
| Parallel tool calls | Per-node batch | No | Per-turn sequential | No | Per-turn sequential | Per-script |

Key insight: Smolagents and MAF arrive at the same architectural conclusion (code as action) from different directions. Smolagents achieves it through minimal abstraction; MAF achieves it through enterprise sandbox infrastructure. Both validate that CodeAct is pattern-worthy for high-volume tool composition steps.

### Observability

| Feature | LangGraph | CrewAI | MAF | ADK | OpenAI SDK | Smolagents |
|---|---|---|---|---|---|---|
| Built-in tracing | Yes (LangSmith) | Optional (LangSmith) | Yes (Azure) | Yes (Cloud Trace) | Yes (OpenAI dashboard) | No |
| Replay | Yes | No | Yes | Partial | No | No |
| Cost telemetry | External | External | Built-in | External | Built-in | No |
| Evaluation framework | External | No | No | Yes (native) | No | No |

### Observability Note
ADK's native evaluation framework (evalsets, LLM-as-judge, scoring) is the strongest evaluation capability across all frameworks studied. It should be adopted as the pattern validation mechanism in the Enterprise Cognition Learning lifecycle.

### What Cannot Be Achieved Without Studying Each Framework

Each framework's abstraction solves a problem that is invisible until you encounter it in production:

- **CrewAI's role specialization** is needed when pattern steps benefit from strongly differentiated agent personas. Without studying CrewAI, you would not know that role enrichment has a measurable impact on output quality for Exploration and Brainstorm patterns. The evidence base: CrewAI's 2 billion agent executions across 12 months (as of May 2026) with community-reported quality differences between role-rich and role-sparse crews.

- **MAF/CodeAct sandbox isolation** is needed when a single pattern step makes >5 tool calls in sequence and the combination produces emergent effects. Without studying MAF, you would not know that collapsing those calls into a single sandboxed code block reduces token cost by ~60% on representative data-gathering workloads.

- **Google ADK's composition primitives** are needed when patterns need parallel execution, looping with exit criteria, or hierarchical sub-orchestration. Without studying ADK, you would pattern-match these ad-hoc in LangGraph graphs, accruing graph complexity debt.

- **OpenAI Agents SDK's handoff primitive** is needed when the coordination pattern is peer-to-peer delegation with conversation state preservation, especially where a supervisor round-trip is overhead and the specialist agents need to see prior agent's reasoning.

- **LangGraph's state machine** is needed when the pattern requires conditional branching, persistent resume after interruption, or audit replay. Without LangGraph, none of the other frameworks provide deterministic state management at the pattern level.

The cross-framework synthesis: the Enterprise Cognition platform does not *run* these frameworks; it *absorbs* the abstractions that justify their existence and reimplements them as `PatternStep` configuration executed on a LangGraph substrate. This is the "learn from, take as our own" design direction.

## Pattern Knowledge Base

The pattern knowledge base is the set of enterprise-owned `PatternStep` bundles that a researcher can retrieve, adapt, and compose into Sessions. It is populated by two streams:

1. **Authoritative stream**: Patterns authored in-spec (REASONING-PATTERN-CATALOGUE, PATTERN-RECOGNITION-ASSIMILATION) and validated against the Framework Deep-Dive criteria. These enter the knowledge base with `status: production_ready`.

2. **Candidate stream**: Patterns observed in completed Sessions or suggested by the researcher persona that have not yet been validated. These enter with `status: experimental`.

Pattern knowledge base entries carry:

```yaml
pattern_knowledge_entry:
  pattern_id: string
  status: enum [experimental | production_ready | deprecated]
  abstraction_level: enum [direct_reuse | adaptation | metaphorical_transfer]
  source_framework: string | null        # which framework contributed this pattern, if any
  framework_pattern_id: string | null    # e.g. "crewai.tool_use_delegation"
  composability_rules: list[ComposabilityRule]
  context_sensitivity: list[SensitivityRule]
  validation_evidence:
    framework_evidence: string | null      # evidence from framework study
    session_evidence: list[session_id]     # evidence from production Sessions
    eval_score: float | null               # from ADK-style evaluation framework
  promoted_at: datetime | null
  deprecated_at: datetime | null
```

When a pattern is promoted to `production_ready`, it is eligible for direct reuse (Level 1) in new Sessions. When it is `experimental`, it requires researcher approval before being selected as a pipeline step.

Graduation from `experimental` to `production_ready` requires:
- at least three successful executions across distinct Sessions,
- an evaluation score >= threshold, or explicit researcher approval,
- no unresolved governance violations,
- registered in `registry.py` with strict persistence (`_save_manifest` must raise on failure).

## Pathway Registration

A pattern pathway is registered as a pluggable strategy on the LangGraph substrate:

```python
# Conceptual adapter entrypoint (schema, not runtime code)

class PathwayAdapter:
    substrate_id: str  # always "langgraph" in this architecture

    def configure_graph(self, pattern_step: PatternStep, context: ContextRecord) -> GraphConfig:
        """Translate PatternStep requirements into LangGraph StateGraph configuration."""

    def build(self, config: GraphConfig) -> CompiledGraph:
        """Compile the configured graph with checkpointer and interruption policy."""

    def supports(self, pattern_step: PatternStep) -> bool:
        """Return True if this adapter can execute the given pattern step."""
```

The executor flattens the Session pipeline into a sequence of PatternStep invocations. For each step:
1. The registry finds the pathway adapter matching `pattern_step.pathway_preference`.
2. If found, the adapter configures and runs the LangGraph subgraph.
3. If not found, the step degrades: the step's reasoning is executed as a plain tool call within the existing `workflow-runner` loop, and a `degraded_pathway` telemetry event is emitted.
4. Governance gates are checked between steps using LangGraph's interrupt mechanism.

## Human Approval Runtime

Human approval is implemented as a LangGraph interrupt node:
- When a `PatternStep` carries a `governance_gate` of kind `human_approval`, the graph pauses at that node.
- The handler writes `approve` / `reject` / `escalate` to `WorkflowState` via the existing `on_step_complete` callback infrastructure.
- The graph resumes from checkpoint.
- Timeout enforcement: if no response arrives within the `PatternStep` timeout, the step escalates to `PatternResponseStatus.escalated`.

Future: the `human` gateway becomes a first-class `PathwayAdapter` that manages the full approval lifecycle without coupling to the executor loop.

## Registry Strictness

Pattern bundles are stored in the registry as `SkillRecord` with `implementation: distilled`. Today, `_save_manifest` in `agentic/src/workflow-runner/registry.py` silently ignores `OSError` on write failure. For pattern bundle metadata—which encodes enabled/disabled pathway configuration and composability rules—silent failure is unacceptable.

Pattern metadata persistence must be strict:
- Write failure raises an exception.
- Caller decides retry policy.
- The registry emits a telemetry event on successful and failed writes.

This is an implementation constraint on `registry.py`, not a schema change.

## Learning & Knowledge Lifecycle

```
Novel (experimental pattern) → Reasoning execution → Playbook delta → SOP promotion → Deterministic pattern → Habit (native handler)
```

1. **Novel**: Session runs with experimental or meta-cognitive patterns. `PatternStep.status = experimental`.
2. **Reasoning**: Pattern step executes; telemetry and outputs captured in `WorkflowState` via LangGraph checkpoint.
3. **Playbook**: If the Session closes successfully and `LearningLifecycle.enabled` is true, the pipeline analyses step outputs and produces a playbook delta — a proposed revision to the `PatternStep` bundle (adjusted governance gates, enriched role prompts, modified composability rules).
4. **SOP promotion**: If the same pattern sequence is validated across >=3 Sessions with stable outcomes and acceptable gate pass rates, the researcher persona promotes the pattern to `production_ready` and registers it in `registry.py`.
5. **Deterministic execution**: `production_ready` patterns are eligible for inclusion in linear Session pipelines without supervision.
6. **Habit**: Outstanding production patterns with zero governance violations over 50+ executions are migrated to native handlers (`handle_skill_step`, `handle_tool_step`) for zero-LLM execution through the `workflow-runner` substrate.

## Enterprise Asset Store

| Asset Type | Store | Rationale |
|---|---|---|
| Policy metadata, ADRs, pattern bundles, playbook structures, session summaries | Postgres (existing `db.py`) | Structured, queryable |
| Semantic memory, prior outputs, embeddings | Qdrant | Existing container in platform |
| Authored docs, policy documents, design guidelines | Repo markdown | Versioned, reviewable |
| Framework analyses, competitive intelligence | Repo markdown (`docs/architecture/runtime-analysis/`) | Living document maintained by researcher persona |

## Worked Trace: Incident Response

1. **Context** (ENTERPRISE-CONTEXT-MODEL): Problem = incident, ActivityPurpose = execute, Environment = ai_assisted, DecisionContext = human_approval_required, timebox.
2. **Pattern** (REASONING-PATTERN-CATALOGUE + PATTERN-RECOGNITION-ASSIMILATION): Pipeline = Investigation → SOP Execution → Human Approval → Verification. Each step is a `PatternStep` with `context_sensitivity` rules (tight governance gates in `ai_assisted` environment, timebox enforced via max_turns).
3. **Session** (SESSION-MODEL): Pipeline `PatternStep`s inject roles (investigator, operator, approver, validator). `pathway_preference` sequence: `langgraph` → `workflow-runner` → `human` → `workflow-runner`.
4. **Runtime**:
   - Investigation: LangGraph substrate. State graph with conditional loop on investigation findings; interruptible at gate condition.
   - SOP Execution: LangGraph substrate. Sequential node graph wrapping existing `workflow-runner` executor loop.
   - Human Approval: LangGraph substrate. Interrupt node. `on_step_complete` blocks until handler writes approval.
   - Verification: LangGraph substrate. Sequential node graph. No `workflow-runner` degradation needed because all steps use the `langgraph` substrate.

## Worked Trace: Architecture Review Board

1. **Context**: Problem = design, ActivityPurpose = decide, DecisionContext = consensus + human_approval, Environment = humans_and_agents. Context record triggers `context_sensitivity` rule mapping `debate@1.0.0` to governance gate requiring consensus (>=2 participant approvals) before human approval.
2. **Pattern**: Pipeline = Debate → Consensus → Human Approval. Pattern bundles sourced from CrewAI's debate pattern analysis (role-specialized adversarial dialogue) adapted to `humans_and_agents` environment.
3. **Session**: `moderator`, `proposer`, `critic`, `approver` roles injected. Path: Debate runs on `langgraph` substrate as a cyclical graph (propose → critique → revise × N). Consensus runs as a participant vote node. Human approval interrupts.
4. **Runtime**: All steps on `langgraph` substrate. Governance gates embedded as conditional edges in the Debate subgraph. Consensus gate evaluates participant declarations before enabling the Human Approval interrupt node.

## Traceability to Working Principles

| Principle | Runtime Mapping Contract |
|---|---|
| 7. Frameworks are runtimes, not architecture | LangGraph is the single substrate; all patterns are substrate-agnostic `PatternStep` bundles |
| 10. Preserve architectural freedom | Context/Session/Pattern schemas carry zero framework concepts; pathway preference is a runtime hint, not a schema field |
| 8. Convert reasoning into deterministic execution | Experimental patterns graduate to `production_ready` via the Learning lifecycle, then execute deterministically |
| 2. Reason only when uncertainty exists | Known patterns (`production_ready`) run without exploration; only `experimental` patterns trigger Learning hooks |
| 4. Context determines behaviour | `context_sensitivity` rules in PatternStep bundles adapt governance, pathways, and roles to ContextRecord fields |
| 9. Learning updates enterprise assets | Playbook deltas and SOP promotions update the pattern knowledge base and `registry.py` |
