# 韧性增强与模型元数据暴露 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 OpenLLM 网关增加健康评分动态路由、provider 并发限流和模型元数据暴露能力

**Architecture:** 新增 HealthScoreTracker（滚动窗口健康评分）和 ModelMetadataRegistry（模型能力元数据聚合），修改 ComboEngine 按健康分×权重排序，修改 OpenAICompatProvider 加 Semaphore 并发控制，扩展 /v1/models 响应字段

**Tech Stack:** Python 3.11+, asyncio, FastAPI

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `openllm/core/health.py` | 新增 | HealthScoreTracker |
| `openllm/core/model_metadata.py` | 新增 | ModelMetadataRegistry |
| `openllm/core/types.py` | 修改 | ProviderConfig +max_concurrent |
| `openllm/core/combo.py` | 修改 | 动态权重路由，并发超时 failover |
| `openllm/core/config_loader.py` | 修改 | 解析 max_concurrent、models |
| `openllm/core/registry.py` | 修改 | discover_models 读取富元数据 |
| `openllm/providers/openai_compat.py` | 修改 | Semaphore，list_models 扩展 |
| `openllm/server/app.py` | 修改 | 初始化 health_tracker、metadata_registry |
| `openllm/server/routes/models.py` | 修改 | 扩展字段，新增详情端点 |
| `tests/test_health.py` | 新增 | HealthScoreTracker 测试 |
| `tests/test_model_metadata.py` | 新增 | ModelMetadataRegistry 测试 |
| `tests/test_core.py` | 修改 | 补充 ComboEngine 动态权重测试 |
| `docs/` | 无需修改 | spec 已存在 |

---

### Task 1: ProviderConfig 新增 max_concurrent 字段

**Files:**
- Modify: `openllm/core/types.py:107-115`

- [ ] **Step 1: 修改 ProviderConfig**

在 `openllm/core/types.py` 的 `ProviderConfig` 末尾增加 `max_concurrent` 字段：

```python
@dataclass
class ProviderConfig:
    name: str
    api_key: str
    endpoint: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 2
    max_concurrent: int = 8
```

- [ ] **Step 2: 运行测试确认不破坏现有逻辑**

运行: `python -m pytest tests/test_core.py -v`
预期: 全部通过

- [ ] **Step 3: 提交**

```bash
git add openllm/core/types.py
git commit -m "feat: add max_concurrent to ProviderConfig"
```

---

### Task 2: HealthScoreTracker

**Files:**
- Create: `openllm/core/health.py`
- Test: `tests/test_health.py`

- [ ] **Step 1: 编写测试**

```python
"""HealthScoreTracker 单元测试"""

from __future__ import annotations

import pytest
from openllm.core.health import HealthScoreTracker
from openllm.core.types import ErrorKind


class TestHealthScoreTracker:
    @pytest.mark.asyncio
    async def test_initial_score_is_100(self):
        tracker = HealthScoreTracker()
        assert tracker.get_score("test-provider") == 100.0

    @pytest.mark.asyncio
    async def test_success_keeps_score_high(self):
        tracker = HealthScoreTracker()
        for _ in range(20):
            tracker.record_success("p", 100.0)
        score = tracker.get_score("p")
        assert score > 90

    @pytest.mark.asyncio
    async def test_failures_lower_score(self):
        tracker = HealthScoreTracker()
        for _ in range(10):
            tracker.record_success("p", 100.0)
        for _ in range(5):
            tracker.record_failure("p", ErrorKind.SERVER_ERROR)
        score = tracker.get_score("p")
        assert score < 80

    @pytest.mark.asyncio
    async def test_high_error_rate_drops_score_to_zero(self):
        tracker = HealthScoreTracker()
        for _ in range(10):
            tracker.record_failure("p", ErrorKind.SERVER_ERROR)
        assert tracker.get_score("p") == 0.0

    @pytest.mark.asyncio
    async def test_latency_increase_deducts_points(self):
        tracker = HealthScoreTracker()
        # 先建立基线
        for _ in range(20):
            tracker.record_success("p", 100.0)
        baseline = tracker.get_score("p")
        # 延迟飙升
        for _ in range(5):
            tracker.record_success("p", 5000.0)
        after = tracker.get_score("p")
        assert after < baseline

    @pytest.mark.asyncio
    async def test_providers_isolated(self):
        tracker = HealthScoreTracker()
        tracker.record_success("p1", 100.0)
        tracker.record_failure("p2", ErrorKind.TIMEOUT)
        assert tracker.get_score("p1") > tracker.get_score("p2")
```

- [ ] **Step 2: 运行测试确认失败**

运行: `python -m pytest tests/test_health.py -v`
预期: ModuleNotFoundError / ImportError

- [ ] **Step 3: 编写 HealthScoreTracker 实现**

```python
"""健康评分追踪器 — 滚动窗口内追踪 provider 健康状态"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from .types import ErrorKind


class HealthScoreTracker:
    """滚动窗口健康评分，0-100"""

    WINDOW_SIZE = 100
    LATENCY_DECAY = 0.9

    def __init__(self) -> None:
        self._successes: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )
        self._failures: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )
        self._latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )

    def record_success(self, provider: str, latency_ms: float = 0.0) -> None:
        self._successes[provider].append({"time": time.time()})
        if latency_ms > 0:
            self._latencies[provider].append(latency_ms)

    def record_failure(self, provider: str, error_kind: ErrorKind) -> None:
        self._failures[provider].append({
            "time": time.time(),
            "kind": error_kind.value,
        })

    def get_score(self, provider: str) -> float:
        score = 100.0

        successes = len(self._successes.get(provider, []))
        failures = len(self._failures.get(provider, []))
        total = successes + failures
        if total == 0:
            return score

        # 错误率扣分
        error_rate = failures / total
        score -= error_rate * 50

        # 服务端错误比客户端错误更严重
        server_errors = sum(
            1 for f in self._failures.get(provider, [])
            if f.get("kind") in ("server_error", "overloaded", "timeout")
        )
        if server_errors > 0:
            score -= (server_errors / total) * 20

        # 延迟扣分
        latencies = list(self._latencies.get(provider, []))
        if len(latencies) >= 5:
            sorted_lat = sorted(latencies)
            p50 = sorted_lat[len(sorted_lat) // 2]
            p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
            if p50 > 0 and p95 > p50 * 2:
                ratio = p95 / p50
                score -= min(20.0, (ratio - 2.0) * 10.0)

        return max(0.0, min(100.0, score))

    def get_latency_p50(self, provider: str) -> float:
        latencies = list(self._latencies.get(provider, []))
        if not latencies:
            return 0.0
        sorted_lat = sorted(latencies)
        return sorted_lat[len(sorted_lat) // 2]

    def get_latency_p95(self, provider: str) -> float:
        latencies = list(self._latencies.get(provider, []))
        if not latencies:
            return 0.0
        sorted_lat = sorted(latencies)
        return sorted_lat[int(len(sorted_lat) * 0.95)]
```

- [ ] **Step 4: 运行测试确认通过**

运行: `python -m pytest tests/test_health.py -v`
预期: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add openllm/core/health.py tests/test_health.py
git commit -m "feat: add HealthScoreTracker with rolling window scoring"
```

---

### Task 3: ModelMetadataRegistry

**Files:**
- Create: `openllm/core/model_metadata.py`
- Test: `tests/test_model_metadata.py`

- [ ] **Step 1: 编写测试**

```python
"""ModelMetadataRegistry 单元测试"""

from __future__ import annotations

import pytest
from openllm.core.model_metadata import ModelMetadataRegistry, ModelMetadata


class TestModelMetadataRegistry:
    def test_empty_registry(self):
        reg = ModelMetadataRegistry()
        assert reg.list_all() == []

    def test_update_from_api(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("deepseek", [
            {"id": "deepseek-chat", "context_length": 65536,
             "capabilities": ["text", "reasoning"], "supports_reasoning": True},
        ])
        meta = reg.get("deepseek/deepseek-chat")
        assert meta is not None
        assert meta.context_length == 65536
        assert "reasoning" in meta.capabilities
        assert meta.supports_reasoning is True
        assert meta.provider == "deepseek"

    def test_update_from_api_missing_fields_default(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("nvidia", [{"id": "llama-3.1-8b"}])
        meta = reg.get("nvidia/llama-3.1-8b")
        assert meta is not None
        assert meta.context_length == 4096
        assert meta.capabilities == ["text"]
        assert meta.supports_reasoning is False

    def test_update_from_config_overrides_api(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("deepseek", [
            {"id": "deepseek-chat", "context_length": 32000},
        ])
        reg.update_from_config({
            "deepseek/deepseek-chat": {"context_length": 65536},
        })
        meta = reg.get("deepseek/deepseek-chat")
        assert meta.context_length == 65536  # config overrides API

    def test_get_nonexistent_returns_none(self):
        reg = ModelMetadataRegistry()
        assert reg.get("nonexistent/model") is None

    def test_list_all_returns_all(self):
        reg = ModelMetadataRegistry()
        reg.update_from_api("p1", [{"id": "m1"}, {"id": "m2"}])
        reg.update_from_api("p2", [{"id": "m3"}])
        assert len(reg.list_all()) == 3
```

- [ ] **Step 2: 运行测试确认失败**

运行: `python -m pytest tests/test_model_metadata.py -v`
预期: ModuleNotFoundError

- [ ] **Step 3: 编写 ModelMetadataRegistry 实现**

```python
"""模型元数据注册表 — 聚合 provider API、用户配置、默认值"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelMetadata:
    model_id: str
    provider: str
    context_length: int = 4096
    capabilities: list[str] = field(default_factory=lambda: ["text"])
    supports_reasoning: bool = False
    supports_vision: bool = False
    supports_tool_use: bool = False
    supports_streaming: bool = True
    pricing_input_per_1k: float = 0.0
    pricing_output_per_1k: float = 0.0
    max_output_tokens: int | None = None


class ModelMetadataRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}

    def update_from_api(self, provider: str, models: list[dict]) -> None:
        for m in models:
            mid = m.get("id", "")
            key = f"{provider}/{mid}"
            existing = self._models.get(key)
            if existing:
                continue  # 已有用户配置覆盖，不覆盖
            caps = m.get("capabilities", ["text"])
            self._models[key] = ModelMetadata(
                model_id=key,
                provider=provider,
                context_length=m.get("context_length", 4096),
                capabilities=caps,
                supports_reasoning=m.get("supports_reasoning", False),
                supports_vision=m.get("supports_vision", False),
                supports_tool_use=m.get("supports_tool_use", False),
                supports_streaming=m.get("supports_streaming", True),
                pricing_input_per_1k=m.get("pricing_input_per_1k", 0.0),
                pricing_output_per_1k=m.get("pricing_output_per_1k", 0.0),
                max_output_tokens=m.get("max_output_tokens"),
            )

    def update_from_config(self, config: dict[str, dict[str, Any]]) -> None:
        for model_key, overrides in config.items():
            existing = self._models.get(model_key)
            if existing:
                for k, v in overrides.items():
                    if hasattr(existing, k):
                        setattr(existing, k, v)
            else:
                provider = model_key.split("/")[0] if "/" in model_key else ""
                self._models[model_key] = ModelMetadata(
                    model_id=model_key,
                    provider=provider,
                    **{k: v for k, v in overrides.items()
                       if k in ModelMetadata.__dataclass_fields__},
                )

    def get(self, model_id: str) -> ModelMetadata | None:
        return self._models.get(model_id)

    def list_all(self) -> list[ModelMetadata]:
        return list(self._models.values())
```

- [ ] **Step 4: 运行测试确认通过**

运行: `python -m pytest tests/test_model_metadata.py -v`
预期: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add openllm/core/model_metadata.py tests/test_model_metadata.py
git commit -m "feat: add ModelMetadataRegistry for model capability aggregation"
```

---

### Task 4: OpenAICompatProvider — Semaphore 并发限流 + list_models 扩展

**Files:**
- Modify: `openllm/providers/openai_compat.py`

- [ ] **Step 1: 在构造函数中初始化 Semaphore**

在 `__init__` 中增加：

```python
def __init__(self, config: ProviderConfig):
    self.config = config
    self._client: httpx.AsyncClient | None = None
    self._semaphore = asyncio.Semaphore(config.max_concurrent)
```

- [ ] **Step 2: 在 chat_completion 和 chat_completion_stream 入口处加 Semaphore**

```python
async def chat_completion(self, request: ChatRequest) -> ChatResponse:
    async with self._semaphore:
        client = await self._get_client()
        payload = self._build_payload(request)
        ...  # 其余不变

async def chat_completion_stream(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
    async with self._semaphore:
        client = await self._get_client()
        payload = self._build_payload(request)
        payload["stream"] = True
        ...  # 其余不变
```

注意缩进变化。完整的 `chat_completion` 方法：

```python
async def chat_completion(self, request: ChatRequest) -> ChatResponse:
    async with self._semaphore:
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
```

完整的 `chat_completion_stream` 方法：

```python
async def chat_completion_stream(
    self, request: ChatRequest
) -> AsyncIterator[ChatResponse]:
    async with self._semaphore:
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
```

- [ ] **Step 3: 扩展 list_models 返回值**

```python
async def list_models(self) -> list[dict]:
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
                "is_free": False,
                "context_length": m.get("context_length"),
                "capabilities": m.get("capabilities"),
                "supports_reasoning": m.get("supports_reasoning", False),
                "supports_vision": m.get("supports_vision", False),
                "max_output_tokens": m.get("max_output_tokens"),
            })
        return models
    except httpx.HTTPStatusError as e:
        logger.warning("list_models failed for %s: %s", self.config.name, e)
        return []
```

- [ ] **Step 4: 运行现有测试确认不破坏**

运行: `python -m pytest tests/ -v`
预期: 全部通过

- [ ] **Step 5: 提交**

```bash
git add openllm/providers/openai_compat.py
git commit -m "feat: add semaphore concurrency limiting and extend list_models metadata"
```

---

### Task 5: ConfigLoader — 解析 max_concurrent 和 models

**Files:**
- Modify: `openllm/core/config_loader.py`

- [ ] **Step 1: 在 load_providers_from_config 中解析 max_concurrent**

```python
providers.append(ProviderConfig(
    name=name,
    api_key=api_key,
    endpoint=cfg.get("endpoint", ""),
    extra_headers=cfg.get("headers", {}),
    timeout=cfg.get("timeout", 30.0),
    max_retries=cfg.get("max_retries", 2),
    max_concurrent=cfg.get("max_concurrent", 8),
))
```

- [ ] **Step 2: 新增 load_models_from_config 函数**

```python
def load_models_from_config(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """加载用户配置中的模型元数据覆盖"""
    return config.get("models", {})
```

- [ ] **Step 3: 运行测试确认通过**

运行: `python -m pytest tests/test_config_loader.py -v`
预期: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add openllm/core/config_loader.py
git commit -m "feat: parse max_concurrent and models section from config"
```

---

### Task 6: Registry — 集成 ModelMetadataRegistry

**Files:**
- Modify: `openllm/core/registry.py`

- [ ] **Step 1: 在 Registry 中增加 metadata 注册表接口**

```python
class Registry:
    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._models_cache: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()
```

在 `discover_models` 后需要调用 metadata 注册表。由于 Registry 不直接持有 ModelMetadataRegistry 引用，改为在 `server/app.py` 中协调。

- [ ] **Step 2: 扩展 get_cached_models 返回值**

```python
def get_cached_models(self) -> list[dict]:
    flat = []
    for provider, models in self._models_cache.items():
        for m in models:
            flat.append({
                "id": m.get("id", ""),
                "provider": provider,
                "name": m.get("name", m.get("id", "")),
                "is_free": m.get("is_free", False),
                "context_length": m.get("context_length", 4096),
                "capabilities": m.get("capabilities", ["text"]),
                "supports_reasoning": m.get("supports_reasoning", False),
                "supports_vision": m.get("supports_vision", False),
            })
    return flat
```

- [ ] **Step 3: 运行现有测试**

运行: `python -m pytest tests/test_core.py -v`
预期: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add openllm/core/registry.py
git commit -m "feat: extend get_cached_models with context_length and capabilities"
```

---

### Task 7: Server app.py — 初始化新组件

**Files:**
- Modify: `openllm/server/app.py`

- [ ] **Step 1: 增加 import 和全局变量**

```python
from openllm.core.health import HealthScoreTracker
from openllm.core.model_metadata import ModelMetadataRegistry
from openllm.core.config_loader import load_models_from_config

health_tracker = HealthScoreTracker()
metadata_registry = ModelMetadataRegistry()
```

- [ ] **Step 2: 修改 lifespan 初始化 metadata**

在 `lifespan` 的 `_load_providers()` 之后、`discover_models()` 之前增加 metadata 加载：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await cooldown.init()
    _load_providers()
    await registry.discover_models()
    await registry.save_snapshot()

    # 加载模型元数据
    config = load_config()
    models_config = load_models_from_config(config)
    for provider_name in registry.list_providers():
        provider = registry.get(provider_name)
        if provider:
            try:
                cached = registry.get_cached_models()
                provider_models = [m for m in cached if m["provider"] == provider_name]
                metadata_registry.update_from_api(provider_name, provider_models)
            except Exception:
                pass
    metadata_registry.update_from_config(models_config)

    logger.info("OpenLLM started with %d provider(s), %d model(s) with metadata",
                len(registry.list_providers()),
                len(metadata_registry.list_all()))
    ...
```

- [ ] **Step 3: 在 health_check_loop 中集成 health_tracker**

```python
async def _health_check_loop() -> None:
    check_interval = 300
    while True:
        await asyncio.sleep(check_interval)
        providers = registry.list_providers()
        if not providers:
            continue
        healthy = 0
        for name in providers:
            provider = registry.get(name)
            if not provider:
                continue
            try:
                models = await provider.list_models()
                if models is not None:
                    circuit_breaker.record_success(name)
                    health_tracker.record_success(name, 0)
                    healthy += 1
                else:
                    circuit_breaker.record_failure(name)
                    health_tracker.record_failure(name, ErrorKind.SERVER_ERROR)
            except Exception as e:
                logger.warning("Health check failed for %s: %s", name, e)
                tripped = circuit_breaker.record_failure(name)
                health_tracker.record_failure(name, ErrorKind.SERVER_ERROR)
                if tripped:
                    logger.warning("Circuit breaker opened for %s", name)
        ...
```

- [ ] **Step 4: 运行测试确认导入不报错**

运行: `python -m pytest tests/ -v`
预期: 全部通过

- [ ] **Step 5: 提交**

```bash
git add openllm/server/app.py
git commit -m "feat: integrate HealthScoreTracker and ModelMetadataRegistry into server"
```

---

### Task 8: ComboEngine — 动态权重路由 + 并发超时 failover

**Files:**
- Modify: `openllm/core/combo.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: 修改 ComboEngine 构造函数接受 health_tracker**

```python
from .health import HealthScoreTracker

class ComboEngine:
    def __init__(self, registry: Registry, cooldown: CooldownManager,
                 health_tracker: HealthScoreTracker | None = None):
        self._registry = registry
        self._cooldown = cooldown
        self._health_tracker = health_tracker or HealthScoreTracker()
        self._rr_index: dict[str, int] = {}
        self._lock = asyncio.Lock()
```

- [ ] **Step 2: 实现健康分排序方法**

```python
def _sorted_by_health(self, members: list[ComboMember]) -> list[ComboMember]:
    """按 priority 分组，组内按 health_score × weight 降序"""
    from collections import defaultdict
    groups = defaultdict(list)
    for m in members:
        groups[m.priority].append(m)
    result = []
    for priority in sorted(groups.keys()):
        group = groups[priority]
        group.sort(
            key=lambda m: self._health_tracker.get_score(m.provider) * m.weight,
            reverse=True,
        )
        result.extend(group)
    return result
```

- [ ] **Step 3: 修改 _execute_fallback 使用 _sorted_by_health**

```python
async def _execute_fallback(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
    sorted_members = self._sorted_by_health(combo.members)
    ...
```

- [ ] **Step 4: 修改 execute_stream 使用 _sorted_by_health**

```python
def execute_stream(self, combo: ComboConfig, request: ChatRequest):
    sorted_members = self._sorted_by_health(combo.members)
    ...
```

- [ ] **Step 5: 修改 _execute_round_robin 跳过低分 provider**

```python
async def _execute_round_robin(self, combo: ComboConfig, request: ChatRequest) -> ChatResponse:
    available = []
    for m in combo.members:
        if await self._cooldown.is_cooled(f"provider:{m.provider}"):
            logger.debug("RR skipping cooled: %s", m.provider)
            continue
        if self._health_tracker.get_score(m.provider) < 30:
            logger.debug("RR skipping unhealthy: %s (score=%.0f)",
                         m.provider, self._health_tracker.get_score(m.provider))
            continue
        available.append(m)
    ...
```

- [ ] **Step 6: 在 chat_completion / execute_stream 中加 Semaphore 超时 failover**

在 `_execute_fallback` 的 try 块中，在调用 `provider.chat_completion` 之前：

```python
try:
    if hasattr(provider, '_semaphore'):
        try:
            async with asyncio.timeout(0.5):
                await provider._semaphore.acquire()
        except asyncio.TimeoutError:
            failures.append((member.provider, "concurrency limit"))
            provider._semaphore.release()  # 未获取到，不需要 release
            continue
    ...
```

需要注意这个逻辑的实际实现。更好的方式是在 `OpenAICompatProvider` 上加一个 `try_acquire` 方法：

```python
async def try_acquire(self, timeout: float = 0.5) -> bool:
    try:
        async with asyncio.timeout(timeout):
            await self._semaphore.acquire()
            return True
    except asyncio.TimeoutError:
        return False

def release(self) -> None:
    self._semaphore.release()
```

然后在 combo.py 中使用。或者更简洁的：在 chat_completion 和 chat_completion_stream 上直接加 `async with self._semaphore`，combo 中用 `asyncio.wait_for` 包裹整个 provider 调用。

简化为 combo 中先快速检查并发数：

```python
# 在 _execute_fallback 尝试每个成员时
try:
    # 并发限制快速检查
    if hasattr(provider, '_semaphore'):
        acquired = await provider.try_acquire(timeout=0.5)
        if not acquired:
            failures.append((member.provider, "concurrency limit"))
            continue

    req = ChatRequest(...)
    response = await provider.chat_completion(req)
    ...
finally:
    if hasattr(provider, 'release'):
        provider.release()
```

在 `OpenAICompatProvider` 中增加这两个方法。注意原有 `async with self._semaphore` 和 `try_acquire` 不能共存。改为 provider 内部用 try_acquire/release 模式，或者保持简单：provider 内部用 semaphore，combo 层用 `asyncio.wait_for(provider.chat_completion(req), timeout=provider.config.timeout + 0.5)`。

最简方案：不增加 try_acquire，而是 combo 中用整体超时包裹 provider 调用。在 `_execute_fallback` 中：

```python
try:
    total_timeout = member.timeout + 0.5 if hasattr(member, 'timeout') else 30.5
    response = await asyncio.wait_for(
        provider.chat_completion(req),
        timeout=total_timeout
    )
except asyncio.TimeoutError:
    failures.append((member.provider, "timeout"))
    continue
```

不过 httpx 已经有 timeout，这层包裹有些多余。让 provider 内部处理并发限流即可，combo 不需要特殊处理——semaphore 满了就排队，不影响稳定性。

**最终决定：** combo 不改并发逻辑，semaphore 只在 provider 内部工作。combo 只改健康分排序。

- [ ] **Step 7: 在 provider 调用前后记录健康数据**

在 `execute_stream` 成功路径：

```python
# 首 chunk 到达
first_chunk = await stream.__anext__()
first_chunk.actual_provider = member.provider
first_chunk.actual_model = member.model
yield first_chunk
async for chunk in stream:
    chunk.actual_provider = member.provider
    chunk.actual_model = member.model
    yield chunk
self._health_tracker.record_success(member.provider, 0)  # 新增
return
```

在 `_execute_fallback` 成功路径：

```python
response = await provider.chat_completion(req)
response.actual_provider = member.provider
response.actual_model = member.model
self._health_tracker.record_success(member.provider, 0)  # 新增
return response
```

在失败路径：

```python
except ProviderError as e:
    self._health_tracker.record_failure(member.provider, e.kind)  # 新增
    ...
```

- [ ] **Step 8: 更新 ComboEngine 测试**

在 `tests/test_core.py` 的 TestCombo 中补充测试：

```python
@pytest.mark.asyncio
async def test_combo_fallback_health_score_sorting(self):
    reg = Registry()
    cd = CooldownManager()
    await cd.clear()
    ht = HealthScoreTracker()
    engine = ComboEngine(reg, cd, health_tracker=ht)

    mock_p1 = _MockProvider()
    mock_p2 = _MockProvider()
    reg.register("p1", mock_p1)
    reg.register("p2", mock_p2)

    # p2 健康分低于 p1
    for _ in range(5):
        ht.record_failure("p2", ErrorKind.SERVER_ERROR)
    ht.record_success("p1", 50)

    combo = ComboConfig(
        name="test",
        strategy=RoutingStrategy.FALLBACK,
        members=[
            ComboMember(model="m", provider="p1", priority=0, weight=1.0),
            ComboMember(model="m", provider="p2", priority=0, weight=1.0),
        ],
    )

    req = ChatRequest(model="m", messages=[ChatMessage(role="user", content="hi")])
    response = await engine.execute(combo, req)
    # p1 健康分高，应该被选到
    assert response.actual_provider == "p1"
```

- [ ] **Step 9: 运行测试确认全部通过**

运行: `python -m pytest tests/ -v`
预期: 全部 PASS

- [ ] **Step 10: 提交**

```bash
git add openllm/core/combo.py tests/test_core.py
git commit -m "feat: dynamic weight routing by health score in ComboEngine"
```

---

### Task 9: /v1/models 端点增强

**Files:**
- Modify: `openllm/server/routes/models.py`

- [ ] **Step 1: 扩展 list 模型响应**

```python
from openllm.server.app import registry, metadata_registry

@router.get("/v1/models")
async def list_models():
    models = registry.get_cached_models()
    data = []
    for m in models:
        mid = f"{m['provider']}/{m['id']}"
        meta = metadata_registry.get(mid)
        entry = {
            "id": mid,
            "object": "model",
            "created": 0,
            "owned_by": m["provider"],
            "context_window": meta.context_length if meta else m.get("context_length", 4096),
            "capabilities": meta.capabilities if meta else m.get("capabilities", ["text"]),
            "supports_reasoning": meta.supports_reasoning if meta else m.get("supports_reasoning", False),
        }
        if meta and meta.pricing_input_per_1k > 0:
            entry["pricing"] = {
                "input": meta.pricing_input_per_1k,
                "output": meta.pricing_output_per_1k,
            }
        data.append(entry)
    return {"object": "list", "data": data}
```

- [ ] **Step 2: 新增模型详情端点**

```python
@router.get("/v1/models/{provider}/{model_name}")
async def get_model(provider: str, model_name: str):
    model_id = f"{provider}/{model_name}"
    meta = metadata_registry.get(model_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return {
        "id": model_id,
        "object": "model",
        "created": 0,
        "owned_by": provider,
        "context_window": meta.context_length,
        "capabilities": meta.capabilities,
        "supports_reasoning": meta.supports_reasoning,
        "supports_vision": meta.supports_vision,
        "supports_tool_use": meta.supports_tool_use,
        "supports_streaming": meta.supports_streaming,
        "pricing": {
            "input": meta.pricing_input_per_1k,
            "output": meta.pricing_output_per_1k,
        } if meta.pricing_input_per_1k > 0 else None,
        "max_output_tokens": meta.max_output_tokens,
    }
```

- [ ] **Step 3: 提交**

```bash
git add openllm/server/routes/models.py
git commit -m "feat: enhance /v1/models with context_window, capabilities; add detail endpoint"
```

---

### Task 10: 完整集成测试验证

- [ ] **Step 1: 确认所有测试通过**

运行: `python -m pytest tests/ -v`
预期: 全部 PASS（含新增的 health、model_metadata 测试）

- [ ] **Step 2: 确认导入不报错**

运行: `.venv/bin/python -c "from openllm.server.app import create_app; print('OK')"`
预期: OK

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: resilience (health scoring, concurrency limit) and model metadata exposure"
```
