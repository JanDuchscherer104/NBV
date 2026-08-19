"""Read-only inspection helpers for rollout Zarr stores.

This module keeps Streamlit, CLI, and tests away from ad hoc Zarr joins. The
helpers return plain dictionaries and NumPy-backed scalar values so UI code can
choose its own rendering library without owning rollout-store semantics.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
import zarr

from ..oracle.target_selection import TARGET_INVALID_REASON_CODES
from ..pose_generation import ViewDirectionMode, candidate_strategy_id
from .audits import candidate_policy_entropy
from .manifest import read_rollout_store_manifest
from .read_model import (
    decode_invalid_reason,
    decode_position_id,
    rollout_at,
    rollout_steps,
    selected_depth_for_step,
    target_rows,
)
from .trace import INVALID_REASON_CODES, _candidate_invalid_reasons
from .zarr_store import (
    Q_H_ARRAY_NAMES,
    Q_H_REWARD_METRIC,
    Q_H_TD_SEMANTICS,
    ROLLOUT_ZARR_SCHEMA_VERSION,
    RolloutZarrStoreReader,
    RolloutZarrValidationResult,
    _required_groups,
)

CandidateGroupField = Literal["position", "strategy", "mixture", "invalid_reason", "policy"]
CANDIDATE_GROUP_FIELDS: tuple[CandidateGroupField, ...] = (
    "position",
    "strategy",
    "mixture",
    "invalid_reason",
    "policy",
)

_TARGET_INVALID_REASON_NAMES = {int(code): name for name, code in TARGET_INVALID_REASON_CODES.items()}
_STRATEGY_NAMES = {candidate_strategy_id(mode): mode.value for mode in ViewDirectionMode}
_POLICY_COHORT_KEY_FIELDS = (
    "source_sample_key",
    "target_id",
    "target_protocol",
    "horizon",
    "acquisition_budget_steps",
    "branch_factor",
    "beam_width",
    "candidate_config",
    "oracle_config",
    "branch_schedule",
)
_TEMPORAL_METRICS = {
    "cumulative_target_rri": ("cumulative_target_rri", "RRI"),
    "marginal_target_rri": ("marginal_target_rri", "RRI"),
    "cumulative_scene_rri": ("cumulative_scene_rri", "RRI"),
    "cumulative_target_root_gain": ("cumulative_target_root_gain", "fraction"),
    "cumulative_scene_root_gain": ("cumulative_scene_root_gain", "fraction"),
    "selected_target_rri": ("selected_target_rri", "RRI"),
    "selected_target_root_gain": ("selected_target_root_gain", "fraction"),
    "selected_scene_rri": ("selected_scene_rri", "RRI"),
    "valid_fanout": ("num_valid_candidates", "candidates"),
    "invalid_fraction": ("invalid_fraction", "fraction"),
    "selected_probability": ("selected_probability", "probability"),
    "selected_entropy": ("selected_entropy", "nats"),
}
_TEMPORAL_GROUP_FIELDS = frozenset(
    {
        "policy",
        "horizon",
        "branch_factor",
        "beam_width",
        "temperature",
        "budget_configuration",
        "selected_position",
        "selected_strategy",
        "selected_mixture",
    }
)
_RECONSTRUCTION_METRIC_SPECS = (
    ("cumulative", "cumulative_target_root_gain", "Cumulative root-normalized target gain"),
    ("cumulative", "cumulative_target_rri", "Cumulative target RRI"),
    ("selected marginal", "selected_target_root_gain", "Selected one-step root-normalized gain"),
    ("selected marginal", "selected_target_rri", "Selected one-step target RRI"),
    ("selection", "selected_probability", "Selected-action probability"),
    ("selection", "selected_entropy", "Policy entropy"),
)
_EXACT_POLICY_ROLE_IDENTIFIERS = {
    ("oracle_greedy", "oracle_greedy"): "oracle_one_step",
    ("oracle_greedy", "oracle_lookahead"): "oracle_lookahead",
    ("oracle_greedy", "oracle_lookahead_diverse"): "oracle_lookahead",
    ("q_h", "q_h"): "q_h",
    ("learned_one_step", "learned_one_step"): "learned_one_step",
}
_HEADROOM_INVARIANT_FIELDS = (
    "source_sample_key",
    "source_sample_index",
    "target_id",
    "target_protocol",
    "horizon",
    "acquisition_budget_steps",
    "candidate_config",
    "oracle_config",
    "manifest_sha256",
    "writer_config_hash",
    "campaign_id",
    "plan_hash",
    "work_unit_hash",
    "profile_hash",
    "explicit_target_hash",
)
_HEADROOM_TREATMENT_FIELDS = ("policy", "branch_schedule", "branch_factor", "beam_width", "rollout_recipe")


@dataclass(frozen=True, slots=True)
class RolloutSuspiciousQueryConfig:
    """Thresholds used by `suspicious_rollout_rows`."""

    min_valid_candidates: int = 3
    """Flag steps with fewer actor-valid candidates than this count."""

    dominant_invalid_fraction: float = 0.8
    """Flag a step when one invalid reason explains at least this fraction of invalid rows."""

    high_target_score: float = 0.5
    """Flag invalid GT target rows whose selection score is at least this value."""

    max_step_distance_m: float = 1.25
    """Motion-realism threshold for selected candidate step length."""

    max_height_delta_m: float = 0.6
    """Motion-realism threshold for selected candidate height delta."""

    max_backward_step_m: float = 0.35
    """Motion-realism threshold for selected candidate backward motion."""

    max_yaw_delta_deg: float = 85.0
    """Motion-realism threshold for selected candidate yaw delta."""


def decode_target_invalid_reason(reason: int | np.integer[Any]) -> str:
    """Return the stable target-invalidity reason name for one numeric code."""

    return _TARGET_INVALID_REASON_NAMES.get(int(reason), f"target_reason_{int(reason)}")


def decode_strategy_id(strategy_id: int | np.integer[Any]) -> str:
    """Return the stable orientation/strategy name for one numeric id."""

    return _STRATEGY_NAMES.get(int(strategy_id), "unknown" if int(strategy_id) < 0 else f"strategy_{int(strategy_id)}")


def discover_rollout_store_paths(base_dir: Path, *, pattern: str = "**/*.zarr") -> list[Path]:
    """Return rollout Zarr store candidates under a cache directory.

    Args:
        base_dir: Directory to scan recursively.
        pattern: Glob pattern used to find Zarr directories.

    Returns:
        Absolute store paths sorted with the newest candidates first.
    """

    root = Path(base_dir).expanduser().resolve()
    if not root.exists():
        return []
    stores = [path.expanduser().resolve() for path in root.glob(pattern) if path.is_dir()]
    return sorted(stores, key=lambda path: (_path_mtime(path), path.as_posix()), reverse=True)


def rollout_store_inventory_rows(
    store_paths: Iterable[Path],
    *,
    validate: bool = True,
) -> list[dict[str, object]]:
    """Return schema, validation, count, lineage, and storage rows for stores.

    Args:
        store_paths: Candidate rollout-store directories.
        validate: Run the full cross-array validator for every discovered
            store. Interactive selectors may disable this and validate only
            the selected immutable store.
    """

    rows = [_rollout_store_inventory_row(Path(path).expanduser().resolve(), validate=validate) for path in store_paths]
    return sorted(
        rows,
        key=lambda row: (
            _schema_sort_rank(str(row.get("schema_status", ""))),
            bool(row.get("validation_ok") is True),
            float(row.get("mtime_unix") or 0.0),
            str(row.get("path", "")),
        ),
        reverse=True,
    )


def rollout_statistics(
    reader: RolloutZarrStoreReader,
    *,
    manifest_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute the compact statistics shared by CLI and report consumers.

    Args:
        reader: Read-only rollout-store adapter.
        manifest_payload: Optional result of :meth:`RolloutZarrStoreReader.manifest`.
            The reader is queried when omitted.

    Returns:
        Nested candidate-validity, selected-action, policy, and source-coverage
        statistics. Missing numeric samples remain explicit ``None`` values.
    """

    manifest_payload = reader.manifest() if manifest_payload is None else manifest_payload
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


def rollout_header_summary(
    reader: RolloutZarrStoreReader,
    *,
    manifest_payload: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Return selected-store counts, reference coverage, and whole-store byte costs.

    Reference coverage is available only when manifest provenance supplies an
    explicit denominator. Observed source rows never define that denominator.
    """

    manifest_payload = reader.manifest() if manifest_payload is None else manifest_payload
    root_attrs = manifest_payload.get("root_attrs")
    manifest = manifest_payload.get("manifest")
    root_attrs = root_attrs if isinstance(root_attrs, dict) else {}
    manifest = manifest if isinstance(manifest, dict) else {}
    counts = manifest.get("counts")
    coverage = manifest.get("source_coverage")
    counts = counts if isinstance(counts, dict) else {}
    coverage = coverage if isinstance(coverage, dict) else {}
    scene_counts = coverage.get("scene_counts")
    source_scenes = len(scene_counts) if isinstance(scene_counts, dict) else None
    source_rows = _nonnegative_int(coverage.get("num_source_rows"))
    rollouts = _nonnegative_int(counts.get("rollouts"), root_attrs.get("num_rollouts"))
    candidates = _nonnegative_int(counts.get("candidates"), root_attrs.get("num_candidates"))
    targets = _nonnegative_int(counts.get("targets"), root_attrs.get("num_targets"))
    reference_scenes = _nonnegative_int(coverage.get("reference_scene_count"))
    reference_rows = _nonnegative_int(coverage.get("reference_source_row_count"))
    scene_coverage_valid = (
        reference_scenes is not None and source_scenes is not None and 0 <= source_scenes <= reference_scenes
    )
    row_coverage_valid = reference_rows is not None and source_rows is not None and 0 <= source_rows <= reference_rows
    storage = runtime_storage_statistics(reader.store_dir, candidate_count=candidates or 0)
    return {
        "scenes": source_scenes,
        "targets": targets,
        "rollouts": rollouts,
        "candidate_rows": candidates,
        "source_rows": source_rows,
        "reference_scene_count": reference_scenes,
        "reference_scene_covered": source_scenes if scene_coverage_valid else None,
        "reference_scene_gap": None
        if reference_scenes is None or source_scenes is None
        else max(0, reference_scenes - source_scenes)
        if scene_coverage_valid
        else None,
        "reference_scene_fraction": _coverage_ratio(source_scenes, reference_scenes),
        "reference_source_row_count": reference_rows,
        "reference_source_rows_covered": source_rows if row_coverage_valid else None,
        "reference_source_row_gap": None
        if reference_rows is None or source_rows is None
        else max(0, reference_rows - source_rows)
        if row_coverage_valid
        else None,
        "reference_source_row_fraction": _coverage_ratio(source_rows, reference_rows),
        "reference_coverage_reason": (
            "manifest provenance declares observed coverage above its reference denominator"
            if (reference_scenes is not None and not scene_coverage_valid)
            or (reference_rows is not None and not row_coverage_valid)
            else None
            if reference_scenes is not None or reference_rows is not None
            else "manifest provenance does not declare a reference denominator"
        ),
        "logical_source_rows": dict(sorted(coverage.get("source_shard_counts", {}).items()))
        if isinstance(coverage.get("source_shard_counts"), dict)
        else {},
        "physical_store_bytes": int(storage["total_bytes"]),
        "physical_bytes_per_rollout": _ratio(int(storage["total_bytes"]), rollouts),
        "physical_bytes_per_candidate": _ratio(int(storage["total_bytes"]), candidates),
        "return_semantics": root_attrs.get("return_semantics"),
        "discount_gamma": _finite_or_none(root_attrs.get("discount_gamma")),
    }


def runtime_storage_statistics(store_dir: Path, *, candidate_count: int) -> dict[str, float | int]:
    """Return compact file-count and byte-cost statistics for one store.

    Args:
        store_dir: Rollout Zarr directory whose regular files are measured.
        candidate_count: Persisted candidate rows used to normalize byte cost.

    Returns:
        Storage totals and the existing rollout-preflight limits. The function
        reads file metadata only and does not open or mutate Zarr arrays.
    """

    file_count = 0
    total_bytes = 0
    for path in Path(store_dir).rglob("*"):
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


def candidate_audit_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    limit: int | None = None,
    row_callback: Callable[[dict[str, object]], None] | None = None,
) -> list[dict[str, object]]:
    """Return candidate rows, or stream them to ``row_callback`` without retention."""
    rows: list[dict[str, object]] = []
    emitted = 0
    oracle_label_mask = reader.array("candidates/oracle_label_mask")
    q_train_mask = reader.array("candidates/q_train_mask")
    strategy_ids = reader.array("candidates/strategy_id")
    target_log_error_gain = reader.array("candidates/target_log_error_gain")
    target_pm_dist_before = reader.array("candidates/target_pm_dist_before")
    target_pm_dist_after = reader.array("candidates/target_pm_dist_after")
    path_collision_mask = reader.array("candidate_diagnostics/path_collision_mask")
    path_collision_applicable = reader.array("candidate_diagnostics/path_collision_applicable_mask")
    path_collision_evaluated = reader.array("candidate_diagnostics/path_collision_evaluated_mask")
    free_space_margin_m = reader.array("candidate_diagnostics/free_space_margin_m")
    motion_height_delta_m = reader.array("candidate_diagnostics/motion_height_delta_m")
    motion_backward_step_m = reader.array("candidate_diagnostics/motion_backward_step_m")
    motion_yaw_delta_deg = reader.array("candidate_diagnostics/motion_yaw_delta_deg")
    target_bearing_yaw_deg = reader.array("candidate_diagnostics/target_bearing_yaw_deg")
    candidate_configs = _decoded_array(reader, "lineage/candidate_config_id", "config")
    rollout_configs = _decoded_array(reader, "lineage/rollout_config_id", "config")
    branch_schedules = _decoded_array(reader, "lineage/branch_schedule_id", "config")
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        cohort_fields = {
            "policy": rollout.policy,
            "horizon": rollout.horizon,
            "acquisition_budget_steps": rollout.horizon,
            "branch_factor": rollout.branch_factor,
            "beam_width": rollout.beam_width,
            "temperature": _finite_or_none(rollout.temperature),
            "candidate_config": candidate_configs[rollout_position],
            "rollout_config": rollout_configs[rollout_position],
            "branch_schedule": branch_schedules[rollout_position],
        }
        cohort_json = json.dumps(cohort_fields, sort_keys=True, separators=(",", ":"))
        generation_cohort_id = hashlib.sha256(cohort_json.encode()).hexdigest()[:16]
        root_center = np.asarray(rollout.root_pose_world[9:12], dtype=np.float64)
        for step in rollout_steps(reader, rollout):
            if step_row_id is not None and step.step_row_id != int(step_row_id):
                continue
            for local, row in enumerate(step.candidate_row_positions.tolist()):
                if limit is not None and emitted >= max(0, int(limit)):
                    return rows
                strategy_id = int(strategy_ids[row])
                pose = step.pose_world_cam[local]
                relative = np.asarray(pose[9:12], dtype=np.float64) - root_center
                candidate_row = {
                    "candidate_row_id": int(step.candidate_row_ids[local]),
                    "rollout_row_id": rollout.rollout_row_id,
                    "step_row_id": step.step_row_id,
                    "step_index": step.step_index,
                    "shell_index": int(step.shell_indices[local]),
                    "compact_valid_index": int(step.compact_valid_indices[local]),
                    "scene": rollout.scene,
                    "split": rollout.split,
                    "policy": rollout.policy,
                    "horizon": rollout.horizon,
                    "branch_factor": rollout.branch_factor,
                    "beam_width": rollout.beam_width,
                    "temperature": _finite_or_none(rollout.temperature),
                    "candidate_config": candidate_configs[rollout_position],
                    "rollout_config": rollout_configs[rollout_position],
                    "branch_schedule": branch_schedules[rollout_position],
                    "generation_cohort_id": generation_cohort_id,
                    "generation_cohort": cohort_json,
                    "target_row_id": rollout.target_row_id,
                    "selected": bool(step.selected_mask[local]),
                    "actor_action": bool(step.actor_action_mask[local]),
                    "oracle_label": bool(oracle_label_mask[row]),
                    "q_train": bool(q_train_mask[row]),
                    "strategy_id": strategy_id,
                    "strategy": decode_strategy_id(strategy_id),
                    "position_id": int(step.position_ids[local]),
                    "position": str(step.position_names[local]),
                    "mixture_id": int(step.mixture_ids[local]),
                    "mixture": str(step.mixture_names[local]),
                    "sampler_probability": _finite_or_none(step.sampler_probabilities[local]),
                    "invalid_reason": str(step.primary_invalid_reason_names[local]),
                    "invalid_reason_bitset": int(step.invalid_reason_bitsets[local]),
                    "target_rri": _finite_or_none(step.target_rri[local]),
                    "target_root_gain": _finite_or_none(step.target_root_gain[local]),
                    "target_log_error_gain": _finite_or_none(target_log_error_gain[row]),
                    "target_pm_dist_before": _finite_or_none(target_pm_dist_before[row]),
                    "target_pm_dist_after": _finite_or_none(target_pm_dist_after[row]),
                    "scene_rri": _finite_or_none(step.scene_rri[local]),
                    "selection_probability": _finite_or_none(step.selection_probabilities[local]),
                    "center_x": float(pose[9]),
                    "center_y": float(pose[10]),
                    "center_z": float(pose[11]),
                    "root_relative_x_m": float(relative[0]),
                    "root_relative_y_m": float(relative[1]),
                    "root_relative_z_m": float(relative[2]),
                    "root_distance_m": float(np.linalg.norm(relative)),
                    "coordinate_frame": "root-centered ARIA world (RIGHT_HAND_Z_UP)",
                    "units": "m",
                    "mesh_distance_m": _finite_or_none(step.mesh_distance_m[local]),
                    "path_min_clearance_m": _finite_or_none(step.path_min_clearance_m[local]),
                    "path_collision": bool(path_collision_mask[row]) if path_collision_evaluated[row] else None,
                    "path_collision_applicable": bool(path_collision_applicable[row]),
                    "path_collision_evaluated": bool(path_collision_evaluated[row]),
                    "free_space_margin_m": _finite_or_none(free_space_margin_m[row]),
                    "motion_step_length_m": _finite_or_none(step.motion_step_length_m[local]),
                    "motion_height_delta_m": _finite_or_none(motion_height_delta_m[row]),
                    "motion_backward_step_m": _finite_or_none(motion_backward_step_m[row]),
                    "motion_yaw_delta_deg": _finite_or_none(motion_yaw_delta_deg[row]),
                    "target_distance_m": _finite_or_none(step.target_distance_m[local]),
                    "target_bearing_yaw_deg": _finite_or_none(target_bearing_yaw_deg[row]),
                }
                if row_callback is not None:
                    row_callback(candidate_row)
                else:
                    rows.append(candidate_row)
                emitted += 1
    return rows


def candidate_population_evidence(
    reader: RolloutZarrStoreReader,
    *,
    group_by: CandidateGroupField | None = None,
    sample_size: int = 500,
    audit_reader: Callable[..., object] = candidate_audit_rows,
) -> dict[str, object]:
    """Collect candidate evidence once and expose bounded public projections.

    The callback path keeps Zarr access incremental and centralizes all
    candidate-derived projections behind one validated grouping vocabulary.
    ``sample`` is deterministic and capped independently from aggregate rows.
    """

    if group_by is not None and group_by not in CANDIDATE_GROUP_FIELDS:
        raise ValueError(f"Unsupported candidate group field {group_by!r}; expected one of {CANDIDATE_GROUP_FIELDS}.")
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")
    accumulator = _CandidatePopulationAccumulator(max_sample_rows=sample_size)
    try:
        audit_reader(reader, row_callback=accumulator.consume)
    except TypeError as error:
        if "row_callback" not in str(error):
            raise
        for row in audit_reader(reader):  # type: ignore[operator]
            accumulator.consume(row)
    rows = accumulator.rows
    sample = accumulator.sample()
    compositions = {key: candidate_composition_rows(rows, group_by=key) for key in CANDIDATE_GROUP_FIELDS}
    calibrations = {key: candidate_proposal_calibration_rows(rows, group_by=key) for key in CANDIDATE_GROUP_FIELDS}
    groups = {
        key: candidate_group_summary_rows(reader, group_by=key, audit_rows=rows) for key in CANDIDATE_GROUP_FIELDS
    }
    return {
        "composition": compositions,
        "calibration": calibrations,
        "collision": candidate_collision_support_rows(rows),
        "groups": groups,
        "sample": sample,
        "population_count": accumulator.population_count,
    }


class _CandidatePopulationAccumulator:
    """Single-pass population collector with bounded deterministic sampling."""

    def __init__(self, *, max_sample_rows: int) -> None:
        self.max_sample_rows = max_sample_rows
        self.population_count = 0
        self.rows: list[dict[str, object]] = []
        self._sample: list[tuple[str, int, dict[str, object]]] = []

    def consume(self, row: Mapping[str, object]) -> None:
        normalized = dict(row)
        self.population_count += 1
        self.rows.append(normalized)
        if self.max_sample_rows:
            candidate_id = int(normalized.get("candidate_row_id", -1))
            rank = hashlib.sha256(f"stored-rollout-display-v1\0{candidate_id}".encode()).hexdigest()
            self._sample.append((rank, candidate_id, normalized))
            self._sample.sort(key=lambda item: (item[0], item[1]))
            del self._sample[self.max_sample_rows :]

    def sample(self) -> dict[str, object]:
        rows = [row for _, _, row in self._sample]
        return {
            "rows": rows,
            "population_count": self.population_count,
            "display_count": len(rows),
            "max_rows": self.max_sample_rows,
            "seed": "stored-rollout-display-v1",
            "display_only": True,
        }


def temporal_metric_summary_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
    *,
    metric: str,
    group_fields: Iterable[str] = (),
) -> list[dict[str, object]]:
    """Aggregate one factual rollout metric over depth and explicit strata.

    Args:
        source: Reader or already-normalized output from
            :func:`rollout_step_objective_rows`.
        metric: Validated scientific metric name. ``valid_fanout`` maps to the
            factual ``num_valid_candidates`` field.
        group_fields: Upstream experiment dimensions or selected-action
            provenance fields. Selected-action fields are descriptive
            post-selection strata, not causal sampling-policy effects.

    Returns:
        One deterministic row per grouping tuple and ``step_index``. Counts
        include all source rows; statistics use finite values only and use
        linear interpolation for quartiles.

    Raises:
        ValueError: If the metric or a grouping field is unsupported.
    """

    if metric not in _TEMPORAL_METRICS:
        raise ValueError(f"Unsupported temporal metric {metric!r}; expected one of {sorted(_TEMPORAL_METRICS)}.")
    groups = tuple(group_fields)
    if len(set(groups)) != len(groups):
        raise ValueError("Temporal group fields must be unique.")
    unsupported = tuple(field for field in groups if field not in _TEMPORAL_GROUP_FIELDS)
    if unsupported:
        raise ValueError(
            f"Unsupported temporal group field(s) {unsupported!r}; expected fields from "
            f"{sorted(_TEMPORAL_GROUP_FIELDS)}."
        )

    source_rows = rollout_step_objective_rows(source) if hasattr(source, "array") else list(source)
    value_field, units = _TEMPORAL_METRICS[metric]
    grouped: dict[tuple[object, ...], list[object]] = {}
    for source_row in source_rows:
        row = dict(source_row)
        step_index = row.get("step_index")
        if step_index is None:
            raise ValueError("Temporal source rows require an explicit step_index.")
        key = (*(_temporal_group_value(row, field) for field in groups), int(step_index))
        grouped.setdefault(key, []).append(row.get(value_field))

    output: list[dict[str, object]] = []
    for key, values in sorted(
        grouped.items(),
        key=lambda item: (*tuple(str(value) for value in item[0][:-1]), int(item[0][-1])),
    ):
        normalized_values = [_finite_or_none(value) for value in values]
        finite_values = np.asarray([value for value in normalized_values if value is not None], dtype=np.float64)
        total_count = len(values)
        finite_count = int(finite_values.size)
        missing_count = total_count - finite_count
        if finite_count:
            q25, median, q75 = np.quantile(
                np.sort(finite_values),
                (0.25, 0.5, 0.75),
                method="linear",
            ).tolist()
            statistics: dict[str, float | None] = {
                "median": float(median),
                "q25": float(q25),
                "q75": float(q75),
                "mean": float(np.mean(finite_values)),
                "min": float(np.min(finite_values)),
                "max": float(np.max(finite_values)),
            }
        else:
            statistics = dict.fromkeys(("median", "q25", "q75", "mean", "min", "max"))
        row_output: dict[str, object] = {
            "metric": metric,
            "units": units,
            "step_index": int(key[-1]),
            **{field: key[index] for index, field in enumerate(groups)},
            "total_count": total_count,
            "finite_count": finite_count,
            "missing_count": missing_count,
            **statistics,
        }
        output.append(row_output)
    return output


def rollout_endpoint_metric_summary(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
    *,
    metric: str,
) -> dict[str, object]:
    """Summarize one terminal factual step per rollout for a metric.

    Each rollout contributes exactly its greatest persisted ``step_index``;
    shorter factual chains are therefore retained. Statistics use finite
    terminal values only, while the denominator counts every rollout endpoint.
    """

    if metric not in _TEMPORAL_METRICS:
        raise ValueError(f"Unsupported temporal metric {metric!r}; expected one of {sorted(_TEMPORAL_METRICS)}.")
    source_rows = rollout_step_objective_rows(source) if hasattr(source, "array") else list(source)
    value_field, units = _TEMPORAL_METRICS[metric]
    endpoints: dict[int, tuple[int, int, object]] = {}
    for position, source_row in enumerate(source_rows):
        row = dict(source_row)
        if row.get("rollout_row_id") is None or row.get("step_index") is None:
            raise ValueError("Endpoint source rows require rollout_row_id and step_index.")
        rollout_row_id = int(row["rollout_row_id"])
        candidate = (int(row["step_index"]), position, row.get(value_field))
        current = endpoints.get(rollout_row_id)
        if current is None or candidate[:2] > current[:2]:
            endpoints[rollout_row_id] = candidate

    values = [_finite_or_none(endpoint[2]) for endpoint in endpoints.values()]
    finite_values = np.asarray([value for value in values if value is not None], dtype=np.float64)
    total_count = len(values)
    finite_count = int(finite_values.size)
    return {
        "metric": metric,
        "units": units,
        "total_count": total_count,
        "finite_count": finite_count,
        "missing_count": total_count - finite_count,
        "median": None if not finite_count else float(np.median(finite_values)),
    }


def reconstruction_metric_summary_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Summarize the fixed factual reconstruction and selection metric plan."""

    source_rows = rollout_step_objective_rows(source) if hasattr(source, "array") else [dict(row) for row in source]
    rollout_count = len({int(row["rollout_row_id"]) for row in source_rows if row.get("rollout_row_id") is not None})
    endpoints = reconstruction_endpoint_rows(source_rows)
    output: list[dict[str, object]] = []
    for family, metric, label in _RECONSTRUCTION_METRIC_SPECS:
        values = [_finite_or_none(row.get(metric)) for row in source_rows]
        finite = np.asarray([value for value in values if value is not None], dtype=np.float64)
        endpoint_values = [_finite_or_none(row.get(metric)) for row in endpoints]
        finite_endpoints = np.asarray([value for value in endpoint_values if value is not None], dtype=np.float64)
        output.append(
            {
                "family": family,
                "metric": metric,
                "label": label,
                "units": _TEMPORAL_METRICS[metric][1],
                "row_count": len(source_rows),
                "rollout_count": rollout_count,
                "finite_count": int(finite.size),
                "missing_count": len(values) - int(finite.size),
                **_finite_summary(finite),
                "endpoint_total_count": len(endpoint_values),
                "endpoint_finite_count": int(finite_endpoints.size),
                "endpoint_missing_count": len(endpoint_values) - int(finite_endpoints.size),
                **{f"endpoint_{key}": value for key, value in _finite_summary(finite_endpoints).items()},
            }
        )
    return output


def reconstruction_endpoint_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Return one greatest persisted factual step per rollout."""

    source_rows = rollout_step_objective_rows(source) if hasattr(source, "array") else [dict(row) for row in source]
    endpoints: dict[int, tuple[int, int, dict[str, object]]] = {}
    for position, row in enumerate(source_rows):
        if row.get("rollout_row_id") is None or row.get("step_index") is None:
            raise ValueError("Endpoint source rows require rollout_row_id and step_index.")
        rollout_row_id = int(row["rollout_row_id"])
        candidate = (int(row["step_index"]), position, row)
        current = endpoints.get(rollout_row_id)
        if current is None or candidate[:2] > current[:2]:
            endpoints[rollout_row_id] = candidate
    fields = tuple(metric for _family, metric, _label in _RECONSTRUCTION_METRIC_SPECS)
    context = ("rollout_row_id", "scene", "policy", "horizon", "step_index")
    return [
        {
            **{field: row.get(field) for field in context},
            **{field: _finite_or_none(row.get(field)) for field in fields},
        }
        for _depth, _position, row in sorted(endpoints.values(), key=lambda item: int(item[2]["rollout_row_id"]))
    ]


def reconstruction_endpoint_summary_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
    *,
    group_fields: Iterable[str] = ("policy", "horizon"),
) -> list[dict[str, object]]:
    """Summarize factual endpoints over supported exact display strata."""

    groups = tuple(group_fields)
    unsupported = tuple(field for field in groups if field not in {"policy", "horizon", "scene"})
    if unsupported:
        raise ValueError(f"Unsupported endpoint group field(s): {unsupported!r}.")
    endpoints = reconstruction_endpoint_rows(source)
    output: list[dict[str, object]] = []
    for family, metric, label in _RECONSTRUCTION_METRIC_SPECS:
        grouped: dict[tuple[object, ...], list[object]] = {}
        for row in endpoints:
            grouped.setdefault(tuple(row.get(field) for field in groups), []).append(row.get(metric))
        for key, values in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
            normalized = [_finite_or_none(value) for value in values]
            finite = np.asarray([value for value in normalized if value is not None], dtype=np.float64)
            output.append(
                {
                    **{field: key[index] for index, field in enumerate(groups)},
                    "family": family,
                    "metric": metric,
                    "label": label,
                    "units": _TEMPORAL_METRICS[metric][1],
                    "total_count": len(values),
                    "finite_count": int(finite.size),
                    "missing_count": len(values) - int(finite.size),
                    **_finite_summary(finite),
                }
            )
    return output


def discounted_rollout_return_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
    *,
    return_semantics: object,
    discount_gamma: object,
) -> dict[str, object]:
    """Derive discounted factual selected gain under the persisted contract."""

    if return_semantics != "cumulative_target_root_gain":
        return {"available": False, "reason": f"unsupported return_semantics={return_semantics!r}", "rows": []}
    gamma = _finite_or_none(discount_gamma)
    if gamma is None or gamma < 0.0 or gamma > 1.0:
        return {"available": False, "reason": f"invalid discount_gamma={discount_gamma!r}", "rows": []}
    source_rows = rollout_step_objective_rows(source) if hasattr(source, "array") else [dict(row) for row in source]
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in source_rows:
        if row.get("rollout_row_id") is not None:
            grouped.setdefault(int(row["rollout_row_id"]), []).append(row)
    output: list[dict[str, object]] = []
    for rollout_row_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: int(row["step_index"]))
        rewards = [_finite_or_none(row.get("selected_target_root_gain")) for row in ordered]
        discounted = (
            None
            if any(reward is None for reward in rewards)
            else float(sum((gamma**index) * float(reward) for index, reward in enumerate(rewards)))
        )
        first = ordered[0]
        output.append(
            {
                "rollout_row_id": rollout_row_id,
                "scene": first.get("scene"),
                "policy": first.get("policy"),
                "horizon": first.get("horizon"),
                "discount_gamma": gamma,
                "discounted_return": discounted,
                "available": discounted is not None,
                "reason": None
                if discounted is not None
                else "one or more factual selected_target_root_gain values are missing",
            }
        )
    return {"available": True, "reason": "derived from factual selected_target_root_gain steps", "rows": output}


def exact_policy_role_rows(cohort_rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Attach roles only from exact persisted ``(policy, branch_schedule)`` pairs."""

    output: list[dict[str, object]] = []
    for source_row in cohort_rows:
        row = dict(source_row)
        identifier = (str(row.get("policy", "")), str(row.get("branch_schedule", "")))
        role = _EXACT_POLICY_ROLE_IDENTIFIERS.get(identifier)
        if role is not None:
            output.append({**row, "semantic_role": role, "role_identifier": f"{identifier[0]} / {identifier[1]}"})
    return output


def oracle_headroom_evidence(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
    *,
    threshold: float = 1e-8,
) -> dict[str, object]:
    """Return exact-role diagnostic endpoint contrasts with honest exclusions."""

    if threshold <= 0.0:
        raise ValueError("threshold must be positive.")
    source_rows = _policy_cohort_projection_rows(source) if hasattr(source, "array") else [dict(row) for row in source]
    role_rows = exact_policy_role_rows(source_rows)
    grouped: dict[str, list[dict[str, object]]] = {}
    malformed_rows: list[dict[str, object]] = []
    for raw_row_index, row in enumerate(role_rows):
        missing = tuple(field for field in _HEADROOM_INVARIANT_FIELDS[:10] if _missing_identity(row.get(field)))
        if missing:
            malformed_rows.append(
                {
                    **row,
                    "raw_row_id": raw_row_index,
                    "exclusion_reason": f"identity_mismatch:{','.join(missing)}",
                }
            )
            continue
        key_payload = {field: row.get(field) for field in _HEADROOM_INVARIANT_FIELDS}
        invariant_key = json.dumps(key_payload, sort_keys=True, separators=(",", ":"))
        grouped.setdefault(invariant_key, []).append({**row, "headroom_invariant_key": invariant_key})

    contrast_specs = {
        "delta_look": ("oracle_one_step", "oracle_lookahead"),
        "delta_Q": ("learned_one_step", "q_h"),
        "eta_Q": ("learned_one_step", "q_h", "oracle_lookahead"),
    }
    contrast_rows: list[dict[str, object]] = []
    for invariant_key, rows in sorted(grouped.items()):
        by_role: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            by_role.setdefault(str(row["semantic_role"]), []).append(row)
        for contrast, roles in contrast_specs.items():
            reason: str | None = None
            selected: dict[str, dict[str, object]] = {}
            for role in roles:
                matches = by_role.get(role, [])
                if not matches:
                    reason = f"missing_role:{role}"
                    break
                if len(matches) != 1:
                    reason = f"duplicate_role:{role}"
                    break
                selected[role] = matches[0]
            normalized_conditions: dict[str, dict[str, object]] = {}
            values: dict[str, float] = {}
            if reason is None:
                for role, row in selected.items():
                    if row.get("termination_reason") == "incomplete_rollout":
                        reason = f"incomplete_rollout:{role}"
                        break
                    temperature, temperature_error = _headroom_condition(row, "temperature", missing_value=-1)
                    random_seed, seed_error = _headroom_condition(row, "random_seed", missing_value=-1)
                    if temperature_error or seed_error:
                        reason = "unsupported_semantics"
                        break
                    normalized_conditions[role] = {"temperature": temperature, "random_seed": random_seed}
                    value = _finite_or_none(row.get("final_cumulative_target_root_gain"))
                    if value is None:
                        reason = f"nonfinite_endpoint:{role}"
                        break
                    values[role] = value
            if reason is None:
                for field in ("temperature", "random_seed"):
                    applicable = {
                        condition[field]
                        for condition in normalized_conditions.values()
                        if condition[field] != "not_applicable"
                    }
                    if len(applicable) > 1:
                        reason = f"incompatible_{field}"
                        break
            value: float | None = None
            denominator: float | None = None
            if reason is None and contrast == "delta_look":
                value = values["oracle_lookahead"] - values["oracle_one_step"]
            elif reason is None and contrast == "delta_Q":
                value = values["q_h"] - values["learned_one_step"]
            elif reason is None:
                denominator = values["oracle_lookahead"] - values["learned_one_step"]
                if denominator <= threshold:
                    reason = "nonpositive_or_weak_headroom"
                else:
                    value = (values["q_h"] - values["learned_one_step"]) / denominator
            evidence_row = next(iter(selected.values()), rows[0])
            contrast_rows.append(
                {
                    "contrast": contrast,
                    "status": "included" if reason is None else "excluded",
                    "exclusion_reason": reason,
                    "value": value,
                    "headroom_denominator": denominator,
                    "headroom_invariant_key": invariant_key,
                    "scene": evidence_row.get("scene"),
                    "normalized_conditions": normalized_conditions,
                    "role_treatments": {
                        role: {field: row.get(field) for field in _HEADROOM_TREATMENT_FIELDS}
                        for role, row in selected.items()
                    },
                }
            )
    malformed_cohorts: list[dict[str, object]] = []
    for malformed in malformed_rows:
        malformed_cohorts.append(malformed)
    for malformed in malformed_cohorts:
        for contrast in contrast_specs:
            contrast_rows.append(
                {
                    "contrast": contrast,
                    "status": "excluded",
                    "exclusion_reason": malformed["exclusion_reason"],
                    "value": None,
                    "headroom_denominator": None,
                    "headroom_invariant_key": None,
                    "scene": malformed.get("scene"),
                    "normalized_conditions": {},
                    "role_treatments": {},
                    "raw_row_id": malformed.get("raw_row_id"),
                }
            )
    summary_rows: list[dict[str, object]] = []
    for contrast in contrast_specs:
        rows = [row for row in contrast_rows if row["contrast"] == contrast]
        reasons = Counter(str(row["exclusion_reason"]) for row in rows if row["exclusion_reason"] is not None)
        included = sum(row["status"] == "included" for row in rows)
        summary_rows.append(
            {
                "contrast": contrast,
                "eligible_count": len(rows),
                "included_count": included,
                "excluded_count": len(rows) - included,
                "exclusion_reason_counts": dict(sorted(reasons.items())),
                "scene_support": len({str(row.get("scene")) for row in rows if row.get("scene") is not None}),
            }
        )
    return {
        "evidence_status": "diagnostic_proxy",
        "metric_source": "final_cumulative_target_root_gain",
        "endpoint_kind": "persisted_chain_terminal_step",
        "independent_endpoint_evaluation": False,
        "role_rows": role_rows,
        "malformed_role_rows": malformed_rows,
        "contrast_rows": contrast_rows,
        "summary_rows": summary_rows,
    }


def _missing_identity(value: object) -> bool:
    return value is None or value == ""


def _headroom_condition(
    row: Mapping[str, object],
    field: str,
    *,
    missing_value: int,
) -> tuple[object, bool]:
    value = row.get(field)
    applicable = bool(row.get(f"{field}_applicable", False))
    if value is None or value == missing_value or (isinstance(value, float) and not np.isfinite(value)):
        return (None, True) if applicable else ("not_applicable", False)
    normalized = _finite_or_none(value)
    return (None, True) if normalized is None else (normalized, False)


def candidate_flow_rows(
    reader: RolloutZarrStoreReader,
    *,
    policies: Iterable[str] | None = None,
    step_indices: Iterable[int] | None = None,
) -> list[dict[str, object]]:
    """Return a count-conserving categorical candidate-provenance flow.

    The projection reads only rollout policy, candidate depth, provenance,
    actor-validity, invalid-reason, and selected-status arrays. It deliberately
    excludes geometry, rewards, oracle labels, training masks, motion, and
    dense depth.

    Args:
        reader: Read-only rollout-store adapter.
        policies: Optional decoded policy allowlist applied before aggregation.
        step_indices: Optional rollout-depth allowlist applied before
            aggregation.

    Returns:
        Consecutive links from the complete filtered candidate population to a
        combined proposal signature, actor validity, and terminal outcome.
        Every count and fraction uses the filtered population as its root
        denominator. A selected actor-invalid row terminates at
        ``selection_contract_violation``.
    """

    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    policy_ids = np.asarray(reader.array("rollouts/policy_id"), dtype=np.int64).reshape(-1)
    policy_names = _read_string_array(reader, "dictionaries/policy")
    if rollout_ids.size != policy_ids.size or np.unique(rollout_ids).size != rollout_ids.size:
        raise ValueError("Candidate flow requires unique, aligned rollout policy rows.")
    policy_by_rollout = {
        int(rollout_id): _decoded_id(int(policy_id), names=dict(enumerate(policy_names)), prefix="policy")
        for rollout_id, policy_id in zip(rollout_ids.tolist(), policy_ids.tolist(), strict=True)
    }

    candidate_rollout_ids = np.asarray(reader.array("candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    candidate_steps = np.asarray(reader.array("candidates/step_index"), dtype=np.int64).reshape(-1)
    mixture_ids = np.asarray(reader.array("candidates/mixture_id"), dtype=np.int64).reshape(-1)
    position_ids = np.asarray(reader.array("candidates/position_id"), dtype=np.int64).reshape(-1)
    strategy_ids = np.asarray(reader.array("candidates/strategy_id"), dtype=np.int64).reshape(-1)
    actor_action = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    primary_invalid_reason = np.asarray(
        reader.array("candidates/primary_invalid_reason"),
        dtype=np.int64,
    ).reshape(-1)
    candidate_count = int(candidate_rollout_ids.size)
    arrays = (
        candidate_steps,
        mixture_ids,
        position_ids,
        strategy_ids,
        actor_action,
        selected,
        primary_invalid_reason,
    )
    if any(array.size != candidate_count for array in arrays):
        raise ValueError("Candidate flow arrays must have one aligned value per candidate row.")

    policy_filter = None if policies is None else {str(value) for value in policies}
    step_filter = None if step_indices is None else {int(value) for value in step_indices}
    include = np.ones(candidate_count, dtype=np.bool_)
    for index, rollout_id in enumerate(candidate_rollout_ids.tolist()):
        policy = policy_by_rollout.get(int(rollout_id), "unknown")
        if policy_filter is not None and policy not in policy_filter:
            include[index] = False
        if step_filter is not None and int(candidate_steps[index]) not in step_filter:
            include[index] = False

    denominator = int(include.sum())
    component_names = _component_names(reader.manifest())
    transition_counts: Counter[tuple[str, str, str, str, str, str]] = Counter()
    root = (
        "root:scoped_candidates",
        f"All candidates in active scope ({denominator:,}; valid + invalid)",
        "root",
    )
    for index in np.flatnonzero(include).tolist():
        mixture = _decoded_id(int(mixture_ids[index]), names=component_names, prefix="mixture")
        position = decode_position_id(int(position_ids[index])) if int(position_ids[index]) >= 0 else "unknown"
        strategy = decode_strategy_id(int(strategy_ids[index]))
        validity = "actor_valid" if bool(actor_action[index]) else "actor_invalid"
        proposal_key = f"{int(mixture_ids[index])}:{int(position_ids[index])}:{int(strategy_ids[index])}"
        proposal_label = f"{mixture} · center={position} · view={strategy}"
        if bool(selected[index]) and not bool(actor_action[index]):
            outcome = "selection_contract_violation"
        elif bool(actor_action[index]):
            outcome = "selected" if bool(selected[index]) else "unselected"
        else:
            outcome = f"invalid: {decode_invalid_reason(primary_invalid_reason[index])}"
        nodes = (
            root,
            (f"proposal:{proposal_key}", proposal_label, "proposal"),
            (f"actor_validity:{validity}", validity, "actor_validity"),
            (f"candidate_outcome:{outcome}", outcome, "candidate_outcome"),
        )
        for source_node, target_node in pairwise(nodes):
            transition_counts[(*source_node, *target_node)] += 1

    rows: list[dict[str, object]] = []
    stage_order = {stage: index for index, stage in enumerate(("root", "proposal", "actor_validity"))}
    for transition, count in sorted(
        transition_counts.items(),
        key=lambda item: (stage_order[item[0][2]], item[0][0], item[0][3]),
    ):
        source_id, source_label, source_stage, target_id, target_label, target_stage = transition
        rows.append(
            {
                "source_id": source_id,
                "source_label": source_label,
                "source_stage": source_stage,
                "target_id": target_id,
                "target_label": target_label,
                "target_stage": target_stage,
                "transition": f"{source_stage} -> {target_stage}",
                "count": int(count),
                "root_denominator": denominator,
                "store_candidate_count": candidate_count,
                "fraction_of_root": _safe_fraction(int(count), denominator),
            }
        )
    return rows


def candidate_composition_rows(
    audit_rows: Iterable[Mapping[str, object]],
    *,
    group_by: CandidateGroupField = "mixture",
) -> list[dict[str, object]]:
    """Macro-summarize candidate populations without pooling decision states.

    ``audit_rows`` must be the one materialized :func:`candidate_audit_rows`
    projection for a validated store.  Counts remain exact; rates are first
    averaged within a state, then within a scene, then equally across scenes.
    """
    if group_by not in CANDIDATE_GROUP_FIELDS:
        raise ValueError(f"Unsupported candidate group field {group_by!r}; expected one of {CANDIDATE_GROUP_FIELDS}.")
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for source_row in audit_rows:
        row = dict(source_row)
        cohort_id = str(row.get("generation_cohort_id", "unknown"))
        family = str(row.get(group_by, "unknown"))
        state = f"{row.get('scene', 'unknown')}\0{row.get('rollout_row_id', 'unknown')}\0{row.get('step_row_id', 'unknown')}"
        grouped.setdefault((cohort_id, family, state), []).append(row)
    per_family: dict[tuple[str, str], list[dict[str, object]]] = {}
    for (cohort_id, family, state), rows in grouped.items():
        per_family.setdefault((cohort_id, family), []).append(
            {
                "state": state,
                "scene": str(rows[0].get("scene", "unknown")),
                "generation_cohort": rows[0].get("generation_cohort"),
                "allocated_count": len(rows),
                "actor_valid_count": sum(bool(row.get("actor_action")) for row in rows),
                "oracle_valid_count": sum(bool(row.get("oracle_label")) for row in rows),
                "trainable_count": sum(bool(row.get("q_train")) for row in rows),
                "selected_count": sum(bool(row.get("selected")) for row in rows),
            }
        )
    output: list[dict[str, object]] = []
    for (cohort_id, family), states in sorted(per_family.items()):
        scenes: dict[str, list[dict[str, object]]] = {}
        for state in states:
            scenes.setdefault(str(state["scene"]), []).append(state)
        scene_rates: list[dict[str, float]] = []
        for scene, scene_states in scenes.items():
            scene_rates.append(
                {
                    "scene": scene,
                    **{
                        f"{field}_rate": float(
                            np.mean(
                                [
                                    _safe_fraction(int(state[field]), int(state["allocated_count"])) or 0.0
                                    for state in scene_states
                                ]
                            )
                        )
                        for field in ("actor_valid_count", "oracle_valid_count", "trainable_count", "selected_count")
                    },
                }
            )
        totals = {
            field: sum(int(state[field]) for state in states)
            for field in (
                "allocated_count",
                "actor_valid_count",
                "oracle_valid_count",
                "trainable_count",
                "selected_count",
            )
        }
        output.append(
            {
                "group_by": group_by,
                "generation_cohort_id": cohort_id,
                "generation_cohort": states[0].get("generation_cohort"),
                "family": family,
                **totals,
                "state_count": len(states),
                "scene_count": len(scenes),
                "macro_actor_valid_rate": float(np.mean([row["actor_valid_count_rate"] for row in scene_rates])),
                "macro_oracle_valid_rate": float(np.mean([row["oracle_valid_count_rate"] for row in scene_rates])),
                "macro_trainable_rate": float(np.mean([row["trainable_count_rate"] for row in scene_rates])),
                "macro_selected_rate": float(np.mean([row["selected_count_rate"] for row in scene_rates])),
                "aggregation": "state_then_scene_macro",
            }
        )
    return output


def candidate_proposal_calibration_rows(
    audit_rows: Iterable[Mapping[str, object]],
    *,
    group_by: CandidateGroupField = "mixture",
) -> list[dict[str, object]]:
    """Compare proposal mass and selected share inside exact decision states."""
    rows = [dict(row) for row in audit_rows]
    composition = candidate_composition_rows(rows, group_by=group_by)
    by_family: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (str(row.get("generation_cohort_id", "unknown")), str(row.get(group_by, "unknown")))
        by_family.setdefault(key, []).append(row)
    output: list[dict[str, object]] = []
    for summary in composition:
        cohort_id = str(summary["generation_cohort_id"])
        family_rows = by_family[(cohort_id, str(summary["family"]))]
        cohort_rows = [row for row in rows if str(row.get("generation_cohort_id", "unknown")) == cohort_id]
        probabilities = [_finite_or_none(row.get("sampler_probability")) for row in family_rows]
        finite = [value for value in probabilities if value is not None]
        probability_error: str | None = None
        for state_key, state_rows_for_probability in _group_candidate_states(cohort_rows).items():
            state_values = [row.get("sampler_probability") for row in state_rows_for_probability]
            normalized = [_finite_or_none(value) for value in state_values]
            if any(value is None for value in normalized):
                probability_error = f"incomplete_probability_vector:{state_key}"
                break
            if any(float(value) < 0.0 for value in normalized if value is not None):
                probability_error = f"negative_probability:{state_key}"
                break
        total_probability = sum(
            value for row in cohort_rows if (value := _finite_or_none(row.get("sampler_probability"))) is not None
        )
        empirical = _safe_fraction(int(summary["allocated_count"]), len(cohort_rows))
        proposal_mass = (
            None
            if probability_error is not None or not finite or total_probability <= 0.0
            else float(sum(finite) / total_probability)
        )
        selected_share = _safe_fraction(
            int(summary["selected_count"]), sum(bool(row.get("selected")) for row in cohort_rows)
        )
        state_rows = _candidate_state_family_rows(family_rows, cohort_rows)
        scene_rows = _candidate_scene_macro_rows(state_rows)
        macro = {
            metric: _macro_mean(scene_rows, metric)
            for metric in ("empirical_frequency", "proposal_mass", "selected_share", "selection_enrichment")
        }
        output.append(
            {
                "group_by": group_by,
                "generation_cohort_id": cohort_id,
                "generation_cohort": summary["generation_cohort"],
                "family": summary["family"],
                "candidate_count": summary["allocated_count"],
                "finite_probability_count": len(finite),
                "population_empirical_frequency": empirical,
                "population_proposal_mass": proposal_mass,
                "population_calibration_gap": None
                if proposal_mass is None or empirical is None
                else empirical - proposal_mass,
                "population_selected_share": selected_share,
                "population_selection_enrichment": None
                if empirical in (None, 0.0) or selected_share is None
                else selected_share / empirical,
                "state_count": len(state_rows),
                "scene_count": len(scene_rows),
                "empirical_frequency": macro["empirical_frequency"],
                "proposal_mass": macro["proposal_mass"],
                "calibration_gap": (
                    None
                    if macro["proposal_mass"] is None or macro["empirical_frequency"] is None
                    else macro["empirical_frequency"] - macro["proposal_mass"]
                ),
                "selected_share": macro["selected_share"],
                "selection_enrichment": macro["selection_enrichment"],
                "empirical_denominator": len(cohort_rows),
                "proposal_denominator": sum(
                    1 for row in cohort_rows if _finite_or_none(row.get("sampler_probability")) is not None
                ),
                "proposal_available": probability_error is None,
                "proposal_unavailable_reason": probability_error,
                "selected_denominator": sum(bool(row.get("selected")) for row in cohort_rows),
                "aggregation": "exact_store_population; descriptive family comparison",
            }
        )
    return output


def _group_candidate_states(rows: Iterable[Mapping[str, object]]) -> dict[tuple[object, ...], list[dict[str, object]]]:
    """Group candidate rows by one persisted decision state for validation."""

    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for source_row in rows:
        row = dict(source_row)
        key = (row.get("rollout_row_id"), row.get("step_row_id"))
        grouped.setdefault(key, []).append(row)
    return grouped


def candidate_collision_support_rows(audit_rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Expose cohort-preserving collision and clearance availability.

    Counts remain exact populations. Rates are additionally reported as a
    state-then-scene macro so uneven candidate fan-out cannot dominate the
    descriptive comparison.
    """
    rows = [dict(row) for row in audit_rows]
    by_cohort: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_cohort.setdefault(str(row.get("generation_cohort_id", "unknown")), []).append(row)
    output: list[dict[str, object]] = []
    for cohort_id, cohort_rows in sorted(by_cohort.items()):
        collision_available = [row for row in cohort_rows if _collision_evaluated(row)]
        clearance = [_finite_or_none(row.get("path_min_clearance_m")) for row in cohort_rows]
        finite_clearance = [value for value in clearance if value is not None]
        state_rows = _candidate_state_rows(cohort_rows)
        scene_rows = _candidate_scene_macro_rows(state_rows)
        collision_count = sum(bool(row.get("path_collision")) for row in collision_available)
        output.append(
            {
                "generation_cohort_id": cohort_id,
                "generation_cohort": cohort_rows[0].get("generation_cohort"),
                "candidate_count": len(cohort_rows),
                "collision_available_count": len(collision_available),
                "collision_evaluated_count": len(collision_available),
                "collision_not_applicable_count": sum(
                    row.get("path_collision_applicable") is False for row in cohort_rows
                ),
                "collision_unavailable_count": sum(not _collision_evaluated(row) for row in cohort_rows),
                "collision_count": collision_count,
                "population_collision_rate": _safe_fraction(collision_count, len(collision_available)),
                "clearance_finite_count": len(finite_clearance),
                "population_clearance_mean_m": None if not finite_clearance else float(np.mean(finite_clearance)),
                "state_count": len(state_rows),
                "scene_count": len(scene_rows),
                "collision_rate": _macro_mean(scene_rows, "collision_rate"),
                "clearance_mean_m": _macro_mean(scene_rows, "clearance_mean_m"),
                "collision_denominator": len(collision_available),
                "clearance_denominator": len(finite_clearance),
                "available": bool(cohort_rows) and bool(collision_available) and bool(finite_clearance),
                "reason": None
                if cohort_rows and collision_available and finite_clearance
                else "collision or clearance evidence is unavailable",
            }
        )
    return output


def _collision_evaluated(row: Mapping[str, object]) -> bool:
    """Read explicit collision availability, retaining legacy row compatibility."""

    if "path_collision_evaluated" in row:
        return row.get("path_collision_evaluated") is True
    return row.get("path_collision") is not None


def _candidate_state_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for source_row in rows:
        row = dict(source_row)
        key = (
            str(row.get("scene", "unknown")),
            str(row.get("rollout_row_id", "unknown")),
            str(row.get("step_row_id", "unknown")),
        )
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, object]] = []
    for (scene, _rollout, _step), state_rows in sorted(grouped.items()):
        available = [row for row in state_rows if _collision_evaluated(row)]
        finite_clearance = [
            value
            for value in (_finite_or_none(row.get("path_min_clearance_m")) for row in state_rows)
            if value is not None
        ]
        output.append(
            {
                "scene": scene,
                "allocated_count": len(state_rows),
                "empirical_frequency": None,
                "proposal_mass": None,
                "selected_share": None,
                "selection_enrichment": None,
                "collision_rate": _safe_fraction(
                    sum(bool(row.get("path_collision")) for row in available), len(available)
                ),
                "clearance_mean_m": None if not finite_clearance else float(np.mean(finite_clearance)),
            }
        )
    return output


def _candidate_state_family_rows(
    family_rows: Iterable[Mapping[str, object]], cohort_rows: Iterable[Mapping[str, object]]
) -> list[dict[str, object]]:
    state_keys = {
        (
            str(row.get("scene", "unknown")),
            str(row.get("rollout_row_id", "unknown")),
            str(row.get("step_row_id", "unknown")),
        )
        for row in cohort_rows
    }
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for source_row in cohort_rows:
        row = dict(source_row)
        grouped.setdefault(
            (
                str(row.get("scene", "unknown")),
                str(row.get("rollout_row_id", "unknown")),
                str(row.get("step_row_id", "unknown")),
            ),
            [],
        ).append(row)
    family_grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for source_row in family_rows:
        row = dict(source_row)
        family_grouped.setdefault(
            (
                str(row.get("scene", "unknown")),
                str(row.get("rollout_row_id", "unknown")),
                str(row.get("step_row_id", "unknown")),
            ),
            [],
        ).append(row)
    output: list[dict[str, object]] = []
    for key in sorted(state_keys):
        state = grouped[key]
        family = family_grouped.get(key, [])
        finite_family = [
            value for value in (_finite_or_none(row.get("sampler_probability")) for row in family) if value is not None
        ]
        finite_all = [
            value for value in (_finite_or_none(row.get("sampler_probability")) for row in state) if value is not None
        ]
        empirical = _safe_fraction(len(family), len(state))
        if not finite_all or sum(finite_all) <= 0 or (family and not finite_family):
            proposal = None
        elif not family:
            proposal = 0.0
        else:
            proposal = float(sum(finite_family) / sum(finite_all))
        selected_total = sum(bool(row.get("selected")) for row in state)
        selected_family = sum(bool(row.get("selected")) for row in family)
        selected_share = _safe_fraction(selected_family, selected_total)
        output.append(
            {
                "scene": key[0],
                "empirical_frequency": empirical,
                "proposal_mass": proposal,
                "selected_share": selected_share,
                "selection_enrichment": (
                    None if empirical in (None, 0.0) or selected_share is None else selected_share / empirical
                ),
            }
        )
    return output


def _candidate_scene_macro_rows(state_rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in state_rows:
        grouped.setdefault(str(row.get("scene", "unknown")), []).append(dict(row))
    return [
        {"scene": scene, **{metric: _macro_mean(rows, metric) for metric in _MACRO_RATE_FIELDS}}
        for scene, rows in sorted(grouped.items())
    ]


_MACRO_RATE_FIELDS = (
    "empirical_frequency",
    "proposal_mass",
    "selected_share",
    "selection_enrichment",
    "collision_rate",
    "clearance_mean_m",
)


def _macro_mean(rows: Iterable[Mapping[str, object]], field: str) -> float | None:
    values = [_finite_or_none(row.get(field)) for row in rows]
    finite = [value for value in values if value is not None]
    return None if not finite else float(np.mean(finite))


def deterministic_candidate_display_sample(
    audit_rows: Iterable[Mapping[str, object]],
    *,
    max_rows: int = 500,
    seed: str = "stored-rollout-display-v1",
) -> dict[str, object]:
    """Return an order-invariant, explicitly descriptive bounded sample."""
    if isinstance(max_rows, bool) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer.")
    if not seed:
        raise ValueError("seed must be non-empty.")
    rows = [dict(row) for row in audit_rows]
    ordered = sorted(
        rows,
        key=lambda row: (
            hashlib.sha256(f"{seed}\\0{row.get('candidate_row_id', '')}".encode()).hexdigest(),
            int(row.get("candidate_row_id", -1)),
        ),
    )
    selected = ordered[:max_rows]
    return {
        "rows": selected,
        "population_count": len(rows),
        "display_count": len(selected),
        "max_rows": max_rows,
        "seed": seed,
        "display_only": True,
    }


def q_h_evidence_rows(
    reader: RolloutZarrStoreReader,
    *,
    deep_count: bool = False,
    chunk_size: int = 1024,
    validation_result: RolloutZarrValidationResult | None = None,
) -> list[dict[str, object]]:
    """Read store-local Q_H contract facts without dataset-stage admission.

    Canonical validation is mandatory.  The default path reads metadata only;
    ``deep_count=True`` performs the explicitly requested bounded mask count.
    """
    validation = reader.validate() if validation_result is None else validation_result
    if not validation.ok:
        return [{"available": False, "blocking_reason": "; ".join(validation.errors[:3]), "deep_count": deep_count}]
    root = reader.root
    if "q_h" not in root:
        return [{"available": False, "blocking_reason": "q_h group is unavailable", "deep_count": deep_count}]
    q_h = root["q_h"]
    required = ("candidate_row_id", "valid_action_mask", "q_train_mask")
    missing = tuple(path for path in required if path not in q_h)
    if missing:
        return [
            {
                "available": False,
                "blocking_reason": f"missing Q_H arrays: {', '.join(missing)}",
                "deep_count": deep_count,
            }
        ]
    root_attrs = dict(root.attrs)
    row: dict[str, object] = {
        "available": True,
        "blocking_reason": None,
        "deep_count": deep_count,
        "view_role": q_h.attrs.get("view_role"),
        "return_semantics": q_h.attrs.get("return_semantics"),
        "td_semantics": q_h.attrs.get("td_semantics"),
        "reward_metric": q_h.attrs.get("reward_metric"),
        "discount_gamma": _finite_or_none(q_h.attrs.get("discount_gamma")),
        "state_count": _nonnegative_int(q_h.attrs.get("state_count"), root_attrs.get("q_h_state_count")),
        "max_candidates": _nonnegative_int(q_h.attrs.get("max_candidates"), root_attrs.get("q_h_max_candidates")),
        "actor_valid_count": None,
        "oracle_valid_count": None,
        "trainable_count": None,
        "padding_count": None,
        "count_reason": "metadata does not prove mask counts; request deep_count",
    }
    if deep_count:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        candidate_ids_array = q_h["candidate_row_id"]
        valid_array = q_h["valid_action_mask"]
        trainable_array = q_h["q_train_mask"]
        factual_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
        factual_oracle = np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_).reshape(-1)
        oracle_by_id = {
            int(candidate_id): bool(factual_oracle[index]) for index, candidate_id in enumerate(factual_ids)
        }
        actor_count = oracle_count = trainable_count = padding_count = 0
        for start in range(0, int(candidate_ids_array.shape[0]), chunk_size):
            stop = min(start + chunk_size, int(candidate_ids_array.shape[0]))
            candidate_ids = np.asarray(candidate_ids_array[start:stop], dtype=np.int64)
            valid = np.asarray(valid_array[start:stop], dtype=np.bool_)
            trainable = np.asarray(trainable_array[start:stop], dtype=np.bool_)
            oracle_count += sum(
                oracle_by_id.get(int(candidate_id), False)
                for candidate_id in candidate_ids.reshape(-1)
                if int(candidate_id) >= 0
            )
            actor_count += int(valid.sum())
            trainable_count += int(trainable.sum())
            padding_count += int((candidate_ids < 0).sum())
        row.update(
            {
                "actor_valid_count": actor_count,
                "oracle_valid_count": oracle_count,
                "trainable_count": trainable_count,
                "padding_count": padding_count,
                "count_reason": "explicit bounded current-store mask projection",
            }
        )
    return [row]


def target_audit_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return stored target-task rows with frozen selection and GT-audit fields."""

    return [
        {
            "target_row_id": row.target_row_id,
            "target_id": row.target_id,
            "source": row.source,
            "source_index": row.source_index,
            "class": row.class_name,
            "sem_id": row.sem_id,
            "inst_id": row.inst_id,
            "confidence": _finite_or_none(row.confidence),
            "selection_rank": row.selection_rank,
            "selection_score": _finite_or_none(row.selection_score),
            "selection_probability": _finite_or_none(row.selection_probability),
            "target_valid": row.target_valid,
            "target_invalid_reason": decode_target_invalid_reason(row.primary_invalid_reason_id),
            "gt_label_valid": row.gt_label_valid,
            "gt_match_status": row.gt_match_status,
            "gt_match_iou": _finite_or_none(row.gt_match_iou),
            "gt_match_score": _finite_or_none(row.gt_match_score),
            "projected_area_pixels": _finite_or_none(row.projected_area_pixels),
            "projected_area_fraction": _finite_or_none(row.projected_area_fraction),
            "semidense_support": _finite_or_none(row.semidense_support_count),
            "evl_support": _finite_or_none(row.evl_support_count),
            "effective_support": _finite_or_none(row.effective_support_count),
            "visibility_score": _finite_or_none(row.visibility_score),
            "support_score": _finite_or_none(row.support_score),
            "deficit_score": _finite_or_none(row.deficit_score),
        }
        for row in target_rows(reader)
    ]


def validity_waterfall_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return full-shell to selected counts for one rollout store."""

    total = int(np.asarray(reader.array("candidates/candidate_row_id")).size)
    actor = int(np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).sum())
    oracle = int(np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_).sum())
    q_train = int(np.asarray(reader.array("candidates/q_train_mask"), dtype=np.bool_).sum())
    selected = int(np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).sum())
    return [
        {"stage": "full shell", "count": total, "fraction_of_full": _safe_fraction(total, total)},
        {"stage": "actor-valid", "count": actor, "fraction_of_full": _safe_fraction(actor, total)},
        {"stage": "oracle-label", "count": oracle, "fraction_of_full": _safe_fraction(oracle, total)},
        {"stage": "q-train", "count": q_train, "fraction_of_full": _safe_fraction(q_train, total)},
        {"stage": "selected", "count": selected, "fraction_of_full": _safe_fraction(selected, total)},
    ]


def mask_combination_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return observed candidate-mask combinations with explicit denominators.

    ``selected_mask`` is an actor decision and therefore only implies
    ``actor_action_mask``. It is not a stage after ``q_train_mask``. The
    training mask independently requires actor validity and oracle-label
    availability, so selected-but-not-training rows remain valid evidence.

    Args:
        reader: Read-only rollout-store adapter.

    Returns:
        Rows for observed Boolean combinations. Counts use the full persisted
        candidate table as their denominator, including invalid candidates.
    """

    actor = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    oracle = np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_).reshape(-1)
    q_train = np.asarray(reader.array("candidates/q_train_mask"), dtype=np.bool_).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    total = int(actor.size)
    rows: list[dict[str, object]] = []
    for actor_value in (False, True):
        for oracle_value in (False, True):
            for q_train_value in (False, True):
                for selected_value in (False, True):
                    mask = (
                        (actor == actor_value)
                        & (oracle == oracle_value)
                        & (q_train == q_train_value)
                        & (selected == selected_value)
                    )
                    count = int(mask.sum())
                    if count == 0:
                        continue
                    contract_valid = (not selected_value or actor_value) and (
                        not q_train_value or (actor_value and oracle_value)
                    )
                    rows.append(
                        {
                            "actor_action": actor_value,
                            "oracle_label": oracle_value,
                            "q_train": q_train_value,
                            "selected": selected_value,
                            "count": count,
                            "denominator": total,
                            "fraction_of_all": _safe_fraction(count, total),
                            "contract_valid": contract_valid,
                            "interpretation": _mask_combination_interpretation(
                                actor_action=actor_value,
                                oracle_label=oracle_value,
                                q_train=q_train_value,
                                selected=selected_value,
                            ),
                        }
                    )
    return rows


def store_invariant_rows(
    reader: RolloutZarrStoreReader,
    *,
    manifest: dict[str, Any] | None = None,
    manifest_payload: dict[str, Any] | None = None,
) -> list[dict[str, object]]:
    """Project the store's scientific and structural invariants as evidence rows.

    Args:
        reader: Read-only rollout-store adapter.
        manifest: Optional result of :meth:`RolloutZarrStoreReader.manifest`.
            The sidecar is read when omitted.
        manifest_payload: Backward-compatible keyword for ``manifest`` used by
            existing inspection callers. Passing both keywords is invalid.

    Returns:
        Deterministically ordered PASS/WARN/FAIL rows with expected conditions,
        observed evidence, source arrays, and actor/oracle/derived-data roles.

    Notes:
        This helper does not repair stale or inconsistent data. In particular,
        the factual ``steps/`` and ``candidates/`` tables remain authoritative;
        ``q_h/`` is checked as a derived training cache.
    """

    if manifest is not None and manifest_payload is not None:
        raise ValueError("Pass either manifest or manifest_payload, not both.")
    payload = manifest or manifest_payload or reader.manifest()
    manifest_data = payload.get("manifest", payload)
    root_attrs = dict(reader.root.attrs)
    rows = [_schema_manifest_invariant(root_attrs, manifest_data)]
    rows.append(_row_identity_invariant(reader))

    actor = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    oracle = np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_).reshape(-1)
    q_train = np.asarray(reader.array("candidates/q_train_mask"), dtype=np.bool_).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    target_rri = np.asarray(reader.array("candidates/target_rri"), dtype=np.float64).reshape(-1)
    target_root_gain = np.asarray(reader.array("candidates/target_root_gain"), dtype=np.float64).reshape(-1)

    selected_violations = int(np.count_nonzero(selected & (~actor)))
    rows.append(
        _invariant_row(
            invariant_id="selected_actor_mask",
            category="mask",
            status="PASS" if selected_violations == 0 else "FAIL",
            summary="Selected candidates are actor-selectable.",
            expected="selected_mask implies actor_action_mask; selected_mask does not imply q_train_mask.",
            observed=f"{selected_violations} selected rows violate actor validity; "
            f"{int(np.count_nonzero(selected & (~q_train)))} selected rows are intentionally outside q_train.",
            source_fields=("candidates/selected_mask", "candidates/actor_action_mask", "candidates/q_train_mask"),
            data_role="actor-visible",
            violation_count=selected_violations,
        )
    )

    q_train_violations = q_train & (
        (~actor) | (~oracle) | (~np.isfinite(target_rri)) | (~np.isfinite(target_root_gain))
    )
    rows.append(
        _invariant_row(
            invariant_id="q_train_supervision",
            category="mask",
            status="PASS" if not q_train_violations.any() else "FAIL",
            summary="Training rows have actor-valid, finite oracle supervision.",
            expected="q_train_mask implies actor_action_mask, oracle_label_mask, and finite target labels.",
            observed=f"{int(q_train_violations.sum())} of {int(q_train.sum())} q_train rows violate supervision.",
            source_fields=(
                "candidates/q_train_mask",
                "candidates/actor_action_mask",
                "candidates/oracle_label_mask",
                "candidates/target_rri",
                "candidates/target_root_gain",
            ),
            data_role="derived training data",
            violation_count=int(q_train_violations.sum()),
        )
    )
    rows.append(_selected_depth_invariant(reader, root_attrs))
    rows.append(_target_eval_invariant(reader, root_attrs))
    rows.append(_target_protocol_invariant(reader, root_attrs))
    rows.extend(_q_h_invariant_rows(reader, root_attrs))
    return rows


def candidate_group_summary_rows(
    reader: RolloutZarrStoreReader,
    *,
    group_by: CandidateGroupField,
    audit_rows: Iterable[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Summarize candidate validity and labels by a decoded categorical field.

    Args:
        reader: Read-only rollout-store adapter.
        group_by: Decoded categorical key present in candidate audit rows.
        audit_rows: Optional already-materialized candidate rows. Reusing this
            projection avoids repeated full-store joins when one active view
            needs several groupings.
    """

    if group_by not in CANDIDATE_GROUP_FIELDS:
        raise ValueError(f"Unsupported candidate group field: {group_by}")
    rows = candidate_audit_rows(reader) if audit_rows is None else audit_rows
    groups: dict[str, dict[str, float]] = {}
    for row in rows:
        key = str(row.get(group_by, "unknown"))
        summary = groups.setdefault(
            key,
            {"total": 0, "actor_valid": 0, "q_train": 0, "selected": 0, "target_root_gain_sum": 0.0, "gain_count": 0},
        )
        summary["total"] += 1
        summary["actor_valid"] += float(bool(row.get("actor_action")))
        summary["q_train"] += float(bool(row.get("q_train")))
        summary["selected"] += float(bool(row.get("selected")))
        gain = row.get("target_root_gain")
        if gain is not None:
            summary["target_root_gain_sum"] += float(gain)
            summary["gain_count"] += 1

    output: list[dict[str, object]] = []
    for key, summary in sorted(groups.items()):
        total = int(summary["total"])
        gain_count = int(summary["gain_count"])
        output.append(
            {
                group_by: key,
                "total": total,
                "actor_valid": int(summary["actor_valid"]),
                "actor_valid_fraction": _safe_fraction(int(summary["actor_valid"]), total),
                "q_train": int(summary["q_train"]),
                "selected": int(summary["selected"]),
                "mean_target_root_gain": None
                if gain_count == 0
                else float(summary["target_root_gain_sum"]) / float(gain_count),
            }
        )
    return output


def comparable_policy_cohorts(reader: RolloutZarrStoreReader) -> dict[str, object]:
    """Build exact matched cohorts for scientifically valid policy comparison.

    Cohorts match on source sample, target identity/protocol, horizon and search
    budget, candidate/oracle configuration, and branch schedule. Policy and
    rollout recipe identify the comparison dimension and are never averaged as
    if they were independent unmatched populations.

    Args:
        reader: Read-only rollout-store adapter.

    Returns:
        Mapping with rollout-level ``cohort_rows``, exact
        ``eligible_cohort_rows``, nearest-key ``mismatch_rows``, comparison
        labels, and the ordered cohort-key field names.
    """

    rows = _policy_cohort_projection_rows(reader)
    key_fields = _POLICY_COHORT_KEY_FIELDS
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["cohort_key"]), []).append(row)

    cohort_summaries: list[dict[str, object]] = []
    eligible_summaries: list[dict[str, object]] = []
    for cohort_key, cohort_rows in sorted(grouped.items()):
        by_label: dict[str, list[dict[str, object]]] = {}
        for row in cohort_rows:
            by_label.setdefault(str(row["comparison_label"]), []).append(row)
        labels = tuple(sorted(by_label))
        duplicate_labels = tuple(sorted(label for label, values in by_label.items() if len(values) != 1))
        eligible = len(labels) >= 2 and not duplicate_labels
        first = cohort_rows[0]
        summary = {
            "cohort_id": str(first["cohort_id"]),
            "cohort_key": cohort_key,
            **{field: first[field] for field in key_fields},
            "comparison_labels": labels,
            "comparison_count": len(labels),
            "rollout_count": len(cohort_rows),
            "eligible": eligible,
            "reason": "matched" if eligible else _cohort_ineligibility_reason(labels, duplicate_labels),
        }
        cohort_summaries.append(summary)
        if eligible:
            eligible_summaries.append(summary)

    comparison_labels = tuple(sorted({str(row["comparison_label"]) for row in rows}))
    mismatch_rows = _nearest_policy_mismatch_rows(rows, comparison_labels, grouped)
    return {
        "eligible": bool(eligible_summaries),
        "key_fields": key_fields,
        "comparison_policies": comparison_labels,
        "cohort_rows": rows,
        "cohort_summary_rows": cohort_summaries,
        "eligible_cohort_rows": eligible_summaries,
        "mismatch_rows": mismatch_rows,
    }


def paired_policy_comparison_rows(
    reader: RolloutZarrStoreReader,
    *,
    bootstrap_samples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> list[dict[str, object]]:
    """Summarize paired endpoint differences over exact policy cohorts.

    Args:
        reader: Read-only rollout-store adapter.
        bootstrap_samples: Number of paired bootstrap resamples. Intervals are
            emitted only for at least three matched cohorts.
        confidence: Central bootstrap interval probability in ``(0, 1)``.
        seed: Base seed for deterministic policy-pair and metric resampling.

    Returns:
        One row per sorted policy/recipe pair and endpoint metric, including
        cohort count, median/IQR per policy, median paired delta ``B - A``, and
        a deterministic bootstrap interval when sufficiently supported.

    Raises:
        ValueError: If ``bootstrap_samples`` or ``confidence`` is invalid.
    """

    if int(bootstrap_samples) < 1:
        raise ValueError("bootstrap_samples must be positive.")
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError("confidence must lie strictly between zero and one.")

    projection = comparable_policy_cohorts(reader)
    eligible_keys = {str(row["cohort_key"]) for row in projection["eligible_cohort_rows"]}
    grouped: dict[str, dict[str, dict[str, object]]] = {}
    for row in projection["cohort_rows"]:
        cohort_key = str(row["cohort_key"])
        if cohort_key not in eligible_keys:
            continue
        grouped.setdefault(cohort_key, {})[str(row["comparison_label"])] = row

    output: list[dict[str, object]] = []
    labels = tuple(str(value) for value in projection["comparison_policies"])
    metrics = (
        ("final_cumulative_target_rri", "dimensionless cumulative target RRI"),
        ("final_cumulative_target_root_gain", "dimensionless root-normalized target gain"),
    )
    summary_index = 0
    for policy_a, policy_b in combinations(labels, 2):
        matched = [
            (cohort_key, values[policy_a], values[policy_b])
            for cohort_key, values in sorted(grouped.items())
            if policy_a in values and policy_b in values
        ]
        if not matched:
            continue
        for metric, units in metrics:
            finite = [
                (cohort_key, float(left[metric]), float(right[metric]))
                for cohort_key, left, right in matched
                if _finite_or_none(left.get(metric)) is not None and _finite_or_none(right.get(metric)) is not None
            ]
            if not finite:
                continue
            a = np.asarray([value_a for _key, value_a, _value_b in finite], dtype=np.float64)
            b = np.asarray([value_b for _key, _value_a, value_b in finite], dtype=np.float64)
            delta = b - a
            ci_low, ci_high = _paired_bootstrap_interval(
                delta,
                bootstrap_samples=int(bootstrap_samples),
                confidence=float(confidence),
                seed=int(seed) + summary_index,
            )
            output.append(
                {
                    "policy_a": policy_a,
                    "policy_b": policy_b,
                    "policy_pair": f"{policy_b} - {policy_a}",
                    "metric": metric,
                    "units": units,
                    "matched_cohort_count": int(delta.size),
                    "matched_cohort_ids": tuple(_cohort_id_from_key(key) for key, _a, _b in finite),
                    "policy_a_median": float(np.median(a)),
                    "policy_a_q25": float(np.percentile(a, 25)),
                    "policy_a_q75": float(np.percentile(a, 75)),
                    "policy_b_median": float(np.median(b)),
                    "policy_b_q25": float(np.percentile(b, 25)),
                    "policy_b_q75": float(np.percentile(b, 75)),
                    "paired_delta_median": float(np.median(delta)),
                    "median_paired_delta": float(np.median(delta)),
                    "paired_delta_q25": float(np.percentile(delta, 25)),
                    "paired_delta_q75": float(np.percentile(delta, 75)),
                    "bootstrap_ci_low": ci_low,
                    "bootstrap_ci_high": ci_high,
                    "bootstrap_confidence": float(confidence) if ci_low is not None else None,
                    "bootstrap_samples": int(bootstrap_samples) if ci_low is not None else 0,
                    "delta_direction": "policy_b - policy_a",
                }
            )
            summary_index += 1
    return output


def selected_candidate_rank_rows(
    reader: RolloutZarrStoreReader,
    *,
    policies: Iterable[str] | None = None,
    step_indices: Iterable[int] | None = None,
) -> list[dict[str, object]]:
    """Rank selected actions by policy score and oracle target diagnostics.

    Root-gain rank/regret preserve the historical projection contract.
    ``selection_score_rank`` uses the persisted logits that actually governed
    selection, while ``target_rri_rank`` is a separate oracle diagnostic. All
    ranks use competition ranking over finite actor-valid alternatives, so
    ties share a rank and invalid or missing labels are never assigned a low
    score.

    Args:
        reader: Read-only rollout-store adapter.
        policies: Optional decoded candidate/action-policy allowlist.
        step_indices: Optional rollout-depth allowlist.

    Returns:
        One row per selected rollout step with policy mechanics, exact ranks,
        regret to the best valid alternative, and finite reward bands.
    """

    policy_filter = None if policies is None else {str(value) for value in policies}
    step_filter = None if step_indices is None else {int(value) for value in step_indices}

    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    source_ids = np.asarray(reader.array("rollouts/source_row_id"), dtype=np.int64).reshape(-1)
    target_ids = np.asarray(reader.array("rollouts/target_row_id"), dtype=np.int64).reshape(-1)
    policy_ids = np.asarray(reader.array("rollouts/policy_id"), dtype=np.int64).reshape(-1)
    temperatures = np.asarray(reader.array("rollouts/temperature"), dtype=np.float64).reshape(-1)
    policy_names = _read_string_array(reader, "dictionaries/policy")
    rollout_arrays = (source_ids, target_ids, policy_ids, temperatures)
    if (
        any(values.size != rollout_ids.size for values in rollout_arrays)
        or np.unique(rollout_ids).size != rollout_ids.size
    ):
        raise ValueError("Selected-action ranks require unique, aligned rollout rows.")
    rollout_context = {
        int(rollout_id): (
            int(source_id),
            int(target_id),
            _decoded_id(int(policy_id), names=dict(enumerate(policy_names)), prefix="policy"),
            _finite_or_none(temperature),
        )
        for rollout_id, source_id, target_id, policy_id, temperature in zip(
            rollout_ids,
            source_ids,
            target_ids,
            policy_ids,
            temperatures,
            strict=True,
        )
    }

    step_row_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    step_rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    step_depths = np.asarray(reader.array("steps/step_index"), dtype=np.int64).reshape(-1)
    selected_candidate_ids = np.asarray(reader.array("steps/selected_candidate_row_id"), dtype=np.int64).reshape(-1)
    step_arrays = (step_rollout_ids, step_depths, selected_candidate_ids)
    if (
        any(values.size != step_row_ids.size for values in step_arrays)
        or np.unique(step_row_ids).size != step_row_ids.size
    ):
        raise ValueError("Selected-action ranks require unique, aligned step rows.")

    candidate_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
    candidate_step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    actor_action = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    target_root_gain = np.asarray(reader.array("candidates/target_root_gain"), dtype=np.float64).reshape(-1)
    target_rri = np.asarray(reader.array("candidates/target_rri"), dtype=np.float64).reshape(-1)
    selection_logits = np.asarray(reader.array("candidates/selection_logits"), dtype=np.float64).reshape(-1)
    selection_probabilities = np.asarray(
        reader.array("candidates/selection_probabilities"),
        dtype=np.float64,
    ).reshape(-1)
    score_source_ids = np.asarray(reader.array("candidates/score_source_id"), dtype=np.int64).reshape(-1)
    score_source_names = _read_string_array(reader, "dictionaries/score_source")
    score_sources = dict(enumerate(score_source_names))
    candidate_arrays = (
        candidate_step_ids,
        actor_action,
        target_root_gain,
        target_rri,
        selection_logits,
        selection_probabilities,
        score_source_ids,
    )
    if any(values.size != candidate_ids.size for values in candidate_arrays):
        raise ValueError("Selected-action ranks require aligned candidate rows.")
    candidate_positions_by_step: dict[int, list[int]] = {}
    for candidate_position, step_row_id in enumerate(candidate_step_ids.tolist()):
        candidate_positions_by_step.setdefault(int(step_row_id), []).append(candidate_position)

    rows: list[dict[str, object]] = []
    for step_row_id, rollout_row_id, step_index, selected_candidate_id in zip(
        step_row_ids,
        step_rollout_ids,
        step_depths,
        selected_candidate_ids,
        strict=True,
    ):
        try:
            source_row_id, target_row_id, policy, temperature = rollout_context[int(rollout_row_id)]
        except KeyError as exc:
            raise ValueError(f"Step {int(step_row_id)} references unknown rollout {int(rollout_row_id)}.") from exc
        if policy_filter is not None and policy not in policy_filter:
            continue
        if step_filter is not None and int(step_index) not in step_filter:
            continue
        positions = np.asarray(candidate_positions_by_step.get(int(step_row_id), []), dtype=np.int64)
        step_candidate_ids = candidate_ids[positions]
        selected_matches = np.flatnonzero(step_candidate_ids == int(selected_candidate_id))
        if selected_matches.size > 1:
            raise ValueError(f"Step {int(step_row_id)} has duplicate selected candidate row ids.")
        selected = int(selected_matches[0]) if selected_matches.size else -1
        step_actor_action = actor_action[positions]
        selected_actor_valid = bool(selected >= 0 and step_actor_action[selected])
        root_gain_rank, root_gain_count, selected_value, values = _selected_competition_rank(
            target_root_gain[positions],
            valid_mask=step_actor_action,
            selected_index=selected,
        )
        target_rri_rank, target_rri_count, selected_target_rri, _target_rri_values = _selected_competition_rank(
            target_rri[positions],
            valid_mask=step_actor_action,
            selected_index=selected,
        )
        selection_score_rank, selection_score_count, _selected_logit, _selection_values = _selected_competition_rank(
            selection_logits[positions],
            valid_mask=step_actor_action,
            selected_index=selected,
        )
        regret = None if selected_value is None or not values.size else float(np.max(values) - selected_value)
        selected_row = int(positions[selected]) if selected >= 0 else -1
        score_source = (
            _decoded_id(int(score_source_ids[selected_row]), names=score_sources, prefix="score_source")
            if selected_row >= 0
            else "unknown"
        )
        entropy = candidate_policy_entropy(
            torch.from_numpy(selection_probabilities[positions]),
            torch.from_numpy(step_actor_action),
        )
        rows.append(
            {
                "rollout_row_id": int(rollout_row_id),
                "step_row_id": int(step_row_id),
                "step_index": int(step_index),
                "source_row_id": source_row_id,
                "target_row_id": target_row_id,
                "policy": policy,
                "temperature": temperature,
                "score_source": score_source,
                "selected_candidate_row_id": int(selected_candidate_id),
                "selected_actor_valid": selected_actor_valid,
                "selected_label_available": selected_value is not None,
                "selected_target_root_gain": selected_value,
                "selected_target_rri": selected_target_rri,
                "selected_probability": (
                    None if selected < 0 else _finite_or_none(selection_probabilities[selected_row])
                ),
                "selection_entropy": _finite_or_none(entropy.item()),
                "selected_reward_negative": selected_value is not None and selected_value < 0.0,
                "selected_rank": root_gain_rank,
                "selection_score_rank": selection_score_rank,
                "selection_score_rank_denominator": selection_score_count,
                "target_rri_rank": target_rri_rank,
                "rank_denominator": target_rri_count,
                "target_rri_rank_label": (
                    "unavailable" if target_rri_rank is None else f"{target_rri_rank} / {target_rri_count}"
                ),
                "regret_to_best": regret,
                "valid_candidate_count": int(step_actor_action.sum()),
                "finite_valid_label_count": root_gain_count,
                "best_valid_target_root_gain": None if values.size == 0 else float(np.max(values)),
                "valid_target_root_gain_q25": None if values.size == 0 else float(np.percentile(values, 25)),
                "valid_target_root_gain_median": None if values.size == 0 else float(np.median(values)),
                "valid_target_root_gain_q75": None if values.size == 0 else float(np.percentile(values, 75)),
                "worst_valid_target_root_gain": None if values.size == 0 else float(np.min(values)),
                "units": "dimensionless root-normalized target gain",
            }
        )
    return rows


def root_relative_candidate_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    actor_valid_only: bool = False,
) -> list[dict[str, object]]:
    """Return candidate centers relative to each rollout root in Z-up metres.

    The translation is ``candidate_center_world - root_center_world``. This
    keeps ARIA world axes, including the gravity-aligned Z axis, while removing
    unrelated scene origins. It intentionally does not aggregate or expose raw
    absolute world coordinates as comparison axes.

    Args:
        reader: Read-only rollout-store adapter.
        rollout_row_id: Optional stable rollout-row filter.
        step_row_id: Optional stable step-row filter.
        actor_valid_only: Exclude candidates outside the hard actor action set.

    Returns:
        Candidate rows in root-centered ARIA world coordinates with metres as
        units and ``RIGHT_HAND_Z_UP`` as the frame convention.
    """

    rows: list[dict[str, object]] = []
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        root_center = np.asarray(rollout.root_pose_world[9:12], dtype=np.float64)
        for step in rollout_steps(reader, rollout):
            if step_row_id is not None and step.step_row_id != int(step_row_id):
                continue
            for local, candidate_row_id in enumerate(step.candidate_row_ids.tolist()):
                if actor_valid_only and not bool(step.actor_action_mask[local]):
                    continue
                relative = np.asarray(step.pose_world_cam[local, 9:12], dtype=np.float64) - root_center
                rows.append(
                    {
                        "candidate_row_id": int(candidate_row_id),
                        "rollout_row_id": rollout.rollout_row_id,
                        "step_row_id": step.step_row_id,
                        "step_index": step.step_index,
                        "source_row_id": rollout.source_row_id,
                        "scene": rollout.scene,
                        "policy": rollout.policy,
                        "target_row_id": rollout.target_row_id,
                        "actor_action": bool(step.actor_action_mask[local]),
                        "selected": bool(step.selected_mask[local]),
                        "position": str(step.position_names[local]),
                        "mixture": str(step.mixture_names[local]),
                        "root_relative_x_m": float(relative[0]),
                        "root_relative_y_m": float(relative[1]),
                        "root_relative_z_m": float(relative[2]),
                        "root_distance_m": float(np.linalg.norm(relative)),
                        "coordinate_frame": "root-centered ARIA world (RIGHT_HAND_Z_UP)",
                        "units": "m",
                    }
                )
    return rows


def rollout_step_objective_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
) -> list[dict[str, object]]:
    """Return per-step objective, branching, and selected-action audit rows."""
    rows: list[dict[str, object]] = []
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        previous_target: float | None = None
        for step in rollout_steps(reader, rollout):
            selected = step.selected_local_index
            cumulative_target = _finite_or_none(step.cumulative_target_rri)
            marginal_target = (
                None
                if cumulative_target is None
                else cumulative_target
                if previous_target is None
                else cumulative_target - previous_target
            )
            previous_target = cumulative_target
            entropy = float(
                candidate_policy_entropy(
                    torch.from_numpy(step.selection_probabilities),
                    torch.from_numpy(step.actor_action_mask),
                ).item()
            )
            selected_row = int(step.candidate_row_positions[selected]) if selected >= 0 else -1
            strategy_id = int(reader.array("candidates/strategy_id")[selected_row]) if selected >= 0 else -1
            rows.append(
                {
                    "rollout_row_id": rollout.rollout_row_id,
                    "step_row_id": step.step_row_id,
                    "step_index": step.step_index,
                    "chain_id": rollout.chain_id,
                    "scene": rollout.scene,
                    "split": rollout.split,
                    "policy": rollout.policy,
                    "target_row_id": rollout.target_row_id,
                    "horizon": rollout.horizon,
                    "branch_factor": rollout.branch_factor,
                    "beam_width": rollout.beam_width,
                    "temperature": _finite_or_none(rollout.temperature),
                    "cumulative_target_rri": cumulative_target,
                    "marginal_target_rri": marginal_target,
                    "cumulative_scene_rri": _finite_or_none(step.cumulative_scene_rri),
                    "cumulative_target_root_gain": _finite_or_none(step.cumulative_target_root_gain),
                    "cumulative_scene_root_gain": _finite_or_none(step.cumulative_scene_root_gain),
                    "num_candidates": step.num_candidates,
                    "num_valid_candidates": step.num_valid_candidates,
                    "invalid_fraction": None
                    if step.num_candidates <= 0
                    else 1.0 - float(step.num_valid_candidates) / float(step.num_candidates),
                    "selected_candidate_row_id": step.selected_candidate_row_id,
                    "selected_target_rri": None if selected < 0 else _finite_or_none(step.target_rri[selected]),
                    "selected_target_root_gain": None
                    if selected < 0
                    else _finite_or_none(step.target_root_gain[selected]),
                    "selected_scene_rri": None if selected < 0 else _finite_or_none(step.scene_rri[selected]),
                    "selected_probability": None
                    if selected < 0
                    else _finite_or_none(step.selection_probabilities[selected]),
                    "selected_entropy": _finite_or_none(entropy),
                    "selected_sampler_probability": None
                    if selected < 0
                    else _finite_or_none(step.sampler_probabilities[selected]),
                    "selected_strategy": decode_strategy_id(strategy_id),
                    "selected_position": "" if selected < 0 else str(step.position_names[selected]),
                    "selected_mixture": "" if selected < 0 else str(step.mixture_names[selected]),
                    "selected_invalid_reason": "" if selected < 0 else str(step.primary_invalid_reason_names[selected]),
                }
            )
    return rows


def rollout_tree_summary_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Summarize selected rollout-tree provenance by policy, step, and family.

    Rollout stores persist factual selected chains, not a full parent-edge tree.
    This helper therefore reports the observed branching/provenance distribution
    across selected steps: policy/recipe parameters, candidate family, fanout,
    invalidity, and selected objective values.
    """

    metric_sources = {
        "valid_fanout": "num_valid_candidates",
        "invalid_fraction": "invalid_fraction",
        "marginal_target_rri": "marginal_target_rri",
        "selected_target_root_gain": "selected_target_root_gain",
        "selected_probability": "selected_probability",
        "selected_entropy": "selected_entropy",
    }
    groups: dict[tuple[object, ...], dict[str, float]] = {}
    for row in rollout_step_objective_rows(reader):
        key = (
            row.get("policy", ""),
            row.get("horizon"),
            row.get("branch_factor"),
            row.get("beam_width"),
            row.get("temperature"),
            row.get("step_index"),
            row.get("selected_position", ""),
            row.get("selected_strategy", ""),
            row.get("selected_mixture", ""),
        )
        summary = groups.setdefault(
            key,
            {
                "selected_steps": 0.0,
                **{f"{metric}_{part}": 0.0 for metric in metric_sources for part in ("sum", "count")},
            },
        )
        summary["selected_steps"] += 1.0
        for metric, source in metric_sources.items():
            value = _finite_or_none(row.get(source))
            if value is not None:
                summary[f"{metric}_sum"] += value
                summary[f"{metric}_count"] += 1.0

    output: list[dict[str, object]] = []
    for key, summary in sorted(groups.items(), key=lambda item: (str(item[0][0]), int(item[0][5] or 0), str(item[0]))):
        (
            policy,
            horizon,
            branch_factor,
            beam_width,
            temperature,
            step_index,
            selected_position,
            selected_strategy,
            selected_mixture,
        ) = key
        step_int = int(step_index) if step_index is not None else -1
        row = {
            "policy": policy,
            "horizon": horizon,
            "branch_factor": branch_factor,
            "beam_width": beam_width,
            "temperature": temperature,
            "step_index": step_int,
            "step_label": f"step {step_int}",
            "selected_position": selected_position,
            "selected_strategy": selected_strategy,
            "selected_mixture": selected_mixture,
            "selected_steps": int(summary["selected_steps"]),
        }
        row.update(
            {
                f"mean_{metric}": None
                if summary[f"{metric}_count"] <= 0
                else summary[f"{metric}_sum"] / summary[f"{metric}_count"]
                for metric in metric_sources
            }
        )
        output.append(row)
    return output


def selected_depth_summary_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    limit: int | None = 128,
) -> list[dict[str, object]]:
    """Return bounded summaries for persisted selected-action depth rasters.

    Dense selected-depth arrays are intentionally read only for the filtered
    step rows. The default limit keeps app and CLI inspections from scanning a
    production store by accident.
    """

    rows: list[dict[str, object]] = []
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        for step in rollout_steps(reader, rollout):
            if step_row_id is not None and step.step_row_id != int(step_row_id):
                continue
            if limit is not None and len(rows) >= max(0, int(limit)):
                return rows
            depth = selected_depth_for_step(reader, step)
            selected = step.selected_local_index
            row: dict[str, object] = dict.fromkeys(
                "candidate_row_id valid_pixels finite_pixels pixel_count valid_fraction finite_fraction "
                "depth_min_m depth_mean_m depth_max_m image_height image_width focal_x_px focal_y_px "
                "principal_x_px principal_y_px".split()
            )
            row.update(
                {
                    "rollout_row_id": rollout.rollout_row_id,
                    "step_row_id": step.step_row_id,
                    "step_index": step.step_index,
                    "selected_candidate_row_id": step.selected_candidate_row_id,
                    "candidate_row_id": depth.candidate_row_id,
                    "available": depth.available,
                    "warning": depth.warning or "",
                }
            )
            if depth.available and depth.depth_m is not None and depth.valid_mask is not None:
                values = depth.depth_m[np.isfinite(depth.depth_m)]
                pixel_count = int(depth.depth_m.size)
                valid_pixels = int(depth.valid_mask.sum())
                finite_pixels = int(values.size)
                row.update(
                    {
                        "candidate_row_id": depth.candidate_row_id,
                        "valid_pixels": valid_pixels,
                        "finite_pixels": finite_pixels,
                        "pixel_count": pixel_count,
                        "valid_fraction": _safe_fraction(valid_pixels, pixel_count),
                        "finite_fraction": _safe_fraction(finite_pixels, pixel_count),
                        "depth_min_m": None if values.size == 0 else float(np.min(values)),
                        "depth_mean_m": None if values.size == 0 else float(np.mean(values)),
                        "depth_max_m": None if values.size == 0 else float(np.max(values)),
                        "image_height": depth.image_size_hw[0] if depth.image_size_hw else None,
                        "image_width": depth.image_size_hw[1] if depth.image_size_hw else None,
                        "focal_x_px": float(depth.focal_px[0]) if depth.focal_px is not None else None,
                        "focal_y_px": float(depth.focal_px[1]) if depth.focal_px is not None else None,
                        "principal_x_px": float(depth.principal_point_px[0])
                        if depth.principal_point_px is not None
                        else None,
                        "principal_y_px": float(depth.principal_point_px[1])
                        if depth.principal_point_px is not None
                        else None,
                        "selected_position": "" if selected < 0 else str(step.position_names[selected]),
                        "selected_strategy": ""
                        if selected < 0
                        else decode_strategy_id(
                            int(reader.array("candidates/strategy_id")[step.candidate_row_positions[selected]])
                        ),
                        "selected_mixture": "" if selected < 0 else str(step.mixture_names[selected]),
                        "selected_target_root_gain": None
                        if selected < 0
                        else _finite_or_none(step.target_root_gain[selected]),
                        "selected_target_rri": None if selected < 0 else _finite_or_none(step.target_rri[selected]),
                    }
                )
            rows.append(row)
    return rows


def selected_depth_preview(
    reader: RolloutZarrStoreReader,
    *,
    step_row_id: int,
    max_size: int = 96,
) -> dict[str, object]:
    """Return one downsampled selected-depth payload for Plotly app previews."""

    matches = []
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        matches.extend(step for step in rollout_steps(reader, rollout) if step.step_row_id == int(step_row_id))
    if len(matches) != 1:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": None,
            "warning": f"selected_depth preview unavailable: expected one step row, found {len(matches)}.",
        }
    depth = selected_depth_for_step(reader, matches[0])
    if not depth.available or depth.depth_m is None or depth.valid_mask is None:
        return {
            "available": False,
            "step_row_id": depth.step_row_id,
            "candidate_row_id": depth.candidate_row_id,
            "warning": depth.warning or "",
        }
    stride = max(1, int(np.ceil(max(depth.depth_m.shape) / float(max(1, int(max_size))))))
    return {
        "available": True,
        "step_row_id": depth.step_row_id,
        "candidate_row_id": depth.candidate_row_id,
        "depth_m": depth.depth_m[::stride, ::stride].copy(),
        "valid_mask": depth.valid_mask[::stride, ::stride].copy(),
        "image_size_hw": depth.image_size_hw,
        "focal_px": () if depth.focal_px is None else tuple(float(value) for value in depth.focal_px),
        "principal_point_px": ()
        if depth.principal_point_px is None
        else tuple(float(value) for value in depth.principal_point_px),
        "stride": stride,
        "warning": "",
    }


def candidate_result_diagnostic_counts(candidates: Any) -> dict[str, list[dict[str, object]]]:
    """Return live `CandidateSamplingResult` counts by position and invalid reason."""

    valid = candidates.mask_valid.detach().cpu().numpy().reshape(-1).astype(bool, copy=False)
    position_values = getattr(candidates, "position_id", None)
    position_rows: list[dict[str, object]] = []
    if position_values is not None:
        positions = position_values.detach().cpu().numpy().reshape(-1)
        for value in sorted(np.unique(positions).tolist()):
            mask = positions == int(value)
            position_rows.append(
                {
                    "position": decode_position_id(int(value)),
                    "total": int(mask.sum()),
                    "valid": int((mask & valid).sum()),
                    "invalid": int((mask & (~valid)).sum()),
                }
            )

    reason_bitset, primary = _candidate_invalid_reasons(candidates)
    del reason_bitset
    primary_np = primary.detach().cpu().numpy().reshape(-1)
    invalid_rows: list[dict[str, object]] = []
    for value in sorted(np.unique(primary_np[~valid]).tolist()):
        mask = (~valid) & (primary_np == int(value))
        invalid_rows.append({"invalid_reason": decode_invalid_reason(int(value)), "count": int(mask.sum())})
    return {"position": position_rows, "invalid_reason": invalid_rows}


def suspicious_rollout_rows(
    reader: RolloutZarrStoreReader,
    *,
    config: RolloutSuspiciousQueryConfig | None = None,
) -> list[dict[str, object]]:
    """Return heuristic anomaly rows for rollout-store QA triage."""

    cfg = config or RolloutSuspiciousQueryConfig()
    rows: list[dict[str, object]] = []
    rows.extend(_mask_violation_rows(reader))
    rows.extend(_low_fanout_rows(reader, cfg))
    rows.extend(_dominant_invalid_reason_rows(reader, cfg))
    rows.extend(_missing_label_rows(reader))
    rows.extend(_high_score_invalid_target_rows(reader, cfg))
    rows.extend(_target_ambiguity_rows(reader))
    rows.extend(_selected_motion_outlier_rows(reader, cfg))
    rows.extend(_selected_depth_health_rows(reader))
    return rows


def _mask_violation_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return exact hard-mask implication violations at candidate-row grain."""

    candidate_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    actor = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    oracle = np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_).reshape(-1)
    q_train = np.asarray(reader.array("candidates/q_train_mask"), dtype=np.bool_).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    step_table_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    step_rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    rollout_by_step = {int(step): int(rollout) for step, rollout in zip(step_table_ids, step_rollout_ids, strict=True)}
    rows: list[dict[str, object]] = []
    for index in np.flatnonzero(selected & (~actor)).tolist():
        step_id = int(step_ids[index])
        rows.append(
            {
                "kind": "selected_actor_mask_violation",
                "severity": "error",
                "rollout_row_id": rollout_by_step.get(step_id),
                "step_row_id": step_id,
                "candidate_row_id": int(candidate_ids[index]),
                "message": "selected_mask=true requires actor_action_mask=true",
            }
        )
    for index in np.flatnonzero(q_train & ((~actor) | (~oracle))).tolist():
        step_id = int(step_ids[index])
        rows.append(
            {
                "kind": "q_train_mask_violation",
                "severity": "error",
                "rollout_row_id": rollout_by_step.get(step_id),
                "step_row_id": step_id,
                "candidate_row_id": int(candidate_ids[index]),
                "message": "q_train_mask=true requires actor_action_mask=true and oracle_label_mask=true",
            }
        )
    return rows


def _target_ambiguity_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return persisted target-match ambiguity without treating it as low reward."""

    rows: list[dict[str, object]] = []
    for target in target_audit_rows(reader):
        status = str(target.get("gt_match_status", "")).lower()
        if "ambigu" not in status:
            continue
        rows.append(
            {
                "kind": "target_ambiguity",
                "severity": "warning",
                "rollout_row_id": None,
                "step_row_id": None,
                "candidate_row_id": None,
                "message": f"target_row_id={target['target_row_id']} has GT match status {status!r}",
            }
        )
    return rows


def _selected_depth_health_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return selected-depth linkage or finite-pixel failures when depth is enabled."""

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return []
    rows: list[dict[str, object]] = []
    for depth in selected_depth_summary_rows(reader, limit=None):
        if bool(depth.get("available")) and int(depth.get("finite_pixels") or 0) > 0:
            continue
        rows.append(
            {
                "kind": "selected_depth_health",
                "severity": "error" if not bool(depth.get("available")) else "warning",
                "rollout_row_id": depth.get("rollout_row_id"),
                "step_row_id": depth.get("step_row_id"),
                "candidate_row_id": depth.get("candidate_row_id"),
                "message": str(depth.get("warning") or "selected depth has no finite pixels"),
            }
        )
    return rows


def _low_fanout_rows(reader: RolloutZarrStoreReader, cfg: RolloutSuspiciousQueryConfig) -> list[dict[str, object]]:
    valid_counts = np.asarray(reader.array("steps/num_valid_candidates"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    return [
        {
            "kind": "low_valid_fanout",
            "severity": "warning",
            "rollout_row_id": int(rollout_ids[index]),
            "step_row_id": int(step_ids[index]),
            "candidate_row_id": None,
            "message": f"valid candidates {int(value)} < {cfg.min_valid_candidates}",
        }
        for index, value in enumerate(valid_counts.tolist())
        if int(value) < int(cfg.min_valid_candidates)
    ]


def _dominant_invalid_reason_rows(
    reader: RolloutZarrStoreReader,
    cfg: RolloutSuspiciousQueryConfig,
) -> list[dict[str, object]]:
    candidate_step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    valid = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    primary = np.asarray(reader.array("candidates/primary_invalid_reason"), dtype=np.int64).reshape(-1)
    output: list[dict[str, object]] = []
    for step_index, step_row_id in enumerate(step_ids.tolist()):
        mask = candidate_step_ids == int(step_row_id)
        invalid_reasons = primary[mask & (~valid)]
        if invalid_reasons.size == 0:
            continue
        values, counts = np.unique(invalid_reasons, return_counts=True)
        best = int(np.argmax(counts))
        fraction = float(counts[best]) / float(invalid_reasons.size)
        if fraction >= float(cfg.dominant_invalid_fraction):
            output.append(
                {
                    "kind": "dominant_invalid_reason",
                    "severity": "warning",
                    "rollout_row_id": int(rollout_ids[step_index]),
                    "step_row_id": int(step_row_id),
                    "candidate_row_id": None,
                    "message": f"{decode_invalid_reason(values[best])} explains {fraction:.2%} of invalid rows",
                }
            )
    return output


def _missing_label_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    candidate_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
    rollout_ids = np.asarray(reader.array("candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    actor_valid = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    oracle_label = np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_).reshape(-1)
    target_root_gain = np.asarray(reader.array("candidates/target_root_gain"), dtype=np.float32).reshape(-1)
    mask = actor_valid & ((~oracle_label) | (~np.isfinite(target_root_gain)))
    return [
        {
            "kind": "valid_candidate_missing_label",
            "severity": "error",
            "rollout_row_id": int(rollout_ids[index]),
            "step_row_id": int(step_ids[index]),
            "candidate_row_id": int(candidate_ids[index]),
            "message": "actor-valid candidate has no finite target_root_gain oracle label",
        }
        for index in np.flatnonzero(mask).tolist()
    ]


def _high_score_invalid_target_rows(
    reader: RolloutZarrStoreReader,
    cfg: RolloutSuspiciousQueryConfig,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in target_audit_rows(reader):
        score = row.get("selection_score")
        if score is None or float(score) < float(cfg.high_target_score) or bool(row.get("gt_label_valid")):
            continue
        output.append(
            {
                "kind": "high_score_invalid_gt_target",
                "severity": "warning",
                "rollout_row_id": None,
                "step_row_id": None,
                "candidate_row_id": None,
                "target_row_id": row["target_row_id"],
                "message": f"target score {float(score):.3f} but GT status={row.get('gt_match_status')}",
            }
        )
    return output


def _selected_motion_outlier_rows(
    reader: RolloutZarrStoreReader,
    cfg: RolloutSuspiciousQueryConfig,
) -> list[dict[str, object]]:
    checks = (
        ("motion_step_length_m", cfg.max_step_distance_m, ">"),
        ("motion_height_delta_m", cfg.max_height_delta_m, "abs>"),
        ("motion_backward_step_m", cfg.max_backward_step_m, ">"),
        ("motion_yaw_delta_deg", cfg.max_yaw_delta_deg, "abs>"),
    )
    output: list[dict[str, object]] = []
    for row in candidate_audit_rows(reader):
        if not bool(row.get("selected")):
            continue
        messages: list[str] = []
        for name, threshold, op in checks:
            value = row.get(name)
            if value is None:
                continue
            value_float = float(value)
            compare = abs(value_float) if op == "abs>" else value_float
            if compare > float(threshold):
                messages.append(f"{name}={value_float:.3f} exceeds {threshold:.3f}")
        if messages:
            output.append(
                {
                    "kind": "selected_motion_outlier",
                    "severity": "warning",
                    "rollout_row_id": row["rollout_row_id"],
                    "step_row_id": row["step_row_id"],
                    "candidate_row_id": row["candidate_row_id"],
                    "message": "; ".join(messages),
                }
            )
    return output


def _rollout_store_inventory_row(store_path: Path, *, validate: bool = True) -> dict[str, object]:
    try:
        root = zarr.open_group(store_path, mode="r")
    except Exception as exc:
        stat = _store_stats(store_path)
        return {
            "path": store_path.as_posix(),
            "name": store_path.name,
            "schema_status": "unreadable",
            "schema_version": None,
            "schema_id": None,
            "manifest_version": None,
            "manifest_schema_version": None,
            "manifest_profile": None,
            "manifest_config": None,
            "manifest_scene_count": None,
            "manifest_split_count": None,
            "validation_ok": False,
            "validation_status": "failed",
            "validation_error_count": 1,
            "first_error": f"{type(exc).__name__}: {exc}",
            "validation_errors": [f"{type(exc).__name__}: {exc}"],
            "required_groups_present": 0,
            "required_groups_missing": len(_required_groups()),
            "missing_required_groups": list(_required_groups()),
            **stat,
        }

    attrs = dict(root.attrs)
    schema_version = attrs.get("schema_version")
    manifest = _safe_manifest(store_path)
    validation_ok: bool | None = None
    validation_errors: list[str] = []
    validator_counts = {"validator_rollouts": None, "validator_steps": None, "validator_candidates": None}
    if validate:
        try:
            validation = RolloutZarrStoreReader(store_path).validate()
        except Exception as exc:
            validation_errors = [f"{type(exc).__name__}: {exc}"]
            validation_ok = False
        else:
            validation_ok = validation.ok
            validation_errors = list(validation.errors)
            validator_counts = {
                "validator_rollouts": int(validation.num_rollouts),
                "validator_steps": int(validation.num_steps),
                "validator_candidates": int(validation.num_candidates),
            }

    missing_required = [name for name in _required_groups() if name not in root]
    row: dict[str, object] = {
        "path": store_path.as_posix(),
        "name": store_path.name,
        "schema_status": "current" if schema_version == ROLLOUT_ZARR_SCHEMA_VERSION else "stale",
        "schema_version": schema_version,
        "schema_id": attrs.get("schema_id"),
        "created_at": attrs.get("created_at_utc") or attrs.get("created_at"),
        "manifest_path": attrs.get("manifest_path"),
        "manifest_version": attrs.get("manifest_version"),
        "manifest_schema_version": manifest.get("manifest_version") if isinstance(manifest, dict) else None,
        "manifest_profile": _manifest_profile(manifest),
        "manifest_config": _manifest_config_stem(manifest),
        "manifest_scene_count": _manifest_coverage_count(manifest, "scenes"),
        "manifest_split_count": _manifest_coverage_count(manifest, "splits"),
        "validation_ok": validation_ok,
        "validation_status": _validation_status(validation_ok),
        "validation_error_count": len(validation_errors),
        "first_error": validation_errors[0] if validation_errors else "",
        "validation_errors": validation_errors,
        "required_groups_present": len(_required_groups()) - len(missing_required),
        "required_groups_missing": len(missing_required),
        "missing_required_groups": missing_required,
        "observed_rollouts": _array_size(root, "rollouts/rollout_row_id"),
        "observed_steps": _array_size(root, "steps/step_row_id"),
        "observed_candidates": _array_size(root, "candidates/candidate_row_id"),
        "actor_action_fraction": _mask_fraction(root, "candidates/actor_action_mask"),
        "q_train_fraction": _mask_fraction(root, "candidates/q_train_mask"),
        "selected_count": _mask_count(root, "candidates/selected_mask"),
        "policy_summary": _rollout_dictionary_summary(
            root, group="rollouts", id_array="policy_id", dictionary="policy"
        ),
        "horizon_summary": _numeric_summary(root, "rollouts/horizon"),
        "branch_factor_summary": _numeric_summary(root, "rollouts/branch_factor"),
        **validator_counts,
        **_store_stats(store_path),
    }
    return row


def _schema_sort_rank(status: str) -> int:
    return {"current": 3, "stale": 2, "unreadable": 1}.get(status, 0)


def _validation_status(validation_ok: bool | None) -> str:
    if validation_ok is True:
        return "ok"
    if validation_ok is False:
        return "failed"
    return "unknown"


def _safe_manifest(store_path: Path) -> dict[str, Any]:
    try:
        manifest = read_rollout_store_manifest(store_path)
    except Exception:
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _manifest_profile(manifest: dict[str, Any]) -> str | None:
    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        return None
    writer_config = generation.get("writer_config")
    if not isinstance(writer_config, dict):
        return None
    for key in ("profile", "recipe_profile", "name"):
        value = writer_config.get(key)
        if value is not None:
            return str(value)
    return None


def _manifest_config_stem(manifest: dict[str, Any]) -> str | None:
    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        return None
    invocation = generation.get("invocation")
    if not isinstance(invocation, dict):
        return None
    config_path = invocation.get("config_path")
    return None if config_path in (None, "") else Path(str(config_path)).stem


def _manifest_coverage_count(manifest: dict[str, Any], key: str) -> int | None:
    coverage = manifest.get("source_coverage")
    if not isinstance(coverage, dict):
        return None
    value = coverage.get(key)
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list | tuple | set):
        return len(value)
    return None


def _store_stats(store_path: Path) -> dict[str, object]:
    file_count = 0
    byte_size = 0
    if store_path.exists():
        for path in store_path.rglob("*"):
            if not path.is_file():
                continue
            file_count += 1
            try:
                byte_size += path.stat().st_size
            except OSError:
                continue
    return {
        "mtime_unix": _path_mtime(store_path),
        "size_bytes": int(byte_size),
        "file_count": int(file_count),
    }


def _path_mtime(path: Path) -> float:
    try:
        return float(path.stat().st_mtime)
    except OSError:
        return 0.0


def _array_size(root: Any, path: str) -> int | None:
    try:
        return int(np.asarray(root[path]).reshape(-1).shape[0])
    except Exception:
        return None


def _mask_count(root: Any, path: str) -> int | None:
    try:
        return int(np.asarray(root[path], dtype=np.bool_).reshape(-1).sum())
    except Exception:
        return None


def _mask_fraction(root: Any, path: str) -> float | None:
    try:
        values = np.asarray(root[path], dtype=np.bool_).reshape(-1)
    except Exception:
        return None
    if values.size == 0:
        return None
    return float(values.sum()) / float(values.size)


def _rollout_dictionary_summary(root: Any, *, group: str, id_array: str, dictionary: str) -> str:
    try:
        ids = np.asarray(root[f"{group}/{id_array}"], dtype=np.int64).reshape(-1)
        values = json.loads(np.asarray(root[f"dictionaries/{dictionary}"], dtype=np.uint8).tobytes().decode("utf-8"))
    except Exception:
        return ""
    names = [
        values[int(value)] if 0 <= int(value) < len(values) else str(int(value)) for value in np.unique(ids).tolist()
    ]
    return ", ".join(names)


def _numeric_summary(root: Any, path: str) -> str:
    try:
        values = np.asarray(root[path]).reshape(-1)
    except Exception:
        return ""
    if values.size == 0:
        return ""
    unique = sorted({int(value) for value in values.tolist()})
    if len(unique) <= 4:
        return ", ".join(str(value) for value in unique)
    return f"{unique[0]}..{unique[-1]} ({len(unique)} values)"


def _mask_combination_interpretation(
    *,
    actor_action: bool,
    oracle_label: bool,
    q_train: bool,
    selected: bool,
) -> str:
    if selected and not actor_action:
        return "invalid contract: selected action is outside the actor action set"
    if q_train and not (actor_action and oracle_label):
        return "invalid contract: training label lacks actor validity or oracle supervision"
    if selected and not q_train:
        return "selected actor action without a training label; valid for execution, excluded from supervised Q_H"
    if q_train and selected:
        return "selected actor action with finite supervised Q_H label"
    if q_train:
        return "unselected actor alternative with finite supervised Q_H label"
    if actor_action and oracle_label:
        return "actor-valid oracle evidence excluded from q_train by stricter target/label requirements"
    if actor_action:
        return "actor-valid candidate without complete oracle supervision"
    return "candidate outside the hard actor action set"


def _invariant_row(
    *,
    invariant_id: str,
    category: str,
    status: str,
    summary: str,
    expected: str,
    observed: str,
    source_fields: tuple[str, ...],
    data_role: str,
    violation_count: int,
) -> dict[str, object]:
    return {
        "invariant_id": invariant_id,
        "category": category,
        "status": status,
        "summary": summary,
        "expected": expected,
        "observed": observed,
        "source_fields": source_fields,
        "data_role": data_role,
        "violation_count": int(violation_count),
    }


def _schema_manifest_invariant(root_attrs: dict[str, Any], manifest: object) -> dict[str, object]:
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    root_schema = root_attrs.get("schema_version")
    manifest_schema = manifest_dict.get("schema_version")
    manifest_version = manifest_dict.get("manifest_version")
    violations = int(root_schema != ROLLOUT_ZARR_SCHEMA_VERSION) + int(manifest_schema != root_schema)
    return _invariant_row(
        invariant_id="schema_manifest",
        category="schema",
        status="PASS" if violations == 0 else "FAIL",
        summary="Root and sidecar identify the same current rollout schema.",
        expected=f"root and manifest schema_version equal {ROLLOUT_ZARR_SCHEMA_VERSION!r}.",
        observed=f"root={root_schema!r}, manifest={manifest_schema!r}, manifest_version={manifest_version!r}.",
        source_fields=("root.attrs/schema_version", "rollout_store_manifest.json/schema_version"),
        data_role="provenance",
        violation_count=violations,
    )


def _row_identity_invariant(reader: RolloutZarrStoreReader) -> dict[str, object]:
    sources = np.asarray(reader.array("sources/source_row_id"), dtype=np.int64).reshape(-1)
    targets = np.asarray(reader.array("targets/target_row_id"), dtype=np.int64).reshape(-1)
    rollouts = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    rollout_sources = np.asarray(reader.array("rollouts/source_row_id"), dtype=np.int64).reshape(-1)
    rollout_targets = np.asarray(reader.array("rollouts/target_row_id"), dtype=np.int64).reshape(-1)
    lineage_rollouts = np.asarray(reader.array("lineage/rollout_row_id"), dtype=np.int64).reshape(-1)
    violations = (
        sources.size
        - np.unique(sources).size
        + targets.size
        - np.unique(targets).size
        + rollouts.size
        - np.unique(rollouts).size
        + int(not np.isin(rollout_sources, sources).all())
        + int(not np.isin(rollout_targets, targets).all())
        + int(not np.array_equal(lineage_rollouts, rollouts))
    )
    return _invariant_row(
        invariant_id="row_identity_lineage",
        category="lineage",
        status="PASS" if violations == 0 else "FAIL",
        summary="Source, target, rollout, and lineage identifiers form unique resolved joins.",
        expected="row ids are unique; rollout foreign keys resolve; lineage rows align one-to-one with rollouts.",
        observed=(
            f"sources={sources.size}, targets={targets.size}, rollouts={rollouts.size}, "
            f"lineage_rows={lineage_rollouts.size}, violations={violations}."
        ),
        source_fields=(
            "sources/source_row_id",
            "targets/target_row_id",
            "rollouts/rollout_row_id",
            "rollouts/source_row_id",
            "rollouts/target_row_id",
            "lineage/rollout_row_id",
        ),
        data_role="provenance",
        violation_count=int(violations),
    )


def _selected_depth_invariant(
    reader: RolloutZarrStoreReader,
    root_attrs: dict[str, Any],
) -> dict[str, object]:
    enabled = bool(root_attrs.get("selected_depth_enabled", False))
    if not enabled:
        return _invariant_row(
            invariant_id="selected_depth_alignment",
            category="evaluation artifact",
            status="WARN",
            summary="Privileged selected-depth evidence is disabled for this store.",
            expected="When enabled, one depth row aligns with each selected step transition.",
            observed="selected_depth_enabled=false; dependent views must remain unavailable.",
            source_fields=("root.attrs/selected_depth_enabled", "selected_depth/*"),
            data_role="oracle/evaluation",
            violation_count=0,
        )
    try:
        step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
        selected_ids = np.asarray(reader.array("steps/selected_candidate_row_id"), dtype=np.int64).reshape(-1)
        depth_steps = np.asarray(reader.array("selected_depth/step_row_id"), dtype=np.int64).reshape(-1)
        depth_candidates = np.asarray(reader.array("selected_depth/candidate_row_id"), dtype=np.int64).reshape(-1)
        expected_shape = (
            int(step_ids.size),
            int(root_attrs.get("selected_depth_height_px", -1)),
            int(root_attrs.get("selected_depth_width_px", -1)),
        )
        depth_shape = tuple(reader.root["selected_depth/depth_m"].shape)
        mask_shape = tuple(reader.root["selected_depth/valid_mask"].shape)
        violations = (
            int(not np.array_equal(depth_steps, step_ids))
            + int(not np.array_equal(depth_candidates, selected_ids))
            + int(depth_shape != expected_shape)
            + int(mask_shape != expected_shape)
        )
        observed = (
            f"rows={depth_steps.size}/{step_ids.size}, candidate_link={np.array_equal(depth_candidates, selected_ids)}, "
            f"depth_shape={depth_shape}, mask_shape={mask_shape}."
        )
    except (KeyError, ValueError) as exc:
        violations = 1
        observed = f"selected-depth arrays unavailable or malformed: {type(exc).__name__}: {exc}"
    return _invariant_row(
        invariant_id="selected_depth_alignment",
        category="evaluation artifact",
        status="PASS" if violations == 0 else "FAIL",
        summary="Privileged selected-depth rows align with selected factual transitions.",
        expected="step ids and selected candidate ids align one-to-one; dense depth and mask shapes match metadata.",
        observed=observed,
        source_fields=(
            "steps/step_row_id",
            "steps/selected_candidate_row_id",
            "selected_depth/step_row_id",
            "selected_depth/candidate_row_id",
            "selected_depth/depth_m",
            "selected_depth/valid_mask",
        ),
        data_role="oracle/evaluation",
        violation_count=violations,
    )


def _target_eval_invariant(
    reader: RolloutZarrStoreReader,
    root_attrs: dict[str, Any],
) -> dict[str, object]:
    enabled = bool(root_attrs.get("target_eval_crops_enabled", False))
    try:
        crop_ids = np.asarray(reader.array("target_eval_crops/crop_row_id"), dtype=np.int64).reshape(-1)
    except KeyError:
        crop_ids = np.asarray([], dtype=np.int64)
        missing_group = True
    else:
        missing_group = False
    if not enabled:
        violations = int(missing_group or crop_ids.size != 0)
        return _invariant_row(
            invariant_id="target_eval_alignment",
            category="evaluation artifact",
            status="PASS" if violations == 0 else "FAIL",
            summary="Privileged target-evaluation crops are disabled and carry no rows.",
            expected="Disabled target-evaluation storage contains zero crop rows.",
            observed=f"enabled=false, crop_rows={crop_ids.size}, group_missing={missing_group}.",
            source_fields=("root.attrs/target_eval_crops_enabled", "target_eval_crops/crop_row_id"),
            data_role="oracle/evaluation",
            violation_count=violations,
        )
    try:
        step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
        candidate_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
        crop_steps = np.asarray(reader.array("target_eval_crops/step_row_id"), dtype=np.int64).reshape(-1)
        crop_candidates = np.asarray(reader.array("target_eval_crops/candidate_row_id"), dtype=np.int64).reshape(-1)
        roles = np.asarray(reader.array("target_eval_crops/source_role_id"), dtype=np.int32).reshape(-1)
        lengths = np.asarray(reader.array("target_eval_crops/lengths"), dtype=np.int64).reshape(-1)
        mask = np.asarray(reader.array("target_eval_crops/mask"), dtype=np.bool_)
        candidate_refs = crop_candidates[roles == 1]
        current_refs = crop_candidates[roles == 0]
        violations = (
            int(missing_group)
            + int(not np.isin(crop_steps, step_ids).all())
            + int(current_refs.size > 0 and np.any(current_refs != -1))
            + int(candidate_refs.size > 0 and not np.isin(candidate_refs, candidate_ids).all())
            + int(mask.ndim != 2 or lengths.shape != (mask.shape[0],))
            + int(mask.ndim == 2 and lengths.shape == (mask.shape[0],) and not np.array_equal(mask.sum(1), lengths))
        )
        observed = (
            f"crop_rows={crop_ids.size}, current_rows={current_refs.size}, candidate_rows={candidate_refs.size}, "
            f"linked_steps={np.isin(crop_steps, step_ids).all()}."
        )
    except (KeyError, ValueError, IndexError) as exc:
        violations = 1
        observed = f"target-evaluation arrays unavailable or malformed: {type(exc).__name__}: {exc}"
    return _invariant_row(
        invariant_id="target_eval_alignment",
        category="evaluation artifact",
        status="PASS" if violations == 0 else "FAIL",
        summary="Privileged target-evaluation crops resolve to factual steps and candidates.",
        expected="crop masks match lengths; current rows use candidate -1; candidate rows resolve to factual ids.",
        observed=observed,
        source_fields=(
            "target_eval_crops/step_row_id",
            "target_eval_crops/candidate_row_id",
            "target_eval_crops/source_role_id",
            "target_eval_crops/lengths",
            "target_eval_crops/mask",
        ),
        data_role="oracle/evaluation",
        violation_count=violations,
    )


def _target_protocol_invariant(
    reader: RolloutZarrStoreReader,
    root_attrs: dict[str, Any],
) -> dict[str, object]:
    expected = str(root_attrs.get("target_protocol_version", ""))
    values = _decoded_array(reader, "lineage/target_protocol_version_id", "config")
    unique = tuple(sorted(set(values)))
    violations = int(not expected) + sum(value != expected for value in values)
    return _invariant_row(
        invariant_id="target_protocol_lineage",
        category="target protocol",
        status="PASS" if violations == 0 else "FAIL",
        summary="Every rollout uses the store-declared target protocol.",
        expected="lineage/target_protocol_version_id decodes to root target_protocol_version for every rollout.",
        observed=f"root={expected!r}, lineage_values={unique!r}.",
        source_fields=("root.attrs/target_protocol_version", "lineage/target_protocol_version_id"),
        data_role="provenance",
        violation_count=int(violations),
    )


def _q_h_invariant_rows(
    reader: RolloutZarrStoreReader,
    root_attrs: dict[str, Any],
) -> list[dict[str, object]]:
    try:
        persisted = reader.q_h_view()
        gamma = float(root_attrs.get("discount_gamma", 1.0))
        derived = reader.q_h_view(discount_gamma=gamma)
    except (KeyError, ValueError) as exc:
        observed = f"Q_H cache unavailable or malformed: {type(exc).__name__}: {exc}"
        return [
            _invariant_row(
                invariant_id=invariant_id,
                category="derived Q_H",
                status="FAIL",
                summary=summary,
                expected=expected,
                observed=observed,
                source_fields=source_fields,
                data_role="derived training data",
                violation_count=1,
            )
            for invariant_id, summary, expected, source_fields in (
                (
                    "q_h_padding",
                    "Q_H padding is masked and carries no labels.",
                    "candidate id -1 implies false masks and NaN one-step labels.",
                    ("q_h/candidate_row_id", "q_h/valid_action_mask", "q_h/q_train_mask"),
                ),
                (
                    "q_h_selected_transition",
                    "Q_H TD rows link to factual selected transitions.",
                    "selected candidate, next-step, terminal, reward, and discount metadata align.",
                    ("q_h/td_selected_candidate_row_id", "q_h/td_reward", "q_h/td_discount"),
                ),
                (
                    "q_h_factual_consistency",
                    "Persisted Q_H equals the factual-table projection.",
                    "every persisted Q_H array equals the deterministic derivation from factual tables.",
                    ("steps/*", "candidates/*", "rollouts/*", "targets/*", "q_h/*"),
                ),
            )
        ]

    padded = np.asarray(persisted["candidate_row_id"], dtype=np.int64) < 0
    valid = np.asarray(persisted["valid_action_mask"], dtype=np.bool_)
    q_train = np.asarray(persisted["q_train_mask"], dtype=np.bool_)
    rri = np.asarray(persisted["one_step_target_rri"], dtype=np.float64)
    gain = np.asarray(persisted["one_step_target_root_gain"], dtype=np.float64)
    padding_violations = int(np.count_nonzero(padded & (valid | q_train | np.isfinite(rri) | np.isfinite(gain))))
    padding_row = _invariant_row(
        invariant_id="q_h_padding",
        category="derived Q_H",
        status="PASS" if padding_violations == 0 else "FAIL",
        summary="Q_H padding is masked and carries no labels.",
        expected="candidate id -1 implies false valid/q_train masks and NaN one-step labels.",
        observed=f"padded_cells={int(padded.sum())}, violating_cells={padding_violations}.",
        source_fields=(
            "q_h/candidate_row_id",
            "q_h/valid_action_mask",
            "q_h/q_train_mask",
            "q_h/one_step_target_rri",
            "q_h/one_step_target_root_gain",
        ),
        data_role="derived training data",
        violation_count=padding_violations,
    )

    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    selected_ids = np.asarray(reader.array("steps/selected_candidate_row_id"), dtype=np.int64).reshape(-1)
    q_step_ids = np.asarray(persisted["state_step_row_id"], dtype=np.int64).reshape(-1)
    q_selected_ids = np.asarray(persisted["td_selected_candidate_row_id"], dtype=np.int64).reshape(-1)
    terminal = np.asarray(persisted["td_terminal_mask"], dtype=np.bool_).reshape(-1)
    discount = np.asarray(persisted["td_discount"], dtype=np.float64).reshape(-1)
    q_group_attrs = dict(reader.root["q_h"].attrs)
    linkage_violations = (
        int(not np.array_equal(q_step_ids, step_ids))
        + int(not np.array_equal(q_selected_ids, selected_ids))
        + int(np.count_nonzero(terminal & (discount != 0.0)))
        + int(q_group_attrs.get("td_semantics") != Q_H_TD_SEMANTICS)
        + int(q_group_attrs.get("reward_metric") != Q_H_REWARD_METRIC)
        + int(float(q_group_attrs.get("discount_gamma", float("nan"))) != float(root_attrs.get("discount_gamma", 1.0)))
    )
    transition_row = _invariant_row(
        invariant_id="q_h_selected_transition",
        category="derived Q_H",
        status="PASS" if linkage_violations == 0 else "FAIL",
        summary="Q_H TD rows link to factual selected transitions and declared reward/discount semantics.",
        expected=(
            f"step and selected ids align; terminal discount is zero; td_semantics={Q_H_TD_SEMANTICS!r}; "
            f"reward_metric={Q_H_REWARD_METRIC!r}."
        ),
        observed=(
            f"states={q_step_ids.size}, selected_links={q_selected_ids.size}, terminal_rows={int(terminal.sum())}, "
            f"reward_metric={q_group_attrs.get('reward_metric')!r}, gamma={q_group_attrs.get('discount_gamma')!r}."
        ),
        source_fields=(
            "steps/step_row_id",
            "steps/selected_candidate_row_id",
            "q_h/state_step_row_id",
            "q_h/td_selected_candidate_row_id",
            "q_h/td_reward",
            "q_h/td_next_step_row_id",
            "q_h/td_terminal_mask",
            "q_h/td_discount",
            "q_h.attrs/reward_metric",
        ),
        data_role="derived training data",
        violation_count=int(linkage_violations),
    )

    mismatches = tuple(
        name
        for name in Q_H_ARRAY_NAMES
        if name not in persisted or name not in derived or not _arrays_equal(persisted[name], derived[name])
    )
    factual_row = _invariant_row(
        invariant_id="q_h_factual_consistency",
        category="derived Q_H",
        status="PASS" if not mismatches else "FAIL",
        summary="Persisted Q_H equals the deterministic factual-table projection.",
        expected="every persisted Q_H array matches the view derived from steps, candidates, rollouts, and targets.",
        observed=f"checked_arrays={len(Q_H_ARRAY_NAMES)}, mismatched_arrays={mismatches!r}.",
        source_fields=("steps/*", "candidates/*", "rollouts/*", "targets/*", "q_h/*"),
        data_role="derived training data",
        violation_count=len(mismatches),
    )
    return [padding_row, transition_row, factual_row]


def _arrays_equal(left: np.ndarray, right: np.ndarray) -> bool:
    left_array = np.asarray(left)
    right_array = np.asarray(right)
    if left_array.shape != right_array.shape or left_array.dtype != right_array.dtype:
        return False
    if np.issubdtype(left_array.dtype, np.floating):
        return bool(np.array_equal(left_array, right_array, equal_nan=True))
    return bool(np.array_equal(left_array, right_array))


def _policy_cohort_projection_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    source_ids = np.asarray(reader.array("rollouts/source_row_id"), dtype=np.int64).reshape(-1)
    target_ids = np.asarray(reader.array("rollouts/target_row_id"), dtype=np.int64).reshape(-1)
    policies = _decoded_array(reader, "rollouts/policy_id", "policy")
    source_rows = np.asarray(reader.array("sources/source_row_id"), dtype=np.int64).reshape(-1)
    source_keys = _decoded_array(reader, "sources/sample_key_id", "source_key")
    source_indices = np.asarray(reader.array("sources/sample_index"), dtype=np.int64).reshape(-1)
    source_by_id = {
        int(row_id): (source_keys[index] or f"source_row:{int(row_id)}", int(source_indices[index]))
        for index, row_id in enumerate(source_rows.tolist())
    }
    target_rows = np.asarray(reader.array("targets/target_row_id"), dtype=np.int64).reshape(-1)
    target_names = _decoded_array(reader, "targets/target_id", "target")
    target_by_id = {int(row_id): target_names[index] for index, row_id in enumerate(target_rows.tolist())}
    candidate_configs = _decoded_array(reader, "lineage/candidate_config_id", "config")
    oracle_configs = _decoded_array(reader, "lineage/oracle_config_id", "config")
    rollout_configs = _decoded_array(reader, "lineage/rollout_config_id", "config")
    schedules = _decoded_array(reader, "lineage/branch_schedule_id", "config")
    protocols = _decoded_array(reader, "lineage/target_protocol_version_id", "config")
    horizons = np.asarray(reader.array("rollouts/horizon"), dtype=np.int64).reshape(-1)
    branch_factors = np.asarray(reader.array("rollouts/branch_factor"), dtype=np.int64).reshape(-1)
    beam_widths = np.asarray(reader.array("rollouts/beam_width"), dtype=np.int64).reshape(-1)
    temperatures = np.asarray(reader.array("rollouts/temperature"), dtype=np.float64).reshape(-1)
    random_seeds = np.asarray(reader.array("rollouts/random_seed"), dtype=np.int64).reshape(-1)
    chain_ids = np.asarray(reader.array("rollouts/chain_id"), dtype=np.int64).reshape(-1)
    final_rri = np.asarray(reader.array("rollouts/final_cumulative_target_rri"), dtype=np.float64).reshape(-1)
    final_gain = np.asarray(reader.array("rollouts/final_cumulative_target_root_gain"), dtype=np.float64).reshape(-1)
    scenes = [rollout_at(reader, index).scene for index in range(rollout_ids.size)]
    manifest_payload = reader.manifest()
    root_attrs = manifest_payload.get("root_attrs")
    manifest = manifest_payload.get("manifest")
    root_attrs = root_attrs if isinstance(root_attrs, dict) else {}
    manifest = manifest if isinstance(manifest, dict) else {}
    generation = manifest.get("generation")
    generation = generation if isinstance(generation, dict) else {}
    shard = generation.get("shard")
    shard = shard if isinstance(shard, dict) else {}
    binding = shard.get("campaign_binding")
    binding = binding if isinstance(binding, dict) else {}

    rows: list[dict[str, object]] = []
    for index, rollout_row_id in enumerate(rollout_ids.tolist()):
        source_key, source_index = source_by_id.get(int(source_ids[index]), (f"source_row:{source_ids[index]}", -1))
        row: dict[str, object] = {
            "rollout_row_id": int(rollout_row_id),
            "chain_id": int(chain_ids[index]),
            "source_row_id": int(source_ids[index]),
            "source_sample_index": source_index,
            "source_sample_key": source_key,
            "target_row_id": int(target_ids[index]),
            "target_id": target_by_id.get(int(target_ids[index]), f"target_row:{target_ids[index]}"),
            "scene": scenes[index],
            "target_protocol": protocols[index],
            "horizon": int(horizons[index]),
            "acquisition_budget_steps": int(horizons[index]),
            "branch_factor": int(branch_factors[index]),
            "beam_width": int(beam_widths[index]),
            "temperature": _finite_or_none(temperatures[index]),
            "random_seed": int(random_seeds[index]),
            "temperature_applicable": _condition_applicable(
                field="temperature", policy=policies[index], recipe=rollout_configs[index]
            ),
            "random_seed_applicable": _condition_applicable(
                field="random_seed", policy=policies[index], recipe=rollout_configs[index]
            ),
            "candidate_config": candidate_configs[index],
            "oracle_config": oracle_configs[index],
            "branch_schedule": schedules[index],
            "policy": policies[index],
            "rollout_recipe": rollout_configs[index],
            "manifest_sha256": root_attrs.get("manifest_sha256"),
            "writer_config_hash": shard.get("writer_config_hash") or "legacy_store_local",
            **{
                field: binding.get(field)
                for field in ("campaign_id", "plan_hash", "work_unit_hash", "profile_hash", "explicit_target_hash")
            },
            "final_cumulative_target_rri": _finite_or_none(final_rri[index]),
            "final_cumulative_target_root_gain": _finite_or_none(final_gain[index]),
        }
        cohort_key = json.dumps({field: row[field] for field in _POLICY_COHORT_KEY_FIELDS}, sort_keys=True)
        row["cohort_key"] = cohort_key
        row["cohort_id"] = _cohort_id_from_key(cohort_key)
        rows.append(row)

    recipes_by_policy: dict[str, set[str]] = {}
    for row in rows:
        recipes_by_policy.setdefault(str(row["policy"]), set()).add(str(row["rollout_recipe"]))
    for row in rows:
        policy = str(row["policy"])
        recipe = str(row["rollout_recipe"])
        row["comparison_label"] = policy if len(recipes_by_policy[policy]) == 1 else f"{policy}@{recipe[:12]}"
    return rows


def _decoded_array(reader: RolloutZarrStoreReader, path: str, dictionary: str) -> list[str]:
    ids = np.asarray(reader.array(path), dtype=np.int64).reshape(-1)
    values = _read_string_array(reader, f"dictionaries/{dictionary}")
    return [values[int(value)] if 0 <= int(value) < len(values) else "" for value in ids.tolist()]


def _condition_applicable(*, field: str, policy: object, recipe: object) -> bool:
    """Derive stochastic-condition applicability from the frozen policy names."""

    policy_name = str(policy)
    recipe_name = str(recipe)
    if field == "temperature":
        return policy_name == "temperature_softmax" or "temperature_softmax" in recipe_name
    if field == "random_seed":
        return policy_name in {"random", "random_valid", "temperature_softmax"} or "random" in recipe_name
    raise ValueError(f"Unsupported headroom condition field {field!r}.")


def _cohort_ineligibility_reason(labels: tuple[str, ...], duplicates: tuple[str, ...]) -> str:
    if len(labels) < 2:
        return "only one policy/recipe is represented for this exact cohort"
    if duplicates:
        return f"multiple rollout chains make policy/recipe rows ambiguous: {', '.join(duplicates)}"
    return "not comparable"


def _nearest_policy_mismatch_rows(
    rows: list[dict[str, object]],
    labels: tuple[str, ...],
    grouped: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    by_label = {label: [row for row in rows if row["comparison_label"] == label] for label in labels}
    for left_label, right_label in combinations(labels, 2):
        exact_match = any(
            {str(row["comparison_label"]) for row in cohort_rows}.issuperset({left_label, right_label})
            for cohort_rows in grouped.values()
        )
        if exact_match:
            continue
        candidates: list[tuple[int, int, int, dict[str, object], dict[str, object], tuple[str, ...]]] = []
        for left in by_label[left_label]:
            for right in by_label[right_label]:
                mismatches = tuple(field for field in _POLICY_COHORT_KEY_FIELDS if left.get(field) != right.get(field))
                candidates.append(
                    (
                        len(mismatches),
                        int(left["rollout_row_id"]),
                        int(right["rollout_row_id"]),
                        left,
                        right,
                        mismatches,
                    )
                )
        if not candidates:
            continue
        _count, _left_id, _right_id, left, right, mismatches = min(
            candidates,
            key=lambda value: (value[0], value[1], value[2]),
        )
        output.append(
            {
                "policy_a": left_label,
                "policy_b": right_label,
                "mismatched_fields": mismatches,
                "mismatch_count": len(mismatches),
                "nearest_policy_a_rollout_row_id": int(left["rollout_row_id"]),
                "nearest_policy_b_rollout_row_id": int(right["rollout_row_id"]),
                "policy_a_values": {field: left[field] for field in mismatches},
                "policy_b_values": {field: right[field] for field in mismatches},
            }
        )
    return output


def _cohort_id_from_key(cohort_key: str) -> str:
    digest = hashlib.sha256(cohort_key.encode("utf-8")).hexdigest()[:12]
    return f"cohort-{digest}"


def _paired_bootstrap_interval(
    delta: np.ndarray,
    *,
    bootstrap_samples: int,
    confidence: float,
    seed: int,
) -> tuple[float | None, float | None]:
    values = np.asarray(delta, dtype=np.float64).reshape(-1)
    if values.size < 3:
        return None, None
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(bootstrap_samples, values.size))
    estimates = np.median(values[indices], axis=1)
    tail = (1.0 - confidence) / 2.0
    return float(np.quantile(estimates, tail)), float(np.quantile(estimates, 1.0 - tail))


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
        lengths.append(
            float(
                sum(
                    np.linalg.norm(np.asarray(points[index + 1]) - np.asarray(points[index]))
                    for index in range(len(points) - 1)
                )
            )
        )
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


def _decoded_id(value: int, *, names: Mapping[int, str], prefix: str) -> str:
    if value < 0:
        return "unknown"
    return str(names.get(value) or f"{prefix}_{value}")


def _temporal_group_value(row: Mapping[str, object], field: str) -> object:
    if field == "budget_configuration":
        existing = row.get(field)
        if existing not in (None, ""):
            return existing
        return " | ".join(f"{name}={row.get(name, 'unknown')}" for name in ("horizon", "branch_factor", "beam_width"))
    value = row.get(field)
    return "unknown" if value in (None, "") else value


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


def _finite_or_none(value: object) -> float | None:
    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return None
    return value_float if np.isfinite(value_float) else None


def _finite_summary(values: np.ndarray) -> dict[str, float | None]:
    """Return deterministic summaries for finite values."""

    if values.size == 0:
        return dict.fromkeys(("mean", "std", "median", "q25", "q75", "min", "max"))
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "median": float(np.median(values)),
        "q25": float(np.quantile(values, 0.25)),
        "q75": float(np.quantile(values, 0.75)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def _nonnegative_int(*values: object) -> int | None:
    for value in values:
        try:
            normalized = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            continue
        if normalized >= 0:
            return normalized
    return None


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _coverage_ratio(numerator: int | None, denominator: int | None) -> float | None:
    """Return coverage only when both counts are a valid bounded claim."""

    if numerator is None or denominator is None or denominator <= 0 or numerator < 0 or numerator > denominator:
        return None
    return float(numerator) / float(denominator)


def _selected_competition_rank(
    values: np.ndarray,
    *,
    valid_mask: np.ndarray,
    selected_index: int,
) -> tuple[int | None, int, float | None, np.ndarray]:
    """Rank one selected value over finite actor-valid alternatives.

    Equal values share the same one-based competition rank. The returned
    denominator contains only finite rows admitted by ``valid_mask``; an
    invalid, absent, or non-finite selection has no rank.
    """

    flattened = np.asarray(values, dtype=np.float64).reshape(-1)
    valid = np.asarray(valid_mask, dtype=np.bool_).reshape(-1)
    if flattened.shape != valid.shape:
        raise ValueError("Rank values and validity mask must have identical one-dimensional shapes.")
    finite_valid = valid & np.isfinite(flattened)
    alternatives = flattened[finite_valid]
    if selected_index < 0 or selected_index >= flattened.size or not bool(finite_valid[selected_index]):
        return None, int(alternatives.size), None, alternatives
    selected_value = float(flattened[selected_index])
    rank = 1 + int(np.count_nonzero(alternatives > selected_value))
    return rank, int(alternatives.size), selected_value, alternatives


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


__all__ = [
    "RolloutSuspiciousQueryConfig",
    "candidate_audit_rows",
    "candidate_flow_rows",
    "candidate_group_summary_rows",
    "candidate_collision_support_rows",
    "candidate_composition_rows",
    "candidate_proposal_calibration_rows",
    "deterministic_candidate_display_sample",
    "candidate_result_diagnostic_counts",
    "comparable_policy_cohorts",
    "decode_invalid_reason",
    "decode_position_id",
    "decode_strategy_id",
    "decode_target_invalid_reason",
    "discover_rollout_store_paths",
    "mask_combination_rows",
    "paired_policy_comparison_rows",
    "root_relative_candidate_rows",
    "rollout_store_inventory_rows",
    "rollout_statistics",
    "q_h_evidence_rows",
    "runtime_storage_statistics",
    "rollout_step_objective_rows",
    "rollout_endpoint_metric_summary",
    "selected_candidate_rank_rows",
    "selected_depth_preview",
    "selected_depth_summary_rows",
    "store_invariant_rows",
    "suspicious_rollout_rows",
    "target_audit_rows",
    "temporal_metric_summary_rows",
    "validity_waterfall_rows",
]
