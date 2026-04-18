"""Base protocol adapter"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import httpx
from src.adapter_model import AdapterConfig
from src.models import ChatResponse, EmbeddingResponse, ModelInfo


class AdapterError(Exception):
    """Adapter error"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)


class RateLimitError(AdapterError):
    """Rate limit exceeded"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, 429)


class ProtocolAdapter(ABC):
    """Base protocol adapter"""

    protocol: str = "base"

    def __init__(self, config: AdapterConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def model_name(self) -> str:
        return self.config.model

    @property
    def endpoint(self) -> str:
        return self.config.endpoint

    @property
    def api_key(self) -> str:
        return self.config.api_key

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.endpoint,
                timeout=self.config.timeout,
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self.config.headers)
        return headers

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def chat_completions(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResponse:
        """Create chat completion"""
        pass

    @abstractmethod
    async def embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        """Create embeddings"""
        pass

    @abstractmethod
    async def get_model_info(self) -> ModelInfo:
        """Get model information"""
        pass

    async def list_available_models(self):
        """List all available models from provider."""
        return [await self.get_model_info()]

    async def health_check(self) -> bool:
        """Check if adapter is healthy"""
        try:
            await self.get_model_info()
            return True
        except Exception:
            return False


def create_adapter(protocol: str, config: AdapterConfig) -> ProtocolAdapter:
    """Factory function to create adapter by protocol type"""
    if protocol == "openai":
        from src.adapters.openai import OpenAIAdapter

        return OpenAIAdapter(config)
    elif protocol == "anthropic":
        from src.adapters.anthropic import AnthropicAdapter

        return AnthropicAdapter(config)
    elif protocol == "rest":
        from src.adapters.rest import RESTAdapter

        return RESTAdapter(config)
    elif protocol == "ollama":
        from src.adapters.ollama import OllamaAdapter

        return OllamaAdapter(config)
    else:
        raise ValueError(f"Unknown protocol: {protocol}")
