"""OpenLLM CLI — 命令行入口"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

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

    # 启动自检
    typer.echo("🔍 OpenLLM Self-Check...")
    issues = _startup_self_check()
    for issue in issues:
        typer.echo(f"  {issue}")

    # 如果有致命问题，继续启动但标记
    critical = [i for i in issues if i.startswith("❌")]
    if critical:
        typer.echo("❌ Fatal: Self-check failed, abort startup")
        raise typer.Exit(code=1)

    if not critical and issues:
        typer.echo("⚠️  Self-check completed with warnings, starting anyway")
    else:
        typer.echo("✅ Self-check passed")

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
    import asyncio

    async def _list():
        from openllm.server.app import _load_providers, registry
        _load_providers()
        await registry.discover_models()
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

    asyncio.run(_list())


@app.command()
def doctor():
    """诊断检查 — 验证配置和 Provider 连通性"""
    import asyncio

    async def _doctor():
        typer.echo("🔍 OpenLLM Doctor")
        typer.echo("═" * 40)

        from openllm.server.app import _load_providers, registry
        _load_providers()
        await registry.discover_models()

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


@app.command()
def rank(
    provider: str = typer.Option(None, "--provider", "-p", help="仅测试指定 Provider"),
    model: str = typer.Option(None, "--model", "-m", help="仅测试指定模型"),
):
    """运行模型基准测试 — 测量速度/质量/成本，生成评分"""
    from openllm.server.app import create_app, registry
    from openllm.core.ranker import Ranker
    import asyncio

    async def _run():
        from openllm.server.app import _load_providers, registry
        _load_providers()
        await registry.discover_models()
        registry.save_snapshot()

        ranker = Ranker(registry)

        if provider and model:
            typer.echo(f"📊 Benchmarking {provider}/{model}...")
            result = await ranker.benchmark_one(provider, model)
            _print_benchmark(result)
        elif provider:
            typer.echo(f"📊 Benchmarking all models from {provider}...")
            results = await ranker.benchmark_all(
                progress=lambda i, t, p, m: typer.echo(
                    f"  [{i}/{t}] {p}/{m}..."
                )
            )
            _print_results_list(results.values())
        else:
            typer.echo("📊 Benchmarking all models from all providers...")
            results = await ranker.benchmark_all(
                progress=lambda i, t, p, m: typer.echo(
                    f"  [{i}/{t}] {p}/{m}..."
                )
            )
            _print_results_list(results.values())

    asyncio.run(_run())


@app.command()
def recommend(
    preference: str = typer.Option(
        "balanced", "--by", "-b",
        help="推荐维度: speed / quality / cost / balanced",
    ),
    top_n: int = typer.Option(5, "--top", "-n", help="返回数量"),
):
    """根据偏好推荐最优模型"""
    from openllm.core.ranker import Ranker

    ranker = Ranker()
    results = ranker.recommend(preference=preference, top_n=top_n)

    if not results:
        typer.echo("⚠️  暂无基准数据，请先运行 `openllm rank`")
        return

    label_map = {
        "speed": "⚡ 速度优先",
        "quality": "🎯 质量优先",
        "cost": "💰 性价比优先",
        "balanced": "⚖️  综合推荐",
    }
    typer.echo(f"\n📋 {label_map.get(preference, '推荐')} Top {len(results)}:")
    typer.echo("═" * 60)

    sort_key = {
        "speed": "speed_score",
        "quality": "quality_score",
        "cost": "cost_score",
        "balanced": "overall_score",
    }.get(preference, "overall_score")

    for i, r in enumerate(results, 1):
        score = getattr(r, sort_key, 0)
        typer.echo(
            f"  #{i}  {r.model_id:<35}  "
            f"{'★' * max(1, int(score / 20)):<5}"
            f"  {score:.0f}/100"
        )
    typer.echo("═" * 60)

    # 显示详情
    best = results[0]
    typer.echo(f"\n🏆 最佳选择: {best.model_id}")
    typer.echo(f"   综合评分: {best.overall_score:.0f}/100")
    typer.echo(f"   速度得分: {best.speed_score:.0f}/100  (延迟: {best.avg_latency_ms:.0f}ms)")
    typer.echo(f"   质量得分: {best.quality_score:.0f}/100")
    typer.echo(f"   成本得分: {best.cost_score:.0f}/100")
    if best.tokens_per_second > 0:
        typer.echo(f"   吞吐量:   {best.tokens_per_second:.0f} tokens/s")
    typer.echo(f"   测试时间: {best.tested_at[:19]}")


def _print_benchmark(r):
    """打印单个模型基准测试结果"""
    typer.echo(f"\n{'═' * 50}")
    typer.echo(f"📊 {r.model_id}")
    typer.echo(f"{'═' * 50}")
    typer.echo(f"  延迟:     {r.avg_latency_ms:.0f}ms" if r.avg_latency_ms > 0 else "  延迟:     N/A")
    typer.echo(f"  吞吐量:   {r.tokens_per_second:.0f} tokens/s" if r.tokens_per_second > 0 else "  吞吐量:   N/A")
    typer.echo(f"  质量评分: {r.quality_score:.0f}/100")
    typer.echo(f"  错误率:   {r.error_rate:.1%}")
    typer.echo(f"  速度得分: {r.speed_score:.0f}/100")
    typer.echo(f"  综合得分: {r.overall_score:.0f}/100")
    typer.echo(f"{'═' * 50}")


def _print_results_list(results):
    """打印基准测试结果列表"""
    sorted_r = sorted(results, key=lambda x: x.overall_score, reverse=True)
    typer.echo(f"\n📊 Benchmark Results ({len(sorted_r)} models)")
    typer.echo("═" * 70)
    typer.echo(f"  {'#':<4} {'Model':<35} {'Speed':<8} {'Quality':<8} {'Overall':<8}")
    typer.echo("─" * 70)
    for i, r in enumerate(sorted_r, 1):
        if r.error_rate >= 1.0:
            typer.echo(f"  {i:<4} {r.model_id:<35} {'❌':<8} {'ERR':<8} {'FAIL':<8}")
        else:
            typer.echo(
                f"  {i:<4} {r.model_id:<35} "
                f"{r.speed_score:<7.0f}  "
                f"{r.quality_score:<7.0f}  "
                f"{r.overall_score:<7.0f}"
            )
    typer.echo("═" * 70)


def _startup_self_check() -> list[str]:
    """启动自检 — 验证配置完整性，返回所有问题列表（空 list = 全部通过）"""
    issues: list[str] = []
    from openllm.core.config_loader import find_config, load_config
    from openllm.core.state import load_env_file

    # 1. 检查配置文件
    config_path = find_config()
    if not config_path:
        issues.append("⚠️  未找到配置文件 (openllm.yaml)，将使用环境变量回退模式")
        return issues  # 无配置文件不用继续检查
    issues.append(f"✅  配置文件: {config_path}")

    # 2. 验证 YAML 结构
    try:
        config: dict[str, Any] = load_config()
    except Exception as e:
        issues.append(f"❌  配置文件解析失败: {e}")
        return issues  # 配置文件坏了，停在这

    # 3. 检查 Provider 配置
    providers_config = config.get("providers", {})
    if not providers_config:
        issues.append("⚠️  配置文件中没有 providers 段，将使用环境变量回退模式")
        return issues

    # 4. 收集环境变量（.env 文件 + 系统环境变量）
    env: dict[str, str] = dict()
    for src in (Path.home() / ".openllm" / ".env", Path.cwd() / ".env"):
        file_env = load_env_file(src)
        for k, v in file_env.items():
            env.setdefault(k, v)
    # 系统环境变量优先
    import os as _os
    for k, v in _os.environ.items():
        env.setdefault(k, v)

    # 5. 逐一检查每个 Provider 的 API key
    all_have_keys = True
    for name, cfg in providers_config.items():
        has_key = bool(cfg.get("api_key", ""))
        env_key = cfg.get("api_key_env", "")
        if env_key:
            has_key = bool(env.get(env_key, ""))
        if has_key:
            issues.append(f"  ✅ {name}: API key 已配置")
        else:
            key_name = env_key or "直接设置的 api_key"
            issues.append(f"  ⚠️  {name}: 缺少 API key (期望 {key_name})")
            all_have_keys = False

    # 6. 检查 Combo 引用的 Provider 是否都存在
    combos_config = config.get("combos", {})
    if combos_config:
        configured_names = set(providers_config.keys())
        for combo_name, combo_cfg in combos_config.items():
            for member in combo_cfg.get("members", []):
                prov = member.get("provider", "")
                if prov and prov not in configured_names:
                    issues.append(f"  ⚠️  combo '{combo_name}' 引用了未配置的 provider '{prov}'")

    # 7. 检查环境变量 HOST/PORT 是否与 .env 冲突
    host_env = env.get("HOST", "")
    port_env = env.get("PORT", "")
    if host_env or port_env:
        issues.append(f"  📌 .env 中 HOST={host_env} PORT={port_env}，会作为默认值被 CLI --host/--port 覆盖")

    if not all_have_keys:
        issues.append("⚠️  部分 Provider 缺少 API key，启动后对应 Provider 将不可用")

    return issues


def main():
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()
