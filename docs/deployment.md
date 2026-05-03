# Deployment Guide

## Local Development

```bash
cd openllm
pip install -r requirements.txt

# Direct run
python -m openllm.src.server

# With uvicorn
uvicorn openllm.src.server:app --host 0.0.0.0 --port 8000 --reload
```

## Production Deployment

### Option 1: Uvicorn with Workers

```bash
pip install uvicorn[standard] gunicorn

gunicorn openllm.src.server:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile -
```

### Option 2: Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "openllm.src.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t openllm .
docker run -p 8000:8000 -v $(pwd)/config:/app/config openllm
```

### Option 3: Systemd Service

```ini
# /etc/systemd/system/openllm.service
[Unit]
Description=OpenLLM Gateway
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/projects/openllm
ExecStart=/home/admin/.local/bin/python3.11 -m uvicorn openllm.src.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable openllm
sudo systemctl start openllm
```

## Configuration

### Model Configuration

Edit `config/models.yaml` to add/remove models:

```yaml
- name: openai/gpt-4o
  protocol: openai
  endpoint: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  rpm: 500
  tpm: 100000

- name: claude/sonnet-4
  protocol: anthropic
  endpoint: https://api.anthropic.com
  api_key: ${ANTHROPIC_API_KEY}
  rpm: 50
  tpm: 50000
```

### Agent Configuration

Agents can be registered via API or by editing `~/.openllm/agents.json`:

```json
{
  "agents": [
    {
      "agent_id": "nanobot",
      "name": "Nanobot Agent",
      "platform": "nanobot",
      "api_key": "sk-nanobot-xxx",
      "default_model": "qwen3.6-plus",
      "code_thinking_enabled": true,
      "terse_enabled": false
    }
  ]
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GROQ_API_KEY` | Groq API key |
| `MISTRAL_API_KEY` | Mistral API key |
| `GOOGLE_API_KEY` | Google/Gemini API key |

### Database Files

OpenLLM creates these files automatically:

| File | Purpose |
|------|---------|
| `~/.openllm/agents.json` | Agent registry & API keys |
| `~/.openllm/sandbox/content_index.db` | Sandbox content search index |
| `~/.openllm/sessions/session_events.db` | Session event store |

## Security

### Firewall

Only expose necessary ports:

```bash
sudo ufw allow 8000/tcp  # OpenLLM
```

### API Key Security

- API keys are stored in `~/.openllm/agents.json` with file permissions `600`
- Keys are never returned in full via API (masked display only)
- Regenerating a key immediately invalidates the old one

### HTTPS

For production, use a reverse proxy:

```nginx
# /etc/nginx/sites-available/openllm
server {
    listen 443 ssl;
    server_name openllm.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/openllm.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/openllm.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/v1/health
# → {"status": "ok", "timestamp": 1777780101}
```

### Logs

```bash
# Stdout logs (uvicorn)
journalctl -u openllm -f

# Application logs (configurable via logging.basicConfig)
```

### Admin Panel

Access the admin panel for real-time monitoring:
```
https://openllm.yourdomain.com/admin/
```
