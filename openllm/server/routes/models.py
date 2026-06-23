"""模型列表路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from openllm.server.app import registry, metadata_registry

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    """列出所有可用模型（OpenAI 兼容格式）"""
    models = registry.get_cached_models()
    data = []
    for m in models:
        mid = f"{m['provider']}/{m['id']}"
        meta = metadata_registry.get(mid)
        entry = {
            "id": mid,
            "object": "model",
            "created": 0,
            "owned_by": m["provider"],
            "context_window": meta.context_length if meta else m.get("context_length", 4096),
            "capabilities": meta.capabilities if meta else m.get("capabilities", ["text"]),
            "supports_reasoning": meta.supports_reasoning if meta else m.get("supports_reasoning", False),
        }
        if meta and meta.pricing_input_per_1k > 0:
            entry["pricing"] = {
                "input": meta.pricing_input_per_1k,
                "output": meta.pricing_output_per_1k,
            }
        data.append(entry)
    return {"object": "list", "data": data}


@router.get("/v1/models/{provider}/{model_name}")
async def get_model(provider: str, model_name: str):
    """获取单个模型的详细信息"""
    model_id = f"{provider}/{model_name}"
    meta = metadata_registry.get(model_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return {
        "id": model_id,
        "object": "model",
        "created": 0,
        "owned_by": provider,
        "context_window": meta.context_length,
        "capabilities": meta.capabilities,
        "supports_reasoning": meta.supports_reasoning,
        "supports_vision": meta.supports_vision,
        "supports_tool_use": meta.supports_tool_use,
        "supports_streaming": meta.supports_streaming,
        "pricing": {
            "input": meta.pricing_input_per_1k,
            "output": meta.pricing_output_per_1k,
        } if meta.pricing_input_per_1k > 0 else None,
        "max_output_tokens": meta.max_output_tokens,
    }
