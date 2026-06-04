# Changelog

## v0.2.0 (2026-06-04)

### 🆕 New Features

- **模型优选系统** — 自动对 Provider 模型运行基准测试，按速度/质量/成本三维评分并智能推荐
  - `openllm rank` — 运行基准测试（速度 3 次取平均 + 质量评估）
  - `openllm recommend` — 按偏好推荐最优模型
  - `GET /v1/models/rankings` — API 查询排名
  - `GET /v1/models/recommend` — API 推荐端点
  - 结果持久化到 `~/.openllm/rankings.json`

- **健壮性增强 — 进程级保护**
  - systemd user service — 进程崩溃 5 秒自动重启，60s 防 crash loop
  - Docker Compose — `restart: unless-stopped` + healthcheck + 内存 512M 限制
  - 启动自检 — 启动前验证 YAML 结构、API key 完整性、Combo Provider 引用

### 🔧 Improvements

- `openllm serve` 新增启动自检，配置错误提前报出
- `openllm.yaml` 配置检查更严格（YAML 解析、API key 缺失、Combo 引用）
- 架构图新增模型优选组件

### 📦 Deployment

- `Dockerfile` — 多阶段构建，python:3.11-slim，HEALTHCHECK，nobody 用户运行
- `docker-compose.yml` — 一键部署，volume 持久化，内存限制
- `~/.config/systemd/user/openllm-gateway.service` — user-level systemd 守护

## v0.1.0 (2026-06-03)

- Initial release
- Protocol translation: Anthropic Messages API ↔ OpenAI Chat Completions
- Combo routing: Fallback / Round-Robin / Priority
- Circuit Breaker: CLOSED→OPEN→HALF_OPEN state machine with LRU eviction
- Exponential backoff retry with httpx error recognition
- RTK tool output compression (git diff / grep / tree / log / JSON)
- 4 context management strategies (Static / Dynamic / Reservoir / Adaptive)
- Input validation: message count, content length, role whitelist
- Optional Bearer Token authentication
- Provider health check background task
- CLI: serve / list-providers / doctor / bind
- 139 tests, ruff zero errors
