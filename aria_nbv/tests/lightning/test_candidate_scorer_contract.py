"""Tests for Lightning-specific candidate scorer contract validation."""

from __future__ import annotations

import pytest

from aria_nbv.lightning._candidate_scorer_contract import validate_vin_lightning_candidate_scorer_contract
from aria_nbv.lightning.lit_module import VinLightningModule, VinLightningModuleConfig
from aria_nbv.vin import (
    MultiStepCandidateScorerConfig,
    TargetConditionedMyopicScorerConfig,
    VinModelV3Config,
)

pytest.importorskip("pytorch_lightning")


def test_lightning_accepts_coral_candidate_contracts() -> None:
    """Runnable one-step scorers should keep the current CORAL training path."""

    assert validate_vin_lightning_candidate_scorer_contract(VinModelV3Config()) == "coral_candidate"
    assert (
        validate_vin_lightning_candidate_scorer_contract(
            TargetConditionedMyopicScorerConfig(target_descriptor_dim=0),
        )
        == "coral_candidate"
    )


def test_lightning_rejects_nonzero_target_descriptor_before_setup_target() -> None:
    """Target descriptors need explicit actor-visible token ownership first."""

    config = TargetConditionedMyopicScorerConfig(num_classes=5, target_descriptor_dim=32)

    with pytest.raises(NotImplementedError, match="target descriptor path is not implemented.*target_descriptor_dim=0"):
        validate_vin_lightning_candidate_scorer_contract(config)

    module_config = VinLightningModuleConfig(vin=config, num_classes=5)
    with pytest.raises(NotImplementedError, match="target descriptor path is not implemented.*target_descriptor_dim=0"):
        VinLightningModule(config=module_config)


def test_lightning_rejects_multi_step_qh_scaffold_before_setup_target() -> None:
    """Finite-horizon Q_H scorers need a rollout objective, not the CORAL loss."""

    config = MultiStepCandidateScorerConfig(horizon=3, discount=0.9)

    with pytest.raises(NotImplementedError, match="CORAL/VinPrediction.*Q_H.*rollout objective"):
        validate_vin_lightning_candidate_scorer_contract(config)

    module_config = VinLightningModuleConfig(vin=config)
    with pytest.raises(NotImplementedError, match="CORAL/VinPrediction.*Q_H.*rollout objective.*Lightning module"):
        VinLightningModule(config=module_config)
