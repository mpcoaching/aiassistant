# Plan: AI Gateway — Portkey Integration

## Goal
Establish a governed AI Gateway capability on `platform-network` that becomes the single integration boundary for LangGraph agents and AI-enabled development tools.

## Architecture Decision (captured in ADRs)
**Decision**: AI-enabled applications integrate through a single AI Gateway abstraction boundary.
**Consequences**: Applications must not contain provider-specific integration logic; routing, resilience, and observability are centralised.
**Alternatives considered**: Direct provider integration per app (rejected — violates boundary); multiple gateways per domain (rejected — increases operational surface).
**Operational impact**: All AI traffic is visible at one point; provider swaps require only gateway config changes; credential management is centralised.

## Solution Decision
Portkey is selected as the implementation of the AI Gateway capability.
**Rationale**: Existing ADR-001 mandates an AI gateway abstraction; Portkey provides provider abstraction, routing, policy enforcement, and observability natively.
**Consequences**: LiteLLM is removed from the platform stack; applications previously targeting LiteLLM are retargeted to Portkey without code changes (same OpenAI-compatible `/v1` surface).
**Operational impact**: Portkey becomes a platform service alongside Postgres/Redis/Qdrant; its config is version-controlled in Git.

## Architecture Boundaries (preserved)
- **Portkey**: provider abstraction, routing, resilience, observability, centralised model config.
- **LangGraph**: agent behaviour, workflows, execution logic. Unchanged.
- **Applications**: domain capability, business rules, user-facing behaviour. Unchanged.
- **Gateway (nginx)**: env↔platform network bridge. Unchanged.

## Consumers (categorised)
| Category | Consumers | Integration notes |
|---|---|---|
| Agent Runtime | LangGraph | Must consume models through Portkey; no provider config in agent code. |
| Developer Tools | Kilo Code, Aider | Must route through Portkey; purpose-based model selection. |
| Experimental / Optional | OpenHands | Route through Portkey when enabled; not a first-class integration target. |

## Current State
- `litellm` runs on `platform-network` at `:4000`, configured by `platform/configs/litellm/config.yaml`.
- Apps already target `OPENAI_API_BASE=http://<env>-platform-gateway:4000/v1` — they are agnostic to the upstream proxy.
- Gateway nginx configs (`platform/configs/nginx/*-gateway.conf`) proxy stream `4000` → `litellm:4000`.
- `.env` holds provider credentials: `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GITHUB_PAT`, `HF_API_KEY`.

## Implementation Sequencing

### Phase 1 — Gateway Foundation
Objective: Deploy Portkey, prove the gateway capability with minimal scope.
Scope:
- Portkey service on `platform-network` exposing `4000`.
- One approved cloud provider (Groq).
- Docker Model Runner (local) as second provider.
- Smoke tests proving end-to-end invocation through Portkey.

Tasks:
1. Create `platform/configs/portkey/config.yaml` using Portkey-native configuration format for:
   - Provider definitions (Groq cloud, Docker Model Runner local).
   - Purpose tags (`coding`).
   - Basic fallback (cloud → local).
   - Timeout/retry settings.
2. Add `portkey` service to `platform/compose.yml`:
   - Image: pinned version (exact image/reference TBD by implementer).
   - Networks: `platform-network` only.
   - Volumes: mount `platform/configs/portkey/config.yaml`.
   - Environment: provider credentials from `.env`.
   - Healthcheck: `/health`.
   - `extra_hosts`: `model-runner.docker.internal:host-gateway` (for local provider resolution).
3. Remove `litellm` service from `platform/compose.yml`.
4. Update `platform/configs/nginx/dev-gateway.conf` and `live-gateway.conf`:
   - Stream upstream `litellm:4000` → `portkey:4000`.
5. Add `PORTKEY_MASTER_KEY` to `.env.template`.
6. Validate:
   - `docker compose -f platform/compose.yml up -d portkey` starts healthy.
   - `curl -fsS http://localhost:4000/health` → 200.
   - Gateway proxies: `curl -fsS http://dev-platform-gateway:4000/v1/models` returns Portkey model list.
   - Smoke request via gateway with `model=coding` returns completion from Groq or local fallback.

### Phase 2 — Consumer Integration
Objective: Integrate first-class consumers to route through Portkey.

#### Story — Integrate LangGraph Runtime
Objective: Ensure LangGraph agents consume AI models through Portkey.
Tasks:
1. Inspect LangGraph runtime configuration for model invocation points.
2. Update any provider-specific configuration to use Portkey endpoint (`http://<env>-platform-gateway:4000/v1`) and Portkey API key.
3. Ensure model selection uses purpose tags, not hard-coded provider model names.
4. Validate:
   - LangGraph does not directly call providers.
   - Agent code contains no provider-specific configuration.
   - Existing workflows continue to operate end-to-end through Portkey.

#### Story — Integrate Kilo Code
Objective: Configure Kilo Code to use Portkey.
Tasks:
1. Inspect Kilo Code plugin/runtime configuration mechanism (environment variables or config file).
2. Configure Kilo Code to call `http://portkey:4000/v1` with `PORTKEY_MASTER_KEY`.
3. Configure Kilo Code model selection to use purpose tags.
4. Validate:
   - Kilo Code connects successfully through Portkey.
   - No direct provider calls in logs.

#### Story — Integrate Aider
Objective: Configure Aider to use Portkey.
Tasks:
1. Update Aider container/command to use Portkey endpoint and API key.
2. Update model argument from `litellm_proxy/coding` to Portkey-compatible identifier.
3. Validate:
   - Aider completes a normal coding workflow through Portkey.
   - No direct provider keys in Aider config.

### Phase 3 — Policy, Resilience, and Observability
Objective: Demonstrate policy-driven model selection and harden the gateway.
Tasks:
1. Expand `platform/configs/portkey/config.yaml` with additional purposes:
   - `reasoning`
   - `general`
   - `private` (Docker Model Runner only)
2. Define routing policies per purpose using Portkey-native routing configuration:
   - Preferred models per purpose.
   - Fallback chains.
   - Retry limits, timeouts, cooldown.
3. Add additional approved cloud providers (one at a time) as separate config changes.
4. Enable/verify observability:
   - Portkey dashboard/usage visibility.
   - Export to existing Langfuse/OTEL if Portkey supports it; otherwise document Portkey-native observability.
5. Validate:
   - Caller specifies purpose and receives appropriate routing without knowing underlying provider.
   - Provider failure triggers fallback.
   - Usage is visible in Portkey dashboard.

## Architecture Artefacts
- Update `docs/decisions.md` with:
  - ADR: AI Gateway abstraction boundary (decision, alternatives, rationale, consequences, operational impact).
  - ADR: Portkey selected as gateway implementation (decision, alternatives, rationale, consequences, operational impact).
- Update `docs/architecture.md` to list `portkey` instead of `litellm` in platform services.
- Update `docs/networking.md` to list `portkey:4000` as a proxied backend on gateways.
- Update `docs/target-state.md` repository structure to reference `platform/configs/portkey/`.
- **Do not create** new documents purely for ceremony. Only update/created where they improve understanding, governance, or maintainability.

## Validation (cross-cutting)
- [ ] `docker compose -f platform/compose.yml up -d` starts `portkey`; `litellm` is absent.
- [ ] `curl -fsS http://localhost:4000/health` → 200.
- [ ] Gateway proxies `4000` correctly on both dev and live.
- [ ] Phase 1: smoke request through gateway returns completion via Groq or local fallback.
- [ ] Phase 2: LangGraph, Kilo Code, and Aider operate through Portkey with no direct provider calls.
- [ ] Phase 3: purpose-based routing works; fallback activates on provider failure; usage visible.
- [ ] Credentials are externalised in `.env`; no secrets in Portkey config file.
- [ ] Reproducible from Git: `git clone` + `docker compose up -d` produces working gateway.

## Risks & Mitigations
| Risk | Mitigation |
|---|---|
| Portkey config format unknown | Implementer must inspect Portkey documentation/schema before writing config; do not blindly translate LiteLLM YAML. |
| Kilo Code provider mechanism is opaque | Inspect `@kilocode/plugin` package for env vars or config keys; document findings. |
| Model Runner host-gateway resolution from Portkey | Add `extra_hosts` to Portkey service in compose. |
| Image promotion immutability | Pin Portkey image to specific version/digest before promotion. |
| Consumer misconfiguration during cutover | Keep cutover isolated per consumer in Phase 2; validate each independently before proceeding. |

## Open Questions
1. **Portkey config schema**: What is the exact Portkey-native YAML/JSON structure for providers, routes, and router settings? (Implementer must verify from Portkey docs/source before writing `config.yaml`.)
2. **Kilo Code configuration mechanism**: Does Kilo Code read `OPENAI_API_BASE`/`OPENAI_API_KEY` from environment, or does it require a `kilo.json` provider section? (Inspect `@kilocode/plugin` runtime to confirm.)
3. **LangGraph model invocation path**: Where exactly does LangGraph construct provider calls? (Inspect `agents/langgraph/src` or related runtime config to identify integration points.)
4. **Portkey image source**: Official Docker Hub image (`portkey/portkey`) or self-hosted build? (Recommend official image, pinned to digest.)
