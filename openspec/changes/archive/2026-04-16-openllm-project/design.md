# Design: OpenLLM - AI Model Aggregation Platform

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        OpenLLM Gateway                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │                 API Router (/v1/*)                  │      │
│  │            OpenAI Compatible Endpoints                │      │
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
│  │               Model Registry                        │      │
│  │        Model Config + Protocol Mapping             │      │
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

## 2. Module Design

### 2.1 Protocol Adapters

```
ProtocolAdapter (ABC)
├── protocol: str
├── chat_completions(messages, model, **opts) -> ChatResponse
├── embeddings(texts, model) -> EmbeddingResponse
└── get_model_info(model) -> ModelInfo

OpenAIAdapter (implements OpenAI protocol)
AnthropicAdapter (implements Claude protocol)
RESTAdapter (implements custom REST)
OllamaAdapter (implements Ollama local protocol)
```

| Adapter | Protocol | Endpoint Pattern |
|---------|----------|------------------|
| OpenAIAdapter | openai | `/v1/chat/completions` |
| AnthropicAdapter | anthropic | `/v1/messages` |
| RESTAdapter | rest | `POST /predict` |
| OllamaAdapter | ollama | `/api/generate` |

### 2.2 Model Registry

```
ModelConfig (Pydantic)
├── name: str                    # e.g., "groq/llama-3.3-70b-versatile"
├── protocol: str              # 'openai' | 'anthropic' | 'rest' | 'ollama'
├── endpoint: str             # API endpoint URL
├── api_key: str               # API key (supports ${ENV_VAR})
├── enabled: bool = True      # Enable/disable
│
├─── Rate Control (per model)
│   ├── rpm: int = 30          # Requests per minute
│   ├── tpm: int = 15000       # Tokens per minute
│   ├── max_concurrent: int = 10  # Max concurrent
│   ├── daily_limit: int = 1000   # Daily request limit
│   └── cost_limit: float = 0.0   # Cost limit (USD)
│
├─── Scoring Weights
│   ├── quality_weight: float = 0.4
│   ├── speed_weight: float = 0.3
│   ├── context_weight: float = 0.2
│   └── reliability_weight: float = 0.1
│
└─── Attributes
    ├── max_context_length: int = 128000
    └── capabilities: list[str] = []  # ['vision', 'tools', etc.]
```

### 2.3 Scorer Engine

```
ModelScore (Pydantic)
├── model_name: str
├── quality_score: float       # Output quality (0-1)
├── speed_score: float         # Response speed (0-1)
├── context_score: float      # Context support (0-1)
├── reliability_score: float  # Availability (0-1)
├── total_score: float        # Weighted total
└── last_updated: datetime

ScorerEngine
├── calculate_score(model, response) -> ModelScore
├── update_rankings() -> list[ModelScore]
└── get_best_model(request) -> str

Score Formula:
  TotalScore = Quality × 0.4 + Speed × 0.3 + Context × 0.2 + Reliability × 0.1
```

### 2.4 Rate Limiter

```
RateLimiter
├── check_limit(model, request) -> bool
├── acquire(model, tokens) -> bool
├── release(model, tokens)
└── wait_if_needed(model) -> float

TokenBucket (per model)
├── capacity: int              # Max tokens
├── tokens: int               # Current tokens
├── refill_rate: float        # Tokens per second
└── last_refill: datetime
```

### 2.5 Dispatcher

```
ModelDispatcher
├── dispatch(request) -> Response
│   ├── select best model
│   ├── check rate limits
│   ├── execute request
│   ├── on rate limit -> failover
│   └── return response
│
└── failover(original_model, request) -> Response
    ├── get ranked alternatives
    ├── try each until success
    └── return response or error
```

### 2.6 Context Manager

```
ContextManager
└── prune(messages, mode, max_tokens) -> list[Message]

Modes:
- static: Keep last N messages
- dynamic: Adaptive token tracking
- reservoir: Keep recent + extractive summary
- adaptive: Auto-detect task type
```

## 3. Data Models

### 3.1 Request Models

```
ChatRequest (Pydantic)
├── model: str                 # 'meta-model' or 'provider/model'
├── messages: list[Message]
├── temperature: float = 0.7
├── max_tokens: int = 2048
├── stream: bool = False
├── session_id: str = None      # Session affinity
├── model_type: str = None      # 'text' | 'coding' | 'ocr'
└── model_scale: str = None     # 'small' | 'medium' | 'large'

Message (Pydantic)
├── role: str                  # 'system' | 'user' | 'assistant'
└── content: str
```

### 3.2 Response Models

```
ChatResponse (Pydantic)
├── id: str
├── object: str = "chat.completion"
├── created: int
├── model: str
├── choices: list[Choice]
└── usage: Usage

Choice (Pydantic)
├── index: int
├── message: Message
└── finish_reason: str

Usage (Pydantic)
├── prompt_tokens: int
├── completion_tokens: int
└── total_tokens: int
```

## 4. Configuration Files

### models.yaml

```yaml
models:
  # OpenAI protocol models
  - name: "gemini/gemini-2.5-flash"
    protocol: "openai"
    endpoint: "https://generativelanguage.googleapis.com/v1beta"
    api_key: "${GEMINI_API_KEY}"
    rpm: 15
    tpm: 1000000
    max_concurrent: 5

  - name: "groq/llama-3.3-70b-versatile"
    protocol: "openai"
    endpoint: "https://api.groq.com/openai/v1"
    api_key: "${GROQ_API_KEY}"
    rpm: 30
    tpm: 6000
    max_concurrent: 10

  - name: "mistral/mistral-large-latest"
    protocol: "openai"
    endpoint: "https://api.mistral.ai/v1"
    api_key: "${MISTRAL_API_KEY}"
    rpm: 30
    tpm: 15000

  # Anthropic protocol models
  - name: "anthropic/claude-3-haiku"
    protocol: "anthropic"
    endpoint: "https://api.anthropic.com"
    api_key: "${ANTHROPIC_API_KEY}"
    rpm: 50
    tpm: 100000

  # REST protocol models
  - name: "custom/model-1"
    protocol: "rest"
    endpoint: "https://api.example.com/v1"
    api_key: "${CUSTOM_API_KEY}"
    method: "POST"
    body_template: '{"prompt": "{{prompt}}"}'
    rpm: 60

  # Ollama local models
  - name: "ollama/llama3"
    protocol: "ollama"
    endpoint: "http://localhost:11434"
    rpm: 100
    tpm: 999999999
```

### settings.json

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

## 5. API Endpoints

### OpenAI Compatible

| Method | Endpoint | Description |
|--------|----------|------------|
| POST | /v1/chat/completions | Chat completions |
| GET | /v1/models | List models |
| GET | /v1/models/{model} | Get model info |
| GET | /v1/usage | Usage statistics |

### OpenLLM Extensions

| Method | Endpoint | Description |
|--------|----------|------------|
| GET | /v1/scores | Model scores |
| POST | /v1/scores/refresh | Refresh scores |
| GET | /health | Health check |

## 6. CLI Commands

| Command | Description |
|---------|------------|
| openllm serve | Start server |
| openllm status | Show status |
| openllm models list | List models |
| openllm models add | Add model |
| openllm models remove | Remove model |
| openllm score | Refresh scores |
| openllm config | Config management |

## 7. Rate Limit Handling Flow

```
Request Arrives
     │
     ▼
┌────��─��─────┐
│Check Rate  │──── OK ────▶ Execute Request ──▶ Return Response
│  Limits   │
│           │
└────┬─────┘
     │ Rate Limited
     ▼
┌────────────┐
│  Automatic │
│  Failover  │
└────┬─────┘
     │
     ▼
Try Next Best Model ──▶ Success ──▶ Return Response
     │
     ▼
No Available Model
     │
     ▼
Return 429 Error
```

## 8. Project Structure

```
openllm/
├── src/
│   ├── __init__.py
│   ├── server.py           # Entry point
│   ├── router.py          # API endpoints
│   ├── dispatcher.py     # Request dispatch
│   ├── scorer.py        # Scoring engine
│   ├── limiter.py       # Rate limiter
│   ├── context.py      # Context manager
│   ├── registry.py     # Model registry
│   ├── config.py      # Configuration
│   ├── models.py      # Data models
│   └── adapters/
│       ├── __init__.py
│       ├── base.py      # Base adapter
│       ├── openai.py   # OpenAI adapter
│       ├── anthropic.py # Anthropic adapter
│       ├── rest.py     # REST adapter
│       └── ollama.py  # Ollama adapter
├── cli/
│   ├── __init__.py
│   └── __main__.py    # CLI entry
├── tests/
│   ├── __init__.py
│   ├── test_adapters.py
│   ├── test_dispatcher.py
│   └── test_scorer.py
├── config/
│   ├── models.yaml
│   └── settings.json
├── pyproject.toml
├── setup.py
└── README.md
```

## 9. Acceptance Criteria

- [ ] Protocol adapters can be extended via configuration
- [ ] Models can be added via models.yaml
- [ ] Rate limits are enforced per model
- [ ] Automatic failover works on rate limit
- [ ] Model scoring updates automatically
- [ ] OpenAI-compatible API works
- [ ] CLI commands function correctly
- [ ] Unit tests pass for all modules