# Legacy Archive

These files are the **pre-refactor** deployment topology. They are archived (not
deleted) so the platform can be rolled back during the defined stable period
(2 promotion cycles or 30 days — see `docs/decisions.md` ADR-001).

## What was archived
| Legacy path | Replaced by |
|---|---|
| `legacy/docker-compose.platform.yml` | `infrastructure/compose.yml` + `platform/compose.yml` |
| `legacy/docker-compose.yml` | `environments/dev/compose.yml` + `environments/live/compose.yml` |
| `legacy/docker-compose.dev.yml` | `environments/dev/laptop.yml` |
| `legacy/ai-assistant-infra/` | `infrastructure/configs/*` + `platform/configs/*` (copied) |
| `infra/ci/*` (moved) | `cicd/*` |
| `infra/wait_for.py` (kept) | still at `infra/wait_for.py` (mounted into apps) |
| `agentic/src/control-center-ui`, `agentic/src/workflow-runner` | `agents/control-center-ui`, `agents/workflow-runner` |

## Key differences vs the new model
- **Networks:** legacy used one flat shared `ai_net` (+ `monitoring-net`). New model uses four
  isolated networks (`infrastructure-network`, `platform-network`, `dev-network`, `live-network`)
  with controlled gateway crossings.
- **LiteLLM:** legacy ran per-env `litellm` + `dev-litellm`. New model runs ONE shared `litellm`
  on `platform-network`, reached by both envs via their gateway with per-env virtual keys.
- **Routing:** legacy nginx had a flat `*.local.test` set and a duplicate `qdrant` block, and the
  dev UI was reached directly on `:8443`. New nginx uses explicit `*.dev.local.test` / `*.live.local.test`
  upstreams through the per-environment gateways.
- **Images:** legacy built locally with `build:` everywhere. New model promotes immutable
  `registry.local.test/aiassistant/<svc>:<git-sha>` from dev → live.
- **DB naming:** legacy `aiassistant_dev`/`aiassistant_live`. New `agent_dev`/`agent_live`.
- **CI:** legacy TeamCity was configured manually (BC1–BC3). New model is Kotlin-DSL CaaS
  (`cicd/teamcity/settings.kts`, 10 build configs).

## Rollback
If a regression forces a revert during the stable period:
1. `docker compose -f infrastructure/compose.yml -f platform/compose.yml down` (new stacks).
2. `git mv legacy/docker-compose*.yml .` and `git mv legacy/ai-assistant-infra .` to restore the
   flat topology, OR simply run the legacy files directly:
   `docker compose -f legacy/docker-compose.platform.yml up -d` then
   `docker compose -f legacy/docker-compose.yml up -d`.
3. The `agent_dev`/`agent_live` databases remain compatible (the new bootstrap still creates them);
   legacy services will connect once `ai_net` is re-created. Note: legacy expects `aiassistant_dev`
   DB names — run the legacy `db-setup` or rename back if you need the old DBs.

After the stable period passes with green promotions, these files may be removed entirely.
