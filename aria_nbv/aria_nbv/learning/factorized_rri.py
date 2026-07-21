r"""Factorized scene, target, and candidate encoding for absolute RRI.

The actor scene is encoded once. Target and candidate rows are then encoded
independently and combined only by a cheap Cartesian scorer. This excludes
target-target and candidate-candidate interaction, so absolute predictions are
consistent under bundle subsets and candidate permutations.
"""

from __future__ import annotations

from typing import Literal, cast

import torch
from jaxtyping import Bool, Float
from torch import Tensor, nn

from .bundle import ActorSceneBundle, SceneBundleSupervision


def _masked_mean(values: Tensor, valid: Tensor, *, dim: int) -> Tensor:
    weights = valid.to(values.dtype).unsqueeze(-1)
    return (values * weights).sum(dim=dim) / weights.sum(dim=dim).clamp_min(1.0)


def _signed_log(value: Tensor) -> Tensor:
    return value.sign() * torch.log1p(value.abs())


def _latest_scene_anchor(bundle: ActorSceneBundle) -> tuple[Tensor, Tensor]:
    masked_time = bundle.scene_time_s.masked_fill(~bundle.scene_valid, -torch.inf)
    index = masked_time.argmax(dim=1)
    batch_index = torch.arange(bundle.scene_features.shape[0], device=index.device)
    pose = bundle.t_world_scene[batch_index, index]
    time_s = bundle.scene_time_s[batch_index, index]
    has_scene = bundle.scene_valid.any(dim=1)
    neutral_pose = torch.eye(4, device=pose.device, dtype=pose.dtype)[:3].expand_as(pose)
    pose = torch.where(has_scene[:, None, None], pose, neutral_pose)
    time_s = torch.where(has_scene, time_s, torch.zeros_like(time_s))
    return pose, time_s


def _anchor_local_geometry(anchor: Tensor, poses: Tensor) -> Tensor:
    anchor_rotation_inv = anchor[..., :3].transpose(-1, -2)
    delta_world = poses[..., 3] - anchor[:, None, :, 3]
    delta_anchor = torch.einsum("bij,bnj->bni", anchor_rotation_inv, delta_world)
    relative_rotation = torch.einsum("bij,bnjk->bnik", anchor_rotation_inv, poses[..., :3])
    return torch.cat((delta_anchor, relative_rotation.flatten(start_dim=-2)), dim=-1)


def _pair_geometry(bundle: ActorSceneBundle, latest_scene_time_s: Tensor) -> Tensor:
    target_rotation_inv = bundle.t_world_target[..., :3].transpose(-1, -2)
    delta_world = bundle.t_world_candidate[:, None, :, :, 3] - bundle.t_world_target[:, :, None, :, 3]
    delta_target = torch.einsum("btij,btcj->btci", target_rotation_inv, delta_world)
    relative_rotation = torch.einsum(
        "btij,bcjk->btcik",
        target_rotation_inv,
        bundle.t_world_candidate[..., :3],
    )
    relative_time = _signed_log(bundle.candidate_time_s - latest_scene_time_s[:, None])[:, None, :, None]
    return torch.cat(
        (
            delta_target,
            relative_rotation.flatten(start_dim=-2),
            relative_time.expand(-1, bundle.target_features.shape[1], -1, -1),
        ),
        dim=-1,
    )


class FactorizedRriModel(nn.Module):
    r"""Predict absolute utility with subset-consistent factorized queries.

    Scene poses are expressed relative to the latest valid actor pose, while
    each target-candidate pair uses target-local translation and rotation.
    These relative transforms make scalar outputs invariant to a shared global
    SE(3) change of coordinates. Repeating ``scene_refiner`` reuses one set of
    weights, providing a small DejaView-style iterative memory update.

    Invalid output slots are unspecified values; consumers must retain
    :attr:`ActorSceneBundle.pair_valid` as a hard mask rather than interpreting
    them as low utility.
    """

    _POSE_DIM = 12
    _TIMED_POSE_DIM = 13

    def __init__(
        self,
        *,
        scene_feature_dim: int,
        target_feature_dim: int,
        candidate_feature_dim: int,
        hidden_dim: int = 32,
        scene_refinement_steps: int = 1,
    ) -> None:
        """Build independent row encoders and one Cartesian pair head."""

        super().__init__()
        if min(scene_feature_dim, target_feature_dim, candidate_feature_dim, hidden_dim) < 1:
            raise ValueError("feature and hidden dimensions must be positive")
        if scene_refinement_steps < 0:
            raise ValueError("scene_refinement_steps must be non-negative")
        self.feature_dims = (scene_feature_dim, target_feature_dim, candidate_feature_dim)
        self.hidden_dim = hidden_dim
        self.scene_refinement_steps = scene_refinement_steps
        self.scene_encoder = nn.Sequential(nn.Linear(scene_feature_dim + self._TIMED_POSE_DIM, hidden_dim), nn.GELU())
        self.scene_refiner = nn.Sequential(
            nn.Linear(2 * hidden_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, hidden_dim)
        )
        self.scene_norm = nn.LayerNorm(hidden_dim)
        self.target_encoder = nn.Sequential(nn.Linear(target_feature_dim + self._POSE_DIM, hidden_dim), nn.GELU())
        self.candidate_encoder = nn.Sequential(
            nn.Linear(candidate_feature_dim + self._TIMED_POSE_DIM, hidden_dim), nn.GELU()
        )
        self.pair_head = nn.Sequential(
            nn.Linear(3 * hidden_dim + self._TIMED_POSE_DIM, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def _validate_features(self, bundle: ActorSceneBundle) -> None:
        actual = (
            bundle.scene_features.shape[-1],
            bundle.target_features.shape[-1],
            bundle.candidate_features.shape[-1],
        )
        if actual != self.feature_dims:
            raise ValueError(f"bundle feature dimensions {actual} do not match model dimensions {self.feature_dims}")

    def forward(self, bundle: ActorSceneBundle) -> Float[Tensor, "B T C"]:
        """Score every target-candidate pair from actor-visible evidence only."""

        self._validate_features(bundle)
        anchor, latest_time_s = _latest_scene_anchor(bundle)
        scene_geometry = _anchor_local_geometry(anchor, bundle.t_world_scene).to(bundle.scene_features.dtype)
        scene_age = torch.log1p((latest_time_s[:, None] - bundle.scene_time_s).clamp_min(0.0))[..., None]
        scene_input = torch.cat((bundle.scene_features, scene_geometry, scene_age), dim=-1)
        scene_tokens = self.scene_encoder(scene_input).masked_fill(~bundle.scene_valid[..., None], 0.0)
        for _ in range(self.scene_refinement_steps):
            summary = _masked_mean(scene_tokens, bundle.scene_valid, dim=1)
            context = summary[:, None].expand_as(scene_tokens)
            scene_tokens = (scene_tokens + self.scene_refiner(torch.cat((scene_tokens, context), dim=-1))).masked_fill(
                ~bundle.scene_valid[..., None], 0.0
            )
        scene = self.scene_norm(_masked_mean(scene_tokens, bundle.scene_valid, dim=1))

        target_geometry = _anchor_local_geometry(anchor, bundle.t_world_target).to(bundle.target_features.dtype)
        target = self.target_encoder(torch.cat((bundle.target_features, target_geometry), dim=-1))
        candidate_geometry = _anchor_local_geometry(anchor, bundle.t_world_candidate).to(
            bundle.candidate_features.dtype
        )
        candidate_time = _signed_log(bundle.candidate_time_s - latest_time_s[:, None])[..., None]
        candidate = self.candidate_encoder(
            torch.cat((bundle.candidate_features, candidate_geometry, candidate_time), dim=-1)
        )

        targets, candidates = bundle.pair_valid.shape[1:]
        pair_input = torch.cat(
            (
                scene[:, None, None].expand(-1, targets, candidates, -1),
                target[:, :, None].expand(-1, -1, candidates, -1),
                candidate[:, None].expand(-1, targets, -1, -1),
                _pair_geometry(bundle, latest_time_s).to(scene.dtype),
            ),
            dim=-1,
        )
        return cast(Tensor, self.pair_head(pair_input).squeeze(-1))


class FactorizedRriTransformer(nn.Module):
    r"""Cross-attend independent target-candidate queries to one scene memory.

    The shared scene block is a weight-tied Transformer refinement step. Pair
    queries attend to scene tokens but never to one another, preserving exact
    target/candidate subset consistency and permutation equivariance while
    keeping the expensive scene projection shared.
    """

    _POSE_DIM = 12
    _TIMED_POSE_DIM = 13

    def __init__(
        self,
        *,
        scene_feature_dim: int,
        target_feature_dim: int,
        candidate_feature_dim: int,
        hidden_dim: int = 32,
        num_heads: int = 4,
        scene_refinement_steps: int = 1,
    ) -> None:
        """Build one tied scene block and parallel Cartesian query attention."""

        super().__init__()
        if min(scene_feature_dim, target_feature_dim, candidate_feature_dim, hidden_dim, num_heads) < 1:
            raise ValueError("feature dimensions, hidden_dim, and num_heads must be positive")
        if hidden_dim % num_heads:
            raise ValueError("hidden_dim must be divisible by num_heads")
        if scene_refinement_steps < 0:
            raise ValueError("scene_refinement_steps must be non-negative")
        self.feature_dims = (scene_feature_dim, target_feature_dim, candidate_feature_dim)
        self.hidden_dim = hidden_dim
        self.scene_refinement_steps = scene_refinement_steps
        self.scene_encoder = nn.Linear(scene_feature_dim + self._TIMED_POSE_DIM, hidden_dim)
        self.scene_summary = nn.Parameter(torch.zeros(1, 1, hidden_dim))
        self.scene_block = nn.TransformerEncoderLayer(
            hidden_dim,
            num_heads,
            dim_feedforward=2 * hidden_dim,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        pair_dim = target_feature_dim + candidate_feature_dim + 3 * self._TIMED_POSE_DIM - 1
        self.pair_encoder = nn.Sequential(nn.Linear(pair_dim, hidden_dim), nn.GELU())
        self.pair_attention = nn.MultiheadAttention(hidden_dim, num_heads, dropout=0.0, batch_first=True)
        self.output_norm = nn.LayerNorm(hidden_dim)
        self.output = nn.Linear(hidden_dim, 1)

    def _validate_features(self, bundle: ActorSceneBundle) -> None:
        actual = (
            bundle.scene_features.shape[-1],
            bundle.target_features.shape[-1],
            bundle.candidate_features.shape[-1],
        )
        if actual != self.feature_dims:
            raise ValueError(f"bundle feature dimensions {actual} do not match model dimensions {self.feature_dims}")

    def forward(self, bundle: ActorSceneBundle) -> Float[Tensor, "B T C"]:
        """Score independent target-candidate queries against shared memory."""

        self._validate_features(bundle)
        anchor, latest_time_s = _latest_scene_anchor(bundle)
        scene_geometry = _anchor_local_geometry(anchor, bundle.t_world_scene).to(bundle.scene_features.dtype)
        scene_age = torch.log1p((latest_time_s[:, None] - bundle.scene_time_s).clamp_min(0.0))[..., None]
        scene_tokens = self.scene_encoder(torch.cat((bundle.scene_features, scene_geometry, scene_age), dim=-1))
        summary = self.scene_summary.expand(scene_tokens.shape[0], -1, -1)
        scene_tokens = torch.cat((summary, scene_tokens), dim=1)
        scene_valid = torch.cat((torch.ones_like(bundle.scene_valid[:, :1]), bundle.scene_valid), dim=1)
        for _ in range(self.scene_refinement_steps):
            scene_tokens = self.scene_block(scene_tokens, src_key_padding_mask=~scene_valid)

        targets, candidates = bundle.pair_valid.shape[1:]
        target_feature = bundle.target_features[:, :, None].expand(-1, -1, candidates, -1)
        candidate_feature = bundle.candidate_features[:, None].expand(-1, targets, -1, -1)
        target_geometry = _anchor_local_geometry(anchor, bundle.t_world_target).to(target_feature.dtype)
        target_geometry = target_geometry[:, :, None].expand(-1, -1, candidates, -1)
        candidate_geometry = _anchor_local_geometry(anchor, bundle.t_world_candidate).to(candidate_feature.dtype)
        candidate_time = _signed_log(bundle.candidate_time_s - latest_time_s[:, None])[..., None]
        candidate_geometry = torch.cat((candidate_geometry, candidate_time), dim=-1)
        candidate_geometry = candidate_geometry[:, None].expand(-1, targets, -1, -1)
        pair_geometry = _pair_geometry(bundle, latest_time_s).to(target_feature.dtype)
        queries = self.pair_encoder(
            torch.cat(
                (target_feature, candidate_feature, target_geometry, candidate_geometry, pair_geometry),
                dim=-1,
            )
        ).flatten(1, 2)
        attended, _ = self.pair_attention(
            queries,
            scene_tokens,
            scene_tokens,
            key_padding_mask=~scene_valid,
            need_weights=False,
        )
        return cast(Tensor, self.output(self.output_norm(queries + attended)).reshape(-1, targets, candidates))


def hierarchical_masked_loss(
    prediction: Float[Tensor, "B T C"],
    supervision: SceneBundleSupervision,
    *,
    pair_valid: Bool[Tensor, "B T C"],
    loss: Literal["mse", "mae"] = "mse",
) -> Tensor:
    r"""Average error over candidates, then targets, then scenes.

    This reduction gives each scene equal weight and each labeled target equal
    weight within its scene, regardless of how many candidate labels happen to
    be available. The effective mask is the intersection of actor-known pair
    validity and oracle label availability.
    """

    if prediction.ndim != 3 or supervision.utility.shape != prediction.shape or pair_valid.shape != prediction.shape:
        raise ValueError("prediction, supervision, and pair_valid must share shape [B,T,C]")
    if pair_valid.dtype is not torch.bool:
        raise TypeError("pair_valid must be a bool tensor")
    if prediction.device != supervision.utility.device or prediction.device != pair_valid.device:
        raise ValueError("prediction, supervision, and pair_valid must share one device")
    valid = pair_valid & supervision.label_valid
    if not valid.any().item():
        raise ValueError("hierarchical_masked_loss requires at least one valid label")
    residual = torch.where(valid, prediction - supervision.utility, torch.zeros_like(prediction))
    error = residual.square() if loss == "mse" else residual.abs() if loss == "mae" else None
    if error is None:
        raise ValueError("loss must be 'mse' or 'mae'")

    candidate_count = valid.sum(dim=2)
    target_error = error.sum(dim=2) / candidate_count.clamp_min(1)
    target_has_label = candidate_count > 0
    scene_error = (target_error * target_has_label).sum(dim=1) / target_has_label.sum(dim=1).clamp_min(1)
    scene_has_label = target_has_label.any(dim=1)
    return (scene_error * scene_has_label).sum() / scene_has_label.sum()


__all__ = ["FactorizedRriModel", "FactorizedRriTransformer", "hierarchical_masked_loss"]
