"""Actor-only finite-horizon scorer for persisted Q_H chain views."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class QhScoreOutput:
    """Candidate-aligned predictions before policy masking.

    Attributes:
        conditional_q: ``Tensor["B S N", float32]`` values conditional on an
            action being feasible. Materialized invalid rows are deliberately
            finite but are neither Q-supervised nor deployable.
        feasibility_logits: ``Tensor["B S N", float32]`` binary-validity
            logits. Positive values denote greater predicted feasibility.
    """

    conditional_q: Tensor
    feasibility_logits: Tensor


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
    """Predict candidate feasibility and conditional finite-horizon value.

    The module exposes one deep interface: a batched
    :class:`~aria_nbv.data_handling.qh_data.QhActorTensors` enters and one
    candidate-aligned :class:`QhScoreOutput` leaves. Every materialized row is
    encoded independently of ``action_mask``. Candidate rows never attend to
    one another, so jointly permuting candidate poses and masks permutes both
    outputs identically and invalid rows cannot influence valid rows.
    """

    def __init__(self, config: TargetFiniteHorizonScorerConfig) -> None:
        super().__init__()
        self.config = config
        self.pose_encoder: R6dLffPoseEncoder = config.pose_encoder.setup_target()
        pose_dim = self.pose_encoder.out_dim
        hidden_dim = int(config.hidden_dim)
        scene_dim = 4 * len(config.scene_channels) + 8

        self.physical_projection = nn.Sequential(
            nn.Linear(2 * pose_dim + scene_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.feasibility_head = nn.Linear(hidden_dim, 1)
        self.value_query_projection = nn.Sequential(
            nn.Linear(hidden_dim + pose_dim, hidden_dim),
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
        self.horizon_projection = nn.Sequential(
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

    def forward(
        self,
        actor: QhActorTensors,
        *,
        requested_horizon: Tensor | None = None,
    ) -> QhScoreOutput:
        """Return mask-independent candidate predictions in stored order.

        Args:
            actor: Batched actor-visible chain with candidate support
                ``Tensor["B S N", bool]`` and compact root EVL evidence.
            requested_horizon: Optional ``Tensor["B S", int64]`` value query.
                ``None`` means :attr:`QhActorTensors.horizon_remaining`.

        Returns:
            Candidate-aligned conditional Q and feasibility logits. Both are
            finite on materialized realized rows and zero only on padding.
        """

        self._validate_actor(actor)
        horizon = self._validated_requested_horizon(actor, requested_horizon)
        candidate_mask = actor.candidate_mask & actor.step_mask.unsqueeze(-1)
        batch_size, steps, width = candidate_mask.shape

        candidate_pose = self._sanitize_pose(
            actor.candidate_pose_relative_root,
            candidate_mask,
            name="candidate",
        )
        history_mask = actor.history_mask & actor.step_mask.unsqueeze(-1)
        history_pose = self._sanitize_pose(actor.history_pose_relative_root, history_mask, name="history")
        target_active = actor.step_mask.any(dim=-1)
        target_pose = self._sanitize_pose(actor.target_pose_relative_root, target_active, name="target")
        if bool((target_active.unsqueeze(-1) & ~torch.isfinite(actor.target_extents)).any()):
            raise ValueError("Q_H active target extents must be finite.")

        current_pose = self._current_pose_relative_root(actor, history_pose)
        root_candidate_features = self.pose_encoder.encode(candidate_pose).pose_enc
        current_from_candidate = self._expand_pose(current_pose.inverse(), width) @ candidate_pose
        current_candidate_features = self.pose_encoder.encode(current_from_candidate).pose_enc
        scene_summary = self._scene_summary(actor)
        candidate_scene = scene_summary[:, None, None, :].expand(-1, steps, width, -1)
        physical_tokens = self.physical_projection(
            torch.cat((root_candidate_features, current_candidate_features, candidate_scene), dim=-1)
        )
        physical_tokens = torch.where(
            candidate_mask.unsqueeze(-1),
            physical_tokens,
            torch.zeros_like(physical_tokens),
        )
        feasibility_logits = self.feasibility_head(physical_tokens).squeeze(-1)

        target_features = self.pose_encoder.encode(target_pose).pose_enc
        target_token = self.target_projection(torch.cat((target_features, actor.target_extents.float()), dim=-1))

        current_from_history = self._expand_pose(current_pose.inverse(), steps) @ history_pose
        history_features = self.pose_encoder.encode(current_from_history).pose_enc
        history_sum = torch.where(history_mask.unsqueeze(-1), history_features, torch.zeros_like(history_features)).sum(
            dim=-2
        )
        history_count = history_mask.sum(dim=-1, keepdim=True).clamp_min(1)
        history_token = self.history_projection(history_sum / history_count)

        budget = actor.horizon_remaining.float().unsqueeze(-1) / float(self.config.max_horizon)
        budget_token = self.budget_projection(budget)
        horizon_token = self.horizon_projection(horizon.float().unsqueeze(-1) / float(self.config.max_horizon))
        scene_token = self.scene_projection(scene_summary).unsqueeze(1).expand(-1, steps, -1)
        target_token = target_token.unsqueeze(1).expand(-1, steps, -1)

        target_by_candidate = self._expand_pose(target_pose, steps, width)
        candidate_from_target = candidate_pose.inverse() @ target_by_candidate
        candidate_target_features = self.pose_encoder.encode(candidate_from_target).pose_enc
        value_queries = self.value_query_projection(torch.cat((physical_tokens, candidate_target_features), dim=-1))
        value_queries = torch.where(candidate_mask.unsqueeze(-1), value_queries, torch.zeros_like(value_queries))

        state_tokens = torch.stack((scene_token, target_token, history_token, budget_token, horizon_token), dim=-2)
        flat_candidates = value_queries.reshape(batch_size * steps, width, -1)
        flat_state = state_tokens.reshape(batch_size * steps, state_tokens.shape[-2], -1)
        attended, _weights = self.state_attention(
            flat_candidates,
            flat_state,
            flat_state,
            need_weights=False,
        )
        attended = attended.reshape(batch_size, steps, width, -1)
        conditional_q = self.value_head(torch.cat((value_queries, attended, value_queries * attended), dim=-1)).squeeze(
            -1
        )
        conditional_q = torch.where(candidate_mask, conditional_q, torch.zeros_like(conditional_q))
        feasibility_logits = torch.where(candidate_mask, feasibility_logits, torch.zeros_like(feasibility_logits))
        if not bool(torch.isfinite(conditional_q[candidate_mask]).all()):
            raise ValueError("TargetFiniteHorizonScorer produced nonfinite conditional Q on materialized rows.")
        if not bool(torch.isfinite(feasibility_logits[candidate_mask]).all()):
            raise ValueError("TargetFiniteHorizonScorer produced nonfinite feasibility logits on materialized rows.")
        return QhScoreOutput(
            conditional_q=conditional_q.float(),
            feasibility_logits=feasibility_logits.float(),
        )

    def _validated_requested_horizon(
        self,
        actor: QhActorTensors,
        requested_horizon: Tensor | None,
    ) -> Tensor:
        """Return the scalar per-state query after fail-closed validation."""

        horizon = actor.horizon_remaining if requested_horizon is None else requested_horizon
        expected = actor.step_mask.shape
        if horizon.shape != expected:
            raise ValueError(f"Q_H requested_horizon must have shape {tuple(expected)}, got {tuple(horizon.shape)}.")
        if horizon.dtype is not torch.int64:
            raise ValueError("Q_H requested_horizon must use int64 dtype.")
        if horizon.device != actor.step_mask.device:
            raise ValueError("Q_H requested_horizon must be on the actor device.")
        realized = actor.step_mask
        invalid_realized = realized & (horizon.lt(1) | horizon.gt(actor.horizon_remaining))
        if bool(invalid_realized.any()):
            raise ValueError("Q_H realized requested horizons must satisfy 1 <= h <= horizon_remaining.")
        if bool((realized & horizon.gt(self.config.max_horizon)).any()):
            raise ValueError(f"Q_H requested_horizon exceeds configured H_max={self.config.max_horizon}.")
        if bool((~realized & horizon.ne(0)).any()):
            raise ValueError("Q_H padded requested horizons must be zero.")
        return horizon

    def _current_pose_relative_root(self, actor: QhActorTensors, history_pose: PoseTW) -> PoseTW:
        """Return root-from-current-camera for every realized state."""

        batch_size, steps = actor.step_mask.shape
        history_index = torch.arange(steps, device=actor.step_mask.device).sub(1).clamp_min(0)
        gather_index = history_index.view(1, steps, 1, 1).expand(batch_size, -1, 1, 12)
        gathered = history_pose.tensor().gather(-2, gather_index).squeeze(-2)
        predecessor_present = actor.history_mask.gather(
            -1,
            history_index.view(1, steps, 1).expand(batch_size, -1, 1),
        ).squeeze(-1)
        requires_predecessor = actor.step_mask & torch.arange(steps, device=actor.step_mask.device).gt(0)
        if bool((requires_predecessor & ~predecessor_present).any()):
            raise ValueError("Q_H every realized non-root state requires its immediate predecessor pose in history.")
        identity = PoseTW().tensor().to(device=gathered.device, dtype=gathered.dtype).expand_as(gathered)
        use_history = requires_predecessor & predecessor_present
        return PoseTW(torch.where(use_history.unsqueeze(-1), gathered, identity))

    @staticmethod
    def _expand_pose(pose: PoseTW, *sizes: int) -> PoseTW:
        """Insert and expand pose axes without copying pose storage."""

        values = pose.tensor()
        for _ in sizes:
            values = values.unsqueeze(-2)
        return PoseTW(values.expand(*values.shape[: -len(sizes) - 1], *sizes, 12))

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
        if actor.candidate_mask.dtype is not torch.bool or actor.action_mask.dtype is not torch.bool:
            raise ValueError("Q_H candidate_mask and action_mask must use bool dtype.")
        if actor.step_mask.shape != actor.action_mask.shape[:2]:
            raise ValueError("Q_H step_mask must match the actor batch/state axes.")
        if actor.step_mask.dtype is not torch.bool:
            raise ValueError("Q_H step_mask must use bool dtype.")
        if actor.history_mask.shape != (*actor.action_mask.shape[:2], actor.action_mask.shape[1]):
            raise ValueError("Q_H history_mask must have shape (B,S,S).")
        if bool((actor.action_mask & ~actor.candidate_mask).any()):
            raise ValueError("Q_H action_mask must imply candidate_mask.")
        if bool((actor.candidate_mask & ~actor.step_mask.unsqueeze(-1)).any()):
            raise ValueError("Q_H padded states cannot contain materialized candidate rows.")
        if actor.horizon_remaining.shape != actor.step_mask.shape or actor.horizon_remaining.dtype is not torch.int64:
            raise ValueError("Q_H horizon_remaining must be int64 with shape (B,S).")
        realized = actor.step_mask
        invalid_budget = (realized & actor.horizon_remaining.lt(1)) | (~realized & actor.horizon_remaining.ne(0))
        if bool(invalid_budget.any() or actor.horizon_remaining.gt(self.config.max_horizon).any()):
            raise ValueError(
                f"Q_H realized horizon_remaining must be in [1,{self.config.max_horizon}] and padding must be zero."
            )
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


__all__ = ["QhScoreOutput", "TargetFiniteHorizonScorer", "TargetFiniteHorizonScorerConfig"]
