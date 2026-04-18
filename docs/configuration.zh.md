# 配置指南

## 概述

OpenLLM 使用两个配置文件：
- `config/models.yaml` - 模型配置
- `config/settings.json` - 服务器设置

## models.yaml

### 基础配置

```yaml
models:
  - name: "model-id"
    protocol: "openai"
    endpoint: "https://api.example.com/v1"
    api_key: "${API_KEY}"
```

### 完整配置

```yaml
models:
  - name: "groq/llama-3.3-70b-versatile"
    protocol: "openai"
    endpoint: "https://api.groq.com/openai/v1"
    api_key: "${GROQ_API_KEY}"
    enabled: true
    rpm: 30
    tpm: 6000
    max_concurrent: 10
    daily_limit: 1000
    cost_limit: 0.0
    quality_weight: 0.4
    speed_weight: 0.3
    context_weight: 0.2
    reliability_weight: 0.1
    max_context_length: 131072
    capabilities:
      - "text"
      - "coding"
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | string | 必填 | 唯一模型标识符 |
| `protocol` | string | 必填 | 协议类型 |
| `endpoint` | string | 必填 | API 端点 URL |
| `api_key` | string | "" | API 密钥（支持 `${ENV_VAR}`） |
| `enabled` | boolean | true | 启用/禁用模型 |
| `rpm` | integer | 30 | 每分钟请求数 |
| `tpm` | integer | 15000 | 每分钟 token 数 |
| `max_concurrent` | integer | 10 | 最大并发请求数 |
| `daily_limit` | integer | 1000 | 每日请求限制 |
| `cost_limit` | float | 0.0 | 成本限制（美元，0=无限制） |
| `quality_weight` | float | 0.4 | 质量评分权重 |
| `speed_weight` | float | 0.3 | 速度评分权重 |
| `context_weight` | float | 0.2 | 上下文评分权重 |
| `reliability_weight` | float | 0.1 | 可靠性评分权重 |
| `max_context_length` | integer | 128000 | 最大上下文长度 |
| `capabilities` | list | [] | 模型能力 |

## settings.json

### 默认配置

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "context": {
    "mode": "dynamic",
    "max_tokens": 128000
  },
  "session": {
    "affinity_enabled": true,
    "cache_ttl": 3600
  },
  "failover": {
    "max_retries": 3,
    "retry_delay": 1.0
  },
  "scoring": {
    "enabled": true,
    "update_interval": 300
  }
}
```

### 参数说明

#### 服务器

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | "0.0.0.0" | 服务器绑定地址 |
| `port` | integer | 8000 | 服务器端口 |

#### 上下文

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mode` | string | "dynamic" | 上下文模式 |
| `max_tokens` | integer | 128000 | 最大 token 数 |

#### 会话

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `affinity_enabled` | boolean | true | 启用会话亲和性 |
| `cache_ttl` | integer | 3600 | 会话缓存 TTL（秒） |

#### 故障转移

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_retries` | integer | 3 | 最大重试次数 |
| `retry_delay` | float | 1.0 | 重试延迟（秒） |

#### 评分

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | true | 启用评分 |
| `update_interval` | integer | 300 | 更新间隔（秒） |

## 协议配置

### OpenAI 协议

```yaml
- name: "groq/llama-3.3-70b-versatile"
  protocol: "openai"
  endpoint: "https://api.groq.com/openai/v1"
  api_key: "${GROQ_API_KEY}"
```

### Anthropic ��议

```yaml
- name: "claude-3-haiku"
  protocol: "anthropic"
  endpoint: "https://api.anthropic.com"
  api_key: "${ANTHROPIC_API_KEY}"
```

### REST 协议

```yaml
- name: "custom-model"
  protocol: "rest"
  endpoint: "https://api.example.com/v1"
  api_key: "${CUSTOM_API_KEY}"
  method: "POST"
  body_template: '{"prompt": "{{content}}"}'
```

### Ollama 协议

```yaml
- name: "ollama/llama3"
  protocol: "ollama"
  endpoint: "http://localhost:11434"
```

## 环境变量

### API 密钥

```bash
# .env 文件
GEMINI_API_KEY=your_google_key
GROQ_API_KEY=your_groq_key
MISTRAL_API_KEY=your_mistral_key
CEREBRAS_API_KEY=your_cerebras_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### 服务器配置

```bash
OPENLLM_HOST=0.0.0.0
OPENLLM_PORT=8000
OPENLLM_CONFIG=/path/to/models.yaml
```

## 模型示例

### Groq 模型

```yaml
- name: "groq/llama-3.3-70b-versatile"
  protocol: "openai"
  endpoint: "https://api.groq.com/openai/v1"
  api_key: "${GROQ_API_KEY}"
  rpm: 30
  tpm: 6000
  capabilities: ["text", "coding"]

- name: "groq/qwen-3-32b"
  protocol: "openai"
  endpoint: "https://api.groq.com/openai/v1"
  api_key: "${GROQ_API_KEY}"
  rpm: 30
  tpm: 6000
```

### Mistral 模型

```yaml
- name: "mistral/mistral-large-latest"
  protocol: "openai"
  endpoint: "https://api.mistral.ai/v1"
  api_key: "${MISTRAL_API_KEY}"
  rpm: 30
  tpm: 15000
  max_context_length: 128000

- name: "mistral/codestral-latest"
  protocol: "openai"
  endpoint: "https://api.mistral.ai/v1"
  api_key: "${MISTRAL_API_KEY}"
  capabilities: ["coding"]
```

### Gemini 模型

```yaml
- name: "gemini/gemini-2.5-flash"
  protocol: "openai"
  endpoint: "https://generativelanguage.googleapis.com/v1beta"
  api_key: "${GEMINI_API_KEY}"
  rpm: 15
  tpm: 1000000
  max_context_length: 1048576
  capabilities: ["text", "vision"]
```

### Cerebras 模型

```yaml
- name: "cerebras/qwen-3-235b-a22b"
  protocol: "openai"
  endpoint: "https://api.cerebras.ai/v1"
  api_key: "${CEREBRAS_API_KEY}"
  rpm: 30
  tpm: 999999999
```

### Ollama 模型

```yaml
- name: "ollama/llama3"
  protocol: "ollama"
  endpoint: "http://localhost:11434"
  rpm: 100
  tpm: 999999999

- name: "ollama/codegemma"
  protocol: "ollama"
  endpoint: "http://localhost:11434"
  capabilities: ["coding"]
```

## 上下文模式

### 静态模式

精确保留最近 N 条消息。

```json
{
  "context": {
    "mode": "static",
    "max_tokens": 64000
  }
}
```

### 动态模式

自适应 token 跟踪。

```json
{
  "context": {
    "mode": "dynamic",
    "max_tokens": 128000
  }
}
```

### 水库模式

保留最近的 + 提取摘要。

```json
{
  "context": {
    "mode": "reservoir",
    "max_tokens": 128000
  }
}
```

### 自适应模式

自动检测任务类型。

```json
{
  "context": {
    "mode": "adaptive",
    "max_tokens": 128000
  }
}
```

## 速率限制配置

### 激进（高流量）

```yaml
- name: "model-name"
  rpm: 60
  tpm: 30000
  max_concurrent: 20
  daily_limit: 5000
```

### 保守（免费套餐）

```yaml
- name: "model-name"
  rpm: 10
  tpm: 5000
  max_concurrent: 5
  daily_limit: 500
```

### 平衡

```yaml
- name: "model-name"
  rpm: 30
  tpm: 15000
  max_concurrent: 10
  daily_limit: 1000
```

## 自动发现

### 手动发现

使�� `discover` 命令从配置的供应商自动发现可用模型：

```bash
openllm discover
```

此命令会：
1. 查询每个配置供应商的模型列表 API
2. 将发现的模型添加到 `models.yaml`，设置 `enabled: false`
3. 保留现有配置

### 支持的供应商

| 供应商 | API 端点 | 说明 |
|--------|---------|------|
| OpenAI 兼容 | `/v1/models` | 列出所有可用模型 |
| Ollama | `/api/tags` | 列出本地安装的模型 |
| Anthropic | N/A | API 访问受限 |
| REST | 可配置 | 必须支持 `/models` 端点 |

### 示例

```bash
# 发现前
$ openllm models
  [✓] groq/llama-3.3-70b-versatile (openai)

# 运行发现
$ openllm discover
Discovered 2 new models:
  - gpt-4-turbo (openai)
  - gpt-3.5-turbo (openai)

# 发现后 - 新模型是禁用的
$ openllm models
  [✓] groq/llama-3.3-70b-versatile (openai)
  [✗] gpt-4-turbo (openai)
  [✗] gpt-3.5-turbo (openai)
```

## 问题排查

### 模型加载失败

检查：
1. `models.yaml` 语法是否有效
2. `endpoint` URL 是否正确
3. `api_key` 环境变量是否已设置

### 速率限制错误

检查：
1. `rpm` 和 `tpm` 值
2. 池中其他模型
3. 增加限制或添加更多模型

### 连接错误

检查：
1. 网络连接
2. API 密钥有效性
3. 供应商状态页面