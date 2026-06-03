"""Anthropic Messages API 兼容端点 — 协议翻译入口

让 Claude Code 等工具可直接使用 OpenAI 兼容的 Provider，
OpenLLM 自动完成格式翻译。
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from openllm.server.app import registry, cooldown
from openllm.core.types import ChatRequest as InternalRequest, ChatMessage
from openllm.translate.anthropic_translate import AnthropicToOpenAI
from openllm.server.validation import validate_chat_messages, validate_model_name

logger = logging.getLogger(__name__)
router = APIRouter()

_translator = AnthropicToOpenAI()


class AnthropicMessage(BaseModel):
    role: str
    content: str | list[dict]


class AnthropicRequest(BaseModel):
    model: str
    messages: list[AnthropicMessage]
    system: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    stream: bool = False


@router.post("/v1/messages")
async def messages(payload: AnthropicRequest):
    """Anthropic Messages API 兼容端点

    1. 接收 Anthropic 格式请求
    2. 翻译为 OpenAI 格式
    3. 通过 OpenLLM Provider 路由执行
    4. 将响应翻译回 Anthropic 格式
    """
    # 输入校验
    msg_err = validate_chat_messages(
        [{"role": m.role, "content": m.content if isinstance(m.content, str) else ""} for m in payload.messages]
    )
    if msg_err:
        raise HTTPException(status_code=400, detail=msg_err)
    model_err = validate_model_name(payload.model)
    if model_err:
        raise HTTPException(status_code=400, detail=model_err)

    # 1. Anthropic → OpenAI 翻译
    anthropic_req = {
        "model": payload.model,
        "messages": [{"role": m.role, "content": m.content} for m in payload.messages],
        "max_tokens": payload.max_tokens,
        "temperature": payload.temperature,
        "top_p": payload.top_p,
        "stream": payload.stream,
    }
    if payload.system:
        anthropic_req["system"] = payload.system

    openai_req = _translator.to_openai(anthropic_req)

    # 2. 解析 Provider / 模型
    provider_name, model_name = _parse_model(openai_req.get("model", ""))
    provider = registry.get(provider_name)
    if not provider:
        found = _find_model_globally(openai_req.get("model", ""))
        if found:
            provider_name, model_name = found
            provider = registry.get(provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"No provider for '{payload.model}'")

    # 3. 冷却检查
    if cooldown.is_cooled(f"provider:{provider_name}"):
        raise HTTPException(status_code=429, detail=f"Provider {provider_name} cooling")

    internal_req = InternalRequest(
        model=model_name or openai_req.get("model", ""),
        messages=[ChatMessage(role=m["role"], content=m["content"]) for m in openai_req.get("messages", [])],
        stream=payload.stream,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        original_format="anthropic",
    )

    # 4. 执行
    if payload.stream:
        return StreamingResponse(
            _stream_anthropic(provider_name, provider, internal_req),
            media_type="text/event-stream",
        )

    try:
        response = await provider.chat_completion(internal_req)
        # 5. OpenAI → Anthropic 翻译
        openai_resp = {
            "id": "chatcmpl-openllm",
            "model": response.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response.content},
                "finish_reason": response.finish_reason,
            }],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            } if response.usage else None,
        }
        return _translator.from_openai(openai_resp)
    except Exception as e:
        logger.error("Anthropic proxy failed: %s", e)
        raise HTTPException(status_code=502, detail="Upstream provider error")


async def _stream_anthropic(
    provider_name: str, provider, req: InternalRequest
) -> AsyncGenerator[str, None]:
    """Anthropic 格式的流式响应 — 完整 SSE 事件序列

    Anthropic SSE 规范要求的完整事件序列：
    1. message_start（含完整消息元数据）
    2. content_block_start（首个文本块）
    3. content_block_delta（增量文本，零到多条）
    4. content_block_stop（文本块结束）
    5. message_delta（含 stop_reason 和 usage）
    6. message_stop（流结束信号）
    """
    _sent_start = False
    _sent_block = False

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    try:
        async for chunk in provider.chat_completion_stream(req):
            # 首次 chunk → 发出 message_start + content_block_start
            if not _sent_start:
                yield _sse({
                    "type": "message_start",
                    "message": {
                        "id": "msg_openllm", "type": "message",
                        "role": "assistant", "content": [], "model": req.model,
                    },
                })
                _sent_start = True
            if not _sent_block:
                yield _sse({
                    "type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""},
                })
                _sent_block = True

            # 翻译为 Anthropic SSE 事件
            anthropic_chunk = _translator.from_openai_stream({
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk.content},
                    "finish_reason": chunk.finish_reason,
                }]
            })
            yield _sse(anthropic_chunk)

        # 流结束 → 发出 content_block_stop + message_delta + message_stop
        yield _sse({"type": "content_block_stop", "index": 0})
        yield _sse({
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": 0},
        })
        yield _sse({"type": "message_stop"})
    except Exception as e:
        logger.error("Anthropic stream error: %s", e)
        yield _sse({"type": "error", "error": {"message": "An internal stream error occurred"}})


def _parse_model(model: str) -> tuple[str, str]:
    if "/" in model:
        parts = model.split("/", 1)
        return parts[0], parts[1]
    return model, model


def _find_model_globally(model: str) -> tuple[str, str] | None:
    cached = registry.get_cached_models()
    for m in cached:
        if m.get("id") == model:
            return m.get("provider", ""), model
    for pname in registry.list_providers():
        if pname == model:
            return pname, "auto"
    return None
