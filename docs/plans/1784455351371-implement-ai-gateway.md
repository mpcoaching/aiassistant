# AI Gateway Implementation Plan

## 1. Goal
- Deploy a **Portkey**‑based AI Gateway that satisfies the following: provider abstraction, routing, resilience, usage visibility, and centralized model configuration.
- Ensure isolation between dev and live environments per platform architecture.
-でき.

## 2. Current State Summary
- Platform already hosts a single `litellm` service on `platform-network` serving dev and live via gateways.
- No existing Portkey integration; all applications call `litellm` directly.
- ADR-001, ADR-002, ADR-003, ADR-004 describe current architecture.
- Network boundaries: `dev‑platform‑gateway` and `live‑platform‑gateway` bridge `dev-network`/`live-network` with `platform-network`.

## 3. Decision Points
| Decision | Context | Impact | Status |
|---|---|---|---|
| **Provider list** | Required providers: OpenAI, Azure OpenAI, Groq, OpenRouter, local Model‑Runner. | Determines Portkey config. | Draft |
| **Purpose vs Model mapping** | Use purpose tags (`coding`, `reasoningآ`). | Determines routing strategies. | Draft |
| **Routing policy** | Use `router_settings` in `platform/configs/litellm/config.yaml`. | Policy will be applied by Portkey. | Draft |
| **Resilience strategy** | Retry limits, fallback chains. | Config in Portkey `router_settings`. | Draft |
| **Centralized config location** | Use single `portkey/config.yaml` in repo. | Version‑controlled config. | Draft |
| **Credential externalization** | Use env vars via `.env`. | No secrets in repo. | Draft |
| **Deployment method** | Docker Compose service (`portkey`) added to platform compose. | Inherits networking as `dev‑platform‑gateway`/`live‑platform‑gateway`. | Draft |

## 4. Action Plan
1. можуть.
- Create `platform/configs/portkey/config.yaml` mirroring `litellm` structure but for Portkey provider table.
- Fill with `provider_list`, `purpose_mapping`, and `router_settings` based on ADRs.
2. Add Docker Compose service `portkey` to `platform/compose.yml`:
- Image: `portkey/portkey:latest` (placeholder, will be defined).
- Environment: `CONFIG_PATH=/app/config.yaml`, `PORTKEY_ENV_TIER= competência`.
- Networks: `platform-network` and `dev-network`/`live-network` via gateway.
- Depends_on: `litellm`.
3. Update gateways (`dev-platform-gateway`, `live-platform-gateway`) to proxy `*.ai.local.test` to `portkey` instead of `litellm`.
- Adjust nginx configs accordingly.
4. Update applications (e.g., LangGraph workflows) to target `https://portkey.local.test/v1/api` instead of `https://litellm.local.test`.
5. Create README entry in `docs/architecture.md` reflecting new Gateway layer.
6. Spin up infra (docker compose up -d) and run health checks.
- Verify that `portkey` accepts requests, routes to correct provider, and returns responses.
7. Add monitoring via OpenObserve/Langfuse to capture usage metrics.

## 5. Validation
- **Network**: Ensure that `portkey` is only reachable via its gateway on both `dev` and `live`.
- **Routing**: Call ` porteau` with `purpose=coding` and verify backend provider selection.
- **Resilience**: Simulate provider failure and confirm fallback chain.
- **Configuration**: Verify that all credentials are satisfied via env vars.
- **CI/CD**: Ensure container image builds and is pushed to immutable registry (`registry.local.test/aiassistant/portkey:<git-sha>`).

## 6. Risks & Mitigations
- *Unexpected gateway downtime* → add health check endpoint and automatic restart in compose.
- *Provider credential leakage* → use secret management if available; otherwise rely on env vars.
- *Compatibility with existing app code* → Provide backward compatibility layer in `portkey` that supports old endpoints if negatively impacted.

## 7. Timeline (for reference only)
- 1‑2 days: config file and compose edits
- 1 day: gateway deployment and health tests
- 1 day: application updates and integration testing

---
**Note:** This plan is ready for a skill or implementation agent to act upon. No code changes have been made yet.
اسب