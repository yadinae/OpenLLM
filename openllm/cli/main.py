"""CLI entry point for OpenLLM"""

import sys
import logging
import asyncio
import typer
import uvicorn
from pathlib import Path
from typing import Optional
from openllm.src.registry import get_registry
from openllm.src.scorer import get_scorer

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

    from openllm.src.server import run

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


def main():
    cli()


if __name__ == "__main__":
    main()
