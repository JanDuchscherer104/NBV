"""Unit contracts for modular A0/A1 finite-horizon state fusion."""

# ruff: noqa: S101

from __future__ import annotations

import pytest
import torch

from aria_nbv.vin.modules.qh_state_fusion import (
    QhCrossAttentionStateFusionConfig,
    QhIndependentMlpStateFusionConfig,
)


def _inputs() -> tuple[torch.Tensor, torch.Tensor]:
    torch.manual_seed(7)
    return torch.randn(2, 3, 4, 16), torch.randn(2, 3, 5, 16)


@pytest.mark.parametrize(
    "config",
    [QhIndependentMlpStateFusionConfig(), QhCrossAttentionStateFusionConfig(attention_heads=4)],
)
def test_qh_state_fusion_controls_share_shape_and_candidate_equivariance(config) -> None:
    queries, state = _inputs()
    torch.manual_seed(13)
    fusion = config.setup_target(hidden_dim=16, state_token_count=5, dropout=0.0).eval()
    permutation = torch.tensor([2, 0, 3, 1])

    expected = fusion(queries, state)
    actual = fusion(queries[:, :, permutation], state)

    assert expected.shape == queries.shape
    assert torch.allclose(actual, expected[:, :, permutation], atol=1e-6, rtol=1e-6)


@pytest.mark.parametrize(
    "config",
    [QhIndependentMlpStateFusionConfig(), QhCrossAttentionStateFusionConfig(attention_heads=4)],
)
def test_qh_state_fusion_duplicate_queries_have_identical_context(config) -> None:
    queries, state = _inputs()
    queries[:, :, 1] = queries[:, :, 0]
    torch.manual_seed(17)
    fusion = config.setup_target(hidden_dim=16, state_token_count=5, dropout=0.0).eval()

    output = fusion(queries, state)

    assert torch.equal(output[:, :, 0], output[:, :, 1])


@pytest.mark.parametrize(
    "config",
    [QhIndependentMlpStateFusionConfig(), QhCrossAttentionStateFusionConfig(attention_heads=4)],
)
def test_qh_state_fusion_candidate_query_rows_are_strictly_isolated(config) -> None:
    queries, state = _inputs()
    torch.manual_seed(18)
    fusion = config.setup_target(hidden_dim=16, state_token_count=5, dropout=0.0).eval()
    baseline = fusion(queries, state)
    changed_queries = queries.clone()
    changed_queries[:, :, 2] += 1000.0
    changed = fusion(changed_queries, state)
    unaffected = torch.tensor([0, 1, 3])

    assert torch.equal(changed[:, :, unaffected], baseline[:, :, unaffected])


def test_qh_a0_reads_every_named_state_token_without_candidate_interaction() -> None:
    queries, state = _inputs()
    torch.manual_seed(19)
    fusion = (
        QhIndependentMlpStateFusionConfig()
        .setup_target(
            hidden_dim=16,
            state_token_count=5,
            dropout=0.0,
        )
        .eval()
    )
    baseline = fusion(queries, state)

    for token_index in range(state.shape[-2]):
        changed = state.clone()
        changed[:, :, token_index] += 0.5
        assert not torch.equal(fusion(queries, changed), baseline)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (QhCrossAttentionStateFusionConfig(attention_heads=3), "divisible"),
        (QhIndependentMlpStateFusionConfig(), "token count"),
    ],
)
def test_qh_state_fusion_fails_closed_on_incompatible_contract(config, message: str) -> None:
    queries, state = _inputs()
    if isinstance(config, QhCrossAttentionStateFusionConfig):
        with pytest.raises(ValueError, match=message):
            config.setup_target(hidden_dim=16, state_token_count=5, dropout=0.0)
        return
    fusion = config.setup_target(hidden_dim=16, state_token_count=4, dropout=0.0)
    with pytest.raises(ValueError, match=message):
        fusion(queries, state)
