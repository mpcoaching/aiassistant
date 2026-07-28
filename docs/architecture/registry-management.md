# Registry Configuration Management

## Overview

The configuration manager validates registry credentials **before** any CI/CD pipeline step attempts registry operations. This ensures that invalid or missing credentials cause an immediate, clear pipeline failure rather than a cryptic Docker login error later in the process.

## Architecture

### Contract Definition

`RegistryConfiguration` defines the required fields for registry authentication:

| Field | Type | Env Var |
|-------|------|---------|
| `username` | `str` | `REGISTRY_USER` |
| `password` | `str` | `REGISTRY_PASSWORD` |
| `endpoint` | `str` | `REGISTRY_ENDPOINT` |

### Provider

`RegistryProvider` (in `packages/configuration/src/configuration/providers/registry.py`) extends `ConfigurationProvider` and implements:

1. **`read()`** – Loads credentials from `.env` (or OS environment), returning only `REGISTRY_*` prefixed keys.
2. **`validate()`** – Performs an HTTP API check against the registry's `/v2/` endpoint using Basic authentication. Returns a `RegistryValidationResult`.
3. **`is_validated()`** – Returns `True` only if the last validation succeeded.
4. **`validation_result()`** – Returns the last `RegistryValidationResult` or `None`.

### Validation Result

`RegistryValidationResult` contains:

- `success` (`bool`) – Whether validation passed.
- `validator_id` (`str`) – Identifier of the validator (`registry-http-auth`).
- `validator_version` (`str`) – Version of the validator (`1.0.0`).
- `evidence` (`dict`) – Diagnostic data (endpoint, status code, latency, errors).
- `error` (`str | None`) – Error message if validation failed.
- `timestamp` (`datetime`) – When validation was performed.

## CI/CD Integration

### Fail-Fast Validation Step

The `.gitea/workflows/build-ci-image.yaml` workflow includes a **"Validate Registry Credentials"** step that runs _before_ the Docker login step:

```yaml
- name: Validate Registry Credentials
  run: |
    python3 -c '
      from configuration.providers.registry import RegistryProvider
      provider = RegistryProvider(env_file=".env")
      result = provider.validate()
      if not result.success:
        print("Registry validation failed: " + result.error)
        exit(1)
      print("Registry validation successful")
    '
```

If validation fails, the pipeline aborts with a clear error message. No further steps (including Docker login) are attempted.

### Credential Source

Credentials are sourced from environment variables or `.env` files, **not** from GitHub secrets. This centralizes credential management through the configuration manager:

| Source | Variable |
|--------|----------|
| `.env` file | `REGISTRY_USER`, `REGISTRY_PASSWORD`, `REGISTRY_ENDPOINT` |
| OS environment | Same variables |
| CI environment | Set by runner or passed via `env_file` |

### Docker Runner Image

The CI runner image (`infrastructure/images/ci-runner/Dockerfile`) includes the configuration package installed via `pip install /tmp/packages/configuration`, enabling `from configuration.providers.registry import RegistryProvider` inside runner containers.

## Test Coverage

Unit tests for `RegistryProvider` cover the following scenarios:

| Test Case | Expected Result |
|-----------|----------------|
| Valid credentials (HTTP 200) | `success=True`, `is_validated()=True` |
| Invalid credentials (HTTP 401) | `success=False`, error message indicates 401 |
| Server error (HTTP 500) | `success=False`, error includes status code |
| Unreachable endpoint (URLError) | `success=False`, error describes connection failure |
| Unexpected exception | `success=False`, error includes exception message |
| No credentials set | `success=False`, error from provider |
| `is_validated()` before `validate()` | Returns `False` |
| `validation_result()` before `validate()` | Returns `None` |

All 49 configuration tests pass, including the 13 provider-specific tests.

## Fail-Fast Behavior

```
Pipeline Start
    │
    ▼
Validate Registry Credentials
    │
    ├── SUCCESS → Continue to Docker login & push
    │
    └── FAILURE → Abort pipeline immediately
                    Error message: "Registry validation failed: <reason>"
                    No secret leakage in logs
```

## Security Notes

- Credentials are **never** logged in plaintext.
- Validation errors include diagnostic metadata (endpoint, status code) but **never** include the password.
- The `RegistryValidationResult.evidence` dict excludes sensitive values.
- GitHub secrets are no longer used for registry authentication in the CI workflow.