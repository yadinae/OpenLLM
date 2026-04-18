"""CLI entry point for OpenLLM"""

import sys
import logging
import asyncio
import typer
import uvicorn
from pathlib import Path
from typing import Optional
from src.registry import get_registry
from src.scorer import get_scorer

cli = typer.Typer(help="OpenLLM CLI")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@cli.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Server host"),
    port: int = typer.Option(8000, help="Server port"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    config: Optional[str] = typer.Option(None, help="Config file path"),
):
    """Start OpenLLM server"""
    typer.echo(f"Starting OpenLLM server at {host}:{port}")

    if config:
        import os

        os.environ["OPENLLM_CONFIG"] = config

    from src.server import run

    run(host=host, port=port, reload=reload)


@cli.command()
def status():
    """Show OpenLLM status"""
    registry = get_registry()
    scorer = get_scorer()

    models = registry.list_models()
    enabled = sum(1 for m in models if m.enabled)

    typer.echo("OpenLLM Status")
    typer.echo(f"  Total models: {len(models)}")
    typer.echo(f"  Enabled: {enabled}")

    ranked = scorer.get_ranked_models()
    if ranked:
        typer.echo("\nTop models:")
        for s in ranked[:5]:
            typer.echo(f"  {s.model_name}: {s.total_score:.3f}")


@cli.command("models")
def models_cmd(
    list_models: bool = typer.Option(True, "--list", help="List models"),
):
    """List available models"""
    registry = get_registry()
    models = registry.list_models()

    if not models:
        typer.echo("No models configured")
        return

    typer.echo("Available models:")
    for m in models:
        status = "✓" if m.enabled else "✗"
        typer.echo(f"  [{status}] {m.name} ({m.protocol})")


@cli.command("discover")
def discover_cmd():
    """Discover available models from providers"""
    registry = get_registry()
    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

    if not config_path.exists():
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1)

    registry.load_from_yaml(config_path)

    async def run():
        discovered = await registry.discover_models(config_path)

        if not discovered:
            typer.echo("No new models discovered")
            return

        typer.echo(f"Discovered {len(discovered)} new models:")
        for m in discovered:
            typer.echo(f"  - {m.name} ({m.protocol})")

        typer.echo(f"\nModels saved to {config_path} (enabled: false)")

    asyncio.run(run())


@cli.command()
def score(
    refresh: bool = typer.Option(False, "--refresh", help="Refresh scores"),
):
    """Show model scores"""
    scorer = get_scorer()
    ranked = scorer.get_ranked_models()

    if not ranked:
        typer.echo("No model scores available")
        return

    typer.echo("Model scores:")
    for s in ranked:
        typer.echo(
            f"  {s.model_name}: "
            f"total={s.total_score:.3f} "
            f"quality={s.quality_score:.3f} "
            f"speed={s.speed_score:.3f}"
        )


@cli.command()
def config(
    show: bool = typer.Option(True, "--show", help="Show config"),
):
    """Manage configuration"""
    registry = get_registry()
    models = registry.list_models()

    typer.echo("Current configuration:")
    for m in models:
        typer.echo(f"\nModel: {m.name}")
        typer.echo(f"  Protocol: {m.protocol}")
        typer.echo(f"  Endpoint: {m.endpoint}")
        typer.echo(f"  RPM: {m.rpm}")
        typer.echo(f"  TPM: {m.tpm}")


@cli.command("test")
def test_cmd(
    all_models: bool = typer.Option(False, "--all", help="Test all models including disabled"),
):
    """Test configured models"""
    from src.tester import ModelTester

    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

    async def run():
        registry = get_registry()
        registry.load_from_yaml(config_path)

        if not config_path.exists():
            typer.echo(f"Config file not found: {config_path}")
            raise typer.Exit(1)

        tester = ModelTester(registry)

        mode = "all" if all_models else "enabled"
        typer.echo(f"Testing {mode} models...")
        results = await tester.test_all_models(enabled_only=not all_models)

        available_count = 0
        for r in results:
            if r.available:
                available_count += 1
                caps = ", ".join(r.capabilities) if r.capabilities else "none"
                size = f" ({r.model_size})" if r.model_size else ""
                typer.echo(
                    f"  ✅ {r.model_name}{size}: "
                    f"available ({r.response_time_ms:.0f}ms), "
                    f"context: {r.max_context_length}, "
                    f"capabilities: [{caps}]"
                )
            else:
                error_msg = f" - {r.error}" if r.error else ""
                typer.echo(f"  ❌ {r.model_name}: unavailable{error_msg}")

        typer.echo(f"\nResults: {available_count}/{len(results)} models available")

    asyncio.run(run())


@cli.command("freeride")
def freeride_cmd(
    enable: bool = typer.Option(False, "--enable", help="Enable FreeRide mode"),
    disable: bool = typer.Option(False, "--disable", help="Disable FreeRide mode"),
    status: bool = typer.Option(False, "--status", help="Show FreeRide status"),
    providers: str = typer.Option("", "--providers", help="Comma-separated providers"),
):
    """Manage FreeRide mode for token freedom"""
    from src.freeride import FreeRideManager

    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

    async def run():
        registry = get_registry()
        registry.load_from_yaml(config_path)

        freeride = FreeRideManager(registry)
        freeride.load_config(config_path)

        if enable:
            selected = [p.strip() for p in providers.split(",")] if providers else None
            added = await freeride.enable(selected)
            if added:
                typer.echo(f"FreeRide enabled! Added {len(added)} free models:")
                for m in added:
                    typer.echo(f"  - {m.name}")
            else:
                typer.echo("No models added. Check API keys in .env")

        elif disable:
            freeride.disable()
            typer.echo("FreeRide disabled - free models removed")

        elif status:
            st = freeride.get_status()
            typer.echo(f"FreeRide Status:")
            typer.echo(f"  Configured Providers: {', '.join(st['configured_providers'])}")
            typer.echo(
                f"  Available Providers: {', '.join(st['available_providers']) if st['available_providers'] else 'None'}"
            )
            typer.echo(f"  Free Models: {st['free_models_count']}")

        else:
            typer.echo("Use --enable, --disable, or --status")

    asyncio.run(run())


@cli.command("provider")
def provider_cmd(
    interactive: bool = typer.Option(True, "-i", "--interactive", help="Interactive mode"),
    add: bool = typer.Option(False, "--add", help="Add a new provider"),
    name: str = typer.Option("", "--name", help="Provider name"),
    endpoint: str = typer.Option("", "--endpoint", help="Provider API endpoint"),
    api_key: str = typer.Option("", "--api-key", help="API key"),
    protocol: str = typer.Option(
        "openai", "--protocol", help="Protocol (openai/ollama/anthropic/rest)"
    ),
    discover: bool = typer.Option(
        True, "--discover/--no-discover", help="Discover models after adding"
    ),
):
    """Manage custom providers"""
    from src.adapters.base import create_adapter
    from src.tester import ModelTester
    import os
    import yaml

    config_path = Path(__file__).parent.parent / "config" / "models.yaml"

    def ask(prompt: str, default: str = "") -> str:
        value = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
        return value if value else default

    async def run():
        if interactive:
            typer.echo("=== OpenLLM Provider Setup ===\n")

            provider_name = ask("Provider name (e.g., myprovider)", name)
            if not provider_name:
                typer.echo("Error: Provider name is required")
                return

            provider_endpoint = ask("API endpoint URL", endpoint)
            if not provider_endpoint:
                typer.echo("Error: API endpoint is required")
                return

            api_key_value = api_key or os.environ.get(f"{provider_name.upper()}_API_KEY", "")
            if not api_key_value:
                api_key_value = ask(
                    f"API key (optional, can set {provider_name.upper()}_API_KEY env)", ""
                )

            provider_protocol = ask("Protocol (openai/ollama/anthropic/rest)", protocol)

            typer.echo(f"\nDiscovering models from {provider_name}...")

            try:
                api_key_final = api_key_value or os.environ.get(
                    f"{provider_name.upper()}_API_KEY", ""
                )
                if not api_key_final:
                    typer.echo("Error: API key required for discovery")
                    return

                adapter_config = type(
                    "AdapterConfig",
                    (),
                    {
                        "model": provider_name,
                        "protocol": provider_protocol,
                        "endpoint": provider_endpoint,
                        "api_key": api_key_final,
                    },
                )()

                adapter = create_adapter(provider_protocol, adapter_config)
                model_infos = await adapter.list_available_models()
                await adapter.close()

                if not model_infos:
                    typer.echo("No models discovered")
                    return

                typer.echo(f"\nDiscovered {len(model_infos)} models:")
                for i, mi in enumerate(model_infos, 1):
                    typer.echo(f"  {i}. {mi.id}")

                selection = ask("\nSelect models (comma-separated numbers or 'all')", "all")

                if selection.lower() == "all":
                    selected = model_infos
                else:
                    selected_indices = [int(x.strip()) - 1 for x in selection.split(",")]
                    selected = [
                        model_infos[i] for i in selected_indices if 0 <= i < len(model_infos)
                    ]

                if not selected:
                    typer.echo("No models selected")
                    return

                with open(config_path) as f:
                    data = yaml.safe_load(f) or {}
                    if "models" not in data:
                        data["models"] = []

                existing = [m.get("name") for m in data.get("models", [])]

                for mi in selected:
                    if mi.id not in existing:
                        config = {
                            "name": mi.id,
                            "protocol": provider_protocol,
                            "endpoint": provider_endpoint,
                            "api_key": f"${{{provider_name.upper()}_API_KEY}}",
                            "enabled": True,
                            "rpm": 30,
                            "tpm": 15000,
                            "max_context_length": 128000,
                            "capabilities": ["text", "coding"],
                        }
                        data["models"].append(config)
                        typer.echo(f"  Added: {mi.id}")
                    else:
                        typer.echo(f"  Already exists: {mi.id}")

                with open(config_path, "w") as f:
                    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

                typer.echo(f"\nDone! Added {len(selected)} models to config/models.yaml")

            except Exception as e:
                typer.echo(f"Error: {e}")

        elif add:
            try:
                adapter = create_adapter(protocol, adapter_config)
                model_infos = await adapter.list_available_models()

                new_models = []
                for mi in model_infos:
                    if mi.id not in existing and mi.id != model_name:
                        new_config = config.copy()
                        new_config["name"] = mi.id
                        data["models"].append(new_config)
                        new_models.append(mi.id)

                if new_models:
                    with open(config_path, "w") as f:
                        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
                    typer.echo(f"Discovered {len(new_models)} models:")
                    for m in new_models:
                        typer.echo(f"  - {m}")
                else:
                    typer.echo("No new models discovered")

                await adapter.close()
            except Exception as e:
                typer.echo(f"Discover failed: {e}")

        else:
            typer.echo(
                "Use --add --name <name> --endpoint <url> [--api-key <key>] [--protocol <protocol>]"
            )

    asyncio.run(run())


def main():
    cli()


if __name__ == "__main__":
    main()
