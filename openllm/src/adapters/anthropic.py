"""Anthropic protocol adapter"""

import time
from typing import Any
import httpx
from openllm.src.adapter_model import AdapterConfig
from openllm.src.adapters.base import ProtocolAdapter, RateLimitError
from openllm.src.models import (
    ChatResponse,
    Choice,
    Message,
    Usage,
    EmbeddingResponse,
    EmbeddingData,
    ModelInfo,
)


class AnthropicAdapter(ProtocolAdapter):
    """Anthropic (Claude) protocol adapter"""

    protocol = "anthropic"

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key or "dummy",
            "anthropic-version": "2023-06-01",
        }
        headers.update(self.config.headers)
        return headers

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                role = "user"
            converted.append({"role": role, "content": msg.get("content", "")})
        return converted

    async def chat_completions(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResponse:
        client = await self.get_client()

        system_msg = None
        converted = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg.get("content", "")
            else:
                converted.append(msg)

        payload = {
            "model": self.config.model,
            "messages": converted,
            "max_tokens": kwargs.get("max_tokens", 1024),
        }

        if system_msg:
            payload["system"] = system_msg
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]

        try:
            response = await client.post("/v1/messages", json=payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError()
            raise

        data = response.json()

        return ChatResponse(
            id=data.get("id", f"msg_{time.time()}"),
            created=int(time.time()),
            model=data.get("model", self.config.model),
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant", content=data.get("content", [{}])[0].get("text", "")
                    ),
                    finish_reason=data.get("stop_reason", "end_turn"),
                )
            ],
            usage=Usage(
                prompt_tokens=data.get("usage", {}).get("input_tokens", 0),
                completion_tokens=data.get("usage", {}).get("output_tokens", 0),
                total_tokens=data.get("usage", {}).get("input_tokens", 0)
                + data.get("usage", {}).get("output_tokens", 0),
            ),
        )

    async def embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        raise NotImplementedError("Anthropic does not support embeddings")

    async def get_model_info(self) -> ModelInfo:
        return ModelInfo(id=self.config.model, created=int(time.time()), owned_by="anthropic")

    async def list_available_models(self):
        """List available models from Anthropic."""
        return [await self.get_model_info()]
