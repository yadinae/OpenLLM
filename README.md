# OpenLLM — AI Model Aggregation Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

OpenLLM is a unified AI model gateway that routes requests across multiple providers, scores model quality, manages rate limits, and now includes intelligent agent management, sandbox execution, and context optimization — inspired by [context-mode](https://github.com/mksglu/context-mode).

---

## ✨ Key Features

### 🌐 Model Aggregation
- **Unified API** — Single OpenAI-compatible endpoint (`/v1/chat/completions`) across all providers
- **Auto-Routing** — Smart model selection based on quality scoring
- **Auto-Failover** — Automatic fallback when models are unavailable
- **Rate Limiting** — Per-model RPM/TPM management

### 🤖 Multi-Agent Management
- **Agent Registration** — Register AI agents (Claude Code, Cursor, nanobot, etc.) with API keys
- **Per-Agent Config** — Independent model defaults, quotas, and enhancement settings
- **Usage Tracking** — Track tokens, requests, and costs per agent
- **Isolated Sessions** — Session data scoped per agent

### 🧪 Sandbox Execution (context-mode inspired)
- **Multi-Language** — Python, JavaScript, TypeScript, Shell, Ruby, Perl, PHP
- **Output Truncation** — Prevents context window overflow (default 50KB limit)
- **Batch Execution** — Run multiple commands, get summary results
- **File Tracking** — Automatically tracks which files are read during execution
- **Security** — Isolated temp directories, cleaned up after execution

### 📋 Session Event Tracking
- **Zero-Cost Extraction** — Rule-based pattern matching (no LLM calls)
- **SQLite FTS5** — Full-text BM25 search over session events
- **13 Event Types** — File ops, errors, tool calls, git, decisions, and more
- **Context Recall** — Automatically enrich current conversation with relevant past events

### 📝 Prompt Enhancement (context-mode inspired)
- **Code Thinking Mode** — Auto-detects analysis tasks, instructs the model to "think in code" instead of reading massive data into context
- **Terse Mode** — Compresses output by 65-75% with 3 intensity levels (mild/moderate/extreme)
- **Event Enrichment** — Injects relevant historical context into system prompts

### 📊 Admin Dashboard
- **Web UI** at `/admin/` — No build step, single HTML file
- **Real-time Stats** — Agent usage, model scores, session activity
- **Agent Management** — Register agents, view/regenerate API keys
- **Sandbox Testing** — Execute code directly from the dashboard

---

## 🚀 Quick Start

### Installation

```bash
cd openllm
pip install -r requirements.txt
```

### Start Server

```bash
# Default: port 8000
python -m openllm.src.server

# Custom port
python -m openllm.src.server --port 8001

# Development with hot reload
uvicorn openllm.src.server:app --host 0.0.0.0 --port 8000 --reload
```

### Basic API Usage

```bash
# Chat completion
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [{"role": "user", "content": "Hello, world!"}]
  }'

# List available models
curl http://localhost:8000/v1/models

# Check health
curl http://localhost:8000/v1/health
```

### Open with Admin Panel

```
http://localhost:8000/admin/
```

---

## 🤖 Agent Registration

### Register a Remote Agent

```bash
curl http://localhost:8000/api/session/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-remote-agent",
    "name": "My Remote Agent",
    "platform": "custom",
    "api_key": "sk-my-secret-key",
    "default_model": "qwen3.6-plus",
    "code_thinking_enabled": true,
    "terse_enabled": true,
    "terse_intensity": "moderate"
  }'
```

### Call OpenLLM as an Agent

```bash
curl http://your-server:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-my-secret-key" \
  -d '{
    "messages": [{"role": "user", "content": "Count functions in src/"}]
  }'
```

### Pre-registered Agents

| Agent ID | Platform | Code Thinking | Terse | Default Model |
|----------|----------|---------------|-------|---------------|
| nanobot | Nanobot | ✅ | ❌ | qwen3.6-plus |
| hermes | Hermes | ✅ | ✅ moderate | qwen3.6-plus |
| claude-code | Claude Code | ✅ | ✅ moderate | claude-sonnet-4 |
| cursor | Cursor IDE | ✅ | ❌ | (none) |
| copilot | GitHub Copilot | ❌ | ✅ mild | (none) |
| gemini-cli | Gemini CLI | ✅ | ❌ | (none) |
| opencode | OpenCode | ✅ | ✅ moderate | (none) |

---

## 🧪 Sandbox API

```bash
# Execute code
curl http://localhost:8000/api/sandbox/execute \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(2 + 2)"}'

# Batch execution
curl http://localhost:8000/api/sandbox/batch \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      {"language": "python", "code": "import os; print(len(os.listdir(\".\")))", "label": "count files"},
      {"language": "shell", "code": "uname -a", "label": "system info"}
    ]
  }'

# Index content for search
curl http://localhost:8000/api/sandbox/index \
  -H "Content-Type: application/json" \
  -d '{"source": "docs/readme", "content": "Your long document here..."}'

# Search indexed content
curl "http://localhost:8000/api/sandbox/search?q=installation+guide"

# View stats
curl http://localhost:8000/api/sandbox/stats
```

---

## 📋 Session Events API

```bash
# Record events from a conversation
curl http://localhost:8000/api/session/events \
  -H "Content-Type: application/json" \
  -d '{"messages": [...], "session_id": "conv-123"}'

# Search past events
curl "http://localhost:8000/api/session/events?q=file+error&session_id=conv-123"

# Get session context
curl http://localhost:8000/api/session/context \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "fix the bug"}], "session_id": "conv-123"}'
```

---

## ⚙️ Configuration

See [docs/configuration.md](docs/configuration.md) for full configuration details.

Key config in `src/enums.py`:

```python
DEFAULT_CONFIG = {
    "server": {"host": "0.0.0.0", "port": 8000},
    "context": {"mode": "dynamic", "max_tokens": 128000},
    "session": {"affinity_enabled": True, "cache_ttl": 3600},
    "failover": {"max_retries": 3, "retry_delay": 1.0},
    "scoring": {"enabled": True, "update_interval": 300},
    "sandbox": {"enabled": True, "max_output_bytes": 50000, "timeout_seconds": 30},
    "prompt_enhancement": {
        "code_thinking_auto": True,
        "code_thinking_language": "en",
        "terse_enabled": False,
        "terse_intensity": "moderate",
        "terse_language": "en",
    },
}
```

---

## 📂 Project Structure

```
openllm/
├── src/
│   ├── server.py              # FastAPI application entry
│   ├── router.py              # /v1/* endpoints
│   ├── models.py              # Pydantic models
│   ├── enums.py               # Constants & config
│   ├── registry.py            # Model registry
│   ├── dispatcher.py          # Request dispatcher
│   ├── scorer.py              # Model scoring
│   ├── limiter.py             # Rate limiting
│   ├── context.py             # Context management
│   ├── token_optimizer.py     # Token optimization
│   ├── complexity_scorer.py   # Request complexity analysis
│   ├── compression_strategy.py # Compression strategies
│   ├── adapter_model.py       # Adapter configuration
│   ├── tester.py              # Model testing
│   ├── freeride.py            # Free-tier handling
│   ├── cache_awareness.py     # Cache optimization
│   ├── code_thinking.py       # Code thinking injection
│   ├── terse_mode.py          # Terse output mode
│   ├── prompt_enhancer.py     # Unified prompt enhancer
│   ├── session_tracker.py     # Session event tracking
│   ├── sandbox/
│   │   ├── executor.py        # Multi-language sandbox
│   │   ├── batch.py           # Batch execution
│   │   └── indexer.py         # FTS5 content indexing
│   ├── admin/
│   │   └── index.html         # Admin dashboard (static)
│   └── adapters/
│       ├── base.py            # Protocol adapter base
│       ├── openai.py          # OpenAI adapter
│       ├── anthropic.py       # Anthropic adapter
│       ├── rest.py            # Generic REST adapter
│       └── ollama.py          # Ollama adapter
├── config/
│   └── models.yaml            # Model configurations
├── docs/                      # Documentation
│   ├── README.zh.md           # Chinese documentation
│   ├── architecture.md        # System architecture
│   ├── agent-guide.md         # Agent management
│   ├── sandbox-guide.md       # Sandbox usage
│   ├── session-tracker.md     # Session events
│   ├── prompt-enhancement.md  # Prompt enhancement
│   ├── admin-guide.md         # Admin panel
│   └── deployment.md          # Deployment guide
├── tests/                     # Test suite
├── requirements.txt
└── setup.py
```

---

## 🔌 API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (OpenAI-compatible) |
| `/v1/models` | GET | List available models |
| `/v1/usage` | GET | Usage statistics |
| `/v1/scores` | GET | Model scores |
| `/v1/scores/refresh` | POST | Refresh model scores |
| `/v1/health` | GET | Health check |

### Agent Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/agents` | GET | List all agents |
| `/api/session/agents/register` | POST | Register new agent |
| `/api/session/agents/{id}/generate-key` | POST | Generate API key |
| `/api/session/agents/{id}/keys` | GET | View agent keys (masked) |
| `/api/session/agents/usage/all` | GET | All agent usage stats |

### Sandbox Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sandbox/execute` | POST | Execute code |
| `/api/sandbox/batch` | POST | Batch execution |
| `/api/sandbox/index` | POST | Index content |
| `/api/sandbox/search` | GET | Search index |
| `/api/sandbox/stats` | GET | Sandbox stats |
| `/api/sandbox/languages` | GET | Available languages |
| `/api/sandbox/purge` | DELETE | Clear index |

### Session Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/events` | POST/GET | Extract/search events |
| `/api/session/enrich` | POST | Enrich messages |
| `/api/session/context` | GET | Get session context |
| `/api/session/stats` | GET | Session stats |
| `/api/session/{id}` | DELETE | Delete session |
| `/api/session/enhance/test` | POST | Test prompt enhancement |

---

## 📖 Documentation

| Guide | Description |
|-------|-------------|
| [Architecture](architecture.md) | System design and components |
| [Configuration](configuration.md) | Configuration reference |
| [API Reference](api.md) | Full API documentation |
| [Agent Guide](agent-guide.md) | Multi-agent management |
| [Sandbox Guide](sandbox-guide.md) | Sandbox execution |
| [Session Tracker](session-tracker.md) | Event tracking |
| [Prompt Enhancement](prompt-enhancement.md) | Code thinking & terse mode |
| [Admin Panel](admin-guide.md) | Web dashboard |
| [Deployment](deployment.md) | Deployment guide |
| [Compression Guide](compression-guide.md) | Token optimization |
| [CLI Reference](cli.md) | Command-line tools |

---

## License

MIT
