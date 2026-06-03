"""输入校验 — 请求体大小限制、内容安全检测"""

from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 默认限制
MAX_MESSAGES = 200          # 单次请求最大消息数
MAX_CONTENT_LENGTH = 50000   # 单条消息最大字符数
MAX_REQUEST_BODY = 2 * 1024 * 1024  # 整个请求体最大 2MB
MAX_MODEL_LENGTH = 256       # 模型名最大长度


def validate_request_body(request: Request) -> Response | None:
    """请求输入校验中间件逻辑

    在请求进入路由前执行：
    - 只校验 POST/PUT 请求
    - 跳过 health/docs 端点
    - 检查 Content-Length 和 Transfer-Encoding
    - 拒绝 chunked encoding（绕过 Content-Length 检查）

    返回 None 表示通过，返回 Response 表示拒绝。
    """
    path = request.url.path

    # 只校验 API 端点
    if request.method not in ("POST", "PUT"):
        return None
    if path in ("/health", "/docs", "/openapi.json", "/"):
        return None

    # 拒绝 chunked transfer encoding（绕过 Content-Length 限制）
    transfer_encoding = request.headers.get("transfer-encoding", "").lower()
    if "chunked" in transfer_encoding:
        return JSONResponse(
            status_code=411,
            content={
                "error": "chunked_not_allowed",
                "message": "Transfer-Encoding: chunked is not allowed. Set Content-Length instead.",
                "code": 411,
            },
        )

    # Content-Length 检查
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY:
        return JSONResponse(
            status_code=413,
            content={
                "error": "request_too_large",
                "message": f"Request body exceeds {MAX_REQUEST_BODY // 1024 // 1024}MB limit",
                "code": 413,
            },
        )

    # 不对非 JSON 请求做深入校验
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return None

    return None  # 通过


def validate_chat_messages(messages: list[dict]) -> str | None:
    """校验消息列表，返回错误信息或 None"""

    if not messages:
        return "messages is required"

    if len(messages) > MAX_MESSAGES:
        return f"Too many messages: {len(messages)} > {MAX_MESSAGES}"

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            return f"messages[{i}] must be an object"

        role = msg.get("role", "")
        if role not in ("user", "assistant", "system", "tool"):
            return f"messages[{i}]: invalid role '{role}'"

        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > MAX_CONTENT_LENGTH:
            return (
                f"messages[{i}]: content too long "
                f"({len(content)} > {MAX_CONTENT_LENGTH} chars)"
            )

    return None


def validate_model_name(model: str) -> str | None:
    """校验模型名，返回错误信息或 None"""
    if not model:
        return "model is required"
    if len(model) > MAX_MODEL_LENGTH:
        return f"model name too long ({len(model)} > {MAX_MODEL_LENGTH})"
    # 检查危险字符（防止路径遍历 / 注入）
    if ".." in model:
        return "model name must not contain '..'"
    # / 是合法的 provider/model 分隔符，但不允许空段
    if model.startswith("/") or model.endswith("/"):
        return "model name must not start or end with '/'"
    if "//" in model:
        return "model name must not contain empty segments"
    return None
