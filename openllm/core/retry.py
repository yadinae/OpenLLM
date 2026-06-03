"""重试包装器 — 指数退避重试（针对 Provider 瞬态失败）"""

from __future__ import annotations

import asyncio
import logging
from typing import TypeVar, Callable, Awaitable

from openllm.core.errors import RateLimitError, AuthError

T = TypeVar("T")
logger = logging.getLogger(__name__)

# 可重试的错误状态码
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs,
) -> T:
    """指数退避重试

    Args:
        fn: 异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）

    Returns:
        函数返回值

    Raises:
        最后一次尝试的异常（不可重试的错误立即抛出）
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except AuthError:
            # 认证错误不可重试
            raise
        except RateLimitError as e:
            # 速率限制 — 按服务端建议等待
            last_exc = e
            if attempt >= max_retries:
                break
            retry_after = getattr(e, "retry_after", base_delay * (2 ** attempt))
            delay = min(retry_after, max_delay)
        except Exception as e:
            last_exc = e
            if attempt >= max_retries:
                break
            # 判断是否可重试
            if not _is_retryable(e):
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)

        logger.warning(
            "Retry %d/%d after %.1fs: %s",
            attempt + 1, max_retries, delay, last_exc,
        )
        await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]


def _is_retryable(exc: Exception) -> bool:
    """判断是否为可重试的异常"""
    from openllm.core.errors import ProviderError
    if isinstance(exc, ProviderError):
        return exc.status_code in RETRYABLE_STATUSES
    # 网络超时/连接错误等
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError)):
        return True
    # httpx 原生异常（在 ProviderError 分类前抛出）
    try:
        import httpx
        if isinstance(exc, (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError)):
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code in RETRYABLE_STATUSES
            return True
    except ImportError:
        pass
    return False
