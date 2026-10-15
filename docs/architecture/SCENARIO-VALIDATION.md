# Scenario Validation: Incident Response and Architecture Review Board

## Purpose

This document traces two canonical scenarios through all five Enterprise Cognition specifications to validate that the cross-spec model is coherent, that backward compatibility is preserved, and that the new competitive framework analysis and pattern recognition/assimilation layer integrates cleanly with the existing architecture.

## Scenarios

### Scenario A: Payment Gateway Incident Response

**Human situation**: A payment processing gateway reports a sudden spike in 5xx errors. The incident commander needs to quickly determine the root cause, apply a fix, obtain human approval for the change, verify recovery, and capture lessons learned.

### Scenario B: Architecture Review Board — Internal Platform Decision

**Human situation**: The architecture review board must decide whether to adopt a new frontend framework for internal platforms. The decision requires adversarial debate, consensus from multiple stakeholders, and formal human approval before the policy is recorded.

---

## Trace A: Payment Gateway Incident Response

### 1. Context (ENTERPRISE-CONTEXT-MODEL.md)

| Field | Value |
|---|---|
| `problem_context` | `incident` |
| `activity_purpose` | `investigate` (first), then `execute` (after root cause found) |
| `environment_context` | `ai_assisted` |
| `information_context` | `enterprise_knowledge` + `internal_only` |
| `decision_context.authority_model` | `single_authority` |
| `decision_context.human_approval_required` | `true` |
| `decision_context.timebox_seconds` | `3600` |
| `free_text_fields` | `sub_category: payment_gateway`; `urgency: high` |

Cross-reference consistency:
- `problem=incident, activity_purpose=investigate` maps to Investigation pattern per the Context-to-Pattern Mapping Table.
- `human_approval_required=true` and `ai_assisted` environment trigger `context_sensitivity` rules on the Human Approval pattern (see PATTERN-RECOGNITION-ASSIMILATION.md): in `ai_assisted`, all pathways are enabled; human is always a fallback.
- The `ai_assisted` environment means the AI agent's personal research store may be consulted (AGENTIC-EXPERIENCE.md Principle 2), but for an incident, the enterprise investigation process is the default.

### 2. Pattern Recognition (PATTERN-RECOGNITION-ASSIMILATION.md)

**Level 1 retrieval**: The context tuple `(incident, investigate)` and `(incident, execute)` both have direct matches in the enterprise pattern store. Confidence: high. No Level 2 or Level 3 synthesis needed.

**Recognised pattern bundle**: `investigation@1.0.0` → `sop_execution@1.0.0` → `human_approval@1.0.0` → `verification@1.0.0`

**Pattern context sensitivity**:

| Pattern | Sensitivity trigger | Effect |
|---|---|---|
| Investigation@1.0.0 | `timebox_seconds: 3600` | Max turns = 3600; investigation escalates if unresolved |
| SOP Execution@1.0.0 | `ai_assisted` | Full pathway enabled; no degradation expected |
| Human Approval@1.0.0 | `human_approval_required: true` | Human pathway always primary; always generates approval trail |
| Verification@1.0.0 | `ai_assisted` | Primary pathway: `workflow-runner`; `maf` listed as alternate (unregistered, degraded fallback) |

### 3. Session (SESSION-MODEL.md)

```yaml
session:
  id: ir-20240615-001
  context:
    problem_context: incident
    activity_purpose: investigate -> execute
    environment_context: ai_assisted
    decision_context:
      authority_model: single_authority
      human_approval_required: true
      timebox_seconds: 3600
  pipeline:
    - pattern_id: investigation@1.0.0
      role_override: investigator
      participants: [investigator_ai, incident_commander_human]
      enabled_pathways: [workflow-runner, langgraph]
      disabled_pathways: [crewai, maf]
      status: pending
    - pattern_id: sop_execution@1.0.0
      role_override: operator
      participants: [operator_ai, incident_commander_human]
      enabled_pathways: [workflow-runner]
      disabled_pathways: [langgraph, crewai, maf]
      status: pending
    - pattern_id: human_approval@1.0.0
      role_override: approver
      participants: [incident_commander_human]
      enabled_pathways: [human, workflow-runner]
      disabled_pathways: [langgraph, crewai, maf]
      status: pending
    - pattern_id: verification@1.0.0
      role_override: validator
      participants: [validator_ai]
      enabled_pathways: [workflow-runner, maf]
      disabled_pathways: [langgraph, crewai]
      status: pending
  governance:
    gates:
      - kind: human_approval
        condition: action_requires_human
        on_fail: stop
      - kind: policy_check
        condition: mandatory_compliance_check
        on_fail: stop
  distillation_hook:
    enabled: true
    target_store: postgres
```

Cross-reference consistency:
- `Participants` conforms to `ParticipantRecord` schema (id, kind, role, capabilities). `agent_ref` fields are set after pathway adapter builds the graph/LangGraph agent.
- `enabled_pathways` / `disabled_pathways` matches the `REASONING-PATTERN-CATALOGUE.md` definition.
- Backward compatibility: this Session config is stored in `WorkflowState.context` under the key `session` and is embeddable in the existing `WorkflowDefinition` YAML via a `session:` top-level block, per `SESSION-MODEL.md` design constraint 1.

### 4. Agentic Experience Layer (AGENTIC-EXPERIENCE.md + PATTERN-RECOGNITION-ASSIMILATION.md)

**At investigation step start**:

1. The Composer assembles the investigator's prompt:
   - Layer 1 (Enterprise): Playbook for payment gateway incidents, PCI-DSS compliance reference.
   - Layer 2 (Session): Incident context, prior logs, ContextRecord fields.
   - Layer 3 (Persona): The `investigator_ai`'s personal research store is consulted. If this investigator has solved a similar incident before, their heuristics appear here. If they have a previously failed approach, that failure is surfaced.
   - Layer 4 (Pattern template): Investigation prompt template.

2. **Principle 1 — Recognition before reasoning**: The investigator's research store is queried first (Level 1 retrieval in PATTERN-RECOGNITION-ASSIMILATION.md). If a direct-match pattern from a prior incident is found, it is proposed as a direct-reuse `PatternStep` adjustment rather than triggering full Investigation pattern execution.

3. **Principle 8 — Convert reasoning into deterministic execution**: If the investigation succeeds and the pattern matches a known SOP (e.g., "PCI gateway restart SOP"), the Learning lifecycle proposes promoting the pattern to `implementation: distilled` in `registry.py`. This promotes the SOP for future direct reuse without investigation.

**At session close**:

- The investigator's findings are stored as a `playbook_delta` in the enterprise asset store (Postgres).
- The incident commander's human approval record is stored as an `Artifact: approval_trail` in `WorkflowState.outputs`.
- The Learning lifecycle is triggered (if `distillation_hook.enabled`). The `Registry._save_manifest` strict persistence requirement ensures the playbook delta is not silently lost.

### 5. Runtime (RUNTIME-MAPPING.md)

```python
# Conceptual runtime flow

# Step 1: Investigation on langgraph substrate
investigation_graph = LangGraphAdapter.configure_graph(
    pattern_step=session.pipeline[0],  # investigation@1.0.0
    context=session.context,
)
investigation_result = investigation_graph.invoke(
    checkpoint=investigator_checkpoint,
    interrupt_on=[Gate(gate_kind="timeout", timebox_seconds=3600)],
)

# Step 2: SOP Execution on workflow-runner substrate (wrapped in langgraph node)
sop_result = WorkflowRunnerAdapter.configure_and_run(
    pattern_step=session.pipeline[1],  # sop_execution@1.0.0
    context=session.context,
    participants=[operator_ai],
)

# Step 3: Human Approval as langgraph interrupt node
approval_graph = LangGraphAdapter.build(
    config=nodes={"approval_gate": HumanApprovalInterruptNode},
    interrupt_before=["approval_gate"],
)
# Graph pauses here; handler writes approval to WorkflowState -> graph resumes
human_approval_result = approval_graph.invoke_until_resumed(checkpoint)

# Step 4: Verification on langgraph substrate (maf adapter not registered -> degraded fallback)
verification_result = LangGraphAdapter.configure_graph(
    pattern_step=session.pipeline[3],  # verification@1.0.0
    context=session.context,
).invoke(
    checkpoint=validator_checkpoint,
)
# maf adapter not registered -> verification runs as sequential langgraph node chain
# degraded_pathway telemetry event emitted
```

**Route summary**:

| Step | Pattern | Primary Pathway | Adapter | Fallback |
|---|---|---|---|---|
| 1 | Investigation@1.0.0 | `langgraph` | LangGraphAdapter | `workflow-runner` |
| 2 | SOP Execution@1.0.0 | `workflow-runner` | WorkflowRunnerAdapter | None |
| 3 | Human Approval@1.0.0 | `human` | HumanInterruptAdapter | None |
| 4 | Verification@1.0.0 | `workflow-runner` (primary), `maf` (alternate) | WorkflowRunnerAdapter | mafPathwayAdapter not registered → degraded fallback (telemetry event emitted) |

**Framework insight**: SOP Execution uses `workflow-runner` because it is deterministic. Investigation uses `langgraph` because it requires conditional branching. This alignment (pattern abstraction level → substrate capability) is exactly the competitive analysis in RUNTIME-MAPPING.md. CrewAI's role-based abstraction would add no value here because roles are simple (investigator, operator). MAF's CodeAct would add value only if Investigation has >5 sequential tool calls; for medium-complexity incidents, the current `workflow-runner` + `langgraph` split is sufficient.

**Consistency checks**:
- ✅ Context tuple `(incident, investigate)` → Investigation pattern: matches REASONING-PATTERN-CATALOGUE.md mapping table.
- ✅ `human_approval: true` → Human Approval pattern with `human` pathway primary: matches REASONING-PATTERN-CATALOGUE.md pattern def.
- ✅ `workflow-runner` as execution substrate for SOP Execution: matches both RUNTIME-MAPPING.md and REASONING-PATTERN-CATALOGUE.md.
- ✅ `maf` adapter not registered → degraded fallback + telemetry event: matches RUNTIME-MAPPING.md degraded routing section.
- ✅ Learning lifecycle enabled → playbook delta promoted to enterprise store: matches PATTERN-RECOGNITION-ASSIMILATION.md assimilation pipeline step 4.
- ✅ `Registry._save_manifest` strict persistence: enforced for playbook delta write.
- ✅ No framework concepts in Context/Session/Pattern schemas: verified.
- ✅ Backward compatibility: Session block is embeddable in existing WorkflowDefinition YAML: verified.

**Handling the Research phase** (fundamental framing): The incident response scenario should ideally include a `Research` pattern step before Investigation when the incident type is novel (ProblemContext = `unknown`). In this case, the incident type is known (`incident`), so Level 1 retrieval succeeds and Research is short-circuited. If the incident were novel, the pipeline would be: `Research → Investigation → SOP Execution → Human Approval → Verification`. This is an explicit scenario design decision: known incidents skip Research because the playbook already contains relevant prior research. Novel incidents insert Research as a pattern step to gather knowledge before investigation begins. This respects the Principle 1 (Recognition before reasoning): if a research record exists in the enterprise store, it is retrieved before triggering expensive Research pattern execution.

---

## Trace B: Architecture Review Board — Internal Platform Decision

### 1. Context (ENTERPRISE-CONTEXT-MODEL.md)

| Field | Value |
|---|---|
| `problem_context` | `design` |
| `activity_purpose` | `decide` |
| `environment_context` | `humans_and_agents` |
| `information_context` | `enterprise_knowledge` + `historic_decisions` |
| `decision_context.authority_model` | `consensus` |
| `decision_context.human_approval_required` | `true` |
| `decision_context.confidence_required` | `high` |
| `free_text_fields` | `sub_category: platform_architecture`; `constraints: internal_only` |

Cross-reference consistency:
- `problem=design, activity_purpose=decide` maps to Debate pattern per the Context-to-Pattern Mapping Table.
- `authority_model=consensus` and `human_approval_required=true` trigger specific `context_sensitivity` rules on Debate and Consensus patterns.
- `environment_context=humans_and_agents` activates human-augmented pathway routing. This is the `meta-participant` context for the researcher persona to observe.

### 2. Pattern Recognition (PATTERN-RECOGNITION-ASSIMILATION.md)

**Level 1 retrieval**: `(design, decide)` maps to Debate pattern with high confidence. Level 2 near-match: if the enterprise store contains a prior framework evaluation debate (e.g., from the previous year's tech-radar review), a Level 2 adaptation is proposed: `debate@framework_evaluation_variant` → `consensus@framework_evaluation_variant`.

**Recognised pattern bundle**: `debate@1.0.0` → `consensus@1.0.0` → `human_approval@1.0.0`

**Pattern context sensitivity** (Framework Analysis influence):

| Pattern | Sensitivity trigger | Effect |
|---|---|---|
| Debate@1.0.0 | `authority_model=consensus` | Governance gate adds confidence threshold >0.8 AND requires >=2 participant approvals before completion |
| Debate@1.0.0 | `environment_context=humans_and_agents` | All pathways enabled; human participants are treated as first-class graph nodes (not as interrupt handlers) |
| Consensus@1.0.0 | `authority_model=consensus` | Consensus gate condition evaluates participant declarations |
| Human Approval@1.0.0 | `human_approval_required=true` | Human pathway always primary; approval trail recorded |

**Framework study influence**: Debate pattern is enriched by the CrewAI analysis in RUNTIME-MAPPING.md — role specialisation (devil's advocate, proposer, moderator) maps to `role_override` on the Debate pattern step. Without studying CrewAI, the Debate pattern would use generic Agent roles; with the CrewAI analysis, the roles carry enriched prompt templates (backstory, goal, trusted sources) that reflect the CrewAI finding that role-rich agents outperform generic agents in adversarial dialogue.

### 3. Session (SESSION-MODEL.md)

```yaml
session:
  id: arb-20240615-001
  context:
    problem_context: design
    activity_purpose: decide
    environment_context: humans_and_agents
    information_context:
      - enterprise_knowledge
      - historic_decisions
    decision_context:
      authority_model: consensus
      human_approval_required: true
      confidence_required: high
  pipeline:
    - pattern_id: debate@1.0.0
      role_override: moderator
      participants: [proposer_ai, critic_ai, chair_human]
      enabled_pathways: [langgraph, crewai, human]
      disabled_pathways: [workflow-runner, maf]
      config:
        max_debate_rounds: 5
        confidence_threshold: 0.8
        roles:
          proposer: { backstory: "...", goal: "..." }
          critic: { backstory: "...", goal: "..." }
      status: pending
    - pattern_id: consensus@1.0.0
      role_override: facilitator
      participants: [proposer_ai, critic_ai, chair_human]
      enabled_pathways: [langgraph, human]
      disabled_pathways: [workflow-runner, crewai, maf]
      status: pending
    - pattern_id: human_approval@1.0.0
      role_override: approver
      participants: [chair_human]
      enabled_pathways: [human, workflow-runner]
      disabled_pathways: [langgraph, crewai, maf]
      status: pending
  governance:
    gates:
      - kind: consensus
        condition: authority_model_met
        on_fail: escalate
      - kind: human_approval
        condition: high_stakes_decision
        on_fail: pause_for_input
  distillation_hook:
    enabled: true
    target_store: postgres
```

**Cross-reference consistency**:
- Debate roles (`proposer`, `critic`, `moderator`) match REASONING-PATTERN-CATALOGUE.md.
- `enabled_pathways: [langgraph, crewai, human]` — note that `crewai` is listed but not registered as a substrate adapter. Session creation resolves this: langgraph is primary for Debate; crewai is retained as a documented pattern variant but not executed as a separate substrate. This is the design intent from RUNTIME-MAPPING.md: framework ideas are absorbed as patterns, not as separate substrates.
- `consensus@1.0.0` sets `disabled_pathways: [workflow-runner, crewai, maf]` — all non-LangGraph substrates disabled for Consensus because the consensus algorithm requires explicit state tracking across participants, which LangGraph provides via checkpointing.

**Backward compatibility**: The `config` block carries enriched role definitions that include `backstory` and `goal` from the CrewAI framework analysis. These are plain strings in YAML — not framework objects — so they are compatible with the stable abstraction boundary. The Composer in `workflow-runner` treats them as additional prompt fragments appended to the role prompt template.

### 4. Agentic Experience Layer (AGENTIC-EXPERIENCE.md + PATTERN-RECOGNITION-ASSIMILATION.md)

**At session creation**:
- The researcher persona (the ARB chair or a designated researcher) accesses the cross-store view: `ResearcherView(perspective_subset=[chair_human, senior_architect_ai])`.
- The researcher's own personal store contains prior ARB sessions and their observations about which debate framing approaches produce consensus most efficiently. This meta-perspective informs the `config.debate_framing` in the Debate pattern step.
- This is the researcher as `meta-participant` from AGENTIC-EXPERIENCE.md: they observe, annotate, and shape the session without executing business steps.

**At session close**:
- The dissenting record (if any) is stored as an `Artifact: dissent_record` in `WorkflowState.outputs`.
- The dissenting outcome is also stored in the `critic_ai`'s personal research store with `scope: team_shared`, so future sessions involving the critic persona carry this perspective.
- The Learning lifecycle proposes a playbook delta: if the debate reaches consensus within 3 rounds 80% of the time, the `config.max_debate_rounds` is reduced from 5 to 3.

### 5. Runtime (RUNTIME-MAPPING.md)

```python
# Conceptual runtime flow

# Step 1: Debate on langgraph substrate (cyclical graph)
debate_graph = LangGraphAdapter.configure_graph(
    pattern_step=session.pipeline[0],  # debate@1.0.0
    context=session.context,
)
# Graph configuration:
#   nodes: proposer, critic, moderator (one node per role participant)
#   edges: proposer -> critic -> moderator -> proposer (cycle, max 5 iterations)
#   interrupt_before: [gate: confidence_threshold > 0.8, gate: consensus check]
#   checkpoint: per-node

debate_result = debate_graph.invoke(
    checkpoint=debate_checkpoint,
    max_iterations=5,
)

# Confidence threshold evaluated inside graph; if unmet, graph continues loop.
# If met, graph proceeds to Consensus node.

# Step 2: Consensus on langgraph substrate
consensus_graph = LangGraphAdapter.configure_graph(
    pattern_step=session.pipeline[1],  # consensus@1.0.0
    context=session.context,
)
# Consensus gate evaluates participant declarations via configured authority_model.
# In `consensus` authority_model: >=2 approvals required from [chair_human, senior_architect_ai, proposer_ai]

consensus_result = consensus_graph.invoke(
    checkpoint=consensus_checkpoint,
)

# Step 3: Human Approval as langgraph interrupt node
approval_graph = LangGraphAdapter.build(
    config=nodes={"approval_gate": HumanApprovalInterruptNode},
    interrupt_before=["approval_gate"],
)
approval_result = approval_graph.invoke_until_resumed(checkpoint)
# Chair human approves via handler -> WorkflowState.approval_trail updated -> graph resumes -> session completes
```

**Route summary**:

| Step | Pattern | Primary Pathway | Adapter | Fallback |
|---|---|---|---|---|
| 1 | Debate@1.0.0 | `langgraph` | LangGraphAdapter | WorkflowRunnerAdapter (degraded, non-cyclic) |
| 2 | Consensus@1.0.0 | `langgraph` | LangGraphAdapter | None (no fallback defined for consensus) |
| 3 | Human Approval@1.0.0 | `human` | HumanInterruptAdapter | None |

**Framework insight**: Debate as a cyclical graph on LangGraph is the natural substrate choice. CrewAI's role-based crew is the *pattern* (enriched roles), not the substrate. If the Debate pattern were to be executed on CrewAI's substrate, it would use CrewAI's hierarchical process with the same role definitions. It would not produce better outcomes than LangGraph with enriched roles, and it would not provide checkpointed state or governance gate interrupts. Therefore, CrewAI as a substrate is discarded; the role-specialization abstraction is absorbed. OpenAI Agents SDK's handoff primitive is not applicable here because Debate requires adversarial cycling rather than peer delegation.

**Handling the Research phase** (fundamental framing): For an ARB decision, the Research phase is embedded within the Debate pattern's `inputs: [propositions, evidence, criteria]`. The propositions and evidence are gathered by the `researcher` agent as part of the Debate's inputs, not as a separate pattern step. This is the correct design: architecture decisions require fresh evidence per debate, not a reusable prior research store. The researcher persona's cross-store view still contributes: the researcher surfaces prior ARB decisions on similar topics from the enterprise store as `input_evidence` before the Debate graph begins.

---

## Scenario-Level Consistency Checks

### Check 1: Schema Stability

| Schema | Frameworks in Incident Trace | Frameworks in ARB Trace | Framework-free? |
|---|---|---|---|
| ContextRecord | 0 | 0 | ✅ |
| Session | 0 | 0 | ✅ |
| PatternStep | 0 | 0 | ✅ |
| ParticipantRecord | 0 | 0 | ✅ |
| AgentPersona | 0 | 0 | ✅ |
| ResearchStoreRef | 0 | 0 | ✅ |

### Check 2: Pathway Resolution

| Pattern | Enabled Pathways | Registered Adapter | Resolution |
|---|---|---|---|
| investigation@1.0.0 | workflow-runner, langgraph | LangGraphAdapter, WorkflowRunnerAdapter | LangGraphAdapter used |
| sop_execution@1.0.0 | workflow-runner | WorkflowRunnerAdapter | Used |
| human_approval@1.0.0 | human, workflow-runner | HumanInterruptAdapter, WorkflowRunnerAdapter | HumanInterruptAdapter used |
| verification@1.0.0 | workflow-runner, maf | WorkflowRunnerAdapter, mafPathwayAdapter (not registered) | WorkflowRunnerAdapter used; maf degraded fallback telemetry event |
| debate@1.0.0 | langgraph, crewai, human | LangGraphAdapter | LangGraphAdapter used; crewai and human not substrates, remain in enabled list as documented pattern variants |
| consensus@1.0.0 | langgraph, human | LangGraphAdapter, HumanInterruptAdapter | LangGraphAdapter used |

### Check 3: Pattern Recognition Levels

| Scenario | Level 1 (direct match) | Level 2 (adaptation) | Level 3 (synthesis) |
|---|---|---|---|
| Incident Response | investigation@1.0.0, sop_execution@1.0.0, human_approval@1.0.0, verification@1.0.0 | None required | None required |
| Architecture Review Board | debate@1.0.0, consensus@1.0.0, human_approval@1.0.0 | Possible: prior ARB debate pattern could be adapted | None required |

### Check 4: Backward Compatibility

| Constraint | Status |
|---|---|
| WorkflowDefinition YAML unchanged | ✅ Session block is a new top-level key; existing YAML keys are untouched |
| db.py unchanged | ✅ Session state stored in `WorkflowState.context` under a `session` key |
| executor.py unchanged | ✅ Adapter dispatch is pluggable and falls back to existing loop |
| Existing `workflow-runner` pathway is primary for deterministic steps | ✅ Both scenarios use `workflow-runner` for SOP/SOP-equivalent steps |
| No framework concepts in Context/Session/Pattern | ✅ Verified |

### Check 5: Framework Competitive Analysis Applied

| Framework | Found in Scenario | Applied As |
|---|---|---|
| LangGraph | Both (Investigation, Debate, Consensus, Human Approval, Verification) | Execution substrate |
| CrewAI | ARB Debate only | Role enrichment pattern (not substrate) |
| AutoGen | Neither | History/Replay pattern absorbed into Session observability |
| MAF / CodeAct | Neither | Under design; future Investigation steps with >5 tool calls would benefit |
| Google ADK | Neither | Composition primitives inform PatternStep. The `consensus` gate uses ADK-influenced authority_model evaluation logic |
| OpenAI Agents SDK | Neither | Handoff primitive future variant |
| Smolagents | Neither | Future Investigation steps with code-based tool composition |

### Check 6: Researcher Persona Cross-Store Access

| Scenario | Researcher Involved | Action |
|---|---|---|
| Incident Response | No dedicated researcher; investigator_ai performs research | Investigator's personal store is read; no cross-persona access needed |
| Architecture Review Board | Chair_human acts as researcher/researcher | Cross-store view: prior ARB decisions, critic_ai's dissent history, proposer_ai's prior proposals |

This is consistent with AGENTIC-EXPERIENCE.md: researcher access is privilege-dependent. The ARB chair has cross-store authority; the incident investigator does not.

---

## Scenario Summary

Both scenarios pass all cross-spec consistency checks. The key findings from validation are:

1. **LangGraph substrate is sufficient**: No scenario requires a separate CrewAI or MAF substrate. Their contribution is in the pattern library, not in runtime execution.

2. **Pattern Recognition short-circuits Research**: For known incident types, Level 1 retrieval bypasses the Research pattern. Research is only triggered for novel problems (Level 3 synthesis). This is the intended behaviour of the recognition-before-reasoning architecture.

3. **Context sensitivity rules work as designed**: The same `debate@1.0.0` pattern produces materially different graph configurations depending on `environment_context` and `decision_context` values, without modifying the pattern bundle itself.

4. **Framework competitive analysis feeds the pattern catalogue**: CrewAI's role-abstraction directly enriches the Debate pattern's role definitions. ADK's composition primitives inform how Debate and Consensus chain. MAF's CodeAct informs the Investigation pattern's tool composition for high-volume steps.

5. **Degraded pathway handling is exercised**: Scenario A exercises the `maf` degradation on Verification. No degradation occurs for the primary workflows, confirming the substrate choice is correct.

6. **Learning lifecycle hook is wired**: Both scenarios have `distillation_hook.enabled: true`, meaning completed sessions trigger playbook delta generation. The strict `_save_manifest` requirement in `registry.py` ensures playbook writes are never silently lost.
