"""Standalone Zarr replay store for finite-candidate rollout traces.

This module is the implementation-contract owner for `rollouts.zarr`. A store
contains compact row tables for rollout chains, steps, full-shell candidates,
shared VIN source rows, lineage, target records, masks, and reason codes. The
padded `Q_H` tensors used by finite-candidate value learning are persisted in a
derived `q_h/` group for high-throughput training and are validated against the
canonical factual `steps/` and `candidates/` tables. The store deliberately does
not mutate or migrate the strict VIN offline store; rollout replay is a
separate artifact with source manifest, split, target, candidate-mixture, policy,
and oracle config hashes.

`q_train_mask` is true only when a candidate row is actor-selectable,
target-valid, GT-label-valid, and has a finite target-root-gain reward. Invalid
candidates keep their full-shell row but carry false masks and NaN labels. Q_H
padding exists only in the derived dense `q_h/` view. Target RRI and scene RRI
are state-relative diagnostics; target labels must not be silently filled from
scene scores or low-quality invalid rows.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
import torch
import zarr
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from zarr.codecs import BloscCname, BloscCodec, BloscShuffle
from zarr.storage import LocalStore

from ..configs import PathConfig
from ..data_handling.identifiers import compact_ase_atek_sample_id, raw_ase_atek_sample_id
from ..targets.protocol import (
    ORACLE_GT_TARGET_SOURCE,
    ActorVisibleTargetSource,
    TargetInputProtocol,
    TargetLabelEvidence,
    target_label_is_trainable,
    validate_target_protocol_admission,
)
from ..utils import BaseConfig
from ..utils.config_paths import resolve_cache_artifact_dir
from .manifest import (
    ROLLOUT_MANIFEST_FILENAME,
    ROLLOUT_MANIFEST_VERSION,
    RolloutStoreManifestContext,
    manifest_sha256,
    read_rollout_store_manifest,
    utc_timestamp,
    write_rollout_store_manifest,
)
from .trace import (
    INVALID_REASON_CODES,
    INVALID_REASON_VERSION,
    RolloutLineage,
    _candidate_invalid_reasons,
    _full_shell_or_default,
    _policy_name,
    _termination_reason,
)


class _EvaluatedRollout(Protocol):
    """Minimal evaluated-rollout view consumed by persistence."""

    @property
    def result(self) -> Any: ...

    def step(self, chain_id: int, step_index: int) -> Any: ...


class _RolloutWriteRecord(Protocol):
    """Private structural writer input supplied by an Oracle pipeline."""

    @property
    def evaluated(self) -> _EvaluatedRollout: ...

    @property
    def lineage(self) -> RolloutLineage: ...

    @property
    def rollout_id_prefix(self) -> str: ...


class _SelectedDepthEvidence(Protocol):
    selected_depth_image_size_hw: tuple[int, int] | None


if TYPE_CHECKING:
    from collections.abc import Iterator

    from .replay.state import CounterfactualStepResult, CounterfactualTrajectory

ROLLOUT_ZARR_SCHEMA_ID = "aria_nbv.rollout_zarr_q_invalidity"
"""Schema id stored as a root attribute on rollout replay stores."""

ROLLOUT_ZARR_SCHEMA_VERSION = "1.0-target-rollout-core"
"""Target-first rollout schema with hot candidate provenance and core parent-depth history."""

DEFAULT_RETURN_SEMANTICS = "cumulative_target_root_gain"
"""Default return target family for root-normalized ``Q_H`` replay views."""

Q_H_REWARD_METRIC = "target_root_gain"
"""Candidate field used as the default Q_H training reward."""

DEFAULT_TARGET_EVAL_CROP_MAX_POINTS = 50_000
"""Default fixed row width for oracle/eval target crop point payloads."""

SELECTED_DEPTH_INVALID_FILL_VALUE = 0.0
"""Fill value written for invalid selected-depth pixels before float16 storage."""

SELECTED_DEPTH_CODEC = "blosc:zstd:clevel=5:bitshuffle"
"""Human-readable selected-depth compressor contract stored in metadata."""

Q_H_TD_SEMANTICS = "selected_transition_only"
"""Q_H TD contract persisted on the ``q_h/`` group."""

Q_H_ARRAY_NAMES = (
    "state_step_row_id",
    "source_row_id",
    "candidate_row_id",
    "valid_action_mask",
    "q_train_mask",
    "target_row_id",
    "selected_candidate_index",
    "position_id",
    "one_step_target_rri",
    "one_step_target_root_gain",
    "invalid_reason_bitset",
    "td_selected_candidate_row_id",
    "td_reward",
    "td_reward_target_rri",
    "td_next_step_row_id",
    "td_terminal_mask",
    "td_discount",
)
"""Arrays persisted in the derived finite-candidate ``q_h/`` training view."""


@dataclass(frozen=True, slots=True)
class _TableField:
    """One fixed-width Zarr table field."""

    name: str
    dtype: Any


@dataclass(frozen=True, slots=True)
class _TableSchema:
    """Compact schema owner for one fixed-width Zarr table."""

    name: str
    fields: tuple[_TableField, ...]

    @property
    def names(self) -> tuple[str, ...]:
        """Return field names in write order."""

        return tuple(field.name for field in self.fields)

    @property
    def dtypes(self) -> dict[str, Any]:
        """Return the field dtype map used for NumPy materialization."""

        return {field.name: field.dtype for field in self.fields}


SOURCE_TABLE = _TableSchema(
    "sources",
    (
        _TableField("source_row_id", np.int64),
        _TableField("sample_index", np.int64),
        _TableField("sample_key_id", np.int32),
        _TableField("scene_id", np.int32),
        _TableField("snippet_id", np.int32),
        _TableField("split_id", np.int32),
        _TableField("source_cache_version_id", np.int32),
        _TableField("source_offline_store_manifest_hash_id", np.int32),
        _TableField("split_manifest_hash_id", np.int32),
        _TableField("source_shard_id", np.int32),
        _TableField("source_shard_row", np.int64),
    ),
)
"""Canonical `sources/` table schema."""

ROLLOUT_TABLE = _TableSchema(
    "rollouts",
    (
        _TableField("rollout_row_id", np.int64),
        _TableField("rollout_id", np.int32),
        _TableField("chain_id", np.int32),
        _TableField("source_row_id", np.int64),
        _TableField("root_pose_world", np.float32),
        _TableField("root_time_ns", np.int64),
        _TableField("root_trajectory_index", np.int32),
        _TableField("root_frame_index", np.int32),
        _TableField("scene_id", np.int32),
        _TableField("snippet_id", np.int32),
        _TableField("target_row_id", np.int64),
        _TableField("policy_id", np.int32),
        _TableField("horizon", np.int16),
        _TableField("branch_factor", np.int16),
        _TableField("beam_width", np.int16),
        _TableField("temperature", np.float32),
        _TableField("random_seed", np.int64),
        _TableField("termination_reason", np.int32),
        _TableField("final_cumulative_target_rri", np.float32),
        _TableField("final_cumulative_scene_rri", np.float32),
        _TableField("final_cumulative_target_root_gain", np.float32),
        _TableField("final_cumulative_scene_root_gain", np.float32),
        _TableField("split_id", np.int32),
    ),
)
"""Canonical `rollouts/` table fields and dtypes."""

LINEAGE_TABLE = _TableSchema(
    "lineage",
    (
        _TableField("rollout_row_id", np.int64),
        _TableField("candidate_config_id", np.int32),
        _TableField("oracle_config_id", np.int32),
        _TableField("rollout_config_id", np.int32),
        _TableField("model_checkpoint_id", np.int32),
        _TableField("mesh_version_id", np.int32),
        _TableField("branch_schedule_id", np.int32),
        _TableField("target_protocol_version_id", np.int32),
        _TableField("target_crop_policy_id", np.int32),
        _TableField("reason_code_version_id", np.int32),
        _TableField("selection_rng_state_hash_id", np.int32),
    ),
)
"""Canonical `lineage/` table fields and dtypes."""

STEP_TABLE = _TableSchema(
    "steps",
    (
        _TableField("step_row_id", np.int64),
        _TableField("rollout_row_id", np.int64),
        _TableField("step_index", np.int16),
        _TableField("selected_candidate_row_id", np.int64),
        _TableField("selected_shell_index", np.int32),
        _TableField("selected_compact_valid_index", np.int32),
        _TableField("num_candidates", np.int32),
        _TableField("num_valid_candidates", np.int32),
        _TableField("cumulative_target_rri", np.float32),
        _TableField("cumulative_scene_rri", np.float32),
        _TableField("cumulative_target_root_gain", np.float32),
        _TableField("cumulative_scene_root_gain", np.float32),
    ),
)
"""Canonical `steps/` table fields and dtypes."""

CANDIDATE_TABLE = _TableSchema(
    "candidates",
    (
        _TableField("candidate_row_id", np.int64),
        _TableField("step_row_id", np.int64),
        _TableField("rollout_row_id", np.int64),
        _TableField("step_index", np.int16),
        _TableField("shell_index", np.int32),
        _TableField("compact_valid_index", np.int32),
        _TableField("pose_world_cam", np.float32),
        _TableField("pose_relative_root", np.float32),
        _TableField("actor_action_mask", np.bool_),
        _TableField("oracle_label_mask", np.bool_),
        _TableField("q_train_mask", np.bool_),
        _TableField("selected_mask", np.bool_),
        _TableField("strategy_id", np.int32),
        _TableField("position_id", np.int32),
        _TableField("mixture_id", np.int32),
        _TableField("sampler_probability", np.float32),
        _TableField("score_source_id", np.int32),
        _TableField("invalid_reason_bitset", np.uint32),
        _TableField("primary_invalid_reason", np.uint16),
        _TableField("scene_rri", np.float32),
        _TableField("target_rri", np.float32),
        _TableField("scene_root_gain", np.float32),
        _TableField("target_root_gain", np.float32),
        _TableField("scene_log_error_gain", np.float32),
        _TableField("target_log_error_gain", np.float32),
        _TableField("scene_pm_dist_before", np.float32),
        _TableField("scene_pm_dist_after", np.float32),
        _TableField("target_pm_dist_before", np.float32),
        _TableField("target_pm_dist_after", np.float32),
        _TableField("target_current_support", np.float32),
        _TableField("target_candidate_support", np.float32),
        _TableField("selection_logits", np.float32),
        _TableField("selection_probabilities", np.float32),
        _TableField("selection_log_probabilities", np.float32),
    ),
)
"""Canonical `candidates/` table fields and dtypes."""

CANDIDATE_DIAGNOSTIC_TABLE = _TableSchema(
    "candidate_diagnostics",
    (
        _TableField("candidate_row_id", np.int64),
        _TableField("position_id", np.int32),
        _TableField("mesh_distance_m", np.float32),
        _TableField("path_min_clearance_m", np.float32),
        _TableField("path_collision_mask", np.bool_),
        _TableField("free_space_margin_m", np.float32),
        _TableField("motion_step_length_m", np.float32),
        _TableField("motion_height_delta_m", np.float32),
        _TableField("motion_backward_step_m", np.float32),
        _TableField("motion_yaw_delta_deg", np.float32),
        _TableField("target_distance_m", np.float32),
        _TableField("target_bearing_yaw_deg", np.float32),
    ),
)
"""Typed candidate-generation diagnostics aligned one-to-one with `candidates/`."""

SELECTED_DEPTH_TABLE = _TableSchema(
    "selected_depth",
    (
        _TableField("step_row_id", np.int64),
        _TableField("candidate_row_id", np.int64),
        _TableField("focal_px", np.float32),
        _TableField("principal_point_px", np.float32),
        _TableField("image_size_hw", np.int32),
    ),
)
"""Metadata rows aligned with selected-action depth rasters.

The companion ``depth_m`` and ``valid_mask`` arrays are respectively
``ndarray["D H_d W_d", float16]`` in metres and
``ndarray["D H_d W_d", bool]``. ``D`` is the selected-depth row axis, normally
one row per materialized step. These mesh-rendered arrays are oracle/audit
artifacts, not actor observations.
"""

TARGET_EVAL_CROP_TABLE = _TableSchema(
    "target_eval_crops",
    (
        _TableField("crop_row_id", np.int64),
        _TableField("step_row_id", np.int64),
        _TableField("candidate_row_id", np.int64),
        _TableField("source_role_id", np.int32),
        _TableField("crop_policy_id", np.int32),
        _TableField("voxel_size_m", np.float32),
        _TableField("max_points", np.int32),
        _TableField("lengths", np.int32),
    ),
)
"""Oracle/eval-only target crop metadata aligned with fixed point payloads.

The companion ``points_world`` array is
``ndarray["R P_max 3", float32]`` in world metres, with
``ndarray["R P_max", bool]`` masks and ``ndarray["R", int32]`` lengths. ``R``
includes optional current-state and candidate-specific crop rows.
"""


@dataclass(slots=True)
class RolloutZarrWriteResult:
    """Summary of one rollout Zarr write.

    Counts refer to materialized row tables, not source VIN samples. One source
    sample can contribute multiple targets, rollout recipes, beam chains,
    steps, and full-shell candidate rows.
    """

    store_dir: Path
    """Resolved standalone rollout-store directory written by the session."""

    num_rollouts: int
    """Number of retained trajectory-chain rows in ``rollouts/``."""

    num_steps: int
    """Number of materialized state/transition rows in ``steps/``."""

    num_candidates: int
    """Number of full-shell action rows in ``candidates/``."""

    manifest_path: Path
    """Human-readable provenance sidecar beside the Zarr payload."""

    manifest_sha256: str
    """SHA-256 binding canonical manifest JSON to the store root attrs."""


@dataclass(slots=True)
class RolloutZarrValidationResult:
    """Validation summary for a rollout Zarr store.

    `errors` contains schema, linkage, mask, and lineage violations. Validation
    fails if candidate strategy ids, mixture ids, target protocol metadata,
    source hashes, or explicit target-root-gain rewards are missing.
    """

    store_dir: Path
    """Resolved rollout-store directory checked in read-only mode."""

    num_rollouts: int
    """Validated number of normalized rollout rows."""

    num_steps: int
    """Validated number of normalized step/state rows."""

    num_candidates: int
    """Validated number of full-shell candidate rows."""

    errors: list[str] = field(default_factory=list)
    """All discovered schema, linkage, mask, label, and provenance violations."""

    @property
    def ok(self) -> bool:
        """Return ``True`` when no validation errors were found."""

        return not self.errors


@dataclass(slots=True)
class _RolloutTables:
    """Materialized rollout store row tables before Zarr persistence."""

    sources: dict[str, np.ndarray]
    """Deduplicated immutable VIN source-row facts keyed by schema field."""

    rollouts: dict[str, np.ndarray]
    """One row per retained trajectory chain."""

    lineage: dict[str, np.ndarray]
    """Configuration and asset provenance aligned one-to-one with rollouts."""

    steps: dict[str, np.ndarray]
    """Materialized rollout state/transition rows across all chains."""

    candidates: dict[str, np.ndarray]
    """Variable-shell candidate facts flattened across step rows."""

    candidate_diagnostics: dict[str, np.ndarray]
    """Generator diagnostics aligned one-to-one with candidate rows."""

    selected_depth: dict[str, np.ndarray]
    """Selected-only oracle depth rasters and camera metadata."""

    target_eval_crops: dict[str, np.ndarray]
    """Optional oracle/evaluation target point crops for sampled audits."""


class RolloutZarrStoreConfig(BaseConfig):
    """Filesystem, replay, and oracle-retention settings for one rollout store.

    The destination is independent of the immutable VIN offline cache. Direct
    writes own and replace ``store_dir``; validated completed stores should be
    treated as immutable inputs. Cluster jobs obtain crash-safe lifecycle
    semantics through temporary shard writes and atomic final promotion.
    """

    paths: PathConfig = Field(default_factory=PathConfig)
    """Repository path defaults used to resolve cache artifact destinations."""

    store_dir: Path = Field(default_factory=lambda: PathConfig().offline_cache_dir / "rollouts.zarr")
    """Standalone destination replaced by a direct write; never the VIN source store."""

    return_semantics: str = DEFAULT_RETURN_SEMANTICS
    """Versioned return family recorded for the derived finite-candidate view."""

    discount_gamma: float = Field(default=1.0, ge=0.0)
    """Discount applied only to non-terminal selected TD transitions."""

    target_protocol_version: TargetInputProtocol = TargetInputProtocol.V0_GT_INPUT
    """Contract version separating target task inputs from oracle labels."""

    reason_code_version: str = INVALID_REASON_VERSION
    """Version of persisted candidate-invalidity bit positions."""

    field_retention_policy: str = "compact"
    """Named policy describing which heavy oracle/audit payloads are retained."""

    source_offline_store_version: str = "unknown-source-version"
    """Immutable VIN source-cache version copied into rollout provenance."""

    split_manifest_hash: str = "unknown-split-manifest"
    """Hash binding the source split and ordered row ownership records."""

    q_h_chunk_states: int = Field(default=64, ge=1)
    """Number of state rows per chunk in the persisted derived ``q_h/`` view."""

    target_eval_crop_max_points: int = Field(default=DEFAULT_TARGET_EVAL_CROP_MAX_POINTS, ge=1)
    """Fixed row width for oracle/eval target crop point payloads."""

    target_eval_crops_enabled: bool = False
    """Persist oracle/eval target crop point payloads for sampled audit shards."""

    _resolve_store_dir = field_validator("store_dir", mode="before")(resolve_cache_artifact_dir)


class RolloutZarrStoreReader:
    """Open a completed standalone rollout replay store in read-only mode.

    The reader never repairs, migrates, or backfills arrays. Canonical factual
    tables remain the source of truth; ``q_h/`` is a validated derived cache.
    """

    def __init__(self, store_dir: Path | str) -> None:
        self.store_dir = Path(store_dir).expanduser().resolve()
        self.root = zarr.open_group(store=LocalStore(str(self.store_dir), read_only=True), mode="r")

    def array(self, path: str) -> np.ndarray:
        """Read an array by slash-separated Zarr path."""

        return np.asarray(self.root[path])

    def validate(self) -> RolloutZarrValidationResult:
        """Validate row linkage, masks, and initial ``Q_H`` target availability."""

        return validate_rollout_zarr_store(self.store_dir)

    def manifest(self) -> dict[str, Any]:
        """Read root attrs and the top-level sidecar manifest without payload arrays."""

        return {
            "root_attrs": dict(self.root.attrs),
            "manifest": read_rollout_store_manifest(self.store_dir),
        }

    def q_h_view(self, *, discount_gamma: float | None = None) -> dict[str, np.ndarray]:
        """Return the padded finite-candidate ``Q_H`` training view.

        Let ``S`` be the number of materialized step/state rows and ``A`` the
        maximum step-local full-shell width. Candidate ids, masks, positions,
        one-step labels, and reason bitsets are ``ndarray["S A", ...]``;
        source/target ids, selected-action indices, and TD linkage are
        ``ndarray["S", ...]``. Shorter shells are padded with id ``-1``, false
        masks, and ``NaN`` labels.

        ``valid_action_mask`` is the hard actor-selectable mask.
        ``q_train_mask`` is stricter: it also requires a label-valid target/GT
        state and finite explicit target-root-gain and target-RRI labels.
        Invalidity is represented by masks and versioned reason bitsets, never
        by a low score. TD reward/linkage describes the factual selected action
        only; unselected action labels remain one-step oracle supervision.

        Args:
            discount_gamma: When ``None``, read the persisted ``q_h/`` cache.
                Otherwise rebuild the view from canonical factual tables using
                this discount for non-terminal selected transitions.

        Returns:
            Mapping containing all :data:`Q_H_ARRAY_NAMES`, preserving the
            ``S`` state axis and padded ``A`` full-shell action axis.
        """

        if discount_gamma is None and "q_h" in self.root:
            return _read_q_h_arrays(self.root)
        gamma = float(self.root.attrs.get("discount_gamma", 1.0) if discount_gamma is None else discount_gamma)
        return _build_q_h_arrays(_read_tables_from_root(self.root), gamma=gamma)


def write_rollout_zarr_store(
    store_dir: Path | str,
    records: Sequence[_RolloutWriteRecord],
    *,
    return_semantics: str = DEFAULT_RETURN_SEMANTICS,
    discount_gamma: float = 1.0,
    target_protocol_version: TargetInputProtocol | str = TargetInputProtocol.V0_GT_INPUT,
    reason_code_version: str = INVALID_REASON_VERSION,
    field_retention_policy: str = "compact",
    source_offline_store_version: str = "unknown-source-version",
    split_manifest_hash: str = "unknown-split-manifest",
    manifest_context: RolloutStoreManifestContext | None = None,
    selected_depth_enabled: bool = True,
    selected_depth_width_px: int = 240,
    selected_depth_height_px: int = 240,
    selected_depth_chunk_steps: int = 16,
    selected_depth_renderer: str = "Pytorch3DDepthRenderer",
    selected_depth_znear_m: float | None = 1e-3,
    selected_depth_zfar_m: float | None = 20.0,
    selected_depth_source_resolution: str = "exact_output_size",
    q_h_chunk_states: int = 64,
    target_eval_crop_max_points: int = DEFAULT_TARGET_EVAL_CROP_MAX_POINTS,
    target_eval_crops_enabled: bool = False,
) -> RolloutZarrWriteResult:
    """Replace a standalone destination with normalized rollout replay tables.

    Candidate shells remain complete in the factual tables; valid-only oracle
    vectors are expanded through masks, and ``q_h/`` is derived from the
    normalized step/candidate rows. Selected mesh depth and optional target
    evaluation crops remain rollout-owned oracle/audit artifacts.

    Args:
        store_dir: Destination directory opened in Zarr write mode. A direct
            call replaces existing content at this path.
        records: Root-target-recipe rollout results with source/target lineage.
        return_semantics: Versioned return family recorded on the derived view.
        discount_gamma: Discount for non-terminal selected TD transitions.
        target_protocol_version: Target input/label boundary contract.
        reason_code_version: Candidate-invalidity code-table version.
        field_retention_policy: Named heavy-field retention policy.
        source_offline_store_version: Immutable VIN source-cache version.
        split_manifest_hash: Hash of split and ordered source-row ownership.
        manifest_context: Optional resolved config, invocation, runtime, and
            shard provenance for the sidecar.
        selected_depth_enabled: Whether selected-only oracle depth is retained.
        selected_depth_width_px: Selected-depth raster width in pixels.
        selected_depth_height_px: Selected-depth raster height in pixels.
        selected_depth_chunk_steps: Selected-depth rows per Zarr chunk.
        selected_depth_renderer: Renderer identity stored as provenance.
        selected_depth_znear_m: Near clipping distance in metres.
        selected_depth_zfar_m: Far clipping distance in metres.
        selected_depth_source_resolution: Resolution-policy provenance label.
        q_h_chunk_states: State rows per derived-view chunk.
        target_eval_crop_max_points: Fixed point width ``P_max`` for audit crops.
        target_eval_crops_enabled: Whether optional oracle target crops persist.

    Returns:
        Row counts, resolved destination, and sidecar manifest digest.

    Notes:
        This low-level direct writer is not a temp-to-final transaction. Use the
        rollout shard runner for validated atomic promotion. In either path the
        VIN source cache is opened only as an input and is never modified.
    """

    return _RolloutZarrWriteSession(
        store_dir=store_dir,
        records=records,
        return_semantics=return_semantics,
        discount_gamma=discount_gamma,
        target_protocol_version=target_protocol_version,
        reason_code_version=reason_code_version,
        field_retention_policy=field_retention_policy,
        source_offline_store_version=source_offline_store_version,
        split_manifest_hash=split_manifest_hash,
        manifest_context=manifest_context,
        selected_depth_enabled=selected_depth_enabled,
        selected_depth_width_px=selected_depth_width_px,
        selected_depth_height_px=selected_depth_height_px,
        selected_depth_chunk_steps=selected_depth_chunk_steps,
        selected_depth_renderer=selected_depth_renderer,
        selected_depth_znear_m=selected_depth_znear_m,
        selected_depth_zfar_m=selected_depth_zfar_m,
        selected_depth_source_resolution=selected_depth_source_resolution,
        q_h_chunk_states=q_h_chunk_states,
        target_eval_crop_max_points=target_eval_crop_max_points,
        target_eval_crops_enabled=target_eval_crops_enabled,
    ).write()


class _RolloutZarrWriteSession:
    """Own one write of a rollout Zarr store and its derived row tables."""

    def __init__(
        self,
        *,
        store_dir: Path | str,
        records: Sequence[_RolloutWriteRecord],
        return_semantics: str,
        discount_gamma: float,
        target_protocol_version: str,
        reason_code_version: str,
        field_retention_policy: str,
        source_offline_store_version: str,
        split_manifest_hash: str,
        manifest_context: RolloutStoreManifestContext | None,
        selected_depth_enabled: bool,
        selected_depth_width_px: int,
        selected_depth_height_px: int,
        selected_depth_chunk_steps: int,
        selected_depth_renderer: str,
        selected_depth_znear_m: float | None,
        selected_depth_zfar_m: float | None,
        selected_depth_source_resolution: str,
        q_h_chunk_states: int,
        target_eval_crop_max_points: int,
        target_eval_crops_enabled: bool,
    ) -> None:
        self.output_dir = Path(store_dir).expanduser().resolve()
        self.records = list(records)
        self.return_semantics = return_semantics
        self.discount_gamma = float(discount_gamma)
        self.target_protocol_version = str(target_protocol_version)
        self.reason_code_version = reason_code_version
        self.field_retention_policy = field_retention_policy
        self.source_offline_store_version = source_offline_store_version
        self.split_manifest_hash = split_manifest_hash
        self.manifest_context = manifest_context or RolloutStoreManifestContext.programmatic()
        self.selected_depth_enabled = bool(selected_depth_enabled)
        self.selected_depth_width_px = int(selected_depth_width_px)
        self.selected_depth_height_px = int(selected_depth_height_px)
        self.selected_depth_chunk_steps = int(selected_depth_chunk_steps)
        self.selected_depth_renderer = str(selected_depth_renderer)
        self.selected_depth_znear_m = selected_depth_znear_m
        self.selected_depth_zfar_m = selected_depth_zfar_m
        self.selected_depth_source_resolution = str(selected_depth_source_resolution)
        self.q_h_chunk_states = int(q_h_chunk_states)
        self.target_eval_crop_max_points = int(target_eval_crop_max_points)
        self.target_eval_crops_enabled = bool(target_eval_crops_enabled)
        if self.selected_depth_width_px < 1 or self.selected_depth_height_px < 1:
            raise ValueError("selected_depth_width_px and selected_depth_height_px must be positive.")
        if self.selected_depth_chunk_steps < 1:
            raise ValueError("selected_depth_chunk_steps must be positive.")
        if self.q_h_chunk_states < 1:
            raise ValueError("q_h_chunk_states must be positive.")
        if self.target_eval_crop_max_points < 1:
            raise ValueError("target_eval_crop_max_points must be positive.")

    def write(self) -> RolloutZarrWriteResult:
        """Materialize the configured rollout traces to disk."""

        created_at_utc = utc_timestamp()
        records = _records_with_global_target_row_ids(self.records)
        dictionaries = _build_dictionaries(records)
        table = _flatten_records(
            records,
            dictionaries,
            selected_depth_width_px=self.selected_depth_width_px,
            selected_depth_height_px=self.selected_depth_height_px,
            target_eval_crop_max_points=self.target_eval_crop_max_points,
            target_eval_crops_enabled=self.target_eval_crops_enabled,
        )
        q_h_horizon = _table_horizon(table)
        q_h_arrays = _build_q_h_arrays(table, gamma=self.discount_gamma)
        root_metadata = _root_metadata_payload(
            records=records,
            tables=table,
            q_h_arrays=q_h_arrays,
            q_h_horizon=q_h_horizon,
            q_h_chunk_states=self.q_h_chunk_states,
            return_semantics=self.return_semantics,
            discount_gamma=self.discount_gamma,
            target_protocol_version=self.target_protocol_version,
            reason_code_version=self.reason_code_version,
            field_retention_policy=self.field_retention_policy,
            source_offline_store_version=self.source_offline_store_version,
            split_manifest_hash=self.split_manifest_hash,
            selected_depth_enabled=self.selected_depth_enabled,
            selected_depth_width_px=self.selected_depth_width_px,
            selected_depth_height_px=self.selected_depth_height_px,
            selected_depth_chunk_steps=self.selected_depth_chunk_steps,
            selected_depth_renderer=self.selected_depth_renderer,
            selected_depth_znear_m=self.selected_depth_znear_m,
            selected_depth_zfar_m=self.selected_depth_zfar_m,
            selected_depth_source_resolution=self.selected_depth_source_resolution,
            target_eval_crop_max_points=self.target_eval_crop_max_points,
            target_eval_crops_enabled=self.target_eval_crops_enabled,
            created_at_utc=created_at_utc,
            manifest_sha256="",
        )
        manifest_payload = _build_manifest_payload(
            records=records,
            tables=table,
            q_h_arrays=q_h_arrays,
            dictionaries=dictionaries,
            context=self.manifest_context,
            root_attrs=root_metadata,
            created_at_utc=created_at_utc,
        )
        manifest_digest = manifest_sha256(manifest_payload)
        root_metadata["manifest_sha256"] = manifest_digest

        root = zarr.open_group(str(self.output_dir), mode="w")
        root.attrs.update(root_metadata)
        groups = {name: root.create_group(name, overwrite=True) for name in _required_groups()}

        _write_dictionaries(groups["dictionaries"], dictionaries)
        _write_metadata_group(groups["metadata"], field_retention_policy=self.field_retention_policy)
        _write_targets(
            groups["targets"],
            records,
            dictionaries,
            target_protocol_version=self.target_protocol_version,
        )

        _write_rollout_tables(groups, table)
        _write_selected_depth_group(
            groups["selected_depth"],
            table.selected_depth,
            enabled=self.selected_depth_enabled,
            width_px=self.selected_depth_width_px,
            height_px=self.selected_depth_height_px,
            chunk_steps=self.selected_depth_chunk_steps,
            renderer=self.selected_depth_renderer,
            znear_m=self.selected_depth_znear_m,
            zfar_m=self.selected_depth_zfar_m,
            source_resolution=self.selected_depth_source_resolution,
        )
        _write_target_eval_crops_group(
            groups["target_eval_crops"],
            table.target_eval_crops,
            dictionaries=dictionaries,
            max_points=self.target_eval_crop_max_points,
            enabled=self.target_eval_crops_enabled,
        )
        _write_q_h_group(
            groups["q_h"],
            q_h_arrays,
            chunk_states=self.q_h_chunk_states,
            horizon=q_h_horizon,
            gamma=self.discount_gamma,
            return_semantics=self.return_semantics,
        )
        written_manifest_digest = write_rollout_store_manifest(self.output_dir, manifest_payload)
        if written_manifest_digest != manifest_digest:
            raise RuntimeError("Rollout manifest digest changed while writing.")

        return RolloutZarrWriteResult(
            store_dir=self.output_dir,
            num_rollouts=int(table.rollouts["rollout_row_id"].shape[0]),
            num_steps=int(table.steps["step_row_id"].shape[0]),
            num_candidates=int(table.candidates["candidate_row_id"].shape[0]),
            manifest_path=self.output_dir / ROLLOUT_MANIFEST_FILENAME,
            manifest_sha256=manifest_digest,
        )


def validate_rollout_zarr_store(store_dir: Path | str) -> RolloutZarrValidationResult:
    """Validate a standalone rollout replay store and return all discovered errors."""

    return _RolloutZarrValidator(store_dir).validate()


class _RolloutZarrValidator:
    """Validate one rollout store without mixing checks into the public facade."""

    def __init__(self, store_dir: Path | str) -> None:
        self.store_dir = Path(store_dir).expanduser().resolve()
        self.root = zarr.open_group(
            store=LocalStore(str(self.store_dir), read_only=True),
            mode="r",
        )
        self.errors: list[str] = []

    def validate(self) -> RolloutZarrValidationResult:
        """Validate row linkage, masks, target validity, and lineage."""

        self._validate_root_contract()
        if self.errors:
            return RolloutZarrValidationResult(self.store_dir, 0, 0, 0, self.errors)

        candidate_row_id = np.asarray(self.root["candidates/candidate_row_id"])
        self._validate_q_h(candidate_row_id)
        self._validate_candidates(candidate_row_id)
        self._validate_candidate_diagnostics(candidate_row_id)
        self._validate_selected_depth()
        self._validate_target_eval_crops()
        self._validate_sources()
        self._validate_targets()
        self._validate_required_lineage()

        return RolloutZarrValidationResult(
            store_dir=self.store_dir,
            num_rollouts=int(np.asarray(self.root["rollouts/rollout_row_id"]).shape[0]),
            num_steps=int(np.asarray(self.root["steps/step_row_id"]).shape[0]),
            num_candidates=int(candidate_row_id.shape[0]),
            errors=self.errors,
        )

    def _validate_root_contract(self) -> None:
        if self.root.attrs.get("schema_version") != ROLLOUT_ZARR_SCHEMA_VERSION:
            self.errors.append(
                f"Unsupported rollout Zarr schema_version={self.root.attrs.get('schema_version')!r}; "
                f"expected {ROLLOUT_ZARR_SCHEMA_VERSION!r}."
            )
        self._validate_manifest_contract()
        for group_name in _required_groups():
            if group_name not in self.root:
                self.errors.append(f"Missing required group {group_name!r}.")

    def _validate_manifest_contract(self) -> None:
        manifest_path_attr = self.root.attrs.get("manifest_path")
        if manifest_path_attr != ROLLOUT_MANIFEST_FILENAME:
            self.errors.append(
                f"Rollout store root attr 'manifest_path' must be {ROLLOUT_MANIFEST_FILENAME!r}, "
                f"got {manifest_path_attr!r}."
            )
            return
        manifest_path = self.store_dir / ROLLOUT_MANIFEST_FILENAME
        if not manifest_path.exists():
            self.errors.append(f"Missing required top-level rollout manifest {manifest_path.name!r}.")
            return
        try:
            payload = read_rollout_store_manifest(self.store_dir)
        except (OSError, json.JSONDecodeError) as exc:
            self.errors.append(f"Failed to read rollout manifest: {exc}.")
            return
        expected_hash = self.root.attrs.get("manifest_sha256")
        if not isinstance(expected_hash, str) or not expected_hash:
            self.errors.append("Rollout store root attr 'manifest_sha256' is missing.")
        elif manifest_sha256(payload) != expected_hash:
            self.errors.append("Rollout store manifest hash does not match root attr 'manifest_sha256'.")
        if payload.get("manifest_version") != ROLLOUT_MANIFEST_VERSION:
            self.errors.append(
                f"Unsupported rollout manifest_version={payload.get('manifest_version')!r}; "
                f"expected {ROLLOUT_MANIFEST_VERSION!r}."
            )
        if payload.get("schema_version") != ROLLOUT_ZARR_SCHEMA_VERSION:
            self.errors.append("Rollout manifest schema_version does not match the current rollout Zarr schema.")

    def _validate_q_h(self, candidate_row_id: np.ndarray) -> None:
        derived = _build_q_h_arrays(
            _read_tables_from_root(self.root),
            gamma=float(self.root.attrs.get("discount_gamma", 1.0)),
        )
        persisted = _read_q_h_arrays_if_present(self.root)
        missing = [name for name in Q_H_ARRAY_NAMES if name not in persisted]
        if missing:
            self.errors.append(f"Missing q_h arrays: {missing}.")
            q_h = derived
        else:
            self._validate_persisted_q_h(persisted, derived)
            q_h = persisted
        q_candidate_row_id = q_h["candidate_row_id"]
        q_train_mask = q_h["q_train_mask"]
        valid_action_mask = q_h["valid_action_mask"]
        one_step_target_rri = q_h["one_step_target_rri"]
        one_step_target_root_gain = q_h["one_step_target_root_gain"]
        td_terminal_mask = q_h["td_terminal_mask"]
        td_discount = q_h["td_discount"]

        real_q_ids = q_candidate_row_id[q_candidate_row_id >= 0]
        if not np.isin(real_q_ids, candidate_row_id).all():
            self.errors.append("Q_H candidate_row_id contains ids not present in candidates/candidate_row_id.")
        if np.any(q_train_mask & (~valid_action_mask)):
            self.errors.append("Q_H q_train_mask is true for invalid candidates.")
        if np.any(q_train_mask & (~np.isfinite(one_step_target_root_gain))):
            self.errors.append("Q_H q_train_mask is true without a finite explicit target-root-gain reward.")
        if np.any(q_train_mask & (~np.isfinite(one_step_target_rri))):
            self.errors.append("Q_H q_train_mask is true without a finite diagnostic target-RRI label.")
        if np.any(td_terminal_mask & (td_discount != 0.0)):
            self.errors.append("Q_H td_discount must be zero for terminal selected transitions.")

    def _validate_persisted_q_h(self, persisted: dict[str, np.ndarray], derived: dict[str, np.ndarray]) -> None:
        group = self.root["q_h"]
        expected_state_count = int(derived["state_step_row_id"].shape[0])
        expected_max_candidates = (
            int(derived["candidate_row_id"].shape[1]) if derived["candidate_row_id"].ndim == 2 else 0
        )
        if int(group.attrs.get("state_count", -1)) != expected_state_count:
            self.errors.append("q_h/state_count attr does not match the derived state count.")
        if int(group.attrs.get("max_candidates", -1)) != expected_max_candidates:
            self.errors.append("q_h/max_candidates attr does not match the derived candidate width.")
        if int(group.attrs.get("horizon", -1)) != _stored_horizon(self.root):
            self.errors.append("q_h/horizon attr does not match rollouts/horizon.")
        if float(group.attrs.get("discount_gamma", float("nan"))) != float(self.root.attrs.get("discount_gamma", 1.0)):
            self.errors.append("q_h/discount_gamma attr does not match root discount_gamma.")
        if group.attrs.get("td_semantics") != Q_H_TD_SEMANTICS:
            self.errors.append(f"q_h/td_semantics must be {Q_H_TD_SEMANTICS!r}.")
        if group.attrs.get("reward_metric") != Q_H_REWARD_METRIC:
            self.errors.append(f"q_h/reward_metric must be {Q_H_REWARD_METRIC!r}.")
        if group.attrs.get("return_semantics") != self.root.attrs.get("return_semantics"):
            self.errors.append("q_h/return_semantics attr does not match root return_semantics.")

        for name in Q_H_ARRAY_NAMES:
            actual = persisted[name]
            expected = derived[name]
            if actual.shape != expected.shape:
                self.errors.append(f"q_h/{name} shape {actual.shape} does not match derived shape {expected.shape}.")
                continue
            if np.dtype(actual.dtype) != np.dtype(expected.dtype):
                self.errors.append(f"q_h/{name} dtype {actual.dtype} does not match derived dtype {expected.dtype}.")
                continue
            if _q_h_arrays_differ(actual, expected):
                self.errors.append(f"q_h/{name} does not match the derived factual-table view.")

    def _validate_candidates(self, candidate_row_id: np.ndarray) -> None:
        selected_mask = np.asarray(self.root["candidates/selected_mask"])
        actor_action_mask = np.asarray(self.root["candidates/actor_action_mask"])
        if np.any(selected_mask & (~actor_action_mask)):
            self.errors.append("Selected candidates must be actor-selectable.")
        if np.any(actor_action_mask & (np.asarray(self.root["candidates/position_id"]) < 0)):
            self.errors.append("Actor-selectable candidates require non-placeholder position_id.")

        rollout_split_id = np.asarray(self.root["rollouts/split_id"])
        if np.unique(rollout_split_id).shape[0] > 1:
            self.errors.append("A rollout shard must contain exactly one split.")

        for name, array in self.root["candidates"].arrays():
            if int(array.shape[0]) != int(candidate_row_id.shape[0]):
                self.errors.append(
                    f"Candidate table field {name!r} has {array.shape[0]} rows, expected {candidate_row_id.shape[0]}."
                )

    def _validate_candidate_diagnostics(self, candidate_row_id: np.ndarray) -> None:
        if "candidate_diagnostics" not in self.root:
            self.errors.append("Missing required group 'candidate_diagnostics'.")
            return
        group = self.root["candidate_diagnostics"]
        missing = [name for name in CANDIDATE_DIAGNOSTIC_TABLE.names if name not in group]
        if missing:
            self.errors.append(f"Missing candidate_diagnostics arrays: {missing}.")
            return
        diag_candidate_row_id = np.asarray(group["candidate_row_id"], dtype=np.int64)
        if not np.array_equal(diag_candidate_row_id, candidate_row_id.astype(np.int64)):
            self.errors.append("candidate_diagnostics/candidate_row_id must align with candidates/candidate_row_id.")
        for table_field in CANDIDATE_DIAGNOSTIC_TABLE.fields:
            array = np.asarray(group[table_field.name])
            if int(array.shape[0]) != int(candidate_row_id.shape[0]):
                self.errors.append(
                    f"Candidate diagnostic field {table_field.name!r} has {array.shape[0]} rows, "
                    f"expected {candidate_row_id.shape[0]}."
                )
            if np.dtype(array.dtype) != np.dtype(table_field.dtype):
                self.errors.append(
                    f"Candidate diagnostic field {table_field.name!r} dtype {array.dtype} "
                    f"must be {np.dtype(table_field.dtype)}."
                )
        collision_mask = np.asarray(group["path_collision_mask"], dtype=np.bool_).reshape(-1)
        if collision_mask.any():
            actor_action_mask = np.asarray(self.root["candidates/actor_action_mask"], dtype=np.bool_).reshape(-1)
            reason_bitset = np.asarray(self.root["candidates/invalid_reason_bitset"], dtype=np.uint32).reshape(-1)
            path_bit = np.uint32(1 << INVALID_REASON_CODES["PATH_SEGMENT_COLLISION"])
            if np.any(collision_mask & actor_action_mask):
                self.errors.append("Path-colliding candidates must not be actor-selectable.")
            if np.any(collision_mask & ((reason_bitset & path_bit) == 0)):
                self.errors.append("path_collision_mask rows must include PATH_SEGMENT_COLLISION invalidity bits.")

    def _validate_selected_depth(self) -> None:
        if not bool(self.root.attrs.get("selected_depth_enabled", False)):
            return

        group = self.root["selected_depth"]
        required = set(SELECTED_DEPTH_TABLE.names) | {"depth_m", "valid_mask"}
        missing = sorted(name for name in required if name not in group)
        if missing:
            self.errors.append(f"Missing selected_depth arrays: {missing}.")
            return

        step_row_id = np.asarray(self.root["steps/step_row_id"], dtype=np.int64)
        selected_candidate_row_id = np.asarray(self.root["steps/selected_candidate_row_id"], dtype=np.int64)
        depth_step_row_id = np.asarray(group["step_row_id"], dtype=np.int64)
        depth_candidate_row_id = np.asarray(group["candidate_row_id"], dtype=np.int64)
        if not np.array_equal(depth_step_row_id, step_row_id):
            self.errors.append("selected_depth/step_row_id must contain exactly one row for every rollout step.")
        if not np.array_equal(depth_candidate_row_id, selected_candidate_row_id):
            self.errors.append("selected_depth/candidate_row_id must align with steps/selected_candidate_row_id.")

        expected_shape = (
            int(step_row_id.shape[0]),
            int(self.root.attrs.get("selected_depth_height_px", -1)),
            int(self.root.attrs.get("selected_depth_width_px", -1)),
        )
        depth_m = group["depth_m"]
        valid_mask = group["valid_mask"]
        if tuple(depth_m.shape) != expected_shape:
            self.errors.append(f"selected_depth/depth_m shape {depth_m.shape} must equal {expected_shape}.")
        if tuple(valid_mask.shape) != expected_shape:
            self.errors.append(f"selected_depth/valid_mask shape {valid_mask.shape} must equal {expected_shape}.")
        if np.dtype(depth_m.dtype) != np.dtype(np.float16):
            self.errors.append("selected_depth/depth_m must be float16.")
        if np.dtype(valid_mask.dtype) != np.dtype(np.bool_):
            self.errors.append("selected_depth/valid_mask must be bool.")
        for name in ("focal_px", "principal_point_px", "image_size_hw"):
            if tuple(group[name].shape) != (int(step_row_id.shape[0]), 2):
                self.errors.append(f"selected_depth/{name} must have shape (num_steps, 2).")

    def _validate_target_eval_crops(self) -> None:
        if "target_eval_crops" not in self.root:
            self.errors.append("Missing required group 'target_eval_crops'.")
            return
        group = self.root["target_eval_crops"]
        if not bool(self.root.attrs.get("target_eval_crops_enabled", False)):
            if int(np.asarray(group["crop_row_id"]).shape[0]) != 0:
                self.errors.append("target_eval_crops must be empty when target_eval_crops_enabled is false.")
            return
        required = set(TARGET_EVAL_CROP_TABLE.names) | {"points_world", "mask", "source_role_names"}
        missing = sorted(name for name in required if name not in group)
        if missing:
            self.errors.append(f"Missing target_eval_crops arrays: {missing}.")
            return
        if group.attrs.get("role") != "oracle_eval_only":
            self.errors.append("target_eval_crops/role attr must be 'oracle_eval_only'.")
        if group.attrs.get("coordinate_frame") != "world":
            self.errors.append("target_eval_crops/coordinate_frame attr must be 'world'.")
        points = np.asarray(group["points_world"])
        mask = np.asarray(group["mask"])
        lengths = np.asarray(group["lengths"], dtype=np.int32)
        crop_row_id = np.asarray(group["crop_row_id"], dtype=np.int64)
        if points.ndim != 3 or points.shape[-1] != 3:
            self.errors.append("target_eval_crops/points_world must have shape (rows,max_points,3).")
            return
        if mask.shape != points.shape[:2]:
            self.errors.append("target_eval_crops/mask must align with points_world rows and point width.")
            return
        if lengths.shape != (points.shape[0],):
            self.errors.append("target_eval_crops/lengths must have one value per crop row.")
            return
        if crop_row_id.shape != (points.shape[0],):
            self.errors.append("target_eval_crops/crop_row_id must have one value per crop row.")
            return
        if not np.array_equal(crop_row_id, np.arange(points.shape[0], dtype=np.int64)):
            self.errors.append("target_eval_crops/crop_row_id must be contiguous from zero.")
        if np.any(lengths < 0) or np.any(lengths > points.shape[1]):
            self.errors.append("target_eval_crops/lengths must be within the fixed point width.")
        if not np.array_equal(mask.sum(axis=1).astype(np.int32), lengths):
            self.errors.append("target_eval_crops/mask true counts must equal lengths.")
        if points.shape[1] != int(self.root.attrs.get("target_eval_crops_max_points", points.shape[1])):
            self.errors.append("target_eval_crops point width must match root target_eval_crops_max_points.")
        step_row_id = np.asarray(self.root["steps/step_row_id"], dtype=np.int64)
        crop_step_row_id = np.asarray(group["step_row_id"], dtype=np.int64)
        if crop_step_row_id.size and not np.isin(crop_step_row_id, step_row_id).all():
            self.errors.append("target_eval_crops/step_row_id contains ids not present in steps/step_row_id.")
        source_role_id = np.asarray(group["source_role_id"], dtype=np.int32)
        if source_role_id.size and not np.isin(source_role_id, np.asarray([0, 1], dtype=np.int32)).all():
            self.errors.append("target_eval_crops/source_role_id must be current_eval=0 or candidate_eval=1.")
        candidate_row_id = np.asarray(group["candidate_row_id"], dtype=np.int64)
        candidate_rows = np.asarray(self.root["candidates/candidate_row_id"], dtype=np.int64)
        candidate_refs = candidate_row_id[source_role_id == 1]
        current_refs = candidate_row_id[source_role_id == 0]
        if current_refs.size and np.any(current_refs != -1):
            self.errors.append("target_eval_crops current_eval rows must use candidate_row_id=-1.")
        if candidate_refs.size and not np.isin(candidate_refs, candidate_rows).all():
            self.errors.append("target_eval_crops candidate_eval rows reference missing candidates.")

    def _validate_sources(self) -> None:
        source_row_id = np.asarray(self.root["sources/source_row_id"])
        rollout_source_row_id = np.asarray(self.root["rollouts/source_row_id"])
        if not np.isin(rollout_source_row_id, source_row_id).all():
            self.errors.append("Rollout source_row_id contains ids not present in sources/source_row_id.")
        if np.unique(source_row_id).shape[0] != source_row_id.shape[0]:
            self.errors.append("sources/source_row_id must be unique within one rollout shard.")
        source_shard_id = np.asarray(self.root["sources/source_shard_id"])
        source_shard_row = np.asarray(self.root["sources/source_shard_row"])
        try:
            source_shard_names = _read_string_array(self.root, "dictionaries/source_shard")
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.errors.append(f"Failed to read source_shard dictionary: {exc}.")
            return
        for value in source_shard_id:
            shard_index = int(value)
            if shard_index < 0 or shard_index >= len(source_shard_names) or not source_shard_names[shard_index]:
                self.errors.append("sources/source_shard_id must reference non-empty VIN source shard ids.")
                break
        if np.any(source_shard_row < 0):
            self.errors.append("sources/source_shard_row must be non-negative.")

    def _validate_targets(self) -> None:
        target_row_id = np.asarray(self.root["targets/target_row_id"])
        rollout_target_row_id = np.asarray(self.root["rollouts/target_row_id"])
        if not np.isin(rollout_target_row_id, target_row_id).all():
            self.errors.append("Rollout target_row_id contains ids not present in targets/target_row_id.")
        if np.unique(target_row_id).shape[0] != target_row_id.shape[0]:
            self.errors.append("targets/target_row_id must be unique within one rollout shard.")
        target_source_ids = np.asarray(self.root["targets/target_source_id"], dtype=np.int64).reshape(-1)
        target_sources = _read_string_array(self.root, "dictionaries/target_source")
        if target_source_ids.shape != target_row_id.shape:
            self.errors.append("targets/target_source_id must have one value per target row.")
        elif np.any((target_source_ids < 0) | (target_source_ids >= len(target_sources))):
            self.errors.append("targets/target_source_id contains an out-of-range dictionary id.")
        else:
            try:
                target_protocol = TargetInputProtocol(
                    str(self.root.attrs.get("target_protocol_version", "")).replace("-", "_")
                )
            except (TypeError, ValueError):
                target_protocol = None
            if target_protocol is None:
                self.errors.append("Rollout store declares an unsupported target protocol version.")
            else:
                actor_visible_sources = {source.value for source in ActorVisibleTargetSource}
                for source_id in target_source_ids.tolist():
                    target_source = target_sources[int(source_id)]
                    if target_protocol is TargetInputProtocol.V0_GT_INPUT:
                        admitted = target_source in {"", ORACLE_GT_TARGET_SOURCE}
                    else:
                        admitted = target_source in actor_visible_sources
                    if not admitted:
                        self.errors.append(
                            f"targets/target_source_id contains source {target_source!r} incompatible with "
                            f"{target_protocol.value}."
                        )
                        break
                    try:
                        validate_target_protocol_admission(
                            target_protocol,
                            target_source=target_source or ORACLE_GT_TARGET_SOURCE,
                            descriptor_source=target_source or ORACLE_GT_TARGET_SOURCE,
                            descriptor_provenance=(
                                "actor_visible_detector"
                                if target_protocol is TargetInputProtocol.V1_OBSERVED
                                else "oracle_gt"
                            ),
                        )
                    except ValueError as exc:
                        self.errors.append(f"Invalid target source admission: {exc}")
                        break
        target_reason = np.asarray(self.root["targets/target_invalid_reason_bitset"], dtype=np.uint32).reshape(-1)
        target_valid = np.asarray(self.root["targets/target_valid_mask"], dtype=np.bool_).reshape(-1)
        expected_target_valid = target_reason == np.uint32(1 << INVALID_REASON_CODES["VALID"])
        if target_valid.shape != target_row_id.shape or target_reason.shape != target_row_id.shape:
            self.errors.append("Target validity arrays must have one value per target row.")
        elif not np.array_equal(target_valid, expected_target_valid):
            self.errors.append("targets/target_valid_mask does not match target_invalid_reason_bitset.")
        if "root_pose_world" not in self.root["rollouts"]:
            self.errors.append("Missing required rollout root_pose_world field.")
        else:
            root_pose_world = np.asarray(self.root["rollouts/root_pose_world"])
            if root_pose_world.shape != (int(np.asarray(self.root["rollouts/rollout_row_id"]).shape[0]), 12):
                self.errors.append("rollouts/root_pose_world must have shape (num_rollouts, 12).")
            elif not np.isfinite(root_pose_world).all():
                self.errors.append("rollouts/root_pose_world contains non-finite values.")
        rollout_count = int(np.asarray(self.root["rollouts/rollout_row_id"]).shape[0])
        for name in ("root_time_ns", "root_trajectory_index", "root_frame_index"):
            if name not in self.root["rollouts"]:
                self.errors.append(f"Missing required rollout {name} field.")
            elif np.asarray(self.root[f"rollouts/{name}"]).shape != (rollout_count,):
                self.errors.append(f"rollouts/{name} must have shape (num_rollouts,).")

        q_state_target_row_id = _q_h_arrays_for_validation(self.root)["target_row_id"]
        step_rollout_row_id = np.asarray(self.root["steps/rollout_row_id"])
        rollout_row_id = np.asarray(self.root["rollouts/rollout_row_id"])
        target_by_rollout = {
            int(row_id): int(target) for row_id, target in zip(rollout_row_id, rollout_target_row_id, strict=True)
        }
        expected_state_target = np.asarray(
            [target_by_rollout.get(int(row_id), -1) for row_id in step_rollout_row_id], dtype=np.int64
        )
        if q_state_target_row_id.shape == expected_state_target.shape and not np.array_equal(
            q_state_target_row_id, expected_state_target
        ):
            self.errors.append("Q_H target_row_id does not match the parent rollout target_row_id.")
        elif q_state_target_row_id.shape != expected_state_target.shape:
            self.errors.append("Q_H target_row_id shape does not match the steps table.")
        self._validate_target_source_lineage(target_row_id=target_row_id, rollout_target_row_id=rollout_target_row_id)

    def _validate_target_source_lineage(
        self,
        *,
        target_row_id: np.ndarray,
        rollout_target_row_id: np.ndarray,
    ) -> None:
        """Validate that store-global target rows do not mix VIN source snippets."""

        rollout_source_row_id = np.asarray(self.root["rollouts/source_row_id"], dtype=np.int64).reshape(-1)
        if rollout_source_row_id.shape != rollout_target_row_id.shape:
            self.errors.append("rollouts/source_row_id and rollouts/target_row_id must have the same shape.")
            return

        for row_id in target_row_id.tolist():
            target_rollout_positions = np.nonzero(rollout_target_row_id == int(row_id))[0]
            if target_rollout_positions.size == 0:
                continue
            source_ids = set(rollout_source_row_id[target_rollout_positions].astype(int).tolist())
            if len(source_ids) > 1:
                self.errors.append(
                    f"targets/target_row_id={int(row_id)} is referenced by multiple source_row_id values: "
                    f"{sorted(source_ids)}."
                )

        target_id_by_row_position = {int(row_id): index for index, row_id in enumerate(target_row_id.tolist())}
        target_ids = _encoded_values(self.root, dictionary_name="target", array_path="targets/target_id")
        matched_gt_target_ids = _encoded_values(
            self.root,
            dictionary_name="target",
            array_path="targets/matched_gt_target_id",
        )
        rollout_snippets = _encoded_values(self.root, dictionary_name="snippet", array_path="rollouts/snippet_id")
        for rollout_index, row_id in enumerate(rollout_target_row_id.astype(int).tolist()):
            target_index = target_id_by_row_position.get(row_id)
            if target_index is None or rollout_index >= len(rollout_snippets):
                continue
            snippet = rollout_snippets[rollout_index]
            for array_name, identifier_values in (
                ("target_id", target_ids),
                ("matched_gt_target_id", matched_gt_target_ids),
            ):
                identifier = identifier_values[target_index] if target_index < len(identifier_values) else ""
                if _target_identifier_mentions_other_snippet(identifier=identifier, snippet=snippet):
                    self.errors.append(
                        f"targets/{array_name} for target_row_id={row_id} does not match rollout snippet_id={snippet!r}."
                    )
                    return

    def _validate_required_lineage(self) -> None:
        target_row_id = np.asarray(self.root["targets/target_row_id"])
        q_h = _q_h_arrays_for_validation(self.root)
        q_state_target_row_id = q_h["target_row_id"]
        q_train_mask = q_h["q_train_mask"]
        expected_target_labels = _canonical_target_label_mask(self.root)
        target_valid_by_id = {
            int(row_id): bool(valid and expected_target_labels[index])
            for index, (row_id, valid) in enumerate(
                zip(
                    target_row_id,
                    np.asarray(self.root["targets/target_valid_mask"]),
                    strict=True,
                )
            )
        }
        persisted_target_labels = np.asarray(self.root["targets/gt_label_valid_mask"], dtype=np.bool_).reshape(-1)
        if not np.array_equal(persisted_target_labels, expected_target_labels):
            self.errors.append("targets/gt_label_valid_mask does not match canonical target evidence.")
        q_target_valid = np.asarray([target_valid_by_id.get(int(row_id), False) for row_id in q_state_target_row_id])
        if q_train_mask.shape[0] == q_target_valid.shape[0] and np.any(q_train_mask & (~q_target_valid[:, None])):
            self.errors.append("Q_H q_train_mask is true for a target without valid task and GT label state.")
        candidate_target_by_rollout = {
            int(rollout_id): target_valid_by_id.get(int(target_id), False)
            for rollout_id, target_id in zip(
                np.asarray(self.root["rollouts/rollout_row_id"]),
                np.asarray(self.root["rollouts/target_row_id"]),
                strict=True,
            )
        }
        step_target_valid = {
            int(step_id): candidate_target_by_rollout.get(int(rollout_id), False)
            for step_id, rollout_id in zip(
                np.asarray(self.root["steps/step_row_id"]),
                np.asarray(self.root["steps/rollout_row_id"]),
                strict=True,
            )
        }
        candidate_target_valid = np.asarray(
            [step_target_valid.get(int(step_id), False) for step_id in np.asarray(self.root["candidates/step_row_id"])],
            dtype=np.bool_,
        )
        actor = np.asarray(self.root["candidates/actor_action_mask"], dtype=np.bool_).reshape(-1)
        oracle = np.asarray(self.root["candidates/oracle_label_mask"], dtype=np.bool_).reshape(-1)
        candidate_q = np.asarray(self.root["candidates/q_train_mask"], dtype=np.bool_).reshape(-1)
        expected_candidate_q = actor & oracle & candidate_target_valid
        if not np.array_equal(candidate_q, expected_candidate_q):
            self.errors.append(
                "candidates/q_train_mask must equal actor_action_mask & oracle_label_mask for admitted targets."
            )
        for attr_name in ("source_offline_store_version", "split_manifest_hash", "target_protocol_version"):
            if _missing_lineage_token(self.root.attrs.get(attr_name)):
                self.errors.append(f"Rollout store is missing required root attr {attr_name!r}.")
        required_lineage = (
            "rollout_row_id",
            "candidate_config_id",
            "oracle_config_id",
            "rollout_config_id",
            "target_protocol_version_id",
            "target_crop_policy_id",
            "reason_code_version_id",
        )
        for name in required_lineage:
            if name not in self.root["lineage"] or np.any(np.asarray(self.root[f"lineage/{name}"]) < 0):
                self.errors.append(f"Rollout store is missing required lineage field {name!r}.")
        rollout_row_id = np.asarray(self.root["rollouts/rollout_row_id"])
        if "rollout_row_id" in self.root["lineage"] and not np.array_equal(
            np.asarray(self.root["lineage/rollout_row_id"]),
            rollout_row_id,
        ):
            self.errors.append("Lineage rollout_row_id must align with rollouts/rollout_row_id.")
        for name in (
            "candidate_config_id",
            "oracle_config_id",
            "rollout_config_id",
            "target_crop_policy_id",
        ):
            values = _encoded_values(self.root, dictionary_name="config", array_path=f"lineage/{name}")
            if any(_missing_lineage_token(value) for value in values):
                self.errors.append(f"Rollout store has empty lineage field {name!r}.")
        expected_config_values = {
            "target_protocol_version_id": str(self.root.attrs.get("target_protocol_version", "")),
            "reason_code_version_id": str(self.root.attrs.get("reason_code_version", "")),
        }
        for name, expected in expected_config_values.items():
            values = _encoded_values(self.root, dictionary_name="config", array_path=f"lineage/{name}")
            if any(value != expected for value in values):
                self.errors.append(f"Rollout store lineage field {name!r} does not match root metadata.")
        for name in ("source_offline_store_manifest_hash_id", "split_manifest_hash_id", "source_cache_version_id"):
            values = _encoded_values(self.root, dictionary_name="config", array_path=f"sources/{name}")
            if any(_missing_lineage_token(value) for value in values):
                self.errors.append(f"Rollout store has empty source field {name!r}.")
        actor_rows = np.asarray(self.root["candidates/actor_action_mask"])
        if np.any(actor_rows & (np.asarray(self.root["candidates/strategy_id"]) < 0)):
            self.errors.append("Actor-selectable candidates require non-placeholder strategy_id.")
        if np.any(actor_rows & (np.asarray(self.root["candidates/mixture_id"]) < 0)):
            self.errors.append("Actor-selectable candidates require non-placeholder mixture_id.")
        if np.any(actor_rows & (~np.isfinite(np.asarray(self.root["candidates/sampler_probability"])))):
            self.errors.append("Actor-selectable candidates require finite sampler_probability.")


def _required_groups() -> tuple[str, ...]:
    return (
        "metadata",
        "dictionaries",
        "sources",
        "lineage",
        "targets",
        "rollouts",
        "steps",
        "candidates",
        "candidate_diagnostics",
        "selected_depth",
        "target_eval_crops",
        "q_h",
    )


def _root_metadata_payload(
    *,
    records: list[_RolloutWriteRecord],
    tables: _RolloutTables,
    q_h_arrays: dict[str, np.ndarray],
    q_h_horizon: int,
    q_h_chunk_states: int,
    return_semantics: str,
    discount_gamma: float,
    target_protocol_version: str,
    reason_code_version: str,
    field_retention_policy: str,
    source_offline_store_version: str,
    split_manifest_hash: str,
    selected_depth_enabled: bool,
    selected_depth_width_px: int,
    selected_depth_height_px: int,
    selected_depth_chunk_steps: int,
    selected_depth_renderer: str,
    selected_depth_znear_m: float | None,
    selected_depth_zfar_m: float | None,
    selected_depth_source_resolution: str,
    target_eval_crop_max_points: int,
    target_eval_crops_enabled: bool,
    created_at_utc: str,
    manifest_sha256: str,
) -> dict[str, Any]:
    """Return compact root attrs for one rollout store."""

    split_values = {
        _lineage_for_chain(record, chain_id).source.split or "unknown"
        for record in records
        for chain_id, _trajectory in enumerate(record.evaluated.result.trajectories)
    }
    return {
        "schema_id": ROLLOUT_ZARR_SCHEMA_ID,
        "schema_version": ROLLOUT_ZARR_SCHEMA_VERSION,
        "zarr_format": 3,
        "created_at_utc": created_at_utc,
        "manifest_path": ROLLOUT_MANIFEST_FILENAME,
        "manifest_sha256": manifest_sha256,
        "manifest_version": ROLLOUT_MANIFEST_VERSION,
        "source_offline_store_version": source_offline_store_version,
        "split_manifest_hash": split_manifest_hash,
        "source_split": next(iter(split_values)) if len(split_values) == 1 else "mixed",
        "reason_code_version": reason_code_version,
        "target_protocol_version": target_protocol_version,
        "return_semantics": return_semantics,
        "discount_gamma": float(discount_gamma),
        "field_retention_policy": field_retention_policy,
        "selected_depth_enabled": bool(selected_depth_enabled),
        "selected_depth_width_px": int(selected_depth_width_px),
        "selected_depth_height_px": int(selected_depth_height_px),
        "selected_depth_dtype": "float16",
        "selected_depth_valid_mask_dtype": "bool",
        "selected_depth_units": "m",
        "selected_depth_invalid_fill_value": SELECTED_DEPTH_INVALID_FILL_VALUE,
        "selected_depth_codec": SELECTED_DEPTH_CODEC,
        "selected_depth_chunk_steps": int(selected_depth_chunk_steps),
        "selected_depth_role": "selected_successor_state_history",
        "selected_depth_renderer": selected_depth_renderer,
        "selected_depth_znear_m": _float_or_nan(selected_depth_znear_m),
        "selected_depth_zfar_m": _float_or_nan(selected_depth_zfar_m),
        "selected_depth_source_resolution": selected_depth_source_resolution,
        "q_h_view_persisted": True,
        "q_h_view_role": "training_core_derived_cache",
        "q_h_source_tables": "steps,candidates,rollouts,targets",
        "q_h_reward_metric": Q_H_REWARD_METRIC,
        "q_h_return_semantics": return_semantics,
        "q_h_horizon": int(q_h_horizon),
        "q_h_chunk_states": int(q_h_chunk_states),
        "q_h_state_count": int(q_h_arrays["state_step_row_id"].shape[0]),
        "q_h_max_candidates": int(q_h_arrays["candidate_row_id"].shape[1])
        if q_h_arrays["candidate_row_id"].ndim == 2
        else 0,
        "num_sources": int(tables.sources["source_row_id"].shape[0]),
        "num_targets": int(len(_unique_targets(records))),
        "num_rollouts": int(tables.rollouts["rollout_row_id"].shape[0]),
        "num_steps": int(tables.steps["step_row_id"].shape[0]),
        "num_candidates": int(tables.candidates["candidate_row_id"].shape[0]),
        "candidate_diagnostics_enabled": True,
        "candidate_diagnostics_role": "audit_rerun_only",
        "candidate_diagnostics_unavailable_float": "NaN",
        "candidate_diagnostics_unavailable_bool": "false",
        "num_candidate_diagnostics": int(tables.candidate_diagnostics["candidate_row_id"].shape[0]),
        "num_selected_depths": int(tables.selected_depth["step_row_id"].shape[0]),
        "target_eval_crops_enabled": bool(target_eval_crops_enabled),
        "target_eval_crops_role": "oracle_eval_only",
        "target_eval_crops_coordinate_frame": "world",
        "target_eval_crops_max_points": int(target_eval_crop_max_points),
        "target_eval_crops_num_rows": int(tables.target_eval_crops["crop_row_id"].shape[0]),
        "num_q_h_states": int(q_h_arrays["state_step_row_id"].shape[0]),
    }


def _build_manifest_payload(
    *,
    records: list[_RolloutWriteRecord],
    tables: _RolloutTables,
    q_h_arrays: dict[str, np.ndarray],
    dictionaries: dict[str, list[str]],
    context: RolloutStoreManifestContext,
    root_attrs: dict[str, Any],
    created_at_utc: str,
) -> dict[str, Any]:
    """Build the human-readable top-level rollout-store manifest."""

    return {
        "manifest_version": ROLLOUT_MANIFEST_VERSION,
        "schema_id": ROLLOUT_ZARR_SCHEMA_ID,
        "schema_version": ROLLOUT_ZARR_SCHEMA_VERSION,
        "created_at_utc": created_at_utc,
        "store_kind": "standalone_rollout_zarr_shard",
        "root_attrs": {key: value for key, value in root_attrs.items() if key != "manifest_sha256"},
        "counts": {
            "sources": int(tables.sources["source_row_id"].shape[0]),
            "targets": int(len(_unique_targets(records))),
            "rollouts": int(tables.rollouts["rollout_row_id"].shape[0]),
            "steps": int(tables.steps["step_row_id"].shape[0]),
            "candidates": int(tables.candidates["candidate_row_id"].shape[0]),
            "candidate_diagnostics": int(tables.candidate_diagnostics["candidate_row_id"].shape[0]),
            "selected_depths": int(tables.selected_depth["step_row_id"].shape[0]),
            "target_eval_crops": int(tables.target_eval_crops["crop_row_id"].shape[0]),
            "q_h_states": int(q_h_arrays["state_step_row_id"].shape[0]),
            "q_h_max_candidates": int(q_h_arrays["candidate_row_id"].shape[1])
            if q_h_arrays["candidate_row_id"].ndim == 2
            else 0,
        },
        "source_coverage": _source_coverage(records),
        "config_hashes": _manifest_config_hashes(records),
        "dictionary_sizes": {name: len(values) for name, values in sorted(dictionaries.items())},
        "generation": context.to_jsonable(),
    }


def _source_coverage(records: list[_RolloutWriteRecord]) -> dict[str, Any]:
    """Summarize source rows without reading Zarr payload arrays."""

    rows: dict[int, dict[str, Any]] = {}
    for record in records:
        lineage = record.lineage
        source_row_id = -1 if lineage.source.source_row_id is None else int(lineage.source.source_row_id)
        rows[source_row_id] = {
            "source_row_id": source_row_id,
            "source_sample_index": lineage.source.source_sample_index,
            "source_sample_key": compact_ase_atek_sample_id(lineage.source.source_sample_key or "") or None,
            "scene_id": lineage.source.scene_id,
            "snippet_id": compact_ase_atek_sample_id(lineage.source.snippet_id or "") or None,
            "split": lineage.source.split,
            "source_shard_id": lineage.source.source_shard_id,
            "source_shard_row": lineage.source.source_shard_row,
        }
    scene_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    source_shard_counts: dict[str, int] = {}
    for row in rows.values():
        scene = str(row["scene_id"] or "unknown")
        split = str(row["split"] or "unknown")
        source_shard = str(row["source_shard_id"] or "unknown")
        scene_counts[scene] = scene_counts.get(scene, 0) + 1
        split_counts[split] = split_counts.get(split, 0) + 1
        source_shard_counts[source_shard] = source_shard_counts.get(source_shard, 0) + 1
    return {
        "num_source_rows": len(rows),
        "scene_counts": dict(sorted(scene_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "source_shard_counts": dict(sorted(source_shard_counts.items())),
        "sources": [rows[key] for key in sorted(rows)],
    }


def _manifest_config_hashes(records: list[_RolloutWriteRecord]) -> dict[str, list[str]]:
    """Collect unique config/protocol hashes stored in rollout lineages."""

    values: dict[str, set[str]] = {
        "candidate": set(),
        "oracle": set(),
        "rollout": set(),
        "model_checkpoint": set(),
        "source_manifest": set(),
        "split_manifest": set(),
        "target_crop_policy": set(),
        "target_protocol": set(),
    }
    for record in records:
        lineage = record.lineage
        _add_manifest_hash(values["candidate"], lineage.policy.candidate_config_hash)
        _add_manifest_hash(values["oracle"], lineage.policy.oracle_config_hash)
        _add_manifest_hash(values["rollout"], lineage.policy.rollout_config_hash)
        _add_manifest_hash(values["model_checkpoint"], lineage.policy.model_checkpoint_hash)
        _add_manifest_hash(values["source_manifest"], lineage.source.source_offline_store_manifest_hash)
        _add_manifest_hash(values["split_manifest"], lineage.source.split_manifest_hash)
        _add_manifest_hash(values["target_crop_policy"], lineage.target.target_crop_policy)
        _add_manifest_hash(values["target_protocol"], lineage.target.target_protocol_version)
    return {name: sorted(items) for name, items in values.items()}


def _add_manifest_hash(target: set[str], value: str | None) -> None:
    if value:
        target.add(value)


def _records_with_global_target_row_ids(records: list[_RolloutWriteRecord]) -> list[_RolloutWriteRecord]:
    """Return records whose lineage target rows are unique within the rollout store.

    ``OracleTargetTask.target_row_id`` is selector-local to one source sample.
    The rollout store needs a globally unique row key because ``rollouts/`` and
    ``q_h/`` join through ``target_row_id``. Preserve the selector-local id in
    ``target_source_index`` and assign dense store-local ids by first use.
    """

    target_row_by_key: dict[tuple[object, ...], int] = {}
    normalized: list[_RolloutWriteRecord] = []
    for record in records:
        lineage = record.lineage
        target_key = _global_target_key(lineage)
        global_target_row_id = target_row_by_key.setdefault(target_key, len(target_row_by_key))
        target_source_index = lineage.target.target_source_index
        if target_source_index is None and lineage.target.target_row_id is not None:
            target_source_index = int(lineage.target.target_row_id)
        normalized.append(
            replace(
                record,
                lineage=replace(
                    lineage,
                    target=replace(
                        lineage.target,
                        target_row_id=global_target_row_id,
                        target_source_index=target_source_index,
                    ),
                ),
            )
        )
    return normalized


def _global_target_key(lineage: RolloutLineage) -> tuple[object, ...]:
    """Return the source-scoped identity for one selected rollout target."""

    selector_local_id = lineage.target.target_source_index
    if selector_local_id is None:
        selector_local_id = lineage.target.target_row_id
    return (
        _lineage_source_row_id(lineage),
        lineage.target.target_id or "",
        lineage.target.matched_gt_target_id or "",
        -1 if lineage.target.matched_gt_target_row_id is None else int(lineage.target.matched_gt_target_row_id),
        -1 if selector_local_id is None else int(selector_local_id),
    )


def _unique_targets(records: list[_RolloutWriteRecord]) -> set[int]:
    """Return unique target row ids represented by rollout records."""

    return {
        int(record.lineage.target.target_row_id)
        for record in records
        if record.lineage.target.target_row_id is not None
    }


def _write_metadata_group(group: zarr.Group, *, field_retention_policy: str) -> None:
    reason_names = [name for name, _bit in sorted(INVALID_REASON_CODES.items(), key=lambda item: item[1])]
    reason_bits = [bit for _name, bit in sorted(INVALID_REASON_CODES.items(), key=lambda item: item[1])]
    _write_array(group, "reason_code_bits", np.asarray(reason_bits, dtype=np.uint16))
    _write_string_array(group, "reason_code_names", reason_names)
    _write_string_array(group, "field_retention_policy", [field_retention_policy])


def _build_dictionaries(records: list[_RolloutWriteRecord]) -> dict[str, list[str]]:
    items = list(_record_items(records))
    policy_values = {_policy_name(record.evaluated.result.selection_policy) for record in records}
    policy_values.update(
        step.selection_policy
        for record in records
        for trajectory in record.evaluated.result.trajectories
        for step in trajectory.steps
    )
    policy_values.update(
        lineage.target.target_selection_policy
        for _record, _trajectory, lineage in items
        if lineage.target.target_selection_policy is not None
    )
    target_values = {lineage.target.target_id or "unknown-target" for _record, _trajectory, lineage in items}
    target_values.update(
        lineage.target.matched_gt_target_id
        for _record, _trajectory, lineage in items
        if lineage.target.matched_gt_target_id is not None
    )
    source_key_values = {
        compact_ase_atek_sample_id(lineage.source.source_sample_key or "") for _record, _trajectory, lineage in items
    }
    source_shard_values = {lineage.source.source_shard_id or "" for _record, _trajectory, lineage in items}
    score_source_values = {
        step.selection_score_label
        for record in records
        for trajectory in record.evaluated.result.trajectories
        for step in trajectory.steps
    }
    crop_policy_values = {
        evaluated.evaluation.evidence.target_eval_crop_policy
        for record in records
        for chain_id, trajectory in enumerate(record.evaluated.result.trajectories)
        for step in trajectory.steps
        if (evaluated := record.evaluated.step(chain_id, step.step_index)) is not None
        and evaluated.evaluation.evidence.target_eval_crop_policy
    }
    split_values = {lineage.source.split or "unknown" for _record, _trajectory, lineage in items}
    target_match_status_values = {
        lineage.target.gt_match_status or "not_requested" for _record, _trajectory, lineage in items
    }
    return {
        "scene": sorted({lineage.source.scene_id or "" for _record, _trajectory, lineage in items}),
        "snippet": sorted(
            {compact_ase_atek_sample_id(lineage.source.snippet_id or "") for _record, _trajectory, lineage in items}
        ),
        "rollout": [lineage.rollout_id for _record, _trajectory, lineage in items],
        "target": sorted(target_values),
        "source_key": sorted(source_key_values),
        "source_shard": sorted(source_shard_values),
        "target_source": sorted({lineage.target.target_source or "" for _record, _trajectory, lineage in items}),
        "policy": sorted(policy_values),
        "score_source": sorted(score_source_values),
        "split": sorted(split_values),
        "config": sorted(
            {
                value
                for _record, _trajectory, lineage in items
                for value in (
                    lineage.policy.candidate_config_hash,
                    lineage.policy.oracle_config_hash,
                    lineage.policy.rollout_config_hash,
                    lineage.policy.model_checkpoint_hash,
                    lineage.source.mesh_version,
                    lineage.source.source_cache_version,
                    lineage.source.source_offline_store_manifest_hash,
                    lineage.source.split_manifest_hash,
                    lineage.policy.branch_schedule_id,
                    lineage.target.target_protocol_version,
                    lineage.target.target_crop_policy,
                    *crop_policy_values,
                    lineage.target.target_reason_code_version,
                    lineage.policy.reason_code_version,
                    lineage.policy.selection_rng_state_hash,
                )
                if value
            }
        ),
        "class_name": sorted(
            {lineage.target.target_class_name or "unknown" for _record, _trajectory, lineage in items}
        ),
        "target_match_status": sorted(target_match_status_values),
        "termination_reason": sorted(
            {
                _termination_reason(record.evaluated.result, trajectory)
                for record in records
                for trajectory in record.evaluated.result.trajectories
            }
        ),
    }


def _write_dictionaries(group: zarr.Group, dictionaries: dict[str, list[str]]) -> None:
    for name, values in dictionaries.items():
        _write_string_array(group, name, values)


def _write_targets(
    group: zarr.Group,
    records: list[_RolloutWriteRecord],
    dictionaries: dict[str, list[str]],
    *,
    target_protocol_version: str,
) -> None:
    target_rows = _target_rows_from_records(records)
    target_ids = sorted(target_rows)
    if not target_ids:
        target_ids = [0]
        target_rows[0] = {}
    _write_array(group, "target_row_id", np.asarray(target_ids, dtype=np.int64))
    _write_array(
        group,
        "target_id",
        np.asarray(
            [
                _dict_id(
                    dictionaries["target"],
                    str(target_rows[target_row_id].get("target_id") or "unknown-target"),
                )
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_selection_policy_id",
        np.asarray(
            [
                _dict_id(dictionaries["policy"], str(target_rows[target_row_id].get("target_selection_policy") or ""))
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_selection_rank",
        np.asarray(
            [
                _int_or_default(target_rows[target_row_id].get("target_selection_rank"), default=-1)
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_selection_score",
        np.asarray(
            [_float_or_nan(target_rows[target_row_id].get("target_selection_score")) for target_row_id in target_ids],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "target_selection_probability",
        np.asarray(
            [
                _float_or_nan(target_rows[target_row_id].get("target_selection_probability"))
                for target_row_id in target_ids
            ],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "target_selection_temperature",
        np.asarray(
            [
                _float_or_nan(target_rows[target_row_id].get("target_selection_temperature"))
                for target_row_id in target_ids
            ],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "target_source_id",
        np.asarray(
            [
                _dict_id(dictionaries["target_source"], str(target_rows[target_row_id].get("target_source") or ""))
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_source_index",
        np.asarray(
            [
                _int_or_default(target_rows[target_row_id].get("target_source_index"), default=-1)
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_sem_id",
        np.asarray(
            [
                _int_or_default(target_rows[target_row_id].get("target_sem_id"), default=-1)
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_inst_id",
        np.asarray(
            [
                _int_or_default(target_rows[target_row_id].get("target_inst_id"), default=-1)
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_class_name_id",
        np.asarray(
            [
                _dict_id(dictionaries["class_name"], str(target_rows[target_row_id].get("target_class_name") or ""))
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "target_confidence",
        np.asarray(
            [_float_or_nan(target_rows[target_row_id].get("target_confidence")) for target_row_id in target_ids],
            dtype=np.float32,
        ),
    )
    for name in (
        "target_projected_area_pixels",
        "target_projected_area_fraction",
        "target_effective_support_count",
        "target_visibility_score",
        "target_support_score",
        "target_deficit_score",
    ):
        _write_array(
            group,
            name,
            np.asarray(
                [_float_or_nan(target_rows[target_row_id].get(name)) for target_row_id in target_ids],
                dtype=np.float32,
            ),
        )
    for name in ("target_semidense_support_count", "target_evl_support_count"):
        _write_array(
            group,
            name,
            np.asarray(
                [_int_or_default(target_rows[target_row_id].get(name), default=-1) for target_row_id in target_ids],
                dtype=np.int32,
            ),
        )
    _write_array(
        group,
        "target_center_world",
        np.asarray(
            [
                _fixed_float_vector(target_rows[target_row_id].get("target_center_world"), length=3)
                for target_row_id in target_ids
            ],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "target_extents",
        np.asarray(
            [
                _fixed_float_vector(target_rows[target_row_id].get("target_extents"), length=3)
                for target_row_id in target_ids
            ],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "target_pose_world_object",
        np.asarray(
            [
                _fixed_float_vector(target_rows[target_row_id].get("target_pose_world_object"), length=12)
                for target_row_id in target_ids
            ],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "target_relative_pose_reference_object",
        np.asarray(
            [
                _fixed_float_vector(
                    target_rows[target_row_id].get("target_relative_pose_reference_object"),
                    length=12,
                )
                for target_row_id in target_ids
            ],
            dtype=np.float32,
        ),
    )
    default_target_reason = (
        0 if target_protocol_version == TargetInputProtocol.V1_OBSERVED else 1 << INVALID_REASON_CODES["VALID"]
    )
    target_reason = np.asarray(
        [
            _int_or_default(
                target_rows[target_row_id].get("target_invalid_reason_bitset"),
                default=default_target_reason,
            )
            for target_row_id in target_ids
        ],
        dtype=np.uint32,
    )
    _write_array(group, "target_valid_mask", target_reason == np.uint32(1 << INVALID_REASON_CODES["VALID"]))
    _write_array(
        group,
        "target_invalid_reason_bitset",
        target_reason,
    )
    _write_array(
        group,
        "target_primary_invalid_reason",
        np.asarray(
            [
                _int_or_default(
                    target_rows[target_row_id].get("target_primary_invalid_reason"),
                    default=INVALID_REASON_CODES["VALID"],
                )
                for target_row_id in target_ids
            ],
            dtype=np.uint16,
        ),
    )
    _write_array(
        group,
        "target_reason_code_version_id",
        np.asarray(
            [
                _dict_id(
                    dictionaries["config"], str(target_rows[target_row_id].get("target_reason_code_version") or "")
                )
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "matched_gt_target_row_id",
        np.asarray(
            [
                _int_or_default(target_rows[target_row_id].get("matched_gt_target_row_id"), default=-1)
                for target_row_id in target_ids
            ],
            dtype=np.int64,
        ),
    )
    _write_array(
        group,
        "matched_gt_target_id",
        np.asarray(
            [
                _dict_id(dictionaries["target"], str(target_rows[target_row_id].get("matched_gt_target_id") or ""))
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "gt_match_iou",
        np.asarray(
            [_float_or_nan(target_rows[target_row_id].get("gt_match_iou")) for target_row_id in target_ids],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "gt_match_score",
        np.asarray(
            [_float_or_nan(target_rows[target_row_id].get("gt_match_score")) for target_row_id in target_ids],
            dtype=np.float32,
        ),
    )
    _write_array(
        group,
        "gt_match_status_id",
        np.asarray(
            [
                _dict_id(
                    dictionaries["target_match_status"],
                    str(target_rows[target_row_id].get("gt_match_status") or "not_requested"),
                )
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_array(
        group,
        "gt_label_valid_mask",
        np.asarray(
            [
                target_label_is_trainable(
                    TargetLabelEvidence(
                        protocol=target_protocol_version,
                        target_source=target_rows[target_row_id].get("target_source"),
                        gt_match_status=target_rows[target_row_id].get("gt_match_status"),
                        matched_gt_target_row_id=_int_or_default(
                            target_rows[target_row_id].get("matched_gt_target_row_id"), default=-1
                        ),
                        matched_gt_target_id=target_rows[target_row_id].get("matched_gt_target_id"),
                        gt_match_iou=target_rows[target_row_id].get("gt_match_iou"),
                        target_valid=(
                            _int_or_default(
                                target_rows[target_row_id].get("target_invalid_reason_bitset"),
                                default=default_target_reason,
                            )
                            == 1 << INVALID_REASON_CODES["VALID"]
                        ),
                    )
                )
                for target_row_id in target_ids
            ],
            dtype=np.bool_,
        ),
    )
    _write_array(
        group,
        "target_crop_policy_id",
        np.asarray(
            [
                _dict_id(dictionaries["config"], str(target_rows[target_row_id].get("target_crop_policy") or ""))
                for target_row_id in target_ids
            ],
            dtype=np.int32,
        ),
    )
    _write_string_array(group, "target_protocol_version", [target_protocol_version])


def _target_rows_from_records(records: list[_RolloutWriteRecord]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for _record, _trajectory, lineage in _record_items(records):
        row_id = lineage.target.target_row_id if lineage.target.target_row_id is not None else 0
        existing = rows.setdefault(int(row_id), {})
        values = {
            "target_id": lineage.target.target_id or "unknown-target",
            "target_selection_policy": lineage.target.target_selection_policy,
            "target_selection_rank": lineage.target.target_selection_rank,
            "target_selection_score": lineage.target.target_selection_score,
            "target_selection_probability": lineage.target.target_selection_probability,
            "target_selection_temperature": lineage.target.target_selection_temperature,
            "target_source": lineage.target.target_source,
            "target_source_index": lineage.target.target_source_index,
            "target_sem_id": lineage.target.target_sem_id,
            "target_inst_id": lineage.target.target_inst_id,
            "target_class_name": lineage.target.target_class_name,
            "target_confidence": lineage.target.target_confidence,
            "target_projected_area_pixels": lineage.target.target_projected_area_pixels,
            "target_projected_area_fraction": lineage.target.target_projected_area_fraction,
            "target_semidense_support_count": lineage.target.target_semidense_support_count,
            "target_evl_support_count": lineage.target.target_evl_support_count,
            "target_effective_support_count": lineage.target.target_effective_support_count,
            "target_visibility_score": lineage.target.target_visibility_score,
            "target_support_score": lineage.target.target_support_score,
            "target_deficit_score": lineage.target.target_deficit_score,
            "target_center_world": lineage.target.target_center_world,
            "target_extents": lineage.target.target_extents,
            "target_pose_world_object": lineage.target.target_pose_world_object,
            "target_relative_pose_reference_object": lineage.target.target_relative_pose_reference_object,
            "target_invalid_reason_bitset": lineage.target.target_invalid_reason_bitset,
            "target_primary_invalid_reason": lineage.target.target_primary_invalid_reason,
            "target_reason_code_version": lineage.target.target_reason_code_version,
            "matched_gt_target_row_id": lineage.target.matched_gt_target_row_id,
            "matched_gt_target_id": lineage.target.matched_gt_target_id,
            "gt_match_iou": lineage.target.gt_match_iou,
            "gt_match_score": lineage.target.gt_match_score,
            "gt_match_status": lineage.target.gt_match_status,
            "target_crop_policy": lineage.target.target_crop_policy,
        }
        for name, value in values.items():
            if value is not None or name not in existing:
                existing[name] = value
    return rows


def _flatten_records(
    records: list[_RolloutWriteRecord],
    dictionaries: dict[str, list[str]],
    *,
    selected_depth_width_px: int,
    selected_depth_height_px: int,
    target_eval_crop_max_points: int,
    target_eval_crops_enabled: bool,
) -> _RolloutTables:
    source_rows: dict[str, list[Any]] = _empty_rows(SOURCE_TABLE)
    rollout_rows: dict[str, list[Any]] = _empty_rows(ROLLOUT_TABLE)
    lineage_rows: dict[str, list[Any]] = _empty_rows(LINEAGE_TABLE)
    step_rows: dict[str, list[Any]] = _empty_rows(STEP_TABLE)
    candidate_rows: dict[str, list[Any]] = _empty_candidate_rows()
    candidate_diagnostic_rows: dict[str, list[Any]] = _empty_candidate_diagnostic_rows()
    selected_depth_rows: dict[str, list[Any]] = _empty_selected_depth_rows()
    target_eval_crop_rows: dict[str, list[Any]] = _empty_target_eval_crop_rows()

    candidate_row_id = 0
    step_row_id = 0
    crop_row_id = 0
    seen_source_rows: dict[int, tuple[object, ...]] = {}
    rollout_row_id = 0
    for record, trajectory, lineage in _record_items(records):
        final_target_rri = _trajectory_cumulative_metric(record, lineage.chain_id, trajectory, ("target_rri", "rri"))
        final_scene_rri = _trajectory_cumulative_metric(record, lineage.chain_id, trajectory, ("scene_rri",))
        final_target_root_gain = _trajectory_cumulative_metric(
            record, lineage.chain_id, trajectory, ("target_root_gain", "root_gain")
        )
        final_scene_root_gain = _trajectory_cumulative_metric(
            record, lineage.chain_id, trajectory, ("scene_root_gain",)
        )
        source_row_id = _lineage_source_row_id(lineage)
        source_identity = _source_identity(lineage=lineage, source_row_id=source_row_id)
        existing_source_identity = seen_source_rows.get(source_row_id)
        if existing_source_identity is None:
            seen_source_rows[source_row_id] = source_identity
            _append_source_row(source_rows, lineage=lineage, source_row_id=source_row_id, dictionaries=dictionaries)
        elif existing_source_identity != source_identity:
            raise ValueError(
                f"Conflicting source lineage for source_row_id={source_row_id}; "
                "rollout source rows must map one-to-one to VIN offline sample-index rows."
            )
        rollout_rows["rollout_row_id"].append(rollout_row_id)
        rollout_rows["rollout_id"].append(_dict_id(dictionaries["rollout"], lineage.rollout_id))
        rollout_rows["chain_id"].append(lineage.chain_id)
        rollout_rows["source_row_id"].append(source_row_id)
        rollout_rows["root_pose_world"].append(
            record.evaluated.result.root_pose_world.tensor().detach().cpu().to(dtype=torch.float32).reshape(-1).numpy()
        )
        rollout_rows["root_time_ns"].append(_int_or_default(record.evaluated.result.root_time_ns, default=-1))
        rollout_rows["root_trajectory_index"].append(
            _int_or_default(record.evaluated.result.root_trajectory_index, default=-1)
        )
        rollout_rows["root_frame_index"].append(_int_or_default(record.evaluated.result.root_frame_index, default=-1))
        rollout_rows["scene_id"].append(_dict_id(dictionaries["scene"], lineage.source.scene_id or ""))
        rollout_rows["snippet_id"].append(
            _dict_id(dictionaries["snippet"], compact_ase_atek_sample_id(lineage.source.snippet_id or ""))
        )
        rollout_rows["target_row_id"].append(
            lineage.target.target_row_id if lineage.target.target_row_id is not None else 0
        )
        rollout_rows["policy_id"].append(
            _dict_id(dictionaries["policy"], _policy_name(record.evaluated.result.selection_policy))
        )
        rollout_rows["horizon"].append(record.evaluated.result.horizon)
        rollout_rows["branch_factor"].append(record.evaluated.result.branch_factor)
        rollout_rows["beam_width"].append(
            -1 if record.evaluated.result.beam_width is None else record.evaluated.result.beam_width
        )
        rollout_rows["temperature"].append(_first_temperature(trajectory))
        rollout_rows["random_seed"].append(-1 if lineage.policy.random_seed is None else lineage.policy.random_seed)
        rollout_rows["termination_reason"].append(
            _dict_id(
                dictionaries["termination_reason"],
                _termination_reason(record.evaluated.result, trajectory),
            )
        )
        rollout_rows["final_cumulative_target_rri"].append(_nan_if_none(final_target_rri))
        rollout_rows["final_cumulative_scene_rri"].append(_nan_if_none(final_scene_rri))
        rollout_rows["final_cumulative_target_root_gain"].append(_nan_if_none(final_target_root_gain))
        rollout_rows["final_cumulative_scene_root_gain"].append(_nan_if_none(final_scene_root_gain))
        rollout_rows["split_id"].append(_dict_id(dictionaries["split"], lineage.source.split or "unknown"))

        lineage_rows["rollout_row_id"].append(rollout_row_id)
        lineage_rows["candidate_config_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.candidate_config_hash or "")
        )
        lineage_rows["oracle_config_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.oracle_config_hash or "")
        )
        lineage_rows["rollout_config_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.rollout_config_hash or "")
        )
        lineage_rows["model_checkpoint_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.model_checkpoint_hash or "")
        )
        lineage_rows["mesh_version_id"].append(_dict_id(dictionaries["config"], lineage.source.mesh_version or ""))
        lineage_rows["branch_schedule_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.branch_schedule_id or "")
        )
        lineage_rows["target_protocol_version_id"].append(
            _dict_id(dictionaries["config"], lineage.target.target_protocol_version or "")
        )
        lineage_rows["target_crop_policy_id"].append(
            _dict_id(dictionaries["config"], lineage.target.target_crop_policy or "")
        )
        lineage_rows["reason_code_version_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.reason_code_version or "")
        )
        lineage_rows["selection_rng_state_hash_id"].append(
            _dict_id(dictionaries["config"], lineage.policy.selection_rng_state_hash or "")
        )

        running_target_rri: float | None = None
        running_scene_rri: float | None = None
        running_target_root_gain: float | None = None
        running_scene_root_gain: float | None = None
        root_pose = record.evaluated.result.root_pose_world.tensor().detach().cpu().reshape(-1)
        for step in trajectory.steps:
            evaluated_step = _evaluated_step(record, lineage.chain_id, step.step_index)
            candidate_valid = _candidate_valid(step)
            running_target_rri = _accumulate_selected_metric(running_target_rri, evaluated_step, ("target_rri", "rri"))
            running_scene_rri = _accumulate_selected_metric(running_scene_rri, evaluated_step, ("scene_rri",))
            running_target_root_gain = _accumulate_selected_metric(
                running_target_root_gain,
                evaluated_step,
                ("target_root_gain", "root_gain"),
            )
            running_scene_root_gain = _accumulate_selected_metric(
                running_scene_root_gain,
                evaluated_step,
                ("scene_root_gain",),
            )
            this_step_row_id = step_row_id
            step_row_id += 1
            selected_candidate_row_id = candidate_row_id + int(step.selected_shell_index)
            step_rows["step_row_id"].append(this_step_row_id)
            step_rows["rollout_row_id"].append(rollout_row_id)
            step_rows["step_index"].append(step.step_index)
            step_rows["selected_candidate_row_id"].append(selected_candidate_row_id)
            step_rows["selected_shell_index"].append(step.selected_shell_index)
            step_rows["selected_compact_valid_index"].append(step.selected_valid_index)
            step_rows["num_candidates"].append(int(candidate_valid.shape[0]))
            step_rows["num_valid_candidates"].append(int(candidate_valid.sum().item()))
            step_rows["cumulative_target_rri"].append(_nan_if_none(running_target_rri))
            step_rows["cumulative_scene_rri"].append(_nan_if_none(running_scene_rri))
            step_rows["cumulative_target_root_gain"].append(_nan_if_none(running_target_root_gain))
            step_rows["cumulative_scene_root_gain"].append(_nan_if_none(running_scene_root_gain))
            _append_selected_depth_row(
                selected_depth_rows,
                evidence=evaluated_step.evaluation.evidence,
                step_row_id=this_step_row_id,
                selected_candidate_row_id=selected_candidate_row_id,
            )
            if target_eval_crops_enabled:
                crop_row_id = _append_target_eval_crop_rows(
                    target_eval_crop_rows,
                    evidence=evaluated_step.evaluation.evidence,
                    candidate_valid=candidate_valid,
                    step_row_id=this_step_row_id,
                    candidate_row_id_start=candidate_row_id,
                    crop_row_id_start=crop_row_id,
                    dictionaries=dictionaries,
                    fixed_max_points=target_eval_crop_max_points,
                )

            for shell_index in range(int(candidate_valid.shape[0])):
                _append_candidate_row(
                    candidate_rows,
                    step=step,
                    labels=evaluated_step.evaluation.labels,
                    candidate_valid=candidate_valid,
                    candidate_row_id=candidate_row_id,
                    step_row_id=this_step_row_id,
                    rollout_row_id=rollout_row_id,
                    shell_index=shell_index,
                    root_pose=root_pose,
                    dictionaries=dictionaries,
                    target_label_valid=_lineage_target_label_valid(lineage),
                )
                _append_candidate_diagnostic_row(
                    candidate_diagnostic_rows,
                    step=step,
                    candidate_valid=candidate_valid,
                    candidate_row_id=candidate_row_id,
                    shell_index=shell_index,
                )
                candidate_row_id += 1
        rollout_row_id += 1

    return _RolloutTables(
        sources=_rows_to_numpy_table(source_rows, SOURCE_TABLE),
        rollouts=_rows_to_numpy_table(rollout_rows, ROLLOUT_TABLE),
        lineage=_rows_to_numpy_table(lineage_rows, LINEAGE_TABLE),
        steps=_rows_to_numpy_table(step_rows, STEP_TABLE),
        candidates=_rows_to_numpy_table(candidate_rows, CANDIDATE_TABLE),
        candidate_diagnostics=_rows_to_numpy_table(candidate_diagnostic_rows, CANDIDATE_DIAGNOSTIC_TABLE),
        selected_depth=_rows_to_numpy_selected_depth_table(
            selected_depth_rows,
            width_px=selected_depth_width_px,
            height_px=selected_depth_height_px,
        ),
        target_eval_crops=_rows_to_numpy_target_eval_crop_table(
            target_eval_crop_rows,
            max_points=target_eval_crop_max_points,
        ),
    )


def _append_source_row(
    rows: dict[str, list[Any]],
    *,
    lineage: RolloutLineage,
    source_row_id: int,
    dictionaries: dict[str, list[str]],
) -> None:
    rows["source_row_id"].append(source_row_id)
    rows["sample_index"].append(
        source_row_id if lineage.source.source_sample_index is None else int(lineage.source.source_sample_index)
    )
    rows["sample_key_id"].append(
        _dict_id(dictionaries["source_key"], compact_ase_atek_sample_id(lineage.source.source_sample_key or ""))
    )
    rows["scene_id"].append(_dict_id(dictionaries["scene"], lineage.source.scene_id or ""))
    rows["snippet_id"].append(
        _dict_id(dictionaries["snippet"], compact_ase_atek_sample_id(lineage.source.snippet_id or ""))
    )
    rows["split_id"].append(_dict_id(dictionaries["split"], lineage.source.split or "unknown"))
    rows["source_cache_version_id"].append(_dict_id(dictionaries["config"], lineage.source.source_cache_version or ""))
    rows["source_offline_store_manifest_hash_id"].append(
        _dict_id(dictionaries["config"], lineage.source.source_offline_store_manifest_hash or "")
    )
    rows["split_manifest_hash_id"].append(_dict_id(dictionaries["config"], lineage.source.split_manifest_hash or ""))
    rows["source_shard_id"].append(_dict_id(dictionaries["source_shard"], lineage.source.source_shard_id or ""))
    rows["source_shard_row"].append(
        -1 if lineage.source.source_shard_row is None else int(lineage.source.source_shard_row)
    )


def _source_identity(*, lineage: RolloutLineage, source_row_id: int) -> tuple[object, ...]:
    """Return the source fields that must be stable for one source row id."""

    return (
        source_row_id,
        None if lineage.source.source_sample_index is None else int(lineage.source.source_sample_index),
        compact_ase_atek_sample_id(lineage.source.source_sample_key or ""),
        lineage.source.scene_id,
        compact_ase_atek_sample_id(lineage.source.snippet_id or ""),
        lineage.source.split,
        lineage.source.source_cache_version,
        lineage.source.source_offline_store_manifest_hash,
        lineage.source.split_manifest_hash,
        lineage.source.source_shard_id,
        None if lineage.source.source_shard_row is None else int(lineage.source.source_shard_row),
    )


def _lineage_source_row_id(lineage: RolloutLineage) -> int:
    if lineage.source.source_row_id is not None:
        return int(lineage.source.source_row_id)
    if lineage.source.source_sample_index is not None:
        return int(lineage.source.source_sample_index)
    return 0


def _empty_rows(schema: _TableSchema) -> dict[str, list[Any]]:
    return {name: [] for name in schema.names}


def _empty_candidate_rows() -> dict[str, list[Any]]:
    return _empty_rows(CANDIDATE_TABLE)


def _empty_candidate_diagnostic_rows() -> dict[str, list[Any]]:
    return _empty_rows(CANDIDATE_DIAGNOSTIC_TABLE)


def _empty_selected_depth_rows() -> dict[str, list[Any]]:
    rows = _empty_rows(SELECTED_DEPTH_TABLE)
    rows["depth_m"] = []
    rows["valid_mask"] = []
    return rows


def _empty_target_eval_crop_rows() -> dict[str, list[Any]]:
    rows = _empty_rows(TARGET_EVAL_CROP_TABLE)
    rows["points_world"] = []
    rows["mask"] = []
    return rows


def _append_target_eval_crop_rows(
    rows: dict[str, list[Any]],
    *,
    evidence: Any,
    candidate_valid: torch.Tensor,
    step_row_id: int,
    candidate_row_id_start: int,
    crop_row_id_start: int,
    dictionaries: dict[str, list[str]],
    fixed_max_points: int,
) -> int:
    """Append oracle/eval-only target crop rows for current and candidate geometry."""

    crop_row_id = int(crop_row_id_start)
    crop_policy_id = _dict_id(dictionaries["config"], evidence.target_eval_crop_policy or "")
    voxel_size_m = _float_or_nan(evidence.target_eval_voxel_size_m)
    max_points = _int_or_default(evidence.target_eval_max_points, default=fixed_max_points)

    if evidence.target_eval_current_points_world is not None:
        points, mask, length = _fixed_crop_payload(evidence.target_eval_current_points_world, fixed_max_points)
        _append_target_eval_crop_row(
            rows,
            crop_row_id=crop_row_id,
            step_row_id=step_row_id,
            candidate_row_id=-1,
            source_role_id=0,
            crop_policy_id=crop_policy_id,
            voxel_size_m=voxel_size_m,
            max_points=max_points,
            points_world=points,
            mask=mask,
            length=length,
        )
        crop_row_id += 1

    if evidence.target_eval_candidate_points_world is None:
        return crop_row_id
    lengths = evidence.target_eval_candidate_point_lengths
    if lengths is None:
        raise ValueError("target_eval_candidate_point_lengths requires target_eval_candidate_points_world.")
    points_q = torch.as_tensor(evidence.target_eval_candidate_points_world).detach().cpu()
    lengths_q = torch.as_tensor(lengths).detach().cpu().to(dtype=torch.long).reshape(-1)
    valid_indices = torch.nonzero(candidate_valid, as_tuple=False).reshape(-1)
    if points_q.ndim != 3 or points_q.shape[0] != valid_indices.numel():
        raise ValueError("target_eval_candidate_points_world must align with valid candidate rows.")
    if lengths_q.shape[0] != valid_indices.numel():
        raise ValueError("target_eval_candidate_point_lengths must align with valid candidate rows.")
    for compact_index, shell_index_t in enumerate(valid_indices):
        shell_index = int(shell_index_t.detach().cpu().item())
        length = int(lengths_q[compact_index].item())
        row_points = points_q[compact_index, :length, :3]
        points, mask, fixed_length = _fixed_crop_payload(row_points, fixed_max_points)
        _append_target_eval_crop_row(
            rows,
            crop_row_id=crop_row_id,
            step_row_id=step_row_id,
            candidate_row_id=candidate_row_id_start + shell_index,
            source_role_id=1,
            crop_policy_id=crop_policy_id,
            voxel_size_m=voxel_size_m,
            max_points=max_points,
            points_world=points,
            mask=mask,
            length=fixed_length,
        )
        crop_row_id += 1
    return crop_row_id


def _append_target_eval_crop_row(
    rows: dict[str, list[Any]],
    *,
    crop_row_id: int,
    step_row_id: int,
    candidate_row_id: int,
    source_role_id: int,
    crop_policy_id: int,
    voxel_size_m: float,
    max_points: int,
    points_world: np.ndarray,
    mask: np.ndarray,
    length: int,
) -> None:
    rows["crop_row_id"].append(int(crop_row_id))
    rows["step_row_id"].append(int(step_row_id))
    rows["candidate_row_id"].append(int(candidate_row_id))
    rows["source_role_id"].append(int(source_role_id))
    rows["crop_policy_id"].append(int(crop_policy_id))
    rows["voxel_size_m"].append(float(voxel_size_m))
    rows["max_points"].append(int(max_points))
    rows["lengths"].append(int(length))
    rows["points_world"].append(points_world)
    rows["mask"].append(mask)


def _fixed_crop_payload(points: torch.Tensor, max_points: int) -> tuple[np.ndarray, np.ndarray, int]:
    pts = torch.as_tensor(points).detach().cpu().to(dtype=torch.float32).reshape(-1, 3)
    finite = torch.isfinite(pts).all(dim=-1)
    pts = pts[finite]
    length = min(int(pts.shape[0]), int(max_points))
    output = np.zeros((int(max_points), 3), dtype=np.float32)
    mask = np.zeros((int(max_points),), dtype=np.bool_)
    if length > 0:
        output[:length, :] = pts[:length].numpy().astype(np.float32, copy=False)
        mask[:length] = True
    return output, mask, length


def _append_candidate_row(
    rows: dict[str, list[Any]],
    *,
    step: CounterfactualStepResult,
    labels: Any,
    candidate_valid: torch.Tensor,
    candidate_row_id: int,
    step_row_id: int,
    rollout_row_id: int,
    shell_index: int,
    root_pose: torch.Tensor,
    dictionaries: dict[str, list[str]],
    target_label_valid: bool,
) -> None:
    is_valid = bool(candidate_valid[shell_index].item())
    is_selected = int(step.selected_shell_index) == int(shell_index)
    target_rri = _metric_value(labels, step, ("target_rri", "oracle_target_rri"), shell_index)
    scene_rri = _metric_value(labels, step, ("scene_rri", "oracle_scene_rri"), shell_index)
    target_root_gain = _metric_value(labels, step, ("target_root_gain", "root_gain"), shell_index)
    scene_root_gain = _metric_value(labels, step, ("scene_root_gain",), shell_index)
    target_log_error_gain = _metric_value(labels, step, ("target_log_error_gain", "log_error_gain"), shell_index)
    scene_log_error_gain = _metric_value(labels, step, ("scene_log_error_gain",), shell_index)
    target_pm_dist_before = _metric_value(labels, step, ("target_pm_dist_before",), shell_index)
    target_pm_dist_after = _metric_value(labels, step, ("target_pm_dist_after",), shell_index)
    scene_pm_dist_before = _metric_value(labels, step, ("scene_pm_dist_before",), shell_index)
    scene_pm_dist_after = _metric_value(labels, step, ("scene_pm_dist_after",), shell_index)
    target_current_support = _metric_value(labels, step, ("target_current_support",), shell_index)
    target_candidate_support = _metric_value(labels, step, ("target_candidate_support",), shell_index)
    if not is_valid:
        target_rri = float("nan")
        scene_rri = float("nan")
        target_root_gain = float("nan")
        scene_root_gain = float("nan")
        target_log_error_gain = float("nan")
        scene_log_error_gain = float("nan")
        target_pm_dist_before = float("nan")
        target_pm_dist_after = float("nan")
        scene_pm_dist_before = float("nan")
        scene_pm_dist_after = float("nan")
        target_current_support = float("nan")
        target_candidate_support = float("nan")
    oracle_label = bool(is_valid and np.isfinite(target_root_gain))
    q_train = bool(is_valid and oracle_label and target_label_valid)
    pose = step.candidates.shell_poses.tensor()[shell_index].detach().cpu().numpy().astype(np.float32)
    rows["candidate_row_id"].append(candidate_row_id)
    rows["step_row_id"].append(step_row_id)
    rows["rollout_row_id"].append(rollout_row_id)
    rows["step_index"].append(step.step_index)
    rows["shell_index"].append(shell_index)
    rows["compact_valid_index"].append(_compact_valid_index(candidate_valid, shell_index))
    rows["pose_world_cam"].append(pose)
    rows["pose_relative_root"].append(_relative_pose_to_root(pose_world_cam=pose, root_pose_world=root_pose))
    rows["actor_action_mask"].append(is_valid)
    rows["oracle_label_mask"].append(oracle_label)
    rows["q_train_mask"].append(q_train)
    rows["selected_mask"].append(is_selected)
    rows["strategy_id"].append(_full_shell_value(step.candidates.strategy_id, shell_index, candidate_valid, default=-1))
    rows["position_id"].append(_full_shell_value(step.candidates.position_id, shell_index, candidate_valid, default=-1))
    rows["mixture_id"].append(_full_shell_value(step.candidates.mixture_id, shell_index, candidate_valid, default=-1))
    rows["sampler_probability"].append(
        _full_shell_value(step.candidates.sampler_probability, shell_index, candidate_valid, default=np.nan)
    )
    rows["score_source_id"].append(_dict_id(dictionaries["score_source"], step.selection_score_label))
    reason_bitset, primary_reason = _candidate_invalid_reasons(step.candidates)
    rows["invalid_reason_bitset"].append(int(reason_bitset[shell_index].item()))
    rows["primary_invalid_reason"].append(int(primary_reason[shell_index].item()))
    rows["scene_rri"].append(scene_rri)
    rows["target_rri"].append(target_rri)
    rows["scene_root_gain"].append(scene_root_gain)
    rows["target_root_gain"].append(target_root_gain)
    rows["scene_log_error_gain"].append(scene_log_error_gain)
    rows["target_log_error_gain"].append(target_log_error_gain)
    rows["scene_pm_dist_before"].append(scene_pm_dist_before)
    rows["scene_pm_dist_after"].append(scene_pm_dist_after)
    rows["target_pm_dist_before"].append(target_pm_dist_before)
    rows["target_pm_dist_after"].append(target_pm_dist_after)
    rows["target_current_support"].append(target_current_support)
    rows["target_candidate_support"].append(target_candidate_support)
    rows["selection_logits"].append(
        _valid_vector_value(step.selection_logits, shell_index, candidate_valid, default=np.nan)
    )
    rows["selection_probabilities"].append(
        _valid_vector_value(step.selection_probabilities, shell_index, candidate_valid, default=0.0)
    )
    rows["selection_log_probabilities"].append(
        _valid_vector_value(step.selection_log_probabilities, shell_index, candidate_valid, default=-np.inf)
    )


def _append_candidate_diagnostic_row(
    rows: dict[str, list[Any]],
    *,
    step: CounterfactualStepResult,
    candidate_valid: torch.Tensor,
    candidate_row_id: int,
    shell_index: int,
) -> None:
    """Append typed candidate-generation diagnostics for one full-shell row."""

    rows["candidate_row_id"].append(int(candidate_row_id))
    rows["position_id"].append(_full_shell_value(step.candidates.position_id, shell_index, candidate_valid, default=-1))
    rows["mesh_distance_m"].append(
        _candidate_extra_value(step.candidates.extras, "min_distance_to_mesh", shell_index, candidate_valid)
    )
    rows["path_min_clearance_m"].append(
        _candidate_extra_value(step.candidates.extras, "path_min_clearance_m", shell_index, candidate_valid)
    )
    rows["path_collision_mask"].append(
        _candidate_extra_bool(step.candidates.extras, "path_collision_mask", shell_index, candidate_valid)
    )
    rows["free_space_margin_m"].append(
        _candidate_extra_value(step.candidates.extras, "free_space_margin_m", shell_index, candidate_valid)
    )
    rows["motion_step_length_m"].append(
        _candidate_extra_value(step.candidates.extras, "motion_step_length_m", shell_index, candidate_valid)
    )
    rows["motion_height_delta_m"].append(
        _candidate_extra_value(step.candidates.extras, "motion_height_delta_m", shell_index, candidate_valid)
    )
    rows["motion_backward_step_m"].append(
        _candidate_extra_value(step.candidates.extras, "motion_backward_step_m", shell_index, candidate_valid)
    )
    rows["motion_yaw_delta_deg"].append(
        np.degrees(_candidate_extra_value(step.candidates.extras, "motion_yaw_delta_rad", shell_index, candidate_valid))
    )
    rows["target_distance_m"].append(
        _candidate_extra_value(step.candidates.extras, "target_distance_m", shell_index, candidate_valid)
    )
    rows["target_bearing_yaw_deg"].append(
        np.degrees(
            _candidate_extra_value(step.candidates.extras, "target_bearing_yaw_rad", shell_index, candidate_valid)
        )
    )


def _append_selected_depth_row(
    rows: dict[str, list[Any]],
    *,
    evidence: Any,
    step_row_id: int,
    selected_candidate_row_id: int,
) -> None:
    """Append one selected-action depth row when the step carries a raster."""

    if evidence.selected_depth_m is None and evidence.selected_depth_valid_mask is None:
        return
    if evidence.selected_depth_m is None or evidence.selected_depth_valid_mask is None:
        raise ValueError("selected_depth_m and selected_depth_valid_mask must be present together.")

    depth = torch.as_tensor(evidence.selected_depth_m).detach().cpu()
    valid_mask = torch.as_tensor(evidence.selected_depth_valid_mask).detach().cpu().to(dtype=torch.bool)
    if depth.ndim != 2:
        raise ValueError(f"selected_depth_m must have shape (H,W), got {tuple(depth.shape)}.")
    if valid_mask.shape != depth.shape:
        raise ValueError(
            f"selected_depth_valid_mask shape {tuple(valid_mask.shape)} must match depth {tuple(depth.shape)}."
        )

    depth_np = depth.to(dtype=torch.float32).numpy()
    valid_np = valid_mask.numpy().astype(bool, copy=False)
    depth_filled = np.where(np.isfinite(depth_np) & valid_np, depth_np, SELECTED_DEPTH_INVALID_FILL_VALUE).astype(
        np.float16
    )

    height, width = depth_filled.shape
    rows["step_row_id"].append(int(step_row_id))
    rows["candidate_row_id"].append(int(selected_candidate_row_id))
    rows["depth_m"].append(depth_filled)
    rows["valid_mask"].append(valid_np)
    rows["focal_px"].append(_fixed_float_vector(evidence.selected_depth_focal_px, length=2))
    rows["principal_point_px"].append(_fixed_float_vector(evidence.selected_depth_principal_point_px, length=2))
    rows["image_size_hw"].append(_selected_depth_image_size(evidence, height=height, width=width))


def _write_rollout_tables(groups: dict[str, zarr.Group], tables: _RolloutTables) -> None:
    for name, values in tables.sources.items():
        _write_array(groups["sources"], name, values)
    for name, values in tables.rollouts.items():
        _write_array(groups["rollouts"], name, values)
    for name, values in tables.lineage.items():
        _write_array(groups["lineage"], name, values)
    for name, values in tables.steps.items():
        _write_array(groups["steps"], name, values)
    for name, values in tables.candidates.items():
        _write_array(groups["candidates"], name, values)
    for name, values in tables.candidate_diagnostics.items():
        _write_array(groups["candidate_diagnostics"], name, values)


def _write_selected_depth_group(
    group: zarr.Group,
    values: dict[str, np.ndarray],
    *,
    enabled: bool,
    width_px: int,
    height_px: int,
    chunk_steps: int,
    renderer: str,
    znear_m: float | None,
    zfar_m: float | None,
    source_resolution: str,
) -> None:
    """Write selected-action depth rasters and row metadata."""

    group.attrs.update(
        {
            "enabled": bool(enabled),
            "width_px": int(width_px),
            "height_px": int(height_px),
            "depth_dtype": "float16",
            "valid_mask_dtype": "bool",
            "units": "m",
            "invalid_fill_value": SELECTED_DEPTH_INVALID_FILL_VALUE,
            "codec": SELECTED_DEPTH_CODEC,
            "chunk_steps": int(chunk_steps),
            "role": "selected_successor_state_history",
            "renderer": renderer,
            "znear_m": _float_or_nan(znear_m),
            "zfar_m": _float_or_nan(zfar_m),
            "source_resolution": source_resolution,
        }
    )
    for name in SELECTED_DEPTH_TABLE.names:
        _write_array(group, name, values[name])
    _write_selected_depth_array(group, "depth_m", values["depth_m"], chunk_steps=chunk_steps)
    _write_selected_depth_array(group, "valid_mask", values["valid_mask"], chunk_steps=chunk_steps)


def _write_target_eval_crops_group(
    group: zarr.Group,
    values: dict[str, np.ndarray],
    *,
    dictionaries: dict[str, list[str]],
    max_points: int,
    enabled: bool,
) -> None:
    """Write oracle/eval-only target crop point payloads and row metadata."""

    group.attrs.update(
        {
            "enabled": bool(enabled),
            "role": "oracle_eval_only",
            "coordinate_frame": "world",
            "points_dtype": "float32",
            "mask_dtype": "bool",
            "max_points": int(max_points),
            "source_roles": "current_eval,candidate_eval",
            "retention": "sampled_audit" if enabled else "disabled_training_core",
        }
    )
    for name in TARGET_EVAL_CROP_TABLE.names:
        _write_array(group, name, values[name])
    _write_array(group, "points_world", values["points_world"])
    _write_array(group, "mask", values["mask"])
    _write_string_array(group, "source_role_names", ["current_eval", "candidate_eval"])
    _write_string_array(group, "crop_policy_dictionary", dictionaries.get("config", []))


def _write_q_h_group(
    group: zarr.Group,
    values: dict[str, np.ndarray],
    *,
    chunk_states: int,
    horizon: int,
    gamma: float,
    return_semantics: str,
) -> None:
    """Write the derived dense finite-candidate training view."""

    state_count = int(values["state_step_row_id"].shape[0])
    max_candidates = int(values["candidate_row_id"].shape[1]) if values["candidate_row_id"].ndim == 2 else 0
    group.attrs.update(
        {
            "view_role": "training_core_derived_cache",
            "source_tables": "steps,candidates,rollouts,targets",
            "td_semantics": Q_H_TD_SEMANTICS,
            "reward_metric": Q_H_REWARD_METRIC,
            "return_semantics": return_semantics,
            "td_reward_target_rri_role": "diagnostic_state_relative_rri",
            "state_count": state_count,
            "max_candidates": max_candidates,
            "horizon": int(horizon),
            "discount_gamma": float(gamma),
            "chunk_states": int(chunk_states),
        }
    )
    for name in Q_H_ARRAY_NAMES:
        _write_q_h_array(group, name, values[name], chunk_states=chunk_states)


def _build_q_h_arrays(tables: _RolloutTables, *, gamma: float) -> dict[str, np.ndarray]:
    steps = tables.steps
    candidates = tables.candidates
    rollouts = tables.rollouts
    step_ids = steps["step_row_id"].astype(np.int64)
    candidate_step_ids = candidates["step_row_id"].astype(np.int64)
    max_candidates = _max_candidates_per_step(steps, candidates)
    state_count = int(step_ids.shape[0])

    q = {
        "state_step_row_id": step_ids,
        "source_row_id": np.full((state_count,), -1, dtype=np.int64),
        "candidate_row_id": np.full((state_count, max_candidates), -1, dtype=np.int64),
        "valid_action_mask": np.zeros((state_count, max_candidates), dtype=np.bool_),
        "q_train_mask": np.zeros((state_count, max_candidates), dtype=np.bool_),
        "target_row_id": np.zeros((state_count,), dtype=np.int64),
        "selected_candidate_index": np.full((state_count,), -1, dtype=np.int32),
        "position_id": np.full((state_count, max_candidates), -1, dtype=np.int32),
        "one_step_target_rri": np.full((state_count, max_candidates), np.nan, dtype=np.float32),
        "one_step_target_root_gain": np.full((state_count, max_candidates), np.nan, dtype=np.float32),
        "invalid_reason_bitset": np.zeros((state_count, max_candidates), dtype=np.uint32),
        "td_selected_candidate_row_id": np.full((state_count,), -1, dtype=np.int64),
        "td_reward": np.full((state_count,), np.nan, dtype=np.float32),
        "td_reward_target_rri": np.full((state_count,), np.nan, dtype=np.float32),
        "td_next_step_row_id": np.full((state_count,), -1, dtype=np.int64),
        "td_terminal_mask": np.ones((state_count,), dtype=np.bool_),
        "td_discount": np.zeros((state_count,), dtype=np.float32),
    }

    next_step_by_rollout: dict[tuple[int, int], int] = {}
    for row, rollout_id in enumerate(steps["rollout_row_id"]):
        step_index = int(steps["step_index"][row])
        next_step_by_rollout[(int(rollout_id), step_index)] = int(steps["step_row_id"][row])

    for row, step_id in enumerate(step_ids):
        indices = np.nonzero(candidate_step_ids == step_id)[0]
        selected_candidate_row_id = int(steps["selected_candidate_row_id"][row])
        rollout_id = int(steps["rollout_row_id"][row])
        rollout_matches = np.nonzero(rollouts["rollout_row_id"] == rollout_id)[0]
        if rollout_matches.size == 1:
            rollout_row = int(rollout_matches[0])
            q["source_row_id"][row] = int(rollouts["source_row_id"][rollout_row])
            q["target_row_id"][row] = int(rollouts["target_row_id"][rollout_row])
        selected_local_index = -1
        for local_index, candidate_index in enumerate(indices):
            q["candidate_row_id"][row, local_index] = int(candidates["candidate_row_id"][candidate_index])
            q["valid_action_mask"][row, local_index] = bool(candidates["actor_action_mask"][candidate_index])
            q["q_train_mask"][row, local_index] = bool(candidates["q_train_mask"][candidate_index])
            q["position_id"][row, local_index] = int(candidates["position_id"][candidate_index])
            q["one_step_target_rri"][row, local_index] = float(candidates["target_rri"][candidate_index])
            q["one_step_target_root_gain"][row, local_index] = float(candidates["target_root_gain"][candidate_index])
            q["invalid_reason_bitset"][row, local_index] = int(candidates["invalid_reason_bitset"][candidate_index])
            if int(candidates["candidate_row_id"][candidate_index]) == selected_candidate_row_id:
                selected_local_index = local_index

        q["selected_candidate_index"][row] = selected_local_index
        q["td_selected_candidate_row_id"][row] = selected_candidate_row_id
        if selected_local_index >= 0:
            q["td_reward"][row] = q["one_step_target_root_gain"][row, selected_local_index]
            q["td_reward_target_rri"][row] = q["one_step_target_rri"][row, selected_local_index]
            next_step = next_step_by_rollout.get((rollout_id, int(steps["step_index"][row]) + 1), -1)
            q["td_next_step_row_id"][row] = next_step
            q["td_terminal_mask"][row] = next_step < 0
            if next_step >= 0:
                q["td_discount"][row] = float(gamma)

    q["q_train_mask"] &= q["valid_action_mask"]
    q["one_step_target_rri"][~q["valid_action_mask"]] = np.nan
    q["one_step_target_root_gain"][~q["valid_action_mask"]] = np.nan
    return q


def _table_horizon(tables: _RolloutTables) -> int:
    values = tables.rollouts["horizon"]
    return int(values.max()) if values.size else 1


def _rows_to_numpy_table(rows: dict[str, list[Any]], schema: _TableSchema) -> dict[str, np.ndarray]:
    expected = set(schema.names)
    if set(rows) != expected:
        missing = sorted(expected - set(rows))
        extra = sorted(set(rows) - expected)
        raise ValueError(f"Row table fields do not match schema; missing={missing}, extra={extra}.")
    return {name: np.asarray(rows[name], dtype=dtype) for name, dtype in schema.dtypes.items()}


def _rows_to_numpy_selected_depth_table(
    rows: dict[str, list[Any]],
    *,
    width_px: int,
    height_px: int,
) -> dict[str, np.ndarray]:
    expected = set(SELECTED_DEPTH_TABLE.names) | {"depth_m", "valid_mask"}
    if set(rows) != expected:
        missing = sorted(expected - set(rows))
        extra = sorted(set(rows) - expected)
        raise ValueError(f"Selected-depth fields do not match schema; missing={missing}, extra={extra}.")
    table = {name: np.asarray(rows[name], dtype=dtype) for name, dtype in SELECTED_DEPTH_TABLE.dtypes.items()}
    for name in ("focal_px", "principal_point_px", "image_size_hw"):
        dtype = SELECTED_DEPTH_TABLE.dtypes[name]
        table[name] = np.asarray(rows[name], dtype=dtype).reshape((-1, 2))
    if rows["depth_m"]:
        table["depth_m"] = np.stack(rows["depth_m"], axis=0).astype(np.float16, copy=False)
        table["valid_mask"] = np.stack(rows["valid_mask"], axis=0).astype(np.bool_, copy=False)
    else:
        table["depth_m"] = np.empty((0, int(height_px), int(width_px)), dtype=np.float16)
        table["valid_mask"] = np.empty((0, int(height_px), int(width_px)), dtype=np.bool_)
    return table


def _rows_to_numpy_target_eval_crop_table(
    rows: dict[str, list[Any]],
    *,
    max_points: int,
) -> dict[str, np.ndarray]:
    expected = set(TARGET_EVAL_CROP_TABLE.names) | {"points_world", "mask"}
    if set(rows) != expected:
        missing = sorted(expected - set(rows))
        extra = sorted(set(rows) - expected)
        raise ValueError(f"Target eval crop fields do not match schema; missing={missing}, extra={extra}.")
    table = {name: np.asarray(rows[name], dtype=dtype) for name, dtype in TARGET_EVAL_CROP_TABLE.dtypes.items()}
    if rows["points_world"]:
        table["points_world"] = np.stack(rows["points_world"], axis=0).astype(np.float32, copy=False)
        table["mask"] = np.stack(rows["mask"], axis=0).astype(np.bool_, copy=False)
    else:
        table["points_world"] = np.empty((0, int(max_points), 3), dtype=np.float32)
        table["mask"] = np.empty((0, int(max_points)), dtype=np.bool_)
    return table


def _read_tables_from_root(root: Any) -> _RolloutTables:
    return _RolloutTables(
        sources=_read_group_table(root, SOURCE_TABLE),
        rollouts=_read_group_table(root, ROLLOUT_TABLE),
        lineage=_read_group_table(root, LINEAGE_TABLE),
        steps=_read_group_table(root, STEP_TABLE),
        candidates=_read_group_table(root, CANDIDATE_TABLE),
        candidate_diagnostics=_read_group_table(root, CANDIDATE_DIAGNOSTIC_TABLE),
        selected_depth=_read_selected_depth_table(root),
        target_eval_crops=_read_target_eval_crop_table(root),
    )


def _read_group_table(root: Any, schema: _TableSchema) -> dict[str, np.ndarray]:
    return {field.name: np.asarray(root[f"{schema.name}/{field.name}"]) for field in schema.fields}


def _read_selected_depth_table(root: Any) -> dict[str, np.ndarray]:
    group = root["selected_depth"]
    values = {field.name: np.asarray(group[field.name]) for field in SELECTED_DEPTH_TABLE.fields}
    values["depth_m"] = np.empty((0, 0, 0), dtype=np.float16)
    values["valid_mask"] = np.empty((0, 0, 0), dtype=bool)
    return values


def _read_target_eval_crop_table(root: Any) -> dict[str, np.ndarray]:
    if "target_eval_crops" not in root:
        values = {field.name: np.empty((0,), dtype=field.dtype) for field in TARGET_EVAL_CROP_TABLE.fields}
        values["points_world"] = np.empty((0, 0, 3), dtype=np.float32)
        values["mask"] = np.empty((0, 0), dtype=np.bool_)
        return values
    group = root["target_eval_crops"]
    values = {field.name: np.asarray(group[field.name]) for field in TARGET_EVAL_CROP_TABLE.fields}
    values["points_world"] = np.asarray(group["points_world"])
    values["mask"] = np.asarray(group["mask"])
    return values


def _read_q_h_arrays(root: Any) -> dict[str, np.ndarray]:
    group = root["q_h"]
    return {name: np.asarray(group[name]) for name in Q_H_ARRAY_NAMES}


def _read_q_h_arrays_if_present(root: Any) -> dict[str, np.ndarray]:
    if "q_h" not in root:
        return {}
    group = root["q_h"]
    return {name: np.asarray(group[name]) for name in Q_H_ARRAY_NAMES if name in group}


def _q_h_arrays_for_validation(root: Any) -> dict[str, np.ndarray]:
    values = _read_q_h_arrays_if_present(root)
    if all(name in values for name in Q_H_ARRAY_NAMES):
        return values
    return _build_q_h_arrays(
        _read_tables_from_root(root),
        gamma=float(root.attrs.get("discount_gamma", 1.0)),
    )


def _stored_horizon(root: Any) -> int:
    values = np.asarray(root["rollouts/horizon"])
    return int(values.max()) if values.size else 1


def _max_candidates_per_step(steps: dict[str, np.ndarray], candidates: dict[str, np.ndarray]) -> int:
    candidate_step_ids = candidates["step_row_id"].astype(np.int64)
    return max((int((candidate_step_ids == int(step_id)).sum()) for step_id in steps["step_row_id"]), default=0)


def _write_array(group: zarr.Group, name: str, values: np.ndarray) -> zarr.Array:
    array = np.asarray(values)
    chunks = _default_chunks(array)
    zarr_array = group.create_array(name, shape=array.shape, chunks=chunks, dtype=array.dtype, overwrite=True)
    zarr_array[...] = array
    return zarr_array


def _write_selected_depth_array(
    group: zarr.Group,
    name: str,
    values: np.ndarray,
    *,
    chunk_steps: int,
) -> zarr.Array:
    array = np.asarray(values)
    chunks = _selected_depth_chunks(array, chunk_steps=chunk_steps)
    zarr_array = group.create_array(
        name,
        shape=array.shape,
        chunks=chunks,
        dtype=array.dtype,
        compressors=_selected_depth_compressors(array.dtype),
        overwrite=True,
    )
    zarr_array[...] = array
    return zarr_array


def _write_q_h_array(
    group: zarr.Group,
    name: str,
    values: np.ndarray,
    *,
    chunk_states: int,
) -> zarr.Array:
    array = np.asarray(values)
    chunks = _q_h_chunks(array, chunk_states=chunk_states)
    zarr_array = group.create_array(name, shape=array.shape, chunks=chunks, dtype=array.dtype, overwrite=True)
    zarr_array[...] = array
    return zarr_array


def _write_string_array(group: zarr.Group, name: str, values: list[str]) -> None:
    encoded = np.frombuffer(json.dumps(values, ensure_ascii=True).encode("utf-8"), dtype=np.uint8)
    _write_array(group, name, encoded)


def _decode_string_array(value: Any) -> list[str]:
    encoded = np.asarray(value, dtype=np.uint8)
    return json.loads(encoded.tobytes().decode("utf-8"))


def _read_string_array(root: Any, path: str) -> list[str]:
    """Read a required JSON-encoded string array from the store."""
    return _decode_string_array(root[path])


def _default_chunks(array: np.ndarray) -> tuple[int, ...] | None:
    if array.ndim == 0:
        return None
    if array.ndim == 1:
        return (min(max(int(array.shape[0]), 1), 1024),)
    return (1, *array.shape[1:])


def _selected_depth_chunks(array: np.ndarray, *, chunk_steps: int) -> tuple[int, ...]:
    if array.ndim != 3:
        raise ValueError(f"Selected-depth arrays must have shape (D,H,W), got {array.shape}.")
    first = max(1, min(int(chunk_steps), max(int(array.shape[0]), 1)))
    return (first, int(array.shape[1]), int(array.shape[2]))


def _q_h_chunks(array: np.ndarray, *, chunk_states: int) -> tuple[int, ...] | None:
    if array.ndim == 0:
        return None
    first = max(1, min(int(chunk_states), max(int(array.shape[0]), 1)))
    if array.ndim == 1:
        return (first,)
    if array.ndim == 2:
        second = max(1, int(array.shape[1]))
        return (first, second)
    return (first, *tuple(max(1, int(dim)) for dim in array.shape[1:]))


def _q_h_arrays_differ(actual: np.ndarray, expected: np.ndarray) -> bool:
    if np.issubdtype(actual.dtype, np.floating):
        return not np.allclose(actual, expected, equal_nan=True)
    return not np.array_equal(actual, expected)


def _selected_depth_compressors(dtype: np.dtype[Any]) -> tuple[BloscCodec, ...]:
    return (
        BloscCodec(
            typesize=np.dtype(dtype).itemsize,
            cname=BloscCname.zstd,
            clevel=5,
            shuffle=BloscShuffle.bitshuffle,
        ),
    )


def _dict_id(values: list[str], value: str) -> int:
    try:
        return values.index(value)
    except ValueError:
        return -1


def _record_items(
    records: list[_RolloutWriteRecord],
) -> Iterator[tuple[_RolloutWriteRecord, CounterfactualTrajectory, RolloutLineage]]:
    for record in records:
        for chain_id, trajectory in enumerate(record.evaluated.result.trajectories):
            yield record, trajectory, _lineage_for_chain(record, chain_id)


def _lineage_for_chain(record: _RolloutWriteRecord, chain_id: int) -> RolloutLineage:
    return record.lineage.for_chain(
        chain_id,
        rollout_id=f"{record.rollout_id_prefix}-{chain_id:06d}",
        rollout_policy=str(record.evaluated.result.selection_policy),
    )


def _first_temperature(trajectory: CounterfactualTrajectory) -> float:
    for step in trajectory.steps:
        if step.selection_temperature is not None:
            return float(step.selection_temperature)
    return float("nan")


def _nan_if_none(value: float | None) -> float:
    return float("nan") if value is None else float(value)


def _trajectory_cumulative_metric(
    record: Any,
    chain_id: int,
    trajectory: CounterfactualTrajectory,
    metric_names: tuple[str, ...],
) -> float | None:
    cumulative: float | None = None
    for step in trajectory.steps:
        cumulative = _accumulate_selected_metric(
            cumulative,
            _evaluated_step(record, chain_id, step.step_index),
            metric_names,
        )
    return cumulative


def _accumulate_selected_metric(
    current: float | None,
    evaluated_step: Any,
    metric_names: tuple[str, ...],
) -> float | None:
    selected_metrics = evaluated_step.evaluation.labels.selected(
        evaluated_step.transition.selected_valid_index,
    )
    for metric_name in metric_names:
        value = selected_metrics.get(metric_name)
        if value is not None and np.isfinite(float(value)):
            return float(value) if current is None else float(current + float(value))
    return current


def _float_or_nan(value: Any) -> float:
    return float("nan") if value is None else float(value)


def _fixed_float_vector(value: Any, *, length: int) -> np.ndarray:
    if value is None:
        return np.full((length,), np.nan, dtype=np.float32)
    array = np.asarray(value, dtype=np.float32).reshape(-1)
    if array.shape[0] != length:
        return np.full((length,), np.nan, dtype=np.float32)
    return array


def _selected_depth_image_size(evidence: _SelectedDepthEvidence, *, height: int, width: int) -> np.ndarray:
    if evidence.selected_depth_image_size_hw is None:
        return np.asarray([height, width], dtype=np.int32)
    array = np.asarray(evidence.selected_depth_image_size_hw, dtype=np.int32).reshape(-1)
    if array.shape[0] != 2:
        return np.asarray([height, width], dtype=np.int32)
    return array


def _int_or_default(value: Any, *, default: int) -> int:
    return int(default) if value is None else int(value)


def _candidate_valid(step: CounterfactualStepResult) -> torch.Tensor:
    return step.candidates.mask_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)


def _compact_valid_index(candidate_valid: torch.Tensor, shell_index: int) -> int:
    if not bool(candidate_valid[shell_index].item()):
        return -1
    valid_indices = np.nonzero(candidate_valid.detach().cpu().numpy().astype(bool))[0]
    matches = np.nonzero(valid_indices == int(shell_index))[0]
    if matches.size != 1:
        return -1
    return int(matches[0])


def _metric_value(
    labels: Any,
    step: CounterfactualStepResult,
    metric_names: tuple[str, ...],
    shell_index: int,
) -> float:
    for metric_name in metric_names:
        values = labels.metrics.get(metric_name)
        if values is not None:
            return float(_valid_vector_value(values, shell_index, _candidate_valid(step), default=np.nan))
    return float("nan")


def _evaluated_step(record: Any, chain_id: int, step_index: int) -> Any:
    evaluated = record.evaluated.step(chain_id, step_index)
    if evaluated is None:
        raise ValueError(f"Missing Oracle labels for rollout chain={chain_id} step={step_index}.")
    return evaluated


def _full_shell_value(
    values: torch.Tensor | None,
    shell_index: int,
    candidate_valid: torch.Tensor,
    *,
    default: float | int,
) -> float | int:
    full = _full_shell_or_default(values, candidate_valid, fill_value=default)
    return full[shell_index].detach().cpu().item()


def _candidate_extra_value(
    extras: dict[str, Any],
    name: str,
    shell_index: int,
    candidate_valid: torch.Tensor,
) -> float:
    value = extras.get(name)
    if value is None:
        return float("nan")
    tensor = torch.as_tensor(value).detach().cpu()
    full = _full_shell_or_default(tensor, candidate_valid, fill_value=float("nan"))
    return float(full[shell_index].item())


def _candidate_extra_bool(
    extras: dict[str, Any],
    name: str,
    shell_index: int,
    candidate_valid: torch.Tensor,
) -> bool:
    value = extras.get(name)
    if value is None:
        return False
    tensor = torch.as_tensor(value).detach().cpu().to(dtype=torch.bool)
    full = _full_shell_or_default(tensor, candidate_valid, fill_value=0)
    return bool(full[shell_index].item())


def _valid_vector_value(
    values: torch.Tensor | None,
    shell_index: int,
    candidate_valid: torch.Tensor,
    *,
    default: float | int,
) -> float | int:
    if values is None:
        return default
    vector = values.detach().cpu().reshape(-1)
    valid_mask = candidate_valid.detach().cpu().to(dtype=torch.bool).reshape(-1)
    if vector.numel() == valid_mask.numel():
        return vector[shell_index].item()
    if vector.numel() != int(valid_mask.sum().item()):
        raise ValueError(
            f"Expected either {valid_mask.numel()} full-shell values or {int(valid_mask.sum().item())} "
            f"valid-candidate values, got {vector.numel()}."
        )
    if not bool(valid_mask[shell_index].item()):
        return default
    return vector[_compact_valid_index(valid_mask, shell_index)].item()


def _lineage_target_label_valid(lineage: RolloutLineage) -> bool:
    protocol = lineage.target.target_protocol_version or TargetInputProtocol.V0_GT_INPUT
    target_bitset = lineage.target.target_invalid_reason_bitset
    return target_label_is_trainable(
        TargetLabelEvidence(
            protocol=protocol,
            target_source=lineage.target.target_source,
            gt_match_status=lineage.target.gt_match_status,
            matched_gt_target_row_id=lineage.target.matched_gt_target_row_id,
            matched_gt_target_id=lineage.target.matched_gt_target_id,
            gt_match_iou=lineage.target.gt_match_iou,
            target_valid=(
                (target_bitset is None and protocol == TargetInputProtocol.V0_GT_INPUT)
                or (target_bitset is not None and int(target_bitset) == (1 << INVALID_REASON_CODES["VALID"]))
            ),
        )
    )


def _canonical_target_label_mask(root: zarr.Group) -> np.ndarray:
    """Materialize the one typed target-label mapping for persisted rows."""

    targets = root["targets"]
    protocol = str(root.attrs.get("target_protocol_version", ""))
    target_sources = _encoded_values(
        root,
        dictionary_name="target_source",
        array_path="targets/target_source_id",
    )
    target_ids = _read_string_array(root, "dictionaries/target")
    statuses = _read_string_array(root, "dictionaries/target_match_status")
    matched_ids = np.asarray(targets["matched_gt_target_id"], dtype=np.int64).reshape(-1)
    matched_rows = np.asarray(targets["matched_gt_target_row_id"], dtype=np.int64).reshape(-1)
    ious = np.asarray(targets["gt_match_iou"], dtype=np.float32).reshape(-1)
    status_ids = np.asarray(targets["gt_match_status_id"], dtype=np.int64).reshape(-1)
    target_valid = np.asarray(targets["target_valid_mask"], dtype=np.bool_).reshape(-1)
    target_reason = np.asarray(targets["target_invalid_reason_bitset"], dtype=np.uint32).reshape(-1)
    values: list[bool] = []
    for row, (match_id, match_row, iou, status_id) in enumerate(
        zip(matched_ids, matched_rows, ious, status_ids, strict=True)
    ):
        values.append(
            target_label_is_trainable(
                TargetLabelEvidence(
                    protocol=protocol,
                    target_source=target_sources[row] if row < len(target_sources) else None,
                    gt_match_status=statuses[int(status_id)] if 0 <= int(status_id) < len(statuses) else None,
                    matched_gt_target_row_id=int(match_row),
                    matched_gt_target_id=target_ids[int(match_id)] if 0 <= int(match_id) < len(target_ids) else None,
                    gt_match_iou=float(iou),
                    target_valid=bool(
                        target_valid[row] and target_reason[row] == np.uint32(1 << INVALID_REASON_CODES["VALID"])
                    ),
                )
            )
        )
    return np.asarray(values, dtype=np.bool_)


def _relative_pose_to_root(*, pose_world_cam: np.ndarray, root_pose_world: torch.Tensor) -> np.ndarray:
    root = PoseTW(root_pose_world.detach().cpu().to(dtype=torch.float32).reshape(-1))
    candidate = PoseTW(torch.as_tensor(pose_world_cam, dtype=torch.float32).reshape(-1))
    return root.inverse().compose(candidate).tensor().detach().cpu().numpy().astype(np.float32).reshape(-1)


def _missing_lineage_token(value: Any) -> bool:
    return value is None or str(value) == ""


def _target_identifier_mentions_other_snippet(*, identifier: str, snippet: str) -> bool:
    """Return true when a structured target id names a different snippet."""

    compact_snippet = compact_ase_atek_sample_id(snippet)
    raw_snippet = raw_ase_atek_sample_id(compact_snippet)
    if (
        not identifier
        or not snippet
        or snippet in identifier
        or compact_snippet in identifier
        or (raw_snippet is not None and raw_snippet in identifier)
    ):
        return False
    return "AtekDataSample_" in identifier or "AriaSyntheticEnvironment_" in identifier


def _encoded_values(root: Any, *, dictionary_name: str, array_path: str) -> list[str]:
    try:
        encoded = np.asarray(root[array_path])
    except KeyError:
        return []
    dictionary = _read_optional_string_array(root, f"dictionaries/{dictionary_name}")
    values: list[str] = []
    for index in encoded.reshape(-1):
        index_int = int(index)
        if index_int < 0 or index_int >= len(dictionary):
            values.append("")
        else:
            values.append(dictionary[index_int])
    return values


def _read_optional_string_array(root: Any, path: str) -> list[str]:
    """Read an optional JSON-encoded string array, returning empty when absent."""
    try:
        return _decode_string_array(root[path])
    except KeyError:
        return []


__all__ = [
    "DEFAULT_RETURN_SEMANTICS",
    "ROLLOUT_ZARR_SCHEMA_ID",
    "ROLLOUT_ZARR_SCHEMA_VERSION",
    "RolloutZarrStoreConfig",
    "RolloutZarrStoreReader",
    "RolloutZarrValidationResult",
    "RolloutZarrWriteResult",
    "validate_rollout_zarr_store",
    "write_rollout_zarr_store",
]
