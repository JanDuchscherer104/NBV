# ruff: noqa: E402

import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch
import trimesh

# Make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[3] / "external" / "efm3d"))
power_spherical_stub = types.ModuleType("power_spherical")
power_spherical_stub.HypersphericalUniform = object
power_spherical_stub.PowerSpherical = object
sys.modules.setdefault("power_spherical", power_spherical_stub)

from efm3d.aria import CameraTW, PoseTW
from efm3d.aria.aria_constants import (
    ARIA_CALIB,
    ARIA_FRAME_ID,
    ARIA_IMG,
    ARIA_IMG_TIME_NS,
    ARIA_POINTS_DIST_STD,
    ARIA_POINTS_INV_DIST_STD,
    ARIA_POINTS_TIME_NS,
    ARIA_POINTS_VOL_MAX,
    ARIA_POINTS_VOL_MIN,
    ARIA_POINTS_WORLD,
    ARIA_POSE_T_WORLD_RIG,
    ARIA_POSE_TIME_NS,
)

from aria_nbv.data_handling.raw.views import EfmSnippetView
from aria_nbv.pose_generation.types import CandidateSamplingResult

try:
    import pytorch3d.renderer as _pytorch3d_renderer  # noqa: F401
except Exception:  # pragma: no cover - availability guard
    PYTORCH3D_AVAILABLE = False
else:  # pragma: no cover - availability guard
    PYTORCH3D_AVAILABLE = True

if PYTORCH3D_AVAILABLE:
    from aria_nbv.rendering import CandidateDepthRendererConfig, Pytorch3DDepthRendererConfig
else:  # pragma: no cover - availability guard
    CandidateDepthRendererConfig = None  # type: ignore[assignment]
    Pytorch3DDepthRendererConfig = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(
    not PYTORCH3D_AVAILABLE,
    reason="PyTorch3D renderer bindings are required for renderer tests.",
)


def test_pytorch3d_config_accepts_debug() -> None:
    cfg = Pytorch3DDepthRendererConfig(device="cpu", is_debug=True)
    assert cfg.is_debug is True

    renderer = cfg.setup_target()
    assert renderer.console.is_debug is True


def _make_camera(width: int = 64, height: int = 64) -> CameraTW:
    params = torch.tensor([[60.0, 60.0, width / 2.0, height / 2.0]], dtype=torch.float32)
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


def _make_mesh(z_center: float = 4.0, extent: float = 10.0) -> trimesh.Trimesh:
    verts = np.array(
        [
            [-extent, -extent, z_center],
            [extent, -extent, z_center],
            [extent, extent, z_center],
            [-extent, extent, z_center],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 2, 1], [0, 3, 2]])
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def _make_snippet(
    mesh: trimesh.Trimesh,
    camera: CameraTW,
    *,
    volume_min: torch.Tensor | None = None,
    volume_max: torch.Tensor | None = None,
) -> EfmSnippetView:
    num_frames = 1
    rgb_key = ARIA_IMG[0]
    calib_key = ARIA_CALIB[0]
    time_key = ARIA_IMG_TIME_NS[0]
    frame_key = ARIA_FRAME_ID[0]

    size = camera.size.squeeze()
    img_w = int(size[0].item())
    img_h = int(size[1].item())
    images = torch.zeros(num_frames, 3, img_h, img_w)
    times = torch.zeros(num_frames, dtype=torch.int64)
    frame_ids = torch.arange(num_frames, dtype=torch.int64)
    pose_seq = PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))
    sem_points = torch.zeros(num_frames, 1, 3)
    if volume_min is None:
        volume_min = torch.tensor([-1.0, -1.0, -1.0])
    if volume_max is None:
        volume_max = torch.tensor([1.0, 1.0, 1.0])

    efm = {
        rgb_key: images,
        calib_key: camera,
        time_key: times,
        frame_key: frame_ids,
        ARIA_POSE_T_WORLD_RIG: pose_seq,
        ARIA_POSE_TIME_NS: times,
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81]),
        ARIA_POINTS_WORLD: sem_points,
        ARIA_POINTS_DIST_STD: torch.zeros(num_frames, 1),
        ARIA_POINTS_INV_DIST_STD: torch.zeros(num_frames, 1),
        ARIA_POINTS_TIME_NS: times,
        ARIA_POINTS_VOL_MIN: volume_min,
        ARIA_POINTS_VOL_MAX: volume_max,
    }
    mesh_verts = torch.from_numpy(mesh.vertices).to(dtype=torch.float32)
    mesh_faces = torch.from_numpy(mesh.faces).to(dtype=torch.int64)
    return EfmSnippetView(
        efm=efm,
        scene_id="demo_scene",
        snippet_id="demo_snippet",
        mesh=mesh,
        mesh_verts=mesh_verts,
        mesh_faces=mesh_faces,
    )


def _make_candidates(num: int = 1, z: float = 2.0) -> CandidateSamplingResult:
    cam_single = _make_camera()
    width = cam_single.size[0].item()
    height = cam_single.size[1].item()
    f_vals = cam_single.f.reshape(-1, 2)[0]
    c_vals = cam_single.c.reshape(-1, 2)[0]
    device = f_vals.device
    t_ref_cam = PoseTW.from_Rt(
        torch.eye(3, device=device).unsqueeze(0).repeat(num, 1, 1),
        torch.tensor([[0.0, 0.0, z]], device=device).repeat(num, 1),
    )
    cams = CameraTW.from_parameters(
        width=torch.full((num, 1), float(width), device=device),
        height=torch.full((num, 1), float(height), device=device),
        fx=torch.full((num, 1), f_vals[0].item(), device=device),
        fy=torch.full((num, 1), f_vals[1].item(), device=device),
        cx=torch.full((num, 1), c_vals[0].item(), device=device),
        cy=torch.full((num, 1), c_vals[1].item(), device=device),
        gain=torch.zeros((num, 1), device=device),
        exposure_s=torch.zeros((num, 1), device=device),
        valid_radiusx=torch.full((num, 1), max(width, height), device=device),
        valid_radiusy=torch.full((num, 1), max(width, height), device=device),
        T_camera_rig=t_ref_cam,
        dist_params=cam_single.dist.expand(num, -1),
    )
    return CandidateSamplingResult(
        views=cams,
        reference_pose=_make_pose(),
        mask_valid=torch.ones(num, dtype=torch.bool),
        masks={},
        shell_poses=t_ref_cam,
    )


def test_pytorch3d_renderer_produces_depth():
    mesh = _make_mesh()
    cam = _make_camera()
    pose = _make_pose()

    cfg = Pytorch3DDepthRendererConfig(device="cpu", verbosity=0)
    renderer = cfg.setup_target()

    verts = torch.from_numpy(mesh.vertices).to(dtype=torch.float32)
    faces = torch.from_numpy(mesh.faces).to(dtype=torch.int64)
    depth, _, _ = renderer.render(poses=pose, mesh=(verts, faces), camera=cam)
    depth = depth.squeeze(0)
    assert depth.shape == (64, 64)
    hit_ratio = float((depth < cfg.zfar).float().mean().item())
    assert torch.isfinite(depth).all()
    assert hit_ratio > 0.2  # large plane should cover most pixels
    assert depth.min().item() < cfg.zfar


def test_candidate_depth_renderer_ignores_mask_and_respects_cap():
    mesh = _make_mesh()
    cam = _make_camera()
    sample = _make_snippet(mesh, cam)
    candidates = _make_candidates(num=3, z=2.0)
    candidates.mask_valid[0] = False

    cfg = CandidateDepthRendererConfig(
        renderer=Pytorch3DDepthRendererConfig(device="cpu", verbosity=0),
        max_candidates_final=2,
    )
    renderer = cfg.setup_target()

    batch = renderer.render(sample=sample, candidates=candidates)
    assert batch.depths.shape[0] == 2
    assert torch.equal(
        batch.candidate_indices,
        torch.tensor([0, 1], device=batch.candidate_indices.device),
    )
    assert batch.depths_valid_mask.shape[0] == 2


@pytest.mark.xfail(reason="PyTorch3D backface culling keeps inward-facing quads when camera is inside the mesh.")
def test_backface_culling_blocks_interior_walls():
    cam = _make_camera()
    pose = _make_pose(z=0.0)
    mesh = trimesh.creation.box(extents=(2.0, 2.0, 2.0))

    cfg_culled = Pytorch3DDepthRendererConfig(device="cpu", cull_backfaces=True, two_sided=False)
    depth_culled = cfg_culled.setup_target().render_depth(pose_world_cam=pose, mesh=mesh, camera=cam)

    cfg_two_sided = Pytorch3DDepthRendererConfig(device="cpu", cull_backfaces=True, two_sided=True)
    depth_two_sided = cfg_two_sided.setup_target().render_depth(pose_world_cam=pose, mesh=mesh, camera=cam)

    hit_ratio_culled = float((depth_culled < cfg_culled.zfar).float().mean().item())
    hit_ratio_two_sided = float((depth_two_sided < cfg_two_sided.zfar).float().mean().item())

    assert hit_ratio_two_sided >= hit_ratio_culled


def test_proxy_walls_expand_to_occupancy_bounds():
    pytest.skip("Proxy wall logic removed; test obsolete.")


def test_candidate_renderer_builds_ordered_occupancy_extent():
    pytest.skip("Occupancy extent helper removed; test obsolete.")
