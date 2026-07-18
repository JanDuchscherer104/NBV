"""Inspect validated rollout Zarr facts without mutating replay artifacts.

This module owns rollout-row resolution, full-shell candidate visualization,
selected-path timelines, branch plots, target provenance, and selected-depth
display. ``actor_action_mask`` and compact-valid indices remain distinct from
the full shell; target RRI, GT matches, and mesh-rendered depth are explicitly
oracle/evaluation overlays rather than actor-visible state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import torch

from aria_nbv.data_handling.identifiers import (
    compact_ase_atek_identifiers,
    compact_ase_atek_sample_id,
    raw_ase_atek_sample_id,
)
from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.audits import candidate_policy_entropy
from aria_nbv.rollouts.read_model import (
    StoredRollout,
    StoredStep,
    rollout_at,
    rollout_by_id,
    rollout_steps,
    selected_depth_for_step,
    target_by_id,
)
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

_TARGET_RRI_RANK_SEMANTICS = "valid_finite_target_rri_desc"


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
    ) -> StoredRollout:
        """Log one rollout chain from a validated rollout Zarr store."""

        reader = RolloutZarrStoreReader(store_dir)
        validation = validate_rollout_zarr_store(store_dir)
        rows = rollout_at(reader, rollout_index) if rollout_row_id is None else rollout_by_id(reader, rollout_row_id)
        steps = rollout_steps(reader, rows)
        target = _rollout_target_payload(reader, rows=rows)
        self._context_warnings.extend(target.warnings)
        self._log_rollout_blueprint(rows=rows, steps=steps)
        self._log_static_context(reader=reader, rows=rows, target=target)
        self._log_rollout_target(target)
        if self.config.rollout_layers.metadata.included:
            self._log_static_metadata(reader=reader, rows=rows, validation_errors=validation.errors, target=target)
        self._log_rollout_plots(reader=reader, selected_rows=rows)

        selected_path: list[list[float]] = _rollout_root_path(rows)
        rollout_depths = self.config.rollout_depths
        if not self.config.rollout_layers.selected_depth.included:
            rollout_depths = rollout_depths.model_copy(update={"enabled": False})
        for order, stored_step in enumerate(steps):
            self._set_rollout_step_time(order)
            step = _step_payload(
                reader,
                rollout=rows,
                step=stored_step,
                rollout_depths=rollout_depths,
                target_metadata=target.metadata,
            )
            self._log_step(step)
            if step.selected_center is not None:
                selected_path.append(step.selected_center.tolist())
            if self.config.rollout_layers.selected_path.included:
                self._log_selected_path(rows=rows, selected_path=selected_path)
        return rows

    def _log_rollout_blueprint(self, *, rows: StoredRollout, steps: tuple[StoredStep, ...]) -> None:
        """Send rollout-specific visibility defaults for the selected chain."""

        log_default_inspector_blueprint(
            self.rr,
            hidden_world_paths=_rollout_layer_hidden_paths(config=self.config, rows=rows, steps=steps),
            use_default_hidden_paths=False,
            scalar_plots_visible=self.config.rollout_layers.scalar_plots.visible,
            metadata_visible=self.config.rollout_layers.metadata.visible,
        )

    def _log_static_context(
        self,
        *,
        reader: RolloutZarrStoreReader,
        rows: StoredRollout,
        target: "_RolloutTargetPayload",
    ) -> None:
        """Log matching VIN offline sample context before rollout-step layers."""

        mode = self.config.selection.rollout_context_mode
        if mode == "off":
            self._context_warnings.append("VIN context logging disabled by selection.rollout_context_mode='off'.")
            return
        context_config = _rollout_context_config(self.config)
        if not _rollout_context_is_included(context_config):
            self._context_warnings.append("VIN context logging excluded by rollout layer policy.")
            return
        selection = _rollout_context_selection(rows=rows, fallback=self.config.selection)
        if selection is None:
            message = "No rollout scene/snippet or explicit sample selector available for VIN context logging."
            if mode == "required":
                raise LookupError(message)
            self._context_warnings.append(message)
            return
        try:
            selected = select_rerun_sample(dataset_config=self.config.dataset.offline, selection=selection)
            inventory = collect_visual_inventory(selected.sample)
            validate_required_inventory(context_config, inventory)
            logger = RerunOfflineLogger(
                context_config,
                rr_module=self.rr,
                target_obb_hint=str(
                    target.metadata.get("matched_gt_target_id")
                    or target.metadata.get("target_id")
                    or target.metadata.get("target_row_id")
                    or ""
                )
                or None,
            )
            logger.log_sample(sample=selected.sample, inventory=inventory, selection=selected.description)
            logger.log_metadata(sample=selected.sample, inventory=inventory, selection=selected.description)
            if self.config.rollout_layers.target_overlay.included:
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
        rows: StoredRollout,
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
                "rollout_index": rows.row_position,
                "chain_id": rows.chain_id,
                "step_rows": rows.step_row_positions.astype(int).tolist(),
            },
            "validation": {"ok": not validation_errors, "errors": validation_errors},
            "target": target.metadata,
            "context": {
                "mode": self.config.selection.rollout_context_mode,
                "warnings": list(self._context_warnings),
            },
            "dictionaries": _dictionary_preview(rows=rows, target=target),
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

        include_overlay = self.config.rollout_layers.target_overlay.included
        if include_overlay and target.center is not None and np.isfinite(target.center).all():
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
            include_overlay
            and target.center is not None
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
        if self.config.rollout_layers.metadata.included:
            self.rr.log(
                f"{target.entity_root}/metadata",
                self.rr.TextDocument(
                    json.dumps(compact_ase_atek_identifiers(target.metadata), indent=2, sort_keys=True),
                    media_type="application/json",
                ),
                static=True,
            )

    def _log_step(self, step: "_RolloutStepPayload") -> None:
        candidates = [candidate for candidate in step.candidates if self._candidate_layer_included(candidate)]
        camera_candidates = list(candidates)
        included_row_ids = {candidate.row_id for candidate in camera_candidates}
        if self.config.rollout_layers.selected_depth.included:
            camera_candidates.extend(
                candidate
                for candidate in step.candidates
                if candidate.selected and candidate.row_id not in included_row_ids
            )
        for candidate in camera_candidates:
            self._log_candidate_camera(candidate)
            self._log_selected_depth_representation(candidate)
        for candidate in candidates:
            self._log_candidate_center(candidate)
        self._log_candidate_group_centers(step, candidates=candidates)
        if self.config.rollout_layers.scalar_plots.included:
            self.rr.log(ENTITY_ROLLOUT_VALID_COUNT, self.rr.Scalars(float(step.valid_candidate_count)))
            self.rr.log(
                ENTITY_ROLLOUT_SELECTED_PROBABILITY,
                self.rr.Scalars(_finite_or_zero(step.selected_probability)),
            )
            self.rr.log(
                ENTITY_ROLLOUT_SELECTED_TARGET_RRI,
                self.rr.Scalars(_finite_or_zero(step.selected_target_rri)),
            )
            self.rr.log(
                ENTITY_ROLLOUT_SELECTED_TARGET_ROOT_GAIN,
                self.rr.Scalars(_finite_or_zero(step.selected_target_root_gain)),
            )
            self.rr.log(ENTITY_ROLLOUT_INVALID_FRACTION, self.rr.Scalars(_finite_or_zero(step.invalid_fraction)))
            self.rr.log(ENTITY_ROLLOUT_SELECTED_POSITION_ID, self.rr.Scalars(float(step.selected_position_id)))
        if self.config.rollout_layers.metadata.included:
            self.rr.log(
                step.metadata_entity,
                self.rr.TextDocument(
                    json.dumps(compact_ase_atek_identifiers(step.metadata), indent=2, sort_keys=True),
                    media_type="application/json",
                ),
            )

    def _candidate_layer_included(self, candidate: "_RolloutCandidatePayload") -> bool:
        """Return whether the candidate's validity class is recorded."""

        layer = (
            self.config.rollout_layers.rollout_candidates
            if candidate.valid
            else self.config.rollout_layers.invalid_candidates
        )
        return layer.included

    def _log_rollout_plots(self, *, reader: RolloutZarrStoreReader, selected_rows: StoredRollout) -> None:
        if not self.config.rollout_plots.enabled or not self.config.rollout_layers.scalar_plots.included:
            return
        plot_rows = _resolve_plot_rollout_rows(
            reader,
            selected_rows=selected_rows,
            branch_scope=self.config.rollout_plots.branch_scope,
        )
        for branch_order, rows in enumerate(plot_rows):
            branch = _branch_plot_descriptor(rows=rows, selected_row_id=selected_rows.rollout_row_id)
            self._log_branch_series_descriptors(branch=branch, branch_order=branch_order)
            for order, stored_step in enumerate(rollout_steps(reader, rows)):
                self._set_rollout_step_time(order)
                step = _plot_step_payload(
                    stored_step,
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

    def _log_candidate_group_centers(
        self,
        step: "_RolloutStepPayload",
        *,
        candidates: list["_RolloutCandidatePayload"],
    ) -> None:
        """Log low-cardinality candidate center groups for fast Rerun filtering."""

        group_specs = (
            ("position_family", "position_mode_name"),
            ("invalid_reason", "primary_invalid_reason_name"),
        )
        for group_name, attr_name in group_specs:
            grouped: dict[str, list[_RolloutCandidatePayload]] = {}
            for candidate in candidates:
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
        if candidate.selected_depth is None or not self.config.rollout_layers.selected_depth.included:
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

    def _log_selected_path(self, *, rows: StoredRollout, selected_path: list[list[float]]) -> None:
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
    valid: bool
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


def _resolve_plot_rollout_rows(
    reader: RolloutZarrStoreReader,
    *,
    selected_rows: StoredRollout,
    branch_scope: str,
) -> list[StoredRollout]:
    """Return rollout rows included in branch-aware scalar plots."""

    if branch_scope == "selected":
        return [selected_rows]
    if branch_scope != "same_source_target":
        raise ValueError(f"Unsupported rollout plot branch_scope={branch_scope!r}.")

    source_ids = np.asarray(reader.array("rollouts/source_row_id"), dtype=np.int64).reshape(-1)
    target_ids = np.asarray(reader.array("rollouts/target_row_id"), dtype=np.int64).reshape(-1)
    positions = np.flatnonzero(
        (source_ids == selected_rows.source_row_id) & (target_ids == selected_rows.target_row_id)
    )
    rows = [rollout_at(reader, int(position)) for position in positions.tolist()]
    if not rows:
        return [selected_rows]
    rows.sort(key=lambda value: (value.rollout_row_id != selected_rows.rollout_row_id, value.rollout_row_id))
    return rows


def _branch_plot_descriptor(
    *,
    rows: StoredRollout,
    selected_row_id: int,
) -> _RolloutBranchPlot:
    policy = rows.policy or None
    selected = rows.rollout_row_id == selected_row_id
    suffix = (
        f"{_safe_entity_token(policy or 'unknown_policy')}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}"
    )
    label = f"{policy or 'unknown'} chain={rows.chain_id} row={rows.rollout_row_id}"
    if selected:
        label = f"selected | {label}"
    return _RolloutBranchPlot(
        rollout_row_id=rows.rollout_row_id,
        rollout_index=rows.row_position,
        selected=selected,
        label=label,
        rri_root=f"{ENTITY_ROLLOUT_RRI_ROOT}/{suffix}",
        diagnostics_root=f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/{suffix}",
    )


def _step_payload(
    reader: RolloutZarrStoreReader,
    *,
    rollout: StoredRollout,
    step: StoredStep,
    rollout_depths: "RerunInspectorRolloutDepthConfig",
    target_metadata: dict[str, Any] | None = None,
) -> _RolloutStepPayload:
    centers = _pose_centers(step.pose_world_cam)
    target_rri_ranks, target_rri_rank_total = _target_rri_ranks(
        target_rri=step.target_rri,
        valid_mask=step.actor_action_mask,
        shell_indices=step.shell_indices,
    )
    entropy = float(
        candidate_policy_entropy(
            torch.from_numpy(step.selection_probabilities),
            torch.from_numpy(step.actor_action_mask),
        ).item()
    )
    selected_depth: _SelectedDepthPayload | None = None
    selected_depth_warnings: list[str] = []
    if rollout_depths.enabled:
        stored_depth = selected_depth_for_step(reader, step)
        if not stored_depth.available:
            warning = stored_depth.warning or "selected_depth unavailable."
            if rollout_depths.require_selected_depth:
                raise ValueError(warning)
            selected_depth_warnings.append(warning)
        else:
            assert stored_depth.depth_m is not None
            assert stored_depth.valid_mask is not None
            assert stored_depth.focal_px is not None
            assert stored_depth.principal_point_px is not None
            assert stored_depth.image_size_hw is not None
            assert stored_depth.candidate_row_id is not None
            selected_depth = _SelectedDepthPayload(
                step_row_id=stored_depth.step_row_id,
                candidate_row_id=stored_depth.candidate_row_id,
                depth_m=stored_depth.depth_m,
                valid_mask=stored_depth.valid_mask,
                focal_px=stored_depth.focal_px,
                principal_point_px=stored_depth.principal_point_px,
                image_size_hw=stored_depth.image_size_hw,
            )
    selected_local = step.selected_local_index
    candidate_payloads = _candidate_payloads(
        candidate_row_ids=step.candidate_row_ids,
        rollout_row_id=rollout.rollout_row_id,
        chain_id=rollout.chain_id,
        step_row_id=step.step_row_id,
        shell_indices=step.shell_indices,
        compact_valid=step.compact_valid_indices,
        valid=step.actor_action_mask,
        selected=step.selected_mask,
        step_index=step.step_index,
        poses=step.pose_world_cam,
        centers=centers,
        target_rri=step.target_rri,
        target_root_gain=step.target_root_gain,
        target_rri_ranks=target_rri_ranks,
        target_rri_rank_total=target_rri_rank_total,
        probabilities=step.selection_probabilities,
        mixture_names=step.mixture_names,
        sampler_probabilities=step.sampler_probabilities,
        position_ids=step.position_ids,
        position_names=step.position_names,
        mesh_distance_m=step.mesh_distance_m,
        path_min_clearance_m=step.path_min_clearance_m,
        motion_step_length_m=step.motion_step_length_m,
        target_distance_m=step.target_distance_m,
        primary_reason_names=step.primary_invalid_reason_names,
        selected_depth=selected_depth,
    )
    metadata = {
        "rollout_row_id": rollout.rollout_row_id,
        "chain_id": rollout.chain_id,
        "step_row_id": step.step_row_id,
        "step_index": step.step_index,
        "selected_candidate_row_id": step.selected_candidate_row_id,
        "num_candidates": step.num_candidates,
        "num_valid_candidates": step.num_valid_candidates,
        "selected_local_index": selected_local,
        "selected_shell_index": int(step.shell_indices[selected_local]) if selected_local >= 0 else None,
        "selected_probability": float(step.selection_probabilities[selected_local]) if selected_local >= 0 else None,
        "selected_target_rri": float(step.target_rri[selected_local]) if selected_local >= 0 else None,
        "selected_target_root_gain": float(step.target_root_gain[selected_local]) if selected_local >= 0 else None,
        "selected_position_id": int(step.position_ids[selected_local]) if selected_local >= 0 else -1,
        "selected_position_family": str(step.position_names[selected_local]) if selected_local >= 0 else "unknown",
        "selection_entropy": float(entropy) if selected_local >= 0 else None,
        "target_rri_rank": int(target_rri_ranks[selected_local]) if selected_local >= 0 else -1,
        "target_rri_rank_total": int(target_rri_rank_total),
        "target_rri_rank_semantics": _TARGET_RRI_RANK_SEMANTICS,
        "invalid_candidate_count": int((~step.actor_action_mask).sum()),
        "invalid_fraction": float((~step.actor_action_mask).sum()) / float(max(step.actor_action_mask.shape[0], 1)),
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
        "q_h": _q_h_metadata(reader, step_row_id=step.step_row_id),
    }
    return _RolloutStepPayload(
        rollout_row_id=rollout.rollout_row_id,
        chain_id=rollout.chain_id,
        step_row_id=step.step_row_id,
        step_index=step.step_index,
        step_entity=_rollout_step_entity(
            rollout_row_id=rollout.rollout_row_id,
            chain_id=rollout.chain_id,
            step_index=step.step_index,
        ),
        metadata_entity=_rollout_step_metadata_entity(
            rollout_row_id=rollout.rollout_row_id,
            chain_id=rollout.chain_id,
            step_index=step.step_index,
        ),
        candidates=candidate_payloads,
        selected_center=centers[selected_local] if selected_local >= 0 else None,
        valid_candidate_count=step.num_valid_candidates,
        selected_probability=float(step.selection_probabilities[selected_local])
        if selected_local >= 0
        else float("nan"),
        selected_target_rri=float(step.target_rri[selected_local]) if selected_local >= 0 else float("nan"),
        selected_target_root_gain=float(step.target_root_gain[selected_local]) if selected_local >= 0 else float("nan"),
        selected_position_id=int(step.position_ids[selected_local]) if selected_local >= 0 else -1,
        invalid_fraction=float((~step.actor_action_mask).sum()) / float(max(step.actor_action_mask.shape[0], 1)),
        metadata=metadata,
    )


def _plot_step_payload(
    step: StoredStep,
    *,
    candidate_top_k: int,
) -> _RolloutPlotStep:
    entropy = float(
        candidate_policy_entropy(
            torch.from_numpy(step.selection_probabilities),
            torch.from_numpy(step.actor_action_mask),
        ).item()
    )
    summary = _candidate_rri_summary(
        target_rri=step.target_rri,
        scene_rri=step.scene_rri,
        probabilities=step.selection_probabilities,
        entropy=entropy,
        valid_mask=step.actor_action_mask,
        selected_mask=step.selected_mask,
        top_k=candidate_top_k,
    )
    return _RolloutPlotStep(
        step_row_id=step.step_row_id,
        cumulative_target_rri=step.cumulative_target_rri,
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


def _rollout_root_path(rows: StoredRollout) -> list[list[float]]:
    """Return the selected-path seed point in the displayed world frame."""

    return [_pose_centers(rows.root_pose_world.reshape(1, 12))[0].tolist()]


def _rollout_context_config(config: "RerunOfflineInspectorConfig") -> "RerunOfflineInspectorConfig":
    """Project rollout layer policy onto the existing offline-context logger."""

    cfg = config.model_copy(deep=True)
    layers = cfg.rollout_layers
    primitives = cfg.primitives
    primitives.log_semidense = layers.actor_context.included
    primitives.log_detected_obbs = layers.actor_context.included
    primitives.log_efm_voxels = layers.actor_context.included
    primitives.log_reference_pose = layers.oracle_mesh_gt.included
    primitives.log_gt_mesh = layers.oracle_mesh_gt.included
    primitives.log_gt_obbs = layers.oracle_mesh_gt.included
    primitives.log_gt_trajectory = layers.oracle_mesh_gt.included
    primitives.log_rgb_keyframes = layers.rgb_depth_context.included
    primitives.log_depth_keyframes = layers.rgb_depth_context.included
    primitives.log_candidate_depths = layers.rgb_depth_context.included
    include_candidates = layers.rollout_candidates.included or layers.invalid_candidates.included
    primitives.log_candidate_frusta = include_candidates
    primitives.log_candidate_centers = layers.rollout_candidates.included
    primitives.log_candidate_points = False
    primitives.log_metadata = layers.metadata.included
    if layers.rollout_candidates.included and not layers.invalid_candidates.included:
        cfg.candidate.subset_mode = "valid_only"
    elif layers.invalid_candidates.included and not layers.rollout_candidates.included:
        cfg.candidate.subset_mode = "invalid_only"
    else:
        cfg.candidate.subset_mode = "all"
    return cfg


def _rollout_context_is_included(config: "RerunOfflineInspectorConfig") -> bool:
    """Return whether the projected offline logger has any entity to produce."""

    primitives = config.primitives
    return any(
        (
            primitives.log_semidense,
            primitives.log_reference_pose,
            primitives.log_candidate_frusta,
            primitives.log_candidate_centers,
            primitives.log_candidate_depths,
            primitives.log_gt_mesh,
            primitives.log_gt_obbs,
            primitives.log_detected_obbs,
            primitives.log_gt_trajectory,
            primitives.log_rgb_keyframes,
            primitives.log_depth_keyframes,
            primitives.log_efm_voxels,
            primitives.log_metadata,
        )
    )


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


def _rollout_layer_hidden_paths(
    *,
    config: "RerunOfflineInspectorConfig",
    rows: StoredRollout,
    steps: tuple[StoredStep, ...],
) -> tuple[str, ...]:
    """Return exact included-but-hidden entity roots for the resolved blueprint."""

    layers = config.rollout_layers
    hidden: list[str] = []

    def add_if_hidden(layer: Any, *paths: str) -> None:
        if layer.included and not layer.visible:
            hidden.extend(paths)

    add_if_hidden(layers.actor_context, "world/ase/semidense", "world/efm")
    add_if_hidden(
        layers.oracle_mesh_gt,
        "world/gt",
        "world/ase/reference",
        "world/ase/trajectory",
    )
    add_if_hidden(layers.rgb_depth_context, "world/ase/cameras")
    chain_entity = _rollout_chain_entity(rollout_row_id=rows.rollout_row_id, chain_id=rows.chain_id)
    add_if_hidden(layers.target_overlay, f"{chain_entity}/target")
    add_if_hidden(layers.selected_path, f"{chain_entity}/selected_path")
    for step in steps:
        step_entity = _rollout_step_entity(
            rollout_row_id=rows.rollout_row_id,
            chain_id=rows.chain_id,
            step_index=step.step_index,
        )
        add_if_hidden(layers.rollout_candidates, f"{step_entity}/selected", f"{step_entity}/valid")
        add_if_hidden(layers.invalid_candidates, f"{step_entity}/invalid")
        if (layers.rollout_candidates.included or layers.invalid_candidates.included) and not (
            layers.rollout_candidates.visible or layers.invalid_candidates.visible
        ):
            hidden.append(f"{step_entity}/groups")
        if step.selected_local_index >= 0:
            selected_shell_index = int(step.shell_indices[step.selected_local_index])
            selected_camera = f"{step_entity}/selected/candidate_shell_{selected_shell_index:03d}/camera"
            add_if_hidden(layers.selected_depth, f"{selected_camera}/depth", f"{selected_camera}/points")
    return tuple(hidden)


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
    mixture_names: NDArray[Any],
    sampler_probabilities: NDArray[Any],
    position_ids: NDArray[Any],
    position_names: NDArray[Any],
    mesh_distance_m: NDArray[Any],
    path_min_clearance_m: NDArray[Any],
    motion_step_length_m: NDArray[Any],
    target_distance_m: NDArray[Any],
    primary_reason_names: NDArray[Any],
    selected_depth: _SelectedDepthPayload | None,
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
        mixture_names,
        sampler_probabilities,
        position_ids,
        position_names,
        mesh_distance_m,
        path_min_clearance_m,
        motion_step_length_m,
        target_distance_m,
        primary_reason_names,
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
            mixture_name,
            sampler_probability,
            position_id,
            position_name,
            mesh_distance,
            path_clearance,
            motion_step_length,
            target_distance,
            primary_reason_name,
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
                valid=bool(is_valid),
                pose=np.asarray(pose, dtype=np.float32).reshape(12),
                center=np.asarray(center, dtype=np.float32).reshape(3),
                position_id=int(position_id),
                target_rri=float(rri),
                target_root_gain=float(root_gain),
                target_rri_rank=int(rri_rank),
                target_rri_rank_total=int(target_rri_rank_total),
                probability=float(prob),
                mixture_component_name=str(mixture_name),
                position_mode_name=str(position_name),
                sampler_probability=float(sampler_probability),
                mesh_distance_m=float(mesh_distance),
                path_min_clearance_m=float(path_clearance),
                motion_step_length_m=float(motion_step_length),
                target_distance_m=float(target_distance),
                primary_invalid_reason_name=str(primary_reason_name),
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
    *,
    rows: StoredRollout,
    fallback: RerunInspectorSelectionConfig,
) -> RerunInspectorSelectionConfig | None:
    if fallback.sample_key or (fallback.scene_id and fallback.snippet_id):
        return fallback.model_copy(deep=True)

    scene_id = rows.scene or None
    snippet_id = rows.snippet or None
    if scene_id and snippet_id:
        return fallback.model_copy(
            deep=True,
            update={"scene_id": scene_id, "snippet_id": compact_ase_atek_sample_id(snippet_id), "sample_key": None},
        )
    if fallback.rollout_context_mode == "required":
        return fallback.model_copy(deep=True)
    return None


def _dictionary_preview(*, rows: StoredRollout, target: _RolloutTargetPayload) -> dict[str, list[str]]:
    target_id = str(target.metadata.get("target_id") or "")
    return compact_ase_atek_identifiers(
        {
            "scene": [rows.scene] if rows.scene else [],
            "snippet": [rows.snippet] if rows.snippet else [],
            "rollout": [str(rows.rollout_row_id)],
            "target": [target_id] if target_id else [],
            "policy": [rows.policy] if rows.policy else [],
        }
    )


def _rollout_target_payload(reader: RolloutZarrStoreReader, *, rows: StoredRollout) -> _RolloutTargetPayload:
    """Build the visible rollout-target overlay payload from factual target tables."""

    target_row_id = rows.target_row_id
    target = target_by_id(reader, target_row_id)
    entity_root = _rollout_target_entity(rollout_row_id=rows.rollout_row_id, chain_id=rows.chain_id)

    warnings: list[str] = []
    if target is None:
        warnings.append(f"rollout target_row_id={target_row_id} does not resolve to exactly one targets/ row.")
        return _RolloutTargetPayload(
            entity_root=entity_root,
            metadata={
                "rollout_row_id": rows.rollout_row_id,
                "chain_id": rows.chain_id,
                "source_row_id": rows.source_row_id,
                "scene_id": rows.scene or None,
                "snippet_id": compact_ase_atek_sample_id(rows.snippet) if rows.snippet else None,
                "target_row_id": target_row_id,
                "warnings": warnings,
            },
            warnings=warnings,
            center=None,
            extents=None,
            pose_world_object=None,
        )

    target_id = target.target_id
    matched_gt_target_id = target.matched_gt_target_id
    for array_name, identifier in (("target_id", target_id), ("matched_gt_target_id", matched_gt_target_id)):
        if _target_identifier_mentions_other_snippet(identifier=identifier, snippet=rows.snippet):
            warnings.append(
                f"targets/{array_name}={compact_ase_atek_sample_id(identifier)!r} "
                f"does not match rollout snippet_id={compact_ase_atek_sample_id(rows.snippet)!r}; "
                "the store is stale or target rows collided."
            )

    center = target.center_world
    extents = target.extents
    pose = target.pose_world_object

    def optional(value: float) -> float | None:
        return float(value) if np.isfinite(value) else None

    metadata = {
        "rollout_row_id": rows.rollout_row_id,
        "chain_id": rows.chain_id,
        "source_row_id": rows.source_row_id,
        "scene_id": rows.scene or None,
        "snippet_id": compact_ase_atek_sample_id(rows.snippet) if rows.snippet else None,
        "target_row_id": target_row_id,
        "target_id": target_id,
        "target_source": target.source,
        "target_source_index": target.source_index,
        "target_sem_id": target.sem_id,
        "target_inst_id": target.inst_id,
        "target_class_name": target.class_name,
        "target_confidence": target.confidence,
        "target_projected_area_pixels": optional(target.projected_area_pixels),
        "target_projected_area_fraction": optional(target.projected_area_fraction),
        "target_semidense_support_count": optional(target.semidense_support_count),
        "target_evl_support_count": optional(target.evl_support_count),
        "target_effective_support_count": optional(target.effective_support_count),
        "target_visibility_score": optional(target.visibility_score),
        "target_support_score": optional(target.support_score),
        "target_deficit_score": optional(target.deficit_score),
        "target_center_world": center.astype(float).tolist(),
        "target_extents": extents.astype(float).tolist(),
        "matched_gt_target_row_id": target.matched_gt_target_row_id,
        "matched_gt_target_id": matched_gt_target_id,
        "gt_match_status": target.gt_match_status,
        "gt_match_iou": target.gt_match_iou,
        "gt_match_score": target.gt_match_score,
        "target_selection_rank": target.selection_rank,
        "target_selection_score": target.selection_score,
        "target_selection_probability": target.selection_probability,
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
) -> StoredRollout:
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
    "run_rollout_zarr_inspector",
]
