"""Focused tests for pooled candidate-choice and transition plots."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import numpy as np
import pandas as pd

from aria_nbv.app.panels._stored_rollouts import candidate_generation
from aria_nbv.rollouts.inspection import _materialize_selection_family_union


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


def test_candidate_choice_controls_pool_all_temperatures_and_cohorts(monkeypatch) -> None:
    rows = pd.DataFrame(
        [
            {
                "contract_id": contract,
                "contract": "frozen",
                "profile": "rich",
                "policy": "temperature_softmax",
                "temperature": temperature,
                "generation_cohort_id": f"cohort-{temperature}",
                "horizon": 8,
                "branch_factor": 1,
                "beam_width": 1,
            }
            for contract, temperature in (("contract-a", 0.5), ("contract-b", 2.0))
        ]
    )
    monkeypatch.setattr(candidate_generation.st, "selectbox", lambda *_args, **_kwargs: "contract-a")

    selected, controls = candidate_generation._select_candidate_choice_controls(rows, group_by="position_strategy")

    assert controls == {"contract_id": "contract-a"}
    assert selected["temperature"].tolist() == [0.5]
    assert selected["generation_cohort_id"].tolist() == ["cohort-0.5"]


def test_pooled_candidate_choice_keeps_absent_family_as_zero_across_temperatures() -> None:
    rows = []
    for temperature, family in ((0.5, "forward"), (2.0, "side")):
        rows.append(
            {
                "group_by": "position_strategy",
                "policy": "temperature_softmax",
                "contract_id": "contract-a",
                "profile": "rich",
                "temperature": temperature,
                "generation_cohort_id": f"cohort-{temperature}",
                "rollout_row_id": int(temperature * 10),
                "step_row_id": int(temperature * 10),
                "step_index": 0,
                "family": family,
                "family_candidate_count": 60,
                "candidate_count": 60,
                "family_actor_valid_count": 60,
                "actor_valid_count": 60,
                "family_selected_count": 1,
                "policy_mass": 1.0,
            }
        )

    union = _materialize_selection_family_union(rows)
    assert sum(int(row["family_candidate_count"]) == 0 for row in union) == 2
    pooled = pd.DataFrame(candidate_generation.candidate_selection_pooled_summary_rows(rows, metric="allocation_share"))

    assert set(pooled["family"]) == {"forward", "side"}
    assert pooled["fraction"].tolist() == [0.5, 0.5]
