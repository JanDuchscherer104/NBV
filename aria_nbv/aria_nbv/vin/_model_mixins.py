"""Shared method mixins for VIN model variants.

These wrappers sit one layer above `aria_nbv.vin.vin_utils`: they bridge
model-owned members such as ``self.pose_encoder``, ``self.global_pooler``, and
``self.config`` into the stateless tensor helpers without repeating identical
method bodies across VIN generations.
"""

from __future__ import annotations

from typing import Any

from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from torch import Tensor

from .geometry import ensure_candidate_batch, frustum_points_world_from_cameras, semidense_proj_feature_index
from .vin_utils import (
    compute_global_context,
    encode_pose_features,
)


class PoseFeatureGlobalContextMixin:
    """Shared pose/context helper methods for VIN v2/v3 style models."""

    def _encode_pose_features(
        self: Any,
        pose_world_cam: PoseTW,
        pose_world_rig_ref: PoseTW,
    ):
        """Encode candidate poses in the reference rig frame."""
        return encode_pose_features(
            pose_encoder=self.pose_encoder,
            pose_world_cam=pose_world_cam,
            pose_world_rig_ref=pose_world_rig_ref,
        )

    def _compute_global_context(
        self: Any,
        field: Tensor,
        pose_enc: Tensor,
        *,
        pts_world: Tensor,
        t_world_voxel: PoseTW,
        pose_world_rig_ref: PoseTW,
        voxel_extent: Tensor,
    ):
        """Compute pose-conditioned global features from the scene field."""
        return compute_global_context(
            global_pooler=self.global_pooler,
            field=field,
            pose_enc=pose_enc,
            pts_world=pts_world,
            t_world_voxel=t_world_voxel,
            pose_world_rig_ref=pose_world_rig_ref,
            voxel_extent=voxel_extent,
        )

    _semidense_proj_feature_index = staticmethod(semidense_proj_feature_index)


class FrustumSamplingMixin:
    """Shared frustum sampling helpers for legacy experimental VIN variants."""

    def _frustum_points_world(
        self: Any,
        poses_world_cam: PoseTW,
        *,
        p3d_cameras: PerspectiveCameras,
    ) -> Tensor:
        """Generate frustum sample points in world coordinates for each candidate."""
        return frustum_points_world_from_cameras(
            poses_world_cam,
            p3d_cameras=p3d_cameras,
            grid_size=self.config.frustum_grid_size,
            depths_m=self.config.frustum_depths_m,
        )

    _ensure_candidate_batch = staticmethod(ensure_candidate_batch)


__all__ = ["FrustumSamplingMixin", "PoseFeatureGlobalContextMixin"]
