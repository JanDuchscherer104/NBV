"""Regression tests for separated rollout return and RRI diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
import torch

from aria_nbv.app.panels import counterfactual_rollouts as rollout_panel


class _Labels:
    def __init__(self, metrics: dict[str, torch.Tensor]) -> None:
        self.metrics = metrics

    def selected(self, index: int) -> dict[str, torch.Tensor]:
        return {name: values[index] for name, values in self.metrics.items()}


def test_missing_root_gain_does_not_promote_target_rri_to_return() -> None:
    candidates = SimpleNamespace(mask_valid=torch.tensor([True, True]))
    step = SimpleNamespace(step_index=0, candidates=candidates)
    evaluated_step = SimpleNamespace(
        transition=SimpleNamespace(selected_valid_index=0, candidates=candidates),
        evaluation=SimpleNamespace(labels=_Labels({"target_rri": torch.tensor([0.3, 0.2])})),
    )
    evaluated = SimpleNamespace(
        result=SimpleNamespace(trajectories=[SimpleNamespace(steps=[step])]),
        step=lambda trajectory_index, step_index: evaluated_step,
    )

    row = rollout_panel._trajectory_metric_rows(evaluated).iloc[0]

    assert row["selected_target_rri"] == pytest.approx(0.3)  # noqa: S101
    assert pd.isna(row["selected_target_root_gain"])  # noqa: S101
    assert pd.isna(row["G_target"])  # noqa: S101
    assert row["top_target_rri"] == pytest.approx([0.3, 0.2])  # noqa: S101
    assert row["top_target_root_gain"] == []  # noqa: S101
