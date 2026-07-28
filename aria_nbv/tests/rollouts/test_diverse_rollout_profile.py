"""Tests for rollout generation profile TOMLs."""

# ruff: noqa: S101

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig, RolloutRecipeConfig
from aria_nbv.oracle.pipelines.shards import plan_rollout_shards
from aria_nbv.pose_generation import CandidatePositionMode, ViewDirectionMode
from aria_nbv.rollouts import CounterfactualPoseGeneratorConfig, RolloutPolicySpec
from aria_nbv.rollouts.shard_manifest import read_rollout_source_manifest

_HIGH_GAIN_SAMPLE_KEYS = [
    "ASE_81283_Atek_000005",
    "ASE_83515_Atek_000000",
    "ASE_83550_Atek_000000",
]


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


def test_paired_rollout_profiles_differ_only_in_candidate_families_and_destination() -> None:
    realistic, diverse = _paired_pilot_configs()
    realistic_payload = realistic.model_dump_jsonable()
    diverse_payload = diverse.model_dump_jsonable()

    realistic_mixture = realistic_payload.pop("candidate_mixture")
    diverse_mixture = diverse_payload.pop("candidate_mixture")
    assert realistic_mixture["base"] == diverse_mixture["base"]

    realistic_store = realistic_payload.pop("store")
    diverse_store = diverse_payload.pop("store")
    assert realistic_store.pop("store_dir") != diverse_store.pop("store_dir")
    assert realistic_store == diverse_store
    assert realistic_payload == diverse_payload


def test_paired_rollout_profiles_use_the_planned_candidate_families() -> None:
    realistic, diverse = _paired_pilot_configs()

    assert [(component.name, component.count) for component in realistic.candidate_mixture.components] == [
        ("forward_local", 24),
        ("target_bearing_local", 24),
        ("lateral_target_bypass", 12),
    ]
    assert [(component.name, component.count) for component in diverse.candidate_mixture.components] == [
        ("forward_local", 18),
        ("target_bearing_local", 18),
        ("lateral_target_bypass", 12),
        ("local_refinement", 6),
        ("revisit_backtrack", 6),
    ]
    assert realistic.candidate_mixture.total_count == diverse.candidate_mixture.total_count == 60

    diverse_by_name = {component.name: component for component in diverse.candidate_mixture.components}
    assert diverse_by_name["local_refinement"].view_mode is ViewDirectionMode.TARGET_POINT
    assert diverse_by_name["local_refinement"].position_mode is CandidatePositionMode.LOCAL_REFINEMENT
    assert diverse_by_name["revisit_backtrack"].view_mode is ViewDirectionMode.FORWARD_RIG
    assert diverse_by_name["revisit_backtrack"].position_mode is CandidatePositionMode.REVISIT_BACKTRACK
    assert all(
        component.view_mode not in {ViewDirectionMode.RADIAL_TOWARDS, ViewDirectionMode.RADIAL_AWAY}
        for component in diverse.candidate_mixture.components
    )


def test_paired_rollout_profiles_bind_the_exact_source_manifest_and_shared_recipes() -> None:
    realistic, diverse = _paired_pilot_configs()
    assert realistic.source_manifest_path == diverse.source_manifest_path
    assert realistic.source_manifest_path is not None

    source_manifest = read_rollout_source_manifest(realistic.source_manifest_path)
    assert len(source_manifest.rows) == realistic.max_samples == diverse.max_samples == 50
    assert source_manifest.split == realistic.source.split == diverse.source.split == "train"
    assert len({row.scene_id for row in source_manifest.rows}) == 5
    assert source_manifest.source_manifest_hash == "0cfa7252e18c1565"
    assert Path(source_manifest.source_store_dir).name == realistic.source.store.store_dir.name
    assert source_manifest.split_manifest_hash == realistic.store.split_manifest_hash
    assert source_manifest.split_manifest_hash == diverse.store.split_manifest_hash

    expected_recipes = {
        "random_valid": ("random_valid", 1, 1, None, 1.0),
        "oracle_greedy": ("oracle_greedy", 1, 1, None, 1.0),
        "oracle_lookahead": ("oracle_greedy", 2, 2, 2, 1.0),
        "temperature_softmax": ("temperature_softmax", 2, 2, 2, 1.0),
    }
    assert {
        recipe.name: (
            recipe.policy.selection_policy.value,
            recipe.policy.horizon,
            recipe.policy.branch_factor,
            recipe.policy.beam_width,
            recipe.policy.selection_temperature,
        )
        for recipe in realistic.recipes
    } == expected_recipes


def test_paired_rollout_profile_rejects_source_manifest_drift() -> None:
    config_path = _repo_root() / ".configs/generation/rollouts/paired/build_rollouts_v1_realistic.toml"
    payload = tomllib.loads(config_path.read_text())
    payload["max_samples"] = 49
    with pytest.raises(ValidationError, match="manifest row count"):
        RolloutDatasetWriterConfig.model_validate(payload)

    payload = tomllib.loads(config_path.read_text())
    payload["store"]["split_manifest_hash"] = "stale-split-hash"
    with pytest.raises(ValidationError, match="split_manifest_hash"):
        RolloutDatasetWriterConfig.model_validate(payload)

    payload = tomllib.loads(config_path.read_text())
    payload["source"]["store"]["store_dir"] = "different-vin-store"
    with pytest.raises(ValidationError, match="source-store identity"):
        RolloutDatasetWriterConfig.model_validate(payload)


def test_multihorizon_highgain_profile_selects_exact_ordered_cross_scene_roots() -> None:
    config = RolloutDatasetWriterConfig.from_toml(
        _repo_root() / ".configs/generation/rollouts/campaigns/build_rollouts_v1_multihorizon_highgain.toml"
    )

    assert config.sample_keys == _HIGH_GAIN_SAMPLE_KEYS
    assert config.max_samples == len(_HIGH_GAIN_SAMPLE_KEYS)
    assert config.source.limit == 50
    assert [(recipe.name, recipe.policy.horizon) for recipe in config.recipes] == [
        (f"oracle_greedy_h{horizon}", horizon) for horizon in range(3, 9)
    ]
    assert all(recipe.policy.branch_factor == 2 for recipe in config.recipes)
    assert all(recipe.policy.beam_width == 2 for recipe in config.recipes)
    assert config.target_scorer.depth.renderer.max_views_per_batch == 2

    entries = plan_rollout_shards(config, rows_per_shard=1)

    assert [row.sample_key for entry in entries for row in entry.rows] == _HIGH_GAIN_SAMPLE_KEYS
    assert [row.scene_id for entry in entries for row in entry.rows] == ["81283", "83515", "83550"]


def test_rollout_sample_keys_fail_closed_for_duplicates_and_manifest_misses() -> None:
    config_path = _repo_root() / ".configs/generation/rollouts/paired/build_rollouts_v1_realistic.toml"
    payload = tomllib.loads(config_path.read_text())
    payload["max_samples"] = 2
    payload["sample_keys"] = ["ASE_81283_Atek_000005", "ASE_81283_Atek_000005"]
    with pytest.raises(ValidationError, match="sample_keys must be unique"):
        RolloutDatasetWriterConfig.model_validate(payload)

    payload["sample_keys"] = ["ASE_81283_Atek_000005", "ASE_missing_Atek_999999"]
    with pytest.raises(ValidationError, match="sample_keys are missing from source_manifest_path"):
        RolloutDatasetWriterConfig.model_validate(payload)


def test_oracle_profiles_explicitly_own_active_target_sampling_parameters() -> None:
    config_paths = (
        Path("generation/rollouts/paired/build_rollouts_v1_realistic.toml"),
        Path("generation/rollouts/paired/build_rollouts_v1_diverse.toml"),
        Path("generation/rollouts/templates/build_rollouts_v1_lrz.template.toml"),
    )

    for config_path in config_paths:
        payload = tomllib.loads((_repo_root() / ".configs" / config_path).read_text())
        assert "target_source" not in payload
        assert "target_selector" not in payload
        assert set(payload["oracle_target_task_sampler"]) == {
            "max_targets_per_sample",
            "seed",
            "policy",
        }
        assert "max_targets_per_sample" not in payload
        if config_path.name in {"build_rollouts_v1_realistic.toml", "build_rollouts_v1_diverse.toml"}:
            assert payload["oracle_target_task_sampler"]["max_targets_per_sample"] == 1
            assert "oversample_factor" not in payload["candidate_mixture"]["base"]
            assert "max_resamples" not in payload["candidate_mixture"]["base"]
        assert payload["target_scorer"]["depth"]["renderer"]["cull_backfaces"] is False


def test_lrz_profile_keeps_realistic_generation_semantics_without_smoke_caps() -> None:
    realistic = RolloutDatasetWriterConfig.from_toml(
        _repo_root() / ".configs/generation/rollouts/paired/build_rollouts_v1_realistic.toml"
    )
    lrz = RolloutDatasetWriterConfig.from_toml(
        _repo_root() / ".configs/generation/rollouts/templates/build_rollouts_v1_lrz.template.toml"
    )

    assert lrz.max_samples is None
    assert lrz.source.limit is None
    lrz_candidate = lrz.candidate_mixture.model_dump_jsonable()
    realistic_candidate = realistic.candidate_mixture.model_dump_jsonable()
    lrz_candidate["base"].pop("oversample_factor")
    realistic_candidate["base"].pop("oversample_factor")
    assert lrz_candidate == realistic_candidate
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


def _paired_pilot_configs() -> tuple[RolloutDatasetWriterConfig, RolloutDatasetWriterConfig]:
    """Parse the two profile TOMLs through the production config model."""

    config_dir = _repo_root() / ".configs/generation/rollouts/paired"
    return (
        RolloutDatasetWriterConfig.from_toml(config_dir / "build_rollouts_v1_realistic.toml"),
        RolloutDatasetWriterConfig.from_toml(config_dir / "build_rollouts_v1_diverse.toml"),
    )
