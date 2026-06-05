from .app import create_app

# 预创建 app 实例，使 uvicorn openllm.server:app 能正确获取 FastAPI 实例
# 而非解析为 openllm.server.app 模块（Python submodule resolution）
app = create_app()

__all__ = ["app", "create_app"]
