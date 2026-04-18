# 架构

## 概述

OpenLLM 是一个 AI 模型聚合平台，提供统一的 API 来访问多个 AI 模型供应商。它自动路由请求、管理速率限制，并对模型进行质量排名。

```
┌─────────────────────────────────────────────────────────────┐
│                        OpenLLM 网关                          │
├─────────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    API 路由器                       │   │
│  │              /v1/chat/completions                   │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                       调度器                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │   │
│  │  │  选择器     │ │  故障转移   │ │ 速率限制器 │  │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                      评分引擎                       │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │   │
│  │  │    质量    │ │    速度    │ │  可靠性   │  │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                    模型注册表                        │   │
│  │              models.yaml → 适配器                    │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼─────────���────────────────────┐   │
│  │                   协议适配器                        │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │   │
│  │  │OpenAI  │ │Anthropic│ │  REST  │ │Ollama  │    │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘    │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────┐
         │    外部 API       │
         │ (Groq, Gemini,   │
         │ Mistral, 等)     │
         └───────────────────┘
```

## 核心组件

### 1. API 路由器

负责暴露 OpenAI 兼容的端点。

- `/v1/chat/completions` - 对话完成
- `/v1/models` - 列出模型
- `/v1/usage` - 使用统计
- `/v1/scores` - 模型评分
- `/health` - 健康检查

### 2. 调度器

将请求路由到适当的模型并处理故障转移。

**主要职责：**
- 基于评分选择模型
- 检查速率限制
- 执行请求
- 错误时自动故障转移

```python
async def dispatch(request: ChatRequest) -> ChatResponse:
    # 1. 选择最佳模型
    model = select_best_model(request)
    
    # 2. 检查速率限制
    if not check_limits(model):
        # 3. 故障转移
        return failover(original_model, request)
    
    # 4. 执行
    return await execute(model, request)
```

### 3. 评分引擎

计算和维护模型评分。

**评分因素：**
- 质量评分 (40%)：输出质量评估
- 速度评分 (30%)：响应时间
- 上下文评分 (20%)：上下文长度支持
- 可靠性评分 (10%)：成功率

```python
score = (
    quality * 0.4 +
    speed * 0.3 +
    context * 0.2 +
    reliability * 0.1
)
```

### 4. 模型注册表

管理从 `models.yaml` 加载的模型配置。

- 加载模型配置
- 创建协议适配器
- 维护模型状态

### 5. 协议适配器

不同 API 协议的抽象层。

```python
class ProtocolAdapter(ABC):
    protocol: str
    
    @abstractmethod
    async def chat_completions(self, messages, **kwargs) -> ChatResponse:
        pass
    
    @abstractmethod
    async def embeddings(self, texts, **kwargs) -> EmbeddingResponse:
        pass
    
    @abstractmethod
    async def get_model_info(self) -> ModelInfo:
        pass
    
    @abstractmethod
    async def list_available_models(self):
        pass
```

### 6. 速率限制器

用于速率限制的令牌桶实现。

- 每模型 RPM 限制
- 每模型 TPM 限制
- 并发请求限制
- 每日配额跟踪

### 7. 上下文管理器

处理多轮对话上下文。

**模式：**
- `static`：保留最近 N 条消息
- `dynamic`：自适应 token 跟踪
- `reservoir`：最近 + 提取摘要
- `adaptive`：自动检测任务类型

## 数据流

### 请求流

```
客户端请求
    │
    ▼
API 路由器 (router.py)
    │
    ▼
调度器 (dispatcher.py)
    │
    ├──▶ 模型选择 (scorer.py)
    │
    ├──▶ 速率检查 (limiter.py)
    │
    ▼
模型注册表 (registry.py)
    │
    ▼
协议适配器
    │
    ▼
外部 API
    │
    ▼
响应
```

### 评分流

```
收到响应
    │
    ▼
评分引擎
    │
    ��──▶ 测量响应时间
    ├──▶ 评估质量
    │
    ▼
更新评分
    │
    ▼
排名模型
```

### 故障转移流

```
速率限制错误
    │
    ▼
获取排名备选
    │
    ▼
尝试下一个最佳模型
    │
    ▼── 成功 ──▶ 返回响应
    │
    ▼── 失败 ──▶ 继续下一个
    │
    ▼
没有可用模型
    │
    ▼
返回 429 错误
```

## 配置流

```
models.yaml
    │
    ▼
模型注册表
    │
    ├──▶ 加载配置
    │
    ▼
创建适配器
    │
    ▼
准备接收请求
```

## 并发

```
                    ┌─────────────────┐
                    │    async main   │
                    └────────┬────────┘
                             │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
 ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
 │  请求 #1   │        │  请求 #2   │        │  请求 #3   │
 └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                          ▼
                 ┌─────────────────┐
                 │ 信号量         │ (max_concurrent)
                 │  每模型       │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ 令牌桶       │ (RPM/TPM)
                 └───────────────┘
```

## 扩展点

### 添加新协议适配器

1. 创建新的适配器类：

```python
from openllm.src.adapters.base import ProtocolAdapter
from openllm.src.models import ChatResponse, EmbeddingResponse, ModelInfo

class MyProtocolAdapter(ProtocolAdapter):
    protocol = "myprotocol"
    
    async def chat_completions(self, messages, **kwargs) -> ChatResponse:
        # 实现
        pass
    
    async def embeddings(self, texts, **kwargs) -> EmbeddingResponse:
        # 实现
        pass
    
    async def get_model_info(self) -> ModelInfo:
        # 实现
        pass
    
    async def list_available_models(self):
        # 实现
        pass
```

2. 在工厂注册：

```python
# 在 adapters/base.py
def create_adapter(protocol: str, config: AdapterConfig):
    if protocol == "myprotocol":
        return MyProtocolAdapter(config)
```

3. 在 `models.yaml` 中配置：

```yaml
- name: "my-model"
  protocol: "myprotocol"
  endpoint: "https://api.example.com"
```

### 添加自定义评分算法

```python
from openllm.src.scorer import ScorerEngine

class CustomScorer(ScorerEngine):
    async def calculate_score(self, model_name, response_time, success, **kwargs):
        # 自定义评分逻辑
        pass
```

## 错误处理

| 错误 | 代码 | 操作 |
|------|------|------|
| RateLimitError | 429 | 自动故障转移 |
| AdapterError | 500 | 记录 + 故障转移 |
| ConfigError | 400 | 返回错误 |
| TimeoutError | 504 | 重试 + 故障转移 |

## 性能考虑

- async/await 用于非阻塞 I/O
- 每个适配器的连接池
- 信号量用于并发控制
- 令牌桶用于速率限制
- 内存评分（快速访问）

## 安全性

- API 密钥存储在环境变量
- 配置文件无密钥
- CORS 可配置
- 通过 Pydantic 进行请求验证