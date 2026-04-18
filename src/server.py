"""Server entry point for OpenLLM"""

import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    logger.info("OpenLLM server started")

    yield

    logger.info("Shutting down OpenLLM server...")
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
