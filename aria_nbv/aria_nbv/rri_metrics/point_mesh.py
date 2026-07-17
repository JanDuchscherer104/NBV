r"""Low-level squared point--mesh distance primitives for oracle RRI.

This module wraps PyTorch3D geometric distance implementations so downstream
code can compute accuracy, completeness, and bidirectional distances in a
uniform, torch-first manner. Device support follows the installed PyTorch3D
backend; this module does not implement a separate fallback. Callers supply
pre-sampled point clouds and one shared mesh. Directional components are
returned separately to expose the accuracy/completeness split.

For a point set $P$ and mesh triangles $F$, `accuracy` averages the squared
distance from each point to its closest triangle, while `completeness` averages
the squared distance from each triangle to its closest point. The scalar error
is their sum. Metric-frame coordinates therefore yield square-metre values;
:class:`aria_nbv.oracle.PreparedRriScorer` normalizes their difference into
dimensionless RRI.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from pytorch3d.loss.point_mesh_distance import (  # type: ignore[import-untyped]
    _DEFAULT_MIN_TRIANGLE_AREA,
    face_point_distance,
    point_face_distance,
)
from torch import Tensor


@dataclass(slots=True)
class DistanceBreakdown:
    """Directional point-mesh distances produced by the Chamfer primitive."""

    accuracy: Tensor
    """Point-to-mesh distances from the reconstruction to ground truth."""

    completeness: Tensor
    """Mesh-to-point distances from ground truth to the reconstruction."""

    bidirectional: Tensor
    """Sum of accuracy and completeness."""


def chamfer_point_mesh(
    points: Tensor,
    gt_verts: Tensor,
    gt_faces: Tensor,
) -> DistanceBreakdown:
    r"""Compute directional mean-squared distances for one point cloud and mesh.

    Args:
        points ``Tensor["P 3", float32]``: Point cloud in the same metric
            coordinate frame as `gt_verts`, conventionally world frame metres.
        gt_verts ``Tensor["V 3", float32]``: Ground-truth mesh vertices in the
            common frame, metres.
        gt_faces ``Tensor["F 3", int64]``: Triangle vertex indices into
            `gt_verts`.

    Returns:
        :class:`DistanceBreakdown` of scalar ``Tensor["", float32]`` accuracy,
        completeness, and bidirectional errors in square metres.

    Theory:
        With $d^2(p,f)$ denoting squared point-to-triangle distance,

        $$
        D(P,M)=\frac{1}{|P|}\sum_{p\in P}\min_{f\in F}d^2(p,f)
        +\frac{1}{|F|}\sum_{f\in F}\min_{p\in P}d^2(p,f).
        $$

        The second term weights mesh triangles equally; it is not an
        area-weighted surface integral.
    """

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
    """Compute candidate-batched squared point--mesh distances.

    Args:
        points ``Tensor["C P_max 3", float32]``: Padded candidate point
            clouds in a common metric frame, conventionally world frame metres.
        lengths ``Tensor["C", int64]``: Valid point count for each candidate;
            padded rows beyond each count are ignored.
        gt_verts ``Tensor["V 3", float32]``: Shared ground-truth mesh vertices
            in the same frame, metres.
        gt_faces ``Tensor["F 3", int64]``: Shared triangle indices into
            `gt_verts`.

    Returns:
        :class:`DistanceBreakdown` whose fields are
        ``Tensor["C", float32]`` mean-squared errors in square metres. The
        candidate axis and input order are preserved.

    Notes:
        This primitive applies no candidate-validity mask. Callers must remove
        or mask invalid actions rather than interpreting their numeric distance
        as low utility.
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
