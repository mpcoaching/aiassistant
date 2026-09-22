# Prisma Application Data Boundary

## A. Purpose of Prisma

Prisma is the **application-owned persistence boundary** for FunnelHub runtime data. It owns mutable application configuration and transactional contact state that is not CMS content and is not part of the Python organisation domain.

Current ownership:
- `Funnel` — application-owned funnel configuration
- `FunnelStep` — application-owned ordered funnel configuration
- `Lead` — application-owned transactional contact/lead state

Prisma is explicitly NOT:
- A CMS content store
- An organisational domain model
- An analytical/reporting store
- A Payload mirror

No existing Python Funnel, FunnelStep, or Lead domain implementation was found outside this Prisma boundary. The models therefore formalise the existing application data shape rather than migrate or duplicate an existing domain abstraction.

## B. Database Ownership

| Database | Purpose | Owner |
|----------|---------|-------|
| `prisma_dev` | Application-owned Funnel configuration and Lead state | Application (Prisma) |
| `payload` | CMS content (articles, pages, pillars, clusters, offers, site_config, etc.) | Payload CMS |

The databases are physically separate. They run on the same PostgreSQL instance (container `postgres_dev`) but on different databases. Prisma connects exclusively to `prisma_dev`. No Prisma operation targets the Payload database.

Connection:
```
PRISMA_DATABASE_URL=postgres://payload:payload@localhost:5433/prisma_dev
```

## C. Model Ownership

### Funnel — Application-owned configuration

Funnel represents a configured marketing/sales journey. It is application-owned configuration because:
- Funnels are created, updated, and deleted through application workflows
- Their steps and business identity are mutable application configuration
- They have a lifecycle independent of CMS content
- A funnel is not a content page or article

**Classification:** application-owned configuration, not CMS content, organisation-domain state, or a derived read model.

**Fields:**
- `id` (String, PK) — application-generated unique identifier
- `name` (String, NOT NULL) — display name
- `slug` (String, NOT NULL, UNIQUE) — business identifier for URL/routing references
- `description` (String, nullable) — human-readable purpose
- `createdAt` (DateTime, NOT NULL) — creation timestamp
- `updatedAt` (DateTime, NOT NULL) — last modification timestamp

**Relationships:** One Funnel → many FunnelSteps; One Funnel → many Leads

### FunnelStep — Application-owned ordered configuration

FunnelStep represents an ordered stage within a Funnel. It is application-owned configuration because:
- Steps define the funnel journey
- Order is meaningful and mutable
- Steps belong exclusively to a Funnel and have no standalone existence

**Classification:** application-owned configuration, not a workflow-engine step, event, CMS page, or organisation-domain entity.

**Fields:**
- `id` (String, PK) — unique identifier
- `name` (String, NOT NULL) — stage name
- `order` (Int, NOT NULL) — position within the funnel
- `funnelId` (String, NOT NULL) — parent funnel reference (FK → Funnel.id)
- `createdAt` (DateTime, NOT NULL) — creation timestamp
- `updatedAt` (DateTime, NOT NULL) — last modification timestamp

**Constraint:** `unique(funnelId, order)` — step order is unique within a funnel, not globally. This correctly expresses that Funnel A can have a step at position 1 and Funnel B can independently also have a step at position 1.

**Relationships:** Many FunnelSteps → one Funnel (CASCADE delete)

### Lead — Application-owned transactional contact state

Lead represents a prospective business contact that may be associated with a Funnel. It is application-owned transactional state because:
- It records a real contact and current lifecycle status
- It can exist before funnel assignment
- It is neither CMS content nor organisation-domain state

**Classification:** application-owned transactional state, not a person identity, interaction event, CMS record, or organisation-domain entity.

**Fields:**
- `id` (String, PK) — unique identifier
- `email` (String, NOT NULL, UNIQUE) — primary business identifier
- `firstName` (String, nullable)
- `lastName` (String, nullable)
- `company` (String, nullable)
- `source` (String, nullable) — where the lead originated
- `funnelId` (String, nullable) — optional funnel association (FK → Funnel.id, `ON DELETE SET NULL`)
- `status` (String, NOT NULL, default: "new") — lifecycle status
- `createdAt` (DateTime, NOT NULL)
- `updatedAt` (DateTime, NOT NULL)

**Key decision:** `funnelId` is nullable because a Lead may exist in the system before being assigned to a funnel (e.g., captured via a general form, or waiting for qualification). A Lead does NOT have to belong to exactly one Funnel at creation time.

**Relationships:** Many Leads → one Funnel (nullable, `ON DELETE SET NULL`, `ON UPDATE CASCADE`). Deleting a Funnel preserves its Lead records and clears their optional `funnelId`.

### `_prisma_migrations` table

Managed by Prisma. Records applied migrations. Not an application model.

## D. Funnel Semantics

A Funnel is a configured conversion journey with ordered steps and optionally associated leads.

**What Funnel is:**
- Application-owned configuration for an ordered conversion journey
- A container reference for currently associated leads
- An application entity with a create/read/update/delete lifecycle

**What Funnel is NOT:**
- A CMS content type (not in Payload)
- An organisational entity (not in the organisation domain)
- A workflow engine
- A state machine or execution-history model

**Naming rationale:** "Funnel" describes the marketing/sales concept where leads enter at the top and progress through stages toward conversion. This is the domain term used by the business.

## E. FunnelStep Semantics

A FunnelStep represents a single ordered stage in a funnel journey.

**What FunnelStep is:**
- An ordered position within a specific funnel
- A stage that leads pass through (descriptively, not as a workflow step)
- An application configuration element

**What FunnelStep is NOT:**
- A workflow engine step
- An event or event sourcing entry
- A page (though it may correspond to a page in some implementations)
- An offer or action (those may be associated externally)

**Ordering constraint:** `unique(funnelId, order)` ensures that within a single funnel, no two steps share the same order position. Steps in different funnels may have the same order number without conflict. This matches the semantic expectation that funnel ordering is local to each funnel.

## F. Lead Semantics

A Lead represents a prospective business contact that has entered or may enter a funnel.

**What Lead is:**
- A contact/application record
- Current state captured at a point in time (`status` field)
- Optionally associated with at most one Funnel in the current model

**What Lead is NOT:**
- A durable person identity
- An event or historical interaction record
- An organisation-domain entity
- A workflow participant or journey-history model

**Funnel relationship:** `funnelId` is nullable so a Lead can exist before funnel assignment. The current schema does not represent multiple simultaneous funnel associations or multiple journeys for one email. Adding those capabilities requires a deliberate model change based on actual requirements; it is not implied by the current boundary.

**Email uniqueness:** `email` has a unique constraint and currently acts as the natural business key. This is a product decision suitable for the minimal model, not a universal person-identity rule.

## G. Payload ↔ Prisma Boundary

### Current state

The deployed Payload CMS owns editorial/content configuration in the separate `payload` database. Payload collection definitions are outside the inspected repository boundary, so this report does not treat them as Prisma models or duplicate them here.

Prisma (`prisma_dev`) owns the FunnelHub application configuration and transactional state defined by the three models in this boundary.

### What crosses the boundary

At this stage, **no integration exists** between Payload and Prisma. The boundary is:

**Payload (source of truth for content):**
- Defines content that may reference funnels (e.g., a page describing a funnel)
- Contains no references to Prisma tables
- Uses its own `payload_migrations` for schema evolution

**Prisma (source of truth for application-owned data):**
- Stores funnel configuration and state
- Contains no references to Payload collections
- Uses its own `_prisma_migrations` for schema evolution

### Future integration (deferred)

If Payload content needs to reference a Prisma funnel (or vice versa), the cross-reference would use **slug** (Funnel.slug) as the stable business identifier, not database IDs. For example:
- A Payload article could store `funnelSlug: "sales-funnel"` as a string
- Prisma would look up the Funnel by slug when needed

No such integration is currently implemented.

## H. Identifier Strategy

### Prisma primary-key type
- All Prisma model `id` fields are `String` (not auto-increment Integer)
- IDs are application-generated (UUID or nanoid-style) at creation time
- The database does not enforce a specific ID format via default

### Payload ID type
- Payload uses its own ID system (document IDs)
- Not directly comparable to Prisma IDs

### Public/stable identifiers
- `Funnel.slug` — stable business identifier for a funnel (used for URLs, references)
- `Lead.email` — stable business identifier for a lead (natural key)

### Slugs as business identifiers
- `Funnel.slug` is the business identifier for funnels
- It is unique, human-readable, and stable across the funnel lifecycle
- External references to a funnel should use `slug`, not `id`

### External identifiers
No dedicated external identifier is necessary at this stage. `slug` (for funnels) and `email` (for leads) serve as stable business identifiers where cross-system references are needed in the future.

**Principle applied:** `persistence identity ≠ business identity`
- `id` = persistence identity (internal, arbitrary)
- `slug`/`email` = business identity (stable, meaningful externally)

## I. Migration Strategy

### Canonical workflow
```
prisma/schema.prisma
    → prisma migrate dev --name <description>
    → prisma/migrations/<timestamp>_<name>/migration.sql
    → prisma_dev database
    → prisma generate (regenerate Prisma Client)
```

### Current migration
- `prisma/migrations/20260915083844_init/migration.sql` — initial schema
- Applied and recorded in `_prisma_migrations` table
- Checksum: `a96f6d276dbcf97aa745a3139bddfbd844fe4c4006b6fe88f2e448705e18c7d9`
- Applied: `2026-09-15T08:38:44Z`

### Development reset
To reset the development database:
1. Drop the `prisma_dev` database
2. Run `prisma migrate deploy` to recreate schema
3. Run `prisma generate` to regenerate client

### Production migration strategy (deferred)
Production deployment will require:
- Review-approved migrations
- Backward-compatible schema changes
- Prisma Client regeneration in CI/CD pipeline
- Rollback procedures

This is deferred. No production database exists.

## J. Environment Safety

### PRISMA_DATABASE_URL verification

- The ignored local `.env` contains `PRISMA_DATABASE_URL=postgres://payload:payload@localhost:5433/prisma_dev`
- `.env.template` now declares the same development placeholder so a fresh checkout has an explicit Prisma configuration
- The URL points exclusively to the `prisma_dev` database on port `5433`
- The Payload database on port `5432` is not referenced by Prisma configuration

### `.env` handling

- `.env` is ignored by Git and contains no production credentials
- `.env.template` is tracked and contains only development-safe placeholder values
- Prisma reads the URL through `env("PRISMA_DATABASE_URL")`; it does not auto-load the repository root `.env`

For local validation, source the root environment before running Prisma commands from `prisma/`:

```bash
set -a && source ../.env && set +a
npm run db:validate
npm test
```

### Accidental database mismatch prevention

- The schema contains no hardcoded connection string
- If `PRISMA_DATABASE_URL` is unset, Prisma fails with P1012 rather than silently selecting another database
- The port (`5433`) and database name (`prisma_dev`) provide defence in depth against targeting Payload
- No application startup code exists yet, so runtime URL-policy validation remains deferred

## K. Organisation Boundary

The organisation architecture (packages/organisation) has its own domain model:
- Actor, Role, Capability, CapabilityAssignment, Work
- These are defined in Python, managed through OrganisationControlPlane
- They are stored in the `AGENT_DEV_DB_NAME` / `AGENT_LIVE_DB_NAME` databases

**No overlap with Prisma:**
- No Actor, Capability, Assignment, Work, Capacity, Value, or Decision entities exist in Prisma
- No Prisma model duplicates any organisation-domain concept
- If funnel functionality eventually needs organisational information (e.g., "which Actor owns this funnel"), that would be an integration/read requirement, not a model duplication

## L. Current Limitations

1. **No application consumer yet:** The Prisma Client is configured and tested, but no production application module imports it. The tests establish persistence behaviour; they are not evidence of a completed FunnelHub feature.

2. **No Payload integration:** No code currently passes identifiers or data between Payload and Prisma.

3. **No runtime environment-policy check:** The schema fails safely without a URL, but there is no application startup check enforcing a `prisma_*` database-name policy.

4. **No indexed Lead funnel lookup:** PostgreSQL does not automatically index the nullable `Lead.funnelId` foreign key. An index should be added only when an actual query pattern demonstrates the need.

5. **Minimal step content:** Steps currently contain only `name` and `order`. Descriptions or action configuration would require a future requirement and migration.

6. **Hard delete:** Deleting a Funnel hard-deletes its steps and clears Lead associations. Audit/soft-delete behaviour is not represented.

## M. Deferred Decisions

1. **Lead funnel cardinality:** The current model supports zero or one Funnel per Lead. Multiple funnel associations or journey history require a new model based on requirements.

2. **Lead status lifecycle:** Currently a free-form `String`. A controlled enum should be introduced only when valid transitions are known.

3. **FunnelStep content:** Additional step configuration remains deferred.

4. **Payload↔Prisma integration:** Deferred until a concrete cross-system data flow exists.

5. **Soft delete vs hard delete:** Current behaviour is hard delete for FunnelStep and `SET NULL` for Lead.

6. **Production migration strategy:** Production deployment will require reviewed, backward-compatible migrations and a rollback plan. No production database exists.

7. **Query indexes:** Add indexes only from observed query requirements.

8. **Prisma version upgrade path:** The project currently targets Prisma 6.19.3.

## N. Recommended Next Step

Do not expand the schema or build features solely because persistence is available. The next evidence-based step is the smallest FunnelHub application use case that consumes the existing Client. Before that slice:

1. Define the use case's source-of-truth and lifecycle responsibilities.
2. Add a runtime environment-policy check only if application startup code is introduced.
3. Add indexes only for queries required by that use case.
4. Revisit Lead cardinality only if the use case requires multiple funnel associations or journey history.
5. Run `prisma generate` and migration checks in CI for the Prisma project.

---

## Report Summary

### Final Prisma Model List

| Model | Table | Owner | Type |
|-------|-------|-------|------|
| Funnel | Funnel | Application | Configuration |
| FunnelStep | FunnelStep | Application | Ordered configuration |
| Lead | Lead | Application | Transactional contact state |

### Ownership of Each Model

- **Funnel**: Application-owned configuration. Created, managed, and deleted through application workflows. Not CMS content.
- **FunnelStep**: Application-owned ordered configuration. Belongs exclusively to a Funnel and is cascade-deleted with it.
- **Lead**: Application-owned transactional contact state. It may be unassigned; deleting a Funnel preserves it and clears `funnelId`.

### Payload ↔ Prisma Boundary

- Payload: CMS source of truth for content, configuration, versioning. Database: `payload`.
- Prisma: Application-owned Funnel configuration and Lead state. Database: `prisma_dev`.
- No integration currently exists. Future cross-references would use `slug`/`email` as stable identifiers.

### Identifier Strategy

- Prisma PKs: String IDs (application-generated)
- Business identifiers: `Funnel.slug`, `Lead.email`
- `slug` is the cross-system reference mechanism (deferred integration)

### Migration Status

- Migration `20260915083844_init` applied to `prisma_dev`
- Recorded in `_prisma_migrations` with checksum
- Schema, generated Client, migration SQL, and live database are consistent

### Tests Created

1. `prisma/tests/prisma_boundary.test.ts` — CRUD, composite ordering, uniqueness, optional association, referential rejection, delete behaviour, generated Client access, and connection tests
2. `prisma/tests/isolation.test.ts` — multi-Funnel isolation for ordering, updates, deletes, and Lead identity

### Test Results

Validation completed with the existing development environment:

```bash
set -a && source ../.env && set +a
npm run db:validate
npx prisma migrate status
npm test
npx tsc --noEmit
```

Results:
- Prisma schema validation: passed
- Migration status: up to date
- Fresh temporary-database migration: passed
- Boundary and isolation tests: **25 passed**
- TypeScript type-check: passed
- Live database FK verification: `FunnelStep` uses `ON DELETE CASCADE`; `Lead` uses `ON DELETE SET NULL`

The root `.env` is intentionally ignored and is not loaded automatically by Prisma, so local commands must source it explicitly or receive the variable from the execution environment.

### Exact Files Changed

**New files:**
- `prisma/schema.prisma` — Prisma schema with Funnel, FunnelStep, and Lead models
- `prisma/migrations/20260915083844_init/migration.sql` — initial schema and referential actions
- `prisma/src/index.ts` — Prisma Client singleton with development global caching
- `prisma/tests/prisma_boundary.test.ts` — persistence, constraint, ordering, referential, and delete-behaviour tests
- `prisma/tests/isolation.test.ts` — multi-Funnel isolation tests
- `prisma/package.json` — Prisma, Vitest, and TypeScript tooling
- `prisma/tsconfig.json` — strict TypeScript configuration for source and tests
- `prisma/vitest.config.ts` — isolated single-fork test configuration
- `docs/architecture/prisma_application_boundary.md` — this boundary report

**Modified files:**
- `.env.template` — added the ignored-local-env Prisma development placeholder

### Production Changes

No application feature code was added. This phase establishes the persistence boundary, schema discipline, tests, and documentation. The only tracked configuration change is the development placeholder in `.env.template`; the actual connection remains in ignored `.env`.

The live `prisma_dev` database was inspected read-only. A separate temporary database was created, migrated, validated, and removed to prove that the committed migration reproduces the intended FK behaviour.

### Deferred Decisions

1. First evidence-based application consumer
2. Payload↔Prisma integration only if a concrete data flow emerges
3. Lead status lifecycle
4. FunnelStep content expansion
5. Soft delete/audit behaviour
6. Production migration and rollback strategy
7. Query-driven indexes
8. Prisma upgrade path

### Recommended Next Increment

Implement the smallest real FunnelHub use case that consumes Prisma. Keep the schema unchanged unless that use case proves a missing lifecycle requirement. Its definition of done should include application-level environment checks, generated Client build validation, migration deployment validation, and tests for the actual read/write behaviour.

### Final Status: GO

The Prisma application data boundary is established. Funnel and FunnelStep are application-owned configuration, while Lead is application-owned transactional contact state. Payload and Prisma remain on separate databases with no model duplication or cross-database foreign keys. The schema, migration, generated Client, tests, environment template, and architecture documentation are internally consistent. No application feature was added and production databases remain untouched.