# 命令行参考

## 服务器管理

```bash
# 启动服务器（默认端口 8000）
python -m openllm.src.server

# 自定义端口
python -m openllm.src.server --port 8001

# 开发模式（热重载）
uvicorn openllm.src.server:app --host 0.0.0.0 --port 8000 --reload

# 生产环境
gunicorn openllm.src.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API 使用

### 对话完成

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "你好"}]}'
```

### 带 Agent 认证

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "X-API-Key: sk-your-key" \
  -d '{"messages": [{"role": "user", "content": "你好"}]}'
```

### 带提示增强

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

### 列出模型

```bash
curl http://localhost:8000/v1/models
```

### 健康检查

```bash
curl http://localhost:8000/v1/health
```

### 模型评分

```bash
curl http://localhost:8000/v1/scores
```

## Agent 管理

### 注册 Agent

```bash
curl http://localhost:8000/api/session/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent", "name": "我的Agent", "platform": "custom", "default_model": "qwen3.6-plus"}'
```

### 列出 Agent

```bash
curl http://localhost:8000/api/session/agents
```

### 生成 API Key

```bash
curl -X POST http://localhost:8000/api/session/agents/my-agent/generate-key
```

### 查看用量

```bash
curl http://localhost:8000/api/session/agents/my-agent/usage
curl http://localhost:8000/api/session/agents/usage/all
```

## 沙盒

### 执行代码

```bash
curl http://localhost:8000/api/sandbox/execute \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(2 + 2)"}'
```

### 批量执行

```bash
curl http://localhost:8000/api/sandbox/batch \
  -H "Content-Type: application/json" \
  -d '{"commands": [{"language": "python", "code": "print(1+1)", "label": "test"}]}'
```

### 搜索索引

```bash
curl "http://localhost:8000/api/sandbox/search?q=安装指南"
```

## 会话事件

### 提取事件

```bash
curl http://localhost:8000/api/session/events \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "读取了 main.py 并修复了 bug"}], "session_id": "conv-123"}'
```

### 搜索事件

```bash
curl "http://localhost:8000/api/session/events?q=文件错误&session_id=conv-123"
```

## 管理面板

浏览器打开：

```
http://localhost:8000/admin/
```
