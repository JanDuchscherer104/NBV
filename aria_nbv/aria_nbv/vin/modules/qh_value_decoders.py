r"""Modular scalar-value decoders for finite-horizon candidate features.

The finite-horizon scorer first builds one candidate-state feature vector per
materialized action. This module owns only the terminal map from that shared
feature space to conditional value. It deliberately does not own feasibility,
hard action masks, Bellman targets, or candidate interaction.

Every decoder returns a scalar ``conditional_q`` in the fitted-Q target's
continuous units, so Lightning backup and online selection have one invariant
meaning. The direct-regression decoder predicts that scalar. The CORAL decoder
instead predicts cumulative ordinal thresholds and differentiably decodes
their repaired class probabilities through fixed, monotone Q representatives.
Its bin edges define training labels; its representatives define the scalar
used by backup and ranking. Both are persisted scorer configuration, because a
different discretization is a different value model even when tensor shapes
match.

CORAL is an ordinal ablation, not evidence that metric distances between
classes are learned. The continuous interpretation comes only from the fixed
representatives supplied by the experiment. Quantile/distributional value
models remain a separate decoder family because they model return uncertainty
rather than an ordinal discretization of one scalar target.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Literal, TypeAlias

import torch
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import TargetConfig
from ..ordinal import CoralLayer, coral_logits_to_prob


@dataclass(frozen=True, slots=True)
class QhCoralAuxiliary:
    """Training-only CORAL tensors attached to a scalar value prediction.

    Attributes:
        logits: ``Tensor["B S N K-1", float32]`` cumulative logits for
            :math:`P(y > k)`. Candidate order matches ``conditional_q``.
        bin_edges: ``Tensor["K-1", float32]`` strictly increasing boundaries
            used to map continuous fitted-Q targets to ordinal labels via
            ``torch.bucketize``. These edges never mask or rank actions.
        bin_values: ``Tensor["K", float32]`` strictly increasing continuous-Q
            representatives used to decode class marginals. Lightning uses
            the outer representatives only for support-saturation diagnostics.
    """

    logits: Tensor
    bin_edges: Tensor
    bin_values: Tensor


@dataclass(frozen=True, slots=True)
class QhDecodedValue:
    """One decoder's scalar value and optional objective-specific payload.

    ``conditional_q`` always has the candidate-aligned leading shape and is the
    only value consumed by Bellman backup or online ranking. ``coral`` exists
    only for the ordinal training objective; regression leaves it ``None``.
    """

    conditional_q: Tensor
    coral: QhCoralAuxiliary | None = None


class QhRegressionValueDecoderConfig(TargetConfig["QhRegressionValueDecoder"]):
    """Configure the canonical direct continuous-Q regression decoder."""

    kind: Literal["regression"] = "regression"
    """Discriminator persisted in scorer and bundle configuration."""

    @property
    def target_type(self) -> type["QhRegressionValueDecoder"]:
        """Return the runtime direct-regression decoder class."""

        return QhRegressionValueDecoder


class QhCoralValueDecoderConfig(TargetConfig["QhCoralValueDecoder"]):
    r"""Configure a fixed-support CORAL decoder for continuous fitted-Q targets.

    For ``K`` ordered classes, ``bin_edges`` contains ``K-1`` boundaries and
    ``bin_values`` contains ``K`` continuous representatives. A target
    :math:`y` is assigned ``bucketize(y, edges)`` and trained with standard
    CORAL cumulative binary cross-entropy. At inference, repaired class
    probabilities :math:`p_k` decode to
    :math:`Q^{cond}=\sum_k p_k u_k` using the fixed representatives ``u_k``.

    Edge and representative identity is part of the checkpoint manifest. The
    outer classes remain open-ended, but their decoded values saturate at the
    first and last representatives; experiments must therefore report target
    support and saturation rather than interpreting ordinal bins as calibrated
    uncertainty.
    """

    kind: Literal["coral"] = "coral"
    """Discriminator persisted in scorer and bundle configuration."""

    bin_edges: tuple[float, ...] = Field(min_length=1)
    """Strictly increasing ``K-1`` fitted-Q label boundaries."""

    bin_values: tuple[float, ...] = Field(min_length=2)
    """Strictly increasing ``K`` continuous Q representatives."""

    preinit_bias: bool = True
    """Use the upstream CORAL threshold-bias initialization."""

    @property
    def target_type(self) -> type["QhCoralValueDecoder"]:
        """Return the runtime CORAL decoder class."""

        return QhCoralValueDecoder

    @model_validator(mode="after")
    def _validate_bins(self) -> "QhCoralValueDecoderConfig":
        """Require one coherent finite ordinal-to-continuous value support."""

        if len(self.bin_values) != len(self.bin_edges) + 1:
            raise ValueError("CORAL Q bin_values must contain exactly one more entry than bin_edges.")
        if not all(math.isfinite(value) for value in (*self.bin_edges, *self.bin_values)):
            raise ValueError("CORAL Q bin edges and representatives must be finite.")
        if any(right <= left for left, right in zip(self.bin_edges, self.bin_edges[1:], strict=False)):
            raise ValueError("CORAL Q bin_edges must be strictly increasing.")
        if any(right <= left for left, right in zip(self.bin_values, self.bin_values[1:], strict=False)):
            raise ValueError("CORAL Q bin_values must be strictly increasing.")
        for lower, edge, upper in zip(
            self.bin_values[:-1],
            self.bin_edges,
            self.bin_values[1:],
            strict=True,
        ):
            if not lower <= edge <= upper:
                raise ValueError("Every CORAL Q bin edge must lie between its adjacent representatives.")
        return self


QhValueDecoderConfig: TypeAlias = Annotated[
    QhRegressionValueDecoderConfig | QhCoralValueDecoderConfig,
    Field(discriminator="kind"),
]
"""Persisted union of terminal scalar-Q decoder configurations."""


def _decoder_trunk(in_dim: int, hidden_dim: int, dropout: float) -> nn.Sequential:
    """Build the shared per-row MLP used by both decoder families."""

    return nn.Sequential(
        nn.Linear(int(in_dim), int(hidden_dim)),
        nn.GELU(),
        nn.Dropout(float(dropout)),
    )


class QhRegressionValueDecoder(nn.Module):
    """Decode shared candidate-state features by direct scalar regression.

    This is the canonical decoder because its output and Huber target already
    share the additive root-gain return units required by Bellman recursion.
    It adds no bin support, ordinal interpretation, or return-distribution
    hypothesis to the representation comparison.
    """

    def __init__(
        self,
        config: QhRegressionValueDecoderConfig,
        *,
        in_dim: int,
        hidden_dim: int,
        dropout: float,
    ) -> None:
        """Construct the canonical MLP-plus-linear continuous-Q head."""

        super().__init__()
        self.config = config
        self.trunk = _decoder_trunk(in_dim, hidden_dim, dropout)
        self.output = nn.Linear(int(hidden_dim), 1)

    def forward(self, features: Tensor) -> QhDecodedValue:
        """Return direct ``Tensor["...", float32]`` conditional-Q values."""

        return QhDecodedValue(conditional_q=self.output(self.trunk(features)).squeeze(-1))


class QhCoralValueDecoder(nn.Module):
    """Decode shared features through cumulative ordinal Q thresholds.

    CORAL shares one projection across thresholds and learns ordered-rank
    evidence for a discretized scalar target. The runtime still diagnoses
    adjacent cumulative-probability violations and repairs negative marginal
    class mass before decoding, because neither ranking nor Bellman backup may
    consume an invalid probability vector. This repair does not make the
    threshold probabilities calibrated; that remains an evaluation question.
    """

    def __init__(
        self,
        config: QhCoralValueDecoderConfig,
        *,
        in_dim: int,
        hidden_dim: int,
        dropout: float,
    ) -> None:
        """Construct the per-row MLP, CORAL layer, and fixed Q support."""

        super().__init__()
        self.config = config
        self.trunk = _decoder_trunk(in_dim, hidden_dim, dropout)
        self.coral = CoralLayer(
            in_dim=int(hidden_dim),
            num_classes=len(config.bin_values),
            preinit_bias=bool(config.preinit_bias),
        )
        self.register_buffer("bin_edges", torch.tensor(config.bin_edges, dtype=torch.float32), persistent=True)
        self.register_buffer("bin_values", torch.tensor(config.bin_values, dtype=torch.float32), persistent=True)

    def validate_configured_support(self) -> None:
        """Reject persisted ordinal support that disagrees with configuration.

        ``bin_edges`` and ``bin_values`` are persistent buffers because they
        helped define the training labels and the scalar decode, respectively.
        Loading a same-shaped state dictionary can otherwise overwrite support
        constructed from the manifest without a PyTorch shape error. Bundle
        publication, warm start, and inference therefore call this method
        after reconstruction or state loading so the manifest-advertised
        ordinal experiment remains identical to the executable decoder.
        """

        expected_edges = torch.tensor(self.config.bin_edges, dtype=self.bin_edges.dtype, device=self.bin_edges.device)
        expected_values = torch.tensor(
            self.config.bin_values,
            dtype=self.bin_values.dtype,
            device=self.bin_values.device,
        )
        if not torch.equal(self.bin_edges, expected_edges):
            raise ValueError("Persisted CORAL Q bin edges do not match the scorer configuration.")
        if not torch.equal(self.bin_values, expected_values):
            raise ValueError("Persisted CORAL Q bin values do not match the scorer configuration.")

    def forward(self, features: Tensor) -> QhDecodedValue:
        r"""Return ordinal logits and their continuous conditional-Q expectation.

        The repaired marginal probabilities are used only to form
        :math:`\sum_k p_k u_k`. This scalar has the same fitted-Q units as the
        regression decoder and is therefore safe for the unchanged backup and
        hard-masked ranking paths. The attached threshold logits retain the
        standard CORAL loss without a second scorer forward pass.
        """

        logits = self.coral(self.trunk(features))
        probabilities = coral_logits_to_prob(logits)
        values = self.bin_values.to(device=probabilities.device, dtype=probabilities.dtype)
        conditional_q = (probabilities * values).sum(dim=-1)
        return QhDecodedValue(
            conditional_q=conditional_q,
            coral=QhCoralAuxiliary(
                logits=logits,
                bin_edges=self.bin_edges,
                bin_values=self.bin_values,
            ),
        )


__all__ = [
    "QhCoralAuxiliary",
    "QhCoralValueDecoder",
    "QhCoralValueDecoderConfig",
    "QhDecodedValue",
    "QhRegressionValueDecoder",
    "QhRegressionValueDecoderConfig",
    "QhValueDecoderConfig",
]
