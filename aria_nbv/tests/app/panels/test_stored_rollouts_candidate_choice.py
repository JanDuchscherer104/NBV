"""Focused tests for pooled candidate-choice and transition plots."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import numpy as np
import pandas as pd

from aria_nbv.app.panels._stored_rollouts import candidate_generation


def _pooled_row(*, family: str, step_index: int, fraction: float) -> dict[str, object]:
    return {
        "metric": "policy_mass",
        "group_by": "position_strategy",
        "policy": "temperature_softmax",
        "horizon": 3,
        "branch_factor": 1,
        "beam_width": 1,
        "step_index": step_index,
        "family": family,
        "state_count": 4,
        "finite_state_count": 4,
        "missing_state_count": 0,
        "numerator": None,
        "denominator": None,
        "fraction": fraction,
    }


def test_pooled_candidate_selection_figure_shows_one_fraction_per_family_and_step() -> None:
    rows = [
        _pooled_row(family=family, step_index=step, fraction=fraction)
        for family, step, fraction in (
            ("forward_local · forward_rig", 0, 0.6),
            ("forward_local · forward_rig", 1, 0.4),
            ("lateral_target_bypass · target_point", 0, 0.4),
            ("lateral_target_bypass · target_point", 1, 0.6),
        )
    ]

    figure = candidate_generation._pooled_candidate_selection_figure(pd.DataFrame(rows))

    lines = [trace for trace in figure.data if trace.mode == "lines+markers"]
    assert len(lines) == 2
    assert {trace.name for trace in lines} == {
        "forward_local · forward_rig",
        "lateral_target_bypass · target_point",
    }
    forward = next(trace for trace in lines if trace.name.startswith("forward_local"))
    assert list(forward.x) == [1, 2]
    assert list(forward.y) == [0.6, 0.4]


def test_candidate_transition_figure_pairs_expected_and_realized_conditionals() -> None:
    rows = pd.DataFrame(
        [
            {
                "step_index": 1,
                "previous_family": previous,
                "next_family": following,
                "context_count": 8,
                "expected_policy_mass_mean": expected,
                "realized_rate": realized,
            }
            for previous, following, expected, realized in (
                ("forward", "forward", 0.7, 0.625),
                ("forward", "side", 0.3, 0.375),
                ("side", "forward", 0.4, 0.5),
                ("side", "side", 0.6, 0.5),
            )
        ]
    )

    figure = candidate_generation._candidate_transition_figure(rows)

    assert len(figure.data) == 2
    assert np.asarray(figure.data[0].z).tolist() == [[0.7, 0.3], [0.4, 0.6]]
    assert np.asarray(figure.data[1].z).tolist() == [[0.625, 0.375], [0.5, 0.5]]
    assert "acquisition 1" in str(figure.layout.title.text)
