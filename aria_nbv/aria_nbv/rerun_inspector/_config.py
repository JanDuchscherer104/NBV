"""Configuration models for the offline Rerun inspector.

The inspector follows the project config-as-factory pattern: the top-level
``RerunOfflineInspectorConfig`` owns the nested dataset, selection, output,
geometry, performance, and primitive toggles used by the CLI runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from aria_nbv.data_handling import VinOfflineDatasetConfig
from aria_nbv.utils import BaseConfig, TargetConfig, Verbosity


class RerunInspectorDatasetConfig(BaseConfig):
    """Force immutable VIN inspection onto the CPU sample-reader boundary.

    The nested dataset remains the provenance owner for sample, scene, snippet,
    store-manifest, and optional EVL/checkpoint facts. Validation rewrites only
    this config copy; the source store itself remains read-only.
    """

    offline: VinOfflineDatasetConfig = Field(
        default_factory=lambda: VinOfflineDatasetConfig(
            return_format="sample",
            map_location="cpu",
            load_candidates=True,
            load_candidate_pcs=False,
            load_depths=False,
            load_gt_obbs=True,
            load_detected_obbs=True,
            load_trajectory_metadata=True,
        ),
    )
    """Immutable VIN offline dataset reader used by the inspector."""

    @model_validator(mode="after")
    def _force_read_only_sample_reader(self) -> "RerunInspectorDatasetConfig":
        """Keep the inspector on the read-only sample-returning CPU path."""

        self.offline.return_format = "sample"
        self.offline.map_location = BaseConfig._resolve_device("cpu")
        return self


class RerunInspectorSelectionConfig(BaseConfig):
    """Resolve offline and rollout context with deterministic selector precedence.

    A sample key outranks scene/snippet identity, which outranks split-local
    index. Rollout context can inherit factual source identity from the rollout
    store or require/disable the immutable VIN overlay explicitly.
    """

    sample_key: str | None = None
    """Stable offline sample key. Highest precedence when provided."""

    scene_id: str | None = None
    """ASE scene identifier used with ``snippet_id`` when no sample key is set."""

    snippet_id: str | None = None
    """ASE snippet identifier used with ``scene_id`` when no sample key is set."""

    split: Literal["all", "train", "val"] = "val"
    """Split used for index-based selection."""

    index: int = Field(default=0, ge=0)
    """Zero-based index inside ``split`` when no higher-precedence selector is set."""

    rollout_context_mode: Literal["auto", "required", "off"] = "auto"
    """VIN context policy for rollout-Zarr inspection."""

    @model_validator(mode="after")
    def _validate_scene_snippet_pair(self) -> "RerunInspectorSelectionConfig":
        """Require scene/snippet selectors to be supplied together."""

        if (self.scene_id is None) ^ (self.snippet_id is None):
            raise ValueError("selection.scene_id and selection.snippet_id must be provided together.")
        return self


class RerunInspectorOutputConfig(BaseConfig):
    """Choose the single Rerun sink opened before any inspector entity logs.

    ``save`` owns an ``.rrd`` destination, ``spawn`` owns a local viewer
    process connection, and ``connect`` targets an existing gRPC server. The
    recording id groups all static and timeline entities from one inspector run.
    """

    mode: Literal["save", "spawn", "connect"] = "save"
    """Exactly one output sink opened immediately after Rerun initialization."""

    application_id: str = "aria-nbv-rerun-inspector"
    """Rerun application identifier."""

    recording_id: str | None = None
    """Optional stable recording id; ``None`` lets Rerun allocate session identity."""

    save_path: Path = Path(".logs") / "rerun" / "offline_inspector.rrd"
    """Owned ``.rrd`` destination whose parent is created for ``mode='save'``."""

    connect_addr: str | None = None
    """Existing Rerun gRPC endpoint used only when ``mode='connect'``."""

    spawn_port: int = Field(default=9876, ge=1, le=65535)
    """Viewer port used when ``mode='spawn'``."""

    spawn_memory_limit: str = "75%"
    """Rerun viewer memory limit used for spawned viewers."""

    hide_welcome_screen: bool = True
    """Whether spawned viewers should hide the Rerun welcome screen."""


class RerunInspectorGeometryConfig(BaseConfig):
    """Metric display sizes for world-frame Rerun geometry primitives."""

    frustum_scale: float = Field(default=0.35, gt=0.0)
    """Displayed camera image-plane distance in world metres."""

    reference_axis_length: float = Field(default=0.45, gt=0.0)
    """Displayed reference-pose axis length in metres."""

    semidense_radius: float = Field(default=0.015, gt=0.0)
    """Rerun radius for semidense world points, in metres."""

    candidate_center_radius: float = Field(default=0.035, gt=0.0)
    """Rerun radius for candidate camera centers, in metres."""

    candidate_point_radius: float = Field(default=0.01, gt=0.0)
    """Rerun radius for optional candidate world points, in metres."""

    trajectory_radius: float = Field(default=0.02, gt=0.0)
    """Rerun line radius for world-frame trajectory paths, in metres."""

    mesh_alpha: int = Field(default=18, ge=0, le=255)
    """Alpha channel for the GT mesh albedo factor in ``[0, 255]``."""


class RerunInspectorPerformanceConfig(BaseConfig):
    """Bound visualization payload size with reproducible subsampling."""

    max_semidense_points: int = Field(default=50_000, ge=0)
    """Maximum semidense points to log after deterministic downsampling."""

    max_candidate_points: int = Field(default=20_000, ge=0)
    """Maximum optional candidate point-cloud points to log."""

    seed: int | None = Field(default=0, ge=0)
    """Seed used for deterministic downsampling."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Console verbosity for the inspector."""

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)


class RerunInspectorCandidateConfig(BaseConfig):
    """Filter the stored VIN oracle-candidate prefix for diagnostic display.

    Indices address the persisted ``N``-row oracle prefix shared by candidate
    poses, RRI, and optional validity data. They are not rollout full-shell ids
    and must not be confused with ``rollouts.zarr`` compact-valid indices.
    Oracle-based ranking affects visualization only.
    """

    subset_mode: Literal["all", "valid_only", "invalid_only", "top_k_oracle", "indices"] = "all"
    """Candidate subset to log as native Rerun camera entities."""

    subset_top_k: int = Field(default=5, ge=1)
    """Number of candidates used when ``subset_mode='top_k_oracle'``."""

    subset_indices: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list)
    """Explicit zero-based rows on the stored VIN candidate-prefix axis ``N``."""

    selected_strategy: Literal["top_valid_oracle", "first_valid", "explicit_index"] = "top_valid_oracle"
    """Strategy used for the single candidate that receives depth/point details."""

    selected_index: int | None = Field(default=None, ge=0)
    """Explicit stored-prefix row receiving detail layers, overriding strategy."""


class RerunInspectorRolloutPlotConfig(BaseConfig):
    """Branch-aware rollout scalar plotting policy."""

    enabled: bool = True
    """Whether rollout-Zarr inspection logs RRI and diagnostic time series."""

    branch_scope: Literal["selected", "same_source_target"] = "same_source_target"
    """Rollout rows included in scalar plots for one inspected rollout."""

    candidate_top_k: int = Field(default=5, ge=1)
    """Number of valid per-step candidate RRI ranks shown in the plot."""


class RerunInspectorRolloutDepthConfig(BaseConfig):
    """Display selected-only mesh depth retained by a rollout Zarr store.

    Depth is an oracle/evaluation artifact associated with the factual selected
    action. It can be logged as a raster or unprojected camera-local LUF points,
    but it must not be interpreted as actor-visible policy input.
    """

    enabled: bool = True
    """Log selected-action depth rasters when ``rollouts.zarr/selected_depth`` is available."""

    representation: Literal["depth_image", "point_cloud", "both"] = "depth_image"
    """Display representation for persisted selected-depth observations."""

    colormap: str = "turbo"
    """Rerun depth colormap used for selected-depth images."""

    point_fill_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    """Rerun point fill ratio for back-projected selected-depth pixels."""

    max_points: int = Field(default=20_000, ge=0)
    """Maximum unprojected selected-depth points logged for point-cloud display."""

    point_radius: float = Field(default=0.006, gt=0.0)
    """Rerun radius for camera-local unprojected points, in metres."""

    require_selected_depth: bool = False
    """Raise when selected-depth rows are missing instead of logging metadata warnings."""


class RerunInspectorEfmVoxelConfig(BaseConfig):
    """Display actor-visible EVL/EFM fields with their source provenance intact.

    Thresholded voxel centers are transformed by ``T_world_voxel`` and logged
    in world metres. Field values depend on the VIN source config and checkpoint;
    they are predictions/evidence, not GT occupancy or oracle labels.
    """

    enabled: bool = True
    """Whether to log curated EFM voxel fields when a backbone output is loaded."""

    log_occ_pr: bool = False
    """Log saturated occupancy probabilities as thresholded voxel-center points."""

    log_cent_pr: bool = True
    """Log centerness probabilities as thresholded voxel-center points."""

    log_cent_pr_nms: bool = True
    """Log NMS-filtered centerness probabilities as thresholded voxel-center points."""

    occ_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    """Minimum ``occ_pr`` value to log."""

    cent_threshold: float = Field(default=0.03, ge=0.0, le=1.0)
    """Minimum ``cent_pr`` value to log."""

    cent_nms_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    """Minimum ``cent_pr_nms`` value to log."""

    max_points_per_field: int = Field(default=10_000, ge=0)
    """Maximum logged voxel centers per EFM field after thresholding."""

    point_radius: float = Field(default=0.025, gt=0.0)
    """Rerun radius for thresholded world-frame voxel centers, in metres."""


class RerunInspectorAseKeyframeConfig(BaseConfig):
    """ASE camera keyframe visualization policy."""

    frame_policy: Literal["first_last"] = "first_last"
    """Frame policy for the curated ASE camera stream view."""


class RerunInspectorPrimitivesConfig(BaseConfig):
    """Choose actor-evidence and oracle-overlay layers for one recording.

    Semidense points, detected OBBs, and EVL voxels are actor-visible evidence.
    GT mesh/OBBs, oracle-ranked candidates, and mesh-derived depth are labeled
    diagnostic or evaluation overlays; toggling them never changes policy state.
    """

    log_semidense: bool = True
    """Log VIN semidense world points."""

    log_reference_pose: bool = True
    """Log the oracle reference pose."""

    log_candidate_frusta: bool = True
    """Log all candidate frusta."""

    log_top_oracle_frustum: bool = True
    """Log the candidate frustum with highest oracle RRI."""

    log_invalid_frusta: bool = True
    """Log invalid candidate frusta when validity masks are available."""

    log_candidate_centers: bool = True
    """Log candidate camera centers."""

    log_metadata: bool = True
    """Log sample metadata as a Rerun text document."""

    log_candidate_points: bool = False
    """Log candidate point clouds only when the inventory and sample expose them."""

    log_gt_mesh: bool = True
    """Log compact or live-attached GT mesh when available."""

    log_gt_obbs: bool = True
    """Log compact or live-attached GT OBBs when available."""

    log_detected_obbs: bool = True
    """Log compact detected OBBs when available."""

    show_gt_obb_labels: bool = True
    """Show GT OBB labels directly in 3D; labels are always logged as metadata."""

    show_detected_obb_labels: bool = False
    """Show detected EFM OBB labels directly in 3D; labels are always logged as metadata."""

    log_gt_trajectory: bool = True
    """Log the snippet rig trajectory when available."""

    log_candidate_depths: bool = False
    """Log candidate depth diagnostics when available."""

    log_rgb_keyframes: bool = False
    """Log live-attached RGB keyframes when a raw EFM snippet is attached."""

    log_depth_keyframes: bool = False
    """Log live-attached depth keyframes when a raw EFM snippet is attached."""

    log_efm_voxels: bool = True
    """Log curated EFM voxel evidence when available."""


class RerunOfflineInspectorConfig(TargetConfig[Any]):
    """Compose source selection, recording lifecycle, and visualization policy.

    The factory creates a one-run inspector: select immutable input, validate
    visual inventory, initialize one Rerun sink, log configured entities, and
    emit provenance metadata. It owns no dataset or rollout-store mutation.
    """

    @property
    def target_type(self) -> type[Any]:
        """Return the inspector runtime factory target."""

        from ._cli import RerunOfflineInspector

        return RerunOfflineInspector

    dataset: RerunInspectorDatasetConfig = Field(default_factory=RerunInspectorDatasetConfig)
    """Dataset reader settings."""

    selection: RerunInspectorSelectionConfig = Field(default_factory=RerunInspectorSelectionConfig)
    """Sample selection settings."""

    output: RerunInspectorOutputConfig = Field(default_factory=RerunInspectorOutputConfig)
    """Rerun output settings."""

    geometry: RerunInspectorGeometryConfig = Field(default_factory=RerunInspectorGeometryConfig)
    """Geometry primitive settings."""

    performance: RerunInspectorPerformanceConfig = Field(default_factory=RerunInspectorPerformanceConfig)
    """Runtime performance settings."""

    candidate: RerunInspectorCandidateConfig = Field(default_factory=RerunInspectorCandidateConfig)
    """Candidate subset and selected-detail logging policy."""

    rollout_plots: RerunInspectorRolloutPlotConfig = Field(default_factory=RerunInspectorRolloutPlotConfig)
    """Rollout branch/RRI scalar plotting policy."""

    rollout_depths: RerunInspectorRolloutDepthConfig = Field(default_factory=RerunInspectorRolloutDepthConfig)
    """Selected-depth visualization policy for rollout-Zarr inspection."""

    efm_voxels: RerunInspectorEfmVoxelConfig = Field(default_factory=RerunInspectorEfmVoxelConfig)
    """EFM voxel-field visualization settings."""

    ase_keyframes: RerunInspectorAseKeyframeConfig = Field(default_factory=RerunInspectorAseKeyframeConfig)
    """ASE camera keyframe visualization settings."""

    primitives: RerunInspectorPrimitivesConfig = Field(default_factory=RerunInspectorPrimitivesConfig)
    """Primitive toggles."""


__all__ = [
    "RerunInspectorDatasetConfig",
    "RerunInspectorGeometryConfig",
    "RerunInspectorAseKeyframeConfig",
    "RerunInspectorCandidateConfig",
    "RerunInspectorEfmVoxelConfig",
    "RerunInspectorOutputConfig",
    "RerunInspectorPerformanceConfig",
    "RerunInspectorPrimitivesConfig",
    "RerunInspectorRolloutDepthConfig",
    "RerunInspectorRolloutPlotConfig",
    "RerunInspectorSelectionConfig",
    "RerunOfflineInspectorConfig",
]
