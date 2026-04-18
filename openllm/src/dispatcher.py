"""Model dispatcher for OpenLLM"""

import asyncio
import logging
import time
from typing import Any, Optional

from openllm.src.adapter_model import ModelConfig
from openllm.src.adapters.base import AdapterError, RateLimitError, ProtocolAdapter
from openllm.src.context import get_context_manager
from openllm.src.limiter import RateLimiter, get_limiter, RateLimitExceeded
from openllm.src.models import ChatRequest, ChatResponse
from openllm.src.registry import get_registry
from openllm.src.scorer import get_scorer

logger = logging.getLogger(__name__)


class Dispatcher:
    """Dispatcher for routing requests to models"""

    def __init__(self):
        self._limiter = get_limiter()
        self._scorer = get_scorer()
        self._registry = get_registry()
        self._context = get_context_manager()
        self._session_cache: dict[str, str] = {}

    async def dispatch(self, request: ChatRequest) -> ChatResponse:
        model_name = request.model

        if model_name == "meta-model":
            model_name = await self._select_best_model(request)

        if request.session_id:
            cached = self._session_cache.get(request.session_id)
            if cached:
                model_name = cached

        model_config = self._registry.get_model(model_name)
        if not model_config:
            raise AdapterError(f"Model not found: {model_name}", 404)

        await self._limiter.set_limits(model_name, model_config)

        semaphore = self._limiter.get_semaphore(model_name)

        if semaphore:
            async with semaphore:
                return await self._execute_request(model_name, model_config, request)
        else:
            return await self._execute_request(model_name, model_config, request)

    async def _execute_request(
        self, model_name: str, model_config: ModelConfig, request: ChatRequest
    ) -> ChatResponse:
        adapter = self._registry.get_or_create_adapter(model_name)
        if not adapter:
            raise AdapterError(f"Adapter not found: {model_name}", 500)

        messages = [msg.model_dump() for msg in request.messages]

        start_time = time.time()

        try:
            response = await adapter.chat_completions(
                messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=request.stream,
            )

            elapsed = time.time() - start_time

            await self._scorer.calculate_score(
                model_name,
                elapsed,
                True,
                model_config.max_context_length,
                model_config.quality_weight,
            )

            return response

        except RateLimitError:
            logger.warning(f"Rate limit for {model_name}, attempting failover")
            await self._scorer.record_failure(model_name)
            return await self.failover(model_name, request)

        except AdapterError as e:
            logger.error(f"Adapter error for {model_name}: {e}")
            await self._scorer.record_failure(model_name)
            return await self.failover(model_name, request)

    async def _select_best_model(self, request: ChatRequest) -> str:
        enabled = self._registry.get_enabled_models(request.model_type, request.model_scale)

        if not enabled:
            raise AdapterError("No models available", 503)

        model_names = [m.name for m in enabled]
        return self._scorer.get_best_model(model_names, request.model_type, request.model_scale)

    async def failover(self, original_model: str, request: ChatRequest) -> ChatResponse:
        enabled = self._registry.get_enabled_models(request.model_type, request.model_scale)

        available = [m for m in enabled if m.name != original_model]

        for model_config in available:
            try:
                logger.info(f"Trying failover model: {model_config.name}")
                response = await self._execute_request(model_config.name, model_config, request)

                if request.session_id:
                    self._session_cache[request.session_id] = model_config.name

                return response

            except (RateLimitError, AdapterError) as e:
                logger.warning(f"Failover failed for {model_config.name}: {e}")
                await self._scorer.record_failure(model_config.name)
                continue

        raise AdapterError("No available models", 503)


_dispatcher_instance: Optional[Dispatcher] = None


def get_dispatcher() -> Dispatcher:
    """Get global dispatcher"""
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = Dispatcher()
    return _dispatcher_instance
