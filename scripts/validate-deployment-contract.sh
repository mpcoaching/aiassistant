#!/bin/bash
set -euo pipefail

echo "Validating deployment contract early (PAT-013: Contract Validation Before Execution)..."

TMP_ENV=$(mktemp)
trap 'rm -f "$TMP_ENV"' EXIT

cat > "$TMP_ENV" <<'ENVEOF'
REGISTRY_URL=${REGISTRY_URL:-}
REGISTRY_USER=${REGISTRY_USER:-}
REGISTRY_PASSWORD=${REGISTRY_PASSWORD:-}
IMAGE_TAG=${IMAGE_TAG:-}
AGENT_DEV_DB_USER=${AGENT_DEV_DB_USER:-}
AGENT_DEV_DB_PASSWORD=${AGENT_DEV_DB_PASSWORD:-}
AGENT_DEV_DB_NAME=${AGENT_DEV_DB_NAME:-}
AGENT_LIVE_DB_USER=${AGENT_LIVE_DB_USER:-}
AGENT_LIVE_DB_PASSWORD=${AGENT_LIVE_DB_PASSWORD:-}
AGENT_LIVE_DB_NAME=${AGENT_LIVE_DB_NAME:-}
LANGGRAPH_DEV_DB_USER=${LANGGRAPH_DEV_DB_USER:-}
LANGGRAPH_DEV_DB_PASSWORD=${LANGGRAPH_DEV_DB_PASSWORD:-}
LANGGRAPH_DEV_DB_NAME=${LANGGRAPH_DEV_DB_NAME:-}
LANGGRAPH_LIVE_DB_USER=${LANGGRAPH_LIVE_DB_USER:-}
LANGGRAPH_LIVE_DB_PASSWORD=${LANGGRAPH_LIVE_DB_PASSWORD:-}
LANGGRAPH_LIVE_DB_NAME=${LANGGRAPH_LIVE_DB_NAME:-}
POSTGRES_DB_USER=${POSTGRES_DB_USER:-}
POSTGRES_DB_PASSWORD=${POSTGRES_DB_PASSWORD:-}
POSTGRES_DB_NAME=${POSTGRES_DB_NAME:-}
QDRANT_KEY=${QDRANT_KEY:-}
PORTKEY_MASTER_KEY=${PORTKEY_MASTER_KEY:-}
PORTKEY_ADMIN_TOKEN=${PORTKEY_ADMIN_TOKEN:-}
GROQ_API_KEY=${GROQ_API_KEY:-}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
GEMINI_API_KEY=${GEMINI_API_KEY:-}
HF_API_KEY=${HF_API_KEY:-}
AI_PROVIDER_BASE_URL=${AI_PROVIDER_BASE_URL:-}
CLICKHOUSE_DB_NAME=${CLICKHOUSE_DB_NAME:-}
CLICKHOUSE_DB_USER=${CLICKHOUSE_DB_USER:-}
CLICKHOUSE_DB_PASSWORD=${CLICKHOUSE_DB_PASSWORD:-}
LANGFUSE_HOSTNAME=${LANGFUSE_HOSTNAME:-}
LANGFUSE_DATABASE_URL=${LANGFUSE_DATABASE_URL:-}
LANGFUSE_NEXTAUTH_SECRET=${LANGFUSE_NEXTAUTH_SECRET:-}
LANGFUSE_NEXTAUTH_URL=${LANGFUSE_NEXTAUTH_URL:-}
LANGFUSE_SALT=${LANGFUSE_SALT:-}
LANGFUSE_ENCRYPTION_KEY=${LANGFUSE_ENCRYPTION_KEY:-}
LANGFUSE_CLICKHOUSE_USER=${LANGFUSE_CLICKHOUSE_USER:-}
LANGFUSE_CLICKHOUSE_PASSWORD=${LANGFUSE_CLICKHOUSE_PASSWORD:-}
LANGFUSE_CLICKHOUSE_URL=${LANGFUSE_CLICKHOUSE_URL:-}
LANGFUSE_CLICKHOUSE_MIGRATION_URL=${LANGFUSE_CLICKHOUSE_MIGRATION_URL:-}
LANGFUSE_REDIS_URL=${LANGFUSE_REDIS_URL:-}
LANGFUSE_S3_MEDIA_UPLOAD_BUCKET=${LANGFUSE_S3_MEDIA_UPLOAD_BUCKET:-}
LANGFUSE_S3_EVENT_UPLOAD_BUCKET=${LANGFUSE_S3_EVENT_UPLOAD_BUCKET:-}
LANGFUSE_S3_ENDPOINT=${LANGFUSE_S3_ENDPOINT:-}
LANGFUSE_STORAGE_TYPE=${LANGFUSE_STORAGE_TYPE:-}
LANGFUSE_LANGCHAIN_TRACING_V2=${LANGFUSE_LANGCHAIN_TRACING_V2:-}
LANGFUSE_LANGCHAIN_ENDPOINT=${LANGFUSE_LANGCHAIN_ENDPOINT:-}
LANGFUSE_LANGCHAIN_API_KEY=${LANGFUSE_LANGCHAIN_API_KEY:-}
ZO_ROOT_USER_EMAIL=${ZO_ROOT_USER_EMAIL:-}
ZO_ROOT_USER_PASSWORD=${ZO_ROOT_USER_PASSWORD:-}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-}
N8N_HOST=${N8N_HOST:-}
N8N_PORT=${N8N_PORT:-}
N8N_WEBHOOK_URL=${N8N_WEBHOOK_URL:-}
N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL:-}
N8N_SECURE_COOKIE=${N8N_SECURE_COOKIE:-}
N8N_PROXY_HOPS=${N8N_PROXY_HOPS:-}
N8N_DB_TYPE=${N8N_DB_TYPE:-}
N8N_DB_HOST=${N8N_DB_HOST:-}
N8N_DB_PORT=${N8N_DB_PORT:-}
N8N_DB_DATABASE=${N8N_DB_DATABASE:-}
N8N_DB_USER=${N8N_DB_USER:-}
N8N_DB_PASSWORD=${N8N_DB_PASSWORD:-}
N8N_OTEL_ENABLED=${N8N_OTEL_ENABLED:-}
N8N_OTEL_SERVICE_NAME=${N8N_OTEL_SERVICE_NAME:-}
N8N_OTEL_EXPORTER_OTLP_ENDPOINT=${N8N_OTEL_EXPORTER_OTLP_ENDPOINT:-}
N8N_LANGCHAIN_TRACING_V2=${N8N_LANGCHAIN_TRACING_V2:-}
N8N_LANGCHAIN_API_KEY=${N8N_LANGCHAIN_API_KEY:-}
N8N_LANGCHAIN_ENDPOINT=${N8N_LANGCHAIN_ENDPOINT:-}
N8N_LANGCHAIN_PROJECT=${N8N_LANGCHAIN_PROJECT:-}
ENVEOF

export TMP_DEPLOY_ENV="$TMP_ENV"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="$REPO_ROOT/packages/configuration/src"

python3 - "$BASE" <<'PYEOF'
import importlib.util
import os
import sys

import yaml

BASE = sys.argv[1]
sys.path.insert(0, BASE)

def load(name, relpath):
    path = os.path.join(BASE, relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

env_provider_mod = load("configuration.providers.env_file", "configuration/providers/env_file.py")
mapping_mod = load("configuration.mapping.adapter", "configuration/mapping/adapter.py")
validation_mod = load("configuration.validation.contract_validator", "configuration/validation/contract_validator.py")
registry_mod = load("configuration.validation.registry", "configuration/validation/registry.py")

contracts_path = os.path.join(BASE, "..", "..", "..", "contracts")
contracts_path = os.path.abspath(contracts_path)

with open(os.path.join(contracts_path, "deployment", "v1", "contract.yaml"), "r", encoding="utf-8") as f:
    contract_def = yaml.safe_load(f) or {}
with open(os.path.join(contracts_path, "deployment", "v1", "mapping.yaml"), "r", encoding="utf-8") as f:
    mapping_data = yaml.safe_load(f) or {}

provider = env_provider_mod.DotEnvProvider(env_file=os.environ.get("TMP_DEPLOY_ENV", ""))
raw_values = provider.read()

adapter = mapping_mod.MappingAdapter(mapping_data.get("mapping", {}))
resolved = adapter.map(raw_values)

requirements = contract_def.get("requirements", {})
for key, spec in requirements.items():
    if isinstance(spec, dict) and "default" in spec and key not in resolved:
        resolved[key] = spec["default"]

registry = registry_mod.ValidatorRegistry()
registry.register("required-fields", validation_mod.StructuralValidator())

result = registry.validate_contract(
    contract_def.get("name", "deployment"),
    contract_def.get("version", "v1"),
    contract_def,
    resolved,
)

if not result.valid:
    print("CONTRACT_VALIDATION_FAILED")
    for err in result.errors:
        print(f"ERROR: {err}")
    sys.exit(1)

print("CONTRACT_VALIDATION_PASSED")
PYEOF