"""Combo 链路由引擎 — 智能故障转移（参考 OmniRoute/9router 设计）"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from .types import ChatRequest, ChatResponse, ComboConfig, RoutingStrategy, ErrorKind
from .errors import AllProvidersFailedError, ProviderError
from .cooldown import CooldownManager
from .registry import Registry
from .health import HealthScoreTracker

logger = logging.getLogger(__name__)


class ComboEngine:
    """Combo 路由引擎"""

    def __init__(self, registry: Registry, cooldown: CooldownManager,
                 health_tracker: HealthScoreTracker | None = None):
        self._registry = registry
        self._cooldown = cooldown
        self._health_tracker = health_tracker or HealthScoreTracker()
        self._rr_index: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _sorted_by_health(self, members: list) -> list:
        groups = defaultdict(list)
        for m in members:
            groups[m.priority].append(m)
        result = []
        for priority in sorted(groups.keys()):
            group = groups[priority]
            group.sort(
                key=lambda m: self._health_tracker.get_score(m.provider) * m.weight,
                reverse=True,
            )
            result.extend(group)
        return result

    async def execute(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
        if combo.strategy in (RoutingStrategy.FALLBACK, RoutingStrategy.PRIORITY):
            return await self._execute_fallback(combo, request)
        elif combo.strategy == RoutingStrategy.ROUND_ROBIN:
            return await self._execute_round_robin(combo, request)
        else:
            return await self._execute_fallback(combo, request)

    async def execute_stream(self, combo: ComboConfig, request: ChatRequest):
        sorted_members = self._sorted_by_health(combo.members)
        failures = []

        for member in sorted_members:
            cool_key = f"provider:{member.provider}"
            if await self._cooldown.is_cooled(cool_key):
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
                first_chunk.actual_provider = member.provider
                first_chunk.actual_model = member.model
                yield first_chunk
                async for chunk in stream:
                    chunk.actual_provider = member.provider
                    chunk.actual_model = member.model
                    yield chunk
                self._health_tracker.record_success(member.provider, 0)
                return
            except StopAsyncIteration:
                failures.append((member.provider, "empty stream"))
            except ProviderError as e:
                logger.warning("Combo stream member %s failed: %s", member.provider, e)
                self._health_tracker.record_failure(member.provider, e.kind)
                await self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
            except Exception as e:
                logger.error("Combo stream member %s error: %s", member.provider, e)
                self._health_tracker.record_failure(member.provider, ErrorKind.UNKNOWN)
                await self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))

        raise AllProvidersFailedError(failures)

    async def _execute_fallback(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
        sorted_members = self._sorted_by_health(combo.members)
        failures: list[tuple[str, str]] = []

        for member in sorted_members:
            cool_key = f"provider:{member.provider}"
            if await self._cooldown.is_cooled(cool_key):
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
                self._health_tracker.record_success(member.provider, 0)
                return response
            except ProviderError as e:
                logger.warning("Provider %s failed: %s", member.provider, e)
                self._health_tracker.record_failure(member.provider, e.kind)
                await self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
            except Exception as e:
                logger.error("Unexpected error from %s: %s", member.provider, e)
                self._health_tracker.record_failure(member.provider, ErrorKind.UNKNOWN)
                await self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))

        raise AllProvidersFailedError(failures)

    async def _execute_round_robin(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
        available = []
        for m in combo.members:
            if await self._cooldown.is_cooled(f"provider:{m.provider}"):
                logger.debug("RR skipping cooled: %s", m.provider)
                continue
            if self._health_tracker.get_score(m.provider) < 30:
                logger.debug("RR skipping unhealthy: %s (score=%.0f)",
                             m.provider, self._health_tracker.get_score(m.provider))
                continue
            available.append(m)

        if not available:
            raise AllProvidersFailedError([("all", "no available providers")])

        start_idx = self._rr_index.get(combo.name, 0) % len(available)
        failures = []

        for offset in range(len(available)):
            idx = (start_idx + offset) % len(available)
            member = available[idx]
            self._rr_index[combo.name] = idx + 1

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
                self._health_tracker.record_success(member.provider, 0)
                return response
            except ProviderError as e:
                logger.warning("RR member %s failed: %s", member.provider, e)
                self._health_tracker.record_failure(member.provider, e.kind)
                await self._record_failure(member.provider, e)
                failures.append((member.provider, str(e)))
            except Exception as e:
                logger.error("RR member %s error: %s", member.provider, e)
                self._health_tracker.record_failure(member.provider, ErrorKind.UNKNOWN)
                failures.append((member.provider, str(e)))

        raise AllProvidersFailedError(failures)

    async def _record_failure(self, provider_name: str, exc: Exception) -> None:
        if isinstance(exc, ProviderError):
            duration = self._cooldown_duration(exc.kind.value)
            await self._cooldown.set_cooldown(f"provider:{provider_name}", duration, exc.kind.value)
        else:
            await self._cooldown.set_cooldown(f"provider:{provider_name}", 60, "unknown")

    def _cooldown_duration(self, error_kind: str) -> float:
        durations = {
            "rate_limit": 120.0, "auth": 300.0, "quota_exhausted": 3600.0,
            "timeout": 30.0, "server_error": 60.0, "overloaded": 120.0,
            "model_not_found": 600.0,
        }
        return durations.get(error_kind, 60.0)
