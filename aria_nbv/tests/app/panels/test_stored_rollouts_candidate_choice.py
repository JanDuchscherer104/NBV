"""Focused tests for pooled candidate-choice and transition plots."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import inspect
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from aria_nbv.app.panels._stored_rollouts import candidate_generation, overview_topology, reconstruction_return
from aria_nbv.rollouts.inspection import _materialize_selection_family_union, candidate_target_view_evidence


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


@pytest.mark.parametrize(
    ("metric", "label"),
    [
        ("allocation_share", "candidate availability"),
        ("valid_share", "actor-valid support"),
        ("policy_mass", "policy mass"),
        ("selected_share", "realized selection"),
    ],
)
def test_pooled_candidate_selection_figure_labels_metric_and_support(metric: str, label: str) -> None:
    rows = pd.DataFrame(
        [
            {
                "family": "forward",
                "step_index": 0,
                "fraction": 0.5,
                "metric": metric,
                "state_count": 4,
                "finite_state_count": 3,
                "missing_state_count": 1,
                "numerator": 2,
                "denominator": 4,
            }
        ]
    )

    figure = candidate_generation._pooled_candidate_selection_figure(rows)

    assert figure.layout.yaxis.title.text == label
    assert all(
        field in figure.data[0].hovertemplate for field in ("state_count", "finite_state_count", "missing_state_count")
    )


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
    assert all(trace.visible is None or trace.visible is True for trace in figure.data)
    assert all(trace.zmin == 0 and trace.zmax == 1 for trace in figure.data)
    assert all("context_count" in trace.hovertemplate for trace in figure.data)
    assert np.asarray(figure.data[0].z).tolist() == [[0.7, 0.3], [0.4, 0.6]]
    assert np.asarray(figure.data[1].z).tolist() == [[0.625, 0.375], [0.5, 0.5]]
    assert "acquisition 1" in str(figure.layout.title.text)


def test_pairwise_correlation_accepts_two_components_and_reports_degenerate_support() -> None:
    frame = pd.DataFrame({"left": [1.0, 2.0, np.inf], "right": [2.0, 4.0, 8.0]})

    prepared = candidate_generation._prepare_pairwise_correlation(frame, ["left", "right"])

    assert prepared["has_finite_off_diagonal"] is True
    assert prepared["counts"].loc["left", "right"] == 2
    assert "n=2" in prepared["reasons"][("left", "right")]


def test_pairwise_correlation_fails_closed_without_two_finite_components() -> None:
    frame = pd.DataFrame({"left": [1.0, np.inf], "right": [np.nan, 2.0]})

    prepared = candidate_generation._prepare_pairwise_correlation(frame, ["left", "right"])

    assert prepared["has_finite_off_diagonal"] is False
    assert "need n>=2" in prepared["reasons"][("left", "right")]


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


def test_candidate_choice_vocabulary_help_describes_compatible_pooling(monkeypatch) -> None:
    help_text: dict[str, str] = {}
    rows = [
        {
            **_pooled_row(family="forward", step_index=0, fraction=1.0),
            "contract_id": "contract-a",
            "contract": "frozen",
            "profile": "rich",
            "temperature": 0.5,
            "generation_cohort_id": "cohort-a",
        }
    ]

    def selectbox(label, options, **kwargs):
        if "help" in kwargs:
            help_text[label] = kwargs["help"]
        return "position_strategy" if label == "Candidate evidence grouping" else list(options)[0]

    monkeypatch.setattr(candidate_generation.st, "selectbox", selectbox)
    monkeypatch.setattr(candidate_generation, "_render_complete_candidate_support", lambda *args, **kwargs: None)
    monkeypatch.setattr(candidate_generation, "candidate_selection_pooled_summary_rows", lambda *args, **kwargs: [])

    population = {
        "composition": {"position_strategy": []},
        "calibration": {"position_strategy": []},
        "collision": [],
        "sample": {"rows": [], "display_count": 0, "population_count": 0},
        "selection_dynamics": {"position_strategy": rows},
    }
    candidate_generation._render_candidate_population_evidence(SimpleNamespace(candidate_population=lambda: population))

    assert help_text["Candidate-choice vocabulary"] == (
        "Exact contract/profile/policy/H/B/beam controls stay fixed; compatible "
        "temperature/generation cohorts are pooled for the population view."
    )


def test_complete_candidate_choice_surface_is_explicit_and_names_all_quantities() -> None:
    """The heavy action is named for lineage/choice and advertises its complete metric surface."""

    source = inspect.getsource(candidate_generation._render_candidate_population_evidence)
    assert "Complete candidate-family lineage and choice" in source
    for quantity in ("allocation_share", "valid_share", "policy_mass", "selected_share"):
        assert quantity in source
    assert "expected_policy_mass_mean" in inspect.getsource(candidate_generation._candidate_transition_figure)
    assert "realized_rate" in inspect.getsource(candidate_generation._candidate_transition_figure)


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


def test_candidate_family_breakdown_requires_family_and_cohort_identity(monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(candidate_generation.st, "warning", warnings.append)

    missing = candidate_generation._require_family_cohort_columns(pd.DataFrame({"position": ["forward"]}), "Family")
    complete = candidate_generation._require_family_cohort_columns(
        pd.DataFrame({"family": ["forward"], "generation_cohort_id": ["cohort-a"]}), "Family"
    )

    assert missing.empty
    assert "missing family, generation_cohort_id" in warnings[0]
    assert complete.to_dict("records") == [{"family": "forward", "generation_cohort_id": "cohort-a"}]


def test_candidate_support_explanation_keeps_theory_and_inspection_owner() -> None:
    explanation = candidate_generation._candidate_population_explanation(
        "Question",
        "Population",
        "Metric",
        "Denominator",
        "Expected",
        "Warning",
        "inspection.candidate_direction_evidence",
        "actor-visible",
        candidate_generation.TheoryReferences(
            equation_ids=("action.angle_cap_transform",),
            term_ids=("finite-candidate-action-set",),
        ),
        external_references=(
            (
                "Candidate inspection contract",
                "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
            ),
        ),
    )

    assert explanation.theory is not None
    assert explanation.theory.equation_ids == ("action.angle_cap_transform",)
    assert explanation.theory.term_ids == ("finite-candidate-action-set",)
    assert explanation.external_references[0][1].endswith("aria_nbv/aria_nbv/rollouts/inspection.py")


def test_complete_candidate_support_renders_reducer_target_view_counts(monkeypatch) -> None:
    """The target-view reducer's persisted ``count`` must not break availability plots."""

    rows = candidate_target_view_evidence(
        [
            {
                "generation_cohort_id": "cohort-a",
                "scene": "scene-a",
                "rollout_row_id": "rollout-a",
                "step_row_id": "step-a",
                "target_distance_m": 1.0,
                "actor_action": True,
            },
            {
                "generation_cohort_id": "cohort-a",
                "scene": "scene-a",
                "rollout_row_id": "rollout-a",
                "step_row_id": "step-a",
                "target_distance_m": None,
                "actor_action": True,
            },
        ]
    )
    assert rows and "count" in rows[0]

    plots = []
    monkeypatch.setattr(candidate_generation, "_render_plot", lambda figure, *_args, **_kwargs: plots.append(figure))
    monkeypatch.setattr(candidate_generation, "_download_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(candidate_generation.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(candidate_generation.st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(candidate_generation.st, "expander", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(
        candidate_generation.st,
        "selectbox",
        lambda _label, options, **_kwargs: list(options)[0],
    )

    candidate_generation._render_complete_candidate_support({"target_view": rows}, evidence_role="actor-visible")

    availability = next(
        figure for figure in plots if figure.layout.title.text == "Target-view availability and missingness"
    )
    assert availability.data
    assert availability.layout.yaxis.title.text == "candidate evidence rows [count]"
    assert {trace.name for trace in availability.data} == {"finite_count", "missing_count"}
    assert sum(sum(float(value) for value in trace.y) for trace in availability.data) > 0


def test_rollout_scientific_reference_owners_and_count_units_are_current() -> None:
    sources = {
        "candidate_generation": inspect.getsource(candidate_generation),
        "overview_topology": inspect.getsource(overview_topology),
        "reconstruction_return": inspect.getsource(reconstruction_return),
    }
    combined = "\n".join(sources.values())
    assert "entity.target_reward" in combined
    assert "entity.target_rri_marginal" in combined
    assert "entity.rri_e" not in combined
    assert "rl.reward_target" not in combined
    assert "candidate evidence rows [count]" in sources["candidate_generation"]
