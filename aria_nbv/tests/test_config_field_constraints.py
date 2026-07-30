"""Regression tests for declarative Pydantic config bounds."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

pytest.importorskip("efm3d")

from aria_nbv.oracle.pipelines.offline_vin import VinOfflineWriterConfig
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig, RolloutRecipeConfig
from aria_nbv.oracle.target_rri import TargetRriScorerConfig
from aria_nbv.oracle.target_selection import OracleTargetTaskSamplerConfig
from aria_nbv.pose_generation import (
    CandidateMixtureComponentConfig,
    CandidateViewGeneratorConfig,
    ViewDirectionMode,
)
from aria_nbv.rerun_inspector._config import (
    RerunInspectorCandidateConfig,
    RerunInspectorEfmVoxelConfig,
    RerunInspectorGeometryConfig,
    RerunInspectorOutputConfig,
    RerunInspectorRolloutDepthConfig,
)
from aria_nbv.rollouts import (
    RolloutPolicySpec,
    RolloutZarrStoreConfig,
)
from aria_nbv.rollouts.replay.policy import CounterfactualSelectionPolicy
from aria_nbv.targets.protocol import TargetInputProtocol
from aria_nbv.utils.grad_norms import GradNormLoggingConfig
from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig, R6dLffPoseEncoderConfig


def _recipe(**kwargs: object) -> RolloutRecipeConfig:
    return RolloutRecipeConfig(
        name="constraint-test",
        policy=RolloutPolicySpec(
            selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
            **kwargs,
        ),
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
        (OracleTargetTaskSamplerConfig, {"max_targets_per_sample": 0}),
        (OracleTargetTaskSamplerConfig, {"policy": "weighted"}),
        (_recipe, {"horizon": 0}),
        (_recipe, {"selection_temperature": 0.0}),
        (_recipe, {"min_sibling_distance_m": -0.1}),
        (_recipe, {"min_sibling_yaw_deg": -1.0}),
        (_recipe, {"min_sibling_target_bearing_deg": -1.0}),
        (RolloutDatasetWriterConfig, {"max_samples": 0}),
        (RolloutZarrStoreConfig, {"discount_gamma": -0.1}),
        (VinOfflineWriterConfig, {"samples_per_shard": 0}),
        (CandidateViewGeneratorConfig, {"view_max_angle_deg": -1.0}),
        (_mixture_component, {"count": 0}),
        (RolloutPolicySpec, {"branch_factor": 0}),
        (RolloutPolicySpec, {"seed": -1}),
        (RolloutPolicySpec, {"min_sibling_target_bearing_deg": -1.0}),
        (TargetRriScorerConfig, {"target_crop_margin_m": -0.01}),
        (RerunInspectorOutputConfig, {"spawn_port": 0}),
        (RerunInspectorGeometryConfig, {"mesh_alpha": 256}),
        (RerunInspectorCandidateConfig, {"subset_indices": [-1]}),
        (RerunInspectorRolloutDepthConfig, {"point_fill_ratio": -0.1}),
        (RerunInspectorEfmVoxelConfig, {"occ_threshold": 1.1}),
        (GradNormLoggingConfig, {"max_items": 0}),
        (LearnableFourierFeaturesConfig, {"fourier_dim": 7}),
        (R6dLffPoseEncoderConfig, {"pose_scale_init": (0.0, 1.0)}),
    ],
)
def test_config_field_constraints_reject_invalid_values(
    factory: Callable[..., object],
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        factory(**kwargs)


def test_rollout_store_target_protocol_default_and_roundtrip() -> None:
    config = RolloutZarrStoreConfig()

    assert config.target_protocol_version is TargetInputProtocol.V0_GT_INPUT
    assert config.model_dump_jsonable()["target_protocol_version"] == "v0_gt_input"
    assert (
        RolloutZarrStoreConfig.model_validate_json(config.model_dump_json()).target_protocol_version
        is TargetInputProtocol.V0_GT_INPUT
    )


@pytest.mark.parametrize("protocol", ["v1-observed", "unknown"])
def test_rollout_store_config_rejects_noncanonical_target_protocol(protocol: str) -> None:
    with pytest.raises(ValidationError, match="v0_gt_input.*v1_observed"):
        RolloutZarrStoreConfig(target_protocol_version=protocol)


def test_rollout_writer_admits_observed_protocol() -> None:
    assert RolloutDatasetWriterConfig().store.target_protocol_version is TargetInputProtocol.V0_GT_INPUT

    config = RolloutDatasetWriterConfig(store=RolloutZarrStoreConfig(target_protocol_version="v1_observed"))

    assert config.store.target_protocol_version is TargetInputProtocol.V1_OBSERVED
