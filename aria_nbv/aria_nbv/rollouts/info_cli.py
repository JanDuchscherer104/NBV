"""Inspect standalone rollout manifests, tables, and replay readiness.

This module provides a CLI that reads stores through
:class:`RolloutZarrStoreReader`, which opens Zarr
payloads read-only. Optional validation checks normalized row links, action and
label masks, provenance, and the derived finite-candidate ``Q_H`` view without
mutating either the rollout store or its immutable VIN source cache.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict, cast

import numpy as np
import typer

from ..data_handling.identifiers import compact_ase_atek_identifiers
from ..utils.cli_format import cli_console, counts_table, distribution_table, key_value_panel
from ..utils.typer_cli import run_typer_app
from .candidate_benchmark import benchmark_binding_from_reader, candidate_family_preflight_from_reader
from .inspection import build_compact_statistics, runtime_storage_statistics
from .reporting import (
    THESIS_REPORT_BUNDLE_ROLE,
    THESIS_REPORT_BUNDLE_VERSION,
    build_thesis_report_frames,
    write_thesis_report_bundle,
)
from .zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION, RolloutZarrStoreConfig, RolloutZarrStoreReader

_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Inspect rollout Zarr metadata, validation status, and compact rollout statistics.",
    pretty_exceptions_show_locals=False,
)


class _RewardSignalPayload(TypedDict):
    """Finite target-root-gain summary used by rollout preflight."""

    finite_count: int
    mean: float | None
    std: float | None
    min: float | None
    max: float | None


def main(argv: list[str] | None = None) -> None:
    """Run rollout-store metadata inspection.

    Args:
        argv: Optional argument vector. Defaults to ``sys.argv[1:]``.
    """

    run_typer_app(app, list(sys.argv[1:] if argv is None else argv), prog_name="nbv-rollouts-info")


@app.command()
def info_command(
    store: Annotated[Path, typer.Option("--store", help="Path or cache artifact name for a rollouts.zarr store.")],
    json_output: Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")] = False,
    validate: Annotated[
        bool,
        typer.Option("--validate", help="Run full Zarr table validation after reading the top-level manifest."),
    ] = False,
    stats: Annotated[
        bool,
        typer.Option("--stats", help="Read compact rollout arrays and print candidate, policy, and path statistics."),
    ] = False,
    preflight: Annotated[
        bool,
        typer.Option("--preflight", help="Run rollout-store go/no-go preflight checks."),
    ] = False,
    profile: Annotated[
        str,
        typer.Option("--profile", help="Preflight strictness profile: smoke or production."),
    ] = "smoke",
    random_index: Annotated[
        bool,
        typer.Option("--random-index", help="Print a deterministic random zero-based rollout row index."),
    ] = False,
    min_horizon: Annotated[
        int,
        typer.Option("--min-horizon", min=0, help="Minimum rollout horizon required by --random-index."),
    ] = 2,
    seed: Annotated[int | None, typer.Option("--seed", help="Seed for deterministic --random-index selection.")] = None,
    thesis_bundle_output: Annotated[
        Path | None,
        typer.Option(
            "--thesis-bundle-output",
            help="Write a strict thesis evidence JSON bundle for this validated store.",
        ),
    ] = None,
    thesis_evidence_status: Annotated[
        str | None,
        typer.Option(
            "--thesis-evidence-status",
            help="Required bundle evidence class: pilot or confirmatory.",
        ),
    ] = None,
    thesis_sidecar: Annotated[
        list[Path] | None,
        typer.Option(
            "--thesis-sidecar",
            help="JSON/JSONL evidence sidecar to audit and merge; repeat for multiple inputs.",
        ),
    ] = None,
    candidate_benchmark_bundle: Annotated[Path | None, typer.Option("--candidate-benchmark-bundle")] = None,
    candidate_benchmark_binding_json: Annotated[Path | None, typer.Option("--candidate-benchmark-binding-json")] = None,
) -> None:
    """Print rollout-store metadata, optional validation, optional stats, or a random row index."""

    sidecar_paths = [] if thesis_sidecar is None else thesis_sidecar
    _validate_thesis_export_options(
        output=thesis_bundle_output,
        evidence_status=thesis_evidence_status,
        sidecars=sidecar_paths,
        random_index=random_index,
        candidate_benchmark_bundle=candidate_benchmark_bundle,
        candidate_benchmark_binding_json=candidate_benchmark_binding_json,
    )
    store_dir = RolloutZarrStoreConfig(store_dir=store).store_dir
    reader = RolloutZarrStoreReader(store_dir)
    if random_index:
        random_payload = _random_index_payload(reader=reader, min_horizon=min_horizon, seed=seed)
        random_payload = compact_ase_atek_identifiers(random_payload)
        if json_output:
            print(json.dumps(random_payload, indent=2, sort_keys=True))
        else:
            print(random_payload["index"])
        return
    payload: dict[str, Any] = reader.manifest()
    validation = None
    if validate or preflight:
        validation = reader.validate()
        payload["validation"] = {
            "ok": validation.ok,
            "num_rollouts": validation.num_rollouts,
            "num_steps": validation.num_steps,
            "num_candidates": validation.num_candidates,
            "errors": validation.errors,
        }
    if stats or preflight:
        payload["stats"] = build_compact_statistics(reader, manifest_payload=payload).payload
    if preflight:
        payload["preflight"] = _preflight_payload(
            reader=reader,
            manifest_payload=payload,
            validation_payload=payload["validation"],
            stats_payload=payload["stats"],
            profile=profile,
        )
    if thesis_bundle_output is not None:
        assert thesis_evidence_status in {"pilot", "confirmatory"}
        evidence_status = cast(Literal["pilot", "confirmatory"], thesis_evidence_status)
        try:
            frames = build_thesis_report_frames(
                [store_dir],
                sidecar_paths=sidecar_paths,
                evidence_status=evidence_status,
            )
            binding = None
            if candidate_benchmark_bundle is not None:
                if candidate_benchmark_binding_json is None:
                    raise typer.BadParameter(
                        "--candidate-benchmark-binding-json is required with --candidate-benchmark-bundle"
                    )
                binding = json.loads(candidate_benchmark_binding_json.read_text(encoding="utf-8"))
                derived_binding = benchmark_binding_from_reader(reader, payload)
                if binding != derived_binding:
                    raise typer.BadParameter("candidate benchmark binding does not match the selected rollout store")
            elif candidate_benchmark_binding_json is not None:
                raise typer.BadParameter(
                    "--candidate-benchmark-bundle is required with --candidate-benchmark-binding-json"
                )
            digest = write_thesis_report_bundle(
                thesis_bundle_output,
                frames,
                candidate_benchmark_path=candidate_benchmark_bundle,
                candidate_benchmark_binding=binding,
            )
        except (FileNotFoundError, TypeError, ValueError) as error:
            raise typer.BadParameter(str(error)) from error
        payload["thesis_bundle"] = {
            "bundle_role": THESIS_REPORT_BUNDLE_ROLE,
            "path": thesis_bundle_output.expanduser().resolve().as_posix(),
            "schema_version": THESIS_REPORT_BUNDLE_VERSION,
            "sha256": digest,
        }
    payload = compact_ase_atek_identifiers(payload)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        if preflight and not payload["preflight"]["go"]:
            raise SystemExit(1)
        return
    _print_text_summary(payload, validate=validate or preflight, stats=stats or preflight, preflight=preflight)
    if preflight and not payload["preflight"]["go"]:
        raise SystemExit(1)


def _validate_thesis_export_options(
    *,
    output: Path | None,
    evidence_status: str | None,
    sidecars: list[Path],
    random_index: bool,
    candidate_benchmark_bundle: Path | None,
    candidate_benchmark_binding_json: Path | None,
) -> None:
    if output is None and (evidence_status is not None or sidecars):
        raise typer.BadParameter("--thesis-evidence-status and --thesis-sidecar require --thesis-bundle-output.")
    if output is not None and evidence_status not in {"pilot", "confirmatory"}:
        raise typer.BadParameter("--thesis-bundle-output requires --thesis-evidence-status pilot|confirmatory.")
    if random_index and output is not None:
        raise typer.BadParameter("--random-index cannot be combined with --thesis-bundle-output.")
    if candidate_benchmark_bundle is None and candidate_benchmark_binding_json is not None:
        raise typer.BadParameter("--candidate-benchmark-bundle is required with --candidate-benchmark-binding-json.")
    if candidate_benchmark_bundle is not None and candidate_benchmark_binding_json is None:
        raise typer.BadParameter("--candidate-benchmark-binding-json is required with --candidate-benchmark-bundle.")
    if candidate_benchmark_bundle is not None and output is None:
        raise typer.BadParameter("candidate benchmark attachment requires --thesis-bundle-output.")


def _random_index_payload(*, reader: RolloutZarrStoreReader, min_horizon: int, seed: int | None) -> dict[str, Any]:
    horizon = np.asarray(reader.array("rollouts/horizon")).reshape(-1)
    eligible = np.flatnonzero(horizon >= int(min_horizon))
    if eligible.size == 0:
        raise SystemExit(f"No rollout rows found with horizon >= {int(min_horizon)}.")
    index = int(eligible[random.Random(seed).randrange(int(eligible.size))])
    return {
        "store_dir": reader.store_dir.as_posix(),
        "seed": seed,
        "min_horizon": int(min_horizon),
        "index": index,
        "horizon": int(horizon[index]),
        "num_eligible": int(eligible.size),
    }


def _preflight_payload(
    *,
    reader: RolloutZarrStoreReader,
    manifest_payload: dict[str, Any],
    validation_payload: dict[str, Any],
    stats_payload: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    profile = str(profile)
    if profile not in {"smoke", "production"}:
        raise typer.BadParameter("profile must be 'smoke' or 'production'")

    root_attrs = manifest_payload.get("root_attrs", {})
    manifest = manifest_payload.get("manifest", {})
    counts = manifest.get("counts", {})
    coverage = manifest.get("source_coverage", {})
    blockers: list[str] = []
    warnings: list[str] = []

    schema_version = str(root_attrs.get("schema_version") or "")
    schema_ok = schema_version == ROLLOUT_ZARR_SCHEMA_VERSION
    if not schema_ok:
        blockers.append(f"stale_schema:{schema_version or 'missing'}")
    if not bool(validation_payload.get("ok")):
        blockers.append("invalid_store")

    split_counts = coverage.get("split_counts")
    has_split_metadata = isinstance(split_counts, dict) and any(str(key) for key in split_counts)
    if not has_split_metadata:
        message = "missing_scene_split_metadata"
        if profile == "production":
            blockers.append(message)
        else:
            warnings.append(message)

    reward = _reward_signal_payload(reader)
    family_preflight = candidate_family_preflight_from_reader(reader)
    family_payload = family_preflight.to_payload()
    family_blockers = [f"candidate_family:{item['code']}" for item in family_payload["blockers"]]
    if profile == "production":
        blockers.extend(family_blockers)
    else:
        warnings.extend(family_blockers)

    storage = runtime_storage_statistics(reader.store_dir, candidate_count=int(counts.get("candidates") or 0))
    bytes_per_candidate = storage["bytes_per_candidate"]
    file_count = storage["file_count"]
    file_count_limit = storage["file_count_limit"]
    bytes_per_candidate_limit = storage["bytes_per_candidate_limit"]
    storage_excessive = (
        isinstance(file_count, int | float)
        and isinstance(file_count_limit, int | float)
        and file_count > file_count_limit
    ) or (
        isinstance(bytes_per_candidate, int | float)
        and isinstance(bytes_per_candidate_limit, int | float)
        and bytes_per_candidate > bytes_per_candidate_limit
    )
    if storage_excessive:
        message = "excessive_chunk_file_bloat"
        if profile == "production":
            blockers.append(message)
        else:
            warnings.append(message)

    validity = stats_payload.get("candidate_validity", {})
    retention = {
        "selected_depth_enabled": bool(root_attrs.get("selected_depth_enabled", False)),
        "q_h_view_persisted": bool(root_attrs.get("q_h_view_persisted", False)),
        "target_eval_crops_enabled": bool(root_attrs.get("target_eval_crops_enabled", False)),
    }
    return {
        "profile": profile,
        "go": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "schema": {
            "ok": schema_ok,
            "actual": schema_version,
            "expected": ROLLOUT_ZARR_SCHEMA_VERSION,
        },
        "validation": validation_payload,
        "lineage": {
            "source_offline_store_version": root_attrs.get("source_offline_store_version"),
            "split_manifest_hash": root_attrs.get("split_manifest_hash"),
            "has_split_metadata": has_split_metadata,
        },
        "coverage": coverage,
        "validity": validity,
        "candidate_family": family_payload,
        "rewards": reward,
        "retention": retention,
        "storage": storage,
    }


def _target_component_count(*component_counts: dict[str, int]) -> int:
    total = 0
    for counts in component_counts:
        for name, count in counts.items():
            if "target" in str(name).lower():
                total += int(count)
    return total


def _reward_signal_payload(reader: RolloutZarrStoreReader) -> _RewardSignalPayload:
    try:
        values = np.asarray(reader.array("candidates/target_root_gain"), dtype=np.float64).reshape(-1)
    except KeyError:
        return {"finite_count": 0, "mean": None, "std": None, "min": None, "max": None}
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"finite_count": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "finite_count": int(finite.size),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
    }


def _print_text_summary(payload: dict[str, Any], *, validate: bool, stats: bool, preflight: bool = False) -> None:
    """Print a human-readable manifest and stats summary."""

    console = cli_console()
    manifest = payload["manifest"]
    root_attrs = payload["root_attrs"]
    counts = manifest.get("counts", {})
    coverage = manifest.get("source_coverage", {})
    invocation = manifest.get("generation", {}).get("invocation", {})
    console.print(
        key_value_panel(
            "Rollout Store",
            [
                ("schema", root_attrs.get("schema_version")),
                ("rollouts", counts.get("rollouts")),
                ("steps", counts.get("steps")),
                ("candidates", counts.get("candidates")),
                ("sources", coverage.get("num_source_rows")),
                ("mode", invocation.get("mode")),
                ("config", invocation.get("config_path")),
                ("toml sha256", invocation.get("raw_toml_sha256")),
            ],
        )
    )
    console.print(counts_table("Scene Coverage", coverage.get("scene_counts", {})))
    console.print(counts_table("Split Coverage", coverage.get("split_counts", {})))
    if validate:
        validation = payload.get("validation", {})
        console.print(
            key_value_panel(
                "Validation",
                [
                    ("ok", validation.get("ok")),
                    ("rollouts", validation.get("num_rollouts")),
                    ("steps", validation.get("num_steps")),
                    ("candidates", validation.get("num_candidates")),
                    ("errors", validation.get("errors", [])),
                ],
            )
        )
    if stats:
        _print_stats(payload.get("stats", {}))
    if preflight:
        result = payload.get("preflight", {})
        console.print(
            key_value_panel(
                "Preflight",
                [
                    ("profile", result.get("profile")),
                    ("go", result.get("go")),
                    ("blockers", result.get("blockers", [])),
                    ("warnings", result.get("warnings", [])),
                ],
            )
        )
    if "thesis_bundle" in payload:
        bundle = payload["thesis_bundle"]
        console.print(
            key_value_panel(
                "Thesis Evidence Bundle",
                [
                    ("role", bundle.get("bundle_role")),
                    ("schema", bundle.get("schema_version")),
                    ("path", bundle.get("path")),
                    ("sha256", bundle.get("sha256")),
                ],
            )
        )


def _print_stats(stats_payload: dict[str, Any]) -> None:
    console = cli_console()
    validity = stats_payload.get("candidate_validity", {})
    selected = stats_payload.get("selected", {})
    valid_candidates = stats_payload.get("valid_candidates", {})
    console.print(
        key_value_panel(
            "Candidate Validity",
            [
                ("valid", validity.get("valid")),
                ("total", validity.get("total")),
                ("fraction", validity.get("fraction")),
            ],
        )
    )
    console.print(
        distribution_table("Valid Candidates Per Step", {"valid_per_step": validity.get("valid_per_step", {})})
    )
    console.print(counts_table("Invalid Reasons", validity.get("invalid_reasons", {})))
    console.print(counts_table("Selected Strategies", selected.get("strategy_counts", {})))
    console.print(counts_table("Selected Components", selected.get("component_counts", {})))
    console.print(distribution_table("Selected Path Length m", {"path_length_m": selected.get("path_length_m", {})}))
    console.print(counts_table("Valid Candidate Strategies", valid_candidates.get("strategy_counts", {})))
    console.print(counts_table("Valid Candidate Components", valid_candidates.get("component_counts", {})))
    console.print(counts_table("Policies", stats_payload.get("policy_counts", {})))


__all__ = ["app", "main"]
