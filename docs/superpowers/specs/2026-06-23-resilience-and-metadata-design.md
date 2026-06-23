# OpenLLM: 韧性增强与模型元数据暴露设计

## 概述

作为 LLM 网关，OpenLLM 的核心诉求是将多个不稳定的上游 provider
聚合为一个稳定的 OpenAI 兼容 provider。本文档围绕两个问题展开设计：

1. **韧性**：如何避免上游 LLM 调用的不稳定影响用户
2. **模型元数据**：如何给用户提供明确的模型上下文长度、能力等信息

## 架构总览

```
                      ┌─────────────────────────────────┐
                      │           FastAPI Server          │
                      │  ┌──────────┐ ┌───────────────┐  │
                      │  │ /v1/models│ │ /v1/chat      │  │
                      │  │ (enhanced)│ │ (router)      │  │
                      │  └─────┬─────┘ └──────┬────────┘  │
                      │        │               │           │
                      │  ┌─────▼───────────────▼────────┐  │
                      │  │   ModelMetadataRegistry      │  │
                      │  │ (API + config + defaults)    │  │
                      │  └──────────────┬───────────────┘  │
                      │                 │                  │
                      │  ┌──────────────▼───────────────┐  │
                      │  │     ComboEngine (enhanced)    │  │
                      │  │  health_score × weight routing│  │
                      │  └──────────────┬───────────────┘  │
                      │                 │                  │
                      │  ┌──────────────▼───────────────┐  │
                      │  │ OpenAICompatProvider          │  │
                      │  │ + Semaphore (concurrency)    │  │
                      │  │ + HealthScoreTracker          │  │
                      │  └──────────────┬───────────────┘  │
                      │                 │                  │
                      │                 ▼                  │
                      │        Upstream LLM APIs           │
                      └─────────────────────────────────┘
```

## 组件 1: HealthScoreTracker

**文件**: `openllm/core/health.py`（新增）

### 职责

追踪每个 provider 的运行时健康状态并计算 0-100 的评分，供路由引擎使用。

### 数据点

- 滚动窗口内最近 N 次调用的成功率（N=100）
- 成功/失败记录带时间戳和错误类型
- P50/P95 延迟（指数衰减移动平均）
- 熔断器状态（从 CircuitBreaker 读取）
- 冷却状态（从 CooldownManager 读取）

### 评分算法

```
score = 100

# 1. 错误率扣分
error_rate = errors / total
score -= error_rate * 50
if errors_5xx > errors_4xx:
    score -= error_rate * 20  # 服务端错误额外扣分

# 2. 延迟扣分
latency_ratio = p95 / historical_p50
if latency_ratio > 2:
    score -= min(20, (latency_ratio - 2) * 10)

# 3. 熔断器状态映射
if state == "OPEN":       score = 0
elif state == "HALF_OPEN": score = min(score, 40)

# 4. 冷却状态扣分
cool_pct = remaining / total_duration
score -= cool_pct * 30

return max(0, min(100, score))
```

### 接口

```python
class HealthScoreTracker:
    WINDOW_SIZE = 100
    LATENCY_DECAY = 0.9

    def record_success(self, provider: str, latency_ms: float) -> None
    def record_failure(self, provider: str, error_kind: ErrorKind) -> None
    def get_score(self, provider: str) -> float       # 0-100
    def get_latency_p50(self, provider: str) -> float
    def get_latency_p95(self, provider: str) -> float
```

### 集成点

- `OpenAICompatProvider.chat_completion` / `chat_completion_stream` 中调用 `record_success/record_failure`
- `server/app.py` 中的健康检查循环也调用 `record_*` 方法
- `server/app.py` 新增全局 `health_tracker = HealthScoreTracker()`，传入 `ComboEngine`

## 组件 2: ComboEngine 动态权重路由

**文件**: `openllm/core/combo.py`（修改）

### 改动

现有 `FALLBACK` 策略保持 priority 分组，组内按 `health_score × weight` 降序排序：

```python
def _sorted_members(self, combo):
    # 先按 priority 分组
    groups = defaultdict(list)
    for m in combo.members:
        groups[m.priority].append(m)

    # 每组内按健康分排序
    result = []
    for priority in sorted(groups.keys()):
        group = groups[priority]
        group.sort(
            key=lambda m: health_tracker.get_score(m.provider) * m.weight,
            reverse=True,
        )
        result.extend(group)
    return result
```

`ROUND_ROBIN` 策略跳过 `score < 30` 的成员。

### 无配置变更

现有 yaml 保持兼容。`weight` 默认为 1.0。

## 组件 3: Provider 并发限流

**文件**: `openllm/providers/openai_compat.py`（修改）

### 改动

```python
class OpenAICompatProvider(Provider):
    def __init__(self, config: ProviderConfig):
        ...
        self._semaphore = asyncio.Semaphore(config.max_concurrent or 8)

    async def chat_completion(self, request):
        async with self._semaphore:
            ...

    async def chat_completion_stream(self, request):
        async with self._semaphore:
            ...
```

**文件**: `openllm/core/types.py`（修改）

```python
@dataclass
class ProviderConfig:
    ...
    max_concurrent: int = 8  # 新增
```

**文件**: `openllm/core/combo.py`（修改）

combo 路由在 semaphore acquire 上加 0.5s 超时，超时则 failover：

```python
try:
    async with asyncio.timeout(0.5):
        async with provider._semaphore:
            ...
except asyncio.TimeoutError:
    # 并发上限，尝试下一成员
    continue
```

**文件**: `openllm/core/config_loader.py`（修改）

解析 `max_concurrent` 字段：

```python
providers.append(ProviderConfig(
    ...
    max_concurrent=cfg.get("max_concurrent", 8),
))
```

## 组件 4: ModelMetadataRegistry

**文件**: `openllm/core/model_metadata.py`（新增）

### 职责

统一管理所有模型的能力信息，聚合三个来源：
1. Provider API 的 `/v1/models` 返回的额外字段
2. 用户 `openllm.yaml` 中的 `models` 配置
3. 内置默认值

优先级: API > 配置 > 默认值

### 数据结构

```python
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
```

### 接口

```python
class ModelMetadataRegistry:
    def update_from_api(self, provider: str, models: list[dict]) -> None
    def update_from_config(self, config: dict) -> None
    def get(self, model_id: str) -> ModelMetadata | None
    def list_all(self) -> list[ModelMetadata]
    def apply_overrides(self, overrides: dict) -> None  # 用户配置覆盖
```

### 集成

**`openai_compat.py`**: `list_models()` 从上游 API 提取额外字段：

```python
return [{
    "id": m.get("id", ""),
    "name": m.get("id", ""),
    "is_free": False,
    "context_length": m.get("context_length"),
    "capabilities": m.get("capabilities"),
    "supports_reasoning": m.get("supports_reasoning", False),
}]
```

**`registry.py`**: `discover_models()` 完成后调用 `metadata_registry.update_from_api()`

**`openllm.yaml`**: 新增可选段：

```yaml
models:
  deepseek/deepseek-chat:
    context_length: 65536
    capabilities: [text, reasoning]
    supports_reasoning: true
```

**`server/routes/models.py`**: `/v1/models` 响应扩展字段：

```json
{
  "id": "deepseek/deepseek-chat",
  "object": "model",
  "created": 0,
  "owned_by": "deepseek",
  "context_window": 65536,
  "capabilities": ["text", "reasoning"],
  "supports_reasoning": true,
  "pricing": {"input": 0.0005, "output": 0.0020}
}
```

新增 `GET /v1/models/{provider}/{model}` 详情端点。

## 配置示例 (`openllm.yaml`)

```yaml
providers:
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    max_concurrent: 4
  nvidia:
    endpoint: https://integrate.api.nvidia.com/v1
    api_key_env: NVIDIA_API_KEY
    timeout: 60

combos:
  auto:
    strategy: fallback
    members:
      - model: auto; provider: opencode; priority: 0; weight: 1.0
      - model: auto; provider: deepseek; priority: 1; weight: 0.8
      - model: auto; provider: nvidia; priority: 2; weight: 0.5

models:
  deepseek/deepseek-chat:
    context_length: 65536
    capabilities: [text, reasoning]
    supports_reasoning: true
```

## 改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `openllm/core/health.py` | 新增 | HealthScoreTracker |
| `openllm/core/model_metadata.py` | 新增 | ModelMetadataRegistry |
| `openllm/core/types.py` | 修改 | ProviderConfig +max_concurrent |
| `openllm/core/combo.py` | 修改 | 动态权重路由，并发超时 failover |
| `openllm/core/config_loader.py` | 修改 | 解析 max_concurrent, models |
| `openllm/core/registry.py` | 修改 | discover_models 读取富元数据 |
| `openllm/providers/openai_compat.py` | 修改 | Semaphore，list_models 扩展 |
| `openllm/server/app.py` | 修改 | 初始化 health_tracker、metadata_registry |
| `openllm/server/routes/models.py` | 修改 | 返回扩展字段，新增详情端点 |
| `tests/test_health.py` | 新增 | HealthScoreTracker 测试 |
| `tests/test_model_metadata.py` | 新增 | ModelMetadataRegistry 测试 |
| `tests/test_combo.py` | 修改 | 补充动态权重测试 |
