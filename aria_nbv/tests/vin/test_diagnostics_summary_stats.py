"""Tests for VIN diagnostic tensor summary helpers."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.vin.diagnostics.summary_stats import (
    finite_1d,
    ordinal_ranks,
    pearson_corr,
    quantile_stats,
    spearman_corr,
)


def test_finite_1d_detaches_flattens_and_filters_nonfinite_values() -> None:
    values = torch.tensor([[1.0, float("nan")], [float("inf"), 4.0]], requires_grad=True)

    finite = finite_1d(values)

    assert not finite.requires_grad
    assert finite.dtype == torch.float32
    torch.testing.assert_close(finite, torch.tensor([1.0, 4.0]))


def test_quantile_stats_matches_existing_summary_schema() -> None:
    stats = quantile_stats(torch.tensor([1.0, 2.0, 3.0, float("nan"), 5.0]))

    assert stats == pytest.approx(
        {
            "min": 1.0,
            "median": 2.5,
            "p95": 4.699999809265137,
            "mean": 2.75,
        }
    )


def test_quantile_stats_returns_none_for_no_finite_values() -> None:
    assert quantile_stats(torch.tensor([float("nan"), float("-inf")])) is None


def test_pearson_corr_handles_constant_or_short_vectors() -> None:
    assert pearson_corr(torch.tensor([1.0]), torch.tensor([2.0])) is None
    assert pearson_corr(torch.tensor([1.0, 1.0]), torch.tensor([2.0, 3.0])) is None


def test_pearson_corr_filters_each_vector_and_truncates_to_shorter_length() -> None:
    corr = pearson_corr(
        torch.tensor([1.0, float("nan"), 3.0, 4.0]),
        torch.tensor([10.0, 20.0]),
    )

    assert corr == pytest.approx(1.0)


def test_spearman_corr_uses_diagnostic_ordinal_rank_policy() -> None:
    x = torch.tensor([0.2, 0.1, 0.3])
    y = torch.tensor([2.0, 1.0, 3.0])

    torch.testing.assert_close(ordinal_ranks(x), torch.tensor([1.0, 0.0, 2.0]))
    assert spearman_corr(x, y) == pytest.approx(1.0)
