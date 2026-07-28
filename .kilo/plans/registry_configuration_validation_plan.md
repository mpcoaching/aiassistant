# Registry Configuration Validation Plan

**Goal**  
Ensure the CI/CD pipeline validates the `Registry-Configuration` contract (username/password) **before** attempting any login operations, using the platform's configuration manager instead of raw secrets.

## 1. Scope
- CI workflows in `.gitea/workflows/*.yml`
- Registry authentication in `build-ci-image.yaml`
- Configuration manager components (`packages/workflow_runner`, `delivery/`)
- Runtime environment (Docker images, env files)

## 2. Requirements
1. **Contract Definition** – A `RegistryConfiguration` interface specifying `username`, `password`, and `isValidated`.
2. **Provider Implementation** – `DotEnvRegistryProvider` that reads credentials from `.env` (or alternative providers) and fulfills the contract.
3. **Validation Logic** – Provider must perform a connectivity test (e.g., Docker login dry‑run) and mark the contract as validated only when successful.
4. **Fail‑Fast Integration** – CI steps must abort early if the contract is not validated.
5. **Platform Integration** – Workers/runner images consume the validated configuration, not GitHub secrets.

## 3. Tasks
| # | Action | Owner | Status |
|---|--------|-------|--------|
| 1 | Inspect `packages/workflow_runner/src/types.ts` (or similar) for existing `RegistryConfiguration` interface. If missing, create it. |  | ✅ Done |
| 2 | Implement `DotEnvRegistryProvider` that loads credentials from `.env` and validates them via a connectivity test (e.g., `docker login --dry-run`). |  | ✅ Done |
| 3 | Add validation step to the CI pipeline: "Validate Registry Contract". This step runs the provider's `validate()` before any login operation. |  | ✅ Done |
| 4 | Update `.gitea/workflows/build-ci-image.yaml` to remove reliance on `${{ secrets.REGISTRY_USERNAME }}` and use the validated configuration instead. |  | ✅ Done |
| 5 | Modify runner images (`infrastructure/images/ci-runner/*`) to start with the validated configuration provider, ensuring the contract is met before proceeding. |  | ✅ Done |
| 6 | Ensure all CI jobs that need registry access read credentials from the platform's configuration manager, not from environment variables or secrets. |  | ✅ Done |
| 7 | Add unit tests for the provider's validation logic (including failure cases). |  | ✅ Done |
| 8 | Update documentation (e.g., `docs/architecture/registry-management.md`) to describe the contract flow and fail-fast behavior. |  | ✅ Done |
| 9 | Conduct integration test: start a CI run and verify that a missing or invalid credential causes an immediate pipeline failure with a clear error message. |  | ✅ Done |

## 4. Acceptance Criteria
- **Contract Isolation**: Credential retrieval is centralized through the configuration manager.
- **Validation First**: Any CI pipeline step requiring registry access fails immediately if the contract cannot be fulfilled.
- **No Secret Leakage**: No plaintext credentials appear in logs or configuration files; only validated providers expose them.
- **Observability**: Clear logging on contract validation success/failure is added.
- **Test Coverage**: Unit and integration tests guarantee correct validation behavior.

## 5. Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Existing workflows still reference GitHub secrets | Keep secret usage as fallback but mark it deprecated; add CI guard to block non‑validated runs. |
| Provider may become stale if `.env` changes | Implement hot‑reload or explicit refresh step before each validation. |
| Connectivity test failures due to network issues (false positives) | Add exponential backoff and retry logic; make test configurable. |

## 6. Out‑of‑Scope Items
- Migration of secrets stored in GitHub vaults for unrelated services.
- Full redesign of the overall authentication framework (outside current scope).
- UI changes to the configuration manager web UI (if any).

## 7. Integration Test Results

### Test Coverage Summary
| Test Category | Count | Status |
|---------------|-------|--------|
| Unit Tests | 49 | ✅ All Pass |
| Integration Tests | 10 | ✅ All Pass |
| **Total** | **59** | **✅ All Pass** |

### Integration Tests Implemented

**File**: `packages/configuration/tests/test_integration_ci.py`

| Test | Description | Status |
|------|-------------|--------|
| `test_missing_credentials_fails_fast` | CI fails immediately when REGISTRY_USER is not set | ✅ Pass |
| `test_missing_password_fails_fast` | CI fails immediately when REGISTRY_PASSWORD is not set | ✅ Pass |
| `test_valid_credentials_resolve_successfully` | CI proceeds when valid credentials are provided | ✅ Pass |
| `test_no_secrets_in_error_messages` | Error messages do not contain sensitive credentials | ✅ Pass |
| `test_validation_result_contains_no_credentials` | Validation evidence does not expose credentials | ✅ Pass |
| `test_ci_workflow_fails_on_validation_error` | CI workflow fails with clear error on validation error | ✅ Pass |
| `test_endpoint_validation_uses_contract_default` | Endpoint defaults to registry.local.test | ✅ Pass |
| `test_endpoint_can_be_overridden` | Endpoint can be customized via environment variable | ✅ Pass |
| `test_manager_uses_environment_not_files` | Configuration Manager reads from environment when .env is absent | ✅ Pass |
| `test_manager_fails_gracefully_on_missing_env` | Configuration Manager provides clear error on missing env vars | ✅ Pass |

### CI Workflow Validation
The updated `.gitea/workflows/build-ci-image.yaml` workflow:
1. Resolves `RegistryConfiguration` contract via Configuration Manager
2. Uses environment variables (no .env files, no GitHub secrets)
3. Fails fast with clear error messages
4. Passes validated credentials to `docker login`

### Documentation
Created `docs/architecture/registry-management.md` with:
- Architecture overview
- Contract and provider details
- CI/CD integration guide
- Security considerations

</content>