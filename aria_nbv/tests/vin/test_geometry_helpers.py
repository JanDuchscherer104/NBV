"""Tests for canonical VIN geometry helper modules."""

from __future__ import annotations

from types import SimpleNamespace

import torch
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

from aria_nbv.vin.geometry import (
    build_scene_field,
    candidate_valid_from_token,
    ensure_candidate_batch,
    ensure_pose_batch,
    frustum_points_world_from_cameras,
)


def _identity_pose(batch: int) -> PoseTW:
    rot = torch.eye(3, dtype=torch.float32).view(1, 3, 3).expand(batch, 3, 3)
    trans = torch.zeros((batch, 3), dtype=torch.float32)
    return PoseTW.from_Rt(rot, trans)


def _candidate_poses(batch: int, num_candidates: int) -> PoseTW:
    pose = _identity_pose(batch * num_candidates)
    return PoseTW(pose._data.reshape(batch, num_candidates, 12))


def _make_cameras(num_cams: int) -> PerspectiveCameras:
    device = torch.device("cpu")
    return PerspectiveCameras(
        device=device,
        R=torch.eye(3, device=device).unsqueeze(0).expand(num_cams, 3, 3),
        T=torch.zeros((num_cams, 3), device=device),
        focal_length=torch.full((num_cams, 2), 60.0, device=device),
        principal_point=torch.full((num_cams, 2), 50.0, device=device),
        image_size=torch.full((num_cams, 2), 100.0, device=device),
        in_ndc=False,
    )


def test_ensure_candidate_batch_accepts_unbatched_and_batched_poses() -> None:
    unbatched = _candidate_poses(batch=1, num_candidates=3).squeeze(0)
    batched = _candidate_poses(batch=2, num_candidates=3)

    assert ensure_candidate_batch(unbatched).shape == (1, 3, 12)
    assert ensure_candidate_batch(batched).shape == (2, 3, 12)


def test_ensure_pose_batch_broadcasts_single_pose() -> None:
    pose = _identity_pose(1)
    broadcast = ensure_pose_batch(pose, batch_size=3, name="reference_pose_world_rig")

    assert isinstance(broadcast, PoseTW)
    assert broadcast.shape == (3, 12)
    assert torch.allclose(broadcast.t, torch.zeros((3, 3), dtype=torch.float32))


def test_frustum_points_world_from_cameras_accepts_single_batch_candidate_cameras() -> None:
    poses = _candidate_poses(batch=1, num_candidates=2)
    points = frustum_points_world_from_cameras(
        poses,
        p3d_cameras=_make_cameras(2),
        grid_size=2,
        depths_m=[1.0, 2.0],
    )

    assert points.shape == (1, 2, 8, 3)
    assert torch.isfinite(points).all()


def test_frustum_points_world_from_cameras_accepts_flat_batched_cameras() -> None:
    poses = _candidate_poses(batch=2, num_candidates=3)
    points = frustum_points_world_from_cameras(
        poses,
        p3d_cameras=_make_cameras(6),
        grid_size=2,
        depths_m=[1.0],
    )

    assert points.shape == (2, 3, 4, 3)
    assert torch.isfinite(points).all()


def test_candidate_valid_from_token_thresholds_last_axis() -> None:
    valid = torch.tensor(
        [
            [[True, False, True], [False, False, True]],
            [[True, True, True], [False, False, False]],
        ],
        dtype=torch.bool,
    )

    candidate_valid = candidate_valid_from_token(valid, min_valid_frac=0.5)

    assert candidate_valid.tolist() == [[True, False], [True, False]]


def test_build_scene_field_preserves_experimental_observed_unknown_contract() -> None:
    occ_pr = torch.full((1, 1, 2, 1, 1), 0.75, dtype=torch.float32)
    occ_input = torch.tensor([[[[[0.8]], [[0.2]]]]], dtype=torch.float32)
    counts = torch.tensor([[[[2]], [[0]]]], dtype=torch.float32)
    out = SimpleNamespace(
        occ_pr=occ_pr,
        occ_input=occ_input,
        cent_pr=torch.full_like(occ_pr, 0.25),
        counts=counts,
        free_input=None,
    )

    field = build_scene_field(
        out,
        use_channels=["observed", "unknown", "counts_norm", "free_input", "new_surface_prior"],
        occ_input_threshold=0.5,
        counts_norm_mode="log1p",
        occ_pr_is_logits=False,
    )

    observed, unknown, counts_norm, free_input, new_surface_prior = (
        field[:, 0],
        field[:, 1],
        field[:, 2],
        field[:, 3],
        field[:, 4],
    )
    assert observed.flatten().tolist() == [1.0, 0.0]
    assert unknown.flatten().tolist() == [0.0, 1.0]
    assert torch.allclose(counts_norm.flatten(), torch.tensor([1.0, 0.0]))
    assert free_input.flatten().tolist() == [0.0, 0.0]
    assert new_surface_prior.flatten().tolist() == [0.0, 0.75]
