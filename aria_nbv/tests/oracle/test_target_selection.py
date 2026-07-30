"""Tests for oracle target-task sampling."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import fields

import pytest
import torch

pytest.importorskip("efm3d")

from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras

from aria_nbv.data_handling import VinSnippetView
from aria_nbv.data_handling.vin_store.batch import CompactObbBlock
from aria_nbv.data_handling.vin_store.dataset import VinOfflineOracleBlock, VinOfflineSample
from aria_nbv.oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    OracleTargetTask,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    TargetTaskIdentityStatus,
)


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
    backbone_out: object | None = None,
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


def _oracle_sampler(**kwargs: object) -> OracleTargetTaskSampler:
    return OracleTargetTaskSampler(OracleTargetTaskSamplerConfig(**kwargs))


def test_oracle_target_task_sampler_config_has_only_selection_controls() -> None:
    assert set(OracleTargetTaskSamplerConfig.model_fields) == {
        "max_targets_per_sample",
        "policy",
        "seed",
    }


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
    assert first.diagnostic_summary()["num_identity_valid"] == 4
    assert len(first.selected_rows) == 3
    assert [row.target_id for row in first.selected_rows] == [row.target_id for row in second.selected_rows]
    assert all(row.selection_probability == pytest.approx(3.0 / 4.0) for row in first.selected_rows)
    assert all(row.identity_status == TargetTaskIdentityStatus.MATCHED.value for row in first.selected_rows)
    assert all(row.target_id.startswith(f"scene:snippet:{ORACLE_TARGET_TASK_SOURCE}:") for row in first.rows)
    assert all(row.descriptor.target_id != row.target_id for row in first.rows)


def test_oracle_target_task_sampler_keeps_duplicate_gt_geometry_as_distinct_tasks() -> None:
    sample = _sample(
        gt_obbs=_obb_block(
            [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [4.0, 0.0, 0.0]],
            sem_ids=[0, 0, 1],
            inst_ids=[10, 11, 12],
        )
    )

    result = _oracle_sampler(max_targets_per_sample=3, seed=0).sample(sample)

    assert len(result.rows) == 3
    assert result.diagnostic_summary()["num_identity_valid"] == 3
    assert len(result.selected_rows) == 3
    assert all(row.identity_status == TargetTaskIdentityStatus.MATCHED.value for row in result.rows)
    assert len({row.source_index for row in result.rows}) == 3
    assert "num_ambiguous_identity" not in result.diagnostic_summary()


def test_oracle_target_task_contains_only_domain_fields() -> None:
    sample = _sample(
        gt_obbs=_obb_block([[0.0, 0.0, 0.0]], probs=[0.05], box_size=0.0),
        points=[],
    )

    row = _oracle_sampler(max_targets_per_sample=1).sample(sample).selected_rows[0]

    assert {field.name for field in fields(OracleTargetTask)} == {
        "source_index",
        "target_row_id",
        "target_id",
        "descriptor",
        "inst_id",
        "confidence",
        "identity_status",
        "selected_rank",
        "selection_probability",
    }
    assert row.identity_status == TargetTaskIdentityStatus.MATCHED.value
    assert row.confidence == pytest.approx(0.05)


def test_oracle_target_task_sampler_rejects_non_offline_sample_input() -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]]))

    assert not hasattr(sample, "to_vin_oracle_batch")
    with pytest.raises(TypeError, match="VinOfflineSample"):
        _oracle_sampler().sample(sample.vin_snippet)  # type: ignore[arg-type]
