"""A compact symmetry-aware transformer over historical EFM field tokens."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

import torch
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import TargetConfig
from ..ordinal import CoralLayer, coral_loss
from ..types.temporal_field import TemporalFieldBatch

if TYPE_CHECKING:
    from ...data_handling.offline.batch import VinOracleBatch
    from ...learning.grouped_rollouts import GroupedRolloutTrainingBatch


class TemporalFieldTransformerConfig(TargetConfig["TemporalFieldTransformer"]):
    """Configure the pure-PyTorch temporal field baseline."""

    @property
    def target_type(self) -> type["TemporalFieldTransformer"]:
        """Factory target for the transformer."""

        return TemporalFieldTransformer

    field_feature_dim: int = Field(gt=0)
    target_feature_dim: int = Field(default=4, gt=0)
    d_model: int = Field(default=128, gt=0)
    num_heads: int = Field(default=4, gt=0)
    num_layers: int = Field(default=2, gt=0)
    num_classes: int = Field(default=15, ge=2)
    dropout: float = Field(default=0.0, ge=0.0, lt=1.0)

    @classmethod
    def from_manifest(cls, oracle: Mapping[str, Any], **overrides: Any) -> "TemporalFieldTransformerConfig":
        """Build a dimension-safe model config from an offline-store manifest."""

        feature_dim = oracle.get("backbone_history_feature_dim")
        if not isinstance(feature_dim, int) or feature_dim < 1:
            raise ValueError("manifest has no positive backbone_history_feature_dim")
        return cls(field_feature_dim=feature_dim, **overrides)

    @model_validator(mode="after")
    def _validate_heads(self) -> "TemporalFieldTransformerConfig":
        """Require an exact multi-head partition."""

        if self.d_model % self.num_heads:
            raise ValueError("d_model must be divisible by num_heads")
        return self


def _relative_pose(reference: Tensor, pose: Tensor) -> Tensor:
    """Express ``pose`` as translation and rotation in ``reference`` frames."""

    reference_rotation_inv = reference[..., :3].transpose(-1, -2)
    delta = pose[..., 3] - reference[..., 3]
    translation = torch.einsum("...ij,...j->...i", reference_rotation_inv, delta)
    rotation = torch.einsum("...ij,...jk->...ik", reference_rotation_inv, pose[..., :3])
    return torch.cat((translation, rotation.flatten(start_dim=-2)), dim=-1)


class TemporalFieldTransformer(nn.Module):
    r"""Predict ordinal RRI for independent target-candidate queries.

    Every pair receives its own query and historical field-token sequence. The
    pair query contains target-to-candidate geometry; each field token contains
    both target-relative and candidate-relative geometry plus causal age. No
    pair attends to another pair, so target/candidate permutations and subsets
    only permute or select outputs. Relative geometry also makes predictions
    invariant to a shared global SE(3) frame change.

    ``num_layers`` repeats one shared refinement block rather than allocating
    distinct blocks, keeping iterative temporal reasoning weight tied.
    """

    _POSE_DIM = 12
    _FIELD_GEOMETRY_DIM = 2 * _POSE_DIM + 1

    def __init__(self, config: TemporalFieldTransformerConfig) -> None:
        """Build compact field/query projections, one refiner, and a CORAL head."""

        super().__init__()
        self.config = config
        self.field_projection = nn.Linear(
            config.field_feature_dim + self._FIELD_GEOMETRY_DIM,
            config.d_model,
        )
        self.query_projection = nn.Linear(self._POSE_DIM + config.target_feature_dim, config.d_model)
        self.query_token = nn.Parameter(torch.zeros(1, 1, config.d_model))
        self.refiner = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.num_heads,
            dim_feedforward=2 * config.d_model,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.norm = nn.LayerNorm(config.d_model)
        self.head_coral = CoralLayer(config.d_model, config.num_classes)

    @staticmethod
    def _validate_poses(name: str, poses: Tensor, *, batch: int) -> None:
        if poses.ndim != 4 or poses.shape[0] != batch or poses.shape[-2:] != (3, 4):
            raise ValueError(f"{name} must have shape [B,N,3,4]")

    @staticmethod
    def _query_times(fields: TemporalFieldBatch, candidates: int, query_time_s: Tensor | None) -> Tensor:
        """Normalize candidate query times without depending on timestamp origin."""

        batch = fields.features.shape[0]
        if query_time_s is None:
            latest = fields.time_s.masked_fill(~fields.valid, -torch.inf).amax(dim=1, keepdim=True)
            latest = torch.where(torch.isfinite(latest), latest, torch.zeros_like(latest))
            return latest.expand(-1, candidates)
        if query_time_s.shape == (batch,):
            return query_time_s[:, None].expand(-1, candidates)
        if query_time_s.shape != (batch, candidates):
            raise ValueError("query_time_s must have shape [B] or [B,C]")
        return query_time_s

    def _pair_inputs(
        self,
        fields: TemporalFieldBatch,
        targets: Tensor,
        candidates: Tensor,
        target_features: Tensor,
        query_time_s: Tensor | None,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Return pair queries, field-token inputs, and a causal field mask."""

        batch, target_count = targets.shape[:2]
        candidate_count = candidates.shape[1]
        field_count = fields.features.shape[1]
        if target_features.shape != (batch, target_count, self.config.target_feature_dim):
            raise ValueError(
                f"target_features must have shape [B,T,{self.config.target_feature_dim}]",
            )
        times = self._query_times(fields, candidate_count, query_time_s)
        causal_valid = fields.valid[:, None] & (fields.time_s[:, None] <= times[:, :, None])

        target = targets[:, :, None]
        candidate = candidates[:, None]
        pair_geometry = _relative_pose(target, candidate).to(fields.features.dtype)
        target_query = target_features[:, :, None].expand(-1, -1, candidate_count, -1)
        pair_query = torch.cat((pair_geometry, target_query.to(pair_geometry.dtype)), dim=-1)

        field = fields.t_world_field
        target_field = _relative_pose(targets[:, :, None], field[:, None]).to(fields.features.dtype)
        candidate_field = _relative_pose(candidates[:, :, None], field[:, None]).to(fields.features.dtype)
        target_field = target_field[:, :, None].expand(-1, -1, candidate_count, -1, -1)
        candidate_field = candidate_field[:, None].expand(-1, target_count, -1, -1, -1)
        age = torch.log1p((times[:, :, None] - fields.time_s[:, None]).clamp_min(0.0))
        age = age.to(fields.features.dtype)[:, None, :, :, None].expand(-1, target_count, -1, -1, -1)
        feature = fields.features[:, None, None].expand(-1, target_count, candidate_count, -1, -1)
        field_inputs = torch.cat((feature, target_field, candidate_field, age), dim=-1)
        valid = causal_valid[:, None].expand(-1, target_count, -1, -1)

        pair_count = batch * target_count * candidate_count
        return (
            pair_query.reshape(pair_count, self._POSE_DIM + self.config.target_feature_dim),
            field_inputs.reshape(pair_count, field_count, -1),
            valid.reshape(pair_count, field_count),
        )

    def forward(
        self,
        fields: TemporalFieldBatch,
        targets_world_query: Tensor,
        candidates_world_camera: Tensor,
        *,
        target_features: Tensor,
        query_time_s: Tensor | None = None,
    ) -> Tensor:
        """Return ``Tensor[B,T,C,K-1]`` target-candidate ordinal logits."""

        batch = fields.features.shape[0]
        self._validate_poses("targets_world_query", targets_world_query, batch=batch)
        self._validate_poses("candidates_world_camera", candidates_world_camera, batch=batch)
        targets = targets_world_query.shape[1]
        candidates = candidates_world_camera.shape[1]
        pair_geometry, field_inputs, valid = self._pair_inputs(
            fields,
            targets_world_query,
            candidates_world_camera,
            target_features,
            query_time_s,
        )
        tokens = self.field_projection(field_inputs)
        query = self.query_token.expand(tokens.shape[0], -1, -1) + self.query_projection(pair_geometry)[:, None]
        tokens = torch.cat((query, tokens), dim=1)
        valid = torch.cat((torch.ones_like(valid[:, :1]), valid), dim=1)
        for _ in range(self.config.num_layers):
            tokens = self.refiner(tokens, src_key_padding_mask=~valid)
        logits = cast(
            Tensor,
            self.head_coral(self.norm(tokens[:, 0])).reshape(
                batch,
                targets,
                candidates,
                self.config.num_classes - 1,
            ),
        )
        return logits

    def forward_vin_batch(
        self,
        batch: VinOracleBatch,
        targets_world_query: Tensor,
        target_features: Tensor,
        *,
        query_time_s: Tensor | None = None,
        pair_valid: Tensor | None = None,
    ) -> Tensor:
        """Run directly on the temporal fields and candidates in a training batch."""

        if batch.temporal_fields is None:
            raise ValueError("VinOracleBatch.temporal_fields is required")
        candidates = batch.candidate_poses_world_cam.matrix3x4
        if candidates.ndim == 3:
            candidates = candidates.unsqueeze(0)
        logits = cast(
            Tensor,
            self(
                batch.temporal_fields,
                targets_world_query,
                candidates,
                target_features=target_features,
                query_time_s=query_time_s,
            ),
        )
        if pair_valid is None:
            return logits
        if pair_valid.dtype is not torch.bool or pair_valid.shape != logits.shape[:-1]:
            raise ValueError("pair_valid must be bool with shape [B,T,C]")
        return logits.masked_fill(~pair_valid[..., None], 0.0)

    def forward_grouped_rollout(
        self,
        batch: VinOracleBatch,
        rollout: GroupedRolloutTrainingBatch,
        *,
        query_time_s: Tensor | None = None,
    ) -> Tensor:
        """Consume one canonical rollout-derived target/candidate view and VIN field history."""

        if batch.temporal_fields is None:
            raise ValueError("VinOracleBatch.temporal_fields is required")
        scene_ids = [batch.scene_id] if isinstance(batch.scene_id, str) else batch.scene_id
        snippet_ids = [batch.snippet_id] if isinstance(batch.snippet_id, str) else batch.snippet_id
        split_ids = [batch.split] if isinstance(batch.split, str) else batch.split
        if (scene_ids, snippet_ids, split_ids) != ([rollout.scene_id], [rollout.snippet_id], [rollout.split]):
            raise ValueError("VIN field history and grouped rollout must identify the same single source snippet")
        logits = cast(
            Tensor,
            self(
                batch.temporal_fields,
                rollout.targets_world_query,
                rollout.candidates_world_camera,
                target_features=rollout.target_features,
                query_time_s=query_time_s,
            ),
        )
        return logits.masked_fill(~rollout.pair_valid[..., None], 0.0)


def hierarchical_temporal_coral_loss(
    logits: Tensor,
    labels: Tensor,
    pair_valid: Tensor,
    *,
    num_classes: int,
) -> Tensor:
    """Average ordinal error over candidates, targets, then real scene batches."""

    if logits.shape[:-1] != labels.shape or labels.shape != pair_valid.shape:
        raise ValueError("logits, labels, and pair_valid must align as [B,T,C,K-1], [B,T,C], [B,T,C]")
    if pair_valid.dtype is not torch.bool:
        raise TypeError("pair_valid must be bool")
    if not pair_valid.any().item():
        raise ValueError("at least one pair must be valid")
    per_pair = coral_loss(logits, labels, num_classes=num_classes, reduction="none")
    target_loss = (per_pair * pair_valid).sum(dim=2) / pair_valid.sum(dim=2).clamp_min(1)
    target_valid = pair_valid.any(dim=2)
    scene_loss = (target_loss * target_valid).sum(dim=1) / target_valid.sum(dim=1).clamp_min(1)
    scene_valid = target_valid.any(dim=1)
    return (scene_loss * scene_valid).sum() / scene_valid.sum()


__all__ = ["TemporalFieldTransformer", "TemporalFieldTransformerConfig", "hierarchical_temporal_coral_loss"]
