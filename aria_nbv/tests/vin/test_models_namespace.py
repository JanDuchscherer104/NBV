"""Tests for the VIN model namespace scaffold."""

from __future__ import annotations

import importlib
from typing import get_args

import pytest
import torch

from aria_nbv.vin import VinModelV3, VinModelV3Config
from aria_nbv.vin.candidate_scorer import CandidateScorerConfig, candidate_scorer_training_contract
from aria_nbv.vin.models import VinModelV3 as NamespacedVinModelV3
from aria_nbv.vin.models import VinModelV3Config as NamespacedVinModelV3Config
from aria_nbv.vin.models import scene_myopic as namespaced_v3
from aria_nbv.vin.models.scene_myopic import VinModelV3 as CanonicalVinModelV3
from aria_nbv.vin.models.scene_myopic import VinModelV3Config as CanonicalVinModelV3Config
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorer, MultiStepCandidateScorerConfig
from aria_nbv.vin.models.target_myopic import TargetConditionedMyopicScorer, TargetConditionedMyopicScorerConfig


def test_models_namespace_reexports_preserved_vin_v3() -> None:
    """The models namespace should own and re-export the preserved v3 implementation."""

    assert VinModelV3 is CanonicalVinModelV3
    assert VinModelV3Config is CanonicalVinModelV3Config
    assert NamespacedVinModelV3 is CanonicalVinModelV3
    assert NamespacedVinModelV3Config is CanonicalVinModelV3Config
    assert CanonicalVinModelV3Config in get_args(CandidateScorerConfig)
    assert namespaced_v3.FIELD_CHANNELS_V3
    assert namespaced_v3.SEMIDENSE_PROJ_DIM > 0


def test_root_vin_namespace_excludes_scaffold_scorers() -> None:
    """Scaffold scorer families should stay leaf-only until they are runnable public APIs."""

    vin_root = importlib.import_module("aria_nbv.vin")
    model_root = importlib.import_module("aria_nbv.vin.models")

    for name in (
        "MultiStepCandidateScorer",
        "MultiStepCandidateScorerConfig",
        "TargetConditionedMyopicScorer",
        "TargetConditionedMyopicScorerConfig",
    ):
        assert not hasattr(vin_root, name)
        assert not hasattr(model_root, name)


def test_experimental_model_namespace_is_removed() -> None:
    """Deprecated experimental model import paths should not remain as facades."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.vin.experimental.model_v2")


def test_legacy_root_v3_module_is_removed() -> None:
    """The preserved v3 implementation should be owned by `aria_nbv.vin.models.scene_myopic`."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.vin.model_v3")

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.vin.models.v3")


def test_legacy_v2_model_module_is_removed() -> None:
    """The deprecated V2 scorer should not remain importable from active VIN."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.vin.models.v2")


def test_helper_sidecars_do_not_cycle_with_models_namespace() -> None:
    """Context and validation sidecars should import without model-package cycles."""

    assert importlib.import_module("aria_nbv.vin.scorer_context")
    assert importlib.import_module("aria_nbv.vin.encoders.validation")


def test_planned_myopic_scorer_config_is_visible_but_not_runnable() -> None:
    """Positive-width target descriptors should fail until actor target tokens exist."""

    config = TargetConditionedMyopicScorerConfig(
        num_classes=5,
        target_descriptor_dim=32,
    )

    assert config.target_type is TargetConditionedMyopicScorer
    with pytest.raises(NotImplementedError, match="target descriptor path is not implemented"):
        config.setup_target()


def test_zero_descriptor_myopic_scorer_wraps_preserved_v3_baseline() -> None:
    """The myopic family should expose a runnable v3-backed CORAL baseline."""

    config = TargetConditionedMyopicScorerConfig(num_classes=5, target_descriptor_dim=0)
    scorer = config.setup_target()

    assert isinstance(scorer, TargetConditionedMyopicScorer)
    assert isinstance(scorer.base_scorer, VinModelV3)
    assert scorer.base_scorer.config.num_classes == 5
    assert scorer.head_coral is scorer.base_scorer.head_coral


def test_zero_descriptor_myopic_scorer_delegates_bin_value_initialization() -> None:
    """The V3-backed wrapper should preserve CORAL bin-value lifecycle parity."""

    config = TargetConditionedMyopicScorerConfig(num_classes=5, target_descriptor_dim=0)
    scorer = config.setup_target()
    values = torch.linspace(0.0, 1.0, steps=5)

    scorer.init_bin_values(values)

    assert scorer.head_coral.has_bin_values
    assert torch.allclose(scorer.head_coral.bin_values.values().detach().cpu(), values)


def test_zero_descriptor_myopic_scorer_uses_custom_base_scorer_config() -> None:
    """The named myopic baseline should preserve v3 architecture settings."""

    config = TargetConditionedMyopicScorerConfig(
        num_classes=5,
        target_descriptor_dim=0,
        base_scorer=VinModelV3Config(num_classes=99, field_dim=12, head_dropout=0.2),
    )

    scorer = config.setup_target()

    assert scorer.base_scorer.config.num_classes == 5
    assert scorer.base_scorer.config.field_dim == 12
    assert scorer.base_scorer.config.head_dropout == 0.2
    assert scorer.base_scorer.config is not config.base_scorer


def test_candidate_scorer_config_accepts_myopic_scaffold() -> None:
    """Lightning config should accept the planned myopic scorer config object."""

    from aria_nbv.lightning.lit_module import VinLightningModuleConfig

    scorer_config = TargetConditionedMyopicScorerConfig(
        num_classes=5,
        target_descriptor_dim=32,
    )
    module_config = VinLightningModuleConfig(vin=scorer_config, num_classes=5)

    assert module_config.vin is scorer_config
    with pytest.raises(NotImplementedError, match="target descriptor path is not implemented"):
        module_config.vin.setup_target()


def test_candidate_scorer_config_parses_myopic_payload() -> None:
    """Dict-style experiment payloads should select the myopic scaffold config."""

    from aria_nbv.lightning.lit_module import VinLightningModuleConfig

    module_config = VinLightningModuleConfig(
        vin={
            "num_classes": 5,
            "target_descriptor_dim": 32,
            "candidate_token_dim": 64,
        },
        num_classes=5,
    )

    assert isinstance(module_config.vin, TargetConditionedMyopicScorerConfig)
    assert module_config.vin.target_descriptor_dim == 32


def test_candidate_scorer_config_parses_myopic_base_scorer_payload() -> None:
    """Dict-style myopic configs should preserve nested v3 architecture fields."""

    from aria_nbv.lightning.lit_module import VinLightningModuleConfig

    module_config = VinLightningModuleConfig(
        vin={
            "num_classes": 5,
            "target_descriptor_dim": 0,
            "base_scorer": {
                "num_classes": 99,
                "field_dim": 12,
                "head_dropout": 0.2,
            },
        },
        num_classes=5,
    )

    assert isinstance(module_config.vin, TargetConditionedMyopicScorerConfig)
    assert module_config.vin.base_scorer.field_dim == 12
    assert module_config.vin.base_scorer.head_dropout == 0.2
    scorer = module_config.vin.setup_target()
    assert scorer.base_scorer.config.num_classes == 5
    assert scorer.base_scorer.config.field_dim == 12


def test_planned_multi_step_scorer_config_is_visible_but_not_runnable() -> None:
    """The finite-horizon scaffold should fail explicitly."""

    config = MultiStepCandidateScorerConfig(horizon=3, discount=0.9)

    assert config.target_type is MultiStepCandidateScorer
    with pytest.raises(NotImplementedError, match="scaffold only"):
        config.setup_target()


def test_candidate_scorer_config_accepts_multi_step_scaffold() -> None:
    """Lightning config should accept the planned finite-horizon scorer config object."""

    from aria_nbv.lightning.lit_module import VinLightningModuleConfig

    scorer_config = MultiStepCandidateScorerConfig(horizon=3, discount=0.9)
    module_config = VinLightningModuleConfig(vin=scorer_config)

    assert module_config.vin is scorer_config
    with pytest.raises(NotImplementedError, match="scaffold only"):
        module_config.vin.setup_target()


def test_candidate_scorer_config_parses_multi_step_payload() -> None:
    """Dict-style experiment payloads should select the finite-horizon scaffold config."""

    from aria_nbv.lightning.lit_module import VinLightningModuleConfig

    module_config = VinLightningModuleConfig(
        vin={
            "horizon": 3,
            "discount": 0.9,
            "candidate_token_dim": 64,
        },
    )

    assert isinstance(module_config.vin, MultiStepCandidateScorerConfig)
    assert module_config.vin.horizon == 3


def test_candidate_scorer_training_contract_classifies_configs() -> None:
    """Training entry points should distinguish CORAL and rollout-value contracts."""

    assert candidate_scorer_training_contract(VinModelV3Config()) == "coral_candidate"
    assert (
        candidate_scorer_training_contract(TargetConditionedMyopicScorerConfig(target_descriptor_dim=0))
        == "coral_candidate"
    )
    assert (
        candidate_scorer_training_contract(TargetConditionedMyopicScorerConfig(target_descriptor_dim=32))
        == "target_myopic_coral_scaffold"
    )
    assert candidate_scorer_training_contract(MultiStepCandidateScorerConfig(horizon=3)) == "finite_horizon_q_scaffold"
