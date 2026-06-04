<p align="center">
  <img src="https://img.shields.io/badge/OpenLLM-AI%20Gateway-blueviolet?style=for-the-badge" alt="OpenLLM"/>
</p>

<h1 align="center">OpenLLM — AI API Gateway</h1>

<p align="center">
  <b>协议翻译 · 智能路由 · 熔断保护 · 模型优选 · 零耦合插件</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
  <img src="https://img.shields.io/badge/tests-139_pass-brightgreen" />
  <img src="https://img.shields.io/badge/lint-ruff_0_error-success" />
  <img src="https://img.shields.io/badge/systemd-auto_restart-blue" />
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" />
</p>

---

OpenLLM 是一个轻量级的 AI API 网关，专为多 Provider 场景设计。它让 **Claude Code 可以调用 Groq**，让 **OpenAI SDK 可以连接 Anthropic**，内置智能路由、熔断保护和模型优选。

### 核心功能

- **🔄 协议翻译** — Anthropic Messages API ↔ OpenAI Chat Completions 双向实时翻译，完整 SSE 事件序列
- **🔀 智能路由** — Fallback / Round-Robin / Priority 三种 Combo 路由策略，首 chunk 锁定真流式切换
- **🛡️ 熔断保护** — Circuit Breaker 状态机（CLOSED→OPEN→HALF_OPEN），自动隔离故障 Provider
- **⚡ 指数退避重试** — 瞬态错误自动重试，AuthError 不重试，httpx 原生异常识别
- **📊 模型优选** — 对各 Provider 模型运行基准测试，按速度/质量/成本综合评分，智能推荐
- **📦 RTK 压缩** — 自动检测 git diff / grep / tree / log / JSON 输出类型，压缩至 10-50%
- **🧠 上下文管理** — Static / Dynamic / Reservoir / Adaptive 四种策略，无 LLM 开销
- **🔐 安全加固** — 可选 Bearer Token 认证 + 请求输入校验（消息数/内容长度/角色白名单）
- **🏥 进程守护** — systemd 自动重启 + Docker healthcheck + 启动自检，崩溃秒级恢复

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

## CLI 参考

| 命令 | 说明 |
|:-----|:------|
| `serve` | 启动网关服务器 |
| `list-providers` | 列出已注册的 Provider |
| `doctor` | 诊断配置和连通性 |
| `bind` | 一键配置 AI 客户端工具 |
| `rank` | 运行模型基准测试，生成评分 |
| `recommend` | 根据偏好推荐最优模型 |

### `openllm rank` — 模型基准测试

```bash
# 测试所有 Provider 的所有模型
openllm rank

# 仅测试指定 Provider
openllm rank --provider deepseek

# 仅测试指定模型
openllm rank --provider openrouter --model deepseek-chat
```

### `openllm recommend` — 模型推荐

```bash
# 综合推荐（默认）
openllm recommend

# 按速度排序
openllm recommend --by speed

# 按质量排序
openllm recommend --by quality

# 按性价比排序
openllm recommend --by cost
```

---

## 架构

```
┌─────────────┐    ┌──────────────────────────────────────────┐
│  客户端工具   │    │              OpenLLM Gateway               │
│             │    │                                            │
│ Claude Code │    │  ┌──────────┐  ┌──────────────────────┐   │
│ OpenAI SDK  │───▶│  │ 协议翻译  │─▶│     路由引擎          │   │
│ aider       │    │  │ (Anthropic│  │  Combo/Fallback      │   │
│ Cursor      │    │  │  ↔OpenAI)│  │  Round-Robin         │───▶───▶ Provider A
│ Hermes      │    │  └──────────┘  └──────────────────────┘   │   (Groq/OpenRouter/...)
└─────────────┘    │                                            │
                   │  ┌──────────┐  ┌──────────────────────┐   │
                   │  │ 熔断器   │  │   冷却管理器          │   │
                   │  │ Circuit  │  │  Cooldown             │   │
                   │  │ Breaker  │  │  Manager              │   │
                   │  └──────────┘  └──────────────────────┘   │
                   │                                            │
                   │  ┌──────────┐  ┌──────────────────────┐   │
                   │  │ 模型优选  │  │   RTK 压缩 / 上下文   │   │
                   │  │ Ranker   │  │   4 种策略            │   │
                   │  └──────────┘  └──────────────────────┘   │
                   └──────────────────────────────────────────┘
```

### 目录结构

```
openllm/
├── cli/                  # CLI 入口 + 客户端绑定
│   ├── __init__.py       # 命令行（serve/list/doctor/bind/rank/recommend）
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
│   ├── provider.py       # Provider 插件协议
│   ├── state.py          # 数据持久化 + 原子写入
│   └── ranker.py         # 模型优选引擎（基准测试 + 评分 + 推荐）
├── context/              # 上下文管理
│   └── manager.py        # 4 种策略
├── optimize/             # RTK 工具输出压缩
│   └── rtk.py            # git diff/grep/tree/log/JSON 压缩器
├── providers/            # Provider 适配器
│   └── openai_compat.py  # OpenAI 兼容 API 通用适配器
├── server/               # HTTP 服务器
│   ├── app.py            # FastAPI 应用工厂 + 后台健康检查 + 启动自检
│   ├── validation.py     # 请求输入校验
│   └── routes/           # API 路由
│       ├── chat.py       # /v1/chat/completions
│       ├── messages.py   # /v1/messages (Anthropic)
│       ├── models.py     # /v1/models
│       ├── health.py     # /health
│       └── rankings.py   # /v1/models/rankings + /v1/models/recommend
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

### `/v1/models/rankings` — 模型排名

```
GET /v1/models/rankings?sort_by=speed&top_n=10
```

按速度/质量/成本/综合评分排序，返回所有模型的基准测试结果。

### `/v1/models/recommend` — 模型推荐

```
GET /v1/models/recommend?preference=balanced&top_n=3
```

根据偏好推荐最优模型。preference 可选：`speed` / `quality` / `cost` / `balanced`。

### `/health` — 健康检查

```
GET /health → {"status": "ok", "providers": ["groq", "openrouter", ...]}
```

---

## 模型优选系统

对各 Provider 的模型进行自动基准测试，提供多维评分和智能推荐。

### 评分维度

| 维度 | 权重 | 说明 |
|:-----|:-----|:------|
| ⚡ 速度 | 30% | 基于 TTFT 和 tokens/s 的百分位排名 |
| 🎯 质量 | 50% | 生成内容的质量评分（代码正确性、完整性、相关性） |
| 💰 成本 | 20% | 基于已知定价的性价比评分（免费模型满分） |

### 工作流程

```
openllm rank
  │
  ├── 发现所有 Provider 的模型
  ├── 速度测试 (3 次非流式取平均)
  ├── 质量测试 (中等长度回复评估)
  ├── 计算百分位评分
  └── 持久化到 ~/.openllm/rankings.json

openllm recommend --by quality
  │
  └── 从 rankings.json 读取 → 按偏好排序 → Top 5
```

---

## Docker 部署

```bash
# 1. 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入 API key

# 2. 启动
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 停止
docker compose down
```

**Docker Compose 特性：**

- `restart: unless-stopped` — 容器崩溃自动重启
- Healthcheck 每 15 秒探测 `/health`
- 内存限制 512MB，预留 128MB
- 持久化 volume 保存熔断器冷却状态

---

## systemd 自动重启

OpenLLM 提供 systemd user service 支持，进程崩溃后 **5 秒**自动恢复。

```bash
# 启用（当前用户级别，无需 sudo）
systemctl --user enable openllm-gateway
systemctl --user start openllm-gateway

# 查看状态
systemctl --user status openllm-gateway

# 查看日志
journalctl --user -u openllm-gateway -f
```

**保护机制：**
- `Restart=on-failure`: 仅崩溃时重启（正常 stop 不会重启）
- `RestartSec=5`: 5 秒后重试
- `StartLimitBurst=3`: 60 秒内最多重启 3 次，防止 crash loop

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
| L7 | 启动自检 | 启动前验证 YAML 结构、API key 完整性、Combo 引用 |
| L8 | 进程守护 | systemd 崩溃 5s 自愈 + Docker restart policy + healthcheck |

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
| 部署 | Docker / systemd |

---

## 文档

| 文档 | 说明 |
|:-----|:------|
| [Provider & Combo 用户指南](docs/provider-combo-user-guide.md) | 配置 Provider、Combo 路由、客户端调用、故障排查（中文） |
| [Provider & Combo 深度分析](docs/provider-combo-system.md) | 源码级架构、模块依赖、容错实现（英文） |

## 许可

MIT License — 详见 [LICENSE](LICENSE)
