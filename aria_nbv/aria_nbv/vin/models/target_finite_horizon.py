"""Actor-only finite-horizon scorer for persisted Q_H chain views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import TargetConfig
from ..encoders import R6dLffPoseEncoder, R6dLffPoseEncoderConfig

if TYPE_CHECKING:
    from ...data_handling.qh_data import QhActorTensors

QhSceneChannel = Literal["occ_pr", "occ_input", "free_input", "counts", "cent_pr"]


class TargetFiniteHorizonScorerConfig(TargetConfig["TargetFiniteHorizonScorer"]):
    """Configure the deployable actor-only finite-horizon value scorer."""

    hidden_dim: int = Field(default=128, gt=0)
    """Shared candidate and state token width."""

    pose_encoder: R6dLffPoseEncoderConfig = Field(default_factory=R6dLffPoseEncoderConfig)
    """R6D plus LFF encoder used for target, candidate, and history poses."""

    scene_channels: tuple[QhSceneChannel, ...] = (
        "occ_pr",
        "occ_input",
        "free_input",
        "counts",
        "cent_pr",
    )
    """Ordered compact root-EVL fields pooled into the state token."""

    representation_semantics: Literal["root_moments_v1"] = "root_moments_v1"
    """Versioned meaning of the scene token: root-frame moments plus support."""

    attention_heads: int = Field(default=4, gt=0)
    """Heads in candidate-to-state attention."""

    dropout: float = Field(default=0.05, ge=0.0, lt=1.0)
    """Training-only dropout in attention and the value head."""

    max_horizon: int = Field(default=5, gt=0)
    """Largest admitted acquisition horizon; remaining budget is normalized by this value."""

    experiment_profile: Literal["qh_cf0_v1"] = "qh_cf0_v1"
    """Closed deployable actor profile; privileged CF+ observations are not accepted."""

    @property
    def target_type(self) -> type["TargetFiniteHorizonScorer"]:
        """Return the concrete scorer constructed by :meth:`setup_target`."""

        return TargetFiniteHorizonScorer

    @model_validator(mode="after")
    def _validate_architecture(self) -> "TargetFiniteHorizonScorerConfig":
        if self.hidden_dim % self.attention_heads != 0:
            raise ValueError("hidden_dim must be divisible by attention_heads.")
        if not self.scene_channels:
            raise ValueError("scene_channels must contain at least one root-EVL field.")
        if len(set(self.scene_channels)) != len(self.scene_channels):
            raise ValueError("scene_channels must be unique and ordered.")
        return self


class TargetFiniteHorizonScorer(nn.Module):
    """Rank finite candidate rows from actor-visible EVL, target, and history.

    The module exposes one deep interface: a batched
    :class:`~aria_nbv.data_handling.qh_data.QhActorTensors` enters and one
    candidate-aligned value table leaves. Candidate rows never attend to one
    another, so jointly permuting candidate poses and masks permutes the output
    identically. Invalid and padded rows are zeroed after scoring and cannot
    influence admitted rows.
    """

    def __init__(self, config: TargetFiniteHorizonScorerConfig) -> None:
        super().__init__()
        self.config = config
        self.pose_encoder: R6dLffPoseEncoder = config.pose_encoder.setup_target()
        pose_dim = self.pose_encoder.out_dim
        hidden_dim = int(config.hidden_dim)
        scene_dim = 4 * len(config.scene_channels) + 8

        self.candidate_projection = nn.Sequential(
            nn.Linear(pose_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.target_projection = nn.Sequential(
            nn.Linear(pose_dim + 3, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.history_projection = nn.Sequential(
            nn.Linear(pose_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.budget_projection = nn.Sequential(
            nn.Linear(1, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.scene_projection = nn.Sequential(
            nn.Linear(scene_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.state_attention = nn.MultiheadAttention(
            hidden_dim,
            int(config.attention_heads),
            dropout=float(config.dropout),
            batch_first=True,
        )
        self.value_head = nn.Sequential(
            nn.Linear(3 * hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(float(config.dropout)),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, actor: QhActorTensors) -> Tensor:
        """Return continuous candidate values aligned with ``action_mask``.

        Args:
            actor: Batched actor-visible chain with candidate support
                ``Tensor["B S N", bool]`` and compact root EVL evidence.

        Returns:
            values ``Tensor["B S N", float32]``: Finite values on admitted
                rows and zero outside realized actor-valid support.
        """

        self._validate_actor(actor)
        action_mask = actor.action_mask & actor.step_mask.unsqueeze(-1)
        batch_size, steps, width = action_mask.shape

        candidate_active = action_mask
        candidate_pose = self._sanitize_pose(
            actor.candidate_pose_relative_root,
            candidate_active,
            name="candidate",
        )
        history_mask = actor.history_mask & actor.step_mask.unsqueeze(-1)
        history_pose = self._sanitize_pose(actor.history_pose_relative_root, history_mask, name="history")
        target_active = actor.step_mask.any(dim=-1)
        target_pose = self._sanitize_pose(actor.target_pose_relative_root, target_active, name="target")
        if bool((target_active.unsqueeze(-1) & ~torch.isfinite(actor.target_extents)).any()):
            raise ValueError("Q_H active target extents must be finite.")

        candidate_features = self.pose_encoder.encode(candidate_pose).pose_enc
        candidate_tokens = self.candidate_projection(candidate_features)
        candidate_tokens = torch.where(action_mask.unsqueeze(-1), candidate_tokens, torch.zeros_like(candidate_tokens))

        target_features = self.pose_encoder.encode(target_pose).pose_enc
        target_token = self.target_projection(torch.cat((target_features, actor.target_extents.float()), dim=-1))

        history_features = self.pose_encoder.encode(history_pose).pose_enc
        history_sum = torch.where(history_mask.unsqueeze(-1), history_features, torch.zeros_like(history_features)).sum(
            dim=-2
        )
        history_count = history_mask.sum(dim=-1, keepdim=True).clamp_min(1)
        history_token = self.history_projection(history_sum / history_count)

        budget = actor.horizon_remaining.float().unsqueeze(-1) / float(self.config.max_horizon)
        budget_token = self.budget_projection(budget)
        scene_token = self.scene_projection(self._scene_summary(actor)).unsqueeze(1).expand(-1, steps, -1)
        target_token = target_token.unsqueeze(1).expand(-1, steps, -1)

        state_tokens = torch.stack((scene_token, target_token, history_token, budget_token), dim=-2)
        flat_candidates = candidate_tokens.reshape(batch_size * steps, width, -1)
        flat_state = state_tokens.reshape(batch_size * steps, state_tokens.shape[-2], -1)
        attended, _weights = self.state_attention(
            flat_candidates,
            flat_state,
            flat_state,
            need_weights=False,
        )
        attended = attended.reshape(batch_size, steps, width, -1)
        values = self.value_head(torch.cat((candidate_tokens, attended, candidate_tokens * attended), dim=-1)).squeeze(
            -1
        )
        values = torch.where(action_mask, values, torch.zeros_like(values))
        if not bool(torch.isfinite(values[action_mask]).all()):
            raise ValueError("TargetFiniteHorizonScorer produced nonfinite values on actor-valid rows.")
        return values

    def _scene_summary(self, actor: QhActorTensors) -> Tensor:
        """Pool detached root EVL and semidense evidence into one chain token."""

        context = actor.static_context
        if context is None:  # guarded by _validate_actor
            raise ValueError("TargetFiniteHorizonScorer requires compact root EVL context.")
        pooled = [self._pool_channel(getattr(context, name)) for name in self.config.scene_channels]

        points = actor.vin_snippet.points_world.detach().float()[..., :3]
        if points.ndim != 3:
            raise ValueError(f"Q_H batched semidense points must have shape (B,P,C), got {tuple(points.shape)}.")
        lengths = actor.vin_snippet.lengths.reshape(points.shape[0], -1)[:, 0].long()
        if bool((lengths < 0).any() or (lengths > points.shape[1]).any()):
            raise ValueError(f"Q_H semidense lengths must be in [0,{points.shape[1]}].")
        point_mask = torch.arange(points.shape[1], device=points.device).unsqueeze(0) < lengths.unsqueeze(1)
        finite = torch.isfinite(points).all(dim=-1)
        point_mask &= finite
        root_active = actor.step_mask.any(dim=-1)
        root_from_world = self._sanitize_pose(actor.root_pose_world, root_active, name="root").inverse()
        points_root = root_from_world.transform(points)
        safe_points = torch.where(point_mask.unsqueeze(-1), points_root, torch.zeros_like(points_root))
        valid_count = point_mask.sum(dim=1, keepdim=True)
        count = valid_count.clamp_min(1)
        mean = safe_points.sum(dim=1) / count
        centered = torch.where(point_mask.unsqueeze(-1), points_root - mean.unsqueeze(1), torch.zeros_like(points_root))
        std = (centered.square().sum(dim=1) / count).sqrt()
        support = (valid_count.float() / max(points.shape[1], 1)).clamp(0.0, 1.0)
        present = valid_count.gt(0).float()
        return torch.cat((*pooled, mean, std, present, support), dim=-1)

    @staticmethod
    def _sanitize_pose(pose: PoseTW, active: Tensor, *, name: str) -> PoseTW:
        """Reject active non-finite poses and replace inactive rows by identity."""

        values = pose.tensor()
        finite = torch.isfinite(values).all(dim=-1)
        if bool((active & ~finite).any()):
            raise ValueError(f"Q_H active {name} poses must be finite.")
        identity = PoseTW().tensor().to(device=values.device, dtype=values.dtype).expand_as(values)
        return PoseTW(torch.where(active.unsqueeze(-1), values, identity))

    @staticmethod
    def _pool_channel(value: Tensor | None) -> Tensor:
        """Return mean, standard deviation, minimum, and maximum per batch row."""

        if value is None:
            raise ValueError("TargetFiniteHorizonScorer requires every configured root EVL field.")
        detached = value.detach().float()
        if detached.ndim < 2:
            raise ValueError(f"Q_H root EVL fields require a batch axis, got {tuple(detached.shape)}.")
        flat = detached.reshape(detached.shape[0], -1)
        if not bool(torch.isfinite(flat).all()):
            raise ValueError("TargetFiniteHorizonScorer root EVL fields must be finite.")
        return torch.stack(
            (
                flat.mean(dim=-1),
                flat.std(dim=-1, unbiased=False),
                flat.amin(dim=-1),
                flat.amax(dim=-1),
            ),
            dim=-1,
        )

    def _validate_actor(self, actor: QhActorTensors) -> None:
        """Fail before scoring when the actor profile or padded axes drift."""

        if actor.action_mask.ndim != 3:
            raise ValueError(
                "TargetFiniteHorizonScorer expects a batched action_mask with shape (B,S,N); "
                f"got {tuple(actor.action_mask.shape)}."
            )
        if actor.candidate_mask.shape != actor.action_mask.shape:
            raise ValueError("Q_H candidate_mask and action_mask shapes must match exactly.")
        if actor.step_mask.shape != actor.action_mask.shape[:2]:
            raise ValueError("Q_H step_mask must match the actor batch/state axes.")
        if actor.history_mask.shape != (*actor.action_mask.shape[:2], actor.action_mask.shape[1]):
            raise ValueError("Q_H history_mask must have shape (B,S,S).")
        if bool((actor.action_mask & ~actor.candidate_mask).any()):
            raise ValueError("Q_H action_mask must imply candidate_mask.")
        if bool((actor.horizon_remaining < 0).any() or (actor.horizon_remaining > self.config.max_horizon).any()):
            raise ValueError(f"Q_H horizon_remaining must be in [0,{self.config.max_horizon}].")
        causal = torch.arange(actor.history_mask.shape[-1], device=actor.history_mask.device).view(1, 1, -1)
        state = torch.arange(actor.history_mask.shape[-2], device=actor.history_mask.device).view(1, -1, 1)
        if bool((actor.history_mask & causal.ge(state)).any()):
            raise ValueError("Q_H history_mask must be strictly causal.")
        context = actor.static_context
        if context is None:
            raise ValueError("TargetFiniteHorizonScorer qh_cf0_v1 requires compact root EVL context.")
        if actor.selected_observation_prefix is not None:
            raise ValueError("TargetFiniteHorizonScorer qh_cf0_v1 rejects privileged selected observations.")
        presence = context.evl_presence
        if presence.shape[-1] != 8 or not bool(presence.all()):
            raise ValueError("TargetFiniteHorizonScorer qh_cf0_v1 requires all eight root EVL fields.")


__all__ = ["TargetFiniteHorizonScorer", "TargetFiniteHorizonScorerConfig"]
