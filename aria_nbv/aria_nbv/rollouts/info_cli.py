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
from typing import Annotated, Any

import numpy as np
import typer

from ..data_handling.identifiers import compact_ase_atek_identifiers
from ..utils.cli_format import cli_console, counts_table, distribution_table, key_value_panel
from ..utils.typer_cli import run_typer_app
from .trace import INVALID_REASON_CODES
from .zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION, RolloutZarrStoreConfig, RolloutZarrStoreReader

_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
_STRATEGY_NAMES = {
    0: "forward_rig",
    1: "radial_away",
    2: "radial_towards",
    3: "target_point",
}

app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Inspect rollout Zarr metadata, validation status, and compact rollout statistics.",
    pretty_exceptions_show_locals=False,
)


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
) -> None:
    """Print rollout-store metadata, optional validation, optional stats, or a random row index."""

    store_dir = RolloutZarrStoreConfig(store_dir=store).store_dir
    reader = RolloutZarrStoreReader(store_dir)
    if random_index:
        payload = _random_index_payload(reader=reader, min_horizon=min_horizon, seed=seed)
        payload = compact_ase_atek_identifiers(payload)
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(payload["index"])
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
        payload["stats"] = _stats_payload(reader=reader, manifest_payload=payload)
    if preflight:
        payload["preflight"] = _preflight_payload(
            reader=reader,
            manifest_payload=payload,
            validation_payload=payload["validation"],
            stats_payload=payload["stats"],
            profile=profile,
        )
    payload = compact_ase_atek_identifiers(payload)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        if preflight and not payload["preflight"]["go"]:
            raise SystemExit(1)
        return
    _print_text_summary(payload, validate=validate or preflight, stats=stats or preflight, preflight=preflight)
    if preflight and not payload["preflight"]["go"]:
        raise SystemExit(1)


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


def _stats_payload(*, reader: RolloutZarrStoreReader, manifest_payload: dict[str, Any]) -> dict[str, Any]:
    valid = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    primary_invalid_reason = np.asarray(reader.array("candidates/primary_invalid_reason"), dtype=np.int64).reshape(-1)
    strategy_id = np.asarray(reader.array("candidates/strategy_id"), dtype=np.int64).reshape(-1)
    mixture_id = np.asarray(reader.array("candidates/mixture_id"), dtype=np.int64).reshape(-1)
    valid_per_step = np.asarray(reader.array("steps/num_valid_candidates"), dtype=np.float64).reshape(-1)
    policy_ids = np.asarray(reader.array("rollouts/policy_id"), dtype=np.int64).reshape(-1)
    policy_names = _read_string_array(reader, "dictionaries/policy")
    component_names = _component_names(manifest_payload)
    return {
        "candidate_validity": {
            "valid": int(valid.sum()),
            "total": int(valid.size),
            "fraction": _safe_fraction(int(valid.sum()), int(valid.size)),
            "valid_per_step": _distribution(valid_per_step),
            "invalid_reasons": _reason_counts(primary_invalid_reason[~valid]),
        },
        "selected": {
            "total": int(selected.sum()),
            "strategy_counts": _id_counts(strategy_id[selected], names=_STRATEGY_NAMES),
            "component_counts": _id_counts(mixture_id[selected], names=component_names),
            "path_length_m": _distribution(_selected_path_lengths(reader)),
        },
        "valid_candidates": {
            "strategy_counts": _id_counts(strategy_id[valid], names=_STRATEGY_NAMES),
            "component_counts": _id_counts(mixture_id[valid], names=component_names),
        },
        "policy_counts": _id_counts(policy_ids, names=dict(enumerate(policy_names))),
        "source_coverage": dict(manifest_payload.get("manifest", {}).get("source_coverage", {})),
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

    valid_components = stats_payload.get("valid_candidates", {}).get("component_counts", {})
    selected_components = stats_payload.get("selected", {}).get("component_counts", {})
    target_component_count = _target_component_count(valid_components) + _target_component_count(selected_components)
    if target_component_count <= 0:
        message = "degenerate_target_aware_family_contribution"
        if profile == "production":
            blockers.append(message)
        else:
            warnings.append(message)

    reward = _reward_signal_payload(reader)
    if reward["finite_count"] <= 0 or reward["std"] is None or float(reward["std"]) <= 1.0e-8:
        message = "flat_reward_signal"
        if profile == "production":
            blockers.append(message)
        else:
            warnings.append(message)

    storage = _storage_payload(reader.store_dir, candidate_count=int(counts.get("candidates") or 0))
    if (
        storage["file_count"] > storage["file_count_limit"]
        or storage["bytes_per_candidate"] > storage["bytes_per_candidate_limit"]
    ):
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


def _reward_signal_payload(reader: RolloutZarrStoreReader) -> dict[str, float | int | None]:
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


def _storage_payload(store_dir: Path, *, candidate_count: int) -> dict[str, float | int]:
    file_count = 0
    total_bytes = 0
    for path in store_dir.rglob("*"):
        if not path.is_file():
            continue
        file_count += 1
        total_bytes += int(path.stat().st_size)
    denominator = max(1, int(candidate_count))
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "bytes_per_candidate": float(total_bytes) / float(denominator),
        "file_count_limit": max(2000, denominator * 20),
        "bytes_per_candidate_limit": 2_000_000.0,
    }


def _selected_path_lengths(reader: RolloutZarrStoreReader) -> np.ndarray:
    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    root_pose = np.asarray(reader.array("rollouts/root_pose_world"), dtype=np.float32).reshape(len(rollout_ids), 12)
    candidate_rollout_ids = np.asarray(reader.array("candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    candidate_steps = np.asarray(reader.array("candidates/step_index"), dtype=np.int64).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    candidate_poses = np.asarray(reader.array("candidates/pose_world_cam"), dtype=np.float32).reshape(-1, 12)
    lengths: list[float] = []
    for rollout_row, rollout_id in enumerate(rollout_ids):
        indices = np.flatnonzero(selected & (candidate_rollout_ids == int(rollout_id)))
        if indices.size == 0:
            lengths.append(0.0)
            continue
        ordered = indices[np.argsort(candidate_steps[indices], kind="stable")]
        points = [root_pose[rollout_row, 9:12], *[candidate_poses[index, 9:12] for index in ordered]]
        segment_lengths = [
            float(np.linalg.norm(np.asarray(points[index + 1]) - np.asarray(points[index])))
            for index in range(len(points) - 1)
        ]
        lengths.append(float(sum(segment_lengths)))
    return np.asarray(lengths, dtype=np.float64)


def _reason_counts(reason_codes: np.ndarray) -> dict[str, int]:
    names = {code: name for name, code in INVALID_REASON_CODES.items()}
    return _id_counts(np.asarray(reason_codes, dtype=np.int64), names=names)


def _id_counts(values: np.ndarray, *, names: dict[int, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in np.asarray(values, dtype=np.int64).reshape(-1):
        if value < 0:
            continue
        key = names.get(int(value), f"id_{int(value)}")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _component_names(manifest_payload: dict[str, Any]) -> dict[int, str]:
    writer_config = manifest_payload.get("manifest", {}).get("generation", {}).get("writer_config")
    components = []
    if isinstance(writer_config, dict):
        candidate_mixture = writer_config.get("candidate_mixture")
        if isinstance(candidate_mixture, dict):
            components = candidate_mixture.get("components") or []
    names: dict[int, str] = {}
    if isinstance(components, list):
        for index, component in enumerate(components):
            if isinstance(component, dict):
                name = component.get("name") or component.get("family") or component.get("position_mode")
                if name is not None:
                    names[index] = str(name)
    return names


def _read_string_array(reader: RolloutZarrStoreReader, path: str) -> list[str]:
    try:
        encoded = np.asarray(reader.array(path), dtype=np.uint8)
    except KeyError:
        return []
    return json.loads(encoded.tobytes().decode("utf-8"))


def _distribution(values: np.ndarray) -> dict[str, float | int | None]:
    finite = np.asarray(values, dtype=np.float64).reshape(-1)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            "count": 0,
            "min": None,
            "p5": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "p95": None,
            "max": None,
        }
    return {
        "count": int(finite.size),
        "min": float(np.min(finite)),
        "p5": float(np.percentile(finite, 5)),
        "p25": float(np.percentile(finite, 25)),
        "median": float(np.median(finite)),
        "mean": float(np.mean(finite)),
        "p75": float(np.percentile(finite, 75)),
        "p95": float(np.percentile(finite, 95)),
        "max": float(np.max(finite)),
    }


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


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
