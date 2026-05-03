"""
Agent Middleware — 从请求头识别 Agent 并注入配置

FastAPI middleware，在请求处理前：
1. 从 X-API-Key / X-Agent-ID 头识别 Agent
2. 将 agent_id 注入请求上下文
3. 按 Agent 应用默认配置（模型、提示增强、限流）

安全模式：
- 不提供 API Key → 降级到 default Agent
- 提供无效 API Key → 401 Unauthorized
- 提供有效 API Key → 识别对应 Agent
"""

import logging
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.agent_registry import AgentRegistry, get_registry, AgentConfig

logger = logging.getLogger(__name__)


class AgentIdentificationMiddleware(BaseHTTPMiddleware):
    """Agent 识别中间件

    从请求头识别 Agent，将 agent_id 存入 request.state
    """

    def __init__(self, app, registry: Optional[AgentRegistry] = None, strict: bool = False):
        super().__init__(app)
        self.registry = registry or get_registry()
        self.strict = strict  # 严格模式：无效 API Key 直接拒绝

    async def dispatch(self, request: Request, call_next):
        # 只处理 API 端点
        path = request.url.path
        if not path.startswith("/v1/") and not path.startswith("/api/"):
            return await call_next(request)

        # 识别 Agent
        headers = dict(request.headers)
        agent = self.registry.identify_from_request(headers, require_auth=self.strict)

        # API Key 提供了但无效 → 拒绝
        if agent is None:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid API Key", "detail": "The provided API Key is not registered"},
            )

        # 存入 request state
        request.state.agent_id = agent.agent_id
        request.state.agent_config = agent

        # 检查 Agent 是否启用
        if not agent.enabled:
            return JSONResponse(
                status_code=403,
                content={"error": f"Agent '{agent.agent_id}' is disabled"},
            )

        # 处理请求
        response = await call_next(request)

        # 注入 Agent ID 到响应头
        response.headers["X-Agent-ID"] = agent.agent_id

        return response


def get_agent_from_request(request: Request) -> AgentConfig:
    """从请求中获取 Agent 配置"""
    return getattr(request.state, "agent_config", None) or get_registry().get_or_default("default")


def get_agent_id_from_request(request: Request) -> str:
    """从请求中获取 Agent ID"""
    return getattr(request.state, "agent_id", None) or "default"
