import sys
from pathlib import Path

import torch

# Make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[2] / "external" / "efm3d"))

import pytest  # isort: split

from efm3d.aria.obb import ObbTW

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGeneratorConfig,
    CandidateViewGeneratorConfig,
    ViewDirectionMode,
)
from aria_nbv.pose_generation.config import (
    BoxViewJitterConfig,
    CandidateGazeConfig,
    TargetShellCenterConfig,
    TargetShellSupportMode,
)
from aria_nbv.targets import TargetDescriptor
from aria_nbv.utils import Verbosity


def _skip_if_missing_data() -> None:
    paths = PathConfig()
    atek_dir = paths.resolve_atek_data_dir("efm")
    if not atek_dir.exists():
        pytest.skip(f"ATEK data dir missing: {atek_dir}", allow_module_level=True)
    if not any(atek_dir.glob("**/*.tar")):
        pytest.skip(f"No ATEK shards found under {atek_dir}", allow_module_level=True)
    mesh_dir = paths.ase_meshes
    if not any(mesh_dir.glob("scene_ply_*.ply")):
        pytest.skip(f"No ASE meshes found under {mesh_dir}", allow_module_level=True)


_skip_if_missing_data()


def _load_sample():
    cfg = AseEfmDatasetConfig(
        scene_ids=["81283"],
        batch_size=None,
        load_meshes=True,
        require_mesh=True,
        mesh_simplify_ratio=0.02,
        device="cpu",
        verbosity=Verbosity.QUIET,
        is_debug=False,
    )
    ds = cfg.setup_target()
    return next(iter(ds))


def test_candidate_generation_seed_is_deterministic_on_real_data():
    sample = _load_sample()

    cfg = CandidateViewGeneratorConfig(
        num_samples=64,
        oversample_factor=1.0,
        max_resamples=0,
        min_radius=0.6,
        max_radius=0.8,
        min_elev_deg=-15.0,
        max_elev_deg=15.0,
        delta_azimuth_deg=360.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        device="cpu",
        verbosity=Verbosity.QUIET,
        seed=123,
        is_debug=False,
    )

    gen = cfg.setup_target()
    out1 = gen.generate_from_typed_sample(sample)
    out2 = gen.generate_from_typed_sample(sample)

    assert out1.shell_offsets_ref is not None
    assert out2.shell_offsets_ref is not None
    assert torch.allclose(out1.shell_offsets_ref, out2.shell_offsets_ref)

    out3 = cfg.model_copy(update={"seed": 124}).setup_target().generate_from_typed_sample(sample)
    assert out3.shell_offsets_ref is not None
    assert not torch.allclose(out1.shell_offsets_ref, out3.shell_offsets_ref)


def _nearest_real_target(sample) -> tuple[TargetDescriptor, float]:
    assert sample.obbs is not None
    obbs = sample.obbs.obbs
    valid = ~obbs.get_padding_mask()
    flat = ObbTW(obbs.tensor().reshape(-1, 34)[valid.reshape(-1)])
    reference = sample.trajectory.final_pose
    distances = torch.linalg.norm(flat.T_world_object.t - reference.t.reshape(1, 3), dim=1)
    target = flat[int(torch.argmin(distances).item())]
    relative = reference.inverse() @ target.T_world_object
    descriptor = TargetDescriptor(
        sem_id=int(target.sem_id.reshape(-1)[0].item()),
        class_name="real-scene-obb",
        pose_world_object=tuple(float(value) for value in target.T_world_object.tensor().reshape(-1).tolist()),
        extents_m=tuple(float(value) for value in target.bb3_diagonal.reshape(-1).tolist()),
        relative_pose_reference_object=tuple(float(value) for value in relative.tensor().reshape(-1).tolist()),
    )
    return descriptor, float(distances.min().item())


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_target_shell_real_scene_repeatability_and_admission(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable")
    sample = _load_sample()
    descriptor, actor_distance = _nearest_real_target(sample)
    count = 512
    center = TargetShellCenterConfig(
        radius_min_m=max(0.2, actor_distance - 0.5),
        radius_max_m=actor_distance + 0.5,
        support_mode=TargetShellSupportMode.ACTOR_FACING_CAP,
        cap_half_angle_deg=25.0,
    )
    base = CandidateViewGeneratorConfig(
        num_samples=count,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        enforce_motion_realism=True,
        max_step_distance_m=1.2,
        max_height_delta_m=0.75,
        max_backward_step_m=1.2,
        max_yaw_delta_deg=180.0,
        collect_debug_stats=True,
        device=device,
        seed=73,
        verbosity=Verbosity.QUIET,
    )
    config = CandidateMixtureViewGeneratorConfig(
        base=base,
        components=(
            CandidateMixtureComponentConfig(
                name="target_shell",
                count=count,
                center=center,
                gazes=(
                    CandidateGazeConfig(
                        name="primary",
                        mode=ViewDirectionMode.TARGET_POINT,
                        jitter=BoxViewJitterConfig(),
                    ),
                ),
            ),
        ),
    )
    runtime = CandidateGenerationRuntimeContext(descriptor=descriptor)
    generator = config.setup_target()

    first = generator.generate_from_typed_sample(sample, runtime_context=runtime)
    second = generator.generate_from_typed_sample(sample, runtime_context=runtime)

    assert torch.equal(first.shell_poses.tensor(), second.shell_poses.tensor())
    assert torch.equal(first.mask_valid, second.mask_valid)
    assert first.shell_poses.t.shape == (count, 3)
    assert 0 < int(first.mask_valid.sum().item()) < count
    target = runtime.target_center_world.to(first.shell_poses.t.device)
    radii = torch.linalg.norm(first.shell_poses.t - target.reshape(1, 3), dim=1)
    assert float(radii.min()) >= center.radius_min_m - 1e-5
    assert float(radii.max()) <= center.radius_max_m + 1e-5
    assert first.extras["view_jitter_is_bounded"].all()
