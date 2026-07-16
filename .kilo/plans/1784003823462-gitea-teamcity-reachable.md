# Plan: Make TeamCity config-as-code reachable via a recreated Gitea repo

## Goal
Stand up the Git source-of-truth (Gitea `ai/aiassistant`) populated with the
current code, wire a TeamCity deploy key, and point TeamCity's Versioned
Settings / VCS root at it — so the Kotlin DSL pipeline (`cicd/teamcity/settings.kts`)
is loadable and compiles. This is the **CI/CD-reachable** milestone only.

### Out of scope (call out honestly)
- The pipeline's *execution* steps (Docker build → push → deploy-dev/live in
  `settings.kts`) still require the **host Docker daemon to trust
  `registry.local.test`**. That is fixed only on the **Windows-side Docker
  Desktop** (install `infrastructure/configs/nginx/certs/local.test.crt` into
  `certs.d/registry.local.test/` or add `registry.local.test` to
  `insecure-registries`). Cannot be done from WSL. Not part of this plan.
- Standing up the **live** tier (`deploy-live.sh`) is a separate step.
- Dev tier is already deployed and verified (200s through nginx).

## Preconditions (already true)
- Gitea + TeamCity containers running (infra stack up).
- `cicd/teamcity/settings.kts` present in working tree.
- Local branch `feature/deployment-platform-refactor` has the code to push.

## Steps

### 1. Define Gitea admin credentials
- Add to `.env` (currently absent; seed.sh would default to `ai`/`changeme`):
  `GITEA_ADMIN_USER=ai`, `GITEA_ADMIN_PASS=<strong-secret>`.
- Update `cicd/scripts/gitea-seed.sh` default to read these (already does via
  `${GITEA_ADMIN_USER:-ai}` / `${GITEA_ADMIN_PASS:-changeme}`).

### 2. Make Gitea reachable from the WSL host (where seed + git push run)
- Add to `/etc/hosts`: `127.0.0.1 gitea.local.test`.
  (Container-only DNS via dnsmasq does NOT resolve on the WSL host.)
- Seed talks plain HTTP to Gitea's internal port 3000. Change the script's
  `GITEA_URL` usage so the seed hits `http://gitea.local.test:3000` (or the
  Gitea container IP:3000). Do NOT rely on `:80` (no plain-HTTP listener).
- For the **git push** step, use `https://gitea.local.test/ai/aiassistant.git`.
  Because the cert is self-signed and the host doesn't trust it, either
  (a) temporarily `git -c http.sslVerify=false`, or (b) trust
  `infrastructure/configs/nginx/certs/local.test.crt` for the push. Prefer (a)
  for the one-off push.

### 3. Generate + install the TeamCity deploy key
- `ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/gitea_deploy"` (creates
  `gitea_deploy.pub` — the exact path `gitea-seed.sh` reads).
- `gitea-seed.sh` already registers that pubkey as a read/write deploy key on
  `ai/aiassistant` (idempotent `|| true`).
- In TeamCity, the VCS root must authenticate with the **private** key. Update
  `cicd/teamcity/settings.kts` `GiteaAiAssistant` auth to use a custom private
  key TeamCity parameter, e.g. set `privateKey` to `%gitea-deploy-key%` and add
  a `password`/`sshKey` param `gitea-deploy-key` whose value is the private key
  contents. (Alternatively configure the deploy key in the TeamCity UI.)

### 4. Create org/repo and push code
- Run `bash cicd/scripts/gitea-seed.sh` (idempotent; creates `ai` org +
  `aiassistant` repo with `auto_init`).
- Push current code to Gitea `main`:
  - `git remote add gitea https://gitea.local.test/ai/aiassistant.git` (or reuse).
  - `git fetch gitea main`; reconcile the auto-init commit (e.g.
    `git push gitea feature/deployment-platform-refactor:main --force` since
    the Gitea repo is freshly created and we own it). Confirm
    `cicd/teamcity/settings.kts` is present on `main`.

### 5. Point TeamCity at the repo (load Versioned Settings)
- TeamCity's VCS root (`settings.kts:65-67`) already targets
  `https://gitea.local.test/ai/aiassistant.git`, branch `refs/heads/main` —
  keep as-is after step 4 pushes `main`.
- Load the settings: Administration → Versioned Settings → add Git repo
  (URL above, auth = deploy key from step 3), set "build settings" to
  `cicd/teamcity`, apply. Optionally automate via TeamCity REST
  (`PUT /app/rest/projects/<id>/versionedSettings/repositories`) using admin
  creds — flag as the step most likely to need a manual UI confirmation.
- Set TeamCity `version` in `settings.kts` stays `"2024.12"` to match the
  running `jetbrains/teamcity-server:2024.12` image (verified present).

## Validation
- `curl -fsS http://gitea.local.test:3000/api/v1/version` → 200.
- `curl -fsS -u ai:<pass> http://gitea.local.test:3000/api/v1/repos/ai/aiassistant`
  → shows repo; confirm `cicd/teamcity/settings.kts` exists in it.
- TeamCity "Versioned Settings" page shows the Gitea repo connected with **no
  parse/compile error** for `settings.kts` (the V6 check). If a Kotlin/version
  error appears, fix `settings.kts` (must match TeamCity 2024.12 DSL).
- Confirm a VCS trigger fires on push (or manually trigger a build to prove the
  pipeline is reachable). Note: build/push/deploy steps will FAIL until
  registry trust is configured (see Out of scope) — that failure is expected
  here and is NOT a blocker for "CI/CD reachable".

## Risks
- Manual TeamCity Versioned-Settings load may be required (UI confirmation).
- Gitea on `:3000` vs `:443`: seed/push must use the reachable port; the
  nginx `https://gitea.local.test` path is for browsers, not the seed.
- `--force` push to Gitea `main` is safe only because the repo is freshly
  created; do not force-push if real history exists.
