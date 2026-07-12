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


def test_rollouts_owns_record_and_store_contracts() -> None:
    """The rollout root is the canonical import surface for replay contracts."""

    module = importlib.import_module("aria_nbv.rollouts")
    expected = {
        "CandidateScores",
        "CounterfactualPoseGenerator",
        "CounterfactualPoseGeneratorConfig",
        "CounterfactualRolloutResult",
        "CounterfactualSelectionPolicy",
        "RolloutPolicySpec",
        "RolloutLineage",
        "RolloutZarrStoreConfig",
        "RolloutZarrStoreReader",
        "write_rollout_zarr_store",
        "validate_rollout_zarr_store",
    }
    assert expected <= set(module.__all__)
    assert "build_synthetic_rollout_traces" not in module.__all__
    assert "RolloutDatasetWriterConfig" not in module.__all__
    assert "read_rollout_traces" not in module.__all__
    assert "write_rollout_traces" not in module.__all__
