# ruff: noqa: N999

"""VIN (View Introspection Network) head on top of a frozen EVL backbone.

This module implements the *learned* component of NBV scoring that sits on top of
EVL's frozen voxel-lifting features. The goal is to predict the **Relative
Reconstruction Improvement (RRI)** for each candidate view, which the oracle
defines (conceptually) as:

    RRI = (d_before - d_after) / d_before,

where ``d_before`` and ``d_after`` are point-to-mesh distances (e.g., Chamfer-like
metrics) before and after adding a candidate view. In training, we discretize
RRI into ordinal bins and optimize the CORAL ordinal loss; at inference we use
the expected ordinal value as a normalized score.

Coordinate frames and transforms follow the EFM3D/ATEK conventions:

- ``T_A_B`` is a transform mapping points from frame **B** to frame **A**.
- ``PoseTW`` stores SE(3) as ``(R, t)`` in world units.
- ``world`` is the global frame; ``rig`` is the device frame; ``cam`` is a
  specific camera frame; ``voxel`` is EVL's voxel grid frame.

Key ingredients implemented here:

1. **Shell pose encoding** (candidate pose in reference frame)

   Given the relative pose:

       T_rig_ref_cam = T_world_rig_ref^{-1} * T_world_cam,

   we define:

       t = translation(T_rig_ref_cam)        (candidate center in rig-ref),
       r = ||t||                               (radius),
       u = t / (r + eps)                       (center direction),
       f = R_rig_ref_cam * z_cam               (camera forward direction),
       s = <f, -u>                             (view alignment scalar).

   These are encoded by ``ShellShPoseEncoder`` using real spherical harmonics for
   ``u`` and ``f`` plus Fourier features for ``r`` and an MLP for ``s``.

2. **Scene field construction**

   EVL provides voxel-aligned evidence volumes. We build a compact field
   ``F(v) in R^{C_in}`` with channels such as:

       occ_pr          = P(occupied | EVL), in [0,1]
       occ_input       = voxelized occupancy evidence from input points
       counts_norm     = log1p(counts) / log1p(max_counts)
       observed        = 1[counts > 0]
       unknown         = 1 - observed
       new_surface_prior = unknown * occ_pr
       free_input      = EVL free-space evidence (or proxy)

   The field is projected with ``1x1x1 Conv3d + GroupNorm + GELU`` to a learned
   feature dimension.

3. **Candidate-conditioned voxel query (frustum sampling)**

   For each candidate camera we sample a small grid of rays on the image plane
   and a set of metric depths ``{d_i}``. The resulting points are unprojected
   into world coordinates using PyTorch3D and then mapped into the voxel frame:

       p_voxel = T_voxel_world * p_world,
       i_x = (x - x_min) / dx,  dx = (x_max - x_min) / W,
       i_y = (y - y_min) / dy,  dy = (y_max - y_min) / H,
       i_z = (z - z_min) / dz,  dz = (z_max - z_min) / D.

   We then sample ``F`` with trilinear interpolation (``grid_sample``), yielding
   per-ray tokens and a validity mask.

4. **Global tokens + CORAL head**

   The per-candidate features are:

       [pose_enc, global_field_mean?, voxel_pose_enc?, local_frustum_feat].

   The head outputs CORAL logits ``l_k`` for thresholds ``k=0..K-2``:

       P(y > k) = sigmoid(l_k),
       E[y] = sum_k P(y > k),
       E_norm = E[y] / (K-1).

These steps provide an interpretable mapping from candidate pose + EVL scene
context to an ordinal NBV score that correlates with oracle RRI.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]
from torch import Tensor, nn

from ...rri_metrics.coral import coral_expected_from_logits, coral_logits_to_prob
from ...utils import TargetConfig
from .._model_mixins import FrustumSamplingMixin
from ..backbones import EvlBackboneConfig
from ..encoders import ShellShPoseEncoderConfig
from ..geometry import (
    build_scene_field as _build_scene_field,
)
from ..geometry import (
    candidate_valid_from_token as _candidate_valid_from_token,
)
from ..geometry import (
    sample_voxel_field as _sample_voxel_field,
)
from ..modules import VinScorerHeadConfig
from ..vin_utils import (
    largest_divisor_leq as _largest_divisor_leq,
)
from .types import EvlBackboneOutput, VinForwardDiagnostics, VinPrediction


class VinModelConfig(TargetConfig["VinModel"]):
    """Configuration for `VinModel`.

    This config collects all architectural choices that determine how VIN
    represents scene context and candidate poses. Conceptually, the VIN score is
    a function:

        score = f( pose_enc(u,f,r,s),
                   voxel_pose_enc?,
                   global_field_mean?,
                   local_frustum_feat ),

    where ``pose_enc`` and ``voxel_pose_enc`` are SH-based shell encodings,
    ``global_field_mean`` summarizes the voxel field, and ``local_frustum_feat``
    samples the voxel field along a candidate frustum.
    """

    @property
    def target_type(self) -> type["VinModel"]:
        """Factory target for `BaseConfig.setup_target`."""
        return VinModel

    backbone: EvlBackboneConfig = Field(default_factory=EvlBackboneConfig)
    """Frozen EVL backbone configuration."""

    pose_encoder_sh: ShellShPoseEncoderConfig = Field(default_factory=ShellShPoseEncoderConfig)
    """Spherical harmonics pose encoding configuration (shell descriptor)."""

    head: VinScorerHeadConfig = Field(default_factory=VinScorerHeadConfig)
    """Scoring head configuration."""

    scene_field_channels: Literal[
        "occ_pr", "occ_input", "counts_norm", "observed", "unknown", "new_surface_prior", "free_input"
    ] = Field(
        default_factory=lambda: ["occ_pr", "occ_input", "counts_norm"],
        min_length=1,
    )
    """Ordered channels used to build the low-dimensional scene field."""

    occ_input_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    """Threshold used when deriving fallback free-space evidence from `occ_input`."""

    counts_norm_mode: Literal["log1p", "linear"] = "log1p"
    """How to normalize voxel `counts` into [0, 1]."""

    occ_pr_is_logits: bool = False
    """Whether `occ_pr` is logits (apply sigmoid) rather than a probability volume."""

    field_dim: int = Field(default=16, gt=0)
    """Channel dimension d0 of the compressed scene field."""

    field_gn_groups: int = Field(default=4, gt=0)
    """Requested GroupNorm groups for the field projection (clamped to a divisor of `field_dim`)."""

    frustum_grid_size: int = Field(default=4, gt=0)
    """Grid size on the image plane for candidate frustum sampling (grid_size² directions)."""

    frustum_depths_m: list[Annotated[float, Field(gt=0.0, allow_inf_nan=False)]] = Field(
        default_factory=lambda: [0.5, 1.0, 2.0, 3.0],
        min_length=1,
    )
    """Depth values (metres) along each frustum direction."""

    use_global_pool: bool = True
    """Whether to concatenate the global mean-pooled embedding to per-candidate features."""

    use_voxel_pose_encoding: bool = True
    """Whether to append a SH-encoded voxel-grid pose (voxel/T_world_voxel) in the reference frame."""

    candidate_min_valid_frac: float = Field(default=0.2, ge=0.0, le=1.0)
    """Minimum fraction of valid frustum samples required to keep a candidate."""

    @field_validator("scene_field_channels")
    @classmethod
    def _validate_scene_field_channels(cls, value: list[str]) -> list[str]:
        """Validate requested scene-field channels.

        We only allow channels that can be constructed from EVL head outputs in
        this module, ensuring the scene field definition remains explicit and
        interpretable (e.g., ``new_surface_prior = unknown * occ_pr``).
        """
        allowed = {
            "occ_pr",
            "occ_input",
            "counts_norm",
            "observed",
            "unknown",
            "new_surface_prior",
            "free_input",
        }
        unknown = [name for name in value if name not in allowed]
        if unknown:
            raise ValueError(f"Unknown/unsupported scene_field_channels: {unknown}")
        if len(set(value)) != len(value):
            raise ValueError("scene_field_channels must not contain duplicates.")
        return value


class VinModel(FrustumSamplingMixin, nn.Module):
    """View Introspection Network (VIN) predicting RRI from EVL voxel features + pose.

    VIN is a light-weight head that queries frozen EVL voxel features to score
    candidate camera poses. The architecture is deliberately simple:

    - **Pose encoding** via real spherical harmonics (direction) and Fourier
      features (radius) to represent candidate shells.
    - **Scene field** built from EVL evidence volumes and projected with a
      1x1x1 Conv3d to a small feature dimension.
    - **Local query**: sample the scene field at frustum points and pool.
    - **Global tokens**: optional mean-pooled field + optional voxel-pose token.
    - **CORAL head** to produce ordinal scores.

    The overall score is computed as:

        z = concat(pose_enc, global_field_mean?, voxel_pose_enc?, local_feat)
        logits = CORAL(MLP(z))
        score = E[y]/(K-1) = (1/(K-1)) * sum_k sigmoid(logit_k)
    """

    def __init__(self, config: VinModelConfig) -> None:
        super().__init__()
        self.config = config

        self.backbone = self.config.backbone.setup_target()
        self.pose_encoder_sh = self.config.pose_encoder_sh.setup_target()

        field_dim = self.config.field_dim
        gn_groups = _largest_divisor_leq(field_dim, self.config.field_gn_groups)

        field_in_dim = len(self.config.scene_field_channels)
        self.field_proj = nn.Sequential(
            nn.Conv3d(field_in_dim, field_dim, kernel_size=1, bias=False),
            nn.GroupNorm(num_groups=gn_groups, num_channels=field_dim),
            nn.GELU(),
        )

        self.use_global_pool = self.config.use_global_pool
        self.use_voxel_pose_encoding = self.config.use_voxel_pose_encoding

        # Head input dim is data-dependent (feature channel count depends on EVL cfg).
        pose_dim = int(self.pose_encoder_sh.out_dim)
        head_in_dim = pose_dim + field_dim
        if self.use_global_pool:
            head_in_dim += field_dim
        if self.use_voxel_pose_encoding:
            head_in_dim += pose_dim
        self.head = self.config.head.setup_target(in_dim=head_in_dim)
        self.to(self.backbone.device)

    def _pool_global(self, field: Tensor) -> Tensor:
        """Mean-pool global context from a voxel field.

        This produces a scene-level token:

            global_feat = mean_{x,y,z} F(x,y,z).

        The global token provides coarse context such as overall occupancy
        density and semantic bias across the snippet.
        """

        return field.mean(dim=(-3, -2, -1))

    def _pool_candidates(self, *, tokens: Tensor, valid: Tensor) -> Tensor:
        """Mean-pool candidate-local frustum samples.

        For each candidate, we compute a masked mean over K frustum samples:

            local_feat = sum_k (valid_k * token_k) / (sum_k valid_k + eps).

        This aggregates the local voxel evidence along the candidate frustum
        while ignoring samples that fall outside the voxel grid.
        """

        if tokens.ndim != 4:
            raise ValueError(f"Expected tokens shape (B,N,K,C), got {tuple(tokens.shape)}.")
        if valid.shape != tokens.shape[:3]:
            raise ValueError(f"Expected valid shape {tuple(tokens.shape[:3])}, got {tuple(valid.shape)}.")

        mask = valid.to(dtype=tokens.dtype).unsqueeze(-1)
        denom = mask.sum(dim=-2).clamp_min(1.0)
        pooled = (tokens * mask).sum(dim=-2) / denom
        return pooled

    def _forward_impl(
        self,
        efm: dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        return_debug: bool,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> tuple[VinPrediction, VinForwardDiagnostics | None]:
        """Run the full VIN forward pass (optionally returning diagnostics).

        Conceptual steps:

        1) **EVL backbone**
           If ``backbone_out`` is not provided, we run EVL once to obtain the
           voxel grid pose ``T_world_voxel`` and evidence volumes (occupancy,
           counts, etc.).

        2) **Candidate pose in reference frame**
           Convert each candidate pose into the reference rig frame:

               T_rig_ref_cam = T_world_rig_ref^{-1} * T_world_cam.

           The candidate center and directions are then:

               t = translation(T_rig_ref_cam)
               r = ||t||
               u = t / (r + eps)
               f = R_rig_ref_cam * z_cam
               s = <f, -u>.

        3) **Pose encoding**
           The tuple (u, f, r, s) is encoded with ``ShellShPoseEncoder`` into a
           fixed-size embedding ``pose_enc``.

        4) **Voxel pose encoding (optional)**
           The EVL voxel grid pose is also expressed in the reference rig frame:

               T_rig_ref_voxel = T_world_rig_ref^{-1} * T_world_voxel,

           and encoded with the same shell encoder. This provides a global token
           indicating how the voxel grid is positioned/oriented relative to the
           reference rig.

        5) **Scene field + global token**
           Build the compact voxel field ``F`` from EVL head outputs and project
           it to ``field_dim``. Optionally compute the global mean token:

               global_feat = mean_{x,y,z} F(x,y,z).

        6) **Frustum query (local token)**
           For each candidate camera, build ``K`` frustum points (grid_size^2 *
           len(depths_m)) in world coordinates, map to voxel coordinates, and
           sample ``F`` to obtain ``tokens``. Pool them with a validity mask:

               local_feat = sum_k (valid_k * token_k) / (sum_k valid_k + eps).

        7) **Candidate validity**
           A candidate is kept if a sufficient fraction of its frustum samples
           lie inside the voxel grid:

               valid_frac = mean_k 1[valid_k],  keep if valid_frac >= min_valid_frac.

        8) **Scoring with CORAL**
           Concatenate all tokens and score with the CORAL head. The expected
           ordinal score is:

               E[y] = sum_{k=0}^{K-2} sigmoid(logit_k),
               E_norm = E[y] / (K-1).

        Args:
            efm: Raw EFM snippet dict (unbatched or batched).
            candidate_poses_world_cam: Candidate camera poses as world<-camera.
            reference_pose_world_rig: Reference rig pose (world<-rig) for the snippet.
            p3d_cameras: PyTorch3D cameras aligned with candidates.
            return_debug: Whether to return intermediate tensors for diagnostics.
            backbone_out: Optional precomputed EVL backbone output.

        Returns:
            Tuple of ``(VinPrediction, VinForwardDiagnostics | None)``.
        """
        if backbone_out is None:
            backbone_out = self.backbone.forward(efm)
        device = backbone_out.voxel_extent.device

        pose_world_cam = self._ensure_candidate_batch(candidate_poses_world_cam).to(device=device)  # type: ignore[arg-type]
        batch_size, num_candidates = int(pose_world_cam.shape[0]), int(pose_world_cam.shape[1])

        pose_world_rig_ref = reference_pose_world_rig.to(device=device)  # type: ignore[arg-type]
        if pose_world_rig_ref.ndim == 1:
            pose_world_rig_ref = PoseTW(pose_world_rig_ref._data.unsqueeze(0))
        elif pose_world_rig_ref.ndim != 2:
            raise ValueError(f"reference_pose_world_rig must have shape (12,) or (B,12), got {pose_world_rig_ref.ndim}")

        if pose_world_rig_ref.shape[0] == 1 and batch_size > 1:
            pose_world_rig_ref = PoseTW(pose_world_rig_ref._data.expand(batch_size, 12))
        elif pose_world_rig_ref.shape[0] != batch_size:
            raise ValueError("reference_pose_world_rig must have batch size 1 or match candidate batch size.")

        # ------------------------------------------------------------------ relative pose (candidate in reference rig frame)
        pose_rig_cam = pose_world_rig_ref.inverse()[:, None] @ pose_world_cam  # rig_ref <- cam

        # ------------------------------------------------------------------ pose encoding (shell descriptor)
        candidate_center_rig_m = pose_rig_cam.t.to(dtype=torch.float32)  # B N 3
        candidate_radius_m = torch.linalg.vector_norm(candidate_center_rig_m, dim=-1, keepdim=True)  # B N 1
        candidate_center_dir_rig = candidate_center_rig_m / (candidate_radius_m + 1e-8)

        cam_forward_axis_cam = torch.tensor([0.0, 0.0, 1.0], device=device, dtype=torch.float32)
        candidate_forward_dir_rig = torch.einsum(
            "...ij,j->...i", pose_rig_cam.R.to(dtype=torch.float32), cam_forward_axis_cam
        )
        candidate_forward_dir_rig = candidate_forward_dir_rig / (
            torch.linalg.vector_norm(candidate_forward_dir_rig, dim=-1, keepdim=True) + 1e-8
        )

        view_alignment = (candidate_forward_dir_rig * (-candidate_center_dir_rig)).sum(dim=-1, keepdim=True)

        pose_enc = self.pose_encoder_sh(
            candidate_center_dir_rig,
            candidate_forward_dir_rig,
            r=candidate_radius_m,
            scalars=view_alignment,
        )

        # ------------------------------------------------------------------ voxel pose encoding (reference rig frame)
        voxel_pose_enc: Tensor | None = None
        voxel_center_rig_m: Tensor | None = None
        voxel_radius_m: Tensor | None = None
        voxel_center_dir_rig: Tensor | None = None
        voxel_forward_dir_rig: Tensor | None = None
        voxel_view_alignment: Tensor | None = None

        t_world_voxel = backbone_out.t_world_voxel
        if t_world_voxel.ndim == 1:
            t_world_voxel = PoseTW(t_world_voxel._data.unsqueeze(0))
        if t_world_voxel.shape[0] == 1 and batch_size > 1:
            t_world_voxel = PoseTW(t_world_voxel._data.expand(batch_size, 12))
        elif t_world_voxel.shape[0] != batch_size:
            raise ValueError("voxel/T_world_voxel must have batch size 1 or match candidate batch size.")

        pose_rig_voxel = pose_world_rig_ref.inverse() @ t_world_voxel  # rig_ref <- voxel
        voxel_center_rig_m = pose_rig_voxel.t.to(dtype=torch.float32)  # B 3
        voxel_radius_m = torch.linalg.vector_norm(voxel_center_rig_m, dim=-1, keepdim=True)  # B 1
        voxel_center_dir_rig = voxel_center_rig_m / (voxel_radius_m + 1e-8)
        voxel_forward_dir_rig = torch.einsum(
            "bij,j->bi", pose_rig_voxel.R.to(dtype=torch.float32), cam_forward_axis_cam
        )
        voxel_forward_dir_rig = voxel_forward_dir_rig / (
            torch.linalg.vector_norm(voxel_forward_dir_rig, dim=-1, keepdim=True) + 1e-8
        )
        voxel_view_alignment = (voxel_forward_dir_rig * (-voxel_center_dir_rig)).sum(dim=-1, keepdim=True)
        voxel_pose_enc = self.pose_encoder_sh.forward(
            voxel_center_dir_rig,
            voxel_forward_dir_rig,
            r=voxel_radius_m,
            scalars=voxel_view_alignment,
        )

        # ------------------------------------------------------------------ build voxel-aligned scene field
        field_in = _build_scene_field(
            backbone_out,
            use_channels=self.config.scene_field_channels,
            occ_input_threshold=self.config.occ_input_threshold,
            counts_norm_mode=self.config.counts_norm_mode,
            occ_pr_is_logits=self.config.occ_pr_is_logits,
        ).to(device=device)
        field = self.field_proj(field_in)

        # ------------------------------------------------------------------ global pooling (coarse tokens)
        parts: list[Tensor] = [pose_enc.to(device=device, dtype=field.dtype)]
        global_feat: Tensor | None = None
        if self.use_global_pool:
            global_feat = self._pool_global(field).unsqueeze(1).expand(batch_size, num_candidates, -1)
            parts.append(global_feat)
        if self.use_voxel_pose_encoding and voxel_pose_enc is not None:
            voxel_feat = voxel_pose_enc.to(device=device, dtype=field.dtype).unsqueeze(1)
            parts.append(voxel_feat.expand(batch_size, num_candidates, -1))

        # ------------------------------------------------------------------ candidate-conditioned frustum query
        points_world = self._frustum_points_world(
            pose_world_cam,
            p3d_cameras=p3d_cameras,
        )
        tokens, token_valid = _sample_voxel_field(
            field,
            points_world=points_world,
            t_world_voxel=backbone_out.t_world_voxel,
            voxel_extent=backbone_out.voxel_extent,
        )
        local_feat = self._pool_candidates(tokens=tokens, valid=token_valid)
        parts.append(local_feat.to(dtype=field.dtype))

        # NOTE: Candidate validity is based on the fraction of frustum samples that fall inside the EVL voxel grid
        # (after mapping WORLD→VOXEL using `voxel/T_world_voxel`). This avoids admitting candidates with only a
        # handful of in-bounds samples.
        candidate_valid = _candidate_valid_from_token(
            token_valid,
            min_valid_frac=self.config.candidate_min_valid_frac,
        )
        voxel_valid_frac = token_valid.float().mean(dim=-1, keepdim=True)

        feats = torch.cat(parts, dim=-1)
        feats = feats * candidate_valid.to(dtype=feats.dtype).unsqueeze(-1)
        logits = self.head(feats.reshape(batch_size * num_candidates, -1)).reshape(batch_size, num_candidates, -1)

        prob = coral_logits_to_prob(logits)
        expected, expected_norm = coral_expected_from_logits(logits)

        pred = VinPrediction(
            logits=logits,
            prob=prob,
            expected=expected,
            expected_normalized=expected_norm,
            candidate_valid=candidate_valid,
            voxel_valid_frac=voxel_valid_frac.squeeze(-1),
            semidense_valid_frac=None,
        )

        if not return_debug:
            return pred, None

        debug = VinForwardDiagnostics(
            backbone_out=backbone_out,
            candidate_center_rig_m=candidate_center_rig_m,
            candidate_radius_m=candidate_radius_m,
            candidate_center_dir_rig=candidate_center_dir_rig,
            candidate_forward_dir_rig=candidate_forward_dir_rig,
            view_alignment=view_alignment,
            pose_enc=pose_enc,
            voxel_center_rig_m=voxel_center_rig_m,
            voxel_radius_m=voxel_radius_m,
            voxel_center_dir_rig=voxel_center_dir_rig,
            voxel_forward_dir_rig=voxel_forward_dir_rig,
            voxel_view_alignment=voxel_view_alignment,
            voxel_pose_enc=voxel_pose_enc,
            field_in=field_in,
            field=field,
            global_feat=global_feat,
            local_feat=local_feat,
            tokens=tokens,
            token_valid=token_valid,
            candidate_valid=candidate_valid,
            voxel_valid_frac=voxel_valid_frac,
            feats=feats,
        )
        return pred, debug

    def forward(
        self,
        efm: dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> VinPrediction:
        """Score candidate poses for one snippet (no diagnostics).

        This is the inference-friendly wrapper around ``_forward_impl``. It
        computes CORAL logits and converts them to:

            prob: class probabilities
            expected: sum_k sigmoid(logit_k)
            expected_normalized: expected / (K-1)

        The output score is *ordinal* rather than metric RRI, but it preserves
        the ordering implied by the learned thresholds.

        Args:
            efm: Raw EFM snippet dict.
            candidate_poses_world_cam: Candidate camera poses as world<-camera.
                Shape can be ``(N,12)`` or ``(B,N,12)``.
            reference_pose_world_rig: Reference rig pose (world<-rig) for the snippet.
            p3d_cameras: PyTorch3D cameras for each candidate (same ordering as candidates).

        Returns:
            `VinPrediction` with CORAL logits, probabilities, and expected scores.
        """

        pred, _ = self._forward_impl(
            efm,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            p3d_cameras=p3d_cameras,
            return_debug=False,
            backbone_out=backbone_out,
        )
        return pred

    def forward_with_debug(
        self,
        efm: dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> tuple[VinPrediction, VinForwardDiagnostics]:
        """Run VIN forward pass and return intermediate tensors.

        This method is intended for debugging and visualization. It exposes the
        *entire* computation graph at key points (pose encoding, scene field
        construction, frustum sampling, masking), enabling detailed sanity
        checks of coordinate transforms and feature magnitudes.

        Args:
            efm: Raw EFM snippet dict.
            candidate_poses_world_cam: Candidate camera poses as world<-camera.
                Shape can be ``(N,12)`` or ``(B,N,12)``.
            reference_pose_world_rig: Reference rig pose (world<-rig) for the snippet.
            p3d_cameras: PyTorch3D cameras for each candidate (same ordering as candidates).

        Returns:
            Tuple of (`VinPrediction`, `VinForwardDiagnostics`).
        """

        pred, debug = self._forward_impl(
            efm,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            p3d_cameras=p3d_cameras,
            return_debug=True,
            backbone_out=backbone_out,
        )
        if debug is None:
            raise RuntimeError("Expected VinForwardDiagnostics when return_debug=True.")
        return pred, debug
