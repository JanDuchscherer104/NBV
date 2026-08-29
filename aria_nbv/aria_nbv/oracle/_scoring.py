r"""Private prepared point-mesh scoring shared by Oracle facades.

This module receives caller-prepared scene or target evidence, computes point-mesh
distances, renders/backprojects candidate evidence when requested, and delegates
the RRI formula to :mod:`aria_nbv.rri_metrics.rri`. Sampling, scene/target crop
selection, and hard-validity policy remain with callers; this module owns only
the shared prepared-scoring boundary.

The implemented scalar score is

$$
\mathrm{RRI}(q) =
\frac{\Delta(P_t, M) - \Delta(P_t \cup P_q, M)}
     {\max(\Delta(P_t, M), \epsilon)}
$$

where $\Delta$ is the configured point-mesh error. Target-specific callers pass
target-cropped points and meshes; invalid crops raise upstream and must not be
silently converted to scene-level labels.

In the thesis target-first pipeline, ASE evaluation depth, rendered candidate
depth, and matched GT mesh crops are oracle-only supervision. Actor-visible VIN
features remain outside this module. Candidate invalidity is likewise owned by
the upstream hard mask: a finite negative RRI is low utility, not invalidity.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
from pydantic import Field

from ..geometry import PreparedMeshQuery
from ..geometry.point_mesh import tensor_identity_token
from ..rendering.candidate_depth_renderer import CandidateDepthRendererConfig, CandidateDepths
from ..rendering.candidate_pointclouds import CandidatePointClouds, build_candidate_pointclouds
from ..rri_metrics.point_mesh import (
    DistanceBreakdown,
    chamfer_prepared_point_mesh,
    chamfer_prepared_point_mesh_batched,
)
from ..rri_metrics.rri import RriResult, compute_rri
from ..utils.base_config import TargetConfig
from .evidence import (
    OracleRriState,
    RootEvalPointCloud,
    RriEvaluationPointCloudSource,
    _eval_depth_far_m,
    _root_evidence_token,
    build_root_eval_pointcloud,
    canonical_fuse_points,
)

if TYPE_CHECKING:
    from ..data_handling import EfmSnippetView
    from ..pose_generation.types import CandidateSamplingResult


class PreparedRriScorerConfig(TargetConfig["PreparedRriScorer"]):
    """Configure prepared point-mesh RRI scoring shared by Oracle facades."""

    @property
    def target_type(self) -> type["PreparedRriScorer"]:
        """Return the prepared scorer constructed by ``setup_target()``."""

        return PreparedRriScorer

    fusion_voxel_size_m: float = Field(default=0.0, ge=0.0)
    """Voxel edge length in metres for deterministic fusion; ``0`` disables voxel aggregation."""

    fusion_max_points: int | None = Field(default=None, ge=1)
    """Optional point cap applied after fusion, with candidate evidence reserved in capped unions."""

    candidate_mesh_batch_size: int = Field(default=8, ge=1)
    """Maximum candidates sharing one materialized mesh batch in PyTorch3D."""


@dataclass(slots=True)
class _PreparedRriReference:
    """Current evidence and baseline evaluated against one prepared mesh."""

    points_t: torch.Tensor
    mesh: PreparedMeshQuery
    dist_before: DistanceBreakdown


@dataclass(slots=True)
class _PreparedRriMesh:
    """Prepared crop plus strong references that keep identity tokens unique."""

    sources: tuple[torch.Tensor, torch.Tensor]
    mesh: PreparedMeshQuery


_MESH_CACHE_SIZE = 2


class PreparedRriScorer:
    r"""Compute geometry-grounded oracle labels for candidate views.

    Conceptual steps:
        1. Merge ``P_t`` (current eval points) with candidate view point cloud
           ``P_q`` to obtain ``P_{t∪q}``.
        2. (Optional) Voxel-downsample both ``P_t`` and ``P_{t∪q}`` to ensure
           comparable density when evaluating point-mesh distances.
        3. Compute accuracy/completeness distances to the GT mesh using the
           PyTorch3D backend.
        4. Form $\mathrm{RRI}=(d_\mathrm{before}-d_\mathrm{after}) /
           \max(d_\mathrm{before},10^{-12})$ and return diagnostics.

    The facade scores geometry only; it does not decide whether a candidate is
    a legal action. In particular, a zero-length candidate point cloud produces
    zero improvement, while upstream masks and reason codes decide whether that
    row is valid supervision.
    """

    config: PreparedRriScorerConfig

    def __init__(self, config: PreparedRriScorerConfig) -> None:
        self.config = config
        self._mesh_cache: OrderedDict[tuple[object, ...], _PreparedRriMesh] = OrderedDict()

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
        r"""Compute candidate-aligned oracle RRI labels in one forward pass.

        Args:
            points_t ``Tensor["P_t 3", float32]``: Current evaluation points
                in world frame, metres. Thesis labels use the observed-prefix
                ASE GT-depth root rather than actor-visible MPS geometry.
            points_q ``Tensor["C P_q 3", float32]``: Padded oracle-rendered
                candidate point clouds in world frame, metres.
            lengths_q ``Tensor["C", int64]``: Valid point count for each
                candidate row in `points_q`.
            gt_verts ``Tensor["V 3", float32]``: Oracle-only GT mesh vertices
                in world frame, metres.
            gt_faces ``Tensor["F 3", int64]``: Triangle indices into
                `gt_verts`.
            extend ``Tensor["6", float32]``: World-frame target AABB
                ``[xmin, xmax, ymin, ymax, zmin, zmax]`` in metres. Faces with
                any vertex inside the box are retained.

        Returns:
            :class:`RriResult` with ``Tensor["C", float32]`` dimensionless RRI
            labels and squared-distance diagnostics in square metres.

        Theory:
            For candidate $q$, this computes

            $$
            \mathrm{RRI}(q)=\frac{D(P_t,M)-D(P_t\cup P_q,M)}
                                  {\max(D(P_t,M),10^{-12})}.
            $$

            Values may be negative. Invalid actions must be excluded through
            the caller's hard-validity contract, not assigned a low RRI.
        """

        reference = self._prepare_reference(
            points_t=points_t,
            gt_verts=gt_verts,
            gt_faces=gt_faces,
            extend=extend,
        )
        lengths_q = lengths_q.to(device=points_q.device)
        if self.config.fusion_voxel_size_m > 0.0 or self.config.fusion_max_points is not None:
            points_tq, lengths_tq = _canonical_fused_unions(
                points_t=reference.points_t,
                points_q=points_q,
                lengths_q=lengths_q,
                voxel_size_m=float(self.config.fusion_voxel_size_m),
                max_points=self.config.fusion_max_points,
            )
        else:
            num_t = reference.points_t.shape[0]
            points_t_exp = reference.points_t.unsqueeze(0).expand(points_q.shape[0], num_t, 3)
            points_tq = torch.cat([points_t_exp, points_q], dim=1)
            lengths_tq = lengths_q + num_t

        dist_after = chamfer_prepared_point_mesh_batched(
            points_tq,
            lengths_tq,
            reference.mesh,
            candidate_chunk_size=int(self.config.candidate_mesh_batch_size),
        )

        return compute_rri(reference.dist_before, dist_after)

    def _prepare_reference(
        self,
        *,
        points_t: torch.Tensor,
        gt_verts: torch.Tensor,
        gt_faces: torch.Tensor,
        extend: torch.Tensor,
    ) -> _PreparedRriReference:
        """Evaluate current evidence while reusing only stable target geometry."""

        fused_points = canonical_fuse_points(
            points_t,
            voxel_size_m=float(self.config.fusion_voxel_size_m),
            max_points=self.config.fusion_max_points,
        )
        mesh = self._prepare_mesh(
            gt_verts=gt_verts,
            gt_faces=gt_faces,
            extend=extend,
            device=fused_points.device,
            dtype=fused_points.dtype,
        )
        return _PreparedRriReference(
            points_t=fused_points,
            mesh=mesh,
            dist_before=chamfer_prepared_point_mesh(
                fused_points,
                mesh,
            ),
        )

    def _prepare_mesh(
        self,
        *,
        gt_verts: torch.Tensor,
        gt_faces: torch.Tensor,
        extend: torch.Tensor,
        device: torch.device,
        dtype: torch.dtype,
    ) -> PreparedMeshQuery:
        """Reuse one of the two most recent immutable target-mesh crops."""

        verts_token = tensor_identity_token(gt_verts)
        faces_token = tensor_identity_token(gt_faces)
        cache_key: tuple[object, ...] | None = None
        if verts_token is not None and faces_token is not None:
            cache_key = (
                verts_token,
                faces_token,
                tuple(float(value) for value in extend.detach().cpu().tolist()),
                device,
                dtype,
            )
            cached = self._mesh_cache.pop(cache_key, None)
            if cached is not None:
                self._mesh_cache[cache_key] = cached
                return cached.mesh

        gt_verts_crop, gt_faces_crop = _crop_mesh_to_aabb(gt_verts, gt_faces, extend)
        mesh = PreparedMeshQuery(
            gt_verts_crop,
            gt_faces_crop,
            device=device,
            dtype=dtype,
        )
        if cache_key is not None:
            self._mesh_cache[cache_key] = _PreparedRriMesh(sources=(gt_verts, gt_faces), mesh=mesh)
            while len(self._mesh_cache) > _MESH_CACHE_SIZE:
                self._mesh_cache.popitem(last=False)
        return mesh


class _CandidateRriScoringEngine:
    """Share render, backprojection, root evidence, fusion, and prepared scoring."""

    def __init__(
        self,
        *,
        sample: EfmSnippetView,
        depth: CandidateDepthRendererConfig,
        oracle: PreparedRriScorerConfig,
        backprojection_stride: int,
        eval_point_cloud_source: RriEvaluationPointCloudSource,
        eval_camera_label: str,
        eval_depth_far_m: float | None,
        eval_fusion_voxel_size_m: float,
    ) -> None:
        self.sample = sample
        self.backprojection_stride = int(backprojection_stride)
        self.eval_point_cloud_source = eval_point_cloud_source
        self.eval_camera_label = eval_camera_label
        self.eval_depth_far_m = eval_depth_far_m
        self.eval_fusion_voxel_size_m = float(eval_fusion_voxel_size_m)
        self._depth_renderer = depth.setup_target()
        self._prepared_rri = oracle.setup_target()
        self._root_eval: RootEvalPointCloud | None = None
        self._root_eval_token: tuple[float, ...] | None = None

    def render_candidate_points(self, candidates: CandidateSamplingResult) -> CandidatePointClouds:
        """Render and backproject one valid candidate table."""

        return self.backproject_candidate_points(self.render_candidate_depths(candidates))

    def render_candidate_depths(self, candidates: CandidateSamplingResult) -> CandidateDepths:
        """Render candidate depths from privileged scene geometry."""

        return self._depth_renderer.render(self.sample, candidates)

    def backproject_candidate_points(self, depths: CandidateDepths) -> CandidatePointClouds:
        """Backproject rendered candidate depths into world-frame points."""

        return build_candidate_pointclouds(self.sample, depths, stride=self.backprojection_stride)

    def current_eval_points(
        self,
        state: OracleRriState,
        *,
        device: torch.device,
        dtype: torch.dtype,
        max_points: int | None,
    ) -> torch.Tensor:
        """Fuse root evidence with selected-history points."""

        points_t = self._root_eval_for(state).points_world.to(device=device, dtype=dtype)
        history_points = state.accumulated_points_world()
        if history_points.numel() > 0:
            points_t = torch.cat([points_t, history_points.to(device=device, dtype=dtype)], dim=0)
        return canonical_fuse_points(
            points_t,
            voxel_size_m=self.eval_fusion_voxel_size_m,
            max_points=max_points,
        )

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
        """Delegate already prepared evidence to the point-mesh scorer."""

        return self._prepared_rri.score(
            points_t=points_t,
            points_q=points_q,
            lengths_q=lengths_q,
            gt_verts=gt_verts,
            gt_faces=gt_faces,
            extend=extend,
        )

    def _root_eval_for(self, state: OracleRriState) -> RootEvalPointCloud:
        token = _root_evidence_token(
            state.root_pose_world,
            root_time_ns=state.root_time_ns,
            root_trajectory_index=state.root_trajectory_index,
            root_frame_index=state.root_frame_index,
        )
        if self._root_eval is None or self._root_eval_token != token:
            self._root_eval = build_root_eval_pointcloud(
                self.sample,
                source=self.eval_point_cloud_source,
                camera_label=self.eval_camera_label,  # type: ignore[arg-type]
                reference_pose_world=state.root_pose_world,
                reference_time_ns=state.root_time_ns,
                reference_trajectory_index=state.root_trajectory_index,
                reference_frame_index=state.root_frame_index,
                stride=self.backprojection_stride,
                far_m=_eval_depth_far_m(
                    source=self.eval_point_cloud_source,
                    configured=self.eval_depth_far_m,
                    depth_renderer=self._depth_renderer,
                ),
                voxel_size_m=self.eval_fusion_voxel_size_m,
                max_points=None,
            )
            self._root_eval_token = token
        return self._root_eval


def _root_error_tensor(
    value: float | None,
    *,
    fallback: torch.Tensor,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    """Resolve a persisted root error or use the current state's first error."""

    if value is None:
        return fallback.reshape(-1)[0].to(device=device, dtype=dtype)
    return torch.tensor(float(value), device=device, dtype=dtype)


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
    row_lengths = lengths_q.to(dtype=torch.long).clamp(min=0, max=points_q.shape[1]).detach().cpu().tolist()
    for row_index, q_length in enumerate(row_lengths):
        q_len = int(q_length)
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


__all__ = ["PreparedRriScorer", "PreparedRriScorerConfig"]
