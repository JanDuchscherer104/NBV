import numpy as np
import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.rendering.efm3d_depth_renderer import Efm3dDepthRendererConfig


def _make_camera(width: int = 32, height: int = 32) -> CameraTW:
    params = torch.tensor([[40.0, 40.0, width / 2.0, height / 2.0]], dtype=torch.float32)
    return CameraTW.from_surreal(
        width=torch.tensor([float(width)], dtype=torch.float32),
        height=torch.tensor([float(height)], dtype=torch.float32),
        type_str="Pinhole",
        params=params,
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([max(width, height)], dtype=torch.float32),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )


def _make_pose(z: float = 0.0) -> PoseTW:
    rot = torch.eye(3).unsqueeze(0)
    t = torch.tensor([[0.0, 0.0, z]], dtype=torch.float32)
    return PoseTW.from_Rt(rot, t)


def test_efm3d_depth_renderer_hits_plane():
    mesh = trimesh.creation.box(
        extents=(4.0, 4.0, 0.01), transform=trimesh.transformations.translation_matrix([0, 0, 4])
    )
    cam = _make_camera()
    pose = _make_pose(z=0.0)

    cfg = Efm3dDepthRendererConfig(device="cpu", zfar=10.0, add_proxy_walls=False)
    renderer = cfg.setup_target()

    depth = renderer.render_depth(pose_world_cam=pose, mesh=mesh, camera=cam)
    assert depth.shape == (32, 32)
    hit_ratio = float((depth < cfg.zfar).float().mean().item())
    assert torch.isfinite(depth).all()
    assert hit_ratio > 0.9
    assert depth.min().item() > 3.0


def test_proxy_walls_expand_bounds():
    mesh = trimesh.creation.box(
        extents=(1.0, 1.0, 1.0), transform=trimesh.transformations.translation_matrix([0, 0, 0.5])
    )
    cfg = Efm3dDepthRendererConfig(device="cpu", add_proxy_walls=True, proxy_wall_area_threshold=0.9)
    renderer = cfg.setup_target()
    occ_extent = torch.tensor([-2.0, 2.0, -3.0, 3.0, -4.0, 4.0])

    merged = renderer._maybe_with_proxy_walls(mesh, occupancy_extent=occ_extent)
    vmin, vmax = merged.bounds
    assert np.allclose(vmin, [-2.0, -3.0, -4.0], atol=1e-4)
    assert np.allclose(vmax, [2.0, 3.0, 4.0], atol=1e-4)
    assert merged.faces.shape[0] > mesh.faces.shape[0]


def test_camera_ray_grid_is_reused_for_same_calibration() -> None:
    """Repeated views reuse the camera-space pixel grid while transforming poses."""

    renderer = Efm3dDepthRendererConfig(device="cpu", add_proxy_walls=False).setup_target()
    rotation = np.eye(3, dtype=np.float32)
    translation = np.zeros(3, dtype=np.float32)
    first_origins, first_dirs = renderer._ray_grid(
        width=8,
        height=6,
        fx=10.0,
        fy=11.0,
        cx=3.5,
        cy=2.5,
        r_wc=rotation,
        t_wc=translation,
    )
    second_origins, second_dirs = renderer._ray_grid(
        width=8,
        height=6,
        fx=10.0,
        fy=11.0,
        cx=3.5,
        cy=2.5,
        r_wc=rotation,
        t_wc=translation,
    )

    assert len(renderer._camera_ray_grid_cache) == 1
    assert np.array_equal(first_origins, second_origins)
    assert np.array_equal(first_dirs, second_dirs)
