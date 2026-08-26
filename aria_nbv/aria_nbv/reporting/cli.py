"""Thin command-line composition for report recipe build and export."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .config import ScientificReportConfig
from .export import write_report_snapshot

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def report_cli() -> None:
    """Build and export immutable ARIA-NBV scientific reports."""


@app.command("build")
def build_report(
    config: Annotated[Path, typer.Option("--config", exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
) -> None:
    """Build a validated recipe once and export its immutable snapshot."""

    recipe = ScientificReportConfig.from_toml(config)
    recipe.validate_build_readiness()
    wandb_api = None
    if recipe.sources.wandb is not None:
        import wandb

        wandb_api = wandb.Api()
    snapshot = recipe.setup_target(wandb_api=wandb_api).build()
    receipt = write_report_snapshot(
        snapshot,
        output,
        width=recipe.export.width,
        height=recipe.export.height,
        scale=recipe.export.scale,
        two_dimensional_format=recipe.export.two_dimensional_format,
        webgl_format=recipe.export.webgl_format,
    )
    typer.echo(f"{receipt.destination} {receipt.manifest_sha256}")


def main() -> None:
    """Run the report CLI."""

    app()


__all__ = ["app", "build_report", "main", "report_cli"]
