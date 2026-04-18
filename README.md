# OpenLLM

<p align="center">
  <strong>AI Model Aggregation Platform with Scoring</strong><br>
  One endpoint. Multiple free AI models. Automatic failover. Smart scoring.
</p>

<p align="center">
  <a href="README.zh.md">中文版</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/openllm/"><img src="https://img.shields.io/pypi/v/openllm.svg" alt="PyPI"></a>
  <a href="https://python.org"><img src="https://img.shields.io/python/py-3.10+/openllm" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/openllm" alt="License"></a>
</p>

## Features

- **Multi-Protocol Adapters**: OpenAI, Anthropic, REST, Ollama protocols
- **Model Scoring**: Automatic quality-based ranking
- **Rate Control**: Per-model RPM/TPM/Concurrency/Daily limits
- **Automatic Failover**: Switch models on rate limit
- **Context Management**: Static, Dynamic, Reservoir, Adaptive modes
- **Session Affinity**: Pin users to providers for caching
- **OpenAI Compatible**: Drop-in for existing code
- **CLI Management**: Command-line tools

## Installation

```bash
pip install openllm
```

Or install from source:

```bash
pip install -e .
```

## Quick Start

### 1. Configure API Keys

Create a `.env` file:

```bash
# Free tier API keys
GEMINI_API_KEY=your_google_gemini_key
GROQ_API_KEY=your_groq_key
MISTRAL_API_KEY=your_mistral_key
CEREBRAS_API_KEY=your_cerebras_key
```

Or export in shell:

```bash
export GEMINI_API_KEY="your-key"
export GROQ_API_KEY="your-key"
```

### 2. Configure Models

Edit `config/models.yaml`:

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

### 3. Start Server

```bash
openllm serve
```

Or:

```bash
python -m openllm.src.server
```

Server runs at `http://localhost:8000`

### 4. Use the API

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer openllm" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-model",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Usage

### Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="openllm"
)

# Auto-routing to best available model
response = client.chat.completions.create(
    model="meta-model",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Direct model selection
response = client.chat.completions.create(
    model="groq/llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Write a function"}]
)
```

### CLI Commands

```bash
openllm serve          # Start server
openllm status        # Show status
openllm models list   # List models
openllm score        # Show scores
openllm config       # Show config
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        OpenLLM Gateway                        │
├────────────────────────────────────���────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐      │
│  │                 API Router (/v1/*)                  │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │                Model Dispatcher                    │      │
│  │     Route Selection + Failover + Rate Control        │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │                 Scorer Engine                      │      │
│  │            Score Calculation + Ranking             │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │            Model Registry                          │      │
│  └──────────────────────┬───────────────────────────────┘      │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────────┐      │
│  │          Protocol Adapters (by Protocol Type)               │
│  │  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │  │  OpenAI  │Anthropic │   REST   │  Ollama  │          │
│  │  └──────────┴──────────┴──────────┴──────────┘          │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### models.yaml

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | required | Model identifier |
| `protocol` | string | required | Protocol type |
| `endpoint` | string | required | API endpoint |
| `api_key` | string | "" | API key (supports `${ENV_VAR}`) |
| `enabled` | bool | true | Enable model |
| `rpm` | int | 30 | Requests per minute |
| `tpm` | int | 15000 | Tokens per minute |
| `max_concurrent` | int | 10 | Max concurrent |
| `daily_limit` | int | 1000 | Daily limit |
| `cost_limit` | float | 0.0 | Cost limit (USD) |
| `max_context_length` | int | 128000 | Context length |
| `capabilities` | list | [] | Model capabilities |

### settings.json

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server.host` | string | "0.0.0.0" | Server host |
| `server.port` | int | 8000 | Server port |
| `context.mode` | string | "dynamic" | Context mode |
| `context.max_tokens` | int | 128000 | Max tokens |
| `session.affinity_enabled` | bool | true | Session affinity |
| `failover.max_retries` | int | 3 | Max retries |
| `scoring.enabled` | bool | true | Enable scoring |

## API Endpoints

### OpenAI Compatible

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /v1/chat/completions | Chat completions |
| GET | /v1/models | List models |
| GET | /v1/models/{model} | Get model info |
| GET | /v1/usage | Usage statistics |

### OpenLLM Extensions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/scores | Model scores |
| POST | /v1/scores/refresh | Refresh scores |
| GET | /health | Health check |

## Protocol Adapters

### OpenAI Protocol

Standard OpenAI `/v1/chat/completions` interface.

```yaml
- name: "model-id"
  protocol: "openai"
  endpoint: "https://api.provider.com/v1"
  api_key: "${API_KEY}"
```

### Anthropic Protocol

Claude-style `/v1/messages` interface.

```yaml
- name: "claude-3-haiku"
  protocol: "anthropic"
  endpoint: "https://api.anthropic.com"
  api_key: "${ANTHROPIC_API_KEY}"
```

### REST Protocol

Custom REST API with template support.

```yaml
- name: "custom-model"
  protocol: "rest"
  endpoint: "https://api.example.com"
  method: "POST"
  body_template: '{"prompt": "{{content}}"}'
```

### Ollama Protocol

Local Ollama models.

```yaml
- name: "ollama/llama3"
  protocol: "ollama"
  endpoint: "http://localhost:11434"
```

## Context Management

### Modes

| Mode | Description |
|------|-------------|
| `static` | Keep last N messages |
| `dynamic` | Adaptive token tracking |
| `reservoir` | Recent + extractive summary |
| `adaptive` | Auto-detect task type |

## Rate Limiting

When a model hits rate limit:
1. Check if request is within limits
2. If limited, automatically failover to next best model
3. Continue trying models until success or exhaustion
4. Return 429 if no models available

## Scoring

Models are scored based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Quality | 40% | Output quality |
| Speed | 30% | Response time |
| Context | 20% | Context length |
| Reliability | 10% | Availability |

```
TotalScore = Quality × 0.4 + Speed × 0.3 + Context × 0.2 + Reliability × 0.1
```

## Contributing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black .
```

## License

MIT License - see [LICENSE](LICENSE)