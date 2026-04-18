"""Model registry for OpenLLM"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Optional
import yaml
from src.adapter_model import AdapterConfig, ModelConfig
from src.adapters.base import ProtocolAdapter, create_adapter
from src.enums import ProtocolType

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing models"""

    def __init__(self):
        self._models: dict[str, ModelConfig] = {}
        self._adapters: dict[str, ProtocolAdapter] = {}

    def load_from_yaml(self, config_path: str | Path) -> None:
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return

        with open(path) as f:
            config_data = yaml.safe_load(f)

        models = config_data.get("models", [])
        for model_data in models:
            config = ModelConfig(**model_data)
            if config.enabled:
                self._models[config.name] = config

        logger.info(f"Loaded {len(self._models)} models from {config_path}")

    def get_model(self, name: str) -> Optional[ModelConfig]:
        return self._models.get(name)

    def list_models(self) -> list[ModelConfig]:
        return list(self._models.values())

    def get_adapter(self, name: str) -> Optional[ProtocolAdapter]:
        return self._adapters.get(name)

    def get_or_create_adapter(self, model_name: str) -> Optional[ProtocolAdapter]:
        if model_name in self._adapters:
            return self._adapters[model_name]

        model = self._models.get(model_name)
        if not model:
            return None

        api_key = self._resolve_env_var(model.api_key)

        config = AdapterConfig(
            model=model.name,
            protocol=model.protocol,
            endpoint=model.endpoint,
            api_key=api_key,
        )

        adapter = create_adapter(model.protocol, config)
        self._adapters[model_name] = adapter
        return adapter

    def _resolve_env_var(self, value: str) -> str:
        if not value:
            return ""
        pattern = r"\$\{(\w+)\}"
        match = re.match(pattern, value)
        if match:
            env_var = match.group(1)
            return os.environ.get(env_var, "")
        return value

    def get_enabled_models(
        self, model_type: Optional[str] = None, model_scale: Optional[str] = None
    ) -> list[ModelConfig]:
        models = []
        for model in self._models.values():
            if not model.enabled:
                continue
            if model_type and model.capabilities:
                if model_type not in model.capabilities:
                    continue
            models.append(model)
        return models

    async def close_all(self):
        for adapter in self._adapters.values():
            await adapter.close()
        self._adapters.clear()

    async def discover_models(self, config_path: str | Path) -> list[ModelConfig]:
        """Discover models from all configured providers."""
        from pathlib import Path as PathType

        config_path = PathType(config_path)
        discovered = []

        models_to_check = list(self._models.values())

        for model in models_to_check:
            adapter = self.get_or_create_adapter(model.name)
            if not adapter:
                continue

            try:
                model_infos = await adapter.list_available_models()
                for mi in model_infos:
                    if mi.id in self._models:
                        continue

                    config = ModelConfig(
                        name=mi.id,
                        protocol=model.protocol,
                        endpoint=model.endpoint,
                        api_key=model.api_key,
                        enabled=False,
                        rpm=model.rpm,
                        tpm=model.tpm,
                        max_concurrent=model.max_concurrent,
                        daily_limit=model.daily_limit,
                        quality_weight=model.quality_weight,
                        speed_weight=model.speed_weight,
                        context_weight=model.context_weight,
                        reliability_weight=model.reliability_weight,
                        max_context_length=model.max_context_length,
                        capabilities=model.capabilities,
                    )
                    self._models[config.name] = config
                    discovered.append(config)
                    logger.info(f"Discovered model: {config.name}")
            except Exception as e:
                logger.warning(f"Failed to discover from {model.name}: {e}")

        if discovered:
            self._save_to_yaml(config_path, discovered)

        return discovered

    def _save_to_yaml(self, config_path: Path, new_models: list[ModelConfig]):
        """Save newly discovered models to YAML config."""
        existing_data = {}
        if config_path.exists():
            with open(config_path) as f:
                existing_data = yaml.safe_load(f) or {}

        existing_models = existing_data.get("models", [])
        existing_names = {m.get("name") for m in existing_models}

        for new_model in new_models:
            if new_model.name not in existing_names:
                existing_models.append(new_model.model_dump())

        existing_data["models"] = existing_models

        with open(config_path, "w") as f:
            yaml.safe_dump(existing_data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved {len(new_models)} new models to {config_path}")


class RegistryManager:
    """Singleton registry manager"""

    _instance: Optional[ModelRegistry] = None

    @classmethod
    def get_instance(cls) -> ModelRegistry:
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    @classmethod
    def reset(cls):
        if cls._instance:
            import asyncio

            asyncio.get_event_loop().run_until_complete(cls._instance.close_all())
        cls._instance = None


def get_registry() -> ModelRegistry:
    """Get the global model registry"""
    return RegistryManager.get_instance()
