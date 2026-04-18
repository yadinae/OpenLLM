# API 参考文档

## 端点

### OpenAI 兼容端点

#### POST /v1/chat/completions

创建对话完成。

**请求：**

```json
{
  "model": "meta-model",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false,
  "session_id": "optional-session-id",
  "model_type": "text",
  "model_scale": "large"
}
```

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `model` | string | 是 | - | 模型名称或 `meta-model` |
| `messages` | array | 是 | - | 消息数组 |
| `temperature` | float | 否 | 0.7 | 采样温度 (0-2) |
| `max_tokens` | integer | 否 | 2048 | 最大生成 token 数 |
| `stream` | boolean | 否 | false | 启用流式输出 |
| `session_id` | string | 否 | - | 会话 ID 用于亲和 |
| `model_type` | string | 否 | - | 过滤：`text`、`coding`、`ocr` |
| `model_scale` | string | 否 | - | 过滤：`small`、`medium`、`large` |

**响应：**

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "meta-model",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  }
}
```

**错误响应 (429)：**

```json
{
  "message": "Rate limit exceeded",
  "type": "error",
  "code": 429
}
```

---

#### GET /v1/models

列出可用模型。

**响应：**

```json
{
  "object": "list",
  "data": [
    {
      "id": "groq/llama-3.3-70b-versatile",
      "object": "model",
      "created": 1700000000,
      "owned_by": "groq"
    }
  ]
}
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `model_type` | 按类型过滤 (`text`, `coding`, `ocr`) |
| `model_scale` | 按规模过滤 (`small`, `medium`, `large`) |

---

#### GET /v1/models/{model}

获取模型信息。

**响应：**

```json
{
  "id": "groq/llama-3.3-70b-versatile",
  "object": "model",
  "created": 1700000000,
  "owned_by": "groq"
}
```

---

#### GET /v1/usage

获取使用统计。

**响应：**

```json
{
  "total_requests": 1000,
  "total_tokens": 50000,
  "model_usage": {
    "groq/llama-3.3-70b-versatile": {
      "success": 950,
      "failure": 50,
      "total": 1000
    }
  }
}
```

---

### OpenLLM 扩展

#### GET /v1/scores

获取模型评分。

**响应：**

```json
{
  "models": [
    {
      "name": "groq/llama-3.3-70b-versatile",
      "total_score": 0.85,
      "quality_score": 0.80,
      "speed_score": 0.90,
      "context_score": 0.75,
      "reliability_score": 0.95,
      "last_updated": "2024-01-01T00:00:00"
    }
  ]
}
```

---

#### POST /v1/scores/refresh

刷新模型评分。

**响应：**

```json
{
  "status": "Scores refreshed"
}
```

---

#### GET /health

��康检查。

**响应：**

```json
{
  "status": "ok",
  "timestamp": 1700000000
}
```

---

## 消息格式

### 消息对象

```json
{
  "role": "user" | "assistant" | "system",
  "content": "消息内容"
}
```

**角色：**
- `system`：系统指令
- `user`：用户消息
- `assistant`：助手响应

---

## 使用统计

### 使用对象

```json
{
  "prompt_tokens": 10,
  "completion_tokens": 8,
  "total_tokens": 18
}
```

---

## 错误代码

| 代码 | 说明 |
|------|------|
| 400 | 请求错误 |
| 401 | 未授权 |
| 404 | 模型未找到 |
| 429 | 速率限制 |
| 500 | 服务器内部错误 |
| 503 | 无可用模型 |

---

## 速率限制

速率限制在 `models.yaml` 中按模型配置：

```yaml
- name: "model-name"
  rpm: 30          # 每分钟请求数
  tpm: 15000     # 每分钟 token 数
  max_concurrent: 10
  daily_limit: 1000
```

---

## 流式输出

设置 `stream: true` 启用流式输出：

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer openllm" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-model",
    "messages": [{"role": "user", "content": "Count to 5"}],
    "stream": true
  }'
```

**流式响应：**

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1700000000,"model":"meta-model","choices":[{"index":0,"delta":{"role":"assistant","content":"1"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1700000000,"model":"meta-model","choices":[{"index":0,"delta":{"content":" 2"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1700000000,"model":"meta-model","choices":[{"index":0,"delta":{"content":" 3"},"finish_reason":null}]}

data: [DONE]
```

---

## 示例

### Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="openllm"
)

response = client.chat.completions.create(
    model="meta-model",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

### cURL

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer openllm" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-model",
    "messages": [
      {"role": "user", "content": "What is 2+2?"}
    ]
  }'
```

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="openllm",
    model="meta-model"
)

response = llm.invoke("Hello!")
print(response.content)
```