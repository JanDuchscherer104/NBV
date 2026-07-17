"""Descriptor compression helpers for point-feature banks.

This module provides explicit channel slicing or linear projection and derives
human-readable compression labels for actor-visible descriptor payloads.
"""

from __future__ import annotations

from torch import Tensor


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
        Compressed descriptors.
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


def resolve_compression_id(
    compression_id: str,
    *,
    projection: Tensor | None,
    output_dim: int | None,
    output_channels: int,
) -> str:
    """Return a human-readable label for raw, sliced, or projected descriptors.

    The generated label records only the transform family and output width; it
    is not a content hash of a projection matrix and cannot uniquely identify
    learned compression weights.
    """
    if compression_id != "raw":
        return compression_id
    if projection is not None:
        return f"linear_projection_{output_channels}d"
    if output_dim is not None:
        return f"slice_{output_channels}d"
    return compression_id


__all__ = ["compress_point_features", "resolve_compression_id"]
