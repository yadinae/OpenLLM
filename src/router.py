"""API router for OpenLLM"""

import time
import logging
from fastapi import APIRouter, HTTPException
from src.dispatcher import get_dispatcher
from src.limiter import get_limiter
from src.models import ChatRequest, ChatResponse, ChatError, ModelList, ModelInfo, UsageInfo
from src.registry import get_registry
from src.scorer import get_scorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest) -> ChatResponse:
    try:
        dispatcher = get_dispatcher()
        return await dispatcher.dispatch(request)
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
