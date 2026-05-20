import math

import numpy as np
import pytest

pytest.importorskip("efm3d")

import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.pose_generation import (
    CandidateViewGenerator,
    CandidateViewGeneratorConfig,
    CollisionBackend,
    SamplingStrategy,
)
from aria_nbv.pose_generation.candidate_generation_rules import (
    FreeSpaceRule,
    MinDistanceToMeshRule,
    MotionRealismRule,
    PathCollisionRule,
)
from aria_nbv.pose_generation.types import CandidateContext
from aria_nbv.utils.frames import world_up_tensor


def _identity_pose(batch: int = 1, device: torch.device | str = "cpu") -> PoseTW:
    data = torch.tensor([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], device=device)
    if batch > 1:
        data = data.repeat(batch, 1)
    return PoseTW(data)


def _dummy_camera(device: torch.device | str = "cpu") -> CameraTW:
    return CameraTW.from_surreal(
        width=torch.tensor([64.0], device=device),
        height=torch.tensor([64.0], device=device),
        type_str="Pinhole",
        params=torch.tensor([[60.0, 60.0, 32.0, 32.0]], device=device),
        gain=torch.zeros(1, device=device),
        exposure_s=torch.zeros(1, device=device),
        valid_radius=torch.tensor([64.0], device=device),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4, device=device).unsqueeze(0)),
    )


def _mesh_triplet(device: torch.device | str = "cpu") -> tuple[trimesh.Trimesh, torch.Tensor, torch.Tensor]:
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    verts = torch.from_numpy(mesh.vertices).to(dtype=torch.float32, device=device)
    faces = torch.from_numpy(mesh.faces).to(dtype=torch.int64, device=device)
    return mesh, verts, faces


def _default_extent(device: torch.device | str = "cpu") -> torch.Tensor:
    return torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32, device=device)


def _run_generate(cfg: CandidateViewGeneratorConfig, reference_pose: PoseTW | None = None):
    gen = CandidateViewGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.device)
    return gen.generate(
        reference_pose=reference_pose if reference_pose is not None else _identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=_default_extent(cfg.device),
    )


def test_sampling_orients_away_and_zero_roll():
    cfg = CandidateViewGeneratorConfig(
        num_samples=16,
        min_radius=0.5,
        max_radius=0.8,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        is_debug=True,
    )
    result = _run_generate(cfg)

    translations = result.shell_poses.t
    rotations = result.shell_poses.R
    radii = torch.linalg.norm(translations, dim=1)
    assert torch.all(radii >= cfg.min_radius - 1e-4)
    assert torch.all(radii <= cfg.max_radius + 1e-4)

    forward = rotations[:, :, 2]
    expected_dir = torch.nn.functional.normalize(translations, dim=1)
    cos_sim = (forward * expected_dir).sum(dim=1)
    assert torch.allclose(cos_sim, torch.ones_like(cos_sim), atol=1e-3)

    world_up = world_up_tensor(device=translations.device, dtype=translations.dtype)
    x_axis = rotations[:, :, 0]
    roll_component = (x_axis * world_up).sum(dim=1).abs()
    assert torch.all(roll_component < 1e-3)


def test_shell_sampling_uniform_area():
    cfg = CandidateViewGeneratorConfig(
        num_samples=2048,
        min_radius=1.0,
        max_radius=1.0,
        min_elev_deg=-30,
        max_elev_deg=30,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        ensure_collision_free=False,
        ensure_free_space=False,
        verbosity=0,
        is_debug=True,
    )
    result = _run_generate(cfg)
    dirs = torch.nn.functional.normalize(result.shell_poses.t, dim=1)
    elev = torch.asin(dirs[:, 1])

    sin_min = math.sin(math.radians(cfg.min_elev_deg))
    sin_max = math.sin(math.radians(cfg.max_elev_deg))
    expected_mean = 0.5 * (sin_min + sin_max)
    empirical = torch.sin(elev).mean().item()
    assert abs(empirical - expected_mean) < 0.04


def test_min_distance_rule_rejects_near_mesh(monkeypatch):
    mesh = trimesh.creation.box(extents=(0.4, 0.4, 0.4))
    cfg = CandidateViewGeneratorConfig(
        min_distance_to_mesh=0.25,
        min_radius=0.1,
        max_radius=0.1,
        ensure_collision_free=False,
        ensure_free_space=False,
        collect_debug_stats=True,
        verbosity=0,
        is_debug=True,
    )
    rule = MinDistanceToMeshRule(cfg)
    monkeypatch.setattr(
        trimesh.proximity.ProximityQuery,
        "signed_distance",
        lambda self, pts: np.array([0.1, 0.5]),
        raising=False,
    )

    poses = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]),
    )
    ctx = CandidateContext(
        cfg=cfg,
        reference_pose=_identity_pose(),
        sampling_pose=_identity_pose(),
        gt_mesh=mesh,
        mesh_verts=torch.from_numpy(mesh.vertices).float(),
        mesh_faces=torch.from_numpy(mesh.faces).long(),
        occupancy_extent=_default_extent(),
        camera_calib_template=_dummy_camera(),
        shell_poses=poses,
        centers_world=poses.t,
        shell_offsets_ref=poses.t,
        mask_valid=torch.ones(2, dtype=torch.bool),
    )
    rule(ctx)
    assert torch.equal(ctx.mask_valid, torch.tensor([False, True]))
    assert torch.allclose(ctx.debug["min_distance_to_mesh"], torch.tensor([0.2, 0.8]), atol=1e-6)


def test_path_collision_rule_records_p3d_min_clearance(monkeypatch):
    cfg = CandidateViewGeneratorConfig(
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        collision_backend=CollisionBackend.P3D,
        ray_subsample=3,
        step_clearance=0.1,
        collect_debug_stats=True,
        verbosity=0,
        is_debug=True,
    )
    monkeypatch.setattr(
        "aria_nbv.pose_generation.candidate_generation_rules.point_mesh_distance",
        lambda pts, verts, faces: torch.tensor([0.2, 0.05, 0.3, 0.4, 0.3, 0.2], dtype=torch.float32),
    )
    rule = PathCollisionRule(cfg)
    mesh, verts, faces = _mesh_triplet()
    poses = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
    )
    ctx = CandidateContext(
        cfg=cfg,
        reference_pose=_identity_pose(),
        sampling_pose=_identity_pose(),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        occupancy_extent=_default_extent(),
        camera_calib_template=_dummy_camera(),
        shell_poses=poses,
        centers_world=poses.t,
        shell_offsets_ref=poses.t,
        mask_valid=torch.ones(2, dtype=torch.bool),
    )
    rule(ctx)
    assert torch.equal(ctx.mask_valid, torch.tensor([False, True]))
    assert torch.equal(ctx.debug["path_collision_mask"], torch.tensor([True, False]))
    assert torch.allclose(ctx.debug["path_min_clearance_m"], torch.tensor([0.05, 0.2]))


def test_path_collision_rule_blocks_intersecting_ray():
    mesh = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    mesh.apply_translation([0.5, 0.0, 0.0])
    cfg = CandidateViewGeneratorConfig(
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        collision_backend=CollisionBackend.TRIMESH,
        collect_debug_stats=True,
        verbosity=0,
        is_debug=True,
    )
    rule = PathCollisionRule(cfg)
    poses = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
    )
    ctx = CandidateContext(
        cfg=cfg,
        reference_pose=_identity_pose(),
        sampling_pose=_identity_pose(),
        gt_mesh=mesh,
        mesh_verts=torch.from_numpy(mesh.vertices).float(),
        mesh_faces=torch.from_numpy(mesh.faces).long(),
        occupancy_extent=_default_extent(),
        camera_calib_template=_dummy_camera(),
        shell_poses=poses,
        centers_world=poses.t,
        shell_offsets_ref=poses.t,
        mask_valid=torch.ones(2, dtype=torch.bool),
    )
    rule(ctx)
    assert torch.equal(ctx.mask_valid, torch.tensor([False, True]))
    assert torch.equal(ctx.debug["path_collision_mask"], torch.tensor([True, False]))


def test_free_space_rule_bounds_candidates():
    cfg = CandidateViewGeneratorConfig(
        ensure_collision_free=False,
        min_distance_to_mesh=0.0,
        ensure_free_space=True,
        collect_debug_stats=True,
        verbosity=0,
        is_debug=True,
    )
    rule = FreeSpaceRule(cfg)
    extent = torch.tensor([-1.0, 1.0, -1.0, 1.0, -0.5, 0.5])
    mesh, verts, faces = _mesh_triplet()
    poses = PoseTW.from_Rt(
        torch.eye(3).repeat(3, 1, 1),
        torch.tensor([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.0, 0.0, 0.6]]),
    )
    ctx = CandidateContext(
        cfg=cfg,
        reference_pose=_identity_pose(),
        sampling_pose=_identity_pose(),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        occupancy_extent=extent,
        camera_calib_template=_dummy_camera(),
        shell_poses=poses,
        centers_world=poses.t,
        shell_offsets_ref=poses.t,
        mask_valid=torch.ones(3, dtype=torch.bool),
    )
    rule(ctx)
    assert torch.equal(ctx.mask_valid, torch.tensor([True, False, False]))
    assert torch.allclose(ctx.debug["free_space_margin_m"], torch.tensor([0.5, -0.5, -0.1]), atol=1e-6)


def test_motion_realism_rule_records_diagnostics():
    cfg = CandidateViewGeneratorConfig(
        ensure_collision_free=False,
        min_distance_to_mesh=0.0,
        enforce_motion_realism=True,
        max_step_distance_m=2.0,
        max_height_delta_m=1.0,
        max_backward_step_m=1.0,
        max_yaw_delta_deg=90.0,
        collect_debug_stats=True,
        verbosity=0,
        is_debug=True,
    )
    rule = MotionRealismRule(cfg)
    mesh, verts, faces = _mesh_triplet()
    poses = PoseTW.from_Rt(
        torch.eye(3).repeat(2, 1, 1),
        torch.tensor([[0.3, 0.0, 0.0], [0.0, 0.2, -0.4]]),
    )
    ctx = CandidateContext(
        cfg=cfg,
        reference_pose=_identity_pose(),
        sampling_pose=_identity_pose(),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        occupancy_extent=_default_extent(),
        camera_calib_template=_dummy_camera(),
        shell_poses=poses,
        centers_world=poses.t,
        shell_offsets_ref=poses.t,
        mask_valid=torch.ones(2, dtype=torch.bool),
    )
    rule(ctx)
    assert torch.equal(ctx.mask_valid, torch.tensor([True, True]))
    assert torch.allclose(ctx.debug["motion_step_length_m"], torch.linalg.norm(poses.t, dim=1))
    assert torch.allclose(ctx.debug["motion_height_delta_m"], torch.tensor([0.0, 0.2]))
    assert torch.allclose(ctx.debug["motion_backward_step_m"], torch.tensor([0.0, 0.4]))
    assert torch.allclose(ctx.debug["motion_yaw_delta_rad"], torch.zeros(2))
    assert torch.equal(ctx.debug["motion_realism_reject_mask"], torch.tensor([False, False]))


def test_candidate_generator_pipeline_synthetic():
    cfg = CandidateViewGeneratorConfig(
        num_samples=16,
        min_radius=0.4,
        max_radius=0.6,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        is_debug=True,
    )
    result = _run_generate(cfg)
    expected_draws = math.ceil(cfg.num_samples * cfg.oversample_factor)
    assert result.views.tensor().shape[0] == int(result.mask_valid.sum().item())
    assert result.mask_valid.shape[0] == expected_draws
    assert torch.all(result.mask_valid)


@pytest.mark.slow
def test_candidate_generator_with_real_dataset_sample():
    try:
        dataset = AseEfmDatasetConfig(load_meshes=True, verbosity=0).setup_target()
        sample = next(iter(dataset))
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"ASE dataset not available locally: {exc}")

    cfg = CandidateViewGeneratorConfig(
        num_samples=32,
        min_radius=0.5,
        max_radius=1.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_max_azimuth_deg=0.0,
        view_max_elevation_deg=0.0,
        verbosity=0,
        is_debug=True,
    )
    result = CandidateViewGenerator(cfg).generate_from_typed_sample(sample)
    expected_draws = math.ceil(cfg.num_samples * cfg.oversample_factor)
    assert result.mask_valid.shape[0] == expected_draws
    assert result.views.tensor().shape[0] == int(result.mask_valid.sum().item())
    assert result.mask_valid.any()
