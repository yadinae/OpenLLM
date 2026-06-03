"""聊天补全路由 — OpenAI 兼容"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from openllm.server.app import registry, combo_engine, cooldown, circuit_breaker, get_combos
from openllm.core.types import ChatRequest as InternalRequest, ChatMessage, ChatResponse
from openllm.core.errors import ProviderError
from openllm.server.validation import validate_chat_messages, validate_model_name

logger = logging.getLogger(__name__)

router = APIRouter()


class MessagePayload(BaseModel):
    role: str
    content: str


class ChatPayload(BaseModel):
    model: str
    messages: list[MessagePayload]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


@router.post("/v1/chat/completions")
async def chat_completions(payload: ChatPayload):
    """OpenAI 兼容的聊天补全端点"""
    model = payload.model
    is_stream = payload.stream

    # 输入校验
    msg_err = validate_chat_messages(
        [{"role": m.role, "content": m.content} for m in payload.messages]
    )
    if msg_err:
        raise HTTPException(status_code=400, detail=msg_err)
    model_err = validate_model_name(model)
    if model_err:
        raise HTTPException(status_code=400, detail=model_err)

    internal_req = InternalRequest(
        model=model,
        messages=[ChatMessage(role=m.role, content=m.content) for m in payload.messages],
        stream=is_stream,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )

    # 1. 判断是 combo
    combo = _find_combo(model)
    if combo:
        if is_stream:
            return StreamingResponse(
                _stream_combo(combo.name, internal_req),
                media_type="text/event-stream",
            )
        try:
            response = await combo_engine.execute(combo, internal_req)
            return _format_response(response)
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

    # 2. 解析 provider/model
    provider_name, model_name = _parse_model(model)
    provider = registry.get(provider_name)
    if not provider:
        # P1-4: 无前缀模型名 → 自动在所有 Provider 中查找
        found = _find_model_globally(model)
        if found:
            provider_name, model_name = found
            provider = registry.get(provider_name)
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"No provider found for '{model}'. Available: {registry.list_providers()}"
        )

    # 3. 检查冷却
    cool_key = f"provider:{provider_name}"
    if cooldown.is_cooled(cool_key):
        remaining = cooldown.get_remaining(cool_key)
        raise HTTPException(
            status_code=429,
            detail=f"Provider {provider_name} is cooling down ({remaining:.0f}s)"
        )

    # 4. 检查熔断
    if circuit_breaker.is_open(provider_name):
        remaining = circuit_breaker.get_remaining(provider_name)
        raise HTTPException(
            status_code=503,
            detail=f"Provider {provider_name} is circuit-broken ({remaining:.0f}s remaining)"
        )

    internal_req.model = model_name or model

    # 4. 流式 / 非流式
    if is_stream:
        return StreamingResponse(
            _stream_provider(provider_name, provider, internal_req),
            media_type="text/event-stream",
        )

    try:
        response = await provider.chat_completion(internal_req)
        circuit_breaker.record_success(provider_name)
        return _format_response(response)
    except Exception as e:
        _record_failure(provider_name, e)
        logger.error("Provider %s failed: %s", provider_name, e)
        raise HTTPException(status_code=502, detail="Upstream provider error")


def _parse_model(model: str) -> tuple[str, str]:
    """解析 'provider/model' 格式"""
    if "/" in model:
        parts = model.split("/", 1)
        return parts[0], parts[1]
    return model, model


def _find_model_globally(model: str) -> tuple[str, str] | None:
    """自动在所有已注册 Provider 中查找模型（P1-4 修复）"""
    cached = registry.get_cached_models()
    for m in cached:
        m_id = m.get("id", "")
        m_provider = m.get("provider", "")
        # 完全匹配
        if m_id == model:
            return m_provider, m_id
    # 未找到缓存的模型，遍历 provider 尝试直接调用
    for pname in registry.list_providers():
        if pname == model:
            return pname, "auto"
    return None


def _record_failure(provider_name: str, exc: Exception) -> None:
    """记录失败并自动设置冷却（P1-2 修复）"""
    from openllm.core.errors import RateLimitError, AuthError
    
    circuit_breaker.record_failure(provider_name)

    if isinstance(exc, RateLimitError):
        cooldown.set_cooldown(f"provider:{provider_name}", 120, "rate_limit")
    elif isinstance(exc, AuthError):
        cooldown.set_cooldown(f"provider:{provider_name}", 300, "auth")
    elif isinstance(exc, ProviderError):
        duration = _cooldown_for_kind(exc.kind)
        cooldown.set_cooldown(f"provider:{provider_name}", duration, exc.kind.value)
    else:
        cooldown.set_cooldown(f"provider:{provider_name}", 60, "unknown")


def _cooldown_for_kind(kind) -> float:
    durations = {
        "rate_limit": 120, "auth": 300, "quota_exhausted": 3600,
        "timeout": 30, "server_error": 60, "overloaded": 120,
        "model_not_found": 600, "unknown": 60,
    }
    return durations.get(kind.value if hasattr(kind, 'value') else kind, 60)


# ─── Combo 查找 ──────────────────────────────────────


def _find_combo(model: str):
    """查找 Combo 配置（从服务器加载的配置中查找）"""
    return get_combos().get(model)


async def _stream_combo(combo_name: str, req: InternalRequest) -> AsyncGenerator[str, None]:
    """真流式 Combo — 首 chunk 到达前可切换 Provider（P1-1 修复）

    逐个尝试 combo 成员：
    - 首 chunk 到达 → 转发该 Provider 的完整流
    - 失败 → 自动切下一成员
    """
    combo = get_combos().get(combo_name)
    if not combo:
        yield f"data: {json.dumps({'error': 'combo not found'})}\n\n"
        return

    sorted_members = sorted(combo.members, key=lambda m: m.priority)
    failures = []
    stream_started = False

    for member in sorted_members:
        cool_key = f"provider:{member.provider}"
        if cooldown.is_cooled(cool_key):
            failures.append(f"{member.provider}: cooled")
            continue

        if circuit_breaker.is_open(member.provider):
            failures.append(f"{member.provider}: circuit-broken")
            continue

        provider = registry.get(member.provider)
        if not provider:
            failures.append(f"{member.provider}: not registered")
            continue

        provider_req = InternalRequest(
            model=member.model,
            messages=req.messages,
            stream=True,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )

        try:
            # 尝试启动流 — 等首 chunk
            stream = provider.chat_completion_stream(provider_req)
            first_chunk = await stream.__anext__()
            # 首 chunk 到达 → 锁定此 Provider，转发首块 + 后续
            yield _sse_chunk(first_chunk)
            async for chunk in stream:
                yield _sse_chunk(chunk)
            yield "data: [DONE]\n\n"
            circuit_breaker.record_success(member.provider)
            stream_started = True
            break
        except StopAsyncIteration:
            failures.append(f"{member.provider}: empty stream")
        except Exception as e:
            logger.warning("Combo member %s failed: %s", member.provider, e)
            _record_failure(member.provider, e)
            failures.append(f"{member.provider}: {e}")

    if not stream_started:
        error_msg = "; ".join(failures)
        yield f"data: {json.dumps({'error': f'All combo members failed: {error_msg}'})}\n\n"


def _sse_chunk(chunk: ChatResponse) -> str:
    """格式化为 SSE 数据行"""
    data = {
        "choices": [{
            "delta": {"content": chunk.content},
            "finish_reason": chunk.finish_reason or None,
        }]
    }
    return f"data: {json.dumps(data)}\n\n"


async def _stream_provider(provider_name: str, provider, req: InternalRequest) -> AsyncGenerator[str, None]:
    """Provider 直连流式"""
    try:
        async for chunk in provider.chat_completion_stream(req):
            yield _sse_chunk(chunk)
        yield "data: [DONE]\n\n"
        circuit_breaker.record_success(provider_name)
    except Exception as e:
        _record_failure(provider_name, e)
        logger.error("Stream error from %s: %s", provider_name, e)
        yield f"data: {json.dumps({'error': 'stream_error', 'message': 'An internal error occurred'})}\n\n"


def _format_response(response: ChatResponse) -> dict:
    """OpenAI 兼容响应格式"""
    return {
        "id": "chatcmpl-openllm",
        "object": "chat.completion",
        "created": 0,
        "model": response.actual_model or response.model,
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
