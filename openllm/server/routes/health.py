"""健康检查路由"""

from __future__ import annotations

from fastapi import APIRouter

from openllm.server.app import registry

router = APIRouter()


@router.get("/health")
async def health():
    """健康检查 — 包含 Provider 级别健康状态"""
    from openllm.server.app import circuit_breaker

    providers = registry.list_providers()
    provider_details = {}
    healthy_count = 0
    for name in providers:
        provider = registry.get(name)
        cb = circuit_breaker.get_state(name)
        status = "unknown"
        if provider:
            try:
                models = await provider.list_models()
                if models:
                    status = "healthy"
                    healthy_count += 1
                else:
                    status = "no_models"
            except Exception:
                status = "unreachable"
        provider_details[name] = {
            "status": status,
            "circuit_breaker": cb,
        }

    overall = "healthy"
    if not providers:
        overall = "degraded"
    elif healthy_count < len(providers):
        overall = "degraded"

    return {
        "status": overall,
        "version": "0.1.0",
        "healthy_providers": healthy_count,
        "total_providers": len(providers),
        "providers": provider_details,
    }
