"""Combo 链路由引擎 — 智能故障转移（参考 OmniRoute/9router 设计）"""

from __future__ import annotations

import asyncio
import logging

from .types import ChatRequest, ChatResponse, ComboConfig, RoutingStrategy
from .errors import AllProvidersFailedError, ProviderError
from .cooldown import CooldownManager
from .registry import Registry

logger = logging.getLogger(__name__)


class ComboEngine:
    """Combo 路由引擎
    
    支持多种路由策略：
    - fallback: 按优先级降级尝试，全部失败则报错
    - round_robin: 轮询 + 失败自动 fallback 到下一可用成员
    - priority: 始终选最高优先级可用模型
    """
    
    def __init__(self, registry: Registry, cooldown: CooldownManager):
        self._registry = registry
        self._cooldown = cooldown
        self._rr_index: dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def execute(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
        """执行 Combo 路由"""
        if combo.strategy in (RoutingStrategy.FALLBACK, RoutingStrategy.PRIORITY):
            return await self._execute_fallback(combo, request)
        elif combo.strategy == RoutingStrategy.ROUND_ROBIN:
            return await self._execute_round_robin(combo, request)
        else:
            return await self._execute_fallback(combo, request)
    
    async def execute_stream(self, combo: ComboConfig, request: ChatRequest):
        """流式执行 — 逐个尝试成员，首 chunk 到达后锁定
        
        注意：这个方法返回的是 async generator。
        调用方需要 async for chunk in engine.execute_stream(...):
        """
        sorted_members = sorted(combo.members, key=lambda m: m.priority)
        failures = []
        
        for member in sorted_members:
            cool_key = f"provider:{member.provider}"
            if self._cooldown.is_cooled(cool_key):
                failures.append((member.provider, "cooled"))
                continue
            
            provider = self._registry.get(member.provider)
            if not provider:
                failures.append((member.provider, "not registered"))
                continue
            
            req = ChatRequest(
                model=member.model,
                messages=request.messages,
                stream=True,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            
            try:
                stream = provider.chat_completion_stream(req)
                first_chunk = await stream.__anext__()
                # 首 chunk 到达 → 锁定，转发首块 + 后续
                yield first_chunk
                async for chunk in stream:
                    yield chunk
                return  # 正常结束
            except StopAsyncIteration:
                failures.append((member.provider, "empty stream"))
            except ProviderError as e:
                logger.warning("Combo stream member %s failed: %s", member.provider, e)
                self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
            except Exception as e:
                logger.error("Combo stream member %s error: %s", member.provider, e)
                self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
        
        raise AllProvidersFailedError(failures)
    
    async def _execute_fallback(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
        """Fallback 策略 — 按优先级尝试，失败切下一成员"""
        sorted_members = sorted(combo.members, key=lambda m: m.priority)
        failures: list[tuple[str, str]] = []
        
        for member in sorted_members:
            cool_key = f"provider:{member.provider}"
            if self._cooldown.is_cooled(cool_key):
                failures.append((member.provider, "cooled"))
                continue
            
            provider = self._registry.get(member.provider)
            if not provider:
                failures.append((member.provider, "not registered"))
                continue
            
            try:
                req = ChatRequest(
                    model=member.model,
                    messages=request.messages,
                    stream=False,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                response = await provider.chat_completion(req)
                response.actual_provider = member.provider
                response.actual_model = member.model
                return response
            except ProviderError as e:
                logger.warning("Provider %s failed: %s", member.provider, e)
                self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
            except Exception as e:
                logger.error("Unexpected error from %s: %s", member.provider, e)
                self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
        
        raise AllProvidersFailedError(failures)
    
    async def _execute_round_robin(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
        """Round-Robin 策略 — 轮询 + 失败自动 fallback（P1-3 修复）"""
        # 先过滤冷却中的成员
        available = []
        for m in combo.members:
            if not self._cooldown.is_cooled(f"provider:{m.provider}"):
                available.append(m)
            else:
                logger.debug("RR skipping cooled: %s", m.provider)
        
        if not available:
            raise AllProvidersFailedError([("all", "no available providers")])
        
        # 从当前索引开始尝试（最多尝试所有可用成员）
        start_idx = self._rr_index.get(combo.name, 0) % len(available)
        failures = []
        
        for offset in range(len(available)):
            idx = (start_idx + offset) % len(available)
            member = available[idx]
            self._rr_index[combo.name] = idx + 1  # 下次从下一个开始
            
            provider = self._registry.get(member.provider)
            if not provider:
                failures.append((member.provider, "not registered"))
                continue
            
            try:
                req = ChatRequest(
                    model=member.model,
                    messages=request.messages,
                    stream=False,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                response = await provider.chat_completion(req)
                response.actual_provider = member.provider
                response.actual_model = member.model
                return response
            except ProviderError as e:
                logger.warning("RR member %s failed: %s", member.provider, e)
                self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
            except Exception as e:
                logger.error("RR member %s error: %s", member.provider, e)
                failures.append((member.provider, str(e)))
        
        raise AllProvidersFailedError(failures)
    
    def _record_failure(self, provider_name: str, exc: Exception) -> None:
        """记录失败并自动设置冷却"""
        if isinstance(exc, ProviderError):
            duration = self._cooldown_duration(exc.kind.value)
            self._cooldown.set_cooldown(f"provider:{provider_name}", duration, exc.kind.value)
        else:
            self._cooldown.set_cooldown(f"provider:{provider_name}", 60, "unknown")
    
    def _cooldown_duration(self, error_kind: str) -> float:
        durations = {
            "rate_limit": 120.0, "auth": 300.0, "quota_exhausted": 3600.0,
            "timeout": 30.0, "server_error": 60.0, "overloaded": 120.0,
            "model_not_found": 600.0,
        }
        return durations.get(error_kind, 60.0)
