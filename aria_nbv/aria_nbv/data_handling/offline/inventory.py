"""Reusable visual-inventory diagnostics for immutable VIN offline samples.

The collector in this module validates the app-facing
``VinOfflineSample`` object built by `VinOfflineDataset` and records
which optional visual payloads are available for downstream diagnostics.
Required model and oracle fields raise actionable errors in strict mode, while
missing optional rich visual blocks are surfaced as warnings.
"""

# Deferred typing cleanup: repo:.agents/todos.toml#todo-097

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
from torch import Tensor

from ..identifiers import compact_ase_atek_sample_id
from .dataset import VinOfflineSample


class OfflineVisualInventoryError(ValueError):
    """Raised when an offline sample is missing required visual-inventory fields."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        """Create an error with all collected inventory failures.

        Args:
            errors: Actionable field-level validation failures.
        """

        self.errors = tuple(errors)
        super().__init__("Offline visual inventory validation failed:\n- " + "\n- ".join(self.errors))


@dataclass(slots=True)
class OfflineVisualInventory:
    """Summary of required and optional visual payloads for one offline sample."""

    sample_key: str | None
    """Stable dataset sample key."""

    sample_index: int | None
    """Global zero-based sample index."""

    split: str | None
    """Dataset split membership."""

    scene_id: str | None
    """ASE scene identifier."""

    snippet_id: str | None
    """ASE snippet identifier."""

    candidate_count: int | None
    """Number of valid prefix candidates."""

    candidate_width: int | None
    """Stored candidate tensor width, derived from ``oracle.rri``."""

    candidate_valid_mask: Tensor | None
    """Boolean prefix mask over ``candidate_width`` candidates."""

    accuracy_delta: Tensor | None
    """Per-candidate ``pm_acc_before - pm_acc_after`` tensor."""

    completeness_delta: Tensor | None
    """Per-candidate ``pm_comp_before - pm_comp_after`` tensor."""

    has_candidates: bool
    """Whether the optional candidate-sampling payload is present."""

    has_candidate_mask: bool
    """Whether the candidate payload exposes ``mask_valid``."""

    has_candidate_invalid_reasons: bool
    """Whether candidate rule masks/invalid reasons are present."""

    has_depths: bool
    """Whether cached candidate depth maps are present."""

    has_candidate_pcs: bool
    """Whether cached candidate point clouds are present."""

    has_semidense_points: bool
    """Whether candidate point-cloud diagnostics include semidense points."""

    has_candidate_points: bool
    """Whether candidate point-cloud diagnostics include candidate points."""

    has_gt_mesh: bool
    """Whether a live EFM snippet exposes a GT mesh."""

    has_gt_obbs: bool
    """Whether a live EFM snippet exposes GT/snippet OBBs."""

    has_detected_obbs: bool
    """Whether compact detected OBBs are available."""

    has_trajectory: bool
    """Whether trajectory metadata is available."""

    has_rgb_keyframes: bool
    """Whether a live EFM RGB camera stream is available for keyframe logging."""

    has_depth_keyframes: bool
    """Whether a live EFM RGB depth stream is available for keyframe logging."""

    has_backbone_voxel_extent: bool
    """Whether cached backbone diagnostics include a voxel extent."""

    has_backbone_points: bool
    """Whether cached backbone diagnostics include world-space voxel points."""

    errors: tuple[str, ...] = ()
    """Required-field validation errors collected when ``strict=False``."""

    warnings: tuple[str, ...] = ()
    """Optional-field warnings and non-fatal diagnostic notes."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Shape and count metadata useful for display panels."""

    @property
    def ok(self) -> bool:
        """Return whether all required checks passed."""

        return not self.errors


def _missing(path: str, errors: list[str]) -> None:
    errors.append(f"Missing required field `{path}`; rebuild or reload the immutable VIN offline sample.")


def _invalid(path: str, reason: str, errors: list[str]) -> None:
    errors.append(f"Invalid required field `{path}`: {reason}.")


def _get_required(owner: object | None, attr: str, path: str, errors: list[str]) -> object | None:
    if owner is None or not hasattr(owner, attr):
        _missing(path, errors)
        return None
    value = getattr(owner, attr)
    if value is None:
        _missing(path, errors)
        return None
    return value


def _as_tensor(value: object | None, path: str, errors: list[str]) -> Tensor | None:
    if value is None:
        _missing(path, errors)
        return None
    if torch.is_tensor(value):
        return value
    tensor_method = getattr(value, "tensor", None)
    if callable(tensor_method):
        tensor = tensor_method()
        if torch.is_tensor(tensor):
            return tensor
    _invalid(path, f"expected a tensor-like value, got {type(value).__name__}", errors)
    return None


def _finite_prefix(values: Tensor, *, count: int, path: str, errors: list[str]) -> None:
    flat = values.reshape(-1)
    if count > flat.numel():
        _invalid(path, f"candidate_count={count} exceeds flattened tensor length {flat.numel()}", errors)
        return
    if count > 0 and not bool(torch.isfinite(flat[:count]).all().item()):
        _invalid(path, "valid prefix contains non-finite values", errors)


def _shape_metadata(metadata: dict[str, Any], name: str, value: object | None) -> None:
    if torch.is_tensor(value):
        metadata[f"{name}.shape"] = tuple(int(dim) for dim in value.shape)


def _first_length(lengths: Tensor, errors: list[str]) -> int | None:
    if lengths.numel() == 0:
        _invalid("sample.vin_snippet.lengths", "expected at least one length value", errors)
        return None
    value = int(lengths.reshape(-1)[0].item())
    if value <= 0:
        _invalid("sample.vin_snippet.lengths", f"expected a positive semidense length, got {value}", errors)
        return None
    return value


def _validate_vin_snippet(vin_snippet: object | None, errors: list[str], metadata: dict[str, Any]) -> None:
    points = _as_tensor(
        _get_required(vin_snippet, "points_world", "sample.vin_snippet.points_world", errors),
        "sample.vin_snippet.points_world",
        errors,
    )
    lengths = _as_tensor(
        _get_required(vin_snippet, "lengths", "sample.vin_snippet.lengths", errors),
        "sample.vin_snippet.lengths",
        errors,
    )
    _shape_metadata(metadata, "vin_snippet.points_world", points)
    _shape_metadata(metadata, "vin_snippet.lengths", lengths)
    if points is None or lengths is None:
        return
    if points.ndim < 2:
        _invalid("sample.vin_snippet.points_world", f"expected at least 2 dims, got {tuple(points.shape)}", errors)
        return
    if int(points.shape[-1]) < 3:
        _invalid("sample.vin_snippet.points_world", "expected XYZ channels in the last dimension", errors)
        return
    length = _first_length(lengths, errors)
    if length is None:
        return
    point_capacity = int(points.shape[-2])
    if length > point_capacity:
        _invalid(
            "sample.vin_snippet.lengths",
            f"length {length} exceeds points capacity {point_capacity}",
            errors,
        )
        return
    valid_xyz = points.narrow(dim=-2, start=0, length=length)[..., :3]
    metadata["vin_snippet.valid_semidense_points"] = length
    if not bool(torch.isfinite(valid_xyz).all().item()):
        _invalid("sample.vin_snippet.points_world", "valid semidense XYZ prefix contains non-finite values", errors)


def _validate_pose(value: object | None, path: str, errors: list[str], metadata: dict[str, Any]) -> Tensor | None:
    tensor = _as_tensor(value, path, errors)
    _shape_metadata(metadata, path, tensor)
    if tensor is not None and not bool(torch.isfinite(tensor).all().item()):
        _invalid(path, "pose tensor contains non-finite values", errors)
    return tensor


def _validate_p3d_cameras(cameras: object | None, errors: list[str], metadata: dict[str, Any]) -> None:
    if cameras is None:
        _missing("sample.oracle.p3d_cameras", errors)
        return
    for name in ("R", "T", "focal_length", "principal_point", "image_size"):
        value = getattr(cameras, name, None)
        _shape_metadata(metadata, f"p3d_cameras.{name}", value)
        if torch.is_tensor(value) and not bool(torch.isfinite(value).all().item()):
            _invalid(f"sample.oracle.p3d_cameras.{name}", "camera parameter contains non-finite values", errors)


def _candidate_count(oracle: object | None, errors: list[str]) -> int | None:
    value = _get_required(oracle, "candidate_count", "sample.oracle.candidate_count", errors)
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        _invalid("sample.oracle.candidate_count", f"expected an integer, got {value!r}", errors)
        return None
    if count < 0:
        _invalid("sample.oracle.candidate_count", f"expected a non-negative value, got {count}", errors)
        return None
    return count


def _validate_oracle(
    oracle: object | None,
    errors: list[str],
    metadata: dict[str, Any],
) -> tuple[int | None, int | None, Tensor | None, Tensor | None, Tensor | None]:
    candidate_count = _candidate_count(oracle, errors)
    _validate_pose(
        _get_required(oracle, "reference_pose_world_rig", "sample.oracle.reference_pose_world_rig", errors),
        "sample.oracle.reference_pose_world_rig",
        errors,
        metadata,
    )
    candidate_poses = _validate_pose(
        _get_required(oracle, "candidate_poses_world_cam", "sample.oracle.candidate_poses_world_cam", errors),
        "sample.oracle.candidate_poses_world_cam",
        errors,
        metadata,
    )

    metric_tensors: dict[str, Tensor] = {}
    for name in (
        "rri",
        "pm_dist_before",
        "pm_dist_after",
        "pm_acc_before",
        "pm_acc_after",
        "pm_comp_before",
        "pm_comp_after",
    ):
        path = f"sample.oracle.{name}"
        tensor = _as_tensor(_get_required(oracle, name, path, errors), path, errors)
        _shape_metadata(metadata, path, tensor)
        if tensor is not None:
            metric_tensors[name] = tensor

    _validate_p3d_cameras(
        _get_required(oracle, "p3d_cameras", "sample.oracle.p3d_cameras", errors),
        errors,
        metadata,
    )

    rri = metric_tensors.get("rri")
    candidate_width = int(rri.shape[-1]) if rri is not None and rri.ndim > 0 else None
    if rri is not None and rri.ndim == 0:
        _invalid("sample.oracle.rri", "expected a candidate vector, got scalar", errors)
    if candidate_count is not None and candidate_width is not None:
        if candidate_count > candidate_width:
            _invalid(
                "sample.oracle.candidate_count",
                f"candidate_count={candidate_count} exceeds oracle.rri width {candidate_width}",
                errors,
            )
        for name, tensor in metric_tensors.items():
            if tensor.shape != rri.shape:
                _invalid(
                    f"sample.oracle.{name}",
                    f"shape {tuple(tensor.shape)} does not match rri {tuple(rri.shape)}",
                    errors,
                )
            _finite_prefix(
                tensor, count=min(candidate_count, candidate_width), path=f"sample.oracle.{name}", errors=errors
            )
        if candidate_poses is not None and candidate_poses.ndim > 0 and int(candidate_poses.shape[0]) < candidate_count:
            _invalid(
                "sample.oracle.candidate_poses_world_cam",
                f"pose count {int(candidate_poses.shape[0])} is smaller than candidate_count={candidate_count}",
                errors,
            )

    candidate_valid_mask = None
    accuracy_delta = None
    completeness_delta = None
    if candidate_count is not None and candidate_width is not None and rri is not None:
        candidate_valid_mask = torch.arange(candidate_width, device=rri.device) < min(candidate_count, candidate_width)
    if "pm_acc_before" in metric_tensors and "pm_acc_after" in metric_tensors:
        accuracy_delta = metric_tensors["pm_acc_before"] - metric_tensors["pm_acc_after"]
    if "pm_comp_before" in metric_tensors and "pm_comp_after" in metric_tensors:
        completeness_delta = metric_tensors["pm_comp_before"] - metric_tensors["pm_comp_after"]
    return candidate_count, candidate_width, candidate_valid_mask, accuracy_delta, completeness_delta


def _optional_inventory(sample: VinOfflineSample, warnings: list[str], metadata: dict[str, Any]) -> dict[str, bool]:
    candidates = sample.candidates
    has_candidates = candidates is not None
    has_candidate_mask = bool(candidates is not None and isinstance(candidates.mask_valid, torch.Tensor))
    masks = candidates.masks if candidates is not None else {}
    has_candidate_invalid_reasons = bool(masks)
    if not has_candidates:
        warnings.append("Optional candidate-sampling payload is missing.")
    elif not has_candidate_mask:
        warnings.append("Optional candidate payload does not expose `mask_valid`.")
    if has_candidates and not has_candidate_invalid_reasons:
        warnings.append("Optional candidate rule masks/invalid reasons are missing.")

    depths = sample.depths
    has_depths = depths is not None
    if depths is None:
        warnings.append("Optional cached candidate depths are missing.")
    else:
        _shape_metadata(metadata, "depths.depths", depths.depths)
        _shape_metadata(metadata, "depths.depths_valid_mask", depths.depths_valid_mask)

    candidate_pcs = sample.candidate_pcs
    has_candidate_pcs = candidate_pcs is not None
    if not has_candidate_pcs:
        warnings.append("Optional cached candidate point clouds are missing.")
    if candidate_pcs is not None:
        points = candidate_pcs.points
        semidense = candidate_pcs.semidense_points
        has_candidate_points = bool(points.numel() > 0)
        has_semidense_points = bool(semidense.numel() > 0)
        _shape_metadata(metadata, "candidate_pcs.points", points)
        _shape_metadata(metadata, "candidate_pcs.semidense_points", semidense)
    else:
        has_candidate_points = False
        has_semidense_points = False
        _shape_metadata(metadata, "candidate_pcs.points", None)
        _shape_metadata(metadata, "candidate_pcs.semidense_points", None)

    efm_snippet = sample.efm_snippet_view
    compact_gt_obbs = sample.gt_obbs
    compact_detected_obbs = sample.detected_obbs
    compact_trajectory = sample.trajectory
    backbone_out = sample.backbone_out
    has_gt_mesh = False
    has_gt_obbs = compact_gt_obbs is not None
    has_detected_obbs = compact_detected_obbs is not None or bool(
        backbone_out is not None and (backbone_out.obb_pred_viz is not None or backbone_out.obb_pred is not None)
    )
    has_trajectory = compact_trajectory is not None
    has_rgb_keyframes = False
    has_depth_keyframes = False
    if compact_gt_obbs is not None:
        _shape_metadata(metadata, "gt_obbs.obbs", compact_gt_obbs.obbs)
        _shape_metadata(metadata, "gt_obbs.probs", compact_gt_obbs.probs)
    if compact_detected_obbs is not None:
        _shape_metadata(metadata, "detected_obbs.obbs", compact_detected_obbs.obbs)
        _shape_metadata(metadata, "detected_obbs.probs", compact_detected_obbs.probs)
    if compact_trajectory is not None:
        _shape_metadata(metadata, "trajectory.time_ns", compact_trajectory.time_ns)
        _shape_metadata(metadata, "trajectory.gravity_in_world", compact_trajectory.gravity_in_world)
    if efm_snippet is None:
        warnings.append("Optional live EFM snippet is missing; GT mesh and OBBs were not inspected.")
    else:
        has_gt_mesh = has_gt_mesh or bool(efm_snippet.has_mesh or efm_snippet.mesh_verts is not None)
        has_gt_obbs = has_gt_obbs or efm_snippet.obbs is not None
        has_trajectory = True
        try:
            camera_rgb = efm_snippet.camera_rgb
            has_rgb_keyframes = bool(camera_rgb.images.numel() > 0)
            has_depth_keyframes = bool(camera_rgb.distance_m is not None and camera_rgb.distance_m.numel() > 0)
            _shape_metadata(metadata, "efm.rgb.images", camera_rgb.images)
            _shape_metadata(metadata, "efm.rgb.distance_m", camera_rgb.distance_m)
        except Exception as exc:
            warnings.append(f"Optional live RGB camera stream was not inspected: {exc}")

    backbone = sample.backbone_out
    if backbone is None:
        warnings.append("Optional cached backbone output is missing.")
    voxel_extent = backbone.voxel_extent if backbone is not None else None
    backbone_points = backbone.pts_world if backbone is not None else None
    has_backbone_voxel_extent = bool(voxel_extent is not None and voxel_extent.numel() > 0)
    has_backbone_points = bool(backbone_points is not None and backbone_points.numel() > 0)
    _shape_metadata(metadata, "backbone.voxel_extent", voxel_extent)
    _shape_metadata(metadata, "backbone.pts_world", backbone_points)

    return {
        "has_candidates": has_candidates,
        "has_candidate_mask": has_candidate_mask,
        "has_candidate_invalid_reasons": has_candidate_invalid_reasons,
        "has_depths": has_depths,
        "has_candidate_pcs": has_candidate_pcs,
        "has_semidense_points": has_semidense_points,
        "has_candidate_points": has_candidate_points,
        "has_gt_mesh": has_gt_mesh,
        "has_gt_obbs": has_gt_obbs,
        "has_detected_obbs": has_detected_obbs,
        "has_trajectory": has_trajectory,
        "has_rgb_keyframes": has_rgb_keyframes,
        "has_depth_keyframes": has_depth_keyframes,
        "has_backbone_voxel_extent": has_backbone_voxel_extent,
        "has_backbone_points": has_backbone_points,
    }


def _sample_metadata(
    sample: object, errors: list[str]
) -> tuple[str | None, int | None, str | None, str | None, str | None]:
    sample_key_value = _get_required(sample, "sample_key", "sample.sample_key", errors)
    sample_key = sample_key_value if isinstance(sample_key_value, str) and sample_key_value else None
    if sample_key_value is not None and sample_key is None:
        _invalid("sample.sample_key", "expected a non-empty string", errors)

    sample_index_value = _get_required(sample, "sample_index", "sample.sample_index", errors)
    sample_index: int | None = None
    if sample_index_value is not None:
        try:
            sample_index = int(sample_index_value)
        except (TypeError, ValueError):
            _invalid("sample.sample_index", f"expected an integer, got {sample_index_value!r}", errors)
        else:
            if sample_index < 0:
                _invalid("sample.sample_index", f"expected a non-negative value, got {sample_index}", errors)

    split_value = _get_required(sample, "split", "sample.split", errors)
    split = split_value if isinstance(split_value, str) and split_value else None
    if split_value is not None and split is None:
        _invalid("sample.split", "expected a non-empty string", errors)

    scene_id_value = _get_required(sample, "scene_id", "sample.scene_id", errors)
    scene_id = scene_id_value if isinstance(scene_id_value, str) and scene_id_value else None
    if scene_id_value is not None and scene_id is None:
        _invalid("sample.scene_id", "expected a non-empty string", errors)

    snippet_id_value = _get_required(sample, "snippet_id", "sample.snippet_id", errors)
    snippet_id = snippet_id_value if isinstance(snippet_id_value, str) and snippet_id_value else None
    if snippet_id_value is not None and snippet_id is None:
        _invalid("sample.snippet_id", "expected a non-empty string", errors)
    return (
        compact_ase_atek_sample_id(sample_key) if sample_key is not None else None,
        sample_index,
        split,
        scene_id,
        compact_ase_atek_sample_id(snippet_id) if snippet_id is not None else None,
    )


def collect_offline_visual_inventory(sample: VinOfflineSample, *, strict: bool = True) -> OfflineVisualInventory:
    """Collect visual diagnostics for a ``VinOfflineSample``.

    Args:
        sample: Offline sample returned by ``VinOfflineDataset`` with
            ``return_format="sample"``.
        strict: If ``True``, raise `OfflineVisualInventoryError` when a
            required field is absent or invalid. Optional visual payloads are
            always represented as warnings instead of failures.

    Returns:
        Inventory summary with required metadata, derived masks/deltas, optional
        payload booleans, warnings, and shape metadata.
    """

    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    sample_key, sample_index, split, scene_id, snippet_id = _sample_metadata(sample, errors)
    vin_snippet = _get_required(sample, "vin_snippet", "sample.vin_snippet", errors)
    oracle = _get_required(sample, "oracle", "sample.oracle", errors)
    _validate_vin_snippet(vin_snippet, errors, metadata)
    candidate_count, candidate_width, candidate_valid_mask, accuracy_delta, completeness_delta = _validate_oracle(
        oracle,
        errors,
        metadata,
    )
    optional = _optional_inventory(sample, warnings, metadata)

    inventory = OfflineVisualInventory(
        sample_key=sample_key,
        sample_index=sample_index,
        split=split,
        scene_id=scene_id,
        snippet_id=snippet_id,
        candidate_count=candidate_count,
        candidate_width=candidate_width,
        candidate_valid_mask=candidate_valid_mask,
        accuracy_delta=accuracy_delta,
        completeness_delta=completeness_delta,
        errors=tuple(errors),
        warnings=tuple(warnings),
        metadata=metadata,
        **optional,
    )
    if strict and errors:
        raise OfflineVisualInventoryError(errors)
    return inventory


__all__ = [
    "OfflineVisualInventory",
    "OfflineVisualInventoryError",
    "collect_offline_visual_inventory",
]
