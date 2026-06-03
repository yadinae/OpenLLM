"""OpenLLM 错误类型体系"""

from __future__ import annotations

from .types import ErrorKind


class OpenLLMError(Exception):
    """基础异常"""
    def __init__(self, message: str, kind: ErrorKind = ErrorKind.UNKNOWN):
        self.kind = kind
        self.message = message
        super().__init__(message)


class ProviderError(OpenLLMError):
    """Provider 层错误"""
    def __init__(self, message: str, provider: str, kind: ErrorKind = ErrorKind.UNKNOWN,
                 status_code: int = 500):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message, kind)


class ModelNotFoundError(ProviderError):
    """模型未找到"""
    def __init__(self, model: str, provider: str = ""):
        self.model = model
        super().__init__(
            f"Model '{model}' not found in provider '{provider}'",
            provider, ErrorKind.MODEL_NOT_FOUND, 404
        )


class RateLimitError(ProviderError):
    """速率限制"""
    def __init__(self, provider: str, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited by {provider}, retry after {retry_after}s",
            provider, ErrorKind.RATE_LIMIT, 429
        )


class AuthError(ProviderError):
    """认证失败"""
    def __init__(self, provider: str):
        super().__init__(
            f"Authentication failed for {provider}",
            provider, ErrorKind.AUTH, 401
        )


class AllProvidersFailedError(OpenLLMError):
    """所有 Provider 都失败了"""
    def __init__(self, failures: list[tuple[str, str]]):
        self.failures = failures
        detail = "; ".join(f"{p}: {e}" for p, e in failures)
        super().__init__(
            f"All providers failed: {detail}",
            ErrorKind.SERVER_ERROR
        )


class ConfigurationError(OpenLLMError):
    """配置错误"""
    def __init__(self, message: str):
        super().__init__(message, ErrorKind.INVALID_REQUEST)
