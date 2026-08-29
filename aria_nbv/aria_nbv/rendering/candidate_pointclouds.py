"""Vectorised depth-to-point-cloud conversion for candidate renders.

Consumes a single `EfmSnippetView` and matching `CandidateDepths`
to produce padded per-candidate point clouds, fused clouds with the collapsed
semi-dense SLAM reconstruction, and a combined occupancy extent for cropping.

This module owns vectorized unprojection, padding, semidense fusion, and bounds
assembly in :class:`CandidatePointClouds`. Depth rasterization, candidate
feasibility, target matching/cropping policy, and RRI scoring remain with their
respective renderer, generator, and metric layers.

The output is world-frame oracle evidence. Scene-level RRI uses the combined
snippet/candidate extent; target-level RRI may further crop both candidate
points and mesh geometry with the matched GT target OBB. Empty target crops or
unusable candidate depth should surface as invalidity, not as a low score.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ..data_handling import EfmSnippetView
from ..utils.typed_payloads import from_serializable, to_serializable
from .candidate_depth_renderer import CandidateDepths
from .unproject import backproject_depths_p3d_batch

Tensor = torch.Tensor


@dataclass(slots=True)
class CandidatePointClouds:
    """Batched candidate point clouds plus fused semi-dense reconstruction."""

    points: Tensor
    """Padded candidate points ``Tensor[\"C P 3\", float]`` in world metres."""

    lengths: Tensor
    """Valid point counts ``Tensor[\"C\", int64]`` for each padded row."""

    semidense_points: Tensor
    """Borrowed immutable collapsed SLAM points ``Tensor[\"K 3\", float]`` in world metres."""

    semidense_length: Tensor
    """Observed point count ``Tensor[\"1\", int64]`` for serialization symmetry."""

    occupancy_bounds: Tensor
    """World bounds ``Tensor[\"6\", float]`` ordered xmin/xmax/ymin/ymax/zmin/zmax."""

    def to_serializable(self) -> dict[str, object]:
        """Serialize this point-cloud batch into a cache-friendly CPU payload."""

        return to_serializable(self)

    @classmethod
    def from_serializable(
        cls,
        payload: dict[str, object],
        *,
        device: torch.device,
    ) -> "CandidatePointClouds":
        """Reconstruct one point-cloud batch from a serialized payload.

        Args:
            payload: Serialized payload produced by `to_serializable`.
            device: Destination device for tensors.

        Returns:
            Reconstructed candidate-pointcloud batch.
        """

        return from_serializable(cls, payload, device=device)


@dataclass(frozen=True, slots=True)
class PreparedSampleGeometry:
    """Device-local sample geometry reused across candidate batches."""

    _source_sample: object
    """Exact sample whose static geometry was prepared."""

    semidense_points: Tensor
    """Collapsed observed points ``Tensor["K 3", float]`` in world metres."""

    semidense_length: Tensor
    """Observed point count ``Tensor["1", int64]``."""

    static_bounds: Tensor
    """Snippet and semidense bounds ``Tensor["6", float]`` in world metres."""


def prepare_sample_geometry(
    sample: EfmSnippetView,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> PreparedSampleGeometry:
    """Collapse and transfer sample-static geometry once for repeated renders."""

    semidense = torch.as_tensor(sample.semidense.collapse_points(), device=device, dtype=dtype)
    semidense_length = torch.tensor([semidense.shape[0]], device=device, dtype=torch.long)
    snippet_bounds = sample.get_occupancy_extend().to(device=device, dtype=dtype)
    static_bounds = _merge_point_bounds(snippet_bounds, semidense)
    return PreparedSampleGeometry(
        _source_sample=sample,
        semidense_points=semidense,
        semidense_length=semidense_length,
        static_bounds=static_bounds,
    )


def build_candidate_pointclouds(
    sample: EfmSnippetView,
    batch: CandidateDepths,
    *,
    stride: int = 1,
    prepared_sample: PreparedSampleGeometry | None = None,
) -> CandidatePointClouds:
    """Convert stacked depth maps into batched point clouds and fuse with SLAM."""
    depths = batch.depths
    cameras = batch.p3d_cameras

    if depths.ndim != 3:
        raise ValueError(f"Expected depths of shape (B,H,W), got {tuple(depths.shape)}")

    padded, lengths = backproject_depths_p3d_batch(
        depths=depths,
        mask_valid=batch.depths_valid_mask,
        cameras=cameras,
        stride=stride,
    )

    device, dtype = padded.device, padded.dtype

    prepared = prepared_sample or prepare_sample_geometry(sample, device=device, dtype=dtype)
    if prepared._source_sample is not sample:
        raise ValueError("prepared_sample was created for a different sample.")
    if prepared.semidense_points.device != device or prepared.semidense_points.dtype != dtype:
        raise ValueError("prepared_sample must match the candidate point-cloud device and dtype.")
    occupancy_bounds = _compute_bounds(prepared.static_bounds, padded, lengths)

    return CandidatePointClouds(
        points=padded,
        lengths=lengths,
        semidense_points=prepared.semidense_points,
        semidense_length=prepared.semidense_length,
        occupancy_bounds=occupancy_bounds,
    )


def _compute_bounds(
    static_bounds: Tensor,
    padded: Tensor,
    lengths: Tensor,
) -> Tensor:
    """Combine snippet occupancy bounds with candidate and semi-dense extents."""
    out = static_bounds.to(device=padded.device, dtype=padded.dtype)
    x_min, x_max, y_min, y_max, z_min, z_max = out.unbind()

    if padded.numel() > 0 and padded.shape[1] > 0:
        mask = torch.arange(padded.shape[1], device=padded.device).unsqueeze(0) < lengths.unsqueeze(1)
        pts = padded[mask]
        if pts.numel() > 0:
            pmin = torch.amin(pts, dim=0)
            pmax = torch.amax(pts, dim=0)
            x_min, x_max = torch.minimum(x_min, pmin[0]), torch.maximum(x_max, pmax[0])
            y_min, y_max = torch.minimum(y_min, pmin[1]), torch.maximum(y_max, pmax[1])
            z_min, z_max = torch.minimum(z_min, pmin[2]), torch.maximum(z_max, pmax[2])

    return torch.stack([x_min, x_max, y_min, y_max, z_min, z_max], dim=0)


def _merge_point_bounds(bounds: Tensor, points: Tensor) -> Tensor:
    """Expand world bounds to include an unpadded point table."""

    if points.numel() == 0:
        return bounds
    point_min = torch.amin(points, dim=0)
    point_max = torch.amax(points, dim=0)
    lower = torch.minimum(bounds[[0, 2, 4]], point_min)
    upper = torch.maximum(bounds[[1, 3, 5]], point_max)
    return torch.stack([lower[0], upper[0], lower[1], upper[1], lower[2], upper[2]])


__all__ = [
    "CandidatePointClouds",
    "PreparedSampleGeometry",
    "build_candidate_pointclouds",
    "prepare_sample_geometry",
]
