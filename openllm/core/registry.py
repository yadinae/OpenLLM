"""Provider 注册表 — 插件发现与管理"""

from __future__ import annotations

import asyncio
import logging
from .provider import Provider
from .state import get_data_dir, write_json_atomic

logger = logging.getLogger(__name__)


class Registry:
    """Provider 注册表

    管理所有已注册的 Provider 插件。
    Provider 通过名称注册，支持热重载。
    """

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._models_cache: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()

    def register(self, name: str, provider: Provider) -> None:
        """注册 Provider"""
        self._providers[name] = provider
        logger.info("Registered provider: %s (api_version=%d)", name, provider.api_version)

    def get(self, name: str) -> Provider | None:
        """获取 Provider 实例"""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """列出所有已注册的 Provider 名称"""
        return list(self._providers.keys())

    async def discover_models(self) -> dict[str, list[dict]]:
        """从所有 Provider 发现模型"""
        results = {}
        for name, provider in self._providers.items():
            try:
                models = await provider.list_models()
                results[name] = models
            except Exception as e:
                logger.warning("Failed to discover models from %s: %s", name, e)
                results[name] = []
        self._models_cache = results
        return results

    def get_cached_models(self) -> list[dict]:
        """获取缓存的模型列表（平铺）"""
        flat = []
        for provider, models in self._models_cache.items():
            for m in models:
                flat.append({
                    "id": m.get("id", ""),
                    "provider": provider,
                    "name": m.get("name", m.get("id", "")),
                    "is_free": m.get("is_free", False),
                    "context_length": m.get("context_length", 4096),
                    "capabilities": m.get("capabilities", ["text"]),
                    "supports_reasoning": m.get("supports_reasoning", False),
                    "supports_vision": m.get("supports_vision", False),
                })
        return flat

    async def save_snapshot(self) -> None:
        """保存注册表快照到磁盘"""
        data_dir = get_data_dir()
        snapshot = {
            "providers": list(self._providers.keys()),
            "models_count": len(self.get_cached_models()),
        }
        await write_json_atomic(data_dir / "registry.json", snapshot)
