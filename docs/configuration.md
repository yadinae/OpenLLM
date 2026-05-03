# Configuration Guide

## models.yaml

Located at `config/models.yaml`. Defines all available models.

```yaml
- name: openai/gpt-4o
  protocol: openai
  endpoint: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  rpm: 500          # requests per minute
  tpm: 100000       # tokens per minute
  enabled: true
  model_type: text
  model_scale: large

- name: claude/sonnet-4
  protocol: anthropic
  endpoint: https://api.anthropic.com
  api_key: ${ANTHROPIC_API_KEY}
  rpm: 50
  tpm: 50000
  enabled: true
```

### Protocol Types

| Protocol | Description |
|----------|-------------|
| `openai` | OpenAI-compatible API |
| `anthropic` | Anthropic Messages API |
| `rest` | Generic REST API |
| `ollama` | Local Ollama instance |

## DEFAULT_CONFIG

Defined in `src/enums.py`:

```python
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
    "context": {
        "mode": "dynamic",          # static/dynamic/reservoir/adaptive
        "max_tokens": 128000,
    },
    "session": {
        "affinity_enabled": True,   # Stick to same model per session
        "cache_ttl": 3600,          # Cache TTL in seconds
        "event_tracking": True,     # Enable session event tracking
        "max_events_per_session": 200,
    },
    "failover": {
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "scoring": {
        "enabled": True,
        "update_interval": 300,     # Seconds between score updates
    },
    "sandbox": {
        "enabled": True,
        "max_output_bytes": 50000,  # Max output per execution
        "timeout_seconds": 30,      # Max execution time
    },
    "prompt_enhancement": {
        "code_thinking_auto": True,   # Auto-detect analysis tasks
        "code_thinking_language": "en",
        "terse_enabled": False,       # Default terse off
        "terse_intensity": "moderate", # mild/moderate/extreme
        "terse_language": "en",
    },
}
```

## Agent Configuration

Stored in `~/.openllm/agents.json`. Auto-created on first agent registration.

```json
{
  "agents": [
    {
      "agent_id": "nanobot",
      "name": "Nanobot Agent",
      "platform": "nanobot",
      "api_key": "sk-nanobot-xxx",
      "enabled": true,
      "default_model": "qwen3.6-plus",
      "allowed_models": [],
      "code_thinking_enabled": true,
      "terse_enabled": false,
      "terse_intensity": "moderate",
      "session_tracking_enabled": true,
      "sandbox_enabled": true,
      "quota": {
        "daily_tokens": 0,
        "daily_requests": 0,
        "rpm": 60,
        "tpm": 100000
      }
    }
  ]
}
```

**Note:** `daily_tokens: 0` and `daily_requests: 0` mean unlimited.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | For OpenAI models |
| `ANTHROPIC_API_KEY` | Anthropic API key | For Claude models |
| `GROQ_API_KEY` | Groq API key | For Groq models |
| `MISTRAL_API_KEY` | Mistral API key | For Mistral models |
| `GOOGLE_API_KEY` | Google API key | For Gemini models |

Reference in models.yaml using `${VARIABLE_NAME}`.

## Database Files

| File | Purpose | Created On |
|------|---------|------------|
| `~/.openllm/agents.json` | Agent registry & API keys | First agent registration |
| `~/.openllm/sandbox/content_index.db` | Sandbox FTS5 search index | First index call |
| `~/.openllm/sessions/session_events.db` | Session event store | First event extraction |

All databases use SQLite WAL mode for safe concurrent access.

## Admin Panel

Access at `http://host:port/admin/`. No configuration needed — served as static files from `src/admin/`.
