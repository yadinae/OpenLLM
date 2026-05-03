"""
Session Tracker Router — FastAPI 端点

端点：
- POST   /api/session/events     — 处理消息，提取事件
- GET    /api/session/events     — 搜索历史事件
- GET    /api/session/context    — 获取会话上下文摘要
- POST   /api/session/enrich     — 用召回事件增强消息
- DELETE /api/session/{id}       — 删除会话
- GET    /api/session/stats      — 统计信息
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.session_tracker import SessionEventTracker, get_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["session"])

_tracker: Optional[SessionEventTracker] = None


def _get() -> SessionEventTracker:
    global _tracker
    if _tracker is None:
        _tracker = get_tracker()
    return _tracker


# ============================================================
# Models
# ============================================================

class ProcessRequest(BaseModel):
    messages: list[dict] = Field(..., description="消息列表")
    session_id: str = Field(..., description="会话 ID")


class ProcessResponse(BaseModel):
    events_extracted: int
    event_types: list[str]
    event_summaries: list[str]


class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询")
    session_id: str = Field(..., description="会话 ID")
    max_events: int = Field(10, description="最大结果数")


class SearchResponse(BaseModel):
    query: str
    events: list[dict]
    total_found: int
    context_tokens_saved: int


class ContextResponse(BaseModel):
    session_id: str
    context_text: str
    event_count: int


class EnrichRequest(BaseModel):
    messages: list[dict] = Field(..., description="消息列表")
    session_id: str = Field(..., description="会话 ID")
    max_tokens: int = Field(2000, description="最大额外 token 数")


class EnrichResponse(BaseModel):
    enhanced_messages: list[dict]
    recalled_events: int
    tokens_saved: int


# ============================================================
# Endpoints
# ============================================================

@router.post("/events", response_model=ProcessResponse)
async def process_events(req: ProcessRequest):
    """处理消息，提取并存储结构化事件

    零 LLM 成本：纯规则提取文件操作、错误、工具调用、用户决策等。
    """
    tracker = _get()
    events = tracker.process_messages(req.messages, req.session_id)

    return ProcessResponse(
        events_extracted=len(events),
        event_types=list(set(e.event_type for e in events)),
        event_summaries=[e.summary for e in events],
    )


@router.get("/events", response_model=SearchResponse)
async def search_events(
    q: str,
    session_id: str,
    max_events: int = 10,
):
    """BM25 搜索历史事件"""
    tracker = _get()
    recall = tracker.recall(query=q, session_id=session_id, max_events=max_events)

    return SearchResponse(
        query=q,
        events=[
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "category": e.category,
                "summary": e.summary,
                "data": e.data[:200],
                "priority": e.priority,
                "timestamp": e.timestamp,
            }
            for e in recall.events
        ],
        total_found=recall.total_found,
        context_tokens_saved=recall.context_tokens_saved,
    )


@router.get("/context", response_model=ContextResponse)
async def get_context(session_id: str, max_events: int = 20):
    """获取会话上下文摘要

    用于注入 system prompt，让模型记住关键历史。
    """
    tracker = _get()
    context = tracker.get_session_context(session_id, max_events=max_events)

    return ContextResponse(
        session_id=session_id,
        context_text=context,
        event_count=len(tracker.store.get_session_events(session_id)),
    )


@router.post("/enrich", response_model=EnrichResponse)
async def enrich_messages(req: EnrichRequest):
    """用召回的事件增强消息

    自动：
    1. 从消息中提取事件
    2. 用最后一条用户消息搜索相关历史
    3. 将历史事件注入 system prompt
    """
    tracker = _get()
    enhanced, meta = tracker.enrich_messages(
        messages=req.messages,
        session_id=req.session_id,
        max_tokens=req.max_tokens,
    )

    return EnrichResponse(
        enhanced_messages=enhanced,
        recalled_events=meta["recalled"],
        tokens_saved=meta["tokens_saved"],
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话的所有事件"""
    tracker = _get()
    deleted = tracker.delete_session(session_id)
    return {"deleted_events": deleted, "session_id": session_id}


@router.get("/stats")
async def get_stats(session_id: Optional[str] = None):
    """获取事件统计"""
    tracker = _get()
    return tracker.get_stats(session_id)


# ============================================================
# Prompt Enhancement Endpoints (Code Thinking + Terse Mode)
# ============================================================

from pydantic import BaseModel as BM
from src.prompt_enhancer import get_enhancer


class EnhanceTestRequest(BM):
    messages: list[dict]
    code_thinking: Optional[bool] = None
    terse: Optional[bool] = None
    terse_intensity: Optional[str] = None


class EnhanceTestResponse(BM):
    original_messages: list[dict]
    enhanced_messages: list[dict]
    code_thinking_enabled: bool
    terse_enabled: bool
    terse_intensity: str
    injected_instructions: list[str]


@router.post("/enhance/test")
async def test_enhance(req: EnhanceTestRequest):
    """测试提示增强效果

    模拟 chat completions 的增强流程，预览 system prompt 注入效果。
    """
    enhancer = get_enhancer()
    result = enhancer.enhance(
        messages=req.messages,
        enable_code_thinking=req.code_thinking,
        enable_terse=req.terse,
        terse_intensity=req.terse_intensity,
    )

    # 提取注入的指令
    instructions = []
    for msg in result.messages:
        if msg.get("role") == "system":
            content = msg.get("content", "")
            # 对比原始 system 和增强后的
            original = ""
            for orig in req.messages:
                if orig.get("role") == "system":
                    original = orig.get("content", "")
                    break
            injected = content[len(original):].strip()
            if injected:
                instructions.append(injected)

    return EnhanceTestResponse(
        original_messages=req.messages,
        enhanced_messages=result.messages,
        code_thinking_enabled=result.code_thinking_enabled,
        terse_enabled=result.terse_mode_enabled,
        terse_intensity=result.terse_intensity,
        injected_instructions=instructions,
    )


# ============================================================
# Agent Management Endpoints
# ============================================================

from src.agent_registry import (
    get_registry as get_agent_registry,
    reset_registry,
    AgentConfig,
    AgentQuota,
)


class AgentRegisterRequest(BM):
    agent_id: str
    name: str = ""
    platform: str = ""
    api_key: str = ""
    default_model: str = ""
    allowed_models: list[str] = []
    quota: Optional[dict] = None
    code_thinking_enabled: bool = True
    terse_enabled: bool = False
    terse_intensity: str = "moderate"


class AgentResponse(BM):
    agent_id: str
    name: str
    platform: str
    enabled: bool
    default_model: str
    code_thinking_enabled: bool
    terse_enabled: bool
    terse_intensity: str


class AgentUsageResponse(BM):
    agent_id: str
    today_tokens: int
    today_requests: int
    total_tokens: int
    total_requests: int
    last_request_at: str


@router.post("/agents/register")
async def register_agent(req: AgentRegisterRequest):
    """注册新 Agent

    如果不提供 api_key，系统会自动生成。
    注册后返回生成的 API Key，请妥善保存。
    """
    registry = get_agent_registry()

    quota = AgentQuota(**req.quota) if req.quota else AgentQuota()
    config = AgentConfig(
        agent_id=req.agent_id,
        name=req.name or req.agent_id,
        platform=req.platform,
        api_key=req.api_key,  # 可能为空，register 会自动生成
        default_model=req.default_model,
        allowed_models=req.allowed_models,
        quota=quota,
        code_thinking_enabled=req.code_thinking_enabled,
        terse_enabled=req.terse_enabled,
        terse_intensity=req.terse_intensity,
    )

    # generate_api_key=True: 如果没有提供 API Key 则自动生成
    success, api_key = registry.register(config, generate_api_key=(not req.api_key))
    if success:
        return {
            "status": "registered",
            "agent_id": req.agent_id,
            "api_key": api_key,
            "warning": "Save this API Key! It won't be shown again." if not req.api_key else None,
        }
    return {"status": "exists", "agent_id": req.agent_id}


@router.get("/agents")
async def list_agents():
    """列出所有 Agent"""
    registry = get_agent_registry()
    agents = registry.get_all_agents()
    return {
        "agents": [
            AgentResponse(
                agent_id=a.agent_id,
                name=a.name,
                platform=a.platform,
                enabled=a.enabled,
                default_model=a.default_model,
                code_thinking_enabled=a.code_thinking_enabled,
                terse_enabled=a.terse_enabled,
                terse_intensity=a.terse_intensity,
            )
            for a in agents
        ]
    }


@router.get("/agents/{agent_id}/usage")
async def get_agent_usage(agent_id: str):
    """获取指定 Agent 的使用统计"""
    registry = get_agent_registry()
    usage = registry.get_usage(agent_id)
    return AgentUsageResponse(
        agent_id=usage.agent_id,
        today_tokens=usage.today_tokens,
        today_requests=usage.today_requests,
        total_tokens=usage.total_tokens,
        total_requests=usage.total_requests,
        last_request_at=usage.last_request_at,
    )


@router.get("/agents/usage/all")
async def get_all_agent_usage():
    """获取所有 Agent 的使用统计"""
    registry = get_agent_registry()
    all_usage = registry.get_all_usage()
    return {
        "agents": [
            {
                "agent_id": u.agent_id,
                "today_tokens": u.today_tokens,
                "today_requests": u.today_requests,
                "total_tokens": u.total_tokens,
                "total_requests": u.total_requests,
                "last_request_at": u.last_request_at,
            }
            for u in all_usage.values()
        ]
    }


# ============================================================
# API Key Management
# ============================================================

class APIKeyResponse(BM):
    agent_id: str
    api_key: str
    masked_key: str


@router.post("/agents/{agent_id}/generate-key")
async def generate_api_key(agent_id: str):
    """为指定 Agent 生成新的 API Key

    会撤销旧的 Key（如果存在）。
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    if not agent:
        return {"error": "Agent not found", "agent_id": agent_id}

    new_key = registry._generate_api_key(agent_id)

    # 撤销旧 key
    if agent.api_key and agent.api_key in registry._api_key_map:
        del registry._api_key_map[agent.api_key]

    # 设置新 key
    agent.api_key = new_key
    registry._api_key_map[new_key] = agent_id
    registry.save()

    return APIKeyResponse(
        agent_id=agent_id,
        api_key=new_key,
        masked_key=new_key[:10] + "..." + new_key[-4:],
    )


@router.get("/agents/{agent_id}/keys")
async def list_agent_keys(agent_id: str):
    """列出 Agent 的 API Key（脱敏显示）"""
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)
    if not agent:
        return {"error": "Agent not found", "agent_id": agent_id}

    if not agent.api_key:
        return {"agent_id": agent_id, "has_key": False}

    key = agent.api_key
    masked = key[:10] + "***" + key[-4:]

    return {
        "agent_id": agent_id,
        "has_key": True,
        "masked_key": masked,
        "hint": f"Use as: X-API-Key: {key}",
    }
