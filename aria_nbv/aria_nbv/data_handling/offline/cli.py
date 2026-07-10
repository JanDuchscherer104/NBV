"""CLI for building immutable VIN offline stores.

This module exposes the ``nbv-build-offline`` console script. It loads a
``VinOfflineWriterConfig`` TOML file, validates it through the normal
config-as-factory path, and runs `aria_nbv.data_handling.VinOfflineWriter`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from ...utils.cli_format import cli_console, key_value_panel
from ...utils.config_paths import resolve_config_toml_path
from ...utils.typer_cli import run_typer_app
from .writer import VinOfflineWriterConfig

_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Build an immutable VIN offline store from raw ASE/EFM snippets and oracle RRI labels.",
    pretty_exceptions_show_locals=False,
)


def main(argv: list[str] | None = None) -> None:
    """Run immutable VIN offline-store creation from a TOML config.

    Args:
        argv: Optional argument vector. Defaults to ``sys.argv[1:]``.
    """

    run_typer_app(app, list(sys.argv[1:] if argv is None else argv), prog_name="nbv-build-offline")


@app.command()
def build_offline_command(
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a VinOfflineWriterConfig TOML file."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Validate the TOML and print resolved paths without loading data or writing shards.",
        ),
    ] = False,
) -> None:
    """Run immutable VIN offline-store creation from a TOML config."""

    console = cli_console()
    config_path = resolve_config_toml_path(config_path)
    cfg = VinOfflineWriterConfig.from_toml(config_path)
    console.print(
        key_value_panel(
            "VIN Offline Build",
            [
                ("config", config_path),
                ("store", cfg.store.store_dir),
                ("dry run", dry_run),
            ],
        )
    )
    if dry_run:
        console.print("Dry run complete; no dataset, backbone, or writer was instantiated.")
        return
    manifest = cfg.setup_target().run()
    console.print(
        key_value_panel(
            "Wrote VIN Offline Store",
            [
                ("samples", manifest.stats.get("num_samples", 0)),
                ("shards", manifest.stats.get("num_shards", 0)),
                ("train", manifest.stats.get("num_train", 0)),
                ("val", manifest.stats.get("num_val", 0)),
            ],
        )
    )


__all__ = ["app", "main"]
