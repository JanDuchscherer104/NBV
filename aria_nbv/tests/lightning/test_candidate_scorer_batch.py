"""Tests for Lightning candidate-scorer batch input preparation."""

from __future__ import annotations

import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling import EfmSnippetView, VinOracleBatch, VinSnippetView
from aria_nbv.lightning._candidate_scorer_batch import prepare_candidate_scorer_batch_inputs
from aria_nbv.vin.types import EvlBackboneOutput

pytest.importorskip("pytorch_lightning")
pytorch3d_cameras = pytest.importorskip("pytorch3d.renderer.cameras")
PerspectiveCameras = pytorch3d_cameras.PerspectiveCameras


def _identity_pose(num: int) -> PoseTW:
    eye = torch.eye(3, dtype=torch.float32).reshape(1, 9).repeat(num, 1)
    t = torch.zeros((num, 3), dtype=torch.float32)
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


def _make_vin_snippet() -> VinSnippetView:
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
        t_world_snippet=_identity_pose(1),
    )


def _make_batch(
    *,
    snippet: EfmSnippetView | VinSnippetView | None = None,
    backbone_out: EvlBackboneOutput | None = None,
) -> VinOracleBatch:
    return VinOracleBatch(
        efm_snippet_view=snippet,
        candidate_poses_world_cam=_identity_pose(2),
        reference_pose_world_rig=PoseTW(_identity_pose(1).tensor().squeeze(0)),
        rri=torch.tensor([0.1, 0.2], dtype=torch.float32),
        pm_dist_before=torch.ones(2, dtype=torch.float32),
        pm_dist_after=torch.ones(2, dtype=torch.float32),
        pm_acc_before=torch.ones(2, dtype=torch.float32),
        pm_comp_before=torch.ones(2, dtype=torch.float32),
        pm_acc_after=torch.ones(2, dtype=torch.float32),
        pm_comp_after=torch.ones(2, dtype=torch.float32),
        p3d_cameras=_make_cameras(2),
        scene_id="scene-a",
        snippet_id="snip-a",
        backbone_out=backbone_out,
    )


def test_prepare_candidate_scorer_batch_inputs_normalizes_devices() -> None:
    """The Lightning scorer-input seam should preserve batch fields and move tensors."""

    batch = _make_batch(snippet=_make_vin_snippet(), backbone_out=_make_backbone())

    inputs = prepare_candidate_scorer_batch_inputs(batch, device=torch.device("cpu"))

    assert inputs.efm is batch.efm_snippet_view  # noqa: S101
    assert inputs.candidate_poses_world_cam.tensor().device.type == "cpu"  # noqa: S101
    assert inputs.reference_pose_world_rig.tensor().device.type == "cpu"  # noqa: S101
    assert inputs.p3d_cameras.device == torch.device("cpu")  # noqa: S101
    assert inputs.backbone_out is not None  # noqa: S101
    assert inputs.backbone_out.occ_pr is not None  # noqa: S101
    assert inputs.backbone_out.occ_pr.device.type == "cpu"  # noqa: S101


def test_prepare_candidate_scorer_batch_inputs_accepts_efm_snippet_without_backbone() -> None:
    """Raw EFM snippets already carry actor-visible scene evidence."""

    batch = _make_batch(
        snippet=EfmSnippetView(efm={}, scene_id="scene-a", snippet_id="snip-a"),
        backbone_out=None,
    )

    inputs = prepare_candidate_scorer_batch_inputs(batch, device=torch.device("cpu"))

    assert inputs.efm is batch.efm_snippet_view  # noqa: S101
    assert inputs.backbone_out is None  # noqa: S101


def test_prepare_candidate_scorer_batch_inputs_rejects_missing_snippet_view() -> None:
    """Batches still need actor-visible snippet evidence before scorer forward."""

    batch = _make_batch()

    with pytest.raises(RuntimeError, match="missing semidense snippet view"):
        prepare_candidate_scorer_batch_inputs(batch, device=torch.device("cpu"))


def test_prepare_candidate_scorer_batch_inputs_requires_cached_backbone_for_vin_snippet() -> None:
    """Minimal VIN snippets require cached EVL fields for the v3 scorer path."""

    batch = _make_batch(snippet=_make_vin_snippet(), backbone_out=None)

    with pytest.raises(RuntimeError, match="missing both efm snippet view and cached backbone outputs"):
        prepare_candidate_scorer_batch_inputs(batch, device=torch.device("cpu"))
