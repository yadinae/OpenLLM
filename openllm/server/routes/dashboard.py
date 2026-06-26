"""Dashboard 管理界面 — Provider 状态、模型列表、熔断器"""
from __future__ import annotations

import pathlib

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from openllm.server.app import registry, circuit_breaker, cooldown, health_tracker, metadata_registry, get_combos

router = APIRouter()

# 读取同目录下的 dashboard.html 模板
_TEMPLATE_PATH = pathlib.Path(__file__).with_suffix(".html")


def _load_html() -> str:
    if _TEMPLATE_PATH.exists():
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    # fallback：内联（不应触发）
    return "<html><body>Dashboard template not found</body></html>"


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """管理界面首页"""
    return HTMLResponse(content=_load_html(), status_code=200)


@router.get("/api/status")
async def api_status():
    """Dashboard 数据端点: Provider 详细状态 + 健康分数 + 延迟"""
    from openllm.server.app import registry as reg
    providers = reg.list_providers()
    result = {}
    for name in providers:
        cb = circuit_breaker.get_state(name)
        score = health_tracker.get_score(name)
        p50 = health_tracker.get_latency_p50(name)
        p95 = health_tracker.get_latency_p95(name)
        result[name] = {
            "health_score": score,
            "latency_p50": p50,
            "latency_p95": p95,
            "circuit_breaker": cb,
        }
    return {"providers": result}


@router.get("/api/combos")
async def api_combos():
    """Dashboard 数据端点: Combo 路由配置"""
    combos = get_combos()
    data = {}
    for name, cfg in combos.items():
        data[name] = {
            "strategy": cfg.strategy.value,
            "members": [{"provider": m.provider, "model": m.model, "priority": m.priority} for m in cfg.members],
        }
    return {"combos": data}
