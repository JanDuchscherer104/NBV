"""Tests for rollout generation profile TOMLs."""

# ruff: noqa: S101

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig, RolloutRecipeConfig
from aria_nbv.pose_generation import CandidateMixtureViewGeneratorConfig, CandidatePositionMode, ViewDirectionMode
from aria_nbv.rollouts import CounterfactualPoseGeneratorConfig, RolloutPolicySpec


def test_replay_and_recipe_configs_each_have_one_policy_field() -> None:
    assert set(CounterfactualPoseGeneratorConfig.model_fields) == {
        "candidate_config",
        "policy",
        "log_timing",
        "verbosity",
        "is_debug",
    }
    assert set(RolloutRecipeConfig.model_fields) == {"name", "policy"}


def test_legacy_flat_rollout_policy_fields_are_rejected() -> None:
    """Canonical configs compose one policy object without a legacy facade."""

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CounterfactualPoseGeneratorConfig(horizon=2)
    with pytest.raises(ValidationError, match="Field required"):
        RolloutRecipeConfig(name="legacy", horizon=2)


def test_rollout_policy_spec_is_immutable() -> None:
    policy = RolloutPolicySpec(horizon=2)

    with pytest.raises(ValidationError, match="frozen"):
        policy.horizon = 3


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
        assert recipe.policy.branch_factor == 3
        assert recipe.policy.beam_width == 3
        assert recipe.policy.require_sibling_strategy_diversity is True
        assert recipe.policy.min_sibling_distance_m > 0.0
        assert recipe.policy.min_sibling_yaw_deg == 20.0
        assert recipe.policy.min_sibling_target_bearing_deg == 20.0


def test_diverse_rollout_profile_matches_named_code_presets() -> None:
    config = RolloutDatasetWriterConfig.from_toml(_repo_root() / ".configs" / "build_rollouts_v1_diverse.toml")

    candidate_preset = CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family()
    assert candidate_preset.base.model_dump() == config.candidate_mixture.base.model_dump()
    assert [component.model_dump() for component in candidate_preset.components] == [
        component.model_dump() for component in config.candidate_mixture.components
    ]

    recipe_preset = RolloutRecipeConfig.diverse_suite()
    assert [recipe.model_dump() for recipe in recipe_preset] == [recipe.model_dump() for recipe in config.recipes]


def test_oracle_profiles_explicitly_own_active_target_sampling_parameters() -> None:
    config_names = (
        "build_rollouts_v1_realistic.toml",
        "build_rollouts_v1_diverse.toml",
        "build_rollouts_v1_lrz.template.toml",
    )

    for config_name in config_names:
        payload = tomllib.loads((_repo_root() / ".configs" / config_name).read_text())
        assert "target_source" not in payload
        assert "target_selector" not in payload
        assert set(payload["oracle_target_task_sampler"]) == {
            "max_targets_per_sample",
            "seed",
            "policy",
        }
        assert payload["max_targets_per_sample"] == payload["oracle_target_task_sampler"]["max_targets_per_sample"]
        assert payload["target_scorer"]["depth"]["renderer"]["cull_backfaces"] is False


def test_lrz_profile_keeps_realistic_generation_semantics_without_smoke_caps() -> None:
    realistic = RolloutDatasetWriterConfig.from_toml(_repo_root() / ".configs" / "build_rollouts_v1_realistic.toml")
    lrz = RolloutDatasetWriterConfig.from_toml(_repo_root() / ".configs" / "build_rollouts_v1_lrz.template.toml")

    assert lrz.max_samples is None
    assert lrz.source.limit is None
    assert lrz.candidate_mixture.model_dump() == realistic.candidate_mixture.model_dump()
    assert lrz.target_scorer.model_dump() == realistic.target_scorer.model_dump()
    assert lrz.selected_depth.model_dump() == realistic.selected_depth.model_dump()
    assert [recipe.model_dump() for recipe in lrz.recipes] == [recipe.model_dump() for recipe in realistic.recipes]


def test_real_lrz_array_does_not_mutate_shared_environment_or_hide_array_size() -> None:
    script = (_repo_root() / "scripts" / "templates" / "lrz" / "rollout_generation.sbatch").read_text()

    assert "#SBATCH --array=" not in script
    assert "SLURM_ARRAY_TASK_ID:?" in script
    assert "pip install" not in script
    assert "uv sync" not in script
    assert "uv run --frozen --no-sync nbv-build-rollouts" in script


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
