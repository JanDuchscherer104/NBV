"""Tests for VinOracleBatch collation with variable candidate counts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling import VinOracleBatch, VinSnippetView
from aria_nbv.data_handling.vin_store.batch import CompactObbBlock, CompactTrajectoryBlock
from aria_nbv.lightning.lit_module import VinLightningModule, VinLightningModuleConfig
from aria_nbv.rri_metrics.ordinal import RriOrdinalBinner
from aria_nbv.utils import Stage
from aria_nbv.vin.models.scene_myopic import VinModelV3Config
from aria_nbv.vin.models.target_myopic import TargetConditionedMyopicScorer, TargetConditionedMyopicScorerConfig
from aria_nbv.vin.ordinal import coral_expected_from_logits, coral_logits_to_prob
from aria_nbv.vin.types import EvlBackboneOutput, VinPrediction

pytest.importorskip("pytorch_lightning")
pytorch3d_cameras = pytest.importorskip("pytorch3d.renderer.cameras")
PerspectiveCameras = pytorch3d_cameras.PerspectiveCameras


def _identity_pose(num: int) -> PoseTW:
    eye = torch.eye(3, dtype=torch.float32).reshape(1, 9).repeat(num, 1)
    t = torch.zeros((num, 3), dtype=torch.float32)
    return PoseTW(torch.cat([eye, t], dim=-1))


def _indexed_pose(num: int, *, offset: float = 0.0) -> PoseTW:
    eye = torch.eye(3, dtype=torch.float32).reshape(1, 9).repeat(num, 1)
    t = torch.zeros((num, 3), dtype=torch.float32)
    t[:, 0] = torch.arange(num, dtype=torch.float32) + float(offset)
    return PoseTW(torch.cat([eye, t], dim=-1))


def _make_cameras(num: int) -> PerspectiveCameras:
    rot = torch.eye(3, dtype=torch.float32).unsqueeze(0).repeat(num, 1, 1)
    trans = torch.zeros((num, 3), dtype=torch.float32)
    focal = torch.full((num, 2), 250.0, dtype=torch.float32)
    principal = torch.zeros((num, 2), dtype=torch.float32)
    image_size = torch.tensor([[640.0, 480.0]], dtype=torch.float32).expand(num, -1)
    return PerspectiveCameras(
        R=rot,
        T=trans,
        focal_length=focal,
        principal_point=principal,
        image_size=image_size,
        in_ndc=False,
    )


def _make_indexed_cameras(num: int, *, offset: float = 0.0) -> PerspectiveCameras:
    rot = torch.eye(3, dtype=torch.float32).unsqueeze(0).repeat(num, 1, 1)
    trans = torch.zeros((num, 3), dtype=torch.float32)
    trans[:, 0] = torch.arange(num, dtype=torch.float32) + float(offset)
    focal = torch.full((num, 2), 250.0, dtype=torch.float32)
    principal = torch.zeros((num, 2), dtype=torch.float32)
    image_size = torch.tensor([[640.0, 480.0]], dtype=torch.float32).expand(num, -1)
    return PerspectiveCameras(
        R=rot,
        T=trans,
        focal_length=focal,
        principal_point=principal,
        image_size=image_size,
        in_ndc=False,
    )


def _make_backbone() -> EvlBackboneOutput:
    t_world_voxel = _identity_pose(1)
    voxel_extent = torch.tensor([0.0, 1.0, 0.0, 1.0, 0.0, 1.0], dtype=torch.float32)
    occ = torch.zeros((1, 1, 2, 2, 2), dtype=torch.float32)
    counts = torch.zeros((1, 2, 2, 2), dtype=torch.int64)
    pts_world = torch.zeros((1, 8, 3), dtype=torch.float32)
    return EvlBackboneOutput(
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
        occ_pr=occ.clone(),
        occ_input=occ.clone(),
        free_input=occ.clone(),
        counts=counts,
        cent_pr=occ.clone(),
        pts_world=pts_world,
    )


def _make_snippet() -> VinSnippetView:
    points_world = torch.tensor(
        [
            [0.0, 0.0, 1.0, 0.1],
            [0.5, 0.0, 1.5, 0.2],
            [float("nan"), float("nan"), float("nan"), float("nan")],
            [float("nan"), float("nan"), float("nan"), float("nan")],
        ],
        dtype=torch.float32,
    )
    return VinSnippetView(
        points_world=points_world,
        lengths=torch.tensor([2], dtype=torch.int64),
        t_world_rig=_identity_pose(2),
    )


def _make_compact_batch(*, sem_names: dict[int, str] | None = None, offset: float = 0.0) -> VinOracleBatch:
    """Build a compact-modality batch fixture."""

    return VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_identity_pose(2),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.1 + offset, 0.2 + offset], dtype=torch.float32),
        pm_dist_before=torch.ones(2, dtype=torch.float32),
        pm_dist_after=torch.ones(2, dtype=torch.float32),
        pm_acc_before=torch.ones(2, dtype=torch.float32),
        pm_comp_before=torch.ones(2, dtype=torch.float32),
        pm_acc_after=torch.ones(2, dtype=torch.float32),
        pm_comp_after=torch.ones(2, dtype=torch.float32),
        p3d_cameras=_make_cameras(2),
        scene_id=f"scene-{offset}",
        snippet_id=f"snip-{offset}",
        gt_obbs=CompactObbBlock(
            obbs=torch.full((2, 34), offset, dtype=torch.float32),
            sem_id_to_name=sem_names,
        ),
        detected_obbs=CompactObbBlock(
            obbs=torch.full((1, 2, 34), offset + 1.0, dtype=torch.float32),
            sem_id_to_name=sem_names,
            probs=torch.full((2, 3), 1.0 / 3.0, dtype=torch.float32),
        ),
        trajectory=CompactTrajectoryBlock(
            time_ns=torch.tensor([100, 200], dtype=torch.int64) + int(offset),
            gravity_in_world=torch.tensor([0.0, 0.0, -9.81], dtype=torch.float32),
        ),
    )


def test_collate_vin_oracle_batches_pads_candidates() -> None:
    """Pad candidate sets and backbone outputs to a shared batch shape."""
    batch_size = 2
    max_candidates = 3
    total_cameras = batch_size * max_candidates
    batch_a = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_identity_pose(2),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.1, 0.2], dtype=torch.float32),
        pm_dist_before=torch.tensor([1.0, 1.1], dtype=torch.float32),
        pm_dist_after=torch.tensor([0.9, 1.0], dtype=torch.float32),
        pm_acc_before=torch.tensor([0.5, 0.6], dtype=torch.float32),
        pm_comp_before=torch.tensor([0.4, 0.5], dtype=torch.float32),
        pm_acc_after=torch.tensor([0.3, 0.4], dtype=torch.float32),
        pm_comp_after=torch.tensor([0.2, 0.3], dtype=torch.float32),
        p3d_cameras=_make_cameras(2),
        scene_id="scene-a",
        snippet_id="snip-a",
        backbone_out=_make_backbone(),
    )
    batch_b = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_identity_pose(3),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.3, 0.4, 0.5], dtype=torch.float32),
        pm_dist_before=torch.tensor([1.2, 1.3, 1.4], dtype=torch.float32),
        pm_dist_after=torch.tensor([1.1, 1.2, 1.3], dtype=torch.float32),
        pm_acc_before=torch.tensor([0.7, 0.8, 0.9], dtype=torch.float32),
        pm_comp_before=torch.tensor([0.6, 0.7, 0.8], dtype=torch.float32),
        pm_acc_after=torch.tensor([0.4, 0.5, 0.6], dtype=torch.float32),
        pm_comp_after=torch.tensor([0.3, 0.4, 0.5], dtype=torch.float32),
        p3d_cameras=_make_cameras(3),
        scene_id="scene-b",
        snippet_id="snip-b",
        backbone_out=_make_backbone(),
    )

    batched = VinOracleBatch.collate([batch_a, batch_b])

    assert batched.candidate_poses_world_cam.shape == (batch_size, max_candidates, 12)  # noqa: S101
    assert batched.rri.shape == (batch_size, max_candidates)  # noqa: S101
    assert torch.equal(batched.candidate_count, torch.tensor([2, 3], dtype=torch.int64))  # noqa: S101
    assert torch.isnan(batched.rri[0, 2])  # noqa: S101
    assert torch.isfinite(batched.rri[1]).all()  # noqa: S101

    cams = batched.p3d_cameras
    assert cams.R.shape[0] == total_cameras  # noqa: S101
    assert cams.R.shape[1:] == (3, 3)  # noqa: S101

    backbone = batched.backbone_out
    assert backbone is not None  # noqa: S101
    assert backbone.occ_pr is not None  # noqa: S101
    assert backbone.occ_pr.shape[0] == batch_size  # noqa: S101
    assert backbone.voxel_extent.shape == (batch_size, 6)  # noqa: S101


def test_collate_batches_compact_obbs_and_trajectory() -> None:
    """Compact numeric OBB and trajectory blocks should stack for training."""

    sem_names = {0: "chair", 1: "table"}
    batch_a = _make_compact_batch(sem_names=sem_names, offset=0.0)
    batch_b = _make_compact_batch(sem_names=sem_names, offset=10.0)

    batched = VinOracleBatch.collate([batch_a, batch_b])

    assert batched.gt_obbs is not None  # noqa: S101
    assert batched.gt_obbs.obbs.shape == (2, 2, 34)  # noqa: S101
    assert batched.gt_obbs.sem_id_to_name == {0: "chair", 1: "table"}  # noqa: S101
    assert batched.detected_obbs is not None  # noqa: S101
    assert batched.detected_obbs.obbs.shape == (2, 2, 34)  # noqa: S101
    assert batched.detected_obbs.probs is not None  # noqa: S101
    assert batched.detected_obbs.probs.shape == (2, 2, 3)  # noqa: S101
    assert batched.trajectory is not None  # noqa: S101
    assert batched.trajectory.time_ns is not None  # noqa: S101
    assert batched.trajectory.time_ns.shape == (2, 2)  # noqa: S101
    assert batched.trajectory.gravity_in_world is not None  # noqa: S101
    assert batched.trajectory.gravity_in_world.shape == (2, 3)  # noqa: S101


def test_collate_rejects_inconsistent_compact_obb_semantic_maps() -> None:
    """Semantic maps are part of the batch contract for compact OBBs."""

    batch_a = _make_compact_batch(sem_names={0: "chair", 1: "table"}, offset=0.0)
    batch_b = _make_compact_batch(sem_names={0: "chair", 1: "lamp"}, offset=10.0)

    with pytest.raises(ValueError, match="gt_obbs.sem_id_to_name must match"):
        VinOracleBatch.collate([batch_a, batch_b])


def test_collate_vin_snippet_view_pads_points_and_traj() -> None:
    """Batch VinSnippetView payloads with padded points and trajectory."""
    points_a = torch.randn(5, 4, dtype=torch.float32)
    points_b = torch.randn(3, 4, dtype=torch.float32)
    traj_a = PoseTW(torch.randn(4, 12, dtype=torch.float32))
    traj_b = PoseTW(torch.randn(4, 12, dtype=torch.float32))
    snippet_a = VinSnippetView(
        points_world=points_a,
        lengths=torch.tensor([5], dtype=torch.int64),
        t_world_rig=traj_a,
    )
    snippet_b = VinSnippetView(
        points_world=points_b,
        lengths=torch.tensor([3], dtype=torch.int64),
        t_world_rig=traj_b,
    )

    batch_a = VinOracleBatch(
        efm_snippet_view=snippet_a,
        candidate_poses_world_cam=_identity_pose(2),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.1, 0.2], dtype=torch.float32),
        pm_dist_before=torch.tensor([1.0, 1.1], dtype=torch.float32),
        pm_dist_after=torch.tensor([0.9, 1.0], dtype=torch.float32),
        pm_acc_before=torch.tensor([0.5, 0.6], dtype=torch.float32),
        pm_comp_before=torch.tensor([0.4, 0.5], dtype=torch.float32),
        pm_acc_after=torch.tensor([0.3, 0.4], dtype=torch.float32),
        pm_comp_after=torch.tensor([0.2, 0.3], dtype=torch.float32),
        p3d_cameras=_make_cameras(2),
        scene_id="scene-a",
        snippet_id="snip-a",
        backbone_out=_make_backbone(),
    )
    batch_b = VinOracleBatch(
        efm_snippet_view=snippet_b,
        candidate_poses_world_cam=_identity_pose(2),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.3, 0.4], dtype=torch.float32),
        pm_dist_before=torch.tensor([1.2, 1.3], dtype=torch.float32),
        pm_dist_after=torch.tensor([1.1, 1.2], dtype=torch.float32),
        pm_acc_before=torch.tensor([0.7, 0.8], dtype=torch.float32),
        pm_comp_before=torch.tensor([0.6, 0.7], dtype=torch.float32),
        pm_acc_after=torch.tensor([0.4, 0.5], dtype=torch.float32),
        pm_comp_after=torch.tensor([0.3, 0.4], dtype=torch.float32),
        p3d_cameras=_make_cameras(2),
        scene_id="scene-b",
        snippet_id="snip-b",
        backbone_out=_make_backbone(),
    )

    batched = VinOracleBatch.collate([batch_a, batch_b])
    assert isinstance(batched.efm_snippet_view, VinSnippetView)  # noqa: S101
    snippet = batched.efm_snippet_view
    assert snippet.points_world.shape == (2, 5, 4)  # noqa: S101
    assert torch.isnan(snippet.points_world[1, 4]).all()  # noqa: S101
    assert snippet.t_world_rig.shape == (2, 4, 12)  # noqa: S101


def test_collate_fixed_width_batches_preserves_candidate_count() -> None:
    """Full-width offline-style batches should stack without shrinking to valid counts."""

    width = 4
    batch_a = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_identity_pose(width),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.1, 0.2, float("nan"), float("nan")], dtype=torch.float32),
        pm_dist_before=torch.tensor([1.0, 1.1, float("nan"), float("nan")], dtype=torch.float32),
        pm_dist_after=torch.tensor([0.9, 1.0, float("nan"), float("nan")], dtype=torch.float32),
        pm_acc_before=torch.tensor([0.5, 0.6, float("nan"), float("nan")], dtype=torch.float32),
        pm_comp_before=torch.tensor([0.4, 0.5, float("nan"), float("nan")], dtype=torch.float32),
        pm_acc_after=torch.tensor([0.3, 0.4, float("nan"), float("nan")], dtype=torch.float32),
        pm_comp_after=torch.tensor([0.2, 0.3, float("nan"), float("nan")], dtype=torch.float32),
        p3d_cameras=_make_cameras(width),
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=_make_backbone(),
    )
    batch_b = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_identity_pose(width),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.3, 0.4, 0.5, float("nan")], dtype=torch.float32),
        pm_dist_before=torch.tensor([1.2, 1.3, 1.4, float("nan")], dtype=torch.float32),
        pm_dist_after=torch.tensor([1.1, 1.2, 1.3, float("nan")], dtype=torch.float32),
        pm_acc_before=torch.tensor([0.7, 0.8, 0.9, float("nan")], dtype=torch.float32),
        pm_comp_before=torch.tensor([0.6, 0.7, 0.8, float("nan")], dtype=torch.float32),
        pm_acc_after=torch.tensor([0.4, 0.5, 0.6, float("nan")], dtype=torch.float32),
        pm_comp_after=torch.tensor([0.3, 0.4, 0.5, float("nan")], dtype=torch.float32),
        p3d_cameras=_make_cameras(width),
        scene_id="scene-b",
        snippet_id="snip-b",
        candidate_count=torch.tensor(3, dtype=torch.int64),
        backbone_out=_make_backbone(),
    )

    batched = VinOracleBatch.collate([batch_a, batch_b])

    assert batched.rri.shape == (2, width)  # noqa: S101
    assert torch.equal(batched.candidate_count, torch.tensor([2, 3], dtype=torch.int64))  # noqa: S101
    assert torch.equal(
        batched.candidate_valid_mask(),
        torch.tensor(
            [
                [True, True, False, False],
                [True, True, True, False],
            ],
            dtype=torch.bool,
        ),
    )  # noqa: S101


def test_lightning_training_step_masks_padded_tail_with_candidate_count() -> None:
    """Candidate count should exclude padded tail entries even when labels are finite."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(num_classes=3),
            num_classes=3,
            aux_regression_loss=None,
        ),
    )
    module._binner = RriOrdinalBinner.fit_from_iterable(
        [torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32)],
        num_classes=3,
    )
    module._trainer = SimpleNamespace(sanity_checking=True)

    logits = torch.tensor(
        [
            [
                [0.25, -0.10],
                [0.05, 0.30],
                [1.50, -1.25],
                [-0.75, 0.80],
            ]
        ],
        dtype=torch.float32,
    )
    probs = coral_logits_to_prob(logits)
    expected, expected_norm = coral_expected_from_logits(logits)
    pred = VinPrediction(
        logits=logits,
        prob=probs,
        expected=expected,
        expected_normalized=expected_norm,
        candidate_valid=torch.ones((1, 4), dtype=torch.bool),
        voxel_valid_frac=torch.ones((1, 4), dtype=torch.float32),
        semidense_candidate_vis_frac=torch.ones((1, 4), dtype=torch.float32),
    )
    module.vin.forward = lambda *args, **kwargs: pred  # type: ignore[method-assign]

    batch = VinOracleBatch(
        efm_snippet_view=_make_snippet(),
        candidate_poses_world_cam=_identity_pose(4),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.10, 0.20, 0.95, 0.85], dtype=torch.float32),
        pm_dist_before=torch.ones(4, dtype=torch.float32),
        pm_dist_after=torch.ones(4, dtype=torch.float32),
        pm_acc_before=torch.ones(4, dtype=torch.float32),
        pm_comp_before=torch.ones(4, dtype=torch.float32),
        pm_acc_after=torch.ones(4, dtype=torch.float32),
        pm_comp_after=torch.ones(4, dtype=torch.float32),
        p3d_cameras=_make_cameras(4),
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=_make_backbone(),
    )

    expected_labels = module._binner.transform(batch.rri[:2])
    expected_loss = module._coral_loss_variant(
        logits[0, :2],
        expected_labels,
        num_classes=int(module._binner.num_classes),
    ).mean()

    loss = module.training_step(batch, batch_idx=0)

    assert loss is not None  # noqa: S101
    assert torch.isclose(loss, expected_loss)  # noqa: S101


def test_lightning_logs_candidate_oracle_hit_with_table_mask(monkeypatch: pytest.MonkeyPatch) -> None:
    """Oracle-hit logging should rank only hard-valid candidate rows."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(num_classes=3),
            num_classes=3,
            aux_regression_loss=None,
        ),
    )
    module._binner = RriOrdinalBinner.fit_from_iterable(
        [torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32)],
        num_classes=3,
    )
    module.prepare_for_inference()
    module._trainer = SimpleNamespace(sanity_checking=False)
    logged: dict[str, torch.Tensor | float] = {}
    log_dict_calls: list[tuple[dict[str, torch.Tensor | float], dict[str, object]]] = []

    def capture_log_dict(values: dict[str, torch.Tensor | float], *args: object, **kwargs: object) -> None:
        del args
        logged.update(values)
        log_dict_calls.append((values, kwargs))

    monkeypatch.setattr(module, "log_dict", capture_log_dict)

    logits = torch.tensor(
        [
            [
                [0.25, -0.10],
                [0.05, 0.30],
                [1.50, -1.25],
                [-0.75, 0.80],
            ]
        ],
        dtype=torch.float32,
    )
    probs = coral_logits_to_prob(logits)
    expected, _ = coral_expected_from_logits(logits)
    pred = VinPrediction(
        logits=logits,
        prob=probs,
        expected=expected,
        expected_normalized=torch.tensor([[0.9, 0.1, 1.0, 0.8]], dtype=torch.float32),
        candidate_valid=torch.ones((1, 4), dtype=torch.bool),
        voxel_valid_frac=torch.ones((1, 4), dtype=torch.float32),
        semidense_candidate_vis_frac=torch.ones((1, 4), dtype=torch.float32),
    )
    module.vin.forward = lambda *args, **kwargs: pred  # type: ignore[method-assign]

    batch = VinOracleBatch(
        efm_snippet_view=_make_snippet(),
        candidate_poses_world_cam=_identity_pose(4),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.10, 0.20, 0.95, 0.85], dtype=torch.float32),
        pm_dist_before=torch.ones(4, dtype=torch.float32),
        pm_dist_after=torch.ones(4, dtype=torch.float32),
        pm_acc_before=torch.ones(4, dtype=torch.float32),
        pm_comp_before=torch.ones(4, dtype=torch.float32),
        pm_acc_after=torch.ones(4, dtype=torch.float32),
        pm_comp_after=torch.ones(4, dtype=torch.float32),
        p3d_cameras=_make_cameras(4),
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=_make_backbone(),
    )

    loss = module.training_step(batch, batch_idx=0)

    assert loss is not None
    assert torch.allclose(logged["train-aux/candidate_top1_oracle_hit"], torch.tensor(0.0))
    assert torch.allclose(logged["train-aux/candidate_top3_oracle_hit"], torch.tensor(1.0))
    assert torch.allclose(logged["train-aux/selected_oracle_regret"], torch.tensor(0.1))
    assert torch.allclose(logged["train-aux/selected_oracle_rank"], torch.tensor(2.0))
    assert torch.allclose(logged["train-aux/selected_oracle_percentile"], torch.tensor(0.0))
    assert torch.allclose(logged["train-aux/selected_oracle_valid_table_rate"], torch.tensor(1.0))
    assert any(
        "train-aux/candidate_top3_oracle_hit" in values and kwargs["batch_size"] == 1
        for values, kwargs in log_dict_calls
    )
    assert any("train/loss" in values and kwargs["batch_size"] == 2 for values, kwargs in log_dict_calls)


def test_lightning_table_metric_logging_uses_per_metric_denominators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(backbone=None, num_classes=3),
            num_classes=3,
        ),
    )
    calls: list[tuple[str, int]] = []

    def capture_log_dict(
        payload: dict[str, torch.Tensor | float],
        *args: object,
        **kwargs: object,
    ) -> None:
        del args
        assert len(payload) == 1
        assert kwargs["on_step"] is True
        assert kwargs["on_epoch"] is False
        calls.append((next(iter(payload)), int(kwargs["batch_size"])))

    monkeypatch.setattr(module, "log_dict", capture_log_dict)

    module._log_candidate_table_step_metrics(
        top1_oracle_hit=torch.tensor([1.0, float("nan"), 0.0]),
        top1_oracle_hit_mean=torch.tensor(0.5),
        top3_oracle_hit=torch.tensor([1.0, float("nan"), float("nan")]),
        top3_oracle_hit_mean=torch.tensor(1.0),
        selected_oracle_regret=torch.tensor([0.2, float("nan"), float("nan")]),
        selected_oracle_regret_mean=torch.tensor(0.2),
        selected_oracle_rank=torch.tensor([1.0, 2.0, float("nan")]),
        selected_oracle_rank_mean=torch.tensor(1.5),
        selected_oracle_percentile=torch.tensor([float("nan"), 0.4, float("nan")]),
        selected_oracle_percentile_mean=torch.tensor(0.4),
        selected_oracle_valid_table=torch.tensor([True, False, True]),
        selected_oracle_valid_rate=torch.tensor(2.0 / 3.0),
    )

    assert dict(calls) == {
        "train-aux/candidate_top1_oracle_hit": 2,
        "train-aux/candidate_top3_oracle_hit": 1,
        "train-aux/selected_oracle_regret": 1,
        "train-aux/selected_oracle_rank": 2,
        "train-aux/selected_oracle_percentile": 1,
        "train-aux/selected_oracle_valid_table_rate": 3,
    }


def test_lightning_candidate_metrics_weight_tables_and_reset_per_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Epoch metrics weight candidate tables, remain stage-local, and reset."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(backbone=None, num_classes=3),
            num_classes=3,
        ),
    )
    module._trainer = SimpleNamespace(sanity_checking=False)
    captured: dict[str, torch.Tensor] = {}

    def capture_log_dict(
        payload: dict[str, torch.Tensor],
        *args: object,
        **kwargs: object,
    ) -> None:
        del args
        assert kwargs["on_step"] is False
        assert kwargs["on_epoch"] is True
        captured.update(payload)

    monkeypatch.setattr(module, "log_dict", capture_log_dict)
    stage_key = f"{Stage.VAL.value}_stage"
    batches = (
        (
            torch.tensor([[0.9, 0.1]]),
            torch.tensor([[1.0, 0.0]]),
        ),
        (
            torch.tensor([[0.9, 0.1], [0.8, 0.2], [0.7, 0.3]]),
            torch.tensor([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]),
        ),
    )
    for predicted, oracle in batches:
        valid = torch.ones_like(predicted, dtype=torch.bool)
        selected = predicted.argmax(dim=-1)
        module._candidate_top1_metrics[stage_key].update(predicted, oracle, valid)
        module._candidate_top3_metrics[stage_key].update(predicted, oracle, valid)
        module._selected_action_metrics[stage_key].update(oracle, selected, valid)

    module._log_candidate_ranking_epoch_metrics(Stage.VAL)

    assert torch.allclose(captured["val-aux/candidate_top1_oracle_hit"], torch.tensor(0.25))
    assert torch.allclose(captured["val-aux/candidate_top3_oracle_hit"], torch.tensor(1.0))
    assert torch.allclose(captured["val-aux/selected_oracle_regret"], torch.tensor(0.75))
    assert module._candidate_top1_metrics[stage_key].hit_count.item() == 0.0
    assert module._selected_action_metrics[stage_key].table_count.item() == 0.0
    assert module._candidate_top1_metrics[f"{Stage.TRAIN.value}_stage"].hit_count.item() == 0.0


def test_lightning_selected_oracle_logs_empty_when_no_finite_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selected-action oracle diagnostics should not select from all-nonfinite valid predictions."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(num_classes=3),
            num_classes=3,
            aux_regression_loss=None,
        ),
    )
    module._binner = RriOrdinalBinner.fit_from_iterable(
        [torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32)],
        num_classes=3,
    )
    module.prepare_for_inference()
    module._trainer = SimpleNamespace(sanity_checking=False)
    logged: dict[str, torch.Tensor | float] = {}

    def capture_log_dict(values: dict[str, torch.Tensor | float], *args: object, **kwargs: object) -> None:
        logged.update(values)

    monkeypatch.setattr(module, "log_dict", capture_log_dict)

    logits = torch.zeros((1, 4, 2), dtype=torch.float32)
    probs = coral_logits_to_prob(logits)
    expected, _ = coral_expected_from_logits(logits)
    pred = VinPrediction(
        logits=logits,
        prob=probs,
        expected=expected,
        expected_normalized=torch.tensor([[float("nan"), float("nan"), 1.0, 0.8]], dtype=torch.float32),
        candidate_valid=torch.ones((1, 4), dtype=torch.bool),
        voxel_valid_frac=torch.ones((1, 4), dtype=torch.float32),
        semidense_candidate_vis_frac=torch.ones((1, 4), dtype=torch.float32),
    )
    module.vin.forward = lambda *args, **kwargs: pred  # type: ignore[method-assign]

    batch = VinOracleBatch(
        efm_snippet_view=_make_snippet(),
        candidate_poses_world_cam=_identity_pose(4),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.10, 0.20, 0.95, 0.85], dtype=torch.float32),
        pm_dist_before=torch.ones(4, dtype=torch.float32),
        pm_dist_after=torch.ones(4, dtype=torch.float32),
        pm_acc_before=torch.ones(4, dtype=torch.float32),
        pm_comp_before=torch.ones(4, dtype=torch.float32),
        pm_acc_after=torch.ones(4, dtype=torch.float32),
        pm_comp_after=torch.ones(4, dtype=torch.float32),
        p3d_cameras=_make_cameras(4),
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=_make_backbone(),
    )

    loss = module.training_step(batch, batch_idx=0)

    assert loss is not None
    assert torch.isnan(logged["train-aux/selected_oracle_regret"])
    assert torch.isnan(logged["train-aux/selected_oracle_rank"])
    assert torch.isnan(logged["train-aux/selected_oracle_percentile"])
    assert torch.allclose(logged["train-aux/selected_oracle_valid_table_rate"], torch.tensor(0.0))


def test_lightning_candidate_scorer_alias_preserves_vin_state_prefix() -> None:
    """The scorer seam should not rename existing VIN checkpoint parameters."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(num_classes=3),
            num_classes=3,
        ),
    )

    assert module.candidate_scorer is module.vin  # noqa: S101
    assert isinstance(module.config.vin, VinModelV3Config)  # noqa: S101
    state_keys = tuple(module.state_dict())
    assert any(key.startswith("vin.") for key in state_keys)  # noqa: S101
    assert not any(key.startswith("candidate_scorer.") for key in state_keys)  # noqa: S101
    assert not any(key.startswith("_candidate_") for key in state_keys)  # noqa: S101


def test_lightning_accepts_zero_descriptor_myopic_scorer_without_state_alias() -> None:
    """The myopic baseline should train through the existing VIN module slot."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=TargetConditionedMyopicScorerConfig(num_classes=3, target_descriptor_dim=0),
            num_classes=3,
        ),
    )

    assert module.candidate_scorer is module.vin  # noqa: S101
    assert isinstance(module.vin, TargetConditionedMyopicScorer)  # noqa: S101
    state_keys = tuple(module.state_dict())
    assert any(key.startswith("vin.base_scorer.") for key in state_keys)  # noqa: S101
    assert not any(key.startswith("candidate_scorer.") for key in state_keys)  # noqa: S101


def test_lightning_accepts_custom_zero_descriptor_myopic_base_scorer() -> None:
    """Custom v3 settings should survive the myopic wrapper without aliasing state."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=TargetConditionedMyopicScorerConfig(
                num_classes=3,
                target_descriptor_dim=0,
                base_scorer=VinModelV3Config(num_classes=99, field_dim=12, head_dropout=0.2),
            ),
            num_classes=3,
        ),
    )

    assert module.candidate_scorer is module.vin  # noqa: S101
    assert isinstance(module.vin, TargetConditionedMyopicScorer)  # noqa: S101
    assert module.vin.base_scorer.config.num_classes == 3  # noqa: S101
    assert module.vin.base_scorer.config.field_dim == 12  # noqa: S101
    assert module.vin.base_scorer.config.head_dropout == 0.2  # noqa: S101
    assert module.vin.base_scorer.config is not module.config.vin.base_scorer  # noqa: S101
    state_keys = tuple(module.state_dict())
    assert any(key.startswith("vin.base_scorer.") for key in state_keys)  # noqa: S101
    assert not any(key.startswith("candidate_scorer.") for key in state_keys)  # noqa: S101


def test_lightning_can_disable_spearman_metric_buffering() -> None:
    """Smoke modules can skip Spearman without disabling confusion/histogram metrics."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=TargetConditionedMyopicScorerConfig(num_classes=3, target_descriptor_dim=0),
            num_classes=3,
            log_spearman=False,
        ),
    )

    for metrics in module._metrics.values():
        assert metrics.spearman is None  # noqa: S101
        assert metrics.confusion is not None  # noqa: S101
        assert metrics.label_hist is not None  # noqa: S101
    assert module._interval_metrics.spearman is None  # noqa: S101


def test_lightning_logs_without_spearman_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabling Spearman should not break scalar logging or interval metrics."""

    module = VinLightningModule(
        config=VinLightningModuleConfig(
            vin=VinModelV3Config(num_classes=3),
            num_classes=3,
            aux_regression_loss=None,
            log_interval_steps=1,
            log_spearman=False,
        ),
    )
    module._binner = RriOrdinalBinner.fit_from_iterable(
        [torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32)],
        num_classes=3,
    )
    module.prepare_for_inference()
    module._trainer = SimpleNamespace(sanity_checking=False)
    logged: dict[str, torch.Tensor | float] = {}

    def capture_log_dict(values: dict[str, torch.Tensor | float], *args: object, **kwargs: object) -> None:
        del args, kwargs
        logged.update(values)

    monkeypatch.setattr(module, "log_dict", capture_log_dict)

    logits = torch.tensor([[[0.25, -0.10], [0.05, 0.30]]], dtype=torch.float32)
    probs = coral_logits_to_prob(logits)
    expected, expected_norm = coral_expected_from_logits(logits)
    pred = VinPrediction(
        logits=logits,
        prob=probs,
        expected=expected,
        expected_normalized=expected_norm,
        candidate_valid=torch.ones((1, 2), dtype=torch.bool),
        voxel_valid_frac=torch.ones((1, 2), dtype=torch.float32),
        semidense_candidate_vis_frac=torch.ones((1, 2), dtype=torch.float32),
    )
    module.vin.forward = lambda *args, **kwargs: pred  # type: ignore[method-assign]

    batch = VinOracleBatch(
        efm_snippet_view=_make_snippet(),
        candidate_poses_world_cam=_identity_pose(2),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.10, 0.20], dtype=torch.float32),
        pm_dist_before=torch.ones(2, dtype=torch.float32),
        pm_dist_after=torch.ones(2, dtype=torch.float32),
        pm_acc_before=torch.ones(2, dtype=torch.float32),
        pm_comp_before=torch.ones(2, dtype=torch.float32),
        pm_acc_after=torch.ones(2, dtype=torch.float32),
        pm_comp_after=torch.ones(2, dtype=torch.float32),
        p3d_cameras=_make_cameras(2),
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=_make_backbone(),
    )

    loss = module.training_step(batch, batch_idx=0)

    assert loss is not None  # noqa: S101
    assert "train/loss" in logged  # noqa: S101
    assert "train-aux/spearman_step" not in logged  # noqa: S101
    assert "train-aux/spearman" not in logged  # noqa: S101


def test_shuffle_candidates_preserves_padded_tail_unbatched() -> None:
    """Only the valid prefix should move when candidate_count is smaller than width."""

    width = 4
    candidates = _indexed_pose(width)
    cameras = _make_indexed_cameras(width)
    batch = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=candidates,
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([10.0, 11.0, 99.0, 100.0], dtype=torch.float32),
        pm_dist_before=torch.tensor([20.0, 21.0, 199.0, 200.0], dtype=torch.float32),
        pm_dist_after=torch.tensor([30.0, 31.0, 299.0, 300.0], dtype=torch.float32),
        pm_acc_before=torch.tensor([40.0, 41.0, 399.0, 400.0], dtype=torch.float32),
        pm_comp_before=torch.tensor([50.0, 51.0, 499.0, 500.0], dtype=torch.float32),
        pm_acc_after=torch.tensor([60.0, 61.0, 599.0, 600.0], dtype=torch.float32),
        pm_comp_after=torch.tensor([70.0, 71.0, 699.0, 700.0], dtype=torch.float32),
        p3d_cameras=cameras,
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=None,
    )

    expected_prefix = torch.randperm(2, generator=torch.Generator().manual_seed(13))
    shuffled = batch.shuffle_candidates(generator=torch.Generator().manual_seed(13))

    assert torch.equal(shuffled.rri[:2], batch.rri[expected_prefix])  # noqa: S101
    assert torch.equal(shuffled.rri[2:], batch.rri[2:])  # noqa: S101
    assert torch.equal(
        shuffled.candidate_poses_world_cam.tensor()[:2],
        candidates.tensor()[expected_prefix],
    )  # noqa: S101
    assert torch.equal(
        shuffled.candidate_poses_world_cam.tensor()[2:],
        candidates.tensor()[2:],
    )  # noqa: S101
    assert torch.equal(shuffled.p3d_cameras.T[:2], cameras.T[expected_prefix])  # noqa: S101
    assert torch.equal(shuffled.p3d_cameras.T[2:], cameras.T[2:])  # noqa: S101


def test_shuffle_candidates_preserves_padded_tail_batched() -> None:
    """Each sample should shuffle only its own valid prefix inside a batched tensor."""

    width = 4
    batch_a = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_indexed_pose(width, offset=0.0),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([10.0, 11.0, 99.0, 100.0], dtype=torch.float32),
        pm_dist_before=torch.tensor([20.0, 21.0, 199.0, 200.0], dtype=torch.float32),
        pm_dist_after=torch.tensor([30.0, 31.0, 299.0, 300.0], dtype=torch.float32),
        pm_acc_before=torch.tensor([40.0, 41.0, 399.0, 400.0], dtype=torch.float32),
        pm_comp_before=torch.tensor([50.0, 51.0, 499.0, 500.0], dtype=torch.float32),
        pm_acc_after=torch.tensor([60.0, 61.0, 599.0, 600.0], dtype=torch.float32),
        pm_comp_after=torch.tensor([70.0, 71.0, 699.0, 700.0], dtype=torch.float32),
        p3d_cameras=_make_indexed_cameras(width, offset=0.0),
        scene_id="scene-a",
        snippet_id="snip-a",
        candidate_count=torch.tensor(2, dtype=torch.int64),
        backbone_out=None,
    )
    batch_b = VinOracleBatch(
        efm_snippet_view=None,
        candidate_poses_world_cam=_indexed_pose(width, offset=10.0),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([210.0, 211.0, 212.0, 299.0], dtype=torch.float32),
        pm_dist_before=torch.tensor([220.0, 221.0, 222.0, 399.0], dtype=torch.float32),
        pm_dist_after=torch.tensor([230.0, 231.0, 232.0, 499.0], dtype=torch.float32),
        pm_acc_before=torch.tensor([240.0, 241.0, 242.0, 599.0], dtype=torch.float32),
        pm_comp_before=torch.tensor([250.0, 251.0, 252.0, 699.0], dtype=torch.float32),
        pm_acc_after=torch.tensor([260.0, 261.0, 262.0, 799.0], dtype=torch.float32),
        pm_comp_after=torch.tensor([270.0, 271.0, 272.0, 899.0], dtype=torch.float32),
        p3d_cameras=_make_indexed_cameras(width, offset=10.0),
        scene_id="scene-b",
        snippet_id="snip-b",
        candidate_count=torch.tensor(3, dtype=torch.int64),
        backbone_out=None,
    )
    batch = VinOracleBatch.collate([batch_a, batch_b])

    gen = torch.Generator().manual_seed(7)
    perm_a = torch.randperm(2, generator=gen)
    perm_b = torch.randperm(3, generator=gen)
    shuffled = batch.shuffle_candidates(generator=torch.Generator().manual_seed(7))

    assert torch.equal(shuffled.rri[0, :2], batch.rri[0, perm_a])  # noqa: S101
    assert torch.equal(shuffled.rri[0, 2:], batch.rri[0, 2:])  # noqa: S101
    assert torch.equal(shuffled.rri[1, :3], batch.rri[1, perm_b])  # noqa: S101
    assert torch.equal(shuffled.rri[1, 3:], batch.rri[1, 3:])  # noqa: S101
    assert torch.equal(
        shuffled.candidate_poses_world_cam.tensor()[0, 2:],
        batch.candidate_poses_world_cam.tensor()[0, 2:],
    )  # noqa: S101
    assert torch.equal(
        shuffled.candidate_poses_world_cam.tensor()[1, 3:],
        batch.candidate_poses_world_cam.tensor()[1, 3:],
    )  # noqa: S101
