"""FreeRide - Free LLM Auto-Discovery and Connection"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.adapter_model import ModelConfig
from src.registry import get_registry

logger = logging.getLogger(__name__)


FREE_PROVIDERS = {
    "groq": {
        "name": "Groq",
        "endpoint": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "protocol": "openai",
        "models": [
            {"name": "llama-3.3-70b-versatile", "rpm": 30, "tpm": 14400, "context": 131072},
            {"name": "llama-3.1-8b-instant", "rpm": 30, "tpm": 14400, "context": 131072},
            {"name": "qwen3-32b", "rpm": 30, "tpm": 14400, "context": 131072},
        ],
    },
    "cerebras": {
        "name": "Cerebras",
        "endpoint": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY",
        "protocol": "openai",
        "models": [
            {"name": "llama3.1-8b", "rpm": 30, "tpm": 1000000, "context": 128000},
            {"name": "qwen-3-235b-a22b-instruct", "rpm": 30, "tpm": 1000000, "context": 131072},
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "protocol": "openai",
        "models": [
            {"name": "deepseek/deepseek-r1-0528:free", "rpm": 20, "tpm": 100000, "context": 163072},
            {
                "name": "meta-llama/llama-3.3-70b-instruct:free",
                "rpm": 20,
                "tpm": 100000,
                "context": 65000,
            },
        ],
    },
    "mistral": {
        "name": "Mistral",
        "endpoint": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "protocol": "openai",
        "models": [
            {"name": "mistral-small-latest", "rpm": 30, "tpm": 15000, "context": 128000},
            {"name": "codestral-latest", "rpm": 30, "tpm": 15000, "context": 256000},
        ],
    },
    "gemini": {
        "name": "Google Gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": "GEMINI_API_KEY",
        "protocol": "openai",
        "models": [
            {"name": "gemini-2.5-flash", "rpm": 10, "tpm": 1000000, "context": 1048576},
        ],
    },
    "ollama": {
        "name": "Ollama",
        "endpoint": "http://localhost:11434",
        "api_key_env": "",
        "protocol": "ollama",
        "models": [
            {"name": "llama3", "rpm": 100, "tpm": 999999, "context": 8192},
            {"name": "mistral", "rpm": 100, "tpm": 999999, "context": 8192},
        ],
    },
}


@dataclass
class FreeRideConfig:
    enabled: bool = False
    providers: list[str] = field(default_factory=list)


class FreeRideManager:
    def __init__(self, registry=None):
        self.registry = registry or get_registry()
        self.config = FreeRideConfig()

    def load_config(self, config_path: Path):
        import yaml

        settings_path = config_path.parent / "settings.yaml"
        if settings_path.exists():
            with open(settings_path) as f:
                data = yaml.safe_load(f) or {}
            fr = data.get("freeride", {})
            self.config.enabled = fr.get("enabled", False)
            self.config.providers = fr.get("providers", list(FREE_PROVIDERS.keys()))

    def get_free_providers(self, selected: list[str] = None) -> dict:
        if selected:
            return {k: v for k, v in FREE_PROVIDERS.items() if k in selected}
        return FREE_PROVIDERS

    async def enable(self, providers: list[str] = None) -> list[ModelConfig]:
        """Enable FreeRide mode and discover models."""
        provider_configs = self.get_free_providers(providers)
        added = []

        for provider_key, provider in provider_configs.items():
            api_key = os.environ.get(provider["api_key_env"], "")

            if not api_key and provider["api_key_env"]:
                logger.warning(
                    f"API key not found for {provider['name']}: {provider['api_key_env']}"
                )
                continue

            for model in provider["models"]:
                model_name = model["name"]

                if model_name in self.registry._models:
                    logger.info(f"Model already exists: {model_name}")
                    continue

                config = ModelConfig(
                    name=model["name"],
                    protocol=provider["protocol"],
                    endpoint=provider["endpoint"],
                    api_key=f"${{{provider['api_key_env']}}}" if provider["api_key_env"] else "",
                    enabled=True,
                    rpm=model.get("rpm", 30),
                    tpm=model.get("tpm", 15000),
                    max_context_length=model.get("context", 128000),
                    capabilities=["text", "coding"],
                )
                self.registry._models[config.name] = config
                added.append(config)
                logger.info(f"FreeRide added: {config.name}")

        return added

    def disable(self):
        """Disable FreeRide mode - remove free models."""
        to_remove = []
        for name in self.registry._models:
            for provider_key in FREE_PROVIDERS:
                if provider_key in name.lower():
                    to_remove.append(name)
                    break

        for name in to_remove:
            if name in self.registry._models:
                del self.registry._models[name]
                logger.info(f"FreeRide removed: {name}")

    def get_status(self) -> dict:
        """Get FreeRide status."""
        free_models = []
        for name in self.registry._models.keys():
            for provider_key in FREE_PROVIDERS:
                if provider_key in name.lower():
                    free_models.append(name)
                    break

        available_providers = []
        for provider_key, provider in FREE_PROVIDERS.items():
            if os.environ.get(provider["api_key_env"], ""):
                available_providers.append(provider_key)

        return {
            "enabled": self.config.enabled,
            "configured_providers": list(FREE_PROVIDERS.keys()),
            "available_providers": available_providers,
            "free_models_count": len(free_models),
        }
