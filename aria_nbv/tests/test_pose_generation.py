import sys
from pathlib import Path

import pytest
import torch

# make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[2] / "external" / "efm3d"))

from aria_nbv.configs import PathConfig  # noqa: E402
from aria_nbv.data_handling import AseEfmDatasetConfig  # noqa: E402
from aria_nbv.pose_generation import (  # noqa: E402
    CandidateViewGenerator,
    CandidateViewGeneratorConfig,
    CollisionBackend,
)


def _skip_if_missing_data():
    paths = PathConfig()
    atek_dir = paths.resolve_atek_data_dir("efm")
    if not atek_dir.exists() or not any(atek_dir.glob("**/*.tar")):
        pytest.skip(f"ATEK data dir or shards missing under {atek_dir}", allow_module_level=True)
    mesh_dir = paths.ase_meshes
    if not any(mesh_dir.glob("scene_ply_*.ply")):
        pytest.skip(f"No ASE meshes found under {mesh_dir}", allow_module_level=True)


_skip_if_missing_data()


@pytest.fixture(scope="session")
def path_cfg():
    return PathConfig()


@pytest.fixture(scope="session")
def efm_sample(path_cfg):
    cfg = AseEfmDatasetConfig(
        paths=path_cfg,
        scene_ids=["81283"],
        batch_size=None,
        verbosity=0,
        load_meshes=True,
        require_mesh=False,
        mesh_simplify_ratio=None,
    )
    ds = cfg.setup_target()
    return next(iter(ds))


def test_generator_runs_on_efm_sample(efm_sample):
    gen_cfg = CandidateViewGeneratorConfig(
        num_samples=16,
        max_resamples=1,
        ensure_collision_free=False,  # avoid ray backend dependency
        ensure_free_space=True,
        min_distance_to_mesh=0.0,  # disable proximity rule (rtree)
        device="cpu",
    )
    gen = CandidateViewGenerator(gen_cfg)
    result = gen.generate_from_typed_sample(efm_sample)

    poses = result.poses_world_cam().tensor()
    mask = result.mask_valid
    shell = result.shell_poses
    masks = result.masks

    assert poses.shape[-1] == 12
    assert isinstance(mask, torch.Tensor) and mask.dtype == torch.bool
    assert mask.numel() == poses.shape[0]
    assert shell is not None and shell.tensor().shape[0] > 0
    assert isinstance(masks, dict)
    # At least one valid candidate
    assert mask.sum() > 0


def test_collision_backend_trimesh_enum():
    assert CollisionBackend.TRIMESH.value == "trimesh"
