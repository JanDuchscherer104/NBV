"""Build lineage-preserving oracle evaluation point clouds for RRI scoring.

This module provides deterministic fusion, observed-prefix selection, and root
point-cloud construction. It separates actor-visible geometry from oracle-only
label geometry.
The thesis-core default builds the root evaluation point cloud from ASE RGB
ground-truth ray-distance depth frames, while semi-dense MPS points remain
available as actor input and as a legacy diagnostic stream.

Candidate rendering and matched GT mesh cropping live in adjacent rendering
and oracle surfaces. This module owns only the root evaluation stream and its
frame/time provenance; it does not decide candidate hard validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol

import torch
from efm3d.aria.obb import ObbTW
from efm3d.utils.depth import dist_im_to_point_cloud_im

from ..data_handling import EfmSnippetView
from .target_selection import (
    OracleTargetTask,
    TargetTaskIdentityStatus,
    _compact_obb_block,
    _valid_obb_data_with_source_indices,
    _world_obbs_for_sample,
)

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

    from ..data_handling.vin_store.dataset import VinOfflineSample

Tensor = torch.Tensor
CameraLabel = Literal["rgb", "slaml", "slamr"]


class OracleEvidenceInvalidReason(StrEnum):
    """Stable semantic reasons for expected Oracle evidence invalidity."""

    ROOT_DEPTH_MISSING = "root_depth_missing"
    ROOT_DEPTH_SHAPE_INVALID = "root_depth_shape_invalid"
    ROOT_OBSERVED_FRAMES_EMPTY = "root_observed_frames_empty"
    ROOT_EVAL_POINTS_EMPTY = "root_eval_points_empty"
    TARGET_GT_LABEL_INVALID = "target_gt_label_invalid"
    TARGET_GT_OBB_MISSING = "target_gt_obb_missing"
    TARGET_GT_ROW_MISSING = "target_gt_row_missing"
    TARGET_SCENE_MESH_EMPTY = "target_scene_mesh_empty"
    TARGET_MESH_CROP_EMPTY = "target_mesh_crop_empty"
    TARGET_CURRENT_SUPPORT_INSUFFICIENT = "target_current_support_insufficient"
    TARGET_EXTENT_EMPTY = "target_extent_empty"


class _OracleEvidenceError(ValueError):
    """Internal coded failure converted to a scorer-owned invalidity outcome."""

    def __init__(self, reason: OracleEvidenceInvalidReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class OracleRriState(Protocol):
    """Minimal actor/replay state consumed by Oracle RRI facades."""

    @property
    def root_pose_world(self) -> PoseTW:
        """Return the rollout root pose in world coordinates."""

    @property
    def root_time_ns(self) -> int | None:
        """Return the root timestamp when available."""

    @property
    def root_trajectory_index(self) -> int | None:
        """Return the root trajectory row when available."""

    @property
    def root_frame_index(self) -> int | None:
        """Return the root frame row when available."""

    def accumulated_points_world(self) -> Tensor:
        """Return selected-history point clouds in world coordinates."""

    def root_metric(self, name: str) -> float | None:
        """Return the first finite persisted metric with ``name``."""


class RriEvaluationPointCloudSource(StrEnum):
    """Select the geometry source used for the root oracle evaluation cloud."""

    ASE_GT_DEPTH_ROOT = "ase_gt_depth_root"
    """Observed-prefix ASE GT ray-distance depth, used by thesis target labels."""
    LEGACY_SEMIDENSE_ROOT = "legacy_semidense_root"
    """MPS semi-dense world points, retained for actor/legacy diagnostics only."""
    RENDERED_LOGGED_DEPTH_ROOT = "rendered_logged_depth_root"
    """Reserved rendered-root parity ablation; current construction raises."""


class RriRewardMode(StrEnum):
    """Choose the normalization used for a valid rollout candidate's oracle gain."""

    ROOT_NORMALIZED_GAIN = "root_normalized_gain"
    """Normalize every step by the fixed rollout-root error for telescoping returns."""
    STATE_RELATIVE_RRI = "state_relative_rri"
    """Normalize one-step improvement by the current-state error for diagnostics."""


@dataclass(frozen=True, slots=True)
class RootEvalPointCloud:
    """Root oracle evaluation points with reproducible source lineage.

    The points are label/evaluation geometry, even when the selected source is
    also available to the actor. Frame and trajectory indices preserve exactly
    which observed prefix was unprojected into the world frame.
    """

    points_world: Tensor
    """``Tensor["P 3", float32]`` fused evaluation points in world frame, metres."""
    source: RriEvaluationPointCloudSource
    """Root evaluation point-cloud source."""
    frame_indices: Tensor
    """``Tensor["F_eval", int64]`` camera/depth frame indices used by the ASE root."""
    trajectory_indices: Tensor
    """``Tensor["F_eval", int64]`` nearest trajectory rows used for world transforms."""
    root_time_ns: int | None
    """Root timestamp in nanoseconds used for observed-prefix filtering, if available."""
    root_trajectory_index: int | None
    """Root trajectory row used for observed-prefix filtering, if available."""
    root_frame_index: int | None
    """Root camera frame index used for observed-prefix filtering, if available."""
    depth_convention: str
    """Depth convention for lineage, e.g. ``ray_distance_m``."""
    camera_label: str
    """Camera stream used to build ``points_world``."""
    stride: int
    """Positive pixel stride applied after ray-distance unprojection."""
    far_m: float | None
    """Maximum retained ray distance in metres, if configured."""
    voxel_size_m: float
    """Voxel size used by canonical fusion; 0 disables voxel fusion."""
    max_points: int | None
    """Maximum retained points after deterministic fusion/downsampling."""


def canonical_fuse_points(
    points: Tensor,
    *,
    voxel_size_m: float = 0.0,
    max_points: int | None = None,
) -> Tensor:
    """Filter, deterministically voxel-fuse, and cap metric-frame points.

    Args:
        points ``Tensor["N D", float32]``: Points in one metric coordinate
            frame. Only the first three coordinates are retained.
        voxel_size_m: Edge length for mean voxel fusion. Values ``<=0`` disable
            voxel aggregation.
        max_points: Optional deterministic cap after voxel fusion.

    Returns:
        ``Tensor["K 3", float32]`` finite points in the input frame and units.
        Voxel representatives are arithmetic means, and deterministic capping
        retains evenly spaced row indices.
    """

    pts = points.reshape(-1, points.shape[-1])[..., :3]
    if pts.numel() == 0:
        return pts.reshape(0, 3)
    pts = pts[torch.isfinite(pts).all(dim=-1)]
    if pts.numel() == 0:
        return pts.reshape(0, 3)

    voxel = float(voxel_size_m)
    if voxel > 0.0:
        keys = torch.floor(pts / voxel).to(dtype=torch.int64)
        _, inverse = torch.unique(keys, dim=0, sorted=True, return_inverse=True)
        fused = torch.zeros((int(inverse.max().item()) + 1, 3), device=pts.device, dtype=pts.dtype)
        fused.scatter_add_(0, inverse[:, None].expand(-1, 3), pts)
        counts = torch.bincount(inverse, minlength=fused.shape[0]).to(device=pts.device, dtype=pts.dtype)
        pts = fused / counts.clamp_min(1).unsqueeze(1)

    if max_points is not None and pts.shape[0] > int(max_points):
        count = int(max_points)
        indices = torch.div(
            torch.arange(count, device=pts.device, dtype=torch.long) * pts.shape[0],
            count,
            rounding_mode="floor",
        )
        pts = pts[indices]
    return pts


def _root_evidence_token(
    root_pose_world: object,
    *,
    root_time_ns: int | None,
    root_trajectory_index: int | None,
    root_frame_index: int | None,
) -> tuple[float, ...]:
    """Return a stable cache key for root-bound Oracle evidence."""

    pose = root_pose_world.tensor().detach().cpu().reshape(-1)  # type: ignore[attr-defined, no-untyped-call]
    return (
        *(round(float(value), 6) for value in pose.tolist()),
        float(-1 if root_time_ns is None else root_time_ns),
        float(-1 if root_trajectory_index is None else root_trajectory_index),
        float(-1 if root_frame_index is None else root_frame_index),
    )


def _eval_depth_far_m(
    *,
    source: RriEvaluationPointCloudSource,
    configured: float | None,
    depth_renderer: object,
) -> float | None:
    """Resolve the Oracle evidence far plane from explicit or renderer config."""

    if configured is not None or source is not RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT:
        return configured
    renderer = getattr(depth_renderer, "renderer", None)
    zfar = getattr(getattr(renderer, "config", None), "zfar", None)
    return 20.0 if zfar is None else float(zfar)


def target_gt_obb_world(task: OracleTargetTask, sample: "VinOfflineSample") -> ObbTW:
    """Resolve an Oracle-selected target's matched GT OBB in world coordinates."""

    if task.identity_status != TargetTaskIdentityStatus.MATCHED.value:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.TARGET_GT_LABEL_INVALID,
            "Target row is not GT-label valid; refusing to build target RRI crop.",
        )
    gt_block = _compact_obb_block(sample.gt_obbs)
    if gt_block is None:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.TARGET_GT_OBB_MISSING,
            "Target RRI crop requires sample.gt_obbs.",
        )
    gt_world = _world_obbs_for_sample(gt_block[0], sample)
    gt_data, gt_source_indices = _valid_obb_data_with_source_indices(gt_world)
    try:
        gt_index = gt_source_indices.index(int(task.source_index))
    except ValueError as exc:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.TARGET_GT_ROW_MISSING,
            f"Oracle target row {task.source_index} is not present in sample.gt_obbs.",
        ) from exc
    return ObbTW(gt_data[gt_index].unsqueeze(0))


def crop_points_to_obb(points: Tensor, obb: ObbTW, *, margin_m: float = 0.0) -> Tensor:
    """Return finite world points inside an oriented target box."""

    if points.numel() == 0:
        return points.reshape(0, 3)
    pts = points.reshape(-1, points.shape[-1])[:, :3]
    return pts[_points_inside_obb_mask(pts, obb, margin_m=margin_m)]


def crop_padded_pointclouds_to_obb(
    points: Tensor,
    lengths: Tensor,
    obb: ObbTW,
    *,
    margin_m: float = 0.0,
    voxel_size_m: float = 0.0,
    max_points: int | None = None,
) -> tuple[Tensor, Tensor]:
    """Crop and fuse each padded candidate point cloud to an oriented box."""

    cropped: list[Tensor] = []
    lengths_out: list[int] = []
    row_lengths = lengths.to(dtype=torch.long).clamp(min=0, max=points.shape[1]).detach().cpu().tolist()
    for row_index, length_value in enumerate(row_lengths):
        length = int(length_value)
        row = crop_points_to_obb(points[row_index, :length, :3], obb, margin_m=margin_m)
        row = canonical_fuse_points(row, voxel_size_m=voxel_size_m, max_points=max_points)
        cropped.append(row)
        lengths_out.append(int(row.shape[0]))
    max_len = max(max(lengths_out), 1)
    output = torch.zeros((points.shape[0], max_len, 3), device=points.device, dtype=points.dtype)
    for row_index, row in enumerate(cropped):
        if row.numel() > 0:
            output[row_index, : row.shape[0], :] = row.to(device=points.device, dtype=points.dtype)
    return output, torch.tensor(lengths_out, device=points.device, dtype=torch.long)


def crop_mesh_to_obb(
    verts: Tensor,
    faces: Tensor,
    obb: ObbTW,
    *,
    margin_m: float = 0.0,
) -> tuple[Tensor, Tensor]:
    """Crop a scene mesh to an oriented target box."""

    if verts.numel() == 0 or faces.numel() == 0:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.TARGET_SCENE_MESH_EMPTY,
            "Target oriented OBB crop requires a non-empty scene mesh.",
        )
    vertex_inside = _points_inside_obb_mask(verts.reshape(-1, 3), obb, margin_m=margin_m)
    face_indices = faces.reshape(-1, 3).to(device=verts.device, dtype=torch.long)
    face_keep = vertex_inside[face_indices].any(dim=1)
    if not bool(face_keep.any().item()):
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.TARGET_MESH_CROP_EMPTY,
            "Target oriented OBB crop contains no mesh faces.",
        )
    kept_faces = face_indices[face_keep]
    unique_vertices, inverse = torch.unique(kept_faces.reshape(-1), sorted=True, return_inverse=True)
    return verts[unique_vertices].reshape(-1, 3), inverse.reshape(-1, 3).to(dtype=torch.long)


def target_aabb_from_points(points: Tensor, *, margin_m: float = 0.0) -> Tensor:
    """Return an axis-aligned scoring extent around prepared target points."""

    pts = points.reshape(-1, points.shape[-1])[:, :3]
    if pts.numel() == 0:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.TARGET_EXTENT_EMPTY,
            "Cannot build target crop extent from an empty point set.",
        )
    lower = pts.min(dim=0).values - float(margin_m)
    upper = pts.max(dim=0).values + float(margin_m)
    return torch.stack([lower[0], upper[0], lower[1], upper[1], lower[2], upper[2]]).to(dtype=pts.dtype)


def _points_inside_obb_mask(points: Tensor, obb: ObbTW, *, margin_m: float = 0.0) -> Tensor:
    pts = points.reshape(-1, points.shape[-1])[:, :3]
    finite = torch.isfinite(pts).all(dim=-1)
    local = obb.T_world_object.inverse().transform(pts).reshape(-1, 3)
    lower = obb.bb3_min_object.reshape(-1, 3)[0].to(device=pts.device, dtype=pts.dtype) - float(margin_m)
    upper = obb.bb3_max_object.reshape(-1, 3)[0].to(device=pts.device, dtype=pts.dtype) + float(margin_m)
    return finite & torch.all((local >= lower) & (local <= upper), dim=-1)


def build_root_eval_pointcloud(
    sample: EfmSnippetView,
    *,
    source: RriEvaluationPointCloudSource | str = RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT,
    camera_label: CameraLabel = "rgb",
    reference_pose_world: object | None = None,
    reference_time_ns: int | None = None,
    reference_trajectory_index: int | None = None,
    reference_frame_index: int | None = None,
    stride: int = 1,
    far_m: float | None = 20.0,
    voxel_size_m: float = 0.02,
    max_points: int | None = 200_000,
) -> RootEvalPointCloud:
    """Build the observed-prefix root cloud used by oracle rollout labels.

    ``ASE_GT_DEPTH_ROOT`` uses all observed camera/depth frames up to the
    rollout reference pose. ``LEGACY_SEMIDENSE_ROOT`` returns the collapsed MPS
    semi-dense point cloud for diagnostics only. ``RENDERED_LOGGED_DEPTH_ROOT``
    is intentionally reserved for the rendered-root ablation and should be
    implemented separately from ASE ray-distance preprocessing.

    Args:
        sample: EFM snippet containing camera calibration, ray-distance depth,
            trajectory poses, and optional MPS semi-dense points.
        source: Evaluation-geometry source. The thesis default is oracle-only
            ASE GT depth; the semi-dense option is a legacy diagnostic.
        camera_label: Calibrated EFM camera stream used for ASE depth.
        reference_pose_world: Optional world-from-rig root pose. It is used
            only when it exactly matches a trajectory row.
        reference_time_ns: Explicit root timestamp in nanoseconds; this has
            precedence over frame, trajectory, and pose-derived timestamps.
        reference_trajectory_index: Optional root trajectory row.
        reference_frame_index: Optional root camera frame row.
        stride: Positive spatial sampling stride after unprojection.
        far_m: Optional maximum retained ray distance in metres.
        voxel_size_m: Voxel edge length in metres for canonical fusion; ``0``
            disables aggregation.
        max_points: Optional deterministic point cap after fusion.

    Returns:
        :class:`RootEvalPointCloud` with ``Tensor["P 3", float32]`` world-frame
        points in metres and observed-prefix lineage.

    Notes:
        The returned geometry is consumed by the oracle label path. Selecting
        the legacy MPS source does not make GT mesh or candidate-rendered
        geometry actor-visible, and this function never converts missing data
        into a low RRI label.
    """

    if stride < 1:
        raise ValueError(f"stride must be >=1, got {stride}.")
    resolved = RriEvaluationPointCloudSource(source)
    if resolved is RriEvaluationPointCloudSource.LEGACY_SEMIDENSE_ROOT:
        points = torch.as_tensor(sample.semidense.collapse_points(), dtype=torch.float32)
        points = canonical_fuse_points(points, voxel_size_m=voxel_size_m, max_points=max_points)
        empty = torch.empty(0, dtype=torch.long, device=points.device)
        return RootEvalPointCloud(
            points_world=points,
            source=resolved,
            frame_indices=empty,
            trajectory_indices=empty,
            root_time_ns=reference_time_ns,
            root_trajectory_index=reference_trajectory_index,
            root_frame_index=reference_frame_index,
            depth_convention="mps_semidense_world",
            camera_label=camera_label,
            stride=stride,
            far_m=far_m,
            voxel_size_m=voxel_size_m,
            max_points=max_points,
        )
    if resolved is RriEvaluationPointCloudSource.RENDERED_LOGGED_DEPTH_ROOT:
        raise NotImplementedError(
            "rendered_logged_depth_root is reserved for the rendered-root parity ablation; "
            "use ase_gt_depth_root or legacy_semidense_root for current execution."
        )

    cam_view = sample.get_camera(camera_label)
    if cam_view.distance_m is None:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.ROOT_DEPTH_MISSING,
            f"RRI eval source ase_gt_depth_root requires {camera_label}/distance_m in the EFM sample.",
        )
    if cam_view.distance_m.ndim != 4 or cam_view.distance_m.shape[1] != 1:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.ROOT_DEPTH_SHAPE_INVALID,
            f"Expected {camera_label}/distance_m shape (F,1,H,W), got {tuple(cam_view.distance_m.shape)}.",
        )

    frame_indices, trajectory_indices = observed_prefix_frame_indices(
        sample,
        camera_label=camera_label,
        reference_pose_world=reference_pose_world,
        reference_time_ns=reference_time_ns,
        reference_trajectory_index=reference_trajectory_index,
        reference_frame_index=reference_frame_index,
    )
    if frame_indices.numel() == 0:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.ROOT_OBSERVED_FRAMES_EMPTY,
            "RRI eval source ase_gt_depth_root found no observed depth frames before the root pose.",
        )

    frame_indices = frame_indices.to(device=cam_view.distance_m.device, dtype=torch.long)
    trajectory_indices = trajectory_indices.to(device=cam_view.distance_m.device, dtype=torch.long)
    depths = cam_view.distance_m[frame_indices, 0]
    calibs = cam_view.calib[frame_indices]

    points_cam, valid = dist_im_to_point_cloud_im(depths, calibs)
    valid = valid & torch.isfinite(depths) & (depths > 0.0)
    if far_m is not None:
        valid = valid & (depths <= float(far_m))
    if stride > 1:
        points_cam = points_cam[:, ::stride, ::stride, :]
        valid = valid[:, ::stride, ::stride]

    t_world_rig = sample.trajectory.t_world_rig[trajectory_indices].to(
        device=points_cam.device,
        dtype=points_cam.dtype,
    )
    t_rig_cam = calibs.T_camera_rig.inverse().to(device=points_cam.device, dtype=points_cam.dtype)
    points_rig = t_rig_cam.transform(points_cam.reshape(points_cam.shape[0], -1, 3))
    points_world = t_world_rig.transform(points_rig).reshape(points_cam.shape[0], -1, 3)
    points = points_world[valid.reshape(valid.shape[0], -1)]
    points = canonical_fuse_points(points, voxel_size_m=voxel_size_m, max_points=max_points)
    if points.numel() == 0:
        raise _OracleEvidenceError(
            OracleEvidenceInvalidReason.ROOT_EVAL_POINTS_EMPTY,
            "RRI eval source ase_gt_depth_root produced no valid root evaluation points.",
        )

    root_time_ns = _root_time_ns(
        sample,
        camera_label=camera_label,
        reference_pose_world=reference_pose_world,
        reference_time_ns=reference_time_ns,
        reference_trajectory_index=reference_trajectory_index,
        reference_frame_index=reference_frame_index,
    )
    root_trajectory_index = _root_trajectory_index(
        sample,
        reference_pose_world=reference_pose_world,
        reference_time_ns=root_time_ns,
        reference_trajectory_index=reference_trajectory_index,
    )
    return RootEvalPointCloud(
        points_world=points,
        source=resolved,
        frame_indices=frame_indices.detach().clone(),
        trajectory_indices=trajectory_indices.detach().clone(),
        root_time_ns=root_time_ns,
        root_trajectory_index=root_trajectory_index,
        root_frame_index=reference_frame_index,
        depth_convention="ray_distance_m",
        camera_label=camera_label,
        stride=stride,
        far_m=far_m,
        voxel_size_m=voxel_size_m,
        max_points=max_points,
    )


def observed_prefix_frame_indices(
    sample: EfmSnippetView,
    *,
    camera_label: CameraLabel = "rgb",
    reference_pose_world: object | None = None,
    reference_time_ns: int | None = None,
    reference_trajectory_index: int | None = None,
    reference_frame_index: int | None = None,
) -> tuple[Tensor, Tensor]:
    """Select camera frames and matched trajectory rows in the observed prefix.

    Prefix membership is defined by camera timestamp and optional trajectory
    row, never by spatial nearest-neighbour pose matching. This prevents looped
    or revisited trajectories from admitting future ASE GT depth frames into a
    non-final rollout root.

    Args:
        sample: EFM snippet whose camera and trajectory timestamps share the
            snippet time domain.
        camera_label: Camera stream whose frame rows are selected.
        reference_pose_world: Optional exact world-from-rig trajectory pose.
        reference_time_ns: Optional explicit root timestamp in nanoseconds.
        reference_trajectory_index: Optional maximum trajectory row.
        reference_frame_index: Optional camera row used to derive root time.

    Returns:
        Tuple containing frame indices ``Tensor["F_eval", int64]`` and their
        nearest trajectory rows ``Tensor["F_eval", int64]``. Both are ordered
        prefixes on the camera timestamp device.
    """

    cam_view = sample.get_camera(camera_label)
    all_frames = torch.arange(cam_view.num_frames, device=cam_view.time_ns.device, dtype=torch.long)
    if all_frames.numel() == 0:
        empty = torch.empty(0, device=cam_view.time_ns.device, dtype=torch.long)
        return empty, empty
    _, trajectory_indices = cam_view.nearest_traj_indices(sample.trajectory.time_ns, all_frames, default_last=False)
    if trajectory_indices.numel() == 0:
        empty = torch.empty(0, device=cam_view.time_ns.device, dtype=torch.long)
        return empty, empty

    root_time = _root_time_ns(
        sample,
        camera_label=camera_label,
        reference_pose_world=reference_pose_world,
        reference_time_ns=reference_time_ns,
        reference_trajectory_index=reference_trajectory_index,
        reference_frame_index=reference_frame_index,
    )
    if root_time is None:
        root_time = int(sample.trajectory.time_ns.reshape(-1)[-1].detach().cpu().item())
    root_traj_index = _root_trajectory_index(
        sample,
        reference_pose_world=reference_pose_world,
        reference_time_ns=root_time,
        reference_trajectory_index=reference_trajectory_index,
    )
    keep = cam_view.time_ns.to(device=all_frames.device)[all_frames] <= int(root_time)
    if root_traj_index is not None:
        keep = keep & (trajectory_indices <= int(root_traj_index))
    return all_frames[keep], trajectory_indices[keep]


def _root_time_ns(
    sample: EfmSnippetView,
    *,
    camera_label: CameraLabel,
    reference_pose_world: object | None,
    reference_time_ns: int | None,
    reference_trajectory_index: int | None,
    reference_frame_index: int | None,
) -> int | None:
    if reference_time_ns is not None:
        return int(reference_time_ns)
    if reference_frame_index is not None:
        cam_view = sample.get_camera(camera_label)
        frame_count = int(cam_view.time_ns.reshape(-1).shape[0])
        if frame_count <= 0:
            return None
        frame_index = int(reference_frame_index)
        if frame_index < 0:
            frame_index += frame_count
        frame_index = max(0, min(frame_index, frame_count - 1))
        return int(cam_view.time_ns.reshape(-1)[frame_index].detach().cpu().item())
    if reference_trajectory_index is not None:
        traj_time = sample.trajectory.time_ns.reshape(-1)
        if traj_time.numel() == 0:
            return None
        index = max(0, min(int(reference_trajectory_index), int(traj_time.numel()) - 1))
        return int(traj_time[index].detach().cpu().item())
    exact_index = _exact_trajectory_index(sample, reference_pose_world=reference_pose_world)
    if exact_index is not None:
        return int(sample.trajectory.time_ns.reshape(-1)[exact_index].detach().cpu().item())
    return None


def _root_trajectory_index(
    sample: EfmSnippetView,
    *,
    reference_pose_world: object | None,
    reference_time_ns: int | None,
    reference_trajectory_index: int | None,
) -> int | None:
    traj_time = sample.trajectory.time_ns.reshape(-1)
    if reference_trajectory_index is not None:
        if traj_time.numel() == 0:
            return None
        return max(0, min(int(reference_trajectory_index), int(traj_time.numel()) - 1))
    exact_index = _exact_trajectory_index(sample, reference_pose_world=reference_pose_world)
    if exact_index is not None:
        return exact_index
    if reference_time_ns is None or traj_time.numel() == 0:
        return None
    eligible = torch.nonzero(traj_time <= int(reference_time_ns), as_tuple=False).reshape(-1)
    if eligible.numel() == 0:
        return 0
    return int(eligible[-1].detach().cpu().item())


def _exact_trajectory_index(sample: EfmSnippetView, *, reference_pose_world: object | None) -> int | None:
    if reference_pose_world is None or not hasattr(reference_pose_world, "tensor"):
        return None
    traj_tensor = sample.trajectory.t_world_rig.tensor().reshape(-1, 12)
    ref_tensor = (
        reference_pose_world.tensor()
        .reshape(-1, 12)[0]
        .to(
            device=traj_tensor.device,
            dtype=traj_tensor.dtype,
        )
    )
    matches = torch.isclose(traj_tensor, ref_tensor.reshape(1, 12), atol=1e-5, rtol=1e-5).all(dim=1)
    indices = torch.nonzero(matches, as_tuple=False).reshape(-1)
    if indices.numel() == 0:
        return None
    return int(indices[0].detach().cpu().item())


__all__ = [
    "RootEvalPointCloud",
    "OracleEvidenceInvalidReason",
    "OracleRriState",
    "RriEvaluationPointCloudSource",
    "RriRewardMode",
    "build_root_eval_pointcloud",
    "canonical_fuse_points",
    "crop_mesh_to_obb",
    "crop_padded_pointclouds_to_obb",
    "crop_points_to_obb",
    "observed_prefix_frame_indices",
    "target_gt_obb_world",
    "target_aabb_from_points",
]
