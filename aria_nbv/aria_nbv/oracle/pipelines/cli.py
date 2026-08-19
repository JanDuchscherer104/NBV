"""Build Oracle-labelled offline stores and target-RRI rollout campaigns.

This module provides an offline command that streams raw snippets through the Oracle VIN pipeline into
an immutable source store. Rollout commands read those rows, materialize
rollout-owned Zarr stores, and expose deterministic shard planning and status
reporting. Shard builds use temporary directories and validated promotion;
direct unsharded builds own their destination and never modify the VIN source.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import click
import typer

from ...rollouts.manifest import RolloutStoreInvocation
from ...rollouts.shard_manifest import load_rollout_shard_entry, read_rollout_source_manifest
from ...utils.cli_format import cli_console, key_value_panel
from ...utils.config_paths import resolve_config_toml_path
from ...utils.fingerprints import stable_config_hash, stable_msgspec_hash
from ...utils.typer_cli import run_typer_app
from ..target_selection import ORACLE_TARGET_TASK_SOURCE
from .campaign import CampaignEvent, CampaignWorkerResult, CudaRolloutCampaignConfig
from .offline_vin import VinOfflineWriterConfig
from .rollout_dataset import RolloutDatasetWriterConfig
from .shards import (
    RolloutShardOwnershipConflictError,
    run_rollout_shard,
    summarize_rollout_shard_campaign,
    write_rollout_shard_manifest_from_config,
)

campaign_app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_show_locals=False,
    help="Plan and run CUDA rollout campaigns.",
)


def campaign_main(argv: list[str] | None = None) -> None:
    """Entry point for the reviewed CUDA campaign CLI."""
    raw = list(sys.argv[1:] if argv is None else argv)
    run_typer_app(campaign_app, raw, prog_name="nbv-rollout-campaign")


def _campaign(config_path: Path):
    return CudaRolloutCampaignConfig.from_toml(resolve_config_toml_path(config_path)).setup_target()


def _writer_config(campaign):
    path = campaign.config.writer_config_path
    if path is None:
        return None
    return RolloutDatasetWriterConfig.from_toml(resolve_config_toml_path(path))


def _validate_plan_digests(campaign, plan, writer_cfg) -> str:
    """Reject stale campaign or writer inputs before any progress is persisted."""
    has_config_hash = hasattr(plan, "config_hash")
    expected_config_hash = getattr(plan, "config_hash", "")
    config_payload = getattr(campaign.config, "model_dump_jsonable", None)
    current_config_hash = stable_msgspec_hash(config_payload()) if config_payload is not None else expected_config_hash
    if has_config_hash and expected_config_hash != current_config_hash:
        raise typer.BadParameter("campaign config hash does not match plan")
    current_writer_hash = stable_config_hash(writer_cfg) if writer_cfg is not None else ""
    has_writer_hash = hasattr(plan, "writer_config_hash")
    expected_writer_hash = getattr(plan, "writer_config_hash", "")
    if has_writer_hash and expected_writer_hash != current_writer_hash:
        raise typer.BadParameter("writer config hash does not match plan")
    return current_writer_hash


def _require_smoke_evidence(campaign, plan) -> dict[str, Any]:
    """Require the structured, validated smoke result before execution."""
    try:
        evidence = campaign.smoke_evidence(plan)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError, AttributeError) as exc:
        raise typer.BadParameter("current passing smoke evidence is required") from exc
    return evidence


@campaign_app.command("plan")
def campaign_plan(
    config_path: Annotated[Path, typer.Option("--config-path")],
    output_json: Annotated[Path | None, typer.Option("--output-json")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    source_manifest: Annotated[Path | None, typer.Option("--source-manifest")] = None,
) -> None:
    """Load the canonical campaign and render its typed configuration."""
    cfg = _campaign(config_path)
    campaign = cfg
    writer_cfg = _writer_config(campaign)
    try:
        campaign.preflight(
            nested_configs=(writer_cfg,) if writer_cfg is not None else (),
            writer_config_path=getattr(campaign.config, "writer_config_path", None),
        )
    except (RuntimeError, ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None
    if source_manifest is not None:
        raw = source_manifest.read_bytes()
        if writer_cfg is None:
            raise typer.BadParameter("campaign planning requires the canonical writer config")
        reviewed_manifest = read_rollout_source_manifest(source_manifest)
        canonical_manifest_path = getattr(writer_cfg, "source_manifest_path", None)
        if canonical_manifest_path is None:
            raise typer.BadParameter("canonical writer config requires source_manifest_path")
        canonical_manifest = read_rollout_source_manifest(canonical_manifest_path)
        if reviewed_manifest.to_jsonable() != canonical_manifest.to_jsonable():
            raise typer.BadParameter("selected source manifest does not match the canonical writer manifest")
        source_rows = campaign.audit_source_manifest(writer_cfg, reviewed_manifest)
        planned = campaign.plan(
            source_rows,
            source_manifest_hash=hashlib.sha256(raw).hexdigest(),
            writer_config_hash=stable_config_hash(writer_cfg) if writer_cfg is not None else "",
        )
        campaign.write_admission_audit(
            source_rows,
            source_manifest_hash=planned.source_manifest_hash,
            expected_hash=planned.admission_audit_hash,
        )
        campaign.write_plan(planned, output_json if output_json is not None else None)
        event_identity = {
            "campaign_id": campaign.config.campaign_id,
            "plan_hash": planned.plan_hash,
            "config_hash": planned.config_hash,
            "writer_config_hash": planned.writer_config_hash,
            "source_manifest_hash": planned.source_manifest_hash,
        }
        campaign.append_event(
            CampaignEvent("source_selection", timestamp=campaign.utc_now().isoformat(), **event_identity)
        )
        campaign.append_event(CampaignEvent("plan_ready", timestamp=campaign.utc_now().isoformat(), **event_identity))
        campaign.write_status(campaign.status(planned, stage="planned"))
        payload = planned.to_jsonable()
    else:
        payload = campaign.config.model_dump_jsonable()
    if output_json:
        output_json.write_text(json.dumps(payload, sort_keys=True, default=str, indent=2) + "\n")
    typer.echo(json.dumps(payload, sort_keys=True, default=str) if json_output or not output_json else str(output_json))


@campaign_app.command("preflight")
def campaign_preflight(config_path: Annotated[Path, typer.Option("--config-path")]) -> None:
    """Run the CUDA availability gate."""
    campaign = _campaign(config_path)
    writer_cfg = _writer_config(campaign)
    try:
        campaign.preflight(
            nested_configs=(writer_cfg,) if writer_cfg is not None else (),
            writer_config_path=getattr(campaign.config, "writer_config_path", None),
        )
    except (RuntimeError, ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from None
    typer.echo("cuda preflight passed")


@campaign_app.command("status")
def campaign_status(
    config_path: Annotated[Path, typer.Option("--config-path")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Print persisted typed campaign status."""
    cfg = _campaign(config_path)
    summary = cfg.progress_summary()
    counts = summary.get("counts", {})
    inferred_state = "completed_with_failures" if counts.get("failed", 0) else "running"
    payload = {
        "state": summary.get("state", inferred_state),
        "campaign_id": cfg.config.campaign_id,
        "counts": counts,
        "plan_hash": summary.get("plan_hash", ""),
        "updated_at": summary.get("updated_at", ""),
        "current_work_unit": summary.get("current_work_unit"),
        "current_target_id": summary.get("current_target_id"),
        "current_profile": summary.get("current_profile"),
        "current_stage": summary.get("current_stage"),
        "elapsed_seconds": summary.get("elapsed_seconds", 0.0),
        "latest_failure_reason": summary.get("latest_failure_reason"),
        "active_pid": summary.get("active_pid"),
        "active_process_group": summary.get("active_process_group"),
        "validated_artifacts": summary.get("validated_artifacts", []),
    }
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(
            "\n".join(
                (
                    f"campaign: {payload['campaign_id']}",
                    f"state: {payload['state']}",
                    f"stage: {payload['current_stage'] or '-'}",
                    f"target/profile: {payload['current_target_id'] or payload['current_work_unit'] or '-'}/{payload['current_profile'] or '-'}",
                    f"elapsed_seconds: {payload['elapsed_seconds']}",
                    f"worker_pid/pgid: {payload['active_pid'] or '-'}/{payload['active_process_group'] or '-'}",
                    f"counts: {json.dumps(payload['counts'], sort_keys=True)}",
                    f"latest_failure_reason: {payload['latest_failure_reason'] or '-'}",
                )
            )
        )


@campaign_app.command("acknowledge-stale-claim")
def campaign_acknowledge_stale_claim(
    claim_path: Annotated[Path, typer.Option("--claim-path")],
    claim_hash: Annotated[str, typer.Option("--claim-hash")],
) -> None:
    """Archive one explicitly identified stale claim for safe reacquisition."""
    from .campaign import CudaRolloutCampaign

    if not claim_path.exists() or not CudaRolloutCampaign.claim_is_stale(claim_path):
        raise typer.BadParameter("claim is missing or its owner is still live")
    try:
        archive = CudaRolloutCampaign.acknowledge_stale_claim(claim_path, claim_hash)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(archive))


@campaign_app.command("smoke")
def campaign_smoke(config_path: Annotated[Path, typer.Option("--config-path")]) -> None:
    """Validate CUDA preflight before a smoke worker is launched."""
    campaign = _campaign(config_path)
    writer_cfg = _writer_config(campaign)
    plan_path = campaign.config.output_root / "plan.json"
    if not plan_path.exists():
        raise typer.BadParameter("plan.json is required before smoke")
    campaign.preflight(
        nested_configs=(writer_cfg,) if writer_cfg is not None else (),
        plan_path=plan_path,
        writer_config_path=getattr(campaign.config, "writer_config_path", None),
    )
    plan = campaign.load_plan(plan_path)
    _validate_plan_digests(campaign, plan, writer_cfg)
    campaign.smoke(plan, config_path=resolve_config_toml_path(config_path), plan_path=plan_path)
    typer.echo("smoke preflight passed")


@campaign_app.command("run")
def campaign_run(
    config_path: Annotated[Path, typer.Option("--config-path")],
    plan_path: Annotated[Path, typer.Option("--plan-path")],
    max_new_units: Annotated[int | None, typer.Option("--max-new-units", min=1, max=100)] = None,
    time_budget_minutes: Annotated[float | None, typer.Option("--time-budget-minutes", min=0.000001)] = None,
    free_disk_floor_gb: Annotated[float | None, typer.Option("--free-disk-floor-gb", min=0.000001)] = None,
) -> None:
    """Start a foreground campaign after preflight (planning is supplied by API callers)."""
    campaign = _campaign(config_path)
    writer_cfg = _writer_config(campaign)
    plan = campaign.load_plan(plan_path)
    writer_hash = _validate_plan_digests(campaign, plan, writer_cfg)
    _require_smoke_evidence(campaign, plan)
    campaign.run(
        plan,
        plan_path=plan_path,
        config_path=config_path,
        current_writer_config_hash=writer_hash,
        max_new_units=max_new_units,
        time_budget_seconds=time_budget_minutes * 60 if time_budget_minutes else None,
        free_disk_floor_gb=free_disk_floor_gb,
    )
    typer.echo("campaign run complete")


@campaign_app.command("resume")
def campaign_resume(
    config_path: Annotated[Path, typer.Option("--config-path")],
    plan_path: Annotated[Path, typer.Option("--plan-path")],
    max_new_units: Annotated[int | None, typer.Option("--max-new-units", min=1, max=100)] = None,
    time_budget_minutes: Annotated[float | None, typer.Option("--time-budget-minutes", min=0.000001)] = None,
    free_disk_floor_gb: Annotated[float | None, typer.Option("--free-disk-floor-gb", min=0.000001)] = None,
) -> None:
    """Resume a campaign through the Python campaign API."""
    campaign = _campaign(config_path)
    writer_cfg = _writer_config(campaign)
    plan = campaign.load_plan(plan_path)
    writer_hash = _validate_plan_digests(campaign, plan, writer_cfg)
    _require_smoke_evidence(campaign, plan)
    campaign.run(
        plan,
        plan_path=plan_path,
        config_path=config_path,
        current_writer_config_hash=writer_hash,
        max_new_units=max_new_units,
        time_budget_seconds=time_budget_minutes * 60 if time_budget_minutes else None,
        free_disk_floor_gb=free_disk_floor_gb,
    )
    typer.echo("campaign resume complete")


@campaign_app.command("worker")
def campaign_worker(
    config_path: Annotated[Path, typer.Option("--config-path")],
    plan_hash: Annotated[str, typer.Option("--plan-hash")],
    work_unit_hash: Annotated[str, typer.Option("--work-unit-hash")],
    plan_path: Annotated[Path, typer.Option("--plan-path")],
    writer_config_path: Annotated[Path | None, typer.Option("--writer-config-path")] = None,
) -> None:
    """Validate internal worker identity arguments and dispatch one unit."""
    if not plan_hash or not work_unit_hash:
        raise typer.BadParameter("plan hash and work-unit hash are required")
    campaign = _campaign(config_path)
    plan = campaign.load_plan(plan_path)
    if plan.plan_hash != plan_hash:
        raise typer.BadParameter("plan hash mismatch")
    unit = next((item for item in plan.work_units if item.work_unit_hash == work_unit_hash), None)
    if unit is None:
        raise typer.BadParameter("work-unit hash is not present in plan")
    writer_path = writer_config_path or campaign.config.writer_config_path
    if writer_path is None:
        raise typer.BadParameter(
            "writer config path is required; set writer_config_path in campaign TOML or pass --writer-config-path"
        )
    try:
        writer_cfg = RolloutDatasetWriterConfig.from_toml(resolve_config_toml_path(writer_path))
    except Exception as exc:
        raise typer.BadParameter(f"writer config is required for worker: {exc}") from exc
    _validate_plan_digests(campaign, plan, writer_cfg)
    entry = campaign.shard_entry_for_unit(plan, unit)
    from dataclasses import replace

    writer_cfg, entry = campaign.adapt_work_unit(
        unit,
        writer_config=writer_cfg,
        shard_entry=entry,
        plan_hash=plan.plan_hash,
        profile_hash=unit.profile_hash,
    )
    entry = replace(entry, writer_config_hash=stable_config_hash(writer_cfg))
    # Validate every nested source/candidate/renderer/scorer/depth device
    # before the shard owner creates its staging directory.
    campaign.preflight(
        nested_configs=(writer_cfg,),
        writer_config_path=writer_path,
        plan_path=plan_path,
    )
    try:
        result = run_rollout_shard(
            writer_cfg,
            shard_entry=entry,
            output_tmp=campaign.config.output_root / "tmp" / unit.work_unit_hash,
            output_final=campaign.config.output_root / "shards" / unit.work_unit_hash,
        )
    except RolloutShardOwnershipConflictError as exc:
        conflict = CampaignWorkerResult(
            campaign_id=plan.campaign_id,
            config_hash=plan.config_hash,
            plan_hash=plan.plan_hash,
            work_unit_hash=unit.work_unit_hash,
            source_identity_hash=unit.source_identity_hash,
            target_id=unit.target_id,
            profile=unit.profile,
            profile_hash=unit.profile_hash,
            generation_revision_hash=unit.generation_revision_hash,
            outcome="conflicted",
            reason=str(exc),
            leaf_evidence={
                "error_type": type(exc).__name__,
                "output_tmp": exc.output_tmp.as_posix(),
                "output_final": exc.output_final.as_posix(),
            },
        )
        typer.echo(json.dumps(conflict.to_jsonable(), sort_keys=True))
        return
    typer.echo(
        json.dumps(
            {
                "outcome": "skipped" if getattr(result, "skipped", False) else getattr(result, "outcome", "succeeded"),
                "reason": getattr(result, "reason", None),
                "validated": getattr(result, "outcome", "succeeded") in {"succeeded", "skipped"},
                "plan_hash": plan_hash,
                "work_unit_hash": unit.work_unit_hash,
                "campaign_id": getattr(campaign.config, "campaign_id", getattr(plan, "campaign_id", "")),
                "config_hash": plan.config_hash,
                "source_identity_hash": getattr(unit, "source_identity_hash", ""),
                "target_id": getattr(unit, "target_id", ""),
                "profile": getattr(unit, "profile", ""),
                "profile_hash": unit.profile_hash,
                "generation_revision_hash": getattr(unit, "generation_revision_hash", ""),
                "leaf_evidence": (
                    {"success_path": str(result.success_path), "owner_path": str(result.owner_path)}
                    if getattr(result, "outcome", "succeeded") in {"succeeded", "skipped"}
                    else None
                ),
            },
            sort_keys=True,
        )
    )


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


def _internal_preflight(
    stage: str,
    *,
    plan_path: Path | None = None,
    writer_config_path: Path | None = None,
    expected_scene_count: int | None = None,
) -> int:
    """Run one named repository-owned preflight subprocess mode."""
    if stage == "cuda-rasterizer-preflight":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        from pytorch3d.renderer import MeshRasterizer, PerspectiveCameras, RasterizationSettings
        from pytorch3d.structures import Meshes

        device = torch.device("cuda:0")
        verts = torch.tensor([[-0.5, -0.5, 2.0], [0.5, -0.5, 2.0], [0.0, 0.5, 2.0]], device=device)
        faces = torch.tensor([[0, 1, 2]], dtype=torch.int64, device=device)
        fragments = MeshRasterizer(
            cameras=PerspectiveCameras(device=device),
            raster_settings=RasterizationSettings(image_size=2, blur_radius=0.0, faces_per_pixel=1),
        )(Meshes([verts], [faces]))
        if fragments.pix_to_face.numel() == 0:
            raise RuntimeError("rasterizer returned no pixels")
    elif stage == "source-target-preflight":
        # Importing and validating the canonical target-task source verifies
        # source/target protocol wiring in the child process.
        from ...targets.protocol import TargetInputProtocol
        from ..target_selection import ORACLE_TARGET_TASK_SOURCE

        if not ORACLE_TARGET_TASK_SOURCE:
            raise RuntimeError("source-target task source is empty")
        if TargetInputProtocol.V1_OBSERVED.value != "v1_observed":
            raise RuntimeError("observed target protocol contract drifted")
        if writer_config_path is not None:
            writer_path = resolve_config_toml_path(writer_config_path)
            writer_cfg = RolloutDatasetWriterConfig.from_toml(writer_path)
            if writer_cfg.source_manifest_path is None:
                raise RuntimeError("source-target preflight requires a canonical source manifest")
            from ...rollouts.shard_manifest import read_rollout_source_manifest

            manifest_path = Path(writer_cfg.source_manifest_path)
            manifest = read_rollout_source_manifest(manifest_path)
            if not manifest.rows:
                raise RuntimeError("source-target preflight found no source rows")
            if expected_scene_count is not None:
                scene_count = len({row.scene_id for row in manifest.rows})
                if scene_count != expected_scene_count:
                    raise RuntimeError(
                        f"source-target preflight requires {expected_scene_count} scenes; found {scene_count}"
                    )
            if not Path(manifest.source_store_dir).exists():
                raise RuntimeError("source-target preflight source store is missing")
            if plan_path is not None:
                from .campaign import CampaignPlan

                CampaignPlan.from_jsonable(json.loads(Path(plan_path).read_text(encoding="utf-8")))
    else:
        raise ValueError(f"unknown internal preflight stage: {stage}")
    return 0


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


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--campaign":
        campaign_main(sys.argv[2:])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--internal-preflight":
        stage = sys.argv[2]
        plan_arg = Path(sys.argv[sys.argv.index("--plan-path") + 1]) if "--plan-path" in sys.argv else None
        writer_arg = (
            Path(sys.argv[sys.argv.index("--writer-config-path") + 1]) if "--writer-config-path" in sys.argv else None
        )
        expected_arg = (
            int(sys.argv[sys.argv.index("--expected-scene-count") + 1])
            if "--expected-scene-count" in sys.argv
            else None
        )
        raise SystemExit(
            _internal_preflight(
                stage,
                plan_path=plan_arg,
                writer_config_path=writer_arg,
                expected_scene_count=expected_arg,
            )
        )
    else:
        main()
