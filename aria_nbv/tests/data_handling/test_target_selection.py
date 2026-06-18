"""Tests for actor-visible top-K target selection."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np
import pytest
import torch

pytest.importorskip("efm3d")

from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras

from aria_nbv.data_handling import (
    ORACLE_TARGET_TASK_SOURCE,
    TARGET_INVALID_REASON_CODES,
    ActorVisibleTargetSelector,
    CompactObbBlock,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    TargetSelectionPolicy,
    TargetSelectorConfig,
    TargetSourceMode,
    TargetTaskIdentityStatus,
    VinSnippetView,
)
from aria_nbv.data_handling import _target_selection as target_selection_module
from aria_nbv.data_handling._offline_dataset import VinOfflineOracleBlock, VinOfflineSample
from aria_nbv.vin.types import EvlBackboneOutput


def _poses(translations: list[list[float]]) -> PoseTW:
    rotation = torch.eye(3, dtype=torch.float32).expand(len(translations), 3, 3).clone()
    return PoseTW.from_Rt(rotation, torch.tensor(translations, dtype=torch.float32))


def _obb_block(
    centers: list[list[float]],
    *,
    sem_ids: list[int] | None = None,
    inst_ids: list[int] | None = None,
    probs: list[float] | None = None,
    box_size: float = 100.0,
    bb2: torch.Tensor | None = None,
) -> CompactObbBlock:
    count = len(centers)
    sem = sem_ids or [0] * count
    inst = inst_ids or list(range(count))
    conf = probs or [0.9] * count
    bb3 = torch.tensor([[-0.5, 0.5, -0.5, 0.5, -0.5, 0.5]] * count, dtype=torch.float32)
    bb2 = (
        bb2.to(dtype=torch.float32)
        if bb2 is not None
        else torch.tensor([[10.0, 10.0 + box_size, 10.0, 10.0 + box_size]] * count, dtype=torch.float32)
    )
    obbs = ObbTW.from_lmc(
        bb3_object=bb3,
        bb2_rgb=bb2,
        bb2_slaml=bb2,
        bb2_slamr=bb2,
        T_world_object=_poses(centers),
        sem_id=torch.tensor(sem, dtype=torch.int64),
        inst_id=torch.tensor(inst, dtype=torch.int64),
        prob=torch.tensor(conf, dtype=torch.float32),
    )
    return CompactObbBlock(obbs=obbs.tensor(), sem_id_to_name={0: "chair", 1: "table", 2: "sofa"})


def _cameras(count: int = 1) -> PerspectiveCameras:
    return PerspectiveCameras(
        R=torch.eye(3, dtype=torch.float32).expand(count, 3, 3).clone(),
        T=torch.zeros(count, 3, dtype=torch.float32),
        focal_length=torch.full((count, 2), 50.0, dtype=torch.float32),
        principal_point=torch.full((count, 2), 2.0, dtype=torch.float32),
        image_size=torch.full((count, 2), 4.0, dtype=torch.float32),
        in_ndc=False,
    )


def _sample(
    *,
    detected_obbs: CompactObbBlock | None = None,
    gt_obbs: CompactObbBlock | None = None,
    backbone_out: EvlBackboneOutput | None = None,
    points: list[list[float]] | None = None,
) -> VinOfflineSample:
    point_tensor = torch.tensor(points or [], dtype=torch.float32).reshape(-1, 3)
    vin_snippet = VinSnippetView(
        points_world=point_tensor,
        lengths=torch.tensor([point_tensor.shape[0]], dtype=torch.int64),
        t_world_rig=_poses([[0.0, 0.0, 0.0]]),
    )
    oracle = VinOfflineOracleBlock(
        candidate_poses_world_cam=_poses([[0.0, 0.0, 0.0]]),
        reference_pose_world_rig=_poses([[0.0, 0.0, 0.0]]),
        candidate_count=1,
        rri=torch.zeros(1, dtype=torch.float32),
        pm_dist_before=torch.zeros(1, dtype=torch.float32),
        pm_dist_after=torch.zeros(1, dtype=torch.float32),
        pm_acc_before=torch.zeros(1, dtype=torch.float32),
        pm_comp_before=torch.zeros(1, dtype=torch.float32),
        pm_acc_after=torch.zeros(1, dtype=torch.float32),
        pm_comp_after=torch.zeros(1, dtype=torch.float32),
        p3d_cameras=_cameras(),
    )
    return VinOfflineSample(
        sample_key="scene/snippet/0",
        scene_id="scene",
        snippet_id="snippet",
        vin_snippet=vin_snippet,
        oracle=oracle,
        detected_obbs=detected_obbs,
        gt_obbs=gt_obbs,
        backbone_out=backbone_out,
    )


def _selector(**kwargs: object) -> ActorVisibleTargetSelector:
    config = TargetSelectorConfig(min_support_points=1, support_saturation_points=10, **kwargs)
    return ActorVisibleTargetSelector(config)


def _oracle_sampler(**kwargs: object) -> OracleTargetTaskSampler:
    return OracleTargetTaskSampler(OracleTargetTaskSamplerConfig(**kwargs))


def test_oracle_target_task_sampler_selects_seeded_uniform_cap() -> None:
    sample = _sample(
        gt_obbs=_obb_block(
            [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [6.0, 0.0, 0.0], [9.0, 0.0, 0.0]],
            sem_ids=[0, 1, 2, 0],
            inst_ids=[10, 11, 12, 13],
        )
    )

    first = _oracle_sampler(max_targets_per_sample=3, seed=7).sample(sample)
    second = _oracle_sampler(max_targets_per_sample=3, seed=7).sample(sample)

    assert first.source == ORACLE_TARGET_TASK_SOURCE
    assert len(first.rows) == 4
    assert len(first.identity_valid_rows) == 4
    assert len(first.selected_rows) == 3
    assert [row.target_id for row in first.selected_rows] == [row.target_id for row in second.selected_rows]
    assert all(row.selection_probability == pytest.approx(3.0 / 4.0) for row in first.selected_rows)
    assert {row.selection_seed for row in first.selected_rows} == {7}
    assert all(row.identity_status == TargetTaskIdentityStatus.MATCHED.value for row in first.selected_rows)
    assert {row.source for row in first.rows} == {ORACLE_TARGET_TASK_SOURCE}
    assert all(row.target_id.startswith(f"scene:snippet:{ORACLE_TARGET_TASK_SOURCE}:") for row in first.rows)


def test_oracle_target_task_sampler_rejects_ambiguous_duplicate_gt_identity() -> None:
    sample = _sample(
        gt_obbs=_obb_block(
            [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [4.0, 0.0, 0.0]],
            sem_ids=[0, 0, 1],
            inst_ids=[10, 11, 12],
        )
    )

    result = _oracle_sampler(max_targets_per_sample=3, seed=0).sample(sample)

    assert len(result.rows) == 3
    assert len(result.identity_valid_rows) == 1
    assert len(result.selected_rows) == 1
    assert sum(row.identity_status == TargetTaskIdentityStatus.AMBIGUOUS.value for row in result.rows) == 2
    assert result.selected_rows[0].source_index == 2


def test_oracle_target_task_sampler_rejects_identity_when_iou_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]]))

    def _raise_iou(*_args: object, **_kwargs: object) -> torch.Tensor:
        raise RuntimeError("forced iou failure")

    monkeypatch.setattr(target_selection_module, "obb_iou3d", _raise_iou)

    result = _oracle_sampler(max_targets_per_sample=1).sample(sample)

    assert len(result.rows) == 1
    assert result.rows[0].identity_status == TargetTaskIdentityStatus.UNMATCHED.value
    assert not result.rows[0].identity_valid
    assert result.identity_valid_rows == ()
    assert result.selected_rows == ()


def test_oracle_target_task_sampler_threshold_sweep_reports_identity_coverage() -> None:
    sample = _sample(
        gt_obbs=_obb_block(
            [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [5.0, 0.0, 0.0]],
            sem_ids=[0, 0, 1],
            inst_ids=[10, 11, 12],
        )
    )

    result = _oracle_sampler(
        identity_iou_thresholds=(0.25,),
        identity_ambiguity_gaps=(0.0, 0.05),
    ).sample(sample)
    cells = result.threshold_sweep()

    assert [(cell.identity_ambiguity_gap, cell.identity_valid_count) for cell in cells] == [(0.0, 1), (0.05, 1)]
    assert result.diagnostic_summary()["num_ambiguous_identity"] == 2


def test_oracle_target_task_sampler_preserves_audit_fields_without_support_or_projection_gate() -> None:
    sample = _sample(
        gt_obbs=_obb_block([[0.0, 0.0, 0.0]], probs=[0.05], box_size=0.0),
        points=[],
    )

    row = _oracle_sampler(max_targets_per_sample=1).sample(sample).selected_rows[0]

    assert row.identity_valid
    assert row.projected_area_pixels == 0.0
    assert row.semidense_support_count == 0
    assert row.effective_support_count == 0.0
    assert row.confidence == pytest.approx(0.05)
    assert row.target_root_error is None
    assert row.max_candidate_gain is None
    assert row.headroom_band is None


def test_oracle_target_task_sampler_rejects_vin_oracle_batch_input() -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]]))

    with pytest.raises(TypeError, match="VinOfflineSample"):
        _oracle_sampler().sample(sample.to_vin_oracle_batch())


def test_greedy_top_k_returns_deterministic_deficit_ranked_rows() -> None:
    sample = _sample(
        detected_obbs=_obb_block([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [6.0, 0.0, 0.0]]),
        points=[
            [0.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [3.1, 0.0, 0.0],
            [3.2, 0.0, 0.0],
            [3.3, 0.0, 0.0],
            [3.4, 0.0, 0.0],
            [6.0, 0.0, 0.0],
            [6.1, 0.0, 0.0],
            [6.2, 0.0, 0.0],
        ],
    )

    result = _selector(k=2).select(sample)

    assert result.source == "detected_obbs"
    assert [row.source_index for row in result.selected_rows] == [0, 2]
    assert [row.selected_rank for row in result.selected_rows] == [0, 1]
    assert result.selected_rows[0].score >= result.selected_rows[1].score
    assert all(row.eligible for row in result.selected_rows)


def test_temperature_softmax_top_k_is_seeded_and_samples_distinct_rows() -> None:
    sample = _sample(
        detected_obbs=_obb_block([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [6.0, 0.0, 0.0]]),
        points=[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [6.0, 0.0, 0.0]],
    )

    first = _selector(k=2, policy=TargetSelectionPolicy.TEMPERATURE_SOFTMAX_TOP_K, seed=42).select(sample)
    second = _selector(k=2, policy=TargetSelectionPolicy.TEMPERATURE_SOFTMAX_TOP_K, seed=42).select(sample)

    assert [row.target_id for row in first.selected_rows] == [row.target_id for row in second.selected_rows]
    assert len({row.source_index for row in first.selected_rows}) == 2
    for row in first.selected_rows:
        assert row.selection_probability is not None
        assert row.selection_log_probability is not None
        assert row.selection_entropy is not None


def test_invalid_low_support_target_is_hard_masked() -> None:
    sample = _sample(detected_obbs=_obb_block([[0.0, 0.0, 0.0]]), points=[])

    result = _selector(k=1).select(sample)

    assert result.selected_rows == ()
    assert len(result.rows) == 1
    row = result.rows[0]
    assert not row.eligible
    assert row.primary_invalid_reason == TARGET_INVALID_REASON_CODES["TARGET_SUPPORT_TOO_LOW"]


def test_v1_refuses_gt_only_source() -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]]), points=[[0.0, 0.0, 0.0]])

    result = _selector(k=1).select(sample)

    assert result.rows == ()
    assert result.selected_rows == ()
    assert any("refused GT OBBs" in warning for warning in result.warnings)


def test_selector_falls_back_to_backbone_obbs_when_detected_block_is_missing() -> None:
    backbone = EvlBackboneOutput(
        t_world_voxel=_poses([[0.0, 0.0, 0.0]]),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32),
        obb_pred_viz=ObbTW(_obb_block([[0.0, 0.0, 0.0]]).obbs),
        obb_pred_sem_id_to_name={0: "chair"},
        pts_world=torch.tensor([[[0.0, 0.0, 0.0]]], dtype=torch.float32),
        counts=torch.ones((1, 1), dtype=torch.int64),
    )
    sample = _sample(backbone_out=backbone, points=[])

    result = _selector(k=1).select(sample)

    assert result.source == "backbone.obb_pred_viz"
    assert len(result.selected_rows) == 1


def test_selector_resolves_sparse_backbone_semantic_names_after_payload_decode() -> None:
    source = EvlBackboneOutput(
        t_world_voxel=_poses([[0.0, 0.0, 0.0]]),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32),
        obb_pred_viz=ObbTW(_obb_block([[0.0, 0.0, 0.0]], sem_ids=[28]).obbs),
        obb_pred_sem_id_to_name={28: "window"},
        pts_world=torch.tensor([[[0.0, 0.0, 0.0]]], dtype=torch.float32),
        counts=torch.ones((1, 1), dtype=torch.int64),
    )
    backbone = EvlBackboneOutput.from_serializable(source.to_serializable(), device=torch.device("cpu"))
    sample = _sample(backbone_out=backbone, points=[])

    result = _selector(k=1).select(sample)

    assert result.source == "backbone.obb_pred_viz"
    assert result.selected_rows[0].class_name == "window"


def test_backbone_obb_without_2d_projection_can_use_3d_support() -> None:
    backbone = EvlBackboneOutput(
        t_world_voxel=_poses([[0.0, 0.0, 0.0]]),
        voxel_extent=torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32),
        obb_pred_viz=ObbTW(_obb_block([[0.0, 0.0, 0.0]], box_size=0.0).obbs),
        obb_pred_sem_id_to_name={0: "chair"},
        pts_world=torch.tensor([[[0.0, 0.0, 0.0]]], dtype=torch.float32),
        counts=torch.ones((1, 1), dtype=torch.int64),
    )
    sample = _sample(backbone_out=backbone, points=[])

    result = _selector(k=1).select(sample)

    assert len(result.selected_rows) == 1
    assert result.selected_rows[0].projected_area_pixels == 0.0
    assert 0.0 < result.selected_rows[0].visibility_score < 1.0


def test_missing_projection_is_penalized_against_visible_supported_target() -> None:
    sample = _sample(
        detected_obbs=_obb_block([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]], box_size=0.0),
        points=[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]],
    )
    visible = _obb_block([[3.0, 0.0, 0.0]], box_size=100.0)
    detected = torch.cat([sample.detected_obbs.obbs[:1], visible.obbs], dim=0)
    sample.detected_obbs = CompactObbBlock(obbs=detected, sem_id_to_name={0: "chair"})

    result = _selector(k=2).select(sample)

    assert result.rows[0].projected_area_pixels == 0.0
    assert result.rows[0].visibility_score == pytest.approx(0.35)
    assert result.rows[1].visibility_score == pytest.approx(1.0)
    assert result.selected_rows[0].source_index == 1


def test_projected_visibility_can_still_be_required() -> None:
    sample = _sample(
        detected_obbs=_obb_block([[0.0, 0.0, 0.0]], box_size=0.0),
        points=[[0.0, 0.0, 0.0]],
    )

    result = _selector(k=1, require_projected_visibility=True).select(sample)

    assert result.selected_rows == ()
    assert result.rows[0].primary_invalid_reason == TARGET_INVALID_REASON_CODES["NO_PROJECTED_VISIBILITY"]


def test_selector_rejects_vin_oracle_batch_input() -> None:
    sample = _sample(detected_obbs=_obb_block([[0.0, 0.0, 0.0]]), points=[[0.0, 0.0, 0.0]])

    with pytest.raises(TypeError, match="VinOfflineSample"):
        _selector(k=1).select(sample.to_vin_oracle_batch())


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires CUDA")
def test_selector_handles_cuda_reference_pose_with_cpu_obbs() -> None:
    sample = _sample(detected_obbs=_obb_block([[0.0, 0.0, 0.0]]), points=[[0.0, 0.0, 0.0]])
    sample.oracle.reference_pose_world_rig = PoseTW(sample.oracle.reference_pose_world_rig.tensor().cuda())

    result = _selector(k=1).select(sample)

    assert len(result.selected_rows) == 1
    assert result.selected_rows[0].relative_pose_reference_object == pytest.approx(
        (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    )


def test_selected_target_matches_compatible_gt_obb() -> None:
    detected = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[10])
    gt = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[99])
    sample = _sample(detected_obbs=detected, gt_obbs=gt, points=[[0.0, 0.0, 0.0]])

    row = _selector(k=1).select(sample).selected_rows[0]

    assert row.gt_label_valid
    assert row.gt_match_status == "matched"
    assert row.gt_target_row_id == 0
    assert np.isclose(row.gt_match_iou, 1.0)
    assert np.isclose(row.gt_match_score, 1.0)


def test_gt_match_score_is_geometry_only_after_target_eligibility() -> None:
    detected = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[10], box_size=0.0)
    gt = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[99])
    sample = _sample(detected_obbs=detected, gt_obbs=gt, points=[[0.0, 0.0, 0.0]])

    row = _selector(k=1).select(sample).selected_rows[0]

    assert row.gt_label_valid
    assert row.gt_match_iou == pytest.approx(1.0)
    assert row.visibility_score < 1.0
    assert row.gt_match_score == pytest.approx(row.gt_match_iou)


def test_projected_area_is_clipped_visible_image_overlap() -> None:
    boxes = torch.tensor([[-20.0, 20.0, -10.0, 30.0]], dtype=torch.float32)
    sample = _sample(
        detected_obbs=_obb_block([[0.0, 0.0, 0.0]], bb2=boxes),
        points=[[0.0, 0.0, 0.0]],
    )

    row = _selector(k=1).select(sample).selected_rows[0]

    assert row.projected_area_pixels == pytest.approx(20.0 * 30.0)
    assert row.projected_area_fraction == pytest.approx((20.0 * 30.0) / (240.0 * 240.0))


def test_duplicate_predicted_targets_make_gt_match_ambiguous() -> None:
    detected = _obb_block([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]], sem_ids=[1, 1], inst_ids=[10, 11])
    gt = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[99])
    sample = _sample(detected_obbs=detected, gt_obbs=gt, points=[[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]])

    selected = _selector(k=2).select(sample).selected_rows

    assert len(selected) == 2
    assert {row.gt_match_status for row in selected} == {"ambiguous_pred_to_gt"}
    assert not any(row.gt_label_valid for row in selected)
    assert {row.primary_invalid_reason for row in selected} == {TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"]}
    assert not any(row.invalid_reason_bitset & (1 << TARGET_INVALID_REASON_CODES["VALID"]) for row in selected)


def test_selected_target_without_gt_match_is_not_label_valid() -> None:
    detected = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[10])
    gt = _obb_block([[10.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[99])
    sample = _sample(detected_obbs=detected, gt_obbs=gt, points=[[0.0, 0.0, 0.0]])

    row = _selector(k=1).select(sample).selected_rows[0]

    assert not row.gt_label_valid
    assert row.gt_match_status == "unmatched_gt"
    assert row.primary_invalid_reason == TARGET_INVALID_REASON_CODES["TARGET_GT_UNMATCHED"]
    assert not row.invalid_reason_bitset & (1 << TARGET_INVALID_REASON_CODES["VALID"])


def test_v0_gt_sanity_source_is_opt_in() -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]]), points=[[0.0, 0.0, 0.0]])

    result = _selector(k=1, source_mode=TargetSourceMode.V0_GT_SANITY).select(sample)

    assert result.source == "gt_obbs_v0_sanity"
    assert len(result.selected_rows) == 1
    assert result.selected_rows[0].gt_label_valid
    assert result.selected_rows[0].gt_match_status == "v0_gt_input"


def test_target_selection_diagnostic_summary_counts_selection_strata() -> None:
    detected = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[10], box_size=0.0)
    gt = _obb_block([[0.0, 0.0, 0.0]], sem_ids=[1], inst_ids=[99])
    sample = _sample(detected_obbs=detected, gt_obbs=gt, points=[[0.0, 0.0, 0.0]])

    summary = _selector(k=1).select(sample).diagnostic_summary()

    assert summary["num_rows"] == 1
    assert summary["num_selected"] == 1
    assert summary["num_gt_label_valid"] == 1
    assert summary["num_missing_projection"] == 1
    assert summary["mean_effective_support_count"] == pytest.approx(1.0)
