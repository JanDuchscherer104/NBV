r"""Candidate-independent-row fusion controls for finite-horizon state tokens.

The finite-horizon scorer builds one candidate query and five shared state
tokens—scene, target, causal history, remaining budget :math:`b_t`, and
requested horizon :math:`h`. This module owns only the interaction that turns
those identical inputs into one candidate-aligned context vector. It never
reads candidate validity, action validity, labels, rewards, or other candidate
rows.

``independent_mlp`` is the A0 interaction control. It concatenates each query
with the five tokens in their manifest-defined semantic order and applies the
same MLP independently to every candidate row. ``cross_attention`` is A1: each
candidate query reads the shared tokens through multi-head cross-attention.
Both return the same ``H``-wide context, so the downstream
``[query, context, query * context]`` decoder feature is unchanged. The
comparison therefore varies interaction structure without varying the actor
carrier, target/source protocol, horizon semantics, decoder family, or mask
ownership.

A0 and A1 are not asserted to be parameter matched. Experiments must report
trainable parameter counts and runtime alongside held-out value and policy
evidence. Neither control models candidate-candidate interaction; jointly
permuting candidate rows must jointly permute their contexts.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

import torch
from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig


class QhIndependentMlpStateFusionConfig(TargetConfig["QhIndependentMlpStateFusion"]):
    """Configure the A0 identical-feature independent-row MLP control."""

    kind: Literal["independent_mlp"] = "independent_mlp"
    """Discriminator persisted in scorer and inference-bundle configuration."""

    @property
    def target_type(self) -> type["QhIndependentMlpStateFusion"]:
        """Return the runtime A0 state-fusion class."""

        return QhIndependentMlpStateFusion


class QhCrossAttentionStateFusionConfig(TargetConfig["QhCrossAttentionStateFusion"]):
    """Configure the A1 candidate-to-state cross-attention interaction."""

    kind: Literal["cross_attention"] = "cross_attention"
    """Discriminator persisted in scorer and inference-bundle configuration."""

    attention_heads: int = Field(default=4, gt=0)
    """Parallel candidate-to-state attention heads; must divide scorer width."""

    @property
    def target_type(self) -> type["QhCrossAttentionStateFusion"]:
        """Return the runtime A1 state-fusion class."""

        return QhCrossAttentionStateFusion


QhStateFusionConfig: TypeAlias = Annotated[
    QhIndependentMlpStateFusionConfig | QhCrossAttentionStateFusionConfig,
    Field(discriminator="kind"),
]
"""Discriminated A0/A1 interaction configuration persisted with the scorer."""


class QhIndependentMlpStateFusion(nn.Module):
    r"""Fuse the same named state tokens independently for each candidate.

    For candidate query :math:`x_{t,i}` and ordered state-token tuple
    :math:`Z_t`, A0 computes
    :math:`c_{t,i}=\operatorname{MLP}([x_{t,i};\operatorname{vec}(Z_t)])`.
    The fixed token order is semantic—not sampled candidate order—and lets the
    control retain every input available to A1 without content-adaptive token
    selection. The shared row-wise map preserves candidate permutation
    equivariance and duplicate-row identity by construction.
    """

    def __init__(
        self,
        config: QhIndependentMlpStateFusionConfig,
        *,
        hidden_dim: int,
        state_token_count: int,
        dropout: float,
    ) -> None:
        """Construct the fixed-order row MLP over one query and all tokens."""

        super().__init__()
        del config
        _validate_constructor(hidden_dim=hidden_dim, state_token_count=state_token_count, dropout=dropout)
        self.hidden_dim = int(hidden_dim)
        self.state_token_count = int(state_token_count)
        self.fusion = nn.Sequential(
            nn.Linear((self.state_token_count + 1) * self.hidden_dim, self.hidden_dim),
            nn.GELU(),
            nn.Dropout(float(dropout)),
            nn.LayerNorm(self.hidden_dim),
        )

    def forward(self, candidate_queries: Tensor, state_tokens: Tensor) -> Tensor:
        """Return ``Tensor["B S N H", float32]`` A0 candidate contexts.

        Args:
            candidate_queries: Candidate-local value queries with shape
                ``[B,S,N,H]``. Rows are processed independently.
            state_tokens: Shared named tokens with shape ``[B,S,K,H]`` in the
                scorer-defined semantic order, where ``K`` equals the
                manifest-bound constructor value.
        """

        _validate_inputs(
            candidate_queries,
            state_tokens,
            hidden_dim=self.hidden_dim,
            state_token_count=self.state_token_count,
        )
        batch_size, steps, candidates, _hidden = candidate_queries.shape
        expanded_state = state_tokens.unsqueeze(-3).expand(
            batch_size,
            steps,
            candidates,
            self.state_token_count,
            self.hidden_dim,
        )
        ordered_features = torch.cat((candidate_queries.unsqueeze(-2), expanded_state), dim=-2).flatten(-2)
        return self.fusion(ordered_features)


class QhCrossAttentionStateFusion(nn.Module):
    r"""Let each candidate query independently read the shared state tokens.

    A1 computes :math:`c_{t,i}=\operatorname{CrossAttn}(x_{t,i},Z_t,Z_t)`.
    State tokens are shared within one state, but candidate queries never serve
    as keys or values. Consequently no candidate can change another
    candidate's context, and no candidate mask is required inside this module.
    Padding is sanitized by the scorer before fusion and zeroed at its output
    boundary; authoritative action validity remains adapter-owned.
    """

    def __init__(
        self,
        config: QhCrossAttentionStateFusionConfig,
        *,
        hidden_dim: int,
        state_token_count: int,
        dropout: float,
    ) -> None:
        """Construct the A1 multi-head candidate-to-state attention block."""

        super().__init__()
        _validate_constructor(hidden_dim=hidden_dim, state_token_count=state_token_count, dropout=dropout)
        if int(hidden_dim) % int(config.attention_heads) != 0:
            raise ValueError("Q_H state-fusion hidden_dim must be divisible by attention_heads.")
        self.hidden_dim = int(hidden_dim)
        self.state_token_count = int(state_token_count)
        self.attention = nn.MultiheadAttention(
            self.hidden_dim,
            int(config.attention_heads),
            dropout=float(dropout),
            batch_first=True,
        )

    def forward(self, candidate_queries: Tensor, state_tokens: Tensor) -> Tensor:
        """Return ``Tensor["B S N H", float32]`` A1 candidate contexts."""

        _validate_inputs(
            candidate_queries,
            state_tokens,
            hidden_dim=self.hidden_dim,
            state_token_count=self.state_token_count,
        )
        batch_size, steps, candidates, _hidden = candidate_queries.shape
        flat_candidates = candidate_queries.reshape(batch_size * steps, candidates, self.hidden_dim)
        flat_state = state_tokens.reshape(batch_size * steps, self.state_token_count, self.hidden_dim)
        context, _weights = self.attention(
            flat_candidates,
            flat_state,
            flat_state,
            need_weights=False,
        )
        return context.reshape(batch_size, steps, candidates, self.hidden_dim)


def _validate_constructor(*, hidden_dim: int, state_token_count: int, dropout: float) -> None:
    """Validate shared dimensions for both runtime fusion controls."""

    if int(hidden_dim) < 1:
        raise ValueError("Q_H state-fusion hidden_dim must be positive.")
    if int(state_token_count) < 1:
        raise ValueError("Q_H state-fusion state_token_count must be positive.")
    if not 0.0 <= float(dropout) < 1.0:
        raise ValueError("Q_H state-fusion dropout must lie in [0, 1).")


def _validate_inputs(
    candidate_queries: Tensor,
    state_tokens: Tensor,
    *,
    hidden_dim: int,
    state_token_count: int,
) -> None:
    """Reject shape or dtype drift at the deep interaction seam."""

    if candidate_queries.ndim != 4 or state_tokens.ndim != 4:
        raise ValueError("Q_H state fusion requires candidate [B,S,N,H] and state [B,S,K,H] tensors.")
    if candidate_queries.shape[:2] != state_tokens.shape[:2]:
        raise ValueError("Q_H candidate queries and state tokens must share B,S axes.")
    if candidate_queries.shape[-1] != hidden_dim or state_tokens.shape[-1] != hidden_dim:
        raise ValueError("Q_H state-fusion inputs must match the configured hidden width.")
    if state_tokens.shape[-2] != state_token_count:
        raise ValueError("Q_H state-fusion token count does not match the configured semantic tuple.")
    if candidate_queries.dtype != state_tokens.dtype:
        raise ValueError("Q_H candidate queries and state tokens must share dtype.")
    if not candidate_queries.is_floating_point() or not state_tokens.is_floating_point():
        raise ValueError("Q_H state-fusion inputs must be floating-point tensors.")


__all__ = [
    "QhCrossAttentionStateFusion",
    "QhCrossAttentionStateFusionConfig",
    "QhIndependentMlpStateFusion",
    "QhIndependentMlpStateFusionConfig",
    "QhStateFusionConfig",
]
