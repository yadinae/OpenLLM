# OpenLLM

<p align="center">
  <strong>AI 模型聚合平台与评分系统</strong><br>
  一个入口，多个免费 AI 模型。自动故障转移。智能评分。
</p>

<p align="center">
  <a href="README.md">English</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/openllm/"><img src="https://img.shields.io/pypi/v/openllm.svg" alt="PyPI"></a>
  <a href="https://python.org"><img src="https://img.shields.io/python/py-3.10+/openllm" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/openllm" alt="License"></a>
</p>

## 特性

- **多协议适配器**：OpenAI、Anthropic、REST、Ollama 协议
- **模型评分**：基于质量的自动排名
- **速率控制**：每模型 RPM/TPM/并发/每日限制
- **自动故障转移**：速率限制时自动切换模型
- **上下文管理**：静态、动态、水库、自适应模式
- **会话亲和**：固定用户到供应商以启用缓存
- **OpenAI 兼容**：可直接替换现有代码
- **CLI 管理**：命令行工具

## 安装

```bash
pip install openllm
```

或从源码安装：

```bash
pip install -e .
```

## 快速开始

### 1. 配置 API 密钥

创建 `.env` 文件：

```bash
# 免费层 API 密钥
GEMINI_API_KEY=your_google_gemini_key
GROQ_API_KEY=your_groq_key
MISTRAL_API_KEY=your_mistral_key
CEREBRAS_API_KEY=your_cerebras_key
```

或在 shell 中导出：

```bash
export GEMINI_API_KEY="your-key"
export GROQ_API_KEY="your-key"
```

### 2. 配置模型

编辑 `config/models.yaml`：

```yaml
models:
  - name: "groq/llama-3.3-70b-versatile"
    protocol: "openai"
    endpoint: "https://api.groq.com/openai/v1"
    api_key: "${GROQ_API_KEY}"
    rpm: 30
    tpm: 6000

  - name: "mistral/mistral-large-latest"
    protocol: "openai"
    endpoint: "https://api.mistral.ai/v1"
    api_key: "${MISTRAL_API_KEY}"
    rpm: 30
```

### 3. 启动服务器

```bash
openllm serve
```

或：

```bash
python -m openllm.src.server
```

服务器运行在 `http://localhost:8000`

### 4. 使用 API

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer openllm" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-model",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 使用方法

### Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="openllm"
)

# 自动路由到最佳可用模型
response = client.chat.completions.create(
    model="meta-model",
    messages=[{"role": "user", "content": "Hello!"}]
)

# 直接选择模型
response = client.chat.completions.create(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Write a function"}]
)
```

### CLI 命令

```bash
openllm serve          # 启动服务器
openllm status        # 显示状态
openllm models list   # 列出模型
openllm score        # 显示评分
openllm config       # 显示配置
openllm discover     # 发现可用模型
```

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        OpenLLM 网关                        │
├───────────────────────���─────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐      │
│  │                 API 路由 (/v1/*)                  │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │                    调度器                          │      │
│  │     路由选择 + 故障转移 + 速率控制                  │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │                    评分引擎                         │      │
│  │               评分计算 + 排名                        │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │                  模型注册表                         │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │           协议适配器（按协议类型）                   │      │
│  │  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │  │  OpenAI  │Anthropic │   REST   │  Ollama  │          │
│  │  └──────────┴──────────┴──────────┴──────────┘          │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## 配置

### models.yaml

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | string | 必填 | 模型标识符 |
| `protocol` | string | 必填 | 协议类型 |
| `endpoint` | string | 必填 | API 端点 |
| `api_key` | string | "" | API 密钥（支持 `${ENV_VAR}`） |
| `enabled` | bool | true | 启用模型 |
| `rpm` | int | 30 | 每分钟请求数 |
| `tpm` | int | 15000 | 每分钟 token 数 |
| `max_concurrent` | int | 10 | 最大并发数 |
| `daily_limit` | int | 1000 | 每日限制 |
| `cost_limit` | float | 0.0 | 成本限制（美元） |
| `max_context_length` | int | 128000 | 上下文长度 |
| `capabilities` | list | [] | 模型能力 |

### settings.json

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `server.host` | string | "0.0.0.0" | 服务器主机 |
| `server.port` | int | 8000 | 服务器端口 |
| `context.mode` | string | "dynamic" | 上下文模式 |
| `context.max_tokens` | int | 128000 | 最大 token 数 |
| `session.affinity_enabled` | bool | true | 会话亲和 |
| `failover.max_retries` | int | 3 | 最大重试次数 |
| `scoring.enabled` | bool | true | 启用评分 |

## API 端点

### OpenAI 兼容

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /v1/chat/completions | 对话完成 |
| GET | /v1/models | 列出模型 |
| GET | /v1/models/{model} | 获取模型信息 |
| GET | /v1/usage | 使用统计 |

### OpenLLM 扩展

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /v1/scores | 模型评分 |
| POST | /v1/scores/refresh | 刷新评分 |
| GET | /health | 健康检查 |

## 协议适配器

### OpenAI 协议

标准 OpenAI `/v1/chat/completions` 接口。

```yaml
- name: "model-id"
  protocol: "openai"
  endpoint: "https://api.provider.com/v1"
  api_key: "${API_KEY}"
```

### Anthropic 协议

Claude 风格的 `/v1/messages` 接口。

```yaml
- name: "claude-3-haiku"
  protocol: "anthropic"
  endpoint: "https://api.anthropic.com"
  api_key: "${ANTHROPIC_API_KEY}"
```

### REST 协议

支持模板的自定义 REST API。

```yaml
- name: "custom-model"
  protocol: "rest"
  endpoint: "https://api.example.com"
  method: "POST"
  body_template: '{"prompt": "{{content}}"}'
```

### Ollama 协议

本地 Ollama 模型。

```yaml
- name: "ollama/llama3"
  protocol: "ollama"
  endpoint: "http://localhost:11434"
```

## 上下文管理

### 模式

| 模式 | 说明 |
|------|------|
| `static` | 保留最近 N 条消息 |
| `dynamic` | 自适应 token 跟踪 |
| `reservoir` | 最近 + 提取摘要 |
| `adaptive` | 自动检测任务类型 |

## 速率限制

当模型达到速率限制时：
1. 检查请求是否在限制内
2. 如果受限，自动故障转移到下一个最佳模型
3. 继续尝试模型直到成功或耗尽
4. 如果没有可用模型返回 429

## 评分

模型评分基于：

| 因素 | 权重 | 说明 |
|------|------|------|
| 质量 | 40% | 输出质量 |
| 速度 | 30% | 响应时间 |
| 上下文 | 20% | 上下文长度 |
| 可靠性 | 10% | 可用性 |

```
总分 = 质量 × 0.4 + 速度 × 0.3 + 上下文 × 0.2 + 可靠性 × 0.1
```

## 自动发现模型

```bash
openllm discover
```

此命令从配置的供应商自动发现可用模型，新发现的模型会添加到 `models.yaml`（`enabled: false`）。

## 贡献

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 运行 lint
ruff check .
black .
```

## 许可证

MIT 许可证 - 参见 [LICENSE](LICENSE)