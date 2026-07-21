"""Finite-horizon candidate-value scorer for target-conditioned rollouts.

The scorer is deliberately objective-agnostic: it maps the actor-visible
:class:`aria_nbv.lightning.qh_data.QhActorInputs` to one finite scalar per
full-shell candidate. Hard action
masks, selected-transition supervision, and Double-Q targets remain owned by
:class:`aria_nbv.lightning.qh_module.QhLightningModule`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import torch
from jaxtyping import Float
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import TargetConfig

if TYPE_CHECKING:
    from ...lightning.qh_data import QhActorInputs


class MultiStepCandidateScorerConfig(TargetConfig["MultiStepCandidateScorer"]):
    """Configure the V0 candidate-to-state query scorer."""

    horizon: int = Field(default=2, ge=1)
    """Maximum selected-step horizon used to normalize remaining budget."""

    candidate_token_dim: int = Field(default=128, gt=0)
    """Shared candidate and state token width."""

    num_heads: int = Field(default=4, gt=0)
    """Cross-attention head count; must divide `candidate_token_dim`."""

    feedforward_multiplier: int = Field(default=2, gt=0)
    """Width multiplier for the candidate-local feed-forward block."""

    dropout: float = Field(default=0.0, ge=0.0, lt=1.0)
    """Dropout used in cross-attention and candidate-local feed-forward layers."""

    @model_validator(mode="after")
    def _validate_attention_width(self) -> Self:
        if self.candidate_token_dim % self.num_heads:
            raise ValueError("candidate_token_dim must be divisible by num_heads.")
        return self

    @property
    def target_type(self) -> type["MultiStepCandidateScorer"]:
        """Runtime scorer constructed by :meth:`setup_target`."""

        return MultiStepCandidateScorer


class MultiStepCandidateScorer(nn.Module):
    r"""Score each finite-shell candidate through shared state queries.

    Candidate tokens never attend other candidate tokens, so jointly permuting
    the candidate axis permutes the output axis without changing values. State
    tokens summarize actor-visible semidense evidence, the V0 target geometry,
    ordered selected-history poses, and remaining budget. Candidate row ids are
    audit keys and are never model features.

    Each candidate query attends only to shared scene, target, budget, and
    ordered-history tokens through PyTorch
    [multi-head attention](https://docs.pytorch.org/docs/stable/generated/torch.nn.MultiheadAttention.html).
    Consequently, for any candidate permutation matrix $P$,
    $f(PX, s)=P f(X, s)$: the scorer is permutation-equivariant on the
    candidate axis. It is not permutation-invariant on selected history,
    whose order encodes rollout time.
    """

    _CANDIDATE_DIM = 26
    _TARGET_DIM = 30
    _SCENE_DIM = 19
    _HISTORY_DIM = 26

    def __init__(self, config: MultiStepCandidateScorerConfig) -> None:
        super().__init__()
        self.config = config
        width = config.candidate_token_dim
        self.candidate_encoder = _mlp(self._CANDIDATE_DIM, width, width)
        self.target_encoder = _mlp(self._TARGET_DIM, width, width)
        self.scene_encoder = _mlp(self._SCENE_DIM, width, width)
        self.budget_encoder = _mlp(1, width, width)
        self.history_encoder = _mlp(self._HISTORY_DIM, width, width)
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=width,
            num_heads=config.num_heads,
            dropout=config.dropout,
            batch_first=True,
        )
        hidden = width * config.feedforward_multiplier
        self.candidate_ffn = nn.Sequential(
            nn.LayerNorm(width),
            nn.Linear(width, hidden),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(hidden, width),
        )
        self.output_norm = nn.LayerNorm(width)
        self.value_head = nn.Linear(width, 1)

    def forward(self, actor: "QhActorInputs") -> Float[Tensor, "B N"]:
        """Return finite candidate values aligned to the padded shell.

        Args:
            actor: Batched actor-only Q_H inputs. Candidate and history tensors
                use right-padded axes; masks remain caller-owned.

        Returns:
            ``Tensor["B N_q", float32]`` finite values for every shell row. The
            caller must apply `actor.actor_action_mask` before selection.
        """

        _validate_actor_shapes(actor)
        candidate_features = torch.cat(
            (
                actor.candidate_pose_world_cam.float(),
                actor.candidate_pose_relative_root.float(),
                _periodic_id(actor.candidate_position_id),
            ),
            dim=-1,
        )
        queries = self.candidate_encoder(torch.nan_to_num(candidate_features))

        target_features = torch.cat(
            (
                actor.target_center_world.float(),
                actor.target_extents.float(),
                actor.target_pose_world_object.float(),
                actor.target_relative_pose_reference_object.float(),
            ),
            dim=-1,
        )
        scene_features = _scene_features(actor)
        budget = actor.remaining_budget.float().unsqueeze(-1) / float(self.config.horizon)
        fixed_tokens = torch.stack(
            (
                self.scene_encoder(scene_features),
                self.target_encoder(torch.nan_to_num(target_features)),
                self.budget_encoder(budget),
            ),
            dim=1,
        )

        history_features = torch.cat(
            (
                actor.history_pose_world_cam.float(),
                actor.history_pose_relative_root.float(),
                _periodic_id(actor.history_position_id),
            ),
            dim=-1,
        )
        history_tokens = self.history_encoder(torch.nan_to_num(history_features))
        state_tokens = torch.cat((fixed_tokens, history_tokens), dim=1)
        fixed_mask = torch.zeros(
            (actor.history_mask.shape[0], 3),
            dtype=torch.bool,
            device=actor.history_mask.device,
        )
        state_padding_mask = torch.cat((fixed_mask, ~actor.history_mask.bool()), dim=1)

        attended, _ = self.cross_attention(
            query=queries,
            key=state_tokens,
            value=state_tokens,
            key_padding_mask=state_padding_mask,
            need_weights=False,
        )
        tokens = queries + attended
        tokens = tokens + self.candidate_ffn(tokens)
        return torch.nan_to_num(self.value_head(self.output_norm(tokens)).squeeze(-1))


def _mlp(input_dim: int, hidden_dim: int, output_dim: int) -> nn.Sequential:
    return nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, output_dim))


def _periodic_id(values: Tensor) -> Tensor:
    values = values.float().unsqueeze(-1)
    return torch.cat((torch.sin(values), torch.cos(values)), dim=-1)


def _scene_features(actor: "QhActorInputs") -> Tensor:
    blocks = dict(actor.vin_blocks)
    missing = {"vin.points_world", "vin.lengths", "vin.t_world_rig"} - set(blocks)
    if missing:
        raise ValueError(f"Q_H scorer requires actor VIN blocks {sorted(missing)}.")
    points = blocks["vin.points_world"].float()
    batch_size, max_points = points.shape[:2]
    lengths = blocks["vin.lengths"].reshape(batch_size, -1)[:, 0].long().clamp(min=0, max=max_points)
    rigs = blocks["vin.t_world_rig"].float()
    point_rows = torch.arange(max_points, device=points.device).unsqueeze(0)
    point_mask = point_rows.lt(lengths.unsqueeze(1)) & torch.isfinite(points[..., :3]).all(dim=-1)
    point_count = point_mask.sum(dim=1, keepdim=True).clamp_min(1)
    xyz = torch.nan_to_num(points[..., :3])
    mean = (xyz * point_mask.unsqueeze(-1)).sum(dim=1) / point_count
    variance = (((xyz - mean.unsqueeze(1)) ** 2) * point_mask.unsqueeze(-1)).sum(dim=1) / point_count

    rig_valid = torch.isfinite(rigs).all(dim=-1) & rigs.abs().sum(dim=-1).gt(0)
    rig_rows = torch.arange(rigs.shape[1], device=rigs.device).expand(batch_size, -1)
    last_rig_index = rig_rows.masked_fill(~rig_valid, -1).max(dim=1).values
    last_rig = rigs[torch.arange(batch_size, device=rigs.device), last_rig_index.clamp_min(0)]
    last_rig = torch.where(last_rig_index.unsqueeze(-1).ge(0), last_rig, torch.zeros_like(last_rig))

    return torch.cat(
        (
            mean,
            variance.sqrt(),
            torch.log1p(lengths.float()).unsqueeze(-1),
            torch.nan_to_num(last_rig),
        ),
        dim=-1,
    )


def _validate_actor_shapes(actor: "QhActorInputs") -> None:
    if actor.candidate_pose_world_cam.ndim != 3 or actor.candidate_pose_world_cam.shape[-1] != 12:
        raise ValueError("candidate_pose_world_cam must have shape [B, N, 12].")
    if actor.candidate_pose_relative_root.shape != actor.candidate_pose_world_cam.shape:
        raise ValueError("Current candidate pose tensors must have identical [B, N, 12] shape.")
    if actor.actor_action_mask.shape != actor.candidate_pose_world_cam.shape[:2]:
        raise ValueError("actor_action_mask must align to the [B, N] candidate shell.")
    if actor.history_pose_world_cam.ndim != 3 or actor.history_pose_world_cam.shape[-1] != 12:
        raise ValueError("history_pose_world_cam must have shape [B, H, 12].")
    if actor.history_mask.shape != actor.history_pose_world_cam.shape[:2]:
        raise ValueError("history_mask must align to the [B, H] history axis.")


__all__ = ["MultiStepCandidateScorer", "MultiStepCandidateScorerConfig"]
