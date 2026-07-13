# ruff: noqa: E402

import sys
import types
from pathlib import Path

import torch
import trimesh

# Make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[3] / "external" / "efm3d"))
# Stub out optional dependency used in pose_generation __init__.
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
from aria_nbv.rendering import CandidateDepthRendererConfig, Pytorch3DDepthRendererConfig


def _make_camera(width: int = 16, height: int = 16) -> CameraTW:
    params = torch.tensor([[20.0, 20.0, width / 2.0, height / 2.0]], dtype=torch.float32)
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


def _make_mesh(z_center: float = 2.0, extent: float = 4.0) -> trimesh.Trimesh:
    verts = torch.tensor(
        [
            [-extent, -extent, z_center],
            [extent, -extent, z_center],
            [extent, extent, z_center],
            [-extent, extent, z_center],
        ],
        dtype=torch.float32,
    ).numpy()
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], dtype=torch.int64).numpy()
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def _make_snippet(mesh: trimesh.Trimesh, camera: CameraTW) -> EfmSnippetView:
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
        ARIA_POINTS_VOL_MIN: torch.tensor([-1.0, -1.0, -1.0]),
        ARIA_POINTS_VOL_MAX: torch.tensor([1.0, 1.0, 1.0]),
    }
    mesh_verts = torch.from_numpy(mesh.vertices).to(dtype=torch.float32)
    mesh_faces = torch.from_numpy(mesh.faces).to(dtype=torch.int64)
    return EfmSnippetView(
        efm=efm,
        scene_id="cpu_scene",
        snippet_id="cpu_snippet",
        mesh=mesh,
        mesh_verts=mesh_verts,
        mesh_faces=mesh_faces,
    )


def _make_candidates(num: int = 1, z: float = 1.0) -> CandidateSamplingResult:
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
    cam = CameraTW.from_parameters(
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
        views=cam,
        reference_pose=_make_pose(),
        mask_valid=torch.ones(num, dtype=torch.bool),
        masks={},
        shell_poses=t_ref_cam,
    )


def test_candidate_renderer_cpu_backend_runs():
    mesh = _make_mesh()
    cam = _make_camera()
    sample = _make_snippet(mesh, cam)
    candidates = _make_candidates(num=2, z=1.0)

    cfg = CandidateDepthRendererConfig(
        renderer=Pytorch3DDepthRendererConfig(device="cpu", verbosity=0),
        max_candidates_final=2,
        resolution_scale=1.0,
    )
    renderer = cfg.setup_target()

    batch = renderer.render(sample=sample, candidates=candidates)
    assert batch.depths.shape[0] == 2
    assert batch.depths.shape[1:] == (16, 16)
    assert torch.isfinite(batch.depths).all()
