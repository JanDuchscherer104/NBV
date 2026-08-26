r"""Modular causal-history summaries for the finite-horizon scorer.

The :math:`Q_H` actor carries, for every realized state :math:`s_t`, the
strictly causal sequence of previously selected camera poses
:math:`(T_{r\leftarrow c_0},\ldots,T_{r\leftarrow c_{t-1}})` and an explicit
``history_mask``. The scorer first expresses every selected pose from the
current camera and applies its shared pose encoder. This module owns only the
map from those row-aligned pose features to one fixed-width history summary;
it does not read candidates, targets, rewards, action validity, requested
horizon, or remaining budget.

``mean_pool_v1`` is the H0 control. It reproduces the original masked arithmetic
mean exactly and therefore destroys order and multiplicity beyond their effect
on the mean. It is parameter-free so pre-existing scorer state dictionaries
retain their ``history_projection`` keys. The scorer omits its ``None`` alias
from serialized legacy-equivalent configuration, so older bundle hashes and
strict state loading remain valid.

``causal_transformer_v1`` is the H1 exploratory carrier. It adds a normalized
relative-age feature to each current-camera-relative pose token, prepends a
learned empty-history token, and applies causal self-attention. The final valid
token summarizes the observed prefix; at :math:`t=0`, the empty token is the
summary. Relative age binds chronology to the pose rather than exposing an
arbitrary padded slot number. History length is allowed to be observable: it
is factual causal state, while remaining budget :math:`b_t` and requested
horizon :math:`h` remain separate scorer tokens. This does not make step index
an independent feature and does not imply stationarity across acquisition
lengths.

Both variants return the pose-feature width. The scorer's existing
``history_projection`` then maps that summary into the shared state-token
width. Keeping projection outside this seam makes H0 a literal behavioral and
checkpoint-compatible control and confines H1's extra capacity to one named
module.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

import torch
from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig


class QhMeanPoolHistoryEncoderConfig(TargetConfig["QhMeanPoolHistoryEncoder"]):
    """Configure the parameter-free H0 masked-mean history control."""

    kind: Literal["mean_pool_v1"] = "mean_pool_v1"
    """Discriminator persisted in scorer and inference-bundle configuration."""

    @property
    def target_type(self) -> type["QhMeanPoolHistoryEncoder"]:
        """Return the runtime H0 history encoder class."""

        return QhMeanPoolHistoryEncoder


class QhCausalTransformerHistoryEncoderConfig(TargetConfig["QhCausalTransformerHistoryEncoder"]):
    """Configure the H1 ordered causal-pose history ablation.

    ``attention_heads`` must divide the configured pose-feature width. The
    feed-forward multiplier and layer count change representation capacity and
    are therefore persisted experiment identity rather than hidden runtime
    tuning.
    """

    kind: Literal["causal_transformer_v1"] = "causal_transformer_v1"
    """Discriminator persisted in scorer and inference-bundle configuration."""

    attention_heads: int = Field(default=4, gt=0)
    """Parallel temporal-attention heads over one state's selected prefix."""

    layers: int = Field(default=1, gt=0)
    """Number of causal Transformer encoder layers."""

    feedforward_multiplier: int = Field(default=2, gt=0)
    """Per-layer feed-forward width as a multiple of pose-feature width."""

    @property
    def target_type(self) -> type["QhCausalTransformerHistoryEncoder"]:
        """Return the runtime H1 history encoder class."""

        return QhCausalTransformerHistoryEncoder


QhHistoryEncoderConfig: TypeAlias = Annotated[
    QhMeanPoolHistoryEncoderConfig | QhCausalTransformerHistoryEncoderConfig,
    Field(discriminator="kind"),
]
"""Persisted union of H0/H1 causal-history representation configurations."""


class QhMeanPoolHistoryEncoder(nn.Module):
    r"""Return the masked mean of past selected-pose features.

    For current-relative pose features :math:`p_{t,j}` and causal support
    :math:`m_{t,j}`, H0 computes

    .. math::
        \bar p_t = \frac{\sum_j m_{t,j}p_{t,j}}
        {\max(1,\sum_j m_{t,j})}.

    Thus the root state returns the all-zero pose summary before the scorer's
    learned projection. Permuting valid history entries cannot change H0; that
    invariance is the control against which an order-sensitive carrier is
    measured.
    """

    def __init__(
        self,
        config: QhMeanPoolHistoryEncoderConfig,
        *,
        feature_dim: int,
        max_horizon: int,
        dropout: float,
    ) -> None:
        """Construct the parameter-free control and validate shared bounds."""

        super().__init__()
        del config
        _validate_constructor(feature_dim=feature_dim, max_horizon=max_horizon, dropout=dropout)
        self.feature_dim = int(feature_dim)
        self.max_horizon = int(max_horizon)

    def forward(self, history_features: Tensor, history_mask: Tensor, step_mask: Tensor) -> Tensor:
        """Return ``Tensor[\"B S F\", float32]`` masked mean summaries."""

        _validate_inputs(
            history_features,
            history_mask,
            step_mask,
            feature_dim=self.feature_dim,
            max_horizon=self.max_horizon,
        )
        history_sum = torch.where(
            history_mask.unsqueeze(-1),
            history_features,
            torch.zeros_like(history_features),
        ).sum(dim=-2)
        history_count = history_mask.sum(dim=-1, keepdim=True).clamp_min(1)
        return history_sum / history_count


class QhCausalTransformerHistoryEncoder(nn.Module):
    r"""Encode selected poses as an ordered, strictly causal prefix.

    Let :math:`a_{t,j}=(t-1-j)/H_{max}` be the relative age of selected pose
    :math:`j` at decision state :math:`t`. H1 forms
    :math:`z_{t,j}=p_{t,j}+g(a_{t,j})`, prepends a learned empty token, and
    applies a causal Transformer. Reading the last materialized token permits
    that summary to attend to the entire observed prefix while preventing any
    token from reading a later slot. Padded keys are masked and their numeric
    contents cannot affect the result.

    Current-camera-relative pose features already remove arbitrary world
    origin, while relative age distinguishes paths containing the same pose
    multiset in a different order. The representation is not claimed to be
    SE(3)-equivariant, a sufficient scene state, or superior to H0; those are
    empirical questions for matched held-out and policy evaluation.
    """

    def __init__(
        self,
        config: QhCausalTransformerHistoryEncoderConfig,
        *,
        feature_dim: int,
        max_horizon: int,
        dropout: float,
    ) -> None:
        """Construct relative-age projection, empty token, and causal stack."""

        super().__init__()
        _validate_constructor(feature_dim=feature_dim, max_horizon=max_horizon, dropout=dropout)
        if int(feature_dim) % int(config.attention_heads) != 0:
            raise ValueError("Q_H history feature_dim must be divisible by attention_heads.")
        self.feature_dim = int(feature_dim)
        self.max_horizon = int(max_horizon)
        self.empty_history = nn.Parameter(torch.zeros(self.feature_dim))
        self.relative_age_projection = nn.Sequential(
            nn.Linear(1, self.feature_dim),
            nn.GELU(),
            nn.LayerNorm(self.feature_dim),
        )
        layer = nn.TransformerEncoderLayer(
            d_model=self.feature_dim,
            nhead=int(config.attention_heads),
            dim_feedforward=self.feature_dim * int(config.feedforward_multiplier),
            dropout=float(dropout),
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            layer,
            num_layers=int(config.layers),
            norm=nn.LayerNorm(self.feature_dim),
            enable_nested_tensor=False,
        )

    def forward(self, history_features: Tensor, history_mask: Tensor, step_mask: Tensor) -> Tensor:
        """Return ``Tensor[\"B S F\", float32]`` last-prefix summaries.

        The input contains one independent sequence per decision state. A
        state's history may be shorter than the materialized history axis, but
        any present entry must precede that state on the shared step axis.
        ``history_mask`` is the pose-support mask; authoritative action
        validity remains outside the representation module. The accompanying
        ``step_mask`` distinguishes the realized empty root state
        from padded states and lets the seam require an exact prefix rather
        than merely a subset of earlier slots.
        """

        _validate_inputs(
            history_features,
            history_mask,
            step_mask,
            feature_dim=self.feature_dim,
            max_horizon=self.max_horizon,
        )
        batch_size, steps, history_slots, _feature_dim = history_features.shape
        state_index = torch.arange(steps, device=history_features.device).view(1, steps, 1, 1)
        history_index = torch.arange(history_slots, device=history_features.device).view(1, 1, history_slots, 1)
        relative_age = state_index - 1 - history_index
        normalized_age = relative_age.to(dtype=history_features.dtype) / float(self.max_horizon)
        age_features = self.relative_age_projection(normalized_age).expand(batch_size, -1, -1, -1)
        history_tokens = torch.where(
            history_mask.unsqueeze(-1),
            history_features + age_features,
            torch.zeros_like(history_features),
        )

        empty = self.empty_history.to(dtype=history_features.dtype).view(1, 1, 1, -1)
        empty = empty.expand(batch_size, steps, 1, -1)
        sequence = torch.cat((empty, history_tokens), dim=-2)
        flat_sequence = sequence.reshape(batch_size * steps, history_slots + 1, self.feature_dim)
        key_padding = torch.cat(
            (
                torch.zeros((*history_mask.shape[:2], 1), dtype=torch.bool, device=history_mask.device),
                ~history_mask,
            ),
            dim=-1,
        ).reshape(batch_size * steps, history_slots + 1)
        causal_mask = torch.ones(
            (history_slots + 1, history_slots + 1),
            dtype=torch.bool,
            device=history_features.device,
        ).triu(diagonal=1)
        encoded = self.transformer(
            flat_sequence,
            mask=causal_mask,
            src_key_padding_mask=key_padding,
        ).reshape(batch_size, steps, history_slots + 1, self.feature_dim)

        slot_numbers = torch.arange(1, history_slots + 1, device=history_mask.device).view(1, 1, -1)
        last_valid = torch.where(history_mask, slot_numbers, torch.zeros_like(slot_numbers)).amax(dim=-1)
        gather_index = last_valid.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, self.feature_dim)
        summary = encoded.gather(-2, gather_index).squeeze(-2)
        return torch.where(step_mask.unsqueeze(-1), summary, torch.zeros_like(summary))


def _validate_constructor(*, feature_dim: int, max_horizon: int, dropout: float) -> None:
    """Validate bounds shared by both history representations."""

    if int(feature_dim) < 1:
        raise ValueError("Q_H history feature_dim must be positive.")
    if int(max_horizon) < 1:
        raise ValueError("Q_H history max_horizon must be positive.")
    if not 0.0 <= float(dropout) < 1.0:
        raise ValueError("Q_H history dropout must lie in [0, 1).")


def _validate_inputs(
    history_features: Tensor,
    history_mask: Tensor,
    step_mask: Tensor,
    *,
    feature_dim: int,
    max_horizon: int,
) -> None:
    """Reject representation drift at the causal-history seam."""

    if history_features.ndim != 4 or history_mask.ndim != 3 or step_mask.ndim != 2:
        raise ValueError("Q_H history encoding requires features [B,S,L,F], history mask [B,S,L], and step mask [B,S].")
    if history_features.shape[:-1] != history_mask.shape:
        raise ValueError("Q_H history features and mask must share B,S,L axes.")
    if history_features.shape[:2] != step_mask.shape:
        raise ValueError("Q_H history features and step_mask must share B,S axes.")
    if history_features.shape[-1] != int(feature_dim):
        raise ValueError("Q_H history features do not match the configured feature width.")
    if history_features.shape[1] > int(max_horizon) or history_features.shape[2] > int(max_horizon):
        raise ValueError("Q_H history axes exceed the configured maximum horizon.")
    if history_mask.dtype is not torch.bool or step_mask.dtype is not torch.bool:
        raise ValueError("Q_H history_mask and step_mask must use bool dtype.")
    if not history_features.is_floating_point():
        raise ValueError("Q_H history features must use a floating dtype.")
    if not bool(torch.isfinite(history_features[history_mask]).all()):
        raise ValueError("Q_H materialized history features must be finite.")
    state_index = torch.arange(history_mask.shape[1], device=history_mask.device).view(1, -1, 1)
    history_index = torch.arange(history_mask.shape[2], device=history_mask.device).view(1, 1, -1)
    expected_prefix = step_mask.unsqueeze(-1) & history_index.lt(state_index)
    if not torch.equal(history_mask, expected_prefix.expand_as(history_mask)):
        raise ValueError("Q_H realized history support must equal the complete strictly causal prefix.")


__all__ = [
    "QhCausalTransformerHistoryEncoder",
    "QhCausalTransformerHistoryEncoderConfig",
    "QhHistoryEncoderConfig",
    "QhMeanPoolHistoryEncoder",
    "QhMeanPoolHistoryEncoderConfig",
]
