"""Convert typed ARIA geometry and image payloads into Rerun-ready arrays.

This module owns CPU NumPy conversion, deterministic point subsampling,
world-from-camera pose extraction, pinhole parameter ordering, and display-only
image rotation. It does not change physical coordinate frames or mutate source
tensors, ``PoseTW`` objects, cameras, or immutable dataset records.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from efm3d.aria.tensor_wrapper import TensorWrapper
from torch import Tensor

if TYPE_CHECKING:
    from efm3d.aria.camera import CameraTW
    from numpy.typing import DTypeLike, NDArray
    from pytorch3d.renderer.cameras import PerspectiveCameras


def to_numpy(value: object, *, dtype: DTypeLike = np.float32) -> NDArray[Any]:
    """Expose a tensor-like payload as a CPU NumPy array of the requested dtype.

    Torch inputs are detached before transfer, so Rerun logging never retains a
    gradient graph. Shape and coordinate frame are preserved; existing NumPy
    inputs may share storage when no dtype conversion is required.
    """

    if isinstance(value, TensorWrapper):
        value = value._data
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=dtype)


def deterministic_downsample(points: object, *, max_points: int, seed: int | None) -> NDArray[Any]:
    """Return an order-preserving random subset of 3D points.

    Args:
        points: Tensor-like coordinates reshaped to
            ``ndarray["N 3", float32]``. The caller owns their frame and units.
        max_points: Maximum returned rows; non-positive values return an empty
            ``ndarray["0 3", float32]``.
        seed: NumPy generator seed, or ``None`` for non-reproducible sampling.

    Returns:
        ``ndarray["M 3", float32]`` with ``M <= max_points``. Sorted sampled
        indices preserve source order and the input is not mutated.
    """

    arr = to_numpy(points).reshape(-1, 3)
    if max_points <= 0:
        return arr[:0]
    if arr.shape[0] <= max_points:
        return arr
    rng = np.random.default_rng(seed)
    indices = np.sort(rng.choice(arr.shape[0], size=max_points, replace=False))
    return arr[indices]


def pose_rt(poses: PoseTW, indices: Sequence[int] | None = None) -> tuple[NDArray[Any], NDArray[Any]]:
    """Extract rotation and translation from typed parent-from-child poses.

    Args:
        poses: ``PoseTW`` with underlying ``Tensor["... 12", float32]``.
        indices: Optional flattened pose rows to retain.

    Returns:
        Rotation ``ndarray["M 3 3", float32]`` and translation
        ``ndarray["M 3", float32]``. Translation keeps the pose's parent frame
        and is in metres for ARIA world transforms.
    """

    r = to_numpy(poses.R).reshape(-1, 3, 3)
    t = to_numpy(poses.t).reshape(-1, 3)
    if indices is not None:
        idx = np.asarray(indices, dtype=np.int64)
        r = r[idx]
        t = t[idx]
    return r, t


def p3d_param_at(values: Tensor, index: int) -> NDArray[Any]:
    """Return one broadcast-aware PyTorch3D parameter row.

    A singleton first axis is reused for every candidate; otherwise ``index``
    is clamped to the available camera batch. The result is
    ``ndarray["D", float32]`` on CPU.
    """

    arr = to_numpy(values).reshape(-1, values.shape[-1])
    if arr.shape[0] == 0:
        raise ValueError("PyTorch3D camera parameter batch is empty.")
    row = arr[0] if arr.shape[0] == 1 else arr[min(max(index, 0), arr.shape[0] - 1)]
    return np.asarray(row, dtype=np.float32)


def p3d_pinhole_kwargs(cameras: PerspectiveCameras, index: int) -> dict[str, list[float]]:
    """Return Rerun ``Pinhole`` kwargs from a PyTorch3D camera entry.

    PyTorch3D stores ``image_size`` as ``(height, width)``; Rerun expects
    ``resolution`` as ``[width, height]``. Focal lengths and principal point
    remain ``[x, y]`` in the camera's pixel calibration convention.
    """

    image_size = p3d_param_at(cameras.image_size, index)
    focal = p3d_param_at(cameras.focal_length, index)
    principal = p3d_param_at(cameras.principal_point, index)
    height, width = float(image_size[0]), float(image_size[1])
    return {
        "resolution": [width, height],
        "focal_length": [float(focal[0]), float(focal[1])],
        "principal_point": [float(principal[0]), float(principal[1])],
    }


def camera_tw_pinhole_kwargs(camera: CameraTW) -> dict[str, list[float]]:
    """Return pixel-calibrated Rerun pinhole values from one ``CameraTW`` row.

    Resolution is ``[width, height]``; focal length ``[f_x, f_y]`` and
    principal point ``[c_x, c_y]`` are in pixels. Extrinsics are intentionally
    excluded and must be logged from the matching world-from-camera ``PoseTW``.
    """

    size = to_numpy(camera.size).reshape(-1, 2)[0]
    focal = to_numpy(camera.f).reshape(-1, 2)[0]
    principal = to_numpy(camera.c).reshape(-1, 2)[0]
    return {
        "resolution": [float(size[0]), float(size[1])],
        "focal_length": [float(focal[0]), float(focal[1])],
        "principal_point": [float(principal[0]), float(principal[1])],
    }


def candidate_centers_world(poses_world_cam: PoseTW, indices: Sequence[int]) -> NDArray[Any]:
    """Return selected camera centers as ``ndarray["M 3", float32]`` in world metres."""

    _, centers = pose_rt(poses_world_cam, indices)
    return centers


def subset_poses(poses_world_cam: PoseTW, indices: Sequence[int]) -> PoseTW:
    """Select flattened world-from-camera pose rows without mutating the source.

    Returns:
        ``PoseTW`` with underlying ``Tensor["M 12", float32]`` in the requested
        index order.
    """

    data = poses_world_cam._data
    if data is None:
        raise ValueError("PoseTW payload is empty; cannot subset candidate poses.")
    data = data.reshape(-1, 12)
    index = torch.as_tensor(list(indices), device=data.device, dtype=torch.long)
    return cast("PoseTW", PoseTW(data.index_select(0, index)))


def image_hwc(tensor: object, index: int) -> NDArray[Any]:
    """Convert one channel-first image to ``ndarray["H W C", uint8]``.

    Batched ``Tensor["F C H W", ...]`` inputs select frame ``index``. Floating
    values in ``[0, 1]`` are scaled to ``[0, 255]``; other values are clipped.
    Physical camera orientation is unchanged until an explicit display rotation.
    """

    arr = to_numpy(tensor)
    if arr.ndim == 4:
        arr = arr[index]
    if arr.ndim == 3 and arr.shape[0] in (1, 3):
        arr = np.moveaxis(arr, 0, -1)
    arr = np.asarray(arr)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0.0, 1.0 if float(np.nanmax(arr)) <= 1.0 else 255.0)
        if float(np.nanmax(arr)) <= 1.0:
            arr = arr * 255.0
        arr = arr.astype(np.uint8)
    return arr


def depth_hw(tensor: object, index: int) -> NDArray[Any]:
    """Return one depth frame as ``ndarray["H W", float32]``.

    Accepted layouts include ``Tensor["F 1 H W", ...]`` and
    ``Tensor["F H W", ...]``. Values preserve source units; inspector depth
    sources are metric distances in metres.
    """

    arr = to_numpy(tensor)
    if arr.ndim == 4:
        arr = arr[index, 0]
    elif arr.ndim == 3:
        arr = arr[index]
        if arr.ndim == 3 and arr.shape[0] == 1:
            arr = arr[0]
    return np.asarray(arr, dtype=np.float32)


def display_rot90_cw(array: NDArray[Any]) -> NDArray[Any]:
    """Return a contiguous CW90 display copy without changing camera geometry.

    The physical ``PoseTW``/``CameraTW`` contract remains untouched; this helper
    exists only to orient image and depth rasters for human viewing.
    """

    return np.ascontiguousarray(np.rot90(array, k=-1))


__all__ = [
    "camera_tw_pinhole_kwargs",
    "candidate_centers_world",
    "depth_hw",
    "deterministic_downsample",
    "display_rot90_cw",
    "image_hwc",
    "p3d_param_at",
    "p3d_pinhole_kwargs",
    "pose_rt",
    "subset_poses",
    "to_numpy",
]
