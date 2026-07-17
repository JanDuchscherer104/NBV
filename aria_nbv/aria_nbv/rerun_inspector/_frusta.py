"""Frame-safe camera frustum line-strip helpers for Rerun inspector views.

The builders here keep public geometry inputs typed as ``PoseTW``, ``CameraTW``,
or PyTorch3D ``PerspectiveCameras`` and return plain NumPy arrays ready for
``rr.LineStrips3D``.  Output points are in the world frame.  The optional CW90
display correction is disabled by default and is applied only to copied output
arrays.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import torch
from efm3d.aria import CameraTW, PoseTW
from numpy.typing import NDArray
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

FloatArray = NDArray[np.float64]
ScalarSequence = Sequence[float] | Sequence[int] | Sequence[bool] | np.ndarray | torch.Tensor


@dataclass(frozen=True)
class CandidateFrustumLineStrips:
    """Rerun-ready geometry aligned to one candidate axis ``N``.

    Every point is expressed in the physical world frame in metres. Labels may
    expose validity and oracle RRI for diagnostics, but those values do not
    alter geometry or convert invalid actions into low-scoring valid actions.
    """

    line_strips: list[FloatArray]
    """One ``ndarray["12 3", float64]`` continuous frustum strip per candidate."""

    labels: list[str]
    """Stable human-readable metadata labels aligned one-to-one with ``N``."""

    centers_world: FloatArray
    """Camera centers as ``ndarray["N 3", float64]`` in world metres."""

    corners_world: FloatArray
    """Image-plane corners as ``ndarray["N 4 3", float64]`` in world metres."""


def frusta_from_camera_tw(
    poses_world_cam: PoseTW,
    camera: CameraTW,
    *,
    depth_m: float = 1.0,
    candidate_ids: Sequence[int] | np.ndarray | torch.Tensor | None = None,
    ranks: Sequence[int] | np.ndarray | torch.Tensor | None = None,
    oracle_rri: Sequence[float] | np.ndarray | torch.Tensor | None = None,
    validity: Sequence[bool] | np.ndarray | torch.Tensor | None = None,
    display_cw90: bool = False,
) -> CandidateFrustumLineStrips:
    """Build world-frame frustum line strips from typed ``PoseTW`` and ``CameraTW``.

    Args:
        poses_world_cam: ``PoseTW`` with underlying
            ``Tensor["N 12", float32]`` storing physical world-from-camera
            transforms.
        camera: Matching ``CameraTW`` intrinsics.  A single camera is broadcast
            across all poses; a batched camera must match the flattened pose
            count.
        depth_m: Metric depth of the displayed image-plane corners along the
            camera +Z ray direction.
        candidate_ids: Optional ``Tensor["N", int64]`` stable ids for labels.
        ranks: Optional ``Tensor["N", int64]`` diagnostic ranks.
        oracle_rri: Optional ``Tensor["N", float32]`` oracle-only labels.
        validity: Optional ``Tensor["N", bool]`` hard action-validity mask.
        display_cw90: If true, apply the historical CW90 display-only local
            roll to copied output arrays.  The input poses and cameras are never
            mutated.

    Returns:
        :class:`CandidateFrustumLineStrips` with all points in world metres.
    """

    _validate_depth(depth_m)
    poses_flat = _flatten_poses(poses_world_cam)
    cameras_flat = _broadcast_cameras(camera, count=int(poses_flat.shape[0]))

    centers: list[np.ndarray] = []
    corners: list[np.ndarray] = []
    line_strips: list[np.ndarray] = []
    for idx in range(int(poses_flat.shape[0])):
        pose_i = poses_flat[idx]
        camera_i = cameras_flat[idx]
        center_i, corners_i = _camera_tw_frustum_vertices(pose_i, camera_i, depth_m=depth_m)
        centers.append(center_i)
        corners.append(corners_i)
        line_strips.append(_line_strip_from_vertices(center_i, corners_i))

    result = CandidateFrustumLineStrips(
        line_strips=line_strips,
        labels=candidate_labels(
            len(line_strips),
            candidate_ids=candidate_ids,
            ranks=ranks,
            oracle_rri=oracle_rri,
            validity=validity,
        ),
        centers_world=np.stack(centers, axis=0) if centers else np.empty((0, 3), dtype=np.float64),
        corners_world=np.stack(corners, axis=0) if corners else np.empty((0, 4, 3), dtype=np.float64),
    )
    if display_cw90:
        return apply_display_cw90(result, poses_world_cam)
    return result


def frusta_from_p3d_cameras(
    poses_world_cam: PoseTW,
    cameras: PerspectiveCameras,
    *,
    depth_m: float = 1.0,
    candidate_ids: Sequence[int] | np.ndarray | torch.Tensor | None = None,
    ranks: Sequence[int] | np.ndarray | torch.Tensor | None = None,
    oracle_rri: Sequence[float] | np.ndarray | torch.Tensor | None = None,
    validity: Sequence[bool] | np.ndarray | torch.Tensor | None = None,
    display_cw90: bool = False,
) -> CandidateFrustumLineStrips:
    """Build world-frame frustum strips from ``PoseTW`` plus PyTorch3D cameras.

    This fallback mirrors `aria_nbv.rendering.unproject`: pixel-space
    corners are converted to PyTorch3D NDC coordinates and unprojected via
    ``PerspectiveCameras.unproject_points(..., world_coordinates=True,
    from_ndc=True)``.  Camera centers come from the typed ``PoseTW`` boundary so
    labels and display transforms remain tied to explicit ``T_world_cam`` poses.

    Args:
        poses_world_cam: ``PoseTW`` storing world-from-camera transforms.
            Single, ``Tensor["N 12", float32]``, and flattened
            ``Tensor["... 12", float32]`` batches are accepted.
        cameras: Matching PyTorch3D cameras from the renderer or offline store.
            A single PyTorch3D camera is broadcast across all poses; otherwise
            its batch length must match the flattened pose count.
        depth_m: Metric +Z camera depth for the displayed corner plane.
        candidate_ids: Optional ``Tensor["N", int64]`` stable ids for labels.
        ranks: Optional ``Tensor["N", int64]`` diagnostic ranks.
        oracle_rri: Optional ``Tensor["N", float32]`` oracle-only labels.
        validity: Optional ``Tensor["N", bool]`` hard action-validity mask.
        display_cw90: If true, apply CW90 only to copied output arrays.

    Returns:
        :class:`CandidateFrustumLineStrips` with all points in world metres.
    """

    _validate_depth(depth_m)
    poses_flat = _flatten_poses(poses_world_cam)
    count = int(poses_flat.shape[0])
    cameras_flat = _broadcast_p3d_cameras(cameras, count=count)
    corners_t = _p3d_corner_points_world(cameras_flat, depth_m=depth_m)

    centers = poses_flat.t.detach().cpu().numpy().reshape(count, 3).astype(np.float64, copy=True)
    corners = corners_t.detach().cpu().numpy().reshape(count, 4, 3).astype(np.float64, copy=True)
    line_strips = [_line_strip_from_vertices(centers[idx], corners[idx]) for idx in range(count)]

    result = CandidateFrustumLineStrips(
        line_strips=line_strips,
        labels=candidate_labels(
            count,
            candidate_ids=candidate_ids,
            ranks=ranks,
            oracle_rri=oracle_rri,
            validity=validity,
        ),
        centers_world=centers,
        corners_world=corners,
    )
    if display_cw90:
        return apply_display_cw90(result, poses_world_cam)
    return result


def apply_display_cw90(
    frusta: CandidateFrustumLineStrips,
    poses_world_cam: PoseTW,
    *,
    undo: bool = False,
) -> CandidateFrustumLineStrips:
    """Return a copy with the display-only CW90 local roll applied.

    Args:
        frusta: Existing world-frame frustum output to rotate. The arrays inside this
            object are never mutated.
        poses_world_cam: ``PoseTW`` used to define each candidate's local camera
            frame for the display roll.
        undo: If true, apply the inverse 90 degree roll.

    Returns:
        A new :class:`CandidateFrustumLineStrips` with copied world-frame arrays.
    """

    poses_flat = _flatten_poses(poses_world_cam)
    count = len(frusta.line_strips)
    if int(poses_flat.shape[0]) != count:
        raise ValueError(f"Pose count {int(poses_flat.shape[0])} must match frustum count {count}")

    deltas = _display_cw90_world_rotations(poses_flat, undo=undo)
    centers = frusta.centers_world.astype(np.float64, copy=True)
    corners = _rotate_point_batches(frusta.corners_world, centers, deltas)
    line_strips = [
        _rotate_points(strip.astype(np.float64, copy=True), centers[idx], deltas[idx])
        for idx, strip in enumerate(frusta.line_strips)
    ]
    return CandidateFrustumLineStrips(
        line_strips=line_strips,
        labels=list(frusta.labels),
        centers_world=centers,
        corners_world=corners,
    )


def candidate_labels(
    count: int,
    *,
    candidate_ids: Sequence[int] | np.ndarray | torch.Tensor | None = None,
    ranks: Sequence[int] | np.ndarray | torch.Tensor | None = None,
    oracle_rri: Sequence[float] | np.ndarray | torch.Tensor | None = None,
    validity: Sequence[bool] | np.ndarray | torch.Tensor | None = None,
) -> list[str]:
    """Build stable candidate labels for Rerun line-strip metadata.

    Args:
        count: Number of candidate labels to produce.
        candidate_ids: Optional ``Tensor["N", int64]`` identifiers. Defaults to
            ``range(count)``.
        ranks: Optional ``Tensor["N", int64]`` diagnostic ranks.
        oracle_rri: Optional ``Tensor["N", float32]`` oracle/evaluation values.
        validity: Optional ``Tensor["N", bool]`` hard candidate-validity mask.

    Returns:
        One stable, human-readable label per candidate.
    """

    if count < 0:
        raise ValueError(f"count must be non-negative, got {count}")
    ids = _as_optional_array(candidate_ids, name="candidate_ids", count=count, dtype=np.int64)
    if ids is None:
        ids = np.arange(count, dtype=np.int64)
    ranks_arr = _as_optional_array(ranks, name="ranks", count=count, dtype=np.int64)
    rri_arr = _as_optional_array(oracle_rri, name="oracle_rri", count=count, dtype=np.float64)
    validity_arr = _as_optional_array(validity, name="validity", count=count, dtype=bool)

    labels: list[str] = []
    for idx in range(count):
        parts = [f"candidate_id={int(ids[idx])}"]
        if ranks_arr is not None:
            parts.append(f"rank={int(ranks_arr[idx])}")
        if rri_arr is not None:
            parts.append(f"oracle_rri={_format_float_label(float(rri_arr[idx]))}")
        if validity_arr is not None:
            parts.append(f"validity={'valid' if bool(validity_arr[idx]) else 'invalid'}")
        labels.append(" | ".join(parts))
    return labels


def _camera_tw_frustum_vertices(
    pose_world_cam: PoseTW, camera: CameraTW, *, depth_m: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return camera center and image corners in world coordinates."""

    pose_world_cam = pose_world_cam.to(device=camera.device, dtype=camera.dtype)
    corners_px = _camera_tw_image_corners(camera)
    rays_cam, _ = camera.unproject(corners_px)
    rays_cam = rays_cam.reshape(4, 3)
    z = rays_cam[:, 2:3]
    if torch.any(torch.abs(z) < 1e-8):
        raise ValueError("CameraTW corner rays must have non-zero +Z components")
    corners_cam = rays_cam * (torch.as_tensor(depth_m, device=rays_cam.device, dtype=rays_cam.dtype) / z)
    corners_world = pose_world_cam.transform(corners_cam)
    center_world = pose_world_cam.t
    return (
        center_world.detach().cpu().numpy().reshape(3).astype(np.float64, copy=True),
        corners_world.detach().cpu().numpy().reshape(4, 3).astype(np.float64, copy=True),
    )


def _camera_tw_image_corners(camera: CameraTW) -> torch.Tensor:
    """Return image-boundary corners as ``Tensor["1 4 2", float32]`` in pixels."""

    size = camera.size.reshape(-1, 2)[0].to(device=camera.device, dtype=camera.dtype)
    width = size[0]
    height = size[1]
    corners = torch.stack(
        [
            torch.stack((torch.zeros_like(width), torch.zeros_like(height))),
            torch.stack((width, torch.zeros_like(height))),
            torch.stack((width, height)),
            torch.stack((torch.zeros_like(width), height)),
        ],
        dim=0,
    )
    return corners.unsqueeze(0)


def _p3d_corner_points_world(cameras: PerspectiveCameras, *, depth_m: float) -> torch.Tensor:
    """Unproject corners as ``Tensor["N 4 3", float32]`` in world metres."""

    num_cams = int(cameras.R.shape[0])
    device = cameras.R.device
    dtype = cameras.R.dtype
    image_size = cameras.image_size.to(device=device, dtype=dtype)
    if image_size.shape[0] == 1 and num_cams > 1:
        image_size = image_size.expand(num_cams, -1)
    if image_size.shape[0] != num_cams:
        raise ValueError(f"image_size batch {image_size.shape[0]} must match camera batch {num_cams}")

    height = image_size[:, 0]
    width = image_size[:, 1]
    scale = torch.minimum(height, width)
    zeros = torch.zeros_like(width)
    pixel_corners = torch.stack(
        [
            torch.stack((zeros, zeros), dim=-1),
            torch.stack((width, zeros), dim=-1),
            torch.stack((width, height), dim=-1),
            torch.stack((zeros, height), dim=-1),
        ],
        dim=1,
    )
    x_ndc = -(pixel_corners[..., 0] - width[:, None] * 0.5) * (2.0 / scale[:, None])
    y_ndc = -(pixel_corners[..., 1] - height[:, None] * 0.5) * (2.0 / scale[:, None])
    depth = torch.full_like(x_ndc, float(depth_m))
    xy_depth = torch.stack([x_ndc, y_ndc, depth], dim=-1)
    return cameras.unproject_points(xy_depth, world_coordinates=True, from_ndc=True)


def _line_strip_from_vertices(center_world: np.ndarray, corners_world: np.ndarray) -> FloatArray:
    """Build one continuous candidate strip from a center and four corners."""

    top_left, top_right, bottom_right, bottom_left = corners_world
    return np.stack(
        [
            center_world,
            top_left,
            top_right,
            bottom_right,
            bottom_left,
            top_left,
            center_world,
            top_right,
            center_world,
            bottom_right,
            center_world,
            bottom_left,
        ],
        axis=0,
    ).astype(np.float64, copy=True)


def _flatten_poses(poses_world_cam: PoseTW) -> PoseTW:
    """Flatten a candidate batch to ``PoseTW`` backed by ``Tensor["N 12", float32]``."""

    tensor = poses_world_cam.tensor()
    if tensor.shape[-1] != 12:
        raise ValueError(f"PoseTW must store 12 values per pose, got shape {tuple(tensor.shape)}")
    return poses_world_cam.reshape(-1, 12)


def _broadcast_cameras(camera: CameraTW, *, count: int) -> list[CameraTW]:
    """Return one ``CameraTW`` per flattened candidate pose."""

    tensor = camera.tensor()
    camera_flat = camera.reshape(-1, tensor.shape[-1])
    num_cameras = int(camera_flat.shape[0])
    if num_cameras == 1:
        return [camera_flat[0] for _ in range(count)]
    if num_cameras != count:
        raise ValueError(f"CameraTW batch {num_cameras} must be 1 or match pose count {count}")
    return [camera_flat[idx] for idx in range(count)]


def _broadcast_p3d_cameras(cameras: PerspectiveCameras, *, count: int) -> PerspectiveCameras:
    """Return PyTorch3D cameras with batch length matching ``count``."""

    num_cameras = int(cameras.R.shape[0])
    if num_cameras == count:
        return cameras
    if num_cameras == 1:
        return cameras.extend(count)
    raise ValueError(f"PerspectiveCameras batch {num_cameras} must be 1 or match pose count {count}")


def _display_cw90_world_rotations(poses_world_cam: PoseTW, *, undo: bool) -> np.ndarray:
    """Return one world-frame local roll matrix per candidate pose."""

    angle = -np.pi / 2.0 if undo else np.pi / 2.0
    c = float(np.cos(angle))
    s = float(np.sin(angle))
    roll_local = np.array(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    r_world_cam = poses_world_cam.R.detach().cpu().numpy().reshape(-1, 3, 3).astype(np.float64, copy=True)
    return r_world_cam @ roll_local @ np.swapaxes(r_world_cam, -1, -2)


def _rotate_point_batches(points: np.ndarray, centers: np.ndarray, rotations: np.ndarray) -> FloatArray:
    """Rotate batched point arrays around candidate centers."""

    out = np.empty_like(points, dtype=np.float64)
    for idx in range(points.shape[0]):
        out[idx] = _rotate_points(points[idx], centers[idx], rotations[idx])
    return out


def _rotate_points(points: np.ndarray, center: np.ndarray, rotation: np.ndarray) -> FloatArray:
    """Rotate a point array around one center using a column-vector rotation."""

    offsets = points.astype(np.float64, copy=False) - center[None, :]
    return (offsets @ rotation.T) + center[None, :]


def _as_optional_array(
    values: ScalarSequence | None,
    *,
    name: str,
    count: int,
    dtype: np.dtype | type[np.generic] | type[bool],
) -> np.ndarray | None:
    """Convert an optional label input to a one-dimensional array."""

    if values is None:
        return None
    if isinstance(values, torch.Tensor):
        arr = values.detach().cpu().numpy()
    else:
        arr = np.asarray(values)
    arr = arr.reshape(-1).astype(dtype, copy=False)
    if arr.shape[0] != count:
        raise ValueError(f"{name} length {arr.shape[0]} must match candidate count {count}")
    return arr


def _format_float_label(value: float) -> str:
    """Format a scalar for stable labels."""

    if not np.isfinite(value):
        return "nan"
    return f"{value:.4f}"


def _validate_depth(depth_m: float) -> None:
    """Validate the metric frustum depth."""

    if not np.isfinite(depth_m) or depth_m <= 0.0:
        raise ValueError(f"depth_m must be a finite positive value, got {depth_m}")


__all__ = [
    "CandidateFrustumLineStrips",
    "apply_display_cw90",
    "candidate_labels",
    "frusta_from_camera_tw",
    "frusta_from_p3d_cameras",
]
