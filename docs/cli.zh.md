# CLI 参考文档

## 命令

### serve

启动 OpenLLM 服务器。

```bash
openllm serve [选项]
```

**选项：**

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | string | "0.0.0.0" | 服务器主机 |
| `--port` | int | 8000 | 服务器端口 |
| `--reload` | bool | false | 启用自动重载 |
| `--config` | string | - | 配置文件路径 |

**示例：**

```bash
# 默认
openllm serve

# 自定义端口
openllm serve --port 9000

# 指定配置
openllm serve --config /path/to/models.yaml

# 开发模式
openllm serve --reload
```

---

### status

显示 OpenLLM 状态。

```bash
openllm status
```

**输出示例：**

```
OpenLLM Status
  Total models: 7
  Enabled: 5

Top models:
  groq/llama-3.3-70b-versatile: 0.850
  mistral/mistral-large-latest: 0.820
```

---

### models

列出可用的模型。

```bash
openllm models [选项]
```

**选项：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `--list` | bool | 列出模型（默认） |

**示例：**

```bash
openllm models
```

**输出示例：**

```
Available models:
  [✓] groq/llama-3.3-70b-versatile (openai)
  [✓] mistral/mistral-large-latest (openai)
  [✓] gemini/gemini-2.5-flash (openai)
  [✓] cerebras/qwen-3-235b-a22b (openai)
  [✗] ollama/llama3 (ollama)
```

---

### score

显示模型评分。

```bash
openllm score [选项]
```

**选项：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `--refresh` | bool | 刷新评分 |

**示例：**

```bash
openllm score
```

**输出示例：**

```
Model scores:
  groq/llama-3.3-70b-versatile: total=0.850 quality=0.800 speed=0.900
  mistral/mistral-large-latest: total=0.820 quality=0.810 speed=0.850
  gemini/gemini-2.5-flash: total=0.780 quality=0.750 speed=0.850
```

---

### config

显示配置信息。

```bash
openllm config [选项]
```

**选项：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `--show` | bool | 显示配置（默认） |

**示例：**

```bash
openllm config
```

**输出示例：**

```
Current configuration:

Model: groq/llama-3.3-70b-versatile
  Protocol: openai
  Endpoint: https://api.groq.com/openai/v1
  RPM: 30
  TPM: 6000

Model: mistral/mistral-large-latest
  Protocol: openai
  Endpoint: https://api.mistral.ai/v1
  RPM: 30
  TPM: 15000
```

---

### discover

从配置的模型供应商发现可用的模型。

```bash
openllm discover
```

**说明：**

此命令会查询所有已配置的模型供应商，发现可用的模型。新发现的模型会自动添加到 `models.yaml`，并设置为 `enabled: false`，让你可以手动审核和启用。

**示例：**

```bash
openllm discover
```

**输出示例：**

```
Discovered 3 new models:
  - gpt-4-turbo (openai)
  - gpt-3.5-turbo (openai)
  - llama3:8b (ollama)

Models saved to /path/to/models.yaml (enabled: false)
```

**支持的供应商：**

| 供应商 | 端点 | 说明 |
|--------|------|------|
| OpenAI 兼容 | `/v1/models` | 列出所有账户模型 |
| Ollama | `/api/tags` | 列出本地模型 |
| Anthropic | N/A | 仅返回当前模型（API 限制） |
| REST | `/models` | 自定义端点 |

---

### test

测试已配置的模型可用性和能力。

```bash
openllm test [选项]
```

**选项：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `--all` | bool | 测试所有模型，包括禁用的 |

**示例：**

```bash
openllm test
```

**输出示例：**

```
Testing enabled models...
  ✅ groq/llama-3.3-70b-versatile (70b): available (120ms), context: 131072, capabilities: [coding, math]
  ❌ mistral/mistral-large-latest: unavailable

Results: 1/2 models available
```

---

### freeride

FreeRide 模式 - 自动发现并连接免费 LLM API，实现 token 自由。

```bash
openllm freeride [选项]
```

**选项：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `--enable` | bool | 启用 FreeRide 模式 |
| `--disable` | bool | 禁用 FreeRide 模式 |
| `--status` | bool | 显示 FreeRide 状态 |
| `--providers` | string | 逗号分隔的供应商列表 |

**示例：**

```bash
# 启用所有供应商
openllm freeride --enable

# 指定供应商
openllm freeride --enable --providers groq,cerebras

# 显示状态
openllm freeride --status
```

**支持的供应商：**

- Groq (llama-3.3-70b-versatile, qwen3-32b)
- Cerebras (llama3.1-8b, qwen-3-235b-a22b)
- OpenRouter (deepseek-r1:free, llama-3.3-70b:free)
- Mistral (mistral-small, codestral)
- Gemini (gemini-2.5-flash)
- Ollama (llama3, mistral)

---

### provider

添加自定义供应商并自动发现其模型。

```bash
openllm provider --add --name <名称> --endpoint <URL> [选项]
```

**选项：**

| 选项 | 类型 | 说明 |
|------|------|------|
| `--add` | bool | 添加新供应商 |
| `--name` | string | 供应商名称 |
| `--endpoint` | string | 供应商 API 端点 |
| `--api-key` | string | API 密钥 |
| `--protocol` | string | 协议 (openai/ollama/anthropic/rest) |
| `--discover` | bool | 添加后自动发现模型 |

**示例：**

```bash
# 添加新供应商
openllm provider --add --name myprovider --endpoint https://api.myprovider.com/v1

# 带 API 密钥
openllm provider --add --name myprovider --endpoint https://api.myprovider.com/v1 --api-key sk-xxx

# 添加并发现模型
openllm provider --add --name myprovider --endpoint https://api.myprovider.com/v1 --discover
```

---

## Python API

### 运行服务器

```python
from openllm.src.server import run

# 默认
run()

# 自定义
run(host="127.0.0.1", port=9000, reload=False)
```

### 编程式使用

```python
from openllm.src.registry import get_registry
from openllm.src.dispatcher import get_dispatcher
from openllm.src.models import ChatRequest, Message

# 获取调度器
dispatcher = get_dispatcher()

# 创建请求
request = ChatRequest(
    model="meta-model",
    messages=[Message(role="user", content="Hello!")]
)

# 执行
response = await dispatcher.dispatch(request)

print(response.choices[0].message.content)
```

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENLLM_HOST` | 服务器主机 |
| `OPENLLM_PORT` | 服务器端口 |
| `OPENLLM_CONFIG` | 配置文件路径 |
| `GEMINI_API_KEY` | Google Gemini API 密钥 |
| `GROQ_API_KEY` | Groq API 密钥 |
| `MISTRAL_API_KEY` | Mistral API 密钥 |
| `CEREBRAS_API_KEY` | Cerebras API 密钥 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |