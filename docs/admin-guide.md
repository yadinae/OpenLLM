# Admin Panel Guide

## Access

```
http://your-server:8000/admin/
```

Note the trailing slash — `/admin` redirects to `/admin/`.

## Dashboard Tab (📊 概览)

Shows at-a-glance metrics:

- **Agent count** — Total registered agents
- **Today's requests** — Request count for current day
- **Today's tokens** — Token usage for current day
- **Available languages** — Sandbox runtime count

Charts:
- **Bar chart** — Token usage per agent
- **Doughnut chart** — Request distribution per agent
- **Activity timeline** — Recent agent activity with timestamps

## Agent Management Tab (🤖 Agent 管理)

### View Agents

Table showing all registered agents:
- Agent ID, Name, Platform
- Default model, Code Thinking, Terse settings
- Enabled/Disabled status
- API Key access

### Register New Agent

Click `+ 注册 Agent` to open the registration form:

| Field | Required | Description |
|-------|----------|-------------|
| Agent ID | ✅ | Unique identifier |
| Name | ❌ | Display name |
| Platform | ✅ | nanobot/hermes/claude-code/cursor/etc |
| API Key | ❌ | Leave empty to auto-generate |
| Default Model | ❌ | Default model for this agent |
| Code Thinking | ✅ (checked) | Enable code thinking mode |
| Terse Mode | ❌ (unchecked) | Enable terse output |

After registration, a modal shows the generated API key. **Copy it immediately** — it won't be shown again.

### Regenerate API Key

Click 🔄 next to an agent to generate a new key (invalidates the old one).

## Session Tab (💬 会话)

### Search Events

Enter a search query and press Enter to search across all agents' session events using BM25 full-text search.

### Filter by Agent

Use the dropdown to filter events for a specific agent.

## Sandbox Tab (🧪 沙盒)

### Runtime Status

Shows which languages are available in the sandbox:
- ✅ Available runtimes with green badges

### Content Index

Shows indexing statistics:
- Document count
- Chunk count
- Total indexed size
- Source count

### Quick Test

Execute code directly from the dashboard:
1. Select language (Python/JavaScript/Shell)
2. Enter code
3. Click `执行`
4. View results inline

## Model Tab (📦 模型)

### Model List

Shows all configured models with their providers.

### Model Scores

Shows ranked model scores:
- Total score (weighted combination)
- Individual factor scores

## Settings Tab (⚙️ 配置)

### API Address

Change the API base URL if the server is on a different host.

### Auto Refresh

Set automatic data refresh interval (10s / 30s / 60s / off).

### Connection Test

Click `测试连接` to verify API connectivity.

### Export Config

Download current settings as JSON.

## Architecture

The admin panel is a **single HTML file** (`src/admin/index.html`) with:
- **Tailwind CSS** via CDN for styling
- **Chart.js** via CDN for charts
- **Vanilla JavaScript** — no build step, no framework

All data is fetched from the OpenLLM REST API. No server-side rendering.
