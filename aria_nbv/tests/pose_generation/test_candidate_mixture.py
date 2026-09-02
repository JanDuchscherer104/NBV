"""Tests for mixed finite-candidate generation."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytest.importorskip("efm3d")

import torch
import trimesh
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGenerator,
    CandidateMixtureViewGeneratorConfig,
    CandidatePositionMode,
    CandidateViewGenerator,
    CandidateViewGeneratorConfig,
    SamplingStrategy,
    ViewDirectionMode,
    candidate_position_id,
    candidate_strategy_id,
)
from aria_nbv.pose_generation.config import (
    BoxViewJitterConfig,
    CandidateGazeConfig,
    PowerSphericalConfig,
    SampledCenterConfig,
    TargetOrbitCenterConfig,
    UniformSphereConfig,
    sphere_distribution_from_legacy,
)
from aria_nbv.targets import TargetDescriptor
from aria_nbv.utils.fingerprints import stable_config_hash
from aria_nbv.utils.frames import world_up_tensor
from aria_nbv.utils.seeding import derive_stable_seed


def test_stable_seed_rejects_unsupported_and_nonfinite_parts() -> None:
    assert derive_stable_seed("component", 3, (True, None, 1.5)) == derive_stable_seed(
        "component", 3, (True, None, 1.5)
    )
    with pytest.raises(TypeError):
        derive_stable_seed(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        derive_stable_seed(float("nan"))


def test_stable_seed_preserves_legacy_bytes_encoding() -> None:
    assert derive_stable_seed(b"legacy-seed") == 160719835


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


def _component(
    *,
    name: str,
    count: int,
    strategy: ViewDirectionMode | None = None,
    view_mode: ViewDirectionMode | None = None,
    paired_view_mode: ViewDirectionMode | None = None,
    position_mode: CandidatePositionMode = CandidatePositionMode.UPPER_BOUND_FREE_SHELL,
    sampling_strategy: SamplingStrategy = SamplingStrategy.UNIFORM_SPHERE,
    view_sampling_strategy: SamplingStrategy | None = None,
    min_radius: float = 0.8,
    max_radius: float = 0.8,
    min_elev_deg: float = -20.0,
    max_elev_deg: float = 25.0,
    delta_azimuth_deg: float = 170.0,
    kappa: float = 4.0,
    view_kappa: float = 4.0,
    view_max_angle_deg: float = 0.0,
    view_max_azimuth_deg: float | None = 60.0,
    view_max_elevation_deg: float | None = 30.0,
    view_roll_jitter_deg: float = 0.0,
    target_orbit_angles_deg: tuple[float, ...] = (-6.0, 6.0, -10.0, 10.0, -14.0, 14.0),
) -> CandidateMixtureComponentConfig:
    resolved_view_mode = view_mode or strategy
    assert resolved_view_mode is not None
    if position_mode is CandidatePositionMode.TARGET_ORBIT:
        center = TargetOrbitCenterConfig(angles_deg=target_orbit_angles_deg)
    else:
        center = SampledCenterConfig(
            mode=position_mode,
            distribution=sphere_distribution_from_legacy(sampling_strategy, kappa),
            min_radius_m=min_radius,
            max_radius_m=max_radius,
            min_elevation_deg=min_elev_deg,
            max_elevation_deg=max_elev_deg,
            azimuth_width_deg=delta_azimuth_deg,
        )

    azimuth = view_max_angle_deg if view_max_azimuth_deg is None else view_max_azimuth_deg
    elevation = view_max_angle_deg if view_max_elevation_deg is None else view_max_elevation_deg
    gazes = [
        CandidateGazeConfig.from_legacy(
            mode=resolved_view_mode,
            sampling_strategy=view_sampling_strategy,
            concentration=view_kappa,
            yaw_half_width_deg=azimuth,
            pitch_half_width_deg=elevation,
            roll_half_width_deg=view_roll_jitter_deg,
        )
    ]
    if paired_view_mode is not None:
        gazes.append(
            CandidateGazeConfig(
                name=f"paired_{paired_view_mode.value}",
                mode=paired_view_mode,
                jitter=gazes[0].jitter,
            )
        )
    return CandidateMixtureComponentConfig(name=name, count=count, center=center, gazes=tuple(gazes))


def _run_generate(
    cfg: CandidateMixtureViewGeneratorConfig,
    *,
    generator: CandidateMixtureViewGenerator | None = None,
    seed: int | None = None,
    descriptor: TargetDescriptor | None = None,
    reference_pose: PoseTW | None = None,
):
    mesh, verts, faces = _mesh_triplet(cfg.device)
    return (generator or CandidateMixtureViewGenerator(cfg)).generate(
        reference_pose=reference_pose or _identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
        runtime_context=CandidateGenerationRuntimeContext(descriptor=descriptor or _descriptor()),
        seed=seed,
    )


def test_mixed_sampler_fixed_counts_and_full_shell_provenance() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[
            _component(name="target", count=4, strategy=ViewDirectionMode.TARGET_POINT),
            _component(name="away", count=2, strategy=ViewDirectionMode.RADIAL_AWAY),
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
    assert result.extras["target_view_evaluated_mask"].all()
    assert result.extras["target_view_angle_deg"].shape == (6,)
    assert result.extras["target_pixel_margin_px"].shape == (6,)
    assert result.extras["target_in_fov_mask"].dtype == torch.bool


def test_target_point_family_projects_actor_visible_target_inside_camera() -> None:
    """Exact CameraTW projection distinguishes target framing from line of sight."""

    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(
            update={
                "view_max_azimuth_deg": 1.0,
                "view_max_elevation_deg": 1.0,
            }
        ),
        components=[
            _component(
                name="target",
                count=6,
                view_mode=ViewDirectionMode.TARGET_POINT,
                position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
                view_max_azimuth_deg=1.0,
                view_max_elevation_deg=1.0,
            )
        ],
    )

    result = _run_generate(cfg, seed=3)

    assert result.extras["target_view_evaluated_mask"].all()
    assert result.extras["target_in_fov_mask"].all()
    assert torch.all(result.extras["target_pixel_margin_px"] > 0.0)
    assert torch.all(result.extras["target_view_angle_deg"] < 2.0)


def test_paired_variants_keep_original_component_id() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[
            _component(
                name="pair",
                count=2,
                view_mode=ViewDirectionMode.TARGET_POINT,
                paired_view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
            ),
            _component(name="after", count=2, view_mode=ViewDirectionMode.FORWARD_RIG),
        ],
    )

    result = _run_generate(cfg)

    assert result.mixture_id is not None
    assert result.mixture_id.tolist() == [0, 0, 0, 0, 1, 1]
    assert result.position_pair_id is not None
    assert result.gaze_variant_id is not None
    assert result.position_pair_id.tolist() == [0, 1, 0, 1, -1, -1]
    assert result.gaze_variant_id.tolist() == [0, 0, 1, 1, -1, -1]


def test_mixture_prepares_mesh_query_once_for_all_components(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.pose_generation.candidate_mixture as mixture_module

    prepared: list[object] = []

    class FakePreparedMeshQuery:
        is_persistently_reusable = True

        def __init__(self, *_args, **_kwargs) -> None:
            prepared.append(self)

        @classmethod
        def acquire(cls, current, *args, **kwargs):
            return current if current is not None else cls(*args, **kwargs)

        def matches(self, *_args, **_kwargs) -> bool:
            return True

        def matches_request(self, *_args, **_kwargs) -> bool:
            return True

        def point_distance(self, points: torch.Tensor) -> torch.Tensor:
            return torch.ones(points.shape[0], device=points.device, dtype=points.dtype)

    monkeypatch.setattr(mixture_module, "PreparedMeshQuery", FakePreparedMeshQuery)
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(update={"min_distance_to_mesh": 0.1}),
        components=[
            _component(name="forward", count=2, strategy=ViewDirectionMode.FORWARD_RIG),
            _component(name="away", count=2, strategy=ViewDirectionMode.RADIAL_AWAY),
        ],
    )

    generator = CandidateMixtureViewGenerator(cfg)
    result = _run_generate(cfg, generator=generator)

    assert result.mask_valid.shape[0] == 4
    assert len(prepared) == 1
    assert all(
        child._mesh_query is None and child._request_mesh_query is None
        for runtime in generator._component_runtimes
        for child in runtime.generators
    )


def test_single_generator_rejects_request_query_from_another_mesh() -> None:
    from aria_nbv.pose_generation.geometry import PreparedMeshQuery

    cfg = _base_cfg().model_copy(update={"min_distance_to_mesh": 0.1, "num_samples": 1})
    target_mesh, target_verts, target_faces = _mesh_triplet(cfg.device)
    other_mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    other_mesh.apply_translation((10.0, 0.0, 0.0))
    other_verts = torch.from_numpy(other_mesh.vertices).to(dtype=torch.float32, device=cfg.device)
    other_faces = torch.from_numpy(other_mesh.faces).to(dtype=torch.int64, device=cfg.device)
    query = PreparedMeshQuery(
        other_verts,
        other_faces,
        device=cfg.device,
        dtype=torch.float32,
        mesh=other_mesh,
    )
    generator = CandidateViewGenerator(cfg, mesh_query=query)

    with pytest.raises(ValueError, match="does not match the supplied mesh contract"):
        generator.generate(
            reference_pose=_identity_pose(device=cfg.device),
            gt_mesh=target_mesh,
            mesh_verts=target_verts,
            mesh_faces=target_faces,
            camera_calib_template=_dummy_camera(cfg.device),
            occupancy_extent=torch.tensor(
                [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
                dtype=torch.float32,
                device=cfg.device,
            ),
        )


def test_single_generator_discards_unused_injected_query() -> None:
    from aria_nbv.pose_generation.geometry import PreparedMeshQuery

    cfg = _base_cfg().model_copy(update={"num_samples": 1})
    mesh, verts, faces = _mesh_triplet(cfg.device)
    leaf = verts.detach().clone().requires_grad_()
    query = PreparedMeshQuery(leaf * 1.0, faces, device=cfg.device, dtype=torch.float32, mesh=mesh)
    generator = CandidateViewGenerator(cfg, mesh_query=query)

    generator.generate(
        reference_pose=_identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor(
            [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
            dtype=torch.float32,
            device=cfg.device,
        ),
    )

    assert generator._request_mesh_query is None
    assert generator._mesh_query is None


def test_mixture_skips_mesh_preparation_when_collision_clearance_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aria_nbv.pose_generation.candidate_mixture as mixture_module

    class UnexpectedPreparedMeshQuery:
        @classmethod
        def acquire(cls, *_args, **_kwargs):
            raise AssertionError("disabled collision clearance must not prepare mesh state")

    monkeypatch.setattr(mixture_module, "PreparedMeshQuery", UnexpectedPreparedMeshQuery)
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(
            update={
                "ensure_collision_free": True,
                "step_clearance": 0.0,
                "collect_debug_stats": True,
            }
        ),
        components=[
            _component(name="forward", count=2, strategy=ViewDirectionMode.FORWARD_RIG),
            _component(name="away", count=2, strategy=ViewDirectionMode.RADIAL_AWAY),
        ],
    )

    result = _run_generate(cfg)

    assert result.mask_valid.shape[0] == 4


def test_mixture_reuses_inference_mesh_within_each_request_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aria_nbv.pose_generation.geometry import PreparedMeshQuery

    prepared: list[PreparedMeshQuery] = []
    original_init = PreparedMeshQuery.__init__

    def counting_init(self: PreparedMeshQuery, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        prepared.append(self)

    monkeypatch.setattr(PreparedMeshQuery, "__init__", counting_init)
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(update={"min_distance_to_mesh": 0.1}),
        components=[
            _component(
                name="forward",
                count=2,
                view_mode=ViewDirectionMode.RADIAL_AWAY,
                paired_view_mode=ViewDirectionMode.FORWARD_RIG,
            ),
            _component(name="away", count=2, strategy=ViewDirectionMode.RADIAL_AWAY),
        ],
    )
    generator = CandidateMixtureViewGenerator(cfg)

    with torch.inference_mode():
        mesh, verts, faces = _mesh_triplet(cfg.device)
        kwargs = {
            "reference_pose": _identity_pose(device=cfg.device),
            "gt_mesh": mesh,
            "mesh_verts": verts,
            "mesh_faces": faces,
            "camera_calib_template": _dummy_camera(cfg.device),
            "occupancy_extent": torch.tensor(
                [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
                dtype=torch.float32,
            ),
            "runtime_context": CandidateGenerationRuntimeContext(descriptor=_descriptor()),
        }
        first_result = generator.generate(**kwargs)
        first_query = generator._mesh_query
        assert len(prepared) == 1
        second_result = generator.generate(**kwargs)

    assert first_result.mask_valid.shape[0] == second_result.mask_valid.shape[0] == 6
    assert len(prepared) == 2
    assert first_query is None
    assert generator._mesh_query is None


def test_mixture_normalizes_mesh_once_across_components(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(update={"min_distance_to_mesh": 0.1}),
        components=[
            _component(
                name="paired",
                count=2,
                view_mode=ViewDirectionMode.RADIAL_AWAY,
                paired_view_mode=ViewDirectionMode.FORWARD_RIG,
            ),
            _component(name="ordinary", count=2, strategy=ViewDirectionMode.RADIAL_AWAY),
        ],
    )
    mesh, verts, faces = _mesh_triplet(cfg.device)
    transfer_calls = {"verts": 0, "faces": 0}
    original_to = torch.Tensor.to

    def counting_to(self: torch.Tensor, *args: object, **kwargs: object) -> torch.Tensor:
        if self is verts:
            transfer_calls["verts"] += 1
        elif self is faces:
            transfer_calls["faces"] += 1
        return original_to(self, *args, **kwargs)

    monkeypatch.setattr(torch.Tensor, "to", counting_to)
    result = CandidateMixtureViewGenerator(cfg).generate(
        reference_pose=_identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor(
            [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
            dtype=torch.float32,
            device=cfg.device,
        ),
        runtime_context=CandidateGenerationRuntimeContext(descriptor=_descriptor()),
    )

    assert result.mask_valid.shape[0] == 6
    assert transfer_calls == {"verts": 1, "faces": 1}


def test_single_generator_does_not_retain_inference_query() -> None:
    cfg = _base_cfg().model_copy(update={"min_distance_to_mesh": 0.1, "num_samples": 1})
    generator = CandidateViewGenerator(cfg)

    with torch.inference_mode():
        mesh, verts, faces = _mesh_triplet(cfg.device)
        generator.generate(
            reference_pose=_identity_pose(device=cfg.device),
            gt_mesh=mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            camera_calib_template=_dummy_camera(cfg.device),
            occupancy_extent=torch.tensor(
                [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
                dtype=torch.float32,
                device=cfg.device,
            ),
        )

    assert generator._mesh_query is None


def test_single_generator_rebuilds_p3d_cache_after_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_triangles: list[torch.Tensor] = []

    def fake_point_face_distance(
        points: torch.Tensor,
        _points_first_idx: torch.Tensor,
        triangles: torch.Tensor,
        _triangles_first_idx: torch.Tensor,
        _max_points: int,
        _min_triangle_area: float,
    ) -> torch.Tensor:
        observed_triangles.append(triangles)
        return torch.ones(points.shape[0], dtype=points.dtype, device=points.device)

    monkeypatch.setattr(
        "pytorch3d.loss.point_mesh_distance.point_face_distance",
        fake_point_face_distance,
    )
    cfg = _base_cfg().model_copy(update={"min_distance_to_mesh": 0.1, "num_samples": 1})
    generator = CandidateViewGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.device)
    kwargs = {
        "reference_pose": _identity_pose(device=cfg.device),
        "gt_mesh": mesh,
        "mesh_verts": verts,
        "mesh_faces": faces,
        "camera_calib_template": _dummy_camera(cfg.device),
        "occupancy_extent": torch.tensor(
            [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
            dtype=torch.float32,
            device=cfg.device,
        ),
    }

    with torch.inference_mode():
        generator.generate(**kwargs)
    retained_query = generator._mesh_query
    generator.generate(**kwargs)

    assert retained_query is not None
    assert generator._mesh_query is retained_query
    assert len(observed_triangles) == 2
    assert observed_triangles[0].is_inference()
    assert not observed_triangles[1].is_inference()


def test_single_generator_does_not_retain_autograd_mesh_source() -> None:
    cfg = _base_cfg().model_copy(update={"min_distance_to_mesh": 0.1, "num_samples": 1})
    generator = CandidateViewGenerator(cfg)
    mesh, verts, faces = _mesh_triplet(cfg.device)
    leaf = verts.detach().clone().requires_grad_()
    mesh_verts = leaf * 1.0

    generator.generate(
        reference_pose=_identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=mesh_verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor(
            [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
            dtype=torch.float32,
            device=cfg.device,
        ),
    )

    assert mesh_verts.grad_fn is not None
    assert generator._mesh_query is None


def test_paired_seed_is_derived_from_resolved_component_seed_for_direct_and_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aria_nbv.rollouts.replay.policy import derive_component_seed

    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[
            _component(
                name="pair",
                count=2,
                view_mode=ViewDirectionMode.TARGET_POINT,
                paired_view_mode=ViewDirectionMode.FORWARD_RIG,
                position_mode=CandidatePositionMode.TARGET_BEARING_LOCAL,
            )
        ],
    )
    observed: list[int | None] = []
    original_generate = CandidateViewGenerator._generate_impl
    original_generate_from_centers = CandidateViewGenerator._generate_from_centers_impl

    def record_generate(self, *args, **kwargs):
        observed.append(kwargs["seed"])
        return original_generate(self, *args, **kwargs)

    def record_generate_from_centers(self, *args, **kwargs):
        observed.append(kwargs["seed"])
        return original_generate_from_centers(self, *args, **kwargs)

    monkeypatch.setattr(CandidateViewGenerator, "_generate_impl", record_generate)
    monkeypatch.setattr(CandidateViewGenerator, "_generate_from_centers_impl", record_generate_from_centers)

    _run_generate(cfg)
    direct_primary, direct_paired = observed
    assert direct_primary == cfg.base.seed
    assert direct_paired == derive_component_seed(direct_primary, "pair__paired_forward_rig")

    observed.clear()
    _run_generate(cfg, seed=41)
    replay_primary, replay_paired = observed
    assert replay_primary == derive_component_seed(41, "pair")
    assert replay_paired == derive_component_seed(replay_primary, "pair__paired_forward_rig")


def test_mixture_generate_reuses_prebuilt_component_generators(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[_component(name="forward", count=2, strategy=ViewDirectionMode.FORWARD_RIG)],
    )
    generator = CandidateMixtureViewGenerator(cfg)
    runtime_ids = tuple(id(child) for runtime in generator._component_runtimes for child in runtime.generators)

    monkeypatch.setattr(
        CandidateViewGenerator,
        "_from_component",
        classmethod(lambda cls, *args, **kwargs: pytest.fail("generate must not construct child generators")),
    )
    _run_generate(cfg, generator=generator)
    _run_generate(cfg, generator=generator)

    assert tuple(id(child) for runtime in generator._component_runtimes for child in runtime.generators) == runtime_ids


def test_single_family_runtime_context_does_not_override_config_target(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_position_target = torch.tensor([0.0, 0.0, 3.0])
    configured_gaze_target = torch.tensor([2.0, 0.0, 0.0])
    cfg = _base_cfg().model_copy(
        update={
            "num_samples": 1,
            "oversample_factor": 1.0,
            "position_mode": CandidatePositionMode.TARGET_BEARING_LOCAL,
            "position_target_point_world": configured_position_target,
            "view_direction_mode": ViewDirectionMode.TARGET_POINT,
            "view_target_point_world": configured_gaze_target,
            "view_max_azimuth_deg": 0.0,
            "view_max_elevation_deg": 0.0,
        }
    )
    generator = CandidateViewGenerator(cfg)
    observed_positions: list[torch.Tensor | None] = []
    observed_gazes: list[torch.Tensor | None] = []
    original_sample = generator._position_sampler.sample
    original_build = generator._orientation_builder.build

    def record_sample(*args, **kwargs):
        observed_positions.append(kwargs["target_center_world"])
        return original_sample(*args, **kwargs)

    def record_build(*args, **kwargs):
        observed_gazes.append(kwargs["target_center_world"])
        return original_build(*args, **kwargs)

    monkeypatch.setattr(generator._position_sampler, "sample", record_sample)
    monkeypatch.setattr(generator._orientation_builder, "build", record_build)
    mesh, verts, faces = _mesh_triplet(cfg.device)
    generator.generate(
        reference_pose=_identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
        runtime_context=CandidateGenerationRuntimeContext(descriptor=_descriptor((3.0, 0.0, 0.0))),
    )

    assert len(observed_positions) == len(observed_gazes) == 1
    assert torch.equal(observed_positions[0], configured_position_target)
    assert torch.equal(observed_gazes[0], configured_gaze_target)


def test_single_family_view_only_target_does_not_enable_position_diagnostics() -> None:
    cfg = _base_cfg().model_copy(
        update={
            "num_samples": 1,
            "oversample_factor": 1.0,
            "position_target_point_world": None,
            "view_direction_mode": ViewDirectionMode.TARGET_POINT,
            "view_target_point_world": torch.tensor([2.0, 0.0, 0.0]),
            "view_max_azimuth_deg": 0.0,
            "view_max_elevation_deg": 0.0,
        }
    )

    mesh, verts, faces = _mesh_triplet(cfg.device)
    result = CandidateViewGenerator(cfg).generate(
        reference_pose=_identity_pose(device=cfg.device),
        gt_mesh=mesh,
        mesh_verts=verts,
        mesh_faces=faces,
        camera_calib_template=_dummy_camera(cfg.device),
        occupancy_extent=torch.tensor([-10.0, 10.0, -10.0, 10.0, -10.0, 10.0], dtype=torch.float32),
    )

    assert "target_bearing_yaw_rad" not in result.extras
    assert "target_distance_m" not in result.extras
    assert "target_in_fov_mask" not in result.extras


def test_mixture_targets_are_request_local_and_not_retained(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[_component(name="target", count=2, strategy=ViewDirectionMode.TARGET_POINT)],
    )
    generator = CandidateMixtureViewGenerator(cfg)
    child = generator._component_runtimes[0].generators[0]
    observed: list[torch.Tensor | None] = []
    original_build = child._orientation_builder.build

    def record_build(*args, **kwargs):
        observed.append(kwargs["target_center_world"])
        return original_build(*args, **kwargs)

    monkeypatch.setattr(child._orientation_builder, "build", record_build)
    _run_generate(cfg, generator=generator, descriptor=_descriptor((1.0, 0.0, 0.0)))
    _run_generate(cfg, generator=generator, descriptor=_descriptor((0.0, 2.0, 0.0)))

    assert observed[0] is not None and torch.equal(observed[0], torch.tensor([1.0, 0.0, 0.0]))
    assert observed[1] is not None and torch.equal(observed[1], torch.tensor([0.0, 2.0, 0.0]))
    assert child.config.position_target_point_world is None
    assert child.config.view_target_point_world is None


@pytest.mark.parametrize("node_seed, identity", [(0, "forward"), (41, "pair__paired_forward_rig")])
def test_private_component_seed_matches_public_rollout_wrapper(node_seed: int, identity: str) -> None:
    from aria_nbv.pose_generation.candidate_mixture import _derive_component_seed
    from aria_nbv.rollouts.replay.policy import derive_component_seed

    assert _derive_component_seed(node_seed, identity) == derive_component_seed(node_seed, identity)


def test_target_point_component_requires_runtime_target_context() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg(),
        components=[_component(name="target", count=2, strategy=ViewDirectionMode.TARGET_POINT)],
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
        components=[_component(name="target", count=4, strategy=ViewDirectionMode.TARGET_POINT)],
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


def test_default_mixture_resolves_exact_nested_authoring_contract() -> None:
    cfg = CandidateMixtureViewGeneratorConfig()

    assert cfg.base.sampling_strategy is SamplingStrategy.FORWARD_POWERSPHERICAL
    assert (cfg.base.min_radius, cfg.base.max_radius) == pytest.approx((0.25, 1.25))
    assert (cfg.base.min_elev_deg, cfg.base.max_elev_deg, cfg.base.delta_azimuth_deg) == pytest.approx(
        (-12.0, 18.0, 120.0)
    )
    assert cfg.base.kappa == pytest.approx(8.0)
    assert [(component.name, component.count) for component in cfg.components] == [
        ("forward_local", 24),
        ("target_bearing_local", 24),
        ("lateral_target_bypass", 12),
    ]
    assert [component.center.mode for component in cfg.components] == [
        CandidatePositionMode.FORWARD_LOCAL,
        CandidatePositionMode.TARGET_BEARING_LOCAL,
        CandidatePositionMode.LATERAL_TARGET_BYPASS,
    ]
    assert [component.gazes[0].mode for component in cfg.components] == [
        ViewDirectionMode.FORWARD_RIG,
        ViewDirectionMode.TARGET_POINT,
        ViewDirectionMode.TARGET_POINT,
    ]
    for component in cfg.components:
        assert isinstance(component.center, SampledCenterConfig)
        assert component.center.min_radius_m == pytest.approx(0.25)
        assert component.center.max_radius_m == pytest.approx(1.25)
        assert isinstance(component.gazes[0].jitter, BoxViewJitterConfig)
        assert component.gazes[0].jitter.yaw_half_width_deg == pytest.approx(60.0)
        assert component.gazes[0].jitter.pitch_half_width_deg == pytest.approx(30.0)


@pytest.mark.parametrize(
    "preset",
    (
        CandidateMixtureViewGeneratorConfig,
        CandidateMixtureViewGeneratorConfig.upper_bound_free_shell,
        CandidateMixtureViewGeneratorConfig.rich_local_five_family,
        CandidateMixtureViewGeneratorConfig.paired_center_gaze_family,
        CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family,
    ),
)
def test_code_owned_mixture_presets_use_nested_distribution_authoring(preset) -> None:
    """Current presets must not route through retired flat distribution keys."""

    config = preset()
    for component in config.components:
        center = component.center.model_dump()
        assert "sampling_strategy" not in center
        assert "concentration" not in center


def _portable_tensor_fingerprint_bytes(value: torch.Tensor) -> bytes:
    """Return exact discrete bytes and 1e-3-quantized floating-point bytes."""

    canonical = value.detach().cpu().contiguous()
    if canonical.is_floating_point():
        canonical = torch.round(canonical.to(torch.float64) * 1_000.0).to(torch.int64)
    return canonical.numpy().tobytes()


@pytest.mark.parametrize(
    ("config_name", "expected_fingerprint"),
    (
        ("build_rollouts_qh_v0_baseline.toml", "657d3762eb39bf91fa69710f0eb3972beb1f992cdc6a84eb78cd16b71c453f3d"),
        (
            "build_rollouts_v2_cuda_campaign_writer.toml",
            "4135d79d895ecffcb319ebef51a3ccddee6409b9191177b95d441325afc0e920",
        ),
        ("build_rollouts_v1_diverse.toml", "5f882b8988b3c29eca53cb84474aa460462e7834c7510dc5bbc42d5db63c7674"),
        (
            "build_rollouts_v1_lrz.template.toml",
            "4135d79d895ecffcb319ebef51a3ccddee6409b9191177b95d441325afc0e920",
        ),
        ("build_rollouts_v1_microset.toml", "34af9d8a090aa83082e055537e5653639bf785d067ba185e04808110e104652f"),
        (
            "build_rollouts_v1_multihorizon_highgain.toml",
            "4135d79d895ecffcb319ebef51a3ccddee6409b9191177b95d441325afc0e920",
        ),
        ("build_rollouts_v2_realistic.toml", "4135d79d895ecffcb319ebef51a3ccddee6409b9191177b95d441325afc0e920"),
        ("build_rollouts_v1_smoke.toml", "61b04effff3d1c9495939615667821cf8a7f3f7b3e4d2328c1f3165ee44b1889"),
    ),
)
def test_migrated_active_profiles_match_origin_main_candidate_fingerprints(
    config_name: str,
    expected_fingerprint: str,
) -> None:
    config_path = Path(__file__).resolve().parents[3] / ".configs" / config_name
    mixture = RolloutDatasetWriterConfig.from_toml(config_path).candidate_mixture
    base = mixture.base.model_copy(update={"device": torch.device("cpu")})
    result = _run_generate(mixture.model_copy(update={"base": base}), seed=123)

    digest = hashlib.sha256()
    for value in (
        result.shell_poses.tensor(),
        result.views.tensor(),
        result.mask_valid,
        result.strategy_id,
        result.position_id,
        result.mixture_id,
        result.sampler_probability,
        result.position_pair_id,
        result.gaze_variant_id,
    ):
        if value is not None:
            digest.update(_portable_tensor_fingerprint_bytes(value))
    for name in sorted(result.masks):
        digest.update(name.encode())
        digest.update(_portable_tensor_fingerprint_bytes(result.masks[name]))
    for name in (
        "view_jitter_yaw_deg",
        "view_jitter_pitch_deg",
        "view_jitter_is_bounded",
        "view_jitter_azimuth_limit_deg",
        "view_jitter_elevation_limit_deg",
    ):
        value = result.extras.get(name)
        if torch.is_tensor(value):
            digest.update(_portable_tensor_fingerprint_bytes(value))
    digest.update("\n".join(result.component_name or ()).encode())

    assert digest.hexdigest() == expected_fingerprint


def test_component_validation_and_three_gaze_expansion() -> None:
    center = _component(name="template", count=6, view_mode=ViewDirectionMode.FORWARD_RIG).center
    gazes = (
        CandidateGazeConfig(name="primary", mode=ViewDirectionMode.FORWARD_RIG, jitter=BoxViewJitterConfig()),
        CandidateGazeConfig(name="target", mode=ViewDirectionMode.TARGET_POINT, jitter=BoxViewJitterConfig()),
        CandidateGazeConfig(name="away", mode=ViewDirectionMode.RADIAL_AWAY, jitter=BoxViewJitterConfig()),
    )
    component = CandidateMixtureComponentConfig(name="triple", count=6, center=center, gazes=gazes)
    cfg = CandidateMixtureViewGeneratorConfig(base=_base_cfg(), components=(component,))

    assert cfg.total_count == 18
    result = _run_generate(cfg)
    assert result.mask_valid.numel() == 18
    assert torch.equal(result.sampler_probability, torch.full_like(result.sampler_probability, 1.0 / 18.0))
    assert result.component_name == ("triple",) * 6 + ("triple__target",) * 6 + ("triple__away",) * 6
    assert result.position_pair_id.tolist() == list(range(6)) * 3
    assert result.gaze_variant_id.tolist() == [0] * 6 + [1] * 6 + [2] * 6

    with pytest.raises(ValueError, match="gaze names must be unique"):
        CandidateMixtureComponentConfig(name="duplicate", count=1, center=center, gazes=(gazes[0], gazes[0]))
    with pytest.raises(ValueError, match="component names must be unique"):
        CandidateMixtureViewGeneratorConfig(components=(component, component))
    colliding = CandidateMixtureComponentConfig(name="triple__target", count=1, center=center, gazes=(gazes[0],))
    with pytest.raises(ValueError, match="provenance names must be globally unique"):
        CandidateMixtureViewGeneratorConfig(components=(component, colliding))


def test_nested_config_defaults_and_identity_propagation_are_owned_once() -> None:
    center = SampledCenterConfig(mode=CandidatePositionMode.FORWARD_LOCAL)
    gaze = CandidateGazeConfig(mode=ViewDirectionMode.FORWARD_RIG)
    component = CandidateMixtureComponentConfig(name="component", count=2, center=center, gazes=(gaze,))

    assert center.model_dump() == {
        "kind": "sampled",
        "mode": CandidatePositionMode.FORWARD_LOCAL,
        "distribution": {
            "kind": SamplingStrategy.FORWARD_POWERSPHERICAL,
            "concentration": 8.0,
        },
        "min_radius_m": 0.25,
        "max_radius_m": 1.25,
        "min_elevation_deg": -12.0,
        "max_elevation_deg": 18.0,
        "azimuth_width_deg": 120.0,
    }
    assert gaze.name == "primary"
    assert isinstance(gaze.jitter, BoxViewJitterConfig)
    assert component.gazes[0].name == "primary"
    assert "name" not in component.gazes[0].propagated_fields


def test_sampled_center_legacy_projection_preserves_controls_and_revalidates_overrides() -> None:
    base = CandidateViewGeneratorConfig(
        sampling_strategy=SamplingStrategy.FORWARD_POWERSPHERICAL,
        kappa=13.0,
        min_radius=0.4,
        max_radius=1.6,
        min_elev_deg=-9.0,
        max_elev_deg=17.0,
        delta_azimuth_deg=155.0,
    )

    center = SampledCenterConfig.from_legacy(
        base,
        mode=CandidatePositionMode.LOCAL_REFINEMENT,
        min_radius_m=0.2,
        max_radius_m=0.7,
    )

    assert center == SampledCenterConfig(
        mode=CandidatePositionMode.LOCAL_REFINEMENT,
        distribution=PowerSphericalConfig(concentration=13.0),
        min_radius_m=0.2,
        max_radius_m=0.7,
        min_elevation_deg=-9.0,
        max_elevation_deg=17.0,
        azimuth_width_deg=155.0,
    )
    with pytest.raises(ValueError, match="min_radius_m must not exceed max_radius_m"):
        SampledCenterConfig.from_legacy(
            base,
            mode=CandidatePositionMode.FORWARD_LOCAL,
            min_radius_m=2.0,
            max_radius_m=1.0,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("min_radius_m", float("nan")),
        ("max_radius_m", float("inf")),
        ("azimuth_width_deg", float("inf")),
    ],
)
def test_sampled_center_rejects_non_finite_support(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        SampledCenterConfig(mode=CandidatePositionMode.FORWARD_LOCAL, **{field: value})


def test_sphere_distribution_is_discriminated_and_has_no_inert_uniform_concentration() -> None:
    uniform = SampledCenterConfig.model_validate({"mode": "forward_local", "distribution": {"kind": "uniform_sphere"}})
    powered = SampledCenterConfig.model_validate(
        {
            "mode": "forward_local",
            "distribution": {"kind": "forward_powerspherical", "concentration": 12.0},
        }
    )

    assert isinstance(uniform.distribution, UniformSphereConfig)
    assert uniform.distribution.model_dump() == {"kind": SamplingStrategy.UNIFORM_SPHERE}
    assert isinstance(powered.distribution, PowerSphericalConfig)
    assert powered.distribution.concentration == pytest.approx(12.0)
    assert stable_config_hash(SampledCenterConfig.model_validate(powered.model_dump())) == stable_config_hash(powered)
    with pytest.raises(ValueError, match="concentration"):
        SampledCenterConfig.model_validate(
            {
                "mode": "forward_local",
                "distribution": {"kind": "uniform_sphere", "concentration": 12.0},
            }
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_power_spherical_distribution_rejects_non_finite_concentration(value: float) -> None:
    with pytest.raises(ValueError):
        PowerSphericalConfig(concentration=value)


def test_component_count_replacement_revalidates_scalar_and_orbit_invariants() -> None:
    component = _component(name="forward", count=2, view_mode=ViewDirectionMode.FORWARD_RIG)
    with pytest.raises(ValueError, match="greater than 0"):
        component.with_count(0)
    with pytest.raises(ValueError, match="greater than 0"):
        component.with_count(-1)

    orbit = CandidateMixtureComponentConfig(
        name="orbit",
        count=2,
        center=TargetOrbitCenterConfig(angles_deg=(-6.0, 6.0)),
        gazes=(CandidateGazeConfig(mode=ViewDirectionMode.TARGET_POINT),),
    )
    with pytest.raises(ValueError, match="at least two centers"):
        CandidateMixtureViewGeneratorConfig(components=(orbit.with_count(1),))


def test_component_config_import_paths_remain_stable() -> None:
    import aria_nbv.pose_generation as pose_generation
    from aria_nbv.pose_generation import CandidateMixtureComponentConfig as PackageConfig
    from aria_nbv.pose_generation.candidate_mixture import CandidateMixtureComponentConfig as ModuleConfig

    assert PackageConfig is CandidateMixtureComponentConfig
    assert ModuleConfig is CandidateMixtureComponentConfig
    assert pose_generation.__all__ == [
        "CandidateViewGenerator",
        "CandidateViewGeneratorConfig",
        "CandidateMixtureComponentConfig",
        "CandidateMixtureViewGenerator",
        "CandidateMixtureViewGeneratorConfig",
        "CandidateGenerationRuntimeContext",
        "CandidatePositionMode",
        "ViewDirectionMode",
        "candidate_position_id",
        "candidate_strategy_id",
        "CandidateSamplingResult",
        "SamplingStrategy",
        "CollisionBackend",
        "summarise_offsets_ref",
        "summarise_dirs_ref",
        "stats_to_markdown_table",
    ]


def test_mixed_generation_ignores_obsolete_base_fields_but_retains_alignment() -> None:
    baseline = CandidateMixtureViewGeneratorConfig(base=_base_cfg())
    changed_base = _base_cfg().model_copy(
        update={
            "num_samples": 1,
            "oversample_factor": 4.0,
            "max_resamples": 9,
            "position_mode": CandidatePositionMode.REVISIT_BACKTRACK,
            "sampling_strategy": SamplingStrategy.FORWARD_POWERSPHERICAL,
            "min_radius": 3.0,
            "max_radius": 4.0,
            "min_elev_deg": 40.0,
            "max_elev_deg": 50.0,
            "delta_azimuth_deg": 20.0,
            "kappa": 1.0,
            "position_target_point_world": torch.tensor([9.0, 8.0, 7.0]),
            "target_orbit_angles_deg": (-40.0, 40.0),
            "view_direction_mode": ViewDirectionMode.RADIAL_AWAY,
            "view_sampling_strategy": SamplingStrategy.UNIFORM_SPHERE,
            "view_kappa": 1.0,
            "view_max_angle_deg": 2.0,
            "view_max_azimuth_deg": 1.0,
            "view_max_elevation_deg": 1.0,
            "view_roll_jitter_deg": 20.0,
            "view_target_point_world": torch.tensor([7.0, 8.0, 9.0]),
        }
    )
    changed = CandidateMixtureViewGeneratorConfig(base=changed_base)

    expected = _run_generate(baseline, seed=17)
    actual = _run_generate(changed, seed=17)
    assert torch.equal(actual.shell_poses.tensor(), expected.shell_poses.tensor())
    assert torch.equal(actual.mask_valid, expected.mask_valid)
    assert torch.equal(actual.views.tensor(), expected.views.tensor())
    assert torch.equal(actual.strategy_id, expected.strategy_id)
    assert torch.equal(actual.position_id, expected.position_id)

    pitch = torch.deg2rad(torch.tensor(30.0))
    tilted = PoseTW.from_Rt(
        torch.tensor(
            [[1.0, 0.0, 0.0], [0.0, torch.cos(pitch), -torch.sin(pitch)], [0.0, torch.sin(pitch), torch.cos(pitch)]]
        ),
        torch.zeros(3),
    )
    aligned = _run_generate(baseline, seed=17, reference_pose=tilted)
    unaligned = _run_generate(
        CandidateMixtureViewGeneratorConfig(base=_base_cfg().model_copy(update={"align_to_gravity": False})),
        seed=17,
        reference_pose=tilted,
    )
    assert not torch.equal(aligned.sampling_pose.tensor(), unaligned.sampling_pose.tensor())


def test_mixture_rejects_zero_resolved_view_jitter() -> None:
    with pytest.raises(ValueError, match="use NoViewJitterConfig"):
        BoxViewJitterConfig(
            yaw_half_width_deg=0.0,
            pitch_half_width_deg=0.0,
            roll_half_width_deg=0.0,
        )

    assert BoxViewJitterConfig(yaw_half_width_deg=1.0, pitch_half_width_deg=0.0)
    assert BoxViewJitterConfig(yaw_half_width_deg=0.0, pitch_half_width_deg=1.0)
    assert BoxViewJitterConfig(yaw_half_width_deg=0.0, pitch_half_width_deg=0.0, roll_half_width_deg=1.0)


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
            _component(
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
    assert cfg.components[0].gazes[1].mode is ViewDirectionMode.FORWARD_RIG


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
    assert component_by_name["radial_towards_target_bearing"].gazes[0].mode is ViewDirectionMode.RADIAL_TOWARDS
    assert component_by_name["radial_towards_target_bearing"].center.mode is CandidatePositionMode.TARGET_BEARING_LOCAL
    assert component_by_name["radial_away_target_bearing"].gazes[0].mode is ViewDirectionMode.RADIAL_AWAY
    assert component_by_name["radial_away_target_bearing"].center.mode is CandidatePositionMode.TARGET_BEARING_LOCAL
    assert component_by_name["revisit_backtrack"].gazes[0].mode is ViewDirectionMode.FORWARD_RIG
    assert component_by_name["revisit_backtrack"].center.mode is CandidatePositionMode.REVISIT_BACKTRACK
    assert component_by_name["revisit_backtrack"].center.max_radius_m == pytest.approx(0.25)
    assert component_by_name["target_point_anchor"].gazes[0].mode is ViewDirectionMode.TARGET_POINT


def test_upper_bound_free_shell_ablation_is_explicit() -> None:
    cfg = CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=5)

    result = _run_generate(cfg)

    assert result.component_name == ("upper_bound_free_shell",) * 5
    assert result.position_id is not None
    assert result.position_id.tolist() == [candidate_position_id(CandidatePositionMode.UPPER_BOUND_FREE_SHELL)] * 5


@pytest.mark.parametrize("align_to_gravity", [True, False])
def test_target_orbit_attempts_both_sides_at_constant_world_horizontal_standoff(
    align_to_gravity: bool,
) -> None:
    target_world = torch.tensor([0.0, 3.0, 0.0])
    pitch_rad = torch.deg2rad(torch.tensor(25.0))
    rotation = torch.tensor(
        [
            [1.0, 0.0, 0.0],
            [0.0, torch.cos(pitch_rad), -torch.sin(pitch_rad)],
            [0.0, torch.sin(pitch_rad), torch.cos(pitch_rad)],
        ]
    )
    tilted_reference = PoseTW.from_Rt(rotation, torch.zeros(3))
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(
            update={
                "num_samples": 12,
                "align_to_gravity": align_to_gravity,
                "enforce_motion_realism": True,
                "max_backward_step_m": 10.0,
                "collect_debug_stats": True,
            }
        ),
        components=[
            _component(
                name="target_orbit",
                count=12,
                view_mode=ViewDirectionMode.TARGET_POINT,
                position_mode=CandidatePositionMode.TARGET_ORBIT,
            )
        ],
    )

    result = _run_generate(
        cfg,
        descriptor=_descriptor(tuple(target_world.tolist())),
        reference_pose=tilted_reference.to(cfg.device),
    )

    target_world_device = target_world.to(result.shell_poses.t.device)
    world_up = world_up_tensor(device=result.shell_poses.t.device, dtype=result.shell_poses.t.dtype)
    root_to_target = target_world_device - result.reference_pose.t.reshape(3)
    target_horizontal = root_to_target - (root_to_target @ world_up) * world_up
    bearing = target_horizontal / target_horizontal.norm()
    lateral = torch.cross(world_up, bearing, dim=0)
    target_to_candidate = result.shell_poses.t - target_world_device.reshape(1, 3)
    horizontal = target_to_candidate - (target_to_candidate @ world_up)[:, None] * world_up[None, :]
    horizontal_standoff = torch.linalg.norm(horizontal, dim=1)
    signed_lateral = target_to_candidate @ lateral

    assert torch.allclose(
        horizontal_standoff,
        torch.full_like(horizontal_standoff, target_horizontal.norm()),
        atol=1e-5,
    )
    assert int((signed_lateral < 0.0).sum()) == int((signed_lateral > 0.0).sum()) == 6
    assert result.position_id.tolist() == [candidate_position_id(CandidatePositionMode.TARGET_ORBIT)] * 12
    expected_offsets_ref = result.reference_pose.inverse().transform(result.shell_poses.t)
    assert torch.allclose(result.shell_offsets_ref, expected_offsets_ref, atol=1e-5)
    assert torch.allclose(
        result.extras["motion_backward_step_m"],
        (-expected_offsets_ref[:, 2]).clamp_min(0.0),
        atol=1e-5,
    )
    assert result.extras["view_jitter_is_bounded"].all()
    assert torch.any(result.extras["view_jitter_yaw_deg"].abs() > 1e-3)


def test_target_orbit_interleaves_reordered_angle_bank_for_small_component() -> None:
    cfg = CandidateMixtureViewGeneratorConfig(
        base=_base_cfg().model_copy(update={"target_orbit_angles_deg": (-6.0, -10.0, 6.0, 10.0)}),
        components=[
            _component(
                name="target_orbit",
                count=2,
                view_mode=ViewDirectionMode.TARGET_POINT,
                position_mode=CandidatePositionMode.TARGET_ORBIT,
                target_orbit_angles_deg=(-6.0, -10.0, 6.0, 10.0),
            )
        ],
    )

    result = _run_generate(cfg, descriptor=_descriptor((0.0, 3.0, 0.0)))

    world_up = world_up_tensor(device=result.shell_poses.t.device, dtype=result.shell_poses.t.dtype)
    target = torch.tensor([0.0, 3.0, 0.0], device=result.shell_poses.t.device)
    bearing = target / target.norm()
    lateral = torch.cross(world_up, bearing, dim=0)
    signed_lateral = (result.shell_poses.t - target.reshape(1, 3)) @ lateral
    assert int((signed_lateral < 0.0).sum()) == int((signed_lateral > 0.0).sum()) == 1


def test_target_orbit_mixture_requires_two_attempted_proposals() -> None:
    with pytest.raises(ValueError, match="at least two centers"):
        CandidateMixtureViewGeneratorConfig(
            base=_base_cfg(),
            components=[
                _component(
                    name="target_orbit",
                    count=1,
                    view_mode=ViewDirectionMode.TARGET_POINT,
                    position_mode=CandidatePositionMode.TARGET_ORBIT,
                )
            ],
        )


def test_target_orbit_single_family_requires_two_attempted_proposals() -> None:
    with pytest.raises(ValueError, match="num_samples >= 2"):
        CandidateViewGeneratorConfig(
            num_samples=1,
            position_mode=CandidatePositionMode.TARGET_ORBIT,
        )

    cfg = _base_cfg().model_copy(
        update={
            "num_samples": 1,
            "oversample_factor": 1.0,
            "position_mode": CandidatePositionMode.TARGET_ORBIT,
            "position_target_point_world": torch.tensor([0.0, 3.0, 0.0]),
        }
    )
    mesh, verts, faces = _mesh_triplet(cfg.device)
    with pytest.raises(ValueError, match="at least two attempted"):
        CandidateViewGenerator(cfg).generate(
            reference_pose=_identity_pose(cfg.device),
            gt_mesh=mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            camera_calib_template=_dummy_camera(cfg.device),
            occupancy_extent=torch.tensor(
                [-10.0, 10.0, -10.0, 10.0, -10.0, 10.0],
                dtype=torch.float32,
                device=cfg.device,
            ),
        )


@pytest.mark.parametrize(
    "angles",
    [(), (0.0, 10.0), (5.0, 10.0), (-5.0, -10.0), (-180.0, 5.0), (float("inf"), -5.0)],
)
def test_target_orbit_angle_bank_rejects_degenerate_support(angles: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="target_orbit_angles_deg"):
        CandidateViewGeneratorConfig(target_orbit_angles_deg=angles)


def _descriptor(center: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> TargetDescriptor:
    return TargetDescriptor(
        sem_id=1,
        class_name="chair",
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *center),
        extents_m=(0.5, 0.5, 0.5),
        relative_pose_reference_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *center),
    )


def test_mixture_runtime_snapshots_mutable_authoring_tree() -> None:
    config = CandidateMixtureViewGeneratorConfig()
    runtime = CandidateMixtureViewGenerator(config)
    original_name = runtime.config.components[0].name
    config.components[0].name = "mutated-after-setup"
    config.components[0].count = 1
    exposed_snapshot = runtime.config
    exposed_snapshot.components[0].name = "mutated-runtime-copy"
    exposed_snapshot.components[0].count = 2

    result = _run_generate(runtime.config, generator=runtime, seed=17)

    assert runtime.config.components[0].name == original_name
    assert runtime.config.components[0].count == 24
    assert result.component_name.count(original_name) == 24
    assert "mutated-after-setup" not in result.component_name
    assert "mutated-runtime-copy" not in result.component_name
