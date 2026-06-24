"""Shared context methods for VIN scorer model variants.

`PoseFeatureGlobalContextMixin` is private glue for
`aria_nbv.vin.models.v2.VinModelV2` and `aria_nbv.vin.models.v3.VinModelV3`.
It keeps the trainable modules owned by the concrete model classes while
delegating the repeated pose encoding and global-context tensor contracts to
`aria_nbv.vin.scorer_context`.
"""

from __future__ import annotations

from typing import Any

from efm3d.aria.pose import PoseTW
from torch import Tensor

from ..geometry.semidense_schema import semidense_proj_feature_index
from ..scorer_context import (
    apply_vin_scorer_film,
    build_vin_scorer_scene_field,
    compute_global_context,
    encode_pose_features,
)


class PoseFeatureGlobalContextMixin:
    """Private pose/context method bridge for concrete VIN scorer modules.

    The mixin assumes the receiving model owns ``pose_encoder`` and
    ``global_pooler`` attributes with the contracts expected by
    `aria_nbv.vin.scorer_context.encode_pose_features` and
    `aria_nbv.vin.scorer_context.compute_global_context`. It intentionally owns
    no parameters, buffers, or configuration so moving it does not affect model
    state dict keys.
    """

    def _encode_pose_features(
        self: Any,
        pose_world_cam: PoseTW,
        pose_world_rig_ref: PoseTW,
    ):
        """Encode candidate camera poses relative to the reference rig pose.

        Parameters
        ----------
        pose_world_cam:
            Candidate camera poses as an EFM3D `PoseTW` batch.
        pose_world_rig_ref:
            Reference rig pose used to express candidate motion features.

        Returns
        -------
        Tensor
            Pose-feature tensor produced by the concrete model's
            ``pose_encoder``.
        """
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
        """Pool scene-field evidence into a per-candidate global context.

        Parameters
        ----------
        field:
            Dense scene feature field with shape ``(B, C, D, H, W)``.
        pose_enc:
            Encoded candidate pose tensor with shape ``(B, K, C_pose)``.
        pts_world:
            World-space voxel or frustum sample points consumed by the
            concrete global pooler.
        t_world_voxel:
            Transform from voxel coordinates to the world frame.
        pose_world_rig_ref:
            Reference rig pose for candidate-relative pooling.
        voxel_extent:
            Physical voxel-field extent in meters.

        Returns
        -------
        Tensor
            Per-candidate global-context features produced by
            ``self.global_pooler``.
        """
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
    _build_vin_scorer_scene_field = staticmethod(build_vin_scorer_scene_field)
    _apply_film = staticmethod(apply_vin_scorer_film)


__all__ = ["PoseFeatureGlobalContextMixin"]
