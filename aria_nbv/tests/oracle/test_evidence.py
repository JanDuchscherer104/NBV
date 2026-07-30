"""Tests for RRI oracle evaluation point-cloud construction."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import dataclass

import pytest
import torch
from efm3d.aria import CameraTW, PoseTW

import aria_nbv.oracle.evidence as evidence
from aria_nbv.data_handling.ase_efm.views import EfmCameraView, EfmTrajectoryView
from aria_nbv.oracle.evidence import (
    OracleEvidenceInvalidReason,
    RriEvaluationPointCloudSource,
    _OracleEvidenceError,
    build_root_eval_pointcloud,
    canonical_fuse_points,
    observed_prefix_frame_indices,
)


def _pose_batch(translations: torch.Tensor) -> PoseTW:
    return PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).reshape(1, 3, 3).repeat(translations.shape[0], 1, 1),
        translations.to(dtype=torch.float32),
    )


def _camera_batch(num_frames: int, *, width: int = 8, height: int = 8) -> CameraTW:
    one = CameraTW.from_surreal(
        width=torch.tensor([float(width)]),
        height=torch.tensor([float(height)]),
        type_str="Pinhole",
        params=torch.tensor([[8.0, 8.0, width / 2.0, height / 2.0]], dtype=torch.float32),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([float(max(width, height))]),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, dtype=torch.float32).unsqueeze(0)),
    )
    return CameraTW(one.tensor().repeat(num_frames, 1))


@dataclass(slots=True)
class _Semidense:
    points: torch.Tensor

    def collapse_points(self):
        return self.points


class _DepthSample:
    def __init__(
        self,
        distance_m: torch.Tensor | None,
        *,
        translations: torch.Tensor | None = None,
        time_ns: torch.Tensor | None = None,
    ) -> None:
        frame_count = 3 if distance_m is None else int(distance_m.shape[0])
        if time_ns is None:
            time_ns = torch.arange(frame_count, dtype=torch.int64) * 10
        if translations is None:
            translations = torch.stack(
                [torch.arange(frame_count, dtype=torch.float32), torch.zeros(frame_count), torch.zeros(frame_count)],
                dim=1,
            )
        self._camera = EfmCameraView(
            images=torch.zeros((frame_count, 3, 8, 8), dtype=torch.float32),
            calib=_camera_batch(frame_count),
            time_ns=time_ns,
            frame_ids=torch.arange(frame_count, dtype=torch.int64),
            distance_m=distance_m,
            distance_time_ns=time_ns if distance_m is not None else None,
        )
        self.trajectory = EfmTrajectoryView(
            t_world_rig=_pose_batch(translations),
            time_ns=time_ns,
            gravity_in_world=torch.tensor([0.0, 0.0, -9.81], dtype=torch.float32),
        )
        self.semidense = _Semidense(torch.tensor([[9.0, 0.0, 0.0], [9.0, 0.0, 0.0]], dtype=torch.float32))

    def get_camera(self, label: str) -> EfmCameraView:
        assert label == "rgb"
        return self._camera


def test_observed_prefix_frame_indices_stop_at_non_final_reference_pose() -> None:
    sample = _DepthSample(torch.ones((3, 1, 8, 8), dtype=torch.float32))
    reference_pose = sample.trajectory.t_world_rig[1]

    frame_indices, traj_indices = observed_prefix_frame_indices(sample, reference_pose_world=reference_pose)

    assert frame_indices.tolist() == [0, 1]
    assert traj_indices.tolist() == [0, 1]


def test_observed_prefix_frame_indices_use_time_not_spatial_nearest_for_loops() -> None:
    translations = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ],
        dtype=torch.float32,
    )
    sample = _DepthSample(
        torch.ones((4, 1, 8, 8), dtype=torch.float32),
        translations=translations,
        time_ns=torch.tensor([0, 10, 20, 30], dtype=torch.int64),
    )

    frame_indices, traj_indices = observed_prefix_frame_indices(sample, reference_time_ns=10)

    assert frame_indices.tolist() == [0, 1]
    assert traj_indices.tolist() == [0, 1]


def test_ase_depth_root_uses_ray_distance_frames_and_far_clip() -> None:
    depth = torch.ones((3, 1, 8, 8), dtype=torch.float32)
    depth[1] = 30.0
    sample = _DepthSample(depth)

    root = build_root_eval_pointcloud(
        sample,
        source=RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT,
        reference_pose_world=sample.trajectory.t_world_rig[1],
        stride=2,
        far_m=20.0,
        voxel_size_m=0.0,
        max_points=None,
    )

    assert root.depth_convention == "ray_distance_m"
    assert root.frame_indices.tolist() == [0, 1]
    assert root.trajectory_indices.tolist() == [0, 1]
    assert root.root_time_ns == 10
    assert root.root_trajectory_index == 1
    assert root.points_world.shape == (16, 3)
    assert torch.isfinite(root.points_world).all()
    assert torch.allclose(torch.linalg.norm(root.points_world, dim=-1), torch.ones(16), atol=1e-5)


def test_ase_depth_root_calls_efm3d_ray_distance_unprojector(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = _DepthSample(torch.ones((3, 1, 8, 8), dtype=torch.float32))
    calls: list[tuple[int, ...]] = []
    original = evidence.dist_im_to_point_cloud_im

    def wrapped(depths: torch.Tensor, calibs: CameraTW):
        calls.append(tuple(depths.shape))
        return original(depths, calibs)

    monkeypatch.setattr(evidence, "dist_im_to_point_cloud_im", wrapped)

    build_root_eval_pointcloud(sample, source=RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT)

    assert calls == [(3, 8, 8)]


def test_ase_depth_root_rejects_missing_depth() -> None:
    sample = _DepthSample(None)

    with pytest.raises(_OracleEvidenceError, match="requires rgb/distance_m") as exc_info:
        build_root_eval_pointcloud(sample, source=RriEvaluationPointCloudSource.ASE_GT_DEPTH_ROOT)

    assert exc_info.value.reason is OracleEvidenceInvalidReason.ROOT_DEPTH_MISSING


def test_legacy_semidense_root_is_diagnostic_and_canonical_fused() -> None:
    sample = _DepthSample(torch.ones((3, 1, 8, 8), dtype=torch.float32))

    root = build_root_eval_pointcloud(
        sample,
        source=RriEvaluationPointCloudSource.LEGACY_SEMIDENSE_ROOT,
        voxel_size_m=0.1,
        max_points=None,
    )

    assert root.depth_convention == "mps_semidense_world"
    assert root.points_world.tolist() == [[9.0, 0.0, 0.0]]


def test_canonical_fuse_points_is_deterministic_and_caps_points() -> None:
    points = torch.tensor(
        [
            [0.01, 0.0, 0.0],
            [0.02, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ],
        dtype=torch.float32,
    )

    fused = canonical_fuse_points(points, voxel_size_m=0.1, max_points=2)

    assert fused.shape == (2, 3)
    assert fused[0, 0] == pytest.approx(0.015)
