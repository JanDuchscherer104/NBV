"""Gauge-invariant V0 scorer for target-conditioned finite-horizon rollouts.

The scorer maps :class:`aria_nbv.data_handling.qh.QhActorInputs` to one value
per finite-shell candidate without learning the arbitrary world gauge.
Semidense world points and the admitted world-from-object target pose are
converted with the explicit persisted world-from-rollout-root pose. The target
pose translation is the sole learned target-center authority. Candidate and
history poses already persisted relative to that rollout root remain in the
same frame. For each candidate, the target center is additionally expressed in
the candidate camera frame, where metres, range, and the repository-owned
shell-descriptor forward direction provide the minimal direct target relation.

The current admitted horizon is two, so selected history is intentionally a
set-valued summary without temporal positions. Candidate row ids, target
semantic/instance ids, storage lineage, hard action masks, and
selected-transition supervision are never learned features. Actor-input and
mask ownership belongs to :mod:`aria_nbv.data_handling.qh`; Double-Q target
construction and optimization belong to
:class:`aria_nbv.lightning.qh_module.QhLightningModule`.

See the [EFM3D ``PoseTW`` implementation](https://github.com/facebookresearch/efm3d/blob/main/efm3d/aria/pose.py)
for the ``T_target_source`` transform convention and
[Double DQN](https://arxiv.org/abs/1509.06461) for the separate action-selection
and evaluation objective.

This module provides the V0 scorer and its strict config factory. It owns only
actor-visible feature construction and permutation-equivariant candidate
scoring; storage joins, padding masks, and fitted-Q optimization remain at
their dedicated seams.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import torch
from efm3d.aria.pose import PoseTW
from jaxtyping import Float
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import TargetConfig
from ..encoders.shell_descriptor import encode_shell_pose_descriptor

if TYPE_CHECKING:
    from ...data_handling.qh import QhActorInputs


class MultiStepCandidateScorerConfig(TargetConfig["MultiStepCandidateScorer"]):
    """Configure the V0 candidate-to-state query scorer."""

    horizon: int = Field(default=2, ge=2, le=2)
    """Fixed two-step V0 horizon used to normalize remaining budget."""

    candidate_token_dim: int = Field(default=128, gt=0)
    """Shared candidate and state token width."""

    num_heads: int = Field(default=4, gt=0)
    """Cross-attention head count; must divide `candidate_token_dim`."""

    feedforward_multiplier: int = Field(default=2, gt=0)
    """Width multiplier for the candidate-local feed-forward block."""

    dropout: float = Field(default=0.0, ge=0.0, le=0.0)
    """Fixed-zero dropout required for deterministic fitted-Q action selection."""

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
    r"""Score each finite-shell candidate through shared local-frame queries.

    Candidate tokens never attend other candidate tokens, so jointly permuting
    the candidate axis permutes the output axis without changing values. State
    tokens summarize rollout-reference-frame semidense evidence, V0 target geometry,
    set-valued selected-history poses, and remaining budget. Candidate row ids
    and target semantic/instance ids are audit keys and are never model
    features.

    Each candidate query attends only to shared scene, target, budget, and
    history-set tokens through PyTorch
    [multi-head attention](https://docs.pytorch.org/docs/stable/generated/torch.nn.MultiheadAttention.html).
    Consequently, for any candidate permutation matrix $P$,
    $f(PX, s)=P f(X, s)$: the scorer is permutation-equivariant on the
    candidate axis. With no temporal position feature, it is invariant to a
    joint permutation of the valid history rows. Temporal encoding is deferred
    until an admitted horizon of at least three makes order observable.

    Theory:
        ``candidate_pose_relative_root`` is $T_{root\leftarrow cam}$. The
        target center from $T_{root\leftarrow object}$ is transformed as
        $p_{cam}=T_{cam\leftarrow root}p_{root}$ to produce
        ``target_center_candidate_m`` ``Tensor["B N 3", float32]``. Its norm
        is ``target_range_m`` ``Tensor["B N 1", float32]`` and its cosine with
        the Aria/EFM camera optical axis ``+Z`` is
        ``target_optical_axis_cos`` ``Tensor["B N 1", float32]`` in
        ``[-1, 1]``. All translations and point coordinates are metres.
    """

    _POSITION_FAMILY_COUNT = 6
    _POSITION_FAMILY_DIM = 8
    _POSITION_PADDING_INDEX = _POSITION_FAMILY_COUNT
    _CANDIDATE_DIM = 12 + _POSITION_FAMILY_DIM + 3 + 1 + 1
    _TARGET_DIM = 3 + 12
    _SCENE_DIM = 7
    _HISTORY_DIM = 12 + _POSITION_FAMILY_DIM

    def __init__(self, config: MultiStepCandidateScorerConfig) -> None:
        super().__init__()
        self.config = config
        width = config.candidate_token_dim
        self.position_family_embedding = nn.Embedding(
            self._POSITION_FAMILY_COUNT + 1,
            self._POSITION_FAMILY_DIM,
            padding_idx=self._POSITION_PADDING_INDEX,
        )
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

        _validate_actor(actor, position_family_count=self._POSITION_FAMILY_COUNT)
        candidate_mask = actor.actor_action_mask.bool()
        candidate_local = _masked_rows(actor.candidate_pose_relative_root.float(), candidate_mask)
        target_pose_relative_root = (
            PoseTW(actor.root_pose_world.float()).inverse() @ PoseTW(actor.target_pose_world_object.float())
        ).tensor()
        target_center_candidate_m, target_range_m, target_optical_axis_cos = _candidate_target_relations(
            candidate_local,
            target_pose_relative_root,
            candidate_mask,
        )
        candidate_features = torch.cat(
            (
                candidate_local,
                self.position_family_embedding(
                    _position_family_indices(
                        actor.candidate_position_id,
                        candidate_mask,
                        family_count=self._POSITION_FAMILY_COUNT,
                        padding_index=self._POSITION_PADDING_INDEX,
                    )
                ),
                target_center_candidate_m,
                target_range_m,
                target_optical_axis_cos,
            ),
            dim=-1,
        )
        queries = self.candidate_encoder(candidate_features)

        target_features = torch.cat(
            (
                actor.target_extents.float(),
                target_pose_relative_root,
            ),
            dim=-1,
        )
        scene_features = _scene_features(actor)
        budget = actor.remaining_budget.float().unsqueeze(-1) / float(self.config.horizon)
        fixed_tokens = torch.stack(
            (
                self.scene_encoder(scene_features),
                self.target_encoder(target_features),
                self.budget_encoder(budget),
            ),
            dim=1,
        )

        history_mask = actor.history_mask.bool()
        history_features = torch.cat(
            (
                _masked_rows(actor.history_pose_relative_root.float(), history_mask),
                self.position_family_embedding(
                    _position_family_indices(
                        actor.history_position_id,
                        history_mask,
                        family_count=self._POSITION_FAMILY_COUNT,
                        padding_index=self._POSITION_PADDING_INDEX,
                    )
                ),
            ),
            dim=-1,
        )
        history_tokens = self.history_encoder(history_features)
        state_tokens = torch.cat((fixed_tokens, history_tokens), dim=1)
        fixed_mask = torch.zeros(
            (actor.history_mask.shape[0], 3),
            dtype=torch.bool,
            device=actor.history_mask.device,
        )
        state_padding_mask = torch.cat((fixed_mask, ~history_mask), dim=1)

        attended, _ = self.cross_attention(
            query=queries,
            key=state_tokens,
            value=state_tokens,
            key_padding_mask=state_padding_mask,
            need_weights=False,
        )
        tokens = queries + attended
        tokens = tokens + self.candidate_ffn(tokens)
        values = self.value_head(self.output_norm(tokens)).squeeze(-1)
        if not torch.isfinite(values).all():
            raise ValueError("Q_H scorer produced non-finite candidate values.")
        return values


def _mlp(input_dim: int, hidden_dim: int, output_dim: int) -> nn.Sequential:
    return nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, output_dim))


def _scene_features(actor: "QhActorInputs") -> Tensor:
    r"""Summarize semidense evidence in the persisted rollout-reference frame.

    The persisted ``root_pose_world`` is $T_{world\leftarrow root}$. Its inverse
    maps world points into the same rollout-root frame as every persisted
    ``*_relative_root`` pose; VIN rig timestamps and Oracle reference poses do
    not define this learned frame.
    """

    points = actor.vin_snippet.points_world.float()
    batch_size, max_points = points.shape[:2]
    lengths = actor.vin_snippet.lengths.reshape(batch_size, -1)[:, 0].long().clamp(min=0, max=max_points)
    point_rows = torch.arange(max_points, device=points.device).unsqueeze(0)
    point_mask = point_rows.lt(lengths.unsqueeze(1))
    point_count = point_mask.sum(dim=1, keepdim=True).clamp_min(1)
    xyz_world = torch.where(point_mask.unsqueeze(-1), points[..., :3], torch.zeros_like(points[..., :3]))

    xyz_root = PoseTW(actor.root_pose_world.float()).inverse().transform(xyz_world)
    mean = (xyz_root * point_mask.unsqueeze(-1)).sum(dim=1) / point_count
    variance = (((xyz_root - mean.unsqueeze(1)) ** 2) * point_mask.unsqueeze(-1)).sum(dim=1) / point_count

    return torch.cat(
        (
            mean,
            variance.sqrt(),
            torch.log1p(lengths.float()).unsqueeze(-1),
        ),
        dim=-1,
    )


def _validate_actor(actor: "QhActorInputs", *, position_family_count: int) -> None:
    """Fail closed on malformed shapes and every valid learned feature."""

    if actor.candidate_pose_relative_root.ndim != 3 or actor.candidate_pose_relative_root.shape[-1] != 12:
        raise ValueError("candidate_pose_relative_root must have shape [B, N, 12].")
    if actor.actor_action_mask.shape != actor.candidate_pose_relative_root.shape[:2]:
        raise ValueError("actor_action_mask must align to the [B, N] candidate shell.")
    if actor.history_pose_relative_root.ndim != 3 or actor.history_pose_relative_root.shape[-1] != 12:
        raise ValueError("history_pose_relative_root must have shape [B, H, 12].")
    if actor.history_mask.shape != actor.history_pose_relative_root.shape[:2]:
        raise ValueError("history_mask must align to the [B, H] history axis.")
    batch_size = actor.candidate_pose_relative_root.shape[0]
    expected_target_shapes = {
        "root_pose_world": (batch_size, 12),
        "target_extents": (batch_size, 3),
        "target_pose_world_object": (batch_size, 12),
    }
    for name, shape in expected_target_shapes.items():
        if getattr(actor, name).shape != shape:
            raise ValueError(f"{name} must have shape {shape}.")
    candidate_mask = actor.actor_action_mask.bool()
    history_mask = actor.history_mask.bool()
    for name, value, mask in (
        ("candidate_pose_relative_root", actor.candidate_pose_relative_root, candidate_mask),
        ("history_pose_relative_root", actor.history_pose_relative_root, history_mask),
    ):
        if not torch.isfinite(value[mask]).all():
            raise ValueError(f"Q_H valid {name} rows must be finite.")
    for name, value in (
        ("root_pose_world", actor.root_pose_world),
        ("target_extents", actor.target_extents),
        ("target_pose_world_object", actor.target_pose_world_object),
    ):
        if not torch.isfinite(value).all():
            raise ValueError(f"Q_H {name} must be finite.")
    points = actor.vin_snippet.points_world
    if points.ndim != 3 or points.shape[-1] < 3:
        raise ValueError("vin_snippet.points_world must have shape [B, P, 3+C].")
    lengths = actor.vin_snippet.lengths.reshape(points.shape[0], -1)[:, 0].long()
    if lengths.lt(0).any() or lengths.gt(points.shape[1]).any():
        raise ValueError("vin_snippet.lengths must stay within the padded point axis.")
    point_mask = torch.arange(points.shape[1], device=points.device).unsqueeze(0).lt(lengths.unsqueeze(1))
    if not torch.isfinite(points[..., :3][point_mask]).all():
        raise ValueError("Q_H valid semidense point coordinates must be finite.")
    _validate_position_ids(
        actor.candidate_position_id,
        candidate_mask,
        family_count=position_family_count,
        name="candidate_position_id",
    )
    _validate_position_ids(
        actor.history_position_id,
        history_mask,
        family_count=position_family_count,
        name="history_position_id",
    )


def _candidate_target_relations(
    candidate_pose_relative_root: Tensor,
    target_pose_relative_root: Tensor,
    candidate_mask: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    """Return candidate-frame target center, range, and ``+Z`` alignment.

    Args:
        candidate_pose_relative_root: ``Float[B,N,12]`` root-from-camera
            transforms ``T_root_cam`` with translations in metres.
        target_pose_relative_root: ``Float[B,12]`` root-from-object transform
            ``T_root_object``; its translation is the target center in metres.
        candidate_mask: ``Bool[B,N]`` true exactly for actor-valid candidates.

    Returns:
        Candidate-frame target centers ``Float[B,N,3]`` in metres, ranges
        ``Float[B,N,1]`` in metres, and camera ``+Z`` optical-axis cosines
        ``Float[B,N,1]`` in ``[-1,1]``. Masked rows are zero padding.
    """

    candidate_pose_root = PoseTW(candidate_pose_relative_root)
    candidate_count = candidate_pose_relative_root.shape[1]
    target_center_root = PoseTW(target_pose_relative_root).t.unsqueeze(1).expand(-1, candidate_count, -1)
    target_center_candidate_m = candidate_pose_root.inverse().transform(target_center_root.unsqueeze(-2)).squeeze(-2)
    target_range_m = torch.linalg.vector_norm(target_center_candidate_m, dim=-1, keepdim=True)
    candidate_forward_root = encode_shell_pose_descriptor(candidate_pose_root).forward_dir
    target_direction_root = target_center_root - candidate_pose_root.t
    target_optical_axis_cos = (candidate_forward_root * target_direction_root).sum(
        dim=-1, keepdim=True
    ) / target_range_m.clamp_min(1e-8)
    target_optical_axis_cos = target_optical_axis_cos.clamp(-1.0, 1.0)
    mask = candidate_mask.unsqueeze(-1)
    return (
        torch.where(mask, target_center_candidate_m, torch.zeros_like(target_center_candidate_m)),
        torch.where(mask, target_range_m, torch.zeros_like(target_range_m)),
        torch.where(mask, target_optical_axis_cos, torch.zeros_like(target_optical_axis_cos)),
    )


def _masked_rows(values: Tensor, mask: Tensor) -> Tensor:
    return torch.where(mask.unsqueeze(-1), values, torch.zeros_like(values))


def _validate_position_ids(values: Tensor, mask: Tensor, *, family_count: int, name: str) -> None:
    if values.shape != mask.shape:
        raise ValueError(f"{name} must align to mask shape {tuple(mask.shape)}.")
    valid = values[mask]
    if valid.numel() and (valid.lt(0).any() or valid.ge(family_count).any()):
        raise ValueError(f"Q_H valid {name} values must lie in [0, {family_count - 1}].")


def _position_family_indices(
    values: Tensor,
    mask: Tensor,
    *,
    family_count: int,
    padding_index: int,
) -> Tensor:
    _validate_position_ids(values, mask, family_count=family_count, name="position_family_id")
    return torch.where(mask, values.long(), torch.full_like(values.long(), padding_index))


__all__ = ["MultiStepCandidateScorer", "MultiStepCandidateScorerConfig"]
