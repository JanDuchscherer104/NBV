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
used by backup and ranking. Both live in a content-addressed support artifact
whose provenance is either training-fitted or physically predeclared. A
different discretization or construction population is a different value model
even when tensor shapes match. Validation/test-derived support is structurally
inadmissible; legacy fixed edges can be inspected but cannot enter a scientific
bundle.

CORAL is an ordinal ablation, not evidence that metric distances between
classes are learned. The continuous interpretation comes only from the fixed
representatives supplied by the experiment. Quantile/distributional value
models remain a separate decoder family because they model return uncertainty
rather than an ordinal discretization of one scalar target.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Self, TypeAlias

import torch
from pydantic import Field, model_validator
from torch import Tensor, nn

from ...utils import BaseConfig, TargetConfig
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
    """``Tensor["B S N K-1", float32]`` cumulative ordinal logits."""

    bin_edges: Tensor
    """``Tensor["K-1", float32]`` fitted-Q label boundaries."""

    bin_values: Tensor
    """``Tensor["K", float32]`` continuous-Q class representatives."""


@dataclass(frozen=True, slots=True)
class QhDecodedValue:
    """One decoder's scalar value and optional objective-specific payload.

    ``conditional_q`` always has the candidate-aligned leading shape and is the
    only value consumed by Bellman backup or online ranking. ``coral`` exists
    only for the ordinal training objective; regression leaves it ``None``.
    """

    conditional_q: Tensor
    """``Tensor["...", float32]`` conditional value in additive fitted-Q units."""

    coral: QhCoralAuxiliary | None = None
    """Ordinal training payload, or ``None`` for direct regression."""


class QhRegressionValueDecoderConfig(TargetConfig["QhRegressionValueDecoder"]):
    """Configure the canonical direct continuous-Q regression decoder."""

    kind: Literal["regression"] = "regression"
    """Discriminator persisted in scorer and bundle configuration."""

    @property
    def target_type(self) -> type["QhRegressionValueDecoder"]:
        """Return the runtime direct-regression decoder class."""

        return QhRegressionValueDecoder


def _support_artifact_digest(payload: dict[str, Any]) -> str:
    """Return the SHA-256 identity of one canonical CORAL support artifact."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_numeric_support(bin_edges: tuple[float, ...], bin_values: tuple[float, ...]) -> None:
    """Require one finite monotone ordinal-to-continuous support."""

    if len(bin_values) != len(bin_edges) + 1:
        raise ValueError("CORAL Q bin_values must contain exactly one more entry than bin_edges.")
    if not all(math.isfinite(value) for value in (*bin_edges, *bin_values)):
        raise ValueError("CORAL Q bin edges and representatives must be finite.")
    if any(right <= left for left, right in zip(bin_edges, bin_edges[1:], strict=False)):
        raise ValueError("CORAL Q bin_edges must be strictly increasing.")
    if any(right <= left for left, right in zip(bin_values, bin_values[1:], strict=False)):
        raise ValueError("CORAL Q bin_values must be strictly increasing.")
    for lower, edge, upper in zip(bin_values[:-1], bin_edges, bin_values[1:], strict=True):
        if not lower <= edge <= upper:
            raise ValueError("Every CORAL Q bin edge must lie between its adjacent representatives.")


class _QhCoralSupportArtifact(BaseConfig):
    """Bind continuous ordinal support to its leakage-relevant construction facts."""

    source_population_digest: str = Field(min_length=1)
    """Digest of the population contract for which this support was declared."""

    ordered_input_digest: str = Field(min_length=1)
    """Digest of ordered fitting rows or ordered physical-rule inputs."""

    bin_edges: tuple[float, ...] = Field(min_length=1)
    """Strictly increasing fitted-Q label boundaries."""

    bin_values: tuple[float, ...] = Field(min_length=2)
    """Strictly increasing continuous-Q class representatives."""

    return_units: Literal["additive_root_gain_v1"] = "additive_root_gain_v1"
    """Physical value semantics shared by labels, representatives, and decoded Q."""

    artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    """SHA-256 over every other field in this support artifact."""

    @model_validator(mode="after")
    def _validate_artifact(self) -> Self:
        """Reject malformed support or provenance altered without re-addressing it."""

        _validate_numeric_support(self.bin_edges, self.bin_values)
        expected = _support_artifact_digest(self.model_dump(exclude={"artifact_digest"}))
        if self.artifact_digest != expected:
            raise ValueError("CORAL support artifact_digest does not match its construction payload.")
        return self


class QhTrainFittedCoralSupport(_QhCoralSupportArtifact):
    """Support fitted only from a frozen ordered training population."""

    provenance_kind: Literal["train_fitted_v1"] = "train_fitted_v1"
    """Promotable support-provenance discriminator."""

    construction_method: Literal["empirical_quantiles_v1"] = "empirical_quantiles_v1"
    """Predeclared deterministic fitting method applied to the ordered targets."""

    split_role: Literal["train"] = "train"
    """Closed leakage boundary; validation and test targets are never admissible."""

    @classmethod
    def create(
        cls,
        *,
        source_population_digest: str,
        ordered_input_digest: str,
        bin_edges: tuple[float, ...],
        bin_values: tuple[float, ...],
    ) -> Self:
        """Construct a self-addressed training-fitted support artifact."""

        normalized_edges = tuple(float(value) for value in bin_edges)
        normalized_values = tuple(float(value) for value in bin_values)
        payload = {
            "source_population_digest": source_population_digest,
            "ordered_input_digest": ordered_input_digest,
            "bin_edges": normalized_edges,
            "bin_values": normalized_values,
            "return_units": "additive_root_gain_v1",
            "provenance_kind": "train_fitted_v1",
            "construction_method": "empirical_quantiles_v1",
            "split_role": "train",
        }
        return cls(**payload, artifact_digest=_support_artifact_digest(payload))


class QhPredeclaredPhysicalCoralSupport(_QhCoralSupportArtifact):
    """Support fixed by a physical rule before empirical target inspection."""

    provenance_kind: Literal["predeclared_physical_v1"] = "predeclared_physical_v1"
    """Promotable support-provenance discriminator."""

    construction_method: Literal["predeclared_physical_rule_v1"] = "predeclared_physical_rule_v1"
    """Construction family that is independent of observed target outcomes."""

    split_role: Literal["not_applicable_predeclared"] = "not_applicable_predeclared"
    """Explicit statement that no empirical dataset split selected the support."""

    physical_rule: str = Field(min_length=1)
    """Versioned rule identifier from which boundaries and representatives derive."""

    @classmethod
    def create(
        cls,
        *,
        source_population_digest: str,
        ordered_input_digest: str,
        physical_rule: str,
        bin_edges: tuple[float, ...],
        bin_values: tuple[float, ...],
    ) -> Self:
        """Construct a self-addressed physically predeclared support artifact."""

        normalized_edges = tuple(float(value) for value in bin_edges)
        normalized_values = tuple(float(value) for value in bin_values)
        payload = {
            "source_population_digest": source_population_digest,
            "ordered_input_digest": ordered_input_digest,
            "bin_edges": normalized_edges,
            "bin_values": normalized_values,
            "return_units": "additive_root_gain_v1",
            "provenance_kind": "predeclared_physical_v1",
            "construction_method": "predeclared_physical_rule_v1",
            "split_role": "not_applicable_predeclared",
            "physical_rule": physical_rule,
        }
        return cls(**payload, artifact_digest=_support_artifact_digest(payload))


QhCoralSupportProvenance: TypeAlias = Annotated[
    QhTrainFittedCoralSupport | QhPredeclaredPhysicalCoralSupport,
    Field(discriminator="provenance_kind"),
]
"""Closed publishable CORAL support-provenance union."""


class QhLegacyFixedCoralSupport(BaseConfig):
    """Ambiguous fixed support admitted only for explicit historical inspection."""

    provenance_kind: Literal["legacy_fixed_support_inspection_only_v1"] = "legacy_fixed_support_inspection_only_v1"
    """Non-publishable legacy discriminator."""

    bin_edges: tuple[float, ...] = Field(min_length=1)
    """Historical label boundaries with no verified construction provenance."""

    bin_values: tuple[float, ...] = Field(min_length=2)
    """Historical representatives with no verified construction provenance."""


QhCoralSupportConfig: TypeAlias = Annotated[
    QhTrainFittedCoralSupport | QhPredeclaredPhysicalCoralSupport | QhLegacyFixedCoralSupport,
    Field(discriminator="provenance_kind"),
]
"""CORAL support accepted by the decoder, including non-publishable history."""


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

    Notes:
        ``support`` is the single owner of boundaries, representatives, source
        population, split role, construction method, return units, and artifact
        digest. ``train_fitted_v1`` is closed to training rows and
        ``predeclared_physical_v1`` is fixed before empirical outcomes. The
        legacy discriminator exists only to read historical configurations and
        is rejected by bundle publication, warm start, and inference.
    """

    kind: Literal["coral"] = "coral"
    """Discriminator persisted in scorer and bundle configuration."""

    support: QhCoralSupportConfig
    """Versioned support plus its construction provenance and artifact identity."""

    preinit_bias: bool = True
    """Use the upstream CORAL threshold-bias initialization."""

    @property
    def target_type(self) -> type["QhCoralValueDecoder"]:
        """Return the runtime CORAL decoder class."""

        return QhCoralValueDecoder

    @property
    def bin_edges(self) -> tuple[float, ...]:
        """Return the support's fitted-Q label boundaries."""

        return self.support.bin_edges

    @property
    def bin_values(self) -> tuple[float, ...]:
        """Return the support's continuous-Q representatives."""

        return self.support.bin_values

    @model_validator(mode="after")
    def _validate_bins(self) -> "QhCoralValueDecoderConfig":
        """Require one coherent finite ordinal-to-continuous value support."""

        if isinstance(self.support, QhLegacyFixedCoralSupport):
            _validate_numeric_support(self.support.bin_edges, self.support.bin_values)
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

    def require_publishable_support(self) -> None:
        """Reject historical fixed support lacking construction provenance."""

        if isinstance(self.config.support, QhLegacyFixedCoralSupport):
            raise ValueError("Legacy CORAL fixed support is inspection-only and cannot enter a scientific bundle.")

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
    "QhCoralSupportConfig",
    "QhCoralSupportProvenance",
    "QhCoralValueDecoder",
    "QhCoralValueDecoderConfig",
    "QhDecodedValue",
    "QhLegacyFixedCoralSupport",
    "QhPredeclaredPhysicalCoralSupport",
    "QhRegressionValueDecoder",
    "QhRegressionValueDecoderConfig",
    "QhTrainFittedCoralSupport",
    "QhValueDecoderConfig",
]
