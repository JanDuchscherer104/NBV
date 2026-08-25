"""Contracts for modular finite-horizon scalar-value decoders."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch
from pydantic import ValidationError

from aria_nbv.vin.modules.qh_value_decoders import (
    QhCoralValueDecoderConfig,
    QhLegacyFixedCoralSupport,
    QhPredeclaredPhysicalCoralSupport,
    QhRegressionValueDecoderConfig,
    QhTrainFittedCoralSupport,
)


def _features() -> torch.Tensor:
    torch.manual_seed(23)
    return torch.randn(2, 3, 4, 8, requires_grad=True)


def _support(
    *,
    bin_edges: tuple[float, ...] = (-0.5, 0.5),
    bin_values: tuple[float, ...] = (-1.0, 0.0, 1.0),
) -> QhPredeclaredPhysicalCoralSupport:
    return QhPredeclaredPhysicalCoralSupport.create(
        source_population_digest="population-v1",
        ordered_input_digest="physical-rule-inputs-v1",
        physical_rule="symmetric-root-gain-support-v1",
        bin_edges=bin_edges,
        bin_values=bin_values,
    )


def test_regression_decoder_returns_only_scalar_conditional_q() -> None:
    features = _features()
    decoder = QhRegressionValueDecoderConfig().setup_target(
        in_dim=8,
        hidden_dim=16,
        dropout=0.0,
    )

    output = decoder(features)
    output.conditional_q.sum().backward()

    assert output.conditional_q.shape == features.shape[:-1]
    assert output.conditional_q.dtype is torch.float32
    assert output.coral is None
    assert features.grad is not None
    assert bool(features.grad.abs().sum() > 0)


def test_coral_decoder_returns_scalar_q_and_training_thresholds() -> None:
    features = _features()
    config = QhCoralValueDecoderConfig(
        support=_support(),
        preinit_bias=False,
    )
    decoder = config.setup_target(in_dim=8, hidden_dim=16, dropout=0.0)

    output = decoder(features)
    assert output.coral is not None
    output.conditional_q.sum().backward()

    assert output.conditional_q.shape == features.shape[:-1]
    assert output.coral.logits.shape == (*features.shape[:-1], 2)
    assert output.coral.bin_edges.tolist() == [-0.5, 0.5]
    assert output.coral.bin_values.tolist() == [-1.0, 0.0, 1.0]
    assert bool((output.conditional_q >= -1.0).all())
    assert bool((output.conditional_q <= 1.0).all())
    assert features.grad is not None
    assert bool(features.grad.abs().sum() > 0)
    state = decoder.state_dict()
    assert torch.equal(state["bin_edges"], torch.tensor([-0.5, 0.5]))
    assert torch.equal(state["bin_values"], torch.tensor([-1.0, 0.0, 1.0]))


def test_coral_decoder_is_equivariant_to_candidate_row_permutation() -> None:
    features = _features().detach()
    decoder = QhCoralValueDecoderConfig(
        support=_support(),
        preinit_bias=False,
    ).setup_target(in_dim=8, hidden_dim=16, dropout=0.0)
    permutation = torch.tensor([2, 0, 3, 1])

    expected = decoder(features)
    actual = decoder(features[:, :, permutation])

    assert expected.coral is not None
    assert actual.coral is not None
    assert torch.allclose(actual.conditional_q, expected.conditional_q[:, :, permutation])
    assert torch.allclose(actual.coral.logits, expected.coral.logits[:, :, permutation])


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (
            {"bin_edges": (0.0,), "bin_values": (-1.0, 0.0, 1.0)},
            "exactly one more",
        ),
        (
            {"bin_edges": (0.0, 0.0), "bin_values": (-1.0, 0.0, 1.0)},
            "strictly increasing",
        ),
        (
            {"bin_edges": (0.0, 1.0), "bin_values": (-1.0, 0.0, 0.0)},
            "strictly increasing",
        ),
        (
            {"bin_edges": (-2.0, 0.5), "bin_values": (-1.0, 0.0, 1.0)},
            "adjacent representatives",
        ),
        (
            {"bin_edges": (float("nan"), 0.5), "bin_values": (-1.0, 0.0, 1.0)},
            "finite",
        ),
    ],
)
def test_coral_config_rejects_ambiguous_or_nonfinite_support(
    config: dict[str, tuple[float, ...]],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _support(**config)


def test_coral_support_artifact_rejects_digest_tampering_and_validation_split() -> None:
    payload = _support().model_dump()
    payload["bin_edges"] = (-0.25, 0.5)
    with pytest.raises(ValidationError, match="artifact_digest"):
        QhPredeclaredPhysicalCoralSupport.model_validate(payload)

    train_payload = QhTrainFittedCoralSupport.create(
        source_population_digest="train-population-v1",
        ordered_input_digest="ordered-train-targets-v1",
        bin_edges=(-0.5, 0.5),
        bin_values=(-1.0, 0.0, 1.0),
    ).model_dump()
    train_payload["split_role"] = "validation"
    with pytest.raises(ValidationError, match="train"):
        QhTrainFittedCoralSupport.model_validate(train_payload)


def test_legacy_coral_support_runs_for_inspection_but_fails_publication_gate() -> None:
    decoder = QhCoralValueDecoderConfig(
        support=QhLegacyFixedCoralSupport(
            bin_edges=(-0.5, 0.5),
            bin_values=(-1.0, 0.0, 1.0),
        )
    ).setup_target(in_dim=8, hidden_dim=16, dropout=0.0)

    assert torch.isfinite(decoder(_features()).conditional_q).all()
    with pytest.raises(ValueError, match="inspection-only"):
        decoder.require_publishable_support()
