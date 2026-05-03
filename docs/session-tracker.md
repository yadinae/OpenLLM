# Session Event Tracker

## Overview

The session event tracker automatically extracts structured events from conversation history and stores them in SQLite FTS5 for BM25 search. This enables the LLM to recall relevant past events when the context window is compressed.

Inspired by [context-mode](https://github.com/mksglu/context-mode)'s session event extraction — zero LLM cost, pure rule-based pattern matching.

## How It Works

```
Conversation Messages
    │
    ▼
EventExtractor (regex patterns, zero LLM cost)
    │
    ├── File Read/Write events
    ├── Error events
    ├── Tool call events
    ├── Git operation events
    ├── User decision events
    ├── Rule/config file events
    ├── Sub-agent events
    ├── Environment change events
    └── Intent events
    │
    ▼
SessionEventStore (SQLite FTS5)
    │
    ▼
BM25 Search → Relevant past events → Inject into system prompt
```

## Event Types

| Type | Category | Trigger Pattern | Example |
|------|----------|-----------------|---------|
| `file_read` | file | "read file X", "查看文件X" | "读取了 config.py" |
| `file_write` | file | "wrote to X", "创建文件X" | "创建了 test.py" |
| `file_edit` | file | "modified X", "修改了X" | "编辑了 main.py" |
| `error` | error | "Error:", "Traceback", "异常" | "KeyError: 'name'" |
| `tool_call` | tool | "running X", "执行命令" | "ran `git status`" |
| `git_commit` | git | "git commit" | "git commit -m 'fix'" |
| `git_push` | git | "git push" | "git push origin main" |
| `git_checkout` | git | "git checkout/branch" | "git checkout -b feature" |
| `decision` | decision | "决定", "decided to" | "决定使用方案A" |
| `rule_read` | rule | CLAUDE.md, AGENTS.md | Reading rule files |
| `env_change` | env | "set env", "export" | "export DEBUG=1" |
| `subagent` | subagent | "spawned agent", "subagent" | "spawned subagent for testing" |
| `intent` | intent | "我想", "I want to" | "I want to refactor this" |

## API Usage

### Extract Events

```bash
POST /api/session/events
{
  "messages": [
    {"role": "user", "content": "帮我修改 main.py 的数据库连接"},
    {"role": "assistant", "content": "我读取了 main.py 并修改了数据库配置"}
  ],
  "session_id": "conv-abc123"
}
```

Response:
```json
{
  "events_extracted": 2,
  "event_types": ["file_read", "file_edit"],
  "session_id": "conv-abc123"
}
```

### Search Events

```bash
GET /api/session/events?q=database+connection&session_id=conv-abc123&limit=10
```

Response:
```json
{
  "query": "database connection",
  "results": [
    {
      "event_type": "file_edit",
      "summary": "修改了 main.py 的数据库配置",
      "data": "...",
      "timestamp": "2026-05-03T10:00:00"
    }
  ],
  "count": 1
}
```

### Get Session Context

```bash
POST /api/session/context
{
  "messages": [{"role": "user", "content": "修复那个 bug"}],
  "session_id": "conv-abc123"
}
```

Returns enriched messages with relevant historical events injected.

## How Recall Works

When the user says something vague like "fix the bug" or "继续之前的工作", the tracker:

1. **Extracts keywords** from the current message
2. **BM25 searches** the session event store
3. **Returns relevant past events** (file edits, errors, decisions)
4. **Injects them** into the system prompt so the LLM knows what happened before

This is **much more accurate** than LLM-based summarization because:
- Exact event data is preserved (file paths, error messages, decisions)
- BM25 ranking finds the most relevant events
- Zero LLM cost for extraction (pure regex)

## Session Isolation

Events are scoped by agent + session:
- `nanobot:conv-123` — events for nanobot's session
- `hermes:conv-123` — events for hermes's session (completely separate)

## Integration with Prompt Enhancement

The `PromptEnhancer` automatically calls the event tracker when processing messages:

```python
enhancer = PromptEnhancer()
result = enhancer.enhance(messages, session_id="conv-123")
# Events are automatically recalled and injected into system prompt
```
