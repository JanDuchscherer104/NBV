"""Read-only inspection helpers for rollout Zarr stores.

This module keeps Streamlit, CLI, and tests away from ad hoc Zarr joins. The
helpers return plain dictionaries and NumPy-backed scalar values so UI code can
choose its own rendering library without owning rollout-store semantics.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
import zarr
from scipy.spatial import cKDTree

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
from .scientific_audit import (
    AuditComparisonProtocol,
    AuditReadiness,
    AuditStatus,
    EndpointAuditRow,
    EquivalenceVerdict,
    MandatoryCohortStatus,
    PolicySemanticRole,
    RowEvaluationStatus,
    ScientificAuditArtifact,
    ValidityAuditRow,
    named_sha256_context_hash,
    verify_scientific_audit_sha256,
)
from .trace import INVALID_REASON_CODES, INVALID_REASON_VERSION, _candidate_invalid_reasons
from .zarr_store import (
    Q_H_ARRAY_NAMES,
    Q_H_REWARD_METRIC,
    Q_H_TD_SEMANTICS,
    ROLLOUT_ZARR_SCHEMA_VERSION,
    RolloutZarrStoreReader,
    _required_groups,
)

_TARGET_INVALID_REASON_NAMES = {int(code): name for name, code in TARGET_INVALID_REASON_CODES.items()}
_STRATEGY_NAMES = {candidate_strategy_id(mode): mode.value for mode in ViewDirectionMode}
CANDIDATE_GENERATION_COHORT_FIELDS = (
    "policy",
    "horizon",
    "acquisition_budget_steps",
    "branch_factor",
    "beam_width",
    "temperature",
    "candidate_config",
    "rollout_config",
    "branch_schedule",
)
_POLICY_COHORT_KEY_FIELDS = (
    "source_sample_key",
    "target_id",
    "target_protocol",
    "evaluation_horizon",
    "acquisition_budget_steps",
    "candidate_config",
    "oracle_config",
)
_POLICY_TREATMENT_FIELDS = ("branch_schedule", "branch_factor", "beam_width")
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

# The project-wide mesh-supervised ASE target is a fixed experimental reference,
# not a claim that every local checkout has materialized every raw tar shard.
_FULL_GT_MESH_ASE_SCENE_COUNT = 100
_FULL_GT_MESH_ASE_SNIPPET_COUNT = 4_608
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
_POLICY_EFFECT_CONTRASTS = {
    "raw_qh": (PolicySemanticRole.LEARNED_ONE_STEP, PolicySemanticRole.LEARNED_QH),
    "delta_look": (PolicySemanticRole.ORACLE_ONE_STEP, PolicySemanticRole.ORACLE_LOOKAHEAD),
}


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
    """Return lightweight selected-store facts for a rollout-inspection header.

    The summary reads manifest/root metadata plus compact target-to-rollout
    linkage. It deliberately avoids candidate and step audit projections, but
    exposes the target-task coverage needed to interpret the stored traces.
    """

    manifest_payload = reader.manifest() if manifest_payload is None else manifest_payload
    root_attrs = manifest_payload.get("root_attrs")
    manifest = manifest_payload.get("manifest")
    root_attrs = root_attrs if isinstance(root_attrs, dict) else {}
    manifest = manifest if isinstance(manifest, dict) else {}
    counts = manifest.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    coverage = manifest.get("source_coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    scene_counts = coverage.get("scene_counts")
    source_scenes = len(scene_counts) if isinstance(scene_counts, dict) else None
    source_rows = _nonnegative_int(coverage.get("num_source_rows"))
    rollouts = _nonnegative_int(counts.get("rollouts"), root_attrs.get("num_rollouts"))
    steps = _nonnegative_int(counts.get("steps"), root_attrs.get("num_steps"))
    candidates = _nonnegative_int(counts.get("candidates"), root_attrs.get("num_candidates"))
    target_tasks = _nonnegative_int(counts.get("targets"), root_attrs.get("num_targets"))
    target_coverage = (
        _target_rollout_header_coverage(reader)
        if target_tasks is not None
        else _unavailable_target_rollout_header_coverage()
    )
    source_footprint = _source_footprint(coverage)
    storage = runtime_storage_statistics(reader.store_dir, candidate_count=candidates or 0)

    return {
        "source_scenes": source_scenes,
        "source_rows": source_rows,
        "source_snippets": source_footprint.get("snippet_count") if source_footprint is not None else None,
        "source_footprint_by_scene": source_footprint.get("by_scene") if source_footprint is not None else None,
        "reference_scene_count": _FULL_GT_MESH_ASE_SCENE_COUNT,
        "reference_snippet_count": _FULL_GT_MESH_ASE_SNIPPET_COUNT,
        "source_scene_coverage": _ratio(source_scenes, _FULL_GT_MESH_ASE_SCENE_COUNT),
        "source_snippet_coverage": _ratio(
            source_footprint.get("snippet_count") if source_footprint is not None else None,
            _FULL_GT_MESH_ASE_SNIPPET_COUNT,
        ),
        "source_split_counts": _split_counts(coverage.get("split_counts")),
        "rollout_split_counts": _rollout_split_counts(reader),
        "horizon": _nonnegative_int(root_attrs.get("q_h_horizon")),
        "rollouts": rollouts,
        "steps": steps,
        "candidates": candidates,
        "candidate_capacity": _nonnegative_int(counts.get("q_h_max_candidates"), root_attrs.get("q_h_max_candidates")),
        "target_protocol": _nonempty_text(root_attrs.get("target_protocol_version")),
        "steps_per_scene": _ratio(steps, source_scenes),
        "snippets_per_scene": _snippets_per_scene(coverage),
        "target_tasks": target_tasks,
        **target_coverage,
        "rollouts_per_source_row": _ratio(rollouts, source_rows),
        "candidates_per_step": _ratio(candidates, steps),
        "store_files": storage["file_count"],
        "store_bytes": storage["total_bytes"],
        "bytes_per_rollout": _ratio(int(storage["total_bytes"]), rollouts),
        "bytes_per_step": _ratio(int(storage["total_bytes"]), steps),
        "bytes_per_candidate": storage["bytes_per_candidate"],
        "q_h_return_semantics": _nonempty_text(root_attrs.get("return_semantics")),
        "discount_gamma": _nonnegative_float(root_attrs.get("discount_gamma")),
    }


def _source_footprint(coverage: dict[str, Any]) -> dict[str, object] | None:
    """Return unique source snippet counts and their scene decomposition.

    The persisted manifest may have several source-row references to the same
    source snippet. Coverage therefore uses the unique ``(scene, snippet)``
    population rather than treating source rows as dataset windows.
    """

    sources = coverage.get("sources")
    if not isinstance(sources, list) or not sources:
        return None
    snippets_by_scene: dict[str, set[str]] = {}
    rows_by_scene: Counter[str] = Counter()
    for source in sources:
        if not isinstance(source, dict):
            return None
        scene = _nonempty_text(source.get("scene_id"))
        snippet = _nonempty_text(source.get("snippet_id"))
        if scene is None or snippet is None:
            return None
        rows_by_scene[scene] += 1
        snippets_by_scene.setdefault(scene, set()).add(snippet)
    return {
        "snippet_count": sum(len(snippets) for snippets in snippets_by_scene.values()),
        "by_scene": {
            scene: {
                "source_rows": int(rows_by_scene[scene]),
                "source_snippets": len(snippets),
            }
            for scene, snippets in sorted(snippets_by_scene.items())
        },
    }


def _target_rollout_header_coverage(reader: RolloutZarrStoreReader) -> dict[str, object]:
    """Summarize persisted target-task validity and rollout coverage by scene.

    Target rows do not persist their source scene directly. The scene view
    therefore follows the validated target-to-rollout link and names its scope
    explicitly as *represented scenes* in the presentation layer.
    """

    unavailable = _unavailable_target_rollout_header_coverage()
    try:
        target_ids = np.asarray(reader.array("targets/target_row_id"), dtype=np.int64).reshape(-1)
        target_valid = np.asarray(reader.array("targets/target_valid_mask"), dtype=np.bool_).reshape(-1)
        gt_label_valid = np.asarray(reader.array("targets/gt_label_valid_mask"), dtype=np.bool_).reshape(-1)
        rollout_target_ids = np.asarray(reader.array("rollouts/target_row_id"), dtype=np.int64).reshape(-1)
        rollout_scene_ids = np.asarray(reader.array("rollouts/scene_id"), dtype=np.int64).reshape(-1)
        scene_names = _read_string_array(reader, "dictionaries/scene")
    except (KeyError, TypeError, ValueError):
        return unavailable
    if target_ids.shape != target_valid.shape or target_ids.shape != gt_label_valid.shape:
        return unavailable
    if rollout_target_ids.shape != rollout_scene_ids.shape:
        return unavailable

    actor_valid_ids = {int(target_id) for target_id, valid in zip(target_ids, target_valid, strict=True) if valid}
    supervised_ids = {
        int(target_id)
        for target_id, valid, label_valid in zip(target_ids, target_valid, gt_label_valid, strict=True)
        if valid and label_valid
    }
    known_target_ids = {int(target_id) for target_id in target_ids.tolist()}
    rollout_target_id_set = {int(target_id) for target_id in rollout_target_ids.tolist()}
    target_ids_by_scene: dict[str, set[int]] = {}
    for target_id, scene_id in zip(rollout_target_ids, rollout_scene_ids, strict=True):
        if int(target_id) not in known_target_ids or not 0 <= int(scene_id) < len(scene_names):
            continue
        target_ids_by_scene.setdefault(scene_names[int(scene_id)], set()).add(int(target_id))

    def per_scene_count(target_id_set: set[int]) -> tuple[int, float, int] | None:
        counts_by_scene = [len(targets & target_id_set) for targets in target_ids_by_scene.values()]
        return _min_median_max(counts_by_scene)

    return {
        "actor_valid_targets": len(actor_valid_ids),
        "gt_supervised_targets": len(supervised_ids),
        "actor_valid_targets_with_rollouts": len(actor_valid_ids & rollout_target_id_set),
        "gt_supervised_targets_with_rollouts": len(supervised_ids & rollout_target_id_set),
        "target_tasks_per_scene": per_scene_count(known_target_ids),
        "actor_valid_targets_per_scene": per_scene_count(actor_valid_ids),
        "actor_valid_targets_with_rollouts_per_scene": per_scene_count(actor_valid_ids & rollout_target_id_set),
    }


def _unavailable_target_rollout_header_coverage() -> dict[str, None]:
    """Preserve stable target-coverage keys when the compact linkage is absent."""

    return {
        "actor_valid_targets": None,
        "gt_supervised_targets": None,
        "actor_valid_targets_with_rollouts": None,
        "gt_supervised_targets_with_rollouts": None,
        "target_tasks_per_scene": None,
        "actor_valid_targets_per_scene": None,
        "actor_valid_targets_with_rollouts_per_scene": None,
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
) -> list[dict[str, object]]:
    """Return candidate rows joined with candidate-generation diagnostics."""
    rows: list[dict[str, object]] = []
    oracle_label_mask = np.asarray(reader.array("candidates/oracle_label_mask"), dtype=np.bool_)
    q_train_mask = np.asarray(reader.array("candidates/q_train_mask"), dtype=np.bool_)
    strategy_ids = np.asarray(reader.array("candidates/strategy_id"), dtype=np.int64)
    target_log_error_gain = np.asarray(reader.array("candidates/target_log_error_gain"))
    target_pm_dist_before = np.asarray(reader.array("candidates/target_pm_dist_before"))
    target_pm_dist_after = np.asarray(reader.array("candidates/target_pm_dist_after"))
    path_collision_mask = np.asarray(reader.array("candidate_diagnostics/path_collision_mask"), dtype=np.bool_)
    free_space_margin_m = np.asarray(reader.array("candidate_diagnostics/free_space_margin_m"))
    motion_height_delta_m = np.asarray(reader.array("candidate_diagnostics/motion_height_delta_m"))
    motion_backward_step_m = np.asarray(reader.array("candidate_diagnostics/motion_backward_step_m"))
    motion_yaw_delta_deg = np.asarray(reader.array("candidate_diagnostics/motion_yaw_delta_deg"))
    target_bearing_yaw_deg = np.asarray(reader.array("candidate_diagnostics/target_bearing_yaw_deg"))
    generation_cohorts = _candidate_generation_cohort_by_rollout(reader)
    target_centers = {
        target.target_row_id: np.asarray(target.center_world, dtype=np.float64) for target in target_rows(reader)
    }
    reason_code_version = _nonempty_text(reader.root.attrs.get("reason_code_version"))
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        root_center = np.asarray(rollout.root_pose_world[9:12], dtype=np.float64)
        target_center = target_centers.get(rollout.target_row_id)
        root_to_target = None if target_center is None else target_center - root_center
        generation_cohort = generation_cohorts[rollout.rollout_row_id]
        for step in rollout_steps(reader, rollout):
            if step_row_id is not None and step.step_row_id != int(step_row_id):
                continue
            for local, row in enumerate(step.candidate_row_positions.tolist()):
                if limit is not None and len(rows) >= max(0, int(limit)):
                    return rows
                strategy_id = int(strategy_ids[row])
                pose = step.pose_world_cam[local]
                relative = np.asarray(pose[9:12], dtype=np.float64) - root_center
                rows.append(
                    {
                        "candidate_row_id": int(step.candidate_row_ids[local]),
                        "rollout_row_id": rollout.rollout_row_id,
                        "step_row_id": step.step_row_id,
                        "step_index": step.step_index,
                        "shell_index": int(step.shell_indices[local]),
                        "compact_valid_index": int(step.compact_valid_indices[local]),
                        "scene": rollout.scene,
                        "split": rollout.split,
                        **generation_cohort,
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
                        "reason_code_version": reason_code_version,
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
                        "root_to_target_x_m": None if root_to_target is None else float(root_to_target[0]),
                        "root_to_target_y_m": None if root_to_target is None else float(root_to_target[1]),
                        "root_to_target_z_m": None if root_to_target is None else float(root_to_target[2]),
                        "coordinate_frame": "root-centered ARIA world (RIGHT_HAND_Z_UP)",
                        "units": "m",
                        "mesh_distance_m": _finite_or_none(step.mesh_distance_m[local]),
                        "path_min_clearance_m": _finite_or_none(step.path_min_clearance_m[local]),
                        "path_collision": bool(path_collision_mask[row]),
                        "free_space_margin_m": _finite_or_none(free_space_margin_m[row]),
                        "motion_step_length_m": _finite_or_none(step.motion_step_length_m[local]),
                        "motion_height_delta_m": _finite_or_none(motion_height_delta_m[row]),
                        "motion_backward_step_m": _finite_or_none(motion_backward_step_m[row]),
                        "motion_yaw_delta_deg": _finite_or_none(motion_yaw_delta_deg[row]),
                        "target_distance_m": _finite_or_none(step.target_distance_m[local]),
                        "target_bearing_yaw_deg": _finite_or_none(target_bearing_yaw_deg[row]),
                    }
                )
    return rows


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
    """Summarize the fixed reconstruction/selection metric plan.

    The plan deliberately excludes fanout and invalidity metrics, which belong
    to validity/support evidence. Every supported metric is returned even when
    it is entirely missing so callers can distinguish absence from filtering.
    """

    source_rows = rollout_step_objective_rows(source) if hasattr(source, "array") else [dict(row) for row in source]
    rollout_count = len({int(row["rollout_row_id"]) for row in source_rows if row.get("rollout_row_id") is not None})
    endpoints = reconstruction_endpoint_rows(source_rows)
    output: list[dict[str, object]] = []
    for family, metric, label in _RECONSTRUCTION_METRIC_SPECS:
        values = [_finite_or_none(row.get(metric)) for row in source_rows]
        finite = np.asarray([value for value in values if value is not None], dtype=np.float64)
        endpoint_values = [_finite_or_none(row.get(metric)) for row in endpoints]
        finite_endpoints = np.asarray(
            [value for value in endpoint_values if value is not None],
            dtype=np.float64,
        )
        endpoint_count = len(endpoint_values)
        finite_endpoint_count = int(finite_endpoints.size)
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
                "endpoint_total_count": endpoint_count,
                "endpoint_finite_count": finite_endpoint_count,
                "endpoint_missing_count": endpoint_count - finite_endpoint_count,
                **{f"endpoint_{key}": value for key, value in _finite_summary(finite_endpoints).items()},
            }
        )
    return output


def reconstruction_endpoint_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Return one terminal factual row per rollout with fixed endpoint metrics."""

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
    """Summarize terminal reconstruction evidence over exact display strata."""

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
    """Derive discounted selected-chain return under the persisted contract."""

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
        if any(reward is None for reward in rewards):
            discounted = None
        else:
            discounted = float(sum((gamma**index) * float(reward) for index, reward in enumerate(rewards)))
        first = ordered[0]
        output.append(
            {
                "rollout_row_id": rollout_row_id,
                "scene": first.get("scene"),
                "policy": first.get("policy"),
                "horizon": first.get("horizon"),
                "discount_gamma": gamma,
                "discounted_return": discounted,
            }
        )
    return {"available": True, "reason": "derived from factual selected_target_root_gain steps", "rows": output}


def exact_policy_role_rows(cohort_rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Attach semantic roles only to exact persisted policy/schedule identifiers."""

    output: list[dict[str, object]] = []
    for source_row in cohort_rows:
        row = dict(source_row)
        identifier = (str(row.get("policy", "")), str(row.get("branch_schedule", "")))
        role = _EXACT_POLICY_ROLE_IDENTIFIERS.get(identifier)
        if role is not None:
            output.append({**row, "semantic_role": role, "role_identifier": f"{identifier[0]} / {identifier[1]}"})
    return output


def oracle_headroom_evidence(
    projection: Mapping[str, object],
    *,
    epsilon: float = 1e-8,
) -> dict[str, object]:
    """Compute diagnostic persisted-return headroom proxies.

    These rows use persisted cumulative root gain, not independently audited
    endpoint $J$, and are explicitly labelled ``diagnostic_proxy``. Target RRI
    is retained as a diagnostic delta but is never a confirmatory endpoint.
    """

    if epsilon <= 0.0:
        raise ValueError("epsilon must be positive.")
    cohort_rows = [dict(row) for row in projection.get("cohort_rows", [])]
    eligible_keys = {str(row["cohort_key"]) for row in projection.get("eligible_cohort_rows", [])}
    all_role_rows = exact_policy_role_rows(cohort_rows)
    role_rows = [row for row in all_role_rows if str(row.get("cohort_key")) in eligible_keys]
    grouped: dict[str, dict[str, list[dict[str, object]]]] = {}
    for row in role_rows:
        grouped.setdefault(str(row["cohort_key"]), {}).setdefault(str(row["semantic_role"]), []).append(row)

    oracle_rows: list[dict[str, object]] = []
    qh_rows: list[dict[str, object]] = []
    for cohort_key, roles in sorted(grouped.items()):
        one = _unique_role_row(roles, "oracle_one_step")
        look = _unique_role_row(roles, "oracle_lookahead")
        if one is not None and look is not None:
            one_gain = _finite_or_none(one.get("final_cumulative_target_root_gain"))
            look_gain = _finite_or_none(look.get("final_cumulative_target_root_gain"))
            if one_gain is not None and look_gain is not None:
                one_rri = _finite_or_none(one.get("final_cumulative_target_rri"))
                look_rri = _finite_or_none(look.get("final_cumulative_target_rri"))
                oracle_rows.append(
                    {
                        "evidence_status": "diagnostic_proxy",
                        "metric_source": "persisted_cumulative_root_gain",
                        "cohort_id": one.get("cohort_id"),
                        "cohort_key": cohort_key,
                        "horizon": one.get("horizon"),
                        "oracle_one_step_endpoint_gain": one_gain,
                        "oracle_lookahead_endpoint_gain": look_gain,
                        "delta_look": look_gain - one_gain,
                        "oracle_one_step_target_rri": one_rri,
                        "oracle_lookahead_target_rri": look_rri,
                        "delta_look_target_rri": None if one_rri is None or look_rri is None else look_rri - one_rri,
                    }
                )
        learned = _unique_role_row(roles, "learned_one_step")
        qh = _unique_role_row(roles, "q_h")
        if look is not None and learned is not None and qh is not None:
            look_gain = _finite_or_none(look.get("final_cumulative_target_root_gain"))
            learned_gain = _finite_or_none(learned.get("final_cumulative_target_root_gain"))
            qh_gain = _finite_or_none(qh.get("final_cumulative_target_root_gain"))
            if look_gain is not None and learned_gain is not None and qh_gain is not None:
                qh_rows.append(
                    {
                        "evidence_status": "diagnostic_proxy",
                        "metric_source": "persisted_cumulative_root_gain",
                        "cohort_id": learned.get("cohort_id"),
                        "cohort_key": cohort_key,
                        "horizon": learned.get("horizon"),
                        "learned_one_step_endpoint_gain": learned_gain,
                        "q_h_endpoint_gain": qh_gain,
                        "oracle_lookahead_endpoint_gain": look_gain,
                        "eta_q": (qh_gain - learned_gain) / (look_gain - learned_gain + float(epsilon)),
                    }
                )

    identifiers_by_role = {
        role: tuple(sorted({str(row["role_identifier"]) for row in all_role_rows if row["semantic_role"] == role}))
        for role in ("oracle_one_step", "oracle_lookahead", "learned_one_step", "q_h")
    }
    blockers = [
        {
            "prerequisite": role,
            "status": "PASS" if identifiers else "BLOCKED",
            "detail": ", ".join(identifiers) if identifiers else "no exact persisted identifier",
        }
        for role, identifiers in identifiers_by_role.items()
    ]
    blockers.extend(
        (
            {
                "prerequisite": "exact oracle cohorts",
                "status": "PASS" if oracle_rows else "BLOCKED",
                "detail": f"{len(oracle_rows)} matched finite cohort(s)"
                if oracle_rows
                else "zero exact finite matches",
            },
            {
                "prerequisite": "exact QH recovery cohorts",
                "status": "PASS" if qh_rows else "BLOCKED",
                "detail": f"{len(qh_rows)} matched finite cohort(s)" if qh_rows else "zero exact finite matches",
            },
        )
    )
    return {
        "evidence_status": "diagnostic_proxy",
        "metric_source": "persisted_cumulative_root_gain",
        "role_rows": role_rows,
        "role_identifiers": identifiers_by_role,
        "oracle_rows": oracle_rows,
        "qh_rows": qh_rows,
        "blocker_rows": blockers,
        "eligible_cohort_count": len(eligible_keys),
    }


def _unique_role_row(
    roles: Mapping[str, list[dict[str, object]]],
    role: str,
) -> dict[str, object] | None:
    """Return an exact role only when its cohort assignment is unambiguous."""

    matches = roles.get(role, [])
    return matches[0] if len(matches) == 1 else None


def _finite_summary(values: np.ndarray) -> dict[str, float | None]:
    """Return stable descriptive statistics for an already-finite vector."""

    if not values.size:
        return dict.fromkeys(("mean", "median", "q25", "q75", "min", "max"))
    q25, median, q75 = np.quantile(np.sort(values), (0.25, 0.5, 0.75), method="linear").tolist()
    return {
        "mean": float(np.mean(values)),
        "median": float(median),
        "q25": float(q25),
        "q75": float(q75),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


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
    group_by: str,
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


def _candidate_generation_cohort_by_rollout(
    reader: RolloutZarrStoreReader,
) -> dict[int, dict[str, object]]:
    """Decode the exact persisted generation cohort for every rollout row."""

    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    lineage_rollout_ids = np.asarray(reader.array("lineage/rollout_row_id"), dtype=np.int64).reshape(-1)
    if rollout_ids.size != lineage_rollout_ids.size or set(rollout_ids.tolist()) != set(lineage_rollout_ids.tolist()):
        raise ValueError("Candidate generation cohorts require one lineage row per rollout row.")
    lineage_positions = {int(row_id): index for index, row_id in enumerate(lineage_rollout_ids.tolist())}
    policy_names = _read_string_array(reader, "dictionaries/policy")
    policy_ids = np.asarray(reader.array("rollouts/policy_id"), dtype=np.int64).reshape(-1)
    horizons = np.asarray(reader.array("rollouts/horizon"), dtype=np.int64).reshape(-1)
    branch_factors = np.asarray(reader.array("rollouts/branch_factor"), dtype=np.int64).reshape(-1)
    beam_widths = np.asarray(reader.array("rollouts/beam_width"), dtype=np.int64).reshape(-1)
    temperatures = np.asarray(reader.array("rollouts/temperature"), dtype=np.float64).reshape(-1)
    candidate_configs = _decoded_array(reader, "lineage/candidate_config_id", "config")
    rollout_configs = _decoded_array(reader, "lineage/rollout_config_id", "config")
    branch_schedules = _decoded_array(reader, "lineage/branch_schedule_id", "config")
    cohort_by_rollout: dict[int, dict[str, object]] = {}
    for rollout_position, rollout_id_value in enumerate(rollout_ids.tolist()):
        rollout_id = int(rollout_id_value)
        lineage_position = lineage_positions[rollout_id]
        fields: dict[str, object] = {
            "policy": _decoded_id(
                int(policy_ids[rollout_position]),
                names=dict(enumerate(policy_names)),
                prefix="policy",
            ),
            "horizon": int(horizons[rollout_position]),
            "acquisition_budget_steps": int(horizons[rollout_position]),
            "branch_factor": int(branch_factors[rollout_position]),
            "beam_width": int(beam_widths[rollout_position]),
            "temperature": _finite_or_none(temperatures[rollout_position]),
            "candidate_config": candidate_configs[lineage_position],
            "rollout_config": rollout_configs[lineage_position],
            "branch_schedule": branch_schedules[lineage_position],
        }
        encoded = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
        fields["generation_cohort_id"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
        cohort_by_rollout[rollout_id] = fields
    return cohort_by_rollout


def _candidate_generation_cohort(row: Mapping[str, object]) -> tuple[object, ...]:
    """Return the exact cohort key, retaining a stable unknown cohort for legacy rows."""

    return (row.get("generation_cohort_id"), *(row.get(field) for field in CANDIDATE_GENERATION_COHORT_FIELDS))


def _candidate_generation_cohort_fields(row: Mapping[str, object]) -> dict[str, object]:
    """Project exact cohort fields and a stable identifier from one candidate row."""

    fields = {field: row.get(field) for field in CANDIDATE_GENERATION_COHORT_FIELDS}
    cohort_id = row.get("generation_cohort_id")
    if cohort_id is None:
        encoded = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
        cohort_id = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return {"generation_cohort_id": str(cohort_id), **fields}


def candidate_family_composition_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return lightweight candidate composition and valid availability.

    This projection reads only categorical lineage, policy linkage, actor mask,
    and selected mask arrays. It never constructs full candidate audit rows.
    """

    cohort_by_rollout = _candidate_generation_cohort_by_rollout(reader)
    candidate_rollouts = np.asarray(reader.array("candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    strategy_ids = np.asarray(reader.array("candidates/strategy_id"), dtype=np.int64).reshape(-1)
    position_ids = np.asarray(reader.array("candidates/position_id"), dtype=np.int64).reshape(-1)
    mixture_ids = np.asarray(reader.array("candidates/mixture_id"), dtype=np.int64).reshape(-1)
    actor_valid = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    arrays = (strategy_ids, position_ids, mixture_ids, actor_valid, selected)
    if any(values.size != candidate_rollouts.size for values in arrays):
        raise ValueError("Candidate composition arrays must align one-to-one.")
    component_names = _component_names(reader.manifest())
    strategies = [decode_strategy_id(int(value)) for value in strategy_ids.tolist()]
    positions = [decode_position_id(int(value)) for value in position_ids.tolist()]
    mixtures = [_decoded_id(int(value), names=component_names, prefix="mixture") for value in mixture_ids.tolist()]
    dimensions = {
        "policy": [cohort_by_rollout[int(value)]["policy"] for value in candidate_rollouts.tolist()],
        "strategy": strategies,
        "position": positions,
        "mixture": mixtures,
        "recipe": [
            f"mixture={mixture} → position={position} → view={strategy}"
            for mixture, position, strategy in zip(mixtures, positions, strategies, strict=True)
        ],
    }
    candidate_cohort_ids = [
        str(cohort_by_rollout[int(rollout_id)]["generation_cohort_id"]) for rollout_id in candidate_rollouts.tolist()
    ]
    cohort_counts = Counter(candidate_cohort_ids)
    output: list[dict[str, object]] = []
    for dimension, values in dimensions.items():
        groups: dict[tuple[str, str], list[int]] = {}
        for index, value in enumerate(values):
            cohort_id = candidate_cohort_ids[index]
            groups.setdefault((cohort_id, str(value)), []).append(index)
        for (cohort_id, value), indices in sorted(groups.items()):
            row_positions = np.asarray(indices, dtype=np.int64)
            total = int(row_positions.size)
            valid_count = int(actor_valid[row_positions].sum())
            selected_count = int(selected[row_positions].sum())
            cohort = cohort_by_rollout[int(candidate_rollouts[int(row_positions[0])])]
            cohort_count = cohort_counts[cohort_id]
            output.append(
                {
                    **cohort,
                    "dimension": dimension,
                    "family": value,
                    "sampled_count": total,
                    "sampled_fraction": _safe_fraction(total, cohort_count),
                    "actor_valid_count": valid_count,
                    "actor_valid_rate": _safe_fraction(valid_count, total),
                    "selected_count": selected_count,
                    "selected_share_of_valid_availability": _safe_fraction(selected_count, valid_count),
                }
            )
    return output


def candidate_evidence_availability_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Report persisted field availability without loading candidate payloads."""

    requirements = {
        "proposal calibration": ("candidates/sampler_probability",),
        "root-relative geometry": ("candidates/pose_world_cam", "rollouts/root_pose_world"),
        "orientation to target": (
            "candidate_diagnostics/motion_yaw_delta_deg",
            "candidate_diagnostics/target_bearing_yaw_deg",
        ),
        "motion support": (
            "candidates/motion_step_length_m",
            "candidates/path_min_clearance_m",
            "candidate_diagnostics/motion_backward_step_m",
            "candidate_diagnostics/path_collision_mask",
        ),
        "oracle rank and regret": (
            "candidates/target_root_gain",
            "candidates/target_rri",
            "candidates/selection_logits",
        ),
    }
    output: list[dict[str, object]] = []
    for evidence, paths in requirements.items():
        missing = tuple(path for path in paths if path not in reader.root)
        output.append(
            {
                "evidence": evidence,
                "available": not missing,
                "required_fields": paths,
                "missing_fields": missing,
                "detail": "persisted fields present" if not missing else f"missing: {', '.join(missing)}",
            }
        )
    return output


def candidate_proposal_calibration_rows(
    audit_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Compare empirical family frequency with proposal mass within exact cohorts."""

    rows = [dict(row) for row in audit_rows]
    output: list[dict[str, object]] = []
    cohorts: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        cohorts.setdefault(_candidate_generation_cohort(row), []).append(row)
    for cohort_rows in cohorts.values():
        cohort_fields = _candidate_generation_cohort_fields(cohort_rows[0])
        finite_total = sum(
            float(value)
            for row in cohort_rows
            if (value := _finite_or_none(row.get("sampler_probability"))) is not None
        )
        for dimension in ("policy", "strategy", "position", "mixture"):
            groups: dict[str, list[dict[str, object]]] = {}
            for row in cohort_rows:
                groups.setdefault(str(row.get(dimension, "unknown")), []).append(row)
            for family, values in sorted(groups.items()):
                probabilities = [
                    value for row in values if (value := _finite_or_none(row.get("sampler_probability"))) is not None
                ]
                proposal_mass = (
                    None if not probabilities or finite_total <= 0.0 else float(sum(probabilities) / finite_total)
                )
                empirical = _safe_fraction(len(values), len(cohort_rows))
                output.append(
                    {
                        **cohort_fields,
                        "dimension": dimension,
                        "family": family,
                        "cohort_candidate_count": len(cohort_rows),
                        "candidate_count": len(values),
                        "finite_probability_count": len(probabilities),
                        "empirical_frequency": empirical,
                        "proposal_mass": proposal_mass,
                        "calibration_gap": None
                        if proposal_mass is None or empirical is None
                        else empirical - proposal_mass,
                    }
                )
    return output


def candidate_geometry_evidence_rows(
    audit_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    r"""Derive root-relative and target-normalized candidate geometry diagnostics.

    The target-normalized XY coordinates rotate and scale each root-centered
    candidate displacement so the target center is always at $(1, 0)$. For
    candidate displacement $c$ and root-to-target XY vector $t$, the emitted
    forward and lateral coordinates are

    $$
    (u, v) = \left(
        \frac{c \cdot t}{\lVert t \rVert^2},
        \frac{-c_x t_y + c_y t_x}{\lVert t \rVert^2}
    \right).
    $$

    This display-only transform removes global XY translation, yaw, and
    root-target distance. It leaves the persisted rollout coordinates unchanged.

    Args:
        audit_rows: Candidate audit rows with root-relative candidate positions
            and the root-to-target vector in right-handed Z-up metres.

    Returns:
        Geometry rows with cylindrical root-relative quantities and unitless
        target-normalized forward/lateral coordinates. Normalized coordinates
        are `None` when the target vector is missing or has zero XY length.
    """

    output: list[dict[str, object]] = []
    for source_row in audit_rows:
        row = dict(source_row)
        x = _finite_or_none(row.get("root_relative_x_m"))
        y = _finite_or_none(row.get("root_relative_y_m"))
        z = _finite_or_none(row.get("root_relative_z_m"))
        radius = None if x is None or y is None else float(np.hypot(x, y))
        azimuth = None if x is None or y is None else float(np.degrees(np.arctan2(y, x)))
        elevation = None if radius is None or z is None else float(np.degrees(np.arctan2(z, radius)))
        yaw = _finite_or_none(row.get("motion_yaw_delta_deg"))
        bearing = _finite_or_none(row.get("target_bearing_yaw_deg"))
        orientation = None if yaw is None or bearing is None else float((yaw - bearing + 180.0) % 360.0 - 180.0)
        target_x = _finite_or_none(row.get("root_to_target_x_m"))
        target_y = _finite_or_none(row.get("root_to_target_y_m"))
        target_xy_squared = None if target_x is None or target_y is None else target_x**2 + target_y**2
        target_xy_distance = None if target_xy_squared is None else float(np.sqrt(target_xy_squared))
        target_normalized_forward = (
            None
            if x is None
            or y is None
            or target_x is None
            or target_y is None
            or target_xy_squared is None
            or target_xy_squared <= 0.0
            else float((x * target_x + y * target_y) / target_xy_squared)
        )
        target_normalized_lateral = (
            None
            if x is None
            or y is None
            or target_x is None
            or target_y is None
            or target_xy_squared is None
            or target_xy_squared <= 0.0
            else float((-x * target_y + y * target_x) / target_xy_squared)
        )
        output.append(
            {
                **row,
                "root_radius_m": radius,
                "root_azimuth_deg": azimuth,
                "root_elevation_deg": elevation,
                "orientation_to_target_bearing_deg": orientation,
                "root_target_xy_distance_m": target_xy_distance,
                "target_normalized_forward": target_normalized_forward,
                "target_normalized_lateral": target_normalized_lateral,
                "target_normalized_coordinate_frame": "root=(0,0), target=(1,0), right-handed lateral axis",
            }
        )
    return output


def candidate_selection_family_rows(
    audit_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Normalize selection counts by actor-valid availability within exact cohorts."""

    rows = [dict(row) for row in audit_rows]
    output: list[dict[str, object]] = []
    cohorts: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        cohorts.setdefault(_candidate_generation_cohort(row), []).append(row)
    for cohort_rows in cohorts.values():
        cohort_fields = _candidate_generation_cohort_fields(cohort_rows[0])
        cohort_valid_count = sum(bool(row.get("actor_action")) for row in cohort_rows)
        cohort_selected_count = sum(bool(row.get("selected")) for row in cohort_rows)
        for dimension in ("policy", "strategy", "position", "mixture"):
            groups: dict[str, list[dict[str, object]]] = {}
            for row in cohort_rows:
                groups.setdefault(str(row.get(dimension, "unknown")), []).append(row)
            for family, values in sorted(groups.items()):
                valid = [row for row in values if bool(row.get("actor_action"))]
                selected = [row for row in values if bool(row.get("selected"))]
                valid_gains = [
                    value for row in valid if (value := _finite_or_none(row.get("target_root_gain"))) is not None
                ]
                selected_gains = [
                    value for row in selected if (value := _finite_or_none(row.get("target_root_gain"))) is not None
                ]
                valid_availability_share = _safe_fraction(len(valid), cohort_valid_count)
                selected_share = _safe_fraction(len(selected), cohort_selected_count)
                selection_enrichment = (
                    None
                    if valid_availability_share in (None, 0.0) or selected_share is None
                    else selected_share / cast(float, valid_availability_share)
                )
                output.append(
                    {
                        **cohort_fields,
                        "dimension": dimension,
                        "family": family,
                        "cohort_candidate_count": len(cohort_rows),
                        "candidate_count": len(values),
                        "actor_valid_count": len(valid),
                        "selected_count": len(selected),
                        "selected_share_of_valid_availability": _safe_fraction(len(selected), len(valid)),
                        "valid_availability_share": valid_availability_share,
                        "selected_share": selected_share,
                        "selection_enrichment_vs_valid_availability": selection_enrichment,
                        "mean_valid_target_root_gain": None if not valid_gains else float(np.mean(valid_gains)),
                        "mean_selected_target_root_gain": None
                        if not selected_gains
                        else float(np.mean(selected_gains)),
                    }
                )
    return output


def candidate_selection_rank_family_rows(
    audit_rows: Iterable[Mapping[str, object]],
    rank_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Join selected rank/regret evidence to its exact generation family."""

    selected = {
        int(cast(int, row["candidate_row_id"])): dict(row)
        for row in audit_rows
        if bool(row.get("selected")) and row.get("candidate_row_id") is not None
    }
    output: list[dict[str, object]] = []
    for source_row in rank_rows:
        row = dict(source_row)
        candidate = selected.get(int(cast(int, row.get("selected_candidate_row_id", -1))))
        if candidate is None:
            continue
        cohort_fields = (
            _candidate_generation_cohort_fields(candidate)
            if "generation_cohort_id" in candidate
            or any(field in candidate for field in CANDIDATE_GENERATION_COHORT_FIELDS)
            else {}
        )
        output.append(
            {
                **row,
                **cohort_fields,
                "strategy": candidate.get("strategy"),
                "position": candidate.get("position"),
                "mixture": candidate.get("mixture"),
            }
        )
    return output


def candidate_validity_evidence(
    candidate_rows: Iterable[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Reduce a full projected candidate table into exact validity evidence.

    The reducer never opens a rollout store. It conserves every projected row
    through explicit missing buckets, keeps all four masks as separate Boolean
    contracts, decodes the complete versioned invalid-reason bitset, and
    aggregates conditional availability within state, then scene, then exact
    generation cohort. Missing masks are unavailable observations, never
    negative labels, and target RRI is deliberately ignored.
    """

    rows = _sorted_candidate_rows(candidate_rows)
    evidence: dict[str, list[dict[str, object]]] = {
        "flow_rows": [],
        "conservation_rows": [],
        "missing_stage_rows": [],
        "mask_intersection_rows": [],
        "invalid_implication_rows": [],
        "reason_intersection_rows": [],
        "conditional_availability_rows": [],
    }
    for cohort_rows in _candidate_cohort_groups(rows):
        if not cohort_rows:
            continue
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        root_count = len(cohort_rows)
        transitions: Counter[tuple[str, str, str, str]] = Counter()
        missing_counts: Counter[str] = Counter()
        for row in cohort_rows:
            proposal = _validity_proposal_bucket(row)
            actor = _optional_bool(row.get("actor_action"))
            oracle = _optional_bool(row.get("oracle_label"))
            q_train = _optional_bool(row.get("q_train"))
            selected = _optional_bool(row.get("selected"))
            if proposal == "missing_proposal":
                missing_counts["proposal"] += 1
            for field, value in (
                ("actor_action", actor),
                ("oracle_label", oracle),
                ("q_train", q_train),
                ("selected", selected),
            ):
                if value is None:
                    missing_counts[field] += 1
            actor_bucket = "actor_unavailable" if actor is None else "actor_valid" if actor else "actor_invalid"
            outcome = _validity_outcome_bucket(row, actor=actor, selected=selected)
            transitions[("sampled", "all_sampled", "proposal", proposal)] += 1
            transitions[("proposal", proposal, "actor_validity", actor_bucket)] += 1
            transitions[("actor_validity", actor_bucket, "outcome", outcome)] += 1

        for (source_stage, source, target_stage, target), count in sorted(transitions.items()):
            evidence["flow_rows"].append(
                {
                    **cohort,
                    "source_stage": source_stage,
                    "source": source,
                    "target_stage": target_stage,
                    "target": target,
                    "count": count,
                    "root_denominator": root_count,
                    "fraction_of_root": _safe_fraction(count, root_count),
                }
            )
        for source_stage, target_stage in (
            ("sampled", "proposal"),
            ("proposal", "actor_validity"),
            ("actor_validity", "outcome"),
        ):
            observed = sum(
                count
                for (source_stage_value, _, target_stage_value, _), count in transitions.items()
                if source_stage_value == source_stage and target_stage_value == target_stage
            )
            evidence["conservation_rows"].append(
                {
                    **cohort,
                    "transition": f"{source_stage} -> {target_stage}",
                    "expected_count": root_count,
                    "observed_count": observed,
                    "difference": observed - root_count,
                    "conserved": observed == root_count,
                    "status": "pass" if observed == root_count else "fail",
                }
            )
        for stage in ("proposal", "actor_action", "oracle_label", "q_train", "selected"):
            count = missing_counts[stage]
            evidence["missing_stage_rows"].append(
                {
                    **cohort,
                    "stage": stage,
                    "missing_count": count,
                    "root_denominator": root_count,
                    "available": count == 0,
                }
            )
        _append_mask_intersections(evidence, cohort, cohort_rows)
        evidence["reason_intersection_rows"].extend(_reason_intersection_evidence(cohort, cohort_rows))
        evidence["conditional_availability_rows"].extend(_conditional_validity_evidence(cohort, cohort_rows))
    return evidence


def validity_audit_evidence(
    artifact: ScientificAuditArtifact,
    *,
    boundary_edges: tuple[float, ...] = (float("-inf"), -0.1, 0.0, 0.1, float("inf")),
) -> dict[str, object]:
    r"""Summarize frozen weighted validity audits without treating rows as IID.

    Weighted state/path/combined confusion uses the sealed per-row
    inverse-inclusion weight $1/\pi_h$. Soundness-style eligibility requires an
    intact confirmatory artifact under the exact same predicate contract.
    Changed-contract audits retain weighted characterization only. Blocked
    independent labels remain unavailable and never enter a false-label cell.
    """

    verify_scientific_audit_sha256(artifact)
    if len(boundary_edges) < 2 or any(
        right <= left for left, right in pairwise(float(value) for value in boundary_edges)
    ):
        raise ValueError("boundary_edges must be strictly increasing.")
    rows = sorted(artifact.validity_rows, key=lambda row: row.unit_id)
    required_kinds = ("state", "path", "combined_actor")
    cohort_ids = tuple(sorted(summary.cohort_id for summary in artifact.cohort_summaries))
    coverage_rows: list[dict[str, object]] = []
    blocker_rows: list[dict[str, object]] = []
    for cohort_id in cohort_ids:
        cohort_rows = [row for row in rows if row.cohort_id == cohort_id]
        for predicate_kind in required_kinds:
            kind_rows = [row for row in cohort_rows if row.predicate_kind == predicate_kind]
            complete = [
                row
                for row in kind_rows
                if row.evaluation_status is RowEvaluationStatus.COMPLETE
                and row.independent_valid is not None
                and row.raw_measurement is not None
                and row.signed_margin is not None
            ]
            changed = [
                row
                for row in kind_rows
                if row.persisted_contract.identity_sha256 != row.independent_contract.identity_sha256
            ]
            reason = (
                "missing_required_predicate_kind"
                if not kind_rows
                else "changed_predicate_contract"
                if changed
                else "incomplete_independent_labels"
                if len(complete) != len(kind_rows)
                else None
            )
            covered = reason is None
            coverage_rows.append(
                {
                    "cohort_id": cohort_id,
                    "predicate_kind": predicate_kind,
                    "sampled_count": len(kind_rows),
                    "complete_count": len(complete),
                    "missing_count": len(kind_rows) - len(complete),
                    "changed_contract_count": len(changed),
                    "covered": covered,
                    "status": "pass" if covered else "blocked",
                    "blocker": reason,
                }
            )
            if reason is not None:
                blocker_rows.append(
                    {
                        "cohort_id": cohort_id,
                        "predicate_kind": predicate_kind,
                        "blocker": reason,
                        "sampled_count": len(kind_rows),
                        "complete_count": len(complete),
                    }
                )
    typed_contract_match = all(
        row.persisted_contract.identity_sha256 == row.independent_contract.identity_sha256 for row in rows
    )
    declared_same_contract = artifact.comparison_protocol is AuditComparisonProtocol.SAME_CONTRACT
    coverage_complete = bool(coverage_rows) and all(bool(row["covered"]) for row in coverage_rows)
    confirmatory = (
        declared_same_contract
        and typed_contract_match
        and artifact.status is AuditStatus.PASS
        and artifact.readiness is AuditReadiness.CONFIRMATORY
        and coverage_complete
    )
    evidence_status = (
        "confirmatory"
        if confirmatory
        else "characterization_only"
        if not declared_same_contract or not typed_contract_match
        else "unavailable"
    )
    confusion_rows: list[dict[str, object]] = []
    for cohort_id in cohort_ids:
        cohort_rows = [row for row in rows if row.cohort_id == cohort_id]
        for predicate_kind in ("state", "path", "combined_actor"):
            kind_rows = [row for row in cohort_rows if row.predicate_kind == predicate_kind]
            complete = [row for row in kind_rows if row.independent_valid is not None]
            cells = Counter((bool(row.persisted_valid), bool(row.independent_valid)) for row in complete)
            weighted_cells: dict[tuple[bool, bool], float] = {}
            for row in complete:
                cell = (bool(row.persisted_valid), bool(row.independent_valid))
                weighted_cells[cell] = weighted_cells.get(cell, 0.0) + float(row.inverse_probability_weight)
            weighted_total = float(sum(weighted_cells.values()))
            tp = weighted_cells.get((True, True), 0.0)
            fp = weighted_cells.get((True, False), 0.0)
            fn = weighted_cells.get((False, True), 0.0)
            tn = weighted_cells.get((False, False), 0.0)
            missing_count = len(kind_rows) - len(complete)
            confusion_rows.append(
                {
                    "cohort_id": cohort_id,
                    "predicate_kind": predicate_kind,
                    "evidence_status": evidence_status,
                    "same_contract": declared_same_contract and typed_contract_match,
                    "eligible": confirmatory and bool(complete) and missing_count == 0,
                    "available": bool(complete),
                    "sampled_count": len(kind_rows),
                    "labeled_count": len(complete),
                    "missing_label_count": missing_count,
                    "unweighted_true_positive": cells[(True, True)],
                    "unweighted_false_positive": cells[(True, False)],
                    "unweighted_false_negative": cells[(False, True)],
                    "unweighted_true_negative": cells[(False, False)],
                    "weighted_true_positive": float(tp),
                    "weighted_false_positive": float(fp),
                    "weighted_false_negative": float(fn),
                    "weighted_true_negative": float(tn),
                    "weighted_population": weighted_total,
                    "weighted_agreement": None if weighted_total == 0 else float((tp + tn) / weighted_total),
                    "weighted_persisted_precision": None if tp + fp == 0 else float(tp / (tp + fp)),
                    "weighted_persisted_recall": None if tp + fn == 0 else float(tp / (tp + fn)),
                    "unavailable_reason": (
                        "no independent labels"
                        if not complete
                        else "independent labels missing for frozen sampled rows"
                        if missing_count
                        else None
                    ),
                }
            )

    margin_rows = _signed_margin_summary_rows(rows, evidence_status=evidence_status)
    boundary_rows = _weighted_boundary_agreement(rows, boundary_edges, evidence_status=evidence_status)
    return {
        "comparison_protocol": artifact.comparison_protocol.value,
        "artifact_status": artifact.status.value,
        "audit_readiness": artifact.readiness.value,
        "evidence_status": evidence_status,
        "same_contract_eligible": confirmatory,
        "typed_contract_match": typed_contract_match,
        "required_predicate_coverage_complete": coverage_complete,
        "fallback_reason": None
        if confirmatory
        else "predicate contract changed; weighted results are characterization only"
        if not declared_same_contract or not typed_contract_match
        else "required predicate coverage is incomplete"
        if not coverage_complete
        else "audit is not confirmatory-ready",
        "coverage_rows": coverage_rows,
        "blocker_rows": blocker_rows,
        "confusion_rows": confusion_rows,
        "margin_rows": margin_rows,
        "boundary_rows": boundary_rows,
    }


_CANDIDATE_EVIDENCE_PROTOCOL_VERSION = "candidate-scientific-evidence-v1"
_DIRECTION_AZIMUTH_BINS = 12
_DIRECTION_SIN_ELEVATION_BINS = 6
_CAP_REFERENCE_COUNT = 128
_COVERING_REFERENCE_COUNT = 512
_CAP_RADII_DEG = (30.0, 60.0, 90.0, 120.0, 150.0)


def candidate_state_composition_evidence(
    audit_rows: Iterable[Mapping[str, object]],
    *,
    family_fields: tuple[str, ...] = ("strategy", "position", "mixture"),
) -> list[dict[str, object]]:
    """Summarize candidate-family composition with equal state weighting.

    Candidate counts do not define the experimental sampling unit. For each
    exact generation cohort, family shares are computed within state, averaged
    equally within scene, and then averaged equally across scenes. States with
    no actor-valid or selected population remain explicit undefined
    denominators.
    """

    rows = _sorted_candidate_rows(audit_rows)
    output: list[dict[str, object]] = []
    for cohort_rows in _candidate_cohort_groups(rows):
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        states = _candidate_state_groups(cohort_rows)
        state_scenes = {
            state_key: str(state_rows[0].get("scene", "unknown")) for state_key, state_rows in states.items()
        }
        for family_field in family_fields:
            families = tuple(sorted({str(row.get(family_field, "unknown")) for row in cohort_rows}))
            for family in families:
                population_state_shares: dict[str, dict[str, float | None]] = {
                    "sampled": {},
                    "actor_valid": {},
                    "selected": {},
                }
                population_state_counts: dict[str, dict[str, tuple[int, int, int]]] = {
                    "sampled": {},
                    "actor_valid": {},
                    "selected": {},
                }
                enrichment_values: dict[str, float | None] = {}
                enrichment_counts: dict[str, tuple[int, int, int]] = {}
                for state_key, state_rows in states.items():
                    family_rows = [row for row in state_rows if str(row.get(family_field, "unknown")) == family]
                    populations = {
                        "sampled": state_rows,
                        "actor_valid": [row for row in state_rows if bool(row.get("actor_action"))],
                        "selected": [row for row in state_rows if bool(row.get("selected"))],
                    }
                    family_populations = {
                        name: [
                            row
                            for row in family_rows
                            if name == "sampled"
                            or (name == "actor_valid" and bool(row.get("actor_action")))
                            or (name == "selected" and bool(row.get("selected")))
                        ]
                        for name in populations
                    }
                    for population, population_rows in populations.items():
                        family_count = len(family_populations[population])
                        population_state_shares[population][state_key] = (
                            None if not population_rows else family_count / len(population_rows)
                        )
                        population_state_counts[population][state_key] = (
                            len(population_rows),
                            family_count,
                            0,
                        )
                    valid_share = (
                        None
                        if not populations["actor_valid"]
                        else len(family_populations["actor_valid"]) / len(populations["actor_valid"])
                    )
                    selected_share = (
                        None
                        if not populations["selected"]
                        else len(family_populations["selected"]) / len(populations["selected"])
                    )
                    enrichment = (
                        None
                        if valid_share in (None, 0.0) or selected_share is None
                        else selected_share / cast(float, valid_share)
                    )
                    enrichment_values[state_key] = enrichment
                    enrichment_counts[state_key] = (
                        len(state_rows),
                        int(enrichment is not None),
                        int(enrichment is None),
                    )

                for population in ("sampled", "actor_valid", "selected"):
                    output.extend(
                        _composition_macro_rows(
                            cohort,
                            population=population,
                            family_dimension=family_field,
                            family=family,
                            state_values=population_state_shares[population],
                            state_scenes=state_scenes,
                            state_counts=population_state_counts[population],
                            value_field="mean_state_family_share",
                            units="fraction",
                            unavailable_reason=f"no defined {population} state denominator",
                            count_semantics="population denominator, family numerator, missing persisted values",
                        )
                    )
                output.extend(
                    _composition_macro_rows(
                        cohort,
                        population="selected_to_valid_enrichment",
                        family_dimension=family_field,
                        family=family,
                        state_values=enrichment_values,
                        state_scenes=state_scenes,
                        state_counts=enrichment_counts,
                        value_field="mean_state_selection_enrichment",
                        units="ratio",
                        unavailable_reason="no state has both selected support and nonzero actor-valid family share",
                        count_semantics="candidate rows, defined state enrichments, undefined state enrichments",
                    )
                )
    return sorted(output, key=_candidate_evidence_sort_key)


def candidate_direction_evidence(
    geometry_rows: Iterable[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    r"""Measure equal-area directional support within exact generation cohorts.

    Direction density bins azimuth and $\sin(\mathrm{elevation})$, whose grid
    cells have equal solid angle. Spherical-cap discrepancy is approximated on
    a fixed Fibonacci reference grid and fixed cap radii; it is evidence
    against a uniform-sphere reference, not proof that uniform sampling is the
    intended proposal distribution.
    """

    rows = _sorted_candidate_rows(geometry_rows)
    density_rows: list[dict[str, object]] = []
    cap_rows: list[dict[str, object]] = []
    angular_rows: list[dict[str, object]] = []
    cap_centers = _fibonacci_sphere(_CAP_REFERENCE_COUNT)
    covering_reference = _fibonacci_sphere(_COVERING_REFERENCE_COUNT)
    for cohort_rows in _candidate_cohort_groups(rows):
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        states = _candidate_state_groups(cohort_rows)
        for population, selector in _candidate_populations():
            state_directions: dict[str, np.ndarray] = {}
            state_scenes: dict[str, str] = {}
            state_counts: dict[str, tuple[int, int]] = {}
            for state_key, state_rows in states.items():
                selected_rows = [row for row in state_rows if selector(row)]
                directions = _finite_unit_directions(selected_rows)
                state_directions[state_key] = directions
                state_scenes[state_key] = str(state_rows[0].get("scene", "unknown"))
                state_counts[state_key] = (len(selected_rows), int(directions.shape[0]))
            for azimuth_bin in range(_DIRECTION_AZIMUTH_BINS):
                for elevation_bin in range(_DIRECTION_SIN_ELEVATION_BINS):
                    fractions: dict[str, float | None] = {}
                    for state_key, directions in state_directions.items():
                        if directions.shape[0] == 0:
                            fractions[state_key] = None
                            continue
                        azimuth = (np.arctan2(directions[:, 1], directions[:, 0]) + np.pi) / (2.0 * np.pi)
                        sin_elevation = (directions[:, 2] + 1.0) / 2.0
                        azimuth_indices = np.minimum(
                            (azimuth * _DIRECTION_AZIMUTH_BINS).astype(np.int64),
                            _DIRECTION_AZIMUTH_BINS - 1,
                        )
                        elevation_indices = np.minimum(
                            (sin_elevation * _DIRECTION_SIN_ELEVATION_BINS).astype(np.int64),
                            _DIRECTION_SIN_ELEVATION_BINS - 1,
                        )
                        fractions[state_key] = float(
                            np.mean((azimuth_indices == azimuth_bin) & (elevation_indices == elevation_bin))
                        )
                    density_rows.extend(
                        _direction_macro_rows(
                            cohort,
                            population,
                            evidence="equal_area_direction_density",
                            state_values=fractions,
                            state_scenes=state_scenes,
                            state_counts=state_counts,
                            value_field="mean_state_fraction",
                            units="solid-angle fraction",
                            unavailable_reason="no finite nonzero root-relative XYZ directions",
                            protocol={
                                "azimuth_bins": _DIRECTION_AZIMUTH_BINS,
                                "sin_elevation_bins": _DIRECTION_SIN_ELEVATION_BINS,
                                "binning": "azimuth x sin(elevation)",
                                "macro_order": "candidate fraction per state, equal-state scene mean, equal-scene cohort mean",
                                "state_row_sparsity": "only nonzero state-bin fractions are emitted; omitted defined state bins are implicit zero",
                                "aggregate_completeness": "every bin is emitted at scene and cohort levels over all eligible states",
                            },
                            extra={"azimuth_bin": azimuth_bin, "sin_elevation_bin": elevation_bin},
                            sparse_state_zeros=True,
                            include_aggregate_state_keys=False,
                        )
                    )
            for radius_deg in _CAP_RADII_DEG:
                discrepancies = {
                    state_key: None
                    if values.shape[0] == 0
                    else _spherical_cap_discrepancy(values, cap_centers, radius_deg)
                    for state_key, values in state_directions.items()
                }
                cap_rows.extend(
                    _direction_macro_rows(
                        cohort,
                        population,
                        evidence="uniform_spherical_cap_discrepancy",
                        state_values=discrepancies,
                        state_scenes=state_scenes,
                        state_counts=state_counts,
                        value_field="mean_state_max_abs_discrepancy",
                        units="fraction",
                        unavailable_reason="no finite nonzero root-relative XYZ directions",
                        protocol={
                            "reference": "fixed Fibonacci sphere",
                            "reference_count": _CAP_REFERENCE_COUNT,
                            "cap_radii_deg": _CAP_RADII_DEG,
                            "limitation": "grid approximation against a uniform-sphere reference only",
                            "macro_order": "per-state discrepancy, equal-state scene mean, equal-scene cohort mean",
                        },
                        extra={
                            "cap_radius_deg": radius_deg,
                            "uniform_reference_fraction": float((1.0 - np.cos(np.radians(radius_deg))) / 2.0),
                        },
                    )
                )
            angular_rows.extend(
                _angular_support_rows(
                    cohort,
                    population,
                    state_directions,
                    state_scenes=state_scenes,
                    state_counts=state_counts,
                    covering_reference=covering_reference,
                )
            )
    return {
        "density_rows": sorted(density_rows, key=_candidate_evidence_sort_key),
        "cap_rows": sorted(cap_rows, key=_candidate_evidence_sort_key),
        "angular_support_rows": sorted(angular_rows, key=_candidate_evidence_sort_key),
    }


def candidate_spatial_support_evidence(
    geometry_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Summarize root-relative spatial shells with state and scene macros."""

    rows = _sorted_candidate_rows(geometry_rows)
    metrics = {
        "root_xy_radius": ("root_radius_m", "m"),
        "root_3d_distance": ("root_distance_m", "m"),
        "root_height": ("root_relative_z_m", "m"),
    }
    output: list[dict[str, object]] = []
    for cohort_rows in _candidate_cohort_groups(rows):
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        for population, selector in _candidate_populations():
            population_rows = [row for row in cohort_rows if selector(row)]
            shells = tuple(sorted({str(row.get("position", "unknown")) for row in population_rows})) or ("unknown",)
            for shell in shells:
                shell_rows = [row for row in population_rows if str(row.get("position", "unknown")) == shell]
                for metric, (field, units) in metrics.items():
                    output.extend(
                        _candidate_numeric_macro_rows(
                            cohort,
                            shell_rows,
                            metric=metric,
                            field=field,
                            population=population,
                            units=units,
                            frame="root-centered ARIA world (RIGHT_HAND_Z_UP)",
                            extra={"declared_shell": shell, "zero_radius_policy": "included"},
                        )
                    )
    return sorted(output, key=_candidate_evidence_sort_key)


def candidate_target_view_evidence(
    geometry_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Summarize target distance and mark unobserved view evidence unavailable."""

    rows = _sorted_candidate_rows(geometry_rows)
    output: list[dict[str, object]] = []
    for cohort_rows in _candidate_cohort_groups(rows):
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        for population, selector in _candidate_populations():
            population_rows = [row for row in cohort_rows if selector(row)]
            output.extend(
                _candidate_numeric_macro_rows(
                    cohort,
                    population_rows,
                    metric="target_distance",
                    field="target_distance_m",
                    population=population,
                    units="m",
                    frame="root-centered ARIA world (RIGHT_HAND_Z_UP)",
                )
            )
            for metric, missing_fields, reason in (
                (
                    "target_orientation_alignment",
                    ("candidate_forward_world", "target_vector_framed"),
                    "candidate forward and framed target vector are not persisted; yaw delta and global bearing are not commensurate",
                ),
                (
                    "target_3d_bearing_error",
                    ("candidate_forward_world", "target_center_world"),
                    "3D camera forward and target bearing are not persisted",
                ),
                (
                    "target_fov_margin",
                    ("camera_calibration", "target_projection"),
                    "camera FOV and projected target support are not persisted per candidate",
                ),
                (
                    "target_pixel_margin",
                    ("target_pixel_bounds",),
                    "target image-plane bounds are not persisted per candidate",
                ),
                (
                    "target_line_of_sight",
                    ("target_los_query",),
                    "target-specific LOS is not persisted; path collision is not LOS",
                ),
            ):
                output.append(
                    {
                        **cohort,
                        **_candidate_evidence_metadata(
                            population=population,
                            frame="unavailable",
                            units="unavailable",
                            available=False,
                            reason=reason,
                        ),
                        "evidence": metric,
                        "state_key": None,
                        "state_keys": tuple(sorted(_candidate_state_groups(population_rows))),
                        "state_count": len(_candidate_state_groups(population_rows)),
                        "defined_state_count": 0,
                        "undefined_state_count": len(_candidate_state_groups(population_rows)),
                        "full_count": len(population_rows),
                        "finite_count": 0,
                        "missing_count": len(population_rows),
                        "missing_fields": missing_fields,
                        "mean": None,
                    }
                )
    return sorted(output, key=_candidate_evidence_sort_key)


def candidate_motion_support_evidence(
    audit_rows: Iterable[Mapping[str, object]],
    *,
    joint_support_conjunction: tuple[str, ...] | None = None,
) -> list[dict[str, object]]:
    """Summarize actor-valid motion support with explicit missingness.

    Joint support is emitted only when the caller supplies an explicit
    conjunction of ``actor_valid``, ``path_collision_free``, and/or
    ``finite_motion``. No implicit conjunction is treated as scientific data.
    """

    allowed_joint = {"actor_valid", "path_collision_free", "finite_motion"}
    if joint_support_conjunction is not None:
        unknown = set(joint_support_conjunction) - allowed_joint
        if unknown or not joint_support_conjunction:
            raise ValueError(f"Unsupported joint support conjunction terms: {sorted(unknown)}")
    rows = _sorted_candidate_rows(audit_rows)
    output: list[dict[str, object]] = []
    metrics = {
        "motion_step_length": ("motion_step_length_m", "m"),
        "motion_height_delta": ("motion_height_delta_m", "m"),
        "motion_backward_step": ("motion_backward_step_m", "m"),
        "motion_yaw_delta": ("motion_yaw_delta_deg", "deg"),
        "path_min_clearance": ("path_min_clearance_m", "m"),
        "free_space_margin": ("free_space_margin_m", "m"),
    }
    for cohort_rows in _candidate_cohort_groups(rows):
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        actor_rows = [row for row in cohort_rows if bool(row.get("actor_action"))]
        output.extend(
            _candidate_boolean_macro_rows(
                cohort,
                actor_rows,
                metric="path_collision_rate",
                field="path_collision",
                population="actor_valid",
                true_is_support=True,
                availability_field="path_min_clearance_m",
            )
        )
        for metric, (field, units) in metrics.items():
            output.extend(
                _candidate_numeric_macro_rows(
                    cohort,
                    actor_rows,
                    metric=metric,
                    field=field,
                    population="actor_valid",
                    units=units,
                    frame="root-centered ARIA world (RIGHT_HAND_Z_UP)",
                )
            )
        if joint_support_conjunction is not None:
            output.extend(_joint_motion_support_rows(cohort, cohort_rows, joint_support_conjunction))
    return sorted(output, key=_candidate_evidence_sort_key)


def candidate_regret_evidence(
    audit_rows: Iterable[Mapping[str, object]],
    rank_rows: Iterable[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    """Summarize selected-action regret and expose selection-contract violations."""

    candidates = _sorted_candidate_rows(audit_rows)
    ranks = [dict(row) for row in rank_rows]
    selected_id_groups: dict[int, list[dict[str, object]]] = {}
    for row in candidates:
        if bool(row.get("selected")) and row.get("candidate_row_id") is not None:
            selected_id_groups.setdefault(int(cast(int, row["candidate_row_id"])), []).append(row)
    selected_by_id = {
        candidate_id: values[0] for candidate_id, values in selected_id_groups.items() if len(values) == 1
    }
    joined: list[dict[str, object]] = []
    violations: list[dict[str, object]] = []
    invalid_states: set[str] = set()
    selected_by_state = _candidate_state_groups([row for row in candidates if bool(row.get("selected"))])
    for state_key, state_rows in selected_by_state.items():
        if len(state_rows) != 1:
            invalid_states.add(state_key)
            violations.append(
                _selection_violation_row(state_rows[0], state_key, "selected_count_not_one", len(state_rows))
            )
        elif not bool(state_rows[0].get("actor_action")):
            invalid_states.add(state_key)
            violations.append(_selection_violation_row(state_rows[0], state_key, "selected_actor_invalid", 1))
    for rank in ranks:
        candidate_id = rank.get("selected_candidate_row_id")
        candidate = None if candidate_id is None else selected_by_id.get(int(cast(int, candidate_id)))
        if candidate is None:
            violations.append(
                {
                    **_candidate_evidence_metadata(
                        population="selected_actor_valid",
                        frame="selection state",
                        units="count",
                        available=False,
                        reason="rank row has no unique selected candidate audit row",
                    ),
                    "generation_cohort_id": str(rank.get("generation_cohort_id", "unknown")),
                    "state_key": _candidate_state_key(rank),
                    "state_count": 1,
                    "full_count": 1,
                    "finite_count": 0,
                    "missing_count": 1,
                    "violation": "missing_selected_candidate_join",
                    "count": 1,
                }
            )
            continue
        state_key = _candidate_state_key(candidate)
        if state_key in invalid_states:
            continue
        valid_candidate_count = _nonnegative_int(rank.get("valid_candidate_count")) or 0
        if not bool(rank.get("selected_actor_valid")) or valid_candidate_count <= 0:
            violations.append(_selection_violation_row(candidate, state_key, "no_actor_valid_selected_support", 1))
            continue
        if (_nonnegative_int(rank.get("finite_valid_label_count")) or 0) <= 0:
            violations.append(_selection_violation_row(candidate, state_key, "no_finite_actor_valid_alternative", 1))
            continue
        joined.append({**candidate, **rank, "state_key": state_key})

    summary_rows: list[dict[str, object]] = []
    for cohort_rows in _candidate_cohort_groups(joined):
        cohort = _candidate_generation_cohort_fields(cohort_rows[0])
        for metric, field, units in (
            ("regret_to_best", "regret_to_best", "dimensionless root-normalized target gain"),
            ("selected_rank", "selected_rank", "rank"),
            ("target_rri_rank", "target_rri_rank", "rank"),
        ):
            summary_rows.extend(
                _candidate_numeric_macro_rows(
                    cohort,
                    cohort_rows,
                    metric=metric,
                    field=field,
                    population="selected_actor_valid",
                    units=units,
                    frame="finite actor-valid alternatives within selection state",
                )
            )
    return {
        "summary_rows": sorted(summary_rows, key=_candidate_evidence_sort_key),
        "violation_rows": sorted(violations, key=_candidate_evidence_sort_key),
    }


def _sorted_candidate_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Materialize the full input once and impose a canonical row order."""

    materialized = [dict(row) for row in rows]
    return sorted(materialized, key=lambda row: json.dumps(row, sort_keys=True, default=str, separators=(",", ":")))


def _optional_bool(value: object) -> bool | None:
    """Return a persisted Boolean or explicit unavailable value."""

    return bool(value) if isinstance(value, (bool, np.bool_)) else None


def _validity_proposal_bucket(row: Mapping[str, object]) -> str:
    """Return an exact proposal signature or an explicit missing stage."""

    values = tuple(row.get(field) for field in ("mixture", "position", "strategy"))
    if any(value is None or str(value) == "" for value in values):
        return "missing_proposal"
    return "proposal:" + "|".join(str(value) for value in values)


def _validity_outcome_bucket(
    row: Mapping[str, object],
    *,
    actor: bool | None,
    selected: bool | None,
) -> str:
    """Return one terminal flow bucket without substituting scores for masks."""

    if selected is None:
        return "selection_unavailable"
    if selected and actor is None:
        return "selected_actor_implication_unavailable"
    if selected and actor is False:
        return "selected_actor_contract_violation"
    if selected:
        return "selected"
    if actor is None:
        return "actor_validity_unavailable"
    if actor:
        return "unselected_actor_valid"
    bitset = row.get("invalid_reason_bitset")
    if not isinstance(bitset, (int, np.integer)) or isinstance(bitset, (bool, np.bool_)) or int(bitset) < 0:
        return "invalid_reason_unavailable"
    return "invalid:" + "&".join(_invalid_reason_names(int(bitset)))


def _append_mask_intersections(
    evidence: dict[str, list[dict[str, object]]],
    cohort: Mapping[str, object],
    rows: list[dict[str, object]],
) -> None:
    """Append all Boolean mask cells plus missing-mask and implication evidence."""

    fields = ("actor_action", "oracle_label", "q_train", "selected")
    observed: Counter[tuple[bool | None, ...]] = Counter(
        tuple(_optional_bool(row.get(field)) for field in fields) for row in rows
    )
    complete_patterns = tuple(
        (actor, oracle, q_train, selected)
        for actor in (False, True)
        for oracle in (False, True)
        for q_train in (False, True)
        for selected in (False, True)
    )
    missing_patterns = tuple(sorted((pattern for pattern in observed if None in pattern), key=repr))
    for pattern in (*complete_patterns, *missing_patterns):
        actor, oracle, q_train, selected = pattern
        count = observed[pattern]
        contract_valid = (
            None
            if None in pattern
            else (not bool(selected) or bool(actor)) and (not bool(q_train) or (bool(actor) and bool(oracle)))
        )
        evidence["mask_intersection_rows"].append(
            {
                **cohort,
                "actor_action": actor,
                "oracle_label": oracle,
                "q_train": q_train,
                "selected": selected,
                "count": count,
                "denominator": len(rows),
                "fraction_of_all": _safe_fraction(count, len(rows)),
                "available": None not in pattern,
                "contract_valid": contract_valid,
            }
        )
    implications = {
        "selected_implies_actor_valid": (
            "selected",
            "actor_action",
        ),
        "q_train_implies_actor_valid": (
            "q_train",
            "actor_action",
        ),
        "q_train_implies_oracle_label": (
            "q_train",
            "oracle_label",
        ),
    }
    for implication, (antecedent_field, consequent_field) in implications.items():
        applicable = [row for row in rows if _optional_bool(row.get(antecedent_field)) is True]
        count = sum(_optional_bool(row.get(consequent_field)) is False for row in applicable)
        unavailable = sum(_optional_bool(row.get(consequent_field)) is None for row in applicable)
        evidence["invalid_implication_rows"].append(
            {
                **cohort,
                "implication": implication,
                "violation_count": int(count),
                "unavailable_count": int(unavailable),
                "denominator": len(rows),
                "status": "fail" if count else "unavailable" if unavailable else "pass",
            }
        )


def _invalid_reason_names(bitset: int) -> tuple[str, ...]:
    """Decode every set invalidity bit without choosing a primary reason."""

    names_by_bit = {bit: name for name, bit in INVALID_REASON_CODES.items()}
    names = [
        names_by_bit.get(bit, f"UNKNOWN_BIT_{bit}") for bit in range(max(1, bitset.bit_length())) if bitset & (1 << bit)
    ]
    return tuple(names or ("NO_REASON_BITS",))


def _reason_intersection_evidence(
    cohort: dict[str, object],
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Aggregate complete reason-bitset intersections through state and scene."""

    version_counts = Counter(
        str(version) if isinstance(version, str) and version else "missing"
        for row in rows
        for version in (row.get("reason_code_version"),)
    )
    supported_rows = [row for row in rows if row.get("reason_code_version") == INVALID_REASON_VERSION]
    states = _candidate_state_groups(rows)
    state_scenes = {key: str(value[0].get("scene", "unknown")) for key, value in states.items()}
    observed_bitsets = sorted(
        {
            int(value)
            for row in supported_rows
            if isinstance((value := row.get("invalid_reason_bitset")), (int, np.integer))
            and not isinstance(value, (bool, np.bool_))
            and int(value) >= 0
        }
    )
    output: list[dict[str, object]] = []
    for version, count in sorted(version_counts.items()):
        if version == INVALID_REASON_VERSION:
            continue
        output.append(
            {
                **cohort,
                "family_dimension": "invalid_reason_bitset_intersection",
                "family": "unavailable",
                "aggregation_level": "cohort_scene_macro",
                "reason_version": None if version == "missing" else version,
                "invalid_reason_bitset": None,
                "reason_names": (),
                "available": False,
                "blocker": "missing_reason_code_version" if version == "missing" else "unsupported_reason_code_version",
                "reason": (
                    "reason_code_version is absent; bit positions cannot be decoded"
                    if version == "missing"
                    else f"reason_code_version {version!r} is not supported by this decoder"
                ),
                "full_count": count,
                "finite_count": 0,
                "missing_count": count,
                "mean_state_fraction": None,
            }
        )
    for bitset in observed_bitsets:
        state_values: dict[str, float | None] = {}
        state_counts: dict[str, tuple[int, int, int]] = {}
        for state_key, state_rows in states.items():
            values = [
                int(value)
                for row in state_rows
                if row.get("reason_code_version") == INVALID_REASON_VERSION
                if isinstance((value := row.get("invalid_reason_bitset")), (int, np.integer))
                and not isinstance(value, (bool, np.bool_))
                and int(value) >= 0
            ]
            state_values[state_key] = None if not values else values.count(bitset) / len(values)
            state_counts[state_key] = (len(state_rows), len(values), len(state_rows) - len(values))
        reason_names = _invalid_reason_names(bitset)
        macro_rows = _composition_macro_rows(
            cohort,
            population="full_candidate_table",
            family_dimension="invalid_reason_bitset_intersection",
            family=" & ".join(reason_names),
            state_values=state_values,
            state_scenes=state_scenes,
            state_counts=state_counts,
            value_field="mean_state_fraction",
            units="fraction",
            unavailable_reason="invalid_reason_bitset unavailable",
            count_semantics="finite_count is the number of rows with a complete versioned reason bitset",
        )
        for row in macro_rows:
            row.update(
                {
                    "reason_version": str(supported_rows[0]["reason_code_version"]),
                    "invalid_reason_bitset": bitset,
                    "reason_names": reason_names,
                    "intersection_size": len(reason_names),
                }
            )
        output.extend(macro_rows)
    if not observed_bitsets and supported_rows:
        output.append(
            {
                **cohort,
                "family_dimension": "invalid_reason_bitset_intersection",
                "family": "unavailable",
                "aggregation_level": "cohort_scene_macro",
                "reason_version": INVALID_REASON_VERSION,
                "invalid_reason_bitset": None,
                "reason_names": (),
                "available": False,
                "reason": "invalid_reason_bitset unavailable for every candidate row with the supported version",
                "full_count": len(supported_rows),
                "finite_count": 0,
                "missing_count": len(supported_rows),
                "mean_state_fraction": None,
            }
        )
    return output


def _conditional_validity_evidence(
    cohort: dict[str, object],
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Aggregate actor admission and oracle coverage with exact denominators."""

    output: list[dict[str, object]] = []
    dimensions = (("all", "all"),) + tuple(
        (field, family)
        for field in ("strategy", "position", "mixture")
        for family in sorted({str(row.get(field, "unknown")) for row in rows})
    )
    for family_dimension, family in dimensions:
        family_rows = (
            rows
            if family_dimension == "all"
            else [row for row in rows if str(row.get(family_dimension, "unknown")) == family]
        )
        states = _candidate_state_groups(family_rows)
        state_scenes = {key: str(value[0].get("scene", "unknown")) for key, value in states.items()}
        for evidence_name in ("actor_valid_availability", "oracle_label_coverage_among_actor_valid"):
            state_values: dict[str, float | None] = {}
            state_counts: dict[str, tuple[int, int, int]] = {}
            for state_key, state_rows in states.items():
                if evidence_name == "actor_valid_availability":
                    values = [
                        value for row in state_rows if (value := _optional_bool(row.get("actor_action"))) is not None
                    ]
                    denominator_count = len(state_rows)
                else:
                    eligible = [row for row in state_rows if _optional_bool(row.get("actor_action")) is True]
                    values = [
                        value for row in eligible if (value := _optional_bool(row.get("oracle_label"))) is not None
                    ]
                    denominator_count = len(eligible)
                state_values[state_key] = None if not values else sum(values) / len(values)
                state_counts[state_key] = (denominator_count, len(values), denominator_count - len(values))
            macro_rows = _composition_macro_rows(
                cohort,
                population="full_candidate_table" if evidence_name == "actor_valid_availability" else "actor_valid",
                family_dimension=family_dimension,
                family=family,
                state_values=state_values,
                state_scenes=state_scenes,
                state_counts=state_counts,
                value_field="mean_state_fraction",
                units="fraction",
                unavailable_reason=(
                    "actor_action mask unavailable"
                    if evidence_name == "actor_valid_availability"
                    else "no actor-valid row with an available oracle-label mask"
                ),
                count_semantics=(
                    "actor-valid count divided by available actor masks"
                    if evidence_name == "actor_valid_availability"
                    else "oracle-label count divided by available oracle masks among actor-valid rows"
                ),
            )
            for row in macro_rows:
                row["evidence"] = evidence_name
                row["metric"] = evidence_name
            output.extend(macro_rows)
    return output


def _signed_margin_summary_rows(
    rows: list[ValidityAuditRow],
    *,
    evidence_status: str,
) -> list[dict[str, object]]:
    """Project per-unit signed margins without treating them as IID evidence."""

    return [
        {
            "cohort_id": row.cohort_id,
            "unit_id": row.unit_id,
            "scene_id": row.scene_id,
            "predicate_kind": row.predicate_kind,
            "predicate_owner": row.predicate_owner,
            "predicate_name": row.predicate_name,
            "comparison_operator": row.comparison_operator,
            "threshold": float(row.threshold),
            "unit": row.unit,
            "raw_measurement": None if row.raw_measurement is None else float(row.raw_measurement),
            "signed_margin": None if row.signed_margin is None else float(row.signed_margin),
            "available": row.raw_measurement is not None and row.signed_margin is not None,
            "missing_reason": row.missing_reason,
            "evidence_status": evidence_status,
        }
        for row in rows
    ]


def _signed_margin_summary_rows(
    rows: list[ValidityAuditRow],
    *,
    evidence_status: str,
) -> list[dict[str, object]]:
    """Aggregate weighted margins within state, then equally by scene and cohort."""

    output: list[dict[str, object]] = []
    state_groups: dict[tuple[str, str, str, int, str, str], list[ValidityAuditRow]] = {}
    for row in rows:
        state_id = (
            f"scene={row.scene_id}:rollout={row.rollout_id}:depth={row.depth}:"
            f"predicate={row.persisted_contract.identity_sha256}:independent={row.independent_contract.identity_sha256}"
        )
        output.append(
            {
                "cohort_id": row.cohort_id,
                "aggregation_level": "candidate_predicate",
                "unit_id": row.unit_id,
                "scene_id": row.scene_id,
                "rollout_id": row.rollout_id,
                "depth": row.depth,
                "state_id": state_id,
                "predicate_kind": row.predicate_kind,
                "predicate_owner": row.predicate_owner,
                "predicate_name": row.predicate_name,
                "persisted_contract_sha256": row.persisted_contract.identity_sha256,
                "independent_contract_sha256": row.independent_contract.identity_sha256,
                "comparison_operator": row.comparison_operator,
                "threshold": float(row.threshold),
                "unit": row.unit,
                "frame": row.independent_contract.frame,
                "raw_measurement": None if row.raw_measurement is None else float(row.raw_measurement),
                "signed_margin": None if row.signed_margin is None else float(row.signed_margin),
                "inverse_probability_weight": float(row.inverse_probability_weight),
                "sampled_count": 1,
                "complete_count": int(row.signed_margin is not None),
                "missing_count": int(row.signed_margin is None),
                "available": row.signed_margin is not None,
                "missing_reason": row.missing_reason,
                "evidence_status": evidence_status,
            }
        )
        state_groups.setdefault(
            (
                row.cohort_id,
                row.scene_id,
                row.rollout_id,
                row.depth,
                row.persisted_contract.identity_sha256,
                row.independent_contract.identity_sha256,
            ),
            [],
        ).append(row)

    state_rows: list[dict[str, object]] = []
    for state_key, state_group in sorted(state_groups.items()):
        cohort_id, scene_id, rollout_id, depth, persisted_identity, independent_identity = state_key
        complete = [row for row in state_group if row.signed_margin is not None]
        total_weight = sum(float(row.inverse_probability_weight) for row in complete)
        weighted_mean = (
            None
            if total_weight == 0.0
            else sum(float(cast(float, row.signed_margin)) * float(row.inverse_probability_weight) for row in complete)
            / total_weight
        )
        representative = state_group[0]
        state_id = (
            f"scene={scene_id}:rollout={rollout_id}:depth={depth}:"
            f"predicate={persisted_identity}:independent={independent_identity}"
        )
        state_rows.append(
            {
                "cohort_id": cohort_id,
                "aggregation_level": "state",
                "scene_id": scene_id,
                "rollout_id": rollout_id,
                "depth": depth,
                "state_id": state_id,
                "predicate_kind": representative.predicate_kind,
                "predicate_owner": representative.predicate_owner,
                "predicate_name": representative.predicate_name,
                "persisted_contract_sha256": persisted_identity,
                "independent_contract_sha256": independent_identity,
                "comparison_operator": representative.comparison_operator,
                "threshold": float(representative.threshold),
                "unit": representative.unit,
                "frame": representative.independent_contract.frame,
                "sampled_count": len(state_group),
                "complete_count": len(complete),
                "missing_count": len(state_group) - len(complete),
                "inverse_probability_weight_sum": float(total_weight),
                "weighted_mean_signed_margin": weighted_mean,
                "available": weighted_mean is not None,
                "evidence_status": evidence_status,
            }
        )
    output.extend(state_rows)

    scene_groups: dict[tuple[str, str, str, str], list[dict[str, object]]] = {}
    for row in state_rows:
        scene_groups.setdefault(
            (
                str(row["cohort_id"]),
                str(row["scene_id"]),
                str(row["persisted_contract_sha256"]),
                str(row["independent_contract_sha256"]),
            ),
            [],
        ).append(row)
    scene_rows: list[dict[str, object]] = []
    for scene_key, group in sorted(scene_groups.items()):
        cohort_id, scene_id, persisted_identity, independent_identity = scene_key
        defined = [row for row in group if row["weighted_mean_signed_margin"] is not None]
        scene_mean = (
            None
            if not defined
            else float(np.mean([float(cast(float, row["weighted_mean_signed_margin"])) for row in defined]))
        )
        representative = group[0]
        scene_rows.append(
            {
                "cohort_id": cohort_id,
                "aggregation_level": "scene_macro",
                "scene_id": scene_id,
                "persisted_contract_sha256": persisted_identity,
                "independent_contract_sha256": independent_identity,
                "predicate_kind": representative["predicate_kind"],
                "predicate_owner": representative["predicate_owner"],
                "predicate_name": representative["predicate_name"],
                "comparison_operator": representative["comparison_operator"],
                "threshold": representative["threshold"],
                "unit": representative["unit"],
                "frame": representative["frame"],
                "sampled_count": sum(int(cast(int, row["sampled_count"])) for row in group),
                "complete_count": sum(int(cast(int, row["complete_count"])) for row in group),
                "missing_count": sum(int(cast(int, row["missing_count"])) for row in group),
                "state_count": len(group),
                "defined_state_count": len(defined),
                "missing_state_count": len(group) - len(defined),
                "mean_state_signed_margin": scene_mean,
                "available": scene_mean is not None,
                "evidence_status": evidence_status,
            }
        )
    output.extend(scene_rows)

    cohort_groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in scene_rows:
        cohort_groups.setdefault(
            (
                str(row["cohort_id"]),
                str(row["persisted_contract_sha256"]),
                str(row["independent_contract_sha256"]),
            ),
            [],
        ).append(row)
    for cohort_key, group in sorted(cohort_groups.items()):
        cohort_id, persisted_identity, independent_identity = cohort_key
        defined = [row for row in group if row["mean_state_signed_margin"] is not None]
        cohort_mean = (
            None
            if not defined
            else float(np.mean([float(cast(float, row["mean_state_signed_margin"])) for row in defined]))
        )
        representative = group[0]
        output.append(
            {
                "cohort_id": cohort_id,
                "aggregation_level": "cohort_scene_macro",
                "scene_id": None,
                "persisted_contract_sha256": persisted_identity,
                "independent_contract_sha256": independent_identity,
                "predicate_kind": representative["predicate_kind"],
                "predicate_owner": representative["predicate_owner"],
                "predicate_name": representative["predicate_name"],
                "comparison_operator": representative["comparison_operator"],
                "threshold": representative["threshold"],
                "unit": representative["unit"],
                "frame": representative["frame"],
                "sampled_count": sum(int(cast(int, row["sampled_count"])) for row in group),
                "complete_count": sum(int(cast(int, row["complete_count"])) for row in group),
                "missing_count": sum(int(cast(int, row["missing_count"])) for row in group),
                "state_count": sum(int(cast(int, row["state_count"])) for row in group),
                "scene_count": len(group),
                "defined_scene_count": len(defined),
                "missing_scene_count": len(group) - len(defined),
                "mean_scene_signed_margin": cohort_mean,
                "available": cohort_mean is not None,
                "evidence_status": evidence_status,
            }
        )
    return output


def _weighted_boundary_agreement(
    rows: list[ValidityAuditRow],
    edges: tuple[float, ...],
    *,
    evidence_status: str,
) -> list[dict[str, object]]:
    """Return inverse-probability-weighted agreement in signed-margin bins."""

    groups: dict[tuple[str, str, str, str, str, str, str, float, str, int], list[ValidityAuditRow]] = {}
    for row in rows:
        if row.signed_margin is None or row.independent_valid is None:
            continue
        margin = float(row.signed_margin)
        bin_index = next(
            (
                index
                for index, (left, right) in enumerate(pairwise(edges))
                if margin >= left and (margin < right or (index == len(edges) - 2 and margin <= right))
            ),
            None,
        )
        if bin_index is None:
            continue
        boundary_key = (
            row.cohort_id,
            row.predicate_kind,
            row.predicate_owner,
            row.predicate_name,
            row.persisted_contract.identity_sha256,
            row.independent_contract.identity_sha256,
            row.comparison_operator,
            float(row.threshold),
            row.unit,
            bin_index,
        )
        groups.setdefault(boundary_key, []).append(row)
    output: list[dict[str, object]] = []
    for group_key, group in sorted(groups.items(), key=lambda item: repr(item[0])):
        cohort_id, kind, owner, name, persisted_identity, independent_identity, operator, threshold, unit, bin_index = (
            group_key
        )
        total_weight = sum(float(row.inverse_probability_weight) for row in group)
        agreement_weight = sum(
            float(row.inverse_probability_weight)
            for row in group
            if bool(row.persisted_valid) is bool(row.independent_valid)
        )
        output.append(
            {
                "cohort_id": cohort_id,
                "predicate_kind": kind,
                "predicate_owner": owner,
                "predicate_name": name,
                "persisted_contract_sha256": persisted_identity,
                "independent_contract_sha256": independent_identity,
                "comparison_operator": operator,
                "threshold": threshold,
                "unit": unit,
                "boundary_bin_index": bin_index,
                "boundary_bin_left": (None if not np.isfinite(edges[int(bin_index)]) else edges[int(bin_index)]),
                "boundary_bin_right": (
                    None if not np.isfinite(edges[int(bin_index) + 1]) else edges[int(bin_index) + 1]
                ),
                "sampled_count": len(group),
                "weighted_population": float(total_weight),
                "weighted_agreement": float(agreement_weight / total_weight),
                "evidence_status": evidence_status,
            }
        )
    return output


def _candidate_cohort_groups(rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    """Partition candidate evidence without pooling exact generation cohorts."""

    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(_candidate_generation_cohort(row), []).append(row)
    return [groups[key] for key in sorted(groups, key=repr)]


def _candidate_state_key(row: Mapping[str, object]) -> str:
    """Return the persisted rollout-step state identity or an explicit missing key."""

    rollout = row.get("rollout_row_id")
    step = row.get("step_row_id")
    if rollout is None or step is None:
        return f"missing-state:{row.get('candidate_row_id', 'unknown')}"
    return f"rollout={rollout}:step={step}"


def _candidate_state_groups(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """Group candidate rows by persisted decision state."""

    groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(_candidate_state_key(row), []).append(row)
    return groups


def _candidate_populations() -> tuple[tuple[str, Any], ...]:
    """Return the fixed all-versus-actor-valid support populations."""

    return (
        ("all", lambda _row: True),
        ("actor_valid", lambda row: bool(row.get("actor_action"))),
    )


def _candidate_evidence_metadata(
    *,
    population: str,
    frame: str,
    units: str,
    available: bool,
    reason: str | None,
) -> dict[str, object]:
    """Return the shared protocol and availability fields for evidence rows."""

    return {
        "protocol_version": _CANDIDATE_EVIDENCE_PROTOCOL_VERSION,
        "population": population,
        "coordinate_frame": frame,
        "units": units,
        "available": available,
        "reason": reason,
    }


def _candidate_evidence_sort_key(row: Mapping[str, object]) -> tuple[str, ...]:
    """Return a stable heterogeneous evidence-row ordering."""

    fields = (
        "generation_cohort_id",
        "population",
        "evidence",
        "metric",
        "aggregation_level",
        "scene",
        "state_key",
        "family_dimension",
        "family",
        "declared_shell",
        "cap_radius_deg",
        "azimuth_bin",
        "sin_elevation_bin",
        "violation",
    )
    return tuple(str(row.get(field, "")) for field in fields)


def _finite_unit_directions(rows: list[dict[str, object]]) -> np.ndarray:
    """Return finite nonzero unit directions from root-relative XYZ rows."""

    vectors: list[tuple[float, float, float]] = []
    for row in rows:
        x = _finite_or_none(row.get("root_relative_x_m"))
        y = _finite_or_none(row.get("root_relative_y_m"))
        z = _finite_or_none(row.get("root_relative_z_m"))
        if x is None or y is None or z is None:
            continue
        norm = float(np.linalg.norm((x, y, z)))
        if norm <= 0.0:
            continue
        vectors.append((x / norm, y / norm, z / norm))
    if not vectors:
        return np.empty((0, 3), dtype=np.float64)
    return np.asarray(vectors, dtype=np.float64)


def _fibonacci_sphere(count: int) -> np.ndarray:
    """Return a deterministic approximately equal-area unit-sphere grid."""

    indices = np.arange(count, dtype=np.float64)
    z = 1.0 - 2.0 * (indices + 0.5) / float(count)
    radius = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    golden_angle = np.pi * (3.0 - np.sqrt(5.0))
    azimuth = indices * golden_angle
    return np.column_stack((radius * np.cos(azimuth), radius * np.sin(azimuth), z))


def _spherical_cap_discrepancy(
    directions: np.ndarray,
    centers: np.ndarray,
    radius_deg: float,
) -> float:
    """Return maximum empirical-minus-uniform cap mass on a fixed grid."""

    cosine = float(np.cos(np.radians(radius_deg)))
    expected = (1.0 - cosine) / 2.0
    dots = np.clip(centers @ directions.T, -1.0, 1.0)
    empirical = np.mean(dots >= cosine, axis=1)
    return float(np.max(np.abs(empirical - expected)))


def _composition_macro_rows(
    cohort: dict[str, object],
    *,
    population: str,
    family_dimension: str,
    family: str,
    state_values: Mapping[str, float | None],
    state_scenes: Mapping[str, str],
    state_counts: Mapping[str, tuple[int, int, int]],
    value_field: str,
    units: str,
    unavailable_reason: str,
    count_semantics: str,
) -> list[dict[str, object]]:
    """Aggregate categorical state evidence through equal-weight scenes."""

    state_rows: list[dict[str, object]] = []
    defined_by_scene: dict[str, list[float]] = {}
    for state_key in sorted(state_values):
        value = state_values[state_key]
        scene = state_scenes[state_key]
        full_count, finite_count, missing_count = state_counts[state_key]
        if value is not None:
            defined_by_scene.setdefault(scene, []).append(value)
        state_rows.append(
            {
                **cohort,
                **_candidate_evidence_metadata(
                    population=population,
                    frame="categorical generation family",
                    units=units,
                    available=value is not None,
                    reason=None if value is not None else unavailable_reason,
                ),
                "family_dimension": family_dimension,
                "family": family,
                "aggregation_level": "state",
                "scene": scene,
                "state_key": state_key,
                "state_keys": (state_key,),
                "state_count": 1,
                "defined_state_count": int(value is not None),
                "undefined_state_count": int(value is None),
                "full_count": full_count,
                "finite_count": finite_count,
                "missing_count": missing_count,
                "count_semantics": count_semantics,
                value_field: value,
            }
        )

    scene_rows: list[dict[str, object]] = []
    scene_values: list[float] = []
    for scene in sorted(set(state_scenes.values())):
        state_keys = tuple(sorted(key for key, value in state_scenes.items() if value == scene))
        values = defined_by_scene.get(scene, [])
        scene_value = None if not values else float(np.mean(values))
        if scene_value is not None:
            scene_values.append(scene_value)
        scene_rows.append(
            {
                **cohort,
                **_candidate_evidence_metadata(
                    population=population,
                    frame="categorical generation family",
                    units=units,
                    available=scene_value is not None,
                    reason=None if scene_value is not None else unavailable_reason,
                ),
                "family_dimension": family_dimension,
                "family": family,
                "aggregation_level": "scene_macro",
                "scene": scene,
                "state_key": None,
                "state_keys": state_keys,
                "state_count": len(state_keys),
                "defined_state_count": len(values),
                "undefined_state_count": len(state_keys) - len(values),
                "full_count": sum(state_counts[key][0] for key in state_keys),
                "finite_count": sum(state_counts[key][1] for key in state_keys),
                "missing_count": sum(state_counts[key][2] for key in state_keys),
                "count_semantics": count_semantics,
                value_field: scene_value,
            }
        )

    all_state_keys = tuple(sorted(state_values))
    cohort_value = None if not scene_values else float(np.mean(scene_values))
    cohort_row = {
        **cohort,
        **_candidate_evidence_metadata(
            population=population,
            frame="categorical generation family",
            units=units,
            available=cohort_value is not None,
            reason=None if cohort_value is not None else unavailable_reason,
        ),
        "family_dimension": family_dimension,
        "family": family,
        "aggregation_level": "cohort_scene_macro",
        "scene": None,
        "state_key": None,
        "state_keys": all_state_keys,
        "state_count": len(all_state_keys),
        "scene_count": len(scene_values),
        "defined_state_count": sum(value is not None for value in state_values.values()),
        "undefined_state_count": sum(value is None for value in state_values.values()),
        "full_count": sum(counts[0] for counts in state_counts.values()),
        "finite_count": sum(counts[1] for counts in state_counts.values()),
        "missing_count": sum(counts[2] for counts in state_counts.values()),
        "count_semantics": count_semantics,
        value_field: cohort_value,
    }
    return [*state_rows, *scene_rows, cohort_row]


def _direction_macro_rows(
    cohort: dict[str, object],
    population: str,
    *,
    evidence: str,
    state_values: Mapping[str, float | None],
    state_scenes: Mapping[str, str],
    state_counts: Mapping[str, tuple[int, int]],
    value_field: str,
    units: str,
    unavailable_reason: str,
    protocol: Mapping[str, object],
    extra: Mapping[str, object] | None = None,
    sparse_state_zeros: bool = False,
    include_aggregate_state_keys: bool = True,
) -> list[dict[str, object]]:
    """Aggregate per-state direction statistics through equal-weight scenes.

    When ``sparse_state_zeros`` is true, defined zero-valued state rows are
    omitted. Their zero remains included in every scene/cohort denominator;
    absence of a state-bin row therefore means an implicit zero, not missing
    evidence. Aggregate rows remain complete.
    """

    details = {} if extra is None else dict(extra)
    state_rows: list[dict[str, object]] = []
    state_values_by_scene: dict[str, list[float]] = {}
    for state_key in sorted(state_values):
        value = state_values[state_key]
        scene = state_scenes[state_key]
        full_count, finite_count = state_counts[state_key]
        if value is not None:
            state_values_by_scene.setdefault(scene, []).append(value)
        if sparse_state_zeros and value == 0.0:
            continue
        state_rows.append(
            {
                **cohort,
                **_candidate_evidence_metadata(
                    population=population,
                    frame="unit sphere in root-centered ARIA world (RIGHT_HAND_Z_UP)",
                    units=units,
                    available=value is not None,
                    reason=None if value is not None else unavailable_reason,
                ),
                "evidence": evidence,
                "metric": evidence,
                "protocol": dict(protocol),
                "aggregation_level": "state",
                "scene": scene,
                "state_key": state_key,
                "state_keys": (state_key,),
                "state_count": 1,
                "defined_state_count": int(value is not None),
                "undefined_state_count": int(value is None),
                "full_count": full_count,
                "finite_count": finite_count,
                "missing_count": full_count - finite_count,
                value_field: value,
                **details,
            }
        )

    scene_rows: list[dict[str, object]] = []
    scene_values: list[float] = []
    for scene in sorted(set(state_scenes.values())):
        scene_state_keys = tuple(sorted(key for key, value in state_scenes.items() if value == scene))
        values = state_values_by_scene.get(scene, [])
        scene_value = None if not values else float(np.mean(values))
        if scene_value is not None:
            scene_values.append(scene_value)
        full_count = sum(state_counts[key][0] for key in scene_state_keys)
        finite_count = sum(state_counts[key][1] for key in scene_state_keys)
        scene_rows.append(
            {
                **cohort,
                **_candidate_evidence_metadata(
                    population=population,
                    frame="unit sphere in root-centered ARIA world (RIGHT_HAND_Z_UP)",
                    units=units,
                    available=scene_value is not None,
                    reason=None if scene_value is not None else unavailable_reason,
                ),
                "evidence": evidence,
                "metric": evidence,
                "protocol": dict(protocol),
                "aggregation_level": "scene_macro",
                "scene": scene,
                "state_key": None,
                "state_keys": scene_state_keys if include_aggregate_state_keys else None,
                "state_count": len(scene_state_keys),
                "defined_state_count": len(values),
                "undefined_state_count": len(scene_state_keys) - len(values),
                "full_count": full_count,
                "finite_count": finite_count,
                "missing_count": full_count - finite_count,
                value_field: scene_value,
                **details,
            }
        )

    all_state_keys = tuple(sorted(state_values))
    full_count = sum(counts[0] for counts in state_counts.values())
    finite_count = sum(counts[1] for counts in state_counts.values())
    cohort_row = {
        **cohort,
        **_candidate_evidence_metadata(
            population=population,
            frame="unit sphere in root-centered ARIA world (RIGHT_HAND_Z_UP)",
            units=units,
            available=bool(scene_values),
            reason=None if scene_values else unavailable_reason,
        ),
        "evidence": evidence,
        "metric": evidence,
        "protocol": dict(protocol),
        "aggregation_level": "cohort_scene_macro",
        "scene": None,
        "state_key": None,
        "state_keys": all_state_keys if include_aggregate_state_keys else None,
        "state_count": len(all_state_keys),
        "scene_count": len(scene_values),
        "defined_state_count": sum(value is not None for value in state_values.values()),
        "undefined_state_count": sum(value is None for value in state_values.values()),
        "full_count": full_count,
        "finite_count": finite_count,
        "missing_count": full_count - finite_count,
        value_field: None if not scene_values else float(np.mean(scene_values)),
        **details,
    }
    return [*state_rows, *scene_rows, cohort_row]


def _angular_support_rows(
    cohort: dict[str, object],
    population: str,
    state_directions: Mapping[str, np.ndarray],
    *,
    state_scenes: Mapping[str, str],
    state_counts: Mapping[str, tuple[int, int]],
    covering_reference: np.ndarray,
) -> list[dict[str, object]]:
    """Return state, equal-state scene, and equal-scene angular summaries."""

    covering_values: dict[str, float | None] = {}
    nn_values: dict[str, dict[str, float | None]] = {
        "q25": {},
        "median": {},
        "q75": {},
    }
    singleton_states: set[str] = set()
    for state_key, directions in state_directions.items():
        if directions.shape[0] == 0:
            covering_values[state_key] = None
            for values in nn_values.values():
                values[state_key] = None
            continue
        tree = cKDTree(directions)
        probes = np.vstack((covering_reference, -directions))
        covering_chords, _ = tree.query(probes, k=1, workers=1)
        covering_angles = np.degrees(2.0 * np.arcsin(np.clip(covering_chords / 2.0, 0.0, 1.0)))
        covering_values[state_key] = float(np.max(covering_angles))
        if directions.shape[0] < 2:
            singleton_states.add(state_key)
            for values in nn_values.values():
                values[state_key] = None
            continue
        neighbor_chords, _ = tree.query(directions, k=2, workers=1)
        separations = np.degrees(2.0 * np.arcsin(np.clip(neighbor_chords[:, 1] / 2.0, 0.0, 1.0)))
        q25, median, q75 = np.quantile(separations, (0.25, 0.5, 0.75)).tolist()
        nn_values["q25"][state_key] = float(q25)
        nn_values["median"][state_key] = float(median)
        nn_values["q75"][state_key] = float(q75)
    protocol = {
        "reference": "fixed Fibonacci sphere plus candidate antipodes",
        "covering_reference_count": _COVERING_REFERENCE_COUNT,
        "nearest_search": "exact scipy.spatial.cKDTree Euclidean chord distance",
        "angular_conversion": "2 asin(clamp(chord / 2, 0, 1))",
        "macro_order": "per-state statistic, equal-state scene mean, equal-scene cohort mean",
    }
    output = _direction_macro_rows(
        cohort,
        population,
        evidence="reference_grid_covering_radius",
        state_values=covering_values,
        state_scenes=state_scenes,
        state_counts=state_counts,
        value_field="mean_state_value",
        units="deg",
        unavailable_reason="no finite nonzero directions",
        protocol=protocol,
    )
    for quantile in ("q25", "median", "q75"):
        values = nn_values[quantile]
        output.extend(
            _direction_macro_rows(
                cohort,
                population,
                evidence=f"nearest_neighbor_angular_separation_{quantile}",
                state_values=values,
                state_scenes=state_scenes,
                state_counts=state_counts,
                value_field="mean_state_value",
                units="deg",
                unavailable_reason="nearest-neighbor separation requires at least two directions per state",
                protocol=protocol,
                extra={"singleton_state_count": len(singleton_states)},
            )
        )
    return output


def _candidate_numeric_macro_rows(
    cohort: dict[str, object],
    rows: list[dict[str, object]],
    *,
    metric: str,
    field: str,
    population: str,
    units: str,
    frame: str,
    extra: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    """Aggregate a finite candidate metric by state, then scene, then cohort."""

    states = _candidate_state_groups(rows)
    state_output: list[dict[str, object]] = []
    state_means_by_scene: dict[str, list[float]] = {}
    finite_count = 0
    for state_key, state_rows in sorted(states.items()):
        values = [value for row in state_rows if (value := _finite_or_none(row.get(field))) is not None]
        finite_count += len(values)
        scene = str(state_rows[0].get("scene", "unknown"))
        mean = None if not values else float(np.mean(values))
        if mean is not None:
            state_means_by_scene.setdefault(scene, []).append(mean)
        state_output.append(
            {
                **cohort,
                **_candidate_evidence_metadata(
                    population=population,
                    frame=frame,
                    units=units,
                    available=bool(values),
                    reason=None if values else f"no finite {field} values in state",
                ),
                "evidence": metric,
                "metric": metric,
                "source_field": field,
                "aggregation_level": "state",
                "scene": scene,
                "state_key": state_key,
                "state_count": 1,
                "full_count": len(state_rows),
                "finite_count": len(values),
                "missing_count": len(state_rows) - len(values),
                "mean": mean,
                "median": None if not values else float(np.median(values)),
                "min": None if not values else float(np.min(values)),
                "max": None if not values else float(np.max(values)),
                **({} if extra is None else dict(extra)),
            }
        )
    scene_output: list[dict[str, object]] = []
    scene_means: list[float] = []
    for scene, values in sorted(state_means_by_scene.items()):
        scene_mean = float(np.mean(values))
        scene_means.append(scene_mean)
        scene_output.append(
            {
                **cohort,
                **_candidate_evidence_metadata(
                    population=population,
                    frame=frame,
                    units=units,
                    available=True,
                    reason=None,
                ),
                "evidence": metric,
                "metric": metric,
                "source_field": field,
                "aggregation_level": "scene_macro",
                "scene": scene,
                "state_key": None,
                "state_keys": tuple(
                    row["state_key"] for row in state_output if row["scene"] == scene and row["available"]
                ),
                "state_count": len(values),
                "full_count": sum(int(cast(int, row["full_count"])) for row in state_output if row["scene"] == scene),
                "finite_count": sum(
                    int(cast(int, row["finite_count"])) for row in state_output if row["scene"] == scene
                ),
                "missing_count": sum(
                    int(cast(int, row["missing_count"])) for row in state_output if row["scene"] == scene
                ),
                "mean": scene_mean,
                **({} if extra is None else dict(extra)),
            }
        )
    cohort_row = {
        **cohort,
        **_candidate_evidence_metadata(
            population=population,
            frame=frame,
            units=units,
            available=bool(scene_means),
            reason=None if scene_means else f"no finite {field} values",
        ),
        "evidence": metric,
        "metric": metric,
        "source_field": field,
        "aggregation_level": "cohort_scene_macro",
        "scene": None,
        "state_key": None,
        "state_keys": tuple(sorted(states)),
        "state_count": len(states),
        "scene_count": len(scene_means),
        "full_count": len(rows),
        "finite_count": finite_count,
        "missing_count": len(rows) - finite_count,
        "mean": None if not scene_means else float(np.mean(scene_means)),
        **({} if extra is None else dict(extra)),
    }
    return [*state_output, *scene_output, cohort_row]


def _candidate_boolean_macro_rows(
    cohort: dict[str, object],
    rows: list[dict[str, object]],
    *,
    metric: str,
    field: str,
    population: str,
    true_is_support: bool,
    availability_field: str | None = None,
) -> list[dict[str, object]]:
    """Aggregate an observed Boolean by state, scene, then cohort."""

    prepared = []
    for row in rows:
        value = row.get(field)
        observed = isinstance(value, (bool, np.bool_))
        if availability_field is not None:
            observed = observed and _finite_or_none(row.get(availability_field)) is not None
        prepared.append(
            {
                **row,
                "_boolean_metric": None if not observed else float(bool(value) is true_is_support),
            }
        )
    return _candidate_numeric_macro_rows(
        cohort,
        prepared,
        metric=metric,
        field="_boolean_metric",
        population=population,
        units="fraction",
        frame="candidate path-validity contract",
        extra={
            "source_field": field,
            "true_is_support": true_is_support,
            "availability_field": availability_field,
        },
    )


def _joint_motion_support_rows(
    cohort: dict[str, object],
    rows: list[dict[str, object]],
    conjunction: tuple[str, ...],
) -> list[dict[str, object]]:
    """Evaluate only an explicitly requested motion-support conjunction."""

    prepared: list[dict[str, object]] = []
    motion_fields = (
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "path_min_clearance_m",
        "free_space_margin_m",
    )
    for row in rows:
        path_collision = row.get("path_collision")
        collision_observed = (
            isinstance(path_collision, (bool, np.bool_))
            and _finite_or_none(row.get("path_min_clearance_m")) is not None
        )
        terms = {
            "actor_valid": bool(row.get("actor_action")),
            "path_collision_free": None if not collision_observed else not bool(path_collision),
            "finite_motion": all(_finite_or_none(row.get(field)) is not None for field in motion_fields),
        }
        requested_terms = [terms[term] for term in conjunction]
        prepared.append(
            {
                **row,
                "_joint_support": None
                if any(term is None for term in requested_terms)
                else float(all(requested_terms)),
            }
        )
    return _candidate_numeric_macro_rows(
        cohort,
        prepared,
        metric="explicit_joint_motion_support",
        field="_joint_support",
        population="explicit_conjunction",
        units="fraction",
        frame="candidate motion-support contract",
        extra={"conjunction": conjunction},
    )


def _selection_violation_row(
    candidate: Mapping[str, object],
    state_key: str,
    violation: str,
    count: int,
) -> dict[str, object]:
    """Return one explicit selection-contract violation row."""

    return {
        **_candidate_generation_cohort_fields(candidate),
        **_candidate_evidence_metadata(
            population="selected_actor_valid",
            frame="selection state",
            units="count",
            available=False,
            reason=violation,
        ),
        "state_key": state_key,
        "state_count": 1,
        "full_count": count,
        "finite_count": 0,
        "missing_count": count,
        "violation": violation,
        "count": count,
    }


def candidate_plot_availability_rows(
    audit_rows: Iterable[Mapping[str, object]],
    rank_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Return explicit blockers for heavy candidate plots."""

    rows = [dict(row) for row in audit_rows]
    ranks = [dict(row) for row in rank_rows]
    geometry_rows = candidate_geometry_evidence_rows(rows)
    requirements = {
        "proposal calibration": (rows, ("sampler_probability",)),
        "root-relative XY": (rows, ("root_relative_x_m", "root_relative_y_m")),
        "radius / height / angles": (
            geometry_rows,
            ("root_radius_m", "root_relative_z_m", "root_azimuth_deg", "root_elevation_deg"),
        ),
        "orientation to target bearing": (
            geometry_rows,
            ("orientation_to_target_bearing_deg",),
        ),
        "motion support": (rows, ("motion_step_length_m", "motion_backward_step_m", "path_min_clearance_m")),
        "selection rank / regret": (ranks, ("selected_rank", "target_rri_rank", "regret_to_best")),
    }
    output: list[dict[str, object]] = []
    for evidence, (population, fields) in requirements.items():
        missing = tuple(
            field for field in fields if not any(_finite_or_none(row.get(field)) is not None for row in population)
        )
        output.append(
            {
                "evidence": evidence,
                "available": not missing,
                "missing_or_nonfinite_fields": missing,
                "detail": "finite evidence present" if not missing else f"unavailable: {', '.join(missing)}",
            }
        )
    return output


def comparable_policy_cohorts(reader: RolloutZarrStoreReader) -> dict[str, object]:
    """Build exact matched cohorts for scientifically valid policy comparison.

    Cohorts match on source sample, target identity/protocol, evaluation
    horizon, acquisition budget, and candidate/oracle configuration. Policy,
    human recipe/schedule, branch factor, and beam width identify the treatment
    dimension and are never averaged as if they were independent unmatched
    populations. The rollout config hash remains provenance, not a role label.

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
        first = cohort_rows[0]
        missing_context_fields = tuple(field for field in key_fields if _missing_cohort_value(first.get(field)))
        eligible = len(labels) >= 2 and not duplicate_labels and not missing_context_fields
        summary = {
            "cohort_id": str(first["cohort_id"]),
            "cohort_key": cohort_key,
            **{field: first[field] for field in key_fields},
            "comparison_labels": labels,
            "comparison_count": len(labels),
            "rollout_count": len(cohort_rows),
            "missing_context_fields": missing_context_fields,
            "eligible": eligible,
            "reason": "matched"
            if eligible
            else _cohort_ineligibility_reason(labels, duplicate_labels, missing_context_fields),
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


def policy_effect_evidence(
    artifact: ScientificAuditArtifact,
    *,
    bootstrap_samples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, object]:
    r"""Estimate exact-pair scene-macro policy effects from an independent audit.

    The bundle SHA-256 is verified before parameter checks or reduction. Only a
    PASS/CONFIRMATORY same-contract artifact can contribute. Within it,
    each endpoint must be complete, effect-eligible, equivalence-PASS, and
    covered by a mandatory-PASS cohort summary. Pairing then uses the complete
    pre-treatment match identity: normalized configs, root action set,
    persisted context, and raw assets. Selected poses and all downstream
    candidate/validity tables are outcomes and never enter the key.

    For contrast $B-A$, the scene-macro estimand is

    $$
    \hat\tau_{B-A}=\frac{1}{S}\sum_s\frac{1}{n_s}
    \sum_i\left(J_{s,i,B}-J_{s,i,A}\right).
    $$

    Confidence intervals resample scenes while retaining every pair within a
    sampled scene. They are suppressed below the audit's frozen 20-scene gate.
    Recovered headroom uses no numerical stabilizer and is emitted only when
    $J_{\mathrm{oracle-look}}-J_{\mathrm{learned-1}}$ is strictly greater than
    the artifact's frozen ``eta_q_min_headroom`` config value.

    Args:
        artifact: Sealed independent scientific-audit artifact.
        bootstrap_samples: Number of deterministic scene-cluster resamples.
        confidence: Central percentile interval probability in ``(0, 1)``.
        seed: Base seed; each contrast derives a stable independent seed.
    Returns:
        JSON-ready evidence containing exact pair rows, equal-weight scene
        means, per-contrast summaries, denominator diagnostics, and explicit
        fail-closed exclusions.

    Raises:
        ValueError: If inference parameters are invalid.
    """

    verify_scientific_audit_sha256(artifact)
    if int(bootstrap_samples) < 1:
        raise ValueError("bootstrap_samples must be positive.")
    if not 0.0 < float(confidence) < 1.0:
        raise ValueError("confidence must lie strictly between zero and one.")
    artifact_exclusions = _artifact_effect_gate_exclusions(artifact)
    exclusions = list(artifact_exclusions)
    eligible_rows: list[EndpointAuditRow] = []
    for row in artifact.endpoint_rows:
        row_exclusions = _endpoint_effect_exclusions(artifact, row)
        if artifact_exclusions or row_exclusions:
            exclusions.extend(row_exclusions)
        else:
            eligible_rows.append(row)

    grouped: dict[str, list[EndpointAuditRow]] = {}
    for row in eligible_rows:
        grouped.setdefault(row.match_identity.exact_match_sha256, []).append(row)

    exclusions.extend(_identity_mismatch_exclusions(eligible_rows))
    pair_rows: list[dict[str, object]] = []
    for contrast, roles in _POLICY_EFFECT_CONTRASTS.items():
        contrast_pairs, contrast_exclusions = _exact_contrast_pairs(grouped, contrast=contrast, roles=roles)
        pair_rows.extend(contrast_pairs)
        exclusions.extend(contrast_exclusions)

    eta_rows, denominator_rows, eta_exclusions = _eta_q_rows(
        grouped,
        threshold=float(artifact.config.eta_q_min_headroom),
    )
    pair_rows.extend(eta_rows)
    exclusions.extend(eta_exclusions)

    scene_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for contrast_index, contrast in enumerate((*_POLICY_EFFECT_CONTRASTS, "eta_q")):
        contrast_pairs = [row for row in pair_rows if row["contrast"] == contrast]
        contrast_exclusions = [row for row in exclusions if row["contrast"] in {contrast, "all"}]
        contrast_scene_rows, summary = _scene_macro_summary(
            contrast,
            contrast_pairs,
            contrast_exclusions,
            min_scenes=artifact.config.min_scenes_for_cluster_ci,
            bootstrap_samples=int(bootstrap_samples),
            confidence=float(confidence),
            seed=_contrast_seed(int(seed), contrast, contrast_index),
        )
        scene_rows.extend(contrast_scene_rows)
        summary_rows.append(summary)

    denominator_values = np.asarray(
        [float(cast(float, row["headroom_denominator"])) for row in denominator_rows],
        dtype=np.float64,
    )
    eligible_denominators = sum(bool(row["eta_eligible"]) for row in denominator_rows)
    return {
        "artifact_status": artifact.status.value,
        "comparison_protocol": artifact.comparison_protocol.value,
        "endpoint_row_count": len(artifact.endpoint_rows),
        "eligible_endpoint_row_count": len(eligible_rows),
        "validity_row_count_ignored": len(artifact.validity_rows),
        "eta_headroom_threshold": float(artifact.config.eta_q_min_headroom),
        "eta_headroom_threshold_provenance": "artifact.config.eta_q_min_headroom",
        "min_scenes_for_cluster_ci": artifact.config.min_scenes_for_cluster_ci,
        "pair_rows": pair_rows,
        "scene_rows": scene_rows,
        "summary_rows": summary_rows,
        "exclusion_rows": exclusions,
        "headroom_denominator_rows": denominator_rows,
        "headroom_denominator_summary": {
            "count": int(denominator_values.size),
            "eligible_count": int(eligible_denominators),
            "excluded_count": int(denominator_values.size - eligible_denominators),
            **_distribution_summary(denominator_values),
        },
    }


def _artifact_effect_gate_exclusions(artifact: ScientificAuditArtifact) -> list[dict[str, object]]:
    """Return artifact-wide blockers that suppress every confirmatory effect."""

    blockers: list[dict[str, object]] = []
    if artifact.status is not AuditStatus.PASS:
        blockers.append(
            {
                "contrast": "all",
                "cohort_id": None,
                "reason": "artifact_status_not_pass",
                "detail": artifact.status.value,
            }
        )
    if artifact.readiness is not AuditReadiness.CONFIRMATORY:
        blockers.append(
            {
                "contrast": "all",
                "cohort_id": None,
                "reason": "artifact_not_confirmatory",
                "detail": artifact.readiness.value,
            }
        )
    if artifact.comparison_protocol is not AuditComparisonProtocol.SAME_CONTRACT:
        blockers.append(
            {
                "contrast": "all",
                "cohort_id": None,
                "reason": "comparison_protocol_mismatch",
                "detail": artifact.comparison_protocol.value,
            }
        )
    return blockers


def _endpoint_effect_exclusions(
    artifact: ScientificAuditArtifact,
    row: EndpointAuditRow,
) -> list[dict[str, object]]:
    """Return row-level reasons that prevent endpoint-effect admission."""

    role = row.match_identity.treatment.semantic_role
    contrasts = _contrasts_for_role(role)
    base = {
        "unit_id": row.unit_id,
        "scene_id": row.scene_id,
        "cohort_id": row.match_identity.exact_match_sha256,
        "semantic_role": role.value,
    }
    reasons: list[str] = []
    if row.evaluation_status is not RowEvaluationStatus.COMPLETE or not row.effect_eligible:
        reasons.append("blocked_endpoint")
    if row.equivalence_verdict is not EquivalenceVerdict.PASS:
        reasons.append("endpoint_equivalence_not_pass")
    if row.endpoint_gain is None or not np.isfinite(float(row.endpoint_gain)):
        reasons.append("missing_endpoint_gain")
    if role in {PolicySemanticRole.LEARNED_ONE_STEP, PolicySemanticRole.LEARNED_QH}:
        if row.match_identity.treatment.model_checkpoint_sha256 is None:
            reasons.append("missing_checkpoint")
    if row.source_store_sha256 != artifact.provenance.source_store_sha256:
        reasons.append("source_store_mismatch")
    if row.split_manifest_sha256 != artifact.provenance.split_manifest_sha256:
        reasons.append("split_manifest_mismatch")
    try:
        measured_raw_asset_context = named_sha256_context_hash(row.raw_assets)
    except ValueError:
        measured_raw_asset_context = None
    if measured_raw_asset_context != row.match_identity.raw_asset_context_sha256:
        reasons.append("raw_asset_context_mismatch")
    cohort_summaries = [summary for summary in artifact.cohort_summaries if summary.cohort_id == row.cohort_id]
    if not cohort_summaries:
        reasons.append("missing_cohort_summary")
    elif len(cohort_summaries) > 1:
        reasons.append("duplicate_cohort_summary")
    elif cohort_summaries[0].mandatory_status is not MandatoryCohortStatus.PASS:
        reasons.append("cohort_mandatory_not_pass")
    return [
        {**base, "contrast": contrast, "reason": reason, "detail": row.missing_reason}
        for contrast in contrasts
        for reason in reasons
    ]


def _contrasts_for_role(role: PolicySemanticRole) -> tuple[str, ...]:
    """Return predeclared contrasts that require one semantic role."""

    contrasts = tuple(contrast for contrast, roles in _POLICY_EFFECT_CONTRASTS.items() if role in roles)
    if role in {
        PolicySemanticRole.LEARNED_ONE_STEP,
        PolicySemanticRole.LEARNED_QH,
        PolicySemanticRole.ORACLE_LOOKAHEAD,
    }:
        return (*contrasts, "eta_q")
    return contrasts


def _exact_contrast_pairs(
    grouped: Mapping[str, list[EndpointAuditRow]],
    *,
    contrast: str,
    roles: tuple[PolicySemanticRole, PolicySemanticRole],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Pair unique semantic roles inside exact non-treatment cohorts."""

    pairs: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for cohort_id, rows in sorted(grouped.items()):
        by_role: dict[PolicySemanticRole, list[EndpointAuditRow]] = {}
        for row in rows:
            by_role.setdefault(row.match_identity.treatment.semantic_role, []).append(row)
        missing = tuple(role.value for role in roles if not by_role.get(role))
        duplicate = tuple(role.value for role in roles if len(by_role.get(role, ())) > 1)
        if missing or duplicate:
            scene_ids = tuple(sorted({row.scene_id for row in rows}))
            if missing:
                exclusions.append(
                    {
                        "contrast": contrast,
                        "cohort_id": cohort_id,
                        "scene_ids": scene_ids,
                        "reason": "missing_role",
                        "roles": missing,
                    }
                )
            if duplicate:
                exclusions.append(
                    {
                        "contrast": contrast,
                        "cohort_id": cohort_id,
                        "scene_ids": scene_ids,
                        "reason": "duplicate_role",
                        "roles": duplicate,
                    }
                )
            continue
        baseline = by_role[roles[0]][0]
        treatment = by_role[roles[1]][0]
        identity_reason = _same_exact_identity_reason(baseline, treatment)
        if identity_reason is not None:
            exclusions.append(
                {
                    "contrast": contrast,
                    "cohort_id": cohort_id,
                    "scene_ids": tuple(sorted({baseline.scene_id, treatment.scene_id})),
                    "reason": identity_reason,
                }
            )
            continue
        assert baseline.endpoint_gain is not None and treatment.endpoint_gain is not None
        pairs.append(
            {
                "contrast": contrast,
                "cohort_id": cohort_id,
                "scene_id": baseline.scene_id,
                "baseline_role": roles[0].value,
                "treatment_role": roles[1].value,
                "baseline_unit_id": baseline.unit_id,
                "treatment_unit_id": treatment.unit_id,
                "baseline_endpoint_gain": float(baseline.endpoint_gain),
                "treatment_endpoint_gain": float(treatment.endpoint_gain),
                "effect": float(treatment.endpoint_gain - baseline.endpoint_gain),
            }
        )
    return pairs, exclusions


def _same_exact_identity_reason(left: EndpointAuditRow, right: EndpointAuditRow) -> str | None:
    """Return a fail-closed reason if a purported exact pair drifts."""

    if left.scene_id != right.scene_id:
        return "scene_mismatch"
    if left.source_sample_key != right.source_sample_key or left.target_id != right.target_id:
        return "source_target_context_mismatch"
    left_identity = left.match_identity
    right_identity = right.match_identity
    if left_identity.root_action_set_sha256 != right_identity.root_action_set_sha256:
        return "root_action_set_mismatch"
    if left_identity.configs.normalized_context_sha256 != right_identity.configs.normalized_context_sha256:
        return "normalized_config_mismatch"
    if left_identity.persisted_context_sha256 != right_identity.persisted_context_sha256:
        return "persisted_context_mismatch"
    if left_identity.raw_asset_context_sha256 != right_identity.raw_asset_context_sha256:
        return "raw_asset_context_mismatch"
    if left_identity.exact_match_sha256 != right_identity.exact_match_sha256:
        return "exact_match_mismatch"
    return None


def _identity_mismatch_exclusions(rows: list[EndpointAuditRow]) -> list[dict[str, object]]:
    """Explain why otherwise corresponding policy rows land in different cohorts."""

    by_logical_unit: dict[tuple[str, str, str, int | None], list[EndpointAuditRow]] = {}
    for row in rows:
        key = (row.scene_id, row.source_sample_key, row.target_id, row.budget)
        by_logical_unit.setdefault(key, []).append(row)

    exclusions: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    mismatch_role_pairs = (
        *_POLICY_EFFECT_CONTRASTS.items(),
        ("eta_q", (PolicySemanticRole.LEARNED_ONE_STEP, PolicySemanticRole.LEARNED_QH)),
        ("eta_q", (PolicySemanticRole.LEARNED_ONE_STEP, PolicySemanticRole.ORACLE_LOOKAHEAD)),
    )
    for logical_key, logical_rows in sorted(by_logical_unit.items()):
        for contrast, roles in mismatch_role_pairs:
            left_rows = [row for row in logical_rows if row.match_identity.treatment.semantic_role is roles[0]]
            right_rows = [row for row in logical_rows if row.match_identity.treatment.semantic_role is roles[1]]
            for left in left_rows:
                for right in right_rows:
                    if left.match_identity.exact_match_sha256 == right.match_identity.exact_match_sha256:
                        continue
                    for reason in _identity_component_mismatches(left, right):
                        pair_key = (contrast, left.unit_id, right.unit_id, reason, repr(logical_key))
                        if pair_key in seen:
                            continue
                        seen.add(pair_key)
                        exclusions.append(
                            {
                                "contrast": contrast,
                                "cohort_id": None,
                                "scene_ids": (logical_key[0],),
                                "reason": reason,
                                "left_unit_id": left.unit_id,
                                "right_unit_id": right.unit_id,
                            }
                        )
    return exclusions


def _identity_component_mismatches(left: EndpointAuditRow, right: EndpointAuditRow) -> tuple[str, ...]:
    """Return every exact-match component that differs between two rows."""

    reasons: list[str] = []
    if left.source_store_sha256 != right.source_store_sha256:
        reasons.append("source_store_mismatch")
    if left.split_manifest_sha256 != right.split_manifest_sha256:
        reasons.append("split_manifest_mismatch")
    if left.match_identity.root_action_set_sha256 != right.match_identity.root_action_set_sha256:
        reasons.append("root_action_set_mismatch")
    if left.match_identity.configs.normalized_context_sha256 != right.match_identity.configs.normalized_context_sha256:
        reasons.append("normalized_config_mismatch")
    if left.match_identity.persisted_context_sha256 != right.match_identity.persisted_context_sha256:
        reasons.append("persisted_context_mismatch")
    if left.match_identity.raw_asset_context_sha256 != right.match_identity.raw_asset_context_sha256:
        reasons.append("raw_asset_context_mismatch")
    return tuple(reasons or ("exact_match_mismatch",))


def _eta_q_rows(
    grouped: Mapping[str, list[EndpointAuditRow]],
    *,
    threshold: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Return gated recovered-headroom rows without an epsilon denominator."""

    roles = (
        PolicySemanticRole.LEARNED_ONE_STEP,
        PolicySemanticRole.LEARNED_QH,
        PolicySemanticRole.ORACLE_LOOKAHEAD,
    )
    eta_rows: list[dict[str, object]] = []
    denominator_rows: list[dict[str, object]] = []
    exclusions: list[dict[str, object]] = []
    for cohort_id, rows in sorted(grouped.items()):
        by_role: dict[PolicySemanticRole, list[EndpointAuditRow]] = {}
        for row in rows:
            by_role.setdefault(row.match_identity.treatment.semantic_role, []).append(row)
        missing = tuple(role.value for role in roles if not by_role.get(role))
        duplicate = tuple(role.value for role in roles if len(by_role.get(role, ())) > 1)
        if missing or duplicate:
            if missing:
                exclusions.append(
                    {"contrast": "eta_q", "cohort_id": cohort_id, "reason": "missing_role", "roles": missing}
                )
            if duplicate:
                exclusions.append(
                    {"contrast": "eta_q", "cohort_id": cohort_id, "reason": "duplicate_role", "roles": duplicate}
                )
            continue
        learned, qh, look = (by_role[role][0] for role in roles)
        identity_reason = _same_exact_identity_reason(learned, qh) or _same_exact_identity_reason(learned, look)
        if identity_reason is not None:
            exclusions.append({"contrast": "eta_q", "cohort_id": cohort_id, "reason": identity_reason})
            continue
        assert learned.endpoint_gain is not None and qh.endpoint_gain is not None and look.endpoint_gain is not None
        numerator = float(qh.endpoint_gain - learned.endpoint_gain)
        denominator = float(look.endpoint_gain - learned.endpoint_gain)
        exclusion_reason: str | None = None
        if denominator < 0.0:
            exclusion_reason = "eta_denominator_negative"
        elif denominator == 0.0:
            exclusion_reason = "eta_denominator_zero"
        elif denominator <= threshold:
            exclusion_reason = "eta_denominator_below_threshold"
        denominator_rows.append(
            {
                "cohort_id": cohort_id,
                "scene_id": learned.scene_id,
                "headroom_denominator": denominator,
                "threshold": threshold,
                "eta_eligible": exclusion_reason is None,
                "exclusion_reason": exclusion_reason,
            }
        )
        if exclusion_reason is not None:
            exclusions.append(
                {
                    "contrast": "eta_q",
                    "cohort_id": cohort_id,
                    "scene_ids": (learned.scene_id,),
                    "reason": exclusion_reason,
                    "headroom_denominator": denominator,
                    "threshold": threshold,
                }
            )
            continue
        eta_rows.append(
            {
                "contrast": "eta_q",
                "cohort_id": cohort_id,
                "scene_id": learned.scene_id,
                "baseline_role": PolicySemanticRole.LEARNED_ONE_STEP.value,
                "treatment_role": PolicySemanticRole.LEARNED_QH.value,
                "baseline_unit_id": learned.unit_id,
                "treatment_unit_id": qh.unit_id,
                "baseline_endpoint_gain": float(learned.endpoint_gain),
                "treatment_endpoint_gain": float(qh.endpoint_gain),
                "oracle_lookahead_endpoint_gain": float(look.endpoint_gain),
                "headroom_denominator": denominator,
                "raw_qh_effect": numerator,
                "effect": numerator / denominator,
            }
        )
    return eta_rows, denominator_rows, exclusions


def _scene_macro_summary(
    contrast: str,
    pair_rows: list[dict[str, object]],
    exclusions: list[dict[str, object]],
    *,
    min_scenes: int,
    bootstrap_samples: int,
    confidence: float,
    seed: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Aggregate paired effects within scene and then equally across scenes."""

    effects_by_scene: dict[str, list[float]] = {}
    for row in pair_rows:
        effects_by_scene.setdefault(str(row["scene_id"]), []).append(float(cast(float, row["effect"])))
    scene_rows: list[dict[str, object]] = [
        {
            "contrast": contrast,
            "scene_id": scene_id,
            "pair_count": len(effects),
            "scene_mean_effect": float(np.mean(np.asarray(effects, dtype=np.float64))),
        }
        for scene_id, effects in sorted(effects_by_scene.items())
    ]
    scene_means = np.asarray(
        [float(cast(float, row["scene_mean_effect"])) for row in scene_rows],
        dtype=np.float64,
    )
    scene_count = int(scene_means.size)
    effect = float(np.mean(scene_means)) if scene_count else None
    ci_low: float | None = None
    ci_high: float | None = None
    if scene_count >= min_scenes:
        rng = np.random.default_rng(seed)
        samples = np.empty(bootstrap_samples, dtype=np.float64)
        for index in range(bootstrap_samples):
            sampled_indices = rng.integers(0, scene_count, size=scene_count)
            samples[index] = float(np.mean(scene_means[sampled_indices]))
        alpha = (1.0 - confidence) / 2.0
        ci_low, ci_high = (float(value) for value in np.quantile(samples, (alpha, 1.0 - alpha)))
    reason_counts = Counter(str(row["reason"]) for row in exclusions)
    return scene_rows, {
        "contrast": contrast,
        "estimable": scene_count > 0,
        "inference_status": "cluster_ci" if ci_low is not None else "descriptive" if scene_count else "no_estimate",
        "pair_count": len(pair_rows),
        "scene_count": scene_count,
        "missing_role_count": reason_counts["missing_role"],
        "duplicate_role_count": reason_counts["duplicate_role"],
        "exclusion_count": len(exclusions),
        "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "scene_macro_mean": effect,
        "cluster_ci_low": ci_low,
        "cluster_ci_high": ci_high,
        "cluster_ci_confidence": confidence if ci_low is not None else None,
        "cluster_bootstrap_samples": bootstrap_samples if ci_low is not None else 0,
        "cluster_ci_min_scenes": min_scenes,
    }


def _contrast_seed(seed: int, contrast: str, index: int) -> int:
    """Derive a stable NumPy seed without process-randomized Python hashing."""

    digest = hashlib.sha256(f"{seed}:{index}:{contrast}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _distribution_summary(values: np.ndarray) -> dict[str, float | None]:
    """Return compact finite distribution statistics for denominator audit."""

    if values.size == 0:
        return {"min": None, "q25": None, "median": None, "q75": None, "max": None}
    return {
        "min": float(np.min(values)),
        "q25": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "q75": float(np.percentile(values, 75)),
        "max": float(np.max(values)),
    }


def paired_policy_comparison_rows(
    reader: RolloutZarrStoreReader,
    *,
    bootstrap_samples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> list[dict[str, object]]:
    """Summarize diagnostic persisted-return differences over exact cohorts.

    This legacy reducer never supplies confirmatory inference. Every row is
    labelled ``diagnostic_proxy`` with persisted cumulative root gain as its
    metric source; use :func:`policy_effect_evidence` for audited endpoint $J$.

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
                    "evidence_status": "diagnostic_proxy",
                    "metric_source": "persisted_cumulative_root_gain",
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
    chain_ids = np.asarray(reader.array("rollouts/chain_id"), dtype=np.int64).reshape(-1)
    final_rri = np.asarray(reader.array("rollouts/final_cumulative_target_rri"), dtype=np.float64).reshape(-1)
    final_gain = np.asarray(reader.array("rollouts/final_cumulative_target_root_gain"), dtype=np.float64).reshape(-1)
    evaluation_horizon = int(reader.root.attrs.get("q_h_horizon", -1))

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
            "target_protocol": protocols[index],
            "evaluation_horizon": evaluation_horizon,
            "horizon": int(horizons[index]),
            "acquisition_budget_steps": int(horizons[index]),
            "branch_factor": int(branch_factors[index]),
            "beam_width": int(beam_widths[index]),
            "candidate_config": candidate_configs[index],
            "oracle_config": oracle_configs[index],
            "branch_schedule": schedules[index],
            "policy": policies[index],
            "rollout_config_hash": rollout_configs[index],
            "final_cumulative_target_rri": _finite_or_none(final_rri[index]),
            "final_cumulative_target_root_gain": _finite_or_none(final_gain[index]),
        }
        cohort_key = json.dumps({field: row[field] for field in _POLICY_COHORT_KEY_FIELDS}, sort_keys=True)
        row["cohort_key"] = cohort_key
        row["cohort_id"] = _cohort_id_from_key(cohort_key)
        rows.append(row)

    for row in rows:
        treatment = ",".join(f"{field}={row[field]}" for field in _POLICY_TREATMENT_FIELDS)
        row["comparison_label"] = f"{row['policy']}@{treatment}"
    return rows


def _decoded_array(reader: RolloutZarrStoreReader, path: str, dictionary: str) -> list[str]:
    ids = np.asarray(reader.array(path), dtype=np.int64).reshape(-1)
    values = _read_string_array(reader, f"dictionaries/{dictionary}")
    return [values[int(value)] if 0 <= int(value) < len(values) else "" for value in ids.tolist()]


def _cohort_ineligibility_reason(
    labels: tuple[str, ...],
    duplicates: tuple[str, ...],
    missing_context_fields: tuple[str, ...],
) -> str:
    if missing_context_fields:
        return f"exact comparison context is missing: {', '.join(missing_context_fields)}"
    if len(labels) < 2:
        return "only one policy treatment is represented for this exact cohort"
    if duplicates:
        return f"multiple rollout chains make policy-treatment rows ambiguous: {', '.join(duplicates)}"
    return "not comparable"


def _missing_cohort_value(value: object) -> bool:
    return value is None or value == "" or value == -1


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


def _nonnegative_int(*values: object) -> int | None:
    """Return the first non-negative integer-like value, if present."""

    for value in values:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _nonempty_text(value: object) -> str | None:
    """Return non-empty persisted text without fabricating a fallback."""

    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _nonnegative_float(value: object) -> float | None:
    """Return one finite non-negative float, if present."""

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) and parsed >= 0.0 else None


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    """Return a finite metadata ratio without fabricating zero-denominator values."""

    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _snippets_per_scene(coverage: dict[str, Any]) -> tuple[int, float, int] | None:
    """Summarize unique manifest snippets per scene without opening Zarr tables."""

    sources = coverage.get("sources")
    if not isinstance(sources, list) or not sources:
        return None
    snippets_by_scene: dict[str, set[str]] = {}
    for source in sources:
        if not isinstance(source, dict):
            return None
        scene = _nonempty_text(source.get("scene_id"))
        snippet = _nonempty_text(source.get("snippet_id"))
        if scene is None or snippet is None:
            return None
        snippets_by_scene.setdefault(scene, set()).add(snippet)
    return _min_median_max(len(snippets) for snippets in snippets_by_scene.values())


def _min_median_max(values: Iterable[int]) -> tuple[int, float, int] | None:
    """Return an integer min/median/max summary without inventing an empty population."""

    sizes = sorted(int(value) for value in values)
    if not sizes:
        return None
    return sizes[0], float(np.median(sizes)), sizes[-1]


def _split_counts(value: object) -> dict[str, int] | None:
    """Normalize persisted split counts or preserve unavailable metadata."""

    if not isinstance(value, dict):
        return None
    output: dict[str, int] = {}
    for split, count in value.items():
        parsed = _nonnegative_int(count)
        if parsed is None:
            return None
        output[str(split)] = parsed
    return output


def _rollout_split_counts(reader: RolloutZarrStoreReader) -> dict[str, int] | None:
    """Count persisted rollout rows by their decoded split identifier."""

    try:
        split_ids = np.asarray(reader.array("rollouts/split_id"), dtype=np.int64).reshape(-1)
        encoded_names = np.asarray(reader.array("dictionaries/split"), dtype=np.uint8)
        names = json.loads(encoded_names.tobytes().decode("utf-8"))
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        return None
    if np.any(split_ids < 0) or np.any(split_ids >= len(names)):
        return None
    counts: Counter[str] = Counter(str(names[int(split_id)]) for split_id in split_ids)
    return dict(sorted(counts.items()))


__all__ = [
    "RolloutSuspiciousQueryConfig",
    "candidate_audit_rows",
    "candidate_evidence_availability_rows",
    "candidate_direction_evidence",
    "candidate_family_composition_rows",
    "candidate_flow_rows",
    "candidate_geometry_evidence_rows",
    "candidate_group_summary_rows",
    "candidate_plot_availability_rows",
    "candidate_proposal_calibration_rows",
    "candidate_motion_support_evidence",
    "candidate_regret_evidence",
    "candidate_result_diagnostic_counts",
    "candidate_selection_family_rows",
    "candidate_selection_rank_family_rows",
    "candidate_spatial_support_evidence",
    "candidate_state_composition_evidence",
    "candidate_target_view_evidence",
    "candidate_validity_evidence",
    "comparable_policy_cohorts",
    "decode_invalid_reason",
    "decode_position_id",
    "decode_strategy_id",
    "decode_target_invalid_reason",
    "discounted_rollout_return_rows",
    "discover_rollout_store_paths",
    "exact_policy_role_rows",
    "mask_combination_rows",
    "paired_policy_comparison_rows",
    "policy_effect_evidence",
    "oracle_headroom_evidence",
    "reconstruction_endpoint_rows",
    "reconstruction_endpoint_summary_rows",
    "reconstruction_metric_summary_rows",
    "root_relative_candidate_rows",
    "rollout_store_inventory_rows",
    "rollout_statistics",
    "runtime_storage_statistics",
    "rollout_step_objective_rows",
    "rollout_endpoint_metric_summary",
    "rollout_header_summary",
    "selected_candidate_rank_rows",
    "selected_depth_preview",
    "selected_depth_summary_rows",
    "store_invariant_rows",
    "suspicious_rollout_rows",
    "target_audit_rows",
    "temporal_metric_summary_rows",
    "validity_waterfall_rows",
    "validity_audit_evidence",
]
