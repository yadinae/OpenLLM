# API Reference

## Endpoints

### OpenAI Compatible Endpoints

#### POST /v1/chat/completions

Create a chat completion.

**Request:**

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

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model name or `meta-model` |
| `messages` | array | Yes | - | Messages array |
| `temperature` | float | No | 0.7 | Sampling temperature (0-2) |
| `max_tokens` | integer | No | 2048 | Max tokens to generate |
| `stream` | boolean | No | false | Enable streaming |
| `session_id` | string | No | - | Session ID for affinity |
| `model_type` | string | No | - | Filter: `text`, `coding`, `ocr` |
| `model_scale` | string | No | - | Filter: `small`, `medium`, `large` |

**Response:**

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

**Error Response (429):**

```json
{
  "message": "Rate limit exceeded",
  "type": "error",
  "code": 429
}
```

---

#### GET /v1/models

List available models.

**Response:**

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

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_type` | Filter by type (`text`, `coding`, `ocr`) |
| `model_scale` | Filter by scale (`small`, `medium`, `large`) |

---

#### GET /v1/models/{model}

Get model information.

**Response:**

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

Get usage statistics.

**Response:**

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

### OpenLLM Extensions

#### GET /v1/scores

Get model scores.

**Response:**

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

Refresh model scores.

**Response:**

```json
{
  "status": "Scores refreshed"
}
```

---

#### GET /health

Health check.

**Response:**

```json
{
  "status": "ok",
  "timestamp": 1700000000
}
```

---

## Message Format

### Message Object

```json
{
  "role": "user" | "assistant" | "system",
  "content": "Message content"
}
```

**Roles:**
- `system`: System instructions
- `user`: User messages
- `assistant`: Assistant responses

---

## Usage Statistics

### Usage Object

```json
{
  "prompt_tokens": 10,
  "completion_tokens": 8,
  "total_tokens": 18
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Model Not Found |
| 429 | Rate Limited |
| 500 | Internal Server Error |
| 503 | No Available Models |

---

## Rate Limits

Rate limits are configured per-model in `models.yaml`:

```yaml
- name: "model-name"
  rpm: 30          # Requests per minute
  tpm: 15000     # Tokens per minute
  max_concurrent: 10
  daily_limit: 1000
```

---

## Streaming

Enable streaming by setting `stream: true`:

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

**Stream Response:**

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1700000000,"model":"meta-model","choices":[{"index":0,"delta":{"role":"assistant","content":"1"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1700000000,"model":"meta-model","choices":[{"index":0,"delta":{"content":" 2"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1700000000,"model":"meta-model","choices":[{"index":0,"delta":{"content":" 3"},"finish_reason":null}]}

data: [DONE]
```

---

## Examples

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