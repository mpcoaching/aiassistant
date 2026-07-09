# Agentic Development Constraints (The "Constitutional" Rules)

## 1. Professional Standards
* **Readability > Brevity**: Avoid "clever" code, deeply nested ternaries, or obscure functional one-liners.
* **Consistency**: Mandatory use of `/patterns`. If an architectural pattern exists, the agent must use it, not invent new logic.
* **Separation of Concerns**: Strictly enforce layer separation (API/Contract -> Business Logic -> Data Worker/DAL).

## 2. Infrastructure & Deployment
* **Container-First**: Every service must contain a `Dockerfile` and be ready to run via `docker-compose`.
* **Lock-in Avoidance**: Code must be infrastructure-agnostic. Logic injected via interfaces. No hardcoded environment-specific configs.
* **Versioning**: Every API endpoint must be versioned (e.g., `/v1/...`).

## 3. Testing & Quality (TDD Mandate)
* **TDD Enforcement**: Every unit of work begins with a failing test.
* **Mocking Default**: External dependencies (Databases, APIs, Message Buses) must be mocked using standard frameworks (e.g., `jest` for TS, `NUnit/Moq` for C#).
* **Coverage**: 100% unit test coverage required. No "happy path" only testing.
* **Integration Tests**: Must include a `tests/integration` folder validating service-to-container connectivity.

## 4. Technical Constraints
* **Language Consistency**: Maintain language consistency within a single service directory (all-TypeScript or all-C#).
* **Structured Logging**: All logs must be in valid JSON format.
* **Health Monitoring**: Every service must implement `GET /health` with internal dependency checks.
* **Dependency Management**: No floating versions. All dependencies must be strictly pinned.

## 5. Agentic Behavior (Enforcement)
* **Strict Adherence**: If the prompt conflicts with these constraints, the Agent must highlight the conflict before proceeding.
* **No Autonomy on Patterns**: If a requested feature lacks a corresponding pattern in `/patterns`, the agent must propose an architectural design first, receive explicit approval, and create the pattern before code generation.

## 6. Architectural Decision Process
* **Architectural Synthesis**: The AI must treat its role as an "Architect's Assistant." For any new sub-system, it must first conduct an interview/discovery session to understand the scope and requirements.
* **ADR Requirement**: All major architectural decisions must be captured in an Architecture Decision Record (ADR) file in `/docs/architecture/adr/`.
* **Standard Format**: ADRs must include: Context, Decision, Consequences, and links to the relevant Template (`/templates`) and Pattern (`/patterns`).