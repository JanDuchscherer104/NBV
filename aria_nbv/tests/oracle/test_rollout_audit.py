"""Tests for independent Oracle-GT rollout endpoint evaluation."""

from __future__ import annotations

import inspect
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW
from efm3d.aria.aria_constants import (
    ARIA_CALIB,
    ARIA_DEPTH_TIME_NS,
    ARIA_DISTANCE_M,
    ARIA_FRAME_ID,
    ARIA_IMG,
    ARIA_IMG_TIME_NS,
    ARIA_POINTS_DIST_STD,
    ARIA_POINTS_INV_DIST_STD,
    ARIA_POINTS_TIME_NS,
    ARIA_POINTS_VOL_MAX,
    ARIA_POINTS_VOL_MIN,
    ARIA_POINTS_WORLD,
    ARIA_POSE_T_WORLD_RIG,
    ARIA_POSE_TIME_NS,
)
from efm3d.aria.obb import ObbTW
from pytorch3d.renderer.cameras import PerspectiveCameras

from aria_nbv.data_handling import VinSnippetView
from aria_nbv.data_handling.offline.batch import CompactObbBlock
from aria_nbv.data_handling.offline.dataset import VinOfflineOracleBlock, VinOfflineSample
from aria_nbv.data_handling.raw.views import EfmSnippetView
from aria_nbv.oracle.pipelines.rollout_audit import (
    EndpointEvaluationBlockedError,
    EndpointEvaluationBlockedReason,
    EndpointRawAssetSha256,
    IndependentEndpointEvaluator,
    IndependentEndpointMeasurement,
    OracleGtEndpointEvaluatorConfig,
    ResolvedEndpointSource,
    _hash_matches,
    build_endpoint_audit_row,
)
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.oracle.target_rri import TargetRriScorerConfig
from aria_nbv.oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    OracleTargetTask,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
)
from aria_nbv.rendering.candidate_depth_renderer import CandidateDepthRenderer, CandidateDepthRendererConfig
from aria_nbv.rendering.pytorch3d_depth_renderer import Pytorch3DDepthRendererConfig
from aria_nbv.rollouts.read_model import (
    StoredEndpointComparator,
    StoredEndpointEvaluationUnit,
    StoredEvaluationLineage,
    StoredRootActionSetIdentity,
    StoredSelectedPoseChain,
    StoredTarget,
    persisted_pre_treatment_context_sha256,
)
from aria_nbv.rollouts.scientific_audit import (
    EquivalenceVerdict,
    NamedSha256,
    PolicyMatchIdentity,
    PolicySemanticRole,
    PolicyTreatmentIdentity,
    RowEvaluationStatus,
    ScientificAuditConfig,
    TreatmentConfigPath,
    named_sha256_context_hash,
    normalize_treatment_configs,
)
from aria_nbv.rollouts.shard_manifest import read_rollout_source_manifest
from aria_nbv.targets.protocol import TargetInputProtocol
from aria_nbv.utils.console import Verbosity
from aria_nbv.utils.fingerprints import stable_config_hash
from aria_nbv.utils.frames import rotate_yaw_cw90


def _camera(width: int = 16, height: int = 16) -> CameraTW:
    camera = CameraTW.from_surreal(
        width=torch.tensor([float(width)]),
        height=torch.tensor([float(height)]),
        type_str="Pinhole",
        params=torch.tensor([[14.0, 14.0, width / 2.0, height / 2.0]], dtype=torch.float32),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([float(max(width, height))]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, dtype=torch.float32).unsqueeze(0)),
    )
    return CameraTW(camera.tensor().reshape(1, -1))


def _pose(translation: tuple[float, float, float]) -> PoseTW:
    return PoseTW.from_Rt(torch.eye(3, dtype=torch.float32).unsqueeze(0), torch.tensor([translation]))


def _target_block() -> CompactObbBlock:
    bounds = torch.tensor([[-12.0, 12.0, -12.0, 12.0, -4.0, 4.0]], dtype=torch.float32)
    bb2 = torch.tensor([[0.0, 15.0, 0.0, 15.0]], dtype=torch.float32)
    obb = ObbTW.from_lmc(
        bb3_object=bounds,
        bb2_rgb=bb2,
        bb2_slaml=bb2,
        bb2_slamr=bb2,
        T_world_object=_pose((0.0, 0.0, 4.0)),
        sem_id=torch.tensor([0]),
        inst_id=torch.tensor([7]),
        prob=torch.tensor([1.0]),
    )
    return CompactObbBlock(obbs=obb.tensor(), sem_id_to_name={0: "target"})


def _snippet() -> EfmSnippetView:
    camera = _camera()
    width, height = 16, 16
    pose = _pose((0.0, 0.0, 0.0))
    times = torch.tensor([10], dtype=torch.int64)
    mesh = trimesh.Trimesh(
        vertices=np.asarray(
            [[-10.0, -10.0, 4.0], [10.0, -10.0, 4.0], [10.0, 10.0, 4.0], [-10.0, 10.0, 4.0]],
            dtype=np.float32,
        ),
        faces=np.asarray([[0, 2, 1], [0, 3, 2]], dtype=np.int64),
        process=False,
    )
    efm = {
        ARIA_IMG[0]: torch.zeros((1, 3, height, width), dtype=torch.float32),
        ARIA_CALIB[0]: camera,
        ARIA_IMG_TIME_NS[0]: times,
        ARIA_FRAME_ID[0]: torch.tensor([0], dtype=torch.int64),
        ARIA_DISTANCE_M[0]: torch.full((1, 1, height, width), 4.0, dtype=torch.float32),
        ARIA_DEPTH_TIME_NS[0]: times,
        ARIA_POSE_T_WORLD_RIG: pose,
        ARIA_POSE_TIME_NS: times,
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81]),
        ARIA_POINTS_WORLD: torch.zeros((1, 1, 3), dtype=torch.float32),
        ARIA_POINTS_DIST_STD: torch.zeros((1, 1), dtype=torch.float32),
        ARIA_POINTS_INV_DIST_STD: torch.zeros((1, 1), dtype=torch.float32),
        ARIA_POINTS_TIME_NS: times,
        ARIA_POINTS_VOL_MIN: torch.tensor([-12.0, -12.0, -1.0]),
        ARIA_POINTS_VOL_MAX: torch.tensor([12.0, 12.0, 8.0]),
    }
    return EfmSnippetView(
        efm=efm,
        scene_id="scene",
        snippet_id="snippet",
        mesh=mesh,
        crop_bounds=(torch.tensor([-12.0, -12.0, -1.0]), torch.tensor([12.0, 12.0, 8.0])),
        mesh_verts=torch.from_numpy(mesh.vertices).to(dtype=torch.float32),
        mesh_faces=torch.from_numpy(mesh.faces).to(dtype=torch.int64),
    )


def _sample() -> VinOfflineSample:
    snippet = _snippet()
    p3d = PerspectiveCameras(
        R=torch.eye(3).unsqueeze(0),
        T=torch.zeros((1, 3)),
        focal_length=torch.tensor([[14.0, 14.0]]),
        principal_point=torch.tensor([[8.0, 8.0]]),
        image_size=torch.tensor([[16.0, 16.0]]),
        in_ndc=False,
    )
    oracle = VinOfflineOracleBlock(
        candidate_poses_world_cam=_pose((0.0, 0.0, 0.0)),
        reference_pose_world_rig=_pose((0.0, 0.0, 0.0)),
        candidate_count=1,
        rri=torch.zeros(1),
        pm_dist_before=torch.zeros(1),
        pm_dist_after=torch.zeros(1),
        pm_acc_before=torch.zeros(1),
        pm_comp_before=torch.zeros(1),
        pm_acc_after=torch.zeros(1),
        pm_comp_after=torch.zeros(1),
        p3d_cameras=p3d,
    )
    vin = VinSnippetView(
        points_world=torch.zeros((1, 3)),
        lengths=torch.tensor([1]),
        t_world_rig=_pose((0.0, 0.0, 0.0)),
    )
    return VinOfflineSample(
        sample_key="scene::snippet",
        scene_id="scene",
        snippet_id="snippet",
        vin_snippet=vin,
        oracle=oracle,
        sample_index=3,
        source_shard_id="shard-0",
        source_shard_row=2,
        efm_snippet_view=snippet,
        gt_obbs=_target_block(),
    )


class _Repository:
    def __init__(self, sample: VinOfflineSample) -> None:
        self.sample = sample

    def resolve(self, lineage: StoredEvaluationLineage) -> ResolvedEndpointSource:
        assert lineage.source_sample_key == self.sample.sample_key
        return ResolvedEndpointSource(
            sample=self.sample,
            source_store_sha256="1" * 64,
            split_manifest_sha256="2" * 64,
        )


def _config() -> OracleGtEndpointEvaluatorConfig:
    scorer = TargetRriScorerConfig(
        depth=CandidateDepthRendererConfig(
            device="cpu",
            renderer=Pytorch3DDepthRendererConfig(device="cpu", verbosity=0),
            max_candidates_final=1,
            resolution_scale=None,
            output_width_px=16,
            output_height_px=16,
            verbosity=0,
        ),
        backprojection_stride=1,
        eval_fusion_voxel_size_m=0.0,
        eval_fusion_max_points=None,
        target_eval_max_points=20_000,
        include_scene_rri=False,
        verbosity=0,
    )
    return OracleGtEndpointEvaluatorConfig(
        source_manifest_path=Path("unused-source-manifest.json"),
        expected_source_store_sha256="1" * 64,
        expected_split_manifest_sha256="2" * 64,
        target_scorer=scorer,
        expected_candidate_config_hashes=("a" * 16,),
        expected_rollout_config_hashes=("b" * 16,),
    )


def _inputs(config: OracleGtEndpointEvaluatorConfig) -> tuple[StoredEvaluationLineage, StoredTarget]:
    sample = _sample()
    task = OracleTargetTaskSampler(OracleTargetTaskSamplerConfig(max_targets_per_sample=None)).sample(sample).rows[0]
    lineage = StoredEvaluationLineage(
        source_row_id=3,
        source_sample_index=3,
        source_sample_key=sample.sample_key,
        source_shard_id="shard-0",
        source_shard_row=2,
        source_offline_store_manifest_hash="1" * 16,
        split_manifest_hash="2" * 16,
        split="train",
        scene_id="scene",
        snippet_id="snippet",
        rollout_row_id=9,
        rollout_id="rollout-9",
        chain_id=0,
        root_time_ns=10,
        root_trajectory_index=0,
        root_frame_index=0,
        candidate_config_hash="a" * 16,
        oracle_config_hash=stable_config_hash(config.target_scorer),
        rollout_config_hash="b" * 16,
        rollout_seed=0,
        model_checkpoint_hash=None,
        selection_rng_state_hash=f"seed-once:0:split-manifest:{'2' * 16}",
        target_row_id=task.target_row_id,
        target_id=task.target_id,
        target_protocol_version=TargetInputProtocol.V0_GT_INPUT.value,
        target_crop_policy=config.target_scorer.target_crop_policy,
    )
    return lineage, _stored_target(task)


def _stored_target(task: OracleTargetTask) -> StoredTarget:
    descriptor = task.descriptor
    return StoredTarget(
        row_position=0,
        target_row_id=task.target_row_id,
        target_id=task.target_id,
        source=ORACLE_TARGET_TASK_SOURCE,
        source_index=task.source_index,
        class_name=descriptor.class_name,
        sem_id=descriptor.sem_id,
        inst_id=task.inst_id,
        confidence=task.confidence,
        selection_rank=0,
        selection_score=float("nan"),
        selection_probability=1.0,
        target_valid=True,
        primary_invalid_reason_id=0,
        gt_label_valid=True,
        matched_gt_target_row_id=-1,
        matched_gt_target_id="",
        gt_match_status="matched",
        gt_match_iou=float("nan"),
        gt_match_score=float("nan"),
        projected_area_pixels=0.0,
        projected_area_fraction=0.0,
        semidense_support_count=0.0,
        evl_support_count=0.0,
        effective_support_count=0.0,
        visibility_score=0.0,
        support_score=0.0,
        deficit_score=0.0,
        center_world=np.asarray(descriptor.center_world, dtype=np.float32),
        extents=np.asarray(descriptor.extents_m, dtype=np.float32),
        pose_world_object=np.asarray(descriptor.pose_world_object, dtype=np.float32),
    )


def _chain(*translations: tuple[float, float, float]) -> StoredSelectedPoseChain:
    root = rotate_yaw_cw90(_pose((0.0, 0.0, 0.0))).tensor().reshape(12).numpy()
    selected = (
        np.stack(
            [rotate_yaw_cw90(_pose(value)).tensor().reshape(12).numpy() for value in translations],
            axis=0,
        )
        if translations
        else np.empty((0, 12), dtype=np.float32)
    )
    return StoredSelectedPoseChain(
        root_pose_world=np.asarray(root, dtype=np.float32),
        selected_poses_world_cam=np.asarray(selected, dtype=np.float32),
        step_row_ids=tuple(range(len(translations))),
        selected_candidate_row_ids=tuple(range(10, 10 + len(translations))),
    )


def _unit(
    config: OracleGtEndpointEvaluatorConfig,
    *,
    comparator_gain: float,
) -> tuple[StoredEndpointEvaluationUnit, StoredTarget]:
    lineage, target = _inputs(config)
    chain = _chain()
    return (
        StoredEndpointEvaluationUnit(
            lineage=lineage,
            pose_chain=chain,
            budget=1,
            achieved_steps=0,
            termination_reason="terminated_early",
            comparator=StoredEndpointComparator(gain=comparator_gain),
        ),
        target,
    )


class _MeasurementEvaluator:
    def __init__(self, measurement: IndependentEndpointMeasurement) -> None:
        self.measurement = measurement
        self.calls: list[tuple[StoredEvaluationLineage, StoredTarget, StoredSelectedPoseChain]] = []

    def evaluate(
        self,
        *,
        lineage: StoredEvaluationLineage,
        target: StoredTarget,
        pose_chain: StoredSelectedPoseChain,
    ) -> IndependentEndpointMeasurement:
        self.calls.append((lineage, target, pose_chain))
        return self.measurement


def _measurement(*, delta_0: float, delta_h: float) -> IndependentEndpointMeasurement:
    return IndependentEndpointMeasurement(
        delta_0=delta_0,
        delta_h=delta_h,
        endpoint_gain=0.0,
        evaluation_cost_s=0.25,
        acquisition_path_length_m=0.0,
        achieved_steps=0,
        source_store_sha256="1" * 64,
        split_manifest_sha256="2" * 64,
        raw_assets=(EndpointRawAssetSha256(name="target_mesh", sha256="6" * 64),),
    )


def _audit_identities(
    unit: StoredEndpointEvaluationUnit,
    target: StoredTarget,
    *,
    treatment: PolicyTreatmentIdentity | None = None,
) -> tuple[PolicyMatchIdentity, StoredRootActionSetIdentity]:
    root_sha256 = "3" * 64
    configs = normalize_treatment_configs(
        {"policy": {"shared": {"budget": unit.budget}, "treatment": "oracle-1"}},
        (TreatmentConfigPath(owner="policy", json_pointer="/treatment"),),
    )
    root_identity = StoredRootActionSetIdentity(
        rollout_row_id=unit.lineage.rollout_row_id,
        step_row_id=0,
        budget=unit.budget,
        candidate_count=12,
        sha256=root_sha256,
    )
    match_identity = PolicyMatchIdentity.derive(
        treatment=treatment
        or PolicyTreatmentIdentity(
            semantic_role=PolicySemanticRole.ORACLE_ONE_STEP,
            treatment_id="oracle-1",
        ),
        configs=configs,
        root_action_set_sha256=root_sha256,
        persisted_context_sha256=persisted_pre_treatment_context_sha256(
            unit.lineage,
            target,
            root_identity,
        ),
        raw_asset_context_sha256=named_sha256_context_hash((NamedSha256(name="target_mesh", sha256="6" * 64),)),
    )
    return match_identity, root_identity


def test_audit_bridge_requires_exact_stored_checkpoint_for_learned_treatment() -> None:
    config = _config()
    base_unit, target = _unit(config, comparator_gain=0.0)
    checkpoint = "a" * 64
    treatment = PolicyTreatmentIdentity(
        semantic_role=PolicySemanticRole.LEARNED_ONE_STEP,
        treatment_id="learned-one-step",
        model_checkpoint_sha256=checkpoint,
    )
    matching_unit = replace(
        base_unit,
        lineage=replace(base_unit.lineage, model_checkpoint_hash=checkpoint),
    )
    match_identity, root_identity = _audit_identities(matching_unit, target, treatment=treatment)
    evaluator = _MeasurementEvaluator(_measurement(delta_0=1.0, delta_h=1.0))

    row = build_endpoint_audit_row(
        evaluator,
        unit=matching_unit,
        target=target,
        audit_config=ScientificAuditConfig(),
        match_identity=match_identity,
        root_action_identity=root_identity,
        unit_id="matching-learned-checkpoint",
        stratum_id="stratum-0",
    )

    assert row.evaluation_status is RowEvaluationStatus.COMPLETE
    assert len(evaluator.calls) == 1

    for label, stored_checkpoint, message in (
        ("missing", None, "requires an exact persisted"),
        ("mismatched", "b" * 64, "differs from the learned policy treatment"),
    ):
        evaluator.calls.clear()
        unit = replace(
            base_unit,
            lineage=replace(base_unit.lineage, model_checkpoint_hash=stored_checkpoint),
        )
        with pytest.raises(ValueError, match=message):
            build_endpoint_audit_row(
                evaluator,
                unit=unit,
                target=target,
                audit_config=ScientificAuditConfig(),
                match_identity=match_identity,
                root_action_identity=root_identity,
                unit_id=f"{label}-learned-checkpoint",
                stratum_id="stratum-0",
            )
        assert evaluator.calls == []


def test_audit_bridge_rejects_stored_checkpoint_for_non_learned_treatment() -> None:
    config = _config()
    base_unit, target = _unit(config, comparator_gain=0.0)
    unit = replace(
        base_unit,
        lineage=replace(base_unit.lineage, model_checkpoint_hash="a" * 64),
    )
    match_identity, root_identity = _audit_identities(base_unit, target)
    evaluator = _MeasurementEvaluator(_measurement(delta_0=1.0, delta_h=1.0))

    with pytest.raises(ValueError, match="Non-learned policy treatment"):
        build_endpoint_audit_row(
            evaluator,
            unit=unit,
            target=target,
            audit_config=ScientificAuditConfig(),
            match_identity=match_identity,
            root_action_identity=root_identity,
            unit_id="non-learned-checkpoint",
            stratum_id="stratum-0",
        )
    assert evaluator.calls == []


def test_evaluator_protocol_has_no_persisted_comparator_input() -> None:
    signature = inspect.signature(IndependentEndpointEvaluator.evaluate)
    assert tuple(signature.parameters) == ("self", "lineage", "target", "pose_chain")
    assert "comparator" not in inspect.signature(_config().setup_target).parameters


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_candidate_config_hashes", ("a" * 15,)),
        ("expected_candidate_config_hashes", ("a" * 17,)),
        ("expected_rollout_config_hashes", ("b" * 63,)),
        ("expected_source_store_sha256", "1" * 16),
        ("expected_split_manifest_sha256", "2" * 65),
    ],
)
def test_config_rejects_noncanonical_identity_lengths(field: str, value: object) -> None:
    payload = _config().model_dump()
    payload[field] = value

    with pytest.raises(ValueError):
        OracleGtEndpointEvaluatorConfig.model_validate(payload)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("a" * 16, "a" * 64, True),
        ("a" * 64, "a" * 16, True),
        ("a" * 64, "a" * 64, True),
        ("a" * 15, "a" * 64, False),
        ("a" * 17, "a" * 64, False),
        ("a" * 16, "b" * 64, False),
    ],
)
def test_hash_matching_allows_only_exact_or_canonical_fingerprint_pairing(
    left: str,
    right: str,
    expected: bool,
) -> None:
    assert _hash_matches(left, right) is expected


def test_injected_repository_must_match_explicit_full_source_identity() -> None:
    config = _config()
    lineage, target = _inputs(config)

    class _WrongRepository:
        def resolve(self, lineage: StoredEvaluationLineage) -> ResolvedEndpointSource:
            return ResolvedEndpointSource(
                sample=_sample(),
                source_store_sha256="3" * 64,
                split_manifest_sha256="2" * 64,
            )

    evaluator = config.setup_target(source_repository=_WrongRepository())
    with pytest.raises(EndpointEvaluationBlockedError) as exc_info:
        evaluator.evaluate(lineage=lineage, target=target, pose_chain=_chain())

    assert exc_info.value.reason is EndpointEvaluationBlockedReason.SOURCE_IDENTITY_MISMATCH


def test_audit_bridge_keeps_thesis_endpoint_distinct_from_clamp_comparator_near_zero() -> None:
    config = _config()
    audit_config = ScientificAuditConfig()
    independent_comparator = 1e-14 / audit_config.comparator_epsilon
    unit, target = _unit(config, comparator_gain=independent_comparator)
    evaluator = _MeasurementEvaluator(_measurement(delta_0=1e-14, delta_h=0.0))
    match_identity, root_identity = _audit_identities(unit, target)

    row = build_endpoint_audit_row(
        evaluator,
        unit=unit,
        target=target,
        audit_config=audit_config,
        match_identity=match_identity,
        root_action_identity=root_identity,
        unit_id="unit-0",
        stratum_id="stratum-0",
    )

    assert row.evaluation_status is RowEvaluationStatus.COMPLETE
    assert row.endpoint_gain == pytest.approx(1e-14 / (1e-14 + audit_config.endpoint_epsilon))
    assert row.independent_comparator_gain == pytest.approx(independent_comparator)
    assert row.endpoint_gain != pytest.approx(row.independent_comparator_gain)
    assert row.equivalence_verdict is EquivalenceVerdict.PASS
    assert row.rollout_row_id == unit.lineage.rollout_row_id
    assert row.match_identity == match_identity
    assert row.source_store_sha256 == "1" * 64
    assert row.split_manifest_sha256 == "2" * 64
    assert row.raw_assets == (NamedSha256(name="target_mesh", sha256="6" * 64),)
    assert row.effect_eligible


def test_audit_bridge_rejects_root_action_identity_drift_before_evaluation() -> None:
    config = _config()
    unit, target = _unit(config, comparator_gain=0.0)
    match_identity, root_identity = _audit_identities(unit, target)
    evaluator = _MeasurementEvaluator(_measurement(delta_0=1.0, delta_h=1.0))

    with pytest.raises(ValueError, match="differs from the frozen policy match"):
        build_endpoint_audit_row(
            evaluator,
            unit=unit,
            target=target,
            audit_config=ScientificAuditConfig(),
            match_identity=match_identity,
            root_action_identity=replace(root_identity, sha256="5" * 64),
            unit_id="unit-identity-drift",
            stratum_id="stratum-0",
        )
    assert evaluator.calls == []


def test_audit_bridge_rejects_forged_persisted_context_before_evaluation() -> None:
    config = _config()
    unit, target = _unit(config, comparator_gain=0.0)
    match_identity, root_identity = _audit_identities(unit, target)
    forged = PolicyMatchIdentity.derive(
        treatment=match_identity.treatment,
        configs=match_identity.configs,
        root_action_set_sha256=match_identity.root_action_set_sha256,
        persisted_context_sha256="f" * 64,
        raw_asset_context_sha256=match_identity.raw_asset_context_sha256,
    )
    evaluator = _MeasurementEvaluator(_measurement(delta_0=1.0, delta_h=1.0))

    with pytest.raises(ValueError, match="Persisted pre-treatment context differs"):
        build_endpoint_audit_row(
            evaluator,
            unit=unit,
            target=target,
            audit_config=ScientificAuditConfig(),
            match_identity=forged,
            root_action_identity=root_identity,
            unit_id="unit-forged-context",
            stratum_id="stratum-0",
        )
    assert evaluator.calls == []


def test_audit_bridge_corrupt_comparator_changes_only_equivalence() -> None:
    config = _config()
    audit_config = ScientificAuditConfig()
    evaluator = _MeasurementEvaluator(_measurement(delta_0=2.0, delta_h=1.0))
    valid_unit, target = _unit(config, comparator_gain=0.5)
    corrupt_unit = replace(valid_unit, comparator=StoredEndpointComparator(gain=0.25))
    match_identity, root_identity = _audit_identities(valid_unit, target)

    valid = build_endpoint_audit_row(
        evaluator,
        unit=valid_unit,
        target=target,
        audit_config=audit_config,
        match_identity=match_identity,
        root_action_identity=root_identity,
        unit_id="valid",
        stratum_id="stratum-0",
    )
    corrupt = build_endpoint_audit_row(
        evaluator,
        unit=corrupt_unit,
        target=target,
        audit_config=audit_config,
        match_identity=match_identity,
        root_action_identity=root_identity,
        unit_id="corrupt",
        stratum_id="stratum-0",
    )

    assert len(evaluator.calls) == 2
    assert evaluator.calls[0] == evaluator.calls[1]
    assert (valid.delta_0, valid.delta_h, valid.endpoint_gain) == (
        corrupt.delta_0,
        corrupt.delta_h,
        corrupt.endpoint_gain,
    )
    assert valid.equivalence_verdict is EquivalenceVerdict.PASS
    assert corrupt.equivalence_verdict is EquivalenceVerdict.FAIL


def test_audit_bridge_retains_typed_blocked_unit() -> None:
    config = _config()
    unit, target = _unit(config, comparator_gain=0.0)
    match_identity, root_identity = _audit_identities(unit, target)

    class _BlockedEvaluator:
        def evaluate(
            self,
            *,
            lineage: StoredEvaluationLineage,
            target: StoredTarget,
            pose_chain: StoredSelectedPoseChain,
        ) -> IndependentEndpointMeasurement:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.DEPTH_MISSING,
                "selected depth unavailable",
            )

    row = build_endpoint_audit_row(
        _BlockedEvaluator(),
        unit=unit,
        target=target,
        audit_config=ScientificAuditConfig(),
        match_identity=match_identity,
        root_action_identity=root_identity,
        unit_id="blocked",
        stratum_id="stratum-0",
    )

    assert row.evaluation_status is RowEvaluationStatus.BLOCKED
    assert row.equivalence_verdict is EquivalenceVerdict.BLOCKED
    assert row.missing_reason == "depth_missing: selected depth unavailable"
    assert row.endpoint_gain is None
    assert not row.effect_eligible
    assert row.match_identity == match_identity


def test_root_only_early_termination_carries_delta_0() -> None:
    config = _config()
    lineage, target = _inputs(config)
    evaluator = config.setup_target(source_repository=_Repository(_sample()))

    measurement = evaluator.evaluate(lineage=lineage, target=target, pose_chain=_chain())

    assert measurement.delta_h == pytest.approx(measurement.delta_0)
    assert measurement.endpoint_gain == pytest.approx(0.0)
    assert measurement.achieved_steps == 0
    assert measurement.acquisition_path_length_m == pytest.approx(0.0)
    assert measurement.source_store_sha256 == "1" * 64
    assert {asset.name for asset in measurement.raw_assets} == {
        "scene_mesh",
        "target_mesh_crop",
        "target_obb_world",
    }


def test_selected_chain_renders_every_explicit_pose_despite_prefix_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    lineage, target = _inputs(config)
    evaluator = config.setup_target(source_repository=_Repository(_sample()))
    calls: list[tuple[int, ...]] = []
    original = CandidateDepthRenderer.render_compact_indices

    def _wrapped(
        self: CandidateDepthRenderer,
        sample: EfmSnippetView,
        candidates: object,
        compact_indices: object,
    ):
        calls.append(tuple(int(index) for index in compact_indices))  # type: ignore[arg-type]
        return original(self, sample, candidates, compact_indices)  # type: ignore[arg-type]

    monkeypatch.setattr(CandidateDepthRenderer, "render_compact_indices", _wrapped)
    measurement = evaluator.evaluate(
        lineage=lineage,
        target=target,
        pose_chain=_chain((0.25, 0.0, 0.0), (-0.25, 0.0, 0.0)),
    )

    assert calls == [(0, 1)]
    assert measurement.achieved_steps == 2
    assert measurement.acquisition_path_length_m == pytest.approx(0.75)
    assert np.isfinite(measurement.delta_0)
    assert np.isfinite(measurement.delta_h)
    assert np.isfinite(measurement.endpoint_gain)


def test_evaluator_fails_closed_on_protocol_and_config_drift() -> None:
    config = _config()
    lineage, target = _inputs(config)
    evaluator = config.setup_target(source_repository=_Repository(_sample()))

    with pytest.raises(EndpointEvaluationBlockedError) as protocol_error:
        evaluator.evaluate(
            lineage=replace(lineage, target_protocol_version=TargetInputProtocol.V1_OBSERVED.value),
            target=target,
            pose_chain=_chain(),
        )
    assert protocol_error.value.reason is EndpointEvaluationBlockedReason.UNSUPPORTED_TARGET_PROTOCOL

    with pytest.raises(EndpointEvaluationBlockedError) as config_error:
        evaluator.evaluate(
            lineage=replace(lineage, oracle_config_hash="f" * 16),
            target=target,
            pose_chain=_chain(),
        )
    assert config_error.value.reason is EndpointEvaluationBlockedReason.CONFIG_IDENTITY_MISMATCH


def test_evaluator_fails_closed_on_nonfinite_pose() -> None:
    config = _config()
    lineage, target = _inputs(config)
    evaluator = config.setup_target(source_repository=_Repository(_sample()))
    chain = _chain((0.0, 0.0, 0.0))
    corrupt = np.array(chain.selected_poses_world_cam, copy=True)
    corrupt[0, 0] = np.nan

    with pytest.raises(EndpointEvaluationBlockedError) as exc_info:
        evaluator.evaluate(
            lineage=lineage,
            target=target,
            pose_chain=replace(chain, selected_poses_world_cam=corrupt),
        )

    assert exc_info.value.reason is EndpointEvaluationBlockedReason.NONFINITE_GEOMETRY


@pytest.mark.skipif(
    os.environ.get("ARIA_NBV_RUN_REAL_ENDPOINT_TRACER") != "1",
    reason="Set ARIA_NBV_RUN_REAL_ENDPOINT_TRACER=1 to reopen the local pilot50 source assets.",
)
def test_real_pilot50_root_only_endpoint_tracer() -> None:
    """Trace one deterministic real source row through the independent evaluator."""

    repo_root = Path(__file__).resolve().parents[3]
    writer = RolloutDatasetWriterConfig.from_toml(
        repo_root / ".configs/generation/rollouts/paired/build_rollouts_v1_realistic.toml"
    )
    source = writer.source.model_copy(
        update={
            "limit": 1,
            "map_location": "cpu",
            "load_backbone": False,
            "verbosity": Verbosity.QUIET,
        }
    )
    renderer = writer.target_scorer.depth.renderer.model_copy(update={"device": "cpu", "verbosity": Verbosity.QUIET})
    depth = writer.target_scorer.depth.model_copy(
        update={"device": "cpu", "renderer": renderer, "verbosity": Verbosity.QUIET}
    )
    scorer = writer.target_scorer.model_copy(update={"depth": depth, "verbosity": Verbosity.QUIET})
    config = OracleGtEndpointEvaluatorConfig(
        source=source,
        source_manifest_path=repo_root / ".configs/evidence/rollouts/rollout_pilot50_source_manifest.json",
        expected_source_store_sha256="0cfa7252e18c1565263eafd994b34a0fa7b4630548f404b477624165421e0e72",
        expected_split_manifest_sha256="0c746d304c1feac2ea8976a0f6bbe94a5634ca70ca66339019ce5b0be0aff840",
        target_scorer=scorer,
        expected_candidate_config_hashes=(stable_config_hash(writer.candidate_mixture),),
        expected_rollout_config_hashes=(stable_config_hash(writer.recipes[0].policy),),
    )
    dataset = source.setup_target()
    sample = dataset[0]
    assert isinstance(sample, VinOfflineSample)
    assert sample.efm_snippet_view is not None
    snippet = sample.efm_snippet_view
    task = writer.oracle_target_task_sampler.setup_target().sample(sample).rows[0]
    trajectory_index = int(snippet.trajectory.time_ns.numel()) - 1
    frame_index = int(snippet.get_camera("rgb").num_frames) - 1
    source_manifest = read_rollout_source_manifest(config.source_manifest_path)
    source_row = source_manifest.rows[0]
    lineage = StoredEvaluationLineage(
        source_row_id=0,
        source_sample_index=source_row.sample_index,
        source_sample_key=source_row.sample_key,
        source_shard_id=source_row.source_shard_id,
        source_shard_row=source_row.source_shard_row,
        source_offline_store_manifest_hash=source_manifest.source_manifest_hash,
        split_manifest_hash=source_manifest.split_manifest_hash,
        split=source_row.split,
        scene_id=source_row.scene_id,
        snippet_id=source_row.snippet_id,
        rollout_row_id=0,
        rollout_id="real-pilot50-root-only",
        chain_id=0,
        root_time_ns=int(snippet.trajectory.time_ns[trajectory_index].item()),
        root_trajectory_index=trajectory_index,
        root_frame_index=frame_index,
        candidate_config_hash=stable_config_hash(writer.candidate_mixture),
        oracle_config_hash=stable_config_hash(scorer),
        rollout_config_hash=stable_config_hash(writer.recipes[0].policy),
        rollout_seed=writer.recipes[0].policy.seed,
        model_checkpoint_hash=None,
        selection_rng_state_hash=(
            f"seed-once:{writer.recipes[0].policy.seed}:split-manifest:{source_manifest.split_manifest_hash}"
        ),
        target_row_id=task.target_row_id,
        target_id=task.target_id,
        target_protocol_version=TargetInputProtocol.V0_GT_INPUT.value,
        target_crop_policy=scorer.target_crop_policy,
    )
    root_pose = rotate_yaw_cw90(snippet.trajectory.final_pose).tensor().reshape(12).detach().cpu().numpy()

    measurement = config.setup_target().evaluate(
        lineage=lineage,
        target=_stored_target(task),
        pose_chain=StoredSelectedPoseChain(
            root_pose_world=np.asarray(root_pose, dtype=np.float32),
            selected_poses_world_cam=np.empty((0, 12), dtype=np.float32),
            step_row_ids=(),
            selected_candidate_row_ids=(),
        ),
    )

    assert measurement.delta_h == pytest.approx(measurement.delta_0)
    assert measurement.endpoint_gain == pytest.approx(0.0)
    assert measurement.achieved_steps == 0
    assert measurement.source_store_sha256 == config.expected_source_store_sha256
    assert measurement.split_manifest_sha256 == config.expected_split_manifest_sha256
