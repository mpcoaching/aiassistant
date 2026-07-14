# Decisions (ADRs)

## ADR-001 — Archive period for legacy topology
The pre-refactor files in `legacy/` are retained (not deleted) for **2 promotion cycles or 30 days**,
whichever is longer, before removal. Rollback during this window is supported (see
`legacy/README.md`).

## ADR-002 — TeamCity agent uses host Docker socket (Option A)
The agent mounts host `/var/run/docker.sock` (near-privileged). Chosen for a single trusted host:
simplest, no image-cache duplication. Mitigations: single trusted host, network-restricted agent.
**Option B** (dedicated rootless dind executor) is recorded as future multi-tenant hardening and may
be adopted if isolation requirements tighten.

## ADR-003 — One shared LiteLLM instance (not per-env)
A single `litellm` on `platform-network` is reached by both envs via their gateway, differentiated by
per-env virtual keys. Rejected the per-env `litellm`/`dev-litellm` design to reduce state duplication.
If per-env isolation of model routing is later required, add `dev-litellm`/`live-litellm` on the
respective env networks (fallback pattern, documented below).

## ADR-004 — Gateway = the only env↔platform bridge
App→platform traffic is centralized through `dev-platform-gateway` / `live-platform-gateway` (nginx
`stream` for TCP + `http` for client ingress) rather than multi-homing app containers onto
`platform-network`. Preferred over raw multi-homing per user direction (adds a control/audit hop;
latency negligible).

## ADR-005 — Fallback: multi-home a single service (only if proxying is impossible)
If a service genuinely cannot be proxied, it may be attached to BOTH `dev-network` and `live-network`.
Such a service MUST document: (a) why proxying is impossible, (b) that app-to-app traffic remains
impossible (distinct subnets), and (c) that DB roles/credentials block cross-env data access. No
service uses this pattern today.

## ADR-006 — Immutable image promotion
Promoted services use `image:` (registry) with immutable `<git-sha>` tags; `build:` is forbidden for
promoted services. `cicd/scripts/validate-promotion.sh` enforces this. Third-party platform images
(`postgres`, `redis`, `litellm`, `goose`, `qdrant`, …) are pinned to explicit versions/digests before
first promotion.

## ADR-007 — DB isolation via roles + GRANTs
Isolation between `agent_dev` and `agent_live` is enforced at the Postgres role level
(`agent_dev_user` owns only `agent_dev`). No app-code change is needed to add a tenant.

## ADR-008 — Windows path removed from `.env`
`AIASSIST_PATH=C:/Users/...` was removed (breaks inside WSL2 containers). Path-dependent tooling must
derive locations from the repo root at runtime.

## ADR-009 — openhands host-network assumption
`openhands` historically used `OH_USE_HOST_NETWORK=true` (Windows/WSL-specific) and referenced
`litellm:4000` directly. In the isolated topology it is carried as a **disabled** profile with
`OH_USE_HOST_NETWORK=false`, `SANDBOX_RUNTIME_NETWORK=dev-network`, and
`OPENAI_BASE_URL=http://dev-platform-gateway:4000/v1`. Re-enable only after validating sandbox
networking on the target host.
