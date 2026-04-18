"""OpenAI protocol adapter"""

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


class OpenAIAdapter(ProtocolAdapter):
    """OpenAI protocol adapter"""

    protocol = "openai"

    async def chat_completions(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResponse:
        client = await self.get_client()

        payload = {"model": self.config.model, "messages": messages, **kwargs}

        try:
            response = await client.post("/v1/chat/completions", json=payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError()
            raise

        data = response.json()

        return ChatResponse(
            id=data.get("id", f"chatcmpl-{time.time()}"),
            created=data.get("created", int(time.time())),
            model=data.get("model", self.config.model),
            choices=[
                Choice(
                    index=i,
                    message=Message(
                        role=choice.get("message", {}).get("role", "assistant"),
                        content=choice.get("message", {}).get("content", ""),
                    ),
                    finish_reason=choice.get("finish_reason"),
                )
                for i, choice in enumerate(data.get("choices", []))
            ],
            usage=Usage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    async def embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        client = await self.get_client()

        payload = {"model": self.config.model, "input": texts}

        response = await client.post("/v1/embeddings", json=payload)
        data = response.json()

        return EmbeddingResponse(
            data=[
                EmbeddingData(embedding=item.get("embedding", []), index=i)
                for i, item in enumerate(data.get("data", []))
            ],
            model=data.get("model", self.config.model),
            usage=Usage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=0,
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    async def get_model_info(self) -> ModelInfo:
        client = await self.get_client()

        try:
            response = await client.get(f"/v1/models/{self.config.model}")
            data = response.json()
            return ModelInfo(
                id=data.get("id", self.config.model),
                created=data.get("created", int(time.time())),
                owned_by=data.get("owned_by", "openai"),
            )
        except httpx.HTTPStatusError:
            return ModelInfo(id=self.config.model, created=int(time.time()), owned_by="unknown")

    async def list_available_models(self):
        client = await self.get_client()
        try:
            response = await client.get("/v1/models")
            data = response.json()
            model_list = data.get("data", [])
            return [
                ModelInfo(
                    id=m.get("id", ""),
                    created=m.get("created", int(time.time())),
                    owned_by=m.get("owned_by", "openai"),
                )
                for m in model_list
                if m.get("id")
            ]
        except Exception:
            return [await self.get_model_info()]
