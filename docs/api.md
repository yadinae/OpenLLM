# API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

For remote access, include your agent's API key:

```
X-API-Key: sk-your-agent-key
```

Or use agent ID directly:
```
X-Agent-ID: nanobot
```

## Core Endpoints

### Chat Completion

```
POST /v1/chat/completions
```

**Request:**
```json
{
  "model": "qwen3.6-plus",
  "messages": [{"role": "user", "content": "Hello"}],
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false,
  "session_id": "conv-123",
  "agent_id": "nanobot",
  "code_thinking": true,
  "terse": true,
  "terse_intensity": "moderate"
}
```

**Response:**
```json
{
  "id": "cmpl-xxx",
  "object": "chat.completion",
  "created": 1777780101,
  "model": "qwen3.6-plus",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
  "code_thinking_enabled": true,
  "terse_enabled": true,
  "terse_intensity": "moderate"
}
```

### List Models

```
GET /v1/models
```

### Health Check

```
GET /v1/health
→ {"status": "ok", "timestamp": 1777780101}
```

### Usage Stats

```
GET /v1/usage
```

### Model Scores

```
GET /v1/scores
POST /v1/scores/refresh
```

## Agent Endpoints

### List Agents

```
GET /api/session/agents
```

### Register Agent

```
POST /api/session/agents/register
{
  "agent_id": "my-agent",
  "name": "My Agent",
  "platform": "custom",
  "api_key": "sk-custom-key",
  "default_model": "qwen3.6-plus",
  "code_thinking_enabled": true,
  "terse_enabled": true,
  "terse_intensity": "moderate"
}
```

### Generate API Key

```
POST /api/session/agents/{agent_id}/generate-key
```

### View Keys (Masked)

```
GET /api/session/agents/{agent_id}/keys
```

### Usage

```
GET /api/session/agents/{agent_id}/usage
GET /api/session/agents/usage/all
```

## Sandbox Endpoints

### Execute Code

```
POST /api/sandbox/execute
{"language": "python", "code": "print('hello')"}
```

### Batch Execution

```
POST /api/sandbox/batch
{"commands": [{"language": "python", "code": "print(1+1)", "label": "test"}]}
```

### Index Content

```
POST /api/sandbox/index
{"source": "docs/api", "content": "...", "content_type": "markdown"}
```

### Search

```
GET /api/sandbox/search?q=installation
```

### Stats

```
GET /api/sandbox/stats
GET /api/sandbox/languages
```

### Purge Index

```
DELETE /api/sandbox/purge
```

## Session Endpoints

### Extract/Search Events

```
POST /api/session/events
GET  /api/session/events?q=error&session_id=conv-123
```

### Get Context

```
GET /api/session/context?session_id=conv-123
```

### Delete Session

```
DELETE /api/session/{session_id}
```

## Admin Panel

```
GET /admin/
```

Web-based management UI. No API key required for local access.
