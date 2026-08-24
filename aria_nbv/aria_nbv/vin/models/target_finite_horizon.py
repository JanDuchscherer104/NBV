r"""Actor-only finite-horizon scorer for persisted :math:`Q_H` chain views.

The scorer estimates a scalar member of the bounded conditional-value family

$$
Q_h(s_t,e,q_{t,i}\mid b_t),\qquad 1 \le h \le b_t \le H_{\max}.
$$

Here ``s_t`` is the actor-visible state before selecting action ``t``: immutable
root evidence, the strictly causal selected-pose prefix, the current finite
candidate table, and factual remaining budget ``b_t``. ``e`` is the target
object represented by its root-relative pose and metric extents, and
``q_{t,i}`` is one materialized candidate camera. The requested residual
horizon ``h`` selects an estimand; it is not a substitute for ``b_t`` and does
not reveal future observations. Supervision, oracle lineage, and policy masks
remain outside this module.

The model implements the shared ``A0/A1--S0-pose--root-moments`` scorer. A1
candidate-to-state attention remains the default; A0 is its identical-input
independent-row MLP control. For each materialized candidate row the scorer
separates four information paths:

* a physical trunk encodes the candidate in the rollout-root and current-camera
  frames together with compact root-scene evidence; it is independent of the
  target, requested horizon, labels, and authoritative ``action_mask``;
* a conditional-value query adds the target expressed in the candidate frame;
* the configured A0/A1 fusion combines that query with exactly five shared
  state tokens: scene, target, causal pose history, remaining budget
  :math:`b_t`, and requested residual horizon :math:`h`;
* a modular terminal decoder maps the shared feature to one continuous
  conditional value. Regression predicts it directly; CORAL discretizes the
  same fitted-Q target and decodes fixed continuous representatives.

The root scene carrier is intentionally small and lossy: detached EVL channel
moments plus root-frame semidense point mean, standard deviation, presence, and
support. It is an executable control, not a claim that global moments are a
sufficient reconstruction state. Candidate rows never exchange information,
so a joint row permutation produces the same output permutation and duplicate
rows remain identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import TargetConfig
from ..encoders import R6dLffPoseEncoder, R6dLffPoseEncoderConfig
from ..modules.qh_state_fusion import (
    QhCrossAttentionStateFusionConfig,
    QhStateFusionConfig,
)
from ..modules.qh_value_decoders import (
    QhCoralAuxiliary,
    QhCoralValueDecoder,
    QhRegressionValueDecoderConfig,
    QhValueDecoderConfig,
)

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
        value_auxiliary: Optional decoder-specific training payload. CORAL
            supplies cumulative threshold logits and fixed Q-bin edges;
            regression supplies ``None``. Bellman backup and online ranking
            always consume ``conditional_q``, never this auxiliary payload.
    """

    conditional_q: Tensor
    """``Tensor["B S N", float32]`` action-mask-independent conditional values."""

    feasibility_logits: Tensor
    """``Tensor["B S N", float32]`` binary-validity logits from the physical trunk."""

    value_auxiliary: QhCoralAuxiliary | None = None
    """Optional decoder training payload; policy backup and ranking never consume it."""


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

    state_fusion: QhStateFusionConfig = Field(default_factory=QhCrossAttentionStateFusionConfig)
    """A0/A1 interaction over the identical candidate query and state tokens.

    The default preserves A1 candidate-to-state cross-attention. A0 replaces
    only that interaction with a fixed-order independent-row MLP; target,
    scene, history, budget, horizon, decoder, and mask semantics stay fixed.
    """

    dropout: float = Field(default=0.05, ge=0.0, lt=1.0)
    """Training-only dropout in state fusion and the value decoder."""

    value_decoder: QhValueDecoderConfig = Field(default_factory=QhRegressionValueDecoderConfig)
    """Terminal scalar-Q decoder over the shared candidate-state feature.

    Direct regression is canonical. CORAL is an explicitly configured ordinal
    ablation whose fixed label edges and continuous representatives are bound
    into scorer and bundle identity.
    """

    max_horizon: int = Field(default=5, gt=0)
    """Largest admitted acquisition horizon; remaining budget is normalized by this value."""

    horizon_query_semantics: Literal["bounded_scalar_v1"] = "bounded_scalar_v1"
    """Scalar query family admitting every realized ``1 <= h <= b_t <= H_max``."""

    experiment_profile: Literal["qh_cf0_v1"] = "qh_cf0_v1"
    """Closed deployable actor profile; privileged CF+ observations are not accepted."""

    @property
    def target_type(self) -> type["TargetFiniteHorizonScorer"]:
        """Return the concrete scorer constructed by :meth:`setup_target`."""

        return TargetFiniteHorizonScorer

    @model_validator(mode="after")
    def _validate_architecture(self) -> "TargetFiniteHorizonScorerConfig":
        """Reject incompatible shared widths and ambiguous scene channels."""

        if (
            isinstance(self.state_fusion, QhCrossAttentionStateFusionConfig)
            and self.hidden_dim % self.state_fusion.attention_heads != 0
        ):
            raise ValueError("hidden_dim must be divisible by state_fusion.attention_heads.")
        if not self.scene_channels:
            raise ValueError("scene_channels must contain at least one root-EVL field.")
        if len(set(self.scene_channels)) != len(self.scene_channels):
            raise ValueError("scene_channels must be unique and ordered.")
        return self


class TargetFiniteHorizonScorer(nn.Module):
    r"""Predict candidate feasibility and conditional finite-horizon value.

    The module exposes one deep interface: a batched
    :class:`~aria_nbv.data_handling.qh_data.QhActorTensors` enters and one
    candidate-aligned :class:`QhScoreOutput` leaves. Every materialized row is
    encoded independently of ``action_mask``. Candidate rows never attend to
    one another, so jointly permuting candidate poses and masks permutes both
    outputs identically and invalid rows cannot influence valid rows.

    Theory:
        The public family is

        $$
        Q_h(s_t,e,q_{t,i}\mid b_t),\qquad 1\le h\le b_t\le H_{\max}.
        $$

        ``b_t`` is the factual number of acquisitions still available in the
        stored state; ``h`` is the number of rewards represented by this query.
        They are separately normalized by ``H_max`` and encoded by separate
        MLPs, so an off-diagonal query changes the value estimand without
        falsifying the actor state. ``None`` means the factual diagonal
        ``h=b_t``. Realized rows reject ``h=0`` or ``h>b_t``; padded states use
        ``h=0`` only. ``Q_0=0`` is a mathematical backup boundary and has no
        learned output.

        The physical trunk reads candidate root/current-relative pose and a
        compact root-scene summary. Its feasibility head therefore cannot read
        the target, requested horizon, remaining budget, labels, or
        ``action_mask``. Conditional Q additionally reads candidate-to-target
        geometry and five shared state tokens: root scene, target, causal pose
        history, budget, and requested horizon. Candidate rows are independent
        queries over those shared tokens; no attention axis crosses candidates.

        Geometry uses explicit transform direction.
        ``candidate_pose_relative_root`` is root-from-candidate
        :math:`T_{r\leftarrow c_i}`. The physical trunk also forms
        current-from-candidate :math:`T_{c_t\leftarrow c_i}`. Conditional Q
        receives candidate-from-target :math:`T_{c_i\leftarrow e}`, so the same
        target induces a different relation for every candidate without making
        feasibility target-dependent.

        The target token encodes the root-relative target pose plus metric
        extents. Target source is an experiment-profile fact rather than
        something inferred from tensor shape. Scene context is the deliberately
        lossy ``root_moments_v1`` carrier. Causal history is the mean of past
        selected poses expressed from the current camera; it discards order so
        ordered history remains an honest representation ablation.

    Notes:
        Syntactic admission does not assert empirical support. Lightning owns
        which horizons receive targets, while a verified inference bundle owns
        the manifest-bound set of horizons that may be deployed.
    """

    def __init__(self, config: TargetFiniteHorizonScorerConfig) -> None:
        """Construct the physical trunk, five state-token paths, and decoder."""

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
        self.state_fusion = config.state_fusion.setup_target(
            hidden_dim=hidden_dim,
            state_token_count=5,
            dropout=float(config.dropout),
        )
        self.value_decoder = config.value_decoder.setup_target(
            in_dim=3 * hidden_dim,
            hidden_dim=hidden_dim,
            dropout=float(config.dropout),
        )

    def validate_value_decoder_state(self, *, require_publishable: bool = False) -> None:
        """Validate non-learned decoder state against scorer configuration.

        Learned weights may vary while the scorer configuration stays fixed,
        but CORAL edges and representatives are experiment identity: they
        determine supervision labels and convert ordinal mass back into the
        continuous units used by Bellman backup and policy ranking. This hook
        gives bundle owners one decoder-agnostic validation seam and leaves
        direct regression as the no-extra-state baseline.
        """

        if isinstance(self.value_decoder, QhCoralValueDecoder):
            self.value_decoder.validate_configured_support()
            if require_publishable:
                self.value_decoder.require_publishable_support()

    def forward(
        self,
        actor: QhActorTensors,
        *,
        requested_horizon: Tensor | None = None,
    ) -> QhScoreOutput:
        r"""Return mask-independent candidate predictions in stored order.

        Args:
            actor: Batched actor-visible chain with candidate support
                ``Tensor["B S N", bool]`` and compact root EVL evidence.
            requested_horizon: Optional ``Tensor["B S", int64]`` value query.
                ``None`` means :attr:`QhActorTensors.horizon_remaining`.
                Realized rows admit ``1 <= h <= b_t <= H_max``; padding must be
                zero. This scalar selects one bounded value estimand per state,
                not a public horizon axis.

        Returns:
            Candidate-aligned conditional Q and feasibility logits. Both are
            finite on materialized realized rows and zero only on padding.
            CORAL additionally returns threshold logits and its fixed support
            in ``value_auxiliary`` for Lightning supervision and diagnostics;
            policy backup and ranking still use only ``conditional_q``.
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
        state_context = self.state_fusion(value_queries, state_tokens)
        decoded_value = self.value_decoder(
            torch.cat((value_queries, state_context, value_queries * state_context), dim=-1)
        )
        conditional_q = decoded_value.conditional_q
        conditional_q = torch.where(candidate_mask, conditional_q, torch.zeros_like(conditional_q))
        feasibility_logits = torch.where(candidate_mask, feasibility_logits, torch.zeros_like(feasibility_logits))
        value_auxiliary = decoded_value.coral
        if value_auxiliary is not None:
            logits = torch.where(
                candidate_mask.unsqueeze(-1),
                value_auxiliary.logits,
                torch.zeros_like(value_auxiliary.logits),
            )
            if not bool(torch.isfinite(logits[candidate_mask]).all()):
                raise ValueError("TargetFiniteHorizonScorer produced nonfinite CORAL logits on materialized rows.")
            value_auxiliary = QhCoralAuxiliary(
                logits=logits.float(),
                bin_edges=value_auxiliary.bin_edges.float(),
                bin_values=value_auxiliary.bin_values.float(),
            )
        if not bool(torch.isfinite(conditional_q[candidate_mask]).all()):
            raise ValueError("TargetFiniteHorizonScorer produced nonfinite conditional Q on materialized rows.")
        if not bool(torch.isfinite(feasibility_logits[candidate_mask]).all()):
            raise ValueError("TargetFiniteHorizonScorer produced nonfinite feasibility logits on materialized rows.")
        return QhScoreOutput(
            conditional_q=conditional_q.float(),
            feasibility_logits=feasibility_logits.float(),
            value_auxiliary=value_auxiliary,
        )

    def _validated_requested_horizon(
        self,
        actor: QhActorTensors,
        requested_horizon: Tensor | None,
    ) -> Tensor:
        """Return one bounded scalar query per state after fail-closed validation."""

        horizon = actor.horizon_remaining if requested_horizon is None else requested_horizon
        expected = actor.step_mask.shape
        if horizon.shape != expected:
            raise ValueError(f"Q_H requested_horizon must have shape {tuple(expected)}, got {tuple(horizon.shape)}.")
        if horizon.dtype is not torch.int64:
            raise ValueError("Q_H requested_horizon must use int64 dtype.")
        if horizon.device != actor.step_mask.device:
            raise ValueError("Q_H requested_horizon must be on the actor device.")
        realized = actor.step_mask
        if bool((realized & horizon.lt(1)).any()):
            raise ValueError("Q_H realized requested_horizon must be at least one.")
        if bool((realized & horizon.gt(actor.horizon_remaining)).any()):
            raise ValueError("Q_H requested_horizon cannot exceed factual horizon_remaining.")
        if bool((realized & horizon.gt(self.config.max_horizon)).any()):
            raise ValueError(f"Q_H requested_horizon exceeds configured H_max={self.config.max_horizon}.")
        if bool((~realized & horizon.ne(0)).any()):
            raise ValueError("Q_H padded requested horizons must be zero.")
        return horizon

    def _current_pose_relative_root(self, actor: QhActorTensors, history_pose: PoseTW) -> PoseTW:
        r"""Return root-from-current-camera :math:`T_{r\leftarrow c_t}`.

        At chain state :math:`s_t`, the current camera is the root identity for
        :math:`t=0` and the immediately preceding selected candidate for
        :math:`t>0`. A realized non-root state without that predecessor is not
        a causal transition and fails closed rather than inventing a pose.
        """

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
        r"""Pool the versioned ``root_moments_v1`` scene carrier.

        Every configured EVL field contributes global mean, standard
        deviation, minimum, and maximum. Semidense world points are transformed
        by :math:`T_{r\leftarrow w}` into the rollout-root frame and contribute
        coordinate-wise mean and standard deviation plus explicit presence and
        valid-support fraction. Source tensors are detached because these are
        persisted actor observations, not an end-to-end EFM3D training path.

        The summary is shared across all states and candidates in one chain.
        It records broad occupancy/free-space statistics but no query-local
        topology, visibility ray, or selected-observation update; richer point
        and ray memories must be evaluated as separately named carriers.
        """

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
