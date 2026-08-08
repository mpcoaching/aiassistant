# Plan: ragpilot Configuration Manager Integration (Validated)

## Goal
Integrate ragpilot with the existing Platform Configuration Manager so that ragpilot has zero direct dependency on `.env` files, environment variables, or any configuration storage mechanism.

## Design Validation Results

### 1. Contract Structure
**Confirmed pattern is NOT uniform across all three files.**

| Contract | contract.yaml | mapping.yaml | Python Model |
|---|---|---|---|
| `registry` | contracts/registry/v1/ | contracts/registry/v1/ | packages/configuration/src/configuration/contracts/v1/registry.py |
| `ci-worker` | contracts/ci-worker/v1/ | contracts/ci-worker/v1/ | none |
| `deployment` | contracts/deployment/v1/ | contracts/deployment/v1/ | none |
| `database` | none | none | packages/configuration/src/configuration/contracts/v1/database.py |
| `message-bus` | none | none | packages/configuration/src/configuration/contracts/v1/message_bus.py |
| `langgraph-runtime` | none | none | packages/configuration/src/configuration/contracts/v1/langgraph_runtime.py |

**Rule:** Python models exist for Python consumers. `contract.yaml` + `mapping.yaml` exist for the HTTP API (`/contracts/{capability}`) and provider mapping. They can exist independently.

**For Qdrant:** Create all three files because:
- Python model: needed for ragpilot Python consumer
- contract.yaml + mapping.yaml: needed for HTTP API consumer and provider chain

### 2. Endpoint Defaults
**Confirmed:** Existing contracts put service endpoints as defaults in the Pydantic model:
- `registry.py:19`: `endpoint: str = Field(default="https://registry.local.test", validation_alias="REGISTRY_ENDPOINT")`
- `langgraph_runtime.py:17`: `url: str = Field(default="http://langgraph:8000", validation_alias="LANGGRAPH_URL")`

**Recommendation:** Put `QDRANT_URL` default in the Python model, not in `contract.yaml`. The `.local.test` domain is local-development-specific; the Python model default is the canonical location for runtime fallbacks. The `contract.yaml` default is redundant when the Python model has one.

### 3. Secret / Credential Pattern
**Confirmed patterns:**
- `registry.py`: `username: str`, `password: str` (separate credential fields)
- `database.py`: `url: str` (full connection string, credential embedded)
- No existing API-key-specific pattern

**Recommendation:** Use `api_key: str` for Qdrant. This is a single credential field, which is the natural representation for an API key. Follow the explicit field naming pattern from `registry.py`.

### 4. Consumer Integration (CRITICAL)
**Confirmed:** Components self-instantiate `ConfigurationManager`. There is NO platform runtime injection.

```python
# workflow_runner/api.py:185 — the ONLY existing Python consumer pattern
manager = ConfigurationManager(DotEnvProvider())
_bus_cfg = manager.resolve(MessageBusConfiguration)
```

**Key finding:** The architecture states consumers are "unaware of providers," but the actual implementation has every Python consumer directly instantiating `DotEnvProvider()`. This is the established pattern despite the architectural intent. There is no factory, no DI container, no platform runtime injection.

**Implication for ragpilot:** ragpilot must follow the same pattern: self-instantiate `ConfigurationManager(DotEnvProvider())`. There is no alternative pattern in the codebase.

### 5. ragpilot Boundary
**Answer: Option A.** ragpilot instantiates `ConfigurationManager` itself, following `workflow_runner` exactly.

There is no:
- Platform runtime injection (Option B)
- Adapter/factory abstraction (Option C)

### 6. Qdrant Configuration Scope
**Recommendation:** Qdrant contract contains ONLY infrastructure:
- `url` — Qdrant server endpoint
- `api_key` — authentication credential

ragpilot-specific configuration (collection name, chunk size, embedding model, retrieval parameters) belongs in ragpilot's own contract or configuration, not in the shared Qdrant contract.

### 7. Runtime API
**Confirmed:** `GET /contracts/{capability}` exists at `packages/configuration/src/configuration/routes/contracts.py:65`. Used by CI at `.gitea/workflows/ci-v2.yaml:60`.

## Implementation Tasks

### 1. Create Qdrant Pydantic Contract Model
**File:** `packages/configuration/src/configuration/contracts/v1/qdrant.py`
```python
class QdrantConfiguration(Contract, BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)
    
    url: str = Field(default="https://qdrant.local.test", validation_alias="QDRANT_URL")
    api_key: str = Field(validation_alias="QDRANT_API_KEY")
    
    @classmethod
    def type_id(cls) -> str:
        return "qdrant"
    
    @classmethod
    def purpose(cls) -> str:
        return "Qdrant vector store connection configuration"
    
    @classmethod
    def owner(cls) -> str:
        return "platform"
    
    @classmethod
    def lifecycle(cls) -> Lifecycle:
        return Lifecycle(platform="platform", capability="qdrant", execution="runtime")
    
    @classmethod
    def documentation(cls) -> str:
        return "Configuration for connecting to the Qdrant vector store"
```

### 2. Register in contracts v1 __init__.py
**File:** `packages/configuration/src/configuration/contracts/v1/__init__.py`
- Add `QdrantConfiguration` to imports and `__all__`

### 3. Create Qdrant Contract Declaration
**File:** `contracts/qdrant/v1/contract.yaml`
```yaml
name: qdrant
version: v1

requirements:
  QDRANT_URL:
    required: true
  QDRANT_API_KEY:
    required: true

validators:
  - required-fields
```
Note: No `default` here — the Python model carries the default.

### 4. Create Qdrant Mapping
**File:** `contracts/qdrant/v1/mapping.yaml`
```yaml
mapping:
  QDRANT_URL:
    source_key: QDRANT_URL
  QDRANT_API_KEY:
    source_key: QDRANT_KEY
```

### 5. ragpilot Bootstrap Pattern (when ragpilot is created)
```python
from configuration import ConfigurationManager, DotEnvProvider
from configuration.contracts.v1.qdrant import QdrantConfiguration

manager = ConfigurationManager(DotEnvProvider())
qdrant_cfg = manager.resolve(QdrantConfiguration)
# Use qdrant_cfg.url and qdrant_cfg.api_key
```

## Validation Steps
1. `contracts/qdrant/v1/contract.yaml` loads without YAML error
2. `contracts/qdrant/v1/mapping.yaml` maps `QDRANT_KEY` → `QDRANT_API_KEY`
3. `GET http://configuration_manager:8080/contracts/qdrant` returns 200 with validated config
4. `QdrantConfiguration` Pydantic model validates successfully against resolved dict
5. `manager.resolve(QdrantConfiguration)` returns model instance with `url` and `api_key`

## Out of Scope
- ragpilot package creation (only configuration integration)
- Migrating `capability_registry` Qdrant usage to Configuration Manager
- Secret scoping / multi-tenant restrictions
- Removing `QDRANT_KEY` from `contracts/deployment/v1/`
- Changing Qdrant service definition in `platform/compose.yml`

## Files Changed
| File | Action |
|------|--------|
| `packages/configuration/src/configuration/contracts/v1/qdrant.py` | Create |
| `packages/configuration/src/configuration/contracts/v1/__init__.py` | Edit |
| `contracts/qdrant/v1/contract.yaml` | Create |
| `contracts/qdrant/v1/mapping.yaml` | Create |
