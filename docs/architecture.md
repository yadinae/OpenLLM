# Architecture

## Overview

OpenLLM is an AI model aggregation platform that provides a unified API for multiple AI model providers. It automatically routes requests, manages rate limits, and ranks models by quality.

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenLLM Gateway                       │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   API Router                         │   │
│  │              /v1/chat/completions                   │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                    Dispatcher                       │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │   │
│  │  │  Selector  │ │  Failover   │ │Rate Limiter │  │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                   Scorer Engine                     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │   │
│  │  │  Quality   │ │   Speed    │ │Reliability │  │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                  Model Registry                     │   │
│  │              models.yaml → adapters                │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │              Protocol Adapters                     │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │   │
│  │  │OpenAI  │ │Anthropic│ │  REST  │ │Ollama  │    │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘    │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │  External APIs    │
        │ (Groq, Gemini,   │
        │ Mistral, etc.)   │
        └───────────────────┘
```

## Core Components

### 1. API Router

Responsible for exposing OpenAI-compatible endpoints.

- `/v1/chat/completions` - Chat completions
- `/v1/models` - List models
- `/v1/usage` - Usage statistics
- `/v1/scores` - Model scores
- `/health` - Health check

### 2. Dispatcher

Routes requests to appropriate models and handles failover.

**Key responsibilities:**
- Model selection based on scoring
- Rate limit checking
- Request execution
- Automatic failover on errors

```python
async def dispatch(request: ChatRequest) -> ChatResponse:
    # 1. Select best model
    model = select_best_model(request)
    
    # 2. Check rate limits
    if not check_limits(model):
        # 3. Failover
        return failover(original_model, request)
    
    # 4. Execute
    return await execute(model, request)
```

### 3. Scorer Engine

Calculates and maintains model scores.

**Score factors:**
- Quality Score (40%): Output quality assessment
- Speed Score (30%): Response time
- Context Score (20%): Context length support
- Reliability Score (10%): Success rate

```python
score = (
    quality * 0.4 +
    speed * 0.3 +
    context * 0.2 +
    reliability * 0.1
)
```

### 4. Model Registry

Manages model configurations loaded from `models.yaml`.

- Loads model configurations
- Creates protocol adapters
- Maintains model state

### 5. Protocol Adapters

Abstraction layer for different API protocols.

```python
class ProtocolAdapter(ABC):
    protocol: str
    
    @abstractmethod
    async def chat_completions(self, messages, **kwargs) -> ChatResponse:
        pass
    
    @abstractmethod
    async def embeddings(self, texts, **kwargs) -> EmbeddingResponse:
        pass
    
    @abstractmethod
    async def get_model_info(self) -> ModelInfo:
        pass
```

### 6. Rate Limiter

Token bucket implementation for rate limiting.

- Per-model RPM limits
- Per-model TPM limits
- Concurrent request limits
- Daily quota tracking

### 7. Context Manager

Handles multi-turn conversation context.

**Modes:**
- `static`: Keep last N messages
- `dynamic`: Adaptive token tracking
- `reservoir`: Recent + extractive summary
- `adaptive`: Auto-detect task type

## Data Flow

### Request Flow

```
Client Request
    │
    ▼
API Router (router.py)
    │
    ▼
Dispatcher (dispatcher.py)
    │
    ├──▶ Model Selection (scorer.py)
    │
    ├──▶ Rate Check (limiter.py)
    │
    ▼
Model Registry (registry.py)
    │
    ▼
Protocol Adapter
    │
    ▼
External API
    │
    ▼
Response
```

### Scoring Flow

```
Response Received
    │
    ▼
Scorer Engine
    │
    ├──▶ Measure response time
    ├──▶ Evaluate quality
    │
    ▼
Update Scores
    │
    ▼
Rank Models
```

### Failover Flow

```
Rate Limit Error
    │
    ▼
Get Ranked Alternatives
    │
    ▼
Try Next Best Model
    │
    ▼── Success ──▶ Return Response
    │
    ▼── Failure ──▶ Continue to next
    │
    ▼
No Models Available
    │
    ▼
Return 429 Error
```

## Configuration Flow

```
models.yaml
    │
    ▼
Model Registry
    │
    ├──▶ Load configurations
    │
    ▼
Create Adapters
    │
    ▼
Ready for Requests
```

## Concurrency

```
                    ┌─────────────────┐
                    │   async main    │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│  Request   │        │  Request   │        │  Request  │
│    #1     │        │    #2     │        │    #3    │
└─────┬─────┘        └─────┬─────┘        └─────┬─────┘
      │                    │                    │
      └────────────────────┼────────────────────┘
                         ▼
                ┌─────────────────┐
                │ Semaphore      │ (max_concurrent)
                │  per model    │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Token Bucket   │ (RPM/TPM)
                └───────────────┘
```

## Extension Points

### Adding New Protocol Adapter

1. Create new adapter class:

```python
from openllm.src.adapters.base import ProtocolAdapter
from openllm.src.models import ChatResponse, EmbeddingResponse, ModelInfo

class MyProtocolAdapter(ProtocolAdapter):
    protocol = "myprotocol"
    
    async def chat_completions(self, messages, **kwargs) -> ChatResponse:
        # Implementation
        pass
    
    async def embeddings(self, texts, **kwargs) -> EmbeddingResponse:
        # Implementation
        pass
    
    async def get_model_info(self) -> ModelInfo:
        # Implementation
        pass
```

2. Register in factory:

```python
# In adapters/base.py
def create_adapter(protocol: str, config: AdapterConfig):
    if protocol == "myprotocol":
        return MyProtocolAdapter(config)
```

3. Configure in `models.yaml`:

```yaml
- name: "my-model"
  protocol: "myprotocol"
  endpoint: "https://api.example.com"
```

### Adding Custom Scoring Algorithm

```python
from openllm.src.scorer import ScorerEngine

class CustomScorer(ScorerEngine):
    async def calculate_score(self, model_name, response_time, success, **kwargs):
        # Custom scoring logic
        pass
```

## Error Handling

| Error | Code | Action |
|-------|------|--------|
| RateLimitError | 429 | Auto-failover |
| AdapterError | 500 | Log + failover |
| ConfigError | 400 | Return error |
| TimeoutError | 504 | Retry + failover |

## Performance Considerations

- Async/await for non-blocking I/O
- Connection pooling per adapter
- Semaphore for concurrency control
- Token bucket for rate limiting
- In-memory scoring (fast access)

## Security

- API keys stored in environment variables
- No secrets in configuration files
- CORS configurable
- Request validation via Pydantic