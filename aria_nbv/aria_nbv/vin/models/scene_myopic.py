"""VIN v3 one-step RRI scorer with evidence-backed components.

This module owns the active VIN one-step baseline. It predicts per-row
RRI scores for a finite candidate set and is used as a myopic scorer/control,
not as the thesis finite-horizon value model. The most reliable signal in the
current implementation comes from pose encoding, EVL voxel evidence, and
semidense projection coverage, so v3 keeps a compact deterministic path with
optional trajectory context behind a config flag:

1) Pose encoding (R6D + LFF):
   Candidate poses are expressed in the reference rig frame
   T_rig_ref_cam = T_world_rig_ref^{-1} * T_world_cam and encoded as translation
   plus rotation-6D with Learnable Fourier Features.

2) Scene field (fixed channels):
   The voxel field concatenates occ_pr, cent_pr, counts_norm, occ_input,
   free_input, and new_surface_prior. We normalize counts as
   counts_norm = log1p(n) / log1p(max(n)) and define unknown = 1 - counts_norm,
   new_surface_prior = unknown * occ_pr. This compact field was stable in sweep
   diagnostics and supports voxel-validity gating.

3) Global context (pose-conditioned attention):
   A pooled voxel grid is attended by pose embeddings, with LFF positional keys
   in the reference rig frame.

4) Semidense projection stats (VIN-NBV proxy):
   We project semidense points into each candidate view to compute coverage,
   empty fraction, visibility fraction, and depth moments. These features act as
   a lightweight proxy for frustum attention, are concatenated into the scorer
   input, and drive a tiny CNN over the projection grid for richer cues.

5) Voxel projection FiLM:
   Pooled voxel centers are projected into candidate views and summarized; this
   drives a light FiLM modulation of the global feature (kept as the only
   view-conditioned modulation).

6) Optional trajectory context (disabled by default):
   Snippet rig poses can be encoded and attended by candidate embeddings to
   provide motion context, mirroring the v2 path without forcing it on the
   baseline.

7) CORAL head:
   A shallow MLP plus CORAL ordinal head produces per-candidate RRI scores.

The forward contract is actor-visible: candidate poses, EVL features, and
semidense observations are inputs; oracle RRI labels are training/evaluation
targets. Target-conditioned rollout data may reuse the same architecture family,
but matched GT targets and target crops must remain outside actor inputs.

Frame-consistency:
Candidate generation applies rotate_yaw_cw90 (a local +Z roll) to poses for UI
alignment. EVL backbone outputs do not use this convention. VinModelV3 therefore
undoes this rotation before computing pose features. If apply_cw90_correction is
enabled, callers must pre-correct p3d_cameras and set cw90_corrected=True.

NOTE: vin inputs are typically VinSnippetView with points_world shaped (N,4)
or (N,5) containing (x, y, z, 1/sigma_d) with optional n_obs. This file
enforces the required XYZ + reliability channel contract to avoid silent
failure modes.

Candidate orientation uses R6D pose features. Accumulated target visibility, if
added for target-conditioned value learning, should be represented as a separate
directional memory over view directions, not folded into the pose encoding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from pytorch3d.renderer.cameras import (  # type: ignore[import-untyped]
    PerspectiveCameras,
)
from torch import Tensor, nn

from aria_nbv.utils.frames import rotate_yaw_cw90

from ...data_handling.offline.adapter import build_vin_snippet_view
from ...data_handling.raw.views import (
    EfmSnippetView,
    VinSnippetView,
    is_efm_snippet_view_instance,
    is_vin_snippet_view_instance,
)
from ...utils import TargetConfig
from ..backbones import EvlBackboneConfig
from ..diagnostics import summarize_vin_v3
from ..encoders import (
    LearnableFourierFeaturesConfig,
    PoseEncoder,
    R6dLffPoseEncoderConfig,
    TrajectoryEncoder,
    TrajectoryEncoderConfig,
    validate_pos_grid_xyz_encoder,
)
from ..geometry import (
    ensure_candidate_batch,
    ensure_pose_batch,
    pool_voxel_points,
    sample_candidate_voxel_coverage,
)
from ..geometry.semidense_projection import (
    encode_projection_summary,
    project_points_to_candidate_cameras,
    sample_semidense_points,
)
from ..geometry.semidense_schema import SEMIDENSE_PROJ_DIM, semidense_proj_feature_index
from ..modules import (
    PoseConditionedGlobalPool,
    SceneFieldProjectionConfig,
    SemidenseGridEncoder,
    SemidenseGridEncoderConfig,
    VinScorerHeadConfig,
    largest_divisor_leq,
)
from ..ordinal import coral_expected_from_logits, coral_logits_to_prob
from ..scorer_context import (
    apply_vin_scorer_film,
    build_vin_scorer_scene_field,
    compute_global_context,
    encode_pose_features,
    encode_trajectory_context,
)
from ..types import (
    EvlBackboneOutput,
    FieldBundle,
    GlobalContext,
    PreparedInputs,
    VinPrediction,
    VinV3ForwardDiagnostics,
)

if TYPE_CHECKING:
    from aria_nbv.data_handling import VinOracleBatch

    from ..encoders import LearnableFourierFeatures


FIELD_CHANNELS_V3: tuple[str, ...] = (
    "occ_pr",
    "occ_input",
    "counts_norm",
    "cent_pr",
    "free_input",
    "unknown",
    "new_surface_prior",
)


class VinModelV3Config(TargetConfig["VinModelV3"]):
    """Configuration for `VinModelV3` (streamlined one-step VIN baseline)."""

    @property
    def target_type(self) -> type["VinModelV3"]:
        """Factory target for `BaseConfig.setup_target` (config-as-factory)."""
        return VinModelV3

    backbone: EvlBackboneConfig | None = Field(default_factory=EvlBackboneConfig)
    """Optional EVL config kept for caller-side materialization of voxel features."""

    pose_encoder: R6dLffPoseEncoderConfig = Field(default_factory=R6dLffPoseEncoderConfig)
    """Pose encoder configuration (R6D + LFF; stable relative pose encoding)."""

    pos_grid_encoder_lff: LearnableFourierFeaturesConfig = Field(
        default_factory=lambda: LearnableFourierFeaturesConfig(
            input_dim=3,
            fourier_dim=32,
            hidden_dim=32,
            output_dim=16,
        ),
    )
    """LFF encoder for XYZ voxel position keys used by global pooling."""

    head_hidden_dim: int = Field(default=192, gt=0)
    """Hidden dimension for the scorer MLP (optuna favored compact heads)."""

    head_num_layers: int = Field(default=1, ge=1)
    """Number of MLP layers before the CORAL layer (best trials used 1)."""

    head_dropout: float = Field(default=0.05, ge=0.0, lt=1.0)
    """Dropout probability in the MLP (sweep best used near-zero dropout)."""

    num_classes: int = Field(default=15, ge=2)
    """Number of ordinal bins (VIN-NBV uses 15 for sweep comparability)."""

    coral_preinit_bias: bool = True
    """Pre-initialize CORAL biases for faster, more stable ordinal learning."""

    field_dim: int = Field(default=16, gt=0)
    """Channel dimension of the projected voxel field (compact by design)."""

    field_gn_groups: int = Field(default=4, gt=0)
    """Requested GroupNorm groups (clamped to a divisor of ``field_dim``) for stability."""

    semidense_proj_grid_size: int = Field(default=24, gt=0)
    """Grid size for semidense projection stats (higher for tiny-CNN cues)."""

    semidense_proj_max_points: int = Field(default=4096, gt=0)
    """Maximum semidense points used for projection stats (sweep best used 4096)."""

    semidense_cnn_enabled: bool = True
    """Whether to encode a tiny 2D CNN over the semidense projection grid."""

    semidense_cnn_channels: int = Field(default=8, gt=0)
    """Hidden channel width for the semidense projection CNN."""

    semidense_cnn_out_dim: int = Field(default=16, gt=0)
    """Output feature dimension of the semidense projection CNN."""

    use_traj_encoder: bool = Field(default=False)
    """Whether to encode snippet trajectories and append trajectory context."""

    traj_encoder: TrajectoryEncoderConfig | None = Field(default_factory=TrajectoryEncoderConfig)
    """Optional trajectory encoder for snippet rig poses (R6D + LFF)."""

    use_voxel_valid_frac_gate: bool = False
    """Deprecated: voxel gate removed. Keep ``False`` (use FiLM only)."""

    semidense_obs_count_min: float = 1.0
    """Global minimum of semidense observation count ``n_obs`` (cache summary)."""

    semidense_obs_count_max: float = 40.0
    """Global maximum of semidense observation count ``n_obs`` (cache summary)."""

    semidense_obs_count_p95: float = 11.0
    """Global 95th percentile of semidense observation count ``n_obs`` (cache summary)."""

    semidense_obs_count_mean: float = 4.3714
    """Global mean of semidense observation count ``n_obs`` (cache summary)."""

    semidense_obs_count_std: float = 3.3134
    """Global standard deviation of semidense observation count ``n_obs`` (cache summary)."""

    semidense_inv_dist_std_min: float = 0.0
    """Global minimum of semidense inverse depth std ``1/sigma_d`` (cache summary)."""

    semidense_inv_dist_std_max: float = 0.03
    """Global maximum of semidense inverse depth std ``1/sigma_d`` (cache summary)."""

    semidense_inv_dist_std_p95: float = 0.011
    """Global 95th percentile of semidense inverse depth std ``1/sigma_d`` (cache summary)."""

    semidense_inv_dist_std_mean: float = 0.0032
    """Global mean of semidense inverse depth std ``1/sigma_d`` (cache summary)."""

    semidense_inv_dist_std_std: float = 0.0040
    """Global standard deviation of semidense inverse depth std ``1/sigma_d`` (cache summary)."""

    apply_cw90_correction: bool = False
    """Undo ``rotate_yaw_cw90`` on poses (requires CW90-corrected cameras)."""

    global_pool_grid_size: int = Field(default=6, gt=0)
    """Target grid size for pose-conditioned global pooling (best trials used ~5)."""

    scene_field_channels: list[
        Literal[
            "occ_pr",
            "occ_input",
            "counts_norm",
            "observed",
            "unknown",
            "free_input",
            "cent_pr",
            "new_surface_prior",
        ]
    ] = Field(
        default_factory=lambda: [
            *FIELD_CHANNELS_V3,
        ],
    )

    """Ordered list of scene-field channels to include in the voxel field.

    This keeps the voxel representation compact and aligned with the sweep
    evidence favoring coverage- and prior-aware features.
    """

    _validate_pos_grid_encoder_lff = field_validator("pos_grid_encoder_lff")(validate_pos_grid_xyz_encoder)

    # NOTE: No additional model validators; VIN-Core keeps a fixed surface area.


class VinModelV3(nn.Module):
    """VIN-Core head for one-step RRI prediction.

    VIN v3 focuses on pose encoding, compact voxel evidence, and semidense
    projection stats, while enforcing fail-fast contracts to avoid silent
    collapse. It ranks candidates for immediate RRI; bounded rollout values
    such as $Q_H$ are separate thesis models trained on rollout replay.

    Candidate-set symmetry is structural: learned blocks use row-wise maps,
    candidate queries over shared scene/trajectory tokens, and symmetric
    GroupNorm statistics across rows. There are no candidate-index embeddings
    or order-sensitive candidate operations. In deterministic evaluation,
    jointly permuting candidate poses and aligned camera rows therefore
    permutes every ``N_q`` output the same way; stochastic training dropout
    preserves only distributional equivariance. This is not graph-isomorphism
    invariance because the model constructs no candidate graph. Its
    reference-frame pose and positional encodings are coordinate-conditioned
    inductive biases and do not enforce SE(3) equivariance.
    """

    def __init__(self, config: VinModelV3Config) -> None:
        super().__init__()
        self.config = config

        # Optional modules (may be None)
        self.voxel_proj_film: nn.Module | None = None
        self.voxel_proj_film_norm: nn.GroupNorm | None = None
        self.semidense_cnn: SemidenseGridEncoder | None = None
        self.traj_encoder: TrajectoryEncoder | None = None
        self.traj_attn: nn.MultiheadAttention | None = None
        self.traj_attn_norm: nn.GroupNorm | None = None

        self.pose_encoder: PoseEncoder = self.config.pose_encoder.setup_target()
        traj_encoder_cfg = self.config.traj_encoder if self.config.use_traj_encoder else None
        if self.config.use_traj_encoder and traj_encoder_cfg is None:
            raise ValueError("use_traj_encoder=True requires a traj_encoder configuration.")
        self.traj_encoder = traj_encoder_cfg.setup_target() if traj_encoder_cfg is not None else None

        field_dim = self.config.field_dim
        self.field_proj = SceneFieldProjectionConfig(
            in_channels=len(self.config.scene_field_channels),
            field_dim=field_dim,
            field_gn_groups=int(self.config.field_gn_groups),
        ).setup_target()

        pose_dim = self.pose_encoder.out_dim
        num_heads = largest_divisor_leq(field_dim, 4)
        self.global_pooler = PoseConditionedGlobalPool(
            field_dim=field_dim,
            pose_dim=pose_dim,
            pool_size=self.config.global_pool_grid_size,
            num_heads=num_heads,
            pos_grid_encoder=self.config.pos_grid_encoder_lff,
        )

        self.voxel_proj_film = nn.Linear(SEMIDENSE_PROJ_DIM, 2 * field_dim, bias=True)
        voxel_proj_groups = largest_divisor_leq(field_dim, 4)
        self.voxel_proj_film_norm = nn.GroupNorm(
            num_groups=voxel_proj_groups,
            num_channels=field_dim,
        )

        # Tiny CNN for semidense projection grids (per-candidate cues).
        if self.config.semidense_cnn_enabled:
            self.semidense_cnn = SemidenseGridEncoderConfig(
                grid_size=int(self.config.semidense_proj_grid_size),
                channels=int(self.config.semidense_cnn_channels),
                out_dim=int(self.config.semidense_cnn_out_dim),
            ).setup_target()

        # ---------------------------------------------------------------------------------
        # Scorer head: MLP + CORAL (pose + global voxel + semidense projection stats + CNN)
        head_in_dim = pose_dim + field_dim + SEMIDENSE_PROJ_DIM
        if self.traj_encoder is not None:
            head_in_dim += pose_dim
        if self.semidense_cnn is not None:
            head_in_dim += int(self.config.semidense_cnn_out_dim)
        head = VinScorerHeadConfig(
            hidden_dim=int(self.config.head_hidden_dim),
            num_layers=int(self.config.head_num_layers),
            dropout=float(self.config.head_dropout),
            num_classes=int(self.config.num_classes),
            coral_preinit_bias=bool(self.config.coral_preinit_bias),
            activation="gelu",
        ).setup_target(in_dim=head_in_dim)
        self.head_mlp = head.mlp
        self.head_coral = head.coral

        if self.traj_encoder is not None:
            traj_dim = int(self.traj_encoder.out_dim)
            traj_heads = largest_divisor_leq(pose_dim, 4)
            self.traj_attn = nn.MultiheadAttention(
                embed_dim=pose_dim,
                num_heads=traj_heads,
                kdim=traj_dim,
                vdim=traj_dim,
                batch_first=True,
            )
            traj_norm_groups = largest_divisor_leq(pose_dim, 4)
            self.traj_attn_norm = nn.GroupNorm(
                num_groups=traj_norm_groups,
                num_channels=pose_dim,
            )

    @property
    def pose_encoder_lff(self) -> LearnableFourierFeatures | None:
        """Return the LFF sub-encoder when present (else ``None``).

        Useful for diagnostics and consistency checks when pose encoding is a
        critical signal in the streamlined baseline.
        """
        return getattr(self.pose_encoder, "pose_encoder_lff", None)

    def _ensure_vin_snippet(
        self,
        efm: EfmSnippetView | VinSnippetView,
        *,
        device: torch.device,
    ) -> VinSnippetView:
        """Ensure a VinSnippetView is available for semidense projection stats.

        VIN v3 consumes padded semidense points, so we always operate on
        `VinSnippetView`. Full EFM snippets are converted on demand.

        Args:
            efm (EfmSnippetView | VinSnippetView): EFM/VIN snippet.
            device (torch.device): Target device.

        Returns:
            Padded `VinSnippetView` with
            ``Tensor["B P C_sem", float32]`` world-point rows.
        """
        if is_vin_snippet_view_instance(efm):
            return efm.to(device=device)
        if is_efm_snippet_view_instance(efm):
            return build_vin_snippet_view(
                efm,
                device=device,
                max_points=self.config.semidense_proj_max_points,
                include_inv_dist_std=True,
                include_obs_count=True,
                pad_points=self.config.semidense_proj_max_points,
            )
        raise TypeError(
            "VinModelV3 expects a VinSnippetView or EfmSnippetView for `efm`.",
        )

    def _prepare_inputs(
        self,
        snippet: VinSnippetView,
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        backbone_out: EvlBackboneOutput,
    ) -> PreparedInputs:
        """Prepare batched inputs, align frames, and enforce required inputs.

        This normalizes candidate/reference pose shapes, applies CW90 undo when
        requested, and verifies that semidense snippet data is present to avoid
        the silent mode-collapse observed when projection stats are missing.

        Args:
            snippet: VIN snippet with padded semidense
                ``Tensor["B P C_sem", float32]`` world-point rows, valid
                ``Tensor["B", int64]`` lengths, and optional
                ``PoseTW["B T 12"]`` world-from-rig trajectory poses.
            candidate_poses_world_cam: ``PoseTW["B N_q 12"]`` world-from-camera
                candidate poses. ``PoseTW["N_q 12"]`` inputs gain ``B = 1``.
            reference_pose_world_rig: ``PoseTW["B 12"]`` world-from-rig
                reference poses.
            backbone_out: Actor-visible EVL fields and
                ``PoseTW["B 12"]`` world-from-voxel grid poses.

        Returns:
            `PreparedInputs` with explicit ``B`` and ``N_q`` axes, aligned
            world-from-camera, world-from-rig, and world-from-voxel poses, and
            the padded semidense snippet.
        """
        device = backbone_out.voxel_extent.device
        pose_world_cam = ensure_candidate_batch(candidate_poses_world_cam).to(
            device=device,
        )
        batch_size, num_candidates = (
            int(pose_world_cam.shape[0]),
            int(pose_world_cam.shape[1]),
        )
        pose_world_rig_ref = ensure_pose_batch(
            reference_pose_world_rig.to(device=device),
            batch_size=batch_size,
            name="reference_pose_world_rig",
        )
        if self.config.apply_cw90_correction:
            pose_world_cam = rotate_yaw_cw90(pose_world_cam, undo=True)
            pose_world_rig_ref = rotate_yaw_cw90(pose_world_rig_ref, undo=True)

        t_world_voxel = ensure_pose_batch(
            backbone_out.t_world_voxel,
            batch_size=batch_size,
            name="voxel/T_world_voxel",
        )
        return PreparedInputs(
            pose_world_cam=pose_world_cam,
            pose_world_rig_ref=pose_world_rig_ref,
            t_world_voxel=t_world_voxel,
            batch_size=batch_size,
            num_candidates=num_candidates,
            device=device,
            snippet=snippet,
        )

    def _encode_traj_features(
        self,
        snippet: EfmSnippetView | VinSnippetView,
        *,
        pose_world_rig_ref: PoseTW,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[Tensor | None, Tensor | None, Tensor | None]:
        """Encode snippet trajectory poses in the reference rig frame.

        This mirrors the v2 trajectory context path but keeps it optional
        (disabled by default) to preserve the streamlined baseline.

        Args:
            snippet (EfmSnippetView | VinSnippetView): Snippet with rig trajectory.
            pose_world_rig_ref: ``PoseTW["B 12"]`` world-from-reference-rig pose.
            batch_size (int): B (batch size).
            device (torch.device): Target device for outputs.
            dtype (torch.dtype): Output dtype.

        Returns:
            Tuple ``(traj_feat, traj_pose_vec, traj_pose_enc)`` shaped as
            ``Tensor["B F_traj", float32]``,
            ``Tensor["B T D_v", float32]``, and
            ``Tensor["B T F_traj", float32]`` when available.

        Notes:
            The trajectory is provided as ``t_world_rig`` (world <- rig_t). We convert
            it into the reference rig frame via:

            - ``T_r_rig_t = (T_w_r)^-1 @ T_w_rig_t``.

            The per-frame encodings can optionally be attended by candidate pose
            tokens (``traj_attn``) to produce a per-candidate context ``traj_ctx``.
        """
        return encode_trajectory_context(
            traj_encoder=self.traj_encoder,
            snippet=snippet,
            pose_world_rig_ref=pose_world_rig_ref,
            batch_size=batch_size,
            device=device,
            dtype=dtype,
        )

    def _build_field_bundle(self, backbone_out: EvlBackboneOutput) -> FieldBundle:
        """Construct the compact voxel scene field and its projection.

        The counts_norm/unknown/new_surface_prior channels encode coverage and
        surface priors that proved robust in sweep diagnostics, while keeping
        the field low-dimensional for stability.

        Args:
            backbone_out: Actor-visible EVL voxel outputs: occupancy,
                occupied-input, centerness, and optional free-space fields as
                ``Tensor["B 1 D H W", float32]``, plus counts as
                ``Tensor["B D H W", int64]``.

        Returns:
            `FieldBundle` containing ``Tensor["B F_in D H W", float32]`` raw
            channels, ``Tensor["B F_g D H W", float32]`` projected features,
            and named single-channel auxiliary fields.
        """

        if not isinstance(backbone_out.occ_pr, torch.Tensor):
            raise RuntimeError("VIN v3 requires backbone_out.occ_pr to be a Tensor.")
        if not isinstance(backbone_out.cent_pr, torch.Tensor):
            raise RuntimeError("VIN v3 requires backbone_out.cent_pr to be a Tensor.")
        if not isinstance(backbone_out.occ_input, torch.Tensor):
            raise RuntimeError("VIN v3 requires backbone_out.occ_input to be a Tensor.")
        if not isinstance(backbone_out.counts, torch.Tensor):
            raise RuntimeError("VIN v3 requires backbone_out.counts to be a Tensor.")

        field_in, field_aux = build_vin_scorer_scene_field(
            backbone_out,
            scene_field_channels=self.config.scene_field_channels,
            model_name="VinModelV3",
        )
        field = self.field_proj(field_in)
        return FieldBundle(field_in=field_in, field=field, aux=field_aux)

    def _encode_semidense_grid_features(
        self,
        proj_data: dict[str, Tensor] | None,
        *,
        batch_size: int,
        num_candidates: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        """Encode semidense projection grids with a tiny CNN.

        This produces a per-candidate 2D grid in screen space (GxG) from the
        projected semidense points and applies a small CNN to obtain richer
        cues than the scalar projection statistics alone.

        Args:
            proj_data (dict[str, Tensor] | None): Projection outputs.
                - ``x``, ``y``, ``z``: ``Tensor["B*N_q P_proj", float32]``
                  pixel coordinates and camera-frame depth in metres.
                - ``valid``: ``Tensor["B*N_q P_proj", bool]`` projection mask.
                - ``image_size``: ``Tensor["B*N_q 2", float32]`` ``(H, W)`` rows.
                - ``num_cams``: scalar integer tensor.
            batch_size (int): B (batch size).
            num_candidates (int): ``N_q`` candidates per batch item.
            device (torch.device): Target device for features.
            dtype (torch.dtype): Output dtype.

        Returns:
            ``Tensor["B N_q F_cnn", float32]`` semidense-grid features.

        Notes:
            Each grid cell aggregates projected points (valid-only) into:
            - occupancy (binary),
            - mean depth,
            - depth std.

            Depth is in camera coordinates (z>0 in front). x/y are in pixel
            coordinates normalized into grid indices via ``image_size``.
        """
        if self.semidense_cnn is None:
            raise RuntimeError("Semidense CNN is disabled.")
        if proj_data is None:
            raise RuntimeError("Semidense projection data is missing.")

        return self.semidense_cnn.encode_projection_features(
            proj_data,
            batch_size=batch_size,
            num_candidates=num_candidates,
            device=device,
            dtype=dtype,
        )

    def _forward_impl(
        self,
        efm: EfmSnippetView | VinSnippetView,
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        return_debug: bool,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> tuple[VinPrediction, VinV3ForwardDiagnostics | None]:
        """Run the VIN v3 forward pass (VIN-Core).

        This method scores a set of candidate camera poses for a single snippet
        using a compact 3D voxel field from EVL and per-candidate semidense
        projection statistics.

        Frame / transform conventions:
            - w: World frame (ASE/EFM global).
            - r: Reference rig frame at the reference timestamp.
            - c_q: Candidate camera frame for candidate q.
            - v: EVL voxel grid frame (axis-aligned metric grid).
            - s: Screen/pixel coordinates from PyTorch3D.

        PoseTW convention:
            - ``pose_world_cam`` stores ``T_w_c`` (world <- cam).
            - ``pose_world_rig_ref`` stores ``T_w_r`` (world <- rig_ref).
            - ``t_world_voxel`` stores ``T_w_v`` (world <- voxel).
            - Pose composition uses ``@`` and point transforms use ``PoseTW * xyz``.

        Branch overview (high-level data flow):
            1) Pose encoding:
               ``T_r_cq = (T_w_r)^-1 @ T_w_cq`` -> (t, R6D) -> LFF MLP -> ``pose_enc``.
            2) Scene field:
               EVL per-voxel scalars in voxel grid v -> concat -> Conv3d -> ``field``.
            3) Candidate voxel coverage:
               Sample ``counts_norm`` at candidate camera centers ``x_w_cq`` -> ``voxel_valid_frac``.
            4) Global context:
               Compute ``pos_grid`` (voxel centers expressed in r, normalized by voxel extent)
               and pool ``field`` with pose queries -> ``global_feat``.
            5) Voxel-projection FiLM:
               Project pooled voxel centers ``x_w_v`` into each candidate camera via ``p3d_cameras``
               (x_s, y_s in pixels; z_s depth) -> ``voxel_proj`` stats -> FiLM(global_feat, voxel_proj).
            6) Semidense projection:
               Sample semidense points ``x_w`` (length-masked) -> project into candidates -> ``semidense_proj``
               stats (+ optional tiny CNN over a GxG occupancy/depth grid).
            7) Optional trajectory context:
               Transform historical rig poses into r and attend by pose tokens -> ``traj_ctx``.
            8) Scoring head:
               Concatenate [pose_enc, global_feat, semidense_proj, (semidense_grid_feat), (traj_ctx)]
               and apply MLP + CORAL -> logits -> prob / expected scores.

        CW90 correction:
            Candidate generation may apply a CW90 yaw convention for visualization. When
            ``apply_cw90_correction=True``, v3 undoes this rotation for PoseTW inputs.
            In that case, callers must also pre-correct ``p3d_cameras`` and set
            ``p3d_cameras.cw90_corrected = True`` to avoid silent pose/camera mismatch.

        Args:
            efm (EfmSnippetView | VinSnippetView): EFM or VIN snippet view.
            candidate_poses_world_cam: ``PoseTW["B N_q 12"]`` world-from-camera poses.
            reference_pose_world_rig: ``PoseTW["B 12"]`` world-from-rig pose.
            p3d_cameras: PyTorch3D camera batch of size ``B * N_q`` aligned
                row-for-row with the candidates.
            return_debug: If ``True``, return `VinV3ForwardDiagnostics`.
            backbone_out: Materialized actor-visible EVL outputs for the snippet.
                Scorer forward requires this cached evidence and does not instantiate or run a backbone.

        Returns:
            Prediction with ``B``/``N_q``-aligned CORAL outputs plus optional diagnostics.
        """
        # Shape notation (see docs/typst/shared/macros.typ):
        # B=batch size, N_q=num_candidates, D/H/W=voxel grid, V=voxel points,
        # P=points per snippet, P_proj=points per projection, F_*=feature dims.
        if self.config.apply_cw90_correction and not getattr(p3d_cameras, "cw90_corrected", False):
            raise RuntimeError(
                "apply_cw90_correction=True requires p3d_cameras to already be CW90-corrected. "
                "Set p3d_cameras.cw90_corrected = True after correcting the camera extrinsics, "
                "or disable apply_cw90_correction.",
            )
        # Inputs: candidate_poses_world_cam is PoseTW (B, N_q, 12),
        # reference_pose_world_rig is PoseTW (B, 12), p3d_cameras batch is B*N_q.
        if not (is_efm_snippet_view_instance(efm) or is_vin_snippet_view_instance(efm)):
            raise TypeError(
                f"VinModelV3 expects a VinSnippetView or EfmSnippetView for `efm`, got {type(efm)}.",
            )
        if backbone_out is None:
            raise RuntimeError(
                "VinModelV3.forward requires cached EVL backbone evidence via `backbone_out`. "
                "Materialize EvlBackboneOutput before calling the scorer; forward does not "
                "instantiate or run `config.backbone`.",
            )

        device = backbone_out.voxel_extent.device

        # vin_snippet.points_world is in WORLD frame (x_w, y_w, z_w) with optional extras per point.
        vin_snippet = self._ensure_vin_snippet(efm, device=device)  # points_world: (B, P, C_sem)
        prepared = self._prepare_inputs(
            vin_snippet,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            backbone_out=backbone_out,
        )
        # prepared.pose_world_cam: (B, N_q, 12) as T_w_cq; prepared.pose_world_rig_ref: (B, 12) as T_w_r.
        pose_feats = encode_pose_features(
            pose_encoder=self.pose_encoder,
            pose_world_cam=prepared.pose_world_cam,
            pose_world_rig_ref=prepared.pose_world_rig_ref,
        )
        # pose_vec: (B, N_q, 9); pose_enc: (B, N_q, F_pose); candidate_center_rig_m: (B, N_q, 3) in rig_ref metres.
        field_bundle = self._build_field_bundle(backbone_out)
        # field_in: (B, F_in, D, H, W); field: (B, F_g, D, H, W)

        candidate_centers_world = prepared.pose_world_cam.t.to(
            dtype=field_bundle.field.dtype,
        )  # (B, N_q, 3)
        # candidate_centers_world are camera centers x_w_cq in WORLD frame (metres).
        counts_norm = field_bundle.aux.get("counts_norm")
        if counts_norm is None:
            raise KeyError("Missing counts_norm in field bundle.")
        pose_finite = torch.isfinite(pose_feats.pose_vec).all(dim=-1)
        voxel_valid_frac = sample_candidate_voxel_coverage(
            counts_norm,
            candidate_centers_world=candidate_centers_world,
            pose_finite=pose_finite,
            t_world_voxel=prepared.t_world_voxel,
            voxel_extent=backbone_out.voxel_extent,
        )

        pts_world = backbone_out.pts_world
        if not isinstance(pts_world, torch.Tensor):
            raise KeyError(
                "Missing backbone output 'voxel/pts_world' required for positional encoding.",
            )
        # pts_world contains WORLD-space voxel center coordinates x_w_v for each voxel cell.
        global_ctx = compute_global_context(
            global_pooler=self.global_pooler,
            field=field_bundle.field,
            pose_enc=pose_feats.pose_enc,
            pts_world=pts_world,
            t_world_voxel=prepared.t_world_voxel,
            pose_world_rig_ref=prepared.pose_world_rig_ref,
            voxel_extent=backbone_out.voxel_extent,
        )
        # global_feat: (B, N_q, F_g); pos_grid: (B, 3, D, H, W) = normalized voxel centers in rig_ref frame.
        global_feat = global_ctx.global_feat
        pool_grid = min(
            int(self.config.global_pool_grid_size),
            int(field_bundle.field.shape[-3]),
            int(field_bundle.field.shape[-2]),
            int(field_bundle.field.shape[-1]),
        )
        voxel_points = pool_voxel_points(
            pts_world,
            grid_shape=(
                int(field_bundle.field.shape[-3]),
                int(field_bundle.field.shape[-2]),
                int(field_bundle.field.shape[-1]),
            ),
            pool_grid=pool_grid,
        )
        # voxel_points: (B, P_proj, 3) WORLD coords with P_proj = G_pool^3 (pooled voxel centers).
        voxel_proj_data = project_points_to_candidate_cameras(
            voxel_points,
            p3d_cameras,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
        )
        # voxel_proj_data: per-camera screen coords (x_s, y_s in pixels) and depth z_s, shape (B*N_q, P_proj).
        voxel_proj = encode_projection_summary(
            voxel_proj_data,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
            dtype=field_bundle.field.dtype,
            grid_size=int(self.config.semidense_proj_grid_size),
            obs_count_max=int(self.config.semidense_obs_count_max),
            inv_dist_std_min=float(self.config.semidense_inv_dist_std_min),
            inv_dist_std_p95=float(self.config.semidense_inv_dist_std_p95),
        )
        # voxel_proj: (B, N_q, F_proj=5)
        if self.voxel_proj_film is not None:
            global_feat = apply_vin_scorer_film(
                global_feat,
                voxel_proj,
                film=self.voxel_proj_film,
                norm=self.voxel_proj_film_norm,
            )
        global_ctx = GlobalContext(pos_grid=global_ctx.pos_grid, global_feat=global_feat)

        # ------------------------------------------------------------------ semidense projection
        semidense_points = sample_semidense_points(
            vin_snippet,
            device=prepared.device,
            max_points=int(self.config.semidense_proj_max_points),
        )
        # semidense_points: (B, P_fr, C_sem) in WORLD frame (XYZ + extras), with P_fr <= semidense_proj_max_points.
        proj_data = project_points_to_candidate_cameras(
            semidense_points,
            p3d_cameras,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
        )
        # proj_data: per-camera screen coords + depth for semidense points, shape (B*N_q, P_fr).
        semidense_proj = encode_projection_summary(
            proj_data,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
            dtype=field_bundle.field.dtype,
            grid_size=int(self.config.semidense_proj_grid_size),
            obs_count_max=int(self.config.semidense_obs_count_max),
            inv_dist_std_min=float(self.config.semidense_inv_dist_std_min),
            inv_dist_std_p95=float(self.config.semidense_inv_dist_std_p95),
        )
        # semidense_proj: (B, N_q, F_proj=5)
        semidense_grid_feat = None
        if self.semidense_cnn is not None:
            semidense_grid_feat = self._encode_semidense_grid_features(
                proj_data,
                batch_size=prepared.batch_size,
                num_candidates=prepared.num_candidates,
                device=prepared.device,
                dtype=field_bundle.field.dtype,
            )
        # semidense_grid_feat: (B, N_q, F_cnn) when enabled
        traj_feat, traj_pose_vec, traj_pose_enc = self._encode_traj_features(
            vin_snippet,
            pose_world_rig_ref=prepared.pose_world_rig_ref,
            batch_size=prepared.batch_size,
            device=prepared.device,
            dtype=field_bundle.field.dtype,
        )
        traj_ctx = None
        if self.traj_attn is not None:
            if traj_pose_enc is None:
                traj_ctx = torch.zeros(
                    (prepared.batch_size, prepared.num_candidates, pose_feats.pose_enc.shape[-1]),
                    device=prepared.device,
                    dtype=field_bundle.field.dtype,
                )
            else:
                traj_ctx, _ = self.traj_attn(
                    query=pose_feats.pose_enc.to(dtype=traj_pose_enc.dtype),
                    key=traj_pose_enc,
                    value=traj_pose_enc,
                    need_weights=False,
                )
                traj_ctx = traj_ctx.to(dtype=field_bundle.field.dtype)
                if self.traj_attn_norm is not None:
                    traj_ctx = self.traj_attn_norm(traj_ctx.transpose(1, 2)).transpose(1, 2)

        semidense_idx = semidense_proj_feature_index("semidense_candidate_vis_frac")
        semidense_candidate_vis_frac = semidense_proj[..., semidense_idx]
        # candidate_valid: (B, N_q); require finite pose + observed voxel + visible semidense.
        candidate_valid = pose_finite & (voxel_valid_frac > 0.0) & (semidense_candidate_vis_frac > 0.0)

        # ------------------------------------------------------------------ final feature assembly + scoring
        # Head input features (per candidate):
        # - pose_enc: relative pose features in rig_ref frame (R6D+LFF).
        # - global_feat: pose-conditioned global scene features from the voxel field (optionally FiLM-modulated).
        # - semidense_proj: per-candidate screen-space coverage/visibility/depth stats from semidense points.
        # - semidense_grid_feat (optional): tiny-CNN encoding over a GxG projection grid.
        # - traj_ctx (optional): trajectory context attended by pose tokens.
        parts: list[Tensor] = [
            pose_feats.pose_enc.to(device=prepared.device, dtype=field_bundle.field.dtype),
            global_feat,
            semidense_proj.to(device=prepared.device, dtype=field_bundle.field.dtype),
        ]
        if semidense_grid_feat is not None:
            parts.append(semidense_grid_feat.to(device=prepared.device, dtype=field_bundle.field.dtype))
        if traj_ctx is not None:
            parts.append(traj_ctx.to(device=prepared.device, dtype=field_bundle.field.dtype))

        feats = torch.cat(parts, dim=-1)  # (B, N_q, F_head)
        flat_feats = feats.reshape(prepared.batch_size * prepared.num_candidates, -1)  # (B*N_q, F_head)
        logits = self.head_coral(self.head_mlp(flat_feats)).reshape(
            prepared.batch_size,
            prepared.num_candidates,
            -1,
        )
        # logits: (B, N_q, K-1)

        prob = coral_logits_to_prob(logits)
        expected, expected_norm = coral_expected_from_logits(logits)  # (B, N_q)

        pred = VinPrediction(
            logits=logits,
            prob=prob,
            expected=expected,
            expected_normalized=expected_norm,
            candidate_valid=candidate_valid,
            voxel_valid_frac=voxel_valid_frac,
            semidense_candidate_vis_frac=semidense_candidate_vis_frac,
        )

        if not return_debug:
            return pred, None

        # ------------------------------------------------------------------
        # ------------------------------------------------------------------ diagnostics

        debug = VinV3ForwardDiagnostics(
            backbone_out=backbone_out,
            candidate_center_rig_m=pose_feats.candidate_center_rig_m,
            pose_enc=pose_feats.pose_enc,
            pose_vec=pose_feats.pose_vec,
            field_in=field_bundle.field_in,
            field=field_bundle.field,
            global_feat=global_feat,
            candidate_valid=candidate_valid,
            voxel_valid_frac=voxel_valid_frac,
            semidense_candidate_vis_frac=semidense_candidate_vis_frac,
            pos_grid=global_ctx.pos_grid,
            feats=feats,
            semidense_proj=semidense_proj,
            semidense_grid_feat=semidense_grid_feat,
            voxel_proj=voxel_proj,
            traj_feat=traj_feat,
            traj_ctx=traj_ctx,
            traj_pose_vec=traj_pose_vec,
            traj_pose_enc=traj_pose_enc,
        )
        return pred, debug

    def forward(
        self,
        efm: EfmSnippetView | VinSnippetView,
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> VinPrediction:
        """Score an aligned candidate set with cached actor-visible evidence.

        Args:
            efm: EFM snippet view or VIN snippet view for the current snippet.
            candidate_poses_world_cam: ``PoseTW["B N_q 12"]`` world-from-camera poses.
            reference_pose_world_rig: ``PoseTW["B 12"]`` world-from-rig pose.
            p3d_cameras: PyTorch3D cameras aligned with the flattened
                ``B * N_q`` candidate rows.
            backbone_out: Required cached actor-visible EVL evidence. ``None``
                is accepted by the signature only to produce a fail-fast error.

        Returns:
            `VinPrediction` with ``Tensor["B N_q K-1", float32]`` CORAL logits,
            ``Tensor["B N_q K", float32]`` probabilities, and aligned expected
            scores and diagnostic validity fields.
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
        efm: EfmSnippetView | VinSnippetView,
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> tuple[VinPrediction, VinV3ForwardDiagnostics]:
        """Run VIN v3 forward pass and return intermediate tensors.

        Args:
            efm: EFM snippet view or VIN snippet view for the current snippet.
            candidate_poses_world_cam: ``PoseTW["B N_q 12"]`` world-from-camera poses.
            reference_pose_world_rig: ``PoseTW["B 12"]`` world-from-rig pose.
            p3d_cameras: PyTorch3D cameras aligned with ``B * N_q`` rows.
            backbone_out: Required cached actor-visible EVL evidence.

        Returns:
            Prediction and ``B``/``N_q``-aligned intermediate tensors.
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
            raise RuntimeError(
                "Expected VinV3ForwardDiagnostics when return_debug=True.",
            )
        return pred, debug

    def init_bin_values(self, values: Tensor, *, overwrite: bool = False) -> None:
        """Initialize learnable bin representatives for CORAL expectation.

        Args:
            values: ``Tensor["K"]`` target bin representatives (e.g., bin means).
            overwrite: If True, overwrite existing bin values.
        """
        self.head_coral.init_bin_values(values, overwrite=overwrite)

    def summarize_vin(
        self,
        batch: VinOracleBatch,
        *,
        include_torchsummary: bool = True,
        torchsummary_depth: int = 3,
    ) -> str:
        """Summarize VIN v3 inputs/outputs for a single oracle-labeled batch.

        This is intended for quick sanity checks when validating the
        streamlined baseline against sweep-derived expectations.

        Args:
            batch: Oracle-labeled batch to inspect.
            include_torchsummary: Whether to include a torchsummary block.
            torchsummary_depth: Depth for torchsummary.

        Returns:
            Human-readable summary string.
        """
        return summarize_vin_v3(
            self, batch, include_torchsummary=include_torchsummary, torchsummary_depth=torchsummary_depth
        )
