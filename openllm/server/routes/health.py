"""健康检查路由"""

from __future__ import annotations

from fastapi import APIRouter

from openllm.server.app import registry

router = APIRouter()


@router.get("/health")
async def health():
    """健康检查"""
    providers = registry.list_providers()
    return {
        "status": "healthy" if providers else "degraded",
        "version": "0.1.0",
        "providers": providers,
    }
