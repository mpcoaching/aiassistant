from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from configuration.cache.redis_cache import RedisCache
from configuration.mapping.adapter import MappingAdapter
from configuration.sources import init_providers, load_sources_config
from configuration.validation.contract_validator import StructuralValidator
from configuration.validation.registry import ValidatorRegistry
from configuration.validation.runtime_validator import RuntimeValidator

router = APIRouter()

_cache: RedisCache | None = None
_registry: ValidatorRegistry | None = None


def get_cache() -> RedisCache:
    global _cache
    if _cache is None:
        from configuration.config import ConfigurationManagerConfig
        config = ConfigurationManagerConfig()
        _cache = RedisCache(redis_url=config.redis_url, ttl_seconds=config.cache_ttl_seconds)
    return _cache


def get_registry() -> ValidatorRegistry:
    global _registry
    if _registry is None:
        _registry = ValidatorRegistry()
        _registry.register("required-fields", StructuralValidator())
        _registry.register("endpoint-connectivity", RuntimeValidator())
        _registry.register("authentication", RuntimeValidator())
    return _registry


def load_contract(contracts_path: str, capability: str) -> dict | None:
    import yaml

    contract_dir = os.path.join(contracts_path, capability, "v1")
    contract_file = os.path.join(contract_dir, "contract.yaml")
    if not os.path.exists(contract_file):
        return None
    with open(contract_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_mapping(contracts_path: str, capability: str) -> dict:
    import yaml

    contract_dir = os.path.join(contracts_path, capability, "v1")
    mapping_file = os.path.join(contract_dir, "mapping.yaml")
    if not os.path.exists(mapping_file):
        return {"mapping": {}}
    with open(mapping_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


@router.get("/contracts/{capability}")
def get_contract(capability: str) -> dict:
    from configuration.config import ConfigurationManagerConfig
    config = ConfigurationManagerConfig()

    contract_def = load_contract(config.contracts_path, capability)
    if contract_def is None:
        raise HTTPException(status_code=404, detail=f"Contract not found for capability: {capability}")

    sources_config = load_sources_config(config.sources_config_path)
    provider_info = init_providers(sources_config)
    providers = provider_info["providers"]
    precedence = provider_info["precedence"]

    ordered = []
    for source_type in precedence:
        if source_type in providers:
            ordered.append(providers[source_type])

    raw_values: dict[str, str] = {}
    for provider in ordered:
        raw_values.update(provider.read())

    mapping_data = load_mapping(config.contracts_path, capability)
    mapping_rules = mapping_data.get("mapping", {})
    adapter = MappingAdapter(mapping_rules)
    resolved = adapter.map(raw_values)

    registry = get_registry()
    validation_result = registry.validate_contract(
        contract_def.get("name", capability),
        contract_def.get("version", "v1"),
        contract_def,
        resolved,
    )

    cache = get_cache()
    if validation_result.valid:
        cache.set(capability, contract_def.get("version", "v1"), {
            "contract": {
                "name": contract_def.get("name", capability),
                "version": contract_def.get("version", "v1"),
            },
            "status": "validated",
            "configuration": resolved,
            "validation": {
                "validated_at": validation_result.validated_at,
            },
        })

    if not validation_result.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "contract": {
                    "name": contract_def.get("name", capability),
                    "version": contract_def.get("version", "v1"),
                },
                "status": "invalid",
                "errors": validation_result.errors,
            },
        )

    cached = cache.get(capability, contract_def.get("version", "v1"))
    if cached is not None:
        return cached

    return {
        "contract": {
            "name": contract_def.get("name", capability),
            "version": contract_def.get("version", "v1"),
        },
        "status": "validated",
        "configuration": resolved,
        "validation": {
            "validated_at": validation_result.validated_at,
        },
    }


@router.get("/contracts/{capability}/raw")
def get_contract_raw(capability: str) -> dict:
    from configuration.config import ConfigurationManagerConfig
    config = ConfigurationManagerConfig()

    contract_def = load_contract(config.contracts_path, capability)
    if contract_def is None:
        raise HTTPException(status_code=404, detail=f"Contract not found for capability: {capability}")

    sources_config = load_sources_config(config.sources_config_path)
    provider_info = init_providers(sources_config)
    providers = provider_info["providers"]
    precedence = provider_info["precedence"]

    ordered = []
    for source_type in precedence:
        if source_type in providers:
            ordered.append(providers[source_type])

    raw_values: dict[str, str] = {}
    for provider in ordered:
        raw_values.update(provider.read())

    mapping_data = load_mapping(config.contracts_path, capability)
    mapping_rules = mapping_data.get("mapping", {})
    adapter = MappingAdapter(mapping_rules)
    resolved = adapter.map(raw_values)

    return {
        "contract": {
            "name": contract_def.get("name", capability),
            "version": contract_def.get("version", "v1"),
        },
        "status": "resolved",
        "configuration": resolved,
    }