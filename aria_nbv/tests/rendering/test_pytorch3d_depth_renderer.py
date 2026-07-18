import pytest
import torch
from efm3d.aria import CameraTW, PoseTW
from pytorch3d.structures import Meshes

from aria_nbv.rendering.pytorch3d_depth_renderer import (
    Pytorch3DDepthRenderer,
    Pytorch3DDepthRendererConfig,
)


def _test_camera(size: int = 64, fx: float = 50.0) -> CameraTW:
    s = float(size)
    c = 0.5 * (s - 1)
    return CameraTW.from_parameters(
        width=torch.tensor([s]),
        height=torch.tensor([s]),
        fx=torch.tensor([fx]),
        fy=torch.tensor([fx]),
        cx=torch.tensor([c]),
        cy=torch.tensor([c]),
        dist_params=torch.zeros(0),
    )


def test_depth_renderer_plane_constant_depth_cpu():
    # Simple square plane at z=2 facing the camera.
    verts = torch.tensor(
        [
            [-1.0, -1.0, 2.0],
            [1.0, -1.0, 2.0],
            [1.0, 1.0, 2.0],
            [-1.0, 1.0, 2.0],
        ],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], dtype=torch.int64)

    cam = _test_camera()
    pose_wc_single = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))  # cam at origin, looking +Z.
    pose_wc = PoseTW(pose_wc_single._data.unsqueeze(0))  # batchify

    cfg = Pytorch3DDepthRendererConfig(device="cpu", is_debug=True, zfar=10.0)
    renderer = Pytorch3DDepthRenderer(cfg)

    depth, pix_to_face, _ = renderer.render(poses=pose_wc, mesh=(verts, faces), camera=cam)

    assert depth.shape == (1, 64, 64)
    valid = pix_to_face >= 0
    hit_ratio = valid.float().mean()
    assert hit_ratio > 0.5
    assert valid.any()
    assert torch.isclose(depth[valid].min(), torch.tensor(2.0), atol=1e-3)


def test_depth_renderer_bounds_mesh_replication_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    verts = torch.tensor(
        [
            [-1.0, -1.0, 2.0],
            [1.0, -1.0, 2.0],
            [1.0, 1.0, 2.0],
            [-1.0, 1.0, 2.0],
        ],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], dtype=torch.int64)
    pose_single = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))
    poses = PoseTW(pose_single.tensor().reshape(1, 12).repeat(5, 1))
    camera = _test_camera()
    reference = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", zfar=10.0, max_views_per_batch=5))
    reference_depth, reference_pix_to_face, reference_cameras = reference.render(
        poses=poses,
        mesh=(verts, faces),
        camera=camera,
    )
    extend_sizes: list[int] = []
    original_extend = Meshes.extend

    def _record_extend(meshes: Meshes, count: int) -> Meshes:
        extend_sizes.append(count)
        return original_extend(meshes, count)

    monkeypatch.setattr(Meshes, "extend", _record_extend)
    renderer = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", zfar=10.0, max_views_per_batch=2))

    depth, pix_to_face, cameras = renderer.render(poses=poses, mesh=(verts, faces), camera=camera)

    assert extend_sizes == [2, 2, 1]
    assert torch.equal(depth, reference_depth)
    assert torch.equal(pix_to_face, reference_pix_to_face)
    assert torch.equal(cameras.R, reference_cameras.R)
    assert torch.equal(cameras.T, reference_cameras.T)
