"""Model tester for OpenLLM"""

import re
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.adapter_model import ModelConfig
from src.adapters.base import create_adapter
from src.models import ChatRequest, Message

logger = logging.getLogger(__name__)


CAPABILITY_TESTS = {
    "coding": (
        "Write a Python function that returns the first 10 fibonacci numbers. Just output the code.",
        lambda r: "def fibonacci" in r or "fibonacci" in r.lower(),
    ),
    "math": (
        "Calculate 123 * 456. Show your reasoning step by step.",
        lambda r: "59268" in r or "5*456" in r.lower(),
    ),
    "reasoning": (
        "If all roses are flowers and some flowers fade quickly, what can we conclude about roses?",
        lambda r: len(r) > 50,
    ),
    "json": (
        'Output a valid JSON object with exactly {"name": "test", "age": 25}',
        lambda r: "{" in r or '"name"' in r,
    ),
}


@dataclass
class ModelTestResult:
    model_name: str
    available: bool
    response_time_ms: float
    rpm_limit: int = 0
    tpm_limit: int = 0
    max_context_length: int = 0
    model_size: str = ""
    capabilities: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    error: Optional[str] = None
    tested_at: datetime = None

    def __post_init__(self):
        if self.tested_at is None:
            self.tested_at = datetime.now()


class ModelTester:
    def __init__(self, registry):
        self.registry = registry

    async def test_model(self, config: ModelConfig) -> ModelTestResult:
        try:
            api_key = self._resolve_env_var(config.api_key)

            adapter_config = type(
                "AdapterConfig",
                (),
                {
                    "model": config.name,
                    "protocol": config.protocol,
                    "endpoint": config.endpoint,
                    "api_key": api_key,
                },
            )()

            adapter = create_adapter(config.protocol, adapter_config)

            start = time.time()
            messages = [{"role": "user", "content": "Hello, respond with just 'OK'"}]
            response = await adapter.chat_completions(messages)
            response_time = (time.time() - start) * 1000

            content = response.choices[0].message.content
            available = "OK" in content

            capabilities = await self._detect_capabilities(adapter, config)
            model_size = self._extract_model_size(config.name)

            await adapter.close()

            return ModelTestResult(
                model_name=config.name,
                available=available,
                response_time_ms=response_time,
                max_context_length=config.max_context_length,
                model_size=model_size,
                capabilities=capabilities,
            )
        except Exception as e:
            logger.error(f"Test failed for {config.name}: {e}")
            return ModelTestResult(
                model_name=config.name, available=False, response_time_ms=0, error=str(e)
            )

    async def _detect_capabilities(self, adapter, config) -> list[str]:
        capabilities = []
        for cap, (prompt, check_fn) in CAPABILITY_TESTS.items():
            try:
                messages = [{"role": "user", "content": prompt}]
                response = await adapter.chat_completions(messages)
                content = response.choices[0].message.content
                if check_fn(content):
                    capabilities.append(cap)
            except Exception:
                pass
        return capabilities

    def _extract_model_size(self, model_name: str) -> str:
        match = re.search(r"(\d+[bB])", model_name)
        return match.group(1) if match else ""

    def _resolve_env_var(self, value: str) -> str:
        if not value:
            return ""
        import os

        pattern = r"\$\{(\w+)\}"
        match = re.match(pattern, value)
        if match:
            env_var = match.group(1)
            return os.environ.get(env_var, "")
        return value

    async def test_all_models(self, enabled_only: bool = True) -> list[ModelTestResult]:
        results = []
        for config in self.registry.list_models():
            if enabled_only and not config.enabled:
                continue
            result = await self.test_model(config)
            results.append(result)
        return results

    def update_config(self, results: list[ModelTestResult], config_path: Path):
        import yaml

        config_path = Path(config_path)
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        for result in results:
            for model in data.get("models", []):
                if model.get("name") == result.model_name:
                    if result.available:
                        model["rpm"] = result.rpm_limit or model.get("rpm", 30)
                        model["tpm"] = result.tpm_limit or model.get("tpm", 15000)
                        model["max_context_length"] = result.max_context_length or model.get(
                            "max_context_length", 128000
                        )
                        model["capabilities"] = result.capabilities

        with open(config_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Updated {len(results)} models in {config_path}")
