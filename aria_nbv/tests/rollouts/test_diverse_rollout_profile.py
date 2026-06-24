"""Tests for rollout generation profile TOMLs."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from aria_nbv.pose_generation import CandidateMixtureViewGeneratorConfig, CandidatePositionMode, ViewDirectionMode
from aria_nbv.rollouts import RolloutDatasetWriterConfig, RolloutRecipeConfig


def test_diverse_rollout_profile_emphasizes_radial_and_backtrack_families() -> None:
    config = RolloutDatasetWriterConfig.from_toml(_repo_root() / ".configs" / "build_rollouts_v1_diverse.toml")

    components = config.candidate_mixture.components
    component_by_name = {component.name: component for component in components}

    assert config.candidate_mixture.total_count == 48
    assert component_by_name["radial_towards_target_bearing"].view_mode is ViewDirectionMode.RADIAL_TOWARDS
    assert component_by_name["radial_away_target_bearing"].view_mode is ViewDirectionMode.RADIAL_AWAY
    assert component_by_name["revisit_backtrack"].position_mode is CandidatePositionMode.REVISIT_BACKTRACK

    radial_or_backtrack = sum(
        component.count
        for component in components
        if component.view_mode in {ViewDirectionMode.RADIAL_TOWARDS, ViewDirectionMode.RADIAL_AWAY}
        or component.position_mode is CandidatePositionMode.REVISIT_BACKTRACK
    )
    assert radial_or_backtrack / config.candidate_mixture.total_count >= 0.9


def test_diverse_rollout_profile_enables_sibling_diversity_controls() -> None:
    config = RolloutDatasetWriterConfig.from_toml(_repo_root() / ".configs" / "build_rollouts_v1_diverse.toml")

    assert {recipe.name for recipe in config.recipes} == {
        "random_valid_diverse",
        "oracle_lookahead_diverse",
        "temperature_softmax_diverse",
    }
    for recipe in config.recipes:
        assert recipe.branch_factor == 3
        assert recipe.beam_width == 3
        assert recipe.require_sibling_strategy_diversity is True
        assert recipe.min_sibling_distance_m > 0.0
        assert recipe.min_sibling_yaw_deg > 0.0


def test_diverse_rollout_profile_matches_named_code_presets() -> None:
    config = RolloutDatasetWriterConfig.from_toml(_repo_root() / ".configs" / "build_rollouts_v1_diverse.toml")

    candidate_preset = CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family()
    assert candidate_preset.base.model_dump() == config.candidate_mixture.base.model_dump()
    assert [component.model_dump() for component in candidate_preset.components] == [
        component.model_dump() for component in config.candidate_mixture.components
    ]

    recipe_preset = RolloutRecipeConfig.diverse_suite()
    assert [recipe.model_dump() for recipe in recipe_preset] == [recipe.model_dump() for recipe in config.recipes]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
