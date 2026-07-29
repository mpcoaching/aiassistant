# Configuration Manager Redesign Plan

**Status**: Draft  
**Date**: 2026-07-29  
**Goal**: Replace the existing Configuration Manager library with a platform-hosted service that resolves, caches, validates, and delivers runtime contracts to capabilities.

---

## 0. What Gets Discarded

The entire current `packages/configuration/` library implementation is discarded. This includes:

| File | Why |
|------|-----|
| `packages/configuration/src/configuration/manager.py` | Library-style manager couples providers, contracts, and validation |
| `packages/configuration/src/configuration/providers/dotenv.py` | Provider conflates source with architecture; .env is just one source |
| `packages/configuration/src/configuration/providers/registry.py` | Conflates provider with validator; performs docker login |
| `packages/configuration/src/configuration/providers/__init__.py` | Couples provider interface with result types |
| `packages/configuration/src/configuration/providers/exceptions.py` | Result types tied to old architecture |
| `packages/configuration/src/configuration/contracts/base.py` | Contracts are Pydantic models; no HTTP/Redis awareness |
| `packages/configuration/src/configuration/contracts/v1/*.py` | Old contracts need replacement under new model |
| `packages/configuration/pyproject.toml` | Old library packaging |
| `packages/configuration/tests/` | Old test suite for discarded architecture |
| `packages/ci_worker/src/ci_worker/configuration.py` | Tightly coupled RegistryConfiguration contract |
| `packages/platform/src/platform/bootstrapper.py` | Direct ConfigurationManager library usage |
| `packages/configuration/src/configuration/contracts/` | Contract definitions must move to platform-owned `contracts/` directory |

The `packages/ci_worker/` and `packages/platform/` packages are retained but their contracts and bootstrapper are rewritten under the new architecture.

Old contract files in `packages/configuration/src/configuration/contracts/` must be relocated to platform-owned `contracts/` directory structure with `contract.yaml` and `mapping.yaml` files alongside each version.

---

## 1. New Architecture Overview

The Configuration Manager is a **platform service** — a Docker container that owns its own bootstrap. It does NOT use itself to configure itself.

```
                 Platform Bootstrap

                       |
                       v

          +-----------------------------+
          | Configuration Manager        |
          |                                |
          | Source Resolution            |
          | Mapping                      |
          | Validation                   |
          | Redis Cache                  |
          | HTTP API                     |
          +-----------------------------+
                       |
          +------------+-------------+
          |                          |
          v                          v

 Source Providers              Contract Validators
 EnvFileProvider               StructuralValidator
 JsonConfigProvider            RuntimeValidator
 LocalConfigStoreProvider

          |
          v

 Raw Configuration Values

          |
          v

 Mapping Adapter

          |
          v

 Contract Definition
        |
        v
Mapping Adapter
        |
        v
Resolved Contract
        |
        v
Validation
        |
        v
Validated Contract

          |
          v

 Validated Contract

          |
          v

 Capability Bootstrap

          |
          v

 CI Worker Runner
```

**Key boundaries**:
- Source Providers retrieve raw values only. They know nothing about contracts, capabilities, or validation.
- Mapping Adapter converts raw values into contract instances using predefined contract definitions. It does not validate.
- Validators prove that a resolved contract is usable. They are associated with contracts, not with providers.
- Configuration Manager orchestrates but owns no business logic.
- Capabilities consume validated contracts. They do not know how contracts were created.

---

## 2. Contract Definitions (Predefined Artifacts)

Contracts are **predefined artifacts owned by the platform architecture**. They are NOT generated dynamically and NOT defined as Python models in the Configuration Manager service.

### 2.1 Location

Contracts are platform-owned artifacts. They live outside the Configuration Manager package.

```
contracts/
    ci-worker/
        v1/
            contract.yaml
            mapping.yaml
```

The Configuration Manager receives the contract location as configuration:

```yaml
contracts:
  path: /etc/platform/contracts
sources:
  path: /etc/platform/sources.yaml
```

The Configuration Manager loads contract definitions from `CONTRACTS_PATH` and source configuration from `SOURCES_CONFIG_PATH` at startup. It does not own them.

The physical layout on disk is:

```
/etc/platform/
    contracts/
        ci-worker/
            v1/
                contract.yaml
                mapping.yaml

    sources.yaml
    config.json
    config.d/
```

`contracts/` defines what capabilities require. `sources.yaml` defines where values are retrieved from. `config.json` and `config.d/` contain the actual configuration values. These are separate concepts and must not share the same path.

### 2.2 Contract Example

`contracts/ci-worker/v1/contract.yaml`:

```yaml
name: ci-worker
version: v1

requirements:
  source_control:
    endpoint:
      required: true
    authentication:
      required: true
  runner:
    labels:
      required: true

validators:
  - required-fields
  - endpoint-connectivity
  - authentication
```

`contracts/ci-worker/v1/mapping.yaml`:

```yaml
mapping:
  source_control.endpoint:
    source_key: GITEA_URL
  source_control.authentication.token:
    source_key: RUNNER_TOKEN
```

### 2.2 Contract Ownership

Contracts are platform-owned artifacts. They define:
- What a capability requires
- Which validators apply to the contract
- The version of the contract

The Configuration Manager loads contracts at startup. It does not own them. No contract definitions live inside `packages/configuration/`.

### 2.4 Mapping Flow

```
Raw Configuration Values
       |
       v
Mapping Rules (per contract)
       |
       v
Resolved Contract
       |
       v
Validation
       |
       v
Validated Contract
```

The Mapping Adapter does NOT define the contract. The contract definition is the input to mapping and validation.

---

## 3. New `packages/configuration/` Structure

This becomes a **platform service** (Docker container), not a library. Contracts are NOT inside this package — they are platform-owned artifacts at a configurable path.

```
packages/configuration/
  pyproject.toml
  src/
    configuration/
      __init__.py
      server.py                  # HTTP FastAPI server
      config.py                  # Service configuration (Redis URL, CONTRACTS_PATH, SOURCES_CONFIG_PATH, etc.)
      routes/
        contracts.py             # GET /contracts/{capability}
        health.py                # GET /health, GET /ready
      providers/
        __init__.py
        base.py                  # SourceProvider ABC
        env_file.py              # EnvFileProvider
        json_file.py             # JsonConfigProvider
        local_store.py           # LocalConfigStoreProvider
      sources/
        __init__.py
        loader.py                # Config-driven source provider loading
        precedence.py            # Source precedence resolution
      mapping/
        __init__.py
        adapter.py               # MappingAdapter (raw -> contract instance)
      validation/
        __init__.py
        registry.py              # Validator Registry
        contract_validator.py    # Structural validation (required fields, types)
        runtime_validator.py     # Runtime validation (reachability, auth)
        result.py                # ValidationResult data class
      cache/
        __init__.py
        redis_cache.py           # Redis-backed cache for validated contracts
      models/
        __init__.py
        resolved_contract.py     # ResolvedContract model
        contract_request.py      # ContractRequest model
  tests/
    conftest.py
    test_providers/
      test_env_file.py
      test_json_file.py
      test_local_store.py
    test_mapping/
      test_adapter.py
    test_validation/
      test_contract_validator.py
      test_runtime_validator.py
    test_cache/
      test_redis_cache.py
    test_integration/
      test_contract_resolution.py
  Dockerfile
```

Contracts live outside this package at `CONTRACTS_PATH` (default: `/etc/platform/contracts`) and `SOURCES_CONFIG_PATH` (default: `/etc/platform/sources.yaml`). Example of the physical layout:

```
/etc/platform/
    contracts/
        ci-worker/
            v1/
                contract.yaml
                mapping.yaml

    sources.yaml
    config.json
    config.d/
```

The Configuration Manager loads contract definitions from `CONTRACTS_PATH` and source configuration from `SOURCES_CONFIG_PATH` at startup. It does not own them.

---

## 4. Source Providers

### 4.1 Design
Source providers retrieve raw configuration values from their source. They do NOT understand capabilities, contracts, or validation.

### 4.2 Config-Driven Provider Loading
Source providers are loaded from configuration, not hard-coded. The Configuration Manager reads a `sources` configuration block at startup and initializes the enabled providers.

```yaml
sources:
  providers:
    - type: env
      enabled: true
    - type: json
      enabled: true
      path: /etc/platform/config.json
    - type: local
      enabled: true
      path: /etc/platform/config.d
  precedence:
    # highest priority first
    - env
    - json
    - local
```

The `sources.providers` list defines available providers. The `sources.precedence` list defines resolution order. The architecture supports adding new provider types by adding a configuration entry without changing the Configuration Manager code.

MVP supports three provider types: `env`, `json`, and `local`. The configuration-driven approach means adding a fourth provider type in the future requires only a YAML change, not a code change.

### 4.3 Provider Interface
```python
class SourceProvider(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def read(self) -> dict[str, str]: ...

    @abstractmethod
    def source_type(self) -> str: ...
```

### 4.3 Providers

**EnvFileProvider** (`source_type: "env"`)
- Reads from `.env` files and `os.environ`
- `os.environ` overrides `.env` values

**JsonConfigProvider** (`source_type: "json"`)
- Reads from `config.json` files

**LocalConfigStoreProvider** (`source_type: "local"`)
- Reads from a local configuration directory
- Each file in the directory is a key-value pair or JSON file

### 4.4 Precedence Resolution

Sources are ordered by precedence. Resolution is explicit: for each required value, the Configuration Manager checks providers in order and uses the first one that provides the value.

```yaml
sources:
  precedence:
    # highest priority first
    - env
    - json
    - local
```

Resolution algorithm:
1. Check env provider first
2. If key is missing, check json provider
3. If key is still missing, check local provider
4. If key is unavailable in any source, the resolution fails

Note: "first wins" means the highest-priority source that contains the key is used. Lower-priority sources are consulted only for keys not found in higher-priority sources.

#### Example: CI Worker Configuration Resolution

Sources:

`.env`:
```
GITEA_URL=https://gitea.local.test
RUNNER_TOKEN=abc123
```

JSON:
```json
{
  "GITEA_URL": "https://fallback.local.test"
}
```

Precedence:
```yaml
sources:
  precedence:
    - env
    - json
    - local
```

Resolution:
- `GITEA_URL` -> env wins -> `https://gitea.local.test`
- `RUNNER_TOKEN` -> env only source -> `abc123`

Resulting Resolved Contract:
```yaml
source_control:
  endpoint: https://gitea.local.test
  authentication:
    token: abc123
```

This reinforces:
- Gitea is not a provider
- `.env` is not the architecture
- Sources provide values only

### 4.5 What Source Providers Do NOT Do
- They do not validate values
- They do not know which contracts consume their data
- They do not know which capabilities use their data
- They do not perform runtime checks (connectivity, authentication)

---

## 5. Mapping Adapter

### 5.1 Purpose
The Mapping Adapter transforms raw configuration values into contract instances. It does not validate — it only maps.

The Mapping Adapter needs to know how raw source keys map into contract fields. This mapping is defined in a separate YAML artifact, not in Python code.

Example:

```
contracts/
    ci-worker/
        v1/
            contract.yaml
            mapping.yaml
```

`mapping.yaml`:
```yaml
mapping:
  source_control.endpoint:
    source_key: GITEA_URL
  source_control.authentication.token:
    source_key: RUNNER_TOKEN
```

### 5.2 How It Works
1. The Configuration Manager loads a contract definition and its corresponding mapping rules
2. The Mapping Adapter reads the mapping rules to know which source key maps to which contract field
3. The adapter reads raw values from resolved sources
4. The adapter maps raw values into the contract structure using the mapping rules
5. If required keys are missing from the raw values, the contract instance is incomplete and will fail validation

### 5.3 What Mapping DOES NOT Do
- It does not validate that values work
- It does not check reachability or authentication
- It does not define the contract itself — the contract YAML is the input
- It does not generate contracts dynamically
- It does not contain mapping logic in Python classes — mapping rules are data, not code

---

## 6. Validation

### 6.1 Association with Contracts
Validators are **associated with contracts**. Each contract definition declares which validators apply to it. The Configuration Manager does not contain arbitrary business validation logic.

Example contract with validators:
```yaml
name: ci-worker
version: v1

requirements:
  source_control:
    endpoint:
      required: true
    authentication:
      required: true
  runner:
    labels:
      required: true

validators:
  - required-fields
  - endpoint-connectivity
  - authentication
```

### 6.2 Contract Validation (Structural)
Checks that the resolved contract can be used:
- Required value exists in the contract instance
- Correct type
- Required dependency declared
- Required authentication supplied

Example failure:
```
ci-worker contract invalid
Missing: source_control.authentication.token
```

### 6.3 Runtime Validation (Functional)
Checks that the values work in practice:
- Endpoint reachable
- Authentication succeeds
- Dependency available

Example failure:
```
ci-worker contract invalid
Unable to authenticate with configured Git service
```

### 6.4 Validation Result
```python
@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    contract_name: str
    contract_version: str
    errors: list[str]
    validated_at: str  # ISO timestamp
```

### 6.5 Fail Fast
If contract validation fails, the capability MUST NOT start. The Configuration Manager returns a clear error and the bootstrap process stops.

---

## 7. Redis Cache

### 7.1 What Gets Cached
Only validated contracts are cached. Unvalidated contracts are never stored in the cache.

The cache represents: **"This contract has been proven usable."**

Not: **"This contract has been resolved."**

Example cached entry:
```json
{
  "contract": "ci-worker",
  "version": "v1",
  "status": "validated",
  "configuration": {
    "GITEA_URL": "https://gitea.local.test",
    "RUNNER_TOKEN": "xxxx"
  },
  "validation": {
    "validated_at": "2026-07-29T10:00:00"
  }
}
```

### 7.2 Cache Lifecycle
```
Request Contract
       |
       v
  Check Redis (contract:{name}:{version})
       |
       +--- Validated contract exists? ---+
       |                                   |
      yes                                  no
       |                                   |
  return cached                      resolve sources
  validated contract                  |
                                     v
                                  map contract
                                     |
                                     v
                                  validate
                                     |
                                     v
                                  cache validated contract
                                     |
                                     v
                                  return validated contract
```

### 7.3 Cache Key
`contract:{name}:{version}`

Example: `contract:ci-worker:v1`

### 7.4 Cache TTL
Contracts are cached for a configurable TTL (default: 300 seconds).

MVP behaviour:
- Validated contracts are cached with TTL
- No source watching or automatic invalidation in MVP
- Manual invalidation support exists (delete key from Redis)
- On cache expiry, the next request triggers a fresh resolution

---

## 8. HTTP API

### 8.1 Endpoints
```
GET /contracts/{capability}
GET /health
GET /ready
```

### 8.2 GET /contracts/{capability}
No additional headers are required. The capability name is the only path parameter.

```
GET /contracts/ci-worker
```

### 8.3 GET /health
Returns the service health status.

```json
{
  "status": "healthy"
}
```

### 8.4 GET /ready
Checks readiness dependencies.

Returns `200` when:
- Redis is available
- Contract definitions are loaded
- Source providers are initialized

Returns `503` when any dependency is unavailable.

```json
{
  "status": "ready"
}
```

### 8.5 Success Response (200) for /contracts/{capability}
Contract metadata and configuration values are returned. For MVP, the Configuration Manager returns the validated contract values required by the capability. The API should support future separation of credentials from configuration, but credential references are outside the current implementation scope.

```json
{
  "contract": {
    "name": "ci-worker",
    "version": "v1"
  },
  "status": "validated",
  "configuration": {
    "GITEA_URL": "https://gitea.local.test",
    "RUNNER_TOKEN": "****"
  },
  "validation": {
    "validated_at": "2026-07-29T10:00:00"
  }
}
```

### 8.6 Failure Response (4xx)
```json
{
  "contract": {
    "name": "ci-worker",
    "version": "v1"
  },
  "status": "invalid",
  "errors": [
    "Missing: runner.token"
  ]
}
```

---

## 9. Platform Bootstrap vs Capability Bootstrap

These are two separate concerns. Do not mix them.

### 9.1 Platform Bootstrap

The Configuration Manager is a platform service. It starts as part of the platform stack using static deployment configuration. It does NOT use the Configuration Manager to configure itself.

```yaml
# infrastructure/compose.yml

services:
  redis:
    image: redis:7-alpine
    networks:
      - platform-network
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  configuration-manager:
    image: platform/configuration-manager:latest
    environment:
      REDIS_URL: redis://redis:6379
      CONTRACTS_PATH: /etc/platform/contracts
      SOURCES_CONFIG_PATH: /etc/platform/sources.yaml
    networks:
      - platform-network
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

The Configuration Manager has bootstrap configuration only.

Bootstrap configuration is limited to infrastructure concerns required to start the service itself:
- Redis connection URL
- contract artifact location (`CONTRACTS_PATH`)
- source provider configuration location (`SOURCES_CONFIG_PATH`)
- service port
- logging configuration

This bootstrap configuration is not capability configuration. The Configuration Manager must not consume capability contracts to configure itself.

Environment variables used by the Configuration Manager are deployment parameters, not the configuration architecture being replaced.

### 9.2 Capability Bootstrap

Capabilities consume validated contracts. The CI Worker is the primary example.

```
CI Worker
    |
    v
Configuration Manager (HTTP API)
    |
    v
Validated Contract
    |
    v
Bootstrap Script (process-scoped)
    |
    v
CI Worker Runner
```

### 9.3 CI Worker Dependency Ordering

The CI Worker MUST NOT start until the Configuration Manager is healthy. This is enforced through `depends_on` with `condition: service_healthy`.

```yaml
# platform/compose.yml
services:
  ci-worker:
    image: aiassistant-ci:0.1.0
    environment:
      CONFIG_MANAGER_URL: http://configuration-manager:8080
      CAPABILITY: ci-worker
    depends_on:
      configuration-manager:
        condition: service_healthy
    networks:
      - platform-network
```

The `condition: service_healthy` ensures the CI Worker container does not start until the Configuration Manager responds to its health check. Combined with the bootstrap script's failure-fast logic, this guarantees that a capability never starts without a validated contract.

---

## 10. CI Worker Bootstrap Entrypoint

### 10.1 Current vs New
**Current**: `start runner`  
**New**: `bootstrap -> request validated contract -> verify response -> populate runtime environment -> start runner`

### 10.2 Bootstrap Flow
```
1. Read CONFIG_MANAGER_URL and CAPABILITY from environment (injected by platform)
2. GET /contracts/{capability} from Configuration Manager
3. Verify response has status "validated" and expected schema
4. Export validated contract configuration as process-scoped environment variables
5. exec the runner process
```

The Configuration Manager validates the contract. The capability bootstrap verifies that it received a valid response. The capability does not perform contract validation.

### 10.3 Bootstrap Script (process-scoped environment)

The bootstrap script uses `export` to set environment variables for the runner process. It does NOT write to `/etc/environment` or any machine-wide state.

```bash
#!/bin/sh
# bootstrap entrypoint

CONFIG_MANAGER_URL="${CONFIG_MANAGER_URL:?CONFIG_MANAGER_URL not set}"
CAPABILITY="${CAPABILITY:?CAPABILITY not set}"

# Request validated contract from Configuration Manager
RESPONSE=$(curl -s -f "${CONFIG_MANAGER_URL}/contracts/${CAPABILITY}")

# Validate response has status "validated"
STATUS=$(echo "$RESPONSE" | jq -r '.status')
if [ "$STATUS" != "validated" ]; then
  echo "Contract validation failed for ${CAPABILITY}"
  echo "$RESPONSE" | jq .errors
  exit 1
fi

# Populate process-scoped environment (not /etc/environment)
export GITEA_URL="$(echo "$RESPONSE" | jq -r '.configuration.GITEA_URL')"
export RUNNER_TOKEN="$(echo "$RESPONSE" | jq -r '.configuration.RUNNER_TOKEN')"

# Start the runner
exec runner start
```

### 10.4 Environment Variables as Compatibility Layer
Environment variables are the **compatibility layer**, NOT the primary configuration mechanism. The primary flow is:

```
Source Providers -> Validated Contract -> Bootstrap Process -> export -> Runner Process
```

Capabilities never read `.env`, `config.json`, or Docker environment directly. The bootstrap script sets environment variables only for the runner process it execs.

---

## 11. Configuration Manager Ownership

The Configuration Manager has **one owner**: `infrastructure/compose.yml`.

It is NOT added to `platform/compose.yml`. Capabilities in the platform compose reference the existing Configuration Manager service.

| File | Contains | Owner |
|------|----------|-------|
| `infrastructure/compose.yml` | redis, configuration-manager | Infrastructure |
| `platform/compose.yml` | ci-worker, other capabilities | Platform |

The ci-worker in `platform/compose.yml` references the configuration-manager by service name (Docker DNS):

```yaml
services:
  ci-worker:
    image: aiassistant-ci:0.1.0
    environment:
      CONFIG_MANAGER_URL: http://configuration-manager:8080
      CAPABILITY: ci-worker
    depends_on:
      - configuration-manager
    networks:
      - platform-network
```

---

## 12. Source Provider, Mapping Adapter, Validator Definitions

These are the precise, unambiguous definitions for each role.

### Source Providers
- **Purpose**: Retrieve raw configuration values from their source
- **Knows about**: Their source only
- **Does NOT know about**: capabilities, contracts, validation
- **Examples**:
  - `EnvFileProvider` — reads `.env` files and `os.environ`
  - `JsonConfigProvider` — reads `config.json` files
  - `LocalConfigStoreProvider` — reads from a local configuration directory

### Mapping Adapters
- **Purpose**: Convert raw values into contract instances
- **Knows about**: contract definitions (YAML), mapping rules
- **Does NOT know about**: validation logic, source internals
- **Examples**:
  - `CiWorkerMappingAdapter` — maps raw values to the ci-worker contract structure

### Validators
- **Purpose**: Prove that a resolved contract is usable
- **Knows about**: contract requirements, validation rules
- **Does NOT know about**: source internals, mapping rules
- **Validators are registered via a Validator Registry**, not hard-coded per capability

#### Validator Registry
The Configuration Manager uses a Validator Registry to discover and execute validators. Validators are registered by name and associated with contracts via the contract definition. The Configuration Manager does NOT contain capability-specific validation logic.

```
Validator Registry
       |
       +-- RequiredFieldsValidator
       +-- ConnectivityValidator
       +-- AuthenticationValidator
```

When a contract specifies `validators: [endpoint-connectivity, authentication]`, the Configuration Manager queries the Validator Registry for implementations registered under those names and executes them.

This means adding a new validator type requires registering it in the Validator Registry, NOT modifying the Configuration Manager's core logic.

#### What Validators Are NOT
- Not GiteaConfigurationProvider (Gitea is an external system described by contract values)
- Not GitHubConfigurationProvider (same reasoning)

**Gitea and GitHub are systems that configuration values may describe. They are NOT configuration sources.** A CI Worker contract may contain `source_control.type: gitea` — this describes the external system the CI Worker interacts with, it is not a configuration source for the Configuration Manager.

Do NOT create `GiteaConfigurationProvider` or `GitHubConfigurationProvider` unless there is a specific requirement to retrieve configuration data from those systems.

---

## 13. Docker Compose Integration

### 13.1 infrastructure/compose.yml — Configuration Manager + Redis

The Configuration Manager and Redis live here as platform infrastructure:

```yaml
services:
  redis:
    image: redis:7-alpine
    networks:
      - platform-network
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  configuration-manager:
    image: platform/configuration-manager:latest
    environment:
      REDIS_URL: redis://redis:6379
      CONTRACTS_PATH: /etc/platform/contracts
      SOURCES_CONFIG_PATH: /etc/platform/sources.yaml
    networks:
      - platform-network
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

### 13.2 platform/compose.yml — CI Worker (Capability)

Capabilities reference the existing Configuration Manager service by DNS name. No Configuration Manager service definition here. The CI Worker waits for the Configuration Manager to be healthy before starting.

```yaml
services:
  ci-worker:
    image: aiassistant-ci:0.1.0
    environment:
      CONFIG_MANAGER_URL: http://configuration-manager:8080
      CAPABILITY: ci-worker
    depends_on:
      configuration-manager:
        condition: service_healthy
    networks:
      - platform-network
```

---

## 14. CI Runner Docker Image

### 14.1 Changes
The CI runner Docker image (`infrastructure/images/ci-runner/Dockerfile`) must:
1. Include the bootstrap script
2. Set the bootstrap as entrypoint (replacing `start runner`)
3. NOT include the old configuration library
4. NOT read `.env` directly
5. Include `curl` and `jq` for contract resolution

### 14.2 Bootstrap Script (process-scoped)
See Section 10.3 for the full bootstrap script. Key points:
- Uses `export` for process-scoped environment variables only
- Does NOT write to `/etc/environment`
- Uses `exec runner start` to replace the bootstrap process with the runner

---

## 15. Implementation Order

### Phase 1: Core Service
1. Create `packages/configuration/` structure with FastAPI server
2. Implement source providers (EnvFileProvider, JsonConfigProvider, LocalConfigStoreProvider)
3. Implement source precedence resolution
4. Implement contract definition loading from YAML files
5. Implement Mapping Adapter
6. Implement validators (RequiredFieldsValidator, ConnectivityValidator, AuthenticationValidator)
7. Implement Redis cache layer with TTL
8. Implement HTTP API endpoint (`GET /contracts/{capability}`)
9. Create Dockerfile for configuration-manager service
10. Unit tests for providers, mapping, validation, cache

### Phase 2: CI Worker Integration
11. Create bootstrap entrypoint script for CI Worker
12. Update CI Worker Dockerfile to use bootstrap entrypoint
13. Update `infrastructure/compose.yml` to add configuration-manager service and redis
14. Update `platform/compose.yml` to update ci-worker service with new environment
15. Integration tests for the full flow

### Phase 3: Validation & Verification
16. Test successful path (manager starts, worker starts, contract resolved, cached, validated, runner starts)
17. Test failure paths (missing required value, validation error, runtime validation error)
18. Verify no provider leakage (capabilities unaware of sources)
19. Verify no Gitea/GitHub providers created
20. Verify .env is not the primary architecture
21. Lint and typecheck

---

## 16. Final Architecture Statement

Source Providers retrieve raw values.

Mapping Adapters transform raw values into contract instances.

Validators prove contract instances are usable.

Configuration Manager orchestrates resolution, validation, caching, and delivery.

Contracts are platform-owned artifacts.

Capabilities consume validated contracts.

Capabilities never know where configuration originated.

---

## 17. Non Goals

The Configuration Manager does NOT:

- Provision infrastructure
- Create repositories
- Configure Gitea/GitHub
- Register runners
- Generate contracts
- Discover capabilities
- Modify source systems
- Manage secrets

Its responsibility is only:

- Resolve values
- Map values
- Validate contract
- Deliver validated contract

---

## 18. Validation Checklist

### Architecture Corrections Applied
- [ ] Contracts are predefined YAML artifacts, not generated Python schemas
- [ ] Contract definitions live outside `packages/configuration` at `CONTRACTS_PATH`
- [ ] Mapping rules are separate data artifacts (`mapping.yaml`), not Python classes
- [ ] Validators are registered via a Validator Registry, not hard-coded per capability
- [ ] Cache stores only validated contracts (never unvalidated)
- [ ] API response separates contract metadata from configuration values
- [ ] No `X-Capability-Name` header on API requests
- [ ] Platform bootstrap and capability bootstrap are separate flows
- [ ] Configuration Manager has `GET /health` and `GET /ready` endpoints
- [ ] Source providers are loaded from configuration, not hard-coded
- [ ] CI Worker uses `condition: service_healthy` for Configuration Manager dependency
- [ ] Bootstrap script uses process-scoped `export`, not `/etc/environment`
- [ ] Bootstrap script uses `exec runner start` to replace itself
- [ ] Terminology uses "Resolved Contract" not "Contract Instance"

### Infrastructure
- [ ] Configuration Manager starts as a Docker service in infrastructure/compose.yml
- [ ] Configuration Manager has a health check (GET /health)
- [ ] Configuration Manager has a readiness check (GET /ready)
- [ ] Redis is used for caching with TTL (not in-memory)
- [ ] Configuration Manager has one owner (infrastructure/compose.yml)
- [ ] Platform compose references Configuration Manager by DNS name only
- [ ] CI Worker waits for Configuration Manager to be healthy before starting

### Source Providers
- [ ] Source providers read only from their sources (no contract/validation knowledge)
- [ ] Source precedence is explicit and correctly implemented
- [ ] Source providers are loaded from configuration, not hard-coded

### Contract Definitions and Mapping
- [ ] Contract definitions are YAML files, not Python models
- [ ] Contract definitions are platform-owned artifacts outside the configuration service
- [ ] Mapping rules are separate YAML artifacts (`mapping.yaml`)
- [ ] Mapping Adapter maps raw values to contract instances using predefined mapping rules
- [ ] Mapping rules are data, not code (no mapping logic in Python classes)

### Validation
- [ ] Contract validation checks required fields, types, dependencies
- [ ] Runtime validation checks reachability and auth
- [ ] Validators are associated with contracts, not with providers
- [ ] Validators are registered via a Validator Registry, not hard-coded per capability
- [ ] No capability-specific validation logic in Configuration Manager
- [ ] Fail fast on validation failure (capability does not start)

### API
- [ ] HTTP API separates contract metadata from configuration values
- [ ] No `X-Capability-Name` header on API requests
- [ ] API has health and readiness endpoints

### CI Worker Bootstrap
- [ ] CI Worker bootstrap uses process-scoped export, not /etc/environment
- [ ] CI Worker bootstrap execs the runner process
- [ ] CI Worker never reads .env or config.json directly
- [ ] Capabilities are unaware of how contracts were created
- [ ] No Gitea/GitHub configuration providers exist

### Testing
- [ ] All successful and failure paths have tests
