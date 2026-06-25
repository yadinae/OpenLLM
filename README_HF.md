---
title: OpenLLM Gateway
emoji: "\U0001F680"
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# OpenLLM — AI API Gateway

多 Provider 路由网关: 协议翻译 (Anthropic↔OpenAI), 智能故障转移, 熔断保护, RTK 压缩.

## 部署步骤

### 1. 创建 Space

在 [huggingface.co/new-space](https://huggingface.co/new-space) 创建新 Space, 选择 **Docker** SDK.

### 2. 上传 Dockerfile

将此仓库的 `Dockerfile.hf` 作为 Space 的 Dockerfile (重命名为 `Dockerfile`).

### 3. 配置 Secrets

在 Space 的 **Settings → Variables and secrets → Secrets** 中添加你的 Provider API Keys:

| Secret 名称 | 说明 |
|-------------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `GROQ_API_KEY` | Groq API 密钥 |
| `OPENROUTER_API_KEY` | OpenRouter API 密钥 |
| `NVIDIA_API_KEY` | NVIDIA API 密钥 |
| `CEREBRAS_API_KEY` | Cerebras API 密钥 |
| `ROUTER_API_KEY` | 网关认证密钥 (可选, 设置后请求需 Bearer Token) |

### 4. 自定义配置 (可选)

如果不设置配置, OpenLLM 使用内置回退模式 — 根据你提供的 API Keys 自动注册对应 Provider.

如需自定义 Provider 和 Combo 路由, 在 **Settings → Variables and secrets → Variables** 中设置 `OPENLLM_CONFIG`, 值为 YAML 字符串:

```yaml
providers:
  deepseek:
    endpoint: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    timeout: 30
  groq:
    endpoint: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    timeout: 30

combos:
  auto:
    strategy: fallback
    members:
      - model: auto
        provider: deepseek
        priority: 0
      - model: auto
        provider: groq
        priority: 1
```

### 5. 等待构建

Space 会自动构建并启动. 首次构建约 2-5 分钟 (安装依赖).

## API 端点

| 端点 | 说明 |
|------|------|
| `/health` | 健康检查 |
| `/v1/models` | 列出可用模型 |
| `/v1/chat/completions` | OpenAI 格式聊天 |
| `/v1/messages` | Anthropic 格式消息 |

## 休眠与保活

免费 CPU 档会在 48 小时无请求后自动休眠. 用 [UptimeRobot](https://uptimerobot.com/) 每 5 分钟 ping `/health` 端点即可保活.

## 其他部署方式

- **Fly.io**: `fly deploy` (使用原版 Dockerfile)
- **Docker**: `docker run` (使用原版 Dockerfile)
- **Cloudflare Containers**: `wrangler deploy` (使用原版 Dockerfile)

详见 [GitHub 仓库](https://github.com/yadinae/OpenLLM).
