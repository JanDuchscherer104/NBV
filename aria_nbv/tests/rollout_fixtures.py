"""Test-only rollout Zarr record fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch
import trimesh  # type: ignore[import-untyped]
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.data_handling import TARGET_INVALID_REASON_VERSION
from aria_nbv.pose_generation.candidate_generation import CandidateViewGeneratorConfig
from aria_nbv.pose_generation.candidate_mixture import candidate_position_id
from aria_nbv.pose_generation.counterfactuals import (
    CounterfactualCandidateEvaluation,
    CounterfactualMetricBundle,
    CounterfactualPoseGenerator,
    CounterfactualPoseGeneratorConfig,
    CounterfactualRolloutResult,
    CounterfactualSelectionPolicy,
    CounterfactualTrajectory,
)
from aria_nbv.pose_generation.target_counterfactuals import TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
from aria_nbv.pose_generation.types import CandidatePositionMode, SamplingStrategy
from aria_nbv.rollouts import INVALID_REASON_VERSION, RolloutLineage, RolloutZarrRecord
from aria_nbv.utils.fingerprints import stable_config_hash

if TYPE_CHECKING:
    from typing import Any

    from aria_nbv.utils import BaseConfig


def build_rollout_records(
    *,
    horizon: int = 2,
    num_samples: int = 8,
    seed: int = 0,
) -> list[RolloutZarrRecord]:
    """Build real-looking fixture rollout records for store tests."""

    records: list[RolloutZarrRecord] = []
    for source_row_id, policy in enumerate(
        (
            CounterfactualSelectionPolicy.ORACLE_GREEDY,
            CounterfactualSelectionPolicy.RANDOM_VALID,
            CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
        )
    ):
        cfg = CounterfactualPoseGeneratorConfig(
            candidate_config=CandidateViewGeneratorConfig(
                num_samples=num_samples,
                min_radius=0.5,
                max_radius=0.5,
                ensure_collision_free=False,
                ensure_free_space=False,
                min_distance_to_mesh=0.0,
                sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
                view_max_azimuth_deg=0.0,
                view_max_elevation_deg=0.0,
                device="cpu",
                seed=seed,
                verbosity=0,
                is_debug=True,
            ),
            horizon=horizon,
            branch_factor=1,
            selection_policy=policy,
            selection_temperature=1.0,
            seed=seed,
            verbosity=0,
        )
        mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        result = CounterfactualPoseGenerator(cfg).generate(
            reference_pose=_identity_pose(),
            gt_mesh=mesh,
            mesh_verts=torch.as_tensor(mesh.vertices, dtype=torch.float32),
            mesh_faces=torch.as_tensor(mesh.faces, dtype=torch.int64),
            camera_calib_template=_dummy_camera(),
            occupancy_extent=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
            score_candidates=_fixture_scores,
        )
        _attach_fixture_candidate_provenance(result)
        records.append(
            RolloutZarrRecord(
                result=result,
                rollout_id_prefix=f"fixture-{policy.value}",
                lineage=RolloutLineage(
                    scene_id="fixture_box",
                    snippet_id="smoke",
                    mesh_version="fixture-mesh-v1",
                    candidate_config_hash=_config_hash(cfg.candidate_config),
                    oracle_config_hash="fixture-oracle",
                    rollout_config_hash=_config_hash(cfg),
                    branch_schedule_id=cfg.branch_schedule_id,
                    random_seed=seed,
                    source_cache_version="7",
                    source_row_id=source_row_id,
                    source_sample_index=source_row_id,
                    source_sample_key=f"fixture:smoke:{source_row_id}",
                    split="train",
                    source_shard_id="vin-shard-000000",
                    source_shard_row=source_row_id,
                    source_offline_store_manifest_hash="fixture-source-manifest",
                    split_manifest_hash="fixture-split-manifest",
                    selection_rng_state_hash="fixture-rng",
                    target_protocol_version="v1-observed",
                    target_crop_policy=TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1,
                    reason_code_version=INVALID_REASON_VERSION,
                    target_row_id=source_row_id,
                    target_id=f"fixture-target-{source_row_id}",
                    target_selection_policy="fixture_top_k",
                    target_selection_rank=source_row_id,
                    target_selection_score=1.0 - 0.1 * source_row_id,
                    target_source="fixture_obbs",
                    target_source_index=source_row_id,
                    target_sem_id=source_row_id + 1,
                    target_inst_id=1000 + source_row_id,
                    target_class_name="fixture_object",
                    target_confidence=0.9,
                    target_projected_area_pixels=512.0,
                    target_projected_area_fraction=512.0 / (240.0 * 240.0),
                    target_semidense_support_count=7,
                    target_evl_support_count=5,
                    target_effective_support_count=12.0,
                    target_visibility_score=0.8,
                    target_support_score=1.0,
                    target_deficit_score=0.9,
                    target_center_world=(float(source_row_id), 0.0, 0.5),
                    target_extents=(0.4, 0.5, 0.6),
                    target_pose_world_object=(
                        1.0,
                        0.0,
                        0.0,
                        0.0,
                        1.0,
                        0.0,
                        0.0,
                        0.0,
                        1.0,
                        float(source_row_id),
                        0.0,
                        0.5,
                    ),
                    target_invalid_reason_bitset=1,
                    target_primary_invalid_reason=0,
                    target_reason_code_version=TARGET_INVALID_REASON_VERSION,
                    matched_gt_target_row_id=100 + source_row_id,
                    matched_gt_target_id=f"fixture-gt-target-{source_row_id}",
                    gt_match_iou=0.9,
                    gt_match_score=0.9,
                    gt_match_status="matched",
                ),
            )
        )
    return records


def _attach_fixture_candidate_provenance(result: CounterfactualRolloutResult) -> None:
    for trajectory in result.trajectories:
        for step in trajectory.steps:
            mask = step.candidates.mask_valid.detach().cpu().reshape(-1)
            n = int(mask.shape[0])
            step.candidates.strategy_id = torch.arange(n, dtype=torch.int64) % 4
            step.candidates.position_id = torch.full(
                (n,),
                candidate_position_id(CandidatePositionMode.FORWARD_LOCAL),
                dtype=torch.int64,
            )
            step.candidates.mixture_id = torch.arange(n, dtype=torch.int64) % 2
            step.candidates.sampler_probability = torch.full((n,), 1.0 / float(max(n, 1)), dtype=torch.float32)
            step.candidates.extras.update(
                {
                    "min_distance_to_mesh": torch.linspace(0.25, 0.25 + 0.01 * max(n - 1, 0), n),
                    "path_min_clearance_m": torch.linspace(0.15, 0.15 + 0.01 * max(n - 1, 0), n),
                    "path_collision_mask": torch.zeros(n, dtype=torch.bool),
                    "free_space_margin_m": torch.full((n,), 1.0, dtype=torch.float32),
                    "motion_step_length_m": torch.linspace(0.5, 0.5 + 0.01 * max(n - 1, 0), n),
                    "motion_height_delta_m": torch.zeros(n, dtype=torch.float32),
                    "motion_backward_step_m": torch.zeros(n, dtype=torch.float32),
                    "motion_yaw_delta_rad": torch.zeros(n, dtype=torch.float32),
                    "target_distance_m": torch.linspace(1.0, 1.0 + 0.01 * max(n - 1, 0), n),
                    "target_bearing_yaw_rad": torch.zeros(n, dtype=torch.float32),
                }
            )
            step.selected_depth_m = torch.full((240, 240), 1.0 + float(step.step_index), dtype=torch.float32)
            step.selected_depth_valid_mask = torch.ones((240, 240), dtype=torch.bool)
            step.selected_depth_focal_px = (120.0, 120.0)
            step.selected_depth_principal_point_px = (120.0, 120.0)
            step.selected_depth_image_size_hw = (240, 240)
            valid_count = int(mask.sum().item())
            step.target_eval_current_points_world = torch.tensor(
                [[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.0, 0.1, 0.0]],
                dtype=torch.float32,
            )
            step.target_eval_candidate_points_world = torch.zeros((valid_count, 2, 3), dtype=torch.float32)
            step.target_eval_candidate_point_lengths = torch.full((valid_count,), 2, dtype=torch.long)
            for valid_index in range(valid_count):
                step.target_eval_candidate_points_world[valid_index, :, :] = torch.tensor(
                    [[float(valid_index), 0.0, 0.0], [float(valid_index), 0.1, 0.0]],
                    dtype=torch.float32,
                )
            step.target_eval_crop_policy = TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1
            step.target_eval_voxel_size_m = 0.02
            step.target_eval_max_points = 50_000


def _config_hash(config: BaseConfig) -> str:
    return stable_config_hash(config)


def _identity_pose() -> PoseTW:
    return PoseTW(
        torch.tensor(
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            dtype=torch.float32,
        )
    )


def _dummy_camera() -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0]),
        height=torch.tensor([64.0]),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]]),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([64.0]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )


def _fixture_scores(
    result: Any,
    trajectory: CounterfactualTrajectory,
    step_index: int,
) -> CounterfactualCandidateEvaluation:
    del trajectory
    valid_poses = result.poses_world_cam()
    centers = valid_poses.t.reshape(-1, 3)
    target_rri = torch.linspace(0.1, 0.1 * centers.shape[0], centers.shape[0], device=centers.device)
    target_rri = target_rri + float(step_index)
    target_root_gain = target_rri + 10.0
    return CounterfactualCandidateEvaluation(
        scores=target_root_gain,
        score_label="target_root_gain",
        metrics=CounterfactualMetricBundle(
            rri=target_rri,
            scene_rri=target_rri,
            target_rri=target_rri,
            scene_root_gain=target_root_gain / 2.0,
            target_root_gain=target_root_gain,
            scene_log_error_gain=target_rri / 3.0,
            target_log_error_gain=target_rri / 2.0,
            scene_pm_dist_before=target_rri + 1.0,
            scene_pm_dist_after=target_rri + 0.5,
            target_pm_dist_before=target_rri + 2.0,
            target_pm_dist_after=target_rri + 1.0,
            target_current_support=torch.full_like(target_rri, 3.0),
            target_candidate_support=torch.full_like(target_rri, 2.0),
        ),
    )
