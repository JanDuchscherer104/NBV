r"""Low-level RRI metric primitives (point-mesh distances).

This module wraps PyTorch3D geometric distance implementations so downstream
code can compute accuracy, completeness, and bidirectional Chamfer distances in
a uniform, torch-first manner. Only the GPU-accelerated PyTorch3D path is
supported; CPU fallbacks were removed to keep the hot path simple and
consistent. The functions remain thin: callers must supply pre-sampled point
clouds and mesh tensors. Directional components are returned separately to
expose the accuracy/completeness split described in ``surface_metrics.qmd``.

For a point set $P$ and mesh $M$, `accuracy` is point-to-mesh error and
`completeness` is mesh-to-point error. The current scalar point-mesh error is
their sum, which is the value consumed by `OracleRRI`.
"""

from __future__ import annotations

import torch
from pytorch3d.loss.point_mesh_distance import (  # type: ignore[import-untyped]
    _DEFAULT_MIN_TRIANGLE_AREA,
    face_point_distance,
    point_face_distance,
)
from torch import Tensor

from .types import DistanceBreakdown


def chamfer_point_mesh(
    points: Tensor,
    gt_verts: Tensor,
    gt_faces: Tensor,
) -> DistanceBreakdown:
    """Compute accuracy, completeness, and bidirectional Chamfer for P<->M."""

    lengths = torch.tensor([points.shape[0]], device=points.device, dtype=torch.long)
    padded = points.unsqueeze(0)

    dist = chamfer_point_mesh_batched(padded, lengths, gt_verts, gt_faces)
    return DistanceBreakdown(
        accuracy=dist.accuracy.squeeze(0),
        completeness=dist.completeness.squeeze(0),
        bidirectional=dist.bidirectional.squeeze(0),
    )


def chamfer_point_mesh_batched(
    points: Tensor,
    lengths: Tensor,
    gt_verts: Tensor,
    gt_faces: Tensor,
) -> DistanceBreakdown:
    """Chamfer-like point↔mesh distance per example (fully vectorised).

    Returns per-candidate accuracy (P→M), completeness (M→P), and bidirectional
    sums without Python-level loops.
    """

    if points.ndim != 3:
        raise ValueError(f"Expected batched points of shape (C,P,3); got {tuple(points.shape)}")

    bsz, max_p, _ = points.shape
    lengths = lengths.clamp(max=max_p)

    mask = torch.arange(max_p, device=points.device).unsqueeze(0) < lengths.unsqueeze(1)
    points_packed = points[mask]  # (Ptot, 3)

    points_first_idx = torch.zeros(bsz, device=points.device, dtype=torch.int64)
    points_first_idx[1:] = lengths.cumsum(0)[:-1]
    max_points = int(lengths.max().item())
    point_to_cloud_idx = torch.repeat_interleave(torch.arange(bsz, device=points.device), lengths)

    v = gt_verts.shape[0]
    f = gt_faces.shape[0]
    verts_packed = gt_verts.repeat(bsz, 1)
    face_offsets = torch.arange(bsz, device=gt_faces.device, dtype=gt_faces.dtype).unsqueeze(1) * v
    faces_packed = (gt_faces.unsqueeze(0) + face_offsets.unsqueeze(-1)).reshape(-1, 3)
    tris = verts_packed[faces_packed]
    tris_first_idx = torch.arange(0, bsz * f, f, device=points.device, dtype=torch.int64)
    max_tris = f
    tri_to_mesh_idx = torch.repeat_interleave(torch.arange(bsz, device=points.device), f)
    num_tris_per_mesh = torch.full((bsz,), f, device=points.device, dtype=points.dtype)

    point_to_face = point_face_distance(
        points_packed, points_first_idx, tris, tris_first_idx, max_points, _DEFAULT_MIN_TRIANGLE_AREA
    )
    num_points_per_cloud = lengths.to(points.dtype).clamp(min=1)
    weights_p = 1.0 / num_points_per_cloud.gather(0, point_to_cloud_idx).float()
    acc = torch.zeros(bsz, device=points.device, dtype=points.dtype)
    acc.scatter_add_(0, point_to_cloud_idx, point_to_face * weights_p)

    face_to_point = face_point_distance(
        points_packed, points_first_idx, tris, tris_first_idx, max_tris, _DEFAULT_MIN_TRIANGLE_AREA
    )
    weights_t = 1.0 / num_tris_per_mesh.gather(0, tri_to_mesh_idx).float()
    comp = torch.zeros(bsz, device=points.device, dtype=points.dtype)
    comp.scatter_add_(0, tri_to_mesh_idx, face_to_point * weights_t)

    return DistanceBreakdown(
        accuracy=acc,
        completeness=comp,
        bidirectional=acc + comp,
    )


__all__ = [
    "chamfer_point_mesh",
    "chamfer_point_mesh_batched",
    "DistanceBreakdown",
]
