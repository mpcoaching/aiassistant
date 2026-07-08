# Architectural Blueprint: The Agentic Software Factory

## 1. High-Level Logical Stack (The "EA View")
This system is architected as a **Deterministic Agentic Factory**, where AI capabilities are treated as constrained services rather than free-form chatbots.

*   **Governance Layer (The C-Suite)**: High-level orchestration using LangGraph. This layer is responsible for goal decomposition, strategic alignment, and auditing.
*   **Capability Layer (The Specialists)**: Containerized services performing specific domain tasks (e.g., Solution Architect, Code Generator).
*   **Infrastructure Layer (The Factory Floor)**: A robust data and execution plane using Redis/Postgres for state management, Qdrant for long-term knowledge, and Aider for deterministic code generation.

## 2. Operating Principles
*   **Slot-Filling over Creation**: Agents must use pre-approved patterns from our `/patterns` repository to ensure consistent, enterprise-grade output.
*   **Deterministic Contracts**: All communication between layers occurs via versioned Pydantic JSON schemas, ensuring clear interface contracts.
*   **Observability**: Every decision, tool call, and state change is logged to ensure auditability and compliance.

## 3. Implementation Roadmap (The MVP Path)
| Phase | Focus | Objective |
| :--- | :--- | :--- |
| **Phase 1** | Template Engine | Build `/patterns` directory and establish manual Aider-based code generation. |
| **Phase 2** | Service Wrapper | Wrap Phase 1 in FastAPI containers to standardize the "slot-filling" API. |
| **Phase 3** | Orchestration | Connect LangGraph "C-Suite" to dispatch work orders to Phase 2 services. |
| **Phase 4** | Multi-Tenancy | Partition state stores (Redis/Postgres) by `tenant_id` for coaching clients. |

## 4. Agentic Guardrails (Rules for AI)
To keep this high-level view synced with technical reality, all agentic systems (including Aider) must obey the following:
1.  **Read-Only Strategy**: Agents must read this `ARCHITECTURE_BLUEPRINT.md` for context but should rarely modify it unless explicitly instructed.
2.  **Schema Compliance**: Agents must adhere to the technical contracts defined in `SYSTEM_DESIGN.md`.
3.  **Pattern Enforcement**: No code is to be generated from scratch if a corresponding template exists in the `/patterns` directory.