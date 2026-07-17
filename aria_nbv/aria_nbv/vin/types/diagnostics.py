"""Diagnostics payloads for active and legacy VIN scorer variants.

These dataclasses are canonical type owners even when the model producing them
is still a deprecated experimental scorer. App panels and diagnostics helpers
should import them through `aria_nbv.vin.types` or this leaf module, not through
`aria_nbv.vin.experimental`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from .backbone import EvlBackboneOutput

Tensor = torch.Tensor


@dataclass(slots=True)
class VinForwardDiagnostics:
    """Intermediate tensors produced during a VIN forward pass."""

    backbone_out: EvlBackboneOutput
    """EVL backbone outputs used to build the scene field."""

    candidate_center_rig_m: Tensor
    """``Tensor["B N_q 3", float32]`` candidate centers in reference-rig metres."""

    candidate_radius_m: Tensor
    """``Tensor["B N_q 1", float32]`` candidate radii in reference-rig metres."""

    candidate_center_dir_rig: Tensor
    """``Tensor["B N_q 3", float32]`` unit center directions in the reference rig frame."""

    candidate_forward_dir_rig: Tensor
    """``Tensor["B N_q 3", float32]`` unit forward directions in the reference rig frame."""

    view_alignment: Tensor
    """``Tensor["B N_q 1", float32]`` forward-to-inward alignment in ``[-1, 1]``."""

    pose_enc: Tensor
    """``Tensor["B N_q E_pose", float32]`` pose encoder output."""

    pose_vec: Tensor | None
    """``Tensor["B N_q D_pose", float32]`` pose vector fed into LFF, if present."""

    voxel_center_rig_m: Tensor | None
    """``Tensor["B 3", float32]`` Voxel-grid origin in the reference rig frame (or None)."""

    voxel_radius_m: Tensor | None
    """``Tensor["B 1", float32]`` Radius of the voxel-grid origin in the reference rig frame (or None)."""

    voxel_center_dir_rig: Tensor | None
    """``Tensor["B 3", float32]`` Unit direction to voxel origin in the reference rig frame (or None)."""

    voxel_forward_dir_rig: Tensor | None
    """``Tensor["B 3", float32]`` Voxel frame +Z axis in the reference rig frame (or None)."""

    voxel_view_alignment: Tensor | None
    """``Tensor["B 1", float32]`` Dot product of voxel forward and -center directions (or None)."""

    voxel_pose_enc: Tensor | None
    """``Tensor["B E_pose", float32]`` LFF-encoded voxel pose in the reference rig frame (or None)."""

    voxel_pose_vec: Tensor | None
    """``Tensor["B D_pose", float32]`` Voxel pose vector fed into LFF (or None)."""

    field_in: Tensor
    """``Tensor["B C_in D H W", float32]`` Raw scene field before projection."""

    field: Tensor
    """``Tensor["B C_out D H W", float32]`` Projected scene field."""

    global_feat: Tensor | None
    """``Tensor["B N_q C_global", float32]`` global candidate features, if present."""

    local_feat: Tensor
    """``Tensor["B N_q C_out", float32]`` pooled frustum features."""

    tokens: Tensor
    """``Tensor["B N_q K C_out", float32]`` sampled frustum tokens."""

    token_valid: Tensor
    """``Tensor["B N_q K", bool]`` token validity mask."""

    candidate_valid: Tensor
    """``Tensor["B N_q", bool]`` candidate validity diagnostic."""

    voxel_valid_frac: Tensor
    """``Tensor["B N_q 1", float32]`` valid voxel/frustum fraction per candidate."""

    feats: Tensor
    """``Tensor["B N_q F", float32]`` concatenated VIN features after masking."""


@dataclass(slots=True)
class VinV3ForwardDiagnostics:
    """Candidate-aligned intermediate tensors from VIN-Core forward passes."""

    backbone_out: EvlBackboneOutput
    """EVL backbone outputs used to build the scene field."""

    candidate_center_rig_m: Tensor
    """``Tensor["B N_q 3", float32]`` candidate centers in reference-rig metres."""

    pose_enc: Tensor
    """``Tensor["B N_q E_pose", float32]`` pose encoder output."""

    pose_vec: Tensor
    """``Tensor["B N_q D_pose", float32]`` pose vector fed into the encoder."""

    field_in: Tensor
    """``Tensor["B C_in D H W", float32]`` Raw scene field before projection."""

    field: Tensor
    """``Tensor["B C_out D H W", float32]`` Projected scene field."""

    global_feat: Tensor
    """``Tensor["B N_q C_global", float32]`` pose-conditioned global features."""

    candidate_valid: Tensor
    """``Tensor["B N_q", bool]`` diagnostic candidate-valid mask."""

    feats: Tensor
    """``Tensor["B N_q F", float32]`` concatenated VIN candidate features."""

    voxel_valid_frac: Tensor | None = None
    """``Tensor["B N_q", float32]`` candidate voxel-coverage proxy, if computed."""

    semidense_candidate_vis_frac: Tensor | None = None
    """``Tensor["B N_q", float32]`` candidate semidense visibility, if computed."""

    @property
    def semidense_valid_frac(self) -> Tensor | None:
        """Read-only compatibility alias for ``semidense_candidate_vis_frac``."""

        return self.semidense_candidate_vis_frac

    pos_grid: Tensor | None = None
    """``Tensor["B 3 D H W", float32]`` Normalized voxel position grid (if computed)."""

    semidense_proj: Tensor | None = None
    """``Tensor["B N_q C_proj", float32]`` semidense projection features."""

    semidense_grid_feat: Tensor | None = None
    """``Tensor["B N_q C_cnn", float32]`` CNN projection-grid features."""

    voxel_proj: Tensor | None = None
    """``Tensor["B N_q C_proj", float32]`` voxel-projection features."""

    traj_feat: Tensor | None = None
    """``Tensor["B F_traj", float32]`` Pooled trajectory embedding (if enabled)."""

    traj_ctx: Tensor | None = None
    """``Tensor["B N_q F_pose", float32]`` trajectory context per candidate query."""

    traj_pose_vec: Tensor | None = None
    """``Tensor["B T D_v", float32]`` Per-frame trajectory pose vectors."""

    traj_pose_enc: Tensor | None = None
    """``Tensor["B T F_traj", float32]`` Per-frame trajectory pose encodings."""


__all__ = [
    "VinForwardDiagnostics",
    "VinV3ForwardDiagnostics",
]
