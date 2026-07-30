"""Candidate-generation presentation contracts."""

# ruff: noqa: S101

from __future__ import annotations

import pandas as pd

from aria_nbv.app.panels._stored_rollouts import candidate_generation


def test_scientific_composition_uses_only_state_then_scene_macro_evidence() -> None:
    rows = pd.DataFrame(
        [
            {
                "population": "sampled",
                "aggregation_level": "state",
                "family_dimension": "strategy",
                "family": "forward_rig",
                "mean_state_family_share": 1.0,
            },
            {
                "population": "sampled",
                "aggregation_level": "cohort_scene_macro",
                "family_dimension": "strategy",
                "family": "forward_rig",
                "mean_state_family_share": 0.5,
            },
            {
                "population": "actor_valid",
                "aggregation_level": "cohort_scene_macro",
                "family_dimension": "strategy",
                "family": "forward_rig",
                "mean_state_family_share": 0.75,
            },
            {
                "population": "sampled",
                "aggregation_level": "cohort_scene_macro",
                "family_dimension": "strategy",
                "family": "target_facing",
                "mean_state_family_share": 0.5,
            },
        ]
    )

    figure = candidate_generation._scientific_composition_figure(rows)

    assert [trace.name for trace in figure.data] == ["View · Forward Rig", "View · Target Facing"]
    assert [trace.y[0] for trace in figure.data] == [0.5, 0.5]
    assert figure.layout.title.text == "State-Then-Scene Macro Candidate Composition"
    assert figure.layout.yaxis.title.text == "Mean Within-State Candidate Share"


def test_pooled_composition_is_explicitly_descriptive_stored_mass() -> None:
    rows = pd.DataFrame(
        {
            "dimension": ["strategy"],
            "family": ["forward_rig"],
            "sampled_fraction": [1.0],
        }
    )

    figure = candidate_generation._composition_figure(rows)

    assert figure.layout.title.text == "Descriptive Stored-Mass Characterization"
    assert figure.layout.yaxis.title.text == "Pooled Share of Stored Candidates"
