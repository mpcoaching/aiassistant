# System Design & Architecture

## 1. Topological Strategy
* **Orchestrator**: Data-driven state machine. Decoupled via internal interface from implementation.
* **Microservices**: Independent containers; strictly isolated via API-first contracts.
* **Data Access**: All persistence operations must be routed through stored procedures. Direct SQL is strictly prohibited.

## 2. Abstraction & Portability
* **API Ubiquity**: Communication is exclusive to `/v1/*` endpoints. No shared memory or database-level coupling.
* **Provider Agnosticism**: All external service integrations (LLMs, Prompt Managers, Message Bus) must be implemented behind interfaces. Implementation is injected at runtime.
* **Orchestrator Decoupling**: Service discovery and task resolution are mediated by registry config; the Orchestrator maintains no hardcoded service logic.

## 3. Data & Asset Management
* **Prompt Management**: Prompts are externalized, versioned assets (e.g., managed via Langfuse abstraction).
* **Payload Schemas**: All interfaces are defined via Pydantic/Zod. These serve as the primary truth for inter-service contracts.

## 4. Architectural Patterns & Blueprints
* **Patterns**: We utilize standard enterprise patterns (e.g., *Service Layer*, *Gateway*, *Data Mapper*).
* **Blueprints**: The implementation of these patterns may be codified in `/templates`. Agents must use these templates to ensure the chosen pattern is applied consistently.

# System Design & Architecture
*   **Orchestrator**: Data-driven state machine. Decoupled via internal interface.
*   **Microservices**: Independent containers; strictly isolated via API-first contracts.
*   **Communication**: API-only (REST/gRPC). No shared memory/DB.
*   **Prompt Management**: Externalized assets via versioned provider interface.
*   **Persistence**: Stored procedures only.