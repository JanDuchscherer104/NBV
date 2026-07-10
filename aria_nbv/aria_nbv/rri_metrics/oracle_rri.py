r"""High-level oracle RRI computation orchestrator.

This module wires together rendering outputs (candidate depth → point clouds),
distance primitives (see ``point_mesh.py``), and configuration defaults to produce
per-candidate Relative Reconstruction Improvement (RRI) scores as defined in
``docs/contents/theory/rri_theory.qmd``. The implementation is intentionally
kept modular:

* **Sampling / downsampling** is delegated to callers (or future helpers) so
  that density can be harmonised between ``P_t`` and ``P_{t∪q}``.
* **Distance evaluation** is performed via PyTorch3D on GPU for efficiency.
* **Config-as-factory** pattern is used to keep runtime objects
  serialisable and consistent with the rest of the codebase.

The implemented scalar score is

$$
\mathrm{RRI}(q) =
\frac{\Delta(P_t, M) - \Delta(P_t \cup P_q, M)}
     {\max(\Delta(P_t, M), \epsilon)}
$$

where $\Delta$ is the configured point-mesh error. Target-specific callers pass
target-cropped points and meshes; invalid crops raise upstream and must not be
silently converted to scene-level labels.
"""

from __future__ import annotations

import torch
from pydantic import Field

from aria_nbv.utils.base_config import TargetConfig

from .eval_pointclouds import canonical_fuse_points
from .point_mesh import chamfer_point_mesh, chamfer_point_mesh_batched
from .rri import RriResult, compute_rri


class OracleRRIConfig(TargetConfig["OracleRRI"]):
    """Config-as-factory wrapper for oracle RRI computation."""

    @property
    def target_type(self) -> type["OracleRRI"]:
        return OracleRRI

    fusion_voxel_size_m: float = Field(default=0.0, ge=0.0)
    """Optional deterministic voxel-fusion size for ``P_t`` and ``P_t ∪ P_q``."""

    fusion_max_points: int | None = Field(default=None, ge=1)
    """Optional deterministic point cap applied after voxel fusion."""


class OracleRRI:
    """Facade to compute oracle RRI for one or more candidates.

    Conceptual steps:
        1. Merge ``P_t`` (current eval points) with candidate view point cloud
           ``P_q`` to obtain ``P_{t∪q}``.
        2. (Optional) Voxel-downsample both ``P_t`` and ``P_{t∪q}`` to ensure
           comparable density when evaluating point-mesh distances.
        3. Compute accuracy/completeness distances to the GT mesh using the
           PyTorch3D backend.
        4. Form RRI = (d_before - d_after) / d_before and return diagnostics.
    """

    config: OracleRRIConfig

    def __init__(self, config: OracleRRIConfig) -> None:
        self.config = config

    def score(
        self,
        *,
        points_t: torch.Tensor,
        points_q: torch.Tensor,
        lengths_q: torch.Tensor,
        gt_verts: torch.Tensor,
        gt_faces: torch.Tensor,
        extend: torch.Tensor,
    ) -> RriResult:
        """Compute :class:`RriResult` for one or more candidates in a single forward pass.

        Args:
            points_t: ``Tensor['N_t', 3]`` current eval point cloud up to time *t*.
            points_q: ``Tensor['N_q', 3]`` candidate-view point cloud rendered from GT.
            gt_verts: ``Tensor['V', 3]`` ground-truth mesh vertices.
            gt_faces: ``Tensor['F', 3]`` ground-truth mesh face indices (int64).
            extend: ``Tensor[6]`` [xmin, xmax, ymin, ymax, zmin, zmax] AABB in world frame used to crop the GT mesh.
        Returns:
            :class:`RriResult` containing scalar RRI and distance breakdowns.
        """

        gt_verts_crop, gt_faces_crop = _crop_mesh_to_aabb(gt_verts, gt_faces, extend)
        lengths_q = lengths_q.to(device=points_q.device)

        points_t = canonical_fuse_points(
            points_t,
            voxel_size_m=float(self.config.fusion_voxel_size_m),
            max_points=self.config.fusion_max_points,
        )
        dist_before = chamfer_point_mesh(points_t, gt_verts_crop, gt_faces_crop)
        if self.config.fusion_voxel_size_m > 0.0 or self.config.fusion_max_points is not None:
            points_tq, lengths_tq = _canonical_fused_unions(
                points_t=points_t,
                points_q=points_q,
                lengths_q=lengths_q,
                voxel_size_m=float(self.config.fusion_voxel_size_m),
                max_points=self.config.fusion_max_points,
            )
        else:
            num_t = points_t.shape[0]
            points_t_exp = points_t.unsqueeze(0).expand(points_q.shape[0], num_t, 3)
            points_tq = torch.cat([points_t_exp, points_q], dim=1)
            lengths_tq = lengths_q + num_t

        dist_after = chamfer_point_mesh_batched(points_tq, lengths_tq, gt_verts_crop, gt_faces_crop)

        return compute_rri(dist_before, dist_after)

    def score_batch(
        self,
        *,
        points_t: torch.Tensor,
        points_q: torch.Tensor,
        lengths_q: torch.Tensor,
        gt_verts: torch.Tensor,
        gt_faces: torch.Tensor,
        extend: torch.Tensor,
    ) -> RriResult:
        """Alias kept for callers using the old batch name."""

        return self.score(
            points_t=points_t,
            points_q=points_q,
            lengths_q=lengths_q,
            gt_verts=gt_verts,
            gt_faces=gt_faces,
            extend=extend,
        )


def _crop_mesh_to_aabb(
    verts: torch.Tensor,
    faces: torch.Tensor,
    aabb: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Crop a mesh to an AABB with explicit empty-crop failure.

    The current crop contract keeps faces whose **any** vertex lies inside the
    world-frame box ``[xmin, xmax, ymin, ymax, zmin, zmax]``. Empty crops raise
    instead of silently falling back to full-scene scoring, because target-aware
    RRI must not turn a missing object crop into a scene-level label.
    """

    if aabb.numel() != 6:
        raise ValueError("extend must be Tensor[6] = [xmin, xmax, ymin, ymax, zmin, zmax]")

    bounds = aabb.reshape(6).to(device=verts.device, dtype=verts.dtype)
    lower = bounds[[0, 2, 4]]
    upper = bounds[[1, 3, 5]]
    if bool(torch.any(lower > upper).item()):
        raise ValueError("extend min bounds must be <= max bounds for x/y/z.")

    vmask = torch.all((verts >= lower) & (verts <= upper), dim=1)

    # Keep faces that intersect the AABB (coarse test via any-vertex-inside).
    fmask = vmask[faces].any(dim=1)
    faces_kept = faces[fmask]
    if faces_kept.numel() == 0:
        raise ValueError(
            "AABB crop produced no mesh faces; refusing to fall back to full-scene RRI.",
        )

    unique_idx, new_idx = torch.unique(faces_kept.reshape(-1), sorted=True, return_inverse=True)
    verts_crop = verts[unique_idx]
    faces_crop = new_idx.reshape(faces_kept.shape)
    return verts_crop, faces_crop


def _canonical_fused_unions(
    *,
    points_t: torch.Tensor,
    points_q: torch.Tensor,
    lengths_q: torch.Tensor,
    voxel_size_m: float,
    max_points: int | None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Fuse each ``P_t ∪ P_q`` row while reserving capped budget for ``P_q``.

    If ``P_t`` is already at the global point cap, fusing the raw union with
    the same cap can erase newly observed candidate evidence. The capped path
    therefore keeps a deterministic source-balanced slice: candidate points get
    all requested budget up to half of the cap, and root/current eval points get
    the remainder. This preserves candidate-added voxels while keeping the
    total distance batch bounded.
    """

    rows: list[torch.Tensor] = []
    lengths: list[int] = []
    for row_index in range(points_q.shape[0]):
        q_len = int(lengths_q[row_index].detach().cpu().item())
        query = canonical_fuse_points(points_q[row_index, :q_len, :3], voxel_size_m=voxel_size_m, max_points=None)
        if max_points is None:
            fused = canonical_fuse_points(
                torch.cat([points_t, query], dim=0),
                voxel_size_m=voxel_size_m,
                max_points=None,
            )
        else:
            fused = _source_balanced_capped_union(
                points_t=points_t,
                points_q=query,
                voxel_size_m=voxel_size_m,
                max_points=int(max_points),
            )
        rows.append(fused)
        lengths.append(int(fused.shape[0]))

    max_len = max(max(lengths), 1)
    padded = torch.zeros((points_q.shape[0], max_len, 3), device=points_q.device, dtype=points_q.dtype)
    for row_index, row in enumerate(rows):
        if row.numel() > 0:
            padded[row_index, : row.shape[0], :] = row
    return padded, torch.tensor(lengths, device=points_q.device, dtype=torch.long)


def _source_balanced_capped_union(
    *,
    points_t: torch.Tensor,
    points_q: torch.Tensor,
    voxel_size_m: float,
    max_points: int,
) -> torch.Tensor:
    """Return a deterministic capped union that cannot drop all query points."""

    if max_points < 1:
        raise ValueError("max_points must be positive when source-balanced union capping is requested.")
    root = canonical_fuse_points(points_t, voxel_size_m=voxel_size_m, max_points=None)
    query = canonical_fuse_points(points_q, voxel_size_m=voxel_size_m, max_points=None)
    if root.shape[0] + query.shape[0] <= max_points:
        return canonical_fuse_points(torch.cat([root, query], dim=0), voxel_size_m=0.0, max_points=None)
    if query.numel() == 0:
        return canonical_fuse_points(root, voxel_size_m=0.0, max_points=max_points)
    query_budget = min(int(query.shape[0]), max(1, min(max_points, max_points // 2)))
    root_budget = max(0, max_points - query_budget)
    root_keep = canonical_fuse_points(root, voxel_size_m=0.0, max_points=root_budget)
    query_keep = canonical_fuse_points(query, voxel_size_m=0.0, max_points=query_budget)
    return torch.cat([root_keep, query_keep], dim=0)


__all__ = ["OracleRRI", "OracleRRIConfig"]
