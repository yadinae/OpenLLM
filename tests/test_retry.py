"""重试包装器单元测试"""
from __future__ import annotations

import pytest

from openllm.core.retry import retry_with_backoff, _is_retryable
from openllm.core.errors import (
    ProviderError, AuthError, ErrorKind,
)


class TestRetryWithBackoff:
    async def test_success_no_retry(self):
        """成功调用不触发重试"""
        call_count = 0

        async def ok():
            nonlocal call_count
            call_count += 1
            return "done"

        result = await retry_with_backoff(ok, max_retries=3)
        assert result == "done"
        assert call_count == 1

    async def test_retry_on_transient_error(self):
        """瞬态错误触发重试"""
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderError("timeout", "test", ErrorKind.TIMEOUT, 504)
            return "ok"

        result = await retry_with_backoff(flaky, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 3

    async def test_auth_error_not_retried(self):
        """AuthError 不重试，立即抛出"""

        async def auth_fail():
            raise AuthError("test")

        with pytest.raises(AuthError):
            await retry_with_backoff(auth_fail, max_retries=3, base_delay=0.01)


class TestIsRetryable:
    def test_retryable_status_codes(self):
        for code in [429, 500, 502, 503, 504]:
            exc = ProviderError("err", "test", ErrorKind.SERVER_ERROR, code)
            assert _is_retryable(exc), f"{code} should be retryable"

    def test_non_retryable_status_codes(self):
        exc = ProviderError("err", "test", ErrorKind.INVALID_REQUEST, 400)
        assert not _is_retryable(exc)

    def test_connection_error_retryable(self):
        assert _is_retryable(ConnectionError("refused"))
