# Database Strategy

## Current model

A single shared Postgres instance. Databases are named `<tenant>_<env>`; today the tenant is the
platform default (`agent`):

| DB | Owner role | Used by |
|---|---|---|
| `agent_dev` | `agent_dev_user` | dev workflow-engine |
| `agent_live` | `agent_live_user` | live workflow-engine |
| `langgraph_dev` | `langgraph_dev_user` | dev langgraph |
| `langgraph_live` | `langgraph_live_user` | live langgraph |
| `litellm` | `litellm_user` | shared LiteLLM (both envs) |

**Isolation is enforced by roles + GRANTs** (see `platform/db-setup/003_apply_permissions.sql`):
each user owns exactly one DB; `REVOKE ALL ... FROM PUBLIC` removes the default connect grant. Even
though both gateways reach the same Postgres, `agent_dev_user` cannot read/write `agent_live` and
vice-versa.

## Tenant-readiness (naming + prefix conventions only)

No application code is changed for multi-tenancy in this phase. To add a tenant `acme` to live:

1. Add `acme_live` DB + `acme_live_user` (a documented bootstrap SQL, mirroring 001/002/003).
2. Issue an LiteLLM virtual key scoped to that tenant.
3. Parameterise Redis key prefix (`acme:live:*`) and Qdrant collection prefix (`acme_live_*`) per env.
4. Point the tenant's connection string + credentials at the new DB.

Because the design uses connection-string + credentials only, a tenant can move between the options
below **without app-code changes**.

## Future options (trade-offs)

- **A — separate databases in shared Postgres (current):** lowest overhead; weakest isolation (one
  host/process, noisy-neighbor, single failure domain). Good for a single trusted operator.
- **B — dedicated Postgres instance per tenant:** stronger fault/resource isolation; more containers
  + connection management; moderate cost. Introduce a `postgres-acme` service on `platform-network`
  and point the tenant's gateway/DB string at it.
- **C — dedicated database host per enterprise tenant:** strongest isolation/compliance; highest
  cost/ops; for enterprise contracts. Point the tenant's `DATABASE_URL` at the external host.

Migration A→B→C is a connection-string + credentials change only.

## Migrations

Goose migrations under `platform/db-setup/migrations`. Applied per env by `migrate-dev` and
`migrate-live` (separate services so both `agent_dev` and `agent_live` are current). Destructive
migrations require a **restore-tested backup** (Phase 7.5) before applying.
