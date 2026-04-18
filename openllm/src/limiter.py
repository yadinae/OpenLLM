"""Rate limiter for OpenLLM"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""

    capacity: int
    tokens: float = field(default_factory=lambda: float("inf"))
    refill_rate: float = 0.0
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: int = 1) -> bool:
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        if self.refill_rate > 0:
            new_tokens = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now


@dataclass
class ModelLimits:
    """Rate limits for a model"""

    rpm: int = 30
    tpm: int = 15000
    max_concurrent: int = 10
    daily_limit: int = 1000
    cost_limit: float = 0.0


class RateLimiter:
    """Rate limiter for managing request/token limits"""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._token_buckets: dict[str, TokenBucket] = {}
        self._concurrency: dict[str, asyncio.Semaphore] = {}
        self._daily_counts: dict[str, int] = {}
        self._daily_reset: dict[str, float] = {}
        self._limits: dict[str, ModelLimits] = {}

    def set_limits(self, model_name: str, limits: ModelLimits):
        self._limits[model_name] = limits

        self._buckets[model_name] = TokenBucket(capacity=limits.rpm, refill_rate=limits.rpm / 60.0)
        self._token_buckets[model_name] = TokenBucket(
            capacity=limits.tpm, refill_rate=limits.tpm / 60.0
        )
        self._concurrency[model_name] = asyncio.Semaphore(limits.max_concurrent)
        self._daily_counts[model_name] = 0
        self._daily_reset[model_name] = time.time()

    def get_semaphore(self, model_name: str) -> Optional[asyncio.Semaphore]:
        return self._concurrency.get(model_name)

    async def acquire(self, model_name: str, tokens: int = 1, wait: bool = True) -> bool:
        limit = self._limits.get(model_name)
        if not limit:
            return True

        bucket = self._buckets.get(model_name)
        if bucket:
            bucket.refill()
            if not bucket.consume(1):
                if wait:
                    await self._wait_for_rpm(model_name)
                    return await self.acquire(model_name, tokens, wait)
                return False

        token_bucket = self._token_buckets.get(model_name)
        if token_bucket:
            token_bucket.refill()
            if not token_bucket.consume(tokens):
                if wait:
                    await self._wait_for_tpm(model_name, tokens)
                    return await self.acquire(model_name, tokens, wait)
                return False

        self._check_daily_limit(model_name)

        return True

    async def release(self, model_name: str, tokens: int = 1):
        pass

    async def wait_for_rpm(self, model_name: str) -> float:
        bucket = self._buckets.get(model_name)
        if not bucket:
            return 0.0

        bucket.refill()
        wait_time = (1 - bucket.tokens) / bucket.refill_rate if bucket.refill_rate > 0 else 0
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        return wait_time

    async def wait_for_tpm(self, model_name: str, tokens: int) -> float:
        bucket = self._token_buckets.get(model_name)
        if not bucket:
            return 0.0

        bucket.refill()
        needed = tokens - bucket.tokens
        wait_time = needed / bucket.refill_rate if bucket.refill_rate > 0 else 0
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        return wait_time

    def _check_daily_limit(self, model_name: str):
        limit = self._limits.get(model_name)
        if not limit or limit.daily_limit <= 0:
            return

        now = time.time()
        if now - self._daily_reset.get(model_name, 0) > 86400:
            self._daily_counts[model_name] = 0
            self._daily_reset[model_name] = now

        count = self._daily_counts.get(model_name, 0)
        if count >= limit.daily_limit:
            raise RateLimitExceeded(f"Daily limit exceeded for {model_name}")

        self._daily_counts[model_name] = count + 1

    def check_limit(self, model_name: str) -> bool:
        limit = self._limits.get(model_name)
        if not limit:
            return True

        bucket = self._buckets.get(model_name)
        if bucket:
            bucket.refill()
            if bucket.tokens < 1:
                return False

        return True


class RateLimitExceeded(Exception):
    """Rate limit exceeded exception"""

    pass


_global_limiter: Optional[RateLimiter] = None


def get_limiter() -> RateLimiter:
    """Get global rate limiter"""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter()
    return _global_limiter
