"""Tests for the VIN model namespace scaffold."""

from __future__ import annotations

import importlib

import pytest

from aria_nbv.vin import (
    MultiStepCandidateScorer,
    MultiStepCandidateScorerConfig,
    TargetConditionedMyopicScorer,
    TargetConditionedMyopicScorerConfig,
    VinModelV3,
    VinModelV3Config,
)
from aria_nbv.vin import model_v3 as legacy_v3
from aria_nbv.vin.candidate_scorer import CandidateScorerConfig
from aria_nbv.vin.model_v3 import VinModelV3 as LegacyVinModelV3
from aria_nbv.vin.model_v3 import VinModelV3Config as LegacyVinModelV3Config
from aria_nbv.vin.models import VinModelV2, VinModelV2Config
from aria_nbv.vin.models import VinModelV3 as NamespacedVinModelV3
from aria_nbv.vin.models import VinModelV3Config as NamespacedVinModelV3Config
from aria_nbv.vin.models import v2 as namespaced_v2
from aria_nbv.vin.models import v3 as namespaced_v3


def test_models_namespace_reexports_preserved_vin_v3() -> None:
    """The new namespace should not clone or move the active v3 implementation."""

    assert VinModelV3 is LegacyVinModelV3
    assert VinModelV3Config is LegacyVinModelV3Config
    assert NamespacedVinModelV3 is LegacyVinModelV3
    assert NamespacedVinModelV3Config is LegacyVinModelV3Config
    assert CandidateScorerConfig is LegacyVinModelV3Config
    assert namespaced_v3.FIELD_CHANNELS_V3 is legacy_v3.FIELD_CHANNELS_V3
    assert namespaced_v3.SEMIDENSE_PROJ_DIM == legacy_v3.SEMIDENSE_PROJ_DIM


def test_models_namespace_owns_vin_v2() -> None:
    """The maintained historical V2 scorer should live under the models namespace."""

    assert VinModelV2Config().target_type is VinModelV2
    assert namespaced_v2.VinModelV2 is VinModelV2
    assert namespaced_v2.FIELD_CHANNELS_V2


def test_experimental_model_namespace_is_removed() -> None:
    """Deprecated experimental model import paths should not remain as facades."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.vin.experimental.model_v2")


def test_planned_myopic_scorer_config_is_visible_but_not_runnable() -> None:
    """The target-conditioned myopic scaffold should fail explicitly."""

    config = TargetConditionedMyopicScorerConfig(
        num_classes=5,
        target_descriptor_dim=32,
    )

    assert config.target_type is TargetConditionedMyopicScorer
    with pytest.raises(NotImplementedError, match="scaffold only"):
        config.setup_target()


def test_planned_multi_step_scorer_config_is_visible_but_not_runnable() -> None:
    """The finite-horizon scaffold should fail explicitly."""

    config = MultiStepCandidateScorerConfig(horizon=3, discount=0.9)

    assert config.target_type is MultiStepCandidateScorer
    with pytest.raises(NotImplementedError, match="scaffold only"):
        config.setup_target()
