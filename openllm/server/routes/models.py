"""模型列表路由"""

from __future__ import annotations

from fastapi import APIRouter

from openllm.server.app import registry

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    """列出所有可用模型（OpenAI 兼容格式）"""
    models = registry.get_cached_models()
    data = []
    for m in models:
        data.append({
            "id": f"{m['provider']}/{m['id']}",
            "object": "model",
            "created": 0,
            "owned_by": m["provider"],
        })
    return {"object": "list", "data": data}
