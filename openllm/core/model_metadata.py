"""模型元数据注册表 — 聚合 provider API、用户配置、默认值"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelMetadata:
    model_id: str
    provider: str
    context_length: int = 4096
    capabilities: list[str] = field(default_factory=lambda: ["text"])
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_tool_use: bool = False
    supports_streaming: bool = True
    pricing_input_per_1k: float = 0.0
    pricing_output_per_1k: float = 0.0
    max_output_tokens: int | None = None


class ModelMetadataRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}

    def update_from_api(self, provider: str, models: list[dict]) -> None:
        for m in models:
            mid = m.get("id", "")
            key = f"{provider}/{mid}"
            existing = self._models.get(key)
            if existing:
                continue
            caps = m.get("capabilities", ["text"])
            self._models[key] = ModelMetadata(
                model_id=key,
                provider=provider,
                context_length=m.get("context_length", 4096),
                capabilities=caps,
                supports_reasoning=m.get("supports_reasoning", False),
                supports_vision=m.get("supports_vision", False),
                supports_tool_use=m.get("supports_tool_use", False),
                supports_streaming=m.get("supports_streaming", True),
                pricing_input_per_1k=m.get("pricing_input_per_1k", 0.0),
                pricing_output_per_1k=m.get("pricing_output_per_1k", 0.0),
                max_output_tokens=m.get("max_output_tokens"),
            )

    def update_from_config(self, config: dict[str, dict[str, Any]]) -> None:
        for model_key, overrides in config.items():
            existing = self._models.get(model_key)
            if existing:
                for k, v in overrides.items():
                    if hasattr(existing, k):
                        setattr(existing, k, v)
            else:
                provider = model_key.split("/")[0] if "/" in model_key else ""
                valid_fields = ModelMetadata.__dataclass_fields__
                filtered = {k: v for k, v in overrides.items() if k in valid_fields}
                self._models[model_key] = ModelMetadata(
                    model_id=model_key,
                    provider=provider,
                    **filtered,
                )

    def get(self, model_id: str) -> ModelMetadata | None:
        return self._models.get(model_id)

    def list_all(self) -> list[ModelMetadata]:
        return list(self._models.values())
