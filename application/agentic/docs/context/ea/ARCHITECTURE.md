AI Executive Assistant — Agentic System Architecture
Status: Design reference, pre-implementation Owner: Martin Platt Purpose: Reference document for building a self-extending, multi-agent "AI Executive Assistant" system, using opencode as the build agent. Intended to be dropped into the project repo so opencode (and any future contributor) has the architectural context without needing it re-explained each session.


1. Core Idea
There are two distinct loops in this system, and conflating them is the most common way these architectures go wrong.

Operating loop — agents doing real work for the business: drafting content, qualifying leads, running diagnostics, managing the BTBL site, tracking admin tasks. This is the run-time system.
Build loop — opencode, writing the code that the operating loop runs (new MCP servers, new LangGraph nodes, new tools). This is the build-time system.

opencode does not sit inside the operating loop as a worker agent. It is invoked — by Martin directly, or by an agent that has determined a new capability is needed — to produce code, which is then reviewed and deployed into the operating loop. The two loops are connected by a spec → code → deploy → telemetry → insight cycle (see Section 6).

Existing stack: Postgres, Qdrant, Redis, RabbitMQ, Langfuse, LangGraph, OpenObserve, Docker/Dockge.


2. Run-Time Execution Flow
                   ┌───────────────────────────────────────┐
                   │        USER / DASHBOARD (UI)          │
                   └───────────────────┬───────────────────┘
                                       │ Publishes Task via API
                                       ▼
                   ┌───────────────────────────────────────┐
                   │       AGENT BUS (EVENT BUS)          │
                   └───────────────────┬───────────────────┘
                                       │ Triggers LangGraph (via API)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH (THE CONDUCTOR)                              │
│                           (API-Accessible Orchestrator)                          │
│                                                                                   │
│   [ Node: Agent A ] ──> API Request to Functionality (via Service Registry)      │
│                                             │                                    │
│                                             ▼                                    │
│   [ Node: Agent B ] ──> API Request to Functionality (via Service Registry)      │
│                                                                                   │
│   (Internal: State Management (Postgres), Vector Lookup (Qdrant), Logs (Langfuse))
└─────────────────────────────────────────────────────────────────────────────────┘

Dashboard / UI Container — single pane of glass. Chat interface, agent state monitors, shared Kanban-style task board. Does not talk to agents directly; it publishes tasks to the agent bus via an API and listens to the bus for status updates. Agents never need to know a UI exists.

Agent Bus (Event Bus) — decouples agents from each other. Agent A publishes {"task": "audit_code", "repo": "xyz"}; whichever agent is subscribed to audit_code events claims it, processes it, and publishes {"task": "audit_complete", "status": "..."}. No hardcoded IP addresses or direct agent-to-agent calls.

LangGraph (The Conductor) — a Python library, treated as an API-accessible service. It acts as the orchestrator, managing the flow between different agent nodes. It is accessed via an API, passed data to make it work, and can be swapped out with other AI orchestration services. Internally, LangGraph nodes (agents) interact with specific functionalities by making API requests, often discovering these functionalities through a service registry.

MCP Server — exposes workflows as atomic skills, accessible via API. Workflows can re-use existing skills.


3. The C-Suite Layer
Martin is the board. Below him is one agent with a standing conversational relationship — everything else reports to it. Each of these is a LangGraph subgraph, not necessarily a separate container.

Agent
Role
CEO / Chief of Staff
The front door. Holds working context (current priorities across BTBL and the AI EA build), routes requests to the right department, synthesizes insights back rather than dumping raw agent output. The only agent Martin talks to directly in normal use.
COO
Owns operating cadence — task board state, status of in-flight workflows, flags stalled work.
CTO
Owns the build loop. Wraps opencode. Turns "I need a tool that does X" into a spec, hands it to opencode, reviews the diff, coordinates deployment.
CMO
Content and LinkedIn — BTBL offer suite work, hook/story/insight post drafting on a cadence.
CFO / Admin
Administrative tracking — disputes, invoicing, the kind of work behind the St George dispute.


Sequencing note: don't build all five at once. Start with CEO/Chief of Staff + one real operating capability, then CTO + opencode for one manual build task, before anything tries to act autonomously. See Section 7.


4. Memory — Three Tiers
This is the part most agentic systems get wrong, and it's central to "track what I'm saying, remember, generate insights."

Working memory — current session/task state. Postgres. Scoped per conversation thread. This already exists in the LangGraph persistence layer described in Section 2.
Episodic / semantic memory — Qdrant. Embeddings of past conversations and decisions, so an agent can retrieve prior context ("what did Martin decide about the ICP three months ago") instead of requiring re-explanation.
Insight memory — the missing piece in most designs. A separate table/collection holding distilled patterns, not raw conversation: recurring requests, repeated workflow failures, two requests that are actually the same underlying need. Populated by a dedicated Reflection Agent (Section 5) that runs periodically over the episodic store.

The insight layer is what allows the system to propose new automation rather than only executing what it's asked.


5. The Reflection Agent
Runs periodically (cron, or triggered off Langfuse trace volume) over the episodic memory store. Does not write prose directly to Martin. Output is a structured proposal:

{

  "pattern": "Recurring request to summarize workflow failures every Monday",

  "evidence_count": 4,

  "recommendation": "Build a scheduled capability that auto-generates this summary",

  "confidence": "medium"

}

This proposal routes to the CTO agent — queued for opencode to build, or surfaced to Martin for a yes/no if consequential. This agent should be built last, after there's real conversation/telemetry volume worth mining (see Section 7).


6. The Self-Extension Cycle
How a new capability gets born — this is the loop that connects build-time and run-time:

Identify — Reflection Agent (or Martin, directly in chat) identifies a need.
Spec — CTO agent turns it into a spec: inputs, outputs, which MCP tools/APIs it needs, where it sits in the graph.
Build — CTO agent invokes opencode against the capability repo to scaffold the MCP server or LangGraph node.
Review — opencode's diff is reviewed (by Martin initially; eventually a lightweight review-agent step once trust is established).
Deploy — pushed live via the existing Dockge flow.
Register — the new node registers itself (manifest file or DB row) so the orchestration layer and dashboard know it exists.
Observe — Langfuse captures telemetry from first invocation, feeding the next Reflection Agent pass.

insight → spec → code → deploy → telemetry → insight (loop)

opencode is the only step in this cycle that writes code. Every other step is orchestration or review.


7. Build Order (Recommended)
Resist building the whole C-Suite at once. Narrowest end-to-end slice that proves the architecture:

CEO / Chief of Staff agent — Postgres working memory + Qdrant recall, wired to existing Manifest model routing.
One real capability behind it — e.g., implement a core session-start flow as a LangGraph node, leveraging code-based building blocks for persistence and resume behavior.
CTO agent + opencode, wired up for exactly one manually triggered build task — to prove the spec→code→deploy mechanics before any agent attempts it autonomously.
Reflection Agent — last. Only useful once there's real conversation/telemetry volume worth mining (see Section 7).


8. Code-Based Building Blocks, Skills, and Tools

Instead of relying on visual workflow tools, the system will leverage code-based building blocks, skills, and tools for constructing workflows. This approach offers greater flexibility, version control, and integration with the build loop.

*   **Workflow Definition:** Workflows are defined programmatically using these building blocks. These can be simple functions, complex multi-step processes, or integrations with external APIs.
*   **Manual Execution:** All defined workflows and individual skills are exposed via an API, allowing for manual execution without direct AI involvement. This provides a way for developers and users to test, debug, and run specific functionalities directly.
*   **MCP Server Skills:** These code-based workflows and atomic skills are registered as capabilities within the system, effectively becoming "MCP Server Skills." This makes them discoverable and callable by AI agents.
*   **Skill Reusability:** Workflows can compose and reuse existing atomic skills, promoting modularity and reducing redundancy.
*   **Caching and AI Optimization:** To enhance efficiency, a caching layer will be implemented. For identical calls to a workflow or skill:
    *   A high percentage (e.g., 8 out of 10 times) will directly return a cached result or execute the standard path.
    *   A smaller percentage (e.g., 2 out of 10 times) will trigger an AI agent to analyze the execution, potentially seeking to optimize the workflow design, improve prompt efficiency, or discover new, more effective approaches. This allows for continuous learning and improvement without impacting every single execution.


9. Notes for Using This With opencode
opencode is a coding agent that operates on a repo on disk — it reads, writes, and edits files, and can run shell commands, much like having a very capable junior engineer who works from a spec. Practical notes for someone new to it but experienced as a coder:

Give it this document as project context (e.g. drop it in the repo root or a /docs folder) so it understands the target architecture before generating scaffolding — it works from whatever context and instructions you give it in-session or via files it can read, so explicit architectural grounding like this materially improves output quality.
Treat opencode like the CTO agent's hands, not the CTO agent itself. opencode writes code from a spec; it doesn't decide what to build. Keep that decision-making in your own head (or eventually the CTO agent) and hand opencode concrete, scoped specs — "scaffold an MCP server with these tool definitions" rather than "build me a CTO agent."
Start with the CTO + opencode slice from Section 7, step 3 before letting any agent call opencode autonomously. Confirm the review/deploy mechanics work end-to-end with you in the loop first.
Repo structure suggestion: a dedicated agent-capabilities repo or directory, separate from the BTBL site repo, with subfolders per capability (mcp-servers/, langgraph-nodes/, manifests/) so opencode's scaffolding output has a consistent home and the orchestration layer has a predictable place to look for new manifests.


10. Open Decisions / Next Steps
Confirm dashboard tooling (Chainlit / Streamlit / custom React) for the UI container.
Define the Postgres schema for working memory (likely extends existing users/sessions tables).
Define the Qdrant collection schema for episodic memory and the insight memory table/collection.
Set up opencode against the capability repo and run one manual build task end-to-end (Section 7, step 3) before building any further agents.
Decide manifest format for capability registration (Section 6, step 6).
