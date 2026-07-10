"""Read-only inspection helpers for rollout Zarr stores.

This module keeps Streamlit, CLI, and tests away from ad hoc Zarr joins. The
helpers return plain dictionaries and NumPy-backed scalar values so UI code can
choose its own rendering library without owning rollout-store semantics.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import zarr

from ..oracle.target_selection import TARGET_INVALID_REASON_CODES
from ..pose_generation import CandidatePositionMode, ViewDirectionMode, candidate_position_id, candidate_strategy_id
from .manifest import read_rollout_store_manifest
from .trace import INVALID_REASON_CODES, _candidate_invalid_reasons
from .zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION, RolloutZarrStoreReader, _required_groups

_INVALID_REASON_NAMES = {int(code): name for name, code in INVALID_REASON_CODES.items()}
_TARGET_INVALID_REASON_NAMES = {int(code): name for name, code in TARGET_INVALID_REASON_CODES.items()}
_POSITION_NAMES = {candidate_position_id(mode): mode.value for mode in CandidatePositionMode}
_STRATEGY_NAMES = {candidate_strategy_id(mode): mode.value for mode in ViewDirectionMode}


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


def decode_invalid_reason(reason: int | np.integer[Any]) -> str:
    """Return the stable invalid-reason name for one numeric code."""

    return _INVALID_REASON_NAMES.get(int(reason), f"reason_{int(reason)}")


def decode_target_invalid_reason(reason: int | np.integer[Any]) -> str:
    """Return the stable target-invalidity reason name for one numeric code."""

    return _TARGET_INVALID_REASON_NAMES.get(int(reason), f"target_reason_{int(reason)}")


def decode_position_id(position_id: int | np.integer[Any]) -> str:
    """Return the stable position-family name for one numeric id."""

    return _POSITION_NAMES.get(int(position_id), "unknown" if int(position_id) < 0 else f"position_{int(position_id)}")


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


def rollout_store_inventory_rows(store_paths: Iterable[Path]) -> list[dict[str, object]]:
    """Return schema, validation, count, lineage, and storage rows for stores."""

    rows = [_rollout_store_inventory_row(Path(path).expanduser().resolve()) for path in store_paths]
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


def candidate_audit_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Return candidate rows joined with candidate-generation diagnostics."""

    candidate_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
    if candidate_ids.size == 0:
        return []
    mask = np.ones(candidate_ids.shape, dtype=np.bool_)
    rollout_ids = np.asarray(reader.array("candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    if rollout_row_id is not None:
        mask &= rollout_ids == int(rollout_row_id)
    if step_row_id is not None:
        mask &= step_ids == int(step_row_id)
    row_positions = np.flatnonzero(mask)
    if limit is not None:
        row_positions = row_positions[: max(0, int(limit))]

    dictionaries = _reader_dictionaries(reader)
    component_names = _component_names(reader)
    rollout_context = _rollout_context_by_id(reader, dictionaries=dictionaries)
    diagnostics = _candidate_diagnostics(reader, row_positions=row_positions)

    rows: list[dict[str, object]] = []
    for local, row in enumerate(row_positions.tolist()):
        candidate_row_id = int(candidate_ids[row])
        rollout_id = int(rollout_ids[row])
        primary_reason = int(reader.array("candidates/primary_invalid_reason")[row])
        position_id = int(diagnostics["position_id"][local])
        strategy_id = int(reader.array("candidates/strategy_id")[row])
        mixture_id = int(reader.array("candidates/mixture_id")[row])
        pose = np.asarray(reader.array("candidates/pose_world_cam")[row], dtype=np.float32).reshape(12)
        context = rollout_context.get(rollout_id, {})
        rows.append(
            {
                "candidate_row_id": candidate_row_id,
                "rollout_row_id": rollout_id,
                "step_row_id": int(step_ids[row]),
                "step_index": int(reader.array("candidates/step_index")[row]),
                "shell_index": int(reader.array("candidates/shell_index")[row]),
                "compact_valid_index": int(reader.array("candidates/compact_valid_index")[row]),
                "scene": context.get("scene", ""),
                "split": context.get("split", ""),
                "policy": context.get("policy", ""),
                "target_row_id": context.get("target_row_id", -1),
                "selected": bool(reader.array("candidates/selected_mask")[row]),
                "actor_action": bool(reader.array("candidates/actor_action_mask")[row]),
                "oracle_label": bool(reader.array("candidates/oracle_label_mask")[row]),
                "q_train": bool(reader.array("candidates/q_train_mask")[row]),
                "strategy_id": strategy_id,
                "strategy": decode_strategy_id(strategy_id),
                "position_id": position_id,
                "position": decode_position_id(position_id),
                "mixture_id": mixture_id,
                "mixture": component_names.get(mixture_id, "unknown" if mixture_id < 0 else f"component_{mixture_id}"),
                "sampler_probability": _finite_or_none(reader.array("candidates/sampler_probability")[row]),
                "invalid_reason": decode_invalid_reason(primary_reason),
                "invalid_reason_bitset": int(reader.array("candidates/invalid_reason_bitset")[row]),
                "target_rri": _finite_or_none(reader.array("candidates/target_rri")[row]),
                "target_root_gain": _finite_or_none(reader.array("candidates/target_root_gain")[row]),
                "target_log_error_gain": _finite_or_none(reader.array("candidates/target_log_error_gain")[row]),
                "target_pm_dist_before": _finite_or_none(reader.array("candidates/target_pm_dist_before")[row]),
                "target_pm_dist_after": _finite_or_none(reader.array("candidates/target_pm_dist_after")[row]),
                "scene_rri": _finite_or_none(reader.array("candidates/scene_rri")[row]),
                "selection_probability": _finite_or_none(reader.array("candidates/selection_probabilities")[row]),
                "center_x": float(pose[9]),
                "center_y": float(pose[10]),
                "center_z": float(pose[11]),
                "mesh_distance_m": _finite_or_none(diagnostics["mesh_distance_m"][local]),
                "path_min_clearance_m": _finite_or_none(diagnostics["path_min_clearance_m"][local]),
                "path_collision": bool(diagnostics["path_collision_mask"][local]),
                "free_space_margin_m": _finite_or_none(diagnostics["free_space_margin_m"][local]),
                "motion_step_length_m": _finite_or_none(diagnostics["motion_step_length_m"][local]),
                "motion_height_delta_m": _finite_or_none(diagnostics["motion_height_delta_m"][local]),
                "motion_backward_step_m": _finite_or_none(diagnostics["motion_backward_step_m"][local]),
                "motion_yaw_delta_deg": _finite_or_none(diagnostics["motion_yaw_delta_deg"][local]),
                "target_distance_m": _finite_or_none(diagnostics["target_distance_m"][local]),
                "target_bearing_yaw_deg": _finite_or_none(diagnostics["target_bearing_yaw_deg"][local]),
            }
        )
    return rows


def target_audit_rows(reader: RolloutZarrStoreReader) -> list[dict[str, object]]:
    """Return stored target rows with actor-visible and GT-audit fields."""

    if "targets" not in reader.root:
        return []
    target_rows = np.asarray(reader.array("targets/target_row_id"), dtype=np.int64).reshape(-1)
    dictionaries = _reader_dictionaries(reader)
    rows: list[dict[str, object]] = []
    for index, target_row_id in enumerate(target_rows.tolist()):
        primary_reason = int(_optional_array(reader, "targets/target_primary_invalid_reason", index, default=0))
        rows.append(
            {
                "target_row_id": int(target_row_id),
                "target_id": _dict_value(dictionaries.get("target", []), reader.array("targets/target_id")[index]),
                "source": _dict_value(
                    dictionaries.get("target_source", []),
                    reader.array("targets/target_source_id")[index],
                ),
                "source_index": int(reader.array("targets/target_source_index")[index]),
                "class": _dict_value(
                    dictionaries.get("class_name", []),
                    reader.array("targets/target_class_name_id")[index],
                ),
                "sem_id": int(reader.array("targets/target_sem_id")[index]),
                "inst_id": int(reader.array("targets/target_inst_id")[index]),
                "confidence": _finite_or_none(reader.array("targets/target_confidence")[index]),
                "selection_rank": int(reader.array("targets/target_selection_rank")[index]),
                "selection_score": _finite_or_none(reader.array("targets/target_selection_score")[index]),
                "selection_probability": _finite_or_none(reader.array("targets/target_selection_probability")[index]),
                "target_valid": bool(reader.array("targets/target_valid_mask")[index]),
                "target_invalid_reason": decode_target_invalid_reason(primary_reason),
                "gt_label_valid": bool(reader.array("targets/gt_label_valid_mask")[index]),
                "gt_match_status": _dict_value(
                    dictionaries.get("target_match_status", []),
                    reader.array("targets/gt_match_status_id")[index],
                ),
                "gt_match_iou": _finite_or_none(reader.array("targets/gt_match_iou")[index]),
                "gt_match_score": _finite_or_none(reader.array("targets/gt_match_score")[index]),
                "projected_area_pixels": _finite_or_none(
                    _optional_array(reader, "targets/target_projected_area_pixels", index)
                ),
                "projected_area_fraction": _finite_or_none(
                    _optional_array(reader, "targets/target_projected_area_fraction", index)
                ),
                "semidense_support": _finite_or_none(
                    _optional_array(reader, "targets/target_semidense_support_count", index)
                ),
                "evl_support": _finite_or_none(_optional_array(reader, "targets/target_evl_support_count", index)),
                "effective_support": _finite_or_none(
                    _optional_array(reader, "targets/target_effective_support_count", index)
                ),
                "visibility_score": _finite_or_none(_optional_array(reader, "targets/target_visibility_score", index)),
                "support_score": _finite_or_none(_optional_array(reader, "targets/target_support_score", index)),
                "deficit_score": _finite_or_none(_optional_array(reader, "targets/target_deficit_score", index)),
            }
        )
    return rows


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


def candidate_group_summary_rows(reader: RolloutZarrStoreReader, *, group_by: str) -> list[dict[str, object]]:
    """Summarize candidate validity and labels by a decoded categorical field."""

    rows = candidate_audit_rows(reader)
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


def rollout_step_objective_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
) -> list[dict[str, object]]:
    """Return per-step objective, branching, and selected-action audit rows."""

    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    if step_ids.size == 0:
        return []

    rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    step_indices = np.asarray(reader.array("steps/step_index"), dtype=np.int64).reshape(-1)
    selected_candidate_ids = np.asarray(reader.array("steps/selected_candidate_row_id"), dtype=np.int64).reshape(-1)
    num_candidates = np.asarray(reader.array("steps/num_candidates"), dtype=np.int64).reshape(-1)
    num_valid = np.asarray(reader.array("steps/num_valid_candidates"), dtype=np.int64).reshape(-1)
    cumulative_target_rri = np.asarray(reader.array("steps/cumulative_target_rri"), dtype=np.float64).reshape(-1)
    cumulative_scene_rri = np.asarray(reader.array("steps/cumulative_scene_rri"), dtype=np.float64).reshape(-1)
    cumulative_target_root_gain = np.asarray(
        reader.array("steps/cumulative_target_root_gain"),
        dtype=np.float64,
    ).reshape(-1)
    cumulative_scene_root_gain = np.asarray(reader.array("steps/cumulative_scene_root_gain"), dtype=np.float64).reshape(
        -1
    )

    dictionaries = _reader_dictionaries(reader)
    rollout_context = _rollout_context_by_id(reader, dictionaries=dictionaries)
    rollout_rows_by_id = _rollout_rows_by_id(reader)
    selected_candidates = _selected_candidate_context_by_id(reader)
    previous_target_by_rollout: dict[int, float | None] = {}

    ordered = sorted(
        range(step_ids.size),
        key=lambda index: (int(rollout_ids[index]), int(step_indices[index]), int(step_ids[index])),
    )
    rows: list[dict[str, object]] = []
    for index in ordered:
        current_rollout_id = int(rollout_ids[index])
        if rollout_row_id is not None and current_rollout_id != int(rollout_row_id):
            continue
        cumulative_target = _finite_or_none(cumulative_target_rri[index])
        previous_target = previous_target_by_rollout.get(current_rollout_id)
        marginal_target = (
            None
            if cumulative_target is None
            else cumulative_target
            if previous_target is None
            else cumulative_target - previous_target
        )
        previous_target_by_rollout[current_rollout_id] = cumulative_target
        candidate_context = selected_candidates.get(int(selected_candidate_ids[index]), {})
        rollout_context_row = rollout_context.get(current_rollout_id, {})
        rollout_row = rollout_rows_by_id.get(current_rollout_id, {})
        invalid_fraction = None
        if int(num_candidates[index]) > 0:
            invalid_fraction = 1.0 - float(num_valid[index]) / float(num_candidates[index])
        rows.append(
            {
                "rollout_row_id": current_rollout_id,
                "step_row_id": int(step_ids[index]),
                "step_index": int(step_indices[index]),
                "chain_id": rollout_row.get("chain_id"),
                "scene": rollout_context_row.get("scene", ""),
                "split": rollout_context_row.get("split", ""),
                "policy": rollout_context_row.get("policy", ""),
                "target_row_id": rollout_context_row.get("target_row_id", -1),
                "horizon": rollout_row.get("horizon"),
                "branch_factor": rollout_row.get("branch_factor"),
                "beam_width": rollout_row.get("beam_width"),
                "temperature": rollout_row.get("temperature"),
                "cumulative_target_rri": cumulative_target,
                "marginal_target_rri": marginal_target,
                "cumulative_scene_rri": _finite_or_none(cumulative_scene_rri[index]),
                "cumulative_target_root_gain": _finite_or_none(cumulative_target_root_gain[index]),
                "cumulative_scene_root_gain": _finite_or_none(cumulative_scene_root_gain[index]),
                "num_candidates": int(num_candidates[index]),
                "num_valid_candidates": int(num_valid[index]),
                "invalid_fraction": invalid_fraction,
                "selected_candidate_row_id": int(selected_candidate_ids[index]),
                "selected_target_rri": candidate_context.get("target_rri"),
                "selected_target_root_gain": candidate_context.get("target_root_gain"),
                "selected_scene_rri": candidate_context.get("scene_rri"),
                "selected_probability": candidate_context.get("selection_probability"),
                "selected_entropy": _step_selection_entropy(reader, step_row_id=int(step_ids[index])),
                "selected_sampler_probability": candidate_context.get("sampler_probability"),
                "selected_strategy": candidate_context.get("strategy", ""),
                "selected_position": candidate_context.get("position", ""),
                "selected_mixture": candidate_context.get("mixture", ""),
                "selected_invalid_reason": candidate_context.get("invalid_reason", ""),
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

    step_rows = rollout_step_objective_rows(reader)
    groups: dict[tuple[object, ...], dict[str, float]] = {}
    for row in step_rows:
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
                "valid_fanout_sum": 0.0,
                "valid_fanout_count": 0.0,
                "invalid_fraction_sum": 0.0,
                "invalid_fraction_count": 0.0,
                "marginal_target_rri_sum": 0.0,
                "marginal_target_rri_count": 0.0,
                "selected_target_root_gain_sum": 0.0,
                "selected_target_root_gain_count": 0.0,
                "selected_probability_sum": 0.0,
                "selected_probability_count": 0.0,
                "selected_entropy_sum": 0.0,
                "selected_entropy_count": 0.0,
            },
        )
        summary["selected_steps"] += 1.0
        _accumulate_optional(summary, "valid_fanout", row.get("num_valid_candidates"))
        _accumulate_optional(summary, "invalid_fraction", row.get("invalid_fraction"))
        _accumulate_optional(summary, "marginal_target_rri", row.get("marginal_target_rri"))
        _accumulate_optional(summary, "selected_target_root_gain", row.get("selected_target_root_gain"))
        _accumulate_optional(summary, "selected_probability", row.get("selected_probability"))
        _accumulate_optional(summary, "selected_entropy", row.get("selected_entropy"))

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
        output.append(
            {
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
                "mean_valid_fanout": _mean_accumulator(summary, "valid_fanout"),
                "mean_invalid_fraction": _mean_accumulator(summary, "invalid_fraction"),
                "mean_marginal_target_rri": _mean_accumulator(summary, "marginal_target_rri"),
                "mean_selected_target_root_gain": _mean_accumulator(summary, "selected_target_root_gain"),
                "mean_selected_probability": _mean_accumulator(summary, "selected_probability"),
                "mean_selected_entropy": _mean_accumulator(summary, "selected_entropy"),
            }
        )
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

    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    if step_ids.size == 0:
        return []
    rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    step_indices = np.asarray(reader.array("steps/step_index"), dtype=np.int64).reshape(-1)
    selected_candidate_ids = np.asarray(reader.array("steps/selected_candidate_row_id"), dtype=np.int64).reshape(-1)
    selected_context = _selected_candidate_context_by_id(reader)

    mask = np.ones(step_ids.shape, dtype=np.bool_)
    if rollout_row_id is not None:
        mask &= rollout_ids == int(rollout_row_id)
    if step_row_id is not None:
        mask &= step_ids == int(step_row_id)
    row_positions = np.flatnonzero(mask)
    if limit is not None:
        row_positions = row_positions[: max(0, int(limit))]

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return [
            _selected_depth_unavailable_row(
                rollout_row_id=int(rollout_ids[index]),
                step_row_id=int(step_ids[index]),
                step_index=int(step_indices[index]),
                selected_candidate_row_id=int(selected_candidate_ids[index]),
                warning="selected_depth unavailable: store metadata has selected_depth_enabled=false.",
            )
            for index in row_positions.tolist()
        ]

    try:
        group = reader.root["selected_depth"]
        depth_step_ids = np.asarray(group["step_row_id"], dtype=np.int64).reshape(-1)
        depth_candidate_ids = np.asarray(group["candidate_row_id"], dtype=np.int64).reshape(-1)
    except KeyError as exc:
        return [
            _selected_depth_unavailable_row(
                rollout_row_id=int(rollout_ids[index]),
                step_row_id=int(step_ids[index]),
                step_index=int(step_indices[index]),
                selected_candidate_row_id=int(selected_candidate_ids[index]),
                warning=f"selected_depth unavailable: missing array {exc}.",
            )
            for index in row_positions.tolist()
        ]

    rows: list[dict[str, object]] = []
    for index in row_positions.tolist():
        selected_candidate_row_id = int(selected_candidate_ids[index])
        base = _selected_depth_base_row(
            rollout_row_id=int(rollout_ids[index]),
            step_row_id=int(step_ids[index]),
            step_index=int(step_indices[index]),
            selected_candidate_row_id=selected_candidate_row_id,
        )
        matches = np.flatnonzero(depth_step_ids == int(step_ids[index]))
        if matches.size != 1:
            rows.append(
                {
                    **base,
                    "available": False,
                    "warning": (
                        f"selected_depth unavailable: expected one row for step_row_id={int(step_ids[index])}, "
                        f"found {matches.size}."
                    ),
                }
            )
            continue
        depth_row = int(matches[0])
        candidate_row_id = int(depth_candidate_ids[depth_row])
        if candidate_row_id != selected_candidate_row_id:
            rows.append(
                {
                    **base,
                    "candidate_row_id": candidate_row_id,
                    "available": False,
                    "warning": (
                        "selected_depth candidate mismatch: "
                        f"depth candidate_row_id={candidate_row_id}, "
                        f"step selected_candidate_row_id={selected_candidate_row_id}."
                    ),
                }
            )
            continue
        summary = _selected_depth_dense_summary(group, row_position=depth_row)
        candidate_context = selected_context.get(candidate_row_id, {})
        rows.append(
            {
                **base,
                **summary,
                "candidate_row_id": candidate_row_id,
                "available": summary.get("warning") in (None, ""),
                "selected_position": candidate_context.get("position", ""),
                "selected_strategy": candidate_context.get("strategy", ""),
                "selected_mixture": candidate_context.get("mixture", ""),
                "selected_target_root_gain": candidate_context.get("target_root_gain"),
                "selected_target_rri": candidate_context.get("target_rri"),
            }
        )
    return rows


def selected_depth_preview(
    reader: RolloutZarrStoreReader,
    *,
    step_row_id: int,
    max_size: int = 96,
) -> dict[str, object]:
    """Return one downsampled selected-depth payload for Plotly app previews."""

    max_side = max(1, int(max_size))
    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    selected_candidate_ids = np.asarray(reader.array("steps/selected_candidate_row_id"), dtype=np.int64).reshape(-1)
    step_matches = np.flatnonzero(step_ids == int(step_row_id))
    if step_matches.size != 1:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": None,
            "warning": f"selected_depth preview unavailable: expected one step row, found {step_matches.size}.",
        }
    selected_candidate_row_id = int(selected_candidate_ids[int(step_matches[0])])
    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": selected_candidate_row_id,
            "warning": "selected_depth unavailable: store metadata has selected_depth_enabled=false.",
        }
    try:
        group = reader.root["selected_depth"]
        depth_step_ids = np.asarray(group["step_row_id"], dtype=np.int64).reshape(-1)
        candidate_ids = np.asarray(group["candidate_row_id"], dtype=np.int64).reshape(-1)
    except KeyError as exc:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": selected_candidate_row_id,
            "warning": f"selected_depth unavailable: missing array {exc}.",
        }
    matches = np.flatnonzero(depth_step_ids == int(step_row_id))
    if matches.size != 1:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": selected_candidate_row_id,
            "warning": f"selected_depth unavailable: expected one row for step_row_id={step_row_id}, found {matches.size}.",
        }
    row = int(matches[0])
    candidate_row_id = int(candidate_ids[row])
    if candidate_row_id != selected_candidate_row_id:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": candidate_row_id,
            "warning": (
                "selected_depth candidate mismatch: "
                f"depth candidate_row_id={candidate_row_id}, "
                f"step selected_candidate_row_id={selected_candidate_row_id}."
            ),
        }
    try:
        depth = np.asarray(group["depth_m"][row], dtype=np.float32)
        valid_mask = np.asarray(group["valid_mask"][row], dtype=np.bool_)
        image_size = np.asarray(group["image_size_hw"][row], dtype=np.int32).reshape(-1)
        focal = np.asarray(group["focal_px"][row], dtype=np.float32).reshape(-1)
        principal = np.asarray(group["principal_point_px"][row], dtype=np.float32).reshape(-1)
    except KeyError as exc:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": candidate_row_id,
            "warning": f"selected_depth unavailable: missing dense array {exc}.",
        }
    if depth.ndim != 2 or valid_mask.shape != depth.shape:
        return {
            "available": False,
            "step_row_id": int(step_row_id),
            "candidate_row_id": candidate_row_id,
            "warning": f"selected_depth shape mismatch: depth_m={tuple(depth.shape)} valid_mask={tuple(valid_mask.shape)}.",
        }
    stride = max(1, int(np.ceil(max(depth.shape) / float(max_side))))
    depth_preview = depth[::stride, ::stride].astype(np.float32, copy=True)
    valid_preview = valid_mask[::stride, ::stride].astype(np.bool_, copy=True)
    depth_preview[~(valid_preview & np.isfinite(depth_preview))] = np.nan
    return {
        "available": True,
        "step_row_id": int(step_row_id),
        "candidate_row_id": candidate_row_id,
        "depth_m": depth_preview,
        "valid_mask": valid_preview,
        "image_size_hw": (int(image_size[0]), int(image_size[1])) if image_size.shape[0] == 2 else tuple(depth.shape),
        "focal_px": tuple(float(value) for value in focal.tolist()) if focal.shape[0] == 2 else (),
        "principal_point_px": tuple(float(value) for value in principal.tolist()) if principal.shape[0] == 2 else (),
        "stride": stride,
        "warning": "",
    }


def _selected_depth_base_row(
    *,
    rollout_row_id: int,
    step_row_id: int,
    step_index: int,
    selected_candidate_row_id: int,
) -> dict[str, object]:
    return {
        "rollout_row_id": int(rollout_row_id),
        "step_row_id": int(step_row_id),
        "step_index": int(step_index),
        "selected_candidate_row_id": int(selected_candidate_row_id),
        "candidate_row_id": None,
        "available": False,
        "valid_pixels": None,
        "finite_pixels": None,
        "pixel_count": None,
        "valid_fraction": None,
        "finite_fraction": None,
        "depth_min_m": None,
        "depth_mean_m": None,
        "depth_max_m": None,
        "image_height": None,
        "image_width": None,
        "focal_x_px": None,
        "focal_y_px": None,
        "principal_x_px": None,
        "principal_y_px": None,
        "warning": "",
    }


def _selected_depth_unavailable_row(
    *,
    rollout_row_id: int,
    step_row_id: int,
    step_index: int,
    selected_candidate_row_id: int,
    warning: str,
) -> dict[str, object]:
    return {
        **_selected_depth_base_row(
            rollout_row_id=rollout_row_id,
            step_row_id=step_row_id,
            step_index=step_index,
            selected_candidate_row_id=selected_candidate_row_id,
        ),
        "warning": warning,
    }


def _selected_depth_dense_summary(group: zarr.Group, *, row_position: int) -> dict[str, object]:
    try:
        depth = np.asarray(group["depth_m"][row_position], dtype=np.float32)
        valid_mask = np.asarray(group["valid_mask"][row_position], dtype=np.bool_)
        focal = np.asarray(group["focal_px"][row_position], dtype=np.float32).reshape(-1)
        principal = np.asarray(group["principal_point_px"][row_position], dtype=np.float32).reshape(-1)
        image_size = np.asarray(group["image_size_hw"][row_position], dtype=np.int32).reshape(-1)
    except KeyError as exc:
        return {"warning": f"selected_depth unavailable: missing dense array {exc}."}
    if depth.ndim != 2 or valid_mask.shape != depth.shape:
        return {
            "warning": f"selected_depth shape mismatch: depth_m={tuple(depth.shape)} "
            f"valid_mask={tuple(valid_mask.shape)}."
        }
    if focal.shape[0] != 2 or principal.shape[0] != 2 or image_size.shape[0] != 2:
        return {"warning": "selected_depth camera metadata must have two values per row."}
    height, width = int(image_size[0]), int(image_size[1])
    if (height, width) != tuple(depth.shape):
        return {
            "warning": f"selected_depth image_size_hw={(height, width)} does not match depth shape {tuple(depth.shape)}."
        }

    finite_valid = valid_mask & np.isfinite(depth)
    valid_depth = depth[finite_valid]
    pixel_count = int(depth.size)
    valid_pixels = int(valid_mask.sum())
    finite_pixels = int(finite_valid.sum())
    return {
        "valid_pixels": valid_pixels,
        "finite_pixels": finite_pixels,
        "pixel_count": pixel_count,
        "valid_fraction": _safe_fraction(valid_pixels, pixel_count),
        "finite_fraction": _safe_fraction(finite_pixels, pixel_count),
        "depth_min_m": None if valid_depth.size == 0 else float(np.min(valid_depth)),
        "depth_mean_m": None if valid_depth.size == 0 else float(np.mean(valid_depth)),
        "depth_max_m": None if valid_depth.size == 0 else float(np.max(valid_depth)),
        "image_height": height,
        "image_width": width,
        "focal_x_px": float(focal[0]),
        "focal_y_px": float(focal[1]),
        "principal_x_px": float(principal[0]),
        "principal_y_px": float(principal[1]),
        "warning": "",
    }


def _accumulate_optional(summary: dict[str, float], key: str, value: object) -> None:
    value_float = _finite_or_none(value)
    if value_float is None:
        return
    summary[f"{key}_sum"] += float(value_float)
    summary[f"{key}_count"] += 1.0


def _mean_accumulator(summary: dict[str, float], key: str) -> float | None:
    count = summary[f"{key}_count"]
    if count <= 0:
        return None
    return float(summary[f"{key}_sum"] / count)


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
    rows.extend(_low_fanout_rows(reader, cfg))
    rows.extend(_dominant_invalid_reason_rows(reader, cfg))
    rows.extend(_missing_label_rows(reader))
    rows.extend(_high_score_invalid_target_rows(reader, cfg))
    rows.extend(_selected_motion_outlier_rows(reader, cfg))
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
    selected = np.asarray(reader.array("candidates/selected_mask"), dtype=np.bool_).reshape(-1)
    if not selected.any():
        return []
    candidate_ids = np.asarray(reader.array("candidates/candidate_row_id"), dtype=np.int64).reshape(-1)
    rollout_ids = np.asarray(reader.array("candidates/rollout_row_id"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    diag = _candidate_diagnostics(reader, row_positions=np.arange(candidate_ids.shape[0], dtype=np.int64))
    checks = (
        ("motion_step_length_m", cfg.max_step_distance_m, ">"),
        ("motion_height_delta_m", cfg.max_height_delta_m, "abs>"),
        ("motion_backward_step_m", cfg.max_backward_step_m, ">"),
        ("motion_yaw_delta_deg", cfg.max_yaw_delta_deg, "abs>"),
    )
    output: list[dict[str, object]] = []
    for index in np.flatnonzero(selected).tolist():
        messages: list[str] = []
        for name, threshold, op in checks:
            value = float(diag[name][index])
            if not np.isfinite(value):
                continue
            compare = abs(value) if op == "abs>" else value
            if compare > float(threshold):
                messages.append(f"{name}={value:.3f} exceeds {threshold:.3f}")
        if messages:
            output.append(
                {
                    "kind": "selected_motion_outlier",
                    "severity": "warning",
                    "rollout_row_id": int(rollout_ids[index]),
                    "step_row_id": int(step_ids[index]),
                    "candidate_row_id": int(candidate_ids[index]),
                    "message": "; ".join(messages),
                }
            )
    return output


def _rollout_store_inventory_row(store_path: Path) -> dict[str, object]:
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
    names = [_dict_value(values, int(value)) or str(int(value)) for value in np.unique(ids).tolist()]
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


def _candidate_diagnostics(reader: RolloutZarrStoreReader, *, row_positions: np.ndarray) -> dict[str, np.ndarray]:
    length = int(row_positions.shape[0])
    defaults: dict[str, tuple[Any, Any]] = {
        "position_id": (np.int32, -1),
        "mesh_distance_m": (np.float32, np.nan),
        "path_min_clearance_m": (np.float32, np.nan),
        "path_collision_mask": (np.bool_, False),
        "free_space_margin_m": (np.float32, np.nan),
        "motion_step_length_m": (np.float32, np.nan),
        "motion_height_delta_m": (np.float32, np.nan),
        "motion_backward_step_m": (np.float32, np.nan),
        "motion_yaw_delta_deg": (np.float32, np.nan),
        "target_distance_m": (np.float32, np.nan),
        "target_bearing_yaw_deg": (np.float32, np.nan),
    }
    output: dict[str, np.ndarray] = {}
    for name, (dtype, default) in defaults.items():
        path = f"candidate_diagnostics/{name}"
        try:
            values = np.asarray(reader.array(path), dtype=dtype).reshape(-1)
            output[name] = values[row_positions]
        except Exception:
            output[name] = np.full((length,), default, dtype=dtype)
    return output


def _rollout_context_by_id(
    reader: RolloutZarrStoreReader,
    *,
    dictionaries: dict[str, list[str]],
) -> dict[int, dict[str, object]]:
    rollout_rows = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    output: dict[int, dict[str, object]] = {}
    source_rows = np.asarray(reader.array("sources/source_row_id"), dtype=np.int64).reshape(-1)
    source_split = np.asarray(reader.array("sources/split_id"), dtype=np.int64).reshape(-1)
    split_by_source = {
        int(source): _dict_value(dictionaries.get("split", []), split_id)
        for source, split_id in zip(source_rows.tolist(), source_split.tolist(), strict=False)
    }
    for index, rollout_row_id in enumerate(rollout_rows.tolist()):
        scene = _dict_value(dictionaries.get("scene", []), reader.array("rollouts/scene_id")[index])
        policy = _dict_value(dictionaries.get("policy", []), reader.array("rollouts/policy_id")[index])
        source_row = int(reader.array("rollouts/source_row_id")[index])
        output[int(rollout_row_id)] = {
            "scene": scene,
            "policy": policy,
            "split": split_by_source.get(source_row, ""),
            "target_row_id": int(reader.array("rollouts/target_row_id")[index]),
        }
    return output


def _rollout_rows_by_id(reader: RolloutZarrStoreReader) -> dict[int, dict[str, object]]:
    rollout_rows = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1)
    output: dict[int, dict[str, object]] = {}
    for index, rollout_row_id in enumerate(rollout_rows.tolist()):
        output[int(rollout_row_id)] = {
            "chain_id": int(reader.array("rollouts/chain_id")[index]),
            "horizon": int(reader.array("rollouts/horizon")[index]),
            "branch_factor": int(reader.array("rollouts/branch_factor")[index]),
            "beam_width": int(reader.array("rollouts/beam_width")[index]),
            "temperature": _finite_or_none(reader.array("rollouts/temperature")[index]),
        }
    return output


def _selected_candidate_context_by_id(reader: RolloutZarrStoreReader) -> dict[int, dict[str, object]]:
    rows = candidate_audit_rows(reader)
    return {
        int(row["candidate_row_id"]): {
            "target_rri": row.get("target_rri"),
            "target_root_gain": row.get("target_root_gain"),
            "scene_rri": row.get("scene_rri"),
            "selection_probability": row.get("selection_probability"),
            "sampler_probability": row.get("sampler_probability"),
            "strategy": row.get("strategy", ""),
            "position": row.get("position", ""),
            "mixture": row.get("mixture", ""),
            "invalid_reason": row.get("invalid_reason", ""),
        }
        for row in rows
        if bool(row.get("selected"))
    }


def _step_selection_entropy(reader: RolloutZarrStoreReader, *, step_row_id: int) -> float | None:
    step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    actor_valid = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    probabilities = np.asarray(reader.array("candidates/selection_probabilities"), dtype=np.float64).reshape(-1)
    mask = (step_ids == int(step_row_id)) & actor_valid & np.isfinite(probabilities) & (probabilities > 0.0)
    values = probabilities[mask]
    if values.size == 0:
        return None
    total = float(values.sum())
    if not np.isfinite(total) or total <= 0.0:
        return None
    normalized = values / total
    return float(-(normalized * np.log(normalized)).sum())


def _component_names(reader: RolloutZarrStoreReader) -> dict[int, str]:
    try:
        writer_config = reader.manifest().get("manifest", {}).get("generation", {}).get("writer_config")
    except Exception:
        writer_config = None
    components = []
    if isinstance(writer_config, dict):
        candidate_mixture = writer_config.get("candidate_mixture")
        if isinstance(candidate_mixture, dict):
            components = candidate_mixture.get("components") or []
    names: dict[int, str] = {}
    if isinstance(components, list):
        for index, component in enumerate(components):
            if isinstance(component, dict):
                value = component.get("name") or component.get("family") or component.get("position_mode")
                if value is not None:
                    names[int(index)] = str(value)
    return names


def _reader_dictionaries(reader: RolloutZarrStoreReader) -> dict[str, list[str]]:
    dictionaries: dict[str, list[str]] = {}
    try:
        group = reader.root["dictionaries"]
    except Exception:
        return dictionaries
    for name in group.array_keys():
        try:
            dictionaries[str(name)] = json.loads(np.asarray(group[name], dtype=np.uint8).tobytes().decode("utf-8"))
        except Exception:
            dictionaries[str(name)] = []
    return dictionaries


def _dict_value(values: list[str], index: object) -> str:
    idx = int(index)
    if idx < 0 or idx >= len(values):
        return ""
    return values[idx]


def _optional_array(
    reader: RolloutZarrStoreReader,
    path: str,
    index: int,
    *,
    default: float | int = np.nan,
) -> float | int:
    try:
        values = np.asarray(reader.array(path)).reshape(-1)
    except Exception:
        return default
    if index < 0 or index >= values.shape[0]:
        return default
    return values[index].item()


def _finite_or_none(value: object) -> float | None:
    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return None
    return value_float if np.isfinite(value_float) else None


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


__all__ = [
    "RolloutSuspiciousQueryConfig",
    "candidate_audit_rows",
    "candidate_group_summary_rows",
    "candidate_result_diagnostic_counts",
    "decode_invalid_reason",
    "decode_position_id",
    "decode_strategy_id",
    "decode_target_invalid_reason",
    "discover_rollout_store_paths",
    "rollout_store_inventory_rows",
    "rollout_step_objective_rows",
    "suspicious_rollout_rows",
    "target_audit_rows",
    "validity_waterfall_rows",
]
