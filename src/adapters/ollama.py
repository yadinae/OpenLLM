"""Ollama protocol adapter"""

import time
from typing import Any
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


class OllamaAdapter(ProtocolAdapter):
    """Ollama local model adapter"""

    protocol = "ollama"

    async def chat_completions(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResponse:
        client = await self.get_client()

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 2048),
            },
        }

        try:
            response = await client.post("/api/chat", json=payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError()
            raise

        data = response.json()

        return ChatResponse(
            id=data.get("id", f"ollama_{time.time()}"),
            created=int(time.time()),
            model=self.config.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant", content=data.get("message", {}).get("content", "")
                    ),
                    finish_reason=data.get("done_reason", "stop"),
                )
            ],
            usage=Usage(
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            ),
        )

    async def embeddings(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        client = await self.get_client()

        embeddings = []
        total_tokens = 0

        for text in texts:
            payload = {"model": self.config.model, "prompt": text}
            response = await client.post("/api/embeddings", json=payload)
            data = response.json()
            embeddings.append(data.get("embedding", []))
            total_tokens += data.get("tokens", 0)

        return EmbeddingResponse(
            data=[EmbeddingData(embedding=emb, index=i) for i, emb in enumerate(embeddings)],
            model=self.config.model,
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=total_tokens),
        )

    async def get_model_info(self) -> ModelInfo:
        client = await self.get_client()

        try:
            response = await client.get("/api/tags")
            data = response.json()
            models = data.get("models", [])
            for model in models:
                if model.get("name") == self.config.model:
                    return ModelInfo(
                        id=self.config.model, created=int(time.time()), owned_by="ollama"
                    )
        except Exception:
            pass

        return ModelInfo(id=self.config.model, created=int(time.time()), owned_by="ollama")

    async def list_available_models(self):
        client = await self.get_client()
        try:
            response = await client.get("/api/tags")
            data = response.json()
            models = data.get("models", [])
            return [
                ModelInfo(id=m.get("name", ""), created=int(time.time()), owned_by="ollama")
                for m in models
                if m.get("name")
            ]
        except Exception:
            return [await self.get_model_info()]
