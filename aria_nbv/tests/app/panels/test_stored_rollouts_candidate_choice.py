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


def _factual_sequence_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "generation_cohort_id": cohort,
                "temperature": temperature,
                "rollout_row_id": rollout_row_id,
                "sequence": " → ".join(families),
                "sequence_families": families,
                "observed_steps": len(families),
                "horizon": 3,
                "completed_horizon": len(families) == 3,
                "terminal_cumulative_target_root_gain": gain,
            }
            for cohort, temperature, rollout_row_id, families, gain in (
                ("cohort-a", 0.5, 7, ("forward", "side", "forward"), 0.2),
                ("cohort-b", 2.0, 11, ("side", "forward"), 0.8),
            )
        ]
    )


def test_selected_family_trajectory_rows_and_figure_show_one_cell_per_factual_acquisition() -> None:
    rows, truncated = reconstruction_return._selected_family_trajectory_rows(_factual_sequence_rows())

    assert not truncated
    assert rows[["trace_label", "acquisition", "family"]].to_dict("records") == [
        {"trace_label": "T=0.5 · rollout 7 · cohort-a", "acquisition": 1, "family": "forward"},
        {"trace_label": "T=0.5 · rollout 7 · cohort-a", "acquisition": 2, "family": "side"},
        {"trace_label": "T=0.5 · rollout 7 · cohort-a", "acquisition": 3, "family": "forward"},
        {"trace_label": "T=2.0 · rollout 11 · cohort-b", "acquisition": 1, "family": "side"},
        {"trace_label": "T=2.0 · rollout 11 · cohort-b", "acquisition": 2, "family": "forward"},
    ]
    figure = reconstruction_return._selected_family_trajectory_figure(rows)

    assert np.asarray(figure.data[0].z).shape == (2, 3)
    assert "Factual selected family" in str(figure.layout.title.text)
    assert figure.layout.xaxis.title.text == "acquisition number (1 = first selected view)"


def test_selected_sequence_endpoint_figure_has_one_marker_per_factual_trajectory() -> None:
    figure = reconstruction_return._selected_sequence_endpoint_figure(_factual_sequence_rows())

    trace = figure.data[0]
    assert trace.mode == "markers"
    assert list(trace.x) == [0.5, 2.0]
    assert list(trace.y) == [0.2, 0.8]
    assert trace.error_x.array is None
    assert trace.error_x.arrayminus is None
    assert "exact rollout configuration" in str(figure.layout.title.text)
