# CLI Reference

## Server Management

```bash
# Start server (default port 8000)
python -m openllm.src.server

# Custom port
python -m openllm.src.server --port 8001

# With uvicorn (development)
uvicorn openllm.src.server:app --host 0.0.0.0 --port 8000 --reload

# Production with gunicorn
gunicorn openllm.src.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Usage

### Chat Completion

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### With Agent Authentication

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "X-API-Key: sk-your-key" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

### With Prompt Enhancement

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [{"role": "user", "content": "统计所有 Python 文件的函数数量"}],
    "code_thinking": true,
    "terse": true,
    "terse_intensity": "moderate"
  }'
```

### List Models

```bash
curl http://localhost:8000/v1/models
```

### Health Check

```bash
curl http://localhost:8000/v1/health
```

### Model Scores

```bash
curl http://localhost:8000/v1/scores
```

## Agent Management

### Register Agent

```bash
curl http://localhost:8000/api/session/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "name": "My Agent",
    "platform": "custom",
    "default_model": "qwen3.6-plus"
  }'
```

### List Agents

```bash
curl http://localhost:8000/api/session/agents
```

### Generate API Key

```bash
curl -X POST http://localhost:8000/api/session/agents/my-agent/generate-key
```

### View Usage

```bash
curl http://localhost:8000/api/session/agents/my-agent/usage
curl http://localhost:8000/api/session/agents/usage/all
```

## Sandbox

### Execute Code

```bash
curl http://localhost:8000/api/sandbox/execute \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(2 + 2)"}'
```

### Batch Execution

```bash
curl http://localhost:8000/api/sandbox/batch \
  -H "Content-Type: application/json" \
  -d '{
    "commands": [
      {"language": "python", "code": "print(len(__import__(\"os\").listdir(\".\")))", "label": "count files"}
    ]
  }'
```

### Search Index

```bash
curl "http://localhost:8000/api/sandbox/search?q=installation+guide"
```

## Session Events

### Extract Events

```bash
curl http://localhost:8000/api/session/events \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "读取了 main.py 并修复了 bug"}],
    "session_id": "conv-123"
  }'
```

### Search Events

```bash
curl "http://localhost:8000/api/session/events?q=file+error&session_id=conv-123"
```

## Admin Panel

Open in browser:

```
http://localhost:8000/admin/
```
