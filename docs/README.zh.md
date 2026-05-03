# OpenLLM — AI 模型聚合平台

OpenLLM 是一个统一的 AI 模型网关，支持多模型路由、智能评分、限流管理，以及 Agent 管理、沙盒执行和上下文优化。

## ✨ 核心功能

### 🌐 模型聚合
- **统一 API** — 兼容 OpenAI 接口的 `/v1/chat/completions`
- **智能路由** — 基于评分的自动模型选择
- **自动故障转移** — 模型不可用时自动切换
- **速率限制** — 每个模型的 RPM/TPM 管理

### 🤖 多 Agent 管理
- **Agent 注册** — 通过 API Key 识别不同 Agent
- **独立配置** — 每个 Agent 有独立的默认模型、限流、提示增强配置
- **用量追踪** — 按 Agent 统计 Token 和请求数
- **会话隔离** — 各 Agent 的会话数据完全隔离

### 🧪 沙盒执行
- **多语言支持** — Python、JavaScript、TypeScript、Shell、Ruby、Perl、PHP
- **输出截断** — 防止大输出淹没上下文窗口
- **批量执行** — 一次运行多个命令，只返回摘要
- **文件追踪** — 自动记录代码读取了哪些文件

### 📋 会话事件追踪
- **零成本提取** — 纯正则匹配，无需 LLM 调用
- **SQLite FTS5** — BM25 全文搜索
- **13 种事件类型** — 文件操作、错误、工具调用、Git 操作、用户决策等
- **上下文召回** — 对话压缩后仍能找回关键历史信息

### 📝 提示增强
- **代码思维** — 自动检测分析任务，引导模型用代码分析而非直接读取大量数据
- **简洁模式** — 输出压缩 65-75%，3 档强度可调
- **事件注入** — 自动将相关历史事件注入系统提示

### 📊 管理面板
- **Web 界面** — 访问 `/admin/` 即可使用
- **实时监控** — Agent 用量、模型评分、会话活动
- **Agent 管理** — 注册 Agent、查看/重新生成 API Key

## 🚀 快速开始

```bash
cd openllm
pip install -r requirements.txt
python -m openllm.src.server

# 访问管理面板
# http://localhost:8000/admin/
```

## 📖 文档

| 文档 | 说明 |
|------|------|
| [系统架构](architecture.md) | 系统设计和组件 |
| [配置指南](configuration.md) | 配置说明 |
| [API 参考](api.md) | 完整 API 文档 |
| [Agent 管理](agent-guide.md) | 多 Agent 管理 |
| [沙盒指南](sandbox-guide.md) | 沙盒执行 |
| [会话追踪](session-tracker.md) | 事件追踪教程 |
| [提示增强](prompt-enhancement.md) | 代码思维与简洁模式 |
| [管理面板](admin-guide.md) | Web 仪表板使用 |
| [部署指南](deployment.md) | 部署指南 |

## 🔌 使用示例

### 注册 Agent

```bash
curl http://localhost:8000/api/session/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent", "name": "My Agent", "platform": "custom"}'
```

### 调用 API

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "X-API-Key: sk-your-key" \
  -d '{"messages": [{"role": "user", "content": "你好"}]}'
```

### 沙盒执行

```bash
curl http://localhost:8000/api/sandbox/execute \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(2 + 2)"}'
```
