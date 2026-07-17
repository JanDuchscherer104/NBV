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
from .trace import _candidate_invalid_reasons
from .zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION, RolloutZarrStoreReader, _required_groups

_TARGET_INVALID_REASON_NAMES = {int(code): name for name, code in TARGET_INVALID_REASON_CODES.items()}
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
    rows: list[dict[str, object]] = []
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        for step in rollout_steps(reader, rollout):
            if step_row_id is not None and step.step_row_id != int(step_row_id):
                continue
            for local, row in enumerate(step.candidate_row_positions.tolist()):
                if limit is not None and len(rows) >= max(0, int(limit)):
                    return rows
                strategy_id = int(reader.array("candidates/strategy_id")[row])
                pose = step.pose_world_cam[local]
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
                        "policy": rollout.policy,
                        "target_row_id": rollout.target_row_id,
                        "selected": bool(step.selected_mask[local]),
                        "actor_action": bool(step.actor_action_mask[local]),
                        "oracle_label": bool(reader.array("candidates/oracle_label_mask")[row]),
                        "q_train": bool(reader.array("candidates/q_train_mask")[row]),
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
                        "target_log_error_gain": _finite_or_none(reader.array("candidates/target_log_error_gain")[row]),
                        "target_pm_dist_before": _finite_or_none(reader.array("candidates/target_pm_dist_before")[row]),
                        "target_pm_dist_after": _finite_or_none(reader.array("candidates/target_pm_dist_after")[row]),
                        "scene_rri": _finite_or_none(step.scene_rri[local]),
                        "selection_probability": _finite_or_none(step.selection_probabilities[local]),
                        "center_x": float(pose[9]),
                        "center_y": float(pose[10]),
                        "center_z": float(pose[11]),
                        "mesh_distance_m": _finite_or_none(step.mesh_distance_m[local]),
                        "path_min_clearance_m": _finite_or_none(step.path_min_clearance_m[local]),
                        "path_collision": bool(reader.array("candidate_diagnostics/path_collision_mask")[row]),
                        "free_space_margin_m": _finite_or_none(
                            reader.array("candidate_diagnostics/free_space_margin_m")[row]
                        ),
                        "motion_step_length_m": _finite_or_none(step.motion_step_length_m[local]),
                        "motion_height_delta_m": _finite_or_none(
                            reader.array("candidate_diagnostics/motion_height_delta_m")[row]
                        ),
                        "motion_backward_step_m": _finite_or_none(
                            reader.array("candidate_diagnostics/motion_backward_step_m")[row]
                        ),
                        "motion_yaw_delta_deg": _finite_or_none(
                            reader.array("candidate_diagnostics/motion_yaw_delta_deg")[row]
                        ),
                        "target_distance_m": _finite_or_none(step.target_distance_m[local]),
                        "target_bearing_yaw_deg": _finite_or_none(
                            reader.array("candidate_diagnostics/target_bearing_yaw_deg")[row]
                        ),
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
