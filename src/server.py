"""Server entry point for OpenLLM"""

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.context import ContextManager, get_context_manager
from src.limiter import get_limiter
from src.registry import get_registry
from src.router import router
from src.scorer import get_scorer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

_auto_test_interval: int = 3600  # 1 hour default
_auto_test_task: Optional[asyncio.Task] = None


async def _run_model_tester():
    from src.tester import ModelTester

    config_dir = Path(__file__).parent.parent / "config"
    models_config = config_dir / "models.yaml"

    registry = get_registry()
    if models_config.exists():
        registry.load_from_yaml(str(models_config))

    tester = ModelTester(registry)

    while True:
        try:
            results = await tester.test_all_models()
            tester.update_config(results, models_config)
            logger.info(f"Model test completed: {len(results)} models tested")
        except Exception as e:
            logger.error(f"Model test failed: {e}")

        await asyncio.sleep(_auto_test_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _auto_test_task

    logger.info("Starting OpenLLM server...")

    config_dir = Path(__file__).parent.parent / "config"
    models_config = config_dir / "models.yaml"

    registry = get_registry()
    if models_config.exists():
        registry.load_from_yaml(str(models_config))
        logger.info(f"Loaded models from {models_config}")
    else:
        logger.warning(f"Models config not found: {models_config}")

    limiter = get_limiter()
    scorer = get_scorer()
    context_mgr = get_context_manager()

    _auto_test_task = asyncio.create_task(_run_model_tester())
    logger.info(f"Auto model tester started (interval: {_auto_test_interval}s)")

    logger.info("OpenLLM server started")

    yield

    logger.info("Shutting down OpenLLM server...")
    if _auto_test_task:
        _auto_test_task.cancel()
        try:
            await _auto_test_task
        except asyncio.CancelledError:
            pass
    await registry.close_all()
    logger.info("OpenLLM server stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenLLM",
        description="AI Model Aggregation Platform with Scoring",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()


def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    uvicorn.run("openllm.src.server:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    run()
