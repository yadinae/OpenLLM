"""OpenLLM CLI — 命令行入口"""

from __future__ import annotations

import logging

import typer

app = typer.Typer(
    name="openllm",
    help="AI API Gateway — route to multiple AI providers with failover",
)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="绑定地址"),
    port: int = typer.Option(11343, "--port", "-p", help="端口"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="日志级别"),
    reload: bool = typer.Option(False, "--reload", help="热重载（开发模式）"),
    api_key: str = typer.Option(None, "--api-key", "-k", help="API 认证密钥（设置后所有端点需要 Bearer Token）"),
):
    """启动 OpenLLM 网关服务器"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    import uvicorn
    from openllm.server import create_app

    app = create_app(api_key=api_key)
    typer.echo(f"🚀 OpenLLM starting on http://{host}:{port}")

    # CORS 安全警告
    if host not in ("127.0.0.1", "localhost") and not api_key:
        typer.echo("⚠️  WARNING: Binding to non-localhost without --api-key")
        typer.echo("   CORS is set to allow all origins (allow_origins=[\"*\"])")
        typer.echo("   Any website can make cross-origin requests to this server.")
        typer.echo("   Use --api-key to enable authentication, or bind to 127.0.0.1")

    if api_key:
        typer.echo("🔐 API key auth enabled")
    typer.echo(f"   Health: http://{host}:{port}/health")
    typer.echo(f"   Models: http://{host}:{port}/v1/models")
    typer.echo(f"   Chat:   POST http://{host}:{port}/v1/chat/completions")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        reload=reload,
    )


@app.command()
def list_providers(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细信息"),
):
    """列出已注册的 Provider"""
    from openllm.server.app import create_app
    import asyncio
    
    async def _list():
        create_app()
        from openllm.server.app import registry
        providers = registry.list_providers()
        if not providers:
            typer.echo("⚠️  No providers registered. Set API keys in .env")
            return
        
        typer.echo(f"📡 Registered providers ({len(providers)}):")
        for name in providers:
            if verbose:
                models = registry.get_cached_models()
                provider_models = [m for m in models if m["provider"] == name]
                typer.echo(f"  ✅ {name} ({len(provider_models)} models)")
            else:
                typer.echo(f"  ✅ {name}")
    
    # 使用 lifespan 上下文
    asyncio.run(_list())


@app.command()
def doctor():
    """诊断检查 — 验证配置和 Provider 连通性"""
    from openllm.server.app import create_app
    import asyncio
    
    async def _doctor():
        typer.echo("🔍 OpenLLM Doctor")
        typer.echo("═" * 40)
        
        _ = create_app()
        from openllm.server.app import registry
        
        providers = registry.list_providers()
        if not providers:
            typer.echo("❌ No providers configured")
            typer.echo("   Set API keys in .env or environment:")
            typer.echo("   - OPENROUTER_API_KEY")
            typer.echo("   - GROQ_API_KEY")
            typer.echo("   - DEEPSEEK_API_KEY")
            typer.echo("   - NVIDIA_API_KEY")
            return
        
        typer.echo(f"✅ Providers: {len(providers)}")
        for name in providers:
            provider = registry.get(name)
            if provider:
                try:
                    models = await provider.list_models()
                    typer.echo(f"   ✅ {name}: {len(models)} models")
                except Exception as e:
                    typer.echo(f"   ⚠️  {name}: {e}")
        
        typer.echo("═" * 40)
        typer.echo("✅ Doctor check complete")
    
    asyncio.run(_doctor())


@app.command()
def bind(
    agent: str = typer.Argument(..., help="Client to configure (aider/continue/hermes/openclaw/claude-code)"),
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="OpenLLM host"),
    port: int = typer.Option(11343, "--port", "-p", help="OpenLLM port"),
):
    """一键配置 AI 客户端工具指向 OpenLLM 网关"""
    from .binder import bind_agent
    result = bind_agent(agent, host, port)
    typer.echo(result)


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()
