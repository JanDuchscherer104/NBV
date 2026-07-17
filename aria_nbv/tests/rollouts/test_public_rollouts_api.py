"""Contract tests for the public ``aria_nbv.rollouts`` root API."""

# ruff: noqa: S101

from __future__ import annotations

import importlib

import pytest


def test_rollouts_public_api_smoke_imports_all_exports() -> None:
    """Every root-exported rollout symbol should resolve."""

    module = importlib.import_module("aria_nbv.rollouts")
    missing = [name for name in module.__all__ if not hasattr(module, name)]
    assert not missing


def test_removed_counterfactuals_module_has_no_compatibility_facade() -> None:
    """The clean replay move must not leave a second module owner behind."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.rollouts.counterfactuals")


def test_rollouts_root_is_the_exact_stable_allowlist() -> None:
    """The rollout root exposes only the stable replay and store entry points."""

    module = importlib.import_module("aria_nbv.rollouts")
    expected = {
        "CandidateScores",
        "CounterfactualPoseGenerator",
        "CounterfactualPoseGeneratorConfig",
        "CounterfactualRolloutResult",
        "CounterfactualTrajectory",
        "RolloutPolicySpec",
        "RolloutZarrStoreConfig",
        "RolloutZarrStoreReader",
    }
    assert set(module.__all__) == expected


def test_read_model_symbols_are_leaf_only() -> None:
    """Typed store projections must not widen the package root."""

    module = importlib.import_module("aria_nbv.rollouts")
    forbidden = {
        "StoredRollout",
        "StoredSelectedDepth",
        "StoredStep",
        "StoredTarget",
        "rollout_at",
        "rollout_by_id",
        "rollout_steps",
        "selected_depth_for_step",
        "target_by_id",
        "target_rows",
    }
    assert forbidden.isdisjoint(module.__all__)
    assert all(not hasattr(module, name) for name in forbidden)
