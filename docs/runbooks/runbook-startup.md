# Runbook — Startup

Bring the platform up in dependency order. Infrastructure first (it owns the four networks).

## Prerequisites
- Docker + Compose v2 installed; host user in the `docker` group.
- `.env` present at repo root (copy from `.env.template` and fill secrets).
- DNS: `dnsmasq` will answer `*.local.test`. If port 53 is taken by `systemd-resolved`, stop it first:
  `sudo systemctl stop systemd-resolved && sudo systemctl disable systemd-resolved` (or point
  `/etc/resolv.conf` at the dnsmasq container).
- Registry CA trusted by the Docker daemon (see `docs/networking.md`) if you will pull/push.

## Steps
```bash
# 1. Infrastructure (creates infrastructure/platform/dev/live networks + control plane + registry)
npm run infra:up
#    or: docker compose -f infrastructure/compose.yml up -d

# 2. Platform (shared services + the two gateways)
npm run platform:up
#    or: docker compose -f platform/compose.yml up -d

# 3. Dev (or Live)
npm run dev:up
#    or: docker compose -f environments/dev/compose.yml up -d
#    live: docker compose -f environments/live/compose.yml up -d
```

## Verify
```bash
docker network ls --filter name=network      # 4 networks present
docker compose -f infrastructure/compose.yml ps
docker compose -f platform/compose.yml ps
curl -fsS https://gitea.local.test          # 200
curl -fsS https://teamcity.local.test       # 200
curl -fsS https://agent.dev.local.test      # 200 (after dev:up)
```

## First-time only
```bash
bash cicd/scripts/gitea-seed.sh             # org/repo/deploy-key/webhook
# In TeamCity: enable Versioned Settings -> Gitea cicd/teamcity
```
