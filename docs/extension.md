# Extension Guide

## Overview

OpenLLM is designed to be extensible. This guide covers how to add custom adapters, scoring algorithms, and integrations.

## Adding Custom Protocol Adapter

### Step 1: Create Adapter Class

Create `openllm/src/adapters/custom.py`:

```python
import time
from typing import Any
import httpx
from openllm.src.adapter_model import AdapterConfig
from openllm.src.adapters.base import ProtocolAdapter, RateLimitError
from openllm.src.models import (
    ChatResponse, Choice, Message, Usage,
    EmbeddingResponse, EmbeddingData, ModelInfo
)

class CustomProtocolAdapter(ProtocolAdapter):
    """Custom protocol adapter"""
    
    protocol = "custom"
    
    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        headers.update(self.config.headers)
        return headers
    
    async def chat_completions(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any
    ) -> ChatResponse:
        client = await self.get_client()
        
        # Build request payload
        payload = {
            "model": self.config.model,
            "messages": messages,
            **kwargs
        }
        
        try:
            response = await client.post("/v1/completions", json=payload)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError()
            raise
        
        data = response.json()
        
        return ChatResponse(
            id=data.get("id", f"custom_{time.time()}"),
            created=data.get("created", int(time.time())),
            model=self.config.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=data.get("text", "")
                    ),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0)
            )
        )
    
    async def embeddings(
        self,
        texts: list[str],
        **kwargs: Any
    ) -> EmbeddingResponse:
        client = await self.get_client()
        
        response = await client.post(
            "/v1/embeddings",
            json={"model": self.config.model, "input": texts}
        )
        data = response.json()
        
        return EmbeddingResponse(
            data=[
                EmbeddingData(embedding=item.get("embedding", []), index=i)
                for i, item in enumerate(data.get("data", []))
            ],
            model=self.config.model,
            usage=Usage()
        )
    
    async def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            id=self.config.model,
            created=int(time.time()),
            owned_by="custom"
        )
```

### Step 2: Register Adapter

Update `openllm/src/adapters/base.py`:

```python
def create_adapter(protocol: str, config: AdapterConfig) -> ProtocolAdapter:
    if protocol == "openai":
        from openllm.src.adapters.openai import OpenAIAdapter
        return OpenAIAdapter(config)
    elif protocol == "anthropic":
        from openllm.src.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter(config)
    elif protocol == "rest":
        from openllm.src.adapters.rest import RESTAdapter
        return RESTAdapter(config)
    elif protocol == "ollama":
        from openllm.src.adapters.ollama import OllamaAdapter
        return OllamaAdapter(config)
    elif protocol == "custom":  # Add this
        from openllm.src.adapters.custom import CustomProtocolAdapter
        return CustomProtocolAdapter(config)
    else:
        raise ValueError(f"Unknown protocol: {protocol}")
```

### Step 3: Configure Model

Add to `config/models.yaml`:

```yaml
- name: "custom/my-model"
  protocol: "custom"
  endpoint: "https://api.custom.com/v1"
  api_key: "${CUSTOM_API_KEY}"
```

## Adding Custom Scoring Algorithm

### Step 1: Create Custom Scorer

```python
from openllm.src.scorer import ScorerEngine, ModelScore
from datetime import datetime

class CustomScorer(ScorerEngine):
    async def calculate_score(
        self,
        model_name: str,
        response_time: float,
        success: bool,
        context_length: int = 0,
        base_score: float = 0.5
    ) -> ModelScore:
        # Custom scoring logic
        custom_factor = await self._get_custom_metric(model_name)
        
        score = ModelScore(model_name=model_name)
        
        score.quality_score = base_score * custom_factor
        score.speed_score = min(1.0, 1.0 / (response_time + 0.1))
        score.context_score = min(1.0, context_length / 128000)
        score.reliability_score = 1.0 if success else 0.0
        
        score.total_score = (
            score.quality_score * 0.4 +
            score.speed_score * 0.3 +
            score.context_score * 0.2 +
            score.reliability_score * 0.1
        )
        
        self._scores[model_name] = score
        return score
    
    async def _get_custom_metric(self, model_name: str) -> float:
        # Custom metric calculation
        return 1.0
```

### Step 2: Replace Global Scorer

```python
from openllm.src import scorer

# Replace global scorer
scorer._scorer_instance = CustomScorer()
```

## Adding Custom Context Pruning

### Step 1: Implement Custom Mode

```python
from openllm.src.context import ContextManager

class CustomContextManager(ContextManager):
    def _prune_custom(self, messages: list[dict], max_tokens: int) -> list[dict]:
        # Custom pruning logic
        result = []
        token_count = 0
        
        for msg in reversed(messages):
            msg_tokens = len(msg.get("content", "").split())
            if token_count + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            token_count += msg_tokens
        
        return result
```

## Custom Rate Limiter

### Step 1: Implement Custom Limiter

```python
from openllm.src.limiter import RateLimiter, ModelLimits

class CustomRateLimiter(RateLimiter):
    async def acquire(self, model_name: str, tokens: int = 1, wait: bool = True) -> bool:
        # Custom rate limiting logic
        custom_check = await self._custom_check(model_name)
        
        if not custom_check:
            return False
        
        return await super().acquire(model_name, tokens, wait)
    
    async def _custom_check(self, model_name: str) -> bool:
        # Custom check logic
        return True
```

## Webhook Integration

### Step 1: Add Webhook Support

```python
from openllm.src.dispatcher import Dispatcher
from openllm.src.models import ChatRequest, ChatResponse

class WebhookDispatcher(Dispatcher):
    def __init__(self, webhook_url: str = None):
        super().__init__()
        self.webhook_url = webhook_url
    
    async def _execute_request(self, model_name, model_config, request):
        response = await super()._execute_request(model_name, model_config, request)
        
        if self.webhook_url:
            await self._send_webhook(response)
        
        return response
    
    async def _send_webhook(self, response: ChatResponse):
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=response.model_dump())
```

## Metrics Export

### Step 1: Add Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    'openllm_requests_total',
    'Total requests',
    ['model', 'status']
)

REQUEST_LATENCY = Histogram(
    'openllm_request_latency_seconds',
    'Request latency',
    ['model']
)
```

### Step 2: Integrate with Dispatcher

```python
from openllm.src.dispatcher import Dispatcher

class MetricsDispatcher(Dispatcher):
    async def _execute_request(self, model_name, model_config, request):
        with REQUEST_LATENCY.labels(model=model_name).time():
            response = await super()._execute_request(model_name, model_config, request)
        
        REQUEST_COUNT.labels(
            model=model_name,
            status="success"
        ).inc()
        
        return response
```

## Custom Authentication

### Step 1: Implement Auth

```python
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="Authorization")

async def verify_api_key(api_key: str = Security(api_key_header)):
    valid_keys = ["key1", "key2"]
    
    if api_key.replace("Bearer ", "") not in valid_keys:
        raise HTTPException(status_code=401)
    
    return True
```

### Step 2: Protect Routes

```python
from openllm.src.router import router

@router.post("/chat/completions")
async def chat_completions(request: ChatRequest, authorized: bool = Depends(verify_api_key)):
    # Your implementation
    pass
```

## Plugin System

### Create Plugin Interface

```python
class OpenLLMPlugin:
    name: str
    
    def on_request(self, request: ChatRequest):
        pass
    
    def on_response(self, response: ChatResponse):
        pass
    
    def on_error(self, error: Exception):
        pass
```

### Register Plugin

```python
class MyPlugin(OpenLLMPlugin):
    name = "my_plugin"
    
    def on_response(self, response: ChatResponse):
        print(f"Response: {response}")

# Register
PLUGINS.append(MyPlugin())
```

## Testing Custom Extensions

```python
import pytest

class TestCustomAdapter:
    @pytest.fixture
    def config(self):
        return AdapterConfig(
            model="test-model",
            protocol="custom",
            endpoint="https://test.com",
            api_key="test-key"
        )
    
    @pytest.fixture
    def adapter(self, config):
        return CustomProtocolAdapter(config)
    
    @pytest.mark.asyncio
    async def test_chat_completions(self, adapter):
        messages = [{"role": "user", "content": "test"}]
        response = await adapter.chat_completions(messages)
        
        assert response.id is not None
        assert len(response.choices) > 0
```

## Best Practices

1. **Keep adapters simple** - Focus on protocol translation
2. **Handle errors gracefully** - Return proper error types
3. **Support streaming** - Implement if provider supports it
4. **Test thoroughly** - Cover edge cases
5. **Document configuration** - Help users understand parameters