<p align="center">
  <img src="https://img.shields.io/badge/OpenLLM-AI%20Gateway-blueviolet?style=for-the-badge" alt="OpenLLM"/>
</p>

<h1 align="center">OpenLLM — AI API Gateway</h1>

<p align="center">
  <b>协议翻译 · 智能路由 · 熔断保护 · 零耦合插件</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
  <img src="https://img.shields.io/badge/tests-139_pass-brightgreen" />
  <img src="https://img.shields.io/badge/lint-ruff_0_error-success" />
</p>

---

OpenLLM 是一个轻量级的 AI API 网关，专为多 Provider 场景设计。它让 **Claude Code 可以调用 Groq**，让 **OpenAI SDK 可以连接 Anthropic**，内置智能路由和熔断保护。

### 核心功能

- **🔄 协议翻译** — Anthropic Messages API ↔ OpenAI Chat Completions 双向实时翻译，完整 SSE 事件序列
- **🔀 智能路由** — Fallback / Round-Robin / Priority 三种 Combo 路由策略，首 chunk 锁定真流式切换
- **🛡️ 熔断保护** — Circuit Breaker 状态机（CLOSED→OPEN→HALF_OPEN），自动隔离故障 Provider
- **⚡ 指数退避重试** — 瞬态错误自动重试，AuthError 不重试，httpx 原生异常识别
- **📦 RTK 压缩** — 自动检测 git diff / grep / tree / log / JSON 输出类型，压缩至 10-50%
- **🧠 上下文管理** — Static / Dynamic / Reservoir / Adaptive 四种策略，无 LLM 开销
- **🔐 安全加固** — 可选 Bearer Token 认证 + 请求输入校验（消息数/内容长度/角色白名单）

---

## 快速开始

### 安装

```bash
git clone https://github.com/yadinae/OpenLLM.git
cd OpenLLM

# 使用 uv（推荐）
uv sync

# 或 pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 配置 Provider

创建 `openllm.yaml`：

```yaml
providers:
  groq:
    endpoint: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    timeout: 30
  openrouter:
    endpoint: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
```

或在 `.env` 中设置：

```bash
GROQ_API_KEY=gsk_xxx
OPENROUTER_API_KEY=sk-or-xxx
DEEPSEEK_API_KEY=sk-xxx
```

### 启动

```bash
# 默认启动（localhost:11343）
openllm serve

# 启用认证
openllm serve --api-key my-secret-key

# 绑定到公网（注意 CORS 警告）
openllm serve --host 0.0.0.0 --port 8080
```

### 使用

**OpenAI 兼容调用：**

```bash
curl http://localhost:11343/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "groq/llama-3", "messages": [{"role": "user", "content": "Hello"}]}'
```

**Anthropic 兼容调用（Claude Code 等工具）：**

```bash
curl http://localhost:11343/v1/messages \
  -H "Content-Type: application/json" \
  -d '{"model": "groq/llama-3", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 100}'
```

### 配置客户端工具

```bash
# aider
openllm bind aider

# Continue.dev
openllm bind continue

# Claude Code
openllm bind claude-code

# Hermes Agent
openllm bind hermes
```

---

## 架构

```
┌─────────────┐    ┌──────────────────────────────────────┐
│  客户端工具   │    │              OpenLLM Gateway            │
│             │    │                                        │
│ Claude Code │    │  ┌──────────┐  ┌──────────────────┐   │
│ OpenAI SDK  │───▶│  │ 协议翻译  │─▶│    路由引擎       │   │
│ aider       │    │  │ (Anthropic│  │  Combo/Fallback  │   │
│ Cursor      │    │  │  ↔OpenAI)│  │  Round-Robin     │───▶───▶ Provider A
│ Hermes      │    │  └──────────┘  └──────────────────┘   │   (Groq/OpenRouter/...)
└─────────────┘    │                                        │
                   │  ┌──────────┐  ┌──────────────────┐   │
                   │  │ 熔断器   │  │   冷却管理器      │   │
                   │  │ Circuit  │  │  Cooldown         │   │
                   │  │ Breaker  │  │  Manager          │   │
                   │  └──────────┘  └──────────────────┘   │
                   │                                        │
                   │  ┌──────────┐  ┌──────────────────┐   │
                   │  │ RTK 压缩 │  │   上下文管理       │   │
                   │  │ (可选)   │  │  4 种策略          │   │
                   │  └──────────┘  └──────────────────┘   │
                   └──────────────────────────────────────┘
```

### 目录结构

```
openllm/
├── cli/                  # CLI 入口 + 客户端绑定
│   ├── __init__.py       # 命令行（serve/list/doctor/bind）
│   └── binder.py         # 一键配置 aider/continue/claude-code
├── core/                 # 核心引擎
│   ├── types.py          # 数据模型 (ChatRequest/Response/Combo/Provider)
│   ├── errors.py         # 错误类型体系
│   ├── registry.py       # Provider 注册表
│   ├── cooldown.py       # 冷却管理（持久化）
│   ├── combo.py          # Combo 路由引擎
│   ├── circuit.py        # 电路熔断器 (LRU+状态机)
│   ├── retry.py          # 指数退避重试
│   ├── config_loader.py  # YAML/JSON 配置加载
│   └── provider.py       # Provider 插件协议
├── context/              # 上下文管理
│   └── manager.py        # 4 种策略
├── optimize/             # RTK 工具输出压缩
│   └── rtk.py            # git diff/grep/tree/log/JSON 压缩器
├── providers/            # Provider 适配器
│   └── openai_compat.py  # OpenAI 兼容 API 通用适配器
├── server/               # HTTP 服务器
│   ├── app.py            # FastAPI 应用工厂 + 后台健康检查
│   ├── validation.py     # 请求输入校验
│   └── routes/           # API 路由
│       ├── chat.py       # /v1/chat/completions
│       ├── messages.py   # /v1/messages (Anthropic)
│       ├── models.py     # /v1/models
│       └── health.py     # /health
└── translate/            # 协议翻译
    ├── base.py           # ProtocolTranslator 基类
    └── anthropic_translate.py  # Anthropic ↔ OpenAI 双向
```

---

## API 参考

### `/v1/chat/completions` — OpenAI 兼容

**请求：**
```json
{
  "model": "groq/llama-3",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 100
}
```

**响应：**
```json
{
  "id": "chatcmpl-openllm",
  "object": "chat.completion",
  "model": "llama-3",
  "choices": [{"message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
}
```

### `/v1/messages` — Anthropic 兼容

**请求：**
```json
{
  "model": "groq/llama-3",
  "messages": [{"role": "user", "content": "Hello"}],
  "system": "You are helpful",
  "max_tokens": 100,
  "stream": false
}
```

**响应：**
```json
{
  "id": "msg_openllm",
  "type": "message",
  "role": "assistant",
  "content": [{"type": "text", "text": "Hi!"}],
  "stop_reason": "end_turn"
}
```

### `/v1/models` — 模型列表

```
GET /v1/models → 已注册 Provider 的所有模型
```

### `/health` — 健康检查

```
GET /health → {"status": "ok", "providers": ["groq", "openrouter", ...]}
```

---

## 深入理解

### 协议翻译流程

```
Anthropic 请求          OpenLLM                   Provider
  ┌──────┐     ┌─────────────────────────┐     ┌────────┐
  │ tool │     │ AnthropicToOpenAI       │     │ Groq   │
  │ sends│────▶│ to_openai(request)      │────▶│ OpenAI │
  │  req  │     │ _convert_messages()     │     │ compat │
  └──────┘     │ _convert_tools()        │     └────┬───┘
               └─────────────────────────┘          │
                                                     │
  ┌──────┐     ┌─────────────────────────┐          │
  │ tool │     │ from_openai(response)   │◀─────────┘
  │receiv│◀────│ from_openai_stream()    │
  │  res │     │ SSE 6-step protocol     │
  └──────┘     └─────────────────────────┘
```

### 熔断器状态机

```
                  连续 5 次失败
  CLOSED ──────────────────────────▶ OPEN
     ▲                                  │
     │         超时 60s                 │
     │    ┌─────────────────────────────┘
     │    │
     │    ▼
     │  HALF_OPEN
     │      │
     └──────┘
     连续 3 次成功
```

### 健壮性设计

| 层级 | 机制 | 说明 |
|:----|:-----|:------|
| L1 | 输入校验 | 消息数 ≤200、单条 ≤50K chars、请求体 ≤2MB、角色白名单 |
| L2 | 认证 | 可选 Bearer Token，/health/docs 白名单 |
| L3 | 冷却 | 按错误类型自动设置冷却（rate_limit 120s / auth 300s / quota 3600s） |
| L4 | 熔断 | 连续 5 次失败熔断 60s，半开 3 次成功恢复，LRU 上限 100 key |
| L5 | 重试 | 指数退避 1→2→4s，429/5xx 自动重试，AuthError 不重试 |
| L6 | 健康检查 | 每 300s 后台探测所有 Provider，自动触发熔断 |

---

## 开发

### 运行测试

```bash
# 全部 139 个测试
uv run pytest

# 单模块
uv run pytest tests/test_circuit.py -v

# 带覆盖率
uv run pytest --cov=openllm
```

### 代码风格

```bash
uv run ruff check openllm/
uv run ruff format openllm/ --check
```

### 添加新 Provider

1. 继承 `Provider` Protocol（`openllm/core/provider.py`）
2. 在 `openllm/providers/` 下实现 `list_models()`、`chat_completion()`、`chat_completion_stream()`
3. 在 `openllm.yaml` 或 `app.py` 中注册

---

## 技术栈

| 组件 | 选型 |
|:-----|:------|
| 框架 | FastAPI 0.115+ |
| HTTP 客户端 | httpx 0.28+ |
| 服务器 | Uvicorn |
| 配置 | PyYAML + JSON |
| 测试 | pytest 9.0+ |
| 代码质量 | ruff |
| 项目工具 | uv |

---

## 许可

MIT License — 详见 [LICENSE](LICENSE)
