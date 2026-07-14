import platform

import torch
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.rendering.pytorch3d_depth_renderer import (
    Pytorch3DDepthRenderer,
    Pytorch3DDepthRendererConfig,
)
from aria_nbv.rri_metrics.point_mesh import chamfer_point_mesh


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


def test_depth_renderer_plane_constant_depth_cpu(monkeypatch):
    require_mojo = platform.system() == "Darwin" and platform.machine() == "arm64"
    monkeypatch.setenv("PYTORCH3D_REQUIRE_MOJO", "1" if require_mojo else "0")

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
    distance = chamfer_point_mesh(torch.tensor([[0.0, 0.0, 3.0]]), verts, faces)
    assert torch.isclose(distance.accuracy, torch.tensor(1.0))
    assert torch.isclose(distance.completeness, torch.tensor(1.0))

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
