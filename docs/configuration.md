# Configuration Guide

## Overview

OpenLLM uses two configuration files:
- `config/models.yaml` - Model configurations
- `config/settings.json` - Server settings

## models.yaml

### Basic Configuration

```yaml
models:
  - name: "model-id"
    protocol: "openai"
    endpoint: "https://api.example.com/v1"
    api_key: "${API_KEY}"
```

### Complete Configuration

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

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | required | Unique model identifier |
| `protocol` | string | required | Protocol type |
| `endpoint` | string | required | API endpoint URL |
| `api_key` | string | "" | API key (supports `${ENV_VAR}`) |
| `enabled` | boolean | true | Enable/disable model |
| `rpm` | integer | 30 | Requests per minute |
| `tpm` | integer | 15000 | Tokens per minute |
| `max_concurrent` | integer | 10 | Max concurrent requests |
| `daily_limit` | integer | 1000 | Daily request limit |
| `cost_limit` | float | 0.0 | Cost limit (USD, 0=unlimited) |
| `quality_weight` | float | 0.4 | Quality score weight |
| `speed_weight` | float | 0.3 | Speed score weight |
| `context_weight` | float | 0.2 | Context score weight |
| `reliability_weight` | float | 0.1 | Reliability score weight |
| `max_context_length` | integer | 128000 | Maximum context length |
| `capabilities` | list | [] | Model capabilities |

## settings.json

### Default Configuration

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

### Parameters

#### Server

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | string | "0.0.0.0" | Server bind address |
| `port` | integer | 8000 | Server port |

#### Context

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | "dynamic" | Context mode |
| `max_tokens` | integer | 128000 | Max tokens |

#### Session

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `affinity_enabled` | boolean | true | Enable session affinity |
| `cache_ttl` | integer | 3600 | Session cache TTL (seconds) |

#### Failover

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | integer | 3 | Max failover attempts |
| `retry_delay` | float | 1.0 | Retry delay (seconds) |

#### Scoring

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | true | Enable scoring |
| `update_interval` | integer | 300 | Update interval (seconds) |

## Protocol Configuration

### OpenAI Protocol

```yaml
- name: "groq/llama-3.3-70b-versatile"
  protocol: "openai"
  endpoint: "https://api.groq.com/openai/v1"
  api_key: "${GROQ_API_KEY}"
```

### Anthropic Protocol

```yaml
- name: "claude-3-haiku"
  protocol: "anthropic"
  endpoint: "https://api.anthropic.com"
  api_key: "${ANTHROPIC_API_KEY}"
```

### REST Protocol

```yaml
- name: "custom-model"
  protocol: "rest"
  endpoint: "https://api.example.com/v1"
  api_key: "${CUSTOM_API_KEY}"
  method: "POST"
  body_template: '{"prompt": "{{content}}"}'
```

### Ollama Protocol

```yaml
- name: "ollama/llama3"
  protocol: "ollama"
  endpoint: "http://localhost:11434"
```

## Environment Variables

### API Keys

```bash
# .env file
GEMINI_API_KEY=your_google_key
GROQ_API_KEY=your_groq_key
MISTRAL_API_KEY=your_mistral_key
CEREBRAS_API_KEY=your_cerebras_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### Server Configuration

```bash
OPENLLM_HOST=0.0.0.0
OPENLLM_PORT=8000
OPENLLM_CONFIG=/path/to/models.yaml
```

## Model Examples

### Groq Models

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

### Mistral Models

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

### Gemini Models

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

### Cerebras Models

```yaml
- name: "cerebras/qwen-3-235b-a22b"
  protocol: "openai"
  endpoint: "https://api.cerebras.ai/v1"
  api_key: "${CEREBRAS_API_KEY}"
  rpm: 30
  tpm: 999999999
```

### Ollama Models

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

## Context Modes

### Static Mode

Keep last N messages exactly.

```json
{
  "context": {
    "mode": "static",
    "max_tokens": 64000
  }
}
```

### Dynamic Mode

Adaptive token tracking.

```json
{
  "context": {
    "mode": "dynamic",
    "max_tokens": 128000
  }
}
```

### Reservoir Mode

Keep recent + extractive summary.

```json
{
  "context": {
    "mode": "reservoir",
    "max_tokens": 128000
  }
}
```

### Adaptive Mode

Auto-detect task type.

```json
{
  "context": {
    "mode": "adaptive",
    "max_tokens": 128000
  }
}
```

## Rate Limit Configuration

### Aggressive (High Traffic)

```yaml
- name: "model-name"
  rpm: 60
  tpm: 30000
  max_concurrent: 20
  daily_limit: 5000
```

### Conservative (Free Tier)

```yaml
- name: "model-name"
  rpm: 10
  tpm: 5000
  max_concurrent: 5
  daily_limit: 500
```

### Balanced

```yaml
- name: "model-name"
  rpm: 30
  tpm: 15000
  max_concurrent: 10
  daily_limit: 1000
```

## Auto Discovery

### Manual Discovery

Use the `discover` command to automatically find available models from configured providers:

```bash
openllm discover
```

This will:
1. Query each configured provider's model list API
2. Add discovered models to `models.yaml` with `enabled: false`
3. Preserve existing configuration

### Supported Providers

| Provider | API Endpoint | Notes |
|----------|--------------|-------|
| OpenAI-compatible | `/v1/models` | Lists all available models |
| Ollama | `/api/tags` | Lists locally installed models |
| Anthropic | N/A | Limited API access |
| REST | Configurable | Must support `/models` endpoint |

### Example

```bash
# Before discovery
$ openllm models
  [✓] groq/llama-3.3-70b-versatile (openai)

# Run discover
$ openllm discover
Discovered 2 new models:
  - gpt-4-turbo (openai)
  - gpt-3.5-turbo (openai)

# After - new models are disabled
$ openllm models
  [✓] groq/llama-3.3-70b-versatile (openai)
  [✗] gpt-4-turbo (openai)
  [✗] gpt-3.5-turbo (openai)
```

## Troubleshooting

### Model Not Loading

Check:
1. `models.yaml` syntax is valid YAML
2. `endpoint` URL is correct
3. `api_key` environment variable is set

### Rate Limit Errors

Check:
1. `rpm` and `tpm` values
2. Other models in pool
3. Increase limits or add more models

### Connection Errors

Check:
1. Network connectivity
2. API key validity
3. Provider status page