"""REST protocol adapter"""

import time
import re
from typing import Any, Optional
import httpx
from src.adapter_model import AdapterConfig
from src.adapters.base import ProtocolAdapter, RateLimitError
from src.models import (
    ChatResponse,
    Choice,
    Message,
    Usage,
    EmbeddingResponse,
    EmbeddingData,
    ModelInfo,
)


class RESTAdapter(ProtocolAdapter):
    """Custom REST protocol adapter"""

    protocol = "rest"

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.method = config.method or "POST"
        self.body_template = config.body_template or '{"prompt": "{{content}}"}'

    def _render_template(self, template: str, context: dict[str, Any]) -> dict[str, Any]:
        result = template
        for key, value in context.items():
            pattern = re.compile(r"\{\{" + re.escape(key) + r"\}\}")
            result = pattern.sub(str(value), result)
        import json

        return json.loads(result)

    async def chat_completions(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResponse:
        client = await self.get_client()

        content = messages[-1].get("content", "") if messages else ""

        body = self._render_template(
            self.body_template,
            {
                "content": content,
                "model": self.config.model,
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 1024),
            },
        )

        try:
            if self.method == "POST":
                response = await client.post("", json=body)
            else:
                response = await client.get("", params=body)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError()
            raise

        data = response.json()

        text = data.get("text") or data.get("content") or data.get("response", "")

        return ChatResponse(
            id=data.get("id", f"rest_{time.time()}"),
            created=int(time.time()),
            model=self.config.model,
            choices=[
                Choice(
                    index=0, message=Message(role="assistant", content=text), finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=data.get("prompt_tokens", 0),
                completion_tokens=data.get("completion_tokens", len(text.split())),
                total_tokens=data.get("total_tokens", 0),
            ),
        )

    async def embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        client = await self.get_client()

        body = {"texts": texts, "model": self.config.model}

        response = await client.post("/embeddings", json=body)
        data = response.json()

        return EmbeddingResponse(
            data=[
                EmbeddingData(embedding=item.get("embedding", []), index=i)
                for i, item in enumerate(data.get("data", []))
            ],
            model=self.config.model,
            usage=Usage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=0,
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
        )

    async def get_model_info(self) -> ModelInfo:
        return ModelInfo(id=self.config.model, created=int(time.time()), owned_by="custom")

    async def list_available_models(self):
        """List available models from REST provider."""
        client = await self.get_client()
        try:
            response = await client.get("/models")
            data = response.json()
            models = data.get("models", [])
            return [
                ModelInfo(
                    id=m.get("id", m.get("name", "")),
                    created=m.get("created", int(time.time())),
                    owned_by=m.get("owned_by", "custom"),
                )
                for m in models
            ]
        except Exception:
            return [await self.get_model_info()]
