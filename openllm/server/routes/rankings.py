"""模型排名路由 — 模型优选系统的 API 端点"""

from __future__ import annotations

from fastapi import APIRouter, Query

from openllm.server.app import registry
from openllm.core.ranker import Ranker

router = APIRouter()
ranker = Ranker(registry)


@router.get("/v1/models/rankings")
async def list_rankings(
    sort_by: str = Query("overall", description="排序字段: speed / quality / cost / overall"),
    top_n: int = Query(100, description="返回数量", ge=1, le=200),
):
    """获取所有模型的基准测试排名"""
    results = ranker.load_rankings()
    if not results:
        return {"object": "list", "data": [], "message": "No benchmark data yet. Run 'openllm rank' first."}

    sort_field_map = {
        "speed": "speed_score",
        "quality": "quality_score",
        "cost": "cost_score",
        "overall": "overall_score",
    }
    sort_field = sort_field_map.get(sort_by, "overall_score")

    sorted_results = sorted(
        results.values(),
        key=lambda r: getattr(r, sort_field, 0),
        reverse=True,
    )[:top_n]

    data = []
    for r in sorted_results:
        data.append({
            "id": r.model_id,
            "provider": r.provider,
            "object": "ranking",
            "scores": {
                "overall": r.overall_score,
                "speed": r.speed_score,
                "quality": r.quality_score,
                "cost": r.cost_score,
            },
            "metrics": {
                "avg_latency_ms": r.avg_latency_ms,
                "tokens_per_second": r.tokens_per_second,
                "error_rate": r.error_rate,
            },
            "tested_at": r.tested_at,
        })

    return {
        "object": "list",
        "data": data,
        "sort_by": sort_by,
    }


@router.get("/v1/models/recommend")
async def recommend_model(
    preference: str = Query("balanced", description="推荐偏好: speed / quality / cost / balanced"),
    top_n: int = Query(3, description="返回数量", ge=1, le=20),
):
    """根据偏好推荐最优模型"""
    results = ranker.recommend(preference=preference, top_n=top_n)
    if not results:
        return {"object": "list", "data": [], "message": "No benchmark data yet. Run 'openllm rank' first."}

    return {
        "object": "list",
        "data": [
            {
                "id": r.model_id,
                "provider": r.provider,
                "preference": preference,
                "overall_score": r.overall_score,
                "speed_score": r.speed_score,
                "quality_score": r.quality_score,
                "cost_score": r.cost_score,
                "avg_latency_ms": r.avg_latency_ms,
                "tokens_per_second": r.tokens_per_second,
            }
            for r in results
        ],
    }
