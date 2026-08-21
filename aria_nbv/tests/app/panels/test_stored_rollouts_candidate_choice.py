"""Focused tests for candidate-choice and selected-sequence comparison plots."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import numpy as np
import pandas as pd

from aria_nbv.app.panels._stored_rollouts import candidate_generation, reconstruction_return


def _temporal_row(*, cohort: str, family: str, step_index: int, median: float) -> dict[str, object]:
    return {
        "metric": "policy_mass",
        "group_by": "position",
        "generation_cohort_id": cohort,
        "generation_cohort": "{}",
        "policy": "temperature_softmax",
        "temperature": 2.0,
        "horizon": 3,
        "branch_factor": 1,
        "beam_width": 1,
        "step_index": step_index,
        "family": family,
        "total_count": 4,
        "finite_count": 4,
        "missing_count": 0,
        "mean": median,
        "median": median,
        "q25": median - 0.05,
        "q75": median + 0.05,
    }


def test_candidate_selection_temporal_figure_keeps_cohorts_and_families_separate() -> None:
    rows = [
        _temporal_row(cohort=cohort, family=family, step_index=step, median=median)
        for cohort, family, step, median in (
            ("cohort-a", "forward", 0, 0.6),
            ("cohort-a", "forward", 1, 0.4),
            ("cohort-a", "side", 0, 0.4),
            ("cohort-a", "side", 1, 0.6),
            ("cohort-b", "forward", 0, 0.8),
        )
    ]

    figure = candidate_generation._candidate_selection_temporal_figure(pd.DataFrame(rows))

    lines = [trace for trace in figure.data if trace.mode == "lines+markers"]
    assert len(lines) == 3
    assert {trace.name.split(" · ")[0] for trace in lines} == {"forward", "side"}
    assert any("cohort-a" in trace.name for trace in lines)
    assert any("cohort-b" in trace.name for trace in lines)
    forward_a = next(trace for trace in lines if trace.name.startswith("forward · cohort-a"))
    assert list(forward_a.x) == [1, 2]
    assert list(forward_a.y) == [0.6, 0.4]


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


def test_candidate_sequence_return_figure_selects_highest_observed_sequences() -> None:
    summary = pd.DataFrame(
        [
            {
                "sequence": sequence,
                "rollout_count": count,
                "completed_count": completed,
                "finite_return_count": count,
                "terminal_return_median": median,
                "terminal_return_q25": median - 0.1,
                "terminal_return_q75": median + 0.1,
            }
            for sequence, count, completed, median in (
                ("forward → forward", 3, 3, 0.2),
                ("forward → side", 2, 2, 0.8),
                ("side → forward", 4, 3, 0.5),
            )
        ]
    )

    figure = reconstruction_return._candidate_sequence_return_figure(summary, max_sequences=2)

    trace = figure.data[0]
    assert list(trace.y) == ["side → forward", "forward → side"]
    assert list(trace.x) == [0.5, 0.8]
    assert list(trace.customdata[:, 0]) == [4.0, 2.0]
    assert "top 2" in str(figure.layout.title.text)
