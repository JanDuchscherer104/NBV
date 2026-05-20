"""Read-only inspection helpers for rollout Zarr stores.

This module keeps Streamlit, CLI, and tests away from ad hoc Zarr joins. The
helpers return plain dictionaries and NumPy-backed scalar values so UI code can
choose its own rendering library without owning rollout-store semantics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..data_handling import TARGET_INVALID_REASON_CODES
from ..pose_generation import CandidatePositionMode, ViewDirectionMode, candidate_position_id, candidate_strategy_id
from .trace import INVALID_REASON_CODES, _candidate_invalid_reasons
from .zarr_store import RolloutZarrStoreReader

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
    "suspicious_rollout_rows",
    "target_audit_rows",
    "validity_waterfall_rows",
]
