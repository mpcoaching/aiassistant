# TeamCity Build Configuration

This documents the three TeamCity build configurations that implement the
dev → live promotion pipeline. Configure them in the TeamCity UI (or import
via Kotlin DSL) against the `teamcity-server` service. Gitea is the VCS root
(`http://gitea.local.test/ai/aiassistant`), with a VCS trigger on `main` and
on pull requests.

## BC1 — Test & Build

Trigger: Gitea push/PR to `main`.

**Step 1 — Python units**
```bash
docker run --rm -v $PWD:/src -w /src/agentic/src/workflow-runner python:3.12-slim \
  bash -c "pip install -r requirements.txt -r requirements-dev.txt && pytest --cov=. --cov-report=json"
```
Produces `coverage.json`.

**Step 2 — TypeScript units**
```bash
docker run --rm -v $PWD:/src -w /src/agentic/src/control-center-ui node:20 \
  bash -c "npm ci && npx vitest run --coverage --reporter=json"
```
Produces `coverage/coverage-summary.json`.

**Step 3 — Playwright e2e (dev tier)**
```bash
# node:20 (NOT alpine) so `playwright install --with-deps chromium` works
docker compose up -d dev-controller dev-workflow-engine dev-langgraph dev-litellm
docker run --rm -v $PWD:/src -w /src/agentic/src/control-center-ui node:20 \
  bash -c "npm ci && npx playwright install --with-deps chromium && npx playwright test"
docker compose down
```
Produces `playwright-results.xml`.

**Step 4 — Ratchet gate (fail on regression)**
```bash
python infra/ci/check-coverage.py \
  --python agentic/src/workflow-runner/coverage.json \
  --ts     agentic/src/control-center-ui/coverage/coverage-summary.json \
  --e2e    agentic/src/control-center-ui/playwright-results.xml \
  --baseline infra/ci/coverage.baseline.json
```

**Step 5 — Raise baseline (main only, on green)**
Re-run `check-coverage.py` with `--update` and commit the raised
`infra/ci/coverage.baseline.json` back to Gitea via the bot deploy key.

## BC2 — Promote to Dev (snapshot dependency on BC1; auto on `main`)

```bash
docker compose up -d --build dev-controller dev-workflow-engine dev-langgraph dev-litellm
```

## BC3 — Promote to Live (snapshot dependency on BC1; **manual approval**)

```bash
docker compose up -d --build control-center-ui workflow-engine langgraph litellm
```

## Notes
- The agentic `docker compose` runs from the agentic project checkout; the
  TeamCity agent mounts the host `/var/run/docker.sock` so it can run sibling
  build/promotion containers.
- Live promotion is gated by the ratchet: until TS/e2e coverage exists, live
  stays on the last promoted build by design.
