"""Sampling helpers for building actor-visible point-feature banks."""

from __future__ import annotations

import torch
from efm3d.aria import CameraTW, PoseTW
from efm3d.utils.image_sampling import sample_images
from torch import Tensor

from .compression import compress_point_features, resolve_compression_id
from .point_feature_bank import PointFeatureBank
from .pooling import pool_multiview_point_features
from .provenance import validate_actor_feature_provenance


def sample_logged_image_features_at_world_points(
    *,
    points_world: Tensor,
    feat2d: Tensor,
    cameras: CameraTW,
    t_world_camera: PoseTW,
    point_weights: Tensor | None = None,
    source_frame_indices: Tensor | None = None,
    feature_source: str = "efm3d_feat2d_upsampled",
    source_role: str = "actor_visible",
    compression_projection: Tensor | None = None,
    compression_output_dim: int | None = None,
    compression_id: str = "raw",
    eps: float = 1.0e-6,
    warn: bool = False,
) -> PointFeatureBank:
    """Sample logged image features at semidense or fused world points.

    Args:
        points_world: ``Tensor["N 3"]`` or ``Tensor["B N 3"]`` world points.
        feat2d: Logged feature maps shaped ``B T C H W`` or ``T C H W``.
        cameras: `CameraTW` with shape ``B T`` or ``T``.
        t_world_camera: `PoseTW` with shape ``B T`` or ``T``.
        point_weights: Optional point/sample weights for pooling.
        source_frame_indices: Optional frame ids shaped ``B T`` or ``T``.
        feature_source: Feature source provenance id.
        source_role: Actor/oracle provenance role.
        compression_projection: Optional projection matrix for descriptors.
        compression_output_dim: Optional slice dimension for descriptors.
        compression_id: Stable compression provenance id.
        eps: Positive denominator guard.
        warn: Forward low-validity warnings from EFM3D `sample_images`.

    Returns:
        Actor-visible point descriptors and provenance masks.
    """
    validate_actor_feature_provenance(feature_source=feature_source, source_role=source_role)
    feat2d_b = _as_batched_logged_features(feat2d)
    batch_size, num_frames = feat2d_b.shape[:2]
    points_b = _as_batched_points(points_world, batch_size=batch_size)
    cameras_b = _as_batched_camera(cameras, batch_size=batch_size, num_frames=num_frames)
    t_world_camera_b = _as_batched_pose(t_world_camera, batch_size=batch_size, num_frames=num_frames)

    points_bt = points_b[:, None, :, :].expand(batch_size, num_frames, -1, -1)
    points_cam = t_world_camera_b.inverse() * points_bt
    sampled_features, valid_mask = sample_images(
        feat2d_b,
        points_cam,
        cameras_b,
        n_by_c=True,
        warn=warn,
        single_channel_mask=True,
    )
    pooled = pool_multiview_point_features(
        sampled_features,
        valid_mask,
        point_weights=point_weights,
        eps=eps,
    )
    features = compress_point_features(
        pooled.features,
        projection=compression_projection,
        output_dim=compression_output_dim,
    )
    frame_indices = _as_source_frame_indices(
        source_frame_indices,
        batch_size=batch_size,
        num_frames=num_frames,
        device=feat2d_b.device,
    )

    resolved_compression_id = resolve_compression_id(
        compression_id,
        projection=compression_projection,
        output_dim=compression_output_dim,
        output_channels=features.shape[-1],
    )

    return PointFeatureBank(
        points_world=points_b,
        features=features,
        valid_mask=pooled.valid_mask,
        valid_frame_count=pooled.valid_frame_count,
        weight_sum=pooled.weight_sum,
        per_frame_valid=valid_mask,
        source_frame_indices=frame_indices,
        feature_source=feature_source,
        source_role=source_role,
        compression_id=resolved_compression_id,
        point_support=point_weights,
    )


def _as_batched_logged_features(feat2d: Tensor) -> Tensor:
    if feat2d.ndim == 5:
        return feat2d
    if feat2d.ndim == 4:
        return feat2d.unsqueeze(0)
    msg = f"feat2d must have shape B T C H W or T C H W, got {tuple(feat2d.shape)}."
    raise ValueError(msg)


def _as_batched_points(points_world: Tensor, *, batch_size: int) -> Tensor:
    if points_world.ndim == 2 and points_world.shape[-1] == 3:
        return points_world.unsqueeze(0).expand(batch_size, -1, -1)
    if points_world.ndim == 3 and points_world.shape[-1] == 3:
        if points_world.shape[0] == batch_size:
            return points_world
        if points_world.shape[0] == 1:
            return points_world.expand(batch_size, -1, -1)
    msg = f"points_world must have shape N 3 or B N 3 for B={batch_size}, got {tuple(points_world.shape)}."
    raise ValueError(msg)


def _as_batched_camera(cameras: CameraTW, *, batch_size: int, num_frames: int) -> CameraTW:
    data = cameras.tensor()
    if data.ndim == 2 and data.shape[0] == num_frames:
        return CameraTW(data.unsqueeze(0).expand(batch_size, -1, -1))
    if data.ndim == 3 and data.shape[:2] == (batch_size, num_frames):
        return cameras
    if data.ndim == 3 and data.shape[0] == 1 and data.shape[1] == num_frames:
        return CameraTW(data.expand(batch_size, -1, -1))
    msg = f"cameras must have shape T D or B T D for B={batch_size}, T={num_frames}; got {tuple(data.shape)}."
    raise ValueError(msg)


def _as_batched_pose(t_world_camera: PoseTW, *, batch_size: int, num_frames: int) -> PoseTW:
    data = t_world_camera.tensor()
    if data.ndim == 2 and data.shape[0] == num_frames:
        return PoseTW(data.unsqueeze(0).expand(batch_size, -1, -1))
    if data.ndim == 3 and data.shape[:2] == (batch_size, num_frames):
        return t_world_camera
    if data.ndim == 3 and data.shape[0] == 1 and data.shape[1] == num_frames:
        return PoseTW(data.expand(batch_size, -1, -1))
    msg = f"t_world_camera must have shape T 12 or B T 12 for B={batch_size}, T={num_frames}; got {tuple(data.shape)}."
    raise ValueError(msg)


def _as_source_frame_indices(
    source_frame_indices: Tensor | None,
    *,
    batch_size: int,
    num_frames: int,
    device: torch.device,
) -> Tensor:
    if source_frame_indices is None:
        return torch.arange(num_frames, dtype=torch.int64, device=device).unsqueeze(0).expand(batch_size, -1)
    indices = source_frame_indices.to(device=device)
    if indices.shape == (num_frames,):
        return indices.unsqueeze(0).expand(batch_size, -1)
    if indices.shape == (batch_size, num_frames):
        return indices
    if indices.shape == (1, num_frames):
        return indices.expand(batch_size, -1)
    msg = (
        f"source_frame_indices must have shape T or B T, got {tuple(indices.shape)} for B={batch_size}, T={num_frames}."
    )
    raise ValueError(msg)


__all__ = ["sample_logged_image_features_at_world_points"]
