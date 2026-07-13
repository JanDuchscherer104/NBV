"""Rerun logging for standalone rollout Zarr replay stores."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from aria_nbv.data_handling.identifiers import (
    compact_ase_atek_identifiers,
    compact_ase_atek_sample_id,
    raw_ase_atek_sample_id,
)
from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.trace import INVALID_REASON_CODES
from aria_nbv.rollouts.zarr_store import validate_rollout_zarr_store

from ._blueprint import log_default_inspector_blueprint
from ._colors import INVALID_RGBA, step_to_rgba
from ._loggers import (
    RerunOfflineLogger,
    _compact_or_live_gt_obbs,
    _gt_obb_semantic_names,
    _obb_boxes,
    _snippet_t_world_snippet,
)
from ._metadata import collect_visual_inventory, validate_required_inventory
from ._sample import select_rerun_sample
from ._session import RerunModule, log_world_coordinates, start_rerun_recording

if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray

    from ._config import (
        RerunInspectorRolloutDepthConfig,
        RerunInspectorSelectionConfig,
        RerunOfflineInspectorConfig,
    )

ENTITY_ROLLOUT_ROOT = "world/rollout"
ENTITY_ROLLOUT_METADATA = "metadata/rollout_zarr"
ENTITY_ROLLOUT_RRI_ROOT = "plots/rollout/rri"
ENTITY_ROLLOUT_DIAGNOSTICS_ROOT = "plots/rollout/diagnostics"
ENTITY_ROLLOUT_VALID_COUNT = f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/selected/valid_candidates"
ENTITY_ROLLOUT_SELECTED_PROBABILITY = f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/selected/selected_probability"
ENTITY_ROLLOUT_SELECTED_TARGET_RRI = f"{ENTITY_ROLLOUT_RRI_ROOT}/selected/selected_target_rri"
ENTITY_ROLLOUT_SELECTED_TARGET_ROOT_GAIN = f"{ENTITY_ROLLOUT_RRI_ROOT}/selected/selected_target_root_gain"
ENTITY_ROLLOUT_INVALID_FRACTION = f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/selected/invalid_fraction"
ENTITY_ROLLOUT_SELECTED_POSITION_ID = f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/selected/selected_position_id"

ROLLOUT_STEP_TIMELINE = "rollout_step"

_PLOT_PALETTE = (
    (56, 189, 248, 255),
    (251, 191, 36, 255),
    (168, 85, 247, 255),
    (34, 197, 94, 255),
    (244, 114, 182, 255),
    (249, 115, 22, 255),
)

_POSITION_NAMES = {
    0: "upper_bound_free_shell",
    1: "forward_local",
    2: "target_bearing_local",
    3: "lateral_target_bypass",
    4: "local_refinement",
    5: "revisit_backtrack",
}
_INVALID_REASON_NAMES = {code: name for name, code in INVALID_REASON_CODES.items()}
_TARGET_RRI_RANK_SEMANTICS = "valid_finite_target_rri_desc"


@dataclass(frozen=True, slots=True)
class SelectedRolloutRows:
    """Resolved row ids for one rollout chain in a standalone replay store."""

    rollout_row_id: int
    rollout_index: int
    chain_id: int
    step_rows: NDArray[np.int64]


class RerunRolloutZarrLogger:
    """Log one multistep rollout chain from ``rollouts.zarr`` to Rerun."""

    def __init__(self, config: RerunOfflineInspectorConfig, *, rr_module: RerunModule | None = None) -> None:
        """Create a rollout-store logger."""

        self.config = config
        if rr_module is None:
            import rerun as imported_rr

            self.rr = cast("RerunModule", imported_rr)
        else:
            self.rr = rr_module
        self._context_warnings: list[str] = []

    def start(self) -> None:
        """Initialize the Rerun recording and configured output sink."""

        start_rerun_recording(self.rr, self.config.output)
        log_world_coordinates(self.rr)

    def log_store(
        self,
        *,
        store_dir: Path | str,
        rollout_index: int = 0,
        rollout_row_id: int | None = None,
    ) -> SelectedRolloutRows:
        """Log one rollout chain from a validated rollout Zarr store."""

        reader = RolloutZarrStoreReader(store_dir)
        validation = validate_rollout_zarr_store(store_dir)
        rows = _resolve_rollout_rows(reader, rollout_index=rollout_index, rollout_row_id=rollout_row_id)
        target = _rollout_target_payload(reader, rows=rows)
        self._context_warnings.extend(target.warnings)
        self._log_rollout_blueprint(reader=reader, rows=rows)
        self._log_static_context(reader=reader, rows=rows, target=target)
        self._log_rollout_target(target)
        self._log_static_metadata(reader=reader, rows=rows, validation_errors=validation.errors, target=target)
        self._log_rollout_plots(reader=reader, selected_rows=rows)

        selected_path: list[list[float]] = _rollout_root_path(reader, rows=rows)
        for order, step_row_position in enumerate(rows.step_rows.tolist()):
            self._set_rollout_step_time(order)
            step = _step_payload(
                reader,
                step_row_position=step_row_position,
                rollout_row_id=rows.rollout_row_id,
                chain_id=rows.chain_id,
                rollout_depths=self.config.rollout_depths,
                target_metadata=target.metadata,
            )
            self._log_step(step)
            if step.selected_center is not None:
                selected_path.append(step.selected_center.tolist())
            self._log_selected_path(rows=rows, selected_path=selected_path)
        return rows

    def _log_rollout_blueprint(self, *, reader: RolloutZarrStoreReader, rows: SelectedRolloutRows) -> None:
        """Send rollout-specific visibility defaults for the selected chain."""

        log_default_inspector_blueprint(
            self.rr,
            hidden_world_paths=_rollout_candidate_group_hidden_paths(reader=reader, rows=rows),
        )

    def _log_static_context(
        self,
        *,
        reader: RolloutZarrStoreReader,
        rows: SelectedRolloutRows,
        target: "_RolloutTargetPayload",
    ) -> None:
        """Log matching VIN offline sample context before rollout-step layers."""

        mode = self.config.selection.rollout_context_mode
        if mode == "off":
            self._context_warnings.append("VIN context logging disabled by selection.rollout_context_mode='off'.")
            return
        selection = _rollout_context_selection(reader, rows=rows, fallback=self.config.selection)
        if selection is None:
            message = "No rollout scene/snippet or explicit sample selector available for VIN context logging."
            if mode == "required":
                raise LookupError(message)
            self._context_warnings.append(message)
            return
        try:
            selected = select_rerun_sample(dataset_config=self.config.dataset.offline, selection=selection)
            inventory = collect_visual_inventory(selected.sample)
            validate_required_inventory(self.config, inventory)
            logger = RerunOfflineLogger(
                self.config,
                rr_module=self.rr,
                target_obb_hint=_rollout_target_hint(reader, rows=rows),
            )
            logger.log_sample(sample=selected.sample, inventory=inventory, selection=selected.description)
            logger.log_metadata(sample=selected.sample, inventory=inventory, selection=selected.description)
            self._log_matched_gt_target_obb(sample=selected.sample, target=target)
        except Exception as exc:
            if mode == "required":
                raise
            self._context_warnings.append(f"VIN context logging skipped: {exc}")

    def _log_matched_gt_target_obb(self, *, sample: Any, target: "_RolloutTargetPayload") -> None:
        """Log the matched GT OBB overlay when VIN context exposes GT OBBs."""

        matched_gt_id = str(target.metadata.get("matched_gt_target_id") or "")
        if not matched_gt_id:
            return
        try:
            t_world_snippet = _snippet_t_world_snippet(sample)
            obbs = _compact_or_live_gt_obbs(sample)
        except AttributeError:
            return
        if t_world_snippet is None or obbs is None:
            return
        centers, half_sizes, quaternions, labels, sem_ids, inst_ids = _obb_boxes(
            obbs,
            t_world_snippet=t_world_snippet,
            sem_id_to_name=_gt_obb_semantic_names(sample),
        )
        if centers.shape[0] == 0:
            return
        sem_id = _structured_target_value(matched_gt_id, key="sem")
        inst_id = _structured_target_value(matched_gt_id, key="inst")
        mask = np.ones((centers.shape[0],), dtype=np.bool_)
        if sem_id is not None:
            mask &= sem_ids.astype(int) == int(sem_id)
        if inst_id is not None:
            mask &= inst_ids.astype(int) == int(inst_id)
        matches = np.nonzero(mask)[0]
        if matches.size == 0:
            return
        index = int(matches[0])
        self.rr.log(
            f"{target.entity_root}/matched_gt_obb",
            self.rr.Boxes3D(
                centers=centers[index : index + 1],
                half_sizes=half_sizes[index : index + 1],
                quaternions=quaternions[index : index + 1],
                colors=[[34, 197, 94, 235]],
                labels=[labels[index]],
            ),
            self.rr.AnyValues(
                matched_gt_target_id=compact_ase_atek_sample_id(matched_gt_id),
                matched_gt_target_row_id=int(target.metadata.get("matched_gt_target_row_id", -1)),
                matched_gt_sem_id=int(sem_ids[index]),
                matched_gt_inst_id=int(inst_ids[index]),
                matched_gt_label=labels[index],
            ),
            static=True,
        )

    def _log_static_metadata(
        self,
        *,
        reader: RolloutZarrStoreReader,
        rows: SelectedRolloutRows,
        validation_errors: list[str],
        target: "_RolloutTargetPayload",
    ) -> None:
        attrs = dict(reader.root.attrs)
        manifest_bundle = reader.manifest()
        document = {
            "store_dir": str(reader.store_dir),
            "root_attrs": attrs,
            "manifest": manifest_bundle["manifest"],
            "selected": {
                "rollout_row_id": rows.rollout_row_id,
                "rollout_index": rows.rollout_index,
                "chain_id": rows.chain_id,
                "step_rows": rows.step_rows.astype(int).tolist(),
            },
            "validation": {"ok": not validation_errors, "errors": validation_errors},
            "target": target.metadata,
            "context": {
                "mode": self.config.selection.rollout_context_mode,
                "warnings": list(self._context_warnings),
            },
            "dictionaries": _dictionary_preview(reader),
        }
        self.rr.log(
            ENTITY_ROLLOUT_METADATA,
            self.rr.TextDocument(
                json.dumps(compact_ase_atek_identifiers(document), indent=2, sort_keys=True),
                media_type="application/json",
            ),
            static=True,
        )

    def _log_rollout_target(self, target: "_RolloutTargetPayload") -> None:
        """Log a visible target overlay scoped to the selected rollout chain."""

        if target.center is not None and np.isfinite(target.center).all():
            self.rr.log(
                f"{target.entity_root}/center",
                self.rr.Points3D(
                    target.center.reshape(1, 3),
                    radii=self.config.geometry.candidate_center_radius * 1.5,
                    colors=[[255, 214, 10, 255]],
                ),
                static=True,
            )
        if (
            target.center is not None
            and target.extents is not None
            and target.pose_world_object is not None
            and np.isfinite(target.center).all()
            and np.isfinite(target.extents).all()
            and np.isfinite(target.pose_world_object).all()
        ):
            self.rr.log(
                f"{target.entity_root}/actor_visible_obb",
                self.rr.Boxes3D(
                    centers=target.center.reshape(1, 3),
                    half_sizes=(0.5 * target.extents).reshape(1, 3),
                    quaternions=_matrix3x3_to_quat_xyzw(target.pose_world_object[:9].reshape(3, 3)).reshape(1, 4),
                    colors=[[255, 214, 10, 225]],
                    labels=[compact_ase_atek_sample_id(str(target.metadata.get("target_id", "rollout_target")))],
                ),
                self.rr.AnyValues(**compact_ase_atek_identifiers(target.metadata)),
                static=True,
            )
        self.rr.log(
            f"{target.entity_root}/metadata",
            self.rr.TextDocument(
                json.dumps(compact_ase_atek_identifiers(target.metadata), indent=2, sort_keys=True),
                media_type="application/json",
            ),
            static=True,
        )

    def _log_step(self, step: "_RolloutStepPayload") -> None:
        for candidate in step.candidates:
            self._log_candidate_camera(candidate)
            self._log_selected_depth_representation(candidate)
            self._log_candidate_center(candidate)
        self._log_candidate_group_centers(step)
        self.rr.log(ENTITY_ROLLOUT_VALID_COUNT, self.rr.Scalars(float(step.valid_candidate_count)))
        self.rr.log(ENTITY_ROLLOUT_SELECTED_PROBABILITY, self.rr.Scalars(_finite_or_zero(step.selected_probability)))
        self.rr.log(ENTITY_ROLLOUT_SELECTED_TARGET_RRI, self.rr.Scalars(_finite_or_zero(step.selected_target_rri)))
        self.rr.log(
            ENTITY_ROLLOUT_SELECTED_TARGET_ROOT_GAIN,
            self.rr.Scalars(_finite_or_zero(step.selected_target_root_gain)),
        )
        self.rr.log(ENTITY_ROLLOUT_INVALID_FRACTION, self.rr.Scalars(_finite_or_zero(step.invalid_fraction)))
        self.rr.log(ENTITY_ROLLOUT_SELECTED_POSITION_ID, self.rr.Scalars(float(step.selected_position_id)))
        self.rr.log(
            step.metadata_entity,
            self.rr.TextDocument(
                json.dumps(compact_ase_atek_identifiers(step.metadata), indent=2, sort_keys=True),
                media_type="application/json",
            ),
        )

    def _log_rollout_plots(self, *, reader: RolloutZarrStoreReader, selected_rows: SelectedRolloutRows) -> None:
        if not self.config.rollout_plots.enabled:
            return
        plot_rows = _resolve_plot_rollout_rows(
            reader,
            selected_rows=selected_rows,
            branch_scope=self.config.rollout_plots.branch_scope,
        )
        for branch_order, rows in enumerate(plot_rows):
            branch = _branch_plot_descriptor(reader, rows=rows, selected_row_id=selected_rows.rollout_row_id)
            self._log_branch_series_descriptors(branch=branch, branch_order=branch_order)
            for order, step_row_position in enumerate(rows.step_rows.tolist()):
                self._set_rollout_step_time(order)
                step = _plot_step_payload(
                    reader,
                    step_row_position=step_row_position,
                    candidate_top_k=self.config.rollout_plots.candidate_top_k,
                )
                self._log_branch_plot_step(branch=branch, step=step)

    def _log_branch_series_descriptors(self, *, branch: "_RolloutBranchPlot", branch_order: int) -> None:
        color = _plot_color(branch_order=branch_order, selected=branch.selected)
        muted = color.copy()
        muted[3] = min(muted[3], 160)
        series = {
            f"{branch.rri_root}/cumulative_target_rri": ("cumulative target RRI", color),
            f"{branch.rri_root}/selected_target_rri": ("selected target RRI", color),
            f"{branch.rri_root}/candidate_fanout_min": ("candidate RRI min", muted),
            f"{branch.rri_root}/candidate_fanout_mean": ("candidate RRI mean", muted),
            f"{branch.rri_root}/candidate_fanout_max": ("candidate RRI max", muted),
            f"{branch.diagnostics_root}/selected_probability": ("selected probability", color),
            f"{branch.diagnostics_root}/valid_candidates": ("valid candidates", color),
            f"{branch.diagnostics_root}/selected_entropy": ("selected entropy", muted),
            f"{branch.diagnostics_root}/selected_scene_rri": ("selected scene RRI", muted),
        }
        for rank in range(self.config.rollout_plots.candidate_top_k):
            alpha = max(90, 210 - 25 * rank)
            top_color = color.copy()
            top_color[3] = alpha
            series[f"{branch.rri_root}/candidate_top_{rank + 1:02d}"] = (f"candidate top-{rank + 1} RRI", top_color)
        for path, (label, line_color) in series.items():
            self.rr.log(
                path,
                self.rr.SeriesLines(colors=[line_color], names=[f"{branch.label} | {label}"]),
                self.rr.SeriesPoints(colors=[line_color], names=[f"{branch.label} | {label}"], marker_sizes=[5.0]),
                static=True,
            )

    def _log_branch_plot_step(self, *, branch: "_RolloutBranchPlot", step: "_RolloutPlotStep") -> None:
        self._log_scalar(f"{branch.rri_root}/cumulative_target_rri", step.cumulative_target_rri)
        self._log_scalar(f"{branch.rri_root}/selected_target_rri", step.selected_target_rri)
        self._log_scalar(f"{branch.rri_root}/candidate_fanout_min", step.candidate_min_target_rri)
        self._log_scalar(f"{branch.rri_root}/candidate_fanout_mean", step.candidate_mean_target_rri)
        self._log_scalar(f"{branch.rri_root}/candidate_fanout_max", step.candidate_max_target_rri)
        for rank, value in enumerate(step.top_candidate_target_rri, start=1):
            self._log_scalar(f"{branch.rri_root}/candidate_top_{rank:02d}", value)
        self._log_scalar(f"{branch.diagnostics_root}/selected_probability", step.selected_probability)
        self._log_scalar(f"{branch.diagnostics_root}/valid_candidates", float(step.valid_candidate_count))
        self._log_scalar(f"{branch.diagnostics_root}/selected_entropy", step.selected_entropy)
        self._log_scalar(f"{branch.diagnostics_root}/selected_scene_rri", step.selected_scene_rri)

    def _set_rollout_step_time(self, order: int) -> None:
        set_time = getattr(self.rr, "set_time", None)
        if callable(set_time):
            set_time(ROLLOUT_STEP_TIMELINE, sequence=int(order))
            return
        self.rr.set_time_sequence(ROLLOUT_STEP_TIMELINE, int(order))

    def _log_scalar(self, entity_path: str, value: float) -> None:
        if not np.isfinite(value):
            return
        self.rr.log(entity_path, self.rr.Scalars(float(value)))

    def _log_candidate_camera(self, candidate: "_RolloutCandidatePayload") -> None:
        rotation = candidate.pose[:9].reshape(3, 3)
        translation = candidate.pose[9:12]
        if candidate.selected_depth is None:
            pinhole = self.rr.Pinhole(
                fov_y=float(np.pi / 2.0),
                aspect_ratio=1.0,
                camera_xyz=self.rr.ViewCoordinates.LUF,
                image_plane_distance=self.config.geometry.frustum_scale,
            )
        else:
            height, width = candidate.selected_depth.image_size_hw
            pinhole = self.rr.Pinhole(
                resolution=[float(width), float(height)],
                focal_length=candidate.selected_depth.focal_px.astype(float).tolist(),
                principal_point=candidate.selected_depth.principal_point_px.astype(float).tolist(),
                camera_xyz=self.rr.ViewCoordinates.LUF,
                image_plane_distance=self.config.geometry.frustum_scale,
            )
        self.rr.log(
            candidate.camera_entity,
            self.rr.Transform3D(
                translation=translation.astype(float).tolist(),
                mat3x3=rotation.astype(float).tolist(),
                relation=self.rr.TransformRelation.ParentFromChild,
            ),
            pinhole,
            self.rr.AnyValues(
                candidate_row_id=candidate.row_id,
                step_row_id=candidate.step_row_id,
                compact_valid_index=candidate.compact_valid_index,
                mixture_component_name=candidate.mixture_component_name,
                position_mode_name=candidate.position_mode_name,
                sampler_probability=candidate.sampler_probability,
                position_id=candidate.position_id,
                target_rri=candidate.target_rri,
                target_root_gain=candidate.target_root_gain,
                target_rri_rank=candidate.target_rri_rank,
                target_rri_rank_total=candidate.target_rri_rank_total,
                selection_probability=candidate.probability,
                mesh_distance_m=candidate.mesh_distance_m,
                path_min_clearance_m=candidate.path_min_clearance_m,
                motion_step_length_m=candidate.motion_step_length_m,
                target_distance_m=candidate.target_distance_m,
                primary_invalid_reason_name=candidate.primary_invalid_reason_name,
            ),
        )

    def _log_candidate_group_centers(self, step: "_RolloutStepPayload") -> None:
        """Log low-cardinality candidate center groups for fast Rerun filtering."""

        group_specs = (
            ("position_family", "position_mode_name"),
            ("invalid_reason", "primary_invalid_reason_name"),
        )
        for group_name, attr_name in group_specs:
            grouped: dict[str, list[_RolloutCandidatePayload]] = {}
            for candidate in step.candidates:
                grouped.setdefault(str(getattr(candidate, attr_name)), []).append(candidate)
            for value, candidates in grouped.items():
                points = np.stack([candidate.center for candidate in candidates], axis=0).astype(np.float32)
                colors = [candidate.color for candidate in candidates]
                selected_count = sum(1 for candidate in candidates if candidate.selected)
                valid_count = sum(1 for candidate in candidates if candidate.primary_invalid_reason_name == "VALID")
                self.rr.log(
                    f"{step.step_entity}/groups/{group_name}/{_safe_entity_token(value)}",
                    self.rr.Points3D(
                        points,
                        radii=self.config.geometry.candidate_center_radius * 0.85,
                        colors=colors,
                    ),
                    self.rr.AnyValues(
                        group_name=group_name,
                        group_value=value,
                        candidate_count=len(candidates),
                        valid_count=valid_count,
                        selected_count=selected_count,
                    ),
                )

    def _log_selected_depth_representation(self, candidate: "_RolloutCandidatePayload") -> None:
        if candidate.selected_depth is None:
            return
        representation = self.config.rollout_depths.representation
        if representation in ("depth_image", "both"):
            self.rr.log(
                f"{candidate.camera_entity}/depth",
                self.rr.DepthImage(
                    candidate.selected_depth.depth_m,
                    meter=1.0,
                    colormap=self.config.rollout_depths.colormap,
                    point_fill_ratio=self.config.rollout_depths.point_fill_ratio,
                ),
            )
        if representation in ("point_cloud", "both"):
            points = _selected_depth_points_camera(
                candidate.selected_depth,
                max_points=self.config.rollout_depths.max_points,
            )
            if points.shape[0] == 0:
                return
            self.rr.log(
                f"{candidate.camera_entity}/points",
                self.rr.Points3D(
                    points,
                    radii=self.config.rollout_depths.point_radius,
                    colors=[candidate.color],
                ),
            )

    def _log_candidate_center(self, candidate: "_RolloutCandidatePayload") -> None:
        self.rr.log(
            candidate.center_entity,
            self.rr.Points3D(
                candidate.center.reshape(1, 3),
                radii=self.config.geometry.candidate_center_radius,
                colors=[candidate.color],
            ),
        )

    def _log_selected_path(self, *, rows: SelectedRolloutRows, selected_path: list[list[float]]) -> None:
        strips = [[selected_path[index], selected_path[index + 1]] for index in range(max(len(selected_path) - 1, 0))]
        colors = step_to_rgba(np.arange(len(strips), dtype=np.int64), alpha=245).astype(int).tolist()
        self.rr.log(
            _rollout_selected_path_entity(rollout_row_id=rows.rollout_row_id, chain_id=rows.chain_id),
            self.rr.LineStrips3D(
                strips,
                colors=colors,
                radii=self.config.geometry.trajectory_radius,
            ),
        )


@dataclass(frozen=True, slots=True)
class _RolloutCandidatePayload:
    row_id: int
    step_row_id: int
    compact_valid_index: int
    selected: bool
    pose: NDArray[np.float32]
    center: NDArray[np.float32]
    position_id: int
    target_rri: float
    target_root_gain: float
    target_rri_rank: int
    target_rri_rank_total: int
    probability: float
    mixture_component_name: str
    position_mode_name: str
    sampler_probability: float
    mesh_distance_m: float
    path_min_clearance_m: float
    motion_step_length_m: float
    target_distance_m: float
    primary_invalid_reason_name: str
    color: list[int]
    camera_entity: str
    center_entity: str
    selected_depth: "_SelectedDepthPayload | None" = None


@dataclass(frozen=True, slots=True)
class _SelectedDepthPayload:
    step_row_id: int
    candidate_row_id: int
    depth_m: NDArray[np.float32]
    valid_mask: NDArray[np.bool_]
    focal_px: NDArray[np.float32]
    principal_point_px: NDArray[np.float32]
    image_size_hw: tuple[int, int]


@dataclass(frozen=True, slots=True)
class _RolloutStepPayload:
    rollout_row_id: int
    chain_id: int
    step_row_id: int
    step_index: int
    step_entity: str
    metadata_entity: str
    candidates: list[_RolloutCandidatePayload]
    selected_center: NDArray[np.float32] | None
    valid_candidate_count: int
    selected_probability: float
    selected_target_rri: float
    selected_target_root_gain: float
    selected_position_id: int
    invalid_fraction: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _RolloutTargetPayload:
    entity_root: str
    metadata: dict[str, Any]
    warnings: list[str]
    center: NDArray[np.float32] | None
    extents: NDArray[np.float32] | None
    pose_world_object: NDArray[np.float32] | None


@dataclass(frozen=True, slots=True)
class _CandidateRriSummary:
    selected_target_rri: float
    selected_scene_rri: float
    selected_probability: float
    selected_entropy: float
    valid_candidate_count: int
    candidate_min_target_rri: float
    candidate_mean_target_rri: float
    candidate_max_target_rri: float
    top_candidate_target_rri: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _RolloutPlotStep:
    step_row_id: int
    cumulative_target_rri: float
    selected_target_rri: float
    selected_scene_rri: float
    selected_probability: float
    selected_entropy: float
    valid_candidate_count: int
    candidate_min_target_rri: float
    candidate_mean_target_rri: float
    candidate_max_target_rri: float
    top_candidate_target_rri: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _RolloutBranchPlot:
    rollout_row_id: int
    rollout_index: int
    selected: bool
    label: str
    rri_root: str
    diagnostics_root: str


def _resolve_rollout_rows(
    reader: RolloutZarrStoreReader,
    *,
    rollout_index: int,
    rollout_row_id: int | None,
) -> SelectedRolloutRows:
    rollout_ids = reader.array("rollouts/rollout_row_id").astype(np.int64).reshape(-1)
    if rollout_row_id is None:
        if int(rollout_index) < 0 or int(rollout_index) >= int(rollout_ids.shape[0]):
            raise IndexError(f"rollout_index {rollout_index} is outside [0, {rollout_ids.shape[0]}).")
        resolved_row_id = int(rollout_ids[int(rollout_index)])
        resolved_index = int(rollout_index)
    else:
        matches = np.nonzero(rollout_ids == int(rollout_row_id))[0]
        if matches.size != 1:
            raise KeyError(f"rollout_row_id {rollout_row_id} is not present in rollouts/rollout_row_id.")
        resolved_row_id = int(rollout_row_id)
        resolved_index = int(matches[0])

    step_rollout_ids = reader.array("steps/rollout_row_id").astype(np.int64).reshape(-1)
    step_indices = reader.array("steps/step_index").astype(np.int64).reshape(-1)
    step_rows = np.nonzero(step_rollout_ids == resolved_row_id)[0].astype(np.int64)
    if step_rows.size == 0:
        raise ValueError(f"Rollout row {resolved_row_id} has no step rows.")
    order = np.argsort(step_indices[step_rows], kind="stable")
    return SelectedRolloutRows(
        rollout_row_id=resolved_row_id,
        rollout_index=resolved_index,
        chain_id=int(reader.array("rollouts/chain_id")[resolved_index]),
        step_rows=step_rows[order],
    )


def _resolve_plot_rollout_rows(
    reader: RolloutZarrStoreReader,
    *,
    selected_rows: SelectedRolloutRows,
    branch_scope: str,
) -> list[SelectedRolloutRows]:
    """Return rollout rows included in branch-aware scalar plots."""

    if branch_scope == "selected":
        return [selected_rows]
    if branch_scope != "same_source_target":
        raise ValueError(f"Unsupported rollout plot branch_scope={branch_scope!r}.")

    rollout_ids = reader.array("rollouts/rollout_row_id").astype(np.int64).reshape(-1)
    source_ids = reader.array("rollouts/source_row_id").astype(np.int64).reshape(-1)
    target_ids = reader.array("rollouts/target_row_id").astype(np.int64).reshape(-1)
    selected_source = int(source_ids[selected_rows.rollout_index])
    selected_target = int(target_ids[selected_rows.rollout_index])
    positions = np.nonzero((source_ids == selected_source) & (target_ids == selected_target))[0]
    if positions.size == 0:
        return [selected_rows]
    rows = [
        _resolve_rollout_rows(reader, rollout_index=int(position), rollout_row_id=int(rollout_ids[int(position)]))
        for position in positions.tolist()
    ]
    rows.sort(key=lambda value: (value.rollout_row_id != selected_rows.rollout_row_id, value.rollout_row_id))
    return rows


def _branch_plot_descriptor(
    reader: RolloutZarrStoreReader,
    *,
    rows: SelectedRolloutRows,
    selected_row_id: int,
) -> _RolloutBranchPlot:
    policy = _rollout_dictionary_value(reader, group="policy", array_path="rollouts/policy_id", row=rows.rollout_index)
    selected = rows.rollout_row_id == selected_row_id
    suffix = (
        f"{_safe_entity_token(policy or 'unknown_policy')}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}"
    )
    label = f"{policy or 'unknown'} chain={rows.chain_id} row={rows.rollout_row_id}"
    if selected:
        label = f"selected | {label}"
    return _RolloutBranchPlot(
        rollout_row_id=rows.rollout_row_id,
        rollout_index=rows.rollout_index,
        selected=selected,
        label=label,
        rri_root=f"{ENTITY_ROLLOUT_RRI_ROOT}/{suffix}",
        diagnostics_root=f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/{suffix}",
    )


def _step_payload(
    reader: RolloutZarrStoreReader,
    *,
    step_row_position: int,
    rollout_row_id: int,
    chain_id: int,
    rollout_depths: "RerunInspectorRolloutDepthConfig",
    target_metadata: dict[str, Any] | None = None,
) -> _RolloutStepPayload:
    step_row_id = int(reader.array("steps/step_row_id")[step_row_position])
    step_index = int(reader.array("steps/step_index")[step_row_position])
    selected_candidate_row_id = int(reader.array("steps/selected_candidate_row_id")[step_row_position])
    candidate_step_ids = reader.array("candidates/step_row_id").astype(np.int64).reshape(-1)
    row_positions = np.nonzero(candidate_step_ids == step_row_id)[0].astype(np.int64)
    shell_indices = reader.array("candidates/shell_index")[row_positions].astype(np.int64)
    order = np.argsort(shell_indices, kind="stable")
    row_positions = row_positions[order]

    valid = reader.array("candidates/actor_action_mask")[row_positions].astype(bool)
    selected = reader.array("candidates/selected_mask")[row_positions].astype(bool)
    poses = reader.array("candidates/pose_world_cam")[row_positions].astype(np.float32).reshape(-1, 12)
    centers = _pose_centers(poses)
    target_rri = reader.array("candidates/target_rri")[row_positions].astype(np.float32).reshape(-1)
    target_root_gain = _optional_rows(
        reader,
        "candidates/target_root_gain",
        row_positions=row_positions,
        dtype=np.float32,
        default=np.nan,
    )
    target_rri_ranks, target_rri_rank_total = _target_rri_ranks(
        target_rri=target_rri,
        valid_mask=valid,
        shell_indices=shell_indices,
    )
    probabilities = reader.array("candidates/selection_probabilities")[row_positions].astype(np.float32).reshape(-1)
    log_probabilities = (
        reader.array("candidates/selection_log_probabilities")[row_positions].astype(np.float32).reshape(-1)
    )
    entropy = _selection_entropy(probabilities=probabilities, log_probabilities=log_probabilities, valid_mask=valid)
    reason_bitsets = reader.array("candidates/invalid_reason_bitset")[row_positions].astype(np.uint32).reshape(-1)
    primary_reasons = reader.array("candidates/primary_invalid_reason")[row_positions].astype(np.uint16).reshape(-1)
    compact_valid = reader.array("candidates/compact_valid_index")[row_positions].astype(np.int64).reshape(-1)
    candidate_row_ids = reader.array("candidates/candidate_row_id")[row_positions].astype(np.int64).reshape(-1)
    mixture_ids = reader.array("candidates/mixture_id")[row_positions].astype(np.int32).reshape(-1)
    sampler_probabilities = reader.array("candidates/sampler_probability")[row_positions].astype(np.float32).reshape(-1)
    diagnostics = _candidate_diagnostics_for_rows(reader, row_positions=row_positions)

    selected_local = int(np.nonzero(selected)[0][0]) if selected.any() else -1
    selected_depth, selected_depth_warnings = _selected_depth_payload(
        reader,
        step_row_id=step_row_id,
        selected_candidate_row_id=selected_candidate_row_id,
        config=rollout_depths,
    )
    candidate_payloads = _candidate_payloads(
        candidate_row_ids=candidate_row_ids,
        rollout_row_id=rollout_row_id,
        chain_id=chain_id,
        step_row_id=step_row_id,
        shell_indices=shell_indices,
        compact_valid=compact_valid,
        valid=valid,
        selected=selected,
        step_index=step_index,
        poses=poses,
        centers=centers,
        target_rri=target_rri,
        target_root_gain=target_root_gain,
        target_rri_ranks=target_rri_ranks,
        target_rri_rank_total=target_rri_rank_total,
        probabilities=probabilities,
        mixture_ids=mixture_ids,
        sampler_probabilities=sampler_probabilities,
        position_ids=diagnostics["position_id"],
        mesh_distance_m=diagnostics["mesh_distance_m"],
        path_min_clearance_m=diagnostics["path_min_clearance_m"],
        motion_step_length_m=diagnostics["motion_step_length_m"],
        target_distance_m=diagnostics["target_distance_m"],
        reason_bitsets=reason_bitsets,
        primary_reasons=primary_reasons,
        selected_depth=selected_depth,
        component_name_by_id=_component_names(reader),
    )
    metadata = {
        "rollout_row_id": rollout_row_id,
        "chain_id": chain_id,
        "step_row_id": step_row_id,
        "step_index": step_index,
        "selected_candidate_row_id": selected_candidate_row_id,
        "num_candidates": int(row_positions.shape[0]),
        "num_valid_candidates": int(valid.sum()),
        "selected_local_index": selected_local,
        "selected_shell_index": int(shell_indices[selected_local]) if selected_local >= 0 else None,
        "selected_probability": float(probabilities[selected_local]) if selected_local >= 0 else None,
        "selected_target_rri": float(target_rri[selected_local]) if selected_local >= 0 else None,
        "selected_target_root_gain": float(target_root_gain[selected_local]) if selected_local >= 0 else None,
        "selected_position_id": int(diagnostics["position_id"][selected_local]) if selected_local >= 0 else -1,
        "selected_position_family": _position_name(int(diagnostics["position_id"][selected_local]))
        if selected_local >= 0
        else "unknown",
        "selection_entropy": float(entropy) if selected_local >= 0 else None,
        "target_rri_rank": int(target_rri_ranks[selected_local]) if selected_local >= 0 else -1,
        "target_rri_rank_total": int(target_rri_rank_total),
        "target_rri_rank_semantics": _TARGET_RRI_RANK_SEMANTICS,
        "invalid_candidate_count": int((~valid).sum()),
        "invalid_fraction": float((~valid).sum()) / float(max(valid.shape[0], 1)),
        "candidate_counts_by_position": _candidate_count_summary(candidate_payloads, "position_mode_name"),
        "candidate_counts_by_invalid_reason": _candidate_count_summary(
            candidate_payloads,
            "primary_invalid_reason_name",
        ),
        "pose_frame": "stored_pose_world_cam",
        "target": target_metadata or {},
        "selected_depth": {
            "enabled": bool(rollout_depths.enabled),
            "available": selected_depth is not None,
            "warnings": selected_depth_warnings,
            "representation": rollout_depths.representation,
            "depth_entity": (
                f"{candidate_payloads[selected_local].camera_entity}/depth"
                if (
                    selected_depth is not None
                    and selected_local >= 0
                    and rollout_depths.representation in ("depth_image", "both")
                )
                else None
            ),
            "points_entity": (
                f"{candidate_payloads[selected_local].camera_entity}/points"
                if (
                    selected_depth is not None
                    and selected_local >= 0
                    and rollout_depths.representation in ("point_cloud", "both")
                )
                else None
            ),
            "image_size_hw": list(selected_depth.image_size_hw) if selected_depth is not None else None,
        },
        "q_h": _q_h_metadata(reader, step_row_id=step_row_id),
    }
    return _RolloutStepPayload(
        rollout_row_id=rollout_row_id,
        chain_id=chain_id,
        step_row_id=step_row_id,
        step_index=step_index,
        step_entity=_rollout_step_entity(
            rollout_row_id=rollout_row_id,
            chain_id=chain_id,
            step_index=step_index,
        ),
        metadata_entity=_rollout_step_metadata_entity(
            rollout_row_id=rollout_row_id,
            chain_id=chain_id,
            step_index=step_index,
        ),
        candidates=candidate_payloads,
        selected_center=centers[selected_local] if selected_local >= 0 else None,
        valid_candidate_count=int(valid.sum()),
        selected_probability=float(probabilities[selected_local]) if selected_local >= 0 else float("nan"),
        selected_target_rri=float(target_rri[selected_local]) if selected_local >= 0 else float("nan"),
        selected_target_root_gain=float(target_root_gain[selected_local]) if selected_local >= 0 else float("nan"),
        selected_position_id=int(diagnostics["position_id"][selected_local]) if selected_local >= 0 else -1,
        invalid_fraction=float((~valid).sum()) / float(max(valid.shape[0], 1)),
        metadata=metadata,
    )


def _plot_step_payload(
    reader: RolloutZarrStoreReader,
    *,
    step_row_position: int,
    candidate_top_k: int,
) -> _RolloutPlotStep:
    step_row_id = int(reader.array("steps/step_row_id")[step_row_position])
    row_positions = _candidate_rows_for_step(reader, step_row_id=step_row_id)
    candidate_valid = reader.array("candidates/actor_action_mask")[row_positions].astype(bool)
    selected = reader.array("candidates/selected_mask")[row_positions].astype(bool)
    target_rri = reader.array("candidates/target_rri")[row_positions].astype(np.float32).reshape(-1)
    scene_rri = reader.array("candidates/scene_rri")[row_positions].astype(np.float32).reshape(-1)
    probabilities = reader.array("candidates/selection_probabilities")[row_positions].astype(np.float32).reshape(-1)
    log_probabilities = (
        reader.array("candidates/selection_log_probabilities")[row_positions].astype(np.float32).reshape(-1)
    )
    entropy = _selection_entropy(
        probabilities=probabilities,
        log_probabilities=log_probabilities,
        valid_mask=candidate_valid,
    )
    summary = _candidate_rri_summary(
        target_rri=target_rri,
        scene_rri=scene_rri,
        probabilities=probabilities,
        entropy=entropy,
        valid_mask=candidate_valid,
        selected_mask=selected,
        top_k=candidate_top_k,
    )
    return _RolloutPlotStep(
        step_row_id=step_row_id,
        cumulative_target_rri=float(reader.array("steps/cumulative_target_rri")[step_row_position]),
        selected_target_rri=summary.selected_target_rri,
        selected_scene_rri=summary.selected_scene_rri,
        selected_probability=summary.selected_probability,
        selected_entropy=summary.selected_entropy,
        valid_candidate_count=summary.valid_candidate_count,
        candidate_min_target_rri=summary.candidate_min_target_rri,
        candidate_mean_target_rri=summary.candidate_mean_target_rri,
        candidate_max_target_rri=summary.candidate_max_target_rri,
        top_candidate_target_rri=summary.top_candidate_target_rri,
    )


def _candidate_rows_for_step(reader: RolloutZarrStoreReader, *, step_row_id: int) -> NDArray[np.int64]:
    candidate_step_ids = reader.array("candidates/step_row_id").astype(np.int64).reshape(-1)
    row_positions = np.nonzero(candidate_step_ids == int(step_row_id))[0].astype(np.int64)
    shell_indices = reader.array("candidates/shell_index")[row_positions].astype(np.int64)
    return row_positions[np.argsort(shell_indices, kind="stable")]


def _selected_depth_payload(
    reader: RolloutZarrStoreReader,
    *,
    step_row_id: int,
    selected_candidate_row_id: int,
    config: "RerunInspectorRolloutDepthConfig",
) -> tuple[_SelectedDepthPayload | None, list[str]]:
    """Read one selected-depth row lazily for a rollout step."""

    if not config.enabled:
        return None, []

    def _handle_missing(message: str) -> tuple[None, list[str]]:
        if config.require_selected_depth:
            raise ValueError(message)
        return None, [message]

    if not bool(reader.root.attrs.get("selected_depth_enabled", False)):
        return _handle_missing("selected_depth unavailable: store metadata has selected_depth_enabled=false.")

    try:
        group = reader.root["selected_depth"]
        step_ids = np.asarray(group["step_row_id"], dtype=np.int64).reshape(-1)
        candidate_ids = np.asarray(group["candidate_row_id"], dtype=np.int64).reshape(-1)
    except KeyError as exc:
        return _handle_missing(f"selected_depth unavailable: missing array {exc}.")

    matches = np.nonzero(step_ids == int(step_row_id))[0]
    if matches.size != 1:
        return _handle_missing(
            f"selected_depth unavailable: expected one row for step_row_id={step_row_id}, found {matches.size}."
        )
    selected_depth_row = int(matches[0])
    stored_candidate_row_id = int(candidate_ids[selected_depth_row])
    if stored_candidate_row_id != int(selected_candidate_row_id):
        return _handle_missing(
            "selected_depth candidate mismatch: "
            f"depth candidate_row_id={stored_candidate_row_id}, step selected_candidate_row_id={selected_candidate_row_id}."
        )

    try:
        depth = np.asarray(group["depth_m"][selected_depth_row], dtype=np.float32)
        valid_mask = np.asarray(group["valid_mask"][selected_depth_row], dtype=np.bool_)
        focal = np.asarray(group["focal_px"][selected_depth_row], dtype=np.float32).reshape(-1)
        principal = np.asarray(group["principal_point_px"][selected_depth_row], dtype=np.float32).reshape(-1)
        image_size = np.asarray(group["image_size_hw"][selected_depth_row], dtype=np.int32).reshape(-1)
    except KeyError as exc:
        return _handle_missing(f"selected_depth unavailable: missing dense array {exc}.")

    if depth.ndim != 2 or valid_mask.shape != depth.shape:
        return _handle_missing(
            f"selected_depth shape mismatch: depth_m={tuple(depth.shape)} valid_mask={tuple(valid_mask.shape)}."
        )
    if focal.shape[0] != 2 or principal.shape[0] != 2 or image_size.shape[0] != 2:
        return _handle_missing("selected_depth camera metadata must have two values per row.")

    height, width = int(image_size[0]), int(image_size[1])
    if (height, width) != tuple(depth.shape):
        return _handle_missing(
            f"selected_depth image_size_hw={(height, width)} does not match depth shape {tuple(depth.shape)}."
        )

    depth = depth.astype(np.float32, copy=True)
    finite_valid = valid_mask & np.isfinite(depth)
    depth[~finite_valid] = np.nan
    return (
        _SelectedDepthPayload(
            step_row_id=int(step_row_id),
            candidate_row_id=stored_candidate_row_id,
            depth_m=depth,
            valid_mask=valid_mask.astype(np.bool_, copy=True),
            focal_px=focal.astype(np.float32, copy=True),
            principal_point_px=principal.astype(np.float32, copy=True),
            image_size_hw=(height, width),
        ),
        [],
    )


def _candidate_rri_summary(
    *,
    target_rri: NDArray[Any],
    scene_rri: NDArray[Any],
    probabilities: NDArray[Any],
    entropy: float,
    valid_mask: NDArray[Any],
    selected_mask: NDArray[Any],
    top_k: int,
) -> _CandidateRriSummary:
    values = np.asarray(target_rri, dtype=np.float32).reshape(-1)
    scene_values = np.asarray(scene_rri, dtype=np.float32).reshape(-1)
    valid = np.asarray(valid_mask, dtype=bool).reshape(-1)
    selected = np.asarray(selected_mask, dtype=bool).reshape(-1)
    finite_valid = valid & np.isfinite(values)
    finite_values = values[finite_valid]
    selected_index = int(np.nonzero(selected)[0][0]) if selected.any() else -1
    if finite_values.size:
        sorted_values = np.sort(finite_values)[::-1]
        minimum = float(np.min(finite_values))
        mean = float(np.mean(finite_values))
        maximum = float(np.max(finite_values))
        top_values = tuple(float(value) for value in sorted_values[: int(top_k)])
    else:
        minimum = mean = maximum = float("nan")
        top_values = ()
    selected_target = float(values[selected_index]) if selected_index >= 0 else float("nan")
    selected_scene = float(scene_values[selected_index]) if selected_index >= 0 else float("nan")
    selected_probability = (
        float(np.asarray(probabilities, dtype=np.float32).reshape(-1)[selected_index])
        if selected_index >= 0
        else float("nan")
    )
    selected_entropy = float(entropy) if selected_index >= 0 else float("nan")
    return _CandidateRriSummary(
        selected_target_rri=selected_target,
        selected_scene_rri=selected_scene,
        selected_probability=selected_probability,
        selected_entropy=selected_entropy,
        valid_candidate_count=int(valid.sum()),
        candidate_min_target_rri=minimum,
        candidate_mean_target_rri=mean,
        candidate_max_target_rri=maximum,
        top_candidate_target_rri=top_values,
    )


def _selection_entropy(
    *,
    probabilities: NDArray[Any],
    log_probabilities: NDArray[Any],
    valid_mask: NDArray[Any],
) -> float:
    """Return the finite-candidate policy entropy for one rollout step."""

    prob = np.asarray(probabilities, dtype=np.float32).reshape(-1)
    log_prob = np.asarray(log_probabilities, dtype=np.float32).reshape(-1)
    valid = np.asarray(valid_mask, dtype=bool).reshape(-1)
    usable = valid & np.isfinite(prob) & np.isfinite(log_prob) & (prob > 0.0)
    if not bool(usable.any()):
        return float("nan")
    return float(-(prob[usable] * log_prob[usable]).sum())


def _q_h_metadata(reader: RolloutZarrStoreReader, *, step_row_id: int) -> dict[str, Any]:
    try:
        state_step_ids = reader.array("steps/step_row_id").astype(np.int64).reshape(-1)
        step_indices = reader.array("steps/step_index").astype(np.int64).reshape(-1)
        step_rollout_ids = reader.array("steps/rollout_row_id").astype(np.int64).reshape(-1)
        step_selected_candidate_ids = reader.array("steps/selected_candidate_row_id").astype(np.int64).reshape(-1)
        candidate_step_ids = reader.array("candidates/step_row_id").astype(np.int64).reshape(-1)
    except KeyError as exc:
        return {"state_row_found": False, "warning": f"Q_H metadata unavailable: missing array {exc}."}

    matches = np.nonzero(state_step_ids == int(step_row_id))[0]
    if matches.size != 1:
        return {"state_row_found": False}
    row = int(matches[0])

    candidate_rows = np.nonzero(candidate_step_ids == int(step_row_id))[0].astype(np.int64)
    try:
        valid_mask = reader.array("candidates/actor_action_mask")[candidate_rows].astype(bool)
    except KeyError as exc:
        return {"state_row_found": False, "warning": f"Q_H metadata unavailable: missing array {exc}."}
    try:
        train_mask = reader.array("candidates/q_train_mask")[candidate_rows].astype(bool) & valid_mask
    except KeyError:
        target_rri = reader.array("candidates/target_rri")[candidate_rows].astype(np.float32).reshape(-1)
        train_mask = valid_mask & np.isfinite(target_rri)

    selected_candidate_row_id = int(step_selected_candidate_ids[row])
    candidate_row_ids = reader.array("candidates/candidate_row_id")[candidate_rows].astype(np.int64).reshape(-1)
    selected_matches = np.nonzero(candidate_row_ids == selected_candidate_row_id)[0]
    selected_local_index = int(selected_matches[0]) if selected_matches.size else -1
    target_rri = reader.array("candidates/target_rri")[candidate_rows].astype(np.float32).reshape(-1)
    td_reward_target_rri = float(target_rri[selected_local_index]) if selected_local_index >= 0 else float("nan")

    rollout_row_id = int(step_rollout_ids[row])
    next_step_matches = np.nonzero((step_rollout_ids == rollout_row_id) & (step_indices == int(step_indices[row]) + 1))[
        0
    ]
    next_step_row_id = int(state_step_ids[int(next_step_matches[0])]) if next_step_matches.size else -1
    return {
        "state_row_found": True,
        "q_h_state_row": row,
        "valid_action_count": int(valid_mask.sum()),
        "trainable_action_count": int(train_mask.sum()),
        "selected_candidate_index": selected_local_index,
        "td_selected_candidate_row_id": selected_candidate_row_id,
        "td_reward_target_rri": td_reward_target_rri,
        "td_next_step_row_id": next_step_row_id,
        "td_terminal": next_step_row_id < 0,
        "selected_transition_available": selected_candidate_row_id >= 0,
    }


def _candidate_count_summary(candidates: list[_RolloutCandidatePayload], attr_name: str) -> dict[str, dict[str, int]]:
    """Return compact valid/selected counts by one candidate payload attribute."""

    output: dict[str, dict[str, int]] = {}
    for candidate in candidates:
        key = str(getattr(candidate, attr_name))
        row = output.setdefault(key, {"total": 0, "valid": 0, "selected": 0})
        row["total"] += 1
        if candidate.primary_invalid_reason_name == "VALID":
            row["valid"] += 1
        if candidate.selected:
            row["selected"] += 1
    return output


def _pose_centers(pose_rows: NDArray[np.float32]) -> NDArray[np.float32]:
    if pose_rows.size == 0:
        return np.empty((0, 3), dtype=np.float32)
    return pose_rows.reshape(-1, 12)[:, 9:12].astype(np.float32, copy=True)


def _selected_depth_points_camera(
    selected_depth: _SelectedDepthPayload,
    *,
    max_points: int,
) -> NDArray[np.float32]:
    """Unproject selected-depth pixels to camera-local LUF points for display."""

    if max_points <= 0:
        return np.empty((0, 3), dtype=np.float32)
    depth = np.asarray(selected_depth.depth_m, dtype=np.float32)
    valid = np.asarray(selected_depth.valid_mask, dtype=bool) & np.isfinite(depth) & (depth > 0.0)
    rows, cols = np.nonzero(valid)
    if rows.size == 0:
        return np.empty((0, 3), dtype=np.float32)

    if rows.size > max_points:
        indices = np.linspace(0, rows.size - 1, num=int(max_points), dtype=np.int64)
        rows = rows[indices]
        cols = cols[indices]

    z = depth[rows, cols]
    fx, fy = selected_depth.focal_px.astype(np.float32)
    cx, cy = selected_depth.principal_point_px.astype(np.float32)
    x_left = (cx - cols.astype(np.float32)) * z / fx
    y_up = (cy - rows.astype(np.float32)) * z / fy
    return np.stack([x_left, y_up, z], axis=1).astype(np.float32, copy=False)


def _rollout_root_path(
    reader: RolloutZarrStoreReader,
    *,
    rows: SelectedRolloutRows,
) -> list[list[float]]:
    """Return the selected-path seed point in the displayed world frame."""

    root = reader.array("rollouts/root_pose_world")[rows.rollout_index].astype(np.float32).reshape(1, 12)
    return [_pose_centers(root)[0].tolist()]


def _rollout_chain_entity(*, rollout_row_id: int, chain_id: int) -> str:
    return f"{ENTITY_ROLLOUT_ROOT}/rollout_{int(rollout_row_id):06d}/chain_{int(chain_id):06d}"


def _rollout_step_entity(*, rollout_row_id: int, chain_id: int, step_index: int) -> str:
    return f"{_rollout_chain_entity(rollout_row_id=rollout_row_id, chain_id=chain_id)}/step_{int(step_index):03d}"


def _rollout_candidate_entity(
    *,
    rollout_row_id: int,
    chain_id: int,
    step_index: int,
    status: str,
    shell_index: int,
) -> str:
    return (
        f"{_rollout_step_entity(rollout_row_id=rollout_row_id, chain_id=chain_id, step_index=step_index)}"
        f"/{status}/candidate_shell_{int(shell_index):03d}"
    )


def _rollout_selected_path_entity(*, rollout_row_id: int, chain_id: int) -> str:
    return f"{_rollout_chain_entity(rollout_row_id=rollout_row_id, chain_id=chain_id)}/selected_path"


def _rollout_step_metadata_entity(*, rollout_row_id: int, chain_id: int, step_index: int) -> str:
    return (
        f"{ENTITY_ROLLOUT_METADATA}/rollout_{int(rollout_row_id):06d}/"
        f"chain_{int(chain_id):06d}/step_{int(step_index):03d}"
    )


def _rollout_target_entity(*, rollout_row_id: int, chain_id: int) -> str:
    return f"{_rollout_chain_entity(rollout_row_id=rollout_row_id, chain_id=chain_id)}/target"


def _rollout_candidate_group_hidden_paths(
    *,
    reader: RolloutZarrStoreReader,
    rows: SelectedRolloutRows,
) -> tuple[str, ...]:
    """Return exact rollout candidate subtrees hidden by default in the viewer."""

    step_indices = reader.array("steps/step_index")[rows.step_rows].astype(np.int64).reshape(-1)
    selected_shell_indices = reader.array("steps/selected_shell_index")[rows.step_rows].astype(np.int64).reshape(-1)
    hidden_paths: list[str] = []
    for step_index, selected_shell_index in zip(step_indices.tolist(), selected_shell_indices.tolist(), strict=False):
        step_entity = _rollout_step_entity(
            rollout_row_id=rows.rollout_row_id,
            chain_id=rows.chain_id,
            step_index=int(step_index),
        )
        hidden_paths.extend((f"{step_entity}/valid", f"{step_entity}/invalid"))
        selected_camera = f"{step_entity}/selected/candidate_shell_{int(selected_shell_index):03d}/camera"
        hidden_paths.extend((f"{selected_camera}/depth", f"{selected_camera}/points"))
    return tuple(hidden_paths)


def _target_rri_ranks(
    *,
    target_rri: NDArray[Any],
    valid_mask: NDArray[Any],
    shell_indices: NDArray[Any],
) -> tuple[NDArray[np.int32], int]:
    """Rank valid finite target-RRI candidates, descending with shell-index tie-breaks."""

    values = np.asarray(target_rri, dtype=np.float32).reshape(-1)
    valid = np.asarray(valid_mask, dtype=bool).reshape(-1)
    shells = np.asarray(shell_indices, dtype=np.int64).reshape(-1)
    ranks = np.full(values.shape, -1, dtype=np.int32)
    eligible = np.nonzero(valid & np.isfinite(values))[0]
    if eligible.size == 0:
        return ranks, 0
    order = sorted(eligible.tolist(), key=lambda index: (-float(values[index]), int(shells[index])))
    for rank, index in enumerate(order, start=1):
        ranks[index] = int(rank)
    return ranks, int(eligible.size)


def _position_name(position_id: int) -> str:
    return _POSITION_NAMES.get(int(position_id), f"unknown_{int(position_id)}")


def _primary_reason_name(reason_id: int) -> str:
    return _INVALID_REASON_NAMES.get(int(reason_id), f"unknown_{int(reason_id)}")


def _candidate_diagnostics_for_rows(
    reader: RolloutZarrStoreReader,
    *,
    row_positions: NDArray[Any],
) -> dict[str, NDArray[Any]]:
    """Read curated candidate-generation diagnostics aligned with candidate row positions."""

    return {
        "position_id": _optional_rows(
            reader,
            "candidate_diagnostics/position_id",
            row_positions=row_positions,
            dtype=np.int32,
            default=-1,
        ),
        "mesh_distance_m": _optional_rows(
            reader,
            "candidate_diagnostics/mesh_distance_m",
            row_positions=row_positions,
            dtype=np.float32,
            default=np.nan,
        ),
        "path_min_clearance_m": _optional_rows(
            reader,
            "candidate_diagnostics/path_min_clearance_m",
            row_positions=row_positions,
            dtype=np.float32,
            default=np.nan,
        ),
        "motion_step_length_m": _optional_rows(
            reader,
            "candidate_diagnostics/motion_step_length_m",
            row_positions=row_positions,
            dtype=np.float32,
            default=np.nan,
        ),
        "target_distance_m": _optional_rows(
            reader,
            "candidate_diagnostics/target_distance_m",
            row_positions=row_positions,
            dtype=np.float32,
            default=np.nan,
        ),
    }


def _optional_rows(
    reader: RolloutZarrStoreReader,
    path: str,
    *,
    row_positions: NDArray[Any],
    dtype: Any,
    default: float | int | bool,
) -> NDArray[Any]:
    """Read a row-aligned optional array, filling absent fields for old stores."""

    try:
        values = reader.array(path)[row_positions].astype(dtype).reshape(-1)
    except KeyError:
        values = np.full((int(row_positions.shape[0]),), default, dtype=dtype)
    return values


def _component_names(reader: RolloutZarrStoreReader) -> dict[int, str]:
    """Return candidate-mixture component names from the store manifest when available."""

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
                name = component.get("name") or component.get("family") or component.get("position_mode")
                if name is not None:
                    names[index] = str(name)
    return names


def _component_name(component_name_by_id: dict[int, str], mixture_id: int) -> str:
    return component_name_by_id.get(int(mixture_id), f"mixture_{int(mixture_id)}")


def _candidate_payloads(
    *,
    candidate_row_ids: NDArray[Any],
    rollout_row_id: int,
    chain_id: int,
    step_row_id: int,
    shell_indices: NDArray[Any],
    compact_valid: NDArray[Any],
    valid: NDArray[Any],
    selected: NDArray[Any],
    step_index: int,
    poses: NDArray[np.float32],
    centers: NDArray[np.float32],
    target_rri: NDArray[Any],
    target_root_gain: NDArray[Any],
    target_rri_ranks: NDArray[Any],
    target_rri_rank_total: int,
    probabilities: NDArray[Any],
    mixture_ids: NDArray[Any],
    sampler_probabilities: NDArray[Any],
    position_ids: NDArray[Any],
    mesh_distance_m: NDArray[Any],
    path_min_clearance_m: NDArray[Any],
    motion_step_length_m: NDArray[Any],
    target_distance_m: NDArray[Any],
    reason_bitsets: NDArray[Any],
    primary_reasons: NDArray[Any],
    selected_depth: _SelectedDepthPayload | None,
    component_name_by_id: dict[int, str],
) -> list[_RolloutCandidatePayload]:
    payloads: list[_RolloutCandidatePayload] = []
    for values in zip(
        candidate_row_ids,
        shell_indices,
        compact_valid,
        valid,
        selected,
        poses,
        centers,
        target_rri,
        target_root_gain,
        target_rri_ranks,
        probabilities,
        mixture_ids,
        sampler_probabilities,
        position_ids,
        mesh_distance_m,
        path_min_clearance_m,
        motion_step_length_m,
        target_distance_m,
        reason_bitsets,
        primary_reasons,
        strict=False,
    ):
        (
            row_id,
            shell,
            compact,
            is_valid,
            is_selected,
            pose,
            center,
            rri,
            root_gain,
            rri_rank,
            prob,
            mixture_id,
            sampler_probability,
            position_id,
            mesh_distance,
            path_clearance,
            motion_step_length,
            target_distance,
            _reason,
            primary,
        ) = values
        shell_index = int(shell)
        status = _candidate_status(valid=bool(is_valid), selected=bool(is_selected))
        color = _candidate_color(
            valid=bool(is_valid),
            selected=bool(is_selected),
            step_index=step_index,
        )
        candidate_root = _rollout_candidate_entity(
            rollout_row_id=rollout_row_id,
            chain_id=chain_id,
            step_index=step_index,
            status=status,
            shell_index=shell_index,
        )
        payloads.append(
            _RolloutCandidatePayload(
                row_id=int(row_id),
                step_row_id=int(step_row_id),
                compact_valid_index=int(compact),
                selected=bool(is_selected),
                pose=np.asarray(pose, dtype=np.float32).reshape(12),
                center=np.asarray(center, dtype=np.float32).reshape(3),
                position_id=int(position_id),
                target_rri=float(rri),
                target_root_gain=float(root_gain),
                target_rri_rank=int(rri_rank),
                target_rri_rank_total=int(target_rri_rank_total),
                probability=float(prob),
                mixture_component_name=_component_name(component_name_by_id, int(mixture_id)),
                position_mode_name=_position_name(int(position_id)),
                sampler_probability=float(sampler_probability),
                mesh_distance_m=float(mesh_distance),
                path_min_clearance_m=float(path_clearance),
                motion_step_length_m=float(motion_step_length),
                target_distance_m=float(target_distance),
                primary_invalid_reason_name=_primary_reason_name(int(primary)),
                color=color,
                camera_entity=f"{candidate_root}/camera",
                center_entity=f"{candidate_root}/center",
                selected_depth=selected_depth if bool(is_selected) else None,
            ),
        )
    return payloads


def _candidate_status(*, valid: bool, selected: bool) -> str:
    if selected:
        return "selected"
    return "valid" if valid else "invalid"


def _candidate_color(*, valid: bool, selected: bool, step_index: int) -> list[int]:
    step_color = step_to_rgba([step_index], alpha=255 if selected else 220).reshape(1, 4)[0].astype(int).tolist()
    if selected:
        return step_color
    if valid:
        return step_color
    invalid_color = step_color.copy()
    invalid_color[3] = int(INVALID_RGBA[3])
    return invalid_color


def _rollout_context_selection(
    reader: RolloutZarrStoreReader,
    *,
    rows: SelectedRolloutRows,
    fallback: RerunInspectorSelectionConfig,
) -> RerunInspectorSelectionConfig | None:
    if fallback.sample_key or (fallback.scene_id and fallback.snippet_id):
        return fallback.model_copy(deep=True)

    scene_id = _rollout_dictionary_value(reader, group="scene", array_path="rollouts/scene_id", row=rows.rollout_index)
    snippet_id = _rollout_dictionary_value(
        reader,
        group="snippet",
        array_path="rollouts/snippet_id",
        row=rows.rollout_index,
    )
    if scene_id and snippet_id:
        return fallback.model_copy(
            deep=True,
            update={"scene_id": scene_id, "snippet_id": compact_ase_atek_sample_id(snippet_id), "sample_key": None},
        )
    if fallback.rollout_context_mode == "required":
        return fallback.model_copy(deep=True)
    return None


def _rollout_dictionary_value(
    reader: RolloutZarrStoreReader,
    *,
    group: str,
    array_path: str,
    row: int,
) -> str | None:
    dictionary = _read_string_dictionary(reader, f"dictionaries/{group}")
    index = int(reader.array(array_path)[row])
    if index < 0 or index >= len(dictionary):
        return None
    value = dictionary[index].strip()
    return value or None


def _dictionary_preview(reader: RolloutZarrStoreReader) -> dict[str, list[str]]:
    return compact_ase_atek_identifiers(
        {
            name: _read_string_dictionary(reader, f"dictionaries/{name}")[:20]
            for name in ("scene", "snippet", "rollout", "target", "policy", "termination_reason")
        }
    )


def _rollout_target_payload(reader: RolloutZarrStoreReader, *, rows: SelectedRolloutRows) -> _RolloutTargetPayload:
    """Build the visible rollout-target overlay payload from factual target tables."""

    target_row_id = int(reader.array("rollouts/target_row_id")[rows.rollout_index])
    target_row_ids = reader.array("targets/target_row_id").astype(np.int64).reshape(-1)
    matches = np.nonzero(target_row_ids == target_row_id)[0]
    target_index = int(matches[0]) if matches.size == 1 else -1
    entity_root = _rollout_target_entity(rollout_row_id=rows.rollout_row_id, chain_id=rows.chain_id)

    scene_id = _rollout_dictionary_value(reader, group="scene", array_path="rollouts/scene_id", row=rows.rollout_index)
    snippet_id = _rollout_dictionary_value(
        reader,
        group="snippet",
        array_path="rollouts/snippet_id",
        row=rows.rollout_index,
    )
    source_row_id = int(reader.array("rollouts/source_row_id")[rows.rollout_index])
    target_ids = _encoded_values(reader.root, dictionary_name="target", array_path="targets/target_id")
    matched_gt_ids = _encoded_values(reader.root, dictionary_name="target", array_path="targets/matched_gt_target_id")
    target_sources = _encoded_values(
        reader.root, dictionary_name="target_source", array_path="targets/target_source_id"
    )
    class_names = _encoded_values(reader.root, dictionary_name="class_name", array_path="targets/target_class_name_id")
    match_statuses = _encoded_values(
        reader.root,
        dictionary_name="target_match_status",
        array_path="targets/gt_match_status_id",
    )

    warnings: list[str] = []
    if target_index < 0:
        warnings.append(f"rollout target_row_id={target_row_id} does not resolve to exactly one targets/ row.")
        return _RolloutTargetPayload(
            entity_root=entity_root,
            metadata={
                "rollout_row_id": rows.rollout_row_id,
                "chain_id": rows.chain_id,
                "source_row_id": source_row_id,
                "scene_id": scene_id,
                "snippet_id": compact_ase_atek_sample_id(snippet_id) if snippet_id is not None else None,
                "target_row_id": target_row_id,
                "warnings": warnings,
            },
            warnings=warnings,
            center=None,
            extents=None,
            pose_world_object=None,
        )

    target_id = _value_at(target_ids, target_index)
    matched_gt_target_id = _value_at(matched_gt_ids, target_index)
    for array_name, identifier in (("target_id", target_id), ("matched_gt_target_id", matched_gt_target_id)):
        if _target_identifier_mentions_other_snippet(identifier=identifier, snippet=snippet_id or ""):
            warnings.append(
                f"targets/{array_name}={compact_ase_atek_sample_id(identifier)!r} "
                f"does not match rollout snippet_id={compact_ase_atek_sample_id(snippet_id or '')!r}; "
                "the store is stale or target rows collided."
            )

    center = reader.array("targets/target_center_world")[target_index].astype(np.float32).reshape(3)
    extents = reader.array("targets/target_extents")[target_index].astype(np.float32).reshape(3)
    pose = reader.array("targets/target_pose_world_object")[target_index].astype(np.float32).reshape(12)
    metadata = {
        "rollout_row_id": rows.rollout_row_id,
        "chain_id": rows.chain_id,
        "source_row_id": source_row_id,
        "scene_id": scene_id,
        "snippet_id": compact_ase_atek_sample_id(snippet_id) if snippet_id is not None else None,
        "target_row_id": target_row_id,
        "target_id": target_id,
        "target_source": _value_at(target_sources, target_index),
        "target_source_index": int(reader.array("targets/target_source_index")[target_index]),
        "target_sem_id": int(reader.array("targets/target_sem_id")[target_index]),
        "target_inst_id": int(reader.array("targets/target_inst_id")[target_index]),
        "target_class_name": _value_at(class_names, target_index),
        "target_confidence": float(reader.array("targets/target_confidence")[target_index]),
        "target_projected_area_pixels": _optional_scalar(
            reader,
            "targets/target_projected_area_pixels",
            target_index,
        ),
        "target_projected_area_fraction": _optional_scalar(
            reader,
            "targets/target_projected_area_fraction",
            target_index,
        ),
        "target_semidense_support_count": _optional_scalar(
            reader,
            "targets/target_semidense_support_count",
            target_index,
        ),
        "target_evl_support_count": _optional_scalar(reader, "targets/target_evl_support_count", target_index),
        "target_effective_support_count": _optional_scalar(
            reader,
            "targets/target_effective_support_count",
            target_index,
        ),
        "target_visibility_score": _optional_scalar(reader, "targets/target_visibility_score", target_index),
        "target_support_score": _optional_scalar(reader, "targets/target_support_score", target_index),
        "target_deficit_score": _optional_scalar(reader, "targets/target_deficit_score", target_index),
        "target_center_world": center.astype(float).tolist(),
        "target_extents": extents.astype(float).tolist(),
        "matched_gt_target_row_id": int(reader.array("targets/matched_gt_target_row_id")[target_index]),
        "matched_gt_target_id": matched_gt_target_id,
        "gt_match_status": _value_at(match_statuses, target_index),
        "gt_match_iou": float(reader.array("targets/gt_match_iou")[target_index]),
        "gt_match_score": float(reader.array("targets/gt_match_score")[target_index]),
        "target_selection_rank": int(reader.array("targets/target_selection_rank")[target_index]),
        "target_selection_score": float(reader.array("targets/target_selection_score")[target_index]),
        "target_selection_probability": float(reader.array("targets/target_selection_probability")[target_index]),
        "matched_gt_obb": {
            "dedicated_overlay": "logged_when_vin_context_available",
            "source": "VIN context GT OBBs; matched GT geometry is not persisted in rollouts.zarr.",
        },
        "warnings": warnings,
    }
    return _RolloutTargetPayload(
        entity_root=entity_root,
        metadata=metadata,
        warnings=warnings,
        center=center,
        extents=extents,
        pose_world_object=pose,
    )


def _rollout_target_hint(reader: RolloutZarrStoreReader, *, rows: SelectedRolloutRows) -> str | None:
    """Return a target dictionary value for optional OBB highlighting."""

    target_rows = reader.array("targets/target_row_id").astype(np.int64).reshape(-1)
    target_row_id = int(reader.array("rollouts/target_row_id")[rows.rollout_index])
    names = _read_string_dictionary(reader, "dictionaries/target")
    matches = np.nonzero(target_rows == target_row_id)[0]
    if matches.size != 1:
        return str(target_row_id)
    match_index = int(matches[0])
    gt_target_ids = reader.array("targets/matched_gt_target_id").astype(np.int64).reshape(-1)
    target_ids = reader.array("targets/target_id").astype(np.int64).reshape(-1)
    name_index = int(gt_target_ids[match_index])
    if name_index < 0:
        name_index = int(target_ids[match_index])
    if 0 <= name_index < len(names):
        return names[name_index]
    return str(target_row_id)


def _read_string_dictionary(reader: RolloutZarrStoreReader, path: str) -> list[str]:
    encoded = reader.array(path).astype(np.uint8).reshape(-1).tobytes()
    values = json.loads(encoded.decode("utf-8"))
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def _encoded_values(root: Any, *, dictionary_name: str, array_path: str) -> list[str]:
    try:
        encoded = np.asarray(root[array_path]).reshape(-1)
        dictionary = json.loads(np.asarray(root[f"dictionaries/{dictionary_name}"], dtype=np.uint8).tobytes())
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(dictionary, list):
        return []
    values: list[str] = []
    for index in encoded:
        index_int = int(index)
        values.append(str(dictionary[index_int]) if 0 <= index_int < len(dictionary) else "")
    return values


def _value_at(values: list[str], index: int) -> str:
    return values[index] if 0 <= int(index) < len(values) else ""


def _optional_scalar(reader: RolloutZarrStoreReader, path: str, index: int) -> float | int | None:
    """Read one optional scalar field from a rollout store."""

    try:
        values = np.asarray(reader.array(path)).reshape(-1)
    except KeyError:
        return None
    if index < 0 or index >= int(values.shape[0]):
        return None
    value = values[index].item()
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def _target_identifier_mentions_other_snippet(*, identifier: str, snippet: str) -> bool:
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


def _structured_target_value(target_id: str, *, key: str) -> int | None:
    match = re.search(rf"(?:^|[:/_-]){key}(?:_id)?[=:](\d+)(?:$|[:/_-])", str(target_id).lower())
    return None if match is None else int(match.group(1))


def _matrix3x3_to_quat_xyzw(matrix: NDArray[np.float32]) -> NDArray[np.float32]:
    """Convert a rotation matrix to an xyzw quaternion for Rerun Boxes3D."""

    rot = np.asarray(matrix, dtype=np.float64).reshape(3, 3)
    trace = float(np.trace(rot))
    if trace > 0.0:
        scale = np.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * scale
        qx = (rot[2, 1] - rot[1, 2]) / scale
        qy = (rot[0, 2] - rot[2, 0]) / scale
        qz = (rot[1, 0] - rot[0, 1]) / scale
    else:
        diagonal = np.diagonal(rot)
        axis = int(np.argmax(diagonal))
        if axis == 0:
            scale = np.sqrt(1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2]) * 2.0
            qw = (rot[2, 1] - rot[1, 2]) / scale
            qx = 0.25 * scale
            qy = (rot[0, 1] + rot[1, 0]) / scale
            qz = (rot[0, 2] + rot[2, 0]) / scale
        elif axis == 1:
            scale = np.sqrt(1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2]) * 2.0
            qw = (rot[0, 2] - rot[2, 0]) / scale
            qx = (rot[0, 1] + rot[1, 0]) / scale
            qy = 0.25 * scale
            qz = (rot[1, 2] + rot[2, 1]) / scale
        else:
            scale = np.sqrt(1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1]) * 2.0
            qw = (rot[1, 0] - rot[0, 1]) / scale
            qx = (rot[0, 2] + rot[2, 0]) / scale
            qy = (rot[1, 2] + rot[2, 1]) / scale
            qz = 0.25 * scale
    quat = np.asarray([qx, qy, qz, qw], dtype=np.float32)
    norm = float(np.linalg.norm(quat))
    return quat if norm == 0.0 else (quat / norm).astype(np.float32)


def _safe_entity_token(value: str) -> str:
    token = "".join(char if char.isalnum() else "_" for char in value.strip().lower())
    token = "_".join(part for part in token.split("_") if part)
    return token or "unknown"


def _plot_color(*, branch_order: int, selected: bool) -> list[int]:
    color = list(_PLOT_PALETTE[branch_order % len(_PLOT_PALETTE)])
    color[3] = 255 if selected else 150
    return color


def _finite_or_zero(value: float) -> float:
    return float(value) if np.isfinite(value) else 0.0


def run_rollout_zarr_inspector(
    config: RerunOfflineInspectorConfig,
    *,
    store_dir: Path | str,
    rollout_index: int = 0,
    rollout_row_id: int | None = None,
    rr_module: RerunModule | None = None,
) -> SelectedRolloutRows:
    """Run the Rerun rollout-store inspector for tests and CLI callers."""

    logger = RerunRolloutZarrLogger(config, rr_module=rr_module)
    logger.start()
    return logger.log_store(store_dir=store_dir, rollout_index=rollout_index, rollout_row_id=rollout_row_id)


__all__ = [
    "ENTITY_ROLLOUT_DIAGNOSTICS_ROOT",
    "ENTITY_ROLLOUT_INVALID_FRACTION",
    "ENTITY_ROLLOUT_METADATA",
    "ENTITY_ROLLOUT_RRI_ROOT",
    "ENTITY_ROLLOUT_ROOT",
    "ENTITY_ROLLOUT_SELECTED_POSITION_ID",
    "ENTITY_ROLLOUT_SELECTED_TARGET_ROOT_GAIN",
    "RerunRolloutZarrLogger",
    "SelectedRolloutRows",
    "run_rollout_zarr_inspector",
]
