"""Actor-visible point feature banks for VIN and finite-candidate Q_H readers."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from efm3d.aria import CameraTW, PoseTW
from efm3d.utils.image_sampling import sample_images
from torch import Tensor

APPROVED_ACTOR_FEATURE_SOURCES = frozenset(
    {
        "semidense_geometry",
        "semidense_support",
        "efm3d_feat2d_upsampled",
        "efm3d_token2d",
        "efm3d_dino_point",
        "efm3d_evl_crop",
        "efm3d_voxel_feat",
        "efm3d_neck_occ_feat",
        "efm3d_neck_obb_feat",
        "cubercnn_proposal",
        "cubercnn_roi",
        "cubercnn_roi_descriptor",
    }
)

FORBIDDEN_ACTOR_FEATURE_SOURCES = frozenset(
    {
        "gt_mesh",
        "gt_obb_crop",
        "gt_semantic_identity",
        "oracle_rri",
        "all_candidate_rendered_depth",
        "unvisited_candidate_rgb",
        "unvisited_candidate_dino",
        "unvisited_candidate_evl",
        "unvisited_candidate_detector",
    }
)

FORBIDDEN_ACTOR_FEATURE_MARKERS = (
    "gt_",
    "oracle",
    "all_candidate",
    "unvisited",
    "future_candidate",
    "rendered_depth",
    "rendered_roi",
    "candidate_rgb",
    "candidate_dino",
    "candidate_evl",
    "candidate_detector",
)


@dataclass(slots=True)
class FeaturePoolingResult:
    """Weighted point descriptors pooled over logged observations.

    Attributes:
        features: ``Tensor["B N C"]`` weighted mean descriptor per point.
        valid_mask: ``Tensor["B N", bool]`` indicating at least one valid sample.
        valid_frame_count: ``Tensor["B N", int64]`` number of valid logged frames.
        weight_sum: ``Tensor["B N"]`` sum of pooling weights before epsilon.
    """

    features: Tensor
    valid_mask: Tensor
    valid_frame_count: Tensor
    weight_sum: Tensor


@dataclass(slots=True)
class PointQueryPool:
    """Masked pooled descriptor for target, frustum, or intersection queries."""

    mean: Tensor
    maximum: Tensor
    std: Tensor
    count: Tensor
    valid_mask: Tensor


@dataclass(slots=True)
class PointFeatureBank:
    """Read-only feature bank derived from logged actor-visible observations.

    Attributes:
        points_world: ``Tensor["B N 3"]`` semidense or fused world points.
        features: ``Tensor["B N C"]`` pooled point descriptors.
        valid_mask: ``Tensor["B N", bool]`` descriptor-valid mask.
        valid_frame_count: ``Tensor["B N", int64]`` number of valid frame samples.
        weight_sum: ``Tensor["B N"]`` sum of valid pooling weights.
        per_frame_valid: ``Tensor["B T N", bool]`` logged projection-valid mask.
        source_frame_indices: ``Tensor["B T"]`` or ``Tensor["T"]`` source frame ids.
        feature_source: Human-readable feature source id.
        source_role: Actor/oracle provenance role. Actor banks must be actor-visible.
        compression_id: Descriptor compression provenance id.
    """

    points_world: Tensor
    features: Tensor
    valid_mask: Tensor
    valid_frame_count: Tensor
    weight_sum: Tensor
    per_frame_valid: Tensor
    source_frame_indices: Tensor
    feature_source: str
    source_role: str = "actor_visible"
    compression_id: str = "raw"
    point_support: Tensor | None = None

    def __post_init__(self) -> None:
        """Validate provenance immediately for direct dataclass construction."""

        self.validate_actor_visible()

    def validate_actor_visible(self) -> None:
        """Raise if this bank is not valid as an actor-visible descriptor source."""

        validate_actor_feature_provenance(
            feature_source=self.feature_source,
            source_role=self.source_role,
        )


def validate_actor_feature_provenance(
    *,
    feature_source: str,
    source_role: str = "actor_visible",
) -> None:
    """Validate that a feature source can be consumed by actor-side models.

    Args:
        feature_source: Stable source id such as ``"efm3d_feat2d_upsampled"``.
        source_role: Provenance role. Actor inputs currently accept only
            ``"actor_visible"``.

    Raises:
        ValueError: If the source is oracle/GT/counterfactual-only evidence.
    """

    if source_role != "actor_visible":
        msg = f"Actor feature banks require source_role='actor_visible', got {source_role!r}."
        raise ValueError(msg)
    normalized = _normalize_feature_source(feature_source)
    if normalized in FORBIDDEN_ACTOR_FEATURE_SOURCES:
        msg = f"{feature_source!r} is not an actor-visible feature source."
        raise ValueError(msg)
    if any(marker in normalized for marker in FORBIDDEN_ACTOR_FEATURE_MARKERS):
        msg = f"{feature_source!r} is not an actor-visible feature source."
        raise ValueError(msg)
    if normalized not in APPROVED_ACTOR_FEATURE_SOURCES:
        msg = f"{feature_source!r} is not an approved actor-visible feature source."
        raise ValueError(msg)


def pool_multiview_point_features(
    sampled_features: Tensor,
    valid_mask: Tensor,
    *,
    point_weights: Tensor | None = None,
    eps: float = 1.0e-6,
) -> FeaturePoolingResult:
    """Pool per-frame point descriptors with projection-valid weights.

    Args:
        sampled_features: ``Tensor["B T N C"]`` sampled logged-frame features.
        valid_mask: ``Tensor["B T N", bool]`` projection-valid samples.
        point_weights: Optional weights shaped ``N``, ``T``, ``B N``,
            ``B T``, ``T N``, or ``B T N``. Typical values encode point
            uncertainty, support, recency, or logged-view quality.
        eps: Positive denominator guard.

    Returns:
        FeaturePoolingResult: Weighted means and validity diagnostics.
    """

    if sampled_features.ndim != 4:
        msg = f"sampled_features must have shape B T N C, got {tuple(sampled_features.shape)}."
        raise ValueError(msg)
    if valid_mask.shape != sampled_features.shape[:3]:
        msg = (
            "valid_mask must have shape matching sampled_features[:3], got "
            f"{tuple(valid_mask.shape)} and {tuple(sampled_features.shape)}."
        )
        raise ValueError(msg)

    weights = valid_mask.to(dtype=sampled_features.dtype)
    if point_weights is not None:
        weights = weights * _broadcast_point_weights(
            point_weights.to(device=sampled_features.device, dtype=sampled_features.dtype),
            valid_mask.shape,
        )

    weight_sum = weights.sum(dim=1)
    pooled = (sampled_features * weights.unsqueeze(-1)).sum(dim=1)
    pooled = pooled / weight_sum.clamp_min(eps).unsqueeze(-1)
    pooled = torch.where(weight_sum.unsqueeze(-1) > 0, pooled, torch.zeros_like(pooled))

    return FeaturePoolingResult(
        features=pooled,
        valid_mask=valid_mask.any(dim=1),
        valid_frame_count=valid_mask.sum(dim=1).to(dtype=torch.int64),
        weight_sum=weight_sum,
    )


def pool_point_query(
    point_features: Tensor,
    point_mask: Tensor,
    *,
    eps: float = 1.0e-6,
) -> PointQueryPool:
    """Compute permutation-invariant masked point-pool summaries.

    Args:
        point_features: ``Tensor["B N C"]`` point descriptors.
        point_mask: ``Tensor["B N", bool]`` points included in the query.
        eps: Positive denominator guard for mean and std.

    Returns:
        PointQueryPool: Mean, max, std, count, and empty-support mask.
    """

    if point_features.ndim != 3:
        msg = f"point_features must have shape B N C, got {tuple(point_features.shape)}."
        raise ValueError(msg)
    if point_mask.shape != point_features.shape[:2]:
        msg = (
            "point_mask must have shape matching point_features[:2], got "
            f"{tuple(point_mask.shape)} and {tuple(point_features.shape)}."
        )
        raise ValueError(msg)

    if point_features.shape[1] == 0:
        batch_size, _, channels = point_features.shape
        empty = point_features.new_zeros((batch_size, channels))
        return PointQueryPool(
            mean=empty,
            maximum=empty.clone(),
            std=empty.clone(),
            count=torch.zeros((batch_size,), dtype=torch.int64, device=point_features.device),
            valid_mask=torch.zeros((batch_size,), dtype=torch.bool, device=point_features.device),
        )

    weights = point_mask.to(dtype=point_features.dtype)
    count = weights.sum(dim=1)
    mean = (point_features * weights.unsqueeze(-1)).sum(dim=1) / count.clamp_min(eps).unsqueeze(-1)
    mean = torch.where(count.unsqueeze(-1) > 0, mean, torch.zeros_like(mean))

    masked = point_features.masked_fill(~point_mask.unsqueeze(-1), -torch.inf)
    maximum = masked.max(dim=1).values
    maximum = torch.where(count.unsqueeze(-1) > 0, maximum, torch.zeros_like(maximum))

    diff = (point_features - mean.unsqueeze(1)) * weights.unsqueeze(-1)
    std = torch.sqrt((diff.square().sum(dim=1) / count.clamp_min(eps).unsqueeze(-1)).clamp_min(0.0))
    std = torch.where(count.unsqueeze(-1) > 0, std, torch.zeros_like(std))

    return PointQueryPool(
        mean=mean,
        maximum=maximum,
        std=std,
        count=count.to(dtype=torch.int64),
        valid_mask=count > 0,
    )


def compress_point_features(
    features: Tensor,
    *,
    projection: Tensor | None = None,
    output_dim: int | None = None,
) -> Tensor:
    """Apply an explicit descriptor compression transform.

    Args:
        features: ``Tensor[..., C]`` point descriptors.
        projection: Optional ``Tensor["C D"]`` projection matrix.
        output_dim: Optional leading channel count when using a simple slice.

    Returns:
        Tensor: Compressed descriptors.
    """

    if projection is not None:
        if projection.ndim != 2 or projection.shape[0] != features.shape[-1]:
            msg = (
                "projection must have shape C D matching features[..., C], got "
                f"{tuple(projection.shape)} for features {tuple(features.shape)}."
            )
            raise ValueError(msg)
        return features @ projection.to(device=features.device, dtype=features.dtype)
    if output_dim is not None:
        if output_dim <= 0 or output_dim > features.shape[-1]:
            msg = f"output_dim must be in [1, {features.shape[-1]}], got {output_dim}."
            raise ValueError(msg)
        return features[..., :output_dim]
    return features


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
        PointFeatureBank: Actor-visible point descriptors and provenance masks.
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

    resolved_compression_id = _resolve_compression_id(
        compression_id,
        projection=compression_projection,
        output_dim=compression_output_dim,
        output_channels=features.shape[-1],
    )

    bank = PointFeatureBank(
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
    return bank


def _broadcast_point_weights(point_weights: Tensor, target_shape: torch.Size) -> Tensor:
    batch_size, num_frames, num_points = target_shape
    if point_weights.shape == (num_points,):
        return point_weights.reshape(1, 1, num_points)
    if point_weights.shape == (num_frames,):
        return point_weights.reshape(1, num_frames, 1)
    if point_weights.shape == (batch_size, num_points):
        return point_weights.reshape(batch_size, 1, num_points)
    if point_weights.shape == (batch_size, num_frames):
        return point_weights.reshape(batch_size, num_frames, 1)
    if point_weights.shape == (num_frames, num_points):
        return point_weights.reshape(1, num_frames, num_points)
    if point_weights.shape == (batch_size, num_frames, num_points):
        return point_weights
    msg = (
        "point_weights must be shaped N, T, B N, B T, T N, or B T N; got "
        f"{tuple(point_weights.shape)} for target B T N={tuple(target_shape)}."
    )
    raise ValueError(msg)


def _normalize_feature_source(feature_source: str) -> str:
    return feature_source.lower().replace("-", "_").replace("/", "_").replace(":", "_").replace(" ", "_")


def _resolve_compression_id(
    compression_id: str,
    *,
    projection: Tensor | None,
    output_dim: int | None,
    output_channels: int,
) -> str:
    if compression_id != "raw":
        return compression_id
    if projection is not None:
        return f"linear_projection_{output_channels}d"
    if output_dim is not None:
        return f"slice_{output_channels}d"
    return compression_id


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
