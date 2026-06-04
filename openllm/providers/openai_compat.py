"""OpenAI 兼容 Provider — 覆盖 80% 的 AI 提供商"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from openllm.core.errors import ProviderError, RateLimitError, AuthError
from openllm.core.provider import Provider
from openllm.core.types import ChatRequest, ChatResponse, ErrorKind, TokenUsage, ProviderConfig
from openllm.core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class OpenAICompatProvider(Provider):
    """OpenAI 兼容 API Provider
    
    通用适配器，适用于 Groq、DeepSeek、NVIDIA、Cerebras 等。
    """
    
    name = "openai_compat"
    api_version = 1
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            endpoint = self.config.endpoint.rstrip("/")
            # 去掉尾部的 /v1，避免重复（适配器路径已有 /v1）
            if endpoint.endswith("/v1"):
                endpoint = endpoint[:-3]
            self._client = httpx.AsyncClient(
                base_url=endpoint,
                timeout=self.config.timeout,
                headers=self.auth_header(),
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端（应用生命周期结束时调用）"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}
    
    @property
    def attribution_header(self) -> dict[str, str]:
        return {"X-OpenLLM-Provider": self.config.name}
    
    def _extract_model_name(self, model: str) -> str:
        """从 'provider/model' 格式中提取纯模型名"""
        if "/" in model:
            return model.split("/", 1)[1]
        return model
    
    async def list_models(self) -> list[dict]:
        """从 /v1/models 端点获取模型列表"""
        client = await self._get_client()
        try:
            resp = await client.get("/v1/models")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("data", []):
                models.append({
                    "id": m.get("id", ""),
                    "name": m.get("id", ""),
                    "is_free": False,  # OpenAI 兼容 API 不提供免费标记
                })
            return models
        except httpx.HTTPStatusError as e:
            logger.warning("list_models failed for %s: %s", self.config.name, e)
            return []
    
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        client = await self._get_client()
        payload = self._build_payload(request)

        async def _do_post() -> dict:
            resp = await client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()

        try:
            data = await retry_with_backoff(_do_post)
            return self._parse_response(data, request.model)
        except httpx.HTTPStatusError as e:
            raise self._classify_http_error(e, self.config.name)
        except httpx.TimeoutException:
            raise ProviderError(
                f"Timeout from {self.config.name}",
                self.config.name, ErrorKind.TIMEOUT, 504
            )
    
    async def chat_completion_stream(
        self, request: ChatRequest
    ) -> AsyncIterator[ChatResponse]:
        client = await self._get_client()
        payload = self._build_payload(request)
        payload["stream"] = True
        
        try:
            async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise ProviderError(
                        f"{self.config.name}: {resp.status_code} {body[:200]}",
                        self.config.name, ErrorKind.SERVER_ERROR, resp.status_code
                    )
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk_str = line[6:].strip()
                    if not chunk_str or chunk_str == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(chunk_str)
                    except json.JSONDecodeError:
                        continue
                    yield self._parse_chunk(chunk, request.model)
        except httpx.TimeoutException:
            raise ProviderError(
                f"Stream timeout from {self.config.name}",
                self.config.name, ErrorKind.TIMEOUT, 504
            )
    
    def classify_error(self, exc: Exception) -> ErrorKind:
        if isinstance(exc, RateLimitError):
            return ErrorKind.RATE_LIMIT
        if isinstance(exc, AuthError):
            return ErrorKind.AUTH
        if isinstance(exc, ProviderError):
            return exc.kind
        return ErrorKind.UNKNOWN
    
    def _build_payload(self, request: ChatRequest) -> dict:
        return {
            "model": self._extract_model_name(request.model),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }
    
    def _parse_response(self, data: dict, model: str) -> ChatResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        # 一些 Provider（如 DeepSeek-v4-flash）将输出放在 reasoning_content 而非 content 中
        content = message.get("content") or message.get("reasoning_content") or ""
        usage_raw = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )
        return ChatResponse(
            content=content,
            model=data.get("model", model),
            provider=self.config.name,
            usage=usage,
            finish_reason=choice.get("finish_reason", "stop"),
        )
    
    def _parse_chunk(self, chunk: dict, model: str) -> ChatResponse:
        choice = chunk.get("choices", [{}])[0]
        delta = choice.get("delta", {})
        # 一些 Provider（如 DeepSeek-v4-flash）将输出放在 reasoning_content 而非 content 中
        content = delta.get("content") or delta.get("reasoning_content") or ""
        finish = choice.get("finish_reason") or ""
        return ChatResponse(
            content=content,
            model=chunk.get("model", model),
            provider=self.config.name,
            is_stream=True,
            finish_reason=finish if finish else "",
        )
    
    def _classify_http_error(self, e: httpx.HTTPStatusError, provider: str) -> ProviderError:
        status = e.response.status_code
        body = e.response.text[:200]
        if status == 429:
            return RateLimitError(provider)
        if status == 401:
            return AuthError(provider)
        if status == 404:
            return ProviderError(f"Model not found: {body}", provider, ErrorKind.MODEL_NOT_FOUND, status)
        if status >= 500:
            return ProviderError(f"Server error: {body}", provider, ErrorKind.SERVER_ERROR, status)
        return ProviderError(f"HTTP {status}: {body}", provider, ErrorKind.UNKNOWN, status)
