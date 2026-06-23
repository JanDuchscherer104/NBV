"""Tests for canonical VIN geometry helper modules."""

from __future__ import annotations

import torch
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

from aria_nbv.vin.geometry import (
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
