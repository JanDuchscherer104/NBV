"""Read-only inspection helpers for rollout Zarr stores.

This module keeps Streamlit, CLI, and tests away from ad hoc Zarr joins. The
helpers return plain dictionaries and NumPy-backed scalar values so UI code can
choose its own rendering library without owning rollout-store semantics.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import pickle
import tempfile
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import torch
import zarr
from numpy.typing import NDArray

from ..oracle.pipelines.shard_promotion import read_promotion_marker_json
from ..oracle.target_selection import TARGET_INVALID_REASON_CODES
from ..pose_generation import ViewDirectionMode, candidate_strategy_id
from ..targets.protocol import ORACLE_GT_TARGET_SOURCE, ActorVisibleTargetSource, TargetInputProtocol
from .audits import candidate_policy_entropy
from .manifest import read_rollout_store_manifest
from .read_model import (
    StoredRollout,
    decode_invalid_reason,
    decode_position_id,
    rollout_at,
    rollout_rows,
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
CandidateSelectionGroupField = Literal["position", "strategy", "mixture", "position_strategy"]
CANDIDATE_SELECTION_GROUP_FIELDS: tuple[CandidateSelectionGroupField, ...] = (
    "position",
    "strategy",
    "mixture",
    "position_strategy",
)


@dataclass(frozen=True)
class PairwiseCorrelationResult:
    """Pair-local finite Pearson evidence for one set of named components."""

    columns: tuple[str, ...]
    correlation: np.ndarray
    counts: np.ndarray
    reasons: dict[tuple[str, str], str]
    has_finite_off_diagonal: bool


def pairwise_finite_pearson(values: Mapping[str, Iterable[Any]], columns: Collection[str]) -> PairwiseCorrelationResult:
    """Compute finite paired Pearson correlations without pooling missing rows.

    Each pair has its own finite-row denominator.  Fewer than two paired rows,
    constant values, and non-finite results remain unavailable with an explicit
    reason; in particular, ``n=2`` is retained as degenerate evidence rather
    than silently presented as a substantive correlation.
    """

    names = tuple(columns)
    numeric = {name: np.asarray(list(values[name]), dtype=float) for name in names}
    correlation = np.full((len(names), len(names)), np.nan, dtype=float)
    counts = np.zeros((len(names), len(names)), dtype=np.int64)
    reasons: dict[tuple[str, str], str] = {}
    has_finite_off_diagonal = False
    for left_index, left in enumerate(names):
        for right_index, right in enumerate(names):
            length = min(numeric[left].size, numeric[right].size)
            paired = np.column_stack((numeric[left][:length], numeric[right][:length]))
            finite_values = paired[np.isfinite(paired).all(axis=1)]
            n = int(len(finite_values))
            counts[left_index, right_index] = n
            if n < 2:
                reasons[(left, right)] = f"insufficient finite paired rows (n={n}; need n>=2)"
                continue
            left_values, right_values = finite_values[:, 0], finite_values[:, 1]
            if np.unique(left_values).size == 1 or np.unique(right_values).size == 1:
                reasons[(left, right)] = "constant pair value (zero variance)"
                continue
            value = float(np.corrcoef(left_values, right_values)[0, 1])
            if not np.isfinite(value):
                reasons[(left, right)] = "non-finite Pearson correlation after finite pair filtering"
                continue
            correlation[left_index, right_index] = value
            if left != right:
                has_finite_off_diagonal = True
                if n == 2:
                    reasons[(left, right)] = "n=2 is algebraically degenerate: |r|=1 is not substantive evidence"
    return PairwiseCorrelationResult(names, correlation, counts, reasons, has_finite_off_diagonal)


_CANDIDATE_SELECTION_TEMPORAL_METRICS = (
    "allocation_share",
    "valid_share",
    "policy_mass",
    "selected_share",
)
_SAMPLER_PROBABILITY_TOLERANCE = 1e-5
_GEOMETRY_EPSILON = 1e-9

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
class ManifestFacts:
    """The single manifest snapshot shared by one inspection demand."""

    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SchemaValidation:
    """Immutable schema-validation result with ordered errors."""

    ok: bool
    num_rollouts: int
    num_steps: int
    num_candidates: int
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    """Optional promotion error for a validated rollout store."""

    error: str | None


@dataclass(frozen=True, slots=True)
class EffectiveTrust:
    """Streamlit trust composition, preserving schema then promotion errors."""

    ok: bool
    num_rollouts: int
    num_steps: int
    num_candidates: int
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompactStatistics:
    """Compact statistics demanded by CLI stats and report consumers."""

    payload: dict[str, Any]


def build_manifest_facts(
    reader: RolloutZarrStoreReader, *, manifest_payload: dict[str, Any] | None = None
) -> ManifestFacts:
    """Read or reuse exactly one manifest snapshot."""

    return ManifestFacts(reader.manifest() if manifest_payload is None else manifest_payload)


def build_schema_validation(reader: RolloutZarrStoreReader) -> SchemaValidation:
    """Validate one store without exposing the reader's mutable result."""

    result = reader.validate()
    return SchemaValidation(
        ok=bool(result.ok),
        num_rollouts=int(result.num_rollouts),
        num_steps=int(result.num_steps),
        num_candidates=int(result.num_candidates),
        errors=tuple(str(error) for error in result.errors),
    )


def build_promotion_evidence(
    reader: RolloutZarrStoreReader,
    *,
    manifest_payload: dict[str, Any] | None = None,
    evaluator: Callable[..., str | None] | None = None,
) -> PromotionEvidence:
    """Evaluate promotion evidence only for consumers that demand it."""

    check = promoted_store_validation_error if evaluator is None else evaluator
    return PromotionEvidence(check(reader, manifest_payload=manifest_payload))


def build_effective_streamlit_trust(schema: SchemaValidation, promotion: PromotionEvidence) -> EffectiveTrust:
    """Compose independent trust facets without mutating either input."""

    errors = list(schema.errors)
    if promotion.error is not None:
        errors.append(promotion.error)
    return EffectiveTrust(
        ok=schema.ok and promotion.error is None,
        num_rollouts=schema.num_rollouts,
        num_steps=schema.num_steps,
        num_candidates=schema.num_candidates,
        errors=tuple(errors),
    )


def build_compact_statistics(
    reader: RolloutZarrStoreReader, *, manifest_payload: dict[str, Any] | None = None
) -> CompactStatistics:
    """Compute compact statistics, reusing a supplied manifest snapshot."""

    return CompactStatistics(rollout_statistics(reader, manifest_payload=manifest_payload))


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
    stores = {path.expanduser().resolve() for path in root.glob(pattern) if path.is_dir()}
    campaign_markers = ("zarr.json", "manifest.json", "_SUCCESS.json", "_owner.json")
    stores.update(
        marker.parent.resolve()
        for marker in root.glob("**/_SUCCESS.json")
        if all((marker.parent / name).is_file() for name in campaign_markers)
    )
    return sorted(stores, key=lambda path: (_path_mtime(path), path.as_posix()), reverse=True)


def rollout_store_inventory_rows(
    store_paths: Iterable[Path],
    *,
    validate: bool = True,
) -> list[dict[str, Any]]:
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
) -> dict[str, Any]:
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
        reference_scenes is not None
        and source_scenes is not None
        and 0 < reference_scenes
        and 0 <= source_scenes <= reference_scenes
    )
    row_coverage_valid = (
        reference_rows is not None
        and source_rows is not None
        and 0 < reference_rows
        and 0 <= source_rows <= reference_rows
    )
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
            "manifest provenance declares a nonpositive reference denominator"
            if reference_scenes == 0 or reference_rows == 0
            else "manifest provenance declares observed coverage above its reference denominator"
            if (reference_scenes is not None and source_scenes is not None and source_scenes > reference_scenes)
            or (reference_rows is not None and source_rows is not None and source_rows > reference_rows)
            else None
            if reference_scenes is not None or reference_rows is not None
            else "manifest provenance does not declare a reference denominator"
        ),
        "logical_source_rows": dict(sorted(coverage.get("source_shard_counts", {}).items()))
        if isinstance(coverage.get("source_shard_counts"), dict)
        else {},
        "physical_store_bytes": _nonnegative_int(storage["total_bytes"]) or 0,
        "physical_bytes_per_rollout": _ratio(_nonnegative_int(storage["total_bytes"]), rollouts),
        "physical_bytes_per_candidate": _ratio(_nonnegative_int(storage["total_bytes"]), candidates),
        "physical_bytes_per_candidate_reason": storage["bytes_per_candidate_reason"],
        "return_semantics": root_attrs.get("return_semantics"),
        "discount_gamma": _finite_or_none(root_attrs.get("discount_gamma")),
    }


def runtime_storage_statistics(store_dir: Path, *, candidate_count: int) -> dict[str, float | int | str | None]:
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
    denominator = int(candidate_count)
    bytes_per_candidate = float(total_bytes) / float(denominator) if denominator > 0 else None
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "bytes_per_candidate": bytes_per_candidate,
        "bytes_per_candidate_reason": None if denominator > 0 else "unavailable: no persisted candidate rows",
        "file_count_limit": max(2000, denominator * 20),
        "bytes_per_candidate_limit": 2_000_000.0,
    }


def promoted_store_validation_error(
    reader: RolloutZarrStoreReader,
    *,
    manifest_payload: Mapping[str, Any] | None = None,
) -> str | None:
    """Return an error when campaign completion evidence is not current."""

    store_dir = reader.store_dir
    success_status, _success = read_promotion_marker_json(store_dir / "_SUCCESS.json")
    owner_status, _owner = read_promotion_marker_json(store_dir / "_owner.json")
    marker_statuses = (success_status, owner_status)
    if marker_statuses == ("missing_file", "missing_file"):
        return None
    if marker_statuses != ("present", "present"):
        if "missing_file" in marker_statuses:
            return "promoted rollout evidence is incomplete"
        return "promoted rollout evidence markers are unreadable"
    payload = reader.manifest() if manifest_payload is None else manifest_payload
    manifest = payload.get("manifest")
    generation = manifest.get("generation") if isinstance(manifest, Mapping) else None
    shard_payload = generation.get("shard") if isinstance(generation, Mapping) else None
    if not isinstance(shard_payload, dict):
        return "promoted rollout manifest has no typed shard ownership"
    try:
        from ..oracle.pipelines.shards import read_validated_completed_shard
        from .shard_manifest import RolloutShardEntry

        shard_entry = RolloutShardEntry.from_jsonable(shard_payload)
        shard_entry.validate()
        evidence = read_validated_completed_shard(
            store_dir,
            shard_entry=shard_entry,
            writer_config_hash=shard_entry.writer_config_hash,
        )
    except (KeyError, TypeError, ValueError):
        return "promoted rollout evidence is malformed"
    return None if evidence is not None else "promoted rollout evidence does not match the canonical store content"


def _generation_cohort_identity(
    rollout: StoredRollout,
    *,
    candidate_config: str,
    rollout_config: str,
    branch_schedule: str,
) -> tuple[str, str]:
    """Return the canonical cohort identity shared by candidate and step views."""

    cohort_fields = {
        "policy": rollout.policy,
        "horizon": rollout.horizon,
        "acquisition_budget_steps": rollout.horizon,
        "branch_factor": rollout.branch_factor,
        "beam_width": rollout.beam_width,
        "temperature": _finite_or_none(rollout.temperature),
        "candidate_config": candidate_config,
        "rollout_config": rollout_config,
        "branch_schedule": branch_schedule,
    }
    cohort_json = json.dumps(cohort_fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(cohort_json.encode()).hexdigest()[:16], cohort_json


def candidate_audit_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_id: int | None = None,
    step_row_id: int | None = None,
    limit: int | None = None,
    row_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Return candidate rows, or stream them to ``row_callback`` without retention."""
    rows: list[dict[str, Any]] = []
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
    candidate_count = int(np.asarray(reader.array("candidates/candidate_row_id")).size)
    view_jitter_yaw_deg = _optional_candidate_diagnostic(
        reader, "view_jitter_yaw_deg", candidate_count=candidate_count, dtype=np.float32, fill=np.nan
    )
    view_jitter_pitch_deg = _optional_candidate_diagnostic(
        reader, "view_jitter_pitch_deg", candidate_count=candidate_count, dtype=np.float32, fill=np.nan
    )
    view_jitter_azimuth_limit_deg = _optional_candidate_diagnostic(
        reader, "view_jitter_azimuth_limit_deg", candidate_count=candidate_count, dtype=np.float32, fill=np.nan
    )
    view_jitter_elevation_limit_deg = _optional_candidate_diagnostic(
        reader, "view_jitter_elevation_limit_deg", candidate_count=candidate_count, dtype=np.float32, fill=np.nan
    )
    view_jitter_is_bounded = _optional_candidate_diagnostic(
        reader, "view_jitter_is_bounded", candidate_count=candidate_count, dtype=np.bool_, fill=False
    )
    target_view_angle_deg = _optional_candidate_diagnostic(
        reader, "target_view_angle_deg", candidate_count=candidate_count, dtype=np.float32, fill=np.nan
    )
    target_pixel_margin_px = _optional_candidate_diagnostic(
        reader, "target_pixel_margin_px", candidate_count=candidate_count, dtype=np.float32, fill=np.nan
    )
    target_in_fov_mask = _optional_candidate_diagnostic(
        reader, "target_in_fov_mask", candidate_count=candidate_count, dtype=np.bool_, fill=False
    )
    target_view_evaluated_mask = _optional_candidate_diagnostic(
        reader, "target_view_evaluated_mask", candidate_count=candidate_count, dtype=np.bool_, fill=False
    )
    candidate_configs = _decoded_array(reader, "lineage/candidate_config_id", "config")
    rollout_configs = _decoded_array(reader, "lineage/rollout_config_id", "config")
    branch_schedules = _decoded_array(reader, "lineage/branch_schedule_id", "config")
    protocol = str(reader.root.attrs.get("target_protocol_version", "")).replace("-", "_")
    target_records = {target.target_row_id: target for target in target_rows(reader)}
    target_centers = {
        target_row_id: np.asarray(target.center_world, dtype=np.float64).reshape(3)
        for target_row_id, target in target_records.items()
    }
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        generation_cohort_id, cohort_json = _generation_cohort_identity(
            rollout,
            candidate_config=candidate_configs[rollout_position],
            rollout_config=rollout_configs[rollout_position],
            branch_schedule=branch_schedules[rollout_position],
        )
        root_center = np.asarray(rollout.root_pose_world[9:12], dtype=np.float64)
        target_delta = target_centers.get(rollout.target_row_id)
        target_record = target_records.get(rollout.target_row_id)
        target_source = None if target_record is None else target_record.source
        target_valid = None if target_record is None else target_record.target_valid
        target_gt_label_valid = None if target_record is None else target_record.gt_label_valid
        target_match_status = None if target_record is None else target_record.gt_match_status
        target_evidence_role = (
            "oracle/evaluation"
            if protocol == TargetInputProtocol.V0_GT_INPUT.value or target_source == ORACLE_GT_TARGET_SOURCE
            else "actor-visible"
            if target_source in {source.value for source in ActorVisibleTargetSource}
            else "unclassified"
            if target_source
            else "unknown"
        )
        if target_delta is not None:
            target_delta = target_delta - root_center
        reference_pose = np.asarray(rollout.root_pose_world, dtype=np.float64).reshape(12)
        reference_available = True
        for step in rollout_steps(reader, rollout):
            emit_step = step_row_id is None or step.step_row_id == int(step_row_id)
            for local, row in enumerate(step.candidate_row_positions.tolist()):
                if not emit_step:
                    continue
                if limit is not None and emitted >= max(0, int(limit)):
                    return rows
                strategy_id = int(strategy_ids[row])
                pose = step.pose_world_cam[local]
                relative = np.asarray(pose[9:12], dtype=np.float64) - root_center
                proposal_relative = _decision_relative_vector(reference_pose, pose) if reference_available else None
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
                    "target_source": target_source,
                    "target_protocol": protocol,
                    "target_valid": target_valid,
                    "target_gt_label_valid": target_gt_label_valid,
                    "target_match_status": target_match_status,
                    "target_evidence_role": target_evidence_role,
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
                    "decision_relative_x_m": None if proposal_relative is None else float(proposal_relative[0]),
                    "decision_relative_y_m": None if proposal_relative is None else float(proposal_relative[1]),
                    "decision_relative_z_m": None if proposal_relative is None else float(proposal_relative[2]),
                    "decision_reference_available": reference_available,
                    "decision_reference_frame": (
                        "root pose world frame for step 0; previous selected camera frame thereafter"
                    ),
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
                    "view_jitter_yaw_deg": _finite_or_none(view_jitter_yaw_deg[row]),
                    "view_jitter_pitch_deg": _finite_or_none(view_jitter_pitch_deg[row]),
                    "view_jitter_azimuth_limit_deg": _finite_or_none(view_jitter_azimuth_limit_deg[row]),
                    "view_jitter_elevation_limit_deg": _finite_or_none(view_jitter_elevation_limit_deg[row]),
                    "view_jitter_is_bounded": (
                        bool(view_jitter_is_bounded[row])
                        if np.isfinite(view_jitter_yaw_deg[row]) and np.isfinite(view_jitter_pitch_deg[row])
                        else None
                    ),
                    "target_view_angle_deg": _finite_or_none(target_view_angle_deg[row]),
                    "target_pixel_margin_px": _finite_or_none(target_pixel_margin_px[row]),
                    "target_in_fov": (bool(target_in_fov_mask[row]) if bool(target_view_evaluated_mask[row]) else None),
                    "target_view_evaluated": bool(target_view_evaluated_mask[row]),
                    "root_to_target_x_m": None if target_delta is None else float(target_delta[0]),
                    "root_to_target_y_m": None if target_delta is None else float(target_delta[1]),
                    "root_to_target_z_m": None if target_delta is None else float(target_delta[2]),
                }
                if row_callback is not None:
                    row_callback(candidate_row)
                else:
                    rows.append(candidate_row)
                emitted += 1
            if step.selected_local_index >= 0:
                reference_pose = np.asarray(step.pose_world_cam[step.selected_local_index], dtype=np.float64).reshape(
                    12
                )
                reference_available = True
            else:
                reference_available = False
    return rows


def _optional_candidate_diagnostic(
    reader: RolloutZarrStoreReader,
    name: str,
    *,
    candidate_count: int,
    dtype: Any,
    fill: float | bool,
) -> np.ndarray:
    """Read one optional diagnostic or return an explicit unavailable vector."""

    group = reader.root["candidate_diagnostics"]
    if name in group:
        return np.asarray(group[name], dtype=dtype).reshape(-1)
    return np.full((candidate_count,), fill, dtype=dtype)


def _decision_relative_vector(reference_pose: np.ndarray, candidate_pose: np.ndarray) -> np.ndarray | None:
    """Return a candidate translation in the current decision reference frame."""

    reference = np.asarray(reference_pose, dtype=np.float64).reshape(-1)
    candidate = np.asarray(candidate_pose, dtype=np.float64).reshape(-1)
    if reference.size < 12 or candidate.size < 12:
        return None
    rotation = reference[:9].reshape(3, 3)
    center = reference[9:12]
    candidate_center = candidate[9:12]
    if not np.isfinite(rotation).all() or not np.isfinite(center).all() or not np.isfinite(candidate_center).all():
        return None
    relative = rotation.T @ (candidate_center - center)
    return relative if np.isfinite(relative).all() else None


def candidate_population_evidence(
    reader: RolloutZarrStoreReader,
    *,
    group_by: CandidateGroupField | None = None,
    sample_size: int = 500,
    scientific_support: bool = True,
    audit_reader: Callable[..., Any] = candidate_audit_rows,
) -> dict[str, Any]:
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
    # Scientific reducers replay a bounded spooled stream instead of retaining
    # a second in-memory copy of every candidate row.  The spool stays in RAM
    # for small stores and transparently moves to a temporary file for large
    # stores; the display sample remains the only retained candidate subset.
    spooled_rows = tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024, mode="w+b") if scientific_support else None

    def consume(row: Mapping[str, Any]) -> None:
        accumulator.consume(row)
        if spooled_rows is not None:
            pickle.dump(dict(row), spooled_rows, protocol=pickle.HIGHEST_PROTOCOL)

    signature = inspect.signature(audit_reader)
    callback_parameter = signature.parameters.get("row_callback")
    accepts_callback = callback_parameter is not None and callback_parameter.kind not in {
        inspect.Parameter.POSITIONAL_ONLY,
    }
    accepts_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
    if accepts_callback or accepts_kwargs:
        # Signature inspection decides the protocol before invocation.  A
        # TypeError raised inside a callback is therefore an actual producer
        # failure and cannot trigger a second, duplicate read.
        audit_reader(reader, row_callback=consume)
    else:
        for row in audit_reader(reader):
            consume(row)
    if spooled_rows is not None:
        spooled_rows.seek(0)

    def replay_rows() -> Iterable[dict[str, Any]]:
        if spooled_rows is None:
            return
        spooled_rows.seek(0)
        while True:
            try:
                yield pickle.load(spooled_rows)
            except EOFError:
                return

    try:
        sample = accumulator.sample()
        compositions = accumulator.compositions()
        calibrations = accumulator.calibrations()
        groups = accumulator.groups()
        collision = accumulator.collision()
        selection_dynamics = accumulator.selection_dynamics()
        selection_transitions = {
            selection_group: (
                candidate_selection_transition_rows(selection_dynamics[selection_group])
                if _selection_rows_have_factual_identity(selection_dynamics[selection_group])
                else []
            )
            for selection_group in CANDIDATE_SELECTION_GROUP_FIELDS
        }
        selection_sequences = {
            selection_group: (
                candidate_selection_sequence_rows(selection_dynamics[selection_group])
                if _selection_rows_have_factual_identity(selection_dynamics[selection_group])
                else []
            )
            for selection_group in CANDIDATE_SELECTION_GROUP_FIELDS
        }
        sample_rows = list(sample["rows"])
        target_roles = accumulator.target_evidence_roles()
        observed_roles = {
            str(row.get("target_evidence_role")) for row in target_roles if int(row.get("candidate_count", 0)) > 0
        }
        target_role = (
            next(iter(observed_roles))
            if len(observed_roles) == 1 and next(iter(observed_roles)) in {"actor-visible", "oracle/evaluation"}
            else "provenance"
        )
        if scientific_support:
            direction, spatial, target_view, motion = _candidate_scientific_macro_evidence(replay_rows())
        else:
            direction = {"density_rows": [], "cap_rows": [], "angular_support_rows": []}
            spatial = []
            target_view = []
            motion = []
        return {
            "composition": compositions,
            "calibration": calibrations,
            "collision": collision,
            "groups": groups,
            "target_evidence_roles": target_roles,
            "evidence_roles": {
                "direction": "actor-visible",
                "spatial": "actor-visible",
                "motion": "actor-visible",
                "collision": "oracle/evaluation",
                "clearance": "oracle/evaluation",
                "target_view": target_role,
                "geometry": target_role,
                "selection": "actor-visible",
                "sequence_return": "oracle/evaluation",
            },
            "selection_dynamics": selection_dynamics,
            "selection_transitions": selection_transitions,
            "selection_sequences": selection_sequences,
            "sequence_returns": {
                selection_group: candidate_sequence_return_summary_rows(selection_sequences[selection_group])
                for selection_group in CANDIDATE_SELECTION_GROUP_FIELDS
            },
            "sample": sample,
            "population_count": accumulator.population_count,
            "geometry": candidate_geometry_evidence_rows(sample_rows),
            "direction": direction,
            "spatial": spatial,
            "target_view": target_view,
            "motion": motion,
        }
    finally:
        if spooled_rows is not None:
            spooled_rows.close()


def candidate_geometry_evidence_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Attach a target-normalized, root-centred 2-D frame to audit rows.

    The frame is deliberately local: the root is ``(0, 0)`` and the observed
    target is ``(1, 0)``.  A positive lateral coordinate is the right-handed
    perpendicular to the root-to-target direction.  Degenerate or absent
    target baselines remain unavailable rather than being fabricated.
    """

    output: list[dict[str, Any]] = []
    frame = "root=(0,0), target=(1,0), right-handed lateral axis"
    for raw in rows:
        row = dict(raw)
        x = _finite_or_none(row.get("root_relative_x_m"))
        y = _finite_or_none(row.get("root_relative_y_m"))
        tx = _finite_or_none(row.get("root_to_target_x_m"))
        ty = _finite_or_none(row.get("root_to_target_y_m"))
        if tx is None or ty is None or x is None or y is None:
            forward = lateral = None
        else:
            norm = float(np.hypot(tx, ty))
            if norm <= _GEOMETRY_EPSILON:
                forward = lateral = None
            else:
                forward = float((x * tx + y * ty) / (norm * norm))
                lateral = float((-x * ty + y * tx) / (norm * norm))
        row.update(
            target_normalized_forward=forward,
            target_normalized_lateral=lateral,
            target_normalized_coordinate_frame=frame,
        )
        output.append(row)
    return output


def _candidate_state_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("scene", "unknown")),
        str(row.get("rollout_row_id", "unknown")),
        str(row.get("step_row_id", "unknown")),
    )


def _population_state_groups(
    rows: Iterable[Mapping[str, Any]],
    *,
    extra_fields: tuple[str, ...] = (),
) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    """Group audit rows by persisted cohort/state and explicit population.

    A state is one factual ``scene/rollout/step`` record.  Aggregation must
    happen after the state reduction: otherwise states with a large candidate
    shell silently dominate the scientific summary.
    """
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    state_keys: set[tuple[str, ...]] = set()
    for raw in rows:
        row = dict(raw)
        cohort = str(row.get("generation_cohort_id", "unknown"))
        scene, rollout_id, step_id = _candidate_state_key(row)
        extra = tuple(str(row.get(field, "unknown")) for field in extra_fields)
        state_keys.add((cohort, scene, rollout_id, step_id, *extra))
        for population in ("all", "actor_valid"):
            if population == "actor_valid" and not bool(row.get("actor_action")):
                continue
            grouped.setdefault((cohort, scene, rollout_id, step_id, *extra, population), []).append(row)
    for state_key in state_keys:
        grouped.setdefault((*state_key, "actor_valid"), [])
    return grouped


def _candidate_scientific_state_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """Return the ordered factual state identity used by scientific reducers."""

    cohort = str(row.get("generation_cohort_id", "unknown"))
    return (cohort, *_candidate_state_key(row))


def _iter_candidate_state_chunks(rows: Iterable[Mapping[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    """Yield contiguous factual states while retaining no prior candidate rows."""

    current_key: tuple[str, str, str, str] | None = None
    current: list[dict[str, Any]] = []
    closed: set[tuple[str, str, str, str]] = set()
    for raw in rows:
        row = dict(raw)
        key = _candidate_scientific_state_key(row)
        if current_key is not None and key != current_key:
            closed.add(current_key)
            yield current
            current = []
        if key in closed:
            raise ValueError(f"candidate scientific rows interleave factual state {key!r}")
        current_key = key
        current.append(row)
    if current:
        yield current


def _iter_candidate_state_groups(
    rows: Iterable[Mapping[str, Any]], *, extra_fields: tuple[str, ...] = ()
) -> Iterable[tuple[tuple[str, ...], list[dict[str, Any]]]]:
    """Reduce each bounded state chunk before advancing the source stream."""

    for chunk in _iter_candidate_state_chunks(rows):
        yield from _population_state_groups(chunk, extra_fields=extra_fields).items()


def _sort_candidate_summary_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restore canonical public ordering after bounded state reduction."""

    normalized: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        if "candidate_direction_count" not in row and "candidate_total_count" in row:
            row["candidate_direction_count"] = row["candidate_total_count"]
        normalized.append(row)
    level_order = {"state": 0, "scene_macro": 1, "cohort_macro": 2}
    metric_order = {"decision_horizontal_radius_m": 0, "decision_distance_m": 1, "decision_height_m": 2}
    fields = (
        "generation_cohort_id",
        "scene",
        "rollout_row_id",
        "step_row_id",
        "population",
        "position_family",
        "evidence",
        "radius_deg",
        "azimuth_bin",
        "sin_elevation_bin",
    )
    return sorted(
        normalized,
        key=lambda row: (
            level_order.get(str(row.get("aggregation_level", "")), 99),
            *(str(row.get(field, "")) for field in fields[:5]),
            metric_order.get(str(row.get("metric", "")), 99),
            *(str(row.get(field, "")) for field in fields[5:]),
        ),
    )


def candidate_direction_evidence(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize directions per factual state, then scene and cohort macros."""
    azimuth_bins, elevation_bins = 12, 6
    density: list[dict[str, Any]] = []
    cap_rows: list[dict[str, Any]] = []
    angular_rows: list[dict[str, Any]] = []
    phi = (1.0 + np.sqrt(5.0)) / 2.0

    def fibonacci_sphere(count: int) -> np.ndarray:
        index = np.arange(count, dtype=np.float64)
        z = 1.0 - 2.0 * (index + 0.5) / count
        theta = 2.0 * np.pi * index / phi
        return np.column_stack((np.cos(theta) * np.sqrt(1.0 - z * z), np.sin(theta) * np.sqrt(1.0 - z * z), z))

    cap_centers, probes = fibonacci_sphere(128), fibonacci_sphere(512)
    for key, state_rows in _iter_candidate_state_groups(rows):
        cohort, scene, rollout_id, step_id, population = key
        vectors: list[np.ndarray] = []
        counts = np.zeros((azimuth_bins, elevation_bins), dtype=np.int64)
        for row in state_rows:
            try:
                vector = np.asarray(
                    [
                        row.get("decision_relative_x_m", row.get("root_relative_x_m")),
                        row.get("decision_relative_y_m", row.get("root_relative_y_m")),
                        row.get("decision_relative_z_m", row.get("root_relative_z_m")),
                    ],
                    dtype=np.float64,
                )
                radius = float(np.linalg.norm(vector))
            except (TypeError, ValueError):
                radius = 0.0
            if not np.isfinite(radius) or radius <= _GEOMETRY_EPSILON:
                continue
            vector /= radius
            vectors.append(vector)
            # EFM/ARIA camera-local coordinates are Left-Up-Forward (LUF).
            azimuth = float(np.arctan2(vector[0], vector[2]))
            sin_elevation = float(np.clip(vector[1], -1.0, 1.0))
            ai = min(azimuth_bins - 1, int(((azimuth + np.pi) / (2 * np.pi)) * azimuth_bins))
            ei = min(elevation_bins - 1, int(((sin_elevation + 1.0) / 2.0) * elevation_bins))
            counts[ai, ei] += 1
        valid = len(vectors)
        base = {
            "evidence": "equal_area_direction_density",
            "aggregation_level": "state",
            "generation_cohort_id": cohort,
            "scene": scene,
            "rollout_row_id": rollout_id,
            "step_row_id": step_id,
            "population": population,
            "state_count": 1,
            "total_count": len(state_rows),
            "valid_count": valid,
            "finite_count": valid,
            "missing_count": len(state_rows) - valid,
            "candidate_total_count": len(state_rows),
            "candidate_finite_count": valid,
            "candidate_missing_count": len(state_rows) - valid,
            "defined_state_count": int(valid > 0),
            "scene_count": 1,
            "candidate_direction_count": len(state_rows),
            "units": "solid-angle fraction",
            "protocol": {"binning": "azimuth x sin(elevation)"},
        }
        for ai in range(azimuth_bins):
            for ei in range(elevation_bins):
                density.append(
                    {
                        **base,
                        "azimuth_bin": ai,
                        "sin_elevation_bin": ei,
                        "count": int(counts[ai, ei]),
                        "mean_state_fraction": None if not valid else float(counts[ai, ei] / valid),
                        "available": valid > 0,
                    }
                )
        if vectors:
            points = np.asarray(vectors)
            discrepancies = []
            for radius in (30, 60, 90, 120, 150):
                threshold = np.cos(np.radians(radius))
                observed = np.mean(points @ cap_centers.T >= threshold, axis=0)
                expected = (1.0 - threshold) / 2.0
                discrepancies.append(float(np.max(np.abs(observed - expected))))
            for radius, value in zip((30, 60, 90, 120, 150), discrepancies, strict=True):
                cap_rows.append(
                    {
                        "evidence": "spherical_cap_discrepancy",
                        "metric_name": "distance_from_isotropy",
                        "aggregation_level": "state",
                        "generation_cohort_id": cohort,
                        "scene": scene,
                        "rollout_row_id": rollout_id,
                        "step_row_id": step_id,
                        "population": population,
                        "radius_deg": radius,
                        "value": value,
                        "discrepancy": value,
                        "valid_count": valid,
                        "candidate_total_count": len(state_rows),
                        "candidate_finite_count": valid,
                        "candidate_missing_count": len(state_rows) - valid,
                        "state_count": 1,
                        "defined_state_count": 1,
                        "available": True,
                        "units": "fraction",
                        "protocol": {
                            "reference": "fixed Fibonacci sphere",
                            "null_model": "uniform S2",
                            "cap_centers": 128,
                            "reference_count": 128,
                            "interpretation": "distance from isotropy only; not a generator-defect test",
                        },
                    }
                )
            cosine = np.clip(points @ points.T, -1.0, 1.0)
            if len(points) == 1:
                nearest = np.asarray([], dtype=np.float64)
            else:
                np.fill_diagonal(cosine, -1.0)
                nearest = np.degrees(np.arccos(np.max(cosine, axis=1)))
            # The fixed reference is augmented with each observed antipode so
            # a singleton has an explicit ~180 degree uncovered direction,
            # while an antipodal pair has the expected ~90 degree radius.
            probe_directions = np.vstack((probes, -points))
            probe_nearest = np.degrees(np.arccos(np.clip(np.max(probe_directions @ points.T, axis=1), -1.0, 1.0)))
            angular_rows.append(
                {
                    "evidence": "nearest_neighbor_angular_separation",
                    "aggregation_level": "state",
                    "generation_cohort_id": cohort,
                    "scene": scene,
                    "rollout_row_id": rollout_id,
                    "step_row_id": step_id,
                    "population": population,
                    "value": None if nearest.size == 0 else float(np.mean(nearest)),
                    "nearest_neighbor_deg": None if nearest.size == 0 else float(np.mean(nearest)),
                    "nearest_neighbor_available": bool(nearest.size),
                    "nearest_neighbor_reason": None if nearest.size else "undefined for a singleton state",
                    "covering_radius_deg": float(np.max(probe_nearest)),
                    "probe_covering_radius_deg": float(np.max(probe_nearest)),
                    "valid_count": valid,
                    "candidate_total_count": len(state_rows),
                    "candidate_finite_count": valid,
                    "candidate_missing_count": len(state_rows) - valid,
                    "state_count": 1,
                    "defined_state_count": 1,
                    "available": True,
                    "units": "degrees",
                    "protocol": {
                        "reference": "fixed Fibonacci sphere",
                        "covering_probes": 512,
                        "reference_count": 512,
                        "covering_reference_count": 512,
                    },
                }
            )
        else:
            for radius in (30, 60, 90, 120, 150):
                cap_rows.append(
                    {
                        **base,
                        "evidence": "spherical_cap_discrepancy",
                        "metric_name": "distance_from_isotropy",
                        "radius_deg": radius,
                        "value": None,
                        "discrepancy": None,
                        "available": False,
                        "units": "fraction",
                        "protocol": {
                            "reference": "fixed Fibonacci sphere",
                            "null_model": "uniform S2",
                            "cap_centers": 128,
                            "reference_count": 128,
                            "interpretation": "distance from isotropy only; not a generator-defect test",
                        },
                    }
                )
            angular_rows.append(
                {
                    **base,
                    "evidence": "nearest_neighbor_angular_separation",
                    "value": None,
                    "nearest_neighbor_deg": None,
                    "covering_radius_deg": None,
                    "available": False,
                    "units": "degrees",
                    "protocol": {
                        "reference": "fixed Fibonacci sphere",
                        "covering_probes": 512,
                        "reference_count": 512,
                        "covering_reference_count": 512,
                    },
                }
            )

    # Cell-wise macros preserve the complete 12x6 grid while excluding only
    # unavailable state values from numeric denominators.
    for level in ("scene_macro", "cohort_macro"):
        groups: dict[tuple[str, str, str, int, int], list[dict[str, Any]]] = {}
        for row in density:
            if row["aggregation_level"] != "state":
                continue
            scene = str(row["scene"]) if level == "scene_macro" else "all"
            groups.setdefault(
                (
                    str(row["generation_cohort_id"]),
                    scene,
                    str(row["population"]),
                    int(row["azimuth_bin"]),
                    int(row["sin_elevation_bin"]),
                ),
                [],
            ).append(row)
        for key, grouped in sorted(groups.items()):
            state_facets: dict[tuple[str, str, str], dict[str, Any]] = {}
            for row in grouped:
                state_key = (str(row["scene"]), str(row["rollout_row_id"]), str(row["step_row_id"]))
                state_facets.setdefault(state_key, row)
            facet_rows = list(state_facets.values())
            total_count = sum(int(row["total_count"]) for row in facet_rows)
            valid_count = sum(int(row["valid_count"]) for row in facet_rows)
            missing_count = sum(int(row["missing_count"]) for row in facet_rows)
            if level == "cohort_macro":
                by_scene: dict[str, list[float]] = {}
                for row in grouped:
                    if row["available"] and row["mean_state_fraction"] is not None:
                        by_scene.setdefault(str(row.get("scene", "unknown")), []).append(
                            float(row["mean_state_fraction"])
                        )
                values = [float(np.mean(scene_values)) for scene_values in by_scene.values() if scene_values]
            else:
                values = [
                    float(row["mean_state_fraction"])
                    for row in grouped
                    if row["available"] and row["mean_state_fraction"] is not None
                ]
            density.append(
                {
                    **grouped[0],
                    "aggregation_level": level,
                    "rollout_row_id": "all",
                    "step_row_id": "all",
                    "scene": key[1],
                    "state_count": len(facet_rows),
                    "defined_state_count": sum(int(row.get("available", False)) for row in facet_rows),
                    "scene_count": len({str(row.get("scene", "unknown")) for row in facet_rows}),
                    "total_count": total_count,
                    "count": sum(int(row.get("count", 0)) for row in facet_rows),
                    "candidate_direction_count": total_count,
                    "valid_count": valid_count,
                    "finite_count": valid_count,
                    "missing_count": missing_count,
                    "candidate_total_count": total_count,
                    "candidate_finite_count": valid_count,
                    "candidate_missing_count": missing_count,
                    "mean_state_fraction": None if not values else float(np.mean(values)),
                    "available": bool(values),
                    "cohort_macro_population": key[2],
                }
            )
    for rows_out, metric_name in ((cap_rows, "cap"), (angular_rows, "angular")):
        for level in ("scene_macro", "cohort_macro"):
            metric_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
            for row in rows_out:
                if row["aggregation_level"] != "state":
                    continue
                scene = str(row["scene"]) if level == "scene_macro" else "all"
                facet = str(row.get("radius_deg", metric_name))
                metric_groups.setdefault(
                    (str(row["generation_cohort_id"]), scene, str(row["population"]), facet), []
                ).append(row)
            for key, grouped in sorted(metric_groups.items(), key=lambda item: tuple(map(str, item[0]))):
                value_key = "discrepancy" if metric_name == "cap" else "nearest_neighbor_deg"
                if level == "cohort_macro":
                    metric_by_scene: dict[str, list[float]] = {}
                    for row in grouped:
                        value = row.get(value_key)
                        if value is not None:
                            metric_by_scene.setdefault(str(row.get("scene", "unknown")), []).append(float(value))
                    values = [float(np.mean(scene_values)) for scene_values in metric_by_scene.values() if scene_values]
                else:
                    values = [float(r[value_key]) for r in grouped if r.get(value_key) is not None]
                covering_values = [
                    float(row["covering_radius_deg"]) for row in grouped if row.get("covering_radius_deg") is not None
                ]
                if level == "cohort_macro":
                    by_scene_covering: dict[str, list[float]] = {}
                    for row in grouped:
                        value = row.get("covering_radius_deg")
                        if value is not None:
                            by_scene_covering.setdefault(str(row.get("scene", "unknown")), []).append(float(value))
                    covering_values = [
                        float(np.mean(scene_values)) for scene_values in by_scene_covering.values() if scene_values
                    ]
                rows_out.append(
                    {
                        **grouped[0],
                        "aggregation_level": level,
                        "rollout_row_id": "all",
                        "step_row_id": "all",
                        "scene": key[1],
                        "state_count": len(grouped),
                        "defined_state_count": sum(int(row.get("defined_state_count", 0)) for row in grouped),
                        "scene_count": len({str(row.get("scene", "unknown")) for row in grouped}),
                        "total_count": sum(int(row["candidate_total_count"]) for row in grouped),
                        "finite_count": sum(int(row["candidate_finite_count"]) for row in grouped),
                        "missing_count": sum(int(row["candidate_missing_count"]) for row in grouped),
                        "valid_count": sum(int(row.get("valid_count", 0)) for row in grouped),
                        "candidate_direction_count": sum(
                            int(row.get("candidate_direction_count", row.get("candidate_total_count", 0)))
                            for row in grouped
                        ),
                        "candidate_total_count": sum(int(row["candidate_total_count"]) for row in grouped),
                        "candidate_finite_count": sum(int(row["candidate_finite_count"]) for row in grouped),
                        "candidate_missing_count": sum(int(row["candidate_missing_count"]) for row in grouped),
                        "value": None if not values else float(np.mean(values)),
                        value_key: None if not values else float(np.mean(values)),
                        "nearest_neighbor_available": bool(values) if metric_name == "angular" else None,
                        "nearest_neighbor_reason": None
                        if metric_name == "angular" and values
                        else "undefined for the selected state population"
                        if metric_name == "angular"
                        else None,
                        "covering_radius_deg": None if not covering_values else float(np.mean(covering_values)),
                        "probe_covering_radius_deg": None if not covering_values else float(np.mean(covering_values)),
                        "available": bool(values or covering_values),
                        "cohort_macro_population": key[2],
                    }
                )
    return {
        "density_rows": _sort_candidate_summary_rows(density),
        "cap_rows": _sort_candidate_summary_rows(cap_rows),
        "angular_support_rows": _sort_candidate_summary_rows(angular_rows),
    }


def candidate_spatial_support_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarize spatial support with shell- and population-preserving macros."""
    output: list[dict[str, Any]] = []
    for key, grouped in _iter_candidate_state_groups(rows, extra_fields=("position",)):
        cohort, scene, rollout_id, step_id, shell, population = key
        values: dict[str, list[float]] = {
            "decision_horizontal_radius_m": [
                float(
                    np.hypot(
                        cast(float, _finite_or_none(r.get("decision_relative_x_m", r.get("root_relative_x_m")))),
                        cast(float, _finite_or_none(r.get("decision_relative_z_m", r.get("root_relative_z_m")))),
                    )
                )
                for r in grouped
                if _finite_or_none(r.get("decision_relative_x_m", r.get("root_relative_x_m"))) is not None
                and _finite_or_none(r.get("decision_relative_z_m", r.get("root_relative_z_m"))) is not None
            ],
            "decision_distance_m": [
                float(
                    np.linalg.norm(
                        [
                            cast(float, _finite_or_none(r.get("decision_relative_x_m", r.get("root_relative_x_m")))),
                            cast(float, _finite_or_none(r.get("decision_relative_y_m", r.get("root_relative_y_m")))),
                            cast(float, _finite_or_none(r.get("decision_relative_z_m", r.get("root_relative_z_m")))),
                        ]
                    )
                )
                for r in grouped
                if all(
                    _finite_or_none(r.get(decision, r.get(root))) is not None
                    for decision, root in zip(
                        ("decision_relative_x_m", "decision_relative_y_m", "decision_relative_z_m"),
                        ("root_relative_x_m", "root_relative_y_m", "root_relative_z_m"),
                        strict=True,
                    )
                )
            ],
            "decision_height_m": [
                cast(float, _finite_or_none(r.get("decision_relative_y_m", r.get("root_relative_y_m"))))
                for r in grouped
                if _finite_or_none(r.get("decision_relative_y_m", r.get("root_relative_y_m"))) is not None
            ],
        }
        for metric, vals in values.items():
            output.append(
                {
                    "metric": metric,
                    "aggregation_level": "state",
                    "generation_cohort_id": cohort,
                    "scene": scene,
                    "rollout_row_id": rollout_id,
                    "step_row_id": step_id,
                    "position_family": shell,
                    "population": population,
                    "count": len(grouped),
                    "total_count": len(grouped),
                    "finite_count": len(vals),
                    "missing_count": len(grouped) - len(vals),
                    "candidate_total_count": len(grouped),
                    "candidate_finite_count": len(vals),
                    "candidate_missing_count": len(grouped) - len(vals),
                    "state_count": 1,
                    "defined_state_count": int(bool(vals)),
                    "scene_count": 1,
                    "mean": None if not vals else float(np.mean(vals)),
                    "units": "m",
                    "available": bool(vals),
                    "zero_radius_policy": "included",
                }
            )
    for level in ("scene_macro", "cohort_macro"):
        groups_macro: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
        for row in output:
            if row["aggregation_level"] != "state":
                continue
            scene = str(row["scene"]) if level == "scene_macro" else "all"
            groups_macro.setdefault(
                (
                    str(row["generation_cohort_id"]),
                    scene,
                    str(row["position_family"]),
                    str(row["population"]),
                    str(row["metric"]),
                ),
                [],
            ).append(row)
        for key, grouped in sorted(groups_macro.items()):
            if level == "cohort_macro":
                by_scene: dict[str, list[float]] = {}
                for row in grouped:
                    if row.get("mean") is not None:
                        by_scene.setdefault(str(row.get("scene", "unknown")), []).append(float(row["mean"]))
                macro_values = [float(np.mean(scene_values)) for scene_values in by_scene.values() if scene_values]
            else:
                macro_values = [float(r["mean"]) for r in grouped if r.get("mean") is not None]
            output.append(
                {
                    **grouped[0],
                    "aggregation_level": level,
                    "rollout_row_id": "all",
                    "step_row_id": "all",
                    "scene": key[1],
                    "mean": None if not macro_values else float(np.mean(macro_values)),
                    "count": sum(int(row.get("count", 0)) for row in grouped),
                    "total_count": sum(int(row.get("total_count", row.get("count", 0))) for row in grouped),
                    "finite_count": sum(int(row.get("finite_count", 0)) for row in grouped),
                    "missing_count": sum(int(row.get("missing_count", 0)) for row in grouped),
                    "candidate_total_count": sum(
                        int(row.get("candidate_total_count", row.get("count", 0))) for row in grouped
                    ),
                    "candidate_finite_count": sum(
                        int(row.get("candidate_finite_count", row.get("finite_count", 0))) for row in grouped
                    ),
                    "candidate_missing_count": sum(
                        int(row.get("candidate_missing_count", row.get("missing_count", 0))) for row in grouped
                    ),
                    "state_count": len(grouped),
                    "defined_state_count": sum(int(row.get("defined_state_count", 0)) for row in grouped),
                    "scene_count": len({str(row.get("scene", "unknown")) for row in grouped}),
                    "available": bool(macro_values),
                }
            )
    return _sort_candidate_summary_rows(output)


def candidate_target_view_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarize actor-visible target framing and explicit visibility gaps."""
    result: list[dict[str, Any]] = []
    for key, grouped in _iter_candidate_state_groups(rows):
        cohort, scene, rollout_id, step_id, population = key
        base = {
            "generation_cohort_id": cohort,
            "scene": scene,
            "rollout_row_id": rollout_id,
            "step_row_id": step_id,
            "population": population,
            "aggregation_level": "state",
            "count": len(grouped),
            "total_count": len(grouped),
            "candidate_total_count": len(grouped),
            "state_count": 1,
            "scene_count": 1,
        }
        for evidence_name, source_name, units in (
            ("target_distance", "target_distance_m", "m"),
            ("target_view_angle", "target_view_angle_deg", "degrees"),
            ("target_pixel_margin", "target_pixel_margin_px", "px"),
            ("target_in_fov", "target_in_fov", "fraction"),
        ):
            finite = [value for row in grouped if (value := _finite_or_none(row.get(source_name))) is not None]
            result.append(
                {
                    **base,
                    "evidence": evidence_name,
                    "available": bool(finite),
                    "finite_count": len(finite),
                    "missing_count": len(grouped) - len(finite),
                    "candidate_finite_count": len(finite),
                    "candidate_missing_count": len(grouped) - len(finite),
                    "defined_state_count": int(bool(finite)),
                    "mean": None if not finite else float(np.mean(finite)),
                    "units": units,
                }
            )
        for name, units, reason in (
            (
                "target_fov_margin",
                "degrees",
                "signed angular boundary margin is not persisted; use exact CameraTW in-FOV and pixel margin",
            ),
            (
                "target_line_of_sight",
                "boolean",
                "scene occlusion or target-surface visibility is not persisted",
            ),
        ):
            result.append(
                {
                    **base,
                    "evidence": name,
                    "available": False,
                    "finite_count": 0,
                    "missing_count": len(grouped),
                    "candidate_finite_count": 0,
                    "candidate_missing_count": len(grouped),
                    "defined_state_count": 0,
                    "units": units,
                    "reason": reason,
                }
            )
    for level in ("scene_macro", "cohort_macro"):
        groups_macro: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for row in result:
            if row["aggregation_level"] != "state":
                continue
            scene = str(row["scene"]) if level == "scene_macro" else "all"
            groups_macro.setdefault(
                (str(row["generation_cohort_id"]), scene, str(row["population"]), str(row["evidence"])), []
            ).append(row)
        for key, grouped in sorted(groups_macro.items()):
            if level == "cohort_macro":
                by_scene: dict[str, list[float]] = {}
                for row in grouped:
                    if row.get("mean") is not None:
                        by_scene.setdefault(str(row.get("scene", "unknown")), []).append(float(row["mean"]))
                finite = [float(np.mean(values)) for values in by_scene.values() if values]
            else:
                finite = [float(row["mean"]) for row in grouped if row.get("mean") is not None]
            result.append(
                {
                    **grouped[0],
                    "aggregation_level": level,
                    "rollout_row_id": "all",
                    "step_row_id": "all",
                    "scene": key[1],
                    "mean": None if not finite else float(np.mean(finite)),
                    "available": bool(finite),
                    "count": sum(int(row["count"]) for row in grouped),
                    "total_count": sum(int(row.get("total_count", row.get("count", 0))) for row in grouped),
                    "finite_count": sum(int(row.get("finite_count", 0)) for row in grouped),
                    "missing_count": sum(int(row.get("missing_count", 0)) for row in grouped),
                    "candidate_total_count": sum(
                        int(row.get("candidate_total_count", row.get("count", 0))) for row in grouped
                    ),
                    "candidate_finite_count": sum(
                        int(row.get("candidate_finite_count", row.get("finite_count", 0))) for row in grouped
                    ),
                    "candidate_missing_count": sum(
                        int(row.get("candidate_missing_count", row.get("missing_count", 0))) for row in grouped
                    ),
                    "state_count": len(grouped),
                    "defined_state_count": sum(int(row.get("defined_state_count", 0)) for row in grouped),
                    "scene_count": len({str(row.get("scene", "unknown")) for row in grouped}),
                }
            )
    return _sort_candidate_summary_rows(result)


def candidate_motion_support_evidence(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarize motion and collision diagnostics per state and real macros."""
    result: list[dict[str, Any]] = []
    metrics = (
        ("motion_step_length_m", "m"),
        ("motion_height_delta_m", "m"),
        ("motion_backward_step_m", "m"),
        ("motion_yaw_delta_deg", "degrees"),
        ("free_space_margin_m", "m"),
        ("path_min_clearance_m", "m"),
    )
    for key, grouped in _iter_candidate_state_groups(rows):
        cohort, scene, rollout_id, step_id, population = key
        base = {
            "generation_cohort_id": cohort,
            "scene": scene,
            "rollout_row_id": rollout_id,
            "step_row_id": step_id,
            "population": population,
            "aggregation_level": "state",
            "count": len(grouped),
            "total_count": len(grouped),
            "candidate_total_count": len(grouped),
            "scene_count": 1,
        }
        for metric, units in metrics:
            values = [value for row in grouped if (value := _finite_or_none(row.get(metric))) is not None]
            result.append(
                {
                    **base,
                    "metric": metric,
                    "available": bool(values),
                    "finite_count": len(values),
                    "missing_count": len(grouped) - len(values),
                    "candidate_finite_count": len(values),
                    "candidate_missing_count": len(grouped) - len(values),
                    "defined_state_count": int(bool(values)),
                    "mean": None if not values else float(np.mean(values)),
                    "units": units,
                }
            )
        applicable = [row for row in grouped if row.get("path_collision_applicable") is True]
        evaluated = [row for row in applicable if row.get("path_collision_evaluated") is True]
        collisions = [row for row in evaluated if row.get("path_collision") is True]
        result.append(
            {
                **base,
                "metric": "path_collision_rate",
                "available": bool(evaluated),
                "finite_count": len(evaluated),
                "missing_count": len(grouped) - len(evaluated),
                "candidate_finite_count": len(evaluated),
                "candidate_missing_count": len(grouped) - len(evaluated),
                "defined_state_count": int(bool(evaluated)),
                "applicable_count": len(applicable),
                "evaluated_count": len(evaluated),
                "collision_count": len(collisions),
                "not_applicable_count": len(grouped) - len(applicable),
                "applicable_unevaluated_count": len(applicable) - len(evaluated),
                "collision_rate": None if not evaluated else len(collisions) / len(evaluated),
                "units": "fraction",
            }
        )
    for level in ("scene_macro", "cohort_macro"):
        groups_macro: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for row in result:
            if row["aggregation_level"] != "state":
                continue
            scene = str(row["scene"]) if level == "scene_macro" else "all"
            groups_macro.setdefault(
                (str(row["generation_cohort_id"]), scene, str(row["population"]), str(row["metric"])), []
            ).append(row)
        for key, grouped in sorted(groups_macro.items()):
            base = {
                **grouped[0],
                "aggregation_level": level,
                "rollout_row_id": "all",
                "step_row_id": "all",
                "scene": key[1],
                "count": sum(int(row["count"]) for row in grouped),
                "total_count": sum(int(row.get("total_count", row.get("count", 0))) for row in grouped),
                "finite_count": sum(int(row.get("finite_count", 0)) for row in grouped),
                "missing_count": sum(int(row.get("missing_count", 0)) for row in grouped),
                "candidate_total_count": sum(
                    int(row.get("candidate_total_count", row.get("count", 0))) for row in grouped
                ),
                "candidate_finite_count": sum(
                    int(row.get("candidate_finite_count", row.get("finite_count", 0))) for row in grouped
                ),
                "candidate_missing_count": sum(
                    int(row.get("candidate_missing_count", row.get("missing_count", 0))) for row in grouped
                ),
                "state_count": len(grouped),
                "defined_state_count": sum(
                    int(row.get("defined_state_count", row.get("available", False))) for row in grouped
                ),
                "scene_count": len({str(row.get("scene", "unknown")) for row in grouped}),
            }
            if key[3] == "path_collision_rate":
                applicable = sum(int(row.get("applicable_count", 0)) for row in grouped)
                evaluated = sum(int(row.get("evaluated_count", 0)) for row in grouped)
                collisions = sum(int(row.get("collision_count", 0)) for row in grouped)
                state_rates = [float(row["collision_rate"]) for row in grouped if row.get("collision_rate") is not None]
                if level == "cohort_macro":
                    collision_by_scene: dict[str, list[float]] = {}
                    for row in grouped:
                        rate = row.get("collision_rate")
                        if rate is not None:
                            collision_by_scene.setdefault(str(row.get("scene", "unknown")), []).append(float(rate))
                    scene_rates = [float(np.mean(rates)) for rates in collision_by_scene.values() if rates]
                else:
                    scene_rates = state_rates
                base.update(
                    applicable_count=applicable,
                    evaluated_count=evaluated,
                    collision_count=collisions,
                    not_applicable_count=sum(int(row.get("not_applicable_count", 0)) for row in grouped),
                    applicable_unevaluated_count=sum(
                        int(row.get("applicable_unevaluated_count", 0)) for row in grouped
                    ),
                    collision_rate=None if not scene_rates else float(np.mean(scene_rates)),
                    available=bool(scene_rates),
                )
            else:
                if level == "cohort_macro":
                    motion_by_scene: dict[str, list[float]] = {}
                    for row in grouped:
                        if row.get("mean") is not None:
                            motion_by_scene.setdefault(str(row.get("scene", "unknown")), []).append(float(row["mean"]))
                    values = [float(np.mean(scene_values)) for scene_values in motion_by_scene.values() if scene_values]
                else:
                    values = [float(row["mean"]) for row in grouped if row.get("mean") is not None]
                base.update(mean=None if not values else float(np.mean(values)), available=bool(values))
            result.append(base)
    return _sort_candidate_summary_rows(result)


_CANDIDATE_MACRO_MEAN_FIELDS = (
    "mean_state_fraction",
    "value",
    "discrepancy",
    "nearest_neighbor_deg",
    "covering_radius_deg",
    "probe_covering_radius_deg",
    "mean",
    "collision_rate",
)
_CANDIDATE_MACRO_SUM_FIELDS = (
    "count",
    "total_count",
    "finite_count",
    "missing_count",
    "valid_count",
    "candidate_direction_count",
    "candidate_total_count",
    "candidate_finite_count",
    "candidate_missing_count",
    "state_count",
    "defined_state_count",
    "applicable_count",
    "evaluated_count",
    "collision_count",
    "not_applicable_count",
    "applicable_unevaluated_count",
)


class _CandidateMacroAccumulator:
    """Reduce state summaries online into scene-then-cohort sufficient statistics."""

    def __init__(self, *, facet_fields: tuple[str, ...]) -> None:
        self._facet_fields = facet_fields
        self._scene_groups: dict[tuple[Any, ...], dict[str, Any]] = {}

    def consume(self, row: Mapping[str, Any]) -> None:
        """Consume one state-level summary without retaining that state row."""

        if row.get("aggregation_level") != "state":
            return
        key = (
            row.get("generation_cohort_id"),
            row.get("scene"),
            *(row.get(field) for field in self._facet_fields),
        )
        self._update(self._scene_groups, key, row)

    @staticmethod
    def _update(
        groups: dict[tuple[Any, ...], dict[str, Any]],
        key: tuple[Any, ...],
        row: Mapping[str, Any],
    ) -> None:
        stats = groups.setdefault(
            key,
            {
                "prototype": dict(row),
                "member_count": 0,
                "mean_sums": {},
                "mean_counts": {},
                "sums": {},
            },
        )
        stats["member_count"] = int(stats["member_count"]) + 1
        mean_sums = stats["mean_sums"]
        mean_counts = stats["mean_counts"]
        sums = stats["sums"]
        assert isinstance(mean_sums, dict)
        assert isinstance(mean_counts, dict)
        assert isinstance(sums, dict)
        for field in _CANDIDATE_MACRO_MEAN_FIELDS:
            value = _finite_or_none(row.get(field))
            if value is not None:
                mean_sums[field] = float(mean_sums.get(field, 0.0)) + value
                mean_counts[field] = int(mean_counts.get(field, 0)) + 1
        for field in _CANDIDATE_MACRO_SUM_FIELDS:
            value = row.get(field)
            if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
                sums[field] = int(sums.get(field, 0)) + int(value)

    def rows(self) -> list[dict[str, Any]]:
        """Return deterministic scene and equal-scene cohort macro rows."""

        scene_rows = [
            self._finalize(stats, level="scene_macro", scene=key[1])
            for key, stats in sorted(self._scene_groups.items(), key=lambda item: tuple(map(str, item[0])))
        ]
        cohort_groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in scene_rows:
            key = (row.get("generation_cohort_id"), *(row.get(field) for field in self._facet_fields))
            self._update(cohort_groups, key, row)
        cohort_rows = [
            self._finalize(stats, level="cohort_macro", scene="all")
            for _key, stats in sorted(cohort_groups.items(), key=lambda item: tuple(map(str, item[0])))
        ]
        return _sort_candidate_summary_rows([*scene_rows, *cohort_rows])

    @staticmethod
    def _finalize(stats: Mapping[str, Any], *, level: str, scene: Any) -> dict[str, Any]:
        prototype = stats["prototype"]
        mean_sums = stats["mean_sums"]
        mean_counts = stats["mean_counts"]
        sums = stats["sums"]
        assert isinstance(prototype, dict)
        assert isinstance(mean_sums, dict)
        assert isinstance(mean_counts, dict)
        assert isinstance(sums, dict)
        row = {
            **prototype,
            "aggregation_level": level,
            "rollout_row_id": "all",
            "step_row_id": "all",
            "scene": scene,
        }
        for field in _CANDIDATE_MACRO_MEAN_FIELDS:
            mean_count = int(mean_counts.get(field, 0))
            if field in prototype or mean_count:
                row[field] = None if not mean_count else float(mean_sums[field] / mean_count)
        for field in _CANDIDATE_MACRO_SUM_FIELDS:
            total = int(sums.get(field, 0))
            if field in prototype or total:
                row[field] = total
        if "candidate_total_count" in row:
            row["total_count"] = row["candidate_total_count"]
        if "candidate_finite_count" in row:
            row["finite_count"] = row["candidate_finite_count"]
        if "candidate_missing_count" in row:
            row["missing_count"] = row["candidate_missing_count"]
        if "state_count" not in row:
            row["state_count"] = int(stats["member_count"])
        row["scene_count"] = 1 if level == "scene_macro" else int(stats["member_count"])
        row["available"] = any(int(mean_counts.get(field, 0)) > 0 for field in _CANDIDATE_MACRO_MEAN_FIELDS)
        if "nearest_neighbor_available" in prototype:
            row["nearest_neighbor_available"] = int(mean_counts.get("nearest_neighbor_deg", 0)) > 0
            row["nearest_neighbor_reason"] = (
                None if row["nearest_neighbor_available"] else "undefined for the selected state population"
            )
        return row


def _candidate_scientific_macro_evidence(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Stream complete candidates into scene/cohort evidence without cached state rows."""

    direction_density = _CandidateMacroAccumulator(facet_fields=("population", "azimuth_bin", "sin_elevation_bin"))
    direction_cap = _CandidateMacroAccumulator(facet_fields=("population", "radius_deg"))
    direction_angular = _CandidateMacroAccumulator(facet_fields=("population", "evidence"))
    spatial = _CandidateMacroAccumulator(facet_fields=("position_family", "population", "metric"))
    target_view = _CandidateMacroAccumulator(facet_fields=("population", "evidence"))
    motion = _CandidateMacroAccumulator(facet_fields=("population", "metric"))
    for chunk in _iter_candidate_state_chunks(rows):
        direction = candidate_direction_evidence(chunk)
        for row in direction["density_rows"]:
            direction_density.consume(row)
        for row in direction["cap_rows"]:
            direction_cap.consume(row)
        for row in direction["angular_support_rows"]:
            direction_angular.consume(row)
        for row in candidate_spatial_support_evidence(chunk):
            spatial.consume(row)
        for row in candidate_target_view_evidence(chunk):
            target_view.consume(row)
        for row in candidate_motion_support_evidence(chunk):
            motion.consume(row)
    direction = {
        "density_rows": direction_density.rows(),
        "cap_rows": direction_cap.rows(),
        "angular_support_rows": direction_angular.rows(),
    }
    for evidence_rows in direction.values():
        for row in evidence_rows:
            row["cohort_macro_population"] = row["population"]
    return (
        direction,
        spatial.rows(),
        target_view.rows(),
        motion.rows(),
    )


def _probability_state_error(state: Mapping[str, Any]) -> str | None:
    """Return the fail-closed reason for one complete sampler vector."""

    total = int(state["total"])
    finite = int(state["finite_probability_count"])
    if finite != total or bool(state["missing"]):
        return "incomplete_probability_vector"
    if bool(state["negative"]):
        return "negative_probability"
    probability_sum = float(state["probability_sum"])
    if probability_sum <= 0.0:
        return "nonpositive_probability_sum"
    if not np.isclose(probability_sum, 1.0, rtol=0.0, atol=_SAMPLER_PROBABILITY_TOLERANCE):
        return "probability_not_normalized"
    return None


class _CandidatePopulationAccumulator:
    """Single-pass candidate aggregates with bounded deterministic sampling.

    The accumulator deliberately retains only state/family totals and a
    bounded display sample.  Candidate-level normalized rows remain owned by
    :func:`candidate_audit_rows` when an interactive caller explicitly asks
    for them.
    """

    def __init__(self, *, max_sample_rows: int) -> None:
        self.max_sample_rows = max_sample_rows
        self.population_count = 0
        self._sample: list[tuple[str, int, dict[str, Any]]] = []
        self._cohorts: dict[str, dict[str, Any]] = {}
        self._state_families: dict[CandidateGroupField, dict[tuple[str, str, str], dict[str, Any]]] = {
            key: {} for key in CANDIDATE_GROUP_FIELDS
        }
        self._groups: dict[CandidateGroupField, dict[str, dict[str, Any]]] = {key: {} for key in CANDIDATE_GROUP_FIELDS}
        self._collision: dict[str, dict[str, Any]] = {}
        self._target_evidence_roles: dict[str, dict[str, int]] = {}
        self._selection_states: dict[tuple[str, str], dict[str, Any]] = {}
        self._selection_vocab: dict[tuple[str, CandidateSelectionGroupField], set[str]] = {}

    def consume(self, row: Mapping[str, Any]) -> None:
        normalized = dict(row)
        self.population_count += 1
        cohort_id = str(normalized.get("generation_cohort_id", "unknown"))
        role = str(normalized.get("target_evidence_role", "unknown"))
        role_counts = self._target_evidence_roles.setdefault(cohort_id, {})
        role_counts[role] = role_counts.get(role, 0) + 1
        scene = str(normalized.get("scene", "unknown"))
        state_id = f"{scene}\0{normalized.get('rollout_row_id', 'unknown')}\0{normalized.get('step_row_id', 'unknown')}"
        cohort = self._cohorts.setdefault(
            cohort_id,
            {
                "generation_cohort": normalized.get("generation_cohort"),
                "total": 0,
                "selected": 0,
                "probability_sum": 0.0,
                "finite_probability_count": 0,
                "states": {},
            },
        )
        cohort["total"] = int(cohort["total"]) + 1
        cohort["selected"] = int(cohort["selected"]) + int(bool(normalized.get("selected")))
        probability = _finite_or_none(normalized.get("sampler_probability"))
        if probability is not None:
            cohort["probability_sum"] = float(cohort["probability_sum"]) + probability
            cohort["finite_probability_count"] = int(cohort["finite_probability_count"]) + 1
        states = cohort["states"]
        assert isinstance(states, dict)
        state = states.setdefault(
            state_id,
            {
                "scene": scene,
                "total": 0,
                "probability_sum": 0.0,
                "finite_probability_count": 0,
                "missing": False,
                "negative": False,
            },
        )
        state["total"] += 1
        if probability is None:
            state["missing"] = True
        else:
            state["probability_sum"] += probability
            state["finite_probability_count"] += 1
            state["negative"] |= probability < 0.0
        selection_probability = _finite_or_none(normalized.get("selection_probability"))
        selection_state = self._selection_states.setdefault(
            (cohort_id, state_id),
            {
                "generation_cohort": normalized.get("generation_cohort"),
                "scene": scene,
                "rollout_row_id": normalized.get("rollout_row_id"),
                "step_row_id": normalized.get("step_row_id"),
                "step_index": normalized.get("step_index"),
                "policy": normalized.get("policy"),
                "temperature": normalized.get("temperature"),
                "horizon": normalized.get("horizon"),
                "branch_factor": normalized.get("branch_factor"),
                "beam_width": normalized.get("beam_width"),
                "cumulative_target_root_gain": normalized.get("cumulative_target_root_gain"),
                "total": 0,
                "actor_valid": 0,
                "selected": 0,
                "probability_sum": 0.0,
                "finite_probability_count": 0,
                "missing": False,
                "negative": False,
                "families": {group_by: {} for group_by in CANDIDATE_SELECTION_GROUP_FIELDS},
            },
        )
        selection_state["total"] += 1
        selection_state["actor_valid"] += int(bool(normalized.get("actor_action")))
        selection_state["selected"] += int(bool(normalized.get("selected")))
        if selection_probability is None:
            selection_state["missing"] = True
        else:
            selection_state["probability_sum"] += selection_probability
            selection_state["finite_probability_count"] += 1
            selection_state["negative"] |= selection_probability < 0.0
        selection_families = selection_state["families"]
        assert isinstance(selection_families, dict)
        for selection_group in CANDIDATE_SELECTION_GROUP_FIELDS:
            family = _candidate_selection_family(normalized, selection_group)
            self._selection_vocab.setdefault((cohort_id, selection_group), set()).add(family)
            family_state = selection_families[selection_group].setdefault(
                family,
                {
                    "allocated": 0,
                    "actor_valid": 0,
                    "selected": 0,
                    "probability_sum": 0.0,
                    "finite_probability_count": 0,
                },
            )
            family_state["allocated"] += 1
            family_state["actor_valid"] += int(bool(normalized.get("actor_action")))
            family_state["selected"] += int(bool(normalized.get("selected")))
            if selection_probability is not None:
                family_state["probability_sum"] += selection_probability
                family_state["finite_probability_count"] += 1
        collision = self._collision.setdefault(
            cohort_id,
            {
                "generation_cohort": normalized.get("generation_cohort"),
                "count": 0,
                "available": 0,
                "collisions": 0,
                "not_applicable": 0,
                "clearance_count": 0,
                "clearance_sum": 0.0,
                "states": {},
            },
        )
        collision["count"] += 1
        evaluated = _collision_evaluated(normalized)
        if evaluated:
            collision["available"] += 1
            collision["collisions"] += int(bool(normalized.get("path_collision")))
        elif normalized.get("path_collision_applicable") is False:
            collision["not_applicable"] += 1
        clearance = _finite_or_none(normalized.get("path_min_clearance_m"))
        if clearance is not None:
            collision["clearance_count"] += 1
            collision["clearance_sum"] += clearance
        collision_state = collision["states"].setdefault(
            state_id,
            {"scene": scene, "count": 0, "available": 0, "collisions": 0, "clearance_count": 0, "clearance_sum": 0.0},
        )
        collision_state["count"] += 1
        collision_state["available"] += int(evaluated)
        collision_state["collisions"] += int(evaluated and bool(normalized.get("path_collision")))
        if clearance is not None:
            collision_state["clearance_count"] += 1
            collision_state["clearance_sum"] += clearance
        for group_by in CANDIDATE_GROUP_FIELDS:
            family = str(normalized.get(group_by, "unknown"))
            summary = self._groups[group_by].setdefault(
                family,
                {
                    "generation_cohort": normalized.get("generation_cohort"),
                    "total": 0,
                    "actor_valid": 0,
                    "oracle_valid": 0,
                    "q_train": 0,
                    "selected": 0,
                    "gain_sum": 0.0,
                    "gain_count": 0,
                },
            )
            summary["total"] += 1
            summary["actor_valid"] += int(bool(normalized.get("actor_action")))
            summary["oracle_valid"] += int(bool(normalized.get("oracle_label")))
            summary["q_train"] += int(bool(normalized.get("q_train")))
            summary["selected"] += int(bool(normalized.get("selected")))
            gain = _finite_or_none(normalized.get("target_root_gain"))
            if gain is not None:
                summary["gain_sum"] += gain
                summary["gain_count"] += 1
            state_key = (cohort_id, family, state_id)
            family_state = self._state_families[group_by].setdefault(
                state_key,
                {
                    "scene": scene,
                    "total": 0,
                    "actor_valid": 0,
                    "oracle_valid": 0,
                    "q_train": 0,
                    "selected": 0,
                    "probability_sum": 0.0,
                    "finite_probability_count": 0,
                },
            )
            family_state["total"] += 1
            family_state["actor_valid"] += int(bool(normalized.get("actor_action")))
            family_state["oracle_valid"] += int(bool(normalized.get("oracle_label")))
            family_state["q_train"] += int(bool(normalized.get("q_train")))
            family_state["selected"] += int(bool(normalized.get("selected")))
            if probability is not None:
                family_state["probability_sum"] += probability
                family_state["finite_probability_count"] += 1
        if self.max_sample_rows:
            candidate_id = int(normalized.get("candidate_row_id", -1))
            rank = hashlib.sha256(f"stored-rollout-display-v1\0{candidate_id}".encode()).hexdigest()
            self._sample.append((rank, candidate_id, normalized))
            self._sample.sort(key=lambda item: (item[0], item[1]))
            del self._sample[self.max_sample_rows :]

    @staticmethod
    def _state_macro(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        by_scene: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            by_scene.setdefault(str(row["scene"]), []).append(row)
        return [
            {
                "scene": scene,
                **{field: _macro_mean(scene_rows, field) for field in _MACRO_RATE_FIELDS},
            }
            for scene, scene_rows in sorted(by_scene.items())
        ]

    def compositions(self) -> dict[CandidateGroupField, list[dict[str, Any]]]:
        output: dict[CandidateGroupField, list[dict[str, Any]]] = {}
        for group_by in CANDIDATE_GROUP_FIELDS:
            families: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for (cohort_id, family, _state_id), state in self._state_families[group_by].items():
                families.setdefault((cohort_id, family), []).append(state)
            rows: list[dict[str, Any]] = []
            for (cohort_id, family), states in sorted(families.items()):
                scenes: dict[str, list[dict[str, Any]]] = {}
                for state in states:
                    scenes.setdefault(str(state["scene"]), []).append(state)
                scene_rates = [
                    {
                        "scene": scene,
                        **{
                            f"{field}_rate": float(
                                np.mean(
                                    [
                                        _safe_fraction(int(state[field]), int(state["total"])) or 0.0
                                        for state in scene_states
                                    ]
                                )
                            )
                            for field in ("actor_valid", "oracle_valid", "q_train", "selected")
                        },
                    }
                    for scene, scene_states in sorted(scenes.items())
                ]
                totals = {
                    field: sum(int(state[field]) for state in states)
                    for field in ("total", "actor_valid", "oracle_valid", "q_train", "selected")
                }
                rows.append(
                    {
                        "group_by": group_by,
                        "generation_cohort_id": cohort_id,
                        "generation_cohort": self._cohorts[cohort_id]["generation_cohort"],
                        "family": family,
                        "allocated_count": totals["total"],
                        "actor_valid_count": totals["actor_valid"],
                        "oracle_valid_count": totals["oracle_valid"],
                        "trainable_count": totals["q_train"],
                        "selected_count": totals["selected"],
                        "state_count": len(states),
                        "scene_count": len(scenes),
                        "macro_actor_valid_rate": float(np.mean([row["actor_valid_rate"] for row in scene_rates])),
                        "macro_oracle_valid_rate": float(np.mean([row["oracle_valid_rate"] for row in scene_rates])),
                        "macro_trainable_rate": float(np.mean([row["q_train_rate"] for row in scene_rates])),
                        "macro_selected_rate": float(np.mean([row["selected_rate"] for row in scene_rates])),
                        "aggregation": "state_then_scene_macro",
                    }
                )
            output[group_by] = rows
        return output

    def target_evidence_roles(self) -> list[dict[str, Any]]:
        """Return complete, cohort-qualified target evidence-role counts."""

        return [
            {
                "generation_cohort_id": cohort_id,
                "target_evidence_role": role,
                "candidate_count": count,
            }
            for cohort_id, roles in sorted(self._target_evidence_roles.items())
            for role, count in sorted(roles.items())
        ]

    def calibrations(self) -> dict[CandidateGroupField, list[dict[str, Any]]]:
        compositions = self.compositions()
        output: dict[CandidateGroupField, list[dict[str, Any]]] = {}
        for group_by in CANDIDATE_GROUP_FIELDS:
            rows: list[dict[str, Any]] = []
            for summary in compositions[group_by]:
                cohort_id = str(summary["generation_cohort_id"])
                family = str(summary["family"])
                cohort = self._cohorts[cohort_id]
                family_states = [
                    state
                    for (cid, fam, _), state in self._state_families[group_by].items()
                    if cid == cohort_id and fam == family
                ]
                all_states = cohort["states"]
                state_rows: list[dict[str, Any]] = []
                family_state_by_id = {
                    key[2]: value
                    for key, value in self._state_families[group_by].items()
                    if key[0] == cohort_id and key[1] == family
                }
                for state_id, base in all_states.items():
                    state = family_state_by_id.get(
                        state_id,
                        {
                            "scene": base["scene"],
                            "total": 0,
                            "selected": 0,
                            "probability_sum": 0.0,
                            "finite_probability_count": 0,
                        },
                    )
                    empirical = _safe_fraction(int(state["total"]), int(base["total"]))
                    proposal = (
                        None
                        if _probability_state_error(base) is not None
                        or (state["total"] and not state["finite_probability_count"])
                        else float(state["probability_sum"] / base["probability_sum"])
                    )
                    selected_total = sum(
                        int(value["selected"])
                        for (cid, _fam, sid), value in self._state_families[group_by].items()
                        if cid == cohort_id and sid == state_id
                    )
                    selected_share = _safe_fraction(int(state["selected"]), selected_total)
                    state_rows.append(
                        {
                            "scene": state["scene"],
                            "empirical_frequency": empirical,
                            "proposal_mass": proposal,
                            "selected_share": selected_share,
                            "selection_enrichment": None
                            if empirical in (None, 0.0) or selected_share is None
                            else selected_share / cast(float, empirical),
                        }
                    )
                scene_rows = self._state_macro(state_rows)
                probability_error = next(
                    (
                        f"{_probability_state_error(value)}:{key}"
                        for key, value in all_states.items()
                        if _probability_state_error(value) is not None
                    ),
                    None,
                )
                finite = int(sum(int(state["finite_probability_count"]) for state in family_states))
                proposal_mass = (
                    None
                    if probability_error or not finite or cohort["probability_sum"] <= 0
                    else float(
                        sum(float(state["probability_sum"]) for state in family_states)
                        / float(cohort["probability_sum"])
                    )
                )
                empirical = _safe_fraction(int(summary["allocated_count"]), int(cohort["total"]))
                selected_share = _safe_fraction(int(summary["selected_count"]), int(cohort["selected"]))
                macro = {
                    metric: _macro_mean(scene_rows, metric)
                    for metric in ("empirical_frequency", "proposal_mass", "selected_share", "selection_enrichment")
                }
                if probability_error is not None:
                    macro["proposal_mass"] = None
                rows.append(
                    {
                        "group_by": group_by,
                        "generation_cohort_id": cohort_id,
                        "generation_cohort": summary["generation_cohort"],
                        "family": family,
                        "candidate_count": summary["allocated_count"],
                        "finite_probability_count": finite,
                        "population_empirical_frequency": empirical,
                        "population_proposal_mass": proposal_mass,
                        "population_calibration_gap": None
                        if proposal_mass is None or empirical is None
                        else empirical - proposal_mass,
                        "population_selected_share": selected_share,
                        "population_selection_enrichment": None
                        if empirical in (None, 0.0) or selected_share is None
                        else selected_share / cast(float, empirical),
                        "state_count": len(all_states),
                        "scene_count": len(scene_rows),
                        "empirical_frequency": macro["empirical_frequency"],
                        "proposal_mass": macro["proposal_mass"],
                        "calibration_gap": None
                        if macro["proposal_mass"] is None or macro["empirical_frequency"] is None
                        else macro["empirical_frequency"] - macro["proposal_mass"],
                        "selected_share": macro["selected_share"],
                        "selection_enrichment": macro["selection_enrichment"],
                        "empirical_denominator": int(cohort["total"]),
                        "proposal_denominator": int(cohort["finite_probability_count"]),
                        "proposal_available": probability_error is None,
                        "proposal_unavailable_reason": probability_error,
                        "selected_denominator": int(cohort["selected"]),
                        "aggregation": "exact_store_population; descriptive family comparison",
                    }
                )
            output[group_by] = rows
        return output

    def collision(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cohort_id, summary in sorted(self._collision.items()):
            state_rows = []
            for state in summary["states"].values():
                state_rows.append(
                    {
                        "scene": state["scene"],
                        "collision_rate": _safe_fraction(state["collisions"], state["available"]),
                        "clearance_mean_m": None
                        if not state["clearance_count"]
                        else state["clearance_sum"] / state["clearance_count"],
                    }
                )
            scene_rows = self._state_macro(state_rows)
            available = int(summary["available"])
            clearance_count = int(summary["clearance_count"])
            rows.append(
                {
                    "generation_cohort_id": cohort_id,
                    "generation_cohort": summary["generation_cohort"],
                    "candidate_count": int(summary["count"]),
                    "collision_available_count": available,
                    "collision_evaluated_count": available,
                    "collision_not_applicable_count": int(summary["not_applicable"]),
                    "collision_unavailable_count": int(summary["count"]) - available - int(summary["not_applicable"]),
                    "collision_count": int(summary["collisions"]),
                    "population_collision_rate": _safe_fraction(int(summary["collisions"]), available),
                    "clearance_finite_count": clearance_count,
                    "population_clearance_mean_m": None
                    if not clearance_count
                    else float(summary["clearance_sum"]) / clearance_count,
                    "state_count": len(summary["states"]),
                    "scene_count": len(scene_rows),
                    "collision_rate": _macro_mean(scene_rows, "collision_rate"),
                    "clearance_mean_m": _macro_mean(scene_rows, "clearance_mean_m"),
                    "collision_denominator": available,
                    "clearance_denominator": clearance_count,
                    "available": bool(summary["count"]) and bool(available) and bool(clearance_count),
                    "reason": None
                    if summary["count"] and available and clearance_count
                    else "collision or clearance evidence is unavailable",
                }
            )
        return rows

    def selection_dynamics(self) -> dict[CandidateSelectionGroupField, list[dict[str, Any]]]:
        """Return state-level family availability, policy mass, and realized selection."""

        output: dict[CandidateSelectionGroupField, list[dict[str, Any]]] = {}
        for group_by in CANDIDATE_SELECTION_GROUP_FIELDS:
            rows: list[dict[str, Any]] = []
            for (cohort_id, _state_id), state in sorted(
                self._selection_states.items(),
                key=lambda item: (
                    item[0][0],
                    int(item[1].get("rollout_row_id") or -1),
                    int(item[1].get("step_index") or 0),
                ),
            ):
                probability_error = _probability_state_error(state)
                families = state["families"]
                assert isinstance(families, dict)
                selected_total = int(state["selected"])
                for family in sorted(self._selection_vocab.get((cohort_id, group_by), set())):
                    family_state = families[group_by].get(
                        family,
                        {
                            "allocated": 0,
                            "actor_valid": 0,
                            "selected": 0,
                            "probability_sum": 0.0,
                            "finite_probability_count": 0,
                        },
                    )
                    policy_mass = None if probability_error is not None else float(family_state["probability_sum"])
                    rows.append(
                        {
                            "group_by": group_by,
                            "family": family,
                            "generation_cohort_id": cohort_id,
                            "generation_cohort": state["generation_cohort"],
                            "scene": state["scene"],
                            "rollout_row_id": state["rollout_row_id"],
                            "step_row_id": state["step_row_id"],
                            "step_index": state["step_index"],
                            "policy": state["policy"],
                            "temperature": state["temperature"],
                            "horizon": state["horizon"],
                            "branch_factor": state["branch_factor"],
                            "beam_width": state["beam_width"],
                            "cumulative_target_root_gain": _finite_or_none(state["cumulative_target_root_gain"]),
                            "candidate_count": int(state["total"]),
                            "actor_valid_count": int(state["actor_valid"]),
                            "family_candidate_count": int(family_state["allocated"]),
                            "family_actor_valid_count": int(family_state["actor_valid"]),
                            "family_selected_count": int(family_state["selected"]),
                            "allocation_share": _safe_fraction(int(family_state["allocated"]), int(state["total"])),
                            "valid_share": _safe_fraction(int(family_state["actor_valid"]), int(state["actor_valid"])),
                            "policy_mass": policy_mass,
                            "selected_share": _safe_fraction(int(family_state["selected"]), selected_total),
                            "probability_available": probability_error is None,
                            "probability_unavailable_reason": probability_error,
                        }
                    )
            output[group_by] = rows
        return output

    def groups(self) -> dict[CandidateGroupField, list[dict[str, Any]]]:
        output: dict[CandidateGroupField, list[dict[str, Any]]] = {}
        for group_by in CANDIDATE_GROUP_FIELDS:
            rows = []
            for family, summary in sorted(self._groups[group_by].items()):
                total = int(summary["total"])
                gain_count = int(summary["gain_count"])
                rows.append(
                    {
                        group_by: family,
                        "total": total,
                        "actor_valid": int(summary["actor_valid"]),
                        "actor_valid_fraction": _safe_fraction(int(summary["actor_valid"]), total),
                        "q_train": int(summary["q_train"]),
                        "selected": int(summary["selected"]),
                        "mean_target_root_gain": None if not gain_count else float(summary["gain_sum"]) / gain_count,
                    }
                )
            output[group_by] = rows
        return output

    def sample(self) -> dict[str, Any]:
        rows = [row for _, _, row in self._sample]
        return {
            "rows": rows,
            "population_count": self.population_count,
            "display_count": len(rows),
            "max_rows": self.max_sample_rows,
            "seed": "stored-rollout-display-v1",
            "display_only": True,
        }


def _candidate_selection_family(row: Mapping[str, Any], group_by: CandidateSelectionGroupField) -> str:
    """Return one closed-vocabulary family label for selection diagnostics."""

    if group_by == "position_strategy":
        return f"{row.get('position', 'unknown')} · {row.get('strategy', 'unknown')}"
    return str(row.get(group_by, "unknown"))


def _selection_rows_have_factual_identity(rows: Iterable[Mapping[str, Any]]) -> bool:
    """Return whether state rows can form ordered factual sequences."""

    materialized = list(rows)
    return bool(materialized) and all(
        row.get("rollout_row_id") is not None and row.get("step_index") is not None for row in materialized
    )


def _materialize_selection_family_union(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Add zero-valued rows for families absent from compatible factual states."""

    materialized = [dict(row) for row in rows]
    families_by_contract: dict[tuple[Any, ...], set[str]] = {}
    for row in materialized:
        contract = (
            row.get("group_by"),
            row.get("policy"),
            row.get("horizon"),
            row.get("branch_factor"),
            row.get("beam_width"),
        )
        families_by_contract.setdefault(contract, set()).add(str(row["family"]))

    states: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in materialized:
        contract = (
            row.get("group_by"),
            row.get("policy"),
            row.get("horizon"),
            row.get("branch_factor"),
            row.get("beam_width"),
        )
        state = (
            contract,
            row.get("generation_cohort_id"),
            row.get("scene"),
            row.get("rollout_row_id"),
            row.get("step_row_id"),
            row.get("step_index"),
        )
        states.setdefault(state, []).append(row)

    output: list[dict[str, Any]] = []
    zero_fields = (
        "family_candidate_count",
        "family_actor_valid_count",
        "family_selected_count",
        "allocation_share",
        "valid_share",
        "selected_share",
    )
    for state_rows in states.values():
        template = state_rows[0]
        contract = (
            template.get("group_by"),
            template.get("policy"),
            template.get("horizon"),
            template.get("branch_factor"),
            template.get("beam_width"),
        )
        present = {str(row["family"]) for row in state_rows}
        output.extend(state_rows)
        for family in sorted(families_by_contract[contract] - present):
            zero_row = dict(template)
            zero_row["family"] = family
            for field in zero_fields:
                zero_row[field] = 0 if field.endswith("_count") else 0.0
            zero_row["policy_mass"] = 0.0 if _finite_or_none(template.get("policy_mass")) is not None else None
            zero_row["probability_available"] = template.get("probability_available")
            zero_row["probability_unavailable_reason"] = template.get("probability_unavailable_reason")
            output.append(zero_row)
    return output


def candidate_selection_transition_rows(
    dynamics_rows: Iterable[Mapping[str, Any]],
    *,
    pool_temperatures: bool = False,
) -> list[dict[str, Any]]:
    """Summarize expected and realized family transitions over factual depth.

    ``policy_mass`` is the complete candidate-level selection-probability mass
    for the next family. Realized transitions use the one persisted selected
    family. Both remain conditioned on the previous selected family and exact
    generation cohort unless ``pool_temperatures`` is requested. The pooled
    view recomputes frequencies from factual states while retaining the policy,
    horizon, branch-factor, and beam-width compatibility controls.
    """

    rows = [dict(row) for row in dynamics_rows]
    if pool_temperatures:
        rows = _materialize_selection_family_union(rows)
    by_rollout: dict[tuple[str, int], dict[int, list[dict[str, Any]]]] = {}
    for row in rows:
        rollout_row_id = row.get("rollout_row_id")
        step_index = row.get("step_index")
        if rollout_row_id is None or step_index is None:
            raise ValueError("Selection dynamics require rollout_row_id and step_index.")
        key = (str(row.get("generation_cohort_id", "unknown")), int(rollout_row_id))
        by_rollout.setdefault(key, {}).setdefault(int(step_index), []).append(row)

    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for (_cohort_id, _rollout_row_id), steps in sorted(by_rollout.items()):
        indices = sorted(steps)
        if indices != list(range(len(indices))):
            raise ValueError(f"Selection dynamics require contiguous zero-based factual steps; received {indices}.")
        for step_index in indices[1:]:
            previous_rows = steps[step_index - 1]
            current_rows = steps[step_index]
            previous_selected = [str(row["family"]) for row in previous_rows if int(row["family_selected_count"]) == 1]
            if len(previous_selected) != 1:
                raise ValueError("Each factual selection state must identify exactly one previously selected family.")
            previous_family = previous_selected[0]
            for row in current_rows:
                key = (
                    (
                        row.get("group_by"),
                        row.get("policy"),
                        row.get("horizon"),
                        row.get("branch_factor"),
                        row.get("beam_width"),
                        int(step_index),
                        previous_family,
                        str(row["family"]),
                    )
                    if pool_temperatures
                    else (
                        row.get("group_by"),
                        row.get("generation_cohort_id"),
                        row.get("generation_cohort"),
                        row.get("policy"),
                        row.get("temperature"),
                        row.get("horizon"),
                        row.get("branch_factor"),
                        row.get("beam_width"),
                        int(step_index),
                        previous_family,
                        str(row["family"]),
                    )
                )
                summary = grouped.setdefault(
                    key,
                    {
                        "context_count": 0,
                        "realized_count": 0,
                        "expected_values": [],
                        "missing_probability_count": 0,
                    },
                )
                summary["context_count"] = int(summary["context_count"]) + 1
                summary["realized_count"] = int(summary["realized_count"]) + int(row["family_selected_count"])
                policy_mass = _finite_or_none(row.get("policy_mass"))
                expected_values = summary["expected_values"]
                assert isinstance(expected_values, list)
                if policy_mass is None:
                    summary["missing_probability_count"] = int(summary["missing_probability_count"]) + 1
                else:
                    expected_values.append(policy_mass)

    output: list[dict[str, Any]] = []
    for key, summary in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        expected = np.asarray(summary["expected_values"], dtype=np.float64)
        q25, median, q75 = (
            (None, None, None)
            if not expected.size
            else tuple(
                float(value) for value in np.quantile(np.sort(expected), (0.25, 0.5, 0.75), method="linear").tolist()
            )
        )
        if pool_temperatures:
            group_by, policy, horizon, branch_factor, beam_width, step_index, previous_family, next_family = key
            cohort_id = None
            cohort = None
            temperature = None
        else:
            (
                group_by,
                cohort_id,
                cohort,
                policy,
                temperature,
                horizon,
                branch_factor,
                beam_width,
                step_index,
                previous_family,
                next_family,
            ) = key
        context_count = int(summary["context_count"])
        output.append(
            {
                "group_by": group_by,
                "generation_cohort_id": cohort_id,
                "generation_cohort": cohort,
                "policy": policy,
                "temperature": temperature,
                "pooled_temperatures": pool_temperatures,
                "horizon": horizon,
                "branch_factor": branch_factor,
                "beam_width": beam_width,
                "step_index": step_index,
                "previous_family": previous_family,
                "next_family": next_family,
                "context_count": context_count,
                "expected_finite_count": int(expected.size),
                "expected_missing_count": int(summary["missing_probability_count"]),
                "expected_policy_mass_mean": None if not expected.size else float(np.mean(expected)),
                "expected_policy_mass_median": median,
                "expected_policy_mass_q25": q25,
                "expected_policy_mass_q75": q75,
                "realized_count": int(summary["realized_count"]),
                "realized_rate": _safe_fraction(int(summary["realized_count"]), context_count),
            }
        )
    return output


def candidate_selection_temporal_summary_rows(
    dynamics_rows: Iterable[Mapping[str, Any]],
    *,
    metric: str,
) -> list[dict[str, Any]]:
    """Summarize one state-level candidate-family quantity over factual depth."""

    if metric not in _CANDIDATE_SELECTION_TEMPORAL_METRICS:
        raise ValueError(
            f"Unsupported candidate selection metric {metric!r}; "
            f"expected one of {_CANDIDATE_SELECTION_TEMPORAL_METRICS}."
        )
    grouped: dict[tuple[Any, ...], list[Any]] = {}
    for source_row in dynamics_rows:
        row = dict(source_row)
        step_index = row.get("step_index")
        if step_index is None:
            raise ValueError("Candidate selection summaries require factual step_index values.")
        key = (
            row.get("group_by"),
            row.get("generation_cohort_id"),
            row.get("generation_cohort"),
            row.get("policy"),
            row.get("temperature"),
            row.get("horizon"),
            row.get("branch_factor"),
            row.get("beam_width"),
            int(step_index),
            row.get("family"),
        )
        grouped.setdefault(key, []).append(row.get(metric))
    output: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        finite = np.asarray(
            [value for value in (_finite_or_none(value) for value in values) if value is not None],
            dtype=np.float64,
        )
        q25, median, q75 = (
            (None, None, None)
            if not finite.size
            else tuple(
                float(value) for value in np.quantile(np.sort(finite), (0.25, 0.5, 0.75), method="linear").tolist()
            )
        )
        (
            group_by,
            cohort_id,
            cohort,
            policy,
            temperature,
            horizon,
            branch_factor,
            beam_width,
            step_index,
            family,
        ) = key
        output.append(
            {
                "metric": metric,
                "group_by": group_by,
                "generation_cohort_id": cohort_id,
                "generation_cohort": cohort,
                "policy": policy,
                "temperature": temperature,
                "horizon": horizon,
                "branch_factor": branch_factor,
                "beam_width": beam_width,
                "step_index": step_index,
                "family": family,
                "total_count": len(values),
                "finite_count": int(finite.size),
                "missing_count": len(values) - int(finite.size),
                "mean": None if not finite.size else float(np.mean(finite)),
                "median": median,
                "q25": q25,
                "q75": q75,
            }
        )
    return output


def candidate_selection_pooled_summary_rows(
    dynamics_rows: Iterable[Mapping[str, Any]],
    *,
    metric: str,
) -> list[dict[str, Any]]:
    """Pool one compatible candidate-family fraction over factual trajectories.

    This is a sample-population view for one selected store. It deliberately
    omits temperature and exact generation-cohort identity while retaining
    policy, horizon, branch factor, and beam width as compatibility controls.
    Candidate and selected shares are recomputed from additive counts; policy
    mass is the equal-state mean of complete persisted probability vectors.
    """

    if metric not in _CANDIDATE_SELECTION_TEMPORAL_METRICS:
        raise ValueError(
            f"Unsupported candidate selection metric {metric!r}; "
            f"expected one of {_CANDIDATE_SELECTION_TEMPORAL_METRICS}."
        )
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in _materialize_selection_family_union(dynamics_rows):
        step_index = row.get("step_index")
        if step_index is None:
            raise ValueError("Candidate selection summaries require factual step_index values.")
        key = (
            row.get("group_by"),
            row.get("policy"),
            row.get("horizon"),
            row.get("branch_factor"),
            row.get("beam_width"),
            int(step_index),
            row.get("family"),
        )
        summary = grouped.setdefault(
            key,
            {
                "state_ids": set(),
                "numerator": 0,
                "denominator": 0,
                "policy_values": [],
                "policy_missing_count": 0,
            },
        )
        state_ids = summary["state_ids"]
        assert isinstance(state_ids, set)
        state_ids.add((row.get("generation_cohort_id"), row.get("rollout_row_id"), int(step_index)))
        if metric == "policy_mass":
            value = _finite_or_none(row.get("policy_mass"))
            if value is None:
                summary["policy_missing_count"] = int(summary["policy_missing_count"]) + 1
            else:
                values = summary["policy_values"]
                assert isinstance(values, list)
                values.append(value)
            continue
        numerator_field, denominator_field = {
            "allocation_share": ("family_candidate_count", "candidate_count"),
            "valid_share": ("family_actor_valid_count", "actor_valid_count"),
            "selected_share": ("family_selected_count", None),
        }[metric]
        summary["numerator"] = int(summary["numerator"]) + int(row[numerator_field])
        denominator = 1 if denominator_field is None else int(row[denominator_field])
        summary["denominator"] = int(summary["denominator"]) + denominator

    output: list[dict[str, Any]] = []
    for key, summary in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        group_by, policy, horizon, branch_factor, beam_width, step_index, family = key
        state_ids = summary["state_ids"]
        assert isinstance(state_ids, set)
        state_count = len(state_ids)
        if metric == "policy_mass":
            values = summary["policy_values"]
            assert isinstance(values, list)
            finite_count = len(values)
            fraction = None if not finite_count else float(np.mean(np.asarray(values, dtype=np.float64)))
            numerator = None
            denominator = None
        else:
            finite_count = state_count
            numerator = int(summary["numerator"])
            denominator = int(summary["denominator"])
            fraction = _safe_fraction(numerator, denominator)
        output.append(
            {
                "metric": metric,
                "group_by": group_by,
                "policy": policy,
                "horizon": horizon,
                "branch_factor": branch_factor,
                "beam_width": beam_width,
                "step_index": step_index,
                "family": family,
                "state_count": state_count,
                "finite_state_count": finite_count,
                "missing_state_count": state_count - finite_count,
                "numerator": numerator,
                "denominator": denominator,
                "fraction": fraction,
            }
        )
    return output


def candidate_selection_sequence_rows(
    dynamics_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one selected-family sequence and terminal gain per factual rollout."""

    rows = [dict(row) for row in dynamics_rows]
    by_rollout: dict[tuple[str, int], dict[int, list[dict[str, Any]]]] = {}
    for row in rows:
        rollout_row_id = row.get("rollout_row_id")
        step_index = row.get("step_index")
        if rollout_row_id is None or step_index is None:
            raise ValueError("Selection dynamics require rollout_row_id and step_index.")
        key = (str(row.get("generation_cohort_id", "unknown")), int(rollout_row_id))
        by_rollout.setdefault(key, {}).setdefault(int(step_index), []).append(row)

    output: list[dict[str, Any]] = []
    for (cohort_id, rollout_row_id), steps in sorted(by_rollout.items()):
        indices = sorted(steps)
        if indices != list(range(len(indices))):
            raise ValueError(f"Selection sequences require contiguous zero-based factual steps; received {indices}.")
        selected_sequence: list[str] = []
        for step_index in indices:
            selected = [str(row["family"]) for row in steps[step_index] if int(row["family_selected_count"]) == 1]
            if len(selected) != 1:
                raise ValueError("Each factual selection state must identify exactly one selected family.")
            selected_sequence.append(selected[0])
        terminal = steps[indices[-1]][0]
        horizon = int(terminal.get("horizon") or len(indices))
        output.append(
            {
                "group_by": terminal.get("group_by"),
                "generation_cohort_id": cohort_id,
                "generation_cohort": terminal.get("generation_cohort"),
                "scene": terminal.get("scene"),
                "rollout_row_id": rollout_row_id,
                "policy": terminal.get("policy"),
                "temperature": terminal.get("temperature"),
                "horizon": horizon,
                "branch_factor": terminal.get("branch_factor"),
                "beam_width": terminal.get("beam_width"),
                "observed_steps": len(indices),
                "completed_horizon": len(indices) == horizon,
                "sequence": " → ".join(selected_sequence),
                "sequence_families": tuple(selected_sequence),
                "terminal_cumulative_target_root_gain": _finite_or_none(terminal.get("cumulative_target_root_gain")),
            }
        )
    return output


def candidate_sequence_return_summary_rows(
    sequence_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize terminal return by exact selected-family sequence."""

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for source_row in sequence_rows:
        row = dict(source_row)
        key = (
            row.get("group_by"),
            row.get("generation_cohort_id"),
            row.get("generation_cohort"),
            row.get("policy"),
            row.get("temperature"),
            row.get("horizon"),
            row.get("branch_factor"),
            row.get("beam_width"),
            row.get("sequence"),
        )
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        gains = np.asarray(
            [
                value
                for row in rows
                if (value := _finite_or_none(row.get("terminal_cumulative_target_root_gain"))) is not None
            ],
            dtype=np.float64,
        )
        q25, median, q75 = (
            (None, None, None)
            if not gains.size
            else tuple(
                float(value) for value in np.quantile(np.sort(gains), (0.25, 0.5, 0.75), method="linear").tolist()
            )
        )
        (
            group_by,
            cohort_id,
            cohort,
            policy,
            temperature,
            horizon,
            branch_factor,
            beam_width,
            sequence,
        ) = key
        output.append(
            {
                "group_by": group_by,
                "generation_cohort_id": cohort_id,
                "generation_cohort": cohort,
                "policy": policy,
                "temperature": temperature,
                "horizon": horizon,
                "branch_factor": branch_factor,
                "beam_width": beam_width,
                "sequence": sequence,
                "rollout_count": len(rows),
                "completed_count": sum(bool(row.get("completed_horizon")) for row in rows),
                "finite_return_count": int(gains.size),
                "terminal_return_mean": None if not gains.size else float(np.mean(gains)),
                "terminal_return_median": median,
                "terminal_return_q25": q25,
                "terminal_return_q75": q75,
            }
        )
    return output


def temporal_metric_summary_rows(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
    *,
    metric: str,
    group_fields: Iterable[str] = (),
) -> list[dict[str, Any]]:
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

    source_rows = rollout_step_objective_rows(source) if isinstance(source, RolloutZarrStoreReader) else list(source)
    value_field, units = _TEMPORAL_METRICS[metric]
    grouped: dict[tuple[Any, ...], list[Any]] = {}
    for source_row in source_rows:
        row = dict(source_row)
        step_index = row.get("step_index")
        if step_index is None:
            raise ValueError("Temporal source rows require an explicit step_index.")
        key = (*(_temporal_group_value(row, field) for field in groups), int(step_index))
        grouped.setdefault(key, []).append(row.get(value_field))

    output: list[dict[str, Any]] = []
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
        row_output: dict[str, Any] = {
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
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
    *,
    metric: str,
) -> dict[str, Any]:
    """Summarize one terminal factual step per rollout for a metric.

    Each rollout contributes exactly its greatest persisted ``step_index``;
    shorter factual chains are therefore retained. Statistics use finite
    terminal values only, while the denominator counts every rollout endpoint.
    """

    if metric not in _TEMPORAL_METRICS:
        raise ValueError(f"Unsupported temporal metric {metric!r}; expected one of {sorted(_TEMPORAL_METRICS)}.")
    source_rows = rollout_step_objective_rows(source) if isinstance(source, RolloutZarrStoreReader) else list(source)
    value_field, units = _TEMPORAL_METRICS[metric]
    endpoints: dict[int, tuple[int, int, Any]] = {}
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
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize the fixed factual reconstruction and selection metric plan."""

    source_rows = (
        rollout_step_objective_rows(source)
        if isinstance(source, RolloutZarrStoreReader)
        else [dict(row) for row in source]
    )
    rollout_count = len({int(row["rollout_row_id"]) for row in source_rows if row.get("rollout_row_id") is not None})
    endpoints = reconstruction_endpoint_rows(source_rows)
    output: list[dict[str, Any]] = []
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
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one greatest persisted factual step per rollout."""

    source_rows = (
        rollout_step_objective_rows(source)
        if isinstance(source, RolloutZarrStoreReader)
        else [dict(row) for row in source]
    )
    endpoints: dict[int, tuple[int, int, dict[str, Any]]] = {}
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
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
    *,
    group_fields: Iterable[str] = ("policy", "horizon"),
) -> list[dict[str, Any]]:
    """Summarize factual endpoints over supported exact display strata."""

    groups = tuple(group_fields)
    unsupported = tuple(field for field in groups if field not in {"policy", "horizon", "scene"})
    if unsupported:
        raise ValueError(f"Unsupported endpoint group field(s): {unsupported!r}.")
    endpoints = reconstruction_endpoint_rows(source)
    output: list[dict[str, Any]] = []
    for family, metric, label in _RECONSTRUCTION_METRIC_SPECS:
        grouped: dict[tuple[Any, ...], list[Any]] = {}
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
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
    *,
    return_semantics: Any,
    discount_gamma: Any,
) -> dict[str, Any]:
    """Derive discounted factual selected gain under the persisted contract."""

    if return_semantics != "cumulative_target_root_gain":
        return {"available": False, "reason": f"unsupported return_semantics={return_semantics!r}", "rows": []}
    gamma = _finite_or_none(discount_gamma)
    if gamma is None or gamma < 0.0 or gamma > 1.0:
        return {"available": False, "reason": f"invalid discount_gamma={discount_gamma!r}", "rows": []}
    source_rows = (
        rollout_step_objective_rows(source)
        if isinstance(source, RolloutZarrStoreReader)
        else [dict(row) for row in source]
    )
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in source_rows:
        if row.get("rollout_row_id") is not None:
            grouped.setdefault(int(row["rollout_row_id"]), []).append(row)
    output: list[dict[str, Any]] = []
    for rollout_row_id, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: int(row["step_index"]))
        rewards = [_finite_or_none(row.get("selected_target_root_gain")) for row in ordered]
        discounted = (
            None
            if any(reward is None for reward in rewards)
            else float(sum((gamma**index) * reward for index, reward in enumerate(cast(list[float], rewards))))
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


def exact_policy_role_rows(cohort_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Attach roles from exact persisted pairs without dropping unknown rows."""

    output: list[dict[str, Any]] = []
    for raw_row_id, source_row in enumerate(cohort_rows):
        row = dict(source_row)
        identifier = (str(row.get("policy", "")), str(row.get("branch_schedule", "")))
        role = _EXACT_POLICY_ROLE_IDENTIFIERS.get(identifier)
        output.append(
            {
                **row,
                "raw_row_id": raw_row_id,
                "semantic_role": role,
                "role_identifier": f"{identifier[0]} / {identifier[1]}",
            }
        )
    return output


def oracle_headroom_evidence(
    source: RolloutZarrStoreReader | Iterable[Mapping[str, Any]],
    *,
    threshold: float = 1e-8,
) -> dict[str, Any]:
    """Return exact-role diagnostic endpoint contrasts with honest exclusions."""

    if threshold <= 0.0:
        raise ValueError("threshold must be positive.")
    if callable(getattr(source, "array", None)):
        source_rows = _policy_cohort_projection_rows(cast(RolloutZarrStoreReader, source))
    else:
        source_rows = [dict(row) for row in cast(Iterable[Mapping[str, Any]], source)]
    role_rows = exact_policy_role_rows(source_rows)
    grouped: dict[str, list[dict[str, Any]]] = {}
    malformed_rows: list[dict[str, Any]] = []
    for row in role_rows:
        if row.get("semantic_role") is None:
            malformed_rows.append(
                {
                    **row,
                    "exclusion_reason": "unsupported_role_identifier",
                }
            )
            continue
        required_fields = list(_HEADROOM_INVARIANT_FIELDS[:10])
        campaign_fields = _HEADROOM_INVARIANT_FIELDS[10:]
        if any(not _missing_identity(row.get(field)) for field in campaign_fields):
            required_fields.extend(campaign_fields)
        missing = tuple(field for field in required_fields if _missing_identity(row.get(field)))
        if missing:
            malformed_rows.append(
                {
                    **row,
                    "exclusion_reason": f"identity_mismatch:{','.join(missing)}",
                }
            )
            continue
        key_payload = {field: row.get(field) for field in _HEADROOM_INVARIANT_FIELDS}
        invariant_key = json.dumps(key_payload, sort_keys=True, separators=(",", ":"))
        row.update({"headroom_invariant_key": invariant_key, "evidence_status": "eligible", "exclusion_reason": None})
        grouped.setdefault(invariant_key, []).append(row)

    malformed_by_id = {int(row["raw_row_id"]): row for row in malformed_rows}
    for row in role_rows:
        malformed = malformed_by_id.get(int(row["raw_row_id"]))
        if malformed is not None:
            row.update({"evidence_status": "excluded", "exclusion_reason": malformed["exclusion_reason"]})

    contrast_specs = {
        "delta_look": ("oracle_one_step", "oracle_lookahead"),
        "delta_Q": ("learned_one_step", "q_h"),
        "eta_Q": ("learned_one_step", "q_h", "oracle_lookahead"),
    }
    contrast_rows: list[dict[str, Any]] = []
    role_disposition_rows: list[dict[str, Any]] = []
    for invariant_key, rows in sorted(grouped.items()):
        by_role: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_role.setdefault(str(row["semantic_role"]), []).append(row)
        for contrast, roles in contrast_specs.items():
            reason: str | None = None
            selected: dict[str, dict[str, Any]] = {}
            for role in roles:
                matches = by_role.get(role, [])
                if not matches:
                    reason = f"missing_role:{role}"
                    break
                if len(matches) != 1:
                    reason = f"duplicate_role:{role}"
                    break
                selected[role] = matches[0]
            normalized_conditions: dict[str, dict[str, Any]] = {}
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
                    endpoint_value = _finite_or_none(row.get("final_cumulative_target_root_gain"))
                    if endpoint_value is None:
                        reason = f"nonfinite_endpoint:{role}"
                        break
                    values[role] = endpoint_value
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
            relevant_rows = [row for row in rows if row.get("semantic_role") in roles]
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
                    "raw_row_ids": [int(row["raw_row_id"]) for row in relevant_rows],
                }
            )
            selected_ids = {int(row["raw_row_id"]) for row in selected.values()}
            role_disposition_rows.extend(
                {
                    "raw_row_id": int(row["raw_row_id"]),
                    "contrast": contrast,
                    "status": (
                        "not_applicable"
                        if row.get("semantic_role") not in roles
                        else "included"
                        if reason is None and int(row["raw_row_id"]) in selected_ids
                        else "excluded"
                    ),
                    "exclusion_reason": None if row.get("semantic_role") not in roles or reason is None else reason,
                }
                for row in rows
            )
    malformed_cohorts: list[dict[str, Any]] = []
    for malformed in malformed_rows:
        malformed_cohorts.append(malformed)
    for malformed in malformed_cohorts:
        semantic_role = malformed.get("semantic_role")
        for contrast, roles in contrast_specs.items():
            disposition = "excluded" if semantic_role is None or semantic_role in roles else "not_applicable"
            if disposition == "not_applicable":
                role_disposition_rows.append(
                    {
                        "raw_row_id": int(malformed["raw_row_id"]),
                        "contrast": contrast,
                        "status": disposition,
                        "exclusion_reason": None,
                    }
                )
                continue
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
                    "raw_row_ids": [malformed.get("raw_row_id")],
                }
            )
            role_disposition_rows.append(
                {
                    "raw_row_id": int(malformed["raw_row_id"]),
                    "contrast": contrast,
                    "status": disposition,
                    "exclusion_reason": malformed["exclusion_reason"],
                }
            )
    dispositions_by_id: dict[int, list[dict[str, Any]]] = {}
    for disposition in role_disposition_rows:
        dispositions_by_id.setdefault(int(disposition["raw_row_id"]), []).append(disposition)
    for row in role_rows:
        dispositions = dispositions_by_id[int(row["raw_row_id"])]
        if any(item["status"] == "included" for item in dispositions):
            row["evidence_status"] = "included"
            row["exclusion_reason"] = None
        elif any(item["status"] == "excluded" for item in dispositions):
            row["evidence_status"] = "excluded"
            row["exclusion_reason"] = next(
                item["exclusion_reason"] for item in dispositions if item["status"] == "excluded"
            )
        else:
            row["evidence_status"] = "not_applicable"
            row["exclusion_reason"] = None
    summary_rows: list[dict[str, Any]] = []
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
        "role_disposition_rows": role_disposition_rows,
        "contrast_rows": contrast_rows,
        "summary_rows": summary_rows,
    }


def _missing_identity(value: Any) -> bool:
    return value is None or value == ""


def _headroom_condition(
    row: Mapping[str, Any],
    field: str,
    *,
    missing_value: int,
) -> tuple[Any, bool]:
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
) -> list[dict[str, Any]]:
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

    rows: list[dict[str, Any]] = []
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
    audit_rows: Iterable[Mapping[str, Any]],
    *,
    group_by: CandidateGroupField = "mixture",
) -> list[dict[str, Any]]:
    """Macro-summarize candidate populations without pooling decision states.

    ``audit_rows`` must be the one materialized :func:`candidate_audit_rows`
    projection for a validated store.  Counts remain exact; rates are first
    averaged within a state, then within a scene, then equally across scenes.
    """
    if group_by not in CANDIDATE_GROUP_FIELDS:
        raise ValueError(f"Unsupported candidate group field {group_by!r}; expected one of {CANDIDATE_GROUP_FIELDS}.")
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for source_row in audit_rows:
        row = dict(source_row)
        cohort_id = str(row.get("generation_cohort_id", "unknown"))
        family = str(row.get(group_by, "unknown"))
        state = f"{row.get('scene', 'unknown')}\0{row.get('rollout_row_id', 'unknown')}\0{row.get('step_row_id', 'unknown')}"
        grouped.setdefault((cohort_id, family, state), []).append(row)
    per_family: dict[tuple[str, str], list[dict[str, Any]]] = {}
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
    output: list[dict[str, Any]] = []
    for (cohort_id, family), states in sorted(per_family.items()):
        scenes: dict[str, list[dict[str, Any]]] = {}
        for state in states:
            scenes.setdefault(str(state["scene"]), []).append(state)
        scene_rates: list[dict[str, Any]] = []
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
    audit_rows: Iterable[Mapping[str, Any]],
    *,
    group_by: CandidateGroupField = "mixture",
) -> list[dict[str, Any]]:
    """Compare proposal mass and selected share inside exact decision states."""
    rows = [dict(row) for row in audit_rows]
    composition = candidate_composition_rows(rows, group_by=group_by)
    by_family: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("generation_cohort_id", "unknown")), str(row.get(group_by, "unknown")))
        by_family.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
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
            state_error = _probability_state_error(
                {
                    "total": len(normalized),
                    "finite_probability_count": sum(value is not None for value in normalized),
                    "missing": any(value is None for value in normalized),
                    "negative": any(float(value) < 0.0 for value in normalized if value is not None),
                    "probability_sum": sum(float(value) for value in normalized if value is not None),
                }
            )
            if state_error is not None:
                probability_error = f"{state_error}:{state_key}"
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
                else selected_share / cast(float, empirical),
                "state_count": len(state_rows),
                "scene_count": len(scene_rows),
                "empirical_frequency": macro["empirical_frequency"],
                "proposal_mass": None if probability_error is not None else macro["proposal_mass"],
                "calibration_gap": (
                    None
                    if probability_error is not None
                    or macro["proposal_mass"] is None
                    or macro["empirical_frequency"] is None
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


def _group_candidate_states(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    """Group candidate rows by one persisted decision state for validation."""

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for source_row in rows:
        row = dict(source_row)
        key = (row.get("rollout_row_id"), row.get("step_row_id"))
        grouped.setdefault(key, []).append(row)
    return grouped


def candidate_collision_support_rows(audit_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Expose cohort-preserving collision and clearance availability.

    Counts remain exact populations. Rates are additionally reported as a
    state-then-scene macro so uneven candidate fan-out cannot dominate the
    descriptive comparison.
    """
    rows = [dict(row) for row in audit_rows]
    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cohort.setdefault(str(row.get("generation_cohort_id", "unknown")), []).append(row)
    output: list[dict[str, Any]] = []
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
                "collision_unavailable_count": sum(
                    not _collision_evaluated(row) and row.get("path_collision_applicable") is not False
                    for row in cohort_rows
                ),
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


def _collision_evaluated(row: Mapping[str, Any]) -> bool:
    """Read only explicit collision-evaluation evidence."""

    return row.get("path_collision_evaluated") is True


def _candidate_state_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for source_row in rows:
        row = dict(source_row)
        key = (
            str(row.get("scene", "unknown")),
            str(row.get("rollout_row_id", "unknown")),
            str(row.get("step_row_id", "unknown")),
        )
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
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
    family_rows: Iterable[Mapping[str, Any]], cohort_rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    state_keys = {
        (
            str(row.get("scene", "unknown")),
            str(row.get("rollout_row_id", "unknown")),
            str(row.get("step_row_id", "unknown")),
        )
        for row in cohort_rows
    }
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
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
    family_grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
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
    output: list[dict[str, Any]] = []
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
                    None
                    if empirical is None or empirical == 0.0 or selected_share is None
                    else selected_share / empirical
                ),
            }
        )
    return output


def _candidate_scene_macro_rows(state_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
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


def _macro_mean(rows: Iterable[Mapping[str, Any]], field: str) -> float | None:
    values = [_finite_or_none(row.get(field)) for row in rows]
    finite = [value for value in values if value is not None]
    return None if not finite else float(np.mean(finite))


def deterministic_candidate_display_sample(
    audit_rows: Iterable[Mapping[str, Any]],
    *,
    max_rows: int = 500,
    seed: str = "stored-rollout-display-v1",
) -> dict[str, Any]:
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
    state_row_limit: int | None = None,
    progress_callback: Callable[[int, int], bool] | None = None,
    validation_result: RolloutZarrValidationResult | None = None,
) -> list[dict[str, Any]]:
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
    row: dict[str, Any] = {
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
        "counted_state_rows": None,
        "total_state_rows": _nonnegative_int(q_h["candidate_row_id"].shape[0]),
        "truncated": None,
        "count_reason": "metadata does not prove mask counts; request deep_count",
    }
    if deep_count:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if state_row_limit is not None and state_row_limit < 0:
            raise ValueError("state_row_limit must be non-negative or None")
        candidate_ids_array = q_h["candidate_row_id"]
        valid_array = q_h["valid_action_mask"]
        trainable_array = q_h["q_train_mask"]
        actor_count = oracle_count = trainable_count = padding_count = 0
        cancelled = False
        factual_ids_array = reader.array("candidates/candidate_row_id")
        factual_oracle_array = reader.array("candidates/oracle_label_mask")
        try:
            _validate_monotonic_array_chunks(factual_ids_array, chunk_size=chunk_size)
        except ValueError as error:
            row.update(
                {
                    "available": False,
                    "blocking_reason": str(error),
                    "count_reason": "factual candidate IDs are not monotonic",
                }
            )
            return [row]
        available_state_rows = int(candidate_ids_array.shape[0])
        requested_state_rows = available_state_rows
        if state_row_limit is not None:
            requested_state_rows = min(available_state_rows, int(state_row_limit))
        counted_state_rows = 0
        for start in range(0, requested_state_rows, chunk_size):
            stop = min(start + chunk_size, requested_state_rows)
            candidate_ids = np.asarray(candidate_ids_array[start:stop], dtype=np.int64)
            valid = np.asarray(valid_array[start:stop], dtype=np.bool_)
            trainable = np.asarray(trainable_array[start:stop], dtype=np.bool_)
            oracle_count += _bounded_candidate_oracle_matches(
                candidate_ids,
                factual_ids_array,
                factual_oracle_array,
                chunk_size=chunk_size,
            )
            actor_count += int(valid.sum())
            trainable_count += int(trainable.sum())
            padding_count += int((candidate_ids < 0).sum())
            counted_state_rows = stop
            if progress_callback is not None and not progress_callback(stop, requested_state_rows):
                cancelled = True
                break
        row.update(
            {
                "actor_valid_count": actor_count,
                "oracle_valid_count": oracle_count,
                "trainable_count": trainable_count,
                "padding_count": padding_count,
                "counted_state_rows": counted_state_rows,
                "total_state_rows": available_state_rows,
                "truncated": counted_state_rows < available_state_rows,
                "count_reason": (
                    "cancelled during bounded current-store mask projection"
                    if cancelled
                    else "explicit bounded-prefix current-store mask projection"
                    if counted_state_rows < available_state_rows
                    else "explicit complete current-store mask projection"
                ),
            }
        )
    return [row]


def _bounded_candidate_oracle_matches(
    q_h_candidate_ids: np.ndarray,
    factual_ids_array: Any,
    factual_oracle_array: Any,
    *,
    chunk_size: int,
) -> int:
    """Join Q_H IDs to factual oracle masks without whole-array materialization."""

    query = q_h_candidate_ids.reshape(-1)
    query = query[query >= 0]
    if not query.size:
        return 0
    matched = 0
    factual_count = int(factual_ids_array.shape[0])
    for start in range(0, factual_count, chunk_size):
        stop = min(start + chunk_size, factual_count)
        factual_ids = np.asarray(factual_ids_array[start:stop], dtype=np.int64).reshape(-1)
        factual_oracle = np.asarray(factual_oracle_array[start:stop], dtype=np.bool_).reshape(-1)
        if factual_ids.size == 0:
            continue
        positions = np.searchsorted(factual_ids, query)
        valid = positions < factual_ids.size
        if valid.any():
            valid_positions = positions[valid]
            equal = factual_ids[valid_positions] == query[valid]
            matched += int(factual_oracle[valid_positions[equal]].sum())
    return matched


def _validate_monotonic_array_chunks(array: Any, *, chunk_size: int) -> None:
    """Reject factual candidate IDs that cannot be joined by bounded search."""

    previous: int | None = None
    for start in range(0, int(array.shape[0]), chunk_size):
        values = np.asarray(array[start : min(start + chunk_size, int(array.shape[0]))], dtype=np.int64).reshape(-1)
        if values.size == 0:
            continue
        if np.any(np.diff(values) < 0) or (previous is not None and int(values[0]) < previous):
            raise ValueError("factual candidate IDs must be monotonic for bounded Q_H join")
        previous = int(values[-1])


def target_audit_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
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


def validity_waterfall_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
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


def mask_combination_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
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
    rows: list[dict[str, Any]] = []
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
) -> list[dict[str, Any]]:
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
    audit_rows: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
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

    output: list[dict[str, Any]] = []
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


def comparable_policy_cohorts(reader: RolloutZarrStoreReader) -> dict[str, Any]:
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
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["cohort_key"]), []).append(row)

    cohort_summaries: list[dict[str, Any]] = []
    eligible_summaries: list[dict[str, Any]] = []
    for cohort_key, cohort_rows in sorted(grouped.items()):
        by_label: dict[str, list[dict[str, Any]]] = {}
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
) -> list[dict[str, Any]]:
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
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in projection["cohort_rows"]:
        cohort_key = str(row["cohort_key"])
        if cohort_key not in eligible_keys:
            continue
        grouped.setdefault(cohort_key, {})[str(row["comparison_label"])] = row

    output: list[dict[str, Any]] = []
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
) -> list[dict[str, Any]]:
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

    rows: list[dict[str, Any]] = []
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
) -> list[dict[str, Any]]:
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

    rows: list[dict[str, Any]] = []
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
) -> list[dict[str, Any]]:
    """Return per-step objective, branching, and selected-action audit rows."""
    rows: list[dict[str, Any]] = []
    rollout_count = int(np.asarray(reader.array("rollouts/rollout_row_id")).size)
    candidate_configs = _decoded_array(reader, "lineage/candidate_config_id", "config")
    rollout_configs = _decoded_array(reader, "lineage/rollout_config_id", "config")
    branch_schedules = _decoded_array(reader, "lineage/branch_schedule_id", "config")
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if rollout_row_id is not None and rollout.rollout_row_id != int(rollout_row_id):
            continue
        generation_cohort_id, cohort_json = _generation_cohort_identity(
            rollout,
            candidate_config=candidate_configs[rollout_position],
            rollout_config=rollout_configs[rollout_position],
            branch_schedule=branch_schedules[rollout_position],
        )
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
                    "generation_cohort_id": generation_cohort_id,
                    "generation_cohort": cohort_json,
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


def rollout_tree_summary_rows(
    reader: RolloutZarrStoreReader,
    *,
    step_rows: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Summarize selected rollout-tree provenance by policy, step, and family.

    Rollout stores persist factual selected chains, not a full parent-edge tree.
    This helper therefore reports the observed branching/provenance distribution
    across selected steps: policy/recipe parameters, candidate family, fanout,
    invalidity, and selected objective values.

    Args:
        reader: Read-only rollout-store adapter used when ``step_rows`` is not
            supplied.
        step_rows: Optional already-materialized rows from
            :func:`rollout_step_objective_rows`. Reusing the exact projection
            avoids a duplicate rollout-store traversal in report builders.
    """

    metric_sources = {
        "valid_fanout": "num_valid_candidates",
        "invalid_fraction": "invalid_fraction",
        "marginal_target_rri": "marginal_target_rri",
        "selected_target_root_gain": "selected_target_root_gain",
        "selected_probability": "selected_probability",
        "selected_entropy": "selected_entropy",
    }
    groups: dict[tuple[Any, ...], dict[str, float]] = {}
    source_rows = rollout_step_objective_rows(reader) if step_rows is None else step_rows
    for row in source_rows:
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

    output: list[dict[str, Any]] = []
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
) -> list[dict[str, Any]]:
    """Return bounded summaries for persisted selected-action depth rasters.

    Dense selected-depth arrays are intentionally read only for the filtered
    step rows. The default limit keeps app and CLI inspections from scanning a
    production store by accident.
    """

    rows: list[dict[str, Any]] = []
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
            row: dict[str, Any] = dict.fromkeys(
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
) -> dict[str, Any]:
    """Return one downsampled selected-depth payload for Plotly app previews."""

    matches: list[Any] = []
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


def candidate_result_diagnostic_counts(candidates: Any) -> dict[str, list[dict[str, Any]]]:
    """Return live `CandidateSamplingResult` counts by position and invalid reason."""

    valid = candidates.mask_valid.detach().cpu().numpy().reshape(-1).astype(bool, copy=False)
    position_values = getattr(candidates, "position_id", None)
    position_rows: list[dict[str, Any]] = []
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
    invalid_rows: list[dict[str, Any]] = []
    for value in sorted(np.unique(primary_np[~valid]).tolist()):
        mask = (~valid) & (primary_np == int(value))
        invalid_rows.append({"invalid_reason": decode_invalid_reason(int(value)), "count": int(mask.sum())})
    return {"position": position_rows, "invalid_reason": invalid_rows}


def suspicious_rollout_rows(
    reader: RolloutZarrStoreReader,
    *,
    config: RolloutSuspiciousQueryConfig | None = None,
) -> list[dict[str, Any]]:
    """Return heuristic anomaly rows for rollout-store QA triage."""

    cfg = config or RolloutSuspiciousQueryConfig()
    rows: list[dict[str, Any]] = []
    rows.extend(_mask_violation_rows(reader))
    rows.extend(_low_fanout_rows(reader, cfg))
    rows.extend(_dominant_invalid_reason_rows(reader, cfg))
    rows.extend(_missing_label_rows(reader))
    rows.extend(_high_score_invalid_target_rows(reader, cfg))
    rows.extend(_target_ambiguity_rows(reader))
    rows.extend(_selected_motion_outlier_rows(reader, cfg))
    rows.extend(_selected_depth_health_rows(reader))
    return rows


def _mask_violation_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
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
    rows: list[dict[str, Any]] = []
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


def _target_ambiguity_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
    """Return persisted target-match ambiguity without treating it as low reward."""

    rows: list[dict[str, Any]] = []
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


def _selected_depth_health_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
    """Return selected-depth linkage or finite-pixel failures when depth is enabled."""

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return []
    rows: list[dict[str, Any]] = []
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


def _low_fanout_rows(reader: RolloutZarrStoreReader, cfg: RolloutSuspiciousQueryConfig) -> list[dict[str, Any]]:
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
) -> list[dict[str, Any]]:
    candidate_step_ids = np.asarray(reader.array("candidates/step_row_id"), dtype=np.int64).reshape(-1)
    step_ids = np.asarray(reader.array("steps/step_row_id"), dtype=np.int64).reshape(-1)
    rollout_ids = np.asarray(reader.array("steps/rollout_row_id"), dtype=np.int64).reshape(-1)
    valid = np.asarray(reader.array("candidates/actor_action_mask"), dtype=np.bool_).reshape(-1)
    primary = np.asarray(reader.array("candidates/primary_invalid_reason"), dtype=np.int64).reshape(-1)
    output: list[dict[str, Any]] = []
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


def _missing_label_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
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
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
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
) -> list[dict[str, Any]]:
    checks = (
        ("motion_step_length_m", cfg.max_step_distance_m, ">"),
        ("motion_height_delta_m", cfg.max_height_delta_m, "abs>"),
        ("motion_backward_step_m", cfg.max_backward_step_m, ">"),
        ("motion_yaw_delta_deg", cfg.max_yaw_delta_deg, "abs>"),
    )
    output: list[dict[str, Any]] = []
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


def _rollout_store_inventory_row(store_path: Path, *, validate: bool = True) -> dict[str, Any]:
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
    row: dict[str, Any] = {
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


def _store_stats(store_path: Path) -> dict[str, Any]:
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
) -> dict[str, Any]:
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


def _schema_manifest_invariant(root_attrs: dict[str, Any], manifest: Any) -> dict[str, Any]:
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


def _row_identity_invariant(reader: RolloutZarrStoreReader) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> list[dict[str, Any]]:
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


def _policy_cohort_projection_rows(reader: RolloutZarrStoreReader) -> list[dict[str, Any]]:
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
    termination_reasons = _decoded_array(reader, "rollouts/termination_reason", "termination_reason")
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

    rows: list[dict[str, Any]] = []
    for index, rollout_row_id in enumerate(rollout_ids.tolist()):
        source_key, source_index = source_by_id.get(int(source_ids[index]), (f"source_row:{source_ids[index]}", -1))
        row: dict[str, Any] = {
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
            "termination_reason": termination_reasons[index],
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


def _condition_applicable(*, field: str, policy: Any, recipe: Any) -> bool:
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
    rows: list[dict[str, Any]],
    labels: tuple[str, ...],
    grouped: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    by_label = {label: [row for row in rows if row["comparison_label"] == label] for label in labels}
    for left_label, right_label in combinations(labels, 2):
        exact_match = any(
            {str(row["comparison_label"]) for row in cohort_rows}.issuperset({left_label, right_label})
            for cohort_rows in grouped.values()
        )
        if exact_match:
            continue
        candidates: list[tuple[int, int, int, dict[str, Any], dict[str, Any], tuple[str, ...]]] = []
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
    lengths = np.zeros(rollout_ids.size, dtype=np.float64)
    if rollout_ids.size == 0:
        return lengths
    selected_positions = np.flatnonzero(selected)
    if selected_positions.size == 0:
        return lengths

    rollout_order = np.argsort(rollout_ids, kind="stable")
    sorted_rollout_ids = rollout_ids[rollout_order]
    selected_rollout_ids = candidate_rollout_ids[selected_positions]
    sorted_positions = np.searchsorted(sorted_rollout_ids, selected_rollout_ids)
    known_rollout = (sorted_positions < rollout_ids.size) & (
        sorted_rollout_ids[np.minimum(sorted_positions, rollout_ids.size - 1)] == selected_rollout_ids
    )
    selected_positions = selected_positions[known_rollout]
    if selected_positions.size == 0:
        return lengths

    rollout_positions = rollout_order[sorted_positions[known_rollout]]
    path_order = np.lexsort((selected_positions, candidate_steps[selected_positions], rollout_positions))
    selected_positions = selected_positions[path_order]
    rollout_positions = rollout_positions[path_order]
    centers = candidate_poses[selected_positions, 9:12]
    previous_centers = np.empty_like(centers)
    starts = np.empty(rollout_positions.size, dtype=np.bool_)
    starts[0] = True
    starts[1:] = rollout_positions[1:] != rollout_positions[:-1]
    previous_centers[starts] = root_pose[rollout_positions[starts], 9:12]
    previous_centers[~starts] = centers[:-1][~starts[1:]]
    segment_lengths = np.linalg.norm(centers - previous_centers, axis=1)
    np.add.at(lengths, rollout_positions, segment_lengths)
    return lengths


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
    components: list[Any] = []
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


def _temporal_group_value(row: Mapping[str, Any], field: str) -> Any:
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
    return cast(list[str], json.loads(encoded.tobytes().decode("utf-8")))


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


def _finite_or_none(value: Any) -> float | None:
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


def _nonnegative_int(*values: Any) -> int | None:
    for value in values:
        try:
            normalized = int(value)
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


_HEADROOM_TREATMENT_FIELDS = ("policy", "branch_schedule", "branch_factor", "beam_width", "rollout_recipe")
_GEOMETRY_EPSILON = 1e-8


class ProposalAlignment(StrEnum):
    """Yaw-only frame used to compare per-step candidate proposal support."""

    TARGET_ALIGNED_Z_UP = "target_aligned_z_up"
    RIG_FORWARD_Z_UP = "rig_forward_z_up"


@dataclass(frozen=True, slots=True)
class GeometryFrame:
    """One normalized Z-up frame used by a geometry projection."""

    frame_id: str
    rollout_row_id: int
    step_row_id: int | None
    step_index: int | None
    origin_kind: Literal["expansion_pose", "rollout_root"]
    expansion_pose_source: Literal["root", "previous_selected", "initial_root"]
    scale_kind: Literal["current_target_distance", "initial_target_distance"]
    alignment: str
    scale_m: float
    initial_scale_m: float
    target_x: float
    target_y: float
    target_z: float
    reference_axis_x: tuple[float, float, float]
    reference_axis_y: tuple[float, float, float]
    reference_axis_z: tuple[float, float, float]
    target_axis_x: tuple[float, float, float]
    target_axis_y: tuple[float, float, float]
    target_axis_z: tuple[float, float, float]
    rig_target_yaw_error_deg: float | None = None
    target_elevation_deg: float | None = None


@dataclass(frozen=True, slots=True)
class GeometryPoint:
    """One candidate or factual trajectory point in a normalized frame."""

    frame_id: str
    role: Literal["candidate", "root", "selected_action"]
    rollout_row_id: int
    step_row_id: int | None
    step_index: int | None
    candidate_row_id: int | None
    path_order: int | None
    actor_action: bool | None
    selected: bool
    position: str | None
    strategy: str | None
    mixture: str | None
    x: float
    y: float
    z: float
    displacement_m: float
    normalization_distance_m: float
    initial_target_distance_m: float
    normalized_radius: float = 0.0
    target_facing_error_deg: float | None = None


@dataclass(frozen=True, slots=True)
class GeometryIssue:
    """Explicit exclusion or truncation affecting a geometry projection."""

    code: str
    message: str
    rollout_row_id: int | None = None
    step_row_id: int | None = None


@dataclass(frozen=True, slots=True)
class GeometryProjection:
    """Presentation-free candidate geometry with auditable frames and issues."""

    view: Literal["proposal_support", "rollout_trajectory"]
    points: tuple[GeometryPoint, ...]
    frames: tuple[GeometryFrame, ...]
    issues: tuple[GeometryIssue, ...]
    truncated: bool = False

    def point_rows(self) -> list[dict[str, Any]]:
        """Return serializable point mappings for reporting and plotting clients."""

        return [asdict(point) for point in self.points]

    def frame_rows(self) -> list[dict[str, Any]]:
        """Return serializable frame mappings for anchor rendering clients."""

        return [asdict(frame) for frame in self.frames]


@dataclass(frozen=True, slots=True)
class S2DirectionHistogram:
    r"""Complete factual selected-action directions in target-object coordinates.

    The movement channel retains one selected transition per factual rollout
    step.  If ``p_{t-1}`` and ``p_t`` are camera centres in world metres, and
    ``R_W^e`` is the target-object-to-world rotation, the recorded direction is

    $$
    \widehat{\boldsymbol{\delta}}_{j,t}^e =
    \frac{(R_W^e)^\mathsf{T}(p_t-p_{t-1}) / r_e}
         {\lVert (R_W^e)^\mathsf{T}(p_t-p_{t-1}) / r_e \rVert_2},
    \qquad r_e=(a_x a_y a_z)^{1/3}.
    $$

    ``(a_x, a_y, a_z)`` are the target OBB semi-axis lengths, obtained by
    halving the persisted full extents.  Their geometric mean defines a
    geometric-mean semi-axis scale, so it does not privilege one OBB axis.  The
    final movement direction is scale invariant, but retaining ``r_e`` also
    exposes the dimensionless transition length used by target-relative
    translation descriptors.  View directions use the selected camera's local
    ``+Z`` optical axis, transformed by ``(R_W^e)^T`` and normalized in the
    same target frame.

    The frustum channel is different from the two direction channels.  It
    places the proxy surface point ``x^e=r_e d^e`` at every equal-area bin
    centre, transforms ``x^e-c_{j,t}^e`` into the selected camera, and tests
    the persisted pinhole image rectangle.  A bin contributes only when the
    proxy surface normal faces the camera and the projected point is in front
    of and inside the calibrated image.  Thus ``frustum_counts`` measures
    geometric field-of-view support on a target-centred proxy sphere whose
    radius is the geometric-mean semi-axis scale.  It is not occlusion-aware
    and must not be reported as measured
    target-mesh visibility.

    Here ``j`` identifies the factual rollout chain and ``t`` its zero-based
    persisted decision step.  The corresponding camera-forward direction is
    ``\widehat{\boldsymbol{v}}_{j,t}^e``.  Projection provenance retains both
    indices, so presentation clients can encode common rollout heritage by
    colour and common acquisition time by marker style without inferring
    either identity from array order.

    ``movement_counts`` and ``view_direction_counts`` have shape
    ``ndarray["Z A", int64]``.  ``Z`` bins target-frame ``z`` uniformly and
    ``A`` bins azimuth uniformly; because ``dΩ=dφ dz``, every cell has equal
    solid angle.  The two ``*_projection`` arrays are bounded, deterministic
    display samples only; the count arrays always include the complete factual
    selected-action population.
    """

    movement_counts: NDArray[np.int64]
    view_direction_counts: NDArray[np.int64]
    movement_projection: NDArray[np.float32]
    movement_projection_normalized_lengths: NDArray[np.float32]
    movement_projection_rollout_row_ids: NDArray[np.int64]
    movement_projection_step_indices: NDArray[np.int64]
    view_direction_projection: NDArray[np.float32]
    view_direction_projection_rollout_row_ids: NDArray[np.int64]
    view_direction_projection_step_indices: NDArray[np.int64]
    frustum_counts: NDArray[np.int64]
    frustum_projection: NDArray[np.float32]
    frustum_projection_rollout_row_ids: NDArray[np.int64]
    frustum_projection_step_indices: NDArray[np.int64]
    movement_count: int
    view_direction_count: int
    frustum_count: int
    frustum_missing_calibration_count: int
    frustum_mean_fov_solid_angle_sr: float | None
    frustum_mean_target_surface_fraction_approx: float | None
    frustum_union_target_surface_fraction_approx: float | None
    movement_skipped_zero_count: int
    rollout_count: int
    store_rollout_count: int
    source_sample_count: int
    source_snippet_count: int
    source_scene_count: int
    target_count: int
    selected_step_count: int
    azimuth_bins: int
    elevation_bins: int
    projection_limit: int
    issues: tuple[GeometryIssue, ...]


@dataclass(frozen=True, slots=True)
class _GeometryStep:
    """Bounded factual shell used by geometry projections.

    Unlike ``rollout_steps`` this helper never converts the complete candidate
    tables to NumPy.  The persisted selected-shell index and candidate id
    define one contiguous slice, which is the only payload materialized.
    """

    step_row_id: int
    step_index: int
    selected_candidate_row_id: int
    selected_local_index: int
    candidate_row_positions: NDArray[np.int64]
    candidate_row_ids: NDArray[np.int64]
    actor_action_mask: NDArray[np.bool_]
    selected_mask: NDArray[np.bool_]
    pose_world_cam: NDArray[np.float32]
    position_names: NDArray[np.str_]
    mixture_names: NDArray[np.str_]


@dataclass(frozen=True, slots=True)
class _SelectedFrustumCalibration:
    """Pinhole calibration aligned to one factual selected candidate."""

    candidate_row_id: int
    focal_px: NDArray[np.float64]
    principal_point_px: NDArray[np.float64]
    image_size_hw: tuple[int, int]


def _bounded_geometry_steps(reader: RolloutZarrStoreReader, rollout: StoredRollout) -> tuple[_GeometryStep, ...]:
    """Read only the candidate shells referenced by one factual rollout."""

    candidates = reader.root["candidates"]
    diagnostics = reader.root["candidate_diagnostics"]
    steps = reader.root["steps"]
    candidate_count = int(candidates["candidate_row_id"].shape[0])
    component_names: dict[int, str] = {}
    payload = reader.manifest().get("manifest", {}).get("generation", {}).get("writer_config", {})
    mixture = payload.get("candidate_mixture") if isinstance(payload, dict) else None
    components = mixture.get("components") if isinstance(mixture, dict) else None
    if isinstance(components, list):
        component_names = {
            index: str(component.get("name") or component.get("family") or component.get("position_mode"))
            for index, component in enumerate(components)
            if isinstance(component, dict)
            and (component.get("name") or component.get("family") or component.get("position_mode")) is not None
        }

    result: list[_GeometryStep] = []
    for step_position in rollout.step_row_positions.tolist():
        step_row_id = int(steps["step_row_id"][step_position])
        step_index = int(steps["step_index"][step_position])
        shell_size = int(steps["num_candidates"][step_position])
        selected_shell = int(steps["selected_shell_index"][step_position])
        selected_candidate = int(steps["selected_candidate_row_id"][step_position])
        start = selected_candidate - selected_shell
        stop = start + shell_size
        if start < 0 or stop > candidate_count:
            raise ValueError(f"Step row {step_row_id} references candidate rows outside the persisted shell.")
        positions = np.arange(start, stop, dtype=np.int64)
        candidate_ids = np.asarray(candidates["candidate_row_id"][start:stop], dtype=np.int64)
        if not np.array_equal(candidate_ids, np.arange(start, stop, dtype=np.int64)):
            raise ValueError(f"Step row {step_row_id} candidate ids are not contiguous with their physical rows.")
        step_ids = np.asarray(candidates["step_row_id"][start:stop], dtype=np.int64)
        if not np.all(step_ids == step_row_id):
            raise ValueError(f"Step row {step_row_id} candidate shell is interleaved with another factual step.")
        selected_mask = np.asarray(candidates["selected_mask"][start:stop], dtype=np.bool_)
        matches = np.flatnonzero(selected_mask)
        if matches.size != 1 or int(matches[0]) != selected_shell:
            raise ValueError(f"Step row {step_row_id} has an invalid selected-shell index.")
        position_ids = np.asarray(diagnostics["position_id"][start:stop], dtype=np.int32)
        mixture_ids = np.asarray(candidates["mixture_id"][start:stop], dtype=np.int32)
        result.append(
            _GeometryStep(
                step_row_id=step_row_id,
                step_index=step_index,
                selected_candidate_row_id=selected_candidate,
                selected_local_index=selected_shell,
                candidate_row_positions=positions,
                candidate_row_ids=candidate_ids,
                actor_action_mask=np.asarray(candidates["actor_action_mask"][start:stop], dtype=np.bool_),
                selected_mask=selected_mask,
                pose_world_cam=np.asarray(candidates["pose_world_cam"][start:stop], dtype=np.float32).reshape(-1, 12),
                position_names=np.asarray([decode_position_id(value) for value in position_ids], dtype=str),
                mixture_names=np.asarray(
                    [component_names.get(int(value), str(int(value))) for value in mixture_ids], dtype=str
                ),
            )
        )
    return tuple(result)


def proposal_support_geometry(
    reader: RolloutZarrStoreReader,
    *,
    alignment: ProposalAlignment = ProposalAlignment.TARGET_ALIGNED_Z_UP,
    rollout_row_ids: Collection[int] | None = None,
    max_candidates: int | None = 50_000,
) -> GeometryProjection:
    r"""Project complete candidate shells around their factual expansion poses.

    Step zero uses the persisted rollout root; later steps use the preceding
    factual selected pose. Coordinates are divided by that expansion pose's
    current 3D target distance, then yaw-aligned while preserving world Z-up.
    """

    requested_ids = None if rollout_row_ids is None else {int(value) for value in rollout_row_ids}
    if max_candidates is not None and max_candidates <= 0:
        raise ValueError("max_candidates must be positive when provided.")
    targets = {target.target_row_id: target for target in target_rows(reader)}
    strategy_ids = reader.root["candidates"]["strategy_id"]
    frames: list[GeometryFrame] = []
    points: list[GeometryPoint] = []
    issues: list[GeometryIssue] = []
    truncated = False
    rollout_count = int(reader.root["rollouts"]["rollout_row_id"].shape[0])
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if requested_ids is not None and rollout.rollout_row_id not in requested_ids:
            continue
        target = targets.get(rollout.target_row_id)
        if target is None:
            issues.append(
                GeometryIssue(
                    "missing_target",
                    "Rollout has no persisted observed-target geometry.",
                    rollout_row_id=rollout.rollout_row_id,
                )
            )
            continue
        root_pose = _geometry_pose(rollout.root_pose_world, role="rollout root")
        target_pose = _geometry_pose(target.pose_world_object, role="observed target")
        target_center = target_pose[9:12]
        initial_scale = _positive_distance(target_center - root_pose[9:12])
        if initial_scale is None:
            issues.append(
                GeometryIssue(
                    "invalid_initial_target_distance",
                    "Initial root-to-target distance is missing, non-finite, or zero.",
                    rollout_row_id=rollout.rollout_row_id,
                )
            )
            continue
        steps = _bounded_geometry_steps(reader, rollout)
        _validate_factual_steps(rollout.rollout_row_id, steps)
        reference_pose = root_pose
        for expected_index, step in enumerate(steps):
            selected_pose = _selected_pose(step)
            shell_size = len(step.candidate_row_ids)
            if max_candidates is not None and len(points) + shell_size > max_candidates:
                truncated = True
                issues.append(
                    GeometryIssue(
                        "candidate_limit_reached",
                        f"Stopped before a {shell_size}-row shell to preserve complete factual shells.",
                        rollout_row_id=rollout.rollout_row_id,
                        step_row_id=step.step_row_id,
                    )
                )
                return GeometryProjection("proposal_support", tuple(points), tuple(frames), tuple(issues), True)
            reference_center = reference_pose[9:12]
            scale = _positive_distance(target_center - reference_center)
            if scale is None:
                issues.append(
                    GeometryIssue(
                        "invalid_current_target_distance",
                        "Expansion-pose-to-target distance is missing, non-finite, or zero.",
                        rollout_row_id=rollout.rollout_row_id,
                        step_row_id=step.step_row_id,
                    )
                )
                reference_pose = selected_pose
                continue
            basis = _proposal_basis(reference_pose, target_center, alignment)
            if basis is None:
                issues.append(
                    GeometryIssue(
                        "degenerate_alignment",
                        f"{alignment.value} has no finite horizontal direction at this step.",
                        rollout_row_id=rollout.rollout_row_id,
                        step_row_id=step.step_row_id,
                    )
                )
                reference_pose = selected_pose
                continue
            frame_id = f"proposal:{rollout.rollout_row_id}:{step.step_row_id}:{alignment.value}"
            target_normalized = basis.T @ (target_center - reference_center) / scale
            frames.append(
                _geometry_frame(
                    frame_id=frame_id,
                    rollout_row_id=rollout.rollout_row_id,
                    step_row_id=step.step_row_id,
                    step_index=expected_index,
                    origin_kind="expansion_pose",
                    expansion_pose_source="root" if expected_index == 0 else "previous_selected",
                    scale_kind="current_target_distance",
                    alignment=alignment.value,
                    scale=scale,
                    initial_scale=initial_scale,
                    target_normalized=target_normalized,
                    reference_rotation=reference_pose[:9].reshape(3, 3),
                    target_rotation=target_pose[:9].reshape(3, 3),
                    basis=basis,
                )
            )
            for local, candidate_row_id in enumerate(step.candidate_row_ids.tolist()):
                candidate_pose = _geometry_pose(
                    step.pose_world_cam[local],
                    role=f"step {step.step_row_id} candidate {int(candidate_row_id)} pose",
                )
                candidate_center = candidate_pose[9:12]
                displacement = candidate_center - reference_center
                normalized = basis.T @ displacement / scale
                points.append(
                    GeometryPoint(
                        frame_id=frame_id,
                        role="candidate",
                        rollout_row_id=rollout.rollout_row_id,
                        step_row_id=step.step_row_id,
                        step_index=step.step_index,
                        candidate_row_id=int(candidate_row_id),
                        path_order=None,
                        actor_action=bool(step.actor_action_mask[local]),
                        selected=bool(step.selected_mask[local]),
                        position=str(step.position_names[local]),
                        strategy=decode_strategy_id(int(strategy_ids[int(step.candidate_row_positions[local])])),
                        mixture=str(step.mixture_names[local]),
                        x=float(normalized[0]),
                        y=float(normalized[1]),
                        z=float(normalized[2]),
                        displacement_m=float(np.linalg.norm(displacement)),
                        normalization_distance_m=scale,
                        initial_target_distance_m=initial_scale,
                        normalized_radius=float(np.linalg.norm(normalized)),
                        target_facing_error_deg=_target_facing_error_deg(candidate_pose, target_center),
                    )
                )
            reference_pose = selected_pose
    return GeometryProjection("proposal_support", tuple(points), tuple(frames), tuple(issues), truncated)


def rollout_trajectory_geometry(
    reader: RolloutZarrStoreReader,
    *,
    rollout_row_ids: Collection[int] | None = None,
) -> GeometryProjection:
    r"""Project factual selected trajectories in one initial target-aligned frame."""

    requested_ids = None if rollout_row_ids is None else {int(value) for value in rollout_row_ids}
    targets = {target.target_row_id: target for target in target_rows(reader)}
    strategy_ids = reader.root["candidates"]["strategy_id"]
    frames: list[GeometryFrame] = []
    points: list[GeometryPoint] = []
    issues: list[GeometryIssue] = []
    rollout_count = int(reader.root["rollouts"]["rollout_row_id"].shape[0])
    for rollout_position in range(rollout_count):
        rollout = rollout_at(reader, rollout_position)
        if requested_ids is not None and rollout.rollout_row_id not in requested_ids:
            continue
        target = targets.get(rollout.target_row_id)
        if target is None:
            issues.append(
                GeometryIssue(
                    "missing_target",
                    "Rollout has no persisted observed-target geometry.",
                    rollout_row_id=rollout.rollout_row_id,
                )
            )
            continue
        root_pose = _geometry_pose(rollout.root_pose_world, role="rollout root")
        target_pose = _geometry_pose(target.pose_world_object, role="observed target")
        target_center = target_pose[9:12]
        root_center = root_pose[9:12]
        scale = _positive_distance(target_center - root_center)
        basis = _target_aligned_basis(target_center - root_center)
        if scale is None or basis is None:
            issues.append(
                GeometryIssue(
                    "invalid_initial_target_frame",
                    "Initial target distance or horizontal target bearing is degenerate.",
                    rollout_row_id=rollout.rollout_row_id,
                )
            )
            continue
        steps = _bounded_geometry_steps(reader, rollout)
        _validate_factual_steps(rollout.rollout_row_id, steps)
        frame_id = f"trajectory:{rollout.rollout_row_id}:target_aligned_z_up"
        target_normalized = basis.T @ (target_center - root_center) / scale
        frames.append(
            _geometry_frame(
                frame_id=frame_id,
                rollout_row_id=rollout.rollout_row_id,
                step_row_id=None,
                step_index=None,
                origin_kind="rollout_root",
                expansion_pose_source="initial_root",
                scale_kind="initial_target_distance",
                alignment=ProposalAlignment.TARGET_ALIGNED_Z_UP.value,
                scale=scale,
                initial_scale=scale,
                target_normalized=target_normalized,
                reference_rotation=root_pose[:9].reshape(3, 3),
                target_rotation=target_pose[:9].reshape(3, 3),
                basis=basis,
            )
        )
        points.append(
            GeometryPoint(
                frame_id=frame_id,
                role="root",
                rollout_row_id=rollout.rollout_row_id,
                step_row_id=None,
                step_index=None,
                candidate_row_id=None,
                path_order=0,
                actor_action=None,
                selected=False,
                position=None,
                strategy=None,
                mixture=None,
                x=0.0,
                y=0.0,
                z=0.0,
                displacement_m=0.0,
                normalization_distance_m=scale,
                initial_target_distance_m=scale,
                normalized_radius=0.0,
                target_facing_error_deg=None,
            )
        )
        for path_order, step in enumerate(steps, start=1):
            selected_pose = _selected_pose(step)
            selected = step.selected_local_index
            displacement = selected_pose[9:12] - root_center
            normalized = basis.T @ displacement / scale
            candidate_position = int(step.candidate_row_positions[selected])
            points.append(
                GeometryPoint(
                    frame_id=frame_id,
                    role="selected_action",
                    rollout_row_id=rollout.rollout_row_id,
                    step_row_id=step.step_row_id,
                    step_index=step.step_index,
                    candidate_row_id=int(step.selected_candidate_row_id),
                    path_order=path_order,
                    actor_action=bool(step.actor_action_mask[selected]),
                    selected=True,
                    position=str(step.position_names[selected]),
                    strategy=decode_strategy_id(int(strategy_ids[candidate_position])),
                    mixture=str(step.mixture_names[selected]),
                    x=float(normalized[0]),
                    y=float(normalized[1]),
                    z=float(normalized[2]),
                    displacement_m=float(np.linalg.norm(displacement)),
                    normalization_distance_m=scale,
                    initial_target_distance_m=scale,
                    normalized_radius=float(np.linalg.norm(normalized)),
                    target_facing_error_deg=_target_facing_error_deg(selected_pose, target_center),
                )
            )
    return GeometryProjection("rollout_trajectory", tuple(points), tuple(frames), tuple(issues))


def s2_target_direction_histogram(
    reader: RolloutZarrStoreReader,
    *,
    azimuth_bins: int = 36,
    elevation_bins: int = 18,
    projection_limit: int = 2_000,
) -> S2DirectionHistogram:
    r"""Aggregate factual movement and camera-forward directions on S².

    The reducer reads only each factual rollout root and its referenced selected
    candidate shells; it never materializes the full candidate table.  For a
    target object frame ``e``, selected camera centres are transformed with
    ``(R_W^e)^T``.  Consecutive translations are normalized by the geometric
    mean of the target OBB semi-axes before their unit-sphere projection, while
    the selected camera local ``+Z`` optical axis supplies the view direction.
    The calibrated-frustum channel evaluates which points of the corresponding
    target-centred geometric-mean-scale proxy sphere are front-facing and project inside
    each selected pinhole camera.

    Args:
        reader: Validated read-only rollout store.
        azimuth_bins: Positive number of uniform target-frame azimuth bins.
        elevation_bins: Positive number of uniform target-frame ``z`` bins.
            Uniform ``z`` rather than uniform polar angle gives equal-solid-
            angle S² cells.
        projection_limit: Maximum deterministic reservoir samples retained per
            channel for a Plotly point overlay.  Counts remain complete.

    Returns:
        `S2DirectionHistogram` containing complete equal-solid-angle count
        grids, bounded target-frame projection samples, and explicit exclusions.

    Notes:
        A degenerate movement has no direction and is counted separately.
        Missing, non-rigid, or non-positive target OBB geometry excludes only
        that rollout and leaves the reason visible to presentation clients.
    """

    if azimuth_bins <= 0:
        raise ValueError("azimuth_bins must be positive.")
    if elevation_bins <= 0:
        raise ValueError("elevation_bins must be positive.")
    if projection_limit <= 0:
        raise ValueError("projection_limit must be positive.")

    movement_counts: NDArray[np.int64] = np.zeros((elevation_bins, azimuth_bins), dtype=np.int64)
    view_counts: NDArray[np.int64] = np.zeros((elevation_bins, azimuth_bins), dtype=np.int64)
    frustum_counts: NDArray[np.int64] = np.zeros((elevation_bins, azimuth_bins), dtype=np.int64)
    sphere_directions = _s2_bin_center_directions(elevation_bins, azimuth_bins)
    movement_projection: list[np.ndarray] = []
    movement_projection_lengths: list[float] = []
    movement_projection_rollout_ids: list[int] = []
    movement_projection_step_indices: list[int] = []
    view_projection: list[np.ndarray] = []
    view_projection_rollout_ids: list[int] = []
    view_projection_step_indices: list[int] = []
    frustum_projection: list[np.ndarray] = []
    frustum_projection_rollout_ids: list[int] = []
    frustum_projection_step_indices: list[int] = []
    movement_rng = np.random.default_rng(0)
    view_rng = np.random.default_rng(1)
    frustum_rng = np.random.default_rng(2)
    movement_count = 0
    view_count = 0
    frustum_count = 0
    frustum_centroid_count = 0
    frustum_missing_calibration_count = 0
    frustum_fov_solid_angles_sr: list[float] = []
    frustum_target_surface_fractions: list[float] = []
    movement_skipped_zero_count = 0
    rollout_count = 0
    source_sample_ids: set[int] = set()
    source_snippets: set[tuple[str, str]] = set()
    source_scenes: set[str] = set()
    target_ids: set[int] = set()
    selected_step_count = 0
    issues: list[GeometryIssue] = []
    try:
        frustum_calibrations = _selected_frustum_calibrations(reader, issues=issues)
    except ValueError as error:
        frustum_calibrations = {}
        issues.append(GeometryIssue("invalid_selected_frustum_calibration", str(error)))
    targets = {target.target_row_id: target for target in target_rows(reader)}
    rollouts = rollout_rows(reader)

    for rollout in rollouts:
        target = targets.get(rollout.target_row_id)
        if target is None:
            issues.append(
                GeometryIssue(
                    "missing_target",
                    "Rollout has no persisted observed-target geometry.",
                    rollout_row_id=rollout.rollout_row_id,
                )
            )
            continue
        try:
            target_pose = _geometry_pose(target.pose_world_object, role="observed target")
            target_scale_m = _target_obb_geometric_mean_scale(target.extents)
            root_pose = _geometry_pose(rollout.root_pose_world, role="rollout root")
            steps = _bounded_geometry_steps(reader, rollout)
            _validate_factual_steps(rollout.rollout_row_id, steps)
        except ValueError as error:
            issues.append(
                GeometryIssue(
                    "invalid_target_frame_or_path",
                    str(error),
                    rollout_row_id=rollout.rollout_row_id,
                )
            )
            continue

        target_rotation = target_pose[:9].reshape(3, 3)
        prior_center = root_pose[9:12]
        rollout_count += 1
        source_sample_ids.add(rollout.source_row_id)
        source_snippets.add((rollout.scene, rollout.snippet))
        source_scenes.add(rollout.scene)
        target_ids.add(rollout.target_row_id)
        selected_step_count += len(steps)
        for step in steps:
            selected_pose = _selected_pose(step)
            selected_center = selected_pose[9:12]
            movement_target = target_rotation.T @ (selected_center - prior_center) / target_scale_m
            normalized_movement = _unit_direction(movement_target)
            if normalized_movement is None:
                movement_skipped_zero_count += 1
            else:
                movement_count += 1
                _increment_s2_count(movement_counts, normalized_movement)
                _reservoir_append(
                    movement_projection,
                    movement_projection_lengths,
                    movement_projection_rollout_ids,
                    movement_projection_step_indices,
                    normalized_movement,
                    float(np.linalg.norm(movement_target)),
                    rollout_row_id=rollout.rollout_row_id,
                    step_index=step.step_index,
                    seen=movement_count,
                    limit=projection_limit,
                    rng=movement_rng,
                )

            view_target = target_rotation.T @ selected_pose[:9].reshape(3, 3)[:, 2]
            normalized_view = _unit_direction(view_target)
            if normalized_view is not None:
                view_count += 1
                _increment_s2_count(view_counts, normalized_view)
                _reservoir_append(
                    view_projection,
                    None,
                    view_projection_rollout_ids,
                    view_projection_step_indices,
                    normalized_view,
                    None,
                    rollout_row_id=rollout.rollout_row_id,
                    step_index=step.step_index,
                    seen=view_count,
                    limit=projection_limit,
                    rng=view_rng,
                )
            calibration = frustum_calibrations.get(step.step_row_id)
            if calibration is None:
                frustum_missing_calibration_count += 1
            elif calibration.candidate_row_id != step.selected_candidate_row_id:
                frustum_missing_calibration_count += 1
                issues.append(
                    GeometryIssue(
                        "selected_frustum_candidate_mismatch",
                        "Selected-depth calibration does not reference the factual selected candidate.",
                        rollout_row_id=rollout.rollout_row_id,
                        step_row_id=step.step_row_id,
                    )
                )
            else:
                frustum_count += 1
                camera_to_target = target_rotation.T @ selected_pose[:9].reshape(3, 3)
                camera_center_target = target_rotation.T @ (selected_center - target_pose[9:12])
                footprint = _target_surface_frustum_mask(
                    sphere_directions,
                    target_scale_m=target_scale_m,
                    camera_center_target=camera_center_target,
                    camera_to_target=camera_to_target,
                    calibration=calibration,
                )
                frustum_counts += footprint.astype(np.int64)
                frustum_fov_solid_angles_sr.append(_pinhole_frustum_solid_angle_sr(calibration))
                frustum_target_surface_fractions.append(float(np.mean(footprint)))
                footprint_centroid = _unit_direction(np.sum(sphere_directions[footprint], axis=0))
                if footprint_centroid is not None:
                    frustum_centroid_count += 1
                    _reservoir_append(
                        frustum_projection,
                        None,
                        frustum_projection_rollout_ids,
                        frustum_projection_step_indices,
                        footprint_centroid,
                        None,
                        rollout_row_id=rollout.rollout_row_id,
                        step_index=step.step_index,
                        seen=frustum_centroid_count,
                        limit=projection_limit,
                        rng=frustum_rng,
                    )
            prior_center = selected_center

    mean_fov_solid_angle = float(np.mean(frustum_fov_solid_angles_sr)) if frustum_fov_solid_angles_sr else None
    mean_target_surface_fraction = (
        float(np.mean(frustum_target_surface_fractions)) if frustum_target_surface_fractions else None
    )
    union_fraction = float(np.count_nonzero(frustum_counts) / frustum_counts.size) if frustum_count else None

    return S2DirectionHistogram(
        movement_counts=movement_counts,
        view_direction_counts=view_counts,
        movement_projection=_stack_s2_samples(movement_projection),
        movement_projection_normalized_lengths=np.asarray(movement_projection_lengths, dtype=np.float32),
        movement_projection_rollout_row_ids=np.asarray(movement_projection_rollout_ids, dtype=np.int64),
        movement_projection_step_indices=np.asarray(movement_projection_step_indices, dtype=np.int64),
        view_direction_projection=_stack_s2_samples(view_projection),
        view_direction_projection_rollout_row_ids=np.asarray(view_projection_rollout_ids, dtype=np.int64),
        view_direction_projection_step_indices=np.asarray(view_projection_step_indices, dtype=np.int64),
        frustum_counts=frustum_counts,
        frustum_projection=_stack_s2_samples(frustum_projection),
        frustum_projection_rollout_row_ids=np.asarray(frustum_projection_rollout_ids, dtype=np.int64),
        frustum_projection_step_indices=np.asarray(frustum_projection_step_indices, dtype=np.int64),
        movement_count=movement_count,
        view_direction_count=view_count,
        frustum_count=frustum_count,
        frustum_missing_calibration_count=frustum_missing_calibration_count,
        frustum_mean_fov_solid_angle_sr=mean_fov_solid_angle,
        frustum_mean_target_surface_fraction_approx=mean_target_surface_fraction,
        frustum_union_target_surface_fraction_approx=union_fraction,
        movement_skipped_zero_count=movement_skipped_zero_count,
        rollout_count=rollout_count,
        store_rollout_count=len(rollouts),
        source_sample_count=len(source_sample_ids),
        source_snippet_count=len(source_snippets),
        source_scene_count=len(source_scenes),
        target_count=len(target_ids),
        selected_step_count=selected_step_count,
        azimuth_bins=azimuth_bins,
        elevation_bins=elevation_bins,
        projection_limit=projection_limit,
        issues=tuple(issues),
    )


def _target_obb_geometric_mean_scale(extents: np.ndarray) -> float:
    """Return the target OBB's geometric-mean semi-axis scale in metres.

    Persisted OBB extents are full axis lengths.  Halving them gives semi-axes
    ``(a_x, a_y, a_z)``; ``r_e=(a_x a_y a_z)^(1/3)`` is their geometric-mean
    scale.  This scale is permutation-invariant over the OBB axes and remains
    equivariant to uniform scaling; it is a proxy normalization length.
    """

    axes = np.asarray(extents, dtype=np.float64).reshape(3)
    if not np.isfinite(axes).all() or np.any(axes <= _GEOMETRY_EPSILON):
        raise ValueError("Target OBB extents must be finite and strictly positive.")
    return float(0.5 * np.exp(np.mean(np.log(axes))))


def _unit_direction(vector: np.ndarray) -> NDArray[np.float64] | None:
    """Return one finite unit vector, or ``None`` when its direction is undefined."""

    value = np.asarray(vector, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(value))
    if not np.isfinite(norm) or norm <= _GEOMETRY_EPSILON:
        return None
    return value / norm


def _image_edge_coordinates(size: int) -> tuple[float, float]:
    """Return continuous pixel-edge coordinates for an image dimension.

    Pixel centres use integer coordinates ``0`` through ``size - 1``.  The
    corresponding image boundary is therefore the half-pixel interval
    ``[-0.5, size - 0.5]``.  Keeping this convention in one helper ensures the
    spherical frustum footprint and its analytic corner-ray solid angle use
    the same image rectangle.
    """

    if int(size) != size or size <= 0:
        raise ValueError("Image dimensions must be positive integers.")
    return -0.5, float(size) - 0.5


def _increment_s2_count(counts: NDArray[np.int64], direction: NDArray[np.float64]) -> None:
    """Add one target-frame unit direction to an equal-solid-angle S² grid."""

    elevation_bins, azimuth_bins = counts.shape
    z = float(np.clip(direction[2], -1.0, 1.0))
    azimuth = float(np.arctan2(direction[1], direction[0]))
    elevation_index = min(int((z + 1.0) * 0.5 * elevation_bins), elevation_bins - 1)
    azimuth_index = min(int((azimuth + np.pi) / (2.0 * np.pi) * azimuth_bins), azimuth_bins - 1)
    counts[elevation_index, azimuth_index] += 1


def _s2_bin_center_directions(elevation_bins: int, azimuth_bins: int) -> NDArray[np.float64]:
    """Return equal-solid-angle target-frame S² cell centres."""

    z_centers = -1.0 + (np.arange(elevation_bins, dtype=np.float64) + 0.5) * 2.0 / elevation_bins
    azimuth_centers = -np.pi + (np.arange(azimuth_bins, dtype=np.float64) + 0.5) * 2.0 * np.pi / azimuth_bins
    grid_shape = (elevation_bins, azimuth_bins)
    azimuth: NDArray[np.float64] = np.broadcast_to(azimuth_centers[None, :], grid_shape).copy()
    z: NDArray[np.float64] = np.broadcast_to(z_centers[:, None], grid_shape).copy()
    radius = np.sqrt(np.maximum(0.0, 1.0 - z**2))
    return np.stack((radius * np.cos(azimuth), radius * np.sin(azimuth), z), axis=-1)


def _selected_frustum_calibrations(
    reader: RolloutZarrStoreReader,
    *,
    issues: list[GeometryIssue] | None = None,
) -> dict[int, _SelectedFrustumCalibration]:
    """Read selected-view pinhole metadata without materializing depth rasters.

    Array-shape, duplicate-key, and missing-field defects are structural and
    fail the whole calibration payload.  A malformed value in one otherwise
    addressable row is a local evidence issue: that row is omitted while all
    other valid rows remain available to the frustum projection.  Pass
    ``issues`` to retain those row-level diagnostics in the returned histogram.
    """

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return {}
    try:
        group = reader.root["selected_depth"]
        step_ids = np.asarray(group["step_row_id"], dtype=np.int64).reshape(-1)
        candidate_ids = np.asarray(group["candidate_row_id"], dtype=np.int64).reshape(-1)
        focal = np.asarray(group["focal_px"], dtype=np.float64).reshape(-1, 2)
        principal = np.asarray(group["principal_point_px"], dtype=np.float64).reshape(-1, 2)
        sizes = np.asarray(group["image_size_hw"], dtype=np.int64).reshape(-1, 2)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Selected-depth frustum metadata is incomplete: {error}.") from error
    row_count = step_ids.size
    if not (candidate_ids.size == row_count == focal.shape[0] == principal.shape[0] == sizes.shape[0]):
        raise ValueError("Selected-depth frustum metadata arrays have inconsistent row counts.")
    if len(set(step_ids.tolist())) != row_count:
        raise ValueError("Selected-depth frustum metadata contains duplicate step_row_id values.")
    result: dict[int, _SelectedFrustumCalibration] = {}
    for row in range(row_count):
        height, width = (int(value) for value in sizes[row])
        if (
            not np.isfinite(focal[row]).all()
            or np.any(focal[row] <= 0.0)
            or not np.isfinite(principal[row]).all()
            or height <= 0
            or width <= 0
        ):
            if issues is not None:
                issues.append(
                    GeometryIssue(
                        "invalid_selected_frustum_calibration_row",
                        f"Selected-depth frustum calibration row {row} is non-finite or non-positive.",
                        step_row_id=int(step_ids[row]),
                    )
                )
            continue
        result[int(step_ids[row])] = _SelectedFrustumCalibration(
            candidate_row_id=int(candidate_ids[row]),
            focal_px=focal[row].copy(),
            principal_point_px=principal[row].copy(),
            image_size_hw=(height, width),
        )
    return result


def _target_surface_frustum_mask(
    sphere_directions: NDArray[np.float64],
    *,
    target_scale_m: float,
    camera_center_target: NDArray[np.float64],
    camera_to_target: NDArray[np.float64],
    calibration: _SelectedFrustumCalibration,
) -> NDArray[np.bool_]:
    r"""Return one selected frustum's visible proxy-surface footprint.

    For target-frame unit direction :math:`\boldsymbol{d}^e`, the proxy point
    is :math:`\boldsymbol{x}^e=r_e\boldsymbol{d}^e`.  Subtracting the selected
    camera centre before applying the target-to-camera rotation is essential:
    rotating :math:`\boldsymbol{d}^e` alone would describe an orientation
    sphere, not a target-centred surface footprint.  A point is admitted only
    when its outward normal faces the camera and its calibrated pinhole
    projection lies in the continuous image rectangle.

    The returned mask is geometric potential visibility.  It includes camera
    translation, rotation, and intrinsics, but not scene or self-occlusion by
    the true target geometry beyond the proxy sphere's front-facing test.
    """

    radius = float(target_scale_m)
    if not np.isfinite(radius) or radius <= _GEOMETRY_EPSILON:
        raise ValueError("target_scale_m must be finite and positive.")
    camera_center = np.asarray(camera_center_target, dtype=np.float64).reshape(3)
    if not np.isfinite(camera_center).all():
        raise ValueError("camera_center_target must be finite.")
    surface_points = radius * sphere_directions
    point_vectors_target = surface_points - camera_center
    points_camera = point_vectors_target @ np.asarray(camera_to_target, dtype=np.float64)
    x = points_camera[..., 0]
    y = points_camera[..., 1]
    z = points_camera[..., 2]
    fx, fy = calibration.focal_px
    cx, cy = calibration.principal_point_px
    height, width = calibration.image_size_hw
    u_min, u_max = _image_edge_coordinates(width)
    v_min, v_max = _image_edge_coordinates(height)
    with np.errstate(divide="ignore", invalid="ignore"):
        u = cx - fx * x / z
        v = cy - fy * y / z
    front_facing = np.sum(sphere_directions * (camera_center - surface_points), axis=-1) > _GEOMETRY_EPSILON
    return np.asarray(
        front_facing & (z > _GEOMETRY_EPSILON) & (u >= u_min) & (u <= u_max) & (v >= v_min) & (v <= v_max),
        dtype=np.bool_,
    )


def _pinhole_frustum_solid_angle_sr(calibration: _SelectedFrustumCalibration) -> float:
    r"""Return the calibrated rectangular pinhole frustum's solid angle.

    Four image-edge corner rays form a spherical quadrilateral.  Splitting it
    into two triangles gives the exact angular area in steradians; triangle
    ``(a,b,c)`` uses

    $$
    \Omega_\triangle=2\operatorname{atan2}
    \left(|a^\top(b\times c)|,1+a^\top b+b^\top c+c^\top a\right).
    $$
    """

    fx, fy = calibration.focal_px
    cx, cy = calibration.principal_point_px
    height, width = calibration.image_size_hw
    u_min, u_max = _image_edge_coordinates(width)
    v_min, v_max = _image_edge_coordinates(height)

    def ray(u: float, v: float) -> NDArray[np.float64]:
        value = np.asarray([(cx - u) / fx, (cy - v) / fy, 1.0], dtype=np.float64)
        return value / np.linalg.norm(value)

    top_left = ray(u_min, v_min)
    top_right = ray(u_max, v_min)
    bottom_right = ray(u_max, v_max)
    bottom_left = ray(u_min, v_max)

    def triangle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        numerator = abs(float(np.dot(a, np.cross(b, c))))
        denominator = 1.0 + float(np.dot(a, b) + np.dot(b, c) + np.dot(c, a))
        return 2.0 * float(np.arctan2(numerator, denominator))

    return triangle(top_left, top_right, bottom_right) + triangle(top_left, bottom_right, bottom_left)


def _reservoir_append(
    samples: list[np.ndarray],
    magnitudes: list[float] | None,
    rollout_row_ids: list[int],
    step_indices: list[int],
    direction: NDArray[np.float64],
    magnitude: float | None,
    *,
    rollout_row_id: int,
    step_index: int,
    seen: int,
    limit: int,
    rng: np.random.Generator,
) -> None:
    """Keep an unbiased bounded display sample without weakening complete counts."""

    if len(samples) < limit:
        samples.append(np.asarray(direction, dtype=np.float32))
        rollout_row_ids.append(int(rollout_row_id))
        step_indices.append(int(step_index))
        if magnitudes is not None and magnitude is not None:
            magnitudes.append(float(magnitude))
        return
    replacement_index = int(rng.integers(0, seen))
    if replacement_index >= limit:
        return
    samples[replacement_index] = np.asarray(direction, dtype=np.float32)
    rollout_row_ids[replacement_index] = int(rollout_row_id)
    step_indices[replacement_index] = int(step_index)
    if magnitudes is not None and magnitude is not None:
        magnitudes[replacement_index] = float(magnitude)


def _stack_s2_samples(samples: list[np.ndarray]) -> NDArray[np.float32]:
    """Return bounded S² samples as a stable ``ndarray[\"N 3\", float32]``."""

    if not samples:
        return np.empty((0, 3), dtype=np.float32)
    return np.asarray(samples, dtype=np.float32).reshape(-1, 3)


def _validate_factual_steps(rollout_row_id: int, steps: tuple[Any, ...]) -> None:
    indices = [int(step.step_index) for step in steps]
    if indices != list(range(len(indices))):
        raise ValueError(f"Rollout row {rollout_row_id} has non-contiguous factual step indices: {indices}.")
    for step in steps:
        _selected_pose(step)


def _selected_pose(step: Any) -> np.ndarray:
    matches = np.flatnonzero(np.asarray(step.selected_mask, dtype=np.bool_))
    if matches.size != 1:
        raise ValueError(f"Step row {step.step_row_id} must have exactly one selected candidate; found {matches.size}.")
    selected = int(matches[0])
    if int(step.candidate_row_ids[selected]) != int(step.selected_candidate_row_id):
        raise ValueError(f"Step row {step.step_row_id} selected mask disagrees with selected_candidate_row_id.")
    return _geometry_pose(step.pose_world_cam[selected], role=f"step {step.step_row_id} selected pose")


def _geometry_pose(pose: Any, *, role: str) -> np.ndarray:
    value = np.asarray(pose, dtype=np.float64).reshape(12)
    if not np.isfinite(value).all():
        raise ValueError(f"{role} contains non-finite pose values.")
    rotation = value[:9].reshape(3, 3)
    if not np.allclose(rotation.T @ rotation, np.eye(3), rtol=0.0, atol=1e-4) or not np.isclose(
        np.linalg.det(rotation),
        1.0,
        rtol=0.0,
        atol=1e-4,
    ):
        raise ValueError(f"{role} contains an invalid rotation matrix.")
    return value


def _positive_distance(delta: np.ndarray) -> float | None:
    distance = float(np.linalg.norm(np.asarray(delta, dtype=np.float64)))
    return distance if np.isfinite(distance) and distance > _GEOMETRY_EPSILON else None


def _target_facing_error_deg(pose: np.ndarray, target_center: np.ndarray) -> float | None:
    """Return the unsigned 3D angle from LUF camera forward to the target."""

    target_direction = np.asarray(target_center, dtype=np.float64) - pose[9:12]
    target_distance = _positive_distance(target_direction)
    if target_distance is None:
        return None
    forward = pose[:9].reshape(3, 3)[:, 2]
    cosine = float(np.dot(forward, target_direction / target_distance))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _horizontal_angle_deg(left: np.ndarray, right: np.ndarray) -> float | None:
    """Return the unsigned angle between two horizontal directions."""

    left_xy = np.asarray(left, dtype=np.float64).reshape(3)[:2]
    right_xy = np.asarray(right, dtype=np.float64).reshape(3)[:2]
    left_norm = float(np.linalg.norm(left_xy))
    right_norm = float(np.linalg.norm(right_xy))
    if min(left_norm, right_norm) <= _GEOMETRY_EPSILON:
        return None
    cosine = float(np.dot(left_xy / left_norm, right_xy / right_norm))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _proposal_basis(
    reference_pose: np.ndarray, target_center: np.ndarray, alignment: ProposalAlignment
) -> np.ndarray | None:
    if alignment is ProposalAlignment.TARGET_ALIGNED_Z_UP:
        return _target_aligned_basis(target_center - reference_pose[9:12])
    if alignment is ProposalAlignment.RIG_FORWARD_Z_UP:
        return _z_up_basis(reference_pose[:9].reshape(3, 3)[:, 2])
    raise ValueError(f"Unsupported proposal alignment: {alignment!r}.")


def _target_aligned_basis(target_delta: np.ndarray) -> np.ndarray | None:
    return _z_up_basis(target_delta)


def _z_up_basis(forward_world: np.ndarray) -> np.ndarray | None:
    forward = np.asarray(forward_world, dtype=np.float64).reshape(3).copy()
    forward[2] = 0.0
    norm = float(np.linalg.norm(forward))
    if not np.isfinite(norm) or norm <= _GEOMETRY_EPSILON:
        return None
    forward /= norm
    up = np.asarray([0.0, 0.0, 1.0], dtype=np.float64)
    left = np.cross(up, forward)
    return np.column_stack((forward, left, up))


def _geometry_frame(
    *,
    frame_id: str,
    rollout_row_id: int,
    step_row_id: int | None,
    step_index: int | None,
    origin_kind: Literal["expansion_pose", "rollout_root"],
    expansion_pose_source: Literal["root", "previous_selected", "initial_root"],
    scale_kind: Literal["current_target_distance", "initial_target_distance"],
    alignment: str,
    scale: float,
    initial_scale: float,
    target_normalized: np.ndarray,
    reference_rotation: np.ndarray,
    target_rotation: np.ndarray,
    basis: np.ndarray,
) -> GeometryFrame:
    local_reference = basis.T @ reference_rotation
    local_target = basis.T @ target_rotation
    target_delta_local = np.asarray(target_normalized, dtype=np.float64)
    target_horizontal = float(np.linalg.norm(target_delta_local[:2]))
    target_elevation = float(np.degrees(np.arctan2(target_delta_local[2], target_horizontal)))
    rig_target_yaw_error = _horizontal_angle_deg(reference_rotation[:, 2], basis @ target_delta_local)

    def axis(rotation: np.ndarray, index: int) -> tuple[float, float, float]:
        values = tuple(float(value) for value in rotation[:, index])
        if len(values) != 3:
            raise ValueError("Geometry rotation axes must have exactly three coordinates.")
        return values

    return GeometryFrame(
        frame_id=frame_id,
        rollout_row_id=rollout_row_id,
        step_row_id=step_row_id,
        step_index=step_index,
        origin_kind=origin_kind,
        expansion_pose_source=expansion_pose_source,
        scale_kind=scale_kind,
        alignment=alignment,
        scale_m=scale,
        initial_scale_m=initial_scale,
        target_x=float(target_normalized[0]),
        target_y=float(target_normalized[1]),
        target_z=float(target_normalized[2]),
        reference_axis_x=axis(local_reference, 0),
        reference_axis_y=axis(local_reference, 1),
        reference_axis_z=axis(local_reference, 2),
        target_axis_x=axis(local_target, 0),
        target_axis_y=axis(local_target, 1),
        target_axis_z=axis(local_target, 2),
        rig_target_yaw_error_deg=rig_target_yaw_error,
        target_elevation_deg=target_elevation,
    )


__all__ = [
    "GeometryFrame",
    "GeometryIssue",
    "GeometryPoint",
    "GeometryProjection",
    "ProposalAlignment",
    "RolloutSuspiciousQueryConfig",
    "S2DirectionHistogram",
    "candidate_audit_rows",
    "candidate_flow_rows",
    "candidate_group_summary_rows",
    "candidate_collision_support_rows",
    "candidate_composition_rows",
    "candidate_proposal_calibration_rows",
    "candidate_selection_pooled_summary_rows",
    "candidate_selection_sequence_rows",
    "candidate_selection_temporal_summary_rows",
    "candidate_selection_transition_rows",
    "candidate_sequence_return_summary_rows",
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
    "proposal_support_geometry",
    "promoted_store_validation_error",
    "root_relative_candidate_rows",
    "rollout_store_inventory_rows",
    "rollout_statistics",
    "q_h_evidence_rows",
    "runtime_storage_statistics",
    "rollout_step_objective_rows",
    "rollout_trajectory_geometry",
    "s2_target_direction_histogram",
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
