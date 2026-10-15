# Plan: Portkey Routing + Langfuse/OpenObserve Integration

## Target Architecture

```
Client
  → CoreDNS
  → outer nginx
  → platform gateway
  → Portkey
  → AI providers

Application/LLM telemetry
  → OTel collector
  → OpenObserve

LLM tracing/cost attribution
  → Langfuse (only if a supported Portkey integration path exists)
```

---

## 1. DNS and CoreDNS

CoreDNS must return the VM LAN IP to external clients. Do not use `127.0.0.1`.

### Required records
```
gateway.local.test  → 192.168.1.238
lf.local.test       → 192.168.1.238
portkey.local.test  → 192.168.1.238
```

`192.168.1.238` is the VM's actual IP on the LAN. Fedora, Windows, and other LAN clients querying CoreDNS cannot reach `127.0.0.1` on the VM.

### Validation

From Fedora:
```bash
dig gateway.local.test +short
curl -k https://gateway.local.test/
```

From Ubuntu VM:
```bash
dig gateway.local.test +short
curl -k https://gateway.local.test/
```

Both must resolve to `192.168.1.238` and route successfully.

---

## 2. Portkey Routing Separation

### gateway.local.test
- Stable AI API endpoint.
- nginx `server_name gateway.local.test` proxies to `portkey:4000`.

### portkey.local.test
- Reserved for a possible future Portkey UI/admin interface.
- CoreDNS resolves it to `192.168.1.238`.
- **Do not create nginx routing for `portkey.local.test` until the running container proves a UI or supported endpoint exists.**

### Portkey UI Discovery (gate)
Before adding any nginx route for `portkey.local.test`, inspect the actual running container:
```bash
docker exec <portkey-container> ss -lntp
docker exec <portkey-container> curl -s localhost:8787 || true
docker exec <portkey-container> curl -s localhost:4000
```

The running deployment is the source of truth, not documentation assumptions.

Only if a real UI or supported endpoint exists at 8787 (or another port), create the corresponding nginx server block.

---

## 3. Portkey → Langfuse Telemetry Discovery

Do not assume that setting `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, or `LANGFUSE_HOST` automatically enables Langfuse tracing.

### Discovery steps (before implementation)
1. Inspect Portkey's running container for Langfuse SDK imports or configuration references:
   ```bash
   docker run --rm portkeyai/gateway:1.15.2 sh -c "grep -ri langfuse /app/ || true"
   ```
2. Review Portkey documentation for supported telemetry backends.
3. Confirm whether Portkey requires explicit config entries in `config.json`, environment variables only, or a separate sidecar/middleware.

### Implementation decision gate (after discovery)

| Path | Condition | Action |
|---|---|---|
| **A — Native Langfuse** | Portkey documents native Langfuse integration via env vars or config | Add the documented Portkey mechanism |
| **B — OpenTelemetry** | Portkey emits OTLP traces | Route traces through existing `otel-collector`; configure Langfuse OTLP ingestion if appropriate |
| **C — Middleware/proxy** | Neither native nor OTLP support exists | Document as a future architecture decision; do not add unsupported configuration |

**Do not add `LANGFUSE_*` environment variables or config entries until the correct path is confirmed.**

### What this section will produce (once validated)
- LLM traces + token usage visible in Langfuse (`lf.local.test`).
- Cost analysis available in Langfuse's built-in dashboard.

---

## 4. OpenObserve and OTel

### Principle
Validate first. Extend second.

### Step 1: Validate existing OTel ingestion (mandatory)
1. Deploy the platform stack.
2. Generate Portkey API traffic (`/v1/chat/completions`).
3. In OpenObserve (`oo.local.test`), confirm:
   - The Portkey test call appears in the **trace** stream.
   - Existing log ingestion works (check for any log data from the running containers).
4. If OpenObserve already receives sufficient observability data via OTLP, **do not add the Docker `filelog` receiver**.

### Step 2: Add Docker filesystem scraping only if required
If and only if Step 1 reveals missing log coverage:
- Add a `filelog` receiver to `platform/configs/otel/otel-collector.config.yaml` that scrapes `/var/lib/docker/containers/*/*.log`.
- Exclude Docker JSON metadata fields.
- Add service name labels from container labels.
- Route through the existing `batch` processor to `otlphttp` exporter.
- The `/var/lib/docker/containers` path is bind-mounted from the host.

Preferred order: application telemetry before container filesystem scraping.

---

## 5. Remove Docker Model Runner Coupling

### Files to update
- `platform/compose.yml`
- `platform/configs/portkey/config.json`
- `environments/dev/compose.yml`
- `environments/live/compose.yml`

### Actions
- Remove `extra_hosts: model-runner.docker.internal:host-gateway` from `portkey`, `dev-workflow-engine`, `dev-langgraph`, `workflow-engine`, `langgraph`.

### Config interpolation
**Do not blindly insert `${AI_PROVIDER_BASE_URL}` into JSON unless Portkey explicitly supports environment variable expansion in JSON config.**

Preferred approach:
- Use `config.template.json` with `${AI_PROVIDER_BASE_URL}` placeholder.
- Generate `config.json` during container startup using the existing `entrypoint.sh` pattern (Node or `envsubst`).
- This is the pattern already used for `${GROQ_API_KEY}` etc. in `platform/configs/portkey/entrypoint.sh`.

If Portkey is confirmed to support native JSON env expansion, use that instead.

### .env
- Add `AI_PROVIDER_BASE_URL=` (empty by default).
- Document that setting it to e.g. `http://ollama:11434/v1` or `https://api.openai.com/v1` activates that provider through Portkey without any code change.

---

## 6. Compose Ownership Rules

### Root infrastructure compose (`infrastructure/compose.yml`) owns
- Networks: `infrastructure-network`, `platform-network`, `dev-network`, `live-network`, `ai_net`
- Shared volumes: `gitea_data`, `registry_data`
- Infrastructure services: `nginx-proxy`, `dns` (CoreDNS), `gitea`, `registry`, `gitea-runner`

### Child compose files own services only
- `platform/compose.yml` — platform services on `platform-network`
- `environments/dev/compose.yml` — dev services on `dev-network`
- `environments/live/compose.yml` — live services on `live-network`

Child composes may attach to existing external networks. They must not redefine networks or shared volumes.

### Validation
```bash
docker compose -f infrastructure/compose.yml config
docker compose -f platform/compose.yml config
docker compose -f environments/dev/compose.yml config
docker compose -f environments/live/compose.yml config
```

Confirm no child compose declares networks or shared volumes as owned resources.

---

## 7. Migration Checkpoints

Execute in order. Do not proceed to the next checkpoint until the current one passes.

### Checkpoint 1 — DNS
**Success criteria:**
```bash
dig gateway.local.test +short    # → 192.168.1.238
dig lf.local.test +short         # → 192.168.1.238
```
Works from:
- Ubuntu VM
- Fedora workstation
- Windows host

### Checkpoint 2 — Gateway routing
**Success criteria:**
```bash
curl -k https://gateway.local.test/
# → Portkey "AI Gateway says hey!" response
```

### Checkpoint 3 — Provider routing
**Success criteria:**
```bash
curl -k https://gateway.local.test/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
# → 200 with completion text
```

### Checkpoint 4 — Observability
**Success criteria:**
- OpenObserve receives supported telemetry traces.
- Langfuse receives traces only if a supported Portkey integration path was confirmed in §3.

---

## 8. Implementation Task List

Dependency-ordered. Do not skip discovery gates.

| Step | Phase | File | Action | Validates |
|---|---|---|---|---|
| 1 | Fix | `infrastructure/compose.yml` | Remove `platform-network` from CoreDNS networks | CoreDNS resolves from WSL2 + Fedora |
| 2 | Fix | `infrastructure/configs/nginx/nginx.conf` | Rename `portkey.local.test` → `gateway.local.test` (4000); add `lf.local.test` (3000) | nginx -t passes; `curl -k https://gateway.local.test` returns Portkey response |
| 3 | Fix | `infrastructure/configs/coredns/Corefile` | Add `gateway.local.test`; retain `portkey.local.test` and `lf.local.test` | `dig gateway.local.test` returns `192.168.1.238` |
| 4 | Fix | `platform/compose.yml` | Expose port 8787; remove `extra_hosts`; add Langfuse env vars **only after discovery** | Portkey healthcheck passes |
| 5 | Discovery | — | Inspect Portkey UI on 8787; inspect Langfuse integration support; confirm JSON env expansion support | Discovery report |
| 6 | Fix | `platform/configs/portkey/config.json` + `entrypoint.sh` | Apply config interpolation method based on discovery outcome | Portkey starts without error |
| 7 | Validate | `platform/configs/otel/otel-collector.config.yaml` | Validate existing OTLP ingestion; add Docker `filelog` receiver only if logs are missing | Traces appear in OpenObserve |
| 8 | Fix | `.env` | Comment stale LiteLLM keys, `OPENCODE_LITELLM_URL`, `OPENAI_API_KEY=${LITELLM_MASTER_KEY}` | No compose service fails to resolve env vars |
| 9 | Fix | `environments/dev/compose.yml`, `live/compose.yml` | Remove `extra_hosts: model-runner.docker.internal:host-gateway` | App containers start cleanly |
| 10 | Validate | All | `docker compose up -d` in order: infrastructure, platform, dev, live | All healthchecks pass; routing works |
| 11 | Validate | All | Functional Portkey validation (§8) | All endpoints respond; traces flow |

---

## 9. Final Acceptance Criteria

### Required
- `gateway.local.test` routes AI API traffic.
- Existing applications do not require endpoint changes.
- CoreDNS works consistently across Ubuntu, Fedora, and Windows.
- Portkey no longer references Docker Model Runner.
- Compose ownership boundaries are preserved.
- OpenObserve remains functional.

### Conditional
- `portkey.local.test` exposes a UI only if one is confirmed by discovery.
- Langfuse receives Portkey traces only through a supported integration method.

---

## 10. Out of Scope
- Portkey enterprise control plane.
- Changing the OTel/Observe backend.
- Per-environment Portkey instances.
- Adding nginx routing for `portkey.local.test` until discovery confirms a UI.
