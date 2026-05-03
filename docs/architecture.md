# OpenLLM Architecture

## System Overview

OpenLLM is a unified AI model gateway that routes requests across multiple providers, scores model quality, manages rate limits, and provides intelligent agent management, sandbox execution, context optimization, and session event tracking.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OpenLLM Gateway                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Agent Identification Middleware                  │   │
│  │   X-API-Key → Agent Config + Quota Check + Session Prefix    │   │
│  └──────────────────────┬──────────────────────────────────────┘   │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐  │
│  │                    API Router                                │  │
│  │         /v1/chat/completions  /v1/models  /v1/scores        │  │
│  │         /api/sandbox/*        /api/session/*   /admin/*     │  │
│  └──────────────────────┬──────────────────────────────────────┘  │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐  │
│  │                  Prompt Enhancer                             │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │  │
│  │  │ Code Thinking │ │  Terse Mode  │ │  Session Event       │ │  │
│  │  │  Injection    │ │  (3 levels)  │ │  Recall (BM25)       │ │  │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │  │
│  └──────────────────────┬──────────────────────────────────────┘  │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐  │
│  │                  Complexity Scorer                           │  │
│  └──────────────────────┬──────────────────────────────────────┘  │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐  │
│  │                   Token Optimizer                            │  │
│  └──────────────────────┬──────────────────────────────────────┘  │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐  │
│  │                    Dispatcher                                │  │
│  │  ┌────────────┐ ┌───────────┐ ┌────────────┐               │  │
│  │  │  Selector  │ │ Failover  │ │Rate Limiter│               │  │
│  │  └────────────┘ └───────────┘ └────────────┘               │  │
│  └──────────────────────┬──────────────────────────────────────┘  │
│                         │                                          │
│  ┌──────────────────────▼──────────────────────────────────────┐  │
│  │                  Model Registry                              │  │
│  │              models.yaml → Protocol Adapters                 │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │   Sandbox    │ │   Sessions   │ │   Admin UI   │               │
│  │  /api/       │ │  /api/       │ │  /admin/     │               │
│  │  sandbox/    │ │  session/    │ │  (static)    │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                    │              │              │
                    ▼              ▼              ▼
              External APIs   SQLite DBs    Web Browser
            (OpenAI, Anthropic,             (Tailwind CSS
             Groq, Mistral,                  + Chart.js)
             Gemini, Ollama)
```

## Core Components

### 1. Agent Identification Middleware (`src/agent_middleware.py`)

Identifies which AI agent is making the request and applies per-agent configuration.

**Identification priority:**
1. `X-API-Key` header → lookup registered agent
2. `X-Agent-ID` header → direct agent ID
3. Request body `agent_id` field → fallback
4. Default agent if none provided

**Per-agent configuration:**
- Default model selection
- Allowed models whitelist
- Code thinking toggle
- Terse mode toggle + intensity
- Quota limits (daily tokens, daily requests, RPM, TPM)
- Session tracking toggle
- Sandbox access toggle

### 2. Agent Registry (`src/agent_registry.py`)

Manages agent registration, API keys, and usage tracking.

- Pre-registered agents: nanobot, hermes, claude-code, cursor, copilot, gemini-cli, opencode
- API key generation (`sk-{agent_id}-{random}`)
- Usage tracking (daily + lifetime tokens/requests)
- Quota enforcement
- Session ID scoping (`{agent_id}:{session_id}`)
- Persistent storage: `~/.openllm/agents.json`

### 3. API Router (`src/router.py`)

OpenAI-compatible endpoints:
- `/v1/chat/completions` — Chat completions
- `/v1/models` — List available models
- `/v1/usage` — Usage statistics
- `/v1/scores` — Model scores
- `/v1/scores/refresh` — Refresh scores
- `/v1/health` — Health check

### 4. Prompt Enhancer (`src/prompt_enhancer.py`)

Intelligent system prompt injection before sending to models:

- **Code Thinking** — Detects analysis tasks, injects "think in code" instructions. Reduces context usage 50-90% by having the model write analysis scripts instead of reading raw data into context.
- **Terse Mode** — Compresses LLM output 65-75%. Three intensity levels (mild/moderate/extreme). Auto-expands for safety warnings.
- **Event Enrichment** — Recalls relevant session events via BM25 search and injects into system prompt.

### 5. Code Thinking (`src/code_thinking.py`)

Auto-detects tasks that should use code analysis:
- Keyword-based trigger detection (English + Chinese)
- Injects structured instructions into system prompt
- Guides model to use sandbox for data processing

### 6. Terse Mode (`src/terse_mode.py`)

Output compression with configurable intensity:
- Removes filler words, pleasantries, hedging
- Preserves technical accuracy
- Three levels: mild (~30-40%), moderate (~50-65%), extreme (~65-75%)
- Safety overrides for security warnings and destructive operations

### 7. Dispatcher (`src/dispatcher.py`)

Routes requests to appropriate models:
- Model selection based on scoring
- Rate limit checking
- Request execution with async/await
- Automatic failover on errors

### 8. Scorer Engine (`src/scorer.py`)

Calculates model quality scores:
- Quality Score (40%): Output quality assessment
- Speed Score (30%): Response time
- Context Score (20%): Context length support
- Reliability Score (10%): Success rate

### 9. Model Registry (`src/registry.py`)

Manages model configurations from `config/models.yaml`:
- Loads model definitions
- Creates protocol adapters
- Maintains model state

### 10. Protocol Adapters (`src/adapters/`)

Abstraction layer for different API protocols:
- OpenAI adapter
- Anthropic adapter
- Generic REST adapter
- Ollama adapter

### 11. Rate Limiter (`src/limiter.py`)

Token bucket implementation:
- Per-model RPM (requests per minute)
- Per-model TPM (tokens per minute)
- Concurrent request limits
- Daily quota tracking

### 12. Context Manager (`src/context.py`)

Multi-turn conversation context:
- Session management
- Context mode (static/dynamic/reservoir/adaptive)
- History summarization
- Cache awareness

### 13. Token Optimizer (`src/token_optimizer.py`)

Token-level optimization:
- Compression strategies
- Context window management
- Token counting

### 14. Complexity Scorer (`src/complexity_scorer.py`)

Analyzes request complexity for routing:
- Code complexity detection
- Task type classification
- Model recommendation

### 15. Sandbox System (`src/sandbox/`)

Isolated multi-language code execution (inspired by context-mode):

#### `executor.py` — SandboxExecutor
- Single code execution with isolation
- Output truncation (default 50KB)
- Timeout control (default 30s)
- Safe environment (minimal env vars)
- Auto-cleanup of temp directories

#### `batch.py` — BatchExecutor
- Sequential multi-command execution
- File read tracking (Python injection)
- Summary-only output for context saving

#### `indexer.py` — ContentIndexer
- SQLite FTS5 full-text search
- Markdown chunking by headings
- BM25 ranking
- Content deduplication via hash

**Supported languages:** Python, JavaScript, TypeScript, Shell, Ruby, Perl, PHP

### 16. Session Event Tracker (`src/session_tracker.py`)

Structured session event tracking:

#### `EventExtractor` — Rule-based extraction (zero LLM cost)
Extracts 13 event types from conversation messages:
- `file_read`, `file_write`, `file_edit`
- `error` — Tracebacks, exceptions, error messages
- `tool_call` — Shell commands, tool invocations
- `git_commit`, `git_push`, `git_checkout`
- `decision` — User decisions and choices
- `rule_read` — Rule file access (CLAUDE.md, etc.)
- `env_change`, `subagent`, `intent`

#### `SessionEventStore` — SQLite FTS5 storage
- Full-text indexed events
- Per-agent session isolation
- BM25 search with filters

#### `SessionEventTracker` — Coordinator
- Process messages → extract events → store
- Search events → recall relevant history
- Enrich messages with recalled events

### 17. Admin UI (`src/admin/index.html`)

Single-file web dashboard (no build step):
- Tailwind CSS + Chart.js via CDN
- Vanilla JavaScript
- Tabs: Dashboard, Agents, Sessions, Sandbox, Models, Settings
- Real-time stats via REST API polling

## Data Flow

### Chat Completion Flow (with Agent Management)

```
Client Request (X-API-Key: sk-xxx)
    │
    ▼
Agent Identification Middleware
    ├── Identify agent by API key
    ├── Apply agent config (model, enhancement, limits)
    ├── Scope session_id with agent prefix
    └── Check quota
    │
    ▼
Prompt Enhancer
    ├── Code thinking injection (auto-detect or forced)
    ├── Terse mode injection (per agent config)
    └── Event enrichment (BM25 recall from session store)
    │
    ▼
Complexity Scorer
    └── Analyze request complexity
    │
    ▼
Token Optimizer
    └── Optimize token usage
    │
    ▼
Dispatcher
    ├── Select best model
    ├── Check rate limits
    ├── Execute request
    └── Failover on error
    │
    ▼
Model Response
    │
    ▼
Record agent usage + quota update
    │
    ▼
Response to client
```

### Session Event Flow

```
Messages (request/response)
    │
    ▼
EventExtractor (regex patterns)
    ├── File operations
    ├── Errors
    ├── Tool calls
    ├── Git operations
    ├── User decisions
    └── ...
    │
    ▼
SessionEventStore (SQLite FTS5)
    │
    ▼
BM25 Search (on recall)
    │
    ▼
Inject into system prompt
```

### Sandbox Flow

```
execute / batch request
    │
    ▼
SandboxExecutor
    ├── Create temp directory
    ├── Write script file
    ├── Execute with timeout
    ├── Capture output (truncated)
    └── Cleanup temp dir
    │
    ▼
Return: stdout, stderr, exit_code, duration
```

## Configuration

### models.yaml

Model definitions with protocol, endpoint, API key, rate limits:

```yaml
- name: openai/gpt-4o
  protocol: openai
  endpoint: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  rpm: 500
  tpm: 100000
```

### DEFAULT_CONFIG (src/enums.py)

```python
{
    "server": {"host": "0.0.0.0", "port": 8000},
    "context": {"mode": "dynamic", "max_tokens": 128000},
    "session": {"affinity_enabled": True, "cache_ttl": 3600},
    "failover": {"max_retries": 3, "retry_delay": 1.0},
    "scoring": {"enabled": True, "update_interval": 300},
    "sandbox": {
        "enabled": True,
        "max_output_bytes": 50000,
        "timeout_seconds": 30,
    },
    "prompt_enhancement": {
        "code_thinking_auto": True,
        "code_thinking_language": "en",
        "terse_enabled": False,
        "terse_intensity": "moderate",
        "terse_language": "en",
    },
}
```

### agents.json (~/.openllm/agents.json)

Agent registry with API keys, quotas, and preferences.

## File Structure

```
openllm/
├── src/
│   ├── server.py                 # FastAPI app entry
│   ├── router.py                 # /v1/* endpoints
│   ├── models.py                 # Pydantic models
│   ├── enums.py                  # Constants & config
│   ├── registry.py               # Model registry
│   ├── dispatcher.py             # Request dispatcher
│   ├── scorer.py                 # Model scoring
│   ├── limiter.py                # Rate limiting
│   ├── context.py                # Context management
│   ├── token_optimizer.py        # Token optimization
│   ├── complexity_scorer.py      # Complexity analysis
│   ├── compression_strategy.py   # Compression strategies
│   ├── adapter_model.py          # Adapter config model
│   ├── tester.py                 # Model testing
│   ├── freeride.py               # Free-tier handling
│   ├── cache_awareness.py        # Cache optimization
│   ├── agent_registry.py         # Agent management
│   ├── agent_middleware.py       # Agent identification middleware
│   ├── prompt_enhancer.py        # Unified prompt enhancer
│   ├── code_thinking.py          # Code thinking injection
│   ├── terse_mode.py             # Terse output mode
│   ├── session_tracker.py        # Session event tracking
│   ├── session_router.py         # Session/agent API endpoints
│   ├── admin/
│   │   └── index.html            # Admin dashboard
│   ├── sandbox/
│   │   ├── executor.py           # Code execution sandbox
│   │   ├── batch.py              # Batch execution
│   │   └── indexer.py            # FTS5 content indexing
│   └── adapters/
│       ├── base.py               # Protocol adapter base
│       ├── openai.py             # OpenAI adapter
│       ├── anthropic.py          # Anthropic adapter
│       ├── rest.py               # Generic REST adapter
│       └── ollama.py             # Ollama adapter
├── config/
│   └── models.yaml               # Model configurations
├── docs/                         # Documentation
│   ├── README.zh.md              # Chinese README
│   ├── architecture.md           # This file
│   ├── agent-guide.md            # Agent management
│   ├── sandbox-guide.md          # Sandbox usage
│   ├── session-tracker.md        # Event tracking
│   ├── prompt-enhancement.md     # Prompt enhancement
│   ├── admin-guide.md            # Admin panel
│   ├── deployment.md             # Deployment
│   └── ...
├── tests/
├── requirements.txt
└── setup.py
```

## Error Handling

| Error | Code | Action |
|-------|------|--------|
| RateLimitError | 429 | Auto-failover |
| AdapterError | 500 | Log + failover |
| ConfigError | 400 | Return error |
| TimeoutError | 504 | Retry + failover |
| Invalid API Key | 401 | Reject |
| Agent Disabled | 403 | Reject |

## Performance

- Async/await for non-blocking I/O
- Connection pooling per adapter
- Semaphore-based concurrency control
- Token bucket rate limiting
- SQLite WAL mode for concurrent reads
- Admin UI: zero server-side processing (static HTML)
