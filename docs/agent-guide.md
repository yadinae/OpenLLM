# Agent Management Guide

## Overview

OpenLLM supports multiple AI agents connecting to the same gateway, each with independent configuration, API keys, quotas, and usage tracking.

## Identification Methods

Agents are identified in priority order:

1. **`X-API-Key` header** — Look up registered agent by API key
2. **`X-Agent-ID` header** — Direct agent ID
3. **Request body `agent_id`** — Fallback for non-HTTP clients
4. **Default agent** — Falls back to `default` if none provided

## Registering Agents

### Via API

```bash
POST /api/session/agents/register
Content-Type: application/json

{
  "agent_id": "my-agent",
  "name": "My Custom Agent",
  "platform": "custom",
  "api_key": "sk-my-secret-key",
  "default_model": "qwen3.6-plus",
  "allowed_models": ["qwen3.6-plus", "openai/gpt-4o"],
  "code_thinking_enabled": true,
  "terse_enabled": true,
  "terse_intensity": "moderate",
  "quota": {
    "daily_tokens": 1000000,
    "daily_requests": 5000,
    "rpm": 60,
    "tpm": 100000
  }
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Unique identifier (lowercase, hyphens allowed) |
| `name` | string | Display name |

### Optional Fields

| Field | Default | Description |
|-------|---------|-------------|
| `platform` | `"unknown"` | Platform type |
| `api_key` | auto-generated | API key for authentication |
| `default_model` | `""` | Default model when none specified |
| `allowed_models` | `[]` (all) | Whitelist of allowed models |
| `code_thinking_enabled` | `true` | Enable code thinking mode |
| `terse_enabled` | `false` | Enable terse output |
| `terse_intensity` | `"moderate"` | Terse intensity: mild/moderate/extreme |

## Using Agents

### Via API Key (Recommended for Remote)

```bash
curl http://your-server:8000/v1/chat/completions \
  -H "X-API-Key: sk-my-secret-key" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

### Via Agent ID Header

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "X-Agent-ID: nanobot" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

### Via Request Body

```bash
curl http://localhost:8000/v1/chat/completions \
  -d '{
    "agent_id": "hermes",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Managing Keys

### Generate New Key

```bash
POST /api/session/agents/{agent_id}/generate-key
```

Returns the new API key (the old one is invalidated).

### View Key (Masked)

```bash
GET /api/session/agents/{agent_id}/keys
```

Returns a masked view (e.g., `sk-hermes-***...abc1`).

## Pre-registered Agents

| Agent ID | Platform | Code Thinking | Terse | Default Model |
|----------|----------|---------------|-------|---------------|
| `nanobot` | Nanobot | ✅ | ❌ | qwen3.6-plus |
| `hermes` | Hermes | ✅ | ✅ moderate | qwen3.6-plus |
| `claude-code` | Claude Code | ✅ | ✅ moderate | claude-sonnet-4 |
| `cursor` | Cursor IDE | ✅ | ❌ | (none) |
| `copilot` | GitHub Copilot | ❌ | ✅ mild | (none) |
| `gemini-cli` | Gemini CLI | ✅ | ❌ | (none) |
| `opencode` | OpenCode | ✅ | ✅ moderate | (none) |

## Session Isolation

Each agent's sessions are automatically scoped:

```
Agent: nanobot, session: conv-123 → stored as "nanobot:conv-123"
Agent: hermes, session: conv-123 → stored as "hermes:conv-123"
```

This means agents never see each other's session events or history.

## Usage Tracking

```bash
# Single agent
GET /api/session/agents/{agent_id}/usage

# All agents
GET /api/session/agents/usage/all
```

Response:
```json
{
  "agent_id": "nanobot",
  "today_tokens": 15234,
  "today_requests": 42,
  "total_tokens": 892001,
  "total_requests": 1523,
  "last_request_at": "2026-05-03T09:15:00"
}
```

## Quota Enforcement

When an agent hits its quota, requests are rejected with `429 Too Many Requests`:

```json
{"error": "Daily token limit exceeded (1000000)"}
```

Set quotas during registration or update via `~/.openllm/agents.json`.
