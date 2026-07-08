"""Pooling helpers for actor-visible point descriptors."""

from __future__ import annotations

import torch
from torch import Tensor

from .feature_pooling_result import FeaturePoolingResult
from .point_query_pool import PointQueryPool


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
        Weighted means and validity diagnostics.
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
        Mean, max, std, count, and empty-support mask.
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


__all__ = ["pool_multiview_point_features", "pool_point_query"]
