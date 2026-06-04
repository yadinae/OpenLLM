# OpenLLM Provider & Combo 用户指南

> OpenLLM v0.1.0 — AI API Gateway
> GitHub: https://github.com/yadinae/OpenLLM

---

## 目录

1. [架构总览](#1-架构总览)
2. [Provider 配置与注册](#2-provider-配置与注册)
3. [模型自动发现](#3-模型自动发现)
4. [Combo 路由策略](#4-combo-路由策略)
5. [路由解析流程](#5-路由解析流程)
6. [客户端调用方式](#6-客户端调用方式)
7. [配置示例大全](#7-配置示例大全)
8. [CLI 命令参考](#8-cli-命令参考)
9. [故障排查](#9-故障排查)

---

## 1. 架构总览

```
用户请求 (model="auto")
  │
  ▼
┌─────────────────────────────────────────┐
│            Route Resolution              │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Combo    │  │Provider/ │  │ Global  │ │
│  │ 匹配     │→ │Model     │→ │ 模型搜索│ │
│  └──────────┘  │解析      │  └────────┘ │
│                └──────────┘             │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│            Core Engine                   │
│  ┌──────────┐  ┌──────────┐             │
│  │ Registry │  │  Combo   │  Fallback   │
│  │ (Provider│◀─│  Engine  │──────────▶  │
│  │  列表)   │  │          │  deepseek   │
│  └──────────┘  └──────────┘  (失败→)     │
│  ┌──────────┐  ┌──────────┐    nvidia   │
│  │ Circuit  │  │ Cooldown │             │
│  │ Breaker  │  │ Manager  │             │
│  └──────────┘  └──────────┘             │
└────────────────┬────────────────────────┘
                 │
                 ▼
        OpenAI 兼容 Provider
        (DeepSeek / NVIDIA / 自定义...)
```

**核心设计原则**：
- **零耦合插件架构**：`Provider` 是 Protocol 接口，核心不依赖具体实现
- **协议翻译**：Anthropic ↔ OpenAI 双向实时翻译（`/v1/messages` 路由）
- **三级路由**：Combo 名 → `provider/model` 前缀 → 全局模型自动发现

---

## 2. Provider 配置与注册

### 2.1 配置文件方式（推荐）

编辑项目根目录 `openllm.yaml`：

```yaml
providers:
  # 标准 OpenAI 兼容 API
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY   # 从环境变量读取 API Key
    timeout: 30                      # 请求超时（秒），可选

  nvidia:
    endpoint: https://integrate.api.nvidia.com/v1
    api_key_env: NVIDIA_API_KEY
    timeout: 60

  opencode:
    endpoint: https://opencode.ai/zen/go/v1
    api_key_env: OPENCODE_API_KEY
    timeout: 60

  # 不需要 API Key 的本地模型
  ollama:
    endpoint: http://localhost:11434/v1
    api_key_env: ""                  # 空字符串 = 不传 Authorization header
    timeout: 120

  # 直接配置 API Key（不推荐，会暴露在配置里）
  my_provider:
    endpoint: https://api.example.com/v1
    api_key: "sk-..."                # 直接写 Key
    timeout: 30
```

**添加新 Provider 只需三步**：

1. 在 `openllm.yaml` 的 `providers:` 下新增一段
2. 设置对应的环境变量（或直接写 `api_key`）
3. 重启服务

> **注意**：`timeout` 可选，默认 30 秒。`api_key_env` 为空字符串时，请求不携带 `Authorization` 头。

### 2.2 环境变量自动发现（无配置文件时）

如果没有 `openllm.yaml`，系统会自动检查以下环境变量并注册 Provider：

| 环境变量 | 自动注册的 Provider | 端点 |
|:---------|:--------------------|:-----|
| `OPENROUTER_API_KEY` | `openrouter` | https://openrouter.ai/api/v1 |
| `GROQ_API_KEY` | `groq` | https://api.groq.com/openai/v1 |
| `DEEPSEEK_API_KEY` | `deepseek` | https://api.deepseek.com/v1 |
| `NVIDIA_API_KEY` | `nvidia` | https://integrate.api.nvidia.com/v1 |
| `CEREBRAS_API_KEY` | `cerebras` | https://api.cerebras.ai/v1 |

只要这些环境变量被设置，启动时自动注册，无需任何配置文件。

### 2.3 配置加载优先级

```
1. openllm.yaml （当前目录优先）
2. openllm.json
3. config.yaml
4. config.json
5. ~/.openllm/ 下的上述文件
6. 环境变量自动发现（硬编码 fallback）
```

### 2.4 编程方式动态注册

```python
from openllm.server.app import registry
from openllm.core.types import ProviderConfig
from openllm.providers.openai_compat import OpenAICompatProvider

cfg = ProviderConfig(
    name="my-provider",
    endpoint="https://api.example.com/v1",
    api_key="sk-...",
)
provider = OpenAICompatProvider(cfg)
registry.register("my-provider", provider)

# 注册后立即发现模型
import asyncio
asyncio.run(registry.discover_models())
```

这对非标准 Provider 的场景很有用，比如需要先获取临时 Token、或对接特殊认证流程。

---

## 3. 模型自动发现

### 3.1 发现流程

每次服务启动时，系统自动对**每个已注册 Provider** 调用 `GET /v1/models`：

```
openllm serve
  │
  ├── 加载配置，注册 Provider
  │
  └── 对每个 Provider 调用 list_models()
        ├── deepseek → GET https://api.deepseek.com/v1/models → 发现 2 个模型
        ├── nvidia   → GET https://integrate.api.nvidia.com/v1/models → 发现 100+ 个
        ├── opencode → GET https://opencode.ai/zen/go/v1/models → 发现多个
        └── router   → GET http://8.208.28.70:20128/v1/models → 发现多个
              │
              └── 缓存到 ~/.openllm/registry.json
```

发现的模型以 **`provider/model_id`** 格式对外暴露：

```
GET /v1/models → {
  "object": "list",
  "data": [
    {"id": "deepseek/deepseek-v4-flash", "object": "model", "owned_by": "deepseek"},
    {"id": "nvidia/01-ai/yi-large",      "object": "model", "owned_by": "nvidia"},
    {"id": "opencode/deepseek-v4-flash", "object": "model", "owned_by": "opencode"},
    ...
  ]
}
```

> 如果某个 Provider 的 `GET /v1/models` 失败（比如网络问题），该 Provider 的模型列表为空，不影响其他 Provider 的发现。

### 3.2 模型名格式

OpenLLM 接受三种格式的模型名：

| 格式 | 示例 | 解析方式 |
|:-----|:-----|:---------|
| **Combo 名** | `auto`、`fast`、`free` | 匹配 combos 配置，走多 Provider 路由 |
| **Provider/Model** | `deepseek/deepseek-v4-flash` | 拆分第一部分为 Provider，第二部分为模型 |
| **裸模型名** | `yi-large` | 全局搜索所有 Provider 的模型缓存 |

---

## 4. Combo 路由策略

Combo 是 OpenLLM 的核心特性——**一组 Provider 的路由组**。客户端只需传入 combo 名称，系统自动在多 Provider 间做故障切换或负载均衡。

### 4.1 配置语法

```yaml
combos:
  combo名称:
    strategy: fallback          # 路由策略
    members:
      - model: auto              # 传给该 Provider 的 model 参数
        provider: deepseek        # 对应 providers 里注册的名字
        priority: 0               # 优先级（0 最高）
      - model: auto
        provider: nvidia
        priority: 1
```

### 4.2 三种路由策略

| 策略 | 行为 | 适用场景 |
|:-----|:------|:---------|
| **`fallback`** | 按优先级依次尝试，**第一个成功的返回**。失败自动冷却 + 切下一个 | 主备切换、高可用 |
| **`priority`** | 同 `fallback`，语义别名 | — |
| **`round_robin`** | 轮询所有可用成员（跳过冷却中的），下一次从上一次中止处继续 | 负载均衡、多 Key 轮换 |

### 4.3 当前配置的 Combo

```yaml
combos:
  auto:
    strategy: fallback
    members:
      - model: auto;  provider: opencode;  priority: 0
      - model: auto;  provider: deepseek;  priority: 1
      - model: auto;  provider: router;    priority: 2
      - model: auto;  provider: nvidia;    priority: 3

  fast:
    strategy: fallback
    members:
      - model: auto;  provider: opencode;  priority: 0
      - model: auto;  provider: deepseek;  priority: 1

  free:
    strategy: fallback
    members:
      - model: auto;  provider: opencode;  priority: 0
```

**`model: auto`** 是什么？特殊值 `auto` 表示使用该 Provider 的**默认模型**（由 Provider 自身决定，通常是其最通用的模型）。

### 4.4 冷却时长

当 Provider 失败时，自动进入冷却，冷却期间跳过该 Provider：

| 错误类型 | 冷却时长 |
|:---------|:---------|
| 超时 (timeout) | 30 秒 |
| 限速 (rate_limit) | 60 秒 |
| 服务不可用 (server_error) | 60 秒 |
| 过载 (overloaded) | 120 秒 |
| 认证失败 (auth) | 300 秒 |
| 模型不存在 (model_not_found) | 600 秒 |
| 额度耗尽 (quota_exhausted) | 3600 秒（1 小时） |
| 未知错误 | 60 秒 |

### 4.5 Fallback 执行流程

```
请求 model = "auto"
  │
  ├── opencode（priority: 0）
  │     ├── 是否在冷却？ → 是 → 跳过
  │     ├── 是否注册？   → 否 → 跳过
  │     └── 调用 chat_completion()
  │           ├── 成功 → ✅ 返回结果
  │           └── 失败 → 记录冷却，继续下一个
  │
  ├── deepseek（priority: 1）
  │     ├── 是否在冷却？ → 是 → 跳过
  │     └── 尝试调用...
  │           ├── 成功 → ✅ 返回结果
  │           └── 失败 → 记录冷却，继续下一个
  │
  ├── router（priority: 2）
  │     └── 同上...
  │
  └── nvidia（priority: 3）
        └── 同上...
              └── 全部失败 → 503 AllProvidersFailedError
```

### 4.6 流式 Fallback

流式请求使用 **"首 chunk 锁定"** 策略：

1. 按优先级尝试 Provider
2. 第一个返回了首个数据块的 Provider 被锁定
3. 后续所有数据块从该 Provider 持续转发
4. 中途 Provider 断开 → 不会切换（流式切换太复杂，容易丢数据）

---

## 5. 路由解析流程

当客户端发送聊天请求时，`model` 参数按照以下流程解析：

```
model = "auto"
  │
  ├── 1. Combo 匹配
  │     └── "auto" 在 combos 配置中吗？
  │           ├── 是 → 走 Combo 路由
  │           └── 否 → 下一步
  │
  ├── 2. Provider/Model 解析
  │     └── 包含 "/" 吗？
  │           ├── 是 → 拆分为 (provider, model)，查 Registry
  │           │         ├── 找到 Provider → 直接转发
  │           │         └── 没找到 → 下一步
  │           └── 否 → 下一步
  │
  ├── 3. 全局模型搜索
  │     └── 遍历所有 Provider 的模型缓存
  │           ├── ID 精确匹配 → 自动识别所属 Provider
  │           └── 完全没找到 → 404
  │
  └── 每一步都有保护：
        ├── 冷却检查 → 429
        └── 熔断检查 → 503
```

---

## 6. 客户端调用方式

### 6.1 OpenAI SDK（标准方式）

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:11343/v1",
    api_key="any-key",  # OpenLLM 不验证 key，占位即可
)

# 方式 1：指定具体 Provider/Model
response = client.chat.completions.create(
    model="deepseek/deepseek-v4-flash",
    messages=[{"role": "user", "content": "Hello"}],
)

# 方式 2：使用 Combo 自动路由
response = client.chat.completions.create(
    model="auto",   # 自动 fallback: opencode→deepseek→router→nvidia
    messages=[{"role": "user", "content": "Hello"}],
)

# 方式 3：裸模型名（自动全局搜索）
response = client.chat.completions.create(
    model="yi-large",  # 在所有 Provider 中查找
    messages=[{"role": "user", "content": "Hello"}],
)

# 流式
stream = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

### 6.2 cURL

```bash
# 指定 Provider/Model
curl http://127.0.0.1:11343/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek/deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 100
  }'

# 使用 Combo 路由
curl http://127.0.0.1:11343/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 流式
curl http://127.0.0.1:11343/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "fast",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

### 6.3 Anthropic SDK

OpenLLM 支持 Anthropic Compatible API：

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://127.0.0.1:11343",
    api_key="any-key",
)

response = client.messages.create(
    model="auto",  # Combo 名称同样生效
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello"}],
)
```

---

## 7. 配置示例大全

### 7.1 最小配置——单 Provider

```yaml
providers:
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
```

### 7.2 多 Provider + 高可用 Combo

```yaml
providers:
  groq:
    endpoint: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
  nvidia:
    endpoint: https://integrate.api.nvidia.com/v1
    api_key_env: NVIDIA_API_KEY

combos:
  production:
    strategy: fallback
    members:
      - model: auto;  provider: groq;      priority: 0
      - model: auto;  provider: deepseek;  priority: 1
      - model: auto;  provider: nvidia;    priority: 2
```

### 7.3 轮询负载均衡——多 Key 分摊

```yaml
providers:
  deepseek_key1:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_KEY1
  deepseek_key2:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_KEY2
  deepseek_key3:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_KEY3

combos:
  load_balanced:
    strategy: round_robin
    members:
      - model: auto;  provider: deepseek_key1;  priority: 0
      - model: auto;  provider: deepseek_key2;  priority: 0
      - model: auto;  provider: deepseek_key3;  priority: 0
```

### 7.4 纯本地模型

```yaml
providers:
  ollama:
    endpoint: http://localhost:11434/v1
    api_key_env: ""   # 不需要认证
  vllm:
    endpoint: http://localhost:8000/v1
    api_key_env: ""
```

### 7.5 .env 文件

启动时自动加载 `cwd/.env` 或 `~/.openllm/.env`：

```bash
# .env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENCODE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ROUTER_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 8. CLI 命令参考

| 命令 | 说明 |
|:-----|:------|
| `openllm serve` | 启动网关服务 |
| `openllm serve --port 8080` | 指定端口 |
| `openllm serve --host 0.0.0.0` | 监听所有网卡 |
| `openllm serve --reload` | 热重载模式（开发用） |
| `openllm serve --log-level debug` | 详细日志 |
| `openllm serve --api-key sk-xxx` | 设置 Bearer Token 认证 |
| `openllm list-providers` | 列出已注册的 Provider 及模型数量 |
| `openllm doctor` | 诊断检查—验证配置和 Provider 连通性 |

### 启动示例

```bash
# 标准启动
cd /home/admin/projects/openllm
.venv/bin/python -m openllm.cli serve

# 自定义端口
.venv/bin/python -m openllm.cli serve --port 8080 --log-level debug

# 加载自定义配置
OPENLLM_CONFIG=/path/to/my-config.yaml .venv/bin/python -m openllm.cli serve
```

### 验证服务

```bash
# 健康检查
curl http://127.0.0.1:11343/health
# → {"status":"healthy","providers":["deepseek","nvidia","router","opencode"]}

# 模型列表
curl http://127.0.0.1:11343/v1/models | jq '.data | length'
# → 188+

# 聊天测试
curl http://127.0.0.1:11343/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek/deepseek-v4-flash","messages":[{"role":"user","content":"hi"}]}'
```

---

## 9. 故障排查

### Provider 注册失败

```
GET /health → {"providers":[]}
```

可能原因：
- API Key 未设置 → 检查环境变量名与 `api_key_env` 是否一致
- `api_key_env: ""` 情况下被跳过 → 注意空字符串表示不传 key，但 Provider 本身仍需能响应
- 网络问题 → 检查 endpoint 是否可达

### Provider 返回 502

```
Provider XXX failed: ...
```

检查 OpenLLM 日志：
- 限速 → 自动冷却，等待冷却结束
- 认证失败 → 检查 API Key 是否过期
- 模型名不存在 → 用 `GET /v1/models` 确认正确的模型名

### Combo 全部失败

```
503 All providers failed: [("opencode","cooled"), ("deepseek","500"), ...]
```

每个成员都失败后触发。查看冷却状态：
```bash
# 检查 registry.json 里的冷却信息
cat ~/.openllm/cooldown.json
```

### 模型名找不到

```
404 No provider found for 'xxx'
```

可能的修复：
1. 确认模型名写法：`provider/model` 或裸模型名
2. 检查对应 Provider 是否正常注册
3. 用 `GET /v1/models` 查看可用模型列表
4. 如果模型名包含 `/`，确保第一部分是 Provider 名而非模型名的一部分

---

## 附录：文件结构

```
openllm/
├── openllm.yaml              # 配置文件（Provider + Combo）
├── .env                      # 环境变量（API Key）
├── openllm/
│   ├── cli/                  # CLI 命令
│   ├── server/
│   │   ├── app.py            # FastAPI 应用 + 配置加载
│   │   └── routes/
│   │       └── chat.py       # 聊天路由 + 路由解析逻辑
│   ├── core/
│   │   ├── types.py          # 数据类型（ComboConfig, ProviderConfig...）
│   │   ├── provider.py       # Provider Protocol 接口
│   │   ├── combo.py          # ComboEngine（路由引擎）
│   │   ├── registry.py       # Provider 注册表
│   │   ├── cooldown.py       # 冷却管理器
│   │   └── retry.py          # 重试逻辑
│   └── providers/
│       └── openai_compat.py  # OpenAI 兼容 Provider 实现
├── tests/                    # 139 个测试
└── docs/                     # 文档
```
