"""Tests for mixed finite-candidate generation."""

# ruff: noqa: S101

from __future__ import annotations

import pytest

pytest.importorskip("efm3d")

import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGenerator,
    CandidateMixtureViewGeneratorConfig,
    CandidatePositionMode,
    CandidateViewGeneratorConfig,
    SamplingStrategy,
    ViewDirectionMode,
    candidate_position_id,
    candidate_strategy_id,
)
from aria_nbv.targets import TargetDescriptor


def _identity_pose(device: torch.device | str = "cpu") -> PoseTW:
    return PoseTW(
        torch.tensor(
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            device=device,
        )
    )


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


def _base_cfg() -> CandidateViewGeneratorConfig:
    return CandidateViewGeneratorConfig(
        num_samples=6,
        oversample_factor=1.0,
        min_radius=0.8,
        max_radius=0.8,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        view_max_azimuth_deg=60.0,
        view_max_elevation_deg=30.0,
        verbosity=0,
        seed=0,
        is_debug=True,
    )


def _run_generate(cfg: CandidateMixtureViewGeneratorConfig):
    mesh, verts, faces = _mesh_triplet(cfg.device)
    return CandidateMixtureViewGenerator(cfg).generate(
        reference_pose=_identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
        runtime_context=CandidateGenerationRuntimeContext(descriptor=_descriptor()),
    )


def test_mixed_sampler_fixed_counts_and_full_shell_provenance() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[
            CandidateMixtureComponentConfig(name="target", count=4, strategy=ViewDirectionMode.TARGET_POINT),
            CandidateMixtureComponentConfig(name="away", count=2, strategy=ViewDirectionMode.RADIAL_AWAY),
        ],
    )

    result = _run_generate(cfg)

    assert result.mask_valid.shape[0] == 6
    assert result.strategy_id is not None
    assert result.position_id is not None
    assert result.mixture_id is not None
    assert result.sampler_probability is not None
    assert (
        result.strategy_id.tolist()
        == [candidate_strategy_id(ViewDirectionMode.TARGET_POINT)] * 4
        + [candidate_strategy_id(ViewDirectionMode.RADIAL_AWAY)] * 2
    )
    assert result.position_id.tolist() == [candidate_position_id(CandidatePositionMode.UPPER_BOUND_FREE_SHELL)] * 6
    assert result.mixture_id.tolist() == [0, 0, 0, 0, 1, 1]
    assert torch.allclose(
        result.sampler_probability,
        torch.full((6,), 1.0 / 6.0, device=result.sampler_probability.device),
    )
    assert result.views.tensor().shape[0] == int(result.mask_valid.sum().item())


def test_target_point_component_requires_runtime_target_context() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[CandidateMixtureComponentConfig(name="target", count=2, strategy=ViewDirectionMode.TARGET_POINT)],
    )
    mesh, verts, faces = _mesh_triplet(cfg.device)

    with pytest.raises(ValueError, match="target_center_world"):
        CandidateMixtureViewGenerator(cfg).generate(
            reference_pose=_identity_pose(device=cfg.device),
            gt_mesh=mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            camera_calib_template=_dummy_camera(cfg.device),
            occupancy_extent=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
        )


def test_target_point_component_applies_nonzero_seminar_jitter_around_target_gaze() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[CandidateMixtureComponentConfig(name="target", count=4, strategy=ViewDirectionMode.TARGET_POINT)],
    )

    result = _run_generate(cfg)
    yaw = result.extras["view_jitter_yaw_deg"]
    pitch = result.extras["view_jitter_pitch_deg"]

    assert torch.max(yaw.abs()) <= 60.0
    assert torch.max(pitch.abs()) <= 30.0
    assert torch.any(yaw.abs() > 1e-6)
    assert torch.any(pitch.abs() > 1e-6)


def test_default_mixture_uses_realistic_position_families_without_free_shell() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(
            update={
                "position_mode": CandidatePositionMode.FORWARD_LOCAL,
                "enforce_motion_realism": True,
                "max_step_distance_m": 1.0,
                "max_height_delta_m": 0.25,
                "max_backward_step_m": 0.25,
                "max_yaw_delta_deg": 70.0,
                "collect_debug_stats": True,
            }
        )
    )

    result = _run_generate(cfg)

    assert cfg.total_count == 60
    assert [component.name for component in cfg.components] == [
        "forward_local",
        "target_bearing_local",
        "lateral_target_bypass",
    ]
    assert [component.count for component in cfg.components] == [24, 24, 12]
    assert cfg.base.max_step_distance_m == pytest.approx(1.0)
    assert cfg.base.max_height_delta_m == pytest.approx(0.25)
    assert cfg.base.max_backward_step_m == pytest.approx(0.25)
    assert cfg.base.max_yaw_delta_deg == pytest.approx(70.0)
    assert result.position_id is not None
    assert CandidatePositionMode.UPPER_BOUND_FREE_SHELL.value not in set(result.component_name or ())
    assert candidate_position_id(CandidatePositionMode.FORWARD_LOCAL) in result.position_id.tolist()
    assert candidate_position_id(CandidatePositionMode.TARGET_BEARING_LOCAL) in result.position_id.tolist()
    assert candidate_position_id(CandidatePositionMode.LATERAL_TARGET_BYPASS) in result.position_id.tolist()
    assert "motion_step_length_m" in result.extras
    assert "target_bearing_yaw_rad" in result.extras


def test_mixture_rejects_zero_resolved_view_jitter() -> None:
    with pytest.raises(ValueError, match="nonzero resolved azimuth and elevation view jitter"):
        CandidateMixtureViewGeneratorConfig(
            base=_base_cfg(),
            components=[
                CandidateMixtureComponentConfig(
                    name="invalid_zero_jitter",
                    count=6,
                    view_mode=ViewDirectionMode.FORWARD_RIG,
                    view_max_azimuth_deg=0.0,
                    view_max_elevation_deg=30.0,
                )
            ],
        )


def test_rich_local_five_family_is_named_ablation() -> None:
    cfg = CandidateMixtureViewGeneratorConfig.rich_local_five_family()

    assert [component.name for component in cfg.components] == [
        "target_bearing_local",
        "forward_local",
        "lateral_target_bypass",
        "local_refinement",
        "revisit_backtrack",
    ]
    assert [component.count for component in cfg.components] == [18, 18, 12, 6, 6]


def test_paired_component_reuses_centers_and_retains_gaze_variants() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[
            CandidateMixtureComponentConfig(
                name="target_forward_pair",
                count=4,
                view_mode=ViewDirectionMode.TARGET_POINT,
                paired_view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
            )
        ],
    )

    result = _run_generate(cfg)

    assert cfg.total_count == 8
    assert result.mask_valid.numel() == 8
    assert result.extras["position_pair_id"].cpu().tolist() == [0, 1, 2, 3, 0, 1, 2, 3]
    assert result.extras["gaze_variant_id"].cpu().tolist() == [0, 0, 0, 0, 1, 1, 1, 1]
    centers = result.shell_poses.t.reshape(-1, 3)
    assert torch.allclose(centers[:4], centers[4:])
    forward = result.shell_poses.R[:, :, 2]
    assert not torch.allclose(forward[:4], forward[4:])
    assert result.component_name == ("target_forward_pair",) * 4 + ("target_forward_pair__paired_forward_rig",) * 4
    assert torch.allclose(result.sampler_probability, torch.full_like(result.sampler_probability, 1.0 / 8.0))


def test_paired_center_gaze_preset_keeps_sixty_candidate_rows() -> None:
    cfg = CandidateMixtureViewGeneratorConfig.paired_center_gaze_family()

    assert cfg.total_count == 60
    assert cfg.components[0].paired_view_mode is ViewDirectionMode.FORWARD_RIG


def test_reviewed_component_templates_preserve_rich_family_fields() -> None:
    writer_target_bearing = CandidateMixtureComponentConfig(
        name="target_bearing_local",
        count=24,
        view_mode=ViewDirectionMode.TARGET_POINT,
        position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
        sampling_strategy=SamplingStrategy.UNIFORM_SPHERE,
        view_sampling_strategy=SamplingStrategy.FORWARD_POWERSPHERICAL,
        min_radius=0.4,
        max_radius=1.1,
        min_elev_deg=-8.0,
        max_elev_deg=14.0,
        delta_azimuth_deg=90.0,
        kappa=6.0,
        view_kappa=12.0,
        view_max_angle_deg=30.0,
        view_max_azimuth_deg=20.0,
        view_max_elevation_deg=10.0,
        view_roll_jitter_deg=5.0,
    )
    components = CandidateMixtureViewGeneratorConfig.reviewed_component_templates(
        (
            ("target_bearing_local", 18),
            ("forward_local", 18),
            ("lateral_target_bypass", 12),
            ("local_refinement", 6),
            ("revisit_backtrack", 6),
        ),
        existing_components=[writer_target_bearing],
    )

    assert sum(component.count for component in components) == 60
    by_name = {component.name: component for component in components}
    assert by_name["target_bearing_local"].model_dump(exclude={"count"}) == writer_target_bearing.model_dump(
        exclude={"count"}
    )
    assert by_name["target_bearing_local"].count == 18
    assert by_name["target_bearing_local"].min_radius == pytest.approx(0.4)
    assert by_name["target_bearing_local"].max_radius == pytest.approx(1.1)
    assert by_name["local_refinement"].view_mode is ViewDirectionMode.TARGET_POINT
    assert by_name["local_refinement"].min_radius == pytest.approx(0.25)
    assert by_name["local_refinement"].max_radius == pytest.approx(0.7)
    assert by_name["revisit_backtrack"].position_mode is CandidatePositionMode.REVISIT_BACKTRACK
    assert by_name["revisit_backtrack"].min_radius == pytest.approx(0.25)
    assert by_name["revisit_backtrack"].max_radius == pytest.approx(0.25)
    assert all(
        component.view_max_azimuth_deg is None for name, component in by_name.items() if name != "target_bearing_local"
    )
    assert all(
        component.view_max_elevation_deg is None
        for name, component in by_name.items()
        if name != "target_bearing_local"
    )

    with pytest.raises(ValueError, match="unsupported reviewed candidate component schedule"):
        CandidateMixtureViewGeneratorConfig.reviewed_component_templates((("new_family", 60),))


def test_radial_target_backtrack_family_is_diverse_rollout_profile() -> None:
    cfg = CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family()

    assert cfg.total_count == 48
    assert cfg.base.num_samples == 48
    assert cfg.base.max_step_distance_m == pytest.approx(1.25)
    assert cfg.base.max_height_delta_m == pytest.approx(0.35)
    assert cfg.base.max_backward_step_m == pytest.approx(0.45)
    assert cfg.base.max_yaw_delta_deg == pytest.approx(90.0)
    assert cfg.base.collect_rule_masks is True
    assert cfg.base.collect_debug_stats is True
    assert [component.name for component in cfg.components] == [
        "radial_towards_target_bearing",
        "radial_away_target_bearing",
        "revisit_backtrack",
        "target_point_anchor",
    ]
    assert [component.count for component in cfg.components] == [16, 16, 12, 4]

    component_by_name = {component.name: component for component in cfg.components}
    assert component_by_name["radial_towards_target_bearing"].view_mode is ViewDirectionMode.RADIAL_TOWARDS
    assert (
        component_by_name["radial_towards_target_bearing"].position_mode is CandidatePositionMode.TARGET_BEARING_LOCAL
    )
    assert component_by_name["radial_away_target_bearing"].view_mode is ViewDirectionMode.RADIAL_AWAY
    assert component_by_name["radial_away_target_bearing"].position_mode is CandidatePositionMode.TARGET_BEARING_LOCAL
    assert component_by_name["revisit_backtrack"].view_mode is ViewDirectionMode.FORWARD_RIG
    assert component_by_name["revisit_backtrack"].position_mode is CandidatePositionMode.REVISIT_BACKTRACK
    assert component_by_name["revisit_backtrack"].max_radius == pytest.approx(0.25)
    assert component_by_name["target_point_anchor"].view_mode is ViewDirectionMode.TARGET_POINT


def test_upper_bound_free_shell_ablation_is_explicit() -> None:
    cfg = CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=5)

    result = _run_generate(cfg)

    assert result.component_name == ("upper_bound_free_shell",) * 5
    assert result.position_id is not None
    assert result.position_id.tolist() == [candidate_position_id(CandidatePositionMode.UPPER_BOUND_FREE_SHELL)] * 5


def _descriptor(center: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> TargetDescriptor:
    return TargetDescriptor(
        sem_id=1,
        class_name="chair",
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *center),
        extents_m=(0.5, 0.5, 0.5),
        relative_pose_reference_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *center),
    )
