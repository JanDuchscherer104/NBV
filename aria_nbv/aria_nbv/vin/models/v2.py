"""VIN v2 (simplified) for RRI prediction with fixed, transparent components.

This module provides a **reduced-configuration** VIN variant that keeps the
most promising architectural pieces while removing mode switches:

1) **Pose encoding (configurable).**
   We express each candidate pose in the reference rig frame,

       T_rig_ref_cam = T_world_rig_ref^{-1} * T_world_cam,

   then encode it with a configurable pose encoder. The default is translation +
   rotation-6D passed through LFF (with learned per-group scaling). Optional
   shell-based LFF/SH encoders are available for experimentation.

2) **Scene field (fixed channels, no hard thresholds).**
   We build a compact voxel field with the most RRI-relevant channels:

       occ_pr, cent_pr, counts_norm, occ_input, free_input, new_surface_prior

   where ``counts_norm`` is log1p-normalized coverage, ``unknown`` is treated as
   ``1 - counts_norm`` (soft), and ``new_surface_prior = unknown * occ_pr``.
   The field is projected via ``1x1x1 Conv3d + GroupNorm + GELU``.

3) **Global context (pose-conditioned attention).**
   A coarse voxel grid is pooled and attended by the pose embeddings. Keys are
   augmented with an LFF positional encoding of XYZ voxel centers derived from
   ``voxel/pts_world`` after mapping those points into the **reference rig frame**.

4) **Semidense view conditioning (projection + frustum MHCA).**
   We project semidense points into each candidate view to derive coverage/depth
   statistics, and we compute a candidate-conditioned **multi-head cross-attention**
   summary over the same projected points. These signals provide explicit
   view-dependent cues aligned with VIN-NBV.

5) **CORAL head.**
   We concatenate pose, global context, semidense projection features, and the
   semidense frustum attention summary (plus any optional priors), then score
   with an MLP + CORAL ordinal head.

Frame-consistency note:
Candidate generation applies ``rotate_yaw_cw90`` (a local +Z roll) to the
reference/candidate poses for UI alignment. EVL backbone outputs do **not**
use this convention. ``VinModelV2`` therefore **undoes** this rotation
before computing pose features.
"""
# NOTE: Additional feature experiments (e.g., RGB/DINOv2 grids) and learnable
# CORAL bin shifts are tracked in docs/contents/todos.qmd.

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator, model_validator
from pytorch3d.renderer.cameras import (  # type: ignore[import-untyped]
    PerspectiveCameras,
)
from torch import Tensor, nn

from aria_nbv.utils.frames import rotate_yaw_cw90

from ...data_handling import EfmSnippetView, VinSnippetView
from ...rri_metrics.coral import coral_expected_from_logits, coral_logits_to_prob
from ...utils import Optimizable, TargetConfig, optimizable_field
from ..backbones import EvlBackboneConfig
from ..diagnostics import summarize_vin_v2
from ..encoders import (
    LearnableFourierFeaturesConfig,
    PointNeXtSEncoder,
    PointNeXtSEncoderConfig,
    PoseEncoder,
    PoseEncoderConfig,
    R6dLffPoseEncoderConfig,
    TrajectoryEncoder,
    TrajectoryEncoderConfig,
    validate_pos_grid_xyz_encoder,
)
from ..geometry import ensure_candidate_batch, ensure_pose_batch, sample_voxel_field
from ..geometry.semidense_schema import SEMIDENSE_PROJ_DIM
from ..modules import PoseConditionedGlobalPool, VinScorerHeadConfig, largest_divisor_leq
from ..types import (
    EvlBackboneOutput,
    FieldBundle,
    GlobalContext,
    PreparedInputs,
    VinPrediction,
    VinV2ForwardDiagnostics,
)
from ._context_mixin import PoseFeatureGlobalContextMixin
from ._v2_semidense import (
    encode_semidense_projection_features_v2,
    project_semidense_points_v2,
    sample_semidense_points_v2,
)

if TYPE_CHECKING:
    from aria_nbv.data_handling import VinOracleBatch

    from ..encoders import LearnableFourierFeatures


FIELD_CHANNELS_V2: tuple[str, ...] = (
    "occ_pr",
    "occ_input",
    "counts_norm",
    "cent_pr",
    "free_input",
    "unknown",
    "new_surface_prior",
)

SEMIDENSE_FRUSTUM_TOKEN_FEATURES: tuple[str, ...] = (
    "x_norm",
    "y_norm",
    "depth_m",
    "inv_dist_std",
    "obs_count",
)
SEMIDENSE_FRUSTUM_TOKEN_DIM = len(SEMIDENSE_FRUSTUM_TOKEN_FEATURES)


class VinModelV2Config(TargetConfig["VinModelV2"]):
    """Configuration for `VinModelV2` (minimal, configurable)."""

    @property
    def target_type(self) -> type[VinModelV2]:
        """Factory target for `BaseConfig.setup_target`."""
        return VinModelV2

    backbone: EvlBackboneConfig | None = Field(default_factory=EvlBackboneConfig)
    """Optional frozen EVL backbone configuration."""

    pose_encoder: PoseEncoderConfig = Field(default_factory=R6dLffPoseEncoderConfig)
    """Pose encoder configuration (discriminated union).

    Note: shell-based encoders use only the forward direction and therefore do
    not encode roll about the forward axis; this is acceptable when roll jitter
    is small.
    """

    pos_grid_encoder_lff: LearnableFourierFeaturesConfig = Field(
        default_factory=lambda: LearnableFourierFeaturesConfig(
            input_dim=3,
            fourier_dim=32,
            hidden_dim=32,
            output_dim=16,
        ),
    )
    """LFF encoder for XYZ voxel position keys (input_dim=3)."""

    head_hidden_dim: int = optimizable_field(
        default=128,
        optimizable=Optimizable.discrete(
            low=64,
            high=512,
            step=64,
            description="Hidden dimension for the scorer MLP.",
        ),
        gt=0,
    )
    """Hidden dimension for the scorer MLP."""

    head_num_layers: int = optimizable_field(
        default=2,
        optimizable=Optimizable.discrete(
            low=1,
            high=3,
            step=1,
            description="Number of MLP layers before the CORAL layer.",
        ),
        ge=1,
    )
    """Number of MLP layers before the CORAL layer."""

    head_dropout: float = optimizable_field(
        default=0.05,
        optimizable=Optimizable.continuous(
            low=0.0,
            high=0.4,
            description="Dropout probability in the MLP.",
        ),
        ge=0.0,
        lt=1.0,
    )
    """Dropout probability in the MLP."""

    head_activation: Literal["gelu", "relu"] = "gelu"
    """Activation function ('gelu' or 'relu')."""

    num_classes: int = Field(default=15, ge=2)
    """Number of ordinal bins (VIN-NBV uses 15)."""

    coral_preinit_bias: bool = True
    """ If true, it will pre-initialize the biases to descending values in
        [0, 1] range instead of initializing it to all zeros. This pre-
        initialization scheme results in faster learning and better
        generalization performance in practice."""

    field_dim: int = optimizable_field(
        default=8,
        optimizable=Optimizable.discrete(
            low=8,
            high=64,
            step=8,
            description="Channel dimension of the projected voxel field.",
        ),
        gt=0,
    )
    """Channel dimension of the projected voxel field."""

    field_gn_groups: int = optimizable_field(
        default=4,
        optimizable=Optimizable.discrete(
            low=1,
            high=8,
            step=1,
            description="GroupNorm groups for the projected voxel field.",
        ),
        gt=0,
    )
    """Requested GroupNorm groups (clamped to a divisor of ``field_dim``)."""

    use_point_encoder: bool = optimizable_field(
        default=False,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Enable the PointNeXt semidense point encoder.",
        ),
    )
    """Whether to enable the semidense point encoder (if configured)."""

    point_encoder: PointNeXtSEncoderConfig | None = None
    """Optional PointNeXt-S encoder for semidense point cloud features."""

    use_traj_encoder: bool = optimizable_field(
        default=True,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Enable the trajectory encoder for snippet rig poses.",
        ),
    )
    """Whether to enable the trajectory encoder (if configured)."""

    traj_encoder: TrajectoryEncoderConfig | None = Field(default_factory=lambda: TrajectoryEncoderConfig())
    """Optional trajectory encoder for snippet rig poses."""

    semidense_proj_grid_size: int = optimizable_field(
        default=16,
        optimizable=Optimizable.discrete(
            low=8,
            high=24,
            step=4,
            description="Spatial grid size for semidense projection coverage features.",
            relies_on={"module_config.vin.use_point_encoder": (True,)},
        ),
        gt=0,
    )
    """Spatial grid size used for semidense projection coverage features."""

    semidense_proj_max_points: int = optimizable_field(
        default=4096,
        optimizable=Optimizable.discrete(
            low=2048,
            high=8192,
            step=1024,
            description="Maximum semidense points used for projection features.",
            relies_on={"module_config.vin.use_point_encoder": (True,)},
        ),
        gt=0,
    )
    """Maximum semidense points used for projection features."""

    semidense_frustum_max_points: int = optimizable_field(
        default=1024,
        optimizable=Optimizable.discrete(
            low=256,
            high=2048,
            step=256,
            description="Maximum semidense points used for frustum MHCA.",
            relies_on={"module_config.vin.use_point_encoder": (True,)},
        ),
        gt=0,
    )
    """Maximum semidense points used for frustum MHCA."""

    enable_semidense_frustum: bool = optimizable_field(
        default=False,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Enable semidense frustum MHCA features.",
            relies_on={"module_config.vin.use_point_encoder": (True,)},
        ),
    )
    """Enable semidense frustum MHCA features (optional)."""

    semidense_include_obs_count: bool = optimizable_field(
        default=True,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Whether to append per-point observation counts when available.",
            relies_on={"module_config.vin.use_point_encoder": (True,)},
        ),
    )
    """Whether to append per-point observation counts when available."""

    semidense_obs_count_norm: Literal["none", "log1p", "log1p_norm"] = optimizable_field(
        default="log1p_norm",
        optimizable=Optimizable.categorical(
            choices=("none", "log1p", "log1p_norm"),
            description="Normalization mode for semidense observation counts.",
            relies_on={
                "module_config.vin.use_point_encoder": (True,),
                "module_config.vin.semidense_include_obs_count": (True,),
            },
        ),
    )
    """Normalization mode for per-point observation counts."""

    semidense_visibility_embed: bool = optimizable_field(
        default=True,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Whether to add a learned visibility embedding to semidense tokens.",
            relies_on={
                "module_config.vin.use_point_encoder": (True,),
                "module_config.vin.enable_semidense_frustum": (True,),
            },
        ),
    )
    """Whether to add a learned visibility embedding to semidense frustum tokens."""

    semidense_frustum_mask_invalid: bool = optimizable_field(
        default=False,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Mask invalid semidense tokens in frustum attention (False keeps them with visibility embed).",
            relies_on={
                "module_config.vin.use_point_encoder": (True,),
                "module_config.vin.enable_semidense_frustum": (True,),
            },
        ),
    )
    """If True, mask invalid semidense tokens in frustum attention."""

    use_voxel_valid_frac_feature: bool = optimizable_field(
        default=False,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Append voxel_valid_frac (and 1-voxel_valid_frac) to the head input.",
        ),
    )
    """Whether to append voxel coverage scalars to the head input."""

    use_voxel_valid_frac_gate: bool = optimizable_field(
        default=True,
        optimizable=Optimizable.categorical(
            choices=(True, False),
            description="Gate voxel/global features based on voxel_valid_frac.",
        ),
    )
    """Whether to gate voxel/global features based on voxel coverage."""

    candidate_min_voxel_valid_frac: float = Field(default=0.0, ge=0.0, le=1.0)
    """Minimum voxel valid fraction to flag a candidate as valid (diagnostics only)."""

    candidate_min_semidense_valid_frac: float = Field(default=0.0, ge=0.0, le=1.0)
    """Minimum semidense valid fraction to flag a candidate as valid (diagnostics only)."""

    candidate_min_valid_frac: float | None = Field(default=None)
    """Deprecated: use candidate_min_voxel_valid_frac / candidate_min_semidense_valid_frac."""

    apply_cw90_correction: bool = True
    """Undo ``rotate_yaw_cw90`` on candidate/reference poses + cameras."""

    global_pool_grid_size: int = optimizable_field(
        default=6,
        optimizable=Optimizable.discrete(
            low=4,
            high=8,
            step=1,
            description="Target grid size for pose-conditioned global pooling.",
        ),
        gt=0,
    )
    """Target grid size for pose-conditioned global pooling."""

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
            "occ_pr",
            "occ_input",
            "counts_norm",
            "cent_pr",
            "free_input",
            "new_surface_prior",
        ],
    )

    """Ordered list of scene-field channels to include in the voxel field."""

    tf_pos_grid_in_candidate_frame: bool = False
    """If True, transform voxel positions into each candidate frame for positional keys.

    Deprecated: kept to load older configs; not currently implemented.
    """

    _validate_pos_grid_encoder_lff = field_validator("pos_grid_encoder_lff")(validate_pos_grid_xyz_encoder)

    @model_validator(mode="after")
    def _apply_candidate_min_valid_frac(self) -> "VinModelV2Config":
        if self.use_point_encoder and self.point_encoder is None:
            raise ValueError("use_point_encoder=True requires a point_encoder configuration.")
        if self.candidate_min_valid_frac is not None:
            if self.candidate_min_voxel_valid_frac == 0.0 and self.candidate_min_semidense_valid_frac == 0.0:
                value = float(self.candidate_min_valid_frac)
                self.candidate_min_voxel_valid_frac = value
                self.candidate_min_semidense_valid_frac = value
        return self


class VinModelV2(PoseFeatureGlobalContextMixin, nn.Module):
    """Simplified VIN head for RRI prediction with configurable pose encoding."""

    def __init__(self, config: VinModelV2Config) -> None:
        super().__init__()
        self.config = config
        # Lazily initialize the backbone on first forward if needed.
        self.backbone = None
        self.pose_encoder: PoseEncoder = self.config.pose_encoder.setup_target()
        point_encoder_cfg = self.config.point_encoder if self.config.use_point_encoder else None
        traj_encoder_cfg = self.config.traj_encoder if self.config.use_traj_encoder else None
        self.point_encoder: PointNeXtSEncoder | None = (
            point_encoder_cfg.setup_target() if point_encoder_cfg is not None else None
        )
        self.traj_encoder: TrajectoryEncoder | None = (
            traj_encoder_cfg.setup_target() if traj_encoder_cfg is not None else None
        )
        self.traj_attn: nn.MultiheadAttention | None = None
        self.traj_attn_norm: nn.GroupNorm | None = None
        self.voxel_gate: nn.Module | None = None
        self.point_film: nn.Module | None = None
        self.point_film_norm: nn.GroupNorm | None = None
        self.sem_proj_film: nn.Module | None = None
        self.sem_proj_film_norm: nn.GroupNorm | None = None
        self.sem_frustum_q_proj: nn.Linear | None = None
        self.sem_frustum_proj: nn.Linear | None = None
        self.sem_frustum_attn: nn.MultiheadAttention | None = None
        self.sem_frustum_norm_q: nn.LayerNorm | None = None
        self.sem_frustum_norm_kv: nn.LayerNorm | None = None
        self.sem_frustum_mlp: nn.Module | None = None
        self.sem_frustum_mlp_norm: nn.LayerNorm | None = None
        self.sem_frustum_vis_embed: nn.Embedding | None = None

        field_dim = self.config.field_dim
        gn_groups = largest_divisor_leq(field_dim, self.config.field_gn_groups)
        self.field_proj = nn.Sequential(
            nn.Conv3d(
                len(self.config.scene_field_channels),
                field_dim,
                kernel_size=1,
                bias=False,
            ),
            nn.GroupNorm(num_groups=gn_groups, num_channels=field_dim),
            nn.GELU(),
        )

        pose_dim = self.pose_encoder.out_dim
        num_heads = largest_divisor_leq(field_dim, 4)
        self.global_pooler = PoseConditionedGlobalPool(
            field_dim=field_dim,
            pose_dim=pose_dim,
            pool_size=self.config.global_pool_grid_size,
            num_heads=num_heads,
            pos_grid_encoder=self.config.pos_grid_encoder_lff,
        )
        if self.config.use_voxel_valid_frac_gate:
            self.voxel_gate = nn.Sequential(
                nn.Linear(1, field_dim),
                nn.Sigmoid(),
            )

        point_dim = int(self.point_encoder.out_dim) if self.point_encoder is not None else 0
        if self.point_encoder is not None:
            self.point_film = nn.Linear(point_dim, 2 * field_dim, bias=True)
            film_groups = largest_divisor_leq(field_dim, 4)
            self.point_film_norm = nn.GroupNorm(
                num_groups=film_groups,
                num_channels=field_dim,
            )
        self.sem_proj_film = nn.Linear(SEMIDENSE_PROJ_DIM, 2 * field_dim, bias=True)
        sem_proj_groups = largest_divisor_leq(field_dim, 4)
        self.sem_proj_film_norm = nn.GroupNorm(
            num_groups=sem_proj_groups,
            num_channels=field_dim,
        )
        if self.config.enable_semidense_frustum:
            self.sem_frustum_q_proj = nn.Linear(pose_dim, field_dim, bias=True)
            self.sem_frustum_proj = nn.Linear(SEMIDENSE_FRUSTUM_TOKEN_DIM, field_dim, bias=True)
            self.sem_frustum_attn = nn.MultiheadAttention(
                embed_dim=field_dim,
                num_heads=num_heads,
                batch_first=True,
            )
            self.sem_frustum_norm_q = nn.LayerNorm(field_dim)
            self.sem_frustum_norm_kv = nn.LayerNorm(field_dim)
            self.sem_frustum_mlp = nn.Sequential(
                nn.Linear(field_dim, field_dim * 2),
                nn.GELU(),
                nn.Linear(field_dim * 2, field_dim),
            )
            self.sem_frustum_mlp_norm = nn.LayerNorm(field_dim)
            if self.config.semidense_visibility_embed:
                self.sem_frustum_vis_embed = nn.Embedding(2, SEMIDENSE_FRUSTUM_TOKEN_DIM)
        traj_ctx_dim = pose_dim if self.traj_encoder is not None else 0
        frustum_dim = field_dim if self.config.enable_semidense_frustum else 0
        voxel_frac_dim = 2 if self.config.use_voxel_valid_frac_feature else 0
        head_in_dim = (
            pose_dim + field_dim + point_dim + traj_ctx_dim + SEMIDENSE_PROJ_DIM + frustum_dim + voxel_frac_dim
        )
        head = VinScorerHeadConfig(
            hidden_dim=int(self.config.head_hidden_dim),
            num_layers=int(self.config.head_num_layers),
            dropout=float(self.config.head_dropout),
            num_classes=int(self.config.num_classes),
            coral_preinit_bias=bool(self.config.coral_preinit_bias),
            activation=self.config.head_activation,
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
            traj_gn_groups = largest_divisor_leq(traj_dim, 4)
            self.traj_attn_norm = nn.GroupNorm(
                num_groups=traj_gn_groups,
                num_channels=traj_dim,
            )
        device = self.backbone.device if self.backbone is not None else torch.device("cpu")
        self.to(device)

    @property
    def pose_encoder_lff(self) -> LearnableFourierFeatures | None:
        """Return the LFF encoder when the pose encoder uses LFF (else ``None``)."""
        return getattr(self.pose_encoder, "pose_encoder_lff", None)

    def _maybe_snippet_view(
        self,
        efm: EfmSnippetView | VinSnippetView | dict[str, Any],
    ) -> EfmSnippetView | VinSnippetView | None:
        """Best-effort conversion of cached EFM dicts into snippet views."""
        if isinstance(efm, (EfmSnippetView, VinSnippetView)):
            return efm
        if not isinstance(efm, dict):
            return None
        try:
            return EfmSnippetView.from_cache_efm(efm)
        except Exception:
            return None

    def _prepare_inputs(
        self,
        efm: EfmSnippetView | VinSnippetView | dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        backbone_out: EvlBackboneOutput,
    ) -> PreparedInputs:
        """Prepare batched inputs and align poses for the forward pass."""
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
            snippet=self._maybe_snippet_view(efm),
        )

    def _build_field_bundle(self, backbone_out: EvlBackboneOutput) -> FieldBundle:
        """Construct the scene field and its projection."""

        field_in, field_aux = self._build_vin_scorer_scene_field(
            backbone_out,
            scene_field_channels=self.config.scene_field_channels,
            model_name="VinModelV2",
        )
        field = self.field_proj(field_in)
        return FieldBundle(field_in=field_in, field=field, aux=field_aux)

    def _normalize_obs_count(self, obs_count: Tensor) -> Tensor:
        """Normalize observation counts according to configuration."""
        mode = self.config.semidense_obs_count_norm
        if mode == "none":
            return obs_count
        obs = torch.log1p(obs_count.clamp_min(0.0))
        if mode == "log1p":
            return obs
        if mode == "log1p_norm":
            denom = obs.max().clamp_min(1.0)
            return obs / denom
        raise ValueError(f"Unknown semidense_obs_count_norm='{mode}'.")

    def _encode_semidense_features(
        self,
        points_world: Tensor | None,
        *,
        pose_world_rig_ref: PoseTW,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor | None:
        """Encode semidense points if a point encoder is configured."""
        if self.point_encoder is None:
            return None
        if points_world is None or points_world.numel() == 0:
            semidense_feat = torch.zeros(
                (batch_size, self.point_encoder.out_dim),
                device=device,
                dtype=dtype,
            )
        else:
            pts_world = points_world.to(dtype=torch.float32)
            if pts_world.ndim == 2:
                pts_world = pts_world.unsqueeze(0)
            if pts_world.shape[0] == 1 and batch_size > 1:
                pts_world = pts_world.expand(batch_size, -1, -1)
            if pts_world.shape[0] != batch_size:
                raise ValueError(
                    "Semidense points batch size must match candidates or be broadcastable.",
                )
            pts_world = pts_world.to(device=device)

            xyz = pts_world[..., :3]
            extra = pts_world[..., 3:] if pts_world.shape[-1] > 3 else None

            valid_xyz = torch.isfinite(xyz).all(dim=-1)
            has_points = valid_xyz.any(dim=1)

            out_dim = int(self.point_encoder.out_dim)
            semidense_feat = torch.zeros((batch_size, out_dim), device=device, dtype=dtype)
            if not bool(has_points.any().item()):
                return semidense_feat

            target_points = int(xyz.shape[1])
            if self.config.point_encoder is not None:
                target_points = min(target_points, int(self.config.point_encoder.max_points))

            selected_xyz: list[torch.Tensor] = []
            selected_extra: list[torch.Tensor] | None = [] if extra is not None else None
            for b in torch.nonzero(has_points, as_tuple=False).reshape(-1).tolist():
                valid_idx = torch.nonzero(valid_xyz[b], as_tuple=False).reshape(-1)
                if valid_idx.numel() >= target_points:
                    chosen = valid_idx[:target_points]
                else:
                    pad = valid_idx[-1:].expand(target_points - valid_idx.numel())
                    chosen = torch.cat([valid_idx, pad], dim=0)
                selected_xyz.append(xyz[b, chosen])
                if selected_extra is not None and extra is not None:
                    selected_extra.append(extra[b, chosen])

            xyz_sel = torch.stack(selected_xyz, dim=0)
            t_rig_world = pose_world_rig_ref.inverse()
            t_rig_world_sel = PoseTW(t_rig_world.tensor()[has_points])
            pts_rig = t_rig_world_sel * xyz_sel
            if selected_extra is not None and extra is not None:
                extra_sel = torch.stack(selected_extra, dim=0).to(dtype=pts_rig.dtype)
                extra_sel = torch.nan_to_num(extra_sel, nan=0.0, posinf=0.0, neginf=0.0)
                if extra_sel.shape[-1] > 1:
                    inv_dist_std = extra_sel[..., :1]
                    obs_count = extra_sel[..., 1:2]
                    obs_count = self._normalize_obs_count(obs_count)
                    extra_sel = torch.cat([inv_dist_std, obs_count], dim=-1)
                pts_rig = torch.cat([pts_rig, extra_sel], dim=-1)
            pts_rig = torch.nan_to_num(pts_rig, nan=0.0, posinf=0.0, neginf=0.0)

            encoded = self.point_encoder(pts_rig.to(device=device))
            semidense_feat[has_points] = encoded.to(dtype=dtype)
        return semidense_feat.to(device=device, dtype=dtype)

    def _sample_semidense_points(
        self,
        snippet: EfmSnippetView | VinSnippetView | None,
        *,
        max_points: int,
        device: torch.device,
    ) -> Tensor | None:
        """Sample semidense points once for shared use."""
        return sample_semidense_points_v2(
            snippet,
            max_points=max_points,
            device=device,
            include_obs_count=bool(self.config.semidense_include_obs_count),
        )

    def _project_semidense_points(
        self,
        points_world: Tensor | None,
        p3d_cameras: PerspectiveCameras,
        *,
        batch_size: int,
        num_candidates: int,
        device: torch.device,
    ) -> dict[str, Tensor] | None:
        """Project semidense points into candidate cameras and return screen coords + masks."""
        return project_semidense_points_v2(
            points_world,
            p3d_cameras,
            batch_size=batch_size,
            num_candidates=num_candidates,
            device=device,
        )

    def _encode_semidense_projection_features(
        self,
        proj_data: dict[str, Tensor] | None,
        *,
        batch_size: int,
        num_candidates: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        """Project semidense points into each candidate view and summarize coverage/depth."""
        return encode_semidense_projection_features_v2(
            proj_data,
            batch_size=batch_size,
            num_candidates=num_candidates,
            device=device,
            dtype=dtype,
            grid_size=int(self.config.semidense_proj_grid_size),
        )

    def _encode_semidense_frustum_context(
        self,
        proj_data: dict[str, Tensor] | None,
        pose_enc: Tensor,
        *,
        batch_size: int,
        num_candidates: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Tensor:
        """Compute candidate-conditioned MHCA summary over projected semidense points."""
        out_dim = int(self.config.field_dim)
        frustum_feat = torch.zeros(
            (batch_size, num_candidates, out_dim),
            device=device,
            dtype=dtype,
        )
        if not self.config.enable_semidense_frustum:
            return frustum_feat
        if (
            self.sem_frustum_q_proj is None
            or self.sem_frustum_proj is None
            or self.sem_frustum_attn is None
            or self.sem_frustum_norm_q is None
            or self.sem_frustum_norm_kv is None
            or self.sem_frustum_mlp is None
            or self.sem_frustum_mlp_norm is None
        ):
            return frustum_feat
        if proj_data is None:
            return frustum_feat

        x = proj_data["x"]
        y = proj_data["y"]
        z = proj_data["z"]
        valid = proj_data["valid"]
        image_size = proj_data["image_size"]
        inv_dist_std = proj_data.get("inv_dist_std")
        if inv_dist_std is not None and inv_dist_std.numel() == 0:
            inv_dist_std = None
        obs_count = proj_data.get("obs_count")
        if obs_count is not None and obs_count.numel() == 0:
            obs_count = None
        num_cams = int(proj_data["num_cams"].item())

        h = image_size[:, 0].unsqueeze(1).clamp_min(1.0)
        w = image_size[:, 1].unsqueeze(1).clamp_min(1.0)
        x_safe = torch.where(valid, x, torch.zeros_like(x))
        y_safe = torch.where(valid, y, torch.zeros_like(y))
        z_safe = torch.where(valid, z, torch.zeros_like(z))
        x_safe = torch.nan_to_num(x_safe, nan=0.0, posinf=0.0, neginf=0.0)
        y_safe = torch.nan_to_num(y_safe, nan=0.0, posinf=0.0, neginf=0.0)
        z_safe = torch.nan_to_num(z_safe, nan=0.0, posinf=0.0, neginf=0.0)
        x_norm = (x_safe / w) * 2.0 - 1.0
        y_norm = (y_safe / h) * 2.0 - 1.0
        depth_m = z_safe
        if inv_dist_std is None:
            inv_feat = torch.zeros_like(depth_m)
        else:
            inv_feat = torch.nan_to_num(
                inv_dist_std.to(device=device, dtype=depth_m.dtype),
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )
        if obs_count is None:
            obs_feat = torch.zeros_like(depth_m)
        else:
            obs_feat = obs_count.to(device=device, dtype=depth_m.dtype)
            obs_feat = self._normalize_obs_count(obs_feat)
            obs_feat = torch.nan_to_num(obs_feat, nan=0.0, posinf=0.0, neginf=0.0)

        tokens = torch.stack([x_norm, y_norm, depth_m, inv_feat, obs_feat], dim=-1)
        if batch_size == 1 and num_cams == num_candidates:
            tokens = tokens.view(1, num_candidates, -1, SEMIDENSE_FRUSTUM_TOKEN_DIM)
            valid = valid.view(1, num_candidates, -1)
        else:
            tokens = tokens.view(batch_size, num_candidates, -1, SEMIDENSE_FRUSTUM_TOKEN_DIM)
            valid = valid.view(batch_size, num_candidates, -1)

        max_points = int(self.config.semidense_frustum_max_points)
        if tokens.shape[2] > max_points:
            tokens = tokens[:, :, :max_points, :]
            valid = valid[:, :, :max_points]

        if self.sem_frustum_vis_embed is not None:
            vis_idx = valid.to(dtype=torch.long)
            tokens = tokens + self.sem_frustum_vis_embed(vis_idx)

        flat_tokens = tokens.reshape(batch_size * num_candidates, -1, SEMIDENSE_FRUSTUM_TOKEN_DIM)
        flat_valid = valid.reshape(batch_size * num_candidates, -1)
        valid_any = flat_valid.any(dim=1)
        if self.config.semidense_frustum_mask_invalid and (~valid_any).any():
            flat_tokens = flat_tokens.clone()
            flat_valid = flat_valid.clone()
            flat_tokens[~valid_any] = 0.0
            flat_valid[~valid_any] = False

        flat_tokens = flat_tokens.to(device=device, dtype=dtype)
        q = self.sem_frustum_q_proj(pose_enc.to(dtype=dtype)).reshape(
            batch_size * num_candidates,
            1,
            out_dim,
        )
        kv = self.sem_frustum_proj(flat_tokens)
        if self.config.semidense_frustum_mask_invalid:
            kv = kv.masked_fill(~flat_valid.unsqueeze(-1), 0.0)
        q_norm = self.sem_frustum_norm_q(q)
        kv_norm = self.sem_frustum_norm_kv(kv)
        key_padding_mask = None
        if self.config.semidense_frustum_mask_invalid:
            key_padding_mask = ~flat_valid
            if (~valid_any).any():
                key_padding_mask = key_padding_mask.clone()
                key_padding_mask[~valid_any] = False
        attn_out, _ = self.sem_frustum_attn(
            q_norm,
            kv_norm,
            kv_norm,
            key_padding_mask=key_padding_mask,
            need_weights=False,
        )
        out = q + attn_out
        out = out + self.sem_frustum_mlp(self.sem_frustum_mlp_norm(out))
        out = out.squeeze(1).reshape(batch_size, num_candidates, out_dim)
        if self.config.semidense_frustum_mask_invalid:
            out = out * valid_any.view(batch_size, num_candidates, 1).to(dtype=out.dtype)
        return out.to(device=device, dtype=dtype)

    def _encode_traj_features(
        self,
        snippet: EfmSnippetView | VinSnippetView | None,
        *,
        pose_world_rig_ref: PoseTW,
        batch_size: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[Tensor | None, Tensor | None, Tensor | None]:
        """Encode trajectory poses in the reference rig frame if configured."""
        return self._encode_trajectory_context(
            traj_encoder=self.traj_encoder,
            snippet=snippet,
            pose_world_rig_ref=pose_world_rig_ref,
            batch_size=batch_size,
            device=device,
            dtype=dtype,
        )

    def _forward_impl(
        self,
        efm: EfmSnippetView | dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        return_debug: bool,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> tuple[VinPrediction, VinV2ForwardDiagnostics | None]:
        """Run the VIN v2 forward pass."""
        efm_dict: dict[str, Any]
        if isinstance(efm, EfmSnippetView):
            efm_dict = efm.efm
        else:
            efm_dict = efm
        if backbone_out is None:
            if self.backbone is None:  # type: ignore
                self.backbone = self.config.backbone.setup_target() if self.config.backbone is not None else None  # type: ignore
            backbone_out = self.backbone.forward(efm_dict)  # type: ignore

        device = backbone_out.voxel_extent.device
        try:
            param_device = next(self.parameters()).device
        except StopIteration:
            param_device = device
        if param_device != device:
            self.to(device)

        prepared = self._prepare_inputs(
            efm,
            candidate_poses_world_cam=candidate_poses_world_cam,
            reference_pose_world_rig=reference_pose_world_rig,
            backbone_out=backbone_out,
        )
        pose_feats = self._encode_pose_features(
            prepared.pose_world_cam,
            prepared.pose_world_rig_ref,
        )
        field_bundle = self._build_field_bundle(backbone_out)

        candidate_centers_world = prepared.pose_world_cam.t.to(
            dtype=field_bundle.field.dtype,
        )
        counts_norm = field_bundle.aux.get("counts_norm")
        if counts_norm is None:
            raise KeyError("Missing counts_norm in field bundle.")
        center_tokens, center_valid = sample_voxel_field(
            counts_norm,
            points_world=candidate_centers_world.unsqueeze(2),
            t_world_voxel=prepared.t_world_voxel,
            voxel_extent=backbone_out.voxel_extent,
        )
        center_valid = center_valid.squeeze(-1)
        counts_norm_center = center_tokens[..., 0, 0]
        pose_finite = (
            torch.isfinite(pose_feats.pose_vec).all(dim=-1)
            if pose_feats.pose_vec is not None
            else torch.ones_like(counts_norm_center, dtype=torch.bool)
        )
        voxel_valid_frac = (counts_norm_center * center_valid.to(dtype=counts_norm_center.dtype)).clamp(0.0, 1.0)
        voxel_valid_frac = (voxel_valid_frac * pose_finite.to(dtype=voxel_valid_frac.dtype)).clamp(0.0, 1.0)

        pts_world = backbone_out.pts_world
        if not isinstance(pts_world, torch.Tensor):
            raise KeyError(
                "Missing backbone output 'voxel/pts_world' required for positional encoding.",
            )
        global_ctx = self._compute_global_context(
            field_bundle.field,
            pose_feats.pose_enc,
            pts_world=pts_world,
            t_world_voxel=prepared.t_world_voxel,
            pose_world_rig_ref=prepared.pose_world_rig_ref,
            voxel_extent=backbone_out.voxel_extent,
        )
        global_feat = global_ctx.global_feat
        if self.voxel_gate is not None:
            gate = self.voxel_gate(voxel_valid_frac.unsqueeze(-1).to(dtype=global_feat.dtype))
            global_feat = global_feat * gate
        global_ctx = GlobalContext(pos_grid=global_ctx.pos_grid, global_feat=global_feat)
        max_points = int(self.config.semidense_proj_max_points)
        if self.point_encoder is not None:
            max_points = min(max_points, int(self.config.point_encoder.max_points))
        semidense_points = self._sample_semidense_points(
            prepared.snippet,
            max_points=max_points,
            device=prepared.device,
        )
        proj_data = self._project_semidense_points(
            semidense_points,
            p3d_cameras,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
        )
        semidense_feat = self._encode_semidense_features(
            semidense_points,
            pose_world_rig_ref=prepared.pose_world_rig_ref,
            batch_size=prepared.batch_size,
            device=prepared.device,
            dtype=field_bundle.field.dtype,
        )
        semidense_proj = self._encode_semidense_projection_features(
            proj_data,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
            dtype=field_bundle.field.dtype,
        )
        semidense_frustum = self._encode_semidense_frustum_context(
            proj_data,
            pose_feats.pose_enc,
            batch_size=prepared.batch_size,
            num_candidates=prepared.num_candidates,
            device=prepared.device,
            dtype=field_bundle.field.dtype,
        )
        global_feat = global_ctx.global_feat
        if semidense_feat is not None and self.point_film is not None:
            global_feat = self._apply_film(
                global_feat,
                semidense_feat[:, None, :],
                film=self.point_film,
                norm=self.point_film_norm,
            )
        if self.sem_proj_film is not None:
            global_feat = self._apply_film(
                global_feat,
                semidense_proj,
                film=self.sem_proj_film,
                norm=self.sem_proj_film_norm,
            )
        global_ctx = GlobalContext(pos_grid=global_ctx.pos_grid, global_feat=global_feat)
        traj_feat, traj_pose_vec, traj_pose_enc = self._encode_traj_features(
            prepared.snippet,
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
                traj_ctx, _ = self.traj_attn.forward(
                    query=pose_feats.pose_enc.to(dtype=traj_pose_enc.dtype),
                    key=traj_pose_enc,
                    value=traj_pose_enc,
                    need_weights=False,
                )
                traj_ctx = traj_ctx.to(dtype=field_bundle.field.dtype)
                if self.traj_attn_norm is not None:
                    traj_ctx = self.traj_attn_norm(traj_ctx.transpose(1, 2)).transpose(1, 2)

        semidense_idx = self._semidense_proj_feature_index("semidense_candidate_vis_frac")
        semidense_candidate_vis_frac = semidense_proj[..., semidense_idx]
        voxel_valid = voxel_valid_frac >= float(self.config.candidate_min_voxel_valid_frac)
        semidense_valid = semidense_candidate_vis_frac >= float(self.config.candidate_min_semidense_valid_frac)
        candidate_valid = voxel_valid & semidense_valid

        # ------------------------------------------------------------------ final feature assembly + scoring
        parts: list[Tensor] = [
            pose_feats.pose_enc.to(device=prepared.device, dtype=field_bundle.field.dtype),
            global_feat,
        ]
        if semidense_feat is not None:
            parts.append(
                semidense_feat[:, None, :].expand(
                    prepared.batch_size,
                    prepared.num_candidates,
                    -1,
                ),
            )
        parts.append(semidense_proj)
        if self.config.enable_semidense_frustum:
            parts.append(semidense_frustum)
        if traj_ctx is not None:
            parts.append(traj_ctx)
        if self.config.use_voxel_valid_frac_feature:
            parts.append(voxel_valid_frac.unsqueeze(-1).to(dtype=field_bundle.field.dtype))
            parts.append((1.0 - voxel_valid_frac).unsqueeze(-1).to(dtype=field_bundle.field.dtype))

        feats = torch.cat(parts, dim=-1)
        flat_feats = feats.reshape(prepared.batch_size * prepared.num_candidates, -1)
        logits = self.head_coral(self.head_mlp(flat_feats)).reshape(
            prepared.batch_size,
            prepared.num_candidates,
            -1,
        )

        prob = coral_logits_to_prob(logits)
        expected, expected_norm = coral_expected_from_logits(logits)

        pred = VinPrediction(
            logits=logits,
            prob=prob,
            expected=expected,
            expected_normalized=expected_norm,
            candidate_valid=candidate_valid,
            voxel_valid_frac=voxel_valid_frac,
            semidense_candidate_vis_frac=semidense_candidate_vis_frac,
            semidense_valid_frac=semidense_candidate_vis_frac,
        )

        if not return_debug:
            return pred, None

        # ------------------------------------------------------------------
        # ------------------------------------------------------------------ diagnostics

        debug = VinV2ForwardDiagnostics(
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
            semidense_valid_frac=semidense_candidate_vis_frac,
            pos_grid=global_ctx.pos_grid,
            feats=feats,
            semidense_feat=semidense_feat,
            semidense_proj=semidense_proj,
            semidense_frustum=semidense_frustum,
            traj_feat=traj_feat,
            traj_ctx=traj_ctx,
            traj_pose_vec=traj_pose_vec,
            traj_pose_enc=traj_pose_enc,
        )
        return pred, debug

    def forward(
        self,
        efm: EfmSnippetView | dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> VinPrediction:
        """Score candidate poses for one snippet (no diagnostics)."""
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
        efm: EfmSnippetView | dict[str, Any],
        candidate_poses_world_cam: PoseTW,
        reference_pose_world_rig: PoseTW,
        p3d_cameras: PerspectiveCameras,
        backbone_out: EvlBackboneOutput | None = None,
    ) -> tuple[VinPrediction, VinV2ForwardDiagnostics]:
        """Run VIN v2 forward pass and return intermediate tensors."""
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
                "Expected VinV2ForwardDiagnostics when return_debug=True.",
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
        """Summarize VIN v2 inputs and outputs for one oracle-labeled batch.

        The report body lives in `aria_nbv.vin.diagnostics.summarize_v2` so the
        model class remains focused on modules, tensor flow, and scorer state.
        """
        return summarize_vin_v2(
            self,
            batch,
            include_torchsummary=include_torchsummary,
            torchsummary_depth=torchsummary_depth,
        )
