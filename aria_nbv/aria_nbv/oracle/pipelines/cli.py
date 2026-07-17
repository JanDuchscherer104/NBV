"""Build Oracle-labelled offline stores and target-RRI rollout campaigns.

This module provides an offline command that streams raw snippets through the Oracle VIN pipeline into
an immutable source store. Rollout commands read those rows, materialize
rollout-owned Zarr stores, and expose deterministic shard planning and status
reporting. Shard builds use temporary directories and validated promotion;
direct unsharded builds own their destination and never modify the VIN source.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any

import click
import typer

from ...rollouts.manifest import RolloutStoreInvocation
from ...rollouts.shard_manifest import load_rollout_shard_entry
from ...utils.cli_format import cli_console, key_value_panel
from ...utils.config_paths import resolve_config_toml_path
from ...utils.typer_cli import run_typer_app
from ..target_selection import ORACLE_TARGET_TASK_SOURCE
from .offline_vin import VinOfflineWriterConfig
from .rollout_dataset import RolloutDatasetWriterConfig
from .shards import run_rollout_shard, summarize_rollout_shard_campaign, write_rollout_shard_manifest_from_config

_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

build_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Build a standalone target-RRI rollout Zarr store from VIN offline rows.",
    pretty_exceptions_show_locals=False,
)
offline_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Build an immutable VIN offline store from raw snippets and Oracle RRI labels.",
    pretty_exceptions_show_locals=False,
)
plan_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Plan deterministic source-row rollout shard manifests from a writer TOML.",
    pretty_exceptions_show_locals=False,
)
status_app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Summarize succeeded, failed, incomplete, and missing rollout shards for one campaign.",
    pretty_exceptions_show_locals=False,
)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for building rollout stores or one rollout shard."""

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    run_typer_app(build_app, raw_argv, prog_name="nbv-build-rollouts", obj={"raw_argv": raw_argv})


def offline_main(argv: list[str] | None = None) -> None:
    """CLI entry point for building an immutable VIN offline store."""

    run_typer_app(
        offline_app,
        list(sys.argv[1:] if argv is None else argv),
        prog_name="nbv-build-offline",
    )


def plan_main(argv: list[str] | None = None) -> None:
    """CLI entry point for planning rollout source-row shards."""

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    run_typer_app(plan_app, raw_argv, prog_name="nbv-plan-rollout-shards", obj={"raw_argv": raw_argv})


def status_main(argv: list[str] | None = None) -> None:
    """CLI entry point for rollout shard campaign status reporting."""

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    run_typer_app(status_app, raw_argv, prog_name="nbv-status-rollout-shards", obj={"raw_argv": raw_argv})


@offline_app.command()
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
    """Build an immutable VIN offline store from a validated TOML config."""

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


@build_app.command()
def build_rollouts_command(
    ctx: typer.Context,
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a RolloutDatasetWriterConfig TOML file."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Validate the TOML and print resolved paths without loading data or writing Zarr."
        ),
    ] = False,
    shard_manifest: Annotated[
        Path | None,
        typer.Option("--shard-manifest", help="JSONL rollout shard manifest emitted by nbv-plan-rollout-shards."),
    ] = None,
    shard_id: Annotated[
        str | None,
        typer.Option("--shard-id", help="Rollout shard id to build, for example shard-000123 or a Slurm array id."),
    ] = None,
    output_tmp: Annotated[
        Path | None,
        typer.Option("--output-tmp", help="Temporary shard output directory used before atomic promotion."),
    ] = None,
    output_final: Annotated[
        Path | None,
        typer.Option("--output-final", help="Final shard output directory that receives _SUCCESS.json last."),
    ] = None,
) -> None:
    """Build a rollout Zarr store, or build one planned shard."""

    console = cli_console()
    config_path = resolve_config_toml_path(config_path)
    cfg = RolloutDatasetWriterConfig.from_toml(config_path)
    sampler_target_cap = cfg.oracle_target_task_sampler.max_targets_per_sample
    target_cap = (
        sampler_target_cap
        if cfg.max_targets_per_sample is None
        else min(cfg.max_targets_per_sample, sampler_target_cap)
    )
    console.print(
        key_value_panel(
            "Rollout Build",
            [
                ("config", config_path),
                ("source store", cfg.source.store.store_dir),
                ("rollout store", cfg.store.store_dir),
                ("target source", ORACLE_TARGET_TASK_SOURCE),
                ("target cap", target_cap),
                ("candidate budget", cfg.candidate_mixture.total_count),
                ("dry run", dry_run),
            ],
        )
    )
    shard_args = (shard_manifest, shard_id, output_tmp, output_final)
    if any(value is not None for value in shard_args) and not all(value is not None for value in shard_args):
        raise click.UsageError(
            "--shard-manifest, --shard-id, --output-tmp, and --output-final must be supplied together."
        )
    raw_argv = _raw_argv(ctx)
    if all(value is not None for value in shard_args):
        assert shard_manifest is not None
        assert shard_id is not None
        assert output_tmp is not None
        assert output_final is not None
        shard_entry = load_rollout_shard_entry(shard_manifest, shard_id)
        console.print(
            key_value_panel(
                "Rollout Shard",
                [
                    ("shard", shard_entry.shard_id),
                    ("rows", len(shard_entry.rows)),
                    ("tmp", output_tmp),
                    ("final", output_final),
                ],
            )
        )
        if dry_run:
            console.print("Dry run complete; shard manifest was loaded but no rollout writer was instantiated.")
            return
        shard_result = run_rollout_shard(
            cfg,
            shard_entry=shard_entry,
            output_tmp=output_tmp,
            output_final=output_final,
            invocation=RolloutStoreInvocation.from_cli(argv=["nbv-build-rollouts", *raw_argv], config_path=config_path),
        )
        if shard_result.skipped:
            console.print(f"Skipped completed rollout shard: {shard_result.final_dir}")
            return
        assert shard_result.store_result is not None
        result = shard_result.store_result
        console.print(
            key_value_panel(
                "Wrote Rollout Shard",
                [
                    ("rollouts", result.num_rollouts),
                    ("steps", result.num_steps),
                    ("candidates", result.num_candidates),
                    ("path", shard_result.final_dir),
                    ("success", shard_result.success_path),
                ],
            )
        )
        return
    if dry_run:
        console.print("Dry run complete; no VIN offline dataset or rollout writer was instantiated.")
        return
    result = cfg.setup_target().run(
        invocation=RolloutStoreInvocation.from_cli(argv=["nbv-build-rollouts", *raw_argv], config_path=config_path)
    )
    console.print(
        key_value_panel(
            "Wrote Rollout Zarr Store",
            [
                ("rollouts", result.num_rollouts),
                ("steps", result.num_steps),
                ("candidates", result.num_candidates),
                ("path", result.store_dir),
                ("manifest", result.manifest_path),
            ],
        )
    )


@plan_app.command()
def plan_rollout_shards_command(
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a RolloutDatasetWriterConfig TOML file."),
    ],
    output_manifest: Annotated[
        Path,
        typer.Option("--output-manifest", help="Destination JSONL shard manifest path."),
    ],
    rows_per_shard: Annotated[
        int,
        typer.Option("--rows-per-shard", min=1, help="Maximum number of VIN source rows owned by one shard."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan shards and print counts without writing the JSONL manifest."),
    ] = False,
) -> None:
    """Plan deterministic rollout shard entries from a writer config."""

    console = cli_console()
    config_path = resolve_config_toml_path(config_path)
    cfg = RolloutDatasetWriterConfig.from_toml(config_path)
    if dry_run:
        from .shards import plan_rollout_shards

        entries = plan_rollout_shards(cfg, rows_per_shard=rows_per_shard)
    else:
        entries = write_rollout_shard_manifest_from_config(
            cfg,
            manifest_path=output_manifest,
            rows_per_shard=rows_per_shard,
        )
    console.print(
        key_value_panel(
            "Planned Rollout Shards",
            [
                ("count", len(entries)),
                ("rows", sum(len(entry.rows) for entry in entries)),
                ("rows per shard", rows_per_shard),
                ("output", output_manifest),
                ("dry run", dry_run),
            ],
        )
    )
    if dry_run:
        console.print(f"Dry run complete; manifest was not written: {output_manifest}")
    else:
        console.print(f"Wrote rollout shard manifest: {output_manifest}")


@status_app.command()
def status_rollout_shards_command(
    shard_manifest: Annotated[
        Path,
        typer.Option("--shard-manifest", help="JSONL rollout shard manifest emitted by nbv-plan-rollout-shards."),
    ],
    final_root: Annotated[
        Path,
        typer.Option("--final-root", help="Directory containing final shard directories."),
    ],
    output_json: Annotated[
        Path | None,
        typer.Option("--output-json", help="Optional path for a machine-readable campaign status JSON file."),
    ] = None,
    require_complete: Annotated[
        bool,
        typer.Option("--require-complete", help="Exit with status 2 when any planned shard is not succeeded."),
    ] = False,
) -> None:
    """Report completion states for every shard in one manifest-driven campaign.

    A shard is successful only when its final store, owner sidecar, and success
    marker agree. ``--require-complete`` turns any failed, incomplete, or
    missing shard into process exit status 2 for schedulers and CI.
    """

    console = cli_console()
    status = summarize_rollout_shard_campaign(shard_manifest, final_root=final_root)
    counts = status.counts
    console.print(
        key_value_panel(
            "Rollout Shard Campaign",
            [
                ("total", len(status.shards)),
                ("succeeded", counts["succeeded"]),
                ("failed", counts["failed"]),
                ("incomplete", counts["incomplete"]),
                ("missing", counts["missing"]),
            ],
        )
    )
    problems = [shard for shard in status.shards if shard.status != "succeeded"]
    if problems:
        problem_ids = ", ".join(f"{shard.shard_id}:{shard.status}" for shard in problems[:20])
        suffix = "" if len(problems) <= 20 else f", ... +{len(problems) - 20} more"
        console.print(f"Problem shards: {problem_ids}{suffix}")
    if output_json is not None:
        from ...rollouts.manifest import manifest_json_bytes

        output_path = output_json.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(manifest_json_bytes(status.to_jsonable()))
        console.print(f"Wrote rollout shard campaign status JSON: {output_path}")
    if require_complete and problems:
        raise SystemExit(2)


def _raw_argv(ctx: typer.Context) -> list[str]:
    obj: Any = ctx.obj
    if isinstance(obj, dict):
        raw = obj.get("raw_argv")
        if isinstance(raw, list):
            return [str(item) for item in raw]
    return []


__all__ = [
    "build_app",
    "main",
    "offline_app",
    "offline_main",
    "plan_app",
    "plan_main",
    "status_app",
    "status_main",
]
