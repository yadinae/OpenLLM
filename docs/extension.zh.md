# 扩展指南

## 概述

OpenLLM 设计为可扩展的。本指南涵盖如何添加自定义适配器、评分算法和集成。

## 添加自定义协议适配器

### 步骤 1：创建适配器类

创建 `openllm/src/adapters/custom.py`：

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
    """自定义协议适配器"""
    
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
        
        # 构建请求载荷
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
    
    async def list_available_models(self):
        """列出可用模型"""
        client = await self.get_client()
        try:
            response = await client.get("/models")
            data = response.json()
            models = data.get("models", [])
            return [
                ModelInfo(
                    id=m.get("id", m.get("name", "")),
                    created=m.get("created", int(time.time())),
                    owned_by="custom"
                )
                for m in models
            ]
        except Exception:
            return [await self.get_model_info()]
```

### 步骤 2：注册适配器

更新 `openllm/src/adapters/base.py`：

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
    elif protocol == "custom":  # 添加这个
        from openllm.src.adapters.custom import CustomProtocolAdapter
        return CustomProtocolAdapter(config)
    else:
        raise ValueError(f"Unknown protocol: {protocol}")
```

### 步骤 3：配置模型

添加到 `config/models.yaml`：

```yaml
- name: "custom/my-model"
  protocol: "custom"
  endpoint: "https://api.custom.com/v1"
  api_key: "${CUSTOM_API_KEY}"
```

## 添加自定义评分算法

### 步骤 1：创建自定义评分器

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
        # 自定义评分逻辑
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
        # 自定义指标计算
        return 1.0
```

### 步骤 2：替换全局评分器

```python
from openllm.src import scorer

# 替换全局评分器
scorer._scorer_instance = CustomScorer()
```

## 添加自定义上下文修剪

### 步骤 1：实现自定义模式

```python
from openllm.src.context import ContextManager

class CustomContextManager(ContextManager):
    def _prune_custom(self, messages: list[dict], max_tokens: int) -> list[dict]:
        # 自定义修剪逻辑
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

## 自定义速率限制器

### 步骤 1：实现自定义限制器

```python
from openllm.src.limiter import RateLimiter, ModelLimits

class CustomRateLimiter(RateLimiter):
    async def acquire(self, model_name: str, tokens: int = 1, wait: bool = True) -> bool:
        # 自定义速率限制逻辑
        custom_check = await self._custom_check(model_name)
        
        if not custom_check:
            return False
        
        return await super().acquire(model_name, tokens, wait)
    
    async def _custom_check(self, model_name: str) -> bool:
        # 自定义检查逻辑
        return True
```

## Webhook 集成

### 步骤 1：添加 Webhook 支持

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

## 指标导出

### 步骤 1：添加 Prometheus 指标

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

### 步骤 2：与调度器集成

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

## 自定义认证

### 步骤 1：实现认证

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

### 步骤 2：保护路由

```python
from openllm.src.router import router

@router.post("/chat/completions")
async def chat_completions(request: ChatRequest, authorized: bool = Depends(verify_api_key)):
    # 你的实现
    pass
```

## 插件系统

### 创建插件接口

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

### 注册插件

```python
class MyPlugin(OpenLLMPlugin):
    name = "my_plugin"
    
    def on_response(self, response: ChatResponse):
        print(f"Response: {response}")

# 注册
PLUGINS.append(MyPlugin())
```

## 测试自定义扩展

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

## 最佳实践

1. **保持适配器简单** - 专注于协议转换
2. **优雅处理错误** - 返回正确的错误类型
3. **支持流式输出** - 如果供应商支持则实现
4. **彻底测试** - 覆盖边缘情况
5. **记录配置** - 帮助用户理解参数