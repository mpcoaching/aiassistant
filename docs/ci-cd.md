# CI/CD

Continuous delivery is provided by **Gitea Actions** with a stateless runner container. The `delivery` Python CLI implements all capabilities. Gitea is the VCS source of truth.

## Topology

```
Gitea (ai/aiassistant)  ──triggers──▶  Gitea Actions runner  ──invokes──▶  delivery CLI
    (repo + workflows)                     (docker)                     (build/test/deploy)
```

- **Workflows:** thin YAML in `.gitea/actions/workflows/*.yml` that invoke `delivery` subcommands.
- **Runner:** `gitea-runner` container with host Docker socket access.
- **Registry auth:** flows through environment `.env` files or Gitea Actions secrets; never committed to Git.

## Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| `.gitea/actions/workflows/pr.yml` | Pull request to `main` | Lint + unit tests |
| `.gitea/actions/workflows/main.yml` | Push to `main` | Build → publish → deploy dev → validate |
| `.gitea/actions/workflows/promote.yml` | Manual dispatch | Promote dev → live |

## Delivery capabilities

| Capability | CLI subcommand | Purpose |
|---|---|---|
| Build | `delivery build <services>` | Build images with buildx |
| Test | `delivery test <kind>` | Run unit/integration/e2e tests |
| Publish | `delivery publish <services>` | Push images to registry |
| Deploy | `delivery deploy <env> <sha>` | Deploy to environment |
| Validate | `delivery validate <env>` | Health checks + smoke tests |
| Promote | `delivery promote <src> <dst> <sha>` | Promote release between envs |
| Rollback | `delivery rollback <env>` | Redeploy previous tag |
| Status | `delivery status [sha]` | Show release/deployment status |
| Doctor | `delivery doctor` | Verify environment prerequisites |
| Backup | `delivery backup` | Backup runtime state |
| Restore | `delivery restore <archive>` | Restore runtime state |
| Logs | `delivery logs <env>` | Stream deployment logs |

## Bootstrap

1. Bring up infrastructure + platform (`infrastructure/compose.yml`, `platform/compose.yml`).
2. Run `bash cicd/scripts/gitea-seed.sh` to create `ai/aiassistant` + deploy key + webhook (if needed).
3. Ensure `.gitea/actions/workflows/*.yml` are present in the repo.
4. Enable Gitea Actions in Gitea admin settings and register the runner.
