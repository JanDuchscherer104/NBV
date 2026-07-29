"""Operator CLIs for planning, running, and inspecting local rollout campaigns."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import click
import typer

from ...rollouts.collection import RolloutCollection
from ...utils.cli_format import cli_console, key_value_panel
from ...utils.config_paths import resolve_config_toml_path
from ...utils.typer_cli import run_typer_app
from .campaign import RolloutCampaignConfig
from .root_selection import discover_ase_root_inventory

_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

plan_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Plan deterministic local ASE rollout roots and profile assignments.",
    pretty_exceptions_show_locals=False,
)
run_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Run or resume bounded immutable rollout-campaign work units.",
    pretty_exceptions_show_locals=False,
)
status_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Inspect durable rollout-campaign and collection status.",
    pretty_exceptions_show_locals=False,
)


def plan_main(argv: list[str] | None = None) -> None:
    """CLI entry point for deterministic campaign planning."""

    run_typer_app(plan_app, list(sys.argv[1:] if argv is None else argv), prog_name="nbv-plan-rollout-campaign")


def run_main(argv: list[str] | None = None) -> None:
    """CLI entry point for bounded local campaign execution."""

    run_typer_app(run_app, list(sys.argv[1:] if argv is None else argv), prog_name="nbv-run-rollout-campaign")


def status_main(argv: list[str] | None = None) -> None:
    """CLI entry point for campaign and collection status inspection."""

    run_typer_app(
        status_app,
        list(sys.argv[1:] if argv is None else argv),
        prog_name="nbv-status-rollout-campaign",
    )


@plan_app.command()
def plan_campaign_command(
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a RolloutCampaignConfig TOML file."),
    ],
    output_json: Annotated[
        Path | None,
        typer.Option("--output-json", help="Optional machine-readable plan summary."),
    ] = None,
) -> None:
    """Validate the central TOML and print exact scene/profile work counts."""

    config_path = resolve_config_toml_path(config_path)
    config = RolloutCampaignConfig.from_toml(config_path)
    inventory = discover_ase_root_inventory(
        ase_efm_dir=config.ase_efm_dir,
        ase_meshes_dir=config.ase_meshes_dir,
        seed=config.seed,
        expected_scene_count=config.expected_scene_count,
    )
    campaign = config.setup_target()
    assignments = campaign.planned_profiles_by_scene(inventory)
    payload = {
        "campaign_id": config.campaign_id,
        "config": config_path.as_posix(),
        "scenes": len(inventory.scenes),
        "root_candidates": sum(len(scene.candidates) for scene in inventory.scenes),
        "selected_roots": len(inventory.selected_sample_keys),
        "scene_profile_shards": sum(len(profiles) for profiles in assignments.values()),
        "paired_panel_scenes": len(campaign.paired_panel_scene_ids(inventory)),
        "profiles": {name: sum(name in profiles for profiles in assignments.values()) for name in config.profiles},
        "max_new_shards": config.runtime.max_new_shards,
        "stop_after_minutes": config.runtime.stop_after_minutes,
        "keep_free_disk_gib": config.runtime.keep_free_disk_gib,
        "max_failed_units": config.runtime.max_failed_units,
    }
    console = cli_console()
    console.print(
        key_value_panel(
            "Local Rollout Campaign Plan",
            [
                ("campaign", payload["campaign_id"]),
                ("scenes / roots", f"{payload['scenes']} / {payload['selected_roots']}"),
                ("profile shards", payload["scene_profile_shards"]),
                ("candidate profiles", len(config.profiles)),
                ("collection", config.collection_dir),
                ("output", config.output_root),
            ],
        )
    )
    if output_json is not None:
        resolved = output_json.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"Wrote campaign plan summary: {resolved}")


@run_app.command()
def run_campaign_command(
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a RolloutCampaignConfig TOML file."),
    ],
    max_new_shards: Annotated[
        int | None,
        typer.Option("--max-new-shards", min=1, help="Operational override for this invocation only."),
    ] = None,
    stop_after_minutes: Annotated[
        float | None,
        typer.Option("--stop-after-minutes", min=0.01, help="Operational wall-clock override for this invocation."),
    ] = None,
) -> None:
    """Run source/reserve and rollout units, stopping only between immutable units."""

    config_path = resolve_config_toml_path(config_path)
    config = RolloutCampaignConfig.from_toml(config_path)
    if max_new_shards is not None or stop_after_minutes is not None:
        updates: dict[str, int | float] = {}
        if max_new_shards is not None:
            updates["max_new_shards"] = max_new_shards
        if stop_after_minutes is not None:
            updates["stop_after_minutes"] = stop_after_minutes
        config.runtime = config.runtime.model_copy(update=updates)
    console = cli_console()
    console.print(
        key_value_panel(
            "Local Rollout Campaign Run",
            [
                ("campaign", config.campaign_id),
                ("config", config_path),
                ("max new shards", config.runtime.max_new_shards),
                ("time limit min", config.runtime.stop_after_minutes),
                ("free disk floor GiB", config.runtime.keep_free_disk_gib),
            ],
        )
    )
    result = config.setup_target().run()
    console.print(
        key_value_panel(
            "Campaign Invocation Result",
            [
                ("reason", result.reason),
                ("new shards", result.new_shards),
                ("skipped shards", result.skipped_shards),
                ("failed shards", result.failed_shards),
                ("failed scenes", result.failed_scenes),
                ("status", result.status_path),
                ("progress", result.progress_path),
            ],
        )
    )
    if result.failed_shards or result.failed_scenes:
        raise click.ClickException(
            "Campaign invocation incomplete: "
            f"failed_shards={result.failed_shards}, failed_scenes={result.failed_scenes}."
        )


@status_app.command()
def status_campaign_command(
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a RolloutCampaignConfig TOML file."),
    ],
    require_valid_collection: Annotated[
        bool,
        typer.Option("--require-valid-collection", help="Exit nonzero when the collection does not validate."),
    ] = False,
) -> None:
    """Print the latest durable campaign events and collection validation."""

    config_path = resolve_config_toml_path(config_path)
    config = RolloutCampaignConfig.from_toml(config_path)
    try:
        status = json.loads(config.status_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        status = {"state": "not_started", "event_counts": {}}
    validation = RolloutCollection(config.collection_dir).validate()
    console = cli_console()
    console.print(
        key_value_panel(
            "Local Rollout Campaign Status",
            [
                ("campaign", config.campaign_id),
                ("state / reason", status.get("reason", status.get("state", "unknown"))),
                ("events", json.dumps(status.get("event_counts", {}), sort_keys=True)),
                ("collection valid", validation.ok),
                ("collection shards", validation.num_shards),
                ("collection counts", json.dumps(validation.counts, sort_keys=True)),
                ("status path", config.status_path),
            ],
        )
    )
    if require_valid_collection and not validation.ok:
        raise click.ClickException("Rollout collection validation failed: " + "; ".join(validation.errors))


__all__ = ["plan_main", "run_main", "status_main"]
