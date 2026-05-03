"""API router for OpenLLM"""

import time
import logging
from fastapi import APIRouter, HTTPException
from src.dispatcher import get_dispatcher
from src.limiter import get_limiter
from src.models import ChatRequest, ChatResponse, ChatError, ModelList, ModelInfo, UsageInfo
from src.registry import get_registry
from src.scorer import get_scorer
from src.token_optimizer import TokenOptimizer, CompressionMode
from src.compression_strategy import get_compression_selector
from src.complexity_scorer import get_scorer, ComplexityLevel
from src.token_monitor import get_monitor
from src.prompt_enhancer import get_enhancer
from src.agent_registry import get_registry as get_agent_registry

logger = logging.getLogger(__name__)

# Global optimizer cache (per-model)
_optimizers: dict[str, TokenOptimizer] = {}

# Global complexity scorer
_scorer = get_scorer()

# Global token monitor
_monitor = get_monitor()


def get_optimizer(model_name: str) -> TokenOptimizer:
    """Get or create a model-specific token optimizer"""
    if model_name in _optimizers:
        return _optimizers[model_name]
    
    selector = get_compression_selector()
    config = selector.get_strategy(model_name)
    
    optimizer = TokenOptimizer(
        mode=config.mode,
        preserve_code=config.preserve_code,
        max_compression_ratio=config.max_compression_ratio,
    )
    
    _optimizers[model_name] = optimizer
    logger.info(
        f"Created optimizer for {model_name}: "
        f"mode={config.mode.value}, max_ratio={config.max_compression_ratio}"
    )
    
    return optimizer


router = APIRouter(prefix="/v1")


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest) -> ChatResponse:
    try:

        # Get agent from request state (set by middleware)
        # Note: We need to access the actual FastAPI Request object
        # For now, use the agent_id from the request body or default
        agent_id = request.agent_id or "default"
        agent_registry = get_agent_registry()
        agent = agent_registry.get_or_default(agent_id)

        # Apply agent config defaults
        effective_code_thinking = request.code_thinking
        effective_terse = request.terse
        effective_terse_intensity = request.terse_intensity
        effective_model = request.model

        # If not explicitly set, use agent defaults
        if effective_code_thinking is None:
            effective_code_thinking = agent.code_thinking_enabled
        if effective_terse is None:
            effective_terse = agent.terse_enabled
        if effective_terse_intensity is None:
            effective_terse_intensity = agent.terse_intensity
        if effective_model == "meta-model" and agent.default_model:
            effective_model = agent.default_model
            request.model = effective_model

        # Scope session_id by agent
        if request.session_id:
            session_prefix = agent_registry.get_session_prefix(agent_id)
            if not request.session_id.startswith(session_prefix):
                request.session_id = f"{session_prefix}{request.session_id}"

        # Step 1: Analyze request complexity
        routing_decision = _scorer.get_routing_decision(
            [m.model_dump() for m in request.messages],
            request.model
        )

        # Step 1.5: Apply prompt enhancement (code thinking + terse mode)
        enhancer = get_enhancer()
        enhance_result = enhancer.enhance(
            messages=[m.model_dump() for m in request.messages],
            enable_code_thinking=effective_code_thinking,
            enable_terse=effective_terse,
            terse_intensity=effective_terse_intensity,
        )

        # Update messages with enhanced version
        from src.models import Message
        request.messages = [Message(**msg) for msg in enhance_result.messages]

        # Step 2: Apply routing if recommended
        original_model = request.model
        if routing_decision["should_route"] and routing_decision["recommended_model"]:
            request.model = routing_decision["recommended_model"]
            logger.info(
                f"Auto-routed: {original_model} → {request.model} "
                f"(complexity={routing_decision['complexity']}, "
                f"score={routing_decision['score']:.2f})"
            )

        # Step 3: Get model-specific optimizer
        model_name = request.model
        if model_name == "meta-model":
            optimizer = get_optimizer("default")
        else:
            optimizer = get_optimizer(model_name)

        # Step 4: Apply token optimization to user messages
        optimized_messages = optimizer.optimize_messages(
            [m.model_dump() for m in request.messages],
            model=model_name
        )

        # Step 5: Update request with optimized messages
        request.messages = [Message(**msg) for msg in optimized_messages]

        # Step 6: Dispatch to model
        dispatcher = get_dispatcher()
        response = await dispatcher.dispatch(request)

        # Step 7: Add routing metadata to response
        response.complexity = routing_decision["complexity"]
        response.routing_applied = routing_decision["should_route"]
        if routing_decision["recommended_model"]:
            response.recommended_model = routing_decision["recommended_model"]

        # Step 8: Add prompt enhancement metadata
        response.code_thinking_enabled = enhance_result.code_thinking_enabled
        response.terse_enabled = enhance_result.terse_mode_enabled
        response.terse_intensity = enhance_result.terse_intensity

        # Step 9: Record agent usage
        output_tokens = response.usage.completion_tokens if response.usage else 0
        agent_registry.record_usage(agent_id, tokens=output_tokens)

        # Step 10: Record monitoring data
        session_id = request.session_id or f"{agent_id}:anonymous-{id(request)}"
        _monitor.record_request(
            session_id=session_id,
            request={"usage": response.usage.model_dump() if response.usage else {}},
            response={"usage": response.usage.model_dump() if response.usage else {}},
            compression_info={
                "tokens_saved": 0
            }
        )

        return response
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models(model_type: str = None, model_scale: str = None) -> ModelList:
    registry = get_registry()
    models = registry.get_enabled_models(model_type, model_scale)

    data = [ModelInfo(id=m.name, created=int(time.time()), owned_by=m.protocol) for m in models]

    return ModelList(data=data)


@router.get("/models/{model}")
async def get_model(model: str) -> ModelInfo:
    registry = get_registry()
    model_config = registry.get_model(model)

    if not model_config:
        raise HTTPException(status_code=404, detail="Model not found")

    return ModelInfo(id=model_config.name, created=int(time.time()), owned_by=model_config.protocol)


@router.get("/usage")
async def usage() -> UsageInfo:
    limiter = get_limiter()
    scorer = get_scorer()

    model_usage = {}
    for model_name in limiter._limits:
        success = scorer._success_counts.get(model_name, 0)
        failure = scorer._failure_counts.get(model_name, 0)
        model_usage[model_name] = {
            "success": success,
            "failure": failure,
            "total": success + failure,
        }

    total_requests = sum(model_usage[m]["total"] for m in model_usage)

    return UsageInfo(total_requests=total_requests, total_tokens=0, model_usage=model_usage)


@router.get("/scores")
async def get_scores():
    scorer = get_scorer()
    scores = scorer.get_ranked_models()

    return {
        "models": [
            {
                "name": s.model_name,
                "total_score": s.total_score,
                "quality_score": s.quality_score,
                "speed_score": s.speed_score,
                "context_score": s.context_score,
                "reliability_score": s.reliability_score,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
            }
            for s in scores
        ]
    }


@router.post("/scores/refresh")
async def refresh_scores():
    return {"status": "Scores refreshed"}


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(time.time())}


# ============================================================
# Token Monitoring Endpoints (Phase 5)
# ============================================================

@router.get("/monitor/global")
async def monitor_global():
    """Get global token monitoring statistics"""
    report = _monitor.export_report()
    return report


@router.get("/monitor/sessions")
async def monitor_sessions(limit: int = 50, offset: int = 0):
    """Get list of sessions with statistics"""
    sessions = _monitor.get_session_list(limit=limit, offset=offset)
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "turns": s.turns,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "total_tokens": s.total_tokens,
                "compressed_tokens": s.compressed_tokens,
                "compression_ratio": s.compression_ratio,
                "cost": s.cost,
                "fill_rate": s.fill_rate,
                "last_activity": s.last_activity
            }
            for s in sessions
        ],
        "total": len(sessions)
    }


@router.get("/monitor/session/{session_id}")
async def monitor_session(session_id: str):
    """Get detailed statistics for a specific session"""
    report = _monitor.export_report(session_id)
    return report


@router.get("/monitor/anomalies")
async def monitor_anomalies(session_id: str = None, severity: str = None, limit: int = 100):
    """Get detected anomalies"""
    anomalies = _monitor.get_anomalies(session_id=session_id, severity=severity, limit=limit)
    return {
        "anomalies": [
            {
                "type": a.type,
                "severity": a.severity.value,
                "message": a.message,
                "session_id": a.session_id,
                "timestamp": a.timestamp,
                "details": a.details
            }
            for a in anomalies
        ]
    }


@router.post("/monitor/clear")
async def monitor_clear(session_id: str = None):
    """Clear monitoring data"""
    if session_id:
        _monitor.clear_session(session_id)
        return {"status": f"Session {session_id} cleared"}
    else:
        _monitor.clear_all()
        return {"status": "All monitoring data cleared"}
