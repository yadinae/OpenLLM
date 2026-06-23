"""冷却管理 — 持久化 Provider/密钥冷却状态（参考 FreeRide 设计）"""

from __future__ import annotations

import asyncio
import time
import logging
# from pathlib import Path  # imported via state

from .state import get_data_dir, read_json, write_json_atomic

logger = logging.getLogger(__name__)


class CooldownManager:
    """冷却管理器

    跟踪 Provider 和密钥的冷却状态，支持持久化。
    冷却中的 Provider 在路由时自动跳过。
    """

    def __init__(self, lazy_load: bool = True):
        self._cooldowns: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._loaded = False
        if not lazy_load:
            # 仅用于同步测试，生产环境应使用 await init()
            pass
    
    async def init(self) -> None:
        """异步初始化，从磁盘加载冷却数据"""
        if self._loaded:
            return
        self._loaded = True
        data = await read_json(get_data_dir() / "cooldown.json", {})
        self._cooldowns = data.get("cooldowns", {})
        # 清理过期条目
        now = time.time()
        expired = [k for k, v in self._cooldowns.items() if v.get("until", 0) <= now]
        for k in expired:
            del self._cooldowns[k]
        if expired:
            await self._save()
    
    async def _save(self) -> None:
        await write_json_atomic(
            get_data_dir() / "cooldown.json",
            {"cooldowns": self._cooldowns}
        )
    
    async def set_cooldown(self, key: str, duration: float = 60.0, reason: str = "") -> None:
        """设置冷却
        
        Args:
            key: 冷却标识（如 "provider:groq" 或 "key:groq:sk-xxx"）
            duration: 冷却时长（秒）
            reason: 冷却原因
        """
        if not self._loaded:
            await self.init()
        async with self._lock:
            until = time.time() + duration
            self._cooldowns[key] = {
                "until": until,
                "reason": reason or "rate_limit",
                "set_at": time.time(),
            }
            await self._save()
        logger.info("Cooldown set for %s: %.0fs (%s)", key, duration, reason)
    
    async def is_cooled(self, key: str) -> bool:
        """检查是否在冷却中"""
        if not self._loaded:
            await self.init()
        async with self._lock:
            entry = self._cooldowns.get(key)
            if entry is None:
                return False
            if entry["until"] <= time.time():
                del self._cooldowns[key]
                await self._save()
                return False
            return True
    
    async def get_remaining(self, key: str) -> float:
        """获取剩余冷却时间（秒）"""
        if not self._loaded:
            await self.init()
        async with self._lock:
            entry = self._cooldowns.get(key)
            if entry is None:
                return 0.0
            remaining = entry["until"] - time.time()
            return max(0.0, remaining)
    
    async def clear(self, key: str | None = None) -> None:
        """清除冷却"""
        if not self._loaded:
            await self.init()
        async with self._lock:
            if key:
                self._cooldowns.pop(key, None)
            else:
                self._cooldowns.clear()
            await self._save()
