import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from openllm.core.registry import Registry
from openllm.core.cooldown import CooldownManager
from openllm.core.combo import ComboEngine
from openllm.core.circuit import CircuitBreaker
from openllm.core.state import load_env_file, get_data_dir
from openllm.core.types import ProviderConfig
from openllm.core.config_loader import load_config, load_providers_from_config, load_combos_from_config
from openllm.providers.openai_compat import OpenAICompatProvider
from openllm.server.validation import validate_request_body

logger = logging.getLogger(__name__)

# 全局单例
registry = Registry()
cooldown = CooldownManager()
combo_engine = ComboEngine(registry, cooldown)
circuit_breaker = CircuitBreaker()
_loaded_combos: dict[str, object] = {}  # 供路由模块读取
_api_key: str | None = None  # API 认证密钥


def set_api_key(key: str | None) -> None:
    """设置 API 认证密钥（由 CLI 传入）"""
    global _api_key
    _api_key = key


def create_app(api_key: str | None = None) -> FastAPI:
    """应用工厂

    Args:
        api_key: 可选 API 密钥，设置后所有端点需要 Authorization: Bearer <key>
    """
    if api_key is not None:
        set_api_key(api_key)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _load_providers()
        await registry.discover_models()
        registry.save_snapshot()
        logger.info("OpenLLM started with %d provider(s)", len(registry.list_providers()))

        # 后台健康检查任务
        health_task = asyncio.create_task(_health_check_loop())
        yield

        # 关闭后台任务
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

        # 关闭所有 Provider 的 HTTP 客户端（逐个关闭，失败不阻塞后续）
        for name in registry.list_providers():
            provider = registry.get(name)
            if provider and hasattr(provider, 'close'):
                try:
                    await provider.close()
                except Exception as e:
                    logger.warning("Error closing provider %s: %s", name, e)
        logger.info("OpenLLM shut down")

    app = FastAPI(title="OpenLLM", version="0.1.0", lifespan=lifespan)

    # CORS: 仅当绑定到非 localhost 且未设置 api_key 时警告
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 认证中间件（可选，设置 api_key 后启用）
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # 请求体大小校验
        validation_result = validate_request_body(request)
        if validation_result is not None:
            return validation_result

        if _api_key:
            # /health 和 /docs 不要求认证
            if request.url.path in ("/health", "/docs", "/openapi.json"):
                return await call_next(request)
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] != _api_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "unauthorized", "message": "Invalid or missing API key"},
                )
        return await call_next(request)

    from .routes import chat, models, health, messages, rankings
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(chat.router)
    app.include_router(messages.router)
    app.include_router(rankings.router)

    return app


def _load_providers() -> None:
    """加载 Provider — 优先从配置文件，其次从环境变量"""
    global _loaded_combos

    # 1. 收集环境变量
    env = dict(os.environ)
    for src in (get_data_dir() / ".env", Path.cwd() / ".env"):
        file_env = load_env_file(src)
        for k, v in file_env.items():
            env.setdefault(k, v)

    # 2. 尝试从配置文件加载
    config = load_config()
    providers_from_config = load_providers_from_config(config, env)
    combos = load_combos_from_config(config)

    if providers_from_config:
        for cfg in providers_from_config:
            provider = OpenAICompatProvider(cfg)
            registry.register(cfg.name, provider)
        _loaded_combos = {c.name: c for c in combos}
        logger.info("Loaded %d providers from config file", len(providers_from_config))
        return

    # 3. Fallback: 硬编码 Provider（向后兼容）
    provider_configs = {
        "openrouter": {"env_key": "OPENROUTER_API_KEY", "endpoint": "https://openrouter.ai/api/v1"},
        "groq": {"env_key": "GROQ_API_KEY", "endpoint": "https://api.groq.com/openai/v1"},
        "deepseek": {"env_key": "DEEPSEEK_API_KEY", "endpoint": "https://api.deepseek.com/v1"},
        "nvidia": {"env_key": "NVIDIA_API_KEY", "endpoint": "https://integrate.api.nvidia.com/v1"},
        "cerebras": {"env_key": "CEREBRAS_API_KEY", "endpoint": "https://api.cerebras.ai/v1"},
    }

    for name, cfg in provider_configs.items():
        api_key = env.get(cfg["env_key"])
        if not api_key:
            continue
        config = ProviderConfig(name=name, api_key=api_key, endpoint=cfg["endpoint"])
        provider = OpenAICompatProvider(config)
        registry.register(name, provider)
        logger.info("Loaded provider (env fallback): %s", name)

    from openllm.core.types import ComboConfig, ComboMember, RoutingStrategy
    _loaded_combos = {
        "auto": ComboConfig(name="auto", strategy=RoutingStrategy.FALLBACK, members=[
            ComboMember(model="auto", provider="openrouter", priority=0),
            ComboMember(model="auto", provider="groq", priority=1),
            ComboMember(model="auto", provider="deepseek", priority=2),
        ]),
        "fast": ComboConfig(name="fast", strategy=RoutingStrategy.FALLBACK, members=[
            ComboMember(model="auto", provider="groq", priority=0),
            ComboMember(model="auto", provider="deepseek", priority=1),
        ]),
        "free": ComboConfig(name="free", strategy=RoutingStrategy.FALLBACK, members=[
            ComboMember(model="auto", provider="openrouter", priority=0),
        ]),
    }


def get_combos() -> dict[str, object]:
    """获取已加载的 Combo 配置（供路由模块使用）"""
    return _loaded_combos


async def _health_check_loop() -> None:
    """后台健康检查 — 定期探测所有 Provider 连通性"""
    import asyncio

    check_interval = 300  # 每 5 分钟
    while True:
        await asyncio.sleep(check_interval)
        providers = registry.list_providers()
        if not providers:
            continue

        healthy = 0
        for name in providers:
            provider = registry.get(name)
            if not provider:
                continue
            try:
                models = await provider.list_models()
                if models is not None:
                    circuit_breaker.record_success(name)
                    healthy += 1
                else:
                    circuit_breaker.record_failure(name)
            except Exception as e:
                logger.warning("Health check failed for %s: %s", name, e)
                tripped = circuit_breaker.record_failure(name)
                if tripped:
                    logger.warning("Circuit breaker opened for %s", name)

        total = len(providers)
        if healthy < total:
            logger.warning(
                "Health check: %d/%d providers healthy",
                healthy, total,
            )
        else:
            logger.info("Health check: %d/%d providers healthy", healthy, total)
