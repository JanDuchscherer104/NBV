import math

import pytest

pytest.importorskip("efm3d")

import torch
import trimesh
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.pose_generation import CandidateViewGeneratorConfig
from aria_nbv.pose_generation.types import ViewDirectionMode
from aria_nbv.utils.frames import world_up_tensor


def _local_roll_z(angle_rad: float, *, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return torch.tensor([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], device=device, dtype=dtype)


def _make_level_pose(*, wup: torch.Tensor) -> PoseTW:
    """Construct a pose with +Y aligned to `wup` and +Z horizontal."""

    wup = wup / wup.norm().clamp_min(1e-6)
    basis = torch.eye(3, device=wup.device, dtype=wup.dtype)
    idx = torch.argmin((basis @ wup).abs())
    z_w = basis[idx]
    z_w = z_w - (z_w * wup).sum() * wup
    z_w = z_w / z_w.norm().clamp_min(1e-6)
    x_w = torch.cross(wup, z_w, dim=-1)
    x_w = x_w / x_w.norm().clamp_min(1e-6)
    y_w = torch.cross(z_w, x_w, dim=-1)
    r_wr = torch.stack([x_w, y_w, z_w], dim=-1)
    return PoseTW.from_Rt(r_wr, torch.zeros(3, device=wup.device, dtype=wup.dtype))


def _dummy_mesh(*, device: torch.device) -> tuple[trimesh.Trimesh, torch.Tensor, torch.Tensor]:
    verts = torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], device=device)
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64, device=device)
    mesh = trimesh.Trimesh(vertices=verts.cpu().numpy(), faces=faces.cpu().numpy(), process=False)
    return mesh, verts, faces


def test_align_to_gravity_respects_world_elevation_caps() -> None:
    device = torch.device("cpu")
    dtype = torch.float32
    wup = world_up_tensor(device=device, dtype=dtype)

    ref_level = _make_level_pose(wup=wup)
    ref_roll = PoseTW.from_Rt(ref_level.R @ _local_roll_z(math.pi / 2, device=device, dtype=dtype), ref_level.t)

    mesh, verts, faces = _dummy_mesh(device=device)
    cam_template = CameraTW(torch.zeros(34, device=device, dtype=dtype))
    occ = torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], device=device, dtype=dtype)

    cfg_common = {
        "device": device,
        "num_samples": 256,
        "oversample_factor": 1.0,
        "ensure_free_space": False,
        "ensure_collision_free": False,
        "min_distance_to_mesh": 0.0,
        "min_radius": 1.0,
        "max_radius": 1.0,
        "min_elev_deg": -5.0,
        "max_elev_deg": 5.0,
        "delta_azimuth_deg": 360.0,
        "seed": 0,
    }

    cfg_no_align = CandidateViewGeneratorConfig(**cfg_common, align_to_gravity=False)
    cfg_align = CandidateViewGeneratorConfig(**cfg_common, align_to_gravity=True)

    out_no_align = cfg_no_align.setup_target().generate(
        reference_pose=ref_roll,
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=cam_template,
        occupancy_extent=occ,
    )
    out_align = cfg_align.setup_target().generate(
        reference_pose=ref_roll,
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=cam_template,
        occupancy_extent=occ,
    )

    def elev_deg(offsets_world: torch.Tensor) -> torch.Tensor:
        dirs = offsets_world / offsets_world.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        dot = (dirs * wup.view(1, 3)).sum(dim=-1).clamp(-1.0, 1.0)
        return torch.rad2deg(torch.asin(dot))

    elev_no_align = elev_deg(out_no_align.shell_poses.t - ref_roll.t)
    elev_align = elev_deg(out_align.shell_poses.t - ref_roll.t)

    assert torch.isfinite(elev_no_align).all()
    assert torch.max(elev_align) <= 5.0 + 1e-3
    assert torch.min(elev_align) >= -5.0 - 1e-3


def test_align_to_gravity_levels_forward_rig_orientations() -> None:
    device = torch.device("cpu")
    dtype = torch.float32
    wup = world_up_tensor(device=device, dtype=dtype)

    ref_level = _make_level_pose(wup=wup)
    ref_roll = PoseTW.from_Rt(ref_level.R @ _local_roll_z(math.pi / 2, device=device, dtype=dtype), ref_level.t)

    mesh, verts, faces = _dummy_mesh(device=device)
    cam_template = CameraTW(torch.zeros(34, device=device, dtype=dtype))
    occ = torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], device=device, dtype=dtype)

    cfg_common = {
        "device": device,
        "num_samples": 16,
        "oversample_factor": 1.0,
        "ensure_free_space": False,
        "ensure_collision_free": False,
        "min_distance_to_mesh": 0.0,
        "view_direction_mode": ViewDirectionMode.FORWARD_RIG,
        "view_max_azimuth_deg": 0.0,
        "view_max_elevation_deg": 0.0,
        "seed": 0,
    }

    cfg_no_align = CandidateViewGeneratorConfig(**cfg_common, align_to_gravity=False)
    cfg_align = CandidateViewGeneratorConfig(**cfg_common, align_to_gravity=True)

    out_no_align = cfg_no_align.setup_target().generate(
        reference_pose=ref_roll,
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=cam_template,
        occupancy_extent=occ,
    )
    out_align = cfg_align.setup_target().generate(
        reference_pose=ref_roll,
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=cam_template,
        occupancy_extent=occ,
    )

    dot_no_align = (out_no_align.shell_poses.R[:, :, 1] * wup.view(1, 3)).sum(dim=-1)
    dot_align = (out_align.shell_poses.R[:, :, 1] * wup.view(1, 3)).sum(dim=-1)

    assert torch.all(dot_no_align < -0.8)
    assert torch.all(dot_align > 0.99)


def test_gravity_aligned_sampling_and_motion_realism_use_the_same_world_up_axis() -> None:
    device = torch.device("cpu")
    dtype = torch.float32
    wup = world_up_tensor(device=device, dtype=dtype)
    ref_level = _make_level_pose(wup=wup)
    ref_roll = PoseTW.from_Rt(ref_level.R @ _local_roll_z(math.pi / 2, device=device, dtype=dtype), ref_level.t)
    mesh, verts, faces = _dummy_mesh(device=device)
    cam_template = CameraTW(torch.zeros(34, device=device, dtype=dtype))
    occ = torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], device=device, dtype=dtype)
    config = CandidateViewGeneratorConfig(
        device=device,
        num_samples=128,
        oversample_factor=1.0,
        align_to_gravity=True,
        min_radius=1.0,
        max_radius=1.0,
        min_elev_deg=-5.0,
        max_elev_deg=5.0,
        delta_azimuth_deg=360.0,
        view_direction_mode=ViewDirectionMode.FORWARD_RIG,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        ensure_free_space=False,
        ensure_collision_free=False,
        min_distance_to_mesh=0.0,
        enforce_motion_realism=True,
        max_step_distance_m=1.01,
        max_height_delta_m=0.1,
        max_backward_step_m=None,
        max_yaw_delta_deg=1.0,
        seed=0,
    )

    result = config.setup_target().generate(
        reference_pose=ref_roll,
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=cam_template,
        occupancy_extent=occ,
    )

    assert result.mask_valid.all()
