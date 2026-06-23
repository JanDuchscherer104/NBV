"""Regression tests for declarative Pydantic config bounds."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

pytest.importorskip("efm3d")

from aria_nbv.app.config import RlPageConfig
from aria_nbv.data_handling import (
    OracleTargetTaskSamplerConfig,
    TargetSelectorConfig,
    VinOfflineWriterConfig,
)
from aria_nbv.pose_generation import (
    CandidateMixtureComponentConfig,
    CandidateViewGeneratorConfig,
    CounterfactualPoseGeneratorConfig,
    CounterfactualSelectionPolicy,
    CounterfactualTargetOracleRriScorerConfig,
    ViewDirectionMode,
)
from aria_nbv.rerun_inspector._config import (
    RerunInspectorCandidateConfig,
    RerunInspectorEfmVoxelConfig,
    RerunInspectorGeometryConfig,
    RerunInspectorOutputConfig,
    RerunInspectorRolloutDepthConfig,
)
from aria_nbv.rl import CounterfactualRLEnvConfig
from aria_nbv.rollouts import RolloutDatasetWriterConfig, RolloutRecipeConfig, RolloutZarrStoreConfig
from aria_nbv.utils.grad_norms import GradNormLoggingConfig
from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig, R6dLffPoseEncoderConfig
from aria_nbv.vin.experimental.model_v1_SH import VinModelConfig as ShVinModelConfig


def _recipe(**kwargs: object) -> RolloutRecipeConfig:
    return RolloutRecipeConfig(
        name="constraint-test",
        selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
        **kwargs,
    )


def _mixture_component(**kwargs: object) -> CandidateMixtureComponentConfig:
    return CandidateMixtureComponentConfig(
        name="constraint-test",
        strategy=ViewDirectionMode.FORWARD_RIG,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (TargetSelectorConfig, {"min_confidence": -0.1}),
        (TargetSelectorConfig, {"k": 0}),
        (OracleTargetTaskSamplerConfig, {"max_targets_per_sample": 0}),
        (OracleTargetTaskSamplerConfig, {"min_identity_iou": -0.1}),
        (OracleTargetTaskSamplerConfig, {"identity_iou_thresholds": ()}),
        (_recipe, {"horizon": 0}),
        (_recipe, {"selection_temperature": 0.0}),
        (_recipe, {"min_sibling_distance_m": -0.1}),
        (_recipe, {"min_sibling_yaw_deg": -1.0}),
        (RolloutDatasetWriterConfig, {"max_samples": 0}),
        (RolloutZarrStoreConfig, {"discount_gamma": -0.1}),
        (VinOfflineWriterConfig, {"samples_per_shard": 0}),
        (CandidateViewGeneratorConfig, {"view_max_angle_deg": -1.0}),
        (_mixture_component, {"count": 0}),
        (CounterfactualPoseGeneratorConfig, {"branch_factor": 0}),
        (CounterfactualPoseGeneratorConfig, {"seed": -1}),
        (CounterfactualTargetOracleRriScorerConfig, {"target_crop_margin_m": -0.01}),
        (RerunInspectorOutputConfig, {"spawn_port": 0}),
        (RerunInspectorGeometryConfig, {"mesh_alpha": 256}),
        (RerunInspectorCandidateConfig, {"subset_indices": [-1]}),
        (RerunInspectorRolloutDepthConfig, {"point_fill_ratio": -0.1}),
        (RerunInspectorEfmVoxelConfig, {"occ_threshold": 1.1}),
        (CounterfactualRLEnvConfig, {"horizon": 0}),
        (GradNormLoggingConfig, {"max_items": 0}),
        (LearnableFourierFeaturesConfig, {"fourier_dim": 7}),
        (R6dLffPoseEncoderConfig, {"pose_scale_init": (0.0, 1.0)}),
        (ShVinModelConfig, {"frustum_depths_m": [float("nan")]}),
        (ShVinModelConfig, {"frustum_depths_m": [0.0]}),
        (RlPageConfig, {"default_eval_episodes": 0}),
    ],
)
def test_config_field_constraints_reject_invalid_values(
    factory: Callable[..., object],
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        factory(**kwargs)
