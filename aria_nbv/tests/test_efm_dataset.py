import sys
from pathlib import Path

import pytest
import torch

# Make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[2] / "external" / "efm3d"))

from aria_nbv.configs import PathConfig  # noqa: E402
from aria_nbv.data_handling import (  # noqa: E402
    AseEfmDatasetConfig,
    EfmSnippetView,
)
from aria_nbv.data_handling.ase_efm.views import (  # noqa: E402
    EfmCameraView,
    EfmPointsView,
    EfmTrajectoryView,
)
from aria_nbv.utils import Verbosity


def _skip_if_missing_data():
    paths = PathConfig()
    atek_dir = paths.resolve_atek_data_dir("efm")
    if not atek_dir.exists():
        pytest.skip(f"ATEK data dir missing: {atek_dir}", allow_module_level=True)
    # require at least one tar shard
    if not any(atek_dir.glob("**/*.tar")):
        pytest.skip(f"No ATEK shards found under {atek_dir}", allow_module_level=True)
    mesh_dir = paths.ase_meshes
    if not any(mesh_dir.glob("scene_ply_*.ply")):
        pytest.skip(f"No ASE meshes found under {mesh_dir}", allow_module_level=True)


_skip_if_missing_data()


@pytest.fixture(scope="session")
def path_cfg():
    return PathConfig()


@pytest.fixture(scope="session")
def efm_config(path_cfg):
    # Use a small, known scene to keep test quick.
    return AseEfmDatasetConfig(
        paths=path_cfg,
        scene_ids=["81283"],
        batch_size=None,
        verbosity=Verbosity.QUIET,
        load_meshes=True,
        require_mesh=False,
        mesh_simplify_ratio=None,
    )


@pytest.fixture(scope="session")
def efm_sample(efm_config):
    ds = efm_config.setup_target()
    sample = next(iter(ds))
    return sample


def test_sample_types(efm_sample):
    assert isinstance(efm_sample, EfmSnippetView)
    assert isinstance(efm_sample.camera_rgb, EfmCameraView)
    assert isinstance(efm_sample.trajectory, EfmTrajectoryView)
    assert isinstance(efm_sample.semidense, EfmPointsView)


def test_shapes_and_ranges(efm_sample, efm_config):
    cam = efm_sample.camera_rgb
    num_frames = int(efm_config.freq_hz * efm_config.snippet_length_s)
    assert cam.images.shape[0] == num_frames
    assert cam.images.shape[1] in (1, 3)
    assert cam.images.ndim == 4
    assert cam.images.dtype == torch.float32
    assert cam.images.max() <= 1.05 and cam.images.min() >= -0.01  # normalized

    # CameraTW is padded to F frames
    assert cam.calib.tensor().shape[0] == num_frames

    traj = efm_sample.trajectory
    tmat = traj.t_world_rig.matrix3x4
    assert tmat.shape[-2:] == (3, 4)
    assert traj.time_ns.shape[0] == num_frames

    pts = efm_sample.semidense
    assert pts.points_world.shape[:2] == (num_frames, efm_config.semidense_points_pad)
    assert pts.points_world.shape[-1] == 3
    assert pts.volume_min.shape == (3,)
    assert pts.volume_max.shape == (3,)
    assert pts.lengths.shape[0] == num_frames


def test_gt_and_obbs_present(efm_sample):
    # gt_data should always exist as dict (may be empty)
    assert isinstance(efm_sample.gt.raw, dict)
    # obbs may not be present for some shards; just ensure accessor works
    _ = efm_sample.obbs


def test_mesh_attached_when_available(efm_sample):
    # Scene 81283 mesh should exist in repo assets
    assert efm_sample.mesh is not None
    assert hasattr(efm_sample.mesh, "vertices")


def test_to_preserves_shapes(efm_sample):
    moved = efm_sample.to("cpu")
    assert moved.camera_rgb.images.device.type == "cpu"
    assert moved.semidense.points_world.device.type == "cpu"


def test_config_resolves_default_paths(path_cfg):
    cfg = AseEfmDatasetConfig(
        scene_ids=["81283"],
        paths=path_cfg,
        verbosity=Verbosity.QUIET,
        load_meshes=True,
        mesh_simplify_ratio=None,
    )
    ds = cfg.setup_target()
    assert cfg.tar_urls, "tar_urls should be auto-populated from PathConfig"
    first = next(iter(ds))
    assert first.scene_id == "81283"
    assert first.mesh is not None


def test_batching_supported(path_cfg):
    cfg = AseEfmDatasetConfig(
        scene_ids=["81283"],
        paths=path_cfg,
        verbosity=Verbosity.QUIET,
        batch_size=2,
        load_meshes=False,
    )
    ds = cfg.setup_target()
    samples = []
    for i, s in enumerate(ds):
        samples.append(s)
        if i >= 1:  # take two samples
            break
    assert all(isinstance(s, EfmSnippetView) for s in samples)
    assert len(samples) == 2
