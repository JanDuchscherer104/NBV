"""Mask-preserving pruning rules for finite candidate pose generation.

Rules inspect the full sampled shell and update its aligned boolean validity
mask in place. They never compact candidate rows, which preserves provenance
and makes invalid actions distinguishable from merely low-value actions.

This module provides the :class:`Rule` protocol, shared rule base, and concrete
mesh-clearance, path-collision, motion-realism, and free-space checks. Candidate
generation owns rule ordering and mask aggregation; renderers and RRI scorers
consume the resulting valid set but do not reinterpret rejected rows as scores.
"""

from __future__ import annotations

import importlib
from math import radians
from typing import TYPE_CHECKING, Protocol

import torch
import trimesh  # type: ignore[import-untyped]

from ..utils import Console
from ..utils.frames import world_up_tensor
from .geometry import point_mesh_distance
from .types import CandidateContext, CollisionBackend

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

    from .candidate_generation import CandidateViewGeneratorConfig


class Rule(Protocol):
    """Protocol for one full-shell, mask-preserving candidate validity rule."""

    def __call__(self, ctx: CandidateContext) -> None: ...


class RuleBase:
    """Shared utilities for pruning rules (logging and mask helpers)."""

    def __init__(self, config: "CandidateViewGeneratorConfig"):
        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__)
        self._warned_backend = False

    def warn_once(self, message: str) -> None:
        """Emit at most one backend-fallback warning per rule instance."""
        if not self._warned_backend:
            self.console.warn(message)
            self._warned_backend = True


class MinDistanceToMeshRule(RuleBase):
    r"""Reject candidates whose centers are too close to the GT mesh.

    For each candidate center $c_i$ and mesh $\mathcal{M}$, this rule computes the distance

    $$
    d_i = \min_{x \in \mathcal{M}} \lVert c_i - x \rVert_2
    $$

    and rejects candidates with $d_i \leq \text{min_distance_to_mesh}$.

    When `cfg.collect_debug_stats` is True, the per-candidate distances are stored as
    `ctx.debug['min_distance_to_mesh']` for later analysis.
    """

    def __init__(self, config: "CandidateViewGeneratorConfig"):
        super().__init__(config)

    def __call__(self, ctx: CandidateContext) -> None:
        """Mark candidates closer than threshold to the mesh as invalid.

        Updates `ctx.mask_valid` in place and records `min_distance_to_mesh` in `ctx.debug`
        when `collect_debug_stats` is enabled.
        """
        if ctx.centers_world is None or ctx.mask_valid is None:
            return
        if ctx.gt_mesh is None:
            if ctx.cfg.collect_debug_stats:
                false = torch.zeros_like(ctx.mask_valid)
                ctx.mark_debug("path_collision_applicable_mask", false)
                ctx.mark_debug("path_collision_evaluated_mask", false)
                ctx.mark_debug("path_collision_detected", false)
                ctx.mark_debug("path_collision_mask", false)
            return

        need_distance = self.config.min_distance_to_mesh > 0 or ctx.cfg.collect_debug_stats
        if not need_distance:
            return

        positions = ctx.centers_world
        backend = self.config.collision_backend

        if backend == CollisionBackend.P3D and ctx.mesh_verts is not None and ctx.mesh_faces is not None:
            dist_t = (
                ctx.mesh_query.point_distance(positions)
                if ctx.mesh_query is not None
                else point_mesh_distance(positions, ctx.mesh_verts, ctx.mesh_faces)
            )
        else:
            try:
                if ctx.mesh_query is not None:
                    dist_t = ctx.mesh_query.signed_distance(positions)
                else:
                    query = trimesh.proximity.ProximityQuery(ctx.gt_mesh)
                    dist_np = query.signed_distance(positions.detach().cpu().numpy())
                    dist_t = torch.from_numpy(dist_np).to(positions.device, positions.dtype).abs()
            except ModuleNotFoundError:
                verts = torch.as_tensor(ctx.gt_mesh.vertices, device=positions.device, dtype=torch.float32)
                faces = torch.as_tensor(ctx.gt_mesh.faces, device=positions.device, dtype=torch.int64)
                dist_t = point_mesh_distance(positions, verts, faces)

        if ctx.cfg.collect_debug_stats:
            ctx.mark_debug("min_distance_to_mesh", dist_t)

        if self.config.min_distance_to_mesh > 0:
            keep = dist_t > self.config.min_distance_to_mesh
            ctx.mask_valid = ctx.mask_valid & keep


class PathCollisionRule(RuleBase):
    """Reject candidates whose straight-line path from reference hits the mesh.

    This rule enforces that the straight segment from the reference rig position to each candidate center does not
    intersect the mesh, optionally with a configurable clearance.

    Depending on `CollisionBackend`, collision checks are implemented either by discretised distance sampling
    (PyTorch3D) or by analytic ray-mesh intersection tests (Trimesh / PyEmbree).

    The method:

    1. Returns early if no mesh is available or the step clearance is non-positive.
    2. Constructs a ray from the reference position to each candidate center.
    3. Depending on `config.collision_backend`:

        * `CollisionBackend.P3D`:
            discretise each segment into ``ray_subsample`` points, compute distances via `point_mesh_distance`,
            and mark collisions where any sample falls below ``step_clearance``.
        * `CollisionBackend.TRIMESH` / `CollisionBackend.PYEMBREE`:
            cast rays with maximum distance equal to the segment length and use the ray engine's
            `intersects_any` to identify collisions.

    4. Records the boolean collision mask in ``ctx.debug['path_collision_mask']`` when debug stats are enabled.
    5. Calls `CandidateContext.invalidate` to apply the collision mask as a rejection mask.
    """

    def __init__(self, config: "CandidateViewGeneratorConfig"):
        super().__init__(config)
        self._pyembree_available = False
        if self.config.collision_backend == CollisionBackend.PYEMBREE:
            try:
                importlib.import_module("trimesh.ray.ray_pyembree")
                self._pyembree_available = True
            except ModuleNotFoundError:
                self._pyembree_available = False

    def __call__(self, ctx: CandidateContext) -> None:
        """Reject candidates whose straight-line path from reference to center intersects the mesh."""
        if ctx.gt_mesh is None or ctx.centers_world is None or ctx.mask_valid is None:
            return

        if ctx.cfg.collect_debug_stats:
            count = ctx.centers_world.shape[0]
            false = torch.zeros(count, device=ctx.centers_world.device, dtype=torch.bool)
            applicable = torch.ones_like(false)
            ctx.mark_debug("path_collision_applicable_mask", applicable)
            ctx.mark_debug("path_collision_applicable", applicable)
            ctx.mark_debug("path_collision_evaluated_mask", false)
            ctx.mark_debug("path_collision_evaluated", false)
            ctx.mark_debug("path_collision_detected", false)

        if self.config.step_clearance <= 0:
            return

        origin = ctx.reference_pose.t.view(1, 3)
        targets = ctx.centers_world
        dirs = targets - origin
        dists = dirs.norm(dim=1).clamp_min(1e-6)
        dirs_norm = dirs / dists.unsqueeze(1)

        backend = self.config.collision_backend

        eligible = ctx.mask_valid.clone()
        eligible_indices = torch.nonzero(eligible, as_tuple=False).reshape(-1)
        if eligible_indices.numel() == 0:
            return
        if backend == CollisionBackend.P3D and ctx.mesh_verts is not None and ctx.mesh_faces is not None:
            steps = max(2, int(self.config.ray_subsample))
            t_vals = torch.linspace(0.0, 1.0, steps, device=targets.device, dtype=targets.dtype)
            eligible_dirs = dirs_norm[eligible_indices]
            eligible_dists = dists[eligible_indices]
            pts = origin.view(1, 1, 3) + eligible_dirs.unsqueeze(1) * (
                t_vals.view(1, -1, 1) * eligible_dists.view(-1, 1, 1)
            )
            pts_flat = pts.reshape(-1, 3)
            dists_pts = (
                ctx.mesh_query.point_distance(pts_flat)
                if ctx.mesh_query is not None
                else point_mesh_distance(pts_flat, ctx.mesh_verts, ctx.mesh_faces)
            ).view(eligible_indices.shape[0], steps)
            min_clearance = dists_pts.min(dim=1).values
            collide = (dists_pts < self.config.step_clearance).any(dim=1)
            if ctx.cfg.collect_debug_stats:
                evaluated = torch.zeros_like(eligible)
                evaluated[eligible_indices] = True
                detected = torch.zeros_like(eligible)
                detected[eligible_indices] = collide
                clearance = torch.full_like(dists, float("nan"))
                clearance[eligible_indices] = min_clearance
                ctx.mark_debug("path_collision_evaluated_mask", evaluated)
                ctx.mark_debug("path_collision_evaluated", evaluated)
                ctx.mark_debug("path_collision_detected", detected)
                ctx.mark_debug("path_collision_mask", detected)
                ctx.mark_debug("path_min_clearance_m", clearance)
            ctx.invalidate(torch.zeros_like(ctx.mask_valid).scatter(0, eligible_indices, collide))
            return

        origins_np = origin.expand_as(targets[eligible_indices]).detach().cpu().numpy()
        dirs_np = dirs_norm[eligible_indices].detach().cpu().numpy()
        max_dist = dists[eligible_indices].detach().cpu().numpy()
        ray_engine = ctx.mesh_query.ray_engine(use_pyembree=False) if ctx.mesh_query is not None else ctx.gt_mesh.ray
        if backend == CollisionBackend.PYEMBREE and self._pyembree_available:
            if ctx.mesh_query is not None:
                ray_engine = ctx.mesh_query.ray_engine(use_pyembree=True)
            else:
                from trimesh.ray.ray_pyembree import RayMeshIntersector  # type: ignore

                ray_engine = RayMeshIntersector(ctx.gt_mesh)
        elif backend == CollisionBackend.PYEMBREE and not self._pyembree_available:
            self.warn_once("pyembree not available; falling back to trimesh ray engine.")

        intersects = ray_engine.intersects_any(origins_np, dirs_np, multiple_hits=False, max_distance=max_dist)
        collide = torch.from_numpy(intersects).to(ctx.mask_valid.device)
        if ctx.cfg.collect_debug_stats:
            evaluated = torch.zeros_like(eligible)
            evaluated[eligible_indices] = True
            detected = torch.zeros_like(eligible)
            detected[eligible_indices] = collide
            ctx.mark_debug("path_collision_evaluated_mask", evaluated)
            ctx.mark_debug("path_collision_evaluated", evaluated)
            ctx.mark_debug("path_collision_detected", detected)
            ctx.mark_debug("path_collision_mask", detected)
        rejection = torch.zeros_like(ctx.mask_valid)
        rejection[eligible_indices] = collide
        ctx.invalidate(rejection)


class MotionRealismRule(RuleBase):
    """Reject candidates that violate local egocentric motion bounds."""

    def __call__(self, ctx: CandidateContext) -> None:
        """Apply step, height, backward-motion, and yaw-change constraints."""

        if ctx.centers_world is None or ctx.mask_valid is None or ctx.shell_poses is None:
            return

        reject = torch.zeros(ctx.centers_world.shape[0], device=ctx.centers_world.device, dtype=torch.bool)
        offsets_ref = ctx.shell_offsets_ref
        if offsets_ref is None:
            offsets_ref = ctx.reference_pose.inverse().transform(ctx.centers_world)

        step_length = torch.linalg.norm(offsets_ref, dim=1)
        if ctx.cfg.collect_debug_stats:
            ctx.mark_debug("motion_step_length_m", step_length)
        if self.config.max_step_distance_m is not None:
            reject |= step_length > float(self.config.max_step_distance_m)

        world_up = world_up_tensor(device=ctx.centers_world.device, dtype=ctx.centers_world.dtype)
        height_delta = ((ctx.centers_world - ctx.reference_pose.t.reshape(1, 3)) * world_up).sum(dim=1).abs()
        if ctx.cfg.collect_debug_stats:
            ctx.mark_debug("motion_height_delta_m", height_delta)
        if self.config.max_height_delta_m is not None:
            reject |= height_delta > float(self.config.max_height_delta_m)

        backward_step = (-offsets_ref[:, 2]).clamp_min(0.0)
        if ctx.cfg.collect_debug_stats:
            ctx.mark_debug("motion_backward_step_m", backward_step)
        if self.config.max_backward_step_m is not None:
            reject |= backward_step > float(self.config.max_backward_step_m)

        yaw_delta = _forward_yaw_delta(ctx.sampling_pose, ctx.shell_poses)
        if ctx.cfg.collect_debug_stats:
            ctx.mark_debug("motion_yaw_delta_rad", yaw_delta)
        if self.config.max_yaw_delta_deg is not None:
            reject |= yaw_delta > radians(float(self.config.max_yaw_delta_deg))

        if ctx.cfg.collect_debug_stats:
            ctx.mark_debug("motion_realism_reject_mask", reject)
        ctx.invalidate(reject)


def _forward_yaw_delta(reference_pose: "PoseTW", shell_poses: "PoseTW") -> torch.Tensor:
    """Return horizontal forward-axis angle from reference to shell poses."""

    ref_forward = reference_pose.R.reshape(-1, 3, 3)[0, :, 2]
    cand_forward = shell_poses.R.reshape(-1, 3, 3)[:, :, 2]
    world_up = world_up_tensor(device=ref_forward.device, dtype=ref_forward.dtype)
    ref_h = ref_forward - (ref_forward * world_up).sum() * world_up
    cand_h = cand_forward - (cand_forward * world_up.reshape(1, 3)).sum(dim=1, keepdim=True) * world_up
    ref_h_norm = ref_h.norm()
    cand_h_norm = cand_h.norm(dim=1)
    ref_h = ref_h / ref_h_norm.clamp_min(1e-8)
    cand_h = cand_h / cand_h_norm.reshape(-1, 1).clamp_min(1e-8)
    horizontal_cos = (cand_h * ref_h.reshape(1, 3)).sum(dim=1)
    full_cos = (cand_forward * ref_forward.reshape(1, 3)).sum(dim=1)
    use_full_axes = (ref_h_norm < 1e-8) | (cand_h_norm < 1e-8)
    cos = torch.where(use_full_axes, full_cos, horizontal_cos).clamp(-1.0, 1.0)
    return torch.acos(cos)


class FreeSpaceRule(RuleBase):
    """Restrict candidate centers to a world-space AABB."""

    def __init__(self, config: "CandidateViewGeneratorConfig"):
        super().__init__(config)

    def __call__(self, ctx: CandidateContext) -> None:
        """Keep only candidates inside the configured occupancy extent (AABB)."""
        if ctx.occupancy_extent is None or ctx.centers_world is None or ctx.mask_valid is None:
            return

        extent = ctx.occupancy_extent.to(ctx.centers_world.device)
        xmin, xmax, ymin, ymax, zmin, zmax = extent
        p = ctx.centers_world
        in_box = (
            (p[:, 0] >= xmin)
            & (p[:, 0] <= xmax)
            & (p[:, 1] >= ymin)
            & (p[:, 1] <= ymax)
            & (p[:, 2] >= zmin)
            & (p[:, 2] <= zmax)
        )
        if ctx.cfg.collect_debug_stats:
            lower = torch.stack((xmin - p[:, 0], ymin - p[:, 1], zmin - p[:, 2]), dim=1).clamp_min(0.0)
            upper = torch.stack((p[:, 0] - xmax, p[:, 1] - ymax, p[:, 2] - zmax), dim=1).clamp_min(0.0)
            outside_distance = torch.linalg.norm(lower + upper, dim=1)
            inside_margin = (
                torch.stack(
                    (
                        p[:, 0] - xmin,
                        xmax - p[:, 0],
                        p[:, 1] - ymin,
                        ymax - p[:, 1],
                        p[:, 2] - zmin,
                        zmax - p[:, 2],
                    ),
                    dim=1,
                )
                .min(dim=1)
                .values
            )
            ctx.mark_debug("free_space_margin_m", torch.where(in_box, inside_margin, -outside_distance))
        ctx.mask_valid = ctx.mask_valid & in_box


__all__ = ["Rule", "RuleBase", "MinDistanceToMeshRule", "MotionRealismRule", "PathCollisionRule", "FreeSpaceRule"]
