# API 参考

## 基础 URL

```
http://localhost:8000
```

## 认证

远程访问时，在请求头中包含 Agent 的 API Key：

```
X-API-Key: sk-your-agent-key
```

或直接用 Agent ID：
```
X-Agent-ID: nanobot
```

## 核心端点

### 对话完成

```
POST /v1/chat/completions
```

**请求：**
```json
{
  "model": "qwen3.6-plus",
  "messages": [{"role": "user", "content": "你好"}],
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

### 列出模型

```
GET /v1/models
```

### 健康检查

```
GET /v1/health
→ {"status": "ok", "timestamp": 1777780101}
```

### 使用统计

```
GET /v1/usage
```

### 模型评分

```
GET /v1/scores
POST /v1/scores/refresh
```

## Agent 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/session/agents` | GET | 列出所有 Agent |
| `/api/session/agents/register` | POST | 注册新 Agent |
| `/api/session/agents/{id}/generate-key` | POST | 生成 API Key |
| `/api/session/agents/{id}/keys` | GET | 查看 Agent Key（脱敏） |
| `/api/session/agents/usage/all` | GET | 所有 Agent 用量 |

## 沙盒端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/sandbox/execute` | POST | 执行代码 |
| `/api/sandbox/batch` | POST | 批量执行 |
| `/api/sandbox/index` | POST | 索引内容 |
| `/api/sandbox/search` | GET | 搜索索引 |
| `/api/sandbox/stats` | GET | 统计信息 |
| `/api/sandbox/languages` | GET | 可用语言 |
| `/api/sandbox/purge` | DELETE | 清除索引 |

## 会话端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/session/events` | POST/GET | 提取/搜索事件 |
| `/api/session/enrich` | POST | 用历史事件增强消息 |
| `/api/session/context` | GET | 获取会话上下文 |
| `/api/session/stats` | GET | 会话统计 |
| `/api/session/{id}` | DELETE | 删除会话 |
| `/api/session/enhance/test` | POST | 测试提示增强 |
| `/api/session/agents` | GET | 列出 Agent |
| `/api/session/agents/register` | POST | 注册 Agent |
| `/api/session/agents/{id}/usage` | GET | Agent 用量 |

## 管理面板

```
GET /admin/
```

基于 Web 的管理界面，无需构建步骤。
